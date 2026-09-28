"""Setting-study network with inverter-based resources, for grids where inverters are not negligible.

setting_study.py leaves inverters out, which is right on TestGrid110kV (0.14 % of short-circuit capacity) and
wrong on the CIGRE MV grid, where each of the two 15 MVA inverters produces about 12 MW against 9-21 MW of load
and supplies much of the fault current (results/CIGREMV_FACTS.md; results/cigremv/study_validation.json).
This module adds them without changing setting_study.py, so TestGrid results cannot move.

INVERTER MODEL (grid-following, current-limited; IEC 60909-0:2016 treats full-converter units as current
sources, and the EvEMTBench controller is described as positive- and negative-sequence reactive-current
fault ride-through behind a phase-current limiter that gives reactive current priority over active current)
  pre-fault   constant P, Q at the inverter terminal (the dispatch)
  fault       positive sequence: the pre-fault active current, plus reactive current
                  i_q = i_q,pre + k1 * max(0, dip - deadband),   dip = 1 - |V1_terminal| (pu)
              negative sequence: I2 = -y2 * V2_terminal (pu), an inductive admittance
              limiter: the largest phase current is held at i_max by first reducing the active current, then
              scaling the positive- and negative-sequence reactive currents together
  zero seq.   none (the interconnection reactor has R0/R1 = X0/X1 = 1e9)
  terminal    behind the interconnection reactor (graph edge Ind*-*IBR), V_terminal = V_bus + Z_reactor I_out
The parameters are not guessed: characterise() reads them off the inverters' own cubicles (dispatch; k1 fitted
with the nameplate deadband; y2; the current limit) and writes results/cigremv/ibr_characterisation.json.
No relay outcome is used, only each inverter's own voltage and current.

SOLUTION  The inverter currents depend on the voltages they cause, so the network is solved by damped fixed
point: sequence networks from setting_study.ybus with the inverters as current injections; the fault by the
Thevenin equivalents at the fault point with every sequence's open-circuit voltage (the inverters inject
negative-sequence current, so V2_oc is not zero); node voltages by superposition; repeat until the inverter
currents change by less than 1e-6 pu. solve_fault returns the relay's sequence phasors exactly like
setting_study.solve_fault (rms, phase-a reference, LL / LLG on phases b-c).

    python src/review/ibr_study.py characterise       -> results/cigremv/ibr_characterisation.json
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import setting_study as ss

A = np.exp(2j * np.pi / 3)
CHAR = os.path.join(cm.ROOT, "results", "cigremv", "ibr_characterisation.json")
DEADBAND = 0.05                       # EvEMTBench controller Deadband_upper_IqV / lower_IqV = +-0.05 pu
TOL, MAX_IT, DAMP = 1e-6, 400, 0.5


# ------------------------------------------------------------------ inverter description
def inverters_from_graph(graph, ub, char):
    """One dict per inverter: bus, ratings, reactor and the characterised control parameters."""
    out = []
    for n, a in graph.nodes(data=True):
        ctl = next((v for k, v in a.items() if k.endswith("cntrlFMUIBRController_param_dict")), None)
        if ctl is None:
            continue
        edge = [(u, v, k, d) for u, v, k, d in graph.edges(keys=True, data=True) if n in (u, v) and str(k).startswith("Ind")]
        u, v, k, d = edge[0]
        bus = v if u == n else u
        rp = d[f"{k}_param_dict"]
        c = char[str(n)]
        out.append(dict(node=str(n), bus=str(bus), sn=float(ctl["Sn"]), imax=float(c["i_max_pu"]),
                        z_reactor=complex(rp["rrea"], rp["xrea"]), p=float(c["p_out_W"]), q=float(c["q_out_var"]),
                        k1=float(c["k1"]), y2=complex(*c["y2_pu"]), deadband=DEADBAND,
                        i_base=float(ctl["Sn"]) / (np.sqrt(3) * ub), v_base=ub / np.sqrt(3)))
    return out


# ------------------------------------------------------------------ network
def with_operating_point(net, ub, loads_mw_mvar=None, usetp=1.0):
    """setting_study net with the simulation's own loads (bus -> (P MW, Q MVAr)) and grid voltage set point."""
    main, lines, grids, loads = net
    if loads_mw_mvar is not None:
        loads = {b: np.conj(complex(p, q) * 1e6) / ub**2 for b, (p, q) in loads_mw_mvar.items()}
    grids = [(g[0], g[1], g[2], (g[3] if len(g) > 3 else ss.UB / np.sqrt(3)) * usetp) for g in grids]
    return main, lines, grids, loads


