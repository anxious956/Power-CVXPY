"""
"Shrinking delta until each detector fails", in Taylor's sense: every detector against ITS OWN worst-case noise inside
the design's eps box (review/STEP3_PILOT_REVIEW.md, option B corrected). Clean front-end measurements (relay frame,
mimic chain) of the pilot runs, plus an adversary:

  per-window  each one-cycle measurement gets its own perturbation e_w, |e_w| <= eps per real component, and so does
              the relay's pre-fault memory (an average of measurements, so also within eps)
  constant    one perturbation e for the whole run, the same on the memory and on every window (a systematic error)

Thresholds are worst-case too: a detector's threshold is the largest score its own adversary can produce on the
calibration normals (pre-fault pseudo-triggers of every run at that delta level), except D1, whose threshold is the
design's (distance > eps). A fault is a worst-case miss if the adversary can keep its score at or below the threshold.

  D1  per-window: a miss iff every window is within 2 eps of N (exact). Constant: an LP over e and every window's
      zonotope coefficients (every combination of N's two pieces over the windows)
  D0  incremental 50N / 50Q: per-window exact (the adversary moves each increment by up to 2 eps per component);
      constant: the perturbation cancels in an increment, so the clean score
  D2  the Gaussian multiple-model test, joint over its two update windows (exact Gaussian per mode, the Kalman updates
      in closed form), noise variance of the stress tier; projected sign-gradient ascent / descent on its log
      posterior odds
  D3  the CNN of step3_detectors, trained as in the pilot (grouped folds, design tier); projected sign-gradient on its
      logit through the feature construction

    python src/step3_adversary.py [specs.json]      -> results/step3/adversary_<name>.json
"""
import os, sys, json, time, itertools
import numpy as np
from scipy.optimize import linprog
from scipy.special import logsumexp
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import step3_detectors as det
from step3_frontend import Relay, CYCLE
from network_delta_test import CASES

OUT = os.path.join(HERE, "..", "results", "step3")
EPS = det.EPS
WIN = np.arange(2.0, 3.0001, 0.25)
PGD_STEPS, PGD_FRAC = 60, 0.08


def realv(z):
    return np.concatenate([z.real, z.imag])


def clean_measurements(rel, inc):
    """Relay-frame measurements (real 12-vectors) of the D1 windows, the memory, the D2 windows, the D3 frames."""
    uL = np.conj(rel.frame(inc))
    mem = det._memory(rel, inc) * uL
    at = lambda c: rel.y(inc + int(round(c * CYCLE))) * uL
    return dict(d1=[realv(at(c)) for c in WIN], mem=realv(mem), d2=[realv(at(c)) for c in det.D2_UPDATES],
                d3=[realv(at(c)) for c in det.D3_FRAMES])


# ----------------------------------------------------------------------------- D1
def d1_worst(M, pieces, mode):
    """True if the adversary makes D1 miss (every window within eps of N after the perturbation)."""
    if mode == "per-window":
        return all(_dist(pieces, y) <= 2 * EPS + 1e-12 for y in M["d1"])
    ys = M["d1"]
    n = ys[0].size
    for combo in itertools.product(range(len(pieces)), repeat=len(ys)):
        # variables: e (n) | for each window: a_w (k_w), nn_w (n)
        blocks, cols = [], n
        for p in combo:
            c, G = pieces[p]
            blocks.append((c, G, cols))
            cols += G.shape[1] + n
        A = np.zeros((n * len(ys), cols))
        b = np.zeros(n * len(ys))
        bounds = [(-EPS, EPS)] * n
        for w, (y, (c, G, off)) in enumerate(zip(ys, blocks)):
            r = slice(w * n, (w + 1) * n)
            A[r, :n] = np.eye(n)                          # y + e + nn = c + G a  ->  e + nn - G a = c - y
            A[r, off:off + G.shape[1]] = -G
            A[r, off + G.shape[1]:off + G.shape[1] + n] = np.eye(n)
            b[r] = c - y
            bounds += [(-1, 1)] * G.shape[1] + [(-EPS, EPS)] * n
        res = linprog(np.zeros(cols), A_eq=A, b_eq=b, bounds=bounds, method="highs")
        if res.status == 0:
            return True
    return False


