# Simulation plan: our own inverter-rich EMT grid in PSCAD

15 Oct 2026. This closes the oldest open item in the project: every public dataset we have used
either has no inverters worth the name (EvEMTBench TestGrid: 0.14 % of short-circuit capacity) or
has inverters but no way to inject anything (CIGRE MV). Taylor's method needs an inverter that
injects a designed signal, so it needs a model we can modify.

**What this is for, stated honestly.** On CIGRE MV a static-model screening did not support the reach
use of a suppliable δ, and passive elements settled direction in EMT data without injection
([PLAN.md](PLAN.md) §1). **Neither was tested with δ injected**: no dataset contains an injection. The
purpose here is to run that test, not to produce a positive result for δ: does the static-model
finding hold in EMT with the signal actually injected, and is it bounded to a 20 kV distribution feeder, on a grid where inverters carry a material share of the
fault current — and, either way, to run the detector comparison there against a baseline that suits
inverter-based sources (rung R5, PLAN.md WP3).

## 1. What we have

| | |
|---|---|
| Product | PSCAD 5.0.1, build 368, installed 7 Oct 2026 |
| Compiler | GFortran 8.1, bundled with the installer |
| Licensing | cloud (`licensing.pscad.com`), configured; no certificate cached on this machine yet |
| Edition | **unknown — step 1 below** |

## 2. Step 1: find out which edition the licence gives

Open PSCAD, sign in to MyCentre with the university account, and read the certificate under
*Licensing* (or *Help → About*). The number that matters is the **electrical node limit**.

| Edition | Node limit | Black-box / automation | Runs IRTSD? |
|---|---|---|---|
| Free | 15 | no | **no** |
| Educational | 200 | yes | plausibly yes |
| Professional | unlimited | yes | yes |

This is not a formality. From `papers/notes/D_ml_and_datasets.md` §19–20: IRTSD uses
frequency-dependent distributed lines, the Python automation library, and six buses with five
synchronous generators and three IBR plants, so it fails the Free edition on three independent
counts. The plan below branches on the answer.

## 2b. Before any model: learn the tool (Prof. Taylor's request)

He does not use PSCAD, so the learning is ours. The installation ships worked examples in
`C:\Users\Public\Documents\PSCAD\5.0\Examples`; the ones that matter here:

| Example | Why |
|---|---|
| `Relay_Cases/case1.pscx`, `case1_prot.pscx`, `case1_prot_type2.pscx` | a line with faults and relays: the exact setting we study |
| `Relay_Cases/case1_CT_CCVT.pscx` | CT and CCVT models, the instrument chain every dataset so far lacked |
| `Relay_Cases/case2_pi.pscx`, `case2_pi_evolving.pscx`, `case3_Mutual*.pscx`, `case3_Multiple_run.pscx` | line models, evolving faults, mutual coupling, and multiple runs (how a sweep is automated) |
| `Protection/Protection_x4.pscx` | protection components in use |
| `Photovoltaic/PVshading.pscx`, `hvdc_vsc/`, `WindFarm/` | inverter-interfaced sources, for the inverter study |

For each: run it, export V and I at one terminal, and read them with our pipeline. When the relay
cases come through `phasors_at()` and the distance element locates a bolted fault, the tool and our
code are connected, and only then does a larger model make sense. The user guides are under
`C:\Program Files (x86)\PSCAD50\help`.

## 3. Plan A (Educational or Professional): IRTSD

**IRTSD**, Ross & Mahapatra, IEEE DataPort doi `10.21227/mp6d-j677`, **CC BY 4.0**. Three parts: the
event data (29.56 GB, not needed at first), **the PSCAD model (15.57 MB)**, and the Python
automation that generates events.

Why it fits:

- 6 buses at 230/500 kV, 5 synchronous generators, **3 IBR plants, ~40 % IBR penetration**, WECC
  generic REGC_A / REEC_A controls.
- **60 Hz**, 20 µs solution step, frequency-dependent distributed lines. Our loader already handles
  60 Hz (`evemt.py:_resample_factors` resamples 7680 Hz to 128 samples per cycle).
- Event types already include **fault-induced IBR tripping and momentary cessation**, which is the
  behaviour that breaks conventional elements.
