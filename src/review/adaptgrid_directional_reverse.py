"""How often the 32P/32Q directional element calls a reverse fault forward on adapt_grid.

ADAPTGRID.md credits directional supervision with removing the reverse-bus and switching trips of the
engineered and distance detectors. That is true of the trips those detectors make, but it is not the same
as the element blocking every reverse fault. This counts, per relay, the faults 32P/32Q (ladder.directional,
the supervision adaptgrid_run applies) declares forward, by class, and breaks the reverse ones down by
fault resistance, grounding and target.

    python src/review/adaptgrid_directional_reverse.py [--frontend relayfe]
    -> results/adaptgrid/directional_reverse_<frontend>.json
"""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import frontend
from review.adaptgrid_run import bundle, supervision

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")
CLASSES = ("pos", "own99", "beyond", "remote_bus_faults", "parallel", "reverse_bus", "reverse_lines", "other")


def kn(fwd, m):
    return dict(k_forward=int((fwd & m).sum()), n=int(m.sum()))


def run_relay(relay):
    R = bundle(relay, None)
    n = len(R["et"])
    fwd = supervision(R, np.arange(n))
    out = dict(by_class={c: kn(fwd, R[c]) for c in CLASSES if c in R})
    for cls in ("reverse_bus", "reverse_lines"):
        m = R[cls]
        out[cls] = dict(
            by_rf_bin={b: kn(fwd, m & (R["rf_bin"] == b)) for b in cm.RF_LABELS},
            by_grounding={g: kn(fwd, m & (R["grounding"] == g)) for g in ("solid", "resistive", "resonant")},
            by_rf_bin_and_grounding={f"{b}|{g}": kn(fwd, m & (R["rf_bin"] == b) & (R["grounding"] == g))
                                     for b in cm.RF_LABELS for g in ("solid", "resistive", "resonant")},
            by_target={str(t): kn(fwd, m & (R["tgt"] == t)) for t in np.unique(R["tgt"][m])})
    return out


def main(fe="relayfe"):
    if fe == "relayfe":
        frontend.enable()
    res = dict(script="adaptgrid_directional_reverse", commit=cm.git_commit(), frontend=fe, t_ms=20, relays={})
    for relay in ("adapt_A", "adapt_B"):
        res["relays"][relay] = r = run_relay(relay)
        rb, rl = r["by_class"]["reverse_bus"], r["by_class"]["reverse_lines"]
        print(f"[{relay}] forward on relay-bus faults {rb['k_forward']}/{rb['n']}, on lines behind "
              f"{rl['k_forward']}/{rl['n']}; relay-bus by R_f bin "
              f"{ {b: (v['k_forward'], v['n']) for b, v in r['reverse_bus']['by_rf_bin'].items()} }", flush=True)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"directional_reverse_{fe}.json")
    json.dump(res, open(path, "w"), indent=1)
    print("saved", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", default="relayfe")
    main(ap.parse_args().frontend)
