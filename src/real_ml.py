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
   1 for every relay. On top of that, one scale per channel fitted on the training fold
   (ChannelScaler). A per-sample-position StandardScaler was tried first and is wrong here:
   see ChannelScaler.

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

7. A measurement chain (white noise at 0.1 % of nominal, 16-bit ADC) on every record, and a
   shortcut control that must score near 0.5. Without the noise, tree models read the zone
   label from sub-volt numerical differences in the pre-fault waveform. See measurement_chain.

8. Operating thresholds from out-of-fold training scores, never in-sample ones (oof_scores).

9. Classes balanced: class_weight for the forest and logistic regression, minority
   oversampling for the MLP and boosting (fit_balanced).

Known limitation: the 9600 -> 6400 Hz polyphase resampling in evemt.py is non-causal, so about
1 ms of the fault transient leaks backwards into the samples just before inception and into
the last samples before each decision time. It does not create the shortcut above (that sits
40 to 100 ms before inception) but it does give every detector, rule included, up to 1 ms of
look-ahead.

    python src/real_ml.py
"""
import sys, os, json, time, zlib
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


NOISE_REL = 1e-3      # white noise, sigma as a fraction of nominal (0.1 %, 60 dB below nominal)
ADC_BITS = 16
V_FULL_SCALE = 2.0    # ADC range +-2 pu voltage
I_FULL_SCALE = 40.0   # ADC range +-40 x the relay's pre-fault peak current


def measurement_chain(x, seed_name):
    """What a relay's analogue front end would give: additive white noise and 16-bit
    quantisation, applied once to the raw record so the rule and every model see the same data.

    Why this is needed and not cosmetic: the noise-free benchmark records carry a numerical
    fingerprint of each simulation configuration in the PRE-FAULT waveform, differences of about
    1e-7 pu (0.01 V at 110 kV) that are identical within a configuration. Without noise, tree
    models predict in zone / out of zone from pre-fault samples alone with ROC AUC 1.000, which
    is physically impossible, and their within-relay scores are that shortcut, not protection.
    See shortcut_control()."""
    rng = np.random.default_rng(zlib.crc32(seed_name.encode()))   # reproducible across runs
    x = x.astype(np.float64)
    ev_guard = x.shape[-1] // 5          # 100 ms of pre-fault record, before the event at 1.1 s
    i_pre = np.abs(x[:, 3:, :ev_guard]).max()
    for ch, (nom, fs) in enumerate([(V_NOM_PEAK, V_FULL_SCALE * V_NOM_PEAK)] * 3 + [(i_pre, I_FULL_SCALE * i_pre)] * 3):
        y = x[:, ch] + rng.normal(0.0, NOISE_REL * nom, x[:, ch].shape)
        step = 2 * fs / 2 ** ADC_BITS
        x[:, ch] = np.clip(np.round(y / step) * step, -fs, fs)
    return x.astype(np.float32)


def relay_data(name):
    cfg = CONFIGS[name]
    import glob
    cache = sorted(glob.glob(os.path.join(ROOT, "data", cfg["cache_glob"])))[0]
    C = load_cache(cache)
    k = C["cubicles"].index(cfg["relay"])
    full = measurement_chain(np.asarray(C["x"][:, k]), cfg["relay"])   # (n, 6, 3201), primary V and A
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
    pre-fault cycle at [256, 384) taken from [-40, -20] ms (shifted back by t mod 20 ms), post cycle at [640, 768) taken
    from the last full cycle before the decision time. Lets the rule and the engineered
    features see exactly the causal window and nothing after it."""
    ev = R["ev"]
    n_post = int(round(t_ms * FS / 1000))
    out = np.zeros((len(idx), 6, 1024))
    # sequence_phasors uses a window-relative DFT basis, so the two source cycles must be a whole
    # number of cycles apart or the post-fault phasors come out rotated against the pre-fault ones
    # (180 deg at 30 and 50 ms, which corrupted the incremental currents used by phase selection).
    # Shift the pre-fault cycle back by n_post mod CYCLE samples; it stays entirely before inception.
    pre = ev - 2 * CYCLE - (n_post % CYCLE)
    out[:, :, EVENT - 2 * CYCLE:EVENT - CYCLE] = R["full"][idx, :, pre:pre + CYCLE]
    out[:, :, EVENT + CYCLE:EVENT + 2 * CYCLE] = R["full"][idx, :, ev + n_post - CYCLE:ev + n_post]
    return out


