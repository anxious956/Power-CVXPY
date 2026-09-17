"""Q-fair: the conventional baseline ladder, one frozen element specification per rung, evaluated once on
every relay and decision time; tuned rungs on exactly the folds of zone_cv.py (same task, same calibration
data as the learned models, own-line 99 % faults included as negatives).

Settings come from line data and the short-circuit / load-flow study model built from the grid graph
(src/review/setting_study.py). No EMT benchmark outcome is used to choose any setting.

FROZEN SPECIFICATION (justification from relay practice)
--------------------------------------------------------
R0  repo rule            zone_model.phase_selected_reactance exactly as in real_ml.py: full-cycle DFT, no
                         DC-offset filter, faulted-phase selection, k0 compensation, trip if the smallest
                         released loop reactance with Im(Z) > 0 is below 0.85 X_line. The sign of X is its
                         only directional decision. Reproduced, not modified.
R1  + mimic filter       Same element, currents through a causal mimic (DC-offset removal) filter with the
                         line time constant before the DFT; half-cycle DFT at 10 ms. Numerical distance
                         relays remove the decaying DC offset before phasor estimation; a first-cycle DFT
                         without it has transient overreach.
R2  + directional quad   R1 phasors and phase selection, plus
                         - directional element: positive-sequence memory polarised (32P; memory = 3-cycle
                           pre-fault V1 ending 20 ms before inception; forward if Re(V1mem I1* e^{-j angle Z1L}) > 0)
                           for every fault; for unbalanced faults (|I2| >= 0.1 |dI1| and |I2| >= 0.05 In)
                           the negative-sequence element (32Q; forward if Re(V2 I2* e^{-j angle Z1L}) < 0)
                           supplements it and takes priority, as in phase-directional logic that uses 32Q
                           for unbalanced and 32P for balanced faults;
                         - quadrilateral per released loop: reactance line X < X_set = 0.85 X_line (negative X
                           allowed), right blinder R < R_set, left blinder R > -0.25 R_set, directional sector
                           -15 deg <= angle(Z) <= 115 deg (vendor-default directional boundaries, e.g. ABB REL670
                           ArgDir 15 deg / ArgNegRes 115 deg; quoted from memory, not re-verified);
                         - minimum loop current 0.2 In, In = 1000 A (assumed CT primary rating);
                         - R_set from rules only: required coverage = arc (Mho formula, 3 m, study fault current
                           at the reach point) + 10 ohm tower footing for ground loops; capped by load
                           encroachment at worst-case load (assumed thermal rating from the conductor type,
                           0.9 pu voltage, 30 deg maximum load angle, both flow directions: R_set <= 0.8 Z_load,min)
                           and by the zone-1 R/X limit (R_set <= 4.5 X_set ground, 3 X_set phase), and
                           - CORRECTED after note E - by the polarising-error limit of Kasztenny 2021
                           eq. (19), R_set <= |Z1L| (1 - m0) / (2 sin(Theta/2)) with Theta the worst
                           uncompensated non-homogeneity angle over the measured tilt band. The
                           smallest cap is used. Set LADDER_RSET=legacy to reproduce the pre-note-E
                           settings (load encroachment and R/X only).
R3  + I2-pol tilt line   R2 with the reactance line measured by a negative-sequence polarised reactance element
                         tilted by the non-homogeneity angle at the reach point from the study's source impedances
                         at both ends (two-source formula). Worst case also reported over source impedances
                         +-25 % magnitude and +-7.5 deg angle at both ends.
R4  + study reach        R3 with X_set reduced to 0.9 x the smallest rung-3 reactance reading of any external
                         study fault (remote bus, first 20 % of each line leaving it, LG/LL/LLG/3PH) with
                         R_f in [0, R_arc + R_tower] that the rung-3 quadrilateral would otherwise pick up.
T1  tuned reach          One threshold on the R0 score at 5 % false trip on the training negatives (beyond the
                         remote bus and own line 99 %), capped at 0.9 X_line.
T2  tuned quad           R2 with (X_set <= 0.9 X_line, R_set) chosen on each training fold: maximum dependability
                         with training false trip <= 5 % on the same negatives.
Reference (not zone-1)   67N: 3|I0| >= 0.1 In and zero-sequence directional forward; 67Q: 3|I2| >= 0.1 In and 32Q
                         forward. Detection only, no reach: shows whether the high-R_f stratum is detectable by
                         standard means.

    python src/review/ladder.py [relay ...]
"""
import sys, os, json, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import setting_study as ss
from review.zone_cv import splits, zone_task

