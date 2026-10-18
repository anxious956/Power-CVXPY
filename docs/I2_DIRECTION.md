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

## (a') result and the model fix (a''), 18 Oct 2026

**(a') stops: 0 % misdirected at every k.** Removing only the loads' negative-sequence path does not break direction.
At k = 0, dY2 is never enabled, but dY1 decides all 400 forward cases correctly (margin ≥ 66.6°), because the loads
are still passive in positive sequence. This is reported as a finding.

**The model was incomplete in two ways** (review session, cross-session message of 18 Oct 2026):
- An inverter-interfaced load is current-controlled in both sequences.
- The source inverter itself ran as a fixed phasor (nw.solve). The model matching gfl_avm (MODE2 = 0) in EMT is
  the V1-referenced fixed point, nw.solve_v1ref.

A fixed-current back side is degenerate, so the fix is:
- **(a'') model.** A share s of each load behind the relay (at R and S) becomes a V1-referenced current sink, drawing
  that share's pre-fault current, with open negative- and zero-sequence paths. The rest stays an impedance with
  y2 = y1. The source inverter is also V1-referenced. Everything is solved with nw.solve_v1ref; where it does not
  converge, relax 0.3 and 3000 iterations are used (relax changes the path, not the fixed point).
- s ∈ {0, 0.5, 0.8, 1}; laws suppressed and IEEE 2800 (K2 = 2).
- **Element.** As before (incremental dY2 enabling), plus absolute pickups |ΔI2| ≥ 0.05 pu for dY2 and
  |ΔI1| ≥ 0.05 pu for dY1, as 32-element supervision does. Misdirected (security) and undecided (dependability) are
  reported separately; misdirection is the failure that matters.
- **Not blind.** The review session ran this static check first. At s = 1, suppressed, it found 44 % of the hard
  forward set misdirected (68 % misdirected or undecided with the pickups), and 0 % under IEEE 2800.
  `src/i2dir_static.py a2` reproduces it here. **The blind test is EMT stage (c) at s = 1, suppressed**, with its
  GO criterion fixed now: the conventional element misdirects or leaves undecided at least ¼ of the hard forward
  set, through the relay's mimic chain.
- **Limitation, stated now.** gfl_avm holds ID / IQ. A real IEEE 2800 inverter also injects positive-sequence
  reactive current (ΔIq = K·ΔV1, K ≥ 2). That gives dY1 a reactive back-side source and would likely restore
  direction even under suppression. It is not modelled in the test case; it is reported as one static sensitivity.
- **Then (b)**: the δ design for direction at s = 1 on the solve_v1ref model.

## (a'') reproduced, and EMT stage (c) pre-registered (18 Oct 2026, before any run)

`src/i2dir_static.py a2` reproduces the review's static check (`results/network/i2dir_static_a2.json`). Suppressed law,
hard forward set, 16 corners:
- with no pickup: misdirected 0 / 0 / 0 / **0.44** at s = 0 / 0.5 / 0.8 / 1;
- with the 0.05 pu pickups at s = 1: **0.36 misdirected** (B-C 0.78, A-G 0.09) and 0.31 undecided.

IEEE 2800 gives 0 at every s, and the reverse set is 0 everywhere.

**Stage (c), EMT, the blind test.** It runs MODE2 0 and 1 first; MODE2 2 follows after the design (b).
- **Network:** s = 1, every load behind the relay inverter-interfaced. The R and S loads are replaced by two
  gfl_avm sinks.
  - The sinks always run MODE2 0 (open negative and zero sequence), whatever the source inverter's mode; a sink
    with an I2 law would put the passive path back.
  - Their ID / IQ come from the static operating point at the EMT case's source point.
  - They use TANG 15 Hz and i_max 10.
  - **Assumption:** the sinks hold their current through the fault, with no trip and no low-voltage blocking. Real
    drives may trip on deep sags; that is a limitation.
- **Source point:** nominal, one point. Cases: the hard forward set (25) and reverse set (25), for each law.
  - Each EMT case is compared with the static prediction for that exact case (solve_v1ref, same point). The
    16-corner fractions stay the static result.
  - First, one pre-fault run per law checks V1 at R and S and the sink currents against static (within a few
    percent), and the TANG lock.
- **Relay chain:** the step-3 front end, clean: mimic filter on the currents, pre-fault memory (windows ending 0.5–2.5
  cycles before inception) for the increments, one phasor frame for V and I. The element, with 0.05 pu pickups, is
  evaluated on windows ending 2.0, 2.25, …, 3.0 cycles after inception. The relay's decision is the first window
  that decides; a wrong first decision is a misdirection. White noise is a second pass.
- **Criteria, fixed now:**
  - the **claim is reproduced** if MODE2 0 has ≥ ¼ of the forward set misdirected or undecided, with misdirected
    reported separately;
  - the **fix is reproduced** if MODE2 1 has ≤ 5 % of the forward set misdirected;
  - **reverse** stays ≤ 5 % misdirected under both laws;
  - per case, where EMT disagrees with static is reported. The filtered reference turns the frames less in the
    decision window than the static fixed point does, which could reduce the misdirection; that is what EMT tests.

**Stage (b) scope, fixed now.**
- The sinks sit at their share of the nominal load, without box symbols, like the impedance loads now. This differs
  slightly from (a''), which set them per corner.
- The fixed point runs over three V1-referenced frames (I, SR, SS), with per-source unit maps. λ and drift are
  shared symbols across the three frames (identical TANG, same inception, one frequency), each frame turning with its
  own bus V1.
- Regression tests before use:
  - with s = 0, the generalised model reproduces the main configuration's sets to round-off;
  - at random source points and λ, the prediction agrees with solve_v1ref within the fitted remainder.
- **"Yes"** means every forward–reverse pair separated by 2ε(1 + ρ) at a δ within the limiter, at s = 1. The prior
  (row 46) predicts no.

**Additions before reading stage (c)'s results** (review of the stage-(c) code, 18 Oct 2026):
- **Pre-fault gate.** Each inverter's pre-fault |I1| must match the static operating point within ±3 % and be settled
  (0.25 s against 0.28 s). If it fails, the direction results are not interpreted.
- **Window stability.** Besides the first decided window, the decision at every window from 2.0 to 3.0 cycles is
  stored. Cases that flip are reported, since the early windows sit at the end of the filtered reference's
  transient.
- **Collapsed buses.** The sinks' own |V1| in the fault (their V1M channel) is reported. Cases below 0.2 pu are
  flagged, not dropped: a real drive would trip there.
- **One point on wave** (t_fault 0.30 s for every run) is a known limit. A repeat at a second inception angle on the
  misdirected cases would settle it.

## Stage (c) result, the IEEE 2800 instability, and the filter shunts (18 Oct 2026, before any further run)

**Suppressed law (MODE2 0), EMT, s = 1, without filter shunts.** The pre-fault gate passed (0.0 % on all three
inverters).
- Forward: **20 % misdirected + 60 % undecided = 80 %**, so the claim is reproduced (≥ ¼). Direction is lost mostly
  as no decision. Only 20 % go the wrong way, against 36 % misdirected in the static prediction for the same cases;
  the static "misdirects 44 %" is not the EMT result.
- Reverse: 0.
- These runs are free of the numerical mode below: peak |vA| in the fault is ≤ 1.01 × nominal and the 5–10 kHz energy
  share is ≤ 1.2·10⁻³.

**IEEE 2800 (MODE2 1) failed its pre-fault gate.** The run diverges numerically before any fault (from about 0.10 s).
The 56 % / 40 % misdirection figures from it are not results and are not quoted. The diagnostics
(`src/i2dir_diag.py`):
- The law is correct: injected I2 / V2 = 2.00 ∠ 89.8° in a stable unbalanced run, so row 46 and PR #27 stand.
- The divergence is not the V2 loop gain. K2 = 0.5 and 2 both diverge (×15–18 per cycle, a ~9 kHz component at
  K2 = 0.5). K2 = 1 grew ×9 within the run without diverging, possibly an early transient. MODE2 0 stays bounded.
- The cause, the review session's reading: at s = 1 the cut separating {R, S} from the rest crosses only the series
  R-L line L1 and current sources, an ill-posed cut-set. A current command that depends on V2 one step behind gives
  the trapezoidal rule's high-frequency chatter a loop to grow in. A real inverter bus always has an output-filter
  capacitor.

**The fix, fixed now: an RC filter shunt at each inverter bus.**
- **Sizing rule.** At each bus (R, S):
  - C is 0.05 pu of the inverters' ratings there. I is rated 1 pu; each sink's rating is its pre-fault current.
  - In series is a damping resistor R = 2ζ·√(X_th / B), with ζ = 0.3 and X_th the positive-sequence Thevenin
    reactance at the bus with the inverters open (R: L1 + zs; S: L1 + L2 + zs).
  - The shunt is wye, ungrounded, so it carries no zero sequence.
- **This is a passive negative-sequence path**, the thing whose absence the claim rests on. So (a'') is first
  re-predicted statically with the shunts: 16 corners, both laws, the 0.05 pu pickups. That prediction is recorded
  below before any EMT run, with the criteria unchanged. If the shunts restore direction statically, that is the
  finding (filter capacitors carry enough I2 on this network), and C is not tuned to keep the effect.
- **Stage (c) is then rerun on the same network for both laws** (MODE2 0 and 1, about 100 runs, in small batches).
  The MODE2 0 result above stays recorded as "without filter shunts".
- Diagnostic only: one normal MODE2 1 run at a 2 µs step, without shunts. If the mode moves with the step or goes
  away, it is numerical. A smaller step is not the fix.
- If MODE2 1 still diverges with the shunts, the fallback, registered now, is a first-order low-pass on the
  controller's V2 measurement.

**The static prediction with the filter shunts, recorded before any EMT run** (`src/i2dir_static.py a2f`,
`results/network/i2dir_static_a2_filters.json`). The shunts at s = 1 are R: B = 0.066 pu, R = 1.81 pu; S:
B = 0.029 pu, R = 3.26 pu. Hard forward set, 16 corners, misdirected / undecided:

| | no pickup | with the 0.05 pu pickups |
|---|---|---|
| suppressed, s = 1 | **1.00 / 0** | **0.55 / 0.27** (A-G 0.25, B-C 1.00 misdirected) |
| suppressed, s = 0.8 | 0 / 0 | 0 / 0.29 |
| IEEE 2800, s = 1 and 0.8 | 0 / 0 | 0 / 0 |

Reverse is 0 everywhere.

**The filter capacitors make direction worse under suppression, not better.** With no other negative-sequence path
behind the relay, the only one is capacitive. The element then sees the back-side impedance with the opposite sign
and calls forward faults reverse. IEEE 2800's current law still fixes direction completely. The EMT rerun (both laws,
with the shunts) tests this prediction under the criteria already fixed.

