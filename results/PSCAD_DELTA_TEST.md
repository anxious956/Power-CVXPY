# The designed signal, injected in EMT: the first test of the method

16 Oct 2026. Steps 1 → 2 of the plan presented to Prof. Taylor: the design tool chooses δ for a circuit,
an inverter in PSCAD injects it, and the separation the tool promises is checked on the EMT waveforms.
Code: `src/pscad_twobus.py` (circuit, now with a settable source EMF), `src/pscad_delta_test.py`
(evaluation), the worst-case realisations from the design model's LP. Numbers:
`results/pscad/delta_test.json`.

## The design

Circuit: the design tool's two-bus `weak_sg` (weak source behind the relay, inverter at the far bus,
uncertainty: source EMF ±5 % and ±5°, inverter current ±0.3 pu in magnitude and angle, noise box
ε = 0.08 per component), with the inverter's zero-sequence path open so it matches the PSCAD build
([PSCAD_TWOBUS.md](PSCAD_TWOBUS.md)). Fault cases: A-G and the phase-phase case, five locations, three
resistances, 30 in all.

- At δ = 0 the tool finds **2 of 30 cases it cannot guarantee to separate** from normal operation:
  A-G at 75 % and 95 % of the line through 40 Ω (1 pu).
- The smallest δ that separates every case (grid of 0.02 pu, 5°): **δ = 0.18 pu at 330°** in the source-EMF
  frame. Within the inverter's limit (0.9 + 0.18 = 1.08 < 1.2 pu).

## The test

Separation is a worst-case statement: *some* realisation in the uncertainty box makes the fault look
normal. So each case is simulated at that realisation, taken from the design model's LP (the point of
the fault set closest to the normal set): source EMF 0.954 pu at −5.23°, inverter current 0.658 pu at
+9.2°. It is reproduced in PSCAD by setting the source and the inverter's ID/IQ, with δ = 0 and with the
designed δ (inverter mode 2). The relay measurement from EMT is then placed against the design tool's
normal-operation set N(δ): the ratio is the noise box that would put it inside N, in units of ε. A clean
measurement plus the relay's own noise against N plus its noise means: **indistinguishable if the ratio
≤ 2, separated if > 2.**

| Realisation | Case | δ = 0 | δ = 0.18 pu |
|---|---|---|---|
| **worst case** | A-G 75 %, 40 Ω | 1.93, **not separated** | 2.18, **separated** |
| **worst case** | A-G 95 %, 40 Ω | 1.80, **not separated** | 2.05, **separated** |
| worst case | normal operation | 0.00, inside N | 0.01, inside N (no false alarm) |
| nominal | A-G 75 % | 2.65, separated | 2.90, separated |
| nominal | A-G 95 % | 2.52, separated | 2.77, separated |
| nominal | normal operation | 0.00, inside N | 0.01, inside N |

**What the tool promised happens in EMT.** At the realisation it identifies as the worst, both faults
are indistinguishable from normal operation without the signal, and distinguishable with the designed
0.18 pu; normal operation stays inside the normal set with the signal on. The design model's own ratios
at the same realisation were 1.89 / 1.76 → 2.13 / 2.01; the EMT ones are 0.04 higher because the EMT
uses the inverter's measured injection, not the box corner exactly.

**EMT and design agree to 1e-5 pu** at the relay in every run here (V and I in all three sequences, at
40 Ω the fault current carries almost no decaying DC; the bolted case in PSCAD_TWOBUS.md agreed to
0.016 pu).

## What this does and does not show

- **It shows** that, on this circuit, the design method's guarantee survives the trip from a static
  sequence model to an EMT simulation with the signal actually injected by an inverter model: the
  first such test in this project, and the step Taylor's papers name as next.
- **Thin margins.** 2.05 against a threshold of 2 at 95 %: the design is the smallest δ that separates,
  by construction. Any unmodelled effect of a few hundredths of ε would close it. A design margin (the
  TAC25 formulation in [DESIGN.md](DESIGN.md) has one) is the obvious next run.
- **The inverter references δ to its own V1, the design assumes a fixed δ.** During these faults V1 at
  the inverter rotates by about 6°, so the injected δ sat at −36° instead of −30°. Separation held
  anyway here; for bolted or closer faults the rotation is larger, and it is an effect the design model
  does not carry.
- **One circuit, two fault cases, one realisation each**, fundamental-frequency phasors over one cycle,
  ideal instruments, a grid-following averaged inverter without PLL dynamics. Not yet: the full set of
  30 cases, the corners of the box other than the worst, other limiter types, a multi-bus grid,
  grid-forming inverters, and detection by a real relay algorithm (step 3).
