"""
EMT check of the step-3 design point, delta = 1.05 pu at 225 deg, rho = 0.04 (results/FRAMES.md), before any step-3
data is generated (review/STEP3_PART3_REVIEW.md section 5). Five groups of runs:

  witness  the cases unseparated at delta = 0, each at its closest-pair realisation (frames.witness): the fault at
           S_F and normal operation at S_N (normals deduplicated). Confirms the provisional model error of 0.1 eps
           where the sets are tightest, and the clean separation ratio there
  edge     the window's edges, 221 and 230 deg: the 8 bolted ab cases (at the source points of the 1.14 pu runs)
           and the 3 A-G witnesses with the smallest gap
  pow      the same 11 cases at 225 deg with the inception drawn over one cycle (point on wave)
  normal   the 16 corners of the source box, and two confusers at the box centre: a balanced load step and a
           single-phase load at bus S (the builder checks' values)
  inst     the controller's own outputs recorded (V1M, V2M, I1M, I2M, ANG) with a 0.3 s fault: bolted L1 ab 15 %
           at 1.14 pu and bolted L1 ab 35 % at 1.05 pu (the worst drift there), each with the bare DFT reference
           and with a PLL-like low-pass on it (TANG = 1 / (2 pi 15 Hz))
  regression  fe_d105_L1ab15r000 rerun unchanged (TANG = 0): the component with the angle filter added must give the
           stored run (added to the spec file by hand, 16 Oct 2026)

Measured: for faults, on windows ending 2.0 ... 3.0 cycles after the run's own inception, the distance to the
case's own set (bare sets: factor 1.0, no reference noise, no model-error box; what the model error must cover)
and the clean distance to N in the design's sets over eps (separated with the margin above 2 (1 + rho)); after 3
cycles (3.25 ... 5.5) the distance to the own set, for the drift. For normals and confusers, the distance to N
(bare sets) before and after the switching.

    python src/frames_design_check.py spec       -> results/network/frames_design_specs.json
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/network/frames_design_specs.json
    python src/frames_design_check.py analyse    -> results/network/frames_design_check.json

Another design point, with the PLL-like reference filter in every run (review/STEP3_PART4_REVIEW.md section 3):

    python src/frames_design_check.py spec --mag 1.12 --rho 0.1 --edges 220 231 --tang-hz 15 --tag pll
    python src/frames_design_check.py analyse --mag 1.12 --rho 0.1 --edges 220 231 --tang-hz 15 --tag pll

writes frames_design_specs_pll.json / frames_design_check_pll.json, run names fq_*, no instrumented group, and an
extra group "all48": every design case once at 225 deg at a random point of the source box (coverage).
"""
import os, sys, json, time, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import make_spec, three_bus, WORK
from pscad_network_check import relay_y, read_case
from network_delta_test import CASES, tag
from frames_emt_check import _settings, SPECS as EMT_SPECS

OUT = os.path.join(HERE, "..", "results", "network")
SPECS = os.path.join(OUT, "frames_design_specs.json")
EPS = 0.08
MAG, ANG0, RHO = 1.05, 225.0, 0.04
EDGES, TANG, PREFIX, TAG = (221.0, 230.0), 0.0, "fd", None
RESULT = os.path.join(OUT, "frames_design_check.json")
MAIN = dict(factor=1.1, drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.1 * EPS)   # src/frames_main.py
BARE = dict(factor=1.0, drift_deg=3.0, ref_phi=0.0, model_err=0.0)                            # src/frames_emt_check.py
T_FAULT = 0.30
WIN = np.arange(2.0, 3.0001, 0.25)
LATE = np.arange(3.25, 5.5001, 0.25)
TANG_PLL = 1.0 / (2 * np.pi * 15.0)
CONFUSERS = [dict(kind="load_step", bus="S", y1=[0.2, -0.06], t=0.30),
             dict(kind="single_phase", bus="S", phase="A", z=[8.0, 2.0], t=0.30)]


def dcmd(ang):
    return MAG * np.exp(1j * np.radians(ang))


