"""
H6: angle uncertainty linearized as 1j * gen * i0 (aux_model.py:104-108).

True source set (what the comments in aux_model.py:25,28 describe):
    S = { (r0 + a u1) e^{j(phi0 + g u2)} : |u1|, |u2| <= 1 }         (annular sector)
Linear box used by the design:
    L = { r0 e^{j phi0} (1 + (a/r0) u1 + j g u2) }
(for the SG the magnitude generator is relative: a = gen_e[0] * |e0|).

Part A: geometry. Directed Hausdorff distances h(S->L) (how far true points lie outside the
design set: unsoundness) and h(L->S) (spurious points), and the same for the sound outer box
wp1_common.sector_outer_box (radial extent [rmin cos g, rmax], tangential +-rmax sin g).
Part B: redesign with the outer box for weak_sg, weak_sg_noisy, all_ibr_hard (global min over
polygons + LP check at the reported delta).

  python src/review/wp1_h6_angle.py         (~3-5 min; polygons cached)
"""
import os, json, time
import numpy as np
from wp1_common import (PRESETS, ModelSet, ms_polygons, exact_min, sector_linear, sector_linear_rel,
                        sector_outer_box, dump, OUTDIR, bracket_min)


def box_points(c, gens, n=401):
    u = np.linspace(-1, 1, n)
    U1, U2 = np.meshgrid(u, u)
    return (c + gens[0] * U1 + gens[1] * U2).ravel()


def dist_to_box(z, c, gens):
    """Euclidean distance from complex points z to the parallelogram c + G[-1,1]^2 (exact, 2-D QP by clipping
    in generator coordinates is not exact for non-orthogonal G; our generators are orthogonal)."""
    G = np.array([[gens[0].real, gens[1].real], [gens[0].imag, gens[1].imag]])
    lens = np.linalg.norm(G, axis=0)
    Q = G / lens
    assert abs(Q[:, 0] @ Q[:, 1]) < 1e-9, "generators must be orthogonal"
    w = np.stack([(z - c).real, (z - c).imag])
    coords = Q.T @ w
    clipped = np.clip(coords, -lens[:, None], lens[:, None])
    return np.linalg.norm(coords - clipped, axis=0)


def dist_to_sector(z, phi0, rmin, rmax, g):
    """Exact Euclidean distance from points to the annular sector."""
    r, ph = np.abs(z), np.angle(z * np.exp(-1j * phi0))
    inside_ang = np.abs(ph) <= g
    d_in = np.where(r < rmin, rmin - r, np.where(r > rmax, r - rmax, 0.0))
    # outside the angular range: distance to the nearest radial edge segment
    best = np.full(z.shape, np.inf)
    for s in (-1, 1):
        e = np.exp(1j * (phi0 + s * g))
        t = np.clip((z * np.conj(e)).real, rmin, rmax)
        best = np.minimum(best, np.abs(z - t * e))
    return np.where(inside_ang, d_in, best)


def sector_boundary(phi0, rmin, rmax, g, n=4000):
    th = np.linspace(-g, g, n)
    rr = np.linspace(rmin, rmax, n)
    pts = [rmax * np.exp(1j * (phi0 + th)), rmin * np.exp(1j * (phi0 + th)),
           rr * np.exp(1j * (phi0 + g)), rr * np.exp(1j * (phi0 - g))]
    return np.concatenate(pts)


