# Review of the IEEE 14-bus pre-registration and Q1 result (branch `ieee14`, docs/IEEE14.md at `35f8d22`; Q1 at `cc1d6f6`)

Reviewer: the independent review session. Read against the PDF in `papers/Taylor_2025_Geometry_of_Distance_Protection.pdf`
(arXiv 2510.04379**v2**, 10 Oct 2025; §II, §IV-C, §V, §VI, Appendices A–C) and the code on the branch
(`src/ieee14.py`, `tests/test_ieee14.py`, 3 tests passing on a scratch checkout). Nothing from Q1 has run.

## Verdict

**Cleared to run Q1 once §3's targets are amended as in §2 below.** The four points research asked about are
confirmed (§1); the amendments are about what Fig. 5 actually shows, and they change the pass/fail rule, so they
go into the doc before the grid runs, not after. The code's separation LP is a faithful transcription of the
paper's (18a), (18b), (19) system and of the sound variant.

## 1. The four points

**(1) Network choices.** Agree with the amended primary (3 Nov): phase-decoupled branches, z0 = z1 in the
network, k = 2 only in the ground-fault loop Ω_z^{ag}. The paper's Appendix A writes i_L = (v_L − v_F)/(m̂_z z)
and i_R = (v_R − v_F)/((1 − m̂_z) z) with the scalar z, and §V-C writes normal operation as v_L = z i_L + v_R;
both are exact only without phase coupling, so a decoupled network is the reading under which the paper's own
formulas are consistent. Two things to record in the doc:
- *Loads are admittances.* "All loads have admittance 0.1 + j0.01" (§IV-C); Appendix A uses i_J = −Y_J v_J. The
  code adds y·I₃ to the diagonal (correct); the doc says "Loads 0.1 + j0.01", which could be read as an impedance.
- *The LL fault at F.* Appendix A says v_F^a − v_F^b = m̂_r r_F (i_F^a − i_F^b). Taken literally (i_F^a = −i_F^b),
  that is a phase-to-phase resistor of 2 m̂_r r_F. Fig. 2 and (3b), and the Ω_r^{ab} = (r_F/2)(e^a − e^b)(Γ + Θ) that
  the doc registers, are the resistor m̂_r r_F. The code uses the Fig. 2 one (`fault_admittance`, [[1, −1], [−1, 1]]/r),
  which is the only reading consistent with Ω_r^{ab}. State the choice; the other reading is a variant only if Q1 fails.
- *V5 (z0 = 3 z1) needs one more change than the doc says.* With coupled lines the N model is
  v_L^a = z (i_L^a + k i_L^0) + v_R^a, i.e. Ω^N = Z_abc Γ^N + Ψ^N (or simply Φ^N). `models()` builds Ω^N with the
  scalar z for every `--z0`, so under `--z0 3` the N model would contradict the network it was solved on. Fix before
  V5 runs (the fault-loop models Ω_z^{ag}, Ω_z^{ab} are already consistent with k = 2 and no zero-sequence).
- Baeckeland's thesis: I could not find it either. The KU Leuven research portal lists the project ("Design and
  Modeling of Inverter Control for Fault Behavior and Power System Protection Analysis", EMT in Simulink of an
  all-inverter 14-bus network); Lirias shows no record. The standard-branch primary stands.

**(2) Noise direction.** Confirmed. With the paper's A = [[1, 1, 1], [1, α², α], [1, α, α²]] and v = A [v⁰, v⁺, v⁻],
the third column is [1, α, α²]ᵀ, so λ_k [1, α, α²]ᵀ is negative-sequence noise. Coding it literally is right. Worth
one sentence in the doc: the noise then lands in the same slot as the signal, i_k = A [0, i_k⁺, Δ_k + λ_k], so each
IBR's negative-sequence injection is uncertain within a radius-1 20-gon around its command (Σ = I; the 20-gon's
inradius is 1, circumradius 1/cos 9° = 1.013). That is why the printed minima for N against all faults sit at
|δ| > 1 and the pair minima at |δ| = 0.2: the signal has to clear the noise polygon, not the grid.

