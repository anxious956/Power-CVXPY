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
X_TF1 = 0.07                                           # assumed, on 7.5 MVA
X_HYDRO = {"X''d 0.20": (0.20 + X_TF1) * SB / 7.5,     # assumed X''d + X_TF1 on 7.5 MVA, on 15 MVA: 0.54 pu (primary)
           "X'd 0.25": (0.25 + X_TF1) * SB / 7.5}      # 0.64 pu (sensitivity)
X_TF2 = 0.06                                           # assumed, on 15 MVA
K2_IEEE, K_FRT = 5.0, 4.0                              # the report's K for I2; K1 for I_Q+ (4: reproduces Fig. 16; 2-6 IEEE 2800)
K_FRT_SENS = 2.0
A3 = np.exp(2j * np.pi / 3)
OPS = {"P0.25Q0.15": (0.25, 0.15), "P1.0Q0": (1.0, 0.0)}
OHM = lambda r: r / ZB
M_IBR = (0.05, 0.50, 0.80)                             # from the IBR end (Bus-2)
RF_OHM = (0.01, 5.0)
# the forward set at R2: Line-2 runs Bus-1 (a) -> Bus-2 (b), so m from Bus-2 is 1 - m from a
FWD = [("L2", round(1 - m, 4), s, OHM(r)) for s in ("ag", "ab") for m in M_IBR for r in RF_OHM]
REV_R1 = [("EQ", round(m, 4), s, OHM(r)) for s in ("ag", "ab") for m in M_IBR for r in RF_OHM]   # EQ: G (a) -> Bus-1 (b)
MODES = {"suppressed": 0.0, "IEEE 2800 K2=5": K2_IEEE}  # MODE2 1's K2 inside the controller, through the limiter
LIM = int(os.environ.get("KIUC_LIM", "2"))             # 2: the report's per-sequence limits; 1: ours (per phase, I2 first)


HYDRO_OPEN0 = 1e3                                      # the hydro behind TF1's delta: no zero-sequence path


def network(hydro="off", tf2="DYg", neg_z=1e6, relay=("L2", "b"), op="P0.25Q0.15", inject=False, xh="X''d 0.20"):
    """The KIUC system in per unit of 15 MVA. The grid: a stiff source at G behind the equivalent line EQ (Z_eq) to
    Bus-1. hydro "off": nothing else; "sg": a second synchronous source at Bus-1 behind X_HYDRO[xh] (Q1, Q2, as the
    report has it); "thevenin": one source at Bus-1, the grid behind Z_eq in parallel with the hydro (Q3: the design
    tool takes one synchronous source; no EQ line then). tf2: "DYg" (delta facing the line: no zero-sequence path at
    Bus-2) or "YgD" (X_TF2 to ground in zero sequence)."""
    p, q = OPS[op]
    i0 = complex(p, -q)                                # the command in the inverter's frame; about absolute at |V| ~ 1
    zero_z = 1j * X_TF2 if tf2 == "YgD" else 1e6
    ibrs = {"I": nw.IBR("B2", i0, (0.1, 0.3), neg_z, zero_z, inject=inject, i_max=1.2)}
    lines = {"L2": nw.Line("B1", "B2", Z_L1, Z_L0)}
    zh = 1j * X_HYDRO[xh]
    if hydro in ("off", "sg"):
        sgs = {"G": nw.SG("G", {1: ZS_STIFF, 2: ZS_STIFF, 0: ZS_STIFF}, 1.0 + 0j)}
        lines = {"EQ": nw.Line("G", "B1", Z_EQ1, Z_EQ0), **lines}
        if hydro == "sg":
            sgs["H"] = nw.SG("B1", {1: zh, 2: zh, 0: HYDRO_OPEN0 * 1j}, 1.0 + 0j, gen=(0.0, 0.0))
    else:
        zg = ZS_STIFF + Z_EQ1
        z1 = zg * zh / (zg + zh)
        e = (1.0 / zg + 1.0 / zh) * z1                 # both EMFs 1.0 at 0 deg (assumed)
        sgs = {"G": nw.SG("B1", {1: z1, 2: z1, 0: ZS_STIFF + Z_EQ0}, e)}
    return nw.Network(lines=lines, sgs=sgs, ibrs=ibrs, loads={}, relay=relay, eps=0.08, rF=1.0)


def sgvals(net, v):
    return {k: v[k] for k in net.sgs}


def nominal_sg(net):
    return {k: g.e0 for k, g in net.sgs.items()}


