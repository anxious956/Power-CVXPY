"""Shared machinery for the review experiments on EvEMTBench (real_ml.py protocol, extended).

- load_relay(name, chain): the relay's record through a configurable measurement chain
  (white noise, ADC, per-installation ratio/phase error, anti-aliasing delay, CVT, CT saturation)
- case labels, sibling groups (target, location, type, R_f) and the faulted phase
- vectorised phasors (full-cycle / half-cycle DFT, optional mimic filter) at any decision time
- relay elements from one set of phasors: the repo's zone-1 reactance rule (reproduced exactly),
  loop R/X for a quadrilateral, Takagi (superimposed-current) and I2-polarised reactance lines,
  an incremental-quantity (TD21-style) element
- grouped cross-validation splitters and grouped out-of-fold thresholds

Nothing here changes src/real_ml.py; it imports its models so the learned side is identical.
"""
import os, sys, glob, zlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
ROOT = os.path.dirname(SRC)
sys.path.insert(0, SRC)

from evemt import load_cache, line_params          # noqa: E402
from real_zone import CONFIGS, REACH                # noqa: E402
import real_ml                                      # noqa: E402

FS = 6400
SPC = 128
F0 = 50.0
A = np.exp(2j * np.pi / 3)
AM = np.array([[1, 1, 1], [1, A**2, A], [1, A, A**2]])     # [s0, s+, s-] -> [a, b, c]
BM = np.linalg.inv(AM)
V_NOM_PEAK = real_ml.V_NOM_PEAK
LOOPS = ("ag", "bg", "cg", "ab", "bc", "ca")
RELAY_BUS = dict(doubleline="MainBus1", testgrid_A="MainBus1", testgrid_B="MainBus2",
                 adapt_A="MainBus1", adapt_B="MainBus2")

_CACHE = {}


def _cache(cfg):
    path = sorted(glob.glob(os.path.join(ROOT, "data", cfg["cache_glob"])))[0]
    if path not in _CACHE:
        _CACHE[path] = load_cache(path)
    return _CACHE[path]


# ----------------------------------------------------------------------------- measurement chain
DEFAULT_CHAIN = dict(noise_rel=1e-3, adc_bits=16, v_fs=2.0, i_fs=40.0, gain_v=0.0, phase_v_deg=0.0,
                     gain_i=0.0, phase_i_deg=0.0, aa_delay=False, cvt=None, ct=None, bias_seed=None)


def _fractional_phase_shift(x, deg):
    """Lag the record by `deg` degrees of the fundamental (deg >= 0) with a causal first-order
    Thiran all-pass of delay d = deg/360 * 128 samples. Only the relative V-I phase error matters for
    every element here, so a lead on one quantity is applied as a lag on the other (see caller)."""
    if deg <= 0.0:
        return x
    from scipy.signal import lfilter
    d = deg / 360.0 * SPC
    c = (1 - d) / (1 + d)
    return lfilter([c, 1.0], [1.0, c], x, axis=-1)


def cvt_filter(v, kind):
    """Coupling-capacitor voltage transformer, linear circuit referred to the intermediate voltage.

    Thevenin of the capacitive divider (C_e = C1 + C2) -> tuning reactor (L_c, R_c) -> burden R_b
    in parallel with a passive ferroresonance-suppression circuit (L_f || C_f tuned to 50 Hz, in
    series with R_f). Gain and phase at 50 Hz are calibrated out, as a CVT is ratio-calibrated; what
    remains is the subsidence transient. Initial conditions: 25 cycles of the first pre-fault cycle
    tiled in front of the record. Parameters are typical textbook values, not a specific product:
      'highC'  C_e = 100 nF, burden 100 VA  (small transient)
      'lowC'   C_e =  20 nF, burden 200 VA, passive FSC (large transient; worst case for zone 1)
    Intermediate voltage 13 kV, secondary 110/sqrt(3) V."""
    from scipy.signal import cont2discrete, lfilter, lfilter_zi
    w = 2 * np.pi * F0
    p = dict(highC=dict(Ce=100e-9, VA=100.0), lowC=dict(Ce=20e-9, VA=200.0))[kind]
    Ce = p["Ce"]
    Lc = 1 / (w**2 * Ce)
    Rc = 0.01 * w * Lc                              # reactor Q ~ 100
    n2 = (13e3 / (110 / np.sqrt(3)))**2
    Rb = (110 / np.sqrt(3))**2 / p["VA"] * n2       # referred burden
    Rf = 0.2 * Rb                                   # FSC damping resistor (referred)
    Lf = 0.05 * Rb / w                              # FSC tank tuned to 50 Hz
    Cf = 1 / (w**2 * Lf)
    # s-domain impedance form: H(s) = Zload / (Zload + Rc + s Lc + 1/(s Ce)), polynomials as coefficient arrays
    # Z_tank = s Lf / (1 + s^2 Lf Cf); Z_fsc = Rf + Z_tank; Zload = Rb Z_fsc / (Rb + Z_fsc)
    P, M = np.polyadd, np.polymul
    num_tank, den_tank = np.array([Lf, 0.0]), np.array([Lf * Cf, 0.0, 1.0])
    num_fsc, den_fsc = P(Rf * den_tank, num_tank), den_tank
    num_load, den_load = Rb * num_fsc, P(Rb * den_fsc, num_fsc)
    zs_num, zs_den = np.array([Lc * Ce, Rc * Ce, 1.0]), np.array([Ce, 0.0])     # series Rc + sLc + 1/(sCe)
    H_num = M(num_load, zs_den)
    H_den = P(M(num_load, zs_den), M(zs_num, den_load))
    b, a, _ = cont2discrete((H_num, H_den), 1 / FS, method="bilinear")
    b = np.ravel(b)
    Hw = np.polyval(b, np.exp(1j * w / FS)) / np.polyval(a, np.exp(1j * w / FS))
    lead = v[..., :SPC]
    pad = np.concatenate([lead] * 25 + [v], axis=-1)
    y = lfilter(b / abs(Hw), a, pad, axis=-1)[..., 25 * SPC:]
    # remove the calibrated phase at 50 Hz with an equivalent sample shift is not causal; instead
    # report the residual phase and correct it at the phasor level by rotating the record with an
    # all-pass: here the CVT circuit at resonance has ~0 phase by construction, check below.
    return y, float(np.degrees(np.angle(Hw)))


