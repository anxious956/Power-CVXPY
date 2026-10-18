"""
EMT check of a high-resistance design point (results/HIGHR.md; review/HIGHR_REVIEW.md): the A-G-only case set of
src/highr_ag_design.py (A-G to R_top, B-C to 5 ohm arc), the structured design tier, the filtered reference in every
run, the mimic chain at the relay. Groups, as src/frames_design_check.py:

  witness  every case unseparated at delta = 0, at its closest-pair realisation (fault S_F; normals at S_N, deduplicated)
  edge     the separating window's two edges, on the witnesses of the 6 smallest-gap cases
  pow      the same 6 at the design angle with the inception drawn over one cycle
  all      every case once at the design angle, at a random source point
  normal   the 16 corners of the source box, and the two confusers at the box centre

Measured, on windows ending 2.0 ... 3.0 cycles after each run's own inception, through the mimic chain:
  outside own set   distance of the fault point to its case's BARE set (factor 1, no reference noise, no model-error
                    box, no instrument symbols: the EMT runs are clean), in units of the white-noise box (V 0.02 / I 0.04)
  distance to N     clean distance to N of the design's sets, same units; separated with the margin above 2 (1 + rho)

    python src/highr_emt_check.py spec    --rtop 160 --mag 1.12 --angle 330 --rho 0 --edges 326 330
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/network/highr_emt_specs_<rtop>.json
    python src/highr_emt_check.py analyse --rtop 160 --mag 1.12 --angle 330 --rho 0 --edges 326 330
"""
import os, sys, json, time, itertools, argparse
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import make_spec, three_bus, WORK
from pscad_network_check import relay_y, read_case
from network_delta_test import tag
from frames_emt_check import _settings
from highr_ag_design import cases_for, INSTR, WHITE

OUT = os.path.join(HERE, "..", "results", "network")
SCALE = np.array(WHITE + WHITE)
TANG = 1.0 / (2 * np.pi * 15.0)
T_FAULT = 0.30
WIN = np.arange(2.0, 3.0001, 0.25)
CONFUSERS = [dict(kind="load_step", bus="S", y1=[0.2, -0.06], t=0.30),
             dict(kind="single_phase", bus="S", phase="A", z=[8.0, 2.0], t=0.30)]


def models(net, cases):
    main = fr.FrameModel(net, cases, n_samples=150, face_pts=3, seed=1, eps=SCALE, factor=1.1, drift_deg=3.0,
                         ref_phi=0.030333432167374483, model_err=0.008, instr=INSTR)
    bare = fr.FrameModel(net, cases, n_samples=150, face_pts=3, seed=1, eps=SCALE, factor=1.0, drift_deg=3.0,
                         ref_phi=0.0, model_err=0.0)
    return main, bare


def make(a):
    net = three_bus()
    cases = cases_for(a.rtop)
    main, _ = models(net, cases)
    d = a.mag * np.exp(1j * np.radians(a.angle))
    t0 = time.time()
    binding = [tuple(c) for c in fr.unseparated(main, 0j, a.rho)]
    wit = {c: fr.witness(main, d, c) for c in binding}
    print(f"{len(binding)} binding cases  [{time.time() - t0:.0f} s]", flush=True)

    def sp_for(name, case, S, ang, kind, group, **extra):
        e, ic = main.sources(np.atleast_2d(S))
        fault = None if case is None else (case[0], case[1], case[2], case[3] * net.rF)
        sp = make_spec(name, net, fault, {"G": e[0]}, {}, 1)
        dd = a.mag * np.exp(1j * np.radians(ang))
        sp["settings"] = _settings(ic[0], dd)
        sp["settings"]["I"]["TANG"] = TANG
        for k in ("confuser", "t_fault"):
            if k in extra:
                sp[k] = extra.pop(k)
        sp.update(kind=kind, group=group, case=None if case is None else list(case), S=[float(x) for x in np.ravel(S)],
                  d_cmd=[dd.real, dd.imag], angle=float(ang), **extra)
        return sp

    p = f"fh{a.rtop}"
    specs, normals = [], {}
    for c, w in wit.items():
        specs.append(sp_for(f"{p}_w_{tag(c)}", c, w["S_F"], a.angle, "fault", "witness", gap=w["gap"]))
        normals.setdefault(tuple(np.round(w["S_N"], 9)), []).append(tag(c))
    for k, S in enumerate(normals):
        specs.append(sp_for(f"{p}_wN{k:02d}", None, np.array(S), a.angle, "normal", "witness"))
    hard = sorted(wit, key=lambda c: wit[c]["gap"])[:6]
    for ang in a.edges:
        for c in hard:
            specs.append(sp_for(f"{p}_e{int(ang)}_{tag(c)}", c, wit[c]["S_F"], ang, "fault", "edge"))
    rng = np.random.default_rng(5)
    for c in hard:
        specs.append(sp_for(f"{p}_p_{tag(c)}", c, wit[c]["S_F"], a.angle, "fault", "pow",
                            t_fault=float(np.round(T_FAULT + rng.uniform(0, 1) / 60, 5))))
    for c, S in zip(cases, rng.uniform(-1, 1, (len(cases), 4))):
        specs.append(sp_for(f"{p}_a_{tag(c)}", c, S, a.angle, "fault", "all"))
    for k, u in enumerate(itertools.product((-1.0, 1.0), repeat=4)):
        specs.append(sp_for(f"{p}_nc{k:02d}", None, np.array(u), a.angle, "normal", "normal"))
    for cf in CONFUSERS:
        specs.append(sp_for(f"{p}_cf_{cf['kind']}", None, np.zeros(4), a.angle, "normal", "confuser", confuser=cf))
    path = os.path.join(OUT, f"highr_emt_specs_{a.rtop}.json")
    json.dump(specs, open(path, "w"), indent=1, default=float)
    by = {}
    for sp in specs:
        by[sp["group"]] = by.get(sp["group"], 0) + 1
    print(f"{len(specs)} runs {by} -> {os.path.relpath(path)}  [{time.time() - t0:.0f} s]")


