"""
Shared machinery for the WP1 review scripts (src/review/wp1_*.py).

Everything here works on the same objects as src/aux_model.py: a measurement model
    y = c + H [Re d, Im d] + G u + n,   |u|_inf <= 1,  |n|_inf <= eps
for the normal set N and for each fault case F.  N and F are separated by d iff the
difference of centres is outside the zonotope Z = {G_N u_N - G_F u_F + n_N - n_F}, whose
noise part is a box of half-width 2 eps.

Functions
  dist_inf(v, G, e)          inf-norm distance from v to {G u + n : |u|<=1, |n|<=e} (primal LP)
  margin_dual(v, G, e)       max_{||lam||_1<=1} lam.v - ||G^T lam||_1 - e ||lam||_1 (dual LP), equals dist_inf
  gauge_dual(v, G, e)        max lam.v s.t. ||G^T lam||_1 + e ||lam||_1 <= 1; >1 iff separated. Always
                             returns a useful direction, also when v is inside Z.
  ModelSet                   N + list of fault cases, with pluggable source generators
  polygon(...)               non-separating set of d for one pair, as a convex polygon (support LPs)
  global_min(...)            exact-on-grid minimum-norm separating d from the polygons
"""
import os, sys
import numpy as np
from scipy.optimize import linprog

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
ROOT = os.path.dirname(SRC)
sys.path.insert(0, SRC)
OUTDIR = os.path.join(ROOT, "results", "review_wp1")
os.makedirs(OUTDIR, exist_ok=True)

from aux_model import Params, PRESETS, solve, realify  # noqa: E402


# ----------------------------------------------------------------------------- LPs
def dist_inf(v, G, e):
    """min s  s.t.  v = G u + n + r, |u|<=1, |n|<=e, |r|_inf <= s.   0 when v in Z."""
    n, k = G.shape
    c = np.zeros(k + 1); c[-1] = 1.0
    one = np.ones((n, 1))
    A = np.block([[-G, -one], [G, -one]])
    b = np.concatenate([e - v, e + v])
    res = linprog(c, A_ub=A, b_ub=b, bounds=[(-1, 1)] * k + [(0, None)], method="highs")
    if res.status != 0:
        raise RuntimeError(res.message)
    return float(res.x[-1])


def _dual_lp(v, G, e, mode):
    n, k = G.shape
    # x = [lam (n), a (k) >= |G^T lam|, b (n) >= |lam|]
    I, Z = np.eye(n), np.zeros
    A = np.block([[G.T, -np.eye(k), Z((k, n))],
                  [-G.T, -np.eye(k), Z((k, n))],
                  [I, Z((n, k)), -I],
                  [-I, Z((n, k)), -I]])
    b = np.zeros(2 * k + 2 * n)
    if mode == "margin":        # max lam.v - sum a - e sum b  s.t. sum b <= 1
        c = np.concatenate([-v, np.ones(k), e * np.ones(n)])
        A = np.vstack([A, np.concatenate([Z(n), Z(k), np.ones(n)])]); b = np.append(b, 1.0)
    else:                       # gauge: max lam.v s.t. sum a + e sum b <= 1
        c = np.concatenate([-v, Z(k), Z(n)])
        A = np.vstack([A, np.concatenate([Z(n), np.ones(k), e * np.ones(n)])]); b = np.append(b, 1.0)
    bounds = [(None, None)] * n + [(0, None)] * (k + n)
    res = linprog(c, A_ub=A, b_ub=b, bounds=bounds, method="highs")
    if res.status != 0:
        raise RuntimeError(res.message)
    return float(-res.fun), res.x[:n]


def margin_dual(v, G, e):
    return _dual_lp(v, G, e, "margin")


def gauge_dual(v, G, e):
    return _dual_lp(v, G, e, "gauge")


def support_Z(lam, G, e):
    return float(np.abs(G.T @ lam).sum() + e * np.abs(lam).sum())


# ----------------------------------------------------------------------- source sets
def sector_linear(s0, dmag, dang):
    """The generators aux_model.source_generators uses: tangent line, not the arc."""
    return s0, [dmag * s0 / abs(s0), 1j * dang * s0]


def sector_linear_rel(s0, rel, dang):
    """SG version in aux_model: magnitude generator is relative (gen_e[0] * e0)."""
    return s0, [rel * s0, 1j * dang * s0]


