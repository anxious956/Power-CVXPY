"""
H1: design the auxiliary signal on the three-bus zone problem (zone_model.py) instead of reusing the
two-bus weak_sg optimum (0.514 pu at -23.2 deg) in zone_detect.py:163-166 and detect.py:191-195.

Classes (as zone_detect.generate draws them, boundary=True):
  IN  : ag, ab on the protected line,  m in [0.62, 0.85]  (6-point grid), mr in {0, 1/3, 2/3, 1}
  OUT : ag2, ab2 on the adjacent line, m in [0.02, 0.18]  (5-point grid), same mr; plus N
  rF  : 0.3 pu (zone_detect default --rf) and 1.0 pu
Uncertainty (zone_detect.py:48-55):
  affine, handled by sound outer zonotopes (wp1_common.sector_outer_box):
    srcL = e0 (1 +- 0.05) e^{+-j0.09}            -> sector box
    iR   = i0 [0.5, 1.6] e^{+-j0.4}, |i0| = 0.45  -> sector box
  NOT affine in the measurement, handled by gridding (one affine piece per sample, union):
    zs x fz, fz in [0.5, 1.8];  yR x sR, yS x sS in [0.6, 1.5];  ibr_zero_z x sg in [0.6, 1.6]
    pieces = 16 vertices + centre = 17.
  -> this is an INNER approximation of the true uncertainty (no bound on what happens between
     pieces or between grid points of m, mr); results are necessary conditions, not a guarantee.
Noise box eps per real phasor component: 0.08 (the author's weak_sg value) and 0.01 (above the
front-end error of the synthetic waveforms, see H2: std 7.2e-4, DC-offset bias <= 6.4e-3).

Separation: every IN zonotope vs every OUT zonotope (all piece pairs). Solved with
  (1) interval-hull prefilter (sufficient for separation), (2) inf-norm distance LP,
  (3) lazy constraint generation for the minimum-norm delta: polygons of the deepest pairs,
      grid candidates outside their union, full check of candidates in order of |delta|, add the
      violating pair's polygon, repeat.

  python src/review/wp1_h1_zone_design.py [--rf 0.3] [--eps 0.08]     (minutes to ~1 h, see log)
"""
import os, sys, time, argparse, itertools
from dataclasses import replace
import numpy as np
from wp1_common import (dist_inf, gauge_dual, polygon, grid_separating, exact_min, realify,
                        sector_outer_box, sector_inner_box, dump, OUTDIR)
from zone_model import ZoneParams, solve_zone

RAD = 1.5


def pieces():
    base = ZoneParams()
    lv = dict(fz=(0.5, 1.8), sR=(0.6, 1.5), sS=(0.6, 1.5), sg=(0.6, 1.6))
    out = [dict(fz=a, sR=b, sS=c, sg=d) for a, b, c, d in itertools.product(*lv.values())]
    out.append({k: (v[0] + v[1]) / 2 for k, v in lv.items()})
    return out


def grid_for(pc, rf):
    g = ZoneParams()
    return replace(g, rF=rf,
                   zs={k: v * pc["fz"] for k, v in g.zs.items()},
                   yR={k: v * pc["sR"] for k, v in g.yR.items()},
                   yS={k: v * pc["sS"] for k, v in g.yS.items()},
                   ibr_zero_z=g.ibr_zero_z * pc["sg"])


SOURCES = "outer"


def affine_zone(g, kind, m, mr):
    box = sector_outer_box if SOURCES == "outer" else sector_inner_box
    cL, gL = box(g.e0, 0.95 * abs(g.e0), 1.05 * abs(g.e0), 0.09)
    cR, gR = box(g.i0, 0.5 * abs(g.i0), 1.6 * abs(g.i0), 0.4)
    y0 = solve_zone(g, kind, cL, cR, 0.0, m, mr)
    H = [solve_zone(g, kind, cL, cR, dd, m, mr) - y0 for dd in (1.0, 1j)]
    G = [solve_zone(g, kind, cL + gg, cR, 0.0, m, mr) - y0 for gg in gL]
    G += [solve_zone(g, kind, cL, cR + gg, 0.0, m, mr) - y0 for gg in gR]
    return realify(y0), np.stack([realify(h) for h in H], 1), np.stack([realify(x) for x in G], 1)


