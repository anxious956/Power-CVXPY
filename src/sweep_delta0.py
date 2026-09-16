"""
Sweep: in which regimes does delta = 0 FAIL to separate normal from faults,
and does some modest negative-sequence injection fix it?
Prints one line per setting. Cheap: ~30 LPs per probe.
"""
import itertools, time
import numpy as np
from aux_model import Params, Problem

probes = [0.0]
for mag in (0.2, 0.4, 0.6, 0.8, 1.0):
    for ang in range(0, 360, 45):
        probes.append(mag * np.exp(1j * np.deg2rad(ang)))

rows = []
t0 = time.time()
for local, ang, eps, rF, zs_scale in itertools.product(
        ["SG", "IBR"], [0.3, 1.0], [0.03, 0.08, 0.15], [0.3, 1.0], [1.0, 8.0]):
    if local == "IBR" and zs_scale != 1.0:
        continue  # zs irrelevant for IBR local source
    zs = {k: v*zs_scale for k, v in {1: 0.05j, 2: 0.05j, 0: 0.10j}.items()}
    p = Params(name="sweep", local=local, zs=zs, gen_i=[0.3, ang], eps=eps, rF=rF)
    P = Problem(p)
    n0 = len(P.unseparated(0.0))
    best = None
    for d in probes:
        if len(P.unseparated(d)) == 0:
            if best is None or abs(d) < abs(best):
                best = d
    rows.append((local, zs_scale, ang, eps, rF, n0, best))
    print(f"local={local:3s} zs_x{zs_scale:<3} ibr_angle_gen={ang:<4} eps={eps:<5} rF={rF:<4} "
          f"| unseparated at delta=0: {n0:2d}/{len(P.faults)} | smallest separating probe: {best}")
print(f"done in {time.time()-t0:.1f}s")
print("\nInteresting = unseparated at delta=0 > 0 AND some probe separates:")
for r in rows:
    if r[5] > 0 and r[6] is not None:
        print("  ", r)
