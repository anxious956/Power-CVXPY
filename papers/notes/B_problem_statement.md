# Notes: the problem statement

These three documents establish, from three independent directions, the failure mode our project
targets. The Sandia/Siemens/EPRI gap analysis (SAND2024-04848) is the authoritative "what is
unsolved" document: it combines a literature review with 18-22 expert interviews across inverter
vendors, relay vendors, consultants, national labs and utilities, and reports that during current
saturation **most grid-forming (GFM) inverters provide at most 1.1-1.2 p.u. fault current**, that
today's relays are built on an assumption of 5+ p.u. synchronous-machine fault current, and that
for six of the eight protection functions it tabulates there is literally **"No literature found"**
on GFM impact. Li, Wu and Wang (2025) supply the analytical mechanism behind one slice of that gap:
they show that what determines whether negative-sequence directional and phase-selection elements
work is not the inverter's current magnitude but the **X/R ratio of the inverter's current-limiting
control (CLC) output impedance**, and they demonstrate with EMT simulation and CHIL tests that the
popular current-reference-saturation limiters produce impedance angles of -0.5 deg, -51.6 deg and
+36.2 deg (i.e. not inductive) and break those elements outright, while even the "good" highly
inductive virtual impedance still breaks **incremental-quantity** elements. Slane and Mate (2026)
add the survey and field-event framing: SGs spike to 5 p.u. or more, IBRs to roughly 2 p.u. or
less, IBR sub-transient current can reach ~5x rated for a few milliseconds that no grid code
governs, and real cascades (Blue Cut Canyon 2016, ~1,200 MW lost; Iberia 2025) have already been
tied to IBR fault behaviour. Read together they justify the premise of Taylor's auxiliary-signal
approach - if the inverter's natural fault signature is both small and, depending on the vendor's
proprietary CLC, *unpredictable in angle*, then the only robust fix is to make the inverter
deliberately inject a designed, known signal - and they simultaneously warn us that our
"guaranteed separation" claim must be stated against a bounded set of CLC behaviours, not one
assumed inverter model.

---

## 1. Sandia 2024 gap analysis

### Full citation

Ulrich Muenz, Siddharth Bhela, Nan Xue, Abhishek Banerjee (Siemens Corporation, Technology);
Matthew J. Reno, Daniel Kelly (Sandia National Laboratories); Evangelos Farantatos, Aboutaleb
Haddadi, Deepak Ramasubramanian, Amin Banaie (EPRI). *Protection of 100% Inverter-dominated Power
Systems with Grid-Forming Inverters and Protection Relays - Gap Analysis and Expert Interviews.*
Sandia Report SAND2024-04848, Sandia National Laboratories, Albuquerque NM, printed April 2024,
48 pages. Funded in part by ARPA-E award DE-AR0001570, part of the project *PICo-Design:
Protection-Inverter Co-Design for 100% Renewable Power Systems*. OSTI 2429968.

### Problem

Protection schemes have been developed over more than 50 years on the assumption that fault
currents are dominated by synchronous generators. Systems are now appearing (Hawaii, Texas are the
report's named examples) in which power-electronic inverters dominate instead. Synchronous
generators and inverters have fundamentally different dynamics *especially during short circuits*,
which "may render today's protection schemes inadequate."

Specific failure modes the report documents:

- **Insufficient fault current for overcurrent-based devices.** "Due to the physical constraints of
  inverters, IBRs cannot provide enough fault currents to trigger over-current-based protection
  devices." Distance and directional schemes that rely on *overcurrent supervision* are affected by
  the same low current.
- **Missing or mis-angled negative sequence.** Many GFL IBRs installed today still provide only
  positive-sequence fault current. Today's protection is "mostly dependent on negative sequence
  current," so negative-sequence overcurrent may fail to pick up and directional negative-sequence
  elements may malfunction because of "the unconventional negative sequence current angle."
- **Non-sinusoidal fault current.** HW-level blocking and fast switch opening "lead to distorted
  wave forms in the first few cycles"; non-sinusoidal currents "can impact RMS-based protection
  schemes." Measured GFM inverters produced literal square-wave fault currents.
- **Phase selection.** "The phase selection logic for distance protection can be severely impacted."
- **IBR trips before protection does.** "IBRs usually trips before protection devices due to the
  fastness of IBR response." Utilities with high solar penetration report that faults typically
  occur during storms at night, and during such events IBRs trip before system protection does.
- **Post-fault problems.** Oscillations observed in the field after a fault was cleared, "esp. after
  inverters came out of current-limiting mode"; inverters then trip as a consequence of those
  oscillations. Momentary cessation is a documented ongoing problem (also in NERC reports).
- **Power-swing false trip, field observed.** A BESS IBR responded so fast to a frequency signal
  that "power swing relays detected the high active power rise and opened the line leading to a
  false trip."
- **Fault recovery / resynchronization.** Functional Acceptance Testing shows issues with voltage
  recovery after fault clearing; inverters "do a ramp after fault is cleared (similar to a
  blackstart)" unlike synchronous machines.
- **Under-voltage protection.** One expert's blackstart tests and protection studies "have shown
  that under-voltage protection would not work properly."

### Method

Not simulation and not new hardware experiments by the authors. It is a **literature review plus
structured expert interviews**, conducted Spring 2023, in two parts: (a) FRT behaviour of GFM IBRs,
(b) response of state-of-the-art protection relays to GFM fault currents/voltages. Section 2.3
summarizes *other people's* hardware measurements.

- Interviews: the report states 18 experts in one place and 22 in the other. **Note the internal
  inconsistency:** Section 2.2 says "We interviewed a total of 18 experts... Of the 22 total expert
  interviews 5 were conducted only within Siemens"; Section 3.2 says "We interviewed a total of 22
  experts... Of the 18 total expert interviews 5 were conducted only within Siemens." The two
  numbers are swapped between sections; the acknowledgements list 21 named individuals plus
  "EPC Power." Safe statement: **roughly 18-22 interviews, 5 of them Siemens-internal under NDA.**
