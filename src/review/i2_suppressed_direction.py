"""Direction with inverters that suppress negative-sequence current: does it break, and how small a designed
injection repairs it? The one place left on the CIGRE MV feeder where Taylor's auxiliary signal could add value.

Why: at the inverter buses the passive superimposed elements settle direction on the EMT data
(opoku_direction.py) because the recorded inverters respond in negative sequence, roughly like IEEE 2800's
"I2 leads V2 by 90 degrees" (characterised secant y2 = 2.3-2.5 pu at -72 deg). Inverters with coupled sequence
control output balanced current, I2 = 0 (PES-TR81, Haddadi et al. 2021), and then there is little for a
negative-sequence element to measure. No public EMT record has such inverters, so this is a model study
(ibr_study, the B1 network, operating points and groundings).

FAULTS  unbalanced (lg, ll, llg). forward: on the protected line at 10, 50 and 85 % from the relay; reverse: at
the relay bus and 5, 20 and 50 % into each line behind it. R_f on the B1 grid, three operating points, solid and
resistive grounding.
LAWS for the inverters' negative-sequence current:
  recorded        the characterised secant y2 (the control case: should match the EMT result, no errors)
  low_u2          the low-u2 admittance, 11 pu at 0 deg
  suppressed      I2 = 0 (coupled control)
  IEEE 2800 k     I2 = j k V2 (leads V2 by 90 deg), k = 2, 6: the proportional rule of the standard
  fixed delta     suppressed, plus a fixed-magnitude delta from the relay's own feeder inverter, in its V1 frame
                  (what a PLL-referenced controller can do), |delta| = 0.05-0.4 pu, 12 angles
  delta lead V2   suppressed, plus a fixed-magnitude delta leading the inverter's V2 by 90 deg (Yang/Popov style).
                  Not defined as V2 -> 0: the fault solution does not converge in up to a fifth of the faults, those
                  with the smallest V2, so its rates (over converged faults) are optimistic
  capped V2       the same, continuous: delta = r j V2 / max(|V2|, vmin), proportional (k = r / vmin) below vmin and
                  r above it; converges everywhere
The injection is added after the limiter (headroom is not checked here; 0.4 pu fits at a design angle in most
faults, results/CIGREMV.md §3).
ELEMENTS at the relay (model phasors, pre-fault reference):
  dY2   arg(dI2/dV2) in (45, 225) deg, enabled when |I2| >= 0.1 |I1| (Opoku et al. 2025)
  dY1   the same test on dI1/dV1 where dY2 is not enabled, |dV1| >= 5 % (opoku_direction.py)
  combined "dY2 when enabled, else dY1"; and dY1 alone, the passive positive-sequence fallback.
A forward fault must be called forward, a reverse fault must not. Angle margins to the sector edges are kept
so a decision that is right by a hair can be seen.

    python src/review/i2_suppressed_direction.py [cigre_R1 ...]   -> results/cigremv/i2_suppressed_direction.json
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import setting_study as ss
from review import ibr_study as ib
from review import b1_delta_screen as b1          # network, operating points, groundings, damping (and its own no-op delta patch)
import real_zone

OUT = os.path.join(cm.ROOT, "results", "cigremv", "i2_suppressed_direction.json")
RELAYS = ("cigre_R1", "cigre_R2", "cigre_R3", "cigre_R4")
FTYPES = ("lg", "ll", "llg")
M_FWD = (0.10, 0.50, 0.85)
BEHIND_AT = (0.05, 0.20, 0.50)
RF = tuple(r for rs in b1.RF_IN.values() for r in rs)
R_DELTA = (0.05, 0.1, 0.2, 0.4)
V2_MIN = (0.02, 0.05)                                 # pu, the capped law's knee
ANGS = tuple(range(0, 360, 30))
PHI, I2_I1_MIN, DV1_MIN = 45.0, 0.1, 0.05
WORKERS = 10

# ------------------------------------------------------------------ injection laws, added after the limiter
_LAW = dict(kind=None, r=0.0, ang=0.0, k=None)
_prev_currents = ib._ibr_currents


def _currents_with_law(ibrs, V1, V2, J1, pre=None):
    o1, o2 = _prev_currents(ibrs, V1, V2, J1, pre)
    k = _LAW["k"]
    if pre is None or k is None or _LAW["kind"] is None or _LAW["r"] == 0:
        return o1, o2
    g = ibrs[k]
    o2 = o2.copy()
    if _LAW["kind"] == "v1":
        vt1 = V1[k] + g["z_reactor"] * J1[k]
        o2[k] += _LAW["r"] * np.exp(1j * np.radians(_LAW["ang"])) * (vt1 / abs(vt1)) * g["i_base"]
    elif _LAW["kind"] == "v2lead" and abs(V2[k]) > 1e-6 * g["v_base"]:
        o2[k] += _LAW["r"] * 1j * (V2[k] / abs(V2[k])) * g["i_base"]
    elif _LAW["kind"] == "v2cap":                     # ang carries vmin (pu)
        o2[k] += _LAW["r"] * 1j * V2[k] / max(abs(V2[k]), _LAW["ang"] * g["v_base"]) * g["i_base"]
    return o1, o2


ib._ibr_currents = _currents_with_law


def laws():
    out = [("recorded", None, None, 0, 0), ("low_u2", "low", None, 0, 0), ("suppressed", 0, None, 0, 0),
           ("IEEE 2800 k=2", -2j, None, 0, 0), ("IEEE 2800 k=6", -6j, None, 0, 0)]
    out += [(f"fixed delta {r} pu @ {a} deg (V1 frame)", 0, "v1", r, a) for r in R_DELTA for a in ANGS]
    out += [(f"delta {r} pu leading V2 by 90 deg", 0, "v2lead", r, 0) for r in R_DELTA]
    out += [(f"capped {r} pu leading V2, k={r / vm:g} below {vm} pu", 0, "v2cap", r, vm) for r in R_DELTA for vm in V2_MIN]
    return out


def solve(net, ibrs, rb, line, s, law, k):
    _, y2, kind, r, a = law
    if y2 is None:
        ibrs_l = ibrs
    elif y2 == "low":
        ibrs_l = [dict(g, y2=b1.Y2_LOW) for g in ibrs]
    else:
        ibrs_l = [dict(g, y2=complex(y2)) for g in ibrs]
    _LAW.update(kind=kind, r=r, ang=a, k=k)
    damp = b1.DAMPING["low_u2" if y2 == "low" else "secant"]
    for d, it in damp:
        ib.DAMP, ib.MAX_IT = d, it
        vs, is_, vp, ip, info = ib.solve_fault(net, ibrs_l, rb, line, s["where"], s["ft"], s["rf"], s["m"], return_ibr=True)
        if info["iterations"] < it:
            break
    _LAW.update(kind=None, r=0.0)
    return vs, is_, vp, ip, info["iterations"] < it


_CTX = {}


def _init(ctx):
    _CTX.update(ctx)


def _eval(job):
    s, law = job
    c = _CTX
    vs, is_, vp, ip, ok = solve(c["nets"][(s["g"], s["op"])], c["ibrs"], c["rb"], c["line"], s, law, c["k"])
    return np.array([vs[1], vs[2], is_[1], is_[2], vp[1], vp[2], ip[1], ip[2]]), ok


def sector(y):
    a = np.degrees(np.angle(y)) % 360
    return (a > PHI) & (a < 180 + PHI), np.minimum(np.abs(a - PHI), np.abs(a - (180 + PHI)))


def decide(P):
    v1, v2, i1, i2, v1p, v2p, i1p, i2p = P.T
    with np.errstate(divide="ignore", invalid="ignore"):
        f2, m2 = sector((i2 - i2p) / (v2 - v2p))
        f1, m1 = sector((i1 - i1p) / (v1 - v1p))
    en2 = np.abs(i2) >= I2_I1_MIN * np.abs(i1)
    vn = b1.UB / np.sqrt(3)
    pick1 = np.abs(v1 - v1p) >= DV1_MIN * vn
    return dict(dY2=en2 & f2, dY1=pick1 & f1, combined=(en2 & f2) | (~en2 & pick1 & f1)), en2, np.where(en2, m2, m1)


def screen(name, L, G, workers=WORKERS):
    t0 = time.time()
    cfg = real_zone.CONFIGS[name]
    rb, line = cfg["relay_bus"], cfg["line"]
    ibrs = ib.inverters_from_graph(G, b1.UB, ib.load_characterisation())
    k = [g["bus"] for g in ibrs].index(b1.INJECTOR[name])
    ops, grs = b1.operating_points(L, G), b1.groundings(L)
    nets = {}
    for g, r in grs:
        base = ss.build(G, ub=b1.UB, grounding=(g, r), open_ends=cfg.get("open_line_ends"))
        for lab, loads, usetp, _ in ops:
            nets[(g, lab)] = ib.with_operating_point(base, b1.UB, loads, usetp)
    lines = next(iter(nets.values()))[1]
    u_own = lines[line][0]
    behind = [kk for kk, (u, v, *_) in lines.items() if rb in (u, v) and kk.startswith("MainLn") and kk not in (line, cfg.get("parallel"))]
    places = [(("bus", rb), 0.0, "relay bus")] + [(("line", bl), x if lines[bl][0] == rb else 1 - x, f"{bl} {int(round(x * 100))} %")
                                                   for bl in behind for x in BEHIND_AT]
    scn = []
    for (g, lab) in nets:
        for ft in FTYPES:
            for rf in RF:
                scn += [dict(g=g, op=lab, ft=ft, rf=rf, where=("line", line), m=mr if u_own == rb else 1 - mr, fwd=True, place=f"own line {int(mr * 100)} %") for mr in M_FWD]
                scn += [dict(g=g, op=lab, ft=ft, rf=rf, where=w, m=m, fwd=False, place=pl) for w, m, pl in places]
    fwd = np.array([s["fwd"] for s in scn])
    from multiprocessing import Pool
    res = {}
    with Pool(workers, initializer=_init, initargs=(dict(nets=nets, ibrs=ibrs, rb=rb, line=line, k=k),)) as pool:
        for law in laws():
            out = pool.map(_eval, [(s, law) for s in scn], chunksize=max(1, len(scn) // (8 * workers)))
            P = np.array([o[0] for o in out]); ok = np.array([o[1] for o in out])
            dec, en2, margin = decide(P)
            v2 = np.abs(P[:, 1]) / (b1.UB / np.sqrt(3))
            r = dict(converged=float(ok.mean()), dY2_enabled_forward=float(en2[fwd & ok].mean()), dY2_enabled_reverse=float(en2[~fwd & ok].mean()),
                     relay_v2_pu_median=dict(converged=float(np.median(v2[ok])), not_converged=float(np.median(v2[~ok])) if (~ok).any() else None))
            for el, d in dec.items():
                r[el] = dict(forward_called_forward=float(d[fwd & ok].mean()), reverse_called_forward=float(d[~fwd & ok].mean()),
                             by_type={ft: dict(fwd=float(d[fwd & ok & (np.array([s["ft"] for s in scn]) == ft)].mean()),
                                               rev=float(d[~fwd & ok & (np.array([s["ft"] for s in scn]) == ft)].mean())) for ft in FTYPES})
            correct = np.where(fwd, dec["combined"], ~dec["combined"])
            r["combined"]["share_correct_with_margin_lt_10deg"] = float(np.mean(correct[ok] & (margin[ok] < 10)))
            res[law[0]] = r
    print(f"[{name}] {len(scn)} faults x {len(laws())} laws [{time.time() - t0:.0f}s]", flush=True)
    for lab in ("recorded", "low_u2", "suppressed", "IEEE 2800 k=2", "IEEE 2800 k=6"):
        c = res[lab]["combined"]; d2 = res[lab]["dY2"]
        print(f"   {lab:14s} combined fwd {c['forward_called_forward']:.3f} rev {c['reverse_called_forward']:.3f} | dY2 fwd {d2['forward_called_forward']:.3f} rev {d2['reverse_called_forward']:.3f} "
              f"| dY2 enabled fwd {res[lab]['dY2_enabled_forward']:.2f}", flush=True)
    for rr in R_DELTA:
        best = max((a for a in ANGS), key=lambda a: min(res[f"fixed delta {rr} pu @ {a} deg (V1 frame)"]["dY2"]["forward_called_forward"],
                                                        1 - res[f"fixed delta {rr} pu @ {a} deg (V1 frame)"]["dY2"]["reverse_called_forward"]))
        c = res[f"fixed delta {rr} pu @ {best} deg (V1 frame)"]; v = res[f"delta {rr} pu leading V2 by 90 deg"]
        print(f"   delta {rr:4} pu: best V1-frame angle {best:3d} -> dY2 fwd {c['dY2']['forward_called_forward']:.3f} rev {c['dY2']['reverse_called_forward']:.3f}"
              f" | lead V2: dY2 fwd {v['dY2']['forward_called_forward']:.3f} rev {v['dY2']['reverse_called_forward']:.3f} (converged {v['converged']:.3f})", flush=True)
        for vm in V2_MIN:
            q = res[f"capped {rr} pu leading V2, k={rr / vm:g} below {vm} pu"]
            print(f"      capped, k={rr / vm:g} below {vm} pu: combined fwd {q['combined']['forward_called_forward']:.3f} rev {q['combined']['reverse_called_forward']:.3f}"
                  f" (converged {q['converged']:.3f})", flush=True)
    return dict(relay=name, injector=b1.INJECTOR[name], n_faults=len(scn), n_forward=int(fwd.sum()), places_reverse=[p[2] for p in places], laws=res,
                runtime_s=time.time() - t0)


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    names = [a for a in sys.argv[1:] if a in RELAYS] or list(RELAYS)
    L, G = b1.grid_data()
    out = dict(script="i2_suppressed_direction.py", commit=cm.git_commit(), ftypes=list(FTYPES), m_forward=list(M_FWD), behind_at=list(BEHIND_AT),
               rf=list(RF), r_delta=list(R_DELTA), angles_deg=list(ANGS), phi_deg=PHI, i2_over_i1_min=I2_I1_MIN, dv1_min=DV1_MIN,
               relays={n: screen(n, L, G) for n in names})
    if os.path.exists(OUT) and len(names) < len(RELAYS):
        prev = json.load(open(OUT, encoding="utf-8")); prev["relays"].update(out["relays"]); out["relays"] = prev["relays"]
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    print("saved", OUT)
