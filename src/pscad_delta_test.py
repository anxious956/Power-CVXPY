"""
First EMT test of the design method with the signal actually injected (steps 1 -> 2 of the plan).

The design tool, on the PSCAD two-bus circuit (weak_sg with the inverter's zero-sequence path open),
finds two fault cases it cannot separate from normal operation at delta = 0 (A-G at 75 % and 95 %
through 40 ohm) and a delta of 0.18 pu at 330 deg (source-EMF frame) that separates every case.
Here each case is simulated in PSCAD with delta = 0 and with that delta, and the relay measurement
from EMT is placed against the design tool's normal-operation set N(delta) (zonotope plus the noise
box eps):

    ratio = (smallest noise box that would put the measurement inside N(delta)) / eps

The EMT measurement is clean; the relay sees it plus noise up to eps, and N(delta) carries its own eps,
so a fault realisation is indistinguishable from normal operation iff ratio <= 2, and separated iff
ratio > 2. The design tool's guarantee is about the worst realisation in the uncertainty box, so the
cases are run at that realisation (computed by the design model) as well as at the nominal point. The same ratio is computed for the static model's prediction
at the same operating point (the inverter's measured injection), so EMT and design can be compared.

    python src/pscad_delta_test.py
"""
import os, sys
import numpy as np
from scipy.optimize import linprog
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aux_model import Params, affine_model, realify, solve
from pscad_twobus_check import read_case, relay_y, injection, WORK

P = Params(name="weak_sg_open0", zs={1: 0.4j, 2: 0.4j, 0: 0.8j}, gen_i=[0.3, 0.3], eps=0.08, rF=1.0,
           ibr_zero_z=1e6)
DELTA = 0.18 * np.exp(1j * np.radians(330))
CN, HN, GN = affine_model(P, "N")


def noise_needed(y_real, d):
    """Smallest t such that y = cN + HN d + GN u + n, |u| <= 1, |n_i| <= t."""
    target = y_real - (CN + HN @ np.array([d.real, d.imag]))
    n, k = target.size, GN.shape[1]
    # variables: u (k), n (n), t (1); minimise t
    c = np.zeros(k + n + 1); c[-1] = 1.0
    A_eq = np.hstack([GN, np.eye(n), np.zeros((n, 1))])
    A_ub = np.vstack([np.hstack([np.zeros((n, k)), np.eye(n), -np.ones((n, 1))]),
                      np.hstack([np.zeros((n, k)), -np.eye(n), -np.ones((n, 1))])])
    bounds = [(-1, 1)] * k + [(None, None)] * n + [(0, None)]
    res = linprog(c, A_ub=A_ub, b_ub=np.zeros(2 * n), A_eq=A_eq, b_eq=target, bounds=bounds, method="highs")
    return res.x[-1]


def evaluate(name, scen, m, rf_ohm, d_design, psi_deg=0.0, t_pre=0.25, t_meas=0.38):
    """psi_deg: the source EMF angle of the realisation simulated (the frame is fixed by it)."""
    run = read_case(os.path.join(WORK, name + ".gf46"), name)
    y_pre, _, _ = relay_y(run, t_pre)
    e1 = y_pre[0] + P.zs[1] * y_pre[3]
    rot = np.exp(1j * (np.radians(psi_deg) - np.angle(e1)))
    tm = t_meas if scen != "N" else t_pre
    y, _, _ = relay_y(run, tm)
    y = y * rot
    i1, i2 = injection(run, tm)
    i1, i2 = i1 * rot, i2 * rot
    e = abs(e1) * np.exp(1j * np.radians(psi_deg))
    ys = solve(P, scen, e, i1, i2, m=m, mr=rf_ohm / 40.0 / P.rF)
    return dict(name=name, injected_I1=i1, injected_I2=i2,
                ratio_emt=noise_needed(realify(y), d_design) / P.eps,
                ratio_static=noise_needed(realify(ys), d_design) / P.eps,
                emt_vs_static=np.abs(y - ys).max())


def main():
    WC = -5.23                                                 # worst-case EMF angle from the design model
    rows = [("nominal", "normal", "dt_N_d0", "N", 0.5, 0.0, 0.0, 0.0), ("nominal", "normal", "dt_N_d1", "N", 0.5, 0.0, DELTA, 0.0),
            ("nominal", "A-G 75 %", "dt_ag75_d0", "ag", 0.75, 40.0, 0.0, 0.0), ("nominal", "A-G 75 %", "dt_ag75_d1", "ag", 0.75, 40.0, DELTA, 0.0),
            ("nominal", "A-G 95 %", "dt_ag95_d0", "ag", 0.95, 40.0, 0.0, 0.0), ("nominal", "A-G 95 %", "dt_ag95_d1", "ag", 0.95, 40.0, DELTA, 0.0),
            ("worst", "normal", "wc_N_d0", "N", 0.5, 0.0, 0.0, WC), ("worst", "normal", "wc_N_d1", "N", 0.5, 0.0, DELTA, WC),
            ("worst", "A-G 75 %", "wc_ag75_d0", "ag", 0.75, 40.0, 0.0, WC), ("worst", "A-G 75 %", "wc_ag75_d1", "ag", 0.75, 40.0, DELTA, WC),
            ("worst", "A-G 95 %", "wc_ag95_d0", "ag", 0.95, 40.0, 0.0, WC), ("worst", "A-G 95 %", "wc_ag95_d1", "ag", 0.95, 40.0, DELTA, WC)]
    print(f"{'point':<8}{'case':<10}{'delta':>6}  {'EMT ratio':>9}  {'design ratio':>12}  {'|EMT-design|':>12}  verdict (threshold 2)")
    out = []
    for point, label, name, scen, m, rf, d, psi in rows:
        r = evaluate(name, scen, m, rf, d, psi)
        if scen == "N":
            verdict = "normal, inside N" if r["ratio_emt"] <= 2 else "FALSE ALARM"
        else:
            verdict = "SEPARATED" if r["ratio_emt"] > 2 else "not separated"
        print(f"{point:<8}{label:<10}{abs(d):>6.2f}  {r['ratio_emt']:>9.2f}  {r['ratio_static']:>12.2f}  {r['emt_vs_static']:>12.4f}  {verdict}")
        out.append(dict(point=point, case=label, run=name, delta=[float(np.real(d)), float(np.imag(d))],
                        injected_I2=[float(r["injected_I2"].real), float(r["injected_I2"].imag)],
                        ratio_emt=float(r["ratio_emt"]), ratio_design=float(r["ratio_static"]),
                        emt_vs_design=float(r["emt_vs_static"]), verdict=verdict))
    import json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "pscad", "delta_test.json")
    json.dump(dict(design_delta=[float(DELTA.real), float(DELTA.imag)], eps=P.eps, threshold=2.0, rows=out),
              open(path, "w"), indent=1)
    print("wrote results/pscad/delta_test.json")


if __name__ == "__main__":
    main()
