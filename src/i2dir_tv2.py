"""
The grid-side bracket's IEEE 2800 cell with the V2 filter (docs/I2_DIRECTION.md, registered before it runs):

  reg     one stored shunt-case MODE2 1 run (i2s_m1_L1ag55r100) rerun under BUILD_VERSION 5 with TV2 = 0: must match
          the stored output to round-off
  cons    5 shunt-case MODE2 1 cases (4 forward, 1 reverse: L2ab05r000) with TV2 = 1/(2 pi 15 Hz): the decisions
          must not change
  grid    no shunts (grid-side current control), MODE2 1 with TV2 = 1/(2 pi 15 Hz): the normal run and the 50 fault
          cases. Stop rule: if it still diverges, the cell is "not runnable in this model". Every fault run also gets
          the per-run numerical check (peak |vA| in the fault <= 2 x nominal, 5-10 kHz energy share <= 1e-3); runs
          failing it are excluded and counted, so the cell reads "n of 25 interpretable"

    python src/i2dir_tv2.py spec      -> results/network/i2dir_tv2_specs.json
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/network/i2dir_tv2_specs.json
    python src/i2dir_tv2.py analyse   -> results/network/i2dir_tv2.json
"""
import os, sys, json, copy
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
from pscad_io import read_case
from pscad_network import WORK
from pscad_network_check import injections
from step3_frontend import Relay
from i2dir_static import network_s, operating_point, solve_v1, direction_pk
from i2dir_emt import decide, U0, T_FAULT

OUT = os.path.join(HERE, "..", "results", "network")
SPECS = os.path.join(OUT, "i2dir_tv2_specs.json")
TV2 = 1.0 / (2 * np.pi * 15.0)
REG = "i2s_m1_L1ag55r100"
CONS = ["i2s_m1_L1ab15r000", "i2s_m1_L1ab55r000", "i2s_m1_L1ag15r050", "i2s_m1_L1ag95r100", "i2s_m1_L2ab05r000"]


def make():
    sh = {s["name"]: s for s in json.load(open(os.path.join(OUT, "i2dir_emt_sh_specs.json")))}
    plain = [s for s in json.load(open(os.path.join(OUT, "i2dir_emt_specs.json"))) if s["law"] == "m1"]
    specs = []
    r = copy.deepcopy(sh[REG])
    r.update(name="i2t_reg_" + REG, group="reg", regression_of=REG)
    specs.append(r)
    for nm in CONS:
        c = copy.deepcopy(sh[nm])
        c["settings"]["I"]["TV2"] = TV2
        c.update(name="i2t_cons_" + nm, group="cons", base=nm)
        specs.append(c)
    for p in plain:
        g = copy.deepcopy(p)
        g["settings"]["I"]["TV2"] = TV2
        g.update(name=p["name"].replace("i2_m1_", "i2t_grid_"), group="grid")
        specs.append(g)
    json.dump(specs, open(SPECS, "w"), indent=1)
    by = {}
    for s in specs:
        by[s["group"]] = by.get(s["group"], 0) + 1
    print(f"{len(specs)} runs {by} -> {os.path.relpath(SPECS)}")


