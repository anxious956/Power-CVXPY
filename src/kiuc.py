"""
The NREL / KIUC two-bus 57.1 kV system (NREL/TP-5D00-94430, Fig. 41, Table 14) with our inverter: docs/KIUC.md.

Per unit on 15 MVA / 57.1 kV (the IBR's rating). The PSCAD builder runs every network in per unit of its own base
(10 MVA / 20 kV); the per-unit circuit is the same, so the EMT runs reproduce this one in per unit, and every
quantity here is in per unit of the 15 MVA base.

  preflight  load flow at both operating points, hydro off / on; the Fig.-16 sanity (bolted AG at 5 % from the IBR
             end, IEEE 2800 mode, K2 = 5): the IBR's I_P+, I_Q+ (FRT off / on), |I2| / |V2| and the angle of I2
             against V2
  static     Q1: at R2 (Bus-2, IBR end, looking into Line-2), the forward set, modes suppressed / IEEE 2800 (K2 = 5),
             FRT off / on, hydro off / on, TF2 DYg (and YgD, static only), the 16 corners of the source box: the
             report's negative-sequence directional elements (32Q for B-C, 32QG for A-G, with their supervision),
             our incremental element, 3|I2| / |I1| and the angle of the IBR's I2 against V2

    python src/kiuc.py preflight   -> results/network/kiuc_preflight.json
    python src/kiuc.py static      -> results/network/kiuc_static.json
"""
import os, sys, json, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
from i2dir_static import direction_pk

OUT = os.path.join(HERE, "..", "results", "network")
SB, VLL = 15.0, 57.1                                   # MVA, kV
ZB = VLL ** 2 / SB                                     # 217.4 ohm
Z_EQ1, Z_EQ0 = complex(5.91, 12.53) / ZB, complex(5.65, 18.93) / ZB          # grid to POI (Table 14)
Z_L1, Z_L0 = complex(1.0433, 3.218) / ZB, complex(1.5649, 4.827) / ZB        # Line-2, Bus-1 to Bus-2
ZS_STIFF = 0.001j                                      # the stiff grid source
X_HYDRO = (0.25 + 0.07) * SB / 7.5                     # assumed X'd + X_TF1 on 7.5 MVA, on 15 MVA: 0.64 pu
X_TF2 = 0.06                                           # assumed, on 15 MVA
K2_IEEE, K_FRT = 5.0, 2.0                              # the report's K for I2; IEEE 2800's K for I_Q+ (range 2-6)
OPS = {"P0.25Q0.15": (0.25, 0.15), "P1.0Q0": (1.0, 0.0)}
OHM = lambda r: r / ZB
M_IBR = (0.05, 0.50, 0.80)                             # from the IBR end (Bus-2)
RF_OHM = (0.01, 5.0)
# the forward set at R2: Line-2 runs Bus-1 (a) -> Bus-2 (b), so m from Bus-2 is 1 - m from a
FWD = [("L2", round(1 - m, 4), s, OHM(r)) for s in ("ag", "ab") for m in M_IBR for r in RF_OHM]
REV_R1 = [("EQ", round(m, 4), s, OHM(r)) for s in ("ag", "ab") for m in M_IBR for r in RF_OHM]   # EQ: G (a) -> Bus-1 (b)
MODES = {"suppressed": 1e6, "IEEE 2800 K2=5": 1.0 / (-1j * K2_IEEE)}             # shunt: I2 = j K2 V2 injected


def network(hydro=False, tf2="DYg", neg_z=1e6, relay=("L2", "b"), op="P0.25Q0.15", inject=False):
    """The KIUC system in per unit of 15 MVA. hydro off: a stiff source at G behind the equivalent line EQ (Z_eq) to
    Bus-1. hydro on: one Thevenin source at Bus-1, the grid behind Z_eq in parallel with the hydro behind X_HYDRO
    (no zero-sequence path through the hydro's delta), as the design tool takes one synchronous source.
    tf2: "DYg" (delta facing the line: no zero-sequence path at Bus-2) or "YgD" (X_TF2 to ground in zero sequence)."""
    p, q = OPS[op]
    i0 = complex(p, -q)                                # the command in the inverter's frame; about absolute at |V| ~ 1
    zero_z = 1j * X_TF2 if tf2 == "YgD" else 1e6
    ibrs = {"I": nw.IBR("B2", i0, (0.1, 0.3), neg_z, zero_z, inject=inject, i_max=1.2)}
    lines = {"L2": nw.Line("B1", "B2", Z_L1, Z_L0)}
    if not hydro:
        sgs = {"G": nw.SG("G", {1: ZS_STIFF, 2: ZS_STIFF, 0: ZS_STIFF}, 1.0 + 0j)}
        lines = {"EQ": nw.Line("G", "B1", Z_EQ1, Z_EQ0), **lines}
    else:
        zg, zh = ZS_STIFF + Z_EQ1, 1j * X_HYDRO
        z1 = zg * zh / (zg + zh)
        e = (1.0 / zg + 1.0 / zh) * z1                 # both EMFs 1.0 at 0 deg (assumed)
        sgs = {"G": nw.SG("B1", {1: z1, 2: z1, 0: ZS_STIFF + Z_EQ0}, e)}
    return nw.Network(lines=lines, sgs=sgs, ibrs=ibrs, loads={}, relay=relay, eps=0.08, rF=1.0)


