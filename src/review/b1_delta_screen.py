"""B1 of the bridge review (review/bridge/LEAD_REVIEW.md, section B): the delta-footprint screening.

QUESTION  In the study model of the CIGRE MV feeder (ibr_study: the characterised grid-following inverters), how
large must a negative-sequence injection delta at one inverter be before the relay's own measurement separates an
in-zone fault from the out-of-zone faults that look like it?  A screening, not the design (bridge milestone M3):
it is optimistic for delta in three ways, so its numbers are what the design would need at least.  Stop rule
(LEAD_REVIEW.md D): if the need exceeds 1.2 pu, the inverter's whole current, in every cell holding >= 5 EMT
in-zone faults, the delta design is dropped on this grid.

OBSERVABLE (LEAD_REVIEW.md, conflicts 4)  The relay's post-fault V0, V1, V2, I0, I1, I2 and pre-fault V1, I1:
16 reals, per unit (ub/sqrt3 and the 433 A of the inverters' 15 MVA rating), rotated by the pre-fault V1, in the
infinity norm.  An error box of eps per real channel on each measurement means a pair is separated when the two
observables differ by more than 2 eps in some channel.  eps = 0.01 (instrument class) is the headline; model error
(B2, not measured yet) only adds to it.

SCENARIOS  in: own line at m = 0.70 and 0.85 from the relay, lg / ll / llg / 3ph, R_f on a grid inside each band
of cm.RF_BINS.  out: the remote bus and 5 / 10 / 20 % into each line beyond it, the same four types, R_f 0-60 ohm
(0.25 ohm steps below 10 ohm, 0.5 above).  Both: three operating points (the EMT's own loads and grid set point in
the simulations at the 10th / 50th / 90th percentile of total load), solid and resistive grounding (the EMT's
median resistances; resonant is left out, the model has no cable C0), and two negative-sequence admittances for
both inverters (the characterised secant, about 2.4 pu at -72 deg, and the low-u2 value, about 11 pu at 0 deg;
review/bridge/SPECIALIST_REPORTS.md F5).  A pair shares operating point and grounding (the relay sees the pre-fault
state, the neutral is a property of the network) but not y2, which the relay cannot know.

DELTA  Added to the injecting inverter's negative-sequence current after its limiter, in pu of its rating, network
phase ("additive mode": the inverter's own -y2 V2 response still acts, so part of delta is shunted).  The inverter
at bus 3 for R1, R2 and R4, at bus 14 for R3 (the two feeders are decoupled in the model).  The response is not
linear in delta (limiter and reactive-current regimes switch; separation is not even monotone in |delta|), so the
model is solved directly on a grid of |delta| in MAGS and 12 angles, and every "need" is the smallest |delta| on
that grid that separates.

PAIRS  An in-zone scenario's confusers are the out-of-zone scenarios within 2 eps of it at delta = 0, plus, in
each (y2, type, place) family that has one, the WINDOW neighbours on either side in R_f (delta moves the in-zone
point, and the nearest R_f moves with it).  Optimistic for delta because (1) pairs separated at delta = 0 are
assumed to stay separated, (2) each in-zone fault may use its own angle unless stated, (3) eps is instrument only.

    python src/review/b1_delta_screen.py [cigre_R1 ...]      -> results/cigremv/b1_delta_screen.json
"""
import os, sys, json, glob, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import setting_study as ss
from review import ibr_study as ib
import real_zone

UB = 20e3
OUT = os.path.join(cm.ROOT, "results", "cigremv", "b1_delta_screen.json")
RELAYS = ("cigre_R1", "cigre_R2", "cigre_R3", "cigre_R4")
INJECTOR = {"cigre_R1": "MainBus3", "cigre_R2": "MainBus3", "cigre_R3": "MainBus14", "cigre_R4": "MainBus3"}
FTYPES = ("lg", "ll", "llg", "3ph")
M_IN = (0.70, 0.85)
RF_IN = {"<5": (0.5, 2.0, 4.5), "5-15": (6.0, 8.5, 11.0, 14.0), "15-40": (17.5, 22.5, 27.5, 32.5, 37.5), ">40": (42.5, 47.5)}
RF_OUT = np.concatenate([np.arange(0.0, 10.0, 0.25), np.arange(10.0, 60.001, 0.5)])
BEYOND_AT = (0.05, 0.10, 0.20)
LOAD_PCT = (10, 50, 90)
EPS = (0.005, 0.01, 0.02)
EPS_HEAD = 0.01
MAGS = (0.2, 0.4, 0.7, 1.2, 2.0, 3.0)            # pu of the injecting inverter's rating
ANGS = np.radians(np.arange(0, 360, 30))
WINDOW = 4
Y2_LOW = complex(11.0, 0.0)
DAMPING = {"secant": ((0.5, 400), (0.2, 1500), (0.08, 4000)), "low_u2": ((0.2, 1500), (0.08, 4000))}
MIN_EMT = 5
WORKERS = 10

