"""
The relay's front end for every step-3 detector (docs/STEP3.md, "The front end and the noise model").

  1. instrument errors on the sampled waveforms: systematic per-run, per-channel CT and VT ratio errors, and white
     noise added at 128 samples per cycle, before the mimic filter; a VT phase error is applied to the voltage phase
     phasors (the voltage chain is linear and unfiltered, so this equals a phase shift of the fundamental)
  2. resampling to 128 samples per cycle (60 Hz)
  3. a mimic filter on the currents, tau = L1's X/R / 2 pi (1.59 cycles), its fundamental gain divided out
  4. one-cycle phasors on the absolute sample index; sequence quantities [V1, V2, V0, I1, I2, I0] in pu
  5. a causal superimposed-current starter (pscad_check.inception_index) on the filtered currents, and the relay
     memory frame: V1_L averaged over windows ending 0.5 to 2.5 cycles before the inception estimate (3 cycles of
     signal), so a measurement in the relay's frame is y * conj(u_L)

Noise levels are set by their post-filter phasor standard deviation (per real component of a sequence phasor),
calibrated by Monte Carlo (calibrate()); the mimic filter amplifies white current noise about 2.7x in std.

    python src/step3_frontend.py calibrate      prints the sample-to-phasor noise gains
"""
import os, sys, functools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pscad_io import read_case
from pscad_check import to_128_per_cycle, inception_index
from waveforms import CYCLE, _B
from pscad_network import WORK, VBASE_PK, IBASE_PK, three_bus

_z1 = three_bus().lines["L1"].z1
MIMIC_TAU = (_z1.imag / _z1.real) / (2 * np.pi)          # cycles
TIERS = {
    "clean": None,
    "design": dict(sigma_i=0.01, sigma_v=0.005, ct=(0.0, 0.01), vt=(0.0, 0.005), vt_phase_deg=(0.0, 0.3)),
    "class": dict(sigma_i=0.01, sigma_v=0.005, ct=(0.05, 0.10), vt=(0.03, 0.06), vt_phase_deg=(2.0, 4.0)),
    # the design's own noise scale: k = 4 standard deviations fill the eps box (0.08 pu) on every component
    "stress": dict(sigma_i=0.02, sigma_v=0.02, ct=(0.0, 0.0), vt=(0.0, 0.0), vt_phase_deg=(0.0, 0.0)),
}
STARTER_FROM = 0.20                                       # s; every inception is at 0.30 s or later


def mimic(x, tau=MIMIC_TAU):
    d = np.exp(-1.0 / (tau * CYCLE))
    y = np.concatenate([x[:, :1], x[:, 1:] - d * x[:, :-1]], axis=1)
    return y, 1 - d * np.exp(-2j * np.pi / CYCLE)


def phase_phasors(x, end, n=CYCLE):
    """(3,) peak phasors of the window [end - n, end), absolute sample reference."""
    k = np.arange(end - n, end)
    return (2.0 / n) * (x[:, end - n:end] @ np.exp(-2j * np.pi * k / CYCLE))


def to_seq(p3):
    s0, s1, s2 = _B @ p3
    return s1, s2, s0


@functools.lru_cache(maxsize=None)
def noise_gains(n_trials=4000, seed=0):
    """Post-chain std of one real component of a sequence phasor for unit-std white noise per sample:
    (plain one-cycle DFT, with the mimic filter)."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, (3, n_trials * CYCLE // 8 + 4 * CYCLE))
    y, H = mimic(x)
    ends = np.arange(2 * CYCLE, x.shape[1], CYCLE // 8)[:n_trials]
    plain = np.array([to_seq(phase_phasors(x, e))[0] for e in ends])
    filt = np.array([to_seq(phase_phasors(y, e))[0] / H for e in ends])
    return float(np.std(plain.real)), float(np.std(filt.real))


class Relay:
    """One run seen by the relay through one noise tier and seed."""

    def __init__(self, name, tier="clean", seed=0, mimic_on=True, work=WORK):
        run = read_case(os.path.join(work, name + ".gf46"), name)
        v = np.array([run["ch"][f"VL{p}"] - run["ch"]["VLG"] for p in "ABC"]) / VBASE_PK
        i = np.array([run["ch"][f"IL{p}"] for p in "ABC"]) / IBASE_PK
        v, fs = to_128_per_cycle(v, run["fs"], 60.0)
        i, _ = to_128_per_cycle(i, run["fs"], 60.0)
        self.fs, self.t0 = fs, float(run["t"][0])
        cfg = TIERS[tier]
        rng = np.random.default_rng(seed)
        self.vt_phase = np.zeros(3)
        if cfg is not None:
            def draw(lohi):
                lo, hi = lohi
                return rng.choice([-1.0, 1.0], 3) * rng.uniform(lo, hi, 3)
            i = i * (1 + draw(cfg["ct"]))[:, None]
            v = v * (1 + draw(cfg["vt"]))[:, None]
            self.vt_phase = np.radians(draw(cfg["vt_phase_deg"]))
            g_plain, g_mimic = noise_gains()
            v = v + rng.normal(0, cfg["sigma_v"] / g_plain, v.shape)
            i = i + rng.normal(0, cfg["sigma_i"] / (g_mimic if mimic_on else g_plain), i.shape)
        self.v = v
        if mimic_on:
            self.i, self.H = mimic(i)
        else:
            self.i, self.H = i, 1.0
        self.i_raw = i
        # the starter runs from 0.2 s: its baseline (the median cycle-to-cycle difference over its first two cycles)
        # must come from settled operation, not from the simulation's start-up and the inverter's ramp
        s0 = self.idx(STARTER_FROM)
        k = inception_index(self.i_raw[:, s0:], CYCLE)
        self.inception = None if k is None else s0 + k

    def idx(self, t):
        return int(round((t - self.t0) * self.fs))

    def y(self, end):
        """[V1, V2, V0, I1, I2, I0] (pu) of the one-cycle window ending at sample `end`."""
        pv = phase_phasors(self.v, end) * np.exp(1j * self.vt_phase)
        pi = phase_phasors(self.i, end) / self.H
        return np.array(to_seq(pv) + to_seq(pi))

    def frame(self, inc):
        """The relay memory's unit phasor: V1_L averaged over windows ending 0.5 ... 2.5 cycles before inc."""
        ends = inc - CYCLE // 2 - np.arange(0, 2 * CYCLE + 1, CYCLE // 4)
        u = np.mean([self.y(e)[0] for e in ends])
        return u / abs(u)

    def windows(self, inc, c0=2.0, c1=3.0, step=0.25):
        """Relay-frame measurements on windows ending c0 ... c1 cycles after sample inc."""
        uL = np.conj(self.frame(inc))
        return [(c, self.y(inc + int(round(c * CYCLE))) * uL) for c in np.arange(c0, c1 + 1e-9, step)]


def calibrate():
    g_plain, g_mimic = noise_gains()
    print(f"one real component of a sequence phasor, per unit white noise per sample (128 / cycle): plain DFT {g_plain:.4f}, "
          f"with mimic {g_mimic:.4f} (std x{g_mimic / g_plain:.2f}, variance x{(g_mimic / g_plain) ** 2:.1f})")
    for t, cfg in TIERS.items():
        if cfg:
            print(f"tier {t}: sample std currents {cfg['sigma_i'] / g_mimic:.4f} pu, voltages {cfg['sigma_v'] / g_plain:.4f} pu")


if __name__ == "__main__":
    {"calibrate": calibrate}[sys.argv[1]]()
