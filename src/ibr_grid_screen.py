"""
A static screen before an inverter-dominated step-3 run (the reviewer's proposal after SORULAR_CEVAPLAR Q42): the
same three-bus network with the relay-end synchronous source replaced by a grid-following inverter, and the voltage
reference moved to bus S (the old source impedance, now a grid equivalent there). Every inverter's zero- and
negative-sequence paths are open, as the PSCAD builder requires: the relay end supplies no 3I0 and no I2.

  A  the designed delta injected by the inverter at R (as before); a non-injecting inverter at the relay bus L
  B  the designed delta injected by the inverter at the relay bus L; a non-injecting inverter at R

For each: (1) what a conventional incremental element sees at the relay on the hard faults at delta = 0 (A-G,
R_f 20-40 ohm, the design's locations): |delta I0|, |delta I2|, |delta I1| and |delta V1| against normal operation,
static absolute model at nominal sources; (2) the absolute-frame design (network.min_delta, current limit inside)
at eps = 0.08 and 0.04 pu, rho = 0.1: cases unseparated at delta = 0 and delta*. The two-frame model (src/frames.py)
assumes one synchronous source at the relay bus and one injecting inverter, so this screen uses the absolute
frames; it decides whether the EMT study and the generalisation are worth it.

    python src/ibr_grid_screen.py      -> results/network/ibr_grid_screen.json
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
import zone_model as zm
from network_delta_test import CASES

OUT = os.path.join(HERE, "..", "results", "network", "ibr_grid_screen.json")
HARD = [c for c in CASES if c[2] == "ag" and c[3] >= 0.5]


def grid(injector_at, zero_z=1e6, neg_z=1e6):
    """zero_z / neg_z of the relay-end inverter's interface: open (the PSCAD builder's), a grounded YNd transformer
    (zero_z finite), or an IEEE 2800 V2-referenced negative-sequence current (neg_z = j / K2, K2 = 2)."""
    p = zm.ZoneParams()
    i_L = 0.5 * np.exp(-0.2j)
    return nw.Network(lines={"L1": nw.Line("L", "R", p.z1, p.z0_ratio * p.z1), "L2": nw.Line("R", "S", p.z2, p.z0_ratio * p.z2)},
                      sgs={"G": nw.SG("S", dict(p.zs), p.e0)},
                      ibrs={"IL": nw.IBR("L", i_L, (0.3, 0.3), neg_z, zero_z, inject=(injector_at == "L"), i_max=1.2),
                            "I": nw.IBR("R", p.i0, (0.3, 0.3), 1e6, 1e6, inject=(injector_at == "R"), i_max=1.2)},
                      loads={"R": dict(p.yR), "S": dict(p.yS)}, relay=("L1", "a"), eps=0.08, rF=p.rF)


def main():
    out = {}
    for label, at in (("A: injector at R", "R"), ("B: injector at the relay bus L", "L")):
        net = grid(at)
        t0 = time.time()
        yN = nw.solve(net)
        inc = []
        for ln, m, s, mr in HARD:
            y = nw.solve(net, fault=(ln, m, s, mr * net.rF))
            d = y - yN
            inc.append(dict(case=[ln, m, s, mr], dI0=float(abs(d[5])), dI2=float(abs(d[4])), dI1=float(abs(d[3])),
                            dV1=float(abs(d[0])), V2=float(abs(y[1])), V0=float(abs(y[2]))))
        res = dict(normal_relay=[[float(z.real), float(z.imag)] for z in yN], hard_increments=inc,
                   max_3dI0=max(3 * q["dI0"] for q in inc), max_dI2=max(q["dI2"] for q in inc),
                   min_dI1=min(q["dI1"] for q in inc), min_dV1=min(q["dV1"] for q in inc), designs={})
        print(f"{label}: hard A-G at delta 0: 3|dI0| max {res['max_3dI0']:.4f}, |dI2| max {res['max_dI2']:.4f}, "
              f"|dI1| min {res['min_dI1']:.3f}, |dV1| min {res['min_dV1']:.3f} pu", flush=True)
        for eps in (0.08, 0.04):
            ms = nw.NetModelSet(net, CASES, mode="outer", eps=eps)
            u0 = nw.unseparated(ms, 0j)
            r = nw.min_delta(ms, rho=0.1, r_step=0.02, n_ang=72, r_max=1.2)
            res["designs"][str(eps)] = dict(unseparated_at_0=len(u0), abs_delta=r.get("abs_delta"), angle_deg=r.get("angle_deg"),
                                            feasible=r.get("feasible", r.get("abs_delta") is not None))
            print(f"   eps {eps}: unseparated at delta 0: {len(u0)} of {len(CASES)}; delta* (rho 0.1, absolute frames) "
                  f"{r.get('abs_delta')} at {r.get('angle_deg')}  [{time.time() - t0:.0f} s]", flush=True)
        out[label] = res
    # the relay-end interface variants (review of 29c73a3): what each conventional element sees, delta = 0
    variants = {"open paths": dict(), "grounded YNd (zero_z 0.15j)": dict(zero_z=0.15j),
                "IEEE 2800 I2 (K2 2, neg_z j/2)": dict(neg_z=0.5j), "both": dict(zero_z=0.15j, neg_z=0.5j)}
    out["interface_variants"] = {}
    print("relay-end interface variants, hard A-G at delta 0 (min-max over the cases):")
    for lab, kw in variants.items():
        net = grid("R", **kw)
        yN = nw.solve(net)
        q = [nw.solve(net, fault=(ln, m, s_, mr * net.rF)) for ln, m, s_, mr in HARD]
        cols = dict(three_dI0=[3 * abs(y[5] - yN[5]) for y in q], dI2=[abs(y[4] - yN[4]) for y in q],
                    V0=[abs(y[2]) for y in q], V2=[abs(y[1]) for y in q])
        out["interface_variants"][lab] = {k: [float(min(v)), float(max(v))] for k, v in cols.items()}
        print(f"   {lab:32s} " + "  ".join(f"{k} {min(v):.2f}-{max(v):.2f}" for k, v in cols.items()))
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    print("-> results/network/ibr_grid_screen.json")


if __name__ == "__main__":
    main()
