# Notes: the 2025 TAC paper and the Baeckeland current-limiting GFM model

Read in full, 17 Sep 2026. Two papers, both paywalled IEEE journal articles, both previously in
the §F gap table of [`papers/README.md`](../README.md) and now held:

- **TAC25** — Taylor & Domínguez-García, *Active fault detection in static systems*, IEEE Trans.
  Automatic Control **70**(8):5523–5529, Aug 2025. DOI 10.1109/TAC.2024.3510612. (7 pp.)
- **BYS26** — Baeckeland, Yang & Seo, *A unified model of current-limiting grid-forming inverters
  for large-signal analysis*, IEEE Trans. Power Systems **41**(1):198–213, Jan 2026.
  DOI 10.1109/TPWRS.2025.3587224. (16 pp.)

The question this note answers is the one posed at the end of the brief: **do either of these
change the design-tool plan in [`REVIEW.md`](../../REVIEW.md) §10 item 2?**

> **Short answer: TAC25 changes it substantially — four of the six sub-items are already solved
> in it, and one (the global solver) turns out to be trivial for our problem size. BYS26 does not
> change the plan; it supplies one clean parameter for a dimension the plan already asks for, and
> it is the model WP2 needs.**

---

# Part 1 — TAC25 against the 2023 conference version

## 1.1 What is actually new

The 2023 conference paper (`Taylor_2023_Auxiliary_Signal_Based_Distance_Protection_IBR.pdf`) is
described in TAC25's own reference list as "our preliminary work [3]". The differences are not
presentational:

| | 2023 conference | TAC25 |
|---|---|---|
| Uncertainty | additive only (λ, ‖λ‖ < 1) | additive **and multiplicative** (ξ, entering as G_k(ξ_k) on the system matrices) |
| Constraints | none | quadratic inequalities x⊤Q x + A⊤x + b ≤ 0, e.g. an inverter current limit |
| Offsets | — | constant offsets h_k, b_k, without which θ can never be zero |
| Reformulation | duality → bilinear program | semidefinite relaxation of the inner problem, **then** duality → bilinear **semidefinite** program |
| Guarantee | none stated | relaxation is one-sided: σ̂ ≤ σ, so σ̂ ≥ 1 is **sufficient** for separation |
| Necessary condition | — | **Theorem 1**: an analytical lower bound on ‖θ‖ from the system matrices alone |
| Solution method | convex–concave procedure | CCP, generic NLP, **or grid the θ-space if dim θ ≲ 3** |
| Models | pairs | all pairs S ⊆ M, |S| = 2, over M = {0, 1, …, M} |

## 1.2 The four things it fixes, item by item against §10 item 2

REVIEW.md §10 item 2 asks for a design tool with: (i) a sound outer source set (H6), (ii) noise as
a box tied to CT/VT class errors (H2), (iii) a margin (H14), (iv) |i⁺| + |i⁻| ≤ I_max worst case
over the i⁺ set (H5), (v) a global solver (H15), then continuous (m, R_f) validation (H13).

**(i) Sound uncertainty set — solved, and our linearisation was solving the wrong problem.**
H6 found the repo's angle uncertainty unsound: the true set reaches 0.085–0.276 pu outside the
linearised box. TAC25 does not linearise. Uncertain impedances enter **multiplicatively**, as in
its own worked example (§VI.B.1):

&nbsp;&nbsp;&nbsp;&nbsp;ē⁻ = z̄⁻(1 + 0.1 ξ_z,0) θ̄,&nbsp;&nbsp;&nbsp;&nbsp;ē⁻ = z̄_f (1 + ξ_z,1) θ̄

with |ξ| ≤ 1. A complex multiplicative factor (1 + ρξ) is exactly "this impedance is uncertain in
magnitude *and* angle", expressed without any small-angle approximation. The bilinearity ξ·x that
this creates is what the semidefinite relaxation of §III exists to handle. **H6 is not a bug to be
patched in our formulation; it is an artefact of using the 2023 formulation, which has no
mechanism for uncertain coefficients.**

