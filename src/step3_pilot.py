"""
The step-3 pilot's go / no-go (docs/STEP3.md, written before the pilot ran). Reads the pilot runs
(results/step3/pilot_specs.json) through the front end at two tiers (clean, design; the same noise draw at every
delta level of a scenario), and reports:

  (a) static model before the fault: |EMT - V1-referenced model| at the relay, relay frame, 50 ms before inception
  (b) the hard stratum at delta = 0 (design tier): D1's and D0's miss rates
  (c) the design on clean data at delta*: D1 on in-range faults and on normal runs (confusers reported apart)
  (d) end to end: which detectors ran
  (e) the noise budget: k sigma + the largest systematic term against eps, on the pilot's fault currents
  (f) the fingerprint: the keys that vary are in every spec (spec_digest hashes the whole spec)

and the detection table by stratum and delta level.

    python src/step3_pilot.py      -> results/step3/pilot_eval.json
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import step3_detectors as det
from step3_frontend import Relay, TIERS
from network_delta_test import CASES

OUT = os.path.join(HERE, "..", "results", "step3")
K = 4.0
TIERS_RUN = ("clean", "design", "stress")
N_SEEDS = 5
D3_FEATS = {}
DETS = ("d1", "d0", "d2g", "d2p", "d3")


def d3_pilot(rows):
    """Grouped 5-fold over scenarios: train on the other scenarios (fault windows positive; pre-fault windows and
    normal / confuser runs negative), score the held-out scenarios' fault, pre-fault and normal windows."""
    scen = sorted({q["scenario"] for q in rows})
    folds = [scen[k::5] for k in range(5)]
    by_name = {q["name"]: q for q in rows}
    for fold in folds:
        tr = [q for q in rows if q["scenario"] not in fold]
        te = [q for q in rows if q["scenario"] in fold]
        X, y = [], []
        for q in tr:
            for x_true, _, pre in D3_FEATS[q["name"]]:
                X.append(x_true)
                y.append(1 if q["kind"] == "fault" else 0)
                X.extend(pre)
                y.extend([0] * len(pre))
        X, y = np.array(X), np.array(y)
        tests = [(q["name"], xt, xs, pre) for q in te for xt, xs, pre in D3_FEATS[q["name"]]]
        Xte = np.array([t[1] for t in tests])
        Xst = np.array([t[2] if t[2] is not None else np.zeros_like(t[1]) for t in tests])
        Xpre = np.array([p for t in tests for p in t[3]])
        s_true, s_st, s_pre = det.cnn_fit_score(X, y, [Xte, Xst, Xpre], seed=0)
        npre = len(tests[0][3])
        for j, (nm, _, x_st, _) in enumerate(tests):
            q = by_name[nm]
            q.setdefault("design_d3_true_seeds", []).append(float(s_true[j]))
            q.setdefault("design_d3_starter_seeds", []).append(None if x_st is None else float(s_st[j]))
            q.setdefault("design_d3_cal", []).extend(map(float, s_pre[j * npre:(j + 1) * npre]))
    for q in rows:
        q["design_d3_true"] = q["design_d3_true_seeds"][0]
        q["design_d3_starter"] = q["design_d3_starter_seeds"][0]


