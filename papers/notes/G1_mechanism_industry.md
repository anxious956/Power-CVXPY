# G1 — Why negative-sequence elements fail next to IBRs, and what industry does about it (reading notes)

These notes cover five documents on how inverter-based resources (IBRs) break negative-sequence protection elements (50Q/51Q, 32Q/67Q, 32P, and fault-type identification FID/FIDS), and on the remedies proposed by utilities, SEL, EPRI/Polytechnique Montréal and PNNL. I read them to support three of our CIGRE MV 20 kV EMT findings. Finding (2): at the inverter buses 32Q/32P is wrong in both directions. Finding (3): an inverter disconnecting at the remote bus looks like a forward fault. Finding (1) is also relevant, because it gives the injection budget: an affordable delta of about 0.4 pu with a 1.2 pu limiter and 0.8 pu dispatch. The notes also bear on the new direction, a designed negative-sequence injection for directional supervision and phase selection at inverter buses.

**How the documents were read.** Every page was read in full as text extracted with `pypdf`. Tables and figures that came through as images were rendered with PyMuPDF and read visually. This covers the Haddadi Tables I–VI, the Part I Tables I–III and Figs. 7/10/11/15/16, and TR81 Figs. 9/19/28–30/33. Numbers taken from a chart are marked "read from figure". Numbers I computed myself are marked "(my derivation)".

**Page conventions.**
- The two TPWRD papers are cited by journal page.
- WPRC is cited by its printed page, which is the same as the PDF page.
- TR81 is cited by its printed page, with the PDF page in brackets (printed page = PDF page − 6).
- PNNL is cited by its printed page, with the PDF page in brackets.

**Element definition used throughout (Part I, p. 2418, Fig. 7).**
- The relay computes Z2 = Re[V2 / (I2·1∠Z2L)].
- F32Q asserts when Z2 < Z2F, enabled only if 3I2 > 50FP.
- R32Q asserts when Z2 > Z2R, enabled only if 3I2 > 50RP.
- For a forward fault the relay measures Z2 ≈ −Z2S (the source behind it). For a reverse fault it measures Z2 ≈ Z2L + Z2R.

---

## Paper 1 — IEEE PES-TR81 (PSRC WG C32): protection challenges and practices for IBRs on transmission

**Citation.**
- IEEE PES Power System Relaying and Control Committee, System Protection Subcommittee, Working Group C32 (M. Nagpal, chair; M. Jensen, vice-chair; M. Higginson, secretary).
- *Protection Challenges and Practices for Interconnecting Inverter Based Resources to Utility Transmission Systems*, IEEE PES Technical Report PES-TR81, 2020.
- Running header: "Impact of Inverter Based Resources on Utility Transmission System Protection". Length: 64 numbered pages plus front matter, 70 PDF pages.
- The report number and the July 2020 date are not printed in the PDF text. They come from the file name and the IEEE catalogue. The PDF metadata is dated 26 Aug 2020.

**Setting.**
- **Scope.** Transmission and sub-transmission protection at the point of interconnection (POI). Distribution and microgrid interconnection are explicitly excluded (p. 2 [PDF 8]).
- **IBR types.** PV, Type III and Type IV wind, a STATCOM, and a battery inverter. The report does not treat grid-forming (GFM) control. The implicit model is a grid-following (GFL) current source (Fig. 11, p. 10).
- **Control.** Mostly coupled sequence control (CSC), meaning the negative sequence is suppressed. Decoupled sequence control (DSC) is shown with a VDE-style k slope.
- **Grid code.** Only VDE-AR-N 4130 required negative-sequence (NS) current at the time of writing (p. 7 [PDF 13]). TR81 proposes a universal NS reactive-current law, I2 = k·V2 with k = 2–6 (Fig. 8). It predates IEEE 2800-2022.
- **Evidence base.**
  - Relay field records (band-pass filtered, 4 samples/cycle) from 230 kV, 138 kV, 500 kV (external fault) and one 25 kV distribution event.
  - EMTP-RV simulations of a North-American 315 kV system with five wind parks. This is the same system as Paper 2.
  - The PSRC D6 test system, used for power swing studies.
- **No HIL.**

**What it shows (key quantities).**
- **Introductory field event** (p. 4–5 [PDF 10–11]). A phase-to-phase fault occurred on a short 138 kV line to a 100 MW Type IV plant.
  - The grid end carried 420 A before the fault and more than 6000 A during it. Zone 1 tripped within 3 cycles.
  - The IBR end stayed at its pre-fault current, began collapsing after about 2 cycles and was nearly zero by the end of the 3rd cycle. The IBR effectively became an open circuit, and the IBR-end distance relay never responded.
- **Current-limit arithmetic** (p. 8 [PDF 14], Fig. 9). Close-in LL fault on the HV side of the unit transformer:
  - A 100 MVA synchronous generator (X'' = 15%, 10% transformer) gives about 50% V2 and about 200% I2.
  - A 100 MVA IBR capped at 120% that keeps 100% pre-fault load current can inject only about 20% I2.
  - Without the load-current obligation it could inject about 60%.
  - Read from figure: at 80% load current the NS curve is about 44–46%, with phases B and C at the 120% cap.
- **Timing** (p. 7, p. 13 [PDF 13, 19]).
  - NS injection needs about 1–2 cycles, or up to the grid-code limit, to measure the unbalance and settle.
  - Before the IBR detects the fault, output rises to 1.1–2.0 pu after a possible spike.
  - Currents below about 20% voltage may cease.
- **NS directional background** (p. 16–18 [PDF 22–24]). With synchronous sources, I2 (or I0) leads its polarizing voltage for forward faults and lags it for reverse faults. Elements are enabled only above a minimum sequence current.
- **Example 1 — Type III wind** (field record, 230 kV, 5 Aug 2014; B-G fault evolving to BC-G; p. 19–23 [PDF 25–29]).
  - At the strong-source end, I2 and I0 lead V2 and V0 by about 90°, and the negative-sequence forward element (32GF) holds.
  - At the GDKT relay, which is fed by the 170 MW Type III plant (forward fault): I0 exceeded 600 A and led V0 by about 90°. I2 was below 90 A and almost **anti-phase** with V2. 32GF asserted only transiently.
  - At the RTLR relay (reverse fault, fed by the 142 MW Type III plant): I0 rose from 90 to 140 A and lagged V0 by 90°, which is correct. I2 was below 40 A and almost **in phase** with V2. 32GR asserted only transiently.
