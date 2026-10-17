"""Which fault type makes the high-R design infeasible? The design's own set separation (zonotopes, rho 0), A-G only
and B-C only, at |delta| 1.12 pu and the angles where sampled A-G faults are all guaranteed (p_highr_lift.py).

    python review/checks/p_highr_types.py      (repo root at 988f93e)
"""
import sys
import numpy as np
sys.path.insert(0, "src")
import frames as fr
from pscad_network import three_bus
from highr_design import INSTR, WHITE, LOCS

for mr in (4.0, 5.0):
    for s in ("ag", "ab"):
        cases = [(ln, m, s, mr) for ln, m in LOCS]
        fm = fr.FrameModel(three_bus(), cases, n_samples=150, face_pts=3, seed=1, eps=np.array(WHITE + WHITE), factor=1.1,
                           drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.008, instr=INSTR)
        line = []
        for a in (0, 270, 315, None):
            d = 0j if a is None else 1.12 * np.exp(1j * np.radians(a))
            try:
                u = fr.unseparated(fm, d, 0.0)
            except fr.Inadmissible:
                line.append(f"{a}: inadmissible"); continue
            line.append(f"{'0' if a is None else f'1.12@{a}'}: {len(u)}/8 unseparated")
        print(f"R_f {40 * mr:.0f} ohm {s}: " + "; ".join(line), flush=True)
