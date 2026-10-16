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
    return fr.FrameModel(three_bus(), CASES, n_samples=150, seed=2)


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
            if k is None:
                got = fm.measurements(S[j:j + 1], d_cmd, None)[0]
            else:
                got = fm.measurements(S[j:j + 1], d_cmd, k, transient=False)[1]     # middle of the drift set = no drift
            assert np.abs(got - ref).max() < 1e-9


@pytest.mark.parametrize("d_cmd", [0j, 0.9 * np.exp(1j * np.radians(200))])
def test_sets_contain_fresh_realisations(fm, d_cmd):
    """Every fresh sample (normal and each case, through the transient window) lies in its own set with zero noise."""
    worst = fr.containment(fm, d_cmd, n_fresh=80, seed=11)
    assert max(worst.values()) < 1e-7, worst


def test_relay_frame_removes_the_absolute_angle(fm):
    """In the relay's own frame the pre-fault V1 at the relay is real and positive: the relay cannot see the
    absolute frame the design used to assume."""
    y = fm.measurements(fm.S[:50], 0.3j, None)
    assert np.all(np.abs(y[:, 0].imag) < 1e-12) and np.all(y[:, 0].real > 0)
