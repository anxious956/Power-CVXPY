"""
Toy replication of the auxiliary-signal design in
  J. A. Taylor, A. D. Dominguez-Garcia, "Geometry of Distance Protection",
  arXiv:2510.04379, Section VI (VI-B design, VI-D1 grid search).

Usage:  python aux_signal_toy.py [preset]      presets in aux_model.PRESETS

Part 1: grid search in the complex delta-plane for separating auxiliary signals (paper Fig. 5).
Part 2: Farkas-dual optimization  min ||delta||^2  s.t. dual systems feasible,
        alternating scheme (paper: ADMM), convex step in CVXPY + Clarabel (as in the paper).
Part 3: apparent-impedance clouds with delta = 0 and delta = optimum.
"""
import sys, os, json, time
import numpy as np
import cvxpy as cp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from aux_model import Params, Problem, PRESETS, solve, source_generators

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
os.makedirs(OUT, exist_ok=True)

preset = sys.argv[1] if len(sys.argv) > 1 else "easy"
p = PRESETS[preset]
rng = np.random.default_rng(0)
t0 = time.time()
P = Problem(p)
print(f"[{preset}] models: 1 normal + {len(P.faults)} fault cases ({time.time()-t0:.1f}s)")

# ---------------------------------------------------- Part 1: grid search (Fig. 5 style)
t0 = time.time()
lim, step = 0.8, 0.05
ax_ = np.arange(-lim, lim + 1e-9, step)
sep_ag = np.zeros((ax_.size, ax_.size), bool); sep_ab = np.zeros_like(sep_ag)
for i, re in enumerate(ax_):
    for j, im in enumerate(ax_):
        d = re + 1j*im
        sep_ag[j, i] = P.separates_all(d, ("ag",))
        sep_ab[j, i] = P.separates_all(d, ("ab",))
sep_all = sep_ag & sep_ab
print(f"grid search done ({time.time()-t0:.1f}s)")

n0 = P.unseparated(0.0)
best = None
for i, re in enumerate(ax_):
    for j, im in enumerate(ax_):
        if sep_all[j, i]:
            d = re + 1j*im
            if best is None or abs(d) < abs(best):
                best = d
print(f"delta = 0: {len(n0)} of {len(P.faults)} fault cases NOT separated from normal")
if n0:
    print("   unseparated at delta=0:", n0)
print(f"smallest separating delta on grid: {best}  |delta| = {None if best is None else round(abs(best),3)}")

# -------------------------------- Part 2: Farkas-dual alternating optimization (CVXPY)
# N and F(m,mr) separated  <=>  cF(d)-cN(d) not in zonotope Z = {GN uN - GF uF + nN - nF}
# Farkas / support function: exists lam:  lam.(cF-cN) > h_Z(lam) = ||GN^T lam||_1 + ||GF^T lam||_1 + 2 eps ||lam||_1
# Bilinear in (lam, d). Alternate: (i) fix d -> best lam per pair (LP); (ii) fix lam -> min ||d||^2 (QP).
def best_lambda(cdiff, GN, GF, eps):
    lam = cp.Variable(cdiff.size)
    slack = lam @ cdiff - cp.norm1(GN.T @ lam) - cp.norm1(GF.T @ lam) - 2*eps*cp.norm1(lam)
    cp.Problem(cp.Maximize(slack), [cp.norm_inf(lam) <= 1]).solve(solver=cp.CLARABEL)
    return lam.value

tau = 1e-3
if best is None:
    print(f"NO separating delta within |delta| <= {lim:.1f} pu on this grid: at this noise/uncertainty level the "
          f"signal cannot make every fault unambiguous. Reduce eps or source uncertainty, or enlarge the grid (lim).")
d_var = np.array([best.real, best.imag]) if best is not None else np.array([0.0, 0.4])
hist = []
for it in range(15 if best is not None else 0):
    lams = [best_lambda((f["c"] + f["H"]@d_var) - (P.cN + P.HN@d_var), P.GN, f["G"], p.eps) for f in P.faults]
    d = cp.Variable(2); cons = []
    for f, lam in zip(P.faults, lams):
        hz = np.abs(P.GN.T@lam).sum() + np.abs(f["G"].T@lam).sum() + 2*p.eps*np.abs(lam).sum()
        cons.append(lam @ ((f["c"]-P.cN) + (f["H"]-P.HN)@d) >= hz + tau)
    prob = cp.Problem(cp.Minimize(cp.sum_squares(d)), cons)
    prob.solve(solver=cp.CLARABEL)
    if d.value is None:
        print("  QP step infeasible at iteration", it); break
    hist.append(float(np.linalg.norm(d.value)))
    if np.linalg.norm(d.value - d_var) < 1e-5:
        d_var = d.value; break
    d_var = d.value
d_opt = complex(d_var[0], d_var[1])
ok = P.separates_all(d_opt) if best is not None else False
if best is not None:
    print(f"CVXPY alternating optimum: delta = {d_opt:.4f}  |delta| = {abs(d_opt):.4f}  verified separating: {ok}  "
          f"iters: {len(hist)}  history: {[round(h,3) for h in hist]}")
else:
    # coarse probe beyond the grid so the user learns how large a signal would be needed
    for mag in (1.0, 1.5, 2.0, 3.0):
        n = min(len(P.unseparated(mag*np.exp(1j*np.deg2rad(a)))) for a in range(0, 360, 15))
        print(f"   probe |delta| = {mag:.1f} pu: best case leaves {n} fault cases ambiguous"
              + ("   <- separates all" if n == 0 else ""))
        if n == 0:
            break
    print("   note: an inverter is typically limited to about 1.1 to 1.2 pu total current, so a signature above ~1 pu is not physically available.")

