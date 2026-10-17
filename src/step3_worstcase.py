"""
D1's worst-case curve (results/STEP3_PILOT.md, option A): on clean EMT runs with delta injected, the fraction of
faults whose distance to N exceeds 2 eps in every decision window (2.0 ... 3.0 cycles after inception), i.e. faults
D1 detects under ANY noise inside the eps box. Clopper-Pearson 95 % bounds. Paired scenarios across delta levels.

    python src/step3_worstcase.py [specs.json]      -> results/step3/worstcase_<name>.json
"""
import os, sys, json, time
import numpy as np
from scipy.stats import beta
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import step3_detectors as det
from step3_frontend import Relay

OUT = os.path.join(HERE, "..", "results", "step3")


def cp(k, n, a=0.05):
    lo = 0.0 if k == 0 else beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - a / 2, k + 1, n - k)
    return float(lo), float(hi)


def main(path):
    specs = [sp for sp in json.load(open(path)) if sp["kind"] == "fault"]
    tag = os.path.splitext(os.path.basename(path))[0].replace("_specs", "")
    t0 = time.time()
    rows = []
    for sp in specs:
        rel = Relay(sp["name"], tier="clean", seed=0)
        s = det.d1_score(rel, sp, "oracle")
        rows.append(dict(name=sp["name"], scenario=sp["scenario"], stratum=sp["stratum"], level=sp["level"],
                         in_range=sp["in_range"], case=sp["case"], d1_clean_eps=float(s), guaranteed=bool(s > 2.0)))
    print(f"{len(rows)} fault runs  [{time.time() - t0:.0f} s]")
    levels = sorted({r["level"] for r in rows})
    summ = {}
    print("D1 guaranteed under any noise in the eps box (clean distance > 2 eps): fraction [95 % bounds], n")
    for st in ("hard", "hard_bc", "uniform", "in_range"):
        cells = []
        for lv in levels:
            q = [r for r in rows if r["level"] == lv and (r["in_range"] if st == "in_range" else r["stratum"] == st)]
            k, n = sum(r["guaranteed"] for r in q), len(q)
            lo, hi = cp(k, n)
            summ[f"{st}|{lv}"] = dict(k=k, n=n, frac=k / n, lo=lo, hi=hi, median_eps=float(np.median([r["d1_clean_eps"] for r in q])),
                                      min_eps=float(min(r["d1_clean_eps"] for r in q)))
            cells.append(f"{k / n:.2f} [{lo:.2f}, {hi:.2f}]")
        print(f"  {st:8s} n={n:3d}: " + "  ".join(cells))
    print("smallest clean D1 distance (eps) per level, hard A-G: " +
          "  ".join(f"{summ[f'hard|{lv}']['min_eps']:.2f}" for lv in levels))
    json.dump(dict(levels=levels, summary=summ, rows=rows), open(os.path.join(OUT, f"worstcase_{tag}.json"), "w"), indent=1)
    print(f"-> results/step3/worstcase_{tag}.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "dense_specs.json"))
