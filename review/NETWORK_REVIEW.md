# Independent review of the multi-bus tool (PR #38) and the limit-row sign fix (PR #37)

16 Oct 2026. Reviewed on `main` at `e9a7894`. PR #38 was already merged (09:11 today) when this review
started, so every reference below is to the merged code. Nothing in `src/`, `tests/` or `results/` was
changed. The check scripts are in [`review/checks/`](checks/); each prints the numbers quoted here.

Test suite: `python -m pytest -q tests` gives **148 passed, 4 skipped**, as claimed.

Severity labels: **blocks a claim** (a stated claim is false as written), **affects a number** (a
reported or stored number is wrong), **cosmetic** (wording, robustness or a latent defect with no current
number affected). Two findings carry a qualifier: the claim they concern is true, but a condition it
depends on is not stated.

## Summary

| # | Where | Finding | Severity |
|---|---|---|---|
| 1 | `src/review/tac25_channels.py:185,191` | PR #37 broke this caller: its LP uses +u_F, the rows now assume −u_F | **affects a number** (DESIGN.md:20, `tac25_channels.json`) |
| 2 | `src/pscad_network.py:7-9` | "Exact for any topology" is false: wrong for meshed networks with unequal z0/z1 | **blocks a claim** (no current result affected) |
| 3 | `results/MULTIBUS.md:71-72,86-92`, `PSCAD_DELTA_SWEEP.md:75` | During the fault, δ and I1 turn up to 29° (three-bus) / 15° (two-bus); I1 leaves the design's fault set in 17/48 runs | **blocks a claim** ("worst realisation", "a few degrees") |
| 4 | `results/MULTIBUS.md:76-79` | The 0.90 pu design holds by cutting the inverter's normal output to ≤ 0.46 pu (0.26–0.34 pu delivered); not stated | affects a claim (unstated condition) |
| 5 | `REVIEW.md:442` (claim 3) | Still quotes 0.26 / 0.26 / 0.16 and 0.50 / 0.52 / 0.36 pu, not struck through | **affects a number** |
| 6 | `tests/test_network.py:105-116` | The "sign is right" test passes for either sign | cosmetic (test gap) |
| 7 | `src/real_ml.py:143-147` | Pre-window shift has the wrong sign: 180° error off the 10 ms grid; correct on the grid used | cosmetic (latent) |
| 8 | `src/pscad_network.py:70-72,214` | SG z2, inverter neg_z and load y2 dropped silently; inverters tied to earth, not G_X | cosmetic |
| 9 | `src/network.py:107-108,324-327,359` | m = 0 or 1 divides by zero; `closest` ignores LP status; `noise_to_normal` returns inf on solver failure | cosmetic |
| 10 | `src/network_delta_test.py:98-101`, `src/pscad_network_check.py:5,41-45` | Frame fixed from E1 = V1 + zs1 I1 without asserting the relay line is the source's only branch; "nothing else is fitted" (\|E\| and injections are measured) | cosmetic |
| 11 | `src/pscad_network.py:280,310` | Fast and normal runners reuse any existing output of the same name (stale-output risk) | cosmetic |
| 12 | `results/MULTIBUS.md` (framing) | Faults on the adjacent line L2 are separated from *normal operation*: fault detection, not zone discrimination | doubt about framing, not a defect |

---

## 1. `tac25_channels` was broken by the PR #37 sign change (affects a number)

**Where.** `src/review/tac25_channels.py:185`:
`Aeq = np.hstack([GN, -GF, EN - EF, XN, -XF, np.eye(n), -np.eye(n)])` against
`beq = (cF + …) − (cN + …)`. That is `c_N + G_N u_N = c_F + G_F u_F`, so in **this** LP the fault-block
variable is **+u_F**. Line 191 calls `td.limit_rows`, which since PR #37 negates the fault block for
`ModelSet.pair`'s `[G_N, +G_F]` layout. In `separated_structured` the limit is therefore now applied to
the mirror image of the fault-side realisation. Before #37 this caller was right; after it, it is wrong.

