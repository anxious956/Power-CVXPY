"""
Quick checks beyond H1-H16 (WP1 review):
  X1  the 'ab' scenario is a b-c fault: which loop reads m*X1 for a bolted fault (aux_model, zone_model),
      and the corrected a-b boundary conditions (wp1_models_fixed).
  X2  consequence for zone_detect: faulted-phase selection (score_reactance) vs the hard-coded L["ab"]
      in zone_features (zone_detect.py:125); engineered-LR AUC with the loop fixed (quick sizes, 1 seed).
  X3  numerical conditioning of the dense solve with ibr_neg_z = 1e6; KCL residual.
  X4  zero-sequence compensation and sign conventions (k0, forward direction).

  python src/review/wp1_extra_checks.py [--no-auc]      (~1 min without AUC, ~5-8 min with)
"""
import sys, time
import numpy as np
from wp1_common import PRESETS, dump, SRC
import aux_model, zone_model
from zone_model import ZoneParams, loop_impedances, phase_selected_reactance
from wp1_models_fixed import solve_fixed, solve_zone_fixed

res = {}
t0 = time.time()

# ------------------------------------------------------------------ X1
p = PRESETS["weak_sg"]
g = ZoneParams()
tab = []
for model, fn, pp, z1, z0, kinds in (("aux_model", solve_fixed, p, p.z1, p.z0, ("ag", "ab", "ab_true")),
                                     ("zone_model", solve_zone_fixed, g, g.z1, g.z0_ratio * g.z1, ("ag", "ab", "ab_true"))):
    for kind in kinds:
        for m in (0.3, 0.7):
            y = fn(pp, kind, pp.e0, pp.i0, 0.0, m, 0.0)
            L = loop_impedances(y, z1, z0)
            err = {k: abs(v.imag - m * z1.imag) for k, v in L.items()}
            best = min(err, key=err.get)
            tab.append(dict(model=model, kind=kind, m=m, mX1=m * z1.imag,
                            X={k: round(float(v.imag), 4) for k, v in L.items()}, loop_reading_mX1=best,
                            err_best=float(err[best]), err_ab_loop=float(err["ab"])))
            print(f"X1 {model:10s} kind={kind:8s} m={m}: m*X1={m*z1.imag:.3f}  loop that reads it: {best} "
                  f"(err {err[best]:.1e}); ab-loop reads {L['ab'].imag:.4f}", flush=True)
res["X1_bolted_loops"] = tab

# phase currents at the relay for a bolted 'ab' with no load current: which phases carry the fault current
g0 = zone_model.ZoneParams(yR={1: 1e-9, 2: 1e-9, 0: 0.0}, yS={1: 1e-9, 2: 1e-9, 0: 0.0})
for kind in ("ab", "ab_true"):
    y_f = solve_zone_fixed(g0, kind, g0.e0, 0.0, 0.0, 0.5, 0.0)
    y_n = solve_zone_fixed(g0, "N", g0.e0, 0.0, 0.0, 0.5, 0.0)
    _, (ia, ib, ic) = zone_model._phase(y_f - y_n)
    res[f"X1_incremental_phase_currents_{kind}"] = [abs(ia), abs(ib), abs(ic)]
    print(f"X1 zone_model {kind}: |incremental Ia, Ib, Ic| at relay = {abs(ia):.3f}, {abs(ib):.3f}, {abs(ic):.3f}")

# ------------------------------------------------------------------ X2 (noise-free phasors)
rows = []
for kind in ("ab", "ab_true"):
    errs_sel, errs_ab, loops = [], [], []
    for m in np.linspace(0.62, 0.85, 8):
        pre = solve_zone_fixed(g, "N", g.e0, g.i0, 0.0, m, 0.0)
        post = solve_zone_fixed(g, kind, g.e0, g.i0, 0.0, m, 0.0)
        vpost = np.array([post[2], post[0], post[1]]); ipost = np.array([post[5], post[3], post[4]])
        ipre = np.array([pre[5], pre[3], pre[4]])
        x = phase_selected_reactance(vpost, ipre, ipost, g.z1, g.z0_ratio * g.z1)
        L = loop_impedances(post, g.z1, g.z0_ratio * g.z1)
        errs_sel.append(abs(x - m * g.z1.imag)); errs_ab.append(abs(L["ab"].imag - m * g.z1.imag))
    rows.append(dict(kind=kind, max_err_phase_selected=float(max(errs_sel)), max_err_ab_loop=float(max(errs_ab)),
                     ab_loop_err_over_line_X=float(max(errs_ab) / g.z1.imag)))
    print(f"X2 in-zone bolted {kind:8s}: max |X_selected - mX1| = {max(errs_sel):.2e}; "
          f"max |X_ab_loop - mX1| = {max(errs_ab):.4f} pu ({max(errs_ab)/g.z1.imag:.0%} of line X)", flush=True)
