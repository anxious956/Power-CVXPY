"""
Direction at the inverter's relay with an I2-suppressing inverter: the static stages (a) and (b) of docs/I2_DIRECTION.md.

  a   the conventional element ("dY2 when enabled, else dY1", Opoku et al. 2025, as src/review/i2_suppressed_direction.py)
      on forward (L1) and reverse (L2) faults at the 16 corners of the source box, delta = 0, for the inverter's
      negative-sequence laws: suppressed (open path) and IEEE 2800 (I2 = j 2 V2, a shunt j / 2)
  b   the design for direction: the smallest delta (suppressed inverter, delta in its V1 frame, two-frame model, main
      configuration) for which every forward case's set and every reverse case's set are 2 eps (1 + rho) apart

The relay is at bus R on L1, looking towards L (the relay next to the inverter).

    python src/i2dir_static.py a              -> results/network/i2dir_static_a.json
    python src/i2dir_static.py b [rho ...]    -> results/network/i2dir_static_b.json
"""
import os, sys, json, time, dataclasses, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network as nw
import zone_model as zm

OUT = os.path.join(HERE, "..", "results", "network")
L1_M = (0.15, 0.35, 0.55, 0.75, 0.95)
L2_M = (0.05, 0.25, 0.5, 0.75, 0.95)
HARD_AG = (0.5, 0.75, 1.0)                     # R_f / rF: 20-40 ohm
ARC_BC = (0.0, 0.125)                          # 0 and 5 ohm
FWD = [("L1", m, "ag", r) for m in L1_M for r in HARD_AG] + [("L1", m, "ab", r) for m in L1_M for r in ARC_BC]
REV = [("L2", m, "ag", r) for m in L2_M for r in HARD_AG] + [("L2", m, "ab", r) for m in L2_M for r in ARC_BC]
PHI, I2_I1_MIN, DV1_MIN = 45.0, 0.1, 0.05


def network(neg_z=1e6, k=1.0):
    """k: the negative-sequence share of the loads behind the relay (R and S), y2 = k y1 with y1 unchanged
    (docs/I2_DIRECTION.md, stage a'): 1 a passive constant-impedance load, 0 an inverter-interfaced load."""
    p = zm.ZoneParams()
    loads = {b: {1: y[1], 2: k * y[1], 0: y[0]} for b, y in (("R", p.yR), ("S", p.yS))}
    return nw.Network(lines={"L1": nw.Line("L", "R", p.z1, p.z0_ratio * p.z1), "L2": nw.Line("R", "S", p.z2, p.z0_ratio * p.z2)},
                      sgs={"G": nw.SG("L", dict(p.zs), p.e0)},
                      ibrs={"I": nw.IBR("R", p.i0, (0.3, 0.3), neg_z, 1e6, inject=True, i_max=1.2)},
                      loads=loads, relay=("L1", "b"), eps=0.08, rF=p.rF)


def direction(yN, y):
    """'f', 'r' or None (no decision): dY2 when enabled (incremental: |dI2| >= 0.1 |dI1|), else dY1 (|dV1| >= 5 %)."""
    en2 = abs(y[4] - yN[4]) >= I2_I1_MIN * abs(y[3] - yN[3])
    for k_i, k_v, ok in ((4, 1, en2), (3, 0, abs(y[0] - yN[0]) >= DV1_MIN)):
        dI, dV = y[k_i] - yN[k_i], y[k_v] - yN[k_v]
        if ok and abs(dV) > 1e-9 and abs(dI) > 1e-9:
            ang = np.degrees(np.angle(dI / dV)) % 360
            return "f" if PHI < ang < 180 + PHI else "r"
    return None


def stage_a(ks=(1.0, 0.5, 0.2, 0.0)):
    out = {}
    for law, neg_z, k in [(l, z, k) for k in ks for l, z in (("suppressed", 1e6), ("IEEE 2800 (K2 = 2)", 0.5j))]:
        net = network(neg_z, k)
        corners = list(itertools.product((-1, 1), repeat=2 * len(net.sources)))
        res = {}
        for side, cases, want in (("forward", FWD, "f"), ("reverse", REV, "r")):
            wrong, none, n = 0, 0, 0
            by_type = {}
            for c in cases:
                for u in corners:
                    v = nw.realisation(net, u)
                    yN = nw.solve(net, v)
                    y = nw.solve(net, v, fault=(c[0], c[1], c[2], c[3] * net.rF))
                    dcs = direction(yN, y)
                    n += 1
                    bad = dcs != want
                    wrong += bad
                    none += dcs is None
                    t = by_type.setdefault(c[2], [0, 0])
                    t[0] += bad
                    t[1] += 1
            res[side] = dict(n=n, misdirected=wrong / n, no_decision=none / n,
                             by_type={k: v[0] / v[1] for k, v in by_type.items()})
            print(f"k {k:.1f} {law:20s} {side:8s}: misdirected or undecided {wrong / n:.2f} (no decision {none / n:.2f}); by type "
                  + ", ".join(f"{k} {v[0] / v[1]:.2f}" for k, v in by_type.items()), flush=True)
        out[f"k={k}|{law}"] = res
    json.dump(dict(fwd=FWD, rev=REV, ks=ks, results=out), open(os.path.join(OUT, "i2dir_static_a.json"), "w"), indent=1)
    s = out["k=0.0|suppressed"]["forward"]["misdirected"]
    print(f"(a') k = 0, suppressed, hard forward set misdirected or undecided {s:.2f}: {'GO (>= 0.25)' if s >= 0.25 else 'STOP (< 0.25)'}")


