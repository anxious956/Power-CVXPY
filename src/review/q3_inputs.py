"""Q3: which input, instead of raw samples? Same task, folds and thresholds as zone_cv.py (own-99 % guard band,
grouped 5-fold, first repeat), decision time 20 ms, relays A and B.

Inputs (all causal, computed from the window ending at the decision time)
  raw        real_ml.raw_window: 40 ms pre-fault + 20 ms post, V/V_nom and I Z_reach/V_nom (6 x 384)
  seq traj   sliding full-cycle DFT phasors, currents through the mimic filter, ending every 2 ms from inception
             to 20 ms (10 frames): V0 V1 V2 I0 I1 I2 and their increments against a 3-cycle pre-fault memory,
             referenced to the angle of V1 memory, V/V_nom, I Z_reach/V_nom (24 x 10)
  loop traj  six k0-compensated loop impedances in units of the protected line's reactance from half-cycle
             mimic-filtered phasors, every 2 ms (12 x 10), clipped at +-20
  snapshot   real_ml / zone_detect engineered features (36)
Canonical phase rotation ('canon'): the raw channels are rotated per case so that the loop released by the
causal phase selector at 20 ms is 'ag' (ground faults) or 'bc' (phase faults) before any feature is computed.
Models: MLP (real_ml hyperparameters; ChannelScaler for raw, StandardScaler otherwise), a small 1D CNN (torch),
logistic regression on the snapshot (real_ml), and a monotone-constrained gradient boosting on the last
loop-trajectory frame (in-zone probability non-increasing in each loop reactance).
Learning curves: MLP on raw-canon and loop-traj-canon with 25 / 50 / 100 % of each training fold.

    python src/review/q3_inputs.py
"""
import sys, os, json, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from review import common as cm
from review import ladder as ld
from review.zone_cv import zone_task, splits
import real_ml
from zone_detect import zone_features

CODE = ("src/review/q3_inputs.py", "src/review/ladder.py", "src/review/common.py", "src/review/setting_study.py",
        "src/review/zone_cv.py", "src/real_ml.py", "src/zone_detect.py", "src/zone_model.py", "src/evemt.py")
FRAMES_MS = np.arange(2, 21, 2)
HELD = ("own99", "reverse_bus", "switching")


def rotation_index(R, sel):
    vpre, vpost, ipre, ipost = cm.phasors_at(R, sel, 20, "full", True)
    mask = cm.phase_selection(ipre, ipost)
    r = np.zeros(len(sel), int)
    g = mask[:, :3].any(1)
    r[g] = mask[g, :3].argmax(1)                         # selected phase -> a
    p = ~g & mask[:, 3:].any(1)
    r[p] = (mask[p, 3:].argmax(1) - 1) % 3               # selected pair (ab, bc, ca) -> bc
    return r


def rotated(R, sel, r):
    """Copy of R whose full record for `sel` has phase channels cyclically rotated by r (a <- phase r)."""
    X = np.asarray(R["full"][sel]).copy()
    for k in (1, 2):
        m = r == k
        for base in (0, 3):
            X[m, base:base + 3] = np.roll(X[m, base:base + 3], -k, axis=1)
    R2 = dict(R); R2["full"] = X
    return R2, np.arange(len(sel))


def seq_traj(R, idx):
    vmem = cm.seq_phasors(R["full"][idx][:, :3], R["ev"] - 128, 384)
    ref = vmem[:, 1] / np.abs(vmem[:, 1])
    Xi, H = cm.mimic(R["full"][idx][:, 3:].astype(np.float64), (R["lp"]["z1"].imag / R["lp"]["z1"].real) / (2 * np.pi))
    imem = cm.seq_phasors(Xi, R["ev"] - 128, 384, H=H)
    s = R["z_reach"] / cm.V_NOM_PEAK
    frames = []
    for t in FRAMES_MS:
        end = R["ev"] + int(t * 6.4)
        v = cm.seq_phasors(R["full"][idx][:, :3], end) / ref[:, None] / cm.V_NOM_PEAK
        i = cm.seq_phasors(Xi, end, H=H) / ref[:, None] * s
        dv, di = v - vmem / ref[:, None] / cm.V_NOM_PEAK, i - imem / ref[:, None] * s
        z = np.concatenate([v, i, dv, di], 1)
        frames.append(np.concatenate([z.real, z.imag], 1))
    return np.stack(frames, 2)                           # (n, 24, 10)


