"""
Step-3 detectors on the common front end (src/step3_frontend.py), task T1 (any fault vs no fault).

  D1  the set test: the design's own relay rule. On windows ending 2.0 ... 3.0 cycles after the trigger, in the
      relay's memory frame, the distance of the measurement to N(delta) (the main design sets: factor 1.1, phi_ref,
      model error 0.1 eps), in units of eps. Alarm when it exceeds 1 (distance > eps, docs/STEP3.md). Its threshold
      is fixed by the design, not calibrated.
  D0  the conventional floor: zero- and negative-sequence overcurrent (50N / 50Q) on the same windows,
      score max(3|I0|, |I2|) in pu, threshold calibrated on normal data at the same delta level (the largest
      calibration-negative score). The signal is negative-sequence, so 50Q's pickup rises with delta.

Triggers: "starter" (the front end's superimposed-current starter; no pickup means no decision), "oracle" (the true
inception, to separate the starter from the detector), and for runs without a fault, "forced" at the scenario's
t_fault (the detector's answer if the starter picked up there).
"""
import os, sys, functools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
from pscad_network import three_bus
from network_delta_test import CASES
from step3_frontend import Relay, CYCLE

EPS = 0.08
MAIN = dict(factor=1.1, drift_deg=3.0, ref_phi=0.030333432167374483, model_err=0.1 * EPS)   # src/frames_main.py


@functools.lru_cache(maxsize=None)
def _model():
    return fr.FrameModel(three_bus(), CASES, n_samples=150, face_pts=3, seed=1, **MAIN)


def normal_set(d_cmd):
    return _model().zonotopes(complex(d_cmd), None)


def trigger(relay, spec, how):
    true = relay.idx(spec.get("t_fault", 0.30))
    inc = true if how in ("oracle", "forced") else relay.inception    # None when the starter does not pick up
    if inc is not None and inc + 3 * CYCLE + 1 > relay.v.shape[1]:
        return None                                      # a pickup too late in the record to reach a decision
    return inc


def d1_score(relay, spec, how="starter", c0=2.0, c1=3.0):
    inc = trigger(relay, spec, how)
    if inc is None:
        return None
    pieces = normal_set(complex(*spec["d_cmd"]))
    return max(fr.distance_to_set(pieces, y) / EPS for _, y in relay.windows(inc, c0, c1))


def d0_score(relay, spec, how="starter", c0=2.0, c1=3.0):
    inc = trigger(relay, spec, how)
    if inc is None:
        return None
    return max(max(3 * abs(y[5]), abs(y[4])) for _, y in relay.windows(inc, c0, c1))


def d0_calibration_scores(relay, spec, c0=2.0, c1=3.0, n_pre=6):
    """D0 scores on pre-fault windows only (calibration negatives): pseudo-triggers spread over the settled
    pre-fault interval, every window wholly before the true inception."""
    true = relay.idx(spec.get("t_fault", 0.30))
    first = relay.idx(0.18)
    last = true - int(round(c1 * CYCLE)) - 1
    out = []
    for inc in np.linspace(first, last, n_pre).astype(int):
        out.append(max(max(3 * abs(y[5]), abs(y[4])) for _, y in relay.windows(inc, c0, c1)))
    return out


# ----------------------------------------------------------------------------- D2
# A multiple-model (Bayesian) test in the phasor domain, with the posterior update of Pirani, Hosseinzadeh, Taylor
# & Sinopoli 2022 (eq. (14): beta_i <- beta_i exp(-||r_i||)), and separately with the Gaussian likelihood
# (review/STEP3_PLAN_REVIEW.md section 1: with static measurements each mode's Kalman filter is recursive Bayesian
# estimation of the source symbols). Modes: normal operation and the 48 design cases (A-G and B-C over the location
# x R_f grid), each piece of each set a sub-mode with its own affine model y = c + J w + v from the frame model:
# w the shared symbols (prior N(0, I/3), the moments of U[-1, 1]), v the remainder box (variance r^2 / 3) plus the
# front end's noise (post-filter phasor variance). Started by the trigger, fixed horizon: one update per cycle on
# the non-overlapping windows ending 2.0 and 3.0 cycles after it. Score: 1 - P(normal).

D2_UPDATES = (2.0, 3.0)
NOISE_STD = dict(clean=(1e-3, 1e-3), design=(0.005, 0.01), stress=(0.02, 0.02), **{"class": (0.005, 0.01)})   # (voltage, current) per component


def _modes(d_cmd):
    fm = _model()
    out = []
    for k in [None] + list(range(len(CASES))):
        for c, G in fm.zonotopes(complex(d_cmd), k):
            nshared = G.shape[1] - c.size
            out.append((k, c, G[:, :nshared], np.diag(G[:, nshared:]) ** 2 / 3.0))
    return out


@functools.lru_cache(maxsize=None)
def _modes_cached(d_re, d_im):
    return _modes(complex(d_re, d_im))


def _noise_var(tier):
    sv, si = NOISE_STD[tier]
    var = np.array([sv] * 3 + [si] * 3) ** 2
    return np.concatenate([var, var])


