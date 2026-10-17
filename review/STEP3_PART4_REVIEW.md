# Review of PR #44, part 4: the design-point EMT check and the PLL-like reference

17 Oct 2026. Reviewed `step3-detection` at `cabcb4e` and `03f17e7`, in a separate worktree, reading #44's stored outputs
(`results/network/frames_design_check.json`, `frames_design_specs.json`). Nothing in `src/`, `tests/` or `results/`
was changed, and no PSCAD or design runs were made.

## Verdict on the decision

**Yes: use the filtered reference (TANG at 15 Hz) for step 3's data generator**, under four conditions:

1. **Call it what it is.** It is a first-order low-pass on the V1 angle phasor, not a PLL. In this fixed-frequency EMT
   that is enough. A real SRF-PLL is second order: it tracks frequency, has overshoot, and can itself go unstable on
   weak grids at high injection. Write "PLL-like reference filter (first order, 15 Hz)" everywhere, and show the
   conclusion does not hinge on 15 Hz: rerun the two instrumented cases at 10 and 30 Hz (4 runs).
2. **Keep the bare-DFT result as a controller-specific finding.** At 1.14 pu the inverter's own measured |V1| swings
   from 0.23 to **2.76 pu**, against 0.40–0.77 pu with the filter. That is an equipment-level instability, not only a
   relay one, and it is worth one sentence in FRAMES.md and REVIEW row 51.
3. **Re-validate what the controller changes, not the whole static design.** The filter does not move the static fixed
   point, so the sets and the static δ* are unchanged for a given r_max. What changes is (a) the cap on |δ|,
   (b) the inverter frame's motion through the 2–3-cycle window, and (c) the late behaviour. The scope is in §3.
4. **Decide the load-step question before generating data** (§2.4). It is independent of the controller, but it will
   decide D1's false-alarm column.

## 1. The TANG Fortran (`src/pscad_inverter.py`)

| Check | Finding |
|---|---|
| Storage | The two filter states use `NSTORF + 7 + 6·NMAX` and `+1`. Those slots are past the DFT ring buffer (`NSTORF + 7 … + 7 + 6·NMAX − 1`) and inside `NSTOR = 7 + 6·NMAX + 3`, so nothing is overlapped. `G_J` is reused after the buffer writes, which is harmless. |
| Discretisation | Forward Euler on (cos, sin) with α = DELT/TANG = 10 µs / 10.6 ms ≈ 9.4·10⁻⁴: stable, with negligible error against the continuous filter. |
| Start-up | The filter state follows the raw DFT angle for the first cycle, then filters. References ramp in only over the third cycle, so the junk angle of the unfilled DFT never reaches the output. |
| Re-normalisation | `ATAN2` of the filtered vector, then cos/sin again: the reference stays a unit phasor even when the filtered vector shrinks during a large swing. |
| TANG = 0 | The block is skipped, and the regression run `fd_reg_d105_L1ab15r000` against `fe_d105_L1ab15r000` shows a largest channel difference of 0.0. |
| Wiring | `build()` creates a `K{inverter}TANG` constant from `INPUTS`, `update()` writes it (default 0), and `BUILD_VERSION = 3` invalidates old fingerprints. The new controller channels (V1M, V2M, I1M, I2M, ANG) are recorded. |
| Limitation | The filter acts on the angle in the DFT's absolute frame e^{jωt} at the fixed F0. At constant 60 Hz it passes the steady angle exactly. Under a frequency deviation it would lag by Δω·TANG, with no frequency tracking. Irrelevant on this grid; relevant for any later frequency event or grid-forming scenario. |

## 2. `src/frames_design_check.py` and `frames.witness`

**Correct:**
- `witness` solves the minimum-gap LP over every pair of pieces of N and F, and maps the shared symbols back to the
  [−1, 1]⁴ box through each piece's own centre and half-width. The fault side's λ and drift come out with it.
- `analyse` takes the relay memory 3 cycles before **each run's own** `t_fault`, so the random-inception group is
  referenced correctly.
- Fault points are judged against their own **bare** set (factor 1.0, no reference noise, no model-error box). That is
  the strict test of what the model-error box must cover.
- Separation is the **clean** distance to the **main** N against 2(1 + ρ) = 2.08, the right criterion for a clean
  measurement.
- Normals are judged against the **bare** N, also the strict choice.

**Reproduced from the stored JSON:**

| group | runs | outside own set (2–3 c) | clean distance to N, min | after 3 cycles |
|---|---|---|---|---|
| witness | 13 | 0 | 2.33ε (L1 A-G 15 %, 40 Ω) | 0 |
| edge (221°, 230°) | 22 | 0 | 2.34ε | up to **15.6ε** outside own set |
| random inception | 11 | 0 | 2.33ε | up to **10.1ε** |
| normal corners | 16 | max 0.034ε outside bare N | — | — |
| confusers | 2 | load step 0.86–0.87ε, single-phase 0.41ε outside bare N | — | — |

