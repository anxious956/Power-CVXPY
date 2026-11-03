"""
Longer lines (docs/LONG_LINES.md, pre-registered 19 Oct 2026): does the designed delta matter more for detection as
the lines get longer? The step-3 three-bus main configuration with one change, a length factor k_L on z1, z2 and
their zero-sequence impedances; R_f stays in ohms.

  preflight  per k_L: the pre-fault load flow (solve_v1ref, V1-referenced inverter) converges and every bus V1 lies
             within 0.9-1.1 pu; phi_ref by the main configuration's rule; the k_L set (3 added if 4 fails)
  static     Q1, the 16 corners of the source box at delta = 0, hard set: D0 = max(3|dI0|, |dI2|) against the
             0.162 pu pickup (0.126 as sensitivity) and D1's distance to N(0) in noise boxes (alarm > 1,
             guaranteed > 2), both tiers
  design     Q2, delta*(k_L): the fault-vs-normal set design, both tiers, rho 0.1 and 0, full polar search
             (5 deg x 0.02 pu to the 1.14 pu cap) with the separating angle set, the margin at each separating
             angle (the carried angle is the one with the largest margin), the price (delivered |I1| in normal
             operation under LIM 1) and dead frames
  spec       Q3 runs: `spec dstar <k_L> <tier>` (delta* of that tier injected) or `spec zero <k_L>`: the 48 cases and
             the normal run at the nominal source point
  analyse    Q3: `analyse dstar <k_L> <tier>` / `analyse zero <k_L>`: gates, the step-3 EMT design check (own-set
             distance, main and bare sets; separation from N), D0 and D1 on the same windows

    python src/longlines.py preflight            -> results/network/longlines_preflight.json
    python src/longlines.py static               -> results/network/longlines_static.json
    python src/longlines.py design               -> results/network/longlines_design.json
    python src/longlines.py spec dstar 2 box     -> results/network/longlines_specs_dstar2_box.json
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/network/longlines_specs_<...>.json
    python src/longlines.py analyse dstar 2 box  -> results/network/longlines_emt_dstar2_box.json
"""
import os, sys, json, time, itertools, dataclasses
import numpy as np
from scipy.optimize import linprog
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
import frames as fr
from pscad_network import three_bus, make_spec, WORK
from pscad_network_check import injections
from pscad_io import read_case
from network_delta_test import CASES, tag
from frames_emt_check import _settings
from step3_frontend import Relay, CYCLE
from step3_detectors import _d0

OUT = os.path.join(HERE, "..", "results", "network")
KL = (1, 2, 4, 8)
KL_FALLBACK = 1.5                                 # added if the set has fewer than 3 points (review, 19 Oct 2026)
P_MIN = 0.75                                      # rule B: every load keeps >= 75 % of its k_L = 1 power (V >= 0.866 x base)
VMAX = 1.1
K, SIGMA, N_MEM = 4.0, 0.01, 3                    # phi_ref rule, frames_main.py
FACTOR, DRIFT, MODEL_ERR, RHO, CAP = 1.1, 3.0, 0.008, 0.1, 1.14
PICKUP, PICKUP_LOW = 0.162, 0.126                 # highr_screen.py: D0 calibrated at the design tier, upper / lower end
TANG = 1.0 / (2 * np.pi * 15.0)
T_FAULT = 0.30
WIN = np.arange(2.0, 3.0001, 0.25)
deg = np.pi / 180
TIERS = {
    "box": dict(eps=None, instr=None),
    "structured": dict(eps=np.array([0.02] * 3 + [0.04] * 3 + [0.02] * 3 + [0.04] * 3),
                       instr=dict(N=(0.005, 0.3 * deg, 0.01, 0.3 * deg), F=(0.005, 0.3 * deg, 0.01, 0.3 * deg))),
}
TIER_LABEL = {"box": "box 0.08 (main configuration)", "structured": "structured design tier"}


# ---------------------------------------------------------------- the network and the model
def net_k(kl):
    """The step-3 three-bus network with z1, z2 and their z0 multiplied by k_L; nothing else changes."""
    base = three_bus()
    lines = {k: nw.Line(l.a, l.b, kl * l.z1, kl * l.z0) for k, l in base.lines.items()}
    return dataclasses.replace(base, lines=lines)


