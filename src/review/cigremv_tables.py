"""Markdown tables for results/CIGREMV.md, generated from results/adaptgrid/*cigre*.json and
results/cigremv/*.json. No number is copied by hand. Tables A-D are adaptgrid_tables.py's, unchanged, for the
four CIGRE MV relays; E-J are the seed, reverse-held-out, Hasan SVM, directional, boundary and switching-trip
summaries.

    python src/review/cigremv_tables.py > results/cigremv/TABLES.md
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from review import adaptgrid_tables as T

RELAYS = (("cigre_R1", "R1 (bus 3, line 2-3, inverter bus)"), ("cigre_R2", "R2 (bus 2, line 2-3)"),
          ("cigre_R3", "R3 (bus 14, line 13-14, inverter bus)"), ("cigre_R4", "R4 (bus 1, line 1-2)"))
TAG = "_" + "-".join(r for r, _ in RELAYS)
CIG = os.path.join(T.ROOT, "results", "cigremv")
pct = T.pct


def load_cig(name):
    p = os.path.join(CIG, name)
    return json.load(open(p)) if os.path.exists(p) else None


def kn(d):
    return "–" if not d else f"{d['k']}/{d['n']}"


def seeds_table():
    print("\n### E. CNN seq-traj over three training seeds, zero false trips (cal0), matched chain, 20 ms\n")
    print("| Relay | Split | seed | dependability | off-line trips | switching trips |")
    print("|---|---|---|---|---|---|")
    for relay, lab in RELAYS:
        S = T.load(f"seeds_{relay}_relayfe_cnn.json")
        if not S:
            continue
        for sp, v in S["splits"].items():
            for seed, x in v["per_seed"].items():
                c = x["cal0"]
                print(f"| {lab} | {sp} | {seed} | {pct(c['dependability'])} | {kn(c['offline'])} | {kn(c['switching'])} |")


def reverse_table():
    J = T.load(f"reverse_heldout_relayfe_cnn{TAG}.json")
    if not J:
        return
    print("\n### F. Reverse faults held out of training: CNN seq-traj, seed 0, cal0, no directional supervision\n")
    print("| Relay | Split | reverse faults in training | dependability | off-line trips | reverse bus | lines behind | switching |")
    print("|---|---|---|---|---|---|---|---|")
    for relay, lab in RELAYS:
        v = J["relays"].get(relay)
        if not v:
            continue
        for sp, per in v["splits"].items():
            for label, say in (("in_training", "yes"), ("held_out", "**no**")):
                c = per[label]["cal0"]["unsupervised"]; pc = c["per_class"]
                print(f"| {lab} | {sp} | {say} | {pct(c['dependability'])} | {kn(c['offline_all'])} | {kn(pc['reverse_bus'])} | "
                      f"{kn(pc['reverse_lines'])} | {kn(pc['switching'])} |")


def hasan_table():
    J = T.load(f"hasan_svm_relayfe{TAG}.json")
    if not J:
        return
    print("\n### G. Hasan et al. (2026) hierarchical linear SVM, relay front end\n")
    print("Native = their own trip rule (forward and zone-1 decision value > 0); cal0 = threshold at zero off-line false trips "
          "on the training negatives, same folds as every detector. Mismatch = trained on installation draw 1, tested on draw 2. "
          "No directional supervision (the JSON also holds the supervised readouts).\n")
    print("| Relay | Variant | t (ms) | Split | Chain | AUC | native dep. | native off-line | native switching | cal0 dep. | cal0 off-line | cal0 switching |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for relay, lab in RELAYS:
        v = J["relays"].get(relay)
        if not v:
            continue
        for key, r in v["runs"].items():
            var, t, sp, chain = key.split("|")
            n, c = r["readouts"]["native"]["unsupervised"], r["readouts"]["cal0"]["unsupervised"]
            print(f"| {lab} | {var} | {t} | {sp} | {chain} | {r['auc']:.3f} | {pct(n['dependability'])} | {kn(n['offline'])} | "
                  f"{kn(n['per_class'].get('switching'))} | {pct(c['dependability'])} | {kn(c['offline'])} | "
                  f"{kn(c['per_class'].get('switching'))} |")


def directional_table():
    J = T.load(f"directional_reverse_relayfe{TAG}.json")
    if not J:
        return
    print("\n### H. 32P/32Q directional element at 20 ms: faults it calls forward\n")
    print("| Relay | in-zone faults (should be forward) | relay-bus faults (reverse) | lines behind (reverse) | "
          "relay-bus by R_f <5 / 5–15 / 15–40 / >40 Ω | relay-bus by grounding solid / resistive / resonant |")
    print("|---|---|---|---|---|---|")
    f = lambda d: f"{d['k_forward']}/{d['n']}"
    for relay, lab in RELAYS:
        r = J["relays"].get(relay)
        if not r:
            continue
        b = r["by_class"]
        rb = r["reverse_bus"]
        print(f"| {lab} | {f(b['pos'])} | {f(b['reverse_bus'])} | {f(b['reverse_lines']) if b['reverse_lines']['n'] else '– (none)'} | "
              + " / ".join(f(rb["by_rf_bin"][x]) for x in T.BANDS) + " | "
              + " / ".join(f(rb["by_grounding"][g]) for g in ("solid", "resistive", "resonant")) + " |")


def boundary_table():
    J = load_cig("diagnostics.json")
    if not J:
        return
    print("\n### I. Is the zone boundary visible from one end? CNN seq-traj out-of-fold scores, loading-bin folds\n")
    print("AUC of in-zone faults against the off-line faults nearest the boundary (remote bus and lines beyond), within each "
          "R_f band, so both classes carry the same resistance. `cigremv_diagnostics.py`.\n")
    print("| Relay | abs(Z1L) Ω | in-zone R_f median Ω | AUC, all off-line | AUC, near boundary | in-zone above the highest off-line score | "
          "near-boundary AUC by R_f <5 / 5–15 / 15–40 / >40 Ω (n in-zone / n near) |")
    print("|---|---|---|---|---|---|---|")
    a = lambda x: "–" if x is None else f"{x:.3f}"
    for relay, r in J["relays"].items():
        bands = " · ".join(f"{a(v['auc'])} ({v['n_pos']}/{v['n_near']})" for v in r["by_rf_band"].values())
        print(f"| {relay} | {r['z1L_abs_ohm']:.2f} | {r['rf_median_in_zone']:.1f} | {a(r['auc_all_offline'])} | {a(r['auc_near'])} | "
              f"{r['above_highest_offline']['k']}/{r['above_highest_offline']['n']} | {bands} |")


def switching_table():
    J = load_cig("diagnostics.json")
    if not J:
        return
    print("\n### J. Switching events that trip the CNN seq-traj at zero false trips (cal0, loading-bin folds), by event and target\n")
    print("| Relay | switching trips | of them 32P/32Q forward | event and target: trips / events of that kind |")
    print("|---|---|---|---|")
    for relay, r in J["relays"].items():
        s = r["switching_trips_cal0"]
        ev = "; ".join(f"{k.replace('|', ' at ')}: {v} / {s['events_of_that_kind'][k]}" for k, v in s["by_event_target"].items()) or "–"
        print(f"| {relay} | {s['k']}/{s['n']} | {s['forward_32']} | {ev} |")


if __name__ == "__main__":
    print("# adapt_grid-CigreMVGrid: generated tables\n")
    print("Generated by `src/review/cigremv_tables.py` from `results/adaptgrid/*cigre*.json` and `results/cigremv/*.json`. "
          "Tables A–D are the TestGrid tables (`adaptgrid_tables.py`) for the four CIGRE MV relays, relay front end only. "
          "Off-line faults = every short circuit off the protected line regardless of direction; k/n are deduplicated counts "
          "with one-sided 95 % binomial upper bounds; CIs are grouped bootstraps over loading bins.\n")
    for relay, lab in RELAYS:
        J = T.load(f"{relay}_relayfe.json")
        if not J:
            continue
        RU = T.load(f"rules_{relay}_relayfe.json")
        print(f"\n---\n\n## Relay {lab}\n")
        for kind in ("grouped", "loqo"):
            T.protection_table(J, RU, lab, kind)
        T.protection_table(J, RU, lab, "grouped", chain="mismatch")
        T.settable_table(J, RU, lab)
        T.budget_table(J, RU, lab, "grouped")
        T.strata_table(J, lab)
        if RU:
            s = RU["settings"]
            print(f"\nSettings (inverter-aware study, `ladder_mv.py`): X_set {float(s['x_set']):.2f} Ω, R_set {float(s['r_set_g']):.2f} Ω "
                  f"(legacy {float(s['r_set_g_legacy']):.1f}, cap from Θ = {float(s['polarising_cap']['theta_r2_deg']):.1f}°), "
                  f"study reach X {float(s['x_set_study']):.2f} Ω.")
            print(f"\n{(RU.get('reference_comm') or {}).get('_note', '')}")
    print("\n---\n\n## Across relays\n")
    seeds_table()
    reverse_table()
    hasan_table()
    directional_table()
    boundary_table()
    switching_table()
