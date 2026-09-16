# Notes: competing and adjacent methods

These three papers bracket Taylor's auxiliary-signal idea from both sides, and between them
they already occupy a lot of the ground a naive novelty claim would try to stand on. Opoku et
al. (2022) is the **passive** extreme: it uses exactly Taylor's chosen signal — incremental
negative-sequence quantities — but only *measures* it, relying on the grid and on grid-code-
mandated negative-sequence injection to supply it, and it reduces to two hand-tuned settings
(a magnitude threshold and a line-angle compensation). Johansson, Xing, N. Taylor and Wang
(2026) is the **analysis** extreme: it builds a general analytical model of how a grid-forming
inverter's current limiter corrupts the pure-fault network that every incremental-quantity
relay assumes, then maps out, by sweep, exactly where an IQ distance element is dependable and
where it is not — which is structurally the same question Joshua Taylor answers with bounded
sets and reachability, but answered deterministically and without any injection or
optimization. Li, Wu and Wang (2025) is the **active** extreme and the most direct competitor:
it uses the inverter as the actuator to fix protection, exactly as Taylor does, but with the
opposite design goal — it reshapes the GFM internal voltage source during the fault so the
inverter *looks like a synchronous generator* to a legacy incremental-quantity relay, rather
than injecting a deliberately distinguishing perturbation. It is validated in CHIL and on 1 kW
hardware. So: the quantity (negative sequence), the failure mechanism (current limiting breaks
superposition), the actuator (inverter control), and the hardware-validation route are all
prior art. What remains genuinely open for Taylor's line, and therefore for us, is the
*set-based* treatment of the unknowns and the *convex-optimization-derived minimal* injection
with a separation guarantee — none of these three papers does that, and none of them even
poses the problem that way.

---

## Paper 1 — Incremental negative-sequence admittance (UCF, 2022)

### Full citation
K. Opoku, S. Pokharel, and A. Dimitrovski, "An Incremental Negative Sequence Admittance Method
for Fault Detection in Inverter-Based Microgrids," University of Central Florida, arXiv
preprint arXiv:2205.02962 [eess.SY], 5 May 2022. 6 pages. Funded by U.S. DOE EERE Solar Energy
Technologies Office, Award DE-EE0002243-2144.

### What problem it solves
Directional fault detection in inverter-based microgrids where (a) fault current is limited to
1.2 pu by IEEE 1547-2018, so magnitude-based overcurrent elements cannot separate fault from
load, and (b) fault current is bidirectional, so legacy radial-feeder coordination misoperates
(sympathetic tripping, protection blinding). Specifically it targets the *sensitivity* of the
negative-sequence directional element (T32Q-type) in the presence of inverter-based DGs, which
supply little negative sequence at their terminals.

### Method
**Passive. Nothing is injected by the authors' scheme.** The relay only measures.

The element is an incremental (superimposed) negative-sequence **admittance**:

- ΔY2 = ΔI2 / ΔV2 = (I2_fault − I2_prefault) / (V2_fault − V2_prefault)   [their eq. (9)]

The whole argument for admittance rather than the conventional superimposed impedance
ΔZ2 = ΔV2/ΔI2 (their eq. (8), taken from Hooshyar & Iravani) is numerical: inverting the ratio
makes the *forward*-fault quantity large rather than small, which they claim improves
sensitivity when the inverter contributes little negative sequence.

Decision logic (their Fig. 5), in words:
1. **Starting/supervision criterion:** proceed only if |I2/I1| > 0.1. This is what blocks
   tripping on unbalanced load and on simulation/control noise.
2. **Magnitude criterion:** require |ΔY2| > Yset, where Yset is set above the maximum value
   seen in normal operation (including unbalanced load).
3. **Angle criterion**, with φ a compensation angle for the protected-line angle:
   - forward fault if 0° + φ < arg{ΔY2} < 180° + φ
   - reverse fault if 180° + φ < arg{ΔY2} < 360° + φ
   For an ideal source and a purely inductive system this degenerates to arg{ΔY2} = +90°
   forward, −90° reverse.

Relies on there *being* negative sequence to measure. The authors explicitly lean on the
German grid code VDE-AR-N 4120, which mandates an injection-based model for IBDGs to supply
negative-sequence reactive current. So the method is a passive detector riding on a
*mandated* injection that someone else specified — it does not design or optimize that
injection.

### Test system and results WITH NUMBERS
- **Simulator:** MATLAB/Simulink.
- **Grid:** a community microgrid. Utility connects at the substation to Bus 1 through a
  300 kVA, 4 kV/0.48 kV transformer. A 442 kWh battery storage unit built from two
  125 kW/kVA inverters sits on Bus 2. Seven commercial loads (six single-phase, one
  three-phase) fed by 120/240 V split-phase and 120/208 V 3P-4W services, each with its own
  rooftop PV inverter (3.8 kW to 43.2 kW AC), each individually islandable. Relays A, B, C at
  Buses 1, 2, 3, all set forward-looking toward the loads.
- **Settings determined by test:** Yset = 10 for relays A and B, Yset = 5 for relay C. φ = 20°
  ("commercial relays set this value typically 20° to 45°"). **Note an internal
  inconsistency:** Section III states φ = 20°, but Case A then evaluates the decision "for a φ
  setting of 30°." Units of Yset are never stated (presumably siemens or per-unit admittance).
