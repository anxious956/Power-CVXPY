"""
One table over a set of PSCAD runs: for every run and every relay terminal, the A-G loop, the
direction, the loop the selector releases, and the zone-1 decision.

    python src/pscad_table.py data/pscad_work/Relay_Cases/runs "case3_Fault_Type=1_Fault_location=*" case3 \
        --ends 1:LINE1 2:LINE1 3:LINE2 4:LINE2

Each --ends item is <terminal digit>:<line-constants name(s) of the line that relay protects>.
"""
import os, sys, glob, argparse, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pscad_check import check


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_dir")
    ap.add_argument("pattern")
    ap.add_argument("case")
    ap.add_argument("--ends", nargs="+", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    rows = []
    for d in sorted(glob.glob(os.path.join(a.runs_dir, a.pattern))):
        label = os.path.basename(d).split("_")[-1]
        for item in a.ends:
            end, line = item.split(":")
            r = check(d, a.case, end, line)
            ag = r["loops"]["ag"]
            x1 = r["z1"].imag
            ok_loop = r["released"] == ["ag"]
            trip = r["distance_pct"] is not None and r["distance_pct"] <= 85 and r["forward"]
            rows.append(dict(run=label, end=end, line=line, ag_pct=round(ag.imag / x1 * 100, 1),
                             ag_ohm=[round(ag.real, 2), round(ag.imag, 2)],
                             direction="fwd" if r["forward"] else "REV", released=r["released"],
                             released_ok=ok_loop,
                             element_pct=None if r["distance_pct"] is None else round(r["distance_pct"], 1),
                             zone1_trip=bool(trip), t_inception=round(r["t_inception"], 4)))
    print(f"{'run':<18}{'end':>4} {'line':<7}{'A-G loop % of X':>16}  {'dir':<4} {'released':<12}{'element %':>10}  zone-1")
    for q in rows:
        el = "-" if q["element_pct"] is None else f"{q['element_pct']:.1f}"
        print(f"{q['run']:<18}{q['end']:>4} {q['line']:<7}{q['ag_pct']:>16.1f}  {q['direction']:<4} "
              f"{','.join(q['released']) + ('' if q['released_ok'] else ' (x)'):<12}{el:>10}  {'TRIP' if q['zone1_trip'] else '-'}")
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
