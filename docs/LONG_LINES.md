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

The rule was re-fixed **from this table alone, before any Q1 number was read** (the review session did not open
the Q1 section), among A: every bus within 0.7–1.1 pu; B: every load's delivered power within −25 % of its k_L = 1
value; C: the window on the relay bus L only.

**Registered rule, B** (registration deviation, 19 Oct 2026; reason: the 0.9–1.1 window was taken from the CIGRE
screen without checking the base network, a weak radial with S already at 0.805 pu): a k_L is in if
- the pre-fault load flow converges (solve_v1ref, V1-referenced inverter);
- every load keeps at least 75 % of its k_L = 1 power (constant impedance: (V/V₁)² ≥ 0.75, V ≥ 0.866 × base) and no
  bus exceeds 1.1 pu. A feeder whose loads lose more than a quarter of their power is not operated that way, so the
  model stops standing for anything;
- the inverter frame settles at every φ_ref probe point and at every (case, corner) of the hard set.
The fallback is **k_L = 1.5** (not 3) when the set has fewer than three points; 2.5 is not added (S would sit near
0.67 pu, under the rule). The pre-flight table reports the delivered load power P/P₁ at R and S and the count of
unsettled (case, corner) points per k_L.

**Consequence for the go/no-go.** The curve covers 1–2× only, and the limit comes from the base network's load
flow, not from the claim. The "never misses a quarter" branch therefore reads "up to 2× on this network", and the
verdict says that a longer range would need a stiffer source or lighter loads: a second network, not this
scenario, and not run now.

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

### Pre-flight under rule B, and Q1 (19 Oct 2026)

`src/longlines.py preflight` → `results/network/longlines_preflight.json`:

| k_L | V1 at L / R / S | load P/P₁ at R / S | unsettled (case, corner) points | φ_ref (rad) | in |
|---|---|---|---|---|---|
| 1 | 0.905 / 0.857 / 0.805 | 1.000 / 1.000 | 0 | 0.0303 | yes |
| 1.5 (fallback) | 0.905 / 0.833 / 0.755 | 0.945 / 0.881 | 0 | 0.0302 | yes |
| 2 | 0.907 / 0.813 / 0.711 | 0.901 / 0.780 | 0 | 0.0300 | yes, by a hair at S (0.780 vs 0.75) |
| 4 (outside the set; the model does not stand here) | 0.923 / 0.770 / 0.576 | 0.807 / 0.513 | 30 | 0.0303 | no (S power, unsettled frames) |
| 8 (outside the set; no model) | 0.952 / 0.776 / 0.431 | 0.820 / 0.287 | — | — | no (S power, no model) |

k_L = 3 (evaluated before the rule was fixed) would fail too: S at 0.636 (P/P₁ 0.62) and 10 unsettled points.
**The set is {1, 1.5, 2}.** φ_ref barely moves (0.0300–0.0303 rad), since the relay bus L stays at 0.905–0.907.

**Q1** (`src/longlines.py static` → `results/network/longlines_static.json`; 16 corners, δ = 0, hard set of 48; a
case is missed when any corner misses; k_L 3 and 4 kept as information from the earlier `--all` run, with their
unsettled corner points left out):

| k_L | D0 missed at 0.162 pu (at 0.126) | D1 box, alarm / guaranteed missed | D1 structured, alarm / guaranteed |
|---|---|---|---|
| **1** | 0 of 48 (0) | 0 / 7 | 0 / 0 |
| **1.5** | 0 (0) | 0 / 11 | 0 / 0 |
| **2** | 0 (0) | 1 / 14 | 0 / 0 |
| 3 (info) | 3 (1): L2 B-C m 0.25 at 40 Ω, m 0.5 at 20 and 40 Ω | 7 / 23 | 0 / 1 |
| 4 (info) | 8 (4): L2 B-C at 0.05–0.5 (all R_f but two), L1 B-C m 0.95 at 40 Ω | 14 / 30 | 0 / 10 |

- **On the registered set the conventional element misses nothing**, at either pickup, so the "misses ≥ ¼" branch
  of the go/no-go is not reached up to 2× on this network. The k_L 3 and 4 rows are **outside the pre-flight set;
  the model does not stand there**: their first failures (far-end, high-R_f B-C faults on L2) support the prior's
  direction but are not results.
- D1's guaranteed-miss count under the box tier grows with k_L (7 → 11 → 14): the δ = 0 design gets harder with the
  line while the conventional element does not notice. δ*(k_L) in Q2 is the quantity that tells whether δ keeps
  up. Under the structured tier the count stays at 0.
- k_L = 2 passes rule B by a hair at S (P/P₁ 0.780 against 0.75).
- Q3's δ = 0 half therefore goes to k_L = 2, the largest in the set, as registered.

