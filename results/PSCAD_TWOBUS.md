# The design tool's circuit, in PSCAD: same circuit, checked

16 Oct 2026. Steps 1 and 2 of the plan meet here: the two-bus circuit the design tool solves
(`src/aux_model.py`, preset `weak_sg`) is built in PSCAD with the injecting inverter
([PSCAD_INVERTER.md](PSCAD_INVERTER.md)), and the EMT relay phasors are compared with the design model's
at the same operating point. Code: `src/pscad_twobus.py` (builds and runs), `src/pscad_twobus_check.py`
(compares).

## The circuit

Base 10 MVA, 20 kV, Zbase = 40 Ω, 60 Hz.

| Element | Design model (pu) | PSCAD |
|---|---|---|
| Source at bus L | EMF 1∠0, zs1 = zs2 = 0.4j, zs0 = 0.8j | `source3`, inductive (Type = L), 16 Ω / 32 Ω |
| Line | z1 = 0.02 + 0.2j, z0 = 3 z1 | per phase 0.8 + j8 Ω; z0 from a ground-return conductor of (z0 − z1)/3 chained like the line |
| Fault at fraction m | ag, or 'ab' (the phase-phase fault symmetric about phase A) | breaker to ground on phase A; B–C through Rf |
| Load at bus R | 1 + 0.3j, ungrounded | wye 40 + j12 Ω, neutral not grounded |
| Inverter at bus R | current source, 0.9 pu, negative-sequence shunt open | the averaged inverter: ID = 0.869, IQ = 0.233 (0.9 pu at −15° from V1), I2 suppressed |
| Inverter's zero-sequence path | 0.15j in the preset | **open** (delta-side interconnection), and the design model is run the same way (`ibr_zero_z = 1e6`) |

The relay measures V and I at bus L, into the line.

## Result: the EMT circuit is the design model's circuit

One rotation maps PSCAD's time frame onto the model's EMF frame, fixed by the source EMF measured
before the fault (E1 = V1 + zs1 I1 = 1.0001 pu). The inverter's measured injection is given to the
model. Nothing else is fitted.

| Run | max |EMT − static| over V1, V2, V0, I1, I2, I0 at the relay |
|---|---|
| before the fault | **0.0000 pu** |
| A-G fault at m = 0.55, bolted (3 cycles in) | **0.016 pu** (largest quantity 0.81 pu) |
| B-C fault at m = 0.55, 20 Ω | **0.001 pu** (largest quantity 0.77 pu) |

Element by element, from the EMT waveforms: zs2 = 0.016 + 0.403j, zs0 = 0.024 + 0.795j, the A-G loop at
the fault point 0.015 + 0.110j (0.55 × z1 = 0.011 + 0.110j), KCL at bus R exact, the inverter at −15.2°
from V1 before the fault and −15.3° during it. The remaining 2 % on the A-G fault is most likely the
decaying DC component three cycles in.

## Two errors found on the way

1. `source3`'s default impedance type is **resistive**. Given a magnitude and an angle, PSCAD used the
   magnitude as a resistance; the source has to be set to Type = L.
2. Phasors from windows at different positions were not in one frame (`waveforms.sequence_phasors`
   referenced each window's start). Fixed for the whole repository; it also withdrew an earlier
   selector finding (REVIEW.md row 48, [PSCAD_FIRST.md](PSCAD_FIRST.md)).

## Next

Design δ for this circuit with the design tool (the preset with the zero-sequence path open), inject it
through the inverter's mode 2, and check in EMT whether the fault cases the tool calls separable are
separable: the first test of the method with the signal actually injected.
