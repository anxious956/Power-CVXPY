# Review of the longer-lines study (branch `long-lines`, `4ecacd0`)

> **Status, 1 Nov 2026.** The three pre-merge items of §4 are on `long-lines` at `3627493` (after a clean merge of
> `origin/main` at `f3e7bec`), checked against the diff `f3e7bec..3627493`: (a) dated brackets in README (intro,
> reach row, "Longer lines" row, docs tree, open item 11), PLAN (header, §3, §5 roadmap row, §6, §7 Q2) and REVIEW
> §7 rows 66–68 inserted after row 59 and numbered after KIUC's 60–65; (b) `static --all` writes its own labelled
> `longlines_static_all.json` and never touches the registered file: its k_L 1, 1.5 and 2 entries equal the
> registered ones case for case (only the run times differ) and its k_L 4 entry reproduces the information row
> (8 (4) missed, 14 / 30, 0 / 10, 30 unsettled points), the k_L 3 row is labelled as coming from the uncommitted
> 19 Oct run; (c) the coordinates named as `sector_outer_box` defines them, the L2 0.5 "0" as the split face. The D0
> thinnest-corner bullet was added as information. The frame / network / step-3 tests pass at `3627493` (29).
> Nothing left from this review; the long-lines PR and the merge are the user's.

1 Nov 2026 (night of 31 Oct). Reviewed in a separate worktree. Read `docs/LONG_LINES.md` in full at the tip,
`src/longlines.py`, the branch's diffs of `src/frames.py` (under-relaxed `fixed_point`) and `src/pscad_network.py`
(`key_extra`), and the stage reports the research session sent on 19 and 31 Oct. Every number in LONG_LINES.md's
pre-flight, Q1, Q2 and three Q3 tables was recomputed from the JSONs under `results/network/longlines_*.json`
(counts from the rows, not from the stored summaries). Three checks of my own, all in `review/checks/`:
`p_ll_widen.py` (the separating-angle set above δ* at k_L 2, same FrameModel and seed), `p_ll_witness.py` (the
set-vs-set witness points of the four static binding cases at δ = 0), and the frame / network / step-3 tests at the
tip (`pytest -k "frame or fixed or network or step3"`: 29 passed). No `src/`, `tests/` or `results/` change and no
PSCAD run. The stage reviews of 19 Oct (pre-flight rule, Q1) and 31 Oct (Q2, Q3 structured half) are folded in.

## Verdict

**The registered verdict holds as written:** on this network the deck's claim that δ matters more for detection on
longer lines **does not hold up to 2×**, for both tiers, because the conventional element (D0 at 0.162 pu) misses
0 of 48 at k_L 1, 1.5 and 2, so the "holds" branch of the go / no-go is never reached. The verdict was written
(`1cba06f`) before Q2 finished and nothing in Q2 or Q3 touches it. The curve is information, and the information is
consistent: the box tier's δ* leaves the 1.14 pu cap between k_L 1 and 1.5 (ρ 0.1), the structured design tier
needs 0.06 pu at 1.5 and 0.48 pu at 2, and the 0.48 pu point holds in EMT at the nominal source point.

Every table reproduces from its JSON (§1). The registration was followed, and the one deviation (the pre-flight rule)
was fixed from the voltage table before any Q1 number was read, with me as the reviewer who chose it (§2). Two
readings that I challenged were corrected on the branch and are now right (§3).

**Before merge** (§4): the entry points (README, PLAN, REVIEW §7) do not yet say the study exists; the k_L 3 and 4
"information" rows of the Q1 table have no stored file behind them at any commit; and the witness corner's
coordinates should be named as `sector_outer_box` defines them. None of these changes a number.

## 1. Consistency: tables against the JSONs