def phi_ref(net):
    probe = fr.FrameModel(net, CASES[:1], n_samples=400, face_pts=5, seed=2)
    v1min = float(np.min(np.abs(probe.measure(np.vstack(probe.samples), 0j, None)[:, 0])))
    return K * SIGMA / (np.sqrt(N_MEM) * v1min), v1min


def model(net, tier, phi, cases=CASES, n_samples=150, face_pts=3, seed=1):
    kw = dict(factor=FACTOR, drift_deg=DRIFT, ref_phi=phi, model_err=MODEL_ERR, instr=TIERS[tier]["instr"])
    if TIERS[tier]["eps"] is not None:
        kw["eps"] = TIERS[tier]["eps"]
    return fr.FrameModel(net, cases, n_samples=n_samples, face_pts=face_pts, seed=seed, **kw)


def scale(fm):
    return np.broadcast_to(np.asarray(fm.eps, float), (12,))


def nominal(fm):
    """The nominal sources: SG EMF and the inverter's I1 command in its own frame; its solve_v1ref settings."""
    e, ic = fm.sources(np.zeros((1, 4)))
    st = {"I": dict(ID=float(ic[0].real), IQ=float(-ic[0].imag), D2MAG=0.0, D2ANG=0.0)}
    return e[0], ic[0], st


# ---------------------------------------------------------------- pre-flight
def preflight_one(kl, base_v=None):
    """Rule B (review, 19 Oct 2026): the pre-fault load flow converges; every load keeps at least 75 % of its k_L = 1
    power (constant impedance: (V/V_1)^2 >= 0.75) and no bus exceeds 1.1 pu; the inverter frame settles at every
    phi_ref probe point; and every (case, corner) of the hard set has a settled fault frame."""
    net = net_k(kl)
    fm = fr.FrameModel(net, CASES[:1], n_samples=4, face_pts=2, seed=0)
    e0, ic, st = nominal(fm)
    res = dict(k_L=kl)
    try:
        y, inj, it = nw.solve_v1ref(net, {"G": e0}, st, None, relax=0.5, max_iter=2000)
        _, V = nw.solve(net, {"G": e0, "I": inj["I"][0]}, {}, None, full=True)
        v = {b: float(abs(V[b][0])) for b in sorted(V)}
        pr = {b: (v[b] / base_v[b]) ** 2 for b in net.loads} if base_v else {b: 1.0 for b in net.loads}
        res.update(converged=True, iterations=it, bus_v1=v, i1_delivered=float(abs(inj["I"][0])), load_power_ratio=pr,
                   v_ok=all(x >= P_MIN for x in pr.values()) and all(x <= VMAX for x in v.values()))
    except RuntimeError as ex:
        res.update(converged=False, error=str(ex), v_ok=False)
    # the frame model needs a settled inverter frame at every source-box sample point (the phi_ref probe, 2032
    # points); where even under-relaxed iteration finds none, the k_L has no model and is out
    res["frame_settles"], res["unsettled_points"] = False, None
    if res["converged"]:
        try:
            phi, v1min = phi_ref(net)
            res.update(phi_ref=float(phi), min_V1L=v1min, frame_settles=True)
        except RuntimeError as ex:
            res["frame_error"] = str(ex)
    if res["frame_settles"]:
        fmc = fr.FrameModel(net, CASES, n_samples=4, face_pts=2, seed=1)
        S = np.array(list(itertools.product((-1.0, 1.0), repeat=4)))
        e, icc = fmc.sources(S)
        _, _, u_pre = fmc.normal_state(S, 0j)
        n_bad = 0
        for k in range(len(CASES)):
            for i in range(len(S)):
                try:
                    fr.fixed_point(fmc.maps_F[k][1], e[i:i + 1], icc[i:i + 1], 0j, fmc.i_max, fmc.lim, u_pre[i:i + 1])
                except RuntimeError:
                    n_bad += 1
        res["unsettled_points"] = n_bad
    res["in_set"] = res["converged"] and res["v_ok"] and res["frame_settles"] and res["unsettled_points"] == 0
    return res


