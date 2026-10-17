# Step-3 pilot: on this network the signal buys a worst-case guarantee, not detection

17 Oct 2026. Step 3 of the deck: *detection under load and noise, shrinking δ until each detector fails*
([docs/STEP3.md](../docs/STEP3.md)). This is the pilot whose go / no-go was written before it ran.

- Runs: 100 PSCAD runs (`src/step3_data.py pilot`). 20 scenarios, each at δ = 0, ¼, ½, ¾ and 1 × the design δ
  (1.12 pu at 225°, ρ = 0.1). All runs use the PLL-like reference filter.
- Evaluation: `src/step3_pilot.py`, with numbers in `results/step3/pilot_eval.json`. Every detector reads the same
  front end (`src/step3_frontend.py`): instrument errors on the samples, a mimic filter on the currents, a
  superimposed-current starter, and the relay's 3-cycle memory frame.
- Detectors (`src/step3_detectors.py`):
  - D1, the set test;
  - D0, incremental 50N/50Q against the pre-fault memory;
  - D2, the multiple-model test, with the Gaussian update (D2g) and the Pirani eq. (14) update (D2p);
  - D3, the sequence-trajectory CNN, trained by grouped 5-fold over scenarios.

  All calibrated detectors use the largest score on pre-fault windows. D1's threshold is the design's (distance > ε).

## Go / no-go

| criterion | result |
|---|---|
| (a) static model before the fault ≤ 0.005 pu | **pass**: largest 0.0032 pu |
| (b) the hard stratum is hard at δ = 0 (D1 and D0 miss ≥ ¼) | **fail**: every detector detects every hard fault at δ = 0 |
| (c) at δ*, clean: D1 detects every in-range fault, no normal alarm | **pass**: 14 / 14, smallest score 2.77 ε; 0 / 2 normal alarms |
| (d) all detectors end to end | **pass** |
| (e) the design tier fits the ε box at k = 4 after the mimic filter | **pass**: currents 0.053 pu, voltages 0.029 pu, against 0.08 |
| (f) the fingerprint covers what varies | **pass** |

By the rule written before the run, **no sweep**: (b) fails.

## What the pilot shows

**Alarm rate with realistic noise (design tier), true trigger.** In each cell the five numbers are D1 / D0 / D2g /
D2p / D3.

| stratum | δ = 0 | ¼ δ* | ½ δ* | ¾ δ* | δ* |
|---|---|---|---|---|---|
| hard A-G (8) | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 |
| hard B-C (2) | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 |
| uniform (4) | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 |
| outside the ranges (2) | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 |
| normal (2) | 0 / 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 |
| load step (1) | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / **1** | … / **1** | … / **1** | … / **1** |
| single-phase load (1) | 0 / 0 / 0 / 0 / **1** | … / **1** | … / **1** | … / **1** | … / **1** |

With noise at the design's own scale (σ = 0.02 pu, so k·σ fills the ε box), D1, D2g and D2p give the same table.
D0 drops to 1 of 2 B-C faults at ¾ δ* and δ*. Random noise, even ε-sized, rarely points the worst way.

**D1's worst case.** A fault whose clean distance to N exceeds 2ε is detected under *any* noise inside the ε box.
This is the design's guarantee. Fraction of faults guaranteed:

| stratum | δ = 0 | ¼ δ* | ½ δ* | ¾ δ* | δ* |
|---|---|---|---|---|---|
| hard A-G | **0.25** | 0.88 | 0.88 | **1.00** | 1.00 |
| hard B-C | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| uniform | 0.75 | 0.75 | 1.00 | 1.00 | 1.00 |
| outside the ranges | 0.50 | 0.50 | 1.00 | 1.00 | 1.00 |

D1's clean score on the hard A-G faults rises from 1.3–2.6 ε at δ = 0 to 2.8–4.7 ε at δ*.

## Reading

