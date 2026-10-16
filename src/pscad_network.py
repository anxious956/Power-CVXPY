"""
Any design-tool network (src/network.py) built in PSCAD from Python, so the circuit the design tool solves
and the circuit EMT simulates are the same by construction.

  - each bus X has phase nodes XA, XB, XC and a local ground-return node G_X;
  - a line a-b is R-L per phase with z1, plus a ground-return conductor (z0 - z1) / 3 from G_a to G_b, so a
    segment's zero-sequence impedance is z1 + 3 (z0 - z1)/3 = z0. Exact for a RADIAL network, or a meshed one
    whose lines all have the same (z0 - z1) / z1; otherwise the phase-sum and return currents obey separate
    loop laws and the zero-sequence response is wrong (review/NETWORK_REVIEW.md finding 2: 1.9e-2 pu on a test
    loop), and `build` refuses it. Grounded elements tie to the return node of their own bus (synchronous-
    source neutrals, the fault); one return node (the first synchronous source's bus) is tied to earth. The
    inverter sources are phase-to-earth, harmless because their references carry no zero sequence;
  - synchronous sources: source3, inductive, z1 = z2 and z0 from the network, neutral on G_X;
  - loads: wye R-L, neutral not grounded (the network's zero-sequence load admittance must be 0);
  - inverters: the averaged inverter of src/pscad_inverter.py (three controlled current sources and its
    Fortran controller); its zero-sequence path must be open (zero_z large), as in the two-bus build;
  - the relay: voltmeters on the relay bus phases and on its return node (v = v_phase - v_G) and ammeters
    from the bus into the relay line.

Base 10 MVA, 20 kV, Zbase = 40 ohm, 60 Hz. Projects live under D:\\JOSHUA_TAYLOR_data\\data\\pscad_work\\
(PSCAD cannot build on a non-ASCII or junction path).

Two halves, because PSCAD's own Python 3.7 has no numpy: `make_spec` (a Python with numpy; uses the design
model) writes each run as plain numbers; `build` (PSCAD's Python, standard library only) builds from it.

    python src/pscad_network.py spec <specs.json>                                  (the three-bus check cases)
    "C:/Program Files/Python37/python.exe" src/pscad_network.py run <specs.json>   (build and run them)
"""
import os, sys, math, cmath, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WORK = r"D:\JOSHUA_TAYLOR_data\data\pscad_work\network"
F0 = 60.0
W = 2 * math.pi * F0
SBASE, VLL = 10.0, 20.0
ZBASE = VLL ** 2 / SBASE
VBASE_PK = VLL / math.sqrt(3) * math.sqrt(2)
IBASE_PK = SBASE / (math.sqrt(3) * VLL) * math.sqrt(2)


def _c(z):
    z = complex(z)
    return [z.real, z.imag]


def _z(v):
    return complex(v[0], v[1])


# ------------------------------------------------------------------ spec side (numpy, design model)
def inverter_settings(net, values, deltas):
    """ID, IQ, D2ANG per inverter, relative to V1 at its own bus before the fault (design model), so the EMT
    inverters deliver the absolute currents `values` and signals `deltas`."""
    import numpy as np
    import network as nw
    _, V = nw.solve(net, values, deltas, None, full=True)
    out = {}
    for name, g in net.ibrs.items():
        i = values.get(name, g.i0)
        v1 = V[g.bus][0]
        rel = np.angle(i) - np.angle(v1)
        d = deltas.get(name, 0.0)
        out[name] = dict(ID=float(abs(i) * np.cos(rel)), IQ=float(-abs(i) * np.sin(rel)), MODE2=2.0 if abs(d) else 0.0,
                         D2MAG=float(abs(d)), D2ANG=float(np.degrees(np.angle(d) - np.angle(v1))) if abs(d) else 0.0)
    return out


