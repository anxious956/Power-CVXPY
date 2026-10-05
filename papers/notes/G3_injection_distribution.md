# G3 — Injection-based and distribution-directional competitors, plus the two-ended reference

These notes cover five papers against our project: Taylor's idea of an IBR injecting a designed fundamental-frequency negative-sequence (NS) current delta, and our EMT findings on the grid-connected CIGRE MV 20 kV feeder (two 15 MVA GFL inverters, 1.2 pu phase-current limit, short 2–4 ohm lines, R_f mostly 5–50 ohm). I read every page of all five PDFs. Text was extracted with `pypdf`. Pages whose tables or figures carry numbers (Saleh Tables I–VI and Figs. 5–11; Mohammadhassani Figs. 3–5; Yang Figs. 1–13; Opoku Figs. 1–10 and Tables 1–3; SEL Figs. 5–8 and 10–14) were rendered to PNG with PyMuPDF and read visually, because `pypdf` returns only their captions. **Page convention:** "p." is the printed journal page where one exists (Saleh 2434–2445; Yang 1–12; Opoku 7094–7109). Mohammadhassani has no printed numbers, so "PDF p." is used. SEL's printed p. N is PDF p. N+1 (PDF p. 1 is a cover sheet). Statements marked **[ours]** are my own inference or arithmetic, not claims made by the authors.

---

## Paper 1 — Saleh, Allam, Mehrizi-Sani (2021): synthetic harmonic *pattern* injection, optimised

**Citation.** K. Saleh, M. A. Allam, A. Mehrizi-Sani, "Protection of Inverter-Based Islanded Microgrids via Synthetic Harmonic Current Pattern Injection," *IEEE Trans. Power Delivery*, vol. 36, no. 4, pp. 2434–2445, Aug. 2021. DOI 10.1109/TPWRD.2020.2994558. (First published May 2020.)

**Setting.**
- Test system: the CIGRE MV benchmark topology in its 12.47 kV North-American variant. It has 14 buses, a 115 kV source through two 115/12.47 kV transformers, and switches S1–S3 that select radial, looped or meshed operation (Fig. 4, p. 2439). This is the same topology family as our feeder, but at 12.47 kV and 60 Hz, where ours is 20 kV and 50 Hz. The 60 Hz follows from 3.5 cycles = 58.33 ms.
- **Islanded only:** both substation transformers are de-energised (p. 2439).
- There are 30 relays, one at each end of 15 lines. The system has 14 IBDGs of 0.5–6 MVA (Table I, p. 2440).
- Inverter control uses per-phase single-phase dq current loops with saturation blocks acting as the current limiter. Each unit is either PQ-controlled (GFL) or droop-controlled (GFM) (Fig. 1, p. 2436). The paper does not say which units are GFM.
- Tools: PSCAD/EMTDC for simulation and MATLAB's genetic algorithm for the optimisation. No HIL.

**Method.**
- *Injected signal.* Each IBDG can inject any subset of three "synthetic" harmonics (3rd, 5th, 7th). The phase is shifted by θ instead of hθ, so all three are **positive-sequence**, including the "3rd" (p. 2436).
  - They are injected by per-phase, per-harmonic PR controllers: an outer loop on grid current and an inner loop on inverter-side current, nine PR loops per inverter (p. 2437).
  - Injection starts only in phases whose filtered rms voltage falls below Ψ = 0.88 pu, a threshold taken from IEEE 1547-2018 LVRT (p. 2437).
- *Injection size and current limit.* The current budget is set in rms terms. The fundamental limiter is lowered to β = 1.0 pu, total rms is capped at α = 1.2 pu, and each harmonic is fixed at sqrt((α² − β²)/3) = **0.38 pu** of the unit rating (eqs. 1–2, p. 2436). Magnitudes are never optimised. A harmonic is either on at 0.38 pu or off.
- *Measurement.* Each relay takes FFT **magnitudes** of the 3rd/5th/7th harmonics in the positive-sequence current. These form the measured pattern MP, a three-element vector with no phase information (p. 2437).
- *Directional decision.* The relay computes the cosine similarity between MP and its stored characteristic pattern CP. It declares forward if the similarity is at least λ = 0.85, otherwise reverse.
  - λ is the largest similarity between any two distinct binary patterns (0.8165) plus a 5 % margin.
  - An optional voltage restraint (relay-side per-phase V < 0.88 pu) can be added (p. 2437).
- *Trip scheme.* POTT is the primary scheme (both line ends must see forward).
  - DZI (direction zone-interlocking) is the remote backup, with a CTI of 10 cycles.
  - As a last resort, all IBDGs trip on LVRT at 15 cycles (pp. 2437–2438).
  - The scheme needs point-to-point low-bandwidth channels (0.5–1.5 kHz analog or 9.6 kbps digital) or IEC 61850 GOOSE (p. 2438).
- *The optimisation, stated exactly (Sec. IV, pp. 2438–2439):*
  - **Variables:** binary vectors IP_n ∈ {0,1}³, one per IBDG n = 1..N. Each element switches one harmonic on or off.
  - **Objective (5):** minimise H = Σ_n ‖IP_n‖₁, the total number of harmonic injections.
  - **Constraint (6), detection:** for every fault F_ij, the 1-norm of the primary relays' MP must be at least ε = 1e-4. In words, each primary relay sees at least one harmonic.
  - **Constraint (7), directionality:** for every relay R_ij, cos(MP^For, MP^Rev) ≤ λ. The forward and reverse patterns must differ. The paper does not say which forward/reverse fault pairs are enumerated; the index set is written only as "for all i, j".
  - **Model:** MPs come from **nodal analysis**. The paper does not give its details (harmonic-frequency network, source model, fault model). Inputs are listed only as topology, IBDG locations and IBDG ratings. **Loads, R_f, fault type and fault position are not inputs.**
  - **Solver:** the problem is a nonconvex nonlinear binary program, solved with MATLAB's GA. There is no optimality or feasibility certificate.
  - **Post-step (8):** CP is the forward MP normalised by its largest element and rounded to the nearest 0.25, giving five levels. That allows 124 non-trivial patterns, of which 1818 of 7626 pairs exceed λ (p. 2439).
