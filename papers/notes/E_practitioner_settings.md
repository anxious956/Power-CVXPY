# Notes: practitioner references for settings and instrument transformers

Read in full, 17 Sep 2026. Six SEL papers, §H of [`papers/README.md`](../README.md).

This note exists to close out one line in [`REVIEW.md`](../../REVIEW.md) §12:

> **Not verified against primary sources.** IEC 61869 class limits; vendor directional-sector
> defaults; conductor ampacity; relay input range; arc and tower-footing values. All are stated
> as assumptions where used.

plus the two settings the review derived itself (the 0.85 reach and the load-encroachment cap),
the Q1 instrument-error assumptions, and what Kasztenny 2022 says about negative-sequence
polarisation, which decides whether ladder rung R3 is a legitimate element at all.

**Nothing was re-run for this note.** Every "would need re-running" below is a proposal, not a
result.

## The papers

| Ref | Paper |
|---|---|
| **K21** | Kasztenny, *Settings considerations for distance elements in line protection applications*, 48th WPRC, 2021 (25 pp) |
| **K22** | Kasztenny, *Distance elements for line protection applications near unconventional sources*, 58th MIPSYCON, 2022 (19 pp) |
| **KC23** | Kasztenny & Chowdhury, *Security criterion for distance zone 1 applications in high SIR systems with CCVTs*, 50th WPRC, 2023 (18 pp) |
| **HR96** | Hou & Roberts, *Capacitive voltage transformers: transient overreach concerns and solutions for distance relaying*, 1995/96, rev. 2010 (21 pp) |
| **CZ12** | Costello & Zimmerman, *CVT transients revisited*, 65th CPRE, 2012 (14 pp) |
| **KFH26** | Kasztenny, Fischer & Hooshyar, *From complexity to consistency: reframing fault response requirements for IBRs*, SEL, 2026 (14 pp) |

---

## 0. The finding that reframes everything else: these grids are not weak

Every SEL zone-1 security concern — CCVT transient overreach, ground potential rise, induced
secondary voltages, steady-state error dominance — is a **high-SIR** phenomenon. K21 §IV makes
the mechanism exact. The distance operating signal for a remote-bus fault is

&nbsp;&nbsp;&nbsp;&nbsp;|(IZ − V)| = (1 − m₁) / (SIR + 1)&nbsp;&nbsp;per unit of nominal loop voltage &nbsp;(K21 eq. 25, KC23 eq. 4)

and any voltage error adds *directly* to it (K21 eq. 28). So the whole literature is about the
regime where that margin is small.

Our benchmark relays are not in it. Taking the source impedances the review already computed
(`results/review/i2_tilt_angles.json`) against the line impedances:

| Relay | \|Z_S\| (Ω) | \|Z1L\| (Ω) | SIR | V at a remote-bus fault | IZ − V margin at 85 % reach |
|---|---|---|---|---|---|
| testgrid_A | 3.42 | 6.55 | **0.52** | 66 % of nominal | 9.9 % of nominal |
| testgrid_B | 5.70 | 10.49 | **0.54** | 65 % of nominal | 9.7 % of nominal |

K21's weak-system discussion begins around SIR 4–5 and its worked examples run to SIR 30, where
the margin is 2.5 % down to 0.5 %. **Our margin is ten to twenty times larger than the regime
these papers are written about.**

This is the explanation for a Q1 result the review recorded without a cause:

> "CVT and CT effects on zone-1 overreach did not appear at these class-T1 / remanence-0.8
> settings."

They did not appear because at SIR 0.5 they are not supposed to. **Q1 tested the instrument
chain in the regime where it does not bite.** That is not a flaw in the experiment, but it is a
limit on what the experiment can conclude, and the conclusion should be stated as
*"at SIR ≈ 0.5, class-T1 CVT and 5P20 CT errors do not move zone-1 security"* rather than as a
general result. Relay B is "the weak-source case" only *relative to its remote end*; against its
own line it is a strong source.

