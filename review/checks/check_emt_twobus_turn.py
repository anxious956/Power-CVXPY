"""How far delta turned in absolute terms during the fault in the two-bus EMT runs (PSCAD_DELTA_SWEEP.md says "a few
degrees"; PSCAD_TAC25.md does not say). Delta at 0.38 s (fault) against delta at 0.25 s (pre-fault), one frame.

    python review/checks/check_emt_twobus_turn.py
"""
import os, sys, json
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from pscad_twobus_check import read_case, injection, WORK  # noqa: E402

for fn in ("delta_design", "tac25_design"):
    runs = json.load(open(os.path.join(ROOT, "results", "pscad", fn + ".json")))["runs"]
    turns = []
    for r in runs:
        if r["kind"] != "fault" or not r.get("d2mag"):
            continue
        p = os.path.join(WORK, r["name"] + ".gf46")
        if not os.path.exists(os.path.join(p, r["name"] + "_01.out")):
            continue
        run = read_case(p, r["name"])
        _, d_pre = injection(run, 0.25)
        _, d_flt = injection(run, 0.38)
        turns.append((float(np.degrees(np.angle(d_flt / d_pre))), r["name"]))
    t = np.array([x[0] for x in turns])
    print(f"{fn}: {len(t)} fault runs with delta; turn {t.min():+.1f} .. {t.max():+.1f} deg, median |.| {np.median(np.abs(t)):.1f}; "
          f"largest {sorted(turns, key=lambda x: -abs(x[0]))[:3]}")
