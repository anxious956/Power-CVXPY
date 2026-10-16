"""The PSCAD two-bus TAC25 design (results/PSCAD_TAC25.md: 0.24 pu no margin, 0.38 pu at rho 0.1) from both engines
in the mode actually used (outer source set, per-phase limit inside), and with the pre-#37 fault-block sign.
tests/test_network.py compares the engines only in the linearised mode.

    python review/checks/check_design_engines.py
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(ROOT, "src", "review"))
import numpy as np
import network as nw
import tac25_design as td
from wp1_common import ModelSet
from pscad_witness import P

net = nw.Network(lines={"L1": nw.Line("L", "R", P.z1, P.z0)}, sgs={"G": nw.SG("L", dict(P.zs), P.e0, tuple(P.gen_e))},
                 ibrs={"I": nw.IBR("R", P.i0, tuple(P.gen_i), P.ibr_neg_z, P.ibr_zero_z, inject=True, i_max=1.2)},
                 loads={"R": dict(P.yld)}, relay=("L1", "a"), eps=P.eps, rF=P.rF)
cases = [("L1", m, s, mr) for s in P.scen for m in P.m_grid for mr in P.mr_grid]
nms = nw.NetModelSet(net, cases, mode="outer")
ms = ModelSet(P, mode="outer")
for rho in (0.0, 0.1):
    a = nw.min_delta(nms, rho=rho, r_step=0.02, n_ang=72)
    b = td.min_delta(ms, i_max=1.2, limit_inside=True, limit_design=False, rho=rho, r_step=0.02, n_ang=72,
                     r_max=2.0, limit_rule="phase")
    print(f"rho {rho}: network.min_delta {a['abs_delta']} pu at {a['angle_deg']:.0f} deg; "
          f"tac25_design.min_delta {b['abs_delta']} pu at {b['angle_deg']:.0f} deg")
orig = td.phase_rows
def old(p, mode, k, i_max, dv, n_poly=td.N_POLY):
    A, b = orig(p, mode, k, i_max, dv, n_poly); A = A.copy(); A[:, k:] *= -1; return A, b
td.phase_rows = old
for rho in (0.0, 0.1):
    b = td.min_delta(ms, i_max=1.2, limit_inside=True, limit_design=False, rho=rho, r_step=0.02, n_ang=72,
                     r_max=2.0, limit_rule="phase")
    print(f"rho {rho}, pre-#37 sign: tac25_design.min_delta {b['abs_delta']} pu")
