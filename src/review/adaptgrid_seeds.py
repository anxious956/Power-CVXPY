"""Seed stability and exact security bounds for the headline detector (results/ADAPTGRID.md section 4).

The relay A result is a ZERO COUNT, not a zero rate: 0 of 2,888 off-line faults and 0 of 5,474 switching
events. A zero count on n trials is only as strong as n makes it, so every zero here is reported with its
one-sided 95 % Clopper-Pearson upper bound. And a single training seed is one draw: the CNN's
initialisation, its batch order and the inner calibration folds all move with it, so the run is repeated
over several seeds and the spread is reported rather than the best draw.

WHAT IS AND IS NOT RE-DRAWN. The seed offset changes the model's initialisation and the inner
calibration folds (`oof_negatives` uses seed) and the outer split's fold assignment is left alone, so
the comparison is like for like across seeds. The threshold is still the largest out-of-fold score among
the TRAINING negatives only: the calibration never sees a test row, and because the inner folds are
grouped by loading bin, it never sees a test operating point either. `threshold_provenance` asserts both
of those on the actual index sets rather than claiming them.

    python src/review/adaptgrid_seeds.py [--relay adapt_A] [--frontend relayfe] [--seeds 0 100 200]
    -> results/adaptgrid/seeds_<relay>_<frontend>_<model>.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import frontend
from review.zone_cv import zone_task, splits
from review import q3_inputs as q3
from review.adaptgrid_run import bundle, features, supervision, rates_plus, pooled_threshold, FAR, T, FEAT_OF

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")


def threshold_provenance(Rtr, idx, y, groups, kind, seed=0):
    """Check on the actual index sets that the calibration never touches a test row or a test loading
    bin. Returns the worst overlap found (both should be zero)."""
    from sklearn.model_selection import StratifiedGroupKFold
    worst_rows, worst_bins = 0, 0
    for f, tr, te, meta in splits(kind, Rtr, idx, y, groups):
        gtr = groups[tr]
        for a, b in StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(np.zeros((len(tr), 1)), y[tr], gtr):
            cal_rows = set(idx[tr][b].tolist())            # rows whose OOF scores set the threshold
            worst_rows = max(worst_rows, len(cal_rows & set(idx[te].tolist())))
            worst_bins = max(worst_bins, len(set(groups[tr][b].tolist()) & set(groups[te].tolist())))
    return dict(calibration_rows_in_test=int(worst_rows), calibration_bins_in_test=int(worst_bins),
                out_of_fold=bool(worst_rows == 0), operating_points_disjoint=bool(worst_bins == 0))


def run_seed(R, idx, y, groups, F, fwd, kind, seed_offset, model="CNN seq-traj"):
    n = len(R["et"]); sel = np.arange(n)
    fk = FEAT_OF[model]
    hrows = np.setdiff1d(sel, idx)
    Z = np.full(n, np.nan)
    H, thr0, thrf, fold_of = [], [], [], np.full(n, -1)
    for f, tr, te, meta in splits(kind, R, idx, y, groups):
        s = f + seed_offset

        from review.adaptgrid_run import oof_negatives
        neg = oof_negatives(q3.cnn_scores, F[fk][idx[tr]], y[tr], groups[tr], s)
        t_far, t_0 = cm.thr_at_far(neg, FAR), float(neg.max())
        s_te, s_h = q3.cnn_scores(F[fk][idx[tr]], y[tr], [F[fk][idx[te]], F[fk][hrows]], s)
        Z[idx[te]] = s_te
        H.append(np.asarray(s_h, float))
        thr0.append(t_0); thrf.append(t_far); fold_of[idx[te]] = f
    Hb = np.stack(H)
    out = {}
    for op in ("cal0", "roc0", "roc1"):
        d = np.zeros(n, bool)
        if op == "cal0":
            t = np.array(thr0)
            m = fold_of >= 0
            d[m] = Z[m] > t[fold_of[m]]
            d[hrows] = np.mean(Hb > t[:, None], axis=0) >= 0.5
        else:
            tau = pooled_threshold(Z[idx][y == 0], 0 if op == "roc0" else 1)
            d[idx] = Z[idx] > tau
            d[hrows] = np.mean(Hb > tau, axis=0) >= 0.5
        r = rates_plus(d, R, sel, idx, y, np.ones(n, bool))
        out[op] = dict(dependability=r["pos"]["rate"],
                       offline=dict(k=r["neg"]["dedup"]["k"], n=r["neg"]["dedup"]["n"], ucb95=r["neg"]["dedup"]["ucb95"]),
                       switching=dict(k=r["switching"]["k"], n=r["switching"]["n"],
                                      ucb95=cm.dedup_rate(d, R["dedup"], R["switching"])["ucb95"]),
                       incipient=dict(k=r["incipient"]["k"], n=r["incipient"]["n"], ucb95=r["incipient"]["ucb95"]),
                       guard=dict(k=r["own99"]["k"], n=r["own99"]["n"]),
                       dep_by_rf_bin={b: (r["dep_by_rf_bin"][b]["rate"]) for b in cm.RF_LABELS})
    out["thresholds_cal0"] = [float(t) for t in thr0]
    return out


def main(relay="adapt_A", fe="relayfe", model="CNN seq-traj", kinds=("grouped", "loqo"), seeds=(0, 100, 200)):
    t0 = time.time()
    if fe == "relayfe":
        frontend.enable()
    R = bundle(relay, None)
    idx, y, groups = zone_task(R)
    F = features(R, np.arange(len(R["et"])))
    fwd = supervision(R, np.arange(len(R["et"])))
    res = dict(relay=relay, frontend=fe, model=model, seeds=list(seeds), commit=cm.git_commit(), splits={})
    res["threshold_provenance"] = {k: threshold_provenance(R, idx, y, groups, k) for k in kinds}
    print("threshold provenance:", res["threshold_provenance"], flush=True)
    for kind in kinds:
        per = {}
        for s in seeds:
            per[str(s)] = run_seed(R, idx, y, groups, F, fwd, kind, s, model)
            c = per[str(s)]["cal0"]
            print(f"  [{relay} {fe} {model} {kind} seed+{s}] cal0 dep {c['dependability']*100:5.1f}  "
                  f"off-line {c['offline']['k']}/{c['offline']['n']} (<={c['offline']['ucb95']*100:.2f}%)  "
                  f"switching {c['switching']['k']}/{c['switching']['n']} (<={c['switching']['ucb95']*100:.2f}%)  "
                  f"roc0 {per[str(s)]['roc0']['dependability']*100:5.1f}  roc1 {per[str(s)]['roc1']['dependability']*100:5.1f}", flush=True)
        dep = [per[str(s)]["cal0"]["dependability"] for s in seeds]
        res["splits"][kind] = dict(per_seed=per, cal0_dependability=dict(
            values=[float(d) for d in dep], mean=float(np.mean(dep)), min=float(np.min(dep)), max=float(np.max(dep)),
            spread=float(np.max(dep) - np.min(dep))))
        off = [per[str(s)]["cal0"]["offline"]["k"] for s in seeds]
        res["splits"][kind]["cal0_offline_trips"] = [int(k) for k in off]
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"seeds_{relay}_{fe}_{model.split()[0].lower()}.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, f"[{res['runtime_s']:.0f}s]")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--relay", default="adapt_A")
    ap.add_argument("--frontend", default="relayfe")
    ap.add_argument("--model", default="CNN seq-traj")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 100, 200])
    ap.add_argument("--splits", nargs="+", default=["grouped", "loqo"])
    a = ap.parse_args()
    main(a.relay, a.frontend, a.model, tuple(a.splits), tuple(a.seeds))
