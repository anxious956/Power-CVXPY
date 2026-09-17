"""Q-fair rungs 3 and 3b with no data fitting: fixed zone-1 settings (0.85 of line reactance) for
the repo's reactance rule, the same with a mimic filter, Takagi (superimposed-current) and
I2/I0-polarised reactance lines, the incremental-quantity element, and half-cycle phasors at 10 ms.
Reports dependability / false trip / AUC per relay and decision time, and the rule's misses by R_f
and out-of-zone trips by target.

    python src/review/elements_fixed.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from review import common as cm

out = {}
t0 = time.time()
for name in ("testgrid_A", "testgrid_B", "doubleline"):
    R = cm.load_relay(name)
    idx = np.where(R["pos"] | R["neg"] | R["own99"] | R["parallel"])[0]
    pos, neg, o99, par = (R[k][idx] for k in ("pos", "neg", "own99", "parallel"))
    zi = pos | neg
    y = pos[zi].astype(int)
    res = {}
    for t in (10, 20, 30, 40, 50):
        variants = {}
        for label, window, mim in (("full", "full", False), ("full+mimic", "full", True),
                                   ("half+mimic", "half", True), ("half", "half", False)):
            if t < 20 and window == "full":
                continue
            E = cm.elements(R, idx, t, window=window, mimic_i=mim)
            for el, key, lower in (("reactance rule", "rule_x", True), ("Takagi", "takagi_x", True),
                                   ("I2-polarised", "i2pol_x", True), ("I0-polarised", "i0pol_x", True),
                                   ("incremental", "incr", False)):
                s = E[key]
                trip = (s < R["x_reach"]) if lower else (s > 1.0)
                sc = -s if lower else s
                d = dict(dependability=float(trip[pos].mean()), false_trip=float(trip[neg].mean()),
                         auc=float(roc_auc_score(y, sc[zi])),
                         own99=float(trip[o99].mean()) if o99.any() else None,
                         parallel=float(trip[par].mean()) if par.any() else None,
                         dep_by_rf={f"{r:g}": float(trip[pos & (R['rf'][idx] == r)].mean()) for r in (1, 10, 40)},
                         ft_by_rf={f"{r:g}": float(trip[neg & (R['rf'][idx] == r)].mean()) for r in (1, 10, 40)})
                if el == "reactance rule":
                    d["ft_by_target"] = {tg: float(trip[neg & (R["tgt"][idx] == tg)].mean())
                                         for tg in np.unique(R["tgt"][idx][neg])}
                variants[f"{el} [{label}]"] = d
        res[t] = variants
        for k, d in variants.items():
            print(f"{name:11s} {t:2d} ms {k:34s} dep {d['dependability']*100:5.1f}  ft {d['false_trip']*100:5.1f}  "
                  f"AUC {d['auc']:.3f}  99% {'' if d['own99'] is None else f'{d['own99']*100:5.1f}'}  "
                  f"par {'' if d['parallel'] is None else f'{d['parallel']*100:5.1f}'}  dep/Rf {d['dep_by_rf']}  ft/Rf {d['ft_by_rf']}", flush=True)
    out[name] = res
os.makedirs(os.path.join(cm.ROOT, "results", "review"), exist_ok=True)
json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "elements_fixed.json"), "w"), indent=2)
print(f"done [{time.time()-t0:.0f}s]")