**2.1 The design gap at the binding witness is 2.10ε, against 2.08ε needed.** EMT is further out (2.33ε), because the
EMT realisation is not the design's extreme pair. So the design point holds in EMT with room, but in the design itself
it holds by 0.02ε at L1 A-G 15 % (40 Ω). Put the 2.10 next to the 2.33 in FRAMES.md.

**2.2 The model-error box is now supported in the decision window.** No witness, edge or random-inception point is
outside its own bare set, and the witnesses are where the sets are tightest. The 0.1ε box covers the decision window
with a filtered or unfiltered reference. It does not cover anything after 3 cycles with the bare DFT (§2.3). This
answers review part 3, §3.

**2.3 With the bare DFT, the drift after 3 cycles is large at the window's edges** (15.6ε at 221° and 230°, 10.1ε at
random inception). That confirms review part 3, §2: the bare-DFT design point is a 2–3-cycle design. With the filter,
both instrumented cases stay at 0 through 16 cycles (0.04ε at 2 cycles for 1.14 pu).

**2.4 The load step is outside the normal model by construction.** A balanced 0.2 − j0.06 pu step at bus S leaves the
relay 0.86–0.87ε outside the bare N in every window. It is a steady new operating point, not a transient. Against the
main N it should be somewhat closer: about 0.75ε, estimated by taking off the 0.1ε model-error box and the factor-1.1
slack, not computed. With D1's noisy-measurement threshold of ε, any
noise of about 0.2ε in the wrong direction makes it a false alarm, and the step-3 noise model (systematic CT/VT plus
white noise) will supply that. So D1's false-alarm rate on load steps is already decided by the design: `network.py`
holds loads fixed. The choice belongs before data generation:
- **(a)** give N a load range: a load-scale symbol in the frame model, which handles non-affine maps already; or
- **(b)** keep loads fixed and report D1's load-step false alarms as a designed-in limitation, not a discovery.

The single-phase load (0.41ε) is the same question, for an unbalanced source N does not contain.

## 3. Re-validation under the filtered reference

What is static is unchanged. These are the checks that can change:

1. **The cap.** Sweep |δ| ∈ {1.05, 1.10, 1.14, 1.18} at 225° on the 8 bolted B-C cases and the 3 hardest A-G
   witnesses, with TANG: 44 runs, plus 221° / 230° at the largest settled |δ| (22 runs). The new r_max is the largest
   level that stays within its own set through the whole fault, not only in the window.
2. **δ* with the raised cap.** The static search with r_max = the new cap, at ρ = 0.1 and 0.04 (no EMT).
   **State the cost:** at 1.14 pu the inverter keeps about 0.06 pu of I1, so a ρ = 0.1 design that needs it is a
   95 %-of-rating design.
3. **The window with the slower reference.** The filter adds a time constant of 0.64 cycles to the frame's turn. At
   2.0 cycles the 1.14 pu case was 0.04ε outside its own set, where the bare DFT gave 0. Measure the distance to the
   own set at 1.5, 1.75 and 2.0 cycles on the cap-sweep runs, and keep the window start where it is 0. The λ sweep
   still covers a first-order, non-overshooting turn: the ANG span of 25–26° equals the settled turn.
4. **The design-point checks at the new design.** `frames_design_check` with TANG in every spec: witness, edge,
   random inception, normals and confusers (about 70 runs).
5. **The 168-run model-error check is not needed in full.** The witnesses are the tight points. Re-run the 48 cases
   once each at the new δ (48 runs) for coverage, not the four magnitudes.

That is about 190 runs, about 30 minutes in fast mode, plus one static design search.

## 4. Smaller points

- `frames_design_check` judges normals before the fault only (`tf − 0.05`) and confusers in the window. Normal
  operation under the filtered reference after a confuser (does the reference settle?) is worth the same 2–3-cycle
  check.
- The instrumented runs record `ANG_I` in the DFT's absolute frame. The 26° span with the filter equals the settled
  turn (−23° to −26° in the static model), so the filter neither overshoots nor lags beyond the window.
- `I1M` is constant (0.062 and 0.15 pu) in all four instrumented runs. The limiter fixes |I1| in the inverter's frame,
  and the instability is entirely in the angle, consistent with review part 3, §2.

## Not checked

- No PSCAD, `analyse` or design runs; every number is from #44's stored JSON.
- The cabcb4e edits to FRAMES.md, STEP3.md and REVIEW row 51 were not re-read line by line against review part 3, §4.
- No true type-2 PLL was tried; condition 1 asks for a bandwidth sensitivity, not a PLL implementation.
