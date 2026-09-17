# Machine learning against the zone-1 rule on real EMT data, set up fairly

> **Review correction (see [REVIEW.md](../REVIEW.md)).** The numbers below are affected by:
> - **Sibling leakage (H22).** Stratified folds put a phase-rotated or identical sibling of 95–96 % of test cases in training. Grouped folds lower relay B engineered + LR from 99.7 % to 95.3 % dependability.
> - **The rule's missing DC-offset filter and directional element (N2).** Relay B's "15 % false trips" at 20 ms fall to 0.7 % with a mimic filter. The rule trips 20–22 % of reverse faults at its own bus, which were never tested.
> - **Security on classes outside training (H24).** Unsupervised boosting trips 92 % of relay-bus reverse faults at relay B.
> - **Own line 85–100 % (H9)** was neither a class nor reported.
> - **Resampling look-ahead (H25/H30).** Models given only the 40 ms ending at inception reach AUC 0.86–0.97; the §3 control ended 5 ms early.
> - **ADC clipping.** The ±40 × pre-fault full scale clips 13 DoubleLine and 14 relay-A in-zone faults, all at 1 % and 20 % of the line, so rates at those locations are affected.
> - **Phasor reference rotation at 30/50 ms (N1).** Rule AUC at relay B, 50 ms: 0.806 → 0.891.
> - **Stage-1 label (H28).** With a responsibility-based label, AUC is 0.90–0.99, not 0.62–0.81.
> - **§3 fingerprint size (N5).** It is 0.1–0.26 V, not 0.01 V.
>
> Corrected tables: REVIEW.md §6 and §9.

17 Sep 2026. Code: `src/real_ml.py`. Run: `python src/real_ml.py` (about 65 min on a laptop CPU).
Numbers: [real_ml.json](real_ml.json). Figure: [real_ml.png](real_ml.png).
Data: EvEMTBench `benchmark-TestGrid110kV` (relays A and B) and `benchmark-DoubleLine`, see
[REAL_TESTGRID.md](REAL_TESTGRID.md) and [REAL_DOUBLELINE.md](REAL_DOUBLELINE.md).

This replaces the learned-detector part of REAL_TESTGRID.md and REAL_DOUBLELINE.md. Those runs
used 80 ms of post-fault data, per-channel standardisation, in-sample thresholds and
noise-free records. Section 3 shows why the last one alone invalidates their in-distribution
1.000 scores.

## 1. Question

A distance relay's zone 1 must trip for faults on its own line up to 85 % and must not trip
for faults beyond the remote bus. Given the same causal window a relay would have, does a
learned classifier make that decision better than the zone-1 reactance setting, and does it
keep doing so on a relay or grid it was not trained on?

## 2. Setup

| Item | Choice | Reason |
|---|---|---|
| In zone | own line at 1, 20, 50, 80 % | 180 cases per relay |
| Out of zone | lines leaving the remote bus at 1, 20 %, and the remote bus | 315 (A), 135 (B), 225 (DoubleLine) |
| Window | 40 ms before inception to decision time t | causal; pre-fault samples are in a relay's buffer |
| Decision time | 10, 20, 30, 40, 50 ms | as Oelhaf et al. 2026 |
| Rule | reactance of the faulted loop (phase selection, k0 compensation) against 85 % of line reactance, phasors from the last full cycle before t | fixed setting, nothing fitted; needs t ≥ 20 ms |
| Input scaling | V / nominal peak; I × (reach impedance / nominal peak), so V/I is in units of the relay's own reach | keeps the V/I ratio distance protection relies on, and is comparable across relays |
| Measurement chain | white noise σ = 0.1 % of nominal, 16-bit ADC (±2 pu V, ±40 × pre-fault peak I) | see section 3 |
| Models | MLP (100 hidden units), histogram gradient boosting, random forest (100 trees), engineered relay features + logistic regression | Oelhaf et al. 2026: MLP best at every window, boosting weak at 10 ms; forest as the tree ensemble; engineered features as the domain model |
| Class balance | class_weight (forest, LR); minority oversampling (MLP, boosting) | class_weight is ~70× slower in HistGradientBoosting (scikit-learn 1.9) |
| Validation within a relay | stratified 5-fold × 2 repeats | |
| Across relays | train on all cases of one relay, test on another | cannot be faked by a split |
| Operating point | threshold at 5 % false trip on **out-of-fold** training scores | see section 4 |

## 3. The benchmark records leak the label without noise

Control: predict in zone vs out of zone from a pre-fault window only (45 to 5 ms before
inception). The fault has not happened, so the answer must be 0.5.

