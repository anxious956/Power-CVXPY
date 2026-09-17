# WP1 review: auxiliary-signal design tool (convex optimization and protection)

Reviewed commit 321e12b. Branch `review-wp1`. Author files in `src/` and `results/*.json|png` are not modified.
Every number below gives the command that reproduces it and the JSON file/key it comes from
(all JSON paths are relative to `results/review_wp1/`). Set `OMP_NUM_THREADS=2`. Runtimes were measured
on a shared, heavily loaded 16-core machine.

Notation: "margin" = inf-norm distance (pu of measurement) from the centre difference to the Minkowski
difference zonotope (both noise boxes included), i.e. `max_{||lam||_1<=1} lam.(cF-cN) - h_Z(lam)`.
"Global minimum" = minimum-norm separating delta over |delta| <= 1.5, bracketed by inner-hull polygons
(lower) and outer polygons (upper), then polished with the normalized alternating scheme and LP-verified
(`wp1_common.bracket_min`).

## Findings table

| ID | Verdict | Sev. | One line | Before -> After |
|---|---|---|---|---|
| H1 | CONFIRMED | Critical | delta (0.514 at -23.2 deg) comes from the two-bus fault-vs-normal problem. On the three-bus IN/OUT problem, nothing with abs(delta) <= 1.5 separates at eps = 0.01 or 0.08, and delta = 0 already separates at eps = 0.001. For detect.py's negatives, the "certified" delta separates nothing. | "certified 0.514" -> no separating delta exists at eps >= 0.01 (witness pairs); at eps 0.001, delta 0 suffices (inner approx.) |
| H2 | CONFIRMED | High | eps = 0.08 box vs 7.2e-4 pu phasor std of the synthetic front end | eps/std 111 (weak_sg) |
| H3 | CONFIRMED | Medium | The three "same system" uncertainty sets differ in i0, ranges, parameters and negatives | table |
| H5 | CONFIRMED | High | With I_max = 1.2 pu, no preset that needs delta > 0 stays feasible | weak_sg needs I_max 1.704 (per-phase, true set) |
| H6 | CONFIRMED | High | The linear angle generator is unsound (Hausdorff 0.085 / 0.30 pu); a sound outer box raises delta | 0.504 -> 0.552 (weak_sg); 0.691 -> 1.042 (noisy); 0.386 -> 1.054 (all_ibr_hard) |
| H13 | PARTIAL (weak_sg only) | Medium | The published delta has no violations on a dense grid. The zero-margin optimum 0.504 leaves 5 of 5000 full-range grid points unseparated | 0 / 5000 at 0.514; 5 / 5000 at 0.504 |
| H14 | CONFIRMED | High | The margin at the reported optima is 0.45-1.25 % of eps; asking for 10 % noise headroom raises delta sharply | weak_sg 0.514 -> 0.666 (rho = 0.1) |
| H15 | CONFIRMED | Medium | The reported deltas are local optima of a non-convex region; the author's scheme cannot start from a non-separating point | weak_sg 0.5141 -> 0.5040; all_ibr_hard 0.4081 -> 0.3863; noisy 0.6969 -> 0.6908; eps12 "infeasible" -> 1.3186 |
| H16 | CONFIRMED (paper issue) | High (for the correctness gate) | The 2023 Fig. 3 is reproduced only with the Appendix's printed, non-standard real form of z | max abs err vs Fig. 3: printed 0.0065, correct 0.129 |
| X1 | CONFIRMED | Medium | The "ab" scenario is a b-c fault; zone_features' L["ab"] reads a healthy loop | ab-loop error 0.031 pu (15 % of line X) -> 0 with the corrected solver |
| X3 | REFUTED (no issue) | - | ibr_neg_z = 1e6 conditioning | cond 33.4, residual 8e-16 |
| X4 | REFUTED (no issue) | - | k0 matches the paper's k | - |
| X2-AUC | UNVERIFIED | - | Engineered-LR AUC with a corrected loop, and zone-detector AUC along a new direction | not run (see Unfinished) |

---

## H1. The delta used in zone_detect.py / detect.py was not designed for those problems

