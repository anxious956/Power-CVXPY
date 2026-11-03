"""Digitise Fig. 5 of Taylor & Dominguez-Garcia, Geometry of Distance Protection (arXiv 2510.04379v2, p. 12):
the two 21 x 21 marker maps (delta on a 0.2 grid over [-2, 2]^2), marker classes

    left panel : '.' separates (N, ag);  'v' separates (N, ab);  '+' separates (N, ag), (N, ab), (ag, ab)
    right panel: '.' N vs all LG;        'v' N vs all LL;         '+' N vs all LG and LL;   ' ' none

and the grid minima the paper prints (j0.2 / 0.53, 3.02, 1.6 + j0.6 / 4.52) re-read from the map.

    python p_i14_fig5.py <pdf> <out.json>
"""
import json, sys
import numpy as np
import fitz
from scipy import ndimage
from scipy.spatial import ConvexHull

pdf, out = sys.argv[1], sys.argv[2]
page = fitz.open(pdf)[11]
r = page.rect
clip = fitz.Rect(r.width * 0.50, r.height * 0.06, r.width * 0.99, r.height * 0.30)
pix = page.get_pixmap(dpi=600, clip=clip, colorspace=fitz.csGRAY)
img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)
dark = img < 128

# axes boxes: long horizontal dark runs give the frames' top/bottom rows; long vertical runs the sides
def longest_run(a):
    """Longest run of True along the last axis (the frame lines are continuous, marker rows are not)."""
    best = np.zeros(a.shape[0], int); cur = np.zeros(a.shape[0], int)
    for k in range(a.shape[1]):
        cur = np.where(a[:, k], cur + 1, 0)
        best = np.maximum(best, cur)
    return best


frame_rows = np.where(longest_run(dark) > 0.20 * dark.shape[1])[0]     # each panel is ~30 % of the clip
frame_cols = np.where(longest_run(dark.T) > 0.50 * dark.shape[0])[0]


def groups(idx, gap=8):
    g, cur = [], [idx[0]]
    for a, b in zip(idx[:-1], idx[1:]):
        if b - a > gap:
            g.append(cur); cur = []
        cur.append(b)
    g.append(cur)
    return [(min(c), max(c)) for c in g]


fr, fc = groups(frame_rows), groups(frame_cols)
assert len(fr) == 2 and len(fc) == 4, (fr, fc)
top, bot = fr[0][1] + 3, fr[1][0] - 3
panels = {"left": (fc[0][1] + 3, fc[1][0] - 3), "right": (fc[2][1] + 3, fc[3][0] - 3)}

VALS = np.round(np.arange(-2.0, 2.01, 0.2), 1)
result = {}
for name, (x0, x1) in panels.items():
    sub = dark[top:bot, x0:x1]
    lab, n = ndimage.label(sub)
    objs = ndimage.find_objects(lab)
    pts = []
    for k, sl in enumerate(objs, 1):
        m = lab[sl] == k
        area = int(m.sum())
        if area < 30:
            continue
        h, w = m.shape
        cy, cx = ndimage.center_of_mass(m)
        fill = area / (h * w)
        # solidity = area / convex-hull area: a plus ~0.6, a disc or triangle ~1
        yy, xx = np.nonzero(m)
        hull = ConvexHull(np.c_[yy, xx])
        solidity = area / hull.volume
        # bottom-pointing triangle: mass sits in the upper half of its box
        top_share = m[: h // 2].sum() / area
        # disc: bbox fill ~0.78; triangle: ~0.5 and top-heavy; plus: fill 0.4-0.6, solidity < 0.8
        # (the right panel's pluses are drawn smaller, so solidity alone misses them there)
        if top_share > 0.62 and solidity > 0.9:
            cls = "v"
        elif fill > 0.68 and solidity > 0.9:
            cls = "."
        else:
            cls = "+"
        pts.append((sl[0].start + cy, sl[1].start + cx, cls, area, round(fill, 2), round(top_share, 2),
                    round(solidity, 2)))
    ys = np.array([p[0] for p in pts]); xs = np.array([p[1] for p in pts])
    # lattice: the markers' extreme centres are delta = ±2 (both rows/cols are fully populated with '+')
    y_lo, y_hi, x_lo, x_hi = ys.min(), ys.max(), xs.min(), xs.max()
    grid = {}
    for y, x, cls, *_ in pts:
        i = int(round((y_hi - y) / (y_hi - y_lo) * 20))      # row 0 = Im -2
        j = int(round((x - x_lo) / (x_hi - x_lo) * 20))      # col 0 = Re -2
        key = (VALS[j], VALS[i])
        assert key not in grid, (name, key)
        grid[key] = cls
    rows_txt = []
    for i in range(20, -1, -1):
        rows_txt.append(f"{VALS[i]:+.1f} " + " ".join(grid.get((VALS[j], VALS[i]), " ") for j in range(21)))
    feats = np.array([p[3:] for p in pts], float)
    result[name] = dict(n_markers=len(pts), map=rows_txt,
                        counts={c: sum(1 for v in grid.values() if v == c) for c in ".v+"},
                        feature_ranges={c: [list(np.round(feats[[p[2] == c for p in pts]].min(0), 2)),
                                            list(np.round(feats[[p[2] == c for p in pts]].max(0), 2))]
                                        for c in ".v+" if any(p[2] == c for p in pts)})

    def minima(classes):
        ok = [(re_, im_) for (re_, im_), c in grid.items() if c in classes]
        if not ok:
            return None
        mag = min(abs(complex(a, b)) for a, b in ok)
        best = sorted((a, b) for a, b in ok if abs(abs(complex(a, b)) - mag) < 1e-9)
        return dict(abs_delta=round(mag, 4), norm_Delta=round(mag * np.sqrt(7), 3), argmin=best)

    if name == "left":
        result[name]["min_N_ag"] = minima(".+")
        result[name]["min_N_ab"] = minima("v+")
        result[name]["min_all_three_pairs"] = minima("+")
    else:
        result[name]["min_N_allLG"] = minima(".+")
        result[name]["min_N_allLL"] = minima("v+")
        result[name]["min_N_all_six"] = minima("+")

for name in result:
    print(name, result[name]["counts"], "markers", result[name]["n_markers"])
    print("\n".join(result[name]["map"]))
    for k, v in result[name].items():
        if k.startswith("min_"):
            print(" ", k, v)
json.dump(result, open(out, "w"), indent=1)
