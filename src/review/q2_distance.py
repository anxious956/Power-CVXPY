"""Q2: is a per-relay threshold a fair deployment assumption? Test the alternative that removes the
problem: make the learned output physical (fault distance in units of the protected line's reactance)
and trip at a fixed 0.85, so the threshold transfers across relays the way the setting does.

Target d: own line loc/100; remote bus 1.0; line beyond the remote bus 1 + (loc/100) X_that_line / X_own_line.
Inputs normalised per relay so they are comparable across relays (real_ml.raw_window already scales V/I by
the reach impedance; the snapshot below uses loop impedances in units of the protected line):
  snapshot  from the rung-R2 front end at 20 ms (mimic, phase selection): selected-loop R/X_line, X/X_line,
            I2-polarised X/X_line, sequence magnitudes relative to pre-fault V1 and I1, sin/cos of sequence
            angles relative to V1 memory, directional decision.
Models: HistGradientBoostingRegressor on the snapshot, MLPRegressor on the raw window (ChannelScaler), and for
comparison the classifiers (gradient boosting on raw, engineered + LR) with an out-of-fold threshold.
Training cases: in-zone, beyond / remote bus, and own line 99 % (a regression target, not a class).
Evaluation: within relay (grouped 5-fold) and across relays (A->B, B->A, A->DoubleLine, B->DoubleLine),
on dependability, beyond false trips (dedup UCB), own-99 % guard band, relay-bus reverse faults, switching.

    python src/review/q2_distance.py
"""
import sys, os, json, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import ladder as ld
from review.zone_cv import splits
import real_ml
from zone_detect import zone_features

CODE = ("src/review/q2_distance.py", "src/review/ladder.py", "src/review/common.py", "src/review/setting_study.py",
        "src/review/zone_cv.py", "src/real_ml.py", "src/zone_detect.py", "src/zone_model.py", "src/evemt.py")
SETS = ("pos", "neg", "own99", "parallel", "reverse_bus", "switching")


def target(R):
    xl = R["z1L"].imag
    g = R["graph"]
    xline = {k: d[f"{k}_param_dict"]["length"] * d[f"{k}_param_dict"]["xline"] for u, v, k, d in g.edges(keys=True, data=True)
             if f"{k}_param_dict" in d and "xline" in d[f"{k}_param_dict"]}
    d = np.full(len(R["tgt"]), np.nan)
    own = R["tgt"] == R["cfg"]["line"]
    d[own] = R["loc"][own] / 100.0
    d[R["tgt"] == R["cfg"]["remote_bus"]] = 1.0
    for ln in R["cfg"]["beyond"]:
        m = R["tgt"] == ln
        d[m] = 1.0 + R["loc"][m] / 100.0 * xline[ln] / xl
    return d


def snapshot(R, S, sel, t=20):
    vpre, vpost, ipre, ipost, vmem = ld.pack(R, sel, t, "full", True)
    Lp = cm.loops(R, vpost, ipost, vpre, ipre)
    mask = cm.phase_selection(ipre, ipost)
    Z = Lp["V"] / (Lp["I"] + 1e-12)
    xl = R["z1L"].imag
    X = np.where(mask, Z.imag, np.inf); j = X.argmin(1); z = Z[np.arange(len(Z)), j]
    _, x2 = ld.evaluate_block(R, vpre, vpost, ipre, ipost, vmem, S, "R3", x_set=1e9, r_set=1e6)
    x2 = np.clip(np.where(np.isfinite(x2), x2, 50 * xl) / xl, -50, 50)
    fwd = ld.directional(vpre, vpost, ipre, ipost, vmem, R["z1L"])
    ref = vmem[:, 1] / np.abs(vmem[:, 1])
    v1n, i1n = np.abs(vmem[:, 1]), np.abs(ipre[:, 1]) + 1e-9
    cols = [np.clip(z.real / xl, -50, 50), np.clip(z.imag / xl, -50, 50), x2, fwd.astype(float), mask.sum(1)]
    for s in range(3):
        for q, nrm in ((vpost, v1n), (ipost, i1n), (vpost - vpre, v1n), (ipost - ipre, i1n)):
            ph = q[:, s] / ref
            cols += [np.abs(q[:, s]) / nrm, np.sin(np.angle(ph)), np.cos(np.angle(ph))]
    return np.column_stack(cols)


