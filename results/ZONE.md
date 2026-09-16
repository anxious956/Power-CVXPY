# In-zone vs out-of-zone: does the auxiliary signal actually help?

Date 16 Sep 2026. Code: `src/zone_model.py`, `src/zone_detect.py`. Run: `python src/zone_detect.py`.

This is the experiment the project is about. The first detection study
([DETECTION.md](DETECTION.md)) used a load as the negative, and a conventional multivariate
element solved it without any injection. The negative here is the case protection actually
finds hard, and the one Taylor's formulation addresses: *the relay decides whether the fault
is on its own line*.

## Setup

Three buses: relay and a weak source at L, the protected line to R, an inverter and load at
R, an adjacent line to S.

```
   L ---- z1 (protected) ---- R ---- z2 (adjacent) ---- S
   |                          |                         |
  source + RELAY          inverter + load             load
```

- **Positives:** line-to-ground and line-to-line faults on the protected line, m ∈ [0.62, 0.85], inside the zone-1 reach.
- **Negatives:** the same fault types on the adjacent line, m ∈ [0.02, 0.18], just past the remote bus.
- Fault resistance 0 to 0.3 pu in both classes (line impedance is 0.201 pu).
- Sampling is concentrated in the boundary band on purpose. Sampling the whole line fills the set with easy cases and flatters every detector.
- **Unknown system conditions**, redrawn per sample: source impedance behind the relay ×[0.5, 1.8], both loads ×[0.6, 1.5], inverter output ×[0.5, 1.6] with ±0.4 rad, grounding impedance ×[0.6, 1.6]. These are exactly the uncertainties Taylor's sets are built around. Without them the map from measurement to class is nearly invertible and every detector scores 100 %.
- The inverter injects the auxiliary signal continuously, in all four classes, swept along the direction the design tool chose (−23.2°).

Thresholds and polarity fixed on train at a 1 % false-trip budget, measured on test. 3600 train and 1800 test cases per point.

## Result

| δ (pu) | apparent reactance | \|i⁻\| magnitude | engineered features + LR | 1D CNN on raw waveform |
|---|---|---|---|---|
| 0.000 | 2.8 % | 6.9 % | **96.0 %** | 76.9 % |
| 0.050 | 1.2 % | 7.4 % | 96.6 % | 83.7 % |
| 0.100 | 0.9 % | 7.0 % | 97.2 % | 89.8 % |
| 0.200 | 2.0 % | 6.8 % | 98.0 % | 93.4 % |
| 0.300 | 0.4 % | 6.8 % | 98.3 % | 92.7 % |
| 0.400 | 1.7 % | 6.8 % | 99.3 % | 96.2 % |
| 0.514 | 1.1 % | 6.7 % | **99.4 %** | 98.6 % |

![zone sweep](zone_sweep.png)

## What it says

**1. The auxiliary signal works, and the effect is monotone.** The engineered detector goes
from 96.0 % to 99.4 %, the learned one from 76.9 % to 98.6 %. This is the first measurement
we have that Taylor's scheme buys real discrimination on waveforms rather than on sets.

**2. Conventional scalar elements cannot use it at all.** The apparent-reactance element sits
near 1 % across the whole sweep, and a negative-sequence magnitude threshold near 7 %. In
this regime both are worse than chance-at-budget. The guarantee lives in the joint
measurement, so an element that collapses the measurement to one number throws it away.
That has a practical consequence worth stating: **this scheme cannot be dropped into an
existing relay's impedance element.** Cashing in the guarantee requires a multivariate
decision, which is a change to the relay, not just to the inverter.

**3. Engineered features beat the learned detector everywhere, and the gap closes as δ
grows.** At δ = 0 the difference is 19 points. At the certified δ it is under 1 point. The
honest reading is that deep learning is not the contribution here; the right quantities are.
The CNN has to learn the sequence transform from raw samples with 3600 examples, which is
why it starts behind. With more data or a sequence-domain front end it would likely close the
gap sooner, and that is worth testing rather than asserting.

**4. The theory-versus-practice gap is small but real.** The design tool certifies
δ = 0.514 pu as separating every scenario pair. On waveforms, at that δ, the best detector
reaches 99.4 %, not 100 %. The residual comes from everything the certificate does not cover:
measurement noise, harmonics, the DC offset, and system conditions drawn outside the
uncertainty box the tool was given. Quantifying that gap in EMT simulation, rather than in
this phasor model, is the project.

## Honest caveats

- Static phasor circuit synthesized into waveforms, not EMT. No inverter dynamics, no
  current-limiter action, no CT saturation, no travelling waves.
- Three buses, one adjacent line, two fault types.
- The reactance element here is a bare reactance comparison, not a tuned quadrilateral with
  fault-resistance coverage and a directional supervision. A real relay would do better than
  1 %. The point of that curve is its flatness in δ, not its level.
- The CNN is small (~40 k parameters, 20 epochs per point) and untuned.
- Detection is offline over a fixed post-event window. Latency is the WP4 question and is not
  measured here.
- Single seed per point. Error bars over seeds are the obvious next addition.

## Next

1. Error bars: repeat each point over several seeds.
2. Give the CNN a sequence-domain front end and see whether it matches the engineered features at δ = 0.
3. Add the multiple-model Kalman filter from Pirani et al. 2022 as the fourth detector, since that is Taylor's own relay-side method.
4. Replace this generator with EMT waveforms from WP2 and re-measure the same curve.
