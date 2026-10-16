"""
Fast runs of the two-bus circuit: build the project once per fault type, then for each run only change
the parameters that differ (line-segment R and L for the fault point, fault resistance, source EMF,
inverter settings) and re-run. Building a fresh project costs ~80 s of API calls per run; an update
costs a few seconds.

Components are found by the grid location pscad_twobus.build gives them, so this module and build()
must stay in step. Each run's output is copied to WORK/<run name>.gf46/ with the files renamed to the
run name, so the analysis scripts read it exactly like a run built by pscad_batch.py.

    "C:/Program Files/Python37/python.exe" src/pscad_twobus_fast.py results/pscad/delta_design.json
"""
import os, sys, json, glob, shutil, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mhi.pscad
from pscad_twobus import build, Z1_LINE, ZN_LINE, W, VLL
from pscad_inverter import WORK, INPUTS, port_xy, run

CTRL_X, CTRL_Y = 90, 30                       # controller location in build()


def _loc(comp):
    loc = comp.get_location() if hasattr(comp, "get_location") else comp.location
    return int(loc[0]), int(loc[1])


def index(prj):
    """{(defn, x, y): component} for the components a run changes."""
    c = prj.canvas("Main")
    idx = {}
    for defn in ("master:resistor", "master:inductor", "master:breaker1", "master:const", "master:source3"):
        for comp in c.find_all(defn):
            idx[(defn, *_loc(comp))] = comp
    return idx


def _r(z):
    return f"{max(z.real, 1e-6):.6g} [ohm]"


def _l(z):
    return f"{max(z.imag, 1e-6) / W:.6g} [H]"


def set_case(idx, scen, m, rf, es_pu, ph_deg, idref, iqref, mode2, d2mag, d2ang, lim=0):
    za, zb, zn = m * Z1_LINE, (1 - m) * Z1_LINE, m * ZN_LINE
    for k in range(3):
        y = 20 + 4 * k
        idx[("master:resistor", 14, y)].parameters(R=_r(za))
        idx[("master:inductor", 18, y)].parameters(L=_l(za))
        idx[("master:resistor", 24, y)].parameters(R=_r(zb))
        idx[("master:inductor", 28, y)].parameters(L=_l(zb))
    idx[("master:resistor", 14, 36)].parameters(R=_r(zn))
    idx[("master:inductor", 18, 36)].parameters(L=_l(zn))
    r = max(rf, 1e-3)
    if scen == "ag":
        idx[("master:breaker1", 30, 44)].parameters(RON=f"{r:.6g} [ohm]")
    elif scen == "ab":
        for y in (44, 48):
            idx[("master:breaker1", 30, y)].parameters(RON=f"{r / 2:.6g} [ohm]")
    idx[("master:source3", 10, 10)].parameters(Es=f"{VLL * es_pu:.6g} [kV]", Ph=f"{ph_deg:.6g} [deg]")
    values = dict(ID=idref, IQ=iqref, MODE2=float(mode2), D2MAG=d2mag, D2ANG=d2ang, LIM=float(lim))
    for p, v in values.items():
        px, py = port_xy(p)
        idx[("master:const", CTRL_X + px // 18 - 2, CTRL_Y + py // 18)].parameters(Value=str(v))


def collect(prj_name, run_name):
    """Copy the project's output to WORK/<run_name>.gf46, renamed to the run."""
    src = os.path.join(WORK, prj_name + ".gf46")
    dst = os.path.join(WORK, run_name + ".gf46")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for f in glob.glob(os.path.join(src, prj_name + "_*.out")) + [os.path.join(src, prj_name + ".inf")]:
        shutil.copy2(f, os.path.join(dst, os.path.basename(f).replace(prj_name, run_name, 1)))


def main():
    spec = json.load(open(sys.argv[1]))
    pscad = mhi.pscad.application()
    projects = {}
    t_all = time.time()
    for k, r in enumerate(spec["runs"]):
        if os.path.exists(os.path.join(WORK, r["name"] + ".gf46", r["name"] + "_01.out")):
            continue
        scen = r["scen"]
        if scen not in projects:
            name = f"fast2_{scen}"
            prj = build(pscad, name, scen=scen, mode2=2)
            projects[scen] = (name, prj, index(prj))
        name, prj, idx = projects[scen]
        set_case(idx, scen, r["m"], r["rf_ohm"], r["es_pu"], r["ph_deg"], r["idref"], r["iqref"], r["mode2"], r["d2mag"],
                 r["d2ang"], r.get("lim", 0))
        for f in glob.glob(os.path.join(WORK, name + ".gf46", name + "_*.out")):
            os.remove(f)
        dt, errs = run(prj)
        ok = not errs and os.path.exists(os.path.join(WORK, name + ".gf46", name + "_01.out"))
        if ok:
            collect(name, r["name"])
        print(f"[{k + 1}/{len(spec['runs'])}] {r['name']}: {dt:.1f} s {'ok' if ok else 'FAILED: ' + ' | '.join(errs[:2])[:200]}",
              flush=True)
    print(f"done in {time.time() - t_all:.0f} s", flush=True)


if __name__ == "__main__":
    main()
