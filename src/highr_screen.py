"""
Where does conventional detection fail as the fault resistance grows? A static screen on the step-3 three-bus network
(synchronous source at the relay bus) before any high-resistance EMT work (results/STEP3_PILOT.md, option C; the
80-ohm design needs about 1 pu of signal even at the design tier). For A-G faults at the design's locations and
R_f = 40 ... 400 ohm: what the relay's incremental elements see at nominal sources, the worst over the corners of the
source box, and whether that clears the pilot's calibrated pickup (D0, incremental 50N / 50Q: 0.126-0.162 pu at
the design tier, results/step3/pilot_eval.json and multiplicative_pilot.json).

    python src/highr_screen.py      -> results/network/highr_screen.json
"""
import os, sys, json, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
from pscad_network import three_bus

OUT = os.path.join(HERE, "..", "results", "network", "highr_screen.json")
RF_OHM = (40, 80, 120, 160, 200, 300, 400)
LOCS = [("L1", m) for m in (0.15, 0.35, 0.55, 0.75, 0.95)] + [("L2", m) for m in (0.05, 0.25, 0.5)]
PICKUP = 0.162


def main():
    net = three_bus()
    zb = 40.0                                          # ohm per unit of rF (rF = 1 pu = 40 ohm)
    corners = list(itertools.product((-1, 1), repeat=2 * len(net.sources)))
    res = {}
    for rf in RF_OHM:
        rows = []
        for ln, m in LOCS:
            vals = []
            for u in corners:
                v = nw.realisation(net, u)
                yN = nw.solve(net, v)
                y = nw.solve(net, v, fault=(ln, m, "ag", rf / zb * net.rF))
                vals.append(max(3 * abs(y[5] - yN[5]), abs(y[4] - yN[4])))
            yN = nw.solve(net)
            y = nw.solve(net, fault=(ln, m, "ag", rf / zb * net.rF))
            rows.append(dict(loc=[ln, m], nominal=float(max(3 * abs(y[5] - yN[5]), abs(y[4] - yN[4]))),
                             worst_corner=float(min(vals))))
        res[str(rf)] = dict(rows=rows, min_nominal=min(r["nominal"] for r in rows), min_worst=min(r["worst_corner"] for r in rows),
                            n_below_pickup=sum(r["worst_corner"] <= PICKUP for r in rows))
        print(f"R_f {rf:3d} ohm: D0 score (max(3|dI0|, |dI2|)) at the relay, A-G: nominal min {res[str(rf)]['min_nominal']:.3f}, "
              f"worst source corner min {res[str(rf)]['min_worst']:.3f} pu; locations below the {PICKUP} pu pickup: "
              f"{res[str(rf)]['n_below_pickup']} of {len(LOCS)}", flush=True)
    json.dump(dict(pickup=PICKUP, results=res), open(OUT, "w"), indent=1)
    print("-> results/network/highr_screen.json")


if __name__ == "__main__":
    main()
