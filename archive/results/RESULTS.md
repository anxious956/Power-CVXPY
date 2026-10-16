# First result: toy replication of Taylor's auxiliary-signal design in CVXPY

Date: 13 Sep 2026. Code: `aux_model.py`, `aux_signal_toy.py`, `sweep_delta0.py`. Run: `python aux_signal_toy.py <preset>`.

## What was built

A static, sequence-domain, two-bus model following the modelling choices of
Taylor & Dominguez-Garcia, *Geometry of Distance Protection* (arXiv:2510.04379):

- Synchronous generator = voltage source behind impedance; inverter = current source (Sec. II-A).
- Auxiliary signal = negative-sequence current injection δ by the inverter (Sec. II-B).
- Uncertainty = zonotopes: source magnitude/angle and relay measurement noise as boxes (Sec. III, IV).
- Fault scenarios: LG (ag) and LL (ab) on a grid of location m and resistance mr·rF (Sec. V).
- Separation test: LP feasibility of the intersection of two pre-test sets (Sec. V-D, VI-A).
- Part 1: grid search over δ in the complex plane, as in the paper's Sec. VI-D1 / Fig. 5.
- Part 2: min ‖δ‖² subject to Farkas dual feasibility (Sec. VI-B, Lemma 8), solved by an
  alternating scheme with the convex step in CVXPY + Clarabel (the paper uses CVXPY + Clarabel and ADMM).
- Part 3: visualization by projecting both sets onto the Farkas direction λ.

Relay measures six phasors at the local bus: v+, v−, v0, i+, i−, i0 (12 real dims).

## Results

| Preset | Sources | Noise ε | Max R_f (pu) | Ambiguous at δ=0 | Smallest δ on grid | CVXPY optimum | Verified |
|---|---|---|---|---|---|---|---|
| easy | stiff SG + IBR | 0.03 | 0.3 | 0 / 30 | 0 | 0 | yes |
| weak_sg | weak SG + IBR | 0.08 | 1.0 | 5 / 30 | 0.515 | **0.514** | yes |
| weak_sg_noisy | weak SG + IBR, wide IBR angle | 0.15 | 0.3 | 7 / 30 | 0.711 | **0.697** | yes |
| all_ibr_hard | IBR + IBR | 0.15 | 1.0 | 5 / 30 | 0.427 | **0.408** | yes |
| weak_sg_eps12 | weak SG + IBR | 0.12 | 1.0 | 10 / 30 | none ≤ 0.8; ≈1.5 separates | not feasible | no |

The last row is the physical edge of the method: with 50 % more relay noise than `weak_sg`, the ambiguous
cases double and the required injection exceeds 1 pu, more than an inverter can deliver (typical limit
1.1 to 1.2 pu total current).

δ in pu negative-sequence current. "Ambiguous" = fault cases whose pre-test set intersects the normal-operation set.

## Observations

1. With a stiff synchronous source at the relay, no auxiliary signal is needed: every fault is
   already separable from normal operation. The signal becomes necessary exactly when the source
   is weak or is itself an inverter, and when fault resistance and noise are high. This is the
   physical story of the paper, reproduced.
2. In every hard preset the ambiguous cases are the same family: **line-to-ground faults with
   high fault resistance**, at every location. Line-to-line faults never needed the signal.
3. The optimizer's δ is 1 to 5 percent smaller than the best grid point, and verified separating
   by re-running the LP tests. Converged in 2 iterations from the grid point.
4. Magnitudes (0.4 to 0.7 pu) are in the same range as the paper's own examples (0.53 to 4.5 pu
   on the 14-bus system), which is a sanity check, not a comparison.

## Honest caveats

- Static phasor model, not EMT. No inverter dynamics, no current limiter behaviour after the fault.
  The paper itself lists EMT evaluation as "a clear next step".
- Two buses. The paper uses a 14-bus system and multiple IBRs with individual δ.
- Bilinear (m, mr) handled by enumeration on a grid, not by the paper's convex relaxations W_Rel.
- The alternating scheme is a heuristic like the paper's ADMM; neither guarantees a global optimum.
- Inverter negative-sequence behaviour modeled as an open circuit plus the injected δ; a real
  IEEE 2800 inverter has a finite negative-sequence response. Parameter `ibr_neg_z` exists for this.
- Grid step 0.05 pu; grid best is an upper bound on the true smallest separating δ.

## Where this leads (project plan)

1. Replace the two-bus static model with the group's simulator or an open EMT model
   (NREL PyPSCAD grid-forming / grid-following, or Simulink), inject the optimized δ, and check
   whether the relay actually sees it under load and noise: **"theoretical minimum vs practical
   breaking point"**.
2. Detect δ on the relay side with (a) the multiple-model Kalman filter of Pirani, Hosseinzadeh,
   Taylor, Sinopoli 2022 and (b) a learned detector (CNN-BiLSTM from Hasanova & Cakir, ISAIA 2026),
   and shrink δ until each fails.
3. Run the detector on an embedded board and measure decision latency against the one-cycle budget.
4. Measure how much the incremental-quantity characteristic (Taylor 2026) drifts under inverter
   control modes, the assumption the paper flags as weak for IBRs.