FAR = 0.05
IN_A = 1000.0
MIN_I_PEAK = 0.2 * IN_A * np.sqrt(2)        # DFT phasor magnitudes are peak values
SECTOR = (-15.0, 115.0)
ARC_LENGTH_M = 3.0                           # assumption
R_TOWER = 10.0                               # assumption, ohm
I_THERMAL_PER_CONDUCTOR = 900.0              # assumption: 435/55 Al/St about 900 A (EN 50182 tables, not re-verified)
V_MIN_PU, LOAD_ANGLE_MAX = 0.9, 30.0
X_CAP = 0.9                                  # tuned reach never beyond 0.9 X_line

# Resistive-reach cap from the polarising phase error (Kasztenny 2021, "Settings considerations for
# distance elements in line protection applications", 48th WPRC, section III.I, eqs. 18-20).
# A quadrilateral's reactance line is only as accurate as the phase angle of its polarising current,
# and that error is amplified by the resistive reach:
#       dZ > 2 R_B sin(Theta/2)      <=>      m0 < 1 - 2 r_B sin(Theta/2)
# with m0 the per-unit reactive reach and r_B the per-unit resistive reach, both in per unit of the
# positive-sequence line impedance |Z1L|, and Theta the polarising phase error. Solved for R_set:
#       R_set <= |Z1L| (1 - m0) / (2 sin(Theta/2)).
# Theta per rung, from this review's own measured tilt band (source impedances +-25 % magnitude and
# +-7.5 deg angle at both ends, `tilt_range_deg`):
#   R2 / T2  untilted reactance line (X = Im Z), so the whole non-homogeneity angle is uncompensated
#            -> Theta = worst |tilt| over the band;
#   R3 / R4  I2-polarised line tilted by tilt_nominal_deg, so only the residual matters
#            -> Theta = worst |tilt - tilt_nominal| over the band.
# r_set_g / r_set_p are one shared setting across rungs, so the binding cap is the larger Theta (R2).
# NOT INCLUDED, so the cap below is an upper bound on what is secure: Kasztenny also lists CT ratio
# error, CT saturation, line charging current and multi-resistance faults as sources of Theta. The
# 5-10 % CT ratio error expected during faults (same paper, section III.B; see
# papers/notes/E_practitioner_settings.md section 7) is not quantified as an angle here.
RSET_MODE = os.environ.get("LADDER_RSET", "polcap")     # "polcap" (corrected) or "legacy" (pre-note-E)


def polarising_cap(z1L_abs, tilt_nominal_deg, tilt_range_deg, m0=None):
    """Kasztenny 2021 eq. (19) solved for the resistive reach. Returns the per-rung polarising phase
    errors and the resistive-reach cap each implies, in ohm."""
    m0 = cm.REACH if m0 is None else m0
    lo, hi = tilt_range_deg
    th_r2 = max(abs(lo), abs(hi))                                   # untilted line: full non-homogeneity
    th_r3 = max(abs(lo - tilt_nominal_deg), abs(hi - tilt_nominal_deg))   # tilted line: residual only
    cap = lambda th: float(z1L_abs * (1 - m0) / (2 * np.sin(np.deg2rad(th) / 2))) if th > 0 else float("inf")
    return dict(theta_r2_deg=float(th_r2), theta_r3_deg=float(th_r3),
                r_cap_r2=cap(th_r2), r_cap_r3=cap(th_r3), binding="R2 (untilted reactance line)")
