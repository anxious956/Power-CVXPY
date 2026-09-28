"""Does the setting-study model reproduce what the relay measures? Validation against the EMT records.

Every conventional setting in ladder.py (reach, resistive reach, polarising cap, study reach) comes from the
sequence-network model of setting_study.py, never from EMT outcomes. That is only sound if the model
reproduces the apparent loop impedance the relay actually measures. This compares, for every short circuit
on the protected line, at its remote bus and on the lines beyond (the faults zone 1 must separate):
  model  setting_study.solve_fault on the relay's network (its own nominal voltage), with the simulation's
         OWN neutral grounding (solid / resistive with that simulation's resistance; resonant as an open
         neutral) and the fault's type, location and resistance; inverters are not in the model
  EMT    the same loop from the recorded phasors at 50 ms (full-cycle DFT), as setting_study.study does
Errors in apparent X and R are in per unit of |Z1L|, reported overall and by grounding, fault type, case
class and R_f band. The TestGrid relays adapt_A / adapt_B, for which the model was built, are run the same
way as the reference for what "good" means.

    set EVEMT_CACHE_DIRS=D:\\evemt\\cache
    python src/review/study_validation.py [--relays adapt_A adapt_B cigre_R1 cigre_R2 cigre_R3 cigre_R4]
    -> results/cigremv/study_validation.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import frontend
from review import setting_study as ss

OUT = os.path.join(cm.ROOT, "results", "cigremv", "study_validation.json")
ROT = {"a": 0, "b": 1, "c": 2}
GROUND_PARAM = {"solid": "grounding/solid_ground_resistance", "resistive": "grounding/resistive_ground_resistance"}


def loop_of(ft, phase):
    if ft == "lg":
        return ["ag", "bg", "cg"][ROT[phase]]
    if ft in ("ll", "llg"):
        return phase
    return "bc"


def case_grounding(R, i):
    g = str(R["grounding"][i])
    if g in GROUND_PARAM:
        return (g, float(R["labels"][GROUND_PARAM[g]].iloc[i]))
    return (g, None)


def summarise(E, sel):
    if not sel.any():
        return None
    ex, er = np.abs(E["x_err"][sel]), np.abs(E["r_err"][sel])
    return dict(n=int(sel.sum()), median_abs_x_err_pu=float(np.median(ex)), p90_abs_x_err_pu=float(np.percentile(ex, 90)),
                median_abs_r_err_pu=float(np.median(er)), p90_abs_r_err_pu=float(np.percentile(er, 90)),
                median_loop_current_ratio_model_over_emt=float(np.median(E["i_ratio"][sel])))


def validate(name):
    R = cm.load_relay(name)
    cfg = R["cfg"]; rb = ss.relay_bus_of(R, name)
    z1 = abs(R["z1L"])
    lines = ss.net_for(R)[1]
    own = R["pos"] | R["own99"]
    cls = np.where(own, "own line", np.where(R["remote_bus_faults"], "remote bus", np.where(R["beyond"], "beyond", "")))
    idx = np.where(cls != "")[0]
    vpre, vpost, ipre, ipost = cm.phasors_at(R, idx, 50)
    Lp = cm.loops(R, vpost, ipost, vpre, ipre)
    nets = {}
    rows = dict(x_err=[], r_err=[], i_ratio=[], ft=[], grounding=[], cls=[], rf=[])
    for n, i in enumerate(idx):
        ft = ss.ETYPE[R["et"][i]]
        lp = loop_of(ft, R["phase"][i])
        gr = case_grounding(R, i)
        key = (gr[0], None if gr[1] is None else round(gr[1], 3))
        if key not in nets:
            nets[key] = ss.net_for(R, grounding=gr if R.get("cfg", {}).get("vn_kv") else None)
        net = nets[key]
        if R["tgt"][i] == cfg["remote_bus"]:
            where, m = ("bus", cfg["remote_bus"]), 0.0
        else:
            where, m = ("line", R["tgt"][i]), R["loc"][i] / 100.0
        vpo, ipo, vpr, ipr = ss.solve_fault(net, rb, cfg["line"], where, ft, R["rf"][i], m)
        Lm = cm.loops(R, vpo[None], ipo[None], vpr[None], ipr[None])
        jm, je = cm.LOOPS.index(ss.LOOP[ft]), cm.LOOPS.index(lp)
        zm = complex(Lm["V"][0, jm] / Lm["I"][0, jm])
        ze = complex(Lp["V"][n, je] / Lp["I"][n, je])
        im = abs(Lm["I"][0, jm]) * np.sqrt(2)                   # model phasors are rms, EMT phasors peak
        ie = abs(Lp["I"][n, je])
        rows["x_err"].append((zm.imag - ze.imag) / z1); rows["r_err"].append((zm.real - ze.real) / z1)
        rows["i_ratio"].append(im / max(ie, 1e-9)); rows["ft"].append(ft); rows["grounding"].append(str(R["grounding"][i]))
        rows["cls"].append(cls[i]); rows["rf"].append(R["rf"][i])
    E = {k: np.array(v) for k, v in rows.items()}
    out = dict(relay=cfg["relay"], line=cfg["line"], z1L_ohm=[R["z1L"].real, R["z1L"].imag], n=len(idx),
               overall=summarise(E, np.ones(len(idx), bool)),
               by_grounding={g: summarise(E, E["grounding"] == g) for g in ("solid", "resistive", "resonant")},
               by_fault_type={t: summarise(E, E["ft"] == t) for t in ("lg", "ll", "llg", "3ph")},
               by_class={c: summarise(E, E["cls"] == c) for c in ("own line", "remote bus", "beyond")},
               by_rf_band={b: summarise(E, (E["rf"] > lo) & (E["rf"] <= hi)) for lo, hi, b in cm.RF_BINS})
    return out


def main(relays):
    t0 = time.time()
    frontend.enable()
    res = dict(script="study_validation", commit=cm.git_commit(), decision_ms=50, relays={})
    for name in relays:
        r = validate(name)
        res["relays"][name] = r
        o = r["overall"]
        print(f"[{name}] n {o['n']}  |X err| median {o['median_abs_x_err_pu']:.3f} p90 {o['p90_abs_x_err_pu']:.3f} pu of |Z1L|  "
              f"|R err| median {o['median_abs_r_err_pu']:.3f}  I model/EMT {o['median_loop_current_ratio_model_over_emt']:.2f}  "
              f"[{time.time()-t0:.0f}s]", flush=True)
        for g, s in r["by_grounding"].items():
            if s:
                print(f"      {g:9s} n {s['n']:4d}  |X err| {s['median_abs_x_err_pu']:.3f} / p90 {s['p90_abs_x_err_pu']:.3f}  "
                      f"|R err| {s['median_abs_r_err_pu']:.3f}  I ratio {s['median_loop_current_ratio_model_over_emt']:.2f}", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    print("saved", OUT, f"[{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--relays", nargs="+", default=["adapt_A", "adapt_B", "cigre_R1", "cigre_R2", "cigre_R3", "cigre_R4"])
    main(ap.parse_args().relays)
