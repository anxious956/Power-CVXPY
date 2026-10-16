"""
Worst-case (witness) realisations from the design model: for a fault case and delta, the source EMF and
inverter current within the uncertainty box that bring the fault measurement closest to the normal set
(an LP over both zonotopes with one combined noise variable; ambiguous iff that noise <= 2 eps).
Prints the PSCAD settings that reproduce each realisation (source Es and Ph, inverter ID, IQ, D2ANG),
used by results/PSCAD_DELTA_TEST.md.

    python src/pscad_witness.py      -> results/pscad/witness.json
"""
import sys, os, json
import numpy as np
from scipy.optimize import linprog
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aux_model import Params, affine_model, solve, source_generators

P = Params(name="weak_sg_open0", zs={1: 0.4j, 2: 0.4j, 0: 0.8j}, gen_i=[0.3, 0.3], eps=0.08, rF=1.0, ibr_zero_z=1e6)
DELTA = 0.18 * np.exp(1j * np.radians(330))
CN, HN, GN = affine_model(P, "N")


def witness(scen, m, mr, d):
    """Fault-side box coordinates uF of the closest approach, and the combined noise it needs."""
    cF, HF, GF = affine_model(P, scen, m, mr)
    dv = np.array([d.real, d.imag])
    target = (cF + HF @ dv) - (CN + HN @ dv)          # GN uN - GF uF + n = target
    n, kN, kF = target.size, GN.shape[1], GF.shape[1]
    c = np.zeros(kN + kF + n + 1)
    c[-1] = 1
    A_eq = np.hstack([GN, -GF, np.eye(n), np.zeros((n, 1))])
    A_ub = np.vstack([np.hstack([np.zeros((n, kN + kF)), np.eye(n), -np.ones((n, 1))]),
                      np.hstack([np.zeros((n, kN + kF)), -np.eye(n), -np.ones((n, 1))])])
    res = linprog(c, A_ub=A_ub, b_ub=np.zeros(2 * n), A_eq=A_eq, b_eq=target,
                  bounds=[(-1, 1)] * (kN + kF) + [(None, None)] * n + [(0, None)], method="highs")
    return res.x[kN:kN + kF], res.x[-1]


def realisation(uF):
    s0, gL, gR = source_generators(P)
    e = s0 + gL[0] * uF[0] + gL[1] * uF[1]
    i = P.i0 + gR[0] * uF[2] + gR[1] * uF[3]
    return e, i


def main():
    out = {}
    for scen, m, mr in (("ag", 0.75, 1.0), ("ag", 0.95, 1.0)):
        for label, d in (("d0", 0.0), ("d1", DELTA)):
            uF, t = witness(scen, m, mr, d)
            e, i = realisation(uF)
            y = solve(P, "N", e, i, d)                 # pre-fault state at that realisation, for V1 at R
            v1r = y[0] - P.z1 * y[3]
            rel = np.degrees(np.angle(i)) - np.degrees(np.angle(v1r))
            key = f"{scen}{int(m * 100)}_{label}"
            out[key] = dict(m=m, uF=uF.tolist(), noise_ratio=float(t / P.eps), Es_pu=float(abs(e)),
                            Ph_deg=float(np.degrees(np.angle(e))), I_mag=float(abs(i)), I_deg=float(np.degrees(np.angle(i))),
                            ID=float(abs(i) * np.cos(np.radians(rel))), IQ=float(-abs(i) * np.sin(np.radians(rel))),
                            D2ANG=float(np.degrees(np.angle(d)) - np.degrees(np.angle(v1r))) if abs(d) else 0.0)
            q = out[key]
            print(f"{key}: worst case needs noise {q['noise_ratio']:.2f} x eps (ambiguous if <= 2); EMF {q['Es_pu']:.3f} at "
                  f"{q['Ph_deg']:.2f} deg, IBR {q['I_mag']:.3f} at {q['I_deg']:.1f} deg -> ID {q['ID']:.4f} IQ {q['IQ']:.4f} "
                  f"D2ANG {q['D2ANG']:.2f}")
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "pscad", "witness.json"), "w"),
              indent=1)


if __name__ == "__main__":
    main()