**(iii) Margin — solved by construction.** In TAC25 the noise balls are normalised to ‖λ_k‖ < 1
and separation is σ_S(θ) ≥ 1 (Definition 2). A margin is then one scalar: require σ_S(θ) ≥ 1 + ρ.
H14's finding — that the published optima have 0.45–1.25 % of eps as margin — is the statement
that we were solving with ρ = 0 and no way to ask for more. In TAC25's normalisation, "10 %
headroom" is literally σ ≥ 1.1.

**(iv) Current limit — solved, and *backwards from what we assumed*.** This is the most
interesting single finding in the paper for us. TAC25 §II:

> "the constraints make the detection problem easier by shrinking the range of possible
> observations, potentially mitigating the worst realizations"

and §II again: "the constraints in (1b) restrict the values x can take on in P⁰_S, increasing its
objective. The presence of such constraints can, therefore, only increase σ_S(θ), **shrinking the
size of auxiliary signal needed** to attain separation."

H5 imposed ‖i⁺‖ ≤ 1.2 pu as an **outer feasibility test applied after** designing δ, and concluded
that "every preset needing δ > 0 is infeasible at 1.2 pu". TAC25 puts the same constraint
**inside** the design problem, where it is an *ally*: it removes measurements the relay would
otherwise have to distinguish. Its own §VI.B.1 demonstrates the effect at full strength — with both
the positive-sequence voltage constraint and the current-magnitude constraint present, **no
auxiliary signal is needed at all**; drop either one and a signal becomes necessary.

**H5's conclusion is therefore not wrong, but it is an upper bound on the problem, not the
answer.** The honest restatement is: *"δ > 0 designed without the current limit is infeasible once
the limit is imposed"*, which is a statement about our procedure. Whether a feasible δ exists when
the limit is in the model from the start is **an open question that has not been asked**, and it is
now cheap to ask.

**(v) Global solver — solved, for our problem, by inspection.** TAC25 §IV.B:

> "If the auxiliary signal is under three or so dimensions, it is viable to grid the space and
> evaluate Ω_S(θ) for all values of θ"

Our δ is a single complex number: **dim θ = 2**. H15 found the alternating scheme stops at local
optima (0.5141 vs the true 0.5040). Gridding the δ-plane and testing SDP feasibility of Ω_S(θ) at
each point is globally certified up to the grid resolution, and it is the method the author himself
prescribes at this dimension. H15 dissolves. The repo already grids the δ-plane in
`aux_signal_toy.py` — it just grids the *wrong test* (the LP separation of the linearised problem)
instead of Ω_S(θ).

## 1.3 Theorem 1 — the part with no analogue in anything we have built

> **CORRECTED 17 Sep 2026, after implementing it.** The optimism below is wrong on the main point.
> Theorem 1 **does not** turn H1 into a proof, and the bound is **vacuous** on our problem. It needs
> Euclidean-ball uncertainty; `aux_model` bounds each component independently. Only the ball
> *inscribed* in that box is a sound lower bound for us (a smaller uncertainty set is easier to
> separate), and on the inscribed ball every pair is already separated at δ = 0 — ζ ≥ 1 everywhere —
> so the bound is 0.000 at every preset. The ball/box gap is √d = 4 at d = 16 and no
> re-parameterisation removes it. The implementation is verified (Lemma 2's bracket holds against an
> independent solve of P⁰_S), so this is the theorem's hypothesis, not our code.
> Full argument and numbers: [`results/DESIGN.md`](../../results/DESIGN.md) §2.
> The rest of this section is left as written, since the *reasoning* about what such a bound would
> buy is still correct — it simply does not apply here.

For purely additive uncertainty with no constraints, TAC25 §V derives χ and ζ directly from the
system matrices (via Λ_x = X₀ᵀX₀ + X₁ᵀX₁ and Λ_θ = X₀ᵀΘ₀ + X₁ᵀΘ₁) and proves:

