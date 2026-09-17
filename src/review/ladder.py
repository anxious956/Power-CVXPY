"""Q-fair: the conventional baseline ladder, one frozen element specification per rung, evaluated once on
every relay and decision time, on exactly the folds of zone_cv.py for the tuned rungs.

Settings come from line data and the short-circuit / load-flow study model built from the grid graph
(src/review/setting_study.py). No EMT benchmark outcome is used to choose any setting.

FROZEN SPECIFICATION (written before evaluation; justification from relay practice)
-------------------------------------------------------------------------------
R0  repo rule            zone_model.phase_selected_reactance exactly as in real_ml.py: full-cycle DFT, no
                         DC-offset filter, faulted-phase selection, k0 compensation, trip if the smallest
                         released loop reactance with Im(Z) > 0 is below 0.85 X_line. The sign of X is its
                         only directional decision. Reproduced, not modified.
R1  + mimic filter       Same element, currents through a causal mimic (DC-offset removal) filter with the
                         line time constant X/(wR) before the DFT; half-cycle DFT at 10 ms. Every numerical
                         distance relay removes the decaying DC offset before phasor estimation (Phadke &
                         Thorp, Computer Relaying, ch. on digital filtering); a first-cycle DFT without it
                         produces the well-known transient overreach.
R2  + directional quad   R1 phasors and phase selection, plus:
                         - separate directional element: negative sequence (forward if
                           Re(V2 I2* e^{-j angle Z1L}) < 0) when |I2| >= 0.1 |dI1|, otherwise positive-sequence
                           memory polarised (forward if Re(V1_mem I1* e^{-j angle Z1L}) > 0);
                         - quadrilateral per released loop: reactance line X < X_set = 0.85 X_line (negative X
                           allowed), right blinder R < R_set, left blinder R > -0.25 R_set, directional sector
                           -15 deg <= angle(Z) <= 115 deg (vendor-default directional boundaries, e.g. ABB REL670
                           ArgDir 15 deg / ArgNegRes 115 deg, quoted from memory, not re-verified);
                         - minimum loop current 0.2 In, In = 1000 A (assumed CT primary rating);
                         - R_set from setting rules only (settings()): arc resistance (Mho formula) plus tower
                           footing for ground loops, capped by load encroachment at worst-case load (thermal
                           rating, 0.9 pu voltage, 30 deg maximum load angle, both directions) and by the
                           zone-1 R/X limit (R_set <= 4.5 X_set ground, 3 X_set phase loops). The cap is used
                           as the setting (maximum resistive coverage the rules allow).
R3  + I2-pol tilt line   R2 with the reactance line measured by a negative-sequence polarised reactance
                         element tilted by the non-homogeneity angle at the reach point from the setting
                         study's source impedances at both ends (two-source formula). Robustness: worst case
                         over source impedances +-25 % magnitude and +-7.5 deg angle at both ends.
R4  + study reach        R3 with X_set reduced to 0.9 x the smallest rung-3 reactance reading of any external
                         study fault (remote bus, first 20 % of each line leaving it, LG/LL/LLG/3PH) with
                         R_f in [0, R_arc + R_tower] that the rung-3 quadrilateral would otherwise pick up.
T1  tuned reach          One threshold on the R0 score at 5 % false trip on the training negatives of each fold.
T2  tuned quad           R2 with (X_set, R_set) chosen on each training fold: maximum dependability with
                         training false trip <= 5 %. Same folds and calibration data as the learned models.

    python src/review/ladder.py
"""
import sys, os, json, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import setting_study as ss
from review.zone_cv import splits, HELD

FAR = 0.05
IN_A = 1000.0
MIN_I_PEAK = 0.2 * IN_A * np.sqrt(2)        # phasor magnitudes are peak values
SECTOR = (-15.0, 115.0)
ARC_LENGTH_M = 3.0                           # assumption: ~ phase spacing / flashover path at 110 kV
R_TOWER = 10.0                               # assumption: tower footing resistance, ohm
I_THERMAL_PER_CONDUCTOR = 900.0              # assumption: 435/55 Al/St ~900 A (EN 50182 tables, not re-verified)
V_MIN_PU, LOAD_ANGLE_MAX = 0.9, 30.0
TIMES = ((10, "half"), (20, "full"), (30, "full"), (50, "full"))


