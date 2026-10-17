"""
Is a PSCAD network built by src/pscad_network.py the circuit the design tool solves? The relay's sequence
phasors from EMT against network.solve at the same operating point (the inverters' measured injections, the
source EMF measured before the fault). One rotation maps PSCAD's time frame onto the design frame: the
relay-bus source EMF E1 = V1 + zs1 I1 is put at the angle the spec asks for. That needs the relay line to be
the only branch at the source's bus (asserted). The comparison re-solves with the MEASURED |E1| and the
MEASURED injections, so it checks the network, not whether the source and inverters were set as asked; that
is checked separately (pre-fault |E1| / |E| and the injections against the spec).

    python src/pscad_network_check.py <specs.json> [t_pre t_meas]
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pscad_io import read_case
from pscad_check import to_128_per_cycle
from waveforms import sequence_phasors, CYCLE
from pscad_network import WORK, VBASE_PK, IBASE_PK, three_bus
import network as nw


def seq(run, names, t_end, base, sub=None, mimic_tau=None):
    """One-cycle sequence phasors ending at t_end. mimic_tau (cycles): a causal DC-removal (mimic) filter first,
    y[k] = x[k] - e^{-Ts/tau} x[k-1], its fundamental gain divided out (as src/review/common.py's mimic)."""
    x = np.array([run["ch"][n] - (run["ch"][sub] if sub else 0.0) for n in names])
    x, fs = to_128_per_cycle(x, run["fs"], 60.0)
    H = 1.0
    if mimic_tau:
        dd = np.exp(-1.0 / (mimic_tau * CYCLE))
        x = np.concatenate([x[:, :1], x[:, 1:] - dd * x[:, :-1]], axis=1)
        H = 1 - dd * np.exp(-2j * np.pi / CYCLE)
    return np.array(sequence_phasors(x, int(round(t_end * fs)) - CYCLE)) / base / H


def relay_y(run, t, mimic_tau=None):
    """The relay's six sequence phasors at t. mimic_tau: a mimic filter on the currents (tau in cycles; the
    protected line's X/R / 2 pi removes its DC offset)."""
    v = seq(run, ["VLA", "VLB", "VLC"], t, VBASE_PK, sub="VLG")
    i = seq(run, ["ILA", "ILB", "ILC"], t, IBASE_PK, mimic_tau=mimic_tau)
    return np.array([v[1], v[2], v[0], i[1], i[2], i[0]])


def injections(run, spec, t):
    out = {}
    for name in spec["ibrs"]:
        j = -seq(run, [f"Iinv{name}{p}" for p in "ABC"], t, IBASE_PK)
        out[name] = (j[1], j[2])
    return out


def assert_single_branch(net):
    """E1 = V1 + zs1 I_relay holds only if the relay bus carries exactly one synchronous source and nothing but
    the relay line besides (review findings 10 and round 2). Returns that source's name."""
    rl, end = net.relay
    here = net.lines[rl].a if end == "a" else net.lines[rl].b
    others = [k for k, l in net.lines.items() if k != rl and here in (l.a, l.b)]
    assert not others and here not in net.loads and not any(g.bus == here for g in net.ibrs.values()), \
        f"relay bus {here} has other branches {others}: the frame cannot be fixed from E1 = V1 + zs1 I_relay"
    sgs = [k for k, g in net.sgs.items() if g.bus == here]
    assert len(sgs) == 1, f"relay bus {here} must carry exactly one synchronous source, has {sgs}"
    return sgs[0]


def compare(spec, net, t_pre=0.25, t_meas=0.38):
    run = read_case(os.path.join(WORK, spec["name"] + ".gf46"), spec["name"])
    here_sg = [assert_single_branch(net)]
    g = net.sgs[here_sg[0]]
    y_pre = relay_y(run, t_pre)
    e1 = y_pre[0] + g.zs[1] * y_pre[3]
    e_spec = complex(*spec["sgs"][here_sg[0]]["e"])
    rot = np.exp(1j * (np.angle(e_spec) - np.angle(e1)))
    res = {}
    for stage, t in (("pre", t_pre), ("fault", t_meas)):
        if stage == "fault" and spec["fault"] is None:
            continue
        y = relay_y(run, t) * rot
        inj = {k: (a * rot, d * rot) for k, (a, d) in injections(run, spec, t).items()}
        vals = {here_sg[0]: abs(e1) * np.exp(1j * np.angle(e_spec)), **{k: a for k, (a, _) in inj.items()}}
        f = None if stage == "pre" else tuple(spec["fault"])
        ys = nw.solve(net, vals, {k: d for k, (_, d) in inj.items()}, f)
        res[stage] = dict(y=y, ys=ys, err=float(np.abs(y - ys).max()), inj=inj)
    return res


if __name__ == "__main__":
    specs = json.load(open(sys.argv[1]))
    net = three_bus()
    for sp in specs:
        r = compare(sp, net)
        line = f"{sp['name']:<10} fault {sp['fault']}: "
        for st, q in r.items():
            i1, i2 = list(q["inj"].values())[0]
            line += f"{st} max|EMT-design| {q['err']:.4f} pu (largest {np.abs(q['ys']).max():.3f}; inverter I1 {abs(i1):.3f} I2 {abs(i2):.3f})   "
        print(line)
