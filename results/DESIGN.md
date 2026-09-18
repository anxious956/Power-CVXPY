# The auxiliary-signal design tool, re-derived in the TAC25 formulation

17 Sep 2026. Code: `src/review/tac25.py`, `tac25_theorem1.py`, `tac25_design.py`, `tac25_map.py`.
Numbers: [`review_wp1/tac25_theorem1.json`](review_wp1/tac25_theorem1.json),
[`review_wp1/tac25_map.json`](review_wp1/tac25_map.json). Nothing here is typed by hand.

This supersedes the design results in [RESULTS.md](RESULTS.md) and the H1 / H5 rows of
[REVIEW.md](../REVIEW.md) §4. The formulation is that of

> J. A. Taylor and A. D. Domínguez-García, *Active fault detection in static systems*,
> IEEE Trans. Automatic Control **70**(8):5523–5529, 2025 — "TAC25" below,
> [`papers/Taylor_2025_Active_Fault_Detection_Static_Systems.pdf`](../papers/Taylor_2025_Active_Fault_Detection_Static_Systems.pdf).

---

## The one-paragraph answer

**An admissible auxiliary signal exists over a usable part of the design space, and the earlier
finding that it does not was an artefact of how the inverter current limit was imposed.** Putting
the limit inside the problem as TAC25 does — an inverter injecting δ cannot simultaneously be
carrying a positive-sequence current above I_max − |δ|, so those realisations leave the uncertainty
set — makes the three presets feasible at roughly **half** the unconstrained signal, where H5's
outer check had declared all of them infeasible. The binding variable is not the current limit but
the **measurement error**: at ε ≤ 0.04 pu no signal is needed at all, at ε = 0.08 pu the required
|δ| is 0.22–0.56 pu depending on the limit, at ε = 0.12 pu the problem is feasible only if the
inverter can be trusted to I_max ≥ 1.3 pu, and **at ε = 0.16 pu no δ separates at any current limit,
including no limit at all** — that last one is a genuine "no admissible δ exists in this regime", and
it is a result, not a failure. The required signal grows monotonically as the limit is relaxed
(0.22 → 0.56 pu as I_max goes 1.1 → 2.1), and this project's own EMT measurement says the limit is
not tight — median |I₁|+|I₂| of 1.07–1.18 pu but p95 ≈ 1.5 and max ≈ 2.1 ([REVIEW.md](../REVIEW.md)
§7 claim 20). **That does not cost the guarantee, and §3.1 measures what it does cost.** Treating
I_max as an uncertain parameter on [1.1, 2.1] and pruning the uncertainty set at the *loosest* bound
keeps the separation guarantee whatever the true limiter does, at **0.56 pu instead of 0.28 at
ε = 0.08** and **1.14 pu at ε = 0.12**, where a hard 1.2 pu limit is infeasible outright. What the
softness actually threatens is not the guarantee but the **injectability**: producing 0.56 pu needs
an inverter with headroom to 1.81 pu, and 1.14 pu needs 2.39 pu, which is past anything measured. So
the honest headline is that the design survives a soft limiter but asks for more current than a
1.2 pu-rated inverter has.

**Two later corrections move the answer further, and in opposite directions.** The scalar ε box is not
an instrument model: replacing it with a structured per-channel set at the same class figures
(§4.1.1) makes δ = 0 separate everything, so the ε = 0.12 boundary does not move, it dissolves. And
closing the inverter's negative-sequence path as IEEE 2800 requires (§4.4) shunts the injected signal
by a factor of 3 to 17 and, under the old scalar box, destroys feasibility outright. Under the
structured set it does not. The instrument model is the stronger of the two effects here, and the
durable finding is the shunting mechanism itself, which holds whichever error model is used.

---

## 1. Gate

Per [REVIEW.md](../REVIEW.md) §10 item 2, no number from the new tool is published until the
replication gate passes.

**Taylor 2023 Fig. 3 (H16) — passes, with the discrepancy stated.** `wp1_taylor2023.py` →
`review_wp1/h16_taylor2023.json`. The exact minimum ‖θ‖ agrees with the closed form to 1.8 × 10⁻⁸.
Against Fig. 3 digitised at ±0.003, the **appendix's printed** M = [[r, −x], [r, x]] gives a maximum
absolute error of **0.0065** and reproduces the flat plateau at 1/(2√2) = 0.3536; the **standard**
complex form M = [[r, −x], [x, r]] peaks at **0.4851** with a maximum error of **0.129**. The
printed form is not a real representation of multiplication by r + jx (singular at x = 0, not a
rotation–scaling), so this is a typesetting slip carried into the figures. The draft note to the
author is [`docs/notes/taylor_matrix_note.md`](../docs/notes/taylor_matrix_note.md).

