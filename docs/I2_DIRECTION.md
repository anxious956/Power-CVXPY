# The I2-suppressing inverter with δ injected: direction at the inverter's relay (plan)

18 Oct 2026. The meeting deck named three places where Taylor's method "could still matter": I2-suppressing
inverters, longer lines and grid-forming inverters. PLAN.md §6 owes "an EMT study with δ injected" there. The
I2-suppressing case has only a static screen so far, on CIGRE MV (REVIEW.md §7 row 46):
- suppression breaks direction at inverter buses;
- a δ fixed in the inverter's V1 frame did not repair it at any of the 48 settings tried;
- a V2-referenced current (IEEE 2800's rule) did.

This study closes that item on the step-3 three-bus network, with δ injected in EMT. It was recommended by the review
session (cross-session message, 18 Oct 2026).

## Set-up

- **Network:** the step-3 three-bus network. The relay sits at bus R on line L1, looking towards L: the relay next to
  the inverter. Behind it are the inverter at R, line L2 and the load at S; in front is L1 and the synchronous
  source at L.
  - **Forward** faults are on L1. Their negative-sequence current at the relay comes from behind, where the
    inverter is.
  - **Reverse** faults are on L2. Their negative-sequence current comes through the relay from the source at L.
- **The inverter's negative-sequence law** (the PSCAD model's MODE2):
  - 0, suppressed: I2 = 0, open negative-sequence path;
  - 1, IEEE 2800: I2 = j K2 V2, K2 = 2, a negative-sequence shunt j/K2 in the static model;
  - 2, designed δ: suppressed plus δ in the inverter's V1 frame, with the filtered reference (TANG 15 Hz).
- **Conventional direction element**, as in `src/review/i2_suppressed_direction.py` (Opoku et al. 2025):
  - ΔY2: forward when arg(ΔI2 / ΔV2) is in (45°, 225°), enabled when |I2| ≥ 0.1 |I1|;
  - otherwise ΔY1, the same test on ΔI1 / ΔV1, enabled when |ΔV1| ≥ 5 %.
  - A forward fault must be called forward, a reverse fault must not; no decision counts as wrong.
- **Hard set:** forward A-G and B-C faults on L1, R_f 20–40 Ω for A-G and arc only for B-C, at the 16 corners of the
  source box.
- **Design for direction:** two fault sets instead of a fault set against N, Taylor's general two-hypothesis form.
  δ* is the smallest δ for which every forward case's set and every reverse case's set are apart by 2ε(1 + ρ). This
  uses the same two-frame model as step 3, the main configuration (ε = 0.08 pu box, φ_ref 0.0303 rad, model error
  0.008 pu, drift 3°) and the 1.14 pu cap. This set-vs-set machinery is also what selectivity (T2) would need later.

## Go / no-go, written before anything runs

- **(a) Is there something to fix?** With MODE2 = 0 at δ = 0, the conventional element misdirects (wrong or no
  decision) at least a quarter of the hard forward set over the source-box corners. *Static.* If not: stop, and
  report that suppression does not break direction on this network.
- **(b) Can a designed δ fix it?** The static set-vs-set design finds a δ within the cap, at ρ = 0.1 (reported also
  at ρ = 0). If not: stop, and report "a designed δ cannot certify direction here within the inverter's limit". That
  also closes the item.
- **(c) EMT.** If (a) and (b) hold: about 50 PSCAD runs comparing MODE2 = 0 / 1 / 2 on the hard set and its reverse
  counterpart, at the design δ, through the relay's mimic chain. Measured:
  - the conventional element under each law;
  - D1 for direction, i.e. which set the measurement lies in.

The prior from row 46 predicts "no" at (b). Then the result is "V2-referenced current (a grid-code requirement) fixes
direction, a designed δ does not", now on this network and, if it gets that far, in EMT.

Code: `src/i2dir_static.py` (stages a and b), `results/network/i2dir_static.json`.
