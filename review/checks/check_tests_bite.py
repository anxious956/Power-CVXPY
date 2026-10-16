"""Round 2, finding 6: do the sign tests of PR #40 fail when the fault-block sign is flipped? Each test is run as
is, then with the sign flipped in memory (network.limit_rows, tac25_design.limit_rows / phase_rows).

    python review/checks/check_tests_bite.py
"""
import os, sys, importlib
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in ("tests", "src", os.path.join("src", "review")):
    sys.path.insert(0, os.path.join(ROOT, p))
import network as nw  # noqa: E402
import tac25_design as td  # noqa: E402
tn = importlib.import_module("test_network")
tt = importlib.import_module("test_tac25")

orig_nw, orig_lr, orig_pr = nw.limit_rows, td.limit_rows, td.phase_rows


def nw_flipped(ms, inj, dv, n_poly=24):
    rows = orig_nw(ms, inj, dv, n_poly)

    def r(k):
        A, b = rows(k)
        A = A.copy(); A[:, k:] *= -1
        return A, b
    return r


def run(fn):
    try:
        fn()
        return "passes"
    except AssertionError as e:
        return f"FAILS ({str(e)[:60] or 'assert'})"


TESTS = [("test_network", tn.test_limit_rows_keep_every_physical_pair_and_only_with_the_right_sign),
         ("test_network", tn.test_closest_realisations_respect_the_limit),
         ("test_network", tn.test_closest_witness_is_a_true_fault_realisation),
         ("test_tac25", tt.test_limit_rows_follow_the_pair_sign_convention)]
for mod, fn in TESTS:
    a = run(fn)
    nw.limit_rows = nw_flipped
    td.limit_rows = lambda *x, **k: orig_lr(*x, **{**k, "fault_sign": +1.0})
    td.phase_rows = lambda *x, **k: orig_pr(*x, **{**k, "fault_sign": +1.0})
    b = run(fn)
    nw.limit_rows, td.limit_rows, td.phase_rows = orig_nw, orig_lr, orig_pr
    print(f"{mod}::{fn.__name__}\n    correct sign: {a}\n    flipped sign: {b}")