**Changes:** the framing of REVIEW.md §6 Q1 and the "Not robust" list.
**Would need re-running:** nothing, to state the caveat. To actually exercise the regime, the Q1
sweep would have to be repeated on a grid with SIR ≥ 5, which EvEMTBench does not contain — this
becomes a requirement on the WP2 dataset (`REVIEW.md` §10 item 3), not a re-run.

---

## 1. Zone-1 reach: 0.85 on both ground and phase — **CONTRADICTED (mildly)**

K21 §III.E, Table I, is the steady-state error budget we did not have:

| Source of error | Typical reach error |
|---|---|
| Voltage transformers | 5 % |
| Current transformers | 10 % |
| Line impedance data | 5 % (phase) / 10 % (ground) |
| Relay steady-state accuracy | 1 % |
| Relay transient accuracy | 5 % |
| **Worst-case additive** | **26 % (phase) / 31 % (ground)** |

K21's recommendation: **80 % phase, 75 % ground** as normal practice, justified by partial
cancellation of the errors; 85–90 % only "with accurate data on the sources of error", and even
then "especially for the phase distance elements". KC23 §II.C gives the arithmetic rule directly:
reduce the reach by the **sum** of the percentage ratio errors.

The repo uses `REACH = 0.85` for **both** ground and phase loops at all three relays.

- For a benchmark, this is defensible and arguably exactly right: the line impedance is read from
  the grid graph exactly, so the 5–10 % line-data term is genuinely zero, which is the one
  condition K21 names for going to 85 %.
- But K21 is explicit that the **ground** element needs more margin than the phase element, for a
  reason that does not disappear with perfect line data: Z₀ varies with terrain, season and tower
  footing (K21 §III.C), and ground potential rise (§V.C) affects only the ground loops. Using one
  number for both is not standard practice, and it is the ground loops that carry our high-R_f
  cases.
- The 0.85 also silently assumes zero relay transient accuracy error, which K21 puts at 5 %.

**Verdict:** the *value* survives for the phase elements on this data; using the same value for
the ground elements is contrary to practice and unexamined.
**Changes:** the definition of `REACH` in `real_zone.py`, therefore rungs R0/R1/R2 and the T1
tuned-reach baseline, and claim 16/17/18 in REVIEW.md §7 indirectly.
**Would need re-running:** the ladder at a split reach (0.80 phase / 0.75 ground) as a fourth
column beside R0/R2/T2 — `python src/review/ladder.py`, ~10 min. Expect security to improve and
dependability to fall; the interesting question is whether T2 still beats R2 once R2 is set the
way a real engineer would set it.

---

## 2. Resistive reach against reactive reach — **CONTRADICTED, and this is the sharpest finding**

K21 §III.I is the part of the literature the review was missing. A quadrilateral's reactance line
is only as good as the phase angle of its polarising current, and the error is *amplified by the
resistive reach*. With Θ the polarising phase error, R_B the resistive blinder and ΔZ the reactive
reach margin (K21 eqs. 18–20):

&nbsp;&nbsp;&nbsp;&nbsp;ΔZ > 2·R_B·sin(Θ/2)&nbsp;&nbsp;⟺&nbsp;&nbsp;m₀ < 1 − 2·r_B·sin(Θ/2)

with r_B the resistive reach in per unit of |Z₁| of the line. Sources of Θ that K21 lists: CT ratio
error, CT saturation, line charging current, **system nonhomogeneity**, and complex faults with
more than one fault resistance.

Our ladder settings (REVIEW.md §6), with z₁ = 0.0334 + j0.2600 Ω/km on all three lines:

| Relay | \|Z1L\| (Ω) | R_set (Ω) | r_B (pu) | Θ_max tolerated at 0.85 reach | Θ the review actually measured |
|---|---|---|---|---|---|
| A | 6.55 | 24.9 | 3.80 | **2.26°** | 6.43° |
| B | 10.49 | 25.4 | 2.42 | **3.55°** | 6.77° |
| DoubleLine | 5.24 | 19.9 | 3.80 | **2.26°** | 7.03° |

The "Θ measured" column is the tilt uncertainty the review already reported — the width of the
R3 tilt range under ±25 % source magnitude and ±7.5° source angle. **It exceeds the tolerable
polarising error by a factor of 2 to 3 at every relay.** By K21's rule our quadrilateral is set
outside its security limit, and has been throughout.