def make_spec(name, net, fault=None, values=None, deltas=None, lim=1):
    values, deltas = values or {}, deltas or {}
    # what the PSCAD build can represent; fail loudly instead of dropping it (review finding 8)
    for k, g in net.sgs.items():
        assert abs(complex(g.zs[2]) - complex(g.zs[1])) <= 1e-12 * max(1.0, abs(g.zs[1])), f"{k}: source3 needs z2 = z1"
    for k, g in net.ibrs.items():
        assert abs(g.neg_z) >= 1e5, f"{k}: the PSCAD inverter has no negative-sequence shunt (neg_z must be open)"
    for k, y in net.loads.items():
        assert abs(complex(y[2]) - complex(y[1])) <= 1e-12 * max(1.0, abs(y[1])), f"load at {k}: needs y2 = y1"
    return dict(name=name, lim=lim, relay=list(net.relay), eps=net.eps,
                fault=None if fault is None else [fault[0], float(fault[1]), fault[2], float(fault[3])],
                lines={k: dict(a=l.a, b=l.b, z1=_c(l.z1), z0=_c(l.z0)) for k, l in net.lines.items()},
                sgs={k: dict(bus=g.bus, z1=_c(g.zs[1]), z0=_c(g.zs[0]), e=_c(values.get(k, g.e0))) for k, g in net.sgs.items()},
                ibrs={k: dict(bus=g.bus, zero_z=abs(g.zero_z), i_max=g.i_max or 1.2) for k, g in net.ibrs.items()},
                loads={k: dict(y1=_c(y[1]), y0=abs(y[0])) for k, y in net.loads.items()},
                settings=inverter_settings(net, values, deltas),
                values={k: _c(v) for k, v in values.items()}, deltas={k: _c(v) for k, v in deltas.items()})


def three_bus():
    """zone_model's default three-bus network, with the inverter's zero-sequence path open (as built here)."""
    import zone_model as zm
    import network as nw
    p = zm.ZoneParams()
    return nw.Network(lines={"L1": nw.Line("L", "R", p.z1, p.z0_ratio * p.z1),
                             "L2": nw.Line("R", "S", p.z2, p.z0_ratio * p.z2)},
                      sgs={"G": nw.SG("L", dict(p.zs), p.e0)},
                      ibrs={"I": nw.IBR("R", p.i0, (0.3, 0.3), p.ibr_neg_z, 1e6, inject=True, i_max=1.2)},
                      loads={"R": dict(p.yR), "S": dict(p.yS)}, relay=("L1", "a"), eps=0.08, rF=p.rF)


# ------------------------------------------------------------------ PSCAD side (standard library)
def _rl(b, a_node, b_node, z_pu, x, y, tag, nm=None):
    """Series R then L; nm names them nm + "R" / nm + "L" so a fast run can find and change them."""
    z = z_pu * ZBASE
    mid = f"{a_node}_{tag}"
    kr, kl = (dict(Name=nm + "R"), dict(Name=nm + "L")) if nm else ({}, {})
    b.series("master:resistor", a_node, mid, x, y, R=f"{max(z.real, 1e-6):.6g} [ohm]", **kr)
    b.series("master:inductor", mid, b_node, x + 4, y, L=f"{max(z.imag, 1e-6) / W:.6g} [H]", **kl)


def seg_name(lname, ph):
    return f"S{lname}{ph}"


def check_line_model(spec):
    """The return-conductor line model is exact only for a radial network or a uniform (z0 - z1)/z1."""
    buses = {x for l in spec["lines"].values() for x in (l["a"], l["b"])}
    parent = {b: b for b in buses}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    loops = False
    for l in spec["lines"].values():
        ra, rb = find(l["a"]), find(l["b"])
        if ra == rb:
            loops = True
        parent[ra] = rb
    if loops:
        ratios = [(_z(l["z0"]) - _z(l["z1"])) / _z(l["z1"]) for l in spec["lines"].values()]
        if not all(abs(r - ratios[0]) <= 1e-9 * max(1.0, abs(ratios[0])) for r in ratios):
            raise ValueError("meshed network with unequal (z0 - z1)/z1: the return-conductor line model is not exact")
    return loops


def spec_digest(spec):
    """A fingerprint of everything that determines a run, so stored output is reused only for the same run."""
    import hashlib
    return hashlib.sha256(json.dumps({k: v for k, v in spec.items() if k != "name"}, sort_keys=True).encode()).hexdigest()


def reusable(spec):
    """Existing output may be reused only if it was made from this exact spec (review finding 11)."""
    d = os.path.join(WORK, spec["name"] + ".gf46")
    out, tag = os.path.join(d, spec["name"] + "_01.out"), os.path.join(d, "spec.sha256")
    return os.path.exists(out) and os.path.exists(tag) and open(tag).read().strip() == spec_digest(spec)


