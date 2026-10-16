"""
Analysis of the EMT test of the TAC25 design (runs listed by src/pscad_tac25_design.py).

The reference is the design's own normal set: the outer source set (H6) restricted by the per-phase limit
rule at the design delta. ratio = smallest noise box (in units of eps) that puts the relay measurement inside
that set. Fault: separated iff ratio > 2, with the margin iff ratio > 2 (1 + rho). Normal: inside iff ratio ~ 0.
Checks first: fault visible at the relay, |EMT - design model| at the relay, what the inverter injected.

    python src/pscad_tac25_sweep.py      -> results/pscad/tac25_sweep.json
"""
import os, sys, json
import numpy as np
from scipy.optimize import linprog
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "review"))
from aux_model import realify, solve
from wp1_common import ModelSet
from pscad_tac25_design import P, MODE, limit_block
from pscad_twobus_check import read_case, relay_y, injection, WORK

ROOT = os.path.join(HERE, "..")
MS = ModelSet(P, mode=MODE)
CN, HN, GN = MS.N
A_PH = np.exp(2j * np.pi / 3)


def noise_needed(y_real, d):
    target = y_real - (CN + HN @ np.array([d.real, d.imag]))
    n, k = target.size, GN.shape[1]
    c = np.zeros(k + n + 1)
    c[-1] = 1
    A1, b1 = limit_block(k, d)
    A_ub = np.vstack([np.hstack([np.zeros((n, k)), np.eye(n), -np.ones((n, 1))]),
                      np.hstack([np.zeros((n, k)), -np.eye(n), -np.ones((n, 1))]),
                      np.hstack([A1, np.zeros((A1.shape[0], n + 1))])])
    b_ub = np.concatenate([np.zeros(2 * n), b1])
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=np.hstack([GN, np.eye(n), np.zeros((n, 1))]), b_eq=target,
                  bounds=[(-1, 1)] * k + [(None, None)] * n + [(0, None)], method="highs")
    return res.x[-1] if res.status == 0 else np.inf


def evaluate(r, t_pre=0.25, t_meas=0.38):
    run = read_case(os.path.join(WORK, r["name"] + ".gf46"), r["name"])
    y_pre, _, _ = relay_y(run, t_pre)
    e1 = y_pre[0] + P.zs[1] * y_pre[3]
    rot = np.exp(1j * (np.radians(r["ph_deg"]) - np.angle(e1)))
    tm = t_meas if r["kind"] == "fault" else t_pre
    y, _, _ = relay_y(run, tm)
    y = y * rot
    i1, i2 = injection(run, tm)
    i1, i2 = i1 * rot, i2 * rot
    d = complex(*r["delta"])
    ys = solve(P, r["scen"], abs(e1) * np.exp(1j * np.radians(r["ph_deg"])), i1, i2, m=r["m"], mr=r["mr"])
    peak = max(abs(i1 * A_PH ** (-k) + i2 * A_PH ** k) for k in range(3))
    asked_i1 = float(np.hypot(r["idref"], r["iqref"]))
    return dict(ratio=float(noise_needed(realify(y), d) / P.eps), emt_vs_design=float(np.abs(y - ys).max()),
                I1=float(abs(i1)), I1_asked=asked_i1, I2=float(abs(i2)), I2_asked=float(r["d2mag"]), phase_peak=float(peak),
                limited=bool(abs(i1) < 0.98 * asked_i1 or (r["d2mag"] and abs(i2) < 0.98 * r["d2mag"])),
                fault_dV1=float(abs(y[0] - y_pre[0] * rot)) if r["kind"] == "fault" else 0.0)


def main():
    spec = json.load(open(os.path.join(ROOT, "results", "pscad", "tac25_design.json")))
    rho = spec["rho"]
    rows = []
    for r in spec["runs"]:
        if not os.path.exists(os.path.join(WORK, r["name"] + ".gf46", r["name"] + "_01.out")):
            continue
        q = {**{k: r.get(k) for k in ("name", "kind", "scen", "m", "mr", "tag", "lim", "corner", "design_ratio")}, **evaluate(r)}
        rows.append(q)
    bad = [q["name"] for q in rows if q["kind"] == "fault" and q["fault_dV1"] < 1e-3]
    big = [(q["name"], round(q["emt_vs_design"], 4)) for q in rows if q["emt_vs_design"] > 0.02]
    over = [(q["name"], round(q["phase_peak"], 3)) for q in rows if q["phase_peak"] > 1.21]
    print(f"checks: {len(rows)} runs; fault not visible in {len(bad)} {bad[:4]}; |EMT - design| > 0.02 pu in {len(big)} {big[:4]}; "
          f"phase peak above 1.21 pu in {len(over)} {over[:4]}; median |EMT - design| "
          f"{np.median([q['emt_vs_design'] for q in rows]):.5f}, max {max(q['emt_vs_design'] for q in rows):.4f} pu")
    g = lambda kind, tag: [q for q in rows if q["kind"] == kind and q["tag"] == tag]
    f0, ft, fc, n1, n0 = g("fault", "d0"), g("fault", "dt"), g("fault", "corner"), g("normal", "lim1"), g("normal", "lim0")
    if f0:
        print(f"30 cases at their worst realisation, delta = 0: {sum(q['ratio'] <= 2 for q in f0)} not separated "
              f"({', '.join(q['name'][2:-3] for q in f0 if q['ratio'] <= 2)})")
    if ft:
        w = min(ft, key=lambda q: q["ratio"])
        print(f"30 cases at their worst realisation, TAC25 delta: {sum(q['ratio'] > 2 for q in ft)} of {len(ft)} separated, "
              f"{sum(q['ratio'] > 2 * (1 + rho) for q in ft)} with the margin; smallest {w['ratio']:.2f} ({w['name']}, design model "
              f"{w['design_ratio']:.2f})")
    for m in (75, 95):
        c = [q for q in fc if q["name"].startswith(f"t_ag{m}_")]
        if c:
            w = min(c, key=lambda q: q["ratio"])
            print(f"A-G {m} %, 40 ohm, TAC25 delta, LIM 1, 16 corners: {sum(q['ratio'] > 2 for q in c)} of {len(c)} separated; "
                  f"smallest {w['ratio']:.2f} at {w['corner']} (limiter cut I1 at {sum(q['limited'] for q in c)})")
    for lab, n in (("LIM 1 (delta kept, I1 cut)", n1), ("LIM 0 (both scaled)", n0)):
        if n:
            print(f"normal operation, 16 corners, {lab}: {sum(q['ratio'] >= 0.05 for q in n)} outside the normal set; "
                  f"largest ratio {max(q['ratio'] for q in n):.2f}; limiter active at {sum(q['limited'] for q in n)}")
    json.dump(dict(rho=rho, rows=rows), open(os.path.join(ROOT, "results", "pscad", "tac25_sweep.json"), "w"), indent=1)
    print("-> results/pscad/tac25_sweep.json")


if __name__ == "__main__":
    main()
