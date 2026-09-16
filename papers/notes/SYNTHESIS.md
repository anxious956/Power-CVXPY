# Synthesis: what 18 papers say, and what the project should therefore be

16 Sep 2026. All 18 papers read in full. Taylor's five were read directly; the other thirteen
were read in three parallel passes and every load-bearing claim below was then spot-checked
against the source PDF. Detail lives in `A_taylor_line.md`, `B_problem_statement.md`,
`C_competing_methods.md`, `D_ml_and_datasets.md`.

---

## 1. The problem is real, and the gap is documented by people who are not us

The Sandia / Siemens / EPRI gap analysis (SAND2024-04848) tabulates the expected impact of
grid-forming inverters on eight protection functions. For **six of the eight the entry reads,
verbatim, "No literature found"**: power swing, negative-sequence, phase selection,
communication-assisted (POTT/PUTT/DCB/DCUB), memory-polarised zero-sequence directional, and
line current differential. Only line distance protection has any grid-forming literature at
all, and Sandia then criticises the single study that exists on five counts: one fault type
only, fault resistance not reported, no IEEE 2800-compliant negative-sequence injection, a
simplified apparent-impedance relay rather than a real characteristic, and no parameter
sensitivity analysis.

That five-point critique is a ready-made experimental design. Anything we build should report
all five.

**The number to quote:** Sandia's expert interviews put grid-forming fault current at
**1.1 to 1.2 pu**, against 5 pu and more for a synchronous machine. One survey in the set
says ~2 pu; quote 1.1-1.2 and note the discrepancy rather than picking silently.

## 2. The failure mechanism is probably angle, not magnitude

This was the biggest surprise in the reading, and it is measured, not argued. The inverter's
current-limiting control determines the **angle** of its negative-sequence output impedance:

| Current limiter | Negative-sequence virtual impedance angle |
|---|---|
| Circular | −0.5° |
| Priority-based | +36.2° |
| Instantaneous | −51.6° |

None is inductive. Directional elements expect −90°. And the same work measures
∠(Δv₁/Δi₁) = **−31.7°** where −90° is required, showing that **incremental-quantity
supervising elements malfunction even with a highly inductive virtual impedance**, because
the limiter's dynamics break the superposition the method rests on. Validated in PSCAD and in
controller hardware-in-the-loop.

This matters directly to Taylor's line. His 2026 incremental-quantities letter states that its
stationarity assumption is "generally not realistic today" for inverters. Another group has
now measured exactly how it fails. **Nobody has joined those two facts.** The current-limiter
type is a missing dimension of the uncertainty set, and it is missing from our own toy model
too, which treats the inverter's negative-sequence path as an open circuit.

## 3. What we can no longer claim as new

Reading the competition cost us three claims. Better now than in a review.

| Claim we might have made | Who already owns it |
|---|---|
| Incremental negative-sequence quantities to detect faults in inverter grids | Opoku, Pokharel & Dimitrovski 2022 (arXiv 2205.02962). Passive, admittance form, directional sectors. |
| Making the inverter behave so legacy protection keeps working, **validated in hardware** | Li, Wu & Wang 2025 (arXiv 2504.21592). Controller-hardware-in-the-loop on three RT-Box3 units **and** a 45 kVA Chroma grid simulator with dSPACE. Verified. |
| Machine learning for fault detection and classification on inverter grids, including sub-cycle detection | Beikbabaei et al. 2024 (96 % on a 100 % inverter microgrid); Oelhaf et al. (macro-F1 0.989 from a 10 ms window) |
| Active probing plus machine learning | Ouali et al. 2024: inject a PRBS, learn the inverter's control mode from measured admittance. For system identification, not sub-cycle fault detection, but it must be cited and distinguished. |

Johansson, Xing, N. Taylor & Wang 2026 (arXiv 2604.10129) is the sharpest competitor. They
model the grid-forming limiter as a time-varying Thévenin, derive the incremental quantities
in closed form, and map dependability and security against fault resistance: dependable to
15 Ω at 45 % of the line, 10 Ω at 60 %, 8 Ω at 75 %, and secure beyond 90 % where a
quadrilateral element overreaches. (Note: Nathaniel Taylor of KTH is **not** Joshua Taylor.)

## 4. What is genuinely still open

Against all of that, four things survive.

**a. Bounded sets versus parameter sweep.** Johansson produces the same dependability picture
Taylor draws, but by sweeping parameters in MATLAB. Taylor computes the *image of an
uncertainty set* and can therefore say "every fault in this set is separated", which a sweep
can never say. **That distinction is the clearest novelty line we have, and the report should
say it in those words.** None of the three competitors treats location, fault resistance,
remote infeed and noise as bounded sets, minimises the perturbation, or offers a separation
guarantee.

**b. Nobody has compared them.** None of the three competing methods is compared against
either of the others. **A head-to-head on one test system is the most tractable real
contribution available to an undergraduate team**, and it is exactly what a senior design
project is shaped to do.