class ChannelScaler:
    """One scale per channel (6 of them), fitted on the training fold, applied to every sample
    of that channel.

    A per-feature StandardScaler on raw waveform samples is wrong for this data: the benchmark
    sets repeat almost the same pre-fault waveform in every simulation, so many sample
    positions have near-zero variance, and a different relay's slightly different pre-fault
    wave lands tens of thousands of standard deviations away. That saturated every model to a
    constant output on an unseen relay (AUC exactly 0.500) in the first run."""
    def fit(self, X, y=None):
        W = X.reshape(len(X), 6, -1)
        self.scale_ = W.transpose(1, 0, 2).reshape(6, -1).std(axis=1) + 1e-12
        return self

    def transform(self, X):
        W = X.reshape(len(X), 6, -1) / self.scale_[None, :, None]
        return W.reshape(len(X), -1)

    def fit_transform(self, X, y=None):
        return self.fit(X).transform(X)

    def get_params(self, deep=True):
        return {}

    def set_params(self, **p):
        return self


def models(seed):
    from sklearn.neural_network import MLPClassifier
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return {
        "MLP": make_pipeline(ChannelScaler(), MLPClassifier(hidden_layer_sizes=(100,), max_iter=800,
                                                            early_stopping=True, random_state=seed)),
        # balanced by oversampling in fit_balanced: class_weight here takes a slow sample-weight
        # path in scikit-learn 1.9 (96 s instead of 1.4 s per fit on 2,688 inputs)
        "gradient boosting": HistGradientBoostingClassifier(random_state=seed),
        "random forest": RandomForestClassifier(n_estimators=100, class_weight="balanced", n_jobs=-1,
                                                random_state=seed),
        # engineered features are physical quantities with real spread, so a per-feature scaler is fine
        "engineered + LR": make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, class_weight="balanced",
                                                                              random_state=seed)),
    }


def _mlp_logit(pipe, X):
    """Pre-sigmoid output of a fitted make_pipeline(scaler, MLPClassifier). predict_proba
    saturates at exactly 1.0 in float64 once the logit passes ~37, which makes every
    false-alarm threshold degenerate."""
    Z = X
    for step in pipe.steps[:-1]:
        Z = step[1].transform(Z)
    mlp = pipe.steps[-1][1]
    for i, (W, b) in enumerate(zip(mlp.coefs_, mlp.intercepts_)):
        Z = Z @ W + b
        if i < len(mlp.coefs_) - 1:
            Z = np.maximum(Z, 0)
    return Z.ravel()


def score(model, X):
    """A ranking score that does not saturate: logits for the MLP, log-odds for boosting,
    decision_function for logistic regression, probability for the forest (bounded but not
    saturating in practice)."""
    from sklearn.pipeline import Pipeline
    if isinstance(model, Pipeline) and type(model.steps[-1][1]).__name__ == "MLPClassifier":
        return _mlp_logit(model, X)
    if hasattr(model, "decision_function"):
        return model.decision_function(X)
    return model.predict_proba(X)[:, 1]


def fit_balanced(model, X, y, seed):
    """Oversample the minority class for the MLP (no class_weight) and gradient boosting
    (class_weight is very slow there). The forest and logistic regression use class_weight."""
    from sklearn.pipeline import Pipeline
    last = model.steps[-1][1] if isinstance(model, Pipeline) else model
    if type(last).__name__ in ("MLPClassifier", "HistGradientBoostingClassifier"):
        rng = np.random.default_rng(seed)
        pos, neg = np.where(y == 1)[0], np.where(y == 0)[0]
        small, big = (pos, neg) if len(pos) < len(neg) else (neg, pos)
        if len(small) and len(small) < len(big):
            extra = rng.choice(small, len(big) - len(small), replace=True)
            idx = np.concatenate([np.arange(len(y)), extra])
            return model.fit(X[idx], y[idx])
    return model.fit(X, y)


