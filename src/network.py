"""
The design tool for a multi-bus network (step 1 of the plan presented to Prof. Taylor).

aux_model.py solves one fixed circuit: a source, one line, an inverter at the far bus. This module solves
any network given as buses, lines, synchronous sources, inverters and loads, in the same conventions
(per unit, sequence domain, synchronous sources as EMFs behind sequence impedances, inverters as current
sources, the auxiliary signal = negative-sequence current injected by an inverter; Taylor &
Dominguez-Garcia, "Geometry of Distance Protection", arXiv 2510.04379):

  - solve()         nodal sequence networks with one shunt fault (ag, ab) at a fraction m along any line,
                    and the relay's six measurements [v+, v-, v0, i+, i-, i0] at one line end;
  - affine_case()   the measurement as an affine map of every uncertain source (zonotope generators,
                    the sound outer sector box or the linearised one, as wp1_common.source_sets) and of
                    the auxiliary signals of every injecting inverter: the uncertainty sets of all
                    sources are aggregated by Minkowski sum, i.e. their generators are stacked;
  - NetModelSet     normal operation and every fault case, with the same .faults / .pair interface as
                    review/wp1_common.ModelSet, so review/tac25_design.separated_at runs on it unchanged;
  - limit_rows()    the per-phase current limit of an injecting inverter (rule "phase") on both blocks,
                    with the fault block's sign handled (ModelSet.pair gives it as -u_F; REVIEW.md row 49);
  - min_delta()     the smallest separating signal of one injecting inverter on a polar grid.

Checked against both hand-written models: the two-bus aux_model.solve and the three-bus
zone_model.solve_zone reproduce to machine precision (tests/test_network.py).
"""
from dataclasses import dataclass, field
import os, sys
import numpy as np
from scipy.optimize import linprog

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "review"))
from wp1_common import sector_linear, sector_linear_rel, sector_outer_box  # noqa: E402

SEQ = (1, 2, 0)
A3 = np.exp(2j * np.pi / 3)


@dataclass
class Line:
    a: str
    b: str
    z1: complex
    z0: complex


@dataclass
class SG:
    bus: str
    zs: dict                                   # {1: z, 2: z, 0: z}
    e0: complex = 1.0 + 0j
    gen: tuple = (0.05, 0.087)                 # |e| +- fraction, angle +- rad


@dataclass
class IBR:
    bus: str
    i0: complex
    gen: tuple = (0.3, 0.3)                    # |i| +- pu, angle +- rad
    neg_z: complex = 1e6                       # negative-sequence shunt (current source: open)
    zero_z: complex = 1e6                      # zero-sequence path (grounded transformer: finite)
    inject: bool = False                       # carries an auxiliary signal
    i_max: float = None                        # per-phase limit for the design (None: no limit)


@dataclass
class Network:
    lines: dict                                # name -> Line
    sgs: dict = field(default_factory=dict)    # name -> SG
    ibrs: dict = field(default_factory=dict)   # name -> IBR
    loads: dict = field(default_factory=dict)  # bus -> {1: y, 2: y, 0: y}
    relay: tuple = None                        # (line name, end "a" or "b")
    eps: float = 0.08
    rF: float = 1.0

    @property
    def buses(self):
        b = []
        for ln in self.lines.values():
            for x in (ln.a, ln.b):
                if x not in b:
                    b.append(x)
        return b

    @property
    def sources(self):
        """Uncertain sources in generator order: synchronous EMFs, then inverter currents."""
        return [("sg", k) for k in self.sgs] + [("ibr", k) for k in self.ibrs]

    @property
    def injectors(self):
        return [k for k, v in self.ibrs.items() if v.inject]


