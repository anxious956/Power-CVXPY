"""
The TAC25 design (current limit INSIDE the problem, review/tac25_design.py) on the PSCAD two-bus
circuit, and the EMT runs that test it. Same circuit and uncertainty as src/pscad_delta_design.py, but
the design model is the reviewed one: the sound outer source set (H6), a separation margin rho (H14), and
the per-phase limit rule "phase": while delta is injected, only positive-sequence realisations whose three
phase currents |i+ + a^k delta| fit under 1.2 pu occur. That rule describes an inverter that keeps delta
and cuts I1 (the EMT inverter's LIM = 1); the runs check it with that limiter, and normal operation also
with the other one (LIM = 0, I1 and delta scaled together).

    python src/pscad_tac25_design.py      -> results/pscad/tac25_design.json (run list for pscad_twobus_fast.py)
"""
import os, sys, json, itertools
import numpy as np
from scipy.optimize import linprog
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "review"))
from tac25_design import min_delta, phase_rows
from wp1_common import ModelSet, source_sets
from pscad_witness import P
from pscad_delta_design import inverter_settings
from aux_model import solve

RHO, IMAX, MODE = 0.10, 1.2, "outer"
OUT = os.path.join(HERE, "..", "results", "pscad", "tac25_design.json")


def limit_block(k, dv):
    """Rows A u <= b for ONE uncertainty block of k coordinates (rule "phase" at delta = dv)."""
    A, b = phase_rows(P, MODE, k, IMAX, dv)
    return A[0::2, :k], b[0::2]


def closest(ms, f, dv, limited=True):
    """Closest approach of fault set f to the normal set at delta dv: (uN, uF, combined noise). uF is the fault
    realisation's box coordinates (sign already undone: ModelSet.pair stacks [G_N, G_F] against c_F - c_N)."""
    dc, dH, G = ms.pair(f)
    target = dc + dH @ np.array([dv.real, dv.imag])
    n, k2 = G.shape
    k = k2 // 2
    c = np.zeros(k2 + n + 1)
    c[-1] = 1
    A_eq = np.hstack([G, np.eye(n), np.zeros((n, 1))])      # GN uN - GF uF ... sign carried by ms.pair
    A_ub = [np.hstack([np.zeros((n, k2)), np.eye(n), -np.ones((n, 1))]),
            np.hstack([np.zeros((n, k2)), -np.eye(n), -np.ones((n, 1))])]
    b_ub = [np.zeros(n), np.zeros(n)]
    if limited:
        A1, b1 = limit_block(k, dv)
        for blk, sg in ((0, 1.0), (1, -1.0)):             # the fault block's variable is -u_F (ModelSet.pair)
            row = np.zeros((A1.shape[0], k2 + n + 1))
            row[:, blk * k:(blk + 1) * k] = sg * A1
            A_ub.append(row)
            b_ub.append(b1)
    res = linprog(c, A_ub=np.vstack(A_ub), b_ub=np.concatenate(b_ub), A_eq=A_eq, b_eq=target,
                  bounds=[(-1, 1)] * k2 + [(None, None)] * n + [(0, None)], method="highs")
    return res.x[:k], -res.x[k:k2], res.x[-1]


A3 = np.exp(2j * np.pi / 3)


def limiter(i1, d, lim, i_max=IMAX):
    """What the EMT inverter delivers for a request (i1, d): the controller's limiter in pscad_inverter.py.
    Phase k carries i1 a^-k + d a^k. LIM 1: d kept, i1 scaled by the largest s <= 1 that fits every phase
    (unless d alone exceeds the limit); then, as for LIM 0, both scaled by i_max / peak if still over."""
    if lim == 1:
        s = 1.0
        for k in range(3):
            q, r = i1 * A3 ** (-k), d * A3 ** k
            a, b, c = abs(q) ** 2, (q * np.conj(r)).real, abs(r) ** 2 - i_max ** 2
            if c < 0 and a > 1e-12:
                s = min(s, (-b + np.sqrt(b * b - a * c)) / a)
        i1 = max(s, 0.0) * i1
    peak = max(abs(i1 * A3 ** (-k) + d * A3 ** k) for k in range(3))
    sc = min(1.0, i_max / peak)
    return sc * i1, sc * d


