"""
Are the window-start excursions of the PLL-like cap runs a DC offset in the relay's one-cycle DFT, not an inverter
transient (review/STEP3_PART5_REVIEW.md point 2)? The stored runs re-evaluated, no new PSCAD runs: the distance of
each fault point to its own bare set, on windows ending every 1/16 cycle from 1.5 to 2.5 cycles after inception and
every 1/4 cycle to 5.5 cycles, with the plain one-cycle DFT and with a mimic filter on the currents matched to L1
(X/R = 10, tau = 1.59 cycles, as src/review/common.py's mimic).

    python src/frames_mimic_check.py [specs.json ...]   (default: the cap sweep, results/network/frames_pll_specs.json,
                                                          and the design-point batch if its runs exist)
                                                     -> results/network/frames_mimic_check.json
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import three_bus, WORK
from pscad_network_check import relay_y, read_case
from network_delta_test import CASES
from frames_design_check import BARE, EPS

OUT = os.path.join(HERE, "..", "results", "network")
DEFAULT = [os.path.join(OUT, "frames_pll_specs.json"), os.path.join(OUT, "frames_design_specs_pll.json")]
CYC = np.concatenate([np.arange(1.5, 2.5001, 1 / 16), np.arange(2.75, 5.5001, 0.25)])


def main(paths):
    net = three_bus()
    z1 = net.lines["L1"].z1
    tau = (z1.imag / z1.real) / (2 * np.pi)
    bare = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, **BARE)
    rows = []
    t0 = time.time()
    for path in paths:
        if not os.path.exists(path):
            continue
        for sp in json.load(open(path)):
            if sp.get("kind") != "fault" or sp.get("group") not in ("cap", "witness", "edge", "pow", "all48"):
                continue
            d = os.path.join(WORK, sp["name"] + ".gf46")
            if not os.path.exists(os.path.join(d, sp["name"] + "_01.out")):
                continue
            run = read_case(d, sp["name"])
            tf = sp.get("t_fault", 0.30)
            dc = complex(*sp["d_cmd"])
            k = CASES.index(tuple(sp["case"]))
            try:
                pieces = bare.zonotopes(dc, k)
            except RuntimeError:
                continue
            out = {}
            for lab, tm in (("plain", None), ("mimic", tau)):
                uL = relay_y(run, tf - 0.05, tm)[0]
                uL /= abs(uL)
                out[lab] = [float(fr.distance_to_set(pieces, relay_y(run, tf + c / 60, tm) * np.conj(uL)) / EPS) for c in CYC]
            rows.append(dict(name=sp["name"], group=sp["group"], case=sp["case"], mag=round(float(abs(dc)), 4), t_fault=tf, **out))
    print(f"{len(rows)} runs  [{time.time() - t0:.0f} s]; mimic tau {tau:.2f} cycles")
    summ = {}
    for mag in sorted({r["mag"] for r in rows}):
        q = [r for r in rows if abs(r["mag"] - mag) < 1e-9]
        for lab in ("plain", "mimic"):
            M = np.array([r[lab] for r in q])
            start = next((c for i, c in enumerate(CYC) if M[:, i:].max() <= 1e-6), None)
            in_box = next((c for i, c in enumerate(CYC) if M[:, i:].max() <= 0.1), None)
            from2 = M[:, CYC >= 2.0 - 1e-9].max()
            summ[f"{mag:.2f}_{lab}"] = dict(n=len(q), max_from_2c=float(from2), all_inside_from=start, inside_box_from=in_box,
                                           max_1p5_2p5=float(M[:, CYC <= 2.5 + 1e-9].max()))
            print(f"|delta| {mag:.2f} {lab:5s}: {len(q)} runs; outside own set from 2.0 c max {from2:.3f} eps; "
                  f"every point inside from {start} c, inside the 0.1 eps box from {in_box} c")
    json.dump(dict(tau_cycles=tau, cycles=list(map(float, CYC)), summary=summ, rows=rows),
              open(os.path.join(OUT, "frames_mimic_check.json"), "w"), indent=1)
    print("-> results/network/frames_mimic_check.json")


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