# ------------------------------------------------------------------ delta, added after the inverter's limiter
_STATE = dict(delta=0j, k=None)
_orig_currents = ib._ibr_currents


def _currents_with_delta(ibrs, V1, V2, J1, pre=None):
    o1, o2 = _orig_currents(ibrs, V1, V2, J1, pre)
    if pre is not None and _STATE["k"] is not None and _STATE["delta"] != 0:
        o2 = o2.copy()
        o2[_STATE["k"]] += _STATE["delta"] * ibrs[_STATE["k"]]["i_base"]
    return o1, o2


ib._ibr_currents = _currents_with_delta


def observe(net, ibrs, y2, rb, line, where, ft, rf, m, delta, k):
    """16-real observable (module docstring) and whether the fixed point converged. The characterised damping
    diverges with the low-u2 admittance (loop gain |y2 Z2| about 3), so the solve retries with heavier damping."""
    _STATE["delta"], _STATE["k"] = complex(delta), k
    for damp, it in DAMPING[y2]:
        ib.DAMP, ib.MAX_IT = damp, it
        vs, is_, vp, ip, info = ib.solve_fault(net, ibrs, rb, line, where, ft, rf, m, return_ibr=True)
        ok = info["iterations"] < it
        if ok:
            break
    _STATE["delta"] = 0j
    vb, ibase = UB / np.sqrt(3), ibrs[k]["i_base"]
    rot = np.conj(vp[1]) / abs(vp[1])
    z = np.concatenate([vs / vb, is_ / ibase, [vp[1] / vb, ip[1] / ibase]]) * rot
    return np.concatenate([z.real, z.imag]), ok


_CTX = {}


def _init(ctx):
    _CTX.update(ctx)


def _eval(job):
    """One scenario at a list of deltas, in a worker: (Y (n_delta, 16), converged (n_delta,))."""
    s, deltas = job
    c = _CTX
    res = [observe(c["nets"][(s["g"], s["op"])], c["ibr_sets"][s["y2"]], s["y2"], c["rb"], c["line"], s["where"], s["ft"],
                   s["rf"], s["m"], d, c["k"]) for d in deltas]
    return np.array([r[0] for r in res]), np.array([r[1] for r in res])


# ------------------------------------------------------------------ grid, operating points, EMT counts
def grid_data():
    from evemt import load_cache
    path = [h for d in cm.CACHE_DIRS for h in sorted(glob.glob(os.path.join(d, "adapt_grid-CigreMVGrid*_cache.meta.npz")))][0]
    C = load_cache(path)
    return C["labels"], C["graph"]


def operating_points(L, G):
    """(label, loads bus -> (P MW, Q MVAr), grid set point, total MW) of the simulations at the LOAD_PCT percentiles of total load."""
    lb = {}
    for n, a in G.nodes(data=True):
        if str(n).startswith("MainBus"):
            for key in a:
                if key.startswith("Ld") and key.endswith("_param_dict") and not key.endswith("_typ_param_dict"):
                    lb[key[:-len("_param_dict")]] = str(n)
    lds = [ld for ld in lb if f"loads/{ld}/load_p" in L]
    total = np.sum([L[f"loads/{ld}/load_p"].to_numpy(float) for ld in lds], axis=0)
    out = []
    for p in LOAD_PCT:
        i = int(np.argmin(np.abs(total - np.percentile(total, p))))
        loads = {}
        for ld in lds:
            P, Q = loads.get(lb[ld], (0.0, 0.0))
            loads[lb[ld]] = (P + float(L[f"loads/{ld}/load_p"].iloc[i]), Q + float(L[f"loads/{ld}/load_q"].iloc[i]))
        usetp = float(L["ExtGrid/usetp"].iloc[i]) if "ExtGrid/usetp" in L else 1.0
        out.append((f"p{p}", loads, usetp, float(total[i])))
    return out


