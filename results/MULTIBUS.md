# Step 1: the design tool on a multi-bus network, checked in EMT

16 Oct 2026. The deck presented to Prof. Taylor proposed, as step 1, to *"turn the two-bus design into a tool for
a multi-bus network"*. This is that tool, and its first test on a network with more than one line, with the
designed signal injected in PSCAD.

## The tool

`src/network.py`. A network is given as buses, lines (z1, z0), synchronous sources (EMF behind sequence
impedances), inverters (current sources; negative- and zero-sequence shunts; optionally injecting a signal,
with a per-phase current limit) and loads. The tool:

- solves the sequence networks with one shunt fault (A-G, or the phase-phase fault) anywhere on any line, and
  returns the relay's six measurements;
- writes the measurement as an affine map of every uncertain source and every injected signal, with the
  sources' uncertainty sets aggregated by **Minkowski sum** (their zonotope generators stacked), as in Taylor
  & Domínguez-García, *Geometry of Distance Protection*;
- runs the reviewed separation test and design on it: the sound outer source set (H6), a margin (H14), the
  per-phase current limit inside the problem with the fault-side sign handled (REVIEW.md row 49), a global
  polar search; plus worst-case realisations and the distance of a measurement to the normal set.

**Checked against the two hand-written models it generalises** (`tests/test_network.py`, 9 tests):

- the two-bus `aux_model.solve` and the three-bus `zone_model.solve_zone` are reproduced to machine precision
  at random operating points, every fault type, both lines;
- the affine models match `wp1_common.affine_case` in both source-set modes;
- on the two-bus circuit the design returns the same signal as `review/tac25_design.min_delta`, with and
  without the limit;
