# Power-CVXPY

**Auxiliary-signal fault detection in inverter-dominated grids: design, simulation, detection, hardware.**

Senior design, NJIT Electrical and Computer Engineering, 2026–27.
Advisor (proposed): Prof. Joshua A. Taylor. Builds on his NSF project *Auxiliary Signal-Based Fault Detection in Inverter-Dominated Power Systems* (NSF 2411925, with A. Domínguez-García, UIUC).

## The problem in one paragraph

A protective relay decides "there is a fault, open the breaker." For a century it did so by watching for a large current, because synchronous generators push 5 to 7 times rated current into a fault. Solar, wind and batteries connect through inverters, and inverters cap their fault current at roughly 1.1 to 1.2 pu. In an inverter-heavy grid a fault can look almost like normal load, and conventional relays misoperate.

## Taylor's idea, and what we add

Taylor and Domínguez-García (2025, 2026) model every unknown the relay faces (fault location, fault resistance, remote-end current, measurement noise) as a bounded set, compute the full region of measurements a fault can produce, and, when that region overlaps normal operation, have the inverter inject a small **auxiliary signal** (negative-sequence current) chosen by convex optimization to be as small as possible while guaranteeing separation. Their papers are analytical. Their conclusions name EMT-simulation evaluation as the next step.

This repository is that next step, split into four parts:

| # | Part | What it delivers | Owner |
|---|------|------------------|-------|
| 1 | **Design tool** | A CVXPY tool: input a grid model, output the smallest separating auxiliary signal | TBD |
| 2 | **Simulation** | A Simulink / PSCAD test grid with SGs and inverters injecting the optimized signal; labeled fault waveforms | TBD |
| 3 | **Detection** | Relay-side detection of the signal: conventional elements and Taylor's multiple-model Kalman filter vs a learned detector; shrink the signal until each fails | Asmar Hasanova |
| 4 | **Embedded** | The detector on an edge board, decision latency measured against a one-cycle (16 ms) budget | TBD |

## What is already here (first result, 13 Sep 2026; corrected after review)

A toy replication of the design method on a two-bus static sequence-domain model, following the paper's modelling choices, with the convex step in CVXPY + Clarabel (the solver the paper uses).

> **These δ are not certificates.** The review reproduced every number below exactly, and then
> showed that each is a *local* optimum of a problem whose uncertainty set is unsound, with no
> margin and no inverter current limit ([REVIEW.md](REVIEW.md) §4 H5/H6/H13–H15, §7 claims 1–5).
> Read the table as "what this tool returns today", not as "the smallest signal that works".

| Preset | Sources | Relay noise | Ambiguous faults at δ = 0 | δ as published | Exact global minimum | With 10 % margin | With a sound angle set |
|---|---|---|---|---|---|---|---|
| `easy` | stiff SG + IBR | 0.03 | 0 / 30 | 0 | 0 | 0 | 0 |
| `weak_sg` | weak SG + IBR | 0.08 | 5 / 30 | 0.51 pu | **0.5040 pu** | 0.666 pu | 0.552 pu |
| `weak_sg_noisy` | weak SG + IBR | 0.15 | 7 / 30 | 0.70 pu | **0.6908 pu** | 0.899 pu | 1.042 pu |
| `all_ibr_hard` | IBR + IBR | 0.15 | 5 / 30 | 0.41 pu | **0.3863 pu** | 1.357 pu | 1.054 pu |
| `weak_sg_eps12` | weak SG + IBR | 0.12 | 10 / 30 | none ≤ 0.8 | **1.3186 pu** | – | – |

Global optima, margins and the sound-angle redesign: [review/WP1_REPORT.md](review/WP1_REPORT.md),
`results/review_wp1/h15_global.json`, `h14_margin.json`, `h6_angle.json`.

Three things fell out, and the review qualified all three.

