# WP3 first experiment: can the relay actually see the auxiliary signal?

Date 16 Sep 2026. Code: `src/waveforms.py`, `src/detect.py`. Run: `python src/detect.py`.

## Setup

The waveform generator drives the **same two-bus sequence circuit as the design tool**
(`aux_model.solve`), so the design tool's certified δ and the detector's measured breaking
point are computed on one system. Sequence phasors per scenario are synthesized into
three-phase waveforms at 128 samples/cycle with noise, 5th and 7th harmonics, and a decaying
DC offset on the currents.

Following *Geometry of Distance Protection*, the auxiliary signal is designed **offline and
injected continuously** ("the auxiliary signal must be designed offline, pre-test"), so δ is
present in normal operation as well as during faults. What changes is where that
negative-sequence current flows: through the load path when healthy, partly into the fault
when not.

δ is swept **along the direction the design tool chose** (−23.2°, from `weak_sg`), so WP1 and
WP3 refer to the same signal. The design tool's certified magnitude, 0.514 pu, is the dotted
line in the figure.

**Task.** The ambiguous regime the design tool itself identified: high-resistance
line-to-ground faults (mr ≥ 0.85), which were the five cases it could not separate at δ = 0.
Negatives are a single-phase line-to-neutral load switching on, which draws equal positive-,
negative- and zero-sequence current and so produces both i⁻ and i⁰ at the relay, plus
balanced load steps.

**Protocol.** Independent train and test sets at every δ. Each detector's threshold, and its
polarity, are fixed on TRAIN at a 1 % false-alarm budget, then detection rate is measured on
TEST. 3600 train and 1800 test waveforms per point.

## Result

| δ (pu) | \|i⁻\| threshold | \|Δi⁻\| incremental | engineered features + LR | 1D CNN on raw waveform |
|---|---|---|---|---|
| 0.000 | 0.0 % | 0.0 % | 99.8 % | 100 % |
| 0.100 | 0.0 % | 0.0 % | 100 % | 100 % |
| 0.200 | 0.2 % | 0.0 % | 100 % | 100 % |
| 0.300 | 17.6 % | 0.0 % | 100 % | 100 % |
| 0.514 | 0.0 % | 0.0 % | 100 % | 100 % |

![detection sweep](detection_sweep.png)

## What this says

1. **The naive detector is not just weak, it is useless here, and more signal does not help
   it.** A magnitude threshold on \|i⁻\| never reaches 20 %. The reason is visible in the
   circuit: as δ grows, the fault's negative-sequence current at the relay goes *down*
   (0.23 → 0.09 pu) while the confuser's goes *up* (0.25 → 0.45 pu). The injected current
   partly diverts into the fault instead of reaching the relay. A scalar magnitude cannot
   use a guarantee that lives in the joint (v, i) space.

2. **A conventional multivariate element already solves this regime, and deep learning adds
   nothing.** Logistic regression on hand-built relay features (sequence magnitudes, the
   i⁰/i⁻ and i⁻/i⁺ ratios, relative angles, and their incremental versions) matches the CNN
   to within noise, at every δ. The gain comes from using the right quantities, not from
   learning. Reporting the CNN against \|i⁻\| alone would have been a strawman.

3. **In this regime the auxiliary signal is not the binding constraint.** A ground fault puts
   zero-sequence current *on the line*, while a single-phase load shunts most of its own at
   the load bus, so the i⁰/i⁻ ratio separates them with no injection at all.

## Why the confuser is too easy, and what to do about it

The negative is a *load*, and loads are easy to tell from faults once you look at zero
sequence. The genuinely hard case in protection, and the one Taylor's formulation is about
(the relay decides whether m ∈ [m̲, 1]), is an **out-of-zone fault near the reach point**:
the same fault type, the same sequence signature, only slightly further away. That is the
next iteration:

- positives: line-to-ground faults at m ≤ 0.8 (in zone)
- negatives: line-to-ground faults at m ≥ 0.9 and beyond the remote bus (out of zone)

With that confuser, the ratios and magnitudes stop separating and the decision has to rest on
the fine structure, which is where an injected signal and a learned detector should earn
their place. Expect all four curves to drop and to separate.

## Honest caveats

- Static phasor circuit, not EMT. No inverter dynamics, no current-limiter action, no CT
  saturation.
- Two buses, one fault type in the hard set, one confuser family.
- The CNN is small (three conv layers, ~40 k parameters) and trained for 18 epochs per point.
  It is not tuned; the point of the experiment is the comparison, not the architecture.
- Detection is offline over a fixed window. Latency, the WP4 question, is not measured here.
- Several earlier versions of this generator were discarded because they leaked the answer:
  faults that always sagged the voltage, and a confuser with no zero-sequence current. Both
  let every detector reach 100 % for the wrong reason. The current version is the first that
  makes the naive detector fail for a reason traceable to the circuit.