- **Example 2 — 100 MW PV at 230 kV** (YNyn transformer with delta tertiary; B-G fault; p. 23–25). The PV plant's I2 was only about 21% of its I1 and 24% of its I0, because the inverters limited NS injection.
- **Example 3 — STATCOM** (±12 MVAr, ±24 MVAr temporary; 138 kV; 30 Jun 2015; p. 25–30 [PDF 31–36]).
  - A C-G fault occurred on the adjacent line. The TAVL relay's Zone-1 ground quadrilateral reactance element, polarized by I2, **overreached**: the line is 5.18 Ω secondary and the reach was set to 3.8 Ω. This caused a regional outage.
  - I2 was about 55 A with a wandering angle, anti-phase with V2 at 1.5 cycles.
  - I0 was a steady 100 A leading V0 by about 90°. Replayed I0 polarization stayed secure (Fig. 26).
- **Example 4 — Type IV wind** (EMTP-RV, 315 kV, 200 × 1.5 MW; LL fault that is **reverse** for a 67Q looking toward the plant; I2 enable threshold 0.02 pu of 550 A; p. 30–33 [PDF 36–39]).
  - With a synchronous generator, V2 leads I2 by about 88° and 67QR is correct.
  - With CSC, I2 is about 0.05–0.1 pu (read from figure) and **67QF chatters: a false forward**.
  - With DSC at K = 2, I2 is about 0.3 pu (read from figure) with a 90° relation, and the decision is correct.
- **51Q** (same system; pickup 330 A ≈ 0.6 pu; p. 37–38 [PDF 43–44], Fig. 33 read from figure).

  | Source | I2 (pu) | I1 (pu) |
  |---|---|---|
  | Synchronous generator | 1.30 | 2.04 |
  | Type III | 0.88 | 1.12 |
  | Type IV, k = 6 | 0.67 | 0.72 |
  | Type IV, k = 2 | 0.54 | 0.54 |
  | Type IV, k = 0 | 0.11 | 1.09 |

  51Q fails at k = 0 and k = 2 and trips at k = 6. Raising k takes current away from I1, because the current limiter trades I1 for I2.
- **Battery inverter on a 25 kV feeder** (the only distribution case; p. 34–37 [PDF 40–43]).
  - 1.25 MVA inverter limited to 2.0 pu (3008 A at 480 V), connected through a delta/grounded-wye transformer. On 27 Jul 2017 it was closed onto a close-in AC-G fault.
  - Each faulted phase carried about 100 A. There was essentially no I2.
  - The transformer supplied a large I0 leading V0 by about 95°, so the zero-sequence direction was correct.
- **Phase distance / zero-power mode (ZPM)** (p. 38–43). A 100 MW Type IV plant sits on a 7.5 km, 138 kV line.
  - The plant's output stayed at its pre-fault level for about 2 cycles and then ceased.
  - An internal 3P fault was missed: phase overcurrent supervision was set above 420 A (1 pu). The fault was cleared by slow undervoltage backup.
- **POTT echo misoperation** (p. 43–44 [PDF 49–50]). A relay at the utility end of an IBR line did not detect a reverse external fault, because the I2 came from the IBR and was unreliable. It echoed permission and tripped. Echo logic was then disabled.
- **Conclusions** (p. 60–61 [PDF 66–67]).
  - NS directional and supervision elements need a k = 2–6 law, i.e. an apparent reactance of j0.5–j0.17 pu, below j0.5 pu. They also need slowing through the IBR transient.
  - 51Q stays hard even at k = 2.
  - Some relays need about 10% I2 relative to I1. This is an a2-type restraint, although TR81 does not use that name.

**Mechanism (as TR81 states it).**
- Converter controls regulate current magnitude to protect the switches and balance the output. Absent a code, they suppress I2.
- As a result, the IBR's apparent NS source impedance is large, **non-inductive and time-varying**, because it follows the controller (p. 10–11, 25, 34). The I2 that does flow therefore has an angle to V2 that is "not readily known" (Ex. 1 lesson, p. 23).
- The current limiter caps whatever I2 is requested. Load current and positive-sequence reactive current share the same limit (p. 8).
- The first 1–2 cycles are neither controlled nor limited in the same way as the later fault period (p. 13, p. 60).
- Delta windings on the interconnection transformer change the fault voltages the IBR sees. For example, an SLG fault appears as a smaller dip on two phases (p. 11–12).
- Grounded-wye/delta transformers are zero-sequence sources **independent of the inverter control**. That is why I0-based elements survived in every field case.

**Remedies proposed and cost.**
- **Zero-sequence ground protection** (32V/67N, 51N). Primary recommendation wherever a grounded-wye/delta transformer exists. It is cheap but only covers ground faults, and it is subject to mutual coupling.
- **Grid-code NS injection**, I2 ∝ V2 with k = 2–6. It needs inverter headroom, which is limited by the current limit and pre-fault load (Fig. 9), and relay slowing through the transient. It does not fix 51Q at low k.
- **Undervoltage backup at the IBR terminal** (phase-to-phase 27, coordinated with PRC-024 / LVRT). It is slow, about 1–1.5 s class, and degrades tapped-load power quality.
- **Direct transfer trip (DTT), POTT with echo plus DTT, DCB plus DTT, and 87L.** These need communication channels. 87L is the most reliable but needs expensive broadband channels and still requires local backup.
- **Low-set phase current supervision** with modern loss-of-potential (LOP) logic.
- **Discourage ZPM.**
- **Synchronous condensers.** High capital and operating cost.

**Assumptions and limitations.**
- *Stated.*
  - Transmission focus only.
  - Only three field faults are used, although "several others" are said to confirm them.
  - The Fig. 9 estimate assumes a close-in LL fault, 120% cap and unity-PF pre-fault load.
- *Unstated.*
  - The evidence is illustrative, not statistical; there are no fault-resistance sweeps.
  - The recommended k law emulates a synchronous machine without checking line angle, fault resistance (low V2 leads to low k·V2) or multiple IBRs.
  - Zero-sequence remedies assume a grounded interconnection transformer.
  - GFM is not considered.
  - Relay behaviour below the I2 threshold is vendor-dependent: it may block, or fall back to non-directional operation (p. 33).

**Rest of the report (skimmed).** Grid-code background covers German LVRT, positive-sequence reactive current and frequency ride-through (PRC-024). Fault-current factors include control strategy, residual voltage, pre-fault condition, time frame, Type III crowbar severity classes and transient ratings. Other sections cover:
- IBR effects on power-swing blocking and out-of-step tripping (PSB/OST) at 25% and 50% wind on the PSRC D6 system.
- Synchronous condensers.
- Subsynchronous control interaction (SSCI) with series capacitors (AEP 2017 events at 25.6 and 22.5 Hz) and SSR-relay requirements.
- Single-pole trip and reclose.
- Anti-islanding (IEEE 1547-2018 2 s, the NERC guideline to disable passive anti-islanding, and a utility screening method using 66% of minimum load).