- **Fault cases:** only two fault types — B-C-G (line-line-ground) and A-G (single-line-
  ground) — applied at t = 0.2 s, at three locations: F1 (utility side), F2 (Load-7 feeder,
  upstream of relay C), F3 (downstream of relay C).
- **Case A, B-C-G at F1 (should read reverse):** relay A |ΔY2| = 6.89, arg = −98°; relay C
  |ΔY2| = 0.88, arg = −24°; relay B |ΔY2| ≈ 0.3 with a visibly oscillating angle. All below
  the respective Yset, all angles in the reverse sector → correct reverse decisions.
- **Case B, B-C-G at F2 (forward for A and B, reverse for C):** relay A |ΔY2| ≈ 19.8, relay B
  ≈ 17.9, both with arg ≈ 100° → correct forward. Relay C correct reverse.
- **Case C, B-C-G at F3 (forward for all):** relay C |ΔY2| ≈ 48.9, arg = 105° → correct
  forward. Relays A and B also forward, which the authors note means a *coordination* scheme
  is still required (the element gives direction, not selectivity).
- **Case D, A-G faults at F1, F2, F3:** all reported qualitatively correct; no magnitudes
  tabulated.

**What is missing from the numbers, and it matters:** no detection *time* anywhere, no trip
times, no fault-resistance sweep (R_f is never mentioned as a variable), no high-impedance
fault cases, no islanded-mode results, no statistics (no confusion matrix, no success rate
over a population of cases), no three-phase balanced faults, no comparison against a baseline
element. Total case count reported is roughly six fault scenarios. This is a feasibility
demonstration, not an evaluation.

### Assumptions and stated limitations
- Explicitly restricted to **unbalanced faults**, justified as "95 percent of distribution
  system faults." A balanced three-phase fault produces no negative sequence and this element
  simply does not exist for it. The authors do not address this case at all.
- Thresholds are **not generalizable**: "it is important, however, for each system to be
  evaluated to determine proper threshold for the magnitude and phase of this element." Default
  Z2 settings guidance for traditional systems cannot be carried over because active
  distribution networks have much more dynamic topology and therefore much wider variation of
  source impedance.
- Threshold must be set for the condition giving the *lowest* negative-sequence impedance seen
  by the relay — an unknown that depends on topology.
- Inverter control action corrupts the impedance estimate: "impedance evaluation should take
  into consideration the variations due to inverter control action."
- Single-phase inverters destabilize arg{ΔY2} (Fig. 8); the element survived only on magnitude
  in that case.
- Settling/response time depends on the inverter: "inverter design must ensure faster action to
  improve settling time for protection decisions," and grid support (grid-connected mode)
  gives faster settling than islanded-ish conditions.
- Performance is explicitly better in grid-connected mode because the grid supplies negative
  sequence. Degradation in islanded 100 %-inverter operation is acknowledged only implicitly.
- The starting criterion |I2/I1| > 0.1 is asserted, never derived or swept.

### Overlap with Taylor's auxiliary-signal approach
- **Same physical quantity.** Both use negative-sequence current as the informative channel.
  We cannot present "negative sequence is the right signal in an inverter-dominated grid" as
  our insight; it is the standing consensus, embedded in IEEE 2800 and VDE-AR-N 4120.
- **Same incremental/superimposed framing.** Both subtract a pre-fault operating point to
  remove load dependence. Taylor's incremental-quantity distance work
  (`Taylor_2026_Distance_Characteristics_Incremental_Quantities.pdf`) shares this exactly.
- **Genuinely different, three ways.** (1) This paper is purely passive; Taylor perturbs.
  (2) This paper handles uncertainty by hand-tuning a scalar threshold per system, tested at a
  handful of operating points; Taylor bounds the unknowns (fault location, R_f, remote
  current, noise) as *sets* and computes the image of those sets in measurement space.
  (3) This paper has no optimization anywhere; Taylor's whole contribution is the convex
  (bilinear-via-duality, CCP/ADMM) program that finds the *minimal* injection.
- **Critical read:** this method's stated weakness — "only a small amount of negative sequence
  may be present at the inverter terminals" — is precisely the gap Taylor's injection fills.
  So this paper is better used as *motivation* for us than as a competitor to beat. It is,
  however, an excellent relay-side detector baseline: cheap to implement, and it will make the
  auxiliary-signal comparison honest, because if ΔY2 already separates the cases at a given
  operating point, injecting anything is wasted power quality.

### What our team must NOT claim as novel because of this paper
1. Using **incremental (superimposed) negative-sequence quantities** for fault detection in
   inverter-based microgrids.
2. Using an **admittance** form ΔI2/ΔV2 rather than an impedance form to improve sensitivity
   with weak negative-sequence sources.
3. A **negative-sequence directional element with line-angle compensation φ** and forward/
   reverse sectors.
4. The **|I2/I1| > 0.1 supervision/starting criterion** against unbalanced load.
5. The observation that inverter fault current limited to ~1.2 pu by IEEE 1547 defeats
   magnitude-based detection. That is the field's opening sentence, not a finding.
6. Demonstrating a negative-sequence element on a **MATLAB/Simulink community microgrid with
   PV and battery inverters**.

---