**Assumption that decides which case is physical, stated before the rerun** (review of 1c1c1fa). The shunt result
assumes **converter-side current control**: the averaged inverter regulates the current behind its filter, so the
capacitor sits outside the I2-suppression loop and is a passive path. With **grid-side current control** the
capacitor current is inside the loop, the terminal I2 is suppressed including the capacitor, and the back side is the
no-shunt case. The two EMT runs therefore bracket the two common control designs:
- no shunt = grid-side current control;
- shunt = converter-side current control.

Both are reported as such; neither is "the realistic one". (A SEL-type 32Q gives the same verdict as our element on
the shunt case: projected on the line angle, the measured Z2 is about +10 pu, far above any reverse setting.)

**Builder changes** (BUILD_VERSION 4, which changes every spec's digest: old outputs are simply not reused if old
specs are resubmitted):
- an optional "shunts" field {bus: {r_ohm, c_uF}}, built as three series R-C branches to a neutral tied to ground
  through 1e8 Ω, connected at the bus beside the inverters' ammeters;
- an optional per-spec solver step dt_us, with the output plot step kept at 50 µs;
- the fast-mode project key now includes the shunts, the step and the inverter set, so a project is never reused
  for another topology.

**The 2 µs diagnostic is dropped** (review of the builder commit). The inverter's DFT buffer holds at most 1700
samples (NMAX). At a 2 µs step a cycle needs 8333, so the window would clamp to about 0.2 cycle: a broken
sequence extraction, not a smaller step. Every step below about 9.8 µs is affected. Instead:
- if MODE2 1 with the shunts is stable at 10 µs, that already points to the undamped cut-set as the cause;
- the grid-side bracket's MODE2 1 (no shunt) then uses the registered fallback, a first-order low-pass on the
  controller's V2 measurement. It will be registered with its time constant before it runs.

