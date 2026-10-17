"""
The design and the set test with both frames a real system has (docs/STEP3.md, "the two frames"):

  - the inverter references I1 and delta to its own measured V1 (I1 = i_cmd u, delta = d_cmd u, u = V1_R/|V1_R|,
    i_cmd and d_cmd fixed in that frame), then applies its limiter; V1_R depends on the injections, so the
    delivered state is a fixed point (network.solve_v1ref). Where several exist, the start (the pre-fault frame,
    as in EMT) picks one;
  - the relay references its phasors to its own pre-fault V1 memory (y_rel = y conj(u_L), u_L = V1_L/|V1_L|
    before the fault), frozen during the fault (memory polarisation, as review/q3_inputs.seq_traj).

Neither is affine in the uncertain sources. Each case's measurement set is enclosed in a union of zonotopes, one
per piece of a split of the source box, each a linear model in shared symbols plus a remainder box:

    y_rel in  c + J w + diag(r) v,   w in [-1, 1]^k shared, v in [-1, 1]^12.

  - the shared symbols w are the four source symbols (EMF magnitude and angle, the inverter's commanded current,
    radial and tangential) and, for a fault, the inverter frame's position in its move from the pre-fault to the
    fault angle through the relay window (lambda) and a drift margin: the same symbols move every component;
  - the linear part (c, J) is a near-minimax fit per component over the samples (Lawson's iteratively reweighted
    least squares), not a derivative at the centre (at large delta the centre sits on the limiter's kink); the box
    is split in two along the commanded-current magnitude, the kink's axis (review round on frames.py, 16 Oct 2026);
  - r is the largest residual over the samples (random interior points, the box corners and a grid on every
    2-face), times a small factor. **Verified by sampling, not proved**: `containment_adversarial` searches for
    violations, and `scenario_bound` states the probabilistic coverage (Calafiore-Campi);
  - the relay's reference is itself measured with noise, which rotates the whole vector by up to
    phi_max = eps / min |V1_L| rad: that rotation is one more shared symbol, sampled and fitted like the others.
    The bound holds because the noise box eps is defined in the RELAY's frame, where V1_L sits at 0 deg and its
    angle error is Im(n) / |V1_L| <= eps / |V1_L|. (A box defined in the raw DFT frame would need sqrt(2) eps /
    |V1_L|, since V1_L's angle there is arbitrary.) A systematic VT phase error is not this rotation: it turns the
    voltages and the reference but not the currents, so after de-rotation it is a relative V-I angle error of
    0.035-0.07 rad x |i|. It is not in the eps budget here; it belongs to the instrument model of the data and to
    the violation matrix (docs/STEP3.md).

A case whose |V1_R| falls below `v1_min` has no usable inverter frame; its rotation is sampled over the full
circle, and the case is reported (`dead_frames`).

The arithmetic is vectorised: in every case the circuit matrix is fixed, the injections only change the right-hand
side, so the relay's measurement and V1 at the inverter bus are fixed linear maps of (EMF, I1, delta).
"""
import os, sys, itertools
import numpy as np
from scipy.optimize import linprog
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import network as nw

A3 = nw.A3


def unit_maps(net, inj, fault):
    """Linear maps of one case: y = My @ [e, i1, d], V1 at the inverter bus = mv @ [e, i1, d]."""
    (sg,) = list(net.sgs)
    zero = {k: 0.0 for k in list(net.sgs) + list(net.ibrs)}
    cols_y, cols_v = [], []
    for which in ("e", "i1", "d"):
        vals, dels = dict(zero), {}
        if which == "e":
            vals[sg] = 1.0
        elif which == "i1":
            vals[inj] = 1.0
        else:
            dels[inj] = 1.0
        y, V = nw.solve(net, vals, dels, fault, full=True)
        cols_y.append(y)
        cols_v.append(V[net.ibrs[inj].bus][0])
    return np.stack(cols_y, 1), np.array(cols_v)