None of this bears on 32Q at inverter buses.

**Relevance to us.**
- **Finding (2).** TR81 documents both error directions in the field, at transmission level:
  - forward faults not confirmed forward (Ex. 1 GDKT; ZPM case);
  - reverse faults declared forward, or not confirmed reverse (Ex. 4 CSC 67QF chatter; Ex. 1 RTLR; the POTT echo misoperation).

  The common condition is that the I2 through the relay is supplied by an IBR. Our inverter-bus relays are in that condition by construction on a radial feeder. The STATCOM case adds a variant: a converter **behind** the relay corrupts an I2-*polarized* element and causes overreach on an external fault.
- **Finding (3).** No example of an IBR trip or cessation being read as a forward fault. The closest material is the introductory event and ZPM, where IBR current steps to zero within 2–3 cycles, and the 1200 MW momentary-cessation event. Finding (3) is therefore **not covered** by TR81.
- **New direction.**
  - TR81 *already recommends* NS injection to restore NS directional and supervision elements. "Inject I2 to help 32Q" is therefore the mainstream industry position, not a novelty.
  - Fig. 9 independently supports our budget: about 0.45 pu I2 at 0.8 pu load with a 1.2 pu cap, against our "affordable 0.4 pu".
  - Fig. 9 also shows that curtailing pre-fault active current raises the available I2, to about 0.6 pu at zero load. That is a lever our optimisation could include explicitly.
- **Reusable material.**
  - The j1/k reactance mapping (k = 2 → j0.5 pu, k = 6 → j0.17 pu; synchronous generator j0.12–j0.4 pu).
  - The roughly 10% I2/I1 relay requirement as an a2-type supervision.
  - Ex. 4: an LL fault that is reverse for a 67Q looking toward the IBR, with a 0.02 pu enable.
  - The POTT-echo reverse-fault case.
  - The distribution battery case (D-YNg, 2 pu limit).
- **Baseline a reviewer will ask about: why not use 32V?** We must check whether the inverter interface transformers and grounding in our CIGRE MV model provide an MV-side I0 path.

---

## Paper 2 — Haddadi et al. 2021: IBRs and negative-sequence protection elements (50Q/51Q, 67Q, POTT, FID)

**Citation.**
A. Haddadi, M. Zhao, I. Kocar, U. Karaagac, K. W. Chan, E. Farantatos, "Impact of Inverter-Based Resources on Negative Sequence Quantities-Based Protection Elements," *IEEE Trans. Power Delivery*, vol. 36, no. 1, pp. 289–298, Feb. 2021. doi:10.1109/TPWRD.2020.2978075. Affiliations: Polytechnique Montréal, HK PolyU, EPRI.

**Setting.**
- **Test system.** EMTP simulation of a realistic 15-bus system at 315/230/120 kV with five wind parks (WP1–WP5) and two grid equivalents. Minimum loading: 30 MW unity-PF loads on the 25 kV sides (p. 292; Table VI).
  - WP1 and WP5 are Type III (DFIG) at 0.6 pu wind.
  - WP2–WP4 are Type IV (full-scale converter, FSC/PMSG) at 1.0 pu wind.
  - All are aggregated from 1.5 MW units.
- **Controls compared.** Type III with CSC; Type IV with CSC; Type IV with DSC per **VDE-AR-N 4120**, with the proportional gain set to its maximum of 6 because lower gains failed 50Q for some faults (p. 292). All are GFL; there is no GFM.
- **Model provenance.** The EMT models are generic but validated against field fault records (PV plant, DFIG parks) and manufacturer models.
- **HIL.** Real-time HIL with a physical distance relay, using a Simulink translation of the EMTP model and 110 V/1 A amplifiers (p. 295–296).
- **Scope notes.** WTG internal protection is ignored. Operating points (units in service, wind speed) are left out for space. PV is claimed to behave like Type IV.

**What it shows (key quantities).**
- **Equivalent NS impedance of the IBR** (Sec. II, p. 290–292). The IBR is represented as I2 = −V2/Z2_WTG, with current flowing into the grid.
  - *FSC with CSC* (Table I, p. 290): |Z2| ranges from about **5 pu to 1142 pu** at about **∠144° to ∠163°**. The exact value depends on the measurement-filter cut-off (1 kHz to 100 kHz) and on the choke/PI combination.
  - *DSC per VDE:* Z2 = 1/k, i.e. **0.167–0.5 pu** for k = 2–6.
  - *DFIG* (Table II, p. 291): **0.19–0.58 pu at about −102° to −114°**, set mostly by the machine's series impedance.
  - *Synchronous generator:* **0.12–0.4 pu at −90°** under the same sign convention.
  - *Simulated versus analytical Z2 of WP3/WP4* (Table III, p. 292): 4.36∠19.0° and 4.80∠28.0° simulated, 4.47∠20.4° analytical. These use a different PI gain (0.427 − j0.862) and a 2.5 kHz filter. The angle therefore moves by more than 100° with controller parameters.
- **50Q** (relay R50 at bus 6; AG1 fault; I2 pickup 0.2 pu of 1000 A; Fig. 3, Table IV, p. 292–293). Measured I2: **0.78 pu (SG), 0.52 (DFIG), 0.14 (FSC-CSC, fails), 0.65 (FSC-DSC, k = 6)**.
- **67Q** (R67_1 at bus 2 looking toward WP1; AB2 fault on line 2–3, which is **reverse**; MTA 85°, forward/reverse limit angles ±80°; pickups 0.25/0.15 pu of 550 A per Table VI, although the text says 0.2 pu; angles measured 100 ms after inception; Fig. 4, Table V, p. 293–294).

  | Source | Angle (V2 leads I2) | 67Q outcome |
  |---|---|---|
  | Synchronous generator | 87.4° | correct reverse |
  | DFIG | 78.0° | correct reverse |
  | FSC-CSC, normal pickups | — | I2 below pickup, **no decision** |
  | FSC-CSC, pickups cut to 0.02 pu | −20.0° (I2 leads V2) | **false forward** (67Q2) |
  | FSC-DSC | 91.5° | correct reverse |

- **POTT** (line 6–7; 21G Zone 2 plus a 67Q2 permissive; p. 294–295, Fig. 5).
  - Under FSC-CSC, 67Q2 at R1 asserted only transiently. The measured NS impedance angle was about **−180°, inside neither the forward nor the reverse zone**.
  - No permissive was keyed, so **POTT failed to trip an in-zone fault**. DSC fixed it.
  - The authors add that NS directional supervision in pilot schemes is a security add-on, not essential.