def groundings(L):
    kind = L["grounding/grnd_type"].astype(str).to_numpy().astype(str)
    return [(g, float(np.median(L[col].to_numpy(float)[kind == g])))
            for g, col in (("solid", "grounding/solid_ground_resistance"), ("resistive", "grounding/resistive_ground_resistance"))]


def emt_counts(L, G, cfg):
    """EMT in-zone faults (own line, <= 85 % from the relay) per (fault type, R_f band)."""
    et = L["events/event_type"].astype(str).to_numpy().astype(str)
    tgt = L["events/event_target"].astype(str).to_numpy().astype(str)
    loc = L["events/event_flt_target_line_location"].to_numpy(float)
    rf = L["events/event_flt_shc_resistance"].to_numpy(float)
    ends = {k: (u, v) for u, v, k in G.edges(keys=True)}
    u, _ = ends[cfg["line"]]
    loc_rel = np.where(cfg["relay_bus"] == u, loc, 100.0 - loc)
    ft = np.array([ss.ETYPE.get(e, "") for e in et])
    pos = (tgt == cfg["line"]) & (loc_rel <= 85.0) & (ft != "")
    band = cm.rf_bin_of(rf)
    return {f"{t}|{b}": int((pos & (ft == t) & (band == b)).sum()) for t in FTYPES for b in RF_IN}


# ------------------------------------------------------------------ the screen
def _need(sep):
    """sep (..., n_mag, n_ang) bool -> smallest |delta| in MAGS separating at some angle (inf if none)."""
    ok = sep.any(-1)
    first = np.where(ok.any(-1), ok.argmax(-1), -1)
    return np.where(first >= 0, np.asarray(MAGS)[np.maximum(first, 0)], np.inf)


def _num(x):
    return None if x is None or not np.isfinite(x) else float(x)


