"""
H16: reproduce the single-IBR single-load example of
  J. A. Taylor, A. D. Dominguez-Garcia, "Auxiliary Signal-Based Distance Protection in
  Inverter-Dominated Power Systems", arXiv:2311.10880 (2023), Sec. V and Appendix; Figs. 2-3.

Setup exactly as printed: z- = z+ = 30 + j35, zf = 26 + j xf, xf in [12, 58] (step 2, 24 points as
in Fig. 3), H0 = H1 = I, no inequality constraints (A_k, b_k absent), Q = I, noise
||lambda_k||_2 <= 1 on the stacked real vector (Appendix, eq. (7) in real form).

The Appendix prints the real form of a complex impedance as
      M = [[r, -x], [r, x]]            ("printed")
whereas multiplication by r + jx is
      M = [[r, -x], [x,  r]]           ("correct")
Both are run. Three solvers per xf:
  exact  : sigma(theta) = optimal value of P0 (SOCP, CVXPY+Clarabel); sigma is convex and
           2-homogeneous in theta, so the minimum |theta| with sigma >= 1 is
           min_phi 1/sqrt(sigma(e^{j phi})) over 720 directions.
  closed : correct -> 2/|zf - z-| ; printed -> sqrt(2)/max(|dr|, |dx|)  (derived in WP1_REPORT.md)
  CCP    : the convex-concave procedure on P2 (paper Sec. IV) with CVXPY+Clarabel (the paper used
           Gurobi). gamma0, gamma_max, zeta, theta0, beta0 are not given in the paper; we use
           gamma0=1, zeta=1.5, gamma_max=1e4, 60 iterations, 2 starts.
Fig. 3 values were read off the rendered PDF figure (300 dpi), +-0.003.

  python src/review/wp1_taylor2023.py       (~3-5 min)
"""
import os, sys, time, json
import numpy as np
import cvxpy as cp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "results", "review_wp1")
os.makedirs(OUT, exist_ok=True)

ZM = ZP = 30 + 35j
XF = np.arange(12, 59, 2)
FIG3_READ = [0.066, 0.072, 0.079, 0.087, 0.098, 0.112, 0.132, 0.160, 0.205, 0.287, 0.357, 0.356,
             0.356, 0.357, 0.287, 0.205, 0.160, 0.133, 0.113, 0.099, 0.088, 0.080, 0.073, 0.068]


def Mreal(z, conv):
    r, x = z.real, z.imag
    return np.array([[r, -x], [r, x]]) if conv == "printed" else np.array([[r, -x], [x, r]])


def matrices(xf, conv):
    Mm, Mp, Mf = Mreal(ZM, conv), Mreal(ZP, conv), Mreal(26 + 1j * xf, conv)
    I, O = np.eye(2), np.zeros((2, 2))
    Th = [np.vstack([-Mm, O]), np.vstack([-Mf, O])]
    X = [np.block([[I, O, O], [O, I, -Mp]]), np.block([[I, O, O], [O, I, -Mf]])]
    return Th, X


def sigma(theta, xf, conv):
    """P0: min omega s.t. Theta_k theta + X_k x = lambda_k, ||lambda_k||^2 <= omega."""
    Th, X = matrices(xf, conv)
    x = cp.Variable(6)
    lams = [Th[k] @ theta + X[k] @ x for k in (0, 1)]
    w = cp.Variable()
    prob = cp.Problem(cp.Minimize(w), [cp.sum_squares(l) <= w for l in lams])
    prob.solve(solver=cp.CLARABEL)
    return float(prob.value)


