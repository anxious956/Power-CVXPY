"""H4: delta is the same in the pre- and post-event solves, so incremental (post - pre)
quantities cancel delta's direct term by construction.

Two data variants on the zone study generator:
  continuous  delta in pre and post (the original; injection runs all the time)
  post-only   delta switched on at the event (delta_pre = 0), so incremental quantities carry it
and detectors split by what they are built from:
  reactance        phase-selected loop reactance (TOTAL V and I; incremental only for selection)
  |i-|             total negative-sequence current magnitude
  |di-|            incremental negative-sequence current magnitude
  LR all           engineered + LR, fixed features (H21), OOF thresholds (H18)
  LR total-only    same, only the features built from post-event totals
  LR incr-only     same, only the features built from post-minus-pre increments
AUC (train-chosen polarity) and the AUC slope vs delta (least squares, per pu, over the mean
of 3 seeds). CPU only; no CNN. --quick sizes, deltas 0, .1, .3, .514.

  python src/review/h4_incremental.py
"""
import time
import numpy as np
from dataclasses import replace
from common import design_direction, save
from waveforms import SigParams, sequence_phasors, CYCLE, EVENT
import detect as D
import zone_detect as Z

direction = design_direction()
grid = replace(Z.ZoneParams(), rF=0.3)
DELTAS = (0.0, 0.10, 0.30, 0.514)
# column groups of zone_features(fixed=True): see zone_detect.zone_features
TOTAL = list(range(0, 6)) + list(range(7, 16)) + list(range(22, 28)) + list(range(30, 36)) + [38, 39, 40]
INCR = list(range(16, 22)) + [28, 29, 36, 37] + [41, 42, 43]


def score_incr_negseq(X):
    return np.array([abs(sequence_phasors(x[3:], EVENT + CYCLE)[2] - sequence_phasors(x[3:], EVENT - 2 * CYCLE)[2])
                     for x in X])


rows = []; t0 = time.time()
for variant in ("continuous", "post-only"):
    for t in DELTAS:
        for sd in range(3):
            kw = dict(delta_pre=0.0) if variant == "post-only" else {}
            Xtr, ytr, _ = Z.make_zone_dataset(350, np.random.default_rng(100 + 17 * sd), t * direction, SigParams(), grid, **kw)
            Xte, yte, _ = Z.make_zone_dataset(250, np.random.default_rng(999 + 31 * sd), t * direction, SigParams(), grid, **kw)
            Ftr, Fte = Z.zone_features(Xtr, grid, fixed=True), Z.zone_features(Xte, grid, fixed=True)
            sc = {"reactance": (Z.score_reactance(Xtr, grid), Z.score_reactance(Xte, grid)),
                  "|i-|": (Z.score_negseq(Xtr), Z.score_negseq(Xte)),
                  "|di-|": (score_incr_negseq(Xtr), score_incr_negseq(Xte)),
                  "LR all": D.fit_lr_scores(Ftr, ytr, Fte, seed=sd, max_iter=4000, oof_folds=5),
                  "LR total-only": D.fit_lr_scores(Ftr[:, TOTAL], ytr, Fte[:, TOTAL], seed=sd, max_iter=4000, oof_folds=5),
                  "LR incr-only": D.fit_lr_scores(Ftr[:, INCR], ytr, Fte[:, INCR], seed=sd, max_iter=4000, oof_folds=5)}
            for k, (a, b) in sc.items():
                rows.append(dict(variant=variant, delta=t, seed=sd, det=k, **D.evaluate(a, ytr, b, yte)))
        print(f"{variant} delta={t} [{time.time()-t0:.0f}s]", flush=True)

dets = ["reactance", "|i-|", "|di-|", "LR all", "LR total-only", "LR incr-only"]
summary = {}
print("\nvariant     detector        " + "  ".join(f"d={t:<5}" for t in DELTAS) + "   slope/pu   dAUC(0.514-0)")
for variant in ("continuous", "post-only"):
    for k in dets:
        mu = []; sdv = []
        for t in DELTAS:
            a = np.array([r["auc"] for r in rows if r["variant"] == variant and r["det"] == k and r["delta"] == t])
            mu.append(a.mean()); sdv.append(a.std())
        slope = float(np.polyfit(DELTAS, mu, 1)[0])
        summary[f"{variant}|{k}"] = dict(auc=mu, sd=sdv, slope=slope, d_auc=float(mu[-1] - mu[0]))
        print(f"{variant:11s} {k:14s} " + "  ".join(f"{m:.3f}" for m in mu) + f"   {slope:+.3f}     {mu[-1]-mu[0]:+.3f}")
save("h4_incremental.json", dict(rows=rows, summary=summary, runtime_s=time.time() - t0))
