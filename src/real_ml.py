"""
A fair machine-learning comparison on real EMT data, set up the way the literature does it.

What changed from real_zone.py, and why:

1. Causal windows. The window ends at the decision time t after fault inception and starts
   40 ms before inception. Pre-fault samples are legitimately in a relay's buffer (incremental
   quantities are built from them); samples after the decision time are not. real_zone.py
   used 80 ms after inception, which no relay deciding in one cycle has. Decision time is
   swept over 10, 20, 30, 40, 50 ms, as in Oelhaf et al. 2026.

2. Same information for every detector. The zone-1 rule computes its phasors from the last
   full cycle before the decision time, so it needs t >= 20 ms and is reported n/a at 10 ms.

3. Physical normalisation instead of per-sample, per-channel standardisation. The old CNN
   scaled every voltage and current channel by its own statistics, which destroys the V/I
   ratio distance protection is built on. Here voltages are divided by nominal peak phase
   voltage and currents are multiplied by (zone-1 reach impedance / nominal peak voltage), so
   V/I is measured in units of the relay's own reach: a fault at the reach boundary sits near
   1 for every relay. On top of that, a StandardScaler fitted on the training fold only.

4. Models chosen from the literature, not by preference. Oelhaf et al. (same FAU group, same
   kind of data): an MLP is best at every window length and linear models fail. Gradient
   boosting is strong at 30 ms and above but collapses at 10 ms. Random forest is included as
   the tree ensemble. Engineered relay features with logistic regression are kept as the
   domain-knowledge model.

5. Two stages. Stage 1 is a fault detector trained on faults AND switching events AND
   pre-fault windows, so it has seen the things it must not trip on. Stage 2 is the zone
   decision on faults. A trip needs both.

6. Generalisation measured two ways: episode-grouped cross-validation within a relay, and
   train-on-one-relay, test-on-another, which no within-relay split can fake.

    python src/real_ml.py
"""
import sys, os, json, time
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evemt import load_cache, line_params
from zone_detect import score_reactance, zone_features
from real_zone import CONFIGS, REACH
from waveforms import CYCLE, EVENT

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "results")
FS = 6400
PRE = 256                       # 40 ms of pre-fault history
DECISIONS_MS = [10, 20, 30, 40, 50]
V_NOM_PEAK = 110e3 * np.sqrt(2 / 3)


def relay_data(name):
    cfg = CONFIGS[name]
    import glob
    cache = sorted(glob.glob(os.path.join(ROOT, "data", cfg["cache_glob"])))[0]
    C = load_cache(cache)
    k = C["cubicles"].index(cfg["relay"])
    full = np.asarray(C["x"][:, k])                         # (n, 6, 3201), primary V and A
    lp = line_params(C["graph"], cfg["line"])
    z_reach = abs(REACH * lp["length_km"] * lp["z1"])
    L = C["labels"]
    et = L["events/event_type"].astype(str)
    tgt = L["events/event_target"].astype(str)
    loc = L["events/event_flt_target_line_location"]
    shc = et.str.contains("shc").to_numpy()
    fault_any = et.str.startswith("flt").to_numpy()
    pos = shc & (tgt == cfg["line"]).to_numpy() & loc.isin([1, 20, 50, 80]).to_numpy()
    neg = shc & ((tgt.isin(cfg["beyond"]) & loc.isin([1, 20])) | (tgt == cfg["remote_bus"])).to_numpy()
    switching = et.str.startswith("switch").to_numpy()
    return dict(name=name, full=full, ev=C["event_index"], lp=lp, z_reach=z_reach,
                g=SimpleNamespace(z1=lp["z1"], z0_ratio=lp["z0"] / lp["z1"]),
                pos=pos, neg=neg, switching=switching, fault_any=fault_any)


