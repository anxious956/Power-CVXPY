"""A STRUCTURED per-channel measurement-error set, replacing the one box on all 12 components
(REVIEW.md section 10, design follow-up 3).

WHAT WAS WRONG WITH THE BOX
---------------------------
`aux_model` puts an independent +-eps box on each of the 12 real components of the relay measurement
[v1, v2, v0, i1, i2, i0]. That is wrong in three ways at once, and all three point the same way (it is
too pessimistic):

  1. CT and VT errors are NOT the same size. The corrected fault-condition figures
     (q1_instrument.draw_installation_fault, from Kasztenny 2021 section III.A-B) are VT ratio 3-6 %
     with 2-4 deg of phase, CT ratio 5-10 % with 1-3 deg. One eps cannot be both.
  2. They are SYSTEMATIC per installation, not independent per component. One transformer has one
     ratio error, and it multiplies all three sequence components of its own quantity coherently.
     An independent box lets the three sequence components err in opposite directions, which no
     instrument does.
  3. They are MULTIPLICATIVE, so they scale with the measured quantity: a 5 % CT error on a 0.1 pu
     negative-sequence current is 0.005 pu, not eps.
  4. The same unknown error is present in BOTH hypotheses. The separation question is whether one
     observation, taken through one instrument set, can be explained as normal and as faulted. The
     instrument error is the same physical constant in both explanations, so it must be a SHARED
     variable of the pair LP, not two independent draws.

THE SET USED HERE
-----------------
Per instrument (VT, CT) and per case:

  systematic     measured x_k = x_k * (c + a u1 + j b u2) for every sequence component k of that
                 quantity, with (c, a, b) the sound outer box of the multiplicative annular sector
                 {(1+g) e^{j phi} : |g| <= G, |phi| <= Phi}  (wp1_common.sector_outer_box geometry:
                 c = ((1-G) cos Phi + (1+G))/2, a = ((1+G) - (1-G) cos Phi)/2, b = (1+G) sin Phi).
                 Two generators per instrument, shared across its three sequence components AND
                 across the two hypotheses.
  per phase      the part that is not common to the three phases: x_phase_p is scaled by an
                 independent zeta_p, and the result is transformed back to sequence coordinates by
                 BM diag(zeta) AM. This is where the partial cancellation lives: a common-mode zeta
                 is the systematic term above, and the differential part leaks between sequences with
                 the 1/3 weights of the transform. Six generators per instrument, also shared.
  white          a small independent +-eps_white box per component, one draw per hypothesis, for
                 everything not covered above (A/D, quantisation, the fitting residual).

THE CROSS TERM IS NOT DROPPED. The multiplicative error acts on the realised signal c + G u, not on
the centre c. Writing E(c + G u) = E(c) + E(G u), the first part is the generator set above and the
second is the instrument error acting on the source uncertainty. It is not negligible here:
`cross_term_bound` measures it at up to 7 % of the measurement on the widest fault case, so dropping
it would be exactly the kind of quiet linearisation this review exists to catch. Instead it is COVERED:
for every source generator column g_j an extra column (VT/CT relative band) x g_j is added, with its
own free coordinate. Giving it an independent sign is conservative, so the set stays an outer one and
the guarantee stays sound.

    python src/review/tac25_channels.py [--quick]   -> results/review_wp1/tac25_channels.json
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

A120 = np.exp(2j * np.pi / 3)
_AM = np.array([[1, 1, 1], [1, A120 ** 2, A120], [1, A120, A120 ** 2]])      # [s0, s+, s-] -> [a, b, c]
_BM = np.linalg.inv(_AM)

# corrected fault-condition figures: ratio band, phase band (deg), and the share of the band that is
# per-phase rather than common to the three phases (the rest is systematic)
CHANNELS = dict(VT=dict(ratio=0.06, phase_deg=4.0, per_phase_share=1 / 3.0),
                CT=dict(ratio=0.10, phase_deg=3.0, per_phase_share=1 / 3.0))
EPS_WHITE = 0.005


def sector_factor(G, Phi_rad):
    """Sound outer box {c + a u1 + j b u2} of the multiplicative sector {(1+g) e^{j phi}}."""
    lo, hi = 1.0 - G, 1.0 + G
    c = (lo * np.cos(Phi_rad) + hi) / 2.0
    a = (hi - lo * np.cos(Phi_rad)) / 2.0
    b = hi * np.sin(Phi_rad)
    return complex(c), float(a), float(b)


def seq_to_seq_phase_generators(x_seq):
    """Generators of BM diag(zeta) AM x_seq for zeta on each phase independently, as complex 3-vectors.
    x_seq is ordered [s1, s2, s0] here (the model's y layout); the transform matrices are in
    [s0, s1, s2] order, so it is permuted in and out."""
    perm = [2, 0, 1]                      # [s1,s2,s0] -> [s0,s1,s2]
    inv = [1, 2, 0]
    x = np.asarray(x_seq)[perm]
    out = []
    for ph in range(3):
        D = np.zeros((3, 3), complex); D[ph, ph] = 1.0
        g = _BM @ D @ _AM @ x
        out.append(g[inv])
    return out


def channel_generators(y0, spec=None, rho=0.0):
    """Instrument-error generators for one case, as a real 12 x q matrix and the centre shift.

    y0: complex length-6 measurement [v1, v2, v0, i1, i2, i0] at the case centre.
    Returns (dc_real12, E_real12xq, labels)."""
    spec = spec or CHANNELS
    v, i = np.asarray(y0[:3]), np.asarray(y0[3:])
    dc = np.zeros(6, complex)
    cols, labels = [], []
    for name, sig, sl in (("VT", v, slice(0, 3)), ("CT", i, slice(3, 6))):
        s = spec[name]
        share = s["per_phase_share"]
        G_sys = s["ratio"] * (1 - share) * (1 + rho)
        P_sys = np.deg2rad(s["phase_deg"]) * (1 - share) * (1 + rho)
        c, a, b = sector_factor(G_sys, P_sys)
        dcx = np.zeros(6, complex); dcx[sl] = sig * (c - 1.0)
        dc += dcx
        for gen, lab in ((a * sig, f"{name} ratio (systematic)"), (1j * b * sig, f"{name} phase (systematic)")):
            col = np.zeros(6, complex); col[sl] = gen
            cols.append(col); labels.append(lab)
        G_ph = s["ratio"] * share * (1 + rho)
        P_ph = np.deg2rad(s["phase_deg"]) * share * (1 + rho)
        for ph, gph in enumerate(seq_to_seq_phase_generators(sig)):
            for scale, lab in ((G_ph, f"{name} ratio (phase {'abc'[ph]})"), (1j * P_ph, f"{name} phase (phase {'abc'[ph]})")):
                col = np.zeros(6, complex); col[sl] = scale * gph
                cols.append(col); labels.append(lab)
    E = np.stack([realify(c) for c in cols], 1)
    return realify(dc), E, labels


def _worst_rel(spec=None):
    """Largest relative instrument deviation (ratio + phase in radians), used to size the cross term."""
    spec = spec or CHANNELS
    return max(spec["VT"]["ratio"] + np.deg2rad(spec["VT"]["phase_deg"]),
               spec["CT"]["ratio"] + np.deg2rad(spec["CT"]["phase_deg"]))


def cross_term_bound(p, mode, scen, m, mr, spec=None):
    """Size of the neglected (instrument error x source uncertainty) cross term, relative to the
    measurement, for one case."""
    spec = spec or CHANNELS
    c, H, G = affine_case(p, scen, m, mr, mode)
    worst_src = float(np.abs(G).sum(axis=1).max())          # largest single-component source deviation
    worst_rel = max(spec["VT"]["ratio"] + np.deg2rad(spec["VT"]["phase_deg"]),
                    spec["CT"]["ratio"] + np.deg2rad(spec["CT"]["phase_deg"]))
    scale = float(np.abs(c).max())
    return dict(cross_abs=worst_src * worst_rel, measurement_scale=scale,
                cross_rel=float(worst_src * worst_rel / max(scale, 1e-12)))


# --------------------------------------------------------------------------- separation with shared error
def _case_y0(p, scen, m, mr, mode):
    (sL0, gL), (iR0, gR) = source_sets(p, mode)
    return solve(p, scen, sL0, iR0, 0.0, m, mr)


def separated_structured(p, ms, dv, spec=None, eps_white=EPS_WHITE, rho=0.0, limit=None, mode="outer"):
    """True iff every fault case is separated from normal at delta = dv under the structured set with a
    SHARED instrument error. Variables [u_N, u_F, w (shared), nN, nF]."""
    spec = spec or CHANNELS
    d2 = np.array([dv.real, dv.imag])
    yN = _case_y0(p, "N", 0.5, 0.0, mode)
    dcN, EN, _ = channel_generators(yN, spec, rho)
    cN, HN, GN = ms.N
    for f in ms.faults:
        (scen, m, mr) = f[0]
        cF, HF, GF = f[1]
        yF = _case_y0(p, scen, m, mr, mode)
        dcF, EF, _ = channel_generators(yF, spec, rho)
        n = cN.size
        k = GN.shape[1]
        q = EN.shape[1]
        # (cN + dcN + HN d + GN uN + EN w + XN vN + nN) == (cF + dcF + HF d + GF uF + EF w + XF vF + nF),
        # with X the cross term (instrument error acting on the source uncertainty), signed freely
        wr = _worst_rel(spec)
        XN, XF = wr * GN, wr * GF
        Aeq = np.hstack([GN, -GF, EN - EF, XN, -XF, np.eye(n), -np.eye(n)])
        beq = (cF + dcF + HF @ d2) - (cN + dcN + HN @ d2)
        bounds = [(-1, 1)] * (2 * k + q + 2 * k) + [(-eps_white, eps_white)] * (2 * n)
        A_ub = b_ub = None
        if limit is not None:
            pp, mode_l, r_head = limit
            A, b = td.limit_rows(pp, mode_l, k, r_head)          # acts on [u_N, u_F] only
            A_ub = np.hstack([A, np.zeros((A.shape[0], q + 2 * k + 2 * n))])
            b_ub = b
        res = linprog(np.zeros(Aeq.shape[1]), A_ub=A_ub, b_ub=b_ub, A_eq=Aeq, b_eq=beq, bounds=bounds, method="highs")
        if res.status != 2:
            return False
    return True


def min_delta_structured(p, mode="outer", spec=None, rho=0.0, i_max=None, r_step=0.02, n_ang=72, r_max=2.0):
    ms = ModelSet(p, mode=mode)
    radii = np.arange(0.0, r_max + 1e-9, r_step)
    angs = np.linspace(0, 2 * np.pi, n_ang, endpoint=False)
    for r in radii:
        limit = None
        if i_max is not None:
            head = i_max - r
            if not td.limit_feasible(p, mode, head):
                continue
            limit = (p, mode, head)
        for a in (angs if r > 0 else [0.0]):
            dv = r * np.exp(1j * a)
            if separated_structured(p, ms, dv, spec, rho=rho, limit=limit, mode=mode):
                return dict(feasible=True, abs_delta=float(r), angle_deg=float(np.degrees(a)), delta=complex(dv))
    return dict(feasible=False, abs_delta=None, angle_deg=None, delta=None)


def component_halfwidths(p, spec=None, rho=0.0, eps_white=EPS_WHITE, mode="outer"):
    """Per-component half-width of the structured set, beside the scalar box it replaces. This is where
    the two sets differ: a ratio error cannot manufacture negative-sequence voltage out of nothing, so
    the structured set is WIDER than the scalar box on the large components and far narrower on the
    near-zero ones, which are the ones separation turns on."""
    names = ["Re v1", "Re v2", "Re v0", "Re i1", "Re i2", "Re i0",
             "Im v1", "Im v2", "Im v0", "Im i1", "Im i2", "Im i0"]
    out = {}
    for lab, (scen, m, mr) in (("normal", ("N", 0.5, 0.0)), ("AG at 55 %, max R_f", ("ag", 0.55, 1.0))):
        y0 = _case_y0(p, scen, m, mr, mode)
        _, E, _ = channel_generators(y0, spec, rho)
        hw = np.abs(E).sum(axis=1) + eps_white
        out[lab] = {n: float(v) for n, v in zip(names, hw)}
    out["scalar_box_eps"] = float(p.eps)
    return out


def imbalance_scale(spec, kappa):
    """The same channel spec with only the PER-PHASE (imbalance) part scaled by kappa. The systematic
    part is untouched: this isolates the error that leaks between sequence components."""
    out = {}
    for k, v in (spec or CHANNELS).items():
        s0 = v["per_phase_share"]
        f = (1 - s0) + kappa * s0                      # systematic part fixed, per-phase part x kappa
        out[k] = dict(ratio=v["ratio"] * f, phase_deg=v["phase_deg"] * f,
                      per_phase_share=kappa * s0 / f)
    return out


def imbalance_boundary(p, i_max=None, rho=0.0, kappas=(1, 2, 3, 4, 6, 8, 12, 16, 24, 32), r_step=0.04, n_ang=36):
    """How much larger the imbalance part of the instrument error has to be before a signal is needed
    at all, and before the problem becomes infeasible. This is the structured set's version of the
    scalar map's eps axis."""
    ms = ModelSet(p, mode="outer")
    rows = []
    for k in kappas:
        spec = imbalance_scale(CHANNELS, k)
        sep0 = separated_structured(p, ms, 0j, spec, rho=rho,
                                    limit=None if i_max is None else (p, "outer", i_max))
        r = dict(kappa=float(k), separated_at_zero=bool(sep0), abs_delta=0.0 if sep0 else None)
        if not sep0:
            m = min_delta_structured(p, spec=spec, rho=rho, i_max=i_max, r_step=r_step, n_ang=n_ang)
            r["abs_delta"] = m["abs_delta"]
            r["feasible"] = m["feasible"]
        rows.append(r)
    return rows


def equivalent_eps(p_maker, target_delta, i_max, rho, eps_grid=(0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16),
                   r_step=0.02, n_ang=72):
    """The scalar eps whose required |delta| first reaches `target_delta` (so the structured set can be
    put on the old map's axis). Returns the smallest eps whose answer is >= target, or None."""
    for eps in eps_grid:
        p = p_maker(eps)
        ms = ModelSet(p, mode="outer")
        r = td.min_delta(ms, i_max=i_max, limit_inside=i_max is not None, limit_design=False, rho=rho,
                         r_step=r_step, n_ang=n_ang, r_max=2.0)
        if not r["feasible"]:
            return dict(eps=float(eps), relation="infeasible at this eps")
        if target_delta is not None and r["abs_delta"] >= target_delta - 1e-12:
            return dict(eps=float(eps), scalar_delta=r["abs_delta"], relation="first scalar eps at least as hard")
    return dict(eps=None, relation="structured set is easier than every scalar eps on the grid")


def main(quick=False):
    t0 = time.time()
    step, nang = (0.04, 36) if quick else (0.02, 72)
    res = dict(script="tac25_channels", commit=cm.git_commit(), channels=CHANNELS, eps_white=EPS_WHITE,
               r_step=step, n_ang=nang, cells=[])
    p_ref = make_params(0.08)
    res["cross_term"] = {f"{s},{m},{mr}": cross_term_bound(p_ref, "outer", s, m, mr)
                         for s, m, mr in (("N", 0.5, 0.0), ("ag", 0.55, 1.0), ("ab", 0.95, 0.0))}
    _, E, labels = channel_generators(_case_y0(p_ref, "N", 0.5, 0.0, "outer"))
    res["n_generators"] = int(E.shape[1])
    res["generator_labels"] = labels
    res["generator_norms"] = [float(np.abs(E[:, j]).max()) for j in range(E.shape[1])]
    res["component_halfwidths"] = component_halfwidths(p_ref)
    res["imbalance_boundary"] = {f"i_max={im}": imbalance_boundary(p_ref, im) for im in (None, 2.1)}
    for rho in (0.0, 0.1):
        for i_max, lab in ((None, "no limit"), (1.2, "hard 1.2"), (2.1, "robust: pruned at 2.1")):
            r = min_delta_structured(p_ref, rho=rho, i_max=i_max, r_step=step, n_ang=nang)
            eq = equivalent_eps(make_params, r["abs_delta"], i_max, rho, r_step=step, n_ang=nang) if r["feasible"] else None
            cell = dict(rho=rho, limit=lab, i_max=i_max, feasible=r["feasible"], abs_delta=r["abs_delta"],
                        angle_deg=r["angle_deg"], equivalent_scalar_eps=eq)
            res["cells"].append(cell)
            print(f"  rho {rho:.1f} {lab:22s}: structured |delta| = {r['abs_delta']}  "
                  f"(equivalent scalar eps {eq['eps'] if eq else '-'})", flush=True)
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "tac25_channels.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, f"[{res['runtime_s']:.0f}s]")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick)