- Organizations interviewed: Electranix, Sandia, EPC Power, Siemens PTI, Siemens Gamesa, Southern
  Company, Quanta, ETAP, GE, Hickory Ledge, RTE France, Dominion Energy, Hawaiian Electric.
  (Acknowledgements also name Clemson, U. Toronto, U. Wisconsin-Madison, NERC.)
- Measurement method used in the cited hardware work: **not** PHIL. Because synchronizing a GFM IBR
  with a grid simulator in PHIL is difficult, all cited test results were obtained by connecting the
  inverter to a **controllable load bank** and applying load steps much larger than the inverter
  rating - e.g. a 500-kW load on Phase A of a 100 kVA GFM IBR, which produces a response similar to
  a single-line-to-ground fault.
- Tools discussed (not run): PSCAD/EMTDC for EMT, Aspen and PSS/CAPE for phasor-domain protection
  studies, PSS/E + PSS/CAPE and ETAP as the combined tools industry actually uses.

### Key findings with NUMBERS

**Inverter fault current**

- "During saturation, most GFM inverters provide at most **1.1-1.2 p.u. fault current**." (This is
  the single most quotable number in the report and is exactly the premise of our project.)
- Semiconductor-driven current magnitude limit: sustained phase current "should not exceed its
  maximum allowed limit, e.g., **1.2-2 p.u.**"
- One cited instantaneous-limiter implementation needs an inverter with a relatively large maximum
  current limit, "**e.g., 2 p.u. in [22]**," because conservative limits in alpha-beta/dq frames
  reduce capacity utilization.
- Expert consensus on what *should* be required: "GFM IBRs should still be required to provide,
  e.g., **1.5 p.u. current over 15-30 cycles** during faults and protection system should adjust to
  these lower overcurrent limitations."

**Hardware measurements of GFM fault response (Section 2.3)**

- Two single-phase split-phase 120/240 V GFM inverters from different manufacturers: **both output
  square-wave current during the fault** (raising total magnitude but injecting harmonics).
  Manufacturer A: fault applied at 0.1 s, calculated RMS current goes to **2.25 p.u.**
  Manufacturer B: fault applied at 0.5 s, RMS current goes to **1.3 p.u.**
- Three-phase GFM #1 (three single-phase inverters, master + two slaves) injected **positive,
  negative and zero sequence square-wave currents** during an SLG fault created by applying a
  **6 p.u. load** to Phase A; positive, negative and zero sequence currents all equal, as expected
  for SLG.
- Three-phase GFM #2 could not source zero sequence (used a delta-wye transformer for the
  zero-sequence path) and injected **sinusoidal** positive and negative sequence current during a
  high-impedance line-to-line fault; positive and negative sequence equal, as expected for L-L.
- Model validation: EMT models of both DUTs reproduced the hardware behaviour closely.
- Phase-angle jump test on a 3-phase GFM using a grid simulator: the jump "pulls large amounts of
  current from the GFM IBR," but the inverter **stabilizes within 10 cycles**.

**IEEE 2800-2022 numbers quoted by the report**

- Unbalanced faults: incremental negative-sequence current must **lead** the POC negative-sequence
  voltage phasor by **90-100 deg** for full-converter IBR units, **90-150 deg** for type III WTGs.
- **The standard does not specify the magnitude** of the injected incremental positive/negative
  sequence currents. (Important for us: the magnitude is a free variable, which is exactly the
  space an auxiliary signal lives in.)
- Step response time: **<= 2.5 cycles** for all IBR units except type III WTGs (unspecified for
  type III). Settling time: **<= 4 cycles** for all others, **<= 6 cycles** for type III WTGs.
  Settling band: max of **+-10%** of required change or **+-2.5%** of IBR unit maximum current.
- Active power recovery after VRT: default recovery time **1 s**, configurable **1.0-10.0 s**,
  restoring to **100%** of pre-disturbance level.
- Under current-limit saturation, incremental positive- and negative-sequence reactive current may
  both be reduced "with a preference of equal reduction in both," and positive-sequence incremental
  reactive current "shall not be reduced below" the negative-sequence one.

**Relay impact evidence (Section 3.1)**

- The single most relevant prior study (ref [58]) modelled three GFM controls: **M1** = dq frame,
  positive-sequence-only current control with current limiter; **M2** = alpha-beta frame with
  current limiter; **M3** = alpha-beta frame with virtual impedance. For phase-B-to-C faults at
  various points on the tie line: with **M1 and M2 the distance relay misoperates** - it measures an
  apparent impedance **in the fourth quadrant for internal faults** and **inside zone 1 for external
  faults** (i.e. it **overreaches**). With **M3 the relay performs much better**, small apparent
  impedance error for most faults, because the virtual impedance X/R matches the line X/R.
- Sandia's critique of that study, which is effectively a to-do list for us: it is simulation-only
  with no analysis of *why*; **only one fault type**; **fault resistance value not stated**;
  IEEE 2800-2022-compliant negative-sequence injection not considered; only a simplified
  apparent-impedance relay model; **no sensitivity analysis** over control or network parameters.
- A second study (ref [59]) on a **46 kV** sub-transmission line looked at inverse-time overcurrent,
  distance and directional elements: no major difficulty found, but the GFM IBR "provided very
  distorted non-sinusoidal" current "that may impact the algorithms in the relays."
- **Table 2 is the headline gap.** Of eight protection-scheme rows, **six say "No literature found"**
  for GFM impact: power swing protection, negative-sequence-based protection, phase selection
  element, communication-assisted protection (POTT/PUTT/DCB/DCUB), memory-polarized zero-sequence
  directional element, and line current differential. Only **line distance protection** has GFM
  literature (refs [58], [85]) and **traveling wave protection** is reported as essentially immune
  ("inverter controls do not respond fast enough to have any impact on the traveling wave arrival
  times").
- Line current differential, GFL findings: "traditional slope-based LCD seems to be immune to the
  IBR fault behavior," but "**alpha-plane LCD is prone to misoperation**" because of lower fault
  current amplitude and varying current angle.
- Named real-world event: the **NERC-reported Odessa, TX event (2021)**.
- Of the four utilities interviewed, **none use out-of-step protection or power swing blocking
  except for generator protection** - yet all are concerned about power swings.

**Quantified-ish qualitative results worth quoting**

- Mode switching: "Most experts ... agreed that mode switching from GFM into GFL or GFL FRT should
  be avoided," because it "is prone to oscillations and chattering between operation modes of
  different IBRs."
- Zero sequence: experts agree it is "still preferable to provide zero sequence current from
  transformers instead of from GFM IBRs" (delta-Y high-side transformers are a common
  interconnection requirement, and because most faults are SLG this mitigates most mis-operations).