- *Contingency model (Sec. V, p. 2439).* Same objective and detection constraint. With the CPs frozen, (7) is replaced by (9), cos(MP^For, CP) ≥ λ, and (10), cos(CP, MP^Rev) ≤ λ. It is re-solved for each outage, and the new IPs are pushed to the IBDGs over the secondary/tertiary-control link.
  - Topology is therefore handled by **re-solving each scenario and communicating the result**, not by robust design.
  - If an injector fails abruptly during a fault, relays may miss the fault, and the scheme falls back to the 15-cycle LVRT shutdown (p. 2439).
- *Uncertainty coverage.* None inside the optimisation for R_f, loading or fault type. Robustness to these was checked afterwards with a few simulations.

**Key results.**
- Base meshed case: 6 of 14 IBDGs inject one harmonic each, so H = 6 (Table I p. 2440; p. 2441).
- F910, bolted 3-phase fault:
  - IBDG voltages fall below Ψ within 3 ms. MPs settle after about 50 ms (3 cycles). Both primaries exceed λ (pp. 2441–2442, Figs. 5–8).
  - Adjacent relays: R89 and R1110 read forward; R98 and R1011 read reverse. POTT trips the faulted line and DZI stays blocked.
  - In Fig. 7 (p. 2442), R89 and R98 measure the **same** MP (≈ 78/85/39 A). Recomputing their cosine similarities from Fig. 7 and Table II gives 0.99 for R89 and 0.844 for R98 **[ours]**. So on that line the forward/reverse call comes entirely from the two relays having different CPs. The element recognises which injectors feed current through the line; it does not measure direction.
- Table V (p. 2440), bolted 3-phase faults at the midpoints of all 15 lines: primaries read 0.96–0.99. Reverse-looking adjacent relays range from 0 to 0.87.
  - Several sit within 0.01–0.04 of λ = 0.85: R98 = 0.84 (F910), R89 = 0.83 (F38), R89 = 0.82 (F814), R1110 = 0.81 (F411).
  - **Two exceed λ:** R65 = 0.87 for F67, and R109 = 0.87 for F1011. Under the naming convention used in every other row (R_ij sits at bus i and looks toward j), both are reverse-looking.
  - The text says only one relay per adjacent line exceeds λ. If my reading is right, both ends of L56 (for F67) and of L910 (for F1011) would declare forward, and POTT would over-trip. **[ours; see the uncertain list]**
- Contingencies: after loss of 1, 2 or 3 injectors, 6, 10 and 8 IBDGs inject (Table III). Line outages 4–11, 3–8 and 5–6 are in Table IV. Correct operation is asserted, but no cosine-similarity table is given for these cases (p. 2442).
- Fault types (bolted, L56): MP magnitudes change a lot (the 3rd harmonic is 30 A for AG and 103 A for ABCG), but the pattern's direction does not, and all cases exceed λ (Figs. 9–10, p. 2443).
  - This is structural: every injector scales its injection by the same faulted-phase count, and cosine similarity ignores scale **[ours]**.
- Fault resistance: **one** case only — a 3-phase fault at F78 with R_f = 10 and 40 Ω, relay R87. The MP roughly halves (5th harmonic 60.8 → 32 A), and the 7th-harmonic share *rises* (7.6 → 9.4 A). Cosine similarity stays above λ (Fig. 11, p. 2443).
  - Only the dependability of a forward-looking primary was tested. Security of reverse-looking relays under R_f, and faults to ground through R_f, were not tested.
- Other configurations: meshed with 7 and with 5 IBDGs (H = 4 in both) and radial with 14 IBDGs (Table VI, p. 2441; p. 2443).
- Speed: POTT 58.33 ms, DZI 166.66 ms, LVRT shutdown 250 ms (p. 2443).

**Assumptions and limitations.**
- *Stated:* islanded operation; communication needed for POTT/DZI and for contingency IP updates; injector failure during a fault defeats the scheme; the voltage restraint trades dependability for security.
- *Unstated:*
  - Grid-connected operation is untested.
  - Faults are bolted except for one R_f case. Load variation is never exercised.
  - The GA gives no guarantee, and the nodal model is unspecified.
  - The magnitude-only MP cannot measure the sign of power flow.
  - Fundamental fault current is cut to 1.0 pu to make room for harmonics.
  - Power quality is not quantified. At 0.38 pu per harmonic against a 1.0 pu fundamental, harmonic rms reaches 0.66 pu (≈ 66 % current THD) on units injecting all three **[ours]**. Voltage distortion in Fig. 6 is visibly heavy.
  - The limit is an **rms** budget. The worst-case instantaneous peak with aligned harmonics is (1 + 3·0.38)/1.2 ≈ 1.8× the peak of a 1.2 pu sinusoid **[ours]**. Semiconductors are limited on peak current, so this matters.
  - The 0.88 pu trigger may never fire for high-R_f faults where voltage stays up.

**Relevance to us.**
- *Versus a Taylor delta.* This is the closest prior art for "optimising the injection so relays can tell forward from reverse". It differs from Taylor's formulation on every axis:
  - variables: binary on/off vs a continuous complex phasor;
  - model: nominal deterministic nodal model vs bounded uncertainty sets over R_f, load and source;
  - solver: GA vs convex/bilinear with certificates;
  - signal: harmonic magnitude pattern vs fundamental NS with a known phase;
  - scheme: communicating POTT vs a single-ended decision;
  - current limit: static rms margin vs an explicit phase-current constraint;
  - operation: islanded vs grid-connected.
