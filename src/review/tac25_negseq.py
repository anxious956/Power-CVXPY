"""Closing the inverter's negative-sequence path, so the IBR-share axis means something
(REVIEW.md section 10, design follow-up 4; results/DESIGN.md section 4.3).

THE DEFECT
----------
`aux_model.Params.ibr_neg_z = 1e6` makes the inverter an OPEN CIRCUIT in the negative sequence. The
auxiliary signal lives entirely in the negative sequence, so this is not a small modelling choice: it
is the one path the whole method uses. With it open, an IBR at the relay end pins the measurement so
tightly that separation becomes free (DESIGN.md section 4.2, "IBR: 0"), which is the opposite of the
project's premise and is an artefact.

WHAT REPLACES IT
----------------
An IEEE 2800-style negative-sequence current response: the inverter injects a negative-sequence
current proportional to the negative-sequence voltage at its terminals, i2 = -K2 * v2 in pu, i.e. a
finite shunt admittance of magnitude K2 at the inverter bus. Two things are swept:

  K2     the gain. IEEE 2800 requires the capability and leaves the gain settable; grid codes in the
         same family ask for roughly 2-6 pu/pu. Swept over (2, 4, 6), plus the old open circuit as the
         reference point. THE EXACT CLAUSE NUMBER AND GAIN RANGE ARE NOT RE-VERIFIED AGAINST THE
         STANDARD TEXT here; they are taken from the reading notes, and the sweep is wide enough that
         the conclusion does not turn on the exact figure.

  angle  the angle of that admittance, which is the real finding of papers/notes/SYNTHESIS.md section
         2: the current limiter sets it, and the measured values are -0.5 deg (circular limiter),
         +36.2 deg (priority-based) and -51.6 deg (instantaneous). None is inductive, against the
         -90 deg a directional element assumes. This is the uncertainty dimension the open circuit
         was hiding.

HOW THE ANGLE IS TREATED. It enters the system matrix, not the right-hand side, so it is NOT a
zonotope generator and cannot be folded into the affine model. It is handled as a finite set: one
model per angle, and separation is required for every admissible combination. Two readings are
reported because they differ:

  matched   the limiter type is a fixed property of the installation, so the normal and fault models
            carry the SAME angle. Physically right.
  crossed   separation required between every normal angle and every fault angle. Conservative; the
            number to quote if the limiter type may differ between the pre-fault and fault regimes
            (which is what SYNTHESIS section 2 says actually happens when the limiter engages).

    python src/review/tac25_negseq.py [--quick]   -> results/review_wp1/tac25_negseq.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from scipy.optimize import linprog
import aux_model as am
from wp1_common import ModelSet, source_sets
import tac25_design as td
from tac25_map import make_params, sir_of
from review import common as cm

OUT = os.path.join(cm.ROOT, "results", "review_wp1")

LIMITER_ANGLES_DEG = {"circular": -0.5, "priority-based": 36.2, "instantaneous": -51.6}
K2_GRID = (2.0, 4.0, 6.0)
OPEN_Z = 1e6


def neg_z(k2, angle_deg):
    """Negative-sequence shunt impedance at the inverter bus: |z| = 1/K2 at the limiter's angle."""
    return complex((1.0 / k2) * np.exp(1j * np.deg2rad(angle_deg)))


def params_with_negseq(eps, local, k2, angle_deg, strength=1.0, rf=1.0):
    p = make_params(eps, strength=strength, local=local, rf=rf)
    p.ibr_neg_z = OPEN_Z if k2 is None else neg_z(k2, angle_deg)
    p.name = f"{p.name}_K{k2}_{angle_deg}"
    return p


