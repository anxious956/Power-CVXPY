"""
The zone experiment on real EMT data (EvEMTBench), one run per (grid, relay).

    python src/real_zone.py doubleline      # control arm: stiff grid, no inverters
    python src/real_zone.py testgrid_A      # relay bus 1 on line 1-2A, inverter at remote bus 2
    python src/real_zone.py testgrid_B      # relay bus 2 on line 2-3,  inverter at remote bus 3

For each relay:
    in zone      faults on the relay's own line at 1, 20, 50, 80 %            (positives)
    out of zone  faults on the lines leaving the remote bus at 1 and 20 %,
                 and faults on the remote bus itself                           (negatives)
    held out, never trained on:
                 own line at 99 % (past the zone-1 reach), the parallel line if there is one,
                 and non-fault switching events
All fault types, all fault resistances, all phase selections.

Detectors:
    zone-1 setting    six k0-compensated loops, faulted-phase selection, trip if the smallest
                      forward reactance is below 0.85 x line reactance. Nothing learned.
    reactance score   the same quantity with its threshold learned on the training folds
    |i-|              negative-sequence current magnitude
    engineered + LR   the multivariate relay feature set
    1D CNN            raw six-channel window

Protocol: 5-fold stratified cross-validation repeated 3 times. One window per simulation, so
folds are grouped by episode and nothing leaks.

For inverter grids the script also measures, from the inverter's own terminals, how far its
current rises during faults, so the 1.2 pu limiter can be confirmed rather than assumed.
"""
import sys, os, json, glob, time
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evemt import load_cache, line_params, window
from zone_detect import score_reactance, score_negseq, zone_features
from detect import evaluate, train_cnn
from waveforms import sequence_phasors

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "results")
REACH = 0.85

CONFIGS = {
    "doubleline": dict(
        cache_glob="benchmark-DoubleLine*_cache.npz",
        title="EvEMTBench DoubleLine, no inverters",
        relay="Cub_2\\pex_MainBus1_MainLn1-2A", line="MainLn1-2A", remote_bus="MainBus2",
        beyond=["MainLn2-3A", "MainLn2-3B"], parallel="MainLn1-2B", ibr_cubicles=[]),
    "testgrid_A": dict(
        cache_glob="benchmark-TestGrid110kV*_cache.meta.npz",
        title="EvEMTBench TestGrid110kV, relay bus 1 on line 1-2A, inverter at remote bus 2",
        relay="Cub_HV_A_A-B-1\\pex_MainBus1_MainLn1-2A", line="MainLn1-2A", remote_bus="MainBus2",
        beyond=["MainLn2-3", "MainLn2-5", "MainLn2-6"], parallel="MainLn1-2B",
        ibr_cubicles=["Cubicle(1)\\pex_MainBus2_Ind2-2IBR"]),
    "testgrid_B": dict(
        cache_glob="benchmark-TestGrid110kV*_cache.meta.npz",
        title="EvEMTBench TestGrid110kV, relay bus 2 on line 2-3, inverter at remote bus 3",
        relay="Cub_HV_B_B-C\\pex_MainBus2_MainLn2-3", line="MainLn2-3", remote_bus="MainBus3",
        beyond=["MainLn3-4"], parallel=None,
        ibr_cubicles=["Cubicle(1)\\pex_MainBus3_Ind3-3IBR"]),
    # EvEMTBench adapt_grid-TestGrid110kV: the same grid, cubicles and relays, but randomised events
    # and randomised operating states (loads scaled 50-150 %). Cache built from the archive on D: by
    # logs/build_adaptgrid_cache.py with the benchmark's 7 cubicles. The benchmark globs above are
    # pinned to 'benchmark-' because this cache sorts first and would otherwise be picked up silently.
    "adapt_A": dict(
        cache_glob="adapt_grid-TestGrid110kV*_cache.meta.npz",
        title="EvEMTBench adapt_grid-TestGrid110kV, relay bus 1 on line 1-2A, varied operating points",
        relay="Cub_HV_A_A-B-1\\pex_MainBus1_MainLn1-2A", line="MainLn1-2A", remote_bus="MainBus2",
        beyond=["MainLn2-3", "MainLn2-5", "MainLn2-6"], parallel="MainLn1-2B",
        ibr_cubicles=["Cubicle(1)\\pex_MainBus2_Ind2-2IBR"], adaptgrid=True,
        remote_cubicle="Cub_HV_B_A-B-1\\pex_MainBus2_MainLn1-2A"),   # remote end of the same line (POTT-equivalent reference)
    "adapt_B": dict(
        cache_glob="adapt_grid-TestGrid110kV*_cache.meta.npz",
        title="EvEMTBench adapt_grid-TestGrid110kV, relay bus 2 on line 2-3, varied operating points",
        relay="Cub_HV_B_B-C\\pex_MainBus2_MainLn2-3", line="MainLn2-3", remote_bus="MainBus3",
        beyond=["MainLn3-4"], parallel=None,
        ibr_cubicles=["Cubicle(1)\\pex_MainBus3_Ind3-3IBR"], adaptgrid=True,
        remote_cubicle="Cub_HV_C_B-C\\pex_MainBus3_MainLn2-3"),
}


