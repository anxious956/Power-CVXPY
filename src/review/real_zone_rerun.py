"""Re-run of the zone-1 setting tables in results/REAL_TESTGRID.md and REAL_DOUBLELINE.md with the fixed
element. real_zone.py takes the post-fault phasor from the cycle 20-40 ms after inception (window() puts
inception at sample 512, score_reactance reads EVENT + CYCLE), so t = 40 ms here, on noise-free records
exactly as real_zone.py (no measurement chain). Rungs as in src/review/ladder.py: R0 = the repo rule,
R2 = mimic + separate directional element + quadrilateral with rule-based settings.

    python src/review/real_zone_rerun.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import ladder as ld

NOISE_FREE = dict(noise_rel=0.0, adc_bits=0)
out = {}
for name in ("testgrid_A", "testgrid_B", "doubleline"):
    R = cm.load_relay(name, NOISE_FREE)
    S = ld.settings(R, name)
    sel = np.where(R["pos"] | R["neg"] | R["own99"] | R["parallel"] | R["reverse"] | R["switching"])[0]
    res = {}
    for rung, mim in (("R0", False), ("R2", True)):
        p = cm.phasors_at(R, sel, 40, "full", mim)
        trip, _ = ld.evaluate_block(R, *p, S, rung)
        r = ld.rates(trip, R, sel)
        by = {}
        for cls in ("pos", "neg", "own99", "parallel", "reverse"):
            m = R[cls][sel]
            if m.any():
                by[cls] = {f"{rf:g} ohm": float(trip[m & (R['rf'][sel] == rf)].mean()) for rf in (1.0, 10.0, 40.0)}
        res[rung] = dict(rates=r, by_rf=by)
        print(f"[{name}] {rung}: dep {r['pos']['rate']*100:5.1f}  out-of-zone {r['neg']['rate']*100:5.1f}  own99 "
              f"{r['own99']['rate']*100:5.1f}  reverse {r['reverse']['rate']*100:5.1f}  switching {r['switching']['rate']*100:5.1f}"
              + (f"  parallel {r['parallel']['rate']*100:5.1f}" if 'parallel' in r else "")
              + "  | by R_f: " + json.dumps({k: {kk: round(vv * 100, 1) for kk, vv in v.items()} for k, v in by.items()}), flush=True)
    out[name] = dict(settings=S, **res)
    del R
json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "real_zone_rerun.json"), "w"), indent=1, default=str)
