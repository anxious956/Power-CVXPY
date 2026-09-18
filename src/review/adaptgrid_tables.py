"""Markdown tables for results/ADAPTGRID.md, generated from results/adaptgrid/*.json
(src/review/adaptgrid_run.py, src/review/adaptgrid_rules.py). No number is copied by hand.

    python src/review/adaptgrid_tables.py > results/adaptgrid/TABLES.md

Table A is the primary one: the protection-grade operating point, threshold calibrated at ZERO false
trips on the training negatives, with the ROC reads at zero and at one off-line false trip beside it.
Table B is the 5 % research convention, kept for comparison. Every detector appears twice, without and
with 32P/32Q directional supervision.
"""
import os, json, glob
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
D = os.path.join(ROOT, "results", "adaptgrid")
RELAYS = (("adapt_A", "A (bus 1, line 1-2A)"), ("adapt_B", "B (bus 2, line 2-3)"))
FES = (("current", "current front end"), ("relayfe", "relay front end (AA 400 Hz + CT full scale)"))
MODELS = ("T1", "T2", "engineered + LR", "gradient boosting", "CNN seq-traj", "GBM distance (Q2)")
FIXED = ("R0", "R1", "R2", "R3", "R4")
BANDS = ("<5", "5-15", "15-40", ">40")
SUP = (("", "unsupervised"), (" + directional", "+ 32P/32Q"))
pct = lambda x: "–" if x is None or x != x else f"{100 * x:.1f}"


def load(pat):
    p = os.path.join(D, pat)
    return json.load(open(p)) if os.path.exists(p) else None


def kn(d):
    return "–" if not d or d.get("n") in (0, None) else (f"{d['k']}/{d['n']}" + (f" (≤{100 * d['ucb95']:.1f})" if "ucb95" in d and d["ucb95"] is not None else ""))


def ci(r):
    c = r.get("dependability_ci")
    return "" if not c else f" [{100 * c[0]:.0f}, {100 * c[1]:.0f}]"


def rfbin(r, b):
    d = (r.get("dep_by_rf_bin") or {}).get(b)
    return "–" if not d or d["rate"] != d["rate"] else f"{100 * d['rate']:.0f}"


def cls(r, h):
    return f"{r[h]['k']}/{r[h]['n']}" if h in r and r[h] else "–"


def settable(r, key):
    d = (r.get("settable") or {}).get(key)
    return "–" if not d or not d["n"] else f"{d['k']}/{d['n']}"


# ------------------------------------------------------------------ table A: protection-grade
HEAD_A = ("| Detector | Supervision | Dependability at zero false trips [95 % CI] | dep. by R_f <5 / 5–15 / 15–40 / >40 Ω | "
          "Off-line faults k/n (≤UCB) | Guard 85–100 % | Switching | Incipient | Reverse bus | dep. at ROC 0 off-line | dep. at ROC ≤1 off-line |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|")


def row_a(label, sup, cal0, roc0, roc1):
    r = cal0
    return (f"| {label} | {sup} | {pct(r['pos']['rate'])}{ci(r)} | " + " / ".join(rfbin(r, b) for b in BANDS) +
            f" | {kn(r['neg']['dedup'])} | {cls(r, 'own99')} | {cls(r, 'switching')} | "
            f"{kn(r.get('incipient'))} | {cls(r, 'reverse_bus')} | {'–' if roc0 is None else pct(roc0['pos']['rate'])} | "
            f"{'–' if roc1 is None else pct(roc1['pos']['rate'])} |")


