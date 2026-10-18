"""
Diagnostics of the unstable IEEE 2800 run in EMT stage (c) of docs/I2_DIRECTION.md (review of 4fd3fa0):

  scale    s = 0 (passive loads), MODE2 1, K2 = 2, with a steady single-phase load at S: in steady state the source
           inverter's injected I2 over its bus V2 must be 2 at +90 deg in pu (the static law, injection = j 2 V2)
  k2_*     s = 1 normal runs, MODE2 1, K2 = 0.5, 1, 2: does the divergence depend on K2, and where is the boundary?
  m0       s = 1 normal run, MODE2 0, longer (0.7 s): the suppressed network itself stays bounded

    python src/i2dir_diag.py spec      -> results/network/i2dir_diag_specs.json
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/network/i2dir_diag_specs.json
    python src/i2dir_diag.py analyse
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pscad_network import make_spec, WORK, IBASE_PK, VBASE_PK
from pscad_io import read_case
from pscad_network_check import seq
from i2dir_static import network_s, operating_point

OUT = os.path.join(HERE, "..", "results", "network")
SPECS = os.path.join(OUT, "i2dir_diag_specs.json")
TANG = 1.0 / (2 * np.pi * 15.0)
U0 = (0.0, 0.0, 0.0, 0.0)


def spec(name, s, mode2, k2, confuser=None, t_end=None):
    net = network_s(s, 1e6)
    sg, st = operating_point(s, 1e6, U0)
    sp = make_spec(name, net, None, {"G": sg["G"]}, {}, 1)
    sp["settings"] = {k: dict(ID=v["ID"], IQ=v["IQ"], MODE2=(mode2 if k == "I" else 0.0), K2=k2, D2MAG=0.0, D2ANG=0.0, TANG=TANG)
                      for k, v in st.items()}
    if confuser:
        sp["confuser"] = confuser
    if t_end:
        sp["t_end"] = t_end
    sp.update(kind="normal", diag=name)
    return sp


def make():
    specs = [spec("i2d_scale", 0.0, 1.0, 2.0, confuser=dict(kind="single_phase", bus="S", phase="A", z=[8.0, 2.0], t=0.15))]
    specs += [spec(f"i2d_k2_{str(k).replace('.', 'p')}", 1.0, 1.0, k) for k in (0.5, 1.0, 2.0)]
    specs.append(spec("i2d_m0_long", 1.0, 0.0, 2.0, t_end=0.7))
    json.dump(specs, open(SPECS, "w"), indent=1)
    print(f"{len(specs)} runs -> {os.path.relpath(SPECS)}")


def analyse():
    for sp in json.load(open(SPECS)):
        r = read_case(os.path.join(WORK, sp["name"] + ".gf46"), sp["name"])
        t = np.asarray(r["t"])
        if sp["name"] == "i2d_scale":
            for tt in (0.35, 0.45):
                i2 = -seq(r, ["IinvIA", "IinvIB", "IinvIC"], tt, IBASE_PK)[2]
                v2 = seq(r, ["VLA", "VLB", "VLC"], tt, VBASE_PK, sub="VLG")[2]
                ratio = i2 / v2
                print(f"scale, t {tt}: |V2| {abs(v2):.4f} pu, injected |I2| {abs(i2):.4f} pu, I2/V2 = {abs(ratio):.3f} at "
                      f"{np.degrees(np.angle(ratio)):.1f} deg (law: 2 at +90 deg)")
        else:
            va = np.asarray(r["ch"]["VLA"])
            peaks = [float(np.max(np.abs(va[(t >= a) & (t < a + 1 / 60)]))) for a in np.arange(0.06, float(t[-1]) - 1 / 60, 1 / 60)]
            grow = [b / a for a, b in zip(peaks[:-1], peaks[1:]) if a > 0]
            print(f"{sp['name']:12s}: bus-R phase-A peak per cycle from 0.06 s: first {peaks[0]:.1f} kV, max {max(peaks):.3g} kV, "
                  f"last {peaks[-1]:.3g} kV; largest cycle-to-cycle growth x{max(grow):.2f}")


if __name__ == "__main__":
    {"spec": make, "analyse": analyse}[sys.argv[1]]()