| table in LONG_LINES.md | file | recomputed | agrees |
|---|---|---|---|
| pre-flight (V1 at L / R / S, P/P₁, unsettled points, φ_ref, in set) for k_L 1, 1.5, 2, 4, 8 | `longlines_preflight.json` | every cell | yes; set {1, 1.5, 2}; k_L 8 `frame_settles` false, no φ_ref |
| Q1 (D0 missed at 0.162 and 0.126; D1 box alarm / guaranteed; structured) for k_L 1, 1.5, 2 | `longlines_static.json` | 0 / 0 / 0 (0 / 0 / 0); 0/7, 0/11, 1/14; 0/0 ×3; every case flag consistent with its distance (`d1_*_min_boxes` ≤ 2 ⇔ guaranteed, ≤ 1 ⇔ alarm, `d0_worst` < 0.162 ⇔ missed) | yes |
| Q2, 12 keys (unseparated at δ = 0, δ*, angle set, carried angle, margin, price, binding case, inadmissible, dead frames) | `longlines_design.json` | all 12 | yes (see 31 Oct review) |
| Q3 δ = 0 half, k_L 2 | `longlines_emt_zero2.json` | box: 48 contained, 39 separated, bare 0.000, nearest 1.30 ε on L2 0.5 A-G 40 Ω, 7 within 2 ε, 9 within 2.2 ε; structured: 48 / 48, nearest 3.72 ε; D0 0 / 0; gate \|I1\| 0.4467 vs 0.4467 | yes |
| Q3 δ* half, box, k_L 1 (1.12 pu @ 230°) | `longlines_emt_dstar1_box.json` | 48 / 48 contained and separated, bare 0.000, nearest 2.58 ε on L1 0.15 A-G 40 Ω, D0 0 / 0; gate \|I1\| 0.0801 / 0.0801, \|δ\| 1.1201 / 1.12 | yes; the step-3 numbers quoted beside it (2.40 / 2.45 ε, 225°) are in `results/FRAMES.md` lines 241–243 |
| Q3 δ* half, structured, k_L 2 (0.48 pu @ 190°) | `longlines_emt_dstar2_structured.json`, `longlines_specs_dstar2_structured.json` | 48 / 48, bare 0.000, nearest 3.98 ε on L2 0.5 B-C 40 Ω, no window-mixed case, D0 values ≥ 1.5 pu on every row; the four binding A-G cases 5.15 / 5.03 / 4.69 / 4.26 ε (4.44 / 4.13 / 3.93 / 3.72 ε at δ = 0); spec: 49 identical settings, D2MAG 0.48, D2ANG −170°, MODE2 2, TANG 1/(2π·15), k_L 2 lines, `key_extra` kL2 | yes |

Shared code. `frames.fixed_point` now tries plain iteration first and relaxes (0.5, then 0.25) only when plain
iteration has not converged, so every step-3 and I2-study result is unchanged by construction; the 29 frame /
network / step-3 tests pass at the tip. The quoted regress figures (3.1·10⁻¹³ against FrameModelMulti) were not
re-run here. `run_fast`'s `key_extra` gives the scaled line its own built project, which is what the gate numbers
(0.0 % from static at k_L 2) confirm.

## 2. Registration integrity

- **The pre-flight rule.** The registered 0.9–1.1 pu window excluded k_L 1 itself (S at 0.805 pu). The doc says so,
  calls it a registration error, and records that the rule was re-fixed from the voltage table alone before Q1 was
  read. That is accurate: on 19 Oct I chose rule B (load power ≥ 75 % of its k_L 1 value) from the table without
  opening the Q1 section, with the 1.5 fallback and the frame-settles condition. k_L 2 passes by a hair (S at 0.780).
