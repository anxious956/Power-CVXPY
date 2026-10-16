"""
Impact of the faulted-phase selector change (magnitude -> angle, 16 Oct 2026) on the current
results: for each relay, the share of records whose released loops differ, and the zone-1 decision
of the plain reactance rule with each selector, on in-zone faults and on every off-line fault.

    EVEMT_CACHE_DIRS=D:\\evemt\\cache python src/review/selector_impact.py adapt_A adapt_B cigre_R1 cigre_R2 cigre_R3 cigre_R4

Writes results/review/selector_impact.json. This decides which earlier results must be re-run: a relay
whose decisions do not change needs no re-run.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import common as cm

T_MS = 20


def impact(name):
    R = cm.load_relay_adapt(name)
    idx = np.where(R["pos"] | R["neg"])[0]
    vpre, vpost, ipre, ipost = cm.phasors_at(R, idx, T_MS)
    Lp = cm.loops(R, vpost, ipost, vpre, ipre)
    out = dict(relay=name, t_ms=T_MS, n=int(len(idx)))
    trips = {}
    for sel in ("magnitude", "angle"):
        mask = cm.phase_selection(ipre, ipost, selector=sel)
        x, _ = cm.rule_reactance(Lp, mask)
        trips[sel] = (x < R["x_reach"], mask)
    differ = (trips["angle"][1] != trips["magnitude"][1]).any(1)
    pos = R["pos"][idx]
    out.update(released_loops_differ=round(float(differ.mean()) * 100, 2),
               released_loops_differ_in_zone=round(float(differ[pos].mean()) * 100, 2))
    for sel in ("magnitude", "angle"):
        t = trips[sel][0]
        out[sel] = dict(in_zone_trip_pct=round(float(t[pos].mean()) * 100, 2), in_zone_n=int(pos.sum()),
                        offline_trips=int(t[~pos].sum()), offline_n=int((~pos).sum()))
    out["decisions_changed"] = int((trips["angle"][0] != trips["magnitude"][0]).sum())
    return out


if __name__ == "__main__":
    res = []
    for name in sys.argv[1:]:
        r = impact(name)
        res.append(r)
        m, a = r["magnitude"], r["angle"]
        print(f"{name}: loops differ on {r['released_loops_differ']:.1f} % of records ({r['released_loops_differ_in_zone']:.1f} % "
              f"of in-zone); in-zone trips {m['in_zone_trip_pct']:.1f} -> {a['in_zone_trip_pct']:.1f} % of {m['in_zone_n']}; "
              f"off-line trips {m['offline_trips']} -> {a['offline_trips']} of {m['offline_n']}; "
              f"decisions changed {r['decisions_changed']}", flush=True)
    out = os.path.join(cm.ROOT, "results", "review", "selector_impact.json")
    json.dump(res, open(out, "w"), indent=1)
    print("wrote", out)
