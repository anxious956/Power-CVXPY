"""Can standard supervision tell an inverter disconnecting from a forward fault? The last open direction-side
failure on the CIGRE MV feeder.

At R2 and R4 the bus-3 inverter tripping is called forward by every direction element tried, including the
passive superimposed elements that settle direction for faults (results/CIGREMV.md §3; opoku_direction.py).
Losing 12 MW of in-feed at bus 3 is a real forward step at bus 2: |dV1| 9-11 %, |dI1| 0.6-0.7 In, and some
negative sequence. This script asks whether a supervising condition a protection engineer would set without
looking at the events removes those trips and keeps the in-zone faults.

DIRECTION  "dY2 or dY1" from opoku_direction.py (20 ms, pre-fault reference).
SUPERVISION, each set from engineering rules, not from the trip events:
  I1 above load   |I1| >= k * I_load, I_load = the largest relay current with the feeder's inverter offline (bus 3
                  for R1, R2, R4; bus 14 for R3), from the
                  ibr_study load flow at the simulation with the largest total load (k = 1.0, 1.2).
  SEL PSV50       block when 32P is forward, 32Q is not and |I1| < 1.2 IMAX (IMAX = 1.3 x the inverter rating),
                  adapted from Chowdhury & Fischer (WPRC 2021) to the remote inverter.
  zero sequence   |dV0| >= 5 % of nominal or |dI0| >= 0.05 In: the inverter has no zero-sequence path, so a
                  disconnection changes neither; ground faults change one of them (resonant grounding aside).
  combined        zero sequence OR I1 above load (k = 1.2).

    python src/review/inverter_trip_supervision.py [relay ...]   -> results/cigremv/inverter_trip_supervision.json
"""
import os, sys, json, glob, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import frontend
from review import ladder as ld
from review import setting_study as ss
from review import ibr_study as ib
import real_zone

OUT = os.path.join(cm.ROOT, "results", "cigremv", "inverter_trip_supervision.json")
RELAYS = ("cigre_R1", "cigre_R2", "cigre_R3", "cigre_R4")
UB, S_IBR = 20e3, 15e6
TRIP_BUS = {"cigre_R1": "MainBus3", "cigre_R2": "MainBus3", "cigre_R3": "MainBus14", "cigre_R4": "MainBus3"}   # the inverter on the relay's feeder


def load_current_inverter_off(name, R):
    """Largest |I1| through the relay (A peak) with its feeder's inverter offline, from the load flow at the
    simulation with the largest total load."""
    cfg = real_zone.CONFIGS[name]
    L, G = R["labels"], R["graph"]
    lb = {}
    for n_, a in G.nodes(data=True):
        if str(n_).startswith("MainBus"):
            for key in a:
                if key.startswith("Ld") and key.endswith("_param_dict") and not key.endswith("_typ_param_dict"):
                    lb[key[:-len("_param_dict")]] = str(n_)
    lds = [ld_ for ld_ in lb if f"loads/{ld_}/load_p" in L]
    total = np.sum([L[f"loads/{x}/load_p"].to_numpy(float) for x in lds], axis=0)
    i = int(np.argmax(total))
    loads = {}
    for x in lds:
        P, Q = loads.get(lb[x], (0.0, 0.0))
        loads[lb[x]] = (P + float(L[f"loads/{x}/load_p"].iloc[i]), Q + float(L[f"loads/{x}/load_q"].iloc[i]))
    usetp = float(L["ExtGrid/usetp"].iloc[i]) if "ExtGrid/usetp" in L else 1.0
    net = ib.with_operating_point(ss.build(G, ub=UB, grounding=None, open_ends=cfg.get("open_line_ends")), UB, loads, usetp)
    ibrs = [g for g in ib.inverters_from_graph(G, UB, ib.load_characterisation()) if g["bus"] != TRIP_BUS[name]]
    nodes, ix, V, J1, pre = ib.prefault(net, ibrs)
    u, v, zl1, _ = net[1][cfg["line"]]
    far = v if u == cfg["relay_bus"] else u
    return float(abs((V[ix[cfg["relay_bus"]]] - V[ix[far]]) / zl1)) * np.sqrt(2), float(total[i])


def kn(dec, m):
    return dict(k=int((dec & m).sum()), n=int(m.sum()))