- Adaptive protection is technically attractive but "require[s] communication overhead ... and are
  therefore not preferred by some utilities. The preferred solution from at least one utility was to
  have **one protection setting that covers all operating conditions**."
- Load encroachment: expert responses were "mixed and inconclusive."

### Stated open problems / gaps

The report's Summary and Conclusion states there is "hardly any literature or knowledge on" the
following **seven knowledge gaps** (reproduced in substance, in the report's own order):

1. **Measurements of fault currents generated by GFM IBRs** - with very few exceptions, those in
   Section 2.3.
2. **FRT strategies for GFM IBRs with a focus on the correct operation of protection relays** from a
   system-protection perspective.
3. **Protection relay functions that respond correctly to fault currents measured in IBR-dominated
   systems**, including during different GFM operating modes such as **black start**.
4. **Interaction between GFM and GFL IBRs during and after faults** and its impact on the protection
   system.
5. **Accurate models for GFM IBRs and for protection relays** for system protection studies.
6. **Tools for protection studies in IBR-dominated systems.**
7. **Input for future protection standards.**

It then states that existing literature is concentrated in three adjacent-but-different places:
(a) system protection for **GFL** IBRs, not GFM; (b) FRT strategies for GFM IBRs pursued for
**voltage balancing, transient stability, synchronization or grid-code compliance** but **not from a
system protection perspective**; (c) protection for inverter-dominated systems studied only for
**microgrids** and for **offshore wind farms radially connected to an HVDC terminal**.

Additional gaps stated elsewhere in the report:

- **Tooling gap (Section 3.2 Q7).** EMT (PSCAD) is necessary to analyse GFM fault behaviour, but
  "running EMT simulation is time consuming and is not a feasible solution for large scale GFM IBR
  penetration and better tools are needed." Industry wants accurate GFM models (especially FRT and
  current-limiting behaviour) inside **phasor-based** tools like Aspen and PSS/CAPE, and wants
  **commercial relay libraries inside PSCAD** (generic relay models exist, an extensive commercial
  library does not). Several vendors have co-simulation interfaces with PSCAD but **none of them are
  currently using this functionality**.
- "It is unclear whether [standardized generic GFM fault performance] would work also for distance
  protection schemes" even if it works for overcurrent.
- Negative sequence: "the **full extent of IBR negative sequence current injection on traditional
  protection schemes is still unknown**, especially when the penetration of IBRs is significantly
  high throughout the interconnection." Also: increased negative-sequence injection reduces
  available positive-sequence injection, with unknown consequences.
- Power swing / ROCOF / UFLS: "More studies are required to characterize the impact" (stated three
  separate times in Table 3).
- Standards gap: "There is a **lack of standards for the integration of energy storage systems or
  inverters with GFM controls**." IEEE PSRC working groups C32 and C45 are cited as work in progress.
- Open items from interviews: it is "unclear how BESS GFM should behave during fault if it is in
  **charge** state"; experts "have not seen existing cases in which GFM IBR connected to transmission
  system trips"; ratio between positive- and negative-sequence current "should be tunable and
  controlled based on operating condition" (identified as a gap on the operational side).
- The explicit call to action: "**To avoid hardware overdesign, it will be imperative to co-design
  inverter controls and system protection schemes.**"

### Relevance to our project

- **WP1 (CVXPY design tool)** - strongest. This report *is* the justification for the design tool.
  1.1-1.2 p.u. is the number that makes the separation problem non-trivial; 1.5 p.u. over 15-30
  cycles is the number the experts want, so our auxiliary signal magnitudes should be reported
  against both. IEEE 2800 not specifying the injected magnitude means the auxiliary signal is a
  *legal* design freedom, while the 90-100 deg lead requirement and the 2.5-cycle step / 4-cycle
  settle times are hard constraints that belong in the CVXPY model. The "one protection setting that
  covers all operating conditions" utility preference argues directly for our bounded-set /
  worst-case formulation over adaptive settings. The Table 1 comparison of current limiters gives us
  the uncertainty set over inverter behaviour we should bound.
- **WP2 (EMT simulation)** - strong. The Sandia critique of ref [58] is a ready-made experimental
  design for us: sweep **multiple fault types**, **report the fault resistance**, include an
  **IEEE 2800-compliant negative-sequence injection** control, use a **real relay characteristic not
  just apparent impedance**, and do a **sensitivity analysis** on control and network parameters.
  Doing exactly that is a defensible contribution because the report says nobody has. The measured
  square-wave / harmonic fault currents and the 10-cycle phase-jump settling time are model
  fidelity targets. Gap 5 and 6 (models, tools) also sit here.
- **WP3 (relay-side detection)** - strong. Gap 3 is literally "protection relay functions that
  respond correctly to fault currents measured in IBR-dominated systems." Table 2's six
  "No literature found" rows tell us which detectors are un-benchmarked against GFM sources.
  The note that non-sinusoidal current breaks RMS-based schemes argues for time-domain / Kalman /
  learned detectors over phasor RMS elements, and the alpha-plane LCD warning tells us which
  baseline is fragile.
- **WP4 (embedded latency)** - moderate. The 2.5-cycle step-response and 4-cycle settling
  requirements of IEEE 2800, and "IBRs usually trip before protection devices due to the fastness of
  IBR response," set the latency budget our embedded detector must live inside. Traveling-wave
  protection being unaffected because inverter controls are too slow marks the fast end of the
  time-scale axis.

### What to cite it for

