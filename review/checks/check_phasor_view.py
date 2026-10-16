"""real_ml.phasor_view copies a pre-fault and a post-fault cycle into a new array. With
waveforms.sequence_phasors referenced to the absolute sample index, the two phasors share the SOURCE frame
only if the two source windows are a whole number of cycles further apart than their destinations.
A pure, constant 50 Hz sinusoid must give the same phasor in both windows; the turn printed is the error.

    python review/checks/check_phasor_view.py
"""
import os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from waveforms import sequence_phasors, CYCLE, EVENT  # noqa: E402
import real_ml  # noqa: E402

FS = real_ml.FS
t = np.arange(6000) / FS
x = np.stack([np.cos(2 * np.pi * 50 * t - k * 2 * np.pi / 3 + 0.3) for k in range(3)] * 2)      # 6 channels
R = dict(full=x[None], ev=2000)
for t_ms in (10, 15, 20, 25, 30, 35, 40, 50):
    w = real_ml.phasor_view(R, [0], t_ms)[0]
    pre = sequence_phasors(w[:3], EVENT - 2 * CYCLE)[1]
    post = sequence_phasors(w[:3], EVENT + CYCLE)[1]
    n_post = int(round(t_ms * FS / 1000))
    print(f"t = {t_ms:2d} ms (n_post mod 128 = {n_post % CYCLE:3d}): post/pre turn {np.degrees(np.angle(post / pre)):+7.1f} deg"
          + ("   <- DECISIONS_MS" if t_ms in real_ml.DECISIONS_MS else ""))
