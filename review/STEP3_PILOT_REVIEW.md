# Review of the step-3 pilot (PR #44, `2b91bff`, `416c4c5`)

17 Oct 2026. Reviewed in a separate worktree, reading `results/STEP3_PILOT.md`, `results/step3/*.json` and the code.
No `src/`, `tests/` or `results/` change and no PSCAD runs. One static check:
[`checks/p44e_gaps0.py`](checks/p44e_gaps0.py).

## Short answer

**(b) did not fail spuriously. It could not have passed with this design and D1's threshold.** At δ = 0, every one of
the 14 cases the design leaves unseparated is still **at least 1.02ε** from N in the design's own sets. D1 alarms
above ε, so no clean fault inside the design's fault set can be missed at δ = 0. A miss needs measurement noise
pointing toward N by more than the gap minus ε (0.02ε for the hardest case, up to 1.05ε for the others). Random
noise, even at the ε scale, almost never does that. The pilot's reading stands: **on this network the signal buys a
worst-case guarantee, not detection.**

**Recommendation: A, plus a corrected B, plus one static curve; defer C to Taylor.** It is all offline or static, and
all inside the four steps (§3).

## 1. Is the hard stratum hard at δ = 0?

`p44e_gaps0.py` computes, in the main design configuration, the closest-pair gap between N(0) and each binding case's
F(0). It also computes the clean distance to N(0) of a fault placed at the δ = 0 witness's source point, and at the
δ* witness's source point, which is what the pilot's hard stratum used.

| case (40 Ω unless stated) | gap at δ = 0 | clean fault at its δ = 0 witness | at the δ* witness (pilot) |
|---|---|---|---|
| L2 A-G 50 % | **1.02ε** | 1.20ε | 1.20ε |
| L2 A-G 25 % | 1.13ε | 1.34ε | 1.34ε |
| L2 A-G 5 % | 1.27ε | 1.49ε | 1.49ε |
| L1 A-G 95 % | 1.35ε | 1.57ε | 1.57ε |
| L1 A-G 75 % | 1.50ε | 1.73ε | 1.73ε |
| … (9 more) | 1.67–2.18ε | | |

- **No gap is below ε (0 of 14); 11 are below 2ε.** So at δ = 0 the design is not unseparated in the sense "a clean
  fault looks normal". It is unseparated in the sense "some noise inside the ε box could hide the fault". (b)'s test,
  "D1 and D0 miss ≥ ¼ at δ = 0", asked for the first. The design only predicts the second.
- **Using the δ* witnesses was not the problem.** Their source points differ from the δ = 0 witnesses' (up to the
  opposite corner), but the clean distance to N(0) comes out the same. The direction that makes A-G faults hard is
  set by the fault, not by the operating point.
- The pilot's EMT clean scores at δ = 0 (1.3–2.6ε) match these static figures.

## 2. Code checks

**Correct, with no effect on (b):**
- **Front end:** systematic CT/VT ratio errors and white noise on the samples, before the mimic; noise set by its
  post-filter phasor std (Monte Carlo ×2.69 std, matching the analytic ×2.7); VT phase error on the voltage phasors,
  so the memory frame turns with the voltages and the currents see the relative V–I error, as intended.
- **Starter from 0.2 s.**
- **Memory frame:** V1 averaged over windows ending 0.5–2.5 cycles before the trigger.
- **D1:** design threshold ε, maximum over the 2–3-cycle windows, main sets.
- **D2:**
  - each mode's recursive update is the right Kalman step for constant symbols (prior I/3, the moments of U[−1, 1]);
  - the remainder variance is r²/3, plus the post-filter noise variance;
  - two updates on non-overlapping windows;
  - both eq. (14) and the Gaussian rule;
  - calibration pseudo-triggers lie wholly before the fault.
- **D3:** frames 1/4–3 cycles, folds grouped by scenario.

**Worth fixing before the full study:**
1. **D0 uses total |I2| and |3I0|.** Its pickup has to clear the steady designed δ, which is why "the signal hurts
   50Q" (pickup 0.16 → 0.90 pu). Relays on inverter-fed lines use incremental (superimposed) quantities. A Δ50Q/Δ50N,
   relative to the pre-fault memory as D3's features already are, is the fair floor. Without it, finding 3 of
   STEP3_PILOT.md overstates the harm.
2. **D2 sees white noise only.** At the design tier the CT/VT ratio draws are ≤ 1 % and ≤ 0.5 %, which is fine. At the
   class tier (5–10 % CT, 3–6 % VT, 2–4° VT phase) the systematic errors dominate, and D2's Gaussian would be
   over-confident. Add the systematic draws to its covariance, or report D2 only at tiers where they are negligible.
3. **D0 and D2 calibration** uses the largest score over six pseudo-triggers per run, on the same 20 scenarios'
   pre-fault data. That is fine for a pilot. In the full study, calibrate on normal scenarios disjoint from the test
   set (review of the plan, §2.3).

## 3. Direction

The pilot answered the question the deck asked, in its first form: **no detector needs the signal to detect these
faults under the noise a relay meets.** That is a result, but the experiment should be pointed where Taylor's claim
actually lives: bounded, worst-case noise.

- **(A) Yes: densify the worst-case curve.** The fraction of faults with clean distance > 2ε, against δ, on clean runs
  with binomial bounds. It is Taylor's own guarantee measured in EMT with δ injected, and it is cheap: one clean run
  per scenario and level, no noise draws.
- **(B) Yes, but each detector against its own worst case, not D1's.** Applying D1's worst ε-box perturbation to D2
  and D3 is a transfer attack, and it favours them, because the direction that hurts D1 need not hurt them. The fair
  comparison of a worst-case claim is each detector's worst case inside the same bounded-noise set:
  - **D0:** the ε-box perturbation that minimises max(|Δ3I0|, |ΔI2|). A small LP-like problem per window.
  - **D2:** maximise P(normal) over the ε box by projected gradient on the windows' inputs.
  - **D3:** PGD on the CNN's input inside the ε box.

  The perturbation should be systematic over the run, constant across windows, as instrument error is. Then "shrink δ
  until each fails" means **the smallest δ at which each detector has no worst-case miss**, which is exactly the
  protocol the deck promised, read in Taylor's sense.
- **Add one static curve: δ*(ε) at the measured noise bound.** The design's ε = 0.08 pu is about 1.5× (currents) and
  2.8× (voltages) the front end's k = 4 design-tier error (criterion (e): 0.053 / 0.029 pu). The tool can compute δ*
  for an anisotropic box at those values, and at the class tier. If δ* falls to 0 or near it at realistic bounds, that
  is the cleanest statement of the step-3 result: the signal is needed only against noise bounds wider than the
  instruments produce. This is Taylor's own parameter, so it stays inside his formulation.
- **(C) Defer, and ask Taylor.** Higher R_f (40–200 Ω) or task T2 is a new design. On this network the design already
  takes 93 % of the inverter at 40 Ω, so a static feasibility check at, for example, 80 Ω would likely answer
  "infeasible within the cap" by itself. Run that check before proposing C. It is one search, no EMT.

## Not checked

- The CNN's training details and its confuser false alarms (pilot-sized, as the write-up says).
- The class and stress tiers' tables beyond the summary in STEP3_PILOT.md.
- Gaps at δ = 0 use the search tier (150 samples), not the dense one.