- **FID** (IA2–IA0 angle sectors with a ±30° margin; p. 295, Fig. 6).
  - With a synchronous generator, IA2 lags IA0 by about 6°, giving the correct AG sector.
  - With FSC-CSC, IA2 **leads IA0 by 80°**, which is outside every sector, so there is no phase selection. DSC is correct.
  - FID falls back to voltages if I2 and I0 are below threshold. That fallback was not triggered here.
- **HIL** (p. 296). A mid-line AG fault, 100 ms, on a line from an FSC-CSC plant. The relay at the **WTG bus** looks into the line, with Zone 1 at 80%.
  - With a synchronous generator, the directional element correctly says forward.
  - With the IBR, the directional element **declared the in-zone forward fault reverse**.

**Mechanism.**
1. Under CSC the converter's current controller tries to keep currents balanced. Its NS "impedance" is only the residual imperfection of that controller: choke impedance, the PI gain evaluated at twice fundamental (the negative sequence appears at 2f in the positive-sequence dq frame), and the measurement filter (Eq. 2).
2. It is therefore **huge**, which gives small I2 and fails the 50Q/67Q pickups. Its **angle is an accident of controller parameters**, so the V2/I2 angle lands in the wrong zone or in no zone. Control-parameter dependence of this angle is far larger than for a DFIG, where the machine dominates.
3. 67Q assumes both the source and the grid are highly inductive, i.e. V2 about 90° from I2 (p. 291). That assumption breaks.
4. DSC restores a reactive I2 that leads V2 by 90° and emulates a synchronous generator.
5. **Limits on DSC** (p. 293–294). VDE ignores line angle. When the line angle is far from 90° and I2 is capped by the converter current limit, the angle seen at buses away from the generator can deviate from the synchronous-generator case. It stayed inside the ±80° margin in their cases, but the paper explicitly says the grid code may **not** fix 67Q otherwise.
6. PNNL's summary of their companion EPSR paper adds that, without separate Id/Iq limits, injected I2 may not be predominantly inductive.

**Remedies and cost.**
- **DSC per VDE-AR-N 4120 with an adequate k.** k = 6 was needed. It costs converter headroom and grid-code compliance, and it takes I2 rise time.
- **Lowering 50Q/67Q pickups.** Impractical because of load-unbalance security, and the correct value depends on IBR type and control. At 0.02 pu it even produced a false forward.
- **Changing 67Q settings.**
- **Their blunt conclusion** (p. 294): do not apply 67Q where the resource cannot supply enough inductive NS current.
- **Echo logic with zero-sequence POTT**, cited from Nagpal and Henville, is noted but not tested.

**Assumptions and limitations.**
- *Stated.* Steady-state phasor impedance model: Z2 is not time-varying. Units in service and wind speed are omitted. WTG internal protection is ignored. PV is not modelled.
- *Unstated.*
  - Essentially one fault per element (AG1, AB2), apparently metallic, at a single operating point.
  - No fault-resistance or location sweeps, so no statistics.
  - Transmission lines with high X/R.
  - A single relay setting per element, and only one HIL case.
  - k = 6 is the maximum of the VDE range, i.e. the most favourable case.
  - Internal inconsistencies: the pickup is 0.2 pu in the text versus 0.25/0.15 in Table VI; the Fig. 5 caption says AB1 while the text says AG1.
  - The angle conventions of Table I (about +150°) and Table III (about +20°) are not reconciled.

**Relevance to us.**
- **Finding (2).** This is the cleanest precedent for *both* error directions:
  - a false **forward** for a reverse fault whose I2 comes from an IBR in front of the relay (67Q case);
  - a false **reverse** for an in-zone forward fault seen by a relay at the IBR bus (HIL);
  - "neither" when the angle sits near ±180° (POTT case).

  The mechanism to adopt and test is that the IBR's apparent NS source impedance is a controller artefact: large, with an arbitrary angle. **Action:** compute V2/I2 at our inverter terminals in the EMT runs and compare with Table I. If our GFL inverters (1.2 pu limiter) show a similarly large, oddly angled Z2, finding (2) is explained.
- **Finding (3).** Not addressed.
- **New direction.**
  - The paper already shows that a VDE-type DSC injection fixes 50Q, 67Q, POTT and FID at transmission level. The generic claim "inject I2 to make 32Q and phase selection work" is **not novel**.
  - The paper itself names the gap we can occupy: limited I2 plus a line angle far from 90° may defeat grid-code emulation. Distribution lines have lower X/R, so we should check our Z2L angle.
  - A proportional law I2 = k·V2 also collapses when V2 is small. This is exactly the high-fault-resistance (5–50 Ω) case on our feeder (my inference).
  - A **designed** delta, whose angle and magnitude are chosen against the relay's real characteristic and robust over an uncertainty set, is a defensible step beyond synchronous-machine emulation.
- **Reusable material.**
  - The Z2_WTG = −V2/I2 representation, which lets us express our delta as a designed "equivalent NS impedance".
  - The metric: V2–I2 angle at 100 ms, and I2 against pickup.
  - The 67Q settings (MTA 85°, ±80°), the FID sector logic (±30°), the POTT-with-67Q2 test and the HIL protocol.

---

## Paper 3 — Chowdhury & Fischer 2021, Part I: transmission line protection with IBRs — problems

**Citation.**
R. Chowdhury, N. Fischer (SEL), "Transmission Line Protection for Systems With Inverter-Based Resources – Part I: Problems," *IEEE Trans. Power Delivery*, vol. 36, no. 4, pp. 2416–2425, Aug. 2021. doi:10.1109/TPWRD.2020.3019990.

**Setting.**
- **Origin.** Sandia- and NERC-led, DOE-funded study with four IBR OEMs supplying **"real-code" black-box firmware models** wrapped in PSCAD. The simulations were run by Electranix.
  - OEM1 and OEM2: Type 4 wind.
  - OEM3: Type 3 wind.
  - OEM4: PV.
- **Relay testing.** COMTRADE records were played through relay hardware from two relay manufacturers. Results are shown for one, which uses full-cycle cosine filters (p. 2416–2418).
- **System** (Fig. 2, p. 2417). 230 kV, three buses.
  - Bus 1 strong: Z1 = Z2 = 10 Ω, Z0 = 30 Ω.
  - Bus 2 weaker: Z1 = Z2 = 30 Ω, Z0 = 90 Ω.
  - Lines: TL12 100 mi, TL13 60 mi, TL23 40 mi.
  - A single 100 MW IBR plant at Bus 3 (POI) through a 230/34.5 kV YNd·yn transformer (9% on 70 MVA). Collector bus SCR 5.5; unit transformers 34.5/0.6 kV YNd.
  - The TL23 relays are R1 (Bus 3, the IBR end) and R2 (Bus 2).
