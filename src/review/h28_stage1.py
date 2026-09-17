"""H28: stage 1 (fault detector) label, baseline and uncertainty.

Positive definitions
  any        event_type starts with 'flt' (real_ml.py): every fault anywhere in the grid, incipient included
  responsible short circuits the relay must start for: own line (all locations), remote bus, lines beyond the
             remote bus (all locations), the parallel line; incipient faults and far-away faults excluded
Negatives: switching events (50 per grid) and a pre-fault window of every episode (as real_ml.py).

Detectors at 20 ms
  conventional starter  superimposed phase-current start (h10_trigger.trigger: |i(k) - i(k-1 cycle)| >
                        max(0.1 In, 8 sigma) for 3 samples within the window) blocked by second-harmonic
                        restraint (I_2nd / I_fund > 15 % on any phase over the last cycle, inrush blocking);
                        nothing fitted
  MLP (real_ml)         trained per grouped fold (groups: fault sibling groups; each switching event its own
                        group) on each positive definition, threshold at 5 % on out-of-fold scores of the
                        training switching events, exactly as real_ml.two_stage_security
Reported with Clopper-Pearson 95 % intervals on switching events (k/n); a 5 % budget cannot be supported by
50 events (59 are needed even with zero trips), which is stated rather than tuned to.
Two-stage security: starter (conventional or MLP) AND zone rung R2 on switching and relay-bus reverse faults.

    python src/review/h28_stage1.py
"""
import sys, os, json, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from review import common as cm
from review import ladder as ld
from review.h10_trigger import trigger
import real_ml

CODE = ("src/review/h28_stage1.py", "src/review/h10_trigger.py", "src/review/ladder.py", "src/review/common.py",
        "src/review/setting_study.py", "src/real_ml.py", "src/evemt.py")


def second_harmonic_block(R, idx, t=20, frac=0.15):
    ev = R["ev"]; end = ev + int(t * 6.4)
    seg = R["full"][idx, 3:, end - 128:end].astype(np.float64)
    k = np.arange(end - 128, end)
    f1 = np.abs(seg @ np.exp(-2j * np.pi * k / 128))
    f2 = np.abs(seg @ np.exp(-2j * np.pi * 2 * k / 128))
    return ((f2 / (f1 + 1e-9)) > frac).any(1)


