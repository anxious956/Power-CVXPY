"""Review of PR #44 part 3, item 2: what does "the inverter does not settle" look like? For the stored frames-EMT runs,
the injected I1 and delta (sequence phasors from the inverter ammeters, quarter-cycle steps, in the relay's pre-fault
frame) through the fault, against the static V1-referenced fixed point, plus |V1| at the inverter bus from the model.

    python review/checks/p44c_settle.py fe_d114_L1ab15r000 fe_d105_L1ab15r000 ...   (repo root at 6d8f812)
"""
import os, sys, json
import numpy as np
sys.path.insert(0, "src")
import frames as fr
from pscad_network import three_bus, WORK
from pscad_network_check import relay_y, injections, read_case
from network_delta_test import CASES

net = three_bus()
specs = {sp["name"]: sp for f in ("frames_emt_specs.json", "frames_emt_specs2.json")
         for sp in json.load(open(os.path.join("results", "network", f)))}
fm = fr.FrameModel(net, CASES[:1], n_samples=10, face_pts=2, seed=0)
for name in ([] if sys.argv[1:] == ["sweep"] else sys.argv[1:]):
    sp = specs[name]
    run = read_case(os.path.join(WORK, name + ".gf46"), name)
    y_pre = relay_y(run, 0.25)
    uL = y_pre[0] / abs(y_pre[0])
    d = complex(*sp["d_cmd"])
    k = CASES.index(tuple(sp["case"]))
    fmk = fr.FrameModel(net, [CASES[k]], n_samples=10, face_pts=2, seed=0)
    S = np.array([sp["S"]])
    e, ic = fmk.sources(S)
    _, _, u_pre = fmk.normal_state(S, d)
    u_f, i1_f, d_f, v1 = fr.fixed_point(fmk.maps_F[0][1], e, ic, d, fmk.i_max, 1, u_pre)
    _, uLm, _ = fmk.normal_state(S, d)
    print(f"{name}: model |V1_R| in the fault {v1[0]:.3f} pu; settled I1 {abs(i1_f[0]):.3f} pu, |delta| {abs(d_f[0]):.3f}; "
          f"settled frame turn from pre-fault {np.degrees(np.angle(u_f[0] / u_pre[0])):+.1f} deg")
    line = []
    for c in np.arange(1.0, 6.01, 0.5):
        t = 0.30 + c / 60
        (i1, i2), = injections(run, sp, t).values()
        i1, i2 = i1 * np.conj(uL), i2 * np.conj(uL)
        line.append(f"{c:.1f}c: d {np.degrees(np.angle(i2 / (d_f[0] * np.conj(uLm[0])))):+6.1f} deg |d| {abs(i2):.3f}")
    print("   delta angle vs settled model (relay frame), by cycles after inception:")
    for j in range(0, len(line), 4):
        print("     " + " | ".join(line[j:j + 4]))


def sweep():
    """Every stored frames-EMT fault run: the largest |delta angle - settled model| in windows ending 2.0-3.0 cycles
    (the decision window) and 3.5-5.5 cycles (before the fault clears at 6 cycles), per |delta| and fault type."""
    out = {}
    for name, sp in specs.items():
        if sp["kind"] != "fault" or not os.path.exists(os.path.join(WORK, name + ".gf46", name + "_01.out")):
            continue
        run = read_case(os.path.join(WORK, name + ".gf46"), name)
        uL = relay_y(run, 0.25)[0]; uL /= abs(uL)
        d = complex(*sp["d_cmd"]); k = CASES.index(tuple(sp["case"]))
        fmk = fr.FrameModel(net, [CASES[k]], n_samples=10, face_pts=2, seed=0)
        S = np.array([sp["S"]]); e, ic = fmk.sources(S)
        _, uLm, u_pre = fmk.normal_state(S, d)
        _, _, d_f, _ = fr.fixed_point(fmk.maps_F[0][1], e, ic, d, fmk.i_max, 1, u_pre)
        ref = d_f[0] * np.conj(uLm[0])
        dev = {}
        for c in np.arange(2.0, 5.51, 0.25):
            (_, i2), = injections(run, sp, 0.30 + c / 60).values()
            dev[c] = abs(np.degrees(np.angle(i2 * np.conj(uL) / ref)))
        key = (sp["dtag"], sp["case"][2], "bolted" if sp["case"][3] == 0 else "R_f")
        a = max(v for c, v in dev.items() if c <= 3.0); b = max(v for c, v in dev.items() if c > 3.0)
        out.setdefault(key, []).append((a, b, name))
    for key in sorted(out):
        v = out[key]
        wa = max(v, key=lambda t: t[0]); wb = max(v, key=lambda t: t[1])
        print(f"{key[0]} {key[1]} {key[2]:6s} ({len(v):2d} runs): max angle off the settled model, 2-3 cycles {wa[0]:6.1f} deg "
              f"({wa[2]}); 3.25-5.5 cycles {wb[1]:6.1f} deg ({wb[2]}); runs over 5 deg after 3 cycles {sum(t[1] > 5 for t in v)}")


if __name__ == "__main__" and sys.argv[1:] == ["sweep"]:
    sweep()