def limiter_vec(i1, d, i_max, lim=1):
    """network.limiter on arrays."""
    i1, d = np.asarray(i1, complex), np.asarray(d, complex)
    if lim == 1:
        s = np.ones(i1.shape)
        for k in range(3):
            q, r = i1 * A3 ** (-k), d * A3 ** k
            a, b, c = np.abs(q) ** 2, (q * np.conj(r)).real, np.abs(r) ** 2 - i_max ** 2
            ok = (c < 0) & (a > 1e-12)
            sk = np.where(ok, (-b + np.sqrt(np.maximum(b * b - a * c, 0.0))) / np.where(a > 1e-12, a, 1.0), np.inf)
            s = np.minimum(s, sk)
        i1 = np.maximum(s, 0.0) * i1
    peak = np.max(np.stack([np.abs(i1 * A3 ** (-k) + d * A3 ** k) for k in range(3)]), 0)
    sc = np.minimum(1.0, i_max / np.maximum(peak, 1e-12))
    return sc * i1, sc * d


def fixed_point(mv, e, i_cmd, d_cmd, i_max, lim, u0, iters=200, tol=1e-12):
    """Vectorised V1-referenced fixed point: (u, i1, d, |V1_R|). Raises if any sample has not converged
    (the scalar network.solve_v1ref does the same)."""
    u = u0.copy()
    for _ in range(iters):
        i1, d = limiter_vec(i_cmd * u, d_cmd * u, i_max, lim)
        v = mv[0] * e + mv[1] * i1 + mv[2] * d
        un = v / np.maximum(np.abs(v), 1e-12)
        step = np.max(np.abs(un - u))
        u = un
        if step < tol:
            break
    else:
        raise RuntimeError(f"frames.fixed_point: not converged after {iters} iterations (step {step:.1e})")
    i1, d = limiter_vec(i_cmd * u, d_cmd * u, i_max, lim)
    v = mv[0] * e + mv[1] * i1 + mv[2] * d
    return u, i1, d, np.abs(v)


def lawson_minimax(A, Y, iters=25):
    """Near-minimax (L-infinity) linear fit of every column of Y on A, by Lawson's iteratively reweighted least
    squares, all columns at once through their weighted normal equations; returns beta (k, m). Never worse than
    the least-squares fit it starts from (the best iterate is kept). Checked against an exact LP minimax on the
    worst component: within 0.02 eps."""
    n, m = Y.shape
    W = np.full((n, m), 1.0 / n)
    beta_ls, *_ = np.linalg.lstsq(A, Y, rcond=None)
    best, best_err = beta_ls.copy(), np.abs(Y - A @ beta_ls).max(0)
    k = A.shape[1]
    for _ in range(iters):
        beta = np.empty_like(beta_ls)
        for j in range(m):
            Aw = A * W[:, j:j + 1]
            beta[:, j] = np.linalg.solve(Aw.T @ A + 1e-14 * np.eye(k), Aw.T @ Y[:, j])
        R = np.abs(Y - A @ beta)
        err = R.max(0)
        better = err < best_err
        best[:, better], best_err[better] = beta[:, better], err[better]
        W = W * R
        W = W / np.maximum(W.sum(0, keepdims=True), 1e-300)
    return best


def _realify2(Y):
    return np.concatenate([Y.real, Y.imag], 1)


