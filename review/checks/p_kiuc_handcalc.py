"""KIUC review: closed-form sequence-network check of static claims that do not need the project's solver.

A-G fault on Line-2 at m from Bus-2 (the IBR end), hydro off, the grid stiff behind EQ. The IBR is a current source
in the positive sequence (open in the Thevenin; its 0.29 pu pre-fault current is dropped, ~2 % on the pre-fault
voltage) and in the negative sequence either open (suppressed) or the IEEE 2800 law I2 = j K V2 at Bus-2, capped at
I_MAX (fixed point). Zero sequence: TF2 YgD puts X_TF2 to ground at Bus-2; DYg leaves no path at Bus-2.
Sequence networks: V1f + V2f + V0f = 3 Rf It with I1 = I2 = I0 = It at the fault.
Reported at the relay R2 (Bus-2, towards the line):
  (1) |I0| at R2 and |I2|/|I0| for |I2| = 0.45 pu (the report's I_Q-) and ours: does the k2 restraint
      (|I2| > 0.2 |I0|) block?                       -> KIUC.md Q1 reading "k2 depends on the inverter's I2"
  (2) z2 = Re[V2 (I2 e^{j ang Z1L})*] / |I2|^2 under the law, DYg (the EMT case): forward if < 0.4 |Z1L|
  (3) TF2's series reactance (X_TF2 = 0.06) between Bus-2 and the terminal: K_eff = K / (1 + X_TF2 K), so whether
      "their V2 is measured behind TF2" (KIUC.md candidate 1) can turn our 1.2 pu into their 0.45 pu
No project import; constants typed from KIUC.md's table (the report's Table 14).

    python review/checks/p_kiuc_handcalc.py
"""
import numpy as np

SB, VLL = 15.0, 57.1
ZB = VLL ** 2 / SB
Z_EQ1, Z_EQ0 = complex(5.91, 12.53) / ZB, complex(5.65, 18.93) / ZB
Z_L1, Z_L0 = complex(1.0433, 3.218) / ZB, complex(1.5649, 4.827) / ZB
ZS = 0.001j
X_TF2 = 0.06
I_MAX = 1.2
TH = np.angle(Z_L1)


def ag_fault(m, rf, tf2, k):
    """Returns (I2 at R2, I0 at R2, V2 at Bus-2, It). k = 0: suppressed (I2 source = 0)."""
    zg1 = ZS + Z_EQ1 + (1 - m) * Z_L1            # grid side to the fault, positive = negative
    zg0 = ZS + Z_EQ0 + (1 - m) * Z_L0            # grid side, zero
    zi0 = (1j * X_TF2 + m * Z_L0) if tf2 == "YgD" else None
    z0 = zg0 if zi0 is None else zg0 * zi0 / (zg0 + zi0)
    src = 0.0 + 0.0j
    for _ in range(500):
        # negative-sequence node F: grid via zg1 to reference, Bus-2 via m Z_L1 carrying the source current into F
        it = (1.0 + zg1 * src) / (zg1 + zg1 + z0 + 3 * rf)      # V1f = 1 - zg1 It, V2f = zg1 (src - It), V0f = -z0 It
        vf = zg1 * (src - it)
        vb = vf + m * Z_L1 * src
        new = 1j * k * vb
        if abs(new) > I_MAX:
            new = new / abs(new) * I_MAX
        if abs(new - src) < 1e-13:
            src = new
            break
        src = 0.5 * src + 0.5 * new
    i0_r2 = 0.0 if zi0 is None else it * zg0 / (zg0 + zi0)       # the share of I0 that comes up through TF2
    return src, i0_r2, vb, it


zl = abs(Z_L1)
print(f"Z1L {zl:.4f} pu at {np.degrees(TH):.1f} deg; Z2F {0.4*zl:.4f}, Z2R {0.6*zl:.4f} pu")
print("\n(1) k2 restraint at R2, TF2 YgD, A-G, hydro off, law K = 5 (the Q1 YgD static-only cells)")
for m in (0.05, 0.5, 0.8):
    for rf in (0.01 / ZB, 5.0 / ZB):
        i2, i0, v2, it = ag_fault(m, rf, "YgD", 5.0)
        _, i0s, v2s, _ = ag_fault(m, rf, "YgD", 0.0)
        print(f"  m {m:.2f} Rf {rf*ZB:5.2f} ohm | law: |I2| {abs(i2):.3f} |V2| {abs(v2):.3f} K_meas {abs(i2)/abs(v2):4.2f} "
              f"|I0|R2 {abs(i0):.3f} -> |I2|/|I0| {abs(i2)/abs(i0):.3f} ({'not blocked' if abs(i2) > 0.2*abs(i0) else 'k2 BLOCKS'})"
              f" | at 0.45 pu: {0.45/abs(i0):.3f} ({'not blocked' if 0.45 > 0.2*abs(i0) else 'k2 BLOCKS'})"
              f" | suppressed: |V2| {abs(v2s):.3f}, |I0|R2 {abs(i0s):.3f}")
print("\n(2) z2 under the law, TF2 DYg (the EMT case), bolted A-G")
for m in (0.05, 0.5, 0.8):
    i2, i0, v2, it = ag_fault(m, 0.01 / ZB, "DYg", 5.0)
    z2 = (v2 * np.conj(i2 * np.exp(1j * TH))).real / abs(i2) ** 2
    print(f"  m {m:.2f}: |I2| {abs(i2):.3f} |V2| {abs(v2):.3f} ang(I2/V2) {np.degrees(np.angle(i2/v2)):6.1f} deg, z2 {z2:+.4f} pu "
          f"-> {'forward' if z2 < 0.4*zl else 'reverse' if z2 > 0.6*zl else 'between'} "
          f"(unsaturated closed form -(1/K) sin(ang Z1L) = {-(1/5.0)*np.sin(TH):+.4f})")
print("\n(3) V2 behind TF2 (X_TF2 = 0.06): K_eff = K / (1 + X_TF2 K); |V2| at Bus-2 that the law needs")
for k in (5.0, 2.0):
    print(f"  K {k:.0f}: K_eff {k/(1+X_TF2*k):.2f}; 1.2 pu saturates when |V2|Bus-2 >= {1.2*(1+X_TF2*k)/k:.3f}; "
          f"0.45 pu needs |V2|Bus-2 = {0.45*(1+X_TF2*k)/k:.3f} pu")
i2, i0, v2, it = ag_fault(0.05, 0.01 / ZB, "DYg", 0.0)
print(f"  for scale: suppressed, bolted A-G 5 % from Bus-2, DYg: |V2| at Bus-2 = {abs(v2):.3f} pu (open-circuit V2 the law acts on)")
