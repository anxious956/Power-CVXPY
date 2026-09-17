"""H19: the CNN standardises every waveform and channel by its own mean and std.

CNN with norm='per_waveform' (original) vs norm='global' (one scale per channel fitted on
train), same data, same seeds, OOF thresholds and train-chosen polarity (H17/H18 fixed).
Zone study, --quick sizes (350/250 per class), deltas 0, .1, .3, .514, 3 seeds, 12 epochs.

  python src/review/h19_cnn_norm.py [--deltas 0 0.514] [--epochs 12]
"""
import time, argparse
import numpy as np
from dataclasses import replace
from common import design_direction, save
from waveforms import SigParams
import detect as D
import zone_detect as Z

ap = argparse.ArgumentParser()
ap.add_argument("--deltas", type=float, nargs="+", default=[0.0, 0.10, 0.30, 0.514])
ap.add_argument("--epochs", type=int, default=12)
ap.add_argument("--n-train", type=int, default=350)
ap.add_argument("--n-test", type=int, default=250)
ap.add_argument("--tag", default="h19_cnn_norm")
ap.add_argument("--norms", nargs="+", default=["per_waveform", "global"])
args = ap.parse_args()

direction = design_direction()
grid = replace(Z.ZoneParams(), rF=0.3)
rows = []; t0 = time.time()
for t in args.deltas:
    for sd in range(3):
        Xtr, ytr, _ = Z.make_zone_dataset(args.n_train, np.random.default_rng(100 + 17 * sd), t * direction, SigParams(), grid)
        Xte, yte, _ = Z.make_zone_dataset(args.n_test, np.random.default_rng(999 + 31 * sd), t * direction, SigParams(), grid)
        for norm in args.norms:
            a, b = D.train_cnn(Xtr, ytr, Xte, epochs=args.epochs, seed=sd, oof_folds=5, norm=norm)
            rows.append(dict(delta=t, seed=sd, norm=norm, **D.evaluate(a, ytr, b, yte, polarity="train")))
    print(f"delta={t} [{time.time()-t0:.0f}s]", flush=True)

print("\ndelta  norm          AUC mean+-sd      dep@1% mean+-sd   FAR@1%")
for t in args.deltas:
    for norm in args.norms:
        rr = [r for r in rows if r["delta"] == t and r["norm"] == norm]
        a = np.array([r["auc"] for r in rr]); d = np.array([r["detection_rate"] for r in rr]) * 100
        f = np.array([r["false_alarm"] for r in rr]) * 100
        print(f"{t:.3f}  {norm:12s}  {a.mean():.4f}+-{a.std():.4f}   {d.mean():5.1f}+-{d.std():4.1f}   {f.mean():4.2f}")
save(args.tag + ".json", dict(rows=rows, args=vars(args), runtime_s=time.time() - t0))
