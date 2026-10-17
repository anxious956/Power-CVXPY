# Step 3 plan: detectors on EMT data with the designed signal injected

16 Oct 2026. Step 3 of the deck presented to Prof. Taylor: *"Detection, under load and noise: your Kalman
filter against a learned detector, shrinking δ until each fails."* The draft plan was reviewed before any code
([review/STEP3_PLAN_REVIEW.md](../review/STEP3_PLAN_REVIEW.md)); this is the plan after that review. Every
change from the draft is marked with the review section that asked for it.

## Detectors

| | What | Why |
|---|---|---|
| **D1, the set test** | the design's own relay rule: alarm when the measurement leaves N(δ) by more than 2ε (`network.noise_to_normal`), applied causally on the phasor stream | the only detector the design's guarantee is about (§2.2); Taylor's Geometry paper proposes these sets as "a new kind of relay characteristic" |
| **D2, multiple-model detector** | in the sense of Pirani, Hosseinzadeh, Taylor & Sinopoli 2022, **moved to the relay**: one filter per hypothesis (normal; A-G and B-C over a location × R_f grid) on the measurement model, mode posteriors by their eq. (14), and separately by the Gaussian likelihood; gated by a causal starter, fixed horizon, one likelihood update per cycle | not called "his Kalman filter": his runs at the inverter on the controller's states, with a perturbation designed for it (§1). Described to him as an adaptation, and asked first |
| **D3, the learned detector** | the sequence-trajectory CNN (`review/q3_inputs.py`), ported to 60 Hz, anchored on the same causal starter, one model per δ level, grouped by scenario | the deck's "learned detector" (§3.5, §3.10) |
| **D0, the conventional floor** | a standard ground / distance element from the project's ladder on the same data | if it already detects the hard cases at δ = 0, that is the result (§5) |

## Data

PSCAD three-bus network (`src/pscad_network.py`, fast mode), δ-priority limiter. Changes from the draft:

- **Stratified, paired scenarios** (§2.1, §2.4). Most fault runs go where δ matters: A-G, R_f 20–40 Ω, operating
  points near the box corners the design's witnesses point to. A uniform stratum is kept for the typical
  number. The same scenarios (operating point, fault, noise seed) are run at every δ level.
- **A realistic inverter** (§3.2, §3.3): I1 and δ referenced to the inverter's measured V1, with ID, IQ, D2MAG
  and D2ANG fixed at commissioning, not set per run from the delivered state.
- **A random inception angle** (§3.9): t_fault becomes a per-run spec field, inside the fingerprint.
- **Confusers** (§3.8): balanced load steps and a switched single-phase load, with false alarms reported per
  confuser type.
- **Instrument error** (§3.7), drawn offline: systematic per-run, per-channel CT ratio error 5–10 % and VT
  ratio error 3–6 %, VT phase error 2–4°, plus small white noise and quantisation; and a stress level at the
  design's ε.
- **Normal data** from the pre-fault part of every run, plus dedicated normal runs. Calibration normals are
  kept disjoint from test normals (§2.3).
- **Mismatch and held-out variation** (§3.1, §3.12): detectors built with line ±10 %, source ±20 % and load
  ±20 % errors, and one grid variation (a longer L2) used only for testing.

## Tasks and metrics

- **T1, any fault vs no fault** (the design's framing) and **T2, L1 fault vs everything else** (the protection
  question; L2 faults are negatives) (§3.6).
- **Curves**, not a threshold crossing: detection rate on the hard stratum against |δ|, with binomial bounds,
  at a false-alarm rate bounded on disjoint test normals (§2.1–2.3).
- **The cost**: the inverter's curtailed active and reactive output per δ level (§3.4).
- **"Shrinking δ"**: the design's δ scaled at its fixed angle; stated as such (§2.5).
- The design's worst-case δ is compared only with D1 at the worst-case realisations (§2.2).
- Headline restricted to A-G and B-C, the hypotheses the design and D2 cover (§3.11).

## Before the sweep: the two frames (§3.2, §6; agreed with the reviewer, 16 Oct 2026)

**The inverter frame.** A real inverter injects I1 = (ID − jIQ)·u and δ = D2MAG·e^{jD2ANG}·u, u = V1_R/|V1_R|, with
the settings fixed at commissioning. The relay frame has the same problem: the relay references its phasors to its
own pre-fault V1_L memory, not to an absolute frame (the E1-based frame used so far is an oracle).

- **(A), the generator.** `network.solve_v1ref`: the exact fixed point of the V1-referenced injections. Checked
  against the 96 stored three-bus EMT fault runs at 0.38 s: |EMT − model| at the relay median 0.0023 pu, max
  0.030 pu, against 0.027 / 0.177 pu for the design's absolute-injection model. It generates the data and is the
  reference the sets are checked against.