**The 2025 14-bus example — NOT reproduced, and this gates the scope of every number below.**
It is specified completely enough to build (`docs/PLAN.md`: SGs at buses 1, 3, 5, 14; IBRs at 2, 4,
7, 8, 12 with angles spread over [0, 2π/3]; loads at 6, 10, 11, 13 at 0.1 + j0.01; 20-gon noise
with Σ = 0.1 I; relay at bus 2 on line 2-3; k = 2; r_F = 1; m̲_z = 0.15), but building it is a
separate piece of work, not a variation on the two-bus model: it needs a general multi-bus
sequence-network solver with per-bus source models, the zonotope machinery lifted from 2 to 14
buses, and Minkowski-sum aggregation over the network rather than a single pair of sources. That is
a day or more, and it was not in this session's scope.

**What that means for what follows.** Every number in this document is validated *only* against the
two-bus model and against the known exact zonotope optima of the presets. **None of it is validated
against the paper's own worked example.** Three things in particular cannot be checked without the
14-bus case: whether the required δ magnitudes are "in the same range as the paper's examples"
(claim 6, still UNTESTED), whether the formulation behaves the same when uncertainty is aggregated
by Minkowski sum over many sources rather than two, and whether the current-limit mechanism below
survives multiple injection points. Until it is built, these are results about our model in TAC25's
formulation, not a replication of TAC25.

---

## 2. Theorem 1 does not turn H1 into a proof

`tac25_theorem1.py` → `review_wp1/tac25_theorem1.json`.

The hope ([`papers/notes/F_taylor_tac_and_gfm_model.md`](../papers/notes/F_taylor_tac_and_gfm_model.md)
§1.3, which I wrote last session) was that TAC25's closed-form necessary condition,

  if ‖θ‖ < (1 − ζ)/χ then θ does not separate S,  with χ and ζ from the system matrices alone,

would convert H1 from a gridded search into a proof. **It does not, for a reason specific to the
uncertainty geometry.**

Theorem 1 needs the uncertainty in a Euclidean ball, ‖λ‖ < 1. `aux_model` bounds each component
independently — a box. For H = [G, εI] with d columns, the ball of radius 1 is *inscribed* in the
box and the ball of radius √d *contains* it. Only the inscribed end is a sound lower bound for our
problem, because a smaller uncertainty set is easier to separate:

  L(inscribed) ≤ δ*(inscribed) ≤ δ*(zonotope),  while L(circumscribed) bounds a **harder** problem.

On the inscribed ball, **every one of the 30 pairs has ζ ≥ 1 at every preset** — the models are
already separated at δ = 0 — so the bound is **0.000 everywhere** and carries no information. With
d = 16 the gap is 4×, and no re-parameterisation removes it: a 12-dimensional noise cube of
half-width ε has insphere ε and circumsphere ε√12.

| Preset | ε | exact zonotope optimum | bound, inscribed (sound) | bound, circumscribed (not a bound for us) |
|---|---|---|---|---|
| easy | 0.03 | 0 | 0.000 | 0.000 |
| weak_sg | 0.08 | 0.5040 | **0.000** | 3.322 |
| weak_sg_eps12 | 0.12 | 1.3186 | **0.000** | 5.772 |
| weak_sg_noisy | 0.15 | 0.6908 | **0.000** | 2.360 |
| all_ibr_hard | 0.15 | 0.3863 | **0.000** | 2.813 |

This is a property of the theorem's hypothesis, not of the implementation. Two checks confirm that:
**Lemma 2's bracket ω̂_mean ≤ σ*(θ) ≤ ω̂_max holds against an independent numerical solve of P⁰_S**
for every pair and both geometries, and the gate bound(inscribed) ≤ exact optimum passes at all five
presets (trivially, since the bound is zero).

**Consequence for H1.** Theorem 1 cannot certify it. §2.1 certifies it a different way, from the
convexity of the problem rather than from a closed form. §1.3 of note F should be corrected accordingly.

### 2.1 H1 as a certificate

`tac25_certificate.py` → [`review_wp1/tac25_certificate.json`](review_wp1/tac25_certificate.json).

