# Notes: Taylor's own line of work

Read in full, 16 Sep 2026. Five papers. These define the project, so the notes are detailed
and include the exact numbers we would need to reproduce anything.

## Synthesis

The line runs: **2022** a single inverter in the time domain with a Kalman filter, **2023**
the general static (phasor) formulation solved by duality, **2025 TAC** the theory (we do
not have it), **2025 Geometry** the full network with zonotope uncertainty, **2026
incremental** removing the operating point, **2026 reachability** dropping phasors for the
time domain. The through-line is always the same question: *given that the relay cannot
measure the rest of the network, can a fault still be told apart from everything else, and
if not, what is the smallest thing the inverter can do to make it so?*

Two things stand out for us. First, every paper stops at simulation or a small example, and
every one of them names evaluation as future work. Second, the assumption their newest work
rests on (that inverters behave predictably for a cycle after a fault) is one they
**explicitly say is false today**. Both are openings.

---

## 1. Pirani, Hosseinzadeh, Taylor, Sinopoli (2022) — Optimal Active Fault Detection in Inverter-Based Grids
*IEEE Trans. Control Systems Technology 31(3):1411-1417, May 2023. arXiv 2209.06760.*

**Setting.** One inverter-based DG, dq frame, **balanced three-phase-to-ground faults only**.
Inner current controller with a fault current limiter (a saturation block), outer voltage
controller.

**Method.** Multiple Model Kalman Filter with two modes, healthy (h) and faulty (f). Each
mode has its own Kalman filter; the posterior probability of each mode is updated from the
residual. The detected mode is the one with the higher posterior. Then they *design the
perturbation* Δu to maximise the distance between the expected outputs of the two modes,
subject to ‖Δu‖∞ ≤ γ. The objective is bounded by √(p₀ₕp₀f)·e^(−φ), so minimising it means
maximising φ, which is a Bhattacharyya-like distance between the two modes' output
distributions.

**Key practical detail (Remark 3).** The perturbation is applied **only when the inverter's
current reference approaches the limiter bound**, i.e. m = |I_ref − ζ_U| is used as a passive
fault indicator. The authors warn this can false-trigger: an abrupt load change can saturate
the limiter with no fault present.

**Results.** Simulation only. Larger ‖Δu‖ gives faster and more confident detection but worse
tracking error, an explicit detection-versus-disruption trade-off. Robust to parameter
variation.

**Stated limitations, verbatim in substance.** "We only consider three phase, balanced faults
and a single converter. Most real faults, however, are unbalanced, and most grids have
multiple converters and synchronous machines."

**For us:** this is the model-based relay-side detector to benchmark against in WP3. Its
trigger logic is also the honest answer to "when does the inverter inject?"

---

## 2. Taylor & Domínguez-García (2023) — Auxiliary Signal-Based Distance Protection in Inverter-Dominated Power Systems
*arXiv 2311.10880, 5 pages.* **Read this one first. It is the clearest statement of the idea.**

**Formulation.** Two models, k = 0 normal and k = 1 faulty:

    Θ_k θ + X_k x = H_k λ_k,   A_k x ≤ b_k,   ‖λ_k‖ < 1

x is what is known or measured, θ is the auxiliary signal, λ_k is the noise / unmodelled
term. If a λ exists for both k = 0 and k = 1, the relay cannot tell which is true. Design θ
so that only one is feasible.

**The optimisation.** P0 minimises ω subject to ‖λ_k‖² ≤ ω; let σ(θ) = ω*. If σ(θ) ≥ 1 at
least one model is infeasible. Then

    P1:  min θᵀQθ  subject to  1 ≤ σ(θ)

The inner minimisation is removed by replacing P0 with its **dual** (strong duality holds, it
is a convex QP), giving **P2, a bilinear program** with a second-order-cone constraint.
Solved by the **convex-concave procedure**, each iteration an SOCP. (The 2025 paper uses ADMM
instead; same problem, different heuristic.)

**Worked example, fully reproducible.** One IBR, one load, one line, a phase-a-to-phase-b
fault. Normal: ē⁻ = z̄⁻θ̄ + λ̄, ē⁺ = z̄⁺ī⁺ + λ̄. Faulted: both use z̄_f. Values:
z̄⁻ = z̄⁺ = 30 + j35, z̄_f = 26 + j·x_f with x_f swept over [12, 58]. Q = I.
Solved in **CVXPY with Gurobi**, under a second each.

