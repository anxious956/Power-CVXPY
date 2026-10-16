# First PSCAD runs: the tool is connected to our code

15–16 Oct 2026. Code: `src/pscad_io.py` (reader), `src/pscad_sweep.py` and `src/pscad_location_sweep.py`
(drive PSCAD), `src/pscad_check.py`, `src/pscad_table.py`, `src/pscad_sweep_table.py` (the distance
element on runs). Models: the `Relay_Cases` examples shipped with PSCAD 5.0.1, run from working copies in
`data/pscad_work/` (git-ignored; the vendor's examples are not redistributed).

> **Correction, 16 Oct 2026.** An earlier version of this document reported that our faulted-phase
> selector released the wrong loop in 32 of 42 decisions and missed in-zone ground faults from 65–75 %
> of the line on. **That was an error in the analysis script, not in the selector.** The pre- and
> post-fault phasors were taken from windows 2.5 cycles apart with a DFT referenced to each window's
> start, so they were rotated 180° against each other; the "incremental" currents were really
> I_post + I_pre, which gives the healthy phases a large false increment of twice the load current.
> `waveforms.sequence_phasors` now references the absolute sample index, so windows anywhere share one
> frame. With that fixed, the selector is right in every case below, and the selector change made in
> response (PR #32) was reverted to the reviewed rule. Details in the last section and in REVIEW.md
> register row 48.

## What was set up

| | |
|---|---|
| Licence | **PSCAD 5.0.1 Educational** (title bar and licensing menu, 15 Oct 2026): 200 electrical nodes, Python automation allowed. Plan A in [docs/PSCAD.md](../docs/PSCAD.md) (IRTSD) is open |
| Automation | `mhi.pscad` 2.9.7 in PSCAD's own Python 3.7 (`C:\Program Files\Python37`), connects to the running PSCAD |
| Compiler | GFortran 4.6 is PSCAD's configured default and works; 8.1 is installed too |
| Output | the examples ship with "save to disk" off (`PlotType = NONE`); the sweep scripts switch it on in the working copy |
| Run time | 8–20 s per 0.5 s case, compile included |

**Pitfalls met, for whoever does this next:**

- Without `PlotType = OUT` a run produces plots in the GUI and **nothing on disk**.
- A distributed-line segment must travel slower than one time step, or EMTDC aborts: a 12 km segment
  travels in ~40 µs, below the shipped 50 µs. The fault-point sweep uses 5 µs.
- A failed run leaves the previous run's output in place. The sweep scripts now delete old output first
  and stop on any PSCAD error; a first sweep silently copied the 86 % run into every later point.
- Phasors from different windows must share one time frame before they are subtracted or compared (the
  correction above).

## The cases

230 kV, 60 Hz. `case1`: a 100 km transposed line between two 100 MVA sources (Source 2 leads by 20°),
measurements at both terminals, a bolted A-G fault at one of four fixed points. `case2`: the same line
split into two 50 km segments with a fifth fault point at the joint; a working copy whose segment lengths
are set from Python sweeps that point across the line. `case3`: two 100 km lines in parallel between the
same two buses, four relays, six fault points. Line constants from PSCAD's own line-constants program:
**Z1 = 3.57 + j50.78 Ω, Z0 = 36.32 + j132.65 Ω** for 100 km. Output 20 kHz, resampled to 7680 Hz
(128 samples per cycle).

## Results: 42 decisions on the three cases

| | case1 | case2 | case3 | total |
|---|---|---|---|---|
| decisions (fault point × relay) | 8 | 10 | 24 | **42** |
| direction right | 8 | 10 | 24 | **42 / 42** |
| right loop released | 8 | 10 | 24 | **42 / 42** |
| zone-1 decision right | 8 | 10 | 24 | **42 / 42** |
| zone-1 trips, at an A-G loop reading of | 0 % | 0 %, **50.3 %, 50.4 %** | 0 % | |

- A fault at the relay terminal reads 0 %; the mid-line fault 50.3 % and 50.4 % from the two ends.
- The far bus reads 106.6–109.4 %, from remote infeed under the 20° load angle (and, in `case3`, the
  parallel circuit), so no relay overreaches it. Both reverse faults are seen as reverse.

Tables: `results/pscad/case{1,2,3}_table.json`.

## The fault point swept across 50–98 % of the line

`src/pscad_location_sweep.py` moves the joint between the two segments of a `case2` copy (T1 = m km,
T2 = 100 − m km) so the fault sits at m % of the line from end 1. 16 points, bolted and through 10 Ω,
A-G, relay at end 1, zone 1 at 85 %, time step 5 µs.

| Fault at (%) | 50 | 60 | 70 | 75 | 80 | 84 | 85 | 86–98 |
|---|---|---|---|---|---|---|---|---|
| bolted: A-G loop reads | 50.3 | 60.3 | 70.3 | 75.3 | 80.3 | 84.3 | 85.3 | 86.3–98.3 |
| bolted: zone 1 | trip | trip | trip | trip | trip | trip | — | — ✓ |
| 10 Ω: A-G loop reads | 55.8 | 66.6 | 77.6 | 83.1 | 88.8 | 93.4 | 94.6 | 95.7–110.2 |
| 10 Ω: zone 1 | trip | trip | trip | trip | — | — | — | — ✓ |

The right loop (`ag`) is released at all 32 points. The measurement is within +0.3 % of the line for
bolted faults. What is missed is physics, not selection: the bolted fault at 85 % reads 85.3 % (on the
boundary), and through 10 Ω remote infeed makes the loop underreach by 6–12 points, so faults at 78–85 %
fall outside. That is the reactance effect a quadrilateral's resistive reach and tilt exist for. No
false trip beyond 85 %. Tables: `results/pscad/sweep_ag_{bolted,10ohm}.json`.

## The error, and what it changed

`pscad_check.py` took the pre-fault phasor from the cycle ending 1 cycle before the detected inception
and the post-fault phasor from the cycle starting half a cycle after it, 2.5 cycles apart, while
`waveforms.sequence_phasors` measured angles from each window's own start. Pre and post were therefore
180° apart in frame, and every incremental quantity was wrong. `src/review/selector_compare.py` had the
same offset at a 30 ms decision time on EvEMTBench. The review's own phasor code
(`review/common.seq_phasors`) uses an absolute sample reference and was never affected, so the
ADAPTGRID, CIGRE MV and ladder results stand.

With the frame fixed, on labelled own-line faults at six EvEMTBench relays (1,350 faults of all types)
and on the PSCAD sweep, **both the magnitude rule and the sequence-angle rule release the right loop
every time** (`results/review/selector_compare.json`). Withdrawn as a result: "the selector misses in-zone
ground faults on a 100 km line", "the angle rule is better", "both selectors fail on high-resistance
faults at weak line ends", and the narrowing of the element's EvEMTBench validation (REVIEW.md row 48).
The magnitude rule is the default again; the angle rule stays available as `selector="angle"`.
