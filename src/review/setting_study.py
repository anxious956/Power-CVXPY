"""Q-fair rung 4: a zone-1 setting study from the grid graph alone (no EMT records used to set it).

Sequence-domain phasor short-circuit model built from the EvEMTBench graph pickle:
  external grids   Sk'' (snss), R/X (rntxn), X0/X1 (x0tx1), R0/X0 (r0tx0), EMF 1.0 pu at 110 kV base,
                   behind the YN-YN 500 MVA transformers (uk, Pcu, x0pu, r0pu)
  lines            z1 = rline + j xline, z0 = rline0 + j xline0 per km, no mutual coupling
                   (the benchmark's parallel circuits are separate single-circuit line types)
  loads            constant impedance from P, Q at 110 kV, no zero-sequence path
  inverters        ignored (35 and 50 MVA against two 30 GVA grids)
Faults by superposition on the pre-fault solution, fault point inserted on a line at fraction m or at
a bus: LG (a-g), LL (b-c), LLG (b-c-g), 3PH, fault resistance R_f per phase to the fault point.
The relay's loop impedances use the same k0 compensation as the EMT element.

Setting rule, as in a setting study: zone-1 reactance reach = min(0.85 X_line, 0.9 * min apparent
reactance of every external fault in the study set with R_f <= R_f,max), where the study set is
the remote bus and the first 20 % of each line leaving it. R_f,max is an assumption of the study
(10, 20 and 40 ohm reported). The script also validates the model against the EMT records: apparent
reactance predicted vs measured for every in/out-of-zone case at 50 ms.

    python src/review/setting_study.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm

A = np.exp(2j * np.pi / 3)
UB = 110e3


def build(graph):
    main = sorted(n for n in graph.nodes if str(n).startswith("MainBus"))
    lines, grids, loads = {}, [], {}
    for u, v, k, d in graph.edges(keys=True, data=True):
        p = d.get(f"{k}_param_dict", {})
        if "xline" in p and u in main and v in main:
            L = p["length"]
            lines[k] = (u, v, L * complex(p["rline"], p["xline"]), L * complex(p["rline0"], p["xline0"]))
        tp = d.get(f"{k}_typ_param_dict", {})
        if "uktr" in tp:
            bus = u if u in main else v
            other = v if bus == u else u
            gp = next((val for key, val in graph.nodes[other].items() if key.startswith("ExtGrid")), None)
            if gp is None or bus not in main:
                continue
            S = tp["strn"] * 1e6
            zt = tp["uktr"] / 100 * UB**2 / S
            rt = tp["pcutr"] * 1e3 * UB**2 / S**2
            zt1 = complex(rt, np.sqrt(zt**2 - rt**2))
            zt0 = complex(tp["r0pu"], tp["x0pu"]) * UB**2 / S
            zg = UB**2 / (gp["snss"] * 1e6)
            xg = zg / np.sqrt(1 + gp["rntxn"]**2)
            zg1 = complex(gp["rntxn"] * xg, xg)
            xg0 = gp["x0tx1"] * xg
            zg0 = complex(gp["r0tx0"] * xg0, xg0)
            grids.append((bus, zg1 + zt1, zg0 + zt0))
    for n in main:
        for key, val in graph.nodes[n].items():
            if key.startswith("Ld") and isinstance(val, dict):
                s = complex(val["p"], val["q"]) * 1e6
                loads[n] = np.conj(s) / UB**2 / 1.0          # Y = S*/V^2 (per phase, line-to-line base)
    return main, lines, grids, loads


def ybus(main, lines, grids, loads, seq, fault_line=None, m=None):
    nodes = list(main) + (["F"] if fault_line else [])
    ix = {n: i for i, n in enumerate(nodes)}
    Y = np.zeros((len(nodes), len(nodes)), complex)
    I = np.zeros(len(nodes), complex)

    def branch(a, b, z):
        y = 1 / z
        Y[ix[a], ix[a]] += y; Y[ix[b], ix[b]] += y; Y[ix[a], ix[b]] -= y; Y[ix[b], ix[a]] -= y

    for name, (u, v, z1, z0) in lines.items():
        z = z1 if seq in (1, 2) else z0
        if name == fault_line:
            branch(u, "F", m * z); branch("F", v, (1 - m) * z)
        else:
            branch(u, v, z)
    for bus, z1, z0 in grids:
        z = z1 if seq in (1, 2) else z0
        Y[ix[bus], ix[bus]] += 1 / z
        if seq == 1:
            I[ix[bus]] += (UB / np.sqrt(3)) / z
    if seq in (1, 2):
        for bus, y in loads.items():
            Y[ix[bus], ix[bus]] += y
    return nodes, ix, Y, I


def solve_fault(net, relay_bus, relay_line, where, ftype, rf, m=0.0):
    """where = ('line', name) or ('bus', name). Returns relay sequence phasors (post) [0,+,-] for V, I
    and pre-fault, phase-a reference; LL/LLG on phases b-c."""
    main, lines, grids, loads = net
    fl = where[1] if where[0] == "line" else None
    m = float(np.clip(m, 1e-4, 1 - 1e-4))
    Vpre, Vpost, Ipre_l, Ipost_l = {}, {}, None, None
    Z = {}
    for seq in (1, 2, 0):
        nodes, ix, Y, I = ybus(main, lines, grids, loads, seq, fl, m)
        Zb = np.linalg.inv(Y)
        Z[seq] = (nodes, ix, Zb)
        if seq == 1:
            v0 = Zb @ I
    nodes, ix, _ = Z[1]
    f = ix["F"] if fl else ix[where[1]]
    vf = v0[f]
    z1, z2, z0 = Z[1][2][f, f], Z[2][2][f, f], Z[0][2][f, f]
    if ftype == "lg":
        i1 = vf / (z1 + z2 + z0 + 3 * rf); i2 = i1; i0 = i1
    elif ftype == "ll":
        i1 = vf / (z1 + z2 + rf); i2 = -i1; i0 = 0.0
    elif ftype == "llg":
        za, zb_, zc = z1 + rf, z2 + rf, z0 + rf
        i1 = vf / (za + zb_ * zc / (zb_ + zc)); i2 = -i1 * zc / (zb_ + zc); i0 = -i1 * zb_ / (zb_ + zc)
    elif ftype == "3ph":
        i1 = vf / (z1 + rf); i2 = 0.0; i0 = 0.0
    If = {1: i1, 2: i2, 0: i0}
    # relay line current from relay_bus toward the other end (or toward F if the fault is on that line)
    u, v, zl1, zl0 = lines[relay_line]
    far = v if u == relay_bus else u
    Vs, Is, Vp, Ip = {}, {}, {}, {}
    for seq in (1, 2, 0):
        nodes_s, ix_s, Zb = Z[seq]
        dv = -Zb[:, f] * If[seq]
        vpre = v0 if seq == 1 else np.zeros(len(nodes_s), complex)
        vv = vpre + dv
        zl = zl1 if seq in (1, 2) else zl0
        if fl == relay_line:
            zseg = (m if u == relay_bus else 1 - m) * zl
            other = ix_s["F"]
        else:
            zseg = zl
            other = ix_s[far]
        Vs[seq] = vv[ix_s[relay_bus]]
        Is[seq] = (vv[ix_s[relay_bus]] - vv[other]) / zseg
        Vp[seq] = vpre[ix_s[relay_bus]]
        Ip[seq] = (vpre[ix_s[relay_bus]] - vpre[other]) / zseg
    seqv = lambda d: np.array([d[0], d[1], d[2]])
    return seqv(Vs), seqv(Is), seqv(Vp), seqv(Ip)


def source_impedances(net, relay_bus, relay_line, seq=2):
    """Thevenin source impedance behind each end of the protected line, with the line itself removed
    (what a setting study lists as Z_S and Z_R), plus the transfer impedance between the two ends
    through the rest of the network (parallel paths)."""
    main, lines, grids, loads = net
    u, v, zl1, zl0 = lines[relay_line]
    remote = v if u == relay_bus else u
    rest = {k: val for k, val in lines.items() if k != relay_line}
    nodes, ix, Y, _ = ybus(main, rest, grids, loads, seq)
    Zb = np.linalg.inv(Y)
    zs, zr, zt = Zb[ix[relay_bus], ix[relay_bus]], Zb[ix[remote], ix[remote]], Zb[ix[relay_bus], ix[remote]]
    return complex(zs), complex(zr), complex(zt), complex(zl1 if seq in (1, 2) else zl0)


def tilt_angles(net, relay_bus, relay_line, m=0.85):
    """Non-homogeneity angle T = angle of the current distribution factor at the reach point.
    two_source: textbook two-machine formula from the source impedance angles at both ends,
        D = (Z_R + (1 - m) Z_L) / (Z_S + Z_L + Z_R)
    network: the exact factor from the full sequence network (injection at the reach point), which
        also accounts for parallel paths between the two ends."""
    out = {}
    for seq in (1, 2):
        zs, zr, zt, zl = source_impedances(net, relay_bus, relay_line, seq)
        D2 = (zr + (1 - m) * zl) / (zs + zl + zr)
        main, lines, grids, loads = net
        nodes, ix, Y, _ = ybus(main, lines, grids, loads, seq, relay_line, m)
        Zb = np.linalg.inv(Y)
        f = ix["F"]
        dv = -Zb[:, f] * 1.0                                   # 1 A drawn at the fault point
        u, v, _, _ = lines[relay_line]
        zseg = (m if u == relay_bus else 1 - m) * zl
        i_relay = (dv[ix[relay_bus]] - dv[f]) / zseg
        out[seq] = dict(Z_S=[zs.real, zs.imag], Z_R=[zr.real, zr.imag], Z_transfer=[zt.real, zt.imag],
                        angle_Z_S_deg=float(np.degrees(np.angle(zs))), angle_Z_R_deg=float(np.degrees(np.angle(zr))),
                        tilt_two_source_deg=float(np.degrees(np.angle(D2))), D_two_source=float(abs(D2)),
                        tilt_network_deg=float(np.degrees(np.angle(i_relay))), D_network=float(abs(i_relay)))
    return out


def prefault_load_impedance(net, relay_bus, relay_line):
    """|V1 / I1| at the relay from the study's load flow (no fault)."""
    main, lines, grids, loads = net
    nodes, ix, Y, I = ybus(main, lines, grids, loads, 1)
    v = np.linalg.solve(Y, I)
    u, w, zl1, _ = lines[relay_line]
    far = w if u == relay_bus else u
    i = (v[ix[relay_bus]] - v[ix[far]]) / zl1
    return complex(v[ix[relay_bus]] / i)


