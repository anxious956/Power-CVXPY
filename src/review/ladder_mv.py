"""Zone-1 settings for relays on a grid with inverters (the CIGRE MV feeders), from the inverter-aware study.

ladder.settings dispatches here for every config that declares a nominal voltage (vn_kv); TestGrid relays
never reach this file. The rules are ladder.py's frozen specification unchanged (x_set = 0.85 X_line; R_set
the smallest of load encroachment, the zone-1 R/X limit and the Kasztenny 2021 eq. (19) polarising cap; R4
from the study reach), with the relay and line assumptions of ladder.profile (the config's relay_profile).
What changes is where the study quantities come from:

  fault current at the reach point   ibr_study.solve_fault (inverters as their characterised control law),
                                      for the arc-resistance coverage term
  non-homogeneity angle               measured in the model instead of the two-source formula: the angle of
                                      the relay's share of the fault current, I_relay / I_fault, per sequence,
                                      for faults at the reach point. An inverter has no source impedance, so
                                      the two-source formula (ladder.tilt_from) has nothing to take; the
                                      current distribution it approximates is computed directly.
                                      Nominal: LG at R_f = 0 (negative sequence), 3PH at R_f = 0 (positive).
                                      Band: the negative-sequence angle over LG / LL / LLG, R_f in {0, the
                                      design coverage}, loads x0.5 / x1 / x1.5, inverter dispatch x0.5 / x1,
                                      solid and resistive grounding
  study reach (R4)                    ladder.study_reach's external set and reading, solved with inverters

Settings are for the effectively earthed system (solid neutral, 1 ohm, about the median of the records'
solid grounding); resonant-grounded ground faults draw almost no current and are not what a ground distance
element is set for. The model's validity on these relays is in results/cigremv/study_validation_ibr.json:
the reactance it predicts is within a few per cent of |Z1L| for low-R_f faults at R2 and R4 but only within
0.2-0.7 |Z1L| at the inverter-bus relays R1 and R3, so R4's study reach is least certain there.
"""
import itertools
import numpy as np
from review import common as cm
from review import setting_study as ss
from review import ibr_study as ib
from review import ladder as ld

SETTING_GROUNDING = ("solid", 1.0)
BAND_GROUNDINGS = (("solid", 1.0), ("resistive", 7.7))
LOAD_SCALES = (0.5, 1.0, 1.5)
DISPATCH_SCALES = (0.5, 1.0)
A = np.exp(2j * np.pi / 3)


def _net(R, grounding, load_scale=1.0):
    main, lines, grids, loads = ss.net_for(R, grounding=grounding)
    return main, lines, grids, {b: y * load_scale for b, y in loads.items()}


def _ibrs(R, dispatch_scale=1.0):
    out = ib.inverters_from_graph(R["graph"], R["cfg"]["vn_kv"] * 1e3, ib.load_characterisation())
    for g in out:
        g["p"] *= dispatch_scale
        g["q"] *= dispatch_scale
    return out


def _share_angle(Ir, If):
    return float(np.degrees(np.angle(Ir / If))) if abs(If) > 1e-6 and abs(Ir) > 1e-9 else None