def stamp(spec):
    with open(os.path.join(WORK, spec["name"] + ".gf46", "spec.sha256"), "w") as fh:
        fh.write(spec_digest(spec))


def build(pscad, spec, t_fault=0.30, dur=0.10, t_end=0.5, dt_us=10.0):
    from pscad_inverter import INPUTS, OUTPUTS, port_xy, definition_xml, Builder
    name, fault, lim = spec["name"], spec["fault"], spec["lim"]
    for g in spec["ibrs"].values():
        assert g["zero_z"] >= 1e5, "inverter zero-sequence path must be open in the PSCAD build"
    for y in spec["loads"].values():
        assert y["y0"] == 0, "loads must be ungrounded in the PSCAD build"
    check_line_model(spec)
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
    row = [10]

    def next_row(h=4):
        y = row[0]
        row[0] += h
        return y

    earthed = False
    for sname, g in spec["sgs"].items():
        e, bus = _z(g["e"]), g["bus"]
        z1, z0 = _z(g["z1"]) * ZBASE, _z(g["z0"]) * ZBASE
        y0 = next_row(8)
        b.comp("master:source3", 10, y0 + 2, Name=sname, Ctrl="0", View="0", MVA=f"{SBASE} [MVA]", Vm=f"{VLL} [kV]",
               F=f"{F0} [Hz]", Es=f"{VLL * abs(e):.6g} [kV]", F0=f"{F0} [Hz]", Ph=f"{math.degrees(cmath.phase(e)):.6g} [deg]",
               Term="0", Type="2", Imp="1", ZSeq="1", Z1=f"{abs(z1):.6g} [ohm]", Phi1=f"{math.degrees(cmath.phase(z1)):.4f} [deg]",
               Z0=f"{abs(z0):.6g} [ohm]", Phi0=f"{math.degrees(cmath.phase(z0)):.4f} [deg]", Tc="0.01 [s]")
        b.node("G_" + bus, 8, y0 + 2)
        b.node("G_" + bus, 6, y0 + 2)
        for k, ph in enumerate("ABC"):
            b.node(bus + ph, 12, y0 + 2 * k)
        if not earthed:
            yy = next_row(2)
            b.node("G_" + bus, 4, yy)
            b.ground(4, yy)
            earthed = True

    lines = {k: (l["a"], l["b"], _z(l["z1"]), _z(l["z0"])) for k, l in spec["lines"].items()}
    if fault is not None:
        fl, m, scen, rf = fault
        la, lb, z1, z0 = lines.pop(fl)
        lines[fl + "_a"] = (la, "F", m * z1, m * z0)
        lines[fl + "_b"] = ("F", lb, (1 - m) * z1, (1 - m) * z0)
    rl, end = spec["relay"]
    here = spec["lines"][rl]["a"] if end == "a" else spec["lines"][rl]["b"]
    relay_first = (fault[0] + ("_a" if end == "a" else "_b")) if fault is not None and fault[0] == rl else rl
    for lname, (a, bb, lz1, lz0) in lines.items():
        if lname == relay_first and bb == here:
            a, bb = bb, a                                   # build from the relay end
        for k, ph in enumerate("ABC"):
            y = next_row(4)
            start = a + ph
            if lname == relay_first:
                b.comp("master:ammeter", 8, y, Name="IL" + ph)
                b.node(a + ph, 8, y)
                start = "RLY" + ph
                b.node(start, 10, y)
            _rl(b, start, bb + ph, lz1, 14, y, lname, seg_name(lname, ph))
        _rl(b, "G_" + a, "G_" + bb, (lz0 - lz1) / 3.0, 14, next_row(4), lname + "n", seg_name(lname, "n"))

    for bus, y in spec["loads"].items():
        zl = 1.0 / _z(y["y1"])
        assert zl.imag > 0, "capacitive loads not built"
        for ph in "ABC":
            _rl(b, bus + ph, "NLD_" + bus, zl, 34, next_row(4), "ld")
        yy = next_row(4)
        b.series("master:resistor", "NLD_" + bus, "GNL_" + bus, 34, yy, R="1.0e6 [ohm]")
        b.ground(36, yy)

    for ph in "ABC":
        y = next_row(4)
        b.comp("master:voltmetergnd", 4, y, Name="VL" + ph)
        b.node(here + ph, 4, y)
    y = next_row(4)
    b.comp("master:voltmetergnd", 4, y, Name="VLG")
    b.node("G_" + here, 4, y)

    if fault is not None:
        b.comp("master:tbreakn", 70, 10, Name="FLTT", NUMS="2", INIT="1", TO1=f"{t_fault} [s]", TO2=f"{t_fault + dur} [s]")
        b.sig("FLT", 68, 10)
        r = max(rf * ZBASE, 1e-3)
        if scen == "ag":
            y = next_row(4)
            b.comp("master:breaker1", 30, y, NAME="FLT", RON=f"{r:.6g} [ohm]", ROFF="1.0e8 [ohm]", BOpen="2")
            b.node("G_F", 28, y)
            b.node("FA", 32, y)
        else:
            for ph in "BC":
                y = next_row(4)
                b.comp("master:breaker1", 30, y, NAME="FLT", RON=f"{r / 2:.6g} [ohm]", ROFF="1.0e8 [ohm]", BOpen="2")
                b.node("FN", 28, y)
                b.node("F" + ph, 32, y)
            y = next_row(4)
            b.series("master:resistor", "FN", "G_F", 30, y, R="1.0e8 [ohm]")

    cx = 90
    for iname, g in spec["ibrs"].items():
        for ph in "ABC":
            y = next_row(4)
            b.comp("master:voltmetergnd", 46, y, Name=f"V{iname}{ph}")
            b.node(g["bus"] + ph, 46, y)
            b.comp("master:ammeter", 50, y, Name=f"Iinv{iname}{ph}")
            b.node(g["bus"] + ph, 50, y)
            b.comp("master:src_ccin_1", 52, y, Name=f"C{iname}{ph}", Cntrl="1", f="0.0 [Hz]", Vm="1.0 [kA]", Tc="0.0 [s]",
                   Ph="0.0 [deg]")
            b.ground(54, y)
            b.sig(f"IREF{iname}{ph}", 52, y + 2)
        cy = next_row(24) + 10
        c.create_component(defn, cx, cy)
        vals = dict(F0=F0, K2=2.0, IBASE=IBASE_PK, VBASE=VBASE_PK, IMAX=g["i_max"], LIM=float(lim), **spec["settings"][iname])
        for p in INPUTS:
            px, py = port_xy(p)
            gx, gy = cx + px // 18, cy + py // 18
            if p in ("VA", "VB", "VC"):
                b.sig(f"V{iname}{p[1]}", gx, gy)
            else:
                b.comp("master:const", gx - 2, gy, Value=str(vals[p]), Name=f"K{iname}{p}")
        for p in OUTPUTS:
            px, py = port_xy(p)
            gx, gy = cx + px // 18, cy + py // 18
            b.sig(f"IREF{iname}{p[1]}" if p in ("IA", "IB", "IC") else f"{p}_{iname}", gx, gy)

    chans = [("VL" + p, "kV") for p in "ABC"] + [("VLG", "kV")] + [("IL" + p, "kA") for p in "ABC"]
    for iname in spec["ibrs"]:
        chans += [(f"Iinv{iname}{p}", "kA") for p in "ABC"]
    r0 = max(row[0] + 10, 200)
    for k, (nm, u) in enumerate(chans):
        b.channel(nm, 120, r0 + 3 * k, u, -50, 50)
    prj.parameters(time_duration=str(t_end), time_step=str(dt_us), sample_step="50", PlotType="OUT",
                   output_filename=name + ".out")
    prj.save()
    return prj


