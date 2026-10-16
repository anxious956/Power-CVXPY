"""
Check what the averaged inverter actually injects: sequence components of the injected current and of
the PCC voltage over the last cycle of a run, against what the controls asked for.

    python src/pscad_inverter_check.py D:/JOSHUA_TAYLOR_data/data/pscad_work/inverter/inv_test.gf46 inv_test
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pscad_io import read_case
from pscad_check import to_128_per_cycle
from waveforms import sequence_phasors, CYCLE

VBASE = 20.0 / 3 ** 0.5 * 2 ** 0.5            # kV phase peak
IBASE = 10.0 / (3 ** 0.5 * 20.0) * 2 ** 0.5   # kA peak, 10 MVA


def seq_at(run, names, t_end, f0=60.0):
    x = np.array([run["ch"][n] for n in names])
    x, fs = to_128_per_cycle(x, run["fs"], f0)
    end = int(round(t_end * fs))
    s0, s1, s2 = sequence_phasors(x, end - CYCLE)
    return s0, s1, s2


def report(out_dir, case, t_end=None):
    run = read_case(out_dir, case)
    t_end = t_end or run["t"][-1] - 1e-4
    v0, v1, v2 = seq_at(run, ["VA", "VB", "VC"], t_end)
    j0, j1, j2 = seq_at(run, ["IinvA", "IinvB", "IinvC"], t_end)
    i0, i1, i2 = -j0, -j1, -j2           # the ammeters read into the source; injection is the opposite
    deg = lambda z: np.degrees(np.angle(z))
    print(f"{case} at t = {t_end:.3f} s:")
    print(f"  V1 {abs(v1) / VBASE:.4f} pu  V2 {abs(v2) / VBASE:.4f} pu")
    print(f"  I1 {abs(i1) / IBASE:.4f} pu at {deg(i1 / v1):7.2f} deg from V1   (P/Q sign: generator convention)")
    print(f"  I2 {abs(i2) / IBASE:.4f} pu" + (f" at {deg(i2 / v2):7.2f} deg from V2, {deg(i2 / v1):7.2f} deg from V1" if abs(i2) > 1e-6 else ""))
    print(f"  I0 {abs(i0) / IBASE:.4f} pu")
    print(f"  controller outputs (last sample): V1M {run['ch']['V1M'][-1]:.4f} V2M {run['ch']['V2M'][-1]:.4f} "
          f"I1M {run['ch']['I1M'][-1]:.4f} I2M {run['ch']['I2M'][-1]:.4f}")
    return dict(v1=v1, v2=v2, i0=i0, i1=i1, i2=i2)


if __name__ == "__main__":
    report(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else None)
