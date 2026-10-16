# Review of the step-3 plan (detection: Kalman filter vs a learned detector, shrinking δ)

16 Oct 2026. A critique of the draft plan sent by the research session, before any code is written. I read
`docs/PLAN.md` §2–3, Pirani, Hosseinzadeh, Taylor & Sinopoli 2022 (in full;
`papers/Pirani_Taylor_2022_…pdf`), `papers/notes/A_taylor_line.md` §1 and
`papers/notes/E_practitioner_settings.md` §7. I also read the code the plan builds on: `src/network.py`,
`src/pscad_network.py`, `src/network_delta_test.py` and `src/review/q3_inputs.py`. One number was computed
for this review; the script is in the appendix.

## Verdict in one paragraph

The plan is buildable and the compute fits in a night, but as drafted it would answer a weaker question
than the deck promises:

- **The "Kalman filter" is not Taylor's.** It moves Pirani et al.'s detector from the inverter to the
  relay, from the time domain to static phasors, and from their optimised perturbation to the zonotope
  δ. What remains is a multiple-hypothesis Gaussian test. That is a fine detector, but calling it "his
  Kalman filter" invites the first objection Taylor will raise.
- **The headline metric saturates.** At δ = 0, under the design's own worst-case noise box, only
  **3.0 %** of uniformly random three-bus faults are hard. Almost all of those are on the *adjacent*
  line, so "the smallest δ at which each detector reaches 99 %" will come out at or near δ = 0 for both
  detectors and say nothing about δ.
- **The confounds the round-1 review found would decide the result.** These are the V1-frame drift, the
  oracle angle setting, the limiter curtailment, and the fault-detection vs zone question.

The fixes are cheap. Name the detector honestly and ask Taylor before building it. Add the design's own
set test as the bridge detector. Concentrate the scenarios where δ matters, with paired runs. Model
instrument error the way it really behaves. Report separate tasks.

---

> **Follow-up (§6):** the user's questions about a set-membership-first design, and the decision to keep all
> three detectors (set test, MMKF, CNN) on the same EMT data, are answered in §6, with a second check
> (appendix B).

## 1. Is the adapted MMKF "his Kalman filter"?

**Not as drafted.** Side by side:

| | Pirani et al. 2022 | Draft plan |
|---|---|---|
| Where it runs | at the **inverter**: output y = the inverter's own dq current (eqs. 7, 9) | at the **relay** on line L1, three buses away from the inverter |
| What the modes are | the inverter's **controller structure**: healthy (voltage + current PI loops, 6 states) vs faulted (current limiter saturated, 4 states; Fig. 2) | the **network's** sequence circuit under normal or one fault hypothesis (type × location × R_f grid) |
| Dynamics | real state dynamics, discretised at 1 ms; the filters track transients | none: y = c + Hδ + Gu is static. The "states" are the uncertain sources, as random walks |
| Perturbation | **designed for the MMKF**: Δu maximises a Bhattacharyya distance φ (eqs. 22–24) under ‖Δu‖∞ ≤ γ | the **zonotope** δ of the TAC25 / Geometry design, which is optimal for a set-separation test, not for an MMKF |
| When it acts | Remark 3: the perturbation is applied **only when the current reference nears the limiter bound** | δ is injected continuously (the design's normal set N(δ) assumes it) |
| Faults | balanced three-phase only (their stated limitation) | unbalanced A-G and B-C |
| Posterior update | eq. (14): β_i·e^{−‖r‖}, the residual **norm**, not a Gaussian log-likelihood | not specified |

Four consequences:

1. **With static measurements, the Kalman filter adds nothing beyond a batch test.** With random-walk
   states and no dynamics, each mode's filter is recursive Bayesian estimation of the source values. The
   MMKF posterior is then a sequential likelihood-ratio test between Gaussian models. Process noise only
   lets the normal-mode filter slowly *absorb* a fault into drifting source estimates, which costs
   dependability. Say what it is: "a multiple-model (Bayesian) test in the phasor domain, with the
   posterior update of Pirani et al.". Better still, offer it as the probabilistic counterpart of the
   Geometry paper's set test.
2. **Remark 3 collapses under the design.** Pirani's fault indicator, and the trigger for their
   perturbation, is the inverter approaching its limit. Under the 0.90 pu design the inverter runs *at*
   its limit in normal operation: with LIM 1 it delivered I1 = 0.26–0.34 pu on the 1.2 pu limit at every
   normal corner (MULTIBUS.md, finding 4). So their trigger would be permanently on. That is worth telling
   Taylor in itself: his two lines of work conflict on this grid.
3. **A fixed-mode MMKF cannot run continuously.** Pirani starts both filters at x₀ and keeps the mode fixed
   over a horizon of N = 8 steps; the trigger of Remark 3 decides when. Run from t = 0, the normal posterior
   tends to 1 during the pre-fault period. A later fault must then overturn an arbitrarily confident prior,
   so detection time depends on how long the run was healthy. Use one of two remedies:
   - a starter (a superimposed-current step, as the relay chain already has) that resets the bank and runs
     it over a fixed horizon (the faithful choice); or
   - an interacting-multiple-model filter with mode-transition probabilities (not Pirani's).
4. **Overlapping DFT windows break the noise assumption.** A one-cycle DFT updated every quarter cycle gives
   residuals that are 75 % shared between updates. A filter that treats them as white counts the same
   information about four times over, and its posteriors are overconfident. Either:
   - use one update per cycle for the likelihood (and report decision times on the quarter-cycle grid
     separately), or
   - model the correlation (an augmented noise state).

   Also, the first cycle after inception mixes pre- and post-fault samples. *Neither* static mode fits
   there, and that is the cycle in which detection time is decided.

**What I would do.**

1. Before writing code, send Taylor a five-line description and ask whether he accepts it as the
   detector the deck promised, or would rather see something else. This is his call; it costs one email.
2. Implement two model-based detectors on the same phasor stream:
   - **D1, the set test**: the design's own relay rule, a measurement that leaves N(δ) by more than ε
     means fault (`network.noise_to_normal`, applied causally; ε, not 2ε, on noisy measurements, see §6.1). It is what the design guarantees, so it is
     the only detector against which "the design's guaranteed δ" means anything.
   - **D2, the MMKF**: Pirani's structure on the relay's measurement model, with their eq. (14) and,
     separately, the proper Gaussian likelihood e^{−½ rᵀΣ⁻¹r}, so the effect of their simplification is
     visible. Gate it with a starter.
3. Optional, but it would make the comparison Taylor's own: also compute Pirani's **φ-optimal δ** on the
   static model. With Gaussian modes, φ (eq. 23) is a closed-form function of δ; a 2-D search under
   |δ| ≤ γ suffices. Then sweep both δ families. The zonotope δ pairs with D1, the φ-optimal δ with D2.

## 2. The metric and the "smallest δ until failure" protocol

**2.1 The headline would saturate.** The appendix script draws 1500 uniform random faults. Each has a random line, type, location and R_f ∈ [0, 40] Ω, at a random
physical operating point inside the stated uncertainty. For each it computes the clean relay measurement's
distance to the design's normal set in units of ε:

| | within 2ε of N (worst-case box noise could hide it) | within 4ε |
|---|---|---|
| δ = 0, all faults | **3.0 %** | 40.1 % |
| δ = 0, L1 A-G | 0.3 % (0.6 % for R_f > 20 Ω) | |
| δ = 0, L2 A-G | 11.6 % (25.9 % for R_f > 20 Ω) | |
| δ = 0, B-C either line | 0.0 % | |
| δ = 0.90 pu | 0.0 % | 37.0 % |

So even an ideal detector facing the design's worst-case noise detects ≥ 97 % at δ = 0. Realistic noise
is not worst case. A "99 % at zero false alarms" criterion would therefore be met at the bottom of the
sweep, or decided by a handful of runs.

The design's 8 unseparated cases are worst-case **realisations** (corners of the box). Random operating
points rarely land there. That is why the design needs 0.90 pu while 97 % of random scenarios need nothing.

What to do instead:
- **Stratify, don't sample uniformly.** Put most fault runs where δ matters: A-G, R_f 20–40 Ω, and
  operating points near the box corners that the design's `closest()` witnesses point to. Report each
  stratum separately and keep a uniform stratum for the "typical" number.
- **Define failure on the hard stratum**, and report the *full curve* (detection vs |δ|, with
  confidence intervals), not only a threshold crossing.

**2.2 "Smallest δ meeting 99 %" vs "the design's guaranteed δ" is a category comparison.** The design's δ
is a worst-case guarantee: every realisation in the set, every noise in the box. A detection rate over
random scenarios with random noise is an average. A detector reaching 99 % at δ < 0.90 pu does not show the
design is conservative; reaching it only above 0.90 pu does not show the design is wrong. The comparison is
only meaningful for D1 (the set test) at the design's worst-case realisations. That is the test the step-2
runs already did (48 / 48 separated). For D2 and the CNN, report the curve, and say plainly that it is a
different quantity.

**2.3 Zero false alarms needs numbers.** With n held-out normal runs and none alarming, the 95 % upper
bound on the false-alarm rate is about 3/n: 1.5 % for 200 normals, 0.6 % for 500. PLAN.md §1 already commits
to "zero off-line false trips with binomial bounds"; carry that over. Normal data are cheap:
- Every fault run has 0.25 s of pre-fault normal operation at its own operating point (about 15 cycles at 60 Hz).
- The threshold must be fixed on a **calibration** set of normals and the rate reported on a **disjoint
  test** set. Setting the threshold on the same held-out normals that are then reported as "zero false
  alarms" is optimistic by construction.

**2.4 Use paired runs (common random numbers).** Run the *same* scenarios (operating point, fault, noise
seed) at every δ level. The curve's differences are then due to δ, not to which scenarios each level
happened to draw, and the variance of the "smallest δ" estimate drops a lot for the same 3000 runs. It also
removes a leak (§3.5).

**2.5 What "shrinking δ" means.** Scaling the 0.90 pu design at its fixed 210° angle is one choice. The
design's own optimum at a smaller margin, or at smaller ε, has a different angle (0.62 pu at 230° with no
margin). State which. Note too that the limiter (§3.4) changes the operating-point distribution with |δ|,
so δ is not the only thing that varies along the sweep.

## 3. Confounds and leaks

1. **Oracle model for the MMKF.** D1 and D2 built from `affine_case` on the very network that generates
   the data have the exact impedances, loads and source sets. The CNN must learn them. That is a legitimate
   "model-based vs learned" contrast only if stated. Add a **mismatch condition**: line impedances
   ±10 %, source impedance ±20 %, load ±20 %, as Pirani et al. did with ±10–20 % (their Figs. 9–10).
2. **The V1-frame drift (round-1 finding 3).** In EMT the inverter's I1 and δ turn by up to 29° when the
   fault starts, and in 17 / 48 runs the fault-time I1 leaves the modelled set. The fault-mode models of
   D1 and D2 (absolute I1 set, absolute δ) are then simply wrong during the fault; the CNN learns the
   drift from data. Unless this is fixed in the model, the comparison measures model error, not the
   detector. PLAN.md already names the fix: I1 and δ in the inverter's V1 frame during the fault (a
   fixed-point solve of `network.solve` with V1-referenced injections). Do it before the sweep, not after.
