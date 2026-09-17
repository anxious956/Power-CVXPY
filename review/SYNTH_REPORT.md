# Synthetic detection pipeline: adversarial ML-evaluation review

Reviewed commit `321e12b` (origin/main). Branch `review-synth`, worktree
`Power-CVXPY-synth`. Scope: `src/waveforms.py`, `src/detect.py`, `src/zone_model.py`,
`src/zone_detect.py`, `results/DETECTION.md`, `results/ZONE.md`, README "Second result".

Line numbers under **Location** refer to `321e12b`. Every number is followed by the
command that produced it and the JSON file (under `results/review_synth/`) and key that holds
it. Environment: Python 3.12.10, numpy, scikit-learn 1.9.1, torch 2.5.1+cu121, RTX 3050 Ti
4 GB shared with other review jobs (CPU at 100 % most of the run), `OMP_NUM_THREADS=4`.
"quick" = `zone_detect.py --quick` sizes: 350 train / 250 test per fault kind (1400 / 1000
waveforms), deltas 0, 0.1, 0.3, 0.514, 3 seeds, 12 CNN epochs. "full" = default sizes: 900 / 450
per kind (3600 / 1800), 7 deltas, 3 seeds, 20 epochs.

Nothing below is UNVERIFIED except where marked: the "original, full size" column of the sweep
table is the author's `results/zone_sweep.json`, not re-run here (the |i-| column, which no fix
touches, reproduces it to all printed digits, which is evidence the data generation is identical).

## Findings summary

| ID | Verdict | Severity | One line |
|---|---|---|---|
| H17 | CONFIRMED (defect); no effect on published zone numbers | Low (published) / Medium (method) | Sign chosen on test detection rate; 0/36 zone flips (quick, reactance/\|i-\|/LR); in the fault-vs-load study it flips \|i-\| at 4/10 deltas and would report AUC 0.048 instead of 0.952 |
| H18 | PARTIAL | Low | In-sample LR thresholds overshoot the 1 % FAR (1.73-2.08 % vs 0.92-1.42 % OOF); the CNN is not memorising, and naive OOF made it worse until test scores came from the fold models |
| H19 | CONFIRMED | **High** | Per-waveform scaling handicapped the CNN: 0.971 -> 0.9998 AUC at delta = 0; corrected CNN is 1.000 at every delta, so "delta helps the CNN" and "engineered beats CNN" do not hold |
| H20/H10 | PARTIAL | Low | DC offset doubles the element's median distance error (0.28 -> 0.63 % of X1) but moves AUC by <= 0.005; +-2 ms trigger jitter changes nothing measurable |
| H21 | PARTIAL | Low | Wrap and noise-floor ratios are frequent (ang(i2/i1) near +-pi in 38-47 % of samples, \|i0\| < 1e-3 pu in 61 % of LL faults), no inf ever aliased; AUC change <= 0.0012 |
| H4 | PARTIAL | Medium | Incremental quantities do cancel delta (\|di-\| slope +0.015/pu vs -0.097/pu when delta switches on at the event), but the reactance decline is not that artefact: it uses total quantities |
| H9 | CONFIRMED | **High** | Excluding own-line faults at 85-100 % hides that the learned detectors trip on 27-56 % of them; as negatives, engineered AUC 0.994 -> 0.959, CNN 1.000 -> 0.980, reactance 0.954 -> 0.896 |
| H26 | CONFIRMED trend, with mechanism caveat | Medium | Reactance AUC(0.514) - AUC(0) = -0.086, 95 % CI [-0.096, -0.077] (full, corrected; paired bootstrap over seeds and samples); the drop is mostly a ground-loop vs phase-loop shift under one reach |
| H31 | CONFIRMED (docs) | Low | README ticks a withdrawn number, leaves "error bars over seeds" unticked; detect.py docstring describes negatives the default run does not draw |
| H33 | DONE | n/a | `tests/test_synth.py`, 15 tests, 2 fail on the original code |
| N2-synth | REFUTED on synthetic data | n/a | No synthetic sample reads negative X or the 10.0 default at any delta; separate directional element changes AUC by 0.000 |

## Corrected zone sweep (full size, 3 seeds)

Command (28 min 07 s on the shared GPU):
`python src/zone_detect.py --seeds 3 --out results/review_synth --tag zone_full_fixed`
(default cfg printed by the run: `oof_folds=5, oof_test='folds', cnn_norm='global',
fixed_features=True, mimic=True`, polarity chosen on train). Original column:
`results/zone_sweep.json` (author, UNVERIFIED re-run). Table built by
`python src/review/sweep_table.py results/zone_sweep.json results/review_synth/zone_full_fixed.json`.
Keys: `rows[i].<detector>.auc / auc_std / detection_rate / detection_std / false_alarm`.

AUC (mean +- sd over seeds), original -> corrected