- *On our feeder:* unlikely to work as published **[ours]**.
  - With the substation connected, the grid is a low-impedance sink at 150–350 Hz. Injected harmonics flow toward the grid wherever the fault is, so "harmonics flow toward the fault" no longer holds. An inverter-bus relay would see its own inverter's pattern for both forward and reverse faults. This is the same failure mode as our 32Q finding.
  - Two injectors give a tiny pattern alphabet.
  - The 0.88 pu trigger may not fire for 5–50 Ω faults.
  - The trip still needs POTT. That puts it in the same class as our both-ends schemes (75–82 %), not a single-ended fix.
  - Injecting 0.38 pu harmonics into a grid-connected feeder on every sag, including external ones, is a poor fit for utility practice.
- *Reusable:*
  - (i) Constraint (7) is the template for our formal requirement that forward and reverse decision statistics be separated. Taylor's version adds a margin that holds over the uncertainty set.
  - (ii) Table V's layout — primaries plus all adjacent relays, each shown with its margin to threshold — is a good reporting format.
  - (iii) The contingency model (relay settings frozen, injection re-optimised per topology) is a sensible "adaptive injection" baseline.
  - (iv) 58 ms POTT with a 3-cycle FFT is a timing reference.
- *Novelty:* we **cannot** claim the first optimisation-designed injection for protection. Our claim must rest on:
  - continuous, fundamental-frequency NS;
  - robustness over bounded uncertainty, with certification;
  - an explicit phase-current limit;
  - grid-connected GFL inverters and a single-ended decision;
  - high R_f.

**Extraction notes.** All six tables and Figs. 1, 4–11 are images, so I read them from renders. Eqs. (6) and (9) lose "≥" in the text layer (it becomes `/greaterorequalslant`), but it renders correctly. Nothing is garbled in the rendered PDF.

---

## Paper 2 — Mohammadhassani, Mehrizi-Sani, Saleh (2021): SVM on the harmonic pattern

**Citation.** A. Mohammadhassani, A. Mehrizi-Sani, K. Saleh, "Fault Current Directionality in Islanded Microgrids Using SVM and Synthetic Harmonic Injection," *Proc. IEEE 30th Int. Symp. Industrial Electronics (ISIE)*, 2021 (ISBN 978-1-7281-9023-5), 5 pp. The PDF prints no page numbers or DOI.

**Setting.** Same 12.47 kV CIGRE system as Paper 1 (Fig. 3, PDF p. 3), islanded with the upper switches open and meshed with the three lower switches closed. It uses Saleh's optimal injection pattern: buses 1 and 4 inject the 3rd, 9 and 12 the 5th, 7 and 11 the 7th (Table I, PDF p. 5). Injection is 0.38 pu per harmonic, triggered at 0.88 pu. Tools: PSCAD/EMTDC and MATLAB `fitcsvm`. No HIL.

**Method.**
- The cosine-similarity/CP element is replaced by a **per-relay linear SVM** on the raw three harmonic magnitudes in amperes (eqs. 5–7, PDF p. 3).
- *Training, per relay (PDF pp. 3–4):* features sampled every 30 µs for one cycle after detection (556 samples per fault) from **two** bolted 3-phase faults. One is forward (midpoint of L9-10); one is reverse (L9-8 for R910, L11-10 for R109). That gives 1121×3 samples.
- *Testing:* **one** bolted 3-phase fault at the L8-3 midpoint, which is reverse for R910 and forward for R109.
- The authors claim no communication is needed. Only the directional element is local, though, and the trip logic that would replace POTT is not described.

**Key results (PDF pp. 4–5).**
- The data are linearly separable. Kernel coefficients are in Table II.
- On the test fault, R910 classifies 100 % of samples as reverse (correct) and R109 88 % as forward (correct). The metric is **per sample**, not per decision.
- Saleh's cosine-similarity method on the same fault gives R910 = 0.91, i.e. **forward — wrong** (Table III, PDF p. 5), and R109 = 0.98 (forward, correct).

**Assumptions and limitations.**
- Balanced bolted faults only, two relays, two training faults per relay, one test fault. Islanded only.
- No R_f, unbalanced faults or load variation.
- The model needs retraining whenever topology or IBDGs change, which is the same weakness the authors criticise in CPs.
- *Unstated:* the features are not normalised, so the classifier is not scale-invariant **[ours]**. As R_f grows, all magnitudes shrink toward the origin, and the bias term (b = −1.43 for R910, +1.02 for R109) sets the class whatever the direction is.
- The 12 % per-sample error at R109 would need a voting or timer rule, which the paper does not define.

**Relevance to us.**
- Independent evidence that the Paper 1 pattern element misclassifies reverse faults. This matches my reading of Paper 1's Table V.
- A learned classifier offers no margin guarantee. That strengthens the case for a certified, robust design of the delta.
- On our feeder it inherits all of Paper 1's physical objections, and it depends on training data. It is not a viable baseline beyond being an illustration of "ML on injected features".
- *Reusable lesson:* report **per-event** dependability and security, not per-sample accuracy, and test on many held-out events.

**Extraction notes.** The equations extracted cleanly. Figs. 4–5 (3-D feature scatter) were read from renders. The test samples cluster near the origin, close to R109's hyperplane.

---

## Paper 3 — Yang, Dyśko, Egea-Àlvarez (2024): negative-sequence current injection (NSCI) — the closest competitor

