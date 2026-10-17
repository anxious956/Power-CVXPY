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
  - D0, 50N/50Q;
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
| hard A-G (8) | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / .88 / 1 / 1 / 1 | 1 / .62 / 1 / 1 / 1 |
| hard B-C (2) | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 0 / 1 / 1 / 1 | 1 / 0 / 1 / 1 / 1 | 1 / 0 / 1 / 1 / 1 |
| uniform (4) | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / .75 / 1 / 1 / 1 | 1 / .25 / 1 / 1 / 1 |
| outside the ranges (2) | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | 1 / .5 / 1 / 1 / 1 | 1 / 0 / 1 / 1 / 1 |
| normal (2) | 0 / 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 |
| load step (1) | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / **1** | … / **1** | … / **1** | … / **1** |
| single-phase load (1) | 0 / 0 / 0 / 0 / **1** | … / **1** | … / **1** | … / **1** | … / **1** |

With noise at the design's own scale (σ = 0.02 pu, so k·σ fills the ε box), D1, D0, D2g and D2p give the same
table. Random noise, even ε-sized, rarely points the worst way.

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
   already sees every hard A-G fault at δ = 0: 3|I0| = 0.47–0.93 pu against a 0.16 pu pickup. So do the
   multiple-model test and the CNN. STEP3.md foresaw this: "if D0 already detects the hard cases at δ = 0, that is
   the result". The "shrinking δ until each fails" curves are flat at 1 for every detector except D0.
2. **What the signal buys is the worst case.** It turns 25 % of the hard A-G faults guaranteed into 100 % by ¾ δ*,
   against any noise inside the ε box. The design does what it says, but its value is a guarantee against
   worst-case noise, not a higher detection rate under the noise a relay meets.
3. **The signal hurts the conventional element.** The injected negative-sequence current raises 50Q's
   normal-operation level, so its calibrated pickup rises with δ (0.16 pu at δ = 0, 0.90 pu at δ*). D0 loses the
   B-C faults from ½ δ* and most of the rest by δ*.
4. **The CNN false-alarms on the confusers once δ > 0.** It alarms on both confusers at every δ > 0, and on the
   single-phase load already at δ = 0. With 20 scenarios this says nothing about a properly trained CNN, only that
   confusers must be in its training data.
5. The cost stays what the design said: about 93 % of the inverter's rating at δ*.

All of this is EMT with δ injected, on one three-bus network, for task T1 (any fault vs no fault), with 20
scenarios. It is a pilot: rates come from 2–8 runs per cell.

## What could make the experiment informative

Not started; the choice belongs with the project (docs/STEP3.md, "no sweep until all six hold"):

- **(A) Report the worst-case curve as the step-3 result.** Densify the guaranteed-fraction curve on clean runs
  (cheap, no noise draws) with binomial bounds. Report alongside it that the statistical detectors do not need the
  signal here.
- **(B) Adversarial noise for every detector.** Put the noise D1 fears most (the ε-box perturbation towards N) on
  every detector's input. This asks whether D2 and D3 also fail where D1's guarantee says the signal is needed.
  Offline, no new runs.
- **(C) A harder fault set.** Use higher fault resistance (e.g. 40–200 Ω, where 50N weakens) or task T2 (L1 vs
  L2). Both need a new design: the design's set stops at 40 Ω and is for detection, not zone discrimination.
