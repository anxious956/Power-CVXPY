"""KIUC review: the report's element (32Q / 32QG) and the incremental element re-decided from the raw PSCAD channels
of the Q2 runs with an independent phasor chain, and the per-window picture behind "first decided window".

Own chain: VLA/B/C - VLG and ILA/B/C in kV/kA from the .out files (pscad_io.read_case, the file reader only),
divided by the build's 20 kV / 10 MVA peak bases (the project is built per unit on that base: pscad_network.SBASE,
VLL), linearly resampled to 128 samples per cycle, one-cycle DFT on an absolute 60 Hz time reference (so windows ending at different times share one
phase frame), sequence components with a = e^{j120}. No mimic filter. Windows end 2.0, 2.25, ..., 3.0 cycles
after inception at 0.30 s. Memory: the mean of five windows ending 0.5 ... 2.5 cycles before inception.
Thresholds as registered in KIUC.md: 3|I2| > 0.1 pu, |I2| > 0.1 |I1|, 32QG |I2| > 0.2 |I0|, forward if
z2 < 0.4 |Z1L|, reverse if z2 > 0.6 |Z1L|; incremental: pickups 0.05 pu, phi 45 deg, dI2 >= 0.1 dI1, dV1 >= 0.05.

Output per group: agreement with kiuc_q2.json's `q` (first decided window) per case, my per-window decisions,
and three aggregates for the incremental element: first decided (theirs), majority of the five windows, last window.

    python <review>/checks/p_kiuc_32q.py        (cwd: the kiuc checkout at 5c883b8; reads D:\\...\\pscad_work\\network)
"""
import os, sys, json, math
import numpy as np
sys.path.insert(0, "src")
from pscad_io import read_case
from pscad_network import WORK, VBASE_PK, IBASE_PK

ZB = 57.1 ** 2 / 15.0
Z_L1 = complex(1.0433, 3.218) / ZB
TH = np.angle(Z_L1)
N = 128
F0 = 60.0
T_FAULT = 0.30
WIN = [2.0, 2.25, 2.5, 2.75, 3.0]
A = np.exp(2j * np.pi / 3)
PK, PHI, I2_I1_MIN, DV1_MIN = 0.05, 45.0, 0.1, 0.05


def resample(run, names, base, sub=None):
    t = np.asarray(run["t"])
    fs = N * F0
    tt = np.arange(t[0], t[-1], 1 / fs)
    x = np.array([np.interp(tt, t, run["ch"][n] - (run["ch"][sub] if sub else 0.0)) for n in names]) / base
    return tt, x


def phasors(x, tt, t_end):
    k = int(round((t_end - tt[0]) * N * F0))
    seg = x[:, k - N:k]
    w = np.exp(-2j * np.pi * np.arange(k - N, k) / N)          # one absolute 60 Hz time reference for every window,
    p = 2.0 / N * (seg * w).sum(axis=1) / math.sqrt(2)         # so pre-fault memory and fault windows share a frame;
    return p                                                   # rms phasors in pu (bases are peak)


def seq(p):
    a, b, c = p
    return np.array([(a + A * b + A * A * c) / 3, (a + A * A * b + A * c) / 3, (a + b + c) / 3])   # V1, V2, V0


def y_of(run, t_end):
    tt, v = resample(run, ["VLA", "VLB", "VLC"], VBASE_PK, sub="VLG")
    _, i = resample(run, ["ILA", "ILB", "ILC"], IBASE_PK)
    sv, si = seq(phasors(v, tt, t_end)), seq(phasors(i, tt, t_end))
    return np.array([sv[0], sv[1], sv[2], si[0], si[1], si[2]])


