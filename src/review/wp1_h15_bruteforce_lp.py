"""
H15 cross-check without polygons: brute-force LP classification of the delta plane for one preset.
Every grid point (step 0.01, |d| <= 1.5) is tested against all 30 grid faults with the primal LP
(inf-norm distance > 1e-9 = separated), stopping at the first unseparated case; the fault that last
blocked a neighbour is tried first. Compared with wp1_h15_global's polygon classification.

  python src/review/wp1_h15_bruteforce_lp.py weak_sg      (~20-40 min single core)
"""
import sys, time
import numpy as np
from wp1_common import PRESETS, ModelSet, dist_inf, ms_polygons, grid_separating, components, dump


def main():
    pr = sys.argv[1] if len(sys.argv) > 1 else "weak_sg"
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
    p = PRESETS[pr]
    ms = ModelSet(p)
    pairs = [ms.pair(f) for f in ms.faults]
    e = 2 * ms.eps
    ax = np.round(np.arange(-1.5, 1.5 + 1e-9, step), 10)
    sep = np.zeros((ax.size, ax.size), bool)
    disk = np.zeros_like(sep)
    t0 = time.time()
    last = 0
    nlp = 0
    for j, im in enumerate(ax):
        for i, re in enumerate(ax):
            if re * re + im * im > 1.5 ** 2 + 1e-12:
                continue
            disk[j, i] = True
            dv = np.array([re, im])
            order = [last] + [k for k in range(len(pairs)) if k != last]
            ok = True
            for k in order:
                dc, dH, G = pairs[k]
                v = dc + dH @ dv
                if np.any(np.abs(v) > np.abs(G).sum(1) + e + 1e-12):
                    continue
                nlp += 1
                if dist_inf(v, G, e) <= 1e-9:
                    ok = False; last = k
                    break
            sep[j, i] = ok
        if j % 30 == 0:
            print(f"row {j}/{ax.size}  LPs {nlp}  {time.time()-t0:.0f}s", flush=True)
    polys = ms_polygons(ms, cache=("lin", pr))
    ax2, okp = grid_separating(polys, R=1.5, step=step)
    okp &= disk
    RE, IM = np.meshgrid(ax, ax)
    mag = np.where(sep, np.abs(RE + 1j * IM), np.inf)
    jj = np.unravel_index(np.argmin(mag), mag.shape)
    out = dict(preset=pr, step=step, points=int(disk.sum()), lp_separating=int(sep.sum()),
               polygon_separating=int(okp.sum()), polygon_sep_but_lp_not=int((okp & ~sep).sum()),
               lp_sep_but_polygon_not=int((sep & ~okp).sum()), lp_components_sep=components(sep),
               lp_components_nonsep=components(disk & ~sep),
               lp_grid_min=[complex(RE[jj], IM[jj]), float(mag[jj])], n_lp=nlp, runtime_s=time.time() - t0)
    print(out, flush=True)
    dump(out, f"h15_bruteforce_lp_{pr}.json")


if __name__ == "__main__":
    main()
