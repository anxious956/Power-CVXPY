"""
Synthetic relay waveform generator for the detection study (WP3).

Not an EMT simulation. It drives the SAME two-bus sequence circuit used by the design tool
(`aux_model.solve`) to get the relay's sequence phasors for each scenario, then synthesizes
three-phase time-domain waveforms with noise, harmonics and a decaying DC offset. Using one
circuit for both halves means the design tool's theoretical minimum delta and the detector's
measured breaking point are computed on the same system, which is the comparison we want.

Framing follows *Geometry of Distance Protection*: the auxiliary signal is designed offline
and the inverter injects it continuously ("the auxiliary signal must be designed offline,
pre-test"). So delta is present in normal operation AND during faults. What differs is where
that negative-sequence current flows: through the load path when healthy, partly into the
fault when not. The relay has to tell those apart.

The non-fault classes matter as much as the faults:
  normal           balanced load, delta injected
  load_step        balanced load increase, no extra negative sequence
  motor_start      large low-power-factor load, slight unbalance
  unbalanced_load  THE CONFUSER: an asymmetric load injecting its own negative-sequence
                   current at the remote bus, comparable in size to delta, but no fault
Convention: per unit, 60 Hz, 128 samples/cycle (7680 Hz), 8 cycles, event at cycle 4.
"""
import os, sys
from dataclasses import replace
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aux_model import Params, PRESETS, solve, source_generators

F0 = 60.0
CYCLE = 128
FS = F0 * CYCLE
N_CYCLES = 8
N = N_CYCLES * CYCLE
EVENT = 4 * CYCLE

ALPHA = np.exp(2j * np.pi / 3)
A_MAT = np.array([[1, 1, 1],
                  [1, ALPHA**2, ALPHA],
                  [1, ALPHA, ALPHA**2]])      # [s0, s+, s-] -> [a, b, c]

SCENARIOS = ["normal", "load_step", "motor_start", "unbalanced_load", "fault_lg", "fault_ll"]
FAULTS = ("fault_lg", "fault_ll")
_SCEN2CKT = {"fault_lg": "ag", "fault_ll": "ab"}


class SigParams:
    """Measurement-chain parameters (the relay's front end)."""
    def __init__(self, noise=0.01, harmonics=(0.02, 0.01), dc_offset=0.3, dc_tau_cycles=1.5):
        self.noise = noise
        self.harmonics = harmonics
        self.dc_offset = dc_offset
        self.dc_tau_cycles = dc_tau_cycles


def _relay_state(grid: Params, scenario, delta, rng, **kw):
    """Sequence phasors [v+,v-,v0,i+,i-,i0] at the relay, pre-event and post-event."""
    s0, gL, gR = source_generators(grid)
    u = rng.uniform(-1, 1, 4)
    srcL = s0 + gL[0] * u[0] + gL[1] * u[1]         # source spread, same box as the design tool
    iR = grid.i0 + gR[0] * u[2] + gR[1] * u[3]
    pre = solve(grid, "N", srcL, iR, delta, 0.5, 0.0)
    meta = {}

    if scenario == "normal":
        post = solve(grid, "N", srcL, iR, delta, 0.5, 0.0)

    elif scenario == "load_step":
        f = kw.get("factor", rng.uniform(1.3, 2.0))
        g = replace(grid, yld={1: grid.yld[1] * f, 2: grid.yld[2] * f, 0: grid.yld[0]})
        post = solve(g, "N", srcL, iR, delta, 0.5, 0.0)
        meta["factor"] = f

    elif scenario == "motor_start":
        f = kw.get("factor", rng.uniform(3.0, 6.0))
        zl = 1.0 / grid.yld[1]
        zm = abs(zl) / f * np.exp(1j * np.deg2rad(rng.uniform(70, 82)))   # low power factor
        g = replace(grid, yld={1: 1 / zm, 2: 1 / zm, 0: grid.yld[0]})
        post = solve(g, "N", srcL, iR, delta, 0.5, 0.0)
        meta["factor"] = f

    elif scenario == "unbalanced_load":
        # A single-phase line-to-neutral load switching on at the remote bus. It draws equal
        # positive-, negative- and zero-sequence current, so like a ground fault it produces
        # both i- and i0 at the relay, and its negative sequence adds to the auxiliary
        # signal. This is the confuser the study is built around.
        u_mag = kw.get("unbalance", rng.uniform(0.05, 0.7))
        u = u_mag * np.exp(1j * rng.uniform(0, 2 * np.pi))
        f = rng.uniform(1.0, 1.4)
        g = replace(grid, yld={1: grid.yld[1] * f, 2: grid.yld[2] * f, 0: grid.yld[0]})
        post = solve(g, "N", srcL, iR + u, delta + u, 0.5, 0.0, inj0=u)
        meta.update(unbalance=u_mag, factor=f)

    elif scenario in FAULTS:
        m = kw.get("m", rng.uniform(0.1, 0.95))
        mr = kw.get("mr", rng.uniform(0.0, 1.0))
        post = solve(grid, _SCEN2CKT[scenario], srcL, iR, delta, m, mr)
        meta.update(m=m, mr=mr, rf=mr * grid.rF)
    else:
        raise ValueError(scenario)
    return pre, post, meta