**Evidence.** [`checks/check_channels_sign.py`](checks/check_channels_sign.py) reruns the cell that
changed in #37 (imbalance κ = 16, I_max = 2.1, on the grid `imbalance_boundary` uses):

| fault-block rows | κ = 16, I_max = 2.1 |
|---|---|
| as merged (sign for `ModelSet.pair`) | 1.08 pu at 20° (= stored `tac25_channels.json`) |
| sign matching this LP's +u_F | **1.20 pu** at 210° (= the pre-#37 value) |

(On the finer 0.02 / 72 grid: 1.02 vs 1.18 pu.)

**Consequence.** `results/DESIGN.md:20` says "§4.1.1 (structured error set): one cell moves, 1.20 → 1.08 pu
at I_max 2.1". No cell moves, and the stored `tac25_channels.json` `imbalance_boundary["i_max=2.1"]` κ = 16
entry is wrong. The DESIGN.md §4.1.1 table quotes the no-limit row (1.20), which is unaffected.
`min_delta_structured` with `i_max` (the "hard 1.2" and "robust 2.1" cells) also goes through this path. All
of those cells are 0.0, so they do not change here, but every limited structured result is suspect until the
caller is fixed.

**Fix (for the author).** Either pass −u_F (write `GF` instead of `-GF` and negate the matching
signs), or give `limit_rows` a `fault_sign` argument and call it with +1 here.

**Other callers, verified correct.** `tac25_certificate.py:177-182` and `tac25_negseq.py:88-94` build
`[G_N, G_F]` against `c_F − c_N`, the same convention as `ModelSet.pair`, so the new sign is right for them.
`pscad_tac25_design.closest` writes its own rows with the sign (line 49) and undoes it on return (line 56).
`pscad_tac25_sweep` limits only the normal block (`limit_block` keeps `A[0::2, :k]`), so no fault sign is
involved. `tac25_limit_presets`, `tac25_map` and `tac25_softlimit` go through `td.min_delta`, and
`separated_at` / `validate_continuous` use `ModelSet.pair`. `pscad_witness.py` writes `[GN, −GF]` with
+u_F and applies no limit (correct). `src/review/ibr_study.py` has its own limiter and no separation LP, so
it is unaffected.

## 2. The PSCAD line model is not exact for meshed networks (blocks a claim)

**Claim.** `src/pscad_network.py:6-9` says the line model (uncoupled R-L z1 per phase plus a return
conductor (z0 − z1)/3 between per-bus return nodes) is "Exact for any topology as long as every grounded
element is tied to the return node of its own bus".

**What is wrong.** On a loop of lines, the phase-sum current S_l and the return current R_l of each line
obey separate loop laws: Σ z1_l S_l = 0 in the phase conductors and Σ (z0_l − z1_l)/3 · R_l = 0 in the
return conductors. KCL alone makes S + R a circulation, not zero. R_l = −S_l on every line (which is what
"zero-sequence impedance z0" requires) holds only if the network is radial, or if (z0 − z1)/z1 is the same
on every line of each loop.

**Evidence.** [`checks/check_network.py`](checks/check_network.py) builds an independent phase-domain nodal
model of exactly what `build()` creates (per-bus return nodes, earth at the first SG's G node, inverters
phase-to-earth, wye loads with a 1e6 pu neutral) and compares the relay's six sequence quantities with
`network.solve` (30 random operating points and faults each):

| network | max error |
|---|---|
| radial three-bus (the one built) | 1.9e-7 pu |
| radial, z0/z1 = 3 on L1, 4.5 on L2 | 1.5e-7 pu |
| meshed (L–R–S plus L3 = L–S), z0/z1 = 3 everywhere | 1.2e-7 pu |
| meshed, z0/z1 = 4 on L3 | **1.9e-2 pu** |

