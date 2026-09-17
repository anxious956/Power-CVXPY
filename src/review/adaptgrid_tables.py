"""Markdown tables for results/ADAPTGRID.md, generated from results/adaptgrid/<relay>_<frontend>.json
(src/review/adaptgrid_run.py). No number is copied by hand.

    python src/review/adaptgrid_tables.py > results/adaptgrid/TABLES.md
"""
import os, json, glob
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
D = os.path.join(ROOT, "results", "adaptgrid")
RELAYS = (("adapt_A", "A (bus 1, line 1-2A)"), ("adapt_B", "B (bus 2, line 2-3)"))
FES = (("current", "current front end"), ("relayfe", "relay front end (AA 400 Hz + CT full scale)"))
MODELS = ("T2", "engineered + LR", "gradient boosting", "CNN seq-traj", "GBM distance (Q2)")
pct = lambda x: "–" if x is None or x != x else f"{100 * x:.1f}"


def load(relay, fe):
    p = os.path.join(D, f"{relay}_{fe}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def kn(d):
    return "–" if not d else f"{d['k']}/{d['n']} (≤{100 * d['ucb95']:.1f})"


def ci(r):
    c = r.get("dependability_ci")
    return "" if not c else f" [{100 * c[0]:.0f}, {100 * c[1]:.0f}]"


def rfbin(r, b):
    d = r.get("dep_by_rf_bin", {}).get(b)
    return "–" if not d or d["rate"] != d["rate"] else f"{100 * d['rate']:.0f}"


def cls(r, h):
    return f"{r[h]['k']}/{r[h]['n']}" if h in r and r[h] else "–"


def row_from_rates(label, r, auc=None):
    a = "–" if auc is None or auc != auc else f"{auc:.3f}"
    return (f"| {label} | {a} | {pct(r['pos']['rate'])}{ci(r)} | {rfbin(r, '1-10')} / {rfbin(r, '10-40')} / {rfbin(r, '>40')} | "
            f"{kn(r['neg']['dedup'])} | {kn(r.get('neg_bench'))} | {cls(r, 'own99')} | {cls(r, 'reverse_bus')} | {cls(r, 'reverse_lines')} | "
            f"{cls(r, 'parallel')} | {cls(r, 'other')} | {kn(r.get('incipient'))} | {cls(r, 'switching')} |")


HEAD = ("| Detector | AUC | Dependability [95 % CI] | dep. by R_f 1–10 / 10–40 / >40 Ω | Off-line faults k/n (≤UCB) | "
        "Remote bus + first 20 % k/n (≤UCB) | Guard 85–100 % | Reverse bus | Lines behind | Parallel | Other lines | Incipient k/n | Switching |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def ladder_table(J, lab):
    L = J.get("ladder")
    if not L:
        return
    print(f"\n#### Conventional ladder, relay {lab}, {J['frontend']} front end, 20 ms (corrected R_set)\n")
    print(HEAD)
    F = L["fixed"]
    for rung in ("R0", "R1", "R2", "R3", "R4"):
        k = f"20|{rung}"
        if k in F:
            r = F[k]
            r.setdefault("neg_bench", None); r.setdefault("incipient", None)
            print(row_from_rates(rung, r))
    T = L["tuned"]
    for rung in ("T1", "T2"):
        for kind in ("grouped", "loqo"):
            k = f"20|{kind}|{rung}|own99-guard"
            if k in T:
                t = T[k]
                h = lambda c: (f"{100 * t['held'][c]['mean_rate']:.1f} %" if c in t["held"] else "–")
                rb = t.get("dep_by_rf_bin") or {}
                rf3 = " / ".join(("–" if not rb.get(b) or rb[b]["rate"] != rb[b]["rate"] else f"{100 * rb[b]['rate']:.0f}") for b in ("1-10", "10-40", ">40"))
                print(f"| {rung} ({kind} folds) | – | {pct(t['dependability'])} [{100 * t['dependability_ci'][0]:.0f}, {100 * t['dependability_ci'][1]:.0f}] | {rf3} | "
                      f"{kn(t['beyond_dedup'])} | – | {h('own99')} | {h('reverse_bus')} | {h('reverse_lines')} | {h('parallel')} | {h('other')} | – | {h('switching')} |")
    ref = L["reference_67"]["20"]["67N or 67Q"]
    ref.setdefault("neg_bench", None); ref.setdefault("incipient", None)
    print(row_from_rates("ref. 67N or 67Q (detection, no reach)", ref))
    s = L["settings"]
    print(f"\nSettings: X_set {s['x_set']:.2f} Ω, R_set {s['r_set_g']:.2f} Ω (legacy {s['r_set_g_legacy']:.1f}, cap from Θ = {s['polarising_cap']['theta_r2_deg']:.1f}°), "
          f"tilt {s['tilt_nominal_deg']:.2f}° in [{s['tilt_range_deg'][0]:.1f}, {s['tilt_range_deg'][1]:.1f}].")


def models_table(J, lab):
    C = J.get("chains", {})
    if not C:
        return
    for kind in ("grouped", "loqo"):
        print(f"\n#### Learned models and T2, relay {lab}, {J['frontend']} front end, 20 ms, "
              f"{'5-fold over loading bins' if kind == 'grouped' else 'leave one loading quartile out'}\n")
        print(HEAD)
        for m in MODELS:
            for chain, variants in (("matched", ("matched", "matched + directional", "starter", "starter + directional")),
                                    ("mismatch", ("matched", "matched + directional"))):
                res = C.get(chain, {}).get(m, {}).get(kind)
                if not res:
                    continue
                for v in variants:
                    tag = {"matched": "", "matched + directional": " + 32P/32Q", "starter": ", starter-anchored",
                           "starter + directional": ", starter + 32P/32Q"}[v]
                    label = f"{m}{', instrument mismatch' if chain == 'mismatch' else ''}{tag}"
                    print(row_from_rates(label, res[v], res.get("auc") if v == "matched" else None))
    X = J.get("cross", {})
    for key, models in X.items():
        print(f"\n#### Cross-relay transfer {key}, {J['frontend']} front end, threshold carried over\n")
        print(HEAD)
        for m, r in models.items():
            print(row_from_rates(f"{m}", r["transferred"], r["auc"]))
            print(row_from_rates(f"{m} + 32P/32Q", r["transferred_directional"]))


def strata_table(J, lab):
    C = J.get("chains", {}).get("matched", {})
    if not C:
        return
    print(f"\n#### Dependability by grounding and loading quartile, relay {lab}, {J['frontend']} front end, matched chain + 32P/32Q, loading-bin folds\n")
    print("| Detector | solid | resistive | resonant | load Q1 (lightest) | Q2 | Q3 | Q4 (heaviest) | off-line trips: solid / resistive / resonant |")
    print("|---|---|---|---|---|---|---|---|---|")
    for m in MODELS:
        res = C.get(m, {}).get("grouped")
        if not res:
            continue
        r = res["matched + directional"]
        g, qd, gb = r.get("dep_by_grounding", {}), r.get("dep_by_op_quartile", {}), r.get("beyond_by_grounding", {})
        f = lambda d, k: ("–" if k not in d or d[k]["rate"] != d[k]["rate"] else f"{100 * d[k]['rate']:.0f} % (n={d[k]['n']})")
        print(f"| {m} | {f(g, 'solid')} | {f(g, 'resistive')} | {f(g, 'resonant')} | {f(qd, '0')} | {f(qd, '1')} | {f(qd, '2')} | {f(qd, '3')} | "
              f"{pct(gb.get('solid', {}).get('rate'))} / {pct(gb.get('resistive', {}).get('rate'))} / {pct(gb.get('resonant', {}).get('rate'))} |")


if __name__ == "__main__":
    print("# adapt_grid-TestGrid110kV: generated tables\n")
    print("Generated by `src/review/adaptgrid_tables.py` from `results/adaptgrid/*.json`. Off-line faults = every short circuit off the "
          "protected line regardless of direction; k/n are deduplicated counts with one-sided 95 % binomial upper bounds; CIs are grouped "
          "bootstraps over loading bins.")
    for relay, lab in RELAYS:
        for fe, felab in FES:
            J = load(relay, fe)
            if not J:
                continue
            print(f"\n---\n\n### Relay {lab}, {felab}\n")
            ladder_table(J, lab)
            models_table(J, lab)
            strata_table(J, lab)
