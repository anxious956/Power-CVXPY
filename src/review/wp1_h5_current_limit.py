"""
H5: the design has no inverter current limit.

Base assumed: system per unit in which the IBR rating is 1.0 pu, so the preset nominal remote IBR
output i0 = 0.9 pu is 90 % loading and the current limit is I_max = 1.2 pu (Sandia gap analysis
1.1-1.2 pu). delta is injected by the remote IBR (aux_model.py:48, 79).

Three constraint forms, each enforced for the WORST CASE over the i+ uncertainty set:
  sum      : max|i+| + |delta| <= I_max                               (triangle bound)
  phase    : max_k max_{i+} |i+ + a^{2k} delta| <= I_max              (per-phase peak, exact)
  paper2   : |i+|^2 + |delta|^2 <= I_max^2, i.e. ||A[0,i+,delta]||_2 <= sqrt(3) I_max
             (the form printed in Geometry of Distance Protection, Sec. II-B)
and for two i+ sets: the design's linear box (its 4 vertices; what the tool believes) and the true
sector (outer arc sampled with 2000 points; what the inverter experiences).

The design with the constraint = minimum-norm d outside all 30 non-separating polygons and inside
the (convex) current-limit region. Candidates: exact_min restricted to the region, plus a
0.005-pu grid (the optimum may sit on the current-limit boundary, which exact_min does not enumerate).

  python src/review/wp1_h5_current_limit.py       (~1 min with the polygon cache from H15)
"""
import os, json, time
import numpy as np
from wp1_common import PRESETS, ModelSet, ms_polygons, exact_min, global_min_on_grid, source_sets, dump, OUTDIR, bracket_min, as_inner

IMAX = 1.2
A2 = np.exp(2j * np.pi / 3) ** 2


def iplus_points(p, which):
    if which == "linear":
        _, (c, g) = source_sets(p, "linear")
        return np.array([c + s1 * g[0] + s2 * g[1] for s1 in (-1, 1) for s2 in (-1, 1)])
    r0, ph0, a, gg = abs(p.i0), np.angle(p.i0), p.gen_i[0], p.gen_i[1]
    th = np.linspace(-gg, gg, 2000)
    return np.concatenate([(r0 + a) * np.exp(1j * (ph0 + th)), (r0 - a) * np.exp(1j * (ph0 + np.array([-gg, gg])))])


def make_mask(P, form):
    maxmod = np.abs(P).max()

    def mask(D):
        D = np.asarray(D)
        shp = D.shape
        d = D.ravel()
        if form == "sum":
            ok = maxmod + np.abs(d) <= IMAX + 1e-12
        elif form == "paper2":
            ok = maxmod ** 2 + np.abs(d) ** 2 <= IMAX ** 2 + 1e-12
        else:
            ok = np.ones(d.shape, bool)
            for k in range(3):
                w = (A2 ** k) * d
                for c0 in range(0, len(d), 4096):
                    wc = w[c0:c0 + 4096]
                    peak = np.abs(P[None, :] + wc[:, None]).max(1)
                    ok[c0:c0 + 4096] &= peak <= IMAX + 1e-12
        return ok.reshape(shp)
    return mask


def peak_phase(P, d):
    return float(max(np.abs(P + (A2 ** k) * d).max() for k in range(3)))


def main():
    t0 = time.time()
    res = dict(imax=IMAX, base="IBR rating = 1.0 pu (i0 = 0.9 pu nominal), I_max = 1.2 pu", presets={})
    for pr in ("easy", "weak_sg", "weak_sg_eps12", "weak_sg_noisy", "all_ibr", "all_ibr_hard"):
        p = PRESETS[pr]
        ms = ModelSet(p)
        polys = ms_polygons(ms, cache=("lin", pr))
        d_un = bracket_min(ms, polys).get("best_point")
        row = dict(unconstrained=None if d_un is None else [d_un, abs(d_un)])
        for which in ("linear", "true"):
            P = iplus_points(p, which)
            row[f"max_abs_iplus_{which}"] = float(np.abs(P).max())
            if d_un is not None:
                row[f"required_imax_phase_at_unconstrained_{which}"] = peak_phase(P, d_un)
                row[f"required_imax_sum_at_unconstrained_{which}"] = float(np.abs(P).max() + abs(d_un))
            for form in ("sum", "phase", "paper2"):
                mask = make_mask(P, form)
                feas0 = bool(mask(np.array([0j]))[0])
                cand = exact_min(polys, 1.5, mask_fn=mask)
                gbest, _, _ = global_min_on_grid(polys, R=1.5, step=0.005, mask_fn=mask)
                lower = exact_min(as_inner(polys), 1.5, mask_fn=mask)
                opts = [c for c in (cand, gbest) if c is not None]
                best = min(opts, key=abs) if opts else None
                if best is not None and d_un is not None and bool(mask(np.array([d_un]))[0]):
                    best = d_un                                  # unconstrained optimum already feasible
                row[f"{which}_{form}"] = dict(feasible_at_delta0=feas0,
                                              lower_bound=None if lower is None else abs(lower),
                                              optimum=None if best is None else [best, abs(best)],
                                              optimum_margin=None if best is None else float(ms.margins(best).min()))
        res["presets"][pr] = row
        print(f"[{pr}] unconstrained {None if d_un is None else round(abs(d_un), 4)} | max|i+| linear "
              f"{row['max_abs_iplus_linear']:.3f} true {row['max_abs_iplus_true']:.3f}", flush=True)
        for which in ("linear", "true"):
            s = "   " + which + ": "
            for form in ("sum", "phase", "paper2"):
                o = row[f"{which}_{form}"]
                s += f"{form}: feas@0={o['feasible_at_delta0']} opt={None if o['optimum'] is None else round(o['optimum'][1], 4)}; "
            if d_un is not None:
                s += f"required I_max (phase) at unconstrained optimum {row[f'required_imax_phase_at_unconstrained_{which}']:.3f}"
            print(s, flush=True)
    res["runtime_s"] = time.time() - t0
    dump(res, "h5_current_limit.json")


if __name__ == "__main__":
    main()
