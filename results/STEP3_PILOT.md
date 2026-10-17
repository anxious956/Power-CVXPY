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
| design tier, V 0.029 / I 0.053 pu | **0** | 1 (L2 50 % A-G, full R_f) | **0.04 pu** at 270° (window 270–310°) | 0.14–0.78 pu (essentially all of it) |

**At the design tier's noise bound, the design needs no signal without margin, and 0.04 pu (3 % of the inverter's
rating) with a 10 % margin.** The design tier is near-nominal instrument accuracy: CT ≤ 1 %, VT ≤ 0.5 %, 0.3°.
At the class tier (CT 5–10 %, VT 3–6 %, VT phase 2–4°) the bound exceeds ε (review/STEP3_WORSTCASE_REVIEW.md).
The 1.12 pu design is the price of ε = 0.08 pu, about 1.5 times the design tier's current error and 2.8 times its
voltage error. The signal's size is set by the noise bound assumed, not by the faults.

**δ*(ε)**, from `src/frames_eps_curve.py` (`results/network/frames_eps_curve.json`). Settings: ρ = 0.1, faults up to
40 Ω, cap 1.14 pu, main configuration otherwise. The noise bound applies to every real component; the two tiers are
per-component bounds.

| noise bound (pu) | 0.03 | **design tier** (V 0.029 / I 0.053) | 0.04 | 0.05 | 0.06 | **0.08 (the design)** | 0.10 | 0.12 | **class tier** (V 0.139 / I 0.168) |
|---|---|---|---|---|---|---|---|---|---|
| δ* (pu) | 0 | **0.04** | 0.10 | 0.34 | 0.58 | **1.12** | none ≤ 1.14 | none | **none ≤ 1.14** |
| cases unseparated at δ = 0 | 0 | 1 | 1 | 4 | 5 | 14 | 18 | 25 | 34 |
| share of the inverter's rating | 0 | 3 % | 9 % | 30 % | 51 % | 93 % | — | — | — |

- The signal grows steeply with the noise bound. Between 0.03 and 0.08 pu it goes from nothing to 93 % of the
  inverter.
- Above about 0.09 pu no admissible signal guarantees detection on this network, against a **box** bound.
- With near-nominal instruments (design tier) the guarantee is almost free.
- The class-tier box (0.139 / 0.168 pu) gives no δ within the cap, but it is the worst multiplicative term (10 % of
  a 1.28 pu fault current) applied to every component of every measurement, normal ones included. A multiplicative
  error is a generator proportional to y, so the right set is structured (review/STEP3_CLASS_REVIEW.md). On the
  two-bus model the structured set needed no signal where the box said infeasible (DESIGN.md §4.1.1).
  `src/frames_structured.py` (`results/network/frames_structured.json`) computes δ* with per-phase CT and VT ratio
  and phase errors as shared symbols of the frame model. The bounds are regime-dependent: normal operation and the
  memory CT 1 % / 1°, VT 3 % / 2°; fault windows CT 10 % / 1°, VT 6 % / 4°. Only the white noise (V 0.02 / I 0.04 pu)
  stays in the box.

  | instrument errors | ρ = 0 | ρ = 0.1 |
  |---|---|---|
  | class tier as a box (V 0.139 / I 0.168 pu) | none within the cap | none within the cap |
  | **class tier, structured, regime-dependent** | **1.08 pu** at 225° (I1 left 0.12–0.21 pu) | **1.12 pu** at 225° (I1 left 0.08–0.14 pu) |
  | design tier, structured | **0** | **0** |

  **At the class tier the guarantee is available, at the same price as the design** (1.12 pu, about 93 % of the
  inverter). The box was too pessimistic. The earlier line "with class-accuracy instruments no signal the inverter
  can deliver buys it" is withdrawn (REVIEW.md §7 row 53). With the structured set the design tier needs no signal
  even with a 10 % margin.

## Each detector against its own worst case (option B)