def settings(net, sg_val, i_abs, frt=0.0):
    """The inverter's command in its own V1 frame for an absolute current realisation, at the no-fault state."""
    _, V = nw.solve(net, {"G": sg_val, "I": i_abs}, full=True)
    u = V["B2"][0] / abs(V["B2"][0])
    c = i_abs / u
    return {"I": dict(ID=float(c.real), IQ=float(-c.imag), D2MAG=0.0, D2ANG=0.0, FRT=float(frt))}


def solve(net, sg_val, st, fault):
    try:
        return nw.solve_v1ref(net, {"G": sg_val}, st, fault, relax=0.5, max_iter=2000)
    except RuntimeError:
        return nw.solve_v1ref(net, {"G": sg_val}, st, fault, relax=0.2, max_iter=8000)


def ibr_state(net, sg_val, st, fault):
    """The IBR's delivered I1 in its own frame (I_P+, I_Q+), its I2 and the Bus-2 V1, V2."""
    y, inj, _ = solve(net, sg_val, st, fault)
    vals = {"G": sg_val, "I": inj["I"][0]}
    _, V = nw.solve(net, vals, {"I": inj["I"][1]}, fault, full=True)
    v1, v2 = V["B2"][0], V["B2"][1]
    u = v1 / abs(v1)
    i1 = inj["I"][0] / u
    i2 = inj["I"][1] - v2 / net.ibrs["I"].neg_z      # injected: the designed delta plus the IEEE 2800 law
    return dict(IP=float(i1.real), IQ=float(-i1.imag), I1=float(abs(inj["I"][0])), V1=float(abs(v1)), V2=float(abs(v2)),
                I2=float(abs(i2)), K_meas=float(abs(i2) / abs(v2)) if abs(v2) > 1e-9 else None,
                ang_I2_V2=float(np.degrees(np.angle(i2 / v2))) if abs(v2) > 1e-9 and abs(i2) > 1e-9 else None), y


# ------------------------------------------------------------------ the report's negative-sequence directional element
A2, K2_RATIO, Q_PICKUP = 0.10, 0.20, 0.10              # SEL defaults: |I2|/|I1| > a2; |I2|/|I0| > k2 (32QG); 3|I2| > 0.1 pu
Z2F_FRAC, Z2R_FRAC = 0.4, 0.6                          # Z2F = |Z2L| / 2 - eps, Z2R = |Z2L| / 2 + eps, eps = 0.1 |Z2L|


def dir32q(y, ground, z_line=Z_L1):
    """The report's 32Q (phase faults) / 32QG (ground faults, with the zero-sequence restraint k2): z2 =
    Re[V2 (I2 e^{j angle Z1L})*] / |I2|^2; forward if z2 < Z2F, reverse if z2 > Z2R. Returns (decision, z2, why)."""
    v2, i1, i2, i0 = y[1], y[3], y[4], y[5]
    if 3 * abs(i2) <= Q_PICKUP:
        return None, None, "3I2 below pickup"
    if abs(i2) <= A2 * abs(i1):
        return None, None, "a2: |I2| <= 0.1 |I1|"
    if ground and abs(i0) > 1e-9 and abs(i2) <= K2_RATIO * abs(i0):
        return None, None, "k2: |I2| <= 0.2 |I0|"
    z2 = (v2 * np.conj(i2 * np.exp(1j * np.angle(z_line)))).real / abs(i2) ** 2
    zl = abs(z_line)
    if z2 < Z2F_FRAC * zl:
        return "f", float(z2), "ok"
    if z2 > Z2R_FRAC * zl:
        return "r", float(z2), "ok"
    return None, float(z2), "between thresholds"


