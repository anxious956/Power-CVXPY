"""
Taylor's IEEE 14-bus auxiliary-signal design (Taylor & Dominguez-Garcia, "Geometry of Distance Protection",
arXiv 2510.04379, §IV-C, §V, §VI-D, Appendices A-C), rebuilt to check our optimization against his numbers
(docs/IEEE14.md).

  - net_matrices()  Appendix A: phase-domain nodal model with a virtual fault bus F at m̂_z on the relay line;
                    Gamma (i_L), Theta (i_R), Phi (v_L), Psi (v_R) as linear maps of the source vector
                    x = [i_C; v_S] (three phases per source), for N and the six LG/LL models;
  - models()        psi, Omega_z, Omega_r (§V) per fault model, Omega^N for normal operation;
  - separated()     Lemma 7: the pair's relaxed intersection (W^{Rel,3}, polyhedral noise) is empty, tested on
                    the primal as one linear feasibility problem (empty <=> the Farkas dual of App. C-A is
                    nonempty). variant "literal" (as printed) or "sound" (docs/IEEE14.md V3);
  - grid()          §VI-D1: a common signal delta at every IBR on a grid of the complex plane.

    python src/ieee14.py q1 [--variant literal|sound] [--noise neg|pos] [--charging] [--endpoint-off] [--z0 3]
"""
import argparse, json, os, sys
import numpy as np
from scipy.optimize import linprog

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "results", "ieee14")

AL = np.exp(2j * np.pi / 3)
A = np.array([[1, 1, 1], [1, AL ** 2, AL], [1, AL, AL ** 2]])     # [zero, positive, negative] -> phases
B_NEG = A[:, 2]                                                   # [1, a, a^2]: the paper's noise direction
B_POS = A[:, 1]
EA, EB, EC = np.eye(3)
E0 = np.ones(3) / 3

# standard IEEE 14-bus branches, per unit on 100 MVA: (from, to, R, X, B)
BRANCHES = [
    (1, 2, 0.01938, 0.05917, 0.0528), (1, 5, 0.05403, 0.22304, 0.0492), (2, 3, 0.04699, 0.19797, 0.0438),
    (2, 4, 0.05811, 0.17632, 0.0340), (2, 5, 0.05695, 0.17388, 0.0346), (3, 4, 0.06701, 0.17103, 0.0128),
    (4, 5, 0.01335, 0.04211, 0.0), (4, 7, 0.0, 0.20912, 0.0), (4, 9, 0.0, 0.55618, 0.0),
    (5, 6, 0.0, 0.25202, 0.0), (6, 11, 0.09498, 0.19890, 0.0), (6, 12, 0.12291, 0.25581, 0.0),
    (6, 13, 0.06615, 0.13027, 0.0), (7, 8, 0.0, 0.17615, 0.0), (7, 9, 0.0, 0.11001, 0.0),
    (9, 10, 0.03181, 0.08450, 0.0), (9, 14, 0.12711, 0.27038, 0.0), (10, 11, 0.08205, 0.19207, 0.0),
    (12, 13, 0.22092, 0.19988, 0.0), (13, 14, 0.17093, 0.34802, 0.0),
]
RELAY = (2, 3)                                   # relay at bus 2 on line 2-3
FAULTS = ["ag", "bg", "cg", "ab", "bc", "ca"]
PH = {"a": EA, "b": EB, "c": EC}


def case(which="vid", endpoint=True):
    """Sources and loads. 'vid': §VI-D, all seven sources IBRs; 'ivc': §IV-C, four SGs and five IBRs."""
    n_ang = lambda k, top: np.linspace(0, top, k) if endpoint else np.linspace(0, top, k + 1)[:k]
    if which == "vid":
        ibr, sg = [1, 2, 3, 4, 5, 8, 14], []
        sigma = 1.0
    else:
        ibr, sg = [2, 4, 7, 8, 12], [1, 3, 5, 14]
        sigma = 0.1
    return dict(ibr=ibr, sg=sg, i0=np.exp(1j * n_ang(len(ibr), 2 * np.pi / 3)),
                e0=np.exp(1j * n_ang(len(sg), 2 * np.pi / 10)) if sg else np.zeros(0),
                loads={b: 0.1 + 0.01j for b in (6, 10, 11, 13)}, sigma=sigma)


