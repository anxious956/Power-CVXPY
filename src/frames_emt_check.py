"""
The two-frame model (src/frames.py) against EMT with the signal injected at the sizes the frames design asks for
(|delta| 0.9 and 1.14 pu at 225 deg, results/network/frames_design.json). The model error box of the main
configuration (0.25 eps, src/frames_main.py) was measured on runs with |delta| <= 0.9 pu built for the absolute-frame
design; this measures it on V1-referenced settings at the frames design's own delta.

  spec     for each delta: every design case once, at a random point of the source box (seeded), and 8 normal
           runs; the inverter gets its settings in its own frame, as the frame model has them (ID - jIQ = I1
           command, D2MAG / D2ANG = delta command, both relative to its measured V1)
  analyse  in the relay's frame (pre-fault V1 at the relay): for decision windows ending 2 to 3 cycles after
           inception, (a) |EMT - settled frame model| per real component, and (b) the distance from the EMT point
           to its own case's set with model_err = 0 (the box the model error actually needs), both in eps

  between  |delta| 1.0 and 1.05 pu at the same angle, for the phase-to-phase cases only (at 1.14 pu the EMT inverter
           does not settle on the bolted ab faults) and 4 normal runs, at the same source points as the 1.14 pu runs,
           to find the largest |delta| at which the EMT settles

    python src/frames_emt_check.py spec          -> results/network/frames_emt_specs.json
    python src/frames_emt_check.py between       -> results/network/frames_emt_specs2.json
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/network/frames_emt_specs.json  (and specs2)
    python src/frames_emt_check.py analyse       -> results/network/frames_emt_check.json  (both spec files)
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import make_spec, three_bus, WORK
from pscad_network_check import relay_y, read_case
from network_delta_test import CASES, tag

OUT = os.path.join(HERE, "..", "results", "network")
SPECS = os.path.join(OUT, "frames_emt_specs.json")
SPECS2 = os.path.join(OUT, "frames_emt_specs2.json")
DELTAS = {"d090": 0.90 * np.exp(1j * np.radians(225)), "d114": 1.14 * np.exp(1j * np.radians(225))}
BETWEEN = {"d100": 1.00 * np.exp(1j * np.radians(225)), "d105": 1.05 * np.exp(1j * np.radians(225))}
N_NORMAL, T_FAULT, T_PRE = 8, 0.30, 0.25
T_DEC = T_FAULT + np.arange(2.0, 3.0001, 0.25) / 60.0        # decision windows ending 2, 2.25, ..., 3 cycles in
SEED = 11


def _settings(i_cmd, d_cmd):
    return {"I": dict(ID=float(i_cmd.real), IQ=float(-i_cmd.imag), MODE2=2.0 if abs(d_cmd) else 0.0,
                      D2MAG=float(abs(d_cmd)), D2ANG=float(np.degrees(np.angle(d_cmd))) if abs(d_cmd) else 0.0)}


def make():
    net = three_bus()
    fm = fr.FrameModel(net, CASES[:1], n_samples=10, face_pts=2, seed=0)
    rng = np.random.default_rng(SEED)
    specs = []
    for dt, d in DELTAS.items():
        runs = [(c, k) for k, c in enumerate(CASES)] + [(None, k) for k in range(N_NORMAL)]
        S = rng.uniform(-1, 1, (len(runs), 4))
        e, ic = fm.sources(S)
        for (case, k), s, ek, ik in zip(runs, S, e, ic):
            fault = None if case is None else (case[0], case[1], case[2], case[3] * net.rF)
            name = f"fe_{dt}_" + ("N%02d" % k if case is None else tag(case))
            sp = make_spec(name, net, fault, {"G": ek}, {}, 1)
            sp["settings"] = _settings(ik, d)
            sp.update(kind="normal" if case is None else "fault", case=None if case is None else list(case),
                      S=[float(x) for x in s], d_cmd=[d.real, d.imag], dtag=dt)
            specs.append(sp)
    json.dump(specs, open(SPECS, "w"), indent=1)
    print(f"{len(specs)} runs -> {os.path.relpath(SPECS)}")


def between():
    net = three_bus()
    fm = fr.FrameModel(net, CASES[:1], n_samples=10, face_pts=2, seed=0)
    base = [sp for sp in json.load(open(SPECS)) if sp["dtag"] == "d114" and
            (sp["kind"] == "normal" and int(sp["name"][-2:]) < 4 or sp["kind"] == "fault" and sp["case"][2] == "ab")]
    specs = []
    for dt, d in BETWEEN.items():
        for b in base:
            S = np.array([b["S"]])
            e, ic = fm.sources(S)
            case = b["case"]
            fault = None if case is None else (case[0], case[1], case[2], case[3] * net.rF)
            name = b["name"].replace("d114", dt)
            sp = make_spec(name, net, fault, {"G": e[0]}, {}, 1)
            sp["settings"] = _settings(ic[0], d)
            sp.update(kind=b["kind"], case=case, S=b["S"], d_cmd=[d.real, d.imag], dtag=dt)
            specs.append(sp)
    json.dump(specs, open(SPECS2, "w"), indent=1)
    print(f"{len(specs)} runs -> {os.path.relpath(SPECS2)}")


def analyse():
    net = three_bus()
    specs = json.load(open(SPECS)) + (json.load(open(SPECS2)) if os.path.exists(SPECS2) else [])
    eps = net.eps
    rows = []
    models = {}
    for dt in {sp["dtag"] for sp in specs}:
        models[dt] = fr.FrameModel(net, CASES, n_samples=150, face_pts=3, seed=1, factor=1.0, drift_deg=3.0,
                                   ref_phi=0.0, model_err=0.0)
    t0 = time.time()
    for sp in specs:
        path = os.path.join(WORK, sp["name"] + ".gf46")
        if not os.path.exists(os.path.join(path, sp["name"] + "_01.out")):
            continue
        run = read_case(path, sp["name"])
        d = complex(*sp["d_cmd"])
        fm = models[sp["dtag"]]
        S = np.array([sp["S"]])
        y_pre = relay_y(run, T_PRE)
        uL = y_pre[0] / abs(y_pre[0])
        k = None if sp["kind"] == "normal" else CASES.index(tuple(sp["case"]))
        y_mod = fm.measure(S, d, k)[0]
        pieces = fm.zonotopes(d, k)
        for t in ([T_PRE] if k is None else T_DEC):
            y = relay_y(run, t) * np.conj(uL)
            err = np.abs(fr.nw._realify(y - y_mod)).max() / eps
            out = fr.distance_to_set(pieces, y) / eps
            rows.append(dict(name=sp["name"], dtag=sp["dtag"], kind=sp["kind"], case=sp["case"],
                             cycles=float((t - T_FAULT) * 60) if k is not None else None,
                             err_settled_eps=float(err), outside_set_eps=float(out)))
    print(f"{len(rows)} decision points from {len({r['name'] for r in rows})} runs  [{time.time() - t0:.0f} s]")
    summ = {}
    for dt in sorted({sp["dtag"] for sp in specs}):
        for kind in ("normal", "fault"):
            q = [r for r in rows if r["dtag"] == dt and r["kind"] == kind]
            if not q:
                continue
            er = np.array([r["err_settled_eps"] for r in q])
            ou = np.array([r["outside_set_eps"] for r in q])
            w = max(q, key=lambda r: r["outside_set_eps"])
            summ[f"{dt}_{kind}"] = dict(n=len(q), err_median=float(np.median(er)), err_max=float(er.max()),
                                        outside_median=float(np.median(ou)), outside_max=float(ou.max()),
                                        outside_max_at=[w["name"], w["cycles"]], n_outside=int((ou > 1e-6).sum()))
            print(f"{dt} {kind:6s}: {len(q)} points; |EMT - settled model| median {np.median(er):.2f}, max {er.max():.2f} eps; "
                  f"outside own set (model_err 0): {int((ou > 1e-6).sum())}, max {ou.max():.3f} eps ({w['name']}, {w['cycles']} cycles)")
    json.dump(dict(deltas={k: [v.real, v.imag] for k, v in {**DELTAS, **BETWEEN}.items()}, t_dec_cycles=list((T_DEC - T_FAULT) * 60),
                   summary=summ, rows=rows), open(os.path.join(OUT, "frames_emt_check.json"), "w"), indent=1)
    print("-> results/network/frames_emt_check.json")


if __name__ == "__main__":
    {"spec": make, "between": between, "analyse": analyse}[sys.argv[1]]()