**Consequence.** Every PSCAD result so far is on the radial three-bus or the two-bus circuit, so none is
affected. MULTIBUS.md:98-99 correctly lists meshed networks as "not yet built or tested in PSCAD". But the
builder would build such a network without complaint and give a wrong zero-sequence response. Assert
radiality or uniform z0/z1 per loop, or use mutually coupled phase conductors.

## 3. The EMT fault runs are not at the design's realisation once the fault starts (blocks a claim)

**What.** `pscad_network.inverter_settings` sets ID / IQ / D2ANG relative to the inverter's own V1 in the
**pre-fault** solution. The inverter keeps those angles to the V1 it measures, so when the fault moves V1, I1
and δ turn with it. The design's fault set assumes the same absolute I1 set and the same δ as before the
fault.

**Evidence.** [`checks/check_emt.py`](checks/check_emt.py) reads all 128 stored three-bus runs. At 0.38 s
(4.8 cycles into the fault), against the spec:

- δ turned **−29.4° to +10.6°, median |12.2°|**, in the 48 design-δ fault runs. The largest are bolted
  phase-phase faults (`tb_L1ab95r000_dm` −29.4°, `tb_L2ab05r000_dm` −28.2°). I1 turned by the same angle,
  and |δ| is unchanged (ratio 1.000–1.001).
- The fault-time I1 lies **outside the design's outer inverter set** in 15 / 48 runs with δ = 0 and
  **17 / 48** with the design δ (largest box coordinate 1.16; at the spec'd realisation it was ≤ 1.00).

[`checks/check_emt_twobus_turn.py`](checks/check_emt_twobus_turn.py) does the same for the two-bus runs:
δ turned −11° to +15° (median 6°) in `delta_design` and −10° to +15° (median 6°) in `tac25_design`.

**Which claims.** MULTIBUS.md:71-72 "48 cases at their worst realisation … EMT and design disagree on
none". The runs *start* at the worst realisation; during the fault they sit at a different realisation, for a
third of them outside the modelled set. The EMT-vs-design ratio differs by up to 0.44 (δ = 0) and 0.96
(design δ). MULTIBUS.md:86-92 reports a 6° drift *within* the fault for one case, not the up-to-29° step at
inception. PSCAD_DELTA_SWEEP.md:75 says "the rotation was a few degrees here"; it was up to 15°.

**What still holds.** The EMT separation outcome itself (48 / 48 above 2.2 with the design δ) is a real
measurement and reproduces from `three_bus_sweep.json`. It is a test of the EMT system, not of the design's
fault set. A design that wants to be validated case by case has to model I1 and δ in the inverter's V1 frame
*during* the fault, which the existing condition 2 of PSCAD_TAC25.md implies but does not quantify.

## 4. The three-bus design curtails the inverter in normal operation (unstated condition)

With δ = 0.90 pu and a 1.2 pu per-phase limit, the largest positive-sequence current that fits beside δ is
**0.46 pu** ([`checks/check_three_bus_design.py`](checks/check_three_bus_design.py)). The modelled inverter
range is 0.45 ± 0.3 pu. In the stored LIM 1 normal runs the inverter was asked for 0.26–0.78 pu at the 16
corners and **delivered 0.264–0.337 pu**, cut at 8 corners by up to 62 % (from `three_bus_design.json`
"asked" and the sweep rows). δ is injected continuously (normal set N(δ)), so this is a standing curtailment
of the inverter's active / reactive output. It is also the mechanism that shrinks the uncertainty set and
makes separation possible. MULTIBUS.md:76 ("The design holds in EMT…") should say so. The two-bus TAC25
design (0.38 pu) has the same effect at 8 corners (PSCAD_TAC25.md "limiter active at 8"), but much smaller.

## 5. REVIEW.md claim 3 still quotes the withdrawn numbers (affects a number)

`REVIEW.md:442`, in the "Caveat … resolved by B5" text, still reads "the minima stay **0.26 / 0.26 / 0.16 pu**
… all holding on 462 continuous points" and "TAC25 as written (‖i⁺‖ ≤ 1.2) gives **0.50 / 0.52 / 0.36**",
neither struck through. Row 49 says the first does not hold. The current `tac25_limit_presets.json` has
phase rule **0.52 / 0.32 / 0.40** and tac25 rule **0.52 / 0.70 / 0.40** (weak_sg / noisy / all_ibr_hard).
The "1.38–1.76 pu per phase" injectability figure in the same sentence was not re-checked.

## 6. `test_closest_witness_is_a_true_fault_realisation` does not test the sign (test gap)

`tests/test_network.py:105-116` checks that `noise_to_normal(solve(realisation(uF)))` equals the LP's
noise `t`. Given u_F, `closest`'s u_N is the minimiser of the same problem whatever rows constrain the fault
block, so the equality holds for either fault-block sign. The docstring's "so the sign is right" (also
MULTIBUS.md:29) is not what it tests. Two sign-sensitive checks, both in `check_network.py`, would catch it:

- **Brute-force soundness of `limit_rows`.** Over 7051 sampled (u_N, u_F) pairs whose true phase currents
  all fit under 1.2 pu, at δ = 0, 0.6∠69° and 0.9∠210°, **0** violate a row with w = [u_N, −u_F]. Reading
  block 1 as +u_F would cut **789** of them. No pair with a phase current above the 24-gon bound
  (1.2103 pu) is kept.
- **The realisations `closest` returns respect the limit.** Their largest phase current is 1.2047 pu, within
  the 24-gon bound, for three cases at 0.62 and 0.90 pu.

The tac25 regression test (`tests/test_tac25.py:208-230`) is sign-sensitive, but it skips its assertion
when `|i_big| ≤ 0.75` (`if abs(i_big) > 0.75`). For weak_sg, |i_big| = 1.23, so the assertion does run; an
unconditional assertion would still be safer.

## 7. `real_ml.phasor_view`: wrong shift direction, harmless on the grid used (latent)

`src/real_ml.py:143-147` moves the pre-fault cycle back by `n_post % CYCLE` "so the two source cycles are a
whole number of cycles apart". With the absolute-index basis in the rebuilt array, the two phasors differ
in frame by 2·(n_post mod 128) samples. They agree only when n_post mod 128 ∈ {0, 64}. The shift should be
forward by `n_post % CYCLE` (or back by `CYCLE − n_post % CYCLE`). The comment also still describes the
pre-16-Oct window-relative basis. [`checks/check_phasor_view.py`](checks/check_phasor_view.py), on a pure
constant 50 Hz signal:

| t (ms) | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 50 |
|---|---|---|---|---|---|---|---|---|
| post/pre turn | 0° | **−180°** | 0° | **−180°** | 0° | **−180°** | 0° | 0° |

`DECISIONS_MS = [10, 20, 30, 40, 50]` and `adaptgrid_run.T = 20` all fall on correct points, so **no
current number is affected**. Any finer decision grid would silently invert the incremental currents.

