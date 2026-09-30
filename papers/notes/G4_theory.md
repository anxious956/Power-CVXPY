# G4: Guaranteed active fault diagnosis theory, and why B1 is negative

These notes cover the set-based ("guaranteed") active fault diagnosis (AFD) literature that sits behind Taylor's auxiliary-signal line, plus one industry report. The aim is to explain and position the B1 screening result: on the CIGRE MV 20 kV static model, a bounded negative-sequence injection δ barely separates an in-zone fault at 85 % from the matching remote-bus fault. I read all four theory papers in full from the pypdf text extraction. The math came out partly garbled, so I reconstructed every formula below from context and flag any doubt. For Sandia SAND2020-0265 I read the front matter, Sections 1 to 5 and the conclusions, and skipped the PSCAD trace appendices.

**Short version.** In all four papers the auxiliary input only *translates* each hypothesis's set of possible measurements. Two hypotheses therefore become separable only through the *difference* of their input-to-output maps, `N = B_i − B_j`. The input must push `N·δ` outside a fixed "difference set" `Z(i,j)`, and that set always contains the instrument-error box counted twice. The necessary size is therefore about `|δ| ≳ (2ε − offset)/|N|`, which tends to infinity as `N → 0`. This is exactly the B1 situation.

A second point matters for defending a negative result. Outer (conservative) set approximations can only *certify separability*; they can never prove inseparability (Nikoukhah Lemma 23; Scott §6). A negative claim must rest on exact witnesses, i.e. sampled real scenarios that overlap, and that is what B1 has.

### Notation I use in the "Relevance to us" parts (mine, not the papers')

- `δ ∈ ℂ ≅ ℝ²`: the negative-sequence current phasor injected by the inverter (pu). It is limited to `|δ| ≤ ρ_max` by the current limit, whose share is split with positive-sequence current.
- `y ∈ ℝ^m`: the relay's measurement channels (real and imaginary parts of the V and I phasors or their sequence components).
- Hypotheses: `h ∈ {in, out}` (in-zone, out-of-zone). Their uncertain parameters are `θ ∈ Θ_h` (fault location, fault resistance R_f, loading).
- Instrument error: `v ∈ V = {‖v‖∞ ≤ ε}`, with `ε = 0.01` pu per channel.
- Static model, linear in δ within one limiter regime: `y = m_h(θ) + B_h(θ)·δ + v`.
- For a pair of scenarios `(θ_i ∈ Θ_in, θ_j ∈ Θ_out)`:
  - `Δm = m_in(θ_i) − m_out(θ_j)` is the δ-independent difference.
  - `N = B_in(θ_i) − B_out(θ_j)` is the *differential* δ-sensitivity.
  - `N_k` is row k of N, and `|N_k|` is its size (0.0008 to 0.024 pu per pu δ in B1).

---

## Paper 1 — Scott et al. 2014: input design with zonotopes

**Citation.** J. K. Scott, R. Findeisen, R. D. Braatz, D. M. Raimondo, "Input design for guaranteed fault diagnosis using zonotopes," *Automatica* 50(6):1580–1589, 2014. doi:10.1016/j.automatica.2014.03.016. A preliminary version appeared at ACC 2013.

### Problem class

- **Dynamics.** Discrete time. There are `n_m` linear time-invariant models, and a fault is a discrete switch between them. A fault *scenario* is a sequence of model indices over `[0,N]`, so sequential and simultaneous faults are allowed. The models are eqs. (1)–(2), p.1581:
  - `x_{k+1} = A(i)x_k + B(i)u_k + r(i) + B_w(i)w_k`
  - `y_k = C(i)x_k + s(i) + D_v(i)v_k`
  - `r` and `s` are additive fault offsets (e.g. sensor or actuator bias).
- **Uncertainty.** Pointwise-in-time bounds. The initial state satisfies `x0 ∈ X0`, and at every step `w_k ∈ W` and `v_k ∈ V`. All three sets are **zonotopes** `{G, c} = {Gξ + c : ‖ξ‖∞ ≤ 1}`.
- **Input.** Open loop: `ũ = (u_0 … u_{N−1})` is designed offline and applied unchanged.
- **Goal.** Any observed output sequence must be consistent with at most one scenario.

### Central separability result

- **Definition 1 (eq. 16, p.1582).** An input ũ *separates* scenarios i and j when their reachable output-sequence sets are disjoint: `Ψ̃(ũ,i) ∩ Ψ̃(ũ,j) = ∅`.
- **Key structural fact (p.1582, from eq. 10).** The reachable output set is a zonotope with a fixed generator matrix `G^Ψ(i)`. Its center `ψ(ũ,i) = ψ(0,i) + C̃(i)B̃(i)ũ` is affine in ũ. So **the input only translates the sets; it never changes their shape or orientation.**
- **Lemma 2 (p.1582, from Dobkin et al.).** Two zonotopes `{G_z, a_z+b_z}` and `{G_y, a_y+b_y}` are disjoint if and only if `a_y − a_z ∉ {G_z, b_z} ⊕ {G_y, −b_y}`.
- **Theorem 3 (eq. 17, p.1582).** ũ separates the scenario set if and only if, for every pair i ≠ j:
  - `Ñ(i,j)·ũ ∉ Z̃(i,j)`, where
  - `Ñ(i,j) = C̃(j)B̃(j) − C̃(i)B̃(i)` (difference of the input-to-output maps), and
  - `Z̃(i,j) = { [G^Ψ(i)  G^Ψ(j)], ψ(0,i) − ψ(0,j) }`, a zonotope with both hypotheses' generators, centered at the difference of the zero-input centers.
  - Z̃ is the Minkowski "difference body" `Ψ_i ⊕ (−Ψ_j)`. Every uncertainty source appears **twice**, once per hypothesis, and that includes the measurement-error box.
- **Consequences stated on p.1583.**
  1. If `Ñ ≠ 0`, the set of separating inputs is non-empty and *unbounded*, i.e. separation is always possible with a large enough input.
  2. If `Ñ = 0`, the input is irrelevant: either every input separates (when `0 ∉ Z̃`) or none does (when `0 ∈ Z̃`).
  3. The set of separating inputs is **non-convex**, being the complement of a convex set. Nikoukhah (1998) had shown the same with polytopes: the non-separating inputs form a convex polytope.
  4. A non-separating input can still give a diagnosis for *particular* outputs. A separating input can sometimes give the diagnosis before step N (p.1582).
