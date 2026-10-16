"""
An averaged, grid-following inverter for PSCAD whose negative-sequence current is ours to set, built
entirely from Python (PSCAD's own Python 3.7 with mhi.pscad, PSCAD open).

Power stage: three master:src_ccin_1 controlled current sources (f = 0, external control), one per
phase, from the PCC node (port A) to ground (port B). Verified separately: such a source injects
exactly its instantaneous control input.

Control: one user component, gfl_avm, written here in Fortran:
  - a one-cycle sliding DFT of the PCC phase voltages gives V1 and V2 (peak phasors, absolute frame
    e^{j w t}, fixed frequency F0: no PLL dynamics);
  - positive sequence I1 = Ibase (ID - j IQ) e^{j angle V1}   (IQ > 0 supplies reactive power);
  - negative sequence, MODE2:
        0  suppressed, I2 = 0
        1  IEEE 2800 style, V2-referenced: I2 = j K2 Ibase V2 / Vbase   (I2 leads V2 by 90 deg)
        2  a designed delta, fixed in the V1 frame: I2 = D2MAG Ibase e^{j (angle V1 + D2ANG)}
  - phase-peak current limit IMAX (pu of Ibase). LIM = 0: I1 and I2 scaled together. LIM = 1: I2 priority,
    I2 kept and I1 alone scaled down until every phase peak fits (I1 and I2 scaled together only if I2
    alone exceeds the limit). LIM = 1 is the limiter the TAC25 design with the limit inside assumes:
    the inverter delivers the full delta and only positive-sequence realisations that fit beside it occur;
  - references ramp in over the third cycle (the DFT needs one full cycle first).
Outputs: the three phase current references (kA) and |V1|, |V2| (pu of Vbase), |I1|, |I2| (pu of Ibase).

PSCAD cannot build a new project on a path with non-ASCII characters or through the data/ junction:
keep projects under D:\\JOSHUA_TAYLOR_data\\data\\pscad_work\\.

    "C:/Program Files/Python37/python.exe" src/pscad_inverter.py test
"""
import os, sys, glob, time, random
import xml.etree.ElementTree as ET

WORK = r"D:\JOSHUA_TAYLOR_data\data\pscad_work\inverter"

INPUTS = ["VA", "VB", "VC", "F0", "ID", "IQ", "MODE2", "K2", "D2MAG", "D2ANG", "IBASE", "VBASE", "IMAX", "LIM"]
OUTPUTS = ["IA", "IB", "IC", "V1M", "V2M", "I1M", "I2M"]
NMAX = 1700                                   # samples per cycle the DFT buffer can hold
NSTOR = 7 + 6 * NMAX + 3

