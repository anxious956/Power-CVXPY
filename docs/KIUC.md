# The NREL / KIUC two-bus system: our inverter, their numbers (plan, pre-registered 31 Oct 2026)

Prof. Taylor sent NREL/TP-5D00-94430 (Wang, Pinheiro, Chakraborty, Johnson, Goncalves Bainy, Hoke, Nov 2025;
https://www.osti.gov/biblio/3011876) at the 20 Oct meeting ([meetings/2026-10-20_biweekly.md](meetings/2026-10-20_biweekly.md)),
with three asks that the report answers in one place: a non-stiff source, an existing system with published numbers,
and GFL/GFM inverters. The report builds generic GFL and GFM inverters in PSCAD, drives PSCAD from Python as we do,
and tests SEL relay elements on a 57.1 kV line of the Kauai (KIUC) system. Its headline is the industry-side form of
our I2-direction result: negative-sequence-dependent elements (32Q/32QG, the I2-polarised quadrilateral, FID)
misoperate unless the inverter controls I2 per IEEE 2800 (magnitude 3I2 > 10 % I1, angle leading V2 by 90–100°);
the current limiter type and the current-control speed matter, the DC source, average-vs-switching model and outer
loop do not. Local copy (git-ignored): `papers/library/NREL_TP-5D00-94430_IBR_protection_2025.pdf`.

**What we do:** rebuild their system with their published numbers in our tools, run our inverter in their three
negative-sequence modes, reproduce their qualitative findings at the IBR-end relay, then put the designed δ on it.
Everything below is written before any code runs; labels as before: static vs EMT, one network, no δ verdict from
runs without injection.

## 1. Their system, in our terms

Report §4.2, Fig. 41, Table 14; §4.3 scenarios; Table 15 fixed parameters.

| element | the report | our model |
|---|---|---|
| voltage, base | 57.1 kV; IBR 15 MVA | base **15 MVA, 57.1 kV**, Z_base = 217.4 Ω |
| equivalent grid | stiff voltage source, or a non-stiff synchronous generator, behind the "equivalent line" Z_eq = 5.91 + j12.53 Ω (Z0 5.65 + j18.93 Ω) between the grid and the POI (Table 14); Line-1 POI→Bus-1 has no separate impedance in Table 14 | **hydro off:** a stiff SG at bus G (zs 0.001j pu) and a line **EQ** G→Bus-1 with Z_eq: **z1 0.0272 + j0.0576 pu, z0 0.0260 + j0.0871 pu**; Line-1 = 0, so POI ≡ Bus-1. Faults on EQ are R1's reverse set |
| hydro at Bus-1 | 7.5 MVA, 6.9 kV, via Y-Δ 57.1/6.9 kV 7.5 MVA TF1, Δ facing the power system (Table 15); no machine data given | **hydro on:** our design tool takes one SG, so the source at Bus-1 becomes the Thevenin equivalent of the grid behind Z_eq in parallel with the hydro behind X'd + X_TF1; X'd **assumed 0.25 pu** and X_TF1 **assumed 0.07 pu**, both on 7.5 MVA (together 0.64 pu on 15 MVA); no hydro zero-sequence path (Δ facing the line). No EQ line in this case, so no reverse set for R1. The hydro's rotor dynamics are not modelled |
| Line-2, Bus-1→Bus-2, 4.6 mi | Z1 = 1.0433 + j3.218 Ω, Z0 = 1.5649 + j4.827 Ω | **z1 = 0.0048 + j0.0148 pu, z0 = 0.0072 + j0.0222 pu**, lumped R-L (short line, charging negligible) |
| IBR at Bus-2 | 15 MVA, 0.48 kV, via TF2 57.1/0.48 kV 15 MVA, YgΔ (Yg facing the line) for ground-fault cases, ΔYg for phase-fault cases; generic GFL (and GFM) | our averaged V1-referenced GFL inverter (`gfl_avm`), i_max 1.2 pu (their I_sat 1.2 pu), PLL-like reference 15 Hz; TF2 as the inverter's zero-sequence path at Bus-2: **zero_z = j0.06 pu for YgΔ** (X_TF2 assumed 6 % on 15 MVA), **open for ΔYg**; the series impedance of TF2 in front of a current source does not change the network currents and is dropped, so the inverter's V1 reference is Bus-2 (HV) rather than the 0.48 kV terminal, stated as an approximation |
| loads | none shown; power flows IBR → grid | none |
| operating points | P 0.25 / Q 0.15 pu (their Fig. 16 and the slow/fast cases); P 1.0 / Q 0; P 0.1 / Q 0; GFM 0.8 / 0 | **P 0.25 / Q 0.15** primary, **P 1.0 / Q 0** secondary, in the inverter's own frame; source EMF set for 1.0 pu at the POI |
| negative-sequence modes | no I2 control (dq / αβ current control: "the absence of negative sequence current"); IEEE 2800 sequence-domain control I2 = K·V2 ∠(∠V2 + 90°), **K = 5**, slow and fast tunings | MODE2 0 (suppressed), MODE2 1 with **K2 = 5** (we used 2 before; 5 is theirs), MODE2 2 (designed δ) |
| relays | R1 at Bus-1 and R2 at Bus-2, both looking into Line-2; SEL-411L elements (I0/I2-polarised quad, V1-memory mho Z1 0.61 Ω / Z2 1.10 Ω secondary, 32Q/32QG/32V, 87L, FID), T400L (TD21/TD32); 480 Hz and 10 kHz COMTRADE | **R2 (IBR end)** primary, R1 secondary; our chain (mimic filter, memory frame, 2–3-cycle windows); elements: (i) the **32QG of the report**, z2 = Re[V2·(I2·1∠Z1L)\*]/\|I2\|², forward if z2 < \|Z2L\|/2 − ε, with its supervision (3I2 above a pickup, the k2 ratio \|I2\|/\|I0\| for ground faults); (ii) our **incremental element** (dY2 when enabled, else dY1, as in I2_DIRECTION); (iii) **D1, the set test**. Reach elements are out of scope |
| faults | at F on Line-2: AG, BC, ABC; R_f 0.01, 1, 5, 10 Ω; m 5 / 50 / 80 % from the IBR end; grid strength hydro on/off; momentary cessation; slow/fast controllers | **forward set for R2:** AG and BC at m 0.05 / 0.50 / 0.80 from Bus-2 at R_f 0.01 and 5 Ω (ABC at 0.01 Ω as a check): 14 cases; **reverse set for R1** (hydro off only): the same types and resistances on the EQ line at 0.05 / 0.50 / 0.80 from Bus-1. R2 has no reverse fault in this topology (nothing behind the IBR but the IBR), so at R2 the question is dependability, as in the report. Cessation and controller speed are not reproduced |

Not in the report and therefore assumed, with a sensitivity each: X'd and X_TF1 of the hydro branch (±50 %),
X_TF2 (3–9 %), the EMF angle. The CT/VT ratios (80 and 3500) matter only for secondary ohms and are not used.

## 1b. Changes from the review, before the first run (31 Oct 2026)

- **Two synchronous sources for Q1 and Q2**, as the report has it: the grid (stiff, 0.001j) at G behind EQ, and the
  hydro at Bus-1 behind **X''d + X_TF1 = 0.20 + 0.07 pu on 7.5 MVA (0.54 pu on 15 MVA)**, no zero-sequence path;
  X'd 0.25 (0.64 pu) as the sensitivity. Both EMFs 1.0∠0 at the nominal point; the hydro's EMF is held at nominal
  (outside the source box). The Thevenin equivalent is a Q3 (design) device only; the pre-flight checks once that
  it gives the same pre-fault state and the same bolted-AG currents at R2 as the two-source network. A source branch
  has no rotor angle or frequency drift; fine for 3 cycles.
- **The inverter's positive-sequence fault response (FRT)**, added to gfl_avm and to network.solve_v1ref (one rule,
  `network.frt_command`): when |V1| < 0.9 pu at Bus-2, I_Q+ = I_Q0 + K1 (0.9 − |V1|), clipped at i_max, and I_P+ cut
  so the command fits i_max (q priority). **K1 = 2** (IEEE 2800's range 2–6; the report states none), **K1 = 4** and
  **K1 = 0** as sensitivities (0 keeps the comparison to our earlier results). In EMT |V1| is low-passed with the
  reference filter's τ = TANG = 1/(2π·15 Hz) so the response does not chatter on the DFT ripple. At the phase limit
  the I2 law keeps priority (LIM 1): I_Q+ and I_P+ give way to I2, in that order of what is left.
- **Q3 is a different inverter from Q2's**: the δ design here is for the inverter without reactive-current support
  (FRT off), and its EMT check runs FRT off too, so design and check describe the same controller; FRT inside
  FrameModel is the follow-up. No Q3 result before the review has seen Q2. The deadband form (0.9 − |V1|) is registered
  here; the reviewer's (1 − |V1|) differs by 0.1 K1 = 0.2 pu, which saturates either way on the close-in faults.
  FRT = 0 reproduces every earlier result (regressions 2.7·10⁻¹³ / 7.4·10⁻¹³ pu; BUILD_VERSION 6).
- **Limiter with K2 = 5**: I2 = 5 V2 reaches 1.2 pu at |V2| = 0.24. LIM 1 (I2 priority) applies: I2 is kept and I1
  (after the FRT command) is scaled until every phase peak fits 1.2 pu; I_sat = 1.2 pu is per phase peak, as the
  report's. K2 = 2 as a one-line sensitivity.
- **MODE2 1 in EMT gets TV2 = 1/(2π·15 Hz)** from the start (Bus-2 has no load and no passive positive/negative
  shunt: the undamped cut-set of the I2 study), with the per-run numerical check (peak |vA| ≤ 2 × nominal, 5–10 kHz
  energy share ≤ 10⁻³) and the caveat "mode slowed, not removed" if it shows.
- **The report's element, two-sided, three outcomes.** 32Q (B-C) and 32QG (A-G): z2 = Re[V2·(I2·1∠Z1L)*]/|I2|²;
  **forward if z2 < Z2F = 0.4 |Z1L|, reverse if z2 > Z2R = 0.6 |Z1L|** (|Z1L|/2 ∓ 0.1 |Z1L|); enabled only if
  3|I2| > 0.1 pu (50Q pickup, the report's "10 % of rated"), |I2| > 0.1 |I1| (a2) and, for 32QG, |I2| > 0.2 |I0|
  (k2, the zero-sequence restraint the report found blocking its own A-G cases). Each case counts forward, reverse
  or not enabled (with the blocking reason).
- **TF2 in PSCAD is ΔYg only** (the builder has no grounded path at an inverter bus): A-G with ΔYg is the report's
  scenario 2, and all its B-C cases are ΔYg. **Every YgΔ cell is static only** and outside the EMT go/no-go; there
  the report's k2 blocking of 32QG on A-G "in both modes" is the expected outcome. A grounding transformer at Bus-2
  is the follow-up, its zero-sequence impedance then the registered X_TF2.
- **Expectation per mode at R2, ΔYg, written before Q1:** beyond R2 there is no zero-sequence path, so I0 = 0 and
  k2 never binds; suppressed: no negative-sequence path either, so 50Q does not pick up (not enabled); IEEE 2800:
  I2 = K·V2 appears and the element declares forward.
- **ABC** is not in the forward-set counts (the static solver has no three-phase fault; it has no I2 by
  construction); a bolted ABC run in EMT is a limiter check only.
- **Weak frame at R2**: |V1| at Bus-2 < 0.2 pu flags a run (read separately, not excluded). The inverter's
  reference is the Bus-2 (HV) V1, since TF2's series impedance is dropped; with the real TF2 the terminal voltage
  would sit higher than Bus-2's during the fault.
- **R1's reverse set is the direction question** (faults on EQ, hydro off): the I2 R1 measures for them comes only
  from the IBR, so suppressed → no I2 → nothing, IEEE 2800 → reverse; the s = 1 result of the I2 study in their
  topology. R1's forward set (Line-2) is the control (the grid behind R1).
- Pre-flight states the pre-fault flow (IBR → grid, no load). The SIR is about 4 (Z_eq 0.0576 vs the line's
  0.0148): faults 50–80 % from Bus-2 are electrically close to Bus-1.

## 1c. Decisions after the pre-flight, before Q1 (31 Oct 2026)

`src/kiuc.py preflight` → `results/network/kiuc_preflight.json`.

| grid case | operating point | \|V1\| G / B1 / B2 | P, Q from Bus-2 into Line-2 |
|---|---|---|---|
| hydro off | P 0.25 / Q 0.15 | 1.000 / 1.016 / 1.019 | +0.253, +0.156 (IBR → grid) |
| hydro off | P 1.0 / Q 0 | 1.000 / 1.029 / 1.035 | +1.032, +0.073 |
| two sources (hydro X''d) | P 0.25 / Q 0.15 | 1.000 / 1.014 / 1.017 | +0.252, +0.156 |
| two sources | P 1.0 / Q 0 | 1.000 / 1.024 / 1.029 | +1.027, +0.069 |

Two-source against Thevenin at R2, pre-fault and bolted AG at 5 %: 1.9·10⁻⁵ pu (X''d and X'd).

- **A bug found and fixed (REVIEW §7 row 60):** the static IEEE 2800 law was a shunt in `network.solve`, outside the
  limiter; at K2 = 5 it gave |I2| = 1.67–1.78 pu, above i_max. The law now sits in `solve_v1ref` as a V2-referenced
  injection through the same limiter as PSCAD (|V2| in the fixed point); regression against the shunt form where
  the limiter does not bind: ≤ 4·10⁻⁷ pu.
- **Primary limiter: LIM 2, "the report's limiter as its Fig. 16 shows it"** (I_Q+ = 1.2 and I_Q− = 0.45 at once):
  |I1| ≤ i_max with q priority via the FRT rule, |I2| ≤ i_max separately, no combined phase limit. This is not a
  physical claim: the phase peak can reach 2·i_max, which no real inverter delivers; every LIM 2 case reports its
  per-phase peak and is flagged "beyond their Fig. 16 envelope" above 1.5 pu. **LIM 1 (ours, per phase, I2 first)**
  is the sensitivity, the comparison's honest frame: their result under their limiter, and what a per-phase limit
  does to it.
- **Primary K1 = 4** (changed from 2, recorded before Q1): their I_Q+ = 1.2 with I_P+ → 0 needs K1 (0.9 − |V1|) ≥ 1.05,
  i.e. K1 ≥ 3.4 at our |V1| ≈ 0.6, so K1 = 2 cannot reproduce their figure; 4 is inside IEEE 2800's range; their own
  K1 and fault location are not stated. Sensitivities K1 = 2 and K1 = 0 (FRT off, "our inverter so far").
- **The Fig.-16 sanity reads**: met at K1 = 4 on YgΔ (I_P+ 0.000, I_Q+ 1.200, ∠I2 − ∠V2 = 90.0°); K1 = 2 fails on I1
  and passes on I2. The check is defined on the YgΔ case, the one the figure most likely shows (a ground fault with
  a grounded transformer); with ΔYg the dip is shallower and I_P+ stays 0.248 at K1 = 4. The I2 sanity is "law
  K = 5, angle 90°; measured K lower where I2 saturates at 1.2 pu"; the go/no-go's 3I2 > 10 % I1 test is unaffected,
  and the reported K is the measured one.
- **Unresolved difference:** their I_Q− = 0.45 pu at K = 5 (V2 ≈ 0.09 at their terminal) against our 1.2 pu
  (V2 0.23–0.38 at Bus-2, saturated). Two candidates: their V2 is measured behind TF2's series impedance, or their
  fault is farther. Not a model error of ours as far as the evidence goes, and it does not touch the direction
  questions: the elements use the angle, which matches.
- Q1 runs with K2 = 5, LIM 2, K1 = 4 (FRT on); sensitivities K1 = 2, K1 = 0, LIM 1, K2 = 2.

## 2. Pre-flight

- Load flow with `network.solve_v1ref` at both operating points, hydro on and off, TF2 both ways: converges, every
  bus within 0.95–1.05 pu. A combination that fails is out and said so.
- Short-circuit sanity against the report's own numbers where it gives them: the bolted AG fault at 5 % from the
  IBR end should put the IBR at its 1.2 pu limit with I_P+ → 0 and I_Q+ → 1.2 pu (their Fig. 16) in the IEEE 2800
  mode, and I2 ≈ K·V2 with the angle leading V2 by about 90°. Tolerance ±10 % on the magnitudes, ±15° on the angle.
  If our inverter does not do this, the inverter is fixed before anything else is read.

## 3. Registered questions

**Q1, static (16 corners of the source box where a box applies; nominal otherwise).** Per mode {suppressed,
IEEE 2800 K = 5} × grid strength {hydro off, on} × TF2 {YgΔ for AG, ΔYg for BC} × operating point, at R2 for the
forward set: the 32QG decision with its supervision, the incremental element's decision, the ratio 3|I2|/|I1| and
the angle ∠I2 − ∠V2 at the relay.
- Expected from the report: suppressed → 32QG not enabled (3I2 below pickup) or no decision; IEEE 2800 → forward on
  every case; 3I2 > 10 % I1 only in the IEEE 2800 mode.

**Q2, EMT (PSCAD).** The 14 forward cases plus the normal run, at P 0.25 / Q 0.15, modes {0, 1}, grid strength
{off, on}: 60 runs; the same at P 1.0 / Q 0 for the suppressed mode and hydro off (15 runs) as a sensitivity. Gates
as in I2_DIRECTION stage (c): pre-fault injections within 3 % of static and settled; the per-run numerical check;
weak-frame flag. Read: the three elements on windows ending 2–3 cycles after inception; EMT against static per case.

**Q3, the designed δ on this system.** Two designs with the step-3 machinery on this network, both tiers, ρ 0.1 and
0, full polar search to the 1.14 pu cap:
- **detection** at R2 (fault set against normal), as in step 3;
- **direction** at R1 (Line-2 set against Line-1 set), as in I2_DIRECTION stage (b), since R1 is the relay with a
  reverse set here.
Then δ* injected in EMT at the nominal point for the forward set (and the R1 reverse set): the set-test check
(contained, separated) and the two conventional elements, as in LONG_LINES Q3. Price as |I1| delivered / commanded.

## 4. Go / no-go, fixed now

- **Reproduction holds at R2** if in EMT (Q2), on the forward set with TF2 ΔYg, the report's element (32Q for B-C,
  32QG for A-G) declares forward on ≥ 90 % and **reverse on none** in the IEEE 2800 mode, and declares nothing or
  reverse on ≥ 50 % in the suppressed mode; and 3I2 > 10 % I1 holds in the IEEE 2800 mode on every case and fails
  in the suppressed mode on ≥ 70 %.
- **Reproduction holds at R1 (direction)** if on R1's reverse set (EQ, hydro off) the element declares reverse on
  ≥ 90 % and forward on none in the IEEE 2800 mode, and nothing or forward on ≥ 50 % in the suppressed mode; R1's
  forward set is reported as the control.
- Partial outcomes are reported as such; a failure at the pre-flight sanity check is a model problem, not a finding.
- **δ on this system**: reported per design with the same wording as before: whether δ* exists within the cap,
  its price, and whether it holds in EMT (consistent with, not confirmed); whether the conventional elements change
  with δ. The prior from step 3 and I2_DIRECTION is "δ buys the guarantee, not the decision"; a different outcome
  here is the finding.
- Stop rules: no re-tuning of thresholds after a result; assumptions stay as registered with their sensitivities
  reported; no δ verdict from runs without injection.

## Q1 result, static (31 Oct 2026)

`src/kiuc.py static` → `results/network/kiuc_static.json`. 12 cases × 16 corners = 192 points per row; the report's
element is 32Q for B-C and 32QG for A-G with their supervision; "right" is forward at R2 and on R1's forward set,
reverse on R1's reverse set. Primary: K2 = 5, LIM 2, K1 = 4. No weak-frame point anywhere (|V1| at Bus-2 ≥ 0.2).

| relay, set | grid | TF2 | mode | FRT K1 | report element: right / not enabled / wrong | incremental: right / none / wrong | 3I2 > 10 % I1 | phase peak max (points > 1.5 pu) |
|---|---|---|---|---|---|---|---|---|
| R2 forward | hydro off | ΔYg | suppressed | 0 | 0 / 1.00 / 0 | 0 / 0.99 / 0.01 | 0 | 0.41 (0) |
| R2 forward | hydro off | ΔYg | suppressed | 4 | 0 / 1.00 / 0 | 0.98 / 0 / 0.02 | 0 | 1.20 (0) |
| R2 forward | hydro off | ΔYg | IEEE 2800 | 0 | 1.00 / 0 / 0 | 1.00 / 0 / 0 | 1.00 | 1.61 (58) |
| R2 forward | hydro off | ΔYg | IEEE 2800 | 4 | **1.00 / 0 / 0** | 1.00 / 0 / 0 | 1.00 | 2.29 (192) |
| R2 forward | two sources | ΔYg | suppressed | 0 | 0 / 1.00 / 0 | 0.04 / 0.90 / 0.06 | 0 | 0.41 (0) |
| R2 forward | two sources | ΔYg | suppressed | 4 | **0 / 1.00 / 0** | 0.97 / 0 / 0.03 | 0 | 1.20 (0) |
| R2 forward | two sources | ΔYg | IEEE 2800 | 0 | 1.00 / 0 / 0 | 1.00 / 0 / 0 | 1.00 | 1.61 (56) |
| R2 forward | two sources | ΔYg | IEEE 2800 | 4 | **1.00 / 0 / 0** | 1.00 / 0 / 0 | 1.00 | 2.26 (189) |
| R2 forward | either | YgΔ (static only) | as ΔYg | | the same as ΔYg in every row | suppressed FRT 0: 0.07 / 0.82 / 0.10 (two sources) | | up to 2.40 |
| R1 reverse | hydro off | ΔYg | suppressed | 0 | 0 / 1.00 / 0 | 0.04 / 0.88 / 0.08 | 0 | 0.41 (0) |
| R1 reverse | hydro off | ΔYg | suppressed | 4 | **0 / 1.00 / 0** | 0.79 / 0.10 / 0.11 | 0 | 1.20 (0) |
| R1 reverse | hydro off | ΔYg | IEEE 2800 | 0 | 1.00 / 0 / 0 | 1.00 / 0 / 0 | 1.00 | 1.61 (44) |
| R1 reverse | hydro off | ΔYg | IEEE 2800 | 4 | **1.00 / 0 / 0** | 1.00 / 0 / 0 | 1.00 | 2.34 (141) |
| R1 forward (control) | hydro off | ΔYg | both | 0, 4 | 1.00 / 0 / 0 | 1.00 / 0 / 0 | 1.00 | |

Sensitivities (one row each, two sources for R2, hydro off for R1): K1 = 2, LIM 1 (both modes), K2 = 2 and X'd 0.25
give **the same report-element decisions as the primary in every row**; LIM 1 caps the phase peak at 1.20 pu
without changing a decision; the incremental element under suppression with LIM 1 is unchanged (R2 0.97 right,
R1 reverse 0.79 right / 0.11 wrong).

**Reading, static model, nominal-to-corner box, before EMT:**
- **The report's finding reproduces exactly at both relays.** With I2 suppressed, the negative-sequence elements are
  never enabled (3|I2| below the pickup on every point, R2 and R1 reverse); with the IEEE 2800 law at K = 5 they
  decide right on every point, at R2 (forward) and at R1 for faults behind it (reverse), with no wrong decision.
  R1's forward set (grid behind) is right in both modes, the control. The outcome holds under LIM 1, K1 = 2, K2 = 2
  and X'd 0.25: on this system the decision does not depend on the limiter, only on whether I2 is controlled.
- **The 32QG's zero-sequence restraint depends on the inverter's I2 magnitude** (a small finding beyond the report).
  On YgΔ A-G the k2 restraint (|I2| > 0.2 |I0|) does not block our 32QG; the report found it blocked on its own A-G
  cases. A static check with |I2| capped at the report's 0.45 pu (information only, registered runs unchanged) gives
  |I2|/|I0| = 0.11–0.14 at R2 and **k2 blocks 96 of 96** points, hydro off and on. So whether the restraint blocks
  the element on a grounded-transformer A-G fault depends on the inverter's I2 magnitude: at the report's 0.45 pu
  it blocks, at our saturated 1.2 pu it does not. It therefore depends on the limiter and on where V2 is measured,
  not only on the fault; reproducing a relay result needs the inverter's limiter as part of the specification.
- **The positive-sequence response (FRT) restores our incremental element under suppression**: with K1 = 4 the
  superimposed positive-sequence element decides R2 right on 97–98 % (from ≤ 4 % without FRT) and R1's reverse set
  on 79 %, with 11 % wrong-way. This is the limitation the I2 study wrote down ("the K-factor would likely restore
  direction even under suppression") now measured; the negative-sequence elements do not benefit from it.
- **LIM 2's unphysical side is visible**: with FRT on and the K2 law active, every point exceeds 1.5 pu of phase
  peak (up to 2.40 pu); LIM 1 keeps 1.20 pu and gives the same decisions.

## Q2, registered after Q1 and before any Q2 result is read (31 Oct 2026)

- **The batch**: 117 runs at K2 = 5, LIM 2, K1 = 4, TANG = TV2 = 1/(2π·15 Hz), nominal source point (13-run groups:
  R2 × {hydro off, two sources} × {suppressed, IEEE 2800}; R1 reverse and R1 forward × both modes, hydro off; P 1.0 /
  Q 0 suppressed at R2), **plus a LIM 1 group of 26 runs** (R2 two sources IEEE 2800; R1 reverse IEEE 2800), since
  LIM 2's phase peaks reach 2.3 pu. Reading rules as registered: per-case static prediction with the same settings,
  three outcomes per element (right / not enabled / wrong), per-run peak and 5–10 kHz check, LIM 2 peaks flagged
  above 1.5 pu.
- **Launch order, stated:** the 117-run batch was started before the review asked for an EMT Fig.-16 pair first. The
  pair (the normal run and the bolted AG at 5 % from Bus-2, R2, hydro off, IEEE 2800) is inside the batch's first
  group; it is checked as soon as it exists, before anything else in the batch is read, and the batch is stopped and
  nothing interpreted if it fails (I_Q+ near 1.2 and I_P+ near 0 at K1 = 4, I2 leading V2 by about 90°, pre-fault
  gate).
- **Sub-question, the FRT finding, pre-registered:** under suppression, does the positive-sequence FRT (K1 = 4) restore
  our incremental element's direction at R2 and R1, as static says (R2 0.97 right; R1 reverse 0.79 right, **0.11
  wrong**)? The wrong-way share at R1 is the number to watch; in EMT the TANG lag turns the frame less, so fewer
  wrong and more undecided are expected, as in the I2 study.
- **How the outcome will be phrased** (if EMT agrees): the I2 study's s = 1 result stands for inverters without
  reactive-current support; with IEEE 2800-style FRT the positive-sequence element recovers, the negative-sequence one
  does not. That is the K-factor limitation of the I2 study, measured.

### The EMT Fig.-16 pair, before the batch was read (31 Oct 2026)

`src/kiuc.py fig16` → `results/network/kiuc_fig16_emt.json`. R2, hydro off, TF2 ΔYg (the only TF2 in PSCAD), IEEE 2800
K2 = 5, K1 = 4, LIM 2, TANG = TV2 = 15 Hz, bolted A-G at 5 % from Bus-2. Pre-fault gate passed (|I1| 0.291 EMT,
0.292 static); numerically clean; both elements forward; no weak frame.

| cycles after inception | I_Q+ | I_P+ | \|V1\| at Bus-2 | \|I2\| |
|---|---|---|---|---|
| 2.0 | 0.575 | 0.274 | 0.724 | 1.030 |
| 2.5 | 0.736 | 0.252 | 0.730 | 1.164 |
| 3.0 | 0.796 | 0.245 | 0.732 | 1.197 |
| 4.0 | 0.821 | 0.245 | 0.733 | 1.200 |
| 5.0 | 0.822 | 0.245 | 0.733 | 1.200 |
| static (same settings) | 0.821 | 0.248 | 0.733 | 1.200 |

At 2.5 cycles: |I2| = 4.73 |V2| (static 4.86), ∠I2 − ∠V2 = 90.5° (static 90.0°), phase peak 1.92 pu (static 2.04,
beyond the 1.5 pu envelope). The EMT converges to the static state by 4 cycles; inside the relay's 2–3-cycle window the
FRT is still rising (it acts on the 15 Hz-filtered |V1|), which is the real controller and registered as such.

### Q2 result, EMT (31 Oct 2026)

`src/kiuc.py analyse` (and `--lim1`) → `results/network/kiuc_q2.json`, `kiuc_q2_lim1.json`. 143 PSCAD runs, nominal
source point, TF2 ΔYg, K2 = 5, K1 = 4, TANG = TV2 = 15 Hz; decisions on windows ending 2–3 cycles after inception
(first decided window). Every group's pre-fault gate passed (|I1| within 0.3 % of static). "Right" is forward at R2
and on R1's forward set, reverse on R1's reverse set.

| relay, set | grid | mode | limiter | clean | report element: right / not enabled / wrong | incremental: right / none / wrong | 3I2 > 10 % I1 | EMT ≠ static (report el. / incremental) | IBR phase peak max (> 1.5 pu) |
|---|---|---|---|---|---|---|---|---|---|
| R2 forward | hydro off | suppressed | LIM 2 | 12/12 | 0 / 1.00 / 0 | 1.00 / 0 / 0 | 0 | 0 / 0 | 1.22 (0) |
| R2 forward | hydro off | IEEE 2800 | LIM 2 | 12/12 | **1.00 / 0 / 0** | 1.00 / 0 / 0 | 1.00 | 0 / 0 | 2.23 (12) |
| R2 forward | two sources | suppressed | LIM 2 | 12/12 | **0 / 1.00 / 0** | 1.00 / 0 / 0 | 0 | 0 / 0 | 1.23 (0) |
| R2 forward | two sources | IEEE 2800 | LIM 2 | 12/12 | **1.00 / 0 / 0** | 1.00 / 0 / 0 | 1.00 | 0 / 0 | 2.25 (12) |
| R2 forward, P 1.0 / Q 0 | hydro off | suppressed | LIM 2 | 12/12 | 0 / 1.00 / 0 | 0.92 / 0 / 0.08 | 0 | 0 / 5 | 1.24 (0) |
| R1 reverse | hydro off | suppressed | LIM 2 | 12/12 | **0 / 1.00 / 0** | 0.75 / 0.17 / **0.08** | 0 | 0 / 1 | 1.22 (0) |
| R1 reverse | hydro off | IEEE 2800 | LIM 2 | 12/12 | **1.00 / 0 / 0** | 1.00 / 0 / 0 | 1.00 | 0 / 0 | 2.24 (9) |
| R1 forward (control) | hydro off | suppressed | LIM 2 | 12/12 | 1.00 / 0 / 0 | 1.00 / 0 / 0 | 1.00 | 0 / 0 | 1.22 (0) |
| R1 forward (control) | hydro off | IEEE 2800 | LIM 2 | 12/12 | 1.00 / 0 / 0 | 1.00 / 0 / 0 | 1.00 | 0 / 0 | 2.23 (12) |
| R2 forward | two sources | IEEE 2800 | **LIM 1** | **6/12** | 1.00 / 0 / 0 (of 6) | 1.00 / 0 / 0 | 1.00 | 0 / 0 | 1.21 (0) |
| R1 reverse | hydro off | IEEE 2800 | **LIM 1** | **7/12** | 1.00 / 0 / 0 (of 7) | 1.00 / 0 / 0 | 1.00 | 0 / 0 | 1.22 (0) |

No weak frame anywhere (|V1| at the inverter ≥ 0.2 pu).

**Go / no-go (registered):**
- **Reproduction holds at R2.** IEEE 2800: forward on 12 of 12 (≥ 90 %) and reverse on none, in both grid cases;
  suppressed: not enabled on 12 of 12 (≥ 50 %); 3I2 > 10 % I1 on every IEEE 2800 case and on no suppressed case
  (≥ 70 %).
- **Reproduction holds at R1 (direction).** IEEE 2800: reverse on 12 of 12 and forward on none; suppressed: not
  enabled on 12 of 12; the forward control right in both modes.
- **EMT agrees with static on every report-element decision** (0 of 107 clean fault runs differ).

**The FRT sub-question (pre-registered):** under suppression, the positive-sequence FRT (K1 = 4) restores our
incremental element: R2 forward 12 of 12 right in both grid cases (static 0.97–0.98); **R1 reverse 0.75 right,
0.17 none, 0.08 wrong** (static 0.79 / 0.10 / 0.11): fewer wrong and more undecided than static, as the TANG lag
predicted. At P 1.0 / Q 0 (less reactive headroom) R2 drops to 0.92 right, 0.08 wrong.

**LIM 1 (ours, per phase, I2 first) is numerically unstable on B-C faults at K2 = 5.** Every excluded run is a B-C
case (11 of 12 B-C across the two groups; peaks 9–30 × nominal, 5–10 kHz share 0.03–0.13); every A-G run is clean and
decides as under LIM 2 with the phase peak held at 1.21–1.22 pu. TV2 = 15 Hz does not prevent it. So under a real
per-phase limit, K = 5 on a phase-to-phase fault is not runnable in this model; the B-C cells of the LIM 1 column
are "not interpretable", and LIM 1 confirms the A-G result only.

**Reading.**
- **The report's finding reproduces in EMT with our own inverter, at both relays:** with I2 suppressed, the
  negative-sequence directional elements are never enabled (I2 below pickup); with the IEEE 2800 law (K = 5) they
  decide right on every case, forward at the IBR end and reverse at the grid end for faults behind it.
- **The I2 study's s = 1 result stands for inverters without reactive-current support; with IEEE 2800-style FRT the
  positive-sequence element recovers, the negative-sequence one does not.** That is the K-factor limitation of the
  I2 study, measured: R2 fully, R1 at 0.75 with 8 % wrong-way.
- **LIM 2's unphysical side**: with the K2 law active, the IBR's phase peak is 2.2 pu on most cases, beyond the report's
  Fig.-16 envelope; LIM 1 holds 1.2 pu on the A-G cases with the same decisions and cannot run B-C.
- Caveats: one system, nominal source point, one point on wave, clean measurements, TF2 ΔYg only in EMT, the hydro as
  a source behind X''d.

### The LIM 1 B-C diagnostic (information only)

`results/network/kiuc_diag_lim1_specs.json`; one B-C case (R2, hydro off, IEEE 2800, bolted at 50 %), LIM 1, K1 = 4:

| run | numerically clean | peak / nominal | 5–10 kHz share |
|---|---|---|---|
| (a) K2 = 2, TV2 15 Hz | **yes** | 1.00 | 1.4·10⁻⁵ |
| (b) K2 = 5, TV2 5 Hz | no | 7.26 | 4.7·10⁻² |
| (c) K2 = 5, TV2 15 Hz (the batch's setting) | no | 32.3 | 1.3·10⁻¹ |

K = 5 with a per-phase, I2-priority limiter is not stable in this controller; K = 2 is. A narrower V2 bandwidth slows
the mode but does not remove it. This is a statement about the limiter–law pair, not about the grid (the likely
mechanism: the I2 demand saturates the phase budget, the per-phase rescaling changes V2, the law changes I2). LIM 1
B-C stays "not runnable at K = 5".

## Q3, registered before any design run (31 Oct 2026)

- **The question is sharper here than in the I2 study.** On this system the IEEE 2800 law already gives direction at
  R1 and the 3I2 the negative-sequence elements need (Q2). The designed δ (MODE2 2, no V2 law, I2 otherwise
  suppressed) must do that job open-loop. The prior, from REVIEW row 58: it certifies the set test and does not
  repair the conventional element. A different outcome is the finding.
- **Q3's inverter is "ours", not Q2's:** FRT off (the design tool, `frames.FrameModel`, has no FRT yet) and LIM 1 (a
  guarantee needs a physical limit; LIM 1 is clean in EMT on A-G). Q2 ran K1 = 4 and LIM 2, the report's.
- **Designs** (`src/kiuc.py design`), both tiers (0.08 pu box; structured design tier), ρ 0.1 (ρ 0 reported), full
  polar search (5° × 0.02 pu to the 1.14 pu cap), δ = 0 pairwise first, dead frames, price as |I1| delivered /
  commanded at the nominal point, the separating angle set and the largest-margin angle carried:
  - **detection at R2**: the forward set against normal operation, hydro off (the network has one source) and hydro
    on (the Thevenin network);
  - **direction at R1**: every forward-set case against every reverse-set case (EQ faults), hydro off.
  "Yes" as before: separation within the cap at ρ 0.1.
- **The EMT check** at the nominal point, δ* injected, the same 12-case sets: the set test (contained ≤ 0.1 ε,
  separated) and the two conventional elements; B-C at R1 reverse under LIM 1 only if a clean configuration exists
  (the diagnostic says K = 2 is clean, but Q3 has no K2 law: MODE2 2 with LIM 1 is the I2 study's configuration, clean
  there), otherwise A-G only, said so.

## Q3 result, static design (31 Oct 2026)

`src/kiuc.py design` → `results/network/kiuc_q3_design.json`. Q3's inverter (FRT off, LIM 1, I2 suppressed),
main configuration, both tiers, ρ 0.1 and 0:

| design | tier | cases (pairs) not apart at δ = 0 | δ* | margin at δ = 0, ρ 0.1 (ρ 0) | binding | price |
|---|---|---|---|---|---|---|
| detection R2, hydro off | box | 0 of 12 | **0** | 1.67 ε (1.87) | L2 A-G 80 % from Bus-2, 5 Ω | none (\|I1\| 0.287 / 0.287) |
| detection R2, hydro off | structured | 0 of 12 | **0** | 12.6 ε (12.8) | same | none |
| detection R2, hydro on (Thevenin) | box | 0 of 12 | **0** | 1.91 ε (2.11) | same | none |
| detection R2, hydro on (Thevenin) | structured | 0 of 12 | **0** | 13.5 ε (13.7) | same | none |
| direction R1, hydro off | box | 0 of 144 | **0** | 29.8 ε (30.0) | L2 A-G 5 % from Bus-2 vs EQ A-G 50 %, 5 Ω | none |
| direction R1, hydro off | structured | 0 of 144 | **0** | 60.4 ε (60.6) | L2 A-G 5 % vs EQ B-C 50 % | none |

No dead frames; no inadmissible candidate (the search never ran: δ = 0 already separates).

**Reading, static model, before EMT:** on this system the designed δ has nothing to do. With I2 suppressed, the set
test separates every fault from normal operation at the IBR-end relay (R2) and every forward fault from every reverse
fault at the grid-end relay (R1), at δ = 0, under both noise tiers, with margins of 1.7–13.7 ε (detection) and
30–60 ε (direction). The conventional negative-sequence elements need the IEEE 2800 law for the same job (Q2), and
the designed δ would have to replace that law open-loop; it does not have to, because the set test does not need
I2 at all here: it uses the voltages and the positive sequence. **The prior "δ buys the guarantee, not the decision"
becomes "the set test needs no δ for the guarantee either" on this system** (strong grid behind R1, SIR about 4,
short line). The EMT check therefore runs at δ = 0, below.

### Deviations during Q2 (recorded)

- **Launch order:** the batch was started before the review asked for the EMT Fig.-16 pair first; the pair was then
  run and read on its own before anything else.
- **Two PSCAD clients for about 5 minutes:** the first launch (a harness-backgrounded command whose Python 3.7 output
  was buffered) was still alive when the batch was relaunched as a detached process; runs 2–3 failed ("simulation
  process stopped unexpectedly", a file lock). The duplicate client was stopped, the 7 outputs it may have touched
  deleted, and nothing from them read; the batch was relaunched once, one client, unbuffered.
- **The project key:** the kiuc branch lacked `key_extra` (it was on long-lines), so different topologies in one batch
  could have shared a built project; added before the relaunch. Outputs are reusable only by spec digest (BUILD 6),
  so nothing from before the fix can be read by mistake.

## 5. What this does not do

Their GFM inverter (we have none yet), their switching model, momentary cessation, slow/fast controller tunings,
the SEL distance elements and 87L, the 480 Hz COMTRADE replay through a MATLAB relay. The hydro is a Thevenin
branch, not a machine. One line, one operating regime, lumped R-L.

## 6. Code

- `src/pscad_network.py`: per-spec base (S_base, V_LL) instead of the module constants 10 MVA / 20 kV; otherwise
  the builder as is (one SG with zs, lines with z0, the inverter with zero_z).
- `src/network.py`: no change expected (any radial network).
- `src/kiuc.py`: the network from the table above, the pre-flight, Q1, the specs and the analysis, the 32QG element.
- `src/frames.py`: the long-lines under-relaxed fixed point (branch long-lines) is cherry-picked if needed.