| Pre-fault window only, ROC AUC | MLP | Gradient boosting | Random forest |
|---|---|---|---|
| Noise-free records, relay A | 0.44 | **1.00** | **1.00** |
| Noise-free records, relay B | 0.47 | **1.00** | **1.00** |
| Noise-free, forest, window ending 40 ms before inception, relay A | | | **1.00** |
| With the measurement chain, relay A | 0.498 | 0.480 | 0.508 |
| With the measurement chain, relay B | 0.493 | 0.545 | 0.518 |

Cause: every simulation of a given event configuration starts from a pre-fault waveform
that differs from the others by about 1e-7 pu (0.01 V at 110 kV), present at least 100 ms
before inception. Tree models split on these differences. A physical relay cannot see them:
instrument transformer error and ADC resolution are orders of magnitude larger. It is not
our resampling; the resampling pre-ringing is confined to the last ~1 ms before inception
(2e-3 pu there, 1e-7 pu elsewhere).

Consequence: **any tree model trained on noise-free EvEMTBench waveforms can reach a
perfect in-distribution score without learning protection.** Our earlier 1.000 results are
withdrawn. This is worth reporting to the dataset authors.

## 4. Thresholds must come from held-out scores

The first version set each model's threshold from its in-sample training scores. The forest
and boosting fit training data perfectly, so the threshold landed far too low: within
relay B they tripped for 81 to 84 % of out-of-zone faults at a nominal 5 %. With
out-of-fold thresholds the same models trip for 2 to 4 %. AUC is unaffected. All numbers
below use out-of-fold thresholds.

## 5. Results

### Within a relay (trained and tested on the same relay)

ROC AUC, mean ± sd over 10 folds. The rule has no fitted parameters, so no spread.

| Relay, t | Rule | MLP | Gradient boosting | Random forest | Engineered + LR |
|---|---|---|---|---|---|
| A, 10 ms | n/a | 0.894 ± 0.086 | 0.996 ± 0.003 | 0.981 ± 0.016 | 0.977 ± 0.016 |
| A, 20 ms | 0.943 | 0.924 ± 0.054 | 0.997 ± 0.004 | 0.988 ± 0.008 | 1.000 ± 0.000 |
| A, 50 ms | 0.948 | 0.955 ± 0.060 | 0.998 ± 0.003 | 0.993 ± 0.008 | 0.995 ± 0.003 |
| B, 10 ms | n/a | 0.784 ± 0.031 | 0.969 ± 0.011 | 0.939 ± 0.019 | 0.895 ± 0.033 |
| B, 20 ms | 0.830 | 0.802 ± 0.064 | 0.964 ± 0.018 | 0.958 ± 0.017 | 0.999 ± 0.001 |
| B, 50 ms | 0.806 | 0.844 ± 0.097 | 0.973 ± 0.015 | 0.971 ± 0.016 | 0.976 ± 0.013 |

Operating point at 20 ms, dependability / false trip:

| | Rule (fixed setting) | MLP | Gradient boosting | Random forest | Engineered + LR |
|---|---|---|---|---|---|
| Relay A | 79 % / 0 % | 65 % / 1 % | 97 % / 2 % | 92 % / 2 % | 100 % / 4 % |
| Relay B | 61 % / **15 %** | 34 % / 3 % | 78 % / 4 % | 78 % / 2 % | 100 % / 4 % |

Within a relay, learned models beat the fixed setting, and at relay B, the remote-infeed
case, by a wide margin. This is a fair comparison of information but not of effort: each
model's threshold is tuned on the relay's own faults, the rule's is not.

The MLP is the weakest learned model here, unlike in Oelhaf et al. Their task (fault type,
eight relays concatenated, thousands of cases) is not ours (zone, one relay, 495 or 315
cases). We read this as the sample size, not as evidence against their result.

### On a relay or grid the model never saw

ROC AUC:

| Train → test, t | Rule on the test relay | MLP | Gradient boosting | Random forest | Engineered + LR |
|---|---|---|---|---|---|
| A → B, 20 ms | 0.830 | 0.841 | 0.789 | 0.835 | 0.911 |
| A → B, 50 ms | 0.806 | 0.852 | 0.757 | 0.773 | 0.718 |
| B → A, 20 ms | 0.943 | 0.905 | 0.590 | 0.724 | 0.992 |
| B → A, 50 ms | 0.948 | 0.955 | 0.648 | 0.741 | 0.961 |
| A → DoubleLine, 20 ms | 0.933 | 0.970 | 0.944 | 0.958 | 1.000 |
| A → DoubleLine, 50 ms | 0.920 | 0.954 | 0.948 | 0.980 | 0.957 |

Dependability / false trip at 20 ms, threshold carried over from the training relay:

| Train → test | Rule | MLP | Gradient boosting | Random forest | Engineered + LR |
|---|---|---|---|---|---|
| A → B | 61 % / 15 % | 85 % / **39 %** | 97 % / **87 %** | 100 % / **100 %** | 83 % / 13 % |
| B → A | 79 % / 0 % | 77 % / 13 % | 100 % / **100 %** | 100 % / **100 %** | 100 % / **27 %** |
| A → DoubleLine | 80 % / 0 % | 97 % / **25 %** | 97 % / **47 %** | 100 % / **100 %** | 100 % / **97 %** |

Two findings:

1. **Ranking partly transfers, trip thresholds do not.** The MLP and the engineered model
   keep AUC close to or above the rule on unseen relays. But the threshold learned on one
   relay is wrong on another: false trips of 13 to 100 %. The rule's setting is defined in
   units of its own line (85 % of reactance), so it transfers by construction.
2. **Tree ensembles transfer worst.** Boosting falls to 0.59 to 0.79 AUC between the two
   TestGrid relays and the forest trips for every out-of-zone fault. With the physical
   scaling, V/I ratios are comparable across relays, but raw sample values are not
   (different load flow, phase angle, source strength), and axis-aligned splits on raw
   samples depend on exactly those.

### Two stages at 20 ms: fault detector, then zone

Stage 1 (MLP) is trained on fault and switching episodes plus a pre-fault window of each.
Its threshold is 5 % false alarm on out-of-fold scores of the 40 training switching events.
Stage 2 (MLP) is the zone decision. Episode-stratified 5-fold.

| Relay | Stage 1 AUC, fault vs switching | In-zone faults tripped | Out of zone tripped | Switching tripped | Stage 1 passes in zone | Stage 2 passes in zone |
|---|---|---|---|---|---|---|
| A | 0.813 ± 0.028 | 47.0 ± 16.3 % | 2.6 % | 0 % | 56 % | 65 % |
| B | 0.623 ± 0.172 | 10.5 ± 7.8 % | 1.7 % | 0 % | 18 % | 18 % |

A learned fault detector does not separate faults from switching events at 20 ms on this
data, and the chain is secure only by being undependable. 50 switching events per grid (10
per test fold) make every rate here coarse: 0 % means 0 of 10.

## 6. What we conclude, and what we do not

- A learned zone decision can outperform a fixed zone-1 setting **on the relay it was tuned
  on**, most clearly under remote infeed (relay B). That is a real, positive result, and
  the case for data-driven settings, not data-driven relays.
- It does **not** carry to another relay without retuning its threshold. The failure is in
  calibration more than in ranking.
- We do **not** claim ML is worse than protection logic in general. One grid family, two
  relays, a few hundred cases, one noise level, grid-following inverters at 0.1 % of short-
  circuit capacity.
- For the project: the useful role for learning here is setting or adapting a relay's
  characteristic from data, with the physics defining the units. That is close to Taylor's
  framing, where the bounded uncertainty sets define what the characteristic must cover.

## 7. Errors found and fixed during this experiment

| # | Error | Symptom | Fix |
|---|---|---|---|
| 1 | StandardScaler per sample position | cross-relay MLP and boosting output a constant, AUC exactly 0.500; relay B inputs at median 76,821 σ in A's scaler | one scale per channel (ChannelScaler) |
| 2 | MLP probabilities saturate at 1.0 | stage-1 threshold = 1.0000, 0 % of faults passed | rank on logits |
| 3 | class_weight in HistGradientBoosting | 96 s instead of 1.4 s per fit; run projected at over 3 h | oversampling instead |
| 4 | Noise-free benchmark records | trees predict the label from pre-fault samples, AUC 1.000 | measurement chain; shortcut control run every time |
| 5 | In-sample thresholds | forest and boosting false trips 81 to 84 % at nominal 5 % | out-of-fold thresholds |

## 8. Limitations and open questions for reviewers

- **Noise level.** 0.1 % white noise and 16 bits is a plausible front end but one point. How
  results move with noise, CT saturation and anti-aliasing filters is not tested.
- **Resampling look-ahead.** 9600 → 6400 Hz polyphase resampling is non-causal; about 1 ms
  of the transient leaks backwards. Every detector gets it, rule included.
- **Rule vs tuned models.** The rule's threshold is a fixed setting; the models' are tuned
  per relay. A rule with a data-tuned reach would be the stricter baseline.
- **Sample size.** 315 to 495 zone cases per relay; the MLP in particular is data-limited.
- **Switching events.** 50 per grid, 40 per training fold. The 5 % stage-1 threshold rests
  on two events.
- **Fixed grid parameters.** Every simulation of a benchmark grid has the same loading and
  source strength; real variation would widen every distribution.
- **No inverter-dominated case.** See REAL_TESTGRID.md; this needs our own simulation.
- Questions: Is a per-relay threshold a fair deployment assumption for a learned zone
  element? Would reach-normalised impedance trajectories, rather than raw samples, be the
  right input for transfer? What noise model would a protection engineer consider realistic
  for 110 kV CVT and CT channels?
