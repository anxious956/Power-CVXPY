"""Fault LOCATION, conventional against learned, stratified (results/ADAPTGRID.md section 4).

Fault location is a solved, standard relay function, and this module exists to keep the project honest
about that. The contribution of this work is zone SELECTIVITY under high fault resistance with strong
remote infeed — deciding whether a fault is inside the reach — not locating it more accurately than a
relay already does. So the two are put side by side on the same data and the same folds, stratified by
fault resistance band and by infeed condition, and the write-up says which wins where.

THE THREE ESTIMATORS
  reactance   m_hat = X_loop / X_line on the phase-selected released loop, with k0 compensation: the
              element `zone_model.phase_selected_reactance` already computes, reproduced here as a
              locator. This is the one whose bolted-fault accuracy REVIEW.md claim 16 puts at 1.5 %.
  Takagi      the same loop with the reactance line polarised by the SUPERIMPOSED current
              (common.polarised_reactance, pol='takagi'), which is the standard first-order correction
              for fault resistance and is what a modern locator actually uses.
  GBM (Q2)    the gradient-boosted regressor on the relay snapshot (q2_distance), trained and scored
              OUT OF FOLD on the same loading-bin folds as every other learned result here.

INFEED CONDITION is measured, not assumed. For a fault at per-unit distance m with resistance R_f the
relay sees Z_app = m Z_L + (I_F / I_relay) R_f, so the apparent added resistance divided by the true
R_f estimates the infeed factor |I_F / I_relay| directly:

    infeed_hat = (Re Z_loop - m Re Z_L) / R_f      (only defined for R_f above a floor)

Cases are binned at 1.5 and 3. This is the axis on which relay B's 40 ohm stratum sits (REVIEW.md
section 10 item 5: an apparent resistance near 80 ohm from a 40 ohm fault).

    python src/review/adaptgrid_location.py [--relays adapt_A adapt_B] [--frontend relayfe]
    -> results/adaptgrid/location_<frontend>.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import ladder as ld
from review import frontend
from review import q2_distance as q2
from review.zone_cv import zone_task, splits
from review.adaptgrid_run import bundle, T

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")
INFEED_BINS = ((0.0, 1.5, "<1.5"), (1.5, 3.0, "1.5-3"), (3.0, 1e9, ">3"))
RF_FLOOR = 1.0            # infeed factor is not identifiable from a bolted fault


def estimators(R):
    """Per-case m_hat from the reactance element and from Takagi, plus the measured infeed factor."""
    sel = np.arange(len(R["et"]))
    vpre, vpost, ipre, ipost, vmem = ld.pack(R, sel, T, "full", True)
    Lp = cm.loops(R, vpost, ipost, vpre, ipre)
    mask = cm.phase_selection(ipre, ipost)
    r_loop, x_loop = cm.loop_rx(Lp, mask)
    xl, rl = R["z1L"].imag, R["z1L"].real
    m_react = x_loop / xl
    m_takagi = cm.polarised_reactance(R, Lp, mask, "takagi") / xl
    m_true = R["loc"] / 100.0
    with np.errstate(divide="ignore", invalid="ignore"):
        infeed = (r_loop - m_true * rl) / np.where(R["rf"] > RF_FLOOR, R["rf"], np.nan)
    return dict(m_react=m_react, m_takagi=m_takagi, m_true=m_true, infeed=infeed,
                r_loop=r_loop, x_loop=x_loop)


def infeed_bin(v):
    out = np.full(len(v), "undefined", dtype=object)
    for lo, hi, lab in INFEED_BINS:
        out[(v > lo) & (v <= hi)] = lab
    out[v <= INFEED_BINS[0][1]] = INFEED_BINS[0][2]
    out[~np.isfinite(v)] = "bolted (undefined)"
    return out.astype(str)


def gbm_oof(R, kind="grouped", seed=0):
    """Out-of-fold distance predictions from the Q2 regressor on the zone rows."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    sel = np.arange(len(R["et"]))
    idx, y, groups = zone_task(R)
    X = q2.snapshot(R, R["S"], sel, T)
    tgt = q2.target(R)
    pred = np.full(len(R["et"]), np.nan)
    for f, tr, te, meta in splits(kind, R, idx, y, groups):
        rtr, rte = idx[tr], idx[te]
        keep = np.isfinite(tgt[rtr])
        m = HistGradientBoostingRegressor(random_state=seed + f).fit(X[rtr][keep], tgt[rtr][keep])
        pred[rte] = m.predict(X[rte])
    return pred


