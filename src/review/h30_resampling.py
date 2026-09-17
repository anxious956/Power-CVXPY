"""H30: look-ahead of evemt.py's non-causal resample_poly (9600 -> 6400 Hz), measured on the three
raw DoubleLine records that are unpacked in data/DoubleLine/data (bolted AG faults on the protected
line at 1, 20, 50 %), against a causal alternative (8th-order Butterworth anti-aliasing at 1.6 kHz,
then linear-phase-free decimation by 3/2 via causal polyphase: upsample 2, causal FIR, downsample 3).

Leakage = resampled(actual record) - resampled(record with every post-inception sample replaced by
the periodic continuation of the last pre-fault cycle). Before inception this is exactly the future
leaking backwards. Reported per sample before inception, relative to real_ml's noise sigma.

    python src/review/h30_resampling.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from scipy.signal import resample_poly, firwin, lfilter, butter
from evemt import CHANNELS, FS_RAW, T0, EVENT_T
from review import common as cm

ROOT = cm.ROOT
cub = "Cub_2\pex_MainBus1_MainLn1-2A"
out = {}
for f in ("result0.csv", "result1.csv", "result2.csv"):
    df = pd.read_csv(os.path.join(ROOT, "data", "DoubleLine", "data", f), header=[0, 1], low_memory=False)
    t = df[("EvemtResult", df["EvemtResult"].columns[0])].to_numpy() if "EvemtResult" in df.columns.get_level_values(0) else None
    sig = df[cub][CHANNELS].to_numpy(dtype=np.float64).T
    ev_raw = int(round((EVENT_T - T0) * FS_RAW))
    spc_raw = FS_RAW // 50
    cont = sig.copy()
    last = sig[:, ev_raw - spc_raw:ev_raw]
    n_after = sig.shape[1] - ev_raw
    cont[:, ev_raw:] = np.tile(last, (1, n_after // spc_raw + 1))[:, :n_after]
    info = dict(fs_check=None if t is None else float(1 / np.median(np.diff(t))), t0=None if t is None else float(t[0]),
                v_peak_prefault=float(np.abs(sig[:3, :ev_raw]).max()))
    ev = int(round((EVENT_T - T0) * 6400))
    # non-causal (evemt.py)
    a, b = resample_poly(sig, 2, 3, axis=1), resample_poly(cont, 2, 3, axis=1)
    leak = np.abs(a - b)
    # causal: upsample x2 (zero stuffing), causal FIR lowpass at 3200/2 Hz... in the 19.2 kHz domain, downsample x3
    up = np.zeros((6, sig.shape[1] * 2)); up[:, ::2] = sig * 2
    upc = np.zeros_like(up); upc[:, ::2] = cont * 2
    h = firwin(121, 2600, fs=19200)                 # causal FIR, 3.1 ms group delay (linear phase, delayed)
    ca, cb = lfilter(h, 1, up, axis=1)[:, ::3], lfilter(h, 1, upc, axis=1)[:, ::3]
    bb, aa = butter(4, 2600, fs=19200)
    ia, ib = lfilter(bb, aa, up, axis=1)[:, ::3], lfilter(bb, aa, upc, axis=1)[:, ::3]
    sig_v, sig_i = 1e-3 * cm.V_NOM_PEAK, None
    res = {}
    for lab, L in (("resample_poly (non-causal, evemt.py)", leak), ("causal FIR 121 taps", np.abs(ca - cb)),
                   ("causal Butterworth 4th order", np.abs(ia - ib))):
        v = L[:3]; i = L[3:]
        ipk = np.abs(a[3:, :ev]).max()
        first = [k for k in range(1, 40) if v[:, ev - k].max() > sig_v]
        res[lab] = dict(
            v_leak_rel_noise_at_minus_k={k: float(v[:, ev - k].max() / sig_v) for k in (1, 2, 3, 4, 6, 8, 12, 16)},
            i_leak_rel_prefault_peak_at_minus_k={k: float(i[:, ev - k].max() / ipk) for k in (1, 2, 3, 4, 6, 8, 12, 16)},
            earliest_sample_with_v_leak_above_noise_sigma=(max(first) if first else 0),
            earliest_ms=(max(first) if first else 0) / 6.4)
    out[f] = dict(info=info, **res)
    print(f, json.dumps(info), flush=True)
    for lab, r in res.items():
        print(f"  {lab:38s} V leak / noise sigma at k=1,2,4,8: "
              + " ".join(f"{r['v_leak_rel_noise_at_minus_k'][k]:8.2f}" for k in (1, 2, 4, 8))
              + f"   earliest above sigma: {r['earliest_ms']:.2f} ms before inception")
os.makedirs(os.path.join(ROOT, "results", "review"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "results", "review", "h30_resampling.json"), "w"), indent=1)