def analyse():
    specs = json.load(open(SPECS))
    out = {}
    # regression
    sp = [s for s in specs if s["group"] == "reg"][0]
    a = read_case(os.path.join(WORK, sp["name"] + ".gf46"), sp["name"])
    b = read_case(os.path.join(WORK, sp["regression_of"] + ".gf46"), sp["regression_of"])
    diff = max(float(np.max(np.abs(np.asarray(a["ch"][ch]) - np.asarray(b["ch"][ch])))) for ch in ("VLA", "VLB", "VLC", "ILA", "ILB", "ILC"))
    out["regression_max_diff"] = diff
    print(f"regression (BUILD_VERSION 5, TV2 = 0) against {sp['regression_of']}: largest channel difference {diff:.3e}")
    # consistency
    cons = []
    for sp in [s for s in specs if s["group"] == "cons"]:
        d_new = decide(Relay(sp["name"], tier="clean"), Relay(sp["name"], tier="clean").idx(T_FAULT))[0]
        rb = Relay(sp["base"], tier="clean")
        d_old = decide(rb, rb.idx(T_FAULT))[0]
        cons.append(dict(case=sp["base"], tv2=d_new, no_tv2=d_old, same=d_new == d_old))
    out["consistency"] = cons
    print(f"consistency, shunt case with TV2 15 Hz: {sum(c['same'] for c in cons)} of {len(cons)} decisions unchanged "
          + str([(c['case'][7:], c['no_tv2'], c['tv2']) for c in cons]))
    # grid-side bracket
    net = network_s(1.0, 0.5j)
    sg, st = operating_point(1.0, 0.5j, U0)
    yN, _ = solve_v1(net, sg, st, None)
    spn = [s for s in specs if s["group"] == "grid" and s["kind"] == "normal"][0]
    run = read_case(os.path.join(WORK, spn["name"] + ".gf46"), spn["name"])
    t = np.asarray(run["t"])
    va = np.asarray(run["ch"]["VLA"])
    nom = np.abs(va[(t > 0.2) & (t < 0.29)]).max()
    tail = float(np.abs(va[t > 0.4]).max() / nom)
    _, inj_static, _ = nw.solve_v1ref(net, sg, st, None)
    inj = injections(run, spn, 0.28)
    gate = {k: abs(abs(inj[k][0]) / abs(inj_static[k][0]) - 1) for k in inj_static}
    stable = tail < 1.5 and all(v <= 0.03 for v in gate.values())
    out["grid_gate"] = dict(tail_peak_over_nominal=tail, i1_errors=gate, passed=stable)
    print(f"grid-side, MODE2 1 + TV2: normal run tail peak {tail:.2f} x nominal; pre-fault |I1| errors "
          + ", ".join(f"{k} {v:.1%}" for k, v in gate.items()) + f"; gate {'PASSED' if stable else 'FAILED: not runnable in this model'}")
    rows = []

    def numerically_clean(name):
        r = read_case(os.path.join(WORK, name + ".gf46"), name)
        tt, fs = np.asarray(r["t"]), r["fs"]
        v = np.asarray(r["ch"]["VLA"])
        nm = np.abs(v[(tt > 0.2) & (tt < 0.29)]).max()
        seg = v[(tt >= 0.30) & (tt < 0.40)]
        f = np.fft.rfftfreq(len(seg), 1 / fs)
        P = np.abs(np.fft.rfft((seg - seg.mean()) * np.hanning(len(seg)))) ** 2
        pk, hf = float(np.abs(seg).max() / nm), float(P[(f >= 5000) & (f <= 10000)].sum() / P.sum())
        return pk <= 2.0 and hf <= 1e-3, pk, hf

    if stable:
        for sp in [s for s in specs if s["group"] == "grid" and s["kind"] == "fault"]:
            ok, pk, hf = numerically_clean(sp["name"])
            if not ok:
                rows.append(dict(name=sp["name"], side=sp["side"], excluded=True, peak=pk, hf=hf))
                continue
            c = tuple(sp["case"])
            y, _ = solve_v1(net, sg, st, (c[0], c[1], c[2], c[3] * net.rF))
            rel = Relay(sp["name"], tier="clean")
            d_emt = decide(rel, rel.idx(T_FAULT))[0]
            want = "f" if sp["side"] == "forward" else "r"
            d_st = direction_pk(yN, y)
            rows.append(dict(name=sp["name"], side=sp["side"], excluded=False, emt=d_emt, static=d_st,
                             misdirected=d_emt is not None and d_emt != want, undecided=d_emt is None))
        for side in ("forward", "reverse"):
            allq = [r for r in rows if r["side"] == side]
            q = [r for r in allq if not r["excluded"]]
            out[side] = dict(n=len(q), of=len(allq), excluded=len(allq) - len(q),
                             misdirected=float(np.mean([r["misdirected"] for r in q])) if q else None,
                             undecided=float(np.mean([r["undecided"] for r in q])) if q else None,
                             disagree=sum(r["emt"] != r["static"] for r in q))
            print(f"grid-side IEEE 2800 {side}: {len(q)} of {len(allq)} interpretable; misdirected {out[side]['misdirected']}, "
                  f"undecided {out[side]['undecided']}; EMT vs static differ on {out[side]['disagree']}")
    out["rows"] = rows
    json.dump(out, open(os.path.join(OUT, "i2dir_tv2.json"), "w"), indent=1, default=str)
    print("-> results/network/i2dir_tv2.json")


if __name__ == "__main__":
    {"spec": make, "analyse": analyse}[sys.argv[1]]()