def protection_table(J, RU, lab, kind, chain="matched", anchor="matched"):
    print(f"\n#### A. Protection-grade operating point, relay {lab}, {J['frontend']} front end, 20 ms, "
          f"{'5-fold over loading bins' if kind == 'grouped' else 'leave one loading quartile out'}"
          f"{'' if chain == 'matched' else ', instrument mismatch'}{'' if anchor == 'matched' else ', starter-anchored'}\n")
    print(HEAD_A)
    if RU and chain == "matched" and anchor == "matched":
        for rung in FIXED:
            r = RU["fixed"].get(rung)
            if r:
                print(row_a(f"{rung} (frozen setting, no threshold)", "as specified", r, None, None))
    for m in MODELS:
        res = J.get("chains", {}).get(chain, {}).get(m, {}).get(kind)
        if not res:
            continue
        P = res.get("protection")
        for key, sup in SUP:
            v = anchor + key
            if not P:
                print(f"| {m} | {sup} | pending rerun | – | – | – | – | – | – | – | – |")
                break
            print(row_a(m, sup, P["cal0"][v], P["roc0"][v], P["roc1"][v]))
    if RU and chain == "matched" and anchor == "matched":
        for lab67 in ("67N or 67Q",):
            r = RU["fixed"].get(lab67)
            if r:
                print(row_a(f"ref. {lab67} (detection, no reach)", "32Q / I0 dir.", r, None, None))
        for lab2, r in (RU.get("reference_comm") or {}).items():
            if not lab2.startswith("_"):
                print(row_a("ref. " + lab2, "as named", r, None, None))


