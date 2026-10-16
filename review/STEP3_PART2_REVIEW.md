# Review of PR #44: the design with both frames

16 Oct 2026. Reviewed `step3-detection` at `7f2f2b5` (PR #44, open) in a separate worktree. Nothing in `src/`,
`tests/` or `results/` was changed. Tests on #44: **167 passed, 4 skipped**. Three check scripts are in
[`review/checks/`](checks/): `p44_ablate.py`, `p44_inner.py`, `p44_drift.py`. They import #44's `src/frames.py`, so
they run on its checkout (or after it is merged). All runs use the search tier that `frames_design.py` uses: 150
random samples, a 3-point face grid, factor 1.1, seed 1.

## Summary

| Question | Answer |
|---|---|
| (1) Is "the guarantee needs nearly the whole inverter" sound? | **Partly.** Under #44's own assumptions it is mostly real: physical witnesses put the true δ* above 0.94 pu at ρ = 0.1, against the reported 1.14. But it hinges on one modelling choice. Without the relay-reference noise rotation, δ* falls to ≤ 0.90 pu at ρ = 0.1, the absolute-frame value. That rotation is, at best, an upper bound that double-counts part of ε. |
| (2) Is the search-tier δ* trustworthy? | **Yes, on its 5° angle grid.** A full 72-angle sweep at 0.90, 1.00, 1.04, 1.08, 1.10 and 1.12 pu finds no separating command. The separating window at 1.14 pu is only 10° wide (225°, 230°), so a 1° scan could find a slightly smaller radius, though not by more than the 0.02 pu radial step plausibly allows. |
| (3) Could a set be too small? | **Nothing found in the remainder or the split.** Two things outside them are not in any set: the static model's error against EMT (up to 0.35ε at the design's decision time), which is larger than the 0.2ε margin ρ = 0.1 provides; and the relay's own first-cycle windows. The Calafiore–Campi figure is overstated. |

## 1. Is the conclusion an artefact?

**1a. Not of the outer approximation.** `p44_inner.py` asks whether a failure at a candidate command is *witnessed*
by physical points: a sampled normal realisation and a sampled fault realisation of the two-frame model within
2ε(1 + ρ) of each other in the ∞-norm. The samples include the fixed point, the limiter, the frame sweep, the drift
and the reference rotation. A witness proves the true sets meet. No witness proves nothing. So the radius at which
every angle is witnessed is a lower bound on the true δ*:

| ρ | every angle witnessed up to | first angles without a witness | reported δ* (outer sets) |
|---|---|---|---|
| 0.1 | **0.94 pu** | 1.00 pu (225°, 230°) | 1.14 pu |
| 0 | 0.60 pu | 0.80 pu (220–230°) | 0.94 pu |

At ρ = 0.1 the true δ* lies in (0.94, 1.14] under #44's assumptions, so the outer sets add at most 0.2 pu. FRAMES.md
says "not an artefact of loose sets" on the strength of the shared-vs-independent ablation. That ablation shows the
shared symbols buy little, not that the sets are tight. This witness test is the evidence for the claim, and it
supports it at ρ = 0.1.

**The binding cases are in-zone.** The witnessing cases are L1 A-G through 40 Ω: L1 15 % at ρ = 0.1 and L1 35 % at
ρ = 0, joined near δ* by L1 B-C through 40 Ω. With the L2 cases removed, δ* only falls from 1.14 to 1.08 pu. So,
unlike the δ = 0 hardness in STEP3_PLAN_REVIEW.md §2.1, the cost here is not driven by the adjacent line.

**1b. It is driven by one modelling choice.** `p44_ablate.py` removes one ingredient at a time (ρ = 0.1, 72 angles
at each radius):

| variant | unseparated at δ = 0 | first radius with a separating angle |
|---|---|---|
| as in #44 | 13 | 1.14 (sweep at 0.90–1.12 empty) |
| no drift margin | 13 | 1.08 |
| settled fault frame only (no λ sweep) | 13 | 1.14 |
| inverter-frame command angle ±0.15 rad (not ±0.3) | 11 | 1.08 |
| L1 cases only | 7 | 1.08 |
| **no relay-reference noise rotation** | 11 | **0.90** |
| settled frame, no drift, no reference noise | 9 | **0.80** |