- **Cases.** 208 in total: 4 OEMs × 4 fault types (AG, ABG, AB, ABCG) × Rf = 0 and 5 Ω × locations A–F, plus location G (0 Ω).
- **Instrument transformers.** CVTs were added as transfer-function models, one with active and one with passive ferroresonance suppression. CTs were not modelled.
- **Control.** Whatever the OEM firmware does. North America had no NS requirement then, and GFL is implicit.

**What it shows (key quantities).**
- **Where failures occur.** Only when TL13 is out, so that the IBR is **radially connected** (locations D and G). With the parallel line in, the system contribution dominates and everything is 100%.
- **Performance tables** (Tables II/III, p. 2420).

  | Relay (locations D, G) | 32 | FIDS | 21Z1 | 21Z2 |
  |---|---|---|---|---|
  | R1 (IBR end) | 68% (dependability) | 87% (security) | 89% (security: overreach) | 56% (dependability: dropout) |
  | R2 (location G) | **68% (security: false forward on a reverse fault)** | 87% | 75% | 75% (all security) |

  87L was 100% everywhere. Denominators are not stated.
- **Type 4 wind** (OEM1/2; external ABG at G; p. 2421, Figs. 14–15).
  - I2 = 55 A primary (3I2 = 0.82 A secondary); I0 = 325 A (3I0 = 4.88 A).
  - I2 **rotates** relative to V2 and I0, because its frequency differs from that of V2 (Fig. 14: the replica current I2·1∠Z2L oscillates faster than V2).
  - FIDS picks BG and then AG for an ABG fault.
  - **R2 declares forward for the reverse fault.** Because the fault is close-in, the apparent impedance is small and Zone 1 misoperates.
  - R1's Zone 1 overreaches for the remote-bus fault, and its Zone 2 drops out.
  - Phasor snapshot (read from figure): R2 sees V2 ≈ 54 kV∠−102° with I2 ≈ 45 A∠0°, i.e. **I2 leads V2 by about 102° → forward**.
- **Type 3 wind** (OEM3; same fault; p. 2422, Figs. 16–17).
  - I2 is about 180 A (3I2 = 2.73 A secondary) and **coherent** with V2 and I0.
  - R1 gives F32Q and R2 gives R32Q, both correct. FIDS is correct.
  - Zone 1 at R1 still overreaches and Zone 2 still drops out.
  - Snapshot: R1 sees I2 leading V2 by about 99°; R2 sees V2 leading I2 by about 76° (read from figure).
  - For a **3P fault at G**, flux decays and the IBR, isolated from the "inertial frequency source", produces rotating current phasors. R2 **loses directionality** and Zone 1 misoperates for a reverse fault.
  - LG faults were fine.
- **PV** (OEM4). Zone 1 overreach at G with the active CVT (Fig. 20).
- **General observations** (p. 2416–2417).
  - IBRs lower I2 to limit dc-link overvoltage and ripple.
  - Their large NS impedance can cause temporary overvoltages.
  - Even standardized injection has a response time of more than one cycle, while line relays are expected to decide within about one cycle.

**Mechanism.** Two distinct mechanisms appear. Both apply whenever the relay's I2 is IBR-dominated.
1. **Low magnitude.** 3I2 approaches the 50FP/50RP enable levels (0.5 A/0.25 A secondary).
2. **Loss of coherence.** The IBR's I2 is not phase-locked to the network V2. It has a different effective frequency, so the V2/I2 angle rotates through the forward and reverse half-planes and the decision toggles.

The second mechanism is worse than Haddadi's static-angle picture, because no fixed angle setting can fix a rotating phasor.

My derivation from the snapshot values: |V2/I2| is about 1000 Ω primary (about 100 Ω secondary) for Type 4, and about 270 Ω primary (about 27 Ω secondary) for Type 3. These are far larger than Z2F/Z2R = ∓0.3 Ω secondary. With small I2, 32Q therefore degenerates into a pure **sign-of-cos(angle) test**: the neutral band between Z2F and Z2R is a fraction of a degree wide.

FIDS fails for the same reason, because I0 is stable (the transformer supplies it) while I2 rotates. Phase distance fails because of the oscillating apparent impedance.

**Remedies.** Deferred to Part II (Paper 4). Part I notes that adjusting settings is much cheaper than replacing relays or IBRs.

**Assumptions and limitations.**
- A single IBR plant, a strong-grid system and one relay vendor.
- Rf only 0 and 5 Ω.
- Transmission (230 kV, 40–100 mi lines).
- CTs not modelled.
- The black-box models are not characterised: CSC versus DSC is unknown, so the mechanism is inferred from waveforms.
- Percentages have no stated denominators.
- High-speed elements (incremental quantities, traveling waves, half-cycle filters) are out of scope.

**Relevance to us.**
- **Finding (2).** Part I is the most direct analogue.
  - At the IBR-end relay, forward faults are not declared forward.
  - At the relay whose reverse-fault current comes only from the IBR, the relay declares **forward**.
  - It is wrong in both directions, only when the IBR is radial.

  **Key mapping:** on a radial distribution feeder, "IBR radially connected" is the *normal* topology for a relay at an inverter bus, not an N-1 contingency. So the failure condition that is rare in the transmission study is the base case for us.
- **The coherence mechanism.** It predicts time-varying 32Q outputs. We should check whether our wrong decisions are stable or chattering, e.g. from the 32Q trace per cycle. A designed delta must be **phase-coherent with the grid V2**, which requires tracking the NS angle (see PNNL on DDSRF-PLL) or it will reproduce the problem.
- **Finding (3).** Only indirectly relevant: the 3P case where the IBR, separated from synchronous sources, yields rotating phasors and a lost or false phase direction. The paper's conclusion states that 32P may misbehave when a 3P fault disconnects the IBR from the power system. Our case, an inverter *tripping* at the remote bus being seen as forward, is not studied.
- **New direction: a 3P opportunity.** Part I also notes that 32Q is dependable for LLG and LL faults but **not 3P faults** (p. 2418). A 3P fault gives no natural V2, so this is where a designed NS probe could give 32Q a signal it otherwise lacks. A 3P fault short-circuits the NS network at the fault point, so the injected I2 would divide according to the fault location. This is my hypothesis and is untested in these papers.
- **Reusable material.**
  - The exact 32Q, 32P, 32G (ORDER Q then V) and FIDS logics (Figs. 7–11).
  - Default thresholds: Z2F = −0.3 Ω and Z2R = +0.3 Ω secondary; 50FP = 10% of nominal (0.5 A) and 50RP = 5% (0.25 A).
  - At their ratios (CTR 200 / PTR 2000) the thresholds equal ±3 Ω primary, about 10% of the line impedance. Scale to our 2–4 Ω lines rather than copy them (my suggestion).
  - The security/dependability scoring rules and the per-location/per-element percentage table format.
  - The 87L alpha-plane defaults, if needed.
