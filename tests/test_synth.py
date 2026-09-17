"""Tests for the synthetic detection pipeline (review H33).

  python -m pytest tests/test_synth.py -q
"""
import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from waveforms import sequence_phasors, A_MAT, CYCLE, SigParams, _synth  # noqa: E402
import detect as D  # noqa: E402
import zone_detect as Z  # noqa: E402
from zone_model import ZoneParams, solve_zone, phase_selected_reactance  # noqa: E402


def _to_zpn(y, off):
    """solve_zone order [+, -, 0] at offset off -> sequence_phasors order [0, +, -]."""
    return np.array([y[off + 2], y[off], y[off + 1]])


# ------------------------------------------------------------------ sequence_phasors
def test_sequence_phasors_recovers_known_phasor_exactly():
    seq = np.array([0.05 - 0.02j, 0.9 * np.exp(0.3j), 0.12 * np.exp(-1.1j)])   # [s0, s+, s-]
    ph = A_MAT @ seq
    n = np.arange(3 * CYCLE)
    x3 = np.real(ph[:, None] * np.exp(1j * 2 * np.pi * n / CYCLE)[None, :])
    for start in (0, CYCLE, 2 * CYCLE):
        np.testing.assert_allclose(sequence_phasors(x3, start), seq, atol=1e-12)


# ------------------------------------------------------------------ evaluate polarity (H17)
def test_evaluate_chooses_polarity_on_train_not_test():
    rng = np.random.default_rng(0)
    y = np.r_[np.zeros(200), np.ones(200)].astype(int)
    s_tr = np.where(y == 1, 1.0, 0.0) + 0.1 * rng.normal(size=400)    # faults HIGH on train
    s_te = np.where(y == 1, -1.0, 0.0) + 0.1 * rng.normal(size=400)   # faults LOW on test
    r = D.evaluate(s_tr, y, s_te, y)
    assert r["polarity"] == +1
    assert r["auc"] < 0.05                  # the train direction does not transfer: say so
    assert r["detection_rate"] < 0.05
    legacy = D.evaluate(s_tr, y, s_te, y, polarity="test")
    assert legacy["polarity"] == -1 and legacy["auc"] > 0.95   # what the old code reported


def test_evaluate_negative_polarity_from_train():
    rng = np.random.default_rng(1)
    y = np.r_[np.zeros(300), np.ones(300)].astype(int)
    s = np.where(y == 1, -1.0, 0.0) + 0.3 * rng.normal(size=600)     # like reactance: low = fault
    r = D.evaluate(s, y, s, y)
    assert r["polarity"] == -1 and r["auc"] > 0.9 and r["auc_train"] > 0.9


# ------------------------------------------------------------------ distance element
M_VALUES = (0.3, 0.7)


@pytest.mark.parametrize("kind", ["ag", "ab"])
@pytest.mark.parametrize("m", M_VALUES)
def test_phase_selected_reactance_bolted_zone_model(kind, m):
    g = ZoneParams()
    srcL, iR = 1.0 + 0j, g.i0
    pre = solve_zone(g, "N", srcL, iR, 0.0)
    post = solve_zone(g, kind, srcL, iR, 0.0, m, 0.0)        # bolted: mr = 0
    x = phase_selected_reactance(_to_zpn(post, 0), _to_zpn(pre, 3), _to_zpn(post, 3),
                                 g.z1, g.z0_ratio * g.z1)
    assert abs(x - m * g.z1.imag) / (m * g.z1.imag) < 0.01


@pytest.mark.parametrize("kind", ["ag", "ab"])
def test_phase_selected_reactance_bolted_through_waveforms(kind):
    """Same, through waveform synthesis and the one-cycle DFT (no noise, DC or harmonics)."""
    g, m = ZoneParams(), 0.6
    pre = solve_zone(g, "N", 1.0 + 0j, g.i0, 0.1)
    post = solve_zone(g, kind, 1.0 + 0j, g.i0, 0.1, m, 0.0)
    p = SigParams(noise=0.0, harmonics=(0.0, 0.0), dc_offset=0.0)
    rng = np.random.default_rng(0)
    x = np.vstack([_synth(pre[:3], post[:3], p, rng), _synth(pre[3:], post[3:], p, rng, True)])
    est = Z.score_reactance(x[None], g)[0]
    assert abs(est - m * g.z1.imag) / (m * g.z1.imag) < 0.01


