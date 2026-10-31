# Project plan

Last updated **19 Oct 2026** (status and milestones, §3–§6: steps 1–3 done on the three-bus grid; the first of the
deck's scenarios, I₂ suppression, done with δ injected; longer lines next; about four months ahead of the October
schedule). The 15 Oct revision follows the technical review ([REVIEW.md](../REVIEW.md)),
the CIGRE MV runs and the B1 screening, which moved the project away from the plan written on
16 Sep 2026. The old plan is in git history; what changed is stated in §1 so the shift is on record.
Evidence for every statement below is in [REVIEW.md](../REVIEW.md) §7 (the claim register) and the
result documents it cites.

## 1. What changed since September, and why

The September plan was: implement Taylor's auxiliary-signal design, put it on EMT data, inject the
signal, show it helps. Four screening findings changed the direction.

> **What none of this is** (as written on 15 Oct 2026; **superseded on 16–19 Oct**: the designed δ has since been
> injected in PSCAD on a two-bus and a three-bus grid, REVIEW rows 49–51, 55–58, and §3–§4 below carry the
> results; the box is kept because the September-to-15-Oct findings it qualifies still carry its limit).
> No result in this repository comes from data with an injected signal.
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

### Step 1 · Design tool — two-bus and multi-bus done

Done 16–17 Oct 2026 ([results/FRAMES.md](../results/FRAMES.md)): the design with **both frames** a real system has, the
inverter's own V1 and the relay's pre-fault memory. It is a sampled Taylor model, verified by containment. The
measured budgets (reference noise, model error, drift) are in it, and so are structured, regime-dependent CT/VT
errors (REVIEW.md row 53). On the three-bus grid:
- the design point is **δ = 1.12 pu at 225°, ρ = 0.1**, about 93 % of the inverter's rating;
- δ*(ε) is 0.04 pu at the design tier's noise bound (box; 0 with the structured design tier) and 1.12 pu at
  ε = 0.08;
- with structured class-tier errors δ* = 1.12 pu.


Done ([results/DESIGN.md](../results/DESIGN.md), REVIEW §10 item 2): TAC25 formulation, sound outer
source set, margin (ρ = 0.1 costs 29 % more signal), the current limit inside the problem, noise tied
to corrected CT/VT figures, a global polar solve, dense (m, R_f) validation.
Done 16 Oct 2026 ([results/MULTIBUS.md](../results/MULTIBUS.md)): **the multi-bus tool** (`src/network.py`),
sequence network of any grid, Minkowski aggregation of the source sets, the reviewed design on it; exact against
the two- and three-bus models; built in PSCAD by `src/pscad_network.py` if radial or of uniform z0/z1; on a
three-bus network the EMT system separates every case with the margin in 128 runs (δ-priority limiter), but the
runs leave the design's realisation once the fault starts and the design curtails the inverter's normal output to
≤ 0.46 pu (REVIEW.md row 50). Needed for a case-by-case check: I1 and δ modelled in the inverter's V1 frame during
the fault.
Open:
1. the IEEE 14-bus example of the Geometry paper (needs the Baeckeland line data); several injecting
   inverters (vector δ); meshed networks in PSCAD;
2. the **current-limiter type** as a dimension of the uncertainty set (measured negative-sequence
   virtual-impedance angles −0.5°, +36.2°, −51.6° for circular, priority-based and instantaneous
   limiters).

### Step 2 · EMT grid — done on the three-bus grid

Done 16–17 Oct 2026 ([results/FRAMES.md](../results/FRAMES.md)): the three-bus PSCAD grid, with the inverter
V1-referenced as its controller runs.
- **The bare-DFT reference is unstable above about 1.0 pu on bolted B-C faults.** A first-order PLL-like reference
  filter (15 Hz) removes it, and the cap becomes 1.14 pu.
- The relay chain has a mimic filter.
- **The design point holds in EMT** at its witnesses, window edges and random inception, and over all 48 cases (0
  points outside their own sets in the 2–3-cycle window).
