"""Tests for the Hasan et al. (2026) re-implementation (src/review/hasan_svm.py). No cache needed.

    python -m pytest tests/test_hasan_svm.py -q
"""
import os, sys
import numpy as np
import pytest

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC)

from review import hasan_svm as hs
from review import common as cm

A = np.exp(2j * np.pi / 3)
EV = 640


def _record(v_pre, v_post, i_pre, i_post, n_total=1280, ev=EV, phase_shift=0.0):
    """(1, 6, n_total) waveform: phasors change at sample ev; phase_shift rotates every channel."""
    k = np.arange(n_total)
    w = np.exp(1j * (2 * np.pi * k / cm.SPC + phase_shift))
    ph = lambda pre, post: np.where(k < ev, np.real(pre[:, None] * w), np.real(post[:, None] * w))
    return np.concatenate([ph(v_pre, v_post), ph(i_pre, i_post)])[None].astype(np.float64)


V0 = 1e5 * np.array([1, A**2, A]); I0 = 400 * np.exp(-0.3j) * np.array([1, A**2, A])
VF = 0.6e5 * np.array([1, A**2, A]); IF = 3000 * np.exp(-1.2j) * np.array([1, A**2, A])


def _feats(X, end_offset, angle="deg"):
    ref = hs.memory_reference(X, EV)
    return hs.buffer_features(X, EV + end_offset, ref, angle=angle)


def test_angle_reference_removes_a_common_phase_rotation():
    """adapt_grid randomises the grid's initial angle; referenced features must not see it. Checked on
    buffers entirely before or entirely after inception: a DFT window that straddles inception depends on
    the point on wave by physics (a step at a different phase), not on the reference."""
    X1 = _record(V0, VF, I0, IF)
    X2 = _record(V0, VF, I0, IF, phase_shift=2.1)
    for off in (-128, hs.BUFFER + cm.SPC):
        f1, f2 = _feats(X1, off), _feats(X2, off)
        for b in ("common", "neg", "zero"):
            d = np.abs(f1[b] - f2[b])
            # angles in degrees wrap at +-180; compare modulo 360 for the angle columns
            if b == "common":
                d[:, 7:13] = np.minimum(d[:, 7:13], 360 - d[:, 7:13])
            assert d.max() < 1e-6 * max(1.0, np.abs(f1[b]).max()), (b, off, d.max())


def test_buffer_is_pre_fault_only_when_it_ends_before_inception_and_post_fault_after():
    X = _record(V0, VF, I0, IF)
    pre = _feats(X, -128)                         # buffer [ev-512, ev-128]: no fault sample
    assert np.allclose(pre["common"][0, 1:4], np.abs(V0), rtol=1e-6)
    assert np.allclose(pre["common"][0, 4:7], np.abs(I0), rtol=1e-6)
    late = _feats(X, hs.BUFFER + cm.SPC)          # every step's DFT window after inception
    assert np.allclose(late["common"][0, 1:4], np.abs(VF), rtol=1e-6)
    assert np.allclose(late["common"][0, 4:7], np.abs(IF), rtol=1e-6)
    mid = _feats(X, 128)                          # the 20 ms decision: mostly pre-fault in the buffer
    assert np.abs(VF[0]) < mid["common"][0, 1] < np.abs(V0[0])


def test_balanced_record_has_no_negative_or_zero_sequence_and_positive_sequence_equals_phase():
    X = _record(V0, V0, I0, I0)
    f = _feats(X, 128)
    assert f["neg"].max() < 1e-6 * np.abs(V0[0]) and f["zero"].max() < 1e-6 * np.abs(V0[0])
    assert np.isclose(f["common"][0, 13], np.abs(V0[0]), rtol=1e-6)      # |V+|
    assert np.isclose(f["common"][0, 0], np.abs(V0[0]) / np.sqrt(2), rtol=1e-3)   # Vrms of a sinusoid


def test_sincos_variant_has_twelve_angle_columns():
    X = _record(V0, VF, I0, IF)
    assert _feats(X, 128, "sincos")["common"].shape[1] == 21
    assert _feats(X, 128, "deg")["common"].shape[1] == 15


def test_fault_class_mapping():
    et = ["flt_1phg_shc", "flt_1phg_shc_w_arc", "flt_2ph_shc", "flt_2phg_shc", "flt_3ph_shc", "switch_load_on", "flt_incipient"]
    assert list(hs.fault_class(et)) == ["LG", "LG", "LL", "LLG", "3P", "", ""]


def test_stage_top_k_selection_uses_only_the_training_data_and_is_deterministic():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, 6)); y = (X[:, 0] + 0.5 * X[:, 1] ** 2 > 0.3).astype(int)
    s1 = hs.Stage(1.0, poly=True, k=20, seed=0).fit(X[:200], y[:200])
    s2 = hs.Stage(1.0, poly=True, k=20, seed=0).fit(X[:200].copy(), y[:200].copy())
    assert len(s1.sel) == 20 and np.array_equal(s1.sel, s2.sel)
    assert np.array_equal(s1.decision(X[200:]), s2.decision(X[200:]))


def test_stage_with_one_class_returns_a_constant_instead_of_failing():
    X = np.zeros((10, 3)); y = np.zeros(10, int)
    st = hs.Stage(1.0).fit(X, y)
    assert (st.predict(X) == 0).all() and (st.decision(X) < 0).all()


def test_gate_blocks_non_forward_decisions():
    class S1:
        def predict(self, X): return np.array([2, 1, 0])
    class S2:
        def predict(self, X): return np.array(["LG_a", "LG_a", "LG_a"])
    class S3:
        def decision(self, X): return np.array([5.0, 5.0, 5.0])[:len(X)]
    h = hs.Hierarchy(); h.s1, h.s2 = S1(), S2(); h.s3 = {c: S3() for c in hs.CLASSES}
    F = dict(common=np.zeros((3, 15)), neg=np.zeros((3, 2)), zero=np.zeros((3, 2)))
    g, d, c = h.score(F, np.arange(3))
    assert g[0] == 5.0 and g[1] == hs.GATE and g[2] == hs.GATE
