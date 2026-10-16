"""Independent checks of src/network.py and of the circuit src/pscad_network.py builds (review/NETWORK_REVIEW.md).

    python review/checks/check_network.py

Each check prints PASS/FAIL with the number that decides it. Nothing here imports the code under review
except to call it; the reference models below are written from first principles.
"""
import os, sys, itertools
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(ROOT, "src", "review"))
import network as nw  # noqa: E402

a = np.exp(2j * np.pi / 3)
T = np.array([[1, 1, 1], [1, a * a, a], [1, a, a * a]])      # [x0, x1, x2] -> [xa, xb, xc]
Ti = np.linalg.inv(T)
RES = []


def report(name, ok, detail):
    RES.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def seq_y(y):
    """network order [v1, v2, v0, i1, i2, i0]"""
    return np.asarray(y)


# --------------------------------------------------------------------------------------------- 1
def check_hand_fault():
    """SG behind zs at L, line to an open bus R: bolted / resistive A-G and B-C faults by the textbook formulas."""
    zs = {1: 0.05 + 0.4j, 2: 0.05 + 0.4j, 0: 0.02 + 0.8j}
    z1, z0, E = 0.02 + 0.2j, 0.06 + 0.6j, 1.02 * np.exp(0.1j)
    net = nw.Network(lines={"L1": nw.Line("L", "R", z1, z0)}, sgs={"G": nw.SG("L", zs, E)},
                     ibrs={"I": nw.IBR("R", 0j)}, relay=("L1", "a"))
    worst = 0.0
    for m, rf in ((0.3, 0.0), (0.7, 0.25)):
        Z = {s: zs[s] + m * (z0 if s == 0 else z1) for s in (1, 2, 0)}
        # A-G: I1 = I2 = I0 = E / (Z1 + Z2 + Z0 + 3 Rf); all of it from L
        If = E / (Z[1] + Z[2] + Z[0] + 3 * rf)
        ref = [E - zs[1] * If, -zs[2] * If, -zs[0] * If, If, If, If]
        got = nw.solve(net, fault=("L1", m, "ag", rf))
        worst = max(worst, np.abs(got - ref).max())
        # phase-phase symmetric about A (i.e. B-C) through Rf between the phases: I1 = -I2 = E / (Z1 + Z2 + Rf)
        I1 = E / (Z[1] + Z[2] + rf)
        ref = [E - zs[1] * I1, zs[2] * I1, 0, I1, -I1, 0]
        got = nw.solve(net, fault=("L1", m, "ab", rf))
        worst = max(worst, np.abs(got - ref).max())
    report("hand-derived radial faults", worst < 1e-5, f"max |network - textbook| = {worst:.2e} pu "
           "(1e-6 pu residual is the 1e6 pu inverter shunts)")