> A 2024 Sandia/Siemens/EPRI gap analysis based on a literature review and interviews with roughly
> twenty industry experts reports that during current saturation most grid-forming inverters supply
> **at most 1.1-1.2 p.u. fault current**, far below the 5+ p.u. that conventional protection
> assumes, and finds **no literature at all** on grid-forming inverter impact for six of the eight
> protection functions it surveys - including negative-sequence, phase-selection and
> communication-assisted schemes.

> The same report names, as an explicit knowledge gap, the absence of "protection relay functions
> that respond correctly to fault currents measured in IBR-dominated systems," and concludes that
> "to avoid hardware overdesign, it will be imperative to **co-design inverter controls and system
> protection schemes**" - which is precisely what auxiliary-signal injection does.

---

## 2. Li, Wu and Wang 2025 - impact of GFM inverters on protective relays

### Full citation

Yifei Li, Heng Wu, Xiongfei Wang. *Impact of Grid-Forming Inverters on Protective Relays: A
Perspective for Current Limiting Control Design.* arXiv:2505.04177, 2025 (PDF produced 7 May 2025).
**Caveat: the PDF itself carries no journal/conference name, volume or DOI** - it is an
IEEE-formatted manuscript. It should be cited as an arXiv preprint unless the team confirms a
published venue. (Wu and Wang are at Aalborg University / KTH in their other work; affiliations are
not printed on this PDF either.)

### Problem

Protective relays use **supervising elements** - directional elements and phase selection elements -
to decide fault direction and fault type before the distance element is allowed to trip. These
elements rest on two preconditions, stated explicitly by the paper:

- (a) the **effective impedances** seen from the relay point are **highly inductive**;
- (b) the **equivalent source dynamics remain nearly unchanged** in the first few cycles after fault
  inception.

In a synchronous-generator system both hold, so the negative- and zero-sequence angle
(voltage-to-current) sits near **-90 deg** for a forward fault and near **+90 deg** for a reverse
fault. The paper's failure mode: a GFM inverter's **current limiting control (CLC)** *rewrites the
inverter's output impedance within a cycle or two of fault inception*, and depending on which CLC
the vendor implements, the **negative-sequence output impedance is resistive or has an entirely
undefined angle**. Precondition (a) is violated, the measured angle lands outside the element's
operating band, and the directional and phase-selection elements make the wrong call. Separately,
because the inverter is current-limited, the fault current is close to the pre-fault current
(I1 ~ Ipre1) - unlike an SG where I1 >> Ipre1 - which breaks precondition (b) and therefore breaks
the **incremental-quantity** elements even when the CLC *is* inductive.

Crucially, the paper shows that the slow **power control** (droop/VSM outer loop) is *not* the
problem - it behaves much like an SG. The CLC is the problem.

### Method

Three layers, in order:

1. **Analysis.** Sequence-network and pure-fault (superposition) network models derived with
   symmetrical components and Kirchhoff's laws, for a bcg fault on a single-GFM two-bus system,
   deriving the angle conditions phi2, phi0, delta-phi1, delta-delta-21, delta-20 and the added
   impedance term Zad that distinguishes the GFM case from the SG case.
2. **EMT simulation** in **PSCAD/EMTDC**.
3. **Controller hardware-in-the-loop (CHIL)** on **three Plexim RT BOX 3 units** - one running the
   GFM control, one running the IBR/plant model, one running the relay algorithms - with an analog
   board, Ethernet switch, oscilloscope and workstation.

CLC variants compared: current-reference-saturation family (**circular limiter**, **priority-based
limiter**, **instantaneous limiter**) versus the **virtual impedance / virtual admittance** family
at different X/R ratios. Same CLC strategy applied to positive and negative sequence for simplicity.
Note the paper applies a **deliberate time delay to the protective elements** to skip the transient
right after fault inception, and says performance during that fluctuation period is left as future
work.

**Extraction caveat: every numbered equation (1)-(15) in this PDF is a floating image and came out
empty in text extraction.** The equations for phi2/phi0, delta-phi1, the phase-selection angle
relations, the internal voltage expressions, the effective-impedance expression (7), the output
impedance (8), virtual admittance (9)/virtual impedance (10), and the Zad derivation (14)/(15) are
**not** reproduced in these notes. If we need them, re-open the PDF visually.

### Key findings with NUMBERS

**Negative-sequence output impedance angle under current-reference saturation (PSCAD, ag fault)** -
Fig. 12, the paper's central number:

| Limiter | Angle of negative-sequence output impedance Zv2 |
|---|---|
| **Circular** | **-0.5 deg** (essentially purely resistive) |
| **Instantaneous** | **+36.2 deg** |
| **Priority-based** (active current only) | **-51.6 deg** |

None is near the +90 deg / inductive value the relay needs. The paper's conclusion is blunt: all
current-reference-saturation methods "should not be employed in practice."

**Virtual impedance X/R sweep (PSCAD, bolted bcg fault at m = 0.5)** - Fig. 13:

- **nX/R2 = 0.1**: phi2 = **-152.1 deg**, delta-20 = **-51.7 deg** - **both outside** the operating
  bands, element misoperates.
- **nX/R2 = 20**: phi2 = **-92.3 deg**, delta-20 = **-5.5 deg** - **both inside** the bands, element
  works. (-92.3 deg is within 2.3 deg of the ideal -90 deg.)

**Incremental-quantity elements fail even with good virtual impedance** - Fig. 14, ag fault at
**m = 0.01** with fault resistance **Rg = 30 ohm**, highly inductive virtual impedance triggered:

- angle(delta-v1 / delta-i1) = **-31.7 deg** (should be ~-90 deg) - a **58 deg** error.
- **Discrepancy in the source:** the Fig. 14 label reads **angle(Zad) = 8.1 deg** while the body text
  for the same figure says "Due to angle-Zad = 4.4 deg." One of the two is a typo; the paper does not
  reconcile them. Either way Zad is nowhere near the -90 deg that would preserve the SG behaviour.

**Element operating bands / settings quoted** (useful as our detector baselines):

- Directional: forward fault identified when the angle is **around -90 deg**, reverse when **around
  +90 deg**; the non-operating angle phi_non is "typically set between **30 deg and 60 deg**."
