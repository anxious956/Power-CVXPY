"""
WP3, second experiment: in-zone vs out-of-zone, the decision distance protection is about.

Positives: line-to-ground and line-to-line faults on the protected line, within reach.
Negatives: the same fault types on the adjacent line, past the remote bus.
Both carry fault resistance drawn over the same range, and the inverter at the remote bus
injects the auxiliary signal continuously in every case.

This is much harder than fault-versus-load. With a resistive fault and remote infeed the
apparent impedance of an in-zone fault at 80 % and an out-of-zone fault at 10 % of the next
line nearly coincide, which is the reach problem Taylor's uncertainty sets are built for.

Detectors, all on the same data with thresholds and polarity fixed on train at a 1 %
false-alarm budget:
  1. |Z| reactance     the textbook element: is the apparent reactance inside the reach?
  2. |i-|              negative-sequence magnitude
  3. engineered + LR   apparent impedance of both loops, sequence magnitudes, ratios, angles
  4. 1D CNN            raw six-channel waveform

  python src/zone_detect.py [--quick]
"""
import sys, os, json, time, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dataclasses import replace as _replace
from zone_model import ZoneParams, solve_zone, apparent_impedance
from waveforms import _synth, SigParams, sequence_phasors, CYCLE, EVENT
from detect import evaluate, train_cnn, FAR

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
os.makedirs(OUT, exist_ok=True)


def generate(kind, rng, delta=0.0, p=None, grid=None, boundary=True):
    """kind: 'ag'/'ab' (in zone) or 'ag2'/'ab2' (out of zone). Returns (x, meta).

    boundary=True concentrates the sampling in the band where the two classes are genuinely
    ambiguous: just inside the reach versus just past the remote bus. Sampling the whole
    line instead fills the set with easy cases and flatters every detector.
    """
    p = p or SigParams()
    g = grid or ZoneParams()
    # System conditions the relay cannot measure and that change with switching: the source
    # impedance behind it, the loads on both buses, the inverter's output and the grounding.
    # These are the uncertainties Taylor's sets are built around, and without them the map
    # from measurement to class is nearly invertible and every detector looks perfect.
    fz = rng.uniform(0.5, 1.8)
    g = _replace(g,
                 zs={k: v * fz for k, v in g.zs.items()},
                 yR={k: v * rng.uniform(0.6, 1.5) for k, v in g.yR.items()},
                 yS={k: v * rng.uniform(0.6, 1.5) for k, v in g.yS.items()},
                 ibr_zero_z=g.ibr_zero_z * rng.uniform(0.6, 1.6))
    srcL = g.e0 * (1 + rng.uniform(-0.05, 0.05)) * np.exp(1j * rng.uniform(-0.09, 0.09))
    iR = g.i0 * rng.uniform(0.5, 1.6) * np.exp(1j * rng.uniform(-0.4, 0.4))
    if kind.endswith("2"):
        m = rng.uniform(0.02, 0.18) if boundary else rng.uniform(0.02, 0.9)
    else:
        m = rng.uniform(0.62, g.reach) if boundary else rng.uniform(0.05, g.reach)
    mr = rng.uniform(0.0, 1.0)
    pre = solve_zone(g, "N", srcL, iR, delta)
    post = solve_zone(g, kind, srcL, iR, delta, m, mr)
    v = _synth(pre[:3], post[:3], p, rng, is_current=False)
    i = _synth(pre[3:], post[3:], p, rng, is_current=True)
    return np.vstack([v, i]).astype(np.float32), dict(kind=kind, m=m, rf=mr * g.rF)


def make_zone_dataset(n, rng, delta=0.0, p=None, grid=None, boundary=True):
    X, y, kinds = [], [], []
    for k in ("ag", "ab"):
        for _ in range(n):
            x, _mt = generate(k, rng, delta, p, grid, boundary)
            X.append(x); y.append(1); kinds.append(k)
    for k in ("ag2", "ab2"):
        for _ in range(n):
            x, _mt = generate(k, rng, delta, p, grid, boundary)
            X.append(x); y.append(0); kinds.append(k)
    return np.stack(X), np.array(y), np.array(kinds)


# ------------------------------------------------------------------------- detectors
def _phasors(x):
    vpre = sequence_phasors(x[:3], EVENT - 2 * CYCLE); vpost = sequence_phasors(x[:3], EVENT + CYCLE)
    ipre = sequence_phasors(x[3:], EVENT - 2 * CYCLE); ipost = sequence_phasors(x[3:], EVENT + CYCLE)
    return vpre, vpost, ipre, ipost


def _zapp(vpost, ipost, loop):
    y = np.array([vpost[1], vpost[2], vpost[0], ipost[1], ipost[2], ipost[0]])
    return apparent_impedance(y, loop)


def score_reactance(X):
    """The textbook distance element: the reactance of the apparent impedance.
    Smaller means closer, so the polarity search in evaluate() will pick 'low = in zone'."""
    out = []
    for x in X:
        _, vpost, _, ipost = _phasors(x)
        zg, zp = _zapp(vpost, ipost, "ag"), _zapp(vpost, ipost, "ab")
        out.append(min(zg.imag, zp.imag))
    return np.array(out)


def score_negseq(X):
    return np.array([abs(sequence_phasors(x[3:], EVENT + CYCLE)[2]) for x in X])


