"""Why relay B's protection-grade dependability depends on the split (results/ADAPTGRID.md section 4).

At the zero-false-trip operating point the sequence-trajectory CNN reads 45.4 % at relay B under
5-fold-over-loading-bins ('grouped') and 83.6 % under leave-one-loading-quartile-out ('loqo'). The gap
is larger than either confidence interval, so the split rule, not the detector, is deciding the answer.
This module finds out which.

It needs no refitting: the driver stores every fold's out-of-fold test score and every fold's threshold
under logs/scores/adaptgrid/, so the operating point can be taken apart after the fact.

WHAT IT MEASURES
  per fold      the calibrated threshold (the largest out-of-fold score among the TRAINING negatives,
                i.e. zero training false trips) and the dependability it buys on that fold's test
                positives. If the answer is driven by the threshold estimator rather than by the
                model, the spread across folds will be large and will track the threshold.
  per loading   dependability by loading bin and by loading quartile, so a failure concentrated in one
                band of the operating range is visible as such.
  missed        the positives that fall below the threshold, stratified by R_f band, fault type,
                location on the line, and the PRE-FAULT POWER FLOW at the relay: S = V1 conj(I1) on the
                3 cycles ending 20 ms before inception, reported as its angle. Relay B imports at about
                -163 deg at the nominal operating point; if the misses concentrate where that angle
                differs from the training folds' angles, the mechanism is operating-point transfer. If
                they do not, it is the threshold.
  negatives     the highest-scoring off-line faults, which are what set the threshold in the first
                place, with the same attributes.

    python src/review/adaptgrid_splitdiag.py [--relay adapt_B] [--frontend relayfe] [--model "CNN seq-traj"]
    -> results/adaptgrid/splitdiag_<relay>_<frontend>.json
"""
import os, sys, json, glob, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import frontend
from review.zone_cv import zone_task

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")
SCORES = os.path.join(cm.ROOT, "logs", "scores", "adaptgrid")


def load_scores(relay, fe, model, split, chain="matched"):
    for f in sorted(glob.glob(os.path.join(SCORES, f"{relay}_{fe}", "*.npz"))):
        z = np.load(f, allow_pickle=True)
        c = json.loads(str(z["config"]))
        if c["model"] == model and c["split"] == split and c["chains"] == chain:
            return z, c
    raise SystemExit(f"no stored scores for {relay} {fe} {model} {split} {chain}")


def prefault_flow(R, sel=None):
    """Pre-fault complex power at the relay, S = V1 conj(I1), from the 3 cycles ending 20 ms before
    inception (the same memory window the directional element uses). Returns |S| and arg(S) in degrees;
    arg near 180 deg means power flowing into the relay bus (import) on this sign convention."""
    sel = np.arange(len(R["et"])) if sel is None else sel
    end = R["ev"] - 128
    v = cm.seq_phasors(R["full"][sel][:, :3], end, 3 * 128)
    i = cm.seq_phasors(R["full"][sel][:, 3:], end, 3 * 128)
    S = v[:, 1] * np.conj(i[:, 1])
    return np.abs(S), np.degrees(np.angle(S))


def bin_table(mask_num, mask_den, key, order):
    out = {}
    for v in order:
        d = mask_den & (key == v)
        out[str(v)] = dict(n=int(d.sum()), k=int((mask_num & d).sum()),
                           rate=(float((mask_num & d).sum() / d.sum()) if d.sum() else None))
    return out


