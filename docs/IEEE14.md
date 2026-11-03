# Taylor's IEEE 14-bus: reproduce his auxiliary-signal design, then build it in PSCAD

> **Status, 3 Nov 2026: pre-registered, nothing run.** Written before any 14-bus code exists. Waiting for the
> reviewer before Q1 is run.

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
no line charging, no transformer taps. Zero sequence: z0 = 3 z1 on every branch (k = z0/z − 1 = 2, the paper's
value for the relay line; it gives no other zero-sequence data). Lines symmetrical and transposed, phase-domain
3×3 impedances A diag(z0, z1, z1) A⁻¹.

**Sources and loads (§VI-D case).** All sources are IBRs, C = {1, 2, 3, 4, 5, 8, 14}: ideal current sources,
i_k = A [0, i_k⁺, Δ_k] with |i_k⁺| = 1 and angles `linspace(0, 2π/3, 7)` in bus order. Loads 0.1 + j0.01 at buses
6, 10, 11, 13, grounded wye (all sequences). Buses 7, 9, 12 junctions. Noise: each source gets λ_k b with b =
[1, α, α²]ᵀ, α = e^{j2π/3}, λ_k in a regular 20-gon (Re[e^{−jφ_l} λ_k] ≤ 1, φ_l = 2πl/20), scaled by Σ = I.
Literally b is A's third column, the negative-sequence direction; we code it literally (variant V1 below).

**Relay and faults.** Relay at bus 2 on line 2-3, z = z_{2-3}. Fault on line 2-3 at the nominal m̂_z = m̂_r = 1/2,
r_F = 1, m̲_z = 0.15. Models N, ag, bg, cg, ab, bc, ca; ψ and Ω as in §V (Ω_z^{ag} = z(e^a + k e^0)Γ^{ag},
Ω_r^{ag} = r_F e^a(Γ^{ag} + Θ^{ag}), Ω_z^{ab} = z(e^a − e^b)Γ^{ab}, Ω_r^{ab} = (r_F/2)(e^a − e^b)(Γ^{ab} + Θ^{ab}),
rotated phases for bg, cg, bc, ca; normal operation v_L = (zΓ^N + Ψ^N) u). Network matrices Γ, Θ (i_L, i_R maps)
from Appendix A at m̂_z = m̂_r = 1/2.

**Separation test.** A signal separates a pair when the paper's relaxation of the pair's intersection, built on
W^{Rel,3} with polyhedral noise, is empty (Lemma 7). We test the primal set directly as a linear feasibility
problem (empty ⇔ the Farkas dual system S of Appendix C-A is nonempty). **Literal reading, primary:** for each
fault model η, one noise vector λ^η appears in u_z = m_z u⁰ + Σλ^η, u_r = m_r u⁰ + Σλ^η and in the i_L equality
(20a), with Pλ^η ≤ 1; and W^{Rel,2} adds u_z = m_z u⁰ + Σλ_{mz}, u_r = m_r u⁰ + Σλ_{mr}, Pλ_{mz} ≤ m_z 1,
Pλ_{mr} ≤ m_r 1. This is what the dual system's equalities encode. *Note recorded before any run: with Σ
invertible these equalities force λ^η = λ_{mz} = λ_{mr}, so the literal set is not obviously a relaxation of W. We
reproduce it as printed and report a sound variant beside it (V3).*

## 2. Registered questions

**Q1. Fig. 5 grid (§VI-D1), common signal Δ = δ·1 at all seven IBRs.** δ on a 0.1 grid over [−2, 2]².
Targets, the paper's own: (a) smallest δ separating (N, ag), (N, ab) and (ag, ab): **δ = j0.2, ‖Δ‖ ≈ 0.53**;
(b) smallest separating N from ag, bg, cg: **‖Δ‖ ≈ 3.02**; (c) smallest separating N from all six faults:
**δ = 1.6 + j0.6, ‖Δ‖ ≈ 4.52**.

**Q2. Per-inverter signal (§VI-D2).** Minimise ‖Δ‖² over a separate Δ_k per IBR, separating N from all six faults,
from Δ₀ = 0 and Δ₀ = (1.6 + j0.6)1. Target **‖Δ‖ ≈ 4.35**, entries ≈ 1.48–1.59 + j0.50–0.66. Method: the paper's
ADMM (Appendix C-B, ρ = 1, Q = I) on the dual systems, with the separation of the result re-checked on the primal.

**Q3 (information).** The §IV-C case (SGs at 1, 3, 5, 14 with unit voltages at angles `linspace(0, 2π/10, 4)`;
IBRs at 2, 4, 7, 8, 12; Σ = 0.1 I): Q1's three grid minima. The paper gives no signal numbers for it.

## 3. Go / no-go, fixed now

- **Q1 reproduced:** all three targets hit on the grid (a: δ = j0.2; b: ‖Δ‖ within ±0.05 of 3.02; c: δ = 1.6 + j0.6).
  **Approximately:** each within one grid step (0.1 in δ). **Not reproduced:** otherwise.
- **Q2 reproduced:** ‖Δ‖ within ±0.1 of 4.35 from both starts, with the primal check confirming separation.
- If Q1 is not reproduced, the variants below run, **all of them, all reported**, as information on what the
  paper's unstated choices are; none becomes "the reproduction" after the fact:
  - **V1:** noise along the positive-sequence direction [1, α², α]ᵀ;
  - **V2:** line charging B/2 at both branch ends (standard IEEE 14-bus B);
  - **V3:** the sound relaxation: λ in u_z, u_r free in Λ and in m_zΛ, m_rΛ, not tied to the i_L noise;
  - **V4:** IBR angles `linspace(0, 2π/3, 8)[:7]` (endpoint excluded).
- Q2 runs whatever Q1 gives, on the formulation that Q1 settles on (primary unless Q1 failed; then stated).

## 4. What this does not do

No EMT, no δ injected in PSCAD, no grid-forming inverter. Static, phasor model, as the paper. The PSCAD build of
the same network (§IV-C case: SGs plus our grid-following inverters) is Q4, registered after Q1–Q2.

## 5. Code

`src/ieee14.py` (network, Appendix A matrices, primal feasibility LP, grid, ADMM); results in `results/ieee14/`.
