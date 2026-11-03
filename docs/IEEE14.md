# Taylor's IEEE 14-bus: reproduce his auxiliary-signal design, then build it in PSCAD

> **Status, 3 Nov 2026: pre-registered and reviewed (PR #69: cleared once §2–§3 carry the review's amendments,
> which they now do); Q1 not yet run.**

## 0. Why this system

Prof. Taylor's 20 Oct meeting (docs/meetings/2026-10-20_biweekly.md) asked for systems with several inverters,
found from existing sources, and the team now works on the optimization (3 Nov 2026). Taylor's own *Geometry of
Distance Protection* (arXiv 2510.04379, papers/Taylor_2025_Geometry_of_Distance_Protection.pdf; equations read
from the arXiv HTML v2) designs auxiliary signals on an IEEE 14-bus system with 5 and then 7 inverters, and
prints the numbers. Reproducing them checks our optimization against his on a multi-inverter system; the same
network then goes to PSCAD (Q4, registered later). It is also the system of his reachability paper with Baeckeland
(five grid-forming inverters, Simulink), which stays out of scope here.

## 1. His system and formulation, as we will code it (§IV-C, §V, §VI-D, Appendices A–C)

**Network.** IEEE 14-bus, "line admittances from Table 3.1" of Baeckeland's 2022 KU Leuven thesis, which we could
not find. **Primary:** the standard IEEE 14-bus branch data (Baeckeland, Yang & Seo 2026 say their 14-bus lines are
"one-to-one translated from the standard IEEE 14-bus benchmark"): series R + jX of the 20 branches on 100 MVA,
no line charging, no transformer taps. *[Amended 3 Nov 2026, before any code ran: the first draft had z0 = 3 z1 on
every branch. Appendix A computes i_L = (v_L − v_F)/(m̂_z z) and i_R with the scalar z, which is exact only if the
network's lines have no phase coupling, so the primary is now:]* each branch is the scalar admittance 1/(R + jX)
in every phase, no mutual coupling (z0 = z1 in the network); k = 2 enters only the relay's ground-fault loop
(Ω_z^{ag}), as the paper writes it. Variant V5 below has z0 = 3 z1 in the network with exact 3×3 line currents.

**Sources and loads (§VI-D case).** All sources are IBRs, C = {1, 2, 3, 4, 5, 8, 14}: ideal current sources,
i_k = A [0, i_k⁺, Δ_k] with |i_k⁺| = 1 and angles `linspace(0, 2π/3, 7)` in bus order. Loads are **admittances**
0.1 + j0.01 per phase to ground at buses 6, 10, 11, 13 (i_J = −Y_J v_J, Appendix A). Buses 7, 9, 12 junctions.
Noise: each source gets λ_k b with b = [1, α, α²]ᵀ, α = e^{j2π/3}, λ_k in a regular 20-gon (Re[e^{−jφ_l} λ_k] ≤ 1,
φ_l = 2πl/20), scaled by Σ = I. Literally b is A's third column, the negative-sequence direction; we code it
literally (variant V1 below). It then lands in the signal's own slot, i_k = A [0, i_k⁺, Δ_k + λ_k]: each IBR's
negative-sequence injection is uncertain within a 20-gon of inradius 1 around its command.

**Relay and faults.** Relay at bus 2 on line 2-3, z = z_{2-3}. Fault on line 2-3 at the nominal m̂_z = m̂_r = 1/2,
r_F = 1, m̲_z = 0.15. Models N, ag, bg, cg, ab, bc, ca; ψ and Ω as in §V (Ω_z^{ag} = z(e^a + k e^0)Γ^{ag},
Ω_r^{ag} = r_F e^a(Γ^{ag} + Θ^{ag}), Ω_z^{ab} = z(e^a − e^b)Γ^{ab}, Ω_r^{ab} = (r_F/2)(e^a − e^b)(Γ^{ab} + Θ^{ab}),
rotated phases for bg, cg, bc, ca; normal operation v_L = (zΓ^N + Ψ^N) u). Network matrices Γ, Θ (i_L, i_R maps)
from Appendix A at m̂_z = m̂_r = 1/2. The LL fault at F is the Fig. 2 / (3b) resistor m̂_r r_F between the two
phases (the only reading consistent with Ω_r^{ab}; Appendix A's sentence, read literally, gives 2 m̂_r r_F).

**Separation test.** A signal separates a pair when the paper's relaxation of the pair's intersection, built on
W^{Rel,3} with polyhedral noise, is empty (Lemma 7). We test the primal set directly as a linear feasibility
problem (empty ⇔ the Farkas dual system S of Appendix C-A is nonempty). **Literal reading, primary:** for each
fault model η, one noise vector λ^η appears in u_z = m_z u⁰ + Σλ^η, u_r = m_r u⁰ + Σλ^η (18b) and in the i_L
equality (18a), with Pλ^η ≤ 1; and W^{Rel,2} (19) adds u_z = m_z u⁰ + Σλ_{mz}, u_r = m_r u⁰ + Σλ_{mr},
Pλ_{mz} ≤ m_z 1, Pλ_{mr} ≤ m_r 1 (equation numbers of the v2 PDF in papers/). This is what the dual system's
equalities encode. *Note recorded before any run, confirmed by the review (PR #69): Σ (21 × 7) is injective, so
these equalities force λ^η = λ_{mz} = λ_{mr}; a point of W lies in the literal set only if λ = 0 or m_z = m_r = 1, so
the literal set is neither a relaxation nor a restriction of W and Lemma 7's certificate does not apply to it. We
reproduce it as printed ("what the paper computed"); any claim of separation rests on the sound variant V3.*

**Decision rule.** Each pair's feasibility is a max-slack LP (HiGHS): maximise t with every polygon row
≤ rhs − t (t ≤ 1); **separated iff t* < −10⁻⁷** (or the equalities are infeasible); |t*| ≤ 10⁻⁷ is counted as not
separated and listed as undecided.

## 2. Registered questions

**Q1. Fig. 5 grid (§VI-D1), common signal Δ = δ·1 at all seven IBRs.** *[Amended 3 Nov 2026 after the review
(PR #69, `review/checks/p_i14_fig5.*`, Fig. 5 digitised), before the grid ran.]* δ on the figure's **0.2 grid over
[−2, 2]² (21 × 21)**; a 0.1 grid is information only. Targets, from the figure (and the text where it agrees):
- (a) smallest δ separating (N, ag), (N, ab) and (ag, ab): **δ = j0.2, the unique minimiser at |δ| = 0.2
  (‖Δ‖ ≈ 0.53)**;
- (b) smallest separating N from all LG faults: **|δ| = 1.2166 with −1.2 + j0.2 among the minimisers
  (‖Δ‖ = 3.22)**; from all LL faults: **|δ| = 1.2166 with 1.2 − j0.2 among them**. The text's 3.02 (|δ| = 1.141) is
  not a 0.2-grid magnitude and contradicts the figure; we report whether any δ with |δ| = 1.141 or 1.131
  (0.1 grid) separates, so it is answered either way;
- (c) smallest separating N from all six faults: **|δ| = 1.7088 with 1.6 + j0.6 among the minimisers** (the figure
  has two, 1.6 + j0.6 and −1.6 − j0.6; the full minimiser set is stored);
- **whole maps:** per panel, the fraction of the 441 cells whose class matches the digitised figure (left: none /
  N-ag only "." / N-ab only "v" / all three "+"; right: none / all LG "." / all LL "v" / all six "+"), mismatches
  listed; and the point symmetry the figure shows (LG ↔ LL under δ → −δ, right panel).

"N and all LG faults" is read two ways, both run from the start: **R9**, the pairs (N, η) only; **R21**, every pair
among the models involved ({N, ag, bg, cg} for LG, {N, ab, bc, ca} for LL, all seven for the six faults). The left
panel is the same under both. The reading whose right-panel map agrees better is taken as Taylor's; both are
reported.

**Q2. Per-inverter signal (§VI-D2).** Minimise ‖Δ‖² over a separate Δ_k per IBR, separating N from all six faults
(pair set R9 or R21, whichever Q1 matches, stated before Q2 runs), from Δ₀ = 0 and Δ₀ = (1.6 + j0.6)1. Target **‖Δ‖ ≈ 4.35**, entries ≈ 1.48–1.59 + j0.50–0.66. Method: the paper's
ADMM (Appendix C-B, ρ = 1, Q = I) on the dual systems, with the separation of the result re-checked on the primal.

**Q3 (information).** The §IV-C case (SGs at 1, 3, 5, 14 with unit voltages at angles `linspace(0, 2π/10, 4)`;
IBRs at 2, 4, 7, 8, 12; Σ = 0.1 I): Q1's three grid minima. The paper gives no signal numbers for it.

## 3. Go / no-go, fixed now

- **Q1 reproduced:** (a)–(c) hold exactly on the 0.2 grid (minimum magnitudes equal, printed points among the
  minimisers) **and** each panel's map agrees on ≥ 95 % of its 441 cells (right panel: the better reading).
  **Approximately:** (a)–(c) hold but a map is below 95 %, or (a)–(c) each hold within one grid step (0.2 in δ).
  **Not reproduced:** otherwise. *[Amended 3 Nov 2026 after PR #69; the first rule (0.1 grid, ‖Δ‖ within ±0.05 of
  3.02) would have scored a correct reproduction "not reproduced".]*
- **Q2 reproduced:** ‖Δ‖ within ±0.1 of 4.35 from both starts, with the primal check confirming separation.
- If Q1 is not reproduced, the variants below run, **all of them, all reported**, as information on what the
  paper's unstated choices are; none becomes "the reproduction" after the fact:
  - **V1:** noise along the positive-sequence direction [1, α², α]ᵀ;
  - **V2:** line charging B/2 at both branch ends (standard IEEE 14-bus B);
  - **V3:** a sound relaxation of W: u_z = m_z u⁰ + Σλ_z, u_r = m_r u⁰ + Σλ_r with Pλ_z ≤ m_z 1, Pλ_r ≤ m_r 1,
    tied to the i_L noise λ only by the valid P(λ − λ_z) ≤ (1 − m_z)1 and P(λ − λ_r) ≤ (1 − m_r)1;
  - **V4:** IBR angles `linspace(0, 2π/3, 8)[:7]` (endpoint excluded);
  - **V5:** z0 = 3 z1 on every branch in the network, i_L and i_R from the 3×3 segment impedances, and
    Ω^N = Z_abc Γ^N + Ψ^N;
  - (if Q1 fails) the LL fault resistor 2 m̂_r r_F, Appendix A's literal sentence.
- **V3 (sound) runs alongside the primary in every case**, as the claim-carrying version, whatever Q1 gives.
- Q2 runs whatever Q1 gives, on the formulation that Q1 settles on (primary unless Q1 failed; then stated).

## 4. What this does not do

No EMT, no δ injected in PSCAD, no grid-forming inverter. Static, phasor model, as the paper. The PSCAD build of
the same network (§IV-C case: SGs plus our grid-following inverters) is Q4, registered after Q1–Q2.

## 5. Code

`src/ieee14.py` (network, Appendix A matrices, primal feasibility LP, grid, ADMM); results in `results/ieee14/`.
