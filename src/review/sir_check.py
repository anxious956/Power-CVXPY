"""Source-to-line impedance ratio (SIR) of the three benchmark relays, and what it implies for the
Q1 instrument-chain conclusions.

Why this matters (papers/notes/E_practitioner_settings.md section 0). Every zone-1 security concern
in the SEL settings literature -- CCVT transient overreach, ground potential rise, voltages induced
in secondary cables, dominance of steady-state errors -- is a *high-SIR* phenomenon. Kasztenny 2021
section IV makes the mechanism exact: the distance element operating signal for a fault at the
remote bus is

    |(IZ - V)| = (1 - m1) / (SIR + 1)        per unit of the nominal loop voltage

and any voltage error adds directly to it. Q1 found that class-T1 CVT and 5P20 CT errors did not
move zone-1 security. This script tests whether that null result was obtained inside or outside the
regime the literature is about.

Two SIR definitions are computed:

  impedance ratio   |Z_S| / |Z1L|, the textbook form, from the study model's Thevenin source
                    impedance behind the relay with the protected line removed;
  voltage based     Kasztenny 2021 eqs. (30a)/(30b), the definition the paper advocates because it
                    is exact for the voltage-divider model and absorbs non-homogeneity, mutual
                    coupling and infeed:
                        SIR_G = 1/V_pu(LG) - 1   from a metallic phase-to-ground fault at the remote bus
                        SIR_P = 1/V_pu(LL) - 1   from a metallic phase-to-phase fault at the remote bus
                    with V_pu the faulted-loop voltage at the relay in per unit of nominal.

    python src/review/sir_check.py            -> results/review/sir.json      (< 1 min, no EMT data)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import setting_study as ss

V_NOM_LG = 110e3 / np.sqrt(3)          # phase-to-ground nominal, rms
V_NOM_LL = 110e3                       # phase-to-phase nominal, rms
REGIMES = [(0.0, 0.5, "very strong"), (0.5, 2.0, "strong"), (2.0, 4.0, "moderate"),
           (4.0, 10.0, "weak"), (10.0, 1e9, "very weak")]


def regime(sir):
    return next(lab for lo, hi, lab in REGIMES if lo <= sir < hi)


def phase_voltages(vseq):
    """[V0, V1, V2] -> phase a, b, c."""
    return cm.AM @ np.asarray(vseq)


def sir_for(name):
    R = cm.load_relay(name, chain=dict(noise_rel=0.0, adc_bits=0))   # study model only; no EMT records used here
    net = ss.build(R["graph"])
    rb = cm.RELAY_BUS[name]
    cfg = R["cfg"]
    z1L = R["z1L"]

    # --- impedance-ratio definition, positive and negative sequence
    out = {}
    for seq in (1, 2):
        zs, zr, ztr, zl = ss.source_impedances(net, rb, cfg["line"], seq)
        out[f"Z_S_seq{seq}"] = [float(zs.real), float(zs.imag)]
        out[f"Z_R_seq{seq}"] = [float(zr.real), float(zr.imag)]
        out[f"sir_impedance_ratio_seq{seq}"] = float(abs(zs) / abs(z1L))

    # --- voltage-based definition (Kasztenny 2021 eqs. 30a/30b): metallic fault at the remote bus
    remote = cfg["remote_bus"]
    for ftype, lab, vnom in (("lg", "G", V_NOM_LG), ("ll", "P", V_NOM_LL)):
        vpo, ipo, vpr, ipr = ss.solve_fault(net, rb, cfg["line"], ("bus", remote), ftype, 0.0)
        va, vb, vc = phase_voltages(vpo)
        # faulted loop: LG solver puts the fault on phase a; LL/LLG on phases b-c
        vloop = abs(va) if ftype == "lg" else abs(vb - vc)
        vpu = float(vloop / vnom)
        out[f"V_pu_remote_bus_{lab}"] = vpu
        out[f"sir_voltage_{lab}"] = float(1.0 / vpu - 1.0) if vpu > 0 else float("inf")

    sir_g, sir_p = out["sir_voltage_G"], out["sir_voltage_P"]
    m1 = cm.REACH
    # Kasztenny 2021 eq. (25) / KC23 eq. (4): the operating-signal margin a remote-bus fault leaves
    out["reach_m1"] = float(m1)
    out["op_signal_margin_G"] = float((1 - m1) / (sir_g + 1))
    out["op_signal_margin_P"] = float((1 - m1) / (sir_p + 1))
    out["regime_G"] = regime(sir_g)
    out["regime_P"] = regime(sir_p)
    return out


def reference_table():
    """What the margin looks like across the SIR range the SEL literature addresses, at our reach."""
    m1 = cm.REACH
    return {f"{s:g}": dict(V_line_end_pu=float(1 / (s + 1)), op_signal_margin=float((1 - m1) / (s + 1)))
            for s in (0.25, 0.5, 1, 2, 5, 10, 20, 30)}


def cvt_margin(relays):
    """Kasztenny & Chowdhury 2023 eq. (6): zone 1 is transient-secure against CCVT transients when

        (1 - m1) / (SIR + 1)  >  |E_CCVT(pu)|(t)      for t beyond the relay's data window

    The CCVT residuals in results/review/cvt_class_check.json are measured for a *terminal short
    circuit*, i.e. a 100 % collapse of the loop voltage. The transient scales with the voltage
    change, so for a fault at the remote bus it is scaled by (1 - V_pu at the remote bus).
    This decides whether Q1's null result is explained by headroom or was simply not the worst case.
    """
    path = os.path.join(cm.ROOT, "results", "review", "cvt_class_check.json")
    if not os.path.exists(path):
        return None
    C = json.load(open(path))
    res = {}
    for variant, V in C.items():
        # worst residual at 20 ms over point-on-wave, for a full (100 %) voltage collapse
        worst = max(V[k]["20"] for k in V if k.endswith("terminal short circuit")) / 100.0
        res[variant] = dict(residual_20ms_full_collapse=float(worst), passes_class=V.get("passes_class"), per_relay={})
        for name, o in relays.items():
            for lab in ("G", "P"):
                dv = 1.0 - o[f"V_pu_remote_bus_{lab}"]           # voltage change at a remote-bus fault
                err = worst * dv
                marg = o[f"op_signal_margin_{lab}"]
                res[variant]["per_relay"][f"{name}|{lab}"] = dict(
                    voltage_change=float(dv), scaled_cvt_error=float(err), op_signal_margin=float(marg),
                    ratio_margin_over_error=float(marg / err) if err > 0 else float("inf"),
                    secure_by_criterion=bool(marg > err))
    return res


if __name__ == "__main__":
    out = dict(reach_m1=float(cm.REACH), commit=cm.git_commit(),
               definition_note="impedance ratio |Z_S|/|Z1L|; voltage based per Kasztenny 2021 eqs. 30a/30b",
               reference_margin_vs_sir=reference_table(), relays={})
    for name in (sys.argv[1:] or ["testgrid_A", "testgrid_B", "doubleline"]):
        out["relays"][name] = sir_for(name)
        o = out["relays"][name]
        print(f"[{name}] SIR  impedance-ratio(+) {o['sir_impedance_ratio_seq1']:5.2f}   "
              f"voltage-based G {o['sir_voltage_G']:5.2f} ({o['regime_G']})  P {o['sir_voltage_P']:5.2f} ({o['regime_P']})   "
              f"|  V at remote bus  LG {o['V_pu_remote_bus_G']*100:5.1f} %  LL {o['V_pu_remote_bus_P']*100:5.1f} %   "
              f"|  IZ-V margin at {o['reach_m1']:.2f} reach  G {o['op_signal_margin_G']*100:5.2f} %  P {o['op_signal_margin_P']*100:5.2f} %", flush=True)
    out["cvt_transient_margin"] = cvt_margin(out["relays"])
    if out["cvt_transient_margin"]:
        print("")
        print("KC23 eq. (6): CCVT residual at 20 ms, scaled by the voltage change at a remote-bus fault,")
        print("against the operating-signal margin at this reach:")
        for variant, V in out["cvt_transient_margin"].items():
            print(f"  {variant}  (T1 pass: {V['passes_class']['T1']})  full-collapse residual at 20 ms "
                  f"{V['residual_20ms_full_collapse']*100:5.2f} %")
            for k, r in V["per_relay"].items():
                print(f"     {k:>15}: scaled error {r['scaled_cvt_error']*100:5.2f} %  vs margin "
                      f"{r['op_signal_margin']*100:5.2f} %  -> {'secure' if r['secure_by_criterion'] else 'NOT SECURE'} "
                      f"(margin/error {r['ratio_margin_over_error']:.2f})")
    path = os.path.join(cm.ROOT, "results", "review", "sir.json")
    json.dump(out, open(path, "w"), indent=1)
    print("saved", path)
