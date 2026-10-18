"""
EMT stage (c) of docs/I2_DIRECTION.md, the blind test: direction at the inverter's relay (bus R on L1) with every load
behind the relay inverter-interfaced (s = 1: the R and S loads are gfl_avm sinks, MODE2 0, TANG 15 Hz, holding their
current through the fault). The source inverter at R runs MODE2 0 (suppressed) or 1 (IEEE 2800, K2 = 2). Nominal
source point; the hard forward (L1) and reverse (L2) sets; one pre-fault run per law.

    python src/i2dir_emt.py spec       -> results/network/i2dir_emt_specs.json
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/network/i2dir_emt_specs.json
    python src/i2dir_emt.py analyse    -> results/network/i2dir_emt.json
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
from pscad_network import make_spec, WORK, IBASE_PK
from pscad_network_check import injections
from step3_frontend import Relay, CYCLE
from network_delta_test import tag
from i2dir_static import network_s, operating_point, solve_v1, direction_pk, FWD, REV

OUT = os.path.join(HERE, "..", "results", "network")
SPECS = os.path.join(OUT, "i2dir_emt_specs.json")
TANG = 1.0 / (2 * np.pi * 15.0)
LAWS = {"m0": ("suppressed", 1e6, 0.0), "m1": ("IEEE 2800 (K2 = 2)", 0.5j, 1.0)}
U0 = (0.0, 0.0, 0.0, 0.0)
T_FAULT = 0.30
WIN = np.arange(2.0, 3.0001, 0.25)


def make():
    specs = []
    net = network_s(1.0, 1e6)                       # the builder's view: every inverter's sequence paths open
    for lt, (law, neg_z, mode2) in LAWS.items():
        sg, st = operating_point(1.0, neg_z, U0)
        for c in [None] + FWD + REV:
            fault = None if c is None else (c[0], c[1], c[2], c[3] * net.rF)
            name = f"i2_{lt}_" + ("N" if c is None else tag(c))
            sp = make_spec(name, net, fault, {"G": sg["G"]}, {}, 1)
            sp["settings"] = {k: dict(ID=v["ID"], IQ=v["IQ"], MODE2=(mode2 if k == "I" else 0.0), D2MAG=0.0, D2ANG=0.0, TANG=TANG)
                              for k, v in st.items()}
            sp.update(kind="normal" if c is None else "fault", law=lt, case=None if c is None else list(c),
                      side=None if c is None else ("forward" if c in FWD else "reverse"))
            specs.append(sp)
    json.dump(specs, open(SPECS, "w"), indent=1)
    print(f"{len(specs)} runs -> {os.path.relpath(SPECS)}")


def decide(rel, inc):
    """The first window (2.0 ... 3.0 cycles) that decides, with the 0.05 pu pickups; increments against the memory."""
    mem_ends = inc - CYCLE // 2 - np.arange(0, 2 * CYCLE + 1, CYCLE // 4)
    mem = np.mean([rel.y(e) for e in mem_ends], axis=0)
    for c in WIN:
        d = direction_pk(mem, rel.y(inc + int(round(c * CYCLE))))
        if d is not None:
            return d, float(c)
    return None, None


def analyse():
    specs = json.load(open(SPECS))
    rows, checks = [], {}
    for lt, (law, neg_z, mode2) in LAWS.items():
        net = network_s(1.0, neg_z)
        sg, st = operating_point(1.0, neg_z, U0)
        yN, _ = solve_v1(net, sg, st, None)
        # pre-fault check: sink and source-inverter currents, EMT against static
        sp = [s for s in specs if s["law"] == lt and s["kind"] == "normal"][0]
        rel = Relay(sp["name"], tier="clean")
        from pscad_io import read_case
        run = read_case(os.path.join(WORK, sp["name"] + ".gf46"), sp["name"])
        inj_emt = injections(run, sp, 0.28)
        _, inj_static, _ = nw.solve_v1ref(net, sg, st, None) if True else (None, None, None)
        checks[lt] = {k: dict(emt=abs(inj_emt[k][0]), static=abs(inj_static[k][0])) for k in inj_static}
        print(f"{law}: pre-fault |I1| EMT vs static: " + ", ".join(f"{k} {v['emt']:.3f} / {v['static']:.3f}" for k, v in checks[lt].items()))
        for sp in [s for s in specs if s["law"] == lt and s["kind"] == "fault"]:
            c = tuple(sp["case"])
            y, _ = solve_v1(net, sg, st, (c[0], c[1], c[2], c[3] * net.rF))
            d_static = direction_pk(yN, y)
            try:
                rel = Relay(sp["name"], tier="clean")
            except FileNotFoundError:
                print("missing", sp["name"])
                continue
            d_emt, at = decide(rel, rel.idx(T_FAULT))
            want = "f" if sp["side"] == "forward" else "r"
            rows.append(dict(name=sp["name"], law=lt, side=sp["side"], case=list(c), static=d_static, emt=d_emt, at_cycles=at,
                             emt_misdirected=d_emt is not None and d_emt != want, emt_undecided=d_emt is None,
                             static_misdirected=d_static is not None and d_static != want, static_undecided=d_static is None))
    summ = {}
    for lt, (law, _, _) in LAWS.items():
        for side in ("forward", "reverse"):
            q = [r for r in rows if r["law"] == lt and r["side"] == side]
            if not q:
                continue
            s = {k: float(np.mean([r[k] for r in q])) for k in ("emt_misdirected", "emt_undecided", "static_misdirected", "static_undecided")}
            s["n"] = len(q)
            s["disagree"] = [r["name"] for r in q if r["emt"] != r["static"]]
            summ[f"{lt}|{side}"] = s
            print(f"{law:20s} {side:8s}: EMT misdirected {s['emt_misdirected']:.2f} undecided {s['emt_undecided']:.2f} | static "
                  f"(same cases) misdirected {s['static_misdirected']:.2f} undecided {s['static_undecided']:.2f} | EMT vs static differ on "
                  f"{len(s['disagree'])} of {len(q)}")
    f0, f1 = summ.get("m0|forward"), summ.get("m1|forward")
    r0, r1 = summ.get("m0|reverse"), summ.get("m1|reverse")
    if f0 and f1 and r0 and r1:
        print(f"claim (MODE2 0 forward misdirected+undecided >= 0.25): {f0['emt_misdirected'] + f0['emt_undecided']:.2f} -> "
              f"{'REPRODUCED' if f0['emt_misdirected'] + f0['emt_undecided'] >= 0.25 else 'NOT reproduced'}")
        print(f"fix (MODE2 1 forward misdirected <= 0.05): {f1['emt_misdirected']:.2f} -> {'REPRODUCED' if f1['emt_misdirected'] <= 0.05 else 'NOT reproduced'}")
        print(f"reverse misdirected <= 0.05 under both: {r0['emt_misdirected']:.2f} / {r1['emt_misdirected']:.2f}")
    json.dump(dict(prefault_checks=checks, summary=summ, rows=rows), open(os.path.join(OUT, "i2dir_emt.json"), "w"), indent=1, default=str)
    print("-> results/network/i2dir_emt.json")


if __name__ == "__main__":
    {"spec": make, "analyse": analyse}[sys.argv[1]]()
