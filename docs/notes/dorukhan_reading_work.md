# Dorukhan reading work: protective relaying

*17 Nov 2026*

Prof. Taylor asked us to learn what a relay is and what it does before the next meeting.
While Asmar ran the PSCAD simulation, Dorukhan worked through a 12-lesson reading plan on protection.
This file records lessons 1–5a (done so far) and lists what lessons 5b–12 will cover.

| Lesson | Topic | Status |
|---|---|---|
| 1 | Power-system basics | Done |
| 2 | Faults | Done |
| 3 | The protection system and its philosophy | Done |
| 4 | Overcurrent (50/51) | Done |
| 5a | Symmetrical components: the three sequences | Done |
| 5b | Symmetrical components: faults in sequence terms, 50N and 50Q | Next |
| 6–12 | See "Still to cover" below | To do |

---

## Part A: Foundations

### 1. Power-system basics

- **Phasors.** A 60 Hz sinusoid is written as a magnitude and an angle (for example 1∠−30°), so AC circuits can be solved with complex numbers.
- **Impedance** Z = R + jX. A transmission line is mostly series inductance, so it can be modelled as an R–L impedance that grows with length. This is why a distance relay can estimate how far away a fault is from Z = V/I.
- **Power** S = P + jQ. Reactive power Q sloshes back and forth between the source and the line's inductance and capacitance each cycle; it does no net work but loads the wires.
- **Per-unit.** Pick a base S and V, then:
  - I_base = S_base / (√3 · V_base)
  - Z_base = V_base² / S_base

  Example: 20 kV and 10 MVA give I_base = 288.7 A, so 1.2 pu is 346.4 A.
- **Stiff vs weak source.** A stiff source has a small source impedance and holds its voltage during a fault. A weak source (high source-to-line impedance ratio, SIR) does not, which makes relays struggle.

### 2. Faults

- A fault is an unintended path for current: a conductor touching ground, another phase, or both.
- **Types and how often they happen:**

  | Fault | Share of faults |
  |---|---|
  | Single line-to-ground (SLG) | 70–80% |
  | Line-to-line (LL) | 10–15% |
  | Double line-to-ground (LLG) | 5–10% |
  | Three-phase (3φ) | 2–5% |

  The three-phase fault is the rarest but usually gives the largest current.
- **Fault resistance.**
  - Arc resistance (Warrington): R ≈ 28,700 · L / I^1.4, with L the arc length in metres and I in amps.
  - Tower-footing resistance is about 5–25 Ω.
  - A *bolted* fault has zero fault resistance.
- **Why fault current is large.** The fault bypasses the load, so only the small source and line impedances limit the current. For an SLG fault:

  I_f = 3E / (Z₁ + Z₂ + Z₀ + 3R_f)
- **Inverters are different.** Their controller caps the current at about 1.2 pu, so an inverter fault current is close to normal load current.
- **Per-phase drawings.** A single-phase circuit represents a balanced (three-phase) fault, and its bottom node is the neutral, not ground.

### 3. The protection system and its philosophy

- **The chain:**
  - The CT (5 A or 1 A secondary) and VT (about 120 V) scale the line's current and voltage down for the relay.
  - The relay decides within 1–2 cycles.
  - The breaker (device 52) opens in 2–3 cycles.
- **The DC trip circuit.** The relay contact closes a circuit made of the station battery, the relay contact, the 52a auxiliary contact and the trip coil. The 52a contact opens the circuit again once the breaker has opened.
  - It runs on a battery because the AC voltage collapses during a fault, which is exactly when the breaker has to open.
- **Zones of protection** overlap around every breaker.
  - The zone edge is set by the CT a relay is wired to. Each relay uses the CT on the far side of the breaker, so the breaker sits inside both zones.
  - If the zones only touched, a fault between the CTs would be in neither zone and would be cleared only by slow remote backup.
- **Primary and backup.**
  - Local backup: breaker-failure protection (50BF).
  - Remote backup: upstream relays, with a time delay.
- **Five design goals:** dependability (trips when it should), security (doesn't trip when it shouldn't), selectivity, speed and sensitivity.
  - Failing to trip violates dependability.
  - A false trip violates security. False trips can cascade: in the 2003 Northeast blackout, zone 3 relays tripped heavily loaded lines that had no fault.

## Part B: How relays decide

### 4. Overcurrent (50/51)

