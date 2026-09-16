"""
Static sequence-domain model used by the auxiliary-signal toy.
Follows the modelling choices of Taylor & Dominguez-Garcia, "Geometry of Distance
Protection" (arXiv:2510.04379): SGs are voltage sources, IBRs are current sources,
uncertainty sets are zonotopes (affine images of a box), the auxiliary signal is a
negative-sequence current injection by the IBR(s).

  bus L (relay, local) --- line z --- bus R (remote)
"""
from dataclasses import dataclass, field
import numpy as np
from scipy.optimize import linprog


@dataclass
class Params:
    name: str = "default"
    z1: complex = 0.02 + 0.20j          # line pos/neg-seq impedance (pu)
    z0_ratio: float = 3.0               # z0 = ratio * z1
    local: str = "SG"                   # "SG" (voltage source) or "IBR" (current source)
    zs: dict = field(default_factory=lambda: {1: 0.05j, 2: 0.05j, 0: 0.10j})  # SG seq impedances
    yld: dict = field(default_factory=lambda: {1: 1/(1.0+0.3j), 2: 1/(1.0+0.3j), 0: 0.0})
    rF: float = 0.30                    # max fault resistance (pu)
    e0: complex = 1.0 + 0j              # nominal SG EMF (if local == SG)
    gen_e: list = field(default_factory=lambda: [0.05, 0.087])   # SG: |e| +-5%, angle +-5 deg
    iL0: complex = 0.9 * np.exp(-1j*np.deg2rad(15))  # nominal local IBR current (if local == IBR)
    i0: complex = 0.9 * np.exp(-1j*np.deg2rad(15))   # nominal remote IBR pos-seq current
    gen_i: list = field(default_factory=lambda: [0.15, 0.30])   # IBR: |i| +-0.15 pu, angle ~+-17 deg
    ibr_neg_z: complex = 1e6            # IBR negative-seq shunt impedance (current source -> open); IEEE 2800 style would be finite
    ibr_zero_z: complex = 0.15j         # zero-seq path at IBR bus (grounded interconnection transformer)
    eps: float = 0.03                   # measurement noise box per real component
    m_grid: tuple = (0.15, 0.35, 0.55, 0.75, 0.95)
    mr_grid: tuple = (0.0, 0.5, 1.0)
    scen: tuple = ("ag", "ab")

    @property
    def z0(self):
        return self.z0_ratio * self.z1


def solve(p: Params, scen, srcL, i_R, delta, m=0.5, mr=0.0):
    """Static sequence-network solve. srcL = SG EMF or local IBR current (per p.local).
    Returns relay measurement y = [vL+, vL-, vL0, iL+, iL-, iL0] (complex)."""
    zl = {1: p.z1, 2: p.z1, 0: p.z0}
    inj = {1: i_R, 2: delta, 0: 0.0}
    Rf = mr * p.rF
    idx = {}
    k = 0
    for s in (1, 2, 0):
        for node in ("L", "F", "R"):
            idx[(s, node)] = k; k += 1
    iF = 9
    A = np.zeros((10, 10), complex); b = np.zeros(10, complex)
    r = 0
    for s in (1, 2, 0):
        L, F, R = idx[(s, "L")], idx[(s, "F")], idx[(s, "R")]
        za, zb = m * zl[s], (1 - m) * zl[s]
        # KCL at L
        if p.local == "SG":
            e = {1: srcL, 2: 0.0, 0: 0.0}[s]
            A[r, L] = -1/p.zs[s] - 1/za; A[r, F] = 1/za; b[r] = -e/p.zs[s]
        else:  # local IBR: pos-seq current source; neg-seq shunt (open by default); zero-seq transformer ground path
            injL = {1: srcL, 2: 0.0, 0: 0.0}[s]
            ysh = {1: 0.0, 2: 1/p.ibr_neg_z, 0: 1/p.ibr_zero_z}[s]
            A[r, L] = -ysh - 1/za; A[r, F] = 1/za; b[r] = -injL
        r += 1
        # KCL at F: (vL - vF)/za + (vR - vF)/zb - If_s = 0
        A[r, L] = 1/za; A[r, F] = -1/za - 1/zb; A[r, R] = 1/zb
        if scen == "ag":
            A[r, iF] = -1.0
        elif scen == "ab":
            A[r, iF] = {1: -1.0, 2: +1.0, 0: 0.0}[s]
        r += 1
        # KCL at R: (vF - vR)/zb - y vR - ysh vR + inj = 0   (remote IBR: neg-seq shunt, zero-seq transformer path)
        yshR = {1: 0.0, 2: 1/p.ibr_neg_z, 0: 1/p.ibr_zero_z}[s]
        A[r, F] = 1/zb; A[r, R] = -1/zb - p.yld[s] - yshR; b[r] = -inj[s]; r += 1
    if scen == "N":
        A[r, iF] = 1.0
    elif scen == "ag":
        for s in (1, 2, 0):
            A[r, idx[(s, "F")]] = 1.0
        A[r, iF] = -3*Rf
    elif scen == "ab":
        A[r, idx[(1, "F")]] = 1.0; A[r, idx[(2, "F")]] = -1.0
        A[r, iF] = -Rf
    x = np.linalg.solve(A, b)
    y = [x[idx[(s, "L")]] for s in (1, 2, 0)]
    for s in (1, 2, 0):
        y.append((x[idx[(s, "L")]] - x[idx[(s, "F")]]) / (m*zl[s]))
    return np.array(y)


