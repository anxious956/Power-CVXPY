# Review of step 3's class-tier results (PR #44, `52bf7bd`, `2c469f4`, `20eaf59`, `950e194`)

17 Oct 2026. Reviewed in a separate worktree, reading `src/step3_multiplicative.py`, `src/frames_eps_curve.py` and
`results/STEP3_PILOT.md`. No `src/`, `tests/` or `results/` change and no PSCAD runs. One static number was computed
(§1).

## Verdict

The wording fixes, the δ*(ε) curve on box bounds, the 80 Ω static results, the dense normals and the restarted additive
adversary are all fine to keep. **Two class-tier conclusions should not go to Taylor yet**, because both come from
applying **fault-condition** instrument errors to **normal operation**, and the first also from boxing a
multiplicative error:

1. "The 1.12 pu signal false-alarms D1 under CT error" (24 of 30 normals at δ*);
2. "At the class tier no guarantee is available" (δ*(ε) "none" at V 0.139 / I 0.168 pu).

Everything else in the package is ready (§3).

## 1. The D1 false alarm under multiplicative error is a regime artefact

`step3_multiplicative.py` uses one set of bounds for every window, before and during the fault: CT ±10 %, VT ±6 %,
VT phase ±4° (`BOUNDS`). The mechanism the write-up gives is right, and it can be checked exactly. In normal
operation the relay carries a steady negative-sequence current from the signal (static model, 400 random operating
points):

| level | relay \|I2\| in normal operation | 10 % of it | 1 % of it |
|---|---|---|---|
| ¾ δ* | 0.650 pu | 0.065 pu < ε | 0.0065 pu |
| δ* | 0.867 pu | **0.087 pu > ε = 0.08** | 0.0087 pu |

That is exactly the reported pattern: 24 of 30 alarms at δ*, none at ¾ δ*. But 10 % is the **fault-condition** CT
figure (K21: "5 to 10 percent … during fault conditions"; E_practitioner_settings.md §7). At load current a
protection-class CT is within about ±1 % in ratio and ±60′ in phase (5P at rated current). A 3P VT is within ±3 % and
±120′ near nominal voltage; 6 % and 4° belong to the protection voltage range during faults.

So the finding is sound as a statement about a CT with a *steady* 10 % error, and not otherwise. With rated-current
accuracy in normal operation, the I2 error at δ* is about 0.009 pu, a ninth of ε, and D1 should not false-alarm.

**Fix: make the multiplicative adversary regime-dependent.**
- Normal operation and the pre-fault memory: rated-current class limits (CT ±1 % / ±1°, VT ±3 % / ±2°).
- Fault windows: the fault-condition limits.
- The same CT may have different errors before and during a fault, since its error depends on current. That matters
  for increments (D0, D3's Δ channels), so let the two regimes' errors vary independently within their bounds.

Report the steady-10 % case as a stated stress case, not as the finding.

## 2. "No guarantee at the class tier" boxes a multiplicative error at its worst magnitude

The class-tier bound (V 0.139 / I 0.168 pu) is 4σ plus the largest systematic term on the pilot's measurements: 10 %
of the largest fault current component (1.28 pu), 6 % plus 4° of 0.92 pu voltage. That box is then applied to **every
component of every measurement**, normal ones included, whose magnitudes are far smaller (normal |I2| 0.87 pu at δ*,
normal |I0| ≈ 0).

A multiplicative error is a generator proportional to the measurement, not a box. The project already has this model:
`review/tac25_channels.py`'s structured per-channel set, with CT/VT ratio and phase generators ∝ y. DESIGN.md §4.1.1
found that on the two-bus model, with that set at class figures, **no signal is needed at all**, where the box said
"infeasible".

The same is likely here. Before sending "no guarantee at the class tier", compute δ* with the structured multiplicative
set:
- add per-phase ratio and phase symbols (CT 3 + 3, VT 3 + 3) to the frame model as shared symbols. Its sampled Taylor
  model already handles products with the sources;
- use the regime-dependent bounds of §1: normal sets with rated-current limits, fault sets with fault-condition
  limits;
- keep k·σ white noise as the box.

If the result is still "none within the cap", the finding stands, and it is a strong one. If it is feasible, the
class-tier conclusion reverses.

## 3. D0 thresholds of 0.000

Yes, combine. A constant multiplicative error with no white noise leaves steady-state increments at zero, so D0's
threshold collapses and its "0 misses" means nothing. Run the multiplicative adversary **together with** the design
tier's white noise: draw seeds for thresholds and misses, or bound the white part per window at k·σ. Use the same
mixture for D2 and D3, so all four face the same instruments.

## 4. The package for Taylor

| Item | Status |
|---|---|
| The design holds in EMT with δ injected (frames, filtered inverter, mimic chain); 93 % of rating at ε = 0.08 | ready |
| D1's worst-case curve with Clopper–Pearson bounds | ready |
| Statistical detection does not need δ on this network (incremental 50N included; 20 pilot scenarios) | ready |
| δ*(ε) for box bounds 0.03 … 0.12 pu, with the design tier marked (0.04 pu) | ready |
| The class tier: "no guarantee", and "the signal false-alarms D1" | **not ready**: §1 and §2 |
| B, the additive adversary, as a stress bound (with the D2 restarts) | ready, labelled as a stress bound |
| 80 Ω: design tier 0.94 / 1.08 pu, design ε infeasible; "where the guarantee needs the signal" | ready as static only |

## Not checked

- `frames_eps_curve.py` and the 80 Ω runs were read through their outputs only.
- The rated-current class limits quoted in §1 are the usual IEC 5P / 3P figures, not checked against the standard's
  text (the same caveat as E_practitioner_settings.md §7).