**Citation.** Z. Yang, A. Dyśko, A. Egea-Àlvarez, "A negative sequence current injection (NSCI)-based active protection scheme for islanded microgrids," *Int. J. Electr. Power Energy Syst.*, vol. 158, art. 109965, 2024. DOI 10.1016/j.ijepes.2024.109965 (open access, CC BY-NC-ND).

**Setting.**
- **Islanded only.** Grid-connected mode is explicitly left to conventional passive protection (p. 2).
- Main test system: an 11 kV, 50 Hz radial microgrid with 5 buses and 4 lines of 2.5 km each at 0.1 + j0.1 Ω/km, i.e. only ≈ 0.25 + j0.25 Ω per line (Table 1, p. 3).
  - Four 10 MVA VSCs: VSC1 is grid-forming (voltage-controlled); the rest are current-controlled. **VSC3 is the single dedicated injector.**
  - 5 MW load at every bus.
- Second system: a modified IEEE 13-bus network rescaled to 11 kV with 1 km lines, VSC6 grid-forming and VSC8 injecting (Table 7, p. 11).
- A variant replaces VSC1 with a synchronous generator (SG) of 10 or 30 MW.
- The simulation tool is **not stated**. HIL is listed as future work (p. 11).

**Method (pp. 2–7).**
1. *Detection.* Each relay detects a fault from V1 < 0.95 pu or V2/V1 > 0.05 (ANSI C84.1-based).
2. *Fault type.* The fault is classed unbalanced if the peak NS current exceeds I2th = 0.2·I2min, with I2min = 0.05·V_LL/(√3·Z_line,max) (eq. 1). Otherwise it is balanced.
3. *Injection sequence* (Fig. 4, p. 4):
   - the relay at the injector bus triggers the injector;
   - the injector ramps its **positive-sequence current to zero** (≈ 20 ms);
   - it waits 40 ms while every relay stores its steady pre-injection NS phasor I2pre by FFT;
   - it injects NS current with a trapezoidal envelope for 80 ms at **0.3 pu amplitude** (≈ 157 A rms for 10 MVA at 11 kV **[ours]**).
4. *Injected phase* (eqs. 2, 5–7, pp. 3, 5):
   - Unbalanced faults: a PI loop holds the injected phase at the pre-injection NS current angle of the branch chosen by the CAS indicator. CAS is the angle between the right-hand-side branch NS current and bus V2; above 90° means the fault is on the right-hand side.
   - Balanced faults: the angle is set to 0.
5. *Fault direction indicator (eqs. 3–4).* Each relay computes ΔI2 = I2gen − I2pre.
   - FDI = |ΔI2| for balanced faults; FDI = Re{ΔI2} for unbalanced faults.
   - Because the injection is aligned with the pre-injection NS current, ΔI2 lies near 0° for relays inside the source-to-fault path (SFP) and near 180° for relays outside it.
6. *Thresholds* come from a current-divider model with lumped load impedances Z_m and Z_n (eqs. 8–10, Fig. 6, p. 6).
   - Balanced: C = I2inj·Z_n/(Z_m + Z_n), the common value both curves approach as R_f → ∞.
   - Unbalanced: 0.2C, an 80 % margin for load uncertainty (Table 3, p. 7).
   - Loads are assumed evenly distributed when computing C.
7. *Trip.* Time-graded breakers with delays of 0.05–0.5 s (Table 2, p. 4) and **no communication**. The graded tripping also provides backup.

What counts as "design" here is only a fixed magnitude and a measured phase alignment. There is no optimisation.

**Key results.**
- *Maximum detectable R_f* is limited by the voltage-based detector (Table 5, p. 8):

  | Fault type | R_f max |
  |---|---|
  | 3-phase | 12.6–18.8 Ω |
  | SLG (B-E) | **3.8–6.7 Ω** |
  | LLG | 7.8–11.5 Ω |
  | LL | 8.9–13.2 Ω |

  It is almost unaffected by the load cases, and lowest on line 1 next to the GFM. Despite the "high impedance fault" framing, these values are small.
- *Direction margins, uniform load* (Fig. 9, p. 8):
  - Unbalanced: inside-SFP FDI stays positive and above C; outside-SFP FDI goes negative toward −C. The margin is wide up to R_f max.
  - Balanced: inside and outside both approach C, so the margin shrinks as R_f grows.
- *Uneven load* (Fig. 10, p. 9):
  - Balanced faults: inside FDI reaches C at 17 Ω (Case 2), and outside FDI reaches C at ≈ 13 Ω (Case 3). That is a **misdirection above ~13 Ω**.
  - Unbalanced faults: unaffected.
  - Power-factor changes (Cases 4–5): minor effect.
- *Strong source (SG) test* (Fig. 11, p. 10; text pp. 8–9):
  - C falls as SG size grows. Balanced-fault discrimination is lost above ≈ 4 Ω, and at a few ohms with a 30 MW SG.
  - Unbalanced faults remain separable up to a 30 MW SG (1.2× total load), but outside-SFP FDI moves close to zero.
- *IEEE 13-bus* (Fig. 13, p. 12): correct up to ≈ 12 Ω. Read from the figure: C ≈ 205 A, 0.2C ≈ 41 A.
- *Timing:* the FDI is available about 140 ms after inception (3 + 20 + 40 + 80 ms), and graded delays are added on top. The authors acknowledge this as slow (p. 9).

**Assumptions and limitations.**
- *Stated* (pp. 9–11):
  - the voltage detector can mis-detect under large single-phase load disturbances;
  - high-R_f faults are hard to see in large networks;
  - operation is slow;
  - one injector may not reach far branches in large networks (suggested fixes: zoning, or grouping buses).