- **Verdict:** CONFIRMED. **Severity:** Critical.
- **Location:**
  - `src/zone_detect.py:163-166` and `src/detect.py:191-195` read `results/aux_signal_toy_weak_sg.json["cvxpy_opt"]`.
  - That value comes from `src/aux_model.py:132-142` (two-bus model, N vs 30 grid faults, preset weak_sg).
  - The figure labels in `src/detect.py:253` and `src/zone_detect.py:230` call it "design tool's certified δ".
- **What the code does:** it sweeps |delta| along the -23.2 deg direction of the two-bus fault-vs-normal design.
- **Why it is wrong:**
  - The zone experiment's classes are in-zone vs out-of-zone faults on a different (three-bus) network, with different uncertainties (H3). The detect.py hard dataset's negatives are unbalanced_load / load_step, not N.
  - So nothing about either experiment is certified by that delta.

### Evidence (a): zone problem

Script: `python src/review/wp1_h1_zone_design.py --rf R --eps E --sources inner`.

Setup:
- IN = ag, ab with m in linspace(0.62, 0.85, 6); OUT = ag2, ab2 with m in linspace(0.02, 0.18, 5), plus N.
- mr in {0, 1/3, 2/3, 1}.
- 17 network pieces: the 16 vertices + centre of fz in [0.5, 1.8], sR, sS in [0.6, 1.5], sg in [0.6, 1.6].
- 816 IN and 697 OUT zonotopes, 568752 pairs.
- `--sources inner`: srcL and iR use boxes *inside* the true sectors, so each unseparated pair is a physical witness. Two different in-zone and out-of-zone conditions, with noise within eps, give an identical measurement. Non-separation claims are therefore sound for the model. Separation claims are only an inner approximation (gridded m, mr and network pieces).

| rF | eps | box candidates at delta = 0 (`delta0.box_candidates`) | LP-unseparated in 4000-pair sample (`delta0.unseparated_in_sample`) -> est. total (`delta0.unseparated_pairs_estimate`) | pairs whose polygon alone covers abs(delta) <= 1.5 (`n_pairs_alone_blocking_disk`, of 60 examined) | top witness (`witnesses[0].pair`), LP distance on 64 points of abs(delta) = 1.5 (`witnesses[0]["lp_max_distance_on_circle_|d|=1.5_64pts"]`) | at author delta, est. (`author_delta.unseparated_pairs_estimate`) | runtime |
|---|---|---|---|---|---|---|---|
| 0.3 | 0.08 | 135491 | 2893 -> 97994 | 34 | ag m = 0.758, Rf = 0.1, piece 12 vs ag2 m = 0.02, Rf = 0.1, **same piece 12**; 0.0 | 98720 | 304 s |
| 0.3 | 0.01 | 55831 | 73 -> 1019 | 1 | ab m = 0.85, Rf = 0.1, piece 11 vs ab2 m = 0.02, Rf = 0.1, piece 12; 0.0 | 1099 | 599 s |
| 1.0 | 0.01 | 41675 | 297 -> 3094 | 2 | ag m = 0.758, Rf = 1.0, piece 10 vs ag2 m = 0.06, Rf = 1.0, piece 11; 0.0 | 2470 | 268 s |
| 0.3 | 0.001 | 44190 | 0 -> 0 | 0 | none. All 44190 box candidates were LP-checked at delta = 0 and all are separated (`design.grid_optimum` = 0) | 0 | 537 s |

- **Is it separable at delta = 0?** No at eps = 0.01 and 0.08. Yes at eps = 0.001, but only for the inner approximation, not as a guarantee.
- **Minimal delta:**
  - At eps >= 0.01: none with |delta| <= 1.5 (`lazy_rounds[-1].free_fraction` = 0.0). A single pair's non-separating polygon covers the disk; for eps = 0.08 the inscribed radius hits the R = 3 cap.
  - At eps = 0.001: delta = 0.
- **Comparison with 0.514 at -23.2 deg:** in no case is 0.514 needed or sufficient.
- Estimated counts are sampled (4000 LPs), so differences such as 1019 vs 1099 are within sampling noise. For scale, 73 / 4000 has a binomial sd of about 8.4.
- A direction scan (`scan`, 1000-pair samples) finds no direction at |delta| in {0.25, 0.514, 1.0} with zero unseparated pairs at eps >= 0.01. The fewest are about 334 at |delta| = 1, 30 deg (rF 0.3, eps 0.01).
- Files: `h1_zone_design_rf{R}_eps{E}_inner.json`.

