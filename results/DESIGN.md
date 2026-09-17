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
it is a result, not a failure. The sting is in the mechanism: the design is feasible *because* the
current limit is tight, and the required signal grows monotonically as the limit is relaxed
(0.22 → 0.56 pu as I_max goes 1.1 → 2.1). This project's own EMT measurement says the limit is not
tight — median |I₁|+|I₂| of 1.07–1.18 pu but p95 ≈ 1.5 and max ≈ 2.1 ([REVIEW.md](../REVIEW.md) §7
claim 20). **The assumption that rescues feasibility is the one the data contradicts**, so the
honest headline is that the design tool's answer is feasible but conditional on an inverter
behaving better than the measured inverters do.

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

**Consequence for H1.** H1 ("no δ ≤ 1.5 pu separates the zone problem at eps ≥ 0.01") remains a
search result. Theorem 1 cannot certify it. What *can*, and what §4 below does instead, is a global
solve on the δ-plane plus a dense continuous (m, R_f) re-check — a bound from exhaustion at a stated
resolution rather than a closed form. §1.3 of note F should be corrected accordingly.

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
> the physical inverter. On EvEMTBench it is not: the review measured median |I₁|+|I₂| of
> 1.07–1.18 pu with **p95 ≈ 1.5 pu and max ≈ 2.1 pu** (claim 20). If the inverter can transiently
> exceed I_max, the restricted uncertainty set is too small and the guarantee is void. §4 sweeps
> I_max to 2.1 for exactly this reason.

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
axis is not.**

---

## 5. Corrected statements for REVIEW.md

| Finding | Was | Now |
|---|---|---|
| **H5** | "No inverter current limit; every preset needing δ > 0 infeasible at 1.2 pu" | The limit was applied as an outer check on the design. Inside the problem as TAC25 (1b), the presets are **feasible** at **0.16–0.26 pu**, about half the unconstrained optimum. Infeasibility appears only at ε ≥ 0.12 with I_max ≤ 1.2 |
| **H1** | "No δ ≤ 1.5 separates the zone problem at eps ≥ 0.01" | Still a search result, not a proof. Theorem 1 cannot certify it (§2). At ε = 0.16 pu no δ separates at any I_max including none — that part is confirmed by exhaustion at a 0.02 pu grid plus a dense (m, R_f) re-check |
| **H2** | "Design eps is 111–208× the synthetic phasor noise std" | True but against the wrong error model. Against fault-condition instrument errors, ε = 0.08–0.16 pu is the defensible band, and the design's feasibility boundary sits inside it |
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
- The IBR-share axis is an artefact of the missing negative-sequence source model (§4.3).
- The δ-plane search is exhaustive at a 0.02 pu radius and 5° angular grid, so every "none" is
  "none on that grid", not a proof of non-existence. Theorem 1 would have supplied the proof and
  cannot (§2).
- The current-limit restriction assumes the limit is hard. The project's own measurement says it is
  not (§3), and that is the single largest threat to the headline result.
