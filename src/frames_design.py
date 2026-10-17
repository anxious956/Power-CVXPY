"""
The three-bus design in the two-frame model (src/frames.py), with the checks the review asked for.

  1. delta* (command, in the inverter's own frame) at rho = 0 and 0.1, search tier (fewer samples);
  2. at delta*: separation re-checked on a dense tier, adversarial containment (also at the rejected candidates
     just below delta*), and the Calafiore-Campi coverage statement;
  3. the remainder factor: separation at delta* with factor 1.0 / 1.1 / 1.25;
  4. the ablation: everything boxed independently (no shared symbols), rho = 0.1;
  5. the absolute-frame design (network.py) for comparison: 0.62 / 0.90 pu.

    python src/frames_design.py      -> results/network/frames_design.json
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import three_bus
from network_delta_test import CASES

OUT = os.path.join(HERE, "..", "results", "network", "frames_design.json")


def cpx(z):
    return None if z is None else [float(np.real(z)), float(np.imag(z))]


def main():
    net = three_bus()
    res = dict(cases=len(CASES), eps=net.eps)
    t0 = time.time()
    search = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, factor=1.1)
    res["dead_frames"] = [list(c) for c in search.dead_frames(0j)]
    for rho in (0.0, 0.1):
        r = fr.min_delta_fast(search, rho=rho)
        res[f"shared_rho{rho}"] = dict(abs_delta=r["abs_delta"], angle_deg=r["angle_deg"], d_cmd=cpx(r["d_cmd"]),
                                      unseparated_at_0=[list(c) for c in r.get("unseparated_at_0", [])])
        print(f"shared, rho {rho}: |d_cmd| = {r['abs_delta']} at {r['angle_deg']} deg; inadmissible skipped {r.get('inadmissible')}; unseparated at 0: "
              f"{len(r.get('unseparated_at_0', []))}  [{time.time() - t0:.0f} s]", flush=True)
    d_star = complex(*res["shared_rho0.1"]["d_cmd"])
    dense = fr.FrameModel(net, CASES, n_samples=400, face_pts=5, seed=2, factor=1.1)
    res["dense_check"] = dict(separated_at_dstar=bool(fr.separated(dense, d_star, 0.1)),
                              unseparated=[list(c) for c in fr.unseparated(dense, d_star, 0.1)])
    print(f"dense tier at delta*: separated {res['dense_check']['separated_at_dstar']} "
          f"(unseparated {res['dense_check']['unseparated']})  [{time.time() - t0:.0f} s]", flush=True)
    worst = fr.containment_adversarial(dense, d_star, n_fresh=300, face_pts=7, n_local=40, seed=9)
    res["containment_at_dstar"] = dict(max_outside_pu=float(max(worst.values())),
                                       per_set={str(k): float(v) for k, v in worst.items()})
    below = abs(d_star) - 0.02
    if below > 0:
        d_below = below * np.exp(1j * np.angle(d_star))
        wb = fr.containment_adversarial(dense, d_below, n_fresh=200, face_pts=5, n_local=30, seed=10)
        res["containment_below"] = dict(abs_delta=float(below), max_outside_pu=float(max(wb.values())))
    n_rows = len(dense._expand(dense.samples[0], 0)[0])
    res["scenario_bound"] = dict(iid_samples_per_piece=dense.n, fitted_params_per_component=9,
                                 coverage_beta_1e3=float(fr.scenario_bound(dense.n, 9)))
    print(f"containment at delta*: largest outside {res['containment_at_dstar']['max_outside_pu']:.2e} pu; "
          f"coverage >= {res['scenario_bound']['coverage_beta_1e3']:.4f} (beta 1e-3)  [{time.time() - t0:.0f} s]", flush=True)
    res["factor_check"] = {}
    for f in (1.0, 1.1, 1.25):
        fm = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, factor=f)
        res["factor_check"][str(f)] = bool(fr.separated(fm, d_star, 0.1))
    print(f"separation at delta* with factor 1.0 / 1.1 / 1.25: {res['factor_check']}  [{time.time() - t0:.0f} s]", flush=True)
    ind = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, factor=1.1, shared=False)
    r = fr.min_delta_fast(ind, rho=0.1)
    res["independent_rho0.1"] = dict(abs_delta=r["abs_delta"], angle_deg=r["angle_deg"],
                                     unseparated_at_0=len(r.get("unseparated_at_0", [])))
    print(f"independent boxes, rho 0.1: |d_cmd| = {r['abs_delta']} at {r['angle_deg']}; unseparated at 0: "
          f"{res['independent_rho0.1']['unseparated_at_0']}  [{time.time() - t0:.0f} s]", flush=True)
    res["absolute_frame_design"] = dict(rho0=0.62, rho0_1=0.90, note="network.min_delta, results/MULTIBUS.md")
    json.dump(res, open(OUT, "w"), indent=1)
    print("-> results/network/frames_design.json", flush=True)


if __name__ == "__main__":
    main()
