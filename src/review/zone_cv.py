"""H22 / H24 / H26 / H9: the within-relay zone decision of real_ml.py under four splits, learned side.
The conventional ladder runs on exactly the same folds in src/review/ladder.py.

Task (changed from real_ml.py, H9): positives = own line at 1, 20, 50, 80 %; negatives = faults beyond the
remote bus (as before) PLUS own-line faults at 99 %, which are outside zone 1 and were never negatives in
real_ml.py, so any threshold could overreach into the 85-100 % band at no cost. Own-99 % faults are used
for training, calibration and evaluation, and their trip rate is reported separately.

Splits (sibling groups = (target, location, fault type, R_f))
  stratified  RepeatedStratifiedKFold 5x2 over simulations (the real_ml.py protocol, inner folds ungrouped)
  grouped     StratifiedGroupKFold 5x2, inner out-of-fold thresholds grouped too
  lolo        leave one in-zone location out; negatives in grouped quarters
  lorfo       leave one fault resistance out

Detectors: MLP, gradient boosting, random forest (raw causal window), engineered + LR, exactly as
real_ml.models / fit_balanced / score, hyperparameters untouched. Threshold at 5 % false trip on
out-of-fold training scores of the negatives. Each fold's models are also scored on parallel-line,
reverse (relay bus, and lines behind it), other-fault and switching events.

Checkpoints: every (decision time, split, fold) is saved under logs/ckpt/zone_cv/<relay>/ as soon as it
finishes and skipped on restart.

    python src/review/zone_cv.py testgrid_B --times 20 --splits grouped stratified lorfo lolo
"""
import sys, os, json, time, argparse, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from review import common as cm
import real_ml
from zone_detect import zone_features

FAR = 0.05
HELD = ("parallel", "reverse_bus", "reverse_lines", "other", "switching")
MODELS = ("MLP", "gradient boosting", "random forest", "engineered + LR")


def zone_task(R):
    """Positions of the zone task: positives, beyond-remote-bus negatives, own-line 99 % negatives."""
    idx = np.where(R["pos"] | R["neg"] | R["own99"])[0]
    return idx, R["pos"][idx].astype(int), R["groups"][idx]


def splits(kind, R, idx, y, groups, seed=0):
    """Yields (fold_id, train, test, meta) as positions into idx."""
    if kind == "stratified":
        for f, (r, tr, te) in enumerate(cm.stratified_folds(y, groups, 5, 2, seed)):
            yield f, tr, te, dict(repeat=r)
    elif kind == "grouped":
        for f, (r, tr, te) in enumerate(cm.grouped_folds(y, groups, 5, 2, seed)):
            yield f, tr, te, dict(repeat=r)
    elif kind == "lolo":
        from sklearn.model_selection import GroupKFold
        loc = R["loc"][idx]
        negi = np.where(y == 0)[0]
        neg_folds = list(GroupKFold(4).split(negi, groups=groups[negi]))
        for f, L in enumerate((1.0, 20.0, 50.0, 80.0)):
            te_neg = negi[neg_folds[f][1]]
            te = np.concatenate([np.where((y == 1) & (loc == L))[0], te_neg])
            tr = np.setdiff1d(np.arange(len(y)), te)
            yield f, tr, te, dict(held_out_location=L)
    elif kind == "lorfo":
        rf = R["rf"][idx]
        for f, r in enumerate((40.0, 1.0, 10.0)):
            te, tr = np.where(rf == r)[0], np.where(rf != r)[0]
            yield f, tr, te, dict(held_out_rf=r)
    else:
        raise ValueError(kind)


def summarise(R, idx, y, groups, ii, dd):
    """Pooled test decisions -> rates with grouped-bootstrap intervals, own-99 % and the high-R_f stratum."""
    yy, gg = y[ii], groups[ii]
    is99 = R["own99"][idx][ii]
    beyond = R["neg"][idx][ii]
    rf = R["rf"][idx][ii]
    dep = lambda s: dd[s][yy[s] == 1].mean()
    ftr = lambda s: dd[s][beyond[s]].mean()
    f99 = lambda s: dd[s][is99[s]].mean()
    return dict(dependability=float(dep(slice(None))), false_trip_beyond=float(ftr(slice(None))),
                trip_own99=float(f99(slice(None))),
                false_trip_all_negatives=float(dd[yy == 0].mean()),
                dependability_ci=cm.grouped_bootstrap(dep, gg, 500), false_trip_beyond_ci=cm.grouped_bootstrap(ftr, gg, 500),
                trip_own99_ci=cm.grouped_bootstrap(f99, gg, 500),
                dep_by_rf={f"{r:g}": float(dd[(yy == 1) & (rf == r)].mean()) for r in (1, 10, 40) if ((yy == 1) & (rf == r)).any()},
                ft_beyond_by_rf={f"{r:g}": float(dd[beyond & (rf == r)].mean()) for r in (1, 10, 40) if (beyond & (rf == r)).any()},
                own99_by_rf={f"{r:g}": float(dd[is99 & (rf == r)].mean()) for r in (1, 10, 40) if (is99 & (rf == r)).any()})