FORTRAN = """#STORAGE REAL:%(nstor)d
#LOCAL INTEGER G_NS
#LOCAL INTEGER G_K
#LOCAL INTEGER G_IP
#LOCAL INTEGER G_J
#LOCAL REAL G_W
#LOCAL REAL G_CW
#LOCAL REAL G_SW
#LOCAL REAL G_RA
#LOCAL REAL G_XA
#LOCAL REAL G_RB
#LOCAL REAL G_XB
#LOCAL REAL G_RC
#LOCAL REAL G_XC
#LOCAL REAL G_V1R
#LOCAL REAL G_V1I
#LOCAL REAL G_V2R
#LOCAL REAL G_V2I
#LOCAL REAL G_CA
#LOCAL REAL G_SA
#LOCAL REAL G_AN
#LOCAL REAL G_I1R
#LOCAL REAL G_I1I
#LOCAL REAL G_I2R
#LOCAL REAL G_I2I
#LOCAL REAL G_PK
#LOCAL REAL G_SC
#LOCAL REAL G_RMP
#LOCAL REAL G_PAR
#LOCAL REAL G_PAI
#LOCAL REAL G_PBR
#LOCAL REAL G_PBI
#LOCAL REAL G_PCR
#LOCAL REAL G_PCI
#LOCAL REAL G_S1
#LOCAL REAL G_QA
#LOCAL REAL G_QB
#LOCAL REAL G_QC
#LOCAL REAL G_QR
#LOCAL REAL G_QI
#LOCAL REAL G_RR
#LOCAL REAL G_RI
#LOCAL REAL G_LL
#LOCAL REAL G_SK
      G_W  = 6.283185307*$F0
      G_NS = NINT(1.0/($F0*DELT))
      IF (G_NS .GT. %(nmax)d) G_NS = %(nmax)d
      G_IP = NINT(STORF(NSTORF))
      G_CW = COS(G_W*TIME)
      G_SW = SIN(G_W*TIME)
      G_J  = NSTORF + 7 + 6*G_IP
      DO G_K = 0, 5
        STORF(NSTORF+1+G_K) = STORF(NSTORF+1+G_K) - STORF(G_J+G_K)
      END DO
      STORF(G_J)   =  $VA*G_CW
      STORF(G_J+1) = -$VA*G_SW
      STORF(G_J+2) =  $VB*G_CW
      STORF(G_J+3) = -$VB*G_SW
      STORF(G_J+4) =  $VC*G_CW
      STORF(G_J+5) = -$VC*G_SW
      DO G_K = 0, 5
        STORF(NSTORF+1+G_K) = STORF(NSTORF+1+G_K) + STORF(G_J+G_K)
      END DO
      G_IP = G_IP + 1
      IF (G_IP .GE. G_NS) G_IP = 0
      STORF(NSTORF) = REAL(G_IP)
      G_RA = 2.0*STORF(NSTORF+1)/G_NS
      G_XA = 2.0*STORF(NSTORF+2)/G_NS
      G_RB = 2.0*STORF(NSTORF+3)/G_NS
      G_XB = 2.0*STORF(NSTORF+4)/G_NS
      G_RC = 2.0*STORF(NSTORF+5)/G_NS
      G_XC = 2.0*STORF(NSTORF+6)/G_NS
      G_V1R = (G_RA - 0.5*G_RB - 0.8660254*G_XB - 0.5*G_RC
     & + 0.8660254*G_XC)/3.0
      G_V1I = (G_XA + 0.8660254*G_RB - 0.5*G_XB - 0.8660254*G_RC
     & - 0.5*G_XC)/3.0
      G_V2R = (G_RA - 0.5*G_RB + 0.8660254*G_XB - 0.5*G_RC
     & - 0.8660254*G_XC)/3.0
      G_V2I = (G_XA - 0.8660254*G_RB - 0.5*G_XB + 0.8660254*G_RC
     & - 0.5*G_XC)/3.0
      G_AN = ATAN2(G_V1I, G_V1R + 1.0E-12)
      G_CA = COS(G_AN)
      G_SA = SIN(G_AN)
      G_I1R = $IBASE*($ID*G_CA + $IQ*G_SA)
      G_I1I = $IBASE*($ID*G_SA - $IQ*G_CA)
      G_I2R = 0.0
      G_I2I = 0.0
      IF ($MODE2 .GT. 0.5 .AND. $MODE2 .LT. 1.5) THEN
        G_I2R = -$K2*$IBASE*G_V2I/$VBASE
        G_I2I =  $K2*$IBASE*G_V2R/$VBASE
      ELSE IF ($MODE2 .GT. 1.5) THEN
        G_I2R = $D2MAG*$IBASE*COS(G_AN + 0.017453293*$D2ANG)
        G_I2I = $D2MAG*$IBASE*SIN(G_AN + 0.017453293*$D2ANG)
      END IF
      IF ($LIM .GT. 0.5) THEN
        G_LL = ($IMAX*$IBASE)**2
        G_S1 = 1.0
        DO G_K = 0, 2
          IF (G_K .EQ. 0) THEN
            G_QR = G_I1R
            G_QI = G_I1I
            G_RR = G_I2R
            G_RI = G_I2I
          ELSE IF (G_K .EQ. 1) THEN
            G_QR = -0.5*G_I1R + 0.8660254*G_I1I
            G_QI = -0.8660254*G_I1R - 0.5*G_I1I
            G_RR = -0.5*G_I2R - 0.8660254*G_I2I
            G_RI = 0.8660254*G_I2R - 0.5*G_I2I
          ELSE
            G_QR = -0.5*G_I1R - 0.8660254*G_I1I
            G_QI = 0.8660254*G_I1R - 0.5*G_I1I
            G_RR = -0.5*G_I2R + 0.8660254*G_I2I
            G_RI = -0.8660254*G_I2R - 0.5*G_I2I
          END IF
          G_QA = G_QR**2 + G_QI**2
          G_QB = G_QR*G_RR + G_QI*G_RI
          G_QC = G_RR**2 + G_RI**2 - G_LL
          IF (G_QC .LT. 0.0 .AND. G_QA .GT. 1.0E-12) THEN
            G_SK = (-G_QB + SQRT(G_QB**2 - G_QA*G_QC))/G_QA
            IF (G_SK .LT. G_S1) G_S1 = G_SK
          END IF
        END DO
        IF (G_S1 .LT. 0.0) G_S1 = 0.0
        G_I1R = G_S1*G_I1R
        G_I1I = G_S1*G_I1I
      END IF
      G_PAR = G_I1R + G_I2R
      G_PAI = G_I1I + G_I2I
      G_PBR = -0.5*G_I1R + 0.8660254*G_I1I - 0.5*G_I2R
     & - 0.8660254*G_I2I
      G_PBI = -0.8660254*G_I1R - 0.5*G_I1I + 0.8660254*G_I2R
     & - 0.5*G_I2I
      G_PCR = -0.5*G_I1R - 0.8660254*G_I1I - 0.5*G_I2R
     & + 0.8660254*G_I2I
      G_PCI =  0.8660254*G_I1R - 0.5*G_I1I - 0.8660254*G_I2R
     & - 0.5*G_I2I
      G_PK = MAX(SQRT(G_PAR**2 + G_PAI**2), SQRT(G_PBR**2
     & + G_PBI**2))
      G_PK = MAX(G_PK, SQRT(G_PCR**2 + G_PCI**2))
      G_SC = 1.0
      IF (G_PK .GT. $IMAX*$IBASE) G_SC = $IMAX*$IBASE/G_PK
      G_RMP = (TIME*$F0 - 2.0)
      IF (G_RMP .LT. 0.0) G_RMP = 0.0
      IF (G_RMP .GT. 1.0) G_RMP = 1.0
      $IA = G_SC*G_RMP*(G_PAR*G_CW - G_PAI*G_SW)
      $IB = G_SC*G_RMP*(G_PBR*G_CW - G_PBI*G_SW)
      $IC = G_SC*G_RMP*(G_PCR*G_CW - G_PCI*G_SW)
      $V1M = SQRT(G_V1R**2 + G_V1I**2)/$VBASE
      $V2M = SQRT(G_V2R**2 + G_V2I**2)/$VBASE
      $I1M = G_SC*G_RMP*SQRT(G_I1R**2 + G_I1I**2)/$IBASE
      $I2M = G_SC*G_RMP*SQRT(G_I2R**2 + G_I2I**2)/$IBASE
      NSTORF = NSTORF + %(nstor)d
""" % dict(nstor=NSTOR, nmax=NMAX)