def d2_score(relay, spec, tier, how="starter", rule="gauss"):
    """1 - P(normal | windows) after the fixed horizon; None if no trigger. rule: "gauss" or "pirani"."""
    inc = trigger(relay, spec, how)
    if inc is None:
        return None
    d = complex(*spec["d_cmd"])
    modes = _modes_cached(d.real, d.imag)
    uL = np.conj(relay.frame(inc))
    ys = [np.concatenate([(relay.y(inc + int(round(c * CYCLE))) * uL).real, (relay.y(inc + int(round(c * CYCLE))) * uL).imag])
          for c in D2_UPDATES]
    nv = _noise_var(tier)
    n_fault_modes = sum(1 for m in modes if m[0] is not None)
    n_norm_modes = len(modes) - n_fault_modes
    logp = []
    for k, c, J, rv in modes:
        w = np.zeros(J.shape[1])
        P = np.eye(J.shape[1]) / 3.0
        R = np.diag(rv + nv)
        lp = np.log(0.5 / (n_norm_modes if k is None else n_fault_modes))
        for y in ys:
            r = y - (c + J @ w)
            S = J @ P @ J.T + R
            if rule == "gauss":
                sign, logdet = np.linalg.slogdet(S)
                lp += -0.5 * (r @ np.linalg.solve(S, r) + logdet + len(r) * np.log(2 * np.pi))
            else:                                        # Pirani eq. (14): the residual norm, in units of eps
                lp += -np.linalg.norm(r) / EPS
            K = P @ J.T @ np.linalg.inv(S)
            w = w + K @ r
            P = P - K @ J @ P
        logp.append((k, lp))
    lps = np.array([lp for _, lp in logp])
    m = lps.max()
    post = np.exp(lps - m)
    post /= post.sum()
    p_normal = float(sum(p for (k, _), p in zip(logp, post) if k is None))
    return 1.0 - p_normal


def d2_calibration_scores(relay, spec, tier, rule="gauss", n_pre=6):
    true = relay.idx(spec.get("t_fault", 0.30))
    first = relay.idx(0.18)
    last = true - int(round(max(D2_UPDATES) * CYCLE)) - 1
    return [d2_score(relay, dict(spec, t_fault=(inc - 0) / relay.fs + relay.t0), tier, "oracle", rule)
            for inc in np.linspace(first, last, n_pre).astype(int)]


# ----------------------------------------------------------------------------- D3
# The learned detector: the sequence-trajectory CNN of src/review/q3_inputs.py on the common front end. Features:
# frames ending every 1/4 cycle from 1/4 to 3 cycles after the trigger (12 frames), each [V, I, V - V_mem, I - I_mem]
# for the three sequences in the relay's memory frame, real and imaginary (24 x 12). The same mimic filter as D1 and
# D2. The small 1D CNN of q3_inputs.cnn_scores. Training, calibration and test are disjoint by scenario.

D3_FRAMES = np.arange(0.25, 3.0001, 0.25)


def d3_features(relay, spec, how="starter"):
    inc = trigger(relay, spec, how)
    if inc is None:
        return None
    uL = np.conj(relay.frame(inc))
    mem_ends = inc - CYCLE // 2 - np.arange(0, 2 * CYCLE + 1, CYCLE // 4)
    mem = np.mean([relay.y(e) for e in mem_ends], axis=0) * uL
    fr_ = []
    for c in D3_FRAMES:
        y = relay.y(inc + int(round(c * CYCLE))) * uL
        z = np.concatenate([y, y - mem])
        fr_.append(np.concatenate([z.real, z.imag]))
    return np.stack(fr_, 1)                               # (24, 12)


def cnn_fit_score(Xtr, ytr, Xte_list, seed=0, epochs=60):
    import torch, torch.nn as nn
    from torch_det import seed_everything, time_mean
    seed_everything(seed)
    np.random.seed(seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    mu = Xtr.mean(axis=(0, 2), keepdims=True)
    sd = Xtr.std(axis=(0, 2), keepdims=True) + 1e-9
    f = lambda X: torch.tensor((X - mu) / sd, dtype=torch.float32, device=dev)
    C = Xtr.shape[1]
    model = nn.Sequential(nn.Conv1d(C, 32, 3, padding=1), nn.ReLU(), nn.Conv1d(32, 32, 3, padding=1), nn.ReLU(),
                          time_mean(), nn.Dropout(0.2), nn.Linear(32, 1)).to(dev)
    pos, neg = (ytr == 1).sum(), (ytr == 0).sum()
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg / max(pos, 1), device=dev))
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-4)
    xt, yt = f(Xtr), torch.tensor(ytr, dtype=torch.float32, device=dev)
    for _ in range(epochs):
        model.train()
        perm = torch.randperm(len(xt), device=dev)
        for b in range(0, len(xt), 32):
            j = perm[b:b + 32]
            opt.zero_grad()
            lossf(model(xt[j]).squeeze(1), yt[j]).backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        return [model(f(X)).squeeze(1).cpu().numpy() for X in Xte_list]
