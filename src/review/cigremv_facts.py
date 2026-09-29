"""Fact sheet for adapt_grid-CigreMVGrid, read before any relay is chosen or any protocol is fixed.

Reads the cache built by src/build_cigremv_cache.py (every cubicle; found through EVEMT_CACHE_DIRS or data/).
Dataset level:
  grid         buses, lines (parameters read with evemt.line_params), transformers, inverters, external grid
  labels       what varies and what is constant, event counts, fault targets and whether every target exists
               in the graph, fault location only on lines, R_f / location / grounding / loading ranges
  integrity    NaN or infinite samples, all-zero cubicle records, whether every inception fits the
               [ev-640, ev+640) window
  siblings     unique (target, location, type, R_f) keys among short circuits; identical pre-fault cycles
  inception    point on wave of phase-a voltage at inception
  sources      the inverters' share of the fault-current rise (inverter and 110/20 kV transformer cubicles)
  lines        pre-fault current at every line end (a normally-open tie carries none)
  waveforms    results/cigremv_waveforms.png: one bolted and one high-R_f ground fault, a three-phase fault,
               an inverter trip, a motor start and a capacitor switching, seen from the bus-3 end of line 3-4
Candidate-relay level (every candidate line end, built from the graph; nominal 20 kV throughout):
  classes      pos (own line <= 85 %), guard band, off-line by class, reverse, switching, incipient, by R_f
               band and grounding, and own-line faults by location band
  shortcut     H25: gradient boosting on the pre-fault window alone, grouped by loading bin, AUC
  SIR          measured from low-R_f remote-bus faults (Kasztenny 2021 eqs. 30a/30b) with the 20 kV nominal
  clipping     ADC clipping under the default chain and the relay front end
  inverter     share of the fault-current rise for faults on the candidate's own line

    set EVEMT_CACHE_DIRS=D:\\evemt\\cache
    python src/review/cigremv_facts.py
    -> results/CIGREMV_FACTS.json, results/cigremv_waveforms.png
"""
import os, sys, json, glob, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from evemt import load_cache, line_params
import real_zone
from review import common as cm
from review import frontend

OUT = os.path.join(cm.ROOT, "results", "CIGREMV_FACTS.json")
PNG = os.path.join(cm.ROOT, "results", "cigremv_waveforms.png")
GLOB = "adapt_grid-CigreMVGrid*_cache.meta.npz"
HALF, SPC = cm.ADAPT_HALF, cm.SPC
VN_KV = 20.0
V_NOM = VN_KV * 1e3 * np.sqrt(2 / 3)
CANDIDATES = [("MainLn1-2", "MainBus1"), ("MainLn2-3", "MainBus2"), ("MainLn2-3", "MainBus3"),
              ("MainLn3-4", "MainBus3"), ("MainLn3-4", "MainBus4"), ("MainLn3-8", "MainBus3"),
              ("MainLn4-5", "MainBus4"), ("MainLn12-13", "MainBus12"), ("MainLn13-14", "MainBus13"),
              ("MainLn13-14", "MainBus14")]


def q(x, ps=(0, 5, 25, 50, 75, 95, 100)):
    x = np.asarray(x, float)
    return {f"p{p}": float(np.percentile(x, p)) for p in ps} if x.size else {}


def find_cache():
    hits = [h for d in cm.CACHE_DIRS for h in sorted(glob.glob(os.path.join(d, GLOB)))]
    if not hits:
        raise FileNotFoundError(f"{GLOB} not in {cm.CACHE_DIRS}; set EVEMT_CACHE_DIRS")
    return hits[0]


def dft(x, end, n=SPC):
    seg = x[..., end - n:end].astype(np.float64)
    k = np.arange(end - n, end)
    return (2.0 / n) * (seg @ np.exp(-2j * np.pi * k / SPC))


def phase_rise(X, t_ms):
    pre = np.abs(dft(X[:, 3:], HALF - SPC))
    post = np.abs(dft(X[:, 3:], HALF + int(round(t_ms * cm.FS / 1000))))
    return (post - pre).max(axis=1), pre.max(axis=1)


