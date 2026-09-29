"""Hasan, Chakraborty & Wang (2026) hierarchical linear-SVM relay, re-implemented on adapt_grid.

Reference: A.S. Hasan, S. Chakraborty, J. Wang, "End-To-End Decentralized Transmission Line Protection in
IBR-Dominated Weak Grids Using Interpretable Data-Driven Methods", Int. J. Electr. Power Energy Syst. 181
(2026) 112007 (OSTI 3577322). Their data are confidential, so the only fair comparison is their method on
our data, under our protocol. This file is the protocol; it was committed before any result was produced.

WHAT IS TAKEN AS PUBLISHED (their section 4-5)
  features   per time step: RMS voltage, |V_a,b,c|, |I_a,b,c|, angle V_a,b,c, angle I_a,b,c, |V+|, |I+|
             (their Table 3, "common"); plus |V-|, |I-| and |V0|, |I0| where their Table 4 adds them
  buffer     the per-step features are averaged over a 3-cycle moving buffer; the mean is the input
  stages     1: no fault / reverse / forward (common features)
             2: fault type, 10 phase-specific types mapped to LG / LL / LLG / 3P (common + neg + zero)
             3: zone, one classifier per fault class, features per their Table 4, expanded with
                3rd-degree polynomial terms, scaled, a first LinearSVC ranks the terms by |coefficient|,
                the top k = 100 are kept (their Table 5 value for every zone classifier) and the final
                LinearSVC is retrained on them
             (4: length estimation is advisory in their scheme and takes no part in the trip; omitted)
  trip       stage 1 says forward AND the stage-3 classifier of the stage-2 class says zone 1
  model      sklearn LinearSVC, StandardScaler; class_weight='balanced' (they tune "misclassification
             penalties and imbalanced data" without giving values)

WHAT HAD TO BE ADAPTED, AND WHY
  angles     their angles are raw. adapt_grid randomises the external-grid initial angle over +-180 deg and
             the inception time, so a raw angle is noise here (and meaningless in a real relay). Every angle
             is referenced to the angle of the pre-fault positive-sequence voltage memory (3 cycles ending
             20 ms before inception, as the CNN input), in degrees wrapped to (-180, 180], and averaged
             as values, as they average them. Variant 'sincos' averages cos and sin instead.
  units      theirs are absolute (kV, kA). Loading varies 2.8x here, so variant 'pu' divides voltages by
             nominal and scales currents by Z_reach / V_nom (the CNN's scaling).
  stage 1    their line is radial (one line behind, one ahead). This grid is meshed: forward = own line,
             lines beyond, remote bus, parallel line; reverse = relay bus and lines behind; faults
             elsewhere ('other') have no defined direction and are left out of stage-1 training (they are
             tested like every off-line fault). The 'no fault' class is the pre-fault window of the same
             training simulations (buffer ending 20 ms before inception), so a simulation's pre-fault and
             fault windows are always in the same fold. Switching and incipient events are never trained on.
  stage 3    their zone 1 is 0-80 % and zone 2 80-120 % (next line's first 20 %). Ours: zone 1 = own line
             <= 85 %; zone 2 = every forward off-line fault (remote bus, all of every line beyond, parallel
             line). The 85-100 % guard band is out of training, as for every detector here.
  time       decision at 20 ms (ours; the 3-cycle buffer then holds two pre-fault cycles) and at 50 ms
             (2.5 cycles, theirs). 2.5 cycles is slow for a transmission zone 1; both are reported.
  C          not published. Variant 'default': C = 1. Variant 'tunedC': C per stage from {0.01, 0.1, 1, 10}
             by grouped 3-fold macro-F1 (their selection metric) on the outer training set only, reused for
             that fold's inner calibration fits.
  phasors    plain full-cycle DFT per step (no mimic filter), at every 8th sample (1/16 cycle); their
             features are per simulation step.

PROTOCOL (identical to adaptgrid_run for everything else)
  data       adapt_grid-TestGrid110kV, relays adapt_A / adapt_B, relay front end (AA 400 Hz + CT full scale)
  splits     grouped (5-fold x 2 over 20 loading bins) and loqo (leave one loading quartile out), from
             zone_cv.splits, i.e. the exact folds of every other detector
  readouts   native: their own rule (forward and zone-1 decision value > 0), no threshold of ours
             cal0: threshold = largest out-of-fold gated score among the training negatives (inner
                   StratifiedGroupKFold(5) over loading bins, as oof_negatives); test rows scored by the
                   hierarchy fitted on all of the outer training rows (the sklearn convention here)
             roc0 / roc1: pooled out-of-fold test scores at 0 / 1 off-line false trips (upper bounds)
             every readout also with 32P/32Q supervision
  gated score  zone-1 decision value of the stage-3 classifier chosen by stage 2, if stage 1 says forward;
             GATE (-1e9) otherwise
  held rows  switching, incipient and guard-band rows are scored by every outer-fold model; a row trips
             when at least half do (as adaptgrid_run)
  also       stage accuracies on the test rows (end-to-end routing, predicted class), LinearSVC convergence
             warnings, selected-term overlap across folds, threshold provenance, a pre-fault shortcut test
             (AUC of a scaled LinearSVC on the 3-cycle buffer ending at inception, grouped 5-fold), and the
             installation-mismatch chain (train draw 1, test draw 2) for the 'default' variant

    python src/review/hasan_svm.py [--relays adapt_A adapt_B] [--times 20 50] [--variants default pu sincos tunedC]
                                   [--splits grouped loqo] [--smoke]
    -> results/adaptgrid/hasan_svm_relayfe.json (…_smoke.json with --smoke: one fold per split, one variant)
"""
import os, sys, json, time, argparse, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.svm import LinearSVC
from sklearn.exceptions import ConvergenceWarning
from review import common as cm
from review import frontend
from review import q1_instrument as q1
from review.zone_cv import zone_task, splits
from review.adaptgrid_run import bundle, supervision, rates_plus, pooled_threshold, FAR

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")
SPC, FS = cm.SPC, cm.FS
BUFFER = 3 * SPC                   # their 3-cycle feature buffer
STRIDE = 8                         # per-step features every 8th sample
MEMORY = (-SPC, 3 * SPC)           # pre-fault V+ memory: 3 cycles ending 20 ms before inception
PREFAULT_END = -SPC                # 'no fault' window: buffer ending 20 ms before inception
K_TOP = 100                        # their Table 5
C_GRID = (0.01, 0.1, 1.0, 10.0)
GATE = -1e9
CLASSES = ("LG", "LL", "LLG", "3P")
VARIANTS = {
    "default": dict(angle="deg", units="abs", tune_c=False),
    "pu": dict(angle="deg", units="pu", tune_c=False),
    "sincos": dict(angle="sincos", units="abs", tune_c=False),
    "tunedC": dict(angle="deg", units="abs", tune_c=True),
}
STAGE3_BLOCKS = {"LG": ("common", "neg", "zero"), "LL": ("common", "neg"),
                 "LLG": ("common", "neg", "zero"), "3P": ("common",)}


