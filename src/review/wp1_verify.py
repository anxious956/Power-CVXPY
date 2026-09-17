"""Independent spot checks of the design-tool findings (written without the agent's code).

H13: at the published weak_sg optimum (0.4725 - 0.2026j), how many faults of the CONTINUOUS set
     m in [0.15, 0.95] x R_f in [0, rF] (the span of the design grid) and m in [0.02, 0.98] are not separated
     from normal operation? 41 x 21 grid, aux_model.separated_lp per point.
H15: brute force of the delta plane for weak_sg, step 0.02 within |Re|,|Im| <= 0.8: smallest |delta| that
     separates all 30 design-grid faults, vs the published 0.514.

    python src/review/wp1_verify.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from aux_model import PRESETS, Problem, affine_model, separated_lp

p = PRESETS["weak_sg"]
P = Problem(p)
t0 = time.time()
out = {}
d = 0.4725 - 0.2026j
dv = np.array([d.real, d.imag])
cN = P.cN + P.HN @ dv
for lab, ms in (("m in [0.15, 0.95]", np.linspace(0.15, 0.95, 41)), ("m in [0.02, 0.98]", np.linspace(0.02, 0.98, 41))):
    bad = []
    for scen in ("ag", "ab"):
        for m in ms:
            for mr in np.linspace(0, 1, 21):
                c, H, G = affine_model(p, scen, m, mr)
                if not separated_lp(cN, P.GN, c + H @ dv, G, p.eps):
                    bad.append((scen, round(float(m), 3), round(float(mr), 3)))
    out[f"H13 {lab}"] = dict(n_points=2 * 41 * 21, not_separated=len(bad), examples=bad[:10])
    print(lab, "not separated:", len(bad), "of", 2 * 41 * 21, bad[:6], f"[{time.time()-t0:.0f}s]", flush=True)
best, n_sep = None, 0
ax = np.arange(-0.8, 0.8001, 0.02)
for re in ax:
    for im in ax:
        dd = re + 1j * im
        if best is not None and abs(dd) >= abs(best):
            continue
        if P.separates_all(dd):
            best = dd
out["H15 brute force step 0.02"] = dict(best=[float(best.real), float(best.imag)] if best is not None else None,
                                        magnitude=float(abs(best)) if best is not None else None)
print("H15 brute-force smallest separating delta:", best, abs(best) if best is not None else None, f"[{time.time()-t0:.0f}s]")
os.makedirs(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "results", "review"), exist_ok=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "results", "review", "wp1_verify.json"), "w"), indent=1)
