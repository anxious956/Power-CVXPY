# Project plan

Last updated 16 Sep 2026.

## Goal

Test Taylor's auxiliary-signal design in realistic simulation and on hardware, and measure three things nobody has measured:

1. **Theory vs practice.** The design gives a theoretical minimum signal. Where does it actually stop working under load, noise and inverter dynamics?
2. **Model-based vs learned detection.** Does a learned detector catch a smaller signal than the multiple-model Kalman filter of Taylor's 2022 paper? Either answer is a result.
3. **Latency.** Can either detector decide within one cycle (16.7 ms at 60 Hz) on an embedded board?

A fourth, optional: how much does the incremental-quantity characteristic (Taylor 2026) drift under real inverter control modes, the assumption the paper itself flags as weak for IBRs.

## Work packages

### WP1 Design tool (optimization)
- Generalize `src/aux_model.py` from two buses to an n-bus admittance model (the paper uses IEEE 14-bus).
- Replace grid enumeration of (m, mr) with the paper's convex relaxations (Sec. V-E).
- Per-IBR auxiliary signals, not one shared δ.
- Output: `design_signal(grid) -> delta` plus a plot of separating sets.
- Skills: Python, CVXPY, linear algebra. Reading: Geometry paper in full, TAC 2025 paper via NJIT library.

### WP2 Simulation (data factory)
- Build a test grid: 1 SG, 1–2 inverters (grid-following and grid-forming), 3–5 lines. Start from NREL PyPSCAD open models or Simulink Simscape Electrical.
- Add negative-sequence injection to the inverter current reference, triggered by the inverter's own fault indicator.
- Scenario matrix: fault type (ag, ab, abc), location, resistance, inverter share, load level, noise. Also non-fault events: load steps, motor start, transformer inrush.
- Output: labeled relay measurements (three-phase v, i, at 4 to 8 kHz) as `.npz`, and a scenario table.
- Skills: Simulink or PSCAD. This is the critical path; everything downstream waits on it.

### WP3 Detection
- Implement the MMKF detector from Pirani et al. 2022 on WP2 data.
- Implement a learned detector (1D CNN + BiLSTM, six channels) on the same data.
- Shrink δ in steps; for each detector find the δ where miss rate or false-alarm rate exceeds a threshold. Plot both curves with the WP1 theoretical minimum as a vertical line.
- Skills: Python, PyTorch, signal processing.

### WP4 Embedded
- Port the two detectors to a Jetson (or Raspberry Pi 5). Stream WP2 waveforms in real time; measure end-to-end decision latency and jitter.
- Deliverable: a live demo, "fault injected, signature detected in X ms."
- Skills: Linux, Python or C++, basic embedded.

## Milestones

| When | What |
|---|---|
| Sep 2026 | Advisor confirmed. Roles assigned. Everyone read the Geometry paper Sec. I, II, VI. |
| Oct 2026 | WP2 test grid running with one inverter and manual fault. WP1 tool handles the same grid. |
| Nov 2026 | Scenario matrix generated. WP3 MMKF running. WP4 board set up. |
| Dec 2026 | First "theory vs practice" curve. Senior design fall report and demo. |
| Feb 2027 | Both detectors compared. Latency measured. |
| Mar–Apr 2027 | Paper written. Senior design final. |
| Jun 2027 | Submit to NAPS 2027 (deadline expected mid-June; 2026's was 15 June). |

## Target venues

- **Primary: NAPS 2027** (North American Power Symposium). IEEE, hakemli, student-friendly. Whole project as one paper.
- **If the advisor wants it early: IEEE PES General Meeting 2027**, San Francisco, deadline 10 Nov 2026. Only if he decides the static-model results plus first simulations are enough.
- **Applied half: Texas A&M Conference for Protective Relay Engineers**, Mar 2027. Relay-side implementation and latency.
- **ML half, if split out: IEEE MLSP 2027 or SmartGridComm 2027.**

## Risks

| Risk | Effect | Mitigation |
|---|---|---|
| No one strong in Simulink | No data, everything stalls | Assign WP2 first; pair with the optimization person; use NREL open models to avoid building from zero |
| Advisor's simulator not shared | 2–3 weeks lost | Start from NREL PyPSCAD or Simulink regardless |
| Advisor uninterested in ML | WP3 loses half | WP3 becomes "MMKF in realistic simulation," still a result |
| Team member drops | WP4 unstaffed | WP4 is optional; core is WP1–3 |
| Simulation too slow for the scenario matrix | Small dataset | Reduce matrix; use PROTECT-90 / IRTSD public EMT data for pretraining |

## Open questions for the advisor

1. Is the NSF project's simulation environment available to the team? In which tool?
2. What is the PhD student working on, so we do not duplicate?
3. Would a learned detector interest you, or should WP3 stay model-based?
4. Co-authorship expectations if this becomes a paper.

## Public data and models to lean on

- PROTECT-90: 9,022 EMT fault episodes, low short-circuit power (Zenodo 18418330).
- IRTSD: IBR-rich transmission datakit with model and scripts (TechRxiv).
- NREL PyPSCAD: open grid-following and grid-forming inverter models, IEEE 9-bus (github.com/NREL/PyPSCAD).
- IEEE Std 2800: the negative-sequence injection requirement Taylor cites.