- Phase selection bands: **+-15 deg for delta-delta-21**, **+-30 deg for delta-20**.
- Active power controller bandwidth "typically limited **below 5 Hz**"; reactive power controller
  output "constrained to around **1 p.u.**"; negative-sequence internal voltage reference Eref2 set
  to **0**.

**CHIL results** (Fig. 16, bolted bcg at m = 0.5; Fig. 17, ag at **m = 0.01, Rg = 20 ohm**):

- Circular limiter: phi2 and delta-20 **outside** their bands - confirms the analysis.
- Highly inductive virtual admittance and virtual impedance: phi2 and delta-20 **inside** their
  bands - elements operate reliably.
- Incremental elements, ag fault: with the circular limiter, delta-phi1 and delta-delta-21 both
  **outside** band. With highly inductive **virtual admittance**, still **outside** band. With highly
  inductive **virtual impedance**, delta-delta-21 **outside** band and delta-phi1 only **approaches
  the boundary** of its band. So incremental elements fail in all three cases.

**Test system parameters (Table II)** - directly reusable for our WP2 model:

| Symbol | Meaning | Value |
|---|---|---|
| vg | Grid voltage (L-L, peak) | **220 kV (1.732 p.u.)** |
| f1 | Grid frequency | **50 Hz** |
| S | Rated power | **100 MW (1 p.u.)** |
| n | Transformer turns ratio | **33 kV / 220 kV** (delta-Y0) |
| vdc | DC-link voltage | **40 kV** |
| l | Transmission line length | **100 km** |
| Zl1/l | Positive-sequence line impedance | **0.03 + j0.34 ohm/km** (X/R ~ 11.3) |
| Zl0/l | Zero-sequence line impedance | **0.18 + j1.19 ohm/km** (X/R ~ 6.6) |

**Structural finding on zero sequence:** the delta-Y0 transformer **bypasses GFM control for
zero-sequence quantities**, so the zero-sequence effective impedance Ze0 consists only of the
transformer leakage impedance and is mainly inductive. Therefore **zero-sequence-only supervising
elements are unaffected by the CLC** - but they are "susceptible to mutual coupling from adjacent
circuits" and are **absent entirely during phase-to-phase faults**. This matches the Sandia
interviews, where utilities rely on delta-Y transformers for exactly this reason.

### Stated open problems / gaps

- The authors frame their own motivation as the gap: "the impact of CLC on the reliability of
  protective relays, especially supervising elements, **remains an open issue**," and prior work
  "mainly derived from numerical simulations ... offer limited analytical insights."
- The paper **cites the Sandia report (ref [22])** as evidence that the field is still focused on
  current-reference-saturation methods despite this problem being "evident from a protection
  perspective" yet "underrecognized in literature."
- **Explicitly deferred:** "this paper does not study the performance of supervising elements during
  the fluctuation period" (the first few cycles after fault inception, before their applied time
  delay). They call it "an interesting topic for future research." **This is a directly open door
  for our project**, because an auxiliary signal acts exactly in that window.
- They do not resolve what to replace incremental-quantity elements with. Their recommendation is
  negative: "the incremental quantity-based supervising elements **should not be directly used**."
- They assume the same CLC is applied to positive and negative sequence "for simplicity" - the
  mixed case is unstudied.
- Vendor CLC is proprietary, so the actual X/R ratio in a deployed inverter is generally unknown to
  the relay engineer. The paper does not address that, but it is the practical consequence.

### Relevance to our project

- **WP1 (CVXPY design tool)** - very strong, and it should change the formulation. The paper proves
  that the inverter's fault-time output impedance angle is a *design variable spanning at least
  -51.6 deg to +36.2 deg* depending on CLC. That is a concrete, cited, numeric **uncertainty set**
  our bounded-set model should carry, alongside fault location, fault resistance, remote infeed and
  noise. It also gives us a strong argument for our approach over the paper's own recommendation:
  their fix is "mandate highly inductive virtual impedance in every inverter," which requires
  changing every vendor's proprietary control; ours adds a signal on top of whatever CLC is present.
- **WP2 (EMT simulation)** - very strong. Table II is a ready-made 100 MW / 220 kV / 100 km /
  delta-Y0 PSCAD test system with published line impedances, and Figs. 12-14 give **exact numbers to
  reproduce as a validation target** (-0.5 / +36.2 / -51.6 deg; phi2 = -152.1 vs -92.3 deg;
  delta-20 = -51.7 vs -5.5 deg). If our EMT model reproduces those three limiter angles, the model
  is credible. Note the paper is 50 Hz - we will need 60 Hz for a US-facing study.
- **WP3 (relay-side detection)** - very strong, and it re-scopes the baseline. Our conventional-element
  baseline must include a **negative-sequence directional element (phi2, band around -90 deg with
  phi_non 30-60 deg)**, a **zero-sequence directional element (phi0)**, and **phase selection on
  delta-delta-21 (+-15 deg) and delta-20 (+-30 deg)** - not just a mho distance characteristic. It
  also warns us off a tempting baseline: **incremental-quantity detectors are shown to fail even
  under the "good" CLC**, so if a learned or Kalman detector using incremental quantities works in
  our study, we must check we have not accidentally learned the specific CLC.
- **WP4 (embedded latency)** - moderate. The paper's use of a time delay to skip the post-inception
  transient is the latency question restated: how early can a detector decide? Their CHIL topology
  (separate real-time boxes for control, plant and **relay algorithm**) is close to the architecture
  we would want for an embedded-latency measurement.

### What to cite it for

> Li, Wu and Wang show analytically and confirm in PSCAD and controller-hardware-in-the-loop tests
> that the reliability of negative-sequence directional and phase-selection elements depends not on
> the magnitude of the inverter's fault current but on the **X/R ratio of its current-limiting
> control**: the circular, instantaneous and priority-based reference-saturation limiters give
> negative-sequence output impedance angles of **-0.5 deg, +36.2 deg and -51.6 deg** respectively,
> and drive phi2 to -152.1 deg where a highly inductive virtual impedance keeps it at -92.3 deg.

