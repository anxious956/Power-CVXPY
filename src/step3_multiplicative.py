"""
Each detector against its own worst MULTIPLICATIVE systematic instrument error inside the class bounds
(review/STEP3_WORSTCASE_REVIEW.md): per-phase CT ratio errors |r_I| <= 10 %, VT ratio errors |r_V| <= 6 % and VT phase
errors |theta| <= 4 deg, constant over the run. They act on the clean phase phasors of every window, the relay's
memory included, so they scale the increments and turn the memory frame (a VT phase error moves the reference
too). There is no additive noise on top.

The worst case is searched over the 2^9 = 512 corners of the parameter box plus 64 random interior points (the
detectors' scores are close to linear in the parameters, so the corners carry the extremes; the search is a lower
bound on the true worst case). Thresholds are worst-case too: the largest score the same adversary produces on the
normal runs (results/step3/normals_specs.json: 16 box corners + 14 random points per delta level, forced trigger)
and on the pre-fault windows of the fault runs. D1 keeps the design's threshold (distance > eps).

    python src/step3_multiplicative.py [fault_specs.json]     -> results/step3/multiplicative_<name>.json
"""
import os, sys, json, time, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
import step3_detectors as det
from step3_frontend import Relay, CYCLE, phase_phasors, to_seq
from step3_adversary import d2_joint, train_d3, EPS
from waveforms import _B

OUT = os.path.join(HERE, "..", "results", "step3")
BOUNDS = dict(r_I=0.10, r_V=0.06, theta=np.radians(4.0))
N_RANDOM = 64


def param_sets(seed=0):
    lo_hi = [BOUNDS["r_V"]] * 3 + [BOUNDS["theta"]] * 3 + [BOUNDS["r_I"]] * 3
    corners = np.array(list(itertools.product((-1.0, 1.0), repeat=9))) * np.array(lo_hi)
    rand = np.random.default_rng(seed).uniform(-1, 1, (N_RANDOM, 9)) * np.array(lo_hi)
    return np.vstack([np.zeros((1, 9)), corners, rand])        # row 0: no error


class Phasors:
    """The clean phase phasors of one run around one trigger: memory windows, D1 windows, D2 windows, D3 frames."""

    def __init__(self, rel, inc):
        self.mem_ends = inc - CYCLE // 2 - np.arange(0, 2 * CYCLE + 1, CYCLE // 4)
        self.ends = dict(d1=[inc + int(round(c * CYCLE)) for c in np.arange(2.0, 3.0001, 0.25)],
                         d2=[inc + int(round(c * CYCLE)) for c in det.D2_UPDATES],
                         d3=[inc + int(round(c * CYCLE)) for c in det.D3_FRAMES])
        allends = sorted(set(self.mem_ends) | {e for v in self.ends.values() for e in v})
        self.idx = {e: k for k, e in enumerate(allends)}
        self.pv = np.array([phase_phasors(rel.v, e) for e in allends])             # (n_w, 3)
        self.pi = np.array([phase_phasors(rel.i, e) / rel.H for e in allends])

    def seq(self, P):
        """Sequence measurements [V1 V2 V0 I1 I2 I0] for every window under each parameter row: (n_p, n_w, 6)."""
        gv = (1 + P[:, :3]) * np.exp(1j * P[:, 3:6])                               # (n_p, 3)
        gi = 1 + P[:, 6:9]
        pv = gv[:, None, :] * self.pv[None]
        pi = gi[:, None, :] * self.pi[None]
        sv = np.einsum("ij,pwj->pwi", _B, pv)                                       # [s0, s+, s-]
        si = np.einsum("ij,pwj->pwi", _B, pi)
        return np.concatenate([sv[..., [1, 2, 0]], si[..., [1, 2, 0]]], axis=-1)

    def views(self, P):
        """Relay-frame windows per detector, and the memory, for each parameter row."""
        Y = self.seq(P)
        mem = Y[:, [self.idx[e] for e in self.mem_ends]].mean(1)                   # (n_p, 6)
        uL = np.conj(mem[:, 0] / np.abs(mem[:, 0]))
        rel = Y * uL[:, None, None]
        out = {k: rel[:, [self.idx[e] for e in v]] for k, v in self.ends.items()}
        out["mem"] = mem * uL[:, None]
        out["mem_abs"] = mem
        out["abs"] = {k: Y[:, [self.idx[e] for e in v]] for k, v in self.ends.items()}
        return out


