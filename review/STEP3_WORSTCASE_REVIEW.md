# Review of step 3's worst-case study (PR #44, `978e14e`, `30d9746`, `6804087`, `d0dafb4`)

17 Oct 2026. Reviewed in a separate worktree, reading `src/step3_adversary.py`, `src/step3_worstcase.py`,
`src/frames_rf80.py`, `results/STEP3_PILOT.md` and the JSON outputs. No `src/`, `tests/` or `results/` change and no runs.

## Verdict on what goes to Taylor

| Item | Send now? | Condition |
|---|---|---|
| The design holds in EMT with δ injected (frames, filtered inverter, mimic chain); cost 93 % of rating at ε = 0.08 | **yes** | |
| D1's worst-case curve (option A): hard A-G guaranteed 0.33 [0.19, 0.49] at δ = 0 → 1.00 [0.91, 1] at ¾ δ* | **yes** | It is Taylor's own guarantee measured in EMT with δ injected, on clean runs, with binomial bounds |
| Statistical detection does not need δ on this network (D0 incremental, D1, D2, D3 all detect every pilot fault) | **yes** | Say "20 pilot scenarios", and that D0 is the incremental element |
| δ* is set by the noise bound: 1.12 pu at ε = 0.08, 0.04 pu at the front end's bound | **as a curve, not as "≈ 0"** | The 0.029 / 0.053 pu bound is the **design tier** (CT ≤ 1 %, VT ≤ 0.5 %, 0.3°), near-nominal accuracy. At fault-condition class errors (CT 5–10 %, VT 3–6 %, 2–4°) the bound is wider than ε. Compute δ* there, or show it is infeasible, and present δ*(ε) with both tiers marked |
| Each detector against its own worst case (option B) | **not yet** | §2: a multiplicative systematic adversary, worst-case thresholds over a dense normal set, PGD restarts |
| 80 Ω as "where the signal is needed" | **not yet** | Static only (δ* 0.94 pu at the measured bound, ρ = 0). Needs the ρ = 0.1 and design-ε runs, an EMT check of the model error at 80 Ω, and a pilot showing the statistical detectors also struggle there. Otherwise it is "where the guarantee needs the signal", which is a different claim |

The message that holds today: **on this network, with δ injected in EMT, Taylor's design keeps its promise. But the
promise is a worst-case one, its price is set by the assumed noise bound, and under realistic noise the conventional
incremental element already detects the faults the signal was designed for.** That is a clear, defensible answer to
his question about where a designed signal earns its cost.

## 1. The adversary code (`src/step3_adversary.py`)

| Part | Finding |
|---|---|
| D1, per-window | "every window within 2ε of N" is exact for an ∞-norm box: moving y by up to ε toward its nearest point of N cuts the distance by exactly min(ε, d). Correct |
| D1, constant | The LP with a shared e, per-window coefficients and ε tolerance, over all 2⁵ piece combinations, is the exact miss condition (each window is tested on its own by the relay's rule). Correct |
| D0 | The box algebra (`_box_min_abs`, `_box_max_abs`) is right, and the max(3\|ΔI0\|, \|ΔI2\|) minimisation separates. **Small overstatement:** per window, the code lets the memory's perturbation differ for each window (r = 2ε each). The memory is one measurement, so its error is shared. The true worst case is min over e_mem of max over w, which is ≥ what the code finds, so D0's per-window misses are slightly overstated. It does not change "D0 misses everything per window" (3\|ΔI0\| of 0.47–0.93 pu against 6√2·ε ≈ 0.68 pu of adversary power) |
| D2 | The closed-form two-window Gaussian per mode is right (Q = JJᵀ/3 shared across the windows, R per window). The PGD is 60 sign steps of 0.08ε from e = 0, with **one start**. The log posterior odds of a mixture is not concave, so these are **misses found, a lower bound**. Add restarts (random corners of the box, and D1's worst direction as a start) |
| D3 | The feature mapping matches `d3_features` exactly: [Re y, Re Δ, Im y, Im Δ]. With the constant adversary the Δ channels get 0, and with per-window the memory perturbation is shared across frames. Normalisation is inside the graph. Correct, with the same lower-bound caveat |

## 2. Before option B can go to Taylor

1. **Model systematic error as multiplicative.** The "constant" adversary adds one fixed phasor e to every window and
   to the memory, so it cancels exactly in an increment and D0 looks immune. Real systematic instrument errors are
   ratio and phase errors, per phase and constant over the run: I → (1 + r)·e^{jφ}·I. They scale the increments
   instead of cancelling in them, and they move D1's absolute measurement by about r·|y|. Under CT 10 % on 0.5–1 pu of
   fault current that is about ε. So the physically faithful systematic adversary is **multiplicative within the
   class bounds**. Run it for all four detectors. The additive per-window adversary is then labelled as a stress
   bound.
2. **Make the worst-case thresholds comparable.** D1's threshold covers all of N by construction. The thresholds of
   D0, D2 and D3 are the largest adversarial score over 4 pseudo-triggers × 20 runs at each level, i.e. 20 operating
   points. A worst-case threshold needs the worst normal operating point too. Take the 16 box corners plus random
   interior points (static model, or EMT pre-fault windows). Otherwise their thresholds are optimistic and their
   worst-case misses are understated, which favours them against D1.
3. **Worst-case false alarms on normal runs rest on 2 runs per level** (the other two normal-kind runs are confusers).
   "None alarms on a normal run" should say so, or wait for the dense normal set of point 2.
4. **PGD restarts for D2 and D3** (§1), and report their numbers as "found by a 60-step search".

## 3. The reading in STEP3_PILOT.md

**Correct:**
- the D0 correction and withdrawal (REVIEW row 52);
- the flat statistical table;
- the worst-case curve and its bounds (spot-checked against `worstcase_dense.json`'s structure);
- the 80 Ω table labelled static.

**Wording to change:**
- **"At the noise bound the front end actually has, the design needs no signal"** → "at the design tier's noise bound
  (near-nominal instrument accuracy)". Add the class-tier result when it exists.
- **"Against a constant (systematic) error the picture turns round for D0: the incremental element is immune"** →
  "against an additive constant offset". With multiplicative systematic errors (§2.1) the increments shrink by the ratio
  error but do not vanish. D0 then still detects these faults, and D1 is the one exposed. So the conclusion may stay,
  but for the right reason.
- **"None of the four detectors alarms on a normal run"** → "on the 2 normal runs".
- **"D0 and D3 fail at every δ against a per-window adversary"**: true, but say that a per-window adversary hits an
  incremental detector twice (memory and window independently, 2ε on every increment), so this is a stress bound and
  not instrument behaviour.

## Not checked

- `step3_worstcase.py` was not re-run. The dense curve was read from the write-up and the JSON structure.
- The 80 Ω runs at ρ = 0.1 and at the design ε (still running).
- D3's training on the design tier.