**(3) The literal W^{Rel,3} intersection.** Confirmed, and it can be said more strongly than "not obviously a
relaxation":
- (18b) uses one λ^η in both u_z = m_z u⁰ + Σλ^η and u_r = m_r u⁰ + Σλ^η, (18a) uses the same λ^η in i_L, and (19)
  adds u_z = m_z u⁰ + Σλ_{mz}, u_r = m_r u⁰ + Σλ_{mr}. Σ = I₇ ⊗ b is 21 × 7 with full column rank, so the equalities
  force λ_{mz} = λ_{mr} = λ^η (the doc says "Σ invertible"; "injective" is the right word). The dual in C-A confirms
  this is what was coded: one multiplier φ^η for Pλ^η ≤ 1 collects γ_z, γ_r and Γ^η†α.
- A point of W has u_z = m_z u⁰ + Σ(m_z λ), u_r = m_r u⁰ + Σ(m_r λ), i_L = Γ(u⁰ + Σλ). To lie in the literal set it
  needs λ^η = λ (from i_L) and Σλ^η = m_z Σλ = m_r Σλ, i.e. λ = 0 or m_z = m_r = 1. So the literal set is neither a
  relaxation nor a restriction of W; Lemma 7's certificate does not apply to it. Its emptiness is "what the paper
  computed", which is the right thing to reproduce; any *claim* of separation rests on V3.
- Lemma 4 (W ⊆ W^{Rel,1}) holds with separate λ_z, λ_r for u_z and u_r (the product reading of W^{Rel,1}); that is
  V3. V3's ties are valid: λ_z = m_z λ gives P(λ − λ_z) = (1 − m_z) Pλ ≤ (1 − m_z) 1, and they keep the sound set
  linear. The code's `variant="sound"` block is exactly that.

**(4) Thresholds and variants.** The list V1–V5 is fine as a list; the thresholds need the amendments in §2,
because the figure does not say what the doc's §3 assumes.

## 2. Fig. 5, digitised: what the targets actually are

`review/checks/p_i14_fig5.py` reads both panels of Fig. 5 from the PDF at 600 dpi, classifies every marker
(disc / triangle / plus by bounding-box fill, convex-hull solidity and top-heaviness; the three classes separate
with margin, ranges in `p_i14_fig5_map.json`) and places it on the lattice. Output `p_i14_fig5.out`, maps in
`p_i14_fig5_map.json`. Findings:

| | doc §3 (35f8d22) | Fig. 5 |
|---|---|---|
| grid | 0.1 step over [−2, 2]² (41 × 41) | **0.2 step, 21 × 21** (rows at 2.0, 1.8, …; 401 and 282 markers) |
| (a) all three pairs | δ = j0.2, ‖Δ‖ 0.53 | **δ = j0.2, unique** minimiser at \|δ\| = 0.2 (0.529) ✓ |
| (b) N vs all LG | ‖Δ‖ ≈ 3.02 ± 0.05 | **\|δ\| = 1.2166 at −1.2 + j0.2, ‖Δ‖ = 3.22**; LL: 1.2 − j0.2, also 3.22 |
| (c) N vs all six | δ = 1.6 + j0.6, ‖Δ‖ 4.52 | **two minimisers, 1.6 + j0.6 and −1.6 − j0.6**, both 4.521 |

So:
- **Grid step 0.2.** A 0.1 grid is finer than the paper's and can find a smaller "smallest on the grid" than the
  paper did without anything being wrong. The reproduction runs on the 0.2 grid; a 0.1 grid may be added as
  information.
- **Target (b) is 3.22 by the figure.** 3.02 corresponds to |δ| = 1.141, which is not a 0.2-grid magnitude (nearest
  2.99 at 0.8 + j0.8 and 3.09 at 1.0 + j0.6, neither marked); it is |1.1 + j0.3| on a 0.1 grid, but the figure's
  grid is 0.2. Treat 3.02 as inconsistent with Fig. 5 (a likely typo for 3.22) *[withdrawn 3 Nov 2026, after Q1:
  3.02 is not a typo but the 0.1-grid value; with V4's angles the 0.1-grid minimum is 0.7 + j0.9, |δ| = 1.1402,
  ‖Δ‖ = 3.017; see §6 below]* and register: reproduced if the LG
  and LL minima are at |δ| = 1.2166 with argmin −1.2 + j0.2 (LG) and 1.2 − j0.2 (LL); report whether anything at
  |δ| = 1.141 or 1.131 separates, so the 3.02 question is answered either way. **With the current ±0.05 band around
  3.02, a correct reproduction would be scored "not reproduced".**