# ------------------------------------------------------------------ dataset level
def graph_summary(G):
    ibr = {}
    for n, a in G.nodes(data=True):
        for k, v in a.items():
            if k.endswith("cntrlFMUIBRController_param_dict"):
                ibr[str(n)] = dict(Sn_MVA=v.get("Sn", 0) / 1e6, Imax_pu=v.get("Imax"), P_FLAG=v.get("P_FLAG"),
                                   Q_FLAG=v.get("Q_FLAG"), IqV_FLAG=v.get("IqV_FLAG"))
    lines, other = {}, []
    for u, v, k, a in G.edges(keys=True, data=True):
        if str(k).startswith("MainLn"):
            try:
                lp = line_params(G, k)
                lines[str(k)] = dict(buses=[str(u), str(v)], length_km=lp["length_km"], z1_ohm_per_km=[lp["z1"].real, lp["z1"].imag],
                                     z0_ohm_per_km=[lp["z0"].real, lp["z0"].imag],
                                     z1_ohm=[lp["z1"].real * lp["length_km"], lp["z1"].imag * lp["length_km"]])
            except Exception as e:
                lines[str(k)] = dict(buses=[str(u), str(v)], error=repr(e))
        else:
            other.append(dict(u=str(u), v=str(v), key=str(k),
                              params={pk: {kk: vv for kk, vv in pv.items() if not isinstance(vv, (list, dict))}
                                      for pk, pv in a.items() if isinstance(pv, dict)}))
    return dict(n_nodes=G.number_of_nodes(), n_edges=G.number_of_edges(), inverters=ibr, lines=lines, other_edges=other,
                ext_grid={str(n): a.get("ExtGrid_param_dict") for n, a in G.nodes(data=True) if "ExtGrid_param_dict" in a})


def label_facts(L, G):
    var = {c: int(L[c].nunique(dropna=True)) for c in L.columns if L[c].nunique(dropna=True) > 1}
    const = {c: str(L[c].dropna().iloc[0]) for c in L.columns if L[c].nunique(dropna=True) <= 1 and L[c].notna().any()}
    et = L["events/event_type"].astype(str); tgt = L["events/event_target"].astype(str)
    shc = et.str.contains("shc"); flt = et.str.startswith("flt")
    loc, rf = L["events/event_flt_target_line_location"], L["events/event_flt_shc_resistance"]
    loads = [c for c in L.columns if c.startswith("loads/") and c.endswith("/load_p") and "LdSwitch" not in c]
    P = L[loads].sum(axis=1)
    nodes = {str(n) for n in G.nodes}; edges = {str(k) for _, _, k in G.edges(keys=True)}
    flt_targets = tgt[flt].value_counts().to_dict()
    return dict(n_simulations=int(len(L)), columns_varying=var, columns_constant=const,
                event_type_counts=et.value_counts().to_dict(),
                fault_targets=flt_targets,
                fault_targets_missing_from_graph=sorted(t for t in flt_targets if t not in nodes and t not in edges),
                fault_targets_on_lines=int((flt & tgt.str.startswith("MainLn")).sum()),
                fault_targets_on_buses=int((flt & tgt.str.startswith("MainBus")).sum()),
                fault_location_pct_on_lines=dict(nunique=int(loc[flt & tgt.str.startswith("MainLn")].nunique()),
                                                 **q(loc[flt & tgt.str.startswith("MainLn")])),
                fault_resistance_ohm_shc=dict(nunique=int(rf[shc].nunique()), **q(rf[shc])),
                hif_resistance_ohm=q(L["events/event_flt_hif_resistance"][et.str.contains("hif")], (0, 50, 100)),
                grounding=L["grounding/grnd_type"].value_counts().to_dict(),
                loading=dict(loads=loads, total_P_MW=dict(min=float(P.min()), median=float(P.median()), max=float(P.max()),
                                                          max_over_min=float(P.max() / P.min()))),
                source=dict(usetp=[float(L["ExtGrid/usetp"].min()), float(L["ExtGrid/usetp"].max())],
                            phiini_deg=[float(L["ExtGrid/phiini"].min()), float(L["ExtGrid/phiini"].max())]),
                inception_s=dict(min=float(L["events/event_start"].min()), max=float(L["events/event_start"].max()),
                                 nunique=int(L["events/event_start"].nunique())))


