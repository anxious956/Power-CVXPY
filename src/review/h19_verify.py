"""Independent check of the synthetic H19 finding (per-waveform standardisation in detect.train_cnn).
Author's zone data at quick size (zone_detect.make_zone_dataset, rF 0.3, boundary band, delta = 0, seeds 0-1),
author's CNN architecture and training loop, two input scalings: the author's per-waveform per-channel z-score,
and one global scale per channel fitted on the training set. AUC on the test set.

    python src/review/h19_verify.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from dataclasses import replace
from sklearn.metrics import roc_auc_score
import detect
from zone_detect import make_zone_dataset
from zone_model import ZoneParams
from waveforms import SigParams

out = {}
grid = replace(ZoneParams(), rF=0.3)
for sd in (0, 1):
    Xtr, ytr, _ = make_zone_dataset(350, np.random.default_rng(100 + 17 * sd), 0.0, SigParams(), grid, True)
    Xte, yte, _ = make_zone_dataset(250, np.random.default_rng(999 + 31 * sd), 0.0, SigParams(), grid, True)
    _, s_te = detect.train_cnn(Xtr, ytr, Xte, epochs=12, seed=sd)
    a_orig = roc_auc_score(yte, s_te)
    mu = Xtr.mean(axis=(0, 2), keepdims=True); sdv = Xtr.std(axis=(0, 2), keepdims=True)
    # detect.train_cnn normalises per waveform internally; feed it globally scaled data AND disable that step
    orig_norm = None
    import types
    src = detect.train_cnn.__code__
    Xg_tr, Xg_te = ((Xtr - mu) / sdv).astype(np.float32), ((Xte - mu) / sdv).astype(np.float32)
    def train_global(Xa, ya, Xb, epochs, seed):
        import torch, torch.nn as nn
        torch.manual_seed(seed)
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        xt = torch.tensor(Xa, device=dev); yt = torch.tensor(ya, dtype=torch.float32, device=dev); xv = torch.tensor(Xb, device=dev)
        model = nn.Sequential(nn.Conv1d(6, 32, 9, stride=2, padding=4), nn.BatchNorm1d(32), nn.ReLU(),
                              nn.Conv1d(32, 64, 7, stride=2, padding=3), nn.BatchNorm1d(64), nn.ReLU(),
                              nn.Conv1d(64, 64, 5, stride=2, padding=2), nn.BatchNorm1d(64), nn.ReLU(),
                              nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Dropout(0.2), nn.Linear(64, 1)).to(dev)
        opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-4); lossf = nn.BCEWithLogitsLoss()
        for ep in range(epochs):
            model.train(); perm = torch.randperm(len(xt), device=dev)
            for b in range(0, len(xt), 64):
                i = perm[b:b + 64]; opt.zero_grad(); lossf(model(xt[i]).squeeze(1), yt[i]).backward(); opt.step()
        model.eval()
        with torch.no_grad():
            return model(xv).squeeze(1).cpu().numpy()
    a_glob = roc_auc_score(yte, train_global(Xg_tr, ytr, Xg_te, 12, sd))
    out[f"seed {sd}"] = dict(per_waveform=float(a_orig), global_per_channel=float(a_glob))
    print(f"seed {sd}: AUC per-waveform (author) {a_orig:.4f}   global per-channel {a_glob:.4f}", flush=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "results", "review", "h19_verify.json"), "w"), indent=1)