- **With a stiff synchronous source no signal is needed.** True, but only for this gridded
  two-bus toy — it is not a statement about stiff sources in general (§7 claim 2).
- **When the source is weak or an inverter, high-resistance line-to-ground faults become
  ambiguous and roughly half a per-unit of negative-sequence injection resolves them.** The
  0.5 pu figure carries no margin: the separation is exactly zero-width, 0.45–1.25 % of the
  noise radius. Ask for 10 % headroom and it becomes 0.666 pu; replace the linearised angle
  box (which is unsound — the true set reaches 0.085–0.276 pu outside it) and it becomes
  0.552 pu. **At a 1.2 pu inverter current limit, every preset that needs δ > 0 is infeasible**
  once the limit is imposed worst-case over the positive-sequence set (§7 claims 3, H5).
- **Raise relay noise by fifty percent and the required injection exceeds what an inverter can
  physically deliver.** This one holds: the exact minimum is 1.3186 pu (§7 claim 4).

One claim in `docs/PLAN.md` does not survive: the optimum was **not** verified against brute
force. Brute force finds 0.504–0.506 pu, below the published 0.5141 — the alternating scheme
stops at a local optimum (§7 claim 5, H15).

![weak_sg result](results/aux_signal_toy_weak_sg.png)

Left: which δ separate faults from normal (black = all). Middle: the five hardest faults projected on the Farkas certificate direction at δ = 0, overlapping normal. Right: same at the optimum, separated.

Full numbers and honest caveats: [results/RESULTS.md](results/RESULTS.md).

## Second result: does the auxiliary signal actually help? (16 Sep 2026)

A waveform generator drives the same circuit family as the design tool, so the certified
signal and the measured detection rate live on one system. Two studies were run.

**Fault versus load** ([results/DETECTION.md](results/DETECTION.md)): a conventional
multivariate element solves that regime with no injection at all, so the negative was too
easy. That part holds — engineered features reach 98.8–100 % and the CNN adds nothing
([REVIEW.md](REVIEW.md) §7 claim 8).

The companion negative result needs a caveat. A magnitude threshold on negative sequence is
useless there, and *at a 1 % false-alarm budget* more signal makes it worse. **By AUC it does
not:** once the detector's polarity is chosen on training data instead of the test set
(H17), |i⁻| improves from 0.563 AUC at δ = 0 to 0.980 at δ = 0.3. Its dependability at 1 %
FAR still never exceeds 17.6 %, so the operating-point statement survives and the
"more signal is worse" reading does not (`results/review_synth/h17_detect_full.json`;
§7 claim 7).

**In-zone versus out-of-zone** ([results/ZONE.md](results/ZONE.md)): the decision distance
protection is actually about, on a three-bus model with an adjacent line, fault resistance,
remote infeed, and system conditions redrawn per sample. Faults just inside the reach against
the same faults just past the remote bus.

The table below is the **corrected** sweep. The originally published one used a CNN crippled by
per-waveform standardisation (H19) and a |i⁻| threshold whose polarity was chosen on the test
set (H17); both are fixed here.

| δ (pu) | apparent reactance | \|i⁻\| magnitude | engineered features + LR | 1D CNN |
|---|---|---|---|---|
| 0.000 | 0.954 ± 0.005 | 0.594 ± 0.020 | 0.996 ± 0.001 | 1.0000 ± 0.0000 |
| 0.100 | 0.946 ± 0.005 | 0.581 ± 0.018 | 0.997 ± 0.001 | 1.0000 ± 0.0000 |
| 0.300 | 0.912 ± 0.009 | 0.559 ± 0.015 | 0.998 ± 0.001 | 1.0000 ± 0.0000 |
| 0.514 | 0.868 ± 0.010 | 0.543 ± 0.014 | 0.998 ± 0.001 | 1.0000 ± 0.0001 |

ROC AUC, mean ± sd over three seeds, 900 train and 450 test waveforms per class per point
(`results/review_synth/zone_full_fixed.json`, corrected pipeline).

