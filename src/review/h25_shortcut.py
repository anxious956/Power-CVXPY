"""H25: shortcut-control coverage.

1. real_ml.shortcut_control (pre-fault window 45..5 ms before inception) on all three relays, including
   DoubleLine, which real_ml.py never checked; grouped folds.
2. Noise-level sweep: the same control at white-noise levels 0, 1e-6, 1e-5, 1e-4, 1e-3, 3e-3 (fraction of
   nominal, 16-bit ADC except at 0), to show where the fingerprint leak disappears.
3. Pre-fault part of the real decision window: the model gets the 40 ms before inception that every
   learned model's 20 ms window contains (not the shifted control window), at the default chain.
4. Label permutation on the actual task at 20 ms: labels permuted within the training fold; test AUC
   must be about 0.5 (checks the pipeline itself cannot manufacture signal).

Gradient boosting and random forest only (the models that exploited the leak); grouped 5-fold,
sibling groups (target, location, type, R_f), own-line 99 % faults as negatives.

    python src/review/h25_shortcut.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from review import common as cm
from review.zone_cv import zone_task
import real_ml

MODELS = ("gradient boosting", "random forest")


def cv_auc(X, y, groups, permute=False, folds=5, seed=0):
    out = {}
    for n in MODELS:
        a = []
        for f, (tr, te) in enumerate(StratifiedGroupKFold(folds, shuffle=True, random_state=seed).split(X, y, groups)):
            ytr = y[tr].copy()
            if permute:
                ytr = np.random.default_rng(100 + f).permutation(ytr)
            m = real_ml.fit_balanced(real_ml.models(f)[n], X[tr], ytr, f)
            a.append(roc_auc_score(y[te], real_ml.score(m, X[te])))
        out[n] = dict(mean=float(np.mean(a)), sd=float(np.std(a)))
    return out


def prefault_window(R, idx):
    """40 ms ending at inception: the pre-fault part of every learned model's decision window."""
    ev = R["ev"]
    w = R["full"][idx, :, ev - real_ml.PRE:ev].astype(np.float64)
    w[:, :3] /= real_ml.V_NOM_PEAK
    w[:, 3:] *= R["z_reach"] / real_ml.V_NOM_PEAK
    return w.reshape(len(idx), -1)


if __name__ == "__main__":
    t0 = time.time()
    res = {}
    for name in ("doubleline", "testgrid_A", "testgrid_B"):
        r = {}
        for noise in (0.0, 1e-6, 1e-5, 1e-4, 1e-3, 3e-3):
            chain = dict(noise_rel=noise, adc_bits=0 if noise == 0.0 else 16)
            R = cm.load_relay(name, chain)
            idx, y, groups = zone_task(R)
            r[f"control_noise_{noise:g}"] = cv_auc(real_ml.raw_window(R, idx, 0, prefault=True), y, groups)
            print(f"[{name}] noise {noise:g}: control (45..5 ms before) {r[f'control_noise_{noise:g}']}  [{time.time()-t0:.0f}s]", flush=True)
            if noise == 1e-3:
                r["prefault_part_of_decision_window"] = cv_auc(prefault_window(R, idx), y, groups)
                print(f"[{name}] 40 ms ending at inception: {r['prefault_part_of_decision_window']}", flush=True)
                r["label_permutation_20ms"] = cv_auc(real_ml.raw_window(R, idx, 20), y, groups, permute=True)
                print(f"[{name}] permuted labels, 20 ms window: {r['label_permutation_20ms']}", flush=True)
            del R
        res[name] = r
        json.dump(res, open(os.path.join(cm.ROOT, "results", "review", "h25_shortcut.json"), "w"), indent=1)
    print(f"saved results/review/h25_shortcut.json [{time.time()-t0:.0f}s]")
