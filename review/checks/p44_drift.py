"""Review of PR #44, question (3): is the +-6 deg drift margin enough? For every stored three-bus EMT fault run, the
angle of the injected delta (and I1) at the relay-decision time against the V1-referenced fixed point
(network.solve_v1ref with the run's own settings and measured EMF), i.e. the drift beyond the static model.
Also the relay-frame model error |EMT - model| in units of eps. Run from the repo root at PR #44 (7f2f2b5): python review/checks/p44_drift.py
"""
import os, sys, json
import numpy as np
sys.path.insert(0, "src")
import network as nw
from pscad_network import three_bus, WORK
from pscad_network_check import relay_y, injections, read_case

net = three_bus()
specs = json.load(open("results/network/three_bus_design.json"))
rows = []
for sp in specs:
    if sp["kind"] != "fault":
        continue
    d = os.path.join(WORK, sp["name"] + ".gf46")
    if not os.path.exists(os.path.join(d, sp["name"] + "_01.out")):
        continue
    run = read_case(d, sp["name"])
    y_pre = relay_y(run, 0.25)
    e1 = y_pre[0] + net.sgs["G"].zs[1] * y_pre[3]
    e_spec = complex(*sp["sgs"]["G"]["e"])
    rot = np.exp(1j * (np.angle(e_spec) - np.angle(e1)))
    st = sp["settings"]["I"]
    for t in (0.333, 0.35, 0.38, 0.395):
        y = relay_y(run, t) * rot
        (i1, i2), = injections(run, sp, t).values()
        i1, i2 = i1 * rot, i2 * rot
        ys, inj, _ = nw.solve_v1ref(net, {"G": abs(e1) * np.exp(1j * np.angle(e_spec))}, {"I": st}, tuple(sp["fault"]), lim=sp["lim"])
        i1m, dm = inj["I"]
        rows.append(dict(name=sp["name"], t=t, i1_turn=float(np.degrees(np.angle(i1 / i1m))),
                         d_turn=float(np.degrees(np.angle(i2 / dm))) if abs(dm) > 1e-6 else None,
                         err_eps=float(np.abs(nw._realify(y - ys)).max() / net.eps)))
for t in (0.333, 0.35, 0.38, 0.395):
    q = [r for r in rows if r["t"] == t]
    i1t = np.array([abs(r["i1_turn"]) for r in q])
    dt = np.array([abs(r["d_turn"]) for r in q if r["d_turn"] is not None])
    er = np.array([r["err_eps"] for r in q])
    w = max(q, key=lambda r: abs(r["i1_turn"]))
    print(f"t = {t:.3f} s ({(t - 0.30) * 60:.1f} cycles into the fault): |I1 turn beyond fixed point| median {np.median(i1t):.1f}, "
          f"max {i1t.max():.1f} deg ({w['name']}); delta max {dt.max():.1f} deg; over 6 deg: {int((i1t > 6).sum())} of {len(q)}; "
          f"|EMT - model| max {er.max():.2f} eps, median {np.median(er):.3f} eps")