> They further show that **even with a protection-interoperable, highly inductive current-limiting
> control, incremental-quantity supervising elements still malfunction** - measured
> angle(delta-v1/delta-i1) of -31.7 deg where -90 deg is required - and conclude that such elements
> "should not be directly used" in grid-forming systems.

---

## 3. Slane and Mate 2026 - impact of IBR on protection of the electrical grid

### Full citation

John Slane and Adam Mate. *Impact of Inverter-Based Resources on the Protection of the Electrical
Grid.* IEEE/IAS 62nd Industrial & Commercial Power Systems (I&CPS) Technical Conference, May 2026.
Manuscript submitted 9 Jan 2026; current version 21 Mar 2026. arXiv:2603.27816v1 [eess.SY],
DOI 10.48550/arXiv.2603.27816, CC BY 4.0. Authors: Norm Asbjornson College of Engineering, Montana
State University, Bozeman MT; Mate also with the Analytics Intelligence and Technology Division,
Los Alamos National Laboratory. 11 pages (7 pages body + references).

### Problem

A survey-level statement of the same failure mode, with more emphasis on **field events, grid codes
and modelling tools** than on relay internals. The core failure: the grid was built assuming SGs
provide inertia, voltage regulation, and a large, bus-voltage-independent fault current. IBRs
provide none of these the same way, so "relatively minor faults [can] turn into cascading failures."

Specific failure modes documented:

- **Undercurrent for protection pickup.** SG short-circuit current rises to **5 p.u. or more** and
  protection uses that overcurrent as a reliable fault indicator; an IBR "may only contribute
  approx. **2 p.u.**" because of current limiting (and elsewhere "a current spike of 2pu or less").
  "Such limited current can prevent protection systems from detecting the fault." Explicitly:
  "the lower current response of an IBR is a primary reason for protection devices to fail to engage
  in the event of a fault."
- **Bus-voltage dependence.** "The fault response of an SG is essentially independent of the bus
  voltage to which it is connected. This is not the case for GFLIs, whose control algorithms use the
  bus voltage as an input." Named as a second key cause of protection misoperation.
- **Sub-transient overcurrent that no code covers.** Inverter steady-state fault current is limited
  to the saturation current of the power electronics, but **sub-transient current can rise to
  approx. 5 times rated current**. Grid codes "provide guidance only for the transient response of
  IBRs, not for their sub-transient behavior." Negligible for one unit; as IBR share rises, "the
  collective sub-transient response of many units can become significant" and "may exceed the design
  limits of existing protection systems, causing **some relays to operate prematurely**."
- **Momentary cessation cascades** (Blue Cut Canyon, below).
- **Phase-angle jumps.** Faults cause instantaneous voltage phase jumps; SGs have built-in damping,
  IBRs do not. The jump "can disrupt an inverter's PLL, causing frequency or voltage dips/spikes, or
  even a complete current collapse and inverter disconnect," with current "unstable (or lost
  entirely) for **several seconds**."
- **Fault-type classification (FTC) failure.** Distance relays commonly use FTC based on per-phase
  voltage phase-angle differences or symmetrical-component current magnitude differences. Citing
  Khan et al. (2022), simulated scenarios show **FTC cannot correctly identify a fault** once IBRs
  are added. Even *with* German-grid-code negative-sequence injection, "in some instances the
  negative sequence current injection is sufficient for FTC to identify the fault correctly, however,
  in other instances it is unable to overcome the inverter's current limiting behavior."
- **GFMI islanding ambiguity.** Unexpected transition to islanded mode "may appear to a utility
  operator as if that section of the grid has gone dark," and the resulting transient "can trigger
  protection systems to engage, potentially creating a fault that would not otherwise exist."
  Safety case: an islanded GFMI reconnecting "could energize sections of the grid unexpectedly"
  while repair crews are working.
- **Model heterogeneity.** "A grid with 10 IBRs may have different control algorithms on each
  inverter," each vendor's control being proprietary IP that changes between models.

### Method

**Literature review / survey only.** No new simulation, no hardware, no interviews. The authors
assembled a corpus of papers published 2000 - early 2025 that directly discuss IBR grid fault
response (163 references), plotted annual publication counts (Fig. 2), and reviewed grid codes
(IEC, IEEE, NERC, German Grid Code) and modelling tools (OpenDSS, the LANL InfrastructureModels.jl
ecosystem).

**Caveat: Fig. 2 (annual paper counts) is a bitmap and the actual per-year counts are not in the
extracted text.** The text only gives the qualitative shape: a rise **2004-2007** focused on DERs, a
cluster **2011-2014** on wind turbines during faults, and "since 2016" a broad body covering control,
modelling, DER and transmission impacts, and machine-learning-based protection. The authors state
the collection "is not exhaustive."

Also note a probable error in the text: it names "the **National Laboratory of the Rockies (NLR)**"
as a leading institution alongside EPRI and SEL; the cited references under that label
([9], [25], [49]) are all **NREL** publications. Treat this as a typo, and cite NREL if we use it.

### Key findings with NUMBERS

- **SG fault current: 5 p.u. or more.** **IBR fault current: approx. 2 p.u. or less.** (Note this is
  a survey-level figure and is *higher* than the 1.1-1.2 p.u. Sandia reports from expert interviews
  for GFM inverters specifically. Worth flagging in our writeup - the 2 p.u. number is closer to the
  hardware capability, the 1.1-1.2 p.u. number is what GFM inverters actually deliver.)
- **Sub-transient IBR fault current: approx. 5x rated current**, lasting "only a few milliseconds"
  (ref [48], Popadic/Dumnic/Strezoski 2020).
- **2016 Blue Cut Canyon fire, California.** Faults cleared rapidly, "within **four cycles**
  (approx. **70 ms**)," yet multiple PV inverters entered momentary cessation; each took **several
  seconds** to recognize stable grid conditions before reconnecting. "At one point the grid lost
  nearly **1,200 MW** of generation," causing a grid-wide voltage dip that cascaded to other PV
  installations. IEEE 2800 came **six years later** (2022).