def zone_features(X):
    feats = []
    for x in X:
        vpre, vpost, ipre, ipost = _phasors(x)
        zg, zp = _zapp(vpost, ipost, "ag"), _zapp(vpost, ipost, "ab")
        v0, v1, v2 = vpost; i0, i1, i2 = ipost
        dv0, dv1, dv2 = vpost - vpre; di0, di1, di2 = ipost - ipre
        e = 1e-9
        feats.append([
            zg.real, zg.imag, abs(zg), np.angle(zg),
            zp.real, zp.imag, abs(zp), np.angle(zp),
            abs(v1), abs(v2), abs(v0), abs(i1), abs(i2), abs(i0),
            abs(dv1), abs(dv2), abs(dv0), abs(di1), abs(di2), abs(di0),
            abs(i2) / (abs(i1) + e), abs(i0) / (abs(i1) + e), abs(i0) / (abs(i2) + e),
            np.angle(i2 / (i1 + e)), np.angle(i0 / (i1 + e)), np.angle(v2 / (i2 + e)),
            np.angle(v0 / (i0 + e)), np.angle(dv2 / (di2 + e)), np.angle(dv1 / (di1 + e)),
            abs(dv1 / (di1 + e)), abs(dv2 / (di2 + e)), abs(dv0 / (di0 + e)),
        ])
    return np.nan_to_num(np.array(feats), nan=0.0, posinf=0.0, neginf=0.0)


def score_engineered(Xtr, ytr, Xte, seed=0):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=4000, random_state=seed))
    ftr, fte = zone_features(Xtr), zone_features(Xte)
    clf.fit(ftr, ytr)
    return clf.decision_function(ftr), clf.decision_function(fte)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--rf", type=float, default=0.3, help="max fault resistance, pu")
    ap.add_argument("--wide", action="store_true", help="sample the whole line, not just the boundary band")
    args = ap.parse_args()

    with open(os.path.join(OUT, "aux_signal_toy_weak_sg.json")) as f:
        o = json.load(f)["cvxpy_opt"]
    design_delta = complex(o[0], o[1])
    direction = design_delta / abs(design_delta)

    mags = [0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.514]
    n_tr, n_te = 900, 450
    if args.quick:
        mags = [0.0, 0.10, 0.30, 0.514]
        n_tr, n_te = 350, 250
        args.epochs = 12


    grid = _replace(ZoneParams(), rF=args.rf)
    p = SigParams()
    rows = []
    band = "whole line" if args.wide else "boundary band only (in 0.62-0.85, out 0.02-0.18)"
    print(f"in-zone (m <= {grid.reach}) vs out-of-zone (adjacent line), {band}")
    print(f"fault resistance 0 to {grid.rF} pu in both  (line |z1| = {abs(grid.z1):.3f} pu)")
    print(f"delta swept along the designed direction ({np.degrees(np.angle(design_delta)):.1f} deg)")
    print(f"train {2*n_tr}+{2*n_tr}, test {2*n_te}+{2*n_te}, FAR budget {FAR:.0%}\n")
    for t in mags:
        d = t * direction
        t0 = time.time()
        Xtr, ytr, _ = make_zone_dataset(n_tr, np.random.default_rng(100), d, p, grid, not args.wide)
        Xte, yte, kte = make_zone_dataset(n_te, np.random.default_rng(999), d, p, grid, not args.wide)
        row = dict(delta=t)
        row["reactance"] = evaluate(score_reactance(Xtr), ytr, score_reactance(Xte), yte)
        row["negseq"] = evaluate(score_negseq(Xtr), ytr, score_negseq(Xte), yte)
        e_tr, e_te = score_engineered(Xtr, ytr, Xte)
        row["engineered"] = evaluate(e_tr, ytr, e_te, yte)
        s_tr, s_te = train_cnn(Xtr, ytr, Xte, epochs=args.epochs)
        row["cnn"] = evaluate(s_tr, ytr, s_te, yte)
        rows.append(row)
        print(f"  |delta|={t:.3f}   reactance {row['reactance']['detection_rate']*100:5.1f}%   "
              f"|i-| {row['negseq']['detection_rate']*100:5.1f}%   "
              f"engineered {row['engineered']['detection_rate']*100:5.1f}%   "
              f"CNN {row['cnn']['detection_rate']*100:5.1f}%   [{time.time()-t0:.0f}s]")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for key, lab, mk, c in (("reactance", "apparent reactance (textbook element)", "o", "tab:gray"),
                            ("negseq", "|i⁻| magnitude", "s", "tab:blue"),
                            ("engineered", "engineered features + LR", "D", "tab:green"),
                            ("cnn", "learned (1D CNN, raw waveform)", "^", "tab:red")):
        ax.plot(mags, [r[key]["detection_rate"] * 100 for r in rows], marker=mk, color=c, label=lab)
    ax.axvline(abs(design_delta), ls=":", lw=1.2, color="tab:green")
    ax.text(abs(design_delta), 20, "  design tool's\n  certified δ", fontsize=8, color="tab:green")
    ax.set_xlabel("auxiliary signal magnitude δ  (pu negative-sequence current)")
    ax.set_ylabel(f"in-zone faults correctly tripped at {FAR:.0%} false trip (%)")
    ax.set_title("In-zone vs out-of-zone with fault resistance and remote infeed")
    ax.grid(alpha=.3); ax.legend(fontsize=8, loc="lower right"); ax.set_ylim(-3, 103)
    plt.tight_layout()
    png = os.path.join(OUT, "zone_sweep.png")
    plt.savefig(png, dpi=140)
    json.dump(dict(far=FAR, magnitudes=mags, n_train=n_tr, n_test=n_te,
                   design_delta=[design_delta.real, design_delta.imag, abs(design_delta)],
                   rows=rows), open(os.path.join(OUT, "zone_sweep.json"), "w"), indent=2)
    print("saved", os.path.relpath(png))


if __name__ == "__main__":
    main()