**The premise, checked before it is used.** For one fault case the separation test is: do the two
uncertainty sets still intersect,

  ∃ u ∈ [−1,1]ᵏ, n ∈ [−e, e]¹² :  Δc + ΔH δ = G u + n ?

δ enters only the right-hand side — it shifts the centre and leaves the generators alone. That is a
claim about the code, not about the mathematics, so it is verified rather than asserted:
`affinity_check` compares the affine model against the nonlinear network solver at random (δ, u), and
the largest residual over the normal case and 12 fault cases is **2.1 × 10⁻¹⁴**. Superposition holds
exactly, because δ and the source perturbations enter the same linear system's right-hand side.

**The consequence.** The set of δ that FAIL to separate a given case is then the preimage of a fixed
polytope under an affine map — a convex polygon in the δ-plane, the intersection of the half-spaces
λᵀΔH δ ≤ h_Z(λ) − λᵀΔc over the facet normals λ of the zonotope. So if the disc |δ| ≤ R lies inside
that polygon for **any single fault case**, then no δ in the disc separates the problem, and the
polygon's supporting hyperplanes are the proof. `failure_polygon` computes the polygon exactly by
support LPs with edge refinement (a polygon has finitely many edges, so the refinement terminates);
`inradius` returns the largest certified R.

| ε | current limit | certified at R = 1.5? | disc actually covered | certifying case | faces |
|---|---|---|---|---|---|
| 0.16 | none | **yes** | **\|δ\| ≤ 2.242** | AG, 35 % of the line, R_f at its maximum | 28 |
| 0.16 | uncertain, pruned at 2.1 | **yes** | \|δ\| ≤ 1.596 | same case | 48 |
| 0.16 | hard 1.2 | not applicable | — | — | — |
| 0.12 | none | no | \|δ\| ≤ 1.363 | AG, 95 %, R_f max | 28 |
| 0.12 | uncertain, pruned at 2.1 | no | \|δ\| ≤ 0.730 | AG, 95 %, R_f max | 47 |

**So H1 at ε = 0.16 is a proof, not a search result**, and a stronger statement than the one claimed:
no δ below **2.24 pu** separates, against the 1.5 pu the claim asserts. One AG fault at 35 % of the
line with the largest modelled fault resistance is unseparable from normal operation by any injection
of that size, and 28 hyperplanes certify it. The whole certificate takes 11 s against 728 s for the
grid search it replaces.

Three honest limits on it.

1. **It is a sufficient condition.** It certifies by finding one case that fails everywhere in the
   disc. If no single case covered the disc but several together did, the test would return "not
   certified" while the answer was still "none" — a union of convex sets need not be convex. At
   ε = 0.16 one case does cover it, so the question does not arise there.
2. **With the current limit the pruning must be conservative.** The restriction |i⁺| ≤ I_max − |δ| is
   not affine in δ, so the certificate prunes at the disc's own radius (headroom I_max − R), which is
   the smallest admissible set over the disc and therefore sound for all of it — and also weaker,
   which is why the covered radius falls to 1.596 and 0.730. At a hard 1.2 pu limit with R = 1.5 the
   headroom is negative and the certificate does not apply at all; that cell is reported as "not
   applicable", not as a result.
3. **At ε = 0.12 it is not a proof, but it brackets one.** The certificate covers |δ| ≤ 1.363 and the
   global search separates at 1.42 (§4.1), so the true minimum lies in a 0.06 pu window, and two
   methods that share no code path agree. That is the best available check that the map is right.

---

## 3. H5 reverses: the current limit belongs inside the problem

`tac25_design.py`. TAC25 §II:

> "the constraints in (1b) restrict the values x can take on in P⁰_S, increasing its objective. The
> presence of such constraints can, therefore, only increase σ_S(θ), **shrinking the size of
> auxiliary signal needed** to attain separation."

There are two readings of |i⁺| + |δ| ≤ I_max and they pull opposite ways.

**(a) A restriction on the design.** Reject any δ whose worst-case i⁺ *over the whole source set*
leaves no headroom. This removes candidates and can only hurt. It is what
`wp1_h5_current_limit.py` does, and it is why REVIEW.md's H5 row reads "every preset needing δ > 0
infeasible at 1.2 pu".

**(b) A restriction on what can be observed.** An inverter injecting δ physically cannot also be
carrying i⁺ above I_max − |δ|, so those realisations do not occur and must leave the uncertainty
set before separation is tested. A smaller set is easier to separate. This is TAC25's (1b).

