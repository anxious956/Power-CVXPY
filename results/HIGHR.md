# High fault resistance: the guarantee reaches 160 Ω; whether 50N fails first depends on its pickup

18 Oct 2026. Follow-up to step 3 ([results/STEP3_PILOT.md](STEP3_PILOT.md)): is there a fault-resistance band where
conventional detection fails but the designed signal can guarantee detection within the inverter's limit? Two
reviews shaped this page (review/HIGHR_REVIEW.md and the review of the A-G-only design). Two earlier readings were
revised on the way (REVIEW.md §7 rows 54–55): "the band is empty" was withdrawn (mixed fault types), and "a band
around 160 Ω" was narrowed to a pickup-dependent statement.

**Units.** Distances on this page are in the high-R design's white-noise box, V 0.02 / I 0.04 pu per real component.
The 40 Ω results (FRAMES.md, STEP3_PILOT.md) are in ε = 0.08 pu. One box is 0.25 ε on a voltage component and
0.5 ε on a current component.

The network is the step-3 three-bus network, with a synchronous source at the relay bus. High fault resistance is a
ground-fault phenomenon, so the case set is:
- A-G at the design's eight locations, R_f from 0 to R_top in 40 Ω steps;
- B-C at the same locations, arc resistance only (0 and 5 Ω).

The instrument model is the structured design tier: per-phase CT 1 % / 0.3°, VT 0.5 % / 0.3° as shared symbols,
white noise V 0.02 / I 0.04 pu in the box. The inverter uses the filtered reference.

## The design (*static*; `src/highr_ag_design.py`, `results/network/highr_ag_design.json`)

| A-G up to | ρ = 0 | ρ = 0.1 | inverter current left |
|---|---|---|---|
| 120 Ω | 0.72 pu at 310° (window 306–329°) | 0.82 pu at 310° (window 308–334°) | 0.14–0.66 / 0.14–0.56 pu |
| **160 Ω** | **1.12 pu, window 326–330°** | none within the 1.14 pu cap | 0.08–0.15 pu |
| 200 Ω | none | none (implied by ρ = 0) | — |

At 160 Ω the design point is taken at the window's centre, 328° (`src/highr_static_checks.py`):
- it separates on the search tier;
- the window is 326–330°;
- the dense tier separates at remainder factors 1.0 and 1.1 but **not at 1.25**, so the point has no margin and is
  sensitive to the remainders;
- the smallest witness gaps are on the 160 Ω A-G cases.

At 200 Ω the blocking cases are the 120–200 Ω A-G faults. The reviewer found every sampled clean A-G point there beyond
two boxes at 315° while the sets stay unseparated: outer-set conservatism. So "not certified by the design" is the
right wording there, not "the signal runs out".

## The 160 Ω design point in EMT (`src/highr_emt_check.py`, `results/network/highr_emt_check_160_328.json`)

The batch has 191 PSCAD runs, all with the filtered reference, read through the relay's mimic chain on windows ending
2.0–3.0 cycles after each run's own inception. Distances are in units of the white-noise box. "Own set" is the case's
bare set; "N" is the design's normal set.

| group | runs | outside own set | clean distance to N, smallest (2 needed) |
|---|---|---|---|
| 20 binding cases at their witnesses | 20 | 2, at most **0.007** | **2.79** |
| window edges 326° / 330° | 12 | 0 | 2.78 |
| inception over one cycle | 6 | 0 | 2.79 |
| all 56 cases once | 56 | 1, at most 0.000 | 3.00 |
| settling at 328°, 1.10 / 1.12 / 1.14 pu (8 bolted B-C + 3 A-G), through the whole fault | 33 | **0** at every level | — |

| normal operation | runs | outside N (bare) |
|---|---|---|
| witness normals | 14 | 0 |
| 16 box corners | 16 | 0.057 box (≈ 0.001–0.002 pu, inside the model-error box) |
| balanced load step | 1 | **2.04 boxes** |

