# Reading list: auxiliary-signal fault detection in inverter-dominated grids

> 34 PDFs are committed here so the team has one place to read from. All of them are
> open access: arXiv preprints, US Department of Energy national laboratory reports,
> conference papers and technical reports that Schweitzer Engineering Laboratories posts
> free on selinc.com, and journal articles under Creative Commons licences. **Paywalled
> papers are not in git**, because the repository is public. That covers the Taylor &
> Domínguez-García TAC paper (#1), the Baeckeland TPWRS paper (#20) and eight in section K.
> Personal library copies (NJIT) sit in `papers/library/`, which git ignores; do not
> redistribute them. #1 and #20 were committed until 30 Sep 2026 and remain in the history.
> Every entry below carries its original link, and `bash papers/fetch.sh` re-downloads
> everything it legally can from source.

Senior design, advisor (proposed) Prof. Joshua A. Taylor, NJIT ECE.
Built by walking the reference lists of Taylor's own papers, so the set covers what he
builds on, not only what cites him. Last updated 30 Sep 2026: 46 papers held (34 in git, 10 paywalled in `papers/library/`, 2 large open-access ones fetched by `fetch.sh`), 8 known gaps (section F) and the papers to fetch in section K.

## A. Taylor's own line — read these first, in this order

| # | File | What it is | Why it matters to us |
|---|------|------------|----------------------|
| 1 | `library/Taylor_2025_Active_Fault_Detection_Static_Systems.pdf` (not in git) | **The theoretical parent of the whole line.** Auxiliary-signal fault detection in static linear systems with quadratic constraints: a general design problem with operational constraints and both additive and multiplicative noise, relaxed and dualised into a semidefinite bilinear program. In the special case of additive uncertainty and no constraints it gives an *analytical lower bound* on the magnitude an auxiliary signal must have to guarantee detection. Worked example is distance protection with negative-sequence current. | Cited as [12] in the Geometry paper; the 2023 conference paper (#3) is its short version. This is the reference for a corrected design-tool formulation — see [`notes/F_taylor_tac_and_gfm_model.md`](notes/F_taylor_tac_and_gfm_model.md). IEEE TAC 70(8):5523–5529, 2025, DOI [10.1109/TAC.2024.3510612](https://doi.org/10.1109/TAC.2024.3510612). **Paywalled.** |
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
| 20 | `library/Baeckeland_2026_Unified_Model_Current_Limiting_GFM_Inverters.pdf` (not in git) | Baeckeland, Yang & Seo. A unified model of grid-forming current limiters that captures several well-known limiter designs and shows their large-signal equivalence through a single *limiter angle*. Validated numerically, analytically, in EMT and on hardware. | **This is the source of the IEEE 14-bus grid-forming model that WP2 needs** — the Simulink system with five grid-forming inverters and current limiters that Taylor's 2026 reachability paper (#6) runs on. Getting the model itself is question 1 for the advisor in [`docs/PLAN.md`](../docs/PLAN.md). The limiter angle is also the natural parameter for the "limiter type as an uncertainty dimension" extension in WP1. See [`notes/F_taylor_tac_and_gfm_model.md`](notes/F_taylor_tac_and_gfm_model.md). IEEE TPWRS 41(1):198–213, 2026, DOI [10.1109/TPWRS.2025.3587224](https://doi.org/10.1109/TPWRS.2025.3587224). **Paywalled.** |

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

Section K (20 papers, read in full on 30 Sep 2026; the key numbers were checked against the PDFs):

- `G1_mechanism_industry.md` — why negative-sequence directional and phase-selection elements fail next
  to IBRs (PES-TR81, Haddadi, Chowdhury & Fischer Parts I and II, PNNL review), and the relay-side fixes.
- `G2_control_remedies.md` — the five controllers that make an inverter look like a synchronous machine
  to the relay (Yang/Popov, Azzouz/Hooshyar, Medhat/Azzouz, Banaiemoqadam), and what IEEE 2800 already buys (Davi).
- `G3_injection_distribution.md` — injection-based protection (Saleh, Mohammadhassani, Yang/Dysko), a
  distribution directional element (Opoku), and the 87L reference (SEL).
- `G4_theory.md` — guaranteed active fault diagnosis (Scott, Raimondo, Nikoukhah, Xu) and why a bounded
  signal cannot separate hypotheses whose sensitivity to it is nearly equal; the Sandia 2020 study.

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
- Auxiliary-signal fault detection: only Taylor's line (#1, #2, #3, #4), all model-based, no learning. **Narrowed 30 Sep 2026 (section K):**
  in protection, injections designed or fixed for the purpose exist outside Taylor's line. Saleh et al. 2021 choose a harmonic pattern by
  optimisation so relays tell forward from reverse. Yang, Dysko et al. 2024 inject a fixed 0.3 pu of I2 to find the faulted section. IEEE 2800
  itself requires I2 injection. What remains specific to Taylor's line is the set-based design with a separation guarantee.
- Learned detection of the auxiliary signal itself, and a measured "how small can the signal be in practice" curve: not found. **Narrowed 30 Sep
  2026:** Mohammadhassani et al. 2021 (#34) learn direction from an injected harmonic signal with an SVM, trained on two bolted faults.
- Latency of auxiliary-signal detectors on embedded hardware: not found.
- Measured drift of the incremental characteristic under inverter control modes: named as an open assumption in #5, not measured.
- Whether the auxiliary signal *harms* the conventional distance element: not found, and our own preliminary result suggests it does.

## K. Added 29 Sep 2026: direction and fault type at inverter buses, and guaranteed active diagnosis

The CIGRE MV results moved the question. A δ the inverter can supply barely resolves zone-1 reach
(bridge step B1, [`REVIEW.md`](../REVIEW.md) §7 row 42), while at the inverter buses the negative-sequence
directional element is wrong in both directions ([`results/CIGREMV.md`](../results/CIGREMV.md) §3). This
section covers that second problem and the theory behind the first. Every entry was checked against its
Crossref record and abstract; the ★ entries were also read at the passages quoted.

| # | File | What it is | Why it matters to us |
|---|------|------------|----------------------|
| 27 ★ | `2020_PES_TR81_Protection_Challenges_IBR_Transmission.pdf` | IEEE PES PSRC WG C32, *Protection Challenges and Practices for Interconnecting Inverter Based Resources to Utility Transmission Systems*, PES-TR81, 2020. | Industry evidence for our finding. 67Q calls a reverse phase-to-phase fault forward next to a 300 MW Type IV wind plant with coupled sequence control, and is correct once the plant injects I2 (decoupled control, slope K = 2). In a field case, unreliable IBR I2 made a relay miss a reverse fault and the echo logic was then disabled. Some relays need about 10 % I2/I1; the report recommends I2 proportional to V2 with a slope of 2–6. [pes-psrc.org/kb/report/109.pdf](https://www.pes-psrc.org/kb/report/109.pdf) |
| 28 ★ | `2014_Scott_Input_Design_Guaranteed_Fault_Diagnosis_Zonotopes.pdf` | Scott, Findeisen, Braatz & Raimondo, *Input design for guaranteed fault diagnosis using zonotopes*, Automatica 50(6):1580–1589, 2014. | Theorem 3: an input u separates hypotheses i and j if and only if N(i,j)·u lies outside a zonotope Z(i,j), with N(i,j) = C(j)B(j) − C(i)B(i). The input only shifts the output sets. If N = 0, no input separates a pair whose sets overlap; if N is small, the separating input must be large. This is the mechanism behind B1. [DOI 10.1016/j.automatica.2014.03.016](https://doi.org/10.1016/j.automatica.2014.03.016) |
| 29 | `2016_Raimondo_Closed_Loop_Input_Design_Guaranteed_Fault_Diagnosis.pdf` | Raimondo, Marseglia, Braatz & Scott, *Closed-loop input design for guaranteed fault diagnosis using set-valued observers*, Automatica 74:107–117, 2016. | The closed-loop version, on a moving horizon. It is the check on whether redesigning δ online helps when an open-loop design cannot separate. [DOI 10.1016/j.automatica.2016.07.033](https://doi.org/10.1016/j.automatica.2016.07.033) |
| 30 | `2021_SEL_Line_Protection_IBR_Solutions_WPRC.pdf` | Chowdhury & Fischer, *Transmission line protection for systems with inverter-based resources*, WPRC 2021. This is the conference version of Part II, IEEE TPWRD 36(4):2426–2433, 2021. | Relay-side fixes (settings and logic only) from the Sandia "real-code" study: raise the fault-detector checks, have fault-type selection rely on its undervoltage method, and use 32P logic for three-phase faults. It is the baseline an injection has to beat. |
| 31 | `2022_SEL_Line_Current_Differential_IBR.pdf` | Chowdhury, McDaniel & Fischer, *Line current differential protection in systems with inverter-based resources — challenges and solutions*, WPRC 2022. | The two-ended reference: what 87L loses with IBRs, and how to set it. [selinc.com/api/download/137350](https://selinc.com/api/download/137350/) |
| 32 | `2023_IEEE2800_Benefits_Transmission_Line_Protection_IPST.pdf` | Davi, Oleskovicz & Lopes, IPST 2023. The journal version is EPSR 220:109304, 2023. | EMT study of legacy balanced-current control against IEEE 2800-compliant I2 control, for seven functions including 32Q, 32G and two phase selectors, checked against commercial-relay routines. What standard I2 injection already buys is the bar a designed δ has to clear. |
| 33 | `2024_PNNL_IBR_Negative_Sequence_Current_Review.pdf` | Lyu, Xie & McDermott, *Impact of IBRs on grid protection: a review of negative-sequence current generation*, PNNL-36069, 2024. | Review of how IBRs generate I2. [DOI 10.2172/2377006](https://doi.org/10.2172/2377006) |
| 34 | `2021_Directionality_SVM_Synthetic_Harmonic_Injection.pdf` | Mohammadhassani, Mehrizi-Sani & Saleh, *Fault current directionality in islanded microgrids using SVM and synthetic harmonic injection*, IEEE ISIE 2021 (accepted manuscript). | The one item that combines injection with learning. It gives forward/reverse direction on the CIGRE 12.47 kV benchmark, for balanced faults. [DOI 10.1109/ISIE45552.2021.9576210](https://doi.org/10.1109/ISIE45552.2021.9576210) |
| 35 | `2025_Opoku_Sequence_Based_Directional_Detection_Active_Distribution.pdf` | Opoku, Dimitrovski & Ferrari, *Performance evaluation of a novel sequence-based directional detection strategy for protection of active distribution networks*, IEEE Access 13:7094–7109, 2025 (CC BY 4.0). | The closest distribution-feeder directional study: which parts of existing directional elements risk misoperating with IBRs, and a direction test built on the angle of the superimposed negative-sequence admittance, run in hardware-in-the-loop against an SEL-411L. [DOI 10.1109/ACCESS.2024.3525057](https://doi.org/10.1109/ACCESS.2024.3525057) |
| 36 | `2024_Yang_Dysko_NSCI_Active_Protection_Islanded_Microgrids.pdf` | Yang, Dyśko & Egea-Àlvarez, *A negative sequence current injection (NSCI)-based active protection scheme for islanded microgrids*, IJEPES 158:109965, 2024 (CC BY-NC-ND). | Inverters inject I2 at a fixed phase angle after a fault, and the faulted section is found from the I2 increment between before and during injection. It needs no communication and detects high-impedance faults. It is the closest negative-sequence injection scheme, but it finds the faulted section rather than the zone reach. [DOI 10.1016/j.ijepes.2024.109965](https://doi.org/10.1016/j.ijepes.2024.109965) |

**To fetch (open access, too large for the repo).** `fetch.sh` fetches both:
- ★ Yang, Liu, Zhang, Chen, Chavez & Popov, *A control method for converter-interfaced sources to improve operation of directional protection elements*, IEEE TPWRD 38(1):642–654, 2023, [DOI 10.1109/TPWRD.2022.3202988](https://doi.org/10.1109/TPWRD.2022.3202988). Green open access via TU Delft (5.9 MB). The IBR shapes its currents so the sequence impedances behind the relay look like a synchronous machine's, and existing directional elements work unchanged. It is the closest precedent and the comparison for a designed δ.
- Sandia SAND2020-0265, *Impact of inverter based resource negative sequence current injection on transmission system protection*, 2020, [DOI 10.2172/1595917](https://doi.org/10.2172/1595917) (100 MB).

**Held locally, not in git (paywalled).** The repository is public, so these library copies (obtained through NJIT on 30 Sep 2026) sit in `papers/library/`, which git ignores; each was checked against its title page and abstract.
- ★ Haddadi, Zhao, Kocar, Karaagac, Chan & Farantatos, *Impact of inverter-based resources on negative sequence quantities-based protection elements*, IEEE TPWRD 36(1):289–298, 2021, [DOI 10.1109/TPWRD.2020.2978075](https://doi.org/10.1109/TPWRD.2020.2978075). → `library/2021_Haddadi_IBR_Negative_Sequence_Protection_Elements.pdf` (the IEEE copy; a free accepted manuscript is at ira.lib.polyu.edu.hk, record 10397/93387). It gives the mechanism: IBR I2 is small (so 50Q/51Q fail) and its angle to V2 is not inductive (so 67Q fails).
- Azzouz & Hooshyar, *Dual current control of inverter-interfaced renewable energy sources for precise phase selection*, IEEE TSG 10(5):5092–5102, 2019, DOI 10.1109/TSG.2018.2875422 → `library/2019_Azzouz_Hooshyar_Dual_Current_Control_Phase_Selection.pdf`. The inverter sets its I2 angle so the relay's phase selector chooses correctly.
- Medhat & Azzouz, *Triple current control of four-wire inverter-interfaced DGs for correct fault type identification*, IEEE TSG 13(5):3607–3618, 2022, DOI 10.1109/TSG.2022.3170241 → `library/2022_Medhat_Azzouz_Triple_Current_Control_Fault_Type.pdf`. The distribution-level version.
- Banaiemoqadam, Hooshyar & Azzouz, *A control-based solution for distance protection of lines connected to converter-interfaced sources during asymmetrical faults*, IEEE TPWRD 35(3):1455–1466, 2020, DOI 10.1109/TPWRD.2019.2946757 → `library/2020_Banaiemoqadam_Control_Based_Distance_Protection_Asymmetrical_Faults.pdf`. Not the dual-current paper in section F.
- Chowdhury & Fischer, Part I: Problems, IEEE TPWRD 36(4):2416–2425, 2021, DOI 10.1109/TPWRD.2020.3019990 → `library/2021_Chowdhury_Fischer_Line_Protection_IBR_Part_I_Problems.pdf`.
- Xu, *Minimal detectable and isolable faults of active fault diagnosis*, IEEE TAC 68(2):1138–1145, 2023, DOI 10.1109/TAC.2022.3148305 → `library/2023_Xu_Minimal_Detectable_Isolable_Faults_Active_Fault_Diagnosis.pdf`. Lets the B1 result be phrased as a minimal isolable fault under an input budget.
- Nikoukhah, *Guaranteed active failure detection and isolation for linear dynamical systems*, Automatica 34(11):1345–1358, 1998, DOI 10.1016/S0005-1098(98)00079-X → `library/1998_Nikoukhah_Guaranteed_Active_Failure_Detection_Isolation.pdf`. The root of the guaranteed formulation: a test signal injected to make failures detectable under inequality-bounded perturbations, with a test for whether a given signal does so.
- Saleh, Allam & Mehrizi-Sani, *Protection of inverter-based islanded microgrids via synthetic harmonic current pattern injection*, IEEE TPWRD 36(4):2434–2445, 2021, DOI 10.1109/TPWRD.2020.2994558 → `library/2021_Saleh_Synthetic_Harmonic_Pattern_Injection_Microgrid_Protection.pdf`. **The closest precedent to a designed injection for direction.** A binary pattern of up to three synthetic harmonics per inverter is chosen by a nonlinear integer program so that every relay measures different patterns for forward and reverse faults, enforced as a cosine-similarity bound in a nominal nodal analysis. The pattern-based directional element feeds POTT and zone-interlocking. The setting is an islanded microgrid with harmonics, not a grid-connected feeder at 50 Hz, and there is no uncertainty set over R_f or loading.

**What this set says about our position.** The published fixes are all control-based: Yang/Popov, Azzouz/Hooshyar and Medhat/Azzouz reshape the inverter's I2 so it looks like a synchronous machine's for the whole fault, and most of them study a single plant on a transmission line. Saleh et al. (2021) do design an injection for direction, but they choose a binary harmonic pattern for a nominal model of an islanded microgrid. None designs a fundamental-frequency δ within the current budget with a separation guarantee over uncertainty sets. None studies a feeder with several inverters where 32Q errs in both directions. And none treats an inverter disconnecting at the remote bus that looks like a forward fault. Those three are not in this search; that is not proof that they are absent from the literature.
