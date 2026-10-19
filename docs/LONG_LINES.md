# Longer lines: does the designed δ matter more for detection? (plan, pre-registered 19 Oct 2026)

The second of the deck's three "where your method could still matter" scenarios (docs/PLAN.md §6). The deck's claim:
δ should matter more on longer lines. The CIGRE reach screen (REVIEW.md §7 row 47: static, coarse, up to 3×) did not
support it for the zone-1 reach question; longer lines helped the passive measurement more than δ. This scenario
tests the claim for the **step-3 detection question**, fault against normal operation, in EMT with δ injected.

Everything below is written before any code runs. Labels as before: static vs EMT, one network, nominal source
point, and no δ verdict from runs without injection.

## 1. Change one thing

The three-bus grid in its step-3 main configuration (`src/pscad_network.py three_bus`, `docs/STEP3.md`,
`src/frames_main.py`): the weak synchronous source at L (zs 0.4j / 0.4j / 0.8j pu), the relay at L looking into L1,
the inverter at R (I1 command 0.45 pu ∠ −15°, i_max 1.2, LIM 1, δ in its own V1 frame through the 15 Hz reference
filter), constant-impedance loads at R (0.30 − 0.09j pu) and S (0.55 − 0.17j pu), 10 MVA / 20 kV base (Z_base
40 Ω), the step-3 hard set, the relay chain (mimic filter, memory frame, windows ending 2–3 cycles after inception)
and the two noise tiers.

A **length factor k_L multiplies z1, z2 and their zero-sequence impedances together**, k_L ∈ {1, 2, 4, 8}:

| | z1 (L1, pu) | z2 (L2, pu) | z0 | at k_L = 1 in ohms |
|---|---|---|---|---|
| k_L × | 0.02 + 0.20j | 0.025 + 0.25j | 3 × the positive sequence | L1: 0.8 + 8j Ω |

Nothing else moves: sources, loads, inverter command, relay, tiers. **R_f stays in ohms** (rF = 1 pu = 40 Ω), so
only the line changes and the fault resistance becomes relatively smaller against it, which is what "longer" means
for a relay.

**Line model.** The EMT lines are lumped series R-L per phase with a neutral return (z0 − z1)/3
(`pscad_network._rl`), and the static model is the same lumped impedance. Shunt charging is neglected. The model's
X/R of 10 is a transmission-type line placed at 20 kV; the per-kilometre reading is nominal. With an overhead-line
charging of about 3 nF/km and 8 Ω ≈ 20 km at k_L = 1, the charging current at k_L = 8 (about 160 km) is roughly
2–3 A per phase against a load current of about 250 A, so the lumped model stays numerically tenable at every k_L
for an overhead line, though 160 km of radial 20 kV is not a credible feeder. For a cable feeder (0.2–0.4 µF/km)
charging reaches about a tenth of the load current between k_L = 2 and 4, and beyond that the lumped model is not
tenable. The result is read as an overhead-line abstraction.

**Pre-flight at each k_L** (not a result; decides which k_L are in): the pre-fault load flow converges
(`network.solve_v1ref` with the inverter V1-referenced) and every bus voltage lies within 0.9–1.1 pu. A k_L that
fails is out and said so (the CIGRE screen lost 10× this way). Expectation written now: 0.85 pu of constant-impedance
load fed through k_L × 0.2 pu of reactance from a 0.4 pu source, with 0.45 pu from the inverter at R, will likely
leave the window at k_L = 8 and possibly at 4. If k_L = 4 fails, k_L = 3 is added so the curve has at least three
points; this fallback is fixed now, not chosen after the fact. If 8 fails as well, the set is {1, 2, 3, 4} or
{1, 2, 3}: the curve is read as far as pre-flight allows, and the "never misses a quarter" branch of the go/no-go
is then conditional on that set, which the verdict must say.

Also recomputed per k_L and reported, by the main configuration's own rules (`frames_main.py`):
- φ_ref = k σ_white / (√n_mem · min|V1_L|) with k = 4, σ_white = 0.01 pu, n_mem = 3 cycles: min|V1_L| changes with
  the load flow, so φ_ref changes;
- the model-error box stays at 0.1 ε = 0.008 pu, **measured at k_L = 1 only** (`frames_emt_check.py`); the EMT step
  (§4, question 3) re-measures it at the chosen k_L through containment.

## 2. The prior, from the two-bus theory