**(a) is not a separate physical requirement — it is (b) misread as a constraint on the design
variable.** It demands headroom against a realisation that cannot occur while δ is being injected.
The correct treatment is (b) alone, with the side condition that the restricted set must be
non-empty (the inverter must still be able to carry *some* admissible pre-fault current).

Measured on the presets, same global polar solve, 0.02 radius grid:

| Preset | exact (no limit) | solver, no limit | **H5's reading (a)** | **TAC25's reading (b)** |
|---|---|---|---|---|
| weak_sg | 0.5040 | 0.520 | **infeasible** | **0.260** |
| weak_sg_noisy | 0.6908 | 0.700 | **infeasible** | **0.260** |
| all_ibr_hard | 0.3863 | 0.400 | **infeasible** | **0.160** |

The "no limit" column reproduces the known exact optima to the grid step, which is the solver's own
check.

So **H5 reverses twice over**: the presets are feasible, and the required signal is about half the
unconstrained value. The disc |i⁺| ≤ I_max − |δ| is imposed as a *circumscribed* 24-gon, so the
restriction is understated and the guarantee stays sound.

> **The assumption this rests on.** (b) is only legitimate if the current limit is a hard bound on
> the physical inverter. On EvEMTBench it is not (claim 20). If the inverter can exceed I_max, the
> restricted uncertainty set is too small and the guarantee is void. §3.1 removes the assumption
> instead of sweeping around it.

### 3.1 The limit as an uncertain parameter, not a constant

`tac25_softlimit.py` → [`review_wp1/tac25_softlimit.json`](review_wp1/tac25_softlimit.json).

**What the measured figures actually are.** `ibr_limiter_check.py` reports the **fundamental phasor**
magnitude from a full-cycle (128-sample) DFT, peak-referenced, in pu of the controller's own I_base,
over 765 faults per inverter against a controller setting of 1.2 pu. It is not the instantaneous peak;
the earlier 1.15–1.2 pu figure in REAL_TESTGRID.md was an instantaneous peak over 0.25–3 cycles and
includes the DC offset. Three windows are measured, and they answer the "is this just a first-cycle
transient?" question directly:

| |I₁| + |I₂|, pu of I_base | cycle 1–2 | cycle 3–4 | cycle 9–10 |
|---|---|---|---|
| median | 1.07 – 1.11 | 1.08 – 1.18 | 1.07 – 1.16 |
| p95 | 1.51 – 1.53 | 1.54 – 1.61 | **1.50 – 1.56** |
| max | 1.84 – 1.86 | 2.08 – 2.17 | **2.07 – 2.12** |

The overshoot is **still there at cycles 9–10**, so it is not an LCL or PLL transient being compared
against a steady-state limit: it is what the limiter does in the steady state. Two caveats on the
quantity itself. |I₁| + |I₂| is a sum of sequence magnitudes and bounds the phase current from above;
the largest **phase**-current magnitude, which is closer to what a limiter regulates, is median
1.02–1.10 and p95 1.44–1.51, so it overshoots too, by less. And the limiter's own setting is 1.2 pu,
so the p95 is 25–30 % above the setting rather than above the rating.

**The treatment.** If I_max is only known to lie in a band [lo, hi], every realisation that can
physically occur while δ is injected satisfies |i⁺| ≤ hi − |δ|. Pruning the uncertainty set with **hi**
therefore keeps a superset of the true set, separation proved on the superset holds on the true set,
and the guarantee is valid whatever the true limiter does. The price is the monotone trend §4.1
already shows.

Required |δ| in pu, band [1.1, 2.1], 0.02 pu radius grid, continuous (m, R_f) re-check passing at
every feasible cell:

| | hard 1.1 | hard 1.2 | hard 1.3 | hard 1.5 | hard 2.1 | **uncertain [1.1, 2.1]** | (no limit) |
|---|---|---|---|---|---|---|---|
| **ε = 0.04** | 0 | 0 | 0 | 0 | 0 | **0** | 0 |
| **ε = 0.08** | 0.22 | 0.28 | 0.32 | 0.42 | 0.56 | **0.56** | 0.56 |
| **ε = 0.12** | none | none | 0.72 | 0.82 | 1.14 | **1.14** | 1.42 |
| **ε = 0.16** | none | none | none | none | none | **none** | none |
| ε = 0.08, ρ = 0.1 | 0.30 | 0.36 | 0.40 | 0.50 | 0.72 | **0.72** | 0.72 |
| ε = 0.12, ρ = 0.1 | none | none | none | none | 1.26 | **1.26** | 1.72 |

