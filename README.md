# Power-CVXPY

**Auxiliary-signal fault detection in inverter-dominated grids: design, simulation, detection, hardware.**

NJIT Electrical and Computer Engineering, 2026–27. Supervised by **Prof. Joshua A. Taylor as
independent research** (agreed at the meeting of 6 Oct 2026). It is not the ECE 414 senior design
project, which is separate. Builds on Taylor's NSF project *Auxiliary Signal-Based Fault Detection in
Inverter-Dominated Power Systems* (NSF 2411925, with A. Domínguez-García, UIUC).

## The problem in one paragraph

A protective relay decides "there is a fault, open the breaker." For a century it did so by watching for a large current, because synchronous generators push 5 to 7 times rated current into a fault. Solar, wind and batteries connect through inverters, and inverters cap their fault current at roughly 1.1 to 1.2 pu. In an inverter-heavy grid a fault can look almost like normal load, and conventional relays misoperate.

## Taylor's idea, and what we add

Taylor and Domínguez-García (2025, 2026) model every unknown the relay faces (fault location, fault resistance, remote-end current, measurement noise) as a bounded set, compute the full region of measurements a fault can produce, and, when that region overlaps normal operation, have the inverter inject a small **auxiliary signal** (negative-sequence current) chosen by convex optimization to be as small as possible while guaranteeing separation. Their papers are analytical. Their conclusions name EMT-simulation evaluation as the next step.

This repository is that next step. It has moved since September, because the measurements moved
it: what changed and why is in [docs/PLAN.md](docs/PLAN.md) §1; the September results, with their
corrections, are kept in [docs/ARCHIVE.md](docs/ARCHIVE.md); the verdict on every claim ever made
here is the register in [REVIEW.md](REVIEW.md) §7.

**The question now:** where does a designed auxiliary signal earn its cost, and where does a passive
element, a channel or a grid-code requirement do the job instead? Four candidate uses have been
screened on an inverter-rich grid. Three look closed **in the screening**, with the limit stated
under the table:

| Candidate use for an injected signal | What the screening found (no injected data, see below) | Register row |
|---|---|---|
| Zone-1 **reach**: make in-zone faults separable from faults past the remote bus | **Not supported in the static model.** A δ the inverter can supply (0.4 pu) adds 2–4 points of separability; the inverter's whole current adds 8–13; longer lines help the passive measurement more | 42, 47 |
| **Direction** at inverter buses | **Not needed in the EMT data (no injection).** Passive superimposed-quantity elements settle it in the first cycle, forward and reverse, for unbalanced and three-phase faults | 44 |
| Direction when inverters **suppress negative sequence** | **In the static model, a current is needed, but a V2-referenced one** (IEEE 2800), not a δ fixed in advance — which failed at all 48 magnitudes and angles tried | 46 |
| Telling a remote **inverter trip** from a fault | **No injection can help** (EMT data, no injection, plus the static model); the tripping inverter is the only source on its feeder. The remedy is an inverter-status channel | 45 |

> **What none of this is.** No result in this repository comes from data with an injected signal.
> No public EMT dataset contains one, and we have not simulated one yet. The reach and longer-line
> verdicts come from a **static sequence model** of the feeder (optimistic for δ: each fault gets its
> best δ angle); the direction and inverter-trip verdicts come from EMT data **without** injection,
> plus the same static model. They say where a δ is unlikely to be needed. They do **not** say a δ
> fails, because that has not been tested. The EMT study with δ injected is what tests it.

## What we told Prof. Taylor, what he asked for, and what we owe him

Presented 6 Oct 2026 (`Taylor_meeting_v4.pptx`, kept out of the repository). Prof. Taylor supervises
the work; **both halves of it are ours: the convex design in CVXPY and the EMT evaluation.**

What the deck told him:

1. On a strong 110 kV grid a learned single-ended detector catches 95–99 % of in-zone faults at zero
   false trips; on the inverter-rich 20 kV feeder **nothing single-ended finds the zone boundary**
   (≤ 16 %), and only two-ended schemes, which need a channel, hold. *(EMT data, no injection.)*
2. In a **static model** of that feeder, a δ the inverter can afford barely separates in-zone from
   just-beyond faults (they are 0.3–0.6 Ω apart, so δ moves both almost equally, as his Theorem 1
   predicts); in the EMT data, direction was settled without a signal, and an inverter trip needs a
   channel. **None of this was measured with δ injected**; the deck's slide carries the same caveat.
3. **The room left for his method:** inverters that suppress negative sequence, longer lines, and
   grid-forming systems, and we asked to test it there.

**What he asked for after the deck:** he arranged the PSCAD licence, and asked us to **learn PSCAD**
(he does not use it himself) and to **study how inverters work**: their control, current limiting,
grid-following versus grid-forming behaviour. That is the immediate work; see [docs/PLAN.md](docs/PLAN.md) §5.

What we committed to, and where it stands:

