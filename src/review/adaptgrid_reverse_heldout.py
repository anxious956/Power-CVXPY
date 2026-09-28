"""Reverse faults as a truly held-out class on adapt_grid (results/ADAPTGRID.md, "the CNN needs no directional
supervision").

On the benchmark the training negatives were the remote bus and the first 20 % of the next line, so a
reverse fault was a class the learned models had never seen, and "trips 0 reverse faults" was a statement
about generalisation. On adapt_grid the zone task's negatives are every short circuit off the protected line
(common.py: neg = shc & ~own), so relay-bus and behind-the-relay faults are in the training and calibration
sets: a CNN that trips none of them has been taught not to, which is weaker evidence that it "needs no
directional supervision".

This script runs the headline detector twice with identical code, seed and splits:
  in_training   the published task (negatives = every off-line short circuit)
  held_out      reverse faults (reverse_bus | reverse_lines) removed from training and calibration; they are
                scored like every other held class (switching, incipient): each fold model scores them and
                a row trips when at least half the fold models trip it
Everything else, including the zero-false-trip threshold (largest out-of-fold score among the training
negatives), is as adaptgrid_seeds.run_seed. Reported unsupervised and with 32P/32Q supervision, at cal0 and
roc0/roc1 (roc thresholds read off the pooled in-task negatives, which in held_out exclude reverse faults).

    python src/review/adaptgrid_reverse_heldout.py [--relays adapt_A adapt_B] [--frontend relayfe]
                                                   [--model "CNN seq-traj"] [--seed 0]
    -> results/adaptgrid/reverse_heldout_<frontend>_<model>.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import frontend
from review.zone_cv import splits
from review import q3_inputs as q3
from review.adaptgrid_run import (bundle, features, supervision, rates_plus, pooled_threshold, oof_negatives,
                                  fit_score, FAR, FEAT_OF)

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")
CLASSES = ("reverse_bus", "reverse_lines", "parallel", "beyond", "remote_bus_faults", "other", "switching", "own99")


def task(R, reverse_in_training):
    rev = R["reverse_bus"] | R["reverse_lines"]
    neg = R["neg"] if reverse_in_training else (R["neg"] & ~rev)
    idx = np.where(R["pos"] | neg)[0]
    return idx, R["pos"][idx].astype(int), R["groups"][idx]


def scores(R, F, model, idx, y, groups, kind, seed):
    """Out-of-fold scores of the task rows, per-fold scores of every other row, per-fold thresholds."""
    n = len(R["et"])
    hrows = np.setdiff1d(np.arange(n), idx)
    X = F[FEAT_OF[model]]
    Z, fold_of, H, thr0 = np.full(n, np.nan), np.full(n, -1), [], []
    for f, tr, te, meta in splits(kind, R, idx, y, groups):
        s = f + seed
        _, t0, (s_te, s_h) = fit_score(model, X[idx[tr]], y[tr], groups[tr], [X[idx[te]], X[hrows]], s)
        Z[idx[te]] = s_te; fold_of[idx[te]] = f
        H.append(np.asarray(s_h, float)); thr0.append(t0)
    return Z, fold_of, np.stack(H), np.array(thr0), hrows


def decisions(Z, fold_of, Hb, thr0, hrows, idx, y, op):
    n = len(Z); d = np.zeros(n, bool)
    if op == "cal0":
        m = fold_of >= 0
        d[m] = Z[m] > thr0[fold_of[m]]
        d[hrows] = np.mean(Hb > thr0[:, None], axis=0) >= 0.5
    else:
        tau = pooled_threshold(Z[idx][y == 0], 0 if op == "roc0" else 1)
        d[idx] = Z[idx] > tau
        d[hrows] = np.mean(Hb > tau, axis=0) >= 0.5
    return d


def summarise(d, R, idx, y):
    n = len(R["et"]); sel = np.arange(n)
    r = rates_plus(d, R, sel, idx, y, np.ones(n, bool))
    kn = lambda h: dict(k=r[h]["k"], n=r[h]["n"], ucb95=r[h]["dedup"]["ucb95"]) if h in r else None
    return dict(dependability=r["pos"]["rate"], dependability_ci=r["dependability_ci"],
                offline_all=dict(k=r["neg"]["dedup"]["k"], n=r["neg"]["dedup"]["n"], ucb95=r["neg"]["dedup"]["ucb95"]),
                per_class={h: kn(h) for h in CLASSES},
                dep_by_rf_bin={b: r["dep_by_rf_bin"][b]["rate"] for b in cm.RF_LABELS})


def run_relay(relay, model, kinds, seed):
    R = bundle(relay, None)
    n = len(R["et"])
    F = features(R, np.arange(n))
    fwd = supervision(R, np.arange(n))
    rev = R["reverse_bus"] | R["reverse_lines"]
    out = dict(n_reverse_bus=int(R["reverse_bus"].sum()), n_reverse_lines=int(R["reverse_lines"].sum()),
               n_offline=int(R["neg"].sum()), directional_blocks_reverse=dict(
                   k_forward=int((fwd & rev).sum()), n=int(rev.sum())), splits={})
    for kind in kinds:
        per = {}
        for label, rin in (("in_training", True), ("held_out", False)):
            idx, y, groups = task(R, rin)
            Z, fold_of, Hb, thr0, hrows = scores(R, F, model, idx, y, groups, kind, seed)
            per[label] = dict(n_task=int(len(idx)), n_task_neg=int((y == 0).sum()), thresholds_cal0=thr0.tolist())
            for op in ("cal0", "roc0", "roc1"):
                d = decisions(Z, fold_of, Hb, thr0, hrows, idx, y, op)
                per[label][op] = dict(unsupervised=summarise(d, R, idx, y), directional=summarise(d & fwd, R, idx, y))
            c = per[label]["cal0"]["unsupervised"]; pc = c["per_class"]
            print(f"  [{relay} {model} {kind} seed {seed}] reverse {label:11s}: cal0 dep {c['dependability']*100:5.1f}  "
                  f"off-line {c['offline_all']['k']}/{c['offline_all']['n']}  reverse bus {pc['reverse_bus']['k']}/{pc['reverse_bus']['n']}  "
                  f"lines behind {pc['reverse_lines']['k']}/{pc['reverse_lines']['n']}  switching {pc['switching']['k']}/{pc['switching']['n']}", flush=True)
        out["splits"][kind] = per
    return out


def main(relays=("adapt_A", "adapt_B"), fe="relayfe", model="CNN seq-traj", kinds=("grouped", "loqo"), seed=0):
    t0 = time.time()
    if fe == "relayfe":
        frontend.enable()
    res = dict(script="adaptgrid_reverse_heldout", commit=cm.git_commit(), frontend=fe, model=model, seed=seed,
               far=FAR, relays={})
    for relay in relays:
        res["relays"][relay] = run_relay(relay, model, kinds, seed)
        print(f"[{relay}] done [{time.time()-t0:.0f}s]", flush=True)
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    tag = "" if tuple(relays) == ("adapt_A", "adapt_B") else "_" + "-".join(relays)     # never overwrite the TestGrid run
    path = os.path.join(OUT, f"reverse_heldout_{fe}_{model.split()[0].lower()}{tag}.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, f"[{res['runtime_s']:.0f}s]")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--relays", nargs="+", default=["adapt_A", "adapt_B"])
    ap.add_argument("--frontend", default="relayfe")
    ap.add_argument("--model", default="CNN seq-traj")
    ap.add_argument("--splits", nargs="+", default=["grouped", "loqo"])
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    main(tuple(a.relays), a.frontend, a.model, tuple(a.splits), a.seed)
