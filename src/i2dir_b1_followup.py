"""
Stage (b1) follow-ups asked for in review, before (b2) is registered (docs/I2_DIRECTION.md):

  emt0    (b0): the set test at delta = 0 on the existing shunt-bracket MODE2 0 EMT runs (i2s_m0_*, nominal source
          point). For each fault run, decision windows ending 2 to 3 cycles after inception in the relay's memory
          frame: the distance to its own case set and the smallest distance to any opposite-side case set, in eps
          units. Separated by the test if the opposite-side distance exceeds 2 (1 + rho) minus the own-set distance.
  patch   the box tier's design point's neighbourhood at 1 deg x 0.01 pu (195-215 deg, 0.94-1.08 pu, rho 0.1): which
          points separate every forward-reverse pair; and at each tier's carried point, the smallest margin
          (forward-reverse gap minus 2 eps (1 + rho)), in pu and in eps units
  state   the operating state at the carried points: delivered |I1| (normal and fault) and the smallest |V1| at
          bus R (I, SR) and bus S (SS) per case over the sample set

    python src/i2dir_b1_followup.py emt0    -> results/network/i2dir_b0_emt.json
    python src/i2dir_b1_followup.py patch   -> results/network/i2dir_b1_patch.json
    python src/i2dir_b1_followup.py state   -> results/network/i2dir_b1_state.json
"""
import os, sys, json, time
import numpy as np
from scipy.optimize import linprog
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
import frames as fr
from frames_multi import FrameModelMulti
from network_delta_test import tag
from step3_frontend import Relay
from i2dir_design import KW, U0, TIERS
from i2dir_static import network_s, network, operating_point, FWD, REV
from i2dir_emt import T_FAULT

OUT = os.path.join(HERE, "..", "results", "network")
CASES = FWD + REV
A, B = list(range(len(FWD))), list(range(len(FWD), len(CASES)))
POINTS = {"box 0.08": 0.98 * np.exp(1j * np.radians(205)), "structured design tier": 0.20 * np.exp(1j * np.radians(230))}


def build(tier):
    net = network_s(1.0, 1e6, filters=True, inject=True)
    _, st = operating_point(1.0, 1e6, U0)
    sinks = {k: complex(v["ID"], -v["IQ"]) for k, v in st.items() if k != "I"}
    kw = dict(KW)
    if TIERS[tier]["eps"] is not None:
        kw["eps"] = TIERS[tier]["eps"]
    return FrameModelMulti(net, CASES, sinks=sinks, base_net=network(1e6, 1.0), n_samples=150, face_pts=3, seed=1,
                           instr=TIERS[tier]["instr"], **kw)


def scale(fm):
    return np.broadcast_to(np.asarray(fm.eps, float), (12,))


def emt0():
    out = {}
    for tier in TIERS:
        fm = build(tier)
        w = scale(fm)
        Z = {k: fm.zonotopes(0j, k) for k in range(len(CASES))}
        rows = []
        for k, c in enumerate(CASES):
            name = "i2s_m0_" + tag(c)
            rel = Relay(name, tier="clean")
            opp = B if k in A else A
            for cyc, y in rel.windows(rel.idx(T_FAULT)):
                own = fr.distance_to_set(Z[k], y, w)
                d_opp = [fr.distance_to_set(Z[j], y, w) for j in opp]
                j = int(np.argmin(d_opp))
                rows.append(dict(case=list(c), side="forward" if k in A else "reverse", cycles=float(cyc),
                                 own_eps=float(own), opp_min_eps=float(d_opp[j]), opp_closest=list(CASES[opp[j]])))
        res = {}
        for rho in (0.1, 0.0):
            for ft in ("bc", "ag"):
                q = [r for r in rows if r["case"][2] == ("ab" if ft == "bc" else "ag")]
                sep = [r["opp_min_eps"] > 2 * (1 + rho) - r["own_eps"] for r in q]
                closer = [r["opp_min_eps"] > r["own_eps"] for r in q]
                res[f"rho {rho} {ft}"] = dict(windows=len(q), runs=len({tuple(r['case']) for r in q}),
                                              separated=int(sum(sep)), own_closer=int(sum(closer)),
                                              own_max_eps=float(max(r["own_eps"] for r in q)),
                                              opp_min_eps=float(min(r["opp_min_eps"] for r in q)))
                print(f"[{tier}] rho {rho} {ft.upper()}: {res[f'rho {rho} {ft}']}", flush=True)
        out[tier] = dict(summary=res, rows=rows)
    json.dump(out, open(os.path.join(OUT, "i2dir_b0_emt.json"), "w"), indent=1)
    print("-> results/network/i2dir_b0_emt.json")


def gap(cA, GA, cB, GB, w):
    """The smallest weighted infinity-norm distance between two zonotopes (in units of w per component)."""
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
    w = scale(fm)
    Z = {k: fm.zonotopes(d, k) for k in range(len(CASES))}
    best = (np.inf, None)
    for i in A:
        for j in B:
            g = min(gap(cA, GA, cB, GB, w) for cA, GA in Z[i] for cB, GB in Z[j])
            if g < best[0]:
                best = (g, (CASES[i], CASES[j]))
    g, pair = best
    return dict(gap_eps=g, margin_eps=g - 2 * (1 + rho), margin_pu=(g - 2 * (1 + rho)) * float(w.min()), pair=[list(p) for p in pair])