- The deck's scenarios with δ injected: I₂ suppressed done (19 Oct, under step 3 below); longer lines next;
  grid-forming open.

The history up to 16 Oct:

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
And ([results/PSCAD_TAC25.md](../results/PSCAD_TAC25.md)): **the TAC25 design (limit inside) holds in EMT** on the
two-bus circuit, 124 runs, for a δ-priority limiter; not for one that scales both. The test exposed a sign error in
the design code's limit rows (REVIEW.md row 49): with the limit inside, δ is about the unconstrained value, not half.
Next, as written on 16 Oct (all three done since: 1 in PR #38–#41, 2 in PR #44, 3's first scenario in PR #57; the
other two scenarios are in §5):
1. the design must name its limiter and the frame of δ (the inverter's own V1 turns δ when the limiter acts);
   then a small multi-bus grid (source, protected line, inverter at the remote bus, adjacent line),
   with faults whose location, resistance and type are swept from Python;
2. the designed δ from step 1 injected, and the separation the tool promises checked in EMT;
3. the deck's scenarios: I₂ suppressed, longer lines, and a grid-forming inverter (Taylor's 14-bus
   model if shared, otherwise our own).
Owner: Asmar Hasanova.

### Step 3 · Detection — done on the EMT data with δ injected; the deck's scenarios follow

Done 17–19 Oct 2026 ([docs/STEP3.md](STEP3.md), [results/STEP3_PILOT.md](../results/STEP3_PILOT.md)):
- **Front end:** a common chain with instrument errors on the samples, the mimic filter, a starter and the memory
  frame.
- **Detectors:** D1 the set test, D0 incremental 50N/50Q, D2 the multiple-model test (Pirani et al., moved to the
  relay), and D3 the CNN.
- **Pilot, with realistic noise:** every detector, 50N included, detected the pilot's 20 hard-set scenarios
  (R_f ≤ 40 Ω) without δ. That is why the
  δ sweep was not run as planned.
- **Worst case:** D1's worst-case curve on 350 clean runs (hard A-G guaranteed 0.33 at δ = 0 → 1.00 at ¾ δ*), plus
  each detector against its own worst case (a stress bound).
