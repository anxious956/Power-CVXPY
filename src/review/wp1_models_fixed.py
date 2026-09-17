"""
Corrected phase-a-to-phase-b fault for the sequence solvers (review of aux_model.py:74-75, 86-88 and
zone_model.py:73, 113-115).

The code imposes  I1 = -I2 (I0 = 0)  and  V1 - V2 = Rf I1  with sequence quantities referenced to
phase a. Those are the textbook boundary conditions of a phase-b-to-phase-c fault. With the same
phase-a reference an a-b fault (Ic = 0, Ia = -Ib, Va - Vb = Rf Ia) is

    I0 = 0,   I2 = -a^2 I1,   V1 - a V2 = Rf I1,       a = e^{j 2 pi / 3}
(derivation: Ic = a I1 + a^2 I2 = 0 ; Ia = (1 - a^2) I1 ; Va - Vb = (1 - a^2) V1 + (1 - a) V2 and
 (1 - a)/(1 - a^2) = 1/(1 + a) = -a).

The functions below are copies of aux_model.solve and zone_model.solve_zone with only those two
places changed, selected by kind 'ab_true' / 'ab_true2'. Nothing in src/ is modified.
"""
import numpy as np
from wp1_common import SRC  # noqa: F401  (puts src on sys.path)
import aux_model
import zone_model

A = np.exp(2j * np.pi / 3)


def solve_fixed(p, scen, srcL, i_R, delta, m=0.5, mr=0.0, inj0=0.0):
    if scen != "ab_true":
        return aux_model.solve(p, scen, srcL, i_R, delta, m, mr, inj0)
    zl = {1: p.z1, 2: p.z1, 0: p.z0}
    inj = {1: i_R, 2: delta, 0: inj0}
    Rf = mr * p.rF
    idx, k = {}, 0
    for s in (1, 2, 0):
        for node in ("L", "F", "R"):
            idx[(s, node)] = k; k += 1
    iF = 9
    Am = np.zeros((10, 10), complex); b = np.zeros(10, complex)
    r = 0
    for s in (1, 2, 0):
        L, F, R = idx[(s, "L")], idx[(s, "F")], idx[(s, "R")]
        za, zb = m * zl[s], (1 - m) * zl[s]
        if p.local == "SG":
            e = {1: srcL, 2: 0.0, 0: 0.0}[s]
            Am[r, L] = -1 / p.zs[s] - 1 / za; Am[r, F] = 1 / za; b[r] = -e / p.zs[s]
        else:
            injL = {1: srcL, 2: 0.0, 0: 0.0}[s]
            ysh = {1: 0.0, 2: 1 / p.ibr_neg_z, 0: 1 / p.ibr_zero_z}[s]
            Am[r, L] = -ysh - 1 / za; Am[r, F] = 1 / za; b[r] = -injL
        r += 1
        Am[r, L] = 1 / za; Am[r, F] = -1 / za - 1 / zb; Am[r, R] = 1 / zb
        Am[r, iF] = {1: -1.0, 2: A ** 2, 0: 0.0}[s]            # I1 = iF, I2 = -a^2 iF
        r += 1
        yshR = {1: 0.0, 2: 1 / p.ibr_neg_z, 0: 1 / p.ibr_zero_z}[s]
        Am[r, F] = 1 / zb; Am[r, R] = -1 / zb - p.yld[s] - yshR; b[r] = -inj[s]; r += 1
    Am[r, idx[(1, "F")]] = 1.0; Am[r, idx[(2, "F")]] = -A; Am[r, iF] = -Rf   # V1 - a V2 = Rf I1
    x = np.linalg.solve(Am, b)
    y = [x[idx[(s, "L")]] for s in (1, 2, 0)]
    for s in (1, 2, 0):
        y.append((x[idx[(s, "L")]] - x[idx[(s, "F")]]) / (m * zl[s]))
    return np.array(y)