if __name__ == "__main__":
    t0 = time.time()
    commit = cm.git_commit()
    if not cm.code_unchanged(commit, commit, CODE):
        raise SystemExit("commit the experiment code first")
    res = {}
    for name in ("testgrid_A", "testgrid_B", "doubleline"):
        cfg = dict(script="h28", relay=name)
        path = os.path.join(cm.ROOT, "logs", "ckpt", "h28", cm.config_hash(cfg) + ".pkl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            rec = pickle.load(open(path, "rb"))
            assert rec["_config"] == cfg and cm.code_unchanged(rec["_commit"], commit, CODE), "checkpoint mismatch"
            res[name] = rec["result"]; continue
        R = cm.load_relay(name)
        S = ld.settings(R, name)
        cfgR = R["cfg"]
        shc = np.char.find(R["et"].astype(str), "shc") >= 0
        responsible = shc & ((R["tgt"] == cfgR["line"]) | (R["tgt"] == cfgR["remote_bus"]) | np.isin(R["tgt"], cfgR["beyond"])
                             | ((R["tgt"] == cfgR["parallel"]) if cfgR["parallel"] else False))
        sets = dict(any=R["fault_any"], responsible=responsible)
        episodes = np.where(R["fault_any"] | R["switching"])[0]
        sw = R["switching"][episodes]
        out = dict(n_switching=int(R["switching"].sum()), n_any=int(R["fault_any"].sum()), n_responsible=int(responsible.sum()),
                   min_events_for_5pct_budget=cm.min_n_for_budget(0.05))
        # conventional starter
        delay = trigger(R, episodes)
        started = (delay < 10**6) & (delay <= 20 * 6.4)
        blocked = second_harmonic_block(R, episodes)
        conv = started & ~blocked
        zone = ld.evaluate_block(R, *ld.pack(R, episodes, 20, "full", True), S, "R2")[0]
        def rate(dec, mask):
            k, n = int(dec[mask].sum()), int(mask.sum())
            return dict(k=k, n=n, rate=k / n if n else None, ci=cm.binom_ci(k, n))
        pos_in_zone = R["pos"][episodes]
        out["conventional starter"] = dict(any=rate(conv, R["fault_any"][episodes]), responsible=rate(conv, responsible[episodes]),
                                           in_zone=rate(conv, pos_in_zone), switching=rate(conv, sw),
                                           switching_by_type={t: rate(conv, sw & (R["et"][episodes] == t)) for t in np.unique(R["et"][episodes][sw])},
                                           two_stage_with_R2=dict(in_zone=rate(conv & zone, pos_in_zone), switching=rate(conv & zone, sw),
                                                                  reverse_bus=rate(conv & zone, R["reverse_bus"][episodes])))
        # learned stage 1, grouped folds
        groups = np.where(sw, 10**6 + episodes, R["groups"][episodes])
        for label, P in sets.items():
            yl = P[episodes].astype(int)
            dec = np.zeros(len(episodes), bool); score = np.zeros(len(episodes)); aucs = []
            for f, (tr, te) in enumerate(StratifiedGroupKFold(5, shuffle=True, random_state=0).split(episodes, np.where(sw, 2, yl), groups)):
                tr_ep = episodes[tr]
                X1 = np.vstack([real_ml.raw_window(R, tr_ep, 20), real_ml.raw_window(R, tr_ep, 20, prefault=True)])
                y1 = np.concatenate([yl[tr], np.zeros(len(tr), int)])
                m1 = real_ml.fit_balanced(real_ml.models(f)["MLP"], X1, y1, f)
                is_sw = np.concatenate([sw[tr], np.zeros(len(tr), bool)])
                g1 = np.concatenate([groups[tr], groups[tr]])              # an episode's pre-fault window shares its group
                thr = np.quantile(cm.oof_scores("MLP", X1, y1, f, groups=g1)[is_sw], 0.95)
                s = real_ml.score(m1, real_ml.raw_window(R, episodes[te], 20))
                dec[te] = s > thr; score[te] = s
                fsw = (yl[te] == 1) | sw[te]
                if 0 < yl[te][fsw].sum() < fsw.sum():
                    aucs.append(roc_auc_score(yl[te][fsw], s[fsw]))
            out[f"MLP stage 1 ({label})"] = dict(auc_fault_vs_switching=float(np.mean(aucs)), auc_sd=float(np.std(aucs)),
                                                 positives=rate(dec, yl == 1), in_zone=rate(dec, pos_in_zone), switching=rate(dec, sw),
                                                 two_stage_with_R2=dict(in_zone=rate(dec & zone, pos_in_zone), switching=rate(dec & zone, sw),
                                                                        reverse_bus=rate(dec & zone, R["reverse_bus"][episodes])))
            print(f"[{name}] MLP stage 1 ({label}): AUC {np.mean(aucs):.3f} +- {np.std(aucs):.3f}; in-zone pass "
                  f"{dec[pos_in_zone].mean()*100:.1f} %, switching {int(dec[sw].sum())}/{int(sw.sum())} [{time.time()-t0:.0f}s]", flush=True)
        c = out["conventional starter"]
        print(f"[{name}] conventional starter: in-zone {c['in_zone']['k']}/{c['in_zone']['n']}, responsible {c['responsible']['rate']*100:.1f} %, "
              f"any {c['any']['rate']*100:.1f} %, switching {c['switching']['k']}/{c['switching']['n']} (95 % CI {np.round(c['switching']['ci'], 3)})", flush=True)
        pickle.dump(dict(_commit=commit, _config=cfg, result=out), open(path, "wb"))
        res[name] = out
        del R
    json.dump(res, open(os.path.join(cm.ROOT, "results", "review", "h28_stage1.json"), "w"), indent=1, default=str)
    print("saved results/review/h28_stage1.json")