**The key result and the intuition.** |θ̄| as a function of x_f is **U-shaped with its
maximum near x_f ≈ 35**, exactly where the fault reactance equals the normal apparent
reactance. When the fault looks like normal operation, a large signal is needed; when it
looks different, almost none. Figure 3.

**For us:** reproducing Figure 3 is the ideal first validation of the WP1 tool. It is small,
fully specified, and the expected shape is known.

**Missing reference we should get:** Blanchini, Casagrande, Giordano, Miani, Olaru, Reppa,
"Active fault isolation: a duality-based approach via convex programming," SIAM J. Control
and Optimization 55(3):1619-1640, 2017. This is the direct inspiration for the duality step.

---

## 3. Taylor & Domínguez-García (2025) — Geometry of Distance Protection
*Submitted to IEEE Trans. Control of Network Systems. arXiv 2510.04379, 16 pages.*

**What is new versus 2023.** The whole network is modelled, not one line; uncertainty is
aggregated with the **Minkowski sum**; sets are **zonotopes** rather than a norm ball; and
the post-test uncertainty sets are proposed as **a new kind of relay characteristic**.

**Scenarios.** Twelve: normal operation N plus eleven faults
{ag, bg, cg | ab, ac, bc | abg, acg, bcg | abc, abcg}. Because the LG and LL fault loops
appear inside all the others, **analysing ag and ab covers all eleven**. (This is why our own
experiments use only those two and it is not a shortcut.)

**Fault loop equations, the heart of it.**
- LG: apparent voltage v^ag_A = v^a_L, apparent current i^ag_A = i^a_L + k·i⁰_L with the
  zero-sequence compensation factor **k = z₀/z − 1**. KVL gives

      z^ag_A = m_z·z  +  m_r·r_F · (i^a_L + i^a_R)/(i^a_L + k·i⁰_L)

- LL: v^ab_A = v^a_L − v^b_L, i^ab_A = i^a_L − i^b_L, and

      z^ab_A = m_z·z  +  (m_r·r_F/2)·(1 + (i^a_R − i^b_R)/(i^a_L − i^b_L))

  The second term is the whole problem: it contains the **remote current i_R, which the relay
  cannot measure**. Bolted fault (m_r = 0) means z_A = m_z·z exactly. No remote infeed means
  m_z = x_A/x. The relay may assume neither.

**Pre-test vs post-test.** Pre-test is before measuring, and is when the auxiliary signal is
designed, offline. Post-test is after measuring v_L and i_L. **The signal is therefore a
standing injection, not something triggered at fault time** — a different design choice from
the 2022 paper, and the one our waveform model follows.

**Separation and the optimisation.** Δ separates a pair (η₁, η₂) if their pre-test sets do not
intersect. Then min Δ†QΔ subject to every pair being separated. Farkas' lemma converts each
"empty intersection" into a **dual system** whose non-emptiness certifies separation, giving a
biconvex program solved by **ADMM** (Appendix C-B). Computations in **Python, CVXPY,
Clarabel**; CVXPY chosen because it supports complex numbers.

**The auxiliary signal itself.** Δ = i⁻_C, negative-sequence current, so i_k(Δ_k) = A[0, i⁺_k,
Δ_k]ᵀ. Chosen because positive and negative sequence impedances are equal in a symmetric
network and negative sequence is not attenuated by high impedance. Constraint ‖i_k(Δ_k)‖₂ ≤
i_max_k keeps it inside the inverter's limit. Harmonics and zero/positive-sequence injection
are alternatives.

**Test system, fully specified and reproducible.** IEEE 14-bus, line admittances from Table
3.1 of Baeckeland's thesis. SGs at buses {1, 3, 5, 14} as voltage sources, unit magnitude,
angles evenly spaced over [0, 2π/10]. IBRs at {2, 4, 7, 8, 12} as current sources, unit
magnitude, angles evenly spaced over **[0, 2π/3]**, deliberately wide to reflect inverter
angle uncertainty. Loads at {6, 10, 11, 13}, admittance 0.1 + j0.01. Noise: a balanced
λ_k[1, α, α²]ᵀ with λ_k in a regular 20-gon, scaled by Σ = 0.1I. Relay at bus 2 on line 2-3.
**k = 2** (a typical value), **r_F = 1**, close-in threshold **m̲_z = 0.15**, nominal
m̂_z = m̂_r = 1/2.

