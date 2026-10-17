# Review of PR #44, part 5: the cap with the reference filter, and the 1.12 pu design point

17 Oct 2026. Reviewed `step3-detection` at `51cfd2d`, `a96b736`, `8a8a391` and `fb89f1b`, in a separate worktree,
reading #44's stored outputs: `results/network/frames_pll_check.json`, `frames_main_pll.json`,
`frames_design_specs_pll.json`. Nothing in `src/`, `tests/` or `results/` was changed, and no PSCAD or design runs were
made. The 117-run design-point batch was still running, so its results are not reviewed here.

## Verdict

**Accept 1.12 pu / 225° / ρ = 0.1 with the filtered reference as the step-3 design point**, with ρ = 0.04 reported as
the alternative. This is conditional on three things:

1. **The 117-run batch passes:**
   - no witness, edge (223° / 230°), point-on-wave or all48 point outside its own bare set in the 2–3-cycle window;
   - clean distance to N ≥ 2.2ε everywhere;
   - normals at most a few hundredths of ε outside the bare N.
2. **The cap is re-stated.** It is a window-start question, not a stability question, and it does not bind at
   ρ = 0.1 (§1).
3. **The window-position effect in §2 is checked** before the data generator relies on a 2.0-cycle start.

**On the cap criterion you asked about.** With the filter, "stays in its own set through the whole fault" now holds at
every level tested, 1.18 pu included (0 from 3 cycles). So the old stability criterion no longer sets the cap. What
remains is whether the early-window excursion fits the model-error box. Reasonable as a criterion, if stated as such:
"settled through the fault, **and** the decision window's excursion within the box". And since δ* = 1.12 pu at ρ = 0.1
is below 1.14, the cap does not bind the chosen design. Say that too.

## 1. The cap sweep (`frames_pll_check.json`, 136 runs)

Reproduced: the largest distance outside the own bare set, per window end (cycles after inception), over the 11 cases
× 3 angles:

| \|δ\| | 1.5 c | 1.75 c | 2.0 c | 2.25 c | 2.5 c | 2.75 c | ≥ 3.0 c | clean distance to N, min |
|---|---|---|---|---|---|---|---|---|
| 1.05 | 0.001 | 0 | 0.001 | 0 | 0 | 0 | 0 | 2.30ε |
| 1.10 | 0.025 | 0 | 0.022 | 0 | 0 | 0 | 0 | 2.37ε |
| 1.14 | 0.041 | 0 | **0.086** | 0 | 0 | 0 | 0 | 2.43ε |
| 1.18 | 0.061 | 0.039 | 0.136 | 0 | 0.031 | 0.011 | 0 | 2.49ε |

- **No instability at any level.** Every run is back inside its own set by 3 cycles. The two-bus result (bare DFT
  unstable above about 1.0 pu on bolted B-C faults) is now a controller-specific finding, as agreed.
- **A-G cases never leave their sets** at any level or window. All excursions are on B-C faults, worst on bolted L1 B-C
  15 % at 221°.
- **The cap does not bind the design.** δ* at ρ = 0.1 is 1.12 pu. Interpolating 1.10 / 1.14 puts its 2.0-cycle
  excursion at about 0.05ε, inside the 0.1ε box, and the all48 and edge groups of the 117-run batch measure it
  directly.
- **The cost, stated correctly.** FRAMES.md says a design at the cap is 95 % of rating. The chosen 1.12 pu design leaves
  0.08–0.14 pu of the 0.14–0.78 pu asked, about 93 %. Both figures are right; quote the one for the design point.

## 2. The excursions depend on where the window ends in the cycle

In every run with a non-zero excursion, the windows ending at 1.5 and 2.0 cycles are outside and the one at
2.25 cycles is back at 0. At 1.75 cycles only three L2 runs are non-zero, and only at 1.18 pu. For example:

| run | 1.5 c | 1.75 c | 2.0 c | 2.25 c | 2.5 c |
|---|---|---|---|---|---|
| fp_114_221_L1ab15r000 | 0.041 | 0 | 0.086 | 0 | 0 |
| fp_118_225_L1ab15r000 | 0.061 | 0 | 0.136 | 0 | 0.031 |

A transient of the inverter's frame would decay monotonically. An error that comes and goes with the window's
position in the cycle is the signature of a decaying DC offset leaking through the relay's plain one-cycle DFT:
`pscad_network_check.relay_y` applies no DC-removal (mimic) filter, unlike `review/q3_inputs.seq_traj`. Two
consequences:

- **The cap sweep used one point on wave.** All 136 runs have t_fault = 0.30 s. The DC offset depends on the inception
  angle, so the window positions that are outside, and how far, move with it. The maximum over inception angles was
  not measured at 1.14 pu. The 117-run batch's point-on-wave group (11 cases at 1.12 pu, random inception) is the first
  test of it.