![zone sweep](results/zone_sweep.png)

Three things came out of it. **The first no longer holds, the second was never tested, and the
third is backwards.**

- ~~The auxiliary signal helps the learned detector~~ **and hurts the conventional one.** The
  first half is withdrawn. With the normalisation bug fixed, the CNN is at 1.0000 AUC *already
  at δ = 0* and has nowhere to climb; its trend over the sweep is flat to very slightly
  negative ([REVIEW.md](REVIEW.md) §7 claims 10, 11, 14). The second half survives: the
  distance element falls monotonically from 0.954 to 0.868, a drop of **−0.086 AUC, 95 % CI
  [−0.096, −0.077]** over 2000 paired bootstrap resamples. But most of that drop comes from
  mixing fault types under one reach, not from the injection as such, and it depends on
  excluding the own-line 85–100 % band (§7 claim 9;
  `results/review_synth/h26_bootstrap_zone_full_fixed.json`).
- **Whether the scheme can be dropped into an existing relay's impedance element is still
  untested.** The sentence that used to stand here was inferred from the synthetic three-bus
  model; no EMT run with an injected δ exists anywhere in this repository (§7 claim 12). The
  underlying advice — anyone proposing auxiliary signals should measure what they do to the
  elements already in service — stands as advice, not as a result.
- **Engineered features are at ceiling without any injection**, at 0.996 AUC, within the
  sampled band; treating the own-line 85–100 % band as negatives drops them to 0.959 (§7 claim
  13). But **"deep learning is not the contribution" does not hold as stated**: the corrected
  CNN is ahead of the engineered model at every δ (§7 claim 14). The honest version is that
  both saturate this synthetic task, so it cannot rank them.

These numbers have been corrected three times, twice by strengthening the conventional
baseline (k0 compensation, then faulted-phase selection, both found by running on real EMT
data) and once by the review, which fixed the learned side. The downward trend in the
reactance element survived all three; the magnitudes did not, and the CNN trend reversed. See
[results/ZONE.md](results/ZONE.md) and [review/SYNTH_REPORT.md](review/SYNTH_REPORT.md).

## Third result: real EMT data (17 Sep 2026)

First run on public electromagnetic-transient data, EvEMTBench `benchmark-DoubleLine`
(110 kV, 50 Hz, stiff grid, **no inverters**: the control arm). Relay at bus 1, zone 1 at
85 % of a 20 km line. The archive is read without unpacking by `src/evemt.py`.

- **The distance element is validated on real data.** Bolted faults are located within 1.5 %
  of the line for all five fault types. This holds: the review reproduced the element to
  < 1e-13 Ω ([REVIEW.md](REVIEW.md) §3, §7 claim 16).
- ~~The zone-1 setting, with nothing learned, is perfectly secure.~~ **It is not.** The rule
  was only ever tested against faults *ahead* of the relay. Tested against faults at its own
  bus it trips **12 of 45 reverse bus faults at 40 ms**, including 60 % of the 1 Ω ones,
  because the sign of the loop reactance was doing duty as the directional element
  (`zone_model.py:206`, finding N2). §7 claim 17.
- **It is fully dependable for low-resistance faults, falling to 65 % at 40 Ω from the
  reactance effect of remote infeed.** Reproduced; the apparent resistance is ≈ 38 Ω, beyond
  the rule-based resistive reach of 19.9 Ω, so this is infeed physics and not only a setting
  error (§7 claim 18).
- ~~Learned detectors do not beat it (CNN AUC 0.852; engineered calls 15.6 % of 99 % faults).~~
  **Withdrawn by the author and superseded.** Under grouped folds the engineered + LR model
  reaches 96.7 % dependability with 10 % own-99 % trips (§7 claim 19).
- **Running on real data exposed a bug in our element**: no faulted-phase selection, which
  had let healthy loops win. Fixed, and the synthetic zone sweep above re-run with it.

