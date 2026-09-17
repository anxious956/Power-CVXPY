# Project plan

Last updated 16 Sep 2026, after reading all 18 papers. See
[`papers/notes/SYNTHESIS.md`](../papers/notes/SYNTHESIS.md) for the evidence behind every
choice below. This revision narrows the project on purpose: three claims we might have made
turn out to be taken, and the reading also handed us a better dataset and a better framing.

## The one-sentence version

Take Taylor's bounded-set auxiliary-signal design, the only method in this space that offers a
separation **guarantee** rather than a parameter sweep, put it on public electromagnetic
transient data with real non-fault events, and compare it head-to-head against the three
published alternatives that have never been compared with each other. Measure where the
guarantee holds, where it breaks, and what the decision costs in milliseconds.

## Why this is defensible

| Question a reviewer asks | Answer |
|---|---|
| Is the problem real? | Sandia SAND2024-04848 records "No literature found" for grid-forming impact on six of eight protection functions. |
| Is the method new? | No, it is Taylor's. Our contribution is evaluation and comparison, which is what his conclusions ask for. |
| Is the evaluation new? | Yes. None of the three competing methods has been compared against either of the others, and none is evaluated on public data with non-fault events. |
| Is the ML angle new? | The auxiliary signal appears **zero** times across ~600 references in the ML literature we read. Detection of an injected signal is untouched. |
| Why not just sweep parameters? | Because a sweep cannot say "every fault in this set is separated." Computing the image of an uncertainty set can. That is the whole distinction. |

## Work packages

### WP1 Design tool (optimisation)
- **First milestone, before anything else:** reproduce Taylor's 2023 single-line example. One
  IBR, one load, z⁻ = z⁺ = 30 + j35, z_f = 26 + j·x_f, sweep x_f over [12, 58], Q = I. The
  expected result is known: |θ̄| peaks near x_f ≈ 35, where the fault reactance matches the
  normal one. If we reproduce that curve, the tool is correct.
- **Second milestone:** the 2025 14-bus example, which is specified completely (SGs at buses
  1, 3, 5, 14; IBRs at 2, 4, 7, 8, 12 with angles spread over [0, 2π/3]; loads at 6, 10, 11,
  13 at 0.1 + j0.01; 20-gon noise scaled by Σ = 0.1I; relay at bus 2 on line 2-3; k = 2;
  r_F = 1; m̲_z = 0.15).
- **Then extend:** add the **current-limiter type** as a dimension of the uncertainty set.
  Measured negative-sequence virtual impedance angles are −0.5°, +36.2° and −51.6° for
  circular, priority-based and instantaneous limiters. Taylor's model does not carry this and
  neither does ours.
- Skills: Python, CVXPY, linear algebra. Reading: A-notes §2 and §3, then the TAC paper.

### WP2 Simulation and data
- **Ask Prof. Taylor first**, before building anything: the 2026 reachability paper runs on a
  Simulink IEEE 14-bus model with five grid-forming inverters and current limiters, from
  Baeckeland, Yang & Seo, IEEE TPWRS 41(1):198-213, 2026. If we can have it, most of this work
  package disappears.
- **Primary dataset: EvEMTBench** (FAU Erlangen). ~70k events at 9600 Hz, point-on-wave
  voltage and current, grid-following inverters with a 1.2 pu limit, and **13 non-fault event
  classes** including motor start, transformer inrush and capacitor switching. Use the
  **IEEE 39-bus 345 kV grid**, the only 60 Hz system in the set, wherever the one-cycle budget
  matters.
- **Secondary: PROTECT-90** (Zenodo 10.5281/zenodo.18418330, CC BY 4.0). 9,022 EMT episodes,
  no inverters, no non-fault events. Use it as the inverter-free control arm and to validate
  the phasor, sequence and incremental front end against exact ground truth.
- **Still ours to generate:** the injection sweep. No public dataset contains an auxiliary
  signal. Build it label-compatible with EvEMTBench's schema so the two can be mixed.
- Retire the hand-written synthetic generator to a sanity-check role once real data is in.

