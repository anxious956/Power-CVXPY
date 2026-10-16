"""The two-frame model (src/frames.py) and the V1-referenced fixed point (network.solve_v1ref).

  python -m pytest tests/test_frames.py -q
"""
import os, sys
import numpy as np
import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import network as nw  # noqa: E402
import frames as fr  # noqa: E402
from pscad_network import three_bus  # noqa: E402

CASES = [("L1", 0.55, "ag", 1.0), ("L2", 0.25, "ag", 0.5), ("L1", 0.95, "ab", 0.0), ("L2", 0.05, "ab", 1.0)]


@pytest.fixture(scope="module")
def fm():
    return fr.FrameModel(three_bus(), CASES, n_samples=120, seed=2)


def test_vectorised_limiter_equals_scalar():
    rng = np.random.default_rng(0)
    i1 = rng.normal(size=500) + 1j * rng.normal(size=500)
    d = 0.6 * (rng.normal(size=500) + 1j * rng.normal(size=500))
    for lim in (0, 1):
        a, b = fr.limiter_vec(i1, d, 1.2, lim)
        for k in range(0, 500, 37):
            ra, rb = nw.limiter(i1[k], d[k], 1.2, lim)
            assert abs(a[k] - ra) < 1e-12 and abs(b[k] - rb) < 1e-12


def test_vectorised_fixed_point_equals_solve_v1ref(fm):
    """The relay measurement in the relay's own pre-fault frame, from the vectorised model and from the scalar
    fixed point, agree for normal operation and for faults on both lines."""
    net = fm.net
    rng = np.random.default_rng(3)
    S = rng.uniform(-1, 1, (4, 4))
    e, ic = fm.sources(S)
    d_cmd = 0.5 * np.exp(-0.8j)
    for k in (None, 0, 1, 2):
        for j in range(len(S)):
            st = {"I": dict(ID=ic[j].real, IQ=-ic[j].imag, D2MAG=abs(d_cmd), D2ANG=float(np.degrees(np.angle(d_cmd))))}
            fault = None if k is None else (CASES[k][0], CASES[k][1], CASES[k][2], CASES[k][3] * net.rF)
            y_ref = nw.solve_v1ref(net, {"G": e[j]}, st, fault, lim=1)[0]
            yN = nw.solve_v1ref(net, {"G": e[j]}, st, None, lim=1)[0]
            ref = y_ref * np.conj(yN[0] / abs(yN[0]))
            got = fm.measure(S[j:j + 1], d_cmd, k)[0]          # a fault: the settled state, no drift
            assert np.abs(got - ref).max() < 1e-9


@pytest.mark.parametrize("d_cmd", [0j, 0.9 * np.exp(1j * np.radians(200))])
def test_sets_contain_fresh_realisations(fm, d_cmd):
    """Every fresh sample (normal and each case, through the transient window) lies in its own set with zero noise."""
    worst = fr.containment_adversarial(fm, d_cmd, n_fresh=60, face_pts=5, n_local=15, seed=11)
    assert max(worst.values()) < 1e-7, worst


def test_relay_frame_removes_the_absolute_angle(fm):
    """In the relay's own frame the pre-fault V1 at the relay is real and positive: the relay cannot see the
    absolute frame the design used to assume."""
    y = fm.measure(fm.samples[0][:50], 0.3j, None)
    assert np.all(np.abs(y[:, 0].imag) < 1e-12) and np.all(y[:, 0].real > 0)


def test_remainder_is_small_after_fit_and_split(fm):
    """With the near-minimax linear part, the transient and the reference rotation as shared symbols and the split
    box, the remainder box stays well inside the noise box (review: 2.8 eps before, about 0.4 eps after)."""
    for d_cmd in (0j, 0.9 * np.exp(1j * np.radians(200))):
        for case in (None, 0, 1, 2, 3):
            for c, G in fm.zonotopes(d_cmd, case):
                r = np.abs(G[:, -12:]).sum(1)                   # the remainder box, per component
                assert r.max() < 1.1 * fm.eps, (d_cmd, case, r.max() / fm.eps)   # raw remainder below eps, times the 1.1 factor


def test_fixed_point_raises_without_convergence():
    import network as nw2
    net = three_bus()
    m = fr.FrameModel(net, CASES[:1], n_samples=5)
    with pytest.raises(RuntimeError):
        fr.fixed_point(m.maps_N[1], np.ones(3, complex), np.ones(3, complex) * 0.4, 0j, 1.2, 1, np.ones(3, complex), iters=1, tol=0.0)