- **Lemma 4 (eq. 20, p.1583): an LP separation margin.**
  - Define `δ^[q](ũ) = min δ` subject to `Ñ·ũ = Gξ + c` and `‖ξ‖∞ ≤ 1 + δ`.
  - Then `Ñũ ∉ Z̃` if and only if `δ^[q](ũ) > 0`. This needs G to have full row rank; Remark 1 (pp.1583–84) gives the fix when it does not.
  - `1 + δ^[q]` is the ∞-norm gauge of `Ñũ − c` with respect to the generators.
- **Convexity (§5.1, p.1584).** `δ^[q](ũ)` is the value of a parametric LP, so it is **convex in ũ** (the paper cites Bertsimas and Tsitsiklis, Thm 5.1). Its maximum over a polytope Ũ is therefore attained at a **vertex**.
- **Lemma 1 (p.1582): support function of a zonotope.** For a half-space `hᵀz ≤ k`, subtracting the zonotope `{G, c}` shrinks the right-hand side to `k − hᵀc − ‖hᵀG‖₁`. The support function is therefore `σ_Z(h) = hᵀc + ‖Gᵀh‖₁`, which I use below.

### When no admissible input separates

The paper states the positive direction. Section 6.1 (eq. 36, p.1584) solves `min J(ũ)` subject to `ũ ∈ Ũ` and `Ñũ ∈ Z̃`. If this is infeasible, every admissible input separates the pair and the pair can be dropped. The converse follows from Theorem 3 but is not stated in the paper:

- **[my derivation]** No admissible input separates the pair if and only if `Ñ·Ũ ⊆ Z̃`.
- Because the margin is convex, it suffices to check the extreme points of Ũ.
- **[my derivation]** Written with the support function: some ũ with `‖ũ‖ ≤ ρ` separates if and only if `∃h: ρ‖Ñᵀh‖₂ > hᵀc + ‖Gᵀh‖₁`.

### How the required input scales [my derivation, exact consequences of Theorem 3]

- **Scaling N.** `S(αÑ, Z̃) = S(Ñ, Z̃)/α`. The required input scales **exactly as 1/|N|**.
- **Scaling the uncertainty.** If Z̃ is centered at 0, then `S(Ñ, κZ̃) = κ·S(Ñ, Z̃)`. The required input grows linearly with the uncertainty size.
- **General necessary bound.** If Z̃ contains a ball of radius r around its center c, then separation needs `‖Ñũ − c‖ ≥ r`. Hence `‖ũ‖ ≥ (r − ‖c‖)/‖Ñ‖`.
- **Limit case.** As `N → 0` the bound tends to infinity, which is consequence 2 above.

### Design problem and computational cost

- **Optimization (18)–(19), p.1583.** Minimize `J(ũ) = Σ u_kᵀ R u_k` over `ũ ∈ Ũ` (a polytopic input bound) intersected with the separating set.
- **Reformulation.**
  - The strict inequality `δ^[q] > 0` becomes `ε ≤ δ^[q] ≤ δ_m^[q]`, which makes the problem the bilevel program (21).
  - The inner LP (20) is replaced by its KKT conditions (22)–(28).
  - The complementarity conditions become binaries through big-M constraints (30)–(32).
  - The result is the **MIQP (33)**, solved with CPLEX.
- **Size.** The number of binaries is `B = Q·2(N+1)·n_y·ℓ`, where `Q = s(s−1)/2` is the number of scenario pairs and `ℓ` is the zonotope order.
- **Complexity reductions.**
  - Pair elimination (§6.1, Lemma 6): a QP per pair, which either removes the pair or replaces it with one linear cut.
  - Zonotope order reduction (§6.2): outer-approximates Z̃. The result is conservative but still guaranteed.
  - Set-valued-observer ("L-separating") inputs (§7): binaries `Q·2·n_y·ℓ`, independent of the horizon N. With observer gain `L = 0` the condition becomes separation at the terminal time only, `Ψ_N(ũ,i) ∩ Ψ_N(ũ,j) = ∅` (eq. 56).
- **Big-M bound (§5.1).** `δ_m^[q]` comes from a vertex maximum or the MILP (34) with Lemma 5.
- **State constraints (§5.2).** Linear constraints obtained through the Pontryagin difference.

### Examples and numbers (pp.1586–1589)

- **2-state, 5-model example.** `‖u‖∞ ≤ 9`, feasible for horizons N ≥ 2.
  - Order ℓ=1: min `‖ũ‖₂ = 8.6143` in 0.02 s. Order ℓ=2: 8.6081 in 3.58 s.
  - With pair elimination: same optimum in 0.36 s.
  - Observer, L=0: needs N ≥ 3, norm 11.5203. Kalman gain: N=2, norm 9.2144.
- **Random models, n_x=50, 10 inputs and 10 outputs, `|u| ≤ 20`, N=10.**

  | Case | Full method | Observer method |
  |---|---|---|
  | 2 models, time | 1.13 s | 0.04 s |
  | 2 models, norm | 19.01 | 41.70 |
  | 3 models, time | 50.30 s | 1.04 s |
  | 3 models, norm | 247.10 | 573.99 |

  The observer method solved N=100 in 20.42 s.
- **Permanent-magnet DC motor.** 6 fault models, `|u_s| ≤ 6` V, 5 ms sampling.
  - Observer L=0, ℓ=3: minimum N=9, norm 15.92, 58.47 s.
  - Pair elimination: 15 → 10 pairs, N=10, norm 16.01, 0.065 s.
  - Table 3, three-model subcase: pole-placement gains reduce N from 7 to 2.
  - Full method: N=2, norm 6.58, 0.035 s.

### Relevance to us

- **Our static problem is Scott with horizon 0.** Take one snapshot, `u = δ ∈ ℝ²`, `Ñ = N`. Then Theorem 3 says δ separates an in-zone scenario set from an out-of-zone set exactly when `N·δ ∉ Z(in,out)`, with `Z = (m_in-set) ⊕ (−m_out-set) ⊕ (V ⊕ −V)`.
- **Only the differential sensitivity matters.** The part of δ's effect that is common to both hypotheses, `(B_in + B_out)/2·δ`, moves both sets together and buys nothing. B1's finding that δ changes both measurements almost equally means almost all of the injected signal is common-mode.
- **The noise box counts twice.** The measurement-error part of Z is a box of half-width **2ε = 0.02 pu** per channel. For a matched pair (Δm ≈ 0) the required injection is therefore at least `2ε/|N|`:

  | `|N|` (pu per pu δ) | Required `|δ|` |
  |---|---|
  | 0.024 | ≥ 0.83 pu |
  | 0.0008 | ≥ 25 pu |

  Both are at or beyond the inverter's negative-sequence capability, which is consistent with B1. **Caveat:** check whether the B1 code counted the 0.01 pu box once or twice. If once, the thresholds halve to 0.42 pu and 12.5 pu.
