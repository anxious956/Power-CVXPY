"""
Run a list of two-bus PSCAD cases (from src/pscad_delta_design.py) in one PSCAD session. Resumable:
a run whose output already exists is skipped. Each project is unloaded after its run so the
workspace does not grow.

    "C:/Program Files/Python37/python.exe" src/pscad_batch.py results/pscad/delta_design.json
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mhi.pscad
from pscad_twobus import build
from pscad_inverter import WORK, run


def main():
    spec = json.load(open(sys.argv[1]))
    runs = spec["runs"]
    pscad = mhi.pscad.application()
    t_all = time.time()
    for k, r in enumerate(runs):
        out = os.path.join(WORK, r["name"] + ".gf46", r["name"] + "_01.out")
        if os.path.exists(out):
            continue
        prj = build(pscad, r["name"], m=r["m"], scen=r["scen"], rf=r["rf_ohm"], idref=r["idref"], iqref=r["iqref"],
                    mode2=r["mode2"], d2mag=r["d2mag"], d2ang=r["d2ang"], es_pu=r["es_pu"], ph_deg=r["ph_deg"])
        dt, errs = run(prj)
        try:
            prj.unload()
        except Exception:
            pass
        status = "ok" if not errs and os.path.exists(out) else "FAILED: " + " | ".join(errs[:2])[:200]
        print(f"[{k + 1}/{len(runs)}] {r['name']}: {dt:.1f} s {status}", flush=True)
    print(f"done in {time.time() - t_all:.0f} s", flush=True)


if __name__ == "__main__":
    main()
