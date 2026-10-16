"""
Faulted-phase selectors compared on labelled faults: EvEMTBench own-line faults at six relays (fault type
and phases are in the labels) and the PSCAD fault-point sweep.

    magnitude  the rule used before 16 Oct 2026: zone_model.released_loops(selector="magnitude")
    angle      the sequence-angle rule adopted then:  released_loops(selector="angle")
    angle+V    angle for ground faults, undervoltage for the phase pair. Tried and rejected: its pair
               rule drops phase-phase faults at 10-40 ohm (83 % -> 33 % over six relays)

    python src/review/selector_compare.py      -> results/review/selector_compare.json

Decision at 30 ms (the cycle ending 30 ms after inception), pre-fault cycle ending 20 ms before it.
"""
import os, sys, glob, json
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
from evemt import load_cache
from waveforms import sequence_phasors, CYCLE
from zone_model import released_loops

A = np.exp(2j * np.pi / 3)
RELAYS = (("data/benchmark-DoubleLine (1)_cache.npz", "Cub_2\\pex_MainBus1_MainLn1-2A", "MainLn1-2A"),
          ("data/benchmark-DoubleLine (1)_cache.npz", "Cub_8\\pex_MainBus2_MainLn1-2A", "MainLn1-2A"),
          ("data/benchmark-TestGrid110kV_cache.meta.npz", "Cub_HV_A_A-B-1\\pex_MainBus1_MainLn1-2A", "MainLn1-2A"),
          ("data/benchmark-TestGrid110kV_cache.meta.npz", "Cub_HV_B_A-B-1\\pex_MainBus2_MainLn1-2A", "MainLn1-2A"),
          ("data/benchmark-TestGrid110kV_cache.meta.npz", "Cub_HV_B_B-C\\pex_MainBus2_MainLn2-3", "MainLn2-3"),
          ("data/benchmark-TestGrid110kV_cache.meta.npz", "Cub_HV_C_B-C\\pex_MainBus3_MainLn2-3", "MainLn2-3"))


def _phases(s):
    s0, s1, s2 = s
    return np.array([s0 + s1 + s2, s0 + A**2 * s1 + A * s2, s0 + A * s1 + A**2 * s2])


def angle_plus_voltage(vpre, vpost, ipre, ipost, ground_ratio=0.2, depth=0.8):
    di0, di1, di2 = ipost - ipre
    if abs(di0) > ground_ratio * max(abs(di1), abs(di2), 1e-12):
        return released_loops(ipre, ipost, selector="angle")
    va, vb, vc = _phases(vpre)
    wa, wb, wc = _phases(vpost)
    r = {"ab": abs(wa - wb) / abs(va - vb), "bc": abs(wb - wc) / abs(vb - vc), "ca": abs(wc - wa) / abs(vc - va)}
    low = min(r.values())
    return [k for k, q in r.items() if q <= low / depth] if low < 0.97 else ["ab", "bc", "ca"]


SELECTORS = (("magnitude", lambda vp, vq, ip, iq: released_loops(ip, iq, selector="magnitude")),
             ("angle", lambda vp, vq, ip, iq: released_loops(ip, iq, selector="angle")),
             ("angle+V", angle_plus_voltage))


def expected(etype, p1, p2):
    if etype.startswith("flt_1phg"):
        return {p1 + "g"}
    if etype.startswith("flt_2ph"):            # 2ph and 2phg: the phase-phase loop
        return {p2}
    if etype.startswith("flt_3ph"):
        return {"ab", "bc", "ca"}
    return None


def ok(rel, exp):
    if exp == {"ab", "bc", "ca"}:
        return len(rel) > 0 and set(rel) <= exp
    return set(rel) == exp


