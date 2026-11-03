# Review of the KIUC multi-inverter pre-registration (branch `kiuc-multi`, docs/KIUC_MULTI.md at `6bb8f78`)

Reviewer: the independent review session, 3 Nov 2026. Read against NREL/TP-5D00-94430 (§2.2, §2.3.1, Fig. 16 and
its text, §5.2.1.4 and Table 17, Table 26, Appendix A.1–A.2, the conclusions), docs/KIUC.md and src/kiuc.py on
main, and the 20 Oct minutes. Nothing has been built or run.

## Verdict

**Not cleared as written; cleared once §1–§4 below are in the doc.** None of it is tuning: four of the items are
things the plan would fail or mis-measure by construction, knowable now from the report and from arithmetic, which
is exactly what a pre-registration is for. The three points research asked about are answered in §1 (stand-in),
§3 (layout) and §4 (island thresholds).

## 1. The GFM stand-in and the limiter it is tested with

**(1) An averaged voltage source behind a reactance is an acceptable stand-in for the steady fault state, but
only with the limiter the report's figures use.** The report's Fig. 16 text: "the current limiter for both the
GFL IBR and the GFM IBR are selected as a q-priority saturation-based limiter scheme" (sequence-domain control,
switch-average model); Table 17, the fixed GFM parameters for §5.2.1.4: average model, dq voltage and current
control, **current limiting "saturation on q-axis"**, TF2 YgΔ for ground faults, fault at 5 % from the IBR end;
Appendix A.1: "regulated negative-sequence current control and identical settings". The plan instead gives the
GFM the virtual-impedance limiter (eqs 16–17) and then tests it against Fig. 16 (A2) and Appendix A (A3). Two
consequences:
- *A2 fails by construction.* The virtual-impedance limiter is proportional: R_vir = k_p (RMS(i) − i_sat), so the
  steady current sits above i_sat by an amount set by k_p. With the registered k_p = 1 pu/pu, σ = 5 and X_c = 0.15,
  a bolted fault at the terminal settles at I ≈ 1.32 pu (solve (1.2 + e)·|jX_c + (1 + j5) e| = 1 for e); the
  registered "≤ 1.2 pu ± 5 %" needs k_p ≳ 3. And a virtual impedance never gives Fig. 16's I_P⁺ → 0, I_Q⁺ → 1.2:
  that profile is the q-priority saturation.
- *The reproduction limiter is the saturation one.* For A2 and A3 register the q-priority saturation limiter as
  the GFM's primary: in the averaged model the source switches to current-limited operation (I_Q⁺ first, I_P⁺
  with what is left, the I2 law kept, i.e. the `gfl_avm` LIM machinery) whenever the voltage-source current would
  exceed 1.2 pu, and returns to voltage-source operation when it would not. The virtual-impedance limiter stays as
  the GFM's second registered limiter ("primarily used for GFM IBRs", §2.2.2.3.1), run in Step B as information
  with its own expectation (≈ 1.3 pu at k_p = 1), not scored by A2.
