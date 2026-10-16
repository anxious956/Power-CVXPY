"""Round 2, finding 2: does pscad_network.check_line_model accept exactly the networks on which the return-conductor
line model is exact? For each topology: the guard's verdict, and the largest error of the conductor model (what
build() makes; review/checks/check_network.phase_domain) against network.solve over random runs and faults.

    python review/checks/check_line_guard.py        (needs PR #40's src/pscad_network.py)
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(ROOT, "src", "review"))
import network as nw  # noqa: E402
from pscad_network import make_spec, check_line_model  # noqa: E402
from check_network import phase_domain  # noqa: E402

ZS = {1: 0.4j, 2: 0.4j, 0: 0.8j}


def net_of(lines, sgs=("A",), ibrs=("C",), loads=("B", "C")):
    L = {k: nw.Line(a, b, z1, r * z1) for k, (a, b, z1, r) in lines.items()}
    first = next(iter(L.values()))
    return nw.Network(lines=L, sgs={f"G{b}": nw.SG(b, dict(ZS), 1.0) for b in sgs},
                      ibrs={f"I{b}": nw.IBR(b, 0.4 * np.exp(-0.3j), (0.3, 0.3), 1e6, 1e6, inject=(b == ibrs[0])) for b in ibrs},
                      loads={b: {1: 0.3 - 0.1j, 2: 0.3 - 0.1j, 0: 0.0} for b in loads}, relay=(next(iter(L)), "a"))


z = (0.02 + 0.2j, 0.025 + 0.25j, 0.03 + 0.35j, 0.01 + 0.15j)
CASES = {
    "radial chain, ratios 3 / 4.5": dict(lines={"L1": ("A", "B", z[0], 3.0), "L2": ("B", "C", z[1], 4.5)}),
    "radial star, 2 SGs, ratios 3 / 4 / 2.5": dict(lines={"L1": ("A", "B", z[0], 3.0), "L2": ("B", "C", z[1], 4.0),
                                                          "L3": ("B", "D", z[2], 2.5)}, sgs=("A", "D")),
    "triangle, uniform 3": dict(lines={"L1": ("A", "B", z[0], 3.0), "L2": ("B", "C", z[1], 3.0), "L3": ("A", "C", z[2], 3.0)}),
    "triangle, uniform 3, 2 SGs": dict(lines={"L1": ("A", "B", z[0], 3.0), "L2": ("B", "C", z[1], 3.0),
                                              "L3": ("A", "C", z[2], 3.0)}, sgs=("A", "B")),
    "triangle, one line 4": dict(lines={"L1": ("A", "B", z[0], 3.0), "L2": ("B", "C", z[1], 3.0), "L3": ("A", "C", z[2], 4.0)}),
    "parallel pair A-B, ratios 3 / 4": dict(lines={"L1": ("A", "B", z[0], 3.0), "L2": ("A", "B", z[2], 4.0),
                                                   "L3": ("B", "C", z[1], 3.0)}),
    "triangle uniform 3 + radial spur at 4.5": dict(lines={"L1": ("A", "B", z[0], 3.0), "L2": ("B", "C", z[1], 3.0),
                                                           "L3": ("A", "C", z[2], 3.0), "L4": ("C", "D", z[3], 4.5)}),
}


def max_error(net, rng, n=25):
    worst, lines = 0.0, list(net.lines)
    for _ in range(n):
        vals = {k: (1 + 0.1 * rng.normal()) * np.exp(0.2j * rng.normal()) for k in net.sgs}
        vals.update({k: 0.5 * (rng.normal() + 1j * rng.normal()) for k in net.ibrs})
        dl = {k: 0.4 * (rng.normal() + 1j * rng.normal()) for k in net.injectors}
        scen = rng.choice(["N", "ag", "ab"])
        fault = None if scen == "N" else (lines[rng.integers(len(lines))], rng.uniform(0.05, 0.95), scen, rng.uniform(0, 1))
        ref = phase_domain(net, vals, dl, fault, True)
        worst = max(worst, np.abs(nw.solve(net, vals, dl, fault) - ref).max())
    return worst


def main():
    rng = np.random.default_rng(7)
    print(f"{'network':45s} {'guard':8s} {'max error (pu)':>14s}  verdict")
    for name, kw in CASES.items():
        net = net_of(**kw)
        try:
            loops = check_line_model(make_spec("x", net))
            guard = "meshed" if loops else "radial"
        except ValueError:
            guard = "REFUSED"
        err = max_error(net, rng)
        exact = err < 1e-5
        ok = (guard != "REFUSED") == exact
        print(f"{name:45s} {guard:8s} {err:14.2e}  "
              + ("agree" if ok else ("over-strict (exact but refused)" if exact else "UNSAFE (inexact but accepted)")))


if __name__ == "__main__":
    main()
