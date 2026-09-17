"""The feasibility map: for which measurement error, inverter current limit, network strength,
IBR share and network homogeneity does an admissible auxiliary signal exist, how large is it, and
with how much margin?

Everything here uses src/review/tac25_design.py, i.e. the TAC25 formulation with the inverter
current limit INSIDE the problem, the sound outer source set (H6), a separation margin in
measurement units (H14), a global polar solve over the delta-plane (H15), and a dense continuous
(m, R_f) re-check of whatever delta is returned (H13).

AXES AND HOW THEY ARE PARAMETERISED (two-bus sequence model, src/aux_model.py)

  eps            measurement error per real component of the relay measurement, in pu. NOT white
                 noise: the binding error is the per-installation ratio and phase error, which does
                 not average down. Kasztenny 2021 section III.A-B during faults gives VT 3-6 % and
                 CT 5-10 %, and eq. (9b) says they ADD in the impedance, so the defensible band on a
                 ~1 pu measurement is roughly 0.08-0.16. Swept 0.02-0.16.
                 (This also re-frames H2: eps is indeed 111-208x the WHITE-NOISE phasor std, but
                 white noise is not the binding error model, so that comparison was against the
                 wrong quantity. See papers/notes/E_practitioner_settings.md section 7.)

  i_max          inverter current limit, pu of inverter rating. Swept 1.1-1.5 as asked, plus 2.1
                 because REVIEW.md claim 20 measured median |I1|+|I2| of 1.07-1.18 pu on
                 EvEMTBench with p95 ~1.5 and max ~2.1 -- i.e. the limit is not hard in the data.
                 This matters more than any other axis; see DESIGN.md.

  strength       source impedance behind the relay, as a multiple of the preset's weak SG. The
                 implied SIR = |z_S| / |z_line| is reported with every row.

  ibr_share      "SG" = synchronous source at the relay end, "IBR" = inverter at both ends. The
                 remote source is a current source in both cases, so this axis is local only.

  homogeneity    the source impedance is rotated off the line angle by `homog_deg`; 0 deg is a
                 homogeneous network. This is the axis rung R3's tilt lives on.

    python src/review/tac25_map.py [--quick]      -> results/review_wp1/tac25_map.json
"""
import os, sys, json, time, pickle, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import aux_model as am
from wp1_common import ModelSet, source_sets
import tac25_design as td
from review import common as cm

OUT = os.path.join(cm.ROOT, "results", "review_wp1")
CKPT = os.path.join(cm.ROOT, "logs", "ckpt", "tac25_map")
CODE = ("src/review/tac25_design.py", "src/review/tac25_map.py", "src/review/wp1_common.py", "src/aux_model.py")

BASE = dict(eps=0.08, i_max=1.2, strength=1.0, local="SG", homog_deg=0.0, rho=0.0, rf=1.0)
EPS_GRID = (0.02, 0.04, 0.08, 0.12, 0.16)
IMAX_GRID = (1.1, 1.2, 1.3, 1.5, 2.1)
STRENGTH_GRID = (0.25, 0.5, 1.0, 2.0, 4.0)
HOMOG_GRID = (0.0, 15.0, 30.0, 45.0)
RHO_GRID = (0.0, 0.1)


def make_params(eps, strength=1.0, local="SG", homog_deg=0.0, rf=1.0):
    """weak_sg-family parameters with the source impedance scaled and rotated."""
    rot = np.exp(-1j * np.deg2rad(homog_deg))          # 0 deg -> purely reactive, as the line is
    zs = {k: complex(v * strength * rot) for k, v in am._WEAK.items()}
    return am.Params(name=f"map_eps{eps:g}_s{strength:g}_h{homog_deg:g}_{local}",
                     local=local, zs=zs, gen_i=[0.3, 0.3], eps=eps, rF=rf)


def sir_of(p):
    return float(abs(p.zs[1]) / abs(p.z1))


