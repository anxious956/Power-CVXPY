"""
Zone-1 decision along a fault-point sweep made by pscad_location_sweep.py, against the right answer
(trip for a fault on the relay's own line at or below the reach, no trip beyond it).

    python src/pscad_sweep_table.py data/pscad_work/Relay_Cases/runs "case2_sweep_Fault_Type=1_time_step=5" \
        --json results/pscad/sweep_ag_bolted.json
"""
import os, sys, glob, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pscad_check import check

REACH = 85.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_dir")
    ap.add_argument("prefix", help="run folder name up to _m=")
    ap.add_argument("--case", default="case2")
    ap.add_argument("--end", default="1")
    ap.add_argument("--line", default="T1+T2")
    ap.add_argument("--json")
    a = ap.parse_args()
    rows = []
    for d in glob.glob(os.path.join(a.runs_dir, a.prefix + "_m=*")):
        m = float(d.rsplit("m=", 1)[1])
        r = check(d, a.case, a.end, a.line)
        x1 = r["z1"].imag
        ag = r["loops"]["ag"]
        trip = r["distance_pct"] is not None and r["distance_pct"] <= REACH and r["forward"]
        ag_trip = r["forward"] and 0 < ag.imag / x1 * 100 <= REACH       # what the A-G loop alone would decide
        rows.append(dict(fault_pct=m, ag_loop_pct=round(ag.imag / x1 * 100, 2), ag_loop_r_ohm=round(ag.real, 2),
                         released=r["released"], element_pct=None if r["distance_pct"] is None else round(r["distance_pct"], 2),
                         direction="forward" if r["forward"] else "reverse", zone1_trip=bool(trip),
                         ag_loop_alone_trip=bool(ag_trip), should_trip=m <= REACH,
                         correct=bool(trip) == (m <= REACH)))
    rows.sort(key=lambda q: q["fault_pct"])
    print(f"{'fault':>6} {'A-G loop':>9} {'R':>7}  {'released':<9}{'element':>9}  {'trip':<5} {'A-G alone':<10} should")
    for q in rows:
        el = "-" if q["element_pct"] is None else f"{q['element_pct']:.1f}%"
        print(f"{q['fault_pct']:5.0f}% {q['ag_loop_pct']:8.1f}% {q['ag_loop_r_ohm']:6.1f}Ω  {','.join(q['released']):<9}{el:>9}  "
              f"{'TRIP' if q['zone1_trip'] else '-':<5} {'TRIP' if q['ag_loop_alone_trip'] else '-':<10} "
              f"{'trip' if q['should_trip'] else 'no'}{'' if q['correct'] else '   <-- WRONG'}")
    if a.json:
        json.dump(dict(reach_pct=REACH, case=a.case, end=a.end, line=a.line, prefix=a.prefix, rows=rows),
                  open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