- **Our δ-gain depends on the uncertain θ.** Fault location and R_f change how δ propagates. So the "translation-only" structure holds only for each *fixed pair* `(θ_i, θ_j)`, not for the hypothesis sets as wholes. Two ways to handle this:
  - (a) Grid θ, as B1 already does. For each pair the condition is exact: `‖Δm + Nδ‖∞ > 2ε`.
  - (b) Use Taylor & Domínguez-García's multiplicative-uncertainty model, which leads to a bilinear SDP.
- **The margin LP (Lemma 4) and its convexity are directly usable.** For one pair, the best δ in the current-limit disk lies on the circle `|δ| = ρ_max`. So a grid over |δ| is unnecessary within one limiter regime (see Synthesis, test T1).

---

## Paper 2 — Raimondo et al. 2016: closed-loop input design with set-valued observers

**Citation.** D. M. Raimondo, G. R. Marseglia, R. D. Braatz, J. K. Scott, "Closed-loop input design for guaranteed fault diagnosis using set-valued observers," *Automatica* 74:107–117, 2016. doi:10.1016/j.automatica.2016.07.033.

### Problem class

- **Dynamics.** The same discrete-time multi-model LTI system as Scott (eqs. 1–2, p.108). One model is active on the whole test window, and the prior initial-state set `X0(i)` may depend on the model.
- **Uncertainty.** `X0(i)`, `W` and `V` are general **convex polytopes**, represented as **constrained zonotopes (CZ)**: `{Gξ + c : ‖ξ‖∞ ≤ 1, Aξ = b}` (Definition 1, eq. 3, p.108). A set is a CZ exactly when it is a convex polytope.
- **Input.** Polytopic constraints `u_k ∈ U`. Designs are open loop (§3), closed loop in a moving horizon (§4), or an explicit precomputed feedback law (§5).

### Central results

- **Theorem 1 (eqs. 19–20, p.110).** `ũ ∈ S_N` if and only if `N(i,j)·ũ ∉ Z(i,j)` for all i ≠ j.
  - `N(i,j) = C̃(j)B̃(j) − C̃(i)B̃(i)`, exactly as in Scott.
  - Z(i,j) is now a CZ with block-diagonal constraints.
  - Eq. (18) prints the generators as `[G^Ψ(i)  −G^Ψ(j)]`. Scott prints them without the sign. The sign is immaterial for a zonotope because `{G,c} = {−G,c}`.
- **Corollary 2 (eq. 21, p.110).** Lifting the CZ to an ordinary zonotope gives `[N; 0]ũ ∉ Z⁺ = {[G_Z; A_Z], [c_Z; −b_Z]}`. Scott's MIQP then applies unchanged.
- **Existence remark (p.110).** Z⁺ is compact, so a separating input exists whenever `N(i,j) ≠ 0`, i.e. whenever the two models do not have identical output-controllability matrices. The separating set is open, so only ε-optimal solutions exist (footnote 1, p.109).
- **Closed-loop foundation.** The observer is defined by eqs. (22)–(23):
  - `X̂_{k|k} ⊇ X̂_{k|k−1} ∩ {x : Cx ∈ (y_k − s) ⊕ (−D_v V)}`
  - `X̂_{k+1|k} ⊇ A·X̂_{k|k} ⊕ Bu_k ⊕ r ⊕ B_w W`
  - The CZ observer is exact in principle; complexity reduction makes it conservative.
- **Lemma 3 and Theorem 4 (eq. 24, p.111).** Suppose that at time K the remaining input `ũ⁺` separates the hypotheses whose initial sets are the current observer sets `X̂_{K+1|K}(i)`. Then the whole output sequence is consistent with at most one model. The converse holds for an exact observer.
- **Theorem 5 (p.111).**
  - Algorithm 1 re-optimizes at every step. It keeps the shifted old sequence when the new one is no better (Step 9) and removes models that become inconsistent (Step 5).
  - It terminates in `β ≤ N` steps with exactly one model left, where N is the **open-loop** minimum horizon.
  - **So closed loop never does worse than open loop, and its worst case equals the open-loop guarantee.** The gain is on average, when measurements happen to shrink the sets.
  - **For us (checked against the paper, 30 Sep 2026):** Theorem 5 assumes N < ∞, that is, an open-loop input that separates within the input bound. If no admissible δ separates open-loop, as B1 finds for most reach cells, the closed-loop algorithm starts with no guarantee. Redesigning δ online therefore does not rescue the reach question.

### Scaling

The formulas are the same as Scott's, with `X0(i)` replaced online by the smaller `X̂_{K+1|K}(i)`. The required remaining input shrinks as the observer sets shrink. Only the *initial-state or parameter* part of Z shrinks; the per-step noise part `D_v V` enters anew at every step.

### Design and computational cost

- **Open loop.** The MIQP of Scott 2014 applied to Z⁺. The most aggressive CZ reduction makes the complexity independent of `n_x`, `n_w` and `n_v` (p.110).
- **Direct closed loop.** One MIQP per sample, computed during `[k, k+1]` before `y_{k+1}` arrives (Remark 1).
- **Explicit closed loop (§5).**
  - Uses finite-memory observers (eqs. 27–32), with memory `J+1 ≥ Ω+1` (Ω+1 is the observability index).
  - Partitions the recent (u, y) space into hyperrectangles and precomputes an MIQP input for each cell offline. Online work reduces to a table lookup.
  - Cost grows exponentially with memory length and grid resolution.

### Examples and numbers (§6, pp.113–115)