def models(net, kw):
    fm = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, **kw)    # one model serves every delta
    return {a: fm for a in (EDGES[0], ANG0, EDGES[1])}


def _spec(net, name, case, S, ang, kind, group, fm, **extra):
    e, ic = fm.sources(np.atleast_2d(S))
    fault = None if case is None else (case[0], case[1], case[2], case[3] * net.rF)
    sp = make_spec(name, net, fault, {"G": e[0]}, {}, 1)
    sp["settings"] = _settings(ic[0], dcmd(ang))
    for k in ("confuser", "t_fault", "dur", "t_end"):
        if k in extra:
            sp[k] = extra.pop(k)
    if "TANG" in extra:
        sp["settings"]["I"]["TANG"] = float(extra.pop("TANG"))
    elif TANG > 0:
        sp["settings"]["I"]["TANG"] = TANG
    sp.update(kind=kind, group=group, case=None if case is None else list(case), S=[float(x) for x in np.ravel(S)],
              d_cmd=[dcmd(ang).real, dcmd(ang).imag], angle=float(ang), **extra)
    return sp


def make():
    net = three_bus()
    t0 = time.time()
    main = models(net, MAIN)[225.0]
    d = dcmd(225.0)
    binding = [tuple(c) for c in fr.unseparated(main, 0j, RHO)]
    wit = {c: fr.witness(main, d, c) for c in binding}
    print(f"{len(binding)} binding cases; witness gaps / eps: " +
          ", ".join(f"{tag(c)} {w['gap'] / EPS:.3f}" for c, w in wit.items()) + f"  [{time.time() - t0:.0f} s]", flush=True)
    specs, normals = [], {}
    for c, w in wit.items():
        specs.append(_spec(net, f"{PREFIX}_w_{tag(c)}", c, w["S_F"], 225.0, "fault", "witness", main, gap_eps=w["gap"] / EPS))
        normals.setdefault(tuple(np.round(w["S_N"], 9)), []).append(tag(c))
    for k, (S, owners) in enumerate(normals.items()):
        specs.append(_spec(net, f"{PREFIX}_wN{k:02d}", None, np.array(S), 225.0, "normal", "witness", main, witness_of=owners))
    s114 = {tuple(sp["case"]): sp["S"] for sp in json.load(open(EMT_SPECS)) if sp["dtag"] == "d114" and sp["kind"] == "fault"}
    bc = [c for c in CASES if c[2] == "ab" and c[3] == 0.0]
    ag3 = sorted([c for c in binding if c[2] == "ag"], key=lambda c: wit[c]["gap"])[:3]
    hard = [(c, np.array(s114[c])) for c in bc] + [(c, wit[c]["S_F"]) for c in ag3]
    for ang in EDGES:
        for c, S in hard:
            specs.append(_spec(net, f"{PREFIX}_e{int(ang)}_{tag(c)}", c, S, ang, "fault", "edge", main))
    rng = np.random.default_rng(5)
    for c, S in hard:
        tf = float(np.round(T_FAULT + rng.uniform(0, 1) / 60.0, 5))
        specs.append(_spec(net, f"{PREFIX}_p_{tag(c)}", c, S, 225.0, "fault", "pow", main, t_fault=tf))
    for k, u in enumerate(itertools.product((-1.0, 1.0), repeat=4)):
        specs.append(_spec(net, f"{PREFIX}_nc{k:02d}", None, np.array(u), 225.0, "normal", "normal", main, corner=list(u)))
    for cf in CONFUSERS:
        specs.append(_spec(net, f"{PREFIX}_cf_{cf['kind']}", None, np.zeros(4), 225.0, "normal", "confuser", main, confuser=cf))
    if TAG is not None:
        S48 = rng.uniform(-1, 1, (len(CASES), 4))
        for c, S in zip(CASES, S48):
            specs.append(_spec(net, f"{PREFIX}_a_{tag(c)}", c, S, 225.0, "fault", "all48", main))
    for mag_tag, mag, c in (() if TAG is not None else (("114", 1.14, ("L1", 0.15, "ab", 0.0)), ("105", 1.05, ("L1", 0.35, "ab", 0.0)))):
        for ttag, tang in (("dft", 0.0), ("pll", TANG_PLL)):
            sp = _spec(net, f"fd_i{mag_tag}_{tag(c)}_{ttag}", c, np.array(s114[c]), 225.0, "fault", "inst", main,
                       dur=0.30, t_end=0.70, TANG=tang)
            sp["settings"]["I"]["D2MAG"] = mag
            sp["d_cmd"] = [mag * np.cos(np.radians(225)), mag * np.sin(np.radians(225))]
            specs.append(sp)
    json.dump(specs, open(SPECS, "w"), indent=1, default=float)
    by = {}
    for sp in specs:
        by[sp["group"]] = by.get(sp["group"], 0) + 1
    print(f"{len(specs)} runs {by} -> {os.path.relpath(SPECS)}  [{time.time() - t0:.0f} s]")


