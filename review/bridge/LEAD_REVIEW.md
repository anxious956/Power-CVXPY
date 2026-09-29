# Bridge review, consolidated (28 Sep 2026)

Five specialist reviews (V&V, protection, optimisation, inverter controls, ML/signal processing;
[SPECIALIST_REPORTS.md](SPECIALIST_REPORTS.md)) of the planned "bridge" — Taylor's auxiliary-signal design
method on the CIGRE MV sequence network — consolidated by a lead review that re-checked the decisive claims.
Read-only reviews; every check script is kept outside the repo (session scratchpad). Statements are the
reviewers'; items marked VERIFIED were re-run by the lead review, and the mirrored R1/R3 labels by the main
session (fixed in 8ed3bf2, REVIEW.md §7 row 41).

## Bottom line

1. **δ barely moves the boundary** (VERIFIED in the study model, all four relays). For the nearest
   confusable pair — in-zone at 85 % against a remote-bus fault whose R_f matches it at δ = 0 — δ at the best
   angle separates them by 0.0008–0.024 pu per pu of δ (one exception: R2 LL at 10 Ω, 0.057); most in-zone
   faults have R_f ≥ 25 Ω, where it is ≤ 0.01. A 0.01 pu per-channel error alone then needs ~1 pu of δ or
   more. The δ design will very likely come out "infeasible within headroom"; a one-day screening (B1) can
   establish that before any engine is built.
2. **Several published statements are wrong whatever the R1/R3 re-run shows** (section A).
3. **The 14-bus example is in Taylor's Geometry paper** (arXiv 2510.04379 §IV-C, §VI-D), not TAC25, and
   there δ separates fault *types* on the relay's own line; reach is left to relay characteristics. The
   bridge's in-zone vs out-of-zone question is an extension of the method, not a replication.

## Verification of the decisive claims

| Claim | Verdict | Evidence |
|---|---|---|
| Sum-rule current-limit pruning (|i⁺| ≤ I_max − |δ|) is unsound for a per-phase limiter | CONFIRMED | Largest phase current at the best relative angle is √(x²+xd+d²): x = 0.80, d = 0.56 gives 1.184 < 1.2, yet pruned (sound radius 0.818 vs 0.64). TAC25 (1b) constrains x only (‖i⁺‖ ≤ 1.2); `DESIGN.md:196` "This is TAC25's (1b)" is wrong. min_delta (linear, 0.02 grid): sum rule 0.26 / 0.26 / 0.16 pu (weak_sg / noisy / all_ibr_hard), sound per-phase disc 0.32 / 0.32 / 0.20, TAC25 as written 0.50 / 0.52 / 0.36. weak_sg_eps12 at 1.2 pu: infeasible under the sum rule, feasible at ≈ 0.76 pu under the sound disc — REVIEW §7 row 4 "infeasible outright" is an artefact |
| Headroom "0 % with output kept" is an artefact of the any-angle bound | CONFIRMED (corrected labels) | R1/R3 in-zone, δ = 0.4 pu, output kept: any angle 0 % (20 ms) / 15–16 % (40 ms); one fixed angle in the V1 frame 38–39 % / 76–78 %; best angle per fault 82–83 % / 89–100 %; δ = 0.7 pu at one fixed angle 8–11 % / 21–33 %. `CIGREMV.md` "0.7 pu fits in none at any time" is REFUTED. Static numbers: the inverter's own response to δ is ignored |
| Line types | CONFIRMED | Lines 12-13 (4.89 km), 13-14 (2.99 km), 8-14 (2.0 km) are overhead (distributed); every other line is XLPE cable, lumped PI, 0.24–4.42 km. R3 protects an overhead line; `real_zone.py` gives it cable assumptions; `setting_study` has no shunt capacitance |
| "Even below 5 Ω / bolted included" | REFUTED as worded | In-zone faults with R_f < 5 Ω: 3 / 3 / 13 / 8 (R1–R4, corrected); < 1 Ω: 0 / 0 / 5 / 2. 5 Ω is 1.3–2.4 × |Z1L|; the median R_f is 6–11.5 × |Z1L| |
| Wideband record separates the boundary at R1/R2/R4 | PARTLY | No leak (shuffled labels 0.46–0.52, grouped folds, corrected labels). In-zone vs remote-bus only, wideband spectra: R1 0.81–0.87, R2 0.92–0.94, R4 0.75–0.78, R3 0.55–0.59. Optimistic: true-inception alignment, ~20 variants tried, threshold read on test scores. Present only on the lumped-PI cable lines, absent on R3's distributed line: possibly simulator lumped-network resonances. Enough to narrow the CIGREMV.md claim to the fundamental-frequency front end, not to say a wideband relay works |
| δ barely discriminates at the boundary | CONFIRMED and extended | See bottom line; the two feeders are decoupled in the model (δ at bus 14 has no effect on R1/R2/R4). Model-conditional: ibr_study, additive δ, nominal loading |
| 14-bus example is the Geometry paper | CONFIRMED | Mislabelled in `DESIGN.md`, `REVIEW.md`, `PLAN.md` |