**c. The auxiliary signal is absent from the entire machine-learning literature.** Across
roughly 600 references in the seven ML and dataset papers, there are **zero** mentions of
auxiliary signals, active fault detection or signal injection. Our detection axis is clean and
now documented.

**d. Two openings Taylor names himself.** The 2025 paper: evaluate the characteristics and
optimised signals in electromagnetic transient simulation. The 2026 reachability paper: build
**underreaching** tests, because all of theirs are overreaching and will pick up faults on
neighbouring lines. Our `zone_detect.py` experiment already measures precisely that.

## 5. Two facts that reshape the work packages

**The simulation model already exists.** Taylor's 2026 reachability paper runs on a Simulink
IEEE 14-bus system with five grid-forming inverters, each with a current limiter, from
Baeckeland, Yang & Seo, IEEE Trans. Power Systems 41(1):198-213, 2026. **Asking him for that
model is the single highest-value question in the first meeting.** It would remove most of
work package 2.

**The hardware work package needs rethinking.** Li, Wu & Wang have already put
protection-aware inverter control on real hardware. Putting a *detector* on a board is still
different, but the honest framing is now: what runs on the board must be the optimised signal
and its detector, or the work is replication. A fair latency comparison is also easier than it
looks, since the published 50-90 ms figure was measured in TensorFlow on a shared Colab VM and
its sub-cycle numbers rely on a non-causal centred filter with 8.3 ms of look-ahead.

## 6. Data: stop generating our own

We have been running on synthetic waveforms generated from our own circuit model, which is as
good as that model and no better. Two public datasets change that.

| | **EvEMTBench** | **PROTECT-90** |
|---|---|---|
| Source | Kordowich et al., FAU Erlangen | arXiv 2606.24298 |
| Size | ~70k events, 11 archives | 9,022 episodes, 12.5 GB |
| Sampling | 9600 Hz point-on-wave, v and i | 6.4 kHz, 8 relays × 6 channels |
| Grids | CIGRE MV 20 kV, 110 kV double line, 110 kV protection reference grid, **IEEE 39-bus 345 kV** | 90 kV double line |
| Inverters | **Yes**, grid-following with a 1.2 pu current limit | **No** |
| Non-fault events | **Yes, 13 classes**: load on/off, capacitor on/off, line and cable energisation, LV and HV transformer inrush, motor start, synchronous machine trip, IBR trip | **No** |
| Faults | 1PHG (with and without arc), 2PH, 2PHG, 3PH, high-impedance | Short circuits, labelled by type, location, inception, operating point |
| Licence | Not stated; FAUDataCloud share link | CC BY 4.0, Zenodo 10.5281/zenodo.18418330 |

**Use EvEMTBench as the primary dataset.** It is the only public source that combines
current-limited inverters with the non-fault events that pose the security question, and
security is the first thing a review panel asks about. Its **IEEE 39-bus grid is 345 kV and
60 Hz**, which also settles the frequency mismatch: every other grid in the set is 50 Hz, so
use the 39-bus one where the 16.7 ms budget matters.

Use PROTECT-90 second, as the inverter-free control arm and to validate the phasor, sequence
and incremental front end against exact ground truth.

**The injection sweep still needs our own EMT simulation**, because no public dataset contains
an auxiliary signal. Generate it label-compatible with EvEMTBench's schema so the two can be
mixed.

**Method to copy:** Oelhaf's protocol, 5 ms stride, a 10 to 50 ms window sweep, and
**episode-grouped cross-validation**. That last part matters: sample-level shuffling leaks
across an episode and is what inflates some published accuracies.

## 7. Caveats to carry into anything we write

- No public dataset contains grid-forming inverters; EvEMTBench's are grid-following.
- No public dataset models CT or VT behaviour or measurement noise.
- EvEMTBench's inverters already inject negative-sequence fault-ride-through current, which is
  a genuine confound for any negative-sequence detector, ours included.
- Equations in three of the papers are embedded images that do not survive text extraction, so
  anything quoted from them must be read off the page.
- One paper contradicts itself on a threshold angle (20° in one section, 30° in a case study),
  and another gives 8.1° in a figure against 4.4° in the text.

## 8. The project, restated

> Take Taylor's bounded-set auxiliary-signal design, which is the only method in this space
> that offers a separation guarantee rather than a parameter sweep, put it on public EMT data
> with real non-fault events, and compare it head-to-head against the three published
> alternatives that have never been compared with each other: passive incremental
> negative-sequence, incremental-quantity distance with a current-limiter model, and
> protection-interoperable inverter control. Measure where the guarantee holds and where it
> breaks, and what the decision costs in milliseconds on a relay-sized processor.

That is defensible against everything in the reading list, and every piece of it is something
an undergraduate team can actually finish.