## Paper 2 — Incremental-quantity distance protection with GFM inverters (KTH + Tsinghua, 2026)

### Full citation
H. Johansson, Q. Xing, N. Taylor, and X. Wang, "Analysis and Enhancement of Incremental-
Quantity-Based Distance Protection With Grid-Forming Inverters," arXiv preprint
arXiv:2604.10129 [eess.SY], 11 Apr 2026. 10 pages. KTH Royal Institute of Technology
(Johansson, Xing, N. Taylor) and Tsinghua University (Wang). Funded by Hitachi Energy and the
Swedish Energy Agency.

> **Name warning for the team: "N. Taylor" here is Nathaniel Taylor at KTH, not Joshua A.
> Taylor at NJIT. Do not cite them as the same person or as a collaboration.**

### What problem it solves
Time-domain incremental-quantity (IQ) distance protection is widely advertised as the fix for
IBR-dominated grids because it works on nonlinear, nonstationary waveforms. The authors point
out the contradiction at the heart of that claim: IQ protection is built on the **superposition
principle** and therefore still assumes a *linear* source, while GFM inverters are strongly
nonlinear during faults because of current limiting. Prior studies of this interoperability
problem are, in their words, "case-specific and numerical studies, leaving the interoperability
issues inconclusive." This paper supplies the missing general analytical model, then uses it to
fix the trip criterion.

### Method
**Passive, relay-side. Nothing is injected.** The inverter control is *not* modified; it is
modelled.

**1. The IQ distance element being analyzed (standard, from Schweitzer/Kasztenny):**
- Incremental quantities by a memory function: Δv_sx(t) = v_sx(t) − v_sx(t − pT),
  Δi_sx(t) = i_sx(t) − i_sx(t − pT), with T = 20 ms the fundamental period and p an integer.
- Incremental voltage drop to the reach point m, per phase and per loop, in words: m·R1 times
  the incremental phase current, plus m·(R0 − R1) times the incremental zero-sequence current,
  plus m·L1 times the time derivative of the incremental phase current, plus m·(L0 − L1) times
  the derivative of the incremental zero-sequence current; the line-line loops drop the
  zero-sequence terms. Derivatives computed by central finite difference.
- **Operating quantity** ψ_op = |Δv_s − Δv_m|, i.e. the magnitude of the incremental voltage
  change *at the reach point*.
- **Restraining quantity** ψ_rst = K·|v_s(t − pT) − v_m(t − pT)|, the memorized pre-fault
  voltage at the reach point, with K ≥ 1 a security bias factor.
- **Trip variable:** the running sum (discrete trapezoidal integral) of (ψ_op − ψ_rst) over
  time. Internal faults make it trend up, external faults and healthy loops make it trend down.
  Conventionally you trip when the running sum crosses a **threshold level**.

**2. The new analytical model (their core contribution).** The GFM inverter's fault-ride-
through is modelled from the power-system side as a *time-varying Thevenin source*: a variable
voltage source Δe_s(t)·H(t) in series with a variable resistance ΔR_s(t) and inductance
ΔL_s(t), with H(t) the Heaviside step at fault inception, and with the fault resistance R_f(t)
also allowed to vary with time. Two current sources equal to the pre-fault inverter current
i_s_pre(t) are placed in parallel with the added impedance so that no current flows through it
before the fault; they cancel at inception, the same way the two pre-fault fault-point voltage
sources cancel. Limit case: ΔR_s or ΔL_s → ∞ gives i_s → 0 and Δi_s → −i_s_pre.

Key modelling insight the team should internalize: a **saturation (magnitude-clipping) current
limiter emulates an adaptive virtual resistance**, whereas a **virtual-impedance limiter
emulates an added impedance at the angle the controller uses** (here, the positive-sequence
line angle, i.e. mainly inductive). Either can model either effect, but one is always the more
direct model.

They then solve the steady-state ("IQ network") equivalent by superposition over three sources
— the pre-fault current source, ΔĒ_s, and the pre-fault fault-point voltage V̄_f_pre — to get
closed-form expressions for the relay-measured ΔĪ_s (eq. 9), ΔV̄_s (eq. 10) and ψ_op (eq. 11).
**These three expressions are heavily garbled by PDF text extraction** (stacked fractions and
overbars collapse) — do not transcribe them from the extracted text; read them off the PDF
pages 5–6 directly if we need them. What survives cleanly and is what matters:
- The ideal, linear-source, solid-fault operating quantity reduces to
  ψ_op,ideal = |−V̄_f_pre · (Z̄_s + m·Z̄_ℓ)/(Z̄_s + m_f·Z̄_ℓ)| and ψ_rst = |V̄_f_pre|, giving the
  clean proof: ψ_op,ideal > ψ_rst ⟺ m_f < m (internal), = ⟺ m_f = m, < ⟺ external.
- With a GFM source and/or resistive fault, ψ_op drops in magnitude **and shifts in phase**
  relative to ψ_rst. The magnitude drop hurts dependability; the phase shift superimposes a
  **100 Hz (second-harmonic) oscillation** on the running sum, hurting both dependability and
  security depending on where the threshold sits.
- Quasi-static validity: ψ_op(t) can be evaluated as a sequence of new steady-state
  equilibria, provided the memory window of eq. (1) still reaches back into the
  pre-disturbance network.