def settings_limited(e, i_req, d, lim):
    """ID, IQ, D2ANG such that the inverter, after its limiter, injects the design's delta at its absolute
    angle: the angles are taken against V1 at bus R for the currents actually delivered."""
    i_r, d_r = limiter(i_req, d, lim)
    y = solve(P, "N", e, i_r, d_r)
    v1r = y[0] - P.z1 * y[3]
    rel = np.angle(i_req) - np.angle(v1r)
    return (float(abs(i_req) * np.cos(rel)), float(-abs(i_req) * np.sin(rel)),
            float(np.degrees(np.angle(d) - np.angle(v1r))) if abs(d) else 0.0)


def realisation(u):
    (cL, gL), (cR, gR) = source_sets(P, MODE)
    return cL + gL[0] * u[0] + gL[1] * u[1], cR + gR[0] * u[2] + gR[1] * u[3]


def main():
    ms = ModelSet(P, mode=MODE)
    designs = {}
    for rho in (0.0, RHO):
        r = min_delta(ms, i_max=IMAX, limit_inside=True, limit_design=False, rho=rho, limit_rule="phase")
        designs[rho] = r
        print(f"TAC25 design, rho = {rho}: |delta| = {r['abs_delta']} pu at {r['angle_deg']} deg; delta fits beside every "
              f"modelled i+ only if the limit were {r['injectable_limit']:.3f} pu")
    dt = designs[RHO]["delta"]
    amb0 = [f[0] for f in ms.faults if closest(ms, f, 0.0)[2] <= 2 * ms.eps]
    print(f"outer set, delta = 0: {len(amb0)} of {len(ms.faults)} cases not separated: {amb0}")
    runs = []
    for f in ms.faults:
        scen, m, mr = f[0]
        for tag, d in (("d0", 0.0), ("dt", dt)):
            _, uF, t = closest(ms, f, d)
            e, i = realisation(uF)
            ID, IQ, D2ANG = inverter_settings(e, i, d)
            runs.append(dict(name=f"t_{scen}{int(m * 100)}_r{int(mr * 100)}_{tag}", kind="fault", scen=scen, m=m, mr=mr,
                             rf_ohm=mr * P.rF * 40.0, delta=[float(np.real(d)), float(np.imag(d))], tag=tag,
                             design_ratio=float(t / P.eps), es_pu=float(abs(e)), ph_deg=float(np.degrees(np.angle(e))),
                             idref=ID, iqref=IQ, mode2=2 if abs(d) else 0, d2mag=float(abs(d)), d2ang=D2ANG, lim=1))
    for k, u in enumerate(itertools.product((-1, 1), repeat=4)):
        e, i = realisation(u)
        peak = max(abs(i * np.exp(-2j * np.pi * kk / 3) + dt * np.exp(2j * np.pi * kk / 3)) for kk in range(3))
        base = dict(scen="N", m=0.5, mr=0.0, rf_ohm=0.0, delta=[float(dt.real), float(dt.imag)], corner=list(u),
                    es_pu=float(abs(e)), ph_deg=float(np.degrees(np.angle(e))), mode2=2,
                    d2mag=float(abs(dt)), asked_phase_peak=float(peak))
        s1 = dict(zip(("idref", "iqref", "d2ang"), settings_limited(e, i, dt, 1)))
        s0 = dict(zip(("idref", "iqref", "d2ang"), settings_limited(e, i, dt, 0)))
        runs.append(dict(base, **s1, name=f"t_N_c{k:02d}_lim1", kind="normal", tag="lim1", lim=1))
        runs.append(dict(base, **s0, name=f"t_N_c{k:02d}_lim0", kind="normal", tag="lim0", lim=0))
        for m in (0.75, 0.95):
            runs.append(dict(base, **s1, name=f"t_ag{int(m * 100)}_r100_c{k:02d}", kind="fault", scen="ag", m=m, mr=1.0,
                             rf_ohm=40.0, tag="corner", design_ratio=None, lim=1))
    n_over = sum(1 for r in runs if r.get("tag") == "lim1" and r["asked_phase_peak"] > IMAX)
    print(f"box corners whose requested phase peak with delta exceeds {IMAX} pu: {n_over} of 16")
    json.dump(dict(rho=RHO, eps=P.eps, mode=MODE, limit_rule="phase", i_max=IMAX,
                   designs={str(k): {kk: (str(vv) if isinstance(vv, complex) else vv) for kk, vv in v.items()} for k, v in designs.items()},
                   delta=[float(dt.real), float(dt.imag)], unseparated_at_0=[list(x) for x in amb0], runs=runs),
              open(OUT, "w"), indent=1)
    print(f"{len(runs)} runs -> results/pscad/tac25_design.json")


if __name__ == "__main__":
    main()
