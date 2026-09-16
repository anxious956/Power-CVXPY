"""
WP3 experiment: how small can the auxiliary signal be and still be detected?

Three detectors on the same data, same protocol:
  1. |i-|      negative-sequence magnitude in the post-event window (the obvious threshold)
  2. |di-|     incremental negative sequence: post-event minus pre-event (the strong baseline,
               the quantity Taylor's 2026 incremental-quantities paper is built on)
  3. CNN       small 1D convolutional net on the raw six-channel waveform

Protocol: for each injection magnitude delta, generate an independent train and test set.
Every detector produces a score; its threshold is set on the TRAIN set at a fixed
false-alarm rate, then detection rate is measured on the TEST set. Same data, same budget,
so the comparison is fair.

Negatives are half "quiet" (normal, balanced load step) and half events that themselves
create negative sequence (unbalanced load switching, motor start). Those are what make
the threshold detectors fail.

  python src/detect.py            # full sweep, writes results/detection_sweep.png + .json
  python src/detect.py --quick    # fewer deltas and samples
"""
import sys, os, json, time, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from waveforms import (make_dataset, sequence_phasors, SigParams, CYCLE, EVENT, FAULTS)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
os.makedirs(OUT, exist_ok=True)
FAR = 0.01          # false-alarm rate the threshold is set to, on the training set


# ----------------------------------------------------------------- threshold detectors
def score_negseq(X):
    """|i-| measured one cycle after the event."""
    return np.array([abs(sequence_phasors(x[3:], EVENT + CYCLE)[2]) for x in X])


def score_incremental(X):
    """|i- post - i- pre|: the change in negative sequence caused by the event."""
    out = []
    for x in X:
        pre = sequence_phasors(x[3:], EVENT - 2 * CYCLE)[2]
        post = sequence_phasors(x[3:], EVENT + CYCLE)[2]
        out.append(abs(post - pre))
    return np.array(out)


def relay_features(X):
    """The engineered feature vector a protection engineer would actually build:
    sequence magnitudes, the ratios and relative angles that directional and ground
    elements are made of, and their incremental (post minus pre) versions.
    This is the strong conventional baseline; beating |i-| alone proves nothing."""
    feats = []
    for x in X:
        vpre, vpost = sequence_phasors(x[:3], EVENT - 2 * CYCLE), sequence_phasors(x[:3], EVENT + CYCLE)
        ipre, ipost = sequence_phasors(x[3:], EVENT - 2 * CYCLE), sequence_phasors(x[3:], EVENT + CYCLE)
        v0, v1, v2 = vpost; i0, i1, i2 = ipost
        dv0, dv1, dv2 = vpost - vpre; di0, di1, di2 = ipost - ipre
        e = 1e-9
        f = [abs(v1), abs(v2), abs(v0), abs(i1), abs(i2), abs(i0),
             abs(dv1), abs(dv2), abs(dv0), abs(di1), abs(di2), abs(di0),
             abs(i2) / (abs(i1) + e), abs(i0) / (abs(i1) + e), abs(i0) / (abs(i2) + e),
             abs(di0) / (abs(di2) + e), abs(di2) / (abs(di1) + e),
             np.angle(i2 / (i1 + e)), np.angle(i0 / (i1 + e)), np.angle(i0 / (i2 + e)),
             np.angle(v2 / (i2 + e)), np.angle(v0 / (i0 + e)),
             np.angle(di2 / (di1 + e)), np.angle(dv2 / (di2 + e)), np.angle(dv0 / (di0 + e)),
             abs(v2 / (i2 + e)), abs(v0 / (i0 + e)), abs(dv1 / (di1 + e))]
        feats.append(f)
    return np.nan_to_num(np.array(feats), nan=0.0, posinf=0.0, neginf=0.0)