# ------------------------------------------------------------------ features
def _phasors(x, end, n=SPC):
    """Full-cycle DFT over [end-n, end) of (m, ch, T) -> (m, ch), absolute sample reference."""
    seg = x[..., end - n:end].astype(np.float64)
    k = np.arange(end - n, end)
    return (2.0 / n) * (seg @ np.exp(-2j * np.pi * k / SPC))


def memory_reference(X, ev):
    """Unit phasor of the pre-fault positive-sequence voltage memory."""
    end, n = ev + MEMORY[0], MEMORY[1]
    v1 = (_phasors(X[:, :3], end, n) @ cm.BM.T)[:, 1]
    return v1 / np.abs(v1)


def buffer_features(X, end, ref, angle="deg", units="abs", z_reach=1.0):
    """Hasan's per-step features averaged over the 3-cycle buffer ending at sample `end`.
    Returns dict of blocks: common (m, 15 or 21), neg (m, 2), zero (m, 2), and names."""
    sv = 1.0 / cm.V_NOM_PEAK if units == "pu" else 1.0
    si = z_reach / cm.V_NOM_PEAK if units == "pu" else 1.0
    acc = None
    steps = np.arange(end - BUFFER + STRIDE, end + 1, STRIDE)
    for e in steps:
        V = _phasors(X[:, :3], e); I = _phasors(X[:, 3:], e)
        sV, sI = V @ cm.BM.T, I @ cm.BM.T                                   # [0, +, -]
        vrms = np.sqrt(np.mean(X[:, :3, e - SPC:e].astype(np.float64) ** 2, axis=-1)).mean(axis=1)
        aV = np.angle(V / ref[:, None]); aI = np.angle(I / ref[:, None])
        if angle == "deg":
            ang = np.degrees(np.concatenate([aV, aI], axis=1))
        else:
            ang = np.concatenate([np.cos(aV), np.cos(aI), np.sin(aV), np.sin(aI)], axis=1)
        common = np.concatenate([vrms[:, None] * sv, np.abs(V) * sv, np.abs(I) * si, ang,
                                 np.abs(sV[:, 1:2]) * sv, np.abs(sI[:, 1:2]) * si], axis=1)
        neg = np.concatenate([np.abs(sV[:, 2:3]) * sv, np.abs(sI[:, 2:3]) * si], axis=1)
        zero = np.concatenate([np.abs(sV[:, 0:1]) * sv, np.abs(sI[:, 0:1]) * si], axis=1)
        blk = (common, neg, zero)
        acc = [b.copy() for b in blk] if acc is None else [a + b for a, b in zip(acc, blk)]
    common, neg, zero = [a / len(steps) for a in acc]
    an = (["angVa", "angVb", "angVc", "angIa", "angIb", "angIc"] if angle == "deg" else
          ["cosVa", "cosVb", "cosVc", "cosIa", "cosIb", "cosIc", "sinVa", "sinVb", "sinVc", "sinIa", "sinIb", "sinIc"])
    names = dict(common=["Vrms", "|Va|", "|Vb|", "|Vc|", "|Ia|", "|Ib|", "|Ic|"] + an + ["|V+|", "|I+|"],
                 neg=["|V-|", "|I-|"], zero=["|V0|", "|I0|"])
    return dict(common=common, neg=neg, zero=zero, names=names)