**Other `sequence_phasors` callers, verified.** `pscad_network_check.seq` resamples 20 kHz to exactly
7680 Hz (48/125) and indexes from t = 0, so pre and fault windows share the e^{−jωt} frame; the rotation
fitted at 0.25 s is valid at 0.38 s. `pscad_twobus_check`, `pscad_inverter_check` and `pscad_check` index
one resampled array. `zone_detect._phasors`, `detect.py`, `h4_incremental`, `check_repro`,
`test_review_real` and `h19_ceiling_check` index one array. `selector_compare` uses arbitrary offsets
(e + CYCLE//2) in one array, which is now correct. `review/common.seq_phasors` uses its own
absolute-index basis. `real_zone.py:169` uses magnitudes only.

## 8–12. Smaller points

- **8, `src/pscad_network.py:70-72`.** `make_spec` writes only zs[1] and zs[0] of an SG, nothing of the
  inverter's `neg_z`, and only y[1] of a load. PSCAD then uses z2 = z1, no negative-sequence shunt and
  y2 = y1, with no assert (unlike `zero_z` and `y0`, `build():106-109`). This is true for every network so
  far, but silent if not. Also, the docstring (line 8) says every grounded element is tied to its bus's
  return node, but the inverter sources go phase-to-**earth** (line 214) and loads go 1e6 Ω to earth. This
  is harmless because the Fortran phase references sum to zero exactly (I1, I2 only) and 1e6 Ω carries
  nothing; the phase-domain check above models it that way.
- **9, `src/network.py`.** A fault at m = 0 or 1 makes a zero-impedance segment (lines 107-108, division by
  zero; the PSCAD side floors at 1e-6 Ω). `closest` does not check `res.status` (lines 324-327) and crashes
  on `None` if the LP fails. `noise_to_normal` returns `inf` on a solver failure (line 359), which a caller
  reads as a certain fault. Prefer raising.
- **10, frame and "fitted".** `network_delta_test.analyse:98-101` fixes the frame from E1 = V1 + zs1 I1 at
  the relay. That is right only when the relay line is the relay-bus source's only branch (true here).
  `pscad_network_check.compare` asserts one SG at the relay bus, but not that, and `analyse` asserts
  neither. Both re-solve with the *measured* |E1| and the *measured* injections, so "|EMT − design|" cannot
  see a source or inverter set wrongly, and "Nothing else is fitted" (`pscad_network_check.py:5`)
  overstates. I checked those separately (section "Verified" below): they were set right.
- **11, `src/pscad_network.py:280,310`.** Both runners skip a spec whose output exists. Changing a spec
  without renaming or deleting reuses stale output, which is exactly what happened in PSCAD_TAC25's first pass
  with the unlimited angle settings. The stored 128 three-bus runs are consistent with the current specs:
  pre-fault injections match to ≤ 0.004 pu, where an 8–14° angle error on 0.9 pu would show ≥ 0.13 pu.
- **12, framing.** The three-bus design treats A-G faults on the *adjacent* line L2 as faults to be
  separated from normal operation. That is the fault-detection problem. A zone-1 relay must *not* trip for
  them (zone_model.py's own docstring). "The adjacent line makes the problem harder" is true for detection;
  the in-zone / out-of-zone question is untouched. Not a code defect.

Also cosmetic: the scenario named "ab" is a **B-C** fault (symmetric about A), consistent in `network.solve`
(I1 = −I2, V1 − V2 = Rf I1) and in the PSCAD build (B and C to a star point, r/2 each). The name misleads.

---

## Verified as correct

**`src/network.py`**

- *Sign conventions.* With nodal KCL `Y v + fc·I_f = injections`, fault current leaves F, and the relay
  current is from the relay bus into its line (or into the relay-side segment when the fault is on that
  line). [`check_network.py`](checks/check_network.py): textbook radial A-G (I = E/(Z1+Z2+Z0+3Rf)) and
  B-C (I1 = −I2 = E/(Z1+Z2+Rf)) to 3e-7 pu. The residual is the 1e6 pu inverter shunts.
- *Independent phase-domain model with coupled lines* (Zs = (z0+2z1)/3, Zm = (z0−z1)/3), radial and meshed
  with unequal z0/z1: matches `network.solve` to 2e-9 pu. Relay at end "b": matches, and equals minus the
  end-a current when the fault is elsewhere (1.7e-9).
- *Zero sequence.* SGs grounded through zs[0], inverter `zero_z`, loads y[0], lines z0: covered by the
  above.
- *Reproduction.* `aux_model.solve`, `zone_model.solve_zone` and `wp1_common.affine_case` (both modes)
  match: tests pass. I read `zone_model` and `aux_model` and agree the KCL rows are the same equations.
- *`affine_case`* is exact (solve is affine in every source and δ), including on a meshed two-inverter
  network: residual 3e-15. *Minkowski aggregation* is generator stacking; the column order matches
  `generator_columns` (2 per source, `net.sources` order).
- *`limit_rows`*: right sign and sound (section 6). Phase currents are |i⁺ + aᵏδ|, k = 0, 1, 2, which is
  the set {|i_a|, |a i_b|, |a² i_c|}. *`_limit_feasible`* uses block 0 only, which is enough because the
  two blocks are the same set up to sign.
- *`closest`* returns u_F = −w_F; its realisations respect the limit. *`noise_to_normal`* limits only the
  normal block. That is right: the measurement is a point, and only the normal set is pruned at δ. "Ratio >
  2 ⇔ separated" is right for a clean measurement (the ε-box around it misses N ⊕ ε iff dist_∞ > 2ε).
- *`min_delta`* equals `tac25_design.min_delta` with `limit_rule="phase"`, also in the outer mode actually
  used ([`check_design_engines.py`](checks/check_design_engines.py)). Two-bus PSCAD design: both engines
  give **0.24 pu at 320°** (ρ = 0) and **0.38 pu at 325°** (ρ = 0.1). The pre-#37 sign gives 0.10 / 0.18 pu,
  the "before" figures in PSCAD_TAC25.md.
- *Three-bus design* re-derived: **8 / 48** unseparated at δ = 0, **0.62 pu at 230°**, **0.90 pu at 210°**
  (ρ = 0.1), as MULTIBUS.md.
- *`limiter`* equals a literal transcription of the Fortran LIM block (`pscad_inverter.py:133-179`): the
  k = 1, 2 rotations (a^{−k} on I1, a^k on I2), the root (−b + √(b² − a·c))/a, the `c < 0` and `a > 1e-12`
  guards, the floor at 0 and the final peak rescale. Max difference 7.8e-9 pu over 40 000 random draws, LIM 0
  and LIM 1. The Fortran phase references are T·[0, I1, I2] (5e-9), and no phase exceeds 1.2 after
  limiting.

**PR #37 reasoning (`tac25_design.limit_rows`, `phase_rows`).** Re-derived: the LP solves
G_N w_N + G_F w_F + n = c_F − c_N, and the sets meet at c_N + G_N u_N = c_F + G_F u_F, so w_F = −u_F and
the fault-side realisation is c − g·w_F. The rows' −1 on block 1 is right for every rule ("phase",
"phase_disc", "sum", "tac25"), because all four constrain a set that is not symmetric about c. The
remaining caller problem is finding 1.

**`src/pscad_network.py`**

- *Bases.* Zbase = 20²/10 = 40 Ω. Vbase = 20/√3·√2 = 16.33 kV phase peak. Ibase = 10/(√3·20)·√2 =
  0.408 kA peak (the DFT gives peak phasors). L = X/ω. Fault RON = Rf·Zbase. B-C as two r/2 halves (r between
  phases, star point 1e8 Ω to G_F). Loads are 1/y1 per phase in wye, inductive asserted.
- *Source convention and ammeter orientation* (from the stored EMT outputs, `check_emt.py`). |E1| measured
  / |E| spec = **1.00008–1.00010** over all 128 runs, so `Es` as L-L RMS is right. A reversed relay ammeter
  would make E1 = V1 − zs1·I1 and break this ratio. Pre-fault inverter injections match the spec to ≤ 0.0039 pu
  (I1 ≤ 0.0029 pu), LIM 0 and LIM 1.
- *Relay voltage* is v_phase − v_G of the relay bus: modelled as such in the conductor check, and exactly
  what the sequence model's node voltage is.
- *`update()`* changes the faulted line's two segments (A, B, C and the return conductor, by m), RON (r or
  r/2), the SG's Es and Ph, and every inverter constant `build()` takes from the spec (ID, IQ, MODE2, D2MAG,
  D2ANG, LIM, IMAX). Everything else `build()` sets is fixed per topology key (fault line and type). The
  stored `fchk_L1ag` and `fchk_L2ag` (fast project built from another spec, then updated) are
  **bit-identical** (max difference 0) to the fresh builds `nb_L1ag` and `nb_L2ag`.
