# Reading list: auxiliary-signal fault detection in inverter-dominated grids

> The 26 PDFs are committed here so the team has one place to read from. Most are
> open-access author copies: arXiv preprints, a US Department of Energy national
> laboratory report, and six conference papers and technical reports that Schweitzer
> Engineering Laboratories posts free on selinc.com. **Two are not open access** — the
> Taylor & Domínguez-García TAC paper (#1) and the Baeckeland TPWRS paper (#20) are
> paywalled IEEE journal articles, held here as personal copies obtained through the
> library; do not redistribute them. Every entry below carries its original link, and
> `bash papers/fetch.sh` re-downloads everything it legally can from source.

Senior design, advisor (proposed) Prof. Joshua A. Taylor, NJIT ECE.
Built by walking the reference lists of Taylor's own papers, so the set covers what he
builds on, not only what cites him. Last updated 17 Sep 2026: 26 papers held, 8 known gaps.

## A. Taylor's own line — read these first, in this order

| # | File | What it is | Why it matters to us |
|---|------|------------|----------------------|
| 1 | `Taylor_2025_Active_Fault_Detection_Static_Systems.pdf` | **The theoretical parent of the whole line.** Auxiliary-signal fault detection in static linear systems with quadratic constraints: a general design problem with operational constraints and both additive and multiplicative noise, relaxed and dualised into a semidefinite bilinear program. In the special case of additive uncertainty and no constraints it gives an *analytical lower bound* on the magnitude an auxiliary signal must have to guarantee detection. Worked example is distance protection with negative-sequence current. | Cited as [12] in the Geometry paper; the 2023 conference paper (#3) is its short version. This is the reference for a corrected design-tool formulation — see [`notes/F_taylor_tac_and_gfm_model.md`](notes/F_taylor_tac_and_gfm_model.md). IEEE TAC 70(8):5523–5529, 2025, DOI [10.1109/TAC.2024.3510612](https://doi.org/10.1109/TAC.2024.3510612). **Paywalled.** |
| 2 | `Pirani_Taylor_2022_Optimal_Active_Fault_Detection_Inverter_Grids.pdf` | Single inverter in the dq frame, balanced three-phase faults. Optimal perturbation sequence plus a Multiple Model Kalman Filter to detect the fault. | The relay-side detector we benchmark against. Its own future work: unbalanced faults, multiple converters and SGs. [arXiv 2209.06760](https://arxiv.org/abs/2209.06760) |
| 3 | `Taylor_2023_Auxiliary_Signal_Based_Distance_Protection_IBR.pdf` | 5-page conference version: the auxiliary-signal design problem for distance relays, reformulated by duality as a bilinear program and solved with the convex-concave procedure. Negative-sequence current as the signal. | The shortest, clearest statement of the whole idea. **Read this before the long papers.** [arXiv 2311.10880](https://arxiv.org/abs/2311.10880) |
| 4 | `Taylor_2025_Geometry_of_Distance_Protection.pdf` | Uncertainty aggregated by Minkowski sum, sets as zonotopes, signal designed via Farkas' lemma, bilinear program solved by ADMM. Worked example on a 14-bus system in CVXPY + Clarabel. | The design we reimplemented. Sections V and VI are the core. [arXiv 2510.04379](https://arxiv.org/abs/2510.04379) |
| 5 | `Taylor_2026_Distance_Characteristics_Incremental_Quantities.pdf` | Characteristics from incremental phasors, operating-point independent under a stationarity assumption the authors admit is weak for IBRs. | The open question we could measure: how far the characteristic drifts under real inverter control modes. [arXiv 2604.16668](https://arxiv.org/abs/2604.16668) |
| 6 | `Taylor_2026_Reachability_Time_Domain_Distance_Protection.pdf` | Drops phasors; reachable set of relay voltage and current in the time domain, per fault type. With Baeckeland. | Relevant to the latency question and to time-domain detectors. [arXiv 2608.19678](https://arxiv.org/abs/2608.19678) |

## B. The problem statement, from people who build relays

| # | File | What it is | Why |
|---|------|------------|-----|
| 7 | `Sandia_2024_Protection_100pct_Inverter_Dominated_Gap_Analysis.pdf` | SAND2024-04848, 48 pages. Sandia + Siemens + EPRI literature review and expert interviews on protecting a 100 % IBR system. | **The single best "what is unsolved" document.** Names seven knowledge gaps, including the absence of relay functions that respond correctly in IBR-dominated systems. Use it to justify the project. [OSTI 2429968](https://www.osti.gov/biblio/2429968) |
| 8 | `2025_Impact_of_Grid_Forming_Inverters_on_Protective_Relays.pdf` | How grid-forming inverters change what relays see. | Independent confirmation of the failure mode. [arXiv 2505.04177](https://arxiv.org/abs/2505.04177) |
| 9 | `2026_Impact_of_IBR_on_Protection_of_the_Electrical_Grid.pdf` | Recent survey of the same problem. | Related-work section. [arXiv 2603.27816](https://arxiv.org/abs/2603.27816) |

## C. Other ways to make the inverter help — the competition

| # | File | What it is | Relation to us |
|---|------|------------|----------------|
| 10 | `2025_Protection_Interoperable_Fault_Ride_Through_Control_GFM.pdf` | A fault-ride-through control designed so protection still works. | The alternative to injecting a signal: change the control instead. [arXiv 2504.21592](https://arxiv.org/abs/2504.21592) |
| 11 | `2022_Incremental_Negative_Sequence_Admittance_Fault_Detection_Inverter_Microgrids.pdf` | Passive method using incremental negative-sequence admittance. | Same physical quantity, no injection, no learning. [arXiv 2205.02962](https://arxiv.org/abs/2205.02962) |
| 12 | `2026_Incremental_Quantity_Distance_Protection_Grid_Forming_Inverters.pdf` | Analysis and enhancement of incremental-quantity distance protection with GFM inverters. | Overlaps Taylor #4 directly; read before duplicating. [arXiv 2604.10129](https://arxiv.org/abs/2604.10129) |

## D. Machine learning in this space — so we can state our novelty honestly

| # | File | What it is | Relation |
|---|------|------------|----------|
| 13 | `2024_ML_Protection_100pct_Inverter_Microgrids.pdf` | Decision-tree fault detection and classification, PSCAD, 100 % inverter microgrid. | ML fault detection on IBR grids is done. Our novelty is not "ML detects faults". [arXiv 2405.07310](https://arxiv.org/abs/2405.07310) |
| 14 | `2024_ML_Classification_Converter_Control_Mode.pdf` | Random forest tells grid-forming from grid-following using admittance measurements. Generalization is the weak point. | Option for a side chapter: infer the inverter type as an input to Taylor's sets. [arXiv 2401.10959](https://arxiv.org/abs/2401.10959) |
| 15 | `2025_Survey_AI_Fault_Detection_Classification_Location.pdf` | Survey of AI for detection, classification and location. | Related work. [arXiv 2507.10011](https://arxiv.org/abs/2507.10011) |

## E. Data and benchmarks — the route off synthetic data

| # | File | What it is |
|---|------|------------|
| 16 | `2026_PROTECT90_Fault_Dataset.pdf` | 9,022 EMT short-circuit episodes, 90 kV, eight relay locations, labelled by type, location and inception, deliberately low short-circuit power. Data on Zenodo, record 18418330. [arXiv 2606.24298](https://arxiv.org/abs/2606.24298) |
| 17 | `2026_Simulation_Dataset_Faults_Events_ML_Power_Systems.pdf` | Simulated faults **and non-fault events** for ML. [arXiv 2608.19777](https://arxiv.org/abs/2608.19777) |
| 18 | `2025_Benchmarking_ML_Fault_Classification_Localization_Protection.pdf` | Benchmark of ML models for fault classification and localization. [arXiv 2510.00831](https://arxiv.org/abs/2510.00831) |
| 19 | `2026_Latency_Aware_DL_Benchmark_Inverter_Dominated_Grids.pdf` | Latency-aware deep-learning benchmark in inverter-dominated grids. | Directly relevant to the embedded-latency work package. [arXiv 2605.17256](https://arxiv.org/abs/2605.17256) |
| 20 | `Baeckeland_2026_Unified_Model_Current_Limiting_GFM_Inverters.pdf` | Baeckeland, Yang & Seo. A unified model of grid-forming current limiters that captures several well-known limiter designs and shows their large-signal equivalence through a single *limiter angle*. Validated numerically, analytically, in EMT and on hardware. | **This is the source of the IEEE 14-bus grid-forming model that WP2 needs** — the Simulink system with five grid-forming inverters and current limiters that Taylor's 2026 reachability paper (#6) runs on. Getting the model itself is question 1 for the advisor in [`docs/PLAN.md`](../docs/PLAN.md). The limiter angle is also the natural parameter for the "limiter type as an uncertainty dimension" extension in WP1. See [`notes/F_taylor_tac_and_gfm_model.md`](notes/F_taylor_tac_and_gfm_model.md). IEEE TPWRS 41(1):198–213, 2026, DOI [10.1109/TPWRS.2025.3587224](https://doi.org/10.1109/TPWRS.2025.3587224). **Paywalled.** |

Also referenced, not papers: NREL PyPSCAD open grid-forming and grid-following models
(github.com/NREL/PyPSCAD), IRTSD IBR-rich transmission datakit (TechRxiv).

## F. Known gaps — what we do not have and why

Four entries left this table on 17 Sep 2026 because we now hold the papers: Taylor &
Domínguez-García 2025 (now #1), Kasztenny 2022 (now #22), Kasztenny, Fischer & Hooshyar 2026
(now #26) and Baeckeland, Yang & Seo 2026 (now #20). Eight remain.

| Reference | Why it matters | Status |
|---|---|---|
| Campbell & Nikoukhah, *Auxiliary Signal Design for Failure Detection*, Princeton UP 2004 | Where the auxiliary-signal idea comes from. Geometry ref [10]. | Book. Library. |
| Baeckeland, Venkatramanan, Dhople & Kleemann, *On the distance protection of power grids dominated by grid-forming inverters*, ISGT Europe 2022 | Geometry ref [5]. Baeckeland is a coauthor on Taylor's 2026 reachability paper. | IEEE only, not on arXiv. |
| IEEE Std 2800-2022 | The standard that mandates negative-sequence injection, i.e. the reason the auxiliary signal is deployable at all. | Standard. NJIT library or IEEE subscription. |
| Baeckeland PhD thesis, KU Leuven 2022 | Chapter 3 carries the 14-bus line data used in the Geometry example | KU Leuven repository |
| Blanchini et al. 2017, SIAM J. Control Optim. | The duality argument the 2023 paper builds on | Journal |
| Banaiemoqadam, Hooshyar & Azzouz 2020, dual current control | Prior art: make inverters relay-friendly by control instead of injection | IEEE TPWRD 36(5) |
| Karimi, Yazdani & Iravani 2008 | Earliest use of negative-sequence injection we found, for islanding detection | IEEE TPEL 23(1) |
| Adhikari, Brahma & Gadde 2021, source-agnostic time-domain distance relay | Closest competitor to the reachability paper | IEEE TPWRD 37(5) |

## G. Notes

All 26 papers have been read in full. Notes live in `papers/notes/`:

- **`SYNTHESIS.md`** — start here. What the whole set says, what we can and cannot claim,
  which dataset to use, and the project restated in one paragraph.
- `A_taylor_line.md` — Taylor's five papers, with the reproducible examples, every parameter
  of the 14-bus test system, the measured detection times, and the openings the authors name.
- `B_problem_statement.md` — the Sandia gap analysis and two impact studies. Contains the
  six "No literature found" entries and the current-limiter angle measurements.
- `C_competing_methods.md` — the three alternatives, and exactly what they cost us in claims.
- `D_ml_and_datasets.md` — the ML literature and a side-by-side of the four datasets.
- `E_practitioner_settings.md` — the six SEL papers of section H checked item by item against
  the review's "not verified against primary sources" list: zone-1 reach and resistive reach,
  load encroachment, arc resistance, directional sector boundaries, CVT transient limits, the
  steady-state error budget, CT/VT class limits, and negative-sequence polarisation on IBR-fed
  lines. Each marked verified / contradicted / still open, with the ladder setting or Q1
  assumption it changes.
- `F_taylor_tac_and_gfm_model.md` — what the 2025 TAC paper (#1) adds over the 2023 conference
  version for a corrected design-tool formulation, and what the Baeckeland current-limiting
  model (#20) gives for an inverter fault-response uncertainty dimension and for WP2.

## H. Practitioner references for settings and instrument transformers

Six Schweitzer Engineering Laboratories papers, all free from selinc.com. They exist in this
list for one reason: the review found that a large part of what looked like a machine-learning
advantage was really a baseline missing standard relay features, and that most of our settings
and instrument-transformer assumptions were never checked against a primary source
([`REVIEW.md`](../REVIEW.md) §4 H8/N2, §6 Q1, §12 "Not verified against primary sources").
These are the primary sources. What each one settles, and what it does not, is worked through
in [`notes/E_practitioner_settings.md`](notes/E_practitioner_settings.md).

| # | File | What it is | Why it matters to us |
|---|------|------------|----------------------|
| 21 | `2021_SEL_Settings_Considerations_Distance_Elements.pdf` | Kasztenny, *Settings considerations for distance elements in line protection applications*, 48th WPRC 2021. The settings rules themselves: reach, resistive reach, load encroachment, the quadrilateral, and why each limit is where it is. | The reference for the ladder's R2/T2 rungs and for the load-encroachment limit (31.8 Ω) that our own reach was capped by. [selinc.com/api/download/133569](https://selinc.com/api/download/133569/) |
| 22 | `2022_SEL_Distance_Elements_Near_Unconventional_Sources.pdf` | Kasztenny, *Distance elements for line protection applications near unconventional sources*, 58th MIPSYCON 2022. The practitioner's statement of the IBR problem, by the person who designs the relays. Geometry ref [4]. | Bears directly on ladder rung R3: what it says about negative-sequence polarisation on IBR-fed lines decides whether an I₂-polarised reactance line is usable at all. [selinc.com/api/download/134587](https://selinc.com/api/download/134587/) |
| 23 | `2023_SEL_Security_Criterion_Zone1_High_SIR_CCVT.pdf` | Kasztenny & Chowdhury, *Security criterion for distance zone 1 applications in high SIR systems with CCVTs*, 50th WPRC 2023. | The zone-1 security criterion we did not have. Directly relevant to Q1: our CVT sweep excluded the low-C model that fails class T1, so the worst case for transient overreach was never covered. [selinc.com/api/download/138266](https://selinc.com/api/download/138266/) |
| 24 | `1996_SEL_CVT_Transient_Overreach_Distance_Relaying.pdf` | Hou & Roberts, *Capacitive voltage transformers: transient overreach concerns and solutions for distance relaying*, 1995/1996, revised 2010. | The classic statement of CVT transient overreach. Our `cvt_filter` model is a textbook circuit with no vendor validation; this is what to check it against. [selinc.com/api/download/2398](https://selinc.com/api/download/2398/) |
| 25 | `2012_SEL_CVT_Transients_Revisited.pdf` | Costello & Zimmerman, *CVT transients revisited — distance, directional overcurrent, and communications-assisted tripping concerns*, 65th CPRE 2012. | The modern follow-up, and it extends the concern to directional overcurrent, which our ladder now relies on (32P/32Q, 67N/67Q). [selinc.com/api/download/99416](https://selinc.com/api/download/99416/) |
| 26 | `2026_SEL_From_Complexity_to_Consistency_IBR_Fault_Response.pdf` | Kasztenny, Fischer & Hooshyar, *From complexity to consistency: reframing fault response requirements for inverter-based resources*, SEL 2026. Argues IEEE 2800's phasor-based specification is the wrong frame and proposes a time-domain one. | Cited by **both** of Taylor's 2026 papers as the reason to hope inverters will become predictable. If its framing is adopted, the uncertainty set WP1 has to cover changes shape. [selinc.com/api/download/141627](https://selinc.com/api/download/141627/) |

## I. Reading order by role

1. **Everyone:** #3 in full (it is five pages), then #7 sections on the gaps.
2. **Optimization:** #4 sections V and VI, then #1 (the TAC paper, now held).
3. **Simulation:** #2 section II for the inverter model, #12, #20 for the 14-bus grid-forming model, NREL PyPSCAD README.
4. **Detection:** #13, #18, #19, #11, then #21 and #22 for how the settings are actually made.
5. **Embedded:** #19, #6.

## J. What is and is not in the literature, as of 16 Sep 2026

- ML fault detection on inverter grids: many papers (#13, #18, #15).
- Auxiliary-signal fault detection: only Taylor's line (#1, #2, #3, #4), all model-based, no learning.
- Learned detection of the auxiliary signal itself, and a measured "how small can the signal be in practice" curve: not found.
- Latency of auxiliary-signal detectors on embedded hardware: not found.
- Measured drift of the incremental characteristic under inverter control modes: named as an open assumption in #5, not measured.
- Whether the auxiliary signal *harms* the conventional distance element: not found, and our own preliminary result suggests it does.
