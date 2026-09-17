# Note for Prof. Taylor: the matrix form in the 2023 appendix

**Status: draft, not sent.**

Using the 2023 paper (arXiv 2311.10880) as a correctness gate for our CVXPY reimplementation, we
found Fig. 3 reproduces only with the real matrix form printed in the appendix, not the standard
one.

Setup as printed: z⁻ = z⁺ = 30 + j35, z_f = 26 + j·x_f, x_f = 12…58 step 2, H = Q = I, ‖λ_k‖₂ ≤ 1.
We solved min‖θ‖ exactly (SOCPs over 360 directions, CVXPY + Clarabel) and in closed form; they
agree to 1.8 × 10⁻⁸. Both closed forms instance |θ|min = 2/σ_max(M⁻ − M_f):

- printed M = [[r, −x], [r, x]] → √2 / max(|Δr|, |Δx|)
- standard M = [[r, −x], [x, r]] → 2 / |z_f − z⁻|

Digitising Fig. 3 (±0.003) gives 0.160, 0.287, 0.357, 0.356, 0.356, 0.357, 0.287 at
x_f = 26, 30, 32, 34, 36, 38, 40. The printed form returns 0.157, 0.283, 0.354, 0.354, 0.354,
0.354, 0.283 — max absolute error **0.0065**, reproducing the flat plateau at 1/(2√2) = 0.3536
for x_f ≈ 31–39 that is the figure's distinctive feature. The standard form peaks at **0.4851**;
max absolute error **0.129**. Fig. 2 agrees: the printed form gives the published ellipse and
vertical strip, the standard form a disk.

[[r, −x], [r, x]] is not a real representation of multiplication by r + jx — singular at x = 0,
not a rotation–scaling — so we suspect a typesetting slip carried into the figures.

Two questions: is the printed form the one used for Figs. 2 and 3, and are the CCP parameters
(γ₀, ζ, γ_max, starts, stopping rule) recoverable? Ours lands 0.004 above the exact optimum,
consistent with the published values, but those settings were guesses.

Script: `src/review/wp1_taylor2023.py` → `results/review_wp1/h16_taylor2023.json`. Detail in
`review/WP1_REPORT.md` §H16.