- **The set is {1, 1.5, 2}** by that rule, and the verdict is stated as conditional on it ("up to 2× on this
  network"), as the registration required.
- **Q3 placement** follows §3: the δ = 0 half at k_L 2 (D0 never misses a quarter, 4 is out, so the largest in the
  set); the box δ* half at k_L 1 (the largest k_L with a feasible box δ* at ρ 0.1); the structured δ* half at k_L 2.
  The carried angle is the largest-margin angle at every key (230°, 280°, 190°, 265°). No run at the cap where δ*
  is infeasible.
- **Stop rules kept.** No pickup, angle or tier was re-tuned after a result; a sensitivity run at the ρ 0 point
  (0.20 pu @ 265°) was proposed and declined (31 Oct), correctly: it is unregistered and 265° does not separate at
  ρ 0.1 at 0.50 or 0.54 pu either.
- **The prior's two predictions are met.** δ*(k_L) is non-decreasing in both tiers (box 1.12 → none → none;
  structured 0 → 0.06 → 0.48). The conventional element's thinnest corners are far-end, high-R_f B-C faults on L2 at
  every k_L (L2 m 0.5 B-C 40 Ω: worst corner 0.280 → 0.219 → 0.176 pu against the 0.162 pu pickup), and its first
  misses in the k_L 3 and 4 information rows are the same cases.

## 3. Independent checks, and the two readings that were corrected

**The δ*(k_L) jump and "knife-edge".** The first report called the k_L 2, ρ 0.1 point knife-edge because its margin
is 0.011 ε. The margin at δ* is where the gap crosses 2(1 + ρ)ε inside one 0.02 pu grid step, so it is bounded by
the gap growth over that step and all six feasible margins sit at 0.005–0.047 ε by construction; it does not rank
robustness. `p_ll_widen.py` extends the angle set above δ*: {190} at 0.48 pu, {190, 195} at 0.50 and 0.54 pu, and
no separating angle in 240–300° at either radius (5° resolution; the third radius, 0.60, and the gap-vs-radius
curve did not run, the machine ran out of memory). So the point is feasible only in a wedge of about 10° that does
not widen with 12 % more δ. The doc now says this and cites the check. The jump from 0.06 to 0.48 pu is a change of
binding direction (270–285° at k_L 1.5 → 190° at k_L 2) as two more 40 Ω A-G faults at the R-bus end join the
unseparated set; at ρ 0 the k_L 2 set (245–295°) continues k_L 1.5's direction. The doc says this too.

