# Step 3 for Prof. Taylor: summary and draft email (not sent)

17 Oct 2026. For Asmar to send if she agrees. Every number below is from EMT (PSCAD) with the designed δ injected by
the inverter, unless marked *static*. One three-bus network, faults up to 40 Ω, task: any fault vs no fault at the
relay. Full write-up: [results/STEP3_PILOT.md](../../results/STEP3_PILOT.md); design: [results/FRAMES.md](../../results/FRAMES.md).

## One-page summary

**What we built (steps 1–3 of the plan we showed you)**
- Your auxiliary-signal design on a multi-bus network, with the inverter and the relay each using their own frame:
  the inverter references δ to its measured V1, the relay to its pre-fault memory.
- The inverter in PSCAD injecting the designed δ: an averaged grid-following model, its own V1 frame, a δ-priority
  current limiter and a first-order (PLL-like) angle reference filter.
- Four detectors on one relay front end (mimic filter, starter, 3-cycle memory):
  - D1, your set-membership test (the Geometry paper's relay characteristic);
  - D2, a multiple-model test: one filter per hypothesis with the posterior update of your eq. (14), moved to the
    relay's phasor model;
  - D3, a CNN;
  - D0, a conventional incremental 50N/50Q element.

**Findings**
1. **The design holds in EMT.** At ε = 0.08 pu the design needs δ = 1.12 pu at 225° with a 10 % margin, about 93 %
   of the inverter's rating. Under it, every checked fault point stays in its set in the 2–3-cycle decision window.
   The checks cover the binding cases at their worst realisations, the angle window's edges, random inception and
   all 48 design cases. Every fault stays at least 2.40 ε from the normal set (2.20 ε needed). Two conditions:
   - the relay needs a mimic filter;
   - the inverter needs a filtered angle reference. With a bare one-cycle DFT reference it loses its frame above
     1.05 pu on bolted phase-to-phase faults: its own |V1| swings from 0.23 to 2.76 pu.
2. **With realistic noise, detection does not need the signal on this network.** With δ = 0 all four detectors,
   the conventional incremental element included, detect every pilot fault. The same holds under sampled realistic
   instrument errors (20 pilot scenarios; a sample, not a worst case).
3. **What the signal buys is your worst-case guarantee.** We counted the high-resistance A-G faults D1 detects under
   *any* noise inside the ε box (70 scenarios, Clopper–Pearson 95 %):
   - δ = 0: 33 % [19, 49];
   - ½ δ*: 93 % [80, 98];
   - ¾ δ*: 100 % [91, 100].
4. **The price of the guarantee is set by the instruments.** δ*(ε) rises steeply (*static*): 0 at ε = 0.03 pu,
   0.34 pu at 0.05, 1.12 pu at 0.08, and none within the inverter's limit from 0.10. With the instrument errors
   modelled as structured per-phase sets (*static*):
   - near-nominal accuracy (CT 1 %, VT 0.5 %): no signal at all;
   - protection-class fault-condition errors (CT 10 %, VT 6 % / 4°): about 93 % of the inverter.
5. **Against worst-case noise per detector** (a stress bound, pilot only), D1 has no worst-case miss from ¾ δ*. D2
   improves with δ but does not reach zero. D0 and the CNN do not benefit from δ.
6. **High-resistance ground faults** (results/HIGHR.md).
   - The designed signal certifies ground-fault detection up to about 160 Ω: 1.12 pu, no margin, a 5° window. It is
     verified in EMT at its witnesses, window edges and random inception. At 120 Ω it holds with a 10 % margin for
     0.82 pu.
   - In the same EMT runs, without the signal, a conventional incremental 50N element and the set test both detect
     every 120 Ω and 160 Ω ground fault. 50N's smallest score is 0.205 pu, against a 0.1 pu pickup.
   - Conventional detection fails only beyond about 250 Ω, where the design cannot certify detection.

   So again the signal buys the guarantee, not the detection.
7. **An inverter at the relay end does not change the detection answer** (*static, nominal sources*;
   results/IBR_GRID_SCREEN.md). With a grid-following inverter in place of the relay-end synchronous source, current
   elements go blind when its sequence paths are open, but 59N then sees |V0| = 0.31–0.57 pu on every hard ground
   fault. Behind a YNd transformer, 50N sees 0.44–1.2 pu; with IEEE 2800 negative-sequence current, 50Q sees
   0.10–0.18 pu. What fails from one end is selectivity: telling a fault on the line from one beyond it.

**Questions for you**
- Is "the guarantee's price is set by instrument accuracy" the result you would expect, and is it worth a write-up?
- Should step 3 go toward selectivity (fault on my line or beyond it) at an inverter-fed relay, where one end fails without the
  signal? That needs a design separating fault sets from each other. Our earlier static screen on a CIGRE MV feeder
  saw only a 2–4 point gain at 0.4 pu of δ, and your Geometry example separates fault types rather than zones, so we
  do not presume δ helps there.
- Is D2, your multiple-model structure moved to the relay's phasor model, an acceptable stand-in for your MMKF?

## Draft email

---

Subject: Step 3 results: what the designed signal buys, and what it costs

Dear Prof. Taylor,

We have reached step 3 of the plan we showed you: detection under load and noise with the designed δ injected in
EMT. A one-page summary is attached. In short:

- The design holds in PSCAD with the inverter injecting it. On our three-bus network it needs 1.12 pu, about 93 %
  of the inverter, at ε = 0.08 pu.
- With realistic noise, all our detectors, including a conventional incremental element, detect every fault
  without the signal.
- What the signal buys is your worst-case guarantee. The share of high-resistance faults that no admissible noise
  can hide rises from about a third at δ = 0 to all of them at three quarters of the design δ.
- Its price is set by the instruments: free with near-nominal accuracy, about 93 % of the inverter with
  protection-class errors under fault.

We would value your view on two things:
1. Is this worth writing up as it stands?
2. Where should step 3 go next? We checked high-resistance faults statically: where the conventional element starts
   to fail (about 160 Ω), no signal within the inverter's limit can guarantee detection either. The remaining
   candidate is selectivity at an inverter-fed relay. There conventional single-ended elements still detect faults
   but cannot tell where they are.

We also kept your multiple-model structure, moved to the relay's phasor model, and would like to know whether that
is an acceptable stand-in for your MMKF.

Best regards,
Asmar

---

Notes for Asmar, not for the email:
- Limits to say if asked: one network, faults to 40 Ω, task "any fault vs no fault", 20 pilot + 70 dense
  scenarios; the per-detector worst case is a stress bound (D2/D3 numbers are lower bounds); 80 Ω is static only.
- Withdrawn along the way (REVIEW.md §7 rows 51–53): the static δ* = 1.14 pu (EMT does not settle there); "the
  signal hurts 50Q" (an artefact of a total-I2 element); "no guarantee at class accuracy" (an artefact of a box
  error model).
- The earlier draft about D2 (docs/notes/email_taylor_step3_draft.md) was not sent; its question is folded in here.
