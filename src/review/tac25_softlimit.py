"""The inverter current limit as an UNCERTAIN PARAMETER, not a known constant (REVIEW.md section 10,
design follow-up 1).

WHY
---
results/DESIGN.md section 3 puts the limit inside the problem as TAC25 (1b) does: an inverter that is
injecting delta cannot simultaneously carry a positive-sequence current above I_max - |delta|, so those
realisations leave the uncertainty set and separation gets easier. That is sound only if I_max is a hard
bound. This project's own EMT measurement says it is not: `ibr_limiter_check.py` measures the fundamental
|I1| + |I2| at the inverter terminals at 1.07-1.18 pu median but p95 ~1.5 and max ~2.1 against a
controller Imax of 1.2 pu, and the overshoot is still there at cycles 9-10, so it is not a first-cycle
transient (see `soft_limit_evidence`).

WHAT TO DO ABOUT IT
-------------------
Treat I_max as an uncertain parameter with a known band [lo, hi] and PRUNE AT THE LOOSEST BOUND. If the
true limit is anywhere in [lo, hi], every realisation that can physically occur while delta is injected
satisfies |i+| <= hi - |delta|, so restricting the uncertainty set with `hi` keeps a superset of what can
occur. Separation proved against a superset holds for the true set:

    U_true(I_max_true) subset U(hi)   for every I_max_true <= hi
    => separation on U(hi) implies separation on U_true

so the guarantee holds regardless of how soft the limiter is, at the cost of a larger delta. This is the
`robust` column below. The price is exactly the monotone trend DESIGN.md section 4.1 already shows: the
looser the bound used for pruning, the larger the required signal.

INJECTABILITY is the other half and is reported separately. Producing delta needs headroom in the
inverter's own current: |i+| + |delta| <= I_max_true. A delta that is proved separating under the loosest
pruning may still be unproducible if the true limit is at the bottom of the band. We report, for each
cell, the smallest true limit at which the robust delta is injectable, i.e. |i+|_max + |delta|. Nothing is
assumed about which end of the band the true limit sits at.

    python src/review/tac25_softlimit.py [--quick]   -> results/review_wp1/tac25_softlimit.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from wp1_common import ModelSet, source_sets
import tac25_design as td
from tac25_map import make_params, sir_of
from review import common as cm

OUT = os.path.join(cm.ROOT, "results", "review_wp1")
EPS_GRID = (0.02, 0.04, 0.08, 0.12, 0.16)
IMAX_GRID = (1.1, 1.2, 1.3, 1.5, 2.1)
BAND = (1.1, 2.1)                      # the measured spread: controller Imax 1.2, p95 1.5, max 2.1
RHO_GRID = (0.0, 0.1)


def i_plus_max(p, mode="outer"):
    _, (c, g) = source_sets(p, mode)
    return float(max(abs(c + s1 * g[0] + s2 * g[1]) for s1 in (-1, 1) for s2 in (-1, 1)))


def robust_min_delta(ms, band=BAND, rho=0.0, r_step=0.02, n_ang=72, r_max=2.0):
    """Smallest separating |delta| when the current limit is only known to lie in `band`.

    Pruning uses the LOOSEST bound, so the uncertainty set is a superset of the true one whatever the
    true limit is, and separation transfers. `min_true_limit_to_inject` is |i+|_max + |delta|: the
    smallest true limit at which the returned delta can actually be produced."""
    lo, hi = band
    r = td.min_delta(ms, i_max=hi, limit_inside=True, limit_design=False, rho=rho,
                     r_step=r_step, n_ang=n_ang, r_max=r_max)
    r["band"] = [float(lo), float(hi)]
    r["pruned_at"] = float(hi)
    if r["feasible"]:
        r["min_true_limit_to_inject"] = float(r["i_plus_max"] + r["abs_delta"])
        r["injectable_at_band_bottom"] = bool(r["min_true_limit_to_inject"] <= lo + 1e-12)
    return r


def soft_limit_evidence():
    """What the measured 1.5 / 2.1 pu figures actually are, read back from the measurement itself."""
    path = os.path.join(cm.ROOT, "results", "review", "ibr_limiter_check.json")
    if not os.path.exists(path):
        return dict(available=False)
    D = json.load(open(path))
    out = dict(available=True, quantity="fundamental phasor magnitude, full-cycle DFT (128 samples), "
                                         "peak-referenced, in pu of the controller's own I_base",
               not_instantaneous_peak=True, windows=["pre-fault", "cycle 1-2", "cycle 3-4", "cycle 9-10"],
               inverters={})
    for cub, v in D.items():
        out["inverters"][cub.split("_")[-1]] = dict(
            imax_setting_pu=v["Imax_pu"], n_faults=v["n"],
            i1_plus_i2={w: dict(median=v[w]["i1_plus_i2_pu_median"], p95=v[w]["i1_plus_i2_pu_p95"],
                                max=v[w]["i1_plus_i2_pu_max"]) for w in out["windows"]},
            max_phase={w: dict(median=v[w]["max_phase_pu_median"], p95=v[w]["max_phase_pu_p95"])
                       for w in out["windows"]})
    # the decisive read: is the overshoot a first-cycle transient or a steady-state property?
    late = [v["cycle 9-10"]["i1_plus_i2_pu_p95"] for v in D.values()]
    early = [v["cycle 1-2"]["i1_plus_i2_pu_p95"] for v in D.values()]
    out["overshoot_is_steady_state"] = bool(min(late) > 1.2)
    out["p95_cycle_1_2"] = [float(x) for x in early]
    out["p95_cycle_9_10"] = [float(x) for x in late]
    out["note"] = ("|I1| + |I2| is a sum of sequence magnitudes and bounds the phase current from above; "
                   "the largest phase-current magnitude is reported beside it. Both exceed the 1.2 pu "
                   "setting at p95, and both still exceed it at cycles 9-10, so the overshoot is not a "
                   "first-cycle LCL/PLL transient being compared against a steady-state limit.")
    return out


def main(quick=False):
    t0 = time.time()
    step, nang = (0.04, 36) if quick else (0.02, 72)
    res = dict(script="tac25_softlimit", commit=cm.git_commit(), band=list(BAND), r_step=step, n_ang=nang,
               evidence=soft_limit_evidence(), cells=[])
    for rho in RHO_GRID:
        for eps in EPS_GRID:
            p = make_params(eps)
            ms = ModelSet(p, mode="outer")
            ipm = i_plus_max(p)
            row = dict(eps=eps, rho=rho, sir=sir_of(p), i_plus_max=ipm, hard=dict())
            for im in IMAX_GRID:                       # the known-limit treatment, for comparison
                r = td.min_delta(ms, i_max=im, limit_inside=True, limit_design=False, rho=rho,
                                 r_step=step, n_ang=nang, r_max=2.0)
                row["hard"][f"{im:g}"] = dict(feasible=r["feasible"], abs_delta=r["abs_delta"])
            rb = robust_min_delta(ms, BAND, rho=rho, r_step=step, n_ang=nang)
            row["robust"] = dict(feasible=rb["feasible"], abs_delta=rb["abs_delta"], angle_deg=rb["angle_deg"],
                                 pruned_at=rb["pruned_at"],
                                 min_true_limit_to_inject=rb.get("min_true_limit_to_inject"),
                                 injectable_at_band_bottom=rb.get("injectable_at_band_bottom"))
            rf = td.min_delta(ms, i_max=99.0, limit_inside=False, limit_design=False, rho=rho,
                              r_step=step, n_ang=nang, r_max=2.0)
            row["no_limit"] = dict(feasible=rf["feasible"], abs_delta=rf["abs_delta"])
            if rb["feasible"]:
                row["continuous_check"] = td.validate_continuous(p, "outer", rb["delta"], eps * (1 + rho),
                                                                 i_max=BAND[1], limit_inside=True)
            res["cells"].append(row)
            print(f"  eps {eps:.2f} rho {rho:.1f}: robust {row['robust']['abs_delta']} "
                  f"(inject needs true limit >= {row['robust']['min_true_limit_to_inject']}) | "
                  f"hard 1.2 {row['hard']['1.2']['abs_delta']} | 2.1 {row['hard']['2.1']['abs_delta']} | "
                  f"no limit {row['no_limit']['abs_delta']}", flush=True)
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "tac25_softlimit.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, f"[{res['runtime_s']:.0f}s]")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick)
