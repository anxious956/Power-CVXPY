"""Two diagnostics of the CNN seq-traj result on the CIGRE MV relays, from the scores adaptgrid_run.py saved.

1. Can the zone boundary be seen from one end? In-zone faults against the off-line faults nearest the boundary
   (remote bus and the first stretch of the lines beyond), within each fault-resistance band.

A detector's overall AUC mixes the boundary with every easy far fault. Within one R_f band both classes carry
the same resistance, so a poor AUC there is not resistance hiding the location: the location itself is not in
the relay's measurement at the resolution zone 1 needs.

2. Which switching events trip it at the protection-grade threshold (cal0, held-out rows by fold majority, as in
   adaptgrid_run.py), by event type and target, and how many of them 32P/32Q calls forward.

Reads the scores adaptgrid_run.py saved (logs/scores/adaptgrid/<relay>_relayfe/, CNN seq-traj, matched chain,
loading-bin folds); needs the relay caches. TestGrid relays are included for comparison.

    python src/review/cigremv_diagnostics.py        -> results/cigremv/diagnostics.json
"""
import os, sys, glob, json, collections
import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from review import common as cm
from review.adaptgrid_run import bundle

RELAYS = ("adapt_A", "adapt_B", "cigre_R1", "cigre_R2", "cigre_R3", "cigre_R4")
BANDS = ((0, 5, "<5"), (5, 15, "5-15"), (15, 40, "15-40"), (40, np.inf, ">40"))
MODEL = "CNN seq-traj"
OUT = os.path.join(cm.ROOT, "results", "cigremv", "diagnostics.json")


def saved_scores(relay):
    for f in glob.glob(os.path.join(cm.ROOT, "logs", "scores", "adaptgrid", f"{relay}_relayfe", "*.npz")):
        z = np.load(f, allow_pickle=True)
        c = json.loads(str(z["config"]))
        if c["model"] == MODEL and c["split"] == "grouped" and c["chains"] == "matched":
            return z, str(z["commit"])
    raise FileNotFoundError(f"no saved {MODEL} scores for {relay}: run adaptgrid_run.py {relay} --frontend relayfe")


def auc(zp, zn):
    if not len(zp) or not len(zn):
        return None
    return float(roc_auc_score(np.r_[np.ones(len(zp)), np.zeros(len(zn))], np.r_[zp, zn]))


def relay_summary(relay):
    R = bundle(relay, None)
    z, commit = saved_scores(relay)
    idx, y, Z = z["idx"], z["y"], z["zone_matched"]
    pos, neg = idx[y == 1], idx[y == 0]
    near = neg[(R["remote_bus_faults"] | R["beyond"])[neg]]
    out = dict(scores_commit=commit, z1L_abs_ohm=float(abs(R["z1L"])), x_line_ohm=float(R["z1L"].imag),
               rf_median_in_zone=float(np.median(R["rf"][pos])), n_pos=int(len(pos)), n_near=int(len(near)),
               auc_all_offline=auc(Z[pos], Z[neg]), auc_near=auc(Z[pos], Z[near]),
               above_highest_offline=dict(k=int((Z[pos] > Z[neg].max()).sum()), n=int(len(pos))), by_rf_band={})
    for lo, hi, lab in BANDS:
        p = pos[(R["rf"][pos] >= lo) & (R["rf"][pos] < hi)]
        n = near[(R["rf"][near] >= lo) & (R["rf"][near] < hi)]
        out["by_rf_band"][lab] = dict(n_pos=int(len(p)), n_near=int(len(n)), auc=auc(Z[p], Z[n]),
                                      above_highest_near=int((Z[p] > Z[n].max()).sum()) if len(n) else None)
    hrows, trip = z["hrows"], np.mean(z["held_matched"] > z["thr_cal0"][:, None], axis=0) >= 0.5
    sw = hrows[trip & R["switching"][hrows]]
    out["switching_trips_cal0"] = dict(
        k=int(len(sw)), n=int(R["switching"].sum()), forward_32=int(z["fwd"][sw].sum()),
        by_event_target={f"{e}|{t}": int(c) for (e, t), c in collections.Counter(zip(R["et"][sw], R["tgt"][sw])).most_common()},
        events_of_that_kind={f"{e}|{t}": int(((R["et"] == e) & (R["tgt"] == t)).sum()) for e, t in set(zip(R["et"][sw], R["tgt"][sw]))})
    return out


def main():
    res = dict(script="cigremv_diagnostics", commit=cm.git_commit(), model=MODEL, split="grouped", chain="matched",
               near="remote_bus_faults | beyond", relays={})
    for relay in RELAYS:
        res["relays"][relay] = r = relay_summary(relay)
        b = " | ".join(f"{k}: {v['auc'] if v['auc'] is None else round(v['auc'], 3)} ({v['n_pos']}/{v['n_near']})"
                       for k, v in r["by_rf_band"].items())
        print(f"[{relay}] |Z1L| {r['z1L_abs_ohm']:.2f} ohm, AUC all {r['auc_all_offline']:.3f}, near {r['auc_near']:.3f}; {b}",
              flush=True)
        s = r["switching_trips_cal0"]
        print(f"    switching trips at cal0 {s['k']}/{s['n']} (32P/32Q forward {s['forward_32']}): {s['by_event_target']} "
              f"of {s['events_of_that_kind']}", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=1)
    print("saved", OUT)


if __name__ == "__main__":
    main()