# ------------------------------------------- Part 3: Farkas-certificate projections
# Separation lives in the 12-dim measurement space, so we visualize it the way the
# lemma does: project both sets onto the dual direction lambda. Overlap at delta=0,
# a gap of at least tau at the optimum.
def samples(f, d, n=400):
    """Sampled measurements y (real 12) for fault case f (or None for normal) at delta d."""
    dv = np.array([np.real(d), np.imag(d)])
    c, G = (P.cN + P.HN @ dv, P.GN) if f is None else (f["c"] + f["H"] @ dv, f["G"])
    U = rng.uniform(-1, 1, (n, G.shape[1])); Nn = rng.uniform(-p.eps, p.eps, (n, c.size))
    return c + U @ G.T + Nn

hard = [f for f in P.faults if (f["scen"], f["m"], f["mr"]) in n0] or P.faults[:5]
fig, axs = plt.subplots(1, 3, figsize=(16, 5), gridspec_kw=dict(width_ratios=[1.15, 1, 1]))
RE, IM = np.meshgrid(ax_, ax_)
axs[0].scatter(RE[sep_ag], IM[sep_ag], s=14, marker="o", alpha=.5, label="separates (N, ag)")
axs[0].scatter(RE[sep_ab], IM[sep_ab], s=14, marker="v", alpha=.5, label="separates (N, ab)")
axs[0].scatter(RE[sep_all], IM[sep_all], s=28, marker="+", color="k", label="separates both")
if best is not None:
    axs[0].plot(best.real, best.imag, "r*", ms=14, label=f"smallest on grid |δ|={abs(best):.2f}")
if best is not None:
    axs[0].plot(d_opt.real, d_opt.imag, "gs", ms=9, label=f"CVXPY optimum |δ|={abs(d_opt):.2f}")
else:
    axs[0].text(0, lim*0.9, f"no separating δ within |δ| ≤ {lim:.1f} pu", ha="center", fontsize=9, color="red")
axs[0].plot(0, 0, "kx", ms=10, label=f"δ=0: {len(n0)}/{len(P.faults)} cases ambiguous")
axs[0].set_xlabel("Re(δ)  [pu negative-seq current]"); axs[0].set_ylabel("Im(δ)")
axs[0].set_title(f"Separating auxiliary signals, preset '{preset}'"); axs[0].legend(fontsize=7); axs[0].grid(alpha=.3)
axs[0].set_aspect("equal")
def interval(c, G, lam):
    """Exact projection of zonotope {c + G u + n} onto lam (support function, closed form)."""
    h = np.abs(G.T @ lam).sum() + p.eps * np.abs(lam).sum()
    return lam @ c - h, lam @ c + h

for ax, dd, ttl in ((axs[1], 0.0, "δ = 0"), (axs[2], d_opt, f"δ = optimum, |δ| = {abs(d_opt):.2f} pu")):
    dv = np.array([np.real(dd), np.imag(dd)])
    cNd = P.cN + P.HN @ dv
    yN = samples(None, dd)
    for k, f in enumerate(hard):
        cFd = f["c"] + f["H"] @ dv
        lam = best_lambda(cFd - cNd, P.GN, f["G"], p.eps)
        lam = lam / (np.linalg.norm(lam) + 1e-12)
        loN, hiN = interval(cNd, P.GN, lam); loF, hiF = interval(cFd, f["G"], lam)
        # exact intervals as bars, random samples faded behind them
        ax.scatter(yN @ lam, np.full(yN.shape[0], k) - 0.18, s=4, color="tab:blue", alpha=.15)
        ax.scatter(samples(f, dd) @ lam, np.full(400, k) + 0.18, s=4, color="tab:orange", alpha=.15)
        ax.plot([loN, hiN], [k - 0.18]*2, color="tab:blue", lw=6, solid_capstyle="butt")
        ax.plot([loF, hiF], [k + 0.18]*2, color="tab:orange", lw=6, solid_capstyle="butt")
        gap = loF - hiN if loF > hiN else (loN - hiF if loN > hiF else -min(hiN, hiF) + max(loN, loF))
        ax.text(min(loN, loF), k + 0.34, f"{f['scen']}  m={f['m']}  Rf={f['mr']*p.rF:.2f} pu   "
                + (f"gap {gap:+.3f}" if gap > 0 else f"OVERLAP {gap:.3f}"), fontsize=7, va="bottom")
    ax.plot([], [], color="tab:blue", lw=6, label="normal (exact interval)")
    ax.plot([], [], color="tab:orange", lw=6, label="fault (exact interval)")
    ax.set_yticks([]); ax.set_ylim(-0.6, len(hard) - 0.2)
    ax.set_xlabel("projection onto Farkas direction  λᵀy"); ax.legend(fontsize=7, loc="lower right")
    ax.set_title(f"Hardest fault cases vs normal, {ttl}"); ax.grid(alpha=.3, axis="x")
plt.tight_layout()
png = os.path.join(OUT, f"aux_signal_toy_{preset}.png"); plt.savefig(png, dpi=140)
json.dump(dict(preset=preset, unseparated_at_zero=n0,
               grid_best=None if best is None else [best.real, best.imag, abs(best)],
               cvxpy_opt=[d_opt.real, d_opt.imag, abs(d_opt)], verified=bool(ok), history=hist,
               eps=p.eps, rF=p.rF, local=p.local, gen_i=p.gen_i),
          open(os.path.join(OUT, f"aux_signal_toy_{preset}.json"), "w"), indent=2)
print("saved", os.path.relpath(png))
