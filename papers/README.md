# Reading list: auxiliary-signal fault detection in inverter-dominated grids

> PDFs are **not** committed to this repository. Run `bash papers/fetch.sh` after cloning to
> download the open-access copies into this folder. Every entry below carries its link.

Senior design, advisor (proposed) Prof. Joshua A. Taylor, NJIT ECE.
Built by walking the reference lists of Taylor's own papers, so the set covers what he
builds on, not only what cites him. Last updated 16 Sep 2026: 18 papers held, 6 known gaps.

## A. Taylor's own line — read these first, in this order

| # | File | What it is | Why it matters to us |
|---|------|------------|----------------------|
| 1 | `Pirani_Taylor_2022_Optimal_Active_Fault_Detection_Inverter_Grids.pdf` | Single inverter in the dq frame, balanced three-phase faults. Optimal perturbation sequence plus a Multiple Model Kalman Filter to detect the fault. | The relay-side detector we benchmark against. Its own future work: unbalanced faults, multiple converters and SGs. [arXiv 2209.06760](https://arxiv.org/abs/2209.06760) |
| 2 | `Taylor_2023_Auxiliary_Signal_Based_Distance_Protection_IBR.pdf` | 5-page conference version: the auxiliary-signal design problem for distance relays, reformulated by duality as a bilinear program and solved with the convex-concave procedure. Negative-sequence current as the signal. | The shortest, clearest statement of the whole idea. **Read this before the long papers.** [arXiv 2311.10880](https://arxiv.org/abs/2311.10880) |
| 3 | `Taylor_2025_Geometry_of_Distance_Protection.pdf` | Uncertainty aggregated by Minkowski sum, sets as zonotopes, signal designed via Farkas' lemma, bilinear program solved by ADMM. Worked example on a 14-bus system in CVXPY + Clarabel. | The design we reimplemented. Sections V and VI are the core. [arXiv 2510.04379](https://arxiv.org/abs/2510.04379) |
| 4 | `Taylor_2026_Distance_Characteristics_Incremental_Quantities.pdf` | Characteristics from incremental phasors, operating-point independent under a stationarity assumption the authors admit is weak for IBRs. | The open question we could measure: how far the characteristic drifts under real inverter control modes. [arXiv 2604.16668](https://arxiv.org/abs/2604.16668) |
| 5 | `Taylor_2026_Reachability_Time_Domain_Distance_Protection.pdf` | Drops phasors; reachable set of relay voltage and current in the time domain, per fault type. With Baeckeland. | Relevant to the latency question and to time-domain detectors. [arXiv 2608.19678](https://arxiv.org/abs/2608.19678) |

## B. The problem statement, from people who build relays

| # | File | What it is | Why |
|---|------|------------|-----|
| 6 | `Sandia_2024_Protection_100pct_Inverter_Dominated_Gap_Analysis.pdf` | SAND2024-04848, 48 pages. Sandia + Siemens + EPRI literature review and expert interviews on protecting a 100 % IBR system. | **The single best "what is unsolved" document.** Names seven knowledge gaps, including the absence of relay functions that respond correctly in IBR-dominated systems. Use it to justify the project. [OSTI 2429968](https://www.osti.gov/biblio/2429968) |
| 7 | `2025_Impact_of_Grid_Forming_Inverters_on_Protective_Relays.pdf` | How grid-forming inverters change what relays see. | Independent confirmation of the failure mode. [arXiv 2505.04177](https://arxiv.org/abs/2505.04177) |
| 8 | `2026_Impact_of_IBR_on_Protection_of_the_Electrical_Grid.pdf` | Recent survey of the same problem. | Related-work section. [arXiv 2603.27816](https://arxiv.org/abs/2603.27816) |

## C. Other ways to make the inverter help — the competition

| # | File | What it is | Relation to us |
|---|------|------------|----------------|
| 9 | `2025_Protection_Interoperable_Fault_Ride_Through_Control_GFM.pdf` | A fault-ride-through control designed so protection still works. | The alternative to injecting a signal: change the control instead. [arXiv 2504.21592](https://arxiv.org/abs/2504.21592) |
| 10 | `2022_Incremental_Negative_Sequence_Admittance_Fault_Detection_Inverter_Microgrids.pdf` | Passive method using incremental negative-sequence admittance. | Same physical quantity, no injection, no learning. [arXiv 2205.02962](https://arxiv.org/abs/2205.02962) |
| 11 | `2026_Incremental_Quantity_Distance_Protection_Grid_Forming_Inverters.pdf` | Analysis and enhancement of incremental-quantity distance protection with GFM inverters. | Overlaps Taylor #4 directly; read before duplicating. [arXiv 2604.10129](https://arxiv.org/abs/2604.10129) |

## D. Machine learning in this space — so we can state our novelty honestly

| # | File | What it is | Relation |
|---|------|------------|----------|
| 12 | `2024_ML_Protection_100pct_Inverter_Microgrids.pdf` | Decision-tree fault detection and classification, PSCAD, 100 % inverter microgrid. | ML fault detection on IBR grids is done. Our novelty is not "ML detects faults". [arXiv 2405.07310](https://arxiv.org/abs/2405.07310) |
| 13 | `2024_ML_Classification_Converter_Control_Mode.pdf` | Random forest tells grid-forming from grid-following using admittance measurements. Generalization is the weak point. | Option for a side chapter: infer the inverter type as an input to Taylor's sets. [arXiv 2401.10959](https://arxiv.org/abs/2401.10959) |
| 14 | `2025_Survey_AI_Fault_Detection_Classification_Location.pdf` | Survey of AI for detection, classification and location. | Related work. [arXiv 2507.10011](https://arxiv.org/abs/2507.10011) |

## E. Data and benchmarks — the route off synthetic data

| # | File | What it is |
|---|------|------------|
| 15 | `2026_PROTECT90_Fault_Dataset.pdf` | 9,022 EMT short-circuit episodes, 90 kV, eight relay locations, labelled by type, location and inception, deliberately low short-circuit power. Data on Zenodo, record 18418330. [arXiv 2606.24298](https://arxiv.org/abs/2606.24298) |
| 16 | `2026_Simulation_Dataset_Faults_Events_ML_Power_Systems.pdf` | Simulated faults **and non-fault events** for ML. [arXiv 2608.19777](https://arxiv.org/abs/2608.19777) |
| 17 | `2025_Benchmarking_ML_Fault_Classification_Localization_Protection.pdf` | Benchmark of ML models for fault classification and localization. [arXiv 2510.00831](https://arxiv.org/abs/2510.00831) |
| 18 | `2026_Latency_Aware_DL_Benchmark_Inverter_Dominated_Grids.pdf` | Latency-aware deep-learning benchmark in inverter-dominated grids. | Directly relevant to the embedded-latency work package. [arXiv 2605.17256](https://arxiv.org/abs/2605.17256) |

Also referenced, not papers: NREL PyPSCAD open grid-forming and grid-following models
(github.com/NREL/PyPSCAD), IRTSD IBR-rich transmission datakit (TechRxiv).

## F. Known gaps — what we do not have and why

| Reference | Why it matters | Status |
|---|---|---|
| Taylor & Domínguez-García, *Active Fault Detection in Static Systems*, IEEE TAC 70(8):5523–5529, 2025 | The theoretical parent of the whole line. Cited as [12] in the Geometry paper. | Paywalled. **Get through the NJIT library.** The 2023 conference paper (#2 above) covers much of it. |
| Campbell & Nikoukhah, *Auxiliary Signal Design for Failure Detection*, Princeton UP 2004 | Where the auxiliary-signal idea comes from. Geometry ref [10]. | Book. Library. |
| Kasztenny, *Distance elements for line protection applications near unconventional sources*, 2022 | The practitioner's statement of the problem, by the person who designs SEL relays. Geometry ref [4]. | IEEE / SEL. Try selinc.com, which posts many of its conference papers free. |
| Kasztenny, Fischer & Hooshyar, *From complexity to consistency: reframing fault response requirements for IBRs*, SEL tech report 2026 | Argues IEEE 2800's phasor-based specification is the wrong frame and proposes a time-domain one. Very recent, directly about the signal our project depends on. | SEL tech report. Try selinc.com. |
| Baeckeland, Venkatramanan, Dhople & Kleemann, *On the distance protection of power grids dominated by grid-forming inverters*, ISGT Europe 2022 | Geometry ref [5]. Baeckeland is a coauthor on Taylor's 2026 reachability paper. | IEEE only, not on arXiv. |
| IEEE Std 2800-2022 | The standard that mandates negative-sequence injection, i.e. the reason the auxiliary signal is deployable at all. | Standard. NJIT library or IEEE subscription. |

## G. Reading order by role

1. **Everyone:** #2 in full (it is five pages), then #6 sections on the gaps.
2. **Optimization:** #3 sections V and VI, then the TAC paper from the library.
3. **Simulation:** #1 section II for the inverter model, #11, NREL PyPSCAD README.
4. **Detection:** #12, #17, #18, #10.
5. **Embedded:** #18, #5.

## H. What is and is not in the literature, as of 16 Sep 2026

- ML fault detection on inverter grids: many papers (#12, #17, #14).
- Auxiliary-signal fault detection: only Taylor's line (#1, #2, #3), all model-based, no learning.
- Learned detection of the auxiliary signal itself, and a measured "how small can the signal be in practice" curve: not found.
- Latency of auxiliary-signal detectors on embedded hardware: not found.
- Measured drift of the incremental characteristic under inverter control modes: named as an open assumption in #4, not measured.
- Whether the auxiliary signal *harms* the conventional distance element: not found, and our own preliminary result suggests it does.