- **Novelty.** Part I establishes that the problem exists. It proposes no IBR-side fix, so it does not threaten a designed-injection claim.

---

## Paper 4 — Chowdhury & Fischer 2021 (WPRC): transmission line protection with IBRs — solutions (conference version of Part II)

**Citation.**
- R. Chowdhury, N. Fischer (SEL), "Transmission Line Protection for Systems With Inverter-Based Resources," SEL technical paper TP6968-01 (© 2021), presented at the Western Protective Relay Conference 2021.
- The PDF text does not name the venue. "WPRC 2021" comes from the file name.
- Journal counterpart: "…Part II: Solutions," *IEEE Trans. Power Delivery*, doi:10.1109/TPWRD.2020.3030168, as cited in Part I.

**Setting.**
- The same Sandia study, system and 208 PSCAD real-code cases as Part I (seven locations A–G).
- The same relay-hardware playback with **modified settings**. There are no new simulations.
- Qualitative extensions: multiple IBR plants (a 230 kV example with CTR 600), undervoltage backup, communications, and parallel lines with zero-sequence mutual coupling.

**What it shows (key quantities).**
- **Setting rules** (p. 2–3, Table II), applied to both terminals whatever the OEM:
  - IMAX = 1.30·S_IBR / (√3·V_HV·CTR) in secondary A. Inverters limit to 1.10–1.30 pu. For their system IMAX = **1.63 A**.
  - **50FP = 1.25·IMAX = 2.04 A** (was 0.50 A).
  - **50RP = 1.00·IMAX = 1.63 A** (was 0.25 A).
  - Where the relay has separate 50QFP/50QRP settings, raise only those.
- **Why 1.25.**
  - A metallic LL fault from a conventional source with 1 pu phase current gives 3I1 = 3I2 = 1.73 pu.
  - OEM Type 4 gave 3I2 = 0.50·IMAX, incoherent. Type 3 gave 1.67·IMAX, coherent.
  - 1.25 is chosen to be secure but still let a synchronous-generator-like I2 through (p. 2).
- **Other settings.**
  - Enable Weak-Infeed Control (EWFC = Y), so FIDS uses phase undervoltage when I2 and I0 are below threshold.
  - ORDER = Q, V, so 32G falls back to 32V.
  - **PSV50 = F32P AND NOT F32Q AND I1 < 1.2·IMAX (1.96 A)**, which blocks phase elements (Zone 1, and Zone 2 via PCT21IN) for suspected IBR-fed 3P faults.
  - Zone 1 phase fault detector **Z50P1 = 2·1.20·IMAX = 3.92 A**.
  - CVT transient blocking if an active CVT is present.
  - A **6-cycle Zone 2 dropout** timer.
- **Results** (Tables III/IV, p. 6).
  - R2 is 100% for all elements and locations.
  - R1 at D and G: 32 is **56%**, FIDS 100%, 21Z1 100%, 21Z2 **38%**, 87L 100%.
  - The authors state **no misoperations**. Security is restored, but R1's directional and Zone 2 **dependability fell** (68% → 56% and 56% → 38%).
- **Type 4 ABG at G.** 32Q was not enabled because I2 was below the raised 50FP, and 32V gave the correct direction.
- **Type 3 LG at G.** I2 = 90 A primary (3I2 = 1.35 A) was below threshold, so 32V was used (3I0 = 6.5 A). FIDS used undervoltage.
- **Sensitivity cost** (Appendix, Fig. 12). The fault-resistance coverage of the sequence directional elements at R1 drops from **about 400 Ω to about 100 Ω primary** as 50FP rises from 0.5 A to about 2 A. The authors call this adequate for most 230 kV applications.
- **Expected clearing without communications, IBR radial** (Table V, p. 7).
  - Weak terminal R1: LG instantaneous. LL/LLG instantaneous or undervoltage-delayed (27D), **depending on whether the IBR supplies I2**. 3P always 27D.
  - Undervoltage backup (27D) trip in about 1.0–1.5 s, coordinated with PRC-024 and a Canadian utility practice (Fig. 10).
- **With communications** (Table VI). POTT with weak-infeed echo gives near-instantaneous clearing. There are delays only for LL/LLG/3P near the weak terminal.
- **IBR-dominated, both ends weak** (Table VII, p. 8). 3P is still 27D. Undervoltage loses selectivity with parallel lines. **Standardized IBR fault current** is named as the way forward.
- **Multiple plants** (p. 6–7). Use the IMAX of all IBRs that can feed an external fault through the line, e.g. 250 MVA → 1.36 A and 350 MVA → 1.90 A at CTR 600, with about a 25% margin.
- **ORDER = V caveat** (p. 6). Zero-sequence-only ground directional (ORDER = V) is popular for IBR lines. However, 32P ignores ORDER and can still misoperate on reverse LL/LLG faults with unpredictable I2 unless PSV50-type logic is added.

**Mechanism (as used for the fix).** Overcurrent magnitude is used as a proxy for "the IBR is radial and I2 cannot be trusted". If 3I2 is below what an IBR could possibly produce with margin, the relay refuses to use I2 at all. It then relies on I0 (grounded transformer), undervoltage, timers and communications.

**Remedies and cost.** All are settings-only, which is cheap. The costs are:
- lower sensitivity (about 4× less Rf coverage);
- lower dependability at the weak terminal (32 at 56%, Zone 2 at 38%);
- slow 27D clearing (seconds) for LL/LLG/3P without communications;
- reliance on pilot channels or 87L for speed;
- reliance on grounded interconnection transformers for 32V;
- IMAX bookkeeping as IBRs are added.

**Assumptions and limitations.**
- Same study limitations as Part I.
- The per-unit reasoning assumes a pure-IBR worst case at transmission voltage, with CT and relay ratios that make the thresholds meaningful.
- The paper assumes security matters more than dependability, which is SEL's explicit stance.
- **Minor typos:** the IMAX equation reference is (1) versus (2); "50P" should read 50RP (p. 3).
- No evaluation beyond the single-IBR system.
- "Adequate ~100 Ω coverage" is a 230 kV judgement.

