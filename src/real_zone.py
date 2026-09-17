"""
The zone experiment on real EMT data: EvEMTBench benchmark-DoubleLine.

Grid (from the archive's own graph): two 30 GVA external grids behind 380/110 kV transformers
at buses 1 and 3, a 200 MW load at bus 2, and two double-circuit 110 kV line pairs
1-2 (20 km and 25 km) and 2-3 (30 km and 40 km). No inverter-based resources. This is the
conventional, stiff-source case, and it is the control arm for the inverter experiment.

Relay: bus 1, start of line 1-2A (cubicle Cub_2). Zone 1 covers the first 85 % of that line.

    in zone      faults on 1-2A at 1, 20, 50, 80 %                         (positives)
    out of zone  faults on 2-3A and 2-3B at 1 and 20 %, and at bus 2        (negatives)
    reported separately, never trained on:
                 faults on 1-2A at 99 %      (past the reach on the relay's own line)
                 faults on the parallel line 1-2B, all locations
                 non-fault switching events

All fault types, all three fault resistances (1, 10, 40 ohm), all phase selections.

Five detectors:
  zone-1 setting     the relay a protection engineer would set: six k0-compensated loops,
                     current supervision, trip if the smallest forward reactance is below
                     0.85 * line reactance. Nothing learned.
  reactance score    the same quantity with its threshold learned on the training folds
  |i-|               negative-sequence current magnitude
  engineered + LR    the multivariate relay feature set
  1D CNN             raw six-channel window

Protocol: 5-fold stratified cross-validation repeated 3 times. Each simulation contributes one
window, so folds are already grouped by episode and nothing leaks between train and test.

  python src/real_zone.py [cache.npz]
"""
import sys, os, json, glob, time
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evemt import load_cache, line_params, window
from zone_model import supervised_reactance
from zone_detect import score_reactance, score_negseq, zone_features, _phasors, _seq_vec
from detect import evaluate, train_cnn

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "results")
RELAY = "Cub_2\\pex_MainBus1_MainLn1-2A"
LINE = "MainLn1-2A"
REACH = 0.85


def engineered_scores(Xtr, ytr, Xte, g, seed):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, C=1.0, random_state=seed))
    clf.fit(zone_features(Xtr, g), ytr)
    return clf, clf.decision_function(zone_features(Xtr, g)), clf.decision_function(zone_features(Xte, g))