def preflight(save=True):
    base = preflight_one(1)
    rows = {1: base}
    for kl in KL[1:]:
        rows[kl] = preflight_one(kl, base["bus_v1"])
    if sum(r["in_set"] for r in rows.values()) < 3:
        rows[KL_FALLBACK] = preflight_one(KL_FALLBACK, base["bus_v1"])
    rows = dict(sorted(rows.items()))
    kls = [kl for kl, r in rows.items() if r["in_set"]]
    for kl, r in rows.items():
        if r["converged"]:
            why = "IN" if r["in_set"] else "OUT (" + ", ".join(w for w, bad in (("load power / voltage", not r["v_ok"]), ("frame does not settle", not r["frame_settles"]),
                                                                              ("unsettled fault frames", bool(r["unsettled_points"]))) if bad) + ")"
            print(f"k_L {kl}: load flow converged ({r['iterations']} it); bus |V1| " + ", ".join(f"{b} {v:.3f}" for b, v in r["bus_v1"].items())
                  + "; load P/P1 " + ", ".join(f"{b} {x:.3f}" for b, x in r["load_power_ratio"].items())
                  + f"; inverter |I1| {r['i1_delivered']:.3f} pu; unsettled (case, corner) points {r['unsettled_points']}; {why}"
                  + (f"; phi_ref {r['phi_ref']:.4f} rad (min |V1_L| {r['min_V1L']:.3f})" if r["frame_settles"] else f"; {r['frame_error']}"), flush=True)
        else:
            print(f"k_L {kl}: load flow did not converge: {r['error']}; OUT", flush=True)
    print(f"k_L set: {kls}")
    out = dict(rule="B: load power >= 75 % of k_L 1, V <= 1.1, solve_v1ref converges, frame settles on the probe and at every (case, corner)",
               rows={str(k): v for k, v in rows.items()}, k_L_set=kls)
    if save:
        json.dump(out, open(os.path.join(OUT, "longlines_preflight.json"), "w"), indent=1)
        print("-> results/network/longlines_preflight.json")
    return out


def kl_set():
    p = os.path.join(OUT, "longlines_preflight.json")
    pf = json.load(open(p)) if os.path.exists(p) else preflight()
    return pf["k_L_set"], {float(k): v for k, v in pf["rows"].items()}


def kl_tag(kl):
    return str(kl).replace(".", "p")


