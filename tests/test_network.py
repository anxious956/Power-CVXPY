"""The multi-bus design tool (src/network.py) against the two hand-written models it generalises.

  python -m pytest tests/test_network.py -q
"""
import os, sys
import numpy as np
import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "review"))
import network as nw  # noqa: E402
import aux_model as am  # noqa: E402
import zone_model as zm  # noqa: E402
from wp1_common import ModelSet, affine_case  # noqa: E402
import tac25_design as td  # noqa: E402


def two_bus(p: am.Params, i_max=None):
    ibrs = {}
    sgs = {}
    if p.local == "SG":
        sgs["G"] = nw.SG("L", dict(p.zs), p.e0, tuple(p.gen_e))
    else:
        ibrs["IL"] = nw.IBR("L", p.iL0, tuple(p.gen_i), p.ibr_neg_z, p.ibr_zero_z)
    ibrs["I"] = nw.IBR("R", p.i0, tuple(p.gen_i), p.ibr_neg_z, p.ibr_zero_z, inject=True, i_max=i_max)
    return nw.Network(lines={"L1": nw.Line("L", "R", p.z1, p.z0)}, sgs=sgs, ibrs=ibrs, loads={"R": dict(p.yld)},
                      relay=("L1", "a"), eps=p.eps, rF=p.rF)


def three_bus(p: zm.ZoneParams):
    return nw.Network(lines={"L1": nw.Line("L", "R", p.z1, p.z0_ratio * p.z1), "L2": nw.Line("R", "S", p.z2, p.z0_ratio * p.z2)},
                      sgs={"G": nw.SG("L", dict(p.zs), p.e0)},
                      ibrs={"I": nw.IBR("R", p.i0, neg_z=p.ibr_neg_z, zero_z=p.ibr_zero_z, inject=True)},
                      loads={"R": dict(p.yR), "S": dict(p.yS)}, relay=("L1", "a"), rF=p.rF)