def _dist(pieces, y):
    import frames as fr
    yc = y[:6] + 1j * y[6:]
    return fr.distance_to_set(pieces, yc)


# ----------------------------------------------------------------------------- D0
def _box_min_abs(z, r):
    return np.hypot(max(abs(z.real) - r, 0.0), max(abs(z.imag) - r, 0.0))


def _box_max_abs(z, r):
    return np.hypot(abs(z.real) + r, abs(z.imag) + r)


def d0_score_adv(M, mode, sense):
    """Worst-case D0 score: sense 'min' (hide a fault) or 'max' (alarm on a normal)."""
    mem = M["mem"][:6] + 1j * M["mem"][6:]
    f = _box_min_abs if sense == "min" else _box_max_abs
    r = 0.0 if mode == "constant" else 2 * EPS
    out = []
    for y in M["d1"]:
        yc = y[:6] + 1j * y[6:]
        out.append(max(f(3 * (yc[5] - mem[5]), 3 * r), f(yc[4] - mem[4], r)))
    return max(out)


# ----------------------------------------------------------------------------- D2
def d2_joint(d_cmd):
    """Per mode: mode index, joint mean and the precision / log-det of the two-window Gaussian."""
    modes = det._modes_cached(d_cmd.real, d_cmd.imag)
    nv = det._noise_var("stress")
    out = []
    for k, c, J, rv in modes:
        Q = J @ J.T / 3.0
        R = np.diag(rv + nv)
        S = np.block([[Q + R, Q], [Q, Q + R]])
        sign, logdet = np.linalg.slogdet(S)
        out.append((k, np.concatenate([c, c]), np.linalg.inv(S), logdet))
    return out


def _llr_grad(Y, joint):
    n_f = sum(1 for m in joint if m[0] is not None)
    n_n = len(joint) - n_f
    lp, g, isf = [], [], []
    for k, mu, P, ld in joint:
        r = Y - mu
        lp.append(-0.5 * (r @ P @ r + ld) + np.log(0.5 / (n_n if k is None else n_f)))
        g.append(-P @ r)
        isf.append(k is not None)
    lp, g, isf = np.array(lp), np.array(g), np.array(isf)
    lf, ln = logsumexp(lp[isf]), logsumexp(lp[~isf])
    wf, wn = np.exp(lp[isf] - lf), np.exp(lp[~isf] - ln)
    return lf - ln, wf @ g[isf] - wn @ g[~isf]


def d2_llr_adv(M, joint, mode, sense):
    """Worst-case log posterior odds (fault vs normal) by projected sign-gradient steps."""
    Y0 = np.concatenate(M["d2"])
    n = Y0.size // 2
    e = np.zeros(n if mode == "constant" else 2 * n)
    expand = (lambda e: np.concatenate([e, e])) if mode == "constant" else (lambda e: e)
    step = PGD_FRAC * EPS
    best = None
    for _ in range(PGD_STEPS):
        llr, gr = _llr_grad(Y0 + expand(e), joint)
        if best is None or (llr < best if sense == "min" else llr > best):
            best = llr
        if mode == "constant":
            gr = gr[:n] + gr[n:]
        e = np.clip(e + (-1 if sense == "min" else 1) * step * np.sign(gr), -EPS, EPS)
    llr, _ = _llr_grad(Y0 + expand(e), joint)
    return min(best, llr) if sense == "min" else max(best, llr)


