# Project plan

Last updated **15 Oct 2026**. This revision follows the technical review ([REVIEW.md](../REVIEW.md)),
the CIGRE MV runs and the B1 screening, which moved the project away from the plan written on
16 Sep 2026. The old plan is in git history; what changed is stated in §1 so the shift is on record.
Evidence for every statement below is in [REVIEW.md](../REVIEW.md) §7 (the claim register) and the
result documents it cites.

## 1. What changed since September, and why

The September plan was: implement Taylor's auxiliary-signal design, put it on EMT data, inject the
signal, show it helps. Four screening findings changed the direction.

> **What none of this is.** No result in this repository comes from data with an injected signal.
> No public EMT dataset contains one, and we have not simulated one yet. The reach and longer-line
> verdicts come from a **static sequence model** of the feeder (optimistic for δ: each fault gets its
> best δ angle); the direction and inverter-trip verdicts come from EMT data **without** injection,
> plus the same static model. They say where a δ is unlikely to be needed. They do **not** say a δ
> fails, because that has not been tested. The EMT study with δ injected is what tests it.


| Finding | Where | Consequence for the plan |
|---|---|---|
| On an inverter-rich grid (CIGRE MV), a δ the inverter can actually supply **barely moves the zone-1 boundary**: +2–4 points of separable in-zone faults at 0.4 pu, and every cell with enough EMT faults either needs no δ or more than 1.2 pu | B1 screen, register row 42 | "Design a δ for reach" is no longer the headline. A static-model finding with a mechanism; untested in EMT with injection. |
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

## 2. What we proposed to Prof. Taylor, and hold to

The deck of 6 Oct 2026 proposed **an EMT test of his method** in four steps. They are the work
packages, in this order:

| Step (as presented) | What it means here |
|---|---|
| **1 · Design tool**: turn the two-bus design into a tool for a multi-bus network | the TAC25 design engine generalised to the sequence network of the grid we simulate |
| **2 · EMT grid**: Simulink or PSCAD, with the inverter injecting the designed signal | a PSCAD grid with an inverter whose negative-sequence current is the designed δ |
| **3 · Detection**: under load and noise, his Kalman filter against a learned detector, shrinking δ until each fails | MMKF (Pirani & Taylor 2022) vs a learned detector on that EMT data, δ swept down |
| **4 · Real time**: the detector on an embedded board, within one cycle | causal decision and inference latency on a board |

The deck's "where your method could still matter" (I₂-suppressing inverters, longer lines,
grid-forming systems) are **scenarios inside steps 2 and 3**, not a separate track: the same EMT grid
is run with the inverter's negative sequence suppressed, V2-referenced, or the designed δ.

## 3. Work packages, in the deck's order

### Step 1 · Design tool — two-bus done, multi-bus open
Done ([results/DESIGN.md](../results/DESIGN.md), REVIEW §10 item 2): TAC25 formulation, sound outer
source set, margin (ρ = 0.1 costs 29 % more signal), the current limit inside the problem, noise tied
to corrected CT/VT figures, a global polar solve, dense (m, R_f) validation.
Open:
1. **the multi-bus tool**: sequence network of an arbitrary grid, Minkowski aggregation of the source
   sets, the separation problem for the fault cases at one relay. First target: the small grid of
   step 2, so design and simulation describe the same circuit; then the IEEE 14-bus example of the
   Geometry paper (needs the Baeckeland line data);
2. the **current-limiter type** as a dimension of the uncertainty set (measured negative-sequence
   virtual-impedance angles −0.5°, +36.2°, −51.6° for circular, priority-based and instantaneous
   limiters).

### Step 2 · EMT grid — the injecting inverter exists; the grid around it is next
Done ([results/PSCAD_INVERTER.md](../results/PSCAD_INVERTER.md)): an averaged grid-following inverter
built in PSCAD from Python, with three negative-sequence modes (suppressed, V2-referenced as IEEE 2800,
a designed δ fixed in the V1 frame) and a 1.2 pu limit, **verified to inject what it is told** (δ of
0.1 pu at +90° measured as 0.1000 pu at +89.5°). Also: PSCAD driven from Python and connected to the
relay code ([results/PSCAD_FIRST.md](../results/PSCAD_FIRST.md)).
Also done ([results/PSCAD_TWOBUS.md](../results/PSCAD_TWOBUS.md)): **the design tool's two-bus circuit
built in PSCAD around that inverter, matching the design model** at the relay to 0.000 pu before the
fault and 0.001–0.016 pu during A-G and B-C faults.
And ([results/PSCAD_DELTA_TEST.md](../results/PSCAD_DELTA_TEST.md)): **the designed δ injected in EMT**.
At the design tool's worst-case realisation, the two cases it cannot separate at δ = 0 are not separated
in EMT without the signal and separated with the designed 0.18 pu, as promised; margins thin.
And ([results/PSCAD_DELTA_SWEEP.md](../results/PSCAD_DELTA_SWEEP.md)): all 30 cases and the box corners,
124 runs. Separation holds everywhere tested, with a 10 % margin; but where the inverter's limiter cuts δ,
normal operation leaves the design's normal set, so the current limit must be inside the design.
Next:
1. the TAC25 design (current limit inside the problem) tested in EMT the same way; then a small multi-bus grid (source, protected line, inverter at the remote bus, adjacent line),
   with faults whose location, resistance and type are swept from Python;