&nbsp;&nbsp;&nbsp;&nbsp;**if ‖θ‖ < (1 − ζ)/χ, then θ does not separate S.**

This is a **certified lower bound evaluated in closed form, with no optimisation at all**. Its
consequences for us:

- It answers H1's question — "does any δ ≤ I_max separate the zone problem?" — *without solving the
  zone design problem*. H1 currently rests on a gridded search reported as the agent's result. A
  closed-form necessary condition would make it a proof.
- Corollary 3: if the models differ enough, ζ ≥ 1 and the bound is non-positive, i.e. **no signal
  is needed**. Corollary 2: if the models are identical, χ = ζ = 0 and no signal of any magnitude
  works. These are the two boundary cases the `easy` and `weak_sg_eps12` presets are trying to
  express, obtainable for free.
- Combined with §1.2(v), we would have **both** bounds: a certified floor from Theorem 1 and a
  certified ceiling from any θ feasible for P2. The published 0.5141/0.5040 numbers have neither.

The honest limits, which TAC25 states itself: the bound holds only for additive uncertainty with no
constraints, so it does *not* apply to the constrained, multiplicative formulation we would
actually want; and there is deliberately **no** matching upper bound on ‖θ‖, because "if θ is not
in the right direction, then no magnitude will be sufficient". Magnitude alone never certifies
separation — a point worth remembering every time the project writes "δ = 0.51 pu" as if the
number were the whole answer. It is a magnitude on a direction (−23.2° in our case) and the
direction is doing at least half the work.

## 1.4 What TAC25 does *not* fix

- **(ii) Noise tied to CT/VT class errors.** TAC25 gives the machinery (‖λ‖ < 1 with H_k setting
  the shape, plus multiplicative ξ for ratio errors) but not the numbers. H2's finding stands
  unchanged: the design eps is 111–208× the synthetic phasor noise std. The numbers now come from
  [`E_practitioner_settings.md`](E_practitioner_settings.md) §7 — and they are **larger** than the
  review assumed, not smaller.
- **(vi) Continuous (m, R_f) validation.** H13 is a question about whether the guarantee holds
  between grid points. TAC25's models are indexed by a finite set M; it says nothing about
  continuously parameterised fault families. Refinement or a Lipschitz bound is still ours to do.
- **Multiple relays and multiple injection points** are named as future work in TAC25 §VII. The
  zone problem has one relay, so this does not block us.
- The relaxation may be **loose** when constraints are absent: "if (1b) is not present at all, then
  the eigenvalues of W are unbounded, and the relaxation may be loose" (§III). A feasible θ is
  always safe, but it may be larger than necessary — so a reported δ from P2 is an upper bound.

## 1.5 Verdict on §10 item 2

**The plan changes.** Item 2 currently reads as six pieces of work to be invented. Four of them
(sound source set, margin, current limit, global solver) are **already solved in TAC25**, and one
of them — the current limit — was solved in the opposite direction to the review's assumption.
The rewritten item should be:

> **2. Design tool that deserves the word "guarantee" (S–M, down from M).**
> Re-implement the design problem in the TAC25 formulation rather than extending the 2023 one:
> models M = {normal, in-zone, out-of-zone}; impedance uncertainty as multiplicative (1 + ρξ);
> CT/VT class errors as the additive box (sizes from `E_practitioner_settings.md` §7); the
> current limit and the positive-sequence voltage bound as constraints **inside** (1b), not as an
> outer check; separation at σ ≥ 1 + margin. Solve by gridding the 2-D δ-plane and testing SDP
> feasibility of Ω_S(θ) — globally certified at this dimension. Report Theorem 1's closed-form
> lower bound alongside every δ.
> **Gate:** Taylor 2023 with the correct complex form, stating the printed-matrix discrepancy to
> the author (H16 — see [`docs/notes/taylor_matrix_note.md`](../../docs/notes/taylor_matrix_note.md)).
> **Risk, restated:** the review's risk was "at realistic eps no δ ≤ I_max exists". TAC25 shows
> constraints *shrink* the required δ, so this risk is **weaker than stated** and must be
> re-tested before being reported as a finding.

