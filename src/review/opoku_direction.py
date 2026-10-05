"""A passive baseline for the direction question: the superimposed negative-sequence admittance element of
Opoku, Dimitrovski & Ferrari (IEEE Access 13:7094-7109, 2025; papers/notes/G3_injection_distribution.md),
beside the repo's 32P/32Q (ladder.directional), on the four CIGRE MV relays and TestGrid A/B.

Why: at the CIGRE inverter buses 32P/32Q is wrong in both directions (results/cigremv/TABLES.md H). Before an
injected signal is argued for direction, a passive element designed for IBR feeders has to be tried on the
same records.

ELEMENT (their eqs. 11-15)  dY2 = (I2 - I2m) / (V2 - V2m), the memory one cycle before. Forward when
|dY2| > Y_set and 45 deg < arg dY2 < 225 deg; anything else is reverse. Enabled for unbalanced faults,
|I2| / |I1| >= 0.1. Here the memory is the pre-fault cycle the repo already uses (ending 20 ms before
inception), the window ends 20 or 40 ms after inception, and the phasors are exactly those of the 32P/32Q
supervision (ladder.pack: relay front end, mimic on the current). Current is measured into the protected
line, as in ladder.directional, so a forward fault gives dY2 = -1/Z2(behind), about 100 deg for an
inductive source. The paper does not state the per-unit base of Y_set: the angle test is reported alone
(Y_set = 0) and with Y_set = 0.1 / 0.4 / 1 pu on a per-grid base (20 kV, 15 MVA on CIGRE as in B1;
110 kV, 100 MVA on TestGrid).

BALANCED FAULTS (our extension, not in the paper)  The same test on positive-sequence superimposed quantities,
dY1 = dI1 / dV1 with the same sector, for events the dY2 element does not enable (|I2| < 0.1 |I1|). Two fault
detectors are compared: |dI1| >= 0.2 In (the relay's CT primary), which misses the high-R_f faults an inverter-fed
relay sees, and a positive-sequence voltage change |dV1| >= 5 % of nominal. "dY2 + dY1" uses dY2 when it is enabled
and dY1 with the voltage detector otherwise. "dY2 or dY1" calls forward when either does; it was chosen AFTER seeing
that a three-phase fault's first-cycle transient can enable dY2 with a wrong angle (6 of 25 at R3), so read it as a
post-hoc rule.

CLASSES  in-zone faults and the faults beyond the remote bus are forward; relay-bus faults and faults on the
lines behind are reverse; switching events (an inverter disconnecting, load and capacitor switching) must not
be called forward. Dependability is reported over all faults and over unbalanced faults only, because the
element is defined for unbalanced faults.

    python src/review/opoku_direction.py [relay ...]      -> results/cigremv/opoku_direction.json
"""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import frontend
from review import ladder as ld

OUT = os.path.join(cm.ROOT, "results", "cigremv", "opoku_direction.json")
RELAYS = ("cigre_R1", "cigre_R2", "cigre_R3", "cigre_R4", "adapt_A", "adapt_B")
T_MS = (20, 40)
PHI = 45.0
I2_I1_MIN = 0.1
Y_SETS = (0.0, 0.1, 0.4, 1.0)
BASE = {"cigre": (20e3, 15e6), "adapt": (110e3, 100e6)}          # (V_LL, S) for the per-unit Y_set
FORWARD = ("pos", "own99", "remote_bus_faults", "beyond")
REVERSE = ("reverse_bus", "reverse_lines")


def kn(dec, m):
    return dict(k=int((dec & m).sum()), n=int(m.sum()))


