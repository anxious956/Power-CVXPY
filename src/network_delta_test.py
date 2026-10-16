"""
The multi-bus design tool's signal, injected in EMT on the three-bus network (steps 1 -> 2 of the plan).

  spec     design delta on the three-bus network (src/network.py: sound outer source set, per-phase limit
           inside, margin rho), then the PSCAD runs that test it: every fault case at its worst realisation
           with delta = 0 and with the design delta; normal operation at the 16 corners of the uncertainty
           box with both limiter types (LIM 1: delta kept, I1 cut, the limiter the design assumes; LIM 0).
           The inverter's angle settings are computed for the current it actually delivers after its limiter.
  analyse  the EMT relay measurement against the design's normal set: ratio = noise needed to put it inside,
           in units of eps; a fault is separated above 2, with the margin above 2 (1 + rho); normal ~0.

    python src/network_delta_test.py spec                       -> results/network/three_bus_design.json
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/network/three_bus_design.json
    python src/network_delta_test.py analyse                    -> results/network/three_bus_sweep.json
"""
import os, sys, json, itertools, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
from pscad_network import make_spec, three_bus, WORK
from pscad_network_check import relay_y, injections, read_case, assert_single_branch

OUT = os.path.join(HERE, "..", "results", "network")
RHO = 0.10
MRS = (0.0, 0.5, 1.0)
CASES = [("L1", m, s, mr) for s in ("ag", "ab") for m in (0.15, 0.35, 0.55, 0.75, 0.95) for mr in MRS] + \
        [("L2", m, s, mr) for s in ("ag", "ab") for m in (0.05, 0.25, 0.5) for mr in MRS]


def model():
    net = three_bus()
    return net, nw.NetModelSet(net, CASES, mode="outer")


def tag(case):
    ln, m, s, mr = case
    return f"{ln}{s}{int(round(m * 100)):02d}r{int(round(mr * 100)):03d}"


def spec_with_limiter(name, net, fault, req, delta, lim):
    """make_spec for a request that the limiter may cut: V1 (and so the angle settings) from the delivered
    currents, ID/IQ scaled back to the request so the controller asks for it and its limiter cuts it."""
    i_req = req["I"]
    i_del, d_del = nw.limiter(i_req, delta, net.ibrs["I"].i_max, lim)
    sp = make_spec(name, net, fault, {**req, "I": i_del}, {"I": d_del if lim == 0 else delta}, lim)
    st = sp["settings"]["I"]
    if abs(i_del) > 1e-9:
        sc = abs(i_req) / abs(i_del)
        st["ID"], st["IQ"] = st["ID"] * sc, st["IQ"] * sc
    if lim == 0 and abs(d_del) > 1e-12:
        st["D2MAG"] = float(abs(delta))
    sp["asked"] = dict(I=[i_req.real, i_req.imag], delta=[delta.real, delta.imag])
    return sp


def make():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    net, ms = model()
    amb0 = nw.unseparated(ms, 0j)
    des = {rho: nw.min_delta(ms, rho=rho, r_step=0.02, n_ang=72) for rho in (0.0, RHO)}
    d = des[RHO]["delta"]
    print(f"{len(CASES)} cases; {len(amb0)} not separated at delta = 0; design delta {des[0.0]['abs_delta']} pu "
          f"(rho 0), {des[RHO]['abs_delta']} pu at {des[RHO]['angle_deg']} deg (rho {RHO})  [{time.time() - t0:.0f} s]")
    lim_d = nw.limit_rows(ms, "I", d)
    lim_0 = nw.limit_rows(ms, "I", 0j)
    specs = []
    for f in ms.faults:
        case = f[0]
        for tg, dv, lim in (("d0", 0j, lim_0), ("dm", d, lim_d)):
            _, uF, t = nw.closest(ms, f, dv, lim)
            vals = nw.realisation(net, uF)
            sp = make_spec(f"tb_{tag(case)}_{tg}", net, (case[0], case[1], case[2], case[3] * net.rF), vals, {"I": dv} if abs(dv) else {}, 1)
            sp.update(kind="fault", case=list(case), tag=tg, design_ratio=float(t / net.eps), delta=[dv.real, dv.imag])
            specs.append(sp)
    for k, u in enumerate(itertools.product((-1, 1), repeat=2 * len(net.sources))):
        vals = nw.realisation(net, u)
        for lim in (1, 0):
            sp = spec_with_limiter(f"tb_N_c{k:02d}_lim{lim}", net, None, vals, d, lim)
            sp.update(kind="normal", corner=list(u), tag=f"lim{lim}", delta=[d.real, d.imag], design_ratio=None)
            specs.append(sp)
    json.dump(specs, open(os.path.join(OUT, "three_bus_design.json"), "w"), indent=1)
    json.dump(dict(cases=[list(c) for c in CASES], unseparated_at_0=[list(c) for c in amb0], rho=RHO, eps=net.eps,
                   designs={str(k): {kk: (str(vv) if isinstance(vv, complex) else vv) for kk, vv in v.items()} for k, v in des.items()}),
              open(os.path.join(OUT, "three_bus_design_summary.json"), "w"), indent=1)
    print(f"{len(specs)} runs -> results/network/three_bus_design.json  [{time.time() - t0:.0f} s]")


