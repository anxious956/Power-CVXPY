"""H30: relay-bandwidth front end.

A numerical distance relay sees its inputs through an analogue anti-aliasing low-pass before sampling at
typically 16-24 samples per cycle. Assumption used here: causal 3rd-order Butterworth at 400 Hz (typical
AA filters are 2nd-4th order with cutoffs of a few hundred hertz; not a specific product). It is applied to
the cached 6400 Hz records before the measurement chain's noise and ADC. src/review/h30_relay_frontend.py
shows on the raw 9600 Hz records that this matches filtering causally before decimation within 0.2 % in the
10 and 20 ms phasors, and removes the non-causal resampling leak (0.18-0.32 sigma one sample before
inception, from 43-56 sigma).

Implemented as a wrapper around review.common.measurement_chain, switched on by enable(), so the experiment
code whose checkpoints are keyed by commit stays byte-identical; the front end is part of each run's config
(chain key 'relay_aa').

    python src/review/frontend.py zone_cv <relay> --times 10 20      learned models, grouped folds
    python src/review/frontend.py ladder                             conventional ladder
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm

ORDER, FC = 3, 400.0
# ADC current full scale from the CT and the relay input (assumptions): CT 1000/1 A, relay current input linear to
# 100 x In rms, so +-100 * 1 A * sqrt(2) * 1000 = +-141.4 kA primary peak. real_ml.py uses +-40 x the relay's largest
# pre-fault peak (20-29 kA), which clips 13 (DoubleLine) and 14 (relay A) close-in in-zone faults.
I_FS_ABS = 100 * 1.0 * np.sqrt(2) * 1000.0
_orig = cm.measurement_chain


def _wrapped(x, seed_name, chain):
    c = dict(chain or {})
    aa = c.pop("relay_aa", None)
    i_fs_abs = c.pop("i_fs_abs", None)
    if i_fs_abs:
        i_pre = float(np.abs(np.asarray(x, dtype=np.float64)[:, 3:, :x.shape[-1] // 5]).max())
        c["i_fs"] = float(i_fs_abs) / i_pre                  # same full scale in amperes for every relay
    if aa:
        from scipy.signal import butter, lfilter
        b, a = butter(int(aa[0]), float(aa[1]), fs=cm.FS)
        x = lfilter(b, a, x.astype(np.float64), axis=-1).astype(np.float32)
    return _orig(x, seed_name, c)


RELAY_CHAIN = dict(relay_aa=[ORDER, FC], i_fs_abs=I_FS_ABS)


def enable(chain=None):
    """Route every load through the relay front end: anti-aliasing low-pass and CT-based ADC full scale."""
    chain = dict(RELAY_CHAIN if chain is None else chain)
    cm.measurement_chain = _wrapped
    orig_load = cm.load_relay.__wrapped__ if hasattr(cm.load_relay, "__wrapped__") else cm.load_relay

    def load_relay(name, ch=None, cubicle=None):
        c = dict(ch or {})
        for k, v in chain.items():
            c.setdefault(k, v)
        return orig_load(name, c, cubicle)
    load_relay.__wrapped__ = orig_load
    cm.load_relay = load_relay
    return chain


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["zone_cv", "ladder"])
    ap.add_argument("relay", nargs="?")
    ap.add_argument("--times", type=int, nargs="+", default=[10, 20])
    ap.add_argument("--splits", nargs="+", default=["grouped"])
    ap.add_argument("--variant", choices=["relay", "clip-only"], default="relay",
                    help="relay: anti-aliasing + CT-based full scale; clip-only: CT-based full scale, no filter")
    a = ap.parse_args()
    chain = dict(RELAY_CHAIN) if a.variant == "relay" else dict(i_fs_abs=I_FS_ABS)
    enable(chain)
    tag = "relayfe" if a.variant == "relay" else "cliponly"
    if a.what == "zone_cv":
        from review import zone_cv
        res = zone_cv.run(a.relay, a.times, a.splits, "guard", chain=chain)
        json.dump(res, open(os.path.join(cm.ROOT, "logs", f"zone_cv_{a.relay}_{tag}.manifest.json"), "w"), indent=1)
    else:
        from review import ladder
        out = {}
        for name in ("testgrid_B", "testgrid_A", "doubleline"):
            out[name] = ladder.run(name)
            json.dump(out, open(os.path.join(cm.ROOT, "results", "review", f"ladder_{tag}.json"), "w"), indent=1, default=str)