def fit_predict_reg(kind, Xtr, ytr, Xte, seed):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import make_pipeline
    if kind == "GBM regressor (snapshot)":
        m = HistGradientBoostingRegressor(random_state=seed)
    else:
        m = make_pipeline(real_ml.ChannelScaler(), MLPRegressor(hidden_layer_sizes=(100,), max_iter=800, early_stopping=True, random_state=seed))
    m.fit(Xtr, np.clip(ytr, 0, 3))
    return m.predict(Xte)


def summary(R, sel, trip):
    r = ld.rates(trip, R, sel)
    return dict(dependability=r["pos"]["rate"], dep40=r["dep_by_rf"]["40"], beyond=r["neg"]["rate"], beyond_dedup=r["neg"]["dedup"],
                own99_guard=r["own99"]["rate"], reverse_bus=r["reverse_bus"]["rate"],
                parallel=r["parallel"]["rate"] if "parallel" in r else None, switching=r["switching"]["rate"])


def prepare(name):
    R = cm.load_relay(name)
    R["g"] = type("G", (), dict(z1=R["lp"]["z1"], z0_ratio=R["lp"]["z0"] / R["lp"]["z1"]))
    S = ld.settings(R, name)
    sel = np.where(np.any([R[h] for h in SETS], axis=0))[0]
    d = target(R)[sel]
    F = dict(snap=snapshot(R, S, sel), raw=real_ml.raw_window(R, sel, 20),
             eng=zone_features(real_ml.phasor_view(R, sel, 20), R["g"]))
    train = R["pos"][sel] | R["neg"][sel] | R["own99"][sel]
    return R, sel, d, F, train


REGS = (("GBM regressor (snapshot)", "snap"), ("MLP regressor (raw)", "raw"))
CLFS = (("gradient boosting classifier (raw)", "gradient boosting", "raw"), ("engineered + LR classifier", "engineered + LR", "eng"))


