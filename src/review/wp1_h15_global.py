"""
H15: is the alternating scheme's delta the global minimum-norm separating delta?

For one (N, F) pair the set of NON-separating d is {d : dc + dH d in Z}, the preimage of a
zonotope under an affine map of the 2-D d-plane, hence a convex polygon. The separating set is
the complement of the union of 30 convex polygons: non-convex by construction. We compute every
polygon from 180 support LPs (outer polygon = halfplane intersection), classify a 0.01-pu grid
over |d| <= 1.5, and find the exact minimum-norm point outside all polygons (edge projections and
edge-edge intersections). Then the author's alternating scheme (aux_signal_toy.py:237-262) is run
from random starts.

  python src/review/wp1_h15_global.py [preset ...]        (~25 s per preset + ~15 s per 10 starts)
"""
import sys, time
import numpy as np
from wp1_common import (PRESETS, ModelSet, ms_polygons, grid_separating, exact_min, components,
                        alternating, dump, OUTDIR, dist_inf, bracket_min)
import json, os

REPORTED = {k: json.load(open(os.path.join(OUTDIR, "..", f"aux_signal_toy_{k}.json")))["cvxpy_opt"]
            for k in PRESETS}


def run(preset, n_starts=8, seed=0):
    p = PRESETS[preset]
    ms = ModelSet(p)
    t0 = time.time()
    polys = ms_polygons(ms, cache=("lin", preset))
    ax, ok = grid_separating(polys, R=1.5, step=0.01)
    RE, IM = np.meshgrid(ax, ax)
    disk = np.abs(RE + 1j * IM) <= 1.5
    sep = ok & disk
    nonsep = (~ok) & disk
    br = bracket_min(ms, polys)
    dstar = br.get("best_point")
    rep = REPORTED[preset]
    rep_d = complex(rep[0], rep[1])
    out = dict(preset=preset, reported=[rep_d, abs(rep_d)], grid_points_in_disk=int(disk.sum()),
               separating_fraction_outer_polygons=float(sep.sum() / disk.sum()),
               separating_components=components(sep), nonseparating_components=components(nonsep),
               bracket_margin0=br)
    if dstar is not None:
        mg = ms.margins(dstar)
        out.update(global_min=[dstar, abs(dstar), float(np.degrees(np.angle(dstar)))],
                   lp_min_margin_at_global=float(mg.min()),
                   reported_over_global=(abs(rep_d) / abs(dstar)) if abs(dstar) > 1e-9 else None)
    else:
        out.update(global_min=None)
    # same question with the author's tau = 1e-3 read as an inf-norm margin (apples to apples):
    # margin >= 1e-3  <=>  separation with the noise half-width inflated by 5e-4
    ms_t = ModelSet(p, eps=p.eps + 5e-4)
    polys_t = ms_polygons(ms_t, cache=("lin_tau", preset))
    br_t = bracket_min(ms_t, polys_t)
    out["bracket_margin_1e-3"] = br_t
    dt = br_t.get("best_point")
    out["global_min_margin_1e-3"] = None if dt is None else [dt, abs(dt), float(np.degrees(np.angle(dt)))]
    out["t_polygons_grid_s"] = time.time() - t0

    # ---- random starts of the author's scheme and of the normalized variant
    rng = np.random.default_rng(seed)
    starts = []
    sep_idx, non_idx = np.argwhere(sep), np.argwhere(nonsep)
    for idx in rng.choice(len(sep_idx), min(n_starts, len(sep_idx)), replace=False):
        j, i = sep_idx[idx]; starts.append(("separating", complex(ax[i], ax[j])))
    if len(non_idx):
        for idx in rng.choice(len(non_idx), min(n_starts // 2, len(non_idx)), replace=False):
            j, i = non_idx[idx]; starts.append(("non-separating", complex(ax[i], ax[j])))
    runs = []
    t1 = time.time()
    for kind, d0 in starts:
        da, ha, sa = alternating(ms, d0, lam_mode="author", iters=15)
        dn, hn, sn = alternating(ms, d0, mu=1e-3, lam_mode="normalized", iters=30)
        mna = ms.margins(da).min(); mnn = ms.margins(dn).min()
        runs.append(dict(start_kind=kind, d0=d0, author_d=da, author_abs=abs(da), author_status=sa,
                         author_min_margin=float(mna), normalized_d=dn, normalized_abs=abs(dn),
                         normalized_status=sn, normalized_min_margin=float(mnn)))
    out["starts"] = runs
    out["t_starts_s"] = time.time() - t1

    # ---- plot
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axp = plt.subplots(figsize=(7, 6.4))
    axp.contourf(RE, IM, np.where(disk, sep.astype(float), np.nan), levels=[-0.5, 0.5, 1.5],
                 colors=["#f2c9c4", "#cfe8cf"])
    for poly in polys:
        if poly is None:
            continue
        V = poly[2]
        axp.fill(V[:, 0], V[:, 1], fill=False, lw=0.5, color="0.4")
    axp.plot(rep_d.real, rep_d.imag, "bs", ms=8, label=f"reported |δ|={abs(rep_d):.3f}")
    if dstar is not None:
        axp.plot(dstar.real, dstar.imag, "k*", ms=13, label=f"global min |δ|={abs(dstar):.3f}")
    for r in runs:
        axp.plot(r["d0"].real, r["d0"].imag, "o", mfc="none", mec="0.3", ms=5)
        if r["author_status"] == "converged":
            axp.annotate("", xy=(r["author_d"].real, r["author_d"].imag), xytext=(r["d0"].real, r["d0"].imag),
                         arrowprops=dict(arrowstyle="->", color="tab:blue", lw=0.7))
        if r["normalized_status"] in ("converged", "maxiter"):
            axp.plot(r["normalized_d"].real, r["normalized_d"].imag, "x", color="tab:purple", ms=6)
    axp.plot([], [], "o", mfc="none", mec="0.3", label="random starts")
    axp.plot([], [], "x", color="tab:purple", label="normalized scheme end")
    axp.plot([], [], color="tab:blue", label="author scheme (converged)")
    axp.set_aspect("equal"); axp.set_xlim(-1.5, 1.5); axp.set_ylim(-1.5, 1.5)
    axp.set_xlabel("Re δ (pu)"); axp.set_ylabel("Im δ (pu)")
    axp.set_title(f"{preset}: green = separates all 30 grid faults (0.01 grid)\n"
                  f"grey outlines = non-separating polygon per fault case")
    axp.legend(fontsize=7, loc="lower left"); axp.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, f"h15_{preset}.png"), dpi=130); plt.close()
    return out


