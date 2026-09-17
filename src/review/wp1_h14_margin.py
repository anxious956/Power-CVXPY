"""
H14: separation margin.

aux_model.separated_lp returns only a boolean (LP infeasible) and aux_signal_toy.py:243-254 asks
for lam.(cF - cN) >= h_Z(lam) + tau with tau = 1e-3 and ||lam||_inf <= 1, i.e. in unnormalized
lambda units. Here the margin is measured as

    mu(d) = min over fault cases of  max_{||lam||_1 <= 1}  lam.(cF(d) - cN(d)) - h_Z(lam)
          = min over fault cases of  inf-norm distance from cF(d) - cN(d) to Z,

where Z contains the two noise boxes (half-width 2 eps). ||lam||_1 <= 1 is chosen because it is
the dual norm of the inf-norm, the norm the noise model uses (a box per real component): mu is
then in pu of measurement, and the design stays separating for every noise half-width up to
eps + mu/2. The redesign asks for mu >= 2 rho eps (separation survives eps -> (1 + rho) eps),
which is the same polygon problem with the noise box inflated to 2 eps + mu.

  python src/review/wp1_h14_margin.py        (~6-10 min, polygons cached in logs/cache)
"""
import os, json, time
import numpy as np
from wp1_common import PRESETS, ModelSet, ms_polygons, exact_min, alternating, dump, OUTDIR, bracket_min

PRESETS_USED = ["weak_sg", "weak_sg_noisy", "all_ibr_hard", "easy", "all_ibr"]
RHOS = [0.10, 0.25, 0.50]


def main():
    out = {}
    t0 = time.time()
    for pr in PRESETS_USED:
        p = PRESETS[pr]
        ms = ModelSet(p)
        rep = json.load(open(os.path.join(OUTDIR, "..", f"aux_signal_toy_{pr}.json")))["cvxpy_opt"]
        d_rep = complex(rep[0], rep[1])
        mg = ms.margins(d_rep)
        worst = int(np.argmin(mg))
        row = dict(eps=p.eps, reported=[d_rep, abs(d_rep)], margin_min_pu=float(mg.min()),
                   margin_min_over_eps=float(mg.min() / p.eps), worst_case=ms.faults[worst][0],
                   n_cases_margin_below_0p01eps=int((mg < 0.01 * p.eps).sum()),
                   noise_tolerance_eps_max=float(p.eps + mg.min() / 2))
        brb = bracket_min(ms, ms_polygons(ms, cache=("lin", pr)))
        base = brb.get("best_point")
        row["global_min_margin0"] = brb
        row["redesign"] = []
        for rho in RHOS:
            mu = 2 * rho * p.eps
            ms_mu = ModelSet(p, eps=p.eps + mu / 2)          # margin >= mu  <=>  separated with eps + mu/2
            polys = ms_polygons(ms_mu, cache=("lin_mu", pr, rho))
            br = bracket_min(ms_mu, polys)
            dm = br.get("best_point")
            r = dict(rho=rho, mu_pu=mu, bracket=br)
            if dm is None:
                r.update(global_min=None)
            else:
                r.update(global_min=[dm, abs(dm), float(np.degrees(np.angle(dm)))],
                         lp_margin_at_design=float(ms.margins(dm).min()))
                # the normalized alternating scheme with margin mu, started from the reported delta
                da, hist, st = alternating(ms, d_rep, mu=mu, lam_mode="normalized", iters=40)
                r.update(alternating_from_reported=[da, abs(da)], alternating_status=st,
                         alternating_margin=float(ms.margins(da).min()))
            row["redesign"].append(r)
        out[pr] = row
        print(f"[{pr}] eps={p.eps}  reported |d|={abs(d_rep):.4f}  margin {mg.min():.2e} pu "
              f"({mg.min()/p.eps:.2%} of eps, worst {row['worst_case']})  global min (margin 0) "
              f"{None if base is None else round(abs(base), 4)} [bracket {brb['lower']}, {brb['upper']}]", flush=True)
        for r in row["redesign"]:
            g = r["global_min"]
            if g is None:
                txt = "none in |d|<=1.5"
            else:
                txt = (f"{g[1]:.4f} at {g[2]:.1f} deg (LP margin {r['lp_margin_at_design']:.4f}; bracket [{r['bracket']['lower']:.4f}, {r['bracket']['upper']:.4f}]); "
                       f"alternating from reported: {r['alternating_from_reported'][1]:.4f} "
                       f"({r['alternating_status']}, margin {r['alternating_margin']:.4f})")
            print(f"     rho={r['rho']:.2f} mu={r['mu_pu']:.3f} pu -> global min {txt}", flush=True)
    out["runtime_s"] = time.time() - t0
    dump(out, "h14_margin.json")


if __name__ == "__main__":
    main()