- **Example 1** (2 states, 3 models, `‖u‖∞ ≤ 3`). The CZ method gives a shorter horizon and a smaller input norm than plain zonotopes, and runs faster (0.01 s vs 0.13 s) because of the shorter horizon.
- **Example 2** (10 states). Horizon 5 → 4, time 129 s → 5.92 s.
- **Example 3** (DC motor, 3 models, `|u_s| ≤ 6` V, closed loop). CZ observers give a better mean input length and norm (reported only as a figure).
- **Example 4** (3 states, partial measurements, `‖u‖∞ ≤ 1`).
  - The explicit method used a grid of 6⁴·4² = 20,736 cells, 7.6 h of offline computation, and 0.97 s per cell.
  - Ranking by mean length and norm: direct closed loop is best, explicit is intermediate, open loop is worst (Fig. 4, no numbers in the text).

### Relevance to us: could closed-loop design help?

- **The analogue in our setting** is sequential injection within one fault:
  1. Take the pre-fault or first-shot measurement, which could use `δ₁ = 0`.
  2. Intersect each hypothesis's (location, R_f, loading) set with it; this is the "observer".
  3. Choose `δ₂` to separate only what remains.
- **[my derivation] It cannot beat the matched-pair bound.** Assume θ is fixed during the fault and the instrument errors are independently bounded at each shot. Then, for a fixed pair `(θ_i, θ_j)`, the stacked measurements overlap exactly when `|Δm + Nδ_s|∞ ≤ 2ε` for *every* shot s. So any open- or closed-loop sequence separates the pair only if **one single shot** does. The bound `|δ| ≥ (2ε − |Δm|)/|N|` therefore holds for any number of shots and any feedback policy. This is the static analogue of Raimondo's Theorem 5, where the worst case equals open loop.
- **Where closed-loop or multi-shot could still help:**
  - (i) Shrinking the *parameter* part of Z. Pre-fault data pins down loading, which is the incremental-quantity idea. This removes out-of-zone scenarios whose Δm is large, but not the matched ones.
  - (ii) If the 0.01 pu instrument error is largely **systematic** (CT/VT ratio or phase bias that is constant during the fault), it cancels in the difference `y(δ₂) − y(δ₁)`. Only the tiny relative error on the incremental quantity remains. Reversing the sign of δ (`δ₁ = −δ₂`) also doubles the swing `Δδ = 2ρ_max`.

  Whether (ii) applies depends entirely on the error model. It is worth stating explicitly in the report.
- **The time budget is a practical obstacle.** Zone 1 must trip in about 1–2 cycles, which rules out online MIQP. Only an explicit, table-lookup two-stage law would be conceivable.

---

## Paper 3 — Nikoukhah 1998: the origin of guaranteed active detection

**Citation.** R. Nikoukhah, "Guaranteed active failure detection and isolation for linear dynamical systems," *Automatica* 34(11):1345–1358, 1998.

### Problem class

- **Dynamics.** Discrete time and linear. The system matrices may depend on the test signal `v(k)`, so the system is effectively time-varying and a test may even change its structure (eqs. 25–26, p.1349).
- **Uncertainty.** Perturbations ν and measured inputs u obey **linear inequality constraints**, i.e. **polyhedral** pointwise bounds (eqs. 27–28). No stochastic model is used.
- **Models.** A normal model and one or more failed models, each possibly of a different dimension.
- **Test signal.** Open loop over a finite horizon N.
- **Three problems (p.1346):**
  - (A) Test whether a given v makes the normal and failed behavior sets disjoint.
  - (B) Build the online decision rule.
  - (C) Design v. This is solved only when v enters **linearly**: constant A–D matrices with v entering through affine offsets `Kv`, `Jv` (eqs. 61–62, p.1353).

### Central results

The paper builds a small algebra of constraint primitives (§2, pp.1346–48): reduction, combination (∧), mutation, and extraction by projection with Fourier–Motzkin. It proves the recursive filter results Theorem 9 and Theorem 10.

- **Definition 11 and Theorem 12 (eqs. 37–39, p.1351).** The normal and failed constraint sets are mutually exclusive for all admissible input–output data exactly when a recursively built constraint `D_N` is inconsistent. The recursion may stop early, which gives a shorter test.
- **Lemma 14 (p.1351).** The set of differences `T = S − S̄` of consistent data (normal minus failed) is a convex polyhedron. S and S̄ are disjoint exactly when `0 ∉ T`.
  - This is the polyhedral forerunner of Scott's `Ñũ ∉ Z̃`.
- **Lemma 15 (eqs. 42–48, pp.1351–52).** Any row vector p with `p·d > 0` for all d in T yields a threshold ν with the two sets on opposite sides of the hyperplane `p·h = ν`. The online test (eq. 60, p.1353) is then **one linear inequality on the stacked (u, y) record**.
  - ν comes from two LPs (eqs. 99–101).
- **Theorem 18 (eq. 65, p.1354).**
  - Let G be the projection onto v-space of the joint constraint "both models consistent".
  - A separating test signal exists exactly when G is a real constraint, i.e. not the whole space.
  - The **non-separating signals form the convex polyhedron domain(G)**, and every v outside it is a proper test signal.
  - The recursion (66)–(67) finds the smallest horizon N.
- **Lemma 19 (eqs. 71–72, p.1354).** Add a priori signal constraints H, such as amplitude bounds `|v(j)| ≤ b_j` (eq. 68) or an ℓ₁ budget (eq. 69). Then no admissible separating signal exists exactly when `domain(H) ⊆ domain(G)`.
  - **This is the cleanest published statement of "no admissible input separates".**
- **Lemmas 21–23 (pp.1357–58): one-sided approximations.** Replace exact reduction by a "sub-reduction", i.e. drop some inequalities to get an outer approximation. Validity is preserved in one direction only: the method may reject a valid test signal but never accepts an invalid one.

### Scaling

The paper gives no explicit formula. Monotonicity is immediate: larger perturbation polyhedra give a larger domain(G) and hence a longer or larger required test signal. Identical responses to v leave domain(G) as the whole space.

### Design and computational cost

- Everything offline uses LP and polyhedral projection. Fourier–Motzkin elimination can blow up the number of inequalities.
- The online test is a single inner product.
- The worked example never exceeded 15 variables and inequalities (p.1357).
- Scott (2014, p.1583) later remarks that this projection becomes intractable once `N(n_y + n_u)` exceeds about 10.

### Example and numbers (pp.1354–57)

