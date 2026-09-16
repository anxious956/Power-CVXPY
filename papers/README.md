# Reading list: auxiliary-signal fault detection in inverter-dominated grids

> PDFs are **not** committed to this repository. Run `bash papers/fetch.sh` after cloning to download
> the open-access (arXiv) versions into this folder. Direct links are in the tables below.

Senior design, advisor Prof. Joshua A. Taylor (NJIT ECE). Collected 13 Sep 2026.
All files are open-access arXiv versions. One core paper is not open access and must be read via NJIT library (see "Not downloaded").

## A. Taylor's own line (read these first, in this order)

| # | File | What it is | Why it matters to us |
|---|------|------------|----------------------|
| 1 | Pirani_Taylor_2022_Optimal_Active_Fault_Detection_Inverter_Grids.pdf | Single inverter, dq frame, balanced 3-phase faults. Optimal perturbation sequence + Multiple Model Kalman Filter detects fault vs no-fault. | The relay-side detector we benchmark against. Its stated future work: unbalanced faults, multiple converters + SGs. |
| 2 | Taylor_2025_Geometry_of_Distance_Protection.pdf | Uncertainty (fault location, resistance, remote current) aggregated by Minkowski sum; sets as zonotopes; auxiliary signal designed via Farkas' lemma; bilinear program solved by ADMM. Negative-sequence injection as the example signal (IEEE 2800). | The auxiliary-signal design we implement in CVXPY. Section VI-B and VI-D are the core. |
| 3 | Taylor_2026_Distance_Characteristics_Incremental_Quantities.pdf | Characteristics from incremental phasors; operating-point independent under a stationarity assumption. Authors admit the assumption is weak for IBRs. | The open question we can measure: how much does the characteristic drift under real inverter control modes. |
| 4 | Taylor_2026_Reachability_Time_Domain_Distance_Protection.pdf | Drops phasors; reachable set of relay (v, i) in time domain per fault type. | Relevant for the latency question and for time-domain detectors. |

**Not downloaded (IEEE TAC 2025, paywalled):** Taylor & Dominguez-Garcia, "Active Fault Detection in Static Systems," IEEE Trans. Automatic Control 70(8):5523-5529. General theory of minimally disruptive auxiliary signals under set-based uncertainty. Get it through the NJIT library; it is the theoretical parent of #2.

## B. Closest related work (know these to state our novelty honestly)

| # | File | What it is | Relation to us |
|---|------|------------|----------------|
| 5 | 2022_Incremental_Negative_Sequence_Admittance_Fault_Detection_Inverter_Microgrids.pdf | Passive method: incremental negative-sequence admittance for fault detection in inverter microgrids. | Same physical signal (negative sequence), no injection, no learning. |
| 6 | 2026_Incremental_Quantity_Distance_Protection_Grid_Forming_Inverters.pdf | Analysis of incremental-quantity distance protection with grid-forming inverters. | Directly overlaps Taylor #3; read to avoid duplicating. |
| 7 | 2024_ML_Protection_100pct_Inverter_Microgrids.pdf | Decision-tree fault detection/classification, PSCAD, 100% inverter microgrid, 7 fault types. | Shows ML fault detection on IBR grids is done. Our novelty is not "ML detects faults." |
| 8 | 2024_ML_Classification_Converter_Control_Mode.pdf | Random forest classifies grid-forming vs grid-following from admittance measurements. Generalization is the weak point. | Option for a side chapter: infer inverter type as input to Taylor's sets. |

## C. Datasets and benchmarks (for the backup plan and pretraining)

| # | File | What it is |
|---|------|------------|
| 9 | 2026_PROTECT90_Fault_Dataset.pdf | 9,022 EMT fault episodes, 90 kV, 8 relay locations, deliberately low short-circuit power. Zenodo 18418330. |
| 10 | 2026_Simulation_Dataset_Faults_Events_ML_Power_Systems.pdf | Simulated faults and non-fault events for ML. |
| 11 | 2025_Benchmarking_ML_Fault_Classification_Localization_Protection.pdf | Benchmark of ML models for fault classification and localization. |
| 12 | 2026_Latency_Aware_DL_Benchmark_Inverter_Dominated_Grids.pdf | Latency-aware DL benchmark for attack and fault classification in inverter-dominated grids. Relevant to our embedded-latency chapter. |
| 13 | 2025_Survey_AI_Fault_Detection_Classification_Location.pdf | Survey of AI methods for detection, classification, location. Use for the related-work section. |

Not downloaded but referenced: IRTSD (IBR-rich transmission system datakit, TechRxiv), NREL PyPSCAD open grid-forming/grid-following models (GitHub NREL/PyPSCAD), IEEE Std 2800 (negative-sequence injection requirement).

## D. What is and is not in the literature (as of 13 Sep 2026)

- ML fault detection on inverter grids: many papers (7, 11, 13).
- Auxiliary-signal fault detection: only Taylor's line (1, 2), all model-based, no learning.
- Learned detection of the auxiliary signal itself, and the "how small can the signal be in practice" curve: not found.
- Latency of aux-signal detectors on embedded hardware: not found.
- Measured drift of the incremental characteristic under inverter control modes: Taylor names it as an open assumption in #3; not measured.

## E. Reading order for the team

1. Everyone: Taylor #2 abstract + Sections I, II, VI. Then #1 abstract + Section I.
2. Optimization person: #2 in full, then the TAC paper from the library.
3. Simulation person: #1 Section II (inverter model), #6, NREL PyPSCAD README.
4. Protection/ML person: #7, #11, #12, #5.
5. Embedded person: #12, #4.

## Direct links (open access)

| File stem | arXiv |
|---|---|
| Pirani_Taylor_2022_Optimal_Active_Fault_Detection_Inverter_Grids | https://arxiv.org/abs/2209.06760 |
| Taylor_2025_Geometry_of_Distance_Protection | https://arxiv.org/abs/2510.04379 |
| Taylor_2026_Distance_Characteristics_Incremental_Quantities | https://arxiv.org/abs/2604.16668 |
| Taylor_2026_Reachability_Time_Domain_Distance_Protection | https://arxiv.org/abs/2608.19678 |
| 2022_Incremental_Negative_Sequence_Admittance_Fault_Detection_Inverter_Microgrids | https://arxiv.org/abs/2205.02962 |
| 2026_Incremental_Quantity_Distance_Protection_Grid_Forming_Inverters | https://arxiv.org/abs/2604.10129 |
| 2024_ML_Protection_100pct_Inverter_Microgrids | https://arxiv.org/abs/2405.07310 |
| 2024_ML_Classification_Converter_Control_Mode | https://arxiv.org/abs/2401.10959 |
| 2026_PROTECT90_Fault_Dataset | https://arxiv.org/abs/2606.24298 |
| 2026_Simulation_Dataset_Faults_Events_ML_Power_Systems | https://arxiv.org/abs/2608.19777 |
| 2025_Benchmarking_ML_Fault_Classification_Localization_Protection | https://arxiv.org/abs/2510.00831 |
| 2026_Latency_Aware_DL_Benchmark_Inverter_Dominated_Grids | https://arxiv.org/abs/2605.17256 |
| 2025_Survey_AI_Fault_Detection_Classification_Location | https://arxiv.org/abs/2507.10011 |

Other resources: NREL PyPSCAD open inverter models (https://github.com/NREL/PyPSCAD),
PROTECT-90 data on Zenodo (record 18418330), IEEE Std 2800 (negative-sequence injection requirement).
