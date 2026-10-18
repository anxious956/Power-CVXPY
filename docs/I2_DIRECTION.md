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

## Stage (a) result, and the re-stated test (18 Oct 2026, before anything else runs)

**(a) stops on the network as built.** With constant-impedance loads behind the relay, I2 suppression does not break
direction:
- 0 % of the hard forward set and 0 % of the reverse set misdirected, under both laws;
- dY2 enabled on every fault, |I2| / |I1| ≥ 0.103;
- angle margins ≥ 46.9°.

The reason is that the passive loads at R and S, behind the relay, carry the negative-sequence current. Removing them
leaves the relay with no decision. This is a finding, reported as it stands (`results/network/i2dir_static_a.json`).

**The deck's scenario is the other regime**: an inverter-dominated back side with no passive negative-sequence path,
as at the CIGRE MV relays where suppression broke direction (REVIEW.md §7 row 46). The review session endorsed one
physical parameter, fixed now, before running:
- **k, the negative-sequence share of the loads behind the relay**: y2 = k·y1 at R and S, with y1 unchanged (so
  the pre-fault flow does not change);
- k ∈ {1, 0.5, 0.2, 0}. k = 1 is a passive constant-impedance load (as built); k = 0 is inverter-interfaced load
  (drives, rectifiers, chargers) that draws no I2;
- the reverse faults are unaffected, since their I2 comes from the source side.

The element's enabling test becomes incremental: dY2 when |ΔI2| ≥ 0.1 |ΔI1|, else dY1, as in Opoku's superimposed
element. With δ injected, a standing I2 would otherwise keep dY2 enabled all the time. At δ = 0 nothing changes;
(a) is re-run with it. With δ > 0, ΔI2 includes δ's own change in the fault (the frame's turn), which is what the
relay sees.

**(a') go / no-go:**
- the misdirected-or-undecided fraction on the hard forward set for each k, suppressed and IEEE 2800 laws;
- **the pre-registered test case is k = 0**: all load behind the relay inverter-interfaced, the CIGRE-like case;
- **GO if k = 0 gives ≥ ¼** for the suppressed law. The whole k curve is reported either way.

Then (b), the set-vs-set design at k = 0, and (c), EMT. In EMT the inverter-interfaced load is a second gfl_avm drawing
current (negative ID, IQ for its reactive part, MODE2 = 0, the same TANG), because wye R-L loads have k = 1 by
construction.
