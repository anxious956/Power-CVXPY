"""H17: polarity chosen on the TEST set in detect.evaluate.

Same scores, evaluated twice: polarity="test" (original) vs polarity="train" (fixed).
Scores come from the ORIGINAL scoring pipeline so only the evaluation changes.
Zone study at --quick sizes (350/250 per class, deltas 0, .1, .3, .514, 3 seeds, 12 epochs)
and the fault-vs-load study (detect.py, hard set) at its --quick sizes (300/200, 5 deltas).

  python src/review/h17_polarity.py [--cnn]

The CNN is off by default: on the shared GPU the first attempt ran 30 min for one delta. The CNN
column's legacy-vs-train sign comparison is instead taken from the sweep score dumps
(results/review_synth/zone_quick_fixed*.npz, which store train-chosen polarity per seed).
"""
import time, argparse
import numpy as np
from common import design_direction, save, ORIGINAL
from waveforms import make_dataset, SigParams
from dataclasses import replace
import detect as D
import zone_detect as Z

ap = argparse.ArgumentParser()
ap.add_argument("--cnn", action="store_true")
args = ap.parse_args()
direction = design_direction()
res = dict(zone=[], detect=[])
t0 = time.time()

grid = replace(Z.ZoneParams(), rF=0.3)
for t in (0.0, 0.10, 0.30, 0.514):
    for sd in range(3):
        Xtr, ytr, _ = Z.make_zone_dataset(350, np.random.default_rng(100 + 17 * sd), t * direction, SigParams(), grid)
        Xte, yte, _ = Z.make_zone_dataset(250, np.random.default_rng(999 + 31 * sd), t * direction, SigParams(), grid)
        if args.cnn:
            sc = Z.score_all(Xtr, ytr, Xte, grid, seed=sd, epochs=12, cfg=ORIGINAL)
        else:
            sc = {"reactance": (Z.score_reactance(Xtr, grid), Z.score_reactance(Xte, grid)),
                  "negseq": (Z.score_negseq(Xtr), Z.score_negseq(Xte)),
                  "engineered": Z.score_engineered(Xtr, ytr, Xte, grid, seed=sd, oof_folds=0,
                                                   fixed_features=False)}
        for k in sc:
            a = D.evaluate(sc[k][0], ytr, sc[k][1], yte, polarity="test")
            b = D.evaluate(sc[k][0], ytr, sc[k][1], yte, polarity="train")
            res["zone"].append(dict(delta=t, seed=sd, det=k, test_sign=a, train_sign=b))
    print(f"zone delta={t} done [{time.time()-t0:.0f}s]", flush=True)

p = SigParams(noise=0.01)
for t in (0.0, 0.05, 0.10, 0.20, 0.40):
    for sd in range(3):
        Xtr, ytr, _ = make_dataset(300, np.random.default_rng(100 + 17 * sd), delta=t * direction, p=p, hard=True)
        Xte, yte, _ = make_dataset(200, np.random.default_rng(999 + 31 * sd), delta=t * direction, p=p, hard=True)
        sc = {"negseq": (D.score_negseq(Xtr), D.score_negseq(Xte)),
              "incremental": (D.score_incremental(Xtr), D.score_incremental(Xte)),
              "engineered": D.score_engineered(Xtr, ytr, Xte, seed=sd, oof_folds=0, fixed_features=False)}
        if args.cnn:
            sc["cnn"] = D.train_cnn(Xtr, ytr, Xte, epochs=10, seed=sd, oof_folds=0, norm="per_waveform")
        for k, (a_, b_) in sc.items():
            a = D.evaluate(a_, ytr, b_, yte, polarity="test")
            b = D.evaluate(a_, ytr, b_, yte, polarity="train")
            res["detect"].append(dict(delta=t, seed=sd, det=k, test_sign=a, train_sign=b))
    print(f"detect delta={t} done [{time.time()-t0:.0f}s]", flush=True)

for study, keys in (("zone", Z.KEYS), ("detect", ("negseq", "incremental", "engineered", "cnn"))):
    print(f"\n{study}: delta | detector | AUC test-sign -> train-sign (mean over seeds) | "
          f"dep@1% test-sign -> train-sign | FAR@1% | #seeds sign differs")
    for t in sorted({r["delta"] for r in res[study]}):
        for k in keys:
            rr = [r for r in res[study] if r["delta"] == t and r["det"] == k]
            if not rr:
                continue
            A = np.array([r["test_sign"]["auc"] for r in rr]); B = np.array([r["train_sign"]["auc"] for r in rr])
            dA = np.array([r["test_sign"]["detection_rate"] for r in rr]); dB = np.array([r["train_sign"]["detection_rate"] for r in rr])
            fA = np.array([r["test_sign"]["false_alarm"] for r in rr]); fB = np.array([r["train_sign"]["false_alarm"] for r in rr])
            nd = sum(r["test_sign"]["polarity"] != r["train_sign"]["polarity"] for r in rr)
            print(f"  {t:.3f} {k:12s} AUC {A.mean():.3f}+-{A.std():.3f} -> {B.mean():.3f}+-{B.std():.3f}   "
                  f"dep {dA.mean()*100:5.1f} -> {dB.mean()*100:5.1f}%   FAR {fA.mean()*100:4.1f} -> {fB.mean()*100:4.1f}%   "
                  f"sign differs {nd}/3")
res["runtime_s"] = time.time() - t0
save("h17_polarity.json", res)
