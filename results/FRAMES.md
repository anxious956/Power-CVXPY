# The design with the frames a real system has: the signal takes almost the whole inverter

16 Oct 2026. Part of step 3 ([docs/STEP3.md](../docs/STEP3.md)), done before any detector because the review of the
plan found it would otherwise decide the result ([review/STEP3_PLAN_REVIEW.md](../review/STEP3_PLAN_REVIEW.md) §3.2,
§3.3, §6). Code: `network.solve_v1ref`, `src/frames.py`, `src/frames_design.py`. Numbers:
`results/network/frames_design.json`. Static model only; the EMT side waits for PSCAD.

## Two frames the design had assumed away

- **The inverter's frame.** A real inverter sets I1 and δ at angles to its own measured V1, with fixed settings. The
  design (results/MULTIBUS.md) took them as absolute phasors. `network.solve_v1ref` solves the realistic inverter as a
  fixed point, limiter included. Against the 96 stored three-bus EMT fault runs at 0.38 s, |EMT − model| at the relay
  falls from median 0.027 / max 0.177 pu (absolute model) to **median 0.0023 / max 0.030 pu**. The rotation the review
  found (δ turning up to 29° when a fault starts) is fully this mechanism.
- **The relay's frame.** A relay references its phasors to its own pre-fault V1 memory. It cannot see the absolute
  frame the design used.

## How they enter the design

Each case's measurement set, in the relay's frame, is enclosed in a union of two zonotopes. The source box is split
along the commanded-current magnitude, the limiter's kink axis. Each zonotope is a near-minimax linear model in
shared symbols plus a remainder box. The shared symbols are:

- the four source symbols;
- for faults, the inverter frame's move through the relay window and a ±6° drift margin;
- the relay reference's own noise rotation, at most ε/|V1_L|, with ε defined in the relay's frame.

The remainder is the largest residual over sampled points: box corners, a grid on every 2-face, and random interior
points. It stays at 0.4–0.97 ε. This is **verified by sampling, not proved**:

- adversarial containment at δ* and 0.02 below it: no sample outside its set;
- Calafiore–Campi coverage ≥ 99.97 % at confidence 1 − 10⁻³;
- separation at δ* unchanged at remainder factors 1.0, 1.1 and 1.25.

The design is no longer convex in δ; the polar grid search stays exact at each candidate. Commands with
|δ| = I_max have no settled inverter state, because the limiter leaves no I1 and δ is referenced to the V1 it alone
creates; the search stays below the limit.

## Result

| | absolute frames (MULTIBUS.md) | **both frames** |
|---|---|---|
| cases not separated at δ = 0 | 8 / 48 | **11** (ρ = 0), **13** (ρ = 0.1) / 48 |
| δ*, no margin | 0.62 pu | **0.94 pu** at 225° |
| δ*, 10 % margin | 0.90 pu | **1.14 pu** at 225° |
| inverter current left beside δ*, no margin | ≤ 0.46 pu | **0.14–0.33 pu**, cut by up to 66 % |
| inverter current left beside δ*, 10 % margin | — | **0.06–0.10 pu**, cut by up to 92 % |
| shared symbols vs everything boxed (ρ = 0.1) | — | 1.14 vs 1.16 pu |

On this grid, once the inverter references its injection to its own V1 and the relay to its own memory, the
guaranteed design needs nearly the whole inverter for the signal. With the margin it leaves under a tenth of the
inverter's rating for active and reactive power. The shared symbols buy almost nothing (0.02 pu): the frames cost is
real, not an artefact of loose sets.

## EMT with the signal injected: the 1.14 pu design does not exist, 1.05 pu at 225° does (16 Oct 2026, evening)

The table above is static. Review of PR #44 asked for two budgets the result rests on: the relay reference's
rotation φ_ref and a box for the static-vs-EMT model error. `src/frames_emt_check.py` measures the second on PSCAD
runs with δ injected by the V1-referenced inverter. Settings are fixed in the inverter's own frame, as the frame model
has them. There were 168 runs: |δ| 0.9 and 1.14 pu on all 48 cases plus 8 normals; 1.0 and 1.05 pu on the 24
phase-to-phase cases plus 4 normals. All at 225°, at random points of the source box, the same points across
1.0 / 1.05 / 1.14 pu. Each run is compared in the relay's frame on windows ending 2, 2.25, …, 3 cycles after
inception, with the frame-model sets at model_err = 0.

