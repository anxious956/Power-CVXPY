"""
The multi-frame fixed point of src/frames_multi.py: how many sample points need under-relaxation, and do relax 0.5 and
0.25 land on the same point (a cheap uniqueness check)? Per case (normal and the 50 hard cases), on the design's sample
set, at |delta| 0, 0.56, 1.12 and 1.14 pu (225 deg), plus dead frames at the cap. The relaxed point is the physical
one: a period-2 swing means the plain map has slope below -1, while the EMT frames follow first-order filter dynamics,
du/dt = (f(u) - u) / tau, which converge to the same point (review of f863c4f).

    python src/i2dir_fixedpoint_check.py   -> results/network/i2dir_fixedpoint_check.json
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from i2dir_design import model
from i2dir_static import FWD, REV

OUT = os.path.join(HERE, "..", "results", "network", "i2dir_fixedpoint_check.json")


def iterate(fm, mv, e, ic, d, u0, relax, iters):
    u = {k: v.copy() for k, v in u0.items()}
    for _ in range(iters):
        X, _, _ = fm._x(e, ic, d, u)
        step = np.zeros(len(e))
        for k in u:
            v = X @ mv[k]
            new = v / np.maximum(np.abs(v), 1e-12)
            new = (1 - relax) * u[k] + relax * new
            new /= np.maximum(np.abs(new), 1e-12)
            step = np.maximum(step, np.abs(new - u[k]))
            u[k] = new
    return u, step


def main():
    fm, _, _ = model(FWD + REV)
    S = np.vstack(fm.samples)
    e, ic = fm.sources(S)
    res = {}
    for mag in (0.0, 0.56, 1.12, 1.14):
        d = mag * np.exp(1j * np.radians(225))
        n_relax, n_total, worst_diff = 0, 0, 0.0
        _, _, u_pre = fm.normal_state(S, d)
        for k in [None] + list(range(len(fm.cases))):
            mv = fm.maps_N[1] if k is None else fm.maps_F[k][1]
            u0 = fm._u0(len(S)) if k is None else u_pre
            _, step = iterate(fm, mv, e, ic, d, u0, 1.0, 400)
            bad = step >= 1e-12
            n_relax += int(bad.sum())
            n_total += len(S)
            if bad.any():
                ua, _ = iterate(fm, mv, e[bad], ic[bad], d, {q: v[bad] for q, v in u0.items()}, 0.5, 2000)
                ub, _ = iterate(fm, mv, e[bad], ic[bad], d, {q: v[bad] for q, v in u0.items()}, 0.25, 6000)
                worst_diff = max(worst_diff, max(float(np.max(np.abs(ua[q] - ub[q]))) for q in ua))
        res[str(mag)] = dict(points=n_total, needing_relaxation=n_relax, relax_05_vs_025_max_diff=worst_diff)
        print(f"|delta| {mag:.2f} pu: {n_relax} of {n_total} sample-point fixed points need under-relaxation; "
              f"relax 0.5 vs 0.25 largest frame difference {worst_diff:.1e}", flush=True)
    dead = fm.dead_frames(1.14 * np.exp(1j * np.radians(225)))
    res["dead_frames_at_cap"] = [list(c) for c in dead]
    print(f"dead frames (any source bus |V1| < {fm.v1_min}) at 1.14 pu: {dead}")
    json.dump(res, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