def realify(v):
    return np.concatenate([v.real, v.imag])


def source_generators(p: Params):
    """Complex generators (perturbation per unit box coordinate) for local source and remote IBR."""
    if p.local == "SG":
        s0 = p.e0
        gL = [p.gen_e[0]*p.e0, 1j*p.gen_e[1]*p.e0]
    else:
        s0 = p.iL0
        gL = [p.gen_i[0]*(p.iL0/abs(p.iL0)), 1j*p.gen_i[1]*p.iL0]
    gR = [p.gen_i[0]*(p.i0/abs(p.i0)), 1j*p.gen_i[1]*p.i0]
    return s0, gL, gR


def affine_model(p: Params, scen, m=0.5, mr=0.0):
    """y = c0 + H [Re d, Im d] + G u + n,  u in [-1,1]^k, |n_i| <= eps  (real 12-dim)."""
    s0, gL, gR = source_generators(p)
    y00 = solve(p, scen, s0, p.i0, 0.0, m, mr)
    yd = solve(p, scen, s0, p.i0, 1.0, m, mr) - y00
    ydj = solve(p, scen, s0, p.i0, 1j, m, mr) - y00
    gens = [solve(p, scen, s0+g, p.i0, 0.0, m, mr) - y00 for g in gL]
    gens += [solve(p, scen, s0, p.i0+g, 0.0, m, mr) - y00 for g in gR]
    return realify(y00), np.stack([realify(yd), realify(ydj)], 1), np.stack([realify(g) for g in gens], 1)


def separated_lp(cN, GN, cF, GF, eps):
    """True iff the two zonotopes (plus noise boxes) do NOT intersect (LP infeasible)."""
    n = cN.size
    Aeq = np.hstack([GN, -GF, np.eye(n), -np.eye(n)])
    bounds = [(-1, 1)]*(GN.shape[1]+GF.shape[1]) + [(-eps, eps)]*(2*n)
    res = linprog(np.zeros(Aeq.shape[1]), A_eq=Aeq, b_eq=cF-cN, bounds=bounds, method="highs")
    return res.status == 2


class Problem:
    """All pre-test sets for a Params instance; separation queries."""
    def __init__(self, p: Params):
        self.p = p
        self.cN, self.HN, self.GN = affine_model(p, "N")
        self.faults = []
        for scen in p.scen:
            for m in p.m_grid:
                for mr in p.mr_grid:
                    c, H, G = affine_model(p, scen, m, mr)
                    self.faults.append(dict(scen=scen, m=m, mr=mr, c=c, H=H, G=G))

    def unseparated(self, d, which=None):
        """List of fault cases NOT separated from N by delta d."""
        dv = np.array([np.real(d), np.imag(d)])
        cNd = self.cN + self.HN @ dv
        out = []
        for f in self.faults:
            if which and f["scen"] not in which:
                continue
            if not separated_lp(cNd, self.GN, f["c"] + f["H"] @ dv, f["G"], self.p.eps):
                out.append((f["scen"], f["m"], f["mr"]))
        return out

    def separates_all(self, d, which=None):
        return len(self.unseparated(d, which)) == 0


_WEAK = {1: 0.4j, 2: 0.4j, 0: 0.8j}   # weak SG at relay end (8x default source impedance)
PRESETS = {
    # stiff SG at relay end, small uncertainty -> delta=0 already separates (sanity check)
    "easy": Params(name="easy"),
    # sweep-identified: weak SG, inverter uncertainty, noise 0.08, faults up to 1.0 pu resistance
    # -> 2/30 fault cases ambiguous at delta=0, a 0.4 pu negative-seq injection resolves them
    "weak_sg": Params(name="weak_sg", zs=_WEAK, gen_i=[0.3, 0.3], eps=0.08, rF=1.0),
    # same as weak_sg but a noisier relay (0.12 instead of 0.08): expect more ambiguous cases, larger delta
    "weak_sg_eps12": Params(name="weak_sg_eps12", zs=_WEAK, gen_i=[0.3, 0.3], eps=0.12, rF=1.0),
    # sweep-identified: weak SG, wide inverter angle uncertainty, noisier relay (0.15), faults up to 0.3 pu
    # -> 7/30 ambiguous at delta=0, a ~0.8 pu injection resolves
    "weak_sg_noisy": Params(name="weak_sg_noisy", zs=_WEAK, gen_i=[0.3, 1.0], eps=0.15, rF=0.3),
    # both ends inverters (Taylor's hard case: all sources IBRs); moderate settings separate at delta=0
    "all_ibr": Params(name="all_ibr", local="IBR", gen_i=[0.3, 1.0], eps=0.08, rF=0.5),
    # sweep-identified: all IBR, noise 0.15, faults up to 1.0 pu -> 5/30 ambiguous, ~0.8 pu injection resolves
    "all_ibr_hard": Params(name="all_ibr_hard", local="IBR", gen_i=[0.3, 0.3], eps=0.15, rF=1.0),
}