**3. The proposed enhancement.** Replace the running-sum *threshold level* with a **time-based
trip criterion: trip when the running sum has stayed above zero for a consecutive duration of
about 10 ms or slightly longer.** Rationale: the parasitic oscillation has a 10 ms period, so
staying positive for longer than 10 ms is a fast time-domain test of whether |ψ_op| genuinely
exceeds |ψ_rst|, and it is independent of how steeply the running sum accumulates — which is
what varies unmanageably with fault location, R_f and inverter control.

### Test system and results WITH NUMBERS
- **Simulator:** PSCAD/EMTDC for all EMT work; MATLAB for the analytical parameter sweeps.
  Hundreds of PSCAD runs automated by a Python script.
- **Grid:** 66 kV GFM inverter (300 MW nominal) → Δ-Y0 transformer with negligible leakage →
  220 kV → 100 km transposed overhead line, PSCAD frequency-dependent (phase) model → utility
  grid. 50 Hz. Source-to-line impedance ratio SIR = 0.3 for both the GFM output filter and the
  remote grid. Relay at the sending end, **reach m = 80 %** of line length. Sampling frequency
  5 kHz; p = 2 in the memory function; incremental quantities filtered by a 3rd-order
  Butterworth low-pass at 450 Hz cutoff; K = 1 in the restraint.
- **Two GFM controls, both P-f droop power-synchronization control:**
  - **GFM1** — 1.2 pu magnitude saturation current limiter, no angle prioritization; single
    (combined-sequence) control. Emulates an adaptive virtual *resistance*.
  - **GFM2** — separate positive- and negative-sequence control; adaptive virtual impedance at
    the positive-sequence line angle (mainly inductive), acting by reducing the voltage
    reference into the outer voltage loop.
  An SG is used as the linear-source reference case.
- **Fault set:** balanced ABCG only; normalized distance m_f ∈ {0.2, 0.45, 0.5, 0.6, 0.7,
  0.75, 0.81, 0.9, 0.99}; fault resistance R_f ∈ {0, 2, 5, 8, 10, 15} Ω; inception angle 0°;
  pre-fault load 1 pu active power. **54 balanced-fault simulations per source**, so 162 total
  across SG, GFM1, GFM2.
- **Model validation run:** strong sending-end source, then at t = 0 the source impedance
  magnitude is multiplied by 5, the internal voltage magnitude drops 1 pu → 0.33 pu, and a
  10 Ω balanced fault is applied at m_f = 0.2 pu. Analytical steady-state values match the
  PSCAD waveforms. Δv_s settles within a few milliseconds; ψ_op settles in about half a
  fundamental period (≈10 ms); Δi_s carries a decaying DC offset and settles slowest. The
  authors state the closed-form expressions "always matched perfectly" with steady-state
  simulation over the full sweep of source magnitude/angle, source R and L, R_f and location.
- **Dependability, proposed IQ element with GFM2 (virtual-impedance limiter):** dependable up
  to R_f = 15 Ω at m_f = 0.45; R_f = 10 Ω at m_f = 0.6; R_f = 8 Ω at m_f = 0.75.
- **Dependability, proposed IQ element with GFM1 (saturation limiter):** dependable up to
  R_f = 8 Ω at m_f = 0.2; R_f = 5 Ω at m_f = 0.7. Worse than GFM2 near the reach point, but
  still better than quadrilateral for close-in faults.
- **Documented misoperation:** both the IQ element and the quadrilateral element fail for
  GFM1 at m_f = 0.5 with R_f = 10 Ω. This matches the analytical prediction.
- **Security:** the proposed IQ element is secure for every simulated external fault at
  m_f = 0.9 and beyond with GFM2; with GFM1 it is secure at m_f ≥ 0.9 except for R_f = 2 Ω.
  The quadrilateral zone-1 element **overreaches for most of those external faults**, in steady
  state for resistive faults and transiently even for R_f = 0.
- **Head-to-head:** IQ distance is more dependable than quadrilateral for **close-in** faults;
  quadrilateral is more dependable for faults near the reach point. Quadrilateral struggles for
  m_f < 0.2 with resistive faults even under an inductive virtual impedance. For solid balanced
  faults both are dependable everywhere.
- **Speed:** trip speed with GFM2 is "almost unchanged" versus an SG, even though the running
  sums accumulate more slowly. Overall trip/no-trip behaviour of the proposed element with
  GFM2 is described as "near identical to that with an SG" — which the quadrilateral element
  cannot match. No absolute trip time in milliseconds is tabulated anywhere; only the relative
  claim plus the dashed trip markers in Figs. 11–13.
- Analytical dependability/security maps are given in the (ΔR_s, ΔX_s) plane with the 1.2 pu
  injected-current contour overlaid, for nine (m_f, R_f) combinations.

### Assumptions and stated limitations
- **Balanced ABCG faults only**, justified by prior work finding balanced faults the hardest
  case for IQ/GFM interoperability. Unbalanced faults — the 95 % that matter in distribution,
  and the case Taylor's negative-sequence injection targets — are not simulated at all.
- The analytical framework is **steady-state / quasi-static phasor**; transient behaviour is
  only accessible through simulation. The authors acknowledge that ψ_op grows from zero while
  ψ_rst does not, "making it difficult to determine if a fault is internal or external during
  the initial energization of ψ_op" — i.e. the model says nothing useful in the first few ms.
