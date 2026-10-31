# Review of the I2-direction study (PR #57, `i2-direction` at `1b7e5d3`)

> **Status, 19 Oct 2026.** The three fixes of §5 were made (`8d3fb26`); PR #57 and this review (PR #58) are merged.

18 Oct 2026. The whole branch was reviewed in a separate worktree: `docs/I2_DIRECTION.md`, `src/i2dir_*.py`,
`src/frames_multi.py`, the `pscad_inverter.py` and `pscad_network.py` changes, the result JSONs and REVIEW rows 56–59.
The stages were also reviewed one by one as they were written (messages to the research session). This file is the
whole-branch verdict. No `src/`, `tests/` or `results/` change and no new PSCAD runs. Four checks in
[`checks/`](checks/): `p_i2dir_sinks.py`, `p_i2dir_backz2.py`, `p_i2dir_b2_frameturn.py` and `p_i2dir_tv2_hf.py`.

## Verdict

**The study's conclusions hold, and the branch can merge after three small fixes (§5).** The process was sound:
- every stage was pre-registered before it ran;
- the two deviations are disclosed (the order of the box-point launch, and the JSON rebuilt from the log after a
  MemoryError);
- failed gates were not interpreted (the first grid-side IEEE 2800 run).

The fixes:
- one wrong number in REVIEW row 56;
- the (b2) hypothesis, which `p_i2dir_b2_frameturn.py` now supports statically at the box point;
- a residual numerical mode in the grid-side IEEE 2800 runs that the doc calls "stable".

The last one does not change a decision, but it needs a caveat.

## 1. What the study now says (the reading I endorse)

On the three-bus network, with the relay at the inverter's bus. The scope is one network, the nominal source point,
one point on wave and clean runs:

1. **I2 suppression breaks direction only when nearly all of the load behind the relay is inverter-interfaced
   (s → 1).** At s = 0.8 only dependability is lost (static). At s = 1, in EMT, 80 % (grid-side control) and 68 %
   (converter-side) of the forward set is lost, 20 % and 40 % of it wrong-way. Reverse faults are never wrong.
2. **IEEE 2800's negative-sequence current restores direction in EMT in both control brackets**: 0 % misdirected
   forward and reverse.
3. **A designed δ does not fix the conventional element.** In EMT with δ injected, forward misdirection is 0.44 at the
   structured point and 0.96 at the box point, against 0.40 without δ. Row 46's prior holds.
4. **The set test decides direction where the conventional element fails.**
   - At δ = 0, the EMT runs are point-separated for every B-C case (the conventional element sends every forward
     B-C reverse), and for A-G under the structured tier.
   - The designed δ adds the worst-case guarantee over the whole sets: 50/50 EMT runs contained and separated at
     both points.
   - **δ buys the guarantee, not the decision**, as in step 3.
5. **The price is set by the instruments**, as in step 3. The structured tier needs 0.20 pu and leaves I1 untouched.
   The box tier needs 0.98 pu, which displaces 46 % of the inverter's normal positive-sequence output all the time.
   Both set margins are thin (0.024 and 0.048 ε) but stable across seeds (spread about 0.003 ε).

## 2. Independent checks