# ----------------------------------------------------------------------------- D3
def d3_adv_scores(model_pack, Ms, mode, sense):
    """Worst-case CNN logits for a list of measurement sets, by projected sign-gradient on the perturbations."""
    import torch
    model, mu, sd, dev = model_pack
    F = np.array([np.stack([np.concatenate([y[:6], y[:6] - M["mem"][:6], y[6:], y[6:] - M["mem"][6:]]) for y in M["d3"]], 1)
                  for M in Ms])                                           # (n, 24, T)
    X = torch.tensor(F, dtype=torch.float32, device=dev)
    T = F.shape[2]
    shape = (len(Ms), 12, 1) if mode == "constant" else (len(Ms), 12, T)
    e = torch.zeros(shape, device=dev, requires_grad=True)
    em = torch.zeros((len(Ms), 12, 1), device=dev, requires_grad=(mode != "constant"))
    mu_t, sd_t = torch.tensor(mu, dtype=torch.float32, device=dev), torch.tensor(sd, dtype=torch.float32, device=dev)
    sgn = -1.0 if sense == "min" else 1.0

    def feats(e, em):
        ee = e.expand(-1, -1, T)
        dd = torch.zeros_like(ee) if mode == "constant" else ee - em   # constant: the memory moves with the windows
        dlt = torch.cat([ee[:, :6], dd[:, :6], ee[:, 6:], dd[:, 6:]], 1)
        return (X + dlt - mu_t) / sd_t

    best = None
    for _ in range(PGD_STEPS):
        out = model(feats(e, em)).squeeze(1)
        cur = out.detach().cpu().numpy()
        best = cur if best is None else (np.minimum(best, cur) if sense == "min" else np.maximum(best, cur))
        out.sum().backward()
        with torch.no_grad():
            e += sgn * PGD_FRAC * EPS * torch.sign(e.grad)
            e.clamp_(-EPS, EPS)
            e.grad.zero_()
            if em.requires_grad:
                em += sgn * PGD_FRAC * EPS * torch.sign(em.grad)
                em.clamp_(-EPS, EPS)
                em.grad.zero_()
    return best


def train_d3(specs, train_scen):
    """The pilot's CNN on the design tier, trained on the given scenarios; returns (model, mu, sd, device)."""
    import torch, torch.nn as nn
    from torch_det import seed_everything, time_mean
    X, y = [], []
    for sp in specs:
        if sp["scenario"] not in train_scen:
            continue
        for sd_ in range(3):
            rel = Relay(sp["name"], tier="design", seed=5000 + 100 * sp["scenario"] + sd_)
            how = "oracle" if sp["kind"] == "fault" else "forced"
            X.append(det.d3_features(rel, sp, how))
            y.append(1 if sp["kind"] == "fault" else 0)
            true = rel.idx(sp["t_fault"])
            for i in np.linspace(rel.idx(0.18), true - 3 * CYCLE - 1, 4).astype(int):
                X.append(det.d3_features(rel, dict(sp, t_fault=i / rel.fs + rel.t0), "oracle"))
                y.append(0)
    X, y = np.array(X), np.array(y)
    seed_everything(0)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    mu = X.mean(axis=(0, 2), keepdims=True)[0]
    sd = X.std(axis=(0, 2), keepdims=True)[0] + 1e-9
    model = nn.Sequential(nn.Conv1d(24, 32, 3, padding=1), nn.ReLU(), nn.Conv1d(32, 32, 3, padding=1), nn.ReLU(),
                          time_mean(), nn.Dropout(0.2), nn.Linear(32, 1)).to(dev)
    xt = torch.tensor((X - mu) / sd, dtype=torch.float32, device=dev)
    yt = torch.tensor(y, dtype=torch.float32, device=dev)
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor((y == 0).sum() / max((y == 1).sum(), 1), device=dev))
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-4)
    for _ in range(60):
        model.train()
        perm = torch.randperm(len(xt), device=dev)
        for b in range(0, len(xt), 32):
            j = perm[b:b + 32]
            opt.zero_grad()
            lossf(model(xt[j]).squeeze(1), yt[j]).backward()
            opt.step()
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model, mu, sd, dev


