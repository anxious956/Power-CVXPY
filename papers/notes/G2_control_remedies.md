# G2 — Control-based remedies: the inverter reshapes its own fault current

These five papers are the closest "control-side" competitors to the Taylor-style designed-delta idea. Instead of changing relays, the IBR controller sets the angle, and sometimes the magnitude, of its positive-, negative- or zero-sequence fault current so that unmodified relay elements decide correctly. The elements covered are 32Q/32P-type directional elements, current-angle and incremental phase selectors, and quadrilateral/mho distance. Four papers propose controllers: Yang et al. 2023 (directional), Azzouz & Hooshyar 2019 and Medhat & Azzouz 2022 (phase selection), and Banaiemoqadam et al. 2020 (distance). The fifth, Davi et al. 2023, measures what the IEEE 2800-2022 negative-sequence requirement already delivers.

**Method.** All pages of all five PDFs were extracted with pypdf. Every IEEE table is an image, and several plots, heat-maps and equations do not extract, so those pages were rendered with PyMuPDF and read visually. Page numbers are journal page numbers; Yang's repository PDF has two cover pages, so journal p. 642 = PDF p. 3. Davi et al. are cited by PDF page (1–8).

**Reference numbers for our feeder, used throughout:**
- Base values: Z_base = 20²/15 = 26.7 Ω and I_rated ≈ 433 A at 20 kV.
- Fault resistance: R_f = 5–50 Ω is about 0.19–1.9 pu on the inverter base.
- Affordable delta: with 0.8 pu pre-fault current and a 1.2 pu limit, the delta guaranteed in every direction is 1.2 − 0.8 = 0.4 pu.

---

## Paper 1 — Yang et al. 2023: control method for directional elements (32Q and superimposed-positive-sequence 32)

**Citation.** Z. Yang, Z. Liu, Q. Zhang, Z. Chen, J. de J. Chavez, M. Popov, "A Control Method for Converter-Interfaced Sources to Improve Operation of Directional Protection Elements," *IEEE Trans. Power Delivery*, vol. 38, no. 1, pp. 642–654, Feb. 2023, doi:10.1109/TPWRD.2022.3202988. (TU Delft green-OA copy.)

**Setting**
- **Network (p. 643, Fig. 1; p. 647; Table II p. 652).** A single 100 MW CIRES plant, modelled as one aggregated grid-side two-level inverter.
  - Collector side: LCL filter (220 µF, 1250/1250 µH), Dyn 0.38/35 kV step-up, 35 kV collection line.
  - Main transformer: YNd 220/35 kV, which grounds the 220 kV side.
  - Line and grid: 40 km, 220 kV, 50 Hz; grid impedance 0.1 + j3.14 Ω, so the plant is 1/30 of the grid short-circuit capacity at the relay.
- **Relays and faults.** Relays sit at both ends of the line: R12 on the plant side and R21 on the grid side.
  - F1 is behind R12, between the plant and R12.
  - F2, F3 and F4 are at 0 %, 50 % and 100 % of the line.
  - F5 is beyond R21.
- **Inverter control.** Grid-following (GFL), 3-wire. The PLL is oriented on positive-sequence d. Sequences are separated by quarter-cycle delayed-signal cancellation in αβ. Positive and negative sequence each have a dq PI loop with grid-voltage feedforward and decoupling. There is a DC chopper, and the source is modelled as a controllable current source.
- **Current limit.** γ = 1.5 pu (the paper quotes 1.2–1.5 pu as typical). It is enforced in the reference calculation, not by a clipping block (p. 647).
- **Tools.** PSCAD. RTDS (RSCAD/GPC; protection logic is evaluated offline in MATLAB, not in a real relay). A downscale hardware test: 2.5 kVA, 190 V inverter on dSPACE DS1006, 10 kHz switching, 1 kHz sampling, with the "fault" made by a California Instruments MX-35 programmable voltage-sag source (pp. 651–652). There is no relay HIL.

**What the controller does**
- **Relay quantities (p. 644).** The positive-sequence element uses the superimposed apparent impedance Z1 = ΔU1/ΔI1 (post-fault minus pre-fault at the relay point). The negative-sequence element uses Z2 = U2/I2. Forward means −180° < ∠Z < 0°, and sensitivity is best at −90° (eq. 3–5).
- **Positive sequence (eq. 9–17, pp. 645–646).**
  - Given the relay-point fault voltage U1, pre-fault Ub, pre-fault Ib and the planned magnitude |I1|, it solves in closed form for the current angle α1 that makes ∠Z1 exactly −90° (an arcsin/arctan expression, eq. 13–15).
  - It then converts α1 into a d/q ratio relative to the PLL angle (eq. 16) and splits the magnitude into i1d, i1q (eq. 17).
  - This overrides the usual reactive-current-versus-voltage-sag rule.
- **Negative sequence (eq. 18–22, p. 646).** It sets I2 to lead the measured U2 by exactly 90° (α2 = φ2 + 90°), so the inverter looks like a lossless inductive negative-sequence impedance. This is converted to an i2q/i2d ratio.
- **Magnitudes (eq. 23–26, pp. 646–647).**
  - Start from |I1| + |I2| = γ·I_N with |I2| = β|I1|, where β is 0.2–1 (0.3 used). β < 1 keeps the phase rotation ABC, and β ≥ 0.2 gives enough I2 to activate 32Q.
  - Then iterate: compute the three phase-current magnitudes from |I1|, |I2| and their angle difference (law of cosines, eq. 24–25). Scale |I1| up or down until the largest phase current equals γ·I_N (eq. 26).
  - It converges in 2–3 iterations, and only the final reference is sent to the current loop.
- **When it acts.** After fault detection (an S-transform detector is cited). It does **not** classify the fault type; the claimed advantage is that no parameter depends on fault type.
- **Relay logic (Fig. 6, p. 647).** Fault detected → check U2 ≥ 2 % of nominal and I2 ≥ 10 % of nominal → angle test.
- **Grid code.** The Danish FRT curve (Fig. 3, p. 645) is the baseline. The proposed method no longer sets i1q from the voltage sag. The authors argue ride-through is still met in their case: PCC voltage 70.5 %, P = 0.70 pu, Q = 0.62 pu, i1d = 1.0024, i1q = −0.68 (p. 648). They list the voltage-support effect as open (p. 652).

**Key quantitative results**
- **Baseline (p. 645, Fig. 4).** With the Danish FRT strategy and I2 = 0, a metallic AG fault at F2 gives ∠Z1 = −139.52° (low sensitivity). ∠Z2 swings through all angles, which is effectively random direction, or blocked by I2 supervision.
- **Proposed method (p. 648, Figs. 7–8).** Same fault, γ = 1.5, β = 0.3: ∠Z1 = −90.61° and ∠Z2 ≈ −90.3° at 100 ms. The phase-A current reaches 1.5 pu.
  - The angle fluctuates heavily for the first ~20 ms, sometimes into the reverse zone, and controller and phasor settling add up. The authors suggest a **40 ms** added delay.
