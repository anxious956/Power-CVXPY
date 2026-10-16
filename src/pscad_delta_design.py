"""
Design side of the extended EMT test of the method (step 1 -> 2): on the PSCAD two-bus circuit,
  - the smallest delta that separates all 30 fault cases, without and with a margin rho (noise box
    enlarged by 1 + rho);
  - for every fault case, the worst-case realisation (source EMF, inverter current) at delta = 0 and at
    the margin design, from the design model's LP;
  - the 16 corners of the uncertainty box for normal operation (false-alarm check under the design).
Writes the run list for src/pscad_batch.py and the design numbers:

    python src/pscad_delta_design.py      -> results/pscad/delta_design.json
"""
import os, sys, json, itertools
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aux_model import Params, Problem, solve, source_generators
from pscad_witness import witness, realisation, P

RHO = 0.10
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "pscad", "delta_design.json")


def smallest_delta(problem, mags=np.arange(0.02, 1.21, 0.02), angs=np.arange(0, 360, 5)):
    for mag in mags:
        ok = [a for a in angs if problem.separates_all(mag * np.exp(1j * np.radians(a)))]
        if ok:
            a = ok[len(ok) // 2]                     # middle of the feasible arc at this magnitude
            return mag * np.exp(1j * np.radians(a)), ok
    return None, []


def inverter_settings(e, i, d):
    """ID, IQ (relative to V1 at bus R) and the delta angle relative to V1_R that reproduce the absolute
    inverter current i and delta d of the design model at EMF e."""
    y = solve(P, "N", e, i, d)
    v1r = y[0] - P.z1 * y[3]
    rel = np.angle(i) - np.angle(v1r)
    return (float(abs(i) * np.cos(rel)), float(-abs(i) * np.sin(rel)),
            float(np.degrees(np.angle(d) - np.angle(v1r))) if abs(d) else 0.0)


def main():
    pr = Problem(P)
    Pm = Params(**{**P.__dict__, "eps": P.eps * (1 + RHO), "name": "weak_sg_open0_margin"})
    prm = Problem(Pm)
    d0, arc0 = smallest_delta(pr)
    dm, arcm = smallest_delta(prm)
    amb0 = pr.unseparated(0.0)
    print(f"unseparated at delta = 0: {len(amb0)} {amb0}")
    print(f"smallest separating delta, no margin:   {abs(d0):.2f} pu at {np.degrees(np.angle(d0)) % 360:.0f} deg (arc {arc0})")
    print(f"smallest separating delta, rho = {RHO}: {abs(dm):.2f} pu at {np.degrees(np.angle(dm)) % 360:.0f} deg (arc {arcm})")
    runs = []
    for f in pr.faults:
        scen, m, mr = f["scen"], f["m"], f["mr"]
        for tag, d in (("d0", 0.0), ("dm", dm)):
            uF, t = witness(scen, m, mr, d)
            e, i = realisation(uF)
            ID, IQ, D2ANG = inverter_settings(e, i, d)
            runs.append(dict(name=f"x_{scen}{int(m * 100)}_r{int(mr * 100)}_{tag}", kind="fault", scen=scen, m=m, mr=mr,
                             rf_ohm=mr * P.rF * 40.0, delta=[float(np.real(d)), float(np.imag(d))], tag=tag,
                             design_ratio=float(t / P.eps), es_pu=float(abs(e)), ph_deg=float(np.degrees(np.angle(e))),
                             idref=ID, iqref=IQ, mode2=2 if abs(d) else 0, d2mag=float(abs(d)), d2ang=D2ANG))
    s0, gL, gR = source_generators(P)
    for k, u in enumerate(itertools.product((-1, 1), repeat=4)):
        e = s0 + gL[0] * u[0] + gL[1] * u[1]
        i = P.i0 + gR[0] * u[2] + gR[1] * u[3]
        ID, IQ, D2ANG = inverter_settings(e, i, dm)
        runs.append(dict(name=f"x_N_c{k:02d}_dm", kind="normal", scen="N", m=0.5, mr=0.0, rf_ohm=0.0,
                         delta=[float(dm.real), float(dm.imag)], tag="dm", corner=list(u), es_pu=float(abs(e)),
                         ph_deg=float(np.degrees(np.angle(e))), idref=ID, iqref=IQ, mode2=2, d2mag=float(abs(dm)),
                         d2ang=D2ANG, inverter_peak_pu=float(abs(i) + abs(dm))))
    # the limiter question: the design ignores the inverter's 1.2 pu limit. Normal operation at every corner
    # with the no-margin delta, and the two hard fault cases at every corner with the margin delta.
    for k, u in enumerate(itertools.product((-1, 1), repeat=4)):
        e = s0 + gL[0] * u[0] + gL[1] * u[1]
        i = P.i0 + gR[0] * u[2] + gR[1] * u[3]
        ID, IQ, D2ANG = inverter_settings(e, i, d0)
        runs.append(dict(name=f"x_N_c{k:02d}_d0s", kind="normal", scen="N", m=0.5, mr=0.0, rf_ohm=0.0,
                         delta=[float(d0.real), float(d0.imag)], tag="d0s", corner=list(u), es_pu=float(abs(e)),
                         ph_deg=float(np.degrees(np.angle(e))), idref=ID, iqref=IQ, mode2=2, d2mag=float(abs(d0)),
                         d2ang=D2ANG, inverter_peak_pu=float(abs(i) + abs(d0))))
        ID, IQ, D2ANG = inverter_settings(e, i, dm)
        for m in (0.75, 0.95):
            runs.append(dict(name=f"x_ag{int(m * 100)}_r100_c{k:02d}_dm", kind="fault", scen="ag", m=m, mr=1.0,
                             rf_ohm=40.0, delta=[float(dm.real), float(dm.imag)], tag="dm_corner", corner=list(u),
                             design_ratio=None, es_pu=float(abs(e)), ph_deg=float(np.degrees(np.angle(e))), idref=ID,
                             iqref=IQ, mode2=2, d2mag=float(abs(dm)), d2ang=D2ANG, inverter_peak_pu=float(abs(i) + abs(dm))))
    n_amb_wc = sum(1 for r in runs if r["kind"] == "fault" and r["tag"] == "d0" and r["design_ratio"] <= 2)
    n_sep_m = sum(1 for r in runs if r["kind"] == "fault" and r["tag"] == "dm" and r["design_ratio"] > 2 * (1 + RHO) - 1e-9)
    print(f"design: worst-case ratio <= 2 at delta = 0 for {n_amb_wc} cases; > 2(1+rho) at the margin design for {n_sep_m} of 30")
    print(f"normal corners whose |I1| + |delta| exceeds the 1.2 pu limit: "
          f"{sum(1 for r in runs if r['kind'] == 'normal' and r['tag'] == 'dm' and r['inverter_peak_pu'] > 1.2)} of 16")
    json.dump(dict(rho=RHO, eps=P.eps, delta0=[float(d0.real), float(d0.imag)], delta_margin=[float(dm.real), float(dm.imag)],
                   arc0=[float(a) for a in arc0], arc_margin=[float(a) for a in arcm], unseparated_at_0=amb0, runs=runs),
              open(OUT, "w"), indent=1)
    print(f"{len(runs)} runs -> results/pscad/delta_design.json")


if __name__ == "__main__":
    main()
