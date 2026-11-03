"""src/ieee14.py: the Appendix A matrices against the sequence-domain solver of src/network.py, and the LP."""
import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import ieee14 as ie  # noqa: E402
import network as nw  # noqa: E402


def _seq_net(cs):
    lines = {f"L{a}_{b}": nw.Line(a, b, complex(r, x), complex(r, x)) for a, b, r, x, _ in ie.BRANCHES}
    ibrs = {f"I{b}": nw.IBR(b, cs["i0"][k], neg_z=1e12, zero_z=1e12) for k, b in enumerate(cs["ibr"])}
    sgs = {f"G{b}": nw.SG(b, {1: 1e-9j, 2: 1e-9j, 0: 1e-9j}, cs["e0"][k]) for k, b in enumerate(cs["sg"])}
    loads = {b: {1: y, 2: y, 0: y} for b, y in cs["loads"].items()}
    return nw.Network(lines, sgs=sgs, ibrs=ibrs, loads=loads, relay=("L2_3", "a"))


def _phase(seq3):                               # network.solve order (+, -, 0) -> phases
    p, n, z = seq3
    return ie.A @ np.array([z, p, n])


def _check(which, eta, scen):
    cs = ie.case(which)
    delta = 0.3 - 0.2j
    x0, _ = ie.source_vector(cs, delta)
    m = ie.net_matrices(cs, eta)
    net = _seq_net(cs)
    vals = {f"I{b}": cs["i0"][k] for k, b in enumerate(cs["ibr"])}
    vals.update({f"G{b}": cs["e0"][k] for k, b in enumerate(cs["sg"])})
    dels = {f"I{b}": delta for b in cs["ibr"]}
    fault = None if eta is None else ("L2_3", 0.5, scen, 0.5)
    y = nw.solve(net, vals, dels, fault)
    vL, iL = _phase(y[:3]), _phase(y[3:])
    assert np.allclose(m["Phi"] @ x0, vL, atol=1e-6), (m["Phi"] @ x0, vL)
    assert np.allclose(m["Gamma"] @ x0, iL, atol=1e-6), (m["Gamma"] @ x0, iL)


def test_matrices_match_sequence_solver():
    for which in ("vid", "ivc"):
        _check(which, None, None)
        _check(which, "ag", "ag")
        _check(which, "bc", "ab")              # network.py's "ab" is symmetric about phase A: b-c


def test_rotated_models_are_rotations():
    """bg, cg (bc, ca) are ag (ab) with the phases rotated: the same |i_F| for a balanced source set."""
    cs = ie.case("vid")
    x0, _ = ie.source_vector(cs, 0.0)
    mods = ie.models(cs)
    za = (mods["ag"]["psi"] @ (mods["ag"]["Gamma"] @ x0))
    zb = (mods["bg"]["psi"] @ (mods["bg"]["Gamma"] @ x0))
    assert np.isclose(abs(za[0]), abs(zb[0]), rtol=1e-9)


def test_pair_with_itself_is_never_separated():
    cs = ie.case("vid")
    mods = ie.models(cs)
    x0, M = ie.source_vector(cs, 1.0 + 0.5j)
    assert not ie.separated(mods, ("ag", "ag"), x0, M)