- **Table I (p. 649), R_f = 0, BG/AB/BCG/ABCG.**
  - Forward F2–F4 at R12: ∠Z1 from −90.65° to −91.06°; ∠Z2 from −88.61° to −90.08°.
  - Reverse F1 at R12: about +79.2° to +79.5°. This is trivial, because the plant current does not pass R12 for F1.
  - Reverse F5 at R21: +88.55° to +89.97°. This is the non-trivial reverse case, because R21 carries the plant's current.
- **Fault resistance (AG at F3, Fig. 9, p. 649).** ∠Z1 = −91.33° at 50 Ω and −91.38° at 100 Ω; ∠Z2 is essentially unchanged. 100 Ω at 220 kV / 100 MVA is only about 0.2 pu on the plant base.
- **Weak grid (Fig. 10, p. 649).** Plant at 1/10 and 1/3 of grid short-circuit capacity, AB fault: direction is still correct, with some angle change at 1/3.
- **Plant size (Fig. 11, p. 650).** 200 and 300 MW, BC at F4: still about −90°.
- **Comparison with Banaiemoqadam 2021 DCC (Fig. 12, p. 650).** BC, 20 Ω at F3, pre-fault PF 0.9/0.95/1. The 2021 method misjudges direction at PF 0.9 and 0.95; Yang's method stays near −90°.
- **RTDS (p. 650, Fig. 14).** AG 100 Ω at F4: ∠Z1 = −90.65°. BC 20 Ω: −91.36°. ∠Z2 is about −90° for both, and phase currents stay under the limit.
- **Hardware (p. 652, Fig. 16).** 0.5 pu sag on phases A and B from the MX-35: steady state within 40 ms, with ∠Z1 and ∠Z2 near −90° (∠Z2 sits in the reverse zone for about the first 20 ms).

**Assumptions and limitations**
- **Stated (p. 652):**
  - No stability proof.
  - Needs decoupled sequence components.
  - Not valid near large clusters of Type-III wind.
  - i1q is no longer set by voltage sag, so the voltage-support impact needs study.
- **Stated (p. 648):** Some GFL inverters do not deliver stable fundamental current in bolted three-phase faults. The method then fails; for 3ph faults the PLL frequency is frozen.
- **Unstated or not tested:**
  - **Relay current = plant current.** One radial plant with the relay at its HV bus; the controller computes references from relay-point U, pre-fault Ub and Ib. No loads, other feeders or other IBRs share the relay current.
  - **Scope of tests.** Only one plant. No measurement error, CT/VT model or noise. No commercial relay.
  - **Fault resistance.** R_f is tested only up to about 0.2 pu on the plant base, and only for AG at F3 plus two RTDS cases. Table I is bolted.
  - **Reverse faults.** Tested only at F1 (trivial) and F5 at R21.
  - **Hardware source.** The hardware test uses a stiff programmable source, so the inverter's I2 cannot change V2. It therefore cannot reveal the interaction described below.
  - **Supervision thresholds.** U2 ≥ 2 % and I2 ≥ 10 % are assumed passable.

**Our analysis (not in the paper): the fixed-magnitude, voltage-referenced trap**

Yang's negative-sequence rule, and the negative-sequence part of Medhat (Paper 3), has two features: a **fixed magnitude** and an **angle locked to the local V2**.
- **Model.** Take the network seen from the inverter bus as a fault-driven negative-sequence Thevenin source V2f behind Z_th ≈ jX.
- **Derivation.** Injecting I2 of magnitude I_s leading V2 by 90° gives V2 = V2f + jX·(j·I_s·V2/|V2|) = V2f − X·I_s·V2/|V2|. The only solution is V2 in phase with V2f, with |V2| = |V2f| − X·I_s.
- **Consequence.** A steady state consistent with the rule exists only if I_s ≤ |V2f|/X. Roughly, the injected I2 must not exceed the negative-sequence current the fault itself drives through that bus, and less for remote faults.
- **Above that limit:**
  - The inverter cannot behave as a passive inductor. It becomes an active negative-sequence source, and its angle reference chases a V2 that it largely creates itself.
  - A relay with that inverter behind it then measures roughly +Z_ahead. That is a reverse-looking value, whatever the fault direction.
- **IEEE 2800 contrast.** The IEEE 2800 law I2 = K·V2 at 90–100° lead (Paper 5) is a true admittance and never violates this condition, but it vanishes as V2 → 0.
- **Rough feeder numbers.** Assumptions: solid grounding and Z1+Z2+Z0 ≈ 10  Ω, **both to be checked in our model**. An SLG fault then drives I2 ≈ 0.35, 0.13 and 0.055 pu (of 433 A) at R_f = 5, 20 and 50 Ω. Yang's β = 0.3 (|I2| ≈ 0.28–0.35 pu at a 1.2 pu cap) and our 0.4 pu delta would sit above the threshold for most of our SLG R_f range. LL faults drive more I2 and are less exposed.
- **Status.** This is a hypothesis to test in EMT, not a result.

**Relevance to us**
- **Difference from a Taylor-style delta.**
  - Yang's is a **deterministic pointwise feedback law**: at every instant it computes the reference that makes the *nominal* relay angle exactly −90° from *measured* quantities.
  - There is no uncertainty set, no margin and no certificate. Measurement or PLL error passes straight into the angle, and R_f/location uncertainty is handled only by sweeping cases.
  - Magnitude is "as large as the limit allows" with a fixed β split, not a budgeted optimum.
  - A Taylor-style delta would choose I2 (magnitude and angle, or an angle offset relative to V2) so that the relay's decision sign is correct with margin for all (location, R_f, loading, measurement error) in a set, under an explicit budget.
- **Would it fix finding (2) on our feeder? Partly, and probably not at high R_f.**
  - **Forward faults.** For a relay at an inverter bus whose current is dominated by that inverter, the negative-sequence rule should correct forward declarations at low R_f. That is the regime Yang validated.
  - **Reverse faults.** The downstream inverter (and loads) must look passive-inductive in negative sequence. That needs the rule applied at **both** inverters, which is untested (single plant only).
  - **High R_f.** The fixed-magnitude rule probably enters the "active source" regime above, and the relay's U2 ≥ 2 % pickup may not be met.
  - **Positive-sequence (32P) part.** It needs relay-point pre-fault quantities. At a feeder bus with loads, the inverter's own terminal quantities are not the relay's, which breaks the construction.
  - **Current limiter.** Our 1.2 pu phase-current clipper may itself inject uncontrolled I2. Yang avoids this by limiting at the reference level (eq. 24–26). This is worth checking as a cause of finding (2).
- **What to reuse as a baseline:**
  - **B2 "SG-emulation, fixed |I2|".** I2 angle = ∠V2 + 90°, |I2| = β/(1+β)·I_max with β = 0.3, plus the eq. 24–26 sequence-aware limiter.
  - **Relay logic.** Fig. 6: U2 ≥ 2 %, I2 ≥ 10 %, angle window.
  - **Optional.** The eq. 13–17 ΔZ1 law for our 32P element.
