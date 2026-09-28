"""Three quick checks on the conventional and both-ends rows of results/CIGREMV.md (and TestGrid for comparison).
No training: every decision is a frozen element evaluated once. Agreed in docs/notes/SORULAR_CEVAPLAR.md Q21.

1. Settings sensitivity. The CIGRE settings come from a study model with 0.24-0.69 |Z1L| of reactance error at
   the inverter-bus relays. The directional quadrilateral (R2) is re-evaluated with X_set and R_set scaled
   by 0.8-1.2: if coverage and security barely move, the conclusion does not rest on the model's error.
2. Channel delay. The both-ends references read the remote end at the same 20 ms as the local one. With a
   channel delay d, a trip at 20 ms needs the remote permission sent by 20 - d ms, so the remote element is
   read on the window ending 20 - d ms after inception (at d >= 20 ms it has seen nothing of the fault).
   The other framing, both ends at 20 ms and the trip at 20 + d ms, gives the d = 0 numbers, later.
   The published POTT-equivalent keys the permission on 32P/32Q alone, with no fault detector; read on a
   window that holds little of the fault, 32P/32Q follows the load flow and keys it for everything. A real
   scheme keys only on a detected fault, so a second row keys the remote permission on the causal starter
   of h10_trigger (superimposed current above max(0.1 In, 8 sigma) for 3 samples) having fired by 20 - d
   ms. 67N/67Q have their own pickup and need no starter.
3. CT saturation. The records carry ideal current transformers. common.ct_saturation (IEEE PSRC-calculator
   style) is applied to both line ends at each relay's CT ratio, for a 5P20-like CT and for an undersized
   one with 80 % remanence, and the rule and both-ends rows are re-read. How much the CT actually distorts
   is reported with it (positive-sequence current at 20 ms, saturated / ideal, in-zone faults).

The unperturbed case of every check must reproduce results/adaptgrid/rules_<relay>_relayfe.json; that is
asserted and stored as `reproduces_rules_json`.

    python src/review/cigremv_checks.py        -> results/cigremv/quick_checks.json
"""
import os, sys, json, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from review import common as cm
from review import ladder as ld
from review import frontend
from review.adaptgrid_run import bundle, rates_plus, T
from review.zone_cv import zone_task
from review import h10_trigger as h10

OUT = os.path.join(cm.ROOT, "results", "cigremv", "quick_checks.json")
RULES = os.path.join(cm.ROOT, "results", "adaptgrid", "rules_{}_relayfe.json")
RELAYS = ("cigre_R1", "cigre_R2", "cigre_R3", "cigre_R4", "adapt_A", "adapt_B")
X_SCALES = (0.8, 0.9, 1.0, 1.1, 1.2)
R_SCALES = (0.8, 1.0, 1.2)
DELAYS_MS = (0, 5, 10, 15, 20)
CT_CASES = {"5P20-like (Vsat 400 V at 5 ohm)": dict(r_burden=5.0, vsat=400.0, remanence=0.0),
            "undersized (Vsat 100 V at 5 ohm), 80 % remanence": dict(r_burden=5.0, vsat=100.0, remanence=0.8)}
POTT, BOTH67 = "32P/32Q both ends (POTT-equivalent, no reach)", "67N/67Q both ends"
POTT_FD = "32P/32Q both ends, remote keyed by its fault detector"


def brief(r):
    g = lambda h: (dict(k=r[h]["k"], n=r[h]["n"]) if h in r else None)
    return dict(dependability=r["pos"]["rate"], dependability_ci=r["dependability_ci"],
                offline=dict(k=r["neg"]["dedup"]["k"], n=r["neg"]["dedup"]["n"], ucb95=r["neg"]["dedup"]["ucb95"]),
                switching=g("switching"), reverse_bus=g("reverse_bus"), incipient=dict(k=r["incipient"]["k"], n=r["incipient"]["n"]),
                dep_by_rf_bin={b: r["dep_by_rf_bin"][b]["rate"] for b in cm.RF_LABELS})


def same(a, b):
    return abs(a["dependability"] - b["pos"]["rate"]) < 1e-12 and a["offline"]["k"] == b["neg"]["dedup"]["k"]


def both_ends(R, Rr, t_remote):
    sel = np.arange(len(R["et"]))
    P, Pr = ld.pack(R, sel, T, "full", True), ld.pack(Rr, sel, t_remote, "full", True)
    fl = ld.directional(*P, R["z1L"], in_a=ld.profile(R)["ct_primary_a"])
    fr = ld.directional(*Pr, Rr["z1L"], in_a=ld.profile(Rr)["ct_primary_a"])
    l67, r67 = np.logical_or(*ld.ground_overcurrent(R, *P)), np.logical_or(*ld.ground_overcurrent(Rr, *Pr))
    trig = h10.trigger(Rr, sel, in_a=ld.profile(Rr)["ct_primary_a"])              # samples after inception
    keyed = (trig < 10**6) & (trig + 2 <= int(round(t_remote * cm.FS / 1000)))
    return {"32P/32Q local only": fl, POTT: fl & fr, POTT_FD: fl & fr & keyed, BOTH67: l67 & r67}