def settings(net, sg, i_abs, frt=0.0, k2=0.0):
    """The inverter's command in its own V1 frame for an absolute current realisation, at the no-fault state.
    sg: {source name: EMF}; k2 > 0: MODE2 1 (the IEEE 2800 law) with that K."""
    _, V = nw.solve(net, {**sg, "I": i_abs}, full=True)
    u = V["B2"][0] / abs(V["B2"][0])
    c = i_abs / u
    return {"I": dict(ID=float(c.real), IQ=float(-c.imag), D2MAG=0.0, D2ANG=0.0, FRT=float(frt), K2=float(k2))}


def solve(net, sg, st, fault, lim=None):
    lim = LIM if lim is None else lim
    try:
        return nw.solve_v1ref(net, sg, st, fault, lim=lim, relax=0.5, max_iter=2000)
    except RuntimeError:
        return nw.solve_v1ref(net, sg, st, fault, lim=lim, relax=0.2, max_iter=8000)


def ibr_state(net, sg, st, fault, lim=None):
    """The IBR's delivered I1 in its own frame (I_P+, I_Q+), its I2, its per-phase peak and the Bus-2 V1, V2."""
    y, inj, _ = solve(net, sg, st, fault, lim)
    vals = {**sg, "I": inj["I"][0]}
    _, V = nw.solve(net, vals, {"I": inj["I"][1]}, fault, full=True)
    v1, v2 = V["B2"][0], V["B2"][1]
    u = v1 / abs(v1)
    i1 = inj["I"][0] / u
    i2 = inj["I"][1] - v2 / net.ibrs["I"].neg_z      # injected: the designed delta plus the IEEE 2800 law
    peak = max(abs(inj["I"][0] * A3 ** (-k) + i2 * A3 ** k) for k in range(3))
    return dict(IP=float(i1.real), IQ=float(-i1.imag), I1=float(abs(inj["I"][0])), V1=float(abs(v1)), V2=float(abs(v2)),
                peak=float(peak),
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
def flow(net, sg, inj):
    """Active and reactive power into Line-2 at Bus-2 (positive: the IBR exports towards the grid)."""
    _, V = nw.solve(net, {**sg, "I": inj["I"][0]}, full=True)
    i = (V["B2"][0] - V["B1"][0]) / net.lines["L2"].z1
    s = V["B2"][0] * np.conj(i)
    return V, float(s.real), float(s.imag)


def preflight():
    out = {"loadflow": [], "thevenin_check": [], "fig16": []}
    ok_all = True
    for hydro in ("off", "sg"):
        for op in OPS:
            net = network(hydro, "DYg", op=op)
            sg = nominal_sg(net)
            st = settings(net, sg, net.ibrs["I"].i0)
            _, inj, it = solve(net, sg, st, None)
            V, p, q = flow(net, sg, inj)
            v = {b: float(abs(V[b][0])) for b in V}
            ok = all(0.95 <= x <= 1.05 for x in v.values())
            ok_all &= ok
            out["loadflow"].append(dict(hydro=hydro, op=op, iterations=it, bus_v1=v, P_into_line2_at_B2=p, Q_into_line2_at_B2=q, ok=ok))
            print(f"load flow, hydro {hydro:3s}, {op}: |V1| " + ", ".join(f"{b} {x:.4f}" for b, x in v.items())
                  + f"; P, Q from Bus-2 into Line-2 {p:+.3f}, {q:+.3f} pu ({'IBR -> grid' if p > 0 else 'grid -> IBR'})  ({it} it) "
                  + ("OK" if ok else "OUT of 0.95-1.05"), flush=True)
    # the Thevenin equivalent (Q3's) against the two-source network: pre-fault and the bolted AG at 5 % from Bus-2, at R2
    fault = ("L2", 0.95, "ag", OHM(0.01))
    for xh in X_HYDRO:
        a, b = network("sg", "DYg", xh=xh), network("thevenin", "DYg", xh=xh)
        sa, sb = nominal_sg(a), nominal_sg(b)
        st = settings(a, sa, a.ibrs["I"].i0)
        d = max(float(np.max(np.abs(solve(a, sa, st, f)[0] - solve(b, sb, st, f)[0]))) for f in (None, fault))
        out["thevenin_check"].append(dict(xh=xh, largest_difference_at_R2=d))
        print(f"two-source vs Thevenin hydro ({xh}): largest difference at R2, pre-fault and bolted AG at 5 %: {d:.1e} pu", flush=True)
    # Fig. 16: bolted AG at 5 % from the IBR end, IEEE 2800 sequence control, P 0.25 / Q 0.15, I_sat 1.2, K = 5
    for tf2 in ("YgD", "DYg"):
        for frt in (0.0, K_FRT, 4.0):
            net = network("off", tf2)
            sg = nominal_sg(net)
            st = settings(net, sg, net.ibrs["I"].i0, frt, K2_IEEE)
            s, _ = ibr_state(net, sg, st, fault)
            chk = dict(IQ_12=abs(s["IQ"] - 1.2) <= 0.12, IP_0=abs(s["IP"]) <= 0.12,
                       K_5=s["K_meas"] is not None and abs(s["K_meas"] - 5.0) <= 0.5,
                       ang_90=s["ang_I2_V2"] is not None and abs(s["ang_I2_V2"] - 90.0) <= 15.0)
            out["fig16"].append(dict(tf2=tf2, frt=frt, state=s, checks=chk))
            print(f"Fig. 16 sanity, TF2 {tf2}, FRT K1 {frt:g}: I_P+ {s['IP']:.3f}, I_Q+ {s['IQ']:.3f} (|I1| {s['I1']:.3f}); "
                  f"|V1| {s['V1']:.3f}, |V2| {s['V2']:.3f}; |I2| {s['I2']:.3f} = {s['K_meas']:.2f} |V2|, I2 leads V2 by "
                  f"{s['ang_I2_V2']:.1f} deg | checks {chk}", flush=True)
    out["loadflow_ok"] = ok_all
    json.dump(out, open(os.path.join(OUT, "kiuc_preflight.json"), "w"), indent=1)
    print("-> results/network/kiuc_preflight.json")


# ------------------------------------------------------------------ Q1
def corners_for(net):
    """The 16 corners of the grid source's and the IBR's boxes; the hydro (if any) at its nominal EMF."""
    out = []
    for g1, g2, i1, i2 in itertools.product((-1, 1), repeat=4):
        u = []
        for kind, name in net.sources:
            u += [g1, g2] if name == "G" else ([i1, i2] if name == "I" else [0.0, 0.0])
        out.append(np.array(u, float))
    return out


def run_set(net, cases, frt, want, k2=0.0, lim=None):
    """Per case and corner: the report's element (32Q / 32QG), our incremental element, 3|I2|/|I1| at the relay,
    the IBR's I2 against V2, its per-phase peak (flag > 1.5 pu under LIM 2), and |V1| at Bus-2 (weak below 0.2)."""
    rows = []
    for c in cases:
        ground = c[2] == "ag"
        res = dict(case=list(c), q=[], inc=[], ratio=[], ang=[], why=[], v1=[], peak=[])
        for u in corners_for(net):
            v = nw.realisation(net, u)
            sg = sgvals(net, v)
            st = settings(net, sg, v["I"], frt, k2)
            yN, _, _ = solve(net, sg, st, None, lim)
            s, y = ibr_state(net, sg, st, c, lim)
            res["peak"].append(s["peak"])
            dq, _, why = dir32q(y, ground)
            res["q"].append(dq)
            res["why"].append(why)
            res["inc"].append(direction_pk(yN, y))
            res["ratio"].append(float(3 * abs(y[4]) / max(abs(y[3]), 1e-12)))
            res["ang"].append(s["ang_I2_V2"])
            res["v1"].append(s["V1"])
        rows.append(res)
    n = len(rows) * 16
    cnt = lambda key, val: sum(x == val for r in rows for x in r[key])
    blocked = {}
    for r in rows:
        for x in r["why"]:
            blocked[x] = blocked.get(x, 0) + 1
    return rows, dict(n=n, want=want, q_right=cnt("q", want) / n, q_none=cnt("q", None) / n,
                      q_wrong=sum(x not in (want, None) for r in rows for x in r["q"]) / n,
                      inc_right=cnt("inc", want) / n, inc_none=cnt("inc", None) / n,
                      inc_wrong=sum(x not in (want, None) for r in rows for x in r["inc"]) / n,
                      ratio_over_10pct=sum(x > 0.1 for r in rows for x in r["ratio"]) / n, why=blocked,
                      weak_frame_points=sum(x < 0.2 for r in rows for x in r["v1"]),
                      peak_max=max(x for r in rows for x in r["peak"]),
                      beyond_fig16_envelope=sum(x > 1.5 for r in rows for x in r["peak"]),
                      by_type={t: dict(q_right=sum(x == want for r in rows if r["case"][2] == t for x in r["q"]) / (n / 2),
                                       inc_right=sum(x == want for r in rows if r["case"][2] == t for x in r["inc"]) / (n / 2))
                               for t in ("ag", "ab")})


def static():
    out = {}
    path = os.path.join(OUT, "kiuc_static.json")

    def record(key, rows, summ):
        out[key] = dict(summary=summ, rows=rows)
        print(f"{key}: report element right {summ['q_right']:.2f} none {summ['q_none']:.2f} wrong {summ['q_wrong']:.2f} | incremental "
              f"right {summ['inc_right']:.2f} none {summ['inc_none']:.2f} wrong {summ['inc_wrong']:.2f} | 3I2 > 10 % I1 "
              f"{summ['ratio_over_10pct']:.2f} | by type {summ['by_type']} | enable: {summ['why']} | weak-frame points "
              f"{summ['weak_frame_points']} | phase peak max {summ['peak_max']:.2f}, > 1.5 pu at {summ['beyond_fig16_envelope']} points",
              flush=True)
        json.dump(dict(fwd=FWD, rev_r1=REV_R1, results=out), open(path, "w"), indent=1, default=str)

    # R2, the forward set (dependability): hydro off / on (two sources), TF2 DYg (EMT too) and YgD (static only)
    for hydro in ("off", "sg"):
        for tf2 in ("DYg", "YgD"):
            for mode, k2 in MODES.items():
                for frt in (0.0, K_FRT):
                    net = network(hydro, tf2, relay=("L2", "b"))
                    rows, summ = run_set(net, FWD, frt, "f", k2)
                    record(f"R2 forward | hydro {hydro} | TF2 {tf2} | {mode} | FRT {frt:g}", rows, summ)
    # R1, the reverse set (direction, faults on EQ, hydro off) and the forward set (the control)
    for mode, k2 in MODES.items():
        for frt in (0.0, K_FRT):
            net = network("off", "DYg", relay=("L2", "a"))
            rows, summ = run_set(net, REV_R1, frt, "r", k2)
            record(f"R1 reverse | hydro off | TF2 DYg | {mode} | FRT {frt:g}", rows, summ)
            rows, summ = run_set(net, FWD, frt, "f", k2)
            record(f"R1 forward (control) | hydro off | TF2 DYg | {mode} | FRT {frt:g}", rows, summ)
    # sensitivities, one line each (primary: K2 5, LIM 2, K1 4): K1 = 2; LIM 1; K2 = 2; X'd 0.25
    for rel, cases, want, relay, hydro in (("R2 forward", FWD, "f", ("L2", "b"), "sg"), ("R1 reverse", REV_R1, "r", ("L2", "a"), "off")):
        net = network(hydro, "DYg", relay=relay)
        record(f"sens {rel} | hydro {hydro} | DYg | IEEE 2800 K2=5 | FRT {K_FRT_SENS:g}", *run_set(net, cases, K_FRT_SENS, want, K2_IEEE))
        for mode, k2 in MODES.items():
            record(f"sens {rel} | hydro {hydro} | DYg | {mode} | FRT {K_FRT:g} | LIM 1", *run_set(net, cases, K_FRT, want, k2, lim=1))
        record(f"sens {rel} | hydro {hydro} | DYg | IEEE 2800 K2=2 | FRT {K_FRT:g}", *run_set(net, cases, K_FRT, want, 2.0))
    net = network("sg", "DYg", xh="X'd 0.25")
    record(f"sens R2 forward | hydro sg X'd 0.25 | DYg | IEEE 2800 K2=5 | FRT {K_FRT:g}", *run_set(net, FWD, K_FRT, "f", K2_IEEE))
    print(f"-> {os.path.relpath(path)}")


# ------------------------------------------------------------------ Q2: EMT
TANG = TV2 = 1.0 / (2 * np.pi * 15.0)
T_FAULT = 0.30
WIN = np.arange(2.0, 3.0001, 0.25)
MIMIC_TAU = (Z_L1.imag / Z_L1.real) / (2 * np.pi)      # Line-2's X/R / 2 pi, cycles
FRT_PRIMARY = float(os.environ.get("KIUC_FRT", "4"))   # registered after the review (docs/KIUC.md)
Q2_SPECS = os.path.join(OUT, "kiuc_q2_specs.json")


def emt_settings(net, frt, k2):
    """The PSCAD inverter's settings at the nominal point: the command in its own frame, MODE2 0 / 1 with K2,
    TANG 15 Hz, TV2 15 Hz with the K2 law, FRT."""
    sg = nominal_sg(net)
    st = settings(net, sg, net.ibrs["I"].i0, frt, k2)["I"]
    return {"I": dict(ID=st["ID"], IQ=st["IQ"], MODE2=1.0 if k2 > 0 else 0.0, K2=float(k2 if k2 > 0 else 2.0),
                      D2MAG=0.0, D2ANG=0.0, TANG=TANG, TV2=TV2 if k2 > 0 else 0.0, FRT=float(frt))}


def tag(c):
    ln, m, s, rf = c
    return f"{ln}{s}{int(round(m * 100)):02d}r{int(round(rf * ZB * 100)):04d}"


def make_q2():
    """The Q2 runs: R2 forward set (both modes, hydro off / two-source), R1 reverse set and forward control (both
    modes, hydro off), the P 1.0 / Q 0 sensitivity (suppressed, hydro off, R2); each with its normal run."""
    from pscad_network import make_spec
    groups = []
    for hydro in ("off", "sg"):
        for mode, k2 in MODES.items():
            groups.append(("R2", hydro, mode, k2, "P0.25Q0.15", FWD, ("L2", "b")))
    for mode, k2 in MODES.items():
        groups.append(("R1rev", "off", mode, k2, "P0.25Q0.15", REV_R1, ("L2", "a")))
        groups.append(("R1fwd", "off", mode, k2, "P0.25Q0.15", FWD, ("L2", "a")))
    groups.append(("R2", "off", "suppressed", 0.0, "P1.0Q0", FWD, ("L2", "b")))
    specs = []
    for rel, hydro, mode, k2, op, cases, relay in groups:
        net = network(hydro, "DYg", relay=relay, op=op)
        st = emt_settings(net, FRT_PRIMARY, k2)
        pre = f"k{rel}_{hydro}_{'m1' if k2 > 0 else 'm0'}_{op.replace('.', 'p')}_"
        for c in [None] + list(cases):
            sp = make_spec(pre + ("N" if c is None else tag(c)), net, c, nominal_sg(net), {}, LIM)
            sp["settings"] = json.loads(json.dumps(st))
            sp["key_extra"] = f"kiuc_{hydro}_{rel}"
            sp.update(kind="normal" if c is None else "fault", case=None if c is None else list(c), relay_name=rel, hydro=hydro,
                      mode=mode, k2=k2, op=op, frt=FRT_PRIMARY, lim_rule=LIM, side=None if c is None else ("reverse" if rel == "R1rev" else "forward"))
            specs.append(sp)
    json.dump(specs, open(Q2_SPECS, "w"), indent=1)
    print(f"{len(specs)} runs, FRT K1 {FRT_PRIMARY:g}, LIM {LIM} -> {os.path.relpath(Q2_SPECS)}")


def numerically_clean(run):
    tt, fs = np.asarray(run["t"]), run["fs"]
    v = np.asarray(run["ch"]["VLA"])
    nm = np.abs(v[(tt > 0.2) & (tt < 0.29)]).max()
    seg = v[(tt >= 0.30) & (tt < 0.40)]
    f = np.fft.rfftfreq(len(seg), 1 / fs)
    P = np.abs(np.fft.rfft((seg - seg.mean()) * np.hanning(len(seg)))) ** 2
    pk, hf = float(np.abs(seg).max() / nm), float(P[(f >= 5000) & (f <= 10000)].sum() / P.sum())
    return pk <= 2.0 and hf <= 1e-3, pk, hf


def analyse_q2():
    from pscad_io import read_case
    from pscad_network import WORK
    from pscad_network_check import injections
    from step3_frontend import Relay, CYCLE
    specs = json.load(open(Q2_SPECS))
    out, rows = {}, []
    groups = sorted({(s["relay_name"], s["hydro"], s["mode"], s["op"]) for s in specs})
    for rel, hydro, mode, op in groups:
        g = [s for s in specs if (s["relay_name"], s["hydro"], s["mode"], s["op"]) == (rel, hydro, mode, op)]
        spn = [s for s in g if s["kind"] == "normal"][0]
        net = network(hydro, "DYg", relay=tuple(spn["relay"]), op=op)
        sg = nominal_sg(net)
        st = settings(net, sg, net.ibrs["I"].i0, spn["frt"], spn["k2"])
        _, inj_st, _ = solve(net, sg, st, None, lim=spn["lim_rule"])
        run = read_case(os.path.join(WORK, spn["name"] + ".gf46"), spn["name"])
        i25, i28 = injections(run, spn, 0.25), injections(run, spn, 0.28)
        e1 = abs(abs(i28["I"][0]) / abs(inj_st["I"][0]) - 1)
        s1 = abs(abs(i28["I"][0]) / max(abs(i25["I"][0]), 1e-9) - 1)
        gate = e1 <= 0.03 and s1 <= 0.03
        key = f"{rel} | hydro {hydro} | {mode} | {op}"
        res = dict(gate=dict(I1_emt=abs(i28["I"][0]), I1_static=abs(inj_st["I"][0]), err=e1, settled=s1, passed=gate), cases=[])
        want = "r" if rel == "R1rev" else "f"
        for sp in [s for s in g if s["kind"] == "fault"]:
            c = tuple(sp["case"])
            run = read_case(os.path.join(WORK, sp["name"] + ".gf46"), sp["name"])
            ok, pk, hf = numerically_clean(run)
            rl = Relay(sp["name"], tier="clean", mimic_tau=MIMIC_TAU)
            inc0 = rl.idx(T_FAULT)
            ends = inc0 - CYCLE // 2 - np.arange(0, 2 * CYCLE + 1, CYCLE // 4)
            mem = np.mean([rl.y(e) for e in ends], axis=0)
            q_per, inc_per, ratio = [], [], []
            for cyc in WIN:
                y = rl.y(inc0 + int(round(cyc * CYCLE)))
                q_per.append(dir32q(y, c[2] == "ag")[0])
                inc_per.append(direction_pk(mem, y))
                ratio.append(float(3 * abs(y[4]) / max(abs(y[3]), 1e-12)))
            first = lambda per: next((d for d in per if d is not None), None)
            x = np.asarray(run["ch"].get("V1M_I", []))
            v1 = float(x[int(round((T_FAULT + 2.5 / 60 - float(run["t"][0])) * run["fs"]))]) if len(x) else None
            _, y_st = ibr_state(net, sg, st, c)
            res["cases"].append(dict(name=sp["name"], case=list(c), clean=ok, peak=pk, hf=hf, q=first(q_per), q_per=q_per,
                                     inc=first(inc_per), inc_per=inc_per, ratio_min=min(ratio), v1_I=v1,
                                     weak=v1 is not None and v1 < 0.2, q_static=dir32q(y_st, c[2] == "ag")[0]))
        q = [r for r in res["cases"] if r["clean"]]
        n = max(len(q), 1)
        res["summary"] = dict(n=len(q), of=len(res["cases"]), want=want,
                              q_right=sum(r["q"] == want for r in q) / n, q_none=sum(r["q"] is None for r in q) / n,
                              q_wrong=sum(r["q"] not in (want, None) for r in q) / n,
                              inc_right=sum(r["inc"] == want for r in q) / n, inc_none=sum(r["inc"] is None for r in q) / n,
                              inc_wrong=sum(r["inc"] not in (want, None) for r in q) / n,
                              ratio_over_10pct=sum(r["ratio_min"] > 0.1 for r in q) / n,
                              emt_vs_static_q_differ=sum(r["q"] != r["q_static"] for r in q),
                              weak=[r["name"] for r in q if r["weak"]])
        out[key] = res
        s = res["summary"]
        print(f"[{key}] gate {'PASSED' if gate else 'FAILED'} (|I1| {res['gate']['I1_emt']:.3f}/{res['gate']['I1_static']:.3f}) | "
              f"{s['n']} of {s['of']} clean | report element right {s['q_right']:.2f} none {s['q_none']:.2f} wrong {s['q_wrong']:.2f} | "
              f"incremental right {s['inc_right']:.2f} none {s['inc_none']:.2f} wrong {s['inc_wrong']:.2f} | 3I2 > 10 % I1 "
              f"{s['ratio_over_10pct']:.2f} | EMT vs static (report element) differ {s['emt_vs_static_q_differ']} | weak {len(s['weak'])}", flush=True)
    json.dump(out, open(os.path.join(OUT, "kiuc_q2.json"), "w"), indent=1, default=str)
    print("-> results/network/kiuc_q2.json")


if __name__ == "__main__":
    {"preflight": preflight, "static": static, "spec": make_q2, "analyse": analyse_q2}[sys.argv[1]]()