def diagnose(relay, fe, model, chain="matched", splits=("grouped", "loqo")):
    if fe == "relayfe":
        frontend.enable()
    R = cm.load_relay(relay)
    n = len(R["et"])
    idx, y, groups = zone_task(R)
    Smag, Sang = prefault_flow(R)
    res = dict(relay=relay, frontend=fe, model=model, chain=chain,
               prefault_flow_angle_deg=dict(median=float(np.median(Sang)), p5=float(np.percentile(Sang, 5)),
                                            p95=float(np.percentile(Sang, 95))),
               splits={})
    for split in splits:
        z, cfg = load_scores(relay, fe, model, split, chain)
        zs, fold_of, thr = z["zone_matched"], z["fold_of"], np.asarray(z["thr_cal0"])
        zi = z["idx"]
        yy = z["y"]
        got = fold_of[zi] >= 0
        dec = np.zeros(n, bool)
        dec[zi[got]] = zs[zi[got]] > thr[fold_of[zi[got]]]
        pos = np.zeros(n, bool); pos[zi[yy == 1]] = True
        neg = np.zeros(n, bool); neg[zi[yy == 0]] = True
        # per fold
        folds = []
        for f in range(len(thr)):
            m = (fold_of == f)
            fp, fn = m & pos, m & neg
            folds.append(dict(fold=int(f), threshold=float(thr[f]), n_pos=int(fp.sum()), n_neg=int(fn.sum()),
                              dependability=(float(dec[fp].mean()) if fp.any() else None),
                              false_trips=int(dec[fn].sum()),
                              median_flow_angle_deg=(float(np.median(Sang[fp])) if fp.any() else None)))
        dep_all = float(dec[pos].mean())
        missed = pos & ~dec
        # strata
        r = dict(n_folds=int(len(thr)), thresholds=[float(t) for t in thr],
                 threshold_spread=float(thr.max() - thr.min()), dependability=dep_all,
                 false_trips=int(dec[neg].sum()), n_pos=int(pos.sum()), n_neg=int(neg.sum()),
                 per_fold=folds,
                 dep_by_loading_bin=bin_table(dec, pos, R["groups"], sorted(set(R["groups"][pos].tolist()))),
                 dep_by_quartile=bin_table(dec, pos, R["op_quartile"], (0, 1, 2, 3)),
                 dep_by_rf_bin=bin_table(dec, pos, R["rf_bin"], cm.RF_LABELS),
                 dep_by_type=bin_table(dec, pos, R["et"], sorted(set(R["et"][pos].tolist()))),
                 dep_by_grounding=bin_table(dec, pos, R["grounding"], sorted(set(R["grounding"][pos].tolist()))))
        r["missed"] = dict(n=int(missed.sum()),
                           rf_median=(float(np.median(R["rf"][missed])) if missed.any() else None),
                           loc_median=(float(np.median(R["loc"][missed])) if missed.any() else None),
                           flow_angle_median=(float(np.median(Sang[missed])) if missed.any() else None),
                           flow_angle_p5_p95=([float(np.percentile(Sang[missed], 5)),
                                               float(np.percentile(Sang[missed], 95))] if missed.any() else None),
                           caught_flow_angle_median=(float(np.median(Sang[pos & dec])) if (pos & dec).any() else None),
                           score_margin_median=(float(np.median(thr[fold_of[missed]] - zs[missed])) if missed.any() else None))
        # the negatives that set the threshold
        ordn = np.argsort(-np.where(neg, zs, -np.inf))[:10]
        r["top_negatives"] = [dict(row=int(k), score=float(zs[k]), fold=int(fold_of[k]), type=str(R["et"][k]),
                                   rf=float(R["rf"][k]), loading_bin=int(R["groups"][k]),
                                   flow_angle_deg=float(Sang[k]),
                                   classes=[h for h in ("neg_bench", "remote_bus_faults", "beyond", "reverse_bus",
                                                        "reverse_lines", "parallel", "other") if h in R and R[h][k]])
                              for k in ordn]
        res["splits"][split] = r
        print(f"  [{relay} {fe} {model} {split}] dep {dep_all*100:5.1f}  false trips {r['false_trips']}  "
              f"folds {len(thr)}  threshold {thr.min():.3f}..{thr.max():.3f} (spread {r['threshold_spread']:.3f})  "
              f"missed {int(missed.sum())} of {int(pos.sum())}", flush=True)
        for f in folds:
            print(f"      fold {f['fold']:2d} thr {f['threshold']:7.3f}  pos {f['n_pos']:3d}  dep "
                  f"{(f['dependability'] or 0)*100:5.1f}  false {f['false_trips']}", flush=True)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"splitdiag_{relay}_{fe}.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, flush=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--relay", default="adapt_B")
    ap.add_argument("--frontend", default="relayfe")
    ap.add_argument("--model", default="CNN seq-traj")
    ap.add_argument("--chain", default="matched")
    a = ap.parse_args()
    diagnose(a.relay, a.frontend, a.model, a.chain)
