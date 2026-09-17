"""H21: feature encoding defects in zone_features / relay_features.

1. Count how often the defects bite: angle features near the +-pi wrap (|angle| > 0.9 pi),
   ratio denominators at or below the phasor noise floor (|den| < 1e-3 pu), and values that are
   non-finite before nan_to_num (the posinf -> 0 aliasing).
2. Engineered + LR with original vs fixed (sin/cos angles, floored log-ratios) features,
   OOF thresholds and train-chosen polarity. CPU only.
Zone study at --quick sizes (deltas 0, .1, .3, .514, 3 seeds); fault-vs-load at --quick sizes.

  python src/review/h21_features.py
"""
import time
import numpy as np
from dataclasses import replace
from synth_common import design_direction, save
from waveforms import make_dataset, sequence_phasors, SigParams, CYCLE, EVENT
import detect as D
import zone_detect as Z

direction = design_direction()
grid = replace(Z.ZoneParams(), rF=0.3)
t0 = time.time()
out = dict(defects={}, auc=[])


def zone_denominators(X):
    """|denominator| of each original ratio / angle-of-ratio feature, per sample."""
    rows = []
    for x in X:
        vpre, vpost, ipre, ipost = Z._phasors(x)
        v0, v1, v2 = vpost; i0, i1, i2 = ipost
        di0, di1, di2 = ipost - ipre
        rows.append([abs(i1), abs(i1), abs(i2), abs(i2), abs(i0), abs(di2), abs(di1), abs(di0)])
    return np.array(rows)


DEN_NAMES = ["i1", "i1(dup)", "i2", "i2(dup)", "i0", "di2", "di1", "di0"]

for t in (0.0, 0.514):
    X, y, kinds = Z.make_zone_dataset(350, np.random.default_rng(100), t * direction, SigParams(), grid)
    F = Z.zone_features(X, grid, fixed=False, raw=True)
    A = F[:, Z.ZONE_ANGLE_COLS]
    names = ["ang(zg)", "ang(zp)", "ang(i2/i1)", "ang(i0/i1)", "ang(v2/i2)", "ang(v0/i0)",
             "ang(dv2/di2)", "ang(dv1/di1)"]
    wrap = {n: float((np.abs(A[:, j]) > 0.9 * np.pi).mean()) for j, n in enumerate(names)}
    straddle = {n: float(min((A[:, j] > 0.9 * np.pi).mean(), (A[:, j] < -0.9 * np.pi).mean()))
                for j, n in enumerate(names)}
    den = zone_denominators(X)
    low = {n: float((den[:, j] < 1e-3).mean()) for j, n in enumerate(DEN_NAMES) if "dup" not in n}
    low_by_kind = {k: {n: float((den[kinds == k, j] < 1e-3).mean()) for j, n in enumerate(DEN_NAMES) if "dup" not in n}
                   for k in ("ag", "ab", "ag2", "ab2")}
    R = F[:, Z.ZONE_RATIO_COLS]
    out["defects"][f"zone_delta_{t}"] = dict(
        n=len(X), frac_abs_angle_gt_09pi=wrap, frac_min_side_of_wrap=straddle,
        frac_denominator_below_1em3=low, by_kind=low_by_kind,
        nonfinite_before_nan_to_num=int((~np.isfinite(F)).sum()),
        ratio_p99=[float(np.percentile(R[:, j], 99)) for j in range(R.shape[1])],
        ratio_max=[float(R[:, j].max()) for j in range(R.shape[1])],
        ratio_median=[float(np.median(R[:, j])) for j in range(R.shape[1])])
    print(f"zone delta={t}: wrap {wrap}\n  straddle {straddle}\n  den<1e-3 {low_by_kind}\n"
          f"  nonfinite {out['defects'][f'zone_delta_{t}']['nonfinite_before_nan_to_num']}\n"
          f"  ratio median/p99/max {out['defects'][f'zone_delta_{t}']['ratio_median']} "
          f"{out['defects'][f'zone_delta_{t}']['ratio_p99']} {out['defects'][f'zone_delta_{t}']['ratio_max']}", flush=True)

for t in (0.0, 0.40):
    X, y, sc = make_dataset(300, np.random.default_rng(100), delta=t * direction, hard=True)
    F = D.relay_features(X, fixed=False)
    A = F[:, 17:25]
    out["defects"][f"detect_delta_{t}"] = dict(
        frac_abs_angle_gt_09pi=[float((np.abs(A[:, j]) > 0.9 * np.pi).mean()) for j in range(8)],
        frac_exact_zero_after_nan_to_num=float((F == 0).mean()))
    print(f"detect delta={t}: wrap per angle col {out['defects'][f'detect_delta_{t}']['frac_abs_angle_gt_09pi']}", flush=True)

for study in ("zone", "detect"):
    deltas = (0.0, 0.10, 0.30, 0.514) if study == "zone" else (0.0, 0.05, 0.10, 0.20, 0.40)
    for t in deltas:
        for sd in range(3):
            if study == "zone":
                Xtr, ytr, _ = Z.make_zone_dataset(350, np.random.default_rng(100 + 17 * sd), t * direction, SigParams(), grid)
                Xte, yte, _ = Z.make_zone_dataset(250, np.random.default_rng(999 + 31 * sd), t * direction, SigParams(), grid)
                fe = lambda X, fx: Z.zone_features(X, grid, fixed=fx); mi = 4000
            else:
                Xtr, ytr, _ = make_dataset(300, np.random.default_rng(100 + 17 * sd), delta=t * direction, hard=True)
                Xte, yte, _ = make_dataset(200, np.random.default_rng(999 + 31 * sd), delta=t * direction, hard=True)
                fe = lambda X, fx: D.relay_features(X, fixed=fx); mi = 3000
            for fx in (False, True):
                a, b = D.fit_lr_scores(fe(Xtr, fx), ytr, fe(Xte, fx), seed=sd, max_iter=mi, oof_folds=5)
                out["auc"].append(dict(study=study, delta=t, seed=sd, fixed=fx,
                                       **D.evaluate(a, ytr, b, yte, polarity="train")))
        print(f"{study} delta={t} [{time.time()-t0:.0f}s]", flush=True)

print("\nstudy  delta  features  AUC mean+-sd    dep@1%   FAR@1%")
for study in ("zone", "detect"):
    for t in sorted({r["delta"] for r in out["auc"] if r["study"] == study}):
        for fx in (False, True):
            rr = [r for r in out["auc"] if r["study"] == study and r["delta"] == t and r["fixed"] == fx]
            a = np.array([r["auc"] for r in rr]); d = np.array([r["detection_rate"] for r in rr]) * 100
            f = np.array([r["false_alarm"] for r in rr]) * 100
            print(f"{study:6s} {t:.3f}  {'fixed' if fx else 'orig ':5s}  {a.mean():.4f}+-{a.std():.4f}  "
                  f"{d.mean():5.1f}+-{d.std():3.1f}  {f.mean():4.2f}")
out["runtime_s"] = time.time() - t0
save("h21_features.json", out)
