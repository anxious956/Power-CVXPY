"""
The design and the set test with both frames a real system has (docs/STEP3.md, "the two frames"):

  - the inverter references I1 and delta to its own measured V1 (I1 = i_cmd u, delta = d_cmd u, u = V1_R/|V1_R|,
    i_cmd and d_cmd fixed in that frame), then applies its limiter; V1_R depends on the injections, so the
    delivered state is a fixed point (network.solve_v1ref);
  - the relay references its phasors to its own pre-fault V1 memory (y_rel = y conj(u_L), u_L = V1_L/|V1_L|
    before the fault), frozen during the fault.

Neither is affine in the uncertain sources. Here each case's measurement set is enclosed in a zonotope by a
first-order (Taylor) model in the source symbols plus a remainder box:

    y_rel(s) in  c + J diag(h) w + diag(r) v,   w in [-1, 1]^4 (the four source symbols), v in [-1, 1]^12,

with the Jacobian J at the box centre and r the largest deviation from the linear part over dense samples of the
box (its corners included), times a safety factor. Keeping the source symbols in the linear part keeps the
correlations: the same realisation that moves the relay frame also rotates the inverter's I1 and delta. The
remainder bound is **verified by sampling, not proved** (review/STEP3_PLAN_REVIEW.md §6 point 3), and the
containment check (`containment`) tests it on fresh samples.

The fault-time samples also cover the inverter's frame moving from its pre-fault to its fault angle during the
relay window (its own DFT lags), and an extra drift margin; a case whose |V1_R| falls below `v1_min` has no
usable frame, and its rotation is sampled over the full circle.

The arithmetic is vectorised: in every case the circuit matrix is fixed, the injections only change the right-hand
side, so the relay's measurement and V1 at the inverter bus are fixed linear maps of (EMF, I1, delta), taken from
network.solve with unit injections.
"""
import os, sys
import numpy as np
from scipy.optimize import linprog
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import network as nw

A3 = nw.A3


def unit_maps(net, inj, fault):
    """Linear maps of one case: y = My @ [e, i1, d] and V1 at the inverter bus = mv @ [e, i1, d], for the single
    synchronous source and the single injecting inverter `inj`."""
    (sg,) = list(net.sgs)
    zero = {k: 0.0 for k in list(net.sgs) + list(net.ibrs)}
    cols_y, cols_v = [], []
    for which in ("e", "i1", "d"):
        vals, dels = dict(zero), {}
        if which == "e":
            vals[sg] = 1.0
        elif which == "i1":
            vals[inj] = 1.0
        else:
            dels[inj] = 1.0
        y, V = nw.solve(net, vals, dels, fault, full=True)
        cols_y.append(y)
        cols_v.append(V[net.ibrs[inj].bus][0])
    return np.stack(cols_y, 1), np.array(cols_v)


def limiter_vec(i1, d, i_max, lim=1):
    """network.limiter on arrays."""
    i1, d = np.asarray(i1, complex), np.asarray(d, complex)
    if lim == 1:
        s = np.ones(i1.shape)
        for k in range(3):
            q, r = i1 * A3 ** (-k), d * A3 ** k
            a, b, c = np.abs(q) ** 2, (q * np.conj(r)).real, np.abs(r) ** 2 - i_max ** 2
            ok = (c < 0) & (a > 1e-12)
            sk = np.where(ok, (-b + np.sqrt(np.maximum(b * b - a * c, 0.0))) / np.where(a > 1e-12, a, 1.0), np.inf)
            s = np.minimum(s, sk)
        i1 = np.maximum(s, 0.0) * i1
    peak = np.max(np.stack([np.abs(i1 * A3 ** (-k) + d * A3 ** k) for k in range(3)]), 0)
    sc = np.minimum(1.0, i_max / np.maximum(peak, 1e-12))
    return sc * i1, sc * d