TIMES = ((10, "half"), (20, "full"), (30, "full"), (50, "full"))
SETS = ("pos", "neg", "own99", "parallel", "reverse_bus", "reverse_lines", "other", "switching")
TYPES = ("flt_1phg_shc", "flt_1phg_shc_w_arc", "flt_2ph_shc", "flt_2phg_shc", "flt_3ph_shc")


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
    pcond = None
    for u, v, k, d in R["graph"].edges(keys=True, data=True):
        if k == cfg["line"]:
            pcond = d.get(f"{k}_typ_param_dict", {}).get("pcond_c")
    n_cond = 2 if pcond and "x2" in str(pcond) else 1         # '435/55 ... x2' read as a 2-conductor bundle
    i_th = I_THERMAL_PER_CONDUCTOR * n_cond
    zload_min = V_MIN_PU * 110e3 / np.sqrt(3) / i_th
    u, v, _, _ = net[1][cfg["line"]]
    m_line = cm.REACH if u == rb else 1 - cm.REACH

    def fault_current(ft, rf):
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

    i_lg, i_ll = fault_current("lg", R_TOWER), fault_current("ll", 0.0)
    r_arc_g, r_arc_p = mho_arc(i_lg), mho_arc(i_ll)
    k0 = (R["z0L"] - R["z1L"]) / (3 * R["z1L"])
    r_cov_g = 1.2 * (r_arc_g + R_TOWER) / abs(1 + k0)
    r_cov_p = 1.2 * r_arc_p / 2
    load_cap = 0.8 * zload_min
    r_leg_g, r_leg_p = min(load_cap, 4.5 * x_set), min(load_cap, 3.0 * x_set)
    zload_bench = ss.prefault_load_impedance(net, rb, cfg["line"])
    zs, zr, _, zl = ss.source_impedances(net, rb, cfg["line"], 2)
    tilts = [tilt_from(zs * ms * np.exp(1j * np.deg2rad(a1)), zr * mr * np.exp(1j * np.deg2rad(a2)), zl)
             for ms, a1, mr, a2 in itertools.product(np.linspace(0.75, 1.25, 5), np.linspace(-7.5, 7.5, 5),
                                                     np.linspace(0.75, 1.25, 5), np.linspace(-7.5, 7.5, 5))]
    zs1, zr1, _, zl1 = ss.source_impedances(net, rb, cfg["line"], 1)
    tilt_nom, tilt_rng = tilt_from(zs, zr, zl), [float(min(tilts)), float(max(tilts))]
    PC = polarising_cap(abs(R["z1L"]), tilt_nom, tilt_rng)
    if RSET_MODE == "polcap":
        r_set_g, r_set_p = min(r_leg_g, PC["r_cap_r2"]), min(r_leg_p, PC["r_cap_r2"])
    else:
        r_set_g, r_set_p = r_leg_g, r_leg_p
    S = dict(x_line=float(xl), x_set=float(x_set), n_conductors_assumed=n_cond, i_thermal_A=float(i_th),
             z_load_min=float(zload_min), load_angle_max_deg=LOAD_ANGLE_MAX, load_cap=float(load_cap),
             i_fault_lg_reach_A=float(i_lg), i_fault_ll_reach_A=float(i_ll), r_arc_g=float(r_arc_g), r_arc_p=float(r_arc_p),
             r_cov_g=float(r_cov_g), r_cov_p=float(r_cov_p), r_set_g=float(r_set_g), r_set_p=float(r_set_p),
             rset_mode=RSET_MODE, z1L_abs=float(abs(R["z1L"])), polarising_cap=PC,
             r_set_g_legacy=float(r_leg_g), r_set_p_legacy=float(r_leg_p),
             reach_if_legacy_rset_kept=float(1 - 2 * (r_leg_g / abs(R["z1L"])) * np.sin(np.deg2rad(PC["theta_r2_deg"]) / 2)),
             coverage_ok_g=bool(r_set_g >= r_cov_g), coverage_ok_p=bool(r_set_p >= r_cov_p),
             coverage_deficit_g=float(max(0.0, r_cov_g - r_set_g)), coverage_deficit_p=float(max(0.0, r_cov_p - r_set_p)),
             r_set_if_0p7_benchmark_load=float(0.7 * abs(zload_bench)), z_load_benchmark=[zload_bench.real, zload_bench.imag],
             Z_S2=[zs.real, zs.imag], Z_R2=[zr.real, zr.imag], tilt_nominal_deg=tilt_nom,
             tilt1_nominal_deg=tilt_from(zs1, zr1, zl1), tilt_range_deg=tilt_rng,
             rf_design=float(r_arc_g + R_TOWER))
    S["x_set_study"], S["study_worst"] = study_reach(R, name, net, S)
    S["infeed_40ohm"] = infeed_factor(R, name, net)
    return S