Known limit of the shunt key: the fast-mode key carries the shunt buses, not their values, and update() does not set
them. This is harmless here, since every spec has the same shunts, but a study that varies them must add the values.

## Stage (c) with the filter shunts: the converter-side-control bracket (18 Oct 2026)

`results/network/i2dir_emt_sh.json`, 102 PSCAD runs at s = 1 with the RC shunts. Both laws passed the pre-fault gate
(0.0 % on all three inverters). The runs are free of the numerical mode: peak |vA| in the fault ≤ 1.00 × nominal and
5–10 kHz energy share ≤ 3·10⁻⁸. The shunts damp the cut-set, as diagnosed.

| | forward misdirected | forward undecided | reverse misdirected | EMT vs static, same cases |
|---|---|---|---|---|
| suppressed (MODE2 0) | **0.40** | 0.28 | 0.00 | 24 of 25 agree |
| IEEE 2800 (MODE2 1) | **0.00** | 0.00 | 0.00 | 25 of 25 agree |

Against the criteria fixed before the run:
- **the claim is reproduced**: suppressed loses 68 % of the forward set, 40 % misdirected;
- **the fix is reproduced**: IEEE 2800 misdirects 0 %;
- **reverse** is 0 under both;
- no case flips across the 2–3-cycle windows, and no sink's |V1| falls below 0.2 pu.

