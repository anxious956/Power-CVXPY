"""Review of PR #44 part 3, item 2: the static V1-referenced map theta -> angle(V1_R(u = e^{j theta})) for the stored
runs' source points: number of fixed points on the circle and the slope there (the static loop gain).

    python review/checks/p44c_fixedpoint.py      (repo root at 6d8f812)
"""
import os, sys, json
import numpy as np
sys.path.insert(0, "src")
import frames as fr
from pscad_network import three_bus
from network_delta_test import CASES

net = three_bus()
specs = {sp["name"]: sp for f in ("frames_emt_specs.json", "frames_emt_specs2.json")
         for sp in json.load(open(os.path.join("results", "network", f)))}
th = np.linspace(-np.pi, np.pi, 7201)
for name in ("fe_d090_L1ab15r000", "fe_d100_L1ab15r000", "fe_d105_L1ab15r000", "fe_d105_L1ab35r000", "fe_d114_L1ab15r000",
             "fe_d114_L1ab95r000", "fe_d114_L1ag15r100"):
    sp = specs[name]
    k = CASES.index(tuple(sp["case"]))
    fm = fr.FrameModel(net, [CASES[k]], n_samples=10, face_pts=2, seed=0)
    S = np.array([sp["S"]]); e, ic = fm.sources(S); d = complex(*sp["d_cmd"])
    mv = fm.maps_F[0][1]
    u = np.exp(1j * th)
    i1, dd = fr.limiter_vec(ic[0] * u, d * u, fm.i_max, 1)
    v = mv[0] * e[0] + mv[1] * i1 + mv[2] * dd
    g = np.angle(v * np.conj(u))                      # angle of V1_R relative to the reference: fixed point where 0
    roots = np.where(np.diff(np.sign(g)) != 0)[0]
    roots = [r for r in roots if abs(g[r]) < 1.0]     # skip the +-pi wrap
    slopes = []
    for r in roots:
        dth = th[r + 1] - th[r]
        f = np.unwrap(np.angle(v))
        slopes.append(float((f[r + 1] - f[r]) / dth))
    share = np.abs(mv[2] * dd).max() / np.abs(v).min()
    print(f"{name}: fixed points {len(roots)} at {[round(float(np.degrees(th[r])), 1) for r in roots]} deg; "
          f"static gain d angle(V1_R)/d theta {[round(s, 3) for s in slopes]}; |V1_R| over the circle "
          f"{np.abs(v).min():.3f}..{np.abs(v).max():.3f}; delta's term / min|V1_R| {share:.2f}")
