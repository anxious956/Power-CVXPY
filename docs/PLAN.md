# Project plan

Last updated **15 Oct 2026**. This revision follows the technical review ([REVIEW.md](../REVIEW.md)),
the CIGRE MV runs and the B1 screening, which moved the project away from the plan written on
16 Sep 2026. The old plan is in git history; what changed is stated in §1 so the shift is on record.
Evidence for every statement below is in [REVIEW.md](../REVIEW.md) §7 (the claim register) and the
result documents it cites.

## 1. What changed since September, and why

The September plan was: implement Taylor's auxiliary-signal design, put it on EMT data, inject the
signal, show it helps. Four findings changed the direction.

| Finding | Where | Consequence for the plan |
|---|---|---|
| On an inverter-rich grid (CIGRE MV), a δ the inverter can actually supply **barely moves the zone-1 boundary**: +2–4 points of separable in-zone faults at 0.4 pu, and every cell with enough EMT faults either needs no δ or more than 1.2 pu | B1 screen, register row 42 | "Design a δ for reach" is not the project's headline. It is a measured negative result with a mechanism. |
| **Direction at inverter buses needs no injected signal.** Passive superimposed-quantity elements (Opoku-style negative-sequence admittance, plus our positive-sequence version) settle it in the first cycle | register rows 44, 46 | The second candidate use for δ is also closed, except for one case below. |
| With inverters that **suppress negative sequence**, direction does fail — and the fix is a **V2-referenced** current as IEEE 2800 asks, with enough gain at small V2. A δ fixed in advance in the inverter's frame fails at all 48 magnitudes and angles tried | register row 46, PR #27 | The remedy is a grid-code requirement, not a designed signal. |
| Telling a remote **inverter trip** from a forward fault needs an inverter-status channel; no injection can help, because the tripping inverter is the only source on its feeder | register row 45 | Another candidate use for δ closed, with the remedy named. |

What survived, and is now the spine of the work:

- a **reproducible evaluation protocol** for zone decisions on EMT data, with the pitfalls it exposes
  (sibling leakage, resampling look-ahead, reverse-fault security, guard band) and reporting at a
  **protection-grade operating point** — zero off-line false trips with binomial bounds — rather than
  at a false-alarm budget, which reorders the detectors;
- a **baseline ladder** that measures how much of an apparent ML advantage standard relay features
  remove, and an IBR-appropriate rung still to be added (§3, WP3);
- the **design tool in the TAC25 formulation** on the two-bus model: the current limit inside the
  problem, a margin in measurement units, a sound source set, a global solve;
- a **map of where an injection can and cannot help**, which is a publishable answer to a question
  Taylor's papers leave open, and which no one has measured.

## 2. The one-sentence version

Measure, on real and realistic EMT data and against a protection-grade baseline, **where a designed
auxiliary signal earns its cost and where a passive element, a channel or a grid-code requirement
does the job instead** — and close the one condition under which the question is still open, an
inverter-dominated grid where the signal can actually be injected.

## 3. Work packages

### WP1 Design tool — largely done, two things open
Done ([results/DESIGN.md](../results/DESIGN.md), REVIEW §10 item 2): TAC25 formulation, sound outer
source set, margin (ρ = 0.1 costs 29 % more signal), the current limit inside the problem, noise tied
to corrected CT/VT figures, a global polar solve, dense (m, R_f) validation.
Open:
1. the multi-bus sequence solver and Minkowski aggregation needed for the IEEE 14-bus example of the
   Geometry paper (optional; gates nothing on real data);
2. the **current-limiter type** as a dimension of the uncertainty set (measured negative-sequence
   virtual-impedance angles −0.5°, +36.2°, −51.6° for circular, priority-based and instantaneous
   limiters). Taylor's model does not carry this and neither does ours.

### WP2 Simulation — now unblocked, the critical path
PSCAD 5.0.1 is licensed and installed. Plan, branch points and risks: [PSCAD.md](PSCAD.md).
The goal is **not** "prove δ works". It is to re-run the B1 screen and the detector comparison where
the inverters carry a material share of the fault current and the injection exists, so that the
negative result above either generalises or is bounded to distribution grids.
Owner: Asmar Hasanova.