That last line is the one that matters most. **H1 and H5 are currently the project's most
publishable negative results, and TAC25 gives a principled reason why both might soften once the
constraints are modelled properly. They should be re-derived in the TAC25 formulation before
either is written into a paper.**

---

# Part 2 — BYS26, the current-limiting GFM model

## 2.1 What the model is

BYS26 unifies the two mainstream GFM current limiters — **SatLim** (current-reference saturation
with anti-windup, a.k.a. the circular or magnitude limiter) and **VI-Lim** (threshold virtual
impedance) — into one continuous algebraic model, parameterised by a saturation gain
ρ = min(1, i_max/|I*|) and a threshold function Ψ. Setting σ ≥ i_max recovers SatLim; setting
σ = i_th with 0° < φ_vi < 90° recovers VI-Lim.

The central result is an equivalence. During current limiting, the inverter is a voltage source
behind a **variable output impedance Z_lim**, and the paper shows that the quasi-static power-angle
behaviour is "solely defined by the equivalent current limiter impedance angle, φ_lim". Hence
their notation **Lim_φ**: Lim0 is any limiter with a 0° (purely resistive) equivalent angle,
Lim85 any with 85° (nearly purely inductive), regardless of which of the two mechanisms produced
it. The equivalence is validated numerically, analytically, in full-order EMT, and on hardware.

The behavioural consequence is strong and monotone: **more inductive limiter angle → larger
large-signal stability margin and more reactive support; more resistive → loss of synchronism.**
In their IEEE 14-bus case, Lim10 loses synchronism and the bus voltages collapse; Lim85 recovers.

## 2.2 What it gives WP2 — the model the plan has been asking for

This is the system `docs/PLAN.md` question 1 is about, and BYS26 §V.E specifies it well enough to
rebuild:

- **IEEE 14-bus network, five GFM inverters, 12 constant-impedance loads.** "The load values and
  line parameters are one-to-one translated from the standard IEEE 14-bus benchmark model" — so
  the network data is public; only the inverter models are the authors'.
- **A deliberate mix of primary controllers**: dVOC at buses 1 and 4, droop at 2 and 5, VSM at 3.
  This matters — it is not five copies of one inverter.
- Active-power setpoints per inverter in the range 0.5–0.9 pu.
- **Disturbance: an unbalanced line-to-line fault at the middle of line 3, 100 ms, then cleared.**
  Unbalanced deliberately, "as it presents a more realistic grid disturbance". Controls are moved
  into the stationary reference frame to handle it.
- i_max = 1.2 pu, i_th = 1.1 pu in the device-level studies; the paper's stated hardware range for
  inverter overload is **1.05–1.20 pu**.

For our purposes the 100 ms L-L fault at mid-line with five GFM sources *is* a distance-protection
scenario, and it is the one Taylor's 2026 reachability paper runs on. Asking Prof. Taylor for this
model remains the highest-value request in `docs/PLAN.md`, and the note to add is that we now know
exactly what we are asking for and could specify a replacement from the paper if it is not
available.

## 2.3 What it gives WP1 — one parameter, with an honest caveat

The plan's existing wording (PLAN.md WP1, third bullet) is:

> add the **current-limiter type** as a dimension of the uncertainty set. Measured negative-sequence
> virtual impedance angles are −0.5°, +36.2° and −51.6° for circular, priority-based and
> instantaneous limiters.

BYS26 improves the *structure* of this but does not directly supply the numbers, and the two must
not be conflated:

- **What improves.** "Limiter type" as a categorical dimension is the wrong shape. BYS26 shows the
  types are not distinct behaviours at all — SatLim and VI-Lim with the same φ_lim are
  large-signal equivalent. The right uncertainty dimension is therefore **one continuous scalar,
  φ_lim ∈ [0°, 90°]**, with the limiter's contribution to the source impedance being
  Z_lim∠φ_lim whose magnitude grows with the depth of limiting. That is a single multiplicative
  uncertainty factor of exactly the kind TAC25 §VI.B.1 models — the two papers fit together
  directly.
- **The caveat, and it is important.** BYS26's φ_lim is derived for the **positive-sequence,
  quasi-static, large-signal power-angle** behaviour. It is *not* a negative-sequence fault-response
  model. The paper's unbalanced work is a demonstration (the 14-bus L-L fault) rather than a
  derivation; it never produces a negative-sequence characteristic. The auxiliary signal lives
  entirely in the negative sequence. **So BYS26 parameterises the wrong sequence for our design
  problem.** It tells us how to make the i⁺ set a one-parameter family, which is real progress for
  the current-limit constraint in TAC25 (1b), but the i⁻ behaviour still has to come from
  elsewhere — today from the −0.5° / +36.2° / −51.6° measurements already in `B_problem_statement.md`,
  and in future, if it is adopted, from KFH26's fixed inductive impedance
  (see [`E_practitioner_settings.md`](E_practitioner_settings.md) §9).
- The paper also notes its p(δ′) curves "only capture quasi-static behaviors, and do not capture
  the small-signal response of current limiters" — and our decisions are made at 10–20 ms.

## 2.4 Verdict on §10 item 2

**BYS26 does not change the plan.** §10 item 2's fifth sub-item already asks for "an IEEE 2800-style
negative-sequence response as an uncertainty dimension (limiter types: circular, priority,
instantaneous)". BYS26 refines *how to write that dimension down* — one angle, not three
categories — but the dimension itself was already in the plan, and BYS26 does not supply the
negative-sequence content it needs. The one edit worth making is to replace "limiter types:
circular, priority, instantaneous" with "limiter angle φ_lim ∈ [0°, 90°] (BYS26), with the
negative-sequence response as a separate, still-unsourced dimension".

Where BYS26 *does* change the plan is **§10 item 3** (the inverter-dominated EMT dataset), which
already names "the Baeckeland 14-bus Simulink model" as the grid. Having read the paper, that item
can now be specified concretely — controller mix, setpoints, fault, limiter angles — and the
limiter sweep should be over **φ_lim**, with Lim10 and Lim85 as the two ends the paper shows are
behaviourally distinct.

---

## Combined verdict

| Question | Answer |
|---|---|
| Does TAC25 change §10 item 2? | **Yes, substantially.** Four of six sub-items are solved in it; the current limit is solved in the *opposite* direction to our assumption; the global solver is a 2-D grid. Item 2 should be rewritten as "re-implement in the TAC25 formulation", and drops from M to S–M. |
| Does BYS26 change §10 item 2? | **No.** It sharpens one dimension the plan already has (one angle, not three types) and is the wrong sequence for the design problem. It changes §10 item 3 instead, which it makes concrete. |
| Biggest single consequence | **H1 and H5 must be re-derived before publication.** — **done 17 Sep 2026, and the negative result did not survive.** H5 reverses: the presets are feasible at 0.16–0.26 pu, about half the unconstrained optimum. H1 moves: the feasibility boundary is at eps ≈ 0.12–0.16 pu, not "no δ ≤ 1.5 at eps ≥ 0.01". [`results/DESIGN.md`](../../results/DESIGN.md) §3–4. |
| Cheapest immediate win | ~~Theorem 1's closed-form lower bound~~ — **implemented, and it is vacuous here** ([`results/DESIGN.md`](../../results/DESIGN.md) §2). The actual win was the current limit: moving it inside the problem reversed H5 and halved the required signal. |