@pytest.mark.parametrize("preset", ["weak_sg", "all_ibr_hard"])
def test_two_bus_reproduces_aux_model(preset):
    p = am.PRESETS[preset]
    net = two_bus(p)
    rng = np.random.default_rng(0)
    local = "G" if p.local == "SG" else "IL"
    for _ in range(40):
        scen = rng.choice(["N", "ag", "ab"])
        m, mr = rng.uniform(0.05, 0.95), rng.uniform(0, 1)
        src = rng.normal() + 1j * rng.normal()
        iR, d = rng.normal() + 1j * rng.normal(), rng.normal() + 1j * rng.normal()
        ref = am.solve(p, scen, src, iR, d, m, mr)
        got = nw.solve(net, {local: src, "I": iR}, {"I": d}, None if scen == "N" else ("L1", m, scen, mr * p.rF))
        np.testing.assert_allclose(got, ref, rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("mode", ["linear", "outer"])
def test_two_bus_affine_model_matches(mode):
    p = am.PRESETS["weak_sg"]
    net = two_bus(p)
    for scen, m, mr in (("N", 0.5, 0.0), ("ag", 0.35, 1.0), ("ab", 0.95, 0.5)):
        ref = affine_case(p, scen, m, mr, mode)
        got = nw.affine_case(net, None if scen == "N" else ("L1", m, scen, mr * p.rF), mode)
        for a, b in zip(got, ref):
            np.testing.assert_allclose(a, b, rtol=1e-10, atol=1e-12)


def test_three_bus_reproduces_zone_model():
    p = zm.ZoneParams()
    net = three_bus(p)
    rng = np.random.default_rng(1)
    for kind in ("N", "ag", "ab", "ag2", "ab2"):
        for _ in range(10):
            m, mr = rng.uniform(0.05, 0.95), rng.uniform(0, 1)
            src, iR, d = (rng.normal() + 1j * rng.normal() for _ in range(3))
            ref = zm.solve_zone(p, kind, src, iR, d, m, mr)
            line = "L2" if kind.endswith("2") else "L1"
            fault = None if kind == "N" else (line, m, kind.rstrip("2"), mr * p.rF)
            got = nw.solve(net, {"G": src, "I": iR}, {"I": d}, fault)
            np.testing.assert_allclose(got, ref, rtol=1e-10, atol=1e-12)


def test_two_bus_design_matches_the_reviewed_engine():
    """Same smallest signal as review/tac25_design.min_delta, with and without the per-phase limit."""
    p = am.PRESETS["weak_sg"]
    cases = [("L1", m, s, mr) for s in p.scen for m in p.m_grid for mr in p.mr_grid]
    for i_max, lim in ((None, False), (1.2, True)):
        ms = nw.NetModelSet(two_bus(p, i_max), cases, mode="linear")
        got = nw.min_delta(ms, r_step=0.04, n_ang=36, limit_inside=lim)
        ref = td.min_delta(ModelSet(p, mode="linear"), i_max=1.2, limit_inside=lim, limit_design=False,
                           r_step=0.04, n_ang=36, r_max=2.0, limit_rule="phase")
        assert got["feasible"] == ref["feasible"]
        assert got["abs_delta"] == pytest.approx(ref["abs_delta"])
        assert got["angle_deg"] == pytest.approx(ref["angle_deg"])


def test_minkowski_aggregation_is_generator_stacking():
    """Two inverters: the normal set's generators are the two single-inverter generator sets side by side."""
    p = zm.ZoneParams()
    net = three_bus(p)
    net.ibrs["I2"] = nw.IBR("S", 0.3 * np.exp(-0.2j))
    c, H, G = nw.affine_case(net)
    assert G.shape[1] == 2 * len(net.sources) == 6
    alone = nw.affine_case(nw.Network(net.lines, net.sgs, {"I2": net.ibrs["I2"]}, net.loads, net.relay))[2]
    np.testing.assert_allclose(G[:, 4:], alone[:, 2:], rtol=1e-10, atol=1e-12)


def test_closest_witness_is_a_true_fault_realisation():
    """The fault realisation closest() returns, re-solved as a fault, sits exactly that far from the normal set.
    This is a consistency check only: it holds for either fault-block sign (review/NETWORK_REVIEW.md finding 6).
    The sign itself is tested by the two tests below."""
    p = am.PRESETS["weak_sg"]
    ms = nw.NetModelSet(two_bus(p, 1.2), [("L1", 0.95, "ag", 1.0), ("L1", 0.35, "ab", 0.5)], mode="outer")
    for f in ms.faults:
        ln, m, s, mr = f[0]
        for dv in (0j, 0.3 * np.exp(-0.6j)):
            lim = nw.limit_rows(ms, "I", dv)
            _, uF, t = nw.closest(ms, f, dv, lim)
            y = nw.solve(ms.net, nw.realisation(ms.net, uF), {"I": dv}, (ln, m, s, mr * p.rF))
            assert nw.noise_to_normal(ms, y, dv, lim) == pytest.approx(t, abs=1e-7)


def test_limiter_matches_the_emt_inverter():
    """Values measured from the PSCAD inverter (results/PSCAD_TAC25.md): I1 = 1.2 and delta = 0.34 pu at +30 deg asked."""
    for lim, (i1, d) in ((0, (0.9575, 0.2713)), (1, (0.8935, 0.3400))):
        a, b = nw.limiter(1.2 + 0j, 0.34 * np.exp(1j * np.radians(30)), 1.2, lim)
        assert abs(a) == pytest.approx(i1, abs=2e-4) and abs(b) == pytest.approx(d, abs=2e-4)


def _phase_peak(i, d):
    return max(abs(i * nw.A3 ** (-k) + d * nw.A3 ** k) for k in range(3))


def test_limit_rows_keep_every_physical_pair_and_only_with_the_right_sign():
    """Brute force on the three-bus network: every sampled (u_N, u_F) whose true inverter phase currents fit under
    the limit satisfies every row when the fault block is passed as -u_F (ModelSet.pair), and reading it as +u_F
    would cut some of them. Fails for the pre-#37 sign."""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from pscad_network import three_bus
    net = three_bus()
    ms = nw.NetModelSet(net, [("L1", 0.55, "ag", 1.0)], mode="outer")
    k = 2 * len(net.sources)
    c0, c1 = ms.generator_columns("I")
    c, g = nw.source_set(net, "ibr", "I", "outer")
    rng = np.random.default_rng(4)
    for dv in (0j, 0.6 * np.exp(1.2j), 0.9 * np.exp(1j * np.radians(210))):
        A, b = nw.limit_rows(ms, "I", dv)(k)
        kept = cut_if_flipped = 0
        for _ in range(4000):
            uN, uF = rng.uniform(-1, 1, k), rng.uniform(-1, 1, k)
            iN = c + g[0] * uN[c0] + g[1] * uN[c1]
            iF = c + g[0] * uF[c0] + g[1] * uF[c1]
            if _phase_peak(iN, dv) <= net.ibrs["I"].i_max and _phase_peak(iF, dv) <= net.ibrs["I"].i_max:
                kept += 1
                assert np.all(A @ np.concatenate([uN, -uF]) <= b + 1e-9)
                cut_if_flipped += bool(np.any(A @ np.concatenate([uN, uF]) > b + 1e-9))
        assert kept > 100
        if abs(dv) > 0:
            assert cut_if_flipped > 0, "the test would not notice a flipped fault-block sign"


def test_closest_realisations_respect_the_limit():
    """The witness closest() returns lies inside the inverter's per-phase limit (up to the 24-gon's 0.9 %)."""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from pscad_network import three_bus
    net = three_bus()
    ms = nw.NetModelSet(net, [("L1", 0.95, "ag", 1.0), ("L2", 0.25, "ag", 1.0)], mode="outer")
    for dv in (0.62 * np.exp(1j * np.radians(230)), 0.9 * np.exp(1j * np.radians(210))):
        lim = nw.limit_rows(ms, "I", dv)
        for f in ms.faults:
            uN, uF, _ = nw.closest(ms, f, dv, lim)
            for u in (uN, uF):
                i = nw.realisation(net, u)["I"]
                assert _phase_peak(i, dv) <= net.ibrs["I"].i_max / np.cos(np.pi / 24) + 1e-9
