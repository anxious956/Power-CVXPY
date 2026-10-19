"""
Stage (b1) follow-up asked for in review: dead frames (any source bus |V1| < v1_min at some sample point) at each
tier's delta* and every separating angle there, and at the 1.14 pu cap at the same angles. If all are empty, the design
(run before the per-bus rule) stands as is. Also: the delta = 0 unseparated forward-reverse pairs by fault type.

    python src/i2dir_b1_deadframes.py   -> results/network/i2dir_b1_deadframes.json
"""
import os, sys, json
from collections import Counter
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from i2dir_design import model
from i2dir_static import FWD, REV

OUT = os.path.join(HERE, "..", "results", "network")


def main():
    runs = json.load(open(os.path.join(OUT, "i2dir_design.json")))["runs"]
    fm, _, _ = model(FWD + REV)              # the frames do not depend on the noise tier
    points = sorted({(r["abs_delta"], a) for r in runs for a in r["separating_angles_deg"]}
                    | {(1.14, a) for r in runs for a in r["separating_angles_deg"]})
    out = dict(points=[])
    for mag, ang in points:
        dead = fm.dead_frames(mag * np.exp(1j * np.radians(ang)))
        out["points"].append(dict(abs_delta=mag, angle_deg=ang, dead=[list(c) for c in dead]))
        print(f"|delta| {mag:.2f} pu at {ang:3d} deg: dead frames {len(dead)}" + (f" {dead}" if dead else ""), flush=True)
    out["all_empty"] = all(not p["dead"] for p in out["points"])
    print(f"all empty: {out['all_empty']}")
    json.dump(out, open(os.path.join(OUT, "i2dir_b1_deadframes.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