def fixed_point(mv, e, i_cmd, d_cmd, i_max, lim, u0, iters=60, tol=1e-12):
    """Vectorised V1-referenced fixed point: returns (u, i1, d, |V1_R|)."""
    u = u0.copy()
    for _ in range(iters):
        i1, d = limiter_vec(i_cmd * u, d_cmd * u, i_max, lim)
        v = mv[0] * e + mv[1] * i1 + mv[2] * d
        un = v / np.maximum(np.abs(v), 1e-12)
        if np.max(np.abs(un - u)) < tol:
            u = un
            break
        u = un
    i1, d = limiter_vec(i_cmd * u, d_cmd * u, i_max, lim)
    v = mv[0] * e + mv[1] * i1 + mv[2] * d
    return u, i1, d, np.abs(v)


class FrameModel:
    """Normal operation and fault cases at one relay, with both frames, for one injecting inverter.

    The inverter's commanded current i_cmd ranges over the outer sector box around its nominal command
    (the nominal current expressed in the nominal V1_R frame), with the same magnitude / angle spread as
    network.IBR.gen; the synchronous EMF over its outer box, as before."""

    def __init__(self, net, cases, eps=None, lim=1, n_samples=600, safety=1.25, drift_deg=6.0, v1_min=0.05,
                 transient_steps=5, seed=0, shared=True):
        self.net, self.cases, self.lim = net, list(cases), lim
        self.eps = net.eps if eps is None else eps
        (self.inj,) = net.injectors
        (self.sg,) = list(net.sgs)
        g = net.ibrs[self.inj]
        self.i_max = g.i_max or 1.2
        self.n, self.safety, self.drift, self.v1_min, self.steps, self.shared = n_samples, safety, np.radians(drift_deg), \
            v1_min, transient_steps, shared
        self.maps_N = unit_maps(net, self.inj, None)
        self.maps_F = [unit_maps(net, self.inj, (ln, m, s, mr * net.rF)) for ln, m, s, mr in self.cases]
        _, V = nw.solve(net, {}, {}, None, full=True)
        self.u_nom = V[g.bus][0] / abs(V[g.bus][0])
        self.cE, self.gE = nw.source_set(net, "sg", self.sg, "outer")
        cI, gI = nw.source_set(net, "ibr", self.inj, "outer")
        rot = np.conj(self.u_nom)                       # the nominal current, in the inverter's own frame
        self.cI, self.gI = cI * rot, [x * rot for x in gI]
        rng = np.random.default_rng(seed)
        corners = np.array(np.meshgrid(*[[-1.0, 1.0]] * 4)).reshape(4, -1).T
        self.S = np.vstack([corners, rng.uniform(-1, 1, (n_samples, 4))])   # source symbols, (n, 4)

    # ---------------------------------------------------------------- realisations
    def sources(self, S):
        e = self.cE + self.gE[0] * S[:, 0] + self.gE[1] * S[:, 1]
        i_cmd = self.cI + self.gI[0] * S[:, 2] + self.gI[1] * S[:, 3]
        return e, i_cmd

    def normal_state(self, S, d_cmd):
        e, i_cmd = self.sources(S)
        My, mv = self.maps_N
        u, i1, d, v1 = fixed_point(mv, e, i_cmd, d_cmd, self.i_max, self.lim, np.full(len(S), self.u_nom))
        y = My[:, 0][None] * e[:, None] + My[:, 1][None] * i1[:, None] + My[:, 2][None] * d[:, None]
        uL = y[:, 0] / np.abs(y[:, 0])
        return y, uL, u, i1, d

    def measurements(self, S, d_cmd, case=None, transient=True, rng=None):
        """Relay measurements in the relay's own pre-fault frame: (n, 6) for normal (case None) or, for a fault
        case, (n * k, 6) covering the frame's move through the relay window and the drift margin."""
        yN, uL, u_pre, _, _ = self.normal_state(S, d_cmd)
        if case is None:
            return yN * np.conj(uL)[:, None]
        e, i_cmd = self.sources(S)
        My, mv = self.maps_F[case]
        u_f, _, _, v1 = fixed_point(mv, e, i_cmd, d_cmd, self.i_max, self.lim, u_pre)
        lams = np.linspace(0.0, 1.0, self.steps) if transient else np.array([1.0])
        drifts = np.array([-self.drift, 0.0, self.drift]) if self.drift else np.array([0.0])
        out = []
        dead = v1 < self.v1_min
        for lam in lams:
            for dr in drifts:
                uu = (1 - lam) * u_pre + lam * u_f
                uu = uu / np.maximum(np.abs(uu), 1e-12) * np.exp(1j * dr * lam)
                if dead.any():                           # no usable frame: any angle
                    ang = (rng or np.random.default_rng(1)).uniform(0, 2 * np.pi, dead.sum())
                    uu = uu.copy()
                    uu[dead] = np.exp(1j * ang)
                i1, d = limiter_vec(i_cmd * uu, d_cmd * uu, self.i_max, self.lim)
                y = My[:, 0][None] * e[:, None] + My[:, 1][None] * i1[:, None] + My[:, 2][None] * d[:, None]
                out.append(y * np.conj(uL)[:, None])
        return np.vstack(out)

    def dead_frame(self, case, d_cmd):
        e, i_cmd = self.sources(self.S)
        _, _, u_pre, _, _ = self.normal_state(self.S, d_cmd)
        *_, v1 = fixed_point(self.maps_F[case][1], e, i_cmd, d_cmd, self.i_max, self.lim, u_pre)
        return bool((v1 < self.v1_min).any())

    # ---------------------------------------------------------------- zonotopes
    def zonotope(self, d_cmd, case=None):
        """(c, G) real 12-dim with G = [J diag(h) | diag(r)] (shared source symbols, then remainder)."""
        S0 = np.zeros((1, 4))
        fn = (lambda S: self.measurements(S, d_cmd, case, transient=False)) if case is not None else \
             (lambda S: self.measurements(S, d_cmd, None))
        c = nw._realify(fn(S0)[0])
        J = np.zeros((12, 4))
        hstep = 1e-4
        for k in range(4):
            Sp, Sm = S0.copy(), S0.copy()
            Sp[0, k] += hstep
            Sm[0, k] -= hstep
            J[:, k] = (nw._realify(fn(Sp)[0]) - nw._realify(fn(Sm)[0])) / (2 * hstep)
        Y = self.measurements(self.S, d_cmd, case)
        reps = len(Y) // len(self.S)
        Sx = np.tile(self.S, (reps, 1))
        R = np.stack([nw._realify(y) for y in Y]) - c[None] - Sx @ J.T
        r = np.abs(R).max(0) * self.safety + 1e-9
        if not self.shared:                              # ablation: no shared symbols, everything in the box
            r = np.abs(np.stack([nw._realify(y) for y in Y]) - c[None]).max(0) * self.safety + 1e-9
            return c, np.diag(r)
        return c, np.hstack([J, np.diag(r)])

    def sets(self, d_cmd):
        return self.zonotope(d_cmd, None), [self.zonotope(d_cmd, k) for k in range(len(self.cases))]


