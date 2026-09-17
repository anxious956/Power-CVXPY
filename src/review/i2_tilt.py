"""Q-fair rung 3: negative-sequence polarised reactance line with a non-homogeneity tilt from the
setting study (source impedance angles at both line ends, two-source formula at the reach point).
Nothing is fitted on EMT records. Evaluated fixed (reach 0.85 of line reactance) and with a tuned reach
(threshold at 5 % false trip on training negatives) on exactly the folds of zone_cv.py.

Also reports the same element with the full-network tilt, and with zero tilt, so the value of the
tilt is visible.

    python src/review/i2_tilt.py
"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from review import common as cm
from review.setting_study import build, tilt_angles, RELAY_BUS
from review.zone_cv import splits

FAR = 0.05
out = {}
for name in ("testgrid_B", "testgrid_A", "doubleline"):
    R = cm.load_relay(name)
    net = build(R["graph"])
    T = tilt_angles(net, RELAY_BUS[name], R["cfg"]["line"])
    tilts = {"two-source tilt": (T[2]["tilt_two_source_deg"], T[1]["tilt_two_source_deg"]),
             "network tilt": (T[2]["tilt_network_deg"], T[1]["tilt_network_deg"]),
             "no tilt": (0.0, 0.0)}
    idx = np.where(R["pos"] | R["neg"] | R["own99"] | R["parallel"])[0]
    zmask = R["pos"][idx] | R["neg"][idx]
    zi = idx[zmask]
    y = R["pos"][zi].astype(int)
    groups = R["groups"][zi]
    res = dict(tilt_angles=T, fixed={}, tuned={})
    for t, window, mim in ((10, "half", True), (20, "full", False), (20, "full", True), (50, "full", False)):
        vpre, vpost, ipre, ipost = cm.phasors_at(R, idx, t, window, mim)
        Lp = cm.loops(R, vpost, ipost, vpre, ipre)
        mask = cm.phase_selection(ipre, ipost)
        key = f"{t} ms {window}{'+mimic' if mim else ''}"
        for lab, (t2, t1) in tilts.items():
            x = cm.i2_tilted_reactance(R, Lp, mask, t2, t1)
            trip = x < R["x_reach"]
            pos, neg = R["pos"][idx], R["neg"][idx]
            o99, par = R["own99"][idx], R["parallel"][idx]
            d = dict(dependability=float(trip[pos].mean()), false_trip=float(trip[neg].mean()),
                     dependability_ci=cm.binom_ci(int(trip[pos].sum()), int(pos.sum())),
                     false_trip_ci=cm.binom_ci(int(trip[neg].sum()), int(neg.sum())),
                     auc=float(roc_auc_score(pos[zmask], -x[zmask])),
                     own99=float(trip[o99].mean()), parallel=float(trip[par].mean()) if par.any() else None,
                     dep_by_rf={f"{r:g}": float(trip[pos & (R['rf'][idx] == r)].mean()) for r in (1, 10, 40)},
                     ft_by_rf={f"{r:g}": float(trip[neg & (R['rf'][idx] == r)].mean()) for r in (1, 10, 40)})
            res["fixed"][f"{key} | {lab}"] = d
            print(f"[{name}] {key:18s} {lab:16s} fixed: dep {d['dependability']*100:5.1f}  FT {d['false_trip']*100:5.1f}  "
                  f"AUC {d['auc']:.3f}  99% {d['own99']*100:5.1f}  dep/Rf {d['dep_by_rf']}  ft/Rf {d['ft_by_rf']}", flush=True)
            if lab != "two-source tilt":
                continue
            # tuned reach on the zone_cv folds
            xs = x[zmask]
            kinds = ["grouped", "stratified", "lorfo", "lolo"] if t == 20 else ["grouped"]
            for kind in kinds:
                dec_all, idx_all = [], []
                for f, tr, te, meta in splits(kind, R, zi, y, groups):
                    thr = cm.thr_at_far(-xs[tr][y[tr] == 0], FAR)
                    dec_all.append(-xs[te] > thr); idx_all.append(te)
                ii, dd = np.concatenate(idx_all), np.concatenate(dec_all)
                yy, gg = y[ii], groups[ii]
                dep = lambda s: dd[s][yy[s] == 1].mean()
                ftr = lambda s: dd[s][yy[s] == 0].mean()
                r_ = dict(dependability=float(dep(slice(None))), false_trip=float(ftr(slice(None))),
                          dependability_ci=cm.grouped_bootstrap(dep, gg, 500), false_trip_ci=cm.grouped_bootstrap(ftr, gg, 500))
                res["tuned"][f"{key} | {kind}"] = r_
                print(f"[{name}] {key:18s} tuned I2-tilt, {kind:10s}: dep {r_['dependability']*100:5.1f} "
                      f"[{r_['dependability_ci'][0]*100:.1f},{r_['dependability_ci'][1]*100:.1f}]  FT {r_['false_trip']*100:5.1f} "
                      f"[{r_['false_trip_ci'][0]*100:.1f},{r_['false_trip_ci'][1]*100:.1f}]", flush=True)
    out[name] = res
    del R
json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "i2_tilt.json"), "w"), indent=1)
print("saved results/review/i2_tilt.json")