In the affine model the relay's measurement in state s is y = c_s + H_s δ + G_s u (DESIGN.md §2.1: δ shifts the
centre, u spans the source box). Fault F separates from normal N when

  Δc + ΔH δ  escapes the zonotope  G_N u_N − G_F u_F + noise,  Δc = c_F − c_N,  ΔH = H_F − H_N.

Δc is the fault's own signature at the relay; ΔH δ is δ's **differential leverage**: how differently the faulted and
the normal network route the signal, injected at R, to the relay at L. Both are current divisions at the fault
point F, at fraction m of L1 from the relay:

- The fault's signature from the source side scales with 1 / (m k_L z1 + zs + fault terms). For faults far from the
  relay (large m) it falls with k_L; for faults close to the relay (small m) it is set by zs and R_f and barely
  moves.
- δ must traverse the whole line to reach the relay. In normal operation the relay's share of δ is the source path
  against the loads, ~ Y_src / (Y_src + Y_load), Y_src = 1 / (k_L z1 + zs); in the fault the branch at F diverts
  part of it. Both shares fall as k_L grows, so **|ΔH| falls at the full-line rate ~ 1 / |k_L z1 + zs| for every
  fault**, bolted ones included (approximately: for a bolted A-G fault the fault takes nearly all of δ and ΔH is
  about the whole normal share; for a bolted B-C fault the negative-sequence network at F connects to the
  positive-sequence network, not to ground, so δ is not simply shunted; the direction of the prior stands).

So longer lines weaken both terms. The deck's claim needs the conventional element to fail (Δc below its pickup)
while δ still has enough leverage within the cap. The prior from the terms above:
1. The conventional element loses far-end, high-R_f faults first, since their signature falls with k_L.
2. δ's leverage falls for every fault at the full-line rate, so the leverage-to-signature ratio falls for near
   faults and stays roughly flat for far ones. δ*(k_L) is expected **non-decreasing**.
3. At k_L = 1 the step-3 design point is already 1.12 pu against the 1.14 pu cap (`docs/STEP3.md`, ρ 0.1, main
   configuration). Any growth of δ* with k_L leaves the cap at k_L = 2 unless the changed load flow moves the
   normal set in δ's favour.

The prior therefore leans to **"does not hold"** under the box tier: δ* is expected to leave the cap before the
conventional element misses a quarter of the hard set. The test decides.