def box_samples(lo, hi, n_random, rng, face_pts=5):
    """Random interior points, every corner, and a grid on every 2-face of the box [lo, hi] (4 dims)."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    k = len(lo)
    pts = [lo + (hi - lo) * rng.uniform(0, 1, (n_random, k))]
    pts.append(np.array(list(itertools.product(*zip(lo, hi)))))
    g = np.linspace(0, 1, face_pts)
    for i, j in itertools.combinations(range(k), 2):
        others = [m for m in range(k) if m not in (i, j)]
        for fixed in itertools.product(*[(lo[m], hi[m]) for m in others]):
            for a in g:
                for b in g:
                    p = np.empty(k)
                    p[i], p[j] = lo[i] + (hi[i] - lo[i]) * a, lo[j] + (hi[j] - lo[j]) * b
                    p[others] = fixed
                    pts.append(p[None])
    return np.vstack(pts)


def scenario_bound(n_iid, d, beta=1e-3):
    """Calafiore-Campi: an envelope fitted to n_iid i.i.d. samples with d decision variables per component (the
    fitted c and J, plus the bound itself) covers, per component, at least a fraction 1 - 2(ln(1/beta) + d)/n_iid
    of the sampling measure, with confidence 1 - beta. Only the random interior points are i.i.d.; the corners,
    face grid and the lambda / drift / reference grids are deterministic and do not count (review of PR #44).
    Stated, not used to set r."""
    return 1.0 - 2.0 * (np.log(1.0 / beta) + d) / n_iid


class FrameModel:
    """Normal operation and fault cases at one relay, with both frames, for one injecting inverter."""

    def __init__(self, net, cases, eps=None, lim=1, n_samples=400, factor=1.1, drift_deg=6.0, v1_min=0.05,
                 transient_steps=5, seed=0, split=True, ref_noise=True, shared=True, face_pts=5, ref_phi=None,
                 model_err=0.0):
        """ref_phi: the relay reference's rotation budget in rad (None: eps / min|V1_L|, the instantaneous worst
        case; the memory averages random noise over its window, and a systematic VT phase error moves voltages and
        reference together, so a smaller budget is defensible: report delta* against it). model_err: a box (pu,
        per real component) added to every remainder for the static-vs-EMT model error (up to 0.35 eps at 0.38 s on
        the stored runs, review of PR #44)."""
        self.net, self.cases, self.lim = net, list(cases), lim
        self.eps = net.eps if eps is None else eps
        (self.inj,) = net.injectors
        (self.sg,) = list(net.sgs)
        g = net.ibrs[self.inj]
        self.i_max = g.i_max or 1.2
        self.n, self.factor, self.drift, self.v1_min, self.steps = n_samples, factor, np.radians(drift_deg), v1_min, transient_steps
        self.split, self.ref_noise, self.shared = split, ref_noise, shared
        self.ref_phi, self.model_err = ref_phi, model_err
        self.maps_N = unit_maps(net, self.inj, None)
        self.maps_F = [unit_maps(net, self.inj, (ln, m, s, mr * net.rF)) for ln, m, s, mr in self.cases]
        _, V = nw.solve(net, {}, {}, None, full=True)
        self.u_nom = V[g.bus][0] / abs(V[g.bus][0])
        self.cE, self.gE = nw.source_set(net, "sg", self.sg, "outer")
        cI, gI = nw.source_set(net, "ibr", self.inj, "outer")
        rot = np.conj(self.u_nom)                       # the nominal current, in the inverter's own frame
        self.cI, self.gI = cI * rot, [x * rot for x in gI]
        self.rng = np.random.default_rng(seed)
        self.pieces = [((-1, -1, -1, -1), (1, 1, 0, 1)), ((-1, -1, 0, -1), (1, 1, 1, 1))] if split else [((-1,) * 4, (1,) * 4)]
        self.samples = [box_samples(lo, hi, n_samples, self.rng, face_pts) for lo, hi in self.pieces]
        self._cache = {}

    # ---------------------------------------------------------------- realisations
    def sources(self, S):
        e = self.cE + self.gE[0] * S[:, 0] + self.gE[1] * S[:, 1]
        i_cmd = self.cI + self.gI[0] * S[:, 2] + self.gI[1] * S[:, 3]
        return e, i_cmd

    def normal_state(self, S, d_cmd):
        e, i_cmd = self.sources(S)
        My, mv = self.maps_N
        u, i1, d, v1 = fixed_point(mv, e, i_cmd, d_cmd, self.i_max, self.lim, np.full(len(S), self.u_nom))
        y = My[:, 0][None] * e[:, None] + My[:, 1][None] * i1[:, None] + My[:, 2][None] * d[:, None]
        return y, y[:, 0] / np.abs(y[:, 0]), u

    def measure(self, S, d_cmd, case=None, lam=None, drift=None):
        """Relay measurements in the relay's own pre-fault frame, one row per sample. For a fault, lam in [0, 1]
        (the inverter frame's position between its pre-fault and fault angles) and drift in [-1, 1] (times the
        drift margin) are per-sample arrays (default: the settled fault state, no drift)."""
        yN, uL, u_pre = self.normal_state(S, d_cmd)
        if case is None:
            return yN * np.conj(uL)[:, None]
        e, i_cmd = self.sources(S)
        My, mv = self.maps_F[case]
        u_f, _, _, v1 = fixed_point(mv, e, i_cmd, d_cmd, self.i_max, self.lim, u_pre)
        lam = np.ones(len(S)) if lam is None else lam
        drift = np.zeros(len(S)) if drift is None else drift
        uu = (1 - lam) * u_pre + lam * u_f
        uu = uu / np.maximum(np.abs(uu), 1e-12) * np.exp(1j * self.drift * drift * lam)
        dead = v1 < self.v1_min
        if dead.any():                                   # no usable frame: any angle
            uu = uu.copy()
            uu[dead] = np.exp(1j * self.rng.uniform(0, 2 * np.pi, dead.sum()))
        i1, d = limiter_vec(i_cmd * uu, d_cmd * uu, self.i_max, self.lim)
        y = My[:, 0][None] * e[:, None] + My[:, 1][None] * i1[:, None] + My[:, 2][None] * d[:, None]
        return y * np.conj(uL)[:, None]

    def dead_frames(self, d_cmd):
        out = []
        S = np.vstack(self.samples)
        e, i_cmd = self.sources(S)
        _, _, u_pre = self.normal_state(S, d_cmd)
        for k in range(len(self.cases)):
            *_, v1 = fixed_point(self.maps_F[k][1], e, i_cmd, d_cmd, self.i_max, self.lim, u_pre)
            if (v1 < self.v1_min).any():
                out.append(self.cases[k])
        return out

    def _expand(self, S, case):
        """Samples and their shared-symbol coordinates: (S rows, lam, drift, ref, W). ref in [-1, 1] is the
        relay reference's noise rotation (times phi_max); lam and drift exist for faults only."""
        refs = np.array([-1.0, 0.0, 1.0]) if self.ref_noise else np.array([0.0])
        if case is None:
            Sx = np.repeat(S, len(refs), 0)
            ref = np.tile(refs, len(S))
            return Sx, None, None, ref, np.hstack([Sx, ref[:, None]])
        lams = np.linspace(0.0, 1.0, self.steps)
        drs = np.array([-1.0, 0.0, 1.0]) if self.drift else np.array([0.0])
        grid = np.array(list(itertools.product(lams, drs, refs)))
        Sx = np.repeat(S, len(grid), 0)
        lam, dr, ref = (np.tile(grid[:, j], len(S)) for j in range(3))
        W = np.hstack([Sx, (2 * lam - 1)[:, None], dr[:, None], ref[:, None]])
        return Sx, lam, dr, ref, W

    def phi_max(self, d_cmd):
        if self.ref_phi is not None:
            return self.ref_phi
        S = np.vstack(self.samples)
        return self.eps / np.min(np.abs(self.measure(S, d_cmd, None)[:, 0]))

    # ---------------------------------------------------------------- zonotopes
    def zonotopes(self, d_cmd, case=None):
        """The union for one set: a list of (c, G), one per piece of the source box."""
        key = (complex(d_cmd), case)
        if key in self._cache:
            return self._cache[key]
        out = []
        phi = self.phi_max(d_cmd) if self.ref_noise else 0.0
        for (lo, hi), S in zip(self.pieces, self.samples):
            Sx, lam, dr, ref, W = self._expand(S, case)
            Y = self.measure(Sx, d_cmd, case, lam, dr) * np.exp(1j * phi * ref)[:, None]
            Yr = _realify2(Y)
            lo_, hi_ = np.asarray(lo, float), np.asarray(hi, float)
            mid, half = (lo_ + hi_) / 2, (hi_ - lo_) / 2
            Wn = W.copy()
            Wn[:, :4] = (W[:, :4] - mid) / half             # shared symbols in [-1, 1] on this piece
            if self.shared:
                A = np.hstack([np.ones((len(Wn), 1)), Wn])
                beta = lawson_minimax(A, Yr)
                c, J = beta[0], beta[1:].T                   # (12,), (12, k)
                R = Yr - A @ beta
            else:                                            # ablation: no shared symbols, everything in the box
                c = (Yr.max(0) + Yr.min(0)) / 2
                J = np.zeros((12, 0))
                R = Yr - c
            resid = np.abs(R).max(0)                    # the fitted J's actual largest residual over all samples
            r = resid * self.factor + self.model_err + 1e-9
            assert np.all(r >= resid), "remainder must cover the actual residual, not the fit's own estimate"
            out.append((c, np.hstack([J, np.diag(r)])))
        self._cache[key] = out
        return out

    def sets(self, d_cmd):
        return self.zonotopes(d_cmd, None), [self.zonotopes(d_cmd, k) for k in range(len(self.cases))]


def _meet(cN, GN, cF, GF, bound):
    """Do N + box(bound) and F intersect? (LP feasibility; bound = 2 eps for two noisy sets)."""
    n = cN.size
    bb = np.broadcast_to(np.asarray(bound, float), (n,))         # a scalar, or one bound per real component
    Aeq = np.hstack([GN, -GF, np.eye(n)])
    res = linprog(np.zeros(Aeq.shape[1]), A_eq=Aeq, b_eq=cF - cN,
                  bounds=[(-1, 1)] * (GN.shape[1] + GF.shape[1]) + [(-x, x) for x in bb], method="highs")
    return res.status == 0


def _meet_union(Ns, Fs, bound):
    return any(_meet(cN, GN, cF, GF, bound) for cN, GN in Ns for cF, GF in Fs)


def separated(fm, d_cmd, rho=0.0):
    Ns, F = fm.sets(d_cmd)
    b = 2 * fm.eps * (1 + rho)
    return all(not _meet_union(Ns, Fs, b) for Fs in F)


def unseparated(fm, d_cmd, rho=0.0):
    Ns, F = fm.sets(d_cmd)
    b = 2 * fm.eps * (1 + rho)
    return [fm.cases[k] for k, Fs in enumerate(F) if _meet_union(Ns, Fs, b)]


def witness(fm, d_cmd, case):
    """The closest pair of N(d_cmd) and one fault set: their infinity-norm gap (pu; the case separates with margin
    rho if gap > 2 eps (1 + rho)) and the source points where it occurs, S_N and S_F in the [-1, 1]^4 box, with
    the fault side's frame symbols. These are the realisations to run in EMT for a design check."""
    k = fm.cases.index(tuple(case)) if not isinstance(case, int) else case
    best = None
    for i, (cN, GN) in enumerate(fm.zonotopes(d_cmd, None)):
        for j, (cF, GF) in enumerate(fm.zonotopes(d_cmd, k)):
            n, kn, kf = cN.size, GN.shape[1], GF.shape[1]
            c = np.zeros(kn + kf + n + 1)
            c[-1] = 1
            A_eq = np.hstack([GN, -GF, np.eye(n), np.zeros((n, 1))])
            A_ub = np.vstack([np.hstack([np.zeros((n, kn + kf)), np.eye(n), -np.ones((n, 1))]),
                              np.hstack([np.zeros((n, kn + kf)), -np.eye(n), -np.ones((n, 1))])])
            res = linprog(c, A_ub=A_ub, b_ub=np.zeros(2 * n), A_eq=A_eq, b_eq=cF - cN,
                          bounds=[(-1, 1)] * (kn + kf) + [(None, None)] * n + [(0, None)], method="highs")
            if res.status != 0:
                raise RuntimeError(f"frames.witness: LP failed ({res.message})")
            if best is None or res.x[-1] < best[0]:
                best = (res.x[-1], i, j, res.x[:kn], res.x[kn:kn + kf])
    gap, i, j, a, b = best
    to_box = lambda piece, w: (np.add(*map(np.asarray, fm.pieces[piece])) / 2
                               + (np.subtract(fm.pieces[piece][1], fm.pieces[piece][0]) / 2) * w[:4])
    return dict(gap=float(gap), S_N=to_box(i, a), S_F=to_box(j, b), lam=float((b[4] + 1) / 2), drift=float(b[5]))


class Inadmissible(Exception):
    pass


def separated_fast(fm, d_cmd, rho=0.0, order=None):
    """As separated(), building the fault sets lazily, hardest first, stopping at the first that meets N.
    Raises Inadmissible if the inverter has no settled state at this command (the V1-referenced fixed point does
    not converge; on the three-bus network this happens only at |d_cmd| = i_max, where the limiter leaves no I1
    and delta is referenced to the V1 it alone creates)."""
    try:
        Ns = fm.zonotopes(d_cmd, None)
    except RuntimeError as ex:
        raise Inadmissible(str(ex))
    b = 2 * fm.eps * (1 + rho)
    for k in (order or range(len(fm.cases))):
        try:
            Fs = fm.zonotopes(d_cmd, k)
        except RuntimeError as ex:
            raise Inadmissible(str(ex))
        if _meet_union(Ns, Fs, b):
            return False
    return True


def _try(fm, d, rho, order, skipped):
    try:
        return separated_fast(fm, d, rho, order)
    except Inadmissible:
        skipped.append(complex(d))
        return False


def min_delta_fast(fm, rho=0.0, coarse=(0.1, 24), fine=(0.02, 72), r_max=None):
    """Coarse polar grid to the first separating radius, then the fine grid from one coarse step below it. Each LP
    is exact at its d_cmd; the problem is not convex in d_cmd, so this is a grid search. The search stays below the
    inverter's current limit (|d_cmd| < i_max: at the limit no I1 fits beside delta); candidates without a settled
    inverter state are skipped and counted."""
    r_max = (fm.i_max - fine[0]) if r_max is None else r_max
    skipped = []
    hard = set(map(tuple, unseparated(fm, 0j, rho)))
    if not hard:
        return dict(d_cmd=0j, abs_delta=0.0, angle_deg=0.0, feasible=True)
    order = [k for k, c in enumerate(fm.cases) if tuple(c) in hard] + [k for k, c in enumerate(fm.cases) if tuple(c) not in hard]
    r0 = None
    for r in np.arange(coarse[0], r_max + 1e-9, coarse[0]):
        if any(_try(fm, r * np.exp(1j * a), rho, order, skipped) for a in np.linspace(0, 2 * np.pi, coarse[1], endpoint=False)):
            r0 = r
            break
    start = max(fine[0], (r0 - coarse[0]) if r0 is not None else r_max - coarse[0])
    rejected = []
    for r in np.arange(start, r_max + 1e-9, fine[0]):
        for a in np.linspace(0, 2 * np.pi, fine[1], endpoint=False):
            d = r * np.exp(1j * a)
            if _try(fm, d, rho, order, skipped):
                return dict(d_cmd=complex(d), abs_delta=float(round(r, 6)), angle_deg=float(np.degrees(a)), feasible=True,
                            coarse_first=None if r0 is None else float(r0), unseparated_at_0=sorted(hard),
                            inadmissible=len(skipped))
    return dict(d_cmd=None, abs_delta=None, angle_deg=None, feasible=False, unseparated_at_0=sorted(hard),
                inadmissible=len(skipped))


def distance_to_set(pieces, y_rel):
    """The smallest noise box (pu) that puts a relay measurement inside the union `pieces` (min over pieces)."""
    best = np.inf
    target_all = nw._realify(np.asarray(y_rel))
    for cN, GN in pieces:
        n, k = cN.size, GN.shape[1]
        c = np.zeros(k + n + 1)
        c[-1] = 1
        A_ub = np.vstack([np.hstack([np.zeros((n, k)), np.eye(n), -np.ones((n, 1))]),
                          np.hstack([np.zeros((n, k)), -np.eye(n), -np.ones((n, 1))])])
        res = linprog(c, A_ub=A_ub, b_ub=np.zeros(2 * n), A_eq=np.hstack([GN, np.eye(n), np.zeros((n, 1))]),
                      b_eq=target_all - cN, bounds=[(-1, 1)] * k + [(None, None)] * n + [(0, None)], method="highs")
        if res.status != 0:
            raise RuntimeError(f"distance_to_set: LP failed ({res.message})")
        best = min(best, res.x[-1])
    return best


def distance_to_normal(fm, y_rel, d_cmd):
    """D1: noise needed to put a relay measurement (relay frame) inside N(d_cmd)."""
    return distance_to_set(fm.zonotopes(d_cmd, None), y_rel)


def containment_adversarial(fm, d_cmd, cases=None, n_fresh=300, face_pts=9, n_local=60, seed=7):
    """Search for samples outside their own set (noise needed > 0): a finer 2-face grid than the design's, fresh
    random points, and local perturbations around the points with the largest residual. Returns
    {case or "N": largest distance found}."""
    rng = np.random.default_rng(seed)
    out = {}
    for case in [None] + (list(range(len(fm.cases))) if cases is None else list(cases)):
        pieces = fm.zonotopes(d_cmd, case)
        S = np.vstack([box_samples((-1,) * 4, (1,) * 4, n_fresh, rng, face_pts)])
        phi = fm.phi_max(d_cmd) if fm.ref_noise else 0.0
        Sx, lam, dr, ref, W = fm._expand(S, case)
        Y = fm.measure(Sx, d_cmd, case, lam, dr) * np.exp(1j * phi * ref)[:, None]
        # cheap pre-screen: distance to the nearer piece's centre-plus-box, then exact LPs on the worst
        score = np.array([min(np.abs(nw._realify(y) - c).max() for c, _ in pieces) for y in Y])
        worst_idx = np.argsort(score)[-n_local:]
        cand = list(Y[worst_idx])
        for i in worst_idx[: n_local // 3]:              # local perturbations around the worst points
            base = W[i]
            for _ in range(3):
                w = np.clip(base + rng.normal(0, 0.05, base.shape), -1, 1)
                if case is None:
                    y = fm.measure(w[None, :4], d_cmd, None)[0]
                else:
                    y = fm.measure(w[None, :4], d_cmd, case, np.array([(w[4] + 1) / 2]), np.array([w[5]]))[0]
                cand.append(y * np.exp(1j * phi * w[-1]))
        out["N" if case is None else fm.cases[case]] = max(distance_to_set(pieces, y) for y in cand)
    return out


def window(fm, r, rho=0.0, center_deg=None, half_width_deg=15, step_deg=1.0):
    """The angles (deg) at radius r that separate, scanned in 1 deg steps around center_deg (or over the full circle):
    the width of the separating window, which a two-decimal delta* should be quoted with."""
    angs = np.arange(0, 360, step_deg) if center_deg is None else \
        np.arange(center_deg - half_width_deg, center_deg + half_width_deg + 1e-9, step_deg)
    ok = []
    for a in angs:
        try:
            if separated_fast(fm, r * np.exp(1j * np.radians(a)), rho):
                ok.append(float(a % 360))
        except Inadmissible:
            pass
    return ok
