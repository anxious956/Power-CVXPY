"""
Static checks of the high-resistance design point at the window's centre (review of the A-G-only design, point 1):
R_top 160 ohm, delta = 1.12 pu at 328 deg, rho = 0, the structured design tier (src/highr_ag_design.py). Separation on
the search tier, the separating window (1 deg steps), the dense tier at remainder factors 1.0 / 1.1 / 1.25, and the
witness gaps of the binding cases (in units of the white box).

    python src/highr_static_checks.py      -> results/network/highr_static_checks.json
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import three_bus
from highr_ag_design import cases_for, INSTR, WHITE

OUT = os.path.join(HERE, "..", "results", "network", "highr_static_checks.json")
R_TOP, MAG, ANG, RHO = 160, 1.12, 328.0, 0.0


def model(**kw):
    base = dict(n_samples=150, face_pts=3, seed=1, eps=np.array(WHITE + WHITE), factor=1.1, drift_deg=3.0,
                ref_phi=0.030333432167374483, model_err=0.008, instr=INSTR)
    base.update(kw)
    return fr.FrameModel(three_bus(), cases_for(R_TOP), **base)


def main():
    t0 = time.time()
    d = MAG * np.exp(1j * np.radians(ANG))
    fm = model()
    res = dict(r_top=R_TOP, mag=MAG, angle=ANG, rho=RHO, separated_search=bool(fr.separated(fm, d, RHO)))
    print(f"search tier, 1.12 pu at 328 deg: separated {res['separated_search']}  [{time.time() - t0:.0f} s]", flush=True)
    res["window_deg"] = fr.window(fm, MAG, RHO, center_deg=ANG, half_width_deg=8, step_deg=1.0)
    print(f"window: {res['window_deg']}  [{time.time() - t0:.0f} s]", flush=True)
    binding = [tuple(c) for c in fr.unseparated(fm, 0j, RHO)]
    scale = np.array(WHITE + WHITE)
    res["witness_gap_box"] = {str(c): float(fr.witness(fm, d, c)["gap"] / 0.02) for c in binding}
    g = sorted(res["witness_gap_box"].items(), key=lambda kv: kv[1])[:5]
    print(f"smallest witness gaps (pu / 0.02, the voltage box): {g}  [{time.time() - t0:.0f} s]", flush=True)
    res["dense_factor_check"] = {}
    for f in (1.0, 1.1, 1.25):
        res["dense_factor_check"][str(f)] = bool(fr.separated(model(n_samples=400, face_pts=5, seed=2, factor=f), d, RHO))
        print(f"dense tier, factor {f}: separated {res['dense_factor_check'][str(f)]}  [{time.time() - t0:.0f} s]", flush=True)
    json.dump(res, open(OUT, "w"), indent=1)
    print("-> results/network/highr_static_checks.json")


if __name__ == "__main__":
    main()