# ------------------------------------------------------------------------------------ settings
def mho_arc(i_rms, length_m=ARC_LENGTH_M):
    return 28710.0 * length_m / i_rms ** 1.4


def tilt_from(zs, zr, zl, m=cm.REACH):
    return float(np.degrees(np.angle((zr + (1 - m) * zl) / (zs + zl + zr))))


def settings(R, name):
    cfg = R["cfg"]
    net = ss.build(R["graph"])
    rb = cm.RELAY_BUS[name]
    xl = R["z1L"].imag
    x_set = cm.REACH * xl
    # thermal rating: the graph has no ampacity; conductor '435/55 Aluminium/Steel 110 kV x2' read as a
    # 2-conductor bundle (assumption); both readings reported
    pcond = None
    for u, v, k, d in R["graph"].edges(keys=True, data=True):
        if k == cfg["line"]:
            pcond = d.get(f"{k}_typ_param_dict", {}).get("pcond_c")
    n_cond = 2 if pcond and "x2" in str(pcond) else 1
    i_th = I_THERMAL_PER_CONDUCTOR * n_cond
    zload_min = V_MIN_PU * 110e3 / np.sqrt(3) / i_th
    # arc current: study LG and LL fault at the reach point, total fault current, R_f = tower footing
    u, v, _, _ = net[1][cfg["line"]]
    m_line = cm.REACH if u == rb else 1 - cm.REACH
    def fault_current(ft, rf):
        """Total fault current (rms; the study EMF is the rms phase voltage) at the reach point."""
        main, lines, grids, loads = net
        Zb = {}
        for seq in (1, 2, 0):
            nodes, ix, Y, I = ss.ybus(main, lines, grids, loads, seq, cfg["line"], m_line)
            Zb[seq] = np.linalg.inv(Y)
            if seq == 1:
                vpre = Zb[1] @ I
        f = ix["F"]
        z1, z2, z0 = Zb[1][f, f], Zb[2][f, f], Zb[0][f, f]
        if ft == "lg":
            return abs(3 * vpre[f] / (z1 + z2 + z0 + 3 * rf))
        return abs(np.sqrt(3) * vpre[f] / (z1 + z2 + rf))
    i_lg = fault_current("lg", R_TOWER)
    i_ll = fault_current("ll", 0.0)
    r_arc_g, r_arc_p = mho_arc(i_lg), mho_arc(i_ll)
    k0 = (R["z0L"] - R["z1L"]) / (3 * R["z1L"])
    r_cov_g = 1.2 * (r_arc_g + R_TOWER) / abs(1 + k0)
    r_cov_p = 1.2 * r_arc_p / 2
    load_cap = 0.8 * zload_min
    r_set_g = min(load_cap, 4.5 * x_set)
    r_set_p = min(load_cap, 3.0 * x_set)
    zload_bench = ss.prefault_load_impedance(net, rb, cfg["line"])
    # tilt, nominal and over the source-impedance box
    zs, zr, _, zl = ss.source_impedances(net, rb, cfg["line"], 2)
    tilt_nom = tilt_from(zs, zr, zl)
    tilts = []
    for ms, as_, mr, ar in itertools.product(np.linspace(0.75, 1.25, 5), np.linspace(-7.5, 7.5, 5),
                                             np.linspace(0.75, 1.25, 5), np.linspace(-7.5, 7.5, 5)):
        tilts.append(tilt_from(zs * ms * np.exp(1j * np.deg2rad(as_)), zr * mr * np.exp(1j * np.deg2rad(ar)), zl))
    zs1, zr1, _, zl1 = ss.source_impedances(net, rb, cfg["line"], 1)
    S = dict(x_line=float(xl), x_set=float(x_set), n_conductors_assumed=n_cond, i_thermal_A=float(i_th),
             z_load_min=float(zload_min), load_cap=float(load_cap),
             i_fault_lg_reach_A=float(i_lg), i_fault_ll_reach_A=float(i_ll), r_arc_g=float(r_arc_g), r_arc_p=float(r_arc_p),
             r_cov_g=float(r_cov_g), r_cov_p=float(r_cov_p), r_set_g=float(r_set_g), r_set_p=float(r_set_p),
             coverage_ok_g=bool(r_set_g >= r_cov_g), coverage_ok_p=bool(r_set_p >= r_cov_p),
             r_set_if_0p7_benchmark_load=float(0.7 * abs(zload_bench)), z_load_benchmark=[zload_bench.real, zload_bench.imag],
             Z_S2=[zs.real, zs.imag], Z_R2=[zr.real, zr.imag], tilt_nominal_deg=tilt_nom,
             tilt1_nominal_deg=tilt_from(zs1, zr1, zl1),
             tilt_range_deg=[float(min(tilts)), float(max(tilts))], rf_design=float(r_arc_g + R_TOWER))
    S["x_set_study"], S["study_worst"] = study_reach(R, name, net, S)
    return S


