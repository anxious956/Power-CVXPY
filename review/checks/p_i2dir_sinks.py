"""I2 direction (a''): the loads behind the relay as current sinks, share s, held fixed vs V1-referenced.

The source inverter I and the sink loads are modelled two ways:
  fixed   nw.solve, every inverter a fixed phasor current (as stage (a) and (a') run the source inverter)
  v1ref   nw.solve_v1ref, every inverter I = (ID - j IQ) V1/|V1| at its bus (the EMT controller, gfl_avm MODE2 = 0)
Each sink draws the pre-fault current of the share s of its load; the rest stays an impedance with y2 = y1.
Reported per s and mode: misdirected-or-undecided on the hard forward / reverse sets (the code's element: no current
pickup on dY1), the same with a 0.05 pu pickup on |dI1| and |dI2|, and the smallest |dI1| at the relay.

    python review/checks/p_i2dir_sinks.py      (repo root at 5e5a607)
"""
import sys, itertools
import numpy as np
sys.path.insert(0, "src")
import network as nw
import i2dir_static as st

PK = 0.05


def direction_pk(yN, y):
    dI2, dI1 = abs(y[4] - yN[4]), abs(y[3] - yN[3])
    for k_i, k_v, ok in ((4, 1, dI2 >= st.I2_I1_MIN * dI1 and dI2 >= PK), (3, 0, abs(y[0] - yN[0]) >= st.DV1_MIN and dI1 >= PK)):
        dI, dV = y[k_i] - yN[k_i], y[k_v] - yN[k_v]
        if ok:
            ang = np.degrees(np.angle(dI / dV)) % 360
            return "f" if st.PHI < ang < 180 + st.PHI else "r"
    return None


def build(base, s, VR, VS):
    loads, ibrs = {}, dict(base.ibrs)
    for b, V in (("R", VR), ("S", VS)):
        y1 = base.loads[b][1]
        loads[b] = {1: (1 - s) * y1, 2: (1 - s) * y1, 0: 0.0}
        if s > 0:
            ibrs["X" + b] = nw.IBR(b, -s * y1 * V, (0.0, 0.0), 1e6, 1e6, inject=False, i_max=10.0)
    return nw.Network(lines=base.lines, sgs=base.sgs, ibrs=ibrs, loads=loads, relay=base.relay, eps=base.eps, rF=base.rF)


base = st.network(1e6, 1.0)
corners = list(itertools.product((-1, 1), repeat=2 * len(base.sources)))
for s in (0.0, 0.5, 0.8, 1.0):
    for mode in ("fixed", "v1ref"):
        out = []
        for side, cases, want in (("fwd", st.FWD, "f"), ("rev", st.REV, "r")):
            bad, badpk, n, dmin = 0, 0, 0, 9.0
            for u in corners:
                v = nw.realisation(base, u)
                _, V = nw.solve(base, v, full=True)
                net = build(base, s, V["R"][0], V["S"][0])
                vals = dict(v)
                for kx in net.ibrs:
                    if kx.startswith("X"):
                        vals[kx] = net.ibrs[kx].i0
                if mode == "v1ref":
                    _, Vn = nw.solve(net, vals, full=True)
                    sets = {}
                    for kx, ib in net.ibrs.items():
                        uu = Vn[ib.bus][0] / abs(Vn[ib.bus][0])
                        c = vals[kx] / uu
                        sets[kx] = dict(ID=c.real, IQ=-c.imag)
                    sg = {g: vals[g] for g in net.sgs}
                    yN = nw.solve_v1ref(net, sg, sets)[0]
                for c in cases:
                    f = (c[0], c[1], c[2], c[3] * net.rF)
                    if mode == "fixed":
                        yN = nw.solve(net, vals)
                        y = nw.solve(net, vals, fault=f)
                    else:
                        y = nw.solve_v1ref(net, sg, sets, fault=f)[0]
                    n += 1
                    bad += st.direction(yN, y) != want
                    badpk += direction_pk(yN, y) != want
                    dmin = min(dmin, abs(y[3] - yN[3]))
            out.append(f"{side} {bad / n:.2f} / pk {badpk / n:.2f} (min |dI1| {dmin:.3f})")
        print(f"s {s:.1f} {mode:5s}: " + "; ".join(out), flush=True)
