"""
H3: uncertainty sets used in three places that are presented as the same system.
  design      aux_model.Params / PRESETS['weak_sg'] with the linear generators (aux_model.py:100-120)
  waveforms   waveforms._relay_state (feeds detect.py), which samples the design's linear box
  zone        zone_detect.generate (feeds zone_detect.py) on zone_model.ZoneParams
Ranges are measured by sampling each generator (200k draws), not transcribed.

  python src/review/wp1_h3_sets.py      (~10 s)
"""
import numpy as np
from wp1_common import PRESETS, source_sets, dump
from zone_model import ZoneParams

rng = np.random.default_rng(0)
n = 200000
p = PRESETS["weak_sg"]
zp = ZoneParams()


def rng_of(z, ref):
    return dict(abs=[float(np.abs(z).min()), float(np.abs(z).max())],
                angle_offset_rad=[float(np.angle(z / ref).min()), float(np.angle(z / ref).max())])


rows = {}
(sL0, gL), (iR0, gR) = source_sets(p, "linear")
u = rng.uniform(-1, 1, (n, 4))
sL = sL0 + gL[0] * u[:, 0] + gL[1] * u[:, 1]
iR = iR0 + gR[0] * u[:, 2] + gR[1] * u[:, 3]
rows["design_weak_sg"] = dict(
    local_source=rng_of(sL, p.e0), remote_ibr=rng_of(iR, p.i0), zs1=abs(p.zs[1]), load_y1=abs(p.yld[1]),
    load_scaling="fixed", ibr_zero_z=abs(p.ibr_zero_z), rF=p.rF, m="grid 0.15..0.95 (5)", mr="grid {0, .5, 1}",
    fault_types="ag, ab(=bc)", negatives="N only (m=0.5 placeholder)", noise=f"box +-{p.eps} per real component",
    network="two-bus L-R")
rows["waveforms_relay_state"] = dict(
    local_source=rng_of(sL, p.e0), remote_ibr=rng_of(iR, p.i0), zs1=abs(p.zs[1]), load_y1=abs(p.yld[1]),
    load_scaling="load_step x U[1.3,2.0]; motor_start |Z|/U[3,6] at 70-82 deg; unbalanced_load x U[1.0,1.4]",
    ibr_zero_z=abs(p.ibr_zero_z), rF=p.rF, m="U[0.10, 0.95] (hard mode same)", mr="U[0,1]; hard mode U[0.85,1]",
    fault_types="fault_lg=ag, fault_ll=ab(=bc)",
    negatives="normal, load_step, motor_start, unbalanced_load (|u| U[0.05,0.7], any angle, also adds to delta and I0)",
    noise="N(0, 0.01) per sample + 2 %/1 % 5th/7th harmonics + DC offset 0.3 (tau 1.5 cyc) on currents",
    network="two-bus L-R (same solve)")
fz = rng.uniform(0.5, 1.8, n)
srcL = zp.e0 * (1 + rng.uniform(-0.05, 0.05, n)) * np.exp(1j * rng.uniform(-0.09, 0.09, n))
iRz = zp.i0 * rng.uniform(0.5, 1.6, n) * np.exp(1j * rng.uniform(-0.4, 0.4, n))
rows["zone_generate"] = dict(
    local_source=rng_of(srcL, zp.e0), remote_ibr=rng_of(iRz, zp.i0), zs1=[float(abs(zp.zs[1]) * fz.min()), float(abs(zp.zs[1]) * fz.max())],
    load_y1=[abs(zp.yR[1]) * 0.6, abs(zp.yR[1]) * 1.5], load_S_y1=[abs(zp.yS[1]) * 0.6, abs(zp.yS[1]) * 1.5],
    load_scaling="yR, yS x U[0.6,1.5] each", ibr_zero_z=[abs(zp.ibr_zero_z) * 0.6, abs(zp.ibr_zero_z) * 1.6],
    rF="--rf, default 0.3 (ZoneParams default 1.0)", m="in U[0.62,0.85], out (line 2) U[0.02,0.18]", mr="U[0,1]",
    fault_types="ag, ab(=bc), ag2, ab2(=bc)", negatives="ag2/ab2 on adjacent line (no N)",
    noise="as waveforms (_synth)", network="three-bus L-R-S, line2 z2 = 0.025+j0.25")
rows["design_i0_vs_zone_i0"] = dict(design=abs(p.i0), zone=abs(zp.i0))
dump(rows, "h3_sets.json")
for k, v in rows.items():
    print(k)
    for kk, vv in (v.items() if isinstance(v, dict) else []):
        print("   ", kk, ":", vv)
