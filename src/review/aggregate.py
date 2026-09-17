"""Aggregate the zone_cv.py checkpoints into tables, refusing on any commit / config / code mismatch.

For every (relay, front end, own-99 % mode, decision time, split) run found under logs/ckpt/zone_cv/:
  - all fold checkpoints must carry one commit and the run's config; the experiment code (zone_cv.CODE) must be
    identical between that commit and HEAD, otherwise the run is refused
  - per model: fold AUC mean +- sd; pooled test decisions -> dependability (grouped-bootstrap CI), beyond /
    remote-bus false trips (deduplicated k/n, one-sided 95 % upper bound), dependability by R_f;
    own-99 % guard band and every held-out class (parallel, relay-bus reverse, lines behind, other, switching):
    mean trip rate over the fold models and the worst fold's deduplicated k/n with its upper bound, flagging
    classes too small to support a 5 % budget
  - per-class operating curves (beyond, relay-bus reverse, own-99 %): per fold, dependability as a function of
    the class false-trip rate, interpolated on a common grid and averaged over folds
  - matched comparison: learned dependability at the beyond false-trip rate of ladder rungs R1 and T2

    python src/review/aggregate.py
"""
import sys, os, json, glob, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from review import common as cm
from review import zone_cv

GRID = np.linspace(0, 0.2, 21)
MODELS = zone_cv.MODELS


def curve(scores_pos, scores_neg):
    """Dependability at each false-trip rate on GRID (threshold between sorted negative scores)."""
    neg = np.sort(scores_neg)[::-1]
    out = []
    for fa in GRID:
        k = int(np.floor(fa * len(neg)))
        thr = neg[k] if k < len(neg) else -np.inf
        out.append(float((scores_pos > thr).mean()))
    return out


