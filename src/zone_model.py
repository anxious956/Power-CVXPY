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


A3 = np.exp(2j * np.pi / 3)


def _phase(y):
    """Sequence measurement [v+,v-,v0,i+,i-,i0] -> phase quantities (va,vb,vc), (ia,ib,ic)."""
    v1, v2, v0, i1, i2, i0 = y
    v = (v1 + v2 + v0, A3**2 * v1 + A3 * v2 + v0, A3 * v1 + A3**2 * v2 + v0)
    i = (i1 + i2 + i0, A3**2 * i1 + A3 * i2 + i0, A3 * i1 + A3**2 * i2 + i0)
    return v, i


def loop_impedances(y, z1, z0, with_current=False):
    """All six fault loops as a real relay computes them.

    Ground loops carry the zero-sequence (residual) compensation
        Z = V_p / (I_p + k0 * 3 I0),   k0 = (Z0 - Z1) / (3 Z1)
    without which a ground loop reads the wrong impedance by a large factor. Phase loops are
    the plain difference quantities. Returns {'ag','bg','cg','ab','bc','ca': complex}, or
    {name: (Z, |I_loop|)} when with_current, since a real relay supervises each loop by its
    own current and only lets picked-up loops vote. Without that supervision a healthy loop
    can return a small spurious reactance and make the element look far worse than it is.
    """
    (va, vb, vc), (ia, ib, ic) = _phase(y)
    i0 = y[5]
    k0 = (z0 - z1) / (3 * z1)
    comp = k0 * 3 * i0
    e = 1e-12
    out = {}
    for name, (vp, ip) in (("ag", (va, ia)), ("bg", (vb, ib)), ("cg", (vc, ic))):
        iloop = ip + comp
        out[name] = (vp / (iloop + e), abs(iloop)) if with_current else vp / (iloop + e)
    for name, (vp, vq, ip, iq) in (("ab", (va, vb, ia, ib)), ("bc", (vb, vc, ib, ic)),
                                   ("ca", (vc, va, ic, ia))):
        iloop = ip - iq
        out[name] = ((vp - vq) / (iloop + e), abs(iloop)) if with_current else (vp - vq) / (iloop + e)
    return out


def phase_selected_reactance(vpost, ipre, ipost, z1, z0, ground_ratio=0.2, frac=0.5, pair_frac=0.8, default=10.0):
    """Distance estimate with faulted-phase selection, the way a numerical relay releases loops.

    Inputs are sequence phasors in the order returned by waveforms.sequence_phasors,
    [s0, s+, s-]. Selection uses incremental currents (post minus pre), which strip out load.

      ground fault if |dI0| > ground_ratio * |dI1|
        phases whose incremental current is at least `frac` of the largest are selected;
        one phase (LG): release that ground loop;
        two phases (LLG): release only their phase-to-phase loop
      otherwise
        release the phase-to-phase loops whose incremental loop current is at least
        `pair_frac` of the largest (one loop for LL, all three for a symmetrical fault).
        pair_frac must exceed 0.5: in an LL fault the two healthy pair currents are exactly
        half the faulted one and would otherwise be released too.

    Then the smallest forward reactance among released loops. Without selection a healthy
    loop that happens to carry current can read a small reactance and win: on EvEMTBench
    DoubleLine that produced 40 % zone-1 trips for faults at 99 % of the line.
    """
    a = np.exp(2j * np.pi / 3)
    di0, di1, di2 = ipost - ipre
    dia, dib, dic = di0 + di1 + di2, di0 + a**2 * di1 + a * di2, di0 + a * di1 + a**2 * di2
    y = np.array([vpost[1], vpost[2], vpost[0], ipost[1], ipost[2], ipost[0]])
    L = loop_impedances(y, z1, z0)
    if abs(di0) > ground_ratio * max(abs(di1), 1e-12):
        mags = {"a": abs(dia), "b": abs(dib), "c": abs(dic)}
        top = max(mags.values())
        sel = [p for p, m in mags.items() if m >= frac * top]
        loops = [p + "g" for p in sel]
        if len(sel) == 2:
            # Double line-to-ground: one of the two ground loops sees the other phase's fault
            # current through the shared ground path and overreaches (on EvEMTBench a bolted
            # fault at 50 % read 39 % on the ground loop, 51 % on the phase loop). Release only
            # the phase-to-phase loop, as relay phase selectors do.
            loops = [{"ab": "ab", "bc": "bc", "ac": "ca"}["".join(sorted(sel))]]
    else:
        pair = {"ab": abs(dia - dib), "bc": abs(dib - dic), "ca": abs(dic - dia)}
        top = max(pair.values())
        loops = [k for k, m in pair.items() if m >= pair_frac * top]
    fwd = [L[k].imag for k in loops if L[k].imag > 0]
    return min(fwd) if fwd else default


def supervised_reactance(y, z1, z0, frac=0.5, default=10.0):
    """Distance estimate a real element would produce: among loops whose own current is at
    least `frac` of the largest loop current (a crude phase selector) and whose reactance is
    forward, take the smallest reactance. Thresholding this is setting a zone reach."""
    L = loop_impedances(y, z1, z0, with_current=True)
    imax = max(c for _z, c in L.values())
    if imax <= 0:
        return default
    cand = [z.imag for z, c in L.values() if c >= frac * imax and z.imag > 0]
    return min(cand) if cand else default


def apparent_impedance(y, kind="ag", z1=None, z0=None):
    """One loop, selected by name. Ground loops use k0 compensation when z1 and z0 are given."""
    if z1 is not None and z0 is not None:
        return loop_impedances(y, z1, z0)[kind[:2] if kind[:2] in
                                          ("ag", "bg", "cg", "ab", "bc", "ca") else "ag"]
    (va, vb, vc), (ia, ib, ic) = _phase(y)
    if kind.startswith("ag"):
        return va / ia
    return (va - vb) / (ia - ib)
