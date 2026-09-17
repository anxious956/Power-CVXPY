# First result on real EMT data: EvEMTBench `benchmark-DoubleLine`

> **Correction, 17 Sep 2026.** The learned-detector numbers below (engineered model, CNN) were obtained on noise-free records with 80 ms windows and in-sample thresholds. The noise-free records let models read the label from pre-fault samples, so the in-distribution 1.000 scores are not valid. The zone-1 setting results are unaffected. See [REAL_ML.md](REAL_ML.md).

17 Sep 2026. Code: `src/evemt.py` (loader), `src/real_zone.py` (experiment).
Run: `python src/real_zone.py "data/benchmark-DoubleLine (1)_cache.npz"`.

## What this dataset is, and what it is not

Read from the archive's own grid graph and labels, not assumed:

- 110 kV, **50 Hz**. Two 30 GVA external grids behind 500 MVA 380/110 kV transformers at buses 1 and 3, a 200 MW load at bus 2, and two double-circuit line pairs: 1-2A 20 km, 1-2B 25 km, 2-3A 30 km, 2-3B 40 km. Line type 110kV Danube Al/St 435/55, z₁ = 0.0334 + j0.2600 Ω/km, z₀ = 0.1181 + j0.9786 Ω/km.
- **No inverter-based resources.** No inverter parameter appears anywhere in the labels or the graph. This is the stiff, conventional case, so it answers nothing about inverters directly. It is the **control arm**: a relay should work here, and whatever breaks later can be attributed to the inverters rather than to the method.
- 1,101 simulations, 0.5 s each at 9600 Hz, event always at 1.1 s. A full factorial of faults: 4 lines × 5 locations (1, 20, 50, 80, 99 %) × 5 fault types × 3 resistances (1, 10, 40 Ω) × 3 phase selections, plus bus faults and incipient faults.
- **Only 24 non-fault events** (transformer inrush, load, capacitor and line switching). Far too few to evaluate security properly.
- The benchmark set uses fixed grid parameters, with no domain randomization. That matters for reading the learned-detector numbers below.

## Setup

Relay at bus 1 on line 1-2A. Zone 1 reach 85 % of the line, a reactance of
0.85 × 20 km × 0.2600 Ω/km = **4.42 Ω**.

| Class | Cases | Count |
|---|---|---|
| In zone (positive) | faults on 1-2A at 1, 20, 50, 80 % | 180 |
| Out of zone (negative) | faults on 2-3A and 2-3B at 1 and 20 %, and at bus 2 | 225 |
| Held out, never trained on | 1-2A at 99 %; parallel line 1-2B at all locations; switching events | 45, 225, 24 |

Waveforms resampled to 128 samples per cycle (6400 Hz) so the existing phasor and detector code runs unchanged. Comparison by 5-fold stratified cross-validation, repeated 3 times; each simulation contributes one window, so folds are grouped by episode.

## Validation before anything else

The distance element was checked against ground truth before it was used as a baseline. With faulted-phase selection, **bolted faults on the relay's own line are located with a mean error under 1.5 % of the line for every fault type**:

| Fault type | Mean distance error, bolted, % of line |
|---|---|
| single line to ground | 0.72 |
| single line to ground, with arc | 1.41 |
| line to line | 1.11 |
| double line to ground | 0.68 |
| three phase | 0.47 |

## Result 1: the zone-1 setting, nothing learned

The relay a protection engineer would set: six loops, k0 compensation, phase selection, trip if the reactance is below 4.42 Ω.

| | Trip rate |
|---|---|
| In zone (dependability) | **83.3 %** |
| Out of zone (false trip) | **0.0 %** |
| Own line at 99 % | 0.0 % |
| Parallel line 1-2B | 2.7 % |
| Switching events | 0.0 % |

By fault resistance:

| | 1 Ω | 10 Ω | 40 Ω |
|---|---|---|---|
| In zone | **100 %** | 85 % | 65 % |
| Out of zone | 0 % | 0 % | 0 % |
| Own line 99 % | 0 % | 0 % | 0 % |
| Parallel 1-2B | 0 % | 8 % | 0 % |

Perfectly secure, and fully dependable for low-resistance faults. Dependability falls to 65 % at 40 Ω. That is the known **reactance effect**: remote infeed through the fault resistance adds a reactive term the relay cannot measure, and a reactance-only reach underreaches. This is physics, and it is exactly the uncertainty Taylor's sets are built to bound.

![real doubleline](real_doubleline.png)

## Result 2: the four detectors, cross-validated

| Detector | ROC AUC | Dependability at 5 % false trip |
|---|---|---|
| Zone-1 reactance, threshold learned | 0.933 ± 0.020 | 86.7 ± 3.7 % |
| Negative-sequence magnitude | 0.654 ± 0.059 | 25.6 ± 5.3 % |
| Engineered features + logistic regression | **1.000 ± 0.000** | 100 ± 0.0 % |
| 1D CNN on raw waveform | 0.852 ± 0.047 | 59.3 ± 12.2 % |

## What it says

**1. The conventional element is a strong, honest baseline on real data.** It locates faults to within 1.5 % of the line and never trips out of zone. Anything proposed later has to beat this, not a straw man.

**2. The learned detectors are not better, and one generalises worse.** The CNN, at 0.852 AUC, is well below the textbook element on 405 examples. The engineered model scores a perfect 1.000 inside the training distribution, but on faults at 99 % of the line, which it never saw, it calls **15.6 %** of them in zone. The physics rule calls **0 %**. On the one real test of generalisation available here, the rule wins.

**3. The perfect 1.000 should not be read as a result.** The benchmark set has fixed grid parameters and a discrete factorial of scenarios, so with a feature vector that includes the loop impedances the classes are close to a lookup. The same thing happened on our synthetic data before we added parameter spread. This set is right for validating the element, not for ranking learned detectors.

**4. The resistance column is the interesting one.** Every miss by the zone-1 setting is a resistive fault. That is where an inverter's limited and angle-uncertain current will make things worse, and where the comparison on inverter data will matter.

## Bug found, and fixed, by running on real data

The first run gave the zone-1 setting **29.8 % false trips out of zone and 40 % trips for faults at 99 % of the line**, on a stiff grid where a correct element should give zero. Diagnosis showed the trips were exactly two of the five fault types. The element released every fault loop that passed a crude 50 % current supervision. In a phase-to-ground fault a healthy phase-to-phase loop also carries current, reads a small reactance with a very large resistance (3.4 Ω and 54 Ω in one case), and won the minimum.

Real relays prevent this with faulted-phase selection. The element now selects loops from incremental currents: ground loops for a phase-to-ground fault, only the phase-to-phase loop for a double line-to-ground fault (one ground loop overreaches there, 39 % against a true 50 %), and phase-to-phase loops above 80 % of the largest pair current otherwise. That produced the validation table above.

**This fix changes the shared element, so the synthetic in-zone versus out-of-zone results in [ZONE.md](ZONE.md) were produced with the flawed version and are being re-run.**

## Caveats

- No inverters, 50 Hz, one relay location, fixed grid parameters.
- 405 labelled cases in the main task. Small for a CNN; the CNN number is a floor, not a verdict.
- 24 switching events cannot support a security claim beyond "none tripped".
- No auxiliary signal, so no injection sweep is possible on this data.

## Next

1. The same experiment on `benchmark-TestGrid110kV` (8.3 GB, downloading), which the dataset paper describes as the protection reference grid for studying inverter impact. First check that it actually contains inverters. Read it straight from the archive; unpacked it would not fit on the disk.
2. Put the zone-1 setting and the engineered detector side by side on inverter data, per fault resistance.