# ------------------------------------------------------------------ pre-flight
def preflight():
    out = {"loadflow": [], "fig16": []}
    ok_all = True
    for hydro in (False, True):
        for op in OPS:
            net = network(hydro, "DYg", 1e6, op=op)
            st = settings(net, 1.0 if not hydro else net.sgs["G"].e0, net.ibrs["I"].i0)
            sg = net.sgs["G"].e0
            _, inj, it = solve(net, sg, st, None)
            _, V = nw.solve(net, {"G": sg, "I": inj["I"][0]}, full=True)
            v = {b: float(abs(V[b][0])) for b in V}
            ok = all(0.95 <= x <= 1.05 for x in v.values())
            ok_all &= ok
            out["loadflow"].append(dict(hydro=hydro, op=op, iterations=it, bus_v1=v, ok=ok))
            print(f"load flow, hydro {'on ' if hydro else 'off'}, {op}: " + ", ".join(f"{b} {x:.4f}" for b, x in v.items())
                  + f"  ({it} it) {'OK' if ok else 'OUT of 0.95-1.05'}", flush=True)
    # Fig. 16: bolted AG at 5 % from the IBR end, IEEE 2800 sequence control, P 0.25 / Q 0.15, I_sat 1.2, K = 5
    fault = ("L2", 0.95, "ag", OHM(0.01))
    for tf2 in ("YgD", "DYg"):
        for frt in (0.0, K_FRT):
            net = network(False, tf2, MODES["IEEE 2800 K2=5"])
            st = settings(net, 1.0, net.ibrs["I"].i0, frt)
            s, _ = ibr_state(net, 1.0, st, fault)
            chk = dict(IQ_12=abs(s["IQ"] - 1.2) <= 0.12, IP_0=abs(s["IP"]) <= 0.12,
                       K_5=s["K_meas"] is not None and abs(s["K_meas"] - 5.0) <= 0.5,
                       ang_90=s["ang_I2_V2"] is not None and abs(s["ang_I2_V2"] - 90.0) <= 15.0)
            out["fig16"].append(dict(tf2=tf2, frt=frt, state=s, checks=chk))
            print(f"Fig. 16 sanity, TF2 {tf2}, FRT {frt:g}: I_P+ {s['IP']:.3f}, I_Q+ {s['IQ']:.3f} (|I1| {s['I1']:.3f}); "
                  f"|V1| {s['V1']:.3f}, |V2| {s['V2']:.3f}; |I2| {s['I2']:.3f} = {s['K_meas']:.2f} |V2|, I2 leads V2 by "
                  f"{s['ang_I2_V2']:.1f} deg | checks {chk}", flush=True)
    out["loadflow_ok"] = ok_all
    json.dump(out, open(os.path.join(OUT, "kiuc_preflight.json"), "w"), indent=1)
    print("-> results/network/kiuc_preflight.json")


# ------------------------------------------------------------------ Q1
def static():
    corners = list(itertools.product((-1, 1), repeat=4))
    out = {}
    for hydro in (False, True):
        for tf2 in ("DYg", "YgD"):
            for mode, nz in MODES.items():
                for frt in (0.0, K_FRT):
                    net = network(hydro, tf2, nz)
                    key = f"hydro {'on' if hydro else 'off'} | TF2 {tf2} | {mode} | FRT {frt:g}"
                    rows = []
                    for c in FWD:
                        ground = c[2] == "ag"
                        res = dict(case=list(c), q=[], inc=[], ratio=[], ang=[], why=[])
                        for u in corners:
                            v = nw.realisation(net, u)
                            st = settings(net, v["G"], v["I"], frt)
                            yN, _, _ = solve(net, v["G"], st, None)
                            s, y = ibr_state(net, v["G"], st, c)
                            dq, _, why = dir32q(y, ground)
                            res["q"].append(dq)
                            res["why"].append(why)
                            res["inc"].append(direction_pk(yN, y))
                            res["ratio"].append(float(3 * abs(y[4]) / max(abs(y[3]), 1e-12)))
                            res["ang"].append(s["ang_I2_V2"])
                        rows.append(res)
                    n = len(rows) * len(corners)
                    cnt = lambda key, val: sum(x == val for r in rows for x in r[key])
                    summ = dict(n=n, q_fwd=cnt("q", "f") / n, q_none=cnt("q", None) / n, q_rev=cnt("q", "r") / n,
                                inc_fwd=cnt("inc", "f") / n, inc_none=cnt("inc", None) / n, inc_rev=cnt("inc", "r") / n,
                                ratio_over_10pct=sum(x > 0.1 for r in rows for x in r["ratio"]) / n,
                                why={w: sum(x == w for r in rows for x in r["why"]) for w in {x for r in rows for x in r["why"]}},
                                by_type={t: dict(q_fwd=sum(x == "f" for r in rows if r["case"][2] == t for x in r["q"]) / (n / 2),
                                                 inc_fwd=sum(x == "f" for r in rows if r["case"][2] == t for x in r["inc"]) / (n / 2))
                                         for t in ("ag", "ab")})
                    out[key] = dict(summary=summ, rows=rows)
                    print(f"{key}: 32Q/32QG fwd {summ['q_fwd']:.2f} none {summ['q_none']:.2f} rev {summ['q_rev']:.2f} | incremental fwd "
                          f"{summ['inc_fwd']:.2f} none {summ['inc_none']:.2f} rev {summ['inc_rev']:.2f} | 3I2 > 10 % I1 on "
                          f"{summ['ratio_over_10pct']:.2f} | by type {summ['by_type']} | blocked by {summ['why']}", flush=True)
                    json.dump(dict(fwd=FWD, results=out), open(os.path.join(OUT, "kiuc_static.json"), "w"), indent=1, default=str)
    print("-> results/network/kiuc_static.json")


if __name__ == "__main__":
    {"preflight": preflight, "static": static}[sys.argv[1]]()