def ct_saturation(i_pri, ratio=1000.0, r_burden=5.0, vsat=400.0, remanence=0.0, S=22.0):
    """Instantaneous CT model in the style of the IEEE PSRC CT saturation calculator: secondary
    circuit resistance r_burden (ohm, CT winding + leads + relay), exciting characteristic
    i_e = (lambda/lambda_s)^S with lambda_s set by the rms saturation voltage vsat, flux integrated
    from the secondary voltage; implicit Euler per sample. Returns the primary-referred measured
    current. Default: 1000/1 A, 5P20-like (Vsat 400 V at 5 ohm), a close-in fully offset fault
    saturates within the first cycle; remanence as a fraction of lambda_s.
    i_pri: (n, 3, t) primary amperes."""
    dt = 1 / FS
    lam_s = vsat * np.sqrt(2) / (2 * np.pi * F0)
    i2 = i_pri / ratio
    lam = np.full(i2.shape[:-1], remanence * lam_s)
    out = np.empty_like(i2)
    for k in range(i2.shape[-1]):
        # solve lam_new = lam + dt*R*(i2 - ie(lam_new)) by 3 Newton steps
        x = lam + dt * r_burden * i2[..., k]
        for _ in range(4):
            ie = np.sign(x) * (np.abs(x) / lam_s) ** S
            f = x - lam - dt * r_burden * (i2[..., k] - ie)
            df = 1 + dt * r_burden * S * (np.abs(x) / lam_s) ** (S - 1) / lam_s
            x = x - f / df
        ie = np.sign(x) * (np.abs(x) / lam_s) ** S
        out[..., k] = i2[..., k] - ie
        lam = x
    return out * ratio


def measurement_chain(x, seed_name, chain):
    """Generalises real_ml.measurement_chain. With DEFAULT_CHAIN it is bit-identical to it."""
    c = dict(DEFAULT_CHAIN, **(chain or {}))
    rng = np.random.default_rng(zlib.crc32(seed_name.encode()))
    x = x.astype(np.float64)
    ev_guard = x.shape[-1] // 5
    i_pre = np.abs(x[:, 3:, :ev_guard]).max()
    physical = any([c["gain_v"], c["phase_v_deg"], c["gain_i"], c["phase_i_deg"], c["aa_delay"], c["cvt"], c["ct"]])
    if physical:
        x = x.copy()
        if c["ct"]:
            x[:, 3:] = ct_saturation(x[:, 3:], **c["ct"])
        if c["cvt"]:
            x[:, :3], _ = cvt_filter(x[:, :3], c["cvt"])
        # per-installation ratio and phase error (drawn outside, passed as numbers)
        x[:, :3] *= 1 + c["gain_v"]
        x[:, 3:] *= 1 + c["gain_i"]
        rel = c["phase_v_deg"] - c["phase_i_deg"]          # V lags I by rel degrees
        if rel > 0:
            x[:, :3] = _fractional_phase_shift(x[:, :3], rel)
        elif rel < 0:
            x[:, 3:] = _fractional_phase_shift(x[:, 3:], -rel)
        if c["aa_delay"]:
            from scipy.signal import butter, lfilter
            b, a = butter(2, 1000 / (FS / 2))       # 2nd-order Butterworth, fc 1 kHz: ~0.45 ms group delay at 50 Hz
            x = lfilter(b, a, x, axis=-1)
    for ch, (nom, fs) in enumerate([(V_NOM_PEAK, c["v_fs"] * V_NOM_PEAK)] * 3 + [(i_pre, c["i_fs"] * i_pre)] * 3):
        y = x[:, ch] + rng.normal(0.0, c["noise_rel"] * nom, x[:, ch].shape)
        if c["adc_bits"]:
            step = 2 * fs / 2 ** c["adc_bits"]
            y = np.clip(np.round(y / step) * step, -fs, fs)
        x[:, ch] = y
    return x.astype(np.float32)