To satisfy the criterion at the measured ≈7° uncertainty, one of two things must give:

| Relay | keep R_set, reach falls to | keep 0.85 reach, R_set falls to |
|---|---|---|
| A | 53.6 % of line | 8.1 Ω (from 24.9) |
| B | 70.4 % of line | 12.9 Ω (from 25.4) |
| DoubleLine | 53.7 % of line | 6.4 Ω (from 19.9) |

This is not a contradiction of a review *result* — it is the missing explanation for one. The
review observed empirically that R3's worst case over the tilt range costs up to 6.7 points of
dependability and that "at relay B the reading moves about 2.6 Ω per degree of tilt error at
40 Ω". K21 says that is exactly what an over-extended resistive reach does, and gives the closed
form for how far is too far.

It also **strengthens** the review's headline conclusion about the hard stratum. REVIEW.md §10
item 5 says zone 1 cannot reach relay B's 40 Ω faults (R_app ≈ 80 Ω) within load-encroachment
limits. K21 tightens the bound further: the secure resistive reach is not the 25.4 Ω that load
encroachment permits but ≈12.9 Ω. **The 40 Ω stratum is further out of reach than the review
concluded, not closer.**

**Changes:** rungs R2, R3, R4 and T2; REVIEW.md §6 Q-fair and §10 item 5.
**Would need re-running:** the ladder with R_set set by K21 eq. (19) from the measured tilt band
rather than by load encroachment — `python src/review/ladder.py` and
`python src/review/frontend.py ladder --variant relay`, ~10 min each. This is the single most
valuable re-run on this list, because it changes what "the best conventional rung" means, and
therefore what the learned models are being compared against.

---

## 3. Load encroachment (assumed 1800 A, 0.9 pu, 30°, Z_load,min = 31.8 Ω) — **STILL OPEN**

Neither K21 nor K22 gives a load-encroachment setting rule. K21 §VII.B defers it to its
reference [13]; K22 §IV.D says only that "the right blinder reach can be set following line
loadability criteria". The phrase "load encroachment" appears three times across the six papers
and never with a number.

So the 31.8 Ω cap remains an assumption. Two things did change around it:

- It is no longer the **binding** constraint. Per §2 above, K21's polarising-error criterion caps
  R_set at 8–13 Ω, well inside 31.8 Ω. Whether the ampacity assumption is 1800 A or 2500 A stops
  mattering, which retires the review's worry that "using 0.7 × the benchmark's own pre-fault load
  impedance instead would have given 120 / 92.7 / 134 Ω, 4–7 times the rule-based reach".
- K22 §IV.A adds a constraint the review did not have: for an *offset* characteristic, the reverse
  reach must include the origin but must not encroach on load, and "reverse reach settings on the
  order of 10 to 30 percent of the line impedance are typically sufficient".

**Changes:** nothing, but the review's stated sensitivity to the ampacity assumption can be
downgraded.
**Would need re-running:** nothing. The honest statement is that load encroachment cannot be
tested on a benchmark with fixed loading (REVIEW.md §6 already says this) and that it is no longer
the binding limit anyway.

---

## 4. Arc resistance and tower-footing values (arc + 10 Ω tower) — **STILL OPEN**

Not addressed. "Tower footing resistance" appears once in all six papers (K21 §III.C) and only as
a contributor to the uncertainty in Z₀, not as a value. No arc-resistance formula appears
anywhere. These papers are about reach *limits*, not about the fault resistance to be covered.

**Changes:** none. The assumption stands, unverified, exactly as REVIEW.md §12 records it.
**Would need re-running:** nothing. To close this, the primary source is the Warrington arc
formula and an IEEE/CIGRE tower-footing survey, neither of which is in `papers/`. Worth one
entry in the §F gap table.

---

## 5. Directional sector boundaries (−15…115°, min loop current 0.2 In) — **STILL OPEN on the numbers, but the architecture is now sourced**

No vendor default sector angles appear in any of the six papers. The specific −15…115° sector
and the 0.2 In minimum remain our own choices.