def analyse(t_pre=0.25, t_meas=0.38):
    net, ms = model()
    sg = assert_single_branch(net)
    specs = json.load(open(os.path.join(OUT, "three_bus_design.json")))
    rows = []
    for sp in specs:
        if not os.path.exists(os.path.join(WORK, sp["name"] + ".gf46", sp["name"] + "_01.out")):
            continue
        run = read_case(os.path.join(WORK, sp["name"] + ".gf46"), sp["name"])
        y_pre = relay_y(run, t_pre)
        e1 = y_pre[0] + net.sgs[sg].zs[1] * y_pre[3]
        e_spec = complex(*sp["sgs"][sg]["e"])
        rot = np.exp(1j * (np.angle(e_spec) - np.angle(e1)))
        tm = t_meas if sp["kind"] == "fault" else t_pre
        y = relay_y(run, tm) * rot
        (i1, i2), = [(a * rot, b * rot) for a, b in injections(run, sp, tm).values()]
        dv = complex(*sp["delta"])
        lim = nw.limit_rows(ms, "I", dv)
        fault = None if sp["fault"] is None else tuple(sp["fault"])
        ys = nw.solve(net, {sg: abs(e1) * np.exp(1j * np.angle(e_spec)), "I": i1}, {"I": i2}, fault)
        ratio = nw.noise_to_normal(ms, y, dv, lim) / net.eps
        peak = max(abs(i1 * nw.A3 ** (-k) + i2 * nw.A3 ** k) for k in range(3))
        rows.append(dict(name=sp["name"], kind=sp["kind"], tag=sp["tag"], case=sp.get("case"), corner=sp.get("corner"),
                         design_ratio=sp.get("design_ratio"), ratio=float(ratio), emt_vs_design=float(np.abs(y - ys).max()),
                         I1=float(abs(i1)), I2=float(abs(i2)), phase_peak=float(peak),
                         fault_dV1=float(abs(y[0] - y_pre[0] * rot)) if sp["kind"] == "fault" else 0.0))
    g = lambda kind, tg: [q for q in rows if q["kind"] == kind and q["tag"] == tg]
    f0, fm, n1, n0 = g("fault", "d0"), g("fault", "dm"), g("normal", "lim1"), g("normal", "lim0")
    bad = [q["name"] for q in rows if q["kind"] == "fault" and q["fault_dV1"] < 1e-3]
    big = [(q["name"], round(q["emt_vs_design"], 4)) for q in rows if q["emt_vs_design"] > 0.02]
    over = [q["name"] for q in rows if q["phase_peak"] > 1.21]
    print(f"checks: {len(rows)} runs; fault not visible {len(bad)} {bad[:3]}; |EMT - design| > 0.02 pu {len(big)} {big[:3]}; "
          f"phase peak > 1.21 pu {len(over)}; |EMT - design| median {np.median([q['emt_vs_design'] for q in rows]):.5f}, "
          f"max {max(q['emt_vs_design'] for q in rows):.4f} pu")
    if f0:
        nsep = [q for q in f0 if q["ratio"] <= 2]
        mism = [q["name"] for q in f0 if (q["ratio"] <= 2) != (q["design_ratio"] <= 2)]
        print(f"{len(f0)} cases at their worst realisation, delta = 0: {len(nsep)} not separated; EMT and design disagree on {len(mism)} {mism[:4]}")
    if fm:
        w = min(fm, key=lambda q: q["ratio"])
        print(f"{len(fm)} cases at their worst realisation, design delta: {sum(q['ratio'] > 2 for q in fm)} separated, "
              f"{sum(q['ratio'] > 2 * (1 + RHO) for q in fm)} with the margin; smallest {w['ratio']:.2f} ({w['name']}, design {w['design_ratio']:.2f})")
    for lab, n in (("LIM 1", n1), ("LIM 0", n0)):
        if n:
            print(f"normal operation, {len(n)} corners, {lab}: {sum(q['ratio'] >= 0.05 for q in n)} outside the normal set; "
                  f"largest ratio {max(q['ratio'] for q in n):.2f}")
    json.dump(dict(rho=RHO, rows=rows), open(os.path.join(OUT, "three_bus_sweep.json"), "w"), indent=1)
    print("-> results/network/three_bus_sweep.json")


if __name__ == "__main__":
    {"spec": make, "analyse": analyse}[sys.argv[1]]()