def _synth(pre, post, p: SigParams, rng, is_current=False):
    """Sequence phasors [s+, s-, s0] before/after the event -> 3-phase time waveform."""
    t = np.arange(N) / FS
    w = 2 * np.pi * F0
    step = np.zeros(N); step[EVENT:] = 1.0
    out = np.zeros((3, N))
    order = {1: 0, 2: 1, 0: 2}                      # solve() returns [+, -, 0]
    for seq_idx, arr_idx in order.items():
        col = {1: 1, 2: 2, 0: 0}[seq_idx]           # column of A_MAT for this sequence
        for ph in range(3):
            coef = A_MAT[ph, col]
            amp = pre[arr_idx] * coef * (1 - step) + post[arr_idx] * coef * step
            out[ph] += np.real(amp * np.exp(1j * w * t))
    if is_current:
        tau = p.dc_tau_cycles * CYCLE / FS
        decay = np.zeros(N); decay[EVENT:] = np.exp(-(t[EVENT:] - t[EVENT]) / tau)
        for ph in range(3):
            jump = out[ph, EVENT] - out[ph, EVENT - 1]
            out[ph] -= p.dc_offset * jump * decay
    for o, a in zip((5, 7), p.harmonics):
        for ph in range(3):
            out[ph] += a * np.real(np.exp(1j * (o * w * t + ph * 2 * np.pi / 3)))
    out += rng.normal(0, p.noise, out.shape)
    return out


DEFAULT_GRID = PRESETS["weak_sg"]


def generate(scenario, rng, delta=0.0, p: SigParams = None, grid: Params = None, **kw):
    """One labeled example: x is (6, N) = [va vb vc ia ib ic] in pu."""
    p = p or SigParams()
    grid = grid or DEFAULT_GRID
    pre, post, meta = _relay_state(grid, scenario, delta, rng, **kw)
    v = _synth(pre[:3], post[:3], p, rng, is_current=False)
    i = _synth(pre[3:], post[3:], p, rng, is_current=True)
    meta["delta"] = delta
    return dict(x=np.vstack([v, i]).astype(np.float32), scenario=scenario,
                is_fault=scenario in FAULTS, meta=meta)


# ------------------------------------------------------------------ measurement helpers
_B = np.linalg.inv(A_MAT)


def sequence_phasors(x3, start, n=CYCLE):
    """One-cycle DFT of a 3-phase block -> [s0, s+, s-] at the fundamental."""
    seg = x3[:, start:start + n]
    basis = np.exp(-2j * np.pi * np.arange(n) / n)
    return _B @ ((2.0 / n) * (seg @ basis))


def neg_seq_track(x3, step=8):
    starts = np.arange(0, x3.shape[1] - CYCLE + 1, step)
    return starts, np.array([abs(sequence_phasors(x3, s)[2]) for s in starts])


def make_dataset(n_per_class, rng, delta=0.0, p: SigParams = None, grid: Params = None,
                 hard=False):
    """Faults vs non-fault events, balanced classes.

    hard=False: all fault types and resistances, all four non-fault events. Easy; a detector
                can separate most of it from the voltage sag alone.
    hard=True:  ONLY the cases the design tool flags as ambiguous at delta = 0, namely
                high-resistance line-to-ground faults, against the negative-sequence
                confuser (unbalanced load switching). This is the regime the auxiliary
                signal exists for, and the regime the study is about.
    """
    X, y, scen = [], [], []
    if hard:
        for _ in range(2 * n_per_class):
            d = generate("fault_lg", rng, delta=delta, p=p, grid=grid,
                         mr=rng.uniform(0.85, 1.0))
            X.append(d["x"]); y.append(1); scen.append("fault_lg_highR")
        for j in range(2 * n_per_class):
            s = "unbalanced_load" if j % 4 else "load_step"
            X.append(generate(s, rng, delta=delta, p=p, grid=grid)["x"])
            y.append(0); scen.append(s)
    else:
        for s in FAULTS:
            for _ in range(n_per_class):
                X.append(generate(s, rng, delta=delta, p=p, grid=grid)["x"])
                y.append(1); scen.append(s)
        non = [s for s in SCENARIOS if s not in FAULTS]
        for j in range(2 * n_per_class):
            s = non[j % len(non)]
            X.append(generate(s, rng, delta=delta, p=p, grid=grid)["x"])
            y.append(0); scen.append(s)
    return np.stack(X), np.array(y), np.array(scen)