- **(B), the design and D1.** The frame rotation is bounded uncertainty in the affine model, with a **shared
  rotation symbol**: ρ = c_Φ + g_r·w1 + j·g_t·w2 multiplies every quantity referenced to V1_R (δ exactly; I1 to
  first order, the cross term G_I u_I (ρ − c_Φ) boxed separately). Before the fault the rotation is linearised in
  the source symbols themselves (it is caused by the source realisation); the relay frame gets the same treatment,
  frozen at pre-fault memory during the fault. Consequences, stated rather than hidden:
  - the design is no longer convex in δ: the polar grid stays exact (each LP at a fixed δ is), but the polygon,
    exact-minimum and certificate tools do not apply, and separation may not be monotone in |δ|;
  - the rotation bound Φ depends on δ and is computed per candidate δ (or bounded uniformly over the search range);
  - Φ comes from (A) on dense interior points and the box corners, called "verified by (A)", not proved; the
    sector spans the inverter's DFT lag through the relay window ([0, Φ_case]) plus the EMT drift margin;
  - cases where |V1_R| → 0 (bolted faults at or next to R) leave the frame undefined: δ's angle carries nothing
    there, and they get a full circle or are excluded, explicitly.
- **Containment check before any sweep**: every (A) realisation (normal and fault, continuous m and R_f between
  the grid points, through the transient window) lies in the (B) set with zero noise; then the same on EMT
  phasors. Measure what the shared symbol buys: δ* with independent boxes vs the shared symbol.

## The main design configuration (review of PR #44, rounds 1–2)

The result is the curve of δ* against the relay reference's rotation budget and the model-error box
(`src/frames_budget.py`, `results/network/frames_budget.json`). The detectors need one N(δ), from
`src/frames_main.py`, with every parameter labelled:

| parameter | value | label |
|---|---|---|
| reference rotation φ_ref | k·σ_white / (√n_mem · min\|V1_L\|), k = 4, σ_white = 0.01 pu, n_mem = 3 cycles | k and σ chosen (the generator's random-noise model); n_mem from the relay memory |
| model-error box | 0.1 ε | **provisional**: measured on random interior source points at 225° (`src/frames_emt_check.py`, 168 runs), EMT points outside their own set by ≤ 0.073 ε; no A-G case at 1.00 / 1.05 pu. The earlier 0.25 ε was the distance to the settled point, which the frame symbols already cover. To be confirmed at the design point's witnesses (review/STEP3_PART3_REVIEW.md §5) |
| largest \|δ\| | 1.05 pu | measured at 225° on ab faults, inside the 2–3-cycle window, for this controller (one-cycle DFT reference, no PLL): at 1.14 pu it does not settle on bolted ab faults; at 1.05 pu 3 of 8 bolted ab runs drift up to 21° after 3 cycles |
| drift margin | 3° | measured (≤ 2.2° in that window) |
| decision window | [2, 3] cycles after inception | chosen |
| margin ρ | 0.04 | chosen for feasibility: at ρ = 0.1 no δ ≤ 1.05 pu separates; at 1.05 pu, 225° the largest is 0.05. Total margin 0.08 ε against 0.073 ε seen outside the sets; remainder factor 1.1 is further headroom |
| **design point** | **δ = 1.12 pu at 225°, ρ = 0.1, PLL-like reference filter (first order, 15 Hz)** | about 93 % of the inverter's rating. Window 223–230°; `results/network/frames_main_pll.json`. The bare-DFT design (1.05 pu, ρ 0.04, `frames_main_fixed.json`) is kept as the controller-specific result |
| D1's phasor chain | one-cycle DFT with a mimic filter on the currents (L1's X/R) | the window-start excursions are DC offset (`src/frames_mimic_check.py`); faults inside and outside the design ranges reported separately |

The guarantee is then **worst case over the sources, k-σ over the random noise**; the systematic VT phase error is in
the violation matrix.

**D1 cannot hold its guarantee inside one cycle on this model.** One cycle after inception the inverter's own DFT is
still turning (28.7° beyond the fixed point) and the DC and network transients are not over: |EMT − model| reaches
1.33 ε. It falls to 0.17–0.23 ε at 2–3 cycles. A guarantee from 2 cycles is slower than step 4's "within one cycle";
that is a stated result, and a fair place for D2 and D3, which carry no guarantee, to decide earlier.
D1 decides only on windows wholly after the starter's inception estimate; mixed windows belong to no set.

## Further decisions (§6 of the review)

- **D1's threshold on noisy data is distance > ε**, not the ratio > 2 used on clean EMT measurements.
- **The noise box ε is defined in the relay's own frame** (V1_L at 0°); the reference's own noise then rotates the
  whole vector by at most ε/|V1_L|, a shared symbol in the sets. A systematic VT phase error is different (it turns
  voltages and reference, not currents: a relative V–I error of 0.035–0.07 rad × |i|) and is tested in the
  violation matrix with the other class errors, not hidden in ε.
