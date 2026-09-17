"""Check 1: the vectorised element reproduces real_ml's zone-1 rule exactly at 20/40 ms.
Check 2: real_ml.phasor_view rotates post-fault phasors by 180 deg against pre-fault at 30/50 ms.
Check 3: measurement_chain with DEFAULT_CHAIN is bit-identical to real_ml.measurement_chain."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
import real_ml
from zone_detect import score_reactance
from waveforms import sequence_phasors, EVENT, CYCLE

out = {}
t0 = time.time()
for name in ("testgrid_A", "testgrid_B", "doubleline"):
    R = cm.load_relay(name)
    Rorig = real_ml.relay_data(name)
    same_chain = bool(np.array_equal(R["full"], Rorig["full"]))
    idx = np.where(R["pos"] | R["neg"])[0]; y = R["pos"][idx].astype(int)
    res = dict(chain_bit_identical=same_chain)
    for t in (20, 30, 40, 50):
        orig = score_reactance(real_ml.phasor_view(Rorig, idx, t), Rorig["g"])
        E = cm.elements(R, idx, t)
        trip_o, trip_n = orig < R["x_reach"], E["rule_x"] < R["x_reach"]
        # phase consistency of the incremental currents: angle between pre-fault I1 from phasor_view and ours
        pv = real_ml.phasor_view(Rorig, idx[:50], t)
        ipre_o = np.array([sequence_phasors(w[3:], EVENT - 2 * CYCLE) for w in pv])
        ipost_o = np.array([sequence_phasors(w[3:], EVENT + CYCLE) for w in pv])
        vpre, vpost, ipre, ipost = E["phasors"]
        rot_post = np.degrees(np.angle(np.median(ipost_o[:, 1] / ipost[:50, 1] * np.conj(ipre_o[:, 1] / ipre[:50, 1]))))
        from sklearn.metrics import roc_auc_score
        res[t] = dict(max_abs_diff_ohm=float(np.max(np.abs(orig - E["rule_x"]))),
                      agree=float(np.mean(trip_o == trip_n)),
                      orig=dict(auc=float(roc_auc_score(y, -orig)), dep=float(trip_o[y == 1].mean()), ft=float(trip_o[y == 0].mean())),
                      absolute_basis=dict(auc=float(roc_auc_score(y, -E["rule_x"])), dep=float(trip_n[y == 1].mean()), ft=float(trip_n[y == 0].mean())),
                      post_vs_pre_rotation_in_phasor_view_deg=float(rot_post))
        print(name, t, json.dumps(res[t]), flush=True)
    out[name] = res
json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "check_repro.json"), "w"), indent=2)
print(f"done [{time.time()-t0:.0f}s]")