| delta | reactance | \|i-\| | engineered+LR | CNN |
|---|---|---|---|---|
| 0.000 | 0.952 +- 0.005 -> 0.954 +- 0.005 | 0.594 +- 0.020 -> 0.594 +- 0.020 | 0.995 +- 0.000 -> 0.996 +- 0.000 | 0.982 +- 0.004 -> 1.000 +- 0.000 |
| 0.050 | 0.949 +- 0.005 -> 0.951 +- 0.005 | 0.587 +- 0.019 -> 0.587 +- 0.019 | 0.997 +- 0.001 -> 0.996 +- 0.001 | 0.989 +- 0.002 -> 1.000 +- 0.000 |
| 0.100 | 0.943 +- 0.005 -> 0.946 +- 0.005 | 0.581 +- 0.018 -> 0.581 +- 0.018 | 0.997 +- 0.001 -> 0.997 +- 0.001 | 0.994 +- 0.001 -> 1.000 +- 0.000 |
| 0.200 | 0.927 +- 0.008 -> 0.931 +- 0.007 | 0.568 +- 0.016 -> 0.568 +- 0.016 | 0.998 +- 0.001 -> 0.997 +- 0.001 | 0.998 +- 0.001 -> 1.000 +- 0.000 |
| 0.300 | 0.908 +- 0.009 -> 0.912 +- 0.009 | 0.559 +- 0.015 -> 0.559 +- 0.015 | 0.998 +- 0.001 -> 0.998 +- 0.001 | 0.999 +- 0.001 -> 1.000 +- 0.000 |
| 0.400 | 0.887 +- 0.009 -> 0.892 +- 0.010 | 0.551 +- 0.014 -> 0.551 +- 0.014 | 0.999 +- 0.001 -> 0.999 +- 0.001 | 0.999 +- 0.001 -> 1.000 +- 0.000 |
| 0.514 | 0.863 +- 0.009 -> 0.868 +- 0.010 | 0.543 +- 0.014 -> 0.543 +- 0.014 | 0.999 +- 0.001 -> 0.998 +- 0.001 | 1.000 +- 0.000 -> 1.000 +- 0.000 |

Corrected CNN AUC to 5 digits: 0.99999, 0.99998, 0.99998, 0.99998, 0.99997, 0.99997, 0.99995.

Dependability at 1 % FAR, % (realised test FAR %), original -> corrected

| delta | reactance | \|i-\| | engineered+LR | CNN |
|---|---|---|---|---|
| 0.000 | 73.6 +- 5.8 (1.07) -> 72.7 +- 6.0 (1.07) | 6.8 +- 0.3 (0.67) -> 6.8 +- 0.3 (0.67) | 98.1 +- 0.1 (1.59) -> 97.0 +- 0.3 (0.89) | 80.5 +- 4.3 (0.93) -> 99.9 +- 0.1 (0.11) |
| 0.050 | 80.7 +- 2.2 (0.85) -> 80.7 +- 2.5 (0.89) | 7.1 +- 0.5 (0.70) -> 7.1 +- 0.5 (0.70) | 98.3 +- 0.3 (1.37) -> 97.6 +- 0.2 (0.85) | 86.1 +- 2.8 (1.00) -> 99.9 +- 0.2 (0.30) |
| 0.100 | 83.8 +- 1.4 (0.93) -> 84.2 +- 1.2 (0.96) | 7.0 +- 0.4 (0.74) -> 7.0 +- 0.4 (0.74) | 98.5 +- 0.4 (1.30) -> 98.0 +- 0.3 (0.81) | 93.1 +- 2.6 (1.19) -> 99.6 +- 0.5 (0.22) |
| 0.200 | 80.7 +- 1.7 (0.85) -> 81.1 +- 1.7 (0.74) | 7.0 +- 0.6 (0.56) -> 7.0 +- 0.6 (0.56) | 98.9 +- 0.4 (1.19) -> 98.3 +- 0.3 (0.85) | 96.5 +- 2.2 (1.22) -> 99.8 +- 0.3 (0.11) |
| 0.300 | 76.8 +- 1.4 (0.89) -> 77.6 +- 1.7 (0.78) | 6.9 +- 0.4 (0.48) -> 6.9 +- 0.4 (0.48) | 99.1 +- 0.3 (1.11) -> 98.2 +- 0.4 (0.78) | 97.0 +- 3.1 (1.22) -> 99.5 +- 0.7 (0.07) |
| 0.400 | 72.4 +- 1.8 (0.78) -> 73.7 +- 1.1 (0.89) | 7.1 +- 0.8 (0.56) -> 7.1 +- 0.8 (0.56) | 99.3 +- 0.1 (1.15) -> 98.6 +- 0.4 (0.89) | 98.1 +- 1.4 (1.37) -> 99.2 +- 0.6 (0.07) |
| 0.514 | 68.0 +- 1.6 (0.70) -> 68.8 +- 1.4 (0.74) | 7.1 +- 0.8 (0.44) -> 7.1 +- 0.8 (0.44) | 99.3 +- 0.1 (0.96) -> 98.8 +- 0.2 (0.78) | 98.9 +- 0.4 (1.04) -> 99.2 +- 0.6 (0.04) |

The same comparison at quick size, both arms re-run here
(original arm `zone_quick_original`: `python src/zone_detect.py --quick --out results/review_synth --tag zone_quick_original`
run on commit 060d5b1 before any fix; `--legacy` on the final code is intended to reproduce it but was not re-run; corrected run `zone_quick_fixed`,
4 min 06 s; table: `python src/review/sweep_table.py results/review_synth/zone_quick_original.json results/review_synth/zone_quick_fixed.json`):

