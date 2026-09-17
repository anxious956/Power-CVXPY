"""H17, second part: the fault-vs-load table in results/DETECTION.md at its full size.

Rebuilds detect.py's exact data (rng 100 / 999, 900 / 450 per class unit, hard set, noise 0.01,
all 10 magnitudes) and evaluates the two threshold detectors, |i-| and |di-|, with the original
test-chosen polarity and with the train-chosen polarity. CPU only (the LR/CNN columns do not
change sign; see h17_polarity.py).

  python src/review/h17_detect_full.py
"""
import time
import numpy as np
from synth_common import design_direction, save
from waveforms import make_dataset, SigParams
import detect as D

direction = design_direction()
mags = [0.0, 0.025, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.40, 0.514]
rows = []; t0 = time.time()
print("delta  detector     test-sign: pol dep FAR AUC   | train-sign: pol dep FAR AUC  (train AUC)")
for t in mags:
    d = t * direction
    Xtr, ytr, _ = make_dataset(900, np.random.default_rng(100), delta=d, p=SigParams(noise=0.01), hard=True)
    Xte, yte, _ = make_dataset(450, np.random.default_rng(999), delta=d, p=SigParams(noise=0.01), hard=True)
    for name, fn in (("negseq", D.score_negseq), ("incremental", D.score_incremental)):
        a, b = fn(Xtr), fn(Xte)
        L = D.evaluate(a, ytr, b, yte, polarity="test")
        T = D.evaluate(a, ytr, b, yte, polarity="train")
        rows.append(dict(delta=t, det=name, test_sign=L, train_sign=T))
        print(f"{t:.3f}  {name:11s}  {L['polarity']:+d} {L['detection_rate']*100:5.1f}% {L['false_alarm']*100:4.1f}% {L['auc']:.3f}"
              f"   |  {T['polarity']:+d} {T['detection_rate']*100:5.1f}% {T['false_alarm']*100:4.1f}% {T['auc']:.3f}  ({T['auc_train']:.3f})",
              flush=True)
save("h17_detect_full.json", dict(rows=rows, runtime_s=time.time() - t0))