def _zabc(z1, z0):
    return A @ np.diag([z0, z1, z1]) @ np.linalg.inv(A)


def fault_admittance(eta, rf):
    """3x3 admittance of fault model eta at F (i into the fault = Y v_F); eta None for normal operation."""
    Y = np.zeros((3, 3), complex)
    if eta is None:
        return Y
    if eta[1] == "g":
        k = "abc".index(eta[0])
        Y[k, k] = 1.0 / rf
    else:
        i, j = "abc".index(eta[0]), "abc".index(eta[1])
        Y[np.ix_([i, j], [i, j])] = np.array([[1, -1], [-1, 1]]) / rf
    return Y


def net_matrices(cs, eta, mz_hat=0.5, mr_hat=0.5, rF=1.0, charging=False, z0_ratio=1.0):
    """Appendix A for model eta (None: normal operation). Returns Gamma, Theta, Phi, Psi (3 x 3ns each) with
    i_L = Gamma x, i_R = Theta x, v_L = Phi x, v_R = Psi x, x = [i_C; v_S] in bus order within each group."""
    nodes = list(range(1, 15)) + ["F"]
    ix = {nd: k for k, nd in enumerate(nodes)}
    N = 3 * len(nodes)
    Y = np.zeros((N, N), complex)

    def add_branch(a, b, z1, bsh=0.0):
        Yb = np.linalg.inv(_zabc(z1, z0_ratio * z1))
        ia, ib = slice(3 * ix[a], 3 * ix[a] + 3), slice(3 * ix[b], 3 * ix[b] + 3)
        Y[ia, ia] += Yb; Y[ib, ib] += Yb; Y[ia, ib] -= Yb; Y[ib, ia] -= Yb
        if bsh:
            for s in (ia, ib):
                Y[s, s] += 0.5j * bsh * np.eye(3)
    zrel = None
    for a, b, r, x, bsh in BRANCHES:
        z = complex(r, x)
        bsh = bsh if charging else 0.0
        if (a, b) == RELAY:
            zrel = z
            add_branch(a, "F", mz_hat * z, mz_hat * bsh)
            add_branch("F", b, (1 - mz_hat) * z, (1 - mz_hat) * bsh)
        else:
            add_branch(a, b, z, bsh)
    for bus, y in cs["loads"].items():
        s = slice(3 * ix[bus], 3 * ix[bus] + 3)
        Y[s, s] += y * np.eye(3)
    sF = slice(3 * ix["F"], 3 * ix["F"] + 3)
    Y[sF, sF] += fault_admittance(eta, mr_hat * rF)

    ibr, sg = cs["ibr"], cs["sg"]
    nx = 3 * (len(ibr) + len(sg))
    known = [3 * ix[b] + p for b in sg for p in range(3)]
    unk = [k for k in range(N) if k not in known]
    # unknown voltages: Y_uu v_u = I_C i_C - Y_uk v_S
    rhs = np.zeros((len(unk), nx), complex)
    pos = {k: r for r, k in enumerate(unk)}
    for c, b in enumerate(ibr):
        for p in range(3):
            rhs[pos[3 * ix[b] + p], 3 * c + p] = 1.0
    if sg:
        rhs[:, 3 * len(ibr):] = -Y[np.ix_(unk, known)]
    Vu = np.linalg.solve(Y[np.ix_(unk, unk)], rhs)
    V = np.zeros((N, nx), complex)
    V[unk] = Vu
    for c, k in enumerate(known):
        V[k, 3 * len(ibr) + c] = 1.0
    aleph = lambda nd: V[3 * ix[nd]: 3 * ix[nd] + 3]
    L, R = RELAY
    Phi, Psi, AF = aleph(L), aleph(R), aleph("F")
    ZL = _zabc(mz_hat * zrel, z0_ratio * mz_hat * zrel)
    ZR = _zabc((1 - mz_hat) * zrel, z0_ratio * (1 - mz_hat) * zrel)
    Gamma = np.linalg.solve(ZL, Phi - AF)        # = (Phi - aleph_F)/(m̂_z z) when z0_ratio = 1
    Theta = np.linalg.solve(ZR, Psi - AF)
    return dict(Gamma=Gamma, Theta=Theta, Phi=Phi, Psi=Psi, z=zrel)


