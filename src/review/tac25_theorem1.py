"""TAC25 Theorem 1: the closed-form lower bound on the auxiliary signal, validated against the
presets where the exact answer is already known, then applied to the zone problem (H1).

VALIDATION GATE. review/WP1_REPORT.md H15 established the exact global minimum separating |delta|
for the two-bus presets under the ZONOTOPE uncertainty of src/aux_model.py:

    weak_sg 0.5040    weak_sg_noisy 0.6908    all_ibr_hard 0.3863    weak_sg_eps12 1.3186
    easy 0 (delta = 0 already separates)

Theorem 1 is a NECESSARY condition, so its bound must not exceed the exact optimum. Because TAC25
uses a Euclidean uncertainty ball where aux_model uses an infinity-norm box, the comparison is only
sound for the INSCRIBED ball (a subset of the zonotope, hence an easier problem, hence a smaller
required signal). The gate is therefore

    bound(inscribed) <= exact zonotope optimum         for every preset.

The circumscribed ball contains the zonotope and its bound may legitimately exceed the exact
zonotope optimum; it is reported as the other end of the bracket, not as a gate.

    python src/review/tac25_theorem1.py        -> results/review_wp1/tac25_theorem1.json   (~1 min)
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import aux_model as am
from review import tac25
from review import common as cm

OUT = os.path.join(cm.ROOT, "results", "review_wp1")

# Exact global optima under the zonotope uncertainty (review/WP1_REPORT.md H15, results/review_wp1/h15_global.json)
EXACT = {"easy": 0.0, "weak_sg": 0.5040, "weak_sg_noisy": 0.6908, "all_ibr_hard": 0.3863,
         "weak_sg_eps12": 1.3186}


def sigma_exact(models, theta):
    """sigma_S(theta) of TAC25 eq. (3) solved directly: min_x max_k ||X_k x - (h_k - Theta_k theta)||^2
    on the folded matrices. Used only to verify Lemma 2 (w_mean <= sigma <= w_max)."""
    import scipy.optimize as so
    A = [m[1] for m in models]
    b = [m[2] - m[0] @ theta for m in models]
    f = lambda x: max(float((A[k] @ x - b[k]) @ (A[k] @ x - b[k])) for k in (0, 1))
    x0 = np.linalg.lstsq(np.vstack(A), np.concatenate(b), rcond=None)[0]
    r = so.minimize(f, x0, method="Nelder-Mead", options=dict(maxiter=40000, xatol=1e-10, fatol=1e-12))
    r = so.minimize(f, r.x, method="Powell", options=dict(maxiter=40000, xtol=1e-12, ftol=1e-14))
    return float(r.fun)


def run_preset(name, p, verify=2):
    row = dict(preset=name, eps=p.eps, exact_zonotope_optimum=EXACT.get(name))
    for geom in tac25.NOISE_GEOMETRY:
        P = tac25.TAC25Problem(p, geometry=geom)
        B = P.pair_bounds()
        sig0 = [tac25.omega_hat([P.normal["folded"], f["folded"]], np.zeros(2)) for f in P.faults]
        row[geom] = dict(lower_bound=B["lower_bound"], binding_pair=B["binding_pair"],
                         n_pairs=B["n_pairs"], n_no_signal_needed=B["n_no_signal_needed"],
                         max_zeta=float(max(r["zeta"] for r in B["rows"])),
                         min_zeta=float(min(r["zeta"] for r in B["rows"])),
                         min_chi=float(min(r["chi_spectral"] for r in B["rows"])),
                         # how close to ambiguous the pairs are at delta = 0
                         n_pairs_possibly_ambiguous_at_0=int(sum(not s["separates_possible"] for s in sig0)),
                         min_w_max_at_0=float(min(s["w_max"] for s in sig0)),
                         lower_bound_frobenius=float(max([r["bound_frobenius"] for r in B["rows"]
                                                          if np.isfinite(r["bound_frobenius"]) and not r["no_signal_needed"]] or [0.0])))
        # Lemma 2 self-check on a few pairs: w_mean <= sigma_exact <= w_max
        chk = []
        for f in P.faults[:verify]:
            mo = [P.normal["folded"], f["folded"]]
            w = tac25.omega_hat(mo, np.zeros(2))
            s = sigma_exact(mo, np.zeros(2))
            chk.append(bool(w["w_mean"] - 1e-6 <= s <= w["w_max"] + 1e-6))
        row[geom]["lemma2_holds"] = bool(all(chk))
    e = row["exact_zonotope_optimum"]
    b = row["inscribed"]["lower_bound"]
    row["gate_inscribed_le_exact"] = bool(e is None or b <= e + 1e-9)
    row["gate_slack"] = None if e is None else float(e - b)
    row["bound_informative"] = bool(b > 1e-9)
    return row


def zone_problem_bounds(rf=0.3, eps_list=(0.001, 0.005, 0.01, 0.02, 0.04, 0.08), i_max=1.2):
    """H1 as a Theorem-1 statement rather than a search result.

    The zone problem is in-zone vs out-of-zone vs normal on the three-bus model. src/aux_model.py is
    a two-bus model, so the closest faithful encoding available here is the two-bus model with the
    IN set at m in [0.62, 0.85] and the OUT set at m in [0.02, 0.18] of the NEXT line, which is what
    src/review/wp1_h1_zone_design.py uses. This function instead reports the bound on the two-bus
    presets' own geometry as a function of eps, which is the quantity H1 turns on: whether any
    admissible delta can separate at a realistic measurement error.

    Reported for the weak_sg source configuration, which is the one H1 was run on.
    """
    rows = []
    for eps in eps_list:
        p = am.Params(name=f"zone_eps{eps:g}", zs=am._WEAK, gen_i=[0.3, 0.3], eps=eps, rF=rf)
        r = dict(eps=eps, rf=rf)
        for geom in tac25.NOISE_GEOMETRY:
            B = tac25.TAC25Problem(p, geometry=geom).pair_bounds()
            r[geom] = dict(lower_bound=B["lower_bound"], binding_pair=B["binding_pair"],
                           n_no_signal_needed=B["n_no_signal_needed"], n_pairs=B["n_pairs"])
            r[f"{geom}_exceeds_imax"] = bool(B["lower_bound"] > i_max)
        rows.append(r)
    return dict(i_max=i_max, rows=rows)


if __name__ == "__main__":
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    out = dict(commit=cm.git_commit(), exact_reference=EXACT, presets=[], note=tac25.__doc__.strip().splitlines()[0])
    print(f"{'preset':>16} {'eps':>6} {'exact':>7} | {'bound(inscr)':>13} {'gate':>6} {'slack':>8} | {'bound(circ)':>12} | {'binding pair':>28}")
    for name, p in am.PRESETS.items():
        if name not in EXACT:
            continue
        r = run_preset(name, p)
        out["presets"].append(r)
        print(f"{name:>16} {r['eps']:6.3f} {r['exact_zonotope_optimum']:7.4f} | "
              f"{r['inscribed']['lower_bound']:13.4f} {str(r['gate_inscribed_le_exact']):>6} {r['gate_slack']:8.4f} | "
              f"{r['circumscribed']['lower_bound']:12.4f} | {str(r['inscribed']['binding_pair']):>28}", flush=True)
    out["gate_all_pass"] = bool(all(r["gate_inscribed_le_exact"] for r in out["presets"]))
    out["lemma2_all_hold"] = bool(all(r[g]["lemma2_holds"] for r in out["presets"] for g in tac25.NOISE_GEOMETRY))
    out["bound_informative_any"] = bool(any(r["bound_informative"] for r in out["presets"]))
    print(f"\nLemma 2 self-check (w_mean <= sigma_exact <= w_max, solved independently): "
          f"{'HOLDS' if out['lemma2_all_hold'] else 'VIOLATED'}")
    print(f"GATE (bound_inscribed <= exact zonotope optimum, every preset): "
          f"{'PASS' if out['gate_all_pass'] else 'FAIL'}")
    print(f"IS THE BOUND INFORMATIVE?  {'yes' if out['bound_informative_any'] else 'NO - it is 0 at every preset'}")
    print("\nDiagnosis. Only the inscribed ball is a sound lower bound for the zonotope problem:")
    print("  inscribed ball  <subset>  zonotope  <subset>  circumscribed ball, and a smaller uncertainty")
    print("  set is easier to separate, so  L(inscribed) <= d*(inscribed) <= d*(zonotope).")
    print("  L(circumscribed) bounds a HARDER problem, so it is not a lower bound for ours.")
    for r in out["presets"]:
        i, c = r["inscribed"], r["circumscribed"]
        print(f"  {r['preset']:>16}: inscribed  zeta in [{i['min_zeta']:.2f}, {i['max_zeta']:.2f}], "
              f"{i['n_no_signal_needed']}/{i['n_pairs']} pairs already separated at delta=0 -> bound {i['lower_bound']:.3f}")
        print(f"  {'':>16}  circumscr. zeta in [{c['min_zeta']:.2f}, {c['max_zeta']:.2f}], "
              f"{c['n_no_signal_needed']}/{c['n_pairs']} already separated              -> bound {c['lower_bound']:.3f}")

    print("\nZone problem: certified lower bound on |delta| against measurement error eps")
    Z = zone_problem_bounds()
    out["zone_problem"] = Z
    print(f"{'eps':>7} | {'bound(inscr)':>13} {'> I_max?':>9} | {'bound(circ)':>12} {'> I_max?':>9} | {'pairs needing a signal':>23}")
    for r in Z["rows"]:
        need = r["inscribed"]["n_pairs"] - r["inscribed"]["n_no_signal_needed"]
        print(f"{r['eps']:7.3f} | {r['inscribed']['lower_bound']:13.4f} {str(r['inscribed_exceeds_imax']):>9} | "
              f"{r['circumscribed']['lower_bound']:12.4f} {str(r['circumscribed_exceeds_imax']):>9} | "
              f"{need:>3}/{r['inscribed']['n_pairs']:<3}", flush=True)

    path = os.path.join(OUT, "tac25_theorem1.json")
    json.dump(out, open(path, "w"), indent=1, default=float)
    print(f"\nsaved {path}  [{time.time()-t0:.0f}s]")