def infeed_factor(R, name, net, m=0.8, rf=40.0):
    """Study model, LG fault at 80 % of the protected line with R_f = 40 ohm: total fault current over the
    relay's superimposed zero-sequence contribution, and the apparent loop impedance the relay reads."""
    cfg = R["cfg"]; rb = cm.RELAY_BUS[name]
    u, v, _, _ = net[1][cfg["line"]]
    mm = m if u == rb else 1 - m
    vpo, ipo, vpr, ipr = ss.solve_fault(net, rb, cfg["line"], ("line", cfg["line"]), "lg", rf, mm)
    main, lines, grids, loads = net
    Zb = {}
    for seq in (1, 2, 0):
        nodes, ix, Y, I = ss.ybus(main, lines, grids, loads, seq, cfg["line"], mm)
        Zb[seq] = np.linalg.inv(Y)
        if seq == 1:
            vp = Zb[1] @ I
    f = ix["F"]
    i0f = vp[f] / (Zb[1][f, f] + Zb[2][f, f] + Zb[0][f, f] + 3 * rf)
    z = ss.apparent_x(R, vpo, ipo, vpr, ipr, "ag")
    return dict(total_over_relay=float(abs(3 * i0f) / abs(3 * ipo[0])), angle_deg=float(np.degrees(np.angle(3 * i0f / (3 * ipo[0])))),
                apparent_R=float(z.real), apparent_X=float(z.imag))


# ------------------------------------------------------------------------------------ elements
def pack(R, idx, t, window, mimic):
    vpre, vpost, ipre, ipost = cm.phasors_at(R, idx, t, window, mimic)
    ev = R["ev"]; end = ev - 128
    vmem = cm.seq_phasors(R["full"][idx][:, :3], end, 3 * 128)
    return vpre, vpost, ipre, ipost, vmem


def directional(vpre, vpost, ipre, ipost, vmem, z1L, parts=False):
    ang = np.exp(-1j * np.angle(z1L))
    i2 = ipost[:, 2]
    di1 = ipost[:, 1] - ipre[:, 1]
    unbal = (np.abs(i2) >= 0.1 * np.abs(di1)) & (np.abs(i2) >= 0.05 * IN_A * np.sqrt(2))
    d32q = np.real(vpost[:, 2] * np.conj(i2) * ang) < 0
    d32p = np.real(vmem[:, 1] * np.conj(ipost[:, 1]) * ang) > 0
    fwd = np.where(unbal, d32q, d32p)
    return (fwd, d32p, d32q, unbal) if parts else fwd


def evaluate_block(R, vpre, vpost, ipre, ipost, vmem, S, rung, tilt=None, x_set=None, r_set=None):
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
    ph = cm._phase_q(ipost)
    iloop = np.abs(np.stack([ph[:, 0], ph[:, 1], ph[:, 2], ph[:, 0] - ph[:, 1], ph[:, 1] - ph[:, 2], ph[:, 2] - ph[:, 0]], 1))
    region = mask & (Z.real < rset) & (Z.real > -0.25 * rset) & (ang >= SECTOR[0]) & (ang <= SECTOR[1]) & (iloop >= MIN_I_PEAK)
    fwd = directional(vpre, vpost, ipre, ipost, vmem, R["z1L"])
    trip = fwd & (region & (X < xs)).any(1)
    return trip, np.where(fwd, np.where(region, X, np.inf).min(1), np.inf)


def ground_overcurrent(R, vpre, vpost, ipre, ipost, vmem):
    """67N and 67Q reference elements (detection, no reach)."""
    pick = 0.1 * IN_A * np.sqrt(2)
    ang0 = np.exp(-1j * np.angle(R["z0L"]))
    i0, i2 = ipost[:, 0], ipost[:, 2]
    f67n = (3 * np.abs(i0) >= pick) & (np.real(vpost[:, 0] * np.conj(i0) * ang0) < 0)
    fwd, d32p, d32q, unbal = directional(vpre, vpost, ipre, ipost, vmem, R["z1L"], parts=True)
    f67q = (3 * np.abs(i2) >= pick) & d32q
    return f67n, f67q


