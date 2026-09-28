"""Fact sheet for adapt_grid-CigreMVGrid: is this the inverter-rich data the project needs, and which lines
can carry a relay?

Reads the cache built by src/build_cigremv_cache.py (every cubicle, 9,906 simulations; found through
EVEMT_CACHE_DIRS or data/). Reports:
  grid        buses, lines, transformers, inverters and the external grid from the shipped graph
  labels      which columns vary, event counts, fault location / resistance / grounding ranges, loading
  sources     the inverters' share of fault current, MEASURED: for every short circuit, the rise of the
              fundamental phase current (largest phase, full-cycle DFT, post window ending t ms after
              inception against the cycle ending 20 ms before it) at the two inverter cubicles and at the
              two 110/20 kV transformer cubicles on the 20 kV side, which between them are every source;
              share = inverter rise / (inverter rise + transformer rise), at 20 and 40 ms
  lines       pre-fault current at each line-end cubicle (a normally-open tie carries none) and which lines
              have a cubicle at both ends (candidate relays with a remote-end reference)

    set EVEMT_CACHE_DIRS=D:\\evemt\\cache
    python src/review/cigremv_facts.py
    -> results/CIGREMV_FACTS.json
"""
import os, sys, json, glob, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from evemt import load_cache
from review import common as cm

OUT = os.path.join(cm.ROOT, "results", "CIGREMV_FACTS.json")
GLOB = "adapt_grid-CigreMVGrid*_cache.meta.npz"
HALF = cm.ADAPT_HALF
SPC = cm.SPC


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
    """X (m, 6, 2*HALF) re-anchored at inception = HALF; largest-phase rise of |I| (A, peak)."""
    pre = np.abs(dft(X[:, 3:], HALF - SPC))
    post = np.abs(dft(X[:, 3:], HALF + int(round(t_ms * cm.FS / 1000))))
    return (post - pre).max(axis=1), pre.max(axis=1)


def graph_summary(G):
    nodes = {}
    for n, a in G.nodes(data=True):
        nodes[str(n)] = {k: v for k, v in a.items() if not k.endswith("cntrlFMUIBRController_param_dict")}
    ibr = {}
    for n, a in G.nodes(data=True):
        for k, v in a.items():
            if k.endswith("cntrlFMUIBRController_param_dict"):
                ibr[str(n)] = dict(Sn_MVA=v.get("Sn", 0) / 1e6, Imax_pu=v.get("Imax"), P_FLAG=v.get("P_FLAG"),
                                   Q_FLAG=v.get("Q_FLAG"), IqV_FLAG=v.get("IqV_FLAG"))
    edges = []
    for u, v, k, a in G.edges(keys=True, data=True):
        edges.append(dict(u=str(u), v=str(v), key=str(k),
                          params={pk: {kk: vv for kk, vv in pv.items() if not isinstance(vv, (list, dict))}
                                  for pk, pv in a.items() if isinstance(pv, dict)}))
    return dict(n_nodes=G.number_of_nodes(), n_edges=G.number_of_edges(), inverters=ibr, edges=edges,
                ext_grid={str(n): a.get("ExtGrid_param_dict") for n, a in G.nodes(data=True) if "ExtGrid_param_dict" in a})


def main():
    t0 = time.time()
    path = find_cache()
    C = load_cache(path)
    L, cubs, x = C["labels"], list(C["cubicles"]), C["x"]
    n = len(L)
    ev_raw = np.rint((L["events/event_start"].to_numpy(dtype=float) - cm.T0_S) * C["fs"]).astype(int)
    et = L["events/event_type"].astype(str).to_numpy()
    tgt = L["events/event_target"].astype(str).to_numpy()
    shc = np.char.find(et.astype(str), "shc") >= 0

    def window(k, rows):
        out = np.empty((len(rows), 6, 2 * HALF), np.float32)
        for i, r in enumerate(rows):
            out[i] = x[r, k, :, ev_raw[r] - HALF:ev_raw[r] + HALF]
        return out

    src = dict(ibr=[c for c in cubs if "IBR" in c], trf=[c for c in cubs if "_Trf0-" in c])
    rows = np.where(shc)[0]
    rise = {}
    for t in (20, 40):
        tot = {}
        for kind, cl in src.items():
            s = np.zeros(len(rows))
            for c in cl:
                s += phase_rise(window(cubs.index(c), rows), t)[0].clip(min=0)
            tot[kind] = s
        share = tot["ibr"] / np.maximum(tot["ibr"] + tot["trf"], 1e-9)
        by_type = {ty: dict(n=int((et[rows] == ty).sum()),
                            median=float(np.median(share[et[rows] == ty])),
                            p90=float(np.percentile(share[et[rows] == ty], 90)))
                   for ty in np.unique(et[rows])}
        by_target = {tg: float(np.median(share[tgt[rows] == tg])) for tg in np.unique(tgt[rows])}
        rise[f"{t}ms"] = dict(median=float(np.median(share)), p10=float(np.percentile(share, 10)),
                              p90=float(np.percentile(share, 90)), max=float(share.max()),
                              by_type=by_type, by_target_median=by_target)
        print(f"inverter share of fault-current rise at {t} ms: median {100*np.median(share):.1f} %, "
              f"p10-p90 {100*np.percentile(share,10):.1f}-{100*np.percentile(share,90):.1f} %, max {100*share.max():.1f} %",
              flush=True)
    # pre-fault current at every line-end cubicle (median over switching-free fault records)
    line_cubs = [c for c in cubs if "_MainLn" in c]
    samp = rows[:500]
    pre_i = {}
    for c in line_cubs:
        pre_i[c] = float(np.median(phase_rise(window(cubs.index(c), samp), 20)[1]))
    lines = {}
    for c in line_cubs:
        ln = c.split("_MainLn")[1]
        lines.setdefault("MainLn" + ln, []).append(c)
    both = {ln: cl for ln, cl in lines.items() if len(cl) == 2}
    varying = [c for c in L.columns if L[c].nunique() > 1]
    rng = lambda col: [float(L[col].min()), float(L[col].max())] if col in L else None
    res = dict(script="cigremv_facts", commit=cm.git_commit(), cache=os.path.basename(path), n_simulations=int(n),
               n_cubicles=len(cubs), cubicles=cubs, fs=C["fs"],
               labels=dict(varying=varying, event_counts=L["events/event_type"].value_counts().to_dict(),
                           fault_location_pct=rng("events/event_flt_target_line_location"),
                           shc_resistance_ohm=rng("events/event_flt_shc_resistance"),
                           grounding=L["grounding/grnd_type"].value_counts().to_dict() if "grounding/grnd_type" in L else None,
                           ext_grid_usetp=rng("ExtGrid/usetp"),
                           shc_targets=pd_counts(tgt[shc])),
               grid=graph_summary(C["graph"]),
               inverter_share_of_fault_current_rise=rise,
               line_end_prefault_current_A_peak=pre_i,
               lines_with_both_ends_cached=both)
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    print("lines with both ends cached:", sorted(both))
    print("line ends with (near) zero pre-fault current:", [c for c, v in pre_i.items() if v < 1.0])
    print("saved", OUT, f"[{time.time()-t0:.0f}s]")


def pd_counts(a):
    u, c = np.unique(a, return_counts=True)
    return {str(k): int(v) for k, v in zip(u, c)}


if __name__ == "__main__":
    main()
