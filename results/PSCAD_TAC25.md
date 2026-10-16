# The TAC25 design (current limit inside) in EMT, and an error it exposed in the design code

16 Oct 2026. Follows [PSCAD_DELTA_SWEEP.md](PSCAD_DELTA_SWEEP.md), which found that a design ignoring the
inverter's current limit promises a normal set the limited inverter cannot produce. Here the reviewed
design with the limit **inside** the problem (`src/review/tac25_design.py`, rule "phase") is tested the
same way. Code: `src/pscad_tac25_design.py`, `src/pscad_tac25_sweep.py`; runs with `src/pscad_twobus_fast.py`.
Numbers: `results/pscad/tac25_design.json`, `tac25_sweep.json`. 124 PSCAD runs.

## First: an error in the design code

Building the worst-case realisations exposed a sign error in `tac25_design.limit_rows` / `phase_rows`.
`ModelSet.pair` stacks `[G_N, G_F]` against `c_F − c_N`, so where the two sets meet the fault-side
realisation is `c_F − G_F u_F`: the fault block's variable is **−u_F**. The limit rows treated it as
+u_F, so on the fault side the current limit was applied to the **mirror image** of the realisation.
Without a limit this is harmless (the box is symmetric); with the limit inside it is not. Fixed, with a
regression test (`tests/test_tac25.py::test_limit_rows_follow_the_pair_sign_convention`); every result
built on those rows was re-run. What changed is in [DESIGN.md](DESIGN.md) and REVIEW.md §7 row 49. In short:
**putting the limit inside the problem does not halve δ.** On the toy presets it changes δ little or
makes the design infeasible.

## The design, on the PSCAD circuit

Two-bus `weak_sg` circuit as built in PSCAD ([PSCAD_TWOBUS.md](PSCAD_TWOBUS.md)); the design model is
the reviewed one: sound outer source set (H6), margin ρ = 0.1 (H14), per-phase limit rule at 1.2 pu.

| | δ |
|---|---|
| limit outside, no margin ([PSCAD_DELTA_SWEEP.md](PSCAD_DELTA_SWEEP.md)) | 0.18 pu |
| limit outside, ρ = 0.1 | 0.34 pu |
| **TAC25, limit inside, no margin** | **0.24 pu** at 320° |
| **TAC25, limit inside, ρ = 0.1** | **0.38 pu** at 325° (the design tested) |

(With the sign error the same design read 0.10 and 0.18 pu.) The outer source set is larger than the
linearised one, so δ = 0 leaves 3 cases unseparated here (A-G at 55, 75, 95 %, 40 Ω) instead of 2.

The "phase" rule means: while δ is injected, only positive-sequence currents whose three phase currents
fit under 1.2 pu occur. That describes an inverter that **keeps δ and cuts I1**. The EMT inverter now has
that limiter as an option (LIM = 1; [PSCAD_INVERTER.md](PSCAD_INVERTER.md)); the old one (LIM = 0)
scales I1 and δ together. A Python copy of the limiter matches the EMT one to 1e-4 pu.

## Checks

124 runs without PSCAD errors and with fresh output; the fault visible at the relay in every fault run;
|EMT − design model| at most 0.010 pu (median 0.00003); no phase current above 1.2 pu.

## Results

Reference: the design's own normal set (outer source set restricted by the limit rule at the design δ).
Ratio = noise box, in units of ε, needed to put the relay measurement inside it; a fault is separated
above 2, with the margin above 2.2; a normal measurement should be inside (ratio ~0).

| Test | Result |
|---|---|
| 30 cases at their worst realisation, δ = 0 | 3 not separated, exactly the 3 the design names |
| 30 cases at their worst realisation, TAC25 δ | **30 / 30 separated, all with the margin** (smallest 2.26; design model 2.20) |
| the two hard cases at all 16 box corners, LIM 1 | **32 / 32 separated** (smallest 2.26), including the 16 where the limiter cut I1 |
| normal operation, 16 corners, **LIM 1** | **0 / 16 outside the normal set** (largest ratio 0.03), limiter active at 8 |
| normal operation, 16 corners, LIM 0 | 8 / 16 outside (ratio up to 0.82): δ itself cut, the set no longer describes it |

**With the limiter the design assumes, the TAC25 design holds in EMT**: every fault separated with its
margin, and normal operation never leaves the normal set, also where the limiter acts. Where the
limiter cuts δ instead, the normal set is wrong again, as in the earlier sweep.

## Two conditions the design does not state

1. **Which limiter.** The guarantee holds for a δ-priority limiter. For one that scales both sequences,
   the same δ produces false-alarm exposure at the box corners where the current is high. A design
   should name the limiter it assumes, or carry the limiter type in the uncertainty set (PLAN step 1,
   open item 2).
2. **The angle reference of δ.** The inverter injects δ at an angle relative to its own V1. When the
   limiter cuts I1, V1 at the inverter moves, and δ turned by 8–14° in absolute terms. **And when the fault
   starts V1 moves again**: δ and I1 turn by −10° to +15° (median 6°) in the fault runs (review/NETWORK_REVIEW.md
   finding 3), so those runs start at the design's worst realisation but sit at another one during the fault;
   the separation measured is that of the EMT system, not a case-by-case check of the design's fault set. In a first pass
   the inverter's angle setting was computed from the unlimited request: normal operation then left the
   normal set at the 8 limited corners (ratio up to 0.80) even with LIM 1. Setting the angle for the
   current actually delivered removes it. A real inverter cannot do that by itself, so the design must
   either model δ in the inverter's own V1 frame or the inverter must hold δ in a stable reference.

## Limits

One two-bus circuit, A-G and the phase-phase case, worst realisations plus box corners; averaged
grid-following inverter at fixed frequency; one-cycle phasors, ideal instruments; the "relay" is the
design's set test, not a protection algorithm (step 3 of the plan).