### Evidence (b): detect.py negatives

Script: `python src/review/wp1_h1_detect_confuser.py` (18 s).

Setup: high-R ag faults (mr in {0.85, 0.925, 1}) vs unbalanced_load (u box 0.7, f in {1.0, ..., 1.4}) and load_step (f in {1.3, ..., 2.0}); weak_sg linear sources, eps 0.08.

- Design grid, 15 fault cases (`design_m_grid_certified_0.514.unseparated_by_negative_set`): unseparated from every unbalanced_load and load_step piece, 15 / 15 each, at the author's delta. From N: 0.
- Dense m 0.10-0.95, 54 cases (`dense_m_0.10_0.95_certified_0.514`): at the author's delta, 54 / 54 unseparated from every unbalanced_load piece and from load_step f >= 1.475; 53 / 54 from load_step f = 1.3; 0 from N.
- At delta = 0 (`dense_m_0.10_0.95_delta0`): 54 / 54 for unbalanced_load, 53 / 54 for every load_step piece and for N.

### Fix and before -> after

- **Fix (implemented as scripts, not wired into src):** `wp1_h1_zone_design.py` builds the design on `zone_model.solve_zone`, with sound outer or inner source boxes, gridded non-affine pieces, interval prefilter + LP, and lazy polygon generation.
- **Recommendation:**
  - Remove the "certified" label from `detect.py` and `zone_detect.py` figures.
  - State that at the noise level of the synthetic front end (eps <= 0.001 would be needed; see H2), delta = 0 already separates the gridded zone sets. At eps >= 0.01 no injection |delta| <= 1.5 can.
- **Before -> after:** "certified 0.514 pu" -> no certificate applies. Zone problem: delta_min = 0 (eps 0.001) or none <= 1.5 (eps 0.01, 0.08).
- **AUC along a new direction: UNVERIFIED (not run).** No separating direction exists at eps >= 0.01. The coordinator asked not to start new sweeps, so `wp1_h1_zone_auc.py` was written but not executed.

## H2. Noise model mismatch

- **Verdict:** CONFIRMED. **Severity:** High.
- **Location:** `src/aux_model.py:31` (eps box per real component), presets at `:166-175`; `src/waveforms.py:127` (`rng.normal(0, p.noise)` per sample), `SigParams.noise = 0.01`.
- **Evidence:** `python src/review/wp1_h2_noise.py` (24 s) -> `h2_noise.json`.
  - One-cycle DFT, 128 samples, sequence component real/imag std:
    - Monte Carlo 7.19e-4 (`noise_only.std_seq_component_mc`)
    - Analytic 7.22e-4 = 0.01·sqrt(2/(3·128)) (`noise_only.std_seq_component_analytic`)
  - Per-phase phasor std: 1.25e-3 (`noise_only.per_phase_analytic`).
  - Full front end (harmonics + DC offset), post-fault window EVENT+CYCLE:
    - Current bias up to 4.17e-3 (`["full_i_post_EVENT+CYCLE"].mean_abs_bias`)
    - Max abs error 6.37e-3 (`.max_abs_err`)
    - Voltage max error 2.6e-3
  - eps / std (`ratio_eps_over_std`): weak_sg and all_ibr 111; weak_sg_noisy and all_ibr_hard 208; easy 41.6.
  - Per-sample sigma that would make eps a 3-sigma phasor bound (`sigma_per_sample_equivalent_to_eps_as_3std`): 0.37 pu for weak_sg.
- **Which model fits instrument transformers:**
  - CT/VT ratio and phase-displacement errors are multiplicative (proportional to the signal): a complex gain error on each phasor.
  - Neither an additive box of constant width nor white sample noise models them.
  - Protection-class CTs (IEC 61869-2 5P/10P) allow a few percent ratio error and tens of minutes of phase error at rated current, larger near the accuracy-limit factor. These class limits are quoted from memory: **UNVERIFIED**.
  - An additive 0.08 pu box is of that order for a 1 pu phasor but is far too large for near-zero quantities (i-, v0, i0 in normal operation), where a multiplicative error is nearly zero.
  - The consistent model is a per-phasor multiplicative zonotope (|1+g| <= 1 + r, arg within phi), which is bilinear in the measurement. It can be handled like the H6 source sectors.