res["X2_zone_loops"] = rows

if "--no-auc" not in sys.argv:
    import zone_detect
    from zone_detect import make_zone_dataset, score_engineered, SigParams
    from detect import evaluate
    from dataclasses import replace
    grid = replace(ZoneParams(), rF=0.3)
    orig_solve, orig_loops = zone_detect.solve_zone, zone_detect._loops
    auc = {}
    for label, use_true_ab, swap_loop in (("as_is", False, False), ("ab_is_bc_use_bc_loop", False, True),
                                          ("true_ab_fault_ab_loop", True, False)):
        if use_true_ab:
            zone_detect.solve_zone = lambda gg, kind, *a, **k: solve_zone_fixed(
                gg, {"ab": "ab_true", "ab2": "ab_true2"}.get(kind, kind), *a, **k)
        else:
            zone_detect.solve_zone = orig_solve
        if swap_loop:
            def _loops(vpost, ipost, gg):
                L = orig_loops(vpost, ipost, gg); L = dict(L); L["ab"] = L["bc"]; return L
            zone_detect._loops = _loops
        else:
            zone_detect._loops = orig_loops
        for d in (0.0, 0.514 * np.exp(-1j * np.deg2rad(23.2))):
            Xtr, ytr, _ = make_zone_dataset(350, np.random.default_rng(100), d, SigParams(), grid, True)
            Xte, yte, _ = make_zone_dataset(250, np.random.default_rng(999), d, SigParams(), grid, True)
            e_tr, e_te = score_engineered(Xtr, ytr, Xte, grid, seed=0)
            r = evaluate(e_tr, ytr, e_te, yte)
            auc[f"{label}_delta{abs(d):.3f}"] = dict(auc=r["auc"], detection_rate=r["detection_rate"])
            rt = zone_detect.score_reactance(Xte, grid)
            rr = evaluate(zone_detect.score_reactance(Xtr, grid), ytr, rt, yte)
            auc[f"{label}_delta{abs(d):.3f}_reactance"] = dict(auc=rr["auc"], detection_rate=rr["detection_rate"])
            print(f"X2 AUC {label:24s} |d|={abs(d):.3f}: engineered {r['auc']:.4f} (dep@1% {r['detection_rate']:.3f}); "
                  f"reactance {rr['auc']:.4f}", flush=True)
    zone_detect.solve_zone, zone_detect._loops = orig_solve, orig_loops
    res["X2_auc_quick_1seed_350_250"] = auc

# ------------------------------------------------------------------ X3
captured = {}
orig = np.linalg.solve


def cap(Am, b):
    captured["A"], captured["b"] = Am, b
    return orig(Am, b)


aux_model.np.linalg.solve = cap
x3 = {}
for nz in (1e3, 1e6, 1e12):
    pp = aux_model.Params(**{**PRESETS["weak_sg"].__dict__, "ibr_neg_z": nz})
    y = aux_model.solve(pp, "ag", pp.e0, pp.i0, 0.3 - 0.1j, 0.55, 1.0)
    Am, b = captured["A"], captured["b"]
    xx = orig(Am, b)
    x3[str(nz)] = dict(y=y, cond=float(np.linalg.cond(Am)), rel_residual=float(np.linalg.norm(Am @ xx - b) / np.linalg.norm(b)))
aux_model.np.linalg.solve = orig
base = x3["1000000.0"]["y"]
for k, v in x3.items():
    v["max_abs_diff_vs_1e6"] = float(np.abs(v["y"] - base).max())
    print(f"X3 ibr_neg_z={k}: cond(A)={v['cond']:.2e}  rel. residual {v['rel_residual']:.1e}  max|y - y(1e6)| {v['max_abs_diff_vs_1e6']:.2e}")
res["X3_conditioning"] = x3

# ------------------------------------------------------------------ X4
k0 = (g.z0_ratio * g.z1 - g.z1) / (3 * g.z1)
res["X4"] = dict(k0=k0, paper_k=g.z0_ratio - 1, equivalent=bool(abs(3 * k0 - (g.z0_ratio - 1)) < 1e-12))
print(f"X4 k0 = {k0:.4f} (applied to 3 I0) == paper k = z0/z - 1 = {g.z0_ratio - 1} (applied to I0): {res['X4']['equivalent']}")
res["runtime_s"] = time.time() - t0
dump(res, "extra_checks.json")