def solve(net: Network, values=None, deltas=None, fault=None, full=False):
    """Sequence solve. values: {source name: EMF or inverter positive-sequence current} (default: nominal);
    deltas: {inverter name: auxiliary signal}; fault: None or (line, m, scen, Rf) with m measured from the
    line's end "a", scen "ag" or "ab" (the phase-phase fault symmetric about phase A), Rf in pu.
    Returns the relay's [v+, v-, v0, i+, i-, i0], the current flowing from the relay bus into its line;
    with full=True also {node: (v+, v-, v0)} for every bus (and "F")."""
    values, deltas = values or {}, deltas or {}
    nodes = list(net.buses)
    lines = dict(net.lines)
    if fault is not None:
        fl, m, scen, rf = fault
        if not 0.0 < m < 1.0:
            raise ValueError(f"fault position m = {m} must lie strictly inside the line (0 < m < 1)")
        ln = lines.pop(fl)
        nodes.append("F")
        lines["_fa"] = Line(ln.a, "F", m * ln.z1, m * ln.z0)
        lines["_fb"] = Line("F", ln.b, (1 - m) * ln.z1, (1 - m) * ln.z0)
    else:
        scen, rf = "N", 0.0
    n = len(nodes)
    ix = {nd: k for k, nd in enumerate(nodes)}
    N = 3 * n + 1
    A = np.zeros((N, N), complex)
    b = np.zeros(N, complex)
    for si, s in enumerate(SEQ):
        o = si * n
        for ln in lines.values():
            y = 1.0 / (ln.z0 if s == 0 else ln.z1)
            i, j = o + ix[ln.a], o + ix[ln.b]
            A[i, i] += y; A[j, j] += y; A[i, j] -= y; A[j, i] -= y
        for name, g in net.sgs.items():
            k = o + ix[g.bus]
            A[k, k] += 1.0 / g.zs[s]
            if s == 1:
                b[k] += values.get(name, g.e0) / g.zs[s]
        for name, g in net.ibrs.items():
            k = o + ix[g.bus]
            A[k, k] += {1: 0.0, 2: 1.0 / g.neg_z, 0: 1.0 / g.zero_z}[s]
            b[k] += {1: values.get(name, g.i0), 2: deltas.get(name, 0.0), 0: 0.0}[s]
        for bus, y in net.loads.items():
            A[o + ix[bus], o + ix[bus]] += y[s]
        if fault is not None:
            fc = 1.0 if scen == "ag" else {1: 1.0, 2: -1.0, 0: 0.0}[s]   # fault current leaving node F
            A[o + ix["F"], 3 * n] = fc
    r = 3 * n
    if fault is None:
        A[r, 3 * n] = 1.0
    elif scen == "ag":
        for si in range(3):
            A[r, si * n + ix["F"]] = 1.0
        A[r, 3 * n] = -3 * rf
    elif scen == "ab":
        A[r, 0 * n + ix["F"]] = 1.0
        A[r, 1 * n + ix["F"]] = -1.0
        A[r, 3 * n] = -rf
    else:
        raise ValueError(scen)
    x = np.linalg.solve(A, b)
    rl, end = net.relay
    ln = net.lines[rl]
    here, there = (ln.a, ln.b) if end == "a" else (ln.b, ln.a)
    if fault is not None and fault[0] == rl:
        seg = lines["_fa"] if end == "a" else lines["_fb"]
        there = "F"
        z = seg
    else:
        z = ln
    v = [x[si * n + ix[here]] for si in range(3)]
    i = [(x[si * n + ix[here]] - x[si * n + ix[there]]) / (z.z0 if s == 0 else z.z1) for si, s in enumerate(SEQ)]
    y = np.array(v + i)
    if full:
        return y, {nd: tuple(x[si * n + ix[nd]] for si in range(3)) for nd in nodes}
    return y


def _realify(v):
    return np.concatenate([v.real, v.imag])


def source_set(net: Network, kind, name, mode="outer"):
    """(centre, [generator, generator]) of one source's uncertainty set (as wp1_common.source_sets)."""
    if kind == "sg":
        g = net.sgs[name]
        if mode == "linear":
            return sector_linear_rel(g.e0, g.gen[0], g.gen[1])
        r = abs(g.e0)
        return sector_outer_box(g.e0, r * (1 - g.gen[0]), r * (1 + g.gen[0]), g.gen[1])
    g = net.ibrs[name]
    if mode == "linear":
        return sector_linear(g.i0, g.gen[0], g.gen[1])
    r = abs(g.i0)
    return sector_outer_box(g.i0, r - g.gen[0], r + g.gen[0], g.gen[1])


def affine_case(net: Network, fault=None, mode="outer"):
    """y = c + H [Re d_1, Im d_1, Re d_2, ...] + G u, u in [-1, 1]^k (real 12-dim; generators of all
    sources stacked = Minkowski sum of their sets)."""
    centres = {nm: source_set(net, kd, nm, mode)[0] for kd, nm in net.sources}
    y00 = solve(net, centres, {}, fault)
    H = []
    for inj in net.injectors:
        for d in (1.0, 1j):
            H.append(_realify(solve(net, centres, {inj: d}, fault) - y00))
    G = []
    for kd, nm in net.sources:
        c, gens = source_set(net, kd, nm, mode)
        for g in gens:
            G.append(_realify(solve(net, {**centres, nm: c + g}, {}, fault) - y00))
    H = np.stack(H, 1) if H else np.zeros((12, 0))
    return _realify(y00), H, np.stack(G, 1)