# ---------------------------------------------------------------- Q1: static, 16 corners, delta = 0
def static():
    kls, rows = kl_set()
    out_name = "longlines_static.json"
    if "--all" in sys.argv:                       # every k_L with a model, for information, whatever the voltage window says
        kls = [kl for kl in sorted(rows) if rows[kl]["converged"] and rows[kl]["frame_settles"]]
        out_name = "longlines_static_all.json"    # its own file: the registered set's file is never overwritten
    S = np.array(list(itertools.product((-1.0, 1.0), repeat=4)))
    out = {}
    for kl in kls:
        t0 = time.time()
        net, phi = net_k(kl), rows[kl]["phi_ref"]
        res = dict(k_L=kl, phi_ref=phi, cases=[])
        fms = {t: model(net, t, phi) for t in TIERS}
        yN = fms["box"].measure(S, 0j, None)                     # the measurement does not depend on the tier
        pieces = {t: fms[t].zonotopes(0j, None) for t in TIERS}
        for k, c in enumerate(CASES):
            # corners where the inverter's fault frame has no fixed point even under-relaxed (longer lines) are
            # counted and left out of this case's corner statistics; a case with such corners is flagged
            yF, settled = [], []
            for i in range(len(S)):
                try:
                    yF.append(fms["box"].measure(S[i:i + 1], 0j, k)[0])
                    settled.append(True)
                except RuntimeError:
                    settled.append(False)
            settled = np.array(settled)
            if not settled.any():
                res["cases"].append(dict(case=list(c), unsettled_corners=16, d0_worst=None, d0_missed=None))
                continue
            yF, yNs = np.array(yF), yN[settled]
            d0 = np.maximum(3 * np.abs(yF[:, 5] - yNs[:, 5]), np.abs(yF[:, 4] - yNs[:, 4]))
            row = dict(case=list(c), unsettled_corners=int((~settled).sum()), d0_worst=float(d0.min()), d0_nominal=None,
                       d0_missed=bool(d0.min() < PICKUP), d0_missed_low=bool(d0.min() < PICKUP_LOW))
            for t in TIERS:
                dist = np.array([fr.distance_to_set(pieces[t], yF[i], scale(fms[t])) for i in range(len(yF))])
                row[f"d1_{t}_min_boxes"] = float(dist.min())
                row[f"d1_{t}_alarm_missed"] = bool(dist.min() <= 1.0)
                row[f"d1_{t}_guaranteed_missed"] = bool(dist.min() <= 2.0)
            res["cases"].append(row)
        yNn, yFn = fms["box"].measure(np.zeros((1, 4)), 0j, None)[0], None
        for k, row in enumerate(res["cases"]):
            yFn = fms["box"].measure(np.zeros((1, 4)), 0j, k)[0]
            row["d0_nominal"] = float(max(3 * abs(yFn[5] - yNn[5]), abs(yFn[4] - yNn[4])))
        n = len(CASES)
        cnt = lambda key: sum(bool(r.get(key)) for r in res["cases"])
        res["summary"] = dict(
            d0_missed=cnt("d0_missed"), d0_missed_low=cnt("d0_missed_low"),
            d0_missed_cases=[r["case"] for r in res["cases"] if r.get("d0_missed")],
            **{f"d1_{t}_{w}_missed": cnt(f"d1_{t}_{w}_missed") for t in TIERS for w in ("alarm", "guaranteed")},
            unsettled_points=sum(r["unsettled_corners"] for r in res["cases"]),
            unsettled_cases=[r["case"] for r in res["cases"] if r["unsettled_corners"]],
            d0_quarter=cnt("d0_missed") >= n / 4, n=n, seconds=time.time() - t0)
        s = res["summary"]
        print(f"k_L {kl}: D0 missed {s['d0_missed']} of {n} at {PICKUP} pu ({s['d0_missed_low']} at {PICKUP_LOW}); "
              f"D1 missed (alarm / guaranteed) box {s['d1_box_alarm_missed']} / {s['d1_box_guaranteed_missed']}, structured "
              f"{s['d1_structured_alarm_missed']} / {s['d1_structured_guaranteed_missed']}; D0 >= 1/4: {s['d0_quarter']}; "
              f"corner points with no settled fault frame {s['unsettled_points']} of {16 * n} in {len(s['unsettled_cases'])} cases  [{s['seconds']:.0f} s]", flush=True)
        if s["d0_missed_cases"]:
            print("   D0 missed: " + ", ".join(tag(tuple(c)) for c in s["d0_missed_cases"]), flush=True)
        out[str(kl)] = res
        json.dump(dict(pickup=PICKUP, pickup_low=PICKUP_LOW, k_L_set=kls, results=out,
                       **(dict(note="--all: every k_L with a model, for information; k_L outside the pre-flight set "
                                    "{1, 1.5, 2} are not results") if "--all" in sys.argv else {})),
                  open(os.path.join(OUT, out_name), "w"), indent=1)
    print(f"-> results/network/{out_name}")


# ---------------------------------------------------------------- Q2: delta*(k_L)
def gap(cA, GA, cB, GB, w):
    """The smallest weighted infinity-norm distance between two zonotopes, in units of w per component."""
    n, ka, kb = cA.size, GA.shape[1], GB.shape[1]
    c = np.zeros(ka + kb + n + 1)
    c[-1] = 1
    A_eq = np.hstack([GA, -GB, np.eye(n), np.zeros((n, 1))])
    W = w.reshape(n, 1)
    A_ub = np.vstack([np.hstack([np.zeros((n, ka + kb)), np.eye(n), -W]), np.hstack([np.zeros((n, ka + kb)), -np.eye(n), -W])])
    res = linprog(c, A_ub=A_ub, b_ub=np.zeros(2 * n), A_eq=A_eq, b_eq=cB - cA,
                  bounds=[(-1, 1)] * (ka + kb) + [(None, None)] * n + [(0, None)], method="highs")
    assert res.status == 0, res.message
    return float(res.x[-1])


def margin(fm, d, rho):
    """The smallest fault-vs-normal gap at d minus 2 (1 + rho), in eps units, and the binding case."""
    w = scale(fm)
    Ns = fm.zonotopes(d, None)
    best = (np.inf, None)
    for k in range(len(fm.cases)):
        g = min(gap(cN, GN, cF, GF, w) for cN, GN in Ns for cF, GF in fm.zonotopes(d, k))
        if g < best[0]:
            best = (g, fm.cases[k])
    fm._cache.clear()
    return dict(gap_eps=best[0], margin_eps=best[0] - 2 * (1 + rho), case=list(best[1]))


