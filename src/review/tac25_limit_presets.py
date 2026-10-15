"""results/DESIGN.md section 3 re-run with sound per-phase limit rows (bridge review B5): the smallest
separating |delta| on the toy presets for each way of putting the inverter current limit into the problem.

Section 3's table was a scratch run under the sum rule |i+| <= I_max - |delta|, which is unsound for a
per-phase limiter (tac25_design module docstring). This makes it reproducible and adds the sound rules.

COLUMNS  (tac25_design.min_delta, global polar solve, linear source set as in section 3, I_max = 1.2 pu)
  none          no limit at all                                (should match the exact optima to the grid step)
  h5_outer      H5's reading (a): reject delta with |i+|max + |delta| > I_max
  sum           |i+| <= I_max - |delta|                        (section 3 as first published)
  phase_disc    |i+| <= (-|delta| + sqrt(4 I_max^2 - 3 |delta|^2)) / 2   (the bridge review's scratch re-check)
  phase         every phase current <= I_max, the exact set for a per-phase limiter
  tac25         TAC25's (1b) as written, ||i+|| <= I_max
and for every feasible answer the smallest per-phase limit at which it can be injected on top of every
modelled i+ (tac25_design.injectable_limit), and the dense continuous (m, R_f) re-check (H13): an answer
that fails it separates the design points but not the faults between them, so it is no design.

    python src/review/tac25_limit_presets.py [--quick]   -> results/review_wp1/tac25_limit_presets.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aux_model as am
from wp1_common import ModelSet
import tac25_design as td
from review import common as cm

OUT = os.path.join(cm.ROOT, "results", "review_wp1", "tac25_limit_presets.json")
PRESETS = ("weak_sg", "weak_sg_noisy", "all_ibr_hard", "weak_sg_eps12")
EXACT = {"weak_sg": 0.5040, "weak_sg_noisy": 0.6908, "all_ibr_hard": 0.3863, "weak_sg_eps12": 1.3186}  # tac25_theorem1
COLUMNS = ("none", "h5_outer", "sum", "phase_disc", "phase", "tac25")
I_MAX = 1.2
WORKERS = 8


def solve(job):
    preset, col, r_step, n_ang = job
    ms = ModelSet(am.PRESETS[preset], mode="linear")
    t0 = time.time()
    kw = dict(i_max=I_MAX, rho=0.0, r_step=r_step, n_ang=n_ang)
    if col == "none":
        r = td.min_delta(ms, limit_inside=False, limit_design=False, r_max=2.0, **kw)
    elif col == "h5_outer":
        r = td.min_delta(ms, limit_inside=False, limit_design=True, **kw)
    else:
        r = td.min_delta(ms, limit_inside=True, limit_design=False, r_max=2.0, limit_rule=col, **kw)
    cont = None
    if r["feasible"] and col != "h5_outer":
        lim = col not in ("none",)
        cont = td.validate_continuous(ms.p, "linear", r["delta"], ms.eps, i_max=I_MAX if lim else None,
                                      limit_inside=lim, limit_rule=col if lim else "sum")
        cont = dict(holds=cont["holds"], n_unseparated=cont["n_unseparated"], n_checked=cont["n_checked"])
    return preset, col, dict(feasible=r["feasible"], abs_delta=r["abs_delta"], angle_deg=r["angle_deg"],
                             injectable_limit=r.get("injectable_limit"), i_plus_max=r["i_plus_max"],
                             continuous_check=cont, lps=r["lps"], runtime_s=time.time() - t0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="coarser delta grid")
    a = ap.parse_args()
    r_step, n_ang = (0.04, 36) if a.quick else (0.02, 72)
    t0 = time.time()
    from multiprocessing import Pool
    jobs = [(pr, col, r_step, n_ang) for pr in PRESETS for col in COLUMNS]
    res = {pr: dict(exact_no_limit=EXACT[pr]) for pr in PRESETS}
    with Pool(WORKERS) as pool:
        for pr, col, r in pool.imap_unordered(solve, jobs):
            res[pr][col] = r
            d = f"{r['abs_delta']:.2f} pu" if r["feasible"] else "none"
            inj = f"{r['injectable_limit']:.3f}" if r["feasible"] else "-"
            c = r["continuous_check"]
            cs = "" if c is None else ("  cont: ok" if c["holds"] else f"  cont: {c['n_unseparated']}/{c['n_checked']} FAIL")
            print(f"{pr:14s} {col:10s} {d:>8}  inject needs {inj}{cs}  [{r['runtime_s']:.0f}s]", flush=True)
    out = dict(script="tac25_limit_presets.py", commit=cm.git_commit(), mode="linear", i_max=I_MAX, r_step=r_step,
               n_ang=n_ang, columns=list(COLUMNS), presets=res, runtime_s=time.time() - t0)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    print("saved", OUT, f"[{out['runtime_s']:.0f}s]")