The radii probed were 0.6, 0.8, 0.9, 1.0, 1.08 and 1.14, so each entry is "first probed radius", an upper bound to
the probe step.

- **The reference rotation is worth about 0.24 pu**, more than all the other ingredients together. Without it the
  two-frame design is back at the absolute-frame 0.90 pu. The inverter's V1 frame itself, which is the mechanism
  behind round-1 finding 3, then costs almost nothing.
- **The rotation is set at φ_max = ε/min|V1_L| (about 5°), the whole ε, on top of the ε noise box.** That is an upper
  bound, and it double-counts:
  - *Systematic* VT error, which ε was tied to (H2), rotates the voltages and the reference together. It leaves
    the voltages unchanged in the relay frame, and its effect on the currents is the relative V–I error that #44
    already moved to the violation matrix. A full-ε reference rotation counts it again.
  - *Random* noise on the reference is averaged by the memory (several pre-fault cycles), so it is smaller than
    the per-window ε by about √(cycles).

  Recommendation: give the reference its own budget, φ_ref = (random ε)/(√n_mem·|V1_L|), with the systematic part
  in the violation matrix. Report δ* as a function of φ_ref (0 to ε/|V1_L|). The headline then reads "0.90–1.14 pu
  depending on how noisy the relay's memory is".
- **The drift margin is generous but cheap.** `p44_drift.py`: beyond the V1-referenced fixed point, the stored EMT
  fault runs drift at most **2.2°** within 4.8 cycles of inception (0 of 96 runs over 6°), and **4.2°** at 5.7
  cycles (bolted L1 B-C at 55 %). So ±6° is about 3× the observed drift for decisions within 5 cycles, and dropping
  it saves only 0.06 pu.
- **The inverter-frame command spread is a changed assumption, not a frame effect.** `FrameModel` takes the
  absolute-frame ±0.3 pu / ±0.3 rad box and applies it in the inverter's own frame. The frame rotation then comes on
  top, so the total absolute I1 angle spread is wider than the absolute model's. Halving the command angle spread
  saves 0.06 pu. State which uncertainty the ±0.3 rad describes (the inverter's setpoint and power-factor range, in
  its own frame), so that "frames cost" and "a wider set" are not conflated.
- **ρ on top of the frame uncertainty is not the driver.** At ρ = 0, δ* is already 0.94 pu.

**1c. The design is fragile.** At the reported δ* only 2 of 72 angles separate (225°, 230°). At the first separating
radius of most variants, 1–3 angles do. A guarantee that holds in a 10° window is sensitive to anything unmodelled,
starting with §3a. Report the window width with δ*.

## 2. Is the search-tier δ* trustworthy?

- **Coarse to fine.** At ρ = 0.1 the coarse pass (24 angles, 0.1 pu steps) found no separating command up to 1.1 pu.
  `min_delta_fast` then started the fine grid at r_max − 0.1 = 1.08 pu, so radii below 1.08 had only been probed at
  15° spacing. The full 72-angle sweep at 0.90, 1.00, 1.04, 1.08, 1.10 and 1.12 pu (`p44_ablate.py base 0.1
  0.9,1.0,1.04,1.08,1.1,1.12`) finds **no** separating angle, so on the 5° grid the search did not miss a smaller
  radius. The witness test (§1a) also leaves no free angle below 1.00 pu at ρ = 0.1.
- **Search vs dense tier.** The dense tier fits on more samples, so its remainder (the largest residual over more
  points) is generally no smaller. It should therefore not separate where the search tier fails, and it was checked
  to separate at δ*. This is not a strict inclusion, because the minimax fit changes with the samples. A spot check
  of 2–3 rejected candidates near δ* on the dense tier would close it.
- **Angle resolution.** With a 10°-wide window at 1.14 pu, windows narrower than 5° may exist at 1.10–1.12 pu. Scan
  1° steps over 210–240° at 1.10 and 1.12 pu before quoting δ* to two decimals. The effect is at most a few
  hundredths of a pu: small next to §1b.
- **The factor check runs on the search tier** (`frames_design.py`: `n_samples=150, face_pts=3`), not the dense one.
  Fine as a sensitivity check, but say so.

## 3. Could a set be too small?