- **Novelty implications.** Yang already claims a control-based fix for 32Q/32P that needs no fault-type detection and covers high R_f and weak grids. We cannot claim "inverter injection makes 32Q work". Our claim must rest on:
  1. guarantees over explicit uncertainty sets under a hard budget;
  2. the distribution / two-IBR / R_f ≈ 0.2–1.9 pu regime, where Yang is untested and plausibly fails;
  3. joint direction and phase selection.
- **Extraction notes.**
  - Equations 10–15 and 24 extract with broken fraction and square-root layout. They were reconstructed from the rendered pages; for example, eq. 13 is α1 = arcsin(F/√(1+tan²E)) + E.
  - Tables I–III and all angle plots are images, read from renders.

---

## Paper 2 — Azzouz & Hooshyar 2019: dual current control for precise phase selection

**Citation.** M. A. Azzouz, A. Hooshyar, "Dual Current Control of Inverter-Interfaced Renewable Energy Sources for Precise Phase Selection," *IEEE Trans. Smart Grid*, vol. 10, no. 5, pp. 5092–5102, Sep. 2019, doi:10.1109/TSG.2018.2875422.

**Setting**
- **Problem-statement system (Fig. 2, p. 5093).** 34.5 kV, 60 Hz. A 9.2 MW wind IIRES at unity PF, connected via a 14 MVA 4.16/34.5 kV dYG transformer, feeding two 8 km lines to a Thevenin grid of 4∠80° Ω.
  - Analytic sweeps use Rg and Rflt in [0.01, 100] Ω (pp. 5094–5095). Time-domain validation is in MATLAB/Simulink.
- **Evaluation system (pp. 5098–5099).** PSCAD/EMTDC, IEEE 14-bus at 138 kV.
  - IIRES: two 20 MW PV (buses 12 and 14) and one 40 MW type-IV wind (bus 13, 5 × 8 MW), each via 22/138 kV dYG, X = 0.1 pu.
  - Plus 2 SGs and 3 synchronous condensers, so the grid is strong.
  - Relays R(13,6), R(14,9) and R(12,6) sit at IIRES buses. R(13,6) also carries flows from buses 12 and 14, so more than one IIRES contributes.
- **Inverter.** GFL, 3-wire, LC filter. Dual (dq±) synchronous-reference-frame current control with PLL and 120 Hz notch filtering (Fig. 8, p. 5097). The positive-sequence loop keeps grid-code reactive current (RCG) and DC-link regulation.
- **Current limit.** I_max around 1.5 pu, handled as I_max ≤ I⁺_limit + I⁻_limit (eq. 28, p. 5098; the numerical split is not reported). Output |I⁻| is held at I⁻_limit (eq. 29).
- **Implementation.** C code for a TI TMS320F28335 DSP runs in about 60 µs (100 µs sampling, 10 kHz switching; p. 5099). This is timing only, not HIL.

**What the controller does (three stages, pp. 5096–5098)**
- **Relay elements it targets.** Current-angle phase selectors using the relative angles of superimposed sequence currents at the relay: δ⁺ = ∠ΔI⁻ − ∠ΔI⁺ (PSM1, GE-D90-style) and δ⁰ = ∠ΔI⁻ − ∠ΔI⁰ (PSM2, SEL-style, with estimated R_lg/R_llg to separate SLG from LLG) (eq. 1, Fig. 1, pp. 5092–5093). Zone half-widths are ±15° for δ⁺ and ±30° for δ⁰.
- **Stage I — classify first, at the inverter.** Uses the Hooshyar et al. 2016 voltage-based classifier on the transformer grid-side voltage.
  - The lead of V⁻ over V⁰ (Δθ₀) selects a zone pair, one SLG and one LLG.
  - The pair is split using phase-voltage magnitude changes (eq. 16).
  - Output: fault type (LG, LL or LLG) → δ⁺_ref or δ⁰_ref at the zone centre.
- **Stage II — reference angle (eq. 17).** Depending on the relay type:
  - PSM1: ∠I⁻_ref = δ⁺_ref + ∠I⁺_o + θ⁺_tr.
  - PSM2: ∠I⁻_ref = δ⁰_ref + ∠I⁰_og + θ⁰_tr.
  - The θ_tr terms compensate the dYG phase shift (60° and 30°).
  - ∠I⁺_o is computed from the inverter's own dq current (eq. 18–20).
  - ∠I⁰_og is **estimated**, not measured, from the grid-side zero-sequence voltage through the transformer zero-sequence impedance, followed by a notch filter (eq. 21–25).
- **Stage III.** Build the dq⁻ references from the angle and |I⁻| = I⁻_limit (eq. 26–29), add filter-capacitor compensation (eq. 30), and run decoupled dq⁻ PI loops (eq. 31).
- **Why I⁻ and not I⁺.** Setting ∠I⁺ could track δ⁺_ref too, but would conflict with grid-code RCG. So I⁺ follows the grid code (Spanish, German or North-American) and only I⁻ is shaped.
- **Key analytic result (Section III, Figs. 5–6, eq. 7, pp. 5094–5095).** With an impedance-emulating negative-sequence loop but grid-code-driven I⁺, δ⁺ depends on the power-factor angle.
  - Spanish GC: only partially compatible.
  - German k-slope GC: cannot keep AG faults in zone for any slope.
  - North-American unity-PF operation: misses SLG entirely.

**Key quantitative results**
- **Motivation (p. 5093, Fig. 3).** Conventional control, bolted BCG: δ⁺ = −126.8° (reads CG) and δ⁰ = 149.4° (CG/ABG), so healthy phases would be tripped.
- **Table I (p. 5099), bolted faults at the midpoint of line 6-13, R(13,6), all three GCs.**
  - δ⁺ for AG is 2.2–5.6°.
  - The largest deviation from zone centre is about 10°: ABG δ⁺ 69.8°, BCG 189.7°, CAG −50.5° (NA-GC).
  - δ⁰ lies within about 7° of centre.
  - R_lg < R_llg for SLG, and the reverse for LLG.
- **Table II (p. 5099), line 9-14, R(14,9).** Similar, all correct.
- **Table III (p. 5100), bolted LL.** δ⁺ = 61.3–66.4° for AB, 181.4–186.6° for BC, −54.2 to −58.7° for CA. For LL faults PSM2 falls back on line-to-line current magnitudes (Fig. 12).
- **Comparison with their 2018 DCC under NA-GC (Fig. 13, p. 5101).** The 2018 DCC puts AG δ⁺ near −90°; the new DCC puts it near 0°.
- **Fault resistance (Fig. 14, p. 5101).** At the midpoint of line 12-6 under the German GC, sweeping Rg over [0, 50] Ω (Rflt = 10 Ω) and Rflt over [0, 50] Ω (Rg = 10 Ω) keeps all δ inside zones. At 138 kV, 50 Ω is only about 0.05–0.1 pu on a 20–40 MVA IIRES base.
- **Speed.** Angles settle within about 1–2 cycles in the plots (Fig. 11).
- There is no success-rate statistic; all results are case studies.

**Assumptions and limitations**
- **Stated or implied:**
  - The controller needs the fault type from the inverter-side classifier.
  - DCC gains are tuned by simulation, and there is no stability proof.
  - The zero-sequence current is estimated from a transformer model.