def _meet(cN, GN, cF, GF, bound):
    """Do N + box(bound) and F intersect? (LP feasibility; bound = 2 eps for two noisy sets)."""
    n = cN.size
    Aeq = np.hstack([GN, -GF, np.eye(n)])
    res = linprog(np.zeros(Aeq.shape[1]), A_eq=Aeq, b_eq=cF - cN,
                  bounds=[(-1, 1)] * (GN.shape[1] + GF.shape[1]) + [(-bound, bound)] * n, method="highs")
    return res.status == 0


def separated(fm: FrameModel, d_cmd, rho=0.0, sets=None):
    (cN, GN), F = sets or fm.sets(d_cmd)
    b = 2 * fm.eps * (1 + rho)
    return all(not _meet(cN, GN, c, G, b) for c, G in F)


def unseparated(fm: FrameModel, d_cmd, rho=0.0):
    (cN, GN), F = fm.sets(d_cmd)
    b = 2 * fm.eps * (1 + rho)
    return [fm.cases[k] for k, (c, G) in enumerate(F) if _meet(cN, GN, c, G, b)]


def min_delta(fm: FrameModel, rho=0.0, r_step=0.02, n_ang=72, r_max=1.2):
    """Smallest separating command |d_cmd| on a polar grid (each LP exact at its d_cmd; not convex in d_cmd)."""
    for r in np.arange(0.0, r_max + 1e-9, r_step):
        for a in (np.linspace(0, 2 * np.pi, n_ang, endpoint=False) if r > 0 else [0.0]):
            d = r * np.exp(1j * a)
            if separated(fm, d, rho):
                return dict(d_cmd=complex(d), abs_delta=float(r), angle_deg=float(np.degrees(a)), feasible=True)
    return dict(d_cmd=None, abs_delta=None, angle_deg=None, feasible=False)