# ------------------------------------------------------------------------------------ element
def evaluate_block(R, vpre, vpost, ipre, ipost, S, rung, tilt=None, x_set=None, r_set=None):
    """Trip decisions for a block of cases (arrays of sequence phasors)."""
    Lp = cm.loops(R, vpost, ipost, vpre, ipre)
    mask = cm.phase_selection(ipre, ipost)
    if rung in ("R0", "R1"):
        x, _ = cm.rule_reactance(Lp, mask)
        return x < (x_set if x_set is not None else S["x_set"]), x
    Z = Lp["V"] / (Lp["I"] + 1e-12)
    if rung in ("R3", "R4"):
        t2 = S["tilt_nominal_deg"] if tilt is None else tilt
        P = np.where(np.abs(Lp["I2pol"]) >= 0.05 * np.abs(Lp["I"]), Lp["I2pol"] * np.exp(-1j * np.deg2rad(t2)),
                     (Lp["I"] - Lp["Ipre"]) * np.exp(-1j * np.deg2rad(S["tilt1_nominal_deg"])))
        den = np.imag(R["z1L"] * Lp["I"] * np.conj(P))
        X = np.imag(Lp["V"] * np.conj(P)) / np.where(np.abs(den) > 1e-9, den, np.nan) * R["z1L"].imag
        X = np.where(np.isfinite(X), X, np.inf)
    else:
        X = Z.imag
    xs = x_set if x_set is not None else (S["x_set_study"] if rung == "R4" else S["x_set"])
    rg, rp = (r_set, r_set * S["r_set_p"] / S["r_set_g"]) if r_set is not None else (S["r_set_g"], S["r_set_p"])
    rset = np.array([rg, rg, rg, rp, rp, rp])[None, :]
    ang = np.degrees(np.angle(Z))
    phase_i = cm._phase_q(ipost)
    iloop = np.stack([np.abs(phase_i[:, 0]), np.abs(phase_i[:, 1]), np.abs(phase_i[:, 2]),
                      np.abs(phase_i[:, 0] - phase_i[:, 1]), np.abs(phase_i[:, 1] - phase_i[:, 2]),
                      np.abs(phase_i[:, 2] - phase_i[:, 0])], 1)
    fwd = directional(vpre, vpost, ipre, ipost, R["z1L"])
    inside = (mask & (X < xs) & (Z.real < rset) & (Z.real > -0.25 * rset) & (ang >= SECTOR[0]) & (ang <= SECTOR[1])
              & (iloop >= MIN_I_PEAK))
    trip = fwd & inside.any(1)
    score = np.where(mask & (Z.real < rset) & (Z.real > -0.25 * rset) & (ang >= SECTOR[0]) & (ang <= SECTOR[1])
                     & (iloop >= MIN_I_PEAK), X, np.inf).min(1)
    return trip, np.where(fwd, score, np.inf)


def directional(vpre, vpost, ipre, ipost, z1L, i2_frac=0.1):
    ang = np.exp(-1j * np.angle(z1L))
    v2, i2 = vpost[:, 2], ipost[:, 2]
    di1 = ipost[:, 1] - ipre[:, 1]
    use2 = np.abs(i2) >= i2_frac * np.abs(di1)
    neg = np.real(v2 * np.conj(i2) * ang) < 0
    mem = np.real(vpre[:, 1] * np.conj(ipost[:, 1]) * ang) > 0
    return np.where(use2, neg, mem)