- **Unstated (our reading):**
  1. **Classifier errors propagate.** If Stage I misclassifies, which is plausible at high R_f where V⁻ and V⁰ are small, the inverter actively steers the relay into the **wrong** zone. That is worse than no control, and classifier accuracy is not evaluated here.
  2. **Total versus superimposed I⁺.** Stage II references the inverter's **total** ∠I⁺_o, while the relay uses the **superimposed** ∠ΔI⁺. Example: 0.8 pu active current before the fault and 1.0 pu reactive-priority current after it. Then ∠ΔI⁺ ≈ −129° while ∠I⁺ = −90°. The 39° gap is far outside the ±15° δ⁺ zones.
  3. **Test conditions.** Only bolted faults in the tables; resistance sweeps at one location; a strong SG/SC system. No measurement error, and no study of loads between inverter and relay.
  4. **Effect on 32Q.** I⁻ is referenced to a current (∠I⁺), not to V⁻, so the inverter is an active negative-sequence source. It is not guaranteed to look inductive to 32Q, and its effect on directional elements is not examined.

**Relevance to us**
- **Difference from a Taylor-style delta.** Design is "place the relay's angle at the zone centre for the classified fault type", pointwise, with no margin optimisation or uncertainty sets. Magnitude is fixed at the negative-sequence limit.
  - Conceptually, the inverter classifies locally and then *signals* the classification to the relay through its current angle. A Taylor-style method could either (a) likewise condition delta on an inverter-side classification but guarantee the zone decision over R_f, location and measurement sets, or (b) seek a classification-free delta.
- **Would it fix finding (2)?** No. It targets phase selection, not direction. Its current-referenced I⁻ could even worsen 32Q at our inverter buses. For the new "phase/fault-type selection" part, it is **the** direct competitor. On our feeder, points 1–2 above (high-R_f classification and the 0.8 pu pre-fault current making ΔI⁺ ≠ I⁺) are likely failure modes to test.
- **What to reuse:**
  - **B4 baseline:** Stage I classifier + eq. 17 (PSM1 mode) + |I⁻| at a fixed limit.
  - **Relay model:** the PSM zone definitions (Fig. 1; ±15° / ±30°), and the ∠I⁰ estimator idea if our inverter transformer grounds the 20 kV side.
- **Novelty implications.** "Inverter shapes I⁻ so commercial phase selectors pick the right phase" is established since 2018–2019. Our novelty for phase selection must be robustness over sets, high-R_f/multi-IBR validity, and ideally one delta serving direction and phase selection at once.
- **Extraction notes.**
  - Eq. 7 (δ⁺ for AG/BCG/BC) is badly garbled in text but readable in the render (p. 5095).
  - Tables I–III and Figs. 5–7, 11 and 13–14 are images, read from renders.

---

## Paper 3 — Medhat & Azzouz 2022: triple current control of four-wire inverters for fault-type identification

**Citation.** W. Medhat, M. A. Azzouz, "Triple Current Control of Four-Wire Inverter-Interfaced DGs for Correct Fault Type Identification," *IEEE Trans. Smart Grid*, vol. 13, no. 5, pp. 3607–3618, Sep. 2022, doi:10.1109/TSG.2022.3170241.

**Setting**
- **Preliminary system (Fig. 2, p. 3608).** 34.5 kV, 60 Hz, grid Thevenin 4∠80° Ω, two 8 km lines. A 9.2 MW four-wire IIDG via a 4.16/34.5 kV **YgYg** transformer (X = 0.1 pu).
- **Main system (Fig. 10, p. 3614).** CIGRE **LV** benchmark: 400 V from a 20 kV/400 V Dyn transformer, simulated in MATLAB/Simulink with an average inverter model at 50 µs.
  - Two 100 kVA PV at nodes 4 and 9; a third PV at node 13 for the multi-IIDG test.
  - The fuse is replaced by CB12, and CB45 is added. Relays R12 and R45 are modelled; the evaluation focuses on R45, at the PV1 bus looking downstream.
- **Inverter.** GFL, **four-wire transformer-less split-capacitor** (neutral current 3I⁰ flows through the DC mid-point).
  - A DDSRF-PLL extracts +/− sequences, and a SOGI-PLL handles zero-sequence synchronisation.
  - dq PI loops handle + and −; a PR controller handles 0, with capacitor-imbalance voltage compensation (eq. 2–5, Fig. 5, p. 3610).
- **Current limit.** I_max = 1.5 pu. The positive-sequence reactive current is prioritised (|I⁺_q| ≤ I⁺_lim, I⁺_d gets the remainder; p. 3614).
- No HIL and no hardware.

**What the controller does**
- **Negative sequence (eq. 6–16, pp. 3610–3611).** Makes the IIDG look like an SG negative-sequence impedance: I⁻ = −V⁻/Z⁻, so θ⁻_ref = ∠V⁻ − ∠Z⁻ − 180°.
  - ∠Z⁻ is set to the **grid** negative-sequence X/R angle (offline data or online estimation). With ∠Z⁻ ≈ 80°, I⁻ leads V⁻ by about 100°.
  - Only the angle emulates an impedance; the magnitude is fixed at I⁻_lim (eq. 16).
- **Zero sequence (eq. 17–20, p. 3611).** θ⁰_ref = ∠V⁰ − ∠Z⁰ − 180° with ∠Z⁰ the grid zero-sequence X/R angle. |I⁰| is held at I⁰_lim = 0.1 pu, the minimum a relay accepts, which also curbs neutral current.
- **Positive sequence.** Standard grid-code control (NA-GC ≈ 0 reactive; German GC proportional to the dip). δ⁺ is **not** controlled.
- **No fault-type classification at the inverter.** The emulation is type-agnostic. The relay's disturbance detector triggers the phase selector within about 5 ms, and the angles settle within one cycle (p. 3612).
- **Current limits (Section IV, pp. 3612–3614).**
  - Phase-current magnitude is derived as a function of the three sequence magnitudes and angles (eq. 21–29; a current "ellipsoid" in αβz).
  - An offline problem, solved by GA and confirmed by brute force, picks I⁺_lim and I⁻_lim. It uses worst-case AG and BCG, with faulted phases at I_max and healthy phases at 1.0 pu, I⁻_lim between 0.1 and 0.5 pu, and I⁰_lim = 0.1 pu (eq. 30–34).
  - Result: AG gives I⁺_lim = 1.16 and I⁻_lim = 0.24 pu; BCG gives 1.30 and 0.23 pu (p. 3613).
  - Oddity: the objective is stated as a *minimisation* of (I⁺_lim)² + (I⁻_lim)² even though the text speaks of maximising injection. The equality constraints make it essentially a feasibility problem.