def solve_zone_fixed(p, kind, srcL, iR, delta, m=0.5, mr=0.0, inj0=0.0):
    """Same as zone_model.solve_zone; 'ab_true' / 'ab_true2' use the a-b boundary conditions."""
    if kind not in ("ab_true", "ab_true2"):
        return zone_model.solve_zone(p, kind, srcL, iR, delta, m, mr, inj0)
    # reuse the original assembly by solving it twice is not possible (A is internal), so re-assemble
    on_line2 = kind.endswith("2")
    Rf = mr * p.rF
    SEQ = (1, 2, 0)
    idx, k = {}, 0
    for s in SEQ:
        for node in ("L", "F", "R", "S"):
            idx[(s, node)] = k; k += 1
    iF = 12
    Am = np.zeros((13, 13), complex); b = np.zeros(13, complex)
    r = 0
    for s in SEQ:
        L, F, R, S = (idx[(s, n)] for n in ("L", "F", "R", "S"))
        z1s, z2s = p.zl(1)[s], p.zl(2)[s]
        yR = p.yR[s] + (1 / p.ibr_zero_z if s == 0 else 0.0) + (1 / p.ibr_neg_z if s == 2 else 0.0)
        yS = p.yS[s]
        injR = {1: iR, 2: delta, 0: inj0}[s]
        fcoef = {1: -1.0, 2: A ** 2, 0: 0.0}[s]
        if not on_line2:
            za, zb = m * z1s, (1 - m) * z1s
            if p.local == "SG":
                e = srcL if s == 1 else 0.0
                Am[r, L] = -1 / p.zs[s] - 1 / za; Am[r, F] = 1 / za; b[r] = -e / p.zs[s]
            else:
                ysh = (1 / p.ibr_zero_z if s == 0 else 0.0) + (1 / p.ibr_neg_z if s == 2 else 0.0)
                Am[r, L] = -ysh - 1 / za; Am[r, F] = 1 / za; b[r] = -(srcL if s == 1 else 0.0)
            r += 1
            Am[r, L] = 1 / za; Am[r, F] = -1 / za - 1 / zb; Am[r, R] = 1 / zb; Am[r, iF] = fcoef; r += 1
            Am[r, F] = 1 / zb; Am[r, R] = -1 / zb - yR - 1 / z2s; Am[r, S] = 1 / z2s; b[r] = -injR; r += 1
            Am[r, R] = 1 / z2s; Am[r, S] = -1 / z2s - yS; r += 1
        else:
            za, zb = m * z2s, (1 - m) * z2s
            if p.local == "SG":
                e = srcL if s == 1 else 0.0
                Am[r, L] = -1 / p.zs[s] - 1 / z1s; Am[r, R] = 1 / z1s; b[r] = -e / p.zs[s]
            else:
                ysh = (1 / p.ibr_zero_z if s == 0 else 0.0) + (1 / p.ibr_neg_z if s == 2 else 0.0)
                Am[r, L] = -ysh - 1 / z1s; Am[r, R] = 1 / z1s; b[r] = -(srcL if s == 1 else 0.0)
            r += 1
            Am[r, L] = 1 / z1s; Am[r, R] = -1 / z1s - yR - 1 / za; Am[r, F] = 1 / za; b[r] = -injR; r += 1
            Am[r, R] = 1 / za; Am[r, F] = -1 / za - 1 / zb; Am[r, S] = 1 / zb; Am[r, iF] = fcoef; r += 1
            Am[r, F] = 1 / zb; Am[r, S] = -1 / zb - yS; r += 1
    Am[r, idx[(1, "F")]] = 1.0; Am[r, idx[(2, "F")]] = -A; Am[r, iF] = -Rf
    x = np.linalg.solve(Am, b)
    v = [x[idx[(s, "L")]] for s in SEQ]
    if on_line2:
        i = [(x[idx[(s, "L")]] - x[idx[(s, "R")]]) / p.zl(1)[s] for s in SEQ]
    else:
        i = [(x[idx[(s, "L")]] - x[idx[(s, "F")]]) / (m * p.zl(1)[s]) for s in SEQ]
    return np.array(v + i)