def integrity(C, ev_raw):
    x = C["x"]; n = x.shape[0]
    bad, zero, peak = 0, 0, np.zeros(n)
    for a in range(0, n, 100):
        blk = np.asarray(x[a:a + 100])
        bad += int((~np.isfinite(blk)).any(axis=(1, 2, 3)).sum())
        zero += int((np.abs(blk).max(axis=(2, 3)) == 0).sum())
        peak[a:a + 100] = np.abs(blk[:, :, 3:]).max(axis=(1, 2, 3))
    fits = (ev_raw - HALF >= 0) & (ev_raw + HALF <= x.shape[-1])
    return dict(records_with_nonfinite_samples=bad, all_zero_cubicle_records=zero,
                inception_window_fits=int(fits.sum()), n=int(n), max_current_A_any_cubicle=q(peak, (0, 50, 99, 100)))


def window(x, k, rows, ev_raw):
    out = np.empty((len(rows), 6, 2 * HALF), np.float32)
    for i, r in enumerate(rows):
        out[i] = x[r, k, :, ev_raw[r] - HALF:ev_raw[r] + HALF]
    return out


def source_share(C, ev_raw, et, tgt):
    cubs, x = list(C["cubicles"]), C["x"]
    rows = np.where(np.char.find(et, "shc") >= 0)[0]
    src = dict(ibr=[c for c in cubs if "IBR" in c], trf=[c for c in cubs if "_Trf0-" in c])
    out, share_at = {}, {}
    for t in (20, 40):
        tot = {}
        for kind, cl in src.items():
            s = np.zeros(len(rows))
            for c in cl:
                s += phase_rise(window(x, cubs.index(c), rows, ev_raw), t)[0].clip(min=0)
            tot[kind] = s
        share = tot["ibr"] / np.maximum(tot["ibr"] + tot["trf"], 1e-9)
        share_at[t] = share
        out[f"{t}ms"] = dict(median=float(np.median(share)), p10=float(np.percentile(share, 10)),
                             p90=float(np.percentile(share, 90)),
                             by_type={ty: dict(n=int((et[rows] == ty).sum()), median=float(np.median(share[et[rows] == ty])))
                                      for ty in np.unique(et[rows])},
                             by_target_median={tg: float(np.median(share[tgt[rows] == tg])) for tg in np.unique(tgt[rows])})
    out["definition"] = ("largest-phase rise of the fundamental current (post window ending t ms after inception "
                         "against the cycle ending 20 ms before it), inverters / (inverters + 110/20 kV transformers)")
    return out, rows, share_at


def siblings_and_pow(C, L, ev_raw, et):
    tgt = L["events/event_target"].astype(str).to_numpy()
    loc = L["events/event_flt_target_line_location"].to_numpy(float)
    rf = L["events/event_flt_shc_resistance"].to_numpy(float)
    shc = np.char.find(et, "shc") >= 0
    key = np.array([f"{t}|{l:.6f}|{e}|{r:.6f}" for t, l, e, r in zip(tgt[shc], loc[shc], et[shc], rf[shc])])
    cubs = list(C["cubicles"]); k = cubs.index([c for c in cubs if "Trf0-1" in c][0])
    rows = np.arange(len(L))
    X = window(C["x"], k, rows, ev_raw)
    pre = X[:, :, HALF - 2 * SPC:HALF - SPC]
    h = np.array([hash(np.round(pre[i], 1).tobytes()) for i in range(len(rows))])
    va = dft(X[:, 0:1], HALF)[:, 0]
    return dict(shc_n=int(shc.sum()), shc_unique_label_keys=int(len(np.unique(key))),
                identical_prefault_cycles_at_substation=int(len(rows) - len(np.unique(h))),
                inception_pow_deg_phase_a=q(np.degrees(np.angle(va)) % 360.0, (0, 25, 50, 75, 100)))


def line_currents(C, ev_raw, rows):
    cubs = list(C["cubicles"]); samp = rows[:500]
    pre = {c: float(np.median(phase_rise(window(C["x"], cubs.index(c), samp, ev_raw), 20)[1]))
           for c in cubs if "_MainLn" in c}
    lines = {}
    for c in pre:
        lines.setdefault("MainLn" + c.split("_MainLn")[1], []).append(c)
    return pre, {ln: cl for ln, cl in lines.items() if len(cl) == 2}