def update(prj, spec):
    """Change an already built project to another run of the same topology (same fault line and type):
    the faulted line's two segments, the fault resistance, the source EMFs and the inverter settings."""
    c = prj.canvas("Main")
    fault = spec["fault"]
    if fault is not None:
        fl, m, scen, rf = fault
        l = spec["lines"][fl]
        z1, z0 = _z(l["z1"]), _z(l["z0"])
        for part, frac in (("_a", m), ("_b", 1 - m)):
            for ph, z in (("A", z1), ("B", z1), ("C", z1), ("n", (z0 - z1) / 3.0)):
                zz = frac * z * ZBASE
                c.find_first("master:resistor", seg_name(fl + part, ph) + "R").parameters(R=f"{max(zz.real, 1e-6):.6g} [ohm]")
                c.find_first("master:inductor", seg_name(fl + part, ph) + "L").parameters(L=f"{max(zz.imag, 1e-6) / W:.6g} [H]")
        r = max(rf * ZBASE, 1e-3)
        for br in c.find_all("master:breaker1", "FLT"):
            br.parameters(RON=f"{(r if scen == 'ag' else r / 2):.6g} [ohm]")
    for sname, g in spec["sgs"].items():
        e = _z(g["e"])
        c.find_first("master:source3", sname).parameters(Es=f"{VLL * abs(e):.6g} [kV]", Ph=f"{math.degrees(cmath.phase(e)):.6g} [deg]")
    for iname, st in spec["settings"].items():
        for k, v in list(st.items()) + [("LIM", float(spec["lim"])), ("IMAX", spec["ibrs"][iname]["i_max"])]:
            c.find_first("master:const", f"K{iname}{k}").parameters(Value=str(v))