Also VERIFIED: `tac25_design.py:120` counts any non-infeasible solver status as "not separated"; `:79-80`
hard-codes the last two generators as the remote inverter; `ibr_study.solve_fault` returns unconverged
silently and drops the negative-sequence reactor drop; the model is validated at 50 ms while detectors decide
at 20 ms; the validation error is apparent X in |Z1L|, not the per-channel phasor error the LP needs.

## Conflicts resolved

1. **Decision time 40 ms** (window 20–40 ms): a triggered δ cannot fill the first cycle; the static model is
   weakest there (46–55 % of in-zone faults on the limiter at 20 ms vs 10–16 % at 40 ms). 50 ms as a
   robustness row; 20 ms only at δ = 0 to link to the published detectors. This is a two-cycle zone 1, to be
   compared with both-ends schemes at 20 + d ms.
2. **Relay order: R2 first, adapt_A as positive control**, then R1 after the re-run, R3 as negative control,
   R4 optional.
3. **Inverter model:** linear network; each inverter's positive-sequence current a bounded set (from the
   characterised law and recorded envelopes at 40 ms); negative sequence as a y₂ shunt at two values
   (secant ∠−72° and the low-u₂ value); δ added to one inverter's I₂ reference; per-phase rows for
   injectability, pruning only at 1.3 pu. Open negative-sequence path rejected; κ ramp, PLL error, regime
   checks, override mode and priority logic deferred.
4. **EMT reference:** the model's own observable — 16 reals (V0–V2, I0–I2, pre-fault V1, I1), rotated by
   pre-fault V1, per unit, at 40 ms, ∞-norm, same ε; report the ε-ambiguity curve and grouped 1-NN error.
   CNN and wideband results are context only.
5. **Sequencing:** bridge v1 (R2 + adapt_A) does not wait for the R1/R3 re-run; the wideband test is a
   documentation task, not a bridge prerequisite.

## A. Corrections to existing documents

Now (independent of the re-run):

- **A1** `CIGREMV.md` "XLPE cables, 0.24–4.89 km" → cables 0.24–4.42 km (lumped PI) and overhead lines
  12-13, 13-14, 8-14 (2.0–4.89 km, distributed); R3 protects the overhead line 13-14; "cables" → "lines" in
  the headline claims (CIGREMV.md, README, REVIEW §1, row 26); R3's relay profile assumes cable (limitation).
- **A2** "the zone boundary is not in the one-ended measurement" → "not resolved by the 20 ms
  fundamental-frequency measurement behind a 400 Hz relay front end" (final wideband wording after B4).
- **A3** "even below 5 Ω", "bolted included" → state the counts; row 35 → "not testable at low R_f on this
  data".
- **A4** headroom: "at any angle" qualifier, add fixed-angle and best-angle rows; "0.7 pu fits in none" is
  wrong; row 37 revised (numbers after the re-run; `ibr_headroom.py` to compute the angle-aware columns).
- **A5** DESIGN.md §3 "This is TAC25's (1b)", "feasible at 0.16–0.26 pu", "infeasible outright" → the rule
  is the review's own and unsound for a per-phase limiter; re-run with sound rows (B5): ≈ 0.20–0.32 pu,
  ε = 0.12 feasible at ≈ 0.76 pu; REVIEW rows 3–4.
- **A6** "TAC25's 14-bus example" → Geometry paper 14-bus example, separates fault types, needs Baeckeland
  thesis Table 3.1 (not in the repo); not a TAC25 gate (DESIGN.md, REVIEW.md, PLAN.md; PLAN also omits the
  SG angle spread [0, 2π/10]).
- **A7** `cigremv_diagnostics.py` docstring "first stretch" → entire lines beyond; REVIEW §7 row order;
  README note that R1/R3 are provisional.

After the re-run: every R1/R3 number and every range pooled over relays (CIGREMV.md §3, TABLES I, "0–10.5 %",
"72–84", "75.0–77.8 %", the headroom table, REVIEW rows 26 and 35–40, README). R2/R4-only statements stand.

## B. Pre-bridge experiments

| # | What | Cost | Decides |
|---|---|---|---|
| B1 | δ-footprint screening: fault types × m ∈ {0.7, 0.85} × 3 loadings × both y₂; required |δ| ≈ 2ε / gain at the instrument ε, then instrument + model error | ~1 day, seconds of CPU | if |δ| > 1.2 pu in every cell with ≥ 5 EMT faults, drop δ design on CIGRE |
| B2 | model error in phasor space: per-channel residuals of the 16-real observable at 40/50 ms per R_f/|Z1L| band, R2 and adapt_A (R1 after the re-run) | ~1 day, 10–30 min CPU per relay | sets ε_model; if the p90 residual exceeds the in/out distances, the δ = 0 comparison cannot discriminate on CIGRE |
| B3 | EMT reference statistics (§ conflicts 4); near = remote bus + first 20 % beyond | ~0.5 day | adapt_A must be clearly separable, else the observable is wrong |
| B4 | wideband, once and frozen: in-zone vs remote bus and 50–85 % vs near; relay vs wide front end; window keyed on the causal starter; grouped 5×2, 3 seeds, shuffled control | ~30 min CPU | CIGREMV.md wording only |
| B5 | sound per-phase limit rows in `tac25_design`; re-run DESIGN §3, §3.1, §4.1 | 0.5–1 day | A5 |