**Relevance to us.**
- **Finding (2).** This is the industry **baseline** we must beat or explain: the "secure settings" at the inverter-bus relay.

  **Quantitative clash with our new direction (my derivation):** 50FP = 1.25·IMAX on 3I2 means I2 must exceed about **0.42·IMAX** before 32Q is even enabled. With a 1.2 pu limiter (IMAX ≈ 1.2–1.3 pu), that is about 0.5 pu I2. Our affordable delta (about 0.4 pu) would be *invisible* to a relay set this way.

  So the new direction needs conventional or low enable thresholds (10% of nominal) and must get its security from the **designed angle**, backed by a certificate. We must argue why that is safe where SEL chose not to trust I2.
- **Finding (3).**
  - PSV50 is directly transferable as a baseline supervision for our disconnection false-forward: block when a phase-directional forward decision comes without an NS confirmation and with I1 at or below the IBR's current limit.
  - A designed NS probe could supply the missing "32Q confirmation". It should give no fault signature for a pure inverter trip, but a clear one for a real fault (hypothesis).
- **Fault resistance.** Coverage collapses as thresholds rise. At 20 kV with Rf = 5–50 Ω and small I2, raising 50FP would drop many in-zone faults; this should be computed on our model.
- **Communications.** Distribution feeders rarely have pilot channels, which strengthens our single-ended premise.
- **Reusable material.**
  - The IMAX formula and its multi-IBR summation, which applies to our two 15 MVA inverters.
  - The PSV50 logic, the Zone 2 dropout timer and the Table V/VI clearing-time format.
- **Novelty.** SEL's philosophy is to *distrust* the IBR's I2. Ours is to *design* it. The contrast is our paper's framing: if a designed delta lets 32Q run at conventional thresholds with guaranteed security, it recovers the dependability SEL gives up.

---

## Paper 5 — Lyu, Xie, McDermott 2024 (PNNL-36069): review of IBR negative-sequence current generation

**Citation.**
X. Lyu, J. Xie (PNNL), T. E. McDermott (Meltran, Inc.), *Impact of Inverter-Based Resources on Grid Protection: A Review of Negative-Sequence Current Generation*, PNNL-36069, Pacific Northwest National Laboratory, Richland, WA, prepared for the U.S. DOE under Contract DE-AC05-76RL01830. The PDF metadata is dated June 2024. It has 15 PDF pages, of which about 7 are body text.

**Setting.** A literature review with no simulations or data of its own. It covers:
- GFL Type III (DFIG) and full-converter IBRs (Type IV and PV), with CSC versus DSC;
- GFM strategies;
- grid codes VDE-AR-N 4120/4130 (k = 2–6) and **IEEE 2800-2022**.

**What it shows (key points, with pages).**
- **Typical IBR fault traits** (p. 1 [PDF 6]):
  - low sustained current because of limits;
  - an initial transient lasting 0.5–1.5 cycles;
  - a V–I angle set by control;
  - no I0 from the inverter itself;
  - I2 partially or fully suppressed.
- **IEEE 2800-2022** (p. 1 [PDF 6]). Requires NS reactive current during unbalanced low voltage, dependent on terminal V2 in magnitude. I2 must **lead V2 by 90°–100° for full-converter IBRs and 90°–150° for Type III**. It applies to GFM as well.
- **Type III** (p. 3 [PDF 8]).
  - Under CSC it behaves roughly like a synchronous generator, per Haddadi, although field data hint at misoperation risk.
  - Chang et al. compare four DFIG controls. Only the flexible positive/negative reactive-current control (PNSC-I12R) meets code NS requirements.
  - Mohammadpour et al.: the DFIG's NS angle drifts from 90°–100° with rotor-side-converter (RSC) current-loop bandwidth. Torque-ripple dual current control can push it outside 90°–150°. A new grid-side-converter (GSC) dual control keeps it at 90°–100°.
- **Full converter** (p. 4–5 [PDF 9–10]).
  - Repeats Haddadi's 50Q/67Q/FID failures (FID: I2 leads I0 by 80°).
  - Haddadi's EPSR 2020 companion paper finds that **k cannot be raised arbitrarily because of the current limit**. Without separate Id/Iq limits the injected I2 **may not be mainly inductive**. DSC fixes 50Q (with a rise-time delay), 67Q and FID.
  - **Precise NS-angle tracking** is needed: DDSRF-PLL, or three per-phase PLLs.
- **Protection-oriented control schemes**, which are the closest prior art to our direction:
  - **Azzouz & Hooshyar** (TSG 2019; cited as 2018). Dual current control that (i) identifies the fault type from terminal sequence voltages, (ii) generates an I2 mimicking a synchronous generator, and (iii) tracks a reference angle in DSRF. The aim is correct *angle-based phase selection*, tested across fault/relay locations, fault resistances and the Spanish, German and North American codes.
  - **Banaiemoqadam, Hooshyar & Azzouz** (TPWRD 36(5), 2021). The positive sequence is a voltage source behind an adaptive virtual impedance. The negative sequence is a single virtual impedance. The aim is correct **directional, phase-selection and distance** operation.
- **GFM** (p. 6 [PDF 11]).
  - Mahamedi et al.: sequence-based control with natural-frame current saturation.
  - Chen, Lasseter & Jahns: droop GFM PV with SOGI sequence separation and NS compensation against dc-link ripple.
  - Per-phase phasor models of GFL and GFM inverters.
  - **Nasr & Hooshyar** (TPWRD 2023): a GFM positive-sequence voltage source plus a negative-sequence *current source* to meet IEEE 2800. It uses adaptive sequence-current division of the inverter's capacity, adaptive virtual impedance, an edge-triggered pulse limiter for the initial transient and a saturator on I2.
  - GFM NS control for protection is judged early-stage.
- **Conclusion** (p. 7 [PDF 12]). IBR NS behaviour is inconsistent across types and controls. Detailed EMT studies and relay–control coordination and standards are needed.

**Mechanism.** The report restates the literature: CSC does not regulate I2, so there is essentially no NS contribution. DSC regulates it but is bounded by the current limit and by angle-tracking accuracy. Type III machines naturally provide an NS path.

**Remedies and cost.**
- DSC to VDE or IEEE 2800 specifications. The cost is current headroom shared with I1, and NS-angle tracking.
- Protection-aware dual- or triple-current control, from the Hooshyar group.
- GFM sequence-current division.

The report gives no quantitative cost.