Three readings.

1. **The guarantee does not depend on the limit being hard.** Pruning at the loosest measured bound
   keeps every cell that was feasible at ε ≤ 0.12, and it costs a factor of two in signal at ε = 0.08
   (0.28 → 0.56) and a factor of 1.6 at ε = 0.12 (0.72 at I_max 1.3 → 1.14). The claim that the
   design is feasible *because* the limit is tight was too strong: it is feasible either way, more
   expensively when the limit is not trusted.
2. **A loose bound can rescue a cell a tight one loses.** At ε = 0.12 with ρ = 0.1 every hard limit
   up to 1.5 is infeasible — the headroom I_max − |δ| admits no pre-fault current at all — while the
   uncertain treatment at 2.1 returns 1.26 pu. The limit binds on the design side long before it
   helps on the uncertainty side.
3. **Injectability is the real casualty, and it is reported separately.** Producing the robust δ
   needs |i⁺| + |δ| within the *true* limit. The smallest true limit that admits it is **1.81 pu at
   ε = 0.08** and **2.39 pu at ε = 0.12**. The first is inside the measured spread but above its p95;
   the second is outside it entirely. A soft limiter does not void the guarantee, but it does not
   supply the headroom the robust design needs either, and no amount of analysis fixes that — it is
   an inverter-rating question.

---

## 4. The feasibility map

`tac25_map.py` → `review_wp1/tac25_map.json`. Sound outer source set (H6), margin in measurement
units (H14), global polar solve over the δ-plane (H15), ε from the corrected fault-condition
instrument figures (H2), and every returned δ re-checked on a dense continuous (m, R_f) grid (H13).

### 4.1 Measurement error against current limit

Required |δ| in pu; "none" = no admissible signal exists. Base network, margin ρ = 0.

| | I_max 1.1 | 1.2 | 1.3 | 1.5 | 2.1 | (no limit) |
|---|---|---|---|---|---|---|
| **ε = 0.02** | 0 | 0 | 0 | 0 | 0 | 0 |
| **ε = 0.04** | 0 | 0 | 0 | 0 | 0 | 0 |
| **ε = 0.08** | 0.22 | **0.28** | 0.32 | 0.42 | 0.56 | 0.56 |
| **ε = 0.12** | none | none | 0.72 | 0.82 | 1.14 | 1.42 |
| **ε = 0.16** | none | none | none | none | none | **none** |

Four things to read off it.

1. **ε is the binding variable, not the current limit.** Below 0.04 pu no signal is needed; above
   0.12 pu none exists at any limit. The whole interesting range is 0.08–0.12 pu — which is
   precisely the band the corrected instrument figures give (VT 3–6 %, CT 5–10 %, adding in the
   impedance per Kasztenny 2021 eq. 9b; see
   [`papers/notes/E_practitioner_settings.md`](../papers/notes/E_practitioner_settings.md) §7).
   **The design sits exactly on its own feasibility boundary at realistic instrument accuracy.**
2. **The required signal grows monotonically with I_max**, and at I_max = 2.1 it equals the
   unconstrained answer to the grid step. That is TAC25's mechanism made visible: a tighter limit
   removes more realisations, so a smaller signal suffices. It also means the tool's answer is only
   as good as the trust one places in the limit.
3. **But a tighter limit can also make the problem infeasible**, and at ε = 0.12 it does: at
   I_max 1.1 and 1.2 the headroom I_max − |δ| no longer admits any realisable pre-fault current, so
   the inverter cannot carry its own load *and* inject what separation requires. The constraint
   helps on one side and binds on the other; the balance moves with ε.
4. **H5's reading (a)** returns "none" in 19 of the 25 cells, including cells where an admissible δ
   demonstrably exists.

This also re-frames **H2**. H2 found "design eps is 111–208× the synthetic phasor noise std", which
is true but measures against the wrong error model: white noise averages down over a 128-sample DFT
and per-installation ratio and phase errors do not. Against the fault-condition figures, ε = 0.08
is at the *low* end of defensible and 0.16 at the high end. The presets' ε was not absurd; the
comparison was.

### 4.1.1 One box on twelve components was the wrong uncertainty set

`tac25_channels.py` → [`review_wp1/tac25_channels.json`](review_wp1/tac25_channels.json).