### WP3 Detection and comparison
- Implement four detectors on one dataset with one protocol: the textbook distance element
  with k0 compensation, passive incremental negative-sequence admittance, Taylor's
  multiple-model Kalman filter, and a learned detector.
- **Protocol, copied deliberately:** 5 ms stride, window swept 10 to 50 ms, and
  **episode-grouped cross-validation**. Sample-level shuffling leaks across an episode and
  inflates published accuracies.
- Report dependability and security separately, and report fault resistance, because Sandia's
  critique of the existing literature is that nobody does.
- Sweep the injection amplitude and find where each detector breaks.
- Skills: Python, PyTorch, signal processing.

### WP4 Embedded latency
- Port the detectors to a Jetson or similar, stream waveforms, measure end-to-end decision
  latency and jitter against 16.7 ms.
- **Framing, corrected:** protection-aware inverter *control* on hardware is already published
  and validated on a 45 kVA setup. What is not done is a *detector* for the optimised signal
  on a relay-sized processor. Say it that way or the work reads as replication.
- The published figure to beat, 50 to 90 ms, was measured in TensorFlow on a shared Colab VM
  and its sub-cycle numbers use a non-causal centred filter with 8.3 ms of look-ahead. A
  causal implementation should beat it comfortably; borrow the classification-time versus
  inference-latency distinction and the confidence-gated abstention output.

## Milestones

| When | What |
|---|---|
| Sep 2026 | Advisor confirmed. Roles assigned. Everyone reads Taylor's 2023 paper (5 pages) and the synthesis. EvEMTBench downloaded and opened. |
| Oct 2026 | WP1 reproduces the 2023 curve. WP2 has EvEMTBench loading and one relay's waveforms plotted. |
| Nov 2026 | Four detectors running on EvEMTBench under one protocol. Embedded board set up. |
| Dec 2026 | First head-to-head comparison and the injection sweep. Fall report and demo. |
| Feb 2027 | Current-limiter type added to the uncertainty set. Latency measured. |
| Mar–Apr 2027 | Paper written. Senior design final. |
| Jun 2027 | Submit to NAPS 2027 (2026's deadline was 15 June). |

## Questions for the advisor, in priority order

1. **Can we have the Simulink 14-bus model with five grid-forming inverters** from Baeckeland,
   Yang & Seo? This is the highest-value question.
2. Which injection regime should we assume? The 2022 paper triggers on the inverter's own
   limiter indicator and warns it can false-trigger on load changes; the 2025 paper designs the
   signal offline and injects it continuously. They are different schemes.
3. Your incremental-quantities letter says the stationarity assumption is not realistic for
   inverters today. Another group has measured that failure with hardware in the loop,
   ∠(Δv₁/Δi₁) = −31.7° where −90° is needed. Would quantifying that drift per current-limiter
   type be useful to you?
4. Is a learned detector of interest, or should WP3 stay model-based?
5. Co-authorship, if this becomes a paper.

## Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Nobody strong in Simulink | WP2 stalls | Public datasets now cover most of WP3, so WP2 is no longer the critical path. Only the injection sweep needs simulation. |
| The Simulink model is not shared | 2-3 weeks lost | EvEMTBench plus NREL PyPSCAD |
| EvEMTBench licence unstated | Cannot redistribute derived data | Email the FAU authors early; cite and link rather than mirror |
| Advisor uninterested in ML | WP3 loses a detector | Three of the four detectors are model-based. The comparison stands without it. |
| Member drops | WP4 unstaffed | WP4 is optional; the core is WP1-3 |
| "This is just replication" | Fatal in review | The framing in §"Why this is defensible" is the answer, and it is evidenced. Never present the hardware piece as novel on its own. |

## What we already have

- A working CVXPY implementation of the design method on a two-bus model, three regimes, the optimum verified against brute force.
- A three-bus in-zone versus out-of-zone experiment, which happens to address the underreaching tests Taylor's 2026 paper names as future work.
- 26 papers read, with notes, and eight known gaps listed with sources. The set now includes
  the Taylor & Domínguez-García TAC 2025 paper, the Baeckeland current-limiting grid-forming
  model, and six SEL practitioner references on settings and instrument transformers.
