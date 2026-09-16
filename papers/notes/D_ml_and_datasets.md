# Notes: machine learning and datasets

Read in full: papers 12–18 of the reading list (three ML papers, four dataset/benchmark papers).
Notes by Claude, 16 Sep 2026. Everything below is from the PDFs in `papers/`; where a fact is
absent from a paper I say so explicitly rather than filling it in.

## Synthesis

The honest position after reading all seven: **machine learning applied to fault detection,
classification and localisation in inverter-dominated grids is a crowded, mature field, and none
of it touches what we are actually doing.** Beikbabaei et al. already do decision-tree fault
detection *and* type classification on a 100 % inverter microgrid with ~96 % accuracy and claim
microcontroller feasibility; the Martinez-Velasco survey catalogues several hundred more such
papers back to the 1980s; Oelhaf et al. show a plain MLP hits macro-F1 0.989 from a 10 ms window.
So "we used ML to detect faults on an IBR grid" is not a contribution and must not be written as
one. What *is* untouched: across all seven papers — roughly 600 references and ~130 pages of text
— there are **zero** occurrences of "auxiliary signal", "active fault detection", "probing
signal", or "signal injection". The only negative-sequence mentions are passive (the survey, one
sentence) or grid-code fault-ride-through (EvEMTBench's inverter model). The closest published
precedent for our idea is Ouali et al., who inject a PRBS at the PCC and learn the inverter's
control mode from the measured admittance — active probing plus learning, but for system
identification over seconds, not sub-cycle fault detection. Our novelty axis is therefore safe,
and it is specifically: *how small can a designed negative-sequence injection be before each of
three detector families (conventional element, model-based Kalman filter, learned detector)
fails.* That is a sensitivity curve nobody has drawn.

On data: of the four "dataset" papers, only **two actually release data**. PROTECT-90 (9,022 EMT
fault episodes, Zenodo, CC BY 4.0) is beautifully documented but has **no inverters and no
non-fault events** — it is a Thevenin-source 90 kV double line. EvEMTBench (~70,000 events across
3 voltage levels, FAU share link) has **both GFL inverters and 13 classes of non-fault
disturbance** — motor starts, transformer inrush, capacitor switching, load steps, IBR trips —
which is precisely the security problem our self-generated synthetic data cannot pose. The
latency-aware Georgia Tech benchmark releases **nothing** (proprietary WinIGS simulator) and is
usable only as a methodology reference for WP4. Neither released dataset contains any auxiliary
injection, so WP3's core experiment still requires our own EMT simulation — the public data's job
is to supply the *nuisance* class and a realism check, not the treatment arm.

---

# Part 1 — The ML papers (what we cannot claim as novel)

## 12. Beikbabaei et al. 2024 — Decision trees on a 100 % inverter microgrid

**Full citation.** M. Beikbabaei, M. Lindemann, M. Heidari Kapourchali, and A. Mehrizi-Sani,
"Machine Learning–Based Protection and Fault Identification of 100% Inverter-Based Microgrids,"
arXiv:2405.07310 [eess.SY], 12 May 2024. (Virginia Tech + Univ. of Alaska Anchorage; NSF
ECCS-1953213, DOE SETO 38637 / UNIFI.)

**Task.** Two outputs from one model, per time sample, at a single relay (R1 at bus 1):
(a) binary fault detection, and (b) 8-class fault type — 0 = no fault, 1 = AG, 2 = BG, 3 = CG,
4 = ABG, 5 = ACG, 6 = BCG, 7 = ABCG. No fault location, no ground/phase discrimination beyond the
8 classes. Local measurements only; explicitly no communication.

**Inputs.** RMS values — *not* raw point-on-wave — of three-phase current I, three-phase voltage
V, real power P and reactive power Q at the relay bus, recorded at **1 ms intervals**. No phasors,
no sequence components, no incremental quantities, no wavelets. **Window length: a single sample**
(the tree classifies each 1 ms sample independently; there is no temporal context at all). The
authors present this as the selling point: "reduces the computational process and memory use …
facilitates practical implementation on a microcontroller."

**Model and size.** scikit-learn `DecisionTreeClassifier`, Gini impurity, **max depth 43, 4,044
leaves**. Training time < 9 s. SVM was rejected explicitly because it scales quadratically-to-
cubically with data size while trees scale linearly.

**Data.** PSCAD/EMTDC, driven by the PSCAD Python automation API. 4-bus, 100 % inverter microgrid:
IBR1 and IBR3 grid-forming (P–f and Q–V droop with PI), IBR2 and IBR4 grid-following (decoupled
dq current control with PLL). Base 1.5 MVA, 480 V LV / 12.47 kV MV, each inverter capped at
1.5 MVA with a fixed 1.2 kV DC source. Case matrix: 7 fault types × 5 fault resistances
{100, 10, 1, 0.1, 0.001 Ω} × 4 fault buses × 3 fault durations {0.05, 0.1, 0.2 s} = **420
simulations**. Fault inception fixed at t = 0.05 s in every case; 1 s simulation length. Total
**715,959 samples of 1 ms**. Split: `train_test_split`, 80/20, shuffled, `random_state=20`.

**Results with numbers.** Feature-set ablation (fault detection acc. / fault type acc.):
I alone 95.58 % / 95.50 %; I+V 95.92 % / 95.82 %; I+P+Q 96.26 % / 96.05 %; I+V+P+Q 96.33 % /
96.04 % (the set used). Case studies: AG at bus 1, 0.01 Ω — detected at t = 50 ms, clearance
detected at 155 ms (5 ms delay), one misclassified sample at 104 ms, self-corrected next step.
ACG at bus 2, 1 Ω — detection and clearance both exact. ABCG at bus 3 with a **40 Ω** fault the
tree was never trained on — detection at 50 ms but unstable for the first ~40 ms, fault type
correct only after 40 ms, clearance detected with 10 ms delay. Headline claim: detection in
< 5 ms for both low- and high-impedance faults.

**Stated limitations.** Only two, both in the conclusion: extend to a larger microgrid, and assess
accuracy under various network configurations.

**Unstated limitations we should note (and not repeat).** (1) **Data leakage.** The 80/20 split is
over *shuffled 1 ms samples*, not over simulations. Samples from the same 1 s PSCAD run appear in
both train and test, so 96 % is a within-episode memorisation figure, not generalisation. Both FAU
dataset papers explicitly warn against exactly this ("sliding windows derived from the same
simulation episode should not be distributed across training and test sets"). (2) No non-fault
disturbances at all — the load at bus 3 varies between runs (0.1–0.6 pu P) but is never *switched*
during a run, so the model has never seen a load step, inrush or motor start and its false-trip
rate is unmeasured. (3) Fault inception is at t = 0.05 s in all 420 cases, so inception angle is
not varied. (4) No CT/VT models, no measurement noise. (5) The 4 % residual error is never broken
down by class.

**What our team cannot claim as novel.** ML-based combined fault detection + type classification
on a 100 % inverter microgrid from local V/I/P/Q. Decision trees as a low-burden, relay-feasible
classifier. Sub-5-ms ML detection. Robustness to an unseen (higher) fault resistance. If we want
to beat this paper we should beat it on the axes it is weak on: episode-level splits, varied
inception angle, and a measured false-alarm rate against non-fault events.

---

## 13. Ouali et al. 2024 — Random forest tells GFM from GFL via injected-PRBS admittance

**Full citation.** R. Ouali, J.-Y. Dieulot, P. Yim, X. Guillaud, F. Colas, Y. Wu, and H. Wu,
"Machine learning classification of power converter control mode," 19 January 2024,
arXiv:2401.10959. (ANR DELTWINCO project, LabEx BASC, ANR-21-CE05-0038.)

**Task.** Binary classification of a black-box grid-connected converter's control mode —
**grid-forming (GFM) vs grid-following (GFL)** — from external measurements at the PCC. Motivation
is TSO compliance checking: converters are owned by private suppliers, structures and parameters
are IP-protected, so the TSO must infer mode without access. **This is not fault detection.**

**Inputs.** Frequency-domain **dq admittance model** measured at the PCC by **actively injecting a
perturbation** (hybrid shunt/series excitation), then FFT of the V and I response. Feature vector:
magnitude and phase of Y_dd and Y_qq → a **300-column** record per sample (four blocks of
frequency bins plus the mode label). Cross-coupling terms Y_dq and Y_qd are computed but **not
used**. Excitation: PRBS on d-axis (order 8, F_max 1000 Hz) and on q-axis (order 7, F_max
1020 Hz). Stated measurement range 1 Hz to 800 kHz; the control-influenced band is identified as
**1 Hz–1 kHz** (below that both modes converge to the operating-point value, above that both
converge to the passive filter admittance). No time-domain waveform is used; no sampling rate or
window length for a streaming input is given, because there is no streaming input.

**Model and size.** Seven scikit-learn models, hyperparameters as reported: Logistic Regression
(`max_iter=100`), Random Forest (`n_estimators=100`), Decision Tree (`max_depth=6`), Naive Bayes
(defaults), XGBoost (listed oddly as `kernel=linear`), SVM (`kernel=linear`), kNN
(`n_neighbors=20`). No parameter counts, memory footprints or inference times are reported
anywhere in the paper.

**Data.** MATLAB/Simulink. Converter: 1.044 GVA / 400 kV VSC, P_nom 1 GW, Q_max 300 MVAr, filter
L_c 0.15 pu / R_c 0.005 pu. Grid fixed at **SCR 15** (grid impedance deliberately held constant;
filter parameters likewise). Operating point swept: P −1…1 pu, Q −0.4…0.4 pu, voltage ±10 %.
Control-parameter sweeps — GFL: ω_p, ω_q ∈ [6, 38] rad/s, ω_v ∈ [3, 15] rad/s, PLL ω_n ∈
[50, 1500] rad/s with ξ_n = 1, current loop ω_cc ∈ [1200, 3000] rad/s, low-level delay d ∈
[50, 200] µs. GFM: H ∈ [0.5, 5] s, ξ ∈ [0.7, 4], TVR ω_f = 60 rad/s, R = 0.09, QSEM ω_LPF =
83 rad/s, ω_cc ∈ [1200, 3000] rad/s, same delay range. **5,000 samples per control mode** split
across four structures (vcGFM + ccGFM for GFM; pvGFL + pqGFL for GFL). Split 80/20; reported
accuracy is the mean cross-validation score over 100 runs. A fifth structure, **viGFL
(2,500 samples), is held out entirely** for the generalisation test — it differs from pqGFL only
in the active-power loop, perturbing the dd-axis admittance over 1–50 Hz.

**Results with numbers.**
- In-distribution accuracy: **RF 98 %**, LR 96 %, SVM 96 %, kNN 96 %, XGB 95 %, DT 92 %, NBC 92 %.
- Generalisation to the unseen viGFL structure: **RF 92 %**, LR 85 %, SVM 84 %, kNN 84 %, NBC 82 %,
  XGB 79 %, **DT 40 %** (worse than chance-adjacent — it had keyed on one column).
- Third-party test, a dataset from Aalborg University, 100 samples per mode:
  **RF 95 %**, SVM 94 %, kNN 94 %, NBC 93 %, LR 92 %, XGB 87 %, DT 83 %.
- Explanation given: feature-importance plots (e.g. `Pdd118Hz`) show DT concentrates importance on
  a single column while RF spreads it, which is why RF generalises.

**Stated limitations.** ML fails on control structures absent from training (DT catastrophically);
grid impedance held constant at one SCR; coupling admittances Y_dq/Y_qd excluded; the method
identifies *mode* only, not control structure or parameters; advanced neural networks are named as
required future work.

**What this means for us.** Two things, and this is the most useful paper of the three for our
framing. (1) **It is the closest prior art to "perturb the inverter deliberately and learn from
the response."** We must cite it and distinguish ourselves clearly: their probe is a broadband
PRBS for offline system identification over many cycles, ours is a *designed, minimal-amplitude
negative-sequence signal for sub-cycle fault discrimination*; their target is the converter's own
control mode, ours is a line fault. The novelty survives, but a reviewer who knows this paper will
ask, so we should pre-empt it in the related-work section. (2) **Steal their evaluation protocol.**
Train on structures A–D, test on held-out structure E, and report the drop. That is exactly the
right way to test whether our learned detector survives an inverter control it has never seen —
far more convincing than a random split, and it directly addresses the most obvious attack on a
learned relay. Their result also gives a prior: expect a 6–50-point accuracy drop on unseen
control structure, and expect ensembles to degrade more gracefully than single trees.
(3) A possible side chapter, as the reading-list README already notes: infer inverter type online
and feed it into Taylor's uncertainty sets.

---

## 14. Martinez-Velasco et al. 2025 — Survey of AI for fault detection, classification, location

**Full citation.** J. A. Martinez-Velasco, A. Serrano-Fontova, R. Bosch-Tous, and P.
Casals-Torrens, "Survey on Methods for Detection, Classification and Location of Faults in Power
Systems Using Artificial Intelligence," preprint dated 14 July 2025, arXiv:2507.10011. ~44 pages,
~550 references. (UPC Barcelona; Reactive Technologies Ltd.)

**Task.** Not a method paper — a bibliographic survey. Scope: AI-based detection, classification
and location of faults **on lines and cables only**, at transmission and distribution levels, AC
and DC, with or without DERs. Explicitly out of scope: transformers, wind turbines, PV plants,
railway and marine systems. Frames fault diagnosis as a five-step pipeline: measure V/I → extract
features → detect → classify → locate.

**Inputs catalogued.** The survey's taxonomy of feature extraction (its §4.1) is the most useful
part for us:
1. *Transform methods* — FT, DFT, FFT, WT, DWT, CWT, S-transform.
2. *Modal transformations* — Clarke, Clarke–Concordia, Karrenbauer (decouple three-phase into
   components that characterise fault type).
3. *Dimensionality reduction* — PCA.
4. *Other, lower-burden* — RMS of phase and zero-sequence currents; normalised ratios of maximum
   absolute currents between two phases; ratio of phase-angle differences; **ratio of zero-sequence
   to positive-sequence current amplitude**; mathematical morphology.

On detection specifically: "Detection methods independent of the classification methods use
**negative sequence components** or parameters extracted by using a wavelet transform." **This is
the only occurrence of "negative sequence" in the entire 44-page survey**, and it refers to passive
measurement. There is no mention anywhere of injecting anything.

**Models catalogued.** ANN, CNN (1D and 2D), LSTM, CNN-LSTM, GNN/GAT/STGCN, SVM, DT/RF, fuzzy
logic, ANFIS, expert systems, metaheuristics (PSO, ACO, GA, tabu, simulated annealing), and newer
named directions: transfer learning, graph learning, attention, deep RL, physics-guided neural
networks, YOLO (for UAV line inspection), federated learning, quantum computing. No model sizes.

**Data.** N/A — the survey generates none. Its Tables 3–6 list ~70 papers published 2021–2025 by
reference / author / year / task / technique. **No accuracy, latency or dataset-size numbers are
tabulated anywhere in the survey.** If we need numbers from this literature we have to go to the
primary sources.

**Results with numbers.** None. This is worth stating plainly: the survey is a map, not a
measurement. Its value to us is the negative result (nobody is injecting) and the meta-observations
below.

**Stated limitations — of the field, which is what we care about.** From §4.2, §4.3 and §V:
- "A high percentage of the selected works is based on either a two-terminal transmission line
  model or a rather small benchmark system, usually an IEEE test system."
- "Only a **few works used public datasets** (e.g. datasets available in Kaggle)." "In general,
  data for training ML-based approaches come from simulations carried out by the authors."
- "Only a small percentage of papers deal with a complete fault diagnosis procedure (detection,
  classification *and* location). Fault location seems to be the task to which a lower number of
  papers has been dedicated."
- "Many authors did **not include the representation of instrument transformers** (i.e., current
  and voltage transformers) in the system models. Therefore, it is advisable to be **careful about
  some conclusions**." — this is the survey authors' own warning, and it applies to every dataset
  in Part 2 below, none of which model CTs/VTs.