def quad_settings(R, name, rf_max=40.0, r_frac=0.7, margin=0.9):
    """Quadrilateral from the setting study: resistive reach r_frac * |Z_load| (load flow), left blinder
    -0.25 of it, reactance reach 0.85 X_line reduced to margin * the smallest reactance of any external
    study fault (R_f <= rf_max) whose loop impedance falls between the blinders. Directional supervision
    handles reverse faults; the external set is forward faults beyond the remote bus."""
    cfg = R["cfg"]
    net = build(R["graph"])
    rb = RELAY_BUS[name]
    zload = prefault_load_impedance(net, rb, cfg["line"])
    r_right = r_frac * abs(zload)
    xl = R["z1L"].imag
    ext = [("bus", cfg["remote_bus"], 0.0)]
    for ln in cfg["beyond"]:
        u, v, _, _ = net[1][ln]
        for frac in (0.0, 0.01, 0.1, 0.2):
            ext.append(("line", ln, frac if u == cfg["remote_bus"] else 1 - frac))
    xmin, worst = np.inf, None
    for kind, tgt, m in ext:
        for ft in ("lg", "ll", "llg", "3ph"):
            for rf in np.linspace(0, rf_max, 9):
                vpo, ipo, vpr, ipr = solve_fault(net, rb, cfg["line"], (kind, tgt), ft, rf, m)
                z = apparent_x(R, vpo, ipo, vpr, ipr, LOOP[ft])
                if -0.25 * r_right < z.real < r_right and z.imag < xmin:
                    xmin, worst = z.imag, (kind, tgt, round(float(m), 2), ft, float(rf), float(z.real), float(z.imag))
    x_set = min(0.85 * xl, margin * xmin)
    return dict(z_load=[zload.real, zload.imag], z_load_abs=abs(zload), r_right=float(r_right),
                x_set=float(x_set), x_set_fraction_of_line=float(x_set / xl), min_external_x=float(xmin),
                worst_external=worst, rf_max=rf_max)