def exact_min(xf, conv, ndir=720):
    best = (np.inf, None)
    Th, X = matrices(xf, conv)
    x = cp.Variable(6); w = cp.Variable(); th = cp.Parameter(2)
    prob = cp.Problem(cp.Minimize(w), [cp.sum_squares(Th[k] @ th + X[k] @ x) <= w for k in (0, 1)])
    for phi in np.linspace(0, np.pi, ndir // 2, endpoint=False):     # sigma(-t) = sigma(t)
        th.value = np.array([np.cos(phi), np.sin(phi)])
        prob.solve(solver=cp.CLARABEL)
        s = max(prob.value, 1e-15)
        r = 1 / np.sqrt(s)
        if r < best[0]:
            best = (r, th.value * r)
    return best


def closed_form(xf, conv):
    dz = (26 + 1j * xf) - ZM
    if conv == "correct":
        return 2 / abs(dz)
    return np.sqrt(2) / max(abs(dz.real), abs(dz.imag))


def ccp(xf, conv, theta0, iters=60, g0=1.0, zeta=1.5, gmax=1e4):
    Th, X = matrices(xf, conv)
    th = cp.Variable(2)
    beta = [cp.Variable(4) for _ in (0, 1)]
    alpha = cp.Variable(2, nonneg=True)
    dlt = cp.Variable(2)
    xi = cp.Variable(nonneg=True)
    base = [alpha[0] + alpha[1] == 1,
            beta[0] @ X[0] + beta[1] @ X[1] == 0]                     # (4d), no A_k
    for k in (0, 1):
        base.append(cp.quad_over_lin(beta[k], alpha[k]) <= 4 * dlt[k])   # (4e) with H = I
    Psi = [np.block([[np.zeros((4, 4)), Th[k]], [Th[k].T, np.zeros((2, 2))]]) for k in (0, 1)]
    psi = [np.linalg.eigvalsh(P).max() for P in Psi]
    thz, bz = np.asarray(theta0, float), [np.zeros(4), np.zeros(4)]
    g = g0
    hist = []
    for it in range(iters):
        rhs = 0
        for k in (0, 1):
            z = cp.hstack([beta[k], th])
            zz = np.concatenate([bz[k], thz])
            Pm = psi[k] * np.eye(6) - Psi[k]                 # PSD; concave part = -1/4 z'Pm z
            Pp = Psi[k] + psi[k] * np.eye(6)                 # PSD; convex part, linearized
            conc = -0.25 * cp.quad_form(z, cp.psd_wrap(Pm))
            lin = 0.25 * zz @ Pp @ zz + 0.5 * (zz @ Pp) @ (z - zz)
            rhs = rhs + conc + lin - dlt[k]
        prob = cp.Problem(cp.Minimize(cp.sum_squares(th) + g * xi), base + [1 - xi <= rhs])
        prob.solve(solver=cp.CLARABEL)
        if th.value is None:
            return dict(status=prob.status, theta=None)
        new = th.value.copy()
        hist.append((float(np.linalg.norm(new)), float(xi.value)))
        done = np.linalg.norm(new - thz) < 1e-7 and xi.value < 1e-7
        thz, bz = new, [beta[0].value.copy(), beta[1].value.copy()]
        g = min(zeta * g, gmax)
        if done:
            break
    return dict(status="ok", theta=thz, abs=float(np.linalg.norm(thz)), xi=float(xi.value), iters=it + 1)


def main():
    t0 = time.time()
    rows = []
    for conv in ("printed", "correct"):
        for j, xf in enumerate(XF):
            r_exact, th_exact = exact_min(xf, conv)
            best = None
            for th0 in ([0.5, 0.5], [-0.7, 0.3]):
                c = ccp(xf, conv, th0)
                if c["theta"] is None:
                    continue
                c["sigma"] = sigma(c["theta"], xf, conv)
                if c["sigma"] >= 1 - 1e-5 and (best is None or c["abs"] < best["abs"]):
                    best = c
            rows.append(dict(conv=conv, xf=int(xf), exact=r_exact, exact_theta=th_exact,
                             closed=closed_form(xf, conv),
                             ccp=None if best is None else best["abs"],
                             ccp_theta=None if best is None else best["theta"],
                             ccp_sigma=None if best is None else best["sigma"],
                             ccp_xi=None if best is None else best["xi"], fig3=FIG3_READ[j]))
            rr = rows[-1]
            print(f"{conv:8s} xf={xf:2d}  exact {r_exact:.4f}  closed {rr['closed']:.4f}  "
                  f"CCP {rr['ccp'] if rr['ccp'] is None else round(rr['ccp'], 4)}  paper Fig.3 {FIG3_READ[j]:.3f}",
                  flush=True)

    # Fig. 2 replica: non-separating grid points for xf = 25, 35 (closed-form sigma check)
    fig2 = {}
    grid = np.round(np.arange(-1, 1.0001, 0.05), 3)
    for conv in ("printed", "correct"):
        for xf in (25, 35):
            dz = (26 + 1j * xf) - ZM
            MU, NU = np.meshgrid(grid, grid)
            if conv == "correct":
                s = abs(dz) ** 2 * (MU ** 2 + NU ** 2) / 4
            else:
                s = (dz.real ** 2 * MU ** 2 + dz.imag ** 2 * NU ** 2) / 2
            fig2[f"{conv}_{xf}"] = (s >= 1)
    # spot-check the closed form sigma against the SOCP on a few points
    chk = []
    rng = np.random.default_rng(0)
    for conv in ("printed", "correct"):
        for xf in (25, 35, 50):
            th = rng.uniform(-1, 1, 2)
            dz = (26 + 1j * xf) - ZM
            cf = abs(dz) ** 2 * (th @ th) / 4 if conv == "correct" else (dz.real ** 2 * th[0] ** 2 + dz.imag ** 2 * th[1] ** 2) / 2
            chk.append(dict(conv=conv, xf=xf, theta=th, sigma_socp=sigma(th, xf, conv), sigma_closed=cf))

    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(16, 4.8), gridspec_kw=dict(width_ratios=[1.6, 1, 1]))
    ax = axs[0]
    ax.plot(XF, FIG3_READ, "ko-", ms=5, label="paper Fig. 3 (read off figure)")
    for conv, c in (("printed", "tab:red"), ("correct", "tab:blue")):
        R = [r for r in rows if r["conv"] == conv]
        ax.plot(XF, [r["exact"] for r in R], "-", color=c, lw=2, alpha=.6, label=f"{conv} M: exact (P0 + polar sweep)")
        ax.plot(XF, [np.nan if r["ccp"] is None else r["ccp"] for r in R], "x", color=c, ms=7, label=f"{conv} M: CCP on P2")
    ax.set_xlabel("x_f (Ω)"); ax.set_ylabel("|θ| minimal separating"); ax.grid(alpha=.3); ax.legend(fontsize=8)
    ax.set_title("Taylor & Domínguez-García 2023, Fig. 3 reproduction")
    for a, xf in zip(axs[1:], (25, 35)):
        for conv, mk, c in (("printed", "o", "tab:red"), ("correct", ".", "tab:blue")):
            MU, NU = np.meshgrid(grid, grid)
            S = fig2[f"{conv}_{xf}"]
            a.scatter(MU[S], NU[S], s=10 if conv == "printed" else 3, marker=mk, facecolors="none" if conv == "printed" else c,
                      edgecolors=c if conv == "printed" else None, label=f"{conv} M: separating")
        a.set_title(f"Fig. 2 replica, x_f = {xf}"); a.set_aspect("equal"); a.set_xlabel("Re θ"); a.set_ylabel("Im θ")
        a.legend(fontsize=7, loc="lower left")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "h16_taylor2023.png"), dpi=130)

    def conv_(o):
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        raise TypeError(type(o))
    pr = [r for r in rows if r["conv"] == "printed"]; co = [r for r in rows if r["conv"] == "correct"]
    summary = dict(
        max_abs_err_printed_exact_vs_fig3=float(max(abs(r["exact"] - r["fig3"]) for r in pr)),
        max_rel_err_printed_exact_vs_fig3=float(max(abs(r["exact"] - r["fig3"]) / r["fig3"] for r in pr)),
        max_abs_err_correct_exact_vs_fig3=float(max(abs(r["exact"] - r["fig3"]) for r in co)),
        peak_printed=float(max(r["exact"] for r in pr)), peak_correct=float(max(r["exact"] for r in co)),
        max_abs_exact_vs_closed=float(max(abs(r["exact"] - r["closed"]) for r in rows)),
        max_abs_ccp_vs_exact=float(max(abs(r["ccp"] - r["exact"]) for r in rows if r["ccp"] is not None)),
        n_ccp_failed=sum(r["ccp"] is None for r in rows),
        runtime_s=time.time() - t0)
    json.dump(dict(rows=rows, sigma_checks=chk, summary=summary,
                   fig2_nonseparating_counts={k: int((~v).sum()) for k, v in fig2.items()}),
              open(os.path.join(OUT, "h16_taylor2023.json"), "w"), indent=2, default=conv_)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
