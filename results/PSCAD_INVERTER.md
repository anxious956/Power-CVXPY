# An inverter that injects a designed negative-sequence signal, in PSCAD

16 Oct 2026. Step 2 of the plan presented to Prof. Taylor ("EMT grid: the inverter injecting the
designed signal"). Code: `src/pscad_inverter.py` (builds the model from Python), `src/pscad_inverter_check.py`
(measures what it injects). Runs on PSCAD 5.0.1 Educational through `mhi.pscad`.

## What was built

An **averaged, grid-following inverter** whose negative-sequence current is ours to set. Averaged means
no switching: the converter is represented by the current it delivers, which is the level of detail of
Taylor's own models (an inverter is a current source with a limit) and of WECC's generic REGC_A.

| Part | How |
|---|---|
| Power stage | Three `master:src_ccin_1` controlled current sources, one per phase, PCC to ground. Checked on its own first: with f = 0 and external control the source injects exactly its instantaneous control input (error 1e-14 kA). |
| Measurement | A one-cycle sliding DFT of the three PCC voltages inside the controller gives V1 and V2. Fixed frequency, no PLL: the angle reference is the measured V1. |
| Positive sequence | I1 = Ibase (ID − j IQ) e^{j∠V1}; IQ > 0 supplies reactive power. |
| Negative sequence | Three modes. **0** suppressed (I2 = 0). **1** IEEE 2800 style, V2-referenced: I2 = j K2 Ibase V2 / Vbase, so I2 leads V2 by 90°. **2** a designed δ, fixed in the V1 frame: I2 = δ Ibase e^{j(∠V1 + angle)}. |
| Current limit | Phase-peak limit at 1.2 pu, I1 and I2 scaled together. |
| Controller | One user component written in Fortran (`gfl_avm`), added to the project as a definition from Python. |

Everything is placed and connected from Python: components by port coordinates read from PSCAD's
master library, joined by node labels and data labels dropped on their ports. No manual drawing.

## Verified: it injects what it is told

Test circuit: a stiff 20 kV source, a 0.5 Ω + 10 mH line, the 10 MVA inverter at the PCC asked for
ID = 0.8 pu. Sequence components of the injected current over the last cycle, computed from the PSCAD
waveforms by our own code (`waveforms.sequence_phasors`), independently of the controller:

| Mode | Asked for | Measured |
|---|---|---|
| 0, I2 suppressed | I1 = 0.8 pu in phase with V1, I2 = 0 | I1 = 0.7999 pu at −0.43°, I2 = 0.0001 pu |
| 2, designed δ | I2 = 0.1 pu at +90° from V1 | I2 = **0.1000 pu at +89.5°** from V1 |
| 1, V2-referenced (K2 = 2), with a 20 Ω A-to-ground load making V2 = 0.053 pu | I2 = 2 × 0.0528 = 0.1056 pu at +90° from V2 | I2 = **0.1055 pu at +89.4°** from V2 |

I0 = 0 in every case, as it must be for a three-wire injection. The small angle offsets (about 0.5°)
are the half-sample delay between the controller's DFT and the measurement. In mode 2 the injected δ
raises V2 at the PCC from 0.0002 to 0.0096 pu through the source and line impedance, as expected.

## What it does not do yet

- **No fault.** The next step is a fault on a line next to the inverter, so the designed δ can be
  checked against what the design tool predicts (step 1 → step 2 of the plan).
- **Fixed frequency, no PLL.** The angle follows the measured V1, but there is no PLL dynamics or
  frequency deviation. Fine for a stiff grid, to be revisited for a weak one.
- **Grid-following only.** A grid-forming inverter (the third case in the deck) needs a voltage-source
  model with a current limiter; not built.
- **Limiter type.** One type only (common scaling of the phase peaks). The circular, priority-based and
  instantaneous limiters of the literature can be added as options in the same component.

## Practical notes

- PSCAD cannot build a new project on a path with non-ASCII characters or through the `data/` junction;
  the projects live under `D:\JOSHUA_TAYLOR_data\data\pscad_work\inverter\`.
- In user-component Fortran, `#LOCAL` declares one variable per line, and local names must not collide
  with node or signal names in the circuit; the controller prefixes all its locals with `G_`.