**Numbers.** Post-test sets for all eleven faults: ~0.9 s. Zonogon relaxation: ~1 ms.
In the auxiliary-signal example the noise is raised to Σ = I and **all** sources are made
IBRs to make the problem hard. Smallest separating δ on the grid for (N, ag), (N, ab),
(ag, ab): δ = j0.2, ‖Δ‖₂ ≈ 0.53. For N against all LG and LL faults: δ = 1.6 + j0.6,
‖Δ‖₂ ≈ 4.52. ADMM improves this to ‖Δ‖₂ ≈ 4.35, **a 4 % reduction**, and the authors
conclude that letting each IBR choose its own signal "might not be helpful."

**Qualitative levers that shrink the uncertainty sets:** raising the close-in threshold m̲_z,
reducing source uncertainty, and assuming bolted faults (r_F = 0).

**Stated future work.** "A clear next step in this research is evaluation of the new relay
characteristics and optimized auxiliary signals in electromagnetic transient simulation."
Also: better handling of the nominal-value approximation, extension to multiple relays,
distributing the problem across IBRs, and applying the same ideas to overcurrent and
time-domain protection.

---

## 4. Taylor & Domínguez-García (2026) — Distance Characteristics for Incremental Quantities
*IEEE Trans. Power Delivery. arXiv 2604.16668, 4 pages, a letter.*

**Idea.** Incremental quantities ṽ = v(t) − v(t − pδ), p = 1. Subtract the pre-fault cycle.
Under **Assumption 1, all sources periodic over [t − δ, t + δ]**, the source terms cancel
algebraically and the incremental remote current becomes

    σ^η(m) = Ω^η(m)·[v_L(t − δ); i_L(t − δ)]

i.e. computable from the relay's **own earlier measurements plus the network structure**,
with no dependence on the operating point during the fault. Ω^η can be precomputed offline.

**Two tractable characteristics.** A **parallelogram** from a point estimate of the remote
current (Minkowski sum of two segments, one along z, one from the fault term), and a
**convex hull** of z^η_A evaluated on a grid of (m_T, m_F).

**Numbers.** Convex hull on an 8×8 grid: **17 ms**. Four corners only: **1 ms**. Point
estimate: **0.7 ms**. The exact set is slightly non-convex at the top left, so the hull is
mildly conservative; the authors judge the error small.

**The admission that matters most to us.** "Assumption 1 is less appropriate for an IBR
because its current magnitude can change suddenly after a fault, upon which the inverter will
go into current limiting mode... An IBR's frequency and phase angle can also change
significantly after a fault. This behavior depends on its control algorithm, which can vary
case by case. **As such, Assumption 1 and the implication that i_C(t) = i_C(t − δ) are
generally not realistic today.**"

Their proposed remedies: standards that force predictable IBR fault behaviour (they cite the
2026 SEL report), or adding uncertainty to i_C(t) while keeping operating-point independence.
Zonotope versions are named as future work.

**For us:** measuring *how far* the characteristic drifts under real inverter control modes is
a well-defined, unclaimed piece of work that the authors themselves flag.

---

