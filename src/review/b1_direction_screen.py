"""Direction screening for three-phase faults, a follow-up of B1: can a negative-sequence injection let the relay
tell a forward three-phase fault from a reverse one, and how large must it be?

Why: on the CIGRE inverter-bus relays a passive superimposed negative-sequence element (Opoku et al. 2025) settles
direction for unbalanced faults but has nothing to measure in a three-phase fault, and 32P misses 5/14 and 12/25
in-zone three-phase faults at R1 and R3 (results/CIGREMV.md §3). A three-phase fault is a balanced shunt, so it
appears in the negative-sequence network too: an injected I2 flows towards it, and the relay's V2 and I2 respond
differently to a fault ahead and a fault behind.

Everything but the hypotheses is b1_delta_screen.py (read its docstring): the ibr_study model, the 16-real
observable and its 0.01 pu error box, the three operating points, two groundings, two inverter negative-sequence
admittances, the injection after the limiter at the same inverter (bus 3 for R1, R2, R4; bus 14 for R3) and the
|delta| x angle grid with direct solves.
  forward: three-phase faults on the protected line at 10, 50 and 85 % from the relay, R_f on the B1 grid;
  reverse: three-phase faults at the relay bus and 5, 20 and 50 % into each line behind it, R_f 0-60 ohm.
A pair is a forward and a reverse scenario at the same operating point and grounding. Cells are the R_f bands of
the forward fault; a cell's EMT count is its in-zone three-phase faults. The stop rule is B1's: if every cell with
>= 5 EMT faults needs more than 1.2 pu, an injection does not settle three-phase direction on this grid.

    python src/review/b1_direction_screen.py [cigre_R1 ...]   -> results/cigremv/b1_direction_3ph.json
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import b1_delta_screen as b1

OUT = os.path.join(cm.ROOT, "results", "cigremv", "b1_direction_3ph.json")
FT = "3ph"
M_FWD = (0.10, 0.50, 0.85)
BEHIND_AT = (0.05, 0.20, 0.50)


def direction_scenarios(cfg, nets, ibr_sets, lines):
    rb, line = cfg["relay_bus"], cfg["line"]
    u_own = lines[line][0]
    behind = [k for k, (u, v, *_) in lines.items() if rb in (u, v) and k.startswith("MainLn") and k not in (line, cfg.get("parallel"))]
    places = [(("bus", rb), 0.0, "relay bus")]
    for bl in behind:
        u, v = lines[bl][:2]
        places += [(("line", bl), x if u == rb else 1 - x, f"{bl} {int(round(x * 100))} %") for x in BEHIND_AT]
    ins, outs = [], []
    for (g, lab) in nets:
        for y2 in ibr_sets:
            for mrel in M_FWD:
                for band, rfs in b1.RF_IN.items():
                    ins += [dict(g=g, op=lab, y2=y2, ft=FT, m_rel=mrel, band=band, rf=rf, where=("line", line),
                                 m=mrel if u_own == rb else 1 - mrel) for rf in rfs]
            for pi, (where, m, place) in enumerate(places):
                outs += [dict(g=g, op=lab, y2=y2, ft=FT, where=where, m=m, place=place, rf=float(rf), ri=j,
                              fam=f"{g}|{lab}|{y2}|{pi}") for j, rf in enumerate(b1.RF_OUT)]
    return ins, outs


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    names = [a for a in sys.argv[1:] if a in b1.RELAYS] or list(b1.RELAYS)
    L, G = b1.grid_data()
    res = []
    for n in names:
        r = b1.screen(n, L, G, scenarios=direction_scenarios, ftypes=(FT,))
        r["hypotheses"] = dict(forward=f"three-phase faults on {r['line']} at {list(M_FWD)} from the relay",
                               reverse=f"three-phase faults at {r['relay_bus']} and {list(BEHIND_AT)} into each line behind it")
        res.append(r)
    out = dict(script="b1_direction_screen.py", commit=cm.git_commit(), eps=list(b1.EPS), eps_headline=b1.EPS_HEAD,
               note="need fields are the smallest |delta| on the grid that separates; null = none up to the largest magnitude",
               m_forward=list(M_FWD), behind_at=list(BEHIND_AT), rf_in=b1.RF_IN,
               rf_out=[float(b1.RF_OUT[0]), float(b1.RF_OUT[-1]), len(b1.RF_OUT)],
               delta_magnitudes_pu=list(b1.MAGS), delta_angles_deg=[float(a) for a in np.degrees(b1.ANGS)],
               rf_window=b1.WINDOW, min_emt_per_cell=b1.MIN_EMT, relays={r["relay"]: r for r in res})
    if os.path.exists(OUT) and len(names) < len(b1.RELAYS):
        prev = json.load(open(OUT, encoding="utf-8"))
        prev["relays"].update(out["relays"]); out["relays"] = prev["relays"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    print("saved", OUT)