def study_reach(R, name, net, S):
    """R4: smallest rung-3 reactance of external study faults (R_f <= R_arc + R_tower) that the rung-3
    quadrilateral would otherwise pick up; X_set = min(0.85 X_line, 0.9 x that)."""
    cfg = R["cfg"]; rb = cm.RELAY_BUS[name]
    ext = [("bus", cfg["remote_bus"], 0.0)]
    for ln in cfg["beyond"]:
        u, v, _, _ = net[1][ln]
        for frac in (0.0, 0.01, 0.1, 0.2):
            ext.append(("line", ln, frac if u == cfg["remote_bus"] else 1 - frac))
    rot = np.array([1, 1, 1])
    xmin, worst = np.inf, None
    for kind, tgt, m in ext:
        for ft in ("lg", "ll", "llg", "3ph"):
            for rf in np.linspace(0, S["r_arc_g"] + R_TOWER, 7):
                vpo, ipo, vpr, ipr = ss.solve_fault(net, rb, cfg["line"], (kind, tgt), ft, rf, m)
                # study phasors are rms; element thresholds (min current) use peak magnitudes
                k = np.sqrt(2)
                trip, x = evaluate_block(R, (vpr * k)[None], (vpo * k)[None], (ipr * k)[None], (ipo * k)[None], S, "R3",
                                         x_set=1e9)
                if np.isfinite(x[0]) and x[0] < xmin:
                    xmin, worst = float(x[0]), (kind, tgt, round(float(m), 2), ft, float(rf))
    return float(min(S["x_set"], 0.9 * xmin)), worst


# ------------------------------------------------------------------------------------ evaluation
def phasors(R, idx, t, window, rung):
    mim = rung != "R0"
    return cm.phasors_at(R, idx, t, window, mim)


def rates(trip, R, sel):
    out = {}
    for h in ("pos", "neg") + HELD:
        m = R[h][sel]
        if m.any():
            k, n = int(trip[m].sum()), int(m.sum())
            out[h] = dict(rate=k / n, k=k, n=n, ci=cm.binom_ci(k, n))
    rf = R["rf"][sel]
    out["dep_by_rf"] = {f"{r:g}": float(trip[R["pos"][sel] & (rf == r)].mean()) for r in (1, 10, 40)}
    out["ft_by_rf"] = {f"{r:g}": float(trip[R["neg"][sel] & (rf == r)].mean()) for r in (1, 10, 40)}
    return out


