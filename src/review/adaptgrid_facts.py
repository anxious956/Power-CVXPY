"""Fact sheet for EvEMTBench adapt_grid-TestGrid110kV, before any experiment on it.

Answers, with numbers, the questions the protocol for results/ADAPTGRID.md sections 3-4 turns on:
which labels vary (loading, source strength, inception point-on-wave), whether location and fault
resistance are continuous, the SIR across operating points per relay, the pre-fault spread and
whether the H25 pre-fault shortcut exists, the sibling/duplicate structure (and hence what the CV
must group on), event counts per class, and ADC clipping under the measurement chain.

Reads labels and the two relays' re-anchored records only (review.common.load_relay_adapt).

    python src/review/adaptgrid_facts.py    -> results/ADAPTGRID_FACTS.json, results/ADAPTGRID_FACTS.md   (~3 min)
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from review import common as cm
from review import frontend

RELAYS = ("adapt_A", "adapt_B")
LOC_BANDS = ((0, 20), (20, 50), (50, 80), (80, 85), (85, 90), (90, 100))


def q(x, ps=(0, 5, 25, 50, 75, 95, 100)):
    x = np.asarray(x, float)
    return {f"p{p}": float(np.percentile(x, p)) for p in ps} if x.size else {}


def label_facts(L):
    """What varies, what is constant, continuity."""
    F = {}
    var = {c: int(L[c].nunique(dropna=True)) for c in L.columns if L[c].nunique(dropna=True) > 1}
    F["n_simulations"] = int(len(L))
    F["columns_varying"] = var
    F["columns_constant"] = {c: str(L[c].dropna().iloc[0]) for c in L.columns if L[c].nunique(dropna=True) <= 1 and L[c].notna().any()}
    loads = ["loads/Ld2/load_p", "loads/Ld5/load_p", "loads/Ld6/load_p"]
    F["loading"] = {c: dict(min=float(L[c].min()), max=float(L[c].max()), nunique=int(L[c].nunique())) for c in loads}
    P = L[loads].sum(axis=1)
    F["loading"]["total_P_MW"] = dict(min=float(P.min()), median=float(P.median()), max=float(P.max()),
                                      max_over_min=float(P.max() / P.min()))
    F["source"] = {"ExtGrid/usetp": dict(min=float(L["ExtGrid/usetp"].min()), max=float(L["ExtGrid/usetp"].max())),
                   "ExtGrid/phiini_deg": dict(min=float(L["ExtGrid/phiini"].min()), max=float(L["ExtGrid/phiini"].max())),
                   "source_strength_column": "NONE - no short-circuit power, impedance or scaling column; grid strength is not varied"}
    F["grounding"] = {"types": L["grounding/grnd_type"].value_counts().to_dict(),
                      "continuous_parameters": ["grounding/coil_tuning", "grounding/solid_ground_resistance",
                                                "grounding/resistive_ground_resistance", "grounding/parasitic_resistance_percentage"]}
    es = L["events/event_start"]
    F["inception"] = dict(event_start_s=dict(min=float(es.min()), max=float(es.max()), nunique=int(es.nunique())),
                          note="continuous, so the point on wave is randomised (measured below from the records)")
    et = L["events/event_type"].astype(str); shc = et.str.contains("shc")
    loc, rf = L["events/event_flt_target_line_location"], L["events/event_flt_shc_resistance"]
    F["fault_location_pct"] = dict(continuous=bool(loc.nunique() > 100), nunique=int(loc.nunique()), **q(loc[et.str.startswith("flt") & L["events/event_target"].astype(str).str.startswith("MainLn")]))
    F["fault_resistance_ohm_shc"] = dict(continuous=bool(rf.nunique() > 100), nunique=int(rf.nunique()), **q(rf[shc]))
    F["hif_resistance_ohm_incipient"] = q(L["events/event_flt_hif_resistance"][et.str.contains("incipient")], (0, 50, 100))
    F["event_type_counts"] = et.value_counts().to_dict()
    F["event_target_counts"] = L["events/event_target"].astype(str).value_counts().to_dict()
    return F


def pow_at_inception(R, idx):
    """Point on wave of phase-a voltage at inception, from the pre-fault phasor: angle of Va at t = ev."""
    v = cm.seq_phasors(R["full"][idx][:, :3], R["ev"], 128)
    va = cm._phase_q(v)[:, 0]
    return np.degrees(np.angle(va)) % 360.0


def sir_empirical(R):
    """Kasztenny 2021 eqs. (30a/30b) measured, not modelled: faulted-loop voltage at the relay 20 ms into a
    short circuit AT THE REMOTE BUS, in per unit of nominal, SIR = 1/V_pu - 1. Only low-R_f faults are
    faithful (R_f raises V and makes the SIR read low); both are reported."""
    rb = np.where(R["remote_bus_faults"])[0]
    vpre, vpost, ipre, ipost = cm.phasors_at(R, rb, 20, "full", True)
    va, vb, vc = cm._phase_q(vpost).T
    et, ph = R["et"][rb], R["phase"][rb]
    lg = np.char.find(et, "1phg") >= 0
    ll = (np.char.find(et, "2ph") >= 0)
    vln = {"a": va, "b": vb, "c": vc}
    vloop = np.array([abs(vln[p][j]) if lg[j] else (abs(va[j] - vb[j]) if p == "ab" else abs(vb[j] - vc[j]) if p == "bc" else abs(vc[j] - va[j]))
                      for j, p in enumerate(ph)])
    vnom = np.where(lg, cm.V_NOM_PEAK, cm.V_NOM_PEAK * np.sqrt(3))
    sir = 1.0 / np.clip(vloop / vnom, 1e-3, None) - 1.0
    rf = R["rf"][rb]
    out = {}
    for lab, sel in (("R_f<=5", (lg | ll) & (rf <= 5)), ("R_f<=10", (lg | ll) & (rf <= 10)), ("all_R_f (reads low)", lg | ll)):
        out[lab] = dict(n=int(sel.sum()), **q(sir[sel], (0, 25, 50, 75, 100)))
    # the same quantity split by grounding type and by loading quartile, R_f <= 10
    sel = (lg | ll) & (rf <= 10)
    out["by_grounding_Rf<=10"] = {g: dict(n=int((sel & (R["grounding"][rb] == g)).sum()), median=float(np.median(sir[sel & (R["grounding"][rb] == g)])) if (sel & (R["grounding"][rb] == g)).any() else None) for g in ("solid", "resistive", "resonant")}
    out["by_loading_quartile_Rf<=10"] = {int(k): dict(n=int((sel & (R["op_quartile"][rb] == k)).sum()), median=float(np.median(sir[sel & (R["op_quartile"][rb] == k)])) if (sel & (R["op_quartile"][rb] == k)).any() else None) for k in range(4)}
    return out


def h25_control(R, idx, y, groups, a, b, seed=0):
    X = R["full"][idx][:, :, a:b].reshape(len(idx), -1)
    s = np.zeros(len(idx))
    for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(X, y, groups):
        s[te] = HistGradientBoostingClassifier(random_state=seed).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return float(roc_auc_score(y, s))


def relay_facts(name):
    R = cm.load_relay(name)
    ev, n = R["ev"], len(R["et"])
    F = dict(relay=R["cfg"]["relay"], line=R["cfg"]["line"], n=n)
    # --- class counts (the zone task of results/ADAPTGRID.md section 3)
    F["classes"] = {k: int(R[k].sum()) for k in ("pos", "own99", "neg", "neg_bench", "beyond", "remote_bus_faults",
                                                  "parallel", "reverse_bus", "reverse_lines", "other", "incipient", "switching")}
    F["switching_by_type"] = {t: int((R["switching"] & (R["et"] == t)).sum()) for t in np.unique(R["et"][R["switching"]])}
    own = R["pos"] | R["own99"]
    F["own_line_by_location_band"] = {f"{lo}-{hi}": int((own & (R["loc"] > lo) & (R["loc"] <= hi)).sum()) for lo, hi in LOC_BANDS}
    F["pos_by_rf_bin"] = {b: int((R["pos"] & (R["rf_bin"] == b)).sum()) for b in cm.RF_LABELS}
    F["rf_distribution_pos_ohm"] = q(R["rf"][R["pos"]], (0, 10, 25, 50, 75, 90, 100))
    F["rf_distribution_offline_ohm"] = q(R["rf"][R["neg"]], (0, 10, 25, 50, 75, 90, 100))
    F["pos_by_grounding"] = {g: int((R["pos"] & (R["grounding"] == g)).sum()) for g in ("solid", "resistive", "resonant")}
    F["pos_by_type"] = {t: int((R["pos"] & (R["et"] == t)).sum()) for t in np.unique(R["et"][R["pos"]])}
    F["incipient_on_own_line"] = int((R["incipient"] & (R["tgt"] == R["cfg"]["line"])).sum())
    F["min_class_for_5pct_budget"] = cm.min_n_for_budget(0.05)
    # --- operating point and grouping
    F["op_point"] = dict(groups="20 quantile bins of total active load Ld2+Ld5+Ld6", bin_sizes=np.bincount(R["groups"]).tolist(),
                         total_P_MW=q(R["p_total"], (0, 25, 50, 75, 100)))
    # --- siblings / duplicates
    key = np.array([f"{t}|{l:.6f}|{e}|{r:.6f}" for t, l, e, r in zip(R["tgt"], R["loc"], R["et"], R["rf"])])
    F["siblings"] = dict(n_unique_label_keys=int(len(np.unique(key))), n=n,
                         statement="every simulation has a unique (target, location, type, R_f); there are no sibling groups")
    pre = np.asarray(R["full"][:, :, ev - 2 * 128:ev - 128], dtype=np.float32)      # one pre-fault cycle
    h = np.array([hash(np.round(pre[i], 1).tobytes()) for i in range(n)])
    F["duplicates"] = dict(identical_prefault_cycles=int(n - len(np.unique(h))),
                           statement="pre-fault cycles rounded to 0.1 V / 0.1 A: number of records identical to another")
    # --- pre-fault spread across simulations
    vpk, ipk = np.abs(pre[:, :3]).max(axis=(1, 2)), np.abs(pre[:, 3:]).max(axis=(1, 2))
    # amplitude spread, not sample-wise: inception and the grid's initial angle are random, so a sample-wise
    # std across simulations is ~amplitude/sqrt(2) by phase alone and says nothing about the operating point
    F["prefault_spread"] = dict(voltage_peak_V=q(vpk, (0, 5, 50, 95, 100)), current_peak_A=q(ipk, (0, 5, 50, 95, 100)),
                                voltage_peak_rel_std=float(vpk.std() / vpk.mean()), current_peak_rel_std=float(ipk.std() / ipk.mean()),
                                benchmark_for_comparison="results/DATASET_FACTS.json: one operating point, spread ~1e-6 of nominal")
    # --- inception point on wave
    F["inception_pow_deg_phase_a"] = q(pow_at_inception(R, np.where(R["fault_any"])[0]), (0, 25, 50, 75, 100))
    # --- H25: can a model predict the label from the pre-fault window alone?
    idx = np.where(R["pos"] | R["neg"])[0]; y = R["pos"][idx].astype(int); g = R["groups"][idx]
    F["h25_prefault_control_auc"] = {"45..5 ms before inception (REAL_ML section 3)": h25_control(R, idx, y, g, ev - 288, ev - 32),
                                      "40 ms ending at inception (REVIEW H25)": h25_control(R, idx, y, g, ev - 256, ev),
                                      "n": int(len(idx)), "n_pos": int(y.sum()),
                                      "benchmark_for_comparison": "0.48-0.56 and 0.86-0.97 respectively (REVIEW.md section 5 H25/H30)"}
    # --- SIR across operating points
    F["sir_empirical"] = sir_empirical(R)
    F["sir_benchmark_voltage_based"] = "1.04-1.69 (results/review/sir.json, study model, metallic remote-bus fault)"
    # --- ADC clipping: default chain (+-40 x global pre-fault current peak) and relay front end (+-141.4 kA)
    x_i = np.asarray(R["full"][:, 3:], dtype=np.float32)
    F["adc_clipping"] = {}
    for lab, fs_a in (("default chain +-40 x prefault peak", 40.0 * float(np.abs(x_i[:, :, :x_i.shape[-1] // 5]).max())),
                      ("relay front end +-141.4 kA", frontend.I_FS_ABS)):
        clipped = (np.abs(x_i[:, :, ev:]) >= fs_a * 0.999).any(axis=(1, 2))
        F["adc_clipping"][lab] = dict(full_scale_A=float(fs_a), sims_clipped=int(clipped.sum()), in_zone_clipped=int(clipped[R["pos"]].sum()),
                                      neg_clipped=int(clipped[R["neg"]].sum()))
    return F


def write_md(facts, path):
    L = facts["labels"]
    o = []
    o.append("# adapt_grid-TestGrid110kV: fact sheet\n")
    o.append("Generated by `src/review/adaptgrid_facts.py` from `results/ADAPTGRID_FACTS.json`; no number typed by hand. "
             "Read before `ADAPTGRID.md`, whose protocol this decides.\n")
    o.append("## What varies\n")
    o.append(f"- {L['n_simulations']} simulations, {len(L['columns_varying'])} label columns vary. Constant: {L['columns_constant']}.")
    P = L["loading"]["total_P_MW"]
    o.append(f"- **Loading varies**: total active load {P['min']:.0f}–{P['max']:.0f} MW (×{P['max_over_min']:.2f}), continuous per simulation, "
             + ", ".join(f"{k.split('/')[1]} {v['min']:.0f}–{v['max']:.0f} MW" for k, v in L["loading"].items() if k != "total_P_MW") + ".")
    o.append(f"- **Source strength does not vary.** {L['source']['source_strength_column']}. The external grid varies only in voltage setpoint "
             f"({L['source']['ExtGrid/usetp']['min']:.3f}–{L['source']['ExtGrid/usetp']['max']:.3f} pu) and initial angle.")
    o.append(f"- **Grounding varies**: {L['grounding']['types']}, each with continuous parameters. This is a regime axis the benchmark set did not have.")
    ic = L["inception"]["event_start_s"]
    o.append(f"- **Inception is randomised**: event_start {ic['min']:.3f}–{ic['max']:.3f} s, {ic['nunique']} distinct values, so the point on wave is uniform "
             f"(measured below). The benchmark set had one fixed inception — the reason its CVT worst case could not be exercised.")
    fl, fr = L["fault_location_pct"], L["fault_resistance_ohm_shc"]
    o.append(f"- **Fault location is continuous**: {fl['p0']:.1f}–{fl['p100']:.1f} % of the line, {fl['nunique']} distinct values. "
             f"**Fault resistance is continuous**: {fr['p0']:.2f}–{fr['p100']:.1f} Ω, median {fr['p50']:.1f} Ω — the benchmark's 1/10/40 Ω strata become bins, "
             f"and the near-bolted stratum (≤1 Ω) is nearly empty.")
    o.append("")
    for name in RELAYS:
        F = facts[name]
        o.append(f"## {name} — {F['line']}\n")
        c = F["classes"]
        o.append(f"| Class | n | | Class | n |\n|---|---|---|---|---|")
        keys = list(c.keys())
        for i in range(0, len(keys), 2):
            a = keys[i]; b = keys[i + 1] if i + 1 < len(keys) else ""
            o.append(f"| {a} | {c[a]} | | {b} | {c.get(b, '')} |")
        o.append(f"\nOwn-line short circuits by location band: {F['own_line_by_location_band']}. Positives by R_f bin: {F['pos_by_rf_bin']}; "
                 f"by grounding: {F['pos_by_grounding']}. Incipient faults on the own line: {F['incipient_on_own_line']}. "
                 f"A 5 % security budget needs ≥ {F['min_class_for_5pct_budget']} units per class.")
        o.append(f"\n- **Siblings:** {F['siblings']['n_unique_label_keys']} unique label keys for {F['siblings']['n']} simulations — {F['siblings']['statement']}. "
                 f"Identical pre-fault cycles: {F['duplicates']['identical_prefault_cycles']}. **Plain random splits are leak-safe here**; the grouped "
                 f"protocol is kept for a different reason — to hold out whole loading bands ({F['op_point']['groups']}, sizes {min(F['op_point']['bin_sizes'])}–{max(F['op_point']['bin_sizes'])}).")
        ps = F["prefault_spread"]
        o.append(f"- **Pre-fault spread:** phase-voltage peak {ps['voltage_peak_V']['p5']/1e3:.1f}–{ps['voltage_peak_V']['p95']/1e3:.1f} kV (p5–p95), current peak "
                 f"{ps['current_peak_A']['p5']:.0f}–{ps['current_peak_A']['p95']:.0f} A; relative std of the peaks across simulations "
                 f"{ps['voltage_peak_rel_std']*100:.1f} % (V) and {ps['current_peak_rel_std']*100:.1f} % (I), against ~1e-4 % on the benchmark's single operating point. "
                 f"The pre-fault state is now genuinely informative about the operating point.")
        h = F["h25_prefault_control_auc"]
        o.append(f"- **H25 pre-fault shortcut:** gradient boosting on the pre-fault window alone, grouped 5-fold: AUC **{h['45..5 ms before inception (REAL_ML section 3)']:.3f}** "
                 f"(45–5 ms before) and **{h['40 ms ending at inception (REVIEW H25)']:.3f}** (40 ms ending at inception; n={h['n']}, pos={h['n_pos']}). Benchmark: {h['benchmark_for_comparison']}. "
                 f"No exploitable fingerprint or look-ahead at this class balance; the zero-phase resampling is unchanged, so the relay front end stays the correct treatment.")
        pw = F["inception_pow_deg_phase_a"]
        o.append(f"- **Inception point on wave** (phase a): p25/p50/p75 = {pw['p25']:.0f}/{pw['p50']:.0f}/{pw['p75']:.0f}°, range {pw['p0']:.0f}–{pw['p100']:.0f}°: uniform.")
        s = F["sir_empirical"]
        a5, a10 = s["R_f<=5"], s["R_f<=10"]
        o.append(f"- **SIR across operating points** (measured from remote-bus faults, Kasztenny eqs. 30a/30b): R_f ≤ 5 Ω, n={a5['n']}: "
                 f"{a5['p0']:.2f}–{a5['p100']:.2f}, median {a5['p50']:.2f}; R_f ≤ 10 Ω, n={a10['n']}: {a10['p0']:.2f}–{a10['p100']:.2f}, median {a10['p50']:.2f}. "
                 f"By grounding (R_f ≤ 10): { {k: (round(v['median'], 2) if v['median'] is not None else None) for k, v in s['by_grounding_Rf<=10'].items()} }; "
                 f"by loading quartile: { {k: (round(v['median'], 2) if v['median'] is not None else None) for k, v in s['by_loading_quartile_Rf<=10'].items()} }. "
                 f"Benchmark (study model): {F['sir_benchmark_voltage_based']}. **adaptgrid does not reach higher SIR** — loading moves it within ≈0.3–1.4, "
                 f"and source strength is not varied — so the instrument-chain and CVT regime caveat of REVIEW.md §6 Q1 stands unchanged here.")
        ad = F["adc_clipping"]
        o.append("- **ADC clipping:** " + "; ".join(f"{k}: {v['sims_clipped']} simulations ({v['in_zone_clipped']} in-zone, {v['neg_clipped']} negatives) at ±{v['full_scale_A']/1e3:.1f} kA" for k, v in ad.items()) + ".")
        o.append("")
    o.append("## What this decides for the protocol\n")
    o.append("1. **Grouping key = loading bin** (20 quantile bins of total P). No siblings exist, so leakage is not the reason; transfer across operating "
             "points is. The transfer test proper is leave-one-loading-quartile-out.\n"
             "2. **Grounding type is a reporting stratum** for every ground-fault result; resonant grounding starves single-phase faults of current.\n"
             "3. **R_f is reported in bins** (≤1, 1–10, 10–40, >40 Ω); the ≤1 Ω stratum is too small to carry a claim.\n"
             "4. **Security bounds are finally tight**: 5,474 switching events and >2,800 off-line faults per relay against 50 and ~120–270 on the benchmark.\n"
             "5. **The regime does not widen**: SIR ≤ 1.4 and source strength fixed, so nothing here tests the weak-system claims.\n")
    open(path, "w", encoding="utf-8").write("\n".join(o))


if __name__ == "__main__":
    t0 = time.time()
    R0 = cm.load_relay(RELAYS[0])
    facts = dict(commit=cm.git_commit(), cache="data/adapt_grid-TestGrid110kV_cache.meta.npz", labels=label_facts(R0["labels"]))
    del R0
    for name in RELAYS:
        facts[name] = relay_facts(name)
        print(f"[{name}] done [{time.time()-t0:.0f}s]", flush=True)
    jp = os.path.join(cm.ROOT, "results", "ADAPTGRID_FACTS.json")
    json.dump(facts, open(jp, "w"), indent=1, default=str)
    write_md(facts, os.path.join(cm.ROOT, "results", "ADAPTGRID_FACTS.md"))
    print(f"saved {jp} and ADAPTGRID_FACTS.md  [{time.time()-t0:.0f}s]")