def study_direction(R, name, net=None):
    """Ground-truth direction for every short-circuit simulation, from the study model only: draw 1 A at the
    fault point in the positive-sequence network and take the direction of the resulting current in the
    protected line at the relay (forward = into the line). Faults on the protected line and at its remote
    bus are forward by construction; for meshed paths the modelled current decides. NaN for non-faults."""
    net = net or build(R["graph"])
    cfg = R["cfg"]; rb = RELAY_BUS[name]
    main, lines, grids, loads = net
    u0, v0, zl1, _ = lines[cfg["line"]]
    far = v0 if u0 == rb else u0
    label = np.full(len(R["tgt"]), np.nan)
    cache = {}
    shc = np.char.find(R["et"].astype(str), "shc") >= 0
    for i in np.where(shc)[0]:
        tgt, loc = R["tgt"][i], R["loc"][i]
        key = (tgt, None if tgt.startswith("MainBus") else float(loc))
        if key not in cache:
            if tgt.startswith("MainBus"):
                nodes, ix, Y, _ = ybus(main, lines, grids, loads, 1)
                f = ix[tgt]; fl = None
            else:
                m = float(np.clip(loc / 100.0, 1e-4, 1 - 1e-4))
                nodes, ix, Y, _ = ybus(main, lines, grids, loads, 1, tgt, m)
                f = ix["F"]; fl = tgt
            dv = -np.linalg.inv(Y)[:, f]
            if fl == cfg["line"]:
                zseg = (m if u0 == rb else 1 - m) * zl1
                i_rel = (dv[ix[rb]] - dv[ix["F"]]) / zseg
            else:
                i_rel = (dv[ix[rb]] - dv[ix[far]]) / zl1
            cache[key] = 1.0 if np.real(i_rel) > 0 else 0.0
        label[i] = cache[key]
    return label


