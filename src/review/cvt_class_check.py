"""Q1: validate the CVT models against IEC 61869-5 transient response classes before using them.

Test as in the standard: short circuit at the primary terminals (primary voltage to zero), at voltage peak
and at voltage zero; residual secondary voltage after Ts, as a percentage of the pre-fault secondary peak.
Class limits (IEC 61869-5 Table 503 / IEC 60044-5 Table 12, quoted from memory, NOT verified against the
standard text; the author should check them):
    Ts [ms]    10     20     40     60     90
    T1          -    <=10   <10    <10    <10
    T2        <=25   <=10   <=2    <=0.6  <=0.2
    T3        <=4    <=2    <=2    <=2    <=2
Residual = max |u_s(t)| for t >= Ts (conservative envelope), in % of the pre-fault peak.
Also reports, for a 90 % sag (close-in fault), the transient error normalised to the pre-fault peak.

    python src/review/cvt_class_check.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm

FS, EV = 6400, 640
LIMITS = {"T1": {10: None, 20: 10, 40: 10, 60: 10, 90: 10}, "T2": {10: 25, 20: 10, 40: 2, 60: 0.6, 90: 0.2},
          "T3": {10: 4, 20: 2, 40: 2, 60: 2, 90: 2}}
t = np.arange(3201) / FS
out = {}
for kind in ("highC", "lowC"):
    r = {}
    for poa in (0.0, 90.0):
        for label, factor in (("terminal short circuit", 0.0), ("90 % sag", 0.1)):
            v = np.sin(2 * np.pi * 50 * t + np.deg2rad(poa))
            v[EV:] *= factor
            y, _ = cm.cvt_filter(v[None, None, :], kind)
            y = y[0, 0]
            if factor == 0.0:
                resid = {ts: float(np.abs(y[EV + int(ts * FS / 1000):]).max() * 100) for ts in (10, 20, 40, 60, 90)}
                r[f"POW {poa:g} {label}"] = resid
            else:
                err = y - v
                r[f"POW {poa:g} {label}"] = {f"cycle {k + 1} peak error % of pre-fault peak": float(np.abs(err[EV + k * 128:EV + (k + 1) * 128]).max() * 100)
                                             for k in range(4)}
    passes = {}
    for cls, lim in LIMITS.items():
        ok = True
        for poa in (0.0, 90.0):
            resid = r[f"POW {poa:g} terminal short circuit"]
            ok &= all(l is None or resid[ts] <= l for ts, l in lim.items())
        passes[cls] = bool(ok)
    r["passes_class"] = passes
    out[kind] = r
    print(kind, json.dumps({k: ({kk: round(vv, 2) for kk, vv in v.items()} if isinstance(v, dict) and k != "passes_class" else v) for k, v in r.items()}, indent=1))
json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "cvt_class_check.json"), "w"), indent=1)