- **System.** A gas chamber with an emergency relief valve that must be tested periodically. The inflow is bounded, the outflow is proportional to a pressure difference, and the valve flow is proportional to chamber pressure. The pressure sensor has a bounded error. A measurement is taken only when `v = 0`; `v = 1` commands the valve open.
- **Parameters.** The extracted numbers are 12.5, 20, 1, 3, 10 and `rTτ/V = 0.1`. The Greek symbols were lost in extraction, so the mapping of these numbers to specific parameters is uncertain.
- **Results.**
  - `v = [0,1,0]` does not separate: `T(0,0)` is consistent (eq. 94).
  - `v = [0,1,1,0]` does not separate (eq. 96).
  - `v = [0,1,1,1,0]` separates (eq. 97). The decision rule is `−197.65·y(0) + 802.35·y(4)` compared with ν, for any ν in (1464.05, 1519.58).
- **Lesson.** Holding the excitation longer lets the pressure difference *accumulate* through the dynamics until it exceeds the sensor-error bound.

### Relevance to us: what Nikoukhah adds historically

1. He is the origin of *guaranteed* set-membership AFD and of the A/B/C decomposition that Scott, Raimondo, Xu and Taylor all follow.
2. The online decision is a **single hyperplane in measurement space**, which in relay terms is a straight-line characteristic. This connects directly to Taylor's Farkas/duality view and to his geometry paper: a separation certificate *is* a linear discriminant.
3. Checking (problems A and B) allows the test signal to enter *nonlinearly*; only design (problem C) needs linearity. For us, that means B1's check at a fixed δ is legitimate even with limiter switching, as long as the model is linear in the uncertainties for that fixed δ. Only the design over δ is hard, and gridding a two-dimensional δ is an accepted way to do it.
4. **Lemma 19** is the formal version of the question "can any δ within the current limit work?".
5. **Lemma 23's one-sidedness** tells us how to defend a *negative* result. Outer approximations of the uncertainty sets can never prove inseparability. Exhibiting real, overlapping scenario pairs can, because they are witnesses. B1's grid of genuine scenarios therefore makes its "not separable" verdicts sound, at least at the sampled δ values. Its "separable" verdicts could be optimistic between grid points.
6. The dynamic example contrasts with ours. A static phasor model has **no integrator to accumulate the signature**: the per-unit-δ difference N is fixed by the network, so only |δ| can be increased, and the current limit caps it.

---

## Paper 4 — Xu 2023: minimal detectable and isolable faults

**Citation.** F. Xu, "Minimal detectable and isolable faults of active fault diagnosis," *IEEE Trans. Automatic Control* 68(2):1138–1145, Feb. 2023. doi:10.1109/TAC.2022.3148305.

### Problem class

- **Dynamics.** Discrete-time LTI (eq. 2, p.1139):
  - `x_{k+1} = A x_k + B G u_k + E ω_k`
  - `y_k = C x_k + F η_k`
  - A is Schur (Assumption II.1). Only single faults are considered (II.2).
- **Faults.** **Multiplicative actuator faults**: `G = diag(g_i)`, with `g_i = 1` healthy and `0 ≤ g_i < 1` faulty. The fault size is `f_i = 1 − g_i`.
- **Bounds.**
  - The input is bounded by a box `|u| ≤ ū` (II.3). *The input bound is the constraint.*
  - Process disturbance ω and measurement noise η are bounded by boxes (II.4), rewritten as zonotopes.
- **Input.** Open-loop, N steps.
- **Uncertainty sets.** Steady-state output sets built from **minimal robust positively invariant (mRPI)** sets (eqs. 12–13, p.1140), approximated by an RPI set.
- **Separation instant.** Separation is imposed at **one time instant k+N** (eq. 17). This is like Scott's terminal-measurement method with L = 0.

### Central results

- **Transformation (eqs. 7–9, p.1139).**
  - The fault is rewritten as an extra input `ũ_i = −f_i·u_i`, entering through `b_i`, the i-th column of B.
  - The augmented input `v = [u; ũ]` lies in the set T. T is a product of boxes with a sign coupling: `sgn(v_i) = −sgn(v_{n_u+i})`.
  - **So the fault's signature is proportional to the input**; faults and inputs are coupled.
- **Structure (eq. 11).** As in Scott, inputs and faults move only the *centers* of the state and output sets. The shapes are fixed by the initial, disturbance and noise sets.
- **Proposition III.1 (eq. 18, p.1140).** The output sets of modes i and j are disjoint at time k+N if and only if `Γ_ij·v ∉ Z_ij = ⟨h_ij, H_ij⟩`, where:
  - `Γ_ij = −C(B̄_i − B̄_j)` is the difference of the N-step input maps;
  - `h_ij = CA^N(x_i^c − x_j^c)` is the difference of the centers;
  - `H_ij = [C·H_X̃i∞, C·H_X̃j∞, F·H_η, F·H_η]`.
  - **The noise generator appears twice**, which confirms the 2ε count used in these notes.
  - All pairs must hold together (eq. 19).
- **Fault metric (eqs. 20–21, p.1140).** `Φ(v) = ‖ũ‖²/‖u‖² = Σ f_i² u_i² / Σ u_i²`. It is an input-weighted mean-square fault size, and Remark III.2 stresses that the metric is a modelling choice.
- **MDI problem (eq. 23, p.1141).** `min_{v∈T} Φ(v)` subject to (19).
  - The origin must be infeasible: with zero input and common initial sets, all modes' sets coincide.
- **Meaning of the result.** Φ* is the smallest input-weighted fault-to-input ratio for which *some* admissible input separates all modes within N steps. Any smaller ratio cannot be isolated. The faults are computed as `f*_i = |ũ*_i / u*_i|`.
- **Maximal isolable faults (eq. 38, p.1143).** Faults are guaranteed isolable only inside the interval `[Φ(v*), Φ(v*_max)]`. Even that interval is *necessary, not sufficient*: the isolable set may be **disconnected** (§III-D, p.1143), and footnote 3 on p.1144 notes that faults not elementwise larger than f* may still be isolable.
- **Other caveat.** The MDI depends on the horizon N.

### Design and computational cost

- **Binary encodings.**
  - The sign coupling in T is encoded with binaries (Proposition III.2, eq. 24).
  - Separation uses Scott's LP margin (Lemma III.1 = Scott Lemma 4), its KKT conditions (26) and big-M binaries (27)–(28).
  - The result is a two-layer **mixed-integer quadratic *fractional* program (MIQFP)**, eq. (29).