def models(cs, k=2.0, rF=1.0, **kw):
    """psi, Omega_z, Omega_r per fault model (§V-A, V-B), and Omega^N, Gamma^N (§V-C)."""
    out = {}
    nm = net_matrices(cs, None, rF=rF, **kw)
    out["N"] = dict(psi=np.eye(3), Omega=nm["z"] * nm["Gamma"] + nm["Psi"], Gamma=nm["Gamma"])
    for eta in FAULTS:
        m = net_matrices(cs, eta, rF=rF, **kw)
        z, G, T = m["z"], m["Gamma"], m["Theta"]
        if eta[1] == "g":
            e = PH[eta[0]]
            psi, Oz, Or = e, z * (e + k * E0) @ G, rF * e @ (G + T)
        else:
            e = PH[eta[0]] - PH[eta[1]]
            psi, Oz, Or = e, z * e @ G, 0.5 * rF * e @ (G + T)
        out[eta] = dict(psi=psi[None, :], Oz=Oz[None, :], Or=Or[None, :], Gamma=G)
    return out


def polygon_P(n_phi=20):
    """H-representation rows of the regular n-gon Re[e^{-j phi_l} lam] <= 1, in (Re lam, Im lam)."""
    phi = 2 * np.pi * np.arange(1, n_phi + 1) / n_phi
    return np.stack([np.cos(phi), np.sin(phi)], 1)


def source_vector(cs, delta, noise="neg"):
    """x0(Delta) = [i_C; v_S] (phase domain) and the noise map M (3ns x ns complex): x = x0 + M lam."""
    ibr, sg = cs["ibr"], cs["sg"]
    delta = np.broadcast_to(np.asarray(delta, complex), (len(ibr),))
    x0 = np.concatenate([A @ np.array([0, cs["i0"][c], delta[c]]) for c in range(len(ibr))]
                        + [A @ np.array([0, cs["e0"][s], 0]) for s in range(len(sg))])
    b = B_NEG if noise == "neg" else B_POS
    ns = len(ibr) + len(sg)
    M = np.zeros((3 * ns, ns), complex)
    for s in range(ns):
        M[3 * s:3 * s + 3, s] = cs["sigma"] * b
    return x0, M


def _re(Mc):
    """Complex linear map acting on complex z = x + jy, as a real map on [x; y] giving [Re; Im]."""
    return np.block([[Mc.real, -Mc.imag], [Mc.imag, Mc.real]])


class _LP:
    def __init__(self):
        self.nv, self.bounds, self.eq, self.ub = 0, [], [], []

    def var(self, n, lo=None, hi=None):
        s = slice(self.nv, self.nv + n)
        self.nv += n
        self.bounds += [(lo, hi)] * n
        return s

    def add_eq(self, terms, rhs):                  # sum (slice, matrix) = rhs
        self.eq.append((terms, np.asarray(rhs, float)))

    def add_ub(self, terms, rhs):
        self.ub.append((terms, np.asarray(rhs, float)))

    def _stack(self, rows):
        if not rows:
            return None, None
        mats, rhs = [], []
        for terms, r in rows:
            m = np.zeros((len(r), self.nv))
            for s, a in terms:
                m[:, s] += a
            mats.append(m); rhs.append(r)
        return np.vstack(mats), np.concatenate(rhs)

    def feasible(self):
        Ae, be = self._stack(self.eq)
        Au, bu = self._stack(self.ub)
        res = linprog(np.zeros(self.nv), A_ub=Au, b_ub=bu, A_eq=Ae, b_eq=be, bounds=self.bounds, method="highs")
        if res.status not in (0, 2):
            raise RuntimeError(res.message)
        return res.status == 0