def features_at(R, rows, t_ms, variant, chunk=2000):
    """Buffer features for `rows` with the buffer ending t_ms after inception (t_ms may be negative)."""
    v = VARIANTS[variant]
    end = R["ev"] + int(round(t_ms * FS / 1000.0))
    out = None
    for a in range(0, len(rows), chunk):
        r = rows[a:a + chunk]
        X = np.asarray(R["full"][r])
        f = buffer_features(X, end, memory_reference(X, R["ev"]), v["angle"], v["units"], R["z_reach"])
        if out is None:
            out = {k: [f[k]] for k in ("common", "neg", "zero")}; names = f["names"]
        else:
            for k in out:
                out[k].append(f[k])
    res = {k: np.concatenate(vv) for k, vv in out.items()}
    res["names"] = names
    return res


def stack(F, blocks, rows=None):
    M = np.concatenate([F[b] for b in blocks], axis=1)
    return M if rows is None else M[rows]


# ------------------------------------------------------------------ labels
def fault_class(et):
    """Event type -> LG / LL / LLG / 3P ('' for non-short-circuit events)."""
    et = np.asarray(et).astype(str)
    out = np.full(len(et), "", dtype=object)
    out[np.char.find(et, "1phg") >= 0] = "LG"
    out[np.char.find(et, "2phg") >= 0] = "LLG"
    out[(np.char.find(et, "2ph") >= 0) & (np.char.find(et, "2phg") < 0)] = "LL"
    out[np.char.find(et, "3ph") >= 0] = "3P"
    return out.astype(str)


def direction_label(R):
    """2 forward, 1 reverse, -1 undefined (faults elsewhere, non-faults)."""
    fwd = R["pos"] | R["own99"] | R["beyond"] | R["remote_bus_faults"] | R["parallel"]
    rev = R["reverse_bus"] | R["reverse_lines"]
    d = np.full(len(R["et"]), -1)
    d[fwd] = 2; d[rev] = 1
    return d


# ------------------------------------------------------------------ models
def _svc(C, seed):
    return LinearSVC(C=C, class_weight="balanced", dual="auto", max_iter=20000, random_state=seed)