- **The cheap fix is in the relay, not the box.** Real relays remove the DC offset (mimic or cosine filter). Put a
  mimic filter matched to the protected line's X/R into D1's measurement chain, with its fundamental gain H as
  `seq_traj` does, then re-measure the excursions. They should shrink. Then either the 0.1ε box gets headroom, or the
  window can start earlier than 2 cycles. Either way the decision chain the guarantee is stated for must be the one
  the detectors use.

To confirm the cause cheaply, take the existing outputs of fp_114_221_L1ab15r000 and evaluate the distance to the own
set every 1/16 cycle between 1.5 and 2.5 cycles, with and without a mimic filter. No new PSCAD runs are needed.

## 3. The design point (`frames_main_pll.json`)

Reproduced:
- 1.12 pu at 225°, ρ = 0.1, r_max 1.14;
- window 223–230° (8 angles at 1°), narrower than the 221–230° at 1.05 pu;
- dense factors 1.0 / 1.1 / 1.25 all separate; containment 0; Calafiore–Campi 0.920;
- continuous check: 30 of 684 unseparated, all outside the design ranges (L1 A-G 5–10 % at full R_f, L2 B-C 80–95 %,
  L2 A-G 90–95 %);
- I1 left 0.08 / 0.084 / 0.143 pu (min / median / max) of 0.14–0.78 pu asked.

The binding witness gap is 2.210ε against 2.20ε needed (L1 A-G 15 %, 40 Ω): **0.01ε of design margin**, half of the
1.05 pu point's 0.02ε. As before, EMT is expected to sit further out (2.33ε at the old point). Quote the design's 2.21
beside the EMT figure once the batch is in.

ρ = 0.1 restores the margin the review asked for at the start (H14), at the price of 0.07 pu more δ and a 2°-narrower
window than ρ = 0.04. That is a reasonable trade for the primary design. Keep the ρ = 0.04 result for the δ-shrink
curve.

## 4. `frames_design_check.py` made parametric (`8a8a391`)

- **One shared FrameModel is equivalent to the per-angle ones.** The zonotope cache is keyed by (complex δ, case), so
  different angles cannot collide. The per-angle models were all built with seed 1, so the samples are identical.
- The new **all48** group (every case once at a random S, 225°) is the coverage check review part 4 asked for.
- **`frames_design_specs_pll.json` is consistent:**
  - TANG = 1/(2π·15 Hz) in every spec;
  - edges at 223° / 230°, the window's own edges;
  - random inception in the pow group;
  - no instrumented group.

  The docstring's example command says `--edges 220 231`, which is outside the window. The spec file was evidently
  made with `223 230`; fix the example, so a rerun does not test the wrong edges.
- The normals are still judged only before the fault, and the confusers only in the window (review part 4 §4). Fine
  for the design point; the data generator's confusers will be analysed by the detectors anyway.

## 5. Before the step-3 data generator

1. **The 117-run batch result**, with the conditions in the verdict.
2. **The DC-offset check of §2, and a mimic filter in D1's chain** (or a stated reason not to). Then fix the window
   start from the filtered chain.
3. **Point on wave everywhere.** The generator must draw t_fault over a cycle (it is in the spec), and the model-error
   box should be confirmed over inception angles at the design point, not only at t = 0.30 s. The batch's pow group
   is a start: 11 cases.
4. **The load-step decision is made** (FRAMES.md, 17 Oct): loads stay fixed in the design, and D1's false alarms on
   load steps and unbalanced loads are a designed-in limitation reported in the violation matrix. That is consistent
   with TAC25 and the four steps. In the step-3 tables, keep those confusers in their own rows, so they do not dilute
   D1's false-alarm rate on genuine normal operation, and do not hide it either.
5. **Ranges in the data match the guarantee's ranges.** The continuous check shows unseparated faults just outside the
   design ranges (L1 at 5–10 %, L2 B-C at 80–95 %). The generator will draw continuous m. Report the inside-range and
   outside-range strata separately, so faults the guarantee never covered are not counted as D1 failures. Or widen
   the design ranges first.
6. **The settings the generator uses** are those of this design point: commands in the inverter's own frame, D2ANG
   fixed at commissioning, LIM 1, TANG 15 Hz, BUILD_VERSION 3. Record all of them in each spec, so the fingerprint
   catches any drift.

## Not checked

- The 117-run batch and the ρ = 0.04 search (still running).
- §2's cause is inferred from the window-position pattern, not computed. The proposed 1/16-cycle re-evaluation with
  and without a mimic filter would confirm it.
- `frames_pll_check.py` itself was read only through its output JSON.