1. **On this network, detection does not need the signal.** With realistic noise, the conventional 50N element
   already sees every hard A-G fault at δ = 0: 3|ΔI0| = 0.47–0.93 pu against a 0.16 pu pickup. So do the
   multiple-model test and the CNN. STEP3.md foresaw this: "if D0 already detects the hard cases at δ = 0, that is
   the result". The "shrinking δ until each fails" curves are flat at 1 for every detector except D0.
2. **What the signal buys is the worst case.** It turns 25 % of the hard A-G faults guaranteed into 100 % by ¾ δ*,
   against any noise inside the ε box. The design does what it says, but its value is a guarantee against
   worst-case noise, not a higher detection rate under the noise a relay meets.
3. ~~**The signal hurts the conventional element.**~~ **Withdrawn** (review/STEP3_PILOT_REVIEW.md; REVIEW.md §7
   row 52). The first D0 used total |I2|, whose pickup had to clear the designed δ's steady I2 (0.16 pu at δ = 0,
   0.90 pu at δ*). It lost B-C faults as δ grew. The standard incremental element (ΔI2, ΔI0 against the pre-fault
   memory) has a pickup of 0.162 pu at every δ level and detects every fault at every level.
4. **The CNN false-alarms on the confusers once δ > 0.** It alarms on both confusers at every δ > 0, and on the
   single-phase load already at δ = 0. With 20 scenarios this says nothing about a properly trained CNN, only that
   confusers must be in its training data.
5. The cost stays what the design said: about 93 % of the inverter's rating at δ*.

All of this is EMT with δ injected, on one three-bus network, for task T1 (any fault vs no fault), with 20
scenarios. It is a pilot: rates come from 2–8 runs per cell.

## The design at the front end's own noise bound

The design's ε (0.08 pu on every component) is not what the front end produces. Its k = 4 bound, on the pilot's
fault currents, is 0.053 pu on the currents and 0.029 pu on the voltages (criterion (e)). The frame model was
re-run with that bound per component, keeping the main configuration otherwise (`results/network/frames_measured_eps.json`):

| noise bound | cases unseparated at δ = 0, ρ = 0 | ρ = 0.1 | δ*, ρ = 0.1 | inverter current left |
|---|---|---|---|---|
| design ε, 0.08 pu | 13 | 14 | **1.12 pu** at 225° | 0.08–0.14 pu (about 93 % of rating to δ) |
| front end, V 0.029 / I 0.053 pu | **0** | 1 (L2 50 % A-G, full R_f) | **0.04 pu** at 270° (window 270–310°) | 0.14–0.78 pu (essentially all of it) |

**At the noise bound the relay actually has, the design needs no signal without margin, and 0.04 pu, 3 % of the
inverter's rating, with a 10 % margin.** The 1.12 pu design is the price of ε = 0.08 pu, about 1.5 times the front
end's current error and 2.8 times its voltage error. The signal's size is set by the noise bound assumed, not by the
faults.

## What could make the experiment informative

Not started; the choice belongs with the project (docs/STEP3.md, "no sweep until all six hold"):

- **(A) Report the worst-case curve as the step-3 result.** Densify the guaranteed-fraction curve on clean runs
  (cheap, no noise draws) with binomial bounds. Report alongside it that the statistical detectors do not need the
  signal here.
- **(B) Adversarial noise for every detector**, as the review corrected it: each detector against its own worst case
  inside the same run-constant ε box (D0 analytic, D1 an LP, D2 projected gradient on P(normal), D3 projected
  gradient on its input). Giving everyone D1's worst case would be a transfer attack, favouring D2 and D3. "Shrink δ
  until each fails" then means: the smallest δ with no worst-case miss, per detector. Offline, no new runs.
- **(C) A harder fault set.** Use higher fault resistance (e.g. 40–200 Ω, where 50N weakens) or task T2 (L1 vs
  L2). Both need a new design: the design's set stops at 40 Ω and is for detection, not zone discrimination.