- **Two screens:**
  - an inverter-fed relay end ([results/IBR_GRID_SCREEN.md](../results/IBR_GRID_SCREEN.md)): 59N detects without δ;
    selectivity (T2) is the open question;
  - high resistance ([results/HIGHR.md](../results/HIGHR.md), PR #56): **the band where the signal certifies
    ground-fault detection and incremental 50N fails depends on the 50N pickup**, crossover about 115 / 160 / 250 Ω
    at a 0.20 / 0.15 / 0.10 pu pickup; the 160 Ω design holds in EMT; a 0.2 pu load step is a certain D1 false
    alarm at that design (REVIEW row 55).
- **Deck scenario 1, the I₂-suppressing inverter** ([docs/I2_DIRECTION.md](I2_DIRECTION.md), PR #57, review PR #58,
  REVIEW rows 56–59), direction at the inverter's relay, δ designed and injected in EMT:
  - suppression breaks direction **only when nearly all of the load behind the relay is inverter-interfaced**
    (s → 1): in EMT 80 % (grid-side control) or 68 % (converter-side) of the forward set is lost, 20 % or 40 % of it
    wrong-way; at s = 0.8 only dependability is lost (static);
  - IEEE 2800's V2-referenced current **restores direction in both control brackets** (0 % misdirected);
  - a designed δ **does not fix the conventional element** (REVIEW row 46's prior holds in EMT); the set test decides
    direction without δ for every B-C run and gets the worst-case guarantee from δ: 0.20 pu at the structured tier,
    free in I1; 0.98 pu at the box tier, displacing 46 % of the inverter's normal output. **δ buys the guarantee,
    not the decision**, as in the step-3 detection results.
  - One network, nominal source point, one point on wave, clean runs.

The history up to 16 Oct:

Done on public data without injection: the conventional ladder (R0–R4, T1, T2) with directional
supervision, a sequence-trajectory CNN, engineered features, the re-implemented Hasan et al. (2026)
SVM, on EvEMTBench DoubleLine, TestGrid110kV, adapt_grid-TestGrid and CIGRE MV, with grouped folds
and held-out reverse faults.
Open on 16 Oct (1 and 2 done since in step 3, above: D2 is the multiple-model test in the sense of Pirani et al.,
and the δ sweep was replaced by the worst-case curve because every detector detected the pilot's 20 hard-set
scenarios (R_f ≤ 40 Ω) without δ under realistic
noise; 3 is still open):
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
- the map of §1: where an injection helps, and what replaces it where it does not;
- (18 Oct) on one three-bus grid, EMT with δ injected: Taylor's design keeps its promise. The guarantee it buys is a
  worst-case one, and its price is set by the instruments: free at near-nominal accuracy, about 93 % of the
  inverter at protection-class fault-condition errors. Under realistic noise, conventional incremental 50N already
  detects the faults it was designed for; where it stops depends on its pickup (crossover about 115 / 160 / 250 Ω
  at a 0.20 / 0.15 / 0.10 pu pickup, REVIEW row 55), and from there the signal certifies ground-fault detection,
  at 160 Ω in EMT.
- (19 Oct) the deck's I₂-suppression scenario, in EMT with δ injected: suppression costs the relay its direction
  only on an inverter-dominated back side (s → 1); IEEE 2800's negative-sequence current restores it; a designed δ
  certifies direction for the set test and does not repair the conventional element. Same scope as above.

Cannot claim:
- that auxiliary signals help detection on inverter-dominated grids: on the synchronous-source three-bus grid the
  signal buys the worst-case guarantee, not detection (step 3); where inverters carry the fault current it is
  untested, except for direction at s = 1 (the I₂ study);
- that learning as such beats protection logic;
- that any of this holds where inverters carry a material share of the fault current.

## 5. Milestones from here

Revised 19 Oct 2026. The October schedule is kept below the new one for the record.

| When | What | Status |
|---|---|---|
| Oct 2026 | Step 2: the injecting inverter; PSCAD and inverter groundwork, as Prof. Taylor asked | **done** (16 Oct) |
| Oct 2026 (planned Nov) | Steps 1 and 2: the three-bus PSCAD grid with swept faults; the multi-bus design tool on it | **done** (PR #38–#41) |
| Oct 2026 (planned Dec) | Steps 1 → 2: the designed δ injected in EMT and the promised separation checked | **done** (PR #44: both frames, filtered reference, mimic chain) |
| Oct 2026 (planned Jan–Feb 2027) | Step 3: detectors on the EMT data, the worst-case sweep | **done** (18 Oct): pilot, worst-case curve, structured errors, inverter-fed and high-R screens, the high-R EMT check (PR #56) |
| Oct 2026 (planned Nov–Dec) | Deck scenario 1: I₂ suppressed, direction, δ designed and injected in EMT | **done** (19 Oct, PR #57, review PR #58) |
| Oct–Nov 2026 | Deck scenario 2: longer lines, with the same machinery (static δ*(length), conventional element vs set test, EMT check where the conventional element first fails), pre-registered ([docs/LONG_LINES.md](LONG_LINES.md), branch `long-lines`) | **in progress** (19 Oct): the pre-flight limits the curve to 1–2× the line, a limit of the base network's load flow, not of the claim; on the registered criterion the claim does not hold up to 2× on this network (the conventional element misses nothing; static, Q1); δ*(k_L) and the two EMT halves pending |
| Nov–Dec 2026 | Deck scenario 3: grid-forming (needs a grid-forming inverter model in PSCAD) | open |
| — | The package for Prof. Taylor (`docs/notes/step3_for_taylor.md`) and the email (draft); his call on selectivity (T2) | **deferred** (18 Oct): the team works on its own for now; the package is kept current |
| Dec 2026 | Fall report | open |
| Jan–Apr 2027 | Step 4: latency on a board; the paper | open |
| Jun 2027 | Submit to NAPS 2027 | |

The October schedule: Oct, the injecting inverter; Nov, the small multi-bus grid and the multi-bus tool; Dec, δ
injected in EMT and the fall report; Jan–Feb 2027, step 3 and the deck's scenarios; Mar–Apr 2027, step 4 and the
paper; Jun 2027, NAPS 2027.

## 6. What Prof. Taylor asked for, and what we owe him

Both halves of the work are ours: the convex design in CVXPY and the EMT evaluation. After the
6 Oct deck he arranged the PSCAD licence and asked us to **learn PSCAD** (he does not use it) and to
**study how inverters work**. Those come first (§5).

The deck named three places his method still has room (I₂-suppressing inverters, longer lines,
grid-forming systems) and asked to test it there. The I₂ case is now **tested in EMT with δ injected**
([docs/I2_DIRECTION.md](I2_DIRECTION.md)): suppression breaks direction only on an inverter-dominated back side,
a V2-referenced current (IEEE 2800) restores it, and a designed δ certifies direction for the set test without
repairing the conventional element. The longer-line case was screened **in the static model only**, for reach on
CIGRE MV (REVIEW row 47: not supported up to 3× length); its test for detection on the three-bus grid, with the
step-3 machinery, is pre-registered and running ([docs/LONG_LINES.md](LONG_LINES.md)): the base network's load flow
limits it to 1–2× the line, and there the conventional element misses nothing (static, Q1), so on the registered
criterion the claim does not hold up to 2×; δ*(length) and the EMT halves are pending. Grid-forming is untested.

## 7. Questions for Prof. Taylor

These are the deck's four questions, in the deck's order, with what we have learned since.

1. **Reach on short lines.** Our screen finds a δ the inverter can afford barely separates in-zone
   from just-beyond faults on 2–4 Ω lines, as Theorem 1 predicts. Does that match his expectation,
   and **is there an observable — time domain, wideband — where the difference is larger?**
2. **Where to test δ next.** We offered I₂-suppressing inverters, longer lines, grid-forming systems.
   Since the deck, the first has been tested with δ injected in EMT (a grid-code question: IEEE 2800 restores
   direction, a designed δ does not repair the conventional element), the static model did not support the
   second for reach, and grid-forming is untested. Longer lines are being run next; is grid-forming the case
   he would want first?
3. **The current limit.** During a fault the inverter already runs near 1.2 pu, so δ has to fit in
   what is left. Should the limit in the design include δ, **checked phase by phase or as one
   total?** (Our own correction: the limit belongs inside the problem, not as an outer check.)
4. **The Baeckeland 14-bus Simulink model** with five grid-forming inverters. Neither IRTSD nor
   CIGRE MV has grid-forming inverters, and PSCAD does not change that.
5. Our B1 result says a suppliable δ barely moves the reach boundary on a distribution feeder, and
   that direction is settled passively. **Is the reach problem the one the method should target, or
   is the intended target fault-type separation on the relay's own line**, as in the Geometry paper?
6. Which injection regime: triggered on the limiter indicator (2022) or designed offline and injected
   continuously (2025)?
7. The negative-sequence suppression case: is a V2-referenced current (IEEE 2800) the intended
   mechanism, in which case the design question becomes gain selection rather than δ selection?
   (19 Oct: in EMT it restores direction where suppression breaks it, and a designed δ does not; REVIEW rows 57–58.)
8. Co-authorship and target venue, if this becomes a paper.

## 8. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| PSCAD edition turns out to be Free (15 nodes) | IRTSD out | Two-bus EMT model as the positive control; decide fast ([PSCAD.md](PSCAD.md)) |
| Snapshot and simulation compute | Weeks lost | Keep the case list small until one documented case is reproduced; build snapshots once |
| IRTSD has no grid-forming inverters | The hardest regime stays untested | Ask for the Baeckeland model (§7 question 4); state the limit in any claim |
| Carrying today's ladder to inverter-dominated data | Repeats the unfair-baseline error in the opposite direction | Rung R5 before that data arrives (WP3) |
| "This is just replication" | Fatal in review | The contribution is the evaluation and the map of §1, not the method |
