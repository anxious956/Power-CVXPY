# KIUC with several inverters, grid-following and grid-forming

> **Status, 3 Nov 2026: pre-registered, reviewed (PR #70), amended per the review; nothing built or run.**

## 0. Why

Prof. Taylor's 20 Oct asks (docs/meetings/2026-10-20_biweekly.md): a system with several inverters, some
grid-forming (GFM) and some grid-following (GFL); an all-inverter system run to equilibrium first, then faulted.
The NREL report he sent (NREL/TP-5D00-94430) has both inverter types but tests one inverter at a time on the
KIUC line (§3.1); it never mixes them. We keep the report's KIUC network and values (docs/KIUC.md, merged in
PR #65) and add inverters to it. Static and EMT, no δ in this study.

## 1. Step A: a grid-forming inverter in PSCAD, from the report

**What the report specifies (§2.2):** droop primary control (PC1), eqs (10)–(13): P and Q from v_C and i_O
through a low-pass τ_S, ω_r = ω_N − n_P (P − P_ref), V_r = V_N − m_Q (Q − Q_ref); an outer-voltage / inner-current
cascade (dq, αβ or sequence domain); current limiters: saturation (d- or q-priority), latching, or virtual
impedance (eqs 16–17: R_vir = k_p^Rvir (RMS(i_L) − i_sat) when positive, X_vir = σ_X/R R_vir); I_sat 1.2 pu;
IEEE 2800 negative-sequence injection available for GFM (§2.2.2.4). VSM (PC2) is the alternative primary.

**What we build (`gfm_avm`, averaged like our `gfl_avm`).** *[Amended 3 Nov 2026 after the review (PR #70),
before anything was built; the first draft had the virtual-impedance limiter as primary, X_c = 0.15, a mode called
"suppressed" that was not, and a layout that put the GFMs outside R2's view.]*
- **Primary:** droop as eqs (10)–(13); an ideal three-phase voltage source behind **X_c = 0.06 pu** on 15 MVA (L_g
  ≈ 0.003 pu plus TF2's 6 % as in docs/KIUC.md; sensitivity 0.03 and 0.09). No LCL, no inner loops: the averaged
  equivalent of a fast cascade.
- **Primary limiter: the report's q-priority saturation**, the one its Fig. 16, Table 17 and Appendix A use: when
  the source's current would exceed 1.2 pu, the inverter switches to current-limited operation with the
  `gfl_avm` LIM logic (I_Q+ first, I_P+ cut), and back when it no longer would.
- **Second limiter, information only:** the virtual-impedance limiter, eqs (16)–(17), k_p^Rvir = 1, σ_X/R = 5.
  Expected now, by arithmetic: a bolted terminal fault settles near **1.32 pu**, not 1.2 (k_p ≥ 3 would be needed),
  and it never gives Fig. 16's I_P+ → 0 / I_Q+ → 1.2. Run in Step B as information.
- **Three negative-sequence modes, with the 32Q / 32QG outcome expected now:**
  - **natural** (no negative-sequence EMF behind X_c): a negative-sequence short, I2 ≈ |V2|/X_c (effective K ≈ 17
    at X_c 0.06) leading V2 by ~90°, a machine's response → **enabled, forward**;
  - **suppressed** (I2 = 0 by a negative-sequence current loop, i⁻_ref = 0, report §2.3.1) → **not enabled**;
  - **IEEE 2800** (I2 = K V2 ∠ 90°, K = 5, through the limiter) → **forward**.
- **Gains the report does not give — ours, fixed now:** n_P = 0.02 pu, m_Q = 0.05 pu, τ_S = 1/(2π·5 Hz);
  sensitivity n_P, m_Q ×0.5 and ×2. **VSM is not built:** the report's Table 26 says droop vs VSM changed neither
  the fault current nor the relay response.

**Step A checks (go/no-go before Step B):**
- A1 static: the GFM's steady state from `network.solve` with the GFM as a voltage source behind X_c (new
  source kind; its negative-sequence branch is the mode above) matches EMT at the nominal point within 3 % in |V1|
  and |I1|.
- A2 the report's Fig. 16 pair (P 0.25 / Q 0.15, IEEE 2800, bolted A-G at 5 %), primary limiter: the GFM's phase
  current at or below 1.2 pu peak in the steady fault state (± 5 %), I2 leading V2 by 90° ± 15°; the I_P+ → 0 read
  is static / TF2 YgΔ only, as in docs/KIUC.md.
- **A3 the report's Appendix A.1 statement** (with regulated I2, GFM and GFL give the same relay decisions):
  **expected to pass**, near-tautologically, because in limit both are current sources with the same I2 law.
  Pass rule: decisions agree on ≥ 90 % of clean cases of the forward set below. Its informative output is the
  per-case |I2|, ∠I2 − ∠V2 and 3I2/I1 of both types, the quantities the report's Figs A-1 / A-2 compare.

## 2. Step B: KIUC with 3 and 5 inverters

**Network (ours, from the report's values):** the KIUC line as built (grid behind EQ, BUS1, Line 2, BUS2 with
the 15 MVA inverter, relay R2 at BUS2 looking into Line 2). New 15 MVA inverter buses on their own 57.1 kV
2-mi lines with Line 2's per-mile impedance: **B3, B4 off BUS2 (behind R2)** and B5, B6 off BUS1 (grid side). All
at P 0.25 / Q 0.15. Hydro off. TF2 ΔYg for every inverter, as in docs/KIUC.md.

| case | inverters | GFM at | grid source | note |
|---|---|---|---|---|
| M3 | BUS2, B3, B4 | — | on | 3 GFL |
| M5 | BUS2, B3–B6 | — | on | 5 GFL |
| M5-mixR2 | BUS2, B3–B6 | **B3, B4** (behind R2) | on | 2 of 5 GFM, their I2 passes R2 |
| M5-mixG | BUS2, B3–B6 | B5, B6 (grid side) | on | information: GFMs outside R2's view |
| M5-island | BUS2, B3–B6 | B3, B4 | **off** | all-inverter, 2 GFM + 3 GFL |
| M5-allGFM | BUS2, B3–B6 | all five | **off** | Taylor's all-GFM grid |

**The islands, made consistent now (they would fail B1 by arithmetic otherwise):**
- **Power balance:** a constant-impedance load at BUS1 equal to the sum of the inverters' references, 5 × (0.25 +
  j0.15) = 1.25 + j0.75 pu on 15 MVA (18.75 MW + j11.25 Mvar at 1.0 pu), so the GFMs sit at their references and
  the droop frequency at 60 Hz. Without it, three GFLs at +0.25 force the two GFMs to −0.375 and droop gives
  +0.75 Hz.
- **Ground:** every TF2 is ΔYg and the grid behind EQ was the only zero-sequence source, so the islands get a
  **grounding bank at BUS1, X0 = j0.06 pu on 15 MVA**; A-G cases are read with it.
- **Static solution without a slack:** angle reference at one GFM (B3), P shared by n_P, V by m_Q (a droop power
  flow), with the GFLs as current sources.

**Fault set (the KIUC forward set, `src/kiuc.py` FWD):** on Line 2 at 5, 50 and 80 % from BUS2, A-G and B-C,
R_f 0.01 and 5 Ω: 12 cases. Every inverter in the same I2 mode per run: suppressed, IEEE 2800, and for GFMs also
natural. Logged per inverter: limiter state, phase peak, the weak-frame flag at BUS2.

**Questions and go/no-go:**
- **B1 equilibrium** (Taylor's "check it runs in equilibrium first"): before the fault, bus |V1| within 0.95–1.05
  pu, frequency within ±0.5 Hz of 60 Hz and drifting less than 0.05 Hz/s over the last 100 ms, inverter currents
  within 3 % of the static solution, the GFMs' P and Q within 3 % of the droop solution. A case that fails is
  reported as failing, with why; it is not tuned until it passes.
- **B2 faults:** read at R2 as in docs/KIUC.md (the report's 32Q / 32QG, our incremental element, EMT against
  static). **"Changed"** = the decision class (right / not enabled / wrong) differs from KIUC's single-inverter
  result on ≥ 2 of the 12 cases. **Priors, written now:** all inverters behind R2 suppressed → 32Q not enabled
  (M3, M5, M5-mixG; KIUC's result); IEEE 2800 everywhere → forward, right; **GFMs behind R2 in natural mode →
  32Q enabled and forward even with the GFLs suppressed** (M5-mixR2, islands), because the GFMs then supply I2
  like machines; GFMs suppressed → back to not enabled.

## 3. What this does not do

No δ design or injection; no VSM (Table 26); no LCL or inner loops; no switching model; one operating point.

## 4. Code and drawing

`src/gfm.py` (static source model, PSCAD controller), `src/kiuc_multi.py` (cases, runs, analysis); the PSCAD
builds drawn readably (aligned rows, real wires, English labels) as `src/pscad_view.py` does for KIUC.
