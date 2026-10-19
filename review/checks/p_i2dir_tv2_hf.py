"""The grid-side IEEE 2800 runs with TV2 (src/i2dir_tv2.py): is the numerical mode gone, or only slowed?

Reads the stored PSCAD output (pscad_network.WORK) of the "grid" group:
  - the normal run: per-cycle peak of vA over 0.10-0.50 s (relative to the 0.20-0.29 s peak), and the share of the
    spectrum above 5 kHz after 0.30 s;
  - the 50 fault runs: the share above 5 kHz in the pre-fault memory span (0.25-0.30 s) and in the fault (0.30-0.35 s).
Plain rectangular FFT of the raw channel; i2dir_tv2.numerically_clean uses a Hanning window on 0.30-0.40 s and the
5-10 kHz band, so the numbers are comparable in size, not identical.

    python review/checks/p_i2dir_tv2_hf.py      (repo root at 1b7e5d3, with the PSCAD output on D:)
"""
import sys, os, json
import numpy as np
sys.path.insert(0, "src")
from pscad_network import WORK
from pscad_io import read_case


def load(name):
    r = read_case(os.path.join(WORK, name + ".gf46"), name)
    return np.asarray(r["t"]), np.asarray(r["ch"]["VLA"])


def hf(t, v, a, b):
    seg = v[(t >= a) & (t < b)]
    f = np.fft.rfftfreq(len(seg), t[1] - t[0])
    P = np.abs(np.fft.rfft(seg)) ** 2
    return P[f >= 5000].sum() / P.sum()


specs = [s for s in json.load(open("results/network/i2dir_tv2_specs.json")) if s.get("group") == "grid"]
t, v = load([s for s in specs if s["kind"] == "normal"][0]["name"])
nom = np.abs(v[(t > 0.2) & (t < 0.29)]).max()
print("normal run, per-cycle peak / nominal:")
print("  " + ", ".join(f"{a:.3f} s {np.abs(v[(t >= a) & (t < a + 1 / 60)]).max() / nom:.3f}" for a in np.arange(0.10, 0.49, 0.025)))
print(f"  share above 5 kHz after 0.30 s: {hf(t, v, 0.30, 0.50):.1e}")
pre, flt = [], []
for s in [s for s in specs if s["kind"] == "fault"]:
    t, v = load(s["name"])
    pre.append(hf(t, v, 0.25, 0.30))
    flt.append(hf(t, v, 0.30, 0.35))
print(f"fault runs (n {len(pre)}): share above 5 kHz, pre-fault 0.25-0.30 s median {np.median(pre):.1e} max {max(pre):.1e}; "
      f"fault 0.30-0.35 s median {np.median(flt):.1e} max {max(flt):.1e}")