3. **The oracle angle setting.** `spec_with_limiter` sets D2ANG from the *delivered* state of each run.
   A real inverter cannot do that, and without it normal operation leaves the normal set (PSCAD_TAC25.md:
   ratio up to 0.80 in the first pass). A detector study must use the setting a real inverter would have:
   D2ANG fixed at commissioning, and I1 and δ referenced to the inverter's measured V1. Otherwise the normal
   data are cleaner than reality, and the false-alarm results are optimistic for every detector.
4. **The limiter curtailment (round-1 finding 4).** At 0.90 pu, I1 ≤ 0.46 pu; at intermediate δ the cut
   depends on δ's angle relative to I1. Larger δ therefore also narrows the spread of I1, which helps every
   detector. That is the mechanism by which the limit-inside design works, but the sweep must report the
   cost alongside: curtailed active and reactive power per δ level. Otherwise "δ helps detection" hides
   "δ halves the inverter's output".
5. **Train/test splits for the CNN.**
   - Group by **scenario across δ levels**. With paired runs (§2.4) the same scenario appears at every
     level, so a scenario-level split is mandatory if one model is trained across levels.
   - Train either one model per δ level or one model with δ as an input, and say which. A model trained at
     0.90 pu and tested at 0.18 pu answers a different question.
   - Keep the calibration normals out of training (§2.3).
6. **Which task (round-1 finding 12).** The hard faults at δ = 0 are almost all on the **adjacent line**
   (L2 A-G: 11.6 %, against 0.3 % on L1). A zone-1 relay at L must *not* trip for those. "Fault vs
   normal" and "in-zone vs out-of-zone" are different tasks, and the design guarantees only the first.
   Report them as two tables:
   - **T1, any fault vs no fault**: the design's framing. δ is needed almost only for L2 faults.
   - **T2, L1 fault vs everything else** (L2 faults included as negatives): the protection question. The
     design gives no guarantee here, and the deck's "detection" will be read as this by a protection
     audience.
7. **Instrument error.** "CT/VT class noise added offline" must not be white noise. The practitioner notes
   (E_practitioner_settings.md §7) give 5–10 % CT ratio error and 3–6 % VT ratio error, 2–4° VT phase error,
   during faults. These are **systematic per run and per channel** (multiplicative, constant over the run),
   not white noise. White noise averages out over a few windows and would flatter every detector, the CNN
   most.

   DESIGN.md §4.1.1 also found that with a *structured* per-channel error set at these class figures the
   two-bus design needs no signal at all. So the noise model may decide the headline by itself. Draw:
   - systematic ratio and phase errors per channel per run;
   - small white noise and quantisation;
   - a stress level at the design's ε to connect with the guarantee.
8. **Confusers outside every model.**
   - **Load steps.** `network.py` holds loads fixed: they are not in the uncertainty set, so the design
     guarantees nothing about a load step. The normal mode of D1 and D2 will flag them unless load
     uncertainty is added to the model.
   - **Unbalanced load switching.** The confuser that matters for a negative-sequence δ is an *unbalanced*
     load. `waveforms.py` calls it "THE CONFUSER". It injects its own I2 (and I0) at a remote bus. The
     PSCAD build has balanced wye loads only, so add a switched single-phase load.
   - Report false alarms per confuser type, not pooled.
9. **Fixed inception time.** `BUILD_ARGS` fixes t_fault = 0.30 s, so every fault has the same point on
   wave. That gives the same DC offset pattern and the same alignment with the DFT grid in every run, which
   a CNN can learn and a phasor filter is tuned to by accident. Randomise the inception angle. That makes
   t_fault a per-run quantity, so it must move into the **spec**, where the fingerprint sees it (round-1
   finding 11), not stay in `BUILD_ARGS`.
10. **Event index and sampling rate.**
    - The CNN input `review/q3_inputs.seq_traj` is anchored at the true event index `R["ev"]`, which is an
      oracle; anchor it on a causal starter, the same one that gates D2.
    - It hard-codes 50 Hz and 6400 Hz (`t * 6.4`, `cm.SPC = 128` at `F0 = 50`); the three-bus grid is
      60 Hz, so it needs a port.
    - The plan names `src/torch_det.py`, which is only the deterministic-torch set-up. The CNN is in
      `detect.py` / `review/q3_inputs.py`.