- the per-phase limit rows keep every sampled physical pair only with the fault block's correct sign, and the
  witnesses respect the limit (brute-force tests; both fail if the pre-#37 sign is put back). A witness
  re-solved as a fault sits exactly at the distance the LP reports, which is a consistency check, not a sign
  test (review/NETWORK_REVIEW.md finding 6).

`src/pscad_network.py` builds such a network in PSCAD from Python, **if it is radial or all its lines have the
same (z0 − z1)/z1** (the line model is exact only then; `build` refuses anything else, conservatively: a radial
spur off a uniform loop would also be exact but is refused too): lines as R-L per phase plus a
ground-return conductor for z0, sources, ungrounded loads, the averaged inverter, the relay's measurements.
The PSCAD side needs only the standard library: the design side writes each run as plain numbers. A fast mode
builds each topology once and updates it per run; it is bit-identical to a fresh build on the cases checked.

## The three-bus network

```
  L ---- line L1 (protected) ---- R ---- line L2 (adjacent) ---- S
  |                               |                              |
 weak source + RELAY           inverter + load                  load
```

`zone_model`'s default: weak source (zs1 = 0.4j pu), L1 = 0.02 + 0.2j, L2 = 0.025 + 0.25j, z0 = 3 z1;
inverter at R, 0.45 pu ± 0.3 pu, ± 0.3 rad, per-phase limit 1.2 pu, zero-sequence path open (as the PSCAD
build requires); ungrounded loads at R and S. Relay at L on L1. 48 fault cases: A-G and phase-phase at five
points of L1 and three of L2, R_f = 0, 20, 40 Ω. Noise box ε = 0.08 pu.

**EMT matches the design model at the relay**: 0.0000 pu before the fault; 0.0000 and 0.0001 pu for faults on
L2; 0.011 pu for a bolted fault on L1 (the decaying DC component).

## The design

| | |
|---|---|
| cases not separable at δ = 0 | **8 of 48**: A-G through 40 Ω at every point of L1 (5) **and of the adjacent line L2 (3)** |
| smallest separating δ, no margin | 0.62 pu |
| smallest separating δ, ρ = 0.1 | **0.90 pu** at 210° (the design tested) |

The adjacent line makes the problem harder than the two-bus one (0.38 pu with the margin there): its high-
resistance faults also fall inside the normal set.

## EMT test: 128 PSCAD runs

Checks: all 128 runs without PSCAD errors and with fresh output; the fault visible at the relay in every
fault run; no phase current above 1.2 pu; |EMT − design| at the relay median 0.00001 pu, largest 0.032 pu
(below).

| Test | Result |
|---|---|
| 48 cases, runs started at their worst realisation, δ = 0 | **8 not separated, the same 8 as the design** (but see below: during the fault the runs are not at that realisation) |
| 48 cases, runs started at their worst realisation, design δ | **48 / 48 separated, all with the margin** (smallest 2.23, design 2.23; during the fault the runs are not at that realisation) |
| normal operation at the 16 box corners, δ-priority limiter (LIM 1) | **0 / 16 outside the normal set** (largest ratio 0.04) |
| normal operation at the 16 corners, limiter scaling both (LIM 0) | **8 / 16 outside, ratio 2.22–2.46 > 2** |

**What the 128 runs show:** with the EMT inverter started at each case's worst realisation (a δ-priority
limiter, δ's angle set for the current it actually delivers), the EMT system separates every fault case with the
design's margin and keeps normal operation inside the normal set at every corner. **What they do not show:** that
the design's fault sets are right case by case, because the runs leave the design's realisation once the fault
starts (qualification 1). Three qualifications, from the independent review
([review/NETWORK_REVIEW.md](../review/NETWORK_REVIEW.md)), all checked again here on the stored runs:

1. **The runs are not at the design's realisation once the fault starts** (finding 3). The inverter keeps I1
   and δ at their angles to its own V1, and the fault moves V1: at 0.38 s δ and I1 have turned by −29.4° to
   +10.6° (median 12.2°; largest on bolted phase-phase faults). The fault-time I1 lies outside the design's
   inverter set in 15 / 48 runs with δ = 0 and 17 / 48 with the design δ. The EMT ratios differ from the design
   model's by up to 0.44 (δ = 0) and 0.96 (design δ). So the table is a test of the EMT system, started at each
   case's worst realisation, not a case-by-case confirmation of the design's fault set. "EMT and design disagree
   on none" was too strong. A design that is to be validated case by case has to model I1 and δ in the
   inverter's V1 frame during the fault.
2. **It costs the inverter its normal output** (finding 4). Beside δ = 0.90 pu, a 1.2 pu per-phase limit leaves
   room for at most 0.46 pu of positive-sequence current; in the LIM 1 normal runs the inverter was asked for
   0.26–0.78 pu and delivered 0.264–0.337 pu, cut by up to 62 %. δ is injected continuously, so this is a standing
   curtailment of active and reactive power, and it is also the mechanism that shrinks the uncertainty set and
   makes separation possible.
3. **This is fault detection, not zone discrimination** (finding 12). Faults on the adjacent line L2 are
   separated from normal operation, as fault cases. A zone-1 relay must not trip for them; the in-zone /
   out-of-zone question is not addressed here. (Also: the case named "ab" is a B-C fault, symmetric about A.)

**With the other limiter it is worse than on the two-bus circuit.** There normal operation left the normal set
but stayed within the noise (ratio up to 0.82); here, with a 0.90 pu signal, the ratio exceeds 2 at 8 corners.
That is not an exposure to noise but a **certain false alarm**: the clean normal measurement is classified as
a fault. The bigger the designed signal, the more the limiter type decides the outcome.

## One more observation: δ referenced to the inverter's own V1 can drift

(The step at fault inception is in qualification 1 above, up to 29°; this is the further drift during the fault.)
In the bolted phase-phase fault at 55 % of L1 with δ = 0.90 pu, |EMT − design| grew from 0.006 pu at 3 cycles
into the fault to 0.032 and 0.077 pu at 5 and 6 cycles. It is not the DC component: the same fault without δ
falls to 0.004 pu. The inverter sets I1 and δ at angles to its own V1, which a bolted fault near it makes small;
over the last three cycles of the fault the injected currents turned by about 6° (I1 −71.5° → −77.4°, δ 96° →
92°) and the one-cycle phasors no longer describe a steady state. The case was separated anyway (ratio 8.1).
It is a dynamic face of the condition stated before: a design that fixes δ in a frame the inverter measures
must account for that frame moving.

## Not yet

- The PSCAD builder refuses meshed networks with unequal (z0 − z1)/z1 (finding 2: its line model is exact only for
  radial networks or a uniform ratio); a meshed test needs coupled line models.

- Grid-forming inverters; more than one injecting inverter (the tool supports a vector δ, the design search is
  for one); the inverter's zero-sequence path (the PSCAD build needs it open); meshed networks (supported by
  the solver, not yet built or tested in PSCAD).
- The IEEE 14-bus example of the Geometry paper: needs the Baeckeland thesis line data, which is not in the repo.
- A relay algorithm (step 3): the test is still the design's own set test.
