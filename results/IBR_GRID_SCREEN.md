# Inverter-dominated relay end: a static screen before a second step-3 run

17 Oct 2026. The reviewer proposed the step-3 pipeline on an inverter-dominated grid (SORULAR_CEVAPLAR Q42). The
question: is Taylor's design needed where inverter-limited fault current defeats conventional detection? This is the
cheap static screen proposed first. Code: `src/ibr_grid_screen.py`. Numbers: `results/network/ibr_grid_screen.json`.
*Static, absolute-frame model; no EMT.*

## The grid

The three-bus network of step 3 with three changes:
- The synchronous source at the relay bus L is replaced by a grid-following inverter (0.5 pu).
- The voltage reference moves to bus S: a grid equivalent with the old source impedance.
- Every inverter's zero- and negative-sequence paths are open, as the PSCAD builder requires.

The relay end therefore supplies no 3I0 and no I2. There are two variants:
- **A**: the designed δ is injected by the inverter at R, as before;
- **B**: δ is injected by the inverter at the relay bus.

## What the relay sees on the hard faults at δ = 0

Hard faults are A-G, R_f 20–40 Ω, at the design's locations, nominal sources, both variants.

| quantity at the relay | hard A-G faults, δ = 0 |
|---|---|
| 3\|ΔI0\|, \|ΔI2\|, \|ΔI1\| | **0** (the relay current is the relay-end inverter's own, fixed) |
| \|ΔV1\| | ≥ 0.119 pu |
| \|V2\| | ≥ 0.119 pu |
| **\|V0\|** | **0.31–0.57 pu** |

The design (absolute frames, current limit inside, ρ = 0.1):

| noise bound | cases unseparated at δ = 0 | δ* |
|---|---|---|
| ε = 0.08 pu | 9 of 48 | 0.42 pu |
| ε = 0.04 pu | 0 | 0 |

(A and B give the same design numbers. The binding cases are on L2, where injecting at L or at R puts the same
current into bus R.)

## The relay-end interface does not change the answer

How the relay-end inverter connects decides which conventional element sees the fault. Hard A-G faults, δ = 0,
static, nominal sources, variant A; the range is over the cases (`ibr_grid_screen.py`, checked independently by the
reviewer):

| relay-end interface | 3\|ΔI0\| (50N) | \|ΔI2\| (50Q) | \|V0\| (59N) | \|V2\| (59Q) |
|---|---|---|---|---|
| open sequence paths (the builder's) | 0 | 0 | **0.31–0.57** | 0.12–0.20 |
| grounded YNd transformer (zero_z 0.15j) | **0.44–1.20** | 0 | 0.02–0.06 | 0.13–0.32 |
| IEEE 2800 V2-referenced I2 (K2 = 2) | 0 | **0.10–0.18** | **0.32–0.64** | 0.05–0.09 |
| both | **0.46–1.40** | 0.11–0.31 | 0.02–0.07 | 0.05–0.15 |

Each choice weakens one element and strengthens another. A grounded transformer cuts V0 to 0.02–0.06 pu, marginal
for 59N, but gives 50N 0.44–1.2 pu. Grid-code positive-sequence reactive current would add ΔI1 of about K·|ΔV1|
(≥ 0.24 pu at K = 2, before the limit). It is not modelled, because the static inverter is a fixed current source.

## Reading

- **Current-based conventional detection fails completely here.** Incremental 50N/50Q (the step-3 D0) sees nothing:
  the only branch at the relay bus besides the line is a current-source inverter with open negative- and
  zero-sequence paths.
- **Voltage-based conventional detection does not fail.** With no zero-sequence path at the relay bus, the fault's
  zero-sequence voltage appears there in full: |V0| ≥ 0.31 pu on every hard A-G fault. A standard 59N element
  (pickup 0.05–0.1 pu) detects all of them without any signal. B-C faults show in V2 the same way.
- So on this grid too, **detecting a fault (task T1) does not need the designed signal**, and that is measured,
  not argued. Single-ended T1 needs no δ on this three-bus grid whether the relay end is synchronous or an inverter:
  - synchronous: 50N;
  - inverter with open sequence paths: 59N / 59Q;
  - inverter behind a YNd transformer: 50N;
  - inverter with IEEE 2800 negative-sequence current: 50Q.

  For the inverter cases this is static at nominal sources; the uncertainty box was not swept. The margins are large
  except V0 under a YNd interface.
- **This is detection, not protection.** 59N on a bus with no zero-sequence source responds to any ground fault on
  the galvanically connected network, including faults beyond R. What a relay at an inverter bus cannot do from one
  end is tell where the fault is. That matches the CIGRE MV result (zone boundary not separable from one end, EMT
  without injection).
- By the screen's own rule (if the conventional floor still sees everything, say so and stop), the EMT
  detection study on this grid is not run. The step-3 pipeline would show the same flat curves, with 59N in place of
  50N.

## What would test the method where it could matter

Selectivity, not detection: task T2, "fault on my line or beyond it", at an inverter-fed relay. The present design
separates faults from normal operation, not L1 from L2 faults. A T2 design means separating the fault sets from one
another. That is a new design, and it is the question to put to Prof. Taylor, with the prior evidence in front of
him. It is an open question, with no presumption that δ helps:
- The B1 screen on CIGRE MV (REVIEW.md §7 row 42, static) moved the zone-1 boundary by only 2–4 points with 0.4 pu
  of δ.
- The Geometry paper's worked example separates fault types on the relay's own line, not zones.