The static prediction for the 16 corners (0.55 / 0.27) and for these nominal cases (0.40 / 0.24) matches EMT closely.

**The two brackets together** (EMT with the source inverter's law as stated; s = 1, every load behind the relay
inverter-interfaced):

| control design | suppressed: forward lost (misdirected) | IEEE 2800 |
|---|---|---|
| grid-side current control (no shunt) | 80 % (20 %), mostly undecided | not yet run: needs the V2-filter fallback |
| converter-side current control (shunt) | 68 % (40 %) | **0 %** |

**Reading.**
- On an inverter-dominated back side, I2 suppression costs the relay its direction decision in EMT, under either
  control design.
- With the filter capacitors as the only passive path behind the relay, wrong-way decisions take the place of
  no-decisions.
- IEEE 2800's V2-referenced negative-sequence current restores direction completely in the bracket where it could
  be run.
- That is the deck's claim for the I2-suppressing case, now in EMT. The designed δ (MODE2 2) for direction is stage
  (b), still to come; row 46's static prior says it will not do this job.

**Scope and the narrowness of the regime** (review of e577755).
- The brackets table covers one three-bus network, the nominal source point, one point on wave, clean measurements,
  25 forward and 25 reverse cases, and **δ = 0: no auxiliary signal injected**. No verdict on δ comes from it; that
  is stage (b).
- The regime is narrow. On this network, suppression costs the relay its direction when nearly all of the load
  behind it is inverter-interfaced (s → 1). At s = 0.8 there are no misdirections, only about 28–29 % undecided, with
  or without shunts: dependability is lost, not security. The CIGRE row-46 case is this regime.
- gfl_avm holds ID / IQ, with no K-factor positive-sequence reactive current. That is still the first objection: such
  a current would give dY1 a reactive back-side source.

**The grid-side bracket's IEEE 2800 cell: the V2 filter, registered before it runs.**
- A first-order low-pass with TV2 = 1/(2π·15 Hz) on the controller's **demodulated V2 phasor** (its two components,
  as TANG filters the V1 angle), not on the abc voltages, so the 60 Hz law is unchanged. It is a new gfl_avm input,
  default 0. BUILD_VERSION goes to 5.
- **Stop rule:** if MODE2 1 without shunts still diverges at TV2 = 15 Hz, that cell is reported as "not runnable in
  this model". τ is not tuned further.
- **Regression:** one stored shunt-case MODE2 1 spec rerun with TV2 = 0 must reproduce its output to round-off.
- **Consistency across brackets:** 5 shunt-case MODE2 1 forward cases rerun with TV2 = 15 Hz must give the same
  decisions. Then the two IEEE 2800 cells differ only in control structure, not in the filter.
- The lag (τ ≈ 0.64 cycle, I2 at about 96 % by 2 cycles) keeps the static prediction applicable.

**Stage (b) will use the shunt bracket** (converter-side control), whose EMT is clean in both laws.

## The grid-side IEEE 2800 cell with the V2 filter (18 Oct 2026)

`src/i2dir_tv2.py`, `results/network/i2dir_tv2.json`, 57 PSCAD runs:
- **Regression** (BUILD_VERSION 5, TV2 = 0) against the stored i2s_m1_L1ag55r100: largest channel difference
  **0**.
- **Consistency:** 5 shunt-case MODE2 1 cases (4 forward, 1 reverse) with TV2 = 15 Hz: **5 of 5 decisions
  unchanged**.