class NetModelSet:
    """Normal operation and the fault cases at one relay; interface of review/wp1_common.ModelSet."""

    def __init__(self, net: Network, cases, mode="outer", eps=None):
        self.net, self.mode = net, mode
        self.eps = net.eps if eps is None else eps
        self.N = affine_case(net, None, mode)
        self.faults = [((ln, float(m), scen, float(mr)), affine_case(net, (ln, m, scen, mr * net.rF), mode))
                       for ln, m, scen, mr in cases]

    def pair(self, f):
        (cN, HN, GN), (cF, HF, GF) = self.N, f[1]
        return cF - cN, HF - HN, np.hstack([GN, GF])

    def generator_columns(self, name):
        """Columns of one source's two generators within a block."""
        k = [nm for _, nm in self.net.sources].index(name)
        return 2 * k, 2 * k + 1


def limit_rows(ms: NetModelSet, inj, dv, n_poly=24):
    """rows(n_u_block) -> (A, b): every phase current of inverter `inj`, |i+ + a^k dv| <= i_max, on both
    blocks; circumscribed polygons (sound). Block 0 is +u_N, block 1 is -u_F (ModelSet.pair)."""
    g = ms.net.ibrs[inj]
    c, gens = source_set(ms.net, "ibr", inj, ms.mode)
    c0, c1 = ms.generator_columns(inj)

    def rows(k):
        R, rhs = [], []
        for kk in range(3):
            ck = c + A3 ** kk * dv
            for th in np.linspace(0, 2 * np.pi, n_poly, endpoint=False):
                e = np.exp(-1j * th)
                for blk, sg in ((0, 1.0), (1, -1.0)):
                    a = np.zeros(2 * k)
                    a[blk * k + c0] = sg * (gens[0] * e).real
                    a[blk * k + c1] = sg * (gens[1] * e).real
                    R.append(a)
                    rhs.append(g.i_max - (ck * e).real)
        return np.array(R), np.array(rhs)
    return rows


