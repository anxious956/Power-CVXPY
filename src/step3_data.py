"""
Step 3's data: PSCAD runs on the three-bus network with the designed signal injected (docs/STEP3.md).

The design point is delta* = 1.12 pu at 225 deg, rho = 0.1, with the PLL-like reference filter (first order, 15 Hz)
in the inverter (results/FRAMES.md). Every scenario is run at each delta level s * delta*, s in LEVELS, with the same
operating point, fault and inception (paired). The inverter's settings are fixed in its own frame: ID - jIQ is the
commanded positive-sequence current, and D2MAG / D2ANG the commanded delta.

Strata (each scenario records its own):
  hard     A-G, R_f 20-40 ohm (0.5-1.0 rF), inside the design's ranges (L1 15-95 %, L2 5-50 %), operating point near the
           corner the design's witnesses sit at (the witness source point of the nearest binding case, jittered)
  hard_bc  B-C, R_f 20-40 ohm, inside the ranges, operating point uniform
  uniform  A-G or B-C, R_f 0-40 ohm, inside the ranges, operating point uniform
  outside  A-G or B-C, R_f 0-40 ohm, outside the ranges (L1 2-15 %, L2 50-98 %)
  normal   no fault, operating point uniform
  load     a balanced load step at bus R or S (0.1-0.3 pu, lagging), at the inception time
  phase1   a single-phase load at bus R or S (z = 6-12 pu), at the inception time
Inception is uniform over one cycle from 0.30 s. Instrument errors and noise are not in the runs; the front end
(src/step3_frontend.py) adds them to the sampled waveforms.

    python src/step3_data.py pilot        -> results/step3/pilot_specs.json   (20 scenarios x 5 levels = 100 runs)
    python src/step3_data.py dense        -> results/step3/dense_specs.json   (70 scenarios x 5 levels = 350 runs)
    "C:/Program Files/Python37/python.exe" src/pscad_network.py fast results/step3/pilot_specs.json
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import make_spec, three_bus
from network_delta_test import CASES
from frames_emt_check import _settings

OUT = os.path.join(HERE, "..", "results", "step3")
DESIGN = dict(mag=1.12, angle_deg=225.0, rho=0.1, tang_hz=15.0)
LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0)
TANG = 1.0 / (2 * np.pi * DESIGN["tang_hz"])
T0 = 0.30
RANGES = {"L1": (0.15, 0.95), "L2": (0.05, 0.50)}
OUTSIDE = {"L1": (0.02, 0.15), "L2": (0.50, 0.98)}
WITNESS_SPECS = os.path.join(HERE, "..", "results", "network", "frames_design_specs_pll.json")
PILOT = dict(hard=8, hard_bc=2, uniform=4, outside=2, normal=2, load=1, phase1=1)
DENSE = dict(hard=40, hard_bc=10, uniform=20)          # the worst-case curve (results/STEP3_PILOT.md, option A)


def delta(level):
    return level * DESIGN["mag"] * np.exp(1j * np.radians(DESIGN["angle_deg"]))


def in_range(line, m):
    lo, hi = RANGES[line]
    return lo - 1e-9 <= m <= hi + 1e-9


def scenarios(counts, seed):
    """Draw the scenarios: a list of dicts with stratum, fault (line, m, type, R_f / rF) or None, confuser, S, t_fault."""
    rng = np.random.default_rng(seed)
    wit = [(tuple(sp["case"]), np.array(sp["S"])) for sp in json.load(open(WITNESS_SPECS))
           if sp["group"] == "witness" and sp["kind"] == "fault"]
    out = []

    def loc(ranges):
        line = str(rng.choice(["L1", "L2"]))
        lo, hi = ranges[line]
        return line, float(np.round(rng.uniform(lo, hi), 3))

    for stratum, n in counts.items():
        for _ in range(n):
            sc = dict(stratum=stratum, fault=None, confuser=None, t_fault=float(np.round(T0 + rng.uniform(0, 1) / 60, 5)))
            S = rng.uniform(-1, 1, 4)
            if stratum == "hard":
                line, m = loc(RANGES)
                mr = float(np.round(rng.uniform(0.5, 1.0), 3))
                near = min(wit, key=lambda w: (w[0][0] != line) * 10 + abs(w[0][1] - m) + abs(w[0][3] - mr))
                S = np.clip(near[1] + rng.uniform(-0.1, 0.1, 4), -1, 1)
                sc["fault"] = [line, m, "ag", mr]
            elif stratum == "hard_bc":
                line, m = loc(RANGES)
                sc["fault"] = [line, m, "ab", float(np.round(rng.uniform(0.5, 1.0), 3))]
            elif stratum in ("uniform", "outside"):
                line, m = loc(RANGES if stratum == "uniform" else OUTSIDE)
                sc["fault"] = [line, m, str(rng.choice(["ag", "ab"])), float(np.round(rng.uniform(0.0, 1.0), 3))]
            elif stratum == "load":
                y = rng.uniform(0.1, 0.3) * np.exp(-1j * rng.uniform(0.1, 0.4))
                sc["confuser"] = dict(kind="load_step", bus=str(rng.choice(["R", "S"])), y1=[float(y.real), float(y.imag)],
                                      t=sc["t_fault"])
            elif stratum == "phase1":
                z = rng.uniform(6, 12) * np.exp(1j * rng.uniform(0.1, 0.4))
                sc["confuser"] = dict(kind="single_phase", bus=str(rng.choice(["R", "S"])), phase="A",
                                      z=[float(z.real), float(z.imag)], t=sc["t_fault"])
            sc["S"] = [float(x) for x in S]
            sc["in_range"] = bool(sc["fault"] is not None and in_range(sc["fault"][0], sc["fault"][1]))
            out.append(sc)
    return out


def specs_for(scs, prefix):
    net = three_bus()
    fm = fr.FrameModel(net, CASES[:1], n_samples=10, face_pts=2, seed=0)
    specs = []
    for k, sc in enumerate(scs):
        e, ic = fm.sources(np.array([sc["S"]]))
        f = sc["fault"]
        fault = None if f is None else (f[0], f[1], f[2], f[3] * net.rF)
        for lv in LEVELS:
            d = delta(lv)
            sp = make_spec(f"{prefix}_{k:03d}_l{int(round(lv * 100)):03d}", net, fault, {"G": e[0]}, {}, 1)
            sp["settings"] = _settings(ic[0], d)
            sp["settings"]["I"]["TANG"] = TANG
            sp["t_fault"] = sc["t_fault"]
            if sc["confuser"]:
                sp["confuser"] = sc["confuser"]
            sp.update(kind="fault" if f else "normal", scenario=k, stratum=sc["stratum"], level=lv,
                      d_cmd=[d.real, d.imag], S=sc["S"], case=f, in_range=sc["in_range"], design=DESIGN)
            specs.append(sp)
    return specs


def pilot():
    os.makedirs(OUT, exist_ok=True)
    scs = scenarios(PILOT, seed=31)
    specs = specs_for(scs, "s3p")
    json.dump(dict(design=DESIGN, levels=LEVELS, scenarios=scs), open(os.path.join(OUT, "pilot_scenarios.json"), "w"), indent=1)
    json.dump(specs, open(os.path.join(OUT, "pilot_specs.json"), "w"), indent=1)
    by = {}
    for sc in scs:
        by[sc["stratum"]] = by.get(sc["stratum"], 0) + 1
    print(f"{len(scs)} scenarios {by} x {len(LEVELS)} levels = {len(specs)} runs -> results/step3/pilot_specs.json")


def dense():
    """Clean runs for D1's worst-case curve: the guaranteed fraction (clean distance to N above 2 eps) against delta,
    with binomial bounds. Its own scenarios (seed 41), disjoint from the pilot's."""
    os.makedirs(OUT, exist_ok=True)
    scs = scenarios(DENSE, seed=41)
    specs = specs_for(scs, "s3w")
    json.dump(dict(design=DESIGN, levels=LEVELS, scenarios=scs), open(os.path.join(OUT, "dense_scenarios.json"), "w"), indent=1)
    json.dump(specs, open(os.path.join(OUT, "dense_specs.json"), "w"), indent=1)
    print(f"{len(scs)} scenarios x {len(LEVELS)} levels = {len(specs)} runs -> results/step3/dense_specs.json")