- **What it is not:** the IBR controls are WECC generic REGC_A / REEC_A, i.e. **grid-following**, and
  penetration is a binary axis (IBRs in or out) at ~40 %, not a sweep. The grid-forming,
  inverter-dominated case stays open and stays a reason to ask Taylor for the Baeckeland model
  (Plan C). Any claim from IRTSD must say this.
- Events are configured through PSCAD **Global Substitutions** whose names match the label CSV
  columns, and the README documents a nine-step recipe for adding a new event type. So adding our
  injection is "one component and one event type in a validated model", not "build a model".

Order of work:

1. Download the model and the automation, not the 29.56 GB of data. Record the licence (CC BY 4.0)
   in `papers/README.md`.
2. Compile and run **one documented fault case** unchanged, and reproduce the published recording
   for it. Until that matches, nothing else counts.
3. Export point-on-wave V and I at one line terminal and feed them through our existing pipeline
   (zone labels, the distance element, the CNN). The element must locate bolted faults within a
   few per cent of the line, as it does on EvEMTBench; that is our end-to-end check.
4. Add the auxiliary signal: a negative-sequence current reference at one IBR plant, with
   magnitude and angle as Global Substitutions, so a sweep over δ becomes a label column.
5. Re-run the B1 screen on this grid, then sweep δ and measure what the detectors do, in zone and
   out, with and without injection. Either outcome is a result: a δ that earns its cost here bounds
   the CIGRE negative to distribution feeders; a δ that does not generalises it.

**Plan around the snapshots.** The model needs about 30 s of simulated time (~15 min of compute) to
settle, so the automation runs from `.snp` snapshot files. Build the snapshots once, keep them, and
never regenerate them casually.

## 4. Plan B (Free edition only): our own two-bus model

Not a fallback in spirit — it is the **positive control the design tool has never had**. Build the
exact two-bus sequence circuit of `src/aux_model.py` in EMT: one source behind an impedance, one
current-limited inverter, one line, faults at a swept location and resistance, and the inverter's
negative-sequence injection as a settable input. Well under 15 nodes.

What it buys: the design tool says "δ = 0.5 pu separates these faults". Nobody has ever checked that
claim against a time-domain simulation of the same circuit. This answers it, and it is a result on
its own, positive or negative.

What it does not buy: nothing about multi-bus infeed, line charging, or realistic IBR controls. So
if the edition allows Plan A, do Plan A and keep this as the validation case.

## 5. Plan C (still worth asking): the Baeckeland 14-bus Simulink model

Taylor's own 2026 paper uses a Simulink IEEE 14-bus model with five grid-forming inverters and
current limiters (Baeckeland, Yang & Seo). It is not public. Now that supervision is agreed, asking
for it costs one e-mail, and grid-**forming** inverters are the case neither IRTSD nor CIGRE MV has.
Needs a MATLAB + Simscape Electrical licence check at NJIT.

## 6. What a run has to produce to be usable here

| Requirement | Why |
|---|---|
| Point-on-wave V and I at the relay terminal, ≥ 4 kHz, published step an integer multiple of 20 µs | the detectors are sample-based; 240 µs (4.17 kHz) is the IRTSD default and is enough |
| Labels: faulted line, location, fault type, R_f in ohms, inception time | our zone labels are built from exactly these |
| Faults **behind** the relay | the review's finding N2: without reverse faults a zone element looks secure when it is not |
| Non-fault events (switching, IBR trip, load step) | security cannot be measured without them |
| δ as a label column | the sweep is the experiment |

## 7. Risks, written down before they bite

- **Edition.** If the licence turns out to be Free, Plan A is out; decide quickly, do not fight it.
- **Compute.** Snapshots plus hundreds of cases is laptop-hours, not minutes. Budget it, and keep
  the case list small until step 3 passes.
- **60 Hz.** Our synthetic work is 50 Hz. The loader handles both, but every hard-coded cycle length
  in a new script must come from the sampling rate, not from a constant.
- **Compiler.** GFortran 8.1 is bundled and is what we have; if a model requires the Intel compiler,
  that is a separate licence question, not a quick fix.
- **Scope.** The goal is one honest sweep of δ on one inverter-rich grid, not a model library.
