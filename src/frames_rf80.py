"""
Option C of results/STEP3_PILOT.md, the static check first (review/STEP3_PILOT_REVIEW.md): the design with the fault
resistance range doubled to 80 ohm (R_f / rF in {0, 0.5, 1, 1.5, 2}, the same locations as network_delta_test.CASES),
main configuration otherwise (phi_ref 0.0303 rad, model error 0.1 eps, drift 3 deg, cap 1.14 pu with the PLL-like
reference filter), at the design's eps (0.08 pu) and at the front end's measured bound (V 0.029 / I 0.053 pu).

    python src/frames_rf80.py      -> results/network/frames_rf80.json
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import three_bus

MRS = (0.0, 0.5, 1.0, 1.5, 2.0)
CASES80 = [("L1", m, s, mr) for s in ("ag", "ab") for m in (0.15, 0.35, 0.55, 0.75, 0.95) for mr in MRS] + \
          [("L2", m, s, mr) for s in ("ag", "ab") for m in (0.05, 0.25, 0.5) for mr in MRS]
KW = dict(factor=1.1, drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.008)
HALF = [0.029] * 3 + [0.053] * 3
OUT = os.path.join(HERE, "..", "results", "network", "frames_rf80.json")


def run(label, eps, rho):
    net = three_bus()
    t0 = time.time()
    fm = fr.FrameModel(net, CASES80, n_samples=150, face_pts=3, seed=1, eps=eps, **KW)
    r = fr.min_delta_fast(fm, rho=rho, r_max=1.14)
    out = dict(label=label, rho=rho, abs_delta=r["abs_delta"], angle_deg=r["angle_deg"], feasible=r["feasible"],
               unseparated_at_0=[list(c) for c in r.get("unseparated_at_0", [])], seconds=time.time() - t0)
    if r["feasible"] and r["abs_delta"] > 0:
        d = r["d_cmd"]
        S = np.vstack(fm.samples)
        e, ic = fm.sources(S)
        _, _, u = fm.normal_state(S, d)
        i1, _ = fr.limiter_vec(ic * u, d * u, fm.i_max, 1)
        out["inverter_current_left"] = [float(np.abs(i1).min()), float(np.median(np.abs(i1))), float(np.abs(i1).max())]
    print(f"{label}, rho {rho}: delta* {out['abs_delta']} at {out['angle_deg']} deg; unseparated at 0: "
          f"{len(out['unseparated_at_0'])}; I1 left {out.get('inverter_current_left')}  [{out['seconds']:.0f} s]", flush=True)
    return out


def main():
    res = []
    for label, eps in (("measured bound", np.array(HALF + HALF)), ("design eps 0.08", None)):
        for rho in (0.0, 0.1):
            res.append(run(label, eps, rho))
            json.dump(dict(cases=len(CASES80), mrs=MRS, runs=res), open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