def auc(s, y):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def oof_scores(name, X, y, seed, folds=5):
    """Out-of-fold scores on the training set, used only to place the operating threshold.
    Thresholds from in-sample scores are wrong for models that fit the training set perfectly
    (the forest, boosting): the negatives score far lower in sample than on new data, so the
    threshold lands too low and the false-trip rate on new data explodes."""
    from sklearn.model_selection import StratifiedKFold
    s = np.zeros(len(y))
    for k, (a, b) in enumerate(StratifiedKFold(folds, shuffle=True, random_state=seed).split(X, y)):
        m = fit_balanced(models(seed + 100 + k)[name], X[a], y[a], seed + k)
        s[b] = score(m, X[b])
    return s


def dep_at_far(s_tr, y_tr, s_te, y_te, far):
    """s_tr must be out-of-fold scores (oof_scores), not in-sample ones."""
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
                fit_balanced(m, feats[n][tr], y[tr], f)
                s_tr, s_te = oof_scores(n, feats[n][tr], y[tr], f), score(m, feats[n][te])
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
            fit_balanced(m, Xtr, ytr, 0)
            s_tr, s_te = oof_scores(n, Xtr, ytr, 0), score(m, Xte)
            d, fa, _ = dep_at_far(s_tr, ytr, s_te, yte, 0.05)
            res[n] = dict(auc=auc(s_te, yte), dependability=d, false_trip=fa)
        out[t] = res
        print(f"  [{Rtr['name']} -> {Rte['name']}] t = {t} ms: " + "  ".join(f"{n} {r['auc']:.3f}" for n, r in res.items()), flush=True)
    return out


# ------------------------------------------------------------------------------ stage 1 + combined
def two_stage_security(R, t=20, folds=5, far=0.05):
    """Episode-grouped folds over faults and switching events.

    Stage 1 (fault vs no fault) is trained on post-inception windows of fault and switching
    episodes plus a pre-fault window from each, with the classes balanced. Its threshold is
    set on the training switching events alone, at `far`: switching events are the negatives
    that look like faults, and pre-fault windows are too easy to set a threshold on. With about
    40 switching events per training fold, a 1 % rate cannot be estimated, so 5 % is used and
    stated.
    Stage 2 is the zone decision on the training faults of the zone task, threshold at 5 %
    false trip on out-of-zone faults. A trip needs both stages.
    Reported per test fold: share tripped of in-zone faults, out-of-zone faults and switching
    events, and each stage's pass rate on in-zone faults so a failure can be located."""
    from sklearn.model_selection import StratifiedKFold
    faults = np.where(R["fault_any"])[0]
    sw = np.where(R["switching"])[0]
    zone_idx = np.where(R["pos"] | R["neg"])[0]
    episodes = np.concatenate([faults, sw])
    ep_label = np.concatenate([np.ones(len(faults), int), np.zeros(len(sw), int)])
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=0)
    acc = dict(switching=[], in_zone=[], out_of_zone=[], stage1_pass_in_zone=[], stage2_pass_in_zone=[],
               stage1_auc_fault_vs_switching=[])
    for f, (tr_e, te_e) in enumerate(skf.split(episodes, ep_label)):
        tr_ep, te_ep = episodes[tr_e], episodes[te_e]
        X1 = np.vstack([raw_window(R, tr_ep, t), raw_window(R, tr_ep, t, prefault=True)])
        y1 = np.concatenate([R["fault_any"][tr_ep].astype(int), np.zeros(len(tr_ep), int)])
        m1 = fit_balanced(models(f)["MLP"], X1, y1, f)
        is_sw = np.concatenate([R["switching"][tr_ep], np.zeros(len(tr_ep), bool)])
        thr1 = np.quantile(oof_scores("MLP", X1, y1, f)[is_sw], 1 - far)
        tr_z = np.intersect1d(tr_ep, zone_idx)
        Xz = raw_window(R, tr_z, t); yz = R["pos"][tr_z].astype(int)
        m2 = fit_balanced(models(f)["MLP"], Xz, yz, f)
        thr2 = np.quantile(oof_scores("MLP", Xz, yz, f)[yz == 0], 1 - far)
        Xte = raw_window(R, te_ep, t)
        s1, s2 = score(m1, Xte), score(m2, Xte)
        st1, st2 = s1 > thr1, s2 > thr2
        trip = st1 & st2
        pos_te, neg_te, sw_te = R["pos"][te_ep], R["neg"][te_ep], R["switching"][te_ep]
        acc["in_zone"].append(float(trip[pos_te].mean()))
        acc["out_of_zone"].append(float(trip[neg_te].mean()))
        acc["switching"].append(float(trip[sw_te].mean()))
        acc["stage1_pass_in_zone"].append(float(st1[pos_te].mean()))
        acc["stage2_pass_in_zone"].append(float(st2[pos_te].mean()))
        fsw = R["fault_any"][te_ep] | sw_te
        acc["stage1_auc_fault_vs_switching"].append(auc(s1[fsw], R["fault_any"][te_ep][fsw].astype(int)))
    return dict(decision_ms=t, far=far, switching_events_per_test_fold=int(len(sw) / folds),
                **{k: float(np.mean(v)) for k, v in acc.items()},
                **{k + "_sd": float(np.std(v)) for k, v in acc.items()})


