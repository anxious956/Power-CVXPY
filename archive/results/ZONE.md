# In-zone vs out-of-zone: does the auxiliary signal actually help?

Code: `src/zone_model.py`, `src/zone_detect.py`. Run: `python src/zone_detect.py --seeds 3`.
Numbers below are from the full sweep of 17 Sep 2026, with the distance element that
includes k0 compensation and faulted-phase selection (see "Corrections" at the end).

This is the experiment the project is about. The earlier detection study
([DETECTION.md](DETECTION.md)) used a load as the negative, and a conventional multivariate
element solved it without any injection. The negative here is the case protection actually
finds hard, and the one Taylor's formulation addresses: *the relay decides whether the fault
is on its own line*. It is also, word for word, the "underreaching test" that the 2026
reachability paper names as future work.

## Setup

Three buses. Relay and a weak source at L, the protected line to R, an inverter and load at
R, an adjacent line to S.

```
   L ---- z1 (protected) ---- R ---- z2 (adjacent) ---- S
   |                          |                         |
  source + RELAY          inverter + load             load
```

- **Positives:** LG and LL faults on the protected line, m ∈ [0.62, 0.85], inside the zone-1 reach.
- **Negatives:** the same fault types on the adjacent line, m ∈ [0.02, 0.18], just past the remote bus.
- Fault resistance 0 to 0.3 pu in both classes; the line impedance is 0.201 pu.
- Sampling is concentrated in the boundary band deliberately. Sampling the whole line fills the set with easy cases and flatters every detector.
- **System conditions the relay cannot measure, redrawn per sample:** source impedance behind the relay ×[0.5, 1.8], both loads ×[0.6, 1.5], inverter output ×[0.5, 1.6] with ±0.4 rad, grounding impedance ×[0.6, 1.6]. These are the uncertainties Taylor's sets exist for. Without them the map from measurement to class is nearly invertible and every detector scores 100 %.
- The inverter injects the auxiliary signal continuously, in all four classes, swept along the direction the design tool chose (−23.2°).

3600 train and 1800 test waveforms per point, three seeds, mean ± standard deviation.

## Result

Primary metric is ROC AUC, which is threshold-free. Dependability at a 1 % false-trip budget
is given too, but a single strict operating point is fragile to a thin tail and should not be
read alone.

| δ (pu) | apparent reactance | \|i⁻\| magnitude | engineered features + LR | 1D CNN on raw waveform |
|---|---|---|---|---|
| 0.000 | 0.952 ± 0.005 | 0.594 ± 0.020 | 0.995 ± 0.000 | 0.982 ± 0.004 |
| 0.050 | 0.949 ± 0.005 | 0.587 ± 0.019 | 0.997 ± 0.001 | 0.989 ± 0.002 |
| 0.100 | 0.943 ± 0.005 | 0.581 ± 0.018 | 0.997 ± 0.001 | 0.994 ± 0.001 |
| 0.200 | 0.927 ± 0.008 | 0.568 ± 0.016 | 0.998 ± 0.001 | 0.998 ± 0.001 |
| 0.300 | 0.908 ± 0.009 | 0.559 ± 0.015 | 0.998 ± 0.001 | 0.999 ± 0.001 |
| 0.400 | 0.887 ± 0.009 | 0.551 ± 0.014 | 0.999 ± 0.001 | 0.999 ± 0.001 |
| 0.514 | 0.863 ± 0.009 | 0.543 ± 0.014 | 0.999 ± 0.001 | 1.000 ± 0.000 |

Dependability at 1 % false trip for the distance element across the sweep: 74 → 81 → 84 → 81 → 77 → 72 → 68 %. Negative-sequence magnitude stays near 7 %, engineered features 98 → 99 %, CNN 80 → 99 %.

![zone sweep](zone_sweep.png)

## What it says

**1. The auxiliary signal helps the learned detector and hurts the conventional one.** The CNN
climbs from 0.982 to 1.000 AUC and its dependability from 80 % to 99 %. Over the same sweep
the distance element falls from 0.952 to 0.863 AUC, monotonically and far outside the seed
spread, and its dependability peaks at 84 % for a small signal before dropping to 68 % at the
certified δ. **More signal makes the textbook distance element worse.** Injected
negative-sequence current distorts the very quantity that element is built on.

That is a result with a practical consequence: **this scheme cannot be dropped into an
existing relay's impedance element.** Cashing in the guarantee means changing the relay, not
only the inverter. Anyone proposing auxiliary signals should measure what they do to the
elements already in service.

**2. Engineered features are at ceiling from the start and do not need the signal.** Logistic
regression on sequence magnitudes, the i⁰/i⁻ and i⁻/i⁺ ratios, relative angles, the
k0-compensated loop impedances and their incremental versions sits at 0.995 AUC with no
injection at all. Deep learning is not the contribution here; the right quantities are. The
CNN only catches up once the signal is large.

**3. The learned detector's gain is real but it is a gain over its own handicap.** It starts
0.014 AUC behind the engineered features and ends level. The honest reading is that the signal
compensates for the CNN having to learn the sequence transform from raw samples, not that
learning beats engineering.

## Honest caveats

- Static phasor circuit synthesised into waveforms, not EMT. No inverter dynamics, no current-limiter action, no CT saturation, no travelling waves. This is the main limitation and the reason to move to public EMT data.
- Three buses, two fault types, one adjacent line.
- The reactance element is a genuine implementation (six loops, k0 compensation, faulted-phase selection from incremental currents, forward loops only, smallest reactance wins). On real EMT data it locates bolted faults within 1.5 % of the line for all five fault types ([REAL_DOUBLELINE.md](REAL_DOUBLELINE.md)). Report the AUC, not the 1 % operating point, when comparing.
- The CNN is small, about 40 k parameters, 20 epochs per point, untuned.
- Detection is offline over a fixed post-event window. Latency is the WP4 question and is not measured here.
- Three seeds. Enough to see that the reactance trend is real; not enough for a tight confidence interval.

## Corrections

An earlier version of this file reported detection rates of 96.0 → 99.4 % for the engineered
detector and described the reactance element as flat near 1 %. Those numbers came from a run
in which **the ground fault loops had no zero-sequence (k0) compensation**, which reads the
wrong impedance by a large factor and made the conventional baseline a straw man. The element
was fixed (k0 = (Z₀ − Z₁)/(3Z₁), applied as I_p + k0·3I₀, validated against m·X₁ for bolted
faults), per-loop current supervision was added, reporting moved to AUC with seed spread, and
the full sweep was re-run. The table above is the corrected result. The direction of the main
finding survived the fix; the magnitudes did not.

**17 Sep 2026.** A second flaw was found by running the element on real EMT data: it had no
faulted-phase selection, so any loop passing a crude current supervision could vote, and a
healthy phase-to-phase loop could win with a small spurious reactance. On EvEMTBench that
gave 40 % zone-1 trips at 99 % of the line. With phase selection added and this sweep re-run,
the distance-element column moved from 0.834 → 0.741 to **0.952 → 0.863**. The conventional
baseline is considerably stronger than first reported; the downward trend with δ survived.
The other three columns are unchanged within noise.

## Next

1. Done for the no-inverter control arm ([REAL_DOUBLELINE.md](REAL_DOUBLELINE.md)). Next, an EvEMTBench grid that actually contains inverters.
2. Add the multiple-model Kalman filter from Pirani et al. 2022 as a fourth detector.
3. Give the learned detector a sequence-domain front end and see whether the δ = 0 gap closes.
4. More seeds, and a proper confidence interval on the reactance trend.