The ε axis above puts a single independent ±ε box on all 12 real components of the measurement. That
is wrong in four ways, and every one of them makes the problem look harder than it is:

1. **CT and VT errors are not the same size.** The corrected fault-condition figures are VT ratio
   3–6 % with 2–4° of phase and CT ratio 5–10 % with 1–3°. One ε cannot be both.
2. **They are systematic per installation, not independent per component.** One transformer has one
   ratio error, and it scales all three sequence components of its own quantity together. The box
   lets them err in opposite directions, which no instrument does.
3. **They are multiplicative.** A 5 % CT error on a 0.1 pu negative-sequence current is 0.005 pu, not
   ε. A ratio error cannot manufacture negative-sequence voltage out of nothing; only the part of the
   error that differs between phases can, and it leaks through the sequence transform at ⅓ weight.
4. **The same unknown error is in both hypotheses.** One observation passes through one instrument
   set, so the error is a shared variable of the pair problem, not two independent draws.

Replacing it with a structured set — two shared systematic generators per instrument, six per-phase
generators per instrument mapped through BM·diag(ζ)·AM, a small independent white box, and explicit
extra columns covering the (error × source uncertainty) cross term, which is **5–7 % of the
measurement here and so is carried rather than dropped** — gives 16 generators in place of the box.
Per-component half-widths, base case:

| | Re v₁ | Re v₂ | Re v₀ | Re i₁ | Re i₂ | Re i₀ |
|---|---|---|---|---|---|---|
| scalar box, ε = 0.08 | 0.080 | 0.080 | 0.080 | 0.080 | 0.080 | 0.080 |
| structured, normal | 0.065 | 0.031 | 0.031 | 0.011 | **0.007** | 0.007 |
| structured, AG at 55 %, max R_f | 0.067 | 0.037 | 0.035 | 0.036 | **0.033** | 0.022 |

The structured set is *comparable* on v₁, where the signal is ~1 pu, and four to eleven times
narrower on the negative-sequence components, which are the ones separation actually turns on.

**The result: no auxiliary signal is needed at all.** At the corrected per-channel figures, δ = 0
separates every fault case, with or without the current limit, at ρ = 0 and ρ = 0.1. **The ε = 0.12
boundary does not move — it dissolves**, because a scalar ε was never the physical axis.

What replaces it is an *imbalance* axis: how large the per-phase (phase-to-phase) part of the
instrument error would have to be before a signal is needed. Scaling only that part by κ, with the
systematic part held at its class figure:

| κ (× the class per-phase imbalance) | 1 | 8 | 12 | 16 | ≥ 24 |
|---|---|---|---|---|---|
| required \|δ\| (pu) | 0 | 0 | 0.12 | 1.20 | none |

κ = 12 is a per-phase ratio spread of about 24 % between phases of the same transformer, which no
protection-class instrument shows. So within this model the design is not on its feasibility boundary
at realistic instrument accuracy, and §4.1's claim that it is was an artefact of the isotropic box.

**Two limits on that, stated.** This makes the uncertainty set smaller in exactly the directions the
method uses, so it should be read as "the scalar-ε axis was measuring the wrong quantity", not as "the
problem is easy". And it is still the two-bus model with the inverter's negative-sequence path open;
§4.3 and the follow-up below are what decide whether that matters more than the instrument model does.

### 4.2 The other axes

One at a time from the base case (ε = 0.08, I_max = 1.2). Continuous (m, R_f) re-check passes at
every feasible cell: 462 dense points, 0 unseparated.

| Axis | Value | SIR | no limit | TAC25 |
|---|---|---|---|---|
| Source strength | ×0.25 | 0.50 | 0 | **0** |
| | ×0.5 | 1.00 | 0.08 | 0.02 |
| | ×1 (base) | 1.99 | 0.56 | 0.28 |
| | ×2 | 3.98 | 1.02 | 0.56 |
| | ×4 | 7.96 | 1.06 | 0.42 |
| Non-homogeneity | 0° (base) | 1.99 | 0.56 | 0.28 |
| | 15° | 1.99 | 0.54 | 0.26 |
| | 30° | 1.99 | 0.50 | 0.24 |
| | 45° | 1.99 | 0.42 | 0.22 |
| Local source | SG (base) | 1.99 | 0.56 | 0.28 |
| | **IBR** | 1.99 | **0** | **0** |
| Margin ρ | 0 (base) | 1.99 | 0.56 | 0.28 |
| | 0.1 | 1.99 | 0.72 | 0.36 |

