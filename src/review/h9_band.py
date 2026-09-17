"""H9: the 85-100 % band of the protected line is never sampled.

Positives are own-line faults at m in [0.62, 0.85], negatives adjacent-line faults at m in
[0.02, 0.18]; own-line faults between the reach and the remote bus appear in neither class.
Two evaluations with the corrected pipeline (H17/H18/H19/H21 fixes; cfg = FIXED):
  (a) don't-care band: detectors trained as in the study; own-line AG/AB faults at m in
      [0.85, 1.0] are scored and the fraction TRIPPED at the 1 % FAR operating point is reported
      (a zone-1 element should trip for few of these, and none near m = 1);
  (b) band as negatives: the same band faults added to the negative class in train and test.
--quick sizes (350 train / 250 test per kind; band 350 / 250 per kind), 3 seeds.

  python src/review/h9_band.py [--deltas 0 0.514] [--seeds 3] [--no-cnn]
"""
import time, argparse
import numpy as np
from dataclasses import replace
from synth_common import design_direction, save, FIXED
from waveforms import SigParams
import detect as D
import zone_detect as Z

ap = argparse.ArgumentParser()
ap.add_argument("--deltas", type=float, nargs="+", default=[0.0, 0.514])
ap.add_argument("--seeds", type=int, default=3)
ap.add_argument("--epochs", type=int, default=12)
ap.add_argument("--no-cnn", action="store_true")
args = ap.parse_args()

direction = design_direction()
grid = replace(Z.ZoneParams(), rF=0.3)
BAND = (0.85, 1.0)
cfg = dict(FIXED)
keys = list(Z.KEYS) if not args.no_cnn else [k for k in Z.KEYS if k != "cnn"]


def scores(Xtr, ytr, Xte, sd):
    if args.no_cnn:
        import zone_detect as ZZ
        orig = ZZ.train_cnn
        ZZ.train_cnn = lambda a, b, c, **k: (np.zeros(len(a)), np.zeros(len(c)))
        try:
            return Z.score_all(Xtr, ytr, Xte, grid, seed=sd, epochs=args.epochs, cfg=cfg)
        finally:
            ZZ.train_cnn = orig
    return Z.score_all(Xtr, ytr, Xte, grid, seed=sd, epochs=args.epochs, cfg=cfg)


rows = []; t0 = time.time()
for t in args.deltas:
    d = t * direction
    for sd in range(args.seeds):
        Xtr, ytr, _ = Z.make_zone_dataset(350, np.random.default_rng(100 + 17 * sd), d, SigParams(), grid)
        Xte, yte, _ = Z.make_zone_dataset(250, np.random.default_rng(999 + 31 * sd), d, SigParams(), grid)
        Btr, _, _, mtr = Z.make_zone_dataset(350, np.random.default_rng(5100 + 17 * sd), d, SigParams(), grid,
                                             kinds_pos=("ag", "ab"), kinds_neg=(), m_range=BAND, return_meta=True)
        Bte, _, bk, mte = Z.make_zone_dataset(250, np.random.default_rng(5999 + 31 * sd), d, SigParams(), grid,
                                              kinds_pos=("ag", "ab"), kinds_neg=(), m_range=BAND, return_meta=True)
        mb = np.array([m["m"] for m in mte])
        # (a) don't-care: train as in the study, score test + band in one pass
        sc = scores(Xtr, ytr, np.concatenate([Xte, Bte]), sd)
        for k in keys:
            s_tr, s_all = sc[k]
            s_te, s_b = s_all[:len(Xte)], s_all[len(Xte):]
            ev = D.evaluate(s_tr, ytr, s_te, yte)
            trip = ev["polarity"] * s_b > ev["threshold"]
            rows.append(dict(eval="dont_care", delta=t, seed=sd, det=k, **ev,
                             band_trip=float(trip.mean()),
                             band_trip_85_925=float(trip[mb < 0.925].mean()),
                             band_trip_925_100=float(trip[mb >= 0.925].mean())))
        # (b) band faults as negatives in train and test
        Xtr2 = np.concatenate([Xtr, Btr]); ytr2 = np.r_[ytr, np.zeros(len(Btr), int)]
        Xte2 = np.concatenate([Xte, Bte]); yte2 = np.r_[yte, np.zeros(len(Bte), int)]
        sc2 = scores(Xtr2, ytr2, Xte2, sd)
        for k in keys:
            ev = D.evaluate(sc2[k][0], ytr2, sc2[k][1], yte2)
            rows.append(dict(eval="band_negative", delta=t, seed=sd, det=k, **ev))
        print(f"delta={t} seed={sd} [{time.time()-t0:.0f}s]", flush=True)

print("\n(a) band [0.85, 1.0] as don't-care: fraction tripped at the 1 % FAR point (mean +- sd over seeds)")
for t in args.deltas:
    for k in keys:
        rr = [r for r in rows if r["eval"] == "dont_care" and r["delta"] == t and r["det"] == k]
        f = lambda n: np.array([r[n] for r in rr]) * 100
        print(f"  d={t:.3f} {k:11s} study AUC {np.mean([r['auc'] for r in rr]):.3f}  dep {f('detection_rate').mean():5.1f}%  "
              f"band trip {f('band_trip').mean():5.1f}+-{f('band_trip').std():4.1f}%  "
              f"(0.85-0.925: {f('band_trip_85_925').mean():5.1f}%, 0.925-1.0: {f('band_trip_925_100').mean():5.1f}%)")
print("\n(b) band as negatives: AUC and dependability at 1 % FAR")
for t in args.deltas:
    for k in keys:
        rr = [r for r in rows if r["eval"] == "band_negative" and r["delta"] == t and r["det"] == k]
        a = np.array([r["auc"] for r in rr]); dd = np.array([r["detection_rate"] for r in rr]) * 100
        fa = np.array([r["false_alarm"] for r in rr]) * 100
        print(f"  d={t:.3f} {k:11s} AUC {a.mean():.3f}+-{a.std():.3f}  dep {dd.mean():5.1f}+-{dd.std():4.1f}%  FAR {fa.mean():4.2f}%")
save("h9_band.json", dict(rows=rows, args=vars(args), runtime_s=time.time() - t0))
