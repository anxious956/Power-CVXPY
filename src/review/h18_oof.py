"""H18: in-sample training scores used to place the 1 % threshold for LR and CNN.

For each split, one full-train model and 5 fold models are fitted; the SAME test scores are
evaluated with three thresholds: in-sample train scores (original), out-of-fold train scores
with the full model on test ("oof/full"), and out-of-fold train scores with the mean of the fold
models on test ("oof/folds"). Polarity is chosen on train in all three (H17 fix applied).
Zone study at --quick sizes, 3 seeds, deltas 0, .1, .3, .514; fault-vs-load at --quick sizes.

  python src/review/h18_oof.py
"""
import time
import numpy as np
from dataclasses import replace
from sklearn.model_selection import StratifiedKFold
from common import design_direction, save
from waveforms import make_dataset, SigParams
import detect as D
import zone_detect as Z

FOLDS = 5
direction = design_direction()


def lr_variants(ftr, ytr, fte, seed, max_iter):
    s_tr_in, s_te = D.fit_lr_scores(ftr, ytr, fte, seed=seed, max_iter=max_iter, oof_folds=0)
    s_tr_oof, _ = D.fit_lr_scores(ftr, ytr, fte, seed=seed, max_iter=max_iter, oof_folds=FOLDS)
    return {"in-sample": (s_tr_in, s_te), "oof/full": (s_tr_oof, s_te)}


def cnn_variants(Xtr, ytr, Xte, seed, epochs):
    Xtr_n, Xte_n = D._norm_per_waveform(Xtr), D._norm_per_waveform(Xte)
    s_tr_in, s_te = D._cnn_fit_predict(Xtr_n, ytr, [Xtr_n, Xte_n], epochs, seed)
    s_oof = np.zeros(len(ytr)); te_f = []
    for k, (a, b) in enumerate(StratifiedKFold(FOLDS, shuffle=True, random_state=seed).split(np.zeros(len(ytr)), ytr)):
        sb, st = D._cnn_fit_predict(Xtr_n[a], ytr[a], [Xtr_n[b], Xte_n], epochs, seed + 1 + k)
        s_oof[b] = sb; te_f.append(st)
    return {"in-sample": (s_tr_in, s_te), "oof/full": (s_oof, s_te),
            "oof/folds": (s_oof, np.mean(te_f, axis=0))}


rows = []
t0 = time.time()
grid = replace(Z.ZoneParams(), rF=0.3)
for t in (0.0, 0.10, 0.30, 0.514):
    for sd in range(3):
        Xtr, ytr, _ = Z.make_zone_dataset(350, np.random.default_rng(100 + 17 * sd), t * direction, SigParams(), grid)
        Xte, yte, _ = Z.make_zone_dataset(250, np.random.default_rng(999 + 31 * sd), t * direction, SigParams(), grid)
        v = {"engineered": lr_variants(Z.zone_features(Xtr, grid), ytr, Z.zone_features(Xte, grid), sd, 4000),
             "cnn": cnn_variants(Xtr, ytr, Xte, sd, 12)}
        for det, vv in v.items():
            for name, (a, b) in vv.items():
                rows.append(dict(study="zone", delta=t, seed=sd, det=det, variant=name,
                                 **D.evaluate(a, ytr, b, yte, polarity="train")))
    print(f"zone delta={t} [{time.time()-t0:.0f}s]", flush=True)

for t in (0.0, 0.05, 0.10, 0.20, 0.40):
    for sd in range(3):
        Xtr, ytr, _ = make_dataset(300, np.random.default_rng(100 + 17 * sd), delta=t * direction, hard=True)
        Xte, yte, _ = make_dataset(200, np.random.default_rng(999 + 31 * sd), delta=t * direction, hard=True)
        v = {"engineered": lr_variants(D.relay_features(Xtr), ytr, D.relay_features(Xte), sd, 3000),
             "cnn": cnn_variants(Xtr, ytr, Xte, sd, 10)}
        for det, vv in v.items():
            for name, (a, b) in vv.items():
                rows.append(dict(study="detect", delta=t, seed=sd, det=det, variant=name,
                                 **D.evaluate(a, ytr, b, yte, polarity="train")))
    print(f"detect delta={t} [{time.time()-t0:.0f}s]", flush=True)

print("\nstudy  delta  detector    variant     test FAR@1%   dep@1%   AUC   (mean +- sd over 3 seeds)")
for study in ("zone", "detect"):
    for t in sorted({r["delta"] for r in rows if r["study"] == study}):
        for det in ("engineered", "cnn"):
            for var in ("in-sample", "oof/full", "oof/folds"):
                rr = [r for r in rows if r["study"] == study and r["delta"] == t and r["det"] == det and r["variant"] == var]
                if not rr:
                    continue
                f = np.array([r["false_alarm"] for r in rr]) * 100
                d = np.array([r["detection_rate"] for r in rr]) * 100
                a = np.array([r["auc"] for r in rr])
                print(f"{study:6s} {t:.3f}  {det:10s} {var:10s}  {f.mean():5.2f}+-{f.std():4.2f}  "
                      f"{d.mean():5.1f}+-{d.std():4.1f}  {a.mean():.3f}")
save("h18_oof.json", dict(rows=rows, runtime_s=time.time() - t0))