def raw_window(R, idx, t_ms, prefault=False):
    """Causal window [inception - 40 ms, decision time], physically normalised, flattened.
    prefault=True shifts the whole window to end 5 ms before inception (a no-fault example)."""
    ev = R["ev"]
    n_post = int(round(t_ms * FS / 1000))
    end = ev - int(0.005 * FS) if prefault else ev + n_post
    start = end - PRE - n_post
    w = R["full"][idx, :, start:end].astype(np.float64)
    w[:, :3] /= V_NOM_PEAK
    w[:, 3:] *= R["z_reach"] / V_NOM_PEAK
    return w.reshape(len(idx), -1)


def phasor_view(R, idx, t_ms):
    """Rebuild a 1024-sample array whose phasor positions match what zone_detect expects:
    pre-fault cycle at [256, 384) taken from [-40, -20] ms, post cycle at [640, 768) taken
    from the last full cycle before the decision time. Lets the rule and the engineered
    features see exactly the causal window and nothing after it."""
    ev = R["ev"]
    n_post = int(round(t_ms * FS / 1000))
    out = np.zeros((len(idx), 6, 1024))
    out[:, :, EVENT - 2 * CYCLE:EVENT - CYCLE] = R["full"][idx, :, ev - 2 * CYCLE:ev - CYCLE]
    out[:, :, EVENT + CYCLE:EVENT + 2 * CYCLE] = R["full"][idx, :, ev + n_post - CYCLE:ev + n_post]
    return out


def models(seed):
    from sklearn.neural_network import MLPClassifier
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return {
        "MLP": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(100,), max_iter=800,
                                                             early_stopping=True, random_state=seed)),
        "gradient boosting": HistGradientBoostingClassifier(random_state=seed),
        "random forest": RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=seed),
        "engineered + LR": make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, random_state=seed)),
    }


def score(model, X):
    return model.predict_proba(X)[:, 1]


def auc(s, y):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def dep_at_far(s_tr, y_tr, s_te, y_te, far):
    thr = np.quantile(s_tr[y_tr == 0], 1 - far)
    return float((s_te[y_te == 1] > thr).mean()), float((s_te[y_te == 0] > thr).mean()), thr


# ------------------------------------------------------------------------------ stage 2
def zone_features_block(R, idx, t_ms, name):
    if name == "engineered + LR":
        return zone_features(phasor_view(R, idx, t_ms), R["g"])
    return raw_window(R, idx, t_ms)


def within_relay_zone(R, reps=2, folds=5):
    from sklearn.model_selection import RepeatedStratifiedKFold
    idx = np.where(R["pos"] | R["neg"])[0]
    y = R["pos"][idx].astype(int)
    out = {}
    for t in DECISIONS_MS:
        res = {}
        if t >= 20:
            react = score_reactance(phasor_view(R, idx, t), R["g"])
            rule_trip = react < REACH * R["lp"]["length_km"] * R["lp"]["z1"].imag
            res["zone-1 rule"] = dict(auc=auc(-react, y), auc_sd=0.0,
                                      dependability=float(rule_trip[y == 1].mean()),
                                      false_trip=float(rule_trip[y == 0].mean()))
        feats = {n: zone_features_block(R, idx, t, n) for n in ("MLP", "engineered + LR")}
        feats["gradient boosting"] = feats["random forest"] = feats["MLP"]
        acc = {n: [] for n in feats}
        rskf = RepeatedStratifiedKFold(n_splits=folds, n_repeats=reps, random_state=0)
        for f, (tr, te) in enumerate(rskf.split(idx, y)):
            for n, m in models(f).items():
                m.fit(feats[n][tr], y[tr])
                s_tr, s_te = score(m, feats[n][tr]), score(m, feats[n][te])
                d, fa, _ = dep_at_far(s_tr, y[tr], s_te, y[te], 0.05)
                acc[n].append((auc(s_te, y[te]), d, fa))
        for n, v in acc.items():
            v = np.array(v)
            res[n] = dict(auc=float(v[:, 0].mean()), auc_sd=float(v[:, 0].std()),
                          dependability=float(v[:, 1].mean()), false_trip=float(v[:, 2].mean()))
        out[t] = res
        print(f"  [{R['name']}] t = {t} ms: " + "  ".join(f"{n} {r['auc']:.3f}" for n, r in res.items()), flush=True)
    return out