def evaluate(name, R):
    n = len(R["et"]); sel = np.arange(n)
    vpre, vpost, ipre, ipost, vmem = ld.pack(R, sel, 20, "full", True)
    In = ld.profile(R)["ct_primary_a"] * np.sqrt(2); Vn = R["v_nom_peak"]
    imax = 1.3 * S_IBR / (np.sqrt(3) * UB) * np.sqrt(2)
    # direction: dY2 or dY1 (opoku_direction.py)
    with np.errstate(divide="ignore", invalid="ignore"):
        a2 = np.degrees(np.angle((ipost[:, 2] - ipre[:, 2]) / (vpost[:, 2] - vpre[:, 2]))) % 360
        a1 = np.degrees(np.angle((ipost[:, 1] - ipre[:, 1]) / (vpost[:, 1] - vpre[:, 1]))) % 360
    en2 = np.abs(ipost[:, 2]) >= 0.1 * np.abs(ipost[:, 1])
    dv1 = np.abs(vpost[:, 1] - vpre[:, 1])
    fwd = (en2 & (a2 > 45) & (a2 < 225)) | ((dv1 >= 0.05 * Vn) & (a1 > 45) & (a1 < 225))
    # supervision
    i_load, p_max = load_current_inverter_off(name, R)
    I1 = np.abs(ipost[:, 1])
    _, d32p, d32q, unbal = ld.directional(vpre, vpost, ipre, ipost, vmem, R["z1L"], parts=True, in_a=ld.profile(R)["ct_primary_a"])
    psv50 = d32p & ~(unbal & d32q) & (I1 < 1.2 * imax)
    zero = (np.abs(vpost[:, 0] - vpre[:, 0]) >= 0.05 * Vn) | (np.abs(ipost[:, 0] - ipre[:, 0]) >= 0.05 * In)
    sup = {"none": np.ones(n, bool), "I1 >= 1.0 I_load": I1 >= i_load, "I1 >= 1.2 I_load": I1 >= 1.2 * i_load,
           "not SEL PSV50": ~psv50, "zero sequence": zero, "zero sequence or I1 >= 1.2 I_load": zero | (I1 >= 1.2 * i_load)}
    trip = R["switching"] & (R["et"] == "switch_ibr_trip") & (R["tgt"] == TRIP_BUS[name])
    inrush = R["switching"] & (np.char.find(R["et"], "inrush") >= 0)
    other_sw = R["switching"] & ~trip & ~inrush
    ft = {t: np.char.find(R["et"], s) >= 0 for t, s in (("lg", "1phg"), ("llg", "2phg"), ("ll", "2ph_shc"), ("3ph", "3ph"))}
    out = dict(i_load_inverter_off_a_peak=i_load, i_load_over_imax=i_load / imax, max_total_load_mw=p_max,
               trip_i1_over_imax=[float(np.min(I1[trip]) / imax), float(np.max(I1[trip]) / imax)] if trip.any() else None,
               pos_i1_over_imax_min=float(np.min(I1[R["pos"]]) / imax), elements={})
    for lab, s in sup.items():
        dec = fwd & s
        out["elements"][lab] = dict(pos=kn(dec, R["pos"]), pos_by_type={t: kn(dec, R["pos"] & m) for t, m in ft.items()},
                                    pos_by_rf_bin={b: kn(dec, R["pos"] & (R["rf_bin"] == b)) for b in cm.RF_LABELS},
                                    reverse=kn(dec, R["reverse"]), inverter_trip=kn(dec, trip), inrush=kn(dec, inrush),
                                    other_switching=kn(dec, other_sw))
    return out


def main(relays):
    frontend.enable()
    res = dict(script="inverter_trip_supervision.py", commit=cm.git_commit(), t_ms=20, relays={})
    for name in relays:
        R = cm.load_relay(name)
        r = res["relays"][name] = evaluate(name, R)
        print(f"[{name}] I_load (inverter off, max load) = {r['i_load_over_imax']:.3f} Imax; inverter-trip I1 {r['trip_i1_over_imax']}, in-zone min {r['pos_i1_over_imax_min']:.3f}", flush=True)
        for lab, e in r["elements"].items():
            print(f"   {lab:34s} in-zone {e['pos']['k']}/{e['pos']['n']} "
                  f"(lg {e['pos_by_type']['lg']['k']}/{e['pos_by_type']['lg']['n']}, ll {e['pos_by_type']['ll']['k']}/{e['pos_by_type']['ll']['n']}, "
                  f"llg {e['pos_by_type']['llg']['k']}/{e['pos_by_type']['llg']['n']}, 3ph {e['pos_by_type']['3ph']['k']}/{e['pos_by_type']['3ph']['n']}) | "
                  f"reverse {e['reverse']['k']}/{e['reverse']['n']} | inverter trip {e['inverter_trip']['k']}/{e['inverter_trip']['n']} | "
                  f"inrush {e['inrush']['k']}/{e['inrush']['n']} | other switching {e['other_switching']['k']}/{e['other_switching']['n']}", flush=True)
        del R
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1)
    print("saved", OUT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("relays", nargs="*", default=list(RELAYS))
    main(tuple(ap.parse_args().relays))
