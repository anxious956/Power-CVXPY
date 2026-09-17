"""H22 / H24 / H26 / H9: the within-relay zone decision of real_ml.py under four splits, learned side.
The conventional ladder runs on exactly the same folds in src/review/ladder.py.

Task
  positives        own line at 1, 20, 50, 80 % (as real_ml.py)
  negatives        faults beyond the remote bus and on the remote bus (as real_ml.py) for training and
                   calibration; security is evaluated on every off-line class: beyond / remote bus (test
                   folds), relay-bus reverse faults, lines behind the relay, the parallel line, other faults
  guard band       own line at 99 %: tripping there still clears the faulted line, so it is neither a
                   positive nor a negative; not used for training or calibration (--own99 guard, default),
                   reported separately. --own99 negative trains and calibrates with it as a hard negative, to
                   show the effect of that choice.

Splits (sibling groups = (target, location, fault type, R_f))
  stratified  RepeatedStratifiedKFold 5x2 over simulations (the real_ml.py protocol, inner folds ungrouped)
  grouped     StratifiedGroupKFold 5x2, inner out-of-fold thresholds grouped too
  lolo        leave one in-zone location out; negatives in grouped quarters
  lorfo       leave one fault resistance out

Detectors: MLP, gradient boosting, random forest (raw causal window), engineered + LR, exactly as
real_ml.models / fit_balanced / score, hyperparameters untouched. Threshold at 5 % false trip on
out-of-fold training scores of the training negatives (point rate, as real_ml.py). Per-class false trips
are then checked on deduplicated units with one-sided 95 % binomial upper bounds (aggregate.py).

Checkpoints: logs/ckpt/zone_cv/<relay>/<config hash>/t<t>_<split>_f<fold>.pkl, each holding the git commit
and the config; a checkpoint whose commit or config differs from the current run is refused.

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
HELD = ("own99", "parallel", "reverse_bus", "reverse_lines", "other", "switching")
MODELS = ("MLP", "gradient boosting", "random forest", "engineered + LR")


def zone_task(R, own99="guard"):
    """Positions of the zone task and labels. own99='guard': own-line 99 % faults excluded;
    own99='negative': included as negatives."""
    m = R["pos"] | R["neg"] | (R["own99"] if own99 == "negative" else False)
    idx = np.where(m)[0]
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


def checkpoint_dir(name, cfg):
    return os.path.join(cm.ROOT, "logs", "ckpt", "zone_cv", name, cm.config_hash(cfg))


CODE = ("src/review/zone_cv.py", "src/review/common.py", "src/real_ml.py", "src/zone_detect.py", "src/zone_model.py",
        "src/evemt.py", "src/real_zone.py", "src/waveforms.py")


def load_checkpoint(path, commit, cfg):
    """Accept a checkpoint only if its config is identical and it was written by the current commit or by a
    commit whose experiment code (CODE) is byte-identical to the current one."""
    rec = pickle.load(open(path, "rb"))
    if rec.get("_config") != cfg or not cm.code_unchanged(rec.get("_commit"), commit, CODE):
        raise RuntimeError(f"checkpoint {path} was written by commit {rec.get('_commit')} / config "
                           f"{rec.get('_config')}; current is {commit} / {cfg}. Refusing to resume.")
    return rec


def run(name, times, split_kinds, own99="guard", far=FAR, chain=None):
    t0 = time.time()
    commit = cm.git_commit()
    if not cm.code_unchanged(commit, commit, CODE):
        raise RuntimeError("experiment code has uncommitted changes; commit before running so checkpoints are keyed")
    R = cm.load_relay(name, chain)
    R["g"] = type("G", (), dict(z1=R["lp"]["z1"], z0_ratio=R["lp"]["z0"] / R["lp"]["z1"]))
    idx, y, groups = zone_task(R, own99)
    held = tuple(h for h in HELD if R[h].any() and not (h == "own99" and own99 == "negative"))
    held_idx = {h: np.where(R[h])[0] for h in held}
    out = dict(relay=name, commit=commit, own99=own99, far=far, chain=chain or {}, n_pos=int(y.sum()),
               n_neg=int((1 - y).sum()), n_held={h: int(len(v)) for h, v in held_idx.items()}, runs={})
    for t in times:
        feats = None
        for kind in split_kinds:
            cfg = dict(script="zone_cv", relay=name, t=t, split=kind, own99=own99, far=far, chain=chain or {},
                       models=list(MODELS), held=list(held))
            ck = checkpoint_dir(name, cfg)
            os.makedirs(ck, exist_ok=True)
            for f, tr, te, meta in splits(kind, R, idx, y, groups):
                path = os.path.join(ck, f"t{t}_{kind}_f{f}.pkl")
                if os.path.exists(path):
                    load_checkpoint(path, commit, cfg)
                    continue
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
                rec = dict(_commit=commit, _config=cfg, test_idx=idx[te], meta=meta, models={})
                for n, m in real_ml.models(f).items():
                    X = fmap[n][:len(idx)]
                    real_ml.fit_balanced(m, X[tr], ytr, f)
                    s_oof = cm.oof_scores(n, X[tr], ytr, f, groups=g_in)
                    thr = cm.thr_at_far(s_oof[ytr == 0], far)
                    rec["models"][n] = dict(threshold=float(thr), test_score=real_ml.score(m, X[te]),
                                            held_score={h: real_ml.score(m, fmap[n][hs]) for h, hs in hsel.items()})
                pickle.dump(rec, open(path, "wb"))
                print(f"  [{name}] t={t} {kind} fold {f} done [{time.time()-t0:.0f}s]", flush=True)
            out["runs"][f"{t}|{kind}"] = dict(checkpoint_dir=os.path.relpath(ck, cm.ROOT), config=cfg,
                                              held_idx={h: v.tolist() for h, v in held_idx.items()})
            print(f"[{name}] t={t} {kind}: all folds checkpointed [{time.time()-t0:.0f}s]", flush=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("relay")
    ap.add_argument("--times", type=int, nargs="+", default=[20])
    ap.add_argument("--splits", nargs="+", default=["grouped", "stratified", "lorfo", "lolo"])
    ap.add_argument("--own99", choices=["guard", "negative"], default="guard")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = run(a.relay, a.times, a.splits, a.own99)
    path = a.out or os.path.join(cm.ROOT, "logs", f"zone_cv_{a.relay}_{a.own99}_{'-'.join(map(str, a.times))}.manifest.json")
    json.dump(res, open(path, "w"), indent=1)
    print("saved", path)
