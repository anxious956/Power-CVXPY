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
def test_bolted_ground_fault_reads_m_x1(m):
    g, (vpre, ipre), (vpost, ipost) = _zone_case("ag", m, 0.0)
    R = dict(z1L=g.z1, z0L=g.z0_ratio * g.z1)
    Lp = cm.loops(R, vpost[None], ipost[None], vpre[None], ipre[None])
    mask = cm.phase_selection(ipre[None], ipost[None])
    x, _ = cm.rule_reactance(Lp, mask)
    assert abs(x[0] / g.z1.imag - m) < 1e-6


def _radial(kind, m, mr, load=0.3):
    """Circuit-solved radial feed: local source, protected line, adjacent line, a constant-current load
    at R and nothing else. No remote source, no remote shunt in any sequence network, no ground path at
    R (ibr_zero_z open). The superimposed network is radial, so the superimposed current at the relay
    is the fault current, and with z0/z1 real the compensated loop current is in phase with it."""
    g = ZoneParams(rF=0.3, yR={1: 0.0, 2: 0.0, 0: 0.0}, yS={1: 0.0, 2: 0.0, 0: 0.0}, ibr_zero_z=1e12,
                   ibr_neg_z=1e12, i0=-load * np.exp(-0.3j))
    pre = solve_zone(g, "N", g.e0, g.i0, 0.0)
    post = solve_zone(g, kind, g.e0, g.i0, 0.0, m, mr)
    seq = lambda y: (np.array([y[2], y[0], y[1]]), np.array([y[5], y[3], y[4]]))
    return g, seq(pre), seq(post)


@pytest.mark.parametrize("m,mr", [(0.2, 0.5), (0.5, 1.0), (0.8, 1.0)])
def test_takagi_is_exact_on_a_radial_circuit_and_plain_reactance_is_not(m, mr):
    g, (vpre, ipre), (vpost, ipost) = _radial("ag", m, mr)
    R = dict(z1L=g.z1, z0L=g.z0_ratio * g.z1)
    Lp = cm.loops(R, vpost[None], ipost[None], vpre[None], ipre[None])
    mask = cm.phase_selection(ipre[None], ipost[None])
    x_tak = cm.polarised_reactance(R, Lp, mask, "takagi")
    x_plain, _ = cm.rule_reactance(Lp, mask)
    assert abs(x_tak[0] / g.z1.imag - m) < 1e-6
    assert abs(x_plain[0] / g.z1.imag - m) > 1e-2


def test_characterise_takagi_error_on_the_non_homogeneous_three_bus_model():
    """Characterisation, not a pass/fail on accuracy: distance error (fraction of line) of the plain
    reactance reading and of the Takagi line for an AG fault at m = 0.7, R_f = 0.15 pu on zone_model's
    three-bus network, versus (a) the angle of the remote inverter's infeed and (b) the angle of the
    remote-bus shunt (load/grounding), which sets the non-homogeneity. Written to
    results/review/takagi_nonhomogeneity.json. The Takagi error term R_f Im(I_f dI*) / Im(Z1L I dI*) has a
    superimposed numerator (independent of the constant-current inverter's pre-fault output) but a
    denominator that carries the total loop current, so it still moves with the infeed angle. Asserted:
    both errors finite, and the Takagi error non-zero (the network is non-homogeneous)."""
    import json
    from dataclasses import replace
    m, mr = 0.7, 0.5
    base = ZoneParams(rF=0.3)
    R = dict(z1L=base.z1, z0L=base.z0_ratio * base.z1)

    def errors(g):
        pre = solve_zone(g, "N", g.e0, g.i0, 0.0)
        post = solve_zone(g, "ag", g.e0, g.i0, 0.0, m, mr)
        vpre, ipre = np.array([pre[2], pre[0], pre[1]]), np.array([pre[5], pre[3], pre[4]])
        vpost, ipost = np.array([post[2], post[0], post[1]]), np.array([post[5], post[3], post[4]])
        Lp = cm.loops(R, vpost[None], ipost[None], vpre[None], ipre[None])
        mask = cm.phase_selection(ipre[None], ipost[None])
        x_plain, _ = cm.rule_reactance(Lp, mask)
        x_tak = cm.polarised_reactance(R, Lp, mask, "takagi")
        return float(x_plain[0] / g.z1.imag - m), float(x_tak[0] / g.z1.imag - m)

    infeed = {}
    for th in range(-60, 61, 15):
        infeed[th] = errors(replace(base, i0=abs(base.i0) * np.exp(1j * np.deg2rad(th))))
    shunt = {}
    for ph in range(-80, 1, 10):
        y = {s: abs(base.yR[s]) * np.exp(1j * np.deg2rad(ph)) for s in (1, 2)}
        shunt[ph] = errors(replace(base, yR={1: y[1], 2: y[2], 0: 0.0}))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "review")
    os.makedirs(out, exist_ok=True)
    json.dump(dict(fault=dict(type="ag", m=m, rf_pu=mr * base.rF),
                   columns=["plain reactance error", "Takagi error"],
                   vs_remote_infeed_angle_deg=infeed, vs_remote_shunt_angle_deg=shunt),
              open(os.path.join(out, "takagi_nonhomogeneity.json"), "w"), indent=1)
    tak = np.array([v[1] for v in infeed.values()]); plain = np.array([v[0] for v in infeed.values()])
    assert np.all(np.isfinite(tak)) and np.all(np.isfinite(plain))
    assert np.all(np.abs(tak) > 1e-3)


def test_binomial_interval_zero_of_ten_is_wide():
    lo, hi = cm.binom_ci(0, 10)
    assert lo == 0.0 and 0.29 < hi < 0.32