class Stage:
    """StandardScaler + LinearSVC, optionally 3rd-degree polynomial expansion and top-k term selection.
    Fitted only on what it is given."""

    def __init__(self, C=1.0, poly=False, k=K_TOP, seed=0):
        self.C, self.poly, self.k, self.seed = C, poly, k, seed
        self.const, self.sel, self.warn = None, None, 0

    def _fit_svc(self, Z, y):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", ConvergenceWarning)
            m = _svc(self.C, self.seed).fit(Z, y)
        self.warn += sum(issubclass(x.category, ConvergenceWarning) for x in w)
        return m

    def fit(self, X, y):
        cls = np.unique(y)
        if len(cls) < 2:                                   # a class absent from this training fold
            self.const = cls[0] if len(cls) else 0
            return self
        Z = X
        if self.poly:
            self.pf = PolynomialFeatures(3, include_bias=False).fit(X)
            Z = self.pf.transform(X)
            sc0 = StandardScaler().fit(Z)
            first = self._fit_svc(sc0.transform(Z), y)
            w = np.abs(first.coef_).max(axis=0)
            self.sel = np.sort(np.argsort(-w)[:min(self.k, Z.shape[1])])
            Z = Z[:, self.sel]
        self.sc = StandardScaler().fit(Z)
        self.m = self._fit_svc(self.sc.transform(Z), y)
        return self

    def _z(self, X):
        Z = self.pf.transform(X) if self.poly else X
        if self.sel is not None:
            Z = Z[:, self.sel]
        return self.sc.transform(Z)

    def predict(self, X):
        if self.const is not None:
            return np.full(len(X), self.const)
        return self.m.predict(self._z(X))

    def decision(self, X):
        """Binary decision value, positive = class 1 (zone 1)."""
        if self.const is not None:
            return np.full(len(X), 1.0 if self.const == 1 else -1.0)
        return self.m.decision_function(self._z(X))


def tune_C(X, y, groups, seed, poly=False):
    """C from C_GRID by grouped 3-fold macro-F1 on the data given (outer training rows only)."""
    if len(np.unique(y)) < 2 or len(np.unique(groups)) < 3:
        return 1.0
    best, bestC = -1, 1.0
    for C in C_GRID:
        pred = np.empty(len(y), dtype=y.dtype)
        for a, b in StratifiedGroupKFold(3, shuffle=True, random_state=seed).split(X, y, groups):
            pred[b] = Stage(C, poly, seed=seed).fit(X[a], y[a]).predict(X[b])
        f = f1_score(y, pred, average="macro")
        if f > best:
            best, bestC = f, C
    return bestC


class Hierarchy:
    """Stages 1-3 fitted on the given training simulations only."""

    def __init__(self, Cs=None, seed=0):
        self.Cs = Cs or {"s1": 1.0, "s2": 1.0, **{f"s3_{c}": 1.0 for c in CLASSES}}
        self.seed = seed

    def fit(self, Ff, Fp, rows, D, cls, fine, pos):
        """Ff, Fp: fault-time and pre-fault features (dicts, indexed by record); rows: training records;
        D direction label, cls fault class, fine phase-specific type, pos zone-1 label (all by record)."""
        s1_rows = rows[D[rows] >= 1]
        X1 = np.concatenate([stack(Fp, ("common",), rows), stack(Ff, ("common",), s1_rows)])
        y1 = np.concatenate([np.zeros(len(rows), int), D[s1_rows]])
        self.s1 = Stage(self.Cs["s1"], seed=self.seed).fit(X1, y1)
        s2_rows = rows[cls[rows] != ""]
        self.s2 = Stage(self.Cs["s2"], seed=self.seed).fit(stack(Ff, ("common", "neg", "zero"), s2_rows), fine[s2_rows])
        self.s3 = {}
        for c in CLASSES:
            r3 = rows[(D[rows] == 2) & (cls[rows] == c)]
            self.s3[c] = Stage(self.Cs[f"s3_{c}"], poly=True, seed=self.seed).fit(
                stack(Ff, STAGE3_BLOCKS[c], r3), pos[r3].astype(int))
        return self

    def score(self, F, rows):
        """Gated zone-1 score, stage-1 direction, stage-2 class, per record in rows."""
        d = self.s1.predict(stack(F, ("common",), rows))
        c = np.array([str(x).split("_")[0] for x in self.s2.predict(stack(F, ("common", "neg", "zero"), rows))])
        s = np.full(len(rows), GATE)
        for k in CLASSES:
            m = c == k
            if m.any():
                s[m] = self.s3[k].decision(stack(F, STAGE3_BLOCKS[k], rows[m]))
        g = np.where(d == 2, s, GATE)
        return g, d, c

    def warnings(self):
        return int(self.s1.warn + self.s2.warn + sum(s.warn for s in self.s3.values()))

    def selected(self):
        return {c: (None if self.s3[c].sel is None else self.s3[c].sel.tolist()) for c in CLASSES}


