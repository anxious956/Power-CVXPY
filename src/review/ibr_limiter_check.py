"""Claim check (REAL_TESTGRID.md): 'both inverters sit at about 1.15 to 1.2 pu of rating during faults'.
real_zone.py measured instantaneous peaks over 0.25-3 cycles after inception, which include DC offset and
the sub-cycle transient. Here: fundamental phase-current magnitude (full-cycle DFT) and positive/negative-sequence
current at the inverter terminals in cycles 1-2, 3-4 and 8-10 after inception, in pu of I_base from the grid
graph (I_base is a peak value: S sqrt(2)/(sqrt(3) V)), for faults on the relay lines and buses (noise-free records).

    python src/review/ibr_limiter_check.py
"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from evemt import load_cache
from review import common as cm

C = load_cache(glob.glob(os.path.join(cm.ROOT, "data", "*TestGrid110kV*_cache.meta.npz"))[0])
L = C["labels"]; G = C["graph"]
et = L["events/event_type"].astype(str).to_numpy(); tgt = L["events/event_target"].astype(str).to_numpy()
shc = np.char.find(et.astype(str), "shc") >= 0
out = {}
for cub, node, key in (("Cubicle(1)\pex_MainBus2_Ind2-2IBR", "Bus2IBR", "IBR2"), ("Cubicle(1)\pex_MainBus3_Ind3-3IBR", "Bus3IBR", "IBR3")):
    ibase = G.nodes[node][f"{key}_cntrlFMUIBRController_param_dict"]["I_base"]
    imax = G.nodes[node][f"{key}_cntrlFMUIBRController_param_dict"]["Imax"]
    k = C["cubicles"].index(cub)
    sel = np.where(shc & np.isin(tgt, ["MainBus2", "MainBus3", "MainLn2-3", "MainLn1-2A", "MainLn3-4"]))[0]
    x = np.asarray(C["x"][sel, k, 3:], dtype=np.float64)
    ev = C["event_index"]
    r = dict(I_base_A_rms=ibase, Imax_pu=imax, n=int(len(sel)))
    for lab, end in (("pre-fault", ev - 128), ("cycle 1-2", ev + 256), ("cycle 3-4", ev + 512), ("cycle 9-10", ev + 1280)):
        seq = cm.seq_phasors(x, end)                       # peak phasors [0, +, -]
        ph = seq @ cm.AM.T
        # I_base in the controller parameters equals S sqrt(2) / (sqrt(3) V): a peak value, like the DFT phasors
        imax_phase = np.abs(ph).max(1) / ibase
        s12 = (np.abs(seq[:, 1]) + np.abs(seq[:, 2])) / ibase
        r[lab] = dict(max_phase_pu_median=float(np.median(imax_phase)), max_phase_pu_p95=float(np.percentile(imax_phase, 95)),
                      i1_pu_median=float(np.median(np.abs(seq[:, 1]) / ibase)), i2_pu_median=float(np.median(np.abs(seq[:, 2]) / ibase)),
                      i1_plus_i2_pu_median=float(np.median(s12)), i1_plus_i2_pu_p95=float(np.percentile(s12, 95)),
                      i1_plus_i2_pu_max=float(s12.max()))
    out[cub] = r
    print(cub, json.dumps(r, indent=1))
json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "ibr_limiter_check.json"), "w"), indent=1)
