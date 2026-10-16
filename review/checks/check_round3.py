"""Round 3 (PR #40 after 6cfff4e): do the two new regression tests fail on the old code, does the new fingerprint
still accept the 128 stored runs and reject a changed build, and does assert_single_branch catch the SG cases?

    python review/checks/check_round3.py
"""
import os, sys, json, copy, importlib
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in ("tests", "src", os.path.join("src", "review")):
    sys.path.insert(0, os.path.join(ROOT, p))
import network as nw  # noqa: E402
import tac25_design as td  # noqa: E402
import real_ml  # noqa: E402
import pscad_network as pn  # noqa: E402
from pscad_network_check import assert_single_branch  # noqa: E402
from waveforms import CYCLE, EVENT  # noqa: E402


def run(fn, *a):
    try:
        fn(*a)
        return "passes"
    except AssertionError:
        return "FAILS"


# 1. test_channels_lp_uses_its_own_fault_sign with the channels call forced back to -1
tt = importlib.import_module("test_tac25")
orig = td.limit_rows
print("test_channels_lp_uses_its_own_fault_sign: as is", run(tt.test_channels_lp_uses_its_own_fault_sign), end="; ")
td.limit_rows = lambda *a, **k: orig(*a, **{**k, "fault_sign": -1.0})
print("with fault_sign forced to -1:", run(tt.test_channels_lp_uses_its_own_fault_sign))
td.limit_rows = orig

# 2. test_phasor_view_keeps_one_frame_at_any_decision_time with the pre-#40 shift
ts = importlib.import_module("test_synth")
new_pv = real_ml.phasor_view


def old_pv(R, idx, t_ms):
    ev = R["ev"]
    n_post = int(round(t_ms * real_ml.FS / 1000))
    out = np.zeros((len(idx), 6, 1024))
    pre = ev - 2 * CYCLE - (n_post % CYCLE)
    out[:, :, EVENT - 2 * CYCLE:EVENT - CYCLE] = R["full"][idx, :, pre:pre + CYCLE]
    out[:, :, EVENT + CYCLE:EVENT + 2 * CYCLE] = R["full"][idx, :, ev + n_post - CYCLE:ev + n_post]
    return out


for lab, pv in (("new shift", new_pv), ("old shift", old_pv)):
    real_ml.phasor_view = pv
    res = {t: run(ts.test_phasor_view_keeps_one_frame_at_any_decision_time, t) for t in (10, 15, 20, 25, 30, 35, 40, 50)}
    print(f"test_phasor_view_keeps_one_frame ({lab}):", ", ".join(f"{t} ms {r}" for t, r in res.items()))
real_ml.phasor_view = new_pv

# 3. fingerprint
specs = json.load(open(os.path.join(ROOT, "results", "network", "three_bus_design.json")))
print("stored runs reusable under the new digest:", sum(pn.reusable(s) for s in specs), "of", len(specs))
ba, bv = dict(pn.BUILD_ARGS), pn.BUILD_VERSION
pn.BUILD_ARGS["dt_us"] = 5.0
print("  with dt_us changed:", sum(pn.reusable(s) for s in specs), end="; ")
pn.BUILD_ARGS.clear(); pn.BUILD_ARGS.update(ba); pn.BUILD_VERSION = bv + 1
print("with BUILD_VERSION bumped:", sum(pn.reusable(s) for s in specs))
pn.BUILD_VERSION = bv
print("  build() defaults equal BUILD_ARGS:",
      dict(zip(("t_fault", "dur", "t_end", "dt_us"), pn.build.__defaults__)) == pn.BUILD_ARGS)


# 4. assert_single_branch
def variant(f):
    n = pn.three_bus()
    n = nw.Network(dict(n.lines), copy.deepcopy(n.sgs), copy.deepcopy(n.ibrs), copy.deepcopy(n.loads), n.relay, n.eps, n.rF)
    f(n)
    return n


for lab, net in (("three-bus as used", pn.three_bus()),
                 ("second SG at the relay bus", variant(lambda n: n.sgs.__setitem__("G2", nw.SG("L", {1: 0.5j, 2: 0.5j, 0: 1j}, 1.0)))),
                 ("no SG at the relay bus", variant(lambda n: setattr(n.sgs["G"], "bus", "S"))),
                 ("SG renamed to 'X'", variant(lambda n: n.sgs.__setitem__("X", n.sgs.pop("G"))))):
    try:
        print(f"assert_single_branch, {lab}: returns {assert_single_branch(net)!r}")
    except AssertionError:
        print(f"assert_single_branch, {lab}: raises")
