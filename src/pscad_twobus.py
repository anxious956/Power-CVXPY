"""
The two-bus circuit of the design tool (src/aux_model.py), built in PSCAD from Python, so the design
and the EMT test describe the same circuit (step 2 of the plan, with step 1's model).

  bus L: weak synchronous source (EMF 1 pu, zs1 = zs2 = 0.4j, zs0 = 0.8j)
  line : z1 = 0.02 + 0.2j, z0 = 3 z1, fault at fraction m from L (ag on phase A, or the design's 'ab',
         which is the phase-phase fault symmetric about phase A, i.e. B-C here)
  bus R: ungrounded load 1 + 0.3j, and the averaged inverter (src/pscad_inverter.py) injecting I1 and the
         negative-sequence signal; its zero-sequence path is open (delta-side interconnection)
Base: 10 MVA, 20 kV line-to-line, Zbase = 40 ohm. The relay measures V and I at bus L, into the line.

z0 != z1 on the line is built with a separate ground-return conductor, chained like the line: phase
conductors carry z1, the return carries (z0 - z1) / 3, so a segment's zero-sequence impedance is
z1 + 3 (z0 - z1) / 3 = z0. Exact here because every ground connection of the circuit sits on that chain
(source neutral at L, fault at F; nothing is grounded at R).

    "C:/Program Files/Python37/python.exe" src/pscad_twobus.py name=tb_ag m=0.55 scen=ag rf=0
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pscad_inverter import WORK, INPUTS, OUTPUTS, port_xy, definition_xml, Builder, run

F0 = 60.0
W = 2 * math.pi * F0
SBASE, VLL = 10.0, 20.0
ZBASE = VLL ** 2 / SBASE                       # 40 ohm
VBASE_PK = VLL / math.sqrt(3) * math.sqrt(2)   # kV
IBASE_PK = SBASE / (math.sqrt(3) * VLL) * math.sqrt(2)  # kA
Z1_LINE = complex(0.02, 0.20) * ZBASE
Z0_LINE = 3.0 * Z1_LINE
ZN_LINE = (Z0_LINE - Z1_LINE) / 3.0
ZS1, ZS0 = 0.4 * ZBASE, 0.8 * ZBASE           # source reactances (ohm)
Z_LOAD = complex(1.0, 0.3) * ZBASE


def _rl(b, a_node, b_node, z, x, y, tag):
    """Series R then L between two nodes; R and L skipped when (near) zero."""
    mid = f"{a_node}_{tag}"
    b.series("master:resistor", a_node, mid, x, y, R=f"{max(z.real, 1e-6):.6g} [ohm]")
    b.series("master:inductor", mid, b_node, x + 4, y, L=f"{max(z.imag, 1e-6) / W:.6g} [H]")


def build(pscad, name, m=0.5, scen="N", rf=0.0, t_fault=0.30, dur=0.10, idref=0.9 * math.cos(math.radians(15)),
          iqref=0.9 * math.sin(math.radians(15)), mode2=0, k2=2.0, d2mag=0.0, d2ang=0.0, t_end=0.5,
          dt_us=10.0):
    os.makedirs(WORK, exist_ok=True)
    if name in [p["name"] for p in pscad.projects()]:
        pscad.project(name).unload()
    for f in os.listdir(WORK):
        if f.startswith(name + ".psc"):
            os.remove(os.path.join(WORK, f))
    prj = pscad.create_case(os.path.join(WORK, name + ".pscx"))
    defn = prj.create_definition(definition_xml())
    c = prj.canvas("Main")
    b = Builder(c)

    # source at bus L; neutral port is at (-2,0) or (-4,0) depending on the view: ground both
    b.comp("master:source3", 10, 10, Name="SG", Ctrl="0", View="0", MVA=f"{SBASE} [MVA]", Vm=f"{VLL} [kV]",
           F=f"{F0} [Hz]", Es=f"{VLL} [kV]", F0=f"{F0} [Hz]", Ph="0.0 [deg]", Term="0", Type="2", Imp="1", ZSeq="1",
           Z1=f"{ZS1} [ohm]", Phi1="89.99 [deg]", Z0=f"{ZS0} [ohm]", Phi0="89.99 [deg]", Tc="0.01 [s]")
    b.ground(8, 10)
    b.ground(6, 10)
    for k, ph in enumerate("ABC"):
        b.node("L" + ph, 12, 8 + 2 * k)

    za, zb = m * Z1_LINE, (1 - m) * Z1_LINE
    for k, ph in enumerate("ABC"):
        y = 20 + 4 * k
        b.comp("master:voltmetergnd", 4, y, Name="VL" + ph)
        b.node("L" + ph, 4, y)
        b.comp("master:ammeter", 8, y, Name="IL" + ph)          # relay current, bus L into the line
        b.node("L" + ph, 8, y)
        b.node("L1" + ph, 10, y)
        _rl(b, "L1" + ph, "F" + ph, za, 14, y, "a")
        _rl(b, "F" + ph, "R" + ph, zb, 24, y, "b")
        # load at R: R-L to an ungrounded neutral
        _rl(b, "R" + ph, "NLD", Z_LOAD, 34, y, "ld")
        # inverter at R
        b.comp("master:voltmetergnd", 46, y, Name="VR" + ph)
        b.node("R" + ph, 46, y)
        b.comp("master:ammeter", 50, y, Name="Iinv" + ph)
        b.node("R" + ph, 50, y)
        b.comp("master:src_ccin_1", 52, y, Name="Cinv" + ph, Cntrl="1", f="0.0 [Hz]", Vm="1.0 [kA]",
               Tc="0.0 [s]", Ph="0.0 [deg]")
        b.ground(54, y)
        b.sig("IREF" + ph, 52, y + 2)
    # ungrounded load neutral: a 1 Mohm leak to ground keeps the node defined
    b.series("master:resistor", "NLD", "GNLD", 40, 36, R="1.0e6 [ohm]")
    b.ground(42, 36)
    # ground-return conductor, segment a (L -> F); grounded at L
    zn_a = m * ZN_LINE
    b.comp("master:resistor", 14, 36, R=f"{max(zn_a.real, 1e-6):.6g} [ohm]")
    b.ground(14, 36)
    b.node("GMA", 16, 36)
    b.series("master:inductor", "GMA", "GF", 18, 36, L=f"{max(zn_a.imag, 1e-6) / W:.6g} [H]")

    # fault at F
    if scen in ("ag", "ab"):
        b.comp("master:tbreakn", 70, 40, Name="FLTT", NUMS="2", INIT="1", TO1=f"{t_fault} [s]",
               TO2=f"{t_fault + dur} [s]")
        b.sig("FLT", 68, 40)                                 # tbreakn output Sig at (-2, 0)
        r = max(rf, 1e-3)
        if scen == "ag":                                      # A to ground through rf
            b.comp("master:breaker1", 30, 44, NAME="FLT", RON=f"{r:.6g} [ohm]", ROFF="1.0e8 [ohm]", BOpen="2")
            b.node("GF", 28, 44)                              # breaker1: B at (-2,0), A at (+2,0)
            b.node("FA", 32, 44)
        else:                                                 # the design's 'ab' = B-C here, rf between them
            for k, ph in enumerate("BC"):
                y = 44 + 4 * k
                b.comp("master:breaker1", 30, y, NAME="FLT", RON=f"{r / 2:.6g} [ohm]", ROFF="1.0e8 [ohm]", BOpen="2")
                b.node("FN", 28, y)
                b.node("F" + ph, 32, y)
            b.series("master:resistor", "FN", "GFN", 30, 54, R="1.0e8 [ohm]")
            b.ground(32, 54)

    # inverter controller
    cx, cy = 90, 30
    c.create_component(defn, cx, cy)
    values = dict(F0=F0, ID=idref, IQ=iqref, MODE2=float(mode2), K2=k2, D2MAG=d2mag, D2ANG=d2ang,
                  IBASE=IBASE_PK, VBASE=VBASE_PK, IMAX=1.2)
    for p in INPUTS:
        px, py = port_xy(p)
        gx, gy = cx + px // 18, cy + py // 18
        if p in ("VA", "VB", "VC"):
            b.sig("VR" + p[1], gx, gy)
        else:
            b.comp("master:const", gx - 2, gy, Value=str(values[p]))
    for p in OUTPUTS:
        px, py = port_xy(p)
        gx, gy = cx + px // 18, cy + py // 18
        b.sig("IREF" + p[1] if p in ("IA", "IB", "IC") else p, gx, gy)

    row = 70
    chans = [("VL" + p, "kV") for p in "ABC"] + [("IL" + p, "kA") for p in "ABC"] + \
            [("VR" + p, "kV") for p in "ABC"] + [("Iinv" + p, "kA") for p in "ABC"] + \
            [(n, "pu") for n in ("V1M", "V2M", "I1M", "I2M")]
    for nm, u in chans:
        b.channel(nm, 10, row, u, -50, 50)
        row += 3
    prj.parameters(time_duration=str(t_end), time_step=str(dt_us), sample_step="50", PlotType="OUT",
                   output_filename=name + ".out")
    prj.save()
    return prj


if __name__ == "__main__":
    import mhi.pscad
    kw = dict(a.split("=", 1) for a in sys.argv[1:])
    name = kw.pop("name", "tb_test")
    scen = kw.pop("scen", "N")
    args = {k: float(v) for k, v in kw.items()}
    pscad = mhi.pscad.application()
    prj = build(pscad, name, scen=scen, **args)
    dt, errs = run(prj)
    print(f"{name}: run {dt:.1f} s, {len(errs)} errors")
    for e in errs[:8]:
        print("  ", e[:300])