- **Device 50** (instantaneous) trips as soon as I exceeds its setting. **Device 51** (time overcurrent) waits longer the smaller the current is.
- **Pickup rule:** max load < pickup < min fault, with margin. If that window doesn't exist, overcurrent protection can't work.
- **IEEE very inverse curve (C37.112):** t = TD · (19.61 / (M² − 1) + 0.491), where M = I / I_pickup and TD is the time dial.
- **Coordination.**
  - The relay nearest the fault trips first, so only its section loses power. Everything downstream of whichever breaker opens goes dark.
  - Upstream relays wait a coordination time interval (CTI) of about 0.2–0.4 s.
  - Coordinate at the largest fault current both relays see.
- **Worked example.** Radial 13.8 kV feeder with relay R1 at bus A and R2 at bus B.
  - R2: pickup 400 A, TD 0.5 → 0.42 s at 3000 A.
  - R1: pickup 600 A, TD 0.6 → 0.79 s at 3000 A, a margin of 0.36 s.
  - R1's 50 element is set at 3750 A (1.25 × the bus B fault current).
  - Check calculation: R2 at 4000 A gives M = 10, so t = 0.345 s.
- **Near inverters:**
  - Fault current is capped at 1.2 pu, about 600 A here, against about 500 A of normal load.
  - A 600 A pickup never trips.
  - A 300 A pickup trips on normal load after about 6.9 s.
  - There is no setting that gives both dependability and security.
- **Radial only.** With sources at both ends, fault current arrives from both sides, and the relay also needs to know direction (lesson 6).

### 5a. Symmetrical components: the three sequences

- **Fortescue (1918):** any three unbalanced phasors can be written as the sum of three balanced sets. The operator a = 1∠120° satisfies 1 + a + a² = 0.
- **The three sets:**
  - **Positive** (order A, B, C) is the normal grid.
  - **Negative** (order A, C, B) exists only when the system is unbalanced.
  - **Zero** has all three phases in phase. Its sum, 3I₀, must return through the neutral or ground.
- **Analysis (phase currents to sequences):**
  - I₀ = (Ia + Ib + Ic) / 3
  - I₁ = (Ia + a·Ib + a²·Ic) / 3
  - I₂ = (Ia + a²·Ib + a·Ic) / 3
- **Synthesis (sequences back to phase currents):**
  - Ia = I₀ + I₁ + I₂
  - Ib = I₀ + a²·I₁ + a·I₂
  - Ic = I₀ + a·I₁ + a²·I₂
- **Worked example.** A phase-A ground fault with Ia = 3, Ib = Ic = 0 gives I₀ = I₁ = I₂ = 1.
- **What each case looks like:**
  - A balanced load has only I₁.
  - A B-C fault has I₁ = −I₂ and I₀ = 0.
- **How a relay gets the numbers.**
  - 3I₀ is the residual current: Ia + Ib + Ic, taken from the common return of the three CTs.
  - Digital relays compute I₂ from the formula above.
  - Load is balanced, so 50N and 50Q can be set far more sensitively than phase overcurrent elements.
- **Project link.** A healthy grid has almost no negative sequence, so a known negative-sequence injection δ from an inverter stands out. IEEE 2800 (2022) requires inverters to inject controlled negative-sequence current during unbalanced faults.

---

## Still to cover

- **5b. Symmetrical components: faults in sequence terms.** How the positive, negative and zero networks connect for each fault type (series for SLG, parallel for LL and LLG), where I_f = 3E/(Z₁+Z₂+Z₀) comes from, and the 50N and 50Q elements.
- **6. Directional relays (67/32).** Telling forward faults from reverse ones; polarising quantities (voltage, negative and zero sequence).
- **7. Distance relays (21).** Z = V/I as distance to the fault; zones 1, 2 and 3; mho and quadrilateral characteristics; effects of fault resistance and infeed. This is the relay the project uses most.
- **8. Differential (87) and communication-assisted schemes.** Comparing both ends of a line, and why that needs a communication channel.
- **9. Instrument transformer limits.** CT saturation and CVT transients, and why the relay doesn't see the true current and voltage.
- **10. How inverters behave in a fault.** Synchronous generators vs inverters; current limiting; grid-following (inner and outer control loops, PLL) vs grid-forming; negative-sequence control; IEEE 2800.
- **11. Why relays fail near inverters, and Taylor's idea.** Which relays from lessons 4–8 break, and why; the auxiliary signal δ; the set-based (convex) design.
- **12. Read the repo with new eyes.** The README; Kasztenny 2022 (SEL); Taylor 2023; `papers/notes/E_practitioner_settings.md`; the 20 Oct meeting asks. Goal: explain the project in two minutes.

## Resources

- *Network Protection & Automation Guide* (GE / Alstom), free online: the chapters on fault calculation, CTs and VTs, overcurrent and distance protection.
- Blackburn & Domin, *Protective Relaying: Principles and Applications*.
- Horowitz & Phadke, *Power System Relaying*.
