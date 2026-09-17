"""Markdown tables for REVIEW.md, generated from the result JSONs (no number is copied by hand).

    python src/review/tables.py > logs/review_tables.md
"""
import os, json
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
R = lambda f: json.load(open(os.path.join(ROOT, "results", "review", f))) if os.path.exists(os.path.join(ROOT, "results", "review", f)) else None
pct = lambda x: "–" if x is None else f"{100 * x:.1f}"
RELAYS = (("testgrid_A", "A"), ("testgrid_B", "B"), ("doubleline", "DoubleLine"))


def kn(d):
    return "–" if d is None else f"{d['k']}/{d['n']} (≤{100 * d['ucb95']:.1f})"


def ladder(fn, title):
    L = R(fn)
    if not L:
        return
    print(f"\n#### {title}\n")
    for t in ("10", "20", "50"):
        print(f"\n**{t} ms**\n")
        print("| Relay | Rung | Dependability | Dep. at 40 Ω | Beyond / remote bus | Own line 99 % (guard) | Relay-bus reverse | Lines behind | Parallel | Switching |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for name, lab in RELAYS:
            if name not in L:
                continue
            F = L[name]["fixed"]
            for rung in ("R0", "R1", "R2", "R3", "R4"):
                k = f"{t}|{rung}"
                if k not in F:
                    continue
                r = F[k]
                g = lambda h: (f"{r[h]['k']}/{r[h]['n']}" if h in r else "–")
                print(f"| {lab} | {rung} | {pct(r['pos']['rate'])} | {pct(r['dep_by_rf']['40'])} | {kn(r['neg']['dedup'])} | {g('own99')} | "
                      f"{g('reverse_bus')} | {g('reverse_lines')} | {g('parallel')} | {g('switching')} |")
            T = L[name]["tuned"]
            for rung in ("T1", "T2"):
                k = f"{t}|grouped|{rung}|own99-guard"
                if k not in T:
                    continue
                r = T[k]
                h = lambda c: (pct(r["held"][c]["mean_rate"]) if c in r["held"] else "–")
                print(f"| {lab} | {rung} (grouped folds) | {pct(r['dependability'])} | {pct(r['dep_by_rf']['40'])} | {kn(r['beyond_dedup'])} | "
                      f"{h('own99')} | {h('reverse_bus')} | {h('reverse_lines')} | {h('parallel')} | {h('switching')} |")
            if t == "20":
                r = L[name]["tilt_robustness"]["20"]
                print(f"| {lab} | R3 worst case over tilt {r['tilt_range_deg'][0]:.1f}…{r['tilt_range_deg'][1]:.1f}° | ≥{pct(r['dep_min'])} | ≥{pct(r['dep40_min'])} | ≤{pct(r['beyond_max'])} | ≤{pct(r['own99_max'])} | ≤{pct(r['reverse_bus_max'])} | ≤{pct(r['reverse_lines_max'])} | ≤{pct(r['parallel_max'])} | – |")
                ref = L[name]["reference_67"]["20"]["67N or 67Q"]
                print(f"| {lab} | ref. 67N or 67Q (detection, no reach) | {pct(ref['pos']['rate'])} | {pct(ref['dep_by_rf']['40'])} | {pct(ref['neg']['rate'])} | {pct(ref['own99']['rate'])} | "
                      f"{pct(ref['reverse_bus']['rate'])} | {pct(ref['reverse_lines']['rate']) if 'reverse_lines' in ref else '–'} | {pct(ref['parallel']['rate']) if 'parallel' in ref else '–'} | {pct(ref['switching']['rate'])} |")


def zone_cv(front="current", mode="own99 guard", t="20 ms", splits=("stratified", "grouped", "lolo", "lorfo")):
    S = R("zone_cv_summary.json")
    if not S:
        return
    print(f"\n#### Learned models, {front} front end, {mode}, {t}\n")
    print("| Relay | Split | Model | AUC | Dependability [95 % CI] | Dep. at 40 Ω | Beyond / remote bus k/n (≤UCB) | Own 99 % (guard) | Relay-bus reverse | Lines behind | Parallel | Other | Switching | + directional: dep / beyond / reverse bus / switching |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, lab in RELAYS:
        for sp in splits:
            key = f"{name} | {front} | {mode} | {t} | {sp}"
            if key not in S:
                continue
            X = S[key]
            for m, M in X["models"].items():
                h = lambda c: (pct(M[c]["mean_rate"]) if c in M else "–")
                s = M["with_directional_supervision"]
                hs = lambda c: (pct(s[c]["mean_rate"]) if c in s else "–")
                print(f"| {lab} | {sp}{'' if X['complete'] else ' (incomplete)'} | {m} | {M['auc']:.3f}±{M['auc_sd']:.3f} | {pct(M['dependability'])} "
                      f"[{pct(M['dependability_ci'][0])}, {pct(M['dependability_ci'][1])}] | {pct(M['dep_by_rf'].get('40'))} | {kn(M['beyond'])} | "
                      f"{h('own99')} | {h('reverse_bus')} | {h('reverse_lines')} | {h('parallel')} | {h('other')} | {h('switching')} | "
                      f"{pct(s['dependability'])} / {kn(s['beyond'])} / {hs('reverse_bus')} / {hs('switching')} |")


if __name__ == "__main__":
    ladder("ladder.json", "Conventional ladder, current front end")
    ladder("ladder_relayfe.json", "Conventional ladder, relay front end (AA 400 Hz + CT full scale)")
    for front in ("current", "relay front end", "CT full scale only"):
        for t in ("10 ms", "20 ms", "50 ms"):
            zone_cv(front, "own99 guard", t)
    zone_cv("current", "own99 negative", "20 ms", ("grouped",))
