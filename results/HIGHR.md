# High fault resistance: the band where the signal would matter is empty on this network

17 Oct 2026. Follow-up to step 3 ([results/STEP3_PILOT.md](STEP3_PILOT.md)). The pilot found that up to 40 Ω every
detector, the conventional incremental element included, detects every fault without the signal. The question here:
is there a fault-resistance band where **conventional detection fails but the designed signal can guarantee
detection** within the inverter's limit? *Static model only.* The step-3 three-bus network (synchronous source at the
relay bus), A-G and B-C faults at the design's eight locations.

## Where conventional detection fails

`src/highr_screen.py`, `results/network/highr_screen.json`. Incremental 50N / 50Q, score max(3|ΔI0|, |ΔI2|) at the
relay, A-G faults. The worst case is over the corners of the source box. The pickup is the pilot's calibrated
0.162 pu (design-tier noise).

| R_f | 40 Ω | 80 Ω | 120 Ω | 160 Ω | 200 Ω | 300 Ω | 400 Ω |
|---|---|---|---|---|---|---|---|
| smallest score, worst corner (pu) | 0.42 | 0.27 | 0.19 | **0.15** | 0.12 | 0.08 | 0.06 |
| locations below the pickup (of 8) | 0 | 0 | 0 | **4** | **8** | 8 | 8 |

Conventional detection starts to fail at about 160 Ω and fails everywhere from 200 Ω. A real 50N with better CTs
could use a lower pickup and reach further.

## Whether the signal can guarantee detection there

`src/highr_design.py`, `results/network/highr_design.json`. The two-frame design with the most favourable instrument
model:
- the structured design tier: per-phase CT 1 % / 0.3°, VT 0.5 % / 0.3°;
- white noise V 0.02 / I 0.04 pu;
- no margin (ρ = 0);
- the 1.14 pu cap of the filtered reference.

| R_f | cases unseparated at δ = 0 (of 16) | δ* within the cap |
|---|---|---|
| 40 Ω (step 3, structured design tier) | 0 | **0** (no signal needed) |
| 80 Ω (box design tier, ρ = 0; results/STEP3_PILOT.md) | 6 of 48 | 0.94 pu |
| 120 Ω | 12 | **none** |
| 160 Ω | 14 | **none** |
| 200 Ω | 16 | **none** |

## Reading

- **On this network there is no fault-resistance band where conventional detection fails and the designed signal
  can guarantee detection.**
  - Up to 40 Ω the guarantee is free at near-nominal accuracy, and detection does not need it anyway.
  - At 80 Ω the guarantee costs most of the inverter.
  - From 120 Ω no admissible signal provides it, even with the best instrument model and no margin.
  - Conventional detection only starts to fail at 160 Ω.
- The reason is that high fault resistance shrinks every fault signature, the injected signal's included. The
  signal cannot be made larger than the inverter's limit, so the guarantee runs out before the conventional element
  does.
- This is about the **worst-case guarantee**. Statistical detectors (the multiple-model test, a tuned 50N, a CNN) might
  still detect at 160–200 Ω with realistic noise; that is not tested here. A guarantee against the full ε box is
  not available there.

All static. One three-bus network with a synchronous source at the relay bus, eight locations per fault type.