- *EMT vs design at the check cases* recomputed with `pscad_network_check.compare`: nb_N 1e-5; nb_L1ag
  1e-5 / **0.0112**; nb_L2ag 1e-5 / 1e-5; nb_L2ab 0 / 8e-5 pu, as MULTIBUS.md.

**EMT test logic (`src/network_delta_test.py`).** `spec_with_limiter` computes V1, and so D2ANG, from the
delivered state (i_del, and δ for LIM 1 or d_del for LIM 0). It scales ID / IQ by |i_req| / |i_del| (and
D2MAG back to |δ| for LIM 0), so the controller asks for the request and its own limiter produces the
delivered state. That is consistent with `limiter` for both types, because relative angles are
frame-invariant. Ratios are taken against N(design δ) with the limit at the design δ, the relay's model.

**Every table in the three result documents reproduces from the JSON:**

- *MULTIBUS.md:* 8 / 48 at δ = 0, no mismatch with the design; 48 / 48 above 2.2 with the design δ
  (smallest 2.232, design 2.229); LIM 1 0 / 16 (max 0.037); LIM 0 8 / 16 (2.22–2.46);
  max |EMT − design| 0.032 pu.
- *PSCAD_TAC25.md:* 3 / 30; 30 / 30 (2.260, design 2.200); 32 / 32 corners (2.26, 16 limited); LIM 1 0 / 16
  (0.032, 8 limited); LIM 0 8 / 16 (0.824).