**Per tier.** At k_L = 1 the box tier (main configuration) is already at 1.12 pu against the 1.14 pu cap, so its
verdict is nearly decided by construction, and carries little information about the claim. The structured design
tier needs no δ at k_L = 1 (review/STEP3_STRUCTURED_REVIEW.md §3: "design tier needs no δ; class tier needs
1.12 pu"), so it is the tier where δ*(k_L) can rise from zero and the claim can show. The verdict is given per
tier: the box tier primary, as in step 3, the structured design tier reported with equal weight. Theorem 1 (TAC25) states a necessary condition
‖θ‖ ≥ (1 − ζ)/χ with χ from the leverage matrices and ζ from the model difference; longer lines lower both, the
theorem gives no sign for their ratio, and on this box-bounded uncertainty it is vacuous anyway (DESIGN.md §2). It
is not used as a prediction.

## 3. Registered questions

**Hard set:** the step-3 cases (`network_delta_test.CASES`): A-G and B-C on L1 at m 0.15 / 0.35 / 0.55 / 0.75 / 0.95
and on L2 at 0.05 / 0.25 / 0.5, each at R_f/rF 0 / 0.5 / 1.0 (0 / 20 / 40 Ω): 48 cases. Fault against normal
operation (detection), as in step 3.

**Q1. Static, 16 corners, at each k_L (`static`).** On the hard set, at δ = 0:
- the conventional incremental element D0 = max(3|ΔI0|, |ΔI2|) at the HIGHR pickup policy, **0.162 pu**: the
  value `src/highr_screen.py` used, the upper end of the D0 pickup calibrated on the pilot at the **design tier**
  (0.126–0.162 pu, results/step3/pilot_eval.json); the lower end 0.126 pu is reported as a sensitivity, not a
  second verdict. A case is missed when D0 is below the pickup at any of the 16 corners;
- D1, the set test, at δ = 0: the distance of a corner measurement to the normal set N(0), in noise boxes (ε per
  component; structured tier reported too). Both fractions are reported, as review/HIGHR_REVIEW.md §3 did:
  **alarm** (distance > 1 box) and **guaranteed** (> 2 boxes). The registered "missed" uses the guaranteed one: a
  case is missed when any corner is within 2 boxes of N(0).
- Where, in location m and R_f, does the conventional element first fail as k_L grows?

**Q2. δ*(k_L) (`design`).** The step-3 set-vs-set design, fault against normal, `frames.FrameModel` on the scaled
network, main configuration (factor 1.1, drift 3°, φ_ref per k_L, model error 0.008 pu), ρ 0.1 (ρ 0 reported),
**both tiers**, the full polar search (5° × 0.02 pu to the 1.14 pu cap) with the set of separating angles at δ*.
At each k_L: the δ = 0 unseparated count, δ*, the margin at every separating angle at δ* (the smallest
fault-vs-normal gap minus 2(1 + ρ), in ε units), the price (the inverter's delivered |I1| in normal operation under
LIM 1 at δ*, against the 0.45 pu command), and dead frames at δ*. **The carried angle** at δ* is the separating
angle with the largest margin (fixed now; step 3 chose inside its window by hand).

Corner measurements in Q1 are clean (nominal instruments): the structured tier's instrument errors live in its
sets, so its D1 distance is "clean measurement against the structured normal set".

**Q3. EMT (`spec` / `analyse`).** Two halves, each at the k_L where what it tests exists (review):
- **the δ* half**, 49 runs (the 48 cases plus the normal run) with δ* injected (MODE2 2, LIM 1, TANG 15 Hz), at
  **the largest k_L where δ* is feasible within the cap** (per tier; the box tier's δ* is injected, the structured
  tier's δ* too if it differs and is non-zero), so the step-3 EMT design check has a pass/fail criterion where the
  guarantee exists;
- **the δ = 0 half**, 49 runs, at **the smallest k_L where D0 misses ≥ ¼ of the hard set in Q1** (12 of 48); if it
  never does, at k_L = 4, or at the largest k_L in the pre-flight set if 4 is out. This gives the (b0)-style point
  separation and D0 in EMT where the conventional element fails.
- If the two k_L coincide, it is one network and about 100 runs; if not, two networks and still about 100 runs.
  The reading of "holds" is unchanged either way: the claim needs both at the same k_L, which the static curve
  decides. No run at the cap when δ* is infeasible: "best angle" has no definition when no angle separates.

Nominal source point, PSCAD fast mode, stage-(c) gates: pre-fault |I1| and |I2| within 3 % of static and settled;
per-run peak and 5–10 kHz checks; the weak-frame flag on the **source inverter's own |V1| at R** below 0.2 pu (there
are no sinks in the step-3 configuration), read separately, not excluded. Read on the same runs:
- **the step-3 EMT design check:** each window (2–3 cycles after inception, memory frame) contained in its own
  case set (distance to the design's own-case set ≤ 0.1 ε) and separated from N(δ*) by more than 2(1 + ρ) minus
  the own distance. The distance to the **bare** own-case set (factor 1, no reference noise, no model-error box) is
  reported beside it: that is the model error re-measured at this k_L, to be compared with the 0.1 ε box carried
  from k_L = 1;
- **the conventional element** D0 at 0.162 pu on the same windows, with and without δ;
- **D1 at δ = 0** on the δ = 0 runs: point separation from N(0).

## 4. Go / no-go, fixed now

A verdict **per tier** (box primary, structured design tier with equal weight; §2 says why the box verdict carries
little information):
- **"The deck's claim holds for detection"** if some k_L ≤ 8 (in the pre-flight set) has the conventional element
  missing ≥ ¼ of the hard set in Q1 while δ*(k_L) is feasible within the 1.14 pu cap in Q2 and holds in EMT in Q3
  (every clean run contained and separated).
- **"Does not hold"** if δ* leaves the cap at a smaller k_L than the one where the conventional element first misses
  a quarter, or if the conventional element never misses a quarter up to the largest k_L in the set (then stated
  as conditional on the pre-flight set).
- The whole k_L curve is reported either way: Q1 miss fractions by element, Q2 δ*, margin, price, unseparated
  count, and the δ = 0 point separation of the EMT runs.
- Stop rules: no re-tuning of angle, pickup or tier after a result; a k_L that fails pre-flight is out, not
  patched; no δ verdict from the δ = 0 runs.

## Pre-flight result, and a registration error (19 Oct 2026, before Q1 is read)

`src/longlines.py preflight` → `results/network/longlines_preflight.json`. The pre-fault load flow converges at
every k_L (37–68 iterations) and the inverter delivers its 0.447 pu command everywhere (no limiter action):

| k_L | V1 at L (relay) | R (inverter) | S | 0.9–1.1 window |
|---|---|---|---|---|
| 1 | 0.905 | 0.857 | 0.805 | out (R, S) |
| 2 | 0.907 | 0.813 | 0.711 | out |
| 3 | 0.914 | 0.785 | 0.636 | out |
| 4 | 0.923 | 0.770 | 0.576 | out |
| 8 | 0.952 | 0.776 | 0.431 | out |

**The registered window excludes k_L = 1, the step-3 network itself.** The base network is a weak-source radial
with S at 0.805 pu; the 0.9–1.1 window was taken from the CIGRE screen and not checked against the base before it
was registered. That is an error in the registration, not a finding about long lines. Since the loads are constant
impedances they shed power as the voltage falls (P ∝ V²): at k_L = 8 the S load runs at 29 % of its rating, so
"the same loads" no longer holds there either.

The rule is being re-fixed **from this table alone, before any Q1 number is read**, by the review session, among:
- A: every bus within 0.7–1.1 pu → {1, 2};
- B: every load's delivered power within −25 % of its k_L = 1 value (V ≥ 0.866 × base) → {1, 2};
- C: the window on the relay bus L only → all five, with S at 0.43 pu flagged as not a credible operating point.
If the set is {1, 2}, k_L = 1.5 is proposed as the fallback instead of 3. Q1 is computed at every k_L for
information meanwhile; it does not depend on the rule.

**A second pre-flight condition, found while computing φ_ref.** The frame model needs a settled inverter frame at
every source-box sample point. On the φ_ref probe (2032 points) and the hard set's fault states (48 × 344 points),
plain fixed-point iteration (`frames.fixed_point`, as step 3 ran it):

| k_L | normal state, plain iteration fails | under-relaxed (0.5 / 0.25) | fault states, plain iteration fails |
|---|---|---|---|
| 1 | 0 of 2032 | — | 0 of 16 512 |
| 2 | 0 | — | 0 |
| 3 | 0 | — | 77 |
| 4 | 0 | — | 286 |
| 8 | 204 | still 204, and the two relaxations disagree (2.0) | 3 217 |

- `frames.fixed_point` now falls back to under-relaxed iteration (0.5 then 0.25) where plain iteration does not
  converge, exactly as `FrameModelMulti._fixed` (reviewed in the I2 study: relaxation changes the path, not the
  fixed point). It never runs where plain iteration converges, so k_L = 1 and 2, and every step-3 result, are
  unchanged by construction. Checked: `i2dir_design.py regress` after the change gives 3.1·10⁻¹³ (FrameModel vs
  FrameModelMulti at 1.12 pu) and ≤ 7.4·10⁻¹³ pu against solve_v1ref, as before.
- **k_L = 8 has no model**: at 10 % of the source points the inverter's frame has no fixed point even
  under-relaxed. It is out on this condition alone, whatever the voltage rule. The condition is added to the
  pre-flight ("the frame settles at every probe point") as a model requirement, not a design choice.
- **k_L = 3 and 4 have fault states with no settled frame at the source corners** (even under-relaxed), all at the
  inverter's high-current corners (i_mag = +1, i_ang = +1), on faults close to the relay: k_L 3, 10 of 768
  (case, corner) points, L1 B-C bolted at m 0.15 / 0.35 / 0.55; k_L 4, 30 of 768, adding L1 A-G bolted at 0.15 /
  0.35, B-C at 20 Ω at 0.15 / 0.35 / 0.55 and B-C bolted at 0.75. k_L 1 and 2 have none. Where this happens the
  V1-referenced inverter has no steady state, so the set test has no fault set to build; Q1 counts these corner
  points and leaves them out of that case's statistics, and the k_L is flagged as partially modelled. Together with
  the voltage table this puts k_L 3 and 4 out on two grounds under rules A or B.

## 5. Caveats carried on every line

One network (three-bus, weak source, X/R 10); nominal source point in EMT; one point on wave; clean runs; the lumped
R-L line (overhead abstraction); the step-3 relay chain and noise tiers; the model-error box measured at k_L = 1.