@pytest.mark.parametrize("m", M_VALUES)
def test_phase_selected_reactance_bolted_abg(m):
    """zone_model.solve_zone has no double-line-to-ground fault, so a radial source + line is
    solved here: bolted BCG in phase-a reference, then phases relabelled to ABG."""
    z1 = 0.02 + 0.20j; z0 = 3 * z1
    zs = {1: 0.4j, 2: 0.4j, 0: 0.8j}
    Z1, Z2, Z0 = zs[1] + m * z1, zs[2] + m * z1, zs[0] + m * z0
    I1 = 1.0 / (Z1 + Z2 * Z0 / (Z2 + Z0))
    I2, I0 = -I1 * Z0 / (Z2 + Z0), -I1 * Z2 / (Z2 + Z0)
    V1, V2, V0 = 1.0 - zs[1] * I1, -zs[2] * I2, -zs[0] * I0          # at the relay
    Vbcg = A_MAT @ np.array([V0, V1, V2])
    Ibcg = A_MAT @ np.array([I0, I1, I2])
    perm = [1, 2, 0]                           # new a = old b, new b = old c, new c = old a
    B = np.linalg.inv(A_MAT)
    v_seq, i_seq = B @ Vbcg[perm], B @ Ibcg[perm]                   # [s0, s+, s-]
    x = phase_selected_reactance(v_seq, np.zeros(3, complex), i_seq, z1, z0)
    assert abs(x - m * z1.imag) / (m * z1.imag) < 0.01


# ------------------------------------------------------------------ OOF thresholds (H18)
def _random_features(n=80, d=60, seed=0):
    rng = np.random.default_rng(seed)
    return rng.normal(size=(n, d)), np.r_[np.zeros(n // 2), np.ones(n // 2)].astype(int)


def test_lr_training_scores_are_out_of_fold():
    """With pure-noise features an in-sample LR separates its own training set (AUC ~1); an
    out-of-fold score cannot. A threshold placed on the former sits on memorised scores."""
    F, y = _random_features()
    s_in, _ = D.fit_lr_scores(F, y, F, oof_folds=0)
    s_oof, _ = D.fit_lr_scores(F, y, F, oof_folds=5)
    assert D._auc(s_in, y) > 0.95
    assert D._auc(s_oof, y) < 0.8


def test_zone_pipeline_default_uses_oof_thresholds(monkeypatch):
    F, y = _random_features(seed=3)
    X = np.zeros((len(y), 6, 8), np.float32)
    monkeypatch.setattr(Z, "zone_features",
                        lambda X_, g, fixed=False, raw=False, mimic_tau=None: F[:len(X_)])
    monkeypatch.setattr(Z, "score_reactance",
                        lambda X_, g, offsets=None, mimic_tau=None: np.zeros(len(X_)))
    monkeypatch.setattr(Z, "score_negseq", lambda X_: np.zeros(len(X_)))
    monkeypatch.setattr(Z, "train_cnn", lambda *a, **k: (np.zeros(len(y)), np.zeros(len(y))))
    sc = Z.score_all(X, y, X, ZoneParams(), cfg=Z.DEFAULT_CFG)
    assert D._auc(sc["engineered"][0], y) < 0.8, "training scores look in-sample: OOF not used"


def test_detect_defaults_are_fixed():
    import inspect
    assert inspect.signature(D.train_cnn).parameters["oof_folds"].default >= 2
    assert inspect.signature(D.train_cnn).parameters["norm"].default == "global"
    assert inspect.signature(D.score_engineered).parameters["oof_folds"].default >= 2
    assert inspect.signature(D.evaluate).parameters["polarity"].default == "train"
    assert Z.DEFAULT_CFG["oof_folds"] >= 2


# ------------------------------------------------------------------ mimic filter (H20)
def test_mimic_filter_removes_decaying_dc():
    g = ZoneParams()
    tau = Z.line_tau_samples(g)
    n = np.arange(4 * CYCLE)
    seq = np.array([0.0, 0.8 * np.exp(0.5j), 0.1])
    x = np.real((A_MAT @ seq)[:, None] * np.exp(1j * 2 * np.pi * n / CYCLE)[None, :])
    x = x + np.array([0.5, -0.2, 0.1])[:, None] * np.exp(-n / tau)[None, :]
    y, H = Z.mimic_filter(x, tau)
    np.testing.assert_allclose(sequence_phasors(y, CYCLE) / H, seq, atol=1e-4)
    assert np.abs(sequence_phasors(x, CYCLE) - seq).max() > 1e-2   # unfiltered is wrong
