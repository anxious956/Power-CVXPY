"""The decisive comparisons on EvEMTBench adapt_grid-TestGrid110kV (results/ADAPTGRID.md sections 3-4).

One relay, one front end per invocation; 20 ms decision time; the reviewed protocol unchanged:
out-of-fold thresholds at 5 % training false trips, per-class held-out rates with deduplicated
counts and binomial upper bounds, grouped-bootstrap CIs, own-line 85-100 % as a guard band, and
physically settable caps on every tuned rung (T2's R_set grid stops at the Kasztenny eq. 19 cap).

Splits are by OPERATING POINT, never by simulation (results/ADAPTGRID_FACTS.md): 'grouped' =
5-fold over 20 loading bins; 'loqo' = leave one loading QUARTILE out, so calibration and test never
share a loading band.

Columns produced for every learned model and for the tuned quadrilateral T2:
  matched        train and test on the same measurement chain (the usual number)
  starter        the same fold models, test windows anchored at the causal superimposed-current
                 starter (h10_trigger.trigger) instead of the true inception
  mismatch       train on fault-condition installation draw 1, test on draw 2 (VT 3-6 %, CT 5-10 %;
                 q1_instrument.draw_installation_fault) - the calibration/service instrument test
each unsupervised and with 32P/32Q directional supervision (ladder.directional), plus the physical
distance output of Q2 (GBM regressor on the relay snapshot, trip at d_hat < 0.85, nothing tuned)
and the cross-relay transfer with a carried threshold.

The conventional ladder R0-R4 / T1 / T2 / 67N/67Q is ladder.run() as-is (corrected R_set).

    python src/review/adaptgrid_run.py adapt_A --frontend current
    python src/review/adaptgrid_run.py adapt_B --frontend relayfe
    -> results/adaptgrid/<relay>_<frontend>.json ; checkpoints logs/ckpt/adaptgrid/, keyed by commit + config
"""
import os, sys, json, time, pickle, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from review import common as cm
from review import ladder as ld
from review import frontend
from review.zone_cv import zone_task, splits
from review import q3_inputs as q3
from review import q2_distance as q2
from review import q1_instrument as q1
from review import h10_trigger as h10
import real_ml
from zone_detect import zone_features

CODE = ("src/review/adaptgrid_run.py", "src/review/ladder.py", "src/review/common.py", "src/review/setting_study.py",
        "src/review/zone_cv.py", "src/review/q3_inputs.py", "src/review/q2_distance.py", "src/review/q1_instrument.py",
        "src/review/h10_trigger.py", "src/review/frontend.py", "src/real_ml.py", "src/zone_detect.py", "src/zone_model.py")
FAR, T = 0.05, 20
SPLITS = ("grouped", "loqo")
MODELS = ("engineered + LR", "gradient boosting", "CNN seq-traj", "GBM distance (Q2)", "T2")
FEAT_OF = {"engineered + LR": "eng", "gradient boosting": "raw", "CNN seq-traj": "seq", "GBM distance (Q2)": "snap", "T2": None}
OUT = os.path.join(cm.ROOT, "results", "adaptgrid")


# ------------------------------------------------------------------ data
def bundle(name, chain):
    R = cm.load_relay(name, chain)
    R["g"] = type("G", (), dict(z1=R["lp"]["z1"], z0_ratio=R["lp"]["z0"] / R["lp"]["z1"]))
    R["S"] = ld.settings(R, name)
    return R


def features(R, sel, ev=None):
    """All model inputs for rows `sel`; `ev` overrides the window anchor (starter-anchored test)."""
    R2 = R if ev is None else dict(R, ev=ev)
    rot = q3.rotation_index(R2, sel)
    Rc, cidx = q3.rotated(R2, sel, rot)
    Rc["ev"] = R2["ev"]
    return dict(eng=zone_features(real_ml.phasor_view(R2, sel, T), R["g"]),
                raw=real_ml.raw_window(R2, sel, T),
                seq=q3.seq_traj(Rc, cidx),
                snap=q2.snapshot(R2, R["S"], sel, T))