**Verdict on the registered criterion, written 19 Oct 2026 before Q2 finished.** The "holds" branch needs the
conventional element to miss at least a quarter of the hard set at some k_L in the pre-flight set, and it misses
0 of 48 at k_L 1, 1.5 and 2. So, for both tiers, **the deck's claim does not hold for detection up to 2× on this
network**, whatever Q2 and Q3 give. A longer range would need a stiffer source or lighter loads, a second network,
not this scenario. Q2 and Q3 still run as registered: the curve δ*(k_L), margin, price and the δ = 0 unseparated
count, then the two EMT halves, are the deliverable, read as information and not as a second chance at the verdict.
Static model; nothing injected yet.

### Q3, the δ = 0 half at k_L = 2 (19 Oct 2026, EMT, no injection)

`src/longlines.py spec zero 2` / `analyse zero 2` → `results/network/longlines_emt_zero2.json`. 49 PSCAD runs (the 48
cases and the normal run), k_L = 2, MODE2 0, TANG 15 Hz, nominal source point, the scaled line built as its own
project (`key_extra`). Pre-fault gate passed: |I1| 0.447 pu, 0.0 % from static. All 48 fault runs numerically clean;
no weak frame.

| tier | contained in own set (main, ≤ 0.1 ε) | bare-set model error, largest | separated from N(0) by 2(1 + ρ) | nearest N | D1 missed, alarm / guaranteed |
|---|---|---|---|---|---|
| box 0.08 | 48 of 48 | **0.000 ε** | 39 of 48 | 1.30 ε | 0 / 7 |
| structured | 48 of 48 | 0.000 ε | 48 of 48 | 3.72 ε | 0 / 0 |

D0 at 0.162 pu: 0 of 48 missed, on the clean tier and on the design tier (seed 7).

- **The model error re-measured at k_L = 2 is 0.000 ε** on every window of every run: the 0.1 ε box carried from
  k_L = 1 is not used. The lumped-line scaling introduces no new static-vs-EMT error at the nominal point.
- Point separation at δ = 0 under the box tier: 39 of 48 runs clear the design margin, 7 are within 2 boxes of
  N(0) (guaranteed-missed) and 9 within 2.2 ε. The static 16-corner count was 14 guaranteed-missed; the nominal
  point is inside that. Under the structured tier every run clears by at least 3.72 ε.
- D0 misses nothing in EMT at k_L = 2, as in the static Q1.

### Q3, the δ* half, box tier, at k_L = 1 (19 Oct 2026, EMT, δ injected)

Q2's box-tier keys (below, when complete) give δ* within the cap at k_L = 1 and none at 1.5 (ρ 0.1), so the box
tier's δ* half runs at **k_L = 1: 1.12 pu at 230°**, the carried angle by the registered largest-margin rule
(margin 0.031 ε; step 3 chose 225° by hand inside the same {225°, 230°} window). `spec dstar 1 box` / `analyse
dstar 1 box` → `results/network/longlines_emt_dstar1_box.json`. 49 PSCAD runs, MODE2 2, LIM 1, TANG 15 Hz, nominal
source point. Pre-fault gate passed: |I1| 0.080 / 0.080 pu and |δ| 1.120 / 1.120 pu against static (0.0 %, settled).
48 of 48 clean; no weak frame.

Side by side with step 3's EMT check of the same design on the same network (results/FRAMES.md, "The step-3 design
point", `frames_design_check … --tag pll`, mimic chain), as a consistency check across the carried-angle rule:

| | this run: 1.12 pu @ **230°**, nominal point, 48 cases | step 3: 1.12 pu @ **225°**, 95 fault runs (witnesses, window edges, random inception, 48 cases at random source points) |
|---|---|---|
| outside own set (bare, mimic chain) | 0 of 48, largest **0.000 ε** | 0 of 95 |
| contained in the design's own set (≤ 0.1 ε) | 48 of 48 | — (not reported there) |
| nearest N(δ*), 2.20 ε needed | **2.58 ε** | 2.40 ε (smallest over the 95), 2.45 ε over the 48 random-point cases |
| D1 missed, alarm / guaranteed | 0 / 0 | 0 (every fault separated with margin) |
| D0 at 0.162 pu | 0 of 48 missed, clean and design tier | 0 missed on the pilot (STEP3_PILOT.md) |

The two angles agree: the design holds in EMT at both, with the nominal-point margin at 230° (2.58 ε) above the
random-point margins at 225° (2.40–2.45 ε), as a nominal point against a sample should sit. The price at the point:
|I1| delivered / commanded **0.080 / 0.447 pu**.

## 5. Caveats carried on every line

One network (three-bus, weak source, X/R 10); nominal source point in EMT; one point on wave; clean runs; the lumped
R-L line (overhead abstraction); the step-3 relay chain and noise tiers; the model-error box measured at k_L = 1;
the k_L range 1–2× set by the base network's load flow (a longer range needs a stiffer source or lighter loads,
a second network).