What *is* now sourced is everything around them, and it matters more:

- **K21 §II** confirms that directional supervision is *optional* for mho and **mandatory** for a
  quadrilateral. Our R2 adds a directional element to a quadrilateral, which is not an
  enhancement but a requirement. This retroactively justifies the review's decision to treat N2
  (the missing directional element) as a Critical bug rather than a design choice.
- **K21 eq. (8b)** shows the directional condition is not a bolt-on: it falls out of the
  m-calculation itself as `Re(I·1∠MTA·S_POL*) > 0`. K21 notes that practitioners who know
  distance protection only as the m-calculation "often do not realis[e] the need for supervision
  with (8b)" — which is precisely the failure mode of `zone_model.py:206`.
- **K22 §VII** gives the overcurrent-supervision rule for a *weak-infeed* directional element:
  1.25·I_FWD(MAX) < 50WI < 0.8·I_REV(MIN). That is a real setting rule, but for the reverse-looking
  blocking element of K22's scheme, not for our forward sector.

**Changes:** none to the settings; a citation for why R2 exists at all.
**Would need re-running:** nothing. A sensitivity sweep of the sector half-width would be cheap
inside `ladder.py`, but the review already shows R2 has 0 beyond-bus and 0 reverse trips at every
Q1 chain point, so there is no evidence the sector is near a boundary.

---

## 6. CVT transient limits and the CVT model — **PARTLY VERIFIED, with one clear error in our "worst case"**

**Verified.** IEC 61869-5 does define CCVT transient response classes as an envelope of maximum
error against time after the disturbance (K21 §V.G and Fig. 24, citing the standard directly).
The review's use of "class T1" as a pass/fail envelope is legitimate. K21 gives a worked point:
a **PT2** CCVT may still be at **10 % of nominal at 30 ms**.

**Verified.** The magnitude: "the transient can be as high as **25 to 40 percent of the nominal
voltage**" for a metallic fault at the relay (K21 §V.G(a)); it "can last a few tens of
milliseconds" and can hold one polarity for 1–2 cycles. HR96 measures durations of **1.75 cycles**
for voltage-zero inception and **1.25 cycles** for voltage-peak inception. Its spectrum sits close
to the fundamental, so it cannot be filtered out (K21 §V.G(e), KC23 §I).

**Verified.** Our capacitance choice. HR96 states C₁+C₂ ≈ **100 nF** for the CVTs it studies —
exactly our `highC` value — and confirms the direction we modelled: higher capacitance gives a
smaller transient.

**Consistent, on the metric that matters.** The review flagged its own "82 % cycle-1 peak error at
voltage-peak inception" as implausibly large against class limits. It is not directly comparable
to K21's 25–40 %: ours is an instantaneous peak error within the first cycle, K21's is the
transient magnitude, and the review itself already said "the phasor-level error (3.7 % at voltage
zero, 19 % at voltage peak, 20 ms, 90 % sag) is the relevant quantity". **19 % at 20 ms for a 90 %
sag is squarely inside the 25–40 % envelope**, and scaled to our actual 34 % voltage change at
SIR 0.5 it is ≈7 %, against a ≈10 % operating margin. That is the correct reading and it explains
why the high-C CVT changed almost nothing in Q1. It also shows the margin is nearer 1:1 than the
Q1 write-up implies.

**Contradicted — our worst-case CVT is not a worst case.** `common.py:cvt_filter` builds the
`lowC` variant as 20 nF + 200 VA + a **passive** ferroresonance-suppression circuit, described in
the code as "large transient; worst case for zone 1". HR96 is explicit that it is the **active**
FSC that aggravates the transient and the **passive** FSC that "has little effect on the CVT
transient", because its components are isolated from the output when ferroresonance is absent.
Our worst case therefore pairs the bad capacitance with the *benign* suppression circuit. The real
worst case is low capacitance + AFSC, and CZ12 quantifies where that leads: for **SIR 18 with an
AFSC CVT, the maximum secure zone-1 reach is 7 % of the line** — i.e. zone 1 is unusable.

