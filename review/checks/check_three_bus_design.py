"""Re-derive the three-bus design numbers of results/MULTIBUS.md (8 / 48 unseparated at delta = 0; 0.62 pu, 0.90 pu at
rho 0.1) without writing any file; and test the design delta's robustness to the turn the EMT runs show during
faults (review/checks/check_emt.py: delta turns -29 .. +11 deg at fault inception).

    python review/checks/check_three_bus_design.py
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(ROOT, "src", "review"))
import numpy as np
import network as nw
from network_delta_test import model, RHO

net, ms = model()
print("unseparated at 0:", len(nw.unseparated(ms, 0j)), "of", len(ms.faults))
for rho in (0.0, RHO):
    print(f"rho {rho}:", nw.min_delta(ms, rho=rho, r_step=0.02, n_ang=72))
d = 0.9 * np.exp(1j * np.radians(210))
lim = nw.limit_rows(ms, "I", d)
print("I1 that fits beside the design delta: largest |i+| over the per-phase-limited set",
      max(abs(i) for i in [r * np.exp(1j * t) for r in np.linspace(0, 1.2, 241) for t in np.linspace(0, 2 * np.pi, 361)]
          if max(abs(i + nw.A3 ** k * d) for k in range(3)) <= 1.2))