# ----------------------------------------------------------------------------- the study
def main(path):
    specs = json.load(open(path))
    tag = os.path.splitext(os.path.basename(path))[0].replace("_specs", "")
    t0 = time.time()
    # clean measurements: the true trigger for faults, forced for normals, plus calibration pseudo-triggers
    data = {}
    for sp in specs:
        rel = Relay(sp["name"], tier="clean", seed=0)
        true = rel.idx(sp["t_fault"])
        cal = [int(i) for i in np.linspace(rel.idx(0.18), true - 3 * CYCLE - 1, 4)]
        data[sp["name"]] = dict(test=clean_measurements(rel, true), cal=[clean_measurements(rel, i) for i in cal])
    print(f"measurements of {len(specs)} runs  [{time.time() - t0:.0f} s]", flush=True)
    levels = sorted({sp["level"] for sp in specs})
    scen = sorted({sp["scenario"] for sp in specs})
    folds = [scen[k::5] for k in range(5)]
    d3_models = {tuple(f): train_d3(specs, [s for s in scen if s not in f]) for f in folds}
    print(f"D3 folds trained  [{time.time() - t0:.0f} s]", flush=True)
    rows = []
    for lv in levels:
        group = [sp for sp in specs if sp["level"] == lv]
        d = complex(*group[0]["d_cmd"])
        pieces = det.normal_set(d)
        joint = d2_joint(d)
        for mode in ("per-window", "constant"):
            cal = [M for sp in group for M in data[sp["name"]]["cal"]]
            thr0 = max(d0_score_adv(M, mode, "max") for M in cal)
            thr2 = max(d2_llr_adv(M, joint, mode, "max") for M in cal)
            thr3, s3 = -np.inf, {}
            for f in folds:
                pack = d3_models[tuple(f)]
                fs = [sp for sp in group if sp["scenario"] in f]
                calf = [M for sp in fs for M in data[sp["name"]]["cal"]]
                if calf:
                    thr3 = max(thr3, float(np.max(d3_adv_scores(pack, calf, mode, "max"))))
                tests = [sp for sp in fs]
                if tests:
                    for sp, smin, smax in zip(tests, d3_adv_scores(pack, [data[sp["name"]]["test"] for sp in tests], mode, "min"),
                                              d3_adv_scores(pack, [data[sp["name"]]["test"] for sp in tests], mode, "max")):
                        s3[sp["name"]] = (float(smin), float(smax))
            for sp in group:
                M = data[sp["name"]]["test"]
                fault = sp["kind"] == "fault"
                sense = "min" if fault else "max"
                r = dict(name=sp["name"], scenario=sp["scenario"], stratum=sp["stratum"], level=lv, mode=mode, kind=sp["kind"],
                         in_range=sp["in_range"])
                if fault:
                    r["d1_miss"] = bool(d1_worst(M, pieces, mode))
                else:
                    worst_n = max(_dist(pieces, y) for y in M["d1"]) / EPS + 1.0   # the adversary adds up to eps
                    r["d1_false_alarm"] = bool(worst_n > 1.0 + 1e-9)
                s0 = d0_score_adv(M, mode, sense)
                s2 = d2_llr_adv(M, joint, mode, sense)
                s3v = s3[sp["name"]][0 if fault else 1]
                for dn, s, t in (("d0", s0, thr0), ("d2", s2, thr2), ("d3", s3v, thr3)):
                    if fault:
                        r[f"{dn}_miss"] = bool(s <= t)
                    else:
                        r[f"{dn}_false_alarm"] = bool(s > t)
                rows.append(r)
            print(f"level {lv}, {mode}: thresholds D0 {thr0:.3f}, D2 {thr2:.2f}, D3 {thr3:.2f}  [{time.time() - t0:.0f} s]", flush=True)
    summ = {}
    for mode in ("per-window", "constant"):
        print(f"\nworst-case MISS rate, {mode} adversary, by stratum and delta level (D1 D0 D2 D3):")
        for st in ("hard", "hard_bc", "uniform", "outside"):
            cells = []
            for lv in levels:
                q = [r for r in rows if r["mode"] == mode and r["stratum"] == st and r["level"] == lv]
                if q:
                    v = [float(np.mean([r[f"{dn}_miss"] for r in q])) for dn in ("d1", "d0", "d2", "d3")]
                    summ[f"{mode}|{st}|{lv}"] = v
                    cells.append(" ".join(f"{x:.2f}" for x in v))
            print(f"    {st:8s} " + "  |  ".join(cells))
        q = [r for r in rows if r["mode"] == mode and r["kind"] == "normal"]
        print("    worst-case false alarms on normal / confuser runs (D1 D0 D2 D3): " +
              " ".join(f"{np.mean([r[f'{dn}_false_alarm'] for r in q]):.2f}" for dn in ("d1", "d0", "d2", "d3")))
    json.dump(dict(eps=EPS, summary=summ, rows=rows), open(os.path.join(OUT, f"adversary_{tag}.json"), "w"), indent=1)
    print(f"-> results/step3/adversary_{tag}.json  [{time.time() - t0:.0f} s]")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "pilot_specs.json"))