- **Network strength is the second variable.** The required signal rises steeply with SIR to about
  SIR 4 and then falls slightly — at SIR 8 the normal and faulted models differ enough in other
  ways that less injection is needed. At SIR ≤ 1, which is where the three benchmark relays actually
  sit (§6 Q1: 1.04–1.69), **no signal or almost none is needed**. The auxiliary signal is a
  weak-system device, and EvEMTBench is not a weak system.
- **Non-homogeneity barely matters, and helps slightly.** Rotating the source impedance 45° off the
  line angle *reduces* the required δ. This is the axis rung R3's tilt lives on, and the design tool
  says it is not where the difficulty is.
- **A 10 % measurement margin costs 29 % more signal** (0.28 → 0.36). Cheap, and it should always
  be carried — H14's zero-margin optima are not designs.
- **Putting an inverter at the relay end removes the need for a signal entirely**, which is the
  opposite of the project's motivating premise. **Do not read this as a physical result.** It is an
  artefact of the toy model, in which an IBR is an ideal positive-sequence current source with an
  open negative-sequence path (`aux_model.py:29`, `ibr_neg_z = 1e6`): a current source pins the
  measurement far more tightly than a voltage source behind an impedance, so the normal-operation
  set shrinks and separation becomes easy. REVIEW.md H7/N7 already records that the models carry no
  inverter fault response; this map turns that gap from a caveat into a load-bearing one, because
  the "IBR share" axis of the feasibility map is currently meaningless. **An IEEE 2800-style
  negative-sequence response must be added before this axis says anything.**

### 4.3 What the IBR axis needs, and what it is not

Per note F, the Baeckeland unified model parameterises the *positive-sequence, quasi-static*
large-signal behaviour through a limiter angle, which is the wrong sequence for an auxiliary signal
that lives entirely in the negative sequence. It is therefore **not** used here. What is needed
instead is a finite negative-sequence source impedance at the IBR with a *non-inductive, uncertain*
angle: the measured virtual-impedance angles are **−0.5° (circular), +36.2° (priority-based),
−51.6° (instantaneous)** ([`papers/notes/SYNTHESIS.md`](../papers/notes/SYNTHESIS.md) §2), none of
them inductive, against the −90° that directional elements assume. That spread is the uncertainty
dimension, and it is the one the current model replaces with an open circuit.

The uncertainty this leaves is not small and should be stated plainly: **until the negative-sequence
path is modelled, the map's ε, I_max, strength and homogeneity axes are meaningful and its IBR-share
axis is not.** §4.4 models it.

### 4.4 The negative-sequence path, closed

`tac25_negseq.py` → [`review_wp1/tac25_negseq.json`](review_wp1/tac25_negseq.json).

The inverter now carries an IEEE 2800-style negative-sequence current response: i₂ = −K₂·v₂ in pu, a
finite shunt admittance of magnitude K₂ at the inverter bus, at the limiter's measured virtual-impedance
angle (−0.5° circular, +36.2° priority-based, −51.6° instantaneous; SYNTHESIS.md §2). The angle enters
the system matrix, not the right-hand side, so it cannot be a zonotope generator: it is handled as a
finite set of models, with separation required for the matched reading (limiter type fixed per
installation, physically right) and for the crossed reading (any normal angle against any fault angle,
conservative). *The IEEE 2800 clause numbering and the K₂ range are from the reading notes and are not
re-verified against the standard text; the sweep is wide enough that nothing here turns on the exact
figure.*

The first thing it shows is mechanical, and it is the point: **the inverter's negative-sequence
response shunts the auxiliary signal.** Negative-sequence voltage seen at the relay per unit of
injected δ:

| | open (the old model) | K₂ = 2 | K₂ = 4 | K₂ = 6 |
|---|---|---|---|---|
| SG at the relay end | 0.307 | 0.188 | 0.125 | 0.092 |
| IBR at the relay end | **1.044** | 0.192 | 0.098 | **0.062** |

A standard-compliant inverter absorbs the very quantity the method injects, and the more compliant it
is, the less signal reaches the relay. Required |δ| at ε = 0.08, I_max uncertain and pruned at 2.1,
0.04 pu grid:

| | open | K₂ = 2 | K₂ = 4 | K₂ = 6 |
|---|---|---|---|---|
| SG at the relay end | 0.56 | **none ≤ 2 pu** | none | none |
| IBR at the relay end | **0** | 1.48 (crossed 1.52) | none | none |
| **both, structured error set (§4.1.1)** | **0** | **0** | **0** | **0** |