**Changes:** the `lowC` preset in `src/review/common.py`, and REVIEW.md §6 Q1's caveat, which
currently reads "a low-C CVT that fails T1 was excluded, so the worst case for CVT transient
overreach is not covered". The stronger statement is that the excluded variant was not the worst
case either.
**Would need re-running:** add an AFSC variant to `cvt_filter` (an LC parallel tank resonant at
f₀ with a tapped loading resistor, HR96 Fig. 6) and re-run
`python src/review/cvt_class_check.py` and `cvt_step_check.py` (< 1 min each), then the one Q1
row — `python src/review/q1_instrument.py`, 11 min. At SIR 0.5 I would expect it still not to
overreach; the value is in being able to say so having actually modelled it.

**One more, from CZ12 §III, that we have not considered at all.** CZ12 documents two field cases
of **negative-sequence directional elements (32Q) asserting forward for a reverse fault** during
CVT transients, and one resulting DCB scheme misoperation. Its overall finding is reassuring —
"directional elements are generally secure for CVT transients" over dozens of RTDS cases — but
not unconditional. Our R2 supervises the quadrilateral with 32P/32Q and the review verified its
directional accuracy against *study-model labels only, never EMT Δ quantities*. The CVT–32Q
interaction is therefore untested here.

---

## 7. Steady-state error budget and CT/VT class limits — **CONTRADICTED: our Q1 error sizes are too optimistic**

Q1 used, as assumptions, "5P CT ±1 % / ±60 min; 3P VT ±3 % / ±120 min (IEC 61869-2/-3/-5 as
commonly tabulated; not verified against the standard text)".

K21 §III.A–B gives the practitioner's numbers for **fault conditions**, which is the regime Q1
cares about:

| Quantity | Q1 assumption | K21 §III | Verdict |
|---|---|---|---|
| VT ratio error | ±3 % | 3–6 % over a protection voltage range; "below a fraction of a percent" only near nominal | assumption is the **optimistic end** |
| VT phase error | ±120 min (2°) | "small (such as 2 to 4 degrees)" | consistent, optimistic end |
| CT ratio error | ±1 % | **"You can expect a 5 to 10 percent ratio error from a typical protection-class current transformer during fault conditions"** | **too small by 5–10×** |
| CT phase error | ±60 min (1°) | not given as a number; saturation makes the current read low and lead | under-modelled |

The ±1 % figure is the accuracy-class limit at rated current — a metering-range number. Q1 applied
it during faults. That is the wrong number for the experiment, and it is the one that matters
most, because per K21 eq. (9b) the voltage and current errors **add** in the impedance:
|δZ| = |δV| + |δI|. A 10 % CT error alone is 10 % of reach.

K21 also notes the one mitigating fact: during faults the CT error "tends to be negative (the
current measures low)", which makes zone 1 **underreach** rather than overreach. So the effect is
on dependability, not security — which is consistent with Q1 finding no security degradation, and
suggests the missing effect would have shown up in the dependability column.

There is a second-order consequence for §2 above: a 5–10 % CT ratio error is itself a source of
polarising phase error, so the Θ we should be testing against is larger than the 6.4–7.0° that
comes from source-impedance uncertainty alone.

**Changes:** the `installation error` draws in `q1_instrument.py`, and the Q1 conclusion "A
calibration/test installation mismatch at class-limit error sizes did not degrade engineered + LR
at this operating point" — which is true, but the error sizes were too small.
**Would need re-running:** `python src/review/q1_instrument.py` (11 min) with the CT ratio draw
widened to ±5–10 % and the VT to ±3–6 %. This is cheap and I would rank it second after the §2
ladder re-run.

---

## 8. Negative-sequence polarisation on IBR-fed lines, and rung R3 — **CONTRADICTED for the grids this project is about; VERIFIED for the grids we tested on**

This is the item with the largest consequence, and K22 could not be more direct. Its three
conservative findings, stated as design rules (K22 §II.F and §X):

> - The use of **memory polarization** should be avoided in applications near unconventional sources.
> - The use of **negative-sequence current in distance element logic** should be avoided in
>   applications near unconventional sources unless and until the sources provide a
>   negative-sequence phase angle response similar to that of a synchronous generator.
> - Unless and until unconventional sources maintain an inductive positive-sequence impedance,
>   **mho expansion** does not bring the expected benefits.

