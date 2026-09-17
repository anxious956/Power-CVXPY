"""WP1 review tests.  python -m pytest tests/test_wp1.py -q"""
import os, sys
from dataclasses import replace
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "review"))

import aux_model  # noqa: E402
from aux_model import Params, PRESETS, solve, separated_lp  # noqa: E402
import zone_model  # noqa: E402
from zone_model import ZoneParams, solve_zone, loop_impedances, _phase  # noqa: E402
from waveforms import A_MAT, sequence_phasors, CYCLE  # noqa: E402
from wp1_common import dist_inf, margin_dual, gauge_dual, sector_outer_box, sector_inner_box  # noqa: E402
from wp1_models_fixed import solve_fixed, solve_zone_fixed  # noqa: E402

A = np.exp(2j * np.pi / 3)


# ---------------------------------------------------------------- sequence solver
def _capture_solve(monkeypatch, module):
    cap = {}
    orig = np.linalg.solve

    def spy(Am, b):
        cap["A"], cap["b"] = Am, b
        x = orig(Am, b)
        cap["x"] = x
        return x
    monkeypatch.setattr(module.np.linalg, "solve", spy)
    return cap


@pytest.mark.parametrize("preset", ["weak_sg", "all_ibr_hard"])
@pytest.mark.parametrize("scen", ["N", "ag", "ab"])
def test_kcl_residual_aux(monkeypatch, preset, scen):
    cap = _capture_solve(monkeypatch, aux_model)
    p = PRESETS[preset]
    solve(p, scen, p.e0 if p.local == "SG" else p.iL0, p.i0, 0.2 - 0.3j, 0.4, 0.7)
    r = cap["A"] @ cap["x"] - cap["b"]
    assert np.linalg.norm(r) <= 1e-10 * max(1.0, np.linalg.norm(cap["b"]))


@pytest.mark.parametrize("kind", ["N", "ag", "ab", "ag2", "ab2"])
def test_kcl_residual_zone(monkeypatch, kind):
    cap = _capture_solve(monkeypatch, zone_model)
    g = ZoneParams()
    solve_zone(g, kind, g.e0, g.i0, 0.3j, 0.3, 0.5)
    r = cap["A"] @ cap["x"] - cap["b"]
    assert np.linalg.norm(r) <= 1e-10 * max(1.0, np.linalg.norm(cap["b"]))


def test_bolted_ag_closed_form():
    """Trivial network: SG at L, nothing at R (no load, no IBR, open zero-seq path).
    All fault current comes from L:  I_f = 3E / (Z1 + Z2 + Z0),  Zk = zs_k + m z_k,  relay I+ = I- = I0 = I_f/3."""
    p = Params(yld={1: 0.0, 2: 0.0, 0: 0.0}, ibr_zero_z=1e12, ibr_neg_z=1e12, i0=0.0)
    m, E = 0.4, 1.0 + 0j
    y = solve(p, "ag", E, 0.0, 0.0, m, 0.0)
    Z = {k: p.zs[k] + m * {1: p.z1, 2: p.z1, 0: p.z0}[k] for k in (1, 2, 0)}
    If = 3 * E / (Z[1] + Z[2] + Z[0])
    np.testing.assert_allclose(y[3:], [If / 3] * 3, rtol=1e-8)
    # and the phase-a relay voltage equals m z1 (I_a + k0 3 I0)
    L = loop_impedances(y, p.z1, p.z0)
    np.testing.assert_allclose(L["ag"], m * p.z1, rtol=1e-8)


def test_bolted_bc_closed_form_for_ab_scenario():
    """The 'ab' boundary conditions give I1 = -I2 = E / (Z1 + Z2), the phase b-c fault formula."""
    p = Params(yld={1: 0.0, 2: 0.0, 0: 0.0}, ibr_zero_z=1e12, ibr_neg_z=1e12, i0=0.0)
    m, E = 0.6, 1.0 + 0j
    y = solve(p, "ab", E, 0.0, 0.0, m, 0.0)
    Z1 = p.zs[1] + m * p.z1; Z2 = p.zs[2] + m * p.z1
    np.testing.assert_allclose([y[3], y[4]], [E / (Z1 + Z2), -E / (Z1 + Z2)], rtol=1e-8)


# ---------------------------------------------------------------- transforms
def test_sequence_phase_round_trip():
    rng = np.random.default_rng(0)
    y = rng.normal(size=6) + 1j * rng.normal(size=6)
    (va, vb, vc), (ia, ib, ic) = _phase(y)
    B = np.linalg.inv(A_MAT)                    # [a,b,c] -> [s0, s+, s-]
    s_v = B @ np.array([va, vb, vc]); s_i = B @ np.array([ia, ib, ic])
    np.testing.assert_allclose([s_v[1], s_v[2], s_v[0], s_i[1], s_i[2], s_i[0]], y, atol=1e-12)
    # _phase agrees with the waveform generator's matrix
    np.testing.assert_allclose(A_MAT @ np.array([y[2], y[0], y[1]]), [va, vb, vc], atol=1e-12)


def test_dft_phasor_recovers_sequence():
    t = np.arange(CYCLE)
    s = np.array([0.1 + 0.2j, 1.0 - 0.3j, 0.05j])       # [s0, s+, s-]
    ph = A_MAT @ s
    x = np.real(ph[:, None] * np.exp(2j * np.pi * t / CYCLE)[None, :])
    np.testing.assert_allclose(sequence_phasors(x, 0), s, atol=1e-12)


# ---------------------------------------------------------------- separation LP
def _box(c, half):
    c = np.asarray(c, float)
    return c, np.eye(c.size) * half


