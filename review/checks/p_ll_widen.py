"""Long-lines Q2 review: is the delta* point 'knife-edge' or is the small margin the 0.02 pu grid step?
(a) the separating angle set at radii just above delta* (how fast the set widens);
(b) the gap at the carried angle at radii just below and above delta* (the slope the margin sits on).
Same FrameModel as longlines.design (seed 1), same test (frames.separated_fast / longlines.margin).
cwd: the long-lines checkout at dc6cf60.   python -I <scratch>/p_ll_widen.py
"""
import sys, os, time, json, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "src")
import numpy as np
from concurrent.futures import ProcessPoolExecutor
import longlines as ll
import frames as fr

JOBS = [   # key, radii for the angle sweep, angle window, radii for the gap at the carried angle
    ("2|structured|0.1",   [0.50, 0.54, 0.60], range(150, 235, 5), 190, [0.44, 0.46, 0.48, 0.50, 0.54, 0.60]),
    ("2|structured|0.0",   [0.22, 0.26],       range(225, 320, 5), 265, [0.18, 0.20, 0.22, 0.26]),
    ("1.5|structured|0.1", [0.08, 0.12],       range(245, 310, 5), 280, [0.04, 0.06, 0.08, 0.12]),
]
_W = {}

def _init(kl, tier, phi, order):
    warnings.filterwarnings("ignore")
    _W.update(fm=ll.model(ll.net_k(kl), tier, phi), order=order)

def _eval(args):
    r, a, rho = args
    d = r * np.exp(1j * np.radians(a))
    try:
        ok = fr.separated_fast(_W["fm"], d, rho, _W["order"])
    except fr.Inadmissible:
        ok = "inadmissible"
    _W["fm"]._cache.clear()
    return a, ok

def _gap(args):
    r, a, rho = args
    m = ll.margin(_W["fm"], r * np.exp(1j * np.radians(a)), rho)
    return r, m

if __name__ == "__main__":
    kls, rows = ll.kl_set()
    stored = json.load(open(os.path.join(ll.OUT, "longlines_design.json")))
    for key, radii, angs, a0, gap_r in JOBS:
        kl_s, tier, rho_s = key.split("|")
        kl = float(kl_s); kl = int(kl) if kl == int(kl) else kl
        rho = float(rho_s)
        phi = rows[float(kl)]["phi_ref"]
        s = stored[key]
        hard = [tuple(c) for c in s["unseparated_cases"]]
        fm0 = ll.model(ll.net_k(kl), tier, phi)
        order = [k for k, c in enumerate(fm0.cases) if tuple(c) in hard] + [k for k, c in enumerate(fm0.cases) if tuple(c) not in hard]
        print(f"\n===== {key}: stored delta* {s['abs_delta']} angles {s['separating_angles_deg']} carried {s['carried_angle_deg']} margin {s['margin']['margin_eps']:.4f} eps", flush=True)
        t0 = time.time()
        with ProcessPoolExecutor(3, initializer=_init, initargs=(kl, tier, phi, order)) as pool:
            for r in radii:
                res = list(pool.map(_eval, [(r, a, rho) for a in angs]))
                ok = [a for a, g in res if g is True]
                bad = [a for a, g in res if g == "inadmissible"]
                print(f"  r {r:.2f}: separating angles {ok} ({len(ok)} of {len(res)} tried in [{angs[0]}, {angs[-1]}]){' inadmissible ' + str(bad) if bad else ''}  [{time.time()-t0:.0f} s]", flush=True)
            for r, m in pool.map(_gap, [(r, a0, rho) for r in gap_r]):
                print(f"  gap at {a0} deg, r {r:.2f}: {m['gap_eps']:.4f} eps (margin {m['gap_eps'] - 2*(1+rho):+.4f}), binding {m['case']}  [{time.time()-t0:.0f} s]", flush=True)
