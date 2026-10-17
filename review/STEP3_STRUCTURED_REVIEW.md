# Review of the structured instrument-error sets (PR #44, `3cfffbd`, `d7c4c4d`, `6ff3997`)

17 Oct 2026. Reviewed in a separate worktree: `src/frames.py` (`instr`), `src/frames_structured.py`,
`src/step3_multiplicative.py`, `results/STEP3_PILOT.md`, REVIEW row 53. No `src/`, `tests/` or `results/` change and no
PSCAD runs. One static check: [`checks/p44g_structured.py`](checks/p44g_structured.py).

## Verdict

**(a) The structured implementation is sound, and the package for Taylor is complete.** Two wording points (§3) remain.

## 1. The implementation (`frames.FrameModel(instr=...)`)

- **`_instr_apply`** takes sequence → abc, multiplies each phase by (1 + r)·e^{jθ}, then abc → sequence. It is
  correct, and the single-phase unit check confirms it.
- **The memory frame is right.** The memory measurement gets the normal-regime gains, and u_L is taken from that
  perturbed V1. A VT phase error common to all three phases therefore cancels in the relay frame, while unequal
  per-phase errors and the relative V–I error remain, as they should.
- **The regimes are right.**
  - The normal set uses one set of normal-regime gains for both the memory and the measurement: a CT carrying load
    current has one error.
  - A fault set has its own fault-regime gains on the fault windows, plus the memory's gains on u_L. Treating the two
    as independent is conservative and physical: a CT's error depends on its current.
- **Sampling.** Every row gets its own E, half at random corners and half uniform. That is the weak point in principle.
  The error is near-bilinear in gain × source, and its worst case for a given operating point is the corner aligned
  with the residual's gradient, which random corners rarely hit. So I tested exactly those.

## 2. Containment at the instrument corners that matter (`p44g_structured.py`)

At the design point (1.12 pu, 225°, class regime, the configuration of `frames_structured.py`), for 25 fresh source
points per set (with random λ, drift and reference rotation for faults), the instrument symbols were placed at the
corner aligned with each output component's residual gradient: the finite-difference dy/dE minus the fitted
instrument columns of J, for both signs of all 12 components. Then the distance to the set's own union was computed.
24 random corners per point serve as contrast.

| set | gradient-aligned corners outside the set | random corners |
|---|---|---|
| N | 0 / 600 | 0 |
| L1 A-G 15 %, 40 Ω (the binding case) | 0 / 600 | 0 |
| L2 A-G 50 %, 40 Ω | 0 / 600 | 0 |
| L1 B-C 15 %, bolted | 0 / 600 | 0 |

The remainder covers the bilinear terms, including at the corners the fit is least likely to have sampled. One HiGHS
numerical failure was retried with the interior-point solver; none failed after that. This is the design point only,
and four of the 49 sets.

## 3. The package for Taylor

Complete, with these labels:

| item | label |
|---|---|
| The design holds in EMT with δ injected (frames, filtered inverter, mimic chain) | one three-bus network, A-G and B-C to 40 Ω |
| D1's worst-case curve with Clopper–Pearson bounds | 70 dense scenarios; clean runs |
| Statistical detection needs no δ here (incremental 50N included) | 20 pilot scenarios |
| **Realistic systematic errors need no δ** | **Rephrase:** "no miss found over 289 sampled multiplicative settings (regime-dependent class bounds) × 3 white-noise seeds". That is a lower bound on misses, with white noise random, not at its k·σ worst. The structured worst-case design (gains at their worst, white noise at k·σ) does need δ at the class tier, 13 cases unseparated at δ = 0. The two are consistent: one is a worst case, the other a sample. Say which is which. |
| δ*(ε) for the box, with the design tier marked | static |
| Structured: design tier needs no δ; class tier needs 1.12 pu (about 93 % of rating) | static, containment checked (§2). **Note** that the class-tier 1.12 pu equals the ε = 0.08 box result only by coincidence of magnitudes; it is not the same set |
| B, the additive adversary | stress bound; D2 and D3 numbers are lower bounds |
| 80 Ω | static only; "where the guarantee needs the signal" |

One headline the package now supports, in Taylor's own terms: **the price of the guarantee is set by the instruments.**
At near-nominal instrument accuracy it is free. At protection-class fault-condition errors it takes about 93 % of the
inverter, on this network, to 40 Ω.

## Not checked

- Containment at other δ levels and the remaining 45 sets.
- `step3_multiplicative.py`'s results were read from the write-up and the JSON summary, not recomputed.
- REVIEW row 53's text beyond its verdict.