Details: [results/REAL_DOUBLELINE.md](results/REAL_DOUBLELINE.md); corrected setting tables in
`results/review/real_zone_rerun.json`.

![real doubleline](results/real_doubleline.png)

## Fourth result: real EMT data with inverters (17 Sep 2026)

EvEMTBench `benchmark-TestGrid110kV`: six buses, two 30 GVA external grids, and two
grid-following inverters of 35 and 50 MVA. 2,435 simulations, read from an 8.9 GB archive by
streaming to disk.

- **The inverter current limiter is real and measured**, but it is not a hard ceiling at
  1.15–1.2 pu. The *median* |I₁| + |I₂| during faults is 1.07–1.18 pu; the p95 is ≈ 1.5 pu and
  the maximum ≈ 2.1 pu (`results/review/ibr_limiter_check.json`; [REVIEW.md](REVIEW.md) §7
  claim 20). Any uncertainty set built on "the inverter cannot exceed 1.2 pu" has to account
  for that tail.
- **The inverters are about 0.1 % of short-circuit capacity, so they change nothing.** Holds:
  85 MVA against two 30 GVA grids is 0.14 %, and the relay current ratios are unchanged (§7
  claim 21). The inverter-dominated regime this project is about is not in the public data, so
  simulation is required.
- **The hard case does appear, from remote infeed.** Relay B misses every 40 Ω fault on its
  line — reproduced, but the cause is split: partly the missing directional element (N2
  discards them because the apparent reactance is negative), partly infeed physics, with an
  apparent resistance ≈ 80 Ω at a study-model infeed factor of 3.9. 67N/67Q elements detect
  100 % of the unbalanced ones, without zone-selecting them (§7 claim 22). The 13 %
  overreach onto the next line at 10 Ω is also reproduced, and **goes to 0 % once a mimic
  filter and a directional quadrilateral are added** (§7 claim 23).
- ~~Learned detectors fail to generalise (82 % switching, 42 % at 99 %).~~ **Withdrawn by the
  author.** The grouped re-run gives 26 % switching trips for LR at relay B, and 0 % once the
  decision is supervised by a directional element (§7 claim 24).

Details: [results/REAL_TESTGRID.md](results/REAL_TESTGRID.md); corrected setting tables in
`results/review/real_zone_rerun.json`.

![relay B](results/real_testgrid_B.png)

## Fifth result: a fair ML comparison on the same real data (17 Sep 2026)

Causal windows of 10 to 50 ms, V/I scaled to each relay's reach, models chosen from the
literature (MLP, gradient boosting, random forest, engineered features), a realistic
measurement chain, thresholds from held-out scores, and training on one relay while testing
on another. This supersedes the learned-detector numbers in the third and fourth results.

- **The noise-free benchmark records leak the label.** Tree models predict in zone vs out of
  zone from pre-fault samples alone with AUC 1.000. With 0.1 % noise and a 16-bit ADC this
  drops to 0.48–0.55. Two corrections: the fingerprint is **0.12–0.26 V peak-to-peak, not
  0.01 V** (§7 claim 31), and the author's control window ended 5 ms early. A control window
  ending *at* inception still scores AUC 0.86–0.97, because `resample_poly` is zero-phase and
  leaks the fault **1.1–1.4 ms backwards** (H30). Earlier perfect scores are withdrawn; so is
  the implied "0.1 % noise makes it safe" (§7 claim 25).
- **On the relay it was tuned on, learning beats the fixed zone-1 setting** — but by much less
  than stated, and only against a baseline missing standard features. The rule's 15 % false
  trips were first-cycle DC offset: a mimic filter takes them to 0.7 %. Under grouped folds
  boosting gives 75.0 % dependability at 4/117 beyond-bus trips, against a **tuned
  quadrilateral at 67.8 %**. Engineered + LR reaches 95.3 % at the same 3/117. And
  unsupervised, boosting trips **92 % of relay-bus reverse faults** (§7 claim 26, H24).
  The honest form: *within one relay at one operating point, a supervised learned zone
  decision beats the best conventional rung on dependability at equal measured security.*