def stage_b(rhos):
    import frames as fr
    net = network(1e6)
    cases = FWD + REV
    A, B = list(range(len(FWD))), list(range(len(FWD), len(cases)))
    fm = fr.FrameModel(net, cases, n_samples=150, face_pts=3, seed=1, factor=1.1, drift_deg=3.0,
                       ref_phi=0.030333432167374483, model_err=0.008)
    order = {"last": None}

    def apart(d, rho):
        b = 2 * fm.eps * (1 + rho)
        pairs = [(i, j) for i in A for j in B]
        if order["last"] in pairs:
            pairs.remove(order["last"])
            pairs.insert(0, order["last"])
        for i, j in pairs:
            if fr._meet_union(fm.zonotopes(d, i), fm.zonotopes(d, j), b):
                order["last"] = (i, j)
                return False
        return True

    def try_(d, rho):
        try:
            return apart(d, rho)
        except RuntimeError:
            return False                                # no settled inverter state

    out = []
    for rho in rhos:
        t0 = time.time()
        b = 2 * fm.eps * (1 + rho)
        n_unsep0 = sum(fr._meet_union(fm.zonotopes(0j, i), fm.zonotopes(0j, j), b) for i in A for j in B)
        res = dict(rho=rho, pairs=len(A) * len(B), unseparated_pairs_at_0=int(n_unsep0))
        print(f"rho {rho}: forward-reverse pairs not apart at delta = 0: {n_unsep0} of {len(A) * len(B)}  [{time.time() - t0:.0f} s]", flush=True)
        if n_unsep0 == 0:
            res.update(abs_delta=0.0, angle_deg=0.0, feasible=True)
        else:
            r0 = None
            for r in np.arange(0.1, 1.14 + 1e-9, 0.1):
                hit = [a for a in range(0, 360, 15) if try_(r * np.exp(1j * np.radians(a)), rho)]
                if hit:
                    r0 = r
                    break
            found = None
            if r0 is not None:
                for r in np.arange(max(0.02, r0 - 0.1), r0 + 1e-9, 0.02):
                    for a in np.arange(0, 360, 5):
                        if try_(r * np.exp(1j * np.radians(a)), rho):
                            found = (float(round(r, 4)), float(a))
                            break
                    if found:
                        break
            res.update(abs_delta=None if found is None else found[0], angle_deg=None if found is None else found[1],
                       feasible=found is not None)
        res["seconds"] = time.time() - t0
        out.append(res)
        print(f"rho {rho}: direction delta* {res['abs_delta']} at {res['angle_deg']} (feasible {res['feasible']})  [{res['seconds']:.0f} s]", flush=True)
        json.dump(dict(fwd=FWD, rev=REV, runs=out), open(os.path.join(OUT, "i2dir_static_b.json"), "w"), indent=1)


# ----------------------------------------------------------------------------- (a''): inverter-interfaced load
PICKUP = 0.05


def network_s(s, neg_z=1e6):
    """Share s of the loads at R and S as V1-referenced current sinks SR, SS (open negative- and zero-sequence
    paths); the rest an impedance with y2 = y1. The source inverter I carries the law (neg_z)."""
    p = zm.ZoneParams()
    loads = {b: {1: (1 - s) * y[1], 2: (1 - s) * y[1], 0: y[0]} for b, y in (("R", p.yR), ("S", p.yS))}
    ibrs = {"I": nw.IBR("R", p.i0, (0.3, 0.3), neg_z, 1e6, inject=False, i_max=1.2)}
    if s > 0:
        ibrs["SR"] = nw.IBR("R", 0j, (0.0, 0.0), 1e6, 1e6, inject=False, i_max=10.0)
        ibrs["SS"] = nw.IBR("S", 0j, (0.0, 0.0), 1e6, 1e6, inject=False, i_max=10.0)
    return nw.Network(lines={"L1": nw.Line("L", "R", p.z1, p.z0_ratio * p.z1), "L2": nw.Line("R", "S", p.z2, p.z0_ratio * p.z2)},
                      sgs={"G": nw.SG("L", dict(p.zs), p.e0)}, ibrs=ibrs, loads=loads, relay=("L1", "b"), eps=0.08, rF=p.rF)


