"""tac25_channels.separated_structured writes its own LP as [G_N, -G_F, ...] = c_F - c_N, so its fault
variable is +u_F, unlike ModelSet.pair's [G_N, +G_F]. This script re-runs the cell that the sign decides
(imbalance kappa = 16, i_max = 2.1) with the fault block as tac25_channels calls it and with it negated.

Round 1 (main at e9a7894, no fault_sign yet): "as called" gave 1.08 pu (wrong), "negated" 1.20 pu.
Since PR #40, tac25_channels passes fault_sign=+1: "as called" gives 1.20 pu, "negated" 1.08 pu.
Works on both versions (keyword arguments pass through).

    python review/checks/check_channels_sign.py [--stored]
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src", "review")); sys.path.insert(0, os.path.join(ROOT, "src"))
import tac25_design as td
import tac25_channels as ch

STEP, NANG = (0.04, 36) if "--stored" in sys.argv else (0.02, 72)   # --stored: imbalance_boundary defaults
p = ch.make_params(0.08)
spec = ch.imbalance_scale(ch.CHANNELS, 16)
orig = td.limit_rows


def negated(pp, mode, k, r_head, *args, **kw):
    A, b = orig(pp, mode, k, r_head, *args, **kw)
    A = A.copy(); A[:, k:] *= -1          # the fault block with the opposite sign to the one the caller asked for
    return A, b


for lab, fn in (("fault block as tac25_channels calls it", orig), ("fault block negated", negated)):
    ch.td.limit_rows = fn
    r = ch.min_delta_structured(p, spec=spec, rho=0.0, i_max=2.1, r_step=STEP, n_ang=NANG)
    print(f"{lab:40s} kappa=16 i_max=2.1: |delta| = {r['abs_delta']}  angle {r['angle_deg']}")
ch.td.limit_rows = orig
