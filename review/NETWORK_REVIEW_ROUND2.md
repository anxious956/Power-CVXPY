# Review round 2: the fixes of PR #40

16 Oct 2026. Reviewed PR #40 (`fix-review-findings` at `3da5e5c`, open) against the findings of
[NETWORK_REVIEW.md](NETWORK_REVIEW.md). The work was done in a separate worktree; nothing in `src/`,
`tests/` or `results/` was changed. New check scripts are in [`review/checks/`](checks/):
`check_line_guard.py`, `check_tests_bite.py`, `check_guards.py`. They import PR #40's code, so they run
only once #40 is merged (or in its checkout). The round-1 scripts were rerun on #40's checkout.

**Tests on #40:** 150 passed, 4 skipped, as claimed. This needs the git-ignored `data` junction to D:.
Without it, the six `test_location_orientation` cache tests skip (148 passed, 6 skipped). That is an
environment difference, not a code one.

## Verdicts

| # | Finding | Verdict |
|---|---|---|
| 1 | `tac25_channels` got the −u_F rows | **fixed** (no regression test for the +1 path) |
| 2 | PSCAD line model not exact on meshes | **fixed in code; docs partly** (three places still say "any network") |
| 3 | fault-time turn of I1 and δ | **partly fixed** (numbers right; headline still overstated, one table label unchanged, README unqualified) |
| 4 | inverter curtailment unstated | **fixed** in MULTIBUS.md (README not updated, see 3) |
| 5 | REVIEW.md claim 3 stale numbers | **fixed** |
| 6 | sign tests that don't bite | **fixed** |
| 7 | `real_ml.phasor_view` shift | **fixed** (the existing test still doesn't pin it) |
| 8 | silent drops in `make_spec` | **fixed** |
| 9 | m = 0/1, LP-status handling | **fixed** |
| 10 | frame needs a single-branch relay bus | **partly fixed** (SG count and location at the relay bus not asserted in `analyse`) |
| 11 | stale output reuse | **fixed, with two residual gaps** (`run_specs` doesn't clear old output; fingerprint excludes build arguments and code) |
| 12 | fault detection vs zone discrimination; "ab" = B-C | **fixed** |

No new problem in the code changes themselves. The new problems are in documents PR #40 did not
touch (README.md, docs/PLAN.md), plus one provenance stamp.

---

## 1. `fault_sign` in `limit_rows` / `phase_rows`: fixed

- `tac25_design.limit_rows` and `phase_rows` take `fault_sign` (default −1, `ModelSet.pair`).
  `tac25_channels.py:192` passes +1, and its LP at line 185 (`[GN, −GF, …]` against c_F − c_N) does carry
  +u_F.
- **Results identical to pre-#37.** `results/review_wp1/tac25_channels.json` on #40 equals both
  `a8a8bcb` and `7ea52c1~1` in every field except `commit` and `runtime_s`. κ = 16 at I_max 2.1 is back to
  **1.20 pu**.
- **No other caller needs +1.** All 12 call sites of `limit_rows` / `phase_rows` / `limit_block` in `src/`
  were checked:
  - `tac25_negseq.py:94` and `tac25_certificate.py:178` use `[GN, GF]` against c_F − c_N, so −1 is right.
  - `tac25_design` internals go through `ModelSet.pair`.
  - `pscad_tac25_design.limit_block` and `pscad_tac25_sweep` use the normal block only.
  - `pscad_tac25_design.closest` writes its own signed rows.
  - The other `[GN, −GF]` LPs (`aux_model.py:126`, `pscad_witness.py:29`) apply no limit.
- **Gaps (cosmetic).**
  - No test exercises the +1 path, so a revert of `tac25_channels.py:192` would not fail the suite. A
    test like the brute-force one in `test_network.py`, run on `separated_structured`, would pin it.
  - The regenerated JSON's `commit` field is `b3a987f` (main's #39 merge), which does not contain the
    `fault_sign` code that produced it.

## 2. Line-model guard: fixed in code, docs partly

`pscad_network.check_line_model` uses union-find over the spec's (unsplit) lines. It flags a loop when a
line joins two buses already connected, which also catches parallel lines. On a loop, it refuses unless
(z0 − z1)/z1 is equal, as a complex number, on **all** lines. `build()` calls it, and so does
`run_fast`, through `build()` for each topology.

[`check_line_guard.py`](checks/check_line_guard.py) compares the guard's verdict with the actual error of
the conductor model `build()` makes (the round-1 phase-domain model) on 7 networks:

| network | guard | max error (pu) | |
|---|---|---|---|
| radial chain, ratios 3 / 4.5 | radial | 2.2e-7 | agree |
| radial star, 2 SGs, ratios 3 / 4 / 2.5 | radial | 1.6e-7 | agree |
| triangle, uniform 3 | meshed | 1.6e-7 | agree |
| triangle, uniform 3, 2 SGs | meshed | 1.0e-7 | agree |
| triangle, one line 4 | refused | 3.1e-2 | agree |
| parallel pair, ratios 3 / 4 | refused | 1.8e-2 | agree |
| uniform triangle + radial spur at 4.5 | refused | 1.4e-7 | **over-strict** |

The guard is **safe**: it never accepts an inexact network. The condition is right: return-conductor
impedances proportional to z1 with one complex constant give the return network the same current split
as the phase network. The guard is stricter than needed: uniformity is required only within each loop
(each 2-edge-connected component), not on radial spurs. That is cosmetic. Its relative tolerance of 1e-9
will also refuse ratios that differ in the tenth digit.

**Docs not updated (affects a claim).** Three statements still say the builder handles any network:

- `results/MULTIBUS.md:34`: "`src/pscad_network.py` builds **any such network in PSCAD**". It contradicts
  the same file's new "Not yet" bullet.
- `README.md:91`: "`src/pscad_network.py` builds any such network in PSCAD".
- `docs/PLAN.md:66`: "any network built in PSCAD by `src/pscad_network.py`".

## 3, 4, 12. Documents: numbers right, two overstatements left

All numbers PR #40 added were checked against round 1's outputs:

- **MULTIBUS.md, finding 3.** Correct: −29.4° to +10.6°, median 12.2°; 15 / 48 and 17 / 48 outside the
  set; ratio differences up to 0.44 and 0.96.
- **MULTIBUS.md, finding 4.** Correct: at most 0.46 pu; asked 0.26–0.78 pu, delivered 0.264–0.337 pu;
  cut up to 62 %.
- **PSCAD_TAC25.md.** Correct: −10° to +15°, median 6° (measured −10.1° to +14.8°, median 6.3°).
- **PSCAD_DELTA_SWEEP.md.** Correct: −11° to +15°, median 6° (measured −11.1° to +14.8°, median 6.1°).
  Both two-bus figures name I1 too. Only δ was measured, but in the Fortran I1 and δ share the factor
  e^{j∠V1}, and LIM 1 scales I1 by a real number, so they turn together.
- **MULTIBUS.md, finding 12.** Qualification 3 (fault detection, not zone discrimination; "ab" is B-C)
  is accurate.

What remains overstated:

- **`results/MULTIBUS.md:79`**: "**The separation the design promises is what the EMT system
  delivers**". The design promises separation for every realisation in the sets. The EMT tested one run
  per case (started at its worst realisation, and per qualification 1 not at it during the fault) and
  16 + 16 normal corners. "In the 128 runs tested, the EMT system separates every fault with the margin
  and keeps normal operation inside its set" is what the data support. Qualification 1 then contradicts
  the headline's wording.
- **`results/MULTIBUS.md:75`**: row 1 of the table was relabelled "runs started at their worst
  realisation". Row 2 ("48 cases at their worst realisation, design δ") was not, though it carries the
  same 17 / 48 caveat.
- **`README.md:91`** still summarises step 1 as "all 48 are separated with the margin and normal
  operation stays in its set", with neither the curtailment (finding 4) nor the fault-time drift
  (finding 3). The same goes for **`docs/PLAN.md:66-67`** ("the design holds in 128 EMT runs").

Cosmetic: the "Not yet" list in MULTIBUS.md has a blank line that splits it into two lists. Its old bullet
"meshed networks (supported by the solver, not yet built or tested in PSCAD)" now sits beside the new one.

**REVIEW.md rows 49 and 50.** Row 50 accurately records findings 1, 2, 3, 4 and 12, and that 6–11
change no stored number (true: none of them alters a stored result). Row 49 still says "all six affected
scripts re-run". That is right for what happened in #37; row 50 records that one of those re-runs was
itself wrong. Acceptable.

## 5. REVIEW.md claim 3: fixed

The old text is struck through. The replacement numbers match `tac25_limit_presets.json`:

| rule | weak_sg | noisy | all_ibr_hard |
|---|---|---|---|
| phase | 0.52 | 0.32 | 0.40 |
| tac25 | 0.52 | 0.70 | 0.40 |
| injectable limit (phase rule, pu) | 1.747 | 1.820 | 1.567 |

The injectable limits are quoted as 1.75 / 1.82 / 1.57 pu per phase. All correct.

## 6. Sign tests: fixed

[`check_tests_bite.py`](checks/check_tests_bite.py) runs each test as is, then with the fault-block sign
flipped in memory (`network.limit_rows`, and `tac25_design.limit_rows` / `phase_rows` with
`fault_sign=+1`):

| test | correct sign | flipped sign |
|---|---|---|
| `test_network::test_limit_rows_keep_every_physical_pair_and_only_with_the_right_sign` | passes | **fails** |
| `test_network::test_closest_realisations_respect_the_limit` | passes | **fails** |
| `test_network::test_closest_witness_is_a_true_fault_realisation` (relabelled "consistency only") | passes | passes, as its new docstring says |
| `test_tac25::test_limit_rows_follow_the_pair_sign_convention` (now unconditional) | passes | **fails** |

The new mirror-image half of the tac25 test is still behind an `if` (`|i_mirror| < 0.7 cos(π/24)`).
For weak_sg |i_mirror| ≈ 0.66 < 0.694, so it runs. Cosmetic.

## 7. `real_ml.phasor_view`: fixed

The new start is `pre = ev − 2·CYCLE − ((CYCLE − n_post mod CYCLE) mod CYCLE)`. The frame offset
between the two windows is then n_post − 2C + s ≡ r + s ≡ 0 (mod C) for every n_post: checked for
n_post = 0…511. The docstring's "pre congruent to ev + n_post" is also right.

- On the grid used (10–50 ms), the old and new back-shifts are identical (64, 0, 64, 0, 64 samples), so
  no stored number changes.
- The maximum back-shift is still 127 samples, so the pre-fault window is no further back than before.
- [`check_phasor_view.py`](checks/check_phasor_view.py) on #40: **0.0°** at 10, 15, 20, 25, 30, 35, 40 and
  50 ms. On main it was −180° at 15, 25 and 35 ms.

**Gap (cosmetic).** `tests/test_review_real.py:35` parametrises the phasor_view test with
`t_ms ∈ {20, 30, 40, 50}`, where the old code was already right. Reverting the fix would not fail any
test. Adding 15 or 25 ms would pin it.

## 8–10. Guards: fixed, one gap in 10

[`check_guards.py`](checks/check_guards.py):

| case | raises |
|---|---|
| `make_spec`, three-bus as used | no |
| `make_spec`, SG z2 ≠ z1 / inverter neg_z = 0.5 pu / load y2 ≠ y1 | yes ×3 (AssertionError) |
| `solve`, fault at m = 0 / m = 1 | yes ×2 (ValueError) |
| `solve`, fault at m = 0.5 | no |
| `closest` / `noise_to_normal`, limit set empty (\|δ\| = 2) | yes ×2 (RuntimeError) |
| `closest` / `noise_to_normal`, normal calls | no |
| `assert_single_branch`, three-bus as used | no |
| `assert_single_branch`: load / second line / relay at end b | yes ×3 |
| `assert_single_branch`, **second SG at the relay bus** | **no** |
| `assert_single_branch`, **no SG at the relay bus** | **no** |

For **10**, `pscad_network_check.compare` still has its own `len(here_sg) == 1` assert, so it catches
both. But `network_delta_test.analyse` calls only `assert_single_branch`, and then uses
`net.sgs["G"].zs[1]` and `sp["sgs"]["G"]` by name (lines 100-101) without checking that "G" sits at the
relay bus or is alone there. Folding the one-SG-at-the-relay-bus check into `assert_single_branch` would
close it. These are `assert`s, so `python -O` removes them; the same holds for the `make_spec` checks.

## 11. Spec fingerprint: fixed, two residual gaps

- `spec_digest` hashes the whole spec except `name`, as sorted JSON.
- `reusable` requires the `.out` file and a matching `spec.sha256`. `stamp` writes it after a successful
  run, in `run_fast` into the freshly recreated destination and in `run_specs` into the build's own
  output folder.
- On the stored runs, all **128 / 128** three-bus runs are reusable under both Python 3.12 and PSCAD's
  **Python 3.7.8** (the digests agree across versions). A spec with D2ANG changed by 1° is not reusable.
- The 128 stamps were written after the fact, on the strength of the injection check (≤ 0.0039 pu against
  spec). That is reasonable, since an 8–14° angle error on 0.9 pu would have shown ≥ 0.13 pu.

Residual gaps (cosmetic):

1. **`run_specs` never deletes the old output** before rebuilding (`build()` removes only `name.psc*`
   project files; `pscad_inverter.run` deletes nothing). A rerun that PSCAD finishes without error
   messages but without writing output would leave the old `_01.out`. `ok = not errs and
   os.path.exists(out)` would then stamp that stale output as matching the new spec. `run_fast` deletes
   its outputs first and has no such gap.
2. **The fingerprint does not cover** `build()`'s arguments (t_fault, dur, t_end, dt_us) or the code
   (builder, Fortran inverter). Changing either does not invalidate stored runs.

## Not checked

- No PSCAD runs. The guard's behaviour inside a PSCAD build is inferred from calling `check_line_model`
  directly.
- Whether the doc sentences PR #40 rewrote read well in context beyond the claims above.
- The other result documents that cite step 1 (only README.md and docs/PLAN.md were searched).
- PR #40's own verification claims beyond what is listed: I re-derived what each finding needed instead.

---

## Round 3: PR #40 after `6cfff4e`

Checked at `6cfff4e` (`fix-review-findings`) in the same separate worktree. New script:
[`checks/check_round3.py`](checks/check_round3.py). [`checks/check_channels_sign.py`](checks/check_channels_sign.py)
is adapted to pass `fault_sign` through; it now runs on both versions. **Tests: 159 passed, 4 skipped**, as
claimed (with the `data` junction).

| Item | Verdict | Evidence |
|---|---|---|
| 2, docs | **fixed** | MULTIBUS.md:34, README.md:91 and docs/PLAN.md:66 now say "radial or uniform z0/z1". MULTIBUS.md describes the guard as conservative (a spur off a uniform loop is refused though exact), which matches `check_line_guard.py`. None of "builds any such", "any network built in PSCAD" or "design holds in 128" remains. |
| 3, docs | **fixed** | The MULTIBUS.md headline now states what the 128 runs show (separation by the EMT system, started at each worst realisation) and what they do not (the design's fault sets case by case). Table row 2 is relabelled like row 1. README.md:91 and docs/PLAN.md:66-70 carry both qualifications (δ turns up to 29°; normal output ≤ 0.46 pu) and point to row 50. |
| 10 | **fixed** | `assert_single_branch` raises for a second SG and for no SG at the relay bus, and returns the SG's name (`'G'`, or `'X'` after renaming). `analyse()` (network_delta_test.py:92,100-101,109) and `compare()` use the returned name. No `sgs["G"]` is left in either. |
| 11 | **fixed** | `run_specs` deletes `<name>_*.out` and `spec.sha256` before a fresh run, so a silent no-output run can't inherit old output. `spec_digest` now includes `BUILD_ARGS` and `BUILD_VERSION`. `build()`'s defaults equal `BUILD_ARGS`. The 128 stored runs are reusable under the new digest with Python 3.12 **and** PSCAD's 3.7.8. Changing `dt_us` or bumping `BUILD_VERSION` makes all 128 non-reusable. |
| new test, finding 1 | **bites** | `test_channels_lp_uses_its_own_fault_sign` passes. With the channels call forced back to `fault_sign=-1` it fails (1.08 pu instead of 1.20). The adapted `check_channels_sign.py --stored` on #40 gives 1.20 pu as called and 1.08 pu negated. |
| new test, finding 7 | **bites** | `test_phasor_view_keeps_one_frame_at_any_decision_time` passes at all 8 times with the new shift. With the pre-#40 shift it fails at exactly 15, 25 and 35 ms. |
| channels provenance | **fixed** | `tac25_channels.json` now records `3da5e5c`, which contains `fault_sign=+1`. Every value equals the pre-#37 file (only `commit` and `runtime_s` differ). |

What remains is cosmetic, and a matter of discipline rather than a defect:

- `BUILD_VERSION` is bumped by hand and is not tied to the Fortran in `pscad_inverter.py`. Its comment
  ("raise when build() or update() changes what a run produces") should name the inverter controller too.
- The digest records `BUILD_ARGS`, not the arguments `build()` was actually called with. The two runners
  call it with the defaults, so they agree today.
- The new phasor test's grid is 10–40 ms in 5 ms steps plus 50 ms (no 45 ms). The message to me described
  it as "10–50 ms in 5 ms steps". 45 ms (n_post mod 128 = 32) would fail on the old code too, so coverage
  is not affected.

**All twelve round-1 findings are now closed.** The open point from round 2 is still open: the guard of
finding 2 is conservative (a spur off a uniform loop is refused though exact). That is now documented, so
it is a design choice, not a defect.

---

## Round 4: PR #40 at `adaeb1a` (the round-3 cosmetics)

- **Scope:** `git show --stat adaeb1a` touches only `src/pscad_network.py` (the `BUILD_VERSION` comment and the
  `spec_digest` docstring; 5 lines, no code) and `tests/test_synth.py` (45 ms added to the parametrisation).
  `BUILD_VERSION`, `BUILD_ARGS` and the digest payload are unchanged.
- **The three leftovers are fixed.** The comment names `pscad_inverter.py` and says the bump is manual. The
  docstring states that the digest records `BUILD_ARGS`, which both runners pass. The phasor test now runs at
  10–50 ms in 5 ms steps. 45 ms has n_post mod 128 = 32, which turned 180° under the pre-#40 shift, so the
  new point also fails on old code.
- **Tests:** 160 passed, 4 skipped (the one extra is the 45 ms case; the phasor test passes 9 / 9).
- **Stored runs:** 128 / 128 three-bus runs are still `reusable`, under Python 3.12 and PSCAD's 3.7.8.

**Verdict: PR #40 is OK to merge** as far as this review goes. All twelve findings are fixed, and nothing
in its last commit changes behaviour. What this review did not cover (no PSCAD runs; the five #37 re-runs
other than channels) is listed in the round-1 file.