`src/step3_adversary.py` uses the pilot's clean measurements (100 runs) and writes
`results/step3/adversary_pilot.json`. The adversary adds noise inside the design's ε box (0.08 pu on every real
component, relay frame) in one of two ways:
- **per window**: every one-cycle measurement and the pre-fault memory get their own perturbation;
- **constant**: one perturbation for the whole run, the same on the memory and every window, i.e. a systematic
  instrument error.

Thresholds are worst-case too. A detector's threshold is the largest score its own adversary produces on the
calibration normals (pre-fault pseudo-triggers at the same δ level). D1 keeps the design's threshold. The worst
cases are:
- D1: exact (within 2ε of N in every window, or an LP for the constant adversary);
- D0: exact;
- D2 (Gaussian) and D3: projected sign-gradient search, 60 steps.

**Worst-case miss rate, per-window adversary.** Each cell lists D1 / D0 / D2 / D3.

| stratum | δ = 0 | ¼ δ* | ½ δ* | ¾ δ* | δ* |
|---|---|---|---|---|---|
| hard A-G (8) | **.75** / 1 / .88 / 1 | .12 / 1 / .75 / 1 | .12 / 1 / .62 / 1 | **0** / 1 / .25 / 1 | **0** / 1 / .12 / 1 |
| hard B-C (2) | 0 / 1 / 0 / 1 | 0 / 1 / .5 / 1 | 0 / 1 / 0 / 1 | 0 / 1 / 0 / 1 | 0 / 1 / 0 / 1 |
| uniform (4) | .25 / .5 / .25 / 1 | .25 / .5 / .25 / 1 | 0 / .75 / .25 / 1 | 0 / .75 / .25 / 1 | 0 / .75 / .25 / 1 |
| outside the ranges (2) | .5 / .5 / .5 / 1 | .5 / .5 / .5 / 1 | 0 / .5 / .5 / 1 | 0 / .5 / .5 / 1 | 0 / 1 / .5 / 1 |

**Constant adversary.** D1 and D2 are unchanged. D0 misses nothing at any level, because a constant error cancels in
an increment. D3 misses 50–75 % at every level.

**Worst-case false alarms.** None of the four detectors alarms on the 2 normal runs (per δ level) under either
adversary. With so few normal runs, and thresholds from 20 operating points × 4 pre-fault windows, this favours D0,
D2 and D3 against D1, whose threshold covers all of N. The thresholds are being rebuilt on the 16 box corners plus
random interior normals. The alarms are all on the confusers:
- the single-phase load: D1, D0 and D2 at every level;
- the load step: D1 3 of 5, D2 1 of 5, D0 0 (per window) or 4 of 5 (constant).

**Reading.**
- **"Shrink δ until each fails", in Taylor's worst-case sense, has a clear answer on this pilot.**
  - D1, the design's own test, has no worst-case miss in the design's set from ¾ δ*. Below that it fails: 75 % of
    the hard A-G faults at δ = 0, 12 % at ¼ and ½ δ*.
  - D2 benefits from δ too (88 % → 12 % on hard A-G), but never reaches zero. Its misses at δ* are one hard, one
    uniform and one outside-the-ranges fault, and the hypothesis grid does not cover the last one. D2's and D3's
    misses are what a 60-step search from one start found: **lower bounds**. Restarts are to be added.
  - D0 and D3 fail at every δ against the per-window adversary. That adversary is a **stress bound**: every window
    and the memory get their own worst-case error, and for D0 the memory's error even differs per window (it is one
    measurement, so this slightly overstates D0's misses). δ does not help them: an incremental element cannot see
    a constant signal, and the CNN is not robust to small worst-case input changes.
- **Against an additive constant offset D0 is immune**, because the offset cancels in an increment. D1 still needs δ
  against it. Real systematic instrument errors are **multiplicative** (per-phase ratio and phase, constant over
  the run). They scale the increments, and at CT 10 % they shift D1's absolute measurement by about ε on fault
  currents. A multiplicative adversary within the class bounds, for all four detectors, comes next. Until it is in,
  option B is not a result to report.