# --------------------------------------------------------------------------------------------- 2
def phase_domain(net, values, deltas, fault, conductor_model, rmin=1e-9):
    """Independent three-phase nodal solve. conductor_model=False: each line a coupled 3x3 impedance
    (Zs = (z0 + 2 z1)/3, Zm = (z0 - z1)/3) to a common ground, i.e. the sequence model's assumption.
    conductor_model=True: what src/pscad_network.py builds: uncoupled z1 per phase plus a return conductor
    (z0 - z1)/3 between per-bus return nodes G_X, SG neutrals and the fault on G_X, the first SG's G node
    earthed, inverters phase-to-earth, loads wye to a floating neutral."""
    buses = list(net.buses)
    lines = dict(net.lines)
    if fault is not None:
        fl, m, scen, rf = fault
        ln = lines.pop(fl)
        buses = buses + ["F"]
        lines["_fa"] = nw.Line(ln.a, "F", m * ln.z1, m * ln.z0)
        lines["_fb"] = nw.Line("F", ln.b, (1 - m) * ln.z1, (1 - m) * ln.z0)
    nodes = [(b, p) for b in buses for p in "abc"]
    if conductor_model:
        nodes += [(b, "G") for b in buses]
    nodes += [("FN", "n")]                               # phase-phase fault star point
    ix = {nd: k for k, nd in enumerate(nodes)}
    n = len(nodes)
    Y = np.zeros((n, n), complex); J = np.zeros(n, complex)
    earth = None                                         # None = the reference (index -1)

    def gnd(bus):
        return ix[(bus, "G")] if conductor_model else None

    def stamp_y(i, j, y):                                # branch admittance between node i and j (None = earth)
        if i is not None: Y[i, i] += y
        if j is not None: Y[j, j] += y
        if i is not None and j is not None: Y[i, j] -= y; Y[j, i] -= y

    def stamp_3(ph_nodes, ref_node, Yabc):               # 3x3 admittance from phases to a reference node
        idx = list(ph_nodes)
        for r in range(3):
            for c in range(3):
                Y[idx[r], idx[c]] += Yabc[r, c]
                if ref_node is not None:
                    Y[idx[r], ref_node] -= Yabc[r, c]; Y[ref_node, idx[c]] -= Yabc[r, c]; Y[ref_node, ref_node] += Yabc[r, c]

    def seq_to_abc(d):                                   # diagonal sequence matrix {1, 2, 0} -> abc
        return T @ np.diag([d[0], d[1], d[2]]) @ Ti

    def P(bus):
        return [ix[(bus, p)] for p in "abc"]

    for ln in lines.values():
        if conductor_model:
            for p in "abc":
                stamp_y(ix[(ln.a, p)], ix[(ln.b, p)], 1 / ln.z1)
            stamp_y(gnd(ln.a), gnd(ln.b), 1 / ((ln.z0 - ln.z1) / 3))
        else:
            Zabc = seq_to_abc({0: ln.z0, 1: ln.z1, 2: ln.z1})
            Yl = np.linalg.inv(Zabc)
            ia, ib = P(ln.a), P(ln.b)
            for r in range(3):
                for c in range(3):
                    Y[ia[r], ia[c]] += Yl[r, c]; Y[ib[r], ib[c]] += Yl[r, c]
                    Y[ia[r], ib[c]] -= Yl[r, c]; Y[ib[r], ia[c]] -= Yl[r, c]
    first = True
    for name, g in net.sgs.items():
        Ys = seq_to_abc({0: 1 / g.zs[0], 1: 1 / g.zs[1], 2: 1 / g.zs[2]})
        e = values.get(name, g.e0)
        Eabc = T @ np.array([0, e, 0])
        nref = gnd(g.bus)
        stamp_3(P(g.bus), nref, Ys)
        Inorton = Ys @ Eabc
        for k, q in enumerate(P(g.bus)):
            J[q] += Inorton[k]
        if nref is not None:
            J[nref] -= Inorton.sum()
            if first:
                Y[nref, nref] += 1e9                     # earthed
                first = False
    for name, g in net.ibrs.items():
        i1, d = values.get(name, g.i0), deltas.get(name, 0.0)
        Iabc = T @ np.array([0, i1, d])
        for k, q in enumerate(P(g.bus)):
            J[q] += Iabc[k]                               # injected from earth into the phase
        ysh = seq_to_abc({0: 1 / g.zero_z, 1: 0.0, 2: 1 / g.neg_z})
        stamp_3(P(g.bus), None, ysh)                      # (1e6 pu: negligible either way)
    for bus, y in net.loads.items():
        assert y[0] == 0 or not conductor_model
        if conductor_model:                               # wye, floating neutral, 1e6 pu to earth
            nn = len(nodes); nodes.append((bus, "N")); ix[(bus, "N")] = nn
            Y = np.pad(Y, ((0, 1), (0, 1))); J = np.pad(J, (0, 1))
            for q in P(bus):
                stamp_y(q, nn, y[1])
            stamp_y(nn, None, 1e-6)
        else:
            stamp_3(P(bus), None, seq_to_abc({0: y[0], 1: y[1], 2: y[2]}))
    if fault is not None:
        rr = max(rf, rmin)
        if scen == "ag":
            stamp_y(ix[("F", "a")], gnd("F"), 1 / rr)
        else:                                             # B-C through Rf: two halves to a star point
            stamp_y(ix[("F", "b")], ix[("FN", "n")], 2 / rr)
            stamp_y(ix[("F", "c")], ix[("FN", "n")], 2 / rr)
            stamp_y(ix[("FN", "n")], gnd("F"), 1e-8)
    Y[ix[("FN", "n")], ix[("FN", "n")]] += 1e-12
    v = np.linalg.solve(Y, J)
    rl, end = net.relay
    ln = net.lines[rl]
    here, there = (ln.a, ln.b) if end == "a" else (ln.b, ln.a)
    seg = ln
    if fault is not None and fault[0] == rl:
        seg = lines["_fa"] if end == "a" else lines["_fb"]
        there = "F"
    vh, vt = v[P(here)], v[P(there)]
    if conductor_model:
        uh = vh - v[gnd(here)]
        i = (vh - vt) / seg.z1
    else:
        uh = vh
        i = np.linalg.inv(seq_to_abc({0: seg.z0, 1: seg.z1, 2: seg.z1})) @ (vh - vt)
    vs, is_ = Ti @ uh, Ti @ i                           # [0, 1, 2]
    return np.array([vs[1], vs[2], vs[0], is_[1], is_[2], is_[0]])


