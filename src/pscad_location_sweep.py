"""
Sweep the fault point along a line in PSCAD by moving the joint between two line segments.

The shipped Relay_Cases/case2 is one line built from two segments (instances T1 and T2 of the same
line definition) with fault point 3 at the joint. Setting T1 = m km and T2 = (L - m) km puts that
fault at m / L of the line from end 1, with the total line unchanged. Runs under PSCAD's Python
(C:\\Program Files\\Python37\\python.exe, mhi.pscad) with PSCAD open, on a working copy:

    "C:\\Program Files\\Python37\\python.exe" src/pscad_location_sweep.py <work_dir> 50 60 70 80 85 90 \
        --set "Fault Type=1" --set "Rf=0.001"

A distributed line segment must have a travel time longer than the time step, or EMTDC aborts
(a 12 km segment travels in ~40 us, below the shipped 50 us): use --prj time_step=5 for segments
down to ~2 km. Every run is checked: old output is deleted first, and a run with PSCAD errors or
no fresh output stops the sweep instead of copying stale files.

Output: <work_dir>/runs/case2_sweep[_<fixed>=<v>...]_m=<m>/. Lengths and controls are put back.
"""
import os, sys, shutil, time, glob
import mhi.pscad
from pscad_sweep import find_control

CASE, TOTAL_KM, JOINT_POINT = "case2", 100.0, "3"


def segments(prj):
    """The two line-segment instances (TLine objects), found by name."""
    out = []
    for name in ("T1", "T2"):
        hits = [c for c in prj.find_all(name) if type(c).__name__ == "TLine"]
        if len(hits) != 1:
            raise LookupError(f"{len(hits)} TLine components named {name}")
        out.append(hits[0])
    return out


def main():
    args, fixed, prj_params = [], [], {}
    it = iter(sys.argv[1:])
    for x in it:
        if x == "--set":
            k, v = next(it).split("=", 1)
            fixed.append((k, v))
        elif x == "--prj":                     # project parameter, e.g. --prj time_step=5
            k, v = next(it).split("=", 1)
            prj_params[k] = v
        else:
            args.append(x)
    work, points = args[0], [float(v) for v in args[1:]]
    pscad = mhi.pscad.application()
    if CASE not in [p["name"] for p in pscad.projects()]:
        pscad.load(os.path.join(work, CASE + ".pscx"))
    prj = pscad.project(CASE)
    prj_restore = {k: prj.parameters()[k] for k in prj_params}
    prj.parameters(PlotType="OUT", output_filename=CASE + ".out", **prj_params)
    t1, t2 = segments(prj)
    restore = [(t1, "Length", t1.parameters()["Length"]), (t2, "Length", t2.parameters()["Length"])]
    for k, v in [("Fault location", JOINT_POINT)] + fixed:
        c = find_control(prj, k)
        restore.append((c, "Value", c.parameters()["Value"]))
        c.parameters(Value=v)
    tag = "".join(f"_{k.strip().replace(' ', '_')}={v}" for k, v in fixed)
    tag += "".join(f"_{k}={v}" for k, v in prj_params.items())
    runs = os.path.join(work, "runs")
    os.makedirs(runs, exist_ok=True)
    try:
        for m in points:
            t1.parameters(Length=f"{m:g} [km]")
            t2.parameters(Length=f"{TOTAL_KM - m:g} [km]")
            for d in glob.glob(os.path.join(work, CASE + ".gf*")):
                for f in glob.glob(os.path.join(d, CASE + "_*.out")) + glob.glob(os.path.join(d, CASE + ".inf")):
                    os.remove(f)               # so a failed run cannot leave the previous run's output behind
            t0 = time.time()
            prj.run()
            errors = [str(x.text) for x in prj.messages() if x.status == "error"]
            out_dir = [d for d in glob.glob(os.path.join(work, CASE + ".gf*")) if os.path.isdir(d)][0]
            if errors or not glob.glob(os.path.join(out_dir, CASE + "_01.out")):
                raise RuntimeError(f"m = {m:g}: run failed ({len(errors)} errors): " + " | ".join(errors[:3]))
            dest = os.path.join(runs, f"{CASE}_sweep{tag}_m={m:g}")
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            os.makedirs(dest)
            for f in glob.glob(os.path.join(out_dir, "*.out")) + glob.glob(os.path.join(out_dir, CASE + ".inf")):
                shutil.copy2(f, dest)
            print(f"m = {m:g} km: {time.time() - t0:.1f} s", flush=True)
    finally:
        for c, k, v in restore:
            c.parameters(**{k: v})
        if prj_restore:
            prj.parameters(**prj_restore)


if __name__ == "__main__":
    main()
