"""The negative-sequence impedance behind the relay (bus R, looking away from L1) at s = 1 with the RC filter shunts and
the source inverter suppressing I2: the R shunt in parallel with L2 plus the S shunt, from i2dir_static.filter_shunts.

    python review/checks/p_i2dir_backz2.py      (repo root at 1b7e5d3)
"""
import sys
import numpy as np
sys.path.insert(0, "src")
import zone_model as zm
from i2dir_static import filter_shunts

p = zm.ZoneParams()
f = filter_shunts(1.0)
for b, v in f.items():
    print(f"shunt at {b}: B {v['B']:.4f} pu, R {v['R']:.3f} pu")
zb = 1.0 / (f["R"]["y"] + 1.0 / (p.z2 + 1.0 / f["S"]["y"]))
print(f"back-side Z2 = {zb.real:.3f} {zb.imag:+.3f}j pu, |Z2| {abs(zb):.2f}, angle {np.degrees(np.angle(zb)):.1f} deg")
zl = np.degrees(np.angle(p.z1))
print(f"forward fault: the element sees -Z2, angle {np.degrees(np.angle(-zb)):.1f} deg; projected on the line angle "
      f"({zl:.1f} deg): {abs(zb) * np.cos(np.angle(-zb) - np.radians(zl)):+.2f} pu")