def _limit(ip, iq, i2, imax):
    """Phase-current limiter: reduce active current first, then scale the reactive currents (I1 reactive and
    I2) together, until the largest phase current is <= imax. Currents in pu, I1 = ip - j iq in the V1 frame
    (i2 already in absolute phase)."""
    def peak(ip_, s):
        i1 = complex(ip_, -iq * s)
        return max(abs(i1 + s * i2), abs(A**2 * i1 + A * s * i2), abs(A * i1 + A**2 * s * i2))
    if peak(ip, 1.0) <= imax:
        return ip, 1.0
    if peak(0.0, 1.0) <= imax:                        # enough to trim active current
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if peak(ip * mid, 1.0) <= imax else (lo, mid)
        return ip * lo, 1.0
    lo, hi = 0.0, 1.0                                 # no active current left: scale reactive currents
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if peak(0.0, mid) <= imax else (lo, mid)
    return 0.0, lo


def _ibr_currents(ibrs, V1, V2, J1, pre=None):
    """Current each inverter injects into its bus (A rms, positive and negative sequence) given bus voltages.
    pre=None: pre-fault (constant P, Q). Otherwise pre = list of (ip0, iq0) from the pre-fault solution."""
    out1, out2 = np.zeros(len(ibrs), complex), np.zeros(len(ibrs), complex)
    for k, g in enumerate(ibrs):
        vt1 = V1[k] + g["z_reactor"] * J1[k]           # terminal voltage (reactor drop from the last iterate)
        if pre is None:
            out1[k] = np.conj((g["p"] + 1j * g["q"]) / (3 * vt1))
            continue
        vt2 = V2[k] + g["z_reactor"] * 0              # negative-sequence reactor drop neglected (second order)
        u1 = abs(vt1) / g["v_base"]
        ref = vt1 / abs(vt1)
        ip0, iq0 = pre[k]
        iq = iq0 + g["k1"] * max(0.0, (1 - u1) - g["deadband"])
        i2 = -g["y2"] * (vt2 / g["v_base"])          # pu, absolute phase
        i2_ref = i2 / ref                             # in the V1 frame, for the limiter
        ip, s = _limit(ip0, iq, i2_ref, g["imax"])
        out1[k] = complex(ip, -iq * s) * ref * g["i_base"]
        out2[k] = s * i2 * g["i_base"]
    return out1, out2


def prefault(net, ibrs):
    """Load flow with inverters as constant-P,Q injections. Returns (nodes, ix, V1 at every node, J1, (ip0, iq0))."""
    main, lines, grids, loads = net
    nodes, ix, Y, I = ss.ybus(main, lines, grids, loads, 1)
    Zb = np.linalg.inv(Y)
    bi = [ix[g["bus"]] for g in ibrs]
    J1 = np.zeros(len(ibrs), complex)
    for _ in range(MAX_IT):
        inj = I.copy()
        inj[bi] += J1
        V = Zb @ inj
        new, _ = _ibr_currents(ibrs, V[bi], np.zeros(len(ibrs)), J1)
        if np.max(np.abs(new - J1), initial=0) < TOL * 1e3:
            J1 = new
            break
        J1 = DAMP * new + (1 - DAMP) * J1
    inj = I.copy(); inj[bi] += J1
    V = Zb @ inj
    pre = []
    for k, g in enumerate(ibrs):
        vt1 = V[bi[k]] + g["z_reactor"] * J1[k]
        i = J1[k] / g["i_base"] / (vt1 / abs(vt1))
        pre.append((i.real, -i.imag))
    return nodes, ix, V, J1, pre


def _fault_currents(ftype, voc, z, rf):
    v1, v2, v0 = voc
    z1, z2, z0 = z
    if ftype == "lg":
        i = (v1 + v2 + v0) / (z1 + z2 + z0 + 3 * rf)
        return {1: i, 2: i, 0: i}
    if ftype == "ll":
        i1 = (v1 - v2) / (z1 + z2 + rf)
        return {1: i1, 2: -i1, 0: 0.0}
    if ftype == "llg":
        za, zb, zc = z1 + rf, z2 + rf, z0 + rf
        vf = (v1 / za + v2 / zb + v0 / zc) / (1 / za + 1 / zb + 1 / zc)
        return {1: (v1 - vf) / za, 2: (v2 - vf) / zb, 0: (v0 - vf) / zc}
    if ftype == "3ph":
        return {1: v1 / (z1 + rf), 2: v2 / (z2 + rf), 0: 0.0}
    raise ValueError(ftype)


