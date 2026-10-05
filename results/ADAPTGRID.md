# adapt_grid-TestGrid110kV: does anything survive a varying operating point?

17 Sep 2026; every CNN number re-run deterministically on 27 Sep 2026 (§4, "Determinism and training
stability"). Code: `src/review/adaptgrid_run.py` (comparisons), `src/review/adaptgrid_facts.py` (fact
sheet), `src/review/adaptgrid_tables.py` (tables). Numbers: `results/adaptgrid/<relay>_<frontend>.json`,
[`ADAPTGRID_FACTS.json`](ADAPTGRID_FACTS.json). Tables: [`adaptgrid/TABLES.md`](adaptgrid/TABLES.md),
generated — no number in this document is typed by hand; each is cited to a table row or a JSON key.

The benchmark set that every result in [REVIEW.md](../REVIEW.md) rests on has **one operating point per
grid** (H23). This set is the same TestGrid110kV grid with randomised events and randomised operating
states, and it is the first data on which the review's conclusions can be tested against a varying
operating point. §4 answers the five questions the brief asked; §5 states what this family of data
cannot test at all.

---

## 1. The data

`D:\evemt\adapt_grid-TestGrid110kV.tar.gz`, 35,176,708,302 bytes, streamed once by `evemt.build_cache_disk`
(never unpacked) into `data/adapt_grid-TestGrid110kV_cache.bin`: **9,739 simulations**, 7 of the grid's
25 cubicles (the benchmark cache's same set: 2 relays, 3 line ends, 2 IBRs, i.e. 28 % of the grid; a
full-grid cache would be ~18.7 GB), **5.24 GB**, **2,020 s** to build, 1.9 s to load. The cache is
self-contained (waveforms, labels, grid graph), so for the two relays used here the archive is not
needed again; it is kept on D: only in case another cubicle is ever wanted.

## 2. Fact sheet — what changes against the benchmark set

Full sheet: [`ADAPTGRID_FACTS.md`](ADAPTGRID_FACTS.md). The points that decide the protocol:

| | benchmark TestGrid110kV | adapt_grid-TestGrid110kV |
|---|---|---|
| Simulations | 2,435 | 9,739 |
| Operating point | one, fixed | **loading continuous per simulation**, total 210–596 MW (×2.84) |
| Source strength | fixed | **fixed** — no short-circuit-power or scaling column; grid setpoint 0.98–1.02 pu and angle only |
| Grounding | one | **resonant / resistive / solid in thirds**, continuous parameters |
| Inception | fixed, 1.1 s | **randomised 1.10–1.30 s**, point on wave uniform |
| Fault location | 1 / 20 / 50 / 80 / 99 % | **continuous 1–99 %** |
| Fault resistance | 1 / 10 / 40 Ω | **continuous 0.03–50 Ω, median 25 Ω**; ≤1 Ω stratum nearly empty (3–5 in-zone faults per relay) |
| Siblings / duplicates | 3-member groups, bit-identical three-phase siblings | **none** — 9,739 unique keys, 0 identical pre-fault cycles |
| Pre-fault shortcut (H25) | AUC 0.86–0.97 on the window ending at inception | **0.52–0.54** at both windows: gone |
| SIR, voltage-based | 1.04–1.69 (study model) | **0.3–1.4 measured** from remote-bus faults; loading moves it, source strength does not |
| Switching events | 50 | **5,474** across 9 types |
| Off-line short circuits, per relay | ~120–270 | **2,888 (A), 2,845 (B)** |
| ADC clipping, either full scale | 13–14 in-zone faults | **0** |

Two consequences run through everything below. **The security bounds are tight for the first time** — a
5 % budget needs ≥59 deduplicated units and every held-out class now has hundreds or thousands. And
**the regime does not widen**: SIR stays ≤1.4 and source strength is fixed, so nothing here tests the
weak-system claims; the instrument-chain and CVT caveat of REVIEW.md §6 Q1 stands unchanged.

## 3. The zone task and the protocol

Fault location is continuous, so the benchmark's discrete labels do not carry over. Definitions
(`common.load_relay_adapt`), each with its reason:

- **In zone (positives):** own-line short circuits at **≤ 85 %** of the line — the reach itself.
- **Guard band:** own-line short circuits at **85–100 %**, excluded from both classes and reported
  separately (kept under the review's name `own99`, so every existing table column reads it unchanged).
  A relay set to 85 % is not wrong to trip or not to trip there; it is wrong to be *scored* there.
- **Negatives:** **every short circuit off the protected line, regardless of direction** — remote bus,
  lines beyond it, the relay's own bus and the lines behind it, and every other line. The benchmark's
  narrower set (remote bus + the first 20 % of the lines beyond) is carried as a second column,
  `neg_bench`, so the two data sets can be compared like for like. Reverse-bus, lines-behind, parallel
  and other-line trips are also reported as separate held-out classes, as the review did.
- **Held out, never trained on:** switching events (5,474) and **incipient high-impedance faults**
  (1,187, 75–88 of them on the own line) — a class the benchmark set did not have.
- **Splits by operating point, never by simulation.** There are no siblings, so plain random splits
  would be leak-safe (§2); the grouping is kept for the opposite reason, to test *transfer*. Two split
  kinds: `grouped` = 5-fold over **20 quantile bins of total active load** (each fold holds out whole
  loading bands); `loqo` = **leave one loading quartile out**, the transfer test proper, in which
  calibration and test never share a loading band. A load-scaling label exists (the three loads' P and
  Q), so the key is derived from it, not from the waveforms.
- **Four operating points, not one.** A 5 % false-trip budget is a research convention; a protection
  engineer sets a zone-1 element so that it does not trip for an external fault at all. Every scored
  detector is therefore read at four points, all out of fold and all reported unsupervised and with
  32P/32Q supervision: **cal0**, the threshold at **zero** false trips on the training negatives — the
  deployable setting, whose test false trips are then whatever they turn out to be, reported as k/n with
  the binomial upper bound; **roc0** and **roc1**, read off the pooled out-of-fold ROC at zero and at one
  off-line false trip, which are upper bounds because the threshold is chosen on the test scores; and
  **far5**, the 5 % convention, kept as the secondary table so this set can be compared with REVIEW.md.
  T1 and T2 are read at the same four points (for T2, which has no score, the four points are four
  choices on its settable grid), so rule and learned detectors are compared at the same security.
- **The settable-characteristic subset.** The largest zone-1 quadrilateral a setting engineer could
  apply here — X_set = 0.9 X_line, R_set at the Kasztenny eq. (19) polarising cap — is evaluated on every
  in-zone fault, and dependability is reported separately on the faults inside it and outside it. This
  separates "the element is set badly" from "the fault is outside anything a quadrilateral can enclose".
- **Standard practice for the high-R_f stratum.** Besides 67N/67Q at the relay, two decisions that are
  not single-ended zone 1 are built from the remote-end cubicle of the same line, which the cache holds:
  **32P/32Q forward at both ends** (a permissive directional-comparison scheme, the POTT equivalent
  without a reach element) and **67N/67Q at both ends**. Both ends are read at the same 20 ms and no
  channel delay is modelled, so these are optimistic references, not proposals.
- **Unchanged from the reviewed protocol:** 20 ms decision time; per-class deduplicated counts with
  one-sided 95 % binomial upper bounds;
  grouped-bootstrap CIs on dependability and beyond-bus trips; 32P/32Q supervision reported beside
  every unsupervised decision; the causal starter as an alternative window anchor (H10); and **every
  tuned rung capped at a physically settable setting** — T2's R_set grid stops at the Kasztenny 2021
  eq. (19) polarising-error cap, so the legacy choice of 75–102 Ω (never a settable setting) is not
  reachable.
- **Strata reported for every result:** R_f in the protection-practice bands **<5, 5–15, 15–40, >40 Ω**
  (`common.RF_BINS`), grounding type, loading quartile.
- **Front ends:** the relay-bandwidth front end (3rd-order Butterworth 400 Hz + CT-based ADC full
  scale, H30) is the primary; the current front end is run too for comparability with REVIEW.md.
- **Detectors:** the corrected conventional ladder R0–R4 and the 67N/67Q reference
  (`adaptgrid_rules.py`), the tuned rungs T1 and T2 on the same folds as the learned models
  (`adaptgrid_run.py`); engineered + LR; gradient boosting on the raw window; the Q3
  winner (sequence-phasor trajectories referenced to the 3-cycle pre-fault V₁ memory, with increments,
  canonical rotation, small CNN); and the Q2 physical distance output (GBM regressor on the relay
  snapshot, trip at d̂ < 0.85, nothing tuned).
- **The instrument-mismatch column is standard,** not an extra: every learned model and T2 is also
  trained on fault-condition installation draw 1 and tested on draw 2 (VT 3–6 %, CT 5–10 %,
  `q1_instrument.draw_installation_fault`). On the benchmark this took engineered + LR from 1.9 % to
  39.7 % beyond-bus trips while the rungs stayed at 0 %.
- **Budget, stated:** one repeat of the 5-fold split (the benchmark used two); random forest and MLP
  dropped (the brief asked for LR, boosting and the Q3 CNN); 40 CNN epochs. Since 27 Sep 2026 the CNN runs
  with deterministic torch (`src/torch_det.py`) and its test rows are scored by the mean of the five
  inner-fold nets that set its threshold (`adaptgrid_run.cnn_foldmean`, review H18), so one seed gives one
  result. Two processes, one relay
  each, eight threads per process.

## 4. Results — the five questions

All numbers are the **relay-bandwidth front end** at 20 ms, matched chain unless stated, from
[`adaptgrid/TABLES.md`](adaptgrid/TABLES.md). "Off-line" is every short circuit off the protected line
(2,888 at A, 2,845 at B); "next-line" is the benchmark-like subset, remote bus plus the first 20 % of
the lines beyond (299 at A, 246 at B). k/n are deduplicated counts with one-sided 95 % upper bounds.
Unless a row says otherwise the operating point is **cal0: the threshold calibrated at zero false trips
on the training negatives**, and every detector is given twice, unsupervised and with 32P/32Q.

### The fault population, before any detector

The in-zone faults are mostly high-resistance: median R_f **24.2 Ω (A) / 22.6 Ω (B)**, quartiles
13.0–37.0 and 10.1–34.4, maximum ~50 Ω; the off-line population has the same median. The largest
**settable** zone-1 quadrilateral (X_set 5.85 / 9.36 Ω, R_set at the polarising cap 6.48 / 8.61 Ω)
encloses **10 of 168 in-zone faults at A (6 %)** and **28 of 207 at B (14 %)**. With the uncapped legacy
resistive reach of about 100 Ω it would be 39 % and 49 %, and that reach is not a setting anyone can
apply. This is the most important number in this document: **on this data a zone-1 quadrilateral cannot
be set to see more than one in seven in-zone faults, whatever it is set to.**

### Q1. Does the rule-set directional quadrilateral (R2) keep its security once loading varies?

**Yes, completely, and its low dependability is a property of the faults, not of the settings.** R2
(and R3, R4, which add nothing) trips **0 of 2,888** off-line faults at A and **0 of 2,845** at B
(≤ 0.1 %), and 0 reverse-bus, 0 lines-behind, 0 parallel, 0 guard-band, **0 of 5,474 switching events**,
under both splits and both front ends. Its dependability is **6.0 % (A) / 13.0 % (B)** — and on the
faults inside the settable characteristic it is **10/10 and 27/28**, with **0 of 158 and 0 of 179**
outside it. The element does exactly what a quadrilateral does; there is almost nothing inside it to do
it to. By R_f band its dependability is 70 / 8 / 0 / 0 % at A and 69 / 6 / 0 / 0 % at B across
<5, 5–15, 15–40, >40 Ω. The uncorrected rule R0 keeps 70.8 % / 56.5 % but trips 9/188 and 15/184
reverse-bus faults and 34–130 switching events, the N2 failure of REVIEW.md. The tuned rungs, held to
the same zero-false-trip discipline, are **T1 3.0 % / 0.0 %** and **T2 5.4 % / 10.1 %**.

### Q2. Does any learned model keep an advantage when calibration and test do not share an operating point, at a protection-grade setting?

**Yes at relay A, partly and unstably at relay B, and what survives at B is concentrated below 40 Ω.** At zero false trips
on the training negatives:

| relay front end, 20 ms, cal0 | dependability | off-line k/n | next-line k/n | switching | incipient | dep. <5 / 5–15 / 15–40 / >40 Ω |
|---|---|---|---|---|---|---|
| T2, A / B | 5.4 % / 10.1 % | 0/2888 · 0/2845 | 0/299 · 0/246 | 0 · 0 | 0 · 0 | 60/8/0/0 · 69/6/0/0 |
| T1, A / B | 3.0 % / 0.0 % | 2/2888 · 1/2845 | 0/299 · 0/246 | 0 · 0 | 0 · 0 | 0/3/4/0 · 0/0/0/0 |
| engineered + LR, A | **82.7 %** [76, 89] | **0/2888** | **0/299** | 0/5474 | 1/1187 | 80/100/78/73 |
| engineered + LR, B | **58.0 %** [51, 64] | 1/2845 | 1/246 | 56 → **0** with 32P/32Q | 16 → **0** | 92/83/54/**14** |
| **CNN seq-traj, A** | **99.4 %** [98, 100] | 3/2888 | 3/299 | 0/5474 | 3/1187 | **100/100/99/100** |
| **CNN seq-traj, B** | 70.0 % [58, 82] (45.4 % under loqo) | 0/2845 | 0/246 | 0 | 0 | 85/81/66/57 |
| gradient boosting, A | 11.3 % | 0/2888 | 0/299 | 0 | 0 | 40/15/9/4 |
| gradient boosting, B | 4.3 % | 0/2845 | 0/246 | 0 | 0 | 12/9/2/0 |
| GBM distance (Q2), A | 91.7 % | 125/2888 → 27 with 32P/32Q | 13/299 | 201 → 153 | 1 | 100/87/95/85 |
| GBM distance (Q2), B | 95.2 % | 40/2845 | 40/246 | 0 | 1 | 100/100/99/76 |

**The sequence-trajectory CNN is the detector that survives the protection-grade setting.** At relay A
it keeps **99.4 %** dependability with 3 off-line trips in 2,888 — all three on the next line, forward
faults just beyond the remote bus — no switching trip in 5,474, and **100 % above 40 Ω**, the band where
every conventional rung is at zero. Under leave-one-quartile-out it reads 98.2 % with 0/2888, and on the
current front end 94.0 % (0/2888) and 100.0 % (1/2888). At relay B the same detector is **not stable at
zero false trips**: 70.0 % under loading-bin folds and 45.4 % under leave-one-quartile-out in this run,
and 45–77 % over three seeds and both splits (Q4). The published single run had the two splits the
other way round (45.4 % against 83.6 %), which is the clearest evidence that the spread is the
threshold's variance and not something the split does to the model ("Why relay B's answer moves").

**Gradient boosting is the clearest casualty of the 5 % convention.** It reads 85.7 % (A) and 87.9 % (B)
at the 5 % budget and **11.3 % and 4.3 %** at zero false trips, with 6.0 % and 0.5 % under
leave-one-quartile-out. Nothing about it survives a protection-grade threshold; its apparent competence
was entirely in the budget.

Under leave-one-loading-quartile-out the engineered model gives up 8 points at A (74.4 %) and gains 5 at
B (62.8 %), with 1 and 3 off-line trips: **loading transfer costs it little.** The ROC read at zero
off-line trips is 84.5 % / 59.4 %, so the calibrated threshold is close to the best that score can do at
that security, and the advantage is not a calibration artefact.

Three things must be said with it. **First, dependability does not collapse at zero false trips for the
engineered model, and does for every conventional rung** — that is the answer to the question as asked.
**Second, the 5 % budget was hiding an overreach**: at far5 the same model reads 100 % / 99.5 %
dependability but trips **109 of 299** next-line faults at A and **141 of 246** at B. Those are forward
faults a few kilometres beyond the remote bus with tens of ohms of resistance, and directional
supervision cannot touch them. Moving to a zero-false-trip threshold removes them and costs 17 points of
dependability at A and 41 at B. **Third, the Q2 distance regressor keeps its 5 % behaviour at cal0
because its threshold is physical (d̂ < 0.85) and was never calibrated**, which is why its off-line count
stays at 125 / 40; read at zero false trips on its own ROC it falls to 20.8 % / 38.2 %.

Supervision is doing the security work throughout, not the learning. At relay B the engineered model
trips 56 switching events and 16 incipient faults unsupervised at cal0 and **none** with 32P/32Q; the Q2
output at A goes from 125 off-line trips to 27, and from 67 of 188 reverse-bus trips to 0. Every table in
`TABLES.md` gives the two rows side by side for this reason.

### The high-R_f stratum, and what standard practice does with it

| relay A / B, 20 ms | dependability | off-line | next-line | switching | incipient | dep. above 40 Ω |
|---|---|---|---|---|---|---|
| R2–R4 (single-ended zone 1) | 6.0 / 13.0 % | 0/2888 · 0/2845 | 0 · 0 | 0 · 0 | 0 · 0 | 0 % / 0 % |
| 67N or 67Q at the relay | 100 / 100 % | 2004/2888 · 373/2845 | – | 158 · 93 | 25 · 11 | 100 % / 100 % |
| 32P/32Q **both ends** (POTT-equivalent) | 97.0 / 100 % | **0/2888 · 0/2845** | 0 · 0 | 5 · 18 | 3 · 7 | 85 % / 100 % |
| 67N/67Q **both ends** | 98.8 / 100 % | 3/2888 · 0/2845 | 0 · 0 | 0 · 0 | 3 · 7 | 92 % / 100 % |
| engineered + LR, cal0 | 82.7 / 58.0 % | 0/2888 · 1/2845 | 0 · 1 | 0 · 0 with 32P/32Q | 1 · 0 | 73 % / 14 % |
| **CNN seq-traj, cal0** | **99.4 / 70.0 %** | 3/2888 · 0/2845 | 3 · 0 | 0 · 0 | 3 · 0 | **100 % / 57 %** |

**With a channel this problem is solved.** Directional comparison between the two line ends covers
97–100 % of the in-zone faults with no off-line trip at all, at both relays, in every R_f band. 67N/67Q
at the relay alone detects every in-zone fault and is not selective (69 % / 13 % of off-line faults),
which is why it is a time-delayed backup and not zone 1.

The niche this project can claim on this data is therefore narrow and specific: **single-ended,
instantaneous, channel-free zone selectivity for high-resistance faults.** At relay A the CNN reaches
**94.6–99.4 %** of in-zone faults over six calibrated runs, with 0–3 off-line false trips in 2,888 and
no communication, against 6 % for every settable quadrilateral and 97 % for the channel-based scheme
that needs both line ends — so on that relay the single-ended learned detector matches the permissive
scheme without a channel. At relay B it reaches 45–77 % at zero false trips, depending on the training
draw, and 90–98 % if one off-line trip in 2,845 is allowed, against 13 % for the quadrilateral and
100 % for the channel scheme, so the gap the channel closes is real and the learned detector closes
only part of it. The claim is not that learning beats protection practice; it is that on this data it
covers most of a gap that single-ended zone 1 structurally cannot, at one relay, and half of it at the
other.

### Q3. Does the per-relay threshold, or the physical distance output, transfer between relays?

**No detector transfers in both directions with a carried zero-false-trip threshold.** Carrying the
threshold between relays, at cal0:

| | AUC | dependability | off-line k/n |
|---|---|---|---|
| engineered + LR, B → A | 0.999 | **91.1 %** | 1/2888 |
| engineered + LR, A → B | 0.988 | 43.5 % | 3/2845 |
| CNN seq-traj, B → A | 0.986 | 63.7 % | **0/2888** |
| CNN seq-traj, A → B | 0.994 | **99.0 %** | 105/2845 |
| gradient boosting, B → A | 0.577 | 0.6 % | 0/2888 |
| gradient boosting, A → B | 0.456 | 8.7 % | 238/2845 → 3 with 32P/32Q |
| GBM distance (Q2), A → B | **0.173** | 89.9 % | **2726/2845** → 202 with 32P/32Q |

The engineered model transfers B → A (91.1 % with one trip) and not A → B. The CNN ranks well across
relays (AUC 0.986–0.994) but its threshold does not carry: B → A it stays safe (0 trips) at 63.7 %, and
A → B it keeps 99.0 % at the price of 105 off-line trips. Gradient boosting does not
transfer in any sense: its ranking is barely better than chance across relays (AUC 0.46–0.58), and the
carried threshold either trips nothing or trips 238 off-line faults. The Q2 distance output is worst:
A → B its ranking **inverts** (AUC 0.173) and it trips 2,726 of 2,845 off-line faults. Its snapshot
features are in line units, but what the regressor learned about them on one line does not carry to a
line of different length and infeed. **No detector here transfers in both directions**, so a per-relay
calibration step is not optional on this data.

### Q4. Does the Q3 winner survive varied operating points and the relay front end?

**Yes at relay A, with a caveat at relay B — and the single-run figures had to be repeated before they
could be quoted.** At the 5 % budget the CNN on V₁-memory-referenced sequence trajectories holds
**100 % dependability at both relays**, in every R_f band, grounding type and loading quartile, with
96/2,888 off-line trips at A and 147/2,845 at B (and 1,143 of 5,474 switching events at B).

Held instead to zero training false trips, one run is one training draw, and a zero count on 2,888 is
only as strong as that draw. The seed study (`adaptgrid_seeds.py`, three seeds × two splits per relay)
was therefore re-run with deterministic torch and fold-mean test scoring on 27 Sep 2026. It replaces the
published single-net figures (relay A 90.5–100 % with 0–22 off-line trips; relay B one run per split):

| relay front end, cal0 | grouped, 3 seeds | loqo, 3 seeds | all six |
|---|---|---|---|
| **A** dependability | 99.4 / 94.6 / 98.2 % | 98.2 / 98.8 / 99.4 % | **94.6 – 99.4 %**, median 98.5 |
| **A** off-line trips of 2,888 | 3 / 0 / 0 | 0 / 0 / 0 | **0 – 3** |
| **A** roc0 (threshold above every test negative) | 100 / 100 / 100 % | 100 / 99.4 / 100 % | 99.4 – 100 % |
| **B** dependability | 70.0 / 77.3 / 61.4 % | 45.4 / 64.3 / 71.0 % | **45.4 – 77.3 %**, median 67.2 |
| **B** off-line trips of 2,845 | 0 / 0 / 0 | 0 / 0 / 0 | **0 in every run** |
| **B** roc1 (≤1 off-line trip in 2,845) | 90.3 / 97.6 / 96.6 % | 93.7 / 94.2 / 94.7 % | **90.3 – 97.6 %** |
| switching trips of 5,474, either relay | 0 in every run | 0 in every run | ≤0.055 % |

1. **At relay A the zero-false-trip point is now tight.** Scoring the test rows with the nets that set
   the threshold removed the worst draw: the 22-trip run of the single-net protocol does not recur, the
   largest count is 3 (all on the next line), and dependability stays within 5 points. In every run a
   threshold with zero off-line trips and ≥ 99.4 % dependability exists (roc0).
2. **At relay B it is not.** Six draws span 45–77 %, all with zero off-line trips, while one permitted
   trip lifts every draw to 90–98 %. The zero-count operating point at B is a property of which single
   off-line fault the calibration happens to score highest, not of the detector.
3. **Why the draws differ is now known**: the network's training trajectory is unstable ("Determinism and
   training stability" below), and the threshold, an extreme-value statistic, turns that into
   dependability.

The calibration was also checked rather than asserted: `threshold_provenance` compares the actual index
sets and finds **0 calibration rows and 0 calibration loading bins inside any test fold**, for both
splits and both relays. The threshold never saw a test case or a test operating point.

At relay B the published single run read 45.4 % (grouped) against 83.6 % (loqo); the deterministic
re-run of the same seed reads 70.0 % against 45.4 %, the other way round. The next section takes that
apart. It was the open cell of REVIEW.md §6 Q3 ("not re-run on the relay front end"); the answer is that
it holds at relay A, and that at relay B the zero-false-trip point is not a stable quantity at all.

### Why relay B's answer moves

`adaptgrid_splitdiag.py` → [`adaptgrid/splitdiag_adapt_B_relayfe.json`](adaptgrid/splitdiag_adapt_B_relayfe.json).
Nothing is refitted: the driver stores every fold's out-of-fold score and threshold, so the operating
point can be taken apart after the fact.

**The split does not change the model. It changes the threshold.** The calibrated threshold is the
largest out-of-fold score among the training negatives — an extreme-value statistic over some 2,845
off-line faults. Per fold, at relay B:

| | threshold range across folds | dependability per fold |
|---|---|---|
| grouped (10 folds) | **4.1 – 17.6** | 92.7 % at 4.1, 94.9 % at 6.4, 76.1 % at 7.9, 61.1 % at 14.2, 28.9 % at 17.6 |
| loqo (4 folds) | 13.2 – 17.2 | 26.5 – 57.4 % |

(Per-fold dependability for the grouped split is given for the five folds of the second repeat, whose
scores the driver keeps.)

Dependability tracks the threshold and little else: the folds with the lowest thresholds return 93–95 %,
the fold with the highest returns 29 %, and under loqo, where this draw put all four thresholds between
13 and 17, every fold is below 58 %. At relay A the thresholds span −3.2 to 23.7 and every fold still
returns 92.5–100 %, because there the positives sit far above the negatives and a threshold swing costs
little. At relay B they sit among them.

**The failures are not concentrated in one place.** Under the grouped split (this draw), dependability
by R_f band is 85 / 81 / 66 / 57 %, by fault type 47–80 %, by loading quartile 58–81 %, by grounding
63–75 %; under loqo every one of those is 20–40 points lower. The whole distribution shifts. The
high-R_f and three-phase faults sit closest to the threshold, so they are lost first when it rises
(above 40 Ω: 57 % grouped, 16 % loqo), but no band, type or grounding regime fails on its own, which is
what a genuine transfer failure would look like.

**The pre-fault flow direction hypothesis is refuted by measurement.** Relay B imports at a median
**−162.7°** with a 5th-to-95th percentile range of **−163.3° to −162.0°** — a 1.3° spread over the
entire set. Missed positives sit at −162.8° and caught ones at −162.7°. Varying the loading varies the
*magnitude* of the pre-fault flow, not its direction, so there is no direction transfer to fail at.
What does set the threshold is visible in the top-scoring negatives: bolted remote-bus faults at
0.2–1.0 Ω, which are electrically the closest thing to an in-zone fault that exists in the data.

**Which split is honest to quote: neither, at that operating point.** Both are estimates of an order
statistic and both are noisy. The deterministic re-run shows it directly: the same seed now puts grouped
above loqo (70.0 % against 45.4 %), the reverse of the published run, and the pooled-ROC read is 75.4 %
against 78.7 %. One permitted false trip removes the problem: at ≤1 off-line trip in 2,845 (upper bound
0.167 %, about 1 in 600) this run's splits agree at **90.3 % and 93.7 %**, and all six seed-study draws
lie in 90–98 %. The honest report for relay B is therefore the ≤1-in-N
operating point with its binomial bound, and the zero-count point quoted as the fold spread it is. That
is a finding about how protection-grade operating points should be estimated, not only about this relay.

### Reverse faults held out of training

On the benchmark the training negatives were the remote bus and the first 20 % of the next line, so a
reverse fault was a class the learned models had never seen. Here the negatives are every off-line short
circuit (`common.py`: `neg = shc & ~own`), so relay-bus and behind-the-relay faults are trained and
calibrated on, and "the CNN needs no directional supervision" is weaker evidence than it was on the
benchmark. `adaptgrid_reverse_heldout.py` →
[`adaptgrid/reverse_heldout_relayfe_cnn.json`](adaptgrid/reverse_heldout_relayfe_cnn.json) runs the CNN
twice with identical code, seed 0 and splits: as published, and with reverse faults removed from
training and calibration and scored as a held class.

| cal0, relay front end | A grouped | A loqo | B grouped | B loqo |
|---|---|---|---|---|
| dependability, reverse in training → held out | 99.4 → 100.0 % | 98.2 → 98.2 % | 70.0 → 52.7 % | 45.4 → 79.7 % |
| relay-bus faults tripped, held out | 0/188 | 0/188 | 0/184 | 0/184 |
| behind-the-relay faults tripped, held out | 0/199 | 0/199 | 0/816 | 0/816 |
| off-line trips, held out | 0/2888 | 0/2888 | 0/2845 | 1/2845 |

**Never shown a reverse fault, the CNN trips none of 1,387**, in every cell (upper bounds 1.6 % for
either relay-bus class, 0.37 % for relay B's lines behind). The in-training rows reproduce the
`adaptgrid_run` numbers exactly, a determinism check across two scripts; the dependability changes at B
are the threshold variance of Q4, not an effect of the training set.

It matters because the directional element is not the reverse-fault blocker the ladder results suggest
at relay A. `adaptgrid_directional_reverse.py` →
[`adaptgrid/directional_reverse_relayfe.json`](adaptgrid/directional_reverse_relayfe.json): 32P/32Q
declares **41 of 188 relay-bus faults and 148 of 199 faults on the line behind (MainLn1-5) forward** at
relay A, against 0 of 1,000 at relay B. The relay-bus misdirections are all at R_f ≥ 15 Ω (0 of 65 below
15 Ω, 19 of 92 at 15–40 Ω, 22 of 31 above 40 Ω), and the behind-line ones rise with R_f the same way (26
of 57 below 15 Ω, 122 of 142 above). A ring through buses 1–2–5 may carry part of the behind-line fault
current forward through the protected line; that is not verified case by case. Supervision still removes
every reverse trip the engineered and distance detectors make, because they do not trip the high-R_f
reverse faults 32P/32Q misreads; it would not protect a detector that did.

### Determinism and training stability

Until 27 Sep 2026 the CNN numbers in this document were single GPU draws: cuDNN's default convolution
backward and adaptive pooling's CUDA backward are non-deterministic, so a fixed seed did not fix the
result, and the zero-false-trip threshold amplified the difference (relay A loqo seed 0: 100 % published,
95.2 % on a repeat). Every CNN number above now comes from `src/review/rerun_cnn_deterministic.bat`, with
`src/torch_det.py` (bit-identical repeats, checked on a smoke run and across `adaptgrid_run` and
`adaptgrid_reverse_heldout`) and with the test rows scored by the five inner-fold nets that set the
threshold (`cnn_foldmean`; the earlier protocol scored them with a sixth net trained on all of train,
whose logit scale differs — review H18). Every non-CNN row reproduced exactly.

`cnn_learning_curve.py` →
[`adaptgrid/learning_curve_relayfe_cnn.json`](adaptgrid/learning_curve_relayfe_cnn.json) and
[`.png`](adaptgrid/learning_curve_relayfe_cnn.png) trains the same network for 120 epochs on three
grouped folds per relay and records training and held-out loss every epoch (the replica equals the
published network bit for bit at 40 epochs in all six folds). **There is no overfitting at 40 epochs**:
held-out loss falls with training loss and is lowest at epochs 71–120. **The optimisation is unstable**:
both losses jump by one to three decades every few epochs (Adam at 2e-3, batch 32, pos_weight 14–17);
at relay B held-out loss plateaus near 1e-2 while training loss reaches 1e-4, and the gap between the
largest held-out and the largest training negative score swings by ±10 from one epoch to the next. The
40-epoch network is a draw from that trajectory, which is where relay B's spread comes from. A lower or
decaying learning rate, gradient clipping or averaging the last epochs' weights are the obvious remedies;
none is applied here, because choosing one needs its own inner-fold selection.

### Decision time: what waiting buys

`adaptgrid_time_sweep.py` →
[`adaptgrid/time_sweep_relayfe_cnn.json`](adaptgrid/time_sweep_relayfe_cnn.json) runs the same CNN at
decision times of 10, 15, 20, 30 and 40 ms with everything else unchanged: ten sequence-phasor frames
evenly spaced from t/10 to t, the canonical phase rotation chosen by the phase selector at t, and training,
calibration and scoring by `adaptgrid_seeds.run_seed` (three seeds, both splits). At 20 ms it reproduces
the seed study exactly, which is the built-in check.

| zero false trips (cal0), range over 3 seeds × 2 splits | 10 ms | 15 ms | 20 ms | 30 ms | 40 ms |
|---|---|---|---|---|---|
| relay A, dependability | 88.1–100 % | 72.6–100 % | 94.6–99.4 % | 96.4–100 % | 92.3–100 % |
| relay A, off-line trips of 2,888 | 0 | 0 | 0–3 | 0–2 | 0–2 |
| relay B, dependability | 53.1–78.7 % | 66.7–87.4 % | 45.4–77.3 % | 58.9–79.2 % | 22.7–70.0 % |
| relay B, dependability at ≤ 1 off-line trip in 2,845 | 87.9–98.1 % | 98.1–100 % | 90.3–97.6 % | 91.3–97.6 % | 78.3–94.7 % |

No run trips a switching event at any decision time. **Waiting buys nothing for this detector.** At relay A
half a cycle already gives 88–100 % with no off-line trip, and one cycle is as good as two. At relay B the
zero-false-trip point does not improve with time and is worst at 40 ms: its spread is the threshold
variance described above ("Why relay B's answer moves"; the unstable optimisation of "Determinism and
training stability"), not a shortage of post-fault data. The 2–2.5-cycle decision of Hasan et al. (below)
is therefore not what this detector needs; a zone-1 element can decide at one cycle or less here.

### The closest published method on this data: Hasan et al. (2026)

Hasan, Chakraborty & Wang (IJEPES 181, 2026, 112007) propose the same thing this project's learned niche
is — single-ended, channel-free zone selection for lines with inverter-based resources — with a
hierarchical linear SVM, and report 97.2 % overall accuracy on a two-bus PSCAD system with a grid-forming
BESS at the relay end. Their data are confidential, so their method was re-implemented and run on this
data under this protocol: `hasan_svm.py` (protocol pre-registered in its docstring, committed before any
result) → [`adaptgrid/hasan_svm_relayfe.json`](adaptgrid/hasan_svm_relayfe.json). Taken as published:
their Table 2–4 features averaged over a 3-cycle buffer; stage 1 no fault / reverse / forward, stage 2
fault type, stage 3 one zone classifier per fault class with 3rd-degree polynomial terms and the top 100
kept; LinearSVC. Adapted, with the reason in the docstring: angles referenced to the pre-fault V₁ memory
(the grid's initial angle is randomised over ±180°, so raw angles are noise), meshed-grid direction labels
with pre-fault windows as the no-fault class, zone 1 = own line ≤ 85 %, and decision at 20 ms (ours) and
50 ms (2.5 cycles, theirs).

With **their own trip rule** (forward and zone-1 decision value > 0):

| relay front end, their rule | dependability | off-line trips | next-line trips | switching trips |
|---|---|---|---|---|
| A, 20 ms (grouped / loqo) | 82.1 / 79.8 % | 22 / 28 of 2,888 | 18 / 19 of 299 | 46 / 48 of 5,474 |
| A, 50 ms | 92.9 / 91.7 % | 7 / 12 | 6 / 6 | 1 / 1 |
| B, 20 ms | 92.8 / 92.3 % | 10 / 9 of 2,845 | 10 / 9 of 246 | 273 / 293 (0 with 32P/32Q) |
| B, 50 ms | 91.8 / 91.3 % | 10 / 4 | 8 / 3 | 2 / 1 |

At **zero off-line false trips** (cal0, same folds and calibration as every detector here), against the
CNN's six-draw range:

| cal0, grouped / loqo | Hasan SVM, C = 1 | Hasan SVM, tuned C | CNN seq-traj (20 ms) |
|---|---|---|---|
| A, 20 ms | 56.0 / 42.9 % | 31.0 / 33.3 % | **94.6 – 99.4 %** |
| A, 50 ms | 57.7 / 14.3 % | 74.4 / 66.1 % | |
| B, 20 ms | 37.7 / 30.9 % | 30.9 / 31.9 % | **45.4 – 77.3 %** |
| B, 50 ms | 9.2 / 11.6 % | 14.5 / 3.9 % | |

(The C = 1 rows keep 0–2 off-line trips; cal0 is calibrated on training negatives, so a few test trips
remain, as for every detector.) Four things follow.

1. **With its own rule the method is dependable but not secure**: 80–93 % of in-zone faults, but 4–28
   off-line trips per ~2,900, mostly on the next line, and at 20 ms up to 293 switching trips. That is not
   a zone-1 operating point.
2. **At a protection-grade threshold it falls well below the CNN** at both relays and both decision times,
   and below the CNN's worst draw at relay B. Tuning C helps only at relay A at 50 ms (74 %).
3. **The weak stage is direction.** Stage 1 separates forward from reverse faults with 72–82 % accuracy at
   relay A and 87–91 % at B (their radial system: 100 %); fault type (99.5 %), no-fault on pre-fault
   windows (≈100 %) and zone given the class (95–99 %) are fine. On a meshed grid direction is the hard
   part, consistent with 32P/32Q's forward calls on relay A's reverse faults above.
4. **The 3-cycle buffer makes it slow by construction**: at 20 ms two of its three cycles are pre-fault.
   At its own 2.5 cycles it does much better with its own rule, and 2.5 cycles is slow for a transmission
   zone 1.

Also measured: the pre-fault shortcut is absent (AUC 0.51 at both relays on the buffer ending at
inception); the threshold provenance holds (0 calibration rows or loading bins in any test fold);
sin/cos angles raise the 20 ms AUC (0.963 against 0.901 at A) but trip up to 306 switching events; the
installation-mismatch chain costs 12 points at A at 20 ms and nothing at 50 ms. The 'pu' variant is
identical to the default by construction — a constant per-relay scale is absorbed by the StandardScaler —
so it was never a different model; per-simulation normalisation, which would be, was not run.

### Fault location, and what it is not evidence for

`adaptgrid_location.py` → [`adaptgrid/location_relayfe.json`](adaptgrid/location_relayfe.json).
**Fault location is a solved, standard relay function.** It is reported here only to place this work
correctly: the contribution is zone selectivity under high fault resistance with strong infeed, not
locating faults more accurately than a relay already does. Mean absolute error in per cent of line
length, in-zone faults, same folds as everything else, with the infeed factor measured per case as
(apparent added resistance)/R_f:

| relay A · relay B | bolted (R_f ≤ 1 Ω) | R_f > 40 Ω | infeed > 3 (relay B, n = 52) |
|---|---|---|---|
| reactance element | **6.9 · 5.6 %** | 143.6 · 4005.8 % | 3369 % |
| Takagi (superimposed current) | 7.3 · **4.6 %** | 126.9 · 236.3 % | 174 % |
| GBM distance (Q2), out of fold | 7.0 · 14.0 % | **15.9 · 24.7 %** | **16.9 %** |

**The conventional locator wins where fault location is actually used** — bolted and low-resistance
faults, where it is within 5–7 % of line length and the learned regressor is no better at relay A and
2.5× worse at relay B. The learned estimator only wins in the high-resistance, strong-infeed corner,
where the reactance element is not merely inaccurate but meaningless: a 4,006 % mean error means the
apparent reactance no longer carries the distance at all. Takagi, which is the standard fault-resistance
correction, recovers most of that but still reads 174 % at infeed above 3.

Two things this does not say. It does not say the learned estimator is a better fault locator; on the
faults locators are specified for, it is not. And it is not an independent result: relay A's in-zone
faults have a measured infeed factor of 0.95 median and no case above 3, while relay B's is 1.78 with
52 of 207 above 3 — the same strong-infeed high-R_f corner that the zone-selectivity result lives in,
measured a second way.

### Q5. Does the instrument-mismatch fragility persist when training spans many operating points?

**It disappears.** Training on installation draw 1 and testing on draw 2 — the test that took
engineered + LR from 1.9 % to **39.7 %** beyond-bus trips on the benchmark — changes almost nothing
here. At cal0, engineered + LR at A goes 82.7 % → **81.5 %** dependability with 0 off-line trips either
way; at B, 58.0 % → 59.9 % with 1 → 0. T2 moves 5.4 → 7.7 % (A) and 10.1 → 10.6 % (B) with 0 off-line
trips throughout. The CNN at A keeps 100 % at cal0 with 1 and 0 off-line trips (grouped, loqo); at the
5 % convention it moves from 96 to 105 off-line trips, and gradient boosting stays inside its band. **The 39.7 % was a single-operating-point artefact**: where every
simulation shares one pre-fault state a model learns that state, and a 5–10 % ratio error on it looks
like a different operating point. When training already spans 210–596 MW a ratio error is inside the
distribution the model has seen. This is the sharpest available test of whether that fragility was data
or method, and the answer is data.

### What the strata add

- **R_f.** Every conventional rung is at 0 % above 15 Ω. Above 40 Ω, at zero false trips, the CNN is at
  **100 % (A)** and 57 % (B; 16 % under loqo), the engineered model at 73 % and 14 %, the Q2 output at 85 % and 76 % but
  with 27–40 off-line trips, and gradient boosting at 4 % and 0 %. The band above 40 Ω is where
  single-ended zone 1 ends, and it is also where the four learned detectors differ most from each other.
- **Grounding.** T2 covers 0 % of solidly grounded in-zone faults at A (10 % resistive, 6 % resonant);
  no detector's off-line trips depend on grounding.
- **Loading.** No detector's dependability depends on the loading quartile except gradient boosting at B
  (79 % in the heaviest quartile against 90 %).
- **Starter anchoring.** Anchoring the window at the causal starter instead of the true inception moves
  nothing at A and costs the engineered model nothing at B.

### Summary in one paragraph

Across a 2.8× loading range, three grounding regimes and a randomised inception, the corrected
conventional zone 1 keeps perfect security and covers 6 % (A) and 13 % (B) of in-zone faults — and those
are exactly the faults inside the largest quadrilateral anyone could set, so the number is a property of
the fault population, not of the settings. Held to the same zero-false-trip discipline, the
sequence-trajectory CNN covers **94.6–99.4 % at relay A across three seeds and two splits** (median
98.5 %) with 0–3 off-line trips in 2,888 and no switching trip in 5,474 in any run, and 45–77 % at
relay B, where the training draw decides which off-line fault sets the threshold (90–98 % if one trip in
2,845 is allowed); the engineered-feature model covers 83 % and 58 %;
gradient boosting collapses to 11 % and 4 %, so its 86–88 % at the 5 % budget was the budget talking.
Every learned model loses the 5 %-budget overreach onto the next line that the benchmark's three
discrete R_f values had concealed. Directional supervision, not the learning, is what removes switching
and reverse-bus trips for the engineered and distance detectors; the CNN needs none, and trips none of
1,387 reverse faults even when they are removed from its training. No detector
transfers between relays in both directions. The closest published method, Hasan et al.'s
hierarchical linear SVM, re-implemented here, is 80–93 % dependable with its own rule but trips 4–28
off-line faults, and at zero false trips reaches 9–58 % (74 % with tuned C at relay A, 50 ms). A both-ends directional comparison covers 97–100 % with no
false trip at all, so the defensible niche is single-ended, channel-free, instantaneous selectivity for
high-resistance faults — a niche the CNN fills at relay A and partly fills at relay B. The
instrument-mismatch fragility that looked like a property of learning is a property of
single-operating-point data and is gone here.

## 5. What no EvEMTBench family can test

Stated plainly, because §4 will be read as more than it is:

- **No injected auxiliary signal.** Nothing in any EvEMTBench set carries a δ, so the project's central
  question — whether a designed negative-sequence injection separates in-zone from out-of-zone faults on
  real EMT data — is not touched here or anywhere in this repository's real-data results.
- **Grid-following inverters only**, with a 1.2 pu limiter, and **inverters at ≈ 0.14 % of short-circuit
  capacity** (85 MVA against two 30 GVA grids). The inverter-dominated regime the project is about is
  absent; every relay here sees a synchronous-source-dominated fault. The ladder's memory and I₂
  polarisation are right for this grid and wrong for that one (REVIEW.md §10 item 1).
- **No CT or CVT models** in the records: instrument transformers are ideal, and every CT/CVT result in
  this repository is a model applied afterwards (`common.ct_saturation`, `cvt_filter`).
- **50 Hz**, 110 kV, one grid topology. The 60 Hz one-cycle budget of the plan is the IEEE 39-bus set,
  out of scope.
- **Source strength fixed** (§2), so the SIR ≤ 1.4 regime caveat holds on this set as on the benchmark.
- **No channel, no remote-end timing.** The both-ends references in §4 read both line ends at the same
  instant. Real permissive schemes carry a channel delay, a security timer and a loss-of-channel mode;
  none of that is in these records, so those rows are an optimistic bound on communication-assisted
  practice and cannot be used to compare against it fairly. A channel delay was since modelled
  afterwards ([CIGREMV.md](CIGREMV.md), quick checks): the rows hold for a trip at 20 + d ms, but to trip
  by 20 ms over a 5–15 ms channel the POTT-equivalent loses its security at relay B (48–179 off-line
  trips) and its dependability at relay A (94.6 → 71.4 %).
- **Two relays, one grid, two front ends.** Relay B's unstable zero-false-trip CNN result (§4) is the clearest
  sign that two relays are not enough to settle how stable a protection-grade threshold is.

The second grid and the inverter-dominated fault are now tested on the CIGRE MV feeder, with the same
protocol: [CIGREMV.md](CIGREMV.md). The single-ended result above does not survive there.
- **The zero-false-trip threshold is an order statistic**, so with a few thousand negatives it carries
  real variance: at relay B six draws of the same detector span 45–77 % at zero off-line trips, and
  one draw's fold thresholds span a factor of four (4.1–17.6). Any protection-grade number in this document is an estimate
  of a quantity that needs either far more negatives or a ≤k-in-N formulation to be stable.

What this family *does* add, and did not have before: a genuinely varying operating point, a
randomised inception, three grounding regimes, a continuous R_f, and enough off-line and switching
events to bound security properly.