def score_engineered(Xtr, ytr, Xte, seed=0):
    """Logistic regression on relay_features: the conventional multivariate detector."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    ftr, fte = relay_features(Xtr), relay_features(Xte)
    clf = make_pipeline(StandardScaler(),
                        LogisticRegression(max_iter=3000, C=1.0, random_state=seed))
    clf.fit(ftr, ytr)
    return clf.decision_function(ftr), clf.decision_function(fte)


def evaluate(scores_tr, y_tr, scores_te, y_te, far=FAR):
    """Threshold fixed on TRAIN at the false-alarm budget, applied to TEST.

    The polarity is chosen on the training set too: a fault may show up as an unusually
    HIGH score or an unusually LOW one, and which it is depends on the injection. Letting
    the baseline pick its own polarity is the fair version of the comparison.
    """
    best = None
    for sign in (+1, -1):
        s_tr, s_te = sign * scores_tr, sign * scores_te
        neg = np.sort(s_tr[y_tr == 0])
        k = int(np.ceil((1 - far) * len(neg))) - 1
        thr = neg[min(max(k, 0), len(neg) - 1)]
        dr = float((s_te[y_te == 1] > thr).mean())
        if best is None or dr > best["detection_rate"]:
            best = dict(detection_rate=dr,
                        false_alarm=float((s_te[y_te == 0] > thr).mean()),
                        threshold=float(thr), polarity=int(sign))
    return best


# ------------------------------------------------------------------------ learned detector
def train_cnn(Xtr, ytr, Xte, epochs=18, seed=0, verbose=False):
    import torch, torch.nn as nn
    torch.manual_seed(seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"

    def norm(X):
        m = X.mean(axis=2, keepdims=True)
        s = X.std(axis=2, keepdims=True) + 1e-6
        return (X - m) / s

    Xtr_n, Xte_n = norm(Xtr), norm(Xte)
    xt = torch.tensor(Xtr_n, device=dev)
    yt = torch.tensor(ytr, dtype=torch.float32, device=dev)
    xv = torch.tensor(Xte_n, device=dev)

    model = nn.Sequential(
        nn.Conv1d(6, 32, 9, stride=2, padding=4), nn.BatchNorm1d(32), nn.ReLU(),
        nn.Conv1d(32, 64, 7, stride=2, padding=3), nn.BatchNorm1d(64), nn.ReLU(),
        nn.Conv1d(64, 64, 5, stride=2, padding=2), nn.BatchNorm1d(64), nn.ReLU(),
        nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Dropout(0.2), nn.Linear(64, 1),
    ).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-4)
    lossf = nn.BCEWithLogitsLoss()
    n, bs = len(xt), 64
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(n, device=dev)
        tot = 0.0
        for b in range(0, n, bs):
            idx = perm[b:b + bs]
            opt.zero_grad()
            loss = lossf(model(xt[idx]).squeeze(1), yt[idx])
            loss.backward(); opt.step()
            tot += loss.item() * len(idx)
        if verbose and (ep + 1) % 6 == 0:
            print(f"      epoch {ep+1:2d}  loss {tot/n:.4f}")
    model.eval()
    with torch.no_grad():
        s_tr = model(xt).squeeze(1).cpu().numpy()
        s_te = model(xv).squeeze(1).cpu().numpy()
    return s_tr, s_te


# ------------------------------------------------------------------------------- sweep
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--noise", type=float, default=0.01)
    ap.add_argument("--epochs", type=int, default=18)
    ap.add_argument("--easy", action="store_true", help="full fault population instead of the ambiguous subset")
    args = ap.parse_args()

    # Sweep |delta| along the direction the design tool chose for this grid, so WP1 and WP3
    # are talking about the same signal. The design tool's answer for `weak_sg` is the
    # vertical line in the figure: the smallest delta it can certify as separating.
    opt_file = os.path.join(OUT, "aux_signal_toy_weak_sg.json")
    with open(opt_file) as f:
        o = json.load(f)["cvxpy_opt"]
    design_delta = complex(o[0], o[1])
    direction = design_delta / abs(design_delta)

    mags = [0.0, 0.025, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.40, 0.514]
    n_tr, n_te = 900, 450
    if args.quick:
        mags = [0.0, 0.05, 0.10, 0.20, 0.40]
        n_tr, n_te = 300, 200
        args.epochs = 10

    p = SigParams(noise=args.noise)
    rows = []
    print(f"design tool optimum for this grid: |delta| = {abs(design_delta):.3f} pu at "
          f"{np.degrees(np.angle(design_delta)):.1f} deg")
    print(f"sweep of |delta| along that direction: {mags}")
    print(f"train {2*n_tr} faults + {2*n_tr} non-faults, test {2*n_te} + {2*n_te}, "
          f"FAR budget {FAR:.0%}")
    for t in mags:
        d = t * direction
        t0 = time.time()
        Xtr, ytr, _ = make_dataset(n_tr, np.random.default_rng(100), delta=d, p=p, hard=not args.easy)
        Xte, yte, ste = make_dataset(n_te, np.random.default_rng(999), delta=d, p=p, hard=not args.easy)
        row = dict(delta=t)
        for name, fn in (("negseq", score_negseq), ("incremental", score_incremental)):
            row[name] = evaluate(fn(Xtr), ytr, fn(Xte), yte)
        e_tr, e_te = score_engineered(Xtr, ytr, Xte)
        row["engineered"] = evaluate(e_tr, ytr, e_te, yte)
        s_tr, s_te = train_cnn(Xtr, ytr, Xte, epochs=args.epochs)
        row["cnn"] = evaluate(s_tr, ytr, s_te, yte)
        # which non-fault event fools each detector most
        for name in ("negseq", "incremental", "engineered", "cnn"):
            sc = {"negseq": score_negseq(Xte), "incremental": score_incremental(Xte),
                  "engineered": e_te, "cnn": s_te}[name]
            fp = row[name]["polarity"] * sc > row[name]["threshold"]
            row[name]["fp_by_event"] = {e: int(((ste == e) & fp).sum())
                                        for e in np.unique(ste[yte == 0])}
        rows.append(row)
        print(f"  |delta|={t:.3f}  |i-| {row['negseq']['detection_rate']*100:5.1f}%   "
              f"|di-| {row['incremental']['detection_rate']*100:5.1f}%   "
              f"engineered {row['engineered']['detection_rate']*100:5.1f}%   "
              f"CNN {row['cnn']['detection_rate']*100:5.1f}%    "
              f"(FAR {row['negseq']['false_alarm']*100:.1f}/"
              f"{row['incremental']['false_alarm']*100:.1f}/"
              f"{row['engineered']['false_alarm']*100:.1f}/"
              f"{row['cnn']['false_alarm']*100:.1f}%)  [{time.time()-t0:.0f}s]")

    # ------------------------------------------------------------------------ figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(12.5, 4.8))
    styles = [("negseq", "|i⁻| threshold", "o", "tab:gray"),
              ("incremental", "|Δi⁻| incremental", "s", "tab:blue"),
              ("engineered", "engineered features + LR", "D", "tab:green"),
              ("cnn", "learned (1D CNN, raw waveform)", "^", "tab:red")]
    for key, lab, mk, c in styles:
        axs[0].plot(mags, [r[key]["detection_rate"] * 100 for r in rows],
                    marker=mk, color=c, label=lab)
    axs[0].axvline(abs(design_delta), ls=":", lw=1.2, color="tab:green")
    axs[0].text(abs(design_delta), 50, "  design tool's\n  certified δ", fontsize=8,
                color="tab:green", va="center")
    axs[0].axhline(95, ls="--", lw=.8, color="k")
    axs[0].text(mags[-1], 95.6, "95%", ha="right", fontsize=8)
    axs[0].set_xlabel("auxiliary signal magnitude δ  (pu negative-sequence current)")
    axs[0].set_ylabel(f"detection rate at {FAR:.0%} false alarm (%)")
    axs[0].set_title("How small can the auxiliary signal be?")
    axs[0].grid(alpha=.3); axs[0].legend(fontsize=8); axs[0].set_ylim(-3, 103)

    events = sorted({e for r in rows for e in r["negseq"]["fp_by_event"]})
    w = 0.26
    xpos = np.arange(len(events))
    w = 0.2
    for j, (key, lab, mk, c) in enumerate(styles):
        tot = [sum(r[key]["fp_by_event"].get(e, 0) for r in rows) for e in events]
        axs[1].bar(xpos + (j - 1.5) * w, tot, w, color=c, label=lab)
    axs[1].set_xticks(xpos); axs[1].set_xticklabels(events, fontsize=8)
    axs[1].set_ylabel("false alarms, summed over the sweep")
    axs[1].set_title("Which non-fault events fool each detector")
    axs[1].grid(alpha=.3, axis="y"); axs[1].legend(fontsize=8)
    plt.tight_layout()
    png = os.path.join(OUT, "detection_sweep.png")
    plt.savefig(png, dpi=140)
    json.dump(dict(far=FAR, magnitudes=mags, n_train=n_tr, n_test=n_te,
                   noise=args.noise,
                   design_delta=[design_delta.real, design_delta.imag, abs(design_delta)],
                   rows=rows),
              open(os.path.join(OUT, "detection_sweep.json"), "w"), indent=2)
    print("saved", os.path.relpath(png))


if __name__ == "__main__":
    main()