- **Solution method.**
  - Each binary pattern t gives a convex piece `S_t` (eqs. 30–31).
  - The fractional objective is handled by **Dinkelbach's** parametric method (eq. 32). The auxiliary function `M(γ) = min J₁ − γJ₂` is concave, strictly decreasing and has a unique root, with `γ* ∈ [0, 1]` (Proposition III.3).
  - γ* is found by bisection (Algorithm 1, p.1142).
  - Each `M(γ)` is an indefinite QP, solved by **branch-and-bound** on rectangular relaxations (eqs. 34–37, method of Phong, An and Tao).
- **Cost.** No computation times are reported. Enumerating binary patterns is exponential in the worst case.

### Example and numbers (pp.1143–44)

- **System.** Linearized two-tank system: 2 states, 3 actuators (pump and two valves), unit input box, `W = ⟨0, 10⁻⁵⟩`, `V = 10⁻⁵·I`.
- **RPI set.** 200 iterations from `0.05·I`. The output-set generator matrix, reduced to 4 columns, is `[0.0161 0.0041 0.0012 0; 0.0081 0.0031 0 0.0004]`.
- **Result.**
  - `N* = 2`, and the optimal input is `u* = [1 1 1; 1 1 1]`: **every input sits at its bound**.
  - MDI faults `f* = [0.491 0.501; 0.417 0.426; 0.785 0.801]`, with `Φ(v*) = 0.3508`. I checked this equals the mean of f*².
  - Maximal isolable faults are all 1.
  - 100 random faults drawn between f* and the maximum were all isolated within 2 steps. One example with `Φ = 0.6226` was isolated using a minimum-energy input.

### Relevance to us: minimal isolable fault for in-zone vs just-beyond

- **Our structure matches Xu's closely.** The two hypotheses differ in *how δ enters*: `B_in(θ)` vs `B_out(θ)`. That is Xu's multiplicative actuator-fault structure `B·G_i`, not Scott's additive one.
- **The "fault size" is the distance to the zone boundary.** For the matched pair, `Δm ≈ 0`, which puts us exactly in Xu's setting where zero input cannot isolate. The fault size becomes the location gap `Δℓ` between the in-zone fault and the remote bus: 15 % of the line, about 0.3–0.6 Ω.
- **First-order signature.** `N ≈ (∂B/∂ℓ)·Δℓ`, with δ playing the role of the input bounded by the current limit.
- **Define a "minimal isolable reach margin"** [my adaptation]:
  - `Δℓ_min(ρ_max, ε)` = the smallest distance inside the remote bus at which every in-zone scenario is guaranteed separable from out-of-zone faults using some `|δ| ≤ ρ_max`.
  - First order, matched pairs: `Δℓ_min ≈ 2ε / (ρ_max · max_k |∂B_k/∂ℓ|)`.
- **Illustrative numbers from B1.** This is my linear extrapolation, not a result.
  - `|N|` of 0.0008–0.024 at `Δℓ = 0.15` gives `|∂B/∂ℓ|` of about 0.005–0.16 per (pu line · pu δ).
  - With `ρ_max = 1.2` pu and `2ε = 0.02`:
    - best scenario: `Δℓ_min ≈ 0.10` (10 % of the line, inside the 15 % margin);
    - worst scenario: about 3 (impossible).
  - **So δ can "buy back" part of the zone-1 underreach margin only in the most favorable scenarios.** This matches B1's modest gain of 8–13 points at 1.2 pu.
- **Xu's optimal input lies at the input bound.** That matches Scott's vertex property and says our minimum isolable margin should be evaluated on the current-limit circle.
- **Xu's caveats transfer to us.**
  - The isolable set can be disconnected.
  - "Larger fault ⇒ isolable" is not guaranteed.
  - So B1 should report separability per scenario (a curve over location and R_f), not assume monotonicity in the distance to the boundary.

---

## Paper 5 — Sandia SAND2020-0265: IBR negative-sequence injection and relays (not theory)

**Citation.** M. Behnke, G. Custer, E. Farantatos, N. Fischer, R. Guttromson, A. Isaacs, R. Majumder, S. Pant, M. Patel, R. Quint, V. R. Konala, I. Voloh, "Impact of Inverter-Based Resource Negative-Sequence Current Injection on Transmission System Protection," Sandia National Laboratories, SAND2020-0265, Jan. 2020. The PDF has 191 pages, most of them trace appendices. The industry team included SEL, GE Multilin, EPRI, NERC, Southern Co. and four IBR manufacturers.

### (a) Study set-up

- **Test system.** A 4-bus, 230 kV system in PSCAD/EMTDC.
  - One 100 MW IBR on a 34.5 kV collector with a 230/0.6/34.5 kV POI transformer (70 MVA, 9 %).
  - Frequency-dependent lines: TL12 100 mi, TL13 60 mi, TL23 40 mi.
  - Source behind Bus 1: 5,290 MVA, `Z1 = Z2 = 10 Ω`, `Z0 = 30 Ω`. Source behind Bus 2: 1,763 MVA, `Z1 = Z2 = 30 Ω`, `Z0 = 90 Ω`.
  - Short-circuit ratio 5.5 at the MV bus.
- **IBR models.** Four manufacturers' EMT models **built from their actual control code** (PV, Type 3 and Type 4 wind), scaled to 100 MW.
- **Scenarios.** 48 per manufacturer, 192 in total:
  - fault types LG, LLG, LLLG and LL;
  - fault resistance 0 or 5 Ω;
  - several fault locations, with or without prior outages;
  - 5-cycle faults, ideal CTs and VTs, no staggered tripping.
- **Relay tests.** Eight scenarios per manufacturer went to relay testing: four with conventional sources, and four in which a prior outage leaves the **IBR as the only source behind the relay**. They were played back as COMTRADE into two relay vendors' commercial relays, set to standard practice.
- **Relay settings (secondary Ω).**
  - Mho `Z1 = 2.57∠83°`, `Z2 = 3.85∠83°` (pilot), `Z3` reverse `1.6∠83°`. By my arithmetic Z1 ≈ 80 % and Z2 ≈ 120 % of the line.
  - Zero-sequence compensation `k0 = 0.661∠−14°`.
  - 32G: `3I0 = 0.5 A`. 32Q: `3I2 = 0.25 A` (0.05·In), `Z2F = −0.3 Ω`, `Z2R = 0.3 Ω`.

### (b) Findings on 32Q / negative-sequence directional and fault-type selection