| delta | reactance | \|i-\| | engineered+LR | CNN |
|---|---|---|---|---|
| 0.000 | 0.953 +- 0.013 -> 0.954 +- 0.015 | 0.592 +- 0.011 -> 0.592 +- 0.011 | 0.994 +- 0.002 -> 0.994 +- 0.002 | 0.957 +- 0.015 -> 1.000 +- 0.000 |
| 0.100 | 0.945 +- 0.011 -> 0.947 +- 0.011 | 0.580 +- 0.010 -> 0.580 +- 0.010 | 0.995 +- 0.002 -> 0.995 +- 0.001 | 0.976 +- 0.006 -> 1.000 +- 0.000 |
| 0.300 | 0.911 +- 0.012 -> 0.915 +- 0.012 | 0.559 +- 0.008 -> 0.559 +- 0.008 | 0.995 +- 0.001 -> 0.995 +- 0.001 | 0.993 +- 0.002 -> 1.000 +- 0.000 |
| 0.514 | 0.865 +- 0.013 -> 0.870 +- 0.013 | 0.542 +- 0.007 -> 0.542 +- 0.007 | 0.998 +- 0.000 -> 0.996 +- 0.002 | 0.995 +- 0.002 -> 1.000 +- 0.000 |

Dependability at 1 % FAR (quick): reactance 72.8/83.7/77.3/69.5 -> 71.2/83.5/78.0/70.3; |i-| unchanged 6.3/6.3/6.7/7.4;
engineered 96.8/97.7/98.1/98.5 (FAR 1.80/2.00/2.47/1.73) -> 95.6/96.6/96.9/97.9 (FAR 1.20/1.00/1.53/1.67);
CNN 68.5/76.7/89.5/93.7 (FAR 1.27/1.13/1.53/1.87) -> 95.8/94.7/96.3/97.7 (FAR 0.00/0.00/0.13/0.13).

## Verdicts on the synthetic headline claims

**"The auxiliary signal helps the learned detector and hurts the conventional one" -- DOES NOT
HOLD as stated.** The "hurts the conventional one" half holds (see next claim). The "helps the
learned detector" half is an artefact of H19: with one scale per channel fitted on train and the
CNN scored by its fold models, the CNN is at 0.99999 AUC and 99.9 % dependability at delta = 0 and
stays there (0.99995, 99.2 % at 0.514; `zone_full_fixed.json`). Gradient boosting on the
engineered features is also 0.9996 at delta = 0 (`h19_ceiling_check.json`), and a pre-event-only
leak check is at chance (0.47-0.49), so the ceiling is real physics of this generator, not a leak.
There is nothing left for the signal to add for the learned detector.

**"CNN 0.982 -> 1.000" -- DOES NOT HOLD.** Corrected: 0.99999 -> 0.99995 (full), 0.9998 -> 0.9998
(quick). The 0.018 gap at delta = 0 came from per-waveform standardisation (quick, fold-model
scoring: 0.971 per-waveform vs 0.9998 global, `h19_cnn_norm.json`).

**"Reactance 0.952 -> 0.863" -- HOLDS WITH CAVEAT.** Corrected full size 0.954 -> 0.868 (the H20
mimic filter adds +0.002 to +0.005). The decline is far outside sampling noise: quick corrected
AUC(0.514) - AUC(0) = -0.084, 95 % CI [-0.103, -0.069] (paired two-level bootstrap over seeds and
test samples, `h26_bootstrap_zone_quick_fixed.json`); full size corrected -0.0857, 95 % CI
[-0.0956, -0.0770], slope -0.170 [-0.191, -0.151] per pu (`h26_bootstrap_zone_full_fixed.json`). Caveats: (1) it is mostly a
cross-fault-type effect of one reach for both loop types. Within AG-vs-AG2 the AUC falls only
0.931 -> 0.904 (full; 0.934 -> 0.912 quick) and within AB-vs-AB2 it rises 0.998 -> 1.000; the pooled drop comes from the
injection pushing ground-loop apparent reactance UP (in-zone AG median 0.894 -> 1.067 X1) and
phase-loop reactance DOWN (out-of-zone AB2 median 1.242 -> 1.113 X1). An element with separate
ground and phase reaches would lose about 0.03, not 0.09 (not simulated; inferred from the per-type AUCs). (2) It is on a band that excludes
85-100 % of the line (H9); with that band as negatives the element falls 0.896 -> 0.818.
(3) It is not caused by the reactance-sign direction test (N2) nor by the pre/post cancellation (H4).
"Monotonically" holds at all seven deltas in both runs.

**"Engineered features at ceiling" -- HOLDS WITH CAVEAT.** LR on engineered features is
0.996-0.999 corrected (full). It is below the corrected CNN (0.99999) and gradient boosting on the
same features (0.9996), and the ceiling is a property of the sampled band: with own-line faults at
85-100 % as negatives it drops to 0.959 (delta = 0) and it trips 48.6 % of those faults as in-zone
at its 1 % FAR operating point (`h9_band.json`).

**"Engineered beats CNN" -- DOES NOT HOLD.** Corrected, the CNN is ahead at every delta
(0.99999 vs 0.996 at delta = 0; dependability 99.9 % vs 97.0 %). The README sentence "beats the
CNN everywhere until the signal is large" was produced by the H19 handicap. On the H9 band the CNN
is also ahead (AUC 0.980 vs 0.959) but trips 27.4 % of 85-100 % faults.

Related claim in the README "Second result" (fault vs load): "a magnitude threshold on negative
sequence is useless there and *more signal makes it worse*" -- HOLDS WITH CAVEAT only at the 1 %
FAR operating point (dependability 0-17.6 %, reproduced exactly). By AUC with the polarity chosen on
train, more signal makes |i-| far better: 0.563 at delta = 0, 0.899 at 0.2, 0.980 at 0.3, 0.952 at
0.514 (`h17_detect_full.json`); faults move to LOWER |i-| than the confuser.