**`p_i2dir_sinks.py`** (my own static model of the s-sweep, written before the branch's (a''), re-run at `1b7e5d3`).
It reproduces the branch's (a'') exactly. Suppressed law, forward set, 16 corners:

| s | fixed phasors | fixed, pickups | V1-referenced | V1-referenced, pickups |
|---|---|---|---|---|
| 0 | 0.00 | 0.00 | 0.00 | 0.00 |
| 0.5 | 0.00 | 0.20 | 0.00 | 0.05 |
| 0.8 | 0.00 | 0.60 | 0.00 | 0.28 |
| 1 | 0.00 | 1.00 | **0.44** | **0.68** |

The "fixed phasors" column is the degenerate model of stages (a) and (a'). Its 0.00 at s = 1 without pickups comes
from decisions taken on the ~1e-6 pu currents of the 1e6 "open" shunts. Row 59 is right to supersede it.

**`p_i2dir_backz2.py`.** With the RC filter shunts and the suppressed source, the back-side negative-sequence impedance
is 1.18 − j10.57 pu (∠ −83.6°). A forward fault therefore looks like +10.4 pu on the line angle, so any
negative-sequence directional element calls reverse, not only ours. This explains why the shunt bracket misdirects
more (40 %) than the grid-side bracket (20 %).

**`p_i2dir_b2_frameturn.py`, the (b2) hypothesis, static, nominal source point, shunt bracket.** It splits ΔI2 at the
relay into a fault part (the same fault at δ = 0) and a signal part (the rest), and compares the signal part with the
delivered δ's own change between normal operation and the fault:

| point | forward wrong or undecided | signal part larger than fault part | wrong decisions following the signal part's direction | signal part vs δ's own change, median relative difference |
|---|---|---|---|---|
| box 0.98 pu @ 205° | 25 of 25 | 24 | 24 | 0.15 (A-G), 0.07 (B-C) |
| structured 0.20 pu @ 230° | 15 of 25 | 15 (all A-G) | 1 | 0.11 (A-G), 0.27 (B-C) |

- **At the box point the hypothesis holds statically.** ΔI2 is dominated by the injected signal's own change, which
  is its frame turn and the limiter, to within 7–15 %. The element follows that change in 24 of the 25 wrong
  decisions. It reads the inverter's reaction, not the fault.
- **At the structured point it does not explain the failures.** The B-C misdirection there is the δ = 0 mechanism,
  the capacitive back side: the fault part dominates in all 10 B-C cases. The signal dominates A-G, but mostly points
  the right way (1 wrong decision follows it).
- The nominal static counts (25 and 15 wrong or undecided) match EMT (24 + 1 and 11 + 5).

**`p_i2dir_tv2_hf.py`, the grid-side IEEE 2800 runs with TV2**, from the stored PSCAD output:
- the normal run is not steady. Its per-cycle peak drifts between 0.92 and 1.02 to 0.40 s, then rises to 1.15 by
  0.45 s. 5.8 % of the spectrum after 0.30 s sits at the output Nyquist (9.98–10 kHz);
- in the fault runs, the pre-fault memory span (0.25–0.30 s) carries 2.9e-3 of its energy above 5 kHz, and the fault
  span 0.30–0.35 s carries ≤ 1.2e-3 (median 1.7e-4).

So TV2 slowed the numerical mode; it did not remove it. The registered gate, a tail peak below 1.5, passed by its
letter, and the fault spans meet the per-run check. The decisions are not affected:
- an oscillation of about 5 % of the fundamental at about 10 kHz leaks into a one-cycle DFT phasor at roughly 1e-3 of
  its amplitude, about 1e-4 pu;
- all 50 runs agree with static.

But "stable" overstates it (§5.3).

## 3. Numbers in the doc and REVIEW against the result files

Each table and row of `docs/I2_DIRECTION.md` (stages c, TV2, b0, b1, b2) and REVIEW rows 56–59 was checked against the
JSON. All of them agree, with one exception:
- **REVIEW row 56** says "EMT agrees with static on 24 or 25 of 25". `i2dir_emt.json` has 5 of 25 forward
  disagreements in the grid-side (no-shunt) bracket, with 3 window flips. Only the shunt bracket has 24 of 25.

The stage-(c) doc text has it right ("differ on 5 of 25 cases").

## 4. Code points checked (summary of the stage reviews)

- **`frames_multi.FrameModelMulti`.** Regressions to round-off against FrameModel with no sinks, and against
  solve_v1ref at δ = 0 and at δ ≠ 0, including 5 limiter-active settings (≤ 1.9e-12). The per-bus dead-frame rule
  never triggers at any design point. The under-relaxed fixed point is unique where checked, and it is the point the
  TANG dynamics reach.
- **Builder.** The shunt topology, solver step and inverter set are in the fast-mode key. The neutral is tied to
  ground through 1e8 Ω. Iinv reads the injection only. BUILD_VERSION is 5, with a TV2 = 0 regression exact to 0.000.
  The DFT buffer clamps below about 9.8 µs, which is why the 2 µs diagnostic was rightly dropped.
- **TV2** filters the demodulated V2 phasor, so the 60 Hz law is unchanged in steady state.
- **Set test in EMT.** Every window from 2 to 3 c must be contained and separated (stricter than the first decided
  window), in the relay's memory frame.

## 5. Before merging

1. **Fix REVIEW row 56:** "EMT agrees with static on 20 of 25 (grid-side) and 24 of 25 (converter-side)".
2. **Replace the "untested" hypothesis paragraph** with the static result above (cite
   `review/checks/p_i2dir_b2_frameturn.py`):
   - at the box point, ΔI2 is dominated by the injected signal's own change and the element follows it in 24 of
     25 wrong decisions;
   - at the structured point, the B-C failures are the δ = 0 capacitive mechanism.
   - Label it "static, nominal point".
3. **Narrow "stable" in the grid-side IEEE 2800 section and in row 57:** "with TV2 the numerical mode is slowed, not
   removed: a residual ~10 kHz component (2.9e-3 of the pre-fault energy, the normal run growing to 1.15× by 0.45 s).
   The decisions are read inside 0.35 s, where the one-cycle DFT rejects it, and all 50 runs agree with static." The
   cell stays a valid result with this caveat. The clean bracket is the converter-side one.

## Not checked

- `src/i2dir_b1_followup.py` and the zonotope distance code beyond their outputs.
- The structured-tier containment at gradient-aligned instrument corners. It was done for step 3's sets
  (STEP3_STRUCTURED_REVIEW.md), not for these.
- Anything off the nominal source point in EMT. Other networks, inception angles, noise, and the positive-sequence
  K-factor limitation stated in the doc.