def main():
    specs = json.load(open(os.path.join(OUT, "pilot_specs.json")))
    fm = det._model()
    rows, t0 = [], time.time()
    for sp in specs:
        r = dict(name=sp["name"], scenario=sp["scenario"], stratum=sp["stratum"], level=sp["level"], kind=sp["kind"],
                 in_range=sp["in_range"], confuser=(sp.get("confuser") or {}).get("kind"))
        d = complex(*sp["d_cmd"])
        for tier in TIERS_RUN:
            rel = Relay(sp["name"], tier=tier, seed=1000 + sp["scenario"])
            if tier == "clean":
                pre = rel.idx(sp["t_fault"] - 0.05)
                y = rel.y(pre)
                y_rel = y * np.conj(y[0] / abs(y[0]))
                y_mod = fm.measure(np.array([sp["S"]]), d, None)[0]
                r["pre_model_err_pu"] = float(np.abs(np.concatenate([(y_rel - y_mod).real, (y_rel - y_mod).imag])).max())
                win = rel.windows(rel.idx(sp["t_fault"]))
                r["max_I_component_pu"] = float(max(np.abs(np.concatenate([yy[3:].real, yy[3:].imag])).max() for _, yy in win))
                r["max_V_pu"] = float(max(np.abs(yy[:3]).max() for _, yy in win))
            how = "oracle" if sp["kind"] == "fault" else "forced"
            r[f"{tier}_starter_picked"] = rel.inception is not None
            r[f"{tier}_d1_starter"] = det.d1_score(rel, sp, "starter")
            r[f"{tier}_d1_true"] = det.d1_score(rel, sp, how)
            r[f"{tier}_d0_starter"] = det.d0_score(rel, sp, "starter")
            r[f"{tier}_d0_true"] = det.d0_score(rel, sp, how)
            r[f"{tier}_d0_cal"] = det.d0_calibration_scores(rel, sp)
            for rule in ("gauss", "pirani"):
                r[f"{tier}_d2{rule[0]}_starter"] = det.d2_score(rel, sp, tier, "starter", rule)
                r[f"{tier}_d2{rule[0]}_true"] = det.d2_score(rel, sp, tier, how, rule)
                r[f"{tier}_d2{rule[0]}_cal"] = det.d2_calibration_scores(rel, sp, tier, rule)
        # D3 features: design tier, several noise draws per run (scenario-paired seeds); pre-fault pseudo-triggers
        feats = []
        for sd in range(N_SEEDS):
            rel = Relay(sp["name"], tier="design", seed=5000 + 100 * sp["scenario"] + sd)
            x_true = det.d3_features(rel, sp, how)
            x_st = det.d3_features(rel, sp, "starter")
            true = rel.idx(sp["t_fault"])
            pre = [det.d3_features(rel, dict(sp, t_fault=i / rel.fs + rel.t0), "oracle")
                   for i in np.linspace(rel.idx(0.18), true - 3 * 128 - 1, 4).astype(int)]
            feats.append((x_true, x_st, pre))
        D3_FEATS[sp["name"]] = feats
        rows.append(r)
        print(f"{sp['name']}: model err {r['pre_model_err_pu']:.4f} pu; D1 clean {r['clean_d1_true']:.2f} eps, design "
              f"{r['design_d1_true']:.2f} eps; starter {r['design_starter_picked']}  [{time.time() - t0:.0f} s]", flush=True)

    d3_pilot(rows)
    # calibrated thresholds: the largest calibration-negative score per detector, tier and level (pre-fault windows
    # of every run); D1's threshold is the design's (distance > eps)
    levels = sorted({q["level"] for q in rows})
    thr = {}
    for dn in ("d0", "d2g", "d2p", "d3"):
        for t in TIERS_RUN:
            if dn == "d3" and t != "design":
                continue
            for lv in levels:
                thr[(dn, t, lv)] = max(x for q in rows if q["level"] == lv for x in q[f"{t}_{dn}_cal"])

    def alarm(q, tier, dname, how):
        s = q.get(f"{tier}_{dname}_{how}")
        if s is None:
            return False
        return s > 1.0 if dname == "d1" else s > thr[(dname, tier, q["level"])]

    res = dict(thresholds={f"{dn}_{t}_{lv}": v for (dn, t, lv), v in thr.items()})
    # (a)
    ea = max(q["pre_model_err_pu"] for q in rows)
    res["a_pre_model_err_max_pu"] = ea
    # (b)
    hard0 = [q for q in rows if q["stratum"] == "hard" and q["level"] == 0.0 and q["in_range"]]
    res["b"] = {f"{dn}_{how}_miss": float(np.mean([not alarm(q, "design", dn, how) for q in hard0])) for dn in DETS
                for how in ("starter", "true")}
    # (c)
    top = [q for q in rows if q["level"] == 1.0]
    fin = [q for q in top if q["kind"] == "fault" and q["in_range"]]
    nor = [q for q in top if q["kind"] == "normal" and q["confuser"] is None]
    con = [q for q in top if q["confuser"]]
    res["c"] = dict(in_range_faults=len(fin), d1_detected_true=int(sum(alarm(q, "clean", "d1", "true") for q in fin)),
                    d1_detected_starter=int(sum(alarm(q, "clean", "d1", "starter") for q in fin)),
                    min_d1_fault_score=min(q["clean_d1_true"] for q in fin),
                    normal_runs=len(nor), d1_normal_alarms=int(sum(alarm(q, "clean", "d1", "true") for q in nor)),
                    max_d1_normal_score=max(q["clean_d1_true"] for q in nor),
                    confusers={q["name"]: q["clean_d1_true"] for q in con})
    # (d)
    res["d"] = {dn: all(f"design_{dn}_true" in q for q in rows) for dn in DETS}
    # (e)
    cfg = TIERS["design"]
    imax = max(q["max_I_component_pu"] for q in rows if q["kind"] == "fault")
    vmax = max(q["max_V_pu"] for q in rows)
    res["e"] = dict(current_budget_pu=K * cfg["sigma_i"] + cfg["ct"][1] * imax, voltage_budget_pu=K * cfg["sigma_v"] + (cfg["vt"][1] + np.radians(cfg["vt_phase_deg"][1])) * vmax,
                    eps=det.EPS, max_I_component_pu=imax, max_V_pu=vmax)
    # (f)
    keys = ("t_fault", "settings", "lim")
    res["f"] = dict(all_specs_carry=all(all(k in sp for k in keys) and "TANG" in sp["settings"]["I"] for sp in specs),
                    confusers_in_spec=all(("confuser" in sp) == bool(sp.get("confuser")) for sp in specs))
    # detection table
    tab = {}
    for tier in TIERS_RUN:
        for st in ("hard", "hard_bc", "uniform", "outside", "normal", "load", "phase1"):
            for lv in sorted({q["level"] for q in rows}):
                q = [x for x in rows if x["stratum"] == st and x["level"] == lv]
                if q:
                    tab[f"{tier}|{st}|{lv}"] = {f"{dn}_{how}": float(np.mean([alarm(x, tier, dn, how) for x in q]))
                                                for dn in (DETS if tier == "design" else DETS[:4]) for how in ("starter", "true")}
    # D1's worst case: a clean distance above 2 eps is detected under ANY noise inside the eps box (the noise moves
    # the measurement by at most eps on every component, and D1 alarms above eps); the design's guarantee
    for st in ("hard", "hard_bc", "uniform", "outside"):
        for lv in sorted({q["level"] for q in rows}):
            q = [x for x in rows if x["stratum"] == st and x["level"] == lv]
            tab[f"guaranteed|{st}|{lv}"] = float(np.mean([x["clean_d1_true"] > 2.0 for x in q]))
    res["table"] = tab
    json.dump(dict(result=res, rows=rows), open(os.path.join(OUT, "pilot_eval.json"), "w"), indent=1, default=float)
    print(f"\n(a) pre-fault |EMT - model| max {ea:.4f} pu (<= 0.005): {'PASS' if ea <= 0.005 else 'FAIL'}")
    b = res["b"]
    print("(b) hard, delta 0, design tier, miss rate (true trigger / starter): " +
          ", ".join(f"{dn.upper()} {b[dn + '_true_miss']:.0%} / {b[dn + '_starter_miss']:.0%}" for dn in DETS) +
          f": {'PASS' if min(b['d1_true_miss'], b['d0_true_miss']) >= 0.25 else 'FAIL'}")
    c = res["c"]
    print(f"(c) delta*, clean: D1 detects {c['d1_detected_true']}/{c['in_range_faults']} in-range faults (starter {c['d1_detected_starter']}), "
          f"smallest score {c['min_d1_fault_score']:.2f} eps; normal alarms {c['d1_normal_alarms']}/{c['normal_runs']} (largest {c['max_d1_normal_score']:.2f}); "
          f"confusers {c['confusers']}: {'PASS' if c['d1_detected_true'] == c['in_range_faults'] and c['d1_normal_alarms'] == 0 else 'FAIL'}")
    print(f"(d) {res['d']}")
    e = res["e"]
    print(f"(e) design tier budget: currents {e['current_budget_pu']:.3f} pu, voltages {e['voltage_budget_pu']:.3f} pu against eps {e['eps']}: "
          f"{'PASS' if max(e['current_budget_pu'], e['voltage_budget_pu']) <= e['eps'] else 'FAIL'} (largest fault current component {e['max_I_component_pu']:.2f} pu)")
    print(f"(f) {res['f']}")
    print("\nalarm rate, true trigger, design tier, by stratum (rows) and delta level 0 / .25 / .5 / .75 / 1 (D1 D0 D2g D2p D3):")
    for st in ("hard", "hard_bc", "uniform", "outside", "normal", "load", "phase1"):
        cells = [" ".join(f"{tab[k][dn + '_true']:.2f}" for dn in DETS) for k in tab if k.startswith(f"design|{st}|")]
        print(f"    {st:8s} " + "  |  ".join(cells))
    print("\nalarm rate, true trigger, stress tier (eps-scale noise), D1 D0 D2g D2p:")
    for st in ("hard", "hard_bc", "uniform", "outside", "normal", "load", "phase1"):
        cells = [" ".join(f"{tab[k][dn + '_true']:.2f}" for dn in DETS[:4]) for k in tab if k.startswith(f"stress|{st}|")]
        print(f"    {st:8s} " + "  |  ".join(cells))
    print("\nD1 guaranteed under any noise inside the eps box (clean distance > 2 eps), delta level 0 / .25 / .5 / .75 / 1:")
    for st in ("hard", "hard_bc", "uniform", "outside"):
        print(f"    {st:8s} " + "  ".join(f"{tab[k]:.2f}" for k in tab if k.startswith(f"guaranteed|{st}|")))
    print("-> results/step3/pilot_eval.json")


if __name__ == "__main__":
    main()