def geometry(label, s0, a_abs, g, relative=False):
    r0, phi0 = abs(s0), np.angle(s0)
    rmin, rmax = r0 - a_abs, r0 + a_abs
    if relative:
        c, gens = sector_linear_rel(s0, a_abs / r0, g)
    else:
        c, gens = sector_linear(s0, a_abs, g)
    co, go = sector_outer_box(s0, rmin, rmax, g)
    S = sector_boundary(phi0, rmin, rmax, g)
    out = dict(label=label, r0=r0, a=a_abs, g=g)
    out["h_true_to_linear"] = float(dist_to_box(S, c, gens).max())     # unsoundness
    out["h_linear_to_true"] = float(dist_to_sector(box_points(c, gens), phi0, rmin, rmax, g).max())
    out["h_true_to_outer"] = float(dist_to_box(S, co, go).max())       # must be 0
    out["h_outer_to_true"] = float(dist_to_sector(box_points(co, go), phi0, rmin, rmax, g).max())
    out["hausdorff_linear"] = max(out["h_true_to_linear"], out["h_linear_to_true"])
    out["linear_box_max_modulus"] = float(np.abs(box_points(c, gens, 81)).max())
    out["true_max_modulus"] = rmax
    out["outer_box_max_modulus"] = float(np.abs(box_points(co, go, 81)).max())
    rng = np.random.default_rng(0)
    u = rng.uniform(-1, 1, (200000, 2))
    Z = (r0 + a_abs * u[:, 0]) * np.exp(1j * (phi0 + g * u[:, 1]))
    out["frac_true_samples_outside_linear"] = float((dist_to_box(Z, c, gens) > 1e-12).mean())
    out["areas"] = dict(true=g * (rmax ** 2 - rmin ** 2), linear=4 * abs(gens[0]) * abs(gens[1]),
                        outer=4 * abs(go[0]) * abs(go[1]))
    return out


def main():
    t0 = time.time()
    res = dict(geometry=[], design={})
    i0 = PRESETS["weak_sg"].i0
    for g in (0.3, 1.0):
        res["geometry"].append(geometry(f"IBR i0=0.9, |i| +-0.3 pu, angle +-{g} rad", i0, 0.3, g))
    res["geometry"].append(geometry("SG e0=1, |e| +-5 %, angle +-0.087 rad", 1.0 + 0j, 0.05, 0.087, relative=True))
    for gg in res["geometry"]:
        print(f"{gg['label']}: h(true->linear) {gg['h_true_to_linear']:.4f}  h(linear->true) "
              f"{gg['h_linear_to_true']:.4f}  h(true->outer) {gg['h_true_to_outer']:.1e}  h(outer->true) "
              f"{gg['h_outer_to_true']:.4f}  true samples outside linear {gg['frac_true_samples_outside_linear']:.1%}  "
              f"max |i| linear {gg['linear_box_max_modulus']:.3f} true {gg['true_max_modulus']:.3f}", flush=True)

    for pr in ("weak_sg", "weak_sg_noisy", "all_ibr_hard"):
        p = PRESETS[pr]
        rep = json.load(open(os.path.join(OUTDIR, "..", f"aux_signal_toy_{pr}.json")))["cvxpy_opt"]
        d_rep = complex(rep[0], rep[1])
        row = dict(reported=[d_rep, abs(d_rep)])
        for mode in ("linear", "outer"):
            ms = ModelSet(p, mode=mode)
            mg0 = ms.margins(0.0); mgr = ms.margins(d_rep)
            br = bracket_min(ms, ms_polygons(ms, cache=("lin" if mode == "linear" else "outer", pr)))
            dm = br.get("best_point")
            r = dict(unseparated_at_0=int((mg0 <= 1e-9).sum()), unseparated_at_reported=int((mgr <= 1e-9).sum()),
                     unseparated_cases_at_reported=[f[0] for f, m in zip(ms.faults, mgr) if m <= 1e-9])
            if dm is None:
                r["global_min"] = None
            else:
                r["global_min"] = [dm, abs(dm), float(np.degrees(np.angle(dm)))]
                r["bracket"] = br
                r["lp_min_margin_at_global"] = float(ms.margins(dm).min())
            row[mode] = r
        res["design"][pr] = row
        gl, go = row["linear"]["global_min"], row["outer"]["global_min"]
        print(f"[{pr}] reported {abs(d_rep):.4f} | linear: unsep@0 {row['linear']['unseparated_at_0']}, global "
              f"{None if gl is None else round(gl[1], 4)} | outer: unsep@0 {row['outer']['unseparated_at_0']}, "
              f"unsep@reported {row['outer']['unseparated_at_reported']}, global "
              f"{'none in |d|<=1.5' if go is None else f'{go[1]:.4f} at {go[2]:.1f} deg'}", flush=True)
    res["runtime_s"] = time.time() - t0
    dump(res, "h6_angle.json")


if __name__ == "__main__":
    main()