- **Target (c) is a set.** Rule: the minimum magnitude matches and the printed point is among the minimisers. The
  code's `smallest()` returns one point by a tie-break (smallest real part first), so on a correct map it would
  return −1.6 − j0.6 and the literal rule "δ = 1.6 + j0.6" would fail. Store the full minimiser set.
- **The LL half of (b)** ("and similarly for N and all LL faults") is in the code (`b_N_all_LL`) but not in the doc.
- **Use the whole map.** Two 21 × 21 marker maps are a far stronger target than three numbers. Register a map
  comparison: per panel, the fraction of the 441 cells whose class (N-ag only / N-ab only / all three / none;
  LG / LL / all six / none) matches the digitised figure, with the mismatching cells listed. Suggested rule:
  "reproduced" needs ≥ 95 % per panel on top of (a)–(c); below that, "approximately" if (a)–(c) hold. The digitised
  figure is point-symmetric with LG ↔ LL swapped under δ → −δ (right panel); the computed map should show the same.
- **Which pairs "N and all LG faults" means** is unstated: the three pairs (N, LG) as the doc reads it, or all six
  pairs among {N, ag, bg, cg}. The left panel's "+" explicitly includes the fault–fault pair (ag, ab), and (15b) is
  over all of F₂, so the second reading is live. Both are cheap on the grid (21 pairs instead of 9, ≈ 5 min):
  register both, run both from the start, and let the map say which one Taylor computed. Same for Q2 ("separates
  N and all LL and LG faults"): the pair set follows whichever reading Q1 matches, stated before Q2 runs.

## 3. Smaller items

- The feasibility decision is a zero-objective LP with the solver's default tolerance. Cells near the boundary of
  a region can flip with tolerance. Register the solver (HiGHS) and either its tolerance, or better the max-slack
  form (maximise t subject to every P-row ≤ rhs − t; separated iff t* < −10⁻⁷, |t*| ≤ 10⁻⁷ reported as undecided).
  Not blocking, but it makes the map comparison reproducible.
- Equation numbers: the PDF in `papers/` (v2) numbers the i_L equality (18a), the (18b) block and the W^{Rel,2}
  block (19); "(20a)" in the doc is the post-test interval there. Cite the PDF's numbers.
- "Σ invertible" → "Σ injective" (21 × 7).
- Q2's targets and method (ADMM, ρ = 1, Q = I, two starts, ±0.1, primal re-check) are fine; ADMM termination is
  unstated in the paper, so a ±0.1 band is the right kind of rule. Note the printed Δ entries average
  1.53 + j0.59, |·| = 1.64, × √7 = 4.34, consistent with ‖Δ‖ ≈ 4.35.
- Q3 (§IV-C case) as information: fine. Its grid minima have no printed target.

## 4. Code (35f8d22), checked against the paper

- `net_matrices`: nodes 1–14 plus F on line 2–3 at m̂_z = ½; Γ = Z_L⁻¹(Φ − ℵ_F), Θ = Z_R⁻¹(Ψ − ℵ_F) as in
  Appendix A; loads as admittances; ag fault admittance 1/(m̂_r r_F) to ground, ab as the Fig. 2 resistor. ✓
- `models`: Ω_z^{ag} = z(e^a + k e⁰)Γ, Ω_r^{ag} = r_F e^a(Γ + Θ), Ω_z^{ab} = z(e^a − e^b)Γ, Ω_r^{ab} = (r_F/2)(e^a − e^b)(Γ + Θ);
  Ω^N = zΓ^N + Ψ^N (scalar z: right for the primary, wrong under `--z0 3`, see §1(1)). ✓ / fix for V5
- `polygon_P`: Re[e^{−jφ_l} λ] ≤ 1, φ_l = 2πl/20. ✓  `_re`: complex map as a real 2 × 2 block. ✓
- `separated`: literal block = (18b) + (19) with one λ (the two M-equalities), Pλ ≤ 1, Pλ_z ≤ m_z 1, Pλ_r ≤ m_r 1;
  sound block = V3's ties; (18a) ties the two models' i_L through their λ; N block v_L = Ω^N(u⁰ + Mλ^N). ✓
- `source_vector`: i_k = A[0, i_k⁺, δ], Σ = scale · I ⊗ b. ✓  `case`: §VI-D and §IV-C bus sets, angles, Σ scales. ✓
- `grid`/`q1`: pairs list is the 9-pair reading only (see §2); `smallest` returns a single tie-broken point (see §2).
- Tests: the three pass; the match to `network.solve` at 10⁻⁶ for N, ag, bc in both cases is a good independent
  check of Appendix A.

## 5. Not checked

Q1 itself (not run); the ADMM (not written); whether the standard-branch primary is Taylor's network (the thesis
table is unavailable); PSCAD (Q4, not registered).