def check_phase_domain(name, net, conductor_model, rng, n=30, tol=1e-6):
    worst = 0.0
    lines = list(net.lines)
    for _ in range(n):
        vals = {k: (1 + 0.1 * rng.normal()) * np.exp(0.2j * rng.normal()) for k in net.sgs}
        vals.update({k: 0.5 * (rng.normal() + 1j * rng.normal()) for k in net.ibrs})
        dl = {k: 0.4 * (rng.normal() + 1j * rng.normal()) for k in net.injectors}
        scen = rng.choice(["N", "ag", "ab"])
        fault = None if scen == "N" else (lines[rng.integers(len(lines))], rng.uniform(0.05, 0.95), scen, rng.uniform(0.0, 1.0))
        ref = phase_domain(net, vals, dl, fault, conductor_model)
        got = nw.solve(net, vals, dl, fault)
        worst = max(worst, np.abs(got - ref).max() / max(1.0, np.abs(ref).max()))
    report(name, worst < tol, f"max |network.solve - phase-domain model| = {worst:.2e} pu over {n} random runs")
    return worst


def three_bus():
    import zone_model as zm
    p = zm.ZoneParams()
    return nw.Network(lines={"L1": nw.Line("L", "R", p.z1, 3 * p.z1), "L2": nw.Line("R", "S", p.z2, 3 * p.z2)},
                      sgs={"G": nw.SG("L", dict(p.zs), p.e0)},
                      ibrs={"I": nw.IBR("R", p.i0, (0.3, 0.3), 1e6, 1e6, inject=True, i_max=1.2)},
                      loads={"R": dict(p.yR), "S": dict(p.yS)}, relay=("L1", "a"))


def radial_mixed():
    """The three-bus network with z0/z1 = 4.5 on L2 (radial, ratios differ)."""
    net = three_bus()
    net.lines["L2"] = nw.Line("R", "S", net.lines["L2"].z1, 4.5 * net.lines["L2"].z1)
    return net


def meshed(z0_ratio_L3):
    """L - R - S with a third line L3 closing the loop L - S; z0/z1 = 3 on L1, L2; z0_ratio_L3 on L3."""
    net = three_bus()
    z3 = 0.03 + 0.35j
    net.lines["L3"] = nw.Line("L", "S", z3, z0_ratio_L3 * z3)
    return net


# --------------------------------------------------------------------------------------------- 3
def check_limit_rows(rng, n=4000):
    """Brute force: sample normal-side and fault-side box coordinates; a pair whose true phase currents
    are all <= i_max must satisfy every row (soundness); rows written for the LP variable w = [u_N, -u_F]."""
    net = three_bus()
    ms = nw.NetModelSet(net, [("L1", 0.55, "ag", 1.0)], mode="outer")
    c, gens = nw.source_set(net, "ibr", "I", "outer")
    k = 2 * len(net.sources)
    c0, c1 = ms.generator_columns("I")
    viol_sound, cut_true, n_ok = 0, 0, 0
    old_sign_viol = 0
    for dv in (0j, 0.6 * np.exp(1.2j), 0.9 * np.exp(1j * np.radians(210))):
        A, b = nw.limit_rows(ms, "I", dv)(k)
        for _ in range(n):
            uN, uF = rng.uniform(-1, 1, k), rng.uniform(-1, 1, k)
            iN = c + gens[0] * uN[c0] + gens[1] * uN[c1]
            iF = c + gens[0] * uF[c0] + gens[1] * uF[c1]
            fitsN = max(abs(iN + a ** j * dv) for j in range(3)) <= 1.2
            fitsF = max(abs(iF + a ** j * dv) for j in range(3)) <= 1.2
            w = np.concatenate([uN, -uF])                 # the LP's variable (ModelSet.pair)
            rows_ok = np.all(A @ w <= b + 1e-12)
            if fitsN and fitsF:
                n_ok += 1
                viol_sound += not rows_ok
                w_old = np.concatenate([uN, uF])          # the pre-#37 reading
                old_sign_viol += not np.all(A @ w_old <= b + 1e-12)
            # a far violation must be cut (polygon of 24 sides: tolerance 1.2 / cos(pi/24) = 1.2103)
            farN = max(abs(iN + a ** j * dv) for j in range(3)) > 1.2104
            if farN and rows_ok:
                cut_true += 1
    report("limit_rows sound on both blocks", viol_sound == 0,
           f"{viol_sound} of {n_ok} admissible (u_N, u_F) pairs cut; reading block 1 as +u_F would cut {old_sign_viol}")
    report("limit_rows tight to the 24-gon", cut_true == 0, f"{cut_true} pairs with a phase current > 1.2103 pu kept")


