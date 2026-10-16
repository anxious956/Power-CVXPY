"""
Analysis of the extended EMT test (runs listed by src/pscad_delta_design.py, run by src/pscad_batch.py).

For every run the EMT relay measurement is placed against the design tool's normal set N(delta):
ratio = smallest noise box (in units of eps) that puts the measurement inside N(delta).
  fault runs:  separated iff ratio > 2; separated with the design margin iff ratio > 2 (1 + rho)
  normal runs: a clean normal measurement should sit inside N (ratio 0); ratio > 0 means some noise
               within eps can push it outside N + eps, i.e. a false alarm is possible
Also reported: what the inverter actually injected (the 1.2 pu limiter can cut it), and |EMT - design|.

    python src/pscad_delta_sweep.py      -> results/pscad/delta_sweep.json
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aux_model import realify, solve
from pscad_delta_test import P, noise_needed
from pscad_twobus_check import read_case, relay_y, injection, WORK

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


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
    i1_asked = float(np.hypot(r["idref"], r["iqref"]))
    return dict(ratio=float(noise_needed(realify(y), d) / P.eps), ratio_design_model=float(noise_needed(realify(ys), d) / P.eps),
                emt_vs_design=float(np.abs(y - ys).max()), I1=float(abs(i1)), I1_asked=i1_asked, I2=float(abs(i2)),
                I2_asked=float(r["d2mag"]), limited=bool(abs(i1) < 0.98 * i1_asked or (r["d2mag"] and abs(i2) < 0.98 * r["d2mag"])),
                fault_dV1=float(abs(y[0] - y_pre[0] * rot)) if r["kind"] == "fault" else 0.0)


def main():
    spec = json.load(open(os.path.join(ROOT, "results", "pscad", "delta_design.json")))
    rho = spec["rho"]
    rows = []
    for r in spec["runs"]:
        if not os.path.exists(os.path.join(WORK, r["name"] + ".gf46", r["name"] + "_01.out")):
            continue
        q = {**{k: r[k] for k in ("name", "kind", "scen", "m", "mr", "tag", "es_pu", "ph_deg")}, **evaluate(r)}
        if r["kind"] == "fault":
            q["design_ratio_witness"] = r.get("design_ratio")
            q["corner"] = r.get("corner")
            q["verdict"] = "separated" if q["ratio"] > 2 else "NOT separated"
            q["with_margin"] = q["ratio"] > 2 * (1 + rho)
        else:
            q["corner"] = r["corner"]
            q["verdict"] = "inside N" if q["ratio"] < 0.05 else "OUTSIDE N (false alarm possible)"
        rows.append(q)
    f0 = [q for q in rows if q["kind"] == "fault" and q["tag"] == "d0"]
    fm = [q for q in rows if q["kind"] == "fault" and q["tag"] == "dm"]
    nm = [q for q in rows if q["kind"] == "normal" and q["tag"] == "dm"]
    n0 = [q for q in rows if q["kind"] == "normal" and q["tag"] == "d0s"]
    fc = [q for q in rows if q["kind"] == "fault" and q["tag"] == "dm_corner"]
    print(f"fault cases at their worst realisation, delta = 0: {sum(q['ratio'] <= 2 for q in f0)} of {len(f0)} not separated "
          f"({', '.join(q['name'][2:-3] for q in f0 if q['ratio'] <= 2)})")
    print(f"fault cases at their worst realisation, margin delta: {sum(q['ratio'] > 2 for q in fm)} of {len(fm)} separated, "
          f"{sum(q['with_margin'] for q in fm)} with the {rho:.0%} margin; smallest ratio {min(q['ratio'] for q in fm):.2f} "
          f"({min(fm, key=lambda q: q['ratio'])['name']})")
    print(f"normal operation at the 16 corners, margin delta: {sum(q['ratio'] >= 0.05 for q in nm)} of {len(nm)} outside N; "
          f"limiter cut delta at {sum(q['limited'] for q in nm)} corners")
    for q in sorted(nm, key=lambda q: -q["ratio"])[:16]:
        print(f"   corner {q['corner']}: EMF {q['es_pu']:.3f}, I1 {q['I1']:.3f}, I2 {q['I2']:.3f} of {q['I2_asked']:.2f}"
              f"{' (limited)' if q['limited'] else ''} -> ratio {q['ratio']:.2f}  [{q['verdict']}]")
    if n0:
        print(f"normal operation at the 16 corners, no-margin delta 0.18: {sum(q['ratio'] >= 0.05 for q in n0)} of {len(n0)} "
              f"outside N (largest ratio {max(q['ratio'] for q in n0):.2f}); limiter active at {sum(q['limited'] for q in n0)}")
    if fc:
        for m in (75, 95):
            g = [q for q in fc if q["name"].startswith(f"x_ag{m}_")]
            print(f"A-G {m} %, 40 ohm, margin delta at all 16 corners: {sum(q['ratio'] > 2 for q in g)} of {len(g)} separated; "
                  f"smallest ratio {min(q['ratio'] for q in g):.2f} at corner {min(g, key=lambda q: q['ratio'])['corner']}"
                  f" (limiter active at {sum(q['limited'] for q in g)})")
    # checks before anything is reported
    bad_fault = [q["name"] for q in rows if q["kind"] == "fault" and q["fault_dV1"] < 1e-3]
    big_diff = [(q["name"], round(q["emt_vs_design"], 4)) for q in rows if q["emt_vs_design"] > 0.02]
    lim = [q["name"] for q in rows if q["limited"]]
    print(f"checks: fault not visible at the relay in {len(bad_fault)} runs {bad_fault[:5]}; |EMT - design| > 0.02 pu in "
          f"{len(big_diff)} runs {big_diff[:6]}; inverter limiter active in {len(lim)} runs")
    worst = max(rows, key=lambda q: q["emt_vs_design"])
    print(f"largest |EMT - design| {worst['emt_vs_design']:.4f} pu ({worst['name']}); median "
          f"{np.median([q['emt_vs_design'] for q in rows]):.5f} pu")
    json.dump(dict(rho=rho, rows=rows), open(os.path.join(ROOT, "results", "pscad", "delta_sweep.json"), "w"), indent=1)
    print(f"{len(rows)} runs evaluated -> results/pscad/delta_sweep.json")


if __name__ == "__main__":
    main()
