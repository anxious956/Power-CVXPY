"""
delta* with the instrument errors as a STRUCTURED set (review/STEP3_CLASS_REVIEW.md): per-phase CT and VT ratio and
phase errors as shared symbols of the frame model (frames.FrameModel(instr=...)), regime-dependent, with only the
k = 4 white noise left in the box (V 0.02 / I 0.04 pu, the design tier's white noise after the mimic filter).

  class, regime-dependent   normal operation and the memory: CT 1 % / 1 deg, VT 3 % / 2 deg (a 5P CT at rated
                            current, a 3P VT near nominal); fault windows: CT 10 % / 1 deg, VT 6 % / 4 deg (the
                            fault-condition class figures); the two independent
  design tier               both regimes CT 1 % / 0.3 deg, VT 0.5 % / 0.3 deg

Main configuration otherwise (phi_ref 0.0303 rad, model error 0.008 pu, drift 3 deg, cap 1.14 pu, filtered reference),
faults up to 40 ohm.

    python src/frames_structured.py [workers]     -> results/network/frames_structured.json
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "..", "results", "network", "frames_structured.json")
deg = np.pi / 180
CONFIGS = {
    "class, regime-dependent": dict(N=(0.03, 2 * deg, 0.01, 1 * deg), F=(0.06, 4 * deg, 0.10, 1 * deg)),
    "design tier": dict(N=(0.005, 0.3 * deg, 0.01, 0.3 * deg), F=(0.005, 0.3 * deg, 0.01, 0.3 * deg)),
}
WHITE = [0.02] * 3 + [0.04] * 3


def run(job):
    import frames as fr
    from pscad_network import three_bus
    from network_delta_test import CASES
    label, rho = job
    t0 = time.time()
    fm = fr.FrameModel(three_bus(), CASES, n_samples=150, face_pts=3, seed=1, eps=np.array(WHITE + WHITE), factor=1.1,
                       drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.008, instr=CONFIGS[label])
    r = fr.min_delta_fast(fm, rho=rho, r_max=1.14)
    out = dict(label=label, rho=rho, instr={k: [float(x) for x in v] for k, v in CONFIGS[label].items()},
               abs_delta=r["abs_delta"], angle_deg=r["angle_deg"], feasible=r["feasible"],
               unseparated_at_0=[list(c) for c in r.get("unseparated_at_0", [])])
    if r["feasible"] and r["abs_delta"] > 0:
        d = r["d_cmd"]
        S = np.vstack(fm.samples)
        e, ic = fm.sources(S)
        _, _, u = fm.normal_state(S, d)
        i1, _ = fr.limiter_vec(ic * u, d * u, fm.i_max, 1)
        out["inverter_current_left"] = [float(np.abs(i1).min()), float(np.median(np.abs(i1))), float(np.abs(i1).max())]
    out["seconds"] = time.time() - t0
    return out


def main(workers=4):
    done = json.load(open(OUT))["runs"] if os.path.exists(OUT) else []
    have = {(q["label"], q["rho"]) for q in done}
    jobs = [(l, r) for l in CONFIGS for r in (0.0, 0.1) if (l, r) not in have]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for f in as_completed([ex.submit(run, j) for j in jobs]):
            q = f.result()
            done.append(q)
            json.dump(dict(white_box=WHITE, runs=done), open(OUT, "w"), indent=1)
            print(f"{q['label']}, rho {q['rho']}: delta* {q['abs_delta']} at {q['angle_deg']} deg (feasible {q['feasible']}); "
                  f"unseparated at 0: {len(q['unseparated_at_0'])}; I1 left {q.get('inverter_current_left')}  [{q['seconds']:.0f} s]", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