- **Fix:** none applied to src. Scripts quantify the gap.
- **Before -> after:** design eps 0.08 vs front-end error <= 6.4e-3 (bias + noise).

## H3. Uncertainty-set mismatch

- **Verdict:** CONFIRMED. **Severity:** Medium.
- **Evidence:** `python src/review/wp1_h3_sets.py` (~10 s) -> `h3_sets.json`. Ranges were sampled with 200k draws each.

| | design weak_sg (`design_weak_sg`) | waveforms._relay_state (`waveforms_relay_state`) | zone_detect.generate (`zone_generate`) |
|---|---|---|---|
| network | two-bus | two-bus (same solve) | three-bus L-R-S |
| abs(srcL) / angle offset | [0.950, 1.054] / ±0.091 (linear box) | same box | [0.95, 1.05] / ±0.09 (true sector) |
| abs(iR) / angle offset | [0.600, 1.229] / ±0.421 around 0.9 pu | same box | [0.225, 0.720] / ±0.400 around 0.45 pu |
| zs1 | 0.4 fixed | 0.4 fixed | [0.20, 0.72] |
| loads | fixed | ×U[1.3, 2.0] (load_step), motor, ×U[1.0, 1.4] + unbalance | yR, yS ×U[0.6, 1.5] |
| ibr_zero_z | 0.15 | 0.15 | [0.09, 0.24] |
| rF / m / mr | 1.0 / grid 0.15-0.95 / {0, .5, 1} | 1.0 / U[0.10, 0.95] / U[0, 1] (hard: U[0.85, 1]) | --rf 0.3 / in U[0.62, 0.85], out U[0.02, 0.18] / U[0, 1] |
| negatives | N | load_step, motor_start, unbalanced_load, normal | ag2, ab2 |
| noise | box ±0.08 | N(0, 0.01)/sample + harmonics + DC | same as waveforms |

(`design_i0_vs_zone_i0`: 0.9 vs 0.45.)

- **Fix:** none in src. H1 builds the design sets from the zone_detect ranges.

## H5. No inverter current limit

- **Verdict:** CONFIRMED. **Severity:** High.
- **Location:** `src/aux_signal_toy.py:75-80` (QP has no current constraint); `src/aux_model.py:26-28`.
- **Base:** IBR rating 1.0 pu on the system base, nominal i0 = 0.9 pu (90 % loading), I_max = 1.2 pu.
- **Evidence:** `python src/review/wp1_h5_current_limit.py` (752 s) -> `h5_current_limit.json`, key `presets.<preset>`.
  - Max |i+| over the design's linear box (`max_abs_iplus_linear`): 1.230 for gen_i = [0.3, 0.3], 1.500 for gen_i = [0.3, 1.0], 1.084 for easy. Over the true sector (`max_abs_iplus_true`): 1.200 (easy 1.050).
    - With the linear box, every preset except easy violates 1.2 pu already at delta = 0 (`linear_*.feasible_at_delta0` = false).
    - With the true set the boundary is exactly reached, so any delta != 0 violates the "sum" form, and the "phase" and "paper2" forms too (`true_*.optimum` = null) for every preset needing delta > 0.
  - Required I_max at the unconstrained global optimum, per-phase peak, true set (`required_imax_phase_at_unconstrained_true`): weak_sg 1.704, weak_sg_noisy 1.891, all_ibr_hard 1.545, weak_sg_eps12 2.519.
  - Feasible presets: easy (delta = 0, all forms, both sets) and all_ibr (delta = 0, true set only).
- **Fix:** constraint masks added to the global solver (`make_mask`: sum / per-phase / paper 2-norm, worst case over set vertices or a 2000-point arc).
- **Before -> after:** weak_sg delta 0.504 (unconstrained) -> infeasible at I_max = 1.2.

## H6. Linearized angle uncertainty

- **Verdict:** CONFIRMED. **Severity:** High.
- **Location:** `src/aux_model.py:104,107,108` (`1j*gen*s0`).
- **Evidence:** `python src/review/wp1_h6_angle.py` (86 s) -> `h6_angle.json`.
  - Geometry (`geometry[i]`), true sector vs linear box, i0 = 0.9, |i| ± 0.3:

| angle gen | h(true->linear) `h_true_to_linear` | h(linear->true) `h_linear_to_true` | true samples outside box `frac_true_samples_outside_linear` | outer box h(true->outer) / h(outer->true) |
|---|---|---|---|---|
| 0.3 rad | 0.0846 | 0.0806 | 7.8 % | 1.1e-16 / 0.169 |
| 1.0 rad | 0.2758 | 0.3000 | 24.3 % | 1.1e-16 / 0.368 |
| SG ±5 %, 0.087 rad | 0.0042 | 0.0041 | 2.3 % | 0 / 0.0087 |

  - The linear box is not contained in the sector and does not contain it (|1 + jg| > 1; the box is flat where the sector is curved).
  - Outer box (`wp1_common.sector_outer_box`): radial [rmin cos g, rmax], tangential ±rmax sin g. Soundness is tested in `tests/test_wp1.py::test_outer_box_contains_sector_and_inner_box_inside`.
  - Redesign (`design.<preset>.{linear,outer}.global_min[1]`, bracket in `.bracket`):

| preset | linear (global, H15) | outer | unseparated at reported delta with outer sets (`outer.unseparated_at_reported`) |
|---|---|---|---|
| weak_sg | 0.5040 | 0.5517 (bracket 0.5517-0.5591) | 1 |
| weak_sg_noisy | 0.6908 | 1.0418 (1.0418-1.0589) | 11 |
| all_ibr_hard | 0.3863 | 1.0544 (1.0454-1.1537; verified point 1.0544) | 10 |

- **Fix:** `source_sets(p, "outer")` in `wp1_common.py`.
- **Before -> after:** see table. For all_ibr_hard the verified outer design (1.054) is 2.7× the linear one.

## H13. Guarantee only on the (m, mr) grid