def sector_outer_box(s0, rmin, rmax, g):
    """Sound outer zonotope (a box aligned with s0) of the annular sector
       {r e^{j(phi0 + phi)} : r in [rmin, rmax], |phi| <= g},  0 <= g <= pi/2, rmin >= 0.
       Radial extent [rmin cos g, rmax], tangential extent +-rmax sin g."""
    assert 0 <= g <= np.pi / 2 and 0 <= rmin <= rmax
    u = s0 / abs(s0)
    xlo, xhi = rmin * np.cos(g), rmax
    ylo = rmax * np.sin(g)
    return u * (xlo + xhi) / 2, [u * (xhi - xlo) / 2, 1j * u * ylo]


def sector_inner_box(s0, rmin, rmax, g, frac=0.5):
    """An inner box (aligned with s0) of the annular sector: every point of the box is a physical
    source value. Radial [x1, x2], tangential +-h with h = x1 tan g, x2 = sqrt(rmax^2 - h^2),
    x1 = rmin + frac * (rmax cos g - rmin) (needs x1 >= rmin, x1 < x2)."""
    x1 = rmin + frac * (rmax * np.cos(g) - rmin)
    h = x1 * np.tan(g)
    x2 = np.sqrt(rmax ** 2 - h ** 2)
    assert rmin <= x1 < x2 <= rmax and np.hypot(x1, h) >= rmin
    u = s0 / abs(s0)
    return u * (x1 + x2) / 2, [u * (x2 - x1) / 2, 1j * u * h]


def source_sets(p: Params, mode="linear"):
    """(centre, generators) of the local source and the remote IBR current."""
    if mode == "linear":
        if p.local == "SG":
            L = sector_linear_rel(p.e0, p.gen_e[0], p.gen_e[1])
        else:
            L = sector_linear(p.iL0, p.gen_i[0], p.gen_i[1])
        R = sector_linear(p.i0, p.gen_i[0], p.gen_i[1])
    elif mode == "outer":
        if p.local == "SG":
            r = abs(p.e0)
            L = sector_outer_box(p.e0, r * (1 - p.gen_e[0]), r * (1 + p.gen_e[0]), p.gen_e[1])
        else:
            r = abs(p.iL0)
            L = sector_outer_box(p.iL0, r - p.gen_i[0], r + p.gen_i[0], p.gen_i[1])
        r = abs(p.i0)
        R = sector_outer_box(p.i0, r - p.gen_i[0], r + p.gen_i[0], p.gen_i[1])
    else:
        raise ValueError(mode)
    return L, R


def sample_true_sources(p: Params, rng, n):
    """Physical (nonlinear) source samples: magnitude and angle drawn in the stated ranges."""
    u = rng.uniform(-1, 1, (n, 4))
    if p.local == "SG":
        sL = p.e0 * (1 + p.gen_e[0] * u[:, 0]) * np.exp(1j * p.gen_e[1] * u[:, 1])
    else:
        sL = (abs(p.iL0) + p.gen_i[0] * u[:, 0]) * np.exp(1j * (np.angle(p.iL0) + p.gen_i[1] * u[:, 1]))
    iR = (abs(p.i0) + p.gen_i[0] * u[:, 2]) * np.exp(1j * (np.angle(p.i0) + p.gen_i[1] * u[:, 3]))
    return sL, iR


def sample_linear_sources(p: Params, rng, n):
    (sL0, gL), (iR0, gR) = source_sets(p, "linear")
    u = rng.uniform(-1, 1, (n, 4))
    return sL0 + gL[0] * u[:, 0] + gL[1] * u[:, 1], iR0 + gR[0] * u[:, 2] + gR[1] * u[:, 3]


# -------------------------------------------------------------------------- models
def affine_case(p: Params, scen, m, mr, mode="linear", solver=None):
    """Same as aux_model.affine_model but with pluggable source sets (and centre shift)."""
    solver = solver or solve
    (sL0, gL), (iR0, gR) = source_sets(p, mode)
    y00 = solver(p, scen, sL0, iR0, 0.0, m, mr)
    yd = solver(p, scen, sL0, iR0, 1.0, m, mr) - y00
    ydj = solver(p, scen, sL0, iR0, 1j, m, mr) - y00
    gens = [solver(p, scen, sL0 + g, iR0, 0.0, m, mr) - y00 for g in gL]
    gens += [solver(p, scen, sL0, iR0 + g, 0.0, m, mr) - y00 for g in gR]
    return realify(y00), np.stack([realify(yd), realify(ydj)], 1), np.stack([realify(g) for g in gens], 1)