- **On a relay it never saw, the ranking partly survives but the trip threshold does not**:
  false trips of 13 to 100 %. This holds, and it is not a threshold-units artefact — replacing
  the threshold with a physical distance output and a fixed 0.85 trip still gives 21–59 %
  beyond-bus trips across relays (§7 claim 27, Q2).
- ~~A learned fault detector does not separate faults from switching at 20 ms (AUC 0.62–0.81).~~
  **This was a label artefact.** The stage-1 label counted every fault anywhere in the grid as
  positive, including faults the relay is not responsible for. With a responsibility-based
  label the same MLP reaches **AUC 0.90–0.99** (§7 claim 29, H28;
  `results/review/h28_stage1.json`).

Five method errors were found and fixed by the author along the way; all are listed in the
details, and all five were confirmed correct by the review ([REVIEW.md](REVIEW.md) §3). The
review found further ones — sibling leakage in the cross-validation, the resampling
look-ahead, windows anchored at true inception rather than at a causal starter, and the
missing directional element.

Details: [results/REAL_ML.md](results/REAL_ML.md), and the grouped re-runs in
[results/review/TABLES.md](results/review/TABLES.md).

![real ml](results/real_ml.png)

## Quick start

```bash
git clone https://github.com/anxious956/Power-CVXPY.git
cd Power-CVXPY
pip install -r requirements.txt
python src/aux_signal_toy.py weak_sg        # design tool, ~40 s, no GPU
python src/sweep_delta0.py                  # which regimes need a signal, ~1 min
python src/detect.py --quick                # detector comparison, fault vs load
python src/zone_detect.py --quick           # in-zone vs out-of-zone, the main experiment
```

Each run prints the ambiguous fault cases, the grid-search minimum, the CVXPY optimum, and writes a PNG and JSON into `results/`. Presets live at the bottom of `src/aux_model.py`; copy one and change a number to run your own case.

## Repository layout

```
src/        aux_model.py      two-bus sequence model, zonotope sets, LP separation test, presets
            aux_signal_toy.py grid search + Farkas-dual optimization + figure
            sweep_delta0.py   which regimes need a signal at all
            waveforms.py      time-domain relay waveforms from the same circuit, with confusers
            detect.py         detector comparison, fault vs load
            zone_model.py     three-bus model: protected line, adjacent line, remote infeed
            zone_detect.py    detector comparison, in-zone vs out-of-zone (synthetic)
            evemt.py          EvEMTBench loader: reads the .tar.gz without unpacking, caches
            real_zone.py      in-zone vs out-of-zone on real EMT data (doubleline, testgrid_A, testgrid_B)
            real_ml.py        fair ML vs zone-1 rule: causal windows, noise, cross-relay, two stages
results/    RESULTS.md   design-tool results, figures and JSON for every preset
            DETECTION.md fault vs load study, and why that negative was too easy
            ZONE.md      in-zone vs out-of-zone, synthetic
            REAL_DOUBLELINE.md, REAL_TESTGRID.md  the same on real EMT data
            REAL_ML.md        the fair ML comparison, with the errors found and fixed
            review/           re-run JSONs and TABLES.md from the technical review
            review_wp1/, review_synth/  the same for the design tool and synthetic pipeline
REVIEW.md   the technical review: findings, claim-by-claim verdict, roadmap
review/     WP1_REPORT.md   design-tool findings with commands and JSON keys
            SYNTH_REPORT.md synthetic-pipeline findings
papers/     README.md reading list with links, fetch.sh to download the open-access PDFs
docs/       PLAN.md   project plan, milestones, deliverables, target venues
            TEAM_BRIEF.md   onboarding note for the team
```

