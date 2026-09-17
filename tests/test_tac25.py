"""Correctness tests for the TAC25 design work and the corrected ladder resistive reach.

No EMT data needed; all of this is the static sequence model and closed-form settings arithmetic.

    python -m pytest tests/test_tac25.py -q
"""
import os, sys
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "review"))

import aux_model as am                      # noqa: E402
from review import tac25                    # noqa: E402
import tac25_design as td                   # noqa: E402
from wp1_common import ModelSet             # noqa: E402


# ------------------------------------------------------------------ Kasztenny 2021 eq. (19)
def test_polarising_cap_inverts_eq19():
    """R_set = |Z1L|(1 - m0)/(2 sin(Theta/2)) must satisfy m0 = 1 - 2 r_B sin(Theta/2)."""
    from review.ladder import polarising_cap
    z, m0 = 10.485, 0.85
    P = polarising_cap(z, tilt_nominal_deg=3.73, tilt_range_deg=[-2.46, 10.49], m0=m0)
    for key, th in (("r_cap_r2", P["theta_r2_deg"]), ("r_cap_r3", P["theta_r3_deg"])):
        r_b = P[key] / z
        assert np.isclose(1 - 2 * r_b * np.sin(np.deg2rad(th) / 2), m0, atol=1e-12)


def test_polarising_cap_theta_per_rung():
    """The untilted rung sees the whole non-homogeneity angle; the tilted one only the residual,
    so its cap is never the tighter of the two."""
    from review.ladder import polarising_cap
    P = polarising_cap(10.485, 3.73, [-2.46, 10.49])
    assert P["theta_r2_deg"] == pytest.approx(10.49)
    assert P["theta_r3_deg"] == pytest.approx(10.49 - 3.73)
    assert P["r_cap_r2"] < P["r_cap_r3"]


def test_polarising_cap_tightens_with_error():
    from review.ladder import polarising_cap
    caps = [polarising_cap(10.0, 0.0, [-t, t])["r_cap_r2"] for t in (2.0, 5.0, 10.0, 20.0)]
    assert caps == sorted(caps, reverse=True)


# ------------------------------------------------------------------ TAC25 Theorem 1
@pytest.mark.parametrize("geom", ["inscribed", "circumscribed"])
def test_lemma2_bracket_holds(geom):
    """TAC25 Lemma 2: w_mean <= sigma_S(theta) <= w_max, against an independent solve of P0_S.
    This is the check that the Theorem 1 machinery is implemented correctly."""
    from scipy.optimize import minimize
    P = tac25.TAC25Problem(am.PRESETS["weak_sg"], geometry=geom)
    th = np.zeros(2)
    for f in P.faults[:3]:
        mo = [P.normal["folded"], f["folded"]]
        w = tac25.omega_hat(mo, th)
        A = [m[1] for m in mo]
        b = [m[2] - m[0] @ th for m in mo]
        fun = lambda x: max(float((A[k] @ x - b[k]) @ (A[k] @ x - b[k])) for k in (0, 1))
        x0 = np.linalg.lstsq(np.vstack(A), np.concatenate(b), rcond=None)[0]
        r = minimize(fun, x0, method="Nelder-Mead", options=dict(maxiter=40000, xatol=1e-10, fatol=1e-12))
        sig = float(minimize(fun, r.x, method="Powell", options=dict(maxiter=40000, xtol=1e-12, ftol=1e-14)).fun)
        assert w["w_mean"] - 1e-6 <= sig <= w["w_max"] + 1e-6


def test_theorem1_bound_never_exceeds_exact_optimum():
    """The bound is a NECESSARY condition, so on the inscribed ball -- the only geometry that is a
    sound lower bound for the zonotope problem -- it may not exceed the known exact optimum."""
    exact = {"weak_sg": 0.5040, "all_ibr_hard": 0.3863}
    for name, e in exact.items():
        B = tac25.TAC25Problem(am.PRESETS[name], geometry="inscribed").pair_bounds()
        assert B["lower_bound"] <= e + 1e-9


def test_theorem1_is_vacuous_on_box_uncertainty():
    """Documents the finding of results/DESIGN.md section 2: with per-component (box) bounds the
    inscribed ball already separates every pair at delta = 0, so the bound carries no information.
    If this ever starts failing, the bound has become useful and DESIGN.md section 2 needs revisiting."""
    B = tac25.TAC25Problem(am.PRESETS["weak_sg"], geometry="inscribed").pair_bounds()
    assert B["n_no_signal_needed"] == B["n_pairs"]
    assert B["lower_bound"] == 0.0