def plot_waveforms(C, L, ev_raw, et):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cubs = list(C["cubicles"]); k = cubs.index([c for c in cubs if c.endswith("pex_MainBus3_MainLn3-4")][0])
    tgt = L["events/event_target"].astype(str).to_numpy(); rf = L["events/event_flt_shc_resistance"].to_numpy(float)
    picks = [("1phg R_f < 5 on 3-4", (et == "flt_1phg_shc") & (tgt == "MainLn3-4") & (rf < 5)),
             ("1phg R_f > 40 on 3-4", (et == "flt_1phg_shc") & (tgt == "MainLn3-4") & (rf > 40)),
             ("3ph on 3-4", (et == "flt_3ph_shc") & (tgt == "MainLn3-4")),
             ("inverter trip", et == "switch_ibr_trip"), ("motor start", et == "switch_motor_start"),
             ("capacitor on", et == "switch_cap_on")]
    fig, ax = plt.subplots(2, len(picks), figsize=(4 * len(picks), 6), sharex=True)
    t = (np.arange(2 * HALF) - HALF) / cm.FS * 1000
    for j, (lab, m) in enumerate(picks):
        r = np.where(m)[0]
        if not len(r):
            continue
        X = window(C["x"], k, r[:1], ev_raw)[0]
        for p in range(3):
            ax[0, j].plot(t, X[p] / 1e3, lw=0.8); ax[1, j].plot(t, X[3 + p], lw=0.8)
        ax[0, j].set_title(f"{lab}\n(sim {r[0]})", fontsize=9)
        for i in (0, 1):
            ax[i, j].axvline(0, color="grey", lw=0.6, ls=":"); ax[i, j].set_xlim(-40, 60)
    ax[0, 0].set_ylabel("voltage, kV"); ax[1, 0].set_ylabel("current, A")
    for j in range(len(picks)):
        ax[1, j].set_xlabel("ms from event")
    fig.suptitle("adapt_grid-CigreMVGrid, bus-3 end of line 3-4 (inverter at bus 3), raw primary quantities", fontsize=10)
    fig.tight_layout(); fig.savefig(PNG, dpi=110); plt.close(fig)


# ------------------------------------------------------------------ candidate relays
def candidate_cfg(line, bus, G, cubs, loads):
    ends = [c for c in cubs if c.endswith(f"_{line}")]
    here = [c for c in ends if f"pex_{bus}_" in c][0]
    remote = [c for c in ends if c != here]
    u, v = [(a, b) for a, b, k in G.edges(keys=True) if k == line][0]
    rbus = v if u == bus else u
    beyond = [str(k) for a, b, k in G.edges(keys=True) if rbus in (a, b) and str(k).startswith("MainLn") and k != line]
    return dict(cache_glob=GLOB, title=f"CIGRE MV {line} at {bus}", relay=here, line=line, remote_bus=str(rbus),
                beyond=beyond, parallel=None, ibr_cubicles=[c for c in cubs if "IBR" in c], adaptgrid=True,
                remote_cubicle=remote[0] if remote else None, loads=loads, relay_bus=bus, vn_kv=VN_KV)


def h25(R, idx, y, groups, a, b, seed=0):
    X = R["full"][idx][:, :, a:b].reshape(len(idx), -1)
    s = np.zeros(len(idx))
    for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(X, y, groups):
        s[te] = HistGradientBoostingClassifier(random_state=seed).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return float(roc_auc_score(y, s))