**Assumptions and limitations.**
- A short, secondary review that relies heavily on Haddadi and the Hooshyar group.
- Transmission and grid-code framing; no distribution-feeder discussion.
- It treats code compliance as sufficient for protection, without testing it.
- Editorial slips: "Gird-Following" in the headings, and reference [1] mixes an EPRI label with the TPWRD volume and pages of Haddadi.

**Relevance to us.**
- **Finding (2).** Nothing new beyond Haddadi. It confirms the CSC mechanism and that DSC is the textbook fix.
- **Finding (3).** Not addressed.
- **New direction.** This is mainly a **novelty map**. The following already exist:
  - "control the IBR's sequence currents so that directional, phase-selection and distance elements work" (Azzouz & Hooshyar; Banaiemoqadam et al.);
  - IEEE 2800's 90°–100° angle window;
  - GFM sequence-current budgeting (Nasr & Hooshyar).

  Our claim must therefore be narrower and sharper. It should rest on:
  - (i) **optimisation-based design** of delta over **bounded uncertainty sets**, with a guarantee or certificate of separation, rather than synchronous-machine emulation;
  - (ii) an explicit **current-limit budget** (0.8 pu dispatch, 1.2 pu cap);
  - (iii) **distribution-feeder** conditions: short 2–4 Ω lines, low X/R, Rf = 5–50 Ω, two inverters on one feeder, unbalanced loads;
  - (iv) the cases the literature ignores: 3P faults, and IBR disconnection seen as a forward fault.

  The NS-angle-tracking point (DDSRF-PLL) links to Part I's incoherence mechanism and is a practical design constraint for delta.
- **Reusable material.**
  - The IEEE 2800 angle window as a baseline "code-compliant" delta to compare against: fixed 90°–100° lead, magnitude ∝ V2.
  - The list of controllers to position against.
- **Prior art to check before any novelty claim.** Several files in our folders are directly on-point but **were not read in this task**:
  - `library/2019_Azzouz_Hooshyar_Dual_Current_Control_Phase_Selection.pdf`
  - `library/2020_Banaiemoqadam_Control_Based_Distance_Protection_Asymmetrical_Faults.pdf` (possibly a different paper from the TPWRD 36(5) one PNNL cites)
  - `library/2022_Medhat_Azzouz_Triple_Current_Control_Fault_Type.pdf`
  - `2023_Yang_Control_Method_Directional_Protection_Elements.pdf`
  - `2024_Yang_Dysko_NSCI_Active_Protection_Islanded_Microgrids.pdf`
  - `2025_Opoku_Sequence_Based_Directional_Detection_Active_Distribution.pdf`
  - `2023_IEEE2800_Benefits_Transmission_Line_Protection_IPST.pdf`
  - `Sandia_2020_IBR_Negative_Sequence_Injection_SAND2020-0265.pdf`, probably the Sandia study behind Papers 3–4.

---

## Synthesis

**What the five establish together.** They establish, at transmission level, that a negative-sequence element is unreliable whenever the I2 flowing through the relay is supplied by an IBR, and that the errors run in both directions:
- false forward for reverse faults fed by an IBR in front of the relay (Haddadi 67Q; TR81 Ex. 4 and the POTT-echo event; Part I R2 at 68% security);
- missing or false reverse for in-zone faults at the IBR-end relay (Haddadi HIL; TR81 Ex. 1; Part I R1 at 68% dependability);
- occasionally neither (Haddadi POTT, angle about −180°).

This is our finding (2), already documented in field records, real-code EMT and HIL, but only under the transmission N-1 condition "IBR radial". On a radial distribution feeder that condition is the base case.

**Three compounding mechanisms.**
- (a) Under coupled control the IBR's NS source impedance is a controller artefact. It is huge (5–1100 pu) and its angle depends on filter and PI parameters, so I2 is small and sits at an arbitrary angle.
- (b) The I2 can be frequency-incoherent with V2, so the V2/I2 angle rotates and 32Q chatters. With small I2, 32Q is effectively a pure sign-of-angle test, because the Z2F/Z2R band is negligible (my derivation from the Part I phasors).
- (c) The current limiter caps any requested I2. TR81 gives about 20% at full load, about 45% at 0.8 pu load (which matches our 0.4 pu budget) and about 60% at no load, with 1–2 cycles of uncontrolled transient first.

**Two industry answers.**
- *Make the IBR look like a synchronous machine*: VDE k = 2–6 or IEEE 2800 (I2 leads V2 by 90°–100°). This fixes 50Q, 67Q, POTT and FID in Haddadi's and TR81's cases, but needs k = 6 for 50Q, and Haddadi warns it may fail when the line angle is far from 90° and I2 is capped.
- *Distrust the IBR* (SEL): raise the 32Q enable thresholds to 1.25·IMAX, fall back to 32V, undervoltage, timers and communications. This buys security at the cost of about 4× less Rf coverage, lower weak-end dependability and seconds-long clearing without channels.

Zero-sequence elements fed by grounded interconnection transformers are the universally preferred ground-fault fallback.

**What they leave open for our topic.**
- Every study is at 138–315 kV with long, high-X/R lines, a single IBR plant and Rf ≤ 5 Ω. None treats a distribution feeder with short 2–4 Ω low-X/R lines, Rf = 5–50 Ω (where a V2-proportional law produces little I2), two inverters on one feeder, unbalanced load NS paths, or GFM.
- No one *designs* the injection against the relay's actual Z2F/Z2R/50FP characteristic with margins guaranteed over an uncertainty set. Everything is either synchronous-machine emulation or relay desensitisation.
- The SEL secure settings would ignore an affordable 0.4 pu delta entirely, because I2 must exceed about 0.42·IMAX (my derivation). A designed-delta scheme therefore has to justify conventional thresholds through a security certificate.
- NS-angle coherence (tracking V2's phase) is recognised (PNNL, Part I) but not treated as a design constraint during the first cycles.
- No paper studies 3P faults with an injected NS probe; 32Q is otherwise blind to them.
- No paper studies an IBR disconnection being read as a forward fault, which is our finding (3). WPRC's PSV50 logic is the only transferable baseline for it.

**Implication for novelty.** "Inject I2 so 32Q and phase selection work" is established. It is in grid codes, in TR81's recommendation, and in Haddadi, Azzouz–Hooshyar, Banaiemoqadam and Nasr–Hooshyar. A defensible claim is narrower: an optimisation-designed, current-limit-budgeted, uncertainty-robust delta for single-ended directional supervision and phase selection at distribution inverter buses, including 3P and disconnection events. That claim still has to be checked against the unread on-point files listed under Paper 5.
