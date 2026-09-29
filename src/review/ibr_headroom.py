"""Is there room in the inverter for an auxiliary signal during a fault? (docs/notes/SORULAR_CEVAPLAR.md Q22, H2)

The project's idea is that the inverter injects a small negative-sequence current delta during a fault so
the relay can separate in-zone from out-of-zone faults. A grid-following inverter's phase current is capped
(Imax = 1.2 pu of its rating on this grid), and during a fault it is already delivering current. What is
left for delta is measured here from the inverters' own cubicles on every short circuit, at the relay's
decision time and later.

Per short circuit and inverter, from the fundamental of the recorded currents (one-cycle DFT ending t ms after
inception, the same DFT as ibr_study.characterise), in pu of the inverter's rating:

  i_phase_max          the largest phase current
  at_limit             i_phase_max >= 0.95 Imax
  headroom_strict      Imax - i_phase_max: a delta of this size fits at ANY angle with the present output
                       kept (|I_k + a^k delta| <= |I_k| + |delta|), a lower bound on what is available
  headroom_reactive    Imax - the largest phase current with the active part of the positive sequence removed:
                       what fits if the inverter gives up active current (the limiter's own priority) and keeps
                       its reactive support and negative-sequence response; an extreme, not a design case
  fits_by_angle        with the output kept, whether delta = d e^{j phi} (negative sequence, in the frame of the
                       inverter's positive-sequence voltage) keeps every phase within Imax, on a 5-degree phi grid:
                         any_angle   fits at every phi (the exact form of headroom_strict >= d)
                         fixed_angle the one phi that fits the most faults of the set, and that share (the phi is
                                     chosen on the set it is read on: a design angle, mildly optimistic)
                         best_angle  fits at some phi, chosen per fault (an upper bound)
                       The design chooses delta's angle, so any_angle alone understates what a designed delta can
                       use (bridge review, review/bridge/LEAD_REVIEW.md).

All of it is static: the recorded currents plus delta, with the inverter's own response to delta (its
negative-sequence control, its limiter) ignored. And a one-cycle window ending 20 ms after inception is the
inception transient, not a steady state; 40 and 60 ms are the fairer reads for a triggered injection.

Read against the toy design's delta, 0.39-1.32 pu for the ambiguous presets (README.md table; the toy's
current base puts the inverter's nominal current at 0.9 pu, so the comparison is indicative, not exact).

The fault sets are all short circuits, and for the relay at each inverter bus (R1 at bus 3, R3 at bus 14) its
in-zone faults and the off-line faults nearest its boundary (remote bus and lines beyond), the faults a
signal would have to separate.

    python src/review/ibr_headroom.py        -> results/cigremv/ibr_headroom.json
"""
import os, sys, glob, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from review import common as cm

OUT = os.path.join(cm.ROOT, "results", "cigremv", "ibr_headroom.json")
TIMES_MS = (20, 40, 60)
RELAY_AT = {"Bus3IBR": "cigre_R1", "Bus14IBR": "cigre_R3"}
DELTA_REF = (0.4, 0.7, 1.0)                         # toy-design delta levels the headroom is read against
A = np.exp(2j * np.pi / 3)


def dft(X, end):
    n = np.arange(end - cm.SPC, end)
    return (2.0 / cm.SPC) * (X[..., end - cm.SPC:end].astype(float) @ np.exp(-2j * np.pi * n / cm.SPC))


def phases(i1, i2):
    return np.stack([i1 + i2, A**2 * i1 + A * i2, A * i1 + A**2 * i2], axis=-1)


def summary(v, imax):
    v = np.asarray(v, float)
    if not len(v):
        return None
    return dict(n=int(len(v)), median=float(np.median(v)), p10=float(np.percentile(v, 10)), p90=float(np.percentile(v, 90)),
                **{f"share_ge_{d:g}": float(np.mean(v >= d)) for d in DELTA_REF})


PHI = np.deg2rad(np.arange(0, 360, 5))


def fits_by_angle(i1, i2, imax):
    """Output kept, delta = d e^{j phi} added to the negative sequence: share of faults that fit at every phi,
    at the best single phi for the set (and that phi), and at the best phi per fault."""
    if not len(i1):
        return None
    out = {}
    for d in DELTA_REF:
        dl = d * np.exp(1j * PHI)[None, :]                                           # (1, n_phi)
        peak = np.abs(phases(i1[:, None], i2[:, None] + dl)).max(-1)                 # (n, n_phi)
        fit = peak <= imax
        share = fit.mean(0)
        out[f"{d:g}"] = dict(any_angle=float(fit.all(1).mean()), fixed_angle=float(share.max()),
                             fixed_angle_deg=float(np.degrees(PHI[share.argmax()])), best_angle=float(fit.any(1).mean()))
    return out