| Promised | Status |
|---|---|
| A model test with **I₂-suppressing inverters** | **Done in the static model** ([PR #27](https://github.com/anxious956/Power-CVXPY/pull/27)). Direction fails there; a **V2-referenced** current with gain at small V2 (IEEE 2800) repairs it, a δ fixed in advance in the inverter's frame did not at any of 48 magnitudes and angles. Not yet checked in EMT |
| **Longer lines**, where we expected δ to separate more strongly | **Done in the static model (coarse), and it narrowed our own claim**: up to 3× line length, separability without δ rises 12–35 points while an affordable δ adds 1–11. He should hear this, because the deck offered it as a reason for optimism. Not yet checked in EMT |
| **An EMT study with δ injected**, ideally on his 14-bus grid-forming model | **Open, and the one that can actually test the method.** It is the critical path, after the PSCAD and inverter groundwork above ([docs/PSCAD.md](docs/PSCAD.md)) |

The four questions put to him in the deck are restated, with what we have learned since, in
[docs/PLAN.md](docs/PLAN.md) §7.

| # | Part | Status | Owner |
|---|------|--------|-------|
| 1 | **Design tool** | Largely done in the TAC25 formulation: current limit inside the problem, margin, sound source set, global solve ([results/DESIGN.md](results/DESIGN.md)). Open: multi-bus aggregation, limiter type in the uncertainty set | Asmar Hasanova |
| 2 | **Simulation** | **Critical path.** PSCAD 5.0.1 Educational, driven from Python and connected to our relay code; plan in [docs/PSCAD.md](docs/PSCAD.md) | Asmar Hasanova |
| 3 | **Detection** | Done on four grids with one protocol: conventional ladder, sequence-trajectory CNN, engineered features, re-implemented Hasan et al. (2026) SVM. Open: an IBR-appropriate ladder rung, MMKF | Asmar Hasanova |
| 4 | **Embedded** | Open: 87 µs on the laptop, no board, no causal end-to-end protocol | TBD |

## Where things stand (15 Oct 2026)

Every line below says what kind of data it comes from. **None of it comes from data with an injected
signal.**

| Area | Current result | Data | Details |
|---|---|---|---|
| Design tool | The TAC25 formulation: the current limit inside the problem, a margin in measurement units, a sound source set, a global solve. On the two-bus model only | static model | [results/DESIGN.md](results/DESIGN.md) |
| Detection, synchronous-dominated grid | A single-ended sequence-trajectory CNN covers 94.6–99.4 % of in-zone faults at relay A with 0–3 of 2,888 off-line trips; relay B is unstable (45–77 %). A settable quadrilateral covers 5–10 % | EMT, EvEMTBench adapt_grid TestGrid 110 kV, no injection | [results/ADAPTGRID.md](results/ADAPTGRID.md) |
| Detection, inverter-rich feeder | No single-ended detector exceeds 15.8 % at zero false trips; two-ended 67N/67Q schemes reach 75–82 % with a channel | EMT, EvEMTBench CIGRE MV 20 kV, no injection | [results/CIGREMV.md](results/CIGREMV.md) |
| Where δ could help | The four screened uses in the table above | static model, and EMT without injection | [results/CIGREMV.md](results/CIGREMV.md) §3 |
| Evaluation pitfalls | Noise-free benchmark records leak the zone label through the pre-fault waveform; zero-phase resampling leaks the fault ~1 ms backwards; sibling simulations leak across folds | EMT, EvEMTBench | [REVIEW.md](REVIEW.md), [results/REAL_ML.md](results/REAL_ML.md) |
| PSCAD | Driven from Python, output through the same relay code. Three shipped relay cases, 42 decisions, all right. Then the fault point swept across 50–98 % of a 100 km line: the A-G loop reads every point within +0.3 %, but **our faulted-phase selector releases the wrong loop inside zone 1**, so bolted A-G faults at 75–84 % and 10 Ω faults at 65–75 % are missed. No false trips | EMT, PSCAD examples, no inverter | [results/PSCAD_FIRST.md](results/PSCAD_FIRST.md) |

## Quick start

```bash
git clone https://github.com/anxious956/Power-CVXPY.git
cd Power-CVXPY
pip install -r requirements.txt
python src/aux_signal_toy.py weak_sg        # design tool on the two-bus model, ~40 s, no GPU
python src/zone_detect.py --quick           # in-zone vs out-of-zone on the synthetic three-bus model
```

The real-data runs need the EvEMTBench archives in `data/` (git-ignored; see `src/evemt.py`). The PSCAD
runs need PSCAD with its own Python and `mhi.pscad`; see [docs/PSCAD.md](docs/PSCAD.md):

```bash
"C:/Program Files/Python37/python.exe" src/pscad_sweep.py <work_dir> case1 "Fault location" 1 2 3 4
python src/pscad_table.py <work_dir>/runs "case1_Fault_location=*" case1 --ends 1:LINE1 2:LINE1
```

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
            dataset_facts.py  dataset fact sheet: labels, factorial structure, sibling leakage, units
            build_adaptgrid_cache.py, build_cigremv_cache.py  one streaming pass over an archive into data/
            torch_det.py      the sequence-trajectory CNN used by the real-data runs
            pscad_io.py       PSCAD output and line-constants reader
            pscad_sweep.py, pscad_location_sweep.py  drive PSCAD from Python (sliders, fault point)
            pscad_check.py, pscad_table.py           the distance element on PSCAD runs
src/review/ the review's experiments, one script per finding (h*.py, n2_*.py, q*_*.py), the
            conventional ladder and settings (ladder.py, setting_study.py, elements_fixed.py),
            grouped CV with keyed checkpoints (zone_cv.py, common.py), the design-tool re-derivation
            (wp1_*.py, tac25_*.py) and the adapt_grid runs (adaptgrid_*.py)
tests/      pytest suites for the real-data pipeline, the synthetic pipeline, WP1 and TAC25
results/    RESULTS.md   design-tool results, figures and JSON for every preset
            DESIGN.md    the design tool in the TAC25 formulation: certificate, soft limit,
                         structured error set, IEEE 2800 negative-sequence path
            DETECTION.md fault vs load study, and why that negative was too easy
            ZONE.md      in-zone vs out-of-zone, synthetic
            REAL_DOUBLELINE.md, REAL_TESTGRID.md  the same on real EMT data
            REAL_ML.md        the fair ML comparison, with the errors found and fixed
            DATASET_FACTS.md  fact sheet of the benchmark EMT data
            ADAPTGRID.md, ADAPTGRID_FACTS.md  the zone task on adapt_grid-TestGrid110kV (varied
                              loading and grounding, continuous R_f), at a zero-false-trip threshold
            CIGREMV.md, CIGREMV_FACTS.md      the same on the inverter-rich CIGRE MV 20 kV feeder, with
                              inverter-aware settings, boundary diagnostics and inverter headroom
            PSCAD_FIRST.md    the first PSCAD runs through our relay code; pscad/ holds their tables
            review/, review_wp1/, review_synth/, adaptgrid/, cigremv/  re-run JSONs and generated tables
REVIEW.md   the technical review: findings, claim-by-claim verdict, roadmap
review/     WP1_REPORT.md   design-tool findings with commands and JSON keys
            SYNTH_REPORT.md synthetic-pipeline findings
            bridge/         five specialist reviews and the lead review of running the design
                            method on CIGRE MV
logs/       run logs and checkpoints of the long experiments (ckpt/, fig/)
data/       EMT archives, caches and PSCAD working copies, git-ignored: nothing in this repository
            ships data
papers/     README.md reading list with links, fetch.sh to download the open-access PDFs;
            notes/ reading notes
docs/       PLAN.md   project plan, milestones, deliverables, target venues
            PSCAD.md  the simulation plan: license check, which model, what a run must produce
            ARCHIVE.md  the September results and the completed status items, kept verbatim
            TEAM_BRIEF.md   onboarding note for the team
            notes/    drafts (taylor_matrix_note.md: note to the author on the Fig. 3 matrix, not sent)
```

## Reading order

All 46 papers in `papers/` have been read; notes are in `papers/notes/` (36 PDFs in git, 10 paywalled ones held locally in the git-ignored `papers/library/`).

1. Everyone: [`papers/notes/SYNTHESIS.md`](papers/notes/SYNTHESIS.md), then Taylor &
   Domínguez-García, *Auxiliary Signal-Based Distance Protection in Inverter-Dominated Power
   Systems* (arXiv 2311.10880). It is five pages and it is the clearest statement of the idea.
2. Then the Sandia gap analysis, the sections on what is missing.
3. Per role: see [papers/README.md](papers/README.md). For how a distance element is
   actually set in practice, and for the instrument-transformer limits our assumptions rest
   on, read §H of that file (six SEL papers) and
   [`papers/notes/E_practitioner_settings.md`](papers/notes/E_practitioner_settings.md).

## Open items

Completed items are listed in [docs/ARCHIVE.md](docs/ARCHIVE.md). What is open, in order:

1. **Fix the faulted-phase selector** (sequence-angle selection): on a 100 km line it misses in-zone
   ground faults from 65–75 % on (REVIEW.md §7 row 48). Check the fix on the PSCAD sweep first, then
   re-run every earlier result with it.
2. **PSCAD groundwork** (Prof. Taylor's request): the remaining shipped examples, other fault types,
   load angles and source strengths on the sweep.
3. **How inverters work** (Prof. Taylor's request): a written note on grid-following and grid-forming
   control, current limiters and their negative-sequence behaviour, IEEE 2800 fault response.
4. **IRTSD in PSCAD**: reproduce one documented fault event, then add the auxiliary signal as an
   event type.
5. **The EMT study with δ injected**, which is the first test of the method itself; ideally also on the
   Baeckeland 14-bus grid-forming model.
6. An IBR-appropriate rung in the conventional baseline (offset quadrilateral, 32G / 32WI / TD32),
   before any inverter-dominated data.
7. Multiple-model Kalman filter detector (Pirani et al. 2022) in the comparison.
8. Report the pre-fault label leak and the resampling look-ahead to the EvEMTBench authors.
9. Embedded latency on a board.
10. Conference paper (target: NAPS 2027).

## License

Not yet chosen. Code is the team's; papers in `papers/` are linked, not redistributed.