def check_closest_realisation(rng):
    """The fault realisation closest() returns must itself respect the limit (tests/test_network.py checks
    only that its distance is consistent, which holds whatever the fault-block sign)."""
    net = three_bus()
    ms = nw.NetModelSet(net, [("L1", 0.55, "ag", 1.0), ("L2", 0.25, "ag", 1.0), ("L1", 0.35, "ab", 0.0)], mode="outer")
    c, gens = nw.source_set(net, "ibr", "I", "outer")
    c0, c1 = ms.generator_columns("I")
    worst = 0.0
    for dv in (0.62 * np.exp(1j * np.radians(230)), 0.9 * np.exp(1j * np.radians(210))):
        lim = nw.limit_rows(ms, "I", dv)
        for f in ms.faults:
            uN, uF, t = nw.closest(ms, f, dv, lim)
            for u in (uN, uF):
                i1 = c + gens[0] * u[c0] + gens[1] * u[c1]
                worst = max(worst, max(abs(i1 + a ** j * dv) for j in range(3)))
    report("closest(): both realisations within the limit", worst <= 1.2 / np.cos(np.pi / 24) + 1e-9,
           f"largest phase current of a returned realisation {worst:.4f} pu (24-gon bound 1.2103)")


# --------------------------------------------------------------------------------------------- 4
def fortran_limiter(i1, d, imax, lim):
    """Literal transcription of the LIM block of src/pscad_inverter.py FORTRAN (real arithmetic)."""
    I1R, I1I, I2R, I2I = i1.real, i1.imag, d.real, d.imag
    if lim > 0.5:
        LL, S1 = imax ** 2, 1.0
        for K in range(3):
            if K == 0:
                QR, QI, RR, RI = I1R, I1I, I2R, I2I
            elif K == 1:
                QR, QI = -0.5 * I1R + 0.8660254 * I1I, -0.8660254 * I1R - 0.5 * I1I
                RR, RI = -0.5 * I2R - 0.8660254 * I2I, 0.8660254 * I2R - 0.5 * I2I
            else:
                QR, QI = -0.5 * I1R - 0.8660254 * I1I, 0.8660254 * I1R - 0.5 * I1I
                RR, RI = -0.5 * I2R + 0.8660254 * I2I, -0.8660254 * I2R - 0.5 * I2I
            QA, QB, QC = QR ** 2 + QI ** 2, QR * RR + QI * RI, RR ** 2 + RI ** 2 - LL
            if QC < 0 and QA > 1e-12:
                S1 = min(S1, (-QB + np.sqrt(QB ** 2 - QA * QC)) / QA)
        S1 = max(S1, 0.0)
        I1R, I1I = S1 * I1R, S1 * I1I
    PA = complex(I1R + I2R, I1I + I2I)
    PB = complex(-0.5 * I1R + 0.8660254 * I1I - 0.5 * I2R - 0.8660254 * I2I,
                 -0.8660254 * I1R - 0.5 * I1I + 0.8660254 * I2R - 0.5 * I2I)
    PC = complex(-0.5 * I1R - 0.8660254 * I1I - 0.5 * I2R + 0.8660254 * I2I,
                 0.8660254 * I1R - 0.5 * I1I - 0.8660254 * I2R - 0.5 * I2I)
    PK = max(abs(PA), abs(PB), abs(PC))
    SC = imax / PK if PK > imax else 1.0
    return SC * complex(I1R, I1I), SC * complex(I2R, I2I), SC * np.array([PA, PB, PC])