- *Unstated:*
  - A **single injector** is a single point of failure.
  - The injector gives up all positive-sequence support during the fault.
  - The superposition argument assumes no other source changes NS current during injection (p. 5). IBRs with IEEE 2800-style NS control would violate this.
  - Relays at the injection bus rely on the passive CAS angle between I2 and V2, justified by sequence-network analysis without any margin study. This is essentially the passive 32Q element we found wrong at inverter buses (finding 2) **[ours]**.
  - Thresholds depend on the load-impedance distribution.
  - Power quality is not discussed: the scheme deliberately unbalances voltage for 80 ms, including during balanced faults.
  - Lines are electrically tiny.
  - Grid-connected operation is untested.

**Relevance to us.**
- *Versus a Taylor delta.* This is the nearest competitor: a fundamental-frequency NS injection, read through the increment it causes, used for direction. The authors state (p. 2) that they know of no earlier protection method based on active NS injection. That makes this paper the **priority reference for "NS current injection for fault direction"**, and our novelty statement must acknowledge it. Differences Taylor's approach can claim:
  - the δ phasor's magnitude **and** phase are designed by optimisation over bounded uncertainty (R_f, load, grid impedance), rather than a fixed 0.3 pu aligned to a measured phase;
  - an explicit phase-current limit is respected **alongside** positive-sequence FRT current, where Yang simply zeros I1;
  - grid-connected operation with several GFL inverters;
  - single-ended, relay-local decisions rather than time-graded SFP logic;
  - an R_f range of 5–50 Ω;
  - EMT dependability and security statistics rather than a handful of curves.
- *On our feeder* **[ours]:** the SG test is the proxy for grid connection. As the strong NS source grows, C and the margins collapse.
  - A 20 kV substation is a much stronger NS source than a 30 MW SG in an 11 kV island. Most of the injected ΔI2 would therefore flow to the substation wherever the fault is. Every relay between injector and substation would read "inside SFP" — a loss of selectivity.
  - Our R_f range of 5–50 Ω is also beyond their demonstrated detection range (≤ 6.7 Ω for SLG).
  - This fits our finding (1): in a grid-connected feeder the injection is small against the grid contribution, so it can shift a sign more easily than resolve a magnitude (reach).
- *Reusable:*
  - (i) **NSCI as a baseline injection policy.** Fixed |δ| of 0.3–0.4 pu, phase aligned with the pre-injection I2 (0 for balanced faults). Compare it head-to-head with a Taylor-designed δ under the same 0.4 pu budget.
  - (ii) The metric FDI = Re{ΔI2·e^(−jθ_ref)}, with inside/outside margin curves against R_f in the format of Figs. 8–11.
  - (iii) The R_f max table format (Table 5).
  - (iv) The load-distribution cases (Table 4) and the strong-source sweep as a robustness protocol.
  - (v) The current-divider model (eqs. 8–10) as a sanity check on our convex model.
  - (vi) The balanced/unbalanced discrimination by I2 threshold — a minimal form of the fault-type selection we want at inverter buses.

**Extraction notes.**
- Eq. (2) is printed with ">" where "=" (a definition) seems intended. This is in the paper itself, not an extraction error.
- The text layer drops the minus signs in eqs. (2) and (5). The renders read Δθ2(CAS) vs |θ2Rpre − θ2Vpre| and θ2inj = (θ2gref − θ2g)(kp + ki/s).
- Fig. 11's legend has typos: "MWA" and "30 MW".

---

## Paper 4 — Opoku, Dimitrovski, Ferrari (2025): superimposed NS admittance ΔY2 directional element (passive, HIL)

**Citation.** K. Opoku, A. Dimitrovski, M. Ferrari, "Performance Evaluation of a Novel Sequence-Based Directional Detection Strategy for Protection of Active Distribution Networks," *IEEE Access*, vol. 13, pp. 7094–7109, 2025. DOI 10.1109/ACCESS.2024.3525057 (CC BY 4.0). The ΔY2 concept first appeared in their ISGT-LA 2023 paper (ref. [47]).

**Setting.**
- Modified IEEE 13-node feeder, 4.16 kV, 60 Hz, with a 5 MVA 115/4.16 kV substation (Fig. 1, p. 7096).
- IBRs: a 250 kW BESS at bus 680, a 125 kW 3-phase PV at 692 and a 40 kW single-phase PV at 646. That is only ≈ 0.4 MW of IBR against a 5 MVA source, so **penetration is low**.
- Two modes (pp. 7096–7097):
  - *Grid-connected:* all inverters are GFL PQ controllers with current-magnitude scaling (eq. 2).
  - *Islanded:* the BESS is GFM (droop, virtual impedance, dual-loop dq control in both sequences). It supplies reactive I2 in proportion to V2, similar to VDE-AR-N 4120. Its current limit follows the conservative rule I1max + I2max ≤ I_invmax (eq. 3, Fig. 3).
- **Tools and HIL:** real-time EMT on OPAL-RT OP5600 (ARTEMiS solver, 25 µs step), with the model built in Simulink.
  - Hardware loop: SEL-411L relays fed through OP5330 analog outputs and an Omicron CMS amplifier; trip contacts return to digital inputs; DNP3 used for monitoring (p. 7101).
  - Physical relays sit at R633, R632 and R671. Tables 1–2 report about ten relays in total.

