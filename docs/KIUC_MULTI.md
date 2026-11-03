# KIUC with several inverters, grid-following and grid-forming

> **Status, 3 Nov 2026: pre-registered, nothing built or run.** Waiting for the reviewer.

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

**What we build (`gfm_avm`, averaged like our `gfl_avm`):** droop primary as eqs (10)–(13); the inverter as an
ideal three-phase voltage source behind a coupling reactance X_c (no LCL, no inner loops: the averaged
equivalent of a fast cascade); current limit by the report's virtual-impedance limiter (eqs 16–17) on the
positive sequence; negative sequence: suppressed (v⁻ = 0 at the source) or the IEEE 2800 law as for gfl_avm
(I2 = K V2 ∠ 90°, K = 5), added as a negative-sequence current through the same limit.

**Values the report does not give — ours, fixed now:** n_P = 0.02 pu (2 % frequency per pu P), m_Q = 0.05 pu,
τ_S = 1/(2π·5 Hz), X_c = 0.15 pu, k_p^Rvir = 1.0 pu/pu, σ_X/R = 5. Sensitivity: n_P, m_Q ×0.5 and ×2.

**Step A checks (go/no-go before Step B):**
- A1 static: the GFM's steady state from `network.solve` with the GFM as a voltage source behind X_c (new
  source kind) matches EMT at the nominal point within 3 % in |V1| and |I1|.
- A2 the report's Fig. 16 pair (P 0.25 / Q 0.15, IEEE 2800, bolted A-G at 5 %): the GFM's phase current stays
  at or below 1.2 pu peak in steady fault state (± 5 %), and I2 leads V2 by 90° ± 15°.
- **A3 the report's Appendix A.1 statement:** with regulated I2 (IEEE 2800), the GFM and the GFL give the same
  decisions at R2 (32Q / 32QG, our incremental element) on the KIUC Q2 forward set. **Reproduced** if the
  decisions agree on ≥ 90 % of clean cases; **not reproduced** otherwise.

## 2. Step B: KIUC with 3 and 5 inverters

**Network (ours, from the report's values):** the KIUC line as built (grid behind EQ, BUS1, Line 2, BUS2 with
the 15 MVA inverter, relay R2 at BUS2 looking into Line 2). New inverter buses B3–B6, each 15 MVA, each on its
own 57.1 kV line with Line 2's per-mile impedance: B3 and B4 off BUS2 (2 mi each), B5 and B6 off BUS1 (2 mi
each). All at P 0.25 / Q 0.15. Hydro off. Zero-sequence paths as in docs/KIUC.md (TF2 ΔYg for every inverter).

| case | inverters | types | grid source |
|---|---|---|---|
| M3 | BUS2, B3, B4 | 3 GFL | on |
| M5 | BUS2, B3–B6 | 5 GFL | on |
| M5-mix | BUS2, B3–B6 | B5, B6 GFM; others GFL | on |
| M5-island | BUS2, B3–B6 | B5, B6 GFM; others GFL | **off** (all-inverter) |

**Questions:**
- **B1 equilibrium** (Taylor's "check it runs in equilibrium first"): each case settles before the fault: bus
  |V1| within 0.95–1.05 pu, frequency within ±0.5 Hz of 60 Hz and drifting less than 0.05 Hz/s over the last
  100 ms, inverter currents within 3 % of the static solution. A case that fails is reported as failing, with
  why; it is not tuned until it passes.
- **B2 faults:** the KIUC forward set on Line 2 (A-G, B-C at 20/50/95 %, R_f 0.01 / 5 Ω), I2 suppressed and
  IEEE 2800 in every inverter. Read at R2 as in docs/KIUC.md: the report's 32Q / 32QG, our incremental element,
  EMT against static. Prior from KIUC: suppressed → 32Q not enabled; IEEE 2800 → right. We report whether more
  inverters, GFM inverters, or no grid change that.

## 3. What this does not do

No δ design or injection; no VSM (droop only, VSM later if A3 passes); no switching model; one operating point.

## 4. Code and drawing

`src/gfm.py` (static source model, PSCAD controller), `src/kiuc_multi.py` (cases, runs, analysis); the PSCAD
builds drawn readably (aligned rows, real wires, English labels) as `src/pscad_view.py` does for KIUC.