if __name__ == "__main__":
    t0 = time.time()
    commit = cm.git_commit()
    if not cm.code_unchanged(commit, commit, CODE):
        raise SystemExit("commit the experiment code first")
    ck = os.path.join(cm.ROOT, "logs", "ckpt", "q2")
    os.makedirs(ck, exist_ok=True)
    D = {n: prepare(n) for n in ("testgrid_A", "testgrid_B", "doubleline")}
    res = dict(within={}, cross={})
    for name, (R, sel, d, F, train) in D.items():
        cfg = dict(script="q2", mode="within", relay=name)
        path = os.path.join(ck, cm.config_hash(cfg) + ".pkl")
        if os.path.exists(path):
            rec = pickle.load(open(path, "rb"))
            assert rec["_config"] == cfg and cm.code_unchanged(rec["_commit"], commit, CODE), "checkpoint mismatch"
            res["within"][name] = rec["result"]; continue
        zi = np.where(train)[0]
        y = R["pos"][sel][zi].astype(int)
        groups = R["groups"][sel][zi]
        held = np.where(~train)[0]
        out = {}
        dec = {k: np.zeros(len(sel), bool) for k, _ in REGS}
        dec.update({k: np.zeros(len(sel), bool) for k, _, _ in CLFS})
        votes = {k: np.zeros(len(sel)) for k in dec}
        mae = {k: [] for k, _ in REGS}
        for f, tr, te, meta in splits("grouped", R, sel[zi], y, groups):
            if f >= 5:
                break
            a, b = zi[tr], zi[te]
            for k, fk in REGS:
                p = fit_predict_reg(k, F[fk][a], d[a], np.concatenate([F[fk][b], F[fk][held]]), f)
                dec[k][b] = p[:len(b)] < 0.85
                votes[k][held] += p[len(b):] < 0.85
                mae[k].append(float(np.mean(np.abs(p[:len(b)] - d[b]))))
            for k, mk, fk in CLFS:
                trn = ~R["own99"][sel][a]                                   # guard band: own-99 % is not a negative
                m = real_ml.fit_balanced(real_ml.models(f)[mk], F[fk][a][trn], y[tr][trn], f)
                thr = cm.thr_at_far(cm.oof_scores(mk, F[fk][a][trn], y[tr][trn], f, groups=groups[tr][trn])[y[tr][trn] == 0], 0.05)
                s = real_ml.score(m, np.concatenate([F[fk][b], F[fk][held]]))
                dec[k][b] = s[:len(b)] > thr
                votes[k][held] += s[len(b):] > thr
        for k in dec:
            tr_ = dec[k].copy(); tr_[held] = votes[k][held] >= 3
            out[k] = summary(R, sel, tr_)
            if k in mae:
                out[k]["distance_MAE_line_units"] = float(np.mean(mae[k]))
        pickle.dump(dict(_commit=commit, _config=cfg, result=out), open(path, "wb"))
        res["within"][name] = out
        print(f"[within {name}] " + "  ".join(f"{k}: dep {v['dependability']*100:4.1f} beyond {v['beyond']*100:4.1f} own99 {v['own99_guard']*100:4.1f} rev {v['reverse_bus']*100:4.1f}" for k, v in out.items()) + f" [{time.time()-t0:.0f}s]", flush=True)
    for a_, b_ in (("testgrid_A", "testgrid_B"), ("testgrid_B", "testgrid_A"), ("testgrid_A", "doubleline"), ("testgrid_B", "doubleline")):
        cfg = dict(script="q2", mode="cross", train=a_, test=b_)
        path = os.path.join(ck, cm.config_hash(cfg) + ".pkl")
        if os.path.exists(path):
            rec = pickle.load(open(path, "rb"))
            assert rec["_config"] == cfg and cm.code_unchanged(rec["_commit"], commit, CODE), "checkpoint mismatch"
            res["cross"][f"{a_}->{b_}"] = rec["result"]; continue
        Ra, sa, da, Fa, tra = D[a_]; Rb, sb, db, Fb, trb = D[b_]
        ia = np.where(tra)[0]; ya = Ra["pos"][sa][ia].astype(int); ga = Ra["groups"][sa][ia]
        out = {}
        for k, fk in REGS:
            p = fit_predict_reg(k, Fa[fk][ia], da[ia], Fb[fk], 0)
            out[k] = summary(Rb, sb, p < 0.85)
            zb = np.isfinite(db)
            out[k]["distance_MAE_line_units"] = float(np.mean(np.abs(p[zb & trb] - db[zb & trb])))
        for k, mk, fk in CLFS:
            trn = ~Ra["own99"][sa][ia]
            m = real_ml.fit_balanced(real_ml.models(0)[mk], Fa[fk][ia][trn], ya[trn], 0)
            thr = cm.thr_at_far(cm.oof_scores(mk, Fa[fk][ia][trn], ya[trn], 0, groups=ga[trn])[ya[trn] == 0], 0.05)
            out[k] = summary(Rb, sb, real_ml.score(m, Fb[fk]) > thr)
        # the fixed rung-R2 setting on the test relay, for reference
        Sb = ld.settings(Rb, b_)
        out["R2 setting (test relay)"] = summary(Rb, sb, ld.evaluate_block(Rb, *ld.pack(Rb, sb, 20, "full", True), Sb, "R2")[0])
        pickle.dump(dict(_commit=commit, _config=cfg, result=out), open(path, "wb"))
        res["cross"][f"{a_}->{b_}"] = out
        print(f"[cross {a_}->{b_}] " + "  ".join(f"{k}: dep {v['dependability']*100:4.1f} beyond {v['beyond']*100:4.1f} own99 {v['own99_guard']*100:4.1f} rev {v['reverse_bus']*100:4.1f}" for k, v in out.items()) + f" [{time.time()-t0:.0f}s]", flush=True)
    json.dump(res, open(os.path.join(cm.ROOT, "results", "review", "q2_distance.json"), "w"), indent=1, default=str)
    print("saved results/review/q2_distance.json")