---

## H17 -- polarity chosen on the test set

- **Verdict:** CONFIRMED (defect). The sub-claim "with a test-chosen sign an AUC can never be
  < 0.5" is REFUTED: the rule selects on test detection rate and keeps +1 on ties, so it did
  report AUC < 0.5.
- **Severity:** Low for the published zone and detection numbers (unchanged); Medium as method,
  because `real_zone.py:165-170` uses the same function.
- **Location:** `src/detect.py:107-132` (`dr` at :125 uses `s_te`); used by `zone_detect.py:194-200`,
  `detect.py` main, `real_zone.py:165-170`.
- **What the code does:** tries sign +1 and -1, sets the threshold on train, and keeps the sign whose
  TEST detection rate is higher; reports test AUC with that sign.
- **Why wrong:** the docstring promises polarity fixed on train; choosing on test is selection on the
  evaluation data, and when both detection rates tie (common at 0 %) the reported AUC is whatever
  +1 gives, which can be far below 0.5 for a detector that is actually good the other way round.
- **Evidence:**
  - Zone study, quick, 3 seeds, original scoring, `python src/review/h17_polarity.py` (5 min 19 s,
    CPU): sign differs in 0 of 36 (delta, seed, detector) cases for reactance, |i-| and engineered;
    all AUC and dependability identical (`h17_polarity.json`, `zone[*].test_sign / train_sign`). The
    CNN arm was not run here (first attempt with the CNN took 30 min 26 s for one delta on the
    shared GPU and was stopped); in the corrected sweeps the CNN's train-chosen sign is +1 in 12/12
    quick and 21/21 full (delta, seed) runs with AUC >= 0.9992 and >= 0.9999, so no flip is possible;
    reactance is -1 and engineered / |i-| +1 in every run.
  - Fault vs load, quick sizes, 3 seeds (same script, `detect[*]`): |i-| sign differs 3/3 at
    delta 0.1 (AUC 0.450 -> 0.550) and 3/3 at 0.2 (0.107 -> 0.893); detection unchanged (0.0 %).
  - Fault vs load at DETECTION.md's exact data (`python src/review/h17_detect_full.py`, 3 min 24 s,
    `h17_detect_full.json`, `rows[*]`): detection rates reproduce the author's JSON exactly (|i-|
    0.2 % / 17.6 % / 8.6 % at delta 0.2 / 0.3 / 0.4 with sign -1). The sign differs at 4/10 deltas
    for |i-|: 0.075 (AUC 0.480 -> 0.520), 0.10 (0.448 -> 0.552), 0.15 (0.359 -> 0.641), 0.514
    (0.048 -> 0.952); detection 0.0 % both ways, FAR 1.7 -> 0.9, 1.7 -> 0.4, 1.8 -> 0.7, 1.4 -> 0.9 %.
    |di-| never differs.
- **Fix:** `evaluate(..., polarity="train")` (default): sign = +1 if train AUC >= 0.5 else -1;
  test metrics and AUC reported with that sign; `auc_train` added; `polarity="test"` reproduces
  the old rule. Commits 2f0cd3a, 1850412, 5ac311c. Test:
  `test_evaluate_chooses_polarity_on_train_not_test`.
- **Before -> after:** zone sweep: no change in any published number. Fault vs load |i-| AUC at
  delta 0.514: 0.048 -> 0.952 (not published; detection 0.0 % both).

## H18 -- in-sample thresholds for LR and CNN

- **Verdict:** PARTIAL. Real for LR, small; not material for the CNN, and the obvious OOF fix
  (threshold from fold models, test scored by a separately trained full model) is worse for the CNN.
- **Severity:** Low.
- **Location:** `src/detect.py:73-82` (`decision_function(ftr)` at :82), `src/detect.py:174`
  (`s_tr = model(xt)`), `src/zone_detect.py:144-151` (:151).
- **What the code does:** the 1 % FAR threshold is the 99th percentile of the model's scores on its
  own training negatives.
- **Why wrong:** a fitted model scores its training negatives lower than new negatives, so the
  threshold is too low and the realised FAR exceeds the budget.
- **Evidence:** `python src/review/h18_oof.py` (5 min 59 s; zone quick and fault-vs-load quick,
  deltas 0 / 0.514 and 0 / 0.4, 3 seeds; `h18_oof.json`, `rows[study, delta, det, variant]`), test
  FAR at the 1 % budget and dependability:

  | study, delta | LR in-sample | LR OOF | CNN in-sample | CNN OOF, full-model test | CNN OOF, fold-model test |
  |---|---|---|---|---|---|
  | zone 0 | 1.80 %, 96.8 % | 1.33 %, 95.2 % | 1.27 %, 68.5 % | 2.40 %, 69.8 % | 0.47 %, 68.5 % |
  | zone 0.514 | 1.73 %, 98.5 % | 1.27 %, 98.3 % | 1.87 %, 93.7 % | 0.00 %, 68.9 % | 0.07 %, 91.0 % |
  | detect 0 | 2.08 %, 99.2 % | 1.42 %, 98.5 % | 1.00 %, 96.6 % | 0.50 %, 83.9 % | 0.50 %, 97.5 % |
  | detect 0.4 | 1.17 %, 100 % | 0.92 %, 100 % | 1.33 %, 100 % | 6.42 %, 99.3 % | 1.00 %, 100 % |

  (CNN here with the original per-waveform scaling.) In the corrected full sweep the engineered
  detector's realised FAR is 0.78-0.89 % (was 0.96-1.59 %) and dependability 0.5-1.1 pp lower.
