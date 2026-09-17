"""Q1: is 0.1 % white noise + 16-bit a realistic error model, and which conclusions survive a realistic one?

One-at-a-time sweep from real_ml's default chain, plus one combined realistic point:
  white noise 0.03 / 0.1 (default) / 0.3 / 1 % of nominal
  per-installation ratio and phase error, 3 draws per relay: VT/CVT class 3P (+-3 %, +-2 deg), CT class 5P
      (+-1 %, +-1 deg) at rated current (IEC 61869-2/-3/-5 limits as commonly tabulated; not re-verified
      against the standard text); drawn once per relay, identical for training and test folds
  bias mismatch (Q2b): training folds see installation draw 1, test folds draw 2 (calibration data from one
      installation state, field data from another)
  CVT transient, high-capacitance model (common.cvt_filter 'highC'), which meets IEC 61869-5 class T1 in
      src/review/cvt_class_check.py; the low-C model fails T1 (11.5 % residual at 20 ms against <= 10 %) and
      is excluded (class limits quoted from memory, to be checked against the standard)
  CT saturation, 1000/1 A, 5P20-like, remanence 0.8 (common.ct_saturation)
  relay front end: review.frontend (causal 3rd-order Butterworth 400 Hz, ADC full scale from CT rating)
  realistic combined: installation draw 1 + CVT highC + CT saturation (remanence 0.5) + relay front end + 0.1 % noise
  (trimmed for compute: white 0.03 % and a third installation draw were dropped before any point was run)

At each point, relays A and B, decision time 20 ms, own-99 % as guard band, grouped 5-fold:
  ladder R0, R1, R2 (fixed settings from the graph study, chain-independent), T2 tuned quadrilateral,
  gradient boosting (raw window) and engineered + LR with grouped out-of-fold thresholds (real_ml models),
  shortcut control (gradient boosting on the pre-fault window 45..5 ms before inception).

Each (relay, point) is checkpointed under logs/ckpt/q1/ keyed by commit and config.

    python src/review/q1_instrument.py
"""
import sys, os, json, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from review import common as cm
from review import ladder as ld
from review.zone_cv import zone_task, splits
import real_ml
from zone_detect import zone_features

CODE = ("src/review/q1_instrument.py", "src/review/ladder.py", "src/review/common.py", "src/review/setting_study.py",
        "src/review/zone_cv.py", "src/real_ml.py", "src/zone_detect.py", "src/zone_model.py", "src/evemt.py")


def draw_installation(name, k):
    rng = np.random.default_rng(1000 + 17 * k + sum(map(ord, name)))
    return dict(gain_v=float(rng.uniform(-0.03, 0.03)), phase_v_deg=float(rng.uniform(-2, 2)),
                gain_i=float(rng.uniform(-0.01, 0.01)), phase_i_deg=float(rng.uniform(-1, 1)))


def points(name):
    P = {"white 0.1 % (default)": {}, "white 0.3 %": dict(noise_rel=3e-3), "white 1 %": dict(noise_rel=1e-2)}
    for k in range(2):
        P[f"installation error draw {k + 1}"] = draw_installation(name, k)
    P["installation mismatch (train draw 1, test draw 2)"] = "mismatch"
    P["CVT high-C"] = dict(cvt="highC")
    P["CT saturation rem 0.8"] = dict(ct=dict(remanence=0.8))
    P["relay front end (AA 400 Hz + CT full scale)"] = "relayfe"
    P["realistic combined (draw 1 + CVT + CT sat 0.5 + relay front end)"] = "combined"
    return P