def cross_relay_zone(Rtr, Rte):
    """Train on every in/out-of-zone case of one relay, test on another relay it never saw."""
    itr = np.where(Rtr["pos"] | Rtr["neg"])[0]; ytr = Rtr["pos"][itr].astype(int)
    ite = np.where(Rte["pos"] | Rte["neg"])[0]; yte = Rte["pos"][ite].astype(int)
    out = {}
    for t in DECISIONS_MS:
        res = {}
        if t >= 20:
            react = score_reactance(phasor_view(Rte, ite, t), Rte["g"])
            trip = react < REACH * Rte["lp"]["length_km"] * Rte["lp"]["z1"].imag
            res["zone-1 rule"] = dict(auc=auc(-react, yte), dependability=float(trip[yte == 1].mean()),
                                      false_trip=float(trip[yte == 0].mean()))
        for n, m in models(0).items():
            Xtr, Xte = zone_features_block(Rtr, itr, t, n), zone_features_block(Rte, ite, t, n)
            m.fit(Xtr, ytr)
            s_tr, s_te = score(m, Xtr), score(m, Xte)
            d, fa, _ = dep_at_far(s_tr, ytr, s_te, yte, 0.05)
            res[n] = dict(auc=auc(s_te, yte), dependability=d, false_trip=fa)
        out[t] = res
        print(f"  [{Rtr['name']} -> {Rte['name']}] t = {t} ms: " + "  ".join(f"{n} {r['auc']:.3f}" for n, r in res.items()), flush=True)
    return out


# ------------------------------------------------------------------------------ stage 1 + combined
def two_stage_security(R, t=20, folds=5, far=0.01):
    """Episode-grouped folds over faults, switching events and pre-fault windows.
    Stage 1: fault vs no-fault (switching events at the same decision time, plus pre-fault
    windows). Stage 2: zone decision. Reports what share of held-out switching events and
    out-of-zone faults end up tripped, against in-zone dependability."""
    from sklearn.model_selection import StratifiedKFold
    faults = np.where(R["fault_any"])[0]
    sw = np.where(R["switching"])[0]
    zone_idx = np.where(R["pos"] | R["neg"])[0]
    episodes = np.concatenate([faults, sw])
    ep_label = np.concatenate([np.ones(len(faults), int), np.zeros(len(sw), int)])
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=0)
    trips = dict(switching=[], in_zone=[], out_of_zone=[])
    s1_auc = []
    for f, (tr_e, te_e) in enumerate(skf.split(episodes, ep_label)):
        tr_ep, te_ep = episodes[tr_e], episodes[te_e]
        # stage 1 training set: post-inception windows of training episodes + their pre-fault windows
        X1 = np.vstack([raw_window(R, tr_ep, t), raw_window(R, tr_ep, t, prefault=True)])
        y1 = np.concatenate([R["fault_any"][tr_ep].astype(int), np.zeros(len(tr_ep), int)])
        m1 = models(f)["MLP"].fit(X1, y1)
        X1te = np.vstack([raw_window(R, te_ep, t), raw_window(R, te_ep, t, prefault=True)])
        y1te = np.concatenate([R["fault_any"][te_ep].astype(int), np.zeros(len(te_ep), int)])
        s1_auc.append(auc(score(m1, X1te), y1te))
        thr1 = np.quantile(score(m1, X1)[y1 == 0], 1 - far)
        # stage 2 on training episodes that are in the zone task
        tr_z = np.intersect1d(tr_ep, zone_idx)
        m2 = models(f)["MLP"].fit(raw_window(R, tr_z, t), R["pos"][tr_z].astype(int))
        s2_tr = score(m2, raw_window(R, tr_z, t))
        thr2 = np.quantile(s2_tr[R["pos"][tr_z] == 0], 1 - 0.05)
        # combined decision on test episodes
        st1 = score(m1, raw_window(R, te_ep, t)) > thr1
        st2 = score(m2, raw_window(R, te_ep, t)) > thr2
        trip = st1 & st2
        for key, mask in (("switching", R["switching"][te_ep]), ("in_zone", R["pos"][te_ep]),
                          ("out_of_zone", R["neg"][te_ep])):
            if mask.any():
                trips[key].append(float(trip[mask].mean()))
    return dict(decision_ms=t, stage1_auc=float(np.mean(s1_auc)), stage1_auc_sd=float(np.std(s1_auc)),
                trip_rate={k: (float(np.mean(v)) if v else None) for k, v in trips.items()})