def study_reach(R, name, net, S):
    cfg = R["cfg"]; rb = cm.RELAY_BUS[name]
    ext = [("bus", cfg["remote_bus"], 0.0)]
    for ln in cfg["beyond"]:
        u, v, _, _ = net[1][ln]
        for frac in (0.0, 0.01, 0.1, 0.2):
            ext.append(("line", ln, frac if u == cfg["remote_bus"] else 1 - frac))
    xmin, worst = np.inf, None
    k = np.sqrt(2)                                 # study phasors are rms, element thresholds use peak
    for kind, tgt, m in ext:
        for ft in ("lg", "ll", "llg", "3ph"):
            for rf in np.linspace(0, S["r_arc_g"] + R_TOWER, 7):
                vpo, ipo, vpr, ipr = ss.solve_fault(net, rb, cfg["line"], (kind, tgt), ft, rf, m)
                _, x = evaluate_block(R, (vpr * k)[None], (vpo * k)[None], (ipr * k)[None], (ipo * k)[None],
                                      (vpr * k)[None], S, "R3", x_set=1e9)
                if np.isfinite(x[0]) and x[0] < xmin:
                    xmin, worst = float(x[0]), (kind, tgt, round(float(m), 2), ft, float(rf))
    return float(min(S["x_set"], 0.9 * xmin)), worst


# ------------------------------------------------------------------------------------ evaluation
def rates(trip, R, sel):
    out = {}
    for h in SETS:
        m = R[h][sel]
        if m.any():
            k, n = int(trip[m].sum()), int(m.sum())
            out[h] = dict(rate=k / n, k=k, n=n, ci=cm.binom_ci(k, n), dedup=cm.dedup_rate(trip, R["dedup"][sel], m))
    rf, et = R["rf"][sel], R["et"][sel]
    mean_or_nan = lambda m: float(trip[m].mean()) if m.any() else float("nan")
    out["dep_by_rf"] = {f"{r:g}": mean_or_nan(R["pos"][sel] & (rf == r)) for r in (1, 10, 40)}
    out["beyond_by_rf"] = {f"{r:g}": mean_or_nan(R["neg"][sel] & (rf == r)) for r in (1, 10, 40)}
    if "rf_bin" in R:                 # adaptgrid: continuous R_f, so bins; grounding and loading quartile as strata
        for key, order in (("rf_bin", ("<=1", "1-10", "10-40", ">40")), ("grounding", ("solid", "resistive", "resonant")),
                           ("op_quartile", (0, 1, 2, 3))):
            g = R[key][sel]
            for cls in ("pos", "neg"):
                out[f"{'dep' if cls == 'pos' else 'beyond'}_by_{key}"] = {
                    str(v): dict(rate=mean_or_nan(R[cls][sel] & (g == v)), n=int((R[cls][sel] & (g == v)).sum())) for v in order}
        out["dep_by_rf"]["40"] = out["dep_by_rf_bin"][">40"]["rate"]        # so every caller's 'dep at 40' column reads the >40 ohm bin
    bus = R["reverse_bus"][sel]
    out["reverse_bus_by_type"] = {t: dict(k=int(trip[bus & (et == t)].sum()), n=int((bus & (et == t)).sum()))
                                  for t in TYPES if (bus & (et == t)).any()}
    out["reverse_bus_by_type_rf1"] = {t: dict(k=int(trip[bus & (et == t) & (rf == 1)].sum()), n=int((bus & (et == t) & (rf == 1)).sum()))
                                      for t in TYPES if (bus & (et == t) & (rf == 1)).any()}
    return out


