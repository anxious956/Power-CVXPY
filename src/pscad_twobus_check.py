"""
Is the PSCAD two-bus grid the circuit the design tool models? Compare the relay phasors from EMT with
aux_model.solve at the same operating point.

Angles: EMT phasors are in PSCAD's time frame, the static model's in the source-EMF frame. One rotation,
fixed by the source EMF E1 = V1 + zs1 I1 measured before the fault, maps one onto the other; everything else
(currents, negative and zero sequence, the fault cycle) must then agree without further fitting. The
inverter's actual injection (I1 and I2 at bus R, measured) is what the static model is given.

    python src/pscad_twobus_check.py tb_N tb_ag:ag:0.55:0 tb_ab:ab:0.55:20
"""
import os, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pscad_io import read_case
from pscad_check import to_128_per_cycle
from waveforms import sequence_phasors, CYCLE
from aux_model import Params, solve
from pscad_twobus import VBASE_PK, IBASE_PK, ZBASE

WORK = r"D:\JOSHUA_TAYLOR_data\data\pscad_work\inverter"
P = Params(name="weak_sg_open0", zs={1: 0.4j, 2: 0.4j, 0: 0.8j}, gen_i=[0.3, 0.3], eps=0.08, rF=1.0,
           ibr_zero_z=1e6)                      # the weak_sg preset with the inverter's zero-sequence path open


def seq(run, names, t_end, base):
    x = np.array([run["ch"][n] for n in names])
    x, fs = to_128_per_cycle(x, run["fs"], 60.0)
    end = int(round(t_end * fs))
    return np.array(sequence_phasors(x, end - CYCLE)) / base       # [s0, s1, s2] in pu


def relay_y(run, t):
    v = seq(run, ["VLA", "VLB", "VLC"], t, VBASE_PK)
    i = seq(run, ["ILA", "ILB", "ILC"], t, IBASE_PK)   # the ammeter already reads bus L into the line
    return np.array([v[1], v[2], v[0], i[1], i[2], i[0]]), v, i


def injection(run, t):
    j = -seq(run, ["IinvA", "IinvB", "IinvC"], t, IBASE_PK)    # injected into bus R
    return j[1], j[2]


def compare(name, scen="N", m=0.5, rf_ohm=0.0, t_pre=0.28, t_flt=0.35, flip_i=None):
    run = read_case(os.path.join(WORK, name + ".gf46"), name)
    y_pre, _, _ = relay_y(run, t_pre)
    i1_pre, i2_pre = injection(run, t_pre)
    # rotation into the static model's frame: the source EMF E1 = V1 + zs1 I1 (pre-fault, EMT) must sit at 0 deg
    e1 = y_pre[0] + P.zs[1] * y_pre[3]
    rot = np.exp(-1j * np.angle(e1))
    ys_pre = solve(P, "N", P.e0 * abs(e1), i1_pre * rot, i2_pre * rot)
    out = {"pre": (y_pre * rot, ys_pre)}
    if scen != "N":
        y_f, _, _ = relay_y(run, t_flt)
        i1_f, i2_f = injection(run, t_flt)
        mr = rf_ohm / ZBASE / P.rF
        ys_f = solve(P, scen, P.e0 * abs(e1), i1_f * rot, i2_f * rot, m=m, mr=mr)
        out["fault"] = (y_f * rot, ys_f)
    labels = ["V1", "V2", "V0", "I1", "I2", "I0"]
    print(f"\n{name} ({scen}, m = {m}, Rf = {rf_ohm} ohm): inverter injects I1 {abs(i1_pre):.3f} pu, I2 {abs(i2_pre):.4f} pu")
    for stage, (ye, ys) in out.items():
        err = np.abs(ye - ys)
        print(f"  {stage:<5} " + "  ".join(f"{l} {abs(a):.3f}/{abs(b):.3f}" for l, a, b in zip(labels, ye, ys)))
        print(f"        max |EMT - static| = {err.max():.4f} pu  (relative to the largest quantity {np.abs(ys).max():.3f} pu)")
    return out


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        parts = arg.split(":")
        name = parts[0]
        if len(parts) == 1:
            compare(name)
        else:
            compare(name, parts[1], float(parts[2]), float(parts[3]))