class ModelSet:
    """Normal set + fault cases (scen, m, mr) with source-set mode 'linear' or 'outer'."""

    def __init__(self, p: Params, mode="linear", m_grid=None, mr_grid=None, scen=None, eps=None, extra=()):
        self.p, self.mode = p, mode
        self.eps = p.eps if eps is None else eps
        self.N = affine_case(p, "N", 0.5, 0.0, mode)
        self.faults = []
        for s in (scen or p.scen):
            for m in (m_grid or p.m_grid):
                for mr in (mr_grid or p.mr_grid):
                    self.faults.append(((s, float(m), float(mr)), affine_case(p, s, m, mr, mode)))
        for key in extra:
            self.faults.append((key, affine_case(p, key[0], key[1], key[2], mode)))

    def add(self, key):
        self.faults.append((key, affine_case(self.p, key[0], key[1], key[2], self.mode)))

    def pair(self, f):
        (cN, HN, GN), (cF, HF, GF) = self.N, f[1]
        return cF - cN, HF - HN, np.hstack([GN, GF])

    def margins(self, d, eps=None):
        e = 2 * (self.eps if eps is None else eps)
        dv = np.array([np.real(d), np.imag(d)])
        out = []
        for f in self.faults:
            dc, dH, G = self.pair(f)
            out.append(dist_inf(dc + dH @ dv, G, e))
        return np.array(out)


# ------------------------------------------------------------ polygons in the d-plane
def polygon(dc, dH, G, e, ndir=180, R=3.0):
    """Non-separating set {d : dc + dH d in Z}, |d|_inf <= R, via support LPs.
    Returns (W, h, V): outer polygon {W d <= h} and support points V (inner hull)."""
    n, k = G.shape
    # vars [d(2), u(k), r(n)] ; dH d - G u - r = -dc ; |u|<=1, |r|<=e, |d|<=R
    Aeq = np.hstack([dH, -G, -np.eye(n)])
    bounds = [(-R, R)] * 2 + [(-1, 1)] * k + [(-e, e)] * n
    ang = np.linspace(0, 2 * np.pi, ndir, endpoint=False)
    W = np.stack([np.cos(ang), np.sin(ang)], 1)
    h, V = [], []
    for w in W:
        c = np.zeros(2 + k + n); c[:2] = -w
        res = linprog(c, A_eq=Aeq, b_eq=-dc, bounds=bounds, method="highs")
        if res.status == 2:
            return None
        if res.status != 0:
            raise RuntimeError(res.message)
        h.append(-res.fun); V.append(res.x[:2])
    return W, np.array(h), np.array(V)


def grid_separating(polys, R=1.5, step=0.01, tol=1e-7):
    """Boolean grid: True where d is outside every outer polygon (i.e. separates all pairs)."""
    ax = np.round(np.arange(-R, R + 1e-9, step), 10)
    RE, IM = np.meshgrid(ax, ax)
    P = np.stack([RE.ravel(), IM.ravel()], 1)
    ok = np.ones(len(P), bool)
    for poly in polys:
        if poly is None:
            continue
        W, h = poly[0], poly[1]
        for c0 in range(0, len(P), 8192):                      # chunked: memory is shared
            Q = P[c0:c0 + 8192]
            inside = np.all(Q @ W.T <= h[None, :] - tol, axis=1)   # strictly inside -> not separating
            ok[c0:c0 + 8192] &= ~inside
    return ax, ok.reshape(RE.shape)


def global_min_on_grid(polys, R=1.5, step=0.005, mask_fn=None):
    ax, ok = grid_separating(polys, R, step)
    RE, IM = np.meshgrid(ax, ax)
    if mask_fn is not None:
        ok = ok & mask_fn(RE + 1j * IM)
    if not ok.any():
        return None, ax, ok
    mag = np.abs(RE + 1j * IM)
    mag[~ok] = np.inf
    j = np.unravel_index(np.argmin(mag), mag.shape)
    return complex(RE[j], IM[j]), ax, ok


def components(ok):
    """Number of 4-connected components of a boolean grid (for connectivity claims)."""
    from scipy.ndimage import label
    lab, n = label(ok)
    return n