def price(fm, d):
    """Delivered |I1| in normal operation under LIM 1 at d: at the nominal point and over the sample set."""
    S = np.vstack(fm.samples)
    for name, SS in (("nominal", np.zeros((1, 4))), ("samples", S)):
        e, ic = fm.sources(SS)
        _, _, u = fm.normal_state(SS, d)
        i1, _ = fr.limiter_vec(ic * u, d * u, fm.i_max, 1)
        if name == "nominal":
            nom = float(abs(i1[0])), float(abs(ic[0]))
        else:
            rng = [float(np.abs(i1).min()), float(np.median(np.abs(i1))), float(np.abs(i1).max())]
    return dict(nominal_delivered=nom[0], nominal_command=nom[1], samples_min_median_max=rng)


def apart(fm, d, rho, state, skipped):
    """frames.separated_fast with the case that met N last checked first at the next candidate (the binding case
    changes slowly with the angle). The test per case and the all-cases requirement are unchanged, so the result at
    every candidate, hence delta* and the separating angle set, is identical; only the time to a False changes."""
    try:
        Ns = fm.zonotopes(d, None)
    except RuntimeError:
        skipped.append(complex(d))
        return False
    b = 2 * fm.eps * (1 + rho)
    for k in list(state["order"]):
        try:
            Fs = fm.zonotopes(d, k)
        except RuntimeError:
            skipped.append(complex(d))
            return False
        if fr._meet_union(Ns, Fs, b):
            state["order"].remove(k)
            state["order"].insert(0, k)
            return False
    return True


_W = {}


def _w_init(kl, tier, phi, order):
    """Worker: its own copy of the frame model (Windows spawns processes) and its own case order, hardest first."""
    import warnings
    warnings.filterwarnings("ignore")
    fm = model(net_k(kl), tier, phi)
    _W.update(fm=fm, state={"order": list(order)})


def _w_eval(args):
    """One candidate: (r, a, rho) -> (a, separates, inadmissible). The candidates are independent, so splitting the
    72 angles of a radius over processes gives the same answer at every one of them."""
    r, a, rho = args
    skipped = []
    ok = apart(_W["fm"], r * np.exp(1j * np.radians(a)), rho, _W["state"], skipped)
    _W["fm"]._cache.clear()
    return a, ok, bool(skipped)


WORKERS = 6


