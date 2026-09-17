"""Q1 follow-up: is the high-C CVT model's 74 % cycle-1 error for a 90 % sag at voltage peak a discretisation
artefact? Both cases (terminal short circuit and 90 % sag, inception at voltage zero and at voltage peak) with one
metric: peak instantaneous error |u_s - u_p| per cycle after inception, % of the pre-fault peak, and the residual
envelope max |u_s| for t >= Ts after a terminal short circuit, % of pre-fault peak. Computed at the cache rate
(6400 Hz, bilinear discretisation) and at 2x and 4x the rate (input upsampled by band-limited interpolation, filter
discretised at the higher rate, output decimated back). IEC 61869-5 class limits remain quoted from memory and
unverified.

    python src/review/cvt_step_check.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from scipy.signal import resample_poly
from review import common as cm

EV, N = 640, 3201
out = {}
orig_fs, orig_spc = cm.FS, cm.SPC
for up in (1, 2, 4):
    fs = 6400 * up
    t = np.arange(N * up) / fs
    for kind in ("highC", "lowC"):
        for poa in (0.0, 90.0):
            for label, factor in (("terminal short circuit", 0.0), ("90 % sag", 0.1)):
                v = np.sin(2 * np.pi * 50 * t + np.deg2rad(poa))
                v[EV * up:] *= factor
                cm.FS, cm.SPC = fs, 128 * up
                try:
                    y, _ = cm.cvt_filter(v[None, None, :], kind)
                finally:
                    cm.FS, cm.SPC = orig_fs, orig_spc
                y = y[0, 0]
                err = np.abs(y - v)
                spc = 128 * up
                r = {f"cycle {k + 1} peak error %": float(err[EV * up + k * spc:EV * up + (k + 1) * spc].max() * 100) for k in range(3)}
                if factor == 0.0:
                    r.update({f"residual after {ts} ms %": float(np.abs(y[EV * up + int(ts * fs / 1000):]).max() * 100) for ts in (10, 20, 40)})
                out[f"{kind} | x{up} rate | POW {poa:g} | {label}"] = r
                print(f"{kind:5s} x{up}  POW {poa:3.0f}  {label:23s} " + "  ".join(f"{k} {v_:6.2f}" for k, v_ in r.items()), flush=True)
json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "cvt_step_check.json"), "w"), indent=1)