def run(name):
    R = cm.load_relay(name)
    S = settings(R, name)
    print(f"[{name}] settings: " + json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in S.items()}), flush=True)
    sel = np.where(R["pos"] | R["neg"] | R["own99"] | R["parallel"] | R["reverse"] | R["other"] | R["switching"])[0]
    zpos = np.where(R["pos"][sel] | R["neg"][sel])[0]
    zidx = sel[zpos]
    y = R["pos"][zidx].astype(int)
    groups = R["groups"][zidx]
    res = dict(settings=S, fixed={}, tuned={}, tilt_robustness={})
    for t, window in TIMES:
        ph = {rg: phasors(R, sel, t, window, rg) for rg in ("R0", "R1")}
        for rung in ("R0", "R1", "R2", "R3", "R4"):
            if rung == "R0" and t < 20:
                continue
            p = ph["R0"] if rung == "R0" else ph["R1"]
            trip, _ = evaluate_block(R, *p, S, rung)
            r = rates(trip, R, sel)
            res["fixed"][f"{t}|{rung}"] = r
            print(f"[{name}] {t:2d} ms {rung}: dep {r['pos']['rate']*100:5.1f}  FT {r['neg']['rate']*100:5.1f}  "
                  + "  ".join(f"{h} {r[h]['rate']*100:5.1f}" for h in HELD if h in r)
                  + f"  dep/Rf {r['dep_by_rf']}  ft/Rf {r['ft_by_rf']}", flush=True)
        # tilt robustness for R3 over the source-impedance box
        worst = dict(dep_min=1.0, ft_max=0.0, own99_max=0.0, reverse_max=0.0, parallel_max=0.0)
        for tl in np.linspace(*S["tilt_range_deg"], 9):
            trip, _ = evaluate_block(R, *ph["R1"], S, "R3", tilt=tl)
            r = rates(trip, R, sel)
            worst["dep_min"] = min(worst["dep_min"], r["pos"]["rate"])
            worst["ft_max"] = max(worst["ft_max"], r["neg"]["rate"])
            for h in ("own99", "reverse", "parallel"):
                if h in r:
                    worst[f"{h}_max"] = max(worst[f"{h}_max"], r[h]["rate"])
        res["tilt_robustness"][str(t)] = worst
        print(f"[{name}] {t:2d} ms R3 over tilt range {S['tilt_range_deg']}: {worst}", flush=True)
        # tuned rungs on the zone_cv folds
        p0 = tuple(a[zpos] for a in ph["R0"]); p1 = tuple(a[zpos] for a in ph["R1"])
        _, x0 = evaluate_block(R, *p0, S, "R0")
        # T2 grid: X_set and R_set scalings of the rule-based R2 settings
        xgrid = S["x_set"] * np.linspace(0.3, 1.3, 21)
        rgrid = S["r_set_g"] * np.array([0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0])
        grid_trips = {}
        for xs in xgrid:
            for rs in rgrid:
                grid_trips[(xs, rs)] = evaluate_block(R, *p1, S, "R2", x_set=xs, r_set=rs)[0]
        held_ph = {h: tuple(a[np.where(R[h][sel])[0]] for a in ph["R1"]) for h in HELD if R[h][sel].any()}
        held_ph0 = {h: tuple(a[np.where(R[h][sel])[0]] for a in ph["R0"]) for h in HELD if R[h][sel].any()}
        kinds = ["grouped", "stratified", "lorfo", "lolo"] if t == 20 else ["grouped"]
        for kind in kinds:
            for rung in ("T1", "T2"):
                if rung == "T1" and t < 20:
                    continue
                dec_all, idx_all, held_rates = [], [], {h: [] for h in held_ph}
                for f, tr, te, meta in splits(kind, R, zidx, y, groups):
                    if rung == "T1":
                        thr = cm.thr_at_far(-x0[tr][y[tr] == 0], FAR)
                        dec = -x0[te] > thr
                        for h, hp in held_ph0.items():
                            held_rates[h].append(float((-evaluate_block(R, *hp, S, "R0")[1] > thr).mean()))
                    else:
                        best = (-1.0, None)
                        for key, tr_trip in grid_trips.items():
                            if tr_trip[tr][y[tr] == 0].mean() <= FAR:
                                dep = tr_trip[tr][y[tr] == 1].mean()
                                if dep > best[0]:
                                    best = (dep, key)
                        xs, rs = best[1]
                        dec = grid_trips[best[1]][te]
                        for h, hp in held_ph.items():
                            held_rates[h].append(float(evaluate_block(R, *hp, S, "R2", x_set=xs, r_set=rs)[0].mean()))
                    dec_all.append(dec); idx_all.append(te)
                ii, dd = np.concatenate(idx_all), np.concatenate(dec_all)
                yy, gg = y[ii], groups[ii]
                dep = lambda s: dd[s][yy[s] == 1].mean()
                ftr = lambda s: dd[s][yy[s] == 0].mean()
                r = dict(dependability=float(dep(slice(None))), false_trip=float(ftr(slice(None))),
                         dependability_ci=cm.grouped_bootstrap(dep, gg, 500), false_trip_ci=cm.grouped_bootstrap(ftr, gg, 500),
                         **{f"trip_{h}": float(np.mean(v)) for h, v in held_rates.items()})
                res["tuned"][f"{t}|{kind}|{rung}"] = r
                print(f"[{name}] {t:2d} ms {rung} {kind:10s}: dep {r['dependability']*100:5.1f} FT {r['false_trip']*100:5.1f}  "
                      + "  ".join(f"{h} {r['trip_' + h]*100:5.1f}" for h in held_rates), flush=True)
    return res


if __name__ == "__main__":
    out = {}
    names = sys.argv[1:] or ["testgrid_B", "testgrid_A", "doubleline"]
    for name in names:
        out[name] = run(name)
        json.dump(out, open(os.path.join(cm.ROOT, "results", "review", "ladder.json"), "w"), indent=1, default=str)
    print("saved results/review/ladder.json")
