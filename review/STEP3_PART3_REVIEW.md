# Review of PR #44, part 3: EMT with δ injected, and the 1.05 pu design point

16 Oct 2026. Reviewed `step3-detection` at `6d8f812` ("Step 3, part 3") in a separate worktree. Nothing in `src/`,
`tests/` or `results/` was changed, and no PSCAD runs were made. Every number below comes from #44's stored outputs:
`results/network/frames_*.json`, and the 168 `fe_*` runs under `D:\JOSHUA_TAYLOR_data\data\pscad_work\network\`.
Two scripts in [`review/checks/`](checks/) produce the new numbers: `p44c_settle.py` and `p44c_fixedpoint.py`. They
import #44's `src/frames.py`, so they run on its checkout.

## Summary

| # | Question | Answer |
|---|---|---|
| 1 | `frames_emt_check.py`: frames and the model-error measure | **Correct.** The inverter gets its commands in its own frame, and the comparison is in the relay's pre-fault frame. "Distance to its own set" is the right quantity for soundness. It is a weak *estimate* of the box the sets need, because it is sampled at one random interior source point per case (§3). |
| 2 | 1.14 pu, bolted B-C faults: component fault or real dynamics? | **Most likely real closed-loop dynamics of this controller, not a component fault.** Proving that needs one instrumented run. It is not confined to 1.14 pu: at 1.05 pu, 3 of 8 bolted B-C runs leave the settled state after 3 cycles, by up to 21°, before the fault clears. |
| 3 | Model-error box 0.25ε → 0.1ε | **The argument is right; the evidence is not yet enough.** The 0.073ε maximum comes from random interior points, 225° only, a fixed inception angle, and no A-G case at 1.00 / 1.05 pu. Keep 0.1ε as provisional until the design point's own worst realisations are run in EMT. |
| 4 | Design point 1.05 pu / 225° / ρ 0.04; FRAMES.md and REVIEW §7 row 51 | **The numbers reproduce from the JSON. Three statements overreach:** "settles on every case" (A-G was not run at 1.05; B-C drifts after 3 cycles), "1.05 pu measured" as the cap (it holds only in the 2–3-cycle window), and ρ = 0.04 (chosen to make the design feasible; it is labelled "chosen", but its margin is half the 0.073ε observed outside). |
| 5 | Another EMT check before step-3 data generation? | **Yes, a focused one (§5):** about 60 runs at the design point, covering the binding A-G cases at their witness realisations, the window edges (221°, 230°), random inception angles, normal operation and confusers at 1.05 pu, and one instrumented unstable run. |

## 1. `src/frames_emt_check.py`

- **Inverter settings in its own frame: yes.** `_settings` writes ID = Re(i_cmd) and IQ = −Im(i_cmd). The Fortran forms
  I1 = Ibase·(ID − jIQ)·e^{j∠V1} = i_cmd·u, and D2MAG / D2ANG give δ = |d|·e^{j(∠V1 + ∠d)} = d_cmd·u (`pscad_inverter.py`,
  `G_I1R` / `G_I1I`, `G_I2R` / `G_I2I`). `FrameModel.cI` is the nominal current rotated into the nominal inverter frame,
  and `sources(S)` gives the same i_cmd that `make` writes. So EMT and model command the same thing. `make_spec`'s own
  absolute-frame settings are overwritten, as intended.
- **Comparison in the relay's frame: yes.** u_L is the EMT relay V1 at 0.25 s, normalised. Fault windows (2.0–3.0 cycles)
  are rotated by its conjugate. The model's `measure` uses its own pre-fault V1 for the same S. Both phasors share the
  absolute-index DFT frame, so the rotation fixed at 0.25 s is valid at 0.33–0.35 s.
- **"Distance to its own set" is the right soundness measure.** It is the smallest ∞-norm box that puts the EMT point
  inside its case's set (with model_err = 0, factor 1.0, ref_phi = 0, drift 3°). The relay does not know S, so a point
  that the set explains at another S is still contained. That is why |EMT − settled model| at the same S (up to 0.54ε
  at 1.05 pu) and the distance to the set (0) differ, and the PR is right that the earlier 0.25ε, a distance to the
  settled point, over-states the box the sets need.
- **What it does not measure.** Each case was run once, at one random interior point of the source box, at one angle
  (225°), with one inception time (t_fault = 0.30 s). The sets are tightest where realisations are extreme (the box
  corners and the `closest()` witnesses). Random interior points rarely reach that boundary, so a maximum taken over
  them is an optimistic estimate of the box needed (§3).
- **Small points.**
  - `T_PRE = 0.25` and the fixed `T_FAULT` ignore the per-run `t_fault` that part 1 added to the spec. Fine for these
    runs, but the analysis should read it from the spec.
  - The normal runs are judged at `T_PRE` only.

## 2. 1.14 pu on bolted B-C faults: component fault or dynamics?

**What happens** (`p44c_settle.py`: δ's angle in the relay frame against the settled V1-referenced model, windows every
half cycle):

| run | 1.0 c | 1.5 c | 2.0 c | 3.0 c | 4.5 c | 5.5 c |
|---|---|---|---|---|---|---|
| 0.90 pu, L1 B-C 15 % bolted | +15.2° | +7.5° | +1.9° | −0.0° | −0.3° | −0.2° |
| 1.05 pu, L1 B-C 15 % bolted | +18.2° | +8.7° | +2.3° | −0.2° | −0.4° | **−10.3°** |
| 1.14 pu, L1 B-C 15 % bolted | +20.3° | +9.5° | −14.8° | −46.0° | −59.6° | +1.7° |
| 1.14 pu, L1 B-C 95 % bolted | +29.0° | +16.0° | +11.8° | +9.3° | **+101°** | +36° |
| 1.14 pu, L1 A-G 15 % 40 Ω | +2.0° | +0.3° | −0.5° | −0.0° | +0.2° | +0.1° |

At 1.14 pu the measured |δ| sags at the same time (1.14 → 0.42–1.04 pu). That is what a one-cycle DFT shows when the
phasor turns within its own window, so the reference is moving fast. Over every stored run, the largest angle off the
settled model:

| \|δ\| | B-C bolted, 2–3 c | B-C bolted, 3.25–5.5 c | B-C with R_f, 3.25–5.5 c | A-G, any |
|---|---|---|---|---|
| 0.90 | 3.3° | 0.3° | 0.3° | ≤ 0.8° |
| 1.00 | 3.9° | 2.6° | 0.3° | not run |
| **1.05** | 4.4° | **20.8° (3 of 8 runs > 5°)** | 0.4° | **not run** |
| 1.14 | 46° | 138° (8 of 8) | 10.3° (3 of 16 > 5°) | ≤ 1.8° |

The fault clears at 6 cycles, so the 3.25–5.5-cycle windows are still inside it.

**Why I think it is real dynamics, not a component fault:**
- It grows smoothly with |δ|: 0.90 stable, 1.00 small, 1.05 slow departure after 3 cycles, 1.14 divergence. A
  coding error in `gfl_avm` would not respect a threshold like that.
- It occurs only on phase-to-phase faults, never on A-G. On a B-C fault V1 = V2 at the fault point, so the injected
  negative-sequence δ creates positive-sequence voltage at the inverter's own bus.
- The runs first approach the static fixed point and then leave it. That is the signature of a lagged loop near its
  stability limit, not of a wrong steady state. The same Fortran is verified to inject what it is told
  (PSCAD_INVERTER.md) and settles at 0.90 pu.

**Why the static analysis misses it** (`p44c_fixedpoint.py`). The static map θ → ∠V1_R(e^{jθ}) has one fixed point, and
its slope there is small and falls with |δ| (L1 B-C 15 %: 0.235 at 0.90, 0.192 at 1.05, 0.161 at 1.14). The PR is
right that the static gain does not predict the failure. Two things do line up with it in these cases:
- the ratio of δ's own term in V1_R to the smallest |V1_R| on the circle: 0.59 / 0.67 for the runs that hold,
  0.73 / 0.79 for the 1.05 pu runs that drift, 0.87 / 1.94 for the 1.14 pu runs that diverge, 0.05 for A-G;
- |V1_R| varies widely around the circle (0.20–0.54 pu).

The inverter's reference is the angle of a one-cycle *average* of the V1 phasor, taken every sample with no PLL. When
the reference moves, the average passes through low-|V1| directions dominated by the inverter's own δ term. The
one-cycle DFT delay and the network's L/R lag (X/R ≈ 10, about 1.6 cycles) add phase. That is a plausible mechanism.
It is not proved here.

**How to settle it with one run.** Record the controller's own outputs as channels: `V1M`, `V2M`, `I1M`, `I2M` exist in
`gfl_avm` but are not saved, and the angle `G_AN` could be added. Run fe_d114_L1ab15r000 with a fault long enough
(0.3 s) to see whether it is a limit cycle, a drift, or a loss of synchronism. Then rerun it with the angle reference
low-pass filtered (a PLL-like 10–20 Hz bandwidth). If the instability disappears or moves, it belongs to the reference
dynamics.

**What it means for the design.**
- The 1.05 pu cap is a property of *this* controller, which has an idealised DFT reference and no PLL. It is not a
  property of inverters in general. A real GFL's PLL could make the boundary lower or higher.
- Even at 1.05 pu the state holds only inside the 2–3-cycle decision window on bolted B-C faults. D1's guarantee
  survives if it decides in that window. The inverter then keeps injecting about 1 pu of drifting δ until the fault
  clears, and that is a behaviour of the protected system, not just of the relay. State both.

## 3. The model-error box: 0.25ε → 0.1ε

The **argument** is sound. The box the sets need is the distance from EMT points to their own set, not to the settled
point, because λ and the drift already absorb the frame's turn. The **evidence** for 0.1ε is thin:

- **Sampling.** 48 random interior source points at 0.90 pu (one per case), and 24 B-C points plus 4 normals at
  1.00 / 1.05 pu. The 12 of 240 points outside their sets (largest 0.073ε, L2 A-G 50 % bolted at 2.0 cycles) are what
  random points found. The maximum over the box sits at the extremes, which were not run.
- **The binding cases were not run at the design point.** The design point is decided by L1 15 % A-G at full R_f.
  No A-G case was run at 1.00 or 1.05 pu. At 0.90 pu, A-G was among the points outside (L2 A-G 50 %).
- **One angle, one inception time.** 225° only, while the design's window is 221–230°. t_fault = 0.30 s for every run,
  so point-on-wave (DC offset) never varied, and the model error at 2.0 cycles depends on it.
- **The window edge.** The worst point is at 2.0 cycles, the window's start. Before that the error grows fast: |EMT − settled model| was
  0.38ε at 1.7 cycles and 0.66ε at 1.5 cycles on the stored `tb_*` runs (review of PR #44, round 3). That is a
  distance to the settled point, so it overstates what the sets need, but the distance to the set was not measured
  before 2.0 cycles at all. An inception estimate
  that is a quarter cycle late puts D1's first window there. The starter's timing error belongs in the window
  definition: start the window at 2 cycles plus the starter's worst lateness.
- **Headroom.** The main configuration's factor 1.1 adds 10 % of each remainder (0.04–0.1ε) on top of 0.1ε, which is
  real headroom over 0.073ε. Report it as part of the margin, not as part of the model error.

Verdict: keep 0.1ε as **provisional**, and label it "measured on random interior points at 225°". Confirm it with the
§5 runs at the design point's witness realisations. If the confirmation shows more than 0.1ε, the design at 1.05 pu
has no slack left (§4).

## 4. The design point, FRAMES.md and REVIEW §7 row 51

**Reproduced from `frames_main_fixed.json`:**
- 1.05 pu at 225°, ρ = 0.04, φ_ref = 0.0303 rad, model_err = 0.008 pu (0.1ε), drift 3°;
- 13 cases unseparated at δ = 0;
- window 221–230° (10 angles at 1°);
- dense factors 1.0 / 1.1 / 1.25 all separate; containment 0; Calafiore–Campi 0.920;
- continuous check: 684 cases, 48 unseparated, all outside the design ranges (44 L2 B-C at 65–95 %, 4 A-G at full R_f
  on L1 5–10 % and L2 90–95 %);
- current left 0.14–0.25 pu of 0.14–0.78 pu asked.

`frames_main.json` (ρ = 0.1) has no design up to 1.05 pu, as stated.

**Statements to correct:**
1. FRAMES.md table, "EMT settles: all 24 ab cases" at 1.00 / 1.05 pu, and docs/STEP3.md, "the EMT inverter settles at
   1.0 and 1.05 pu on every case". True only in the 2–3-cycle window. After 3 cycles, 3 of 8 bolted B-C runs at
   1.05 pu drift by up to 20.8° (§2). "Every case" also covers the A-G cases, which were not run at 1.00 / 1.05 pu.
2. docs/STEP3.md labels the 1.05 pu cap "measured". It is "measured at 225° on B-C cases, inside the decision window,
   for this controller". The window 221–230° was not run.
3. FRAMES.md: "The mechanism is not identified" is honest. "Neither the loop gain nor the inverter's own share of its
   bus voltage predicts it across δ levels" is too strong: in the cases checked, δ's term over min|V1_R| orders them
   correctly (§2). Say "not established".
4. ρ = 0.04 is a margin chosen to reach feasibility (the largest is 0.05). It is labelled "chosen", which is right.
   But the design's whole margin, 2ε·0.04 = 0.08ε in total, is about the size of the 0.073ε seen outside. Put
   the two numbers next to each other in FRAMES.md.
5. REVIEW §7 row 51, "DOES NOT HOLD in EMT; the headline holds more strongly": right for 1.14 pu. Add that the
   1.05 pu replacement is verified only in the decision window, at 225°, on B-C faults, at random interior points, and
   that EMT at 1.05 pu drifts after 3 cycles.

The headline itself is supported. With the measured budgets the guarantee needs 87.5 % of the inverter, in a 10° window,
with a 4 % margin. If anything the qualifications make it stronger: the cap comes from the controller's dynamics, not
from the sets.

## 5. Another EMT check before step-3 data generation?

Yes. Step 3 builds every detector's normal set and data at this design point, so it should be checked where it matters,
in one batch of about 60 runs (about 10 minutes in fast mode):

1. **The binding cases at their witnesses.** For each of the 13 cases unseparated at δ = 0, run the `closest()` normal
   and fault realisations at the design point. Measure the distance to the own set and the clean separation ratio.
   This is the confirmation of model_err = 0.1ε (§3).
2. **The window's edges.** 221° and 230° on the 8 bolted B-C cases (settling after 3 cycles) and on the 3 hardest A-G
   cases.
3. **Point on wave.** The same 11 cases with t_fault drawn over one cycle (it is in the spec since part 1).
4. **Normal operation at 1.05 pu.** The 16 box corners (LIM 1) and two confusers (a load step, a single-phase load).
   Check the distance to the normal set (must be 0) and that the inverter's loop stays settled under a normal
   disturbance. Only 4 normal runs exist at 1.05 pu, and at 1.14 pu one normal run was already 0.10ε outside its set.
5. **One instrumented run** (§2) to classify the instability. If the limit is the reference dynamics, the step-3 data
   generator should carry a PLL-like reference, or the cap should be stated as controller-specific.

## Not checked

- No PSCAD runs. Everything above comes from #44's 168 stored `fe_*` runs and its JSON files.
- `frames_budget.py`, `frames_main.py` and the continuous check were not re-run; their stored outputs were read.
- The instability mechanism in §2 is a lead, not a result.
- docs/STEP3.md beyond the new "main design configuration" section was not re-read.
