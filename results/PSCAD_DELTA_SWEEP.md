# The designed signal in EMT, all cases: separation holds, the current limit breaks the normal set

16 Oct 2026. Extends [PSCAD_DELTA_TEST.md](PSCAD_DELTA_TEST.md) (two cases, one realisation each) to every
fault case, every corner of the uncertainty box, and a design with a margin. 124 PSCAD runs.
Code: `src/pscad_delta_design.py` (design and run list), `src/pscad_twobus_fast.py` (runs),
`src/pscad_delta_sweep.py` (analysis). Numbers: `results/pscad/delta_design.json`, `delta_sweep.json`.

## Set-up

The design tool's two-bus `weak_sg` circuit built in PSCAD ([PSCAD_TWOBUS.md](PSCAD_TWOBUS.md)): weak
source behind the relay, the averaged inverter at the far bus ([PSCAD_INVERTER.md](PSCAD_INVERTER.md)),
uncertainty box source EMF ±5 % and ±5°, inverter current ±0.3 pu in magnitude and angle, noise box
ε = 0.08 per component. 30 fault cases: A-G and the phase-phase case, five locations, three
resistances (0, 20, 40 Ω).

| Design | δ | Model's verdict |
|---|---|---|
| none | 0 | 2 of 30 cases not separable (A-G at 75 % and 95 %, 40 Ω) |
| smallest separating | 0.18 pu at 330° | 30 of 30 |
| with a 10 % margin (noise box × 1.1) | **0.34 pu** at 330° | 30 of 30, each with the margin |

The design ignores the inverter's current limit. At 8 of the 16 corners the inverter already delivers
about 1.2 pu, so 0.18 or 0.34 pu more does not fit; the EMT inverter's 1.2 pu phase-peak limiter then
scales I1 and δ down together (δ of 0.34 became 0.26).

## Checks before reading the results

All 124 runs: PSCAD without errors and with fresh output (old output deleted before each run); the fault
visible at the relay in every fault run; |EMT − design model| at the relay at most **0.010 pu** (median
0.00003 pu; the largest on bolted faults, from the decaying DC); limiter activity recorded per run (32).
The fast runner was checked against freshly built projects on two runs: identical output.

## Results

Ratio = the noise box, in units of ε, that would put the relay measurement inside the normal set N(δ).
A fault is separated if the ratio exceeds 2; a normal measurement should sit inside N (ratio 0).

**Fault separation holds everywhere it was tested.**

| Test | Result |
|---|---|
| each of the 30 cases at its worst realisation, δ = 0 | 2 not separated (A-G 75 %, 95 %, 40 Ω), as the model predicts |
| each of the 30 cases at its worst realisation, margin δ | **30 of 30 separated, all with the margin** (smallest 2.28) |
| the two hard cases at all 16 corners, margin δ | **32 of 32 separated** (smallest 2.28), including the 16 runs where the limiter cut δ |

**Normal operation leaves the normal set where the limiter acts.**

| δ | Corners outside N | Largest ratio | Noise needed for a false alarm (was ε) |
|---|---|---|---|
| 0.18 (no margin) | 8 of 16, exactly the limited ones | 0.28 | 0.72 ε |
| 0.34 (margin) | 8 of 16, exactly the limited ones | 0.78 | 0.22 ε |

At the eight corners where the inverter cannot deliver the full δ, the normal-operation measurement sits
outside the design's normal set, because that set assumes the full δ is injected. The relay's rule
(alarm when the measurement leaves N plus the noise box) can then fire on normal operation for noise
smaller than the box. The bigger the δ, the worse: **the margin that makes fault separation robust makes
false alarms more likely.**

## What it means

1. **The method's separation survives EMT** on this circuit, for every case and every corner tested,
   with the signal actually injected and limited by a real limiter.
2. **The design must contain the current limit.** A design that ignores it promises a normal set the
   inverter cannot produce. This is the review's correction H5 (REVIEW.md; [DESIGN.md](DESIGN.md)),
   now seen in EMT rather than argued from the model. The TAC25 formulation in the repository puts the
   limit inside the problem; testing that design the same way is the next step.
3. **A margin is not free.** It doubled δ (0.18 → 0.34 pu) and, with the limit outside the design,
   tripled the false-alarm exposure.

## Limits

- One circuit (two-bus, weak source), A-G and phase-phase faults, one line, the box corners plus each
  case's worst realisation, not the whole box.
- Averaged grid-following inverter, fixed frequency, no PLL dynamics; the inverter references δ to its
  own V1, the design assumes a fixed δ (the rotation was a few degrees here).
- Fundamental-frequency phasors over one cycle, ideal instruments; the "relay" is the design tool's set
  test, not a protection algorithm (that is step 3 of the plan).
