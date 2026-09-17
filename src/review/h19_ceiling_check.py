"""H19 follow-up: is the corrected CNN's AUC 1.000 at delta = 0 plausible, or a leak?

CPU checks on the zone study data, --quick sizes, 3 seeds, delta 0 and 0.514:
  1. gradient boosting on the (fixed) engineered features: can a NONLINEAR model on the same
     phasor quantities reach the CNN's ceiling? (if yes, LR's 0.994 is a linearity limit)
  2. leak check: gradient boosting on features from the PRE-event window only (sequence phasor
     magnitudes, real/imag parts, v/i ratios two cycles before the event). Both classes share
     the same pre-event process, so anything clearly above 0.5 would be a generator leak.
  3. same pre-event check on raw samples: gradient boosting on the pre-event currents and
     voltages decimated to 16 samples/cycle, globally scaled.

  python src/review/h19_ceiling_check.py
"""
import time
import numpy as np
from dataclasses import replace
from sklearn.ensemble import HistGradientBoostingClassifier
from synth_common import design_direction, save
from waveforms import SigParams, sequence_phasors, CYCLE, EVENT
import detect as D
import zone_detect as Z

direction = design_direction()
grid = replace(Z.ZoneParams(), rF=0.3)


def pre_features(X):
    out = []
    for x in X:
        v = sequence_phasors(x[:3], EVENT - 2 * CYCLE); i = sequence_phasors(x[3:], EVENT - 2 * CYCLE)
        f = []
        for c in np.r_[v, i]:
            f += [abs(c), c.real, c.imag]
        f += [abs(v[1] / i[1]), np.angle(v[1] * np.conj(i[1]))]
        out.append(f)
    return np.array(out)


def pre_raw(X):
    return X[:, :, :EVENT:8].reshape(len(X), -1)


def gbm(Ftr, ytr, Fte, seed):
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.1, random_state=seed)
    m.fit(Ftr, ytr)
    return m.decision_function(Fte)


rows = []; t0 = time.time()
for t in (0.0, 0.514):
    for sd in range(3):
        Xtr, ytr, _ = Z.make_zone_dataset(350, np.random.default_rng(100 + 17 * sd), t * direction, SigParams(), grid)
        Xte, yte, _ = Z.make_zone_dataset(250, np.random.default_rng(999 + 31 * sd), t * direction, SigParams(), grid)
        tau = Z.line_tau_samples(grid)
        Ftr, Fte = Z.zone_features(Xtr, grid, fixed=True, mimic_tau=tau), Z.zone_features(Xte, grid, fixed=True, mimic_tau=tau)
        r = dict(delta=t, seed=sd)
        r["gbm_engineered"] = D._auc(gbm(Ftr, ytr, Fte, sd), yte)
        r["lr_engineered"] = D._auc(D.fit_lr_scores(Ftr, ytr, Fte, seed=sd, max_iter=4000)[1], yte)
        r["gbm_pre_event_phasors"] = D._auc(gbm(pre_features(Xtr), ytr, pre_features(Xte), sd), yte)
        r["gbm_pre_event_raw"] = D._auc(gbm(pre_raw(Xtr), ytr, pre_raw(Xte), sd), yte)
        rows.append(r)
        print(r, f"[{time.time()-t0:.0f}s]", flush=True)
print()
for t in (0.0, 0.514):
    rr = [r for r in rows if r["delta"] == t]
    print(f"delta={t}: " + "  ".join(f"{k} {np.mean([r[k] for r in rr]):.4f}+-{np.std([r[k] for r in rr]):.4f}"
                                     for k in ("lr_engineered", "gbm_engineered", "gbm_pre_event_phasors", "gbm_pre_event_raw")))
save("h19_ceiling_check.json", dict(rows=rows, runtime_s=time.time() - t0))