def separated_multi(models, dv, eps_eff, limit=None, crossed=False):
    """True iff every (normal model, fault model) combination required by `crossed` is separated at dv.

    `models` is a list of ModelSet, one per admissible angle. matched: N and F share the angle.
    crossed: every N angle against every F angle."""
    d2 = np.array([dv.real, dv.imag])
    for a, msN in enumerate(models):
        cN, HN, GN = msN.N
        for b, msF in enumerate(models):
            if not crossed and a != b:
                continue
            for f in msF.faults:
                cF, HF, GF = f[1]
                n = cN.size
                G = np.hstack([GN, GF])
                Aeq = np.hstack([G, np.eye(n)])
                beq = (cF + HF @ d2) - (cN + HN @ d2)
                bounds = [(-1, 1)] * G.shape[1] + [(-2 * eps_eff, 2 * eps_eff)] * n
                A_ub = b_ub = None
                if limit is not None:
                    p, mode, r_head = limit
                    A, bb = td.limit_rows(p, mode, G.shape[1] // 2, r_head)
                    A_ub = np.hstack([A, np.zeros((A.shape[0], n))])
                    b_ub = bb
                res = linprog(np.zeros(Aeq.shape[1]), A_ub=A_ub, b_ub=b_ub, A_eq=Aeq, b_eq=beq,
                              bounds=bounds, method="highs")
                if res.status != 2:
                    return False
    return True


def min_delta_multi(models, p0, eps, rho=0.0, i_max=None, crossed=False, r_step=0.02, n_ang=72, r_max=2.0,
                    mode="outer"):
    eps_eff = eps * (1 + rho)
    radii = np.arange(0.0, r_max + 1e-9, r_step)
    angs = np.linspace(0, 2 * np.pi, n_ang, endpoint=False)
    for r in radii:
        limit = None
        if i_max is not None:
            head = i_max - r
            if not td.limit_feasible(p0, mode, head):
                continue
            limit = (p0, mode, head)
        for a in (angs if r > 0 else [0.0]):
            dv = r * np.exp(1j * a)
            if separated_multi(models, dv, eps_eff, limit, crossed):
                return dict(feasible=True, abs_delta=float(r), angle_deg=float(np.degrees(a)), delta=complex(dv))
    return dict(feasible=False, abs_delta=None, angle_deg=None, delta=None)


def negseq_visibility(p, mode="outer"):
    """How much negative-sequence current the injected delta actually drives into the relay, and how
    much negative-sequence voltage appears: the quantity the open circuit was zeroing."""
    (sL0, gL), (iR0, gR) = source_sets(p, mode)
    y0 = am.solve(p, "N", sL0, iR0, 0.0, 0.5, 0.0)
    y1 = am.solve(p, "N", sL0, iR0, 1.0, 0.5, 0.0)
    d = y1 - y0
    return dict(dv2_per_unit_delta=float(abs(d[1])), di2_per_unit_delta=float(abs(d[4])),
                v2_normal=float(abs(y0[1])), i2_normal=float(abs(y0[4])))


def main(quick=False, eps=0.08, i_max=2.1, rho=0.0):
    t0 = time.time()
    step, nang = (0.04, 36) if quick else (0.02, 72)
    res = dict(script="tac25_negseq", commit=cm.git_commit(), eps=eps, i_max=i_max, rho=rho,
               limiter_angles_deg=LIMITER_ANGLES_DEG, k2_grid=list(K2_GRID), r_step=step, n_ang=nang,
               standard_caveat="IEEE 2800 clause numbers and the K2 range are from the reading notes, "
                               "not re-verified against the standard text; the sweep is wide enough that "
                               "the conclusion does not turn on the exact figure.",
               cells=[])
    for local in ("SG", "IBR"):
        for k2 in (None,) + K2_GRID:
            models, p0 = [], None
            for lab, ang in LIMITER_ANGLES_DEG.items():
                p = params_with_negseq(eps, local, k2, ang)
                p0 = p0 or p
                models.append(ModelSet(p, mode="outer"))
                if k2 is None:
                    break                                   # the open circuit has no angle
            vis = negseq_visibility(p0)
            row = dict(local=local, k2=k2, negseq_path=("open (1e6)" if k2 is None else f"|z2| = {1/k2:.3f} pu"),
                       visibility=vis)
            for crossed in ((False,) if k2 is None else (False, True)):
                r = min_delta_multi(models, p0, eps, rho=rho, i_max=i_max, crossed=crossed,
                                    r_step=step, n_ang=nang)
                row["crossed" if crossed else "matched"] = dict(feasible=r["feasible"], abs_delta=r["abs_delta"],
                                                                angle_deg=r["angle_deg"])
            res["cells"].append(row)
            print(f"  local {local:3s} K2 {str(k2):4s}: dv2/delta {vis['dv2_per_unit_delta']:.4f}  "
                  f"matched |delta| {row['matched']['abs_delta']}  "
                  f"crossed {row.get('crossed', {}).get('abs_delta')}", flush=True)
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "tac25_negseq.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, f"[{res['runtime_s']:.0f}s]")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--eps", type=float, default=0.08)
    ap.add_argument("--i-max", type=float, default=2.1)
    a = ap.parse_args()
    main(a.quick, a.eps, a.i_max)