def main():
    from evemt import load_cache
    from review.adaptgrid_run import bundle
    path = [h for d in cm.CACHE_DIRS for h in sorted(glob.glob(os.path.join(d, "adapt_grid-CigreMVGrid*_cache.meta.npz")))][0]
    C = load_cache(path); L = C["labels"]; G = C["graph"]; cubs = list(C["cubicles"]); x = C["x"]
    ev = np.rint((L["events/event_start"].to_numpy(float) - cm.T0_S) * C["fs"]).astype(int)
    et = L["events/event_type"].astype(str).to_numpy().astype(str)
    shc = np.where(np.char.find(et, "shc") >= 0)[0]
    res = dict(script="ibr_headroom", commit=cm.git_commit(), times_ms=list(TIMES_MS), delta_ref_pu=list(DELTA_REF),
               convention="fundamental phasors, pu of the inverter's rating (peak), currents injected into the grid",
               inverters={})
    for n, a in G.nodes(data=True):
        ctl = next((v for k, v in a.items() if k.endswith("cntrlFMUIBRController_param_dict")), None)
        if ctl is None:
            continue
        name = str(n)
        busnum = name.replace("Bus", "").replace("IBR", "")
        k = cubs.index([c for c in cubs if "IBR" in c and f"MainBus{busnum}_" in c][0])
        ib, imax = float(ctl["I_base"]), float(ctl.get("Imax", 1.2))
        R = bundle(RELAY_AT[name], None)
        assert np.array_equal(R["et"], et), "bundle rows are not the cache rows"
        sets = {"all short circuits": np.ones(len(shc), bool),
                f"{RELAY_AT[name]} in-zone": R["pos"][shc],
                f"{RELAY_AT[name]} near boundary (remote bus + first 20 % beyond)": R["neg_bench"][shc]}
        X = np.stack([x[r, k, :, ev[r] - cm.ADAPT_HALF:ev[r] + cm.ADAPT_HALF] for r in shc])
        out = res["inverters"][name] = dict(relay_at_bus=RELAY_AT[name], i_max_pu=imax, n_short_circuits=int(len(shc)), by_time={})
        for t in TIMES_MS:
            end = cm.ADAPT_HALF + int(round(t * cm.FS / 1000))
            V = dft(X[:, :3], end) @ cm.BM.T                       # sequence components 0, 1, 2
            I = -(dft(X[:, 3:], end) @ cm.BM.T)
            ref = V[:, 1] / np.maximum(np.abs(V[:, 1]), 1e-9)     # positive-sequence voltage angle
            i1, i2 = I[:, 1] / ref / ib, I[:, 2] / ref / ib
            iph = np.abs(-(dft(X[:, 3:], end))).max(1) / ib
            react = np.abs(phases(1j * i1.imag, i2)).max(1)       # active part of i1 removed
            per = {}
            for lab, m in sets.items():
                per[lab] = dict(n=int(m.sum()), at_limit=float(np.mean(iph[m] >= 0.95 * imax)) if m.any() else None,
                                i_phase_max=summary(iph[m], imax),
                                headroom_strict=summary(np.maximum(imax - iph[m], 0), imax),
                                headroom_reactive=summary(np.maximum(imax - react[m], 0), imax),
                                fits_by_angle=fits_by_angle(i1[m], i2[m], imax))
            out["by_time"][str(t)] = per
            for lab, p in per.items():
                if p["n"]:
                    hs, fa = p["headroom_strict"], p["fits_by_angle"]
                    ang = "  ".join(f"{d} pu any/fixed/best {100 * v['any_angle']:4.1f}/{100 * v['fixed_angle']:4.1f}/{100 * v['best_angle']:4.1f} %"
                                    for d, v in fa.items())
                    print(f"[{name} {t} ms] {lab:50s} n {p['n']:4d}  at limit {100 * p['at_limit']:5.1f} %  "
                          f"strict median {hs['median']:.2f}  | output kept: {ang}", flush=True)
        del R, X
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=1)
    print("saved", OUT)


if __name__ == "__main__":
    main()