- **Overall.** 16 of 32 tests were problematic, meaning at least one relay misbehaved. All of them were in the IBR-only cases; the cases with conventional sources all operated correctly.
- **Low negative-sequence current.** The IBR's I2 was always much lower than a conventional source's, and it varied by manufacturer *and* by scenario. The 67Q/32Q elements often did **not pick up** because I2 was too low. Setting them more sensitively risks security.
- **Loss of coherency.** The frequency of the IBR's current differed from the grid-set voltage frequency. The I2 angle therefore rotated continuously relative to V2 (Figs 3-3 and 3-4), which **made negative-sequence directional decisions unreliable**.
  - For an AB fault, both relays declared a *reverse* fault: R32P and reverse Z3P for about 4 cycles, with forward Z2P only after about 5 cycles.
  - An LLLG case showed similar direction errors.
- **Faulted-phase selection was inconsistent**, for example on an ABG fault (Fig. 3-2), because the I0–I2 relationship was unpredictable.
- **Slow response.** The IBRs needed 2 cycles or more to settle their I1 and I2.
- **Zero-sequence still works.** Zero-sequence (32G/67G) elements worked, because the POI transformer supplies the I0 path from the grid.
- **Overvoltages** came from islanding and from harmonic instability in one model. Whether the lack of I2 causes unfaulted-phase overvoltage was left open.
- **Table 3-2 I2 values.** The table lists a min–max I2 range per scenario of roughly 0–200. The units are illegible in the extraction; primary amperes against a rating of about 251 A is plausible.

### (c) Recommendations on negative-sequence injection

1. **Standardize IBR response to unbalanced faults**, since protection engineers cannot routinely run EMT studies.
2. **Require I2 injection** with a controlled phase relationship: reactive, **I2 leading V2 by about 90°**, as in German VDE-AR-N 4120/4130, where I2 is proportional to the change in V2. The *frequency* of the injected current must also be controlled so that it stays coherent with the voltage.
3. **Mind the current limit.** The phasor sum of I1 load current, I1 reactive current and I2 reactive current is capped at the rating, so I2 stays small and must not starve I1. A higher transient rating is possible but costly.
4. **Use zero-sequence elements** where a grounded transformer provides the path.
5. **Further study:** staggered tripping, mutual coupling, single-pole tripping, series faults, out-of-section faults, series compensation.

### Relevance to us

- **Direction vs reach.** Sandia's motivation for I2 injection is *direction and fault-type* discrimination, not *reach*.
  - **[my inference]** For direction, the V2/I2 relation seen by 32Q flips sign between a forward fault (−Z2 of the source behind) and a reverse fault (+Z2 of line plus remote). The differential sensitivity N is therefore of the order of a full impedance: large.
  - For reach at 85 % vs 100 %, the difference is only the 15 % line segment, further diluted by the fault's coupling of the sequence networks: small N.
  - So, by Scott's Theorem 3, an auxiliary signal is a **direction and fault-type tool, not a reach tool**. This is a clean way to position B1.
- **Magnitudes.** The 32Q pickup of `3I2 = 0.25 A` secondary is about 17 A primary I2, **≈ 0.07 pu** of the 100 MW plant's current. That is my arithmetic, assuming about 100 MVA at 230 kV. Direction supervision needs only that small sensitivity threshold, whereas B1's reach separation needs at least 0.83 pu even in the best case.
- **Shared current limit.** Sandia's current-limit sharing (item 3 above) is exactly the nonlinearity B1 sees as limiter regime switching. Pushing δ toward the limit reduces I1 and changes regime.

---

## Synthesis

### Why a bounded auxiliary signal cannot separate hypotheses with nearly identical δ-sensitivity

1. **The signal only moves the sets.** In every framework here, the set of measurements consistent with a hypothesis is a fixed-shape set whose position is affine in the auxiliary input. This holds for Scott's zonotopes (p.1582), Raimondo's constrained zonotopes (eqs. 12–13), Xu's mRPI sets (eq. 11), Nikoukhah's polyhedra, and Taylor & Domínguez-García with additive noise. Its shape is fixed by the uncertainty: fault location, R_f, loading and instrument error.
2. **Only the differential response counts.** The response that is common to both hypotheses moves both sets together and cannot separate them. Separation happens exactly when `N·δ ∉ Z(i,j)` (Scott Thm 3; Raimondo Thm 1 and Cor. 2; Xu Prop. III.1; Nikoukhah Lemma 14 and Thm 18). Here `N = B_i − B_j` and `Z(i,j) = Z_i ⊕ (−Z_j)` is the difference body. In B1, δ moves the in-zone and remote-bus measurements "almost equally": nearly all of the injected current is common-mode.
3. **The difference body contains the instrument error twice.** It has half-width `2ε = 0.02` pu per channel (Xu eq. 18 shows the two noise blocks explicitly), plus the spread from R_f, loading and location. Since `‖Nδ‖ ≤ |N||δ|`, separation is impossible when `|δ| < (2ε − |Δm|)/|N|` [my bound; same form as Taylor & Domínguez-García 2025 Thm 1, p.5526, `‖θ‖ < (1−ζ)/χ`].
   - For the matched 85 % / remote-bus pair (Δm ≈ 0) with `|N|` of 0.0008–0.024, this means `|δ| ≳ 0.83` pu at best and up to about 25 pu.
   - This exceeds or approaches the negative-sequence share of a current-limited inverter. Sandia confirms that share is small because it competes with I1.
4. **As N → 0 no input helps.** The required magnitude tends to infinity (Scott p.1583; Raimondo p.110; Taylor & Domínguez-García Cor. 2).
5. **With a hard input bound, inseparability is a containment.** It is exactly `N·U ⊆ Z`: the image of the current-limit disk lies inside the difference body (Nikoukhah Lemma 19). The separation margin is convex in δ (Scott §5.1), so the check reduces to the boundary circle. Xu's optimum likewise sits at the input bound.
6. **Neither repetition nor feedback beats bounded noise.**
   - With pointwise-bounded, independent errors, a fixed scenario pair is separated by a sequence of shots only if one shot separates it [my derivation]. Worst-case noise does not average out.
   - A static phasor map has no dynamics to accumulate the signature, unlike Nikoukhah's valve test, which needed a longer excitation.
   - Closed-loop design (Raimondo Thm 5) keeps the open-loop worst case; it only shrinks the parameter part of Z.
   - The one escape is a *systematic* (bias-type) instrument error, which cancels in incremental measurements.
