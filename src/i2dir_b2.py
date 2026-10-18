"""
Stage (b2), and (b1) in EMT, of docs/I2_DIRECTION.md (registered there before any run): the designed delta injected
by the source inverter (MODE2 2, LIM 1, delta in its own V1 frame) on the shunt bracket at s = 1, the source
suppressing I2 otherwise.

  static  (b2) at the 16 corners of the source box: direction_pk on solve_v1ref's measurements, every case
  spec    the 50 stage (c) shunt-bracket cases plus the normal run at the nominal source point, delta injected
  analyse the same runs read twice: (b1-EMT) each window's distance to its own case set and to the nearest
          opposite-side set (the tier the delta was designed for), and (b2) the conventional element (decide)

    python src/i2dir_b2.py carry             -> results/network/i2dir_b2_box_carried.json (after the map)
    python src/i2dir_b2.py static
    python src/i2dir_b2.py spec <point>      -> results/network/i2dir_b2_<point>_specs.json
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/network/i2dir_b2_<point>_specs.json
    python src/i2dir_b2.py analyse <point>   -> results/network/i2dir_b2_<point>.json
"""
import os, sys, json, copy, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
import frames as fr
from pscad_io import read_case
from pscad_network import WORK
from pscad_network_check import injections
from step3_frontend import Relay
from i2dir_static import network_s, operating_point, direction_pk, FWD, REV
from i2dir_emt import decide, v1m, U0, T_FAULT
from i2dir_b1_followup import build, CASES, A, B

OUT = os.path.join(HERE, "..", "results", "network")
# carried points: (tier the delta was designed for, |delta| pu, angle deg in the inverter's V1 frame)
PT = {"st020": ("structured design tier", 0.20, 230.0)}
_box = os.path.join(OUT, "i2dir_b1_patch.json")
_carried = os.path.join(OUT, "i2dir_b2_box_carried.json")
if os.path.exists(_carried):
    _c = json.load(open(_carried))
    PT["box"] = ("box 0.08", _c["abs_delta"], _c["angle_deg"])
RHO = 0.1
FLAG_V1 = 0.2


def settings(st, ic, mag, ang):
    s = copy.deepcopy(st)
    s["I"] = dict(ID=float(ic.real), IQ=float(-ic.imag), D2MAG=float(mag), D2ANG=float(ang))
    return s


def solve(net, e, s, fault):
    try:
        return nw.solve_v1ref(net, {"G": e}, s, fault, relax=0.5, max_iter=2000)
    except RuntimeError:
        return nw.solve_v1ref(net, {"G": e}, s, fault, relax=0.25, max_iter=6000)


def static():
    net = network_s(1.0, 1e6, filters=True, inject=True)
    _, st = operating_point(1.0, 1e6, U0)
    fm = build("box 0.08")
    corners = np.array(list(itertools.product((-1.0, 1.0), repeat=4)))
    e, ic = fm.sources(corners)
    out = {}
    for key, (tier, mag, ang) in [("delta 0", (None, 0.0, 0.0))] + list(PT.items()):
        rows = []
        for n, (ek, ik) in enumerate(zip(e, ic)):
            s = settings(st, ik, mag, ang)
            yN = solve(net, ek, s, None)[0]
            for c in CASES:
                y = solve(net, ek, s, (c[0], c[1], c[2], c[3] * net.rF))[0]
                rows.append(dict(corner=n, case=list(c), side="forward" if c in FWD else "reverse", d=direction_pk(yN, y)))
        res = {}
        for side, want in (("forward", "f"), ("reverse", "r")):
            q = [r for r in rows if r["side"] == side]
            res[side] = dict(n=len(q), misdirected=float(np.mean([r["d"] not in (None, want) for r in q])),
                             undecided=float(np.mean([r["d"] is None for r in q])),
                             by_type={ft: dict(misdirected=int(sum(r["d"] not in (None, want) for r in q if r["case"][2] == ft)),
                                               undecided=int(sum(r["d"] is None for r in q if r["case"][2] == ft)),
                                               n=sum(r["case"][2] == ft for r in q)) for ft in ("ab", "ag")})
        out[key] = dict(abs_delta=mag, angle_deg=ang, **res, rows=rows)
        print(f"[{key}] {mag:.2f} pu @ {ang:.0f} deg, 16 corners: forward misdirected {res['forward']['misdirected']:.2f} "
              f"undecided {res['forward']['undecided']:.2f} {res['forward']['by_type']}; reverse misdirected "
              f"{res['reverse']['misdirected']:.2f} undecided {res['reverse']['undecided']:.2f}", flush=True)
    json.dump(out, open(os.path.join(OUT, "i2dir_b2_static.json"), "w"), indent=1)
    print("-> results/network/i2dir_b2_static.json")


