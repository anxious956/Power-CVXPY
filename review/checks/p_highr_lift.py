"""Review of the high-R follow-up (988f93e): no delta GUARANTEES detection from 120 ohm, but does delta still lift
high-R A-G faults over D1's alarm threshold (outside N by more than the noise box), where detection under realistic
noise is decided? Static two-frame model with the structured design tier (as src/highr_design.py). Distances are in
units of the per-component white box (V 0.02 / I 0.04): > 1 means D1 alarms on the clean measurement (detected under
small noise, not guaranteed), > 2 guaranteed. Clean faults at random source points (no instrument error, settled).

    python review/checks/p_highr_lift.py      (repo root at 988f93e)
"""
import sys
import numpy as np
sys.path.insert(0, "src")
import frames as fr
from pscad_network import three_bus
from highr_design import INSTR, WHITE, LOCS

W = 1.0 / np.array(WHITE + WHITE)
rng = np.random.default_rng(3)
S = rng.uniform(-1, 1, (30, 4))


def wdist(pieces, y):
    """inf-norm distance in units of the box: scale the pieces and the point by 1 / eps per component."""
    sp = [(c * W, G * W[:, None]) for c, G in pieces]
    z = fr.nw._realify(y) * W
    return fr.distance_to_set(sp, z[:6] + 1j * z[6:])


for mr in (4.0, 5.0):
    cases = [(ln, m, "ag", mr) for ln, m in LOCS]
    fm = fr.FrameModel(three_bus(), cases, n_samples=150, face_pts=3, seed=1, eps=np.array(WHITE + WHITE), factor=1.1,
                       drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.008, instr=INSTR)
    res = {}
    for label, d in [("0", 0j)] + [(f"1.12@{a}", 1.12 * np.exp(1j * np.radians(a))) for a in range(0, 360, 45)]:
        try:
            N = fm.zonotopes(d, None)
        except fr.Inadmissible:
            continue
        ds = np.array([[wdist(N, fm.measure(S[j:j + 1], d, k)[0]) for j in range(len(S))] for k in range(len(cases))])
        res[label] = ((ds > 1).mean(), (ds > 2).mean(), ds.min(axis=1).min())
    base = res["0"]
    best = max((v for k, v in res.items() if k != "0"), key=lambda v: v[0])
    bl = [k for k, v in res.items() if v is best][0]
    print(f"R_f {40 * mr:.0f} ohm: delta 0: alarm {base[0]:.2f}, guaranteed {base[1]:.2f}; best |delta| 1.12 ({bl} deg): "
          f"alarm {best[0]:.2f}, guaranteed {best[1]:.2f}  (fraction of 8 locations x 30 source points)")
    for k, v in res.items():
        print(f"    {k:9s} alarm {v[0]:.2f} guaranteed {v[1]:.2f} smallest distance {v[2]:.2f} box")