| \|δ\| | fault points outside their own set | largest \|EMT − settled model\| | EMT settles, in the 2–3-cycle window |
|---|---|---|---|
| 0.90 pu | 12 of 240, at most **0.073 ε** | 0.40 ε | all 48 cases |
| 1.00 pu | 0 of 120 | 0.47 ε | the 24 ab cases run (no A-G run) |
| 1.05 pu | 0 of 120 | 0.54 ε | the 24 ab cases run (no A-G run); **3 of 8 bolted ab runs drift up to 21° after 3 cycles** |
| 1.14 pu | 90 of 240, up to **18.7 ε** | 18.9 ε | **not on 7 bolted ab faults** |

- **At 1.14 pu the inverter does not settle on bolted phase-to-phase faults.** The δ-priority limiter cuts I1 to
  0.06 pu. The inverter's angle, from its one-cycle DFT of V1, keeps turning through the fault: δ turns 80° in three
  cycles, and the relay current reaches 3 pu against 1.4 pu at 0.9 pu. The static fixed point exists, is unique and
  has a small angle gain (≈ 0.25, falling with |δ|). The failure is dynamic. It grows smoothly with |δ|, occurs on
  phase-to-phase faults only (where δ makes positive-sequence voltage at the inverter's own bus), and the runs first
  approach the fixed point and then leave it. The review (review/STEP3_PART3_REVIEW.md §2) finds that δ's own term
  over the smallest |V1_R| on the circle orders the cases checked (0.59 / 0.67 hold, 0.73 / 0.79 drift at 1.05 pu,
  0.87 / 1.94 diverge at 1.14 pu). The mechanism is not established. Whatever it is, it belongs to **this**
  controller (a one-cycle DFT reference, no PLL), not to inverters in general.
- **Even at 1.05 pu the settled state holds only in the decision window.** On bolted ab faults, 3 of 8 runs leave it
  between 3.25 and 5.5 cycles, by up to 20.8°, before the fault clears at 6 cycles (1.00 pu: 2.6°; 0.90 pu: 0.3°). D1's
  guarantee survives if it decides within 2–3 cycles. The inverter then keeps injecting about 1 pu of drifting δ
  until the fault clears, a behaviour of the protected system, not just of the relay.
- **The model error the sets need is small where the inverter settles.** Measured as the distance to the set, not
  to the settled point, it is at most 0.073 ε: the frame symbols (λ, drift) already cover the turn through the window.
  The earlier box of 0.25 ε (the distance to the settled point, `frames_main_err025.json`) double-counted it.
  The evidence is thin, and 0.1 ε is **provisional**. It comes from one random interior source point per case, at
  225° only, with one inception time, and no A-G case at 1.00 / 1.05 pu. The worst point is at the window's 2.0-cycle
  edge. The remainder factor 1.1 adds 0.04–0.1 ε of headroom on top; it is reported as margin, not as model error.
- **The design with measured budgets.** Main configuration: φ_ref 0.0303 rad, model error 0.1 ε, drift 3°,
  window 2–3 cycles. |δ| is capped at 1.05 pu: the largest level at which this controller holds its state in
  EMT, measured at 225° on ab faults inside the decision window. Results:
  - At ρ = 0.1, no δ up to 1.05 pu separates.
  - At 1.05 pu, 225° every case separates for ρ up to 0.05; the binding case is L1 15 % A-G at full R_f.
  - Between 60° and 165° at 1.05 pu the inverter has no settled state in the static model.
  - Per angle at 1.05 pu (cases unseparated at ρ = 0): 210–225° none; 195° 5; 240° 5; 270° 20.
  - The design point for step 3 is **δ = 1.05 pu at 225°, ρ = 0.04**, 87.5 % of the inverter's rating. ρ is chosen
    to make the design feasible (the largest is 0.05). The whole margin, 2ε·0.04 = **0.08 ε**, is about the
    **0.073 ε** seen outside the sets: the design has almost no slack left if the model error is larger. Its
    checks (`results/network/frames_main_fixed.json`):
    - separating window at 1.05 pu: **221–230°**;
    - separation on the dense tier at remainder factors 1.0, 1.1 and 1.25: all hold;
    - adversarial containment: no sample outside its set; Calafiore–Campi coverage ≥ 92 % (β = 10⁻³);
    - continuous (m, R_f) between the design cases: **0 of 486** unseparated inside the design's ranges
      (L1 15–95 %, L2 5–50 %). 48 of the 198 faults outside those ranges are unseparated: 44 are L2 ab at 65–95 %,
      4 are A-G at full R_f on L1 5–10 % and L2 90–95 %. The guarantee covers only the fault set it was designed for;
    - inverter current left beside δ: **0.14–0.25 pu** (median 0.16) of 0.14–0.78 pu asked, cut by up to 68 %.

**What this changes.** "δ* = 1.14 pu at 225° (ρ 0.1)" above is a static-model number that EMT does not support:
REVIEW.md §7 row 51. The headline gets stronger, not weaker. With the frames, the measured model error and the
inverter's dynamics, the guarantee on this network needs 87.5 % of the inverter. It holds only in a narrow angle
window, with a 5 % margin at most, and only within the 2–3-cycle window on bolted ab faults. The 1.05 pu cap is
verified at 225° on ab faults only. The design point's own EMT check (binding cases at their witnesses, window
edges, point on wave, normal corners, confusers) is review §5 and comes next.

