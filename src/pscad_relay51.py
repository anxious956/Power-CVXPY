"""
Relay lesson 1: the smallest circuit with a real PSCAD relay block, an inverse-time overcurrent relay (51).

    source 13.8 kV - breaker BRK - CT (multimeter) - line 2 + j4 ohm - BUS2: load 2.4 MW, three-phase fault

    relay:  Iabc -> phase A -> ideal CT 200:5 -> FFT (60 Hz RMS) -> itoc51 (pickup, time dial) -> latch -> BRK

Everything is drawn in single-line view with wires, the way it is built by hand (docs/notes, Q&A 69).
Run with PSCAD's own Python, PSCAD already started by the user:

    "C:/Program Files/Python37/python.exe" src/pscad_relay51.py <name> [key=value ...]
        pickup=5 td=1 rf=0.01 fault=1 latch=1 tfault=0.5 dur=2.5 fdur=100 tlatch=100 run=1
    fdur: how long the fault lasts; tlatch: how long the trip is held (the breaker recloses after it)
"""
import os, sys, glob, math

WORK = r"D:\JOSHUA_TAYLOR_data\data\pscad_work\relay"
VLL, F0 = 13.8, 60.0                 # kV line-line RMS, Hz
XS = 0.5                             # source reactance, ohm
RL, XL = 2.0, 4.0                    # line, ohm
PLOAD = 2.4                          # MW, three-phase
CT_PRIM, CT_SEC = 200.0, 5.0         # CT 200:5
W = 2 * math.pi * F0
Y1, Y2, Y3 = 13, 33, 46              # rows: power circuit, relay, output channels