def run_fast(path):
    """Run many specs: one project per topology (fault line, fault type), updated per run. Each run's output
    is copied to WORK/<run name>.gf46/ with the files renamed to the run, as a freshly built run would be."""
    import glob, shutil, time
    import mhi.pscad
    from pscad_inverter import run
    pscad = mhi.pscad.application()
    specs = json.load(open(path))
    projects = {}
    t0 = time.time()
    for k, sp in enumerate(specs):
        if reusable(sp):
            continue
        key = "N" if sp["fault"] is None else f"{sp['fault'][0]}_{sp['fault'][2]}"
        if key not in projects:
            pname = "fastnet_" + key
            projects[key] = (pname, build(pscad, dict(sp, name=pname)))
        pname, prj = projects[key]
        update(prj, sp)
        src = os.path.join(WORK, pname + ".gf46")
        for f in glob.glob(os.path.join(src, pname + "_*.out")):
            os.remove(f)
        dt, errs = run(prj)
        ok = not errs and os.path.exists(os.path.join(src, pname + "_01.out"))
        if ok:
            dst = os.path.join(WORK, sp["name"] + ".gf46")
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            os.makedirs(dst)
            for f in glob.glob(os.path.join(src, pname + "_*.out")) + [os.path.join(src, pname + ".inf")]:
                shutil.copy2(f, os.path.join(dst, os.path.basename(f).replace(pname, sp["name"], 1)))
            stamp(sp)
        print(f"[{k + 1}/{len(specs)}] {sp['name']}: {dt:.1f} s " + ("ok" if ok else "FAILED " + " | ".join(errs[:2])[:200]), flush=True)
    print(f"done in {time.time() - t0:.0f} s", flush=True)


def run_specs(path):
    import mhi.pscad
    from pscad_inverter import run
    pscad = mhi.pscad.application()
    for sp in json.load(open(path)):
        out = os.path.join(WORK, sp["name"] + ".gf46", sp["name"] + "_01.out")
        if reusable(sp):
            continue
        prj = build(pscad, sp)
        dt, errs = run(prj)
        ok = not errs and os.path.exists(out)
        if ok:
            stamp(sp)
        print(f"{sp['name']}: {dt:.1f} s " + ("ok" if ok else "FAILED " + " | ".join(errs[:2])[:200]), flush=True)
        try:
            prj.unload()
        except Exception:
            pass


if __name__ == "__main__":
    if sys.argv[1] == "spec":
        import numpy as np
        net = three_bus()
        d = {"I": 0.2 * np.exp(-0.5j)}
        cases = (("nb_N", None), ("nb_L1ag", ("L1", 0.55, "ag", 0.0)), ("nb_L2ag", ("L2", 0.25, "ag", 0.5)),
                 ("nb_L2ab", ("L2", 0.5, "ab", 0.25)))
        specs = [make_spec(nm, net, flt, {}, d) for nm, flt in cases]
        json.dump(specs, open(sys.argv[2], "w"), indent=1)
        print(len(specs), "specs ->", sys.argv[2])
    elif sys.argv[1] == "fast":
        run_fast(sys.argv[2])
    else:
        run_specs(sys.argv[2])