def starter_features(R, sel):
    """Features with every test window anchored at the causal starter; rows on which the starter never
    fires get no decision (score -inf). The starter fires a median 0.16 ms after inception on the
    benchmark (REVIEW.md section 6 H10)."""
    delay = h10.trigger(R, sel)
    ok = (delay < 10**6) & (R["ev"] + delay + 2 + int(T * 6.4) + 128 <= R["full"].shape[-1])
    # rows without a starter keep the inception-anchored features so every estimator sees finite input;
    # their scores are forced to -inf by the caller (`ok` mask), so they never trip
    F = {k: v.copy() for k, v in features(R, sel).items()}
    for d in np.unique(delay[ok]):
        m = np.where(ok & (delay == d))[0]
        Fd = features(R, sel[m], ev=R["ev"] + int(d) + 2)
        for k in F:
            F[k][m] = Fd[k]
    return F, ok, delay


def supervision(R, sel, ev=None):
    R2 = R if ev is None else dict(R, ev=ev)
    return ld.directional(*ld.pack(R2, sel, T, "full", True), R["z1L"])


def starter_supervision(R, sel, delay, ok):
    fwd = np.zeros(len(sel), bool)
    for d in np.unique(delay[ok]):
        m = np.where(ok & (delay == d))[0]
        fwd[m] = supervision(R, sel[m], ev=R["ev"] + int(d) + 2)
    return fwd


# ------------------------------------------------------------------ models
def t2_grid(R, sel):
    """The tuned quadrilateral's candidate settings: X_set <= 0.9 X_line, R_set on the absolute legacy grid
    truncated at the polarising-error cap (what a setting engineer could actually apply)."""
    S = R["S"]
    xgrid = np.linspace(0.3 * S["x_set"], ld.X_CAP * S["x_line"], 21)
    rgrid = S["r_set_g_legacy"] * np.array([0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0])
    rgrid = rgrid[rgrid <= S["polarising_cap"]["r_cap_r2"]]
    if rgrid.size == 0:
        rgrid = np.array([S["polarising_cap"]["r_cap_r2"]])
    P = ld.pack(R, sel, T, "full", True)
    return {(float(a), float(b)): ld.evaluate_block(R, *P, S, "R2", x_set=a, r_set=b)[0] for a in xgrid for b in rgrid}


def t2_choose(grid, rows, y):
    best = (-1.0, None)
    for key, dec in grid.items():
        if dec[rows][y == 0].mean() <= FAR:
            d = dec[rows][y == 1].mean()
            if d > best[0]:
                best = (d, key)
    return best[1] if best[1] is not None else min(grid, key=lambda k: grid[k][rows][y == 0].mean())


def fit_score(model, Ftr, ytr, gtr, tests, seed):
    """Fit on the training rows, OOF threshold on training negatives, score every test set.
    Returns (threshold, [scores per test set], oof auc placeholder)."""
    if model == "CNN seq-traj":
        thr = q3.oof_threshold(q3.cnn_scores, Ftr, ytr, gtr, seed, FAR)
        return thr, q3.cnn_scores(Ftr, ytr, tests, seed)
    if model == "GBM distance (Q2)":
        from sklearn.ensemble import HistGradientBoostingRegressor
        m = HistGradientBoostingRegressor(random_state=seed).fit(Ftr, np.clip(ytr, 0, 3))
        return -0.85, [-m.predict(X) for X in tests]          # trip when d_hat < 0.85, i.e. -d_hat > -0.85
    m = real_ml.fit_balanced(real_ml.models(seed)[model], Ftr, ytr, seed)
    thr = cm.thr_at_far(cm.oof_scores(model, Ftr, ytr, seed, groups=gtr)[ytr == 0], FAR)
    return thr, [real_ml.score(m, X) for X in tests]