def carry():
    """The registered rule for the box tier's carried point, from the neighbourhood map (results/network/
    i2dir_b1_patch.json). Angular width = span of the feasible angles at 0.98 pu; radial width = span of the feasible
    radii at 205 deg. A sliver (angular width under 3 deg or radial width under 0.03 pu) carries the centroid of all
    feasible grid points if the centroid itself separates every forward-reverse pair, else the feasible grid point
    nearest to it (in the delta plane); otherwise 0.98 pu at 205 deg. The carried point's margin is reported."""
    from i2dir_b1_followup import margin
    g = json.load(open(_box))["box_patch_rho_0.1"]
    f = [(x["abs_delta"], a) for x in g for a in x["separating_angles_deg"]]
    a98 = [a for x in g if abs(x["abs_delta"] - 0.98) < 1e-9 for a in x["separating_angles_deg"]]
    r205 = [x["abs_delta"] for x in g if 205 in x["separating_angles_deg"]]
    wa = max(a98) - min(a98) if a98 else 0.0
    wr = max(r205) - min(r205) if r205 else 0.0
    sliver = wa < 3 or wr < 0.03 - 1e-9
    fm = build("box 0.08")
    out = dict(feasible_grid_points=len(f), angular_width_deg=wa, radial_width_pu=wr, sliver=sliver)
    if not sliver:
        mag, ang, how = 0.98, 205.0, "not a sliver: the design point"
    else:
        r, a = map(np.array, zip(*f))
        cen = complex(np.mean(r * np.exp(1j * np.radians(a))))
        cm, ca = abs(cen), float(np.degrees(np.angle(cen)) % 360)
        b = 2 * fm.eps * (1 + RHO)
        ok = all(not fr._meet_union(fm.zonotopes(cen, i), fm.zonotopes(cen, j), b) for i in A for j in B)
        out.update(centroid=[cm, ca], centroid_separates=ok)
        if ok:
            mag, ang, how = round(cm, 4), round(ca, 2), "sliver: the centroid (separates)"
        else:
            k = int(np.argmin(np.abs(r * np.exp(1j * np.radians(a)) - cen)))
            mag, ang, how = float(r[k]), float(a[k]), "sliver: the feasible grid point nearest the centroid"
    m = margin(fm, mag * np.exp(1j * np.radians(ang)), RHO)
    out.update(abs_delta=mag, angle_deg=ang, how=how, margin=m)
    json.dump(out, open(_carried, "w"), indent=1)
    print(f"box carried point: {mag} pu @ {ang} deg ({how}); widths {wa} deg at 0.98 pu, {wr:.2f} pu at 205 deg; "
          f"margin {m['margin_eps']:.3f} eps ({m['margin_pu']:.4f} pu), closest pair {m['pair']}")


def specs_path(p):
    return os.path.join(OUT, f"i2dir_b2_{p}_specs.json")


def make(p):
    _, mag, ang = PT[p]
    base = [s for s in json.load(open(os.path.join(OUT, "i2dir_emt_sh_specs.json"))) if s["law"] == "m0"]
    specs = []
    for b in base:
        sp = copy.deepcopy(b)
        sp["settings"]["I"].update(MODE2=2.0, D2MAG=float(mag), D2ANG=float(ang))
        sp.update(name=b["name"].replace("i2s_m0_", f"i2d_{p}_"), point=p, base=b["name"])
        specs.append(sp)
    json.dump(specs, open(specs_path(p), "w"), indent=1)
    print(f"{len(specs)} runs ({mag:.2f} pu @ {ang:.1f} deg) -> {os.path.relpath(specs_path(p))}")


def numerically_clean(run):
    tt, fs = np.asarray(run["t"]), run["fs"]
    v = np.asarray(run["ch"]["VLA"])
    nm = np.abs(v[(tt > 0.2) & (tt < 0.29)]).max()
    seg = v[(tt >= 0.30) & (tt < 0.40)]
    f = np.fft.rfftfreq(len(seg), 1 / fs)
    P = np.abs(np.fft.rfft((seg - seg.mean()) * np.hanning(len(seg)))) ** 2
    pk, hf = float(np.abs(seg).max() / nm), float(P[(f >= 5000) & (f <= 10000)].sum() / P.sum())
    return pk <= 2.0 and hf <= 1e-3, pk, hf