def separated(ms: NetModelSet, dv, eps_eff=None, limit=None):
    """Every fault case separated from normal operation at signal dv (complex: one injector; or a vector
    [Re d_1, Im d_1, ...])."""
    eps_eff = ms.eps if eps_eff is None else eps_eff
    d = np.array([dv.real, dv.imag]) if np.isscalar(dv) else np.asarray(dv, float)
    for f in ms.faults:
        dc, dH, G = ms.pair(f)
        n, k2 = G.shape
        beq = dc + (dH @ d if dH.shape[1] else 0.0)
        Aeq = np.hstack([G, np.eye(n)])
        bounds = [(-1, 1)] * k2 + [(-2 * eps_eff, 2 * eps_eff)] * n
        kw = {}
        if limit is not None:
            A, b = limit(k2 // 2)
            kw = dict(A_ub=np.hstack([A, np.zeros((A.shape[0], n))]), b_ub=b)
        res = linprog(np.zeros(k2 + n), A_eq=Aeq, b_eq=beq, bounds=bounds, method="highs", **kw)
        if res.status != 2:
            return False
    return True


def unseparated(ms: NetModelSet, dv=0j, eps_eff=None, limit=None):
    out = []
    for f in ms.faults:
        sub = NetModelSet.__new__(NetModelSet)
        sub.net, sub.mode, sub.eps, sub.N, sub.faults = ms.net, ms.mode, ms.eps, ms.N, [f]
        if not separated(sub, dv, eps_eff, limit):
            out.append(f[0])
    return out


def min_delta(ms: NetModelSet, rho=0.0, r_step=0.02, n_ang=72, r_max=2.0, limit_inside=True):
    """Smallest separating signal of the single injecting inverter, on a polar grid (global, as
    review/tac25_design.min_delta). limit_inside: prune the uncertainty set with the inverter's
    per-phase limit at each candidate (rule "phase"); candidates beside which no modelled current fits
    are skipped."""
    (inj,) = ms.net.injectors
    eps_eff = ms.eps * (1 + rho)
    use_lim = limit_inside and ms.net.ibrs[inj].i_max is not None
    for r in np.arange(0.0, r_max + 1e-9, r_step):
        for a in (np.linspace(0, 2 * np.pi, n_ang, endpoint=False) if r > 0 else [0.0]):
            dv = r * np.exp(1j * a)
            lim = limit_rows(ms, inj, dv) if use_lim else None
            if lim is not None and not _limit_feasible(ms, inj, dv):
                continue
            if separated(ms, dv, eps_eff, lim):
                return dict(delta=complex(dv), abs_delta=float(r), angle_deg=float(np.degrees(a)), feasible=True)
    return dict(delta=None, abs_delta=None, angle_deg=None, feasible=False)


def _limit_feasible(ms, inj, dv):
    """Does any modelled current of `inj` fit beside dv?"""
    A, b = limit_rows(ms, inj, dv)(len(ms.net.sources) * 2)
    k = len(ms.net.sources) * 2
    A = A[0::2, :k]
    b = b[0::2]
    res = linprog(np.zeros(k), A_ub=A, b_ub=b, bounds=[(-1, 1)] * k, method="highs")
    return res.status == 0


def closest(ms: NetModelSet, f, dv=0j, limit=None):
    """Closest approach of fault set f to the normal set at signal dv: (u_N, u_F, combined noise), u_F the
    fault realisation's box coordinates (sign undone: ModelSet.pair gives the fault block as -u_F). The
    case is ambiguous iff the noise is <= 2 eps."""
    dc, dH, G = ms.pair(f)
    d = np.array([dv.real, dv.imag]) if np.isscalar(dv) else np.asarray(dv, float)
    target = dc + (dH @ d if dH.shape[1] else 0.0)
    n, k2 = G.shape
    c = np.zeros(k2 + n + 1)
    c[-1] = 1
    A_ub = [np.hstack([np.zeros((n, k2)), np.eye(n), -np.ones((n, 1))]),
            np.hstack([np.zeros((n, k2)), -np.eye(n), -np.ones((n, 1))])]
    b_ub = [np.zeros(n), np.zeros(n)]
    if limit is not None:
        A, b = limit(k2 // 2)
        A_ub.append(np.hstack([A, np.zeros((A.shape[0], n + 1))]))
        b_ub.append(b)
    res = linprog(c, A_ub=np.vstack(A_ub), b_ub=np.concatenate(b_ub), A_eq=np.hstack([G, np.eye(n), np.zeros((n, 1))]),
                  b_eq=target, bounds=[(-1, 1)] * k2 + [(None, None)] * n + [(0, None)], method="highs")
    if res.status != 0:
        raise RuntimeError(f"closest(): LP failed for {f[0]} ({res.message})")
    k = k2 // 2
    return res.x[:k], -res.x[k:k2], res.x[-1]


def realisation(net: Network, u, mode="outer"):
    """{source: value} at box coordinates u (two per source, in net.sources order)."""
    out = {}
    for j, (kd, nm) in enumerate(net.sources):
        c, g = source_set(net, kd, nm, mode)
        out[nm] = c + g[0] * u[2 * j] + g[1] * u[2 * j + 1]
    return out


def noise_to_normal(ms: NetModelSet, y, dv=0j, limit=None):
    """Smallest noise box (pu) that puts a measurement y (complex 6-vector) inside the normal set N(dv),
    restricted by `limit` on the normal block. A clean measurement against N plus its own eps: a fault is
    told from normal operation iff this exceeds 2 eps; a normal measurement should give ~0."""
    cN, HN, GN = ms.N
    d = np.array([dv.real, dv.imag]) if np.isscalar(dv) else np.asarray(dv, float)
    target = _realify(np.asarray(y)) - (cN + (HN @ d if HN.shape[1] else 0.0))
    n, k = target.size, GN.shape[1]
    c = np.zeros(k + n + 1)
    c[-1] = 1
    A_ub = [np.hstack([np.zeros((n, k)), np.eye(n), -np.ones((n, 1))]),
            np.hstack([np.zeros((n, k)), -np.eye(n), -np.ones((n, 1))])]
    b_ub = [np.zeros(n), np.zeros(n)]
    if limit is not None:
        A, b = limit(k)
        A = A[0::2, :k]                                   # normal block only
        A_ub.append(np.hstack([A, np.zeros((A.shape[0], n + 1))]))
        b_ub.append(b[0::2])
    res = linprog(c, A_ub=np.vstack(A_ub), b_ub=np.concatenate(b_ub), A_eq=np.hstack([GN, np.eye(n), np.zeros((n, 1))]),
                  b_eq=target, bounds=[(-1, 1)] * k + [(None, None)] * n + [(0, None)], method="highs")
    if res.status != 0:
        # an infeasible set (the limit leaves no modelled current beside dv) or a solver failure: never read it
        # as "infinitely far", which a caller would take for a certain fault (review finding 9)
        raise RuntimeError(f"noise_to_normal(): LP failed ({res.message})")
    return res.x[-1]


def limiter(i1, d, i_max, lim=1):
    """The EMT inverter's limiter (src/pscad_inverter.py): LIM 1 keeps d and scales i1 so every phase
    |i1 a^-k + d a^k| fits; then (and for LIM 0) both scaled by i_max / peak if still over."""
    if lim == 1:
        s = 1.0
        for k in range(3):
            q, r = i1 * A3 ** (-k), d * A3 ** k
            a, b, cc = abs(q) ** 2, (q * np.conj(r)).real, abs(r) ** 2 - i_max ** 2
            if cc < 0 and a > 1e-12:
                s = min(s, (-b + np.sqrt(b * b - a * cc)) / a)
        i1 = max(s, 0.0) * i1
    peak = max(abs(i1 * A3 ** (-k) + d * A3 ** k) for k in range(3))
    sc = min(1.0, i_max / peak)
    return sc * i1, sc * d