# ------------------------------------------------------------------ table B: 5 % convention
HEAD_B = ("| Detector | Supervision | AUC | Dependability [95 % CI] | dep. by R_f <5 / 5–15 / 15–40 / >40 Ω | Off-line faults k/n (≤UCB) | "
          "Remote bus + first 20 % k/n | Guard 85–100 % | Reverse bus | Lines behind | Parallel | Other lines | Incipient | Switching |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def row_b(label, sup, r, auc=None):
    a = "–" if auc is None or auc != auc else f"{auc:.3f}"
    return (f"| {label} | {sup} | {a} | {pct(r['pos']['rate'])}{ci(r)} | " +
            " / ".join(rfbin(r, b) for b in BANDS) +
            f" | {kn(r['neg']['dedup'])} | {kn(r.get('neg_bench'))} | {cls(r, 'own99')} | {cls(r, 'reverse_bus')} | {cls(r, 'reverse_lines')} | "
            f"{cls(r, 'parallel')} | {cls(r, 'other')} | {kn(r.get('incipient'))} | {cls(r, 'switching')} |")


def budget_table(J, RU, lab, kind):
    print(f"\n#### B. The 5 % false-trip convention (secondary), relay {lab}, {J['frontend']} front end, 20 ms, "
          f"{'loading-bin folds' if kind == 'grouped' else 'leave one loading quartile out'}\n")
    print(HEAD_B)
    if RU:
        for rung in FIXED:
            r = RU["fixed"].get(rung)
            if r:
                print(row_b(f"{rung} (frozen)", "as specified", r))
    for chain, ctag in (("matched", ""), ("mismatch", ", instrument mismatch")):
        for m in MODELS:
            res = J.get("chains", {}).get(chain, {}).get(m, {}).get(kind)
            if not res:
                continue
            for key, sup in SUP:
                print(row_b(m + ctag, sup, res["matched" + key], res.get("auc") if key == "" else None))
            for key, sup in SUP:
                if "starter" + key in res:
                    print(row_b(m + ctag + ", starter-anchored", sup, res["starter" + key]))
    if RU:
        for lab67 in ("67N", "67Q", "67N or 67Q"):
            r = RU["fixed"].get(lab67)
            if r:
                print(row_b(f"ref. {lab67} (detection, no reach)", "directional", r))
        for lab2, r in (RU.get("reference_comm") or {}).items():
            if not lab2.startswith("_"):
                print(row_b("ref. " + lab2, "as named", r))
    X = J.get("cross", {})
    for key, models in X.items():
        for m, r in models.items():
            print(row_b(f"cross-relay {key}: {m}", "unsupervised", r["transferred"], r["auc"]))
            print(row_b(f"cross-relay {key}: {m}", "+ 32P/32Q", r["transferred_directional"]))


# ------------------------------------------------------------------ table C: R_f and the settable characteristic
def settable_table(J, RU, lab):
    S = (RU or {}).get("settable")
    if not S:
        return
    print(f"\n#### C. Fault resistance and the largest settable zone-1 characteristic, relay {lab}, {J['frontend']} front end\n")
    q = S["rf_quantiles_pos"]
    print(f"In-zone R_f (Ω), percentiles: min {q['0']:.2f}, 10 % {q['10']:.1f}, 25 % {q['25']:.1f}, median {q['50']:.1f}, "
          f"75 % {q['75']:.1f}, 90 % {q['90']:.1f}, max {q['100']:.1f}. Off-line median {S['rf_quantiles_offline']['50']:.1f} Ω.\n")
    print(f"Largest settable characteristic: X_set = {S['x_set_max']:.2f} Ω (0.9 X_line), R_set = {S['r_set_max_capped']:.2f} Ω "
          f"(Kasztenny eq. 19 cap; the uncapped legacy grid would allow {S['r_set_max_legacy']:.1f} Ω).\n")
    print("| R_f band | in-zone faults | inside the capped characteristic | inside the uncapped legacy characteristic |")
    print("|---|---|---|---|")
    for b in BANDS:
        d = S["by_rf_bin"][b]
        print(f"| {b} Ω | {d['n']} | {d['inside_capped']} | {d['inside_legacy']} |")
    print(f"| **all** | **{S['n_pos']}** | **{S['inside_capped']} ({100 * S['inside_capped'] / max(S['n_pos'], 1):.0f} %)** | "
          f"**{S['inside_legacy']} ({100 * S['inside_legacy'] / max(S['n_pos'], 1):.0f} %)** |")
    print(f"\nDependability on the two subsets, at the protection-grade point (zero false trips), matched chain, loading-bin folds:\n")
    print("| Detector | Supervision | inside the settable characteristic | outside it |")
    print("|---|---|---|---|")
    for rung in FIXED:
        r = (RU or {}).get("fixed", {}).get(rung)
        if r:
            print(f"| {rung} (frozen) | as specified | {settable(r, 'inside')} | {settable(r, 'outside')} |")
    for m in MODELS:
        res = J.get("chains", {}).get("matched", {}).get(m, {}).get("grouped")
        if not res:
            continue
        P = res.get("protection")
        if not P:
            print(f"| {m} | – | pending rerun | pending rerun |")
            continue
        for key, sup in SUP:
            r = P["cal0"]["matched" + key]
            print(f"| {m} | {sup} | {settable(r, 'inside')} | {settable(r, 'outside')} |")
    for lab2, r in ((RU or {}).get("reference_comm") or {}).items():
        if not lab2.startswith("_"):
            print(f"| ref. {lab2} | as named | {settable(r, 'inside')} | {settable(r, 'outside')} |")


# ------------------------------------------------------------------ table D: strata
def strata_table(J, lab):
    C = J.get("chains", {}).get("matched", {})
    if not C:
        return
    print(f"\n#### D. Dependability by grounding and loading quartile, relay {lab}, {J['frontend']} front end, "
          f"matched chain + 32P/32Q, loading-bin folds, 5 % budget\n")
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
          "bootstraps over loading bins. Every detector appears unsupervised and with 32P/32Q directional supervision.\n")
    for relay, lab in RELAYS:
        for fe, felab in FES:
            J = load(f"{relay}_{fe}.json")
            if not J:
                continue
            RU = load(f"rules_{relay}_{fe}.json")
            print(f"\n---\n\n### Relay {lab}, {felab}\n")
            if J.get("legacy_note"):
                print(f"> {J['legacy_note']}\n")
            for kind in ("grouped", "loqo"):
                protection_table(J, RU, lab, kind)
            protection_table(J, RU, lab, "grouped", anchor="starter")
            protection_table(J, RU, lab, "grouped", chain="mismatch")
            settable_table(J, RU, lab)
            for kind in ("grouped", "loqo"):
                budget_table(J, RU if kind == "grouped" else None, lab, kind)
            strata_table(J, lab)
            if RU:
                s = RU["settings"]
                print(f"\nSettings: X_set {float(s['x_set']):.2f} Ω, R_set {float(s['r_set_g']):.2f} Ω (legacy {float(s['r_set_g_legacy']):.1f}, "
                      f"cap from Θ = {float(s['polarising_cap']['theta_r2_deg']):.1f}°).")
                print(f"\n{(RU.get('reference_comm') or {}).get('_note', '')}")