def dir32q(y, ground):
    v2, i1, i2, i0 = y[1], y[3], y[4], y[5]
    if 3 * abs(i2) <= 0.10:
        return None
    if abs(i2) <= 0.10 * abs(i1):
        return None
    if ground and abs(i0) > 1e-9 and abs(i2) <= 0.20 * abs(i0):
        return None
    z2 = (v2 * np.conj(i2 * np.exp(1j * TH))).real / abs(i2) ** 2
    zl = abs(Z_L1)
    return "f" if z2 < 0.4 * zl else "r" if z2 > 0.6 * zl else None


def incremental(yN, y):
    dI2, dI1 = abs(y[4] - yN[4]), abs(y[3] - yN[3])
    for k_i, k_v, ok in ((4, 1, dI2 >= I2_I1_MIN * dI1 and dI2 >= PK), (3, 0, abs(y[0] - yN[0]) >= DV1_MIN and dI1 >= PK)):
        dI, dV = y[k_i] - yN[k_i], y[k_v] - yN[k_v]
        if ok and abs(dV) > 1e-9:
            ang = np.degrees(np.angle(dI / dV)) % 360
            return "f" if PHI < ang < 180 + PHI else "r"
    return None


def majority(per):
    d = [x for x in per if x is not None]
    if not d:
        return None
    f, r = d.count("f"), d.count("r")
    return "f" if f > r else "r" if r > f else None


first = lambda per: next((d for d in per if d is not None), None)

files = ["results/network/kiuc_q2.json", "results/network/kiuc_q2_lim1.json"]
tot = dict(cases=0, q_agree=0, q_window_uniform=0, inc_first_agree=0, inc_mixed=0)
for f in files:
    d = json.load(open(f))
    for key, g in d.items():
        want = "r" if key.startswith("R1rev") else "f"
        cnt = {k: dict(right=0, none=0, wrong=0) for k in ("first", "majority", "last")}
        n = 0
        lines = []
        for c in g["cases"]:
            if not c["clean"]:
                continue
            run = read_case(os.path.join(WORK, c["name"] + ".gf46"), c["name"])
            ground = c["case"][2] == "ag"
            mem_ends = [T_FAULT - (0.5 + 0.5 * k) / F0 for k in range(5)]
            yN = np.mean([y_of(run, e) for e in mem_ends], axis=0)
            q_per, inc_per = [], []
            for cyc in WIN:
                y = y_of(run, T_FAULT + cyc / F0)
                q_per.append(dir32q(y, ground))
                inc_per.append(incremental(yN, y))
            n += 1
            tot["cases"] += 1
            tot["q_agree"] += first(q_per) == c["q"]
            tot["q_window_uniform"] += len(set(map(str, q_per))) == 1
            tot["inc_first_agree"] += first(inc_per) == c["inc"]
            tot["inc_mixed"] += len(set(map(str, inc_per))) > 1
            for rule, dec in (("first", first(inc_per)), ("majority", majority(inc_per)), ("last", inc_per[-1])):
                cnt[rule]["right" if dec == want else "none" if dec is None else "wrong"] += 1
            flag = "" if first(q_per) == c["q"] and first(inc_per) == c["inc"] else "  <-- differs from kiuc_q2.json"
            if len(set(map(str, inc_per))) > 1 or len(set(map(str, q_per))) > 1 or flag:
                lines.append(f"    {c['name'][-16:]}: 32Q {q_per} | inc {inc_per} (json q {c['q']}, inc {c['inc']}){flag}")
        print(f"{os.path.basename(f)} :: {key} :: {n} clean | incremental right/none/wrong by rule: " +
              " | ".join(f"{r} {v['right']}/{v['none']}/{v['wrong']}" for r, v in cnt.items()), flush=True)
        for ln in lines:
            print(ln)
print("\nTOTAL clean fault runs", tot["cases"], "| report element: my first-decided == json", tot["q_agree"],
      "| 32Q decision identical on all five windows", tot["q_window_uniform"],
      "| incremental: my first-decided == json", tot["inc_first_agree"], "| incremental mixed across windows", tot["inc_mixed"])