- **2025 Iberian blackout** (28 April 2025): system-wide blackout across Spain, Portugal and parts
  of France. Root cause "still under investigation at the time of writing," but "the first generators
  to go offline were several wind and solar units in Spain, followed shortly by a surge in load on
  distribution networks that appears to be linked to rooftop solar generators going offline."
- **NERC PRC-030-1** (in work, not yet enforceable) will require IBRs on transmission and
  distribution to record any unexpected loss of power of "**at least 20 MW and at least 10% of the
  plant's gross nameplate rating, occurring within a 4 second period**." Companion standards:
  **PRC-028-1** (disturbance monitoring and reporting for IBRs) and **PRC-029-1** (frequency and
  voltage ride-through, built on IEEE 2800 with identical operating regions and timing).
- **IEEE 2800-2022 Section 7** differences from IEEE 1547: (1) outside all defined regions the IBR
  "**may ride through or may trip**" rather than being required to cease; (2) balanced faults -
  positive-sequence current with reactive current priority, *method of allocating reactive/active
  power not specified*; unbalanced faults - negative-sequence current proportional to per-unit PCC
  voltage and **leading PCC voltage by 90-to-100 degrees**.
- **IEEE 1547** was made the US national standard by the **Energy Policy Act of 2005**; latest
  revision **2018**; Section 6 defines the voltage/frequency zones. **IEEE 2800 (2022) is NOT
  mandatory** for US system operators "unless the local or state governing body ... mandates it."
- **Recloser timing:** breakers reclose "after a few grid cycles (on the order of milliseconds)" and
  lock out "after a handful of times."
- **IEEE 2800 escape hatch quoted verbatim, Section 7.2.2.3.2:** "If requested by the [transmission
  network] owner, and mutually agreed with the IBR owner, the IBR unit may operate in **active
  current priority mode** for both the high- and low-voltage ride-through events." The authors flag
  this as a source of unpredictable variety in IBR fault response.

**Tool findings (Section IV)** - the most actionable part for WP2:

- **OpenDSS** (EPRI): fault object is an impedance connected to two nodes or one node and ground;
  gives snapshot or dynamic results; can model current limiting and reactive/active current
  priority; can import vendor DLLs; can model both GFLI and GFMI, **but "documentation suggests that
  GFMI models only be used for islanded microgrids."** Limitations: treats an IBR plant as a single
  IBR rather than an array feeding a collector; may not capture an IBR repeatedly entering and
  exiting control modes (which introduces harmonics and unexpected grid conditions).
- **PowerModelsProtection.jl** (LANL, Julia, part of InfrastructureModels.jl with PowerModels.jl and
  PowerModelsDistribution.jl): GFLIs modelled with PQ control and **positive-sequence current
  injection constraints only** - "it does not appear to include options for GFLI negative sequence
  current injection that is now required by certain grid codes." GFMIs use a current-limiting model
  with optional droop. SGs are a voltage source behind **sub-transient** impedance; IBRs use a
  **virtual impedance that does not distinguish sub-transient from transient** - which matters
  because "transient current is limited to the saturation current of the inverter, but sub-transient
  current is only limited by the true internal impedance." Open source, so custom control logic can
  be added.
- **The vendor-DLL practice:** IBR owners supply a DLL giving terminal currents for given grid
  voltage/frequency conditions; operators import it without modelling the inverter. "As the share of
  IBRs on the grid continues to grow ... currently held assumptions on the validity of models and
  simulation results will no longer hold true or will result in lower grid reliability."
- **Why fault modelling is hard:** the non-linearity of inverter control systems requires IBR
  parameters to be modelled **with respect to time**, whereas "traditional load-flow models are not
  time-dependent but state-dependent, which is much more efficient for computers to solve and less
  prone to error." Plet et al. (2010) proposed a load-flow-based multi-IBR fault prediction strategy
  that works, "**however, it only does so for a specific control strategy**."
- IEEE 2800 itself notes all models involve simplifications: "a PV array is rarely modeled down to
  each individual inverter within an IBR plant, rather the entire plant is modeled as a single
  generator," yet in practice within one plant "some IBRs may trip while others do not."

### Stated open problems / gaps

The conclusion names these, in the authors' order of priority:

1. **Grid modelling is "the most pressing"** gap: "the need for operators to have accurate
   information available when conducting fault analysis studies." Specifically, "more detailed
   guidance on IBR fault-ride-through behavior, **including positive and negative sequence current
   injection profiles**, would allow operators to model IBRs more accurately."
2. **Standards are incomplete and unenforced.** "These standards are not yet comprehensive, and it
   is uncertain how well IBR owners will be able to meet them or **how rigorously they will be
   enforced**." "To date, very few grid entities or legislative bodies have set enforceable
   requirements to IBR fault response."
3. **Sub-transient behaviour is ungoverned.** Grid codes "almost exclusively refer to steady-state or
   transient response to a fault"; the sub-transient spike emitted before inverter controls engage is
   not covered.
4. **No GFLI/GFMI distinction and no islanding standard.** "Grid codes generally do not differentiate
   between GFLIs and GFMIs, however, they do not include any standards for inverters switching to or
   from islanding mode."
5. **Modelling tools cannot represent required behaviours.** "Modeling tools vary in their ability to
   represent IBRs, particularly regarding the response characteristics required by emerging
   standards; this makes it challenging to verify the expected performance of both IBRs and the
   associated fault protection schemes."
6. **The penetration-to-reliability relationship is unquantified.** "It is difficult to quantify how
   a given IBR penetration level will affect grid reliability," though loss-of-power faults are
   "likely" to increase with penetration.
7. **Deployment lag.** Research has already produced schemes handling both the sub-transient and the
   current-limited transient response, improved distance-relay algorithms for high-IBR grids, and
   phase-jump handling - "It will be important for these improvements to be **implemented as early
   as possible** to avoid costly disruptions."
8. Simulating faults on grids with IBRs "remains a challenge: expanding on modeling approaches is
   necessary, and then developing best practices or standards (including new models in fault
   simulation tools) so that faults can be predicted and managed with confidence."