def loop_traj(R, idx):
    frames = []
    xl = R["z1L"].imag
    for t in FRAMES_MS:
        vpre, vpost, ipre, ipost = cm.phasors_at(R, idx, t, "half", True)
        Lp = cm.loops(R, vpost, ipost, vpre, ipre)
        Z = np.clip(Lp["V"] / (Lp["I"] + 1e-9) / xl, -20, 20)
        frames.append(np.concatenate([Z.real, Z.imag], 1))
    return np.stack(frames, 2)                           # (n, 12, 10)


def cnn_scores(Xtr, ytr, Xte_list, seed, epochs=40):
    import torch, torch.nn as nn
    torch.manual_seed(seed); np.random.seed(seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    mu = Xtr.mean(axis=(0, 2), keepdims=True); sd = Xtr.std(axis=(0, 2), keepdims=True) + 1e-9
    f = lambda X: torch.tensor((X - mu) / sd, dtype=torch.float32, device=dev)
    C = Xtr.shape[1]
    k1 = 9 if Xtr.shape[2] > 50 else 3
    model = nn.Sequential(nn.Conv1d(C, 32, k1, padding=k1 // 2), nn.ReLU(), nn.Conv1d(32, 32, k1, padding=k1 // 2), nn.ReLU(),
                          nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Dropout(0.2), nn.Linear(32, 1)).to(dev)
    pos = (ytr == 1).sum(); neg = (ytr == 0).sum()
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg / max(pos, 1), device=dev))
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-4)
    xt, yt = f(Xtr), torch.tensor(ytr, dtype=torch.float32, device=dev)
    for _ in range(epochs):
        model.train()
        perm = torch.randperm(len(xt), device=dev)
        for b in range(0, len(xt), 32):
            j = perm[b:b + 32]
            opt.zero_grad(); lossf(model(xt[j]).squeeze(1), yt[j]).backward(); opt.step()
    model.eval()
    with torch.no_grad():
        return [model(f(X)).squeeze(1).cpu().numpy() for X in Xte_list]


def mlp_scores(Xtr, ytr, Xte_list, seed, raw=False):
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    m = make_pipeline(real_ml.ChannelScaler() if raw else StandardScaler(),
                      MLPClassifier(hidden_layer_sizes=(100,), max_iter=800, early_stopping=True, random_state=seed))
    real_ml.fit_balanced(m, Xtr, ytr, seed)
    return [real_ml._mlp_logit(m, X) for X in Xte_list]


def lr_scores(Xtr, ytr, Xte_list, seed):
    m = real_ml.models(seed)["engineered + LR"].fit(Xtr, ytr)
    return [m.decision_function(X) for X in Xte_list]


def mgbm_scores(Xtr, ytr, Xte_list, seed):
    from sklearn.ensemble import HistGradientBoostingClassifier
    cst = [0] * 6 + [-1] * 6                              # last frame: 6 loop R (free), 6 loop X (non-increasing)
    m = real_ml.fit_balanced(HistGradientBoostingClassifier(monotonic_cst=cst, random_state=seed), Xtr, ytr, seed)
    return [m.decision_function(X) for X in Xte_list]


def oof_threshold(fn, Xtr, ytr, gtr, seed, far=0.05):
    from sklearn.model_selection import StratifiedGroupKFold
    s = np.zeros(len(ytr))
    for k, (a, b) in enumerate(StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(Xtr, ytr, gtr)):
        s[b] = fn(Xtr[a], ytr[a], [Xtr[b]], seed + 100 + k)[0]
    return cm.thr_at_far(s[ytr == 0], far)