- Both relays "risk overreaching during the transient period of external faults."
- Solid faults assumed, line stray capacitance neglected, line assumed ideally transposed when
  deriving the six loop operating quantities.
- The memory function must still reach into the pre-disturbance network for the whole framework
  to hold — a real constraint on how long the element can be relied on.
- R_f is swept only to 15 Ω. No high-impedance faults.
- Single-ended protection; no communication-assisted schemes.
- The honest central admission: for the *conventional* threshold-based implementation, "tuning
  of its settings is hard to generalize for various sources and faults," because running sums
  "can reach similar values for various internal and external faults due to the superimposed
  100 Hz oscillations" — a threshold cannot discriminate in those cases. This is the motivation
  for their time-based criterion, and it is also an admission that the *state of the art they
  are improving* is fragile.
- Only two GFM control strategies tested; generalization to other limiters is argued from the
  model, not demonstrated.

### Overlap with Taylor's auxiliary-signal approach
- **This is a direct competitor to Taylor's two 2026 papers**, not to the auxiliary-signal
  injection idea itself. It overlaps `Taylor_2026_Distance_Characteristics_Incremental_
  Quantities.pdf` (incremental-quantity distance characteristics under IBR control) and
  `Taylor_2026_Reachability_Time_Domain_Distance_Protection.pdf` (time-domain reachable sets
  of relay voltage and current) almost head-on in subject matter.
- **Same underlying question as Taylor's set approach, answered differently.** Taylor asks:
  given the unknowns as bounded sets, what region of measurements can a fault produce, and
  does it overlap normal operation? Johansson et al. ask: given the current limiter's
  equivalent (ΔR_s, ΔX_s), is ψ_op above or below ψ_rst? Their shaded/coloured region maps in
  the (ΔR_s, ΔX_s) plane, with the 1.2 pu current contour drawn on top, are *visually and
  conceptually* the same object as Taylor's overlapping fault/normal regions. The difference
  is the epistemic status: theirs is a **sweep over a deterministic parameter plane**, so it
  shows where the element happens to work for the cases enumerated; Taylor's is a **computed
  image of a bounded uncertainty set** (Minkowski sums, zonotopes, Farkas' lemma), so it
  claims coverage of *all* admissible unknowns, not just the gridded ones. That distinction is
  our strongest remaining novelty argument in this area, and we should state it in exactly
  those terms.
- **Genuinely different.** No injection, no actuation, no optimization, no minimality, no
  guarantee. The inverter is a passive object of study. The "enhancement" is a relay-side
  timing heuristic.
- **Uncomfortably close in one respect.** They already show that the interoperability problem
  can be *characterized in closed form* as a function of the inverter's equivalent impedance
  change. If we plan to contribute "a model of how inverter control shifts the measurement
  region," it is done, for GFM inverters, balanced faults, and IQ distance.

### What our team must NOT claim as novel because of this paper
1. The finding that **GFM current limiting violates the superposition / pure-fault-network
   assumption** underlying incremental-quantity relays. Stated, modelled and quantified here.
2. Modelling an inverter's FRT/current-limiting behaviour as a **time-varying Thevenin
   equivalent** (variable internal voltage source plus variable R and L), including the
   pre-fault current-source cancellation trick.
3. The result that a **saturation limiter behaves like an added virtual resistance and a
   virtual-impedance limiter like an added reactance**, and that the inductive one is friendlier
   to protection.
4. The **head-to-head comparison of IQ distance against quadrilateral distance with GFM
   inverters**, including the pattern "IQ better close-in, quadrilateral better near the reach
   point, quadrilateral overreaches externally."
5. Identifying the **100 Hz oscillation on the running sums** caused by the ψ_op/ψ_rst phase
   shift, and the consequent unreliability of a fixed running-sum threshold.
6. The **time-above-zero trip criterion** (≈10 ms consecutive) as an alternative to a threshold
   level.
7. PSCAD EMT evaluation of IQ distance on a 100 km, 220 kV line with GFM1/GFM2-style limiters
   over an (m_f, R_f) grid. If we run that grid, we are reproducing, not extending — which is
   fine as a baseline, but must be labelled as such.

---

## Paper 3 — Protection-interoperable fault-ride-through control for GFM inverters (2025)

### Full citation
Y. Li, H. Wu, and X. Wang, "A Protection-Interoperable Fault Ride-Through Control for
Grid-Forming Inverters," arXiv preprint arXiv:2504.21592, 2025. 10 pages. (Author group
associated with Aalborg/Tsinghua/KTH; Xiongfei Wang is also an author of Paper 2.)

### What problem it solves
Incremental-quantity-based **supervising elements** — the directional element and the phase-
selection element that sit in front of the distance element in every real relay — rest on
"compensation theory," which assumes the source's internal voltage source (IVS) and output
impedance are essentially the same during the fault as before it. For a GFM-IBR the IVS is
indeed nearly unchanged (slow-timescale power control), but the **output impedance changes
abruptly** the moment the virtual-impedance current limiter engages. That single change breaks
the assumption, the incremental-quantity angles wander out of their correct bands, and the
supervising elements misoperate. Rather than replace the relays (expensive; the authors cite
the SEL-T400L travelling-wave route as needing 1 MHz sampling), they change the inverter.

