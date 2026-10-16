"""Round 2, findings 8-10: do PR #40's guards raise on bad input and stay quiet on the networks in use?

    python review/checks/check_guards.py
"""
import os, sys, copy
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(ROOT, "src", "review"))
import network as nw  # noqa: E402
from pscad_network import make_spec, three_bus  # noqa: E402
from pscad_network_check import assert_single_branch  # noqa: E402


def raises(fn, exc=Exception):
    try:
        fn()
        return "no"
    except exc as e:
        return f"yes ({type(e).__name__})"


def variant(f):
    n = three_bus()
    n = nw.Network(dict(n.lines), copy.deepcopy(n.sgs), copy.deepcopy(n.ibrs), copy.deepcopy(n.loads), n.relay, n.eps, n.rF)
    f(n)
    return n


rows = []
# 8: make_spec
rows.append(("make_spec, three-bus as used", raises(lambda: make_spec("x", three_bus()))))
rows.append(("make_spec, SG z2 != z1", raises(lambda: make_spec("x", variant(lambda n: n.sgs["G"].zs.__setitem__(2, 0.3j))))))
rows.append(("make_spec, inverter neg_z = 0.5 pu", raises(lambda: make_spec("x", variant(lambda n: setattr(n.ibrs["I"], "neg_z", 0.5))))))
rows.append(("make_spec, load y2 != y1", raises(lambda: make_spec("x", variant(lambda n: n.loads["R"].__setitem__(2, 0.1))))))
# 9: network.solve / closest / noise_to_normal
net = three_bus()
for m in (0.0, 1.0, 1e-9, 0.5):
    rows.append((f"solve, fault at m = {m}", raises(lambda m=m: nw.solve(net, fault=("L1", m, "ag", 0.0)))))
ms = nw.NetModelSet(net, [("L1", 0.55, "ag", 1.0)], mode="outer")
huge = 2.0 * np.exp(0.3j)                                   # no modelled current fits beside it: limit set empty
rows.append(("closest, empty limited set", raises(lambda: nw.closest(ms, ms.faults[0], huge, nw.limit_rows(ms, "I", huge)))))
rows.append(("closest, normal call", raises(lambda: nw.closest(ms, ms.faults[0], 0.9 * np.exp(3.665j), nw.limit_rows(ms, "I", 0.9 * np.exp(3.665j))))))
y = nw.solve(net)
rows.append(("noise_to_normal, empty limited set", raises(lambda: nw.noise_to_normal(ms, y, huge, nw.limit_rows(ms, "I", huge)))))
rows.append(("noise_to_normal, normal call", raises(lambda: nw.noise_to_normal(ms, y, 0j, nw.limit_rows(ms, "I", 0j)))))
# 10: assert_single_branch
rows.append(("assert_single_branch, three-bus as used", raises(lambda: assert_single_branch(three_bus()))))
rows.append(("assert_single_branch, load at the relay bus", raises(lambda: assert_single_branch(variant(lambda n: n.loads.__setitem__("L", {1: 0.1, 2: 0.1, 0: 0.0}))))))
rows.append(("assert_single_branch, second line at the relay bus", raises(lambda: assert_single_branch(
    variant(lambda n: n.lines.__setitem__("L3", nw.Line("L", "S", 0.03 + 0.3j, 0.09 + 0.9j)))))))
rows.append(("assert_single_branch, relay at end b (bus R: load, inverter, L2)", raises(lambda: assert_single_branch(
    variant(lambda n: setattr(n, "relay", ("L1", "b")))))))
rows.append(("assert_single_branch, SECOND SG at the relay bus", raises(lambda: assert_single_branch(
    variant(lambda n: n.sgs.__setitem__("G2", nw.SG("L", {1: 0.5j, 2: 0.5j, 0: 1.0j}, 1.0)))))))
rows.append(("assert_single_branch, no SG at the relay bus (SG moved to S)", raises(lambda: assert_single_branch(
    variant(lambda n: setattr(n.sgs["G"], "bus", "S"))))))
for name, r in rows:
    print(f"  raises: {r:22s} {name}")