def line(name, t, rung, r):
    s = f"[{name}] {t:2d} ms {rung:3s}: dep {r['pos']['rate']*100:5.1f}  beyond {r['neg']['rate']*100:5.1f}  own99 {r['own99']['rate']*100:5.1f}"
    for h in ("parallel", "reverse_bus", "reverse_lines", "other", "switching"):
        if h in r:
            s += f"  {h} {r[h]['rate']*100:5.1f}"
    s += f"  dep@40 {r['dep_by_rf']['40']*100:5.1f}  rev-bus 3ph {r['reverse_bus_by_type'].get('flt_3ph_shc', {}).get('k', '-')}/{r['reverse_bus_by_type'].get('flt_3ph_shc', {}).get('n', '-')}"
    return s


def run(name):
    R = cm.load_relay(name)
    S = settings(R, name)
    print(f"[{name}] settings: " + json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in S.items()}, default=str), flush=True)
    sel = np.where(np.any([R[h] for h in SETS], axis=0))[0]
    study_dir = ss.study_direction(R, name)
    res = dict(settings=S, fixed={}, tuned={}, tilt_robustness={}, directional_reverse_bus={}, reference_67={},
               directional_accuracy_vs_study={}, operating_curves={})
    for t, window in TIMES:
        P0 = pack(R, sel, t, window, False)
        P1 = pack(R, sel, t, window, True)
        for rung in ("R0", "R1", "R2", "R3", "R4"):
            if rung == "R0" and t < 20:
                continue
            trip, _ = evaluate_block(R, *(P0 if rung == "R0" else P1), S, rung)
            r = rates(trip, R, sel)
            res["fixed"][f"{t}|{rung}"] = r
            print(line(name, t, rung, r), flush=True)
        # directional element on reverse bus faults, by fault type
        fwd, d32p, d32q, unbal = directional(*P1, R["z1L"], parts=True)
        bus = R["reverse_bus"][sel]
        et = R["et"][sel]
        res["directional_reverse_bus"][str(t)] = {ty: dict(n=int((bus & (et == ty)).sum()), forward_combined=float(fwd[bus & (et == ty)].mean()),
                                                           forward_32P=float(d32p[bus & (et == ty)].mean()),
                                                           forward_32Q=float(d32q[bus & (et == ty)].mean()),
                                                           unbalanced_flag=float(unbal[bus & (et == ty)].mean()))
                                                  for ty in TYPES if (bus & (et == ty)).any()}
        # 67N / 67Q reference
        f67n, f67q = ground_overcurrent(R, *P1)
        ref = {}
        for lab, tr in (("67N", f67n), ("67Q", f67q), ("67N or 67Q", f67n | f67q)):
            rr = rates(tr, R, sel)
            ref[lab] = rr
            print(f"[{name}] {t:2d} ms {lab:10s}: in-zone {rr['pos']['rate']*100:5.1f} (40 ohm {rr['dep_by_rf']['40']*100:5.1f})  "
                  f"beyond {rr['neg']['rate']*100:5.1f}  own99 {rr['own99']['rate']*100:5.1f}  reverse bus {rr['reverse_bus']['rate']*100:5.1f}  "
                  f"lines behind {rr['reverse_lines']['rate']*100 if 'reverse_lines' in rr else float('nan'):5.1f}  "
                  f"switching {rr['switching']['rate']*100:5.1f}", flush=True)
        res["reference_67"][str(t)] = ref
        # R3 worst case over the tilt range
        worst = dict(dep_min=1.0, dep40_min=1.0, beyond_max=0.0, own99_max=0.0, reverse_bus_max=0.0, reverse_lines_max=0.0, parallel_max=0.0)
        for tl in np.linspace(*S["tilt_range_deg"], 9):
            r = rates(evaluate_block(R, *P1, S, "R3", tilt=tl)[0], R, sel)
            worst["dep_min"] = min(worst["dep_min"], r["pos"]["rate"])
            worst["dep40_min"] = min(worst["dep40_min"], r["dep_by_rf"]["40"])
            worst["beyond_max"] = max(worst["beyond_max"], r["neg"]["rate"])
            for h in ("own99", "reverse_bus", "reverse_lines", "parallel"):
                if h in r:
                    worst[f"{h}_max"] = max(worst[f"{h}_max"], r[h]["rate"])
        res["tilt_robustness"][str(t)] = dict(tilt_range_deg=S["tilt_range_deg"], **worst)
        print(f"[{name}] {t:2d} ms R3 worst case over tilt {np.round(S['tilt_range_deg'], 2)}: {worst}", flush=True)
        # directional element accuracy against study-model labels (never from EMT quantities)
        lab = study_dir[sel]
        acc = {}
        for h in ("pos", "neg", "own99", "parallel", "reverse_bus", "reverse_lines", "other"):
            m = R[h][sel] & np.isfinite(lab)
            if m.any():
                acc[h] = dict(n=int(m.sum()), study_forward_share=float(lab[m].mean()),
                              agreement=float((fwd[m] == (lab[m] == 1)).mean()),
                              by_type={ty: float((fwd[m & (et == ty)] == (lab[m & (et == ty)] == 1)).mean())
                                       for ty in TYPES if (m & (et == ty)).any()})
        res["directional_accuracy_vs_study"][str(t)] = acc
        print(f"[{name}] {t:2d} ms directional agreement with study labels: "
              + "  ".join(f"{h} {v['agreement']*100:5.1f}% (fwd {v['study_forward_share']*100:3.0f}%)" for h, v in acc.items()), flush=True)
        # per-class operating curves of the scored rungs (no fitting): dependability vs per-class false trip
        curves = {}
        for rung, PP in (("R0", P0), ("R2", P1)):
            _, sc = evaluate_block(R, *PP, S, rung, x_set=1e9) if rung == "R2" else evaluate_block(R, *PP, S, rung)
            thr_grid = np.quantile(sc[np.isfinite(sc)], np.linspace(0, 1, 41))
            curves[rung] = {h: [float((sc[R[h][sel]] < th).mean()) for th in thr_grid] for h in SETS if R[h][sel].any()}
            curves[rung]["threshold_ohm"] = thr_grid.tolist()
        res["operating_curves"][str(t)] = curves
        # tuned rungs on the zone_cv folds; own-99 % as guard band (default) and as hard negative (20 ms, grouped)
        cap = X_CAP * S["x_line"]
        xgrid = np.linspace(0.3 * S["x_set"], cap, 21)
        # Absolute R_set candidates, identical in both RSET_MODEs, so that the only difference
        # between the legacy and polcap runs is the security cap itself and not a moved grid.
        # In polcap mode the candidates above the Kasztenny cap are removed: a tuned rung is still a
        # conventional rung and a setting engineer cannot choose a resistive reach the criterion forbids.
        rgrid = S["r_set_g_legacy"] * np.array([0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0])
        if RSET_MODE == "polcap":
            rgrid = rgrid[rgrid <= S["polarising_cap"]["r_cap_r2"]]
            if rgrid.size == 0:
                rgrid = np.array([S["polarising_cap"]["r_cap_r2"]])
        heldsets = ("own99", "parallel", "reverse_bus", "reverse_lines", "other", "switching")
        for mode in (("guard", "negative") if t == 20 else ("guard",)):
            zidx, y, groups = zone_task(R, mode)
            zpos = np.searchsorted(sel, zidx)
            beyond = R["neg"][zidx]
            Pz0 = tuple(a[zpos] for a in P0); Pz1 = tuple(a[zpos] for a in P1)
            _, x0 = evaluate_block(R, *Pz0, S, "R0")
            grid = {(xs, rs): evaluate_block(R, *Pz1, S, "R2", x_set=xs, r_set=rs)[0] for xs in xgrid for rs in rgrid}
            hs = tuple(h for h in heldsets if R[h][sel].any() and not (h == "own99" and mode == "negative"))
            Ph0 = {h: tuple(a[np.where(R[h][sel])[0]] for a in P0) for h in hs}
            Ph1 = {h: tuple(a[np.where(R[h][sel])[0]] for a in P1) for h in hs}
            dd_h = {h: R["dedup"][sel][R[h][sel]] for h in hs}
            if R.get("adaptgrid"):          # continuous R_f and location: lorfo/lolo are undefined; loading quartiles instead
                kinds = ["grouped", "loqo"] if (t == 20 and mode == "guard") else ["grouped"]
            else:
                kinds = (["grouped", "stratified", "lorfo", "lolo"] if t == 20 else ["grouped"]) if mode == "guard" else ["grouped"]
            for kind in kinds:
                for rung in ("T1", "T2"):
                    if rung == "T1" and t < 20:
                        continue
                    dec_all, idx_all, held, chosen = [], [], {h: [] for h in hs}, []
                    for f, tr, te, meta in splits(kind, R, zidx, y, groups):
                        if rung == "T1":
                            thr = max(cm.thr_at_far(-x0[tr][y[tr] == 0], FAR), -cap)
                            dec = -x0[te] > thr
                            for h, hp in Ph0.items():
                                held[h].append(-evaluate_block(R, *hp, S, "R0")[1] > thr)
                        else:
                            best = (-1.0, None)
                            for key, tt in grid.items():
                                if tt[tr][y[tr] == 0].mean() <= FAR:
                                    d = tt[tr][y[tr] == 1].mean()
                                    if d > best[0]:
                                        best = (d, key)
                            dec = grid[best[1]][te]
                            chosen.append((float(best[1][0]), float(best[1][1])))
                            for h, hp in Ph1.items():
                                held[h].append(evaluate_block(R, *hp, S, "R2", x_set=best[1][0], r_set=best[1][1])[0])
                        dec_all.append(dec); idx_all.append(te)
                    ii, dd = np.concatenate(idx_all), np.concatenate(dec_all)
                    yy, gg, b = y[ii], groups[ii], beyond[ii]
                    rf = R["rf"][zidx][ii]
                    dep = lambda s: dd[s][yy[s] == 1].mean()
                    ftb = lambda s: dd[s][b[s]].mean()
                    # per-class held-out: mean rate over folds, and the worst fold's deduplicated k/n with 95 % UCB
                    perclass = {}
                    for h, v in held.items():
                        folds = [cm.dedup_rate(d, dd_h[h], np.ones(len(d), bool)) for d in v]
                        worst = max(folds, key=lambda z: z["ucb95"])
                        perclass[h] = dict(mean_rate=float(np.mean([z["rate"] for z in folds])), worst_fold=worst,
                                           supports_5pct_budget=bool(worst["n"] >= cm.min_n_for_budget(0.05)))
                    r = dict(own99_mode=mode, dependability=float(dep(slice(None))), false_trip_beyond=float(ftb(slice(None))),
                             dependability_ci=cm.grouped_bootstrap(dep, gg, 500), false_trip_beyond_ci=cm.grouped_bootstrap(ftb, gg, 500),
                             beyond_dedup=cm.dedup_rate(dd, R["dedup"][zidx][ii], b),
                             dep_by_rf={f"{x:g}": float(dd[(yy == 1) & (rf == x)].mean()) for x in (1, 10, 40)},
                             held=perclass)
                    if chosen:
                        r["chosen_x_set"] = [c[0] for c in chosen]
                        r["chosen_r_set"] = [c[1] for c in chosen]
                        r["chosen_r_set_at_cap"] = bool(RSET_MODE == "polcap" and
                                                        max(c[1] for c in chosen) >= 0.999 * max(rgrid))
                        r["r_set_candidates"] = [float(v) for v in rgrid]
                    res["tuned"][f"{t}|{kind}|{rung}|own99-{mode}"] = r
                    print(f"[{name}] {t:2d} ms {rung} {kind:10s} own99={mode:8s}: dep {r['dependability']*100:5.1f}  beyond "
                          f"{r['false_trip_beyond']*100:5.1f} (dedup {r['beyond_dedup']['k']}/{r['beyond_dedup']['n']}, UCB "
                          f"{r['beyond_dedup']['ucb95']*100:4.1f})  dep@40 {r['dep_by_rf']['40']*100:5.1f}  "
                          + "  ".join(f"{h} {v['mean_rate']*100:5.1f}" for h, v in perclass.items()), flush=True)
    return res


if __name__ == "__main__":
    suffix = "" if RSET_MODE == "legacy" else f"_{RSET_MODE}"
    path = os.path.join(cm.ROOT, "results", "review", f"ladder{suffix}.json")
    out = {}
    for name in (sys.argv[1:] or ["testgrid_B", "testgrid_A", "doubleline"]):
        out[name] = run(name)
        json.dump(out, open(path, "w"), indent=1, default=str)
    print("saved", path)
