"""
H1 (evaluation): AUC of the zone detectors along two injection directions at the same magnitudes:
the author's direction (-23.2 deg, from the two-bus weak_sg design) and an alternative direction
taken from the zone scan (fewest non-separated IN/OUT pairs, wp1_h1_zone_design.py). Reuses
zone_detect's generator, detectors and evaluation unchanged.

QUICK SIZES, ONE SEED: n_train = 350 and n_test = 250 per class-kind (zone_detect --quick sizes),
CNN 12 epochs, seed 0 only. Differences below ~0.01 AUC are within seed noise (ZONE.md reports
sd 0.001-0.009 at 3 seeds with larger sets).

  python src/review/wp1_h1_zone_auc.py --angles -23.2 120 [--mags 0 0.1 0.3 0.514] [--no-cnn]
"""
import sys, os, time, argparse
from dataclasses import replace
import numpy as np
from wp1_common import dump
import zone_detect as zd
from zone_model import ZoneParams
from detect import evaluate, train_cnn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--angles", type=float, nargs="+", default=[-23.2, 120.0])
    ap.add_argument("--mags", type=float, nargs="+", default=[0.0, 0.1, 0.3, 0.514])
    ap.add_argument("--rf", type=float, default=0.3)
    ap.add_argument("--no-cnn", action="store_true")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    grid = replace(ZoneParams(), rF=args.rf)
    p = zd.SigParams()
    out = dict(n_train=350, n_test=250, seeds=[0], epochs=12, rf=args.rf, rows=[])
    t0 = time.time()
    for ang in args.angles:
        for mag in args.mags:
            if mag == 0 and ang != args.angles[0]:
                continue
            d = mag * np.exp(1j * np.deg2rad(ang))
            Xtr, ytr, _ = zd.make_zone_dataset(350, np.random.default_rng(100), d, p, grid, True)
            Xte, yte, _ = zd.make_zone_dataset(250, np.random.default_rng(999), d, p, grid, True)
            row = dict(angle=ang, mag=mag)
            row["reactance"] = evaluate(zd.score_reactance(Xtr, grid), ytr, zd.score_reactance(Xte, grid), yte)["auc"]
            row["negseq"] = evaluate(zd.score_negseq(Xtr), ytr, zd.score_negseq(Xte), yte)["auc"]
            e_tr, e_te = zd.score_engineered(Xtr, ytr, Xte, grid, seed=0)
            row["engineered"] = evaluate(e_tr, ytr, e_te, yte)["auc"]
            if not args.no_cnn:
                s_tr, s_te = train_cnn(Xtr, ytr, Xte, epochs=12, seed=0)
                row["cnn"] = evaluate(s_tr, ytr, s_te, yte)["auc"]
            out["rows"].append(row)
            print(f"angle {ang:7.1f} |d|={mag:.3f}: AUC reactance {row['reactance']:.4f}  |i-| {row['negseq']:.4f}  "
                  f"engineered {row['engineered']:.4f}  cnn {row.get('cnn', float('nan')):.4f}  [{time.time()-t0:.0f}s]", flush=True)
    out["runtime_s"] = time.time() - t0
    dump(out, f"h1_zone_auc{args.tag}.json")


if __name__ == "__main__":
    main()