**Key quantitative results**
- **Motivation (Figs. 3–4, p. 3609).** A constant-active-power TCC misplaces δ⁺ and δ⁰ for bolted BCG. Their earlier 3-wire DCC gets the angles right, but the neutral current reaches about 5 pu.
- **Preliminary MV system (Fig. 8, p. 3612).** Bolted BCG is correct under NA and German GC. Neutral current falls from about 5.0 pu to 0.3 pu. NA-GC needs δ⁺ zones expanded backward by 90°.
- **CIGRE LV system (Fig. 11, p. 3614).** For bolted BCG, I⁺ ≈ 1.30 pu, I⁻ ≈ 0.22 pu, I⁰ ≈ 0.1 pu, and phase currents stay below 1.5 pu.
- **Maximum fault resistance.** 0.73 pu, derived from a 0.88 pu faulted-phase voltage and 1.2 pu minimum IIDG current (p. 3614). That is about 1.2 Ω on the 100 kVA/400 V base, or ≈ 19 Ω if scaled to our 15 MVA/20 kV base.
- **Tables I–II (p. 3615), faults at cable 12-13, R_f = 0 and 0.73 pu.**
  - δ⁰ is always in zone, near ideal (e.g. ABG 109–112°).
  - δ⁺ under the German GC is far off. AG reads 38–60° (zone ±15° about 0°), ABG 110–118°, and German BC −121° / −110° (ideal 180°).
  - Correct classification therefore needs δ⁰ plus a **relay-side expansion of the δ⁺ zones by 90°**: forward for resistive grids (the paper's proposal) or backward for inductive grids (their earlier recommendation).
- **Tables III–IV (p. 3615), three IIDGs, faults at the near/far ends of cable 6-7.** All angles near ideal, e.g. AG δ⁺ between −0.4° and −3.1°.
- **Tables V–VI (p. 3616), PV1/PV2 at 125/75 kVA, faults at node 2.** Under the German GC, δ⁺ deviates up to about 75° (BC 255.6°, BCG 228.9°, CA +13.7°); δ⁰ is fine.
- **Tables VII–IX (pp. 3616–3617).** Feeder impedance ±50 % and filter impedance +20 %: still correct.
- **Stability.** Checked by more than 300 time-domain runs (p. 3617).

**Assumptions and limitations**
- **Stated:**
  - Needs the grid X/R angles.
  - δ⁺ is not controlled, and correct selection relies on expanded δ⁺ zones.
  - Stability is shown by simulation only.
  - Balanced faults are excluded.
- **Unstated or not tested:**
  - **Relay settings.** The expanded δ⁺ zones are a relay setting change. That contradicts the "commercial relays unmodified" framing for SLG/LLG discrimination.
  - **Impedance test.** The ±50 % test probably scales R and X together, leaving the X/R angle, the actual design parameter, unchanged. The paper does not say.
  - **Fixed magnitudes.** |I⁻| and |I⁰| are fixed while angles are voltage-referenced, which is the same existence issue as Paper 1. The maximum R_f is only 0.73 pu.
  - **Scope.** No measurement error. LV only, without an MV/HV transformer between inverter and relay.
- **Our reading of the topology (moderate confidence).** Faults at cable 12-13, node 2 and node 3 are upstream of R45, so R45 then measures PV2's contribution flowing upstream. This is an "IIDG-fed reverse fault" case, and it is where the German-GC δ⁺ errors are largest. Forward faults (cable 6-7, node 8) are grid-dominated and near-ideal.

**Relevance to us**
- **Difference from a Taylor-style delta.**
  - The negative-sequence part is the same idea as Yang and IEEE 2800 (I⁻ leading V⁻ by about 90–100°), with the angle tied to an assumed grid X/R.
  - The robustness claims come from zone-width tolerance ("the PSM is zone-based with margin"), not from design over a set.
  - The one optimisation (GA for current limits) is offline and solved worst-case by fault type. It concerns the budget split, not the relay decision.
- **Would it fix finding (2)?** Only via its negative-sequence part, which for a 3-wire inverter behind a transformer reduces to Paper 1 / IEEE 2800 behaviour. It is not tested for direction. The zero-sequence controller applies only if our inverters are four-wire or grounded-wye on the 20 kV side.
- **What to reuse:**
  - **Current-limit mapping.** The sequence-to-phase magnitude formula (eq. 29) is exactly the current-limit map our designed delta needs.
  - **Convexity (our observation).** Written in complex rectangular coordinates, the limit is convex: for fixed I⁺ and I⁰, each |I⁰ + aᵏI⁺ + a⁻ᵏδ| ≤ I_max is a disc, so the feasible delta set is an intersection of three discs. The paper's GA over magnitudes and angles is therefore unnecessary. For our 0.8 pu / 1.2 pu case, the largest centred disc has radius 0.4 pu, which matches our "affordable delta".
  - **Magnitude benchmark.** Their I⁻_lim ≈ 0.23–0.24 pu is a useful comparison point for our 0.4 pu.
- **Novelty implications.** It adds to the prior art for "inverter shapes I⁻ (and I⁰) so existing phase selectors work", and shows multi-IIDG feeder tests exist (LV, bolted and 0.73 pu R_f). Our distinction has to be the guarantee, the MV high-R_f regime and joint direction plus selection.
- **Extraction notes.**
  - Eq. 29 (phase currents from sequence currents) and eq. 14 extract garbled but are readable in the renders.
  - All nine tables and Figs. 3–4, 8, 10–12 are images, read from renders.

---

## Paper 4 — Banaiemoqadam, Hooshyar & Azzouz 2020: control-based distance protection during asymmetrical faults

**Citation.** A. Banaiemoqadam, A. Hooshyar, M. A. Azzouz, "A Control-Based Solution for Distance Protection of Lines Connected to Converter-Interfaced Sources During Asymmetrical Faults," *IEEE Trans. Power Delivery*, vol. 35, no. 3, pp. 1455–1466, Jun. 2020, doi:10.1109/TPWRD.2019.2946757.

**Setting**
- **Network (Fig. 1, p. 1456).** IEEE 9-bus at 230 kV, 60 Hz. The SG at bus 9 is replaced by a 100 MVA, 13.5 kV CIRES behind a 13.5/230 kV, 150 MVA transformer T3 (Y side grounded on HV). Line L89 is 100 km.
- **Relay model.**
  - R98 is at the CIRES substation, modelled on an ABB REL670 quadrilateral characteristic. Zone 1 covers 90 % of L89 (48 Ω), zone 2 covers 120 % (64 Ω), and the default resistive reach is 100 Ω.
  - A voltage-polarised mho element (memory V⁺) is also tested.
- **Inverter.** GFL SRF current control with grid-voltage feedforward (Fig. 8, p. 1458). As a result, the converter is open-circuit in negative and zero sequence. The CIRES is at rated power, unity PF, before the fault.
- **Current limit.** 1.2 pu. FRT uses a chopper, with a PV + DC/DC variant (pp. 1464–1465).
- **Tools.** PSCAD/EMTDC only.

**What the controller does**
- **Root cause (pp. 1456–1458).**
  - Apparent impedance is Z⁺_f + R_f(1 + M_r) (eq. 1–2), where M_r is the ratio of remote to local loop currents. With SGs, M_r is nearly real.
  - With a current-controlled CIRES, M_r gets a large angle. Example: BCG, 20 Ω at 40 %: under RCG the numerator leads by 57° and R98 sees above zone 1; under unity-PF ACG it lags by 76° and R98 measures −62.2 Ω.
  - Intermediate infeed is similar: ACG gives an overreach to 45.1 Ω reactance for an external fault, a false zone-1 trip (Fig. 7).
- **Control variable.** Only the **positive-sequence** current angle (iq/id ratio, eq. 5) and magnitude (set to the 1.2 pu maximum). The goal is to make ∠M_r ≈ 0.
- **Activation (Fig. 16, p. 1461).** Enters FRT mode when V < 0.9 pu. It **classifies the fault type** with the voltage-based classifier (δ⁰ = lead of V⁻ over V⁰, Fig. 12, plus phase-voltage magnitudes) within 2–3 ms.
- **Strategy 1 — replicate SG angles (pp. 1459–1460).**
  - Compute what ∠I⁻ *would* be if an SG replaced the CIRES, using V⁻ at the PCC and an assumed SG+transformer ∠Z⁻_eq ≈ 84° (eq. 6).
  - Then pick ∠I⁺ from the SG sequence-angle pattern for the classified fault type (Fig. 9).
  - Result: ∠M_r ≈ 7.9° (versus −11.7° for a real SG), but the weak magnitude still needs weak-infeed / echo logic.
- **Strategy 2 — worst-case tuning (p. 1460).** Replace ∠Z⁻_eq by a constant α tuned **offline** so that ∠M_r = 0 for the worst case: a fault at the zone-1 reach with maximum R_f (100 Ω).
  - Iterate α ← α + ∠M_r for one LL, one LLG and one SLG case; at most 5 iterations.
  - Result: α = 73° (LL/LLG) and 63° (SLG) for this system.
- **Negative-sequence variant (p. 1464).** With a DCC, the same procedure also sets ∠I⁻.
- **Grid code.** The fixed reactive-current curve is overridden, but GC entry/exit FRT criteria are respected. The authors note GC reactive-current response times (30 ms German, 150 ms Spanish) exceed distance-relay trip times (p. 1457).

**Key quantitative results**
- **Zone-1 internal faults (Table I, p. 1461).** AG, BCG and BC at 30 and 60 km with R_f = 10/50/90 Ω all trip instantaneously; ∠M_r ranges from −6.1° to +0.7°.
  - AG reactance error is at most 4.4 Ω (30 km, 90 Ω), and the impedance enters zone 1 within 9 ms (Fig. 17).
  - **BC/BCG under-measure X substantially:**
    - BC, 90 Ω, 30 km: X = −1.1 Ω versus X_act = 15.8 Ω;
    - BC, 50 Ω, 30 km: 5.0 versus 15.8 Ω;
    - BC, 90 Ω, 60 km: 19.9 versus 31.7 Ω.
- **At the reach, 100 Ω (Figs. 18–19, p. 1462).** AG and BCG measure right at the reach setting. This needs a 375 Ω resistive reach, well above the 100 Ω default (the maximum load R is 520 Ω).
- **Close-in BC, 30 Ω (Fig. 20).** ∠M_r = −7.7°, slightly in the fourth quadrant; it trips given the −15° default directional line.
- **Zone 2 (pp. 1462–1463).**
  - BCG 10 Ω at bus 8: proposed control measures 54.7 Ω versus 53 Ω actual. ACG is off by about 73 Ω (fourth quadrant) and RCG by about 10 Ω.
  - Intermediate infeed: ∠M_i drops to 5.2° from 22.5° (RCG) and −116° (ACG).
- **Small R_f (p. 1463).** Even 0.5 Ω causes misoperation under RCG (reach) or ACG (close-in); the proposed control fixes both.
- **Mho (pp. 1463–1464).** BCG 5 Ω at 50 %: comparator angle enters the trip zone in 3 ms and settles at 54.6°. External AG 20 Ω: 164.3°, no trip.
- **DCC variant (p. 1464).** AG 10 Ω at 30 %: ∠M_r = 3°, overreach 0.6 Ω.
- **Non-chopper FRT (p. 1465).** ∠M_r = 0.2°, DC overvoltage < 4 %.
- **Weak grid (sources ×5, p. 1465).** BC 5 Ω at 80 % is still in zone 1.

**Assumptions and limitations**
- **Stated or implied:**
  - The remote and intermediate infeeds must be **SG-dominated**, since the reference angle is "SG-like".
  - Needs fault-type classification.
  - α must be re-tuned per system and relay.
  - The directional-line angle must be set from close-in high-R_f cases.
- **Unstated or not tested:**
  - **Scope.** Single CIRES, relay current = CIRES current, no loads between. Transmission scale: 100 Ω is about 0.19 pu on the plant base. No measurement error.
  - **Overreach risk.** α is tuned at a single worst-case point per fault type, but Table I shows the largest reactance errors at intermediate locations (up to about 17 Ω on a 48 Ω reach). External high-R_f faults just beyond the reach, where such errors would cause overreach, are not shown.
  - **Printed equation.** Eq. 6 as printed (∠I⁻ = −∠V⁻_PCC + ∠Z⁻_eq) does not match the impedance relation I⁻ = −V⁻/Z⁻, whose angle would be ∠V⁻ − ∠Z⁻ + 180°. Treat it as a sign-convention issue and do not implement it verbatim.

**Relevance to us**
- **Difference from a Taylor-style delta.**
  - Strategy 2 is the **closest in spirit** to Taylor: an explicit offline worst-case design of one angle parameter against the maximum R_f at the reach.
  - But it is a single-scenario heuristic iteration, with no set, no guarantee and no budget trade-off (magnitude pinned at 1.2 pu).
  - Their own Table I shows the worst case is not where they tuned, which argues for set-based design.
- **Would it fix finding (2)?** Not targeted: it changes only I⁺, for distance.
- **Relevance to finding (1).** Their numbers support finding (1). The apparent-R term R_f(1+|M_r|) turns any residual angle into a reactance error.
  - On our feeder, take R_f = 20–50 Ω and |M_r| of order 1. A residual angle of only 2° gives about 1.4–3.5 Ω of reactance error.
  - That is comparable to the whole 2–4 Ω line. So one-ended zone-1 reach cannot be resolved by current-angle shaping in our regime, consistent with our finding (1).
- **What to reuse:**
  - **B5 baseline for zone 1:** positive-sequence angle law + offline α tuning.
  - **Illustration:** the M_r decomposition (eq. 1–4) explains *why* reach fails.
  - **Reporting template:** ∠M_r, X_measured versus X_actual.
- **Novelty implications.** Current-angle shaping for distance protection exists (2020, and a 2021 "comprehensive DCC" follow-up in TPWRD 36(5) that Yang compares against). Our reach result (1) is best framed as an **impossibility or limit**, not something we "fix".
- **Extraction notes.**
  - Table I and all impedance-plane figures are images, read from renders.
  - Eq. 1–4 underbraces extract as junk glyphs but are readable in the renders.

---

## Paper 5 — Davi, Oleskovicz & Lopes 2023: what IEEE 2800-2022 buys for line protection

**Citation.** M. J. B. B. Davi, M. Oleskovicz, F. V. Lopes, "Study on IEEE 2800-2022 Standard Benefits for Transmission Line Protection in the Presence of Inverter-Based Resources," *Int. Conf. Power Systems Transients (IPST 2023)*, Thessaloniki, Jun. 12–15, 2023 (8 pp.).

**Setting (pp. 1–3)**
- **Plant.** 147 × 1.5 MW full-converter PMSG wind turbines (220.5 MW, 0 var pre-fault), modelled on GE 1.5 MW dynamics with a chopper (on at 1.15 pu DC, off at 1.05 pu).
- **Transformers.** 0.575/34.5 kV Dyn11 per unit, 138/34.5 kV YNd1 (90 MVA), 500/138 kV YNyn0 (250 MVA).
- **Lines.** 100 km (1-2) and 147 km (2-3). They appear to be 500 kV from the Fig. 2 colour legend and the 490/480 kV sources; the text never states it.
- **Measurement.** Relays at P1 (IBR end of line 1-2) and P2 (grid end). CT ratio 60, VT ratio 4500, 3rd-order 180 Hz anti-aliasing filters.
- **Two control groups (Fig. 1, p. 2):**
  - **G1C** (coupled-sequence, legacy): I2 suppressed.
  - **G2C** (IEEE 2800-compliant, decoupled-sequence): extra positive-sequence reactive current per voltage deviation (VDE-AR-N 4120 cited). I2 is injected proportional to V2 and leads it by 90–100° (the figure shows I_neg = K·V_neg; K is not reported).
- **Scenario matrix.**
  - Fault types: all 10.
  - Resistances: R_ph = 0, 1, 1.5, 2.5 Ω and R_g = 0, 25, 50, 100 Ω.
  - Inception angles: 0° and 90°.
  - Locations: 0–100 % of line 1-2 in 10 % steps, plus 5 % and 50 % of line 2-3.
  - Total: 8320 PSCAD runs. Decisions use phasors at 100 ms after inception, since controls take about 50 ms.
- **Relay validation.** COMTRADE playback into a commercial relay (make not named).

**What the "controller" does.** There is no new controller: the paper evaluates the IEEE 2800 behaviour as implemented, with no fault-type classification. On current limiting it only states a typical 1.2 pu, and it does not describe how the I2 injection shares the limit.

**Relay element models (reusable)**
- **32Q (eq. 1, p. 3).** SEL-style scalar Z2 = Re[V2·(1∠θ_L1·I2)*]/|I2|².
  - Forward if Z2 < Z2F = 0.5|Z_L1|; reverse if Z2 > Z2R = Z2F + 0.2 Ω.
  - Supervision: 3|I2| > 0.25·I_nom.
- **32G (eq. 2).** Analogous, with supervision 3I0 > 0.5·I_nom.
- **Incremental-torque phase selector (eq. 3–5, Table II, p. 4).** ΔT_ab, ΔT_bc and ΔT_ca are normalised, with thresholds L_up = 0.7, L_int = 0.5 and L_low = 0.35.
- **Current-angle phase selector (Fig. 6, p. 5).** δ between I2 and I0 selects a sector; SLG versus LLG is resolved by the lowest mho reach or the lowest resistance estimate. It uses the same I2/I0 supervision.
- **Mho distance (Table III, p. 5).** Self-, memory- and cross-polarised elements, with a 75 % reach and a 50 ms intentional delay.

**Key quantitative results**
- **32Q at the IBR end P1, internal (forward) faults only (Fig. 3, p. 3).**
  - G1C: blocked in 100 % of cases.
  - G2C: 100 % correct for PP and PPG, and about 90 % for PG (the text says 90 %; the bar looks about 88 %).
  - PG errors occur only at high R_g, where V2 and hence I2 = K·V2 are too small.
  - At P2 (grid end), 100 % for both groups.
- **32G (Fig. 4, p. 4).** 100 % at both ends for both groups, because the zero sequence comes from the grounded YNyn0/YNd1 transformers, not the IBR.
- **Incremental phase selector at P1 (Fig. 5, p. 4).**
  - G1C: SLG 9.94 %, LL(G) 15.1 %, 3ph 75 %. About 65 % of SLG faults are read as PP/PPG.
  - G2C: SLG 68.56 %, LL(G) 95.31 %, 3ph 100 %. SLG errors are mostly AG read as AB/ABG (19.6 %) and CG read as CA/CAG (26.1 %).
- **Current-angle phase selector at P1 (Fig. 7, p. 5).**
  - G1C: fully blocked, because the I2 supervision fails.
  - G2C: SLG 88.44 %, LL(G) 81.34 %.
  - Notably, AB/ABG is read as **CG** in 36.9 % of cases and BC/BCG as **AG** in 13.6 %. These errors arise from the SLG-versus-LLG resistance/reach tie-break within a shared δ sector, not from the angle.
- **Distance at P1 (Fig. 9, p. 6).**
  - PG: about 57–59 % correct under both groups; controls have little effect because PG loops are dominated by grid zero-sequence current.
  - PP/PPG/PPP, self-polarised: G1C has undue trips averaging 17.3 %, and G2C nearly eliminates them.
  - PP/PPG/PPP, memory-polarised: G1C gives 25.7 / 70.5 / 76.9 %, G2C gives 93.0 / 94.6 / 92.3 %, an average of about 93.3 %. That is about +67 points for PP.
- **Commercial relay (Fig. 13, pp. 7–8).** Bolted AB at 50 %: under G1C the comparator enters the zone only after about 100 ms, so there is no trip; under G2C it enters after about 40 ms and trips after the 50 ms delay.

**Assumptions and limitations**
- **Stated:** One plant and one line pair, a transmission-level strong grid, decisions at 100 ms, and K and other G2C details only sketched.
- **Unstated or not tested:**
  - **No reverse faults for 32Q.** Section IV analyses only line 1-2 faults, which are forward for both P1 and P2. The 32Q success rates at the IBR end therefore contain **no reverse faults**, and security against reverse faults is unassessed.
  - **Low fault resistance on the plant base.** R_g ≤ 100 Ω is only about 0.09 pu on a 220.5 MVA / 500 kV base; R_ph ≤ 2.5 Ω is negligible.
  - **Scope.** No measurement-error study beyond realistic CT/VT ratios and filters, and no multi-IBR case.
  - **Text/figure inconsistency.** For G1C two-phase faults the text says about 73 % are read as three-phase, but the heat-map shows about 73 % "not classified" (Fig. 5a, p. 4).

**Relevance to us**
- **Difference from a Taylor-style delta.**
  - IEEE 2800 is a fixed, passive linear law: I2 = K·V2 with 90–100° lead, i.e. a true negative-sequence admittance.
  - It is direction-faithful by construction but proportional to V2, so it fades exactly in the high-R_f cases that matter to us. There is no budget optimisation and no guarantee.
  - A designed delta competes by keeping a guaranteed minimum decision margin when V2 is small, while respecting the current disc constraints.
- **Would it fix finding (2)?**
  - **Forward faults, low R_f at the inverter bus:** likely yes. That is their 100 % PP/PPG result.
  - **High R_f:** likely not. Their only failures are high-R_g PG, and our R_f is 2–20× larger relative to the inverter base, so expect many "blocked" or low-margin cases.
  - **Reverse faults:** unknown from this paper. A passive K·V2 law at the downstream inverter should give the right sign when I2 is large enough.
  - **Applicability.** IEEE 2800 is scoped to transmission-connected IBRs. For a 20 kV feeder, IEEE 1547-2018 (North America) does not require negative-sequence injection, while German MV code VDE-AR-N 4110 does include asymmetric reactive-current injection (from our background knowledge, not this paper; verify).
- **What to reuse:**
  - **B1 baseline (the "status quo" to beat):** I2 = K·V2 leading by 90–100°, K ∈ {2, …, 6} pu/pu swept.
  - **Relay models:** their exact 32Q/32G/phase-selector implementations and thresholds.
  - **Evaluation design:** the correct / missed-trip / undue-trip metric, and the scenario-grid design (types × R × inception × location).
  - **Threshold caution:** with our 2–4 Ω lines, Z2F ≈ 1–2 Ω, so the 32Q thresholds are tight.
- **Novelty implications.** Since IEEE 2800-2022 *mandates* SG-like negative-sequence behaviour, "IBR injects I2 so 32Q/phase selectors work" is now the regulatory baseline, not a contribution. Any novelty claim must show gains **over the IEEE 2800 law** in regimes where it fails (high R_f, reverse faults, multiple IBRs, budget-limited), with a guarantee.
- **Extraction notes.**
  - Bar-chart values and the Fig. 5/7 heat-maps extract as unordered number streams. They were read from renders.
  - The equations extract cleanly.

---

## Synthesis

All five papers follow one paradigm: make the IBR's sequence currents imitate a synchronous generator's, so that unmodified relay elements decide correctly. They differ in which sequence component is shaped and what it is referenced to:
- **Referenced to V2, so the inverter mimics a passive negative-sequence impedance (direction-oriented):** Yang 2023, the negative-sequence part of Medhat 2022, and IEEE 2800 as studied by Davi 2023.
- **Referenced to the inverter's own I⁺ or I⁰, making it an active source (phase-selection-oriented):** Azzouz 2019.
- **I⁺ referenced to a hypothetical SG I⁻ (distance-oriented):** Banaiemoqadam 2020.

Common ground and gaps:
- **Deterministic laws, validated by sweeps.** Every method is a deterministic feedback law tuned at nominal or worst-case points and validated by scenario sweeps. Two of the four controller papers also need an inverter-side fault-type classifier.
- **Narrow validated range.** Validation is on transmission systems (or one LV feeder) with strong SG backing, one or a few IBRs, and relay current ≈ IBR current. R_f is at most about 0.2 pu of the IBR base (0.73 pu only in the LV case). There are no measurement-error sets and no correctness certificate.
- **Heuristic current limits:** sum-of-magnitudes, iterative maximisation, or offline GA.

Our feeder lies outside every validated range: two 15 MVA IBRs, R_f ≈ 0.19–1.9 pu, 2–4 Ω lines, 0.8 pu dispatch and a 1.2 pu limit. Our back-of-envelope analysis suggests SG emulation itself breaks down there:
- The passive proportional law (IEEE 2800) fades below relay pickup.
- The visible fixed-magnitude laws (Yang, Medhat) can no longer stay passive once the injected I2 exceeds the fault's own I2. They then act as active sources and bias a relay with that inverter behind it toward "reverse".
- Current-angle shaping cannot rescue one-ended reach, because R_f(1+M_r) turns a 2° residual into a line-sized reactance error.

Implications:
- **Novelty.** The claim should not be "IBR negative-sequence injection helps relays"; that is established and now standardised. The claim should be a **budget-limited delta, with correctness guaranteed over explicit uncertainty sets, in the high-R_f multi-IBR distribution regime where emulation laws provably or empirically fail, serving directional supervision and phase selection jointly**.
- **Baselines.** IEEE 2800-style K·V2 (B1) and Yang-style fixed-|I2| emulation (B2) are mandatory; Azzouz-2019 (B4) is the phase-selection competitor, and Banaiemoqadam (B5) is only for the reach discussion.
- **Finding (3).** None of the five papers addresses non-fault events such as a remote inverter disconnecting. A negative-sequence-gated direction decision has a natural advantage here over superimposed-positive-sequence 32P: a balanced disconnection produces no I2.
- **Budget set.** The current limit is convex in the complex delta: an intersection of three discs, which yields the 0.4 pu figure. That makes the budget constraint easy to handle in a Taylor-style convex or bilinear program.

**Comparison table (supports the synthesis)**

| | Yang 2023 | Azzouz 2019 | Medhat 2022 | Banaiemoqadam 2020 | Davi 2023 (IEEE 2800) |
|---|---|---|---|---|---|
| Target element | 32Q + superimposed-positive-sequence 32 | Current-angle phase selector (δ⁺/δ⁰) | Current-angle phase selector | Quadrilateral/mho distance | 32Q, 32G, 2 phase selectors, mho |
| Shaped current | I⁺ angle and I⁻ angle | I⁻ angle | I⁻ and I⁰ angles | I⁺ angle (optionally I⁻) | I2 = K·V2 |
| Reference | ΔU1 memory; V2 (+90°) | ∠I⁺ or ∠I⁰ + zone centre | V⁻, V⁰ and grid X/R | Emulated SG I⁻ + α offset | V2 (+90–100°) |
| Needs fault-type classification | No | Yes (voltage-based) | No | Yes (voltage-based) | No |
| I2 magnitude | Fixed fraction β/(1+β) of 1.5 pu | Fixed at I⁻_limit | Fixed 0.23–0.24 pu | — (or DCC) | ∝ V2 |
| Current-limit method | Iterative phase-peak maximisation | I⁺_lim + I⁻_lim ≥ I_max | Offline GA, worst case | |I⁺| = 1.2 pu | Not described |
| Grid code | Overrides reactive-current curve | Keeps GC for I⁺ | Keeps GC for I⁺ | Overrides curve | Compliant by definition |
| Test system | 220 kV, 1 plant, SCR 30 (weak 10, 3) | 138 kV IEEE 14-bus, 3 IIRES + SGs | CIGRE LV 400 V, 2–3 PV | 230 kV IEEE 9-bus, 1 CIRES | 500 kV (inferred), 1 plant |
| Max R_f (≈ pu of IBR base) | 100 Ω (~0.2) | 50 Ω (~0.05–0.1) | 0.73 pu | 100 Ω (~0.19) | R_g 100 Ω (~0.09) |
| Tools | PSCAD, RTDS, 2.5 kVA hardware | PSCAD, Simulink, DSP timing | Simulink (average model) | PSCAD | PSCAD + commercial-relay playback |
| Reverse faults tested | Yes (F1 trivial, F5 at R21) | n/a (phase selection) | Yes (IIDG-fed, by our reading) | No (only forward external: zone 2, bus 8, L48) | **No** (32Q) |