**B1 done (29 Sep 2026)**, `src/review/b1_delta_screen.py`: direct solves on a |δ| × angle grid (the model is
not linear in δ), all four relays. δ ≤ 1.2 pu adds 8–13 points of separable in-zone faults, 0.4 pu adds 2–4;
every cell with ≥ 5 EMT faults needs no δ or more than 1.2 pu. Stop rule (section D) met at R1–R3, at R4 in
substance: no M3 on CIGRE (results/CIGREMV.md §3, REVIEW.md §7 row 42).

## C. The bridge

Relays R2, adapt_A, then R1 and R3. IN: own line 0–85 % from the relay, four fault types. OUT: remote bus +
first 20 % of the lines beyond. R_f in bands of R_f/|Z1L|; loading over the recorded range; solid and
resistive grounding (resonant needs cable C0). Pairwise separation LP with margin τ; δ one complex injection
at one inverter, minimum |δ| by 2-D polar search confirmed with exact polygons.

| Milestone | Effort | Acceptance |
|---|---|---|
| M0 engine | 3 d | matches `ibr_study.solve_fault` on 20 EMT scenarios with inverter currents fixed (≤ 1e-10); toy optima 0.5040 / 0.6908 / 0.3863 within a grid step; affine in δ ≤ 1e-12 |
| M1 fidelity (= B2) | 2 d | on a held-out half, ≥ 95 % of EMT records inside the ε-inflated model set, else the cell is UNINFORMATIVE |
| M2 verdicts at δ = 0 | 2–3 d | SEPARATED (outer sets, margin > 0, dual re-checked) / AMBIGUOUS (witness replayed through nonlinear ibr_study) / UNKNOWN; adapt_A SEPARATED where EMT separates; fail if "ambiguous" everywhere on both grids |
| M3 δ design and headroom | 2 d | minimum |δ| per cell; fits if ≥ 95 % of the cell's faults are within the per-phase limit at a fixed angle at 40 ms |
| M4 write-up | 2 d | — |

11–12 person-days plus ~4 for B1–B5: 4–6 calendar weeks for four part-time students. Optional M5: Geometry
14-bus replication (+5–8 days), gates nothing. Pre-register (config hash committed before the first EMT
comparison): relay order and injectors, hypotheses, observable and windows, error model, verdict rules, EMT
statistics and ε matching, bands and the ≥ 5-per-class minimum, scoring (Type I = model SEPARATED while the
EMT ambiguity's lower 95 % bound > 0; fail if on ≥ 2 relays), the δ-fits criterion.

## D. Stop or re-scope

| Trigger | Action |
|---|---|
| B1: |δ| > 1.2 pu everywhere | drop M3 on CIGRE, publish the negative result with its mechanism, run the δ design on TestGrid |
| B2: residual swamps the in/out distances | TestGrid becomes the main grid, CIGRE the stress case |
| positive control fails | stop, fix the model or observable |
| solver/tolerance flips a verdict | UNKNOWN |
| M0 not done in 1.5 weeks | extend ibr_study by finite differences instead of a new engine |
| re-run reverses the R1/R3 picture | reorder relays, scope unchanged |

Standing constraint: no claim about δ in EMT is possible; no record contains an injection.

## E. What to ask Prof. Taylor

One short email with a one-page summary: (1) the Geometry paper uses δ for fault types on the own line and
leaves reach to characteristics — is in-zone vs just-beyond separation a meaningful use of δ? (2) should the
current limit include θ, as a per-phase peak or a norm (TAC25 (1b) leaves θ out)? (3) the 14-bus line data
(Baeckeland thesis Table 3.1) or the Simulink model; (4) would a negative result interest him — that a
fundamental-frequency δ cannot resolve the boundary on short MV lines at high R_f? The unsent matrix note
(`docs/notes/taylor_matrix_note.md`) can go with it.

## Where the specialists overreach (lead's view)

V&V: E1–E5, 1e4 Monte Carlo per cell, hash tests and tolerance sweeps are too much; keep the M0 reproductions,
a held-out containment check and 1e3 samples for SEPARATED cells. Optimisation: θ-cell branch-and-bound, MILP
for several injectors and reverse-convex enumeration are too much; a grid plus dense re-check, reported as
"separated on grid". Inverter: y-regimes, κ ramp, PLL error and priority logic are v2; the headroom critique
is right. ML: only experiment 1 (with the near-set fix) matters for the documents; "R4 carries boundary
information" is weak and simulator-conditional. Protection: right on R2 and on the phasor space; its
validation figures are apparent-X errors, not the ε the LP needs.