def _rid():
    return str(random.randint(100000000, 2000000000))


def port_xy(name):
    """Port position in px relative to the component origin (inputs left, outputs right)."""
    if name in INPUTS:
        return -90, -108 + 18 * INPUTS.index(name)
    return 90, -54 + 18 * OUTPUTS.index(name)


def definition_xml(name="gfl_avm"):
    d = ET.Element("Definition", classid="UserCmpDefn", name=name, group="", url="", version="", build="",
                   crc="0", instances="0", key="", view="false", date="0", id=_rid())
    pl = ET.SubElement(d, "paramlist")
    ET.SubElement(pl, "param", name="Description", value="Averaged grid-following inverter, settable I2")
    ET.SubElement(d, "form", name="", w="320", h="400", splitter="60")
    svg = ET.SubElement(d, "svg", viewBox="-200 -200 200 200")
    for p in INPUTS + OUTPUTS:
        x, y = port_xy(p)
        e = ET.SubElement(svg, "port", model="Transfer", name=p, x=str(x), y=str(y), dim="1",
                          mode="Input" if p in INPUTS else "Output", type="Real", internal="")
        e.text = "true"
    ET.SubElement(svg, "rect", x="-72", y="-126", width="144", height="270", stroke="Black",
                  **{"stroke-dasharray": "none", "stroke-width": "0.2", "fill-style": "Hollow",
                     "fill-fg": "Black", "fill-bg": "", "port": ""})
    t = ET.SubElement(svg, "text", x="0", y="0", stroke="Black", fill="Black",
                      **{"font-size": "Small", "text-anchor": "Middle"})
    t.text = "GFL AVM"
    sc = ET.SubElement(d, "script")
    seg = ET.SubElement(sc, "segment", name="Fortran", id=_rid(), classid="CoreSegment")
    seg.text = FORTRAN
    ET.SubElement(sc, "segment", name="Branch", id=_rid(), classid="CoreSegment")
    ET.SubElement(sc, "segment", name="Computations", id=_rid(), classid="CoreSegment")
    g = ET.SubElement(d, "graphics")
    ET.SubElement(g, "paramlist")
    for p in INPUTS + OUTPUTS:
        x, y = port_xy(p)
        P = ET.SubElement(g, "Port", id=_rid(), classid="Port", x=str(x), y=str(y))
        ppl = ET.SubElement(P, "paramlist")
        for k, v in (("name", p), ("internal", "false"), ("cond", "true"),
                     ("mode", "1" if p in INPUTS else "2"), ("datatype", "3"), ("electype", "0"), ("dim", "1")):
            ET.SubElement(ppl, "param", name=k, value=v)
    gx = ET.SubElement(g, "Gfx", classid="Graphics.Rectangle", id=_rid(), x="-72", y="-126", w="144", h="270")
    gpl = ET.SubElement(gx, "paramlist")
    for k, v in (("color", "Black"), ("dasharray", "0"), ("thickness", "0"), ("port", ""), ("fill_style", "0"),
                 ("fill_fg", "Black"), ("fill_bg", "White"), ("cond", "true")):
        ET.SubElement(gpl, "param", name=k, value=v)
    return ET.tostring(d, encoding="unicode")