def settings_mv(R, name):
    cfg = R["cfg"]; rb = ss.relay_bus_of(R, name); P = ld.profile(R)
    xl = R["z1L"].imag
    x_set = cm.REACH * xl
    vn = cfg["vn_kv"] * 1e3
    i_th = P["i_thermal_per_conductor"]
    zload_min = ld.V_MIN_PU * vn / np.sqrt(3) / i_th
    load_cap = 0.8 * zload_min
    lines = ss.net_for(R)[1]
    u, v, _, _ = lines[cfg["line"]]
    m_line = cm.REACH if u == rb else 1 - cm.REACH
    net0, ibrs0 = _net(R, SETTING_GROUNDING), _ibrs(R)

    def solve(net, ibrs, where, ft, rf, m):
        return ib.solve_fault(net, ibrs, rb, cfg["line"], where, ft, rf, m, return_ibr=True)

    def fault_current(ft, rf):
        *_, info = solve(net0, ibrs0, ("line", cfg["line"]), ft, rf, m_line)
        i0, i1, i2 = info["If"]
        return abs(i0 + i1 + i2) if ft == "lg" else abs(A**2 * i1 + A * i2)     # phase a (LG), phase b (LL)

    i_lg, i_ll = fault_current("lg", P["r_ground"]), fault_current("ll", 0.0)
    r_arc_g, r_arc_p = ld.mho_arc(i_lg, P["arc_length_m"]), ld.mho_arc(i_ll, P["arc_length_m"])
    k0 = (R["z0L"] - R["z1L"]) / (3 * R["z1L"])
    r_cov_g = 1.2 * (r_arc_g + P["r_ground"]) / abs(1 + k0)
    r_cov_p = 1.2 * r_arc_p / 2
    r_leg_g, r_leg_p = min(load_cap, 4.5 * x_set), min(load_cap, 3.0 * x_set)
    rf_design = r_arc_g + P["r_ground"]

    # non-homogeneity angles from the model
    def angles(net, ibrs, ft, rf):
        vpo, ipo, vpr, ipr, info = solve(net, ibrs, ("line", cfg["line"]), ft, rf, m_line)
        If = info["If"]
        return _share_angle(ipo[2], If[2]), _share_angle(ipo[1] - ipr[1], If[1])

    tilt_nom = angles(net0, ibrs0, "lg", 0.0)[0]
    tilt1_nom = angles(net0, ibrs0, "3ph", 0.0)[1]
    band = []
    for gr, ls, ds, ft, rf in itertools.product(BAND_GROUNDINGS, LOAD_SCALES, DISPATCH_SCALES, ("lg", "ll", "llg"),
                                               (0.0, rf_design)):
        a2, _ = angles(_net(R, gr, ls), _ibrs(R, ds), ft, rf)
        if a2 is not None:
            band.append(a2)
    tilt_rng = [float(min(band)), float(max(band))]
    PC = ld.polarising_cap(abs(R["z1L"]), tilt_nom, tilt_rng)
    if ld.RSET_MODE == "polcap":
        r_set_g, r_set_p = min(r_leg_g, PC["r_cap_r2"]), min(r_leg_p, PC["r_cap_r2"])
    else:
        r_set_g, r_set_p = r_leg_g, r_leg_p
    S = dict(x_line=float(xl), x_set=float(x_set), i_thermal_A=float(i_th), z_load_min=float(zload_min),
             load_angle_max_deg=ld.LOAD_ANGLE_MAX, load_cap=float(load_cap), i_fault_lg_reach_A=float(i_lg),
             i_fault_ll_reach_A=float(i_ll), r_arc_g=float(r_arc_g), r_arc_p=float(r_arc_p), r_cov_g=float(r_cov_g),
             r_cov_p=float(r_cov_p), r_set_g=float(r_set_g), r_set_p=float(r_set_p), rset_mode=ld.RSET_MODE,
             z1L_abs=float(abs(R["z1L"])), polarising_cap=PC, r_set_g_legacy=float(r_leg_g), r_set_p_legacy=float(r_leg_p),
             reach_if_legacy_rset_kept=float(1 - 2 * (r_leg_g / abs(R["z1L"])) * np.sin(np.deg2rad(PC["theta_r2_deg"]) / 2)),
             coverage_ok_g=bool(r_set_g >= r_cov_g), coverage_ok_p=bool(r_set_p >= r_cov_p),
             coverage_deficit_g=float(max(0.0, r_cov_g - r_set_g)), coverage_deficit_p=float(max(0.0, r_cov_p - r_set_p)),
             tilt_nominal_deg=float(tilt_nom), tilt1_nominal_deg=float(tilt1_nom), tilt_range_deg=tilt_rng,
             tilt_band_n=len(band), rf_design=float(rf_design), relay_profile=P,
             study_model="ibr_study (inverters as characterised control law)", setting_grounding=list(SETTING_GROUNDING))
    S["x_set_study"], S["study_worst"] = study_reach_mv(R, S, solve, net0, ibrs0, P)
    S["infeed_40ohm"] = infeed_mv(R, solve, net0, ibrs0, rb)
    return S


def study_reach_mv(R, S, solve, net, ibrs, P):
    """ladder.study_reach with the inverter-aware solver."""
    cfg = R["cfg"]
    lines = net[1]
    ext = [("bus", cfg["remote_bus"], 0.0)]
    for ln in cfg["beyond"]:
        u, v, _, _ = lines[ln]
        for frac in (0.0, 0.01, 0.1, 0.2):
            ext.append(("line", ln, frac if u == cfg["remote_bus"] else 1 - frac))
    xmin, worst = np.inf, None
    k = np.sqrt(2)
    for kind, tgt, m in ext:
        for ft in ("lg", "ll", "llg", "3ph"):
            for rf in np.linspace(0, S["r_arc_g"] + P["r_ground"], 7):
                vpo, ipo, vpr, ipr, _ = solve(net, ibrs, (kind, tgt), ft, rf, m)
                _, x = ld.evaluate_block(R, (vpr * k)[None], (vpo * k)[None], (ipr * k)[None], (ipo * k)[None],
                                         (vpr * k)[None], S, "R3", x_set=1e9)
                if np.isfinite(x[0]) and x[0] < xmin:
                    xmin, worst = float(x[0]), (kind, tgt, round(float(m), 2), ft, float(rf))
    return float(min(S["x_set"], 0.9 * xmin)), worst


def infeed_mv(R, solve, net, ibrs, rb, m=0.8, rf=40.0):
    cfg = R["cfg"]
    u, v, _, _ = net[1][cfg["line"]]
    mm = m if u == rb else 1 - m
    vpo, ipo, vpr, ipr, info = solve(net, ibrs, ("line", cfg["line"]), "lg", rf, mm)
    z = ss.apparent_x(R, vpo, ipo, vpr, ipr, "ag")
    i0f = info["If"][0]
    return dict(total_over_relay=float(abs(3 * i0f) / max(abs(3 * ipo[0]), 1e-9)),
                angle_deg=float(np.degrees(np.angle(3 * i0f / (3 * ipo[0])))) if abs(ipo[0]) > 1e-9 else None,
                apparent_R=float(z.real), apparent_X=float(z.imag))