def realv(z):
    return np.concatenate([z.real, z.imag], axis=-1)


def scores(ph, P, pieces, joint, d3pack):
    """Per parameter row: D1 max distance (eps), D0, D2 LLR, D3 logit."""
    V = ph.views(P)
    d1 = np.array([max(fr.distance_to_set(pieces, y) for y in V["d1"][p]) / EPS for p in range(len(P))])
    m = V["mem_abs"]
    A = V["abs"]["d1"]
    d0 = np.max(np.maximum(3 * np.abs(A[..., 5] - m[:, None, 5]), np.abs(A[..., 4] - m[:, None, 4])), axis=1)
    Y2 = realv(V["d2"]).reshape(len(P), -1)
    d2 = np.array([_llr(y, joint) for y in Y2])
    feats = np.concatenate([V["d3"], V["d3"] - V["mem"][:, None, :]], axis=-1)       # (n_p, T, 12) complex
    F = np.transpose(realv(feats), (0, 2, 1))                                        # (n_p, 24, T)
    d3 = _cnn(d3pack, F)
    return d1, d0, d2, d3


def _llr(Y, joint):
    from scipy.special import logsumexp
    n_f = sum(1 for m in joint if m[0] is not None)
    n_n = len(joint) - n_f
    lp, isf = [], []
    for k, mu, Pm, ld in joint:
        r = Y - mu
        lp.append(-0.5 * (r @ Pm @ r + ld) + np.log(0.5 / (n_n if k is None else n_f)))
        isf.append(k is not None)
    lp, isf = np.array(lp), np.array(isf)
    return logsumexp(lp[isf]) - logsumexp(lp[~isf])


def _cnn(pack, F):
    import torch
    model, mu, sd, dev = pack
    with torch.no_grad():
        return model(torch.tensor((F - mu) / sd, dtype=torch.float32, device=dev)).squeeze(1).cpu().numpy()


def d1_scores_fast(ph, P, pieces):
    """D1 for the fault side: the smallest over parameter rows of the max-over-windows distance, with early exits."""
    V = ph.views(P)
    best = np.inf
    for p in range(len(P)):
        worst_w = 0.0
        for y in V["d1"][p]:
            dd = fr.distance_to_set(pieces, y) / EPS
            worst_w = max(worst_w, dd)
            if worst_w >= best:
                break
        best = min(best, worst_w)
    return best