def tuned_Cs(Ff, Fp, rows, D, cls, fine, pos, groups_of, seed):
    s1_rows = rows[D[rows] >= 1]
    X1 = np.concatenate([stack(Fp, ("common",), rows), stack(Ff, ("common",), s1_rows)])
    y1 = np.concatenate([np.zeros(len(rows), int), D[s1_rows]])
    g1 = np.concatenate([groups_of[rows], groups_of[s1_rows]])
    Cs = {"s1": tune_C(X1, y1, g1, seed)}
    s2_rows = rows[cls[rows] != ""]
    Cs["s2"] = tune_C(stack(Ff, ("common", "neg", "zero"), s2_rows), fine[s2_rows], groups_of[s2_rows], seed)
    for c in CLASSES:
        r3 = rows[(D[rows] == 2) & (cls[rows] == c)]
        Cs[f"s3_{c}"] = tune_C(stack(Ff, STAGE3_BLOCKS[c], r3), pos[r3].astype(int), groups_of[r3], seed, poly=True)
    return Cs


# ------------------------------------------------------------------ evaluation
def labels(R):
    cls = fault_class(R["et"])
    fine = np.array([f"{c}_{p}" if c else "" for c, p in zip(cls, np.asarray(R["phase"]).astype(str))])
    return direction_label(R), cls, fine, R["pos"].astype(int)


def summarise(dec, R, idx, y):
    n = len(R["et"]); sel = np.arange(n)
    r = rates_plus(dec, R, sel, idx, y, np.ones(n, bool))
    kn = lambda h: (dict(k=r[h]["k"], n=r[h]["n"], ucb95=r[h]["dedup"]["ucb95"]) if h in r else None)
    return dict(dependability=r["pos"]["rate"], dependability_ci=r["dependability_ci"],
                offline=dict(k=r["neg"]["dedup"]["k"], n=r["neg"]["dedup"]["n"], ucb95=r["neg"]["dedup"]["ucb95"]),
                next_line=r["neg_bench"], incipient=r["incipient"],
                per_class={h: kn(h) for h in ("own99", "parallel", "reverse_bus", "reverse_lines", "other", "switching")},
                dep_by_rf_bin={b: r["dep_by_rf_bin"][b]["rate"] for b in cm.RF_LABELS},
                settable=r["settable"])


