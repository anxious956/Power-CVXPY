"""The auxiliary-signal design problem in the formulation of

    J. A. Taylor and A. D. Dominguez-Garcia, "Active fault detection in static systems",
    IEEE Trans. Automatic Control 70(8):5523-5529, 2025.  DOI 10.1109/TAC.2024.3510612
    (papers/Taylor_2025_Active_Fault_Detection_Static_Systems.pdf)

referred to below as TAC25. This supersedes the 2023 conference formulation that
src/aux_model.py and src/aux_signal_toy.py implement. The differences that matter to this project
are set out in papers/notes/F_taylor_tac_and_gfm_model.md; the two that drive this module are:

  * TAC25 (1b) puts system limits -- an inverter current limit above all -- INSIDE the design
    problem as constraints on the measurement, where they SHRINK the required signal:
    "the constraints make the detection problem easier by shrinking the range of possible
    observations" (TAC25 section II). REVIEW.md's H5 applied the limit as an outer feasibility
    check AFTER designing delta, which can only ever remove solutions.
  * TAC25 Theorem 1 gives a closed-form NECESSARY condition on ||theta||, evaluable from the
    system matrices with no optimisation at all.


MODEL MAPPING
-------------
src/aux_model.affine_model returns, for one scenario (normal or a fault at (m, mr)),

    y = c + Hd [Re delta, Im delta] + G u + n,    ||u||_inf <= 1,  ||n||_inf <= eps      (real, 12-dim)

TAC25 model k is  ([Theta_k, X_k] + G_k(xi_k)) [theta; x] = h_k + H_k lambda_k,  ||lambda_k|| < 1.
Rearranging ours into that shape with the measurement as x = y:

    -Hd theta + I y = c + [G, eps I] [u; n/eps]

so  Theta_k = -Hd_k,   X_k = I,   h_k = c_k,   H_k = [G_k, eps I],  lambda_k = [u; n/eps].


THE ONE GEOMETRY CHANGE, STATED PLAINLY
---------------------------------------
TAC25 bounds the uncertainty in the EUCLIDEAN norm, ||lambda|| < 1; aux_model bounds it in the
INFINITY norm (a zonotope). These are different sets and the answers are not interchangeable.
For H = [G, eps I] with d columns:

    {H lambda : ||lambda||_2 <= 1}      is INSCRIBED in the zonotope   -> less uncertainty
    {H lambda : ||lambda||_2 <= sqrt(d)} CONTAINS the zonotope         -> more uncertainty

Every result from this module is therefore reported as a bracket, `inscribed` and `circumscribed`,
and the zonotope answer lies between them. The inscribed case is the one that must satisfy
    Theorem-1 bound (inscribed)  <=  exact zonotope optimum
and that inequality is the validation gate in tac25_theorem1.py.

Theorem 1 additionally needs H_k to have full COLUMN rank so it can be folded into the other
matrices by pseudoinverse. Our H_k is wide (12 x d, d > 12). The ellipsoid {H lambda : ||lambda||<=1}
equals {z : z' (H H')^-1 z <= 1}, so we replace H_k by the symmetric square root of H_k H_k',
which is square, and positive definite whenever eps > 0 (because H H' >= eps^2 I). This is an exact
re-parameterisation of the same ellipsoid, not an approximation.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import scipy.linalg as sla
import aux_model as am

NOISE_GEOMETRY = ("inscribed", "circumscribed")


# --------------------------------------------------------------------------- model assembly
def model_matrices(c, Hd, G, eps, geometry="inscribed"):
    """One TAC25 model from one affine scenario.

    Returns Theta (12x2), X (12x12), h (12,), M (12x12 uncertainty shaping, symmetric PD),
    where the uncertainty set is {M lambda : ||lambda||_2 <= 1}."""
    n = c.size
    H = np.hstack([G, eps * np.eye(n)])
    if geometry == "circumscribed":
        H = H * np.sqrt(H.shape[1])          # ball of radius sqrt(d) written as radius 1
    elif geometry != "inscribed":
        raise ValueError(geometry)
    M = sla.sqrtm(H @ H.T)
    M = np.real((M + M.T) / 2)
    return -Hd, np.eye(n), c.copy(), M


def fold(Theta, X, h, M):
    """Pre-multiply by M^-1 so the uncertainty becomes an unshaped unit ball (TAC25 section V:
    'incorporated into the other system matrices via the pseudoinverse')."""
    Mi = np.linalg.inv(M)
    return Mi @ Theta, Mi @ X, Mi @ h


# --------------------------------------------------------------------------- Theorem 1
def theorem1(models):
    """TAC25 Theorem 1 for one pair S = {0, 1}.

        chi  = max_k || Theta_k - X_k Lx^-1 Lt ||
        zeta = max_k || (X_k Lx^-1 X_k' - I) h_k + X_k Lx^-1 X_j' h_j ||     (j the other model)
        if ||theta|| < (1 - zeta) / chi  then theta does not separate S.

    `models` is a 2-sequence of (Theta, X, h) already folded. The paper's norm convention is
    Frobenius for matrices (TAC25 section II); the spectral norm is also valid in the
    Cauchy-Schwarz step of the proof and is never larger, so it gives a tighter -- still sound --
    bound. Both are returned; `bound` uses the spectral norm.
    """
    (T0, X0, h0), (T1, X1, h1) = models
    Lx = X0.T @ X0 + X1.T @ X1
    Lt = X0.T @ T0 + X1.T @ T1
    Lxi = np.linalg.inv(Lx)
    A0, A1 = T0 - X0 @ Lxi @ Lt, T1 - X1 @ Lxi @ Lt
    b0 = (X0 @ Lxi @ X0.T - np.eye(X0.shape[0])) @ h0 + X0 @ Lxi @ X1.T @ h1
    b1 = X1 @ Lxi @ X0.T @ h0 + (X1 @ Lxi @ X1.T - np.eye(X1.shape[0])) @ h1
    zeta = float(max(np.linalg.norm(b0), np.linalg.norm(b1)))
    chi_s = float(max(np.linalg.norm(A0, 2), np.linalg.norm(A1, 2)))
    chi_f = float(max(np.linalg.norm(A0, "fro"), np.linalg.norm(A1, "fro")))
    bnd = lambda chi: (float("inf") if chi <= 0 else (1.0 - zeta) / chi)
    return dict(chi_spectral=chi_s, chi_frobenius=chi_f, zeta=zeta,
                bound=bnd(chi_s), bound_frobenius=bnd(chi_f),
                # TAC25 Corollary 3: models differ enough that no signal is needed
                no_signal_needed=bool(zeta >= 1.0),
                # TAC25 Corollary 2: identical models, no signal of any size separates them
                identical_models=bool(chi_s <= 1e-12 and zeta <= 1e-12))


def omega_hat(models, theta):
    """The exact mean-uncertainty objective of TAC25 eq. (8) at a given theta, i.e. the quantity
    the triangle inequality in Theorem 1's proof bounds. max(sqrt(w0), sqrt(w1)) >= 1 is the
    NECESSARY condition for separation; w_mean >= 1 is SUFFICIENT (TAC25 Lemma 2)."""
    (T0, X0, h0), (T1, X1, h1) = models
    Lx = X0.T @ X0 + X1.T @ X1
    Lt = X0.T @ T0 + X1.T @ T1
    Lxi = np.linalg.inv(Lx)
    r0 = (T0 - X0 @ Lxi @ Lt) @ theta + (X0 @ Lxi @ X0.T - np.eye(X0.shape[0])) @ h0 + X0 @ Lxi @ X1.T @ h1
    r1 = (T1 - X1 @ Lxi @ Lt) @ theta + X1 @ Lxi @ X0.T @ h0 + (X1 @ Lxi @ X1.T - np.eye(X1.shape[0])) @ h1
    w0, w1 = float(r0 @ r0), float(r1 @ r1)
    return dict(w0=w0, w1=w1, w_mean=0.5 * (w0 + w1), w_max=max(w0, w1),
                separates_sufficient=bool(0.5 * (w0 + w1) >= 1.0),
                separates_possible=bool(max(w0, w1) >= 1.0))


# --------------------------------------------------------------------------- problem wrapper
class TAC25Problem:
    """All models of an aux_model.Params instance, in TAC25 form, for one noise geometry."""

    def __init__(self, p: am.Params, geometry="inscribed", eps=None):
        self.p, self.geometry = p, (eps if eps is not None else p.eps) and geometry
        self.geometry = geometry
        self.eps = p.eps if eps is None else eps
        cN, HN, GN = am.affine_model(p, "N")
        self.normal = dict(label="N", raw=(cN, HN, GN), **self._mk(cN, HN, GN))
        self.faults = []
        for scen in p.scen:
            for m in p.m_grid:
                for mr in p.mr_grid:
                    c, H, G = am.affine_model(p, scen, m, mr)
                    self.faults.append(dict(label=f"{scen}|m={m:g}|mr={mr:g}", scen=scen, m=m, mr=mr,
                                            raw=(c, H, G), **self._mk(c, H, G)))

    def _mk(self, c, H, G):
        Th, X, h, M = model_matrices(c, H, G, self.eps, self.geometry)
        Thf, Xf, hf = fold(Th, X, h, M)
        return dict(folded=(Thf, Xf, hf), M=M)

    def pair_bounds(self):
        """Theorem 1 for every (normal, fault) pair. The signal must satisfy every pair, so the
        overall certified lower bound on |delta| is the maximum over pairs."""
        rows = []
        for f in self.faults:
            r = theorem1([self.normal["folded"], f["folded"]])
            rows.append(dict(pair=f"N vs {f['label']}", scen=f["scen"], m=f["m"], mr=f["mr"], **r))
        finite = [r["bound"] for r in rows if np.isfinite(r["bound"]) and not r["no_signal_needed"]]
        return dict(rows=rows, n_pairs=len(rows),
                    n_no_signal_needed=int(sum(r["no_signal_needed"] for r in rows)),
                    lower_bound=float(max(finite)) if finite else 0.0,
                    binding_pair=max(rows, key=lambda r: (not r["no_signal_needed"]) * r["bound"])["pair"] if finite else None)