def main():
    head = cm.git_commit()
    base = os.path.join(cm.ROOT, "logs", "ckpt", "zone_cv")
    relays = {}
    summary = {}
    for relay_dir in sorted(glob.glob(os.path.join(base, "*"))):
        name = os.path.basename(relay_dir)
        for run_dir in sorted(glob.glob(os.path.join(relay_dir, "*"))):
            files = sorted(glob.glob(os.path.join(run_dir, "*.pkl")))
            if not files:
                continue
            recs = [pickle.load(open(f, "rb")) for f in files]
            cfg, commit = recs[0]["_config"], recs[0]["_commit"]
            if any(r["_config"] != cfg or r["_commit"] != commit for r in recs):
                raise SystemExit(f"{run_dir}: checkpoints disagree on commit or config; refusing to aggregate")
            if cm.config_hash(cfg) != os.path.basename(run_dir):
                raise SystemExit(f"{run_dir}: directory hash does not match config; refusing to aggregate")
            if not cm.code_unchanged(commit, head, zone_cv.CODE):
                raise SystemExit(f"{run_dir}: experiment code changed between {commit} and HEAD; refusing to aggregate")
            fe = "relay-bandwidth" if cfg["chain"].get("relay_aa") else "current"
            expected = {"grouped": 10, "stratified": 10, "lorfo": 3, "lolo": 4}[cfg["split"]]
            complete = len(recs) == expected
            if name not in relays:
                relays[name] = cm.load_relay(name)
            R = relays[name]
            idx, y, groups = zone_cv.zone_task(R, cfg["own99"])
            pos_of = {int(i): k for k, i in enumerate(idx)}
            held_idx = {h: np.where(R[h])[0] for h in cfg["held"]}
            key = f"{name} | {fe} | own99 {cfg['own99']} | {cfg['t']} ms | {cfg['split']}"
            S = dict(commit=commit, config=cfg, folds=len(recs), complete=complete, models={})
            for n in MODELS:
                te_all, dec_all, aucs, held_dec, curves = [], [], [], {h: [] for h in held_idx}, {"beyond": [], "reverse_bus": [], "own99": []}
                for r in recs:
                    m = r["models"][n]
                    te = np.array([pos_of[int(i)] for i in r["test_idx"]])
                    s, thr = m["test_score"], m["threshold"]
                    te_all.append(te); dec_all.append(s > thr)
                    yt = y[te]
                    if 0 < yt.sum() < len(yt):
                        aucs.append(roc_auc_score(yt, s))
                    for h in held_idx:
                        held_dec[h].append(m["held_score"][h] > thr)
                    beyond = R["neg"][idx][te]
                    if (yt == 1).any() and beyond.any():
                        curves["beyond"].append(curve(s[yt == 1], s[beyond]))
                    for h in ("reverse_bus", "own99"):
                        if h in m["held_score"] and (yt == 1).any():
                            curves[h].append(curve(s[yt == 1], m["held_score"][h]))
                ii, dd = np.concatenate(te_all), np.concatenate(dec_all)
                yy, gg = y[ii], groups[ii]
                beyond = R["neg"][idx][ii]
                dep = lambda s_: dd[s_][yy[s_] == 1].mean()
                rf = R["rf"][idx][ii]
                M = dict(auc=float(np.mean(aucs)) if aucs else None, auc_sd=float(np.std(aucs)) if aucs else None,
                         dependability=float(dep(slice(None))), dependability_ci=cm.grouped_bootstrap(dep, gg, 500),
                         dep_by_rf={f"{x:g}": float(dd[(yy == 1) & (rf == x)].mean()) for x in (1, 10, 40) if ((yy == 1) & (rf == x)).any()},
                         beyond=cm.dedup_rate(dd, R["dedup"][idx][ii], beyond))
                if cfg["own99"] == "negative":
                    M["own99_test"] = cm.dedup_rate(dd, R["dedup"][idx][ii], R["own99"][idx][ii])
                for h, v in held_dec.items():
                    per = [cm.dedup_rate(d, R["dedup"][held_idx[h]], np.ones(len(d), bool)) for d in v]
                    worst = max(per, key=lambda z: z["ucb95"])
                    M[h] = dict(mean_rate=float(np.mean([z["rate"] for z in per])), worst_fold=worst,
                                supports_5pct_budget=bool(worst["n"] >= cm.min_n_for_budget(0.05)))
                M["operating_curves"] = {h: np.mean(c, axis=0).tolist() for h, c in curves.items() if c}
                S["models"][n] = M
            summary[key] = S
            print(f"{key}  folds {len(recs)}{'' if complete else ' (INCOMPLETE)'}", flush=True)
            for n, M in S["models"].items():
                g = lambda h: (f"{M[h]['mean_rate']*100:5.1f}" if h in M else "   - ")
                print(f"   {n:18s} AUC {M['auc']:.3f}+-{M['auc_sd']:.3f}  dep {M['dependability']*100:5.1f}  dep@40 "
                      f"{M['dep_by_rf'].get('40', float('nan'))*100:5.1f}  beyond {M['beyond']['k']}/{M['beyond']['n']} "
                      f"(UCB {M['beyond']['ucb95']*100:4.1f})  own99 {g('own99')}  rev-bus {g('reverse_bus')}  "
                      f"lines-behind {g('reverse_lines')}  parallel {g('parallel')}  other {g('other')}  switching {g('switching')}", flush=True)
    # matched comparison against the ladder (same relay, front end, 20 ms, grouped, guard band)
    ladders = {}
    for fe, fn in (("current", "ladder.json"), ("relay-bandwidth", "ladder_relay_frontend.json")):
        p = os.path.join(cm.ROOT, "results", "review", fn)
        if os.path.exists(p):
            ladders[fe] = json.load(open(p))
    for key, S in summary.items():
        name, fe, mode, t, split = [s.strip() for s in key.split("|")]
        if split != "grouped" or mode != "own99 guard" or fe not in ladders or name not in ladders[fe]:
            continue
        L = ladders[fe][name]
        tt = t.split()[0]
        refs = {}
        if f"{tt}|R1" in L["fixed"]:
            refs["R1"] = L["fixed"][f"{tt}|R1"]["neg"]["rate"]
        k2 = f"{tt}|grouped|T2|own99-guard"
        if k2 in L["tuned"]:
            refs["T2"] = L["tuned"][k2]["false_trip_beyond"]
        refs["R2"] = L["fixed"][f"{tt}|R2"]["neg"]["rate"] if f"{tt}|R2" in L["fixed"] else None
        for n, M in S["models"].items():
            c = M["operating_curves"].get("beyond")
            if c is None:
                continue
            M["dependability_at_ladder_false_trip"] = {r: (float(np.interp(v, GRID, c)) if v is not None else None) for r, v in refs.items()}
    json.dump(summary, open(os.path.join(cm.ROOT, "results", "review", "zone_cv_summary.json"), "w"), indent=1, default=str)
    print("saved results/review/zone_cv_summary.json")


if __name__ == "__main__":
    main()