def main():
    report, tot = dict(relays={}, total={}, pscad={}), {}
    for cache, cub, line in RELAYS:
        C = load_cache(cache)
        L, ev, k = C["labels"], C["event_index"], C["cubicles"].index(cub)
        et = L["events/event_type"].astype(str).to_numpy()
        tg = L["events/event_target"].astype(str).to_numpy()
        rf = L["events/event_flt_shc_resistance"].to_numpy()
        p1 = L["events/event_phase_select_1ph"].astype(str).to_numpy()
        p2 = L["events/event_phase_select_2ph"].astype(str).to_numpy()
        x = np.asarray(C["x"][:, k], dtype=np.float64)
        tab = {}
        for i in range(len(et)):
            e = expected(et[i], p1[i], p2[i])
            if e is None or "incipient" in et[i] or tg[i] != line:
                continue
            pre, post = ev - 2 * CYCLE, ev + int(round(0.030 * C["fs"])) - CYCLE
            args = (sequence_phasors(x[i, :3], pre), sequence_phasors(x[i, :3], post),
                    sequence_phasors(x[i, 3:], pre), sequence_phasors(x[i, 3:], post))
            kind = et[i].replace("_w_arc", "").replace("_shc", "").replace("flt_", "")
            for n, f in SELECTORS:
                g = ok(f(*args), e)
                for key, d in (((kind, float(rf[i]), n), tab), ((kind, n), tot)):
                    c = d.setdefault(key, [0, 0])
                    c[0] += int(g)
                    c[1] += 1
        report["relays"][cub] = {f"{kd}|R={r:g}|{n}": v for (kd, r, n), v in tab.items()}
        print(f"\n{cub.split(chr(92))[0]} ({os.path.basename(cache)[:22]}), own line {line}: magnitude | angle | angle+V")
        for kind in ("1phg", "2ph", "2phg", "3ph"):
            cells = [f"R={r:g}: " + " | ".join(f"{tab[(kind, r, n)][0]:>2}" for n, _ in SELECTORS) + f" /{tab[(kind, r, 'angle')][1]}"
                     for r in sorted({q[1] for q in tab if q[0] == kind})]
            print(f"  {kind:<5} " + "    ".join(cells))
    print("\nAll six relays, own-line faults:")
    for kind in ("1phg", "2ph", "2phg", "3ph"):
        print(f"  {kind:<5} " + "   ".join(f"{n} {tot[(kind, n)][0]}/{tot[(kind, n)][1]}" for n, _ in SELECTORS))
    report["total"] = {f"{kd}|{n}": v for (kd, n), v in tot.items()}

    from pscad_check import read_case, to_128_per_cycle, inception_index
    for pat in ("case2_sweep_Fault_Type=1_time_step=5_m=*", "case2_sweep_Fault_Type=1_Rf=10_time_step=5_m=*"):
        good, cnt = {n: 0 for n, _ in SELECTORS}, 0
        for d in glob.glob(os.path.join("data", "pscad_work", "Relay_Cases", "runs", pat)):
            run = read_case(d, "case2")
            v = to_128_per_cycle(np.array([run["ch"][f"V1{p}"] for p in "abc"]), run["fs"], 60)[0]
            i = to_128_per_cycle(np.array([run["ch"][f"I1{p}"] for p in "abc"]), run["fs"], 60)[0]
            e = inception_index(i, CYCLE)
            args = (sequence_phasors(v, e - 2 * CYCLE), sequence_phasors(v, e + CYCLE // 2),
                    sequence_phasors(i, e - 2 * CYCLE), sequence_phasors(i, e + CYCLE // 2))
            for n, f in SELECTORS:
                good[n] += int(f(*args) == ["ag"])
            cnt += 1
        report["pscad"][pat] = dict(good, n=cnt)
        print(f"PSCAD {pat.split('_time')[0]}: " + "  ".join(f"{n} {good[n]}/{cnt}" for n, _ in SELECTORS))
    json.dump(report, open(os.path.join("results", "review", "selector_compare.json"), "w"), indent=1)
    print("wrote results/review/selector_compare.json")


if __name__ == "__main__":
    main()