def design(redo=None):
    """redo: 'k_L|tier|rho' recomputes that key without saving and prints it beside the stored one (a check that
    the reordered search reproduces the stored result)."""
    kls, rows = kl_set()
    path = os.path.join(OUT, "longlines_design.json")
    out = json.load(open(path)) if os.path.exists(path) else {}
    for kl in kls:
        net, phi = net_k(kl), rows[kl]["phi_ref"]
        for tier in TIERS:
            fm = None
            for rho in (RHO, 0.0):
                key = f"{kl}|{tier}|{rho}"
                if redo is not None and key != redo:
                    continue
                if key in out and redo is None:
                    continue
                fm = fm or model(net, tier, phi)
                t0 = time.time()
                hard = [tuple(c) for c in fr.unseparated(fm, 0j, rho)]
                res = dict(k_L=kl, tier=tier, rho=rho, phi_ref=phi, unseparated_at_0=len(hard), unseparated_cases=[list(c) for c in hard])
                print(f"[k_L {kl}, {tier}] rho {rho}: cases not separated from normal at delta = 0: {len(hard)} of {len(CASES)}  [{time.time() - t0:.0f} s]", flush=True)
                if not hard:
                    res.update(abs_delta=0.0, separating_angles_deg=list(range(0, 360, 5)), feasible=True, inadmissible=0,
                               margin=margin(fm, 0j, rho), price=price(fm, 0j), dead_frames=[], carried_angle_deg=None)
                else:
                    order = [k for k, c in enumerate(fm.cases) if tuple(c) in hard] + [k for k, c in enumerate(fm.cases) if tuple(c) not in hard]
                    found, angles, n_inadm = None, [], 0
                    from concurrent.futures import ProcessPoolExecutor
                    with ProcessPoolExecutor(WORKERS, initializer=_w_init, initargs=(kl, tier, phi, order)) as pool:
                        for r in np.arange(0.02, CAP + 1e-9, 0.02):
                            res_r = list(pool.map(_w_eval, [(float(r), a, rho) for a in range(0, 360, 5)]))
                            n_inadm += sum(x[2] for x in res_r)
                            ok = [a for a, good, _ in res_r if good]
                            if ok:
                                found, angles = float(round(r, 4)), ok
                                break
                    res.update(abs_delta=found, separating_angles_deg=angles, feasible=found is not None, inadmissible=n_inadm)
                    if found is not None:
                        ms = {a: margin(fm, found * np.exp(1j * np.radians(a)), rho) for a in angles}
                        a_star = max(ms, key=lambda a: ms[a]["margin_eps"])
                        d = found * np.exp(1j * np.radians(a_star))
                        res.update(margins_by_angle={str(a): m for a, m in ms.items()}, carried_angle_deg=a_star, margin=ms[a_star],
                                   price=price(fm, d), dead_frames=[list(c) for c in fm.dead_frames(d)])
                res["seconds"] = time.time() - t0
                if redo is not None:
                    old = out.get(key, {})
                    same = old.get("abs_delta") == res["abs_delta"] and old.get("separating_angles_deg") == res["separating_angles_deg"]
                    print(f"REDO {key}: stored delta* {old.get('abs_delta')} angles {old.get('separating_angles_deg')} | recomputed delta* {res['abs_delta']} "
                          f"angles {res['separating_angles_deg']} | {'IDENTICAL' if same else 'DIFFERENT'}  [{res['seconds']:.0f} s vs {old.get('seconds', 0):.0f} s]", flush=True)
                    return
                out[key] = res
                json.dump(out, open(path, "w"), indent=1)
                if res["feasible"]:
                    print(f"[k_L {kl}, {tier}] rho {rho}: delta* {res['abs_delta']} pu; separating angles {res['separating_angles_deg']}; "
                          f"carried {res['carried_angle_deg']} deg, margin {res['margin']['margin_eps']:.3f} eps ({res['margin']['case']}); "
                          f"price: |I1| {res['price']['nominal_delivered']:.3f} of {res['price']['nominal_command']:.3f} pu at the nominal point; "
                          f"dead frames {len(res['dead_frames'])}; inadmissible {res['inadmissible']}  [{res['seconds']:.0f} s]", flush=True)
                else:
                    print(f"[k_L {kl}, {tier}] rho {rho}: no delta within the {CAP} pu cap separates; inadmissible {res['inadmissible']}  [{res['seconds']:.0f} s]", flush=True)
    print(f"-> {os.path.relpath(path)}")


# ---------------------------------------------------------------- Q3: EMT
def carried(kl, tier):
    d = json.load(open(os.path.join(OUT, "longlines_design.json")))[f"{kl}|{tier}|{RHO}"]
    assert d["feasible"] and d["abs_delta"] > 0, f"no non-zero delta* at k_L {kl}, {tier}"
    return d["abs_delta"] * np.exp(1j * np.radians(d["carried_angle_deg"]))


def spec_path(half, kl, tier=None):
    return os.path.join(OUT, f"longlines_specs_{half}{kl}" + (f"_{tier}" if tier else "") + ".json")


def make(half, kl, tier=None):
    net = net_k(kl)
    fm = fr.FrameModel(net, CASES[:1], n_samples=4, face_pts=2, seed=0)
    e0, ic, _ = nominal(fm)
    d = carried(kl, tier) if half == "dstar" else 0j
    specs = []
    for c in [None] + list(CASES):
        fault = None if c is None else (c[0], c[1], c[2], c[3] * net.rF)
        name = f"ll{kl_tag(kl)}{'' if half == 'zero' else tier[0]}_" + ("N" if c is None else tag(c))
        sp = make_spec(name, net, fault, {"G": e0}, {}, 1)
        sp["settings"] = _settings(ic, d)
        sp["settings"]["I"]["TANG"] = TANG
        sp["key_extra"] = f"kL{kl_tag(kl)}"           # a different line impedance needs its own built project
        sp.update(kind="normal" if c is None else "fault", case=None if c is None else list(c), k_L=kl, half=half,
                  tier=tier, d_cmd=[d.real, d.imag])
        specs.append(sp)
    json.dump(specs, open(spec_path(half, kl, tier), "w"), indent=1)
    print(f"{len(specs)} runs, k_L {kl}, {half}" + (f" ({tier}: {abs(d):.3f} pu @ {np.degrees(np.angle(d)) % 360:.0f} deg)" if half == "dstar" else "")
          + f" -> {os.path.relpath(spec_path(half, kl, tier))}")