## 6. Q1 result (ieee14 at `cc1d6f6`), checked 3 Nov 2026

**Registration integrity.** The amendments (88603ca, 04:26: 0.2 grid, figure targets, set rule, map comparison,
R9/R21, max-slack rule, V5's Ω^N) precede the run (cc1d6f6, 04:51). Every registered variant ran and is in the
table; the §3 verdict is applied as written: **primary not reproduced**; **V4 (angles `linspace(0, 2π/3, 8)[:7]`,
i.e. multiples of 2π/21) meets every "reproduced" condition and is reported as information, not substituted**.
Q2 on V4's angles follows §3's "primary unless Q1 failed; then stated".

**Independent recomputation** from the stored t* values (`results/ieee14/q1_*.json`, my own classification and
comparison code against `review/checks/p_i14_fig5_map.json`, which `results/ieee14/fig5_digitised.json` equals
byte for byte):

| run | (a) | (b) LG / LL | (c) | left | right |
|---|---|---|---|---|---|
| primary | j0.4 (1.058) | 0.6 ± j1.0 / −0.6 ± j1.0 (3.085) | ±1.4 ± j0.8, four (4.266) | 94.56 % | 89.12 % |
| V4 | j0.2 unique (0.529) | −1.2 + j0.2 / 1.2 − j0.2 (3.219) | ±(1.6 + j0.6) (4.521) | 100 % | 99.55 % |
| V1 | j0.4 | 3.085 | 4.266 | 94.33 % | 88.66 % |
| V2, V5, LL 2 m̂_r r_F | as primary | as primary | as primary | 94.56 % | 89.12 % |

All as the doc reports. The sound variant (V3) gives the same decision on all 9 261 (cell, pair) entries as the
literal one, with and without V4; R9 and R21 give identical maps in every run; no undecided cell (smallest |t*|
over all runs 1.6 × 10⁻⁴, above the 10⁻⁷ tolerance). The §IV-C information run: δ = 0 separates every R9 pair; under
R21 the LL fault–fault pairs need 2.0 − j1.4 (|δ| = 2.44), the grid's edge.

**Symmetry.** The primary's right-panel map is conjugate-symmetric (0 cells differ between δ and δ̄) and point-
symmetric with LG ↔ LL (0 violations). V4 breaks the conjugate symmetry (70 cells) and keeps the point symmetry
(0 violations), as the figure does. That is the measurable form of the doc's "same pattern turned by about 10°".

**The two V4 cells that differ from the figure**, (−1.8, 0.4) and (1.8, −0.4): the figure has LG-only and LL-only
(re-read at 900 dpi: the (−1.8, 0.4) marker is a disc), ours has all six. The deciding pair's slack is
t* = −0.0031 (N–ca at the first, N–bg at the second; −0.0030 under V3) on the 20-gon's unit scale, i.e. 0.3 % of
the noise radius: a region-edge cell that a solver tolerance or a different polygon orientation moves.

**3.02, corrected.** My §2 called the printed 3.02 a likely typo. Research's 0.1-grid information run with V4's
angles gives the N-vs-all-LG minimum at 0.7 + j0.9, |δ| = 1.1402, ‖Δ‖ = 3.017 (LL at −0.7 − j0.9), which I confirm
from the stored t*. So the text quotes (b) from a 0.1 grid and (c) from the 0.2 grid (on the 0.1 grid (c) is
4.506 at ±(1.3 − j1.1)); with the primary angles nothing at |δ| = 1.141 or 1.131 separates all LG faults. The
claim is withdrawn in §2 with a dated bracket; it goes into REVIEW.md §7 at the PR as a refuted reviewer claim,
beside "the primary as registered reproduces Fig. 5" (refuted) and the V4 finding.

**Determinism.** Rerunning `q1` (primary) and `q1 --endpoint-off` (V4) on a scratch checkout of cc1d6f6 reproduces every stored t* exactly (max difference 0 over 2 × 9 261 entries), the same minima and the same agreement figures.

**For Q2, before it runs:** state the ADMM termination rule and iteration cap (the paper gives none), and run the
primal re-check of the result under V3 as well as the literal set, so the 4.35 carries a valid certificate.