def distance_to_normal(fm: FrameModel, y_rel, d_cmd, setN=None):
    """D1: the smallest noise box (pu) that puts a relay measurement (in the relay's own frame) inside N."""
    cN, GN = setN or fm.zonotope(d_cmd, None)
    n, k = cN.size, GN.shape[1]
    target = nw._realify(np.asarray(y_rel)) - cN
    c = np.zeros(k + n + 1)
    c[-1] = 1
    A_ub = np.vstack([np.hstack([np.zeros((n, k)), np.eye(n), -np.ones((n, 1))]),
                      np.hstack([np.zeros((n, k)), -np.eye(n), -np.ones((n, 1))])])
    res = linprog(c, A_ub=A_ub, b_ub=np.zeros(2 * n), A_eq=np.hstack([GN, np.eye(n), np.zeros((n, 1))]), b_eq=target,
                  bounds=[(-1, 1)] * k + [(None, None)] * n + [(0, None)], method="highs")
    if res.status != 0:
        raise RuntimeError(f"distance_to_normal: LP failed ({res.message})")
    return res.x[-1]


def containment(fm: FrameModel, d_cmd, n_fresh=400, seed=7):
    """Fresh (A) samples, normal and every case, through the transient window: the largest noise needed to put a
    sample inside its own set (0 = contained). Returns {case or 'N': max distance}."""
    rng = np.random.default_rng(seed)
    S = rng.uniform(-1, 1, (n_fresh, 4))
    out = {}
    for case in [None] + list(range(len(fm.cases))):
        c, G = fm.zonotope(d_cmd, case)
        Y = fm.measurements(S, d_cmd, case)
        worst = 0.0
        for y in Y[:: max(1, len(Y) // 200)]:
            worst = max(worst, distance_to_normal(fm, y, d_cmd, (c, G)))
        out["N" if case is None else fm.cases[case]] = worst
    return out


def separated_fast(fm: FrameModel, d_cmd, rho=0.0, order=None):
    """As separated(), but builds the fault sets lazily, hardest cases first (`order`), and stops at the first
    case that meets the normal set. Same answer, much less work for candidates that fail."""
    cN, GN = fm.zonotope(d_cmd, None)
    b = 2 * fm.eps * (1 + rho)
    for k in (order or range(len(fm.cases))):
        c, G = fm.zonotope(d_cmd, k)
        if _meet(cN, GN, c, G, b):
            return False
    return True


def min_delta_fast(fm: FrameModel, rho=0.0, coarse=(0.1, 24), fine=(0.02, 72), r_max=1.2):
    """Coarse polar grid to the first separating radius, then the fine grid from one coarse step below it.
    Reports the fine-grid answer. Hardest cases (unseparated at d = 0) are tried first."""
    hard = set(map(tuple, unseparated(fm, 0j, rho)))
    order = [k for k, c in enumerate(fm.cases) if tuple(c) in hard] + [k for k, c in enumerate(fm.cases) if tuple(c) not in hard]
    if not hard:
        return dict(d_cmd=0j, abs_delta=0.0, angle_deg=0.0, feasible=True)
    r0 = None
    for r in np.arange(coarse[0], r_max + 1e-9, coarse[0]):
        if any(separated_fast(fm, r * np.exp(1j * a), rho, order) for a in np.linspace(0, 2 * np.pi, coarse[1], endpoint=False)):
            r0 = r
            break
    start = max(fine[0], (r0 - coarse[0]) if r0 is not None else r_max - coarse[0])
    for r in np.arange(start, r_max + 1e-9, fine[0]):
        for a in np.linspace(0, 2 * np.pi, fine[1], endpoint=False):
            d = r * np.exp(1j * a)
            if separated_fast(fm, d, rho, order):
                return dict(d_cmd=complex(d), abs_delta=float(round(r, 6)), angle_deg=float(np.degrees(a)), feasible=True,
                            coarse_first=None if r0 is None else float(r0))
    return dict(d_cmd=None, abs_delta=None, angle_deg=None, feasible=False)