def run_one(Rtr, Rte, variant, t_ms, kind, seed=0, smoke=False, fwd=None):
    """One relay x variant x decision time x split. Rtr / Rte differ only for the mismatch chain."""
    t0 = time.time()
    v = VARIANTS[variant]
    n = len(Rtr["et"])
    idx, y, groups = zone_task(Rtr)
    hrows = np.setdiff1d(np.arange(n), idx)
    D, cls, fine, pos = labels(Rtr)
    groups_of = Rtr["groups"]
    all_rows = np.arange(n)
    Ff_tr, Fp_tr = features_at(Rtr, all_rows, t_ms, variant), features_at(Rtr, all_rows, PREFAULT_END / FS * 1000, variant)
    Ff_te = Ff_tr if Rte is Rtr else features_at(Rte, all_rows, t_ms, variant)
    Fp_te = Fp_tr if Rte is Rtr else features_at(Rte, all_rows, PREFAULT_END / FS * 1000, variant)
    Z = np.full(n, np.nan); Znat = np.full(n, np.nan); fold_of = np.full(n, -1)
    H, Hnat, thr0, thrf, warn, sel, Cs_used, st = [], [], [], [], 0, [], [], dict(s1=[], s2=[], s3=[])
    for f, tr, te, meta in splits(kind, Rtr, idx, y, groups):
        if smoke and f > 0:
            break
        s = f + seed
        rtr, rte = idx[tr], idx[te]
        Cs = tuned_Cs(Ff_tr, Fp_tr, rtr, D, cls, fine, pos, groups_of, s) if v["tune_c"] else None
        Cs_used.append(Cs)
        # inner out-of-fold scores of the training negatives -> thresholds (grouped by loading bin)
        oof = np.full(len(rtr), np.nan)
        for k, (a, b) in enumerate(StratifiedGroupKFold(5, shuffle=True, random_state=s).split(rtr, y[tr], groups[tr])):
            hk = Hierarchy(Cs, seed=s + 100 + k).fit(Ff_tr, Fp_tr, rtr[a], D, cls, fine, pos)
            oof[b] = hk.score(Ff_tr, rtr[b])[0]
            warn += hk.warnings()
        neg = oof[y[tr] == 0]
        thr0.append(float(neg.max())); thrf.append(float(cm.thr_at_far(neg, FAR)))
        h = Hierarchy(Cs, seed=s).fit(Ff_tr, Fp_tr, rtr, D, cls, fine, pos)
        warn += h.warnings(); sel.append(h.selected())
        g, d, c = h.score(Ff_te, rte)
        Z[rte] = g; fold_of[rte] = f
        gh, dh, _ = h.score(Ff_te, hrows)
        H.append(gh)
        # stage accuracies on the test simulations (end-to-end routing)
        dd = D[rte]; known = dd >= 1
        dpre = h.s1.predict(stack(Fp_te, ("common",), rte))
        st["s1"].append(dict(fault_dir_acc=float((d[known] == dd[known]).mean()) if known.any() else None,
                             prefault_nofault_acc=float((dpre == 0).mean())))
        cc = cls[rte]; kc = cc != ""
        st["s2"].append(float((c[kc] == cc[kc]).mean()) if kc.any() else None)
        fz = (dd == 2)
        st["s3"].append(float(((g[fz] > 0) == (pos[rte][fz] == 1)).mean()) if fz.any() else None)
    tested = fold_of >= 0
    Hb = np.stack(H); thr0 = np.array(thr0)
    out = dict(variant=variant, t_ms=t_ms, split=kind, n_folds=int(len(thr0)), thresholds_cal0=thr0.tolist(),
               convergence_warnings=int(warn), tuned_C=Cs_used if v["tune_c"] else None,
               stage_accuracy=dict(s1_fault_direction=[x["fault_dir_acc"] for x in st["s1"]],
                                   s1_prefault_no_fault=[x["prefault_nofault_acc"] for x in st["s1"]],
                                   s2_fault_class=st["s2"], s3_zone_end_to_end=st["s3"]),
               selected_term_overlap=_overlap(sel), readouts={})
    zi = idx[tested[idx]]
    auc = roc_auc_score(y[np.isin(idx, zi)], Z[zi]) if len(np.unique(y[np.isin(idx, zi)])) > 1 else None
    out["auc"] = auc
    fwd = fwd if fwd is not None else np.ones(n, bool)
    for op in ("native", "cal0", "roc0", "roc1"):
        dec = np.zeros(n, bool)
        if op == "native":
            dec[tested] = Z[tested] > 0
            dec[hrows] = np.mean(Hb > 0, axis=0) >= 0.5
        elif op == "cal0":
            dec[tested] = Z[tested] > thr0[fold_of[tested]]
            dec[hrows] = np.mean(Hb > thr0[:, None], axis=0) >= 0.5
        else:
            tau = pooled_threshold(Z[zi][y[np.isin(idx, zi)] == 0], 0 if op == "roc0" else 1)
            dec[tested] = Z[tested] > tau
            dec[hrows] = np.mean(Hb > tau, axis=0) >= 0.5
        idx_t = idx[tested[idx]]; y_t = Rtr["pos"][idx_t].astype(int)
        out["readouts"][op] = dict(unsupervised=summarise(dec, Rte, idx_t, y_t),
                                   directional=summarise(dec & fwd, Rte, idx_t, y_t))
    out["runtime_s"] = float(time.time() - t0)
    return out


def _overlap(sel):
    """Mean pairwise Jaccard overlap of the selected stage-3 terms across folds, per class."""
    res = {}
    for c in CLASSES:
        S = [set(s[c]) for s in sel if s.get(c)]
        if len(S) < 2:
            res[c] = None; continue
        j = [len(a & b) / len(a | b) for i, a in enumerate(S) for b in S[i + 1:]]
        res[c] = float(np.mean(j))
    return res


