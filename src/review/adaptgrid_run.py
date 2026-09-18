"""The decisive comparisons on EvEMTBench adapt_grid-TestGrid110kV (results/ADAPTGRID.md sections 3-4).

One relay, one front end per invocation; 20 ms decision time; the reviewed protocol unchanged:
out-of-fold thresholds, per-class held-out rates with deduplicated counts and binomial upper bounds,
grouped-bootstrap CIs, own-line 85-100 % as a guard band, and physically settable caps on every tuned
rung (T1 never beyond 0.9 X_line; T2's R_set grid stops at the Kasztenny eq. 19 cap).

Splits are by OPERATING POINT, never by simulation (results/ADAPTGRID_FACTS.md): 'grouped' =
5-fold over 20 loading bins; 'loqo' = leave one loading QUARTILE out, so calibration and test never
share a loading band.

OPERATING POINTS. Every scored detector is read at four points, all out of fold:
  far5   threshold at 5 % false trips on the training negatives (the review's research convention)
  cal0   threshold at ZERO false trips on the training negatives - the deployable protection-grade
         setting; its test false trips are whatever they turn out to be (k/N with the binomial UCB)
  roc0   threshold read off the pooled out-of-fold ROC at zero off-line false trips (0/N): the
         dependability the detector could have at protection-grade security, an upper bound since the
         threshold is chosen on the test scores
  roc1   the same at most one off-line false trip (1/N)
For T2 (a characteristic, no score) the same four points are taken over its setting grid. Q2's
distance output keeps its physical threshold (d_hat < 0.85) at far5 and cal0.

VARIANTS. Every operating point is reported unsupervised and with 32P/32Q directional supervision
(ladder.directional), side by side; on the inception-anchored window ('matched') and on the window
anchored at the causal starter (h10_trigger.trigger, 'starter'); and for the instrument-mismatch chain
(train on installation draw 1, test on draw 2; q1_instrument.draw_installation_fault). Plus the
cross-relay transfer with a carried threshold.

R_f. Dependability is stratified by the protection-practice bands <5 / 5-15 / 15-40 / >40 ohm
(common.RF_BINS) and by whether the in-zone fault lies inside the LARGEST SETTABLE zone-1
characteristic (quadrilateral at 0.9 X_line and the capped resistive reach; 'settable'). Rule and
learned detectors are compared on that subset and on its complement separately.

REFERENCES that are not single-ended zone 1: 67N/67Q (ladder), and two communication-assisted
decisions built from the remote-end cubicle of the same line in the cache (real_zone
remote_cubicle): 32P/32Q forward at BOTH ends (a permissive directional-comparison scheme, the
POTT equivalent without a reach element) and 67N/67Q forward at both ends. No channel delay is
modelled: both ends are read at 20 ms after inception.

The conventional ladder R0-R4 / T1 / T2 / 67N/67Q is ladder.run() as-is (corrected R_set).

    python src/review/adaptgrid_run.py adapt_A --frontend current
    python src/review/adaptgrid_run.py adapt_B --frontend relayfe
    -> results/adaptgrid/<relay>_<frontend>.json ; checkpoints logs/ckpt/adaptgrid/, keyed by commit + config;
       out-of-fold scores logs/scores/adaptgrid/ (not committed)
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
        "src/review/h10_trigger.py", "src/review/frontend.py", "src/real_ml.py", "src/zone_detect.py", "src/zone_model.py",
        "src/real_zone.py")
FAR, T = 0.05, 20
SPLITS = ("grouped", "loqo")
MODELS = ("T1", "T2", "engineered + LR", "gradient boosting", "CNN seq-traj", "GBM distance (Q2)")
FEAT_OF = {"engineered + LR": "eng", "gradient boosting": "raw", "CNN seq-traj": "seq", "GBM distance (Q2)": "snap", "T1": None, "T2": None}
OPS = ("far5", "cal0", "roc0", "roc1")
VARIANTS = ("matched", "matched + directional", "starter", "starter + directional")
OUT = os.path.join(cm.ROOT, "results", "adaptgrid")
SCORES = os.path.join(cm.ROOT, "logs", "scores", "adaptgrid")


# ------------------------------------------------------------------ data
def bundle(name, chain):
    R = cm.load_relay(name, chain)
    R["g"] = type("G", (), dict(z1=R["lp"]["z1"], z0_ratio=R["lp"]["z0"] / R["lp"]["z1"]))
    S = R["S"] = ld.settings(R, name)
    sel = np.arange(len(R["et"]))
    P1 = ld.pack(R, sel, T, "full", True)
    R["x0"] = ld.evaluate_block(R, *ld.pack(R, sel, T, "full", False), S, "R0")[1]            # T1's score is -x0
    R["x_cap"] = ld.X_CAP * S["x_line"]
    # the largest settable zone-1 characteristic: 0.9 X_line and the capped resistive reach (data property of each fault)
    R["settable"] = ld.evaluate_block(R, *P1, S, "R2", x_set=R["x_cap"], r_set=S["polarising_cap"]["r_cap_r2"])[0]
    R["settable_legacy"] = ld.evaluate_block(R, *P1, S, "R2", x_set=R["x_cap"], r_set=4 * S["r_set_g_legacy"])[0]
    return R


def settable_summary(R):
    pos, rfb = R["pos"], R["rf_bin"]
    return dict(n_pos=int(pos.sum()), inside_capped=int((pos & R["settable"]).sum()), inside_legacy=int((pos & R["settable_legacy"]).sum()),
                x_set_max=float(R["x_cap"]), r_set_max_capped=float(R["S"]["polarising_cap"]["r_cap_r2"]),
                r_set_max_legacy=float(4 * R["S"]["r_set_g_legacy"]),
                by_rf_bin={b: dict(n=int((pos & (rfb == b)).sum()), inside_capped=int((pos & R["settable"] & (rfb == b)).sum()),
                                   inside_legacy=int((pos & R["settable_legacy"] & (rfb == b)).sum())) for b in cm.RF_LABELS},
                rf_quantiles_pos={str(q): float(np.quantile(R["rf"][pos], q / 100)) for q in (0, 10, 25, 50, 75, 90, 100)},
                rf_quantiles_offline={str(q): float(np.quantile(R["rf"][R["neg"]], q / 100)) for q in (0, 10, 25, 50, 75, 90, 100)})


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
    x0 = np.full(len(sel), np.inf)
    for d in np.unique(delay[ok]):
        m = np.where(ok & (delay == d))[0]
        Fd = features(R, sel[m], ev=R["ev"] + int(d) + 2)
        for k in F:
            F[k][m] = Fd[k]
        R2 = dict(R, ev=R["ev"] + int(d) + 2)
        x0[m] = ld.evaluate_block(R2, *ld.pack(R2, sel[m], T, "full", False), R["S"], "R0")[1]
    return F, ok, delay, x0


def supervision(R, sel, ev=None):
    R2 = R if ev is None else dict(R, ev=ev)
    return ld.directional(*ld.pack(R2, sel, T, "full", True), R["z1L"])


def starter_supervision(R, sel, delay, ok):
    fwd = np.zeros(len(sel), bool)
    for d in np.unique(delay[ok]):
        m = np.where(ok & (delay == d))[0]
        fwd[m] = supervision(R, sel[m], ev=R["ev"] + int(d) + 2)
    return fwd


def comm_reference(name, chain):
    """Local 32P/32Q alone, and the two both-ends decisions from the remote cubicle of the same line."""
    R = bundle(name, chain)
    Rr = cm.load_relay(name, chain, cubicle=R["cfg"]["remote_cubicle"])
    n = len(R["et"]); sel = np.arange(n)
    P, Pr = ld.pack(R, sel, T, "full", True), ld.pack(Rr, sel, T, "full", True)
    fl, fr = ld.directional(*P, R["z1L"]), ld.directional(*Pr, Rr["z1L"])
    l67, r67 = np.logical_or(*ld.ground_overcurrent(R, *P)), np.logical_or(*ld.ground_overcurrent(Rr, *Pr))
    idx, y, _ = zone_task(R)
    ok = np.ones(n, bool)
    out = {}
    for lab, dec in (("32P/32Q local only (direction, no reach)", fl),
                     ("32P/32Q both ends (POTT-equivalent, no reach)", fl & fr),
                     ("67N/67Q both ends", l67 & r67)):
        out[lab] = rates_plus(dec, R, sel, idx, y, ok)
    out["_note"] = ("remote end read at the same 20 ms after inception; no channel delay, no zone-2 element; " +
                    f"remote cubicle {R['cfg']['remote_cubicle']}")
    return out


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


def t2_choose(grid, rows, y, far):
    """Largest training dependability with training false trips <= far (a rate); at far = 0 the count must be 0."""
    best = (-1.0, None)
    for key, dec in grid.items():
        ft = dec[rows][y == 0]
        if (ft.sum() == 0 if far == 0 else ft.mean() <= far):
            d = dec[rows][y == 1].mean()
            if d > best[0]:
                best = (d, key)
    return best[1] if best[1] is not None else min(grid, key=lambda k: grid[k][rows][y == 0].mean())


def t2_choose_pooled(grid, rows, y, max_false):
    """ROC read for a characteristic: the setting with the largest dependability on `rows` among those
    with at most `max_false` false trips on the negatives of `rows` (chosen on the test rows, an upper bound)."""
    best = (-1.0, None)
    for key, dec in grid.items():
        if dec[rows][y == 0].sum() <= max_false:
            d = dec[rows][y == 1].mean()
            if d > best[0]:
                best = (d, key)
    return best[1] if best[1] is not None else min(grid, key=lambda k: grid[k][rows][y == 0].sum())


def t2_starter(Rte, key, delay, ok):
    n = len(delay); dst = np.zeros(n, bool)
    for d in np.unique(delay[ok]):
        m = np.where(ok & (delay == d))[0]
        R2 = dict(Rte, ev=Rte["ev"] + int(d) + 2)
        dst[m] = ld.evaluate_block(R2, *ld.pack(R2, m, T, "full", True), Rte["S"], "R2", x_set=key[0], r_set=key[1])[0]
    return dst


def oof_negatives(fn, Xtr, ytr, gtr, seed):
    """Out-of-fold scores of the training negatives (grouped 5-fold), as q3.oof_threshold builds them."""
    from sklearn.model_selection import StratifiedGroupKFold
    s = np.zeros(len(ytr))
    for k, (a, b) in enumerate(StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(Xtr, ytr, gtr)):
        s[b] = fn(Xtr[a], ytr[a], [Xtr[b]], seed + 100 + k)[0]
    return s[ytr == 0]


def fit_score(model, Ftr, ytr, gtr, tests, seed):
    """Fit on the training rows, thresholds from the out-of-fold scores of the training negatives at
    5 % (far5) and at zero (cal0) false trips, score every test set. Returns (thr_far, thr0, [scores])."""
    if model == "CNN seq-traj":
        s_neg = oof_negatives(q3.cnn_scores, Ftr, ytr, gtr, seed)
        return cm.thr_at_far(s_neg, FAR), float(s_neg.max()), q3.cnn_scores(Ftr, ytr, tests, seed)
    if model == "GBM distance (Q2)":
        from sklearn.ensemble import HistGradientBoostingRegressor
        m = HistGradientBoostingRegressor(random_state=seed).fit(Ftr, np.clip(ytr, 0, 3))
        return -0.85, -0.85, [-m.predict(X) for X in tests]      # trip when d_hat < 0.85: physical, nothing calibrated
    m = real_ml.fit_balanced(real_ml.models(seed)[model], Ftr, ytr, seed)
    s_neg = cm.oof_scores(model, Ftr, ytr, seed, groups=gtr)[ytr == 0]
    return cm.thr_at_far(s_neg, FAR), float(s_neg.max()), [real_ml.score(m, X) for X in tests]


# ------------------------------------------------------------------ evaluation
def rates_plus(dec, R, sel, idx, y, tested):
    """ladder.rates on the tested rows, plus CIs, the settable-subset split and the extra classes."""
    mask = tested.copy()
    d = np.where(mask, dec, False)
    r = ld.rates(d, R, sel)
    zi = np.searchsorted(sel, idx)
    gg = R["groups"][idx]
    dz, yz = dec[zi], y
    dep = lambda s: float(dz[s][yz[s] == 1].mean())
    ftb = lambda s: float(dz[s][yz[s] == 0].mean())
    r["dependability_ci"] = cm.grouped_bootstrap(dep, gg, 500)
    r["false_trip_beyond_ci"] = cm.grouped_bootstrap(ftb, gg, 500)
    r["neg_bench"] = cm.dedup_rate(d, R["dedup"][sel], R["neg_bench"][sel])
    r["incipient"] = cm.dedup_rate(d, R["dedup"][sel], R["incipient"][sel])
    pos = R["pos"][sel]
    kn = lambda m: dict(k=int(d[m].sum()), n=int(m.sum()), rate=(float(d[m].mean()) if m.any() else None))
    r["settable"] = dict(inside=kn(pos & R["settable"][sel]), outside=kn(pos & ~R["settable"][sel]),
                         inside_legacy=kn(pos & R["settable_legacy"][sel]), outside_legacy=kn(pos & ~R["settable_legacy"][sel]))
    return r


def pooled_threshold(z_neg, k_false, floor=None):
    """Threshold read off the pooled out-of-fold negatives: strictly above the (k_false + 1)-th largest score."""
    s = np.sort(z_neg)
    tau = float(s[-1 - k_false]) if len(s) > k_false else -np.inf
    return tau if floor is None else max(tau, floor)


def evaluate(name, fe, train_chain, test_chain, tag, models, split_kinds, commit, smoke=False):
    """All models on one (train chain, test chain) pair; returns {model: {split: {...}}} with the far5 rates
    under the variant keys (as before) and the protection-grade points under 'protection'[op][variant]."""
    Rtr = bundle(name, train_chain)
    Rte = Rtr if test_chain is train_chain else bundle(name, test_chain)
    n = len(Rtr["et"]); sel = np.arange(n)
    idx, y, groups = zone_task(Rtr)                          # pos | neg, own99 as guard band
    zi = idx                                                 # sel is every row, so positions == indices
    Ftr = features(Rtr, sel)
    Fte = Ftr if Rte is Rtr else features(Rte, sel)
    Fst, ok_st, delay, x0_st = starter_features(Rte, sel)
    fwd = supervision(Rte, sel)
    fwd_st = starter_supervision(Rte, sel, delay, ok_st)
    d_target = q2.target(Rtr)                                # continuous line units; NaN off the studied lines
    grid_tr = t2_grid(Rtr, sel) if "T2" in models else None
    grid_te = grid_tr if Rte is Rtr else (t2_grid(Rte, sel) if "T2" in models else None)
    hrows = np.setdiff1d(sel, zi)
    all_rows = np.ones(n, bool)
    out = {}
    for model in models:
        out[model] = {}
        for kind in split_kinds:
            cfg = dict(script="adaptgrid_run", relay=name, frontend=fe, chains=tag, model=model, split=kind, t=T, far=FAR, ops=list(OPS))
            ck = os.path.join(cm.ROOT, "logs", "ckpt", "adaptgrid", f"{name}_{fe}", cm.config_hash(cfg) + ".pkl")
            os.makedirs(os.path.dirname(ck), exist_ok=True)
            if os.path.exists(ck) and not smoke:
                rec = pickle.load(open(ck, "rb"))
                if rec["_config"] != cfg or not cm.code_unchanged(rec["_commit"], commit, CODE):
                    raise SystemExit(f"checkpoint mismatch at {ck}; refusing to resume")
                out[model][kind] = rec["result"]; continue
            t0 = time.time()
            res = dict(protection={op: {} for op in OPS if op != "far5"})
            fk = FEAT_OF[model]
            floor = -Rte["x_cap"] if model == "T1" else None
            if model == "T2":
                # a characteristic has no score: the four operating points are four setting choices
                dec = {op: {b: np.zeros(n, bool) for b in ("matched", "starter")} for op in OPS}
                chosen = {op: [] for op in OPS}
                tested = np.zeros(n, bool)
                for f, tr, te, meta in splits(kind, Rtr, idx, y, groups):
                    if smoke and f >= 1:
                        break
                    rtr, rte = zi[tr], zi[te]
                    for op, far in (("far5", FAR), ("cal0", 0.0)):
                        key = t2_choose(grid_tr, rtr, y[tr], far); chosen[op].append(key)
                        dec[op]["matched"][rte] = grid_te[key][rte]
                    tested[rte] = True
                for op, kf in (("roc0", 0), ("roc1", 1)):
                    key = t2_choose_pooled(grid_te, zi[tested[zi]], y[tested[zi]], kf); chosen[op].append(key)
                    dec[op]["matched"][zi] = grid_te[key][zi]
                for op in OPS:
                    # held-out classes: the per-fold chosen settings, majority over folds
                    keys = chosen[op]
                    dec[op]["matched"][hrows] = np.mean([grid_te[k][hrows] for k in keys], axis=0) >= 0.5
                    # starter-anchored: re-evaluate every chosen setting on starter phasors
                    dec[op]["starter"] = np.mean([t2_starter(Rte, k, delay, ok_st) for k in dict.fromkeys(keys)], axis=0) >= 0.5
                    for base in ("matched", "starter"):
                        d = dec[op][base]
                        fw = fwd if base == "matched" else fwd_st
                        tgt = res if op == "far5" else res["protection"][op]
                        tgt[base] = rates_plus(d, Rte, sel, idx, y, tested | np.isin(sel, hrows))
                        tgt[base + " + directional"] = rates_plus(d & fw, Rte, sel, idx, y, tested | np.isin(sel, hrows))
                    tgt = res if op == "far5" else res["protection"][op]
                    tgt["chosen_t2"] = [(float(k[0]), float(k[1])) for k in keys]
                res.update(fold_auc=[], auc=float("nan"), auc_sd=float("nan"), n_folds=len(chosen["far5"]),
                           starter_no_decision=int((~ok_st).sum()), chosen_t2=res["chosen_t2"])
            else:
                Z = {b: np.full(n, np.nan) for b in ("matched", "starter")}
                H = {b: [] for b in Z}
                thr_f = {"far5": [], "cal0": []}
                tested = np.zeros(n, bool); aucs = []
                for f, tr, te, meta in splits(kind, Rtr, idx, y, groups):
                    if smoke and f >= 1:
                        break
                    rtr, rte = zi[tr], zi[te]
                    if model == "T1":
                        s_neg = -Rtr["x0"][rtr][y[tr] == 0]
                        thr_far, thr0 = max(cm.thr_at_far(s_neg, FAR), floor), max(float(s_neg.max()), floor)
                        s_te, s_h, s_te_st, s_h_st = -Rte["x0"][rte], -Rte["x0"][hrows], -x0_st[rte], -x0_st[hrows]
                    elif model == "GBM distance (Q2)":
                        # regression target exists only on the studied lines; train on those, test on everything
                        keep = np.isfinite(d_target[rtr])
                        thr_far, thr0, (s_te, s_h, s_te_st, s_h_st) = fit_score(model, Ftr[fk][rtr][keep], d_target[rtr][keep], groups[tr][keep],
                                                                                [Fte[fk][rte], Fte[fk][hrows], Fst[fk][rte], Fst[fk][hrows]], f)
                    else:
                        thr_far, thr0, (s_te, s_h, s_te_st, s_h_st) = fit_score(model, Ftr[fk][rtr], y[tr], groups[tr],
                                                                                [Fte[fk][rte], Fte[fk][hrows], Fst[fk][rte], Fst[fk][hrows]], f)
                    s_te_st = np.where(ok_st[rte], np.nan_to_num(s_te_st, nan=-np.inf), -np.inf)
                    s_h_st = np.where(ok_st[hrows], np.nan_to_num(s_h_st, nan=-np.inf), -np.inf)
                    Z["matched"][rte] = s_te; H["matched"].append(np.asarray(s_h, float))
                    Z["starter"][rte] = s_te_st; H["starter"].append(np.asarray(s_h_st, float))
                    thr_f["far5"].append(float(thr_far)); thr_f["cal0"].append(float(thr0))
                    tested[rte] = True
                    aucs.append(float(roc_auc_score(y[te], s_te)))
                nf = len(thr_f["far5"])
                fold_of = np.full(n, -1)
                for f, (_, tr, te, _) in enumerate(splits(kind, Rtr, idx, y, groups)):
                    if f < nf:
                        fold_of[zi[te]] = f
                for base in ("matched", "starter"):
                    fw = fwd if base == "matched" else fwd_st
                    Hb = np.stack(H[base])                                             # (folds, held)
                    for sup in (False, True):
                        z = Z[base].copy()
                        hb = Hb.copy()
                        if sup:
                            z[~fw] = -np.inf; hb[:, ~fw[hrows]] = -np.inf
                        vkey = base + (" + directional" if sup else "")
                        for op in OPS:
                            d = np.zeros(n, bool)
                            if op in ("far5", "cal0"):
                                th = np.array(thr_f[op])
                                m = tested
                                d[m] = z[m] > th[fold_of[m]]
                                d[hrows] = np.mean(hb > th[:, None], axis=0) >= 0.5
                                info = dict(threshold_per_fold=thr_f[op])
                            else:
                                tau = pooled_threshold(z[zi][(y == 0) & tested[zi]], 0 if op == "roc0" else 1, floor)
                                d[zi] = z[zi] > tau
                                d[hrows] = np.mean(hb > tau, axis=0) >= 0.5
                                info = dict(threshold=tau)
                            tgt = res if op == "far5" else res["protection"][op]
                            tgt[vkey] = rates_plus(d, Rte, sel, idx, y, tested | np.isin(sel, hrows))
                            tgt[vkey].update(info)
                res.update(fold_auc=aucs, auc=float(np.mean(aucs)) if aucs else float("nan"), auc_sd=float(np.std(aucs)) if aucs else float("nan"),
                           n_folds=nf, starter_no_decision=int((~ok_st).sum()), chosen_t2=None)
                if not smoke:
                    os.makedirs(os.path.join(SCORES, f"{name}_{fe}"), exist_ok=True)
                    np.savez_compressed(os.path.join(SCORES, f"{name}_{fe}", cm.config_hash(cfg) + ".npz"),
                                        zone_matched=Z["matched"], zone_starter=Z["starter"], held_matched=np.stack(H["matched"]),
                                        held_starter=np.stack(H["starter"]), hrows=hrows, idx=idx, y=y, fwd=fwd, fwd_st=fwd_st,
                                        fold_of=fold_of, thr_far5=thr_f["far5"], thr_cal0=thr_f["cal0"], commit=commit, config=json.dumps(cfg))
            res["runtime_s"] = float(time.time() - t0)
            if not smoke:
                pickle.dump(dict(_commit=commit, _config=cfg, result=res), open(ck, "wb"))
            out[model][kind] = res
            m, s = res["matched"], res["matched + directional"]
            p0, p0s = res["protection"]["roc0"]["matched"], res["protection"]["roc0"]["matched + directional"]
            c0, c0s = res["protection"]["cal0"]["matched"], res["protection"]["cal0"]["matched + directional"]
            print(f"  [{name} {fe} {tag}] {model:18s} {kind:7s} AUC {res['auc']:.3f} | far5 dep {m['pos']['rate']*100:5.1f} beyond {m['neg']['dedup']['k']}/{m['neg']['dedup']['n']} "
                  f"sw {m['switching']['rate']*100:4.1f} (+dir dep {s['pos']['rate']*100:5.1f} beyond {s['neg']['rate']*100:4.1f} sw {s['switching']['rate']*100:4.1f}) "
                  f"| roc0 dep {p0['pos']['rate']*100:5.1f} (+dir {p0s['pos']['rate']*100:5.1f}) sw {p0['switching']['rate']*100:4.1f}/{p0s['switching']['rate']*100:4.1f} "
                  f"| cal0 dep {c0['pos']['rate']*100:5.1f} beyond {c0['neg']['dedup']['k']}/{c0['neg']['dedup']['n']} (+dir {c0s['pos']['rate']*100:5.1f} beyond {c0s['neg']['dedup']['k']}) "
                  f"| starter far5 dep {res['starter']['pos']['rate']*100:5.1f}  [{res['runtime_s']:.0f}s]", flush=True)
    return out


def cross_relay(src, dst, fe, models, commit, smoke=False):
    """Train on every zone case of one relay (matched chain), carry the thresholds (far5, cal0) to the other;
    roc0/roc1 read on the destination's zone rows."""
    Rs, Rd = bundle(src, None), bundle(dst, None)
    ns, nd = len(Rs["et"]), len(Rd["et"])
    idx_s, y_s, g_s = zone_task(Rs); idx_d, y_d, g_d = zone_task(Rd)
    Fs, Fd = features(Rs, idx_s), features(Rd, np.arange(nd))
    fwd_d = supervision(Rd, np.arange(nd))
    tested = np.ones(nd, bool)
    out = {}
    for model in models:
        if model in ("T1", "T2"):
            continue
        fk = FEAT_OF[model]
        if model == "GBM distance (Q2)":
            tgt = q2.target(Rs)[idx_s]; keep = np.isfinite(tgt)
            thr, thr0, (s_d,) = fit_score(model, Fs[fk][keep], tgt[keep], g_s[keep], [Fd[fk]], 0)
        else:
            thr, thr0, (s_d,) = fit_score(model, Fs[fk], y_s, g_s, [Fd[fk]], 0)
        r = dict(auc=float(roc_auc_score(y_d, s_d[idx_d])), threshold=float(thr), threshold_cal0=float(thr0), protection={})
        for op, tau in (("far5", thr), ("cal0", thr0),
                        ("roc0", pooled_threshold(s_d[idx_d][y_d == 0], 0)), ("roc1", pooled_threshold(s_d[idx_d][y_d == 0], 1))):
            dec = s_d > tau
            rr = dict(transferred=rates_plus(dec, Rd, np.arange(nd), idx_d, y_d, tested),
                      transferred_directional=rates_plus(dec & fwd_d, Rd, np.arange(nd), idx_d, y_d, tested), threshold=float(tau))
            if op == "far5":
                r.update(rr)
            else:
                r["protection"][op] = rr
        out[model] = r
        print(f"  [{src}->{dst} {fe}] {model:18s} AUC {r['auc']:.3f}  far5 dep {r['transferred']['pos']['rate']*100:5.1f} "
              f"beyond {r['transferred']['neg']['rate']*100:5.1f}  | roc0 dep {r['protection']['roc0']['transferred']['pos']['rate']*100:5.1f} "
              f"(+dir {r['protection']['roc0']['transferred_directional']['pos']['rate']*100:5.1f})", flush=True)
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
    res = dict(relay=name, frontend=fe, commit=commit, t_ms=T, far=FAR, ops=list(OPS), splits=a.splits, models=a.models,
               protocol="results/ADAPTGRID.md section 3", rf_bins=list(cm.RF_LABELS), chains={})
    if not a.no_ladder:
        print(f"=== ladder {name} {fe} ===", flush=True)
        res["ladder"] = ld.run(name)
    print(f"=== settable characteristic and communication-assisted references ===", flush=True)
    res["settable"] = settable_summary(bundle(name, None))
    res["reference_comm"] = comm_reference(name, None)
    for lab, r in res["reference_comm"].items():
        if not lab.startswith("_"):
            print(f"  {lab:48s} dep {r['pos']['rate']*100:5.1f}  off-line {r['neg']['dedup']['k']}/{r['neg']['dedup']['n']}  "
                  f"switching {r['switching']['rate']*100:4.1f}  incipient {r['incipient']['k']}/{r['incipient']['n']}", flush=True)
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