- *PSCAD_DELTA_SWEEP.md:* 2 / 30; 30 / 30 (2.282); 32 / 32 (2.282); normal 8 / 16 at both δ (0.276 and
  0.784), exactly the limited corners; false-alarm noise 0.72 ε and 0.22 ε.

## What I did NOT check

- No PSCAD runs. PSCAD component semantics (source3 `Type` / `Imp` / `ZSeq` fields, pin orientation of
  meters and sources, `find_first` / `find_all` matching) were checked only through their effect on the
  stored outputs. The source's zero-sequence impedance in PSCAD is supported only indirectly, by the small
  EMT-vs-design error on the A-G runs.
- The two-bus builders (`pscad_twobus*.py`), the inverter's Fortran DFT, ramp and output stage beyond the
  limiter block, and the inverter's dynamics. Fast-mode identity is checked on 2 cases only.
- Five of the six scripts PR #37 re-ran (`tac25_limit_presets`, `tac25_softlimit`, `tac25_map`,
  `tac25_certificate`, `tac25_negseq`) were not re-run. Their callers' sign conventions were read, and they
  are right (section 1). Also not checked: `tac25_tables.py`, or DESIGN.md §2.1, §3.1, §4.4 numbers
  beyond the two-bus PSCAD design.
- `real_ml` / `adaptgrid` results were not re-run; finding 7 is shown on a synthetic signal.
- Whether the 0.05 "inside" threshold for normal runs (ratios 0.03–0.04 come from about 0.003 pu
  model / EMT differences) is a principled choice.
- In line with the standing caveat: every verdict here is about the static model or the stored EMT runs
  as they were set up. Nothing was tested beyond them.

## Reproduce

```
python -m pytest -q tests
python review/checks/check_network.py              # 12 / 13 pass; the failure is finding 2, expected
python review/checks/check_channels_sign.py --stored
python review/checks/check_design_engines.py
python review/checks/check_three_bus_design.py
python review/checks/check_emt.py                  # needs D:\JOSHUA_TAYLOR_data\data\pscad_work\network
python review/checks/check_emt_twobus_turn.py      # needs ...\pscad_work\inverter
python review/checks/check_phasor_view.py
```
