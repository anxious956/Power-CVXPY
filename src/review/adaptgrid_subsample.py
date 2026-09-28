"""Is the CIGRE MV collapse a sample-size effect? The TestGrid CNN with as few in-zone faults as a CIGRE relay.

results/CIGREMV.md: at zero false trips the sequence-trajectory CNN covers 0-10.5 % on the CIGRE MV relays
against 70-99 % on TestGrid, and three causes are confounded there: short cables, inverter in-feed, and
only 72-84 in-zone faults to learn from instead of 168-207. This isolates the third on TestGrid, where the
first two are absent: the zone task keeps every off-line negative and a random subset of the in-zone faults
of the CIGRE size, and everything else is adaptgrid_seeds.run_seed unchanged (same folds, same inner-fold
calibration at zero false trips, same model).

Dependability is read on two sets:
  kept      the retained in-zone faults, scored out of fold: the CIGRE-analogous number
  dropped   the in-zone faults removed from the task, never trained or calibrated on, scored like every
            held row (fold-majority vote): a larger, fully held-out check of the same model
Security (off-line faults, switching) is on the same rows as always. run_seed's own 'dependability' key
counts every in-zone row, kept and dropped together; read the two keys above instead.

If the kept dependability stays near the full-size TestGrid result (adaptgrid_seeds: 94.6-99.4 % at A,
45-77 % at B), sample size does not explain CIGRE; if it falls to the CIGRE level, it can.

    python src/review/adaptgrid_subsample.py [--relays adapt_A adapt_B] [--sizes 72] [--draws 0 1 2]
    -> results/adaptgrid/subsample_relayfe_cnn.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import frontend
from review.zone_cv import zone_task
from review.adaptgrid_run import bundle, features, supervision
from review.adaptgrid_seeds import run_seed

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")
MODEL = "CNN seq-traj"


def subsample(idx, y, groups, size, draw):
    """All negatives, `size` in-zone faults drawn without replacement. Returns the task and the dropped rows."""
    pos = np.where(y == 1)[0]
    if size >= len(pos):
        raise ValueError(f"size {size} is not below the {len(pos)} in-zone faults")
    keep = np.random.default_rng(1000 * draw + size).choice(pos, size, replace=False)
    m = y == 0
    m[keep] = True
    return idx[m], y[m], groups[m], idx[~m]


def rate(d, rows):
    return dict(k=int(d[rows].sum()), n=int(len(rows)), rate=float(d[rows].mean()) if len(rows) else None)


def main(relays=("adapt_A", "adapt_B"), fe="relayfe", sizes=(72,), draws=(0, 1, 2), kinds=("grouped",), seed=0):
    t0 = time.time()
    if fe == "relayfe":
        frontend.enable()
    res = dict(script="adaptgrid_subsample", commit=cm.git_commit(), frontend=fe, model=MODEL, seed=seed,
               sizes=list(sizes), draws=list(draws), relays={})
    for relay in relays:
        R = bundle(relay, None)
        idx, y, groups = zone_task(R)
        F = features(R, np.arange(len(R["et"])))
        fwd = supervision(R, np.arange(len(R["et"])))
        rr = res["relays"][relay] = dict(n_pos_full=int(y.sum()), n_neg=int((y == 0).sum()), runs={})
        for size in sizes:
            for draw in draws:
                idx_s, y_s, g_s, dropped = subsample(idx, y, groups, size, draw)
                for kind in kinds:
                    out = run_seed(R, idx_s, y_s, g_s, F, fwd, kind, seed, MODEL, decisions=True)
                    dec = out.pop("_decisions")
                    kept = idx_s[y_s == 1]
                    for op in ("cal0", "roc0", "roc1"):
                        out[op]["dependability_kept"] = rate(dec[op], kept)
                        out[op]["dependability_dropped"] = rate(dec[op], dropped)
                    rr["runs"][f"{size}|{draw}|{kind}"] = out
                    c = out["cal0"]
                    print(f"  [{relay} {size} in-zone, draw {draw}, {kind}] cal0 dep kept {100 * c['dependability_kept']['rate']:5.1f} "
                          f"({c['dependability_kept']['k']}/{c['dependability_kept']['n']})  dropped "
                          f"{100 * c['dependability_dropped']['rate']:5.1f} ({c['dependability_dropped']['k']}/{c['dependability_dropped']['n']})  "
                          f"off-line {c['offline']['k']}/{c['offline']['n']}  switching {c['switching']['k']}/{c['switching']['n']}  "
                          f"[{time.time() - t0:.0f}s]", flush=True)
        del R, F
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"subsample_{fe}_cnn.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, f"[{res['runtime_s']:.0f}s]", flush=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--relays", nargs="+", default=["adapt_A", "adapt_B"])
    ap.add_argument("--frontend", default="relayfe")
    ap.add_argument("--sizes", type=int, nargs="+", default=[72])
    ap.add_argument("--draws", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--splits", nargs="+", default=["grouped"])
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    main(tuple(a.relays), a.frontend, tuple(a.sizes), tuple(a.draws), tuple(a.splits), a.seed)