2. the designed δ from step 1 injected, and the separation the tool promises checked in EMT;
3. the deck's scenarios: I₂ suppressed, longer lines, and a grid-forming inverter (Taylor's 14-bus
   model if shared, otherwise our own).
Owner: Asmar Hasanova.

### Step 3 · Detection — learned side done on public data, Kalman filter and δ sweep open
Done on public data without injection: the conventional ladder (R0–R4, T1, T2) with directional
supervision, a sequence-trajectory CNN, engineered features, the re-implemented Hasan et al. (2026)
SVM, on EvEMTBench DoubleLine, TestGrid110kV, adapt_grid-TestGrid and CIGRE MV, with grouped folds
and held-out reverse faults.
Open:
1. **MMKF** (Pirani & Taylor 2022), the detector the deck names;
2. both on the step-2 EMT data, under load and noise, **shrinking δ until each fails**;
3. rung R5, the IBR-appropriate conventional baseline (Kasztenny 2022), before inverter-dominated data.

### Step 4 · Real time — open
CNN inference measured on the laptop (87 µs the network, 784 µs with features). Missing: a board and a
causal end-to-end protocol (decisions at 10 / 20 ms from a causal starter, inference latency measured
separately; one cycle is 16.7 ms at 60 Hz).

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
| Oct 2026 | Step 2: the injecting inverter (done, 16 Oct). PSCAD and inverter groundwork, as Prof. Taylor asked. |
| Nov 2026 | Step 2: the small multi-bus grid around it with swept faults. Step 1: the multi-bus design tool on the same grid. |
| Dec 2026 | Steps 1 → 2: the designed δ injected in EMT and the promised separation checked. Fall report. |
| Jan–Feb 2027 | Step 3: MMKF and a learned detector on that data, δ shrunk until each fails; the deck's scenarios (I₂ suppressed, longer lines, grid-forming). |
| Mar–Apr 2027 | Step 4: latency on a board. Paper written. |
| Jun 2027 | Submit to NAPS 2027. |

## 6. What Prof. Taylor asked for, and what we owe him

Both halves of the work are ours: the convex design in CVXPY and the EMT evaluation. After the
6 Oct deck he arranged the PSCAD licence and asked us to **learn PSCAD** (he does not use it) and to
**study how inverters work**. Those come first (§5).

The deck named three places his method still has room (I₂-suppressing inverters, longer lines,
grid-forming systems) and asked to test it there. Two have since been screened **in the static model
only**: the I₂ case points to a V2-referenced current rather than a designed δ, and the longer-line
case did not behave as the deck suggested. That correction is ours to deliver, with its limit
attached: neither was tested with δ injected in EMT. What is left of the promise is the test that
can settle all three, an EMT study with δ injected.

## 7. Questions for Prof. Taylor

These are the deck's four questions, in the deck's order, with what we have learned since.

1. **Reach on short lines.** Our screen finds a δ the inverter can afford barely separates in-zone
   from just-beyond faults on 2–4 Ω lines, as Theorem 1 predicts. Does that match his expectation,
   and **is there an observable — time domain, wideband — where the difference is larger?**
2. **Where to test δ next.** We offered I₂-suppressing inverters, longer lines, grid-forming systems.
   Since the deck, the static model pointed the first towards a grid-code question and did not
   support the second, which leaves grid-forming as the strongest case. None of the three has been
   tested with δ injected in EMT; which should the first injected EMT run target?
3. **The current limit.** During a fault the inverter already runs near 1.2 pu, so δ has to fit in
   what is left. Should the limit in the design include δ, **checked phase by phase or as one
   total?** (Our own correction: the limit belongs inside the problem, not as an outer check.)
4. **The Baeckeland 14-bus Simulink model** with five grid-forming inverters. Neither IRTSD nor
   CIGRE MV has grid-forming inverters, and PSCAD does not change that.
2. Our B1 result says a suppliable δ barely moves the reach boundary on a distribution feeder, and
   that direction is settled passively. **Is the reach problem the one the method should target, or
   is the intended target fault-type separation on the relay's own line**, as in the Geometry paper?
3. Which injection regime: triggered on the limiter indicator (2022) or designed offline and injected
   continuously (2025)?
4. The negative-sequence suppression case: is a V2-referenced current (IEEE 2800) the intended
   mechanism, in which case the design question becomes gain selection rather than δ selection?
5. Co-authorship and target venue, if this becomes a paper.

## 8. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| PSCAD edition turns out to be Free (15 nodes) | IRTSD out | Two-bus EMT model as the positive control; decide fast ([PSCAD.md](PSCAD.md)) |
| Snapshot and simulation compute | Weeks lost | Keep the case list small until one documented case is reproduced; build snapshots once |
| IRTSD has no grid-forming inverters | The hardest regime stays untested | Ask for the Baeckeland model (question 1); state the limit in any claim |
| Carrying today's ladder to inverter-dominated data | Repeats the unfair-baseline error in the opposite direction | Rung R5 before that data arrives (WP3) |
| "This is just replication" | Fatal in review | The contribution is the evaluation and the map of §1, not the method |