**Where the static meeting at δ = 0 comes from.** The research session read the EMT distances (binding cases 3.7–
4.4 ε clear at δ = 0 at the nominal point) as "the static unseparated cases come from the source-box corners".
`p_ll_witness.py` (the witness LP with `longlines.gap`'s per-component ε weighting, same FrameModel) confirms it:
set-vs-set gaps 2.13 / 1.96 / 1.74 / 1.49 ε against 2.2 for L1 0.95, L2 0.05, L2 0.25, L2 0.5 (all 40 Ω A-G), the
fault-side witness at the corner S_F = (−1, −1, −1, +1) for the first three and (−1, −1, 0, +1) for L2 0.5, the
fault-frame drift symbol at +1 and λ = 0 in all four, the normal-side witness on the faces S₁ = −1, S₃ = +1. The
doc carries this with the citation. The coordinates are `sector_outer_box`'s: S₀, S₁ are the source EMF's radial
(magnitude) and tangential (angle) coordinates of a box aligned with the nominal phasor, S₂, S₃ the inverter
command's; the "0" in L2 0.5's third slot is the magnitude at the split boundary of the two sample pieces, so it is
on a piece face, not an interior point. §4 (c) asks for that naming.

**"Bolted".** The first Q2 report called the binding case bolted; it is the 40 Ω fault (R_f/r_F = 1.0), and every
unseparated case in the structured tier at every key is a 40 Ω A-G fault. Corrected on the branch.

**Information the doc could add, not asked for.** At k_L 2 the conventional element clears its pickup at the worst
corner by 0.014 pu (0.176 vs 0.162) on the L2 m 0.5 B-C 40 Ω case, after 0.280 and 0.219 at k_L 1 and 1.5. The
"misses nothing" at the end of the set is therefore by a thin margin on one case, but the go / no-go needs twelve
missed cases, so the verdict is not near its threshold. The two elements fail on different faults: D0 on far-end
high-R_f **B-C** faults, the set test on 40 Ω **A-G** faults.

## 4. Before merge

- **(a) Entry points.** The branch changes four files and none of them is an entry point. By the supersession
  convention the study must appear where the earlier, static-only statements are:
  - `README.md` row "Longer lines" (line 68) still ends "Not yet checked in EMT". Add, dated: checked in EMT with δ
    injected (docs/LONG_LINES.md): the claim does not hold for detection up to 2× on this network (D0 misses 0 of
    48); the structured design tier needs δ from 1.5× (0.06 pu) and 0.48 pu @ 190° at 2×, which holds in EMT at the
    nominal point; the box tier's δ* leaves the 1.14 pu cap between 1× and 1.5×.
  - `docs/PLAN.md` §2 / §5 / §6 / §7 and the roadmap row "Nov–Dec 2026: the deck's scenarios with δ injected":
    longer lines done, with a pointer; §7 question 2 ("None of the three has been tested with δ injected in EMT")
    is now out of date for two of the three (I₂ suppressed, PRs #57–#58; longer lines, this branch).
  - `REVIEW.md` §7: three rows, numbered after the KIUC rows if PR #65 merges first (66–68, else 60–62):
    (i) the claim "δ matters more for detection on longer lines" → NOT SUPPORTED up to 2× on this network, both
    tiers, EMT with δ injected at the nominal point, with the D0 counts and the cap crossing; (ii) the pre-flight
    registration (0.9–1.1 pu window) → WITHDRAWN before Q1 was read, replaced by rule B, set {1, 1.5, 2}, range
    limited by the base network's load flow; (iii) the curve as information: structured δ* 0 → 0.06 → 0.48 pu in a
    ~10° wedge, holds in EMT at the nominal point, static meeting at one source-box corner. The branch adds no REVIEW
    rows now, so it will not conflict with `kiuc`'s rows 60–65 at merge.
- **(b) The k_L 3 and 4 information rows** of the Q1 table (D0 missed 3 (1) and 8 (4), D1 7/23 and 14/30,
  structured 0/1 and 0/10, with named cases) have no stored file: `longlines_static.json` holds only the set at every
  commit on the branch, and no other static file was ever committed. Either store the `--all` run's output as its own
  file (e.g. `longlines_static_info.json`, labelled outside the set) or say in the table that the rows are from an
  uncommitted 19 Oct run and cannot be re-read. They carry no weight in the verdict, but the doc names cases from them.
- **(c) Coordinate naming** in the Q3 structured section: "(−1, −1, −1, +1)" = source EMF magnitude and angle at
  their lower bounds, inverter command magnitude at its lower bound and angle at its upper bound; for L2 0.5 the
  command magnitude at the split boundary (0), still a face of the piece. The current wording ("both coordinates …
  at −1", "first coordinate at its centre") is not wrong; this names them.
- **(d) Small.** §1 still registers k_L ∈ {1, 2, 4, 8}; the dated rule-B section supersedes it, which is the
  convention, and no bracket is needed. The Q1 table head says "D0 missed at 0.162 pu (at 0.126)": fine. §5
  caveats are complete for this branch.

## 5. Not checked

- The PSCAD runs were not repeated and the raw channels were not re-decided with an independent chain (unlike the
  KIUC review): the analysis chain is step 3's, reviewed at PR #44, and the three halves' gates (0.0–0.2 % from
  static) and the bare error of 0.000 ε on every window leave little room for a chain error to hide.
- `i2dir_design.py regress` after the `fixed_point` change was not re-run; the tests were.
- The third radius (0.60 pu) and the gap-vs-radius curve at 190° (both MemoryError).
- FrameModel's structured-tier ε vector and instrument model are inherited from step 3 and were not re-derived.