def sir(R):
    rb = np.where(R["remote_bus_faults"])[0]
    if not len(rb):
        return None
    vpre, vpost, ipre, ipost = cm.phasors_at(R, rb, 20, "full", True)
    va, vb, vc = cm._phase_q(vpost).T
    et, ph, rf = R["et"][rb], R["phase"][rb], R["rf"][rb]
    lg = np.char.find(et, "1phg") >= 0; ll = np.char.find(et, "2ph") >= 0
    vln = {"a": va, "b": vb, "c": vc}
    vloop = np.array([abs(vln[p][j]) if lg[j] else (abs(va[j] - vb[j]) if p == "ab" else abs(vb[j] - vc[j]) if p == "bc" else abs(vc[j] - va[j]))
                      for j, p in enumerate(ph)])
    vnom = np.where(lg, R["v_nom_peak"], R["v_nom_peak"] * np.sqrt(3))
    s = 1.0 / np.clip(vloop / vnom, 1e-3, None) - 1.0
    out = {}
    for lab, sel in (("R_f<=1", (lg | ll) & (rf <= 1)), ("R_f<=5", (lg | ll) & (rf <= 5))):
        out[lab] = dict(n=int(sel.sum()), **q(s[sel], (0, 25, 50, 75, 100)))
    out["R_f<=1_by_grounding_median"] = {g: (float(np.median(s[(lg | ll) & (rf <= 1) & (R["grounding"][rb] == g)]))
                                             if ((lg | ll) & (rf <= 1) & (R["grounding"][rb] == g)).any() else None)
                                         for g in ("solid", "resistive", "resonant")}
    return out