### Method
**ACTIVE — but active in the sense of reshaping the inverter's fault response, not injecting a
probing signal.** Nothing is injected on top of the fault response; the internal voltage
reference is *biased* so the relay sees a pre-fault-consistent source.

**Preconditions the supervising elements need** (their summary):
(a) the effective impedance is highly inductive; (b) the difference in source dynamics (IVS and
output impedance) between the fault sequence network and the pre-fault circuit is negligible.

A GFM with a generic virtual-impedance limiter violates (a) if the virtual impedance has
resistive content, and always violates (b). Precondition (a) is handled by making the
current-limiting control use **virtual inductance only** (no steady-state virtual resistance),
so Z_v1 and Z_v2 stay highly inductive and the negative- and zero-sequence elements (φ2, φ0,
δ20) remain correct. Precondition (b) is the real contribution.

**The central idea, in words.** Two ways to restore equivalence:
- (a) Force the *faulted* inverter model to equal the *pre-fault* one, i.e. set
  n·e_ref1 − n²·i1·Z_v1 = n·e_pre1. Rejected as impractical: it holds the terminal voltage at
  its pre-fault value during the fault, which inherently disables overcurrent limiting.
- (b) **Chosen:** force the *pre-fault* model to be equivalent to the *faulted* one, i.e. make
  the pre-fault IVS e_pre1 equal the fault-time IVS e_ref1 in series with the virtual impedance
  Z_v1. Concretely, adjust the internal voltage reference during the fault so that
  **e_ref1 − i_tpre1·Z_v1 = e_pre1**, i.e. e_ref1 = e_pre1 + i_tpre1·Z_v1, where i_tpre1 is the
  *pre-fault* positive-sequence terminal current. That is their eq. (9).
  > **PDF extraction note:** eqs. (1)–(3), (5)–(8), (9)–(13) and (14)–(22) are rendered as
  > images in this PDF and come out of pypdf as blank equation slots. The relation above is
  > reconstructed from the surrounding prose, which states it in words twice ("e_ref1 −
  > i_tpre1·Z_v1 = e_pre1"). **Do not transcribe eqs. (10), (13), (17)–(22) from text
  > extraction — they did not extract at all.** Read pages 4–6 of the PDF directly.

  With this bias applied, the effective incremental impedance ΔZ_e1 becomes highly inductive
  again, the voltage and current at the relay point in the equivalent pre-fault circuit match
  the true pre-fault values, and the pure-fault circuit of the IBR system "closely resembles"
  the SG-based one. In plain terms: **the inverter is made to impersonate a synchronous
  generator as seen by an incremental-quantity relay.**

**Realization — two control modes with explicit switching:**
- *Protection-interoperable mode:* IVS magnitude E_ref1 and angle θ_ref1 taken from eq. (9),
  **open loop**. The active power controller is **frozen** (P1 substituted by P_ref) so the
  P_ref ≠ P1 error does not accumulate in the angle and cause a power transient on fault
  clearance.
- *Normal mode:* conventional closed-loop APC (P-ω droop with virtual inertia H, damping K_pP)
  and RPC.
- **Entry trigger:** I_max ≥ I_th1, where I_max is built from the peak phase currents I_ta,
  I_tb, I_tc and **I_th1 = 1.05·I_N1** (just above nominal), chosen high-sensitivity to protect
  relay reliability.
- **Exit trigger:** either I_max < I_th1 continuously for **t1 = 50 ms**, or the elapsed time
  since fault inception reaches **t_p**, the supervising elements' data-storage window — after
  t_p the memorized "pre-fault" data are stale, the incremental quantities collapse toward
  zero and the supervising elements deactivate anyway.
- **Transient current limiting:** a highly inductive virtual impedance slows the decay of the
  fault-current DC component, so a **transient virtual resistance is applied for at most
  t_r = 50 ms** at inception — and, because that resistance breaks the inductive precondition,
  a matching **t_r time delay is imposed on the protective relay**. So the first 50 ms is
  explicitly not protected by this scheme.
- **Adaptive virtual inductance** X_v1, X_v2 generated from the measured positive- and
  negative-sequence current magnitudes above thresholds I_thX1, I_thX2 with gains K_X1, K_X2,
  through low-pass filters (measurement LPF plus a first-order LPF on the inductance for
  small-signal stability). Only inductances, never resistances, in steady state. K_X1 and K_X2
  are set from the expected maximum |v_tpre1 − v_t1| and V_t2.
- **Transient stability:** open loop during protection mode removes the stability question
  there; on return to normal mode the adaptive fast/slow power control of Wu & Wang is used,
  switching to fast-timescale control when I_t1 ≥ **I_thf = 0.94 pu** to avoid loss of
  synchronism. Shortening t_p shrinks the open-loop window and further reduces LOS risk.

**Magnitude of the "injection":** there is none in the auxiliary-signal sense. What is bounded
is the *current*: the design constraints on Z_v1 and Z_v2 keep the positive- and negative-
sequence currents within I_lim1 and I_lim2, and the measured worst case in the experiments is
**below 1.5 pu**. Note that is higher than the 1.1–1.2 pu usually quoted.

### Test system and results WITH NUMBERS
**Controller-hardware-in-the-loop (CHIL), three RT-Box3 units** — one running the controller,
one the plant, one the relay — with an analog board, oscilloscope, Ethernet switch and
workstation.
- Parameters (Table I): grid 220 kV L-L RMS (1.732 pu), 50 Hz, rated S = 100 MW (1 pu),
  transformer 33 kV/220 kV, v_dc = 40 kV, filter L_f = 5 mH, transformer leakage L_T = 77 mH
  (0.05 pu), line length 100 km, Z_l1 = 0.03 + j0.34 Ω/km, Z_l0 = 0.18 + j1.19 Ω/km, grid
  impedance 200 mH (**SCR = 6.8**).
- **One fault case reported:** a-g fault between bus 1 and bus 2 at **m = 0.01** (essentially
  at the relay), **R_f = 20 Ω**, with t_p artificially set to **1 s** to lengthen the
  observation window.
- **Baseline (conventional power control):** Δφ1 (incremental directional angle) and Δδ21
  (incremental phase-selection angle) **deviate out of their correct bands** — the misoperation.
  Meanwhile φ2, φ0 and δ20 stay correct, because the inductive virtual impedance is already
  enforced and the Δ-Y0 transformer bypasses zero-sequence control.
- **With the proposed FRT:** Δφ1 and Δδ21 **remain inside their bands after fault inception**;
  φ2, φ0, δ20 also remain correct. That is the headline result.
- Directional bands: forward ≈ −90°, reverse ≈ +90°, with a **non-tripping zone of 30° to 60°**
  for reliability. Phase-selection zones extended by **±15° for Δδ21 and ±30° for δ20**.

**Physical experiment, 1 kW scale.** 45 kVA Chroma 61850 grid simulator generating the
disturbances, dSPACE DS1007 running the control. Parameters (Table II): v_g = 86.6 V L-L RMS
(0.816 pu), 50 Hz, sampling 10 kHz, rated 1 kW, grid inductance L_g = 6 mH (**SCR = 4**),
filter L_f = 3 mH.
- *Switching criteria:* v_g dropped to **0.7 pu for 0.2 s**, t_p = 0.3 s. Protection mode
  activates (S_p = 1) on I_max ≥ I_th1; ∠ΔZ_t1 stays close to **−90°** through the fault; S_p
  returns to 0 after S_I has been 0 for **t1 = 50 ms**.
- *Overcurrent limiting:* disturbances of 0.3 s with t_p = 0.2 s — (a) v_g down to **0.1 pu**,
  (b) a **−60° phase jump**. ∠ΔZ_t1 stays near −90°; **fault current stays below 1.5 pu**.
- *Transient stability:* same two disturbances (0.1 pu sag, −60° phase jump, 0.3 s) with
  t_p = 0.2 s; the power angle δ between POC and grid voltage remains stable, no loss of
  synchronism.

**What is missing from the numbers:** one CHIL fault case only, no sweep over fault location or
resistance, no unbalanced fault types beyond the single a-g, no distance-element results at all
(only the supervising elements), no detection-time or trip-time figures, no statistics, no
comparison against any alternative scheme, no islanded or multi-inverter case.

### Assumptions and stated limitations
- **Only supervising elements** (directional + phase selection) are addressed. Whether the
  downstream distance element then reaches correctly is never shown.
- Requires **modifying the inverter's control firmware**. Not a relay-only or grid-side fix, and
  it assumes the inverter vendor will implement it.
- Requires a **highly inductive virtual-impedance CLC**. The authors state plainly that this
  conflicts with transient current limiting (inductive virtual impedance slows DC decay), which
  is why they need the 50 ms transient virtual resistance — and then a **matching 50 ms relay
  time delay**, i.e. the scheme concedes the first 50 ms.
- **Open-loop active power control during the fault** is a transient-stability hazard; they
  mitigate it by freezing the APC, by the adaptive fast/slow control on exit, and by keeping
  t_p short, and they acknowledge the LOS risk explicitly.
- Bounded by **t_p, the relay's incremental-quantity memory window**: after it, the scheme must
  revert regardless of whether the fault has cleared. In CHIL they had to set t_p = 1 s
  artificially to make the effect visible, which is not a realistic setting.
- Needs the pre-fault terminal current i_tpre1 and pre-fault IVS e_pre1 to be available and
  accurate.
- Assumes a **constant DC-link voltage** maintained by a front-end converter or storage.
- Zero-sequence is not controlled at all (Δ-Y0 transformer bypasses it); the zero-sequence
  elements work by accident of topology, not by design.
- Sequence separation is done by all-pass filters, which have their own delay.
- Single inverter against an infinite bus, SCR 6.8 (CHIL) and SCR 4 (bench). No multi-inverter,
  no 100 % IBR case.

### Overlap with Taylor's auxiliary-signal approach
- **This is the closest competitor of the three, and the team should treat it as the one to
  beat.** Both papers accept the same premise: the relay-side fix is expensive and slow to
  deploy, so use the inverter as the actuator. Both intervene only during suspected faults,
  both bound the resulting current, and both are validated (or intend to be) in hardware.
- **Opposite design philosophy, and this is the clean distinction to draw in our report.** Li
  et al. make the inverter **indistinguishable from a synchronous generator** so that the
  *legacy assumption* (compensation/superposition) is restored and legacy elements work
  unchanged. Taylor makes the inverter **deliberately distinguishable** — it injects a
  perturbation chosen so the fault and normal measurement sets separate. Li et al. restore an
  assumption; Taylor engineers a separation.
- **Where Taylor is genuinely different and we can defend it:**
  1. **Uncertainty is explicit and set-valued.** Li et al. have no representation of fault
     location, fault resistance, remote infeed or noise as bounded unknowns. Their argument is
     a single-operating-point circuit equivalence: it either holds or it does not, and they
     verify it at one fault (m = 0.01, R_f = 20 Ω). Taylor computes the reachable measurement
     set over all admissible unknowns.
  2. **Optimization and minimality.** Li et al.'s IVS bias e_pre1 + i_tpre1·Z_v1 is whatever
     the equivalence demands; it is not minimized against any cost, and there is no notion of
     "smallest perturbation that separates." Taylor's entire formulation is min θᵀQθ subject to
     separation, solved by duality + CCP/ADMM.
  3. **Guarantee.** Li et al. offer no statement of the form "detection succeeds for every
     fault in this set." Taylor's constraint 1 ≤ σ(θ) is exactly such a statement.
  4. **Scope of unbalance.** Li et al. handle asymmetrical faults via dual-sequence control but
     never exploit negative sequence as an information channel; they merely keep it inductive.
- **Where the overlap genuinely hurts us:**
  - "**Use inverter control to make protection work**" is established prior art, not just here
    but in the references this paper builds on — Banaiemoqadam/Hooshyar/Azzouz control-based
    distance solutions, Yang et al.'s directional-element-aware current reference generation,
    and the control-based faulty-phase detection line. Taylor's own 2023 paper concedes the
    same, citing schemes that inject harmonics or modulate positive/negative sequence currents.
  - **Hardware validation of an inverter-side protection fix is done**, at both CHIL and bench
    scale. Our planned hardware evaluation is therefore a replication activity, not a novelty
    claim, unless what we put in hardware is the *optimized* signal.
  - The **switching logic** (current-magnitude threshold in, dwell-time out, bounded activation
    window tied to relay memory) is a solved engineering problem. If we need a trigger for when
    to inject, we should adopt this one and cite it rather than reinventing it.

### What our team must NOT claim as novel because of this paper
1. **Modifying GFM inverter control during a fault so that protective relays operate
   correctly.** This is the paper's thesis and it is prior art.
2. Identifying that the **output-impedance change from the current limiter** (not the IVS) is
   what breaks compensation theory for GFM-IBRs, whereas for SGs the source dynamics are
   effectively unchanged.
3. The idea of **making the inverter's equivalent pre-fault/fault source dynamics match** so
   that the pure-fault network of an IBR system resembles that of an SG system.
4. **Enforcing a highly inductive virtual impedance** so the effective sequence impedances stay
   inductive and directional/phase-selection elements remain valid.
5. A **two-mode (protection-interoperable / normal) FRT controller with explicit switching
   criteria** based on a current-magnitude threshold (≈1.05 pu) in and a dwell time (50 ms)
   out, bounded by the relay's incremental-quantity memory window.
6. **Freezing the active power controller during the fault** to prevent angle-error accumulation
   and post-clearance power transients.
7. Treating **transient stability and protection interoperability as joint constraints** on
   inverter FRT design.
8. **CHIL validation of an inverter-side protection scheme** on an RT-Box-class platform, and
   bench validation on a kW-scale inverter against a programmable grid simulator.

---

## Cross-cutting: what is left for us

Reading all three together, the defensible remaining ground for the project is narrow and
specific, and it is worth writing down so we do not drift:

- **Not** "negative sequence carries the information" (Paper 1 and IEEE 2800).
- **Not** "current limiting breaks incremental-quantity protection" (Paper 2, in closed form).
- **Not** "the inverter can be controlled to fix protection" (Paper 3, in hardware).
- **Yes**, the treatment of fault location, fault resistance, remote infeed and noise as
  **bounded sets** with a computed image in measurement space, rather than a swept grid of
  cases or a single operating point.
- **Yes**, a **minimal** injection obtained from a convex program with a **separation
  guarantee** over that set, rather than a control bias sized by circuit equivalence or a
  threshold tuned per system.
- **Yes** (and this is the most tractable senior-design contribution), an **honest head-to-head
  comparison** of relay-side detectors on one common test system: the ΔY2 element of Paper 1,
  the time-based IQ running-sum criterion of Paper 2, and Taylor's set-based detector, with and
  without the auxiliary signal, including the power-quality cost of the injection and the
  detection latency. None of these three papers compares against either of the others.

### Three specific traps
1. **Do not confuse Nathaniel Taylor (KTH, Paper 2) with Joshua A. Taylor (NJIT).** Different
   people, overlapping topic, no shared authorship.
2. **Papers 2 and 3 share an author (Xiongfei Wang).** They are two halves of one research
   programme — Paper 2 diagnoses the IQ/GFM interoperability problem from the relay side,
   Paper 3 fixes it from the inverter side. Cite them as a pair; a reviewer familiar with one
   will know the other.
3. **The equations in Paper 3 and eqs. (9)–(11) of Paper 2 do not survive text extraction.**
   Anything we quote from them must be read off the PDF pages directly, not copied from a
   pypdf dump.