- **Fix:** `fit_lr_scores(..., oof_folds=5)` and `train_cnn(..., oof_folds=5, oof_test="folds")`:
  5-fold stratified out-of-fold training scores set threshold and polarity; the CNN's test scores
  are the mean logit of the same 5 fold models. Commits 3a9b64d, bd23719. Tests:
  `test_lr_training_scores_are_out_of_fold`, `test_zone_pipeline_default_uses_oof_thresholds`
  (both fail on the original code).
- **Before -> after:** see the tables above (engineered FAR 1.59 -> 0.89 % at delta 0, full).

## H19 -- CNN standardises each waveform and channel by itself

- **Verdict:** CONFIRMED.
- **Severity:** High: it produced two headline claims.
- **Location:** `src/detect.py:141-144`.
- **What the code does:** `(X - X.mean(axis=2)) / X.std(axis=2)` per sample and channel.
- **Why wrong:** divides away the absolute voltage and current magnitudes and the V/I ratio, i.e.
  the apparent impedance a distance decision rests on; the net must recover it from waveform shape.
- **Evidence:**
  - `python src/review/h19_cnn_norm.py --deltas 0 0.514` (4 min 00 s; quick, 3 seeds, OOF with
    fold-model test scores; `h19_cnn_norm.json`, `rows[delta, seed, norm]`): delta 0: per-waveform
    0.9710 +- 0.0016 AUC, 68.5 % dependability (FAR 0.47 %) vs global 0.9998 +- 0.0000, 95.8 %
    (FAR 0.00 %). delta 0.514: 0.9990 +- 0.0001, 91.0 % vs 0.9998 +- 0.0002, 97.7 %.
    Delta's gain for the CNN: +0.028 AUC per-waveform, +0.000 global.
  - Single full-data net with global scaling (`zone_quick_fixed_ooffull.json`, `rows[*].cnn.per_seed`):
    delta 0 seeds 0.9979 / 0.9995 / 0.9407: global scaling already removes most of the gap; the
    fold ensemble removes the unstable seed.
  - Full corrected sweep: CNN 0.99999 at delta 0 and 0.99995 at 0.514 (`zone_full_fixed.json`).
  - Plausibility: `python src/review/h19_ceiling_check.py` (3 min 11 s, `h19_ceiling_check.json`):
    gradient boosting on the engineered features 0.9996 +- 0.0002 (delta 0) and 0.9996 +- 0.0001
    (0.514); LR 0.9939 / 0.9959. Leak check on pre-event data only: phasor features 0.4706 / 0.4853,
    raw samples 0.4877 / 0.4875 (chance).
- **Fix:** `train_cnn(norm="global")`: one offset and scale per channel fitted on the training fold
  (as `real_ml.ChannelScaler`). Commit 8ff6ec9.
- **Before -> after:** full sweep CNN AUC 0.982 -> 1.000 at delta 0 (dependability 80.5 -> 99.9 %);
  "delta helps the CNN" and "engineered beats CNN" do not survive (see verdicts).

## H20 / H10 -- oracle event index, one-cycle DFT, no mimic filter

- **Verdict:** PARTIAL. The measurement chain is idealised, but its effect on the reported
  comparison is small.
- **Severity:** Low.
- **Location:** `src/zone_detect.py:82-85` (`_phasors`, windows anchored at the true `EVENT`);
  `src/waveforms.py:118-123` (DC offset 0.3 x the sample-to-sample jump, tau 1.5 cycles; note the
  "jump" includes one sample of normal sinusoid slope, not only the step); `waveforms.py:150-154`.
- **Why it matters:** a decaying exponential is not rejected by a one-cycle DFT; a real relay
  also does not know the fault inception sample.
- **Evidence:** `python src/review/h20_dc_trigger.py` (15 min 42 s, CPU; `h20_dc_trigger.json`,
  `error[*]` and `auc[*]`). Distance error of the element against the noise-free reactance of the same
  fault, % of X1, median |error| / p95, delta 0 (0.514 in brackets):
  default (dc 0.3, noise, harmonics) 0.63 / 2.04 (0.71 / 2.58); dc 0 0.28 / 0.98 (0.28 / 1.01);
  dc 0.3 + mimic 0.33 / 1.38 (0.34 / 1.66); dc 0.3 + jitter +-2 ms 0.68 / 2.32 (0.75 / 2.59);
  mimic + jitter 0.34 / 1.51. Without noise and harmonics the DC offset alone biases AB loops by
  -0.86 % X1 and AG by +0.24 % (delta 0); a matched mimic filter reduces that to 0.01 %.
  Element AUC (quick, 3 seeds): delta 0: 0.9529 default, 0.9544 dc 0, 0.9540 mimic, 0.9529 jitter;
  delta 0.514: 0.8649, 0.8698, 0.8696, 0.8650. Dependability at 1 % FAR moves by at most 1.6 pp.
  Jitter is harmless here because the post-event window starts a full cycle after the event, so a
  +-15 sample shift never straddles the inception.