def _real_vec(c):
    c = np.atleast_1d(c)
    return np.concatenate([c.real, c.imag])


def _noise_ineq(lp, P, ns, lam, scale_slice=None, const=1.0, minus=None):
    """P lam_k <= const (or <= m with m a variable slice) for every source block; minus: P(lam - minus) <= ..."""
    for s in range(ns):
        sel = np.zeros((2, 2 * ns)); sel[0, s] = 1; sel[1, ns + s] = 1
        Pk = P @ sel
        terms = [(lam, Pk)]
        if minus is not None:
            terms.append((minus, -Pk))
        if scale_slice is None:
            lp.add_ub(terms, np.full(len(P), const))
        else:
            sl, coef = scale_slice                 # P(...) - coef*m <= const
            terms.append((sl, -coef * np.ones((len(P), 1))))
            lp.add_ub(terms, np.full(len(P), const))


def _fault_block(lp, md, x0, M, P, mz_lo, variant, vL):
    """Constraints of one fault model's relaxed pre-test set; returns the i_L noise slice lam."""
    ns = M.shape[1]
    mz = lp.var(1, mz_lo, 1.0)
    mr = lp.var(1, 0.0, 1.0)
    lam = lp.var(2 * ns)
    lz = lp.var(2 * ns)
    lr = lp.var(2 * ns)
    Mr = _re(M)
    x0r = _real_vec(x0)
    # psi v_L = Oz u_z + Or u_r, u_z = mz x0 + M lam_z, u_r = mr x0 + M lam_r
    Oz, Or = _re(md["Oz"]), _re(md["Or"])
    lp.add_eq([(vL, _re(md["psi"])), (mz, -(Oz @ x0r)[:, None]), (mr, -(Or @ x0r)[:, None]),
               (lz, -Oz @ Mr), (lr, -Or @ Mr)], np.zeros(2))
    _noise_ineq(lp, P, ns, lam)                               # P lam <= 1
    _noise_ineq(lp, P, ns, lz, scale_slice=(mz, 1.0), const=0.0)   # P lam_z <= mz 1
    _noise_ineq(lp, P, ns, lr, scale_slice=(mr, 1.0), const=0.0)   # P lam_r <= mr 1
    if variant == "literal":
        # W^{Rel,1} as printed: u_z = mz x0 + M lam, u_r = mr x0 + M lam  =>  M lam = M lam_z = M lam_r
        lp.add_eq([(lam, Mr), (lz, -Mr)], np.zeros(Mr.shape[0]))
        lp.add_eq([(lam, Mr), (lr, -Mr)], np.zeros(Mr.shape[0]))
    else:
        # sound ties: P(lam - lam_z) <= (1 - mz) 1, P(lam - lam_r) <= (1 - mr) 1
        _noise_ineq(lp, P, ns, lam, scale_slice=(mz, -1.0), const=1.0, minus=lz)
        _noise_ineq(lp, P, ns, lam, scale_slice=(mr, -1.0), const=1.0, minus=lr)
    return lam


def separated(mods, pair, x0, M, mz_lo=0.15, variant="literal", n_phi=20):
    """True if the relaxed intersection of the pair's pre-test sets is empty (Lemma 7, second bullet)."""
    P = polygon_P(n_phi)
    lp = _LP()
    vL = lp.var(6)
    Mr, x0r = _re(M), _real_vec(x0)
    lams = {}
    for eta in pair:
        if eta == "N":
            ns = M.shape[1]
            lam = lp.var(2 * ns)
            On = _re(mods["N"]["Omega"])
            lp.add_eq([(vL, np.eye(6)), (lam, -On @ Mr)], On @ x0r)
            _noise_ineq(lp, P, ns, lam)
        else:
            lam = _fault_block(lp, mods[eta], x0, M, P, mz_lo, variant, vL)
        lams[eta] = lam
    e1, e2 = pair
    G1, G2 = _re(mods[e1]["Gamma"]), _re(mods[e2]["Gamma"])
    # (20a): Gamma1 (x0 + M lam1) = Gamma2 (x0 + M lam2)
    lp.add_eq([(lams[e1], G1 @ Mr), (lams[e2], -G2 @ Mr)], (G2 - G1) @ x0r)
    return not lp.feasible()