- **Grid-side bracket, MODE2 1 with TV2:** stable (normal-run tail peak 1.15 × nominal, pre-fault |I1| errors 0.0 %),
  so the stop rule does not apply. Every fault run passes the per-run numerical check: **25 of 25 interpretable** on
  each side. **Forward misdirected 0 %, undecided 0 %; reverse 0 %**, and EMT agrees with static on every case.

**The brackets, complete** (EMT, s = 1, every load behind the relay inverter-interfaced; nominal source point, one
point on wave, clean measurements, 25 forward and 25 reverse cases, δ = 0):

| control design | suppressed I2: forward lost (of which misdirected) | IEEE 2800 V2-referenced I2: forward lost |
|---|---|---|
| grid-side current control (no shunt) | 80 % (20 %) | **0 %** (with the V2 filter) |
| converter-side current control (filter shunt) | 68 % (40 %) | **0 %** |

**Reading.** On an inverter-dominated back side (s → 1), I2-suppressing inverters cost the relay at the inverter bus
its direction decision in EMT, under either control design:
- with grid-side current control, mostly as no decision;
- with the filter capacitor as the only passive path, mostly as wrong-way decisions.

The grid-code V2-referenced negative-sequence current restores direction completely in both. The regime is narrow: at
s = 0.8 suppression costs only dependability (about 28 % undecided, no misdirection). The positive-sequence
reactive-current response (K-factor) is not modelled. No δ was injected; whether a designed δ can do this job is
stage (b).

## Stage (b): the designed δ for direction, pre-registered (18 Oct 2026, before the design runs)

**Model** (`src/frames_multi.py`). The two-frame model with several V1-referenced current sources:
- the source inverter I, with the box of the source symbols, injecting δ in its own frame;
- the sinks SR and SS, with fixed commands from the all-impedance operating point the EMT runs used.

The fixed point runs over all three frames. λ and drift are shared symbols. Network: s = 1 with the filter shunts
(the converter-side-control bracket, clean in EMT under both laws), the source inverter suppressing I2.

**Regressions, all passed** (`src/i2dir_design.py regress`):
1. with no sinks, the sets equal frames.FrameModel's on the step-3 network: largest difference in (c, G) 1·10⁻¹³;
2. at δ = 0, the nominal point, settled frames, the relay measurements equal solve_v1ref's: 5·10⁻¹³ pu over normal
   operation and 10 faults;
3. the same at three random source points: ≤ 7·10⁻¹³ pu.

**"Yes" means:** every forward–reverse pair of case sets separated by 2ε(1 + ρ) with ρ = 0.1, at a δ within the
1.14 pu cap, at s = 1. ρ = 0 is reported too. The main configuration applies otherwise (ε = 0.08 pu box, φ_ref
0.0303 rad, model error 0.008 pu, drift 3°). The forward set is A-G at 20–40 Ω and B-C at arc on L1; the reverse set
is the same on L2. The prior (REVIEW row 46, static, CIGRE) says a δ fixed in the inverter's frame does not repair
direction.

**Additions before the first design number** (review session, 18 Oct 2026):
1. **Noise model.** Primary: the 0.08 pu box, the step-3 design point's main configuration. Secondary: the
   structured design tier (CT 1 % / 0.3°, VT 0.5 % / 0.3° as shared symbols, white box V 0.02 / I 0.04 pu).
2. **δ = 0 first.** The pairwise forward–reverse separation at δ = 0 is reported before any search. If every pair is
   already apart, δ* = 0 and the finding is "the set test decides direction here without δ".
3. **Two questions, kept apart.**
   - **(b1)** The set test: the smallest |δ| within the cap for which every forward–reverse pair is 2ε(1 + ρ)
     apart, ρ = 0.1 and 0. That gives a set-based direction decision, a new detector.
   - **(b2)** The conventional element at that δ: does direction_pk on the injected measurements get the forward set
     right? Static at the 16 corners first, then EMT with MODE2 2.

   Row 46's prior is about (b2). A yes on (b1) with a no on (b2) is a legitimate result, and they are not merged.
4. **The search.** The full polar grid: 5° over 360°, 0.02 pu steps up to the 1.14 pu cap. The whole set of
   separating angles at δ* is recorded.

A fourth regression, at δ ≠ 0 (0.5 and 1.0 pu, three angles, random points), also agrees with solve_v1ref: ≤ 2·10⁻¹²
pu. The multi-frame fixed point falls back to under-relaxed iteration where plain iteration swings between frames;
the fixed point is unchanged.
