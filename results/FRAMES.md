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

## What it means and does not

- It is a static-model result on one three-bus network with the design's ε, for detection, not zone discrimination.
- It strengthens the deck's own question, *where does a designed signal earn its cost?* Here the cost of a guarantee
  is the inverter's output. The step-3 detectors will show what a statistical criterion needs instead (docs/STEP3.md).
- The EMT checks of the frame model, and the relay's memory freeze across the fault windows, wait for PSCAD.