if __name__ == "__main__":
    presets = sys.argv[1:] or ["easy", "weak_sg", "weak_sg_eps12", "weak_sg_noisy", "all_ibr", "all_ibr_hard"]
    allr = {}
    for pr in presets:
        r = run(pr)
        allr[pr] = r
        g = r["global_min"]
        print(f"[{pr}] reported |d|={r['reported'][1]:.4f}  global min "
              f"{'none in |d|<=1.5' if g is None else f'{g[1]:.4f} at {g[2]:.1f} deg'}  "
              f"[bracket {r['bracket_margin0']['lower']}, {r['bracket_margin0']['upper']}] (with margin 1e-3: {'none' if r['global_min_margin_1e-3'] is None else round(r['global_min_margin_1e-3'][1],4)})  sep fraction {r['separating_fraction_outer_polygons']:.3f}  components sep/non {r['separating_components']}/"
              f"{r['nonseparating_components']}  ({r['t_polygons_grid_s']:.0f}s)", flush=True)
        for s in r["starts"]:
            print(f"    start {s['start_kind']:14s} |d0|={abs(s['d0']):.3f} -> author {s['author_status']:18s} "
                  f"|d|={s['author_abs']:.4f} (min margin {s['author_min_margin']:.2e}) ; normalized "
                  f"{s['normalized_status']:10s} |d|={s['normalized_abs']:.4f} (min margin {s['normalized_min_margin']:.2e})", flush=True)
        dump(allr, "h15_global.json" if len(presets) > 1 else f"h15_{pr}.json")