def shortcut_control(R, folds=5):
    """Sanity check that must come out near 0.5: predict in zone vs out of zone from a pre-fault
    window only (45 to 5 ms before inception). Anything well above 0.5 means the models can read
    the label from something other than the fault."""
    from sklearn.model_selection import StratifiedKFold
    idx = np.where(R["pos"] | R["neg"])[0]
    y = R["pos"][idx].astype(int)
    X = raw_window(R, idx, 0, prefault=True)
    out = {}
    for n in ("MLP", "gradient boosting", "random forest"):
        a = []
        for f, (tr, te) in enumerate(StratifiedKFold(folds, shuffle=True, random_state=0).split(X, y)):
            m = fit_balanced(models(f)[n], X[tr], y[tr], f)
            a.append(auc(score(m, X[te]), y[te]))
        out[n] = float(np.mean(a))
    return out


def main():
    t0 = time.time()
    R = {n: relay_data(n) for n in ("testgrid_A", "testgrid_B", "doubleline")}
    for n, r in R.items():
        print(f"{n}: {r['full'].shape}, reach impedance {r['z_reach']:.2f} ohm, in zone {r['pos'].sum()}, "
              f"out of zone {r['neg'].sum()}, switching {r['switching'].sum()}")
    result = dict(measurement=dict(noise_rel=NOISE_REL, adc_bits=ADC_BITS, v_full_scale_pu=V_FULL_SCALE,
                                   i_full_scale_x_prefault=I_FULL_SCALE),
                  shortcut_control={}, within={}, cross={}, two_stage={})
    print("\nShortcut control, pre-fault window only (must be near 0.5):")
    for n in ("testgrid_A", "testgrid_B"):
        result["shortcut_control"][n] = sc = shortcut_control(R[n])
        print(f"  {n}: " + "  ".join(f"{k} {v:.3f}" for k, v in sc.items()), flush=True)
    print("\nWithin-relay zone decision, 5-fold x 2, causal windows:")
    for n in ("testgrid_A", "testgrid_B"):
        result["within"][n] = within_relay_zone(R[n])
    print("\nCross-relay zone decision, trained on one relay, tested on another:")
    for a, b in (("testgrid_A", "testgrid_B"), ("testgrid_B", "testgrid_A"), ("testgrid_A", "doubleline")):
        result["cross"][f"{a}->{b}"] = cross_relay_zone(R[a], R[b])
    print("\nTwo-stage relay at 20 ms (stage 1 trained with switching events, 5 % false-alarm thresholds):")
    for n in ("testgrid_A", "testgrid_B"):
        result["two_stage"][n] = ts = two_stage_security(R[n])
        print(f"  {n}: stage-1 AUC fault vs switching {ts['stage1_auc_fault_vs_switching']:.3f}; tripped: "
              f"in zone {ts['in_zone']*100:.1f}%  out of zone {ts['out_of_zone']*100:.1f}%  "
              f"switching {ts['switching']*100:.1f}% (~{ts['switching_events_per_test_fold']} per fold); "
              f"in-zone pass: stage 1 {ts['stage1_pass_in_zone']*100:.0f}%, stage 2 {ts['stage2_pass_in_zone']*100:.0f}%")
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