### WP3 Detection and comparison — done on three grids, two gaps
Done: the conventional ladder (R0–R4, T1, T2) with directional supervision, a sequence-trajectory
CNN, engineered features, the re-implemented Hasan et al. (2026) SVM, on EvEMTBench DoubleLine,
TestGrid110kV, adapt_grid-TestGrid and CIGRE MV, with grouped folds and held-out reverse faults.
Open:
1. **Rung R5, the IBR-appropriate ladder** (Kasztenny 2022): offset quadrilateral with a
   loop-current-polarised reactance line, voltage-based loop selection, 32G / 32WI / TD32
   supervision, zone 1 enabled only for a 2–3 cycle window. Today's ladder is memory- and
   I₂-polarised, which is correct for synchronous-dominated data and **wrong** for the
   inverter-dominated data of WP2. Add it *before* that data arrives.
2. **MMKF** (Pirani & Taylor 2022) and an incremental-quantity element as the remaining
   conventional competitors.

### WP4 Embedded latency — unchanged, still open
CNN inference measured on the laptop (87 µs the network, 784 µs with features). What is missing is a
board and a causal end-to-end protocol: decisions at 10 / 20 ms from a **causal starter**, not from
true inception, with inference latency measured separately. Budget: one cycle, 20 ms at 50 Hz,
16.7 ms on the 60 Hz sets.

## 4. What the work can claim today, and what it cannot

Claim (REVIEW §10 item 8):
- the evaluation protocol and the pitfalls it exposes, at a protection-grade operating point;
- the ladder result: how much of an apparent ML advantage standard relay features remove;
- the design tool in the TAC25 formulation, within its two-bus model;
- on adapt_grid, a single-ended learned detector covering most of the high-R_f in-zone faults no
  settable quadrilateral can enclose, at zero off-line false trips — at one relay of two;
- the map of §1: where an injection helps, and what replaces it where it does not.

Cannot claim:
- that auxiliary signals help detection on inverter-dominated grids (untested — that is WP2);
- that learning as such beats protection logic;
- that any of this holds where inverters carry a material share of the fault current.

## 5. Milestones from here

| When | What |
|---|---|
| Oct 2026 | PSCAD edition confirmed; IRTSD model obtained and one documented fault case reproduced. PR #27 merged. |
| Nov 2026 | IRTSD waveforms through our pipeline (element locates bolted faults within a few per cent). Rung R5 implemented. |
| Dec 2026 | Auxiliary signal added as an event type; first δ sweep on an inverter-rich grid. Fall report. |
| Jan–Feb 2027 | B1 screen re-run on that data; limiter type added to the uncertainty set; MMKF in the comparison. |
| Mar–Apr 2027 | Embedded latency on a board. Paper written. |
| Jun 2027 | Submit to NAPS 2027. |

## 6. Questions for Prof. Taylor

1. **The Baeckeland 14-bus Simulink model** with five grid-forming inverters. Still the highest-value
   ask: neither IRTSD nor CIGRE MV has grid-forming inverters, and PSCAD does not change that.
2. Our B1 result says a suppliable δ barely moves the reach boundary on a distribution feeder, and
   that direction is settled passively. **Is the reach problem the one the method should target, or
   is the intended target fault-type separation on the relay's own line**, as in the Geometry paper?
3. Which injection regime: triggered on the limiter indicator (2022) or designed offline and injected
   continuously (2025)?
4. The negative-sequence suppression case: is a V2-referenced current (IEEE 2800) the intended
   mechanism, in which case the design question becomes gain selection rather than δ selection?
5. Co-authorship and target venue, if this becomes a paper.

## 7. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| PSCAD edition turns out to be Free (15 nodes) | IRTSD out | Two-bus EMT model as the positive control; decide fast ([PSCAD.md](PSCAD.md)) |
| Snapshot and simulation compute | Weeks lost | Keep the case list small until one documented case is reproduced; build snapshots once |
| IRTSD has no grid-forming inverters | The hardest regime stays untested | Ask for the Baeckeland model (question 1); state the limit in any claim |
| Carrying today's ladder to inverter-dominated data | Repeats the unfair-baseline error in the opposite direction | Rung R5 before that data arrives (WP3) |
| "This is just replication" | Fatal in review | The contribution is the evaluation and the map of §1, not the method |