def solve_fault(net, ibrs, relay_bus, relay_line, where, ftype, rf, m=0.0, return_ibr=False):
    """setting_study.solve_fault with inverters. With ibrs == [] it is the same computation."""
    main, lines, grids, loads = net
    fl = where[1] if where[0] == "line" else None
    m = float(np.clip(m, 1e-4, 1 - 1e-4))
    nodes_p, ix_p, Vp_nodes, J1p, pre = prefault(net, ibrs)
    Z, src = {}, {}
    for seq in (1, 2, 0):
        nodes, ix, Y, I = ss.ybus(main, lines, grids, loads, seq, fl, m)
        Z[seq] = (nodes, ix, np.linalg.inv(Y))
        src[seq] = I if seq == 1 else np.zeros(len(nodes), complex)
    nodes, ix, _ = Z[1]
    f = ix["F"] if fl else ix[where[1]]
    bi = [ix[g["bus"]] for g in ibrs]
    J1, J2 = J1p.copy(), np.zeros(len(ibrs), complex)
    for it in range(MAX_IT):
        V = {}
        voc = []
        for seq in (1, 2, 0):
            inj = src[seq].copy()
            if seq == 1:
                inj[bi] += J1
            elif seq == 2:
                inj[bi] += J2
            V[seq] = Z[seq][2] @ inj
            voc.append(V[seq][f])
        If = _fault_currents(ftype, voc, (Z[1][2][f, f], Z[2][2][f, f], Z[0][2][f, f]), rf)
        for seq in (1, 2, 0):
            V[seq] = V[seq] - Z[seq][2][:, f] * If[seq]
        if not ibrs:
            break
        n1, n2 = _ibr_currents(ibrs, V[1][bi], V[2][bi], J1, pre)
        d = max(np.max(np.abs(n1 - J1)), np.max(np.abs(n2 - J2)))
        J1, J2 = DAMP * n1 + (1 - DAMP) * J1, DAMP * n2 + (1 - DAMP) * J2
        if d < TOL * min(g["i_base"] for g in ibrs):
            break
    u, v, zl1, zl0 = lines[relay_line]
    far = v if u == relay_bus else u
    Vs, Is, Vpr, Ipr = {}, {}, {}, {}
    for seq in (1, 2, 0):
        nodes_s, ix_s, _ = Z[seq]
        zl = zl1 if seq in (1, 2) else zl0
        if fl == relay_line:
            zseg = (m if u == relay_bus else 1 - m) * zl
            other = ix_s["F"]
        else:
            zseg, other = zl, ix_s[far]
        Vs[seq] = V[seq][ix_s[relay_bus]]
        Is[seq] = (V[seq][ix_s[relay_bus]] - V[seq][other]) / zseg
    for seq in (1, 2, 0):                                          # pre-fault, from the load flow
        if seq == 1:
            Vpr[1] = Vp_nodes[ix_p[relay_bus]]
            Ipr[1] = (Vp_nodes[ix_p[relay_bus]] - Vp_nodes[ix_p[far]]) / zl1
        else:
            Vpr[seq] = 0.0; Ipr[seq] = 0.0
    seqv = lambda dct: np.array([dct[0], dct[1], dct[2]])
    res = (seqv(Vs), seqv(Is), seqv(Vpr), seqv(Ipr))
    return res + ((dict(iterations=it + 1, J1=J1, J2=J2),) if return_ibr else ())