def dump(obj, name):
    import json
    path = os.path.join(OUTDIR, name)

    def conv(o):
        if isinstance(o, complex):
            return [o.real, o.imag]
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (np.bool_,)):
            return bool(o)
        raise TypeError(type(o))
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=conv)
    return path


def _outer_vertices(W, h):
    """Vertices of {W d <= h} for directions sorted by angle (consecutive halfplane intersections)."""
    n = len(h)
    V = []
    for i in range(n):
        j = (i + 1) % n
        A = np.array([W[i], W[j]])
        V.append(np.linalg.solve(A, [h[i], h[j]]))
    return np.array(V)


def inner_halfplanes(V, tol=1e-12):
    """Halfplanes of the convex hull of support points V (ordered by support direction, i.e. CCW)."""
    keep = [V[0]]
    for v in V[1:]:
        if np.linalg.norm(v - keep[-1]) > 1e-10:
            keep.append(v)
    if len(keep) > 1 and np.linalg.norm(keep[0] - keep[-1]) <= 1e-10:
        keep.pop()
    P = np.array(keep)
    if len(P) < 3:
        return None
    E = np.roll(P, -1, axis=0) - P
    Nn = np.stack([E[:, 1], -E[:, 0]], 1)
    Nn /= np.linalg.norm(Nn, axis=1, keepdims=True)
    return Nn, (Nn * P).sum(1), P


def as_inner(polys):
    """Replace every outer polygon by the convex hull of its support points (an inner polygon)."""
    out = []
    for poly in polys:
        if poly is None:
            out.append(None); continue
        hp = inner_halfplanes(poly[2])
        out.append(None if hp is None else (hp[0], hp[1], hp[2], "inner"))
    return out


def _is_inner(poly):
    return len(poly) == 4 and poly[3] == "inner"


def exact_min(polys, rmax, tol=1e-9, mask_fn=None):
    """Minimum-norm d outside the interior of every outer polygon, |d| <= rmax.
    Candidates: origin, projections of the origin onto every edge, pairwise edge intersections
    (only edges that come within rmax of the origin). Exact for the polygonal outer
    approximation; conservative (never below) w.r.t. the true non-separating sets."""
    segs = []
    for poly in polys:
        if poly is None:
            continue
        V = poly[2] if _is_inner(poly) else _outer_vertices(poly[0], poly[1])
        A, B = V, np.roll(V, -1, axis=0)
        segs.append(np.stack([A, B], 1))
    if not segs:
        return 0j
    S = np.concatenate(segs)                       # (ns, 2, 2)
    A, B = S[:, 0], S[:, 1]
    AB = B - A
    L2 = (AB ** 2).sum(1) + 1e-300
    t = np.clip(-(A * AB).sum(1) / L2, 0, 1)
    proj = A + t[:, None] * AB
    near = np.linalg.norm(proj, axis=1) <= rmax
    cands = [np.zeros((1, 2)), proj[near], A[np.linalg.norm(A, axis=1) <= rmax]]
    An, ABn = A[near], AB[near]
    m = len(An)
    for i in range(m):                              # segment-segment intersections
        r, s = ABn[i], ABn
        den = r[0] * s[:, 1] - r[1] * s[:, 0]
        qp = An - An[i]
        with np.errstate(divide="ignore", invalid="ignore"):
            tt = (qp[:, 0] * s[:, 1] - qp[:, 1] * s[:, 0]) / den
            uu = (qp[:, 0] * r[1] - qp[:, 1] * r[0]) / den
        ok = (np.abs(den) > 1e-14) & (tt >= 0) & (tt <= 1) & (uu >= 0) & (uu <= 1)
        cands.append(An[i] + tt[ok, None] * r)
    C = np.concatenate(cands)
    C = C[np.linalg.norm(C, axis=1) <= rmax]
    order = np.argsort(np.linalg.norm(C, axis=1))
    C = C[order]
    for chunk in range(0, len(C), 4096):
        P = C[chunk:chunk + 4096]
        bad = np.zeros(len(P), bool)
        for poly in polys:
            if poly is None:
                continue
            W, h = poly[0], poly[1]
            bad |= np.all(P @ W.T < h[None, :] - tol, axis=1)
        if mask_fn is not None:
            bad |= ~mask_fn(P[:, 0] + 1j * P[:, 1])
        good = np.where(~bad)[0]
        if len(good):
            q = P[good[0]]
            return complex(q[0], q[1])
    return None