- **A violation matrix** for the false-alarm side, held out from every detector: unbalanced load (0.15 pu I2
  alarms D1 92–94 % in the static model), a wider box, balanced load ±50 %, CT/VT error at fault-condition
  figures (up to 82 % of ε already). A physically defined hard stratum is reported next to D1's own.
- **Three measures of "shrinking δ"**: binary at the design's witnesses (δ*_EMT vs δ* on a 0.02 pu grid, ~50 runs
  per point); the worst-witness margin curve; the population curve with binomial bounds. N(δ) is rebuilt per level;
  the δ*(ε) frontier is added.
- **The CNN**: trained in the design world only, with the same front end (60 Hz port, starter anchor); a second CNN
  trained on `network.solve` synthesised waveforms (no PSCAD runs, the same information as D1 and D2); grouped by
  scenario across δ levels and windows; train / calibrate / test disjoint; one CNN per level plus a δ = 0 CNN;
  all detectors calibrated identically (largest calibration-negative score, ~3/n bound); a learning curve on the
  pilot, pretraining on synthetic data, more windows per run, 1000–1500 runs at the deciding levels, ≥ 5 seeds.
- **D0**, a conventional ground element, as the training-free floor; the CNN's stated role is the δ = 0
  counterfactual.
- **Ask Taylor first** about D2 (draft email in this repository, sent by the user).

## The front end and the noise model (review/STEP3_PART5_REVIEW.md, verdict of 17 Oct 2026)

Every detector reads the relay through one front end (`src/step3_frontend.py`):

1. Instrument errors are applied to the **sampled waveforms**: systematic per-run, per-channel CT and VT ratio
   errors and a VT phase error, plus white noise.
2. Resample to 128 samples per cycle.
3. A **mimic filter on the currents** with τ fixed by L1's X/R (1.59 cycles). It is a relay setting, the same for
   every detector, including the CNN's seq_traj.
4. One-cycle sequence phasors in the relay's memory frame. The frame is the pre-fault V1_L averaged over 3 cycles
   before the starter's inception estimate.

The mimic filter amplifies white noise on the current phasors: variance ×7.4, std ×2.7 (reviewer's figure, checked by
Monte Carlo in the front end). Systematic CT errors pass through it unchanged. Three consequences:
- the white noise is added before the mimic filter, never at phasor level;
- the noise levels are set by their **post-filter** phasor standard deviation;
- D2's likelihood uses the post-filter current covariance, including the correlation between overlapping windows.

Noise tiers:

| tier | white noise, post-filter phasor std | systematic | role |
|---|---|---|---|
| clean | none | none | consistency with the design check |
| design | currents 0.01 pu, voltages 0.005 pu | CT ratio ±1 %, VT ratio ±0.5 %, VT phase ±0.3° | inside the ε box at k = 4: D1's guarantee applies |
| class | as design | CT 5–10 %, VT 3–6 %, VT phase 2–4° (the §3.7 figures) | the violation matrix; no guarantee |

D1's threshold is distance > ε on noisy data. The design tier must fit the ε box: k·σ plus the largest systematic
term ≤ ε on every real component. The pilot checks this on the measured fault currents.

## Pilot go / no-go, written before it runs (17 Oct 2026)

Pilot: about 100 runs, `src/step3_data.py pilot`. There are 16 fault scenarios and 4 normal or confuser scenarios,
each run at 5 δ levels: 0, ¼, ½, ¾ and 1 × the design δ (1.12 pu at 225°). Every run uses the filtered reference.

- (a) **Static model before the fault.** EMT matches the V1-referenced model at the relay before the fault
  (≤ 0.005 pu) on every pilot run.
- (b) **The hard stratum is hard at δ = 0.** D1 misses at least a quarter of the hard in-range faults at δ = 0, and
  so does D0.
- (c) **The design holds on clean pilot data.** At the design δ with the clean tier, D1 detects every in-range fault
  in the 2–3-cycle window and alarms on no normal run. Confusers are reported, not counted.
- (d) **End to end.** D1, D2, D3 and D0 run end to end on the pilot. Every detector reads the same front end and
  is calibrated the same way.
- (e) **Noise budget.** On the pilot's fault currents the design tier fits the ε box at k = 4 after the mimic filter.
  If it does not, the design tier's white noise is reduced until it does, and that is stated.
- (f) **Fingerprint.** It covers everything that varies: t_fault, TANG, the inverter settings, the confusers and
  dur / t_end.

No sweep until all six hold. Faults inside and outside the design ranges are reported separately throughout.

## Compute

Five δ levels × ~300 paired scenarios, plus normals and confusers, and 1000–1500 runs at the levels that decide the
headline: about 3000–4000 PSCAD runs, one to two nights in fast mode.