**Method.**
- *Signal.* Superimposed NS quantities against a one-cycle memory: ΔY2 = (I2 − I2m)/(V2 − V2m) (eqs. 11–13, p. 7100). This is **passive** — nothing is injected for protection.
- *Forward* is declared when |ΔY2| > Y_set **and** φ < arg ΔY2 < 180° + φ, with compensation φ = 45° (eq. 14).
- *Reverse* is declared if the angle is in the other half-plane **or** the magnitude is below the setting (eq. 15, Fig. 7, p. 7102). Low magnitude therefore defaults to reverse.
- *Supervision* is |I2|/|I1|. Fig. 7 shows 0.1, while the SELogic listing in Fig. 15 (p. 7108) uses 0.25. A latch holds the one-cycle quantities (p. 7101).
- *Settings.* Y_set = 1 pu grid-connected (calculations gave 0.4–0.8 pu for a 0.9 pu minimum voltage; 1 pu was chosen for simplicity) and 0.8 pu islanded, applied as separate setting groups (pp. 7102, 7104). The per-unit base of ΔY2 is not stated.
- *Implementation* uses SELogic free-form math, with chains of math variables creating the one-cycle delay. No firmware change or communication is needed. The element covers **unbalanced faults only**.

**Key results.**
- *Problems with existing elements* (Sec. III, pp. 7097–7100):
  - T32P misoperates forward (torque +188) for a reverse BC-G fault because the grid-dominated load angle pulls it (p. 7098).
  - T32Q loses sensitivity for remote faults with a strong source behind the relay: |V2| = 11.5 V secondary and I2/I1 = 0.167, near the restraint (pp. 7098–7099).
  - The SEL built-in Z2 element (32Q) fails at R671 in grid-connected mode, where I2 is 504 A against 2.9 kA at R632 (p. 7103).
  - It also fails at R2, R671 and R692 in islanded mode (e.g. Z2 = 2.83 against a Z2F threshold of −0.94) (pp. 7104–7107).
- *ΔY2 performance:* every tabulated decision is correct for SLG, 2LG and LL faults at F1–F9 in both modes (Tables 1–2, pp. 7105–7106). Forward |ΔY2| ranges 0.8–3.3 pu. Most reverse cases are "reverse" because |ΔY2| < 0.1, not because of the angle.
- *Tight margins:*
  - R680, at the BESS bus, reads |ΔY2| = 1.003–1.168 against Y_set = 1.0 in grid-connected mode (0.3 % margin in the worst case).
  - The same relay's angle for an LL fault at F6 is 50.0°, against a 45° boundary.
  - R633 for a reverse F1 fault reads |ΔY2| = 0.949, close to 1.0, and is saved by its angle (−72°).
  - **R680 is only ever tested with forward faults.** No security data exist at the IBR bus.
- *Speed:* 2.5 cycles (R2, R632, grid-connected), 6 cycles (R671, grid-connected), 2 cycles (R671, islanded) and 1.5 cycles (R692, islanded) (pp. 7102–7107).
  - In islanded mode R671's |ΔY2| drops below 0.8 after 3.75 cycles because the NS control fluctuates, which undermines use as time-delayed backup (p. 7106).
- *R_f:* a single value, "minimum 5 Ω assumed in each case" (p. 7102). High-impedance faults are left for future work (p. 7108).

