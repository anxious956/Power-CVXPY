"""
Stage (b) of docs/I2_DIRECTION.md: can a designed delta certify direction at the inverter's relay when every load
behind it is inverter-interfaced (s = 1, the filter-shunt bracket, the source inverter suppressing I2)?

  regress   the three regression tests registered for the generalised model (src/frames_multi.py):
              1 with no sinks it reproduces frames.FrameModel's sets on the step-3 network
              2 at delta = 0, the nominal source point, settled frames: its relay measurements equal solve_v1ref's
              3 the same at random source points
  design    the set-vs-set design: the smallest delta (in the source inverter's V1 frame, within the 1.14 pu cap) for
            which every forward case's set and every reverse case's set are 2 eps (1 + rho) apart; rho 0.1 and 0.
            Main configuration otherwise (eps 0.08 box, phi_ref 0.0303 rad, model error 0.008 pu, drift 3 deg).

    python src/i2dir_design.py regress
    python src/i2dir_design.py design      -> results/network/i2dir_design.json
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
import frames as fr
from frames_multi import FrameModelMulti
from pscad_network import three_bus
from network_delta_test import CASES
from i2dir_static import network_s, network, operating_point, FWD, REV

OUT = os.path.join(HERE, "..", "results", "network")
KW = dict(factor=1.1, drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.008)
U0 = (0.0, 0.0, 0.0, 0.0)


def model(cases, n_samples=150, face_pts=3, seed=1):
    net = network_s(1.0, 1e6, filters=True, inject=True)
    _, st = operating_point(1.0, 1e6, U0)
    sinks = {k: complex(v["ID"], -v["IQ"]) for k, v in st.items() if k != "I"}
    return FrameModelMulti(net, cases, sinks=sinks, base_net=network(1e6, 1.0), n_samples=n_samples, face_pts=face_pts,
                           seed=seed, **KW), net, st


def regress():
    # 1: no sinks reproduces FrameModel on the step-3 network
    net = three_bus()
    a = fr.FrameModel(net, CASES[:3], n_samples=40, face_pts=2, seed=1, **KW)
    b = FrameModelMulti(net, CASES[:3], sinks={}, n_samples=40, face_pts=2, seed=1, **KW)
    d = 1.12 * np.exp(1j * np.radians(225))
    diff = max(max(np.abs(za[0] - zb[0]).max(), np.abs(za[1] - zb[1]).max())
               for k in [None, 0, 1, 2] for za, zb in zip(a.zonotopes(d, k), b.zonotopes(d, k)))
    print(f"1  no sinks vs FrameModel, 4 sets at 1.12 pu: largest difference in (c, G) {diff:.2e}")
    # 2 and 3: the generalised model against solve_v1ref on the s = 1 shunt network
    fm, net1, st = model(FWD[:6] + REV[:4], n_samples=10, face_pts=2)
    p = 0
    for label, S in (("nominal", np.zeros(4)),) + tuple((f"random {j}", np.random.default_rng(j).uniform(-1, 1, 4)) for j in range(3)):
        e, ic = fm.sources(S[None])
        st_s = dict(st)
        st_s["I"] = dict(ID=float(ic[0].real), IQ=float(-ic[0].imag), D2MAG=0.0, D2ANG=0.0)
        yN, _, _ = nw.solve_v1ref(net1, {"G": e[0]}, st_s, None, relax=0.5, max_iter=2000)
        uL = np.conj(yN[0] / abs(yN[0]))
        worst = float(np.abs(fm.measure(S[None], 0j, None)[0] - yN * uL).max())
        for k, c in enumerate(fm.cases):
            y, _, _ = nw.solve_v1ref(net1, {"G": e[0]}, st_s, (c[0], c[1], c[2], c[3] * net1.rF), relax=0.5, max_iter=2000)
            worst = max(worst, float(np.abs(fm.measure(S[None], 0j, k)[0] - y * uL).max()))
        print(f"{'2' if label == 'nominal' else '3'}  {label:9s}: largest |FrameModelMulti - solve_v1ref| over normal + {len(fm.cases)} faults "
              f"(delta 0, settled frames) {worst:.2e} pu")


def design(rhos=(0.1, 0.0)):
    cases = FWD + REV
    fm, _, _ = model(cases)
    A, B = list(range(len(FWD))), list(range(len(FWD), len(cases)))
    order = {"last": None}

    def apart(d, rho):
        b = 2 * fm.eps * (1 + rho)
        pairs = [(i, j) for i in A for j in B]
        if order["last"] in pairs:
            pairs.remove(order["last"])
            pairs.insert(0, order["last"])
        for i, j in pairs:
            if fr._meet_union(fm.zonotopes(d, i), fm.zonotopes(d, j), b):
                order["last"] = (i, j)
                return False
        return True

    def try_(d, rho):
        try:
            return apart(d, rho)
        except RuntimeError:
            return False

    out = []
    for rho in rhos:
        t0 = time.time()
        b = 2 * fm.eps * (1 + rho)
        n0 = sum(fr._meet_union(fm.zonotopes(0j, i), fm.zonotopes(0j, j), b) for i in A for j in B)
        res = dict(rho=rho, pairs=len(A) * len(B), unseparated_pairs_at_0=int(n0))
        print(f"rho {rho}: forward-reverse pairs not apart at delta = 0: {n0} of {len(A) * len(B)}  [{time.time() - t0:.0f} s]", flush=True)
        found = (0.0, 0.0) if n0 == 0 else None
        if found is None:
            r0 = next((r for r in np.arange(0.1, 1.14 + 1e-9, 0.1) if any(try_(r * np.exp(1j * np.radians(a)), rho) for a in range(0, 360, 15))), None)
            if r0 is not None:
                for r in np.arange(max(0.02, r0 - 0.1), r0 + 1e-9, 0.02):
                    a = next((a for a in np.arange(0, 360, 5) if try_(r * np.exp(1j * np.radians(a)), rho)), None)
                    if a is not None:
                        found = (float(round(r, 4)), float(a))
                        break
        res.update(abs_delta=None if found is None else found[0], angle_deg=None if found is None else found[1],
                   feasible=found is not None, seconds=time.time() - t0)
        out.append(res)
        print(f"rho {rho}: direction delta* {res['abs_delta']} at {res['angle_deg']} (feasible {res['feasible']})  [{res['seconds']:.0f} s]", flush=True)
        json.dump(dict(bracket="converter-side control (filter shunts), s = 1", fwd=FWD, rev=REV, runs=out),
                  open(os.path.join(OUT, "i2dir_design.json"), "w"), indent=1)


if __name__ == "__main__":
    {"regress": regress, "design": design}[sys.argv[1]]()
