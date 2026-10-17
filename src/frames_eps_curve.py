"""
delta*(eps): the design's signal against the noise bound it assumes (review/STEP3_WORSTCASE_REVIEW.md), main
configuration otherwise (phi_ref 0.0303 rad, model error 0.008 pu, drift 3 deg, rho 0.1, cap 1.14 pu with the PLL-like
reference filter). Scalar bounds on every real component, plus the two front-end tiers as per-component bounds
(k = 4 white noise plus the largest systematic term on the pilot's fault measurements, results/step3/pilot_eval.json):

  design tier  V 0.029 / I 0.053 pu   (CT <= 1 %, VT <= 0.5 %, 0.3 deg: near-nominal accuracy)
  class tier   V 0.139 / I 0.168 pu   (CT 10 %, VT 6 %, VT phase 4 deg at the largest pilot measurements)

    python src/frames_eps_curve.py [workers]     -> results/network/frames_eps_curve.json (each point saved when done)
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "..", "results", "network", "frames_eps_curve.json")
POINTS = [("eps 0.03", 0.03, 0.03), ("eps 0.04", 0.04, 0.04), ("eps 0.05", 0.05, 0.05), ("eps 0.06", 0.06, 0.06),
          ("eps 0.08 (the design)", 0.08, 0.08), ("eps 0.10", 0.10, 0.10), ("eps 0.12", 0.12, 0.12),
          ("design tier", 0.029, 0.053), ("class tier", 0.139, 0.168)]
RHO, RMAX = 0.1, 1.14


def run(pt):
    import frames as fr
    from pscad_network import three_bus
    from network_delta_test import CASES
    label, ev, ei = pt
    half = [ev] * 3 + [ei] * 3
    t0 = time.time()
    fm = fr.FrameModel(three_bus(), CASES, n_samples=150, face_pts=3, seed=1, eps=np.array(half + half), factor=1.1,
                       drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.008)
    r = fr.min_delta_fast(fm, rho=RHO, r_max=RMAX)
    out = dict(label=label, eps_V=ev, eps_I=ei, abs_delta=r["abs_delta"], angle_deg=r["angle_deg"], feasible=r["feasible"],
               unseparated_at_0=len(r.get("unseparated_at_0", [])))
    if r["feasible"] and r["abs_delta"] > 0:
        d = r["d_cmd"]
        S = np.vstack(fm.samples)
        e, ic = fm.sources(S)
        _, _, u = fm.normal_state(S, d)
        i1, _ = fr.limiter_vec(ic * u, d * u, fm.i_max, 1)
        out["inverter_current_left"] = [float(np.abs(i1).min()), float(np.median(np.abs(i1))), float(np.abs(i1).max())]
    out["seconds"] = time.time() - t0
    return out


def main(workers=3):
    done = json.load(open(OUT))["points"] if os.path.exists(OUT) else []
    have = {q["label"] for q in done}
    todo = [p for p in POINTS if p[0] not in have]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for f in as_completed([ex.submit(run, p) for p in todo]):
            q = f.result()
            done.append(q)
            json.dump(dict(rho=RHO, r_max=RMAX, points=done), open(OUT, "w"), indent=1)
            print(f"{q['label']}: delta* {q['abs_delta']} at {q['angle_deg']} deg (feasible {q['feasible']}); unseparated at 0: "
                  f"{q['unseparated_at_0']}; I1 left {q.get('inverter_current_left')}  [{q['seconds']:.0f} s]", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