**Assumptions and limitations.**
- *Stated:* depends on how fast the inverter delivers NS current in islanded mode; high-R_f faults not addressed; setting rules still open; standardised I2 injection would help (pp. 7107–7108).
- *Unstated:*
  - Unbalanced faults only; one R_f value; low IBR penetration.
  - A setting group per mode, so the relay must know the operating mode.
  - The one-cycle superimposed window overlaps the inverter's first-cycle control transient.
  - The element needs a **real NS source behind the relay** (the grid, or a GFM with NS control). With a positive-sequence-only GFL source behind the relay, the admittance behind is essentially the load. |ΔY2| is then small, and a forward fault defaults to "reverse" **[ours; consistent with R692's low-magnitude reverse calls]**.
  - The text says grid-connected IBRs supply positive sequence only, yet the R632/R671 grid-connected test explicitly enables BESS I2 injection per IEEE 2800 (p. 7103). The two statements conflict.

**Relevance to us.**
- *Versus a Taylor delta:* ΔY2 is a passive incremental version of what the injection would make deterministic.
  - For a forward fault ΔY2 ≈ −1/Z2(behind). At a GFL inverter bus, "behind" is set by the inverter's control, which is exactly why our 32Q/32P fail in both directions there (finding 2).
  - With a **known** injected δ, the relay (or a model) can use ΔV2/δ, the network NS impedance seen from the inverter bus, instead of an uncontrolled ratio **[ours]**.
  - Opoku notes that islanded operation needs substantial NS injection for sequence-based direction, and suggests GFM control should emulate the conventional NS contribution (p. 7104). That supports our direction of work.
  - Their I1max + I2max ≤ I_max rule is the kind of conservative convex inner approximation of a phase-current limit that a Taylor formulation can use.
- *On our feeder* **[ours]:** relays on the substation side probably work, because the grid is a strong NS source. At the GFL inverter buses, forward faults will probably default to reverse on low |ΔY2| (a dependability loss).
  - For finding (3), a remote inverter disconnecting mostly changes positive-sequence current. The |I2|/|I1| supervision should keep ΔY2 from treating that as a forward fault. This is a hypothesis we can test.
  - **We must test ΔY2 on our EMT data before claiming injection is necessary.** If this passive element already fixes the inverter-bus direction problem, the injection loses much of its value.
- *Reusable:*
  - (i) ΔY2 (φ = 45°, magnitude plus angle, |I2|/|I1| supervision) as the passive baseline.
  - (ii) SEL's built-in Z2/32Q as the commercial baseline.
  - (iii) Their per-relay, per-fault-type table reporting both |ΔY2| and arg ΔY2.
  - (iv) SELogic implementation as the route to "deployable on existing relays".

**Extraction notes.**
- The text layer turns Δ into "1" (e.g. "1Y2", "1I2").
- Fig. 7 prints the forward-angle inequality reversed (a typo in the figure); eq. (14) is correct.
- Tables 1–3 are images and were read from renders.
- The ohm symbol in "minimum fault resistance of 5 Ω" is lost in the text layer but visible in the render.

---

## Paper 5 — Chowdhury, McDaniel, Fischer (SEL, 2022): line current differential (87L) with IBRs

**Citation.** R. Chowdhury, R. McDaniel, N. Fischer, "Line Current Differential Protection in Systems With Inverter-Based Resources—Challenges and Solutions," *49th Annual Western Protective Relay Conference*, Spokane, WA, Oct. 2022. Also presented at the 76th Conference for Protective Relay Engineers (Mar. 2023) and the 76th Georgia Tech Protective Relaying Conference (May 2023). SEL TP7071-01.

**Setting.** Transmission level, not distribution. There is no single test system; the evidence comes from several cases:
- *Dependability case:* an EPRI simulation of a ≈ 1,700 MVA Type-4 wind farm on a 500 kV system with a 15 Ω AG internal fault, played back through relay hardware (p. 3).
- *Security case:* a field event from August 2019 on a 0.2-mile, 138 kV line near a 184 MVA Type-3 wind farm (pp. 3–4).
- *CT-requirement study:* 500 kV, lines 1–200 km, X/R up to 100, dual-breaker terminal, remanence up to 80 %, point-on-wave in 5° steps (p. 4).
- *Sensitivity study:* 230 kV, 50 km line; the weak IBR terminal has SIR1 = 5 and SIR0 = 0.5, the grid terminal SIR = 1 (p. 6).
- *Application example:* a 138 kV, 20 km tie line to a 100 MVA IBR through a YG/D/YG transformer, with a POI ring bus (p. 7).

**Method.**
- *Element.* Alpha-plane 87L (ratio I_L/I_R) with phase (87LP), zero-sequence (87LG) and negative-sequence (87LQ) sub-elements.
  - An external-fault detector (87EFD) switches between sensitive and secure settings.
  - Defaults: pickups 1.2/0.25/0.25 pu, radius 6, angle 195° (Table II, p. 2).
- *Proposed sensitive settings* (Table III, p. 5): pickups 0.30/0.20 pu (87LP/87LG), radius 1.35, angle 90°.
- *Proposed secure settings* (Table IV, p. 5): pickups 0.75/0.30 pu, radius 5, angle 170°.
- *How the settings are derived:*
  - The blocking angle comes from channel asymmetry: angle = asymmetry × f × 360° (eq. 1, p. 3). For example, 5 ms gives 108°, and 3.5 ms plus a 15° margin gives 90°.
  - The radius comes from the CT dimensioning factor K_TOT, which includes dc offset and 80 % remanence, with V_SAT = K_TOT · I_F · (R_CT + R_B) (eq. 4, p. 8; Fig. 8, p. 4).
  - The **87LQ pickup is set to 1.25× the IBR rated current** in CT per-unit: 1.25 · S_IBR / (√3 · V_HV · CTR · I_NOM) (eq. 2, p. 5). The secure pickup is 1.30× that (eq. 3), with minima of 0.20 and 0.30 pu. The purpose is to ignore the IBR's unreliable NS contribution.
- *Design change:* a phase-segregated 87EFD — three bits per packet instead of one on the 64 kbps channel (p. 6).

**Key results.**
- *Dependability problem* (Fig. 6, p. 3): for an internal AG fault, the unfaulted phases change a lot. The IBR transformer is a strong zero-sequence path while the IBR is a weak positive/negative-sequence source. 87EFD therefore asserts and holds the relay in secure mode, and with the default 1 s dropout the relay may not trip for **more than 1 s**.
- *Security problem* (Fig. 7, p. 4): 87LQ set at 0.10 pu tripped with **no fault**. IBR harmonics produced a rippling apparent NS differential current.
- *CT sizing* (pp. 4–5):
  - K_TOT = 4 is needed for the intended design.
  - K_TOT = 2 is the minimum for security.
  - Between 2 and 4, 87AP should be blocked while 87EFD is asserted.
  - Field line CTs are typically better than K_TOT = 6, which gives radius 4 and angle 80° at X/R = 100.
- *After the fixes* (p. 6):
  - The 1,700 MVA case trips on 87LP, 87LG and 87LQ despite EFD assertion, 87LP in about 30 ms (Fig. 11). 87LQ is delayed by the incoherent IBR NS current.
  - Recomputed 87LQ pickups are 1.23/1.60 pu for the 1,700 MVA case and 0.48/0.63 pu for the 184 MVA case; 0.48 pu would have kept the field event secure. I recomputed all four values from eq. (2) and they match **[ours]**.
- *Sensitivity* (Figs. 12–13, p. 7): 87AP catches LG faults up to ≈ 380 Ω primary on the 230 kV line, against ≈ 150–170 Ω for a percentage differential (87PCT) at 40 % slope. 87PCT loses sensitivity as channel asymmetry grows; 87AP does not.
- *Application example* (pp. 7–8): C400 CTs give K_TOT of 12 and 6, leading to radius 5 / angle 170°. C800 CTs at the dual-breaker terminal (K_TOT 11.33) allow radius 4.6 / angle 150°.

**Assumptions and limitations.**
- *Stated:* needs a reliable channel with bounded asymmetry; provides no remote backup; 87LG and 87LQ can still lose dependability in the EFD scenario.
- *Unstated:*
  - Transmission and two-terminal lines only; no distribution feeder, taps or laterals.
  - Evidence is event-based, with no dependability or security statistics.
  - The harmonic issue is solved by desensitising 87LQ, not by filtering.

**Relevance to us.**
- *Our two-ended reference.* This is the canonical both-ends scheme. It reaches far higher R_f sensitivity than directional comparison (hundreds of primary ohms) and trips in about 30 ms plus channel time. It is the upper bound to compare our both-ends 67N/67Q POTT-equivalent (75–82 %) against, and it is the scheme an injection-based single-ended proposal must justify *not* using.
  - The usual arguments against it are channel cost and availability on distribution feeders, and that differential cannot cover branched lines (Saleh, p. 2435).
- *CT sizing (finding 4).* Our finding that an undersized CT costs 67N/67Q its security should be stated in their K_TOT terms, using V_SAT ≥ K_TOT · I_F · (R_CT + R_B) with K_TOT ≥ 4. This gives the finding a recognised criterion.
- *Implication for a NS δ* **[ours]:** under SEL's 87LQ guidance, a 0.4 pu δ sits well below the pickup (1.25 pu of IBR rating). The injection therefore neither helps nor harms a correctly set 87LQ, and its value lies in single-ended or directional-comparison schemes.
  - The harmonic-induced 87LQ trip is also a warning for harmonic-injection schemes (Papers 1–2) that share relays with sensitive NS elements.
- *Illustrative scale for our feeder* **[ours; CT ratio assumed]:**
  - One 15 MVA inverter at 20 kV has a rated current of 433 A. Eq. (2) puts 87LQ sensitive pickup near 541 A primary.
  - A 50 Ω SLG fault at 20 kV draws at most ≈ 231 A. 87LQ and 87LP (0.30 pu, i.e. 180 A for an assumed 600 A CT) would miss or be marginal.
  - 87LG (0.20 pu, i.e. 120 A) would carry dependability for high-R_f ground faults.

**Extraction notes.**
- Eqs. (2)–(6) are scrambled in the text layer (fractions flattened). I rebuilt them from the renders and checked them numerically against the paper's own results.
- The figures are event records and characteristic plots, read from renders.

---

## Synthesis

The two injection families both demonstrate their concept **only in islanded, inverter-dominated, electrically compact microgrids**, and neither carries any guarantee over fault resistance, loading or topology:
- The harmonic-pattern family (Saleh; Mohammadhassani) uses a magnitude-only 3rd/5th/7th pattern at 0.38 pu per harmonic. Its injection is chosen by a nominal, GA-solved binary programme, and direction is inferred by pattern matching over a communicating POTT/DZI scheme. It is fragile even on the nominal bolted case: Paper 2 shows a reverse fault read as forward (0.91), and I read two reverse relays above λ in Saleh's Table V.
- The fundamental-NS family (Yang) uses a fixed 0.3 pu NS current whose phase is aligned to a measured pre-injection current, with an incremental Re{ΔI2} indicator and time-graded, communication-free tripping. It works best for unbalanced faults, but is detection-limited to about 4–19 Ω. Its margins collapse as a stiff source is added — the SG test, which is the closest thing in any of these papers to grid connection.

The distribution-directional paper (Opoku) shows, in HIL with SEL-411L relays, that a passive superimposed-NS-admittance element fixes load-induced 32Q/32P errors. Its measurement is still set by whatever NS source sits behind the relay; its margins at the BESS bus are razor-thin; it was tested at one R_f value and with low IBR penetration. The SEL 87L paper confirms that the two-ended scheme remains the dependable reference, provided the channel asymmetry and CT K_TOT are controlled. It deliberately sets 87LQ pickups above the IBR's rating and documents IBR-specific pitfalls: EFD-induced delays and harmonic-induced 87LQ trips.

For our project this leaves a well-defined gap: grid-connected feeders with **GFL** inverters that supply no NS source, **high R_f (5–50 Ω)**, a binding **phase-current limit shared with FRT current**, and a **single-ended** directional or fault-type decision at inverter buses whose correctness can be certified. It also forces two concessions in our novelty statement. We are not the first to inject current for protection (Saleh 2021; Yang 2024, which claims priority for NS injection). Nor are we the first to optimise an injection for directional discrimination (Saleh's NLIP). Our claim must be the robust, convex/bilinear design of a fundamental-frequency NS delta under explicit current limits, evaluated statistically in EMT.

None of the papers attempts zone-1 reach; all retreat to direction plus communication or time grading. That supports our pivot from reach to directional supervision. The immediate to-dos are:
1. Run Opoku's ΔY2 and a Yang-style fixed-phase NSCI as baselines on our CIGRE MV EMT cases at the same 0.4 pu budget.
2. Reuse Yang's R_f max and margin-versus-R_f curves and Saleh's primary/adjacent-relay margin table as reporting formats.
3. Express our CT-security finding with SEL's K_TOT criterion.

| | Saleh 2021 | Mohammadhassani 2021 | Yang 2024 | Opoku 2025 | SEL 2022 |
|---|---|---|---|---|---|
| Signal | 3rd/5th/7th synthetic (+seq), 0.38 pu each | same | fundamental NS, 0.3 pu, I1→0 | passive ΔI2/ΔV2 | two-end currents |
| Design | binary NLIP, GA, nominal | SVM on magnitudes | fixed size, phase aligned | none | settings rules |
| Mode | islanded | islanded | islanded | grid + islanded | transmission |
| Comms | POTT + DZI | claims none | none (time-graded) | none | 87L channel |
| R_f tested | 10, 40 Ω (one 3-phase case) | 0 | ≤ 6.7 Ω SLG … ≤ 18.8 Ω 3-phase | 5 Ω | 15 Ω event; ~380 Ω sensitivity calc |
| Speed | 58 ms POTT | 1 cycle of features | ≈ 140 ms + 0.05–0.5 s | 1.5–6 cycles | ≈ 30 ms + channel |
| Tool | PSCAD | PSCAD + MATLAB | not stated | OPAL-RT + SEL-411L HIL | relay playback, field records |
