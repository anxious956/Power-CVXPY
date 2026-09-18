"""The fixed conventional rungs on adapt_grid-TestGrid110kV, at the protection-practice R_f bands.

R0-R4 and the 67N/67Q reference have no threshold and no fold: one frozen setting, evaluated once.
They are separated from ladder.py's full run (tilt sweep, operating curves, tuned rungs) so that the
rule side of results/ADAPTGRID.md can be regenerated in a couple of minutes; the tuned rungs T1 and
T2 come from adaptgrid_run.py, which reads them at the same four operating points as the learned
models.

    python src/review/adaptgrid_rules.py adapt_A adapt_B [--frontend relayfe]
    -> results/adaptgrid/rules_<relay>_<frontend>.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import ladder as ld
from review import frontend
from review.adaptgrid_run import bundle, settable_summary, comm_reference, rates_plus, T
from review.zone_cv import zone_task

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("relays", nargs="+", choices=["adapt_A", "adapt_B"])
    ap.add_argument("--frontend", choices=["current", "relayfe"], default="relayfe")
    a = ap.parse_args()
    if a.frontend == "relayfe":
        frontend.enable()
    commit = cm.git_commit()
    os.makedirs(OUT, exist_ok=True)
    for name in a.relays:
        t0 = time.time()
        R = bundle(name, None)
        n = len(R["et"]); sel = np.arange(n)
        idx, y, _ = zone_task(R)
        ok = np.ones(n, bool)
        P0 = ld.pack(R, sel, T, "full", False)
        P1 = ld.pack(R, sel, T, "full", True)
        fixed = {}
        for rung in ("R0", "R1", "R2", "R3", "R4"):
            trip = ld.evaluate_block(R, *(P0 if rung == "R0" else P1), R["S"], rung)[0]
            fixed[rung] = rates_plus(trip, R, sel, idx, y, ok)
            r = fixed[rung]
            print(f"  [{name} {a.frontend}] {rung}: dep {r['pos']['rate']*100:5.1f}  off-line {r['neg']['dedup']['k']}/{r['neg']['dedup']['n']} "
                  f"(<={r['neg']['dedup']['ucb95']*100:4.1f})  guard {r['own99']['rate']*100:5.1f}  switching {r['switching']['rate']*100:5.1f}  "
                  f"settable in/out {r['settable']['inside']['k']}/{r['settable']['inside']['n']} {r['settable']['outside']['k']}/{r['settable']['outside']['n']}", flush=True)
        f67n, f67q = ld.ground_overcurrent(R, *P1)
        for lab, tr in (("67N", f67n), ("67Q", f67q), ("67N or 67Q", f67n | f67q)):
            fixed[lab] = rates_plus(tr, R, sel, idx, y, ok)
            r = fixed[lab]
            print(f"  [{name} {a.frontend}] {lab:11s}: dep {r['pos']['rate']*100:5.1f}  off-line {r['neg']['dedup']['k']}/{r['neg']['dedup']['n']}  "
                  f"switching {r['switching']['rate']*100:5.1f}", flush=True)
        res = dict(relay=name, frontend=a.frontend, commit=commit, t_ms=T, rf_bins=list(cm.RF_LABELS),
                   settings={k: (v if not isinstance(v, np.generic) else float(v)) for k, v in R["S"].items()},
                   fixed=fixed, settable=settable_summary(R), reference_comm=comm_reference(name, None),
                   runtime_s=float(time.time() - t0))
        path = os.path.join(OUT, f"rules_{name}_{a.frontend}.json")
        json.dump(res, open(path, "w"), indent=1, default=str)
        print(f"saved {path}  [{res['runtime_s']:.0f}s]", flush=True)
