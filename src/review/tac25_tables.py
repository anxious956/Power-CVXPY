"""
The DESIGN.md tables built on the current-limit rows, generated from the result files instead of typed by
hand: §3 (tac25_limit_presets.json), §3.1 (tac25_softlimit.json), §4.1 (tac25_map.json).

    python src/review/tac25_tables.py [--before DIR]

--before DIR: also print each cell as "old -> new" against copies of the same files in DIR.
"""
import os, sys, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "..", "results", "review_wp1")


def _load(name, d=RES):
    return json.load(open(os.path.join(d, name)))


def _cell(r, cont=None):
    if not r or not r.get("feasible"):
        return "none"
    v = f"{r['abs_delta']:.2f}"
    cc = cont if cont is not None else r.get("continuous_check")
    if cc and cc.get("holds") is False:
        v += f"* ({cc.get('n_unseparated')})"
    return v


def presets(d=RES):
    j = _load("tac25_limit_presets.json", d)
    cols = ("none", "h5_outer", "sum", "phase", "phase_disc", "tac25")
    rows = {}
    for pz, v in j["presets"].items():
        rows[pz] = [f"{v['exact_no_limit']:.4f}"] + [_cell(v.get(c)) for c in cols] + \
                   [f"{v['phase']['injectable_limit']:.2f}" if v.get("phase", {}).get("feasible") else "—"]
    head = ["exact (no limit)", "solver, no limit", "H5's reading (a)", "sum rule", "per phase", "bounding disc",
            "TAC25 (1b) as written", "per-phase limit to inject"]
    return head, rows


def softlimit(d=RES):
    j = _load("tac25_softlimit.json", d)
    lims = ("1.1", "1.2", "1.3", "1.5", "2.1")
    rows = {}
    for c in j["cells"]:
        key = f"eps = {c['eps']:g}" + (f", rho = {c['rho']:g}" if c["rho"] else "")
        rows[key] = [_cell(c["hard"].get(l)) for l in lims] + [_cell(c["robust"], c.get("continuous_check")),
                                                               _cell(c["no_limit"])]
    return [f"hard {l}" for l in lims] + ["uncertain [1.1, 2.1]", "(no limit)"], rows


def feasibility_map(d=RES):
    j = _load("tac25_map.json", d)
    plane = j["plane"] if isinstance(j["plane"], list) else [j["plane"]]
    eps_vals = sorted({p["cfg"]["eps"] for p in plane})
    im_vals = sorted({p["cfg"]["i_max"] for p in plane})
    rows = {}
    for e in eps_vals:
        cells = []
        for im in im_vals:
            p = next((p for p in plane if p["cfg"]["eps"] == e and p["cfg"]["i_max"] == im), None)
            cells.append(_cell(p["limit_inside"], p.get("continuous_check")) if p else "")
        p0 = next((p for p in plane if p["cfg"]["eps"] == e), None)
        cells.append(_cell(p0["no_limit"]) if p0 else "")
        rows[f"eps = {e:g}"] = cells
    return [f"I_max {im:g}" for im in im_vals] + ["(no limit)"], rows


def markdown(head, rows, before=None, first="Preset"):
    out = [f"| {first} | " + " | ".join(head) + " |", "|---" * (len(head) + 1) + "|"]
    for k, v in rows.items():
        if before and k in before:
            v = [b if b == a else f"{b} → **{a}**" for a, b in zip(v, before[k])]
        out.append(f"| {k} | " + " | ".join(v) + " |")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--before")
    a = ap.parse_args()
    for title, fn, first in (("§3 presets, I_max 1.2", presets, "Preset"), ("§3.1 soft limit", softlimit, ""),
                             ("§4.1 map, base network, rho 0", feasibility_map, "")):
        h, r = fn()
        b = fn(a.before)[1] if a.before else None
        print(f"\n### {title}\n")
        print(markdown(h, r, b, first))
