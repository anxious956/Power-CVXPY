# First PSCAD runs: the tool is connected to our code

15 Oct 2026. Code: `src/pscad_io.py` (reader), `src/pscad_sweep.py` (drives PSCAD), `src/pscad_check.py`
(distance element on a run). Model: the `Relay_Cases/case1` example shipped with PSCAD 5.0.1, run from
a working copy in `data/pscad_work/` (git-ignored; the vendor's example is not redistributed).

## What was set up

| | |
|---|---|
| Licence | **PSCAD 5.0.1 Educational** (title bar and licensing menu, 15 Oct 2026): 200 electrical nodes, Python automation allowed. Plan A in [docs/PSCAD.md](../docs/PSCAD.md) (IRTSD) is open |
| Automation | `mhi.pscad` 2.9.7 in PSCAD's own Python 3.7 (`C:\Program Files\Python37`), connects to the running PSCAD |
| Compiler | GFortran 4.6 is PSCAD's configured default and works; 8.1 is installed too |
| Output | the example ships with "save to disk" off (`PlotType = NONE`); `pscad_sweep.py` switches it on in the working copy |
| Run time | 12–14 s per 0.5 s case, compile included |

**Pitfalls met, for whoever does this next:**

- Without `PlotType = OUT` a run produces plots in the GUI and **nothing on disk**.
- The build log shows "The system cannot find the path specified" after the compiler batch file. It is
  harmless here: the executable is built and runs. The working path contains `Masaüstü`, which the log
  prints mangled; it has not broken a build yet, but it is the first suspect if one fails.
- Each run overwrites `<case>.gf46/`; `pscad_sweep.py` copies every run's output to `runs/<case>_<control>=<value>/`.

## The case

230 kV, 60 Hz, a 100 km transposed line between two 100 MVA sources (Source 2 leads by 20°, so load
flows from end 2 to end 1), breakers at both ends, measurements V1/I1 and V2/I2 at each terminal.
Line constants from PSCAD's own line-constants program: **Z1 = 3.57 + j50.78 Ω, Z0 = 36.32 + j132.65 Ω**
for the whole line. Bolted A-to-ground fault (R_f = 0.001 Ω) at 0.2 s for 0.12 s, at one of four
points selected by a slider. 20 kHz output, resampled to 7680 Hz (128 samples per cycle at 60 Hz).

## Result: the element on all four fault points, from both ends

Phasors one cycle before the detected inception and over the cycle ending 1.5 cycles after it.

| Fault point | Relay at end 1: A-G loop | Direction | Released loop | Relay at end 2: A-G loop | Direction | Released loop |
|---|---|---|---|---|---|---|
| 1, behind relay 1 | −0.07 − j0.01 Ω | **reverse** ✓ | ca ✗ | 0.25 + j55.54 Ω (109 %) | forward ✓ | ca ✗ |
| 2, line start at end 1 | 0.00 + j0.00 Ω (0 %) | forward ✓ | ag ✓ | 0.19 + j55.50 Ω (109 %) | forward ✓ | ca ✗ |
| 3, line end at end 2 | −0.85 + j54.12 Ω (107 %) | forward ✓ | ab ✗ | 0.00 + j0.00 Ω (0 %) | forward ✓ | ag ✓ |
| 4, behind relay 2 | −0.80 + j54.15 Ω (107 %) | forward ✓ | ab ✗ | −0.07 − j0.00 Ω | **reverse** ✓ | ab ✗ |

Inception detected 1.0–1.8 ms after the true 0.2 s by a causal superimposed-current starter.

What it shows:

1. **The pipeline is connected end to end.** A PSCAD run goes through the same phasor and loop code
   as every EvEMTBench result, and the A-G loop is exactly 0 Ω at the near terminal.
2. **The direction element is right in all eight cases**, including both reverse faults.
3. **The A-G loop reads 106.6–109.4 % for a fault at 100 %**: an underreach of 7–9 %, from the
   remote infeed under a 20° load angle (and line charging on a 100 km line). Correct physics, and the
   reason a zone 1 is set at 85 %.
4. **The faulted-phase selector is wrong in six of eight cases.** It releases a phase-to-phase loop
   (ab or ca) for an A-to-ground fault whenever the fault is not right at the relay. Measured cause:
   the zero-sequence ratio |ΔI0|/|ΔI1| is 0.32–0.38, so the ground branch is taken correctly, but with
   remote infeed the healthy phases' incremental currents pass 50 % of the faulted phase's, two phases
   are selected, and the rule that maps two selected phases to the phase-phase loop (added on
   EvEMTBench for LLG overreach) drops the ground loop. Here the trip decision is still right, because
   every misselected case is outside zone 1 or reverse anyway. Whether that holds for faults inside
   zone 1 away from the relay is tested in the next section. **This narrows an earlier claim** (the
   element validated within 1.5 % on EvEMTBench): register row 48.

## Two more cases: a mid-line fault, and a parallel line

`case2` is the same 100 km line split into two 50 km segments with a fifth fault point between them;
`case3` is two 100 km lines in parallel between the same two buses, four relays, six fault points.
Bolted A-G faults (`--set "Fault Type=1"`). Tables: `results/pscad/case{1,2,3}_table.json`, made by
`src/pscad_table.py`.

| | case1 | case2 | case3 | total |
|---|---|---|---|---|
| decisions (fault point × relay) | 8 | 10 | 24 | **42** |
| direction right | 8 | 10 | 24 | **42 / 42** |
| zone-1 decision right (trip only for a fault on the relay's own line inside 85 %) | 8 | 10 | 24 | **42 / 42** |
| zone-1 trips | 2 | 4 | 4 | 10 |
| … at an A-G loop reading of | 0 % | 0 %, **50.3 %, 50.4 %** | 0 % | |
| selector released the wrong loop | 6 | 6 | 20 | 32 / 42 |
| … on a decision that tripped | 0 | 0 | 0 | **0 / 10** |

- **The mid-line fault is located at 50.3 % from end 1 and 50.4 % from end 2**, with the right loop
  released at both ends, and both trip zone 1.
- **With a parallel line, the far bus reads 106.4–109.4 %** from every relay (infeed through the
  parallel circuit), so no relay overreaches onto the far bus. Faults at the near bus on the other
  circuit are correctly reverse.
- **The selector fails only on faults at the far bus or behind the relay**: 32 of 42, none of them a
  trip. On every fault that tripped (0 % and 50 %) it released the right loop. So the risk stated above
  did **not** appear at 50 %. It is still open between 50 % and 100 %, which is where the 85 % reach
  boundary sits.

## The fault point swept across 50–98 % of the line: the selector costs zone-1 dependability

`src/pscad_location_sweep.py` moves the joint between the two 50 km segments of a `case2` copy
(T1 = m km, T2 = 100 − m km) so fault point 3 sits at m % of the line from end 1, with the line itself
unchanged. 16 points, bolted and through 10 Ω, A-G, relay at end 1, zone 1 at 85 %. Time step 5 µs:
at the shipped 50 µs a segment shorter than ~13 km travels faster than one step and EMTDC aborts. A
first sweep at 50 µs did not notice and copied the 86 % output into every later point; the script now
deletes old output before a run and stops on any PSCAD error. Tables:
`results/pscad/sweep_ag_bolted.json`, `sweep_ag_10ohm.json` (`src/pscad_sweep_table.py`).

| Fault at | 50 | 60 | 65 | 70 | 75 | 78 | 80 | 82 | 84 | 85 | 86–98 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Bolted**: A-G loop reads | 50.3 | 60.3 | 65.3 | 70.3 | 75.3 | 78.3 | 80.3 | 82.3 | 84.3 | 85.3 | 86.3–98.3 |
| loop released | ag | ag | ag | ag | **ab** | **ab** | **ab** | **ab** | **ab** | ab | ab |
| zone 1 trips? (should) | ✓ | ✓ | ✓ | ✓ | **✗** | **✗** | **✗** | **✗** | **✗** | ✗ (A-G reads 85.3) | — ✓ |
| **10 Ω**: A-G loop reads | 55.8 | 66.6 | 72.1 | 77.6 | 83.1 | 86.5 | 88.8 | 91.1 | 93.4 | 94.6 | 95.7–110.2 |
| loop released | ag | ag | **ab** | **ab** | **ab** | ab | ab | ab | ab | ab | ab |
| zone 1 trips? (should) | ✓ | ✓ | **✗** | **✗** | **✗** | ✗ (infeed) | ✗ | ✗ | ✗ | ✗ | — ✓ |

**Bold ✗**: missed only because of the selector; the A-G loop alone would have tripped.

What it shows:

1. **The measurement is right.** The bolted A-G loop reads every point within +0.3 % of the line, from
   50 % to 98 %.
2. **The selector failure reaches inside zone 1.** For bolted faults it releases the phase-phase loop
   from 75 % on, so **five in-zone faults (75–84 %) are missed** that the A-G loop would trip. Through
   10 Ω it starts at 65 %: **three more (65, 70, 75 %)**. On this line the effective zone-1 reach for a
   ground fault is about 70 % bolted and 60 % through 10 Ω, not 85 %. This is the risk the first runs
   could only name; here it is measured.
3. **Separately, fault resistance under remote infeed makes the A-G loop underreach** by 6–12 points at
   10 Ω (78–85 % read 86.5–94.6 %): the textbook reactance effect, the reason quadrilateral elements
   carry a resistive reach and a tilt, and not a defect of our code.
4. **No false trip anywhere**: nothing beyond 85 % trips in either sweep.

The fix belongs to the selector, not the measurement. It is made in the next section.

## The selector fixed: sequence-angle selection (16 Oct 2026)

`zone_model.released_loops` (and its vectorised copy `review/common.phase_selection`) now selects the
faulted phases from **angles** of the incremental sequence currents, as relay phase selectors do:
∠(ΔI2/ΔI0) picks the sector (A at 0°, B at −120°, C at +120°), and ∠(ΔI2/ΔI1), rotated into that
sector, separates a single line-to-ground fault (near 0°) from a double line-to-ground fault on the
other two phases (near 180°). The old magnitude rule is kept as `selector="magnitude"`, so every
earlier number can be reproduced. Both implementations agree on 600 of 600 records under each rule;
the test suite passes (137, 4 skipped).

**Tested on labelled faults before adoption** (`src/review/selector_compare.py`,
`results/review/selector_compare.json`): own-line faults at six EvEMTBench relays, where the fault
type and phases are in the labels, and the PSCAD sweep.

| Correct loop released | magnitude (old) | **angle (new)** | angle + undervoltage pair |
|---|---|---|---|
| single line-to-ground, 6 relays | 340 / 540 | **363 / 540** | 363 / 540 |
| phase-phase | 225 / 270 | **225 / 270** | 90 / 270 |
| double line-to-ground | 192 / 270 | **213 / 270** | 201 / 270 |
| three-phase | 270 / 270 | **270 / 270** | 270 / 270 |
| PSCAD sweep, A-G, bolted and 10 Ω | 6 / 32 | **32 / 32** | 32 / 32 |

The angle rule is never worse than the magnitude rule in any of the 72 relay × type × resistance cells.
A variant with undervoltage selection of the phase pair was tried and **rejected**: its pair rule is too
crude and loses most 10–40 Ω phase-phase faults. What both selectors still miss is high-resistance faults
seen from the weak end of a line (TestGrid relay B side, DoubleLine end 2): there the relay barely sees
the fault, which is a sensitivity limit, not a selection rule.

**The PSCAD sweep with the new selector**: the A-G loop is released at all 32 points, so the eight
in-zone faults missed before (bolted 75–84 %, 10 Ω 65–75 %) now trip. Left: the bolted fault at 85 %
reads 85.3 % (at the boundary), and 10 Ω faults at 78–85 % read 86.5–94.6 % from remote-infeed
underreach, which is for a resistive reach and tilt to deal with. The three relay cases: selector wrong
0 of 42 (was 32). Tables in `results/pscad/` are regenerated with the new selector.

**Impact on earlier results.** On the current results the change is negligible (`src/review/selector_impact.py`, plain reactance rule at 20 ms, six relays, ~15,000 records): the released loops are identical on every in-zone fault at all six relays, they differ on 1.7–17.9 % of off-line records, and 2 decisions change, both at adapt_B and both removed false trips (42 → 40 of 2,845). So the ADAPTGRID and CIGREMV conclusions stand without a re-run; the one thing not covered is whether the off-line differences move a zero-false-trip threshold of a mask-based ladder rung, which a ladder re-run at adapt_B and cigre_R3 (largest differences) would settle.


## What is not done

- One line, one source arrangement (20° load angle), A-G only, two resistances. Other fault types,
  load angles and source strengths change where the selector flips.
- The selector is **not changed** here: it is shared by every earlier result, so a fix (for example a
  sequence-angle selector, the angle of ΔI2 against ΔI0) must be re-run on all of them.
- No inverter. This was the tool check; the inverter study is the next item in PLAN.md §5.
