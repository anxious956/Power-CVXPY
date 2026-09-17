"""H30 fix check: a relay-bandwidth front end (causal 3rd-order Butterworth anti-aliasing at 400 Hz, an
assumption for a numerical distance relay sampling at 16-24 samples per cycle; typical analogue AA filters
are 2nd-4th order with a cutoff of a few hundred hertz) applied
  (a) to the cached 6400 Hz records, after evemt.py's non-causal resample_poly (what can be done without
      re-streaming the archives), versus
  (b) causally at 9600 Hz on the raw record, then decimated to 6400 Hz with a causal polyphase FIR
      (what a rebuilt cache would contain).
On the three raw DoubleLine records: pre-inception leak of (a) relative to the noise sigma, and the
difference between (a) and (b) in samples and in full-cycle phasors at 10 and 20 ms.

    python src/review/h30_relay_frontend.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from scipy.signal import resample_poly, butter, lfilter, firwin
from evemt import CHANNELS, FS_RAW, T0, EVENT_T
from review import common as cm

ORDER, FC = 3, 400.0
cub = "Cub_2\\pex_MainBus1_MainLn1-2A"
out = {}
for f in ("result0.csv", "result1.csv", "result2.csv"):
    df = pd.read_csv(os.path.join(cm.ROOT, "data", "DoubleLine", "data", f), header=[0, 1], low_memory=False)
    sig = df[cub][CHANNELS].to_numpy(dtype=np.float64).T
    ev_raw = int(round((EVENT_T - T0) * FS_RAW)); ev = int(round((EVENT_T - T0) * 6400))
    cont = sig.copy(); last = sig[:, ev_raw - 192:ev_raw]; n = sig.shape[1] - ev_raw
    cont[:, ev_raw:] = np.tile(last, (1, n // 192 + 1))[:, :n]
    b6, a6 = butter(ORDER, FC, fs=6400)
    A = lambda s: lfilter(b6, a6, resample_poly(s, 2, 3, axis=1), axis=1)
    b9, a9 = butter(ORDER, FC, fs=9600)
    h = firwin(121, 2600, fs=19200)
    def B(s):
        y = lfilter(b9, a9, s, axis=1)
        up = np.zeros((6, y.shape[1] * 2)); up[:, ::2] = 2 * y
        return lfilter(h, 1, up, axis=1)[:, ::3]
    xa, xa_c = A(sig), A(cont)
    xb = B(sig)

    # align (b) to (a) by the lag maximising correlation on the pre-fault voltage
    lags = range(0, 40)
    err = [np.abs(xa[:3, 400:ev - 5] - xb[:3, 400 + L:ev - 5 + L]).mean() for L in lags]
    L = int(np.argmin(err))
    sigma_v = 1e-3 * cm.V_NOM_PEAK
    leak = np.abs(xa - xa_c)[:3]
    def ph(x, end):
        k = np.arange(end - 128, end); return (2 / 128) * (x[:, end - 128:end] @ np.exp(-2j * np.pi * k / 128))
    res = dict(lag_samples_b_vs_a=L, leak_a_rel_sigma_at_minus_k={k: float(leak[:, ev - k].max() / sigma_v) for k in (1, 2, 4, 8)},
               sample_rms_diff_a_vs_b_rel_nominal=float(np.sqrt(np.mean((xa[:, 300:2800] - xb[:, 300 + L:2800 + L]) ** 2, axis=1)).max()
                                                         / cm.V_NOM_PEAK))
    for t in (10, 20):
        end = ev + int(t * 6.4)
        pa, pb = ph(xa, end), ph(xb, end + L) * np.exp(2j * np.pi * L / 128)   # undo the DFT reference shift of L samples
        res[f"phasor_rel_diff_{t}ms"] = float((np.abs(pa - pb) / np.abs(pb)).max())
    out[f] = res
    print(f, json.dumps(res))
json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "h30_relay_frontend.json"), "w"), indent=1)