# ------------------------------------------------------------------ characterisation from the inverters' own records
def characterise(decision_ms=50):
    """Dispatch, positive-sequence reactive gain (nameplate deadband), negative-sequence admittance and current
    limit of every inverter, from its own cubicle over every short circuit. Currents are read into the
    inverter branch in the recording and reported here as injected into the grid."""
    from evemt import load_cache
    import glob
    path = [h for d in cm.CACHE_DIRS for h in sorted(glob.glob(os.path.join(d, "adapt_grid-CigreMVGrid*_cache.meta.npz")))][0]
    C = load_cache(path); L = C["labels"]; G = C["graph"]; cubs = list(C["cubicles"]); x = C["x"]
    ev = np.rint((L["events/event_start"].to_numpy(float) - cm.T0_S) * C["fs"]).astype(int)
    et = L["events/event_type"].astype(str).to_numpy()
    shc = np.where(np.char.find(et.astype(str), "shc") >= 0)[0]
    end_f = cm.ADAPT_HALF + int(round(decision_ms * cm.FS / 1000))
    dft = lambda X, end: (2.0 / cm.SPC) * (X[..., end - cm.SPC:end].astype(float) @ np.exp(-2j * np.pi * np.arange(end - cm.SPC, end) / cm.SPC))
    res = dict(script="ibr_study.characterise", commit=cm.git_commit(), decision_ms=decision_ms,
               convention="currents injected into the grid; per unit of the inverter's own rating", inverters={})
    for n, a in G.nodes(data=True):
        ctl = next((v for k, v in a.items() if k.endswith("cntrlFMUIBRController_param_dict")), None)
        if ctl is None:
            continue
        busnum = str(n).replace("Bus", "").replace("IBR", "")
        cub = [c for c in cubs if "IBR" in c and f"MainBus{busnum}_" in c][0]
        k = cubs.index(cub)
        X = np.stack([x[r, k, :, ev[r] - cm.ADAPT_HALF:ev[r] + cm.ADAPT_HALF] for r in shc])
        ib, vb = float(ctl["I_base"]), float(ctl["V_base"])          # peak phase quantities of the rating
        Vp = dft(X[:, :3], cm.ADAPT_HALF - cm.SPC) @ cm.BM.T
        Ip = -(dft(X[:, 3:], cm.ADAPT_HALF - cm.SPC) @ cm.BM.T)       # injected into the grid
        S = 1.5 * Vp[:, 1] * np.conj(Ip[:, 1])
        Vf = dft(X[:, :3], end_f) @ cm.BM.T
        If = -(dft(X[:, 3:], end_f) @ cm.BM.T)
        u1, u2 = np.abs(Vf[:, 1]) / vb, np.abs(Vf[:, 2]) / vb
        ref = Vf[:, 1] / np.abs(Vf[:, 1]); refp = Vp[:, 1] / np.abs(Vp[:, 1])
        i1 = If[:, 1] / ref / ib; i1p = Ip[:, 1] / refp / ib
        iq, iq0 = -i1.imag, -i1p.imag
        iph = np.abs(-(dft(X[:, 3:], end_f))).max(1) / ib
        free = iph < 0.95 * 1.2                                     # not on the limiter
        dip = 1 - u1
        sel = free & (dip > DEADBAND + 0.02) & (dip < 0.6)
        k1 = float(np.sum((iq - iq0)[sel] * (dip - DEADBAND)[sel]) / np.sum((dip - DEADBAND)[sel] ** 2))
        s2 = free & (u2 > 0.05)
        ratio = -(If[s2, 2] / ib) / (Vf[s2, 2] / vb)               # I2 = -y2 V2
        y2c = complex(float(np.median(ratio.real)), float(np.median(ratio.imag)))
        deep = u1 < 0.5
        res["inverters"][str(n)] = dict(cubicle=cub, n_short_circuits=int(len(shc)),
                                        p_out_W=float(np.median(S.real)), q_out_var=float(np.median(S.imag)),
                                        p_out_range_W=[float(S.real.min()), float(S.real.max())],
                                        k1=k1, k1_n=int(sel.sum()), k1_nameplate_Kp_IqV=float(ctl.get("Kp_IqV", np.nan)),
                                        y2_pu=[y2c.real, y2c.imag], y2_abs=float(abs(y2c)), y2_angle_deg=float(np.degrees(np.angle(y2c))),
                                        y2_n=int(s2.sum()),
                                        i_max_pu=float(ctl.get("Imax", 1.2)),
                                        max_phase_current_deep_dips_pu=dict(n=int(deep.sum()), median=float(np.median(iph[deep])) if deep.any() else None,
                                                                            p99=float(np.percentile(iph[deep], 99)) if deep.any() else None))
    os.makedirs(os.path.dirname(CHAR), exist_ok=True)
    json.dump(res, open(CHAR, "w"), indent=1)
    return res


def load_characterisation():
    return json.load(open(CHAR, encoding="utf-8"))["inverters"]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "characterise":
        r = characterise()
        for n, v in r["inverters"].items():
            print(n, {k: v[k] for k in ("p_out_W", "q_out_var", "k1", "k1_n", "y2_abs", "y2_angle_deg", "y2_n", "i_max_pu",
                                        "max_phase_current_deep_dips_pu")})
        print("saved", CHAR)