def main(fault_path):
    specs = json.load(open(fault_path))
    normals = json.load(open(os.path.join(OUT, "normals_specs.json")))
    tag = os.path.splitext(os.path.basename(fault_path))[0].replace("_specs", "")
    P = param_sets()
    t0 = time.time()
    scen = sorted({sp["scenario"] for sp in specs})
    folds = [scen[k::5] for k in range(5)]
    d3_models = {tuple(f): train_d3(specs, [s for s in scen if s not in f]) for f in folds}
    print(f"D3 folds trained  [{time.time() - t0:.0f} s]", flush=True)
    rows = []
    for lv in sorted({sp["level"] for sp in specs}):
        group = [sp for sp in specs if sp["level"] == lv]
        d = complex(*group[0]["d_cmd"])
        pieces, joint = det.normal_set(d), d2_joint(d)
        # thresholds: max over the adversary on normal runs (forced trigger) and pre-fault windows; D3 with every fold
        cal = []
        for sp in [n for n in normals if n["level"] == lv]:
            rel = Relay(sp["name"], tier="clean", seed=0)
            cal.append(Phasors(rel, rel.idx(sp["t_fault"])))
        for sp in group:
            rel = Relay(sp["name"], tier="clean", seed=0)
            true = rel.idx(sp["t_fault"])
            cal += [Phasors(rel, int(i)) for i in np.linspace(rel.idx(0.18), true - 3 * CYCLE - 1, 2)]
        thr = dict(d0=-np.inf, d2=-np.inf, d3=-np.inf)
        d1_normal_worst = 0.0
        for ph in cal:
            V = ph.views(P)
            m, A = V["mem_abs"], V["abs"]["d1"]
            thr["d0"] = max(thr["d0"], float(np.max(np.maximum(3 * np.abs(A[..., 5] - m[:, None, 5]), np.abs(A[..., 4] - m[:, None, 4])))))
            thr["d2"] = max(thr["d2"], max(_llr(y, joint) for y in realv(V["d2"]).reshape(len(P), -1)))
            feats = np.concatenate([V["d3"], V["d3"] - V["mem"][:, None, :]], axis=-1)
            F = np.transpose(realv(feats), (0, 2, 1))
            thr["d3"] = max(thr["d3"], max(float(np.max(_cnn(pk, F))) for pk in d3_models.values()))
        n_norm_alarm = {dn: 0 for dn in ("d1", "d0", "d2", "d3")}
        for sp in [n for n in normals if n["level"] == lv]:
            rel = Relay(sp["name"], tier="clean", seed=0)
            V = Phasors(rel, rel.idx(sp["t_fault"])).views(P)
            if max(fr.distance_to_set(pieces, y) / EPS for p in range(0, len(P), 37) for y in V["d1"][p]) > 1.0:
                n_norm_alarm["d1"] += 1
        print(f"level {lv}: thresholds D0 {thr['d0']:.3f}, D2 {thr['d2']:.2f}, D3 {thr['d3']:.2f}; normal runs D1 can alarm on "
              f"(sampled): {n_norm_alarm['d1']}  [{time.time() - t0:.0f} s]", flush=True)
        for sp in group:
            if sp["kind"] != "fault":
                continue
            rel = Relay(sp["name"], tier="clean", seed=0)
            ph = Phasors(rel, rel.idx(sp["t_fault"]))
            V = ph.views(P)
            m, A = V["mem_abs"], V["abs"]["d1"]
            d0 = np.max(np.maximum(3 * np.abs(A[..., 5] - m[:, None, 5]), np.abs(A[..., 4] - m[:, None, 4])), axis=1)
            d2 = np.array([_llr(y, joint) for y in realv(V["d2"]).reshape(len(P), -1)])
            feats = np.concatenate([V["d3"], V["d3"] - V["mem"][:, None, :]], axis=-1)
            F = np.transpose(realv(feats), (0, 2, 1))
            fold = [f for f in folds if sp["scenario"] in f][0]
            d3 = _cnn(d3_models[tuple(fold)], F)
            d1min = d1_scores_fast(ph, P, pieces)
            rows.append(dict(name=sp["name"], scenario=sp["scenario"], stratum=sp["stratum"], level=lv, in_range=sp["in_range"],
                             d1_min_eps=float(d1min), d1_clean_eps=float(max(fr.distance_to_set(pieces, y) / EPS for y in V["d1"][0])),
                             d1_miss=bool(d1min <= 1.0), d0_miss=bool(d0.min() <= thr["d0"]), d2_miss=bool(d2.min() <= thr["d2"]),
                             d3_miss=bool(d3.min() <= thr["d3"]), d0_min=float(d0.min()), d2_min=float(d2.min()), d3_min=float(d3.min()),
                             thresholds=thr))
        print(f"level {lv} done  [{time.time() - t0:.0f} s]", flush=True)
    summ = {}
    print("\nworst-case MISS rate, multiplicative class-bound adversary (D1 D0 D2 D3), by stratum and delta level:")
    for st in ("hard", "hard_bc", "uniform", "outside"):
        cells = []
        for lv in sorted({r["level"] for r in rows}):
            q = [r for r in rows if r["stratum"] == st and r["level"] == lv]
            if q:
                v = [float(np.mean([r[f"{dn}_miss"] for r in q])) for dn in ("d1", "d0", "d2", "d3")]
                summ[f"{st}|{lv}"] = v
                cells.append(" ".join(f"{x:.2f}" for x in v))
        print(f"    {st:8s} " + "  |  ".join(cells))
    json.dump(dict(bounds={k: float(v) for k, v in BOUNDS.items()}, n_params=len(P), summary=summ, rows=rows),
              open(os.path.join(OUT, f"multiplicative_{tag}.json"), "w"), indent=1, default=float)
    print(f"-> results/step3/multiplicative_{tag}.json  [{time.time() - t0:.0f} s]")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "pilot_specs.json"))