def solve_cell(cfg, mode="outer", r_step=0.02, n_ang=72, validate=True):
    p = make_params(cfg["eps"], cfg["strength"], cfg["local"], cfg["homog_deg"], cfg["rf"])
    ms = ModelSet(p, mode=mode)
    t0 = time.time()
    # what the tool returns with the limit read as TAC25 reads it
    r = td.min_delta(ms, i_max=cfg["i_max"], limit_inside=True, limit_design=False,
                     rho=cfg["rho"], r_step=r_step, n_ang=n_ang, r_max=2.0)
    # the two references: no limit at all, and the limit as H5 applied it (outer check on delta)
    r_free = td.min_delta(ms, i_max=cfg["i_max"], limit_inside=False, limit_design=False,
                          rho=cfg["rho"], r_step=r_step, n_ang=n_ang, r_max=2.0)
    r_h5 = td.min_delta(ms, i_max=cfg["i_max"], limit_inside=False, limit_design=True,
                        rho=cfg["rho"], r_step=r_step, n_ang=n_ang)
    out = dict(cfg=cfg, sir=sir_of(p), mode=mode,
               tac25=dict(feasible=r["feasible"], abs_delta=r["abs_delta"], angle_deg=r["angle_deg"]),
               no_limit=dict(feasible=r_free["feasible"], abs_delta=r_free["abs_delta"]),
               h5_outer_check=dict(feasible=r_h5["feasible"], abs_delta=r_h5["abs_delta"]),
               i_plus_max=r["i_plus_max"], runtime_s=float(time.time() - t0))
    if validate and r["feasible"]:
        out["continuous_check"] = td.validate_continuous(p, mode, r["delta"], p.eps * (1 + cfg["rho"]),
                                                         i_max=cfg["i_max"], limit_inside=True)
    return out


def cell(cfg, commit, **kw):
    os.makedirs(CKPT, exist_ok=True)
    path = os.path.join(CKPT, cm.config_hash(dict(cfg, **kw)) + ".pkl")
    if os.path.exists(path):
        rec = pickle.load(open(path, "rb"))
        if rec["_config"] == dict(cfg, **kw) and cm.code_unchanged(rec["_commit"], commit, CODE):
            return rec["result"]
    r = solve_cell(cfg, **kw)
    pickle.dump(dict(_commit=commit, _config=dict(cfg, **kw), result=r), open(path, "wb"))
    return r


def line(tag, r):
    t, f, h = r["tac25"], r["no_limit"], r["h5_outer_check"]
    g = lambda d: (f"{d['abs_delta']:.3f}" if d["feasible"] else "none")
    cc = r.get("continuous_check")
    v = "" if cc is None else ("  cont: ok" if cc["holds"] else f"  cont: {cc['n_unseparated']}/{cc['n_checked']} FAIL")
    return (f"{tag:52s} SIR {r['sir']:4.2f}  |i+|max {r['i_plus_max']:.2f}  "
            f"no-limit {g(f):>5}  H5-outer {g(h):>6}  TAC25 {g(t):>5}{v}  [{r['runtime_s']:.0f}s]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="coarser delta grid")
    a = ap.parse_args()
    kw = dict(mode="outer", r_step=0.04 if a.quick else 0.02, n_ang=36 if a.quick else 72)
    commit = cm.git_commit()
    out = dict(commit=commit, base=BASE, mode=kw["mode"], r_step=kw["r_step"], n_ang=kw["n_ang"],
               axes=dict(eps=EPS_GRID, i_max=IMAX_GRID, strength=STRENGTH_GRID,
                         homog_deg=HOMOG_GRID, rho=RHO_GRID), plane=[], oat={})
    t0 = time.time()

    print("=== eps x i_max plane (base network) ===", flush=True)
    for eps in EPS_GRID:
        for imax in IMAX_GRID:
            cfg = dict(BASE, eps=eps, i_max=imax)
            r = cell(cfg, commit, **kw)
            out["plane"].append(r)
            print(line(f"eps {eps:.2f}  I_max {imax:.1f}", r), flush=True)
            json.dump(out, open(os.path.join(OUT, "tac25_map.json"), "w"), indent=1, default=str)

    for axis, grid, key in (("strength", STRENGTH_GRID, "strength"), ("homogeneity", HOMOG_GRID, "homog_deg"),
                            ("ibr_share", ("SG", "IBR"), "local"), ("margin", RHO_GRID, "rho")):
        print(f"=== {axis} (one at a time from base) ===", flush=True)
        out["oat"][axis] = []
        for v in grid:
            cfg = dict(BASE, **{key: v})
            r = cell(cfg, commit, **kw)
            out["oat"][axis].append(r)
            print(line(f"{axis} = {v}", r), flush=True)
            json.dump(out, open(os.path.join(OUT, "tac25_map.json"), "w"), indent=1, default=str)

    out["runtime_s"] = float(time.time() - t0)
    json.dump(out, open(os.path.join(OUT, "tac25_map.json"), "w"), indent=1, default=str)
    print(f"\nsaved {os.path.join(OUT, 'tac25_map.json')}  [{out['runtime_s']:.0f}s]")