### Relevance to our project

- **WP1 (CVXPY design tool)** - moderate. Best used for framing and for constraint sourcing, not
  method. IEEE 2800's 90-100 deg negative-sequence lead requirement and the *unspecified* reactive/
  active allocation method are constraints and freedoms for the design tool. NERC PRC-029-1 mirroring
  IEEE 2800 tells us the constraint set is about to become enforceable in North America, which is a
  good motivation paragraph. The "at least 20 MW and at least 10% within 4 seconds" PRC-030-1
  threshold is a concrete reportable-event definition if we ever need to size "what counts as a
  consequential misoperation."
- **WP2 (EMT simulation)** - strong, mainly as a **tool-selection** argument. It documents exactly
  why we need EMT: load-flow tools are state-dependent, not time-dependent; OpenDSS advises GFMI
  models only for islanded microgrids; PowerModelsProtection.jl has no GFL negative-sequence
  injection and does not distinguish sub-transient from transient impedance. That is a defensible
  paragraph justifying PSCAD/EMTDC (or equivalent) over phasor tools for our study. The 5x-rated
  sub-transient current and the four-cycle/70 ms clearing time are quantities our EMT model should
  reproduce or at least bound.
- **WP3 (relay-side detection)** - moderate. Gives us the FTC baseline description (per-phase voltage
  angle differences, or symmetrical-component current magnitude differences) and a citable claim that
  FTC fails with IBRs even when negative-sequence injection is present. The phase-angle-jump failure
  mode is a good non-fault "nuisance" case our detector must not trip on - i.e. a negative test case
  for the learned detectors.
- **WP4 (embedded latency)** - moderate to strong on framing. The time scales are all here in one
  place: sub-transient spike "a few milliseconds"; fault clearing four cycles / ~70 ms; recloser
  "a few grid cycles"; momentary cessation recovery "several seconds"; PLL disruption "several
  seconds"; PRC-030-1's 4-second window. Our embedded detector's latency budget should be stated
  against the ~70 ms clearing target and the few-millisecond sub-transient window.

### What to cite it for

> A 2026 IEEE I&CPS survey summarizes the core failure mode: synchronous generators supply
> **5 p.u. or more** short-circuit current, which protection systems use as a reliable fault
> indicator, whereas current-limited inverter-based resources may contribute only about **2 p.u.**,
> and "the lower current response of an IBR is a primary reason for protection devices to fail to
> engage in the event of a fault."

> The same survey identifies **accurate grid modelling as the most pressing gap** - noting that
> OpenDSS advises using grid-forming models only for islanded microgrids and that
> PowerModelsProtection.jl offers no grid-following negative-sequence current injection and does not
> distinguish sub-transient from transient inverter impedance - and points to the 2016 Blue Cut
> Canyon event, in which faults cleared in four cycles (~70 ms) nonetheless caused a loss of nearly
> **1,200 MW** of generation through inverter momentary cessation.

---

## Cross-cutting notes for the team

**Numbers that disagree across the three papers - decide which to quote.**

| Quantity | Sandia 2024 | Li/Wu/Wang 2025 | Slane/Mate 2026 |
|---|---|---|---|
| Inverter fault current, steady | **1.1-1.2 p.u.** (measured GFM, expert consensus) | implied by current limit, not quoted | **~2 p.u. or less** |
| Hardware/design current limit | **1.2-2 p.u.** | Ilim (symbolic) | ~2 p.u. |
| SG fault current | 5+ p.u. implied | not quoted | **5 p.u. or more** |
| Sub-transient IBR current | first-few-cycle distortion noted, no number | not studied (delay applied) | **~5x rated** |
| Measured RMS in hardware | **2.25 p.u.** and **1.3 p.u.** (single-phase, square wave) | n/a | n/a |

Recommendation: quote **1.1-1.2 p.u.** as the GFM figure (it is the interview/measurement-based one
and it is the harder case for us), and note the ~2 p.u. survey figure as the design-limit upper end.

**Three things here that should change how we scope the project.**

1. **Angle, not magnitude, may be the real problem.** Sandia says relays fail because current is too
   small; Li/Wu/Wang show that even at the current limit, elements fail because the *angle* is wrong,
   and that the angle depends on a proprietary vendor choice spanning at least -51.6 deg to +36.2 deg.
   Our auxiliary signal should be argued as fixing both, and our bounded-set model should include
   **CLC type** as an uncertainty dimension, not only fault location / Rf / remote infeed / noise.
2. **Incremental-quantity detectors are a trap.** Li/Wu/Wang show incremental elements fail under
   *every* CLC they tested, including the protection-interoperable one. Several of our reference
   papers (Taylor 2026 incremental quantities; the 2022 incremental negative-sequence admittance
   paper; the 2026 incremental-quantity distance protection paper) build on incremental quantities.
   We need to reconcile that explicitly rather than assume it.
3. **The un-studied window is ours to claim.** Li/Wu/Wang deliberately apply a time delay to skip the
   first few cycles and say the fluctuation period is future work; Slane/Mate say grid codes do not
   govern the sub-transient at all; Sandia says the first few cycles are distorted/square-wave. The
   **first few cycles after fault inception is simultaneously the most consequential window and the
   least studied one**, and it is exactly where an injected auxiliary signal would act. That is a
   strong, defensible scope statement for the project.

**Extraction caveats, stated plainly.**

- All numbered equations (1)-(15) in Li/Wu/Wang extracted as empty - they are images. Formulas in
  these notes are described, never reconstructed.
- Fig. 2 of Slane/Mate (annual publication counts) is a bitmap; per-year numbers are unavailable.
- All figures in the Sandia report are images; the numbers above come from the report's prose
  descriptions of those figures.
- Internal inconsistency in Sandia interview counts (18 vs 22, swapped between Sections 2.2 and 3.2).
- Internal inconsistency in Li/Wu/Wang Fig. 14 (angle Zad = 8.1 deg in the figure, 4.4 deg in the
  text).
- The Li/Wu/Wang PDF carries no venue, volume or DOI; cite as arXiv:2505.04177 until confirmed.
