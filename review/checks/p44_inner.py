"""Review of PR #44, question (1): is delta* set by real (physical) overlaps or by the outer approximation?

For a candidate command d, a case is WITNESSED as not separated if some sampled normal realisation and some sampled
fault realisation (each a physical point of the two-frame model: fixed point, limiter, frame sweep, drift, reference
rotation) lie within 2 eps (1 + rho) of each other in the inf-norm. A witness proves the true sets meet (under the
model's assumptions); no witness proves nothing. So the smallest radius at which some angle has no witnessed case is
a LOWER bound on the true delta*: if it sits just below the reported delta*, the outer sets are not what sets it.

    python review/checks/p44_inner.py <rho> [n_random]      (repo root, PR #44 at 7f2f2b5)
"""
import sys, time
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, "src")
import frames as fr
import network as nw
from pscad_network import three_bus
from network_delta_test import CASES

rho = float(sys.argv[1]); nr = int(sys.argv[2]) if len(sys.argv) > 2 else 300
net = three_bus()
fm = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, factor=1.1)
rng = np.random.default_rng(5)
S = np.vstack([fr.box_samples((-1,) * 4, (1,) * 4, nr, rng, 3)])
bound = 2 * fm.eps * (1 + rho)


def cloud(d, case):
    phi = fm.phi_max(d)
    Sx, lam, dr, ref, W = fm._expand(S, case)
    Y = fm.measure(Sx, d, case, lam, dr) * np.exp(1j * phi * ref)[:, None]
    return fr._realify2(Y)


hard0 = [k for k, c in enumerate(CASES) if c in fr.unseparated(fm, 0j, rho)]
order = hard0 + [k for k in range(len(CASES)) if k not in hard0]
t0 = time.time()
for r in (0.6, 0.8, 0.9, 0.94, 1.0, 1.04, 1.08, 1.1, 1.12, 1.14):
    free, binding = [], {}
    for a in np.linspace(0, 2 * np.pi, 72, endpoint=False):
        d = r * np.exp(1j * a)
        try:
            tree = cKDTree(cloud(d, None))
        except RuntimeError:
            continue
        hit = None
        for k in order:
            dist, _ = tree.query(cloud(d, k), k=1, p=np.inf, distance_upper_bound=bound * (1 + 1e-9))
            if np.isfinite(dist).any():
                hit = k
                break
        if hit is None:
            free.append(round(float(np.degrees(a))))
        else:
            binding[CASES[hit]] = binding.get(CASES[hit], 0) + 1
    top = sorted(binding.items(), key=lambda t: -t[1])[:4]
    print(f"rho {rho} |d| = {r:.2f}: angles with no witnessed case {len(free)} / 72 {free[:10]}; "
          f"witnessing cases {top}  [{time.time() - t0:.0f} s]", flush=True)