- **Not measured:** decisions inside the first cycle (latency), where anchoring matters most.
- **Fix:** `mimic_filter` (tau from the line X/R = 203.7 samples; phasor divided by the filter's
  complex gain) and per-sample trigger offsets in `_phasors`/`score_reactance`; mimic on by default
  in the corrected pipeline. Commit c593bc4 (+ bd23719 default). Test:
  `test_mimic_filter_removes_decaying_dc`.
- **Before -> after:** reactance AUC 0.952 -> 0.954 (delta 0), 0.863 -> 0.868 (0.514), full sweep.

## H21 -- raw angles and epsilon ratios in the engineered features

- **Verdict:** PARTIAL. The defects occur often; they do not change results.
- **Severity:** Low.
- **Location:** `src/zone_detect.py:118-141` (angles :137-139 and `np.angle(zg)`, `np.angle(zp)`;
  ratios :136, :140; `nan_to_num(posinf=0)` :141); `src/detect.py:49-70` (:65-70).
- **Evidence:** `python src/review/h21_features.py` (11 min 16 s, CPU; `h21_features.json`,
  `defects` and `auc`). Zone quick, 1400 samples: ang(i2/i1) has |angle| > 0.9 pi in 38.2 % (delta 0)
  and 46.6 % (0.514) of samples, with at least 4.1 % / 15.6 % on each side of the wrap; ang(zg)
  3.7 % on each side at 0.514. |i0| < 1e-3 pu in 60.6 % of AB and 61.4 % of AB2 faults, |dI0| < 1e-3
  in 36.6 % / 40.0 %: the i0 ratios and angles of LL faults are noise; |dv0/di0| median 0.94, max
  44.5. Non-finite values before `nan_to_num`: 0 (e = 1e-9 prevents inf, so posinf -> 0 never fires).
  Fault vs load: angle columns beyond 0.9 pi in up to 14.9 %.
  LR AUC with OOF thresholds, original -> fixed features: zone 0.9936 -> 0.9939 (delta 0), 0.9947 ->
  0.9955, 0.9950 -> 0.9957, 0.9980 -> 0.9970 (0.514); fault vs load 0.9986 -> 0.9998 (0), >= 0.9991
  -> >= 0.9998 elsewhere. Dependability changes <= 1.1 pp.
- **Fix:** `zone_features(fixed=True)` / `relay_features(fixed=True)`: angles as sin and cos of
  angle(a conj(b)), ratios as log((|a| + 1e-3) / (|b| + 1e-3)). Commit 50d403d.
- **Before -> after:** engineered AUC 0.995 -> 0.996 (delta 0), 0.999 -> 0.998 (0.514), full sweep.

## H4 -- delta identical before and after the event

- **Verdict:** PARTIAL. The cancellation is real and measurable; it is not what drives the
  headline reactance trend.
- **Severity:** Medium (a modelling choice that decides which detectors can see delta at all).
- **Location:** `src/zone_detect.py:61-62` (same `delta` in the pre and post solves);
  `src/waveforms.py:63-98`.
- **Evidence:** `python src/review/h4_incremental.py` (11 min 56 s, CPU; `h4_incremental.json`,
  `summary["<variant>|<detector>"]`). AUC at delta 0 / 0.1 / 0.3 / 0.514, slope per pu:

  | detector | continuous (original) | slope | switched on at event | slope |
  |---|---|---|---|---|
  | reactance (totals) | 0.953 / 0.945 / 0.911 / 0.865 | -0.174 | 0.953 / 0.945 / 0.839 / 0.713 | -0.487 |
  | \|i-\| (total) | 0.592 / 0.580 / 0.559 / 0.542 | -0.097 | identical | -0.097 |
  | \|di-\| (incremental) | 0.592 / 0.596 / 0.601 / 0.600 | +0.015 | 0.592 / 0.581 / 0.559 / 0.542 | -0.097 |
  | LR all features | 0.994 / 0.995 / 0.996 / 0.997 | +0.005 | 0.994 / 0.995 / 0.995 / 0.997 | +0.006 |
  | LR total-only | 0.993 / 0.995 / 0.995 / 0.997 | +0.007 | 0.993 / 0.995 / 0.996 / 0.997 | +0.007 |
  | LR incremental-only | 0.905 / 0.902 / 0.897 / 0.886 | -0.036 | 0.905 / 0.907 / 0.906 / 0.907 | +0.005 |

  Incremental quantities are flat by construction under continuous injection (|di-| +0.007) and
  track the total when the signal is switched on at the event. The reactance element reads total
  quantities, so its -0.088 is not a cancellation artefact; if the signal were switched on at the
  event it would fall 2.7x faster (-0.240), because phase selection uses incremental currents that
  then contain delta.
- **Fix:** none applied (modelling choice); `generate(delta_pre=...)` option added (commit c593bc4).
  ZONE.md should state that incremental elements are blind to a continuously injected delta.

## H9 -- the 85-100 % band of the protected line is never sampled

- **Verdict:** CONFIRMED.
- **Severity:** High for the "at ceiling" and "engineered beats CNN" readings; the reach decision is
  exactly about that band.
- **Location:** `src/zone_detect.py:56-59` (positives m in [0.62, 0.85], negatives m in
  [0.02, 0.18] of the adjacent line).