def screen(name, L, G, workers=WORKERS, verbose=True, scenarios=None, ftypes=FTYPES):
    """scenarios: optional callable (cfg, nets, ibr_sets, lines) -> (ins, outs) replacing the reach hypotheses below
    (b1_direction_screen.py); each out scenario carries 'fam' (its R_f family) and 'ri' (its index in RF_OUT).
    ftypes: the fault types the cells are reported for."""
    t0 = time.time()
    cfg = real_zone.CONFIGS[name]
    rb, line, remote = cfg["relay_bus"], cfg["line"], cfg["remote_bus"]
    ibrs0 = ib.inverters_from_graph(G, UB, ib.load_characterisation())
    k = [g["bus"] for g in ibrs0].index(INJECTOR[name])
    Y2 = {"secant": [g["y2"] for g in ibrs0], "low_u2": [Y2_LOW] * len(ibrs0)}
    ibr_sets = {y: [dict(g, y2=v) for g, v in zip(ibrs0, vals)] for y, vals in Y2.items()}
    ops, grs = operating_points(L, G), groundings(L)
    nets = {}
    for g, r in grs:
        base = ss.build(G, ub=UB, grounding=(g, r), open_ends=cfg.get("open_line_ends"))
        for lab, loads, usetp, _ in ops:
            nets[(g, lab)] = ib.with_operating_point(base, UB, loads, usetp)
    lines = next(iter(nets.values()))[1]
    u_own = lines[line][0]
    places = [(("bus", remote), 0.0, "remote bus")]
    for bl in cfg["beyond"]:
        ub_, vb_ = lines[bl][:2]
        if remote not in (ub_, vb_):
            raise ValueError(f"{bl} does not start at {remote}")
        places += [(("line", bl), x if ub_ == remote else 1 - x, f"{bl} {int(round(x * 100))} %") for x in BEYOND_AT]

    ins, outs = [], []
    for (g, lab) in (nets if scenarios is None else ()):
        for y2 in ibr_sets:
            for ft in FTYPES:
                for mrel in M_IN:
                    for band, rfs in RF_IN.items():
                        ins += [dict(g=g, op=lab, y2=y2, ft=ft, m_rel=mrel, band=band, rf=rf, where=("line", line),
                                     m=mrel if u_own == rb else 1 - mrel) for rf in rfs]
                for pi, (where, m, place) in enumerate(places):
                    outs += [dict(g=g, op=lab, y2=y2, ft=ft, where=where, m=m, place=place, rf=float(rf), ri=j,
                                  fam=f"{g}|{lab}|{y2}|{ft}|{pi}") for j, rf in enumerate(RF_OUT)]
    if scenarios is not None:
        ins, outs = scenarios(cfg, nets, ibr_sets, lines)
    from multiprocessing import Pool
    pool = Pool(workers, initializer=_init, initargs=(dict(nets=nets, ibr_sets=ibr_sets, rb=rb, line=line, k=k),))
    solve = lambda scns, deltas: pool.map(_eval, [(s, deltas) for s in scns], chunksize=max(1, len(scns) // (8 * workers)))
    Yi, ci = (np.array(a)[:, 0] for a in zip(*solve(ins, [0j])))
    Yo, co = (np.array(a)[:, 0] for a in zip(*solve(outs, [0j])))
    if verbose:
        print(f"[{name}] delta = 0: {len(ins)} in, {len(outs)} out; unconverged {int((~ci).sum())} / {int((~co).sum())} [{time.time() - t0:.0f}s]", flush=True)

    # confusers of every in-zone scenario at eps_head (plus R_f neighbours in their family)
    key_i = np.array([f"{s['g']}|{s['op']}" for s in ins]); key_o = np.array([f"{s['g']}|{s['op']}" for s in outs])
    fam = np.array([s["fam"] for s in outs]); ri = np.array([s["ri"] for s in outs])
    fam_index = {}
    for j, fm in enumerate(fam):
        fam_index.setdefault(fm, {})[ri[j]] = j
    d0_all, partners = {}, {}
    for i in range(len(ins)):
        if not ci[i]:
            continue
        same = np.where((key_o == key_i[i]) & co)[0]
        d0 = np.abs(Yo[same] - Yi[i]).max(1)
        d0_all[i] = float(d0.min()) if len(d0) else np.inf
        close = same[d0 < 2 * EPS_HEAD]
        keep = set(close.tolist())
        for fm in set(fam[close]):
            members = same[fam[same] == fm]
            best = members[np.argmin(np.abs(Yo[members] - Yi[i]).max(1))]
            for r_ in range(ri[best] - WINDOW, ri[best] + WINDOW + 1):
                j = fam_index[fm].get(r_)
                if j is not None and co[j]:
                    keep.add(j)
        partners[i] = np.array(sorted(keep), int)
    inv_in = [i for i in partners if len(partners[i])]
    inv_out = sorted(set(np.concatenate([partners[i] for i in inv_in]).tolist())) if inv_in else []
    if verbose:
        print(f"[{name}] delta grid on {len(inv_in)} in + {len(inv_out)} out scenarios [{time.time() - t0:.0f}s]", flush=True)
    D = [MAGS[a] * np.exp(1j * ANGS[b]) for a in range(len(MAGS)) for b in range(len(ANGS))]

    def on_grid(scns):
        out = []
        for Y, ok in solve(scns, D):
            Y = np.where(ok[:, None], Y, np.nan)
            out.append(Y.reshape(len(MAGS), len(ANGS), 16))
        return out
    Gi = dict(zip(inv_in, on_grid([ins[i] for i in inv_in])))
    Go = dict(zip(inv_out, on_grid([outs[j] for j in inv_out])))
    pool.close(); pool.join()
    if verbose:
        print(f"[{name}] delta grid solved [{time.time() - t0:.0f}s]", flush=True)

    # needs at eps_head: per pair, per in-zone scenario (one angle), per cell (one angle)
    sep_scn, need_pair, need_scn, bind = {}, {}, {}, {}
    for i in inv_in:
        Yp = np.stack([Go[j] for j in partners[i]])                                  # (P, mag, ang, 16)
        sep = np.nanmax(np.abs(Yp - Gi[i][None]), -1) >= 2 * EPS_HEAD                # nan (unconverged) counts as not separated
        sep_scn[i] = sep.all(0)                                                      # (mag, ang): all partners separated
        n_p = _need(sep)
        need_pair[i] = n_p
        need_scn[i] = float(_need(sep_scn[i][None])[0])
        jb = int(np.argmax(n_p))
        bind[i] = (float(n_p[jb]), int(partners[i][jb]))
    cells, counts = {}, emt_counts(L, G, cfg)
    for ft in ftypes:
        for band in RF_IN:
            idx = [i for i in range(len(ins)) if ci[i] and ins[i]["ft"] == ft and ins[i]["band"] == band]
            amb = {f"eps={e}": float(np.mean([d0_all[i] < 2 * e for i in idx])) for e in EPS} if idx else None
            ns = np.array([need_scn.get(i, 0.0) for i in idx])
            lb = max([float(need_pair[i].max()) for i in idx if i in need_pair] or [0.0])
            cell_sep = np.ones((len(MAGS), len(ANGS)), bool)
            for i in idx:
                if i in sep_scn:
                    cell_sep &= sep_scn[i]
            cell = dict(emt_in_zone=counts[f"{ft}|{band}"], n_model=len(idx), ambiguous_at_delta0=amb,
                        need_lower_bound_pu=_num(lb) if idx else None, need_exceeds_grid=bool(idx) and not np.isfinite(lb),
                        median_one_angle_per_fault_pu=_num(float(np.median(ns))) if idx else None,
                        share_le_0p4=float(np.mean(ns <= 0.4)) if idx else None,
                        share_le_1p2=float(np.mean(ns <= 1.2)) if idx else None,
                        one_angle_for_cell_pu=(_num(float(_need(cell_sep[None])[0])) if any(i in sep_scn for i in idx) else 0.0) if idx else None)
            hard = [i for i in idx if i in bind]
            if hard:
                i = max(hard, key=lambda q: bind[q][0])
                si, so = ins[i], outs[bind[i][1]]
                cell["binding_pair"] = dict(in_zone={q: si[q] for q in ("g", "op", "y2", "ft", "m_rel", "rf")},
                                            out_of_zone={q: so[q] for q in ("y2", "ft", "place", "rf")},
                                            distance_at_delta0=float(np.abs(Yi[i] - Yo[bind[i][1]]).max()),
                                            need_pu=_num(bind[i][0]))
            cells[f"{ft}|{band}"] = cell
    big = [c for c in cells.values() if c["emt_in_zone"] >= MIN_EMT and c["n_model"]]
    lbv = lambda c: np.inf if c["need_exceeds_grid"] else c["need_lower_bound_pu"]
    verdict = dict(cells_with_min_emt=len(big), cells_need_above_1p2=sum(lbv(c) > 1.2 for c in big),
                   emt_in_zone_in_those_cells=sum(c["emt_in_zone"] for c in big),
                   emt_in_zone_in_cells_need_above_1p2=sum(c["emt_in_zone"] for c in big if lbv(c) > 1.2),
                   stop_rule_met=bool(big) and all(lbv(c) > 1.2 for c in big),
                   emt_weighted_share_le_0p4=float(sum(c["emt_in_zone"] * c["share_le_0p4"] for c in big) / max(1, sum(c["emt_in_zone"] for c in big))),
                   emt_weighted_share_le_1p2=float(sum(c["emt_in_zone"] * c["share_le_1p2"] for c in big) / max(1, sum(c["emt_in_zone"] for c in big))))
    if verbose:
        print(f"[{name}] done [{time.time() - t0:.0f}s] {verdict}", flush=True)
    return dict(relay=name, relay_bus=rb, line=line, remote_bus=remote, injector=INJECTOR[name],
                operating_points=[dict(label=o[0], total_load_mw=o[3], usetp=o[2]) for o in ops],
                groundings=[dict(kind=g, r_ohm=r) for g, r in grs], y2={y: [[v.real, v.imag] for v in vals] for y, vals in Y2.items()},
                n_in=len(ins), n_out=len(outs), unconverged_in=int((~ci).sum()), unconverged_out=int((~co).sum()),
                delta_grid_in=len(inv_in), delta_grid_out=len(inv_out),
                cells=cells, verdict_eps_0p01=verdict, runtime_s=time.time() - t0)


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)                   # all-nan slices of unconverged solves
    names = [a for a in sys.argv[1:] if a in RELAYS] or list(RELAYS)
    L, G = grid_data()
    res = [screen(n, L, G) for n in names]
    out = dict(script="b1_delta_screen.py", commit=cm.git_commit(), eps=list(EPS), eps_headline=EPS_HEAD,
               note="need fields are the smallest |delta| on the grid that separates; null = none up to the largest magnitude",
               m_in=list(M_IN), rf_in=RF_IN, rf_out=[float(RF_OUT[0]), float(RF_OUT[-1]), len(RF_OUT)], beyond_at=list(BEYOND_AT),
               delta_magnitudes_pu=list(MAGS), delta_angles_deg=[float(a) for a in np.degrees(ANGS)], rf_window=WINDOW,
               min_emt_per_cell=MIN_EMT, relays={r["relay"]: r for r in res})
    if os.path.exists(OUT) and len(names) < len(RELAYS):
        prev = json.load(open(OUT, encoding="utf-8"))
        prev["relays"].update(out["relays"]); out["relays"] = prev["relays"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    print("saved", OUT)