def err_table(err, mask, key, order):
    out = {}
    for v in order:
        s = mask & (key == v) & np.isfinite(err)
        out[str(v)] = dict(n=int(s.sum()),
                           mae_pct_of_line=(float(np.mean(np.abs(err[s])) * 100) if s.any() else None),
                           p90_pct_of_line=(float(np.percentile(np.abs(err[s]), 90) * 100) if s.any() else None))
    return out


def run(relay, fe):
    if fe == "relayfe":
        frontend.enable()
    R = bundle(relay, None)
    E = estimators(R)
    pred = gbm_oof(R)
    pos = R["pos"]                                   # in-zone faults only: locating an off-line fault is a different task
    ib = infeed_bin(E["infeed"])
    res = dict(relay=relay, frontend=fe, n_in_zone=int(pos.sum()),
               infeed=dict(median=float(np.nanmedian(E["infeed"][pos])),
                           p90=float(np.nanpercentile(E["infeed"][pos], 90)),
                           by_bin={b: int((pos & (ib == b)).sum()) for b in
                                   [x[2] for x in INFEED_BINS] + ["bolted (undefined)"]}),
               estimators={})
    for name, mhat in (("reactance element", E["m_react"]), ("Takagi", E["m_takagi"]), ("GBM distance (Q2)", pred)):
        err = mhat - E["m_true"]
        bolted = pos & (R["rf"] <= 1.0)
        res["estimators"][name] = dict(
            overall=dict(n=int((pos & np.isfinite(err)).sum()),
                         mae_pct_of_line=float(np.mean(np.abs(err[pos & np.isfinite(err)])) * 100),
                         p90_pct_of_line=float(np.percentile(np.abs(err[pos & np.isfinite(err)]), 90) * 100)),
            bolted_only=dict(n=int(bolted.sum()),
                             mae_pct_of_line=(float(np.mean(np.abs(err[bolted & np.isfinite(err)])) * 100)
                                              if (bolted & np.isfinite(err)).any() else None)),
            by_rf_bin=err_table(err, pos, R["rf_bin"], cm.RF_LABELS),
            by_infeed=err_table(err, pos, ib, [x[2] for x in INFEED_BINS] + ["bolted (undefined)"]))
        o = res["estimators"][name]["overall"]
        print(f"  [{relay} {fe}] {name:20s} MAE {o['mae_pct_of_line']:6.2f} % of line  p90 {o['p90_pct_of_line']:6.2f} "
              f"| bolted {res['estimators'][name]['bolted_only']['mae_pct_of_line'] or float('nan'):5.2f} "
              f"| by R_f " + " ".join(f"{b}:{(res['estimators'][name]['by_rf_bin'][b]['mae_pct_of_line'] or 0):.1f}"
                                      for b in cm.RF_LABELS), flush=True)
    return res


def main(relays=("adapt_A", "adapt_B"), fe="relayfe"):
    t0 = time.time()
    out = dict(script="adaptgrid_location", commit=cm.git_commit(), frontend=fe, t_ms=T,
               note=("Fault location is a standard relay function and is reported here only to place the "
                     "project's contribution correctly: the contribution is zone selectivity under high "
                     "fault resistance with strong infeed, not location accuracy."),
               relays={})
    for r in relays:
        out["relays"][r] = run(r, fe)
    out["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, f"location_{fe}.json")
    json.dump(out, open(p, "w"), indent=1, default=str)
    print("saved", p, f"[{out['runtime_s']:.0f}s]")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--relays", nargs="+", default=["adapt_A", "adapt_B"])
    ap.add_argument("--frontend", default="relayfe")
    a = ap.parse_args()
    main(tuple(a.relays), a.frontend)
