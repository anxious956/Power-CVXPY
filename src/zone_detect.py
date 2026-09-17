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
from zone_model import ZoneParams, solve_zone, loop_impedances, supervised_reactance, phase_selected_reactance
from waveforms import _synth, SigParams, sequence_phasors, CYCLE, EVENT
from detect import evaluate, train_cnn, fit_lr_scores, FAR

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
os.makedirs(OUT, exist_ok=True)


def generate(kind, rng, delta=0.0, p=None, grid=None, boundary=True, delta_pre=None, m_range=None):
    """kind: 'ag'/'ab' (in zone) or 'ag2'/'ab2' (out of zone). Returns (x, meta).

    boundary=True concentrates the sampling in the band where the two classes are genuinely
    ambiguous: just inside the reach versus just past the remote bus. Sampling the whole
    line instead fills the set with easy cases and flatters every detector.

    Review options (defaults reproduce the original):
      delta_pre  auxiliary signal in the PRE-event solve; None = same as delta (continuous
                 injection). delta_pre=0 switches the signal on at the event (H4).
      m_range    (lo, hi) overrides the fault-position band, e.g. (0.85, 1.0) for own-line faults
                 past the reach (H9). The rng draw order is unchanged.
    The returned meta also carries the noise-free sequence phasors 'pre' and 'post' (H20).
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
    if m_range is not None:            # map the draw linearly onto the new band (same rng order)
        lo, hi = ((0.02, 0.18) if boundary else (0.02, 0.9)) if kind.endswith("2") else                  ((0.62, g.reach) if boundary else (0.05, g.reach))
        m = m_range[0] + (m - lo) / (hi - lo) * (m_range[1] - m_range[0])
    mr = rng.uniform(0.0, 1.0)
    pre = solve_zone(g, "N", srcL, iR, delta if delta_pre is None else delta_pre)
    post = solve_zone(g, kind, srcL, iR, delta, m, mr)
    v = _synth(pre[:3], post[:3], p, rng, is_current=False)
    i = _synth(pre[3:], post[3:], p, rng, is_current=True)
    return np.vstack([v, i]).astype(np.float32), dict(kind=kind, m=m, rf=mr * g.rF, pre=pre,
                                                        post=post, grid=g)


def make_zone_dataset(n, rng, delta=0.0, p=None, grid=None, boundary=True, delta_pre=None,
                      kinds_pos=("ag", "ab"), kinds_neg=("ag2", "ab2"), m_range=None,
                      return_meta=False):
    X, y, kinds, metas = [], [], [], []
    for label, ks in ((1, kinds_pos), (0, kinds_neg)):
        for k in ks:
            for _ in range(n):
                x, mt = generate(k, rng, delta, p, grid, boundary, delta_pre, m_range)
                X.append(x); y.append(label); kinds.append(k); metas.append(mt)
    if return_meta:
        return np.stack(X), np.array(y), np.array(kinds), metas
    return np.stack(X), np.array(y), np.array(kinds)


# ------------------------------------------------------------------------- detectors
def mimic_filter(x3, tau_samples):
    """Digital mimic (DC-removal) filter y[n] = (1+tau) x[n] - tau x[n-1], tau in samples.
    Returns the filtered block and its complex gain at the fundamental, by which a phasor of the
    filtered signal must be divided to recover the unfiltered phasor (magnitude AND angle)."""
    y = np.empty_like(x3, dtype=float)
    y[:, 1:] = (1 + tau_samples) * x3[:, 1:] - tau_samples * x3[:, :-1]
    y[:, 0] = x3[:, 0]
    H = (1 + tau_samples) - tau_samples * np.exp(-2j * np.pi / CYCLE)
    return y, H


def line_tau_samples(g):
    """DC time constant of a fault through the protected line, X/(omega R), in samples."""
    return (g.z1.imag / g.z1.real) * CYCLE / (2 * np.pi)


def _phasors(x, offset=0, mimic_tau=None):
    """Pre-event window 2 cycles before the event, post-event window one cycle after it.
    offset (samples) shifts both anchors, modelling a trigger-time error (H20); mimic_tau
    (samples) applies a mimic filter to the currents (H20). Defaults reproduce the original."""
    a_pre, a_post = EVENT - 2 * CYCLE + offset, EVENT + CYCLE + offset
    xi, H = (x[3:], 1.0) if mimic_tau is None else mimic_filter(x[3:], mimic_tau)
    vpre = sequence_phasors(x[:3], a_pre); vpost = sequence_phasors(x[:3], a_post)
    ipre = sequence_phasors(xi, a_pre) / H; ipost = sequence_phasors(xi, a_post) / H
    return vpre, vpost, ipre, ipost


def _loops(vpost, ipost, g):
    y = np.array([vpost[1], vpost[2], vpost[0], ipost[1], ipost[2], ipost[0]])
    return loop_impedances(y, g.z1, g.z0_ratio * g.z1)


def _seq_vec(vpost, ipost):
    return np.array([vpost[1], vpost[2], vpost[0], ipost[1], ipost[2], ipost[0]])


def score_reactance(X, g, offsets=None, mimic_tau=None):
    """The textbook distance element, implemented the way a relay does it: six fault loops,
    k0 compensation on the ground loops, faulted-phase selection from incremental currents so
    that only the faulted loops are released, forward loops only, smallest reactance wins.
    Thresholding this score is exactly setting a zone reach.

    An earlier version released every loop that passed a crude 50 % current supervision. On
    real EMT data that let healthy phase-to-phase loops win and gave 40 % zone-1 trips for
    faults at 99 % of the line; see zone_model.phase_selected_reactance."""
    z1, z0 = g.z1, g.z0_ratio * g.z1
    out = []
    for j, x in enumerate(X):
        off = 0 if offsets is None else int(offsets[j])
        _, vpost, ipre, ipost = _phasors(x, off, mimic_tau)
        out.append(phase_selected_reactance(vpost, ipre, ipost, z1, z0))
    return np.array(out)


def score_negseq(X):
    return np.array([abs(sequence_phasors(x[3:], EVENT + CYCLE)[2]) for x in X])


FLOOR = 1e-3        # pu; about the phasor noise floor, used by the fixed ratio features (H21)


def _ang(a, b):
    """Angle of a/b without dividing (no epsilon, no blow-up when b ~ 0)."""
    return np.angle(a * np.conj(b))


def _logratio(a, b, floor=FLOOR):
    return np.log((abs(a) + floor) / (abs(b) + floor))


def zone_features(X, g, fixed=False, raw=False, mimic_tau=None):
    """fixed=False: the original 36 features (raw angles in [-pi, pi], ratios with e=1e-9, then
    nan_to_num(posinf=0)). fixed=True (review H21): every angle enters as (sin, cos), every
    ratio as log((|a|+floor)/(|b|+floor)); the linear features are unchanged.
    raw=True returns the original matrix before nan_to_num (for counting defects)."""
    feats = []
    for x in X:
        vpre, vpost, ipre, ipost = _phasors(x, 0, mimic_tau)
        L = _loops(vpost, ipost, g)
        fwd = [z.imag for z in L.values() if z.imag > 0]
        sup = phase_selected_reactance(vpost, ipre, ipost, g.z1, g.z0_ratio * g.z1)
        zg, zp = L["ag"], L["ab"]
        v0, v1, v2 = vpost; i0, i1, i2 = ipost
        dv0, dv1, dv2 = vpost - vpre; di0, di1, di2 = ipost - ipre
        e = 1e-9
        lin = [zg.real, zg.imag, abs(zg), zp.real, zp.imag, abs(zp),
               sup, min(fwd) if fwd else 10.0, len(fwd),
               min((z.imag for z in L.values()), default=0.0),
               abs(v1), abs(v2), abs(v0), abs(i1), abs(i2), abs(i0),
               abs(dv1), abs(dv2), abs(dv0), abs(di1), abs(di2), abs(di0)]
        if not fixed:
            feats.append([
                zg.real, zg.imag, abs(zg), np.angle(zg),
                zp.real, zp.imag, abs(zp), np.angle(zp),
                sup, min(fwd) if fwd else 10.0, len(fwd),
                min((z.imag for z in L.values()), default=0.0),
                abs(v1), abs(v2), abs(v0), abs(i1), abs(i2), abs(i0),
                abs(dv1), abs(dv2), abs(dv0), abs(di1), abs(di2), abs(di0),
                abs(i2) / (abs(i1) + e), abs(i0) / (abs(i1) + e), abs(i0) / (abs(i2) + e),
                np.angle(i2 / (i1 + e)), np.angle(i0 / (i1 + e)), np.angle(v2 / (i2 + e)),
                np.angle(v0 / (i0 + e)), np.angle(dv2 / (di2 + e)), np.angle(dv1 / (di1 + e)),
                abs(dv1 / (di1 + e)), abs(dv2 / (di2 + e)), abs(dv0 / (di0 + e)),
            ])
        else:
            angs = [np.angle(zg), np.angle(zp), _ang(i2, i1), _ang(i0, i1), _ang(v2, i2),
                    _ang(v0, i0), _ang(dv2, di2), _ang(dv1, di1)]
            rats = [_logratio(i2, i1), _logratio(i0, i1), _logratio(i0, i2),
                    _logratio(dv1, di1), _logratio(dv2, di2), _logratio(dv0, di0)]
            feats.append(lin + [np.sin(a) for a in angs] + [np.cos(a) for a in angs] + rats)
    F = np.array(feats)
    if raw:
        return F
    return np.nan_to_num(F, nan=0.0, posinf=0.0, neginf=0.0)


# column indices of the original zone_features, for the H21 defect count
ZONE_ANGLE_COLS = [3, 7, 27, 28, 29, 30, 31, 32]
ZONE_RATIO_COLS = [24, 25, 26, 33, 34, 35]


def score_engineered(Xtr, ytr, Xte, g, seed=0, oof_folds=5, fixed_features=True, mimic_tau=None):
    """oof_folds=0 reproduces the original in-sample training scores (review H18);
    fixed_features=False the original feature encoding (review H21)."""
    return fit_lr_scores(zone_features(Xtr, g, fixed_features, mimic_tau=mimic_tau), ytr,
                         zone_features(Xte, g, fixed_features, mimic_tau=mimic_tau), seed=seed,
                         max_iter=4000, oof_folds=oof_folds)


KEYS = ("reactance", "negseq", "engineered", "cnn")


def score_all(Xtr, ytr, Xte, grid, seed=0, epochs=20, cfg=None):
    """All four detectors on one train/test split -> {name: (train_scores, test_scores)}.
    cfg holds the review switches; an empty cfg is the original pipeline."""
    cfg = dict(cfg or {})
    out = {}
    mt = line_tau_samples(grid) if cfg.get("mimic", False) else None
    out["reactance"] = (score_reactance(Xtr, grid, mimic_tau=mt), score_reactance(Xte, grid, mimic_tau=mt))
    out["negseq"] = (score_negseq(Xtr), score_negseq(Xte))
    oof = cfg.get("oof_folds", 0)
    out["engineered"] = score_engineered(Xtr, ytr, Xte, grid, seed=seed, oof_folds=oof,
                                         fixed_features=cfg.get("fixed_features", False),
                                         mimic_tau=mt)
    out["cnn"] = train_cnn(Xtr, ytr, Xte, epochs=epochs, seed=seed, oof_folds=oof,
                           oof_test=cfg.get("oof_test", "full"),
                           norm=cfg.get("cnn_norm", "per_waveform"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--rf", type=float, default=0.3, help="max fault resistance, pu")
    ap.add_argument("--wide", action="store_true", help="sample the whole line, not just the boundary band")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--out", default=OUT, help="output directory (review: keep author results intact)")
    ap.add_argument("--tag", default="zone_sweep", help="basename of the .json/.png/.npz outputs")
    ap.add_argument("--polarity", choices=("train", "test"), default="train",
                    help="'test' reproduces the original test-chosen sign (review H17)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    dump = {}                                   # raw test scores per (delta, seed, detector)

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
    cfg = {}
    for t in mags:
        d = t * direction
        t0 = time.time()
        per_seed = {k: [] for k in KEYS}
        for sd in range(args.seeds):
            Xtr, ytr, _ = make_zone_dataset(n_tr, np.random.default_rng(100 + 17 * sd), d, p,
                                            grid, not args.wide)
            Xte, yte, _k = make_zone_dataset(n_te, np.random.default_rng(999 + 31 * sd), d, p,
                                             grid, not args.wide)
            sc = score_all(Xtr, ytr, Xte, grid, seed=sd, epochs=args.epochs, cfg=cfg)
            for k in KEYS:
                per_seed[k].append(evaluate(sc[k][0], ytr, sc[k][1], yte, polarity=args.polarity))
            dump[f"y_{t}_{sd}"] = yte; dump[f"kind_{t}_{sd}"] = _k
            for k in KEYS:
                dump[f"{k}_{t}_{sd}"] = sc[k][1]
        row = dict(delta=t)
        for k in KEYS:
            g_ = lambda f: np.array([r[f] for r in per_seed[k]])
            dr, au, d5 = g_("detection_rate"), g_("auc"), g_("detection_at_5pct")
            row[k] = dict(detection_rate=float(dr.mean()), detection_std=float(dr.std()),
                          auc=float(au.mean()), auc_std=float(au.std()),
                          detection_at_5pct=float(d5.mean()),
                          false_alarm=float(g_("false_alarm").mean()),
                          seeds=[float(x) for x in dr], per_seed=per_seed[k])
        rows.append(row)
        f = lambda k: f"{row[k]['auc']:.3f}+-{row[k]['auc_std']:.3f}"
        d = lambda k: f"{row[k]['detection_rate']*100:.0f}"
        print(f"  |delta|={t:.3f}  AUC  reactance {f('reactance')}  |i-| {f('negseq')}  "
              f"engineered {f('engineered')}  CNN {f('cnn')}   "
              f"| dep@1%FAR {d('reactance')}/{d('negseq')}/{d('engineered')}/{d('cnn')}  "
              f"[{time.time()-t0:.0f}s]")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for key, lab, mk, c in (("reactance", "apparent reactance (textbook element)", "o", "tab:gray"),
                            ("negseq", "|i⁻| magnitude", "s", "tab:blue"),
                            ("engineered", "engineered features + LR", "D", "tab:green"),
                            ("cnn", "learned (1D CNN, raw waveform)", "^", "tab:red")):
        mu = np.array([r[key]["auc"] for r in rows])
        sd = np.array([r[key]["auc_std"] for r in rows])
        ax.errorbar(mags, mu, yerr=sd, marker=mk, color=c, label=lab, capsize=3, lw=1.6)
    ax.axvline(abs(design_delta), ls=":", lw=1.2, color="tab:green")
    ax.text(abs(design_delta), 0.62, " design tool's\n certified δ", fontsize=8, color="tab:green")
    ax.axhline(0.5, ls="--", lw=.8, color="k")
    ax.text(mags[0], 0.508, "chance", fontsize=8)
    ax.set_xlabel("auxiliary signal magnitude δ  (pu negative-sequence current)")
    ax.set_ylabel("ROC AUC, in-zone vs out-of-zone")
    ax.set_title("Does the auxiliary signal help?\n"
                 "In-zone vs out-of-zone, fault resistance and inverter infeed, mean ± sd over seeds")
    ax.grid(alpha=.3); ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(0.02, 0.48)); ax.set_ylim(0.45, 1.03)
    plt.tight_layout()
    png = os.path.join(args.out, args.tag + ".png")
    plt.savefig(png, dpi=140)
    json.dump(dict(far=FAR, magnitudes=mags, n_train=n_tr, n_test=n_te,
                   design_delta=[design_delta.real, design_delta.imag, abs(design_delta)],
                   rows=rows, args=vars(args)),
              open(os.path.join(args.out, args.tag + ".json"), "w"), indent=2)
    np.savez_compressed(os.path.join(args.out, args.tag + "_scores.npz"), **dump)
    print("saved", os.path.relpath(png))


if __name__ == "__main__":
    main()