def shortcut_auc(R, variant, seed=0):
    """AUC of a scaled LinearSVC on the 3-cycle buffer ending at inception (no fault in it), grouped 5-fold."""
    idx, y, groups = zone_task(R)
    F = features_at(R, idx, 0.0, variant)
    X = stack(F, ("common", "neg", "zero"))
    s = np.zeros(len(y))
    for a, b in StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(X, y, groups):
        st = Stage(1.0, seed=seed).fit(X[a], y[a])
        s[b] = st.decision(X[b])
    return float(roc_auc_score(y, s))


def main(relays=("adapt_A", "adapt_B"), times=(20, 50), variants=tuple(VARIANTS), kinds=("grouped", "loqo"),
         smoke=False):
    t0 = time.time()
    frontend.enable()
    res = dict(script="hasan_svm", commit=cm.git_commit(), frontend="relayfe", smoke=smoke,
               protocol=dict(buffer_cycles=BUFFER / SPC, stride_samples=STRIDE, k_top=K_TOP, c_grid=list(C_GRID),
                             variants=VARIANTS, stage3_blocks=STAGE3_BLOCKS, prefault_end_ms=PREFAULT_END / FS * 1000),
               relays={})
    if smoke:
        variants, kinds = variants[:1], kinds
    for relay in relays:
        R = bundle(relay, None)
        fwd = supervision(R, np.arange(len(R["et"])))
        rr = dict(shortcut_auc={v: shortcut_auc(R, v) for v in variants[:1]}, runs={})
        from review.adaptgrid_seeds import threshold_provenance
        idx, y, groups = zone_task(R)
        rr["threshold_provenance"] = {k: threshold_provenance(R, idx, y, groups, k) for k in kinds}
        for v in variants:
            for t in times:
                for kind in kinds:
                    r = run_one(R, R, v, t, kind, smoke=smoke, fwd=fwd)
                    rr["runs"][f"{v}|{t}|{kind}|matched"] = r
                    _print(relay, r, "matched")
        if not smoke and "default" in variants:
            d1, d2 = q1.draw_installation_fault(relay, 0), q1.draw_installation_fault(relay, 1)
            R1, R2 = bundle(relay, d1), bundle(relay, d2)
            fwd2 = supervision(R2, np.arange(len(R2["et"])))
            rr["mismatch_draws"] = dict(train=d1, test=d2)
            for t in times:
                for kind in kinds:
                    r = run_one(R1, R2, "default", t, kind, fwd=fwd2)
                    rr["runs"][f"default|{t}|{kind}|mismatch"] = r
                    _print(relay, r, "mismatch")
            del R1, R2
        res["relays"][relay] = rr
        del R
    res["runtime_s"] = float(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    tag = "" if tuple(relays) == ("adapt_A", "adapt_B") else "_" + "-".join(relays)     # never overwrite the TestGrid run
    path = os.path.join(OUT, f"hasan_svm_relayfe{tag}{'_smoke' if smoke else ''}.json")
    json.dump(res, open(path, "w"), indent=1, default=str)
    print("saved", path, f"[{res['runtime_s']:.0f}s]", flush=True)
    return res


def _print(relay, r, chain):
    nat, c0 = r["readouts"]["native"]["unsupervised"], r["readouts"]["cal0"]["unsupervised"]
    print(f"  [{relay} {chain} {r['variant']:7s} {r['t_ms']:2d} ms {r['split']:7s}] AUC {r['auc'] if r['auc'] is None else round(r['auc'], 4)} | "
          f"native dep {100*nat['dependability']:5.1f} off {nat['offline']['k']}/{nat['offline']['n']} sw {nat['per_class']['switching']['k']} | "
          f"cal0 dep {100*c0['dependability']:5.1f} off {c0['offline']['k']}/{c0['offline']['n']} sw {c0['per_class']['switching']['k']} | "
          f"warn {r['convergence_warnings']} [{r['runtime_s']:.0f}s]", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--relays", nargs="+", default=["adapt_A", "adapt_B"])
    ap.add_argument("--times", type=int, nargs="+", default=[20, 50])
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS))
    ap.add_argument("--splits", nargs="+", default=["grouped", "loqo"])
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    main(tuple(a.relays), tuple(a.times), tuple(a.variants), tuple(a.splits), a.smoke)
