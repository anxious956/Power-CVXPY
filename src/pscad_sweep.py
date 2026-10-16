"""
Drive PSCAD through its automation library: set a slider or variable on a loaded case, run it,
and keep each run's output in its own folder so the next run does not overwrite it.

Runs under PSCAD's own Python (C:\\Program Files\\Python37\\python.exe, which has mhi.pscad), with
PSCAD open:

    "C:\\Program Files\\Python37\\python.exe" src/pscad_sweep.py <work_dir> case1 "Fault location" 1 2 3 4
    ... case3 "Fault location" 1 2 3 4 5 6 --set "Fault Type=1" --set "Rf=10"

--set holds other controls fixed for the whole sweep; every control is put back afterwards.
The case file must already be a working copy (data/pscad_work/, git-ignored), never the shipped
example. Output folders: <work_dir>/runs/<case>[_<fixed>=<v>...]_<slider>=<value>/.
"""
import os, sys, shutil, time, glob
import mhi.pscad


def find_control(prj, name):
    """The slider / variable component whose 'Name' parameter is `name`, on any canvas."""
    hits = []
    for defn in ("master:var_pot", "master:var", "master:var_switch"):
        try:
            comps = prj.find_all(defn)
        except Exception:
            comps = []
        for c in comps:
            try:
                if (c.parameters().get("Name") or "").strip() == name.strip():
                    hits.append(c)
            except Exception:
                pass
    if len(hits) != 1:
        raise LookupError(f"{len(hits)} controls named {name!r} in {prj.name}")
    return hits[0]


def main():
    args, fixed = [], []
    it = iter(sys.argv[1:])
    for x in it:
        if x == "--set":                       # --set "Fault Type=1": held fixed for the whole sweep
            k, v = next(it).split("=", 1)
            fixed.append((k, v))
        else:
            args.append(x)
    work, case, control, values = args[0], args[1], args[2], args[3:]
    pscad = mhi.pscad.application()
    if case not in [p["name"] for p in pscad.projects()]:
        pscad.load(os.path.join(work, case + ".pscx"))
    prj = pscad.project(case)
    prj.parameters(PlotType="OUT", output_filename=case + ".out")
    comp = find_control(prj, control)
    restore = [(comp, comp.parameters()["Value"])]
    for k, v in fixed:
        c = find_control(prj, k)
        restore.append((c, c.parameters()["Value"]))
        c.parameters(Value=v)
    tag = "".join(f"_{k.strip().replace(' ', '_')}={v}" for k, v in fixed)
    runs = os.path.join(work, "runs")
    os.makedirs(runs, exist_ok=True)
    try:
        for v in values:
            comp.parameters(Value=v)
            t0 = time.time()
            prj.run()
            out_dir = [d for d in glob.glob(os.path.join(work, case + ".gf*")) if os.path.isdir(d)][0]
            dest = os.path.join(runs, f"{case}{tag}_{control.strip().replace(' ', '_')}={v}")
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            os.makedirs(dest)
            # channel files, the .inf, and the line-constants output of every line in the case
            for f in glob.glob(os.path.join(out_dir, "*.out")) + glob.glob(os.path.join(out_dir, case + ".inf")) \
                    + glob.glob(os.path.join(out_dir, "*.tli")):
                shutil.copy2(f, dest)
            print(f"{control} = {v}: {time.time() - t0:.1f} s -> {dest}", flush=True)
    finally:
        for c, v in restore:
            c.parameters(Value=v)


if __name__ == "__main__":
    main()