def relay_checks(name):
    t0 = time.time()
    rules = json.load(open(RULES.format(name)))
    R = bundle(name, None)
    n = len(R["et"]); sel = np.arange(n); ok = np.ones(n, bool)
    idx, y, _ = zone_task(R)
    S = R["S"]
    rate = lambda dec: brief(rates_plus(dec, R, sel, idx, y, ok))
    out = dict(settings=dict(x_set=float(S["x_set"]), r_set_g=float(S["r_set_g"])), reproduces_rules_json={})

    # 1. settings sensitivity
    P1 = ld.pack(R, sel, T, "full", True)
    sens = {}
    for fx in X_SCALES:
        for fr in R_SCALES:
            trip = ld.evaluate_block(R, *P1, S, "R2", x_set=fx * S["x_set"], r_set=fr * S["r_set_g"])[0]
            sens[f"x{fx:g}|r{fr:g}"] = rate(trip)
    out["settings_sensitivity_R2"] = sens
    out["reproduces_rules_json"]["R2"] = same(sens["x1|r1"], rules["fixed"]["R2"])

    # 2. channel delay on the both-ends references (only where the config names the remote cubicle)
    rc = R["cfg"].get("remote_cubicle")
    if rc:
        Rr = cm.load_relay(name, None, cubicle=rc)
        out["channel_delay"] = {}
        for d in DELAYS_MS:
            dec = both_ends(R, Rr, T - d)
            out["channel_delay"][str(d)] = {k: rate(v) for k, v in dec.items() if k != "32P/32Q local only"}
        ref = rules["reference_comm"]
        out["reproduces_rules_json"]["both_ends"] = all(same(out["channel_delay"]["0"][k], ref[k]) for k in (POTT, BOTH67))
        del Rr

    # 3. CT saturation, both ends
    ct_a = ld.profile(R)["ct_primary_a"]
    i1_ideal = np.abs(P1[3][:, 1])
    out["ct_saturation"] = {}
    for lab, ct in CT_CASES.items():
        chain = {"ct": dict(ct, ratio=ct_a)}
        Rc = bundle(name, chain)
        Pc = ld.pack(Rc, sel, T, "full", True)
        ratio = np.abs(Pc[3][:, 1]) / np.maximum(i1_ideal, 1e-9)
        pos = R["pos"]
        res = dict(ct=dict(chain["ct"]), i1_ratio_in_zone=dict(
            median=float(np.median(ratio[pos])), p5=float(np.percentile(ratio[pos], 5)),
            share_below_0_95=float(np.mean(ratio[pos] < 0.95)), share_below_0_8=float(np.mean(ratio[pos] < 0.8))),
            R2=rate(ld.evaluate_block(Rc, *Pc, Rc["S"], "R2")[0]))
        if rc:
            Rrc = cm.load_relay(name, chain, cubicle=rc)
            res.update({k: rate(v) for k, v in both_ends(Rc, Rrc, T).items()})
            del Rrc
        out["ct_saturation"][lab] = res
        del Rc
    out["runtime_s"] = float(time.time() - t0)
    return out


def main():
    frontend.enable()
    res = dict(script="cigremv_checks", commit=cm.git_commit(), frontend="relayfe", t_ms=T, relays={})
    for name in RELAYS:
        r = res["relays"][name] = relay_checks(name)
        s = r["settings_sensitivity_R2"]
        lo = min(v["dependability"] for v in s.values()); hi = max(v["dependability"] for v in s.values())
        offl = [v["offline"]["k"] for v in s.values()]
        print(f"[{name}] reproduces rules JSON: {r['reproduces_rules_json']}  [{r['runtime_s']:.0f}s]", flush=True)
        print(f"   R2, X_set x0.8-1.2 and R_set x0.8-1.2: dependability {100 * lo:.1f}-{100 * hi:.1f} %, off-line trips {min(offl)}-{max(offl)}", flush=True)
        for d, v in (r.get("channel_delay") or {}).items():
            print(f"   channel delay {d:>2} ms: POTT {100 * v[POTT]['dependability']:5.1f} % off {v[POTT]['offline']['k']:4d} | "
                  f"POTT + fault detector {100 * v[POTT_FD]['dependability']:5.1f} % off {v[POTT_FD]['offline']['k']:4d} "
                  f"sw {v[POTT_FD]['switching']['k']:3d} | "
                  f"67N/67Q both {100 * v[BOTH67]['dependability']:5.1f} % off {v[BOTH67]['offline']['k']:3d}", flush=True)
        for lab, v in r["ct_saturation"].items():
            q = v["i1_ratio_in_zone"]
            line = (f"   CT {lab}: I1 ratio in-zone median {q['median']:.3f}, p5 {q['p5']:.3f}, <0.95 {100 * q['share_below_0_95']:.1f} % | "
                    f"R2 {100 * v['R2']['dependability']:.1f} % off {v['R2']['offline']['k']}")
            if POTT in v:
                line += (f" | POTT {100 * v[POTT]['dependability']:.1f} % off {v[POTT]['offline']['k']} | 67N/67Q both "
                         f"{100 * v[BOTH67]['dependability']:.1f} % off {v[BOTH67]['offline']['k']}")
            print(line, flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    print("saved", OUT)


if __name__ == "__main__":
    main()
