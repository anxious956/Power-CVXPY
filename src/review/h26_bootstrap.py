"""H26 (synthetic): confidence interval on "the reactance element falls 0.952 -> 0.863".

Reads a zone sweep's raw test scores (zone_detect.py --out ... --tag ..., which writes
<tag>.json and <tag>_scores.npz) and runs a two-level paired bootstrap:
  level 1: resample seeds with replacement (3 of 3),
  level 2: within each drawn seed, resample test samples stratified by class,
with the SAME resampled indices at every delta (the test sets at different delta share their
random draws, so the comparison across delta is paired). Polarity is the train-chosen sign stored
per seed in the json (H17); if a json predates that field, the sign that makes the test AUC >= 0.5
is used (the legacy behaviour for AUC).
Reports, per detector: mean AUC per delta with 95 % percentile CI, AUC(last) - AUC(first) with CI,
and the least-squares slope of AUC vs delta with CI.

  python src/review/h26_bootstrap.py zone_quick_fixed [zone_full_fixed ...] [--B 2000]
"""
import sys, json, os, argparse, time
import numpy as np
from scipy.stats import rankdata
from common import OUT, save

ap = argparse.ArgumentParser()
ap.add_argument("tags", nargs="+")
ap.add_argument("--B", type=int, default=2000)
args = ap.parse_args()


def auc(s, y):
    r = rankdata(s)
    n1 = (y == 1).sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


result = {}
for tag in args.tags:
    t0 = time.time()
    meta = json.load(open(os.path.join(OUT, tag + ".json")))
    Z = np.load(os.path.join(OUT, tag + "_scores.npz"))
    mags = meta["magnitudes"]
    seeds = sorted({int(k.rsplit("_", 1)[1]) for k in Z.files if k.startswith("y_")})
    dets = [k for k in ("reactance", "negseq", "engineered", "cnn") if f"{k}_{mags[0]}_{seeds[0]}" in Z.files]
    rng = np.random.default_rng(12345)
    out = {}; signs = {}
    for det in dets:
        sign = signs[det] = {}
        for i, t in enumerate(mags):
            ps = meta["rows"][i][det].get("per_seed")
            for sd in seeds:
                s, y = Z[f"{det}_{t}_{sd}"], Z[f"y_{t}_{sd}"]
                if ps is not None:
                    sign[(t, sd)] = ps[sd]["polarity"]
                else:
                    sign[(t, sd)] = 1 if auc(s, y) >= 0.5 else -1
        # point estimate
        point = [np.mean([auc(sign[(t, sd)] * Z[f"{det}_{t}_{sd}"], Z[f"y_{t}_{sd}"]) for sd in seeds]) for t in mags]
        boots = np.zeros((args.B, len(mags)))
        y0 = {sd: Z[f"y_{mags[0]}_{sd}"] for sd in seeds}
        for b in range(args.B):
            drawn = rng.choice(seeds, size=len(seeds), replace=True)
            idxs = []
            for sd in drawn:
                y = y0[sd]
                pos, neg = np.where(y == 1)[0], np.where(y == 0)[0]
                idxs.append((sd, np.r_[rng.choice(pos, len(pos)), rng.choice(neg, len(neg))]))
            for i, t in enumerate(mags):
                boots[b, i] = np.mean([auc(sign[(t, sd)] * Z[f"{det}_{t}_{sd}"][ix], Z[f"y_{t}_{sd}"][ix])
                                       for sd, ix in idxs])
        ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
        diff = boots[:, -1] - boots[:, 0]
        slopes = np.polyfit(mags, boots.T, 1)[0]
        out[det] = dict(auc=[float(p) for p in point], auc_ci=[ci(boots[:, i]) for i in range(len(mags))],
                        diff_last_minus_first=float(point[-1] - point[0]), diff_ci=ci(diff),
                        slope=float(np.polyfit(mags, point, 1)[0]), slope_ci=ci(slopes),
                        frac_boot_diff_below_0=float((diff < 0).mean()),
                        polarities=sorted({int(v) for v in sign.values()}))
        o = out[det]
        print(f"[{tag}] {det:10s} AUC " + "  ".join(f"{p:.3f}[{c[0]:.3f},{c[1]:.3f}]" for p, c in zip(o['auc'], o['auc_ci'])))
        print(f"[{tag}] {det:10s} AUC({mags[-1]})-AUC({mags[0]}) = {o['diff_last_minus_first']:+.4f} "
              f"95% CI [{o['diff_ci'][0]:+.4f}, {o['diff_ci'][1]:+.4f}]   slope {o['slope']:+.4f}/pu "
              f"CI [{o['slope_ci'][0]:+.4f}, {o['slope_ci'][1]:+.4f}]   P(diff<0) {o['frac_boot_diff_below_0']:.3f}  "
              f"signs used {o['polarities']}", flush=True)
    # which fault type drives each detector's trend: AUC of AG vs AG2 and AB vs AB2 separately
    if f"kind_{mags[0]}_{seeds[0]}" in Z.files:
        by_kind = {}
        for det in dets:
            for pos, neg in (("ag", "ag2"), ("ab", "ab2")):
                vals = []
                for t in mags:
                    a_ = []
                    for sd in seeds:
                        s, y, k = Z[f"{det}_{t}_{sd}"], Z[f"y_{t}_{sd}"], Z[f"kind_{t}_{sd}"]
                        m = (k == pos) | (k == neg)
                        a_.append(auc(signs[det][(t, sd)] * s[m], y[m]))
                    vals.append(float(np.mean(a_)))
                by_kind[f"{det}|{pos}-vs-{neg}"] = vals
                print(f"[{tag}] {det:10s} {pos}-vs-{neg} AUC " + "  ".join(f"{v:.3f}" for v in vals))
        out["auc_by_kind_pair"] = by_kind
    out["runtime_s"] = time.time() - t0
    out["B"] = args.B
    result[tag] = out
save("h26_bootstrap_" + "_".join(args.tags) + ".json", result)