def build(rf):
    mr_axis = [0.0, 1 / 3, 2 / 3, 1.0]
    IN, OUT = [], []
    for ip, pc in enumerate(pieces()):
        g = grid_for(pc, rf)
        for kind in ("ag", "ab"):
            for m in np.linspace(0.62, 0.85, 6):
                for mr in mr_axis:
                    IN.append(((kind, round(float(m), 4), round(mr, 3), ip), affine_zone(g, kind, m, mr)))
        for kind in ("ag2", "ab2"):
            for m in np.linspace(0.02, 0.18, 5):
                for mr in mr_axis:
                    OUT.append(((kind, round(float(m), 4), round(mr, 3), ip), affine_zone(g, kind, m, mr)))
        OUT.append((("N", 0.5, 0.0, ip), affine_zone(g, "N", 0.5, 0.0)))
    stack = lambda L: tuple(np.stack([x[1][j] for x in L]) for j in range(3))
    return IN, OUT, stack(IN), stack(OUT)


class PairSet:
    def __init__(self, rf, eps):
        self.IN, self.OUT, (self.cI, self.HI, self.GI), (self.cO, self.HO, self.GO) = build(rf)
        self.e = 2 * eps
        self.rI = np.abs(self.GI).sum(2)           # (nI, 12)
        self.rO = np.abs(self.GO).sum(2)

    def candidates(self, d, extra=0.0):
        """(i, j) pairs NOT separated by the interval-hull test at d (or over the |d|<=RAD box if d is None)."""
        out = []
        for i in range(len(self.cI)):
            dc = self.cI[i][None, :] - self.cO                     # (nO, 12)
            dH = self.HI[i][None, :, :] - self.HO                  # (nO, 12, 2)
            rad = self.rI[i][None, :] + self.rO + self.e + extra
            if d is None:
                lo = np.abs(dc) - RAD * np.abs(dH).sum(2)
                sep = np.any(lo > rad, axis=1)
            else:
                v = dc + dH @ np.array([d.real, d.imag])
                sep = np.any(np.abs(v) > rad, axis=1)
            for j in np.where(~sep)[0]:
                out.append((i, int(j)))
        return out

    def pair(self, i, j):
        return (self.cI[i] - self.cO[j], self.HI[i] - self.HO[j], np.hstack([self.GI[i], self.GO[j]]))

    def check(self, d, pairs, stop_at_first=False):
        bad = []
        dv = np.array([d.real, d.imag])
        for (i, j) in pairs:
            dc, dH, G = self.pair(i, j)
            if dist_inf(dc + dH @ dv, G, self.e) <= 1e-9:
                bad.append((i, j))
                if stop_at_first:
                    break
        return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rf", type=float, default=0.3)
    ap.add_argument("--eps", type=float, default=0.08)
    ap.add_argument("--max-rounds", type=int, default=400)
    ap.add_argument("--sample", type=int, default=4000, help="LP-checked pairs per delta for counts")
    ap.add_argument("--sources", choices=("outer", "inner"), default="outer",
                    help="outer: sound outer boxes of the source sectors (separation claims); inner: boxes inside "
                         "the sectors, so every non-separated pair is a physical witness (impossibility claims)")
    args = ap.parse_args()
    global SOURCES
    SOURCES = args.sources
    t0 = time.time()
    S = PairSet(args.rf, args.eps)
    nI, nO = len(S.IN), len(S.OUT)
    res = dict(rf=args.rf, eps=args.eps, sources=args.sources, n_in=nI, n_out=nO, n_pairs=nI * nO, pieces=len(pieces()))
    print(f"rf={args.rf} eps={args.eps}: IN {nI} zonotopes, OUT {nO} (incl. N), pairs {nI*nO} ({time.time()-t0:.0f}s)", flush=True)

    rng = np.random.default_rng(0)

    def sub(pairs, n):
        if len(pairs) <= n:
            return list(pairs), 1.0
        idx = rng.choice(len(pairs), n, replace=False)
        return [pairs[k] for k in idx], len(pairs) / n

    # ---------------- delta = 0 (LP on a random subsample of the box candidates; count is an estimate)
    cand0 = S.candidates(0j)
    s0, scale0 = sub(cand0, args.sample)
    bad0 = S.check(0j, s0)
    res["delta0"] = dict(box_candidates=len(cand0), lp_checked=len(s0), unseparated_in_sample=len(bad0),
                         unseparated_pairs_estimate=len(bad0) * scale0,
                         unseparated_fraction_of_all_pairs_estimate=len(bad0) * scale0 / (nI * nO))
    by = {}
    for i, j in bad0:
        key = (S.IN[i][0][0], S.OUT[j][0][0])
        by[str(key)] = by.get(str(key), 0) + 1
    res["delta0"]["unseparated_by_kind"] = by
    same_piece = sum(S.IN[i][0][3] == S.OUT[j][0][3] for i, j in bad0)
    res["delta0"]["unseparated_same_piece"] = same_piece
    print(f"delta=0: box-prefilter candidates {len(cand0)}, LP-unseparated {len(bad0)}/{len(s0)} checked (est. total {len(bad0)*scale0:.0f}) "
          f"(same piece {same_piece}); by kind {by} ({time.time()-t0:.0f}s)", flush=True)

    # ---------------- witnesses: pairs whose non-separating polygon alone contains the disk |d| <= RAD
    wit = []
    for pr in bad0[:60]:
        poly = polygon(*S.pair(*pr), S.e, ndir=72, R=3.0)
        if poly is None:
            continue
        inscribed = float(poly[1].min())          # origin inside -> min support value bounds the inscribed radius
        wit.append(dict(pair=[S.IN[pr[0]][0], S.OUT[pr[1]][0]], inscribed_radius_lb=inscribed, idx=pr))
    wit.sort(key=lambda w: -w["inscribed_radius_lb"])
    if wit and wit[0]["inscribed_radius_lb"] >= RAD:
        i, j = wit[0]["idx"]
        dc, dH, G = S.pair(i, j)
        circ = [RAD * np.exp(1j * t) for t in np.linspace(0, 2 * np.pi, 64, endpoint=False)]
        worst = max(dist_inf(dc + dH @ np.array([d.real, d.imag]), G, S.e) for d in circ)
        wit[0]["lp_max_distance_on_circle_|d|=1.5_64pts"] = worst
    res["witnesses"] = [{k: v for k, v in w.items() if k != "idx"} for w in wit[:10]]
    res["n_pairs_alone_blocking_disk"] = sum(w["inscribed_radius_lb"] >= RAD for w in wit)
    if wit:
        print(f"witness pairs (of {len(wit)} examined) whose polygon alone covers |d|<={RAD}: "
              f"{res['n_pairs_alone_blocking_disk']}; top: {wit[0]['pair']} inscribed radius >= "
              f"{wit[0]['inscribed_radius_lb']:.3f} (R cap 3.0); LP check on circle: "
              f"{wit[0].get('lp_max_distance_on_circle_|d|=1.5_64pts')}", flush=True)
        dHn = np.linalg.norm(S.pair(*wit[0]['idx'])[1])
        res["witness_top_norm_dH"] = float(dHn)

    # ---------------- pairs that could be unseparated anywhere in |d|_inf <= RAD
    candR = S.candidates(None)
    res["pairs_possibly_unseparated_in_box"] = len(candR)
    print(f"pairs not box-separable for all |d|_inf<=1.5: {len(candR)} ({time.time()-t0:.0f}s)", flush=True)

    # ---------------- lazy constraint generation for the min-norm separating delta
    polys, used = [], set()
    seeds = bad0[:: max(1, len(bad0) // 30)][:30] if bad0 else []
    for pr in seeds:
        polys.append(polygon(*S.pair(*pr), S.e, ndir=120)); used.add(pr)
    history = []
    found = None
    for rnd in range(args.max_rounds):
        ax, ok = grid_separating(polys, R=RAD, step=0.01)
        RE, IM = np.meshgrid(ax, ax)
        Dg = (RE + 1j * IM)
        mask = ok & (np.abs(Dg) <= RAD)
        frac = float(mask.sum() / (np.abs(Dg) <= RAD).sum())
        if not mask.any():
            history.append(dict(round=rnd, polygons=len(polys), free_fraction=0.0))
            print(f"round {rnd}: {len(polys)} polygons cover the whole disk |d|<=1.5 -> no separating delta", flush=True)
            break
        order = np.argsort(np.abs(Dg[mask]))
        pts = Dg[mask][order]
        # check the smallest candidates; the first one that passes every pair is the grid optimum
        newbad = None
        for d in pts[:1]:
            cd = S.candidates(d)
            rng.shuffle(cd)
            b = S.check(d, cd, stop_at_first=True)
            if not b:
                found = d
            else:
                newbad = b[0]
        history.append(dict(round=rnd, polygons=len(polys), free_fraction=frac, best_free=[pts[0], abs(pts[0])]))
        if rnd % 10 == 0:
            print(f"round {rnd}: {len(polys)} polygons, free fraction of disk {frac:.4f}, smallest free |d|={abs(pts[0]):.3f} "
                  f"({time.time()-t0:.0f}s)", flush=True)
        if found is not None:
            break
        if newbad in used:
            raise RuntimeError("violating pair already has a polygon: tolerance issue")
        polys.append(polygon(*S.pair(*newbad), S.e, ndir=120)); used.add(newbad)
    res["lazy_rounds"] = history
    if found is not None:
        dmin = exact_min(polys, RAD)
        res["design"] = dict(grid_optimum=[found, abs(found), float(np.degrees(np.angle(found)))],
                             polygon_exact_lower_bound=None if dmin is None else [dmin, abs(dmin)],
                             polygons_used=len(polys))
        print(f"FOUND separating delta on 0.01 grid: {found:.3f}  |d|={abs(found):.3f} at {np.degrees(np.angle(found)):.1f} deg", flush=True)
    else:
        res["design"] = None
        # most informative fallback: which delta direction separates the most pairs among the candidates
    # compare with the author's delta
    d_auth = 0.4725416047022092 - 0.20261044826170205j
    cand_a = S.candidates(d_auth)
    sa, scale_a = sub(cand_a, args.sample)
    bad_a = S.check(d_auth, sa)
    res["author_delta"] = dict(delta=[d_auth, abs(d_auth)], box_candidates=len(cand_a), lp_checked=len(sa),
                               unseparated_in_sample=len(bad_a), unseparated_pairs_estimate=len(bad_a) * scale_a)
    print(f"author delta 0.514@-23.2: box candidates {len(cand_a)}, unseparated est. {len(bad_a)*scale_a:.0f} "
          f"(delta=0: {len(bad0)*scale0:.0f})", flush=True)
    # scan of unseparated-pair counts along directions at |d| in {0.25, 0.514, 1.0}: cheap summary
    scan = []
    for mag in (0.25, 0.514, 1.0):
        for ang in range(0, 360, 30):
            d = mag * np.exp(1j * np.deg2rad(ang))
            c = S.candidates(d)
            sc, scl = sub(c, max(500, args.sample // 4))
            scan.append(dict(mag=mag, ang=ang, box_candidates=len(c), lp_checked=len(sc),
                             unseparated=len(S.check(d, sc)) * scl))
        best = min((s for s in scan if s["mag"] == mag), key=lambda s: s["unseparated"])
        print(f"  scan |d|={mag}: fewest unseparated pairs (est.) {best['unseparated']:.0f} at {best['ang']} deg "
              f"({time.time()-t0:.0f}s)", flush=True)
    res["scan"] = scan
    res["runtime_s"] = time.time() - t0
    dump(res, f"h1_zone_design_rf{args.rf}_eps{args.eps}_{args.sources}.json")


if __name__ == "__main__":
    main()