- With realistic random noise all four detect everything at every δ (above). So the signal matters only for
  worst-case noise. At the design tier's noise bound the design needs almost none of it (δ* 0 or 0.04 pu).

These are 8 hard A-G scenarios. The dense batch (option A) gives the worst-case curve with binomial bounds.

### Multiplicative systematic errors, regime-dependent, with white noise

`src/step3_multiplicative.py`, `results/step3/multiplicative_pilot.json`. The errors are per-phase VT and CT ratio
and phase errors, constant over a run, in two independent regimes:
- normal operation and the memory: CT 1 % / 1°, VT 3 % / 2°;
- fault windows: CT 10 % / 1°, VT 6 % / 4°.

On top is the design tier's white noise, added to the samples (3 seeds). The search covers 289 parameter sets per run
(zero, 256 random corners of the 24-parameter box, 32 interior points) and takes the worst over sets and seeds: a
lower bound. Thresholds are worst-case over the 150 normal runs and the pre-fault windows. D0's threshold is now
0.126 pu at every level; with white noise it is no longer degenerate.

| | δ = 0 | ¼ δ* | ½ δ* | ¾ δ* | δ* |
|---|---|---|---|---|---|
| worst-case miss, every stratum (D1 / D0 / D2 / D3) | 0 / 0 / 0 / 0 (D3: 1 of 2 B-C) | 0 | 0 | 0 | 0 |
| D1 false alarms on the 30 normal runs | 0 | 0 | 0 | 0 | 0 |

**Realistic systematic instrument errors hide no pilot fault from any detector at any δ, and cause no false alarm.**
This matches the statistical result. Regime-dependent multiplicative errors are not where the signal matters on this
network; only a per-window additive worst case (the stress bound above) is.

### Multiplicative systematic errors: the stress case

This first version applied the fault-condition limits to every window and to the memory. That makes it a **stress
case**, not a finding (review/STEP3_CLASS_REVIEW.md). At load current a 5P CT stays within about ±1 % / ±60′ and a 3P
VT within ±3 % / ±120′. A 1 % CT error on the 0.867 pu steady I2 that δ* creates at the relay is 0.009 pu, well inside
ε. The regime-dependent version, with white noise on top, is `src/step3_multiplicative.py`.

`results/step3/multiplicative_pilot_stress_v1.json`. The adversary uses per-phase CT
ratio errors |r_I| ≤ 10 %, VT ratio errors ≤ 6 % and VT phase errors ≤ 4°, constant over the run. They apply to
every window and to the memory, so they scale the increments and turn the memory frame. There is no white noise on
top. The search covers 577 parameter sets: the 512 corners of the box, 64 random points and the zero-error point.
That is a lower bound on the worst case. Thresholds are the largest score under the same adversary over the 150
dense normal runs (16 box corners and 14 random points per level, forced trigger) and the pre-fault windows. D1 keeps
the design's threshold.

| | δ = 0 | ¼ δ* | ½ δ* | ¾ δ* | δ* |
|---|---|---|---|---|---|
| worst-case miss, hard A-G (D1 / D0 / D2 / D3) | .12 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 | 0 | 0 |
| D1's smallest distance on hard A-G, clean → worst error (ε) | 1.30 → 0.91 | 1.64 → 1.12 | 1.98 → 1.52 | 2.33 → 1.80 | 2.77 → 2.17 |
| **normal runs on which D1 can false-alarm** (of 30) | 0 | 0 | 0 | 0 | **24** |

- **A class-accuracy systematic error hides almost nothing.** It scales a fault's measurement by at most about 10 %.
  The one miss is D1 at δ = 0, on one hard A-G fault.
- **Stress case only: with fault-condition CT error in normal operation, the design's own signal becomes a
  false-alarm source.** At δ* the relay carries a steady |I2| of 0.867 pu (0.650 pu at ¾ δ*). 10 % of it,
  0.087 pu, exceeds ε, so D1 alarms on 24 of 30 normal runs. At ¾ δ* the error is 0.065 pu and D1 alarms on none.
  A CT within its rated-current accuracy (1 %) removes this.
