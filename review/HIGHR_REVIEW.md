# Review of the high-resistance follow-up (`step3-highR`, `fa60d0c`, `988f93e`)

17 Oct 2026. Reviewed in a separate worktree: `src/highr_screen.py`, `src/highr_design.py`, `results/HIGHR.md`. No
`src/`, `tests/` or `results/` change and no PSCAD runs. Two static checks in [`checks/`](checks/):
`p_highr_lift.py` and `p_highr_types.py`.

## Verdict

**The conclusion "the band is empty" does not hold as stated.** It comes from the B-C cases, not the A-G ones. At
160 Ω the signal (1.12 pu at 315°) separates **every** A-G case in the design's own sets. Incremental 50N/50Q is
below its pickup at half the locations there (HIGHR.md: 4 of 8). So on this network **there is a band, around
160 Ω for ground faults, where the conventional element fails and the signal guarantees detection.** The Taylor
package is not final until this is corrected.

## 1. Is the single-R_f case set fair?

Yes, and in the conservative direction. A design facing only the R_f cases faces a subset of a 0…R_f range's cases,
and fewer fault sets can only make separation easier. So "infeasible at a single R_f" implies "infeasible for the
range". It does not explain the result.

## 2. What makes the high-R design infeasible: the B-C cases

`p_highr_types.py` re-runs the design's own set separation (structured design tier, white box V 0.02 / I 0.04, ρ = 0,
exactly `highr_design.py`'s model), for the A-G and the B-C cases separately:

| R_f | fault type | δ = 0 | 1.12 pu at 0° | at 270° | at 315° |
|---|---|---|---|---|---|
| 160 Ω | A-G | 8/8 unseparated | 8/8 | 8/8 | **0/8** |
| 160 Ω | B-C | 6/8 | 8/8 | 8/8 | 8/8 |
| 200 Ω | A-G | 8/8 | 8/8 | 8/8 | 8/8 |
| 200 Ω | B-C | 8/8 | 8/8 | 8/8 | 8/8 |

At 160 Ω the A-G cases are guaranteed at 315°, and the 16-case design fails only because of B-C. But **high fault
resistance is a ground-fault phenomenon**: tree contact, high-impedance surfaces, tower footing. A phase-to-phase fault
carries only arc resistance, a few ohms. A B-C case at 120–200 Ω is not a realistic member of the high-R set. The
conventional screen (`highr_screen.py`) also tested A-G only, so "conventional fails from 160 Ω" (A-G) and "the
signal runs out from 120 Ω" (A-G + B-C) were measured on different fault sets.

**Fix:** re-run the high-R design on A-G only (with B-C at most up to its arc-resistance range, as in the 40 Ω
design), with the full polar search, at 120 / 160 / 200 Ω. On the angles tested, 160 Ω is feasible for A-G and 200 Ω
is not. The full search will place the boundary.

## 3. Statistical detection at 160–200 Ω, and how much the outer sets cost

`p_highr_lift.py` takes clean A-G faults at 30 random source points per location (8 locations) and computes their
distance to N, in units of the per-component box:

| R_f | δ | D1 alarms (> 1 box) | guaranteed (> 2 boxes) | smallest distance |
|---|---|---|---|---|
| 160 Ω | 0 | **1.00** | 0.49 | 1.32 |
| 160 Ω | 1.12 pu at 315° | 1.00 | **1.00** | 2.91 |
| 200 Ω | 0 | **0.99** | 0 | 0.95 |
| 200 Ω | 1.12 pu at 315° | 1.00 | **1.00** | 2.26 |

Two things follow:
- **D1 detects high-R A-G faults without the signal** under small noise: 99–100 % of clean faults are already outside
  N by more than the box. Incremental 50N/50Q is below its pickup there. The set test, which uses the voltages as
  well, is the better conventional-style detector at high R; the signal adds the guarantee. That is the same pattern
  as at 40 Ω, one step further out.
- **At 200 Ω the sampled faults are all guaranteed at 315° (smallest 2.26 boxes), while the design's sets say 8/8
  unseparated.** The difference is the outer approximation: worst source corners, the remainder, the reference
  rotation and the model-error box. 30 random interior points do not reach the set's extremes. So 200 Ω A-G is
  "not guaranteed by the design", not "not separable". Say that, rather than "the signal runs out".

## 4. The corrected reading

On this network, for ground faults:
- **to about 120 Ω** conventional incremental detection works without δ (as at 40 Ω);
- **around 160 Ω** it starts to fail (4 of 8 locations below pickup). The signal, at 1.12 pu and 315°, **guarantees**
  every A-G case in the design's sets. That is the band where Taylor's method does something the conventional
  element cannot, at the price of about 93 % of the inverter;
- **at 200 Ω** the design no longer guarantees A-G at the angles tested, though sampled faults are all separated.
  It is at the edge of what the outer sets can certify;
- throughout, the set test D1 detects these faults statistically without δ.

B-C faults at high resistance are excluded as unrealistic. Report B-C at its arc-resistance range only.

## 5. The Taylor package

**Not final.** Revise HIGHR.md and finding 6 of `docs/notes/step3_for_taylor.md` along §4, after the A-G-only design
re-run with the full angle search. This finding becomes the package's most interesting one for Taylor: **on a
synchronous-source grid, the designed signal earns its cost for ground faults around 160 Ω**, where the conventional
incremental element fails and the guarantee still exists. It needs an EMT check, with the same machinery as before
(witnesses, edges, point on wave), before it goes to him as a result rather than a static finding.

## Not checked

- The full polar search for A-G only at 120 / 160 / 200 Ω (only 0°, 270° and 315° here).
- EMT at high R_f.
- `highr_screen.py`'s worst-corner D0 scores were taken from HIGHR.md.