class Builder:
    """Places components in grid units (18 px) and joins them by node labels (electrical) and
    data labels (signals) dropped exactly on ports."""

    def __init__(self, canvas):
        self.c = canvas

    def comp(self, defn, x, y, **p):
        return self.c.create_component(defn, x, y, **p)

    def node(self, name, x, y):
        self.comp("master:nodelabel", x, y, Name=name)

    def sig(self, name, x, y):
        self.comp("master:datalabel", x, y, Name=name)

    def ground(self, x, y):
        self.comp("master:ground", x, y)

    def series(self, defn, a, b, x, y, **p):
        """Two-terminal element with ports A (0,0) and B (+2,0) between nodes a and b."""
        self.comp(defn, x, y, **p)
        self.node(a, x, y)
        self.node(b, x + 2, y)

    def channel(self, name, x, y, units="", lo=-1, hi=1):
        self.sig(name, x, y)
        self.comp("master:pgb", x, y, Name=name, Units=units, Min=str(lo), Max=str(hi))


def build_test(pscad, name="inv_test", mode2=0, k2=2.0, d2mag=0.1, d2ang=90.0, idref=0.8, iqref=0.0,
               fault=None, unbalance_ohm=None):
    """Stiff 20 kV source - R-L line - PCC with the inverter (10 MVA). fault: None or
    (start_s, duration_s, R_ohm) for a phase-A-to-ground fault at the PCC (not yet built).
    unbalance_ohm: a steady resistor from phase A of the PCC to ground, to create V2."""
    os.makedirs(WORK, exist_ok=True)
    if name in [p["name"] for p in pscad.projects()]:
        pscad.project(name).unload()
    for f in glob.glob(os.path.join(WORK, name + ".psc*")):
        os.remove(f)
    prj = pscad.create_case(os.path.join(WORK, name + ".pscx"))
    defn = prj.create_definition(definition_xml())
    c = prj.canvas("Main")
    b = Builder(c)
    vb_ll = 20.0                                      # kV
    vbase_pk = vb_ll / 3 ** 0.5 * 2 ** 0.5            # kV, phase peak
    ibase_pk = 10.0 / (3 ** 0.5 * vb_ll) * 2 ** 0.5   # kA peak for 10 MVA

    # source: A, B, C at (+2,-2), (+2,0), (+2,+2); neutral at (-2,0) or (-4,0) depending on the view
    b.comp("master:source3", 10, 10, Name="Grid", Ctrl="0", View="0", MVA="100.0 [MVA]", Vm="20.0 [kV]",
           F="60.0 [Hz]", Es="20.0 [kV]", F0="60.0 [Hz]", Ph="0.0 [deg]", Imp="1", Z1="0.5 [ohm]",
           Phi1="85.0 [deg]", Tc="0.01 [s]")
    b.ground(8, 10)
    b.ground(6, 10)
    for k, ph in enumerate("ABC"):
        b.node("S" + ph, 12, 8 + 2 * k)
        y = 20 + 4 * k                                # one row per phase for the line
        b.series("master:resistor", "S" + ph, "M" + ph, 10, y, R="0.5 [ohm]")
        b.series("master:inductor", "M" + ph, "P" + ph, 14, y, L="0.01 [H]")
        # inverter phase: ammeter P -> Q, controlled current source Q -> ground
        b.comp("master:ammeter", 20, y, Name="Iinv" + ph)
        b.node("P" + ph, 20, y)
        b.comp("master:src_ccin_1", 22, y, Name="Cinv" + ph, Cntrl="1", f="0.0 [Hz]", Vm="1.0 [kA]",
               Tc="0.0 [s]", Ph="0.0 [deg]")
        b.ground(24, y)
        b.sig("IREF" + ph, 22, y + 2)
        b.comp("master:voltmetergnd", 30, y, Name="V" + ph)
        b.node("P" + ph, 30, y)
    if unbalance_ohm:
        b.series("master:resistor", "PA", "G0", 40, 20, R=f"{unbalance_ohm} [ohm]")
        b.ground(42, 20)
    # control component at (60, 30); ports at x -/+ 5 grid, y from the port table
    cx, cy = 60, 30
    c.create_component(defn, cx, cy)
    values = dict(F0=60.0, ID=idref, IQ=iqref, MODE2=float(mode2), K2=k2, D2MAG=d2mag, D2ANG=d2ang,
                  IBASE=ibase_pk, VBASE=vbase_pk, IMAX=1.2, LIM=0.0)
    for p in INPUTS:
        px, py = port_xy(p)
        gx, gy = cx + px // 18, cy + py // 18
        if p in ("VA", "VB", "VC"):
            b.sig("V" + p[1], gx, gy)
        else:
            b.comp("master:const", gx - 2, gy, Value=str(values[p]))
    for p in OUTPUTS:
        px, py = port_xy(p)
        gx, gy = cx + px // 18, cy + py // 18
        b.sig("IREF" + p[1] if p in ("IA", "IB", "IC") else p, gx, gy)
    # channels
    row = 70
    for name_, u in [("V" + ph, "kV") for ph in "ABC"] + [("Iinv" + ph, "kA") for ph in "ABC"] + \
                    [("IREF" + ph, "kA") for ph in "ABC"] + [(n, "pu") for n in ("V1M", "V2M", "I1M", "I2M")]:
        b.channel(name_, 10, row, u, -50, 50)
        row += 3
    prj.parameters(time_duration="0.3", time_step="20", sample_step="50", PlotType="OUT",
                   output_filename=name + ".out")
    prj.save()
    return prj


def run(prj):
    t0 = time.time()
    prj.run()
    errs = [str(m.text) for m in prj.messages() if m.status == "error"]
    return time.time() - t0, errs


if __name__ == "__main__":
    import mhi.pscad
    pscad = mhi.pscad.application()
    kw = dict(a.split("=") for a in sys.argv[2:])
    prj = build_test(pscad, name=kw.pop("name", "inv_test"), **{k: float(v) for k, v in kw.items()})
    dt, errs = run(prj)
    print(f"run {dt:.1f} s, {len(errs)} errors")
    for e in errs[:10]:
        print("  ", e[:300])
    for m in prj.messages():
        if m.status == "warning":
            print("  warning:", str(m.text)[:200])
