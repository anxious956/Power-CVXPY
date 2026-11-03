"""Long-lines Q3 review: where do the static unseparated cases at delta = 0 (k_L 2, structured, rho 0.1) come from?
frames.witness gives the closest N / fault pair's gap and the source points S_N, S_F in the [-1, 1]^4 box.
Witness points on the box faces (|S_i| ~ 1) mean the meeting comes from the source-box corners, not the nominal
point (S = 0). The nominal point's own fault measurement against N(0) is printed beside it for scale.
cwd: the long-lines checkout at ee98f34.   python <scratch>/p_ll_witness.py
"""
import sys, json, warnings, time
warnings.filterwarnings("ignore")
sys.path.insert(0, "src")
import numpy as np
import longlines as ll, frames as fr

kls, rows = ll.kl_set()
fm = ll.model(ll.net_k(2), "structured", rows[2.0]["phi_ref"])
w = ll.scale(fm)
bind = [("L1", 0.95, "ag", 1.0), ("L2", 0.05, "ag", 1.0), ("L2", 0.25, "ag", 1.0), ("L2", 0.5, "ag", 1.0)]
from scipy.optimize import linprog

def wwitness(fm, d, k):
    """frames.witness with longlines.gap's per-component eps weighting (the structured tier's eps is a vector)."""
    best = None
    for i, (cN, GN) in enumerate(fm.zonotopes(d, None)):
        for j, (cF, GF) in enumerate(fm.zonotopes(d, k)):
            n, kn, kf = cN.size, GN.shape[1], GF.shape[1]
            c = np.zeros(kn + kf + n + 1); c[-1] = 1
            A_eq = np.hstack([GN, -GF, np.eye(n), np.zeros((n, 1))])
            W = w.reshape(n, 1)
            A_ub = np.vstack([np.hstack([np.zeros((n, kn + kf)), np.eye(n), -W]), np.hstack([np.zeros((n, kn + kf)), -np.eye(n), -W])])
            res = linprog(c, A_ub=A_ub, b_ub=np.zeros(2 * n), A_eq=A_eq, b_eq=cF - cN,
                          bounds=[(-1, 1)] * (kn + kf) + [(None, None)] * n + [(0, None)], method="highs")
            assert res.status == 0, res.message
            if best is None or res.x[-1] < best[0]:
                best = (res.x[-1], i, j, res.x[:kn], res.x[kn:kn + kf])
    g, i, j, a, b = best
    to_box = lambda piece, u: (np.add(*map(np.asarray, fm.pieces[piece])) / 2 + (np.subtract(fm.pieces[piece][1], fm.pieces[piece][0]) / 2) * u[:4])
    return dict(gap_eps=float(g), S_N=to_box(i, a), S_F=to_box(j, b), lam=float((b[4] + 1) / 2), drift=float(b[5]))

t0 = time.time()
print("eps vector:", np.asarray(fm.eps), "| pieces:", fm.pieces, flush=True)
for c in bind:
    k = fm.cases.index(c)
    r = wwitness(fm, 0j, k)
    print(f"{c}: gap {r['gap_eps']:.3f} eps (2(1+rho) = 2.2) | S_N {np.round(r['S_N'],2)} | S_F {np.round(r['S_F'],2)} | lam {r['lam']:.2f} drift {r['drift']:+.2f}  [{time.time()-t0:.0f} s]", flush=True)
    fm._cache.clear()