- **Evidence:** `python src/review/h9_band.py` (5 min 58 s; quick, 3 seeds, corrected pipeline;
  `h9_band.json`, `rows[eval, delta, det]`).
  (a) Band [0.85, 1.0] as don't-care, fraction tripped at the 1 % FAR operating point, delta 0 (0.514):
  reactance 15.5 % (43.8 %); |i-| 2.7 % (3.8 %); engineered 48.6 % (55.5 %); CNN 27.4 % (32.9 %).
  For m in [0.925, 1.0] only: reactance 8.5 % (35.6 %), engineered 30.2 % (37.6 %), CNN 5.9 % (10.7 %).
  (b) Band as negatives, AUC and dependability, delta 0 (0.514): reactance 0.896, 34.7 % (0.818,
  51.9 %); |i-| 0.554 (0.527); engineered 0.959, 56.6 % (0.974, 67.6 %); CNN 0.980, 47.7 %
  (0.981, 54.3 %).
- **Fix:** none to the default experiment; `m_range` option and the script added (commits c593bc4,
  72e7cf4). The study should report (a) or (b) next to the boundary-band numbers.
- **Before -> after:** engineered AUC 0.994 -> 0.959, CNN 1.000 -> 0.980, reactance 0.954 -> 0.896
  at delta 0 when the band is counted as out of zone.

## H26 (synthetic) -- confidence interval on the reactance trend

- **Verdict:** CONFIRMED that the trend is outside sampling noise, before and after H17; with the
  mechanism caveat in the verdicts section.
- **Severity:** Medium (the claim is right, its explanation in ZONE.md is incomplete).
- **Location:** `results/ZONE.md:58-59, 86`; README.md:74.
- **Evidence:** `python src/review/h26_bootstrap.py <tag> --B 2000` (paired two-level bootstrap:
  seeds with replacement, then test samples within seed stratified by class, same indices at every
  delta; `h26_bootstrap_<tag>.json`, `<tag>.reactance.diff_ci / slope_ci / auc_ci`).
  - quick original (2 min 36 s): AUC 0.953 [0.935, 0.967] -> 0.865 [0.846, 0.885]; difference -0.0881
    [-0.1062, -0.0724]; slope -0.174 [-0.210, -0.144] per pu; P(diff < 0) = 1.000.
  - quick corrected (2 min 34 s): 0.954 [0.935, 0.969] -> 0.870 [0.851, 0.890]; difference -0.0844
    [-0.1026, -0.0685]; slope -0.167 [-0.202, -0.136]; P = 1.000.
  - full corrected (4 min 53 s): 0.954 [0.945, 0.962] -> 0.868 [0.854, 0.882]; difference -0.0857
    [-0.0956, -0.0770]; slope -0.170 [-0.191, -0.151]; P = 1.000. Per type (full): AG vs AG2
    0.931 -> 0.904, AB vs AB2 0.998 -> 1.000. Engineered +0.0020 [-0.0000, +0.0039]; CNN -0.00003
    [-0.0001, -0.0000] (at 0.99999).
  - the H17 fix cannot change it: reactance's sign is -1 in every seed and delta in both rules.
  - By fault-type pair (quick corrected, `auc_by_kind_pair`): AG vs AG2 0.934 / 0.939 / 0.933 / 0.912;
    AB vs AB2 0.998 / 0.999 / 1.000 / 1.000. Median apparent reactance in X1 units, delta 0 -> 0.514
    (from `zone_quick_fixed_scores.npz`): AG 0.894 -> 1.067, AB 0.838 -> 0.740, AG2 1.513 -> 1.836,
    AB2 1.242 -> 1.113.
  - For comparison the same bootstrap on the other columns (quick corrected): engineered +0.0020
    [-0.0019, +0.0065] (P(diff < 0) = 0.174, no trend); CNN +0.0000 [-0.0002, +0.0002].
    Quick original: CNN +0.0379 [+0.0250, +0.0547]; engineered +0.0044 [+0.0015, +0.0079].
- **Fix:** none needed for the number; ZONE.md's explanation should mention the opposite shifts of
  ground and phase loops and report per-type AUC.

## H31 -- documentation inconsistencies (verified, not edited except one docstring)

- **Verdict:** CONFIRMED. **Severity:** Low.
- `README.md:214`: "- [x] Measured that the auxiliary signal improves multivariate detection, 96.0
  to 99.4 %". `results/ZONE.md:90-92` withdraws exactly those numbers ("An earlier version of this
  file reported detection rates of 96.0 -> 99.4 % ... came from a run in which the ground fault
  loops had no zero-sequence (k0) compensation"). With the corrections, engineered detection is
  97.0 -> 98.8 % (full) and the "improves" direction for the engineered detector is +0.002 AUC.
- `README.md:215`: "- [ ] Error bars over seeds" is unticked although `zone_detect.py` runs 3 seeds by
  default and README:63-68 and ZONE.md:132-138 print +- sd over seeds.
- `src/detect.py:15-17` (docstring): "Negatives are half 'quiet' (normal, balanced load step) and half
  events that themselves create negative sequence (unbalanced load switching, motor start)". The
  default run calls `make_dataset(..., hard=not args.easy)` (`detect.py:214-215`), and
  `waveforms.py:174-182` draws for hard=True only `unbalanced_load` (3 of 4) and `load_step` (1 of 4):
  no motor start, no normal. `detect.py:4` says "Three detectors" but four are run.
- Fix: detect.py docstring corrected (commit c17db9e). README and ZONE.md left to the author.

## H33 -- tests

