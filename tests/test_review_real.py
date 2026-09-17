"""Correctness tests for the real-data pipeline and the review machinery (H33, N1, H22).

    python -m pytest tests/test_review_real.py -q

None of these needs the EvEMTBench caches.
"""
import os, sys
import numpy as np
import pytest

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC)

import real_ml
from review import common as cm
from zone_model import ZoneParams, solve_zone, phase_selected_reactance, loop_impedances
from waveforms import sequence_phasors, EVENT, CYCLE

A = np.exp(2j * np.pi / 3)


def _three_phase(ph_pre, ph_post, n_total=3201, ev=640, spc=128):
    """Phase phasors (3,) before/after sample ev -> (3, n_total) waveform at 128 samples/cycle."""
    k = np.arange(n_total)
    w = np.exp(2j * np.pi * k / spc)
    x = np.where(k < ev, np.real(ph_pre[:, None] * w), np.real(ph_post[:, None] * w))
    return x


def _record(v_pre, v_post, i_pre, i_post):
    return np.concatenate([_three_phase(v_pre, v_post), _three_phase(i_pre, i_post)])[None]


# ------------------------------------------------------------------------------------------- N1
@pytest.mark.parametrize("t_ms", [20, 30, 40, 50])
def test_phasor_view_keeps_pre_and_post_in_one_phase_reference(t_ms):
    """A record with no event must give identical pre- and post-fault phasors at every decision
    time. Before the N1 fix the post-fault phasor came out rotated by 180 deg at 30 and 50 ms."""
    v = 1e5 * np.array([1, A**2, A]); i = 400 * np.exp(-0.3j) * np.array([1, A**2, A])
    R = dict(full=_record(v, v, i, i).astype(np.float32), ev=640)
    pv = real_ml.phasor_view(R, np.array([0]), t_ms)[0]
    pre = sequence_phasors(pv[3:], EVENT - 2 * CYCLE)
    post = sequence_phasors(pv[3:], EVENT + CYCLE)
    assert np.allclose(pre, post, rtol=1e-4, atol=1e-3)


# ------------------------------------------------------------------------------------------- H22
def test_grouped_folds_never_split_a_sibling_group():
    rng = np.random.default_rng(0)
    groups = np.repeat(np.arange(60), 3)
    y = (groups % 2).astype(int)
    for _, tr, te in cm.grouped_folds(y, groups, 5, 2, 0):
        assert not set(groups[tr]) & set(groups[te])


def test_stratified_folds_do_split_sibling_groups():
    """Documents H22: the split real_ml.within_relay_zone uses puts siblings on both sides."""
    groups = np.repeat(np.arange(60), 3)
    y = (groups % 2).astype(int)
    shares = []
    for _, tr, te in cm.stratified_folds(y, groups, 5, 2, 0):
        shares.append(np.mean([g in set(groups[tr]) for g in groups[te]]))
    assert np.mean(shares) > 0.8


# ------------------------------------------------------------------------------------------- chain
def test_default_chain_is_bit_identical_to_real_ml():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, (4, 6, 3201)).astype(np.float32)
    x[:, :3] *= 9e4; x[:, 3:] *= 500
    assert np.array_equal(cm.measurement_chain(x, "relay-x", None), real_ml.measurement_chain(x, "relay-x"))


def test_ct_saturation_is_transparent_below_saturation_and_clips_offset_faults():
    t = np.arange(3201) / 6400
    small = (1000 * np.sin(2 * np.pi * 50 * t))[None, None]                       # 0.7 A rms secondary
    assert np.allclose(cm.ct_saturation(small), small, rtol=0, atol=2.0)
    big = 30e3 * (np.sin(2 * np.pi * 50 * t - np.pi / 2) + np.exp(-t / 0.03))[None, None]
    out = cm.ct_saturation(big, remanence=0.8)
    assert np.abs(out[..., 200:1600]).max() < 0.9 * np.abs(big[..., 200:1600]).max()


# ------------------------------------------------------------------------------------------- elements
def _zone_case(kind, m, mr):
    g = ZoneParams(rF=0.3)
    pre = solve_zone(g, "N", g.e0, g.i0, 0.0)
    post = solve_zone(g, kind, g.e0, g.i0, 0.0, m, mr)
    # [v+, v-, v0, i+, i-, i0] -> [s0, s+, s-]
    seq = lambda y: (np.array([y[2], y[0], y[1]]), np.array([y[5], y[3], y[4]]))
    return g, seq(pre), seq(post)


@pytest.mark.parametrize("kind,m,mr", [("ag", 0.3, 0.0), ("ag", 0.7, 0.5), ("ab", 0.5, 0.0), ("ab", 0.8, 0.9),
                                       ("ag2", 0.1, 0.3)])
def test_vectorised_phase_selection_matches_zone_model(kind, m, mr):
    g, (vpre, ipre), (vpost, ipost) = _zone_case(kind, m, mr)
    x_ref = phase_selected_reactance(vpost, ipre, ipost, g.z1, g.z0_ratio * g.z1)
    R = dict(z1L=g.z1, z0L=g.z0_ratio * g.z1)
    Lp = cm.loops(R, vpost[None], ipost[None], vpre[None], ipre[None])
    mask = cm.phase_selection(ipre[None], ipost[None])
    x, _ = cm.rule_reactance(Lp, mask)
    assert np.isclose(x[0], x_ref)


@pytest.mark.parametrize("m", [0.2, 0.5, 0.8])
def test_bolted_ground_fault_reads_m_x1_and_takagi_removes_fault_resistance(m):
    g, (vpre, ipre), (vpost, ipost) = _zone_case("ag", m, 0.0)
    R = dict(z1L=g.z1, z0L=g.z0_ratio * g.z1)
    Lp = cm.loops(R, vpost[None], ipost[None], vpre[None], ipre[None])
    mask = cm.phase_selection(ipre[None], ipost[None])
    x, _ = cm.rule_reactance(Lp, mask)
    assert abs(x[0] / g.z1.imag - m) < 1e-6
    # Takagi formula: loop V = m Z1L I + Rf If with If a real multiple of the superimposed loop current.
    # With load flow the plain reactance reading is shifted, the superimposed-current line is exact.
    z1L = 3.3 + 26j
    I_pre, dI = 400 * np.exp(-0.2j), 3000 * np.exp(-1.35j)
    I = I_pre + dI
    V = m * z1L * I + 20.0 * (1.7 * dI)
    V_pre = 9e4 + 0j
    Lp = dict(V=np.array([[V, 0, 0, 0, 0, 0]]), I=np.array([[I, 1, 1, 1, 1, 1]]),
              Vpre=np.array([[V_pre, 0, 0, 0, 0, 0]]), Ipre=np.array([[I_pre, 1, 1, 1, 1, 1]]))
    mask = np.array([[True, False, False, False, False, False]])
    R = dict(z1L=z1L)
    x_tak = cm.polarised_reactance(R, Lp, mask, "takagi")
    x_plain, _ = cm.rule_reactance(Lp, mask)
    assert abs(x_tak[0] / z1L.imag - m) < 1e-9
    assert abs(x_plain[0] / z1L.imag - m) > 1e-2


def test_binomial_interval_zero_of_ten_is_wide():
    lo, hi = cm.binom_ci(0, 10)
    assert lo == 0.0 and 0.29 < hi < 0.32
