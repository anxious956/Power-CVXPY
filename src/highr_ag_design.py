"""
The high-resistance design with realistic fault types (review/HIGHR_REVIEW.md): high fault resistance is a ground-
fault phenomenon, a phase-phase fault carries only arc resistance. Case set for a top resistance R_top:

  A-G  the design's eight locations x R_f in {0, 40, 80, ..., R_top} ohm (R_f / rF = 0, 1, 2, ...)
  B-C  the same locations x R_f in {0, 5} ohm (arc resistance)

Two-frame design with the structured design tier (src/frames_structured.py: per-phase CT 1 % / 0.3 deg, VT 0.5 % /
0.3 deg as shared symbols; white noise V 0.02 / I 0.04 pu in the box), cap 1.14 pu (filtered reference), the full
polar search of frames.min_delta_fast, rho = 0 and 0.1, for R_top = 120, 160 and 200 ohm.

    python src/highr_ag_design.py [workers]      -> results/network/highr_ag_design.json
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "..", "results", "network", "highr_ag_design.json")
deg = np.pi / 180
INSTR = dict(N=(0.005, 0.3 * deg, 0.01, 0.3 * deg), F=(0.005, 0.3 * deg, 0.01, 0.3 * deg))
WHITE = [0.02] * 3 + [0.04] * 3
LOCS = [("L1", m) for m in (0.15, 0.35, 0.55, 0.75, 0.95)] + [("L2", m) for m in (0.05, 0.25, 0.5)]


def cases_for(r_top_ohm):
    ag = [(ln, m, "ag", float(k)) for ln, m in LOCS for k in range(0, int(round(r_top_ohm / 40)) + 1)]
    bc = [(ln, m, "ab", mr) for ln, m in LOCS for mr in (0.0, 0.125)]
    return ag + bc


def run(job):
    import frames as fr
    from pscad_network import three_bus
    r_top, rho = job
    cases = cases_for(r_top)
    t0 = time.time()
    fm = fr.FrameModel(three_bus(), cases, n_samples=150, face_pts=3, seed=1, eps=np.array(WHITE + WHITE), factor=1.1,
                       drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.008, instr=INSTR)
    r = fr.min_delta_fast(fm, rho=rho, r_max=1.14)
    out = dict(r_top_ohm=r_top, rho=rho, n_cases=len(cases), abs_delta=r["abs_delta"], angle_deg=r["angle_deg"],
               feasible=r["feasible"], unseparated_at_0=[list(c) for c in r.get("unseparated_at_0", [])])
    if r["feasible"] and r["abs_delta"] > 0:
        d = r["d_cmd"]
        S = np.vstack(fm.samples)
        e, ic = fm.sources(S)
        _, _, u = fm.normal_state(S, d)
        i1, _ = fr.limiter_vec(ic * u, d * u, fm.i_max, 1)
        out["inverter_current_left"] = [float(np.abs(i1).min()), float(np.median(np.abs(i1))), float(np.abs(i1).max())]
        out["window_deg"] = fr.window(fm, r["abs_delta"], rho, center_deg=r["angle_deg"], half_width_deg=30, step_deg=1.0)
    else:
        # which cases block at the cap: unseparated at the largest radius, every 15 deg
        out["blocking_at_cap"] = {}
        for a in range(0, 360, 15):
            try:
                out["blocking_at_cap"][str(a)] = [list(c) for c in fr.unseparated(fm, 1.12 * np.exp(1j * np.radians(a)), rho)]
            except Exception as ex:
                out["blocking_at_cap"][str(a)] = str(type(ex).__name__)
    out["seconds"] = time.time() - t0
    return out


def main(workers=3):
    done = json.load(open(OUT))["runs"] if os.path.exists(OUT) else []
    have = {(q["r_top_ohm"], q["rho"]) for q in done}
    jobs = [(r, rho) for r in (120, 160, 200) for rho in (0.0, 0.1) if (r, rho) not in have]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for f in as_completed([ex.submit(run, j) for j in jobs]):
            q = f.result()
            done.append(q)
            json.dump(dict(instr={k: list(v) for k, v in INSTR.items()}, white=WHITE, runs=done), open(OUT, "w"), indent=1)
            print(f"R_top {q['r_top_ohm']} ohm, rho {q['rho']}: delta* {q['abs_delta']} at {q['angle_deg']} (feasible {q['feasible']}); "
                  f"unseparated at 0: {len(q['unseparated_at_0'])} of {q['n_cases']}; window {q.get('window_deg')}; "
                  f"I1 left {q.get('inverter_current_left')}  [{q['seconds']:.0f} s]", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
