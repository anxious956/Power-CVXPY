"""
delta* in the two-frame model as a function of the two budgets the review of PR #44 found to carry the result
(review/STEP3_PART2_REVIEW.md): the relay reference's rotation budget phi_ref, and a model-error box for the
static-vs-EMT difference. rho = 0.1, drift margin 3 deg (EMT drift beyond the fixed point is <= 2.2 deg in 4.8
cycles on the stored runs). Model error 0.1 eps and |delta| <= 1.05 pu, both measured in EMT with delta injected
(src/frames_emt_check.py: points outside their own set by <= 0.073 eps at 0.9 pu, none at 1.0 / 1.05 pu; at 1.14 pu
the inverter does not settle on bolted ab faults). For each configuration: delta* on the search tier, the separating angle window at
delta* in 1 deg steps, and separation at delta* on the dense tier at remainder factors 1.0 / 1.1 / 1.25.

    python src/frames_budget.py [workers]     -> results/network/frames_budget.json

Each worker takes ~1.2 GB, so the default is 3 in parallel (8 at once ran a 16 GB machine out of memory). Every
finished configuration is written at once; a rerun skips the ones already in the file.
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RHO, DRIFT = 0.1, 3.0
EPS = 0.08
PHIS = [0.0, 0.05, None]                    # None: eps / min|V1_L| (~0.085 rad); 0.0303 is src/frames_main.py
MODEL_ERRS = [0.1 * EPS]
R_MAX = 1.05
OUT = os.path.join(HERE, "..", "results", "network", "frames_budget.json")


def run(cfg):
    import frames as fr
    from pscad_network import three_bus
    from network_delta_test import CASES
    phi, me = cfg
    net = three_bus()
    t0 = time.time()
    fm = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, factor=1.1, drift_deg=DRIFT, ref_phi=phi, model_err=me)
    r = fr.min_delta_fast(fm, rho=RHO, r_max=R_MAX)
    out = dict(cfg=[phi, me], ref_phi=phi if phi is not None else float(fm.phi_max(0j)), ref_phi_rule="eps/min|V1_L|" if phi is None else "fixed",
               model_err=me, abs_delta=r["abs_delta"], angle_deg=r["angle_deg"],
               unseparated_at_0=len(r.get("unseparated_at_0", [])), inadmissible=r.get("inadmissible"))
    if r["feasible"]:
        out["window_deg"] = fr.window(fm, r["abs_delta"], RHO, center_deg=r["angle_deg"], half_width_deg=20)
        d = complex(*[r["d_cmd"].real, r["d_cmd"].imag])
        out["dense_factor_check"] = {}
        for f in (1.0, 1.1, 1.25):
            dense = fr.FrameModel(net, CASES, n_samples=400, face_pts=5, seed=2, factor=f, drift_deg=DRIFT, ref_phi=phi,
                                  model_err=me)
            out["dense_factor_check"][str(f)] = bool(fr.separated(dense, d, RHO))
        S = np.vstack(fm.samples)
        e, ic = fm.sources(S)
        _, _, u = fm.normal_state(S, d)
        i1, _ = fr.limiter_vec(ic * u, d * u, fm.i_max, 1)
        out["inverter_current_left"] = [float(np.abs(i1).min()), float(np.median(np.abs(i1))), float(np.abs(i1).max())]
    out["seconds"] = time.time() - t0
    return out


def main(workers=3):
    done = json.load(open(OUT))["runs"] if os.path.exists(OUT) else []
    have = {tuple(q["cfg"]) for q in done if "cfg" in q}
    cfgs = [(p, m) for p in PHIS for m in MODEL_ERRS if (p, m) not in have]
    print(f"{len(have)} configurations already done, {len(cfgs)} to run, {workers} at a time", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run, c) for c in cfgs]
        for f in as_completed(futs):
            q = f.result()
            done.append(q)
            json.dump(dict(rho=RHO, drift_deg=DRIFT, eps=EPS, r_max=R_MAX, runs=done), open(OUT, "w"), indent=1)
            print(f"phi_ref {q['ref_phi']:.3f} rad, model err {q['model_err'] / EPS:.2f} eps: delta* {q['abs_delta']} at "
                  f"{q['angle_deg']} deg; window {q.get('window_deg')}; dense factors {q.get('dense_factor_check')}; "
                  f"inverter current left {q.get('inverter_current_left')}  [{q['seconds']:.0f} s]", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
