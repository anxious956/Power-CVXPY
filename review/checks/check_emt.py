"""What the stored three-bus EMT runs actually delivered, against what each spec asked for
(review/NETWORK_REVIEW.md, section 4). Reads D:\\JOSHUA_TAYLOR_data\\data\\pscad_work\\network\\; no PSCAD needed.

    python review/checks/check_emt.py

network_delta_test.analyse and pscad_network_check.compare re-solve the design model with the MEASURED source
EMF magnitude and the MEASURED inverter injections, so |EMT - design| cannot see a source or inverter that was
set wrong (by build(), by update() in the fast mode, or by a units convention). This script compares the
measured quantities with the spec instead, and measures how far delta turned during the fault.
"""
import os, sys, json
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from pscad_network_check import relay_y, injections, read_case  # noqa: E402
from pscad_network import WORK, three_bus  # noqa: E402
import network as nw  # noqa: E402

T_PRE, T_MEAS = 0.25, 0.38


def box_coords(i, _net=three_bus()):
    """Coordinates of an inverter current in the design's outer box (|u| <= 1 inside)."""
    c, g = nw.source_set(_net, "ibr", "I", "outer")
    M = np.array([[g[0].real, g[1].real], [g[0].imag, g[1].imag]])
    return np.linalg.solve(M, [(i - c).real, (i - c).imag])


def main():
    net = three_bus()
    zs1 = net.sgs["G"].zs[1]
    specs = json.load(open(os.path.join(ROOT, "results", "network", "three_bus_design.json")))
    rows = []
    for sp in specs:
        d = os.path.join(WORK, sp["name"] + ".gf46")
        if not os.path.exists(os.path.join(d, sp["name"] + "_01.out")):
            continue
        run = read_case(d, sp["name"])
        y = relay_y(run, T_PRE)
        e1 = y[0] + zs1 * y[3]
        e_spec = complex(*sp["sgs"]["G"]["e"])
        rot = np.exp(1j * (np.angle(e_spec) - np.angle(e1)))
        (i1p, i2p), = injections(run, sp, T_PRE).values()
        i1p, i2p = i1p * rot, i2p * rot
        i1_spec = complex(*sp["values"]["I"]) if "I" in sp["values"] else net.ibrs["I"].i0
        d_spec = complex(*sp["deltas"]["I"]) if "I" in sp["deltas"] else 0j
        r = dict(name=sp["name"], kind=sp["kind"], tag=sp["tag"], e_ratio=abs(e1) / abs(e_spec),
                 i1_err=abs(i1p - i1_spec), d_err=abs(i2p - d_spec), rot_deg=float(np.degrees(np.angle(rot))))
        if sp["kind"] == "fault" and abs(d_spec) > 0:
            (i1f, i2f), = injections(run, sp, T_MEAS).values()
            i1f, i2f = i1f * rot, i2f * rot
            r["d_turn_deg"] = float(np.degrees(np.angle(i2f / d_spec)))
            r["d_mag_ratio"] = float(abs(i2f) / abs(d_spec))
            r["i1_turn_deg"] = float(np.degrees(np.angle(i1f / i1_spec)))
        if sp["kind"] == "fault":
            (i1f, _), = injections(run, sp, T_MEAS).values()
            r["u_fault"] = float(np.abs(box_coords(i1f * rot)).max())     # > 1: outside the design's inverter set
            r["u_spec"] = float(np.abs(box_coords(i1_spec)).max())
        rows.append(r)
    print(f"{len(rows)} runs read")
    er = np.array([q["e_ratio"] for q in rows])
    print(f"|E1 measured| / |E spec|: {er.min():.5f} .. {er.max():.5f}")
    for kind, tag in (("fault", "d0"), ("fault", "dm"), ("normal", "lim1"), ("normal", "lim0")):
        q = [x for x in rows if x["kind"] == kind and x["tag"] == tag]
        if not q:
            continue
        print(f"{kind:6s} {tag}: pre-fault |I1 - spec| max {max(x['i1_err'] for x in q):.4f} pu, "
              f"|delta - spec| max {max(x['d_err'] for x in q):.4f} pu")
    q = [x for x in rows if "d_turn_deg" in x]
    if q:
        t = np.array([x["d_turn_deg"] for x in q]); m = np.array([x["d_mag_ratio"] for x in q])
        t1 = np.array([x["i1_turn_deg"] for x in q])
        print(f"fault runs with the design delta ({len(q)}): delta during the fault turned {t.min():+.1f} .. {t.max():+.1f} deg "
              f"(median |.| {np.median(np.abs(t)):.1f}), |delta| ratio {m.min():.3f} .. {m.max():.3f}; "
              f"I1 turned {t1.min():+.1f} .. {t1.max():+.1f} deg")
        worst = sorted(q, key=lambda x: -abs(x["d_turn_deg"]))[:5]
        print("  largest turns:", [(x["name"], round(x["d_turn_deg"], 1)) for x in worst])
    for tag in ("d0", "dm"):
        q = [x for x in rows if x["kind"] == "fault" and x["tag"] == tag]
        out = [x for x in q if x["u_fault"] > 1 + 1e-6]
        print(f"fault {tag}: inverter I1 during the fault outside the design's set in {len(out)} of {len(q)} runs "
              f"(largest box coordinate {max(x['u_fault'] for x in q):.2f}; at the spec'd realisation {max(x['u_spec'] for x in q):.2f})")


if __name__ == "__main__":
    main()