def analyse(a):
    net = three_bus()
    cases = cases_for(a.rtop)
    main, bare = models(net, cases)
    z1 = net.lines["L1"].z1
    tau = (z1.imag / z1.real) / (2 * np.pi)
    specs = json.load(open(os.path.join(OUT, f"highr_emt_specs_{a.rtop}.json")))
    rows = []
    for sp in specs:
        path = os.path.join(WORK, sp["name"] + ".gf46")
        if not os.path.exists(os.path.join(path, sp["name"] + "_01.out")):
            print("missing", sp["name"])
            continue
        run = read_case(path, sp["name"])
        tf = sp.get("t_fault", T_FAULT)
        d = complex(*sp["d_cmd"])
        uL = relay_y(run, tf - 0.05, tau)[0]
        uL /= abs(uL)
        yat = lambda c: relay_y(run, tf + c / 60.0, tau) * np.conj(uL)
        if sp["kind"] == "fault":
            k = cases.index(tuple(sp["case"]))
            own = [fr.distance_to_set(bare.zonotopes(d, k), yat(c), SCALE) for c in WIN]
            to_n = [fr.distance_to_set(main.zonotopes(d, None), yat(c), SCALE) for c in WIN]
            rows.append(dict(name=sp["name"], group=sp["group"], case=sp["case"], angle=sp["angle"], outside_own=max(own),
                             to_N=min(to_n), separated_margin=bool(min(to_n) > 2 * (1 + a.rho)), gap=sp.get("gap")))
        else:
            pre = fr.distance_to_set(bare.zonotopes(d, None), relay_y(run, tf - 0.05, tau) * np.conj(uL), SCALE)
            post = [fr.distance_to_set(bare.zonotopes(d, None), yat(c), SCALE) for c in WIN] if sp.get("confuser") else []
            rows.append(dict(name=sp["name"], group=sp["group"], normal_outside=max([pre] + post)))
    summ = {}
    print(f"R_top {a.rtop} ohm, delta {a.mag} pu at {a.angle} deg, rho {a.rho}; distances in units of the white box:")
    for g in ("witness", "edge", "pow", "all"):
        f = [r for r in rows if r["group"] == g and "outside_own" in r]
        if f:
            w = max(f, key=lambda r: r["outside_own"])
            m = min(f, key=lambda r: r["to_N"])
            summ[g] = dict(n=len(f), outside_own_max=w["outside_own"], at=w["name"], n_outside=sum(r["outside_own"] > 1e-6 for r in f),
                           to_N_min=m["to_N"], to_N_min_at=m["name"], n_not_separated=sum(not r["separated_margin"] for r in f))
            print(f"  {g:8s}: {len(f)} faults; outside own set max {w['outside_own']:.3f} ({w['name']}), {summ[g]['n_outside']} outside; "
                  f"clean distance to N min {m['to_N']:.2f} ({m['name']}), {summ[g]['n_not_separated']} below 2 (1 + rho)")
    for g in ("witness", "normal", "confuser"):
        n = [r for r in rows if r["group"] == g and "normal_outside" in r]
        if n:
            w = max(n, key=lambda r: r["normal_outside"])
            summ[g + "_normal"] = dict(n=len(n), outside_max=w["normal_outside"], at=w["name"])
            print(f"  {g:8s}: {len(n)} normal runs; outside N max {w['normal_outside']:.3f} ({w['name']})")
    path = os.path.join(OUT, f"highr_emt_check_{a.rtop}.json")
    json.dump(dict(design=vars(a), summary=summ, rows=rows), open(path, "w"), indent=1, default=float)
    print(f"-> {os.path.relpath(path)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["spec", "analyse"])
    ap.add_argument("--rtop", type=int, default=160)
    ap.add_argument("--mag", type=float, default=1.12)
    ap.add_argument("--angle", type=float, default=330.0)
    ap.add_argument("--rho", type=float, default=0.0)
    ap.add_argument("--edges", type=float, nargs=2, default=(326.0, 330.0))
    a = ap.parse_args()
    {"spec": make, "analyse": analyse}[a.what](a)
