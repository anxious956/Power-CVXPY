"""Review of PR #44: which ingredient of the two-frame model drives delta*? Search tier (as frames_design.py).
For each variant: cases unseparated at delta = 0, and the cases still unseparated at the best angle of a few radii
just below the reported delta*; plus how many of the 72 fine angles separate at each radius.

    python review/checks/p44_ablate.py <variant> <rho> [radii]   (repo root, PR #44 at 7f2f2b5; variants: base, nodrift,
    settled, noref, steady_only, narrow_i1, L1only)
"""
import sys, time, json
import numpy as np
sys.path.insert(0, "src")
import frames as fr
import network as nw
from pscad_network import three_bus
from network_delta_test import CASES

variant, rho = sys.argv[1], float(sys.argv[2])
radii = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [0.9, 1.0, 1.08, 1.14]


class SettledOnly(fr.FrameModel):
    """Fault sets at the settled fault frame only (lambda = 1): a relay deciding after the inverter's DFT settled."""
    def _expand(self, S, case):
        if case is None:
            return super()._expand(S, case)
        refs = np.array([-1.0, 0.0, 1.0]) if self.ref_noise else np.array([0.0])
        drs = np.array([-1.0, 0.0, 1.0]) if self.drift else np.array([0.0])
        import itertools
        grid = np.array(list(itertools.product([1.0], drs, refs)))
        Sx = np.repeat(S, len(grid), 0)
        lam, dr, ref = (np.tile(grid[:, j], len(S)) for j in range(3))
        W = np.hstack([Sx, dr[:, None], ref[:, None]])
        return Sx, lam, dr, ref, W


net = three_bus()
cases = CASES
kw = dict(n_samples=150, face_pts=3, seed=1, factor=1.1)
cls = fr.FrameModel
if variant == "base":
    pass
elif variant == "nodrift":
    kw["drift_deg"] = 0.0
elif variant == "settled":
    cls = SettledOnly
elif variant == "noref":
    kw["ref_noise"] = False
elif variant == "steady_only":                      # settled frame, no drift, no reference noise
    cls = SettledOnly; kw.update(drift_deg=0.0, ref_noise=False)
elif variant == "narrow_i1":                        # inverter command angle spread +-0.15 rad in its own frame
    net.ibrs["I"].gen = (0.3, 0.15)
elif variant == "L1only":
    cases = [c for c in CASES if c[0] == "L1"]
else:
    raise ValueError(variant)
t0 = time.time()
fm = cls(net, cases, **kw)
hard = fr.unseparated(fm, 0j, rho)
order = [k for k, c in enumerate(fm.cases) if c in hard] + [k for k, c in enumerate(fm.cases) if c not in hard]
out = dict(variant=variant, rho=rho, unseparated_at_0=len(hard), radii={})
print(f"{variant} rho {rho}: unseparated at 0: {len(hard)}  [{time.time() - t0:.0f} s]", flush=True)
for r in radii:
    ok_angles, best = [], None
    for a in np.linspace(0, 2 * np.pi, 72, endpoint=False):
        d = r * np.exp(1j * a)
        try:
            s = fr.separated_fast(fm, d, rho, order)
        except fr.Inadmissible:
            continue
        if s:
            ok_angles.append(round(float(np.degrees(a))))
    out["radii"][r] = ok_angles
    print(f"  |d| = {r:.2f}: separating angles {len(ok_angles)} / 72 {ok_angles[:12]}  [{time.time() - t0:.0f} s]", flush=True)
print(json.dumps(out))
