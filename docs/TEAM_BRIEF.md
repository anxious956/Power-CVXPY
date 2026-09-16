# Team brief

Read this once before the first meeting.

## The problem in plain words

A relay is the device that says "there's a fault, open the breaker." For a century it worked by watching for a big current spike, because generators push huge current into a fault. Solar, wind and batteries connect through inverters, and inverters cap their current at roughly 1.1 to 1.2 times normal. So in a modern grid a fault can look almost like normal load, and the relay can miss it. This is a real, unsolved industry problem and an NSF-funded project in Prof. Taylor's group.

## Taylor's idea

Since the inverter won't give big current, make it inject a small deliberate signature during a fault: a slight unbalance of the three phases, called negative-sequence current. A healthy grid has almost none, so even a small amount means "fault." His papers use convex optimization to compute the smallest signature that still guarantees the relay can tell fault from normal. All math, no simulation yet. His own paper says the next step is testing it in realistic simulation. That is our project.

## What already exists

A toy version of his method in Python with CVXPY (the tool he recommended). On a two-bus grid: with a strong generator no signature is needed; with a weak source or an inverter at the relay, high-resistance ground faults become invisible and a signature of about 0.5 pu fixes them; raise relay noise by 50 percent and the needed signature exceeds what an inverter can physically give. Runs in 40 seconds on a laptop, no GPU. See `results/RESULTS.md`.

## The four roles

1. **Optimization / design tool.** Turn the toy into a proper tool: input a grid, output the smallest signature. CVXPY, Python, some linear algebra. For whoever likes math and clean code.
2. **Simulation.** Build a realistic test grid in Simulink or PSCAD with a generator and inverters, put the signature into the inverter control, create faults, export what the relay sees. This is the data factory for everyone else. Needs someone comfortable with Simulink. Most important role.
3. **Detection.** Check whether the relay actually sees the signature under load and noise. Compare Taylor's Kalman filter detector against a neural network, and shrink the signature until each one fails. (Asmar; her ISAIA paper is exactly this kind of weak-signal detection.)
4. **Embedded / hardware.** Run the detector on a Jetson or similar board, stream simulated waveforms in, measure decision latency. A relay must decide within one cycle, about 16 ms. This gives the project its physical demo.

## What we'd find

- Where Taylor's theoretical minimum signature actually breaks in practice. Any answer is a result.
- Whether a learned detector catches a smaller signature than the filter. Any answer is a result.
- Whether these detectors are fast enough for a real relay. Nobody has measured it.

## Output

Working tool + simulation + demo by December for senior design. A conference paper in spring, most likely NAPS 2027. Taylor as advisor and likely co-author.

## What each person should do this week

- Everyone: clone the repo, run `python src/aux_signal_toy.py weak_sg`, open the PNG, read Sections I, II and VI of the Geometry paper (link in `papers/README.md`).
- Reply with: are you in, first and second role choice, Simulink experience 1 to 5.

## Vocabulary you will hear

- **Relay:** the fault-detecting device. **Trip:** its decision to open the breaker.
- **pu (per unit):** a quantity divided by its rated value. 1.0 pu = rated.
- **Synchronous generator (SG):** a rotating machine; gives 5–7 pu fault current.
- **Inverter-based resource (IBR):** solar, wind, battery; gives ~1.2 pu fault current.
- **Negative-sequence current:** the unbalanced part of three-phase current. Near zero when healthy.
- **Auxiliary signal / δ:** the deliberate injection. Design variable of the whole project.
- **Apparent impedance, R-X plane:** relay voltage over current, plotted as a point; distance relays trip when it lands in a region.
- **Zonotope:** a box mapped through a linear map; how uncertainty is modeled.
- **Farkas' lemma:** "two sets don't overlap" turned into a constraint an optimizer can satisfy.
- **EMT simulation:** electromagnetic-transient, i.e. waveform-level, simulation (PSCAD, Simulink).
- **MMKF:** multiple-model Kalman filter, the detector in Taylor's 2022 paper.
