"""tac25_channels.separated_structured writes its own LP as [G_N, -G_F, ...] = c_F - c_N, so its fault
variable is +u_F; since PR #37 td.limit_rows negates the fault block (for ModelSet.pair's [G_N, +G_F]).
This script re-runs the one changed cell (imbalance kappa = 16, i_max = 2.1) with the rows as they are
and with the fault-block sign restored for this LP only, and checks a feasible point's realisations."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src", "review")); sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np
import tac25_design as td
import tac25_channels as ch

STEP, NANG = (0.04, 36) if "--stored" in sys.argv else (0.02, 72)   # --stored: imbalance_boundary defaults
p = ch.make_params(0.08)
spec = ch.imbalance_scale(ch.CHANNELS, 16)
orig = td.limit_rows

def flipped(pp, mode, k, r_head, n_poly=td.N_POLY):
    A, b = orig(pp, mode, k, r_head, n_poly)
    A = A.copy(); A[:, k:] *= -1          # undo the -u_F sign: this LP's fault variable is +u_F
    return A, b

for lab, fn in (("as merged (sign for ModelSet.pair)", orig), ("sign for this LP ([GN, -GF])", flipped)):
    ch.td.limit_rows = fn
    r = ch.min_delta_structured(p, spec=spec, rho=0.0, i_max=2.1, r_step=STEP, n_ang=NANG)
    print(f"{lab:40s} kappa=16 i_max=2.1: |delta| = {r['abs_delta']}  angle {r['angle_deg']}")
ch.td.limit_rows = orig