def apparent_x(R, vpost, ipost, vpre, ipre, loop):
    Lp = cm.loops(R, vpost[None], ipost[None], vpre[None], ipre[None])
    j = cm.LOOPS.index(loop)
    return complex(Lp["V"][0, j] / Lp["I"][0, j])


RELAY_BUS = dict(doubleline="MainBus1", testgrid_A="MainBus1", testgrid_B="MainBus2")
LOOP = {"lg": "ag", "ll": "bc", "llg": "bc", "3ph": "bc"}
ETYPE = {"flt_1phg_shc": "lg", "flt_1phg_shc_w_arc": "lg", "flt_2ph_shc": "ll", "flt_2phg_shc": "llg", "flt_3ph_shc": "3ph"}


def study(name):
    R = cm.load_relay(name)
    cfg = R["cfg"]
    net = build(R["graph"])
    rb = RELAY_BUS[name]
    xl = R["z1L"].imag
    # external study set: remote bus + first 20 % of each line leaving it (oriented from the remote bus)
    ext = [("bus", cfg["remote_bus"], 0.0)]
    for ln in cfg["beyond"]:
        u, v, _, _ = net[1][ln]
        for frac in (0.0, 0.01, 0.1, 0.2):
            ext.append(("line", ln, frac if u == cfg["remote_bus"] else 1 - frac))
    res = {}
    for rfmax in (10.0, 20.0, 40.0):
        xmin = np.inf; worst = None
        for kind, tgt, m in ext:
            for ft in ("lg", "ll", "llg", "3ph"):
                for rf in np.linspace(0, rfmax, 9):
                    vpo, ipo, vpr, ipr = solve_fault(net, rb, cfg["line"], (kind, tgt), ft, rf, m)
                    z = apparent_x(R, vpo, ipo, vpr, ipr, LOOP[ft])
                    if 0 < z.imag < xmin:
                        xmin, worst = z.imag, (kind, tgt, round(m, 2), ft, float(rf), z.real)
        reach = min(0.85 * xl, 0.9 * xmin)
        res[f"{rfmax:g}"] = dict(min_external_x_ohm=float(xmin), worst_case=worst, reach_ohm=float(reach),
                                 reach_fraction_of_line=float(reach / xl))
    # validation against EMT: every in/out-of-zone case, loop of the labelled fault type, 50 ms phasors
    idx = np.where(R["pos"] | R["neg"])[0]
    vpre, vpost, ipre, ipost = cm.phasors_at(R, idx, 50)
    Lp = cm.loops(R, vpost, ipost, vpre, ipre)
    errs = []
    rot = {"a": 0, "b": 1, "c": 2, "bc": 0, "ca": 1, "ab": 2, "abc": 0}
    for n, i in enumerate(idx):
        ft = ETYPE[R["et"][i]]
        ph = R["phase"][i]
        # rotate the model's a-g / b-c fault to the labelled phase(s)
        if ft == "lg":
            loop = ["ag", "bg", "cg"][rot[ph]]
        elif ft in ("ll", "llg"):
            loop = {"bc": "bc", "ca": "ca", "ab": "ab"}[ph]
        else:
            loop = "bc"
        if R["tgt"][i] == cfg["remote_bus"]:
            where, m = ("bus", cfg["remote_bus"]), 0.0
        else:
            u, v, _, _ = net[1][R["tgt"][i]]
            where, m = ("line", R["tgt"][i]), R["loc"][i] / 100.0
        vpo, ipo, vpr, ipr = solve_fault(net, RELAY_BUS[name], cfg["line"], where, ft, R["rf"][i], m)
        zm = apparent_x(R, vpo, ipo, vpr, ipr, LOOP[ft])
        ze = Lp["V"][n, cm.LOOPS.index(loop)] / Lp["I"][n, cm.LOOPS.index(loop)]
        errs.append((R["rf"][i], R["pos"][i], zm.imag, ze.imag, zm.real, ze.real))
    E = np.array(errs, dtype=float)
    rel = np.abs(E[:, 2] - E[:, 3]) / xl
    res["validation"] = dict(n=len(E), median_abs_x_error_fraction_of_line=float(np.median(rel)),
                             p90_abs_x_error_fraction_of_line=float(np.percentile(rel, 90)),
                             by_rf={f"{r:g}": float(np.median(rel[E[:, 0] == r])) for r in (1, 10, 40)})
    return R, res


