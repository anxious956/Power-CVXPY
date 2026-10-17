"""
The main two-frame design configuration for the step-3 detectors (agreed with the reviewer, 16 Oct 2026), each
parameter labelled as measured or chosen:

  phi_ref   = k sigma_white / (sqrt(n_mem) min|V1_L|)   k = 4, sigma_white = 0.01 pu: CHOSEN (the data generator's
              random noise model, docs/STEP3.md); n_mem = 3 cycles: the relay memory's window (seq_traj). The
              guarantee is then "worst case over the sources, k-sigma over random noise"; the systematic VT phase
              error is in the violation matrix, not here
  model_err = 0.1 eps     MEASURED: EMT with delta injected in the inverter's own frame (src/frames_emt_check.py,
              168 runs, |delta| 0.9 / 1.0 / 1.05 / 1.14 pu at 225 deg): relay points outside their own set (model_err 0)
              by at most 0.073 eps for windows ending 2-3 cycles after inception. (The earlier 0.25 eps was the
              distance to the settled point, which the frame symbols already cover; with it no delta separated.)
  r_max     = 1.05 pu     MEASURED: the EMT inverter settles at 1.0 and 1.05 pu on every case; at 1.14 pu it does
              not settle on the bolted ab faults (error up to 18.9 eps). Checked at 225 deg only: delta* elsewhere
              needs its own EMT check
  drift     = 3 deg       MEASURED: EMT I1 turn beyond the fixed point <= 2.2 deg in that window
  window    = [2, 3] cycles after inception   CHOSEN: the guarantee cannot hold inside one cycle on this model
              (model error 1.33 eps, frame turn 28.7 deg at 1 cycle)
  rho       = 0.1         CHOSEN

Reports delta*, the separating angle window (1 deg steps), dense-tier separation at factors 1.0 / 1.1 / 1.25,
adversarial containment at delta*, the separation re-check on continuous (m, R_f) between the design cases, and
the inverter current left.

    python src/frames_main.py                      -> results/network/frames_main.json
    python src/frames_main.py 1.05 225 0.05        -> results/network/frames_main_fixed.json

The second form skips the search and checks a given design point (|delta| pu, angle deg, rho): at rho 0.1 no delta
up to 1.05 pu separates (results/network/frames_main_err025.json is the run with the earlier 0.25 eps box); at
1.05 pu, 225 deg every case separates with rho up to 0.05 (bound by L1 15 % A-G at full R_f).
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import three_bus
from network_delta_test import CASES

EPS, K, SIGMA, N_MEM = 0.08, 4.0, 0.01, 3
MODEL_ERR, DRIFT, RHO, R_MAX = 0.1 * EPS, 3.0, 0.1, 1.05
OUT = os.path.join(HERE, "..", "results", "network", "frames_main.json")


def main(fixed=None):
    rho = RHO
    net = three_bus()
    t0 = time.time()
    probe = fr.FrameModel(net, CASES[:1], n_samples=400, face_pts=5, seed=2)
    v1min = float(np.min(np.abs(probe.measure(np.vstack(probe.samples), 0j, None)[:, 0])))
    phi = K * SIGMA / (np.sqrt(N_MEM) * v1min)
    cfg = dict(phi_ref=float(phi), k=K, sigma_white=SIGMA, n_mem=N_MEM, min_V1L=v1min, model_err=MODEL_ERR, drift_deg=DRIFT,
               rho=rho, r_max=R_MAX, window_cycles=[2, 3],
               labels=dict(k="chosen", sigma_white="chosen", n_mem="relay design", model_err="measured (EMT, delta injected)", r_max="measured (EMT settles)",
                           drift_deg="measured", window_cycles="chosen", rho="chosen"))
    print(f"phi_ref = {phi:.4f} rad", flush=True)
    kw = dict(factor=1.1, drift_deg=DRIFT, ref_phi=phi, model_err=MODEL_ERR)
    search = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, **kw)
    out = OUT
    if fixed is not None:
        mag, ang, rho = fixed
        cfg["rho"] = rho
        d0 = mag * np.exp(1j * np.radians(ang))
        sep = fr.separated(search, d0, rho)
        r = dict(feasible=bool(sep), d_cmd=d0 if sep else None, abs_delta=mag, angle_deg=ang, fixed=True,
                 unseparated_at_0=fr.unseparated(search, 0j, rho))
        out = OUT.replace(".json", "_fixed.json")
    res = dict(config=cfg, abs_delta=r["abs_delta"], angle_deg=r["angle_deg"], unseparated_at_0=[list(c) for c in r.get("unseparated_at_0", [])],
               inadmissible=r.get("inadmissible"), fixed=bool(fixed), separated_search_tier=r["feasible"])
    print(f"delta* = {r['abs_delta']} at {r['angle_deg']} deg; unseparated at 0: {len(res['unseparated_at_0'])}  [{time.time() - t0:.0f} s]", flush=True)
    if not r["feasible"]:
        json.dump(res, open(out, "w"), indent=1)
        return
    d = r["d_cmd"]
    res["window_deg"] = fr.window(search, r["abs_delta"], rho, center_deg=r["angle_deg"], half_width_deg=25)
    print(f"window at delta*: {res['window_deg']}  [{time.time() - t0:.0f} s]", flush=True)
    res["dense_factor_check"] = {}
    for f in (1.0, 1.1, 1.25):
        dense = fr.FrameModel(net, CASES, n_samples=400, face_pts=5, seed=2, **dict(kw, factor=f))
        res["dense_factor_check"][str(f)] = bool(fr.separated(dense, d, rho))
    print(f"dense factors: {res['dense_factor_check']}  [{time.time() - t0:.0f} s]", flush=True)
    dense = fr.FrameModel(net, CASES, n_samples=400, face_pts=5, seed=2, **kw)
    worst = fr.containment_adversarial(dense, d, n_fresh=300, face_pts=7, n_local=40, seed=9)
    res["containment_at_dstar_pu"] = float(max(worst.values()))
    res["scenario_bound"] = float(fr.scenario_bound(dense.n, 9))
    # continuous (m, R_f) between the design cases (review of PR #44, point 3)
    cont = [(ln, float(m), s, float(mr)) for ln, ms in (("L1", np.arange(0.05, 0.951, 0.05)), ("L2", np.arange(0.05, 0.951, 0.05)))
            for m in ms for s in ("ag", "ab") for mr in np.arange(0.0, 1.0001, 0.125)]
    cfm = fr.FrameModel(net, cont, n_samples=150, face_pts=3, seed=4, **kw)
    unsep = fr.unseparated(cfm, d, rho)
    res["continuous_check"] = dict(n_cases=len(cont), unseparated=[list(c) for c in unsep])
    print(f"continuous check: {len(unsep)} of {len(cont)} unseparated  [{time.time() - t0:.0f} s]", flush=True)
    S = np.vstack(search.samples)
    e, ic = search.sources(S)
    _, _, u = search.normal_state(S, d)
    i1, _ = fr.limiter_vec(ic * u, d * u, search.i_max, 1)
    res["inverter_current_left"] = [float(np.abs(i1).min()), float(np.median(np.abs(i1))), float(np.abs(i1).max())]
    res["inverter_current_asked"] = [float(np.abs(ic).min()), float(np.abs(ic).max())]
    res["seconds"] = time.time() - t0
    json.dump(res, open(out, "w"), indent=1, default=str)
    print(f"inverter current left {res['inverter_current_left']}; -> {os.path.relpath(out)}", flush=True)


if __name__ == "__main__":
    main(tuple(float(x) for x in sys.argv[1:4]) if len(sys.argv) > 3 else None)