@pytest.mark.parametrize("shift, expect_sep", [(1.0, True), (0.5, True), (0.2, False), (0.0, False)])
def test_separated_lp_boxes(shift, expect_sep):
    n, eps = 12, 0.01
    cN, GN = _box(np.zeros(n), 0.1)
    cF, GF = _box(np.eye(n)[3] * shift, 0.1)          # boxes of half-width 0.1 + eps each: touch at 0.22
    assert separated_lp(cN, GN, cF, GF, eps) == expect_sep
    d = dist_inf(cF - cN, np.hstack([GN, GF]), 2 * eps)
    np.testing.assert_allclose(d, max(0.0, shift - 0.22), atol=1e-9)
    md, lam = margin_dual(cF - cN, np.hstack([GN, GF]), 2 * eps)
    np.testing.assert_allclose(md, d, atol=1e-8)
    g, _ = gauge_dual(cF - cN, np.hstack([GN, GF]), 2 * eps)
    assert (g > 1 + 1e-9) == expect_sep


def test_separated_lp_rotated_zonotopes():
    """Non-axis-aligned: segment along (1,1) vs a point; distance is along the normal."""
    n = 12
    GN = np.zeros((n, 1)); GN[0, 0] = GN[1, 0] = 1.0
    GF = np.zeros((n, 1))
    v = np.zeros(n); v[0], v[1] = 0.5, -0.5                 # inf-distance to the segment = 0.5
    assert separated_lp(np.zeros(n), GN, v, GF, 0.1)        # 2*0.1 < 0.5
    assert not separated_lp(np.zeros(n), GN, v, GF, 0.3)    # 2*0.3 > 0.5
    np.testing.assert_allclose(dist_inf(v, np.hstack([GN, GF]), 0.2), 0.3, atol=1e-9)


# ---------------------------------------------------------------- source sets
@pytest.mark.parametrize("g", [0.09, 0.3, 0.4, 1.0])
def test_outer_box_contains_sector_and_inner_box_inside(g):
    s0, rmin, rmax = 0.45 * np.exp(-1j * 0.26), 0.225, 0.72
    c, G = sector_outer_box(s0, rmin, rmax, g)
    ci, Gi = sector_inner_box(s0, rmin, rmax, g)
    u = np.random.default_rng(1).uniform(-1, 1, (20000, 2))
    Z = (rmin + (rmax - rmin) * (u[:, 0] + 1) / 2) * np.exp(1j * (np.angle(s0) + g * u[:, 1]))
    M = np.array([[G[0].real, G[1].real], [G[0].imag, G[1].imag]])
    coords = np.linalg.solve(M, np.stack([(Z - c).real, (Z - c).imag]))
    assert np.abs(coords).max() <= 1 + 1e-9
    P = ci + Gi[0] * u[:, 0] + Gi[1] * u[:, 1]
    rel = P / s0 * abs(s0)
    assert np.all(np.abs(P) >= rmin - 1e-12) and np.all(np.abs(P) <= rmax + 1e-12)
    assert np.all(np.abs(np.angle(rel)) <= g + 1e-12)


def test_linear_angle_generator_is_not_sound():
    """aux_model's 1j*gen*i0 generator misses true source values (H6)."""
    i0 = PRESETS["weak_sg"].i0
    true_pt = (abs(i0) + 0.3) * np.exp(1j * (np.angle(i0) + 0.3))
    # coordinates of true_pt in the linear box
    G = np.array([[(0.3 * i0 / abs(i0)).real, (0.3j * i0).real], [(0.3 * i0 / abs(i0)).imag, (0.3j * i0).imag]])
    u = np.linalg.solve(G, [(true_pt - i0).real, (true_pt - i0).imag])
    assert np.abs(u).max() > 1.0


# ---------------------------------------------------------------- fault loops
@pytest.mark.parametrize("m", [0.3, 0.62, 0.85])
def test_bolted_loop_reads_m_z1_zone(m):
    g = ZoneParams()
    z0 = g.z0_ratio * g.z1
    L = loop_impedances(solve_zone(g, "ag", g.e0, g.i0, 0.0, m, 0.0), g.z1, z0)
    np.testing.assert_allclose(L["ag"], m * g.z1, rtol=1e-9)
    # the 'ab' scenario as implemented is a b-c fault: the bc loop reads m z1, the ab loop does not
    L = loop_impedances(solve_zone(g, "ab", g.e0, g.i0, 0.0, m, 0.0), g.z1, z0)
    np.testing.assert_allclose(L["bc"], m * g.z1, rtol=1e-9)
    assert abs(L["ab"] - m * g.z1) > 0.01
    # corrected a-b boundary conditions
    L = loop_impedances(solve_zone_fixed(g, "ab_true", g.e0, g.i0, 0.0, m, 0.0), g.z1, z0)
    np.testing.assert_allclose(L["ab"], m * g.z1, rtol=1e-9)


def test_bolted_loop_reads_m_z1_aux():
    p = PRESETS["weak_sg"]
    for m in (0.15, 0.55, 0.95):
        L = loop_impedances(solve(p, "ab", p.e0, p.i0, 0.0, m, 0.0), p.z1, p.z0)
        np.testing.assert_allclose(L["bc"], m * p.z1, rtol=1e-9)
        L = loop_impedances(solve_fixed(p, "ab_true", p.e0, p.i0, 0.0, m, 0.0), p.z1, p.z0)
        np.testing.assert_allclose(L["ab"], m * p.z1, rtol=1e-9)