- Practical implementation requires "powerful and flexible microprocessors that could be easily
  reprogrammed"; real-time simulation platforms "will be of much help."
- Supervised ML (NN, SVM, DT) is by far the most popular family; none of the surveyed transmission
  papers addresses AI-based diagnosis of transmission-level insulated cables.

**What our team cannot claim as novel.** Applying ML/DL to fault detection, classification or
location — this is 40+ years old with hundreds of papers. Wavelet, Fourier, S-transform, Clarke or
PCA features. **Using negative-sequence components for fault detection** (passive use is standard).
Sequence-ratio features. CNNs/LSTMs/GNNs on relay waveforms. "Physics-informed" or "physics-guided"
as a framing. What *is* free: no paper in this survey injects a designed signal, and the survey
itself certifies that public datasets are barely used — so simply doing WP3 on a public EMT dataset
with an episode-level split is already above the field's median rigour.

---

# Part 2 — The dataset and benchmark papers

## Comparison table (read this first)

| | **PROTECT-90** | **EvEMTBench** | **Controlled Comparison** | **Latency-Aware DL Benchmark** |
|---|---|---|---|---|
| Paper | Oelhaf et al., arXiv:2606.24298 | Kordowich et al., arXiv:2608.19777 | Oelhaf et al., arXiv:2510.00831v2 | Abukhousa et al., arXiv:2605.17256 |
| Is it a dataset? | **Yes** | **Yes** | No — benchmark *on* PROTECT-90 | No — **nothing released** |
| Download | Zenodo **10.5281/zenodo.18418330**, CC BY 4.0 | FAUDataCloud share link (see below). **No DOI, no licence stated** | n/a (uses PROTECT-90) | **None.** WinIGS is proprietary commercial |
| Simulator | DIgSILENT PowerFactory EMT, 10 µs step | DIgSILENT PowerFactory EMT, 10 µs step | — | WinIGS (Advanced Grounding Concepts) |
| Cases | 9,022 episodes | ~10,000 events × 11 sets (3 multigrid + 4 adaptgrid + 4 benchmark) ≈ 70k+ | 207k–280k windows cut from the 9,022 | 105,768 samples over **22 s**, one testbed |
| Voltage | 90 kV only | **20 / 110 / 345 kV** | 90 kV | LV/MV microgrid (not stated precisely) |
| Topology | Fixed 3-bus double line, 4 line sections | CIGRE MV 14-bus, 110 kV Protection Reference Grid, IEEE 39-bus, Double Line, **plus 105 random topologies per voltage level** | Same as PROTECT-90 | One fixed microgrid, Protection Zone 2 |
| Frequency | 50 Hz | **50 Hz and 60 Hz** (IEEE 39-bus is the 60 Hz one) | 50 Hz | Not stated (60 Hz implied, US) |
| Sampling | **6,400 Hz** = 128 samples/cycle @50 Hz | **9,600 Hz** (192/cycle @50 Hz, 160/cycle @60 Hz) | 6,400 Hz | **4,800 Hz** (208 µs) |
| Episode length | 1.0 s (6,400 samples), 0.1 s warm-up discarded | 0.5 s exported (4,801 samples) of a 1.5 s sim | ±80 ms around inception, 10–50 ms windows | 22 s continuous stream |
| Measurement points | **8 relay locations** × 6 ch = 48 channels | Every cubicle of the main voltage level (n varies by grid) × 6 ch | all 8, centralised | **2 merging units** × 7 = 14 features |
| Format / size | per-episode `.pkl` pandas float32; **12.5 GB zipped / ~31 GB unzipped**; metadata CSV 7.3 MB | 11 `.tar.gz`; `result{N}.csv` + `settings_clean.csv` + NetworkX `.pickle` + `.pfd`. **Total size not stated** | — | COMTRADE (not released) |
| **Inverter sources?** | **NO.** External-grid Thevenin equivalents only. S″_k biased low (90–1000 MVA) "to reflect" future IBR grids, but no inverter model exists | **YES, GFL only** — "we focus exclusively on GFL IBRs." MV: IBR is the only source type, ~20 % of buses. 110 kV: 50 % source probability, {Sym, IBR}. **345 kV: synchronous only** | NO (inherits PROTECT-90) | **YES** — 50 kVA PV inverter + 30 kVA BESS. Control type (GFM/GFL) **not stated**; share not quantified |
| **Non-fault events?** | **NO.** "9,022 fault scenarios **without a non-fault class**" | **YES — 13 classes**: load on/off, capacitor on/off, OHL on/off, cable on/off, LV & HV trafo inrush, motor start, sync-machine trip, IBR trip | NO (pre-fault windows only) | **NO** disturbances. Only "Normal" + cyber-attacks (CT/PT ratio, GPS spoof) |
| **Auxiliary / injected neg-seq signal?** | **NO** | **NO** designed probe. (Inverter *does* inject negative-sequence inductive reactive current as grid-code FRT during unbalanced faults — a confound, not a probe) | **NO** | **NO** |
| CT/VT models, noise | **None** — "ideal primary voltage and current signals" | Not mentioned | None | CT/PT digitised outputs claimed, no model described |
| Train/test split | **None provided.** Episode-wise recommended | None. Simulation-level (adaptgrid) / topology-level (multigrid) recommended | 5-fold CV **grouped by episode** | 70/10/20 "stratified block-based" |
| **Verdict for WP3** | **Secondary.** Front-end + conventional-element validation only. Cannot show the problem we solve (no inverter ⇒ conventional elements won't fail) and cannot test security (no non-fault events) | **PRIMARY.** The only source of realistic non-fault nuisance events *with* current-limited inverters. Use 20 kV + 110 kV subsets | **Protocol source.** Copy the window sweep + episode-grouped CV wholesale | **Unusable as data.** WP4 methodology reference only |

FAUDataCloud link (EvEMTBench), transcribed exactly from the paper:
`https://data.fau.de/share/0e8d60feb7e65616c60aab78b93db77053275da53fd894bf5b75fc5e9ee7dfbf/`

---

## 15. PROTECT-90

**Full citation.** J. Oelhaf, G. Kordowich, C. Bergler, A. Maier, J. Jäger, and S. Bayer,
"PROTECT-90: A Fault Dataset for Power System Protection," arXiv:2606.24298 [eess.SP], 23 June
2026; accepted, IEEE ISGT Europe 2026. Oelhaf and Kordowich contributed equally. FAU
Erlangen-Nürnberg + OTH Amberg-Weiden. DFG 535389056.

**Where to download.** Zenodo, **DOI 10.5281/zenodo.18418330** (dataset citation: G. Kordowich,
J. Oelhaf, C. Bergler, A. Maier, S. Bayer, J. Jäger, March 2026). Licence **CC BY 4.0**.
Archive **12.5 GB compressed, ~31 GB uncompressed**, plus a 7.3 MB metadata CSV.

**Contents.** 9,022 EMT episodes on a fixed standardised **90 kV double-line** topology: Bus 1 —
(Line 1-2A ∥ Line 1-2B) — Bus 2 — (Line 2-3A ∥ Line 2-3B) — Bus 3, with external-grid equivalents
at Bus 1 and Bus 3 and aggregated loads at Bus 2 and Bus 3. Chosen deliberately because parallel
paths and intermediate infeed "introduce non-trivial current distribution and impedance measurement
errors relevant for distance protection studies." DIgSILENT PowerFactory, fixed-step EMT solver at
**10 µs**, 0.1 s warm-up discarded, then **1 s recorded at 6,400 Hz = 6,400 samples = 128 samples
per 50 Hz cycle** ("typical digital fault recording resolution"). Three-phase V and I at **both
terminals of each of the four line sections = 8 relay locations × 6 channels = 48 synchronised
channels**; per episode the tensor is X ∈ R^(8 × 6 × 6400), stored as a 49-column pandas DataFrame
(time + 48) in a `.pkl` per episode, float32, Python 3.11. Channel naming convention e.g.
`Bus_3_Line_02_03A_vol_L3_V`, currents `..._cur_Lx_A`. **No CT/VT models — "all exported quantities
represent ideal primary voltage and current signals."** No added noise.

**Labels.** CSV indexed by `sample_id`. Fields: `sc_type` (SLG / LL / LLG / LLL), `phase_select`
(affected phases), `fault_target` (faulted line section), `sc_location` (normalised % of line
length, approximately uniform 0–100 %), fault resistance **R_f ∈ [0.1, 10] Ω**, inception time
**t_f ∈ [0.2, 0.5] s**, plus every domain-randomised grid parameter with units — line length
ℓ ∈ [10, 60] km, R′ ∈ [0.01, 0.20] Ω/km, X′ ∈ [0.35, 0.45] Ω/km, C′ ∈ [8.5, 10] nF/km, load
P ∈ [20, 50] MW, Q ∈ [−20, 20] Mvar, external-grid S″_k ∈ [90, 1000] MVA, V ∈ [0.95, 1.05] pu,
phase angle φ ∈ [−180, 180]° — and boolean topology flags (Line 1-2B out, Line 2-3B out, Bus 3
external grid deactivated), each balanced ~50/50. Physical-plausibility constraints: load-flow
convergence, EMT stability, and R/X of all lines confined to [0.05, 0.5]. **No derived or
preprocessed features are included.** Coverage: SLG/LL/LLG/LLL approximately uniform; primary
corridors 1-2A and 2-3A ~35 % of episodes each, secondary 1-2B and 2-3B ~15 % each.
**Fault inception angle is not a labelled field** — inception *time* is randomised over 0.2–0.5 s
and the external-grid phase angle is randomised over ±180°, which together randomise the angle
implicitly, but there is no column giving it.

**Inverter-based sources?** **No.** The design rationale says the 90 kV level "enables realistic
transient behavior **without restricting the dataset to** extra-high-voltage **or
inverter-dominated system configurations**." Sources are external-grid Thevenin equivalents. The
only IBR-flavoured choice is that S″_k is "intentionally biased toward comparatively low values to
reflect future grid conditions with increasing penetration of inverter-based resources and
consequently reduced fault levels." **This is not equivalent to an inverter.** A weak Thevenin
source still delivers a fault current proportional to 1/Z with correct phase and unbounded
negative-sequence contribution; a current-limited inverter clamps at ~1.1–1.2 pu and controls its
sequence currents. The failure mode our project exists to fix does not occur in this dataset.

**Non-fault events?** **No.** Stated flatly: "The dataset comprises 9,022 fault scenarios **without
a non-fault class**." The authors' own guidance: "Because the dataset contains only fault
scenarios, detection tasks require explicit definition of windowing and labeling assumptions" — in
practice you manufacture a no-fault class from the 0.2–0.5 s of pre-fault steady state in each
episode. That gives a *quiescent* negative class, never a *disturbed* one.

**Auxiliary / negative-sequence injection?** **No.** Zero mentions of injection, auxiliary signals
or negative sequence anywhere in the paper.

**Verdict for WP3.** Usable, but for supporting roles only, and we should be explicit about which:
- **Yes**: validating our signal-processing front end at exactly 128 samples/cycle — phasor
  extraction, incremental quantities, sequence decomposition — against 9,022 correctly labelled
  faults with known R_f, location and line parameters.
- **Yes**: characterising our *conventional* relay elements (50/51, 21 distance, 67Q) on a topology
  with real intermediate infeed and parallel-line coupling, where we know ground truth. Also gives
  a defensible "distance protection error vs. fault location" curve for the report.
- **Yes**: an inverter-free control arm — "here is how the learned detector does when the sources
  are conventional," which is the right baseline against which to show degradation under IBR.
- **No**: the central WP3 experiment. No inverter means conventional elements will *work*, so there
  is no gap for the auxiliary signal to close and no injection-amplitude axis to sweep.
- **No**: any security / dependability claim, since there are zero non-fault events.
- Note the 50 Hz / 6,400 Hz combination: 6400/60 = 106.67, non-integer, so this data does not map
  cleanly onto our 16.7 ms (60 Hz) one-cycle budget without resampling.

---

## 16. EvEMTBench

**Full citation.** G. Kordowich, J. Loebel, J. Oelhaf, A. Maier, S. Bayer, C. Bergler, and J.
Jaeger, "A simulation based dataset of faults and events for machine learning in power systems,"
arXiv:2608.19777, 20 August 2026 (DOI 10.48550/arXiv.2608.19777; preprint licensed CC BY-NC-ND
4.0). FAU Erlangen-Nürnberg + OTH Amberg-Weiden. DFG 535389056.

**Where to download.** FAUDataCloud:
`https://data.fau.de/share/0e8d60feb7e65616c60aab78b93db77053275da53fd894bf5b75fc5e9ee7dfbf/`
**There is no DOI for the data and no licence is stated in the paper for the dataset itself**
(only the preprint's CC BY-NC-ND). A share link can rot — download early and keep a local copy,
and if we publish, email Kordowich (georg.kordowich@fau.de) to ask for a citable DOI.

**Contents.** 11 `.tar.gz` files in three families:
- **multigrid** (3 files: Template20kV, Template110kV, Template345kV) — 10,000 events per voltage
  level across **105 randomly generated topologies per voltage level**. Topology, operating state
  and event parameters all randomised. For cross-topology generalisation.
- **adaptgrid** (4 files: CigreMVGrid 20 kV 14-bus, DoubleLine 110 kV, TestGrid110kV, IEEE39Bus
  345 kV) — 10,000 events each, fixed topology, randomised events + operating states (loads scaled
  50–150 %). For fine-tuning to a specific grid.
- **benchmark** (same 4 grids) — discrete event parameters (e.g. fault location ∈ {1, 20, 50, 80,
  99} %), constant operating states. For systematic evaluation.
"The total number of usable data records is slightly less than 10000 simulations per dataset"
after discarding non-converging runs. So order ~70,000+ events overall; the paper never gives a
grand total or a byte count.

Simulation: PowerFactory EMT, **10 µs** step, 1.5 s simulated, **first 1.0 s discarded**, last
**0.5 s exported at 9,600 Hz → 4,801 samples**. Measurement tensor
M ∈ R^(n × 6 × 4801), n = number of cubicles on the main voltage level (varies per grid — not a
fixed 8 as in PROTECT-90), channels = [v_a, v_b, v_c, i_a, i_b, i_c] (phase-to-ground voltages,
phase currents, "all current measurements are oriented towards the branch element"). 9,600 Hz was
chosen because it suits **both 50 Hz and 60 Hz** (192 and 160 samples/cycle respectively).
Modelling targets CIGRE **Group I transients, 0.1 Hz–3 kHz**.

Component modelling is unusually deep and matters for us: overhead lines and cables use the
frequency-dependent **universal line model (Gustavsen)** built from tower/cable *geometry* (5
HV tower types, 2 MV types, fitted 0.01 Hz–1 MHz); transformers have a full piecewise saturation
characteristic so **inrush is physically real**; synchronous machines use IEEE model 2.2 with AC1A
exciters; loads are ZIP; and **grounding is modelled per voltage level** — isolated, solid,
resistance, or **arc-suppression-coil (Petersen coil) resonant grounding with detuning I_ASC**,
which strongly shapes the zero- and negative-sequence content of ground faults. Arc faults use
Kizilcay's arc model. **No CT/VT models and no measurement noise are mentioned.**

**Labels.** `labels/settings_clean.csv`, one row per simulation. Fields:
`general/result_file_path`, `general/sim_idx`, `general/vn` (20 / 110 / 345 kV),
`general/fn` (50 / 60 Hz), `general/grid_graph`; `events/event_type` (e.g. `flt_1phg_shc`),
`events/event_start`, `events/event_target` (component, e.g. `MainLn1-2`),
`events/event_flt_target_line_location` (1.0–99.0 %), `events/event_flt_shc_resistance` (Ω),
`events/event_flt_hif_resistance` (Ω), `events/event_phase_select_2ph` (e.g. `ab`),
`events/event_phase_select_1ph` (e.g. `a`), `events/event_iflt_duration` (s); plus
`element/parameter` fields for **every randomly sampled component parameter** (e.g. `arc/arc_tau`).
Warning from the authors: all fields are populated for every simulation even when they do not apply
(arc parameters exist on non-arc faults and must be ignored). Event sampling ranges: event start
**1.1–1.3 s** (i.e. 0.1–0.3 s into the exported window, leaving ≥100 ms of pre-event data),
fault location U[1, 99] %, short-circuit resistance **0.001–50 Ω**, HIF resistance **50 Ω–150 kΩ**
in four equally-likely bands ([50, 500], [500, 5k], [5k, 50k], [50k, 150k] Ω), incipient-fault
duration 0.002–0.08 s. Topology is shipped as a machine-readable **NetworkX graph pickle**
(`graph_grid{N}.pickle`, NetworkX 3.2.1 / Python 3.9) with bus, line and machine parameters
accessible, plus an optional proprietary `.pfd`. **Operating point is labelled** via the sampled
load/generation parameters. **Fault inception angle is not an explicit field** (event start time is,
and the external-grid initial phase angle is randomised over ±180° precisely so that waveforms are
not phase-aligned across simulations).

**Inverter-based sources?** **Yes, but grid-following only** — stated explicitly: "While grid
forming inverters are expected to play a greater role in the future, currently existing IBRs are
mostly controlled using grid following (GFL) control algorithms. Therefore, we focus **exclusively
on GFL IBRs** in this study." **This is the single biggest limitation for us**, since Taylor's
auxiliary-signal work is most natural on a grid-forming inverter.

Share and ratings: **20 kV** — IBR is the *only* source type, connected to ~20 % of buses,
1–15 MVA each; **110 kV** — source connection probability 50 %, type ∈ {Sym, IBR}, 20–50 MVA each;
**345 kV** — synchronous machines only, **no IBRs at all**. Active-power setpoint 0.1–0.9 pu.

Control detail (their Fig. 6), which is close enough to our assumptions to be usable: ideal AC
voltage source behind an impedance (average model, no switching); **DDSRF PLL** separating positive
and negative sequence dq; positive-sequence active power control with frequency support; reactive
power control with voltage support; positive-sequence FRT injecting capacitive reactive current;
**negative-sequence FRT injecting inductive reactive current during unbalanced faults**; and an
unsymmetrical current limiter that clamps when any phase current exceeds **1.2 pu**, prioritising
(i) positive- and negative-sequence reactive currents equally and highest, (ii) positive-sequence
active current lowest, while preserving the positive/negative reactive ratio. **The 1.2 pu limit is
exactly the premise of our project**, and the current-limit logic is the mechanism that blinds
conventional relays.

**Non-fault events?** **Yes — this is the dataset's defining feature and the reason to pick it.**
22 event types (their Table 1), of which **13 are non-fault operating events**:
Load On, Load Off, Capacitor On, Capacitor Off, OHL On, OHL Off, Cable On (MV only), Cable Off (MV
only), Inrush LV Trafo, Inrush HV Trafo (MV/HV only), **Motor Start** (MV only, induction motor),
Synchronous Machine Trip (HV/EHV), **IBR Trip** (MV/HV). The 9 fault types: 1PHG SHC, 1PHG SHC with
Arc, 2PH SHC, 2PHG SHC, 3PH SHC, 1PHG HIF (MV), 1PHG HIF with Arc (MV), Incipient Fault,
Incipient Fault with Arc. Their technical validation figure confirms the expected physics: HIFs are
"barely visible in the phase currents and voltages, but clearly visible in the zero sequence
system"; load and motor switches produce rising phase currents with distinct transients; transformer
and capacitor switching are clearly visible in the phase currents.

**Auxiliary / negative-sequence injection?** **No designed probe.** The negative-sequence FRT
current described above is *reactive* — grid-code-mandated, triggered by the fault itself, and
proportional to the negative-sequence voltage. It is not an always-on designed auxiliary signal
and it does not make faults distinguishable in Taylor's sense. Two implications: (a) our novelty
holds; (b) this is a **confound we must control** — any negative-sequence-based detector we test on
EvEMTBench will see inverter FRT negative-sequence current and could look better than it should.
We must report whether a detection is driven by fault physics or by the inverter's own FRT response.

**Verdict for WP3.** **This is the dataset to use, and it should be the primary one.** Specifically:
- **Security / false-alarm testing (the highest-value use).** Run all three detectors — conventional
  element, Kalman filter, learned — over the 13 non-fault event classes and report the false-trip
  rate for each. Our team currently cannot do this at all with self-generated data, and "does your
  detector trip on a motor start or transformer inrush?" is the first question any protection
  engineer or review panel will ask. Use the **20 kV and 110 kV** subsets, which is where the
  inverters live.
- **Dependability under realistic IBR current limiting.** The 1.2 pu limiter and the GFL controls
  give a credible "relay is blinded" scenario without us having to build it ourselves.
- **Cross-topology generalisation.** Train on multigrid-110kV (105 topologies), test on the
  adaptgrid/benchmark 110 kV Protection Reference Grid — the strongest available evidence that a
  learned detector is not just memorising one network.
- **Incipient / high-impedance faults** as a stress class for the minimum-detectable-signal study.
- **Limits to state honestly**: GFL only (no grid-forming); no auxiliary injection; IBR penetration
  is 20–50 % of buses, not 100 %; no CT/VT or noise models; everything with inverters is **50 Hz**
  (the only 60 Hz grid, IEEE 39-bus, has no IBRs), so a "one-cycle" budget on this data is 20 ms,
  not our 16.7 ms — we should either state the budget as "one cycle" generically or resample.
- **Recommended split** (theirs): simulation-level for adaptgrid, topology-level for multigrid.

---

## 17. Controlled Comparison of ML Models for Fault Classification and Localization

**Full citation.** J. Oelhaf, G. Kordowich, C. Kim, P. A. Pérez-Toro, C. Bergler, A. Maier, J.
Jäger, and S. Bayer, "Controlled Comparison of Machine Learning Models for Fault Classification and
Localization in Power System Protection," arXiv:2510.00831v2 [cs.AI], 18 June 2026; accepted IEEE
ISGT Europe 2026. DFG 535389056.

**Where to download.** **This paper releases no dataset and no code.** It is an evaluation *on*
PROTECT-90 (Zenodo 10.5281/zenodo.18418330). Treat it as a protocol and results reference.

**Contents / method.** Uses all 9,022 PROTECT-90 episodes at 6,400 Hz. Preprocessing: crop each
episode to **±80 ms around fault inception**; extract overlapping sliding windows with a **5 ms
stride** ("matching the typical interrupt cycle of numerical protection relay processors");
evaluate window lengths **10, 20, 30, 40, 50 ms** = 64/128/192/256/320 samples (0.5–2.5 cycles at
50 Hz, justified against IEC 60255-1 and IEEE C37.114). Window counts and fault-window share:
10 ms → 279,682 windows, 9,022 fault (3.2 %); 20 ms → 261,638 / 27,066; 30 ms → 243,594 / 45,110;
40 ms → 225,550 / 63,154; 50 ms → 207,506 / 81,198 (39.1 %). Input: three-phase V and I from **all
eight relays concatenated** — i.e. **centralised**, 48 channels, explicitly "a practical performance
upper bound" assuming IEC 61850 substation communication, **not a local relay**. All models
scikit-learn with **default hyperparameters** and standardised inputs; **5-fold cross-validation
grouped by simulation episode** to prevent leakage from overlapping windows.

**Labels / tasks.** FC = 11-class (c₀ "No Fault" + AG/BG/CG, AB/BC/CA, ABG/BCG/CAG, ABC), macro-F1.
FL = regression on fault position as % of line length, MAE, using only windows that fully contain
the inception instant.

**Results with numbers.**
*Fault classification, macro-F1 (mean ± std over 5 runs):*

| Window | MLP | GB | KNN | RF | ET | Ridge | LG |
|---|---|---|---|---|---|---|---|
| 50 ms | **0.990** ±0.003 | 0.982 | 0.863 | 0.838 | 0.431 | 0.089 | 0.071 |
| 40 ms | 0.978 ±0.013 | **0.982** | 0.851 | 0.828 | 0.300 | 0.091 | 0.079 |
| 30 ms | **0.989** ±0.003 | 0.977 | 0.831 | 0.802 | 0.213 | 0.093 | 0.086 |
| 20 ms | **0.993** ±0.002 | 0.738 | 0.799 | 0.771 | 0.162 | 0.095 | 0.090 |
| 10 ms | **0.989** ±0.003 | 0.418 | 0.738 | 0.292 | 0.098 | 0.097 | 0.104 |

*Fault localisation, MAE in % of normalised line length:*

| Window | Stacking | MLP | Voting | GB | KNN | DT | ET |
|---|---|---|---|---|---|---|---|
| 50 ms | **9.676** | 9.915 | 10.623 | 14.658 | 19.121 | 19.714 | 21.761 |
| 30 ms | **9.906** | 10.179 | 10.763 | 14.642 | 19.646 | 20.211 | 21.759 |
| 10 ms | **10.304** | 10.662 | 10.943 | 14.646 | 20.376 | 22.102 | 21.730 |

Key findings: (1) **fault-type information is fully present in the first 10 ms** — the MLP is flat
at ~0.99 across all horizons, so longer windows buy nothing for a high-capacity model; (2) linear
models fail completely at every horizon (F1 0.07–0.10), so the task genuinely needs nonlinear
boundaries; (3) localisation shows a **hard ~10 % error floor** insensitive to window length and
shared by the three best models, attributed to topology-induced identifiability limits (parallel
lines + intermediate infeed) rather than model capacity; per-line MAE for MLP@50 ms: Line 1-2A
9.08, 1-2B 9.18, 2-3A 10.58, 2-3B 11.05.

*Inference time* (13th-gen Intel i7-13700HX, **single CPU core**, batched single-sample forward
passes over 5,000 iterations, inference only): **DT 0.04 ms, MLP 0.56 ms, GB 1.23 ms, ET 1.64 ms,
Voting 2.88 ms, Stacking 2.95 ms, KNN 1,287.53 ms** (unsuitable for real time). Preprocessing
(window extraction + standardisation) adds **< 0.1 ms** per sample; full pipeline ≤ 3.1 ms for all
but KNN.

**Stated limitations.** Models exceeding 24 h training under the CV protocol were excluded —
Bagging, LinearSVC, SGD and SVC for classification; SVR, Bagging and RF for regression — so the
model rosters differ between tasks. Default hyperparameters throughout (deliberate, to compare
tasks not tune models). Centralised access to all relays assumed. The double-line topology "does
not capture the effects of large-scale meshed networks."

**Unstated limitations relevant to us.** Inherits all of PROTECT-90's: no inverters, no non-fault
disturbances (the "No Fault" class is quiescent pre-fault data only), ideal V/I with no CT/VT and
no noise. And the centralised 8-relay input means these numbers are *not* achievable by a local
relay, which is the setting WP3 and WP4 actually target.

**Value to us — this is the protocol paper, and we should copy it.**
- The experimental skeleton is exactly what WP3 needs: **sweep one axis, hold sensing/timing/
  validation identical, report macro-F1 with std over runs**. Swap their x-axis (window length) for
  ours (**injection amplitude**), keep everything else, and we have a directly comparable,
  defensible design.
- Adopt their **5 ms stride** (relay interrupt cadence) and **episode-grouped CV**. Adopting
  group-CV also fixes the leakage flaw in Beikbabaei et al.
- Their runtime table is a useful **CPU reference point for WP4**: an MLP at 0.56 ms and a decision
  tree at 0.04 ms on one desktop core means the model is not the bottleneck — the feature pipeline,
  the data window and the hardware will be.
- Their ~10 % localisation floor is a useful caution if anyone on the team wants to add fault
  location as a stretch goal: on this topology it is structurally capped, not a modelling failure.
- **What we cannot claim as novel**: that a learned detector works from a 10 ms (sub-cycle) window;
  that an MLP outperforms tree ensembles at short horizons; that fault-type information appears in
  the earliest transient; the window-sweep + grouped-CV evaluation protocol itself.

---

## 18. Latency-Aware Deep Learning Benchmark

**Full citation.** E. Abukhousa, S. Zonouz, and A. P. S. Meliopoulos, "Latency-Aware Deep Learning
Benchmark for Real-Time Cyber-Physical Attack and Fault Classification in Inverter-Dominated Power
Grids," arXiv:2605.17256 [eess.SY], 17 May 2026. Georgia Institute of Technology.

**Where to download.** **Nothing is released — no dataset, no code, no repository.** The data were
generated with **WinIGS v8.1.5** (Advanced Grounding Concepts, Alpharetta GA), a **proprietary
commercial** simulator. Reproducibility is limited to the reported hardware config (Google Colab,
Linux 6.1.123, 1 physical core / 2 threads @ 2.20 GHz, 12.67 GB RAM, one NVIDIA Tesla T4,
TensorFlow 2.19.0). **We cannot use this as data. Do not plan around it.**

**Contents (as described).** An "inverter-rich microgrid" testbed: **50 kVA PV inverter + 30 kVA
BESS**, step-down transformers, distribution lines, diverse loads. Only **Protection Zone 2** is
instrumented, with two merging units MU23 and MU32 emulating IEC 61850 Sampled Values, exported
via COMTRADE. **14 features** total = 2 MUs × 7 signals (I_a, I_b, I_c, **I_n**, V_an, V_bn, V_cn).
**105,768 samples over 22 s at 4,800 Hz** (208 µs resolution). Plus two short held-out streaming
sequences: "Prediction Dataset 1" (5 consecutive anomalies) and "Prediction Dataset 2" (4
anomalies), events placed at 1.0–1.2, 2.0–2.2, 3.0–3.2, 4.0–4.2 and 5.0–5.2 s.

**Labels.** An 18-entry taxonomy (classes 0–17): 0 Normal Operation; 1–3 SLG (A-N, B-N, C-N);
5–7 LL (AB, AC, BC); 9–11 DLG (AB-N, AC-N, BC-N); 14–15 three-phase (ABC, ABC-N); and the cyber
classes 4 & 8 CT-ratio attacks, 12–13 PT-ratio attacks, 16–17 GPS-spoofing attacks (each on MU23 or
MU32). **No fault resistance, no fault location, no inception angle, no operating point is
labelled**, and there is no localisation task. *Two internal inconsistencies worth flagging if we
cite it*: the abstract and text say "17 different physical faults and cyber-attacks" while the
taxonomy table lists 18 entries (0–17); and class 4 is a CT attack on MU23 in Table I but is
reported as "CT Attack MU32 (4)" in the streaming ground-truth table.

**Inverter-based sources?** **Yes** — PV inverter and BESS, described as a DER-integrated,
inverter-rich microgrid "where inverter control dynamics dominate transient behavior." But the
**control mode (GFL or GFM) is never stated**, the inverter share is never quantified, there is one
fixed topology, and one operating point across only 22 s.

**Non-fault events?** **No.** Only class 0 "Normal Operation" plus the cyber-attack classes. There
are **no load steps, motor starts, transformer inrush or capacitor switching events**. So despite
being the most "inverter-rich" of the four, it does not help our security question either.

**Auxiliary / negative-sequence injection?** **No.** (The CT/PT-ratio attacks are measurement-chain
manipulations, not injected physical signals — superficially similar framing, completely different
mechanism. Worth one sentence of distinction if we cite it, so nobody confuses the two.)

**Models and sizes.** Eight architectures, input = sequences of **50 samples, stride 1** (≈10.4 ms
at 4.8 kHz). Parameter counts (Table II): Transformer 36,434; ST-GCN 67,730; **MLP 157,394**;
TCN 195,136; LSTM 279,826; 1D-CNN 285,842; CNN-LSTM 542,290; ResNet1D 977,106. (*The body text
claims the MLP has "49k parameters" — inconsistent with its own table.*) Split 70/10/20
"stratified block-based," class weights for imbalance, 40 epochs, Adam, sparse categorical
cross-entropy, early stopping + LR reduction.

**Results with numbers.**
*Offline training performance (accuracy / balanced acc. / macro-F1):* MLP **99.66 / 99.88 / 99.53**;
1D-CNN 98.89 / 99.77 / 98.71; CNN-LSTM 97.13 / 99.65 / 96.84; LSTM 97.09 / 99.64 / 96.79;
ResNet1D 96.21 / 99.52 / 95.87; ST-GCN 95.89 / 99.49 / 95.52; Transformer 95.37 / **99.88** / 95.00;
TCN 94.32 / 99.35 / 93.93.

*Streaming performance, 100 runs of Event 1 (accuracy / coverage / classification time / mean
inference latency):*

| Model | Acc % | Coverage % | Class. time (ms) | **Latency (ms)** |
|---|---|---|---|---|
| MLP | **97.57** | 97.57 | **3.38** | **57.20** |
| Transformer | 96.86 | 97.15 | 6.29 | 67.77 |
| ST-GCN | 96.44 | 96.59 | 4.25 | 88.89 |
| 1D-CNN | 95.73 | 96.67 | 8.54 | 70.22 |
| ResNet1D | 95.03 | 96.11 | 5.29 | 72.42 |
| LSTM | 93.40 | 89.41 | 12.63 | 58.25 |
| CNN-LSTM | 92.59 | 97.34 | 14.83 | 69.64 |
| TCN | 90.88 | 92.50 | 4.17 | 61.68 |

**The headline is the gap**: classification time is sub-cycle (**3–15 ms**) for every model, but
**end-to-end inference latency is 50–90 ms — more than three cycles** — so "at present, the latency
profile is more suited for control and situational awareness functions" rather than primary
protection. Also reported: raw streaming predictions jitter badly and are "unsuitable for practical
protection"; a one-cycle moving average plus a confidence gate (τ = 0.6) stabilises them; an
out-of-zone SLG fault the model had never seen was correctly *abstained* on (class −1) rather than
misclassified, via the confidence drop.

**Stated limitations.** Models need retraining across loading scenarios; more edge cases needed
(conductor loss, more diverse fault conditions); latency requires "hardware acceleration" and
"high-performance industrial hardware."

**Unstated limitations — important, because WP4 will be tempted to cite these numbers.**
1. **The smoothing filter is non-causal.** Equation (1) is a *centred* moving average with
   N_cyc = 80 and N_half = 40, which the paper itself admits "introduces ≈8.3 ms look-ahead."
   A relay cannot look into the future. Every reported classification time should be read as
   **+8.3 ms** for a causal implementation, which pushes several models past one cycle.
2. **The latency figure is soft.** 50–90 ms is Python + TensorFlow on a shared Google Colab VM with
   one 2.2 GHz core. It is an upper bound of poor quality and says almost nothing about a fixed-point
   C implementation on a Cortex-M or a small FPGA. **Our WP4 number should be far better and we
   should say why, rather than treating 50–90 ms as a real floor.**
3. **Probable optimism in the 99.66 %.** 50-sample windows at stride 1 overlap by 49/50; with only
   22 s of data from a single testbed and a "stratified block-based" split, adjacent near-duplicate
   windows can straddle the split. Contrast the FAU papers' insistence on episode/topology grouping.
4. One topology, one operating point, no fault resistance or location variation.

**Verdict for WP3/WP4.** **As a dataset: unusable — nothing is released.** As a reference it is
still the most directly relevant paper for **WP4**, for three reasons: it is the only one that
separates *classification time* from *inference latency* (a distinction we should adopt verbatim in
our own reporting); it demonstrates a **confidence-gated abstention policy** that produces a safe
"unclassified" output on out-of-zone events, which is a genuinely good idea for a relay and cheap
for us to implement; and it establishes the one-cycle framing (16–34 ms) we are already using.
Cite it as the state of the art we intend to beat on latency, and be explicit about the
non-causal-filter caveat so our comparison is fair in both directions.

---

# What this means for the team — concrete data plan

**Recommendation: EvEMTBench primary, PROTECT-90 secondary, our own EMT simulation for the
treatment arm.** Three tiers:

**Tier 1 — security / false-alarm (EvEMTBench, 20 kV + 110 kV).** Run all three detectors over the
13 non-fault event classes (motor start, LV and HV transformer inrush, capacitor on/off, load
on/off, line and cable energisation, synchronous-machine trip, IBR trip) and report a false-trip
rate per detector. This is the single highest-value thing the public data unlocks, it is impossible
with our current self-generated data, and it will be the first question asked at review. Use
simulation-level splits on adaptgrid and topology-level splits on multigrid.

**Tier 2 — front end and conventional elements (PROTECT-90).** Validate phasor extraction,
incremental quantities and sequence decomposition at 128 samples/cycle against 9,022 labelled
faults with known R_f, location and line parameters. Characterise our 50/51, 21 and 67Q elements
where ground truth is exact and the topology has genuine intermediate infeed and parallel-line
coupling. This is also our inverter-free control arm.

**Tier 3 — the actual WP3 experiment (ours).** The injection-amplitude sweep still requires our own
EMT simulation, because no public dataset contains an auxiliary signal — a fact we should state
plainly in the report as a contribution in itself. Build it to be *label-compatible*: mirror
EvEMTBench's `settings_clean.csv` field names and PROTECT-90's channel naming convention so our
episodes can be concatenated with theirs and so a reviewer can see the schema is not ad hoc.

**Four caveats to write into the report up front.**
1. **No grid-forming inverters exist in any public dataset here.** EvEMTBench is GFL-only by
   explicit choice; PROTECT-90 has no inverters; the Georgia Tech testbed does not state its mode.
   If our auxiliary signal assumes a GFM inverter, that gap is ours to fill and ours to disclose.
2. **No CT/VT models and no measurement noise anywhere.** All four sources use ideal primary
   quantities. The survey's own authors warn to "be careful about some conclusions" for exactly this
   reason. Adding a CT saturation model and realistic noise to our own data would be a cheap,
   genuinely differentiating robustness result.
3. **Frequency mismatch.** Everything with inverters is 50 Hz; the only 60 Hz grid in EvEMTBench
   (IEEE 39-bus) has no IBRs. Our 16.7 ms budget is a 60 Hz number. Either state the budget as "one
   cycle" generically or resample, but do not silently mix them.
4. **The FRT confound.** EvEMTBench's GFL inverters already inject negative-sequence inductive
   reactive current during unbalanced faults as grid-code fault ride-through. Any negative-sequence
   detector we evaluate on it will partly be detecting the inverter's own FRT response, not the
   fault. Control for this explicitly or the result will be challenged.