def ms_polygons(ms, eps_total=None, ndir=180, R=3.0, cache=None):
    """Polygons for every fault of a ModelSet (cached on disk under logs/cache)."""
    import pickle, hashlib
    e = 2 * ms.eps if eps_total is None else eps_total
    if cache:
        cdir = os.path.join(ROOT, "logs", "cache"); os.makedirs(cdir, exist_ok=True)
        key = hashlib.md5(repr((cache, e, ndir, R, [f[0] for f in ms.faults])).encode()).hexdigest()
        path = os.path.join(cdir, key + ".pkl")
        if os.path.exists(path):
            return pickle.load(open(path, "rb"))
    polys = [polygon(*ms.pair(f), e, ndir, R) for f in ms.faults]
    if cache:
        pickle.dump(polys, open(path, "wb"))
    return polys


# ---------------------------------------------------------------- alternating scheme
def alternating(ms, d0, mu=0.0, lam_mode="author", tau=1e-3, iters=30, extra_cons=None):
    """Alternating Farkas scheme.
    lam_mode='author': lam = argmax lam.v - h_Z(lam) s.t. ||lam||_inf <= 1, QP margin tau (as
                       aux_signal_toy.py:237-262). Fails (QP infeasible) when a pair is not
                       separated at the current iterate, because then lam = 0.
    lam_mode='normalized': lam from gauge LP (works inside Z too), rescaled to ||lam||_1 = 1, QP
                       constraint lam.v(d) - h_Z(lam) >= mu, so mu is an inf-norm distance in pu.
    Returns (d, history, status)."""
    import cvxpy as cp
    e = 2 * ms.eps
    dv = np.array([np.real(d0), np.imag(d0)], float)
    hist = []
    for it in range(iters):
        lams = []
        for f in ms.faults:
            dc, dH, G = ms.pair(f)
            v = dc + dH @ dv
            if lam_mode == "author":
                lam = cp.Variable(v.size)
                obj = lam @ v - cp.norm1(G.T @ lam) - e * cp.norm1(lam)
                cp.Problem(cp.Maximize(obj), [cp.norm_inf(lam) <= 1]).solve(solver=cp.CLARABEL)
                lams.append(np.asarray(lam.value))
            else:
                _, lam = gauge_dual(v, G, e)
                lams.append(lam / max(np.abs(lam).sum(), 1e-300))
        d = cp.Variable(2)
        cons = []
        for f, lam in zip(ms.faults, lams):
            dc, dH, G = ms.pair(f)
            hz = support_Z(lam, G, e)
            rhs = hz + (tau if lam_mode == "author" else mu)
            cons.append(lam @ (dc + dH @ d) >= rhs)
        if extra_cons is not None:
            cons += extra_cons(d)
        prob = cp.Problem(cp.Minimize(cp.sum_squares(d)), cons)
        try:
            prob.solve(solver=cp.CLARABEL)
        except Exception:
            return complex(*dv), hist, "solver_error"
        if d.value is None or prob.status not in ("optimal", "optimal_inaccurate"):
            return complex(*dv), hist, f"qp_{prob.status}_it{it}"
        hist.append(float(np.linalg.norm(d.value)))
        if np.linalg.norm(d.value - dv) < 1e-6:
            dv = d.value
            return complex(*dv), hist, "converged"
        dv = d.value
    return complex(*dv), hist, "maxiter"


def bracket_min(ms, polys, rmax=1.5, polish=True):
    """Global minimum-norm separating d bracketed by inner-hull polygons (lower bound) and outer
    polygons (upper bound, verified by LP), then polished by the normalized alternating scheme from
    the outer point (a separating point with margin ~1e-7 at or below the upper bound)."""
    up = exact_min(polys, rmax)
    lo = exact_min(as_inner(polys), rmax)
    out = dict(lower=None if lo is None else abs(lo), upper=None if up is None else abs(up),
               upper_point=up, lower_point=lo)
    if up is not None and abs(up) > 0 and polish:
        dp, _, st = alternating(ms, up, mu=1e-7, lam_mode="normalized", iters=40)
        mg = ms.margins(dp).min()
        out.update(polished=abs(dp), polished_point=dp, polished_status=st, polished_margin=float(mg))
        if mg > 0 and abs(dp) < abs(up):
            out["best_verified"] = abs(dp); out["best_point"] = dp
        else:
            out["best_verified"] = abs(up); out["best_point"] = up
    elif up is not None:
        out.update(best_verified=abs(up), best_point=up)
    return out
