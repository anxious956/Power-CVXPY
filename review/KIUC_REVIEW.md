# Review of the KIUC study (branch `kiuc`, `209c3f2`; results as of `5c883b8`)

> **Status, 31 Oct 2026 (evening).** Every fix asked for below is on `kiuc` as commit `8821d1d` (PR #65): the
> window aggregation registered as a dated addition (majority over the five windows, per-window counts kept), the
> incremental column re-read (R2 P 1.0 / Q 0: 6 / 0 / 6; R1 reverse: 10 / 2 / 0), row 62 and the entry points reworded
> to "on ground faults only at full output, no wrong-way decision at R1", 108 runs, the §6 base sentence, the TF2
> candidate struck, the Q3 framing sentence added. Checked against the diff `209c3f2..8821d1d`.

31 Oct 2026. Reviewed in a separate worktree. Read `docs/KIUC.md` in full, `src/kiuc.py`, the branch's diffs of
`src/network.py` (LIM 2, `frt_command`, the K2 law inside `solve_v1ref`), `src/pscad_inverter.py` (FRT and LIM 2 in
the Fortran block), `src/frames.py` (under-relaxed fixed point), `src/pscad_network.py` (BUILD_VERSION 6, `key_extra`),
`src/step3_frontend.py` (`mimic_tau`), REVIEW.md rows 60–65 and the README / PLAN rows. Every number in KIUC.md's
pre-flight, Q1, Fig.-16, Q2, Q3-design, Q3-extras and Q3-EMT tables was compared with the JSONs under
`results/network/kiuc_*.json`. Two independent checks were run, both in `review/checks/`: `p_kiuc_32q.py` (the two
elements re-decided from the raw PSCAD channels with my own phasor chain, all 121 clean fault runs) and
`p_kiuc_handcalc.py` (closed-form sequence networks, no project import). No `src/`, `tests/` or `results/` change
and no PSCAD run.

## Verdict

**Rows 61, 63, 64 and 65 hold as written** (63 with the label added in `209c3f2`). The reproduction of the report's
finding is the strongest result on the branch: with an independent phasor chain (plain one-cycle DFT, no mimic filter,
no memory frame) the report's element gives the same decision as `kiuc_q2.json` on 121 of 121 clean fault runs, and
the decision is identical on all five windows of every run.

**Row 62 needs one correction before it is quoted.** The incremental element's "0.92 right" at P 1.0 / Q 0 and the
"0.08 wrong" at R1 come from a "first decided window" rule that the registration did not fix and that happens to pick
the fragile window. On the later windows (2.5–3.0 cycles), in both phasor chains, the element misdirects **every B-C
case at P 1.0 / Q 0** (6 of 6; the static model says reverse for them too), and at R1 it has **no wrong-way decision**
(10 right, 2 undecided). So at full output FRT restores the positive-sequence element on ground faults only. §2.

Three text fixes (§3) and one framing sentence for Q3 (§4). Nothing here changes the go / no-go outcomes.

## 1. What was checked and found consistent

- **Tables against the JSONs.** Q1 (14 primary rows plus the sensitivities, 192 points each), the Fig.-16 pair by
  cycle, Q2 (11 rows: right / none / wrong, 3I2 ratio, EMT ≠ static, peaks, exclusions), Q3 design (12 cells: gaps,
  margins at ρ 0.1 and 0, binding pairs, price, no dead frames), Q3 extras (seeds identical to three decimals;
  margin 1.674 / 1.736 / 1.830 / 1.984 ε), Q3 EMT (8 tier cells: contained, separated, nearest other set, model
  error). Every quoted number is in its JSON within rounding. The go / no-go thresholds were met with the margins the
  text states.
- **The report's element, re-decided independently** (`p_kiuc_32q.py`): 121 of 121 agree with `q` in the JSONs;
  decisions uniform over the five windows on every run. The incremental element agrees on 118 of 121 first-decided
  windows; the three that differ are exactly the window-sensitive cases of §2.
- **Why the decision is so robust** (closed form, `p_kiuc_handcalc.py` (2)): under the law I2 = jK·V2 the relay sees
  V2/I2 = −j/K, so z2 = −(1/K)·sin∠Z1L = −0.190 pu against Z2F = 0.4|Z1L| = 0.0062 pu, thirty times the threshold on
  the forward side; saturation changes |I2| but keeps the angle, so LIM 1 / LIM 2 / K2 = 2 cannot move the decision.
  KIUC.md's "the decision does not depend on the limiter, only on whether I2 is controlled" is the right reading, and
  it is a property of the law's angle, not of this network.
- **The k2 restraint** (`p_kiuc_handcalc.py` (1)): A-G on YgΔ, hydro off, |I0| at R2 is 2.8–3.6 pu, so |I2|/|I0| is
  0.12–0.16 at the report's 0.45 pu (k2 blocks) and 0.33–0.42 at our saturated 1.2 pu (not blocked). KIUC.md's
  0.11–0.14 and "96 of 96 blocked" are consistent with this; row 64 stands.
- **Registration integrity.** The primary K1 (2 → 4) and limiter (LIM 2) were changed after the pre-flight and before
  Q1 and are recorded as such; the go / no-go thresholds were not touched; the Fig.-16 sanity is met on YgΔ only,
  which EMT never runs, and the text says so; the launch-order and duplicate-client deviations are recorded with what
  was discarded. The FRT = 0 regression (2.7·10⁻¹³ / 7.4·10⁻¹³ pu) keeps every earlier result.
- **The static-model bug (row 60)** is a genuine find and the fix is the right one: the law was a shunt outside the
  limiter and could not saturate; it now goes through the same limiter as PSCAD. The I2 study's quoted EMT runs stayed
  below the limit, so nothing already published moves.

## 2. The "first decided window" rule and row 62

`analyse_q2` reads five windows (2.0, 2.25, …, 3.0 cycles after inception) and keeps the **first window that
decides**. The registration said "windows ending 2–3 cycles after inception" and nothing about aggregation; the rule
appears first in the result text. For the report's element this is harmless (every run is uniform). For the
incremental element 6 of 108 clean runs change their decision between windows, all in the two groups the FRT
sub-question is about:

| group | case | `kiuc_q2.json` per window (2.0 … 3.0) | my chain | static |
|---|---|---|---|---|
| R2, P 1.0 / Q 0, suppressed, K1 = 4 | B-C 5 % from Bus-2, 0.01 Ω | f r r r r | f f r r r | r |
| | B-C 5 %, 5 Ω | r r r r r | r r r r r | r |
| | B-C 50 %, 0.01 Ω | f r r r r | f f r r r | r |
| | B-C 50 %, 5 Ω | f r r r r | r f r r r | r |
| | B-C 80 %, 0.01 Ω | f r r r r | f f r r r | r |
| | B-C 80 %, 5 Ω | f r r r r | r f r r r | r |
| R1 reverse, suppressed, K1 = 4 | A-G 50 % on EQ, 5 Ω | f r r r r | r r r r r | r |

The 2.0- and 2.25-cycle decisions differ between the two chains (mine has no mimic filter and a different memory
average); from 2.5 cycles on both chains agree with each other and with the static model. Aggregates:

| group | rule | right / none / wrong |
|---|---|---|
| R2, P 1.0 / Q 0 | first decided (KIUC.md, row 62) | 11 / 0 / 1 (0.92 / 0 / 0.08) |
| | majority of the five windows, or last window | **6 / 0 / 6**: A-G 6 of 6 right, B-C 0 of 6 |
| R1 reverse | first decided (KIUC.md, row 62) | 9 / 2 / 1 (0.75 / 0.17 / 0.08) |
| | majority, or last window | **10 / 2 / 0** |

So the two numbers row 62 quotes for the FRT finding are the two that the rule decides. What the data supports:

- **R2 at P 0.25 / Q 0.15**: 12 of 12 right on every window, both grid cases (unchanged).
- **R2 at P 1.0 / Q 0**: FRT restores the element on the six ground faults and **misdirects all six phase-to-phase
  faults** from 2.5 cycles on; the static model says reverse for all six as well (that is what "EMT ≠ static: 5" in
  the Q2 table is). A plausible mechanism, not checked: at full output with q priority the FRT command is mostly a
  cut of I_P+, and the superimposed current then does not have the angle to ΔV1 of a source behind the relay.
- **R1 reverse**: 10 of 12 right, 2 undecided (the two 5 Ω faults at 5 % that barely dent |V1|: 0.99 and 0.94),
  **no wrong-way decision**; static had 0.11 wrong. The pre-registered expectation "fewer wrong and more undecided
  than static" holds, more strongly than stated.

**Fix.** State the aggregation rule in the Q2 registration block as a dated addition (per-window counts as in
I2_DIRECTION stage (c), or the majority of the five windows), re-read the incremental column with it (the report's
column does not change), and reword the FRT paragraph, the status header line, row 62 and the README row from
"R1 reverse 0.75 right, 0.08 wrong" and "R2 drops to 0.92" to the ground-fault-only statement at P 1.0 / Q 0 and the
0 wrong at R1. The headline "with IEEE 2800-style FRT the positive-sequence element recovers" needs the qualifier
"on ground faults at full output, on every case at a quarter output".

## 3. Text fixes

1. **"0 of 107 clean fault runs differ"** (Q2 reading; row 61 "all 107"): the nine LIM 2 groups have 12 clean fault
   runs each, 108; with the 13 clean LIM 1 runs, 121. My re-decision used 121.
2. **§6 "per-spec base (S_base, V_LL) instead of the module constants 10 MVA / 20 kV"**: the code does not do this.
   `pscad_network.SBASE, VLL` are still 10 MVA / 20 kV, the sources are built at 20 kV, and the relay (`step3_frontend.
   Relay`, `pscad_network_check.seq`) divides by the same peak bases. Because the KIUC network enters as per-unit
   impedances (Table 14 over Z_B = 217.4 Ω) and everything in PSCAD is scaled by the same base, the results are
   base-independent and correct; §6 should say that the system is built per unit on the 10 MVA / 20 kV base, not
   that a per-spec base was added.
3. **The "unresolved difference" (their I_Q− = 0.45 pu at K = 5 against our 1.2 pu)**: candidate 1, "their V2 is
   measured behind TF2's series impedance", cannot carry it alone at the registered X_TF2 = 0.06 pu
   (`p_kiuc_handcalc.py` (3)). With the law acting on the terminal voltage, the inductive I2 lowers V2 across TF2 and the
   effective gain seen from Bus-2 is K_eff = K/(1 + X_TF2·K) = 3.85; |I2| still saturates at 1.2 pu for any |V2| at Bus-2 above 0.31, and 0.45 pu
   needs |V2| at Bus-2 ≈ 0.12 pu, where the forward set gives 0.23–0.35 under the law (0.29–0.40 with I2 suppressed).
   Candidate 2 (a farther fault / a weaker dip) or a different definition of K or of the current base in the report
   remain; the paragraph should say so rather than leave the two candidates level.

## 4. Framing of Q3 (row 63)

The label added in `209c3f2` ("the design's sets; static design, EMT at the nominal point, clean runs, FRT off; not a
field claim") is the right one. One more sentence belongs beside it: **the margins are large because the sets differ
in |V1| and |I1| by a lot**. At R2 every forward fault pulls |V1| at the inverter to 0.50–0.80 pu against ~1.02 in
normal operation; at R1 the reverse set's relay current is the IBR's 0.29 pu against several pu for a forward fault.
The set test reads those; so would an undervoltage-supervised or memory-polarised positive-sequence directional
element. "The set test needs neither the law nor δ" is therefore a comparison with **the two elements tested** (the
negative-sequence 32Q / 32QG and the superimposed element without FRT), not with conventional protection in general,
and the text should say "the two conventional elements tested" where it now says "the conventional elements".
The prior's rewording ("δ buys the guarantee where the guarantee is not already free") is fine.

## 5. Smaller points, no action needed

- `dir32q` skips the k2 test when |I0| < 10⁻⁹; on ΔYg in EMT the DFT leaves a non-zero numerical I0, but the pickup
  test runs first, so a suppressed run is "3I2 below pickup" before k2 could fire, and under the law |I2| ≈ 1.2 pu
  dwarfs any numerical I0. Fine as is.
- The FRT in EMT acts on the 15 Hz-filtered |V1|, so inside the relay window I_Q+ is still rising (0.74 at 2.5
  cycles against 0.82 static). This makes the EMT incremental results see less FRT than static, which is the
  direction of the observed differences and is stated.
- The hydro as a source behind X''d with EMF 1.0∠0 and no pre-fault output is an assumption the text records; for a
  3-cycle window and these relays it is immaterial.
- LIM 2's 2.2 pu phase peaks are reported on every row and the label "the report's limiter as its Fig. 16 shows it"
  is honest; the EMT reproduction under a physical limiter rests on LIM 1's A-G runs only (B-C unstable, row 65),
  and the text says so.

## Not checked

- The Q3 set-test computations (containment and separation through `FrameModelMulti`) were read through
  `kiuc_q3_emt.json` only; the independent chain here does not reproduce the design's sets.
- The Fortran FRT block beyond reading; the LIM 1 B-C instability mechanism (row 65) beyond the diagnostic's numbers.
- One point on wave, the nominal source point in EMT, clean measurements: the branch's own caveats, kept.