if __name__ == "__main__":
    out = {}
    for name in ("testgrid_A", "testgrid_B", "doubleline"):
        R, res = study(name)
        out[name] = res
        print(name, json.dumps(res, indent=1, default=str), flush=True)
        # evaluate the study reach on EMT data at 20/30/50 ms with the repo rule and rule+mimic
        idx = np.where(R["pos"] | R["neg"] | R["own99"])[0]
        pos, neg, o99 = R["pos"][idx], R["neg"][idx], R["own99"][idx]
        ev = {}
        for t in (20, 30, 50):
            for lab, mim in (("rule", False), ("rule+mimic", True)):
                x = cm.elements(R, idx, t, "full", mim)["rule_x"]
                for rfm in ("10", "20", "40"):
                    trip = x < res[rfm]["reach_ohm"]
                    ev[f"{t}ms {lab} study Rf<={rfm}"] = dict(dependability=float(trip[pos].mean()),
                                                              false_trip=float(trip[neg].mean()), own99=float(trip[o99].mean()))
                    print(f"  {name} {t} ms {lab:10s} reach(Rf<={rfm}) {res[rfm]['reach_fraction_of_line']:.2f} of line: "
                          f"dep {trip[pos].mean()*100:5.1f}  FT {trip[neg].mean()*100:5.1f}  99% {trip[o99].mean()*100:5.1f}")
        out[name]["emt_evaluation"] = ev
    json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "setting_study.json"), "w"), indent=1, default=str)