def operating_point(s, neg_z, u):
    """Settings for one source-box corner u (SG |e|, angle; inverter |i|, angle): the source inverter's command in
    its own frame, and the sinks drawing share s of their load's current at the all-impedance operating point."""
    base = network(neg_z, 1.0)
    v = nw.realisation(base, u)
    _, V = nw.solve(base, v, full=True)
    p = zm.ZoneParams()
    uR = V["R"][0] / abs(V["R"][0])
    st = {"I": dict(ID=float((v["I"] / uR).real), IQ=float(-(v["I"] / uR).imag), D2MAG=0.0, D2ANG=0.0)}
    if s > 0:
        for k, b, y in (("SR", "R", p.yR), ("SS", "S", p.yS)):
            ub = V[b][0] / abs(V[b][0])
            i = -s * y[1] * V[b][0] / ub                      # drawn current in the sink's own V1 frame
            st[k] = dict(ID=float(i.real), IQ=float(-i.imag), D2MAG=0.0, D2ANG=0.0)
    return {"G": v["G"]}, st


def solve_v1(net, sg, st, fault):
    try:
        return nw.solve_v1ref(net, sg, st, fault)[0], False
    except RuntimeError:
        return nw.solve_v1ref(net, sg, st, fault, relax=0.3, max_iter=3000)[0], True


def direction_pk(yN, y, pickup=PICKUP):
    dI2, dI1 = abs(y[4] - yN[4]), abs(y[3] - yN[3])
    for k_i, k_v, ok in ((4, 1, dI2 >= I2_I1_MIN * dI1 and dI2 >= pickup), (3, 0, abs(y[0] - yN[0]) >= DV1_MIN and dI1 >= pickup)):
        dI, dV = y[k_i] - yN[k_i], y[k_v] - yN[k_v]
        if ok and abs(dV) > 1e-9:
            ang = np.degrees(np.angle(dI / dV)) % 360
            return "f" if PHI < ang < 180 + PHI else "r"
    return None


def stage_a2(shares=(0.0, 0.5, 0.8, 1.0)):
    corners = list(itertools.product((-1, 1), repeat=4))
    out = {}
    for law, neg_z in (("suppressed", 1e6), ("IEEE 2800 (K2 = 2)", 0.5j)):
        for sh in shares:
            net = network_s(sh, neg_z)
            res, relaxed = {}, 0
            for side, cases, want in (("forward", FWD, "f"), ("reverse", REV, "r")):
                cnt = dict(n=0, mis=0, und=0, mis_pk=0, und_pk=0)
                by = {}
                for u in corners:
                    sg, st = operating_point(sh, neg_z, u)
                    yN, r0 = solve_v1(net, sg, st, None)
                    relaxed += r0
                    for c in cases:
                        y, r1 = solve_v1(net, sg, st, (c[0], c[1], c[2], c[3] * net.rF))
                        relaxed += r1
                        d0, d1 = direction(yN, y), direction_pk(yN, y)
                        cnt["n"] += 1
                        cnt["mis"] += d0 is not None and d0 != want
                        cnt["und"] += d0 is None
                        cnt["mis_pk"] += d1 is not None and d1 != want
                        cnt["und_pk"] += d1 is None
                        b = by.setdefault(c[2], [0, 0])
                        b[0] += d1 is not None and d1 != want
                        b[1] += 1
                res[side] = {k: (v / cnt["n"] if k != "n" else v) for k, v in cnt.items()}
                res[side]["misdirected_pk_by_type"] = {k: v[0] / v[1] for k, v in by.items()}
                print(f"{law:20s} s {sh:.1f} {side:8s}: no pickup misdirected {res[side]['mis']:.2f} undecided {res[side]['und']:.2f}; "
                      f"with 0.05 pu pickups misdirected {res[side]['mis_pk']:.2f} undecided {res[side]['und_pk']:.2f} "
                      f"(misdirected by type {res[side]['misdirected_pk_by_type']})", flush=True)
            res["relaxed_solves"] = relaxed
            out[f"{law}|s={sh}"] = res
    json.dump(dict(fwd=FWD, rev=REV, shares=shares, pickup=PICKUP, results=out),
              open(os.path.join(OUT, "i2dir_static_a2.json"), "w"), indent=1)
    t = out["suppressed|s=1.0"]["forward"]
    print(f"(a'') s = 1, suppressed: misdirected {t['mis_pk']:.2f} + undecided {t['und_pk']:.2f} with pickups "
          f"(the blind test is EMT stage c)")


if __name__ == "__main__":
    if sys.argv[1] == "a2":
        stage_a2()
    elif sys.argv[1] == "a":
        stage_a()
    else:
        stage_b([float(x) for x in sys.argv[2:]] or [0.1, 0.0])