## The design point in EMT (17 Oct 2026)

`src/frames_design_check.py`, 71 PSCAD runs at δ = 1.05 pu, 225°, ρ = 0.04 (review/STEP3_PART3_REVIEW.md §5). Output:
`results/network/frames_design_check.json`. Faults are judged on windows ending 2.0–3.0 cycles after each run's own
inception. Two distances are reported. The first is to the case's own set, built bare: factor 1.0, no reference
noise, no model-error box. This is what the model error must cover. The second is the clean distance to N in the
design's sets, which separates with the margin above 2(1 + ρ) = 2.08 ε.

| group | runs | outside own set, 2–3 cycles | clean distance to N, smallest | outside own set after 3 cycles |
|---|---|---|---|---|
| 13 binding cases at their witness realisations | 13 | **0** | **2.33 ε** (L1 15 % A-G, full R_f; the design's own gap there is 2.10 ε) | 0 |
| window edges 221° / 230° (8 bolted ab, 3 hardest A-G) | 22 | **0** | 2.34 ε | up to 15.6 ε (bolted ab) |
| inception over one cycle (same 11 cases, 225°) | 11 | **0** | 2.33 ε | up to 10.1 ε (bolted ab) |

| normal operation | runs | outside N (bare sets) |
|---|---|---|
| witness normals | 2 | 0 |
| 16 corners of the source box | 16 | at most 0.034 ε (inside the 0.1 ε box) |
| balanced load step at bus S | 1 | **0.87 ε** |
| single-phase load at bus S | 1 | 0.41 ε |

- **Inside the decision window the design point holds in EMT where it is tightest.** At the witnesses, the window
  edges and random inception angles, no fault point leaves its own set, and every fault stays at least 2.33 ε from N
  against the 2.08 ε the margin needs. The provisional 0.1 ε model error is not used up there. In the design itself
  the binding gap is **2.10 ε against 2.08 ε** (L1 15 % A-G, full R_f): it holds there by 0.02 ε. EMT has more room
  (2.33 ε) because its realisation is not the design's extreme pair.
- **After 3 cycles bolted ab faults leave their sets** (up to 15.6 ε), as the review found. A decision after 3 cycles
  is not covered.
- **A balanced 0.2 pu load step moves normal operation 0.87 ε outside N.** On clean data that is below D1's alarm
  threshold (distance > ε), but not by much: about 0.2 ε of measurement noise in the wrong direction makes D1
  alarm. The single-phase load (0.41 ε) is the same question. **Decision (17 Oct 2026): loads stay fixed in the
  design**, as in network.py and the TAC25 formulation. D1's false alarms on load steps and unbalanced loads are
  reported as a designed-in limitation in the violation matrix, not as a discovery. Giving N a load-scale symbol
  would be a new design, outside the four steps (review/STEP3_PART4_REVIEW.md §2.4, option b).
- **The drift belongs to the controller's bare DFT reference.** Four instrumented runs, with a 0.3 s fault and the
  controller's own outputs recorded:

  | run | angle reference | reference angle span over the fault | outside own set at 2 / 3 / 5 / 8 / 12 / 16 cycles |
  |---|---|---|---|
  | 1.14 pu, L1 ab 15 % bolted | bare DFT | 451° (runs away) | 13.6 / 18.7 / 12.9 / 21.7 / 23.9 / 15.9 ε |
  | 1.14 pu, L1 ab 15 % bolted | DFT + 15 Hz low-pass (PLL-like) | 26° | 0.04 / 0 / 0 / 0 / 0 / 0 ε |
  | 1.05 pu, L1 ab 35 % bolted | bare DFT | 112° | 0 / 0 / 2.9 / 6.6 / 1.4 / 15.2 ε |
  | 1.05 pu, L1 ab 35 % bolted | DFT + 15 Hz low-pass | 25° | 0 at every window |

  A first-order 15 Hz low-pass on the angle reference (a **PLL-like reference filter**, not a PLL: a real SRF-PLL
  is second order, tracks frequency, overshoots and can itself go unstable on weak grids) removes the instability at
  1.14 pu and the drift at 1.05 pu. The model then holds through the whole fault. The 1.05 pu cap is therefore a
  property of the bare-DFT controller, as the review suspected. The bare-DFT instability is an equipment-level
  finding, not only a relay one: at 1.14 pu the inverter's own measured |V1| swings between 0.23 and **2.76 pu**
  (0.40–0.77 pu with the filter). Step 3 uses the filtered reference. The cap under it, the window start and a 10 / 30 Hz
  sensitivity are measured by `src/frames_pll_check.py` (review/STEP3_PART4_REVIEW.md §3). A component regression run (TANG = 0) reproduces the stored run exactly (difference 0).

## The cap with the PLL-like reference filter (17 Oct 2026)

`src/frames_pll_check.py`, 136 PSCAD runs with the first-order 15 Hz reference filter. Output:
`results/network/frames_pll_check.json`. The runs cover |δ| 1.05 / 1.10 / 1.14 / 1.18 pu at 221°, 225° and 230°,
on the 8 bolted ab cases and the 3 hardest A-G witnesses. Each run is judged against its own bare set on windows
ending 1.5–5.5 cycles after inception, i.e. through the whole fault.

| \|δ\| | outside own set from 2.0 cycles, largest | from 2.25 cycles to 5.5 cycles | clean distance to N, 2–3 cycles, smallest |
|---|---|---|---|
| 1.05 pu | 0.001 ε | 0 | 2.30 ε |
| 1.10 pu | 0.022 ε | 0 | 2.37 ε |
| **1.14 pu** | **0.086 ε** (inside the 0.1 ε box) | **0** | 2.43 ε |
| 1.18 pu | 0.136 ε (outside the box) | 0.031 ε at 2.5 cycles, 0 from 3 cycles | 2.49 ε |

- **With the filter the inverter settles at every level, through the whole fault.** The largest excursions sit at the
  2.0-cycle window (L1 ab 15 % bolted), and every point is back inside by 2.25 cycles.
- **The new cap is 1.14 pu.** The criterion: the inverter settles through the whole fault, and its window excursions
  fit the 0.1 ε model-error box. With the filter every level settles, 1.18 pu included, so the box decides:
  - 1.14 pu: largest excursion 0.086 ε, inside the box;
  - 1.18 pu: 0.136 ε, outside it.

  At the cap the inverter keeps about 0.06 pu of I1 (95 % of rating goes to δ). The cap does not bind at ρ = 0.1:
  the design point below is 1.12 pu.
- **The conclusion does not hinge on 15 Hz.** With 10 Hz and 30 Hz filters, the two instrumented cases (1.14 pu L1 ab
  15 %, 1.05 pu L1 ab 35 %, 0.3 s fault) stay within 0.04 ε at 2 cycles and at 0 from 3 to 16 cycles.
- The window start stays at 2 cycles, inside the 0.1 ε box. From 2.25 cycles no box is needed at all at 1.14 pu.
- **The excursions are DC offset in the relay's one-cycle DFT, not an inverter transient**
  (`src/frames_mimic_check.py`, results/network/frames_mimic_check.json). They appear at windows ending 1.5 and
  2.0 cycles, are 0 at 1.75 and 2.25, and every run used t_fault = 0.30 s. Re-evaluated every 1/16 cycle with a
  mimic filter on the currents (L1's X/R, τ = 1.59 cycles, unity fundamental gain), the stored runs give:

  | \|δ\| | plain DFT, largest from 2.0 cycles | with mimic | with mimic, every point inside from |
  |---|---|---|---|
  | 1.05 pu | 0.001 ε | 0 | 1.5 cycles |
  | 1.10 pu | 0.022 ε | 0 | 1.5 cycles |
  | 1.14 pu | 0.086 ε | **0** | 1.625 cycles |
  | 1.18 pu | 0.136 ε | 0.005 ε | 2.06 cycles |

  **D1's chain gets the mimic filter.** With it the model-error box is not used by the window start at all, and an
  earlier window (1.75 cycles) is open. Both still have to be confirmed over inception angles, on the design-point
  batch.

## The step-3 design point: 1.12 pu at 225°, ρ = 0.1, with the filtered reference (17 Oct 2026)

`python src/frames_main.py --rmax 1.14 --rho 0.1 --tag pll`, `results/network/frames_main_pll.json`. Same budgets as
the main configuration (φ_ref 0.0303 rad, model error 0.1 ε, drift 3°, window 2–3 cycles), cap 1.14 pu.

- **δ* = 1.12 pu at 225°**, with a 10 % margin. With the bare DFT reference no δ up to 1.05 pu separated at ρ = 0.1.
- The separating window is 223–230°. Dense-tier separation at factors 1.0, 1.1 and 1.25 holds. Adversarial
  containment finds nothing outside, and Calafiore–Campi coverage is ≥ 92 %.
- The continuous check finds 0 of 486 cases unseparated inside the design ranges. 30 of 198 outside them are
  unseparated: L1 A-G 5–10 %, L2 ab 80–95 %, L2 A-G 90–95 %. Step 3 reports faults inside and outside the design
  ranges separately.
- **Cost:** the inverter keeps 0.08–0.14 pu of I1, against 0.14–0.78 pu asked. About **93 % of its rating** goes to δ.
- The binding witness gap (L1 15 % A-G, full R_f) is **2.210 ε against 2.20 ε** needed, a design margin of 0.01 ε.
  The EMT number for it comes from the design-point batch (`frames_design_check.py … --tag pll`).
- The alternative with a 4 % margin (`--rho 0.04 --tag pll04`) is reported beside it.

**The design point in EMT** (`frames_design_check.py --mag 1.12 --rho 0.1 --edges 223 230 --tang-hz 15 --tag pll`,
117 PSCAD runs, all with the filtered reference). Results are in `results/network/frames_design_check_pll.json`
(plain DFT) and `frames_design_check_pll_mimic.json` (D1's chain, mimic filter on the currents). Faults are judged
on windows ending 2.0–3.0 cycles after each run's own inception.

| group | runs | outside own set, plain DFT | **outside own set, with mimic** | clean distance to N, smallest (2.20 ε needed) |
|---|---|---|---|---|
| 14 binding cases at their witnesses | 14 | 0 | **0** | **2.41 ε** (design gap there 2.21 ε) |
| window edges 223° / 230° | 22 | 6, up to 0.029 ε | **0** | 2.40 ε |
| inception over one cycle | 11 | 3, up to 0.054 ε | **0** | 2.42 ε |
| all 48 cases, random source point | 48 | 27, up to **0.112 ε** | **0** | 2.45 ε |

| normal operation | runs | outside N (bare sets) |
|---|---|---|
| witness normals | 4 | 0.033 ε |
| 16 corners of the source box | 16 | 0.036 ε |
| balanced load step at bus S | 1 | **0.95 ε** |
| single-phase load at bus S | 1 | 0.43 ε |

- **With D1's chain (mimic filter) the design point holds in EMT everywhere it was checked.** Across all 95 fault runs
  (witnesses, window edges, random inception, every case) no point leaves its own bare set, and every fault stays at
  least 2.40 ε from N against the 2.20 ε the 10 % margin needs. The model-error box is not used.
- **Without the mimic filter the plain DFT exceeds the box** (0.112 ε on L2 ab 25 %, at the 2.0-cycle window). The
  filter is part of the design, not an option.
- **The window can start earlier with the filter.** Over the 95 runs with random inception, every point is inside its
  own set from 1.875 cycles, and inside the 0.1 ε box from 1.5 cycles (`results/network/frames_mimic_check_pll.json`).
  The guarantee is stated for 2–3 cycles; 1.875 cycles is measured, not designed.
- **The filtered inverter settles through the fault.** After 3 cycles the largest excursion is 0.04 ε (plain DFT), 0
  with the filter.
- **The balanced load step is 0.95 ε outside N, close to D1's alarm threshold of ε.** By the decision of 17 Oct
  (loads fixed) this is a designed-in false-alarm source, reported in its own row in step 3.

## What it means and does not

- It is a static-model result on one three-bus network with the design's ε, for detection, not zone discrimination.
- It strengthens the deck's own question, *where does a designed signal earn its cost?* Here the cost of a guarantee
  is the inverter's output. The step-3 detectors will show what a statistical criterion needs instead (docs/STEP3.md).
- The EMT checks of the frame model, and the relay's memory freeze across the fault windows, wait for PSCAD.
