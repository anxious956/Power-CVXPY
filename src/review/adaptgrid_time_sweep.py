"""Decision-time sweep of the adapt_grid sequence-trajectory CNN: what does waiting buy?

The CNN decides at 20 ms (one cycle) everywhere else. Hasan et al. (2026) decide at 2-2.5 cycles, and a
zone-1 element is judged by how fast it is. This runs the CNN at decision times of 10, 15, 20, 30 and 40 ms
with everything else unchanged: the input is ten sequence-phasor frames evenly spaced from t/10 to t
(q3_inputs.seq_traj; at 20 ms these are exactly its 2, 4, ..., 20 ms frames), the canonical phase rotation
is chosen by the causal phase selector at the decision time t (q3_inputs uses 20 ms), and training,
calibration and scoring are adaptgrid_seeds.run_seed (deterministic torch, cnn_foldmean). At 20 ms the run
therefore reproduces the deterministic seed study exactly, which is the built-in check.

    python src/review/adaptgrid_time_sweep.py [--relays adapt_A adapt_B] [--times 10 15 20 30 40]
                                              [--seeds 0 100 200] [--splits grouped loqo]
    -> results/adaptgrid/time_sweep_relayfe_cnn.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from review import common as cm
from review import frontend
from review import q3_inputs as q3
from review.zone_cv import zone_task
from review.adaptgrid_run import bundle, supervision
from review.adaptgrid_seeds import run_seed

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")


def rotation_index_at(R, sel, t_ms):
    """q3_inputs.rotation_index with the phase selector read at the decision time instead of 20 ms."""
    vpre, vpost, ipre, ipost = cm.phasors_at(R, sel, t_ms, "full", True)
    mask = cm.phase_selection(ipre, ipost)
    r = np.zeros(len(sel), int)
    g = mask[:, :3].any(1)
    r[g] = mask[g, :3].argmax(1)
    p = ~g & mask[:, 3:].any(1)
    r[p] = (mask[p, 3:].argmax(1) - 1) % 3
    return r


def frames_for(t_ms):
    return np.linspace(t_ms / 10.0, t_ms, 10)


def seq_features_at(R, t_ms):
    """(n, 24, 10) CNN input for every record, decision at t_ms."""
    sel = np.arange(len(R["et"]))
    Rc, cidx = q3.rotated(R, sel, rotation_index_at(R, sel, t_ms))
    Rc["ev"] = R["ev"]
    old = q3.FRAMES_MS
    q3.FRAMES_MS = frames_for(t_ms)
    try:
        return q3.seq_traj(Rc, cidx)
    finally:
        q3.FRAMES_MS = old


def main(relays=("adapt_A", "adapt_B"), times=(10, 15, 20, 30, 40), seeds=(0, 100, 200),
         kinds=("grouped", "loqo")):
    t0 = time.time()
    frontend.enable()
    res = dict(script="adaptgrid_time_sweep", commit=cm.git_commit(), frontend="relayfe", model="CNN seq-traj",
               times_ms=list(times), seeds=list(seeds), frames="10 frames evenly spaced from t/10 to t", relays={})
    for relay in relays:
        R = bundle(relay, None)
        idx, y, groups = zone_task(R)
        fwd = supervision(R, np.arange(len(R["et"])))
        rr = {}
        for t in times:
            F = {"seq": seq_features_at(R, t)}
            for kind in kinds:
                for s in seeds:
                    r = run_seed(R, idx, y, groups, F, fwd, kind, s)
                    rr[f"{t}|{kind}|{s}"] = r
                    c, r1 = r["cal0"], r["roc1"]
                    print(f"  [{relay} {t:2d} ms {kind:7s} seed+{s}] cal0 dep {100*c['dependability']:5.1f} "
                          f"off-line {c['offline']['k']}/{c['offline']['n']} switching {c['switching']['k']} | "
                          f"roc1 dep {100*r1['dependability']:5.1f} [{time.time()-t0:.0f}s]", flush=True)
        res["relays"][relay] = rr
        del R
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "time_sweep_relayfe_cnn.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, f"[{res['runtime_s']:.0f}s]", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--relays", nargs="+", default=["adapt_A", "adapt_B"])
    ap.add_argument("--times", type=int, nargs="+", default=[10, 15, 20, 30, 40])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 100, 200])
    ap.add_argument("--splits", nargs="+", default=["grouped", "loqo"])
    a = ap.parse_args()
    main(tuple(a.relays), tuple(a.times), tuple(a.seeds), tuple(a.splits))
