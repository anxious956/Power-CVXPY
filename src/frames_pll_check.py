"""
The cap on |delta| with the PLL-like reference filter (first order, TANG = 1 / (2 pi 15 Hz)) that step 3 will use
(review/STEP3_PART4_REVIEW.md: the bare DFT reference loses its frame on bolted phase-to-phase faults above 1.05 pu).

  cap      |delta| 1.05 / 1.10 / 1.14 / 1.18 pu at 221, 225 and 230 deg, on the 8 bolted ab cases (at the source points
           of the 1.14 pu runs) and the 3 A-G witnesses with the smallest gap (frames_design_check): 132 runs
  sens     the two instrumented cases (1.14 pu L1 ab 15 %, 1.05 pu L1 ab 35 %, 0.3 s fault) at 10 and 30 Hz: 4 runs

The cap is the largest level whose fault points stay inside their own bare set (factor 1.0, no reference noise, no
model-error box) through the whole fault, windows ending 1.5 ... 5.5 cycles after inception; the window start is the
earliest of 1.5 / 1.75 / 2.0 cycles from which every point is inside.

    python src/frames_pll_check.py spec        -> results/network/frames_pll_specs.json
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/network/frames_pll_specs.json
    python src/frames_pll_check.py analyse     -> results/network/frames_pll_check.json
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import make_spec, three_bus, WORK
from pscad_network_check import relay_y, read_case
from network_delta_test import CASES, tag
from frames_emt_check import _settings
from frames_design_check import SPECS as DESIGN_SPECS, BARE, MAIN, EPS, TANG_PLL

OUT = os.path.join(HERE, "..", "results", "network")
SPECS = os.path.join(OUT, "frames_pll_specs.json")
MAGS = (1.05, 1.10, 1.14, 1.18)
ANGS = (221.0, 225.0, 230.0)
WIN = np.arange(1.5, 5.5001, 0.25)
T_FAULT = 0.30
SENS_HZ = (10.0, 30.0)


def d_of(mag, ang):
    return mag * np.exp(1j * np.radians(ang))


def make():
    net = three_bus()
    fm = fr.FrameModel(net, CASES[:1], n_samples=10, face_pts=2, seed=0)
    design = json.load(open(DESIGN_SPECS))
    edge = {tuple(sp["case"]): sp["S"] for sp in design if sp["group"] == "edge" and sp["angle"] == 221.0}
    inst = [sp for sp in design if sp["group"] == "inst" and sp["name"].endswith("_dft")]
    specs = []
    for mag in MAGS:
        for ang in ANGS:
            for c, S in edge.items():
                e, ic = fm.sources(np.array([S]))
                sp = make_spec(f"fp_{int(round(mag * 100))}_{int(ang)}_{tag(c)}", net, (c[0], c[1], c[2], c[3] * net.rF),
                               {"G": e[0]}, {}, 1)
                sp["settings"] = _settings(ic[0], d_of(mag, ang))
                sp["settings"]["I"]["TANG"] = TANG_PLL
                sp.update(kind="fault", group="cap", case=list(c), S=S, mag=mag, angle=ang, d_cmd=[d_of(mag, ang).real, d_of(mag, ang).imag])
                specs.append(sp)
    for b in inst:
        for hz in SENS_HZ:
            sp = json.loads(json.dumps(b))
            sp["name"] = b["name"].replace("_dft", f"_lp{int(hz)}").replace("fd_i", "fp_i")
            sp["settings"]["I"]["TANG"] = 1.0 / (2 * np.pi * hz)
            sp.update(group="sens", hz=hz, mag=float(sp["settings"]["I"]["D2MAG"]))
            specs.append(sp)
    json.dump(specs, open(SPECS, "w"), indent=1, default=float)
    print(f"{len(specs)} runs -> {os.path.relpath(SPECS)}")


def analyse():
    net = three_bus()
    specs = json.load(open(SPECS))
    bare = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, **BARE)
    main = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, **MAIN)
    rows = []
    t0 = time.time()
    for sp in specs:
        path = os.path.join(WORK, sp["name"] + ".gf46")
        if not os.path.exists(os.path.join(path, sp["name"] + "_01.out")):
            print("missing", sp["name"])
            continue
        run = read_case(path, sp["name"])
        tf = sp.get("t_fault", T_FAULT)
        d = complex(*sp["d_cmd"])
        uL = relay_y(run, tf - 0.05)[0]
        uL /= abs(uL)
        k = CASES.index(tuple(sp["case"]))
        cyc = WIN if sp["group"] == "cap" else np.array([2.0, 3.0, 5.0, 8.0, 12.0, 16.0])
        try:
            own = [fr.distance_to_set(bare.zonotopes(d, k), relay_y(run, tf + c / 60) * np.conj(uL)) / EPS for c in cyc]
            to_n = [fr.distance_to_set(main.zonotopes(d, None), relay_y(run, tf + c / 60) * np.conj(uL)) / EPS for c in cyc if 2.0 <= c <= 3.0]
        except RuntimeError as err:                      # no settled static state at this command: not a design candidate
            print(f"{sp['name']}: static model inadmissible ({str(err)[:60]})")
            continue
        v1 = np.asarray(run["ch"].get("V1M_I", []))
        rows.append(dict(name=sp["name"], group=sp["group"], case=sp["case"], mag=sp["mag"], angle=sp.get("angle", 225.0),
                         hz=sp.get("hz"), cycles=[float(c) for c in cyc], outside_own_eps=[float(x) for x in own],
                         ratio_to_N=min(to_n) if to_n else None,
                         v1_inverter=[float(v1.min()), float(v1.max())] if len(v1) else None))
    print(f"{len(rows)} runs analysed  [{time.time() - t0:.0f} s]")
    summ = {}
    for mag in MAGS:
        q = [r for r in rows if r["group"] == "cap" and r["mag"] == mag]
        if not q:
            continue
        whole = [max(x for c, x in zip(r["cycles"], r["outside_own_eps"]) if c >= 2.0) for r in q]
        start = None
        for s0 in (1.5, 1.75, 2.0):
            if all(max(x for c, x in zip(r["cycles"], r["outside_own_eps"]) if c >= s0) <= 1e-6 for r in q):
                start = s0
                break
        w = q[int(np.argmax(whole))]
        rn = [r["ratio_to_N"] for r in q]
        summ[str(mag)] = dict(n=len(q), outside_own_max_from_2c=max(whole), at=w["name"], n_outside=int(sum(x > 1e-6 for x in whole)),
                              window_start_cycles=start, ratio_to_N_min=min(rn),
                              by_angle={str(a): max(m for r, m in zip(q, whole) if r["angle"] == a) for a in ANGS})
        print(f"|delta| {mag:.2f}: {len(q)} runs; outside own set from 2 c to 5.5 c: {summ[str(mag)]['n_outside']} runs, max "
              f"{max(whole):.3f} eps ({w['name']}); by angle {summ[str(mag)]['by_angle']}; all inside from {start} c; "
              f"clean distance to N (2-3 c) min {min(rn):.2f} eps")
    for r in rows:
        if r["group"] == "sens":
            print(f"{r['name']}: outside own set at 2/3/5/8/12/16 c " + " ".join(f"{x:.2f}" for x in r["outside_own_eps"])
                  + f"; inverter |V1| {r['v1_inverter']}")
    json.dump(dict(tang_hz=15.0, mags=MAGS, angles=ANGS, summary=summ, rows=rows),
              open(os.path.join(OUT, "frames_pll_check.json"), "w"), indent=1, default=float)
    print("-> results/network/frames_pll_check.json")


if __name__ == "__main__":
    {"spec": make, "analyse": analyse}[sys.argv[1]]()
