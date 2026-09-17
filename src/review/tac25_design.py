"""The auxiliary-signal design with the inverter current limit INSIDE the formulation, in the sense
of TAC25 (Taylor & Dominguez-Garcia, IEEE TAC 70(8):5523-5529, 2025), plus the review's other
corrections carried over. This is the corrected H5, and the engine behind results/DESIGN.md.

WHY THIS IS NOT WHAT H5 DID
---------------------------
TAC25 section II: "the constraints in (1b) restrict the values x can take on in P0_S, increasing
its objective. The presence of such constraints can, therefore, only increase sigma_S(theta),
shrinking the size of auxiliary signal needed to attain separation."

There are two different things one can do with an inverter current limit, and they pull opposite
ways:

  (a) treat it as a restriction on the DESIGN VARIABLE: the chosen delta must satisfy
      |i+| + |delta| <= I_max for every i+ in the source set. This removes candidate deltas and can
      only make the answer worse or infeasible. This is what src/review/wp1_h5_current_limit.py
      does -- it builds a mask on the delta-plane and intersects it with the separating region --
      and it is why REVIEW.md's H5 row reads "every preset needing delta > 0 infeasible at 1.2 pu".

  (b) treat it as a restriction on WHAT THE RELAY CAN OBSERVE: an inverter that is injecting delta
      physically cannot also be carrying a positive-sequence current larger than I_max - |delta|,
      so source realisations outside that disc do not occur and must be removed from the
      uncertainty set before separation is tested. A smaller uncertainty set is easier to separate.
      This is TAC25's (1b) and it is what this module adds.

Both are real. (a) is a hard feasibility limit on the answer; (b) shrinks the problem. The honest
design applies BOTH at once, which is what `min_delta(..., limit_inside=True)` does: at a candidate
delta of magnitude |delta|, the realisable positive-sequence current is restricted to
|i+| <= I_max - |delta| AND that must be non-empty. H5 applied only (a).

The disc |i+| <= r is imposed as a CIRCUMSCRIBED regular polygon, Re(i+ e^{-j theta_k}) <= r for
N equally spaced angles. A circumscribed polygon contains the disc, so it keeps slightly more
realisations than are physical: the restriction is understated, never overstated, and the result
stays a sound guarantee.

OTHER CORRECTIONS CARRIED OVER
------------------------------
  H6  sound outer source set          mode="outer" (wp1_common.sector_outer_box), not the
                                      linearised angle generator
  H14 separation margin               the noise box is inflated to (1 + rho) * eps, so a design is
                                      only accepted if it still separates with rho of headroom in
                                      measurement units
  H2  noise tied to CT/VT class       eps is an argument, fed from the corrected fault-condition
                                      figures (papers/notes/E_practitioner_settings.md section 7)
  H15 global solve                    a polar grid over the whole delta-plane, not the alternating
                                      scheme; the smallest separating radius is returned
  H13 continuous (m, R_f) validation  `validate_continuous` re-tests the returned delta on a dense
                                      (m, mr) grid rather than the 30 design points
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from scipy.optimize import linprog
from wp1_common import ModelSet, source_sets, affine_case
from aux_model import Params

N_POLY = 24            # circumscribed polygon for the current-limit disc
IMAX_DEFAULT = 1.2


# --------------------------------------------------------------------------- current-limit rows
def limit_rows(p, mode, n_u_block, r_head, n_poly=N_POLY):
    """Linear rows enforcing |i+| <= r_head on BOTH uncertainty blocks of a separation LP.

    The pair LP has u = [u_N (k), u_F (k)]; within each block the last two coordinates are the
    remote IBR current generators (wp1_common.source_sets returns 2 generators for each source).
    Returns (A, b) with A u <= b, or (None, None) if the constraint is vacuous.
    """
    _, (c, g) = source_sets(p, mode)
    k = n_u_block
    rows, rhs = [], []
    ang = np.linspace(0, 2 * np.pi, n_poly, endpoint=False)
    for th in ang:
        e = np.exp(-1j * th)
        # Re((c + g0 u_{k-2} + g1 u_{k-1}) e^{-j th}) <= r_head
        for blk in (0, 1):
            a = np.zeros(2 * k)
            a[blk * k + k - 2] = (g[0] * e).real
            a[blk * k + k - 1] = (g[1] * e).real
            rows.append(a)
            rhs.append(r_head - (c * e).real)
    return np.array(rows), np.array(rhs)


def limit_feasible(p, mode, r_head):
    """Is any modelled positive-sequence realisation still possible at this headroom?
    (Uses the same circumscribed polygon, so it errs towards saying yes.)"""
    _, (c, g) = source_sets(p, mode)
    A, b = [], []
    ang = np.linspace(0, 2 * np.pi, N_POLY, endpoint=False)
    for th in ang:
        e = np.exp(-1j * th)
        A.append([(g[0] * e).real, (g[1] * e).real])
        b.append(r_head - (c * e).real)
    res = linprog(np.zeros(2), A_ub=np.array(A), b_ub=np.array(b), bounds=[(-1, 1)] * 2, method="highs")
    return res.status == 0


# --------------------------------------------------------------------------- separation at one delta
def separated_at(ms, dv, eps_eff, limit=None):
    """True iff EVERY fault case is separated from normal at delta = dv.

    `limit` is (p, mode, r_head) to restrict both uncertainty blocks to |i+| <= r_head, or None.
    Short-circuits on the first pair that is not separated."""
    d2 = np.array([dv.real, dv.imag])
    for f in ms.faults:
        dc, dH, G = ms.pair(f)
        n, k2 = G.shape
        beq = dc + dH @ d2
        Aeq = np.hstack([G, np.eye(n)])
        bounds = [(-1, 1)] * k2 + [(-eps_eff * 2, eps_eff * 2)] * n
        if limit is None:
            res = linprog(np.zeros(k2 + n), A_eq=Aeq, b_eq=beq, bounds=bounds, method="highs")
        else:
            p, mode, r_head = limit
            A, b = limit_rows(p, mode, k2 // 2, r_head)
            A = np.hstack([A, np.zeros((A.shape[0], n))])
            res = linprog(np.zeros(k2 + n), A_ub=A, b_ub=b, A_eq=Aeq, b_eq=beq, bounds=bounds, method="highs")
        if res.status != 2:          # 2 = infeasible = the two sets do not intersect = separated
            return False
    return True


# --------------------------------------------------------------------------- global solve
def min_delta(ms, i_max=IMAX_DEFAULT, limit_inside=True, limit_design=True, rho=0.0,
              r_step=0.02, n_ang=72, r_max=None):
    """Smallest |delta| that separates every pair, searched globally on a polar grid.

    limit_design  apply (a): reject delta with |i+|max + |delta| > I_max   [what H5 did]
    limit_inside  apply (b): restrict the uncertainty to |i+| <= I_max - |delta|   [TAC25]
    rho           separation margin in measurement units: the noise box is inflated to (1+rho) eps
    """
    p, mode = ms.p, ms.mode
    eps_eff = ms.eps * (1.0 + rho)
    _, (c, g) = source_sets(p, mode)
    i_plus_max = float(max(abs(c + s1 * g[0] + s2 * g[1]) for s1 in (-1, 1) for s2 in (-1, 1)))
    r_max = (i_max if limit_design else 2.0) if r_max is None else r_max
    radii = np.arange(0.0, r_max + 1e-9, r_step)
    angs = np.linspace(0, 2 * np.pi, n_ang, endpoint=False)
    tried = 0
    for r in radii:
        if limit_design and i_plus_max + r > i_max + 1e-12:
            continue                                     # (a) no admissible i+ leaves room for this delta
        lim = None
        if limit_inside:
            head = i_max - r
            if not limit_feasible(p, mode, head):
                continue                                 # inverter cannot even carry its own pre-fault current
            lim = (p, mode, head)
        for a in (angs if r > 0 else [0.0]):
            dv = r * np.exp(1j * a)
            tried += 1
            if separated_at(ms, dv, eps_eff, lim):
                return dict(delta=complex(dv), abs_delta=float(r), angle_deg=float(np.degrees(a)),
                            feasible=True, lps=tried, i_plus_max=i_plus_max,
                            headroom=float(i_max - r) if limit_inside else None)
    return dict(delta=None, abs_delta=None, angle_deg=None, feasible=False, lps=tried,
                i_plus_max=i_plus_max, r_max_searched=float(r_max))


# --------------------------------------------------------------------------- H13 continuous check
def validate_continuous(p, mode, dv, eps_eff, n_m=21, n_mr=11, i_max=None, limit_inside=False):
    """Re-test a design on a dense (m, R_f) grid rather than the 30 design points (H13)."""
    # tuples, not arrays: ModelSet uses `m_grid or p.m_grid`, which is ambiguous for an ndarray
    ms = ModelSet(p, mode=mode, m_grid=tuple(np.linspace(min(p.m_grid), max(p.m_grid), n_m)),
                  mr_grid=tuple(np.linspace(0.0, 1.0, n_mr)), eps=p.eps)
    lim = None
    if limit_inside and i_max is not None:
        lim = (p, mode, i_max - abs(dv))
    bad = []
    d2 = np.array([dv.real, dv.imag])
    for f in ms.faults:
        dc, dH, G = ms.pair(f)
        n, k2 = G.shape
        Aeq = np.hstack([G, np.eye(n)])
        bounds = [(-1, 1)] * k2 + [(-eps_eff * 2, eps_eff * 2)] * n
        if lim is None:
            res = linprog(np.zeros(k2 + n), A_eq=Aeq, b_eq=dc + dH @ d2, bounds=bounds, method="highs")
        else:
            A, b = limit_rows(p, mode, k2 // 2, lim[2])
            A = np.hstack([A, np.zeros((A.shape[0], n))])
            res = linprog(np.zeros(k2 + n), A_ub=A, b_ub=b, A_eq=Aeq, b_eq=dc + dH @ d2, bounds=bounds, method="highs")
        if res.status != 2:
            bad.append(f[0])
    return dict(n_checked=len(ms.faults), n_unseparated=len(bad),
                unseparated=[list(map(float, b[1:])) + [b[0]] for b in bad[:20]], holds=bool(not bad))