**The IBR-share axis can now be reported, and it reverses.** The old cell said an inverter at the
relay end removes the need for a signal entirely; that was the open circuit pinning the measurement.
With a compliant path the same cell needs 1.48 pu at K₂ = 2 and has no solution at all at K₂ ≥ 4. The
axis was not merely meaningless before, it had the wrong sign.

**And the two corrections of this session pull in opposite directions.** Closing the negative-sequence
path destroys feasibility under the scalar ε box; replacing that box with the structured per-channel
set (§4.1.1) restores it completely — δ = 0 separates at every K₂ and every limiter angle. In this
model the instrument set is the stronger effect. Neither number should be quoted alone: "IEEE 2800
compliance kills the auxiliary signal" is true only against an error model that was itself wrong, and
"no signal is needed" is true only in a two-bus model at one operating point. What is solid is the
mechanism, the shunting factor in the first table, which does not depend on the error model at all.

---

## 5. Corrected statements for REVIEW.md

| Finding | Was | Now |
|---|---|---|
| **H5** | "No inverter current limit; every preset needing δ > 0 infeasible at 1.2 pu" | The limit was applied as an outer check on the design. Inside the problem as TAC25 (1b), the presets are **feasible** at **0.16–0.26 pu**, about half the unconstrained optimum. Infeasibility appears only at ε ≥ 0.12 with I_max ≤ 1.2 |
| **H1** | "No δ ≤ 1.5 separates the zone problem at eps ≥ 0.01" | **Proved at ε = 0.16**, and more strongly than claimed: no δ below **2.24 pu** separates, certified by 28 supporting hyperplanes of one fault case's failure polygon (§2.1), in 11 s. Theorem 1 still cannot do it (§2); the convexity of the separation condition in δ can. At ε = 0.12 it stays a search result, bracketed to [1.363, 1.42] pu |
| **H2** | "Design eps is 111–208× the synthetic phasor noise std" | True but against the wrong error model — and the replacement (a scalar 0.08–0.16 pu box) is also wrong, because instrument error is per-channel, systematic and multiplicative. With a structured set at the same class figures no signal is needed at all (§4.1.1); the feasibility boundary is an imbalance of ~12× the class per-phase spread, not a scalar ε |
| **H7 / N7** | "No inverter fault response in the models" | Half closed. The inverter now has an IEEE 2800-style negative-sequence current response at the measured limiter angles (§4.4), which shunts the injected signal by 3–17× and reverses the IBR-share axis. Still absent: any inverter fault response in the EMT models themselves |
| **H6** | Linearised angle set unsound | Carried: the map uses the sound outer source set throughout |
| **H13** | Guarantee only on 30 grid points | Carried: every feasible cell re-checked on 462 continuous (m, R_f) points, 0 unseparated |
| **H14** | Zero-margin separation | Carried: ρ = 0.1 costs 29 % more signal and is affordable |
| **H15** | Alternating scheme stops at local optima | Carried: global polar solve; reproduces the exact optima to the grid step |
| **Claim 3** | "~0.5 pu resolves high-R LG faults — infeasible at I_max 1.2 pu" | **0.28 pu** at ε = 0.08, I_max 1.2, and feasible. The "infeasible" half is withdrawn |
| **Claim 4** | "50 % more noise → injection exceeds inverter capability" (eps12, 1.3186 pu) | **Holds and strengthens.** At ε = 0.12 the problem is infeasible outright at I_max ≤ 1.2 — not merely expensive |

---

## 6. What this does not show

- No EMT data anywhere in this document. It is the static sequence model only.
- The 14-bus gate is not passed (§1), so none of this is a replication of TAC25.
- The IBR-share axis was an artefact of the missing negative-sequence source model; it is now modelled
  (§4.4), and the answer depends on which error model it is read against, which is itself a result.
- The δ-plane search is exhaustive at a 0.02 pu radius and 5° angular grid, so a "none" away from
  ε = 0.16 is "none on that grid". At ε = 0.16 it is a proof (§2.1); the certificate is a sufficient
  condition, so a "not certified" elsewhere is not evidence that a δ exists.
- The current-limit restriction no longer assumes the limit is hard (§3.1). What remains open is
  whether the inverter can supply the robust δ at all: it needs headroom to 1.81 pu at ε = 0.08 and
  2.39 pu at ε = 0.12, and the measured inverters reach 1.5 pu at p95.