def main():
    cache = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(os.path.join(ROOT, "data", "*DoubleLine*_cache.npz")))[0]
    t0 = time.time()
    C = load_cache(cache)
    L = C["labels"]
    ci = C["cubicles"].index(RELAY)
    X_all = window(C["x"][:, ci], C["event_index"])            # (n, 6, 1024)
    lp = line_params(C["graph"], LINE)
    g = SimpleNamespace(z1=lp["z1"], z0_ratio=lp["z0"] / lp["z1"])
    x_reach = REACH * lp["length_km"] * lp["z1"].imag
    print(f"loaded {X_all.shape} from {os.path.basename(cache)} in {time.time()-t0:.0f}s")
    print(f"line {LINE}: {lp['length_km']:.0f} km, z1 {lp['z1']:.4f}, z0 {lp['z0']:.4f} ohm/km, "
          f"zone-1 reactance reach {x_reach:.3f} ohm")

    et = L["events/event_type"].astype(str)
    tgt = L["events/event_target"].astype(str)
    loc = L["events/event_flt_target_line_location"]
    rf = L["events/event_flt_shc_resistance"]
    shc = et.str.contains("shc").to_numpy()

    pos = shc & (tgt == LINE).to_numpy() & loc.isin([1, 20, 50, 80]).to_numpy()
    neg = shc & ((tgt.isin(["MainLn2-3A", "MainLn2-3B"]) & loc.isin([1, 20])) | (tgt == "MainBus2")).to_numpy()
    own99 = shc & (tgt == LINE).to_numpy() & (loc == 99).to_numpy()
    parallel = shc & (tgt == "MainLn1-2B").to_numpy()
    nonfault = et.str.startswith("switch").to_numpy()
    print(f"in zone {pos.sum()}, out of zone {neg.sum()} | held out: own line 99% {own99.sum()}, "
          f"parallel line {parallel.sum()}, non-fault events {nonfault.sum()}")

    idx = np.where(pos | neg)[0]
    X = X_all[idx]
    y = pos[idx].astype(int)

    # ---------------------------------------------------------------- zone-1 setting, no learning
    react_all = score_reactance(X_all, g)
    trip = react_all < x_reach
    setting = dict(
        dependability=float(trip[pos].mean()), false_trip_out_of_zone=float(trip[neg].mean()),
        trip_own_line_99=float(trip[own99].mean()), trip_parallel_line=float(trip[parallel].mean()),
        trip_nonfault=float(trip[nonfault].mean()) if nonfault.any() else None)
    breakdown = {}
    for name, mask in (("in zone", pos), ("out of zone", neg), ("own line 99%", own99), ("parallel 1-2B", parallel)):
        row = {}
        for r in (1.0, 10.0, 40.0):
            m = mask & (rf == r).to_numpy()
            row[f"{r:g} ohm"] = float(trip[m].mean()) if m.any() else None
        breakdown[name] = row
    print("\nzone-1 setting (reactance < %.3f ohm), nothing learned:" % x_reach)
    for k, v in setting.items():
        print(f"  {k:26s} {v*100:6.1f} %" if v is not None else f"  {k:26s}   n/a")
    print("  trip rate by fault resistance:")
    for name, row in breakdown.items():
        print("   %-15s " % name + "  ".join(f"{k}: {v*100:5.1f}%" for k, v in row.items() if v is not None))

    # ---------------------------------------------------------------- cross-validated comparison
    from sklearn.model_selection import RepeatedStratifiedKFold
    rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=0)
    keys = ("reactance", "negseq", "engineered", "cnn")
    folds = {k: [] for k in keys}
    react_X, neg_X = react_all[idx], score_negseq(X)
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
                          dep_at_5pct_sd=float(get("detection_at_5pct").std()),
                          false_trip_at_5pct=float(get("false_alarm_at_5pct").mean()))
        s = summary[k]
        print(f"  {k:11s} AUC {s['auc']:.3f} +- {s['auc_sd']:.3f}   dependability at 5% false trip "
              f"{s['dep_at_5pct']*100:5.1f} +- {s['dep_at_5pct_sd']*100:.1f} %")

    # ---------------------------------------------------------------- held-out sets, learned detectors
    # Train each learned detector once on all in/out-of-zone cases, set its threshold at a 5 %
    # false-trip rate on those negatives, then ask how it treats cases it never saw.
    held = {"own line 99%": own99, "parallel line 1-2B": parallel}
    if nonfault.any():
        held["non-fault events"] = nonfault
    heldout = {}
    clf, e_all_tr, _ = engineered_scores(X, y, X[:1], g, seed=0)
    thr_e = np.quantile(e_all_tr[y == 0], 0.95)
    heldout["engineered"] = {n: float((clf.decision_function(zone_features(X_all[m], g)) > thr_e).mean())
                             for n, m in held.items()}
    heldout["zone-1 setting"] = {n: float(trip[m].mean()) for n, m in held.items()}
    print("\nheld-out sets, fraction the detector calls in-zone (all should be low):")
    for d, r in heldout.items():
        print(f"  {d:15s} " + "   ".join(f"{n}: {v*100:5.1f}%" for n, v in r.items()))

    # ---------------------------------------------------------------- figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw=dict(width_ratios=[1, 1.15]))
    names = ["zone-1 reactance\n(threshold learned)", "|i⁻| magnitude", "engineered\nfeatures + LR", "1D CNN\nraw waveform"]
    cols = ["tab:gray", "tab:blue", "tab:green", "tab:red"]
    au = [summary[k]["auc"] for k in keys]
    sd = [summary[k]["auc_sd"] for k in keys]
    axs[0].bar(range(4), au, yerr=sd, color=cols, capsize=4)
    axs[0].axhline(0.5, ls="--", lw=.8, color="k")
    for i, v in enumerate(au):
        axs[0].text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=9)
    axs[0].set_xticks(range(4)); axs[0].set_xticklabels(names, fontsize=8)
    axs[0].set_ylim(0.4, 1.08); axs[0].set_ylabel("ROC AUC, in zone vs out of zone")
    axs[0].set_title("Real EMT data (EvEMTBench DoubleLine), no inverters\n5-fold CV x 3, mean ± sd")
    rows = list(breakdown.keys()); cols_r = ["1 ohm", "10 ohm", "40 ohm"]
    M = np.array([[breakdown[r][c] if breakdown[r][c] is not None else np.nan for c in cols_r] for r in rows]) * 100
    im = axs[1].imshow(M, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            axs[1].text(j, i, f"{M[i,j]:.0f}%", ha="center", va="center", fontsize=10)
    axs[1].set_xticks(range(3)); axs[1].set_xticklabels(["R_f = 1 Ω", "10 Ω", "40 Ω"])
    axs[1].set_yticks(range(len(rows))); axs[1].set_yticklabels(rows)
    axs[1].set_title(f"Zone-1 setting (X < {x_reach:.2f} Ω), nothing learned:\nshare of faults tripped. "
                     "Top row should be green, the rest red.")
    plt.colorbar(im, ax=axs[1], fraction=0.04)
    plt.tight_layout()
    png = os.path.join(OUT, "real_doubleline.png")
    plt.savefig(png, dpi=140)
    json.dump(dict(dataset="EvEMTBench benchmark-DoubleLine", relay=RELAY, line=LINE,
                   line_km=lp["length_km"], z1=[lp["z1"].real, lp["z1"].imag],
                   z0=[lp["z0"].real, lp["z0"].imag], zone1_reach_ohm=x_reach,
                   counts=dict(in_zone=int(pos.sum()), out_of_zone=int(neg.sum()), own99=int(own99.sum()),
                               parallel=int(parallel.sum()), nonfault=int(nonfault.sum())),
                   zone1_setting=setting, zone1_breakdown=breakdown, cv=summary, heldout=heldout),
              open(os.path.join(OUT, "real_doubleline.json"), "w"), indent=2)
    print(f"\nsaved {os.path.relpath(png)}  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
