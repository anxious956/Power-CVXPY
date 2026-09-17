"""
H1 (detect.py part): detect.py:188-195 labels the weak_sg optimum "the smallest delta the design tool
can certify as separating", but its hard dataset (waveforms.make_dataset(hard=True)) uses as
negatives unbalanced_load (75 %) and load_step (25 %), and as positives ag faults with
mr in [0.85, 1]. The design's pre-test sets contain only N and the 30 grid faults. Here the
confuser sets are added as zonotopes and the separation is re-checked at the certified delta.

unbalanced_load (waveforms.py:83-93): post = solve(g_f, "N", srcL, iR + u, delta + u, inj0 = u),
  |u| in [0.05, 0.7], any angle; load factor f in [1.0, 1.4] on yld[1], yld[2].
  u enters affinely (iR, delta and inj0 each + u): generators from the outer box |Re u|,|Im u| <= 0.7
  (sound for the disc). f is not affine: pieces f in {1.0, 1.1, 1.2, 1.3, 1.4} (inner approximation).
load_step (waveforms.py:69-73): f in [1.3, 2.0] on yld[1], yld[2]; pieces f in {1.3, 1.475, 1.65, 1.825, 2.0}.
Faults: ag, m in Params.m_grid and a dense 0.1..0.95 grid, mr in {0.85, 0.925, 1.0}.
Sources: the design's linear box; noise box eps = 0.08.

  python src/review/wp1_h1_detect_confuser.py     (~1 min)
"""
import os, json, time
from dataclasses import replace
import numpy as np
from wp1_common import PRESETS, source_sets, realify, solve, dist_inf, dump, OUTDIR

p = PRESETS["weak_sg"]
eps = p.eps
rep = json.load(open(os.path.join(OUTDIR, "..", "aux_signal_toy_weak_sg.json")))["cvxpy_opt"]
D_REP = complex(rep[0], rep[1])


def affine_generic(fun):
    """fun(sL, iR, delta, u) -> complex 6-vector; returns c, H (d), G (sources + optional u)."""
    (sL0, gL), (iR0, gR) = source_sets(p, "linear")
    y0 = fun(sL0, iR0, 0.0, 0.0)
    H = np.stack([realify(fun(sL0, iR0, dd, 0.0) - y0) for dd in (1.0, 1j)], 1)
    G = [fun(sL0 + g, iR0, 0.0, 0.0) - y0 for g in gL] + [fun(sL0, iR0 + g, 0.0, 0.0) - y0 for g in gR]
    return realify(y0), H, G, y0


def confuser_sets():
    sets = []
    for f in np.linspace(1.0, 1.4, 5):
        g = replace(p, yld={1: p.yld[1] * f, 2: p.yld[2] * f, 0: p.yld[0]})
        fun = lambda sL, iR, d, u, g=g: solve(g, "N", sL, iR + u, d + u, 0.5, 0.0, inj0=u)
        c, H, G, y0 = affine_generic(fun)
        (sL0, _), (iR0, _) = source_sets(p, "linear")
        G += [fun(sL0, iR0, 0.0, 0.7) - y0, fun(sL0, iR0, 0.0, 0.7j) - y0]
        sets.append((("unbalanced_load", round(float(f), 3)), c, H, np.stack([realify(x) for x in G], 1)))
    for f in np.linspace(1.3, 2.0, 5):
        g = replace(p, yld={1: p.yld[1] * f, 2: p.yld[2] * f, 0: p.yld[0]})
        fun = lambda sL, iR, d, u, g=g: solve(g, "N", sL, iR, d, 0.5, 0.0)
        c, H, G, _ = affine_generic(fun)
        sets.append((("load_step", round(float(f), 3)), c, H, np.stack([realify(x) for x in G], 1)))
    fun = lambda sL, iR, d, u: solve(p, "N", sL, iR, d, 0.5, 0.0)
    c, H, G, _ = affine_generic(fun)
    sets.append((("N", 1.0), c, H, np.stack([realify(x) for x in G], 1)))
    return sets


def fault_sets(m_axis):
    out = []
    for m in m_axis:
        for mr in (0.85, 0.925, 1.0):
            fun = lambda sL, iR, d, u, m=m, mr=mr: solve(p, "ag", sL, iR, d, m, mr)
            c, H, G, _ = affine_generic(fun)
            out.append((("ag", round(float(m), 3), mr), c, H, np.stack([realify(x) for x in G], 1)))
    return out


def count(conf, faults, d):
    dv = np.array([d.real, d.imag])
    res = {}
    for key, cN, HN, GN in conf:
        bad = 0
        for fk, cF, HF, GF in faults:
            if dist_inf((cF - cN) + (HF - HN) @ dv, np.hstack([GN, GF]), 2 * eps) <= 1e-9:
                bad += 1
        res[str(key)] = bad
    return res


def main():
    t0 = time.time()
    conf = confuser_sets()
    out = {}
    for lbl, ax in (("design_m_grid", list(p.m_grid)), ("dense_m_0.10_0.95", list(np.linspace(0.1, 0.95, 18)))):
        F = fault_sets(ax)
        for dl, d in (("delta0", 0j), ("certified_0.514", D_REP)):
            c = count(conf, F, d)
            out[f"{lbl}_{dl}"] = dict(n_fault_cases=len(F), unseparated_by_negative_set=c)
            print(f"{lbl:22s} {dl:16s}: of {len(F)} high-R ag fault cases, unseparated from ->", c, flush=True)
    out["runtime_s"] = time.time() - t0
    dump(out, "h1_detect_confuser.json")


if __name__ == "__main__":
    main()
