"""Learning curves of the adapt_grid sequence-trajectory CNN: does 40 epochs overfit?

q3_inputs.cnn_scores trains for a fixed 40 epochs with no validation set and no early stopping. This script
trains the same network, on the same features and outer folds as adaptgrid_run, and records after every
epoch, on the training rows and on the fold's held-out test rows (loading bins the net never saw):
  loss        the weighted BCE the net is trained on (pos_weight = negatives / positives of the training rows)
  auc         ranking quality
  dep_at_0    dependability at the largest score of the training negatives (an in-sample zero-false-trip
              point: optimistic, reported only for the train-vs-test gap)
  gap         largest held-out negative score minus largest training negative score; a growing gap means
              the net separates the negatives it has seen much better than unseen ones, which is what makes
              the zero-false-trip threshold hard to carry to new data
Rising held-out loss while the training loss keeps falling is the overfitting signature. The run also checks
that the replica reproduces q3_inputs.cnn_scores bit for bit at 40 epochs, so the curves are of the network
that produced the published numbers.

    python src/review/cnn_learning_curve.py [--relays adapt_A adapt_B] [--folds 0 1 2] [--epochs 120]
    -> results/adaptgrid/learning_curve_relayfe_cnn.json, results/adaptgrid/learning_curve_relayfe_cnn.png
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from torch_det import seed_everything, time_mean
from review import common as cm
from review import frontend
from review import q3_inputs as q3
from review.zone_cv import zone_task, splits
from review.adaptgrid_run import bundle, features

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")


def curve(Xtr, ytr, Xte, yte, seed, epochs):
    """q3_inputs.cnn_scores with per-epoch evaluation (evaluation does not touch the RNG used by training)."""
    import torch, torch.nn as nn
    seed_everything(seed); np.random.seed(seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    mu = Xtr.mean(axis=(0, 2), keepdims=True); sd = Xtr.std(axis=(0, 2), keepdims=True) + 1e-9
    f = lambda X: torch.tensor((X - mu) / sd, dtype=torch.float32, device=dev)
    C = Xtr.shape[1]
    k1 = 9 if Xtr.shape[2] > 50 else 3
    model = nn.Sequential(nn.Conv1d(C, 32, k1, padding=k1 // 2), nn.ReLU(), nn.Conv1d(32, 32, k1, padding=k1 // 2), nn.ReLU(),
                          time_mean(), nn.Dropout(0.2), nn.Linear(32, 1)).to(dev)
    pos = (ytr == 1).sum(); neg = (ytr == 0).sum()
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg / max(pos, 1), device=dev))
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-4)
    xt, yt = f(Xtr), torch.tensor(ytr, dtype=torch.float32, device=dev)
    xv, yv = f(Xte), torch.tensor(yte, dtype=torch.float32, device=dev)
    hist, scores40 = [], None
    for ep in range(1, epochs + 1):
        model.train()
        perm = torch.randperm(len(xt), device=dev)
        for b in range(0, len(xt), 32):
            j = perm[b:b + 32]
            opt.zero_grad(); lossf(model(xt[j]).squeeze(1), yt[j]).backward(); opt.step()
        model.eval()
        with torch.no_grad():
            st, sv = model(xt).squeeze(1), model(xv).squeeze(1)
            lt, lv = float(lossf(st, yt)), float(lossf(sv, yv))
        st, sv = st.cpu().numpy(), sv.cpu().numpy()
        t0 = st[ytr == 0].max()
        hist.append(dict(epoch=ep, train_loss=lt, test_loss=lv,
                         train_auc=float(roc_auc_score(ytr, st)), test_auc=float(roc_auc_score(yte, sv)),
                         train_dep_at_0=float((st[ytr == 1] > t0).mean()), test_dep_at_0=float((sv[yte == 1] > t0).mean()),
                         test_false_at_0=int((sv[yte == 0] > t0).sum()),
                         gap=float(sv[yte == 0].max() - t0)))
        if ep == 40:
            scores40 = sv.copy()
    return hist, scores40


def main(relays=("adapt_A", "adapt_B"), folds=(0, 1, 2), epochs=120, kind="grouped", seed=0):
    t0 = time.time()
    frontend.enable()
    res = dict(script="cnn_learning_curve", commit=cm.git_commit(), frontend="relayfe", split=kind, seed=seed,
               epochs=epochs, published_epochs=40, relays={})
    for relay in relays:
        R = bundle(relay, None)
        idx, y, groups = zone_task(R)
        X = features(R, idx)["seq"]
        per = {}
        for f, tr, te, meta in splits(kind, R, idx, y, groups):
            if f not in folds:
                continue
            s = f + seed
            hist, sv40 = curve(X[tr], y[tr], X[te], y[te], s, epochs)
            ref = q3.cnn_scores(X[tr], y[tr], [X[te]], s)[0]          # the published network, 40 epochs
            same = bool(np.array_equal(np.asarray(ref, np.float32), sv40.astype(np.float32)))
            best = min(hist, key=lambda h: h["test_loss"])
            per[str(f)] = dict(history=hist, replica_matches_cnn_scores_at_40=same,
                               best_test_loss_epoch=best["epoch"], n_train=int(len(tr)), n_test=int(len(te)))
            h40 = hist[39]
            print(f"  [{relay} fold {f}] replica == cnn_scores at 40 epochs: {same} | best held-out loss at epoch "
                  f"{best['epoch']} | epoch 40: train loss {h40['train_loss']:.3f} test loss {h40['test_loss']:.3f} "
                  f"test AUC {h40['test_auc']:.4f} gap {h40['gap']:+.2f} [{time.time()-t0:.0f}s]", flush=True)
        res["relays"][relay] = per
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "learning_curve_relayfe_cnn.json")
    json.dump(res, open(path, "w"), indent=1)
    plot(res, os.path.join(OUT, "learning_curve_relayfe_cnn.png"))
    print("saved", path, f"[{res['runtime_s']:.0f}s]")
    return res


def plot(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    relays = list(res["relays"])
    fig, ax = plt.subplots(2, len(relays), figsize=(6 * len(relays), 7), squeeze=False)
    for c, relay in enumerate(relays):
        for f, P in res["relays"][relay].items():
            H = P["history"]; ep = [h["epoch"] for h in H]
            l, = ax[0, c].plot(ep, [h["train_loss"] for h in H], lw=1.2, label=f"fold {f} train")
            ax[0, c].plot(ep, [h["test_loss"] for h in H], lw=1.2, ls="--", color=l.get_color(), label=f"fold {f} held-out")
            ax[1, c].plot(ep, [h["gap"] for h in H], lw=1.2, color=l.get_color(), label=f"fold {f}")
        for r in (0, 1):
            ax[r, c].axvline(res["published_epochs"], color="grey", lw=0.8, ls=":")
        ax[0, c].set_title(f"{relay}: weighted BCE (solid train, dashed held-out loading bins)")
        ax[0, c].set_yscale("log"); ax[0, c].set_xlabel("epoch"); ax[0, c].legend(fontsize=7)
        ax[1, c].set_title("largest held-out negative score minus largest training negative score")
        ax[1, c].set_xlabel("epoch"); ax[1, c].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--relays", nargs="+", default=["adapt_A", "adapt_B"])
    ap.add_argument("--folds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--epochs", type=int, default=120)
    a = ap.parse_args()
    main(tuple(a.relays), tuple(a.folds), a.epochs)