def build(pscad, name, pickup=5.0, td=1.0, rf=0.01, fault=1, latch=1, tfault=0.5, dur=2.5, fdur=100.0, tlatch=100.0):
    os.makedirs(WORK, exist_ok=True)
    if name in [p["name"] for p in pscad.projects()]:
        pscad.project(name).unload()
    for f in glob.glob(os.path.join(WORK, name + ".psc*")):
        os.remove(f)
    prj = pscad.create_case(os.path.join(WORK, name + ".pscx"))
    c = prj.canvas("Main")
    c.parameters(size="11X17", orient="LANDSCAPE")
    comp, wire = c.create_component, c.create_wire
    sig = lambda n, x, y: comp("master:datalabel", x, y, Name=n)
    note = lambda x, y, l1, l2=None: c.create_annotation(x, y, l1, l2)

    # ---- power circuit, single-line view, along row Y1 ----
    comp("master:source_3", 6, Y1, Name="SRC", Type="4", Grnd="1", View="1", Spec="0", Vm=f"{VLL} [kV]",
         f=f"{F0} [Hz]", Tc="0.05 [s]", Ph="0.0 [deg]", L=f"{XS / W:.6g} [H]", L_=f"{XS / W:.6g} [H]")
    wire((8, Y1), (12, Y1))
    comp("master:breaker3", 14, Y1, NAME="BRK", View="1", ROFF="1.0e6 [ohm]", RON="0.005 [ohm]")
    wire((16, Y1), (21, Y1))
    comp("master:multimeter", 22, Y1, MeasI="1", CurI="Iabc", Name="CT")
    wire((23, Y1), (28, Y1))
    comp("master:resistor", 28, Y1, R=f"{RL} [ohm]", Name="Rline")
    wire((30, Y1), (35, Y1))
    comp("master:inductor", 35, Y1, L=f"{XL / W:.6g} [H]", Name="Lline")
    wire((37, Y1), (42, Y1))
    wire((42, Y1), (52, Y1))
    # fault under the line end, load at the end
    wire((42, Y1), (42, Y1 + 4))
    comp("master:tpflt", 41, Y1 + 4, Name="FLT", Ctype="0", Grnd="1", View="1", RON=f"{rf} [ohm]",
         ROFF="1.0e6 [ohm]", A="1", B="1", C="1", G="1")
    # fault = 0: the fault is timed after the end of the run, so it never happens
    comp("master:tfaultn", 47, Y1 + 6, Name="FLTtime", TF=f"{tfault if fault else 1000.0} [s]", DF=f"{fdur} [s]")
    wire((43, Y1 + 6), (45, Y1 + 6))
    wire((52, Y1), (52, Y1 + 4))
    comp("master:resistive_load", 52, Y1 + 4, Name="LOAD", P=f"{PLOAD} [MW]", V=f"{VLL} [kV]", SD="0")

    # ---- relay, along row Y2 ----
    sig("Iabc", 6, Y2 - 1)
    wire((6, Y2 - 1), (9, Y2 - 1))
    comp("master:datatap", 10, Y2, Index="1", Dim="1", Type="2")          # phase A of Iabc [kA]
    wire((10, Y2), (13, Y2))
    sig("Ia", 10, Y2)
    comp("master:gain", 15, Y2, G=f"{1000.0 * CT_SEC / CT_PRIM:.6g}", Name="CT_200_5")   # kA primary -> A secondary
    wire((17, Y2), (20, Y2))
    comp("master:fft", 24, Y2, Type="1", Size="0", F=f"{F0} [Hz]", AMod="0", PMod="1", Filt="1", Track="0")
    wire((28, Y2 - 2), (31, Y2 - 2))
    comp("master:datatap", 32, Y2 - 1, Index="1", Dim="1", Type="2")      # harmonic 1 = 60 Hz magnitude
    wire((32, Y2 - 1), (34, Y2 - 1))
    wire((34, Y2 - 1), (36, Y2 - 1))
    sig("Irelay", 34, Y2 - 1)
    comp("master:itoc51", 39, Y2 - 1, Name="R51", DF="1", RS="0", IPICK=f"{pickup}", TD=f"{td}", TYPS="0", CHS="2",
         intIP="IntIP", intOP="IntOP")
    wire((41, Y2 - 1), (43, Y2 - 1))
    wire((43, Y2 - 1), (45, Y2 - 1))
    sig("TRIP51", 43, Y2 - 1)
    if latch:
        comp("master:monostable", 47, Y2 - 1, Name="LATCH", T=f"{tlatch} [s]", INTR="0")
        wire((49, Y2 - 1), (53, Y2 - 1))
        sig("BRK", 53, Y2 - 1)
    else:
        sig("BRK", 45, Y2 - 1)

    # ---- output channels ----
    pgb = {}
    for k, (n, u, lo, hi) in enumerate((("Ia", "kA", -3, 3), ("Irelay", "A", 0, 50), ("IntOP", "", 0, 1.2),
                                        ("TRIP51", "", -0.1, 1.2), ("BRK", "", -0.1, 1.2))):
        x = 8 + 9 * k
        sig(n, x, Y3)
        wire((x, Y3), (x + 2, Y3))
        pgb[n] = comp("master:pgb", x + 2, Y3, Name=n, Units=u, UseSignalName="0", Min=str(lo), Max=str(hi))

    # ---- graphs inside PSCAD, drawn live during the run (for showing it on screen) ----
    try:
        frame, g1, _ = c.create_graph(pgb["Ia"], 4, Y3 + 4)
        frame.set_parameters(title="Relay lesson 1: line current, relay current, trip and breaker",
                             markers=True, deltareadout=True, xmarker=tfault, omarker=tfault + 0.806)
        g1.set_parameters(title="line current, phase A [kA]")
        g2, _ = frame.add_overlay_graph(pgb["Irelay"])
        g2.set_parameters(title="relay current [A secondary], pickup 5 A")
        g3, _ = frame.add_overlay_graph(pgb["TRIP51"], pgb["BRK"])
        g3.set_parameters(title="TRIP51 and BRK (1 = trip / open)")
        frame.size = (50, 34)                    # grid units; the default 32 x 16 squeezes three graphs
    except Exception as e:                       # the graph is only for display; never fail the build on it
        print("graph not added:", type(e).__name__, e)

    # ---- labels ----
    for x, l1, l2 in ((7, "Source", "13.8 kV, X = 0.5 ohm"), (14, "Breaker", "BRK"), (22, "CT", "measures Iabc"),
                      (32, "Line", "2 + j4 ohm"), (42, "Fault", "three-phase, at BUS2"), (52, "Load", "2.4 MW")):
        note(x, Y1 - 5, l1, l2)
    # what each part is for, above its title (short lines: neighbours are only 7-10 squares apart)
    for x, l1, l2 in ((7, "the grid behind", "limits the current"), (14, "the switch", "opens if BRK = 1"),
                      (22, "measures current", "sent out as Iabc"), (32, "= 4.47 ohm, 63 deg", "~10 km feeder"),
                      (42, "short circuit", "on at 0.5 s"), (52, "the customers", "~98 A normally")):
        note(x, Y1 - 8, l1, l2)
    for x, l1, l2 in ((8, "Phase A", "current [kA]"), (14, "Ideal CT", "200:5"), (22, "FFT", "60 Hz RMS"),
                      (30, "60 Hz", "magnitude [A]"), (37, "51 relay", "pickup, time dial"), (45, "Latch", "trip stays 1")):
        note(x, Y2 - 7, l1, l2)
    for x, l1, l2 in ((8, "picks phase A", "from Iabc"), (14, "kA x 1000 / 40", "= x 25"),
                      (22, "size of the", "60 Hz wave"), (30, "Irelay", "2.45 A -> 40.4 A"),
                      (37, "5 A, TD 1,", "very inverse"), (45, "holds trip at 1", "(like relay 86)")):
        note(x, Y2 - 10, l1, l2)
    note(30, Y1 - 11, "Relay lesson 1: overcurrent relay (51) on a 13.8 kV feeder",
         "the rows are linked by name: Iabc (CT to relay), BRK (relay to breaker)")
    note(3, Y3 - 3, "Output channels", None)
    prj.parameters(time_duration=str(dur), time_step="50", sample_step="250", PlotType="OUT",
                   output_filename=name + ".out")
    prj.save()
    return prj


if __name__ == "__main__":
    import mhi.pscad
    name = sys.argv[1]
    kw = dict(a.split("=") for a in sys.argv[2:])
    run = int(kw.pop("run", 1))
    kw = {k: (int(v) if k in ("fault", "latch") else float(v)) for k, v in kw.items()}
    pscad = mhi.pscad.application()
    if not pscad.licensed():
        pscad.get_certificate(list(pscad.get_available_certificates().values())[0])
    prj = build(pscad, name, **kw)
    print("built", prj.name, kw)
    if run:
        prj.run()
        print("run done")
