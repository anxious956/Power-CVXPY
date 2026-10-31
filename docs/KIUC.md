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

- **Reproduction holds** if in EMT (Q2), at R2, the 32QG declares forward on ≥ 90 % of the forward set in the
  IEEE 2800 mode and declares nothing or reverse on ≥ 50 % of it in the suppressed mode, and 3I2 > 10 % I1 holds in
  the IEEE 2800 mode on every case and fails in the suppressed mode on most (≥ 70 %). Partial outcomes are reported
  as such; a failure at the pre-flight sanity check is a model problem, not a finding.
- **δ on this system**: reported per design with the same wording as before: whether δ* exists within the cap,
  its price, and whether it holds in EMT (consistent with, not confirmed); whether the conventional elements change
  with δ. The prior from step 3 and I2_DIRECTION is "δ buys the guarantee, not the decision"; a different outcome
  here is the finding.
- Stop rules: no re-tuning of thresholds after a result; assumptions stay as registered with their sensitivities
  reported; no δ verdict from runs without injection.

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