def analyse(p):
    tier, mag, ang = PT[p]
    d = mag * np.exp(1j * np.radians(ang))
    specs = json.load(open(specs_path(p)))
    net = network_s(1.0, 1e6, filters=True, inject=True)
    sg, st = operating_point(1.0, 1e6, U0)
    s = settings(st, complex(st["I"]["ID"], -st["I"]["IQ"]), mag, ang)
    out = dict(point=p, tier=tier, abs_delta=mag, angle_deg=ang)
    # pre-fault gate: |I1| and |I2| of every inverter, EMT against static, within 3 % and settled (0.25 vs 0.28 s)
    spn = [x for x in specs if x["kind"] == "normal"][0]
    run = read_case(os.path.join(WORK, spn["name"] + ".gf46"), spn["name"])
    i25, i28 = injections(run, spn, 0.25), injections(run, spn, 0.28)
    yN, inj_st, _ = solve(net, sg["G"], s, None)
    gate = {}
    for k in inj_st:
        for q, lab in ((0, "I1"), (1, "I2")):
            ref = abs(inj_st[k][q])
            if ref < 0.02:
                continue
            gate[f"{k} {lab}"] = dict(emt=abs(i28[k][q]), static=ref, err=abs(abs(i28[k][q]) / ref - 1),
                                     settled=abs(abs(i28[k][q]) / max(abs(i25[k][q]), 1e-9) - 1))
    passed = all(g["err"] <= 0.03 and g["settled"] <= 0.03 for g in gate.values())
    out["gate"] = dict(checks=gate, passed=passed)
    print(f"[{p}] pre-fault: " + ", ".join(f"{k} {g['emt']:.3f}/{g['static']:.3f} ({g['err']:.1%}, {g['settled']:.1%})" for k, g in gate.items())
          + f"; gate {'PASSED' if passed else 'FAILED: results not interpreted'}", flush=True)
    fm = build(tier)
    w = np.broadcast_to(np.asarray(fm.eps, float), (12,))
    Z = {k: fm.zonotopes(d, k) for k in range(len(CASES))}
    state = json.load(open(os.path.join(OUT, "i2dir_b1_state.json")))
    weak = {tuple(c) for c in state.get(tier, {}).get("v1R_below_0.2", [])}
    rows = []
    for sp in [x for x in specs if x["kind"] == "fault"]:
        c = tuple(sp["case"])
        k = CASES.index(c)
        run = read_case(os.path.join(WORK, sp["name"] + ".gf46"), sp["name"])
        ok, pk, hf = numerically_clean(run)
        rel = Relay(sp["name"], tier="clean")
        inc = rel.idx(T_FAULT)
        opp = B if k in A else A
        win = []
        for cyc, y in rel.windows(inc):
            own = fr.distance_to_set(Z[k], y, w)
            dop = min(fr.distance_to_set(Z[j], y, w) for j in opp)
            win.append(dict(cycles=float(cyc), own_eps=float(own), opp_min_eps=float(dop), separated=bool(dop > 2 * (1 + RHO) - own)))
        d_emt, at, per = decide(rel, inc)
        want = "f" if sp["side"] == "forward" else "r"
        y = solve(net, sg["G"], s, (c[0], c[1], c[2], c[3] * net.rF))[0]
        v_sink = {q: v1m(run, q, T_FAULT + 2.5 / 60) for q in ("SR", "SS")}
        rows.append(dict(name=sp["name"], case=list(c), side=sp["side"], clean=ok, peak=pk, hf=hf, windows=win,
                         b1_contained=all(x["own_eps"] <= 0.1 for x in win), b1_separated=all(x["separated"] for x in win),
                         emt=d_emt, at_cycles=at, per_window=per, static=direction_pk(yN, y),
                         misdirected=d_emt is not None and d_emt != want, undecided=d_emt is None,
                         weak_frame=c in weak or any(v is not None and v < FLAG_V1 for v in v_sink.values()), sink_v1=v_sink))
    summ = {}
    for side in ("forward", "reverse"):
        q = [r for r in rows if r["side"] == side and r["clean"]]
        summ[side] = dict(n=len(q), of=sum(r["side"] == side for r in rows),
                          b1_contained=sum(r["b1_contained"] for r in q), b1_separated=sum(r["b1_separated"] for r in q),
                          own_max_eps=max(x["own_eps"] for r in q for x in r["windows"]),
                          opp_min_eps=min(x["opp_min_eps"] for r in q for x in r["windows"]),
                          misdirected=float(np.mean([r["misdirected"] for r in q])), undecided=float(np.mean([r["undecided"] for r in q])),
                          emt_vs_static_differ=sum(r["emt"] != r["static"] for r in q),
                          weak_frame=[dict(name=r["name"], emt=r["emt"], b1_contained=r["b1_contained"], b1_separated=r["b1_separated"]) for r in q if r["weak_frame"]])
        x = summ[side]
        print(f"[{p}] {side}: {x['n']} of {x['of']} numerically clean | (b1-EMT) contained {x['b1_contained']}, separated "
              f"{x['b1_separated']} (own max {x['own_max_eps']:.3f} eps, nearest opposite {x['opp_min_eps']:.2f} eps) | (b2) "
              f"misdirected {x['misdirected']:.2f} undecided {x['undecided']:.2f}, EMT vs static differ {x['emt_vs_static_differ']} | "
              f"weak frame {len(x['weak_frame'])}", flush=True)
    out.update(summary=summ, rows=rows)
    json.dump(out, open(os.path.join(OUT, f"i2dir_b2_{p}.json"), "w"), indent=1, default=str)
    print(f"-> results/network/i2dir_b2_{p}.json")


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"carry": carry, "static": static, "spec": lambda: make(sys.argv[2]), "analyse": lambda: analyse(sys.argv[2])}[cmd]()
