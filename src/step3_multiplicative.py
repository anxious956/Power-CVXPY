"""
Each detector against its own worst MULTIPLICATIVE systematic instrument error (review/STEP3_WORSTCASE_REVIEW.md,
regime-dependent after review/STEP3_CLASS_REVIEW.md). Per-phase VT ratio, VT phase, CT ratio and CT phase errors,
constant over a run, multiply the phase phasors. A CT's and a VT's error depends on the current or voltage it sees,
so there are two independent parameter sets:

  normal regime  (the relay's memory, and every window of a normal run): CT 1 % / 1 deg, VT 3 % / 2 deg
  fault regime   (the decision windows of a fault run): CT 10 % / 1 deg, VT 6 % / 4 deg

On top, the design tier's white noise (front-end tier "white", added to the samples before the mimic filter), drawn
with N_SEEDS seeds; the adversary picks the worst over its parameter sets and the seeds. The search covers zero
error plus N_SETS random corners of the 24-parameter box (12 for a normal run) and N_RANDOM interior points: a
lower bound on the worst case. Thresholds: the largest score under the same adversary over the 150 dense normal
runs (forced trigger) and the pre-fault windows of the fault runs. D1 keeps the design's threshold (distance > eps).

--stress: the earlier stress case, the fault-condition limits applied to every window and the memory (CT 10 %,
VT 6 % / 4 deg, no CT phase error) and no white noise.

    python src/step3_multiplicative.py [fault_specs.json] [--stress]   -> results/step3/multiplicative_<name>[_stress].json
"""
import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames as fr
import step3_detectors as det
from step3_frontend import Relay, CYCLE, phase_phasors
from step3_adversary import d2_joint, train_d3, EPS
from waveforms import _B

OUT = os.path.join(HERE, "..", "results", "step3")
deg = np.pi / 180
REGIME = dict(N=(0.03, 2 * deg, 0.01, 1 * deg), F=(0.06, 4 * deg, 0.10, 1 * deg))      # (vt, vt_ph, ct, ct_ph)
STRESS = dict(N=(0.06, 4 * deg, 0.10, 0.0), F=(0.06, 4 * deg, 0.10, 0.0))
N_SETS, N_RANDOM, N_SEEDS = 256, 32, 3


def param_sets(n_par, seed=0):
    rng = np.random.default_rng(seed)
    corners = rng.choice([-1.0, 1.0], (N_SETS, n_par))
    return np.vstack([np.zeros((1, n_par)), corners, rng.uniform(-1, 1, (N_RANDOM, n_par))])


def gains(P12, b):
    vt, vt_ph, ct, ct_ph = b
    gv = (1 + P12[:, 0:3] * vt) * np.exp(1j * P12[:, 3:6] * vt_ph)
    gi = (1 + P12[:, 6:9] * ct) * np.exp(1j * P12[:, 9:12] * ct_ph)
    return gv, gi


