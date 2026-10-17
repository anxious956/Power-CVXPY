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

| \|δ\| | fault points outside their own set | largest \|EMT − settled model\| | EMT settles |
|---|---|---|---|
| 0.90 pu | 12 of 240, at most **0.073 ε** | 0.40 ε | all 48 cases |
| 1.00 pu | 0 of 120 | 0.47 ε | all 24 ab cases |
| 1.05 pu | 0 of 120 | 0.54 ε | all 24 ab cases |
| 1.14 pu | 90 of 240, up to **18.7 ε** | 18.9 ε | **not on 7 bolted ab faults** |

- **At 1.14 pu the inverter does not settle on bolted phase-to-phase faults.** The δ-priority limiter cuts I1 to
  0.06 pu. The inverter's angle, from its one-cycle DFT of V1, keeps turning through the fault: δ turns 80° in three
  cycles, and the relay current reaches 3 pu against 1.4 pu at 0.9 pu. The static fixed point exists, is unique and
  has a small angle gain (≈ 0.25). The failure is dynamic. Neither the loop gain nor the inverter's own share of its
  bus voltage predicts it across δ levels. The mechanism is not identified.
- **The model error the sets need is small where the inverter settles.** Measured as the distance to the set, not
  to the settled point, it is at most 0.073 ε: the frame symbols (λ, drift) already cover the turn through the window.
  The earlier box of 0.25 ε (the distance to the settled point, `frames_main_err025.json`) double-counted it.
- **The design with measured budgets.** Main configuration: φ_ref 0.0303 rad, model error 0.1 ε, drift 3°,
  window 2–3 cycles. |δ| is capped at 1.05 pu, the largest level verified in EMT. Results:
  - At ρ = 0.1, no δ up to 1.05 pu separates.
  - At 1.05 pu, 225° every case separates for ρ up to 0.05; the binding case is L1 15 % A-G at full R_f.
  - Between 60° and 165° at 1.05 pu the inverter has no settled state in the static model.
  - Per angle at 1.05 pu (cases unseparated at ρ = 0): 210–225° none; 195° 5; 240° 5; 270° 20.
  - The design point for step 3 is **δ = 1.05 pu at 225°, ρ = 0.04**, 87.5 % of the inverter's rating. Its
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
window and with a 5 % margin at most. The 1.05 pu cap is verified at 225° only.

## What it means and does not

- It is a static-model result on one three-bus network with the design's ε, for detection, not zone discrimination.
- It strengthens the deck's own question, *where does a designed signal earn its cost?* Here the cost of a guarantee
  is the inverter's output. The step-3 detectors will show what a statistical criterion needs instead (docs/STEP3.md).
- The EMT checks of the frame model, and the relay's memory freeze across the fault windows, wait for PSCAD.