# ----------------------------------------------------------------------------- adaptgrid relay data
ADAPT_HALF = 640          # samples kept each side of the inception -> event at index 640, as in the benchmark caches
ADAPT_OP_BINS = 20        # loading bins used as CV groups: grouped 5-fold then holds out whole loading bands
RF_BINS = ((0.0, 5.0, "<5"), (5.0, 15.0, "5-15"), (15.0, 40.0, "15-40"), (40.0, 1e9, ">40"))   # protection-practice bands
RF_LABELS = tuple(b[2] for b in RF_BINS)
T0_S = 1.0                # first sample time of every EvEMTBench record (evemt.T0)


def rf_bin_of(rf):
    out = np.full(len(rf), "", dtype=object)
    for lo, hi, lab in RF_BINS:
        out[(rf > lo) & (rf <= hi)] = lab
    out[rf <= RF_BINS[0][1]] = RF_BINS[0][2]
    return out.astype(str)


def load_relay_adapt(name, chain=None, cubicle=None):
    """adapt_grid variant of load_relay: continuous fault location and resistance, randomised
    inception, per-simulation operating point. Every difference from the benchmark loader is a
    protocol decision, written up in results/ADAPTGRID.md section 3:

      - each record is re-anchored on its OWN inception (events/event_start, 1.10-1.30 s) and cut to
        [ev-640, ev+640), so R['ev'] = 640 and every downstream window (memory, pre-fault cycle,
        10-50 ms decision windows) is where the rest of the code expects it;
      - pos   = own-line short circuits at <= 85 % of the line (the reach);
      - own99 = own-line short circuits in the 85-100 % guard band (name kept so zone_task, the
        ladder and zone_cv report it unchanged); excluded from both classes;
      - neg   = EVERY short circuit off the protected line, regardless of direction: remote bus,
        lines beyond, reverse bus and lines, other lines. neg_bench = remote bus + first 20 % of
        the lines beyond, the benchmark's definition, for a like-for-like column;
      - incipient (high-impedance, arcing) faults are a held-out class of their own; switching too;
      - groups = quantile bins of total active load, i.e. the operating point. There are no
        siblings: fault location, resistance and every load are continuous per simulation, so
        every simulation is its own deduplicated unit (dedup = arange).
    """
    cfg = CONFIGS[name]
    C = _cache(cfg)
    relay = cubicle or cfg["relay"]
    k = C["cubicles"].index(relay)
    L = C["labels"]
    n = len(L)
    lp = line_params(C["graph"], cfg["line"])
    # --- re-anchor every record on its own inception
    ev_raw = np.rint((L["events/event_start"].to_numpy(dtype=float) - T0_S) * C["fs"]).astype(int)
    if (ev_raw - ADAPT_HALF < 0).any() or (ev_raw + ADAPT_HALF > C["x"].shape[-1]).any():
        raise RuntimeError("an adaptgrid record does not fit the [ev-640, ev+640) window")
    X = C["x"]
    full = np.empty((n, 6, 2 * ADAPT_HALF), np.float32)
    for i in range(n):
        full[i] = X[i, k, :, ev_raw[i] - ADAPT_HALF:ev_raw[i] + ADAPT_HALF]
    full = measurement_chain(full, relay, chain)
    # --- labels
    S = lambda c: L[c].astype(str).to_numpy().astype(str)      # numpy str dtype, not object, for np.char
    et, tgt = S("events/event_type"), S("events/event_target")
    loc = L["events/event_flt_target_line_location"].to_numpy(dtype=float)
    rf = L["events/event_flt_shc_resistance"].to_numpy(dtype=float)
    ph1, ph2 = S("events/event_phase_select_1ph"), S("events/event_phase_select_2ph")
    shc = np.char.find(et, "shc") >= 0
    incipient = np.char.find(et, "incipient") >= 0
    switching = np.char.startswith(et, "switch")
    fault_any = np.char.startswith(et, "flt")
    own = shc & (tgt == cfg["line"])
    pos = own & (loc <= 100.0 * REACH)
    own99 = own & (loc > 100.0 * REACH)
    relay_bus = RELAY_BUS[name]
    behind = [kk for u, v, kk in C["graph"].edges(keys=True) if relay_bus in (u, v) and str(kk).startswith("MainLn")
              and kk not in (cfg["line"], cfg["parallel"])]
    beyond = shc & np.isin(tgt, cfg["beyond"])
    remote_bus = shc & (tgt == cfg["remote_bus"])
    parallel = shc & (tgt == cfg["parallel"]) if cfg["parallel"] else np.zeros(n, bool)
    reverse_bus = shc & (tgt == relay_bus)
    reverse_lines = shc & np.isin(tgt, behind)
    reverse = reverse_bus | reverse_lines
    neg = shc & ~own                                             # everything off the protected line
    neg_bench = remote_bus | (beyond & (loc <= 20.0))            # the benchmark's negative set
    other = neg & ~(beyond | remote_bus | parallel | reverse)
    # --- operating point: total active load, binned by quantile; grounding as a stratum
    p_tot = L[["loads/Ld2/load_p", "loads/Ld5/load_p", "loads/Ld6/load_p"]].sum(axis=1).to_numpy(dtype=float)
    rank = np.argsort(np.argsort(p_tot))
    op_bin = np.minimum(rank * ADAPT_OP_BINS // n, ADAPT_OP_BINS - 1)
    op_quartile = np.minimum(rank * 4 // n, 3)
    grounding = S("grounding/grnd_type")
    phase = np.where(np.char.find(et, "1phg") >= 0, ph1, np.where(np.char.find(et, "2ph") >= 0, ph2, "abc"))
    return dict(name=name, cfg=cfg, full=full, ev=ADAPT_HALF, ev_raw=ev_raw, lp=lp,
                z1L=lp["length_km"] * lp["z1"], z0L=lp["length_km"] * lp["z0"],
                x_reach=REACH * lp["length_km"] * lp["z1"].imag,
                z_reach=abs(REACH * lp["length_km"] * lp["z1"]),
                et=et, tgt=tgt, loc=loc, rf=rf, rf_bin=rf_bin_of(rf), phase=phase,
                groups=op_bin, op_bin=op_bin, op_quartile=op_quartile, p_total=p_tot, grounding=grounding,
                dedup=np.arange(n),
                pos=pos, neg=neg, neg_bench=neg_bench, own99=own99, beyond=beyond, remote_bus_faults=remote_bus,
                parallel=parallel, switching=switching, fault_any=fault_any, incipient=incipient,
                reverse=reverse, reverse_bus=reverse_bus, reverse_lines=reverse_lines, other=other,
                relay_bus=relay_bus, behind_lines=behind, graph=C["graph"], labels=L, adaptgrid=True)


# ----------------------------------------------------------------------------- relay data
def load_relay(name, chain=None, cubicle=None):
    cfg = CONFIGS[name]
    if cfg.get("adaptgrid"):
        return load_relay_adapt(name, chain, cubicle)
    C = _cache(cfg)
    relay = cubicle or cfg["relay"]
    k = C["cubicles"].index(relay)
    full = measurement_chain(np.asarray(C["x"][:, k]), relay, chain)
    lp = line_params(C["graph"], cfg["line"])
    L = C["labels"]
    et = L["events/event_type"].astype(str).to_numpy()
    tgt = L["events/event_target"].astype(str).to_numpy()
    loc = L["events/event_flt_target_line_location"].to_numpy(dtype=float)
    rf = L["events/event_flt_shc_resistance"].to_numpy(dtype=float)
    ph1 = L["events/event_phase_select_1ph"].astype(str).to_numpy()
    ph2 = L["events/event_phase_select_2ph"].astype(str).to_numpy()
    shc = np.char.find(et.astype(str), "shc") >= 0
    pos = shc & (tgt == cfg["line"]) & np.isin(loc, [1, 20, 50, 80])
    neg = shc & ((np.isin(tgt, cfg["beyond"]) & np.isin(loc, [1, 20])) | (tgt == cfg["remote_bus"]))
    own99 = shc & (tgt == cfg["line"]) & (loc == 99)
    parallel = shc & (tgt == cfg["parallel"]) if cfg["parallel"] else np.zeros(len(L), bool)
    switching = np.char.startswith(et.astype(str), "switch")
    fault_any = np.char.startswith(et.astype(str), "flt")
    # reverse faults: the relay's own bus and every line leaving it except the protected and parallel line
    relay_bus = RELAY_BUS[name]
    behind = [k for u, v, k in C["graph"].edges(keys=True) if relay_bus in (u, v) and str(k).startswith("MainLn")
              and k not in (cfg["line"], cfg["parallel"])]
    reverse = shc & ((tgt == relay_bus) | np.isin(tgt, behind))
    reverse_bus = shc & (tgt == relay_bus)                 # unambiguously reverse
    reverse_lines = shc & np.isin(tgt, behind)             # in a meshed grid part of these are fed forward
    other = shc & ~(pos | neg | own99 | parallel | reverse)
    key = np.array([f"{t}|{l}|{e}|{r}" for t, l, e, r in zip(tgt, loc, et, rf)])
    _, groups = np.unique(key, return_inverse=True)
    # deduplication: three-phase "siblings" are bit-identical simulations (results/DATASET_FACTS.json), so
    # they count once in any per-class rate; every other simulation is its own unit
    dkey = np.where(np.char.find(et.astype(str), "3ph") >= 0, key, np.array([f"sim{i}" for i in range(len(key))]))
    _, dedup = np.unique(dkey, return_inverse=True)
    phase = np.where(np.char.find(et.astype(str), "1phg") >= 0, ph1,
                     np.where(np.char.find(et.astype(str), "2ph") >= 0, ph2, "abc"))
    return dict(name=name, cfg=cfg, full=full, ev=C["event_index"], lp=lp,
                z1L=lp["length_km"] * lp["z1"], z0L=lp["length_km"] * lp["z0"],
                x_reach=REACH * lp["length_km"] * lp["z1"].imag,
                z_reach=abs(REACH * lp["length_km"] * lp["z1"]),
                et=et, tgt=tgt, loc=loc, rf=rf, phase=phase, groups=groups, dedup=dedup,
                pos=pos, neg=neg, own99=own99, parallel=parallel, switching=switching, fault_any=fault_any,
                reverse=reverse, reverse_bus=reverse_bus, reverse_lines=reverse_lines, other=other, relay_bus=relay_bus, behind_lines=behind,
                graph=C["graph"], labels=L)


# ----------------------------------------------------------------------------- phasors
def mimic(x, tau_cycles):
    """Causal DC-removal (mimic) filter y[k] = K (x[k] - e^{-Ts/tau} x[k-1]), unity gain and the
    fundamental phase shift removed at the phasor level (returned complex gain)."""
    d = np.exp(-1.0 / (tau_cycles * SPC))
    y = x.copy()
    y[..., 1:] = x[..., 1:] - d * x[..., :-1]
    H = 1 - d * np.exp(-2j * np.pi / SPC)
    return y, H


def seq_phasors(x3, end, n=SPC, H=1.0):
    """DFT over [end-n, end) of (m, 3, t) -> (m, 3) sequence phasors [s0, s+, s-] at the fundamental.
    n = 128 full cycle, n = 64 half cycle (exact for a pure fundamental, not for DC)."""
    seg = x3[..., end - n:end].astype(np.float64)
    k = np.arange(end - n, end)
    basis = np.exp(-2j * np.pi * k / SPC)       # absolute sample reference, like waveforms.sequence_phasors at start=0 mod 128
    ph = (2.0 / n) * (seg @ basis) / H
    return ph @ BM.T


def lowpass(x, fc=400.0, order=2):
    """Causal Butterworth low-pass applied identically to V and I, so V/I at 50 Hz is unaffected;
    its complex gain at 50 Hz is returned for phasor normalisation."""
    from scipy.signal import butter, lfilter, freqz
    b, a = butter(order, fc / (FS / 2))
    _, h = freqz(b, a, worN=[2 * np.pi * F0 / FS])
    return lfilter(b, a, x, axis=-1), complex(h[0])


def phasors_at(R, idx, t_ms, window="full", mimic_i=False, pre_end_ms=-20.0, lpf=None):
    """Pre-fault phasors from the cycle ending 20 ms before inception, post from the window ending at
    decision time t. Returns vpre, vpost, ipre, ipost as (m, 3) [s0, s+, s-]."""
    ev = R["ev"]
    n = SPC if window == "full" else SPC // 2
    end = ev + int(round(t_ms * FS / 1000))
    pre_end = ev + int(round(pre_end_ms * FS / 1000))
    X = R["full"][idx]
    xv, xi, H, Hv = X[:, :3], X[:, 3:], 1.0, 1.0
    if mimic_i:
        xi, H = mimic(X[:, 3:].astype(np.float64), tau_cycles=(R["lp"]["z1"].imag / R["lp"]["z1"].real) / (2 * np.pi))
    if lpf:
        xv, Hv = lowpass(xv.astype(np.float64), lpf)
        xi, Hl = lowpass(xi.astype(np.float64), lpf)
        H = H * Hl
    vpre = seq_phasors(xv, pre_end, H=Hv)
    ipre = seq_phasors(xi, pre_end, H=H)
    vpost = seq_phasors(xv, end, n, H=Hv)
    ipost = seq_phasors(xi, end, n, H=H)
    return vpre, vpost, ipre, ipost


# ----------------------------------------------------------------------------- relay elements
def _phase_q(s):
    """(m, 3) [s0, s+, s-] -> (m, 3) phase a, b, c."""
    return s @ AM.T


def loops(R, vpost, ipost, vpre=None, ipre=None):
    """Loop voltages and currents for the six loops, k0-compensated ground loops.
    Returns dict of (m, 6) arrays: V, I, and the same for pre-fault if given."""
    k0 = (R["z0L"] - R["z1L"]) / (3 * R["z1L"])
    def build(v, i):
        va, vb, vc = _phase_q(v).T
        ia, ib, ic = _phase_q(i).T
        comp = k0 * 3 * i[:, 0]
        V = np.stack([va, vb, vc, va - vb, vb - vc, vc - va], 1)
        I = np.stack([ia + comp, ib + comp, ic + comp, ia - ib, ib - ic, ic - ia], 1)
        return V, I
    out = {}
    out["V"], out["I"] = build(vpost, ipost)
    if vpre is not None:
        out["Vpre"], out["Ipre"] = build(vpre, ipre)
    # negative-sequence polarising currents per loop
    i2 = ipost[:, 2]
    i2ph = np.stack([i2, A * i2, A**2 * i2], 1)
    out["I2pol"] = np.concatenate([i2ph, np.stack([i2ph[:, 0] - i2ph[:, 1], i2ph[:, 1] - i2ph[:, 2],
                                                   i2ph[:, 2] - i2ph[:, 0]], 1)], 1)
    out["I0pol"] = np.repeat(ipost[:, [0]], 6, axis=1)
    return out


def phase_selection(ipre, ipost, ground_ratio=0.2, frac=0.5, pair_frac=0.8):
    """Vectorised copy of zone_model.phase_selected_reactance's selector. (m, 6) boolean mask over LOOPS."""
    di = ipost - ipre
    di0, di1, di2 = di[:, 0], di[:, 1], di[:, 2]
    dia, dib, dic = di0 + di1 + di2, di0 + A**2 * di1 + A * di2, di0 + A * di1 + A**2 * di2
    m = len(di)
    mask = np.zeros((m, 6), bool)
    ground = np.abs(di0) > ground_ratio * np.maximum(np.abs(di1), 1e-12)
    mags = np.abs(np.stack([dia, dib, dic], 1))
    sel = mags >= frac * mags.max(1, keepdims=True)
    nsel = sel.sum(1)
    one_or_three = ground & (nsel != 2)
    mask[one_or_three, :3] = sel[one_or_three]
    two = ground & (nsel == 2)
    # pair loop of the two selected phases: ab if a&b, bc if b&c, ca if c&a
    mask[two & sel[:, 0] & sel[:, 1], 3] = True
    mask[two & sel[:, 1] & sel[:, 2], 4] = True
    mask[two & sel[:, 2] & sel[:, 0], 5] = True
    pair = np.abs(np.stack([dia - dib, dib - dic, dic - dia], 1))
    ps = pair >= pair_frac * pair.max(1, keepdims=True)
    mask[~ground, 3:] = ps[~ground]
    return mask


def rule_reactance(Lp, mask, default=10.0):
    """Smallest forward reactance among released loops (zone_model.phase_selected_reactance)."""
    Z = Lp["V"] / (Lp["I"] + 1e-12)
    X = np.where(mask & (Z.imag > 0), Z.imag, np.inf)
    x = X.min(1)
    return np.where(np.isfinite(x), x, default), Z


def i2_tilted_reactance(R, Lp, mask, tilt2_deg, tilt1_deg=None, default=10.0):
    """Q-fair rung 3: negative-sequence polarised reactance line with a non-homogeneity (tilt) correction.

    I2 at the relay is D2 * I2 at the fault, D2 = |D2| exp(j T2) the negative-sequence current
    distribution factor at the reach point, so the fault current is in phase with I2 exp(-j T2):
        m = Im(V (I2 e^{-jT2})*) / Im(Z1L I (I2 e^{-jT2})*),  returned as m * X1L (ohm).
    T2 comes from the setting study (source impedances at both line ends), not from the EMT records.
    Loops whose I2 polarising current is below 5 % of the loop current (three-phase faults) fall back
    to the superimposed loop current with the positive-sequence tilt T1 (defaults to T2)."""
    t2 = np.exp(-1j * np.deg2rad(tilt2_deg))
    t1 = np.exp(-1j * np.deg2rad(tilt2_deg if tilt1_deg is None else tilt1_deg))
    dI = Lp["I"] - Lp["Ipre"]
    P = np.where(np.abs(Lp["I2pol"]) >= 0.05 * np.abs(Lp["I"]), Lp["I2pol"] * t2, dI * t1)
    num = np.imag(Lp["V"] * np.conj(P))
    den = np.imag(R["z1L"] * Lp["I"] * np.conj(P))
    m = num / np.where(np.abs(den) > 1e-9, den, np.nan)
    xm = m * R["z1L"].imag
    X = np.where(mask & (xm > 0) & np.isfinite(xm), xm, np.inf)
    x = X.min(1)
    return np.where(np.isfinite(x), x, default)


def polarised_reactance(R, Lp, mask, pol="takagi", default=10.0):
    """Reactance-line distance estimate with a polarising current that is (ideally) in phase with
    the fault current, so the fault-resistance term drops out of Im(V Ipol*):
        m = Im(V Ipol*) / Im(Z1L I Ipol*),   returned as m * X1L (ohm) for a common threshold.
    pol = 'takagi': superimposed loop current (post - pre); 'i2': negative-sequence loop current,
    falling back to the superimposed current for loops where |I2pol| < 5 % of |I| (symmetrical
    faults); 'i0': zero-sequence current for ground loops, superimposed current for phase loops.
    Settings from line data only, no tilt."""
    dI = Lp["I"] - Lp["Ipre"]
    if pol == "takagi":
        P = dI
    elif pol == "i2":
        P = np.where(np.abs(Lp["I2pol"]) >= 0.05 * np.abs(Lp["I"]), Lp["I2pol"], dI)
    elif pol == "i0":
        P = np.concatenate([Lp["I0pol"][:, :3], dI[:, 3:]], 1)
        P = np.where(np.abs(P) >= 0.05 * np.abs(Lp["I"]), P, dI)
    else:
        raise ValueError(pol)
    num = np.imag(Lp["V"] * np.conj(P))
    den = np.imag(R["z1L"] * Lp["I"] * np.conj(P))
    m = num / np.where(np.abs(den) > 1e-9, den, np.nan)
    xm = m * R["z1L"].imag
    X = np.where(mask & (xm > 0) & np.isfinite(xm), xm, np.inf)
    x = X.min(1)
    return np.where(np.isfinite(x), x, default)


def directional_forward(vpre, vpost, ipre, ipost, z1L, i2_frac=0.1):
    """Negative-sequence directional element (forward when V2 = -Z_S2 I2, i.e. Re(V2 I2* e^{-j angle Z1L}) < 0),
    falling back to superimposed positive-sequence quantities when |I2| < i2_frac |dI1| (symmetrical faults).
    Replaces the repo rule's use of the sign of the loop reactance as its directional decision."""
    ang = np.exp(-1j * np.angle(z1L))
    v2, i2 = vpost[:, 2], ipost[:, 2]
    dv1, di1 = vpost[:, 1] - vpre[:, 1], ipost[:, 1] - ipre[:, 1]
    use2 = np.abs(i2) > i2_frac * np.abs(di1)
    return np.where(use2, np.real(v2 * np.conj(i2) * ang) < 0, np.real(dv1 * np.conj(di1) * ang) < 0)


def quad_inside(Lp, mask, x_set, r_right, r_left_frac=0.25):
    """Any released loop inside a quadrilateral: X below the reactance line (negative X allowed) and R
    between the left and right resistive blinders. Returns (inside, loop R, loop X)."""
    Z = Lp["V"] / (Lp["I"] + 1e-12)
    inside = mask & (Z.imag < x_set) & (Z.real < r_right) & (Z.real > -r_left_frac * r_right)
    return inside.any(1), Z.real, Z.imag


def loop_rx(Lp, mask):
    """For a quadrilateral: per case, the (R, X) of the released forward loop with the smallest X."""
    Z = Lp["V"] / (Lp["I"] + 1e-12)
    X = np.where(mask & (Z.imag > 0), Z.imag, np.inf)
    j = X.argmin(1)
    z = Z[np.arange(len(Z)), j]
    ok = np.isfinite(X.min(1))
    return np.where(ok, z.real, 1e3), np.where(ok, z.imag, 1e3)


def incremental_distance(R, Lp, mask, reach=REACH):
    """Phasor form of the incremental-quantity distance element (TD21 idea):
        operating  |dV - Zr dI|   restraint  |V_pre|  at the reach point Zr = reach * Z1L
    trips when operating > restraint on any released loop. Returned as the ratio op/restraint
    (in zone = high)."""
    dV = Lp["V"] - Lp["Vpre"]
    dI = Lp["I"] - Lp["Ipre"]
    Zr = reach * R["z1L"]
    op = np.abs(dV - Zr * dI)
    res = np.abs(Lp["Vpre"] - Zr * Lp["Ipre"]) + 1e-9
    ratio = np.where(mask, op / res, 0.0)
    return ratio.max(1)


def elements(R, idx, t_ms, window="full", mimic_i=False, lpf=None):
    """All phasor-based elements for cases idx at decision time t. Scores are 'lower = in zone' for
    reactance-type elements, 'higher = in zone' for the incremental element."""
    vpre, vpost, ipre, ipost = phasors_at(R, idx, t_ms, window, mimic_i, lpf=lpf)
    Lp = loops(R, vpost, ipost, vpre, ipre)
    mask = phase_selection(ipre, ipost)
    x_rule, Z = rule_reactance(Lp, mask)
    r_q, x_q = loop_rx(Lp, mask)
    return dict(rule_x=x_rule, takagi_x=polarised_reactance(R, Lp, mask, "takagi"),
                i2pol_x=polarised_reactance(R, Lp, mask, "i2"), i0pol_x=polarised_reactance(R, Lp, mask, "i0"),
                quad_r=r_q, quad_x=x_q, incr=incremental_distance(R, Lp, mask), mask=mask,
                phasors=(vpre, vpost, ipre, ipost))


# ----------------------------------------------------------------------------- splitters
def grouped_folds(y, groups, n_splits=5, repeats=2, seed=0):
    from sklearn.model_selection import StratifiedGroupKFold
    for r in range(repeats):
        for tr, te in StratifiedGroupKFold(n_splits, shuffle=True, random_state=seed + r).split(y, y, groups):
            yield r, tr, te


def stratified_folds(y, groups=None, n_splits=5, repeats=2, seed=0):
    from sklearn.model_selection import RepeatedStratifiedKFold
    for f, (tr, te) in enumerate(RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=repeats,
                                                         random_state=seed).split(y, y)):
        yield f // n_splits, tr, te


def oof_scores(name, X, y, seed, groups=None, folds=5):
    """real_ml.oof_scores, grouped when groups is given."""
    from sklearn.model_selection import StratifiedKFold, StratifiedGroupKFold
    s = np.zeros(len(y))
    if groups is None:
        split = StratifiedKFold(folds, shuffle=True, random_state=seed).split(X, y)
    else:
        split = StratifiedGroupKFold(folds, shuffle=True, random_state=seed).split(X, y, groups)
    for k, (a, b) in enumerate(split):
        m = real_ml.fit_balanced(real_ml.models(seed + 100 + k)[name], X[a], y[a], seed + k)
        s[b] = real_ml.score(m, X[b])
    return s


def thr_at_far(s_neg, far):
    return float(np.quantile(s_neg, 1 - far))


def dedup_rate(trip, dedup, mask):
    """Per-class trip count on deduplicated units: a unit trips if any of its identical copies trips
    (conservative). Returns k, n, point rate, one-sided 95 % Clopper-Pearson upper bound."""
    from scipy.stats import beta
    u = np.unique(dedup[mask])
    if len(u) == 0:
        return dict(k=0, n=0, rate=None, ucb95=None)
    tripped = np.zeros(dedup.max() + 1, bool)
    np.logical_or.at(tripped, dedup[mask], trip[mask])
    k, n = int(tripped[u].sum()), int(len(u))
    ucb = 1.0 if k == n else float(beta.ppf(0.95, k + 1, n - k))
    return dict(k=k, n=n, rate=k / n, ucb95=ucb)


def min_n_for_budget(budget=0.05):
    """Smallest class size whose one-sided 95 % upper bound can be below `budget` with zero trips."""
    n = 1
    while 1 - 0.05 ** (1 / n) > budget:
        n += 1
    return n


def git_commit():
    import subprocess
    return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def code_unchanged(commit_a, commit_b, files):
    """True if both commits exist and `files` are identical between them, and the working tree has no
    uncommitted change to them."""
    import subprocess
    if not commit_a or not commit_b:
        return False
    if commit_a != commit_b:
        r = subprocess.run(["git", "-C", ROOT, "diff", "--quiet", commit_a, commit_b, "--", *files])
        if r.returncode != 0:
            return False
    return subprocess.run(["git", "-C", ROOT, "diff", "--quiet", "HEAD", "--", *files]).returncode == 0


def config_hash(cfg):
    import hashlib, json as _json
    return hashlib.sha1(_json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:12]


def binom_ci(k, n, alpha=0.05):
    """Clopper-Pearson interval."""
    from scipy.stats import beta
    if n == 0:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    return (float(lo), float(hi))


def grouped_bootstrap(stat, groups, n_boot=1000, seed=0):
    """95 % interval of stat(index array) resampling sibling groups with replacement."""
    rng = np.random.default_rng(seed)
    ug = np.unique(groups)
    members = {g: np.where(groups == g)[0] for g in ug}
    vals = []
    for _ in range(n_boot):
        pick = rng.choice(ug, len(ug), replace=True)
        idx = np.concatenate([members[g] for g in pick])
        try:
            vals.append(stat(idx))
        except ValueError:
            pass
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))
