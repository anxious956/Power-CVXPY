"""
Checks of the step-3 additions to the PSCAD builder (docs/STEP3.md), on three runs:

  s3_loadstep  a balanced load switched in at bus S at 0.30 s: the relay before and after must match the
               V1-referenced model (network.solve_v1ref) without and with that load
  s3_1ph       a single-phase load switched in: outside the sequence model; it must create negative- and
               zero-sequence current at the relay, and nothing before it switches
  s3_tf        an A-G fault asked for at 0.3033 s: the fault must start then (causal superimposed-current
               starter on the relay current)

    python src/step3_builder_check.py <specs.json>
"""
import os, sys, json, copy
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import network as nw
from pscad_network import three_bus, WORK
from pscad_network_check import relay_y, read_case
from pscad_check import to_128_per_cycle


def model_frame(net, run, sp, t=0.25):
    y = relay_y(run, t)
    e1 = y[0] + net.sgs["G"].zs[1] * y[3]
    e_spec = complex(*sp["sgs"]["G"]["e"])
    return np.exp(1j * (np.angle(e_spec) - np.angle(e1))), abs(e1) * np.exp(1j * np.angle(e_spec))


def main(path):
    specs = {s["name"]: s for s in json.load(open(path))}
    net = three_bus()
    sp = specs["s3_loadstep"]
    run = read_case(os.path.join(WORK, sp["name"] + ".gf46"), sp["name"])
    rot, e = model_frame(net, run, sp)
    st = {"I": sp["settings"]["I"]}
    for lab, t, extra in (("before the step", 0.25, None), ("after the step", 0.38, sp["confuser"])):
        n2 = copy.deepcopy(net)
        if extra:
            y_add = complex(*extra["y1"])
            n2.loads[extra["bus"]] = {s: n2.loads[extra["bus"]][s] + (y_add if s != 0 else 0) for s in (1, 2, 0)}
        ym, _, it = nw.solve_v1ref(n2, {"G": e}, st, None, lim=sp["lim"])
        print(f"load step, {lab}: max |EMT - V1-referenced model| = {np.abs(relay_y(run, t) * rot - ym).max():.4f} pu")
    sp = specs["s3_1ph"]
    run = read_case(os.path.join(WORK, sp["name"] + ".gf46"), sp["name"])
    rot, _ = model_frame(net, run, sp)
    yb, ya = relay_y(run, 0.25) * rot, relay_y(run, 0.38) * rot
    print(f"single-phase load: relay I2 {abs(yb[4]):.4f} -> {abs(ya[4]):.4f} pu, I0 {abs(yb[5]):.4f} -> {abs(ya[5]):.4f} pu, "
          f"V2 {abs(yb[1]):.4f} -> {abs(ya[1]):.4f} pu")
    sp = specs["s3_tf"]
    run = read_case(os.path.join(WORK, sp["name"] + ".gf46"), sp["name"])
    i = np.array([run["ch"][f"IL{p}"] for p in "ABC"])
    t = run["t"]
    di = np.abs(i[:, 1:] - i[:, :-1]).max(0)
    base = np.median(di[(t[1:] > 0.1) & (t[1:] < 0.29)])
    k = np.argmax((di > 20 * base) & (t[1:] > 0.29))
    print(f"fault asked at {sp['t_fault'] * 1e3:.2f} ms; the relay current jumps at {t[k + 1] * 1e3:.2f} ms "
          f"(sample {1e6 * (t[1] - t[0]):.0f} us)")


if __name__ == "__main__":
    main(sys.argv[1])
