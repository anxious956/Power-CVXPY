"""Review of the step-3 pilot: is the hard stratum hard at delta = 0? For the main configuration of the 1.12 pu design
(src/frames_main.py with r_max 1.14), the closest-pair gap between N(0) and each case's F(0), against D1's two
thresholds: < eps means even a CLEAN fault there is missed by the alarm rule "distance > eps"; < 2 eps means not
guaranteed under worst-case noise. Also the gap at the witness source points the pilot used (the delta* witnesses).

    python review/checks/p44e_gaps0.py      (repo root at 416c4c5)
"""
import sys, json
import numpy as np
sys.path.insert(0, "src")
import frames as fr
from pscad_network import three_bus
from network_delta_test import CASES

EPS = 0.08
net = three_bus()
fm = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, factor=1.1, drift_deg=3.0,
                   ref_phi=0.030333432167374483, model_err=0.1 * EPS)
d_star = 1.12 * np.exp(1j * np.radians(225))
binding = [tuple(c) for c in fr.unseparated(fm, 0j, 0.1)]
print(f"{len(binding)} cases unseparated at delta = 0 (rho 0.1)")
wit_star = {tuple(sp["case"]): np.array(sp["S"]) for sp in json.load(open("results/network/frames_design_specs_pll.json"))
            if sp["group"] == "witness" and sp["kind"] == "fault"}
Ns0 = fm.zonotopes(0j, None)
rows = []
for c in binding:
    w0 = fr.witness(fm, 0j, c)
    k = CASES.index(c)
    y = fm.measure(np.atleast_2d(wit_star[c]), 0j, k)[0] if c in wit_star else None   # clean fault at the delta* witness S
    d_at_star_S = fr.distance_to_set(Ns0, y) / EPS if y is not None else float("nan")
    y0 = fm.measure(np.atleast_2d(w0["S_F"]), 0j, k)[0]
    d_at_0_S = fr.distance_to_set(Ns0, y0) / EPS
    rows.append((c, w0["gap"] / EPS, d_at_0_S, d_at_star_S, np.abs(w0["S_F"] - wit_star.get(c, np.full(4, np.nan))).max()))
    print(f"{c}: gap(0) {w0['gap'] / EPS:.2f} eps; clean fault at its delta=0 witness S: {d_at_0_S:.2f} eps; "
          f"at the delta* witness S (what the pilot used): {d_at_star_S:.2f} eps; |S0 - S*|max {rows[-1][4]:.2f}")
g = np.array([r[1] for r in rows])
print(f"\ngap(0): min {g.min():.2f} eps; cases with gap < eps (missed even clean): {int((g < 1).sum())}; < 2 eps: {int((g < 2).sum())}")