**Checked and sound:**
- the split covers the box: two pieces with the commanded-current radial symbol at ≤ 0 and ≥ 0;
- r is the fitted model's actual largest residual over all samples, and the assert holds;
- every corner of the 7-D symbol box is sampled: the 4-D corners × λ ∈ {0, 1} × drift ∈ {±1} × reference ∈ {±1};
- the λ path is right. The inverter's DFT estimate during the window is a convex combination of the pre-fault and
  fault V1 phasors, whose angle lies on the same short arc as the normalised interpolation used;
- the drift scales with λ;
- no case has a dead frame;
- the fixed point raises on non-convergence, so such candidates are skipped as inadmissible, which is
  conservative;
- the ε box is defined in the relay frame, consistent with φ_max.

**Not in any set:**

- **3a. Static model error.** Against the stored EMT runs, the two-frame model is off at the relay by up to:

  | time after inception | max \|EMT − model\| | median |
  |---|---|---|
  | 2 cycles | 0.25ε | 0.06ε |
  | 4.8 cycles (the stored runs' decision time) | **0.35ε** | 0.03ε |
  | 5.7 cycles (bolted L1 B-C 55 %, growing) | 0.82ε | 0.03ε |

  At ρ = 0.1 the design's margin is 2ε·0.1 = **0.2ε**, smaller than the worst model error at the decision time. A
  guarantee that is meant to hold in EMT needs that error inside the sets (an extra box of the measured size per
  case class), or a stated decision window in which it is below the margin.
- **3b. The relay's own first cycle.** Windows that straddle inception mix pre-fault and fault measurements and
  belong to no set. D1 must only decide on windows entirely after inception (starter + one cycle). That is a
  detection-time cost, not a soundness gap, but it should be in the guarantee's statement.
- **3c. Continuous (m, R_f).** The 48 cases are grid points. Between them nothing is guaranteed (H13), so a
  continuous re-check at δ* belongs with the containment checks.
- **3d. The Calafiore–Campi figure is overstated.** `scenario_bound(45720)` treats all 45,720 rows of a fault piece
  as i.i.d. samples. But only the ~400 random interior points per piece are random. The corners and face grid are
  deterministic, and the λ / drift / reference values are deterministic grid copies. The envelope also fits c and J
  from the same samples, so each component has d = 1 + 7 + 1 = 9 decision variables, not 1. With n = 400 and
  d = 9, ε_cc = 2(ln(1/β) + d)/n = 0.0795: coverage ≥ **92 %** per component and piece at β = 10⁻³ (≥ 93 % for the
  normal set, d = 7). Over 12 components × 2 pieces the confidence is 1 − 24β. The quoted 99.97 % should go. It is
  also coverage of the sampling measure, not a worst-case statement, so it supports nothing about the guarantee.
- **3e.** λ, drift and reference are sampled only at grid values (5, 3, 3). Their interiors are covered only by the
  adversarial local perturbations. That is reasonable, but say so.

## Recommendations before building on #44

1. Give the relay-reference rotation its own budget (memory averaging, systematic part in the violation matrix),
   and report δ* as a function of it. As it stands, "nearly the whole inverter" is the upper end of a 0.90–1.14 pu
   range.
2. Put the static-vs-EMT model error into the sets, or restrict the guarantee to a decision window where it is below
   the margin.
3. Fix the Calafiore–Campi statement (i.i.d. count, d per component), or drop it.
4. Report the separating window's width at δ*, and do a 1° angle scan near it.
5. Reword FRAMES.md's "the frames cost is real, not an artefact of loose sets". The outer sets are close to tight
   at ρ = 0.1 (witness test), but the cost comes almost entirely from the reference-noise symbol, not from the
   inverter's frame.
6. Note that the binding cases are in-zone L1 A-G through 40 Ω, which matters for the T1 / T2 split.

## Not checked

- No PSCAD runs. The drift and model-error figures come from the 96 stored three-bus EMT fault runs (`tb_*`,
  LIM 1, the absolute-frame worst realisations), not from runs at the two-frame design's δ* = 1.14 pu.
- ρ = 0 ablations were not run, and no ablation was run on the dense tier.
- The 1° angle scan and the dense-tier spot checks below δ* (§2) were not run.
- `solve_v1ref` and the vectorised fixed point were not re-derived; #44's tests (vectorised = scalar) were relied on.
- docs/STEP3.md beyond the frame paragraph, and `step3_builder_check.py`, were not reviewed.