def run(name, times, split_kinds, far=FAR, chain=None, tag=""):
    t0 = time.time()
    ck = os.path.join(cm.ROOT, "logs", "ckpt", "zone_cv", name + tag)
    os.makedirs(ck, exist_ok=True)
    R = cm.load_relay(name, chain)
    R["g"] = type("G", (), dict(z1=R["lp"]["z1"], z0_ratio=R["lp"]["z0"] / R["lp"]["z1"]))
    idx, y, groups = zone_task(R)
    held_idx = {h: np.where(R[h])[0] for h in HELD if R[h].any()}
    out = dict(relay=name, far=far, n_pos=int(y.sum()), n_beyond=int(R["neg"].sum()), n_own99=int(R["own99"].sum()),
               chain=chain or {}, n_held={h: int(len(v)) for h, v in held_idx.items()}, results={})
    for t in times:
        feats = None
        for kind in split_kinds:
            per_model = {n: [] for n in MODELS}
            for f, tr, te, meta in splits(kind, R, idx, y, groups):
                path = os.path.join(ck, f"t{t}_{kind}_f{f}.pkl")
                if os.path.exists(path):
                    rec = pickle.load(open(path, "rb"))
                else:
                    if feats is None:
                        all_idx = np.concatenate([idx] + list(held_idx.values()))
                        F_raw = real_ml.raw_window(R, all_idx, t)
                        F_eng = zone_features(real_ml.phasor_view(R, all_idx, t), R["g"])
                        offs, hsel = len(idx), {}
                        for h, v in held_idx.items():
                            hsel[h] = np.arange(offs, offs + len(v)); offs += len(v)
                        feats = ({"MLP": F_raw, "gradient boosting": F_raw, "random forest": F_raw, "engineered + LR": F_eng}, hsel)
                    fmap, hsel = feats
                    ytr, yte = y[tr], y[te]
                    g_in = groups[tr] if kind != "stratified" else None
                    rec = {}
                    for n, m in real_ml.models(f).items():
                        X = fmap[n][:len(idx)]
                        real_ml.fit_balanced(m, X[tr], ytr, f)
                        s_oof = cm.oof_scores(n, X[tr], ytr, f, groups=g_in)
                        thr = cm.thr_at_far(s_oof[ytr == 0], far)
                        s_te = real_ml.score(m, X[te])
                        rec[n] = dict(te=te, score=s_te, dec=s_te > thr, threshold=float(thr), meta=meta,
                                      auc=float(roc_auc_score(yte, s_te)) if 0 < yte.sum() < len(yte) else None,
                                      held={h: float((real_ml.score(m, fmap[n][hs]) > thr).mean()) for h, hs in hsel.items()})
                    pickle.dump(rec, open(path, "wb"))
                    print(f"  [{name}{tag}] t={t} {kind} fold {f} done [{time.time()-t0:.0f}s]", flush=True)
                for n in MODELS:
                    per_model[n].append(rec[n])
            summ = {}
            for n, folds in per_model.items():
                ii = np.concatenate([r["te"] for r in folds]); dd = np.concatenate([r["dec"] for r in folds])
                aucs = [r["auc"] for r in folds if r["auc"] is not None]
                summ[n] = dict(auc=float(np.mean(aucs)) if aucs else None, auc_sd=float(np.std(aucs)) if aucs else None,
                               **summarise(R, idx, y, groups, ii, dd),
                               **{f"trip_{h}": float(np.mean([r["held"][h] for r in folds])) for h in held_idx},
                               folds=[dict(auc=r["auc"], threshold=r["threshold"], **r["meta"],
                                           **{f"trip_{h}": r["held"][h] for h in held_idx}) for r in folds])
            out["results"].setdefault(str(t), {})[kind] = summ
            print(f"[{name}{tag}] t={t} ms, split={kind}")
            for n, S in summ.items():
                a = "  n/a " if S["auc"] is None else f"{S['auc']:.3f}"
                print(f"   {n:18s} AUC {a}  dep {S['dependability']*100:5.1f}  FT beyond {S['false_trip_beyond']*100:5.1f}  "
                      f"own99 {S['trip_own99']*100:5.1f}  dep@40ohm {S['dep_by_rf'].get('40', float('nan'))*100:5.1f}  "
                      + "  ".join(f"{h} {S['trip_' + h]*100:5.1f}" for h in held_idx), flush=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("relay")
    ap.add_argument("--times", type=int, nargs="+", default=[10, 20, 50])
    ap.add_argument("--splits", nargs="+", default=["stratified", "grouped", "lolo", "lorfo"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = run(a.relay, a.times, a.splits)
    os.makedirs(os.path.join(cm.ROOT, "results", "review"), exist_ok=True)
    path = a.out or os.path.join(cm.ROOT, "results", "review", f"zone_cv_{a.relay}.json")
    json.dump(res, open(path, "w"), indent=1)
    print("saved", path)
