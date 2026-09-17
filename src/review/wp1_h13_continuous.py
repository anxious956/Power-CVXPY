"""
H13: the separation guarantee holds only on the 5 x 3 grid of (m, mr) per fault type.

Part A  dense check at the reported delta: m in [0.15, 0.95] (the span of Params.m_grid) and in
        [0.01, 0.99] (m = 0 and m = 1 are singular in aux_model.solve), 200 x 50 points in (m, mr),
        both fault types, LP per point (interval-hull prefilter first, which is a sufficient test).
Part B  Monte Carlo over the uncertainty: random fault type, m ~ U[0.15, 0.95], mr ~ U[0, 1],
        sources either from the design's linear box or from the true (rotated) sector, noise
        ~ U[-eps, eps] per real component; a sample is AMBIGUOUS if the measured y lies in the
        normal zonotope N(delta) (LP membership, single noise box). Also the converse: true-source
        normal-operation samples that fall OUTSIDE N(delta) (the relay would reject normal operation).
Part C  refinement: add the unseparated dense points to the fault set, recompute the global minimum
        (polygons), re-check densely, repeat until the 200 x 50 grid on [0.15, 0.95] is clean.
        This is still a sampled guarantee (see the report for the Lipschitz alternative).

  python src/review/wp1_h13_continuous.py [preset ...]    (~3-6 min per preset)
"""
import os, sys, json, time
import numpy as np
from wp1_common import (PRESETS, ModelSet, affine_case, polygon, exact_min, dist_inf, dump, OUTDIR,
                        sample_true_sources, sample_linear_sources, realify, solve, ms_polygons, bracket_min)


def box_separated(v, G, e):
    return np.any(np.abs(v) > np.abs(G).sum(1) + e + 1e-12)


def dense_check(ms, d, m_axis, mr_axis, scen=("ag", "ab")):
    p, e = ms.p, 2 * ms.eps
    dv = np.array([d.real, d.imag])
    cN, HN, GN = ms.N
    bad, minm = [], np.inf
    for s in scen:
        for m in m_axis:
            for mr in mr_axis:
                cF, HF, GF = affine_case(p, s, m, mr, ms.mode)
                v = (cF - cN) + (HF - HN) @ dv
                G = np.hstack([GN, GF])
                if box_separated(v, G, e):
                    continue
                dist = dist_inf(v, G, e)
                minm = min(minm, dist)
                if dist <= 1e-9:
                    bad.append((s, float(m), float(mr)))
    return bad, minm


def monte_carlo(ms, d, n, rng, source="linear"):
    p, eps = ms.p, ms.eps
    dv = np.array([d.real, d.imag])
    cN, HN, GN = ms.N
    cNd = cN + HN @ dv
    sampler = sample_linear_sources if source == "linear" else sample_true_sources
    sL, iR = sampler(p, rng, n)
    scen = rng.choice(["ag", "ab"], n)
    m = rng.uniform(0.15, 0.95, n); mr = rng.uniform(0, 1, n)
    amb, amb_cases = 0, []
    rad = np.abs(GN).sum(1) + eps
    for k in range(n):
        y = realify(solve(p, scen[k], sL[k], iR[k], d, m[k], mr[k])) + rng.uniform(-eps, eps, cNd.size)
        v = y - cNd
        if np.any(np.abs(v) > rad + 1e-12):
            continue
        if dist_inf(v, GN, eps) <= 1e-9:
            amb += 1
            if len(amb_cases) < 20:
                amb_cases.append((str(scen[k]), float(m[k]), float(mr[k])))
    # normal operation with the same source sampler: outside the N zonotope?
    sL2, iR2 = sampler(p, rng, n)
    outside = 0
    for k in range(n):
        y = realify(solve(p, "N", sL2[k], iR2[k], d, 0.5, 0.0)) + rng.uniform(-eps, eps, cNd.size)
        v = y - cNd
        if np.any(np.abs(v) > rad + 1e-12) or dist_inf(v, GN, eps) > 1e-9:
            outside += 1
    return dict(n=n, ambiguous_fault_samples=amb, ambiguous_examples=amb_cases, normal_samples_outside_N=outside)