- **The design holds in EMT at 160 Ω.** At the witnesses, the window edges and random inception, the fault points
  stay in their sets and at least 2.78 boxes from N, against 2 needed. The inverter settles at 328° up to the cap.
- **With the smaller box, the load step is a certain false alarm for D1.** It sits 2.04 boxes outside N, about
  0.076 pu, mostly on a current component. That is the same physical offset as the 0.95 ε at the 40 Ω design (only
  the unit changed). Beyond 2 boxes, D1 alarms on a 0.2 pu balanced load step at S under any noise inside the box:
  the designed-in limitation of fixed loads, now with certainty. Incremental D0 sees a balanced step as
  ΔI0 = ΔI2 ≈ 0 and does not alarm.

## Conventional and statistical detection in the same runs

The front end has the design tier's noise, 3 seeds. D0 is incremental 50N/50Q, with its pickup calibrated on the
batch's normal runs and pre-fault windows. D1 is the distance to N, alarming above one box.

| | pickup | A-G 120 Ω | A-G 160 Ω | normal alarms |
|---|---|---|---|---|
| δ = 0: D0 | 0.099 pu | **1.00** (smallest score 0.257 pu) | **1.00** (smallest score 0.205 pu) | 0 |
| δ = 0: D1 | 1 box | 1.00 | 1.00 | 0 |
| δ = 1.12 pu: D0 / D1, every A-G band 0–160 Ω | | 1.00 / 1.00 | 1.00 / 1.00 | 0 |

**Without the signal, incremental 50N detects every 120 Ω and 160 Ω ground fault in these EMT runs.** Its smallest
score is 0.205 pu, against a pickup of 0.099 pu set by normal-operation noise. D1 detects them all too. But the EMT
fault runs sit at random source points. 50N's worst case is the worst corner of the source box, which EMT did not
run. Whether 50N fails first therefore depends on its pickup. The worst-corner crossover, interpolated from the static
screen (`src/highr_screen.py`):

| 50N pickup | worst-corner crossover R_f | the design certifies detection up to |
|---|---|---|
| 0.10 pu (bare noise level, this batch) | about 250 Ω (between 200 and 300) | 160 Ω (ρ = 0): **no band** |
| 0.15 pu (security factor about 1.5) | about 160 Ω (between 120 and 160) | 160 Ω: **a narrow band at about 160 Ω** |
| 0.20 pu (security factor about 2) | about 115 Ω (between 80 and 120) | 160 Ω (ρ = 0), 120 Ω (ρ = 0.1): **a band of about 115–160 Ω** |

A protection engineer sets 50N above standing unbalance and noise with a security factor, typically 1.5–2 times,
about 0.15–0.2 pu here, where the pilot's calibrated 0.162 pu sat. Sensitive earth-fault elements reach much higher
fault resistance with a time delay. The comparison here is at the 2–3-cycle decision time.

## Reading

- **The designed signal certifies ground-fault detection up to about 160 Ω on this network**, at about 93 % of the
  inverter, with no margin, in a 5° window, and verified in EMT. At 120 Ω it does so with a 10 % margin for 0.82 pu.
- **Whether there is a band where conventional detection fails first depends on the 50N setting policy.**
  - At a bare 0.1 pu pickup, 50N detects up to about 250 Ω at the worst corner, beyond what the design certifies,
    so there is no band.
  - At 0.15–0.2 pu, the pickup a security factor gives, 50N's worst corner fails from about 115–160 Ω, inside the
    range the design certifies. That is a band, narrow, at 93 % of the inverter and no margin.
- **The set test detects these faults statistically without the signal** in EMT (D1 at δ = 0: every 120 Ω and
  160 Ω fault). Even inside the band, what the signal buys is the worst-case guarantee, not detection by every
  detector.
- **The guarantee has a cost beyond the inverter's output.** At this design D1 alarms on a balanced 0.2 pu load step
  with certainty.
- At 200 Ω and beyond the design does not certify detection; that "not certified" includes the outer sets'
  conservatism.

One three-bus network with a synchronous source at the relay bus; 8 locations per fault type; EMT checks at 160 Ω only.