- **Verdict:** PARTIAL. **Severity:** Medium.
- **Location:** `src/aux_model.py:32-33,139-142`.
- **Evidence:** `python src/review/wp1_h13_continuous.py weak_sg --nm 100 --nmr 25 --nmc 2000 --rounds 4` (37 s) -> `h13_continuous_weak_sg_100x25.json["weak_sg"]`. **Only weak_sg and only 100 × 25 were run** (the planned 200 × 50 run for three presets was stopped at the coordinator's request).
  - At the reported 0.5141:
    - m in [0.15, 0.95]: 0 / 5000 unseparated (`dense_span_0.15_0.95.unseparated`)
    - m in [0.01, 0.99]: 0 / 5000 (`dense_full_0.01_0.99.unseparated`)
    - Consistent with the coordinator's 0 / 1722.
  - Monte Carlo:
    - Linear-box sources: 0 / 2000 ambiguous fault samples (`mc_linear.ambiguous_fault_samples`)
    - True rotated sources: 0 / 2000 ambiguous (`mc_true.ambiguous_fault_samples`), and 1 / 2000 normal-operation samples fall outside the design's N zonotope (`mc_true.normal_samples_outside_N`). That is a false "not normal" caused by H6.
  - At the zero-margin global optimum 0.5040 (`refinement[0].delta`):
    - 0 / 5000 unseparated on the [0.15, 0.95] grid (`refinement[0].dense_unseparated`)
    - 5 / 5000 on the [0.01, 0.99] grid (`refined_full_range_unseparated`). The (m, mr) of those 5 points were not recorded.
  - The published delta survives only because of its tau margin (H14).
- **Refinement:** the loop (add violating dense points, recompute global minimum, repeat) needed 0 rounds on the span grid. The Lipschitz-bound version was not implemented (UNVERIFIED).
- **Before -> after:** 0.5141 (0 violations) / 0.5040 (5 violations on the full range) -> no refined delta computed for the full range. weak_sg_noisy and all_ibr_hard: UNVERIFIED (not run).

## H14. Zero-margin separation test; tau in unnormalized units

- **Verdict:** CONFIRMED. **Severity:** High.
- **Location:** `src/aux_model.py:123-129` (`return res.status == 2`); `src/aux_signal_toy.py:61-67` (`norm_inf(lam) <= 1`, `tau = 1e-3`), `:78`.
- **Choice:** ||lam||_1 <= 1. It is the dual of the inf-norm used by the noise box, so the margin mu is in pu and separation survives any noise half-width up to eps + mu/2 (`wp1_common.margin_dual`, equal to the primal `dist_inf`; tested in `test_separated_lp_boxes`).
- **Evidence:** `python src/review/wp1_h14_margin.py` (403 s) -> `h14_margin.json`.

| preset | eps | margin at reported delta (`margin_min_pu`) | % of eps (`margin_min_over_eps`) | worst case | global min at margin 0 (`global_min_margin0.best_verified`) | rho = 0.10 (mu = 0.2 eps) | rho = 0.25 | rho = 0.50 |
|---|---|---|---|---|---|---|---|---|
| weak_sg | 0.08 | 1.00e-3 | 1.25 % | ag m .95 mr 1 | 0.5040 | 0.6663 | 0.9097 | 1.3186 |
| weak_sg_noisy | 0.15 | 6.80e-4 | 0.45 % | ab .95 1 | 0.6908 | 0.8985 | 1.2119 | none <= 1.5 |
| all_ibr_hard | 0.15 | 7.64e-4 | 0.51 % | ab .55 1 | 0.3863 | 1.3574 | none | none |
| easy | 0.03 | 0.416 | - | - | 0 | 0 | 0 | 0 |
| all_ibr | 0.08 | 0.143 | - | - | 0 | 0 | 0 | 0 |

- Redesign values are `redesign[k].global_min[1]`. Each is LP-verified to have margin mu (`redesign[k].lp_margin_at_design`: 0.0160 / 0.0400 / 0.0800 for weak_sg) and matches the normalized alternating scheme started from the reported delta (`alternating_from_reported`).
- "rho" means separation survives eps -> (1 + rho) eps.
- **Fix:** `margin_dual` / `dist_inf` plus `alternating(..., lam_mode="normalized", mu=...)`.
- **Before -> after (stated requirement: 10 % noise headroom):** weak_sg 0.514 -> 0.666; weak_sg_noisy 0.697 -> 0.899; all_ibr_hard 0.408 -> 1.357.

## H15. Local optimum of the alternating scheme

- **Verdict:** CONFIRMED. **Severity:** Medium.
- **Location:** `src/aux_signal_toy.py:61-86`.
- **Method:** for each fault, the non-separating set in the delta plane is a convex polygon (preimage of a zonotope under an affine map), computed with 180 support LPs. The separating set is the complement of a union of 30 convex polygons.
- **Evidence:** `python src/review/wp1_h15_global.py` (per preset 40-89 s) -> `h15_global.json`, plots `h15_<preset>.png`.

| preset | reported | global min, margin 0 (`global_min[1]`, bracket `bracket_margin0.lower/upper`) | angle | global min with margin 1e-3 (`global_min_margin_1e-3[1]`) | separating components / non-separating (`separating_components`, `nonseparating_components`) |
|---|---|---|---|---|---|
| weak_sg | 0.5141 | 0.5040 (0.50400-0.51024) | -23.2 | 0.5141 | 1 / 2 |
| weak_sg_eps12 | none (probe ~1.5) | 1.3186 (1.31859-1.34220) | -19.2 | 1.3292 | 1 / 1 |
| weak_sg_noisy | 0.6969 | 0.6908 (0.69080-0.69964) | -129.8 | 0.6977 | 2 / 1 |
| all_ibr_hard | 0.4081 | 0.3863 (0.38629-0.49904) | -62.9 | 0.4146 | 5 / 1 |
| easy, all_ibr | 0 | 0 | - | 0 | 1 / 0, 1 / 3 |

- LP margin at every reported global min is 1.0e-7 (`lp_min_margin_at_global`); the polish targets 1e-7.
- The margin-1e-3 column is the apples-to-apples comparison with the author's tau: equal to the reported value for weak_sg. It is larger for noisy and all_ibr_hard, because the author's actual normalized margin there is below 1e-3 (H14).
- **Random starts** (`starts`: 8 separating + 4 non-separating grid points):
  - Author scheme on weak_sg ends at 0.5141 (2 runs) or at a second local optimum, 0.6272 / 0.6268 (6 runs).
  - weak_sg_noisy: 0.6969 or 0.7898.
  - From every non-separating start the author scheme returns `qp_infeasible_it0` (lam = 0 makes `0 >= tau` infeasible): 4 / 4 on each of the 5 presets that have non-separating grid points (easy has none).
  - The normalized (gauge-direction) variant runs from those starts and reaches 0.5141, 0.6289, or stays at the start point in some cases.
- **LP brute force without polygons:** `python src/review/wp1_h15_bruteforce_lp.py weak_sg` (491 s) -> `h15_bruteforce_lp_weak_sg.json`.
  - 70681 points at step 0.01, abs(delta) <= 1.5.
  - LP-separating 23970; polygon-separating 23597; polygon-separating but LP-not 0 (the outer polygons are conservative, as intended); LP-separating but polygon-not 373.
  - LP components 1 / 2. LP grid minimum 0.5054 at 0.45-0.23j (`lp_grid_min`).
  - Agrees with the coordinator's 0.02-step 0.506 at 0.48-0.16j (abs = 0.5060), which lies between our exact 0.5040 and 0.5141.
- **Fix:** `bracket_min` (global), and `alternating(lam_mode="normalized")`, which works from non-separating starts.
- **Before -> after:** see table.

## H16. Taylor 2023 correctness gate

- **Verdict:** CONFIRMED (the paper's printed formulation is inconsistent). **Severity:** High for the plan's "if we reproduce that curve, the tool is correct".
- **Location:** `papers/Taylor_2023_...pdf`, Appendix, M- as printed; Figs. 2-3.
- **Evidence:** `python src/review/wp1_taylor2023.py` (622 s) -> `h16_taylor2023.json`, `h16_taylor2023.png`. Setup as printed: z- = z+ = 30 + j35, zf = 26 + j·xf, xf = 12:2:58, H = I, Q = I, no A/b, ||lambda_k||_2 <= 1, CVXPY + Clarabel.
  - Exact minimum |theta| (P0 SOCP over 360 directions) equals the closed forms to 1.8e-8 (`summary.max_abs_exact_vs_closed`):
    - printed M = [[r, -x], [r, x]]: sqrt(2)/max(|Δr|, |Δx|)
    - correct M = [[r, -x], [x, r]]: 2/|zf - z-|
    - Both are the same as 2/sigma_max(M- - Mf), which the coordinator verified independently.
  - Peak: printed 0.3536, flat for xf in [31, 39]; correct 0.4851 at xf = 34 / 36 (`summary.peak_printed`, `peak_correct`).
  - Against Fig. 3 values read off the figure (±0.003, `rows[].fig3`):
    - printed: max abs err 0.0065, max rel err 9.6 % (`summary.max_abs_err_printed_exact_vs_fig3`, `max_rel_err_printed_exact_vs_fig3`)
    - correct: max abs err 0.129 (`max_abs_err_correct_exact_vs_fig3`)
  - Fig. 2 replica (`fig2_nonseparating_counts`): printed gives an ellipse (semi-axes 0.354 / 0.141) at xf = 25 and a vertical strip |Re theta| < 0.354 at xf = 35. That is the paper's picture. The correct form gives a disk.
  - CCP on P2 (paper Sec. IV; gamma0 = 1, zeta = 1.5, gamma_max = 1e4, 60 iterations, 2 starts, **parameters not given in the paper**) is within 0.0061 of exact (`summary.max_abs_ccp_vs_exact`), 0 failures.
  - The paper's values sit about 0.004 above the printed-form optimum, consistent with a CCP that has not fully converged (our CCP at xf = 30 gives 0.2876 vs exact 0.2828, paper 0.287).
- **Not specified in the paper:** CCP parameters and starting points (theta0, beta0), stopping rule, xf step (inferred as 2 from Fig. 3's 24 points), and the norm of (7) (Appendix: squared 2-norm of the stacked real vector, assumed). The printed M is not a valid real form of complex multiplication (it is singular at x = 0 and is not a rotation-scaling).
- **Fix:** the review script implements both forms. The WP1 gate should state "reproduces Fig. 3 with the Appendix matrix as printed; with the correct real form the peak is 0.485, not 0.355".
- **Coordinator check:** agrees (plateau 0.356 at xf 32-38 = printed form).

## X1. The "ab" scenario is a b-c fault

- **Verdict:** CONFIRMED. **Severity:** Medium.
- **Location:** `src/aux_model.py:74-75, 86-88`; `src/zone_model.py:73, 113-115`; consequence at `src/zone_detect.py:125` (`zp = L["ab"]`).
- **Evidence:** `python src/review/wp1_extra_checks.py --no-auc` (<1 min) -> `extra_checks.json`.
  - Bolted "ab" at m = 0.3 / 0.7: the loop reading m·X1 is **bc** (error 1.6e-14 / 4.4e-14) in both models (`X1_bolted_loops[].loop_reading_mX1`).
  - Incremental relay currents |Ia, Ib, Ic| = 0.000, 1.732, 1.732 (`X1_incremental_phase_currents_ab`).
  - With the corrected boundary conditions I2 = -a² I1, V1 - a V2 = Rf I1 (`wp1_models_fixed.py`, kind "ab_true"): the ab loop reads m·X1 (error 9e-15) and the currents are 1.732, 1.732, 0 (`X1_incremental_phase_currents_ab_true`).
- **Consequence:**
  - `score_reactance` (phase selection) is unaffected: max error 5.6e-14 (`X2_zone_loops[0].max_err_phase_selected`).
  - The hard-coded `L["ab"]` feature in `zone_features` misreads in-zone bolted faults by up to 0.0307 pu, 15 % of line X (`X2_zone_loops[0].max_err_ab_loop`).
  - The effect on the engineered-LR AUC: **UNVERIFIED** (the AUC part of the script was not run).
- **Fix:** corrected solvers in `src/review/wp1_models_fixed.py`, tested in `tests/test_wp1.py::test_bolted_loop_reads_m_z1_*`. Minimal src patch: either rename the scenario "bc", or use the rotated conditions above; and use `L["bc"]` in `zone_features`.

## X3, X4 and other quick checks

- **X3 (REFUTED):** ibr_neg_z = 1e6 in a dense solve. cond(A) = 33.4, relative residual 8e-16; outputs change by 2.1e-5 at 1e3 and 2.1e-8 at 1e12 (`X3_conditioning`). Same command as X1.
- **X4 (REFUTED):** k0 = (z0 - z1)/(3 z1) applied to 3 I0 equals the paper's k = z0/z - 1 applied to I0 (`X4.equivalent` = true).
- **Sign convention:** relay current = (vL - vF)/(m z), positive toward the fault. Bolted ag reads +m·z1 (`test_bolted_ag_closed_form`, which also checks I_f = 3E/(Z1 + Z2 + Z0) to 1e-8).
- **Zero-sequence path:** only through ibr_zero_z at R (and at L for a local IBR); loads carry no zero sequence. That is consistent with an ag fault drawing I0 at the relay. No further finding.
- **Delta location vs paper:** a single remote IBR injects delta. The paper (all sources IBRs in its example) has every IBR inject. The all_ibr presets' local IBR does not inject. Not quantified.

## Tests

`python -m pytest tests/test_wp1.py -q`: 29 passed (2.5 s). Covered:
- KCL residuals of both solvers (spy on `np.linalg.solve`)
- Bolted AG and BC closed forms
- Sequence <-> phase round trip and DFT phasor recovery
- `separated_lp`, `dist_inf`, `margin_dual`, `gauge_dual` on 4 box cases + a rotated segment case
- Outer / inner sector box soundness
- Unsoundness of the linear angle generator
- Bolted loop impedance per fault type (zone and aux; actual vs corrected "ab")

## What is sound

- The sequence-network solves satisfy KCL to 1e-10 relative and match closed-form bolted AG/BC currents.
- Separation as LP infeasibility of the Minkowski difference is correct. Our independent primal/dual LPs agree with `separated_lp` on every grid case.
- The grid-best and CVXPY deltas the author reports are genuinely separating on the 30-case grid, and remain so on a 100 × 25 continuous grid (H13).
- The ground-loop k0 compensation and the phase-selected reactance element are correct.
- Conditioning is not an issue.

## Unfinished / UNVERIFIED

- **H1 AUC along a new direction:** not run (`wp1_h1_zone_auc.py` exists, untested). No separating direction exists at eps >= 0.01, so the "designed direction" is undefined there.
- **X1 engineered-LR AUC** with the corrected loop: not run.
- **H13** for weak_sg_noisy and all_ibr_hard, and at 200 × 50: not run. Lipschitz refinement: not implemented.
- **H1 outer-source runs** (separation-side claims) were superseded by the inner runs and not saved. The zone design's outer mode is implemented but has no committed result.
- **IEC 61869 class limits** in H2 are quoted from memory.