def normals():
    """Normal operation for worst-case thresholds (review/STEP3_WORSTCASE_REVIEW.md): the 16 corners of the source box
    and 14 random interior points, at every delta level (no fault; t_fault is the pseudo-trigger)."""
    import itertools
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(51)
    pts = [list(map(float, u)) for u in itertools.product((-1.0, 1.0), repeat=4)] +           [list(map(float, x)) for x in rng.uniform(-1, 1, (14, 4))]
    scs = [dict(stratum="normal_corner" if k < 16 else "normal_random", fault=None, confuser=None, S=S, in_range=False,
                t_fault=float(np.round(T0 + rng.uniform(0, 1) / 60, 5))) for k, S in enumerate(pts)]
    specs = specs_for(scs, "s3n")
    json.dump(dict(design=DESIGN, levels=LEVELS, scenarios=scs), open(os.path.join(OUT, "normals_scenarios.json"), "w"), indent=1)
    json.dump(specs, open(os.path.join(OUT, "normals_specs.json"), "w"), indent=1)
    print(f"{len(scs)} normal points x {len(LEVELS)} levels = {len(specs)} runs -> results/step3/normals_specs.json")


if __name__ == "__main__":
    {"pilot": pilot, "dense": dense, "normals": normals}[sys.argv[1]]()
