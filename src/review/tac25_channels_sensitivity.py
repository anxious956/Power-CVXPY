"""Sensitivity of the "delta = 0 suffices" result (tac25_channels.py) to the systematic/per-phase SPLIT.

WHY THIS EXISTS
---------------
tac25_channels.CHANNELS sets per_phase_share = 1/3 for both VT and CT. That number has NO source. The
only citation in this codebase for the error MAGNITUDES is Kasztenny 2021 section III.A-B
(papers/notes/E_practitioner_settings.md section 7), and it gives a total ratio/phase band per
instrument under fault conditions -- it says nothing about how much of that band is common to the three
phases of one instrument set (systematic) versus differs between them (per-phase). The 1/3 figure was
picked when tac25_channels.py was written, with no derivation; it visually matches the unrelated 1/3
weighting that appears structurally in the symmetric-component transform (see
seq_to_seq_phase_generators), but that is a fact about the transform's arithmetic, not a measurement of
any instrument's phase-to-phase spread, and the two numbers being equal is coincidence dressed up to
look like derivation.

WHAT THIS SCRIPT DOES
----------------------
Holds the TOTAL error band at the cited Kasztenny figures (VT 6%/4deg, CT 10%/3deg -- the wide end of
the cited range, already the more conservative choice) and sweeps ONLY the split, per_phase_share in
[0, 1], from "all systematic" (share=0, the most optimistic possible reading -- an instrument's three
phases err identically) to "all per-phase" (share=1, the most pessimistic -- none of the error is
common-mode, everything differs phase to phase). This isolates exactly the free parameter that has no
citation, without introducing a second unsourced number.

A PHYSICAL REASON THE TRUE SHARE MAY BE WELL ABOVE 1/3, NOT BELOW: CT saturation is driven by the
instantaneous flux history of each phase's core, which depends on that phase's own fault current
magnitude and DC offset. During an unbalanced fault the three phase currents differ substantially, so
saturation-driven ratio error is not common-mode -- it is inherently phase-asymmetric. The 1/3 default
is therefore not obviously conservative; if anything the physically motivated correction runs the
opposite direction from what section 4.1.1 assumed.

    python src/review/tac25_channels_sensitivity.py [--quick]
    -> results/review_wp1/tac25_channels_sensitivity.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from wp1_common import ModelSet
import tac25_channels as tch
from tac25_map import make_params
from review import common as cm

OUT = os.path.join(cm.ROOT, "results", "review_wp1")

# the cited total bands only -- no split assumption baked in here
TOTAL_BANDS = dict(VT=dict(ratio=0.06, phase_deg=4.0), CT=dict(ratio=0.10, phase_deg=3.0))
SHARES = (0.0, 1 / 3, 0.5, 2 / 3, 0.85, 1.0)


def spec_at_share(share):
    return dict(VT=dict(TOTAL_BANDS["VT"], per_phase_share=share),
                CT=dict(TOTAL_BANDS["CT"], per_phase_share=share))


def min_delta_at_share(p, share, i_max=None, rho=0.0, r_step=0.02, n_ang=72, r_max=2.0):
    spec = spec_at_share(share)
    return tch.min_delta_structured(p, spec=spec, rho=rho, i_max=i_max, r_step=r_step, n_ang=n_ang, r_max=r_max)


def find_share_boundary(p, i_max=None, rho=0.0, r_step=0.02, n_ang=72, lo=0.0, hi=1.0, tol=0.01, max_iter=20):
    """Bisect for the smallest per_phase_share at which delta=0 no longer separates every case. Returns
    None if delta=0 separates even at share=1 (the fully differential, most pessimistic reading)."""
    ms_at = lambda share: ModelSet(p, mode="outer")
    ms = ms_at(1.0)
    sep_at_1 = tch.separated_structured(p, ms, 0j, spec_at_share(hi), rho=rho,
                                        limit=None if i_max is None else (p, "outer", i_max))
    if sep_at_1:
        return None
    a, b = lo, hi
    for _ in range(max_iter):
        mid = (a + b) / 2
        sep = tch.separated_structured(p, ms, 0j, spec_at_share(mid), rho=rho,
                                       limit=None if i_max is None else (p, "outer", i_max))
        if sep:
            a = mid
        else:
            b = mid
        if b - a < tol:
            break
    return float(b)


def one_scenario(quick, i_max, rho):
    step, nang = (0.04, 36) if quick else (0.02, 72)
    p = make_params(0.08)
    cells = []
    for share in SHARES:
        r = min_delta_at_share(p, share, i_max=i_max, rho=rho, r_step=step, n_ang=nang)
        cells.append(dict(per_phase_share=share, feasible=r["feasible"], abs_delta=r["abs_delta"]))
        print(f"  [i_max={i_max} rho={rho}] per_phase_share {share:.3f}: |delta| = {r['abs_delta']}", flush=True)
    boundary = find_share_boundary(p, i_max=i_max, rho=rho, r_step=step, n_ang=nang)
    if boundary is None:
        print(f"  [i_max={i_max} rho={rho}] delta=0 separates at EVERY share up to 1.0", flush=True)
    else:
        print(f"  [i_max={i_max} rho={rho}] delta=0 stops separating once per_phase_share exceeds {boundary:.3f}", flush=True)
    return dict(i_max=i_max, rho=rho, cells=cells, share_at_which_delta0_first_fails=boundary)


def main(quick=False, i_max=2.1, rho=0.0):
    t0 = time.time()
    res = dict(script="tac25_channels_sensitivity", commit=cm.git_commit(),
               total_bands_cited=TOTAL_BANDS, shares_swept=list(SHARES),
               note=("per_phase_share has no citation anywhere in this codebase; only the TOTAL ratio/phase "
                     "bands (Kasztenny 2021 section III.A-B) are cited. This sweep holds the total fixed and "
                     "varies only the split."),
               scenarios=[])
    for im, rh in ((2.1, 0.0), (2.1, 0.1), (1.2, 0.0)):
        res["scenarios"].append(one_scenario(quick, im, rh))
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "tac25_channels_sensitivity.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, f"[{res['runtime_s']:.0f}s]")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--i-max", type=float, default=2.1)
    ap.add_argument("--rho", type=float, default=0.0)
    a = ap.parse_args()
    main(a.quick, a.i_max, a.rho)