`tests/test_synth.py` (commit 05576f9), `python -m pytest tests/test_synth.py -q`: 15 passed in
~8 s on the corrected code; on `321e12b`-equivalent code 2 fail
(`test_zone_pipeline_default_uses_oof_thresholds`, `test_detect_defaults_are_fixed`). Contents:
sequence_phasors recovers a known [s0, s+, s-] exactly (atol 1e-12); evaluate() polarity from train
when train and test disagree (and documents that the old rule reported AUC > 0.95 for the wrong
direction); phase_selected_reactance within 1 % of m X1 for bolted AG and AB faults from
`zone_model.solve_zone` at m = 0.3, 0.7 (sequence path) and m = 0.6 through waveform synthesis
and the DFT; bolted ABG at m = 0.3, 0.7 on a radial source-line network solved in the test
(solve_zone has no LLG fault); LR training scores out of fold (in-sample AUC > 0.95 vs OOF < 0.8 on
pure noise); zone pipeline default uses OOF; mimic filter recovers a phasor under a decaying DC
offset to 1e-4 while the unfiltered DFT is off by > 1e-2.

## N2-synth -- reactance sign used as the direction test

- **Verdict:** REFUTED on the synthetic data (the mechanism exists in code but is never exercised).
- **Location:** `src/zone_model.py:206-207`.
- **Evidence:** `python src/review/n2_directional.py` (2 min 19 s, CPU; quick, 3 seeds, test sets;
  `n2_directional.json`, `rates[*]` and `summary`). At delta 0, 0.1, 0.3, 0.514 and for every kind
  (AG, AB, AG2, AB2): 0.0 % of samples scored 10.0 by the original element, 0.0 % with min X < 0
  over released loops, 100.0 % forward by the separate directional element, negative-sequence branch
  used in 100.0 % (|I2| >= 0.1 |dI1| always, since every fault is unbalanced). AUC, original /
  no sign test / separate directional element: 0.953 / 0.953 / 0.953, 0.945 / ..., 0.911 / ...,
  0.865 / 0.865 / 0.865; dependability 73 / 84 / 77 / 70 % in all three. So the decline is not driven
  by discarded negative-X loops, and delta does not bias the negative-sequence directional decision in
  this range. Limitation: the synthetic model has no reverse faults and rF <= 0.3 pu with a
  0.20 pu line, so neither the security of the directional element nor the real-data regime
  (40 ohm faults under strong remote infeed) is represented.
- **Code:** `released_loops`, `directional_forward`, `directional_reactance` added to
  `zone_model.py` without changing the original function (commit 92a4650).

## Run commands and runtimes

All from the worktree root, `OMP_NUM_THREADS=4`; CPU-only runs with `CUDA_VISIBLE_DEVICES=""`.
Runtimes are wall clock on a machine shared with other review jobs.

| command | runtime | output |
|---|---|---|
| `python src/zone_detect.py --quick --out results/review_synth --tag zone_quick_original` (commit 060d5b1, before fixes) | 1 min 22 s | zone_quick_original.* |
| `python src/review/h17_polarity.py` (first attempt with CNN, stopped) | 30 min 26 s for 1 of 9 deltas | none |
| `python src/review/h17_polarity.py` (CPU) | 5 min 19 s | h17_polarity.json |
| `python src/review/h17_detect_full.py` | 3 min 24 s | h17_detect_full.json |
| `python src/review/h21_features.py` | 11 min 16 s | h21_features.json |
| `python src/review/h20_dc_trigger.py` | 15 min 42 s | h20_dc_trigger.json |
| `python src/review/h4_incremental.py` | 11 min 56 s | h4_incremental.json |
| `python src/review/n2_directional.py` | 2 min 19 s | n2_directional.json |
| `python src/zone_detect.py --quick --mimic ... --tag zone_quick_fixed` (CNN test scored by the full model; superseded) | 7 min 48 s | zone_quick_fixed_ooffull.* (renamed) |
| `python src/review/h18_oof.py` | 5 min 59 s | h18_oof.json |
| `python src/zone_detect.py --quick --out results/review_synth --tag zone_quick_fixed` | 4 min 06 s | zone_quick_fixed.* |
| `python src/review/h19_cnn_norm.py --deltas 0 0.514` | 4 min 00 s | h19_cnn_norm.json |
| `python src/review/h19_ceiling_check.py` | 3 min 11 s | h19_ceiling_check.json |
| `python src/review/h9_band.py` | 5 min 58 s | h9_band.json |
| `python src/zone_detect.py --seeds 3 --out results/review_synth --tag zone_full_fixed` | 28 min 07 s | zone_full_fixed.* |
| `python src/review/h26_bootstrap.py zone_quick_original --B 2000` / `zone_quick_fixed` | 2 min 36 s / 2 min 34 s | h26_bootstrap_*.json |
| `python src/review/h26_bootstrap.py zone_full_fixed --B 2000` | 4 min 53 s | h26_bootstrap_zone_full_fixed.json |
| `python -m pytest tests/test_synth.py -q` | ~8 s | |

## Not done / limits

- The original full-size sweep was not re-run (author's JSON used); the quick original was.
- `detect.py` (fault vs load) was not re-run end to end with all fixes; H17, H18 and H21 were
  measured on it at quick size, and its |i-| / |di-| columns at full size.
- The CNN arm of H17 was not run (GPU contention); argued from the corrected sweeps' signs.
- `real_zone.py` also calls `evaluate` and `train_cnn`; the new defaults (train-chosen polarity, OOF
  fold-model scoring, global scaling) change its behaviour. It was not re-run (out of scope).
- Latency-limited windows (decision inside the first cycle) were not tested under H20.