def engineered_scores(Xtr, ytr, Xte, g, seed):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, C=1.0, random_state=seed))
    clf.fit(zone_features(Xtr, g), ytr)
    return clf, clf.decision_function(zone_features(Xtr, g)), clf.decision_function(zone_features(Xte, g))


def windows(C, cubicle):
    k = C["cubicles"].index(cubicle)
    return np.ascontiguousarray(window(np.asarray(C["x"][:, k]), C["event_index"]))


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "doubleline"
    cfg = CONFIGS[name]
    cache = sys.argv[2] if len(sys.argv) > 2 else sorted(glob.glob(os.path.join(ROOT, "data", cfg["cache_glob"])))[0]
    t0 = time.time()
    C = load_cache(cache)
    L = C["labels"]
    X_all = windows(C, cfg["relay"])                              # (n, 6, 1024)
    lp = line_params(C["graph"], cfg["line"])
    g = SimpleNamespace(z1=lp["z1"], z0_ratio=lp["z0"] / lp["z1"])
    x_reach = REACH * lp["length_km"] * lp["z1"].imag
    print(f"[{name}] {cfg['title']}")
    print(f"loaded {X_all.shape} from {os.path.basename(cache)} in {time.time()-t0:.0f}s")
    print(f"line {cfg['line']}: {lp['length_km']:.1f} km, z1 {lp['z1']:.4f}, z0 {lp['z0']:.4f} ohm/km, "
          f"zone-1 reactance reach {x_reach:.3f} ohm")

    et = L["events/event_type"].astype(str)
    tgt = L["events/event_target"].astype(str)
    loc = L["events/event_flt_target_line_location"]
    rf = L["events/event_flt_shc_resistance"]
    shc = et.str.contains("shc").to_numpy()
    print("fault targets in labels:", sorted(tgt[shc].unique()))
    print("fault resistances:", sorted(rf[shc].dropna().unique()), " locations:", sorted(loc[shc].dropna().unique()))

    pos = shc & (tgt == cfg["line"]).to_numpy() & loc.isin([1, 20, 50, 80]).to_numpy()
    neg = shc & ((tgt.isin(cfg["beyond"]) & loc.isin([1, 20])) | (tgt == cfg["remote_bus"])).to_numpy()
    own99 = shc & (tgt == cfg["line"]).to_numpy() & (loc == 99).to_numpy()
    parallel = (shc & (tgt == cfg["parallel"]).to_numpy()) if cfg["parallel"] else np.zeros(len(L), bool)
    nonfault = et.str.startswith("switch").to_numpy()
    print(f"in zone {pos.sum()}, out of zone {neg.sum()} | held out: own line 99% {own99.sum()}, "
          f"parallel line {parallel.sum()}, non-fault events {nonfault.sum()}")
    if pos.sum() == 0 or neg.sum() == 0:
        raise SystemExit("empty class; check CONFIGS against the fault targets printed above")

    # ------------------------------------------------ is the inverter actually current-limiting?
    spc, ev = C["samples_per_cycle"], 4 * C["samples_per_cycle"]
    inverter = {}
    for cub in cfg["ibr_cubicles"]:
        W = windows(C, cub)
        peak_pre = np.abs(W[:, 3:, ev - 2 * spc:ev]).max(axis=(1, 2))
        peak_post = np.abs(W[:, 3:, ev + spc // 4:ev + 3 * spc]).max(axis=(1, 2))
        ratio = peak_post / np.maximum(peak_pre, 1e-9)
        i1_pre = np.array([abs(sequence_phasors(w[3:], ev - 2 * spc)[1]) for w in W])
        inverter[cub] = dict(prefault_I1_median_A=float(np.median(i1_pre[shc])),
                             fault_peak_ratio_median=float(np.median(ratio[shc])),
                             fault_peak_ratio_p95=float(np.percentile(ratio[shc], 95)),
                             fault_peak_ratio_max=float(ratio[shc].max()))
        v = inverter[cub]
        print(f"inverter {cub}: prefault |I1| median {v['prefault_I1_median_A']:.0f} A; during faults peak "
              f"current is {v['fault_peak_ratio_median']:.2f}x prefault (median), "
              f"{v['fault_peak_ratio_p95']:.2f}x (95th pct), {v['fault_peak_ratio_max']:.2f}x (max)")
    relay_ratio = (np.abs(X_all[:, 3:, ev + spc // 4:ev + 3 * spc]).max(axis=(1, 2))
                   / np.maximum(np.abs(X_all[:, 3:, ev - 2 * spc:ev]).max(axis=(1, 2)), 1e-9))
    print(f"relay current during in-zone faults: {np.median(relay_ratio[pos]):.1f}x prefault peak (median)")

    # ------------------------------------------------ zone-1 setting, nothing learned
    react_all = score_reactance(X_all, g)
    trip = react_all < x_reach
    setting = dict(dependability=float(trip[pos].mean()), false_trip_out_of_zone=float(trip[neg].mean()),
                   trip_own_line_99=float(trip[own99].mean()) if own99.any() else None,
                   trip_parallel_line=float(trip[parallel].mean()) if parallel.any() else None,
                   trip_nonfault=float(trip[nonfault].mean()) if nonfault.any() else None)
    groups = [("in zone", pos), ("out of zone", neg), ("own line 99%", own99)]
    if parallel.any():
        groups.append((f"parallel {cfg['parallel']}", parallel))
    resistances = sorted(rf[shc].dropna().unique())
    breakdown = {gn: {f"{r:g} ohm": (float(trip[m & (rf == r).to_numpy()].mean())
                                     if (m & (rf == r).to_numpy()).any() else None) for r in resistances}
                 for gn, m in groups}
    print(f"\nzone-1 setting (reactance < {x_reach:.3f} ohm), nothing learned:")
    for k, v in setting.items():
        print(f"  {k:26s} " + (f"{v*100:6.1f} %" if v is not None else "   n/a"))
    print("  trip rate by fault resistance:")
    for gn, row in breakdown.items():
        print(f"   {gn:18s} " + "  ".join(f"{k}: {v*100:5.1f}%" for k, v in row.items() if v is not None))

    # ------------------------------------------------ cross-validated comparison
    from sklearn.model_selection import RepeatedStratifiedKFold
    idx = np.where(pos | neg)[0]
    X, y = X_all[idx], pos[idx].astype(int)
    react_X, neg_X = react_all[idx], score_negseq(X)
    keys = ("reactance", "negseq", "engineered", "cnn")
    folds = {k: [] for k in keys}
    rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=0)
    for f, (tr, te) in enumerate(rskf.split(X, y)):
        folds["reactance"].append(evaluate(react_X[tr], y[tr], react_X[te], y[te]))
        folds["negseq"].append(evaluate(neg_X[tr], y[tr], neg_X[te], y[te]))
        _, e_tr, e_te = engineered_scores(X[tr], y[tr], X[te], g, seed=f)
        folds["engineered"].append(evaluate(e_tr, y[tr], e_te, y[te]))
        s_tr, s_te = train_cnn(X[tr], y[tr], X[te], epochs=25, seed=f)
        folds["cnn"].append(evaluate(s_tr, y[tr], s_te, y[te]))
        if (f + 1) % 5 == 0:
            print(f"  folds done: {f+1}/15  [{time.time()-t0:.0f}s]", flush=True)
    summary = {}
    print("\ncross-validated, 5 folds x 3 repeats (mean +- sd):")
    for k in keys:
        get = lambda fld: np.array([r[fld] for r in folds[k]])
        summary[k] = dict(auc=float(get("auc").mean()), auc_sd=float(get("auc").std()),
                          dep_at_5pct=float(get("detection_at_5pct").mean()),
                          dep_at_5pct_sd=float(get("detection_at_5pct").std()))
        s = summary[k]
        print(f"  {k:11s} AUC {s['auc']:.3f} +- {s['auc_sd']:.3f}   dependability at 5% false trip "
              f"{s['dep_at_5pct']*100:5.1f} +- {s['dep_at_5pct_sd']*100:.1f} %")

    # ------------------------------------------------ held-out sets
    held = {"own line 99%": own99}
    if parallel.any():
        held[f"parallel line {cfg['parallel']}"] = parallel
    if nonfault.any():
        held["non-fault events"] = nonfault
    clf, e_all_tr, _ = engineered_scores(X, y, X[:1], g, seed=0)
    thr_e = np.quantile(e_all_tr[y == 0], 0.95)
    heldout = {"engineered": {n: float((clf.decision_function(zone_features(X_all[m], g)) > thr_e).mean())
                              for n, m in held.items() if m.any()},
               "zone-1 setting": {n: float(trip[m].mean()) for n, m in held.items() if m.any()}}
    print("\nheld-out sets, fraction called in zone (all should be low):")
    for d, r in heldout.items():
        print(f"  {d:15s} " + "   ".join(f"{n}: {v*100:5.1f}%" for n, v in r.items()))

    # ------------------------------------------------ figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw=dict(width_ratios=[1, 1.15]))
    labels_ = ["zone-1 reactance\n(threshold learned)", "|i⁻| magnitude", "engineered\nfeatures + LR", "1D CNN\nraw waveform"]
    colors = ["tab:gray", "tab:blue", "tab:green", "tab:red"]
    au = [summary[k]["auc"] for k in keys]
    axs[0].bar(range(4), au, yerr=[summary[k]["auc_sd"] for k in keys], color=colors, capsize=4)
    axs[0].axhline(0.5, ls="--", lw=.8, color="k")
    for i, v in enumerate(au):
        axs[0].text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=9)
    axs[0].set_xticks(range(4)); axs[0].set_xticklabels(labels_, fontsize=8)
    axs[0].set_ylim(0.4, 1.08); axs[0].set_ylabel("ROC AUC, in zone vs out of zone")
    axs[0].set_title(cfg["title"].replace(", relay", "\nrelay") + "\n5-fold CV x 3, mean ± sd", fontsize=9)
    rows = list(breakdown.keys()); cols = list(next(iter(breakdown.values())).keys())
    M = np.array([[breakdown[r][c] if breakdown[r][c] is not None else np.nan for c in cols] for r in rows]) * 100
    im = axs[1].imshow(M, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if not np.isnan(M[i, j]):
                axs[1].text(j, i, f"{M[i,j]:.0f}%", ha="center", va="center", fontsize=10)
    axs[1].set_xticks(range(len(cols))); axs[1].set_xticklabels([f"R_f = {c.replace(' ohm',' Ω')}" for c in cols])
    axs[1].set_yticks(range(len(rows))); axs[1].set_yticklabels(rows)
    axs[1].set_title(f"Zone-1 setting (X < {x_reach:.2f} Ω), nothing learned: share of faults tripped.\n"
                     "Top row should be green, the rest red.", fontsize=9)
    plt.colorbar(im, ax=axs[1], fraction=0.04)
    plt.tight_layout()
    png = os.path.join(OUT, f"real_{name}.png")
    plt.savefig(png, dpi=140)
    json.dump(dict(config=name, dataset=cfg["title"], relay=cfg["relay"], line=cfg["line"],
                   line_km=lp["length_km"], z1=[lp["z1"].real, lp["z1"].imag], z0=[lp["z0"].real, lp["z0"].imag],
                   zone1_reach_ohm=x_reach, inverter_current=inverter,
                   relay_current_ratio_in_zone_median=float(np.median(relay_ratio[pos])),
                   counts=dict(in_zone=int(pos.sum()), out_of_zone=int(neg.sum()), own99=int(own99.sum()),
                               parallel=int(parallel.sum()), nonfault=int(nonfault.sum())),
                   zone1_setting=setting, zone1_breakdown=breakdown, cv=summary, heldout=heldout),
              open(os.path.join(OUT, f"real_{name}.json"), "w"), indent=2)
    print(f"\nsaved {os.path.relpath(png)}  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