def analyse():
    net = three_bus()
    specs = json.load(open(SPECS))
    bare, main = models(net, BARE), models(net, MAIN)
    rows, inst = [], {}
    t0 = time.time()
    for sp in specs:
        path = os.path.join(WORK, sp["name"] + ".gf46")
        if not os.path.exists(os.path.join(path, sp["name"] + "_01.out")):
            print("missing", sp["name"])
            continue
        run = read_case(path, sp["name"])
        tf = sp.get("t_fault", T_FAULT)
        ang = sp["angle"]
        d = complex(*sp["d_cmd"])
        uL = relay_y(run, tf - 0.05)[0]
        uL /= abs(uL)
        yat = lambda cyc: relay_y(run, tf + cyc / 60.0) * np.conj(uL)
        if sp["group"] == "regression":
            ref = read_case(os.path.join(WORK, sp["regression_of"] + ".gf46"), sp["regression_of"])
            diff = max(float(np.max(np.abs(np.asarray(run["ch"][ch]) - np.asarray(ref["ch"][ch]))))
                       for ch in ("VLA", "VLB", "VLC", "ILA", "ILB", "ILC", "IinvIA", "IinvIB", "IinvIC"))
            print(f"regression {sp['name']} against {sp['regression_of']} (TANG = 0, new component): largest "
                  f"channel difference {diff:.3e} (kV / kA)")
            inst[sp["name"]] = dict(regression_max_diff=diff)
            continue
        if sp["group"] == "inst":
            ts = np.arange(tf - 2 / 60, tf + 0.30 + 2 / 60, 0.5 / 60)
            tr = {}
            for ch in ("V1M_I", "V2M_I", "I1M_I", "I2M_I", "ANG_I"):
                x = np.asarray(run["ch"].get(ch, []))
                if len(x):
                    tt = np.arange(len(x)) / run["fs"]
                    tr[ch] = [float(np.interp(q, tt, np.unwrap(np.radians(x)) * 180 / np.pi if ch == "ANG_I" else x)) for q in ts]
            k = CASES.index(tuple(sp["case"]))
            tr["outside_own_eps"] = [float(fr.distance_to_set(bare[ang].zonotopes(d, k), yat(c)) / EPS)
                                     for c in (2.0, 3.0, 5.0, 8.0, 12.0, 16.0)]
            tr["t"] = [float(q) for q in ts]
            inst[sp["name"]] = tr
            continue
        if sp["kind"] == "fault":
            k = CASES.index(tuple(sp["case"]))
            own = [fr.distance_to_set(bare[ang].zonotopes(d, k), yat(c)) / EPS for c in WIN]
            to_n = [fr.distance_to_set(main[ang].zonotopes(d, None), yat(c)) / EPS for c in WIN]
            late = [fr.distance_to_set(bare[ang].zonotopes(d, k), yat(c)) / EPS for c in LATE]
            rows.append(dict(name=sp["name"], group=sp["group"], case=sp["case"], angle=ang, t_fault=tf,
                             gap_eps=sp.get("gap_eps"), outside_own_eps=max(own), outside_own_at=float(WIN[int(np.argmax(own))]),
                             ratio_to_N=min(to_n), separated_margin=bool(min(to_n) > 2 * (1 + RHO)), late_outside_own_eps=max(late)))
        else:
            pre = fr.distance_to_set(bare[ang].zonotopes(d, None), relay_y(run, tf - 0.05) * np.conj(uL)) / EPS
            post = [fr.distance_to_set(bare[ang].zonotopes(d, None), yat(c)) / EPS for c in WIN] if sp.get("confuser") else []
            rows.append(dict(name=sp["name"], group=sp["group"], angle=ang, normal_outside_eps=max([pre] + post), pre_eps=pre,
                             post_eps=post))
    print(f"{len(rows)} runs analysed, {len(inst)} instrumented  [{time.time() - t0:.0f} s]")
    summ = {}
    for g in ("witness", "edge", "pow", "all48"):
        f = [r for r in rows if r["group"] == g and "outside_own_eps" in r]
        if f:
            w = max(f, key=lambda r: r["outside_own_eps"])
            m = min(f, key=lambda r: r["ratio_to_N"])
            summ[g] = dict(n=len(f), outside_own_max=w["outside_own_eps"], outside_own_at=[w["name"], w["outside_own_at"]],
                           n_outside=sum(r["outside_own_eps"] > 1e-6 for r in f), ratio_to_N_min=m["ratio_to_N"],
                           ratio_to_N_min_at=m["name"], n_not_separated_margin=sum(not r["separated_margin"] for r in f),
                           late_outside_max=max(r["late_outside_own_eps"] for r in f))
            print(f"{g:8s}: {len(f)} faults; outside own set max {w['outside_own_eps']:.3f} eps ({w['name']}, {w['outside_own_at']} c), "
                  f"{summ[g]['n_outside']} outside; clean distance to N min {m['ratio_to_N']:.2f} eps ({m['name']}), "
                  f"{summ[g]['n_not_separated_margin']} below 2(1 + rho); after 3 cycles outside own set max {summ[g]['late_outside_max']:.2f} eps")
    for g in ("witness", "normal", "confuser"):
        n = [r for r in rows if r["group"] == g and "normal_outside_eps" in r]
        if n:
            w = max(n, key=lambda r: r["normal_outside_eps"])
            summ[g + "_normal"] = dict(n=len(n), outside_max=w["normal_outside_eps"], at=w["name"])
            print(f"{g:8s}: {len(n)} normal runs; outside N max {w['normal_outside_eps']:.3f} eps ({w['name']})")
    for nm, tr in inst.items():
        if "regression_max_diff" in tr:
            continue
        a = tr.get("ANG_I")
        print(f"{nm}: ANG span over the fault {max(a) - min(a):.1f} deg; |I1| {min(tr['I1M_I']):.2f}-{max(tr['I1M_I']):.2f}, "
              f"|I2| {min(tr['I2M_I']):.2f}-{max(tr['I2M_I']):.2f} pu; outside own set at 2/3/5/8/12/16 c: "
              + " ".join(f"{x:.2f}" for x in tr["outside_own_eps"]) if a else f"{nm}: no controller channels")
    json.dump(dict(design=dict(mag=MAG, angle=ANG0, rho=RHO, edges=EDGES, tang=TANG, main=MAIN, bare=BARE), summary=summ,
                   rows=rows, inst=inst), open(RESULT, "w"), indent=1, default=float)
    print(f"-> {os.path.relpath(RESULT)}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["spec", "analyse"])
    ap.add_argument("--mag", type=float, default=MAG)
    ap.add_argument("--rho", type=float, default=RHO)
    ap.add_argument("--edges", type=float, nargs=2, default=EDGES)
    ap.add_argument("--tang-hz", type=float, default=0.0)
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    MAG, RHO, EDGES, TAG = a.mag, a.rho, tuple(a.edges), a.tag
    TANG = 1.0 / (2 * np.pi * a.tang_hz) if a.tang_hz > 0 else 0.0
    if TAG is not None:
        PREFIX = "fq"
        SPECS = os.path.join(OUT, f"frames_design_specs_{TAG}.json")
        RESULT = os.path.join(OUT, f"frames_design_check_{TAG}.json")
    {"spec": make, "analyse": analyse}[a.what]()