def check_limiter(rng, n=20000):
    worst, worst_ph, over = 0.0, 0.0, 0.0
    for _ in range(n):
        i1 = rng.uniform(0, 2) * np.exp(1j * rng.uniform(-np.pi, np.pi))
        d = rng.uniform(0, 1.5) * np.exp(1j * rng.uniform(-np.pi, np.pi))
        for lim in (0, 1):
            a1, b1 = nw.limiter(i1, d, 1.2, lim)
            a2, b2, ph = fortran_limiter(i1, d, 1.2, lim)
            worst = max(worst, abs(a1 - a2), abs(b1 - b2))
            # the Fortran phase currents are the sequence currents' phases (abc order)
            worst_ph = max(worst_ph, np.abs(ph - T @ np.array([0, a2, b2])).max())
            over = max(over, np.abs(ph).max() - 1.2)
    report("limiter == Fortran LIM 0 / LIM 1", worst < 1e-6,
           f"max |python - fortran| {worst:.1e} pu over {2 * n} draws; Fortran phases = T [0, I1, I2] to {worst_ph:.1e}; "
           f"largest phase after limiting exceeds 1.2 by {over:.1e}")


# --------------------------------------------------------------------------------------------- 5
def check_affine_linear(rng):
    """affine_case's generators are exact (solve is affine in every source): random box points re-solved."""
    net = meshed(3.0)
    net.ibrs["I2"] = nw.IBR("S", 0.3 * np.exp(-0.2j), (0.2, 0.2))
    worst = 0.0
    for fault in (None, ("L3", 0.4, "ag", 0.3), ("L2", 0.7, "ab", 0.0)):
        c, H, G = nw.affine_case(net, fault, "outer")
        for _ in range(10):
            u = rng.uniform(-1, 1, G.shape[1])
            d = rng.normal(size=H.shape[1])
            vals = nw.realisation(net, u)
            y = nw.solve(net, vals, {"I": complex(d[0], d[1])}, fault)
            worst = max(worst, np.abs(nw._realify(y) - (c + H @ d + G @ u)).max())
    report("affine_case exact on a meshed 2-inverter network", worst < 1e-9, f"max residual {worst:.1e}")


def check_relay_end_b(rng):
    """Relay at end b sees minus the end-a current when the fault is elsewhere; and the faulted-line
    segment is chosen correctly when the fault is on the relay line."""
    net = meshed(3.0)
    worst = 0.0
    for fault in (None, ("L2", 0.3, "ag", 0.2), ("L1", 0.3, "ag", 0.2), ("L1", 0.8, "ab", 0.1)):
        na = nw.Network(net.lines, net.sgs, net.ibrs, net.loads, ("L1", "a"))
        nb = nw.Network(net.lines, net.sgs, net.ibrs, net.loads, ("L1", "b"))
        ya, yb = nw.solve(na, fault=fault), nw.solve(nb, fault=fault)
        ref_b = phase_domain(nb, {}, {}, fault, False)
        worst = max(worst, np.abs(yb - ref_b).max())
        if fault is None or fault[0] != "L1":
            worst = max(worst, np.abs(ya[3:] + yb[3:]).max())
    report("relay at end b", worst < 1e-6, f"max error {worst:.1e}")


def main():
    rng = np.random.default_rng(20261016)
    check_hand_fault()
    check_phase_domain("phase domain, coupled lines, radial three-bus", three_bus(), False, rng)
    check_phase_domain("phase domain, coupled lines, meshed (L3 z0/z1 = 4)", meshed(4.0), False, rng)
    check_phase_domain("PSCAD conductor model, radial three-bus", three_bus(), True, rng)
    check_phase_domain("PSCAD conductor model, radial, z0/z1 = 3 and 4.5", radial_mixed(), True, rng)
    check_phase_domain("PSCAD conductor model, meshed, uniform z0/z1 = 3", meshed(3.0), True, rng)
    check_phase_domain("PSCAD conductor model, meshed, L3 z0/z1 = 4 (expected to fail)", meshed(4.0), True, rng)
    check_relay_end_b(rng)
    check_affine_linear(rng)
    check_limit_rows(rng)
    check_closest_realisation(rng)
    check_limiter(rng)
    print(f"\n{sum(ok for _, ok in RES)} / {len(RES)} checks passed")


if __name__ == "__main__":
    main()