The mechanism for the middle one (K22 §II.C) is exactly the assumption R3 is built on:

> "polarizing with the negative-sequence current requires the negative-sequence current phase
> angle at the relay location to represent the voltage phase angle at the location of the resistive
> fault. This key assumption is true if the negative-sequence network is homogeneous throughout
> the system. It requires the source behind the relay to have an inductive negative-sequence
> impedance."

An IBR does not provide that. K22 adds that the negative-sequence *magnitude* may be low and its
*angle* may change quickly relative to V₁, V₂ and I₀.

Our ladder uses **both** prohibited ingredients: R2 is a "3-cycle **memory-polarised** 32P with
32Q priority", and R3 is an "**I₂-polarised** reactance line with tilt from the study's source
impedances". So:

- **On EvEMTBench, R2 and R3 are correctly specified.** These grids are synchronous-source
  dominated — the review measured inverters at 0.14 % of short-circuit capacity — and K22 §IX
  point 10 says so explicitly: "When applied to traditional systems with high-inertia synchronous
  generators, the weak-infeed distance elements may perform worse than today's distance elements
  that use memory polarization and negative-sequence current." Our baseline is the right baseline
  *for this data*.
- **On an inverter-dominated grid, R2 and R3 are the wrong design.** Any WP2 result that carries
  this ladder forward to a GFM grid would be comparing learned models against a baseline that
  a protection engineer would not have built. That would repeat, in the opposite direction, the
  exact error the review found in H8: an unfair baseline.

There is one partial rescue, and it is worth keeping. K22 §V.B observes that **memory polarisation
remains valid for *reverse* faults**, because during a reverse fault it is the system, not the
IBR, that maintains the terminal voltage and drives the current. R2's memory-polarised element used
as a *reverse-blocking* supervision would survive; used as a *forward-permissive* decision it
would not. The review's R2 uses it in the forward-permissive sense.

K22's replacement, for the record, is a coherent and fully specified design: an **offset
(non-directional) quadrilateral on apparent impedance**, reactance line polarised by the **loop
current** with a permanent downward security tilt (K22 Fig. 10), forward reach set by standard
practice, reverse reach 10–30 % of the line; directionality from a **32G** zero-sequence element
(permissive, ground loops), a **32WI** weak-infeed reverse-blocking element (phase loops), and
optionally an incremental-quantity **TD32** element; faulted-loop selection by **undervoltage**
rather than sequence currents; and — because a low-inertia source drifts in frequency and drags
the apparent impedance around a circle of radius |I_Y/I_X| (K22 §II.B, eq. 5) — zone 1 **enabled
only for a 2–3 cycle window** after fault detection.

That last point is a phenomenon the review never modelled and EvEMTBench cannot show: with a
low-inertia source the infeed ratio I_Y/I_X is not static but **rotates** at 360°·Δf per second, so
a 0.25 Hz frequency error moves the apparent impedance 90° per second. Our R3 tilt is a *constant*
derived from a static study model. On an IBR grid the tilt would be time-varying within the fault.

