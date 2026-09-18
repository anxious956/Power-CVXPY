"""H1 as a CERTIFICATE rather than a search result (REVIEW.md section 10, design follow-up 2).

THE CLAIM TO BE CERTIFIED
-------------------------
"No admissible delta with |delta| <= R separates the zone problem at this eps." DESIGN.md section 4
answers it by exhausting a polar grid, so every "none" is "none on that grid". The structure of the
problem gives a proof instead.

THE STRUCTURE
-------------
For one fault case, separation fails at delta exactly when the two uncertainty sets still intersect:

    exists u in [-1,1]^k, n in [-e,e]^12 :   G u + n  =  dc + dH [Re delta, Im delta]          (*)

The generator matrix G and the noise box do NOT depend on delta; delta only shifts the centre (dc is
the fault-minus-normal centre difference and dH its sensitivity). `affinity_check` verifies that
numerically against the nonlinear solver rather than taking it on trust: the network solve is linear
in the injected delta, the source perturbations enter the same right-hand side, and superposition
therefore holds exactly.

Given that, the right-hand side of (*) is affine in delta and the left-hand side is a fixed polytope
Z = G[-1,1]^k + [-e,e]^12 (a zonotope). So

    F = { delta : separation FAILS }  =  { delta : dc + dH delta in Z }

is the preimage of a convex polytope under an affine map: a convex POLYGON in the delta-plane, equal
to the intersection of the half-spaces  lambda^T dH delta <= h_Z(lambda) - lambda^T dc  over the facet
normals lambda of Z. Every delta inside F fails on that one fault case. Hence

    if  B_R = {|delta| <= R}  is contained in F for ANY single fault case,
    then no delta with |delta| <= R separates the problem -- a proof, not a search.

`failure_polygon` computes F exactly by support LPs with edge refinement (finite termination, because
F is a polygon), and returns the supporting hyperplanes. `inradius` is the largest R with B_R subset F.
The certificate is the list of hyperplanes plus the radius; it can be re-checked by hand.

THE CURRENT LIMIT
-----------------
With the limit inside the problem the uncertainty set is restricted to |i+| <= I_max - |delta|, which is
not affine in delta. Soundness is recovered by pruning at the radius of the disc: over |delta| <= R the
smallest admissible set is the one at |delta| = R, so a failure proved with headroom I_max - R holds for
every delta in the disc (the true set at smaller |delta| is larger, and a larger set can only keep the
intersection non-empty). `certify` takes `i_max` and does exactly that.

    python src/review/tac25_certificate.py [--eps 0.16] [--R 1.5]
    -> results/review_wp1/tac25_certificate.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from scipy.optimize import linprog
from wp1_common import ModelSet, source_sets, affine_case, realify
from aux_model import Params, solve
import tac25_design as td
from tac25_map import make_params, sir_of
from review import common as cm

OUT = os.path.join(cm.ROOT, "results", "review_wp1")
TOL = 1e-9


# --------------------------------------------------------------------- premise: affinity in delta
def affinity_check(p, mode="outer", n_draw=12, seed=0):
    """Verify y(delta, u) = c + H delta + G u against the nonlinear solver, for the normal case and a
    few fault cases. Returns the largest absolute residual over all draws (should be ~1e-12)."""
    rng = np.random.default_rng(seed)
    (sL0, gL), (iR0, gR) = source_sets(p, mode)
    worst = 0.0
    cases = [("N", 0.5, 0.0)] + [(s, m, mr) for s in p.scen for m in (0.15, 0.55, 0.95) for mr in (0.0, 1.0)]
    for scen, m, mr in cases:
        c, H, G = affine_case(p, scen, m, mr, mode)
        for _ in range(n_draw):
            d = complex(rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5))
            u = rng.uniform(-1, 1, 4)
            sL = sL0 + u[0] * gL[0] + u[1] * gL[1]
            iR = iR0 + u[2] * gR[0] + u[3] * gR[1]
            y = realify(solve(p, scen, sL, iR, d, m, mr))
            pred = c + H @ np.array([d.real, d.imag]) + G @ u
            worst = max(worst, float(np.abs(y - pred).max()))
    return worst


# --------------------------------------------------------------------- the failure polygon
def _support(dc, dH, G, e, w, A_ub=None, b_ub=None, big=50.0):
    """max w^T delta over {delta : dc + dH delta in Z}. Returns (value, argmax) or (None, None) if the
    set is empty. Variables [delta(2), u(k), n(12)]."""
    n, k = G.shape
    Aeq = np.hstack([dH, -G, -np.eye(n)])
    bounds = [(-big, big)] * 2 + [(-1, 1)] * k + [(-e, e)] * n
    c = np.zeros(2 + k + n); c[:2] = -w
    if A_ub is not None:
        A_ub = np.hstack([np.zeros((A_ub.shape[0], 2)), A_ub, np.zeros((A_ub.shape[0], n))])
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=Aeq, b_eq=-dc, bounds=bounds, method="highs")
    if res.status == 2:
        return None, None
    if res.status != 0:
        raise RuntimeError(res.message)
    return float(-res.fun), np.asarray(res.x[:2])


def failure_polygon(dc, dH, G, e, A_ub=None, b_ub=None, n_seed=16, max_iter=400, tol=1e-9, big=50.0):
    """Exact outer description of F = {delta : dc + dH delta in Z} as {W delta <= h}.

    Seeded with `n_seed` directions, then refined: for each adjacent pair of support directions whose
    support points differ, the edge normal between them is added. A polygon has finitely many edges, so
    the refinement terminates when every added normal is already tight at both neighbouring vertices.
    Returns dict with W, h, vertices, bounded, empty."""
    ang = np.linspace(0, 2 * np.pi, n_seed, endpoint=False)
    dirs = [np.array([np.cos(a), np.sin(a)]) for a in ang]
    W, h, V = [], [], []
    for w in dirs:
        val, arg = _support(dc, dH, G, e, w, A_ub, b_ub, big)
        if val is None:
            return dict(empty=True, bounded=None, W=None, h=None, vertices=None)
        W.append(w); h.append(val); V.append(arg)
    W, h, V = np.stack(W), np.asarray(h), np.stack(V)
    bounded = bool(np.abs(V).max() < big - 1e-6)
    it = 0
    while it < max_iter:
        it += 1
        new = []
        order = np.argsort(np.arctan2(W[:, 1], W[:, 0]))
        Ws, hs, Vs = W[order], h[order], V[order]
        for i in range(len(Ws)):
            j = (i + 1) % len(Ws)
            a, b = Vs[i], Vs[j]
            if np.linalg.norm(a - b) < 1e-7:
                continue                                   # same vertex: the two directions share it
            edge = b - a
            wn = np.array([edge[1], -edge[0]])
            nrm = np.linalg.norm(wn)
            if nrm < 1e-12:
                continue
            wn = wn / nrm
            if wn @ a < (wn @ Vs[i]) - 1e-12:
                wn = -wn
            if any(np.linalg.norm(wn - w0) < 1e-7 for w0 in W):
                continue
            new.append(wn)
        if not new:
            break
        for w in new:
            val, arg = _support(dc, dH, G, e, w, A_ub, b_ub, big)
            if val is None:
                return dict(empty=True, bounded=None, W=None, h=None, vertices=None)
            W = np.vstack([W, w]); h = np.append(h, val); V = np.vstack([V, arg])
            bounded = bounded and bool(np.abs(arg).max() < big - 1e-6)
    return dict(empty=False, bounded=bounded, W=W, h=h, vertices=V, n_faces=int(len(h)), iters=it)


def inradius(poly, tol=TOL):
    """Largest R with {|delta| <= R} contained in the polygon {W delta <= h}; 0 if the origin is not
    strictly inside (the polygon's faces all have unit normals, so h_i is the distance)."""
    if poly.get("empty") or poly["W"] is None:
        return 0.0
    W, h = poly["W"], poly["h"]
    nrm = np.linalg.norm(W, axis=1)
    d = h / np.maximum(nrm, 1e-15)
    return float(max(0.0, d.min())) if (d > tol).all() else 0.0


# --------------------------------------------------------------------- the certificate
def certify(p, mode="outer", R=1.5, rho=0.0, i_max=None, n_seed=16, verbose=True):
    """Try to certify 'no delta with |delta| <= R separates'. Succeeds if some single fault case fails
    for the whole disc. With `i_max`, the uncertainty is pruned at headroom i_max - R, which is sound
    for the whole disc (see the module docstring)."""
    ms = ModelSet(p, mode=mode)
    e = 2.0 * p.eps * (1.0 + rho)
    A_ub = b_ub = None
    head = None
    if i_max is not None:
        head = i_max - R
        if not td.limit_feasible(p, mode, head):
            return dict(certified=None, reason=f"no admissible pre-fault current at headroom {head:.3f}; "
                                               "the limit itself makes the problem vacuous at this R")
        k2 = ms.pair(ms.faults[0])[2].shape[1]
        A_ub, b_ub = td.limit_rows(p, mode, k2 // 2, head)
    best = dict(radius=-1.0, case=None)
    per_case = []
    for f in ms.faults:
        dc, dH, G = ms.pair(f)
        poly = failure_polygon(dc, dH, G, e, A_ub, b_ub, n_seed=n_seed)
        r = inradius(poly)
        per_case.append(dict(case=list(map(str, f[0])), covered_radius=r, n_faces=poly.get("n_faces"),
                             bounded=poly.get("bounded"), empty=bool(poly.get("empty"))))
        if r > best["radius"]:
            best = dict(radius=r, case=f[0], poly=poly)
        if verbose:
            print(f"    {str(f[0]):28s} covers |delta| <= {r:.3f}"
                  + ("" if not poly.get("empty") else "  (separated at every delta)"), flush=True)
    cert = dict(certified=bool(best["radius"] >= R - 1e-9), R=float(R), eps=float(p.eps), rho=float(rho),
                i_max=(None if i_max is None else float(i_max)), headroom=(None if head is None else float(head)),
                covered_radius=float(best["radius"]), certifying_case=list(map(str, best["case"])) if best["case"] else None,
                per_case=per_case)
    if best.get("poly") and best["poly"].get("W") is not None:
        W, h = best["poly"]["W"], best["poly"]["h"]
        keep = np.argsort(h / np.linalg.norm(W, axis=1))[:8]      # the binding hyperplanes
        cert["supporting_hyperplanes"] = [dict(w=[float(x) for x in W[i]], h=float(h[i]),
                                               distance=float(h[i] / np.linalg.norm(W[i]))) for i in keep]
        cert["n_faces"] = int(len(h))
    return cert


def main(eps_list=(0.16,), R=1.5, rho=0.0, i_max_list=(None, 1.2, 2.1)):
    t0 = time.time()
    res = dict(script="tac25_certificate", commit=cm.git_commit(), R=R, rho=rho, results=[])
    p0 = make_params(0.16)
    res["affinity_residual"] = affinity_check(p0)
    res["affinity_holds"] = bool(res["affinity_residual"] < 1e-8)
    print(f"affinity of the separation condition in delta: max residual {res['affinity_residual']:.2e} "
          f"-> {'HOLDS' if res['affinity_holds'] else 'FAILS'}", flush=True)
    if not res["affinity_holds"]:
        res["note"] = "the affinity premise failed; H1 stays a search result at the stated grid"
        json.dump(res, open(os.path.join(OUT, "tac25_certificate.json"), "w"), indent=1, default=str)
        return res
    for eps in eps_list:
        p = make_params(eps)
        for im in i_max_list:
            print(f"  eps {eps:g}, i_max {im}, R {R}", flush=True)
            c = certify(p, R=R, rho=rho, i_max=im)
            c["sir"] = sir_of(p)
            res["results"].append(c)
            print(f"  -> certified={c.get('certified')} covered_radius={c.get('covered_radius')}", flush=True)
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "tac25_certificate.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, f"[{res['runtime_s']:.0f}s]")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--eps", type=float, nargs="+", default=[0.16])
    ap.add_argument("--R", type=float, default=1.5)
    ap.add_argument("--rho", type=float, default=0.0)
    a = ap.parse_args()
    main(tuple(a.eps), a.R, a.rho)