# ------------------------------------------------------------------ current limit inside the problem
def test_circumscribed_polygon_contains_the_disc():
    """limit_rows uses a circumscribed polygon, so it must accept every point of the disc it
    approximates -- the restriction is understated, never overstated, which keeps it sound."""
    p = am.PRESETS["weak_sg"]
    from wp1_common import source_sets
    _, (c, g) = source_sets(p, "linear")
    r_head = 1.0
    A, b = td.limit_rows(p, "linear", 4, r_head)
    rng = np.random.default_rng(0)
    for _ in range(300):
        u = rng.uniform(-1, 1, 2)
        i_plus = c + g[0] * u[0] + g[1] * u[1]
        if abs(i_plus) <= r_head:                       # inside the disc -> must satisfy every row
            uu = np.zeros(8)
            uu[2], uu[3] = u
            assert np.all(A @ uu <= b + 1e-9)


def test_min_delta_reproduces_exact_optimum_unconstrained():
    """The global polar solve must land on the known exact zonotope optimum, to the grid step."""
    ms = ModelSet(am.PRESETS["all_ibr_hard"], mode="linear")
    r = td.min_delta(ms, limit_inside=False, limit_design=False, r_step=0.02, n_ang=72, r_max=1.0)
    assert r["feasible"]
    assert 0.3863 <= r["abs_delta"] <= 0.3863 + 0.02 + 1e-9


def test_limit_inside_never_needs_more_than_unconstrained():
    """The central claim of results/DESIGN.md section 3: restricting the uncertainty to what a
    current-limited inverter can actually produce can only make separation easier, so the required
    signal must not increase."""
    ms = ModelSet(am.PRESETS["all_ibr_hard"], mode="linear")
    free = td.min_delta(ms, limit_inside=False, limit_design=False, r_step=0.04, n_ang=36, r_max=1.0)
    inside = td.min_delta(ms, i_max=1.2, limit_inside=True, limit_design=False, r_step=0.04, n_ang=36, r_max=1.0)
    assert free["feasible"] and inside["feasible"]
    assert inside["abs_delta"] <= free["abs_delta"] + 1e-9


def test_limit_inside_relaxes_towards_unconstrained_as_imax_grows():
    """A looser limit removes fewer realisations, so the required signal rises towards the
    unconstrained answer -- the mechanism the feasibility map shows."""
    ms = ModelSet(am.PRESETS["weak_sg"], mode="linear")
    d = [td.min_delta(ms, i_max=im, limit_inside=True, limit_design=False, r_step=0.04, n_ang=36, r_max=1.2)
         for im in (1.2, 1.5, 2.1)]
    got = [x["abs_delta"] for x in d if x["feasible"]]
    assert len(got) == 3
    assert got == sorted(got)


def test_h5_outer_check_is_the_stricter_reading():
    """H5 applied the limit to the design variable, which can only remove candidates. Wherever it
    returns an answer, that answer cannot be smaller than the one from restricting the uncertainty."""
    ms = ModelSet(am.PRESETS["weak_sg"], mode="linear")
    outer = td.min_delta(ms, i_max=1.2, limit_inside=False, limit_design=True, r_step=0.04, n_ang=36)
    inside = td.min_delta(ms, i_max=1.2, limit_inside=True, limit_design=False, r_step=0.04, n_ang=36, r_max=1.2)
    assert inside["feasible"]
    assert not outer["feasible"] or outer["abs_delta"] >= inside["abs_delta"] - 1e-9


def test_margin_costs_signal():
    """H14: asking for measurement-unit headroom must not make the design cheaper."""
    ms = ModelSet(am.PRESETS["weak_sg"], mode="linear")
    a = td.min_delta(ms, i_max=1.2, limit_inside=True, limit_design=False, rho=0.0, r_step=0.04, n_ang=36, r_max=1.5)
    b = td.min_delta(ms, i_max=1.2, limit_inside=True, limit_design=False, rho=0.1, r_step=0.04, n_ang=36, r_max=1.5)
    assert a["feasible"] and b["feasible"]
    assert b["abs_delta"] >= a["abs_delta"] - 1e-9