**Changes:** the interpretation of rungs R2/R3 (correct here, not transferable); REVIEW.md §10
item 3's dataset requirements; REVIEW.md §10 item 4's "always supervised by 32P/32Q and a starter",
which should read 32G/32WI/TD32 on an inverter-dominated grid.
**Would need re-running:** nothing on EvEMTBench — the conclusion is that the existing ladder is
right for this data. For WP2, a K22-style rung ("R5: offset quad, loop-current polarised, fixed
security tilt, 32G/TD32 supervision, 2-cycle window") should be added to `ladder.py` *before* any
inverter-dominated data arrives, so the comparison is fair from the first run.

---

## 9. What KFH26 changes about the future

KFH26 is the paper both of Taylor's 2026 papers cite as the reason to expect inverters to become
predictable. Its proposal, if adopted, reverses §8 above.

The mechanism: freeze the positive-sequence controller and the PLL at fault inception for at least
2 cycles, and emulate a **virtual shunt reactor** at the IBR terminals so that the *incremental*
currents — and therefore the negative-sequence current, which is an incremental quantity because
it is near zero under load — are tied to the incremental voltages by a **fixed, highly inductive
impedance**. KFH26 §II.D states the purpose in so many words: "This highly inductive impedance
maintains the homogeneity of the network." Homogeneity of the negative-sequence network is exactly
the condition K22 §II.C says I₂ polarisation requires. **If KFH26 is adopted, R3 becomes valid
again on IBR grids.**

Three numbers from it that bear directly on our work:

- **IBR phase currents are limited to ≈1.2–1.5 pu**, possibly 2 pu in future. The review measured
  median |I₁|+|I₂| of 1.07–1.18 pu with p95 ≈1.5 and max ≈2.1 — an independent confirmation, from
  a practitioner source, that the p95/max tail the review reported is normal and that the design
  tool's hard 1.2 pu limit is at the **low end** of the plausible range, not the high end.
- **The incremental headroom an IBR can provide during faults is 0.2–0.5 pu** (KFH26 §II.C). The
  design tool's answer for `weak_sg` is δ ≈ 0.50 pu of negative-sequence injection. That sits
  exactly at the top of the practitioner's stated headroom. This is independent corroboration of
  H5 from outside the project: the current limit binds, and it binds at the number we computed.
- **IEEE 2800's step-response time is 2.5 cycles and its settling time 4 cycles**, while
  ultra-high-speed protection clears in 1.5 cycles. The negative-sequence response the auxiliary
  signal rides on is not settled when the relay must decide. The design tool is a phasor,
  steady-state formulation; this is a timing assumption it does not carry.

**Changes:** REVIEW.md §10 item 2's "IEEE 2800-style negative-sequence response as an uncertainty
dimension" should be split — an IEEE 2800 dimension (today, wide and unhomogeneous) and a KFH26
dimension (proposed, a single inductive impedance). The second is a much smaller set and worth
computing as the optimistic bound.
**Would need re-running:** nothing existing. This is a WP1 design input, taken up in
[`F_taylor_tac_and_gfm_model.md`](F_taylor_tac_and_gfm_model.md).

---

## Summary table

| Item (REVIEW.md §12 and §6) | Verdict | What changes | Re-run |
|---|---|---|---|
| Benchmark SIR regime | new finding: SIR ≈ 0.5 | Q1 conclusions are regime-limited | none |
| Zone-1 reach 0.85, ground and phase alike | contradicted (mildly) | `REACH`, R0–R2, T1 | ladder, ~10 min |
| Resistive vs reactive reach coordination | **contradicted, 2–3× over limit** | R2/R3/R4, T2, §10 item 5 | ladder ×2, ~20 min |
| Load encroachment, 1800 A → 31.8 Ω | still open | no longer the binding cap | none |
| Arc resistance, tower footing | still open | nothing; add to §F gaps | none |
| Directional sector −15…115°, 0.2 In | still open on numbers | citation for why R2 is mandatory | none |
| IEC 61869-5 CCVT transient classes | verified | Q1 wording | none |
| CVT worst case (`lowC` + passive FSC) | **contradicted** | `cvt_filter`, Q1 caveat | cvt checks + 1 Q1 row, ~12 min |
| 32Q security during CVT transients | new, untested here | R2's directional supervision | — |
| Steady-state error budget (Table I) | verified | gives us the missing budget | none |
| CT class limit ±1 % during faults | **contradicted, 5–10×** | `q1_instrument.py` draws | Q1, 11 min |
| VT class limit ±3 % | optimistic end | same | same |
| I₂ polarisation on IBR lines (R3) | **contradicted for IBR grids, verified here** | R2/R3 transferability, §10 items 3–4 | none now; new rung for WP2 |
| Memory polarisation (R2) | contradicted for forward use on IBR grids | R2 architecture | none now |

**If only two things are re-run:** the ladder with K21's resistive-reach criterion (§2), and Q1
with realistic CT/VT fault-condition errors (§7). Between them they decide what "the best
conventional rung" is, which is the number every claim about learning is measured against.