11. **Fault types outside the hypotheses.** The design and the planned bank cover A-G and B-C only. If the
    data contain other types (BC-G, ABC), they need hypotheses in D2, or they must be excluded from the
    headline and reported apart.
12. **One network for everything.** Design, data generator, model-based detectors and test all use one
    three-bus network with one parameter set. Whatever the result, it is "on this grid". Hold out at least
    one variation for testing only, for every detector: a stronger source, or L2 longer.

## 4. Compute plan

The arithmetic holds: 3000 runs × 10 s ≈ 8.3 h, and the detectors are cheap (about 50 static Gaussian filters at
4 updates per cycle). Four changes:

- **Spend the runs where they matter** (§2.1) and pair them (§2.4). With stratification, 5 levels × ~300
  scenarios paired probably beats 6 × 500 unpaired. Take normal windows from the pre-fault part of every
  run as well (§2.3).
- **The pilot needs go / no-go criteria, written down before it runs.**
  - (a) EMT matches the static model at the relay pre-fault (≤ 0.005 pu) with the *realistic* D2ANG
    setting (§3.3).
  - (b) The hard stratum really is hard at δ = 0: the set test D1 misses some cases.
  - (c) Both detectors run end to end on a handful of runs.
  - (d) The output fingerprint includes everything that varies (t_fault, noise seed if added in PSCAD,
    D2ANG rule).
- **Instrument error offline, yes; the inverter setting and inception time in PSCAD.** The first is cheap
  to redraw; the second and third change the run itself.
- **The fast mode's topology key** is (fault line, fault type). Random faults stay within four projects,
  plus the new confuser topologies (an unbalanced load switch is a new topology key).

## 5. Change, drop, add

**Change**
- "His Kalman filter" → "a multiple-model detector in the sense of Pirani et al., moved to the relay", and
  ask Taylor first (§1).
- The headline: from "smallest δ at 99 %" to **detection-vs-|δ| curves on the hard stratum, per task
  (T1, T2), with binomial bounds, plus the curtailment cost per level**.
- Uniform scenarios → stratified and paired.
- White "class noise" → systematic per-run ratio and phase errors plus white noise.

**Drop**
- The comparison of a statistical "smallest δ" with the design's worst-case δ for the CNN and the MMKF
  (§2.2). Keep it only for the set test.
- Random-walk process noise in the MMKF during the decision horizon (constant sources, starter-gated).

**Add**
- D1, the design's own set test, as the bridge between the guarantee and the statistics.
- The V1-frame fault model (§3.2) and a realistic D2ANG rule (§3.3), *before* the sweep.
- Unbalanced load switching as a confuser, and load uncertainty in the model or a separate confuser table.
- A model-mismatch condition and one held-out grid variation.
- Optionally, Pirani's φ-optimal δ as a second δ family for the MMKF.
- The conventional floor: a standard ground element (or the R-ladder used elsewhere in the project) on the
  same data. If it already detects the hard stratum at δ = 0, that is the result.

## 6. Follow-up: the set test as primary, and the decision to keep all three detectors

The user asked whether step 3 could be fully algorithmic, with the design's own set-membership test as the
primary detector, the MMKF second, and the CNN optional or dropped. The user has since decided: **keep all
three** and compare them on the same PSCAD EMT data with δ injected. The answers below assume that
decision. §6.1–6.3 answer the three questions about the set test; §6.4 is the CNN.

### 6.1 Is a set-test-first study better? (a)

**Yes, for the question the deck asks about δ**, and it is what Taylor would recognise:

- His design does not promise that *some* detector improves. It promises that the post-test sets become
  disjoint, and the Geometry paper proposes those sets as a relay characteristic.
- The set test is therefore the only one of the three detectors to which "the guaranteed δ" applies.
  Putting it first turns step 3 into a test of his claim, not of a detector we chose.

Two reservations:

1. **Taylor vs Taylor needs an outside reference.** With the set test and the MMKF both from his line of
   work, nothing measures what protection already achieves without δ. Keeping the CNN supplies one outside
   reference. A conventional ground element (the project's R-ladder) costs no training and is the floor a
   protection reader will ask about first.
2. **Keeping the CNN is right only if its question is stated.** Its most informative role is the
   counterfactual: *is the information δ is meant to create already in the waveforms at δ = 0?* If a
   learned detector reaches the target on the hard stratum at δ = 0 while the set test needs 0.90 pu,
   that is a headline in its own right. Say so in the one sentence to Taylor.

**One correction to the proposal as written: the relay threshold is 1, not 2.**
- The "ratio > 2" rule used in the EMT tests applies to **clean** measurements. It tests whether the two
  sets are separated, since both measurements carry up to ε of noise.
- A relay sees **noisy** measurements. The rule that carries the guarantee is: alarm iff the distance from
  y to N(δ) exceeds ε.
  - A normal measurement is within ε of N by assumption, so it never alarms.
  - A fault the design separates is more than 2ε from N, so with its own noise it stays more than ε away
    and always alarms.
- With threshold 2 on noisy data, a separated fault whose clean distance lies between 2ε and 3ε can be
  missed. Report the guaranteed rule (threshold 1). Any other threshold is a tuned operating point, to be
  calibrated like the other detectors' thresholds (§6.4).

Two properties of the set test worth stating up front:
- **It is a one-class detector.** At run time it needs only N(δ); the fault sets enter only at design time.
  It therefore detects fault types the design never modelled (BC-G, ABC) if they leave N, and it false-
  alarms on any normal behaviour the model left out. Its false-alarm side is the crux (§6.2).
- **It is cheap enough for step 4.** One small LP (12 equalities, about 30 variables) per update.
  Alternatively, N(δ) ⊕ ε can be precomputed offline as a table of halfspaces, which turns the test into a
  matrix-vector product.

### 6.2 Is it fair to evaluate the set test on data from the same model family? What confounds? (b)

**Inside its assumptions the result is a tautology.** If sources stay in the set, noise stays in the box,
the network and loads are as modelled, the limiter is LIM 1 and δ is delivered as designed, then the set
test cannot false-alarm. It also cannot miss a fault the design separated. Data generated inside those
assumptions can only confirm that. Everything informative is in the **violations**, so the evaluation
should be built around them.

[Appendix B](#appendix-b-set-test-false-alarms-under-violated-assumptions) measures the normal side on the
static three-bus model. It applies 300 random normal operating points per row, at δ = 0 and at the 0.90 pu
design (inverter cut by LIM 1). An alarm means the clean measurement is already more than ε from N, before
any noise:

| assumption broken | alarm, δ = 0 | alarm, δ = 0.90 pu | largest distance (ε) |
|---|---|---|---|
| none (inside the box) | 0 % | 0 % | 0.00 |
| box 1.5× wider (EMF ±7.5 %, I1 ±0.45 pu, ±0.45 rad) | 0.3 % | 0 % | 1.12 / 0.84 |
| box 2× wider | **23.7 %** | **9.3 %** | 2.67 / 1.80 |
| balanced load at S ×1.2, ×1.5; at R ×0.5 | 0 % | 0 % | ≤ 0.91 |
| unbalanced load at S, extra I2 = 0.05 pu | 0 % | 0 % | 0.45 |
| unbalanced load at S, extra I2 = 0.15 pu | **94 %** | **92 %** | 1.36 |
| CT/VT near nominal (VT 0.5 %, 0.3°; CT 1 %, 1°) | 0 % | 0 % | ≤ 0.16 |
| CT/VT at fault-condition figures (VT 6 %, 4°; CT 10 %, 1°) | 0 % | 0 % | **≤ 0.82** |

What it says:
- **ε = 0.08 pu is generous.** It absorbs ±50 % balanced load changes and a 1.5× wider source box. That is
  also why 97 % of random faults are already separated at δ = 0 (§2.1).
- **The real false-alarm risk is a negative-sequence confuser.** An unbalanced load injecting 0.15 pu of
  I2 at a remote bus alarms almost every time. This is exactly the confuser a negative-sequence δ is up
  against, and exactly the one the PSCAD build lacks (§3.8). It must be in the data.
- **Systematic instrument error uses up the noise budget.** At fault-condition figures it consumes up to
  82 % of ε before any white noise. The remaining 18 % then decides false alarms. So the noise model
  (§3.7) is not a detail.
- **The fault side is not in this table but matters as much.**
  - The V1-frame drift (§3.2) moves fault measurements in a way the design ignores.
  - The first-cycle DFT transient produces measurements that belong to no static state. That can make
    switching events look like faults, and it sets the detection time.

Guards, in one design: **build in the design world, test in the real one.**
- **The design world** is the box, the fault ranges, the modelled loads, LIM 1, instrument error within
  ε. All three detectors are *constructed* from it:
  - the set test from N(δ);
  - the MMKF from the same affine model;
  - the CNN *trained* on runs drawn from the same distribution.
- **The test set** contains the design world plus a **violation matrix**, each axis at two or three
  strengths. Each strength is held out from every detector's construction and calibration:
  - box inflation;
  - load steps;
  - unbalanced load switching;
  - systematic CT/VT error at fault-condition figures;
  - line and source impedance error of ±10–20 %;
  - fault types outside the design (BC-G, ABC);
  - continuous (m, R_f) between the design's grid points (H13);
  - the realistic D2ANG rule (§3.3);
  - LIM 0.
- Report each detector's dependability and false alarms **per axis**. The set test should break first on
  the false-alarm side, the CNN wherever training did not reach, and the MMKF somewhere in between. Where
  each breaks is the result.
- **Avoid circularity in the strata.** §2.1's "hard" stratum is defined by the set test's own distance.
  Also report a stratum defined physically (A-G, R_f > 20 Ω, near the box corners), so the set test is not
  graded only where its own metric says the problem is hard.

### 6.3 "Shrink δ until it fails" for a detector whose guarantee is binary (c)

The guarantee is binary for a given (model, ε, set, fault grid); its *margin* is not. Use three measures,
each defined in advance:

1. **Binary against binary, at the worst case.** At each |δ| on a fine grid (0.02 pu, the design tool's
   step), with the angle re-optimised at that magnitude:
   - the design tool says separated or not, and names the cases that fail;
   - in EMT, run the design's own witnesses (`closest()` at that δ) plus the box corners.

   Define δ*_EMT as the smallest |δ| at which every witness is separated in EMT (clean ratio > 2), and
   compare it with the tool's δ*. Equal within a grid step means the guarantee is tight in EMT. Below δ*
   means the design is conservative there; above means the guarantee fails in EMT. This needs only about
   50 runs per δ point, so it can afford a fine δ grid near δ*.
2. **The margin curve.** The worst witness margin, min over cases of (distance/ε − 2), as a function of
   |δ|, both in EMT and in the static model. It is continuous, so its zero crossing locates δ*_EMT more
   precisely than the run grid. The gap between the two curves *is* the model error at the worst case.
3. **The population curve.** The set test at threshold 1 on the stratified random population with
   realistic noise (§2, §3.7):
   - dependability and false alarms vs |δ|, with binomial bounds;
   - "fails" defined in advance as dependability on the hard stratum below the target at zero false alarms
     on the calibration normals.

   Below δ* the guarantee is gone but most cases still pass. Report the fraction that do. That fraction is
   the honest "how much the worst case over-states the need".

Two rules for every level:
- The relay knows δ, so **N(δ) and the limit rows are rebuilt for each level**. False alarms must be
  re-measured per level, because curtailment and the frame change with δ.
- Add the **ε axis**. Realistic noise is below the design's ε, and the design at a smaller ε needs a
  smaller δ. The natural "shrink" for the set test is the frontier δ*(ε) in the (δ, ε) plane, which the
  tool computes; EMT then checks points on and just below it.

The MMKF and the CNN have no guarantee, so for them only the population curve (measure 3) applies.

### 6.4 The CNN, kept

**Fairness against two detectors built from the model.** The set test and the MMKF are given the exact
model at zero PSCAD runs. The CNN learns from runs. Make both kinds of cost visible:

- **Same information.** Train the CNN on the *design world* distribution only (§6.2), the same world the
  model-based detectors are built from, and test all three on the same test set with the violation matrix.
  A CNN trained on violations would be given data the others were not.
- **Same front end.** Use the same causal, starter-anchored, one-cycle-DFT phasor trajectory for all
  three, or report the CNN on raw samples separately. Otherwise front end and detector are confounded.
  That also means porting `seq_traj` to 60 Hz and to a starter anchor (§3.10).
- **A model-trained CNN as a second variant.** Train it on waveforms synthesised from `network.solve`
  (as `waveforms.py` does for the two-bus model), with zero PSCAD runs. It has exactly the information the
  model-based detectors have. The gap between it and the EMT-trained CNN measures what EMT adds; the gap
  between it and the set test measures learning vs geometry on equal information.
- **What counts as a real advantage.** The CNN *can* learn the V1-frame drift and the DFT transient, which
  the model-based detectors get wrong unless modelled (§3.2). It *must not* be able to learn simulator
  artefacts. Randomise the inception angle and the window alignment (§3.9), and record which runs the CNN
  saw.

**Splits and grouping.**
- **The group is the scenario**: one operating-point draw plus one fault (or normal) draw. All its runs
  belong to one group: every δ level of a paired scenario (§2.4), every decision window, and the normal
  windows taken from its pre-fault part. Use grouped k-fold CV over scenarios, as the project already does
  on EvEMTBench (sibling leakage).
- **Three disjoint parts per fold: train / calibrate / test.** The zero-false-alarm threshold is fixed on
  the calibration part and reported on the test part. Calibration normals come from runs, not windows, the
  CNN never saw.
- **Violation scenarios appear only in test folds.**

**One CNN per δ level or one across levels?** These are two questions:
- **Primary: one CNN per level, trained and tested at that δ.** This matches the deployed relay, which runs
  at one designed δ, and it matches the model-based detectors, which are rebuilt per level.
- **Secondary: one CNN across levels with δ as an input**, grouped by scenario across levels. This is
  data-efficient and shows whether one network generalises along δ. It is a different question.
- Never train at 0.90 pu and test at smaller δ as the headline.
- **A δ = 0 CNN is required in either case.** It is the counterfactual of §6.1.

**Class balance and the zero-false-alarm threshold.**
- Faults are cheap to oversample, and should be: the hard stratum for dependability, plus the uniform
  stratum for the typical figure.
- The zero-false-alarm threshold is set by the *tail* of the negatives, so the negatives need diversity
  more than balance:
  - normal operation across the box;
  - load steps and unbalanced switching;
  - for task T2, out-of-zone L2 faults.
- Use class weights in the loss rather than discarding normals.
- Calibrate all three detectors the same way: threshold = the largest score over the calibration
  negatives. For the set test, report both that calibrated threshold and the theoretical one (distance
  > ε).
- Report the false-alarm bound (≈ 3/n for n clean calibration normals) next to every "zero".

**How much data the CNN needs.** The project's own evidence (adapt_grid, `results/adaptgrid/`):
- With about 170–210 in-zone positives and about 2850 negatives per relay, the CNN covered 94.6–99.4 % of
  in-zone faults at relay A with 0–3 of 2888 off-line trips, and was unstable at relay B (45–77 %; README).
- In `subsample_relayfe_cnn.json`, with 72 positives, relay A held at 0.99–1.00 while relay B ranged
  0.41–0.90 across three draws.
- In `learning_curve_relayfe_cnn.json` (about 2440 training records per fold), dependability at zero false
  trips swings from epoch to epoch (relay B: 0.98 → 0.30 → 0.98).

The plan's ~500 runs per level contain perhaps 350 fault runs. With stratification perhaps 150 are hard,
so about 120 per training fold: **the regime in which that CNN was unstable**. Recommendations:
- **Measure before committing.** A learning curve on the pilot: train on 25 / 50 / 100 % of the pilot's
  scenarios and watch dependability and its spread across seeds.
- **Get more training examples per run.** Several decision windows per fault run and many normal windows
  per run, all grouped by run.
- **Pretrain on the model-generated synthetic data** (unlimited and free), then fine-tune on EMT.
- **Spend PSCAD runs where the CNN needs them.** About 1000–1500 runs at the levels that decide the
  headline (δ = 0, near δ*, the design value), fewer elsewhere. Paired scenarios serve every per-level model.
- **Several seeds.** At least five, with the spread reported. The project already found that one seed's
  zero-false-trip number does not reproduce (`torch_det.py`).

## Not checked

- No code was written or run beyond the hardness check above. Its 3 % assumes the design's noise box ε
  and the outer-box limit rows. It uses the static model, not EMT, so it ignores the fault-time drift
  (§3.2).
- Pirani et al.'s results were not reproduced; the comparison table is from their text.
- PSCAD fast-mode speed (~10 s per run) is the research session's figure, not measured here.
- Whether the deck's "under load" meant load steps or load level; I treated it as confusers.
- Appendix B is static-model only: no EMT transients, no V1-frame drift, and the unbalanced load is modelled as a
  pure negative-sequence injection at bus S (no zero sequence, no change of positive-sequence load). The
  CT/VT draws are uniform per phase within the stated bounds, applied in normal operation (pessimistic: the
  fault-condition figures are for faults).
- The CNN data figures in §6.4 are from adapt_grid (50 Hz, a different grid and task); they indicate the regime,
  not the number of runs this grid needs.

## Appendix A: the hardness check

Save as `review/checks/check_step3_hardness.py` (its paths assume that place) and run it on main at `e5f0085`
(1500 draws, a few minutes); it prints the §2.1 table.

```python
"""Step-3 plan review: how many uniformly random three-bus fault scenarios are hard at all?

For random faults (line L1 or L2, type A-G or B-C, location uniform, R_f uniform on [0, 40] ohm) at random
physical operating points (|e| within +-5 %, angle +-5 deg; inverter |i| within +-0.3 pu, angle +-0.3 rad), the
clean relay measurement's distance to the design's normal set, in units of eps (network.noise_to_normal):
ratio <= 2 means worst-case box noise of eps could make it look normal. Printed at delta = 0 and at the design
delta (0.90 pu at 210 deg, limit inside, inverter current cut by the delta-priority limiter as in EMT).

    python review/checks/check_step3_hardness.py [n]
"""
import os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(ROOT, "src", "review"))
import network as nw  # noqa: E402
from network_delta_test import model  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
rng = np.random.default_rng(3)
net, ms = model()
sg, ibr = net.sgs["G"], net.ibrs["I"]
D = 0.9 * np.exp(1j * np.radians(210))
for dv in (0j, D):
    lim = nw.limit_rows(ms, "I", dv)
    rows = []
    for _ in range(n):
        e = sg.e0 * (1 + sg.gen[0] * rng.uniform(-1, 1)) * np.exp(1j * sg.gen[1] * rng.uniform(-1, 1))
        i1 = (abs(ibr.i0) + ibr.gen[0] * rng.uniform(-1, 1)) * np.exp(1j * (np.angle(ibr.i0) + ibr.gen[1] * rng.uniform(-1, 1)))
        i1, d = nw.limiter(i1, dv, ibr.i_max, 1) if abs(dv) else (i1, 0j)
        line = rng.choice(["L1", "L2"])
        scen = rng.choice(["ag", "ab"])
        m = rng.uniform(0.02, 0.98)
        rf = rng.uniform(0, 1.0) * net.rF
        y = nw.solve(net, {"G": e, "I": i1}, {"I": d} if abs(dv) else {}, (line, m, scen, rf))
        rows.append((line, scen, rf, nw.noise_to_normal(ms, y, dv, lim) / net.eps))
    r = np.array([q[3] for q in rows])
    hard = r <= 2
    lab = "delta = 0" if not abs(dv) else "design delta 0.90 pu"
    print(f"{lab}: {hard.sum()} of {n} random faults within 2 eps of the normal set ({100 * hard.mean():.1f} %); "
          f"within 4 eps {100 * (r <= 4).mean():.1f} %; median ratio {np.median(r):.1f}")
    for ln in ("L1", "L2"):
        for sc in ("ag", "ab"):
            sel = [k for k, q in enumerate(rows) if q[0] == ln and q[1] == sc]
            hr = [k for k in sel if rows[k][2] > 0.5 * net.rF]
            print(f"   {ln} {sc}: {100 * hard[sel].mean():5.1f} % hard; with R_f > 20 ohm {100 * hard[hr].mean():5.1f} % hard")
```

## Appendix B: set-test false alarms under violated assumptions

Save as `review/checks/check_step3_settest_fa.py` and run on main at `e5f0085` (300 draws per row, about 10
minutes); it prints the §6.2 table.

```python
"""Step-3 plan review, set-membership detector: how often does NORMAL operation leave N(delta) + eps when one of
the test's assumptions is broken? Static three-bus model (network.py), relay at L; clean measurements, so a
ratio > 1 (distance to N in units of eps) is an alarm before any noise is added, and > 2 a certain alarm.

    python review/checks/check_step3_settest_fa.py [n]
"""
import os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(ROOT, "src", "review"))
import network as nw  # noqa: E402
from network_delta_test import model  # noqa: E402

A = np.exp(2j * np.pi / 3)
T = np.array([[1, 1, 1], [1, A * A, A], [1, A, A * A]])       # [x0, x1, x2] -> abc
Ti = np.linalg.inv(T)
n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
rng = np.random.default_rng(11)
net, ms = model()
sg, ibr = net.sgs["G"], net.ibrs["I"]


def draw(k=1.0):
    e = sg.e0 * (1 + k * sg.gen[0] * rng.uniform(-1, 1)) * np.exp(1j * k * sg.gen[1] * rng.uniform(-1, 1))
    i1 = (abs(ibr.i0) + k * ibr.gen[0] * rng.uniform(-1, 1)) * np.exp(1j * (np.angle(ibr.i0) + k * ibr.gen[1] * rng.uniform(-1, 1)))
    return e, i1


def instrument(y, vr, vp, cr, cp):
    """Per-phase multiplicative ratio / phase errors (drawn per run) on V and I, back to sequence order."""
    v = T @ np.array([y[2], y[0], y[1]]); i = T @ np.array([y[5], y[3], y[4]])
    gv = (1 + rng.uniform(-vr, vr, 3)) * np.exp(1j * np.radians(rng.uniform(-vp, vp, 3)))
    gi = (1 + rng.uniform(-cr, cr, 3)) * np.exp(1j * np.radians(rng.uniform(-cp, cp, 3)))
    vs, is_ = Ti @ (gv * v), Ti @ (gi * i)
    return np.array([vs[1], vs[2], vs[0], is_[1], is_[2], is_[0]])


CASES = [
    ("inside the box (the design's assumption)", dict()),
    ("box 1.5x wider (EMF +-7.5 %, I1 +-0.45 pu, +-0.45 rad)", dict(k=1.5)),
    ("box 2x wider", dict(k=2.0)),
    ("load at S x1.2 (balanced)", dict(load=("S", 1.2))),
    ("load at S x1.5", dict(load=("S", 1.5))),
    ("load at R x0.5", dict(load=("R", 0.5))),
    ("unbalanced load at S: extra I2 0.05 pu", dict(unbal=0.05)),
    ("unbalanced load at S: extra I2 0.15 pu", dict(unbal=0.15)),
    ("CT/VT near nominal (VT 0.5 %, 0.3 deg; CT 1 %, 1 deg)", dict(inst=(0.005, 0.3, 0.01, 1.0))),
    ("CT/VT at fault-condition figures (VT 6 %, 4 deg; CT 10 %, 1 deg)", dict(inst=(0.06, 4.0, 0.10, 1.0))),
]
for dv in (0j, 0.9 * np.exp(1j * np.radians(210))):
    lim = nw.limit_rows(ms, "I", dv)
    print(f"--- delta = {abs(dv):.2f} pu ---")
    for lab, c in CASES:
        r = []
        for _ in range(n):
            e, i1 = draw(c.get("k", 1.0))
            d = 0j
            if abs(dv):
                i1, d = nw.limiter(i1, dv, ibr.i_max, 1)
            loads = {b: dict(y) for b, y in net.loads.items()}
            if "load" in c:
                b, f = c["load"]; loads[b] = {s: f * v for s, v in loads[b].items()}
            ibrs = dict(net.ibrs)
            vals, dl = {"G": e, "I": i1}, ({"I": d} if abs(dv) else {})
            if "unbal" in c:
                ibrs["U"] = nw.IBR("S", 0j)
                dl = {**dl, "U": c["unbal"] * np.exp(1j * rng.uniform(0, 2 * np.pi))}
                vals["U"] = 0j
            m = nw.Network(net.lines, net.sgs, ibrs, loads, net.relay, net.eps, net.rF)
            y = nw.solve(m, vals, dl)
            if "inst" in c:
                y = instrument(y, *c["inst"])
            r.append(nw.noise_to_normal(ms, y, dv, lim) / net.eps)
        r = np.array(r)
        print(f"  {lab:62s} alarm (>1) {100 * (r > 1).mean():5.1f} %   certain (>2) {100 * (r > 2).mean():5.1f} %   max {r.max():.2f}")
```