## 5. Taylor, Baeckeland, Domínguez-García (2026) — Reachability-based Time-domain Distance Protection
*arXiv 2608.19678, 7 pages.* Baeckeland is at the National Laboratory of the Rockies (the DOE
contract number is NREL's).

**Idea.** Drop phasors. The set of time-domain measurements a relay can see during a fault
**is** a reachable set, and the natural fault test **is** set-based state estimation. Model
the network as a lumped RLC circuit with sources.

**Why it matters for speed.** Phasor detection needs about **1.5 cycles**. Time-domain
schemes can detect in as little as **a quarter of a cycle**.

**The tractability trick.** Full reachable sets are intractable. For each fault type they
build a **reduced-order two-dimensional model whose two states are the apparent voltage and
current** of that fault loop, via singular perturbation. Three consequences: the matrices are
computed offline; the states are the standard distance-protection quantities; and the
consistent state set is just the measurement, so no intersections are needed.

**Instantaneous test.** Instead of solving the differential equation, evaluate its residual
ε^η_m(t) directly from the measurement, take the convex hull over the four corners of the
(m_T, m_F) square, and **declare a fault if 0 is inside that set**. With Λ = {0} and four
corners this is a convex hull of four points in the plane.

**Example and the headline numbers.** Simulink model of the IEEE 14-bus system with **five
grid-forming inverters** (droop, virtual synchronous machine, dispatchable virtual oscillator
control), each with a current limiter. Phase-a-to-phase-b fault at the midpoint of line ℓ₃,
relay at bus 2, R_F = 10 Ω assumed in the test. Detection times:

| Fault resistance | Detection time | Current limiters |
|---|---|---|
| 10 Ω (high) | **1/8 cycle** | none active, IBRs act as voltage sources |
| 1 Ω (medium) | **~3/8 cycle** | some active |
| 0.01 Ω (bolted) | **just over 1 cycle** | all active |

**This is backwards from the usual intuition and it is the most interesting number in the
whole set.** The *bolted* fault is the slowest to detect, because the severe fault drives
every inverter into current limiting, which breaks the model the test relies on. Fault
severity and detectability are inversely related here.

**Stated future work, and one item is ours.** "All of the tests in this paper are
**overreaching** in that they aim to detect all possible faults on the line, and therefore
potentially faults on neighboring lines. We intend to construct corresponding **underreaching
tests** that might miss faults on the relay's line, but will not detect faults on neighboring
lines." That is precisely the in-zone versus out-of-zone problem, which is what our
`zone_detect.py` experiment measures. Also open: which model is right for IBRs (current
source, voltage source, or full RLC), and reducing dependence on network modelling.

---

## What we can take from all five

1. **Two reproducible examples exist** and neither needs anything we do not have: the 2023
   single-line sweep of |θ̄| versus x_f, and the 2025 14-bus system, specified down to the
   bus numbers, the source angle ranges, the 20-gon noise and Σ = 0.1I. Reproducing either is
   a concrete first deliverable for WP1.
2. **The simulation environment for WP2 is named**: Baeckeland, Yang & Seo, "Unified model of
   current-limiting grid-forming inverters for large-signal analysis," IEEE Trans. Power
   Systems 41(1):198-213, 2026, DOI 10.1109/TPWRS.2025.3587224. A Simulink IEEE 14-bus model
   with five GFM inverters and current limiters. **Ask Prof. Taylor for this model first.**
   It would save the team most of WP2.
3. **The design choice differs between papers**: 2022 triggers the perturbation on the
   inverter's own limiter indicator; 2025 injects it continuously and designs it offline. Ask
   him which one the project should assume.
4. **Three openings they name themselves**: EMT evaluation of the 2025 characteristics;
   underreaching (in-zone versus out-of-zone) time-domain tests; and how far the incremental
   characteristic drifts when Assumption 1 fails for real inverters.
5. **Nobody in this line uses learning**, and nobody measures detection latency on hardware.

## Further references these papers led us to, which we do not yet have

| Reference | Why | Where |
|---|---|---|
| Baeckeland, Yang & Seo 2026, unified current-limiting GFM model | **The Simulink test system.** Highest priority. | IEEE TPWRS, DOI 10.1109/TPWRS.2025.3587224; NREL research hub |
| Baeckeland, PhD dissertation, KU Leuven 2022 | Chapter 3 has the 14-bus line data used by the Geometry example | KU Leuven repository |
| Blanchini et al. 2017, SIAM J. Control Optim. 55(3):1619-1640 | The duality argument the 2023 paper takes from | Journal |
| Kasztenny, Fischer & Hooshyar 2026, "From complexity to consistency" | The argument that IEEE 2800's phasor framing is wrong. Cited by both 2026 papers. | https://selinc.com/api/download/141627/ — **blocked to automated download; open it in a browser** |
| Banaiemoqadam, Hooshyar & Azzouz 2020, dual current control scheme | Prior art for making inverters relay-friendly by control | IEEE TPWRD 36(5):2715-2729 |
| Karimi, Yazdani & Iravani 2008, negative-sequence injection for islanding detection | The earliest use of the injection idea we have found | IEEE Trans. Power Electronics 23(1):298-307 |
| Adhikari, Brahma & Gadde 2021, source-agnostic time-domain distance relay | Closest competitor to the reachability paper | IEEE TPWRD 37(5):3620-3629 |
