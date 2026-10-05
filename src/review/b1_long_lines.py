"""B1 on longer lines: does an injected delta help the zone-1 reach decision more when the protected line is long?

Why: on the CIGRE MV feeder delta barely helps reach (b1_delta_screen.py; results/CIGREMV.md §3) because an in-zone
fault at 85 % and a fault at the remote bus are only 0.3-0.6 ohm of line apart, so delta moves both measurements
almost equally (Taylor's Theorem 1 in the TAC 2025 paper predicts the same). The hypothesis left for the method
(docs/notes/SORULAR_CEVAPLAR.md Q34) is that it needs longer lines: with more line between the two faults their
responses to delta should differ more. This tests that in the same study model, changing one thing.

WHAT CHANGES  For each relay, the positive- and zero-sequence impedances of the protected line and of the lines
beyond its remote bus (real_zone.CONFIGS 'beyond', where the out-of-zone faults are placed) are multiplied by
SCALE. Everything else is B1 as run: network, inverters and their y2, operating points, groundings, fault
types, R_f grids, eps, the |delta| x angle grid, and the EMT weights per (type, R_f band) cell.

LIMIT  A 20 kV feeder cannot carry the inverters' 12 MW over much longer lines: at SCALE 10 the pre-fault load
flow (ibr_study.prefault, which does not report it) fails to converge at every relay and its voltages are
meaningless (0.48-1.56 pu). Hence SCALE 2 and 3 only, and every pre-fault state is checked first: a relay and
scale whose load flow does not converge is not screened, and the pre-fault voltage range is recorded (R3 at
SCALE 3 reaches about 1.14 pu at its inverter bus).

READ  The EMT-weighted share of in-zone scenarios that separate from every out-of-zone confuser at eps = 0.01:
without delta, with |delta| <= 0.4 pu (what fits the inverter at a design angle) and <= 1.2 pu (its whole
current). SCALE = 1 is b1_delta_screen.json itself (the wrapper is then the identity). The hypothesis is supported
if the gain from delta (the 0.4 and 1.2 shares minus the share without delta) grows with SCALE.

    python src/review/b1_long_lines.py [2 3] [cigre_R1 ...]   -> results/cigremv/b1_long_lines.json
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import setting_study as ss
from review import ibr_study as ib
from review import b1_delta_screen as b1
import real_zone

OUT = os.path.join(cm.ROOT, "results", "cigremv", "b1_long_lines.json")
SCALES = (2.0, 3.0)
RELAY_ORDER = ("cigre_R3", "cigre_R1", "cigre_R4", "cigre_R2")   # the two relays where B1 found least first
# The headline needs |delta| <= 1.2 pu only; 2 and 3 pu (B1's top of grid) add a third of the run time at SCALE 3.
b1.MAGS = (0.2, 0.4, 0.7, 1.2)

# ------------------------------------------------------------------ longer lines, in the network the screen builds
_SCALE = dict(k=1.0, lines=())
_build = ss.build


def _build_scaled(graph, *a, **kw):
    main, lines, grids, loads = _build(graph, *a, **kw)
    lines = {key: (u, v, z1 * _SCALE["k"], z0 * _SCALE["k"]) if key in _SCALE["lines"] else (u, v, z1, z0)
             for key, (u, v, z1, z0) in lines.items()}
    return main, lines, grids, loads


ss.build = _build_scaled


def prefault_states(L, G, cfg):
    """The pre-fault load flow of every network the screen builds (grounding x operating point), with the same
    iteration as ibr_study.prefault: converged or not, and |V1| in pu (all main buses, relay bus, remote bus)."""
    ibrs = ib.inverters_from_graph(G, b1.UB, ib.load_characterisation())
    vb, out = b1.UB / np.sqrt(3), []
    for g, r in b1.groundings(L):
        base = ss.build(G, ub=b1.UB, grounding=(g, r), open_ends=cfg.get("open_line_ends"))
        for lab, loads, usetp, _ in b1.operating_points(L, G):
            main, lines, grids, lds = ib.with_operating_point(base, b1.UB, loads, usetp)
            nodes, ix, Y, I = ss.ybus(main, lines, grids, lds, 1)
            Zb, bi = np.linalg.inv(Y), [ix[q["bus"]] for q in ibrs]
            J1, ok = np.zeros(len(ibrs), complex), False
            for it in range(ib.MAX_IT):
                inj = I.copy(); inj[bi] += J1
                V = Zb @ inj
                new, _ = ib._ibr_currents(ibrs, V[bi], np.zeros(len(ibrs)), J1)
                if np.max(np.abs(new - J1), initial=0) < ib.TOL * 1e3:
                    J1, ok = new, True
                    break
                J1 = ib.DAMP * new + (1 - ib.DAMP) * J1
            inj = I.copy(); inj[bi] += J1
            vm = np.abs(Zb @ inj) / vb
            on_main = [ix[q] for q in main if q in ix]
            out.append(dict(grounding=g, op=lab, converged=ok, iterations=it + 1, v_min_pu=float(vm[on_main].min()),
                            v_max_pu=float(vm[on_main].max()), v_relay_pu=float(vm[ix[cfg["relay_bus"]]]),
                            v_remote_pu=float(vm[ix[cfg["remote_bus"]]])))
    return out


def headline(r):
    """EMT-weighted shares (%) over every cell the model populates: separable without delta, with |delta| <= 0.4
    and <= 1.2 pu at eps = 0.01. Reproduces the B1 table in results/CIGREMV.md from b1_delta_screen.json."""
    cs = [c for c in r["cells"].values() if c["n_model"]]
    w = sum(c["emt_in_zone"] for c in cs)
    f = lambda g: 100.0 * sum(c["emt_in_zone"] * g(c) for c in cs) / w
    return dict(without_delta=f(lambda c: 1 - c["ambiguous_at_delta0"]["eps=0.01"]),
                delta_le_0p4=f(lambda c: c["share_le_0p4"]), delta_le_1p2=f(lambda c: c["share_le_1p2"]))


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    scales = [float(a) for a in sys.argv[1:] if a.replace(".", "", 1).isdigit()] or list(SCALES)
    names = [a for a in sys.argv[1:] if a in b1.RELAYS] or list(RELAY_ORDER)
    L, G = b1.grid_data()
    base = json.load(open(b1.OUT, encoding="utf-8"))["relays"]
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    out.update(script="b1_long_lines.py", commit=cm.git_commit(), eps_headline=b1.EPS_HEAD,
               delta_magnitudes_pu=list(b1.MAGS),
               note="scale multiplies Z1 and Z0 of the protected line and the lines beyond its remote bus; scale 1 is "
                    "b1_delta_screen.json. The |delta| grid stops at 1.2 pu, so a need above it reads as none")
    res = out.setdefault("relays", {})
    for n in names:
        cfg = real_zone.CONFIGS[n]
        _SCALE["lines"] = (cfg["line"],) + tuple(cfg["beyond"])
        z1 = abs(_build(G, ub=b1.UB, grounding=b1.groundings(L)[0], open_ends=cfg.get("open_line_ends"))[1][cfg["line"]][2])
        res.setdefault(n, {})["1"] = dict(z1_line_ohm=z1, gap_85_to_remote_ohm=0.15 * z1, **headline(base[n]))
        for k in scales:
            t0 = time.time()
            _SCALE["k"] = k
            pre = prefault_states(L, G, cfg)
            if not all(q["converged"] for q in pre):
                _SCALE["k"] = 1.0
                res[n][f"{k:g}"] = dict(z1_line_ohm=k * z1, skipped="pre-fault load flow does not converge", prefault=pre)
                print(f"[{n}] scale {k:g}: SKIPPED, the pre-fault load flow does not converge", flush=True)
                json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
                continue
            r = b1.screen(n, L, G)
            _SCALE["k"] = 1.0
            res[n][f"{k:g}"] = dict(z1_line_ohm=k * z1, gap_85_to_remote_ohm=0.15 * k * z1, **headline(r), prefault=pre,
                                    verdict_eps_0p01=r["verdict_eps_0p01"], unconverged_in=r["unconverged_in"],
                                    unconverged_out=r["unconverged_out"], n_in=r["n_in"], n_out=r["n_out"], cells=r["cells"],
                                    runtime_s=time.time() - t0)
            h = res[n][f"{k:g}"]
            print(f"[{n}] scale {k:g}: |Z1L| {k * z1:.1f} ohm, pre-fault |V| {min(q['v_min_pu'] for q in pre):.3f}-"
                  f"{max(q['v_max_pu'] for q in pre):.3f} pu; separable {h['without_delta']:.1f} % without delta, "
                  f"{h['delta_le_0p4']:.1f} % with <= 0.4 pu, {h['delta_le_1p2']:.1f} % with <= 1.2 pu "
                  f"(scale 1: {res[n]['1']['without_delta']:.1f} / {res[n]['1']['delta_le_0p4']:.1f} / {res[n]['1']['delta_le_1p2']:.1f}); "
                  f"unconverged {r['unconverged_in']}/{r['n_in']} in, {r['unconverged_out']}/{r['n_out']} out", flush=True)
            json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    print("saved", OUT)
