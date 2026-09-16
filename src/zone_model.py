"""
Three-bus sequence model for the real protection question: in-zone or out-of-zone?

    L ---- z (protected line) ---- R ---- z2 (adjacent line) ---- S
    |                              |                              |
   local source                IBR + load                       load
   + RELAY

A distance relay at L must trip for a fault on its own line up to its reach (about 80 to
85 %), and must NOT trip for a fault past the remote bus, on the adjacent line. Both look
alike: same fault type, same sequence signature, only slightly further away. This is the
discrimination Taylor's formulation is about, "the relay tries to determine if mz in
[mz_bar, 1]", and it is much harder than telling a fault from a load.

The remote infeed is what makes it hard. Current from the IBR at R flows into a fault on
the adjacent line, so the relay sees an apparent impedance inflated by a term it cannot
measure. With high fault resistance this pushes an out-of-zone fault into the zone and an
in-zone fault out of it.

Same conventions as aux_model: per unit, sequence domain, SG as voltage source, IBR as
current source, auxiliary signal = negative-sequence current injected by the IBR at R.
"""
from dataclasses import dataclass, field
import numpy as np

SEQ = (1, 2, 0)


@dataclass
class ZoneParams:
    z1: complex = 0.02 + 0.20j                 # protected line, positive/negative sequence
    z2: complex = 0.025 + 0.25j                # adjacent line
    z0_ratio: float = 3.0
    local: str = "SG"
    zs: dict = field(default_factory=lambda: {1: 0.4j, 2: 0.4j, 0: 0.8j})   # weak source at L
    yR: dict = field(default_factory=lambda: {1: 0.30 - 0.09j, 2: 0.30 - 0.09j, 0: 0.0})
    yS: dict = field(default_factory=lambda: {1: 0.55 - 0.17j, 2: 0.55 - 0.17j, 0: 0.0})
    ibr_zero_z: complex = 0.15j                # grounded interconnection transformer at R
    ibr_neg_z: complex = 1e6
    rF: float = 1.0                            # max fault resistance, pu
    e0: complex = 1.0 + 0j
    i0: complex = 0.45 * np.exp(-1j * np.deg2rad(15))     # IBR positive-sequence output
    reach: float = 0.85                        # zone-1 reach, fraction of the protected line

    def zl(self, which):
        z = self.z1 if which == 1 else self.z2
        return {1: z, 2: z, 0: self.z0_ratio * z}