def grid(cs, mods, pairs, step=0.1, half=2.0, noise="neg", variant="literal"):
    """Common signal delta at every IBR on a square grid; returns {pair-set name: list of separating deltas}."""
    vals = np.round(np.arange(-half, half + 1e-9, step), 10)
    sep = {}
    for re_ in vals:
        for im_ in vals:
            d = complex(re_, im_)
            x0, M = source_vector(cs, d, noise)
            sep[d] = {p: separated(mods, p, x0, M, variant=variant) for p in pairs}
    return sep


def smallest(sep, need, n_ibr):
    ok = [d for d, s in sep.items() if all(s[p] for p in need)]
    if not ok:
        return None
    d = min(ok, key=lambda c: (abs(c), c.real, c.imag))
    return dict(delta=[d.real, d.imag], norm_Delta=abs(d) * np.sqrt(n_ibr), n_points=len(ok))


def q1(args):
    cs = case(args.case, endpoint=not args.endpoint_off)
    mods = models(cs, charging=args.charging, z0_ratio=args.z0)
    pairs = [("N", "ag"), ("N", "ab"), ("ag", "ab")] + [("N", f) for f in FAULTS if f not in ("ag", "ab")]
    sep = grid(cs, mods, pairs, step=args.step, noise=args.noise, variant=args.variant)
    n = len(cs["ibr"])
    res = dict(
        settings=dict(case=args.case, variant=args.variant, noise=args.noise, charging=args.charging,
                      endpoint=not args.endpoint_off, z0_ratio=args.z0, step=args.step),
        a_N_ag_ab=smallest(sep, [("N", "ag"), ("N", "ab"), ("ag", "ab")], n),
        b_N_all_LG=smallest(sep, [("N", f) for f in ("ag", "bg", "cg")], n),
        b_N_all_LL=smallest(sep, [("N", f) for f in ("ab", "bc", "ca")], n),
        c_N_all=smallest(sep, [("N", f) for f in FAULTS], n),
        delta0=sep[0j],
    )
    res["delta0"] = {f"{a}-{b}": bool(v) for (a, b), v in res["delta0"].items()}
    res["map"] = {f"{d.real:+.2f}{d.imag:+.2f}j": [int(bool(v)) for v in s.values()] for d, s in sep.items()}
    res["map_pairs"] = [f"{a}-{b}" for a, b in pairs]
    os.makedirs(OUT, exist_ok=True)
    tag = "_".join([args.case, args.variant, args.noise] + (["charging"] if args.charging else [])
                   + (["noend"] if args.endpoint_off else []) + ([f"z0x{args.z0:g}"] if args.z0 != 1 else []))
    path = os.path.join(OUT, f"q1_{tag}.json")
    with open(path, "w") as f:
        json.dump(res, f, indent=1)
    for key in ("a_N_ag_ab", "b_N_all_LG", "b_N_all_LL", "c_N_all"):
        print(key, res[key])
    print("delta = 0 separates:", res["delta0"])
    print("wrote", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["q1"])
    ap.add_argument("--case", default="vid", choices=["vid", "ivc"])
    ap.add_argument("--variant", default="literal", choices=["literal", "sound"])
    ap.add_argument("--noise", default="neg", choices=["neg", "pos"])
    ap.add_argument("--charging", action="store_true")
    ap.add_argument("--endpoint-off", action="store_true")
    ap.add_argument("--z0", type=float, default=1.0)
    ap.add_argument("--step", type=float, default=0.1)
    a = ap.parse_args()
    {"q1": q1}[a.cmd](a)