- The incremental detectors' thresholds come out near 0 (D0 0.000–0.001 pu). In steady state a constant
  multiplicative error leaves an increment at zero. With no white noise in this adversary, D0's perfect record here
  says nothing about noise; the per-window additive bound above does.

**Restarts.** With 4 random starts added to D2's and D3's searches, and the 150 normal runs in the calibration, the
additive tables above change only for D2. Its hard A-G misses at ½ / ¾ δ* rise to 0.75 / 0.62 (from 0.62 / 0.25),
and its B-C misses to 0.5 from ¼ to ¾ δ*. The searches find more with more starts, so D2's and D3's numbers remain
lower bounds.

## D1's worst-case curve with bounds (option A)

The dense batch has 350 clean PSCAD runs (`src/step3_data.py dense`): 70 new scenarios (40 hard A-G, 10 hard B-C,
20 uniform, all inside the design's ranges), each at the five δ levels, all with the filtered reference.
`src/step3_worstcase.py` computes, for each run, the fraction of faults D1 detects under any noise inside the ε box,
i.e. whose clean distance to N exceeds 2ε in every 2–3-cycle window. Bounds are Clopper–Pearson 95 %. Results are
in `results/step3/worstcase_dense.json`.

| stratum | n | δ = 0 | ¼ δ* | ½ δ* | ¾ δ* | δ* |
|---|---|---|---|---|---|---|
| hard A-G | 40 | **0.33** [0.19, 0.49] | 0.60 [0.43, 0.75] | 0.93 [0.80, 0.98] | **1.00** [0.91, 1.00] | 1.00 [0.91, 1.00] |
| hard B-C | 10 | 1.00 [0.69, 1.00] | 1.00 | 1.00 | 1.00 | 1.00 |
| uniform | 20 | 0.95 [0.75, 1.00] | 1.00 [0.83, 1.00] | 1.00 | 1.00 | 1.00 |
| all in range | 70 | 0.60 [0.48, 0.72] | 0.77 [0.66, 0.86] | 0.96 [0.88, 0.99] | **1.00** [0.95, 1.00] | 1.00 [0.95, 1.00] |

The smallest clean D1 distance on the hard A-G faults is 1.21 / 1.53 / 1.85 / 2.17 / 2.52 ε across the five levels.

**This is Taylor's guarantee, measured in EMT.**
- Without the signal, two thirds of the high-resistance A-G faults can be hidden by a noise the design admits.
- At ¾ δ* (0.84 pu) none of these 40 can be (95 % bound ≥ 0.91).
- EMT reaches the guarantee below the design's δ*: the design covers the extreme realisation pair of every case, and
  random realisations near the witnesses are not that extreme.

## A higher fault resistance (option C, static)

`src/frames_rf80.py`, `results/network/frames_rf80.json`. The design's grid has R_f up to 80 Ω (R_f / rF in
{0, 0.5, 1, 1.5, 2}), the main configuration otherwise, cap 1.14 pu.

| noise bound | margin | δ* | cases unseparated at δ = 0 | inverter current left |
|---|---|---|---|---|
| design tier, V 0.029 / I 0.053 pu | ρ = 0 | **0.94 pu** at 225° | 6 | 0.14–0.33 pu |
| design tier, V 0.029 / I 0.053 pu | ρ = 0.1 | **1.08 pu** at 30° | 9 | 0.12–0.21 pu |
| design ε, 0.08 pu | ρ = 0 | **none up to the 1.14 pu cap** | 36 | — |
| design ε, 0.08 pu | ρ = 0.1 | **none up to the cap** | 41 | — |

At 40 Ω and the same noise bound, δ* was 0. **At high fault resistance the guarantee needs the signal even at the
design tier's noise bound.** This is static only. It is "where the guarantee needs the signal", not yet "where
detection needs it". Before that claim, three things are needed:
- an EMT model-error check at 80 Ω;
- a pilot showing whether the statistical detectors also struggle there.

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