if __name__ == "__main__":
    t0 = time.time()
    commit = cm.git_commit()
    if not cm.code_unchanged(commit, commit, CODE):
        raise SystemExit("commit the experiment code first")
    res = {}
    for name in ("testgrid_B", "testgrid_A"):
        R = cm.load_relay(name)
        R["g"] = type("G", (), dict(z1=R["lp"]["z1"], z0_ratio=R["lp"]["z0"] / R["lp"]["z1"]))
        sel = np.where(np.any([R[h] for h in ("pos", "neg") + HELD], axis=0))[0]
        idx, y, groups = zone_task(R)
        zpos = np.searchsorted(sel, idx); held = np.setdiff1d(np.arange(len(sel)), zpos)
        rot = rotation_index(R, sel)
        Rc, cidx = rotated(R, sel, rot)
        Rc["ev"] = R["ev"]
        feats = {"raw": real_ml.raw_window(R, sel, 20), "raw canon": real_ml.raw_window(Rc, cidx, 20),
                 "seq traj": seq_traj(R, sel), "seq traj canon": seq_traj(Rc, cidx),
                 "loop traj": loop_traj(R, sel), "loop traj canon": loop_traj(Rc, cidx),
                 "snapshot": zone_features(real_ml.phasor_view(R, sel, 20), R["g"])}
        flat = lambda X: X.reshape(len(X), -1)
        runs = [("MLP", k, lambda Xa, ya, Xl, s, raw=k.startswith("raw"): mlp_scores(flat(Xa), ya, [flat(x) for x in Xl], s, raw), 1.0)
                for k in ("raw", "raw canon", "seq traj", "seq traj canon", "loop traj", "loop traj canon")]
        runs += [("CNN", k, cnn_scores, 1.0) for k in ("raw canon", "seq traj canon", "loop traj canon")]
        runs += [("CNN", "raw canon 6ch", lambda Xa, ya, Xl, s: cnn_scores(Xa.reshape(len(Xa), 6, -1), ya, [x.reshape(len(x), 6, -1) for x in Xl], s), 1.0)]
        runs = [r for r in runs if not (r[0] == "CNN" and r[1] == "raw canon")]
        runs += [("LR", "snapshot", lr_scores, 1.0),
                 ("monotone GBM", "loop traj canon (last frame)", lambda Xa, ya, Xl, s: mgbm_scores(Xa[:, :, -1], ya, [x[:, :, -1] for x in Xl], s), 1.0)]
        runs += [("MLP", k, lambda Xa, ya, Xl, s, raw=k.startswith("raw"): mlp_scores(flat(Xa), ya, [flat(x) for x in Xl], s, raw), frac)
                 for k in ("raw canon", "loop traj canon") for frac in (0.25, 0.5)]
        res[name] = {}
        for model, inp, fn, frac in runs:
            key = f"{model} | {inp} | train {int(frac * 100)} %"
            cfg = dict(script="q3", relay=name, key=key)
            path = os.path.join(cm.ROOT, "logs", "ckpt", "q3", cm.config_hash(cfg) + ".pkl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.path.exists(path):
                rec = pickle.load(open(path, "rb"))
                assert rec["_config"] == cfg and cm.code_unchanged(rec["_commit"], commit, CODE), "checkpoint mismatch"
                res[name][key] = rec["result"]; continue
            F = feats["loop traj canon" if inp.startswith("loop traj canon") else ("raw canon" if inp.startswith("raw canon") else inp)]
            Fz, Fh = F[zpos], F[held]
            dec = np.zeros(len(sel), bool); votes = np.zeros(len(sel)); aucs = []
            for f, tr, te, meta in splits("grouped", R, idx, y, groups):
                if f >= 5:
                    break
                if frac < 1.0:
                    ug = np.unique(groups[tr]); keep = np.random.default_rng(f).choice(ug, int(len(ug) * frac), replace=False)
                    tr = tr[np.isin(groups[tr], keep)]
                thr = oof_threshold(fn, Fz[tr], y[tr], groups[tr], f)
                s_te, s_h = fn(Fz[tr], y[tr], [Fz[te], Fh], f)
                dec[zpos[te]] = s_te > thr; votes[held] += s_h > thr
                aucs.append(roc_auc_score(y[te], s_te))
            dec[held] = votes[held] >= 3
            r = ld.rates(dec, R, sel)
            out = dict(auc=float(np.mean(aucs)), auc_sd=float(np.std(aucs)), dependability=r["pos"]["rate"], dep40=r["dep_by_rf"]["40"],
                       beyond=r["neg"]["rate"], beyond_dedup=r["neg"]["dedup"], own99_guard=r["own99"]["rate"],
                       reverse_bus=r["reverse_bus"]["rate"], switching=r["switching"]["rate"])
            pickle.dump(dict(_commit=commit, _config=cfg, result=out), open(path, "wb"))
            res[name][key] = out
            print(f"[{name}] {key:45s} AUC {out['auc']:.3f}+-{out['auc_sd']:.3f}  dep {out['dependability']*100:5.1f}  dep@40 {out['dep40']*100:5.1f}  "
                  f"beyond {out['beyond']*100:5.1f}  own99 {out['own99_guard']*100:5.1f}  rev-bus {out['reverse_bus']*100:5.1f}  "
                  f"switching {out['switching']*100:5.1f}  [{time.time()-t0:.0f}s]", flush=True)
            json.dump(res, open(os.path.join(cm.ROOT, "results", "review", "q3_inputs.json"), "w"), indent=1)
        del R, Rc, feats
    print("saved results/review/q3_inputs.json")