def evaluate(R, t):
    n = len(R["et"])
    sel = np.arange(n)
    P = ld.pack(R, sel, t, "full", True)
    vpre, vpost, ipre, ipost, _ = P
    d32 = ld.directional(*P, R["z1L"], in_a=ld.profile(R)["ct_primary_a"])
    dI2, dV2 = ipost[:, 2] - ipre[:, 2], vpost[:, 2] - vpre[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        Y = np.where(np.abs(dV2) > 0, dI2 / dV2, np.nan)
    v_ll, s_base = BASE["cigre" if R["name"].startswith("cigre") else "adapt"]
    y_pu = np.abs(Y) * v_ll ** 2 / s_base
    ang = np.degrees(np.angle(Y)) % 360
    enabled = np.abs(ipost[:, 2]) >= I2_I1_MIN * np.abs(ipost[:, 1])
    fwd_ang = enabled & (ang > PHI) & (ang < 180 + PHI)
    dy = {f"Y_set={y}": fwd_ang & (y_pu > y) for y in Y_SETS}
    dI1, dV1 = ipost[:, 1] - ipre[:, 1], vpost[:, 1] - vpre[:, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        ang1 = np.degrees(np.angle(np.where(np.abs(dV1) > 0, dI1 / dV1, np.nan))) % 360
    sector1 = (ang1 > PHI) & (ang1 < 180 + PHI)
    dy1_i = ~enabled & (np.abs(dI1) >= 0.2 * ld.profile(R)["ct_primary_a"] * np.sqrt(2)) & sector1
    dy1 = ~enabled & (np.abs(dV1) >= 0.05 * R["v_nom_peak"]) & sector1
    unbal = np.isin(R["et"], [e for e in np.unique(R["et"]) if ("1phg" in e or "2ph" in e)])
    elements = {"32P/32Q": d32, **{f"dY2 {k}": v for k, v in dy.items()}, "dY1, current detector (balanced only)": dy1_i,
                "dY1, voltage detector (balanced only)": dy1,
                "dY2 + dY1": dy["Y_set=0.0"] | dy1,
                "dY2 or dY1": dy["Y_set=0.0"] | ((np.abs(dV1) >= 0.05 * R["v_nom_peak"]) & sector1)}
    out = dict(t_ms=t, elements={})
    for name, dec in elements.items():
        e = dict()
        for c in FORWARD + REVERSE:
            e[c] = kn(dec, R[c])
            if c in ("pos",) + REVERSE:
                e[c + "_unbalanced"] = kn(dec, R[c] & unbal)
                e[c + "_balanced"] = kn(dec, R[c] & ~unbal)
                e[c + "_by_rf_bin"] = {b: kn(dec, R[c] & (R["rf_bin"] == b)) for b in cm.RF_LABELS}
        sw = R["switching"]
        e["switching"] = kn(dec, sw)
        e["switching_by_event"] = {f"{a}|{b}": kn(dec, sw & (R["et"] == a) & (R["tgt"] == b))
                                   for a, b in sorted(set(zip(R["et"][sw], R["tgt"][sw])))}
        out["elements"][name] = e
    # what the element sees: dY2 magnitude and angle by class (medians and the share inside the forward sector)
    out["dY2_by_class"] = {c: dict(n=int(R[c].sum()), enabled=float(enabled[R[c]].mean()) if R[c].any() else None,
                                   median_abs_pu=float(np.nanmedian(y_pu[R[c] & enabled])) if (R[c] & enabled).any() else None,
                                   share_in_forward_sector=float(fwd_ang[R[c] & enabled].mean()) if (R[c] & enabled).any() else None)
                           for c in FORWARD + REVERSE + ("switching",)}
    return out


def main(relays):
    frontend.enable()
    res = dict(script="opoku_direction.py", commit=cm.git_commit(), phi_deg=PHI, i2_over_i1_min=I2_I1_MIN,
               y_set_pu=list(Y_SETS), base={k: dict(v_ll=v[0], s=v[1]) for k, v in BASE.items()}, relays={})
    if os.path.exists(OUT):
        res["relays"] = json.load(open(OUT, encoding="utf-8")).get("relays", {})
    for name in relays:
        R = cm.load_relay(name)
        r = res["relays"][name] = {f"t={t}": evaluate(R, t) for t in T_MS}
        e20 = r["t=20"]["elements"]
        for el in ("32P/32Q", "dY2 Y_set=0.0", "dY2 + dY1", "dY2 or dY1"):
            e = e20[el]
            print(f"[{name}] 20 ms {el:16s} in-zone fwd {e['pos']['k']}/{e['pos']['n']} (unbal {e['pos_unbalanced']['k']}/{e['pos_unbalanced']['n']})"
                  f"  relay-bus fwd {e['reverse_bus']['k']}/{e['reverse_bus']['n']}  behind fwd {e['reverse_lines']['k']}/{e['reverse_lines']['n']}"
                  f"  beyond fwd {e['beyond']['k']}/{e['beyond']['n']}  switching fwd {e['switching']['k']}/{e['switching']['n']}", flush=True)
        del R
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1)
    print("saved", OUT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("relays", nargs="*", default=list(RELAYS))
    main(tuple(ap.parse_args().relays))