def patch():
    out = {}
    fm = build("box 0.08")
    b = 2 * fm.eps * (1 + 0.1)
    grid = []
    t0 = time.time()
    last = [None]

    def apart(d):
        pairs = [(i, j) for i in A for j in B]
        if last[0] in pairs:
            pairs.remove(last[0])
            pairs.insert(0, last[0])
        for i, j in pairs:
            if fr._meet_union(fm.zonotopes(d, i), fm.zonotopes(d, j), b):
                last[0] = (i, j)
                return False
        return True

    for r in np.round(np.arange(0.94, 1.08 + 1e-9, 0.01), 2):
        ok = []
        for a in range(195, 216):
            if apart(r * np.exp(1j * np.radians(a))):
                ok.append(a)
            fm._cache.clear()                   # one set of zonotopes per delta: the cache would grow without bound
        grid.append(dict(abs_delta=float(r), separating_angles_deg=ok))
        print(f"|delta| {r:.2f} pu: separating angles {ok}  [{time.time() - t0:.0f} s]", flush=True)
    out["box_patch_rho_0.1"] = grid
    feas = [(g["abs_delta"], a) for g in grid for a in g["separating_angles_deg"]]
    out["box_patch_points"] = len(feas)
    if feas:
        rs, angs = zip(*feas)
        centre = (float(np.mean(rs)), float(np.mean(angs)))
        out["box_patch_centre"] = centre
        print(f"feasible patch: {len(feas)} grid points, |delta| {min(rs):.2f}-{max(rs):.2f} pu, {min(angs)}-{max(angs)} deg; "
              f"centroid {centre[0]:.3f} pu at {centre[1]:.1f} deg", flush=True)
    for tier, d in POINTS.items():
        fm_t = fm if tier == "box 0.08" else build(tier)
        m = margin(fm_t, d, 0.1)
        out[f"margin {tier}"] = dict(abs_delta=abs(d), angle_deg=float(np.degrees(np.angle(d))) % 360, **m)
        print(f"[{tier}] margin at {abs(d):.2f} pu {np.degrees(np.angle(d)) % 360:.0f} deg, rho 0.1: {m}", flush=True)
    json.dump(out, open(os.path.join(OUT, "i2dir_b1_patch.json"), "w"), indent=1)
    print("-> results/network/i2dir_b1_patch.json")


def state():
    fm = build("box 0.08")                     # the operating state does not depend on the noise tier
    S = np.vstack(fm.samples)
    e, ic = fm.sources(S)
    bus = {k: fm.net.ibrs[k].bus for k in [fm.inj] + list(fm.sinks)}
    out = {}
    for tier, d in POINTS.items():
        _, _, u_pre = fm.normal_state(S, d)
        X, i1, _ = fm._x(e, ic, d, u_pre)
        res = dict(abs_delta=abs(d), angle_deg=float(np.degrees(np.angle(d))) % 360,
                   i1_normal=[float(np.abs(i1).min()), float(np.abs(i1).max())], cases=[])
        i1f = []
        for k, c in enumerate(CASES):
            u_f, _, _ = fm._fixed(fm.maps_F[k][1], e, ic, d, u_pre)
            _, i1k, _ = fm._x(e, ic, d, u_f)
            i1f.append(np.abs(i1k))
            v = {name: float(fm._v1_last[name].min()) for name in fm._v1_last}
            res["cases"].append(dict(case=list(c), v1_min_by_source=v, v1R_min=min(v[n] for n in v if bus[n] == bus[fm.inj])))
        i1f = np.concatenate(i1f)
        res["i1_fault"] = [float(i1f.min()), float(i1f.max())]
        low = [r for r in res["cases"] if r["v1R_min"] < 0.2]
        res["v1R_below_0.2"] = [r["case"] for r in low]
        vS = min(r["v1_min_by_source"][n] for r in res["cases"] for n in r["v1_min_by_source"] if bus[n] != bus[fm.inj])
        res["v1R_min_overall"] = min(r["v1R_min"] for r in res["cases"])
        res["v1S_min_overall"] = vS
        out[tier] = res
        print(f"[{tier}] {abs(d):.2f} pu at {res['angle_deg']:.0f} deg: delivered |I1| normal {res['i1_normal'][0]:.3f}-{res['i1_normal'][1]:.3f}, "
              f"fault {res['i1_fault'][0]:.3f}-{res['i1_fault'][1]:.3f} pu; smallest |V1| at R {res['v1R_min_overall']:.3f}, at S {vS:.3f} pu; "
              f"cases with |V1_R| < 0.2: {len(low)} {[tuple(r['case']) for r in low]}", flush=True)
    json.dump(out, open(os.path.join(OUT, "i2dir_b1_state.json"), "w"), indent=1)
    print("-> results/network/i2dir_b1_state.json")


if __name__ == "__main__":
    {"emt0": emt0, "patch": patch, "state": state}[sys.argv[1]]()
