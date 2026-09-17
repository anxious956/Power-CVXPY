"""H20/H10: oracle event position, one-cycle DFT, no mimic filter, decaying DC offset.

The reactance element reads the post-fault phasor one cycle after the TRUE event index.
Measured here, on the zone study's own generator (CPU only):
  1. distance error of the element vs the noise-free reactance of the same fault (computed with
     phase_selected_reactance on the exact sequence phasors), in % of the line reactance X1,
     for dc_offset 0.3 (default) vs 0, mimic filter off/on (tau from the line X/R), trigger
     jitter 0 vs uniform +-2 ms (+-15 samples at 7680 Hz), with and without noise/harmonics;
  2. the element's AUC and dependability at 1 % FAR (threshold and polarity on train) for the
     same variants, --quick sizes (350/250 per class), 3 seeds, delta 0 and 0.514.

  python src/review/h20_dc_trigger.py
"""
import time
import numpy as np
from dataclasses import replace
from common import design_direction, save
from waveforms import SigParams, FS
import detect as D
import zone_detect as Z
from zone_model import phase_selected_reactance

direction = design_direction()
grid = replace(Z.ZoneParams(), rF=0.3)
TAU = Z.line_tau_samples(grid)
J = int(round(0.002 * FS))           # 2 ms in samples
t0 = time.time()


def true_reactance(meta):
    pre, post, g = meta["pre"], meta["post"], meta["grid"]
    seq = lambda a, o: np.array([a[o + 2], a[o], a[o + 1]])        # -> [s0, s+, s-]
    return phase_selected_reactance(seq(post, 0), seq(pre, 3), seq(post, 3), g.z1, g.z0_ratio * g.z1)


VARIANTS = [  # name, SigParams kwargs, mimic, jitter
    ("default (dc 0.3, noise, harm)", {}, False, False),
    ("dc 0", dict(dc_offset=0.0), False, False),
    ("dc 0.3 + mimic", {}, True, False),
    ("dc 0.3, jitter +-2ms", {}, False, True),
    ("dc 0.3 + mimic, jitter +-2ms", {}, True, True),
    ("clean: no noise/harm, dc 0.3", dict(noise=0.0, harmonics=(0.0, 0.0)), False, False),
    ("clean: no noise/harm, dc 0", dict(noise=0.0, harmonics=(0.0, 0.0), dc_offset=0.0), False, False),
    ("clean: no noise/harm, dc 0.3 + mimic", dict(noise=0.0, harmonics=(0.0, 0.0)), True, False),
]

res = dict(error=[], auc=[], tau_samples=TAU, jitter_samples=J)
X1 = grid.z1.imag
for t in (0.0, 0.514):
    for name, kw, mim, jit in VARIANTS:
        X, y, kinds, metas = Z.make_zone_dataset(350, np.random.default_rng(100), t * direction,
                                                 SigParams(**kw), grid, return_meta=True)
        off = np.random.default_rng(7).integers(-J, J + 1, len(X)) if jit else None
        est = Z.score_reactance(X, grid, offsets=off, mimic_tau=TAU if mim else None)
        tru = np.array([true_reactance(m) for m in metas])
        err = (est - tru) / X1 * 100
        ok = (tru < 5) & (est < 5)          # both found a forward loop
        row = dict(delta=t, variant=name, n=int(len(X)), frac_no_forward_loop=float(1 - ok.mean()))
        for k in ("ag", "ab", "ag2", "ab2", "all"):
            mk = ok & ((kinds == k) if k != "all" else True)
            e = err[mk]
            row[k] = dict(bias=float(np.median(e)), mae=float(np.median(np.abs(e))),
                          p95=float(np.percentile(np.abs(e), 95)))
        res["error"].append(row)
        print(f"delta={t:.3f} {name:38s} |err| median {row['all']['mae']:5.2f}% p95 {row['all']['p95']:6.2f}%  "
              f"bias ag {row['ag']['bias']:+5.2f} ab {row['ab']['bias']:+5.2f} ag2 {row['ag2']['bias']:+5.2f} "
              f"ab2 {row['ab2']['bias']:+5.2f} (% of X1)  no-fwd {row['frac_no_forward_loop']*100:.1f}%", flush=True)

for t in (0.0, 0.514):
    for name, kw, mim, jit in VARIANTS[:5]:
        for sd in range(3):
            Xtr, ytr, _ = Z.make_zone_dataset(350, np.random.default_rng(100 + 17 * sd), t * direction, SigParams(**kw), grid)
            Xte, yte, _ = Z.make_zone_dataset(250, np.random.default_rng(999 + 31 * sd), t * direction, SigParams(**kw), grid)
            otr = np.random.default_rng(7 + sd).integers(-J, J + 1, len(Xtr)) if jit else None
            ote = np.random.default_rng(70 + sd).integers(-J, J + 1, len(Xte)) if jit else None
            a = Z.score_reactance(Xtr, grid, offsets=otr, mimic_tau=TAU if mim else None)
            b = Z.score_reactance(Xte, grid, offsets=ote, mimic_tau=TAU if mim else None)
            res["auc"].append(dict(delta=t, variant=name, seed=sd, **D.evaluate(a, ytr, b, yte, polarity="train")))
        rr = [r for r in res["auc"] if r["delta"] == t and r["variant"] == name]
        au = np.array([r["auc"] for r in rr]); de = np.array([r["detection_rate"] for r in rr]) * 100
        print(f"AUC delta={t:.3f} {name:38s} {au.mean():.4f}+-{au.std():.4f}  dep@1% {de.mean():5.1f}+-{de.std():4.1f}", flush=True)
res["runtime_s"] = time.time() - t0
save("h20_dc_trigger.json", res)