def relay_facts(name, share_rows, share_at):
    R = cm.load_relay(name)
    ev, n = R["ev"], len(R["et"])
    F = dict(relay=R["cfg"]["relay"], line=R["cfg"]["line"], remote_bus=R["cfg"]["remote_bus"], beyond=R["cfg"]["beyond"],
             behind=R["behind_lines"], line_z1_ohm=[R["z1L"].real, R["z1L"].imag], length_km=R["lp"]["length_km"],
             remote_end_cached=R["cfg"]["remote_cubicle"] is not None)
    F["classes"] = {k: int(R[k].sum()) for k in ("pos", "own99", "neg", "neg_bench", "beyond", "remote_bus_faults",
                                                  "reverse_bus", "reverse_lines", "other", "incipient", "switching")}
    own = R["pos"] | R["own99"]
    F["own_line_by_location_band"] = {f"{lo}-{hi}": int((own & (R["loc"] > lo) & (R["loc"] <= hi)).sum())
                                      for lo, hi in ((0, 20), (20, 50), (50, 80), (80, 85), (85, 100))}
    F["pos_by_rf_bin"] = {b: int((R["pos"] & (R["rf_bin"] == b)).sum()) for b in cm.RF_LABELS}
    F["pos_by_grounding"] = {g: int((R["pos"] & (R["grounding"] == g)).sum()) for g in ("solid", "resistive", "resonant")}
    F["pos_by_type"] = {t: int((R["pos"] & (R["et"] == t)).sum()) for t in np.unique(R["et"][R["pos"]])}
    F["op_bins"] = np.bincount(R["groups"]).tolist()
    idx = np.where(R["pos"] | R["neg"])[0]; y = R["pos"][idx].astype(int); g = R["groups"][idx]
    F["h25_prefault_auc"] = {"45..5 ms before inception": h25(R, idx, y, g, ev - 288, ev - 32),
                             "40 ms ending at inception": h25(R, idx, y, g, ev - 256, ev)} if y.sum() >= 10 else None
    F["sir_measured"] = sir(R)
    x_i = np.asarray(R["full"][:, 3:], dtype=np.float32)
    F["adc_clipping"] = {}
    for lab, fs_a in (("default chain +-40 x prefault peak", 40.0 * float(np.abs(x_i[:, :, :x_i.shape[-1] // 5]).max())),
                      ("relay front end +-141.4 kA", frontend.I_FS_ABS)):
        clipped = (np.abs(x_i[:, :, ev:]) >= fs_a * 0.999).any(axis=(1, 2))
        F["adc_clipping"][lab] = dict(full_scale_A=float(fs_a), sims_clipped=int(clipped.sum()), in_zone_clipped=int(clipped[R["pos"]].sum()))
    on_line = np.isin(share_rows, np.where(R["tgt"] == R["cfg"]["line"])[0])
    F["inverter_share_own_line_faults"] = {f"{t}ms": (float(np.median(share_at[t][on_line])) if on_line.any() else None) for t in (20, 40)}
    return F


def main():
    t0 = time.time()
    path = find_cache()
    C = load_cache(path)
    L, cubs, G = C["labels"], list(C["cubicles"]), C["graph"]
    ev_raw = np.rint((L["events/event_start"].to_numpy(dtype=float) - cm.T0_S) * C["fs"]).astype(int)
    et = L["events/event_type"].astype(str).to_numpy().astype(str)
    tgt = L["events/event_target"].astype(str).to_numpy().astype(str)
    res = dict(script="cigremv_facts", commit=cm.git_commit(), cache=os.path.basename(path), n_cubicles=len(cubs), cubicles=cubs,
               fs=C["fs"], nominal_kV=VN_KV)
    res["grid"] = graph_summary(G); print("grid done", flush=True)
    res["labels"] = label_facts(L, G); print("labels done", flush=True)
    res["integrity"] = integrity(C, ev_raw); print("integrity", res["integrity"], flush=True)
    res["siblings_and_inception"] = siblings_and_pow(C, L, ev_raw, et); print("siblings", res["siblings_and_inception"], flush=True)
    share, rows, share_at = source_share(C, ev_raw, et, tgt)
    res["inverter_share_of_fault_current_rise"] = share
    print("inverter share median 20/40 ms:", share["20ms"]["median"], share["40ms"]["median"], flush=True)
    pre, both = line_currents(C, ev_raw, rows)
    res["line_end_prefault_current_A_peak"] = pre
    res["lines_with_both_ends_cached"] = both
    plot_waveforms(C, L, ev_raw, et); print("waveforms", PNG, flush=True)
    frontend.enable()
    loads = res["labels"]["loading"]["loads"]
    res["candidates"] = {}
    for line, bus in CANDIDATES:
        name = f"cigre_{line.replace('MainLn', '')}_{bus.replace('MainBus', 'b')}"
        real_zone.CONFIGS[name] = candidate_cfg(line, bus, G, cubs, loads)
        f = relay_facts(name, rows, share_at)
        res["candidates"][name] = f
        cm._CACHE.pop(os.path.join(os.path.dirname(path), os.path.basename(path)), None)
        print(f"[{name}] pos {f['classes']['pos']} neg {f['classes']['neg']} rev {f['classes']['reverse_bus']}+{f['classes']['reverse_lines']} "
              f"h25 {f['h25_prefault_auc']} sir {None if f['sir_measured'] is None else f['sir_measured']['R_f<=1'].get('p50')} "
              f"inv share {f['inverter_share_own_line_faults']} [{time.time()-t0:.0f}s]", flush=True)
    res["runtime_s"] = float(time.time() - t0)
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    print("saved", OUT, f"[{res['runtime_s']:.0f}s]")


def write_md(path_json=OUT, path_md=OUT.replace(".json", ".md")):
    """results/CIGREMV_FACTS.md from the JSON; no number typed by hand."""
    d = json.load(open(path_json, encoding="utf-8"))
    lab, integ, sib, sh = d["labels"], d["integrity"], d["siblings_and_inception"], d["inverter_share_of_fault_current_rise"]
    o = ["# adapt_grid-CigreMVGrid: fact sheet", "",
         f"Generated by `src/review/cigremv_facts.py` from `results/CIGREMV_FACTS.json` (commit {d['commit'][:7]}); no number "
         "typed by hand. Read before choosing relays or fixing a protocol on this grid.", "", "## Data", "",
         f"- **{lab['n_simulations']} simulations, {d['n_cubicles']} cubicles**, {d['nominal_kV']:.0f} kV, 50 Hz, cache `{d['cache']}`.",
         f"- **Integrity:** {integ['records_with_nonfinite_samples']} records with non-finite samples, "
         f"{integ['all_zero_cubicle_records']} all-zero cubicle records, inception window fits {integ['inception_window_fits']} of {integ['n']}.",
         f"- **Siblings:** {sib['shc_unique_label_keys']} unique (target, location, type, R_f) keys for {sib['shc_n']} short circuits; "
         f"{sib['identical_prefault_cycles_at_substation']} identical pre-fault cycles at the substation.",
         f"- **Inception point on wave** (phase a): p25/p50/p75 = {sib['inception_pow_deg_phase_a']['p25']:.0f}/"
         f"{sib['inception_pow_deg_phase_a']['p50']:.0f}/{sib['inception_pow_deg_phase_a']['p75']:.0f} deg.",
         f"- **Loading:** total P {lab['loading']['total_P_MW']['min']:.1f}–{lab['loading']['total_P_MW']['max']:.1f} MW "
         f"(×{lab['loading']['total_P_MW']['max_over_min']:.2f}) over {len(lab['loading']['loads'])} loads.",
         f"- **Grounding:** {lab['grounding']}.",
         f"- **Fault resistance (short circuits):** p5 {lab['fault_resistance_ohm_shc']['p5']:.1f} Ω, median "
         f"{lab['fault_resistance_ohm_shc']['p50']:.1f} Ω, max {lab['fault_resistance_ohm_shc']['p100']:.1f} Ω — near-bolted faults are rare.",
         f"- **Fault targets:** {lab['fault_targets_on_lines']} on lines, {lab['fault_targets_on_buses']} on buses; "
         f"missing from the graph: {lab['fault_targets_missing_from_graph'] or 'none'}.",
         f"- **Events:** {lab['event_type_counts']}.", "", "## Grid", "",
         f"- Inverters: {d['grid']['inverters']}.", f"- External grid: {d['grid']['ext_grid']}.",
         "- Line-end cubicles with (almost) no pre-fault current (open ties): " +
         ", ".join(f"`{c}`" for c, v in d["line_end_prefault_current_A_peak"].items() if v < 1.0) + ".", "",
         "| line | buses | length km | Z1 (Ω) |", "|---|---|---|---|"]
    for ln, v in sorted(d["grid"]["lines"].items()):
        z = v.get("z1_ohm", [float("nan")] * 2)
        o.append(f"| {ln} | {' – '.join(v['buses'])} | {v.get('length_km', float('nan')):.2f} | {z[0]:.2f} + j{z[1]:.2f} |")
    o += ["", "## Sources", "", f"Inverter share of the fault-current rise ({sh['definition']}):", "",
          "| | median | p10 | p90 |", "|---|---|---|---|"]
    for t in ("20ms", "40ms"):
        o.append(f"| {t} | {100*sh[t]['median']:.1f} % | {100*sh[t]['p10']:.1f} % | {100*sh[t]['p90']:.1f} % |")
    o += ["", "## Candidate relays", "",
          "| candidate | line | length km | pos | own 85–100 % | off-line | reverse bus / lines | pos R_f <5/5–15/15–40/>40 | H25 AUC (40 ms at inception) | SIR, R_f ≤ 5 (n, median) | inverter share, own-line faults 20/40 ms |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, c in d["candidates"].items():
        k = c["classes"]; rf = c["pos_by_rf_bin"]; s = c["sir_measured"] or {}
        s5 = s.get("R_f<=5", {}); inv = c["inverter_share_own_line_faults"]
        h = c["h25_prefault_auc"]["40 ms ending at inception"] if c["h25_prefault_auc"] else float("nan")
        o.append(f"| {n} | {c['line']} | {c['length_km']:.2f} | {k['pos']} | {k['own99']} | {k['neg']} | {k['reverse_bus']} / {k['reverse_lines']} | "
                 f"{rf['<5']}/{rf['5-15']}/{rf['15-40']}/{rf['>40']} | {h:.2f} | {s5.get('n', 0)}, {s5.get('p50', float('nan')):.2f} | "
                 f"{100*inv['20ms']:.0f} / {100*inv['40ms']:.0f} % |")
    o += ["", "![waveforms](cigremv_waveforms.png)", ""]
    open(path_md, "w", encoding="utf-8").write("\n".join(o))
    print("saved", path_md)


def plot_only():
    C = load_cache(find_cache()); L = C["labels"]
    ev_raw = np.rint((L["events/event_start"].to_numpy(dtype=float) - cm.T0_S) * C["fs"]).astype(int)
    plot_waveforms(C, L, ev_raw, L["events/event_type"].astype(str).to_numpy().astype(str))
    print("saved", PNG)


if __name__ == "__main__":
    if "--md-only" in sys.argv:
        write_md()
    elif "--plot-only" in sys.argv:
        plot_only()
    else:
        main()
        write_md()
