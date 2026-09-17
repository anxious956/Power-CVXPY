"""H25/H30 follow-up: is the pre-fault 'shortcut' at inception the non-causal resampling look-ahead?
Gradient boosting (grouped 5-fold, own-99 % guard band, default chain) on a 40 ms window ending k samples
before inception, k = 0, 3, 6, 9, 13, 32 (0, 0.5, 0.9, 1.4, 2.0, 5.0 ms). If AUC falls to about 0.5 once the
window stops ~1.4 ms before inception, the signal is the fault leaking backwards through resample_poly.

    python src/review/h25_leak_edge.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from review import common as cm
from review.zone_cv import zone_task, splits
import real_ml

res = {}
for name in ("testgrid_A", "testgrid_B", "doubleline"):
    R = cm.load_relay(name)
    idx, y, groups = zone_task(R)
    r = {}
    for k in (0, 3, 6, 9, 13, 32):
        end = R["ev"] - k
        w = R["full"][idx, :, end - real_ml.PRE:end].astype(np.float64)
        w[:, :3] /= real_ml.V_NOM_PEAK; w[:, 3:] *= R["z_reach"] / real_ml.V_NOM_PEAK
        X = w.reshape(len(idx), -1)
        a = []
        for f, tr, te, meta in splits("grouped", R, idx, y, groups):
            if f >= 5:
                break
            m = real_ml.fit_balanced(real_ml.models(f)["gradient boosting"], X[tr], y[tr], f)
            a.append(roc_auc_score(y[te], real_ml.score(m, X[te])))
        r[f"{k / 6.4:.2f} ms before inception"] = dict(mean=float(np.mean(a)), sd=float(np.std(a)))
        print(name, f"window ends {k / 6.4:.2f} ms before inception: GB AUC {np.mean(a):.3f} +- {np.std(a):.3f}", flush=True)
    res[name] = r
    del R
json.dump(res, open(os.path.join(cm.ROOT, "results", "review", "h25_leak_edge.json"), "w"), indent=1)