# ------------------------------------------------------------------ evaluation
def rates_plus(dec, R, sel, idx, y, tested):
    """ladder.rates on the tested rows, plus CIs, all keyed as the review's tables expect."""
    mask = tested.copy()
    r = ld.rates(np.where(mask, dec, False), R, sel)
    zi = np.searchsorted(sel, idx)
    gg = R["groups"][idx]
    dz, yz = dec[zi], y
    dep = lambda s: float(dz[s][yz[s] == 1].mean())
    ftb = lambda s: float(dz[s][yz[s] == 0].mean())
    r["dependability_ci"] = cm.grouped_bootstrap(dep, gg, 500)
    r["false_trip_beyond_ci"] = cm.grouped_bootstrap(ftb, gg, 500)
    r["neg_bench"] = cm.dedup_rate(np.where(mask, dec, False), R["dedup"][sel], R["neg_bench"][sel])
    r["incipient"] = cm.dedup_rate(np.where(mask, dec, False), R["dedup"][sel], R["incipient"][sel])
    return r


def evaluate(name, fe, train_chain, test_chain, tag, models, split_kinds, commit, smoke=False):
    """All models on one (train chain, test chain) pair; returns {model: {split: {variant: rates}}}."""
    Rtr = bundle(name, train_chain)
    Rte = Rtr if test_chain is train_chain else bundle(name, test_chain)
    n = len(Rtr["et"]); sel = np.arange(n)
    idx, y, groups = zone_task(Rtr)                          # pos | neg, own99 as guard band
    zi = idx                                                 # sel is every row, so positions == indices
    Ftr = features(Rtr, sel)
    Fte = Ftr if Rte is Rtr else features(Rte, sel)
    Fst, ok_st, delay = starter_features(Rte, sel)
    fwd = supervision(Rte, sel)
    fwd_st = starter_supervision(Rte, sel, delay, ok_st)
    d_target = q2.target(Rtr)                                # continuous line units; NaN off the studied lines
    grid_tr = t2_grid(Rtr, sel) if "T2" in models else None
    grid_te = grid_tr if Rte is Rtr else (t2_grid(Rte, sel) if "T2" in models else None)
    out = {}
    for model in models:
        out[model] = {}
        for kind in split_kinds:
            cfg = dict(script="adaptgrid_run", relay=name, frontend=fe, chains=tag, model=model, split=kind, t=T, far=FAR)
            ck = os.path.join(cm.ROOT, "logs", "ckpt", "adaptgrid", f"{name}_{fe}", cm.config_hash(cfg) + ".pkl")
            os.makedirs(os.path.dirname(ck), exist_ok=True)
            if os.path.exists(ck) and not smoke:
                rec = pickle.load(open(ck, "rb"))
                if rec["_config"] != cfg or not cm.code_unchanged(rec["_commit"], commit, CODE):
                    raise SystemExit(f"checkpoint mismatch at {ck}; refusing to resume")
                out[model][kind] = rec["result"]; continue
            t0 = time.time()
            dec = {v: np.zeros(n, bool) for v in ("matched", "starter")}
            held = {v: [] for v in dec}
            tested = np.zeros(n, bool); aucs = []; chosen = []
            fk = FEAT_OF[model]
            hrows = np.setdiff1d(sel, zi)
            for f, tr, te, meta in splits(kind, Rtr, idx, y, groups):
                if smoke and f >= 1:
                    break
                rtr, rte = zi[tr], zi[te]
                if model == "T2":
                    key = t2_choose(grid_tr, rtr, y[tr]); chosen.append(key)
                    dec["matched"][rte] = grid_te[key][rte]; held["matched"].append(grid_te[key][hrows])
                    # starter variant of T2: re-evaluate the chosen setting on starter-anchored phasors
                    dst = np.zeros(n, bool)
                    for d in np.unique(delay[ok_st]):
                        m = np.where(ok_st & (delay == d))[0]
                        P = ld.pack(dict(Rte, ev=Rte["ev"] + int(d) + 2), m, T, "full", True)
                        dst[m] = ld.evaluate_block(Rte, *P, Rte["S"], "R2", x_set=key[0], r_set=key[1])[0]
                    dec["starter"][rte] = dst[rte]; held["starter"].append(dst[hrows])
                    tested[rte] = True                       # a fixed characteristic has no score, hence no AUC
                    continue
                ytr_ = y[tr]
                if model == "GBM distance (Q2)":
                    # regression target exists only on the studied lines; train on those, test on everything
                    keep = np.isfinite(d_target[rtr])
                    thr, (s_te, s_h, s_te_st, s_h_st) = fit_score(model, Ftr[fk][rtr][keep], d_target[rtr][keep], groups[tr][keep],
                                                                   [Fte[fk][rte], Fte[fk][hrows], Fst[fk][rte], Fst[fk][hrows]], f)
                else:
                    thr, (s_te, s_h, s_te_st, s_h_st) = fit_score(model, Ftr[fk][rtr], ytr_, groups[tr],
                                                                   [Fte[fk][rte], Fte[fk][hrows], Fst[fk][rte], Fst[fk][hrows]], f)
                dec["matched"][rte] = s_te > thr; held["matched"].append(s_h > thr)
                s_te_st = np.where(ok_st[rte], np.nan_to_num(s_te_st, nan=-np.inf), -np.inf)
                s_h_st = np.where(ok_st[hrows], np.nan_to_num(s_h_st, nan=-np.inf), -np.inf)
                dec["starter"][rte] = s_te_st > thr; held["starter"].append(s_h_st > thr)
                tested[rte] = True
                aucs.append(float(roc_auc_score(y[te], s_te)) if model != "GBM distance (Q2)" else float(roc_auc_score(y[te], s_te)))
            res = dict(fold_auc=aucs, auc=float(np.mean(aucs)) if aucs else float("nan"), auc_sd=float(np.std(aucs)) if aucs else float("nan"),
                       n_folds=len(aucs), starter_no_decision=int((~ok_st).sum()), chosen_t2=chosen or None)
            for v in dec:
                d = dec[v].copy(); d[hrows] = np.mean(held[v], axis=0) >= 0.5
                res[v] = rates_plus(d, Rte, sel, idx, y, tested | np.isin(sel, hrows))
                fw = fwd if v == "matched" else fwd_st
                res[v + " + directional"] = rates_plus(d & fw, Rte, sel, idx, y, tested | np.isin(sel, hrows))
            res["runtime_s"] = float(time.time() - t0)
            if not smoke:
                pickle.dump(dict(_commit=commit, _config=cfg, result=res), open(ck, "wb"))
            out[model][kind] = res
            m, s = res["matched"], res["matched + directional"]
            print(f"  [{name} {fe} {tag}] {model:20s} {kind:8s} AUC {res['auc']:.3f}  dep {m['pos']['rate']*100:5.1f} "
                  f"[{m['dependability_ci'][0]*100:.0f},{m['dependability_ci'][1]*100:.0f}]  beyond {m['neg']['dedup']['k']}/{m['neg']['dedup']['n']} "
                  f"(<={m['neg']['dedup']['ucb95']*100:.1f})  rev-bus {m['reverse_bus']['rate']*100:5.1f}  switching {m['switching']['rate']*100:5.1f}  "
                  f"| +dir dep {s['pos']['rate']*100:5.1f} beyond {s['neg']['rate']*100:5.1f} rev {s['reverse_bus']['rate']*100:5.1f}  "
                  f"| starter dep {res['starter']['pos']['rate']*100:5.1f} beyond {res['starter']['neg']['rate']*100:5.1f}  [{res['runtime_s']:.0f}s]", flush=True)
    return out