class Phasors:
    """The phase phasors of one run (one noise draw) around one trigger: memory windows, D1 / D2 windows, D3 frames."""

    def __init__(self, rel, inc):
        self.mem_ends = list(inc - CYCLE // 2 - np.arange(0, 2 * CYCLE + 1, CYCLE // 4))
        self.ends = dict(d1=[inc + int(round(c * CYCLE)) for c in np.arange(2.0, 3.0001, 0.25)],
                         d2=[inc + int(round(c * CYCLE)) for c in det.D2_UPDATES],
                         d3=[inc + int(round(c * CYCLE)) for c in det.D3_FRAMES])
        post = sorted({e for v in self.ends.values() for e in v})
        self.mem_pv = np.array([phase_phasors(rel.v, e) for e in self.mem_ends])
        self.mem_pi = np.array([phase_phasors(rel.i, e) / rel.H for e in self.mem_ends])
        self.post_idx = {e: k for k, e in enumerate(post)}
        self.pv = np.array([phase_phasors(rel.v, e) for e in post])
        self.pi = np.array([phase_phasors(rel.i, e) / rel.H for e in post])

    @staticmethod
    def _seq(gv, gi, pv, pi):
        sv = np.einsum("ij,pwj->pwi", _B, gv[:, None, :] * pv[None])
        si = np.einsum("ij,pwj->pwi", _B, gi[:, None, :] * pi[None])
        return np.concatenate([sv[..., [1, 2, 0]], si[..., [1, 2, 0]]], axis=-1)

    def views(self, P, bounds, normal_run):
        """Relay-frame windows per detector and the memory, for each parameter row. P: (n_p, 24) = [N params, F params]
        (a normal run uses the N params for every window)."""
        gvN, giN = gains(P[:, :12], bounds["N"])
        gvF, giF = (gvN, giN) if normal_run else gains(P[:, 12:24], bounds["F"])
        mem = self._seq(gvN, giN, self.mem_pv, self.mem_pi).mean(1)
        Y = self._seq(gvF, giF, self.pv, self.pi)
        uL = np.conj(mem[:, 0] / np.abs(mem[:, 0]))
        out = {k: Y[:, [self.post_idx[e] for e in v]] * uL[:, None, None] for k, v in self.ends.items()}
        out["abs_d1"] = Y[:, [self.post_idx[e] for e in self.ends["d1"]]]
        out["mem"] = mem * uL[:, None]
        out["mem_abs"] = mem
        return out


def realv(z):
    return np.concatenate([z.real, z.imag], axis=-1)


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


def detector_scores(V, joint, pack):
    m, A = V["mem_abs"], V["abs_d1"]
    d0 = np.max(np.maximum(3 * np.abs(A[..., 5] - m[:, None, 5]), np.abs(A[..., 4] - m[:, None, 4])), axis=1)
    d2 = np.array([_llr(y, joint) for y in realv(V["d2"]).reshape(len(m), -1)])
    feats = np.concatenate([V["d3"], V["d3"] - V["mem"][:, None, :]], axis=-1)
    F = np.transpose(realv(feats), (0, 2, 1))
    d3 = _cnn(pack, F) if pack is not None else None
    return d0, d2, F, d3


def d1_min(V, pieces):
    best = np.inf
    for p in range(len(V["d1"])):
        worst_w = 0.0
        for y in V["d1"][p]:
            worst_w = max(worst_w, fr.distance_to_set(pieces, y) / EPS)
            if worst_w >= best:
                break
        best = min(best, worst_w)
    return best


def d1_max(V, pieces, stride=1):
    return max(fr.distance_to_set(pieces, y) / EPS for p in range(0, len(V["d1"]), stride) for y in V["d1"][p])


def main(fault_path, stress=False):
    specs = json.load(open(fault_path))
    normals = json.load(open(os.path.join(OUT, "normals_specs.json")))
    tag = os.path.splitext(os.path.basename(fault_path))[0].replace("_specs", "") + ("_stress" if stress else "")
    bounds = STRESS if stress else REGIME
    tier, seeds = ("clean", [0]) if stress else ("white", list(range(N_SEEDS)))
    P = param_sets(24)
    t0 = time.time()
    scen = sorted({sp["scenario"] for sp in specs})
    folds = [scen[k::5] for k in range(5)]
    d3_models = {tuple(f): train_d3(specs, [s for s in scen if s not in f]) for f in folds}
    print(f"D3 folds trained  [{time.time() - t0:.0f} s]", flush=True)
    rows, nrows = [], []
    for lv in sorted({sp["level"] for sp in specs}):
        group = [sp for sp in specs if sp["level"] == lv]
        d = complex(*group[0]["d_cmd"])
        pieces, joint = det.normal_set(d), d2_joint(d)
        thr = dict(d0=-np.inf, d2=-np.inf, d3=-np.inf)
        norm_views = []
        for sp in [n for n in normals if n["level"] == lv]:
            for sd in seeds:
                rel = Relay(sp["name"], tier=tier, seed=7000 + sd)
                norm_views.append((sp["name"], Phasors(rel, rel.idx(sp["t_fault"])).views(P, bounds, True)))
        pre_views = []
        for sp in group:
            for sd in seeds:
                rel = Relay(sp["name"], tier=tier, seed=8000 + 100 * sp["scenario"] + sd)
                true = rel.idx(sp["t_fault"])
                for i in np.linspace(rel.idx(0.18), true - 3 * CYCLE - 1, 2).astype(int):
                    pre_views.append(Phasors(rel, int(i)).views(P, bounds, True))
        for V in [v for _, v in norm_views] + pre_views:
            d0, d2, F, _ = detector_scores(V, joint, None)
            thr["d0"] = max(thr["d0"], float(d0.max()))
            thr["d2"] = max(thr["d2"], float(d2.max()))
            thr["d3"] = max(thr["d3"], max(float(np.max(_cnn(pk, F))) for pk in d3_models.values()))
        # D1's false alarms on the normal runs (its threshold is fixed by the design)
        for nm in sorted({n for n, _ in norm_views}):
            worst = max(d1_max(V, pieces, stride=9) for n, V in norm_views if n == nm)
            nrows.append(dict(name=nm, level=lv, d1_worst_eps=float(worst), d1_false_alarm=bool(worst > 1.0)))
        n_fa = sum(r["d1_false_alarm"] for r in nrows if r["level"] == lv)
        print(f"level {lv}: thresholds D0 {thr['d0']:.3f}, D2 {thr['d2']:.2f}, D3 {thr['d3']:.2f}; D1 false alarms on "
              f"{n_fa} of {len({n for n, _ in norm_views})} normal runs  [{time.time() - t0:.0f} s]", flush=True)
        for sp in group:
            if sp["kind"] != "fault":
                continue
            fold = [f for f in folds if sp["scenario"] in f][0]
            r = dict(name=sp["name"], scenario=sp["scenario"], stratum=sp["stratum"], level=lv, in_range=sp["in_range"],
                     d1_min_eps=np.inf, d0_min=np.inf, d2_min=np.inf, d3_min=np.inf)
            for sd in seeds:
                rel = Relay(sp["name"], tier=tier, seed=9000 + 100 * sp["scenario"] + sd)
                V = Phasors(rel, rel.idx(sp["t_fault"])).views(P, bounds, False)
                d0, d2, F, d3 = detector_scores(V, joint, d3_models[tuple(fold)])
                r["d1_min_eps"] = min(r["d1_min_eps"], float(d1_min(V, pieces)))
                r["d0_min"], r["d2_min"], r["d3_min"] = (min(r["d0_min"], float(d0.min())), min(r["d2_min"], float(d2.min())),
                                                         min(r["d3_min"], float(d3.min())))
            r.update(d1_miss=bool(r["d1_min_eps"] <= 1.0), d0_miss=bool(r["d0_min"] <= thr["d0"]),
                     d2_miss=bool(r["d2_min"] <= thr["d2"]), d3_miss=bool(r["d3_min"] <= thr["d3"]), thresholds=thr)
            rows.append(r)
        print(f"level {lv} done  [{time.time() - t0:.0f} s]", flush=True)
    summ = {}
    print(f"\nworst-case MISS rate, multiplicative adversary ({'stress' if stress else 'regime-dependent + white noise'}), "
          f"D1 D0 D2 D3, by stratum and delta level:")
    for st in ("hard", "hard_bc", "uniform", "outside"):
        cells = []
        for lv in sorted({r["level"] for r in rows}):
            q = [r for r in rows if r["stratum"] == st and r["level"] == lv]
            if q:
                v = [float(np.mean([r[f"{dn}_miss"] for r in q])) for dn in ("d1", "d0", "d2", "d3")]
                summ[f"{st}|{lv}"] = v
                cells.append(" ".join(f"{x:.2f}" for x in v))
        print(f"    {st:8s} " + "  |  ".join(cells))
    print("    D1 false alarms on the normal runs, by level: " +
          "  ".join(f"{sum(r['d1_false_alarm'] for r in nrows if r['level'] == lv)}/{sum(1 for r in nrows if r['level'] == lv)}"
                    for lv in sorted({r['level'] for r in nrows})))
    json.dump(dict(bounds={k: [float(x) for x in v] for k, v in bounds.items()}, tier=tier, seeds=seeds, n_params=len(P),
                   summary=summ, rows=rows, normal_rows=nrows),
              open(os.path.join(OUT, f"multiplicative_{tag}.json"), "w"), indent=1, default=float)
    print(f"-> results/step3/multiplicative_{tag}.json  [{time.time() - t0:.0f} s]")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else os.path.join(OUT, "pilot_specs.json"), stress="--stress" in sys.argv)