def evaluate_point(name, chain_train, chain_test, S):
    Rtr = cm.load_relay(name, chain_train)
    Rte = Rtr if chain_test is chain_train else cm.load_relay(name, chain_test)
    for R in (Rtr, Rte):
        R["g"] = type("G", (), dict(z1=R["lp"]["z1"], z0_ratio=R["lp"]["z0"] / R["lp"]["z1"]))
    sets = ("pos", "neg", "own99", "reverse_bus", "switching")
    sel = np.where(np.any([Rte[h] for h in sets], axis=0))[0]
    idx, y, groups = zone_task(Rtr)
    zpos = np.searchsorted(sel, idx)
    out = {}
    # fixed rungs on the test chain
    for rung, mim in (("R0", False), ("R1", True), ("R2", True)):
        trip, _ = ld.evaluate_block(Rte, *ld.pack(Rte, sel, 20, "full", mim), S, rung)
        r = ld.rates(trip, Rte, sel)
        out[rung] = dict(dependability=r["pos"]["rate"], beyond=r["neg"]["rate"], beyond_dedup=r["neg"]["dedup"],
                         own99=r["own99"]["rate"], reverse_bus=r["reverse_bus"]["rate"], dep40=r["dep_by_rf"]["40"])
    # tuned quadrilateral and learned models: fit on train chain, test on test chain
    P1tr, P1te = ld.pack(Rtr, sel, 20, "full", True), ld.pack(Rte, sel, 20, "full", True)
    xgrid = np.linspace(0.3 * S["x_set"], ld.X_CAP * S["x_line"], 21)
    rgrid = S["r_set_g"] * np.array([0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0])
    gtr = {(a, b): ld.evaluate_block(Rtr, *P1tr, S, "R2", x_set=a, r_set=b)[0] for a in xgrid for b in rgrid}
    gte = {(a, b): ld.evaluate_block(Rte, *P1te, S, "R2", x_set=a, r_set=b)[0] for a in xgrid for b in rgrid}
    Fr_tr, Fr_te = real_ml.raw_window(Rtr, sel, 20), real_ml.raw_window(Rte, sel, 20)
    Fe_tr = zone_features(real_ml.phasor_view(Rtr, sel, 20), Rtr["g"])
    Fe_te = Fe_tr if Rte is Rtr else zone_features(real_ml.phasor_view(Rte, sel, 20), Rte["g"])
    dec = {k: np.zeros(len(sel), bool) for k in ("T2", "gradient boosting", "engineered + LR")}
    tested = np.zeros(len(sel), bool)
    aucs = {k: [] for k in ("gradient boosting", "engineered + LR")}
    nz = np.array([i for i in range(len(sel)) if i not in set(zpos)])      # held-out rows (own99, reverse, switching)
    held_dec = {k: [] for k in dec}
    for f, tr, te, meta in splits("grouped", Rtr, idx, y, groups):
        if f >= 5:
            break                                                          # one repeat
        rtr, rte = zpos[tr], zpos[te]
        best = max(((gtr[k][rtr][y[tr] == 1].mean(), k) for k in gtr if gtr[k][rtr][y[tr] == 0].mean() <= 0.05), default=(0, None))
        dec["T2"][rte] = gte[best[1]][rte]
        held_dec["T2"].append(gte[best[1]][nz])
        for n, Ftr, Fte in (("gradient boosting", Fr_tr, Fr_te), ("engineered + LR", Fe_tr, Fe_te)):
            m = real_ml.fit_balanced(real_ml.models(f)[n], Ftr[rtr], y[tr], f)
            thr = cm.thr_at_far(cm.oof_scores(n, Ftr[rtr], y[tr], f, groups=groups[tr])[y[tr] == 0], 0.05)
            s = real_ml.score(m, Fte[rte])
            dec[n][rte] = s > thr
            aucs[n].append(roc_auc_score(y[te], s))
            held_dec[n].append(real_ml.score(m, Fte[nz]) > thr)
        tested[rte] = True
    for k in dec:
        d = dec[k].copy()
        hd = np.mean(held_dec[k], axis=0) >= 0.5                           # majority over the 5 fold models
        d[nz] = hd
        mask = tested.copy(); mask[nz] = True
        r = ld.rates(np.where(mask, d, False), Rte, sel)
        out[k] = dict(dependability=r["pos"]["rate"], beyond=r["neg"]["rate"], beyond_dedup=r["neg"]["dedup"], own99=r["own99"]["rate"],
                      reverse_bus=r["reverse_bus"]["rate"], dep40=r["dep_by_rf"]["40"],
                      auc=float(np.mean(aucs[k])) if k in aucs else None)
    # shortcut control on the test chain
    X = real_ml.raw_window(Rte, idx, 0, prefault=True)
    a = []
    for f, tr, te, meta in splits("grouped", Rte, idx, y, groups):
        if f >= 5:
            break
        m = real_ml.fit_balanced(real_ml.models(f)["gradient boosting"], X[tr], y[tr], f)
        a.append(roc_auc_score(y[te], real_ml.score(m, X[te])))
    out["shortcut control AUC (GB, pre-fault only)"] = float(np.mean(a))
    return out


if __name__ == "__main__":
    t0 = time.time()
    commit = cm.git_commit()
    if not cm.code_unchanged(commit, commit, CODE):
        raise SystemExit("commit the experiment code first")
    res = {}
    for name in ("testgrid_B", "testgrid_A"):
        S = ld.settings(cm.load_relay(name), name)
        res[name] = {}
        for label, chain in points(name).items():
            cfg = dict(script="q1", relay=name, point=label, chain=chain)
            path = os.path.join(cm.ROOT, "logs", "ckpt", "q1", f"{name}_{cm.config_hash(cfg)}.pkl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.path.exists(path):
                rec = pickle.load(open(path, "rb"))
                if rec["_config"] != cfg or not cm.code_unchanged(rec["_commit"], commit, CODE):
                    raise SystemExit(f"checkpoint mismatch at {path}; refusing to resume")
                r = rec["result"]
            else:
                if chain == "mismatch":
                    r = evaluate_point(name, draw_installation(name, 0), draw_installation(name, 1), S)
                elif chain in ("relayfe", "combined"):
                    from review import frontend
                    ch = dict(frontend.RELAY_CHAIN)
                    if chain == "combined":
                        ch.update(draw_installation(name, 0), cvt="highC", ct=dict(remanence=0.5))
                    orig = cm.measurement_chain
                    cm.measurement_chain = frontend._wrapped
                    try:
                        r = evaluate_point(name, ch, ch, S)
                    finally:
                        cm.measurement_chain = orig
                else:
                    ch = chain or None
                    r = evaluate_point(name, ch, ch, S)
                pickle.dump(dict(_commit=commit, _config=cfg, result=r), open(path, "wb"))
            res[name][label] = dict(chain=chain, **r)
            print(f"[{name}] {label:48s} " + "  ".join(
                f"{k}: dep {v['dependability']*100:4.1f} beyond {v['beyond']*100:4.1f} own99 {v['own99']*100:4.1f} rev {v['reverse_bus']*100:4.1f}"
                for k, v in r.items() if isinstance(v, dict)) + f"  shortcut {r['shortcut control AUC (GB, pre-fault only)']:.3f}  [{time.time()-t0:.0f}s]", flush=True)
            json.dump(res, open(os.path.join(cm.ROOT, "results", "review", "q1_instrument.json"), "w"), indent=1, default=str)
    print("saved results/review/q1_instrument.json")
