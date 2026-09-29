"""Tests for the setting-study network with inverters (src/review/ibr_study.py). No cache needed.

    python -m pytest tests/test_ibr_study.py -q
"""
import os, sys
import numpy as np
import pytest

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC)

from review import setting_study as ss
from review import ibr_study as ib

UB = 20e3
A = np.exp(2j * np.pi / 3)


def _net():
    """Three buses in a row, a grid behind a Dyn transformer at bus 1, a load at bus 3."""
    main = ["MainBus1", "MainBus2", "MainBus3"]
    lines = {"L12": ("MainBus1", "MainBus2", 2.2 + 3.1j, 3.6 + 7.0j),
             "L23": ("MainBus2", "MainBus3", 1.4 + 1.5j, 2.3 + 3.5j)}
    grids = [("MainBus1", 0.1 + 1.9j, 0.2 + 1.6j + 3.0, UB / np.sqrt(3))]
    loads = {"MainBus3": np.conj(complex(8e6, 2e6)) / UB**2}
    return main, lines, grids, loads


def _ibr(p=0.0, q=0.0, k1=0.0, y2=0j, imax=1.2):
    return dict(node="Bus3IBR", bus="MainBus3", sn=15e6, imax=imax, z_reactor=0.03 + 1.6j, p=p, q=q, k1=k1, y2=y2,
                deadband=0.05, i_base=15e6 / (np.sqrt(3) * UB), v_base=UB / np.sqrt(3))


CASES = [(("line", "L23"), ft, rf, m) for ft in ("lg", "ll", "llg", "3ph") for rf in (0.0, 5.0, 40.0) for m in (0.2, 0.7)] + \
        [(("bus", "MainBus2"), ft, 2.0, 0.0) for ft in ("lg", "ll", "llg", "3ph")]


@pytest.mark.parametrize("where,ft,rf,m", CASES)
def test_without_inverters_it_is_setting_study(where, ft, rf, m):
    ref = ss.solve_fault(_net(), "MainBus1", "L12", where, ft, rf, m)
    got = ib.solve_fault(_net(), [], "MainBus1", "L12", where, ft, rf, m)
    for a, b in zip(ref, got):
        assert np.allclose(a, b, rtol=1e-9, atol=1e-9)


@pytest.mark.parametrize("where,ft,rf,m", CASES[:8])
def test_an_idle_inverter_changes_nothing(where, ft, rf, m):
    ref = ib.solve_fault(_net(), [], "MainBus1", "L12", where, ft, rf, m)
    got = ib.solve_fault(_net(), [_ibr()], "MainBus1", "L12", where, ft, rf, m)
    for a, b in zip(ref, got):
        assert np.allclose(a, b, rtol=1e-7, atol=1e-6)


def test_prefault_dispatch_is_delivered():
    g = _ibr(p=12e6, q=-1e6)
    nodes, ix, V, J1, pre = ib.prefault(_net(), [g])
    vt = V[ix["MainBus3"]] + g["z_reactor"] * J1[0]
    s = 3 * vt * np.conj(J1[0])
    assert abs(s - complex(12e6, -1e6)) < 1e3


@pytest.mark.parametrize("ft", ["lg", "ll", "llg", "3ph"])
def test_phase_current_never_exceeds_the_limit(ft):
    g = _ibr(p=12e6, q=0.0, k1=2.0, y2=0.3 - 3.0j)
    *_, info = ib.solve_fault(_net(), [g], "MainBus1", "L12", ("line", "L23"), ft, 0.0, 0.5, return_ibr=True)
    i1, i2 = info["J1"][0] / g["i_base"], info["J2"][0] / g["i_base"]
    peak = max(abs(i1 + i2), abs(A**2 * i1 + A * i2), abs(A * i1 + A**2 * i2))
    assert peak <= g["imax"] + 1e-3


def test_limiter_trims_active_before_reactive():
    ip, s = ib._limit(0.8, 0.9, 0j, 1.2)
    assert s == 1.0 and 0.0 <= ip < 0.8 and np.isclose(np.hypot(ip, 0.9), 1.2, atol=1e-6)
    ip, s = ib._limit(0.8, 1.5, 0j, 1.2)
    assert ip == 0.0 and np.isclose(1.5 * s, 1.2, atol=1e-6)


def test_default_relay_profile_is_the_legacy_transmission_constants():
    from review import ladder as ld
    p = ld.profile(dict(cfg={}))
    assert (p["ct_primary_a"], p["arc_length_m"], p["r_ground"], p["i_thermal_per_conductor"]) == \
           (ld.IN_A, ld.ARC_LENGTH_M, ld.R_TOWER, ld.I_THERMAL_PER_CONDUCTOR)
    assert p["min_i_peak"] == ld.MIN_I_PEAK
