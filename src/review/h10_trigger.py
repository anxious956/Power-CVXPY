"""H10 / H20: every pipeline anchors its windows at the ground-truth inception sample (1.1 s). A relay
anchors at its own start element. This script

1. implements a causal starter: superimposed phase current di(k) = i(k) - i(k - 1 cycle) above
   max(0.1 In, 8 sigma of the pre-fault di) for 3 consecutive samples (In = 1000 A peak-referenced as in
   ladder.py), and reports the trigger delay relative to inception per class, and missed starts;
2. re-evaluates, with windows anchored at the trigger (window end = trigger + 20 ms), models trained on
   truth-aligned windows exactly as in zone_cv.py (grouped folds, own-99 % negatives): gradient boosting
   on the raw window and engineered + LR; and the ladder rungs R0 and R2 with the same anchoring.
   Cases with no trigger are counted as not tripped.

    python src/review/h10_trigger.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from review import common as cm
from review import ladder as ld
from review.zone_cv import zone_task, splits
import real_ml
from zone_detect import zone_features

SPC, FS = 128, 6400


def trigger(R, idx, in_a=1000.0):
    i = R["full"][idx, 3:].astype(np.float64)
    di = np.abs(i[:, :, SPC:] - i[:, :, :-SPC]).max(axis=1)          # (n, t - SPC), sample k + SPC
    ev = R["ev"] - SPC
    pre = di[:, ev - 2 * SPC:ev - 8]
    thr = np.maximum(0.1 * in_a * np.sqrt(2), 8 * pre.std(axis=1, keepdims=True))
    above = di > thr
    run3 = above[:, :-2] & above[:, 1:-1] & above[:, 2:]
    run3[:, :ev - 8] = False                                           # search from 8 samples before inception
    has = run3.any(1)
    first = np.where(has, run3.argmax(1), -1)
    return np.where(has, first - ev, 10**6)                            # delay in samples (2 extra samples to confirm)


def shifted(R, idx, delay, t_ms, fn):
    """Apply fn(R', idx_group, t) to groups of cases with the same trigger delay, by shifting the event index."""
    out = [None] * len(idx)
    for d in np.unique(delay):
        m = np.where(delay == d)[0]
        R2 = dict(R); R2["ev"] = R["ev"] + int(d) + 2
        vals = fn(R2, idx[m], t_ms)
        for k, j in enumerate(m):
            out[j] = vals[k] if not isinstance(vals, tuple) else tuple(v[k] for v in vals)
    return out


if __name__ == "__main__":
    t0 = time.time()
    res = {}
    from review import frontend
    for fe in ("current", "relay-bandwidth"):
      if fe == "relay-bandwidth":
        frontend.enable()                                  # H30: 3rd-order Butterworth 400 Hz before noise and ADC
      res[fe] = {}
      for name in ("testgrid_B", "testgrid_A", "doubleline"):
        R = cm.load_relay(name)
        R["g"] = type("G", (), dict(z1=R["lp"]["z1"], z0_ratio=R["lp"]["z0"] / R["lp"]["z1"]))
        S = ld.settings(R, name)
        sets = ("pos", "neg", "own99", "switching", "reverse_bus")
        allidx = np.where(np.any([R[h] for h in sets], axis=0))[0]
        delay = trigger(R, allidx)
        r = dict(delay_ms={})
        for h in sets:
            m = R[h][allidx]
            d = delay[m]; ok = d < 10**6
            r["delay_ms"][h] = dict(n=int(m.sum()), started=float(ok.mean()),
                                    median=float(np.median(d[ok]) / 6.4) if ok.any() else None,
                                    p95=float(np.percentile(d[ok], 95) / 6.4) if ok.any() else None,
                                    min=float(d[ok].min() / 6.4) if ok.any() else None)
        print(f"[{name}] trigger delay: {json.dumps(r['delay_ms'])}", flush=True)
        idx, y, groups = zone_task(R)
        dz = delay[np.searchsorted(allidx, idx)]
        started = dz < 10**6
        dz_s = np.where(started, np.clip(dz, -8, 200), 0)
        t = 20
        # features: truth-aligned and trigger-anchored
        Fr = real_ml.raw_window(R, idx, t); Fe = zone_features(real_ml.phasor_view(R, idx, t), R["g"])
        Fr_t = np.stack(shifted(R, idx, dz_s, t, lambda RR, ii, tt: real_ml.raw_window(RR, ii, tt)))
        Fe_t = np.stack(shifted(R, idx, dz_s, t, lambda RR, ii, tt: zone_features(real_ml.phasor_view(RR, ii, tt), R["g"])))
        acc = {}
        for f, tr, te, meta in splits("grouped", R, idx, y, groups):
            for n, Xa, Xt in (("gradient boosting", Fr, Fr_t), ("engineered + LR", Fe, Fe_t)):
                m = real_ml.fit_balanced(real_ml.models(f)[n], Xa[tr], y[tr], f)
                thr = cm.thr_at_far(cm.oof_scores(n, Xa[tr], y[tr], f, groups=groups[tr])[y[tr] == 0], 0.05)
                for lab, X in (("truth-aligned", Xa), ("trigger-anchored", Xt)):
                    s = real_ml.score(m, X[te]); dec = (s > thr) & (started[te] if lab == "trigger-anchored" else True)
                    acc.setdefault((n, lab), []).append((te, dec, s))
            print(f"  [{name}] fold {f} [{time.time()-t0:.0f}s]", flush=True)
        for (n, lab), v in acc.items():
            ii = np.concatenate([a[0] for a in v]); dd = np.concatenate([a[1] for a in v])
            aucs = [roc_auc_score(y[a[0]], a[2]) for a in v]
            r[f"{n} | {lab}"] = dict(auc=float(np.mean(aucs)), dependability=float(dd[y[ii] == 1].mean()),
                                     false_trip_beyond=float(dd[R["neg"][idx][ii]].mean()), own99=float(dd[R["own99"][idx][ii]].mean()))
        # ladder rungs with the same anchoring
        for rung, mim in (("R0", False), ("R2", True)):
            for lab, dd_ in (("truth-aligned", np.zeros(len(idx), int)), ("trigger-anchored", dz_s)):
                P = shifted(R, idx, dd_ if lab == "trigger-anchored" else dd_ - 2, t, lambda RR, ii, tt: ld.pack(RR, ii, tt, "full", mim))
                P = tuple(np.stack([p[k] for p in P]) for k in range(5))
                trip, _ = ld.evaluate_block(R, *P, S, rung)
                if lab == "trigger-anchored":
                    trip = trip & started
                r[f"{rung} | {lab}"] = dict(dependability=float(trip[y == 1].mean()), false_trip_beyond=float(trip[R["neg"][idx]].mean()),
                                            own99=float(trip[R["own99"][idx]].mean()))
        for k, v in r.items():
            if k != "delay_ms":
                print(f"[{name}] {k:40s} {json.dumps({kk: round(vv, 3) for kk, vv in v.items()})}", flush=True)
        res[fe][name] = r
        print(f"[{fe}] {name} done", flush=True)
        json.dump(res, open(os.path.join(cm.ROOT, "results", "review", "h10_trigger.json"), "w"), indent=1)
        del R
    print(f"done [{time.time()-t0:.0f}s]")
