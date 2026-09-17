# Dataset fact sheet (EvEMTBench DoubleLine and TestGrid110kV, as cached in `data/`)

Script: `src/dataset_facts.py` → [DATASET_FACTS.json](DATASET_FACTS.json). Follow-ups: `src/review/h30_resampling.py`,
`h30_relay_frontend.py`, `h25_shortcut.py`, `h25_leak_edge.py`, `h10_trigger.py`. Every number below is read from the
caches or the three raw `result*.csv` files, not from the repository's markdown.

Changes to the template script: `flt_1phg_shc_w_arc` also matches `shc` (counted as a short circuit, as `real_ml.py`
does); per-relay facts for the three relays (A and B share one cache); exact-duplicate test for three-phase
siblings; the ADC check also reports the peak-to-pre-fault ratio.

## 1. What varies across simulations

| | DoubleLine | TestGrid110kV |
|---|---|---|
| Simulations | 1,101 | 2,435 |
| Label columns that vary | event type (15), target (7), location (1/20/50/80/99 %), R_f (1/10/40 Ω), phase selections | event type (16), target (15), location, R_f, phase selections |
| Constant | `event_start` 1.1 s, 50 Hz, 110 kV, HIF resistance, arc parameters, `event_iflt_duration` | same |
| Loading, source strength, inverter set-point, point-on-wave inception | **no column exists** | **no column exists** |
| Short circuits / incipient / switching | 1,035 / 42 / 24 | 2,295 / 90 / 50 |

There is one operating point per grid (H23). Inception is at 1.1 s in every record, so the point-on-wave angle is fixed
per faulted phase (H10). Pre-fault waveforms of all fault simulations differ by at most 0.12 V (DoubleLine),
0.20 V (A) and 0.26 V (B) peak-to-peak, i.e. 1–3·10⁻⁶ of nominal: that is the fingerprint the shortcut control
detects, about ten times larger than the 0.01 V that REAL_ML.md §3 quotes. Three switching types start from a different
network state (`switch_cap_off` 1.6–2.3 kV pre-fault offset, `switch_load_off` 10–13 V, `switch_ohl_off` 25–34 V);
the others share the fault simulations' pre-fault state.

## 2. The zone task is a full factorial with identical siblings (H22)

Per relay: 180 in-zone cases = 4 locations × 5 fault types × 3 R_f × 3 phase selections; out-of-zone 225 (DoubleLine),
315 (A), 135 (B). Every sibling group (target, location, type, R_f) has exactly 3 members.

| Share of test cases with a sibling in the training fold | DoubleLine | A | B |
|---|---|---|---|
| RepeatedStratifiedKFold 5×2 (`real_ml.within_relay_zone`) | 95.2 % | 96.4 % | 94.8 % |
| GroupKFold by sibling group | 0 % | 0 % | 0 % |

Three-phase siblings are **bit-identical** simulations (maximum relative difference 0.0 in 24, 30 and 18 groups): the
"phase selection" label has no physical meaning for a symmetrical fault. Under stratified CV a third of the
three-phase test cases have an exact copy in training, separated only by the measurement-chain noise draw. Rates in the
review count these copies once (`common.dedup_rate`).

## 3. Units (H12)

Pre-fault phase-voltage peak 92,966 V (DoubleLine), 91,047 V (A), 89,489 V (B) against 89,815 V for 110 kV primary;
current peaks 460–650 A. The records are **primary** quantities. The channel names `c:Usec:*` / `c:Isec:*` are
misleading, but `V_NOM_PEAK = 110 kV·√(2/3)` and the reach in primary ohms are correct.

## 4. Fault-detector labels (H28)

`fault_any = event_type.startswith("flt")` covers 1,077 (DoubleLine) and 2,385 (TestGrid) episodes, of which 42 / 90
are incipient faults, and only 744 (DoubleLine), 975 (A) and 513 (B) are on the relay's own line, its remote bus or
the lines beyond it. Most stage-1 positives are faults the relay is not responsible for.

## 5. Measurement-chain ADC (H30)

`real_ml.measurement_chain` sets current full scale to ±40 × the largest pre-fault peak of that relay (21.9 kA,
20.2 kA, 28.7 kA). Clipped in-zone simulations: 13 (DoubleLine) and 14 (A), all at 1 % and 20 % of the line
(peaks up to 57× and 64× pre-fault); 0 at B (peak ≤ 27×).

## 6. Timing and front end (H10, H30)

- `evemt.py` resamples 9600 → 6400 Hz with `resample_poly`, which is zero-phase. On the three raw DoubleLine records
  (bolted AG faults at 1, 20, 50 %) the fault leaks backwards **1.1–1.4 ms** before inception, at 43–56× the
  measurement-noise σ one sample before (`h30_resampling.json`).
- That leak carries zone information. Gradient boosting given only the 40 ms that **end at inception** separates
  in-zone from out-of-zone with AUC 0.967 (A), 0.83 (B) and 0.948 (DoubleLine) at the default 0.1 % noise. With the
  window ending 0.47 / 0.94 / 1.41 / 2.03 / 5.0 ms before inception, AUC at A is 0.892 / 0.703 / 0.497 / 0.519 / 0.498
  (`h25_leak_edge.json`). REAL_ML.md's control ended 5 ms early and could not see it.
- A relay-bandwidth front end (causal 3rd-order Butterworth, 400 Hz, an assumption) applied to the cached records
  matches causal filtering before decimation within 0.2 % in the 10 and 20 ms phasors and leaves 0.18–0.32 σ of leak
  (`h30_relay_frontend.json`). The review re-runs models and ladder on both front ends.
- A causal superimposed-current starter fires a median 0.16 ms (95th percentile 0.94 ms) after inception on in-zone
  faults at relay B and starts on 24 % of switching events (`h10_trigger.json`).

## 7. What this changed in the review

1. Within-relay CV had to be grouped (H22); deduplicated counts are used for every per-class rate.
2. The benchmark cannot test operating-point robustness, load encroachment or point-on-wave variation (H23): these are
   listed as requirements for the project's own EMT data.
3. The shortcut control had to be extended to the window edge; the resampling look-ahead is exploitable and is removed
   by a relay front end (H25, H30).
4. Stage 1 needs a responsibility-based label (H28).
