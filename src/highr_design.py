"""
Can the designed signal guarantee detection where conventional detection fails (src/highr_screen.py: the incremental
50N / 50Q falls below its calibrated pickup from about 160 ohm)? The two-frame design with the most favourable
instrument model, the structured design tier (src/frames_structured.py: per-phase CT 1 % / 0.3 deg, VT 0.5 % /
0.3 deg as shared symbols, white noise V 0.02 / I 0.04 pu in the box), no margin (rho = 0), cap 1.14 pu (filtered
reference), for A-G and B-C faults at the design's locations with R_f = 120, 160 and 200 ohm (R_f / rF = 3, 4, 5).

    python src/highr_design.py [workers]      -> results/network/highr_design.json
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "..", "results", "network", "highr_design.json")
deg = np.pi / 180
INSTR = dict(N=(0.005, 0.3 * deg, 0.01, 0.3 * deg), F=(0.005, 0.3 * deg, 0.01, 0.3 * deg))
WHITE = [0.02] * 3 + [0.04] * 3
LOCS = [("L1", m) for m in (0.15, 0.35, 0.55, 0.75, 0.95)] + [("L2", m) for m in (0.05, 0.25, 0.5)]


def run(mr):
    import frames as fr
    from pscad_network import three_bus
    cases = [(ln, m, s, mr) for s in ("ag", "ab") for ln, m in LOCS]
    t0 = time.time()
    fm = fr.FrameModel(three_bus(), cases, n_samples=150, face_pts=3, seed=1, eps=np.array(WHITE + WHITE), factor=1.1,
                       drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.008, instr=INSTR)
    r = fr.min_delta_fast(fm, rho=0.0, r_max=1.14)
    out = dict(rf_ohm=40 * mr, abs_delta=r["abs_delta"], angle_deg=r["angle_deg"], feasible=r["feasible"],
               unseparated_at_0=[list(c) for c in r.get("unseparated_at_0", [])], seconds=time.time() - t0)
    return out


def main(workers=3):
    done = json.load(open(OUT))["runs"] if os.path.exists(OUT) else []
    have = {q["rf_ohm"] for q in done}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for f in as_completed([ex.submit(run, mr) for mr in (3.0, 4.0, 5.0) if 40 * mr not in have]):
            q = f.result()
            done.append(q)
            json.dump(dict(instr={k: list(v) for k, v in INSTR.items()}, white=WHITE, rho=0.0, runs=done), open(OUT, "w"), indent=1)
            print(f"R_f {q['rf_ohm']:.0f} ohm: delta* {q['abs_delta']} at {q['angle_deg']} (feasible {q['feasible']}); "
                  f"unseparated at 0: {len(q['unseparated_at_0'])} of 16  [{q['seconds']:.0f} s]", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
