"""
H2: design noise box (eps per real phasor component) vs the waveform noise the detectors see.

waveforms._synth adds N(0, sigma) per sample per phase (sigma = SigParams.noise = 0.01), plus 5th
and 7th harmonics and a decaying DC offset on currents. The relay estimate is a one-cycle DFT
(waveforms.sequence_phasors, 128 samples/cycle) converted to sequence components.

Analytic: per-phase phasor real/imag std = sigma*sqrt(2/n); sequence component real/imag std
= sigma*sqrt(2/(3n)).  Numerically checked below by Monte Carlo on the real code path, with and
without harmonics/DC offset, in the post-event window used by detect.py / zone_detect.py
(start = EVENT + CYCLE).

  python src/review/wp1_h2_noise.py        (~20 s)
"""
import os, sys, time
import numpy as np
from wp1_common import SRC, dump, PRESETS
from waveforms import _synth, SigParams, sequence_phasors, CYCLE, EVENT, N
from aux_model import solve

rng = np.random.default_rng(0)
n_mc = 4000
sig = 0.01
t0 = time.time()

zero3 = np.zeros(3, complex)


def phasor_err(p, pre, post, is_current, start):
    x = _synth(pre, post, p, rng, is_current=is_current)
    est = sequence_phasors(x, start)                      # [s0, s+, s-]
    ref = post if start >= EVENT else pre
    true = np.array([ref[2], ref[0], ref[1]])             # _synth input order is [+, -, 0]
    return est - true


res = {}
# 1) pure noise, zero signal: isolates the DFT noise
p = SigParams(noise=sig, harmonics=(0.0, 0.0), dc_offset=0.0)
E = np.array([phasor_err(p, zero3, zero3, False, EVENT + CYCLE) for _ in range(n_mc)])
std_mc = float(np.std(np.concatenate([E.real.ravel(), E.imag.ravel()])))
std_an = sig * np.sqrt(2 / (3 * CYCLE))
res["noise_only"] = dict(std_seq_component_mc=std_mc, std_seq_component_analytic=std_an,
                         per_phase_analytic=sig * np.sqrt(2 / CYCLE))

# 2) full front end on a realistic fault (weak_sg, ag, m=0.55, mr=1): harmonics + DC offset
g = PRESETS["weak_sg"]
pre = solve(g, "N", g.e0, g.i0, 0.0, 0.5, 0.0)
post = solve(g, "ag", g.e0, g.i0, 0.0, 0.55, 1.0)
p_full = SigParams(noise=sig)
for lbl, start in (("post_EVENT+CYCLE", EVENT + CYCLE), ("pre_EVENT-2CYCLE", EVENT - 2 * CYCLE)):
    Ev = np.array([phasor_err(p_full, pre[:3], post[:3], False, start) for _ in range(n_mc // 4)])
    Ei = np.array([phasor_err(p_full, pre[3:], post[3:], True, start) for _ in range(n_mc // 4)])
    for nm, EE in (("v", Ev), ("i", Ei)):
        comp = np.concatenate([EE.real, EE.imag], 1)      # (n, 6): Re s0,s+,s- ; Im s0,s+,s-
        res[f"full_{nm}_{lbl}"] = dict(mean_abs_bias=float(np.abs(comp.mean(0)).max()),
                                       std_max=float(comp.std(0).max()),
                                       max_abs_err=float(np.abs(comp).max()))

eps_design = {k: PRESETS[k].eps for k in PRESETS}
res["eps_design"] = eps_design
res["ratio_eps_over_std"] = {k: v / std_an for k, v in eps_design.items()}
res["ratio_eps_over_3std"] = {k: v / (3 * std_an) for k, v in eps_design.items()}
# the box is the half-width; a Gaussian needs P(|n| <= eps) per component; with 12 components:
from math import erf, sqrt
res["prob_all12_inside_box_at_weak_sg_eps"] = float(erf(PRESETS["weak_sg"].eps / (std_an * sqrt(2))) ** 12)
res["sigma_per_sample_equivalent_to_eps_as_3std"] = {k: v / 3 / np.sqrt(2 / (3 * CYCLE)) for k, v in eps_design.items()}
res["runtime_s"] = time.time() - t0
dump(res, "h2_noise.json")
for k, v in res.items():
    print(k, v)
