"""Review of the structured instrument-error sets (PR #44, 6ff3997): are the sets big enough at the instrument
corners that matter? The error is near-bilinear (gain x source), so for a given source point the worst instrument
setting for an output component is the corner aligned with that component's RESIDUAL gradient (dy/dE minus the fitted
linear part). Random corners, as the fit samples them, rarely hit it. For fresh source points this puts E at that
corner (per component and sign) and asks whether the measurement is still inside its own set (distance 0).

    python review/checks/p44g_structured.py      (repo root at 6ff3997)
"""
import sys, time
import numpy as np
sys.path.insert(0, "src")
import frames as fr
from pscad_network import three_bus
from network_delta_test import CASES

deg = np.pi / 180
CLASS = dict(N=(0.03, 2 * deg, 0.01, 1 * deg), F=(0.06, 4 * deg, 0.10, 1 * deg))
WHITE = [0.02] * 3 + [0.04] * 3
net = three_bus()
fm = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, eps=np.array(WHITE + WHITE), factor=1.1,
                   drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.008, instr=CLASS)
d = 1.12 * np.exp(1j * np.radians(225))
rng = np.random.default_rng(17)
phi = fm.phi_max(d)


FAILED = [0]


def dist_to(pieces, z):
    """frames.distance_to_set, retried with the interior-point solver if HiGHS returns a numerical status."""
    from scipy.optimize import linprog
    y = z[:6] + 1j * z[6:]
    try:
        return fr.distance_to_set(pieces, y)
    except RuntimeError:
        best = np.inf
        for cN, GN in pieces:
            n, kk = cN.size, GN.shape[1]
            c = np.zeros(kk + n + 1); c[-1] = 1
            A_ub = np.vstack([np.hstack([np.zeros((n, kk)), np.eye(n), -np.ones((n, 1))]),
                              np.hstack([np.zeros((n, kk)), -np.eye(n), -np.ones((n, 1))])])
            res = linprog(c, A_ub=A_ub, b_ub=np.zeros(2 * n), A_eq=np.hstack([GN, np.eye(n), np.zeros((n, 1))]),
                          b_eq=fr.nw._realify(y) - cN, bounds=[(-1, 1)] * kk + [(None, None)] * n + [(0, None)],
                          method="highs-ipm")
            if res.status == 0:
                best = min(best, res.x[-1])
        if not np.isfinite(best):
            FAILED[0] += 1
            return 0.0
        return best


def meas(S, k, lam, dr, ref, E):
    y = fm.measure(S[None], d, k, None if k is None else np.array([lam]), None if k is None else np.array([dr]), E=E[None])
    return fr._realify2(y * np.exp(1j * phi * ref))[0]


t0 = time.time()
for label, k in (("N", None), ("L1 A-G 15 % 40 ohm", CASES.index(("L1", 0.15, "ag", 1.0))),
                 ("L2 A-G 50 % 40 ohm", CASES.index(("L2", 0.5, "ag", 1.0))), ("L1 B-C 15 % bolted", CASES.index(("L1", 0.15, "ab", 0.0)))):
    pieces = fm.zonotopes(d, k)
    nE = 12 if k is None else 24
    worst, worst_rand, n_out, n_tot = 0.0, 0.0, 0, 0
    for _ in range(25):
        S = rng.uniform(-1, 1, 4)
        lam, dr, ref = rng.uniform(0, 1), rng.choice([-1.0, 1.0]), rng.choice([-1.0, 1.0])
        p = 0 if S[2] <= 0 else 1
        c, G = pieces[p]
        JE = G[:, G.shape[1] - 12 - nE:G.shape[1] - 12]          # the instrument columns (just before diag(r))
        E0 = np.zeros(nE)
        y0 = meas(S, k, lam, dr, ref, E0)
        h = 1e-3
        dY = np.stack([(meas(S, k, lam, dr, ref, E0 + h * np.eye(nE)[j]) - y0) / h for j in range(nE)], 1)   # (12, nE)
        g = dY - JE
        for comp in range(12):
            for s in (1.0, -1.0):
                E = np.sign(s * g[comp]); E[E == 0] = 1.0
                dist = dist_to(pieces, meas(S, k, lam, dr, ref, E))
                worst = max(worst, dist); n_out += dist > 1e-9; n_tot += 1
        for _ in range(24):                                       # the same number of random corners, for contrast
            E = rng.choice([-1.0, 1.0], nE)
            dist = dist_to(pieces, meas(S, k, lam, dr, ref, E))
            worst_rand = max(worst_rand, dist)
    print(f"{label:22s}: gradient-aligned corners outside their set {n_out} of {n_tot}, largest {worst:.4f} pu "
          f"({worst / 0.08:.2f} eps); random corners largest {worst_rand:.4f} pu; LPs failed {FAILED[0]}  [{time.time() - t0:.0f} s]", flush=True)