def main():
    t0 = time.time()
    R = {n: relay_data(n) for n in ("testgrid_A", "testgrid_B", "doubleline")}
    for n, r in R.items():
        print(f"{n}: {r['full'].shape}, reach impedance {r['z_reach']:.2f} ohm, in zone {r['pos'].sum()}, "
              f"out of zone {r['neg'].sum()}, switching {r['switching'].sum()}")
    result = dict(within={}, cross={}, two_stage={})
    print("\nWithin-relay zone decision, 5-fold x 2, causal windows:")
    for n in ("testgrid_A", "testgrid_B"):
        result["within"][n] = within_relay_zone(R[n])
    print("\nCross-relay zone decision, trained on one relay, tested on another:")
    for a, b in (("testgrid_A", "testgrid_B"), ("testgrid_B", "testgrid_A"), ("testgrid_A", "doubleline")):
        result["cross"][f"{a}->{b}"] = cross_relay_zone(R[a], R[b])
    print("\nTwo-stage security at 20 ms (stage 1 trained with switching events):")
    for n in ("testgrid_A", "testgrid_B"):
        result["two_stage"][n] = two_stage_security(R[n])
        ts = result["two_stage"][n]
        print(f"  {n}: stage-1 AUC {ts['stage1_auc']:.3f}; trip rate  in zone "
              f"{ts['trip_rate']['in_zone']*100:.1f}%  out of zone {ts['trip_rate']['out_of_zone']*100:.1f}%  "
              f"switching {ts['trip_rate']['switching']*100:.1f}%")
    json.dump(result, open(os.path.join(OUT, "real_ml.json"), "w"), indent=2)
    plot(result)
    print(f"\nsaved results/real_ml.json, results/real_ml.png  [{time.time()-t0:.0f}s]")


def plot(result):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = ["zone-1 rule", "MLP", "gradient boosting", "random forest", "engineered + LR"]
    colors = dict(zip(names, ["tab:gray", "tab:red", "tab:orange", "tab:olive", "tab:green"]))
    panels = [("within", "testgrid_A", "Relay A, within relay"), ("within", "testgrid_B", "Relay B, within relay"),
              ("cross", "testgrid_A->testgrid_B", "Train A, test B (unseen relay)"),
              ("cross", "testgrid_A->doubleline", "Train A, test DoubleLine (unseen grid)")]
    fig, axs = plt.subplots(1, 4, figsize=(18, 4.6), sharey=True)
    for ax, (kind, key, title) in zip(axs, panels):
        block = result[kind][key]
        for n in names:
            xs = [t for t in DECISIONS_MS if n in block[t]]
            ys = [block[t][n]["auc"] for t in xs]
            if xs:
                ax.plot(xs, ys, marker="o", color=colors[n], label=n)
        ax.axhline(0.5, ls="--", lw=.8, color="k")
        ax.set_title(title, fontsize=10); ax.set_xlabel("decision time after inception (ms)")
        ax.set_xticks(DECISIONS_MS); ax.grid(alpha=.3)
    axs[0].set_ylabel("ROC AUC, in zone vs out of zone"); axs[0].set_ylim(0.3, 1.02)
    axs[0].legend(fontsize=8, loc="lower right")
    fig.suptitle("Causal windows, physical V/I normalisation, models from the literature. "
                 "EvEMTBench TestGrid110kV and DoubleLine.", fontsize=11)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "real_ml.png"), dpi=140)


if __name__ == "__main__":
    main()