def cross_relay(src, dst, fe, models, commit, smoke=False):
    """Train on every zone case of one relay (matched chain), carry the OOF threshold to the other."""
    Rs, Rd = bundle(src, None), bundle(dst, None)
    ns, nd = len(Rs["et"]), len(Rd["et"])
    idx_s, y_s, g_s = zone_task(Rs); idx_d, y_d, g_d = zone_task(Rd)
    Fs, Fd = features(Rs, idx_s), features(Rd, np.arange(nd))
    fwd_d = supervision(Rd, np.arange(nd))
    out = {}
    for model in models:
        if model == "T2":
            continue
        fk = FEAT_OF[model]
        if model == "GBM distance (Q2)":
            tgt = q2.target(Rs)[idx_s]; keep = np.isfinite(tgt)
            thr, (s_d,) = fit_score(model, Fs[fk][keep], tgt[keep], g_s[keep], [Fd[fk]], 0)
        else:
            thr, (s_d,) = fit_score(model, Fs[fk], y_s, g_s, [Fd[fk]], 0)
        dec = s_d > thr
        tested = np.ones(nd, bool)
        r = dict(auc=float(roc_auc_score(y_d, s_d[idx_d])), threshold=float(thr),
                 transferred=rates_plus(dec, Rd, np.arange(nd), idx_d, y_d, tested),
                 transferred_directional=rates_plus(dec & fwd_d, Rd, np.arange(nd), idx_d, y_d, tested))
        out[model] = r
        print(f"  [{src}->{dst} {fe}] {model:20s} AUC {r['auc']:.3f}  dep {r['transferred']['pos']['rate']*100:5.1f}  "
              f"beyond {r['transferred']['neg']['rate']*100:5.1f}  rev-bus {r['transferred']['reverse_bus']['rate']*100:5.1f}", flush=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("relay", choices=["adapt_A", "adapt_B"])
    ap.add_argument("--frontend", choices=["current", "relayfe"], default="current")
    ap.add_argument("--models", nargs="+", default=list(MODELS))
    ap.add_argument("--splits", nargs="+", default=list(SPLITS))
    ap.add_argument("--no-ladder", action="store_true")
    ap.add_argument("--no-cross", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="1 fold, no checkpoints, scratch output")
    a = ap.parse_args()
    t0 = time.time()
    commit = cm.git_commit()
    if not a.smoke and not cm.code_unchanged(commit, commit, CODE):
        raise SystemExit("commit the experiment code first")
    if a.frontend == "relayfe":
        frontend.enable()                                   # AA 400 Hz + CT-based full scale, for every load below
    os.makedirs(OUT, exist_ok=True)
    name, fe = a.relay, a.frontend
    res = dict(relay=name, frontend=fe, commit=commit, t_ms=T, far=FAR, splits=a.splits, models=a.models,
               protocol="results/ADAPTGRID.md section 3", chains={})
    if not a.no_ladder:
        print(f"=== ladder {name} {fe} ===", flush=True)
        res["ladder"] = ld.run(name)
    print(f"=== matched chain ===", flush=True)
    res["chains"]["matched"] = evaluate(name, fe, None, None, "matched", a.models, a.splits, commit, a.smoke)
    d1, d2 = q1.draw_installation_fault(name, 0), q1.draw_installation_fault(name, 1)
    print(f"=== instrument mismatch: train {d1} / test {d2} ===", flush=True)
    res["chains"]["mismatch"] = evaluate(name, fe, d1, d2, "mismatch", a.models, a.splits, commit, a.smoke)
    res["mismatch_draws"] = dict(train=d1, test=d2)
    if not a.no_cross:
        other = "adapt_B" if name == "adapt_A" else "adapt_A"
        print(f"=== cross relay {other} -> {name} ===", flush=True)
        res["cross"] = {f"{other}->{name}": cross_relay(other, name, fe, a.models, commit, a.smoke)}
    res["runtime_s"] = float(time.time() - t0)
    path = os.path.join(OUT, f"{name}_{fe}{'_smoke' if a.smoke else ''}.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print(f"saved {path}  [{res['runtime_s']:.0f}s]")