def solve_zone(p: ZoneParams, kind, srcL, iR, delta, m=0.5, mr=0.0, inj0=0.0):
    """Sequence solve. kind: 'N' (no fault), 'ag'/'ab' on the protected line at fraction m,
    or 'ag2'/'ab2' on the adjacent line at fraction m (measured from R).
    Returns [vL+, vL-, vL0, iL+, iL-, iL0] as seen by the relay at L."""
    on_line2 = kind.endswith("2")
    ftype = kind[:-1] if on_line2 else kind
    Rf = mr * p.rF
    idx, k = {}, 0
    for s in SEQ:
        for node in ("L", "F", "R", "S"):
            idx[(s, node)] = k; k += 1
    iF = 12
    A = np.zeros((13, 13), complex); b = np.zeros(13, complex)
    r = 0
    for s in SEQ:
        L, F, R, S = (idx[(s, n)] for n in ("L", "F", "R", "S"))
        z1s, z2s = p.zl(1)[s], p.zl(2)[s]
        yR = p.yR[s] + (1 / p.ibr_zero_z if s == 0 else 0.0) + (1 / p.ibr_neg_z if s == 2 else 0.0)
        yS = p.yS[s]
        injR = {1: iR, 2: delta, 0: inj0}[s]
        fault_here = ftype in ("ag", "ab")
        fcoef = 0.0
        if fault_here:
            fcoef = -1.0 if ftype == "ag" else {1: -1.0, 2: +1.0, 0: 0.0}[s]

        if not on_line2:                        # F sits on line 1 between L and R
            za, zb = m * z1s, (1 - m) * z1s
            if p.local == "SG":
                e = p.e0 if s == 1 else 0.0
                e = srcL if s == 1 else 0.0
                A[r, L] = -1 / p.zs[s] - 1 / za; A[r, F] = 1 / za; b[r] = -e / p.zs[s]
            else:
                ysh = (1 / p.ibr_zero_z if s == 0 else 0.0) + (1 / p.ibr_neg_z if s == 2 else 0.0)
                A[r, L] = -ysh - 1 / za; A[r, F] = 1 / za
                b[r] = -(srcL if s == 1 else 0.0)
            r += 1
            A[r, L] = 1 / za; A[r, F] = -1 / za - 1 / zb; A[r, R] = 1 / zb
            A[r, iF] = fcoef; r += 1                                     # KCL at F
            A[r, F] = 1 / zb; A[r, R] = -1 / zb - yR - 1 / z2s; A[r, S] = 1 / z2s
            b[r] = -injR; r += 1                                         # KCL at R
            A[r, R] = 1 / z2s; A[r, S] = -1 / z2s - yS; r += 1           # KCL at S
        else:                                    # F sits on line 2 between R and S
            za, zb = m * z2s, (1 - m) * z2s
            if p.local == "SG":
                e = srcL if s == 1 else 0.0
                A[r, L] = -1 / p.zs[s] - 1 / z1s; A[r, R] = 1 / z1s; b[r] = -e / p.zs[s]
            else:
                ysh = (1 / p.ibr_zero_z if s == 0 else 0.0) + (1 / p.ibr_neg_z if s == 2 else 0.0)
                A[r, L] = -ysh - 1 / z1s; A[r, R] = 1 / z1s
                b[r] = -(srcL if s == 1 else 0.0)
            r += 1
            A[r, L] = 1 / z1s; A[r, R] = -1 / z1s - yR - 1 / za; A[r, F] = 1 / za
            b[r] = -injR; r += 1                                         # KCL at R
            A[r, R] = 1 / za; A[r, F] = -1 / za - 1 / zb; A[r, S] = 1 / zb
            A[r, iF] = fcoef; r += 1                                     # KCL at F
            A[r, F] = 1 / zb; A[r, S] = -1 / zb - yS; r += 1             # KCL at S

    if ftype == "N":
        A[r, iF] = 1.0
    elif ftype == "ag":
        for s in SEQ:
            A[r, idx[(s, "F")]] = 1.0
        A[r, iF] = -3 * Rf
    else:
        A[r, idx[(1, "F")]] = 1.0; A[r, idx[(2, "F")]] = -1.0
        A[r, iF] = -Rf

    x = np.linalg.solve(A, b)
    v = [x[idx[(s, "L")]] for s in SEQ]
    i = []
    for s in SEQ:
        if on_line2 or ftype == "N" and on_line2:
            i.append((x[idx[(s, "L")]] - x[idx[(s, "R")]]) / p.zl(1)[s])
        else:
            i.append((x[idx[(s, "L")]] - x[idx[(s, "F")]]) / (m * p.zl(1)[s]))
    return np.array(v + i)


def apparent_impedance(y, kind="ag"):
    """Relay apparent impedance for the standard fault loops.
    ag: phase-a-to-ground loop with zero-sequence compensation omitted (raw loop).
    ab: phase-to-phase loop."""
    v1, v2, v0, i1, i2, i0 = y
    a = np.exp(2j * np.pi / 3)
    if kind.startswith("ag"):
        va = v1 + v2 + v0
        ia = i1 + i2 + i0
        return va / ia
    vab = (v1 + v2 + v0) - (a**2 * v1 + a * v2 + v0)
    iab = (i1 + i2 + i0) - (a**2 * i1 + a * i2 + i0)
    return vab / iab
