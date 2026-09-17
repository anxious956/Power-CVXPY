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
    if not S or not any(f"{n} | {front} | {mode} | {t} | {sp}" in S for n, _ in RELAYS for sp in splits):
        return
    label = {"current": "current front end", "relay front end": "relay front end (AA 400 Hz + CT full scale)",
             "CT full scale only": "CT-based ADC full scale only"}[front]
    print(f"\n#### Learned models, {label}, {mode.replace('own99', 'own-99 %')}, {t}\n")
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


def settings_table():
    """Old -> new resistive reach under the Kasztenny 2021 eq. (19) polarising-error cap."""
    O, N = R("ladder.json"), R("ladder_polcap.json")
    if not O or not N:
        return
    print("")
    print("#### Resistive reach: load-encroachment rule vs the polarising-error criterion")
    print("")
    print(r"| Relay | \|Z1L\| (Ω) | Θ untilted (R2/T2) | Θ residual (R3/R4) | R_set old g/p (Ω) | "
          r"R_set new g/p (Ω) | Required arc+tower coverage (Ω) | Covers it? | Reach needed to keep the old R_set |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, lab in RELAYS:
        if name not in N:
            continue
        s, o = N[name]["settings"], O[name]["settings"]
        P = s["polarising_cap"]
        cov = "yes" if s["coverage_ok_g"] else f"**no**, short by {s['coverage_deficit_g']:.1f} Ω"
        print(f"| {lab} | {s['z1L_abs']:.2f} | {P['theta_r2_deg']:.2f}° | {P['theta_r3_deg']:.2f}° | "
              f"{o['r_set_g']:.1f} / {o['r_set_p']:.1f} | **{s['r_set_g']:.1f} / {s['r_set_p']:.1f}** | "
              f"{s['r_cov_g']:.1f} | {cov} | {s['reach_if_legacy_rset_kept']*100:.0f} % of line |")


def sir_table():
    S = R("sir.json")
    if not S:
        return
    print("")
    print("#### Source-to-line impedance ratio, and the CCVT transient margin it leaves")
    print("")
    print(r"| Relay | SIR \|Z_S\|/\|Z1L\| | SIR voltage-based, ground | phase | V at a remote-bus fault (LG) | "
          r"IZ−V margin at 0.85 reach (G) | Regime |")
    print("|---|---|---|---|---|---|---|")
    for name, lab in RELAYS:
        o = S["relays"].get(name)
        if not o:
            continue
        print(f"| {lab} | {o['sir_impedance_ratio_seq1']:.2f} | {o['sir_voltage_G']:.2f} | {o['sir_voltage_P']:.2f} | "
              f"{o['V_pu_remote_bus_G']*100:.1f} % | {o['op_signal_margin_G']*100:.2f} % | {o['regime_G']} |")
    C = S.get("cvt_transient_margin")
    if C:
        print("")
        print("Kasztenny & Chowdhury 2023 eq. (6): CCVT residual at 20 ms scaled by the voltage change")
        print("at a remote-bus fault, against that margin.")
        print("")
        print("| CVT model | Passes class T1 | Residual at 20 ms, full collapse | Relay / loop | Scaled error | Margin | Secure? |")
        print("|---|---|---|---|---|---|---|")
        for variant, V in C.items():
            for k, r in V["per_relay"].items():
                print(f"| {variant} | {V['passes_class']['T1']} | {V['residual_20ms_full_collapse']*100:.2f} % | {k.replace('|', ' / ')} | "
                      f"{r['scaled_cvt_error']*100:.2f} % | {r['op_signal_margin']*100:.2f} % | "
                      f"{'yes' if r['secure_by_criterion'] else '**NO**'} |")


if __name__ == "__main__":
    settings_table()
    sir_table()
    ladder("ladder.json", "Conventional ladder, current front end — LEGACY R_set (load encroachment only)")
    ladder("ladder_polcap.json", "Conventional ladder, current front end — CORRECTED R_set (polarising-error cap)")
    ladder("ladder_relayfe.json", "Conventional ladder, relay front end — LEGACY R_set")
    ladder("ladder_polcap_relayfe.json", "Conventional ladder, relay front end — CORRECTED R_set")
    for front in ("current", "relay front end", "CT full scale only"):
        for t in ("10 ms", "20 ms", "50 ms"):
            zone_cv(front, "own99 guard", t)
    zone_cv("current", "own99 negative", "20 ms", ("grouped",))