## Reading order

All 26 papers in `papers/` have been read; notes are in `papers/notes/`.

1. Everyone: [`papers/notes/SYNTHESIS.md`](papers/notes/SYNTHESIS.md), then Taylor &
   Domínguez-García, *Auxiliary Signal-Based Distance Protection in Inverter-Dominated Power
   Systems* (arXiv 2311.10880). It is five pages and it is the clearest statement of the idea.
2. Then the Sandia gap analysis, the sections on what is missing.
3. Per role: see [papers/README.md](papers/README.md). For how a distance element is
   actually set in practice, and for the instrument-transformer limits our assumptions rest
   on, read §H of that file (six SEL papers) and
   [`papers/notes/E_practitioner_settings.md`](papers/notes/E_practitioner_settings.md).

What the reading changed: three claims we might have made are already taken (incremental
negative-sequence detection, protection-aware inverter control validated on hardware, and ML
fault detection on inverter grids). What survives is that Taylor's method is the only one
offering a separation **guarantee** rather than a parameter sweep, that nobody has compared
the competing methods against each other, and that the auxiliary signal appears zero times in
~600 references of ML literature. The project is repositioned accordingly in
[`docs/PLAN.md`](docs/PLAN.md).

## Status

An independent technical review of this repository is complete and merged:
[REVIEW.md](REVIEW.md). Every headline claim above has been re-checked against it and corrected
in place; §7 carries the claim-by-claim verdict and §10 the roadmap. The re-run numbers live in
[results/review/TABLES.md](results/review/TABLES.md),
[review/WP1_REPORT.md](review/WP1_REPORT.md) and
[review/SYNTH_REPORT.md](review/SYNTH_REPORT.md).

- [x] Toy replication of the design method, three regimes — reproduces exactly, but the optima
      are local, not verified (§7 claim 5)
- [x] Literature collected, gap stated (26 papers held, 8 known gaps)
- [x] Waveform generator on the same circuit, with negative-sequence confusers
- [x] First detector comparison: naive threshold vs engineered features vs CNN
- [x] Three-bus model and the in-zone vs out-of-zone experiment
- [x] Error bars over seeds (in [results/ZONE.md](results/ZONE.md) and every review sweep)
- [x] EvEMTBench DoubleLine loaded straight from the archive; element validated on real EMT data
- [x] Inverter grid (TestGrid110kV) run: limiter measured, inverters too small to matter,
      remote-infeed problem reproduced
- [x] Fair ML comparison on real data: causal windows, measurement noise, cross-relay test,
      out-of-fold thresholds — superseded by the review's grouped re-runs
- [x] Rule with a data-tuned reach as the stricter baseline; noise, CVT and CT saturation sweep
      (ladder rungs R0–R4 / T1 / T2 and the Q1 instrument sweep)
- [x] Reproduce the Taylor 2023 example (|θ| vs fault location) with Clarabel — reproduces only
      with the appendix's printed matrix form; see `docs/notes/taylor_matrix_note.md` (§4 H16)
- [x] Independent technical review, landed on main
- [ ] Multiple-model Kalman filter detector (Pirani et al. 2022) in the comparison
- [ ] Sequence-domain front end for the learned detector
- [ ] Design tool that earns the word "guarantee": zone problem, sound source set, margin,
      current limit, global solver (§10 item 2)
- [ ] Report the pre-fault label leak and the resampling look-ahead to the EvEMTBench authors
- [ ] Inverter-dominated EMT grid (Baeckeland Simulink model, or our own)
- [ ] Advisor confirmed
- [ ] Team roles assigned
- [ ] EMT simulation test grid (Simulink or PSCAD)
- [ ] Embedded latency measurement
- [ ] Conference paper (target: NAPS 2027)

## License

Not yet chosen. Code is the team's; papers in `papers/` are linked, not redistributed.
