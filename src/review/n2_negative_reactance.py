"""N2: zone_model.phase_selected_reactance (zone_model.py:206) keeps only released loops with Im(Z) > 0 and
otherwise returns 10 ohm: the sign of the loop reactance is its only directional decision. Measures, per
relay, decision time, class and R_f, how often the rule returns that default because the faulted loop
reads negative reactance, what a separate directional element says for the same cases, and the rule's
trip rate on reverse faults (relay bus and lines behind the relay), which it has no element to block.

    python src/review/n2_negative_reactance.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review.ladder import directional

out = {}
for name in ("testgrid_B", "testgrid_A", "doubleline"):
    R = cm.load_relay(name)
    sel = np.where(R["pos"] | R["neg"] | R["reverse"])[0]
    res = {}
    for t in (20, 40, 50):
        vpre, vpost, ipre, ipost = cm.phasors_at(R, sel, t)
        Lp = cm.loops(R, vpost, ipost, vpre, ipre)
        mask = cm.phase_selection(ipre, ipost)
        x, Z = cm.rule_reactance(Lp, mask)
        default = x == 10.0
        neg_x = (np.where(mask, Z.imag, np.inf) < 0).any(1)
        fwd = directional(vpre, vpost, ipre, ipost, R["z1L"])
        trip = x < R["x_reach"]
        r = {}
        for cls in ("pos", "neg", "reverse"):
            for rf in (1.0, 10.0, 40.0):
                m = R[cls][sel] & (R["rf"][sel] == rf)
                if m.any():
                    r[f"{cls}|{rf:g}"] = dict(n=int(m.sum()), rule_default=float(default[m].mean()),
                                              released_loop_negative_x=float(neg_x[m].mean()),
                                              directional_forward=float(fwd[m].mean()), rule_trip=float(trip[m].mean()))
        res[str(t)] = r
        for k, v in r.items():
            print(f"{name} {t} ms {k:12s} n={v['n']:3d}  rule default {v['rule_default']*100:5.1f}%  loop X<0 "
                  f"{v['released_loop_negative_x']*100:5.1f}%  directional fwd {v['directional_forward']*100:5.1f}%  "
                  f"rule trips {v['rule_trip']*100:5.1f}%", flush=True)
    out[name] = res
    del R
json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "n2_negative_reactance.json"), "w"), indent=1)