- *A3 is then nearly a tautology, and should say so.* In limit with regulated I2, a GFM and a GFL are both current
  sources with the same I2 law and the same |I1| cap; what differs is the positive-sequence angle reference (droop
  θ_r against the GFL's filtered V1 frame). The report's own conclusion is the same ("their fault currents are
  limited by the current limiter… as long as they produce a reliable negative-sequence current"). So write the
  expectation "A3 passes" now, and make A3's informative output the per-case |I2|, ∠I2 − ∠V2 and 3I2/I1 of the two
  types, which is what Figs A-1/A-2 actually compare, beside the decisions. Note also that Appendix A.1 is two
  figures (one AG, one BC) at one operating point; the 14-case, ≥ 90 % form is ours.
- Droop against VSM: Table 26 says the outer loop did not change the fault current or the relay response, so
  "droop only" is the report's own finding, not a gap. Cite it instead of "VSM later".

**The coupling reactance.** The report regulates the filter-capacitor voltage v_C; between v_C and the 57.1 kV
bus sit L_g (1.5 μH, ≈ 0.003 pu on the 480 V, 1.25 MVA base of Table 1) and the step-up transformer, whose
reactance KIUC assumed at 6 %. So the physical X_c is ≈ X_TF2 ≈ 0.06 pu, not 0.15. Register X_c = 0.06 (the KIUC
assumption, with its 3–9 % sensitivity) or justify 0.15; it enters the natural negative-sequence current directly
(§2).

## 2. The negative-sequence modes are mislabelled

"Suppressed (v⁻ = 0 at the source)" is not suppression. A voltage source with no negative-sequence EMF behind
X_c is a negative-sequence short: at the terminal I2 = −V2/(jX_c + Z_vir), magnitude ≈ |V2|/X_c (an effective
K of 1/X_c: 6.7 at 0.15 pu, 17 at 0.06, above the report's K = 5 and then limited), angle leading V2 by about
90°. That is a synchronous machine's response, and it enables 32Q/32QG and declares forward just as the IEEE 2800
law does. Suppression (I2 = 0) needs a negative-sequence current loop (the report's sequence-domain control with
i⁻_ref = 0, §2.3.1); in the averaged model, a controlled negative-sequence source cancelling the natural current.
Register three GFM modes, each with its expected 32Q outcome written now: **natural** (v⁻ = 0: enabled, forward),
**suppressed** (I2 = 0: not enabled), **IEEE 2800** (K = 5: forward). This changes B2's prior for every case with a
GFM behind R2, and the natural mode is the one a plain "voltage source behind X_c" build gives by default.

## 3. Layout (point 2)

- **The GFMs are invisible to R2 where the plan puts them.** R2 at BUS2 measures the current from BUS2 into
  Line 2, i.e. the inverters behind it (BUS2, B3, B4). B5 and B6 hang off BUS1, on the grid side: in M5-mix their
  I2 flows into the fault from BUS1 and never through R2, so "whether GFM inverters change R2's decision" is
  not tested by M5-mix. Add (or swap to) a case with the GFMs at B3/B4, behind R2.
- **Taylor's asks are three, the plan covers one and a half.** The minutes: a mix of GFM and GFL (M5-mix, M5-island:
  covered); "a grid with all grid-forming inverters: check whether it can run in equilibrium, then simulate a
  fault" (not covered: add an all-GFM island, M5-gfm-island or M3-gfm-island); "half grid-forming, half
  grid-following" (M5-mix is 2 of 5; say so, or make the mix 2 + 2 on an M4).
- **Fault locations.** B2 says "A-G, B-C at 20/50/95 %"; the KIUC forward set is at **5 / 50 / 80 % from Bus-2**,
  R_f 0.01 / 5 Ω (src/kiuc.py `M_IBR`), 12 cases plus ABC. Fix the text or register the change.
- The 2-mi stubs (0.43 of Line 2: 0.0021 + j0.0064 pu on 15 MVA) are fine as a design. With three inverters
  behind R2 the forward-set current at R2 can reach 3 × 1.2 pu; log per inverter the limiter state and phase
  peak, and keep KIUC's weak-frame flag at BUS2.
- Every inverter's TF2 is ΔYg (no zero-sequence path at any inverter bus): with the grid on, the only ground
  source is the grid behind EQ, as in KIUC. See §4 for what that does to the island.

## 4. M5-island (point 3): two failures knowable now

- **Power balance.** The KIUC model has no load. With the grid off, the three GFLs inject 0.25 pu each and the two
  GFMs must absorb it: P_GFM = −0.375 pu against P_ref = +0.25, so the droop gives ω_r = ω_N + n_P · 0.625 =
  +1.25 %, **+0.75 Hz at n_P = 0.02 (1.5 Hz at the ×2 sensitivity)**. B1's ±0.5 Hz fails by arithmetic before PSCAD
  runs; "reported, not tuned" would then report a result that was decided in the registration. Register the island's
  balance now, as a design choice, not a tuning: a load (at BUS1, sized so the GFMs sit at their references,
  ≈ 1.25 pu of 15 MVA active plus the matching reactive), or GFM P_ref = −0.375 (absorbing; the report notes GFM
  IBRs need a stiff DC source, which makes it legitimate), or isochronous PC3 (n_P = 0). The voltage side is fine
  as is: the GFMs absorb ≈ 0.19 pu Q each, V_r = 1 + m_Q · 0.34 ≈ 1.02. A frequency offset also enters the GFLs'
  reference frames and the relay's DFT (off-nominal phasor ripple), a second reason to balance.
- **Grounding.** The grid behind EQ was the island's only zero-sequence source; with every TF2 ΔYg and no line
  charging, the island has no ground path. An A-G fault then draws no fault current, and in PSCAD the floating
  network's zero-sequence voltage is undefined (singular without a shunt). Register a grounding bank at BUS1
  (zig-zag or Yg, stated X0) for the island cases, or state that the island's A-G cases are "no ground current, not
  read" and score only B-C.
- With those two fixed, B1's thresholds are adequate: ±0.5 Hz with n_P = 0.02 tolerates a 0.42 pu imbalance;
  the 0.05 Hz/s drift and the 3 % current match are fine. Add the GFMs' P and Q within 3 % of the droop solution.
- Static island: say how `network.solve` handles a network with no slack: angle reference at one GFM, P shared by
  the n_P's at a common frequency, V by the m_Q's.
- "A case that fails is reported, not tuned until it passes" is the right stop rule *after* the registration is
  consistent; it is not a substitute for fixing a failure that is already visible on paper.

## 5. Smaller items

- A1: the static GFM is an SG-type source (EMF behind jX_c, E = V_r from the Q droop at the operating point); the
  negative-sequence impedance of that source is the mode of §2 (natural: jX_c; suppressed: open; IEEE 2800: the
  law). Say which.
- A2 is defined in KIUC on the YgΔ ground-fault case (static only; the PSCAD builder has no grounded inverter
  bus); with ΔYg the dip is shallower (KIUC: I_P⁺ 0.25 at K1 = 4). Keep A2's EMT criterion to the phase-peak and
  I2-angle reads, as the plan does, and say the I_P⁺ → 0 read is static/YgΔ only.
- B2 has no go/no-go. Register one: per case and mode, the report element's and the incremental element's
  decision against KIUC's single-inverter result; "changed" if the decision class differs on ≥ 2 of the 12
  A-G/B-C cases; and the priors per case written now (M3/M5 suppressed → not enabled, IEEE 2800 → forward;
  natural-mode GFM behind R2 → enabled and forward even with the GFLs suppressed; island → B-C only unless grounded).
- n_P 0.02, m_Q 0.05, τ_S 1/(2π·5 Hz), I_sat 1.2, K = 5: reasonable and registered with sensitivities; fine.
- The plan's "§2.2.2.4" for GFM negative-sequence injection is §2.3.1 in the PDF.

## 6. Not checked

Any code (none exists); the PSCAD GFM block itself; whether PSCAD's averaged voltage source with a mode switch
initialises cleanly in an island (B1 will say).