def refine(ms, pr, m_axis, mr_axis, max_rounds=8):
    polys = list(ms_polygons(ms, cache=("lin", pr)))
    rounds = []
    for it in range(max_rounds):
        d = bracket_min(ms, polys).get("best_point")
        if d is None:
            rounds.append(dict(round=it, delta=None, n_faults=len(ms.faults)))
            break
        bad, minm = dense_check(ms, d, m_axis, mr_axis)
        rounds.append(dict(round=it, delta=[d, abs(d), float(np.degrees(np.angle(d)))], n_faults=len(ms.faults),
                           dense_unseparated=len(bad), dense_min_margin=float(minm)))
        print(f"   refine round {it}: |d|={abs(d):.4f} at {np.degrees(np.angle(d)):.1f} deg, faults in design "
              f"{len(ms.faults)}, dense unseparated {len(bad)}", flush=True)
        if not bad:
            break
        # add at most 40 new cases per round, spread over the violating set
        idx = np.linspace(0, len(bad) - 1, min(40, len(bad))).round().astype(int)
        for j in sorted(set(idx)):
            ms.add(bad[j])
            polys.append(polygon(*ms.pair(ms.faults[-1]), 2 * ms.eps))
    return rounds


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("presets", nargs="*", default=["weak_sg", "weak_sg_noisy", "all_ibr_hard"])
    ap.add_argument("--nm", type=int, default=200)
    ap.add_argument("--nmr", type=int, default=50)
    ap.add_argument("--nmc", type=int, default=5000)
    ap.add_argument("--rounds", type=int, default=8)
    args = ap.parse_args()
    presets = args.presets
    out = dict(settings=vars(args))
    m_span = np.linspace(0.15, 0.95, args.nm)
    m_full = np.linspace(0.01, 0.99, args.nm)
    mr_axis = np.linspace(0, 1, args.nmr)
    for pr in presets:
        t0 = time.time()
        p = PRESETS[pr]
        ms = ModelSet(p)
        rep = json.load(open(os.path.join(OUTDIR, "..", f"aux_signal_toy_{pr}.json")))["cvxpy_opt"]
        d = complex(rep[0], rep[1])
        row = dict(reported=[d, abs(d)])
        grid_bad = [f[0] for f, mg in zip(ms.faults, ms.margins(d)) if mg <= 1e-9]
        row["grid_unseparated_at_reported"] = len(grid_bad)
        for lbl, ax in (("span_0.15_0.95", m_span), ("full_0.01_0.99", m_full)):
            bad, minm = dense_check(ms, d, ax, mr_axis)
            ms_ = sorted({b[1] for b in bad}); mrs_ = sorted({b[2] for b in bad})
            row[f"dense_{lbl}"] = dict(points=2 * len(ax) * len(mr_axis), unseparated=len(bad),
                                       by_type={s: sum(b[0] == s for b in bad) for s in ("ag", "ab")},
                                       m_range=[ms_[0], ms_[-1]] if bad else None,
                                       mr_range=[mrs_[0], mrs_[-1]] if bad else None)
            print(f"[{pr}] |d|={abs(d):.4f} dense {lbl}: {len(bad)}/{2*len(ax)*len(mr_axis)} unseparated "
                  f"{row[f'dense_{lbl}']['by_type']} m {row[f'dense_{lbl}']['m_range']} mr {row[f'dense_{lbl}']['mr_range']}",
                  flush=True)
        rng = np.random.default_rng(1)
        for src in ("linear", "true"):
            mc = monte_carlo(ms, d, args.nmc, rng, src)
            row[f"mc_{src}"] = mc
            print(f"[{pr}] MC sources={src}: ambiguous fault samples {mc['ambiguous_fault_samples']}/{mc['n']}, "
                  f"normal samples outside N {mc['normal_samples_outside_N']}/{mc['n']}", flush=True)
        ms_ref = ModelSet(p)
        row["refinement"] = refine(ms_ref, pr, m_span, mr_axis, max_rounds=args.rounds)
        final = row["refinement"][-1]
        if final.get("delta") is not None:
            dfin = final["delta"][0]
            bad_full, _ = dense_check(ms_ref, dfin, m_full, mr_axis)
            row["refined_full_range_unseparated"] = len(bad_full)
            mc = monte_carlo(ModelSet(p), dfin, args.nmc, np.random.default_rng(2), "linear")
            row["refined_mc_linear"] = mc
            print(f"[{pr}] refined |d|={abs(dfin):.4f}: full-range dense unseparated {len(bad_full)}, MC linear ambiguous "
                  f"{mc['ambiguous_fault_samples']}/{mc['n']}", flush=True)
        row["runtime_s"] = time.time() - t0
        out[pr] = row
        dump(out, f"h13_continuous_{'_'.join(presets)}_{args.nm}x{args.nmr}.json")


if __name__ == "__main__":
    main()