7. **Xu's minimal-isolable-fault view.** The in-zone vs just-beyond "fault" is a location difference of 15 % of a 2–4 Ω line. Its signature scales as `(∂B/∂ℓ)·Δℓ·δ`. With `ρ_max ≤ 1.2` pu and `ε = 0.01`, this 15 % gap is below the minimal isolable gap for most scenarios. Only those with the largest ∂B/∂ℓ, or with a passive difference `|Δm|` already near 2ε, become separable. That is exactly the B1 pattern of 2–4 points at 0.4 pu and 8–13 points at 1.2 pu.
8. **Positioning.** Negative-sequence injection is well suited to hypotheses whose δ-response differs *qualitatively*: forward vs reverse, fault type. This is what Sandia and IEEE 2800 target and why 32Q needs only about 0.07 pu of I2. It is poorly suited to hypotheses that differ *quantitatively by a small fraction*, such as the zone-1 reach boundary. B1's negative result is a predicted consequence of the theory, not an artefact of the grid.

**Two caveats.**
- **The multiplicative case can be worse.** B1's δ-gain depends on R_f and location, so the sets inflate as |δ| grows. If some pair `(θ_i, θ_j)` has both `N·d ≈ 0` in a direction d and `|Δm| ≤ 2ε`, then no magnitude in that direction ever separates [my derivation].
- **The limiter makes the map only piecewise affine.** All the results above then hold within each regime.

### Formulas and tests we could implement (replacing or augmenting the δ grid)

- **T1: exact pairwise minimum injection** [my derivation, closed form; for box noise and a response linear in δ within a regime].
  - Fix a pair `(θ_i, θ_j)`, with channel differences `Δm_k` and complex channel sensitivities `N_k` (for real channels, N_k is a 2-vector).
  - `ρ*_pair = min_k (2ε − |Δm_k|)⁺ / |N_k|`. It is zero if some `|Δm_k| > 2ε` (already separated passively).
  - Proof sketch: `max_{|δ|≤ρ} |Δm_k + N_k δ| = |Δm_k| + ρ|N_k|`.
- **T2: exact per-scenario minimum injection via a 1-D angle sweep.**
  - For direction `d = e^{jφ}` and pair q, the exit radius of the pair's "forbidden polygon" `{δ : ‖Δm + Nδ‖∞ ≤ 2ε}` is `t̄_q(φ) = min_k (2ε − sgn(a_k)·Δm_k)/|a_k|`, with `a_k = N_k·d`.
  - Then `ρ*(θ_i) = min_φ max_{θ_j} t̄(θ_i, θ_j, φ)`.
  - This is valid when every relevant pair polygon contains δ = 0. The union is then star-shaped, so separation along each ray is monotone in |δ|.
  - The separable fraction at any current limit is simply the **empirical CDF of ρ*(θ_i)**. B1's "% separable vs δ_max" curve comes out at every δ_max at once, with no magnitude grid.
- **T3: a quick certificate of inseparability.**
  - `ρ_LB(θ_i) = max_{θ_j} min_k (2ε − |Δm_k|)/|N_k| ≥` the cruder `(2ε − ‖Δm‖∞)/max_k|N_k|` for the matched pair.
  - If `ρ_LB > ρ_max`, the scenario is proven non-separable by any admissible δ, open or closed loop. This rests on witnesses (sampled real pairs), so it is sound.
- **T4: Scott's LP margin (eq. 20) when θ-sets are convexified into zonotopes.** `δ^[q](δ) = min{s : Nδ = Gξ + c, ‖ξ‖∞ ≤ 1 + s}`. It gives a scalar margin that is convex in δ, useful for margin maps and sensitivity. Remember that zonotope *outer* approximations can only certify separability, never inseparability.
- **T5: Xu-style minimal isolable reach margin.** Compute `Δℓ_min(ρ_max, ε)` = the smallest distance inside the remote bus at which every in-zone scenario has `ρ* ≤ ρ_max`. Plot it against ρ_max for ε of 0.005, 0.01 and 0.02, and compare with the 15–20 % zone-1 margin.
- **T6: Taylor & Domínguez-García 2025 Thm 1 bound (p.5526).** Cast the linearized model into their additive form `[Θ_k, X_k][θ; x] = h_k + λ_k`, with Euclidean-ball noise and no constraints. Compute χ and ζ from the matrices; `‖θ‖ < (1−ζ)/χ` means no separation. This is a citable cross-check of T3 in Taylor's own notation.
- **T7: common-mode vs differential decomposition per scenario.** Report `|(B_in + B_out)/2|` against `|B_in − B_out|`. The figure of merit of an injection strategy is `|N|/(2ε)`: pu of separation per pu of current, relative to the noise. The required current is its inverse.
- **T8: linearity and regime check.**
  - Estimate B by finite differences at several |δ| and phase angles.
  - Tag the limiter regime, and apply T1–T3 per regime; for exact nonlinear behaviour, do 1-D root-finding along each ray in T2.
  - Alternatively, treat regimes as separate models: Scott's switched-model formalism, with an extra binary per regime in the MIQP.
- **T9: incremental two-shot variant.** Model the error as bias plus random: `v = b + r`, with b constant during the fault. The two-shot difference `y(δ) − y(−δ) = 2Nδ + (r₁ − r₂)` then removes both the θ-offset and the bias. Evaluate T1 with ε replaced by the random-part bound only. This is the only route the theory leaves open for rescuing reach discrimination.

### Uncertain points in these notes

- The Nikoukhah example parameters: the Greek symbols were garbled, so which of 12.5, 20, 1, 3, 10 is which is uncertain. The hyperplane side conventions in eqs. (44)–(45) and (60) were also garbled; I stated only the substance.
- Raimondo's objective index (whether the sum starts at ℓ=0 or ℓ=1) and the sign in the generator block of eq. (18); the sign is immaterial.
- The units of Sandia's Table 3-2 I2 column are illegible.
- The Sandia "≈ 0.07 pu I2 pickup" and "Z1 ≈ 80 % / Z2 ≈ 120 %" figures are my arithmetic, not stated in the report.
- My reading of B1's "0.0008–0.024 pu per pu δ" as the per-channel `|N_k|`, and whether B1 counted the 0.01 pu box once or twice (this changes every threshold by a factor of 2).
- Every item marked "[my derivation]" or "[my inference]" is not stated in the papers, although each follows from their theorems: T1–T3, the multi-shot result, the multiplicative-case condition, the Δℓ_min extrapolation, and the direction-vs-reach N argument.