def numerically_clean(run):
    tt, fs = np.asarray(run["t"]), run["fs"]
    v = np.asarray(run["ch"]["VLA"])
    nm = np.abs(v[(tt > 0.2) & (tt < 0.29)]).max()
    seg = v[(tt >= 0.30) & (tt < 0.40)]
    f = np.fft.rfftfreq(len(seg), 1 / fs)
    P = np.abs(np.fft.rfft((seg - seg.mean()) * np.hanning(len(seg)))) ** 2
    pk, hf = float(np.abs(seg).max() / nm), float(P[(f >= 5000) & (f <= 10000)].sum() / P.sum())
    return pk <= 2.0 and hf <= 1e-3, pk, hf


def v1m(run, name, t):
    x = np.asarray(run["ch"].get(f"V1M_{name}", []))
    return float(x[int(round((t - float(run["t"][0])) * run["fs"]))]) if len(x) else None


def analyse(half, kl, tier=None):
    specs = json.load(open(spec_path(half, kl, tier)))
    _, rows = kl_set()
    net, phi = net_k(kl), rows[kl]["phi_ref"]
    d = complex(*specs[0]["d_cmd"])
    tiers = [tier] if half == "dstar" else list(TIERS)
    fms = {t: model(net, t, phi) for t in tiers}
    bare = {t: fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, eps=TIERS[t]["eps"], factor=1.0, drift_deg=DRIFT,
                             ref_phi=0.0, model_err=0.0) if TIERS[t]["eps"] is not None else
            fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, factor=1.0, drift_deg=DRIFT, ref_phi=0.0, model_err=0.0)
            for t in tiers}
    e0, ic, st = nominal(fms[tiers[0]])
    st["I"].update(D2MAG=float(abs(d)), D2ANG=float(np.degrees(np.angle(d))) if abs(d) else 0.0)
    out = dict(half=half, k_L=kl, tier=tier, d_cmd=[d.real, d.imag])
    # pre-fault gate
    spn = [x for x in specs if x["kind"] == "normal"][0]
    run = read_case(os.path.join(WORK, spn["name"] + ".gf46"), spn["name"])
    i25, i28 = injections(run, spn, 0.25), injections(run, spn, 0.28)
    _, inj_st, _ = nw.solve_v1ref(net, {"G": e0}, st, None, relax=0.5, max_iter=2000)
    gate = {}
    for q, lab in ((0, "I1"), (1, "delta")):
        ref = abs(inj_st["I"][q])
        if ref < 0.02:
            continue
        gate[lab] = dict(emt=abs(i28["I"][q]), static=ref, err=abs(abs(i28["I"][q]) / ref - 1),
                         settled=abs(abs(i28["I"][q]) / max(abs(i25["I"][q]), 1e-9) - 1))
    passed = all(g["err"] <= 0.03 and g["settled"] <= 0.03 for g in gate.values())
    out["gate"] = dict(checks=gate, passed=passed)
    print(f"[{half} k_L {kl}{' ' + tier if tier else ''}] pre-fault: " + ", ".join(f"{k} {g['emt']:.3f}/{g['static']:.3f} ({g['err']:.1%}, {g['settled']:.1%})" for k, g in gate.items())
          + f"; gate {'PASSED' if passed else 'FAILED: results not interpreted'}", flush=True)
    N = {t: fms[t].zonotopes(d, None) for t in tiers}
    Z = {t: {} for t in tiers}
    rrows = []
    for sp in [x for x in specs if x["kind"] == "fault"]:
        c = tuple(sp["case"])
        k = CASES.index(c)
        run = read_case(os.path.join(WORK, sp["name"] + ".gf46"), sp["name"])
        ok, pk, hf = numerically_clean(run)
        rel = Relay(sp["name"], tier="clean")
        inc = rel.idx(T_FAULT)
        row = dict(name=sp["name"], case=list(c), clean=ok, peak=pk, hf=hf, weak_frame=False)
        v = v1m(run, "I", T_FAULT + 2.5 / 60)
        row["v1_I"] = v
        row["weak_frame"] = v is not None and v < 0.2
        for t in tiers:
            w = scale(fms[t])
            own_m = fms[t].zonotopes(d, k)
            own_b = bare[t].zonotopes(d, k)
            win = []
            for cyc, y in rel.windows(inc):
                om, ob = fr.distance_to_set(own_m, y, w), fr.distance_to_set(own_b, y, w)
                dn = fr.distance_to_set(N[t], y, w)
                win.append(dict(cycles=float(cyc), own_main=float(om), own_bare=float(ob), to_N=float(dn),
                                separated=bool(dn > 2 * (1 + RHO) - om)))
            row[t] = dict(windows=win, contained=all(x["own_main"] <= 0.1 for x in win), model_err_bare=max(x["own_bare"] for x in win),
                          separated=all(x["separated"] for x in win), to_N_min=min(x["to_N"] for x in win))
            fms[t]._cache.clear(); bare[t]._cache.clear()
        row["d0_clean"] = float(_d0(rel, inc, 2.0, 3.0))
        reld = Relay(sp["name"], tier="design", seed=7)
        row["d0_design"] = float(_d0(reld, reld.idx(T_FAULT), 2.0, 3.0))
        rrows.append(row)
    q = [r for r in rrows if r["clean"]]
    summ = dict(n=len(q), of=len(rrows), weak_frame=[r["name"] for r in q if r["weak_frame"]],
                d0_missed_clean=sum(r["d0_clean"] < PICKUP for r in q), d0_missed_design=sum(r["d0_design"] < PICKUP for r in q),
                d0_missed_clean_cases=[r["case"] for r in q if r["d0_clean"] < PICKUP])
    for t in tiers:
        summ[t] = dict(contained=sum(r[t]["contained"] for r in q), separated=sum(r[t]["separated"] for r in q),
                       model_err_bare_max=max(r[t]["model_err_bare"] for r in q), to_N_min=min(r[t]["to_N_min"] for r in q),
                       d1_alarm_missed=sum(r[t]["to_N_min"] <= 1.0 for r in q), d1_guaranteed_missed=sum(r[t]["to_N_min"] <= 2.0 for r in q),
                       weak=[dict(name=r["name"], contained=r[t]["contained"], separated=r[t]["separated"]) for r in q if r["weak_frame"]])
        s = summ[t]
        print(f"[{half} k_L {kl}, {t}] {len(q)} of {len(rrows)} clean | contained (main, <= 0.1 eps) {s['contained']}, separated {s['separated']}, "
              f"nearest N {s['to_N_min']:.2f} eps; bare-set model error max {s['model_err_bare_max']:.3f} eps | D1 missed alarm / guaranteed "
              f"{s['d1_alarm_missed']} / {s['d1_guaranteed_missed']}", flush=True)
    print(f"[{half} k_L {kl}] D0 at {PICKUP} pu missed: clean {summ['d0_missed_clean']}, design tier {summ['d0_missed_design']} of {len(q)}; "
          f"weak frame {len(summ['weak_frame'])}", flush=True)
    out.update(summary=summ, rows=rrows)
    p = os.path.join(OUT, f"longlines_emt_{half}{kl}" + (f"_{tier}" if tier else "") + ".json")
    json.dump(out, open(p, "w"), indent=1, default=str)
    print(f"-> {os.path.relpath(p)}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "preflight":
        preflight()
    elif cmd == "static":
        static()
    elif cmd == "design":
        design(redo=sys.argv[sys.argv.index("--redo") + 1] if "--redo" in sys.argv else None)
    elif cmd in ("spec", "analyse"):
        half, kl = sys.argv[2], float(sys.argv[3])
        kl = int(kl) if kl == int(kl) else kl
        tier = sys.argv[4] if half == "dstar" else None
        (make if cmd == "spec" else analyse)(half, kl, tier)
