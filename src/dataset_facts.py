"""Dataset fact sheet for the review: labels, factorial structure, CV sibling leakage,
units, pre-fault fingerprint, operating-point variation, ADC clipping. Reads labels and a
small part of each relay's record only.

    python src/dataset_facts.py

Changes from the template in the review brief: event_type contains 'flt_1phg_shc_w_arc',
which also matches 'shc'; the phase-selection columns are reported; exact-duplicate checks
for symmetrical (3ph) siblings; per-relay facts for all three relays of the review (A and B
share one TestGrid cache); location/R_f read as floats.
"""
import sys, os, glob, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evemt import load_cache
from real_zone import CONFIGS
from sklearn.model_selection import RepeatedStratifiedKFold, GroupKFold

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
V_NOM_PEAK_PRIMARY = 110e3 * np.sqrt(2 / 3)
I_FULL_SCALE = 40.0          # as in real_ml.py


def col(L, name):
    return L[name] if name in L.columns else pd.Series([np.nan] * len(L), index=L.index)


def sibling_share(groups, y, splitter):
    shares = []
    for tr, te in splitter.split(np.zeros(len(y)), y, groups):
        in_train = set(groups[tr])
        shares.append(float(np.mean([g in in_train for g in groups[te]])))
    return float(np.mean(shares)), float(np.std(shares))


def zone_groups(L, cfg):
    et = L["events/event_type"].astype(str)
    tgt = L["events/event_target"].astype(str)
    loc = col(L, "events/event_flt_target_line_location")
    rf = col(L, "events/event_flt_shc_resistance")
    shc = et.str.contains("shc").to_numpy()
    pos = shc & (tgt == cfg["line"]).to_numpy() & loc.isin([1, 20, 50, 80]).to_numpy()
    neg = shc & ((tgt.isin(cfg["beyond"]) & loc.isin([1, 20])) | (tgt == cfg["remote_bus"])).to_numpy()
    idx = np.where(pos | neg)[0]
    key = (tgt.iloc[idx].astype(str) + "|" + loc.iloc[idx].astype(str) + "|"
           + et.iloc[idx] + "|" + rf.iloc[idx].astype(str)).to_numpy()
    _, groups = np.unique(key, return_inverse=True)
    return pos, neg, idx, groups


def main():
    facts = {}
    caches = {}
    for name, cfg in CONFIGS.items():
        paths = sorted(glob.glob(os.path.join(ROOT, "data", cfg["cache_glob"])))
        if not paths:
            facts[name] = "cache not found"; print(name, "cache not found"); continue
        if paths[0] not in caches:
            caches[paths[0]] = load_cache(paths[0])
        C = caches[paths[0]]; L = C["labels"]
        et = L["events/event_type"].astype(str)
        tgt = L["events/event_target"].astype(str)
        loc = col(L, "events/event_flt_target_line_location")
        rf = col(L, "events/event_flt_shc_resistance")
        F = {"cache": os.path.basename(paths[0]), "relay": cfg["relay"]}

        # 1. label vocabulary and what actually varies across simulations
        F["n_simulations"] = int(len(L))
        F["event_type_counts"] = et.value_counts().to_dict()
        F["columns_that_vary"] = {c: int(L[c].nunique(dropna=True)) for c in L.columns
                                  if L[c].nunique(dropna=True) > 1}
        F["columns_constant"] = {c: (str(L[c].dropna().iloc[0]) if L[c].notna().any() else "all NaN")
                                 for c in L.columns if L[c].nunique(dropna=True) <= 1}
        F["operating_point_columns_present"] = [c for c in L.columns if any(
            s in c.lower() for s in ("load", "sc_", "ssc", "source", "angle", "inception", "pow", "ibr_p", "loading"))]

        # 2. zone task as defined in real_zone.py / real_ml.py, and its factorial structure
        shc = et.str.contains("shc").to_numpy()
        flt = et.str.startswith("flt").to_numpy()
        pos, neg, idx, groups = zone_groups(L, cfg)
        y = pos[idx].astype(int)
        F["counts"] = dict(in_zone=int(pos.sum()), out_of_zone=int(neg.sum()), shc=int(shc.sum()),
                           flt_any=int(flt.sum()), flt_not_shc=int((flt & ~shc).sum()),
                           flt_not_shc_types=et[flt & ~shc].value_counts().to_dict(),
                           switching=int(et.str.startswith("switch").sum()),
                           flt_any_on_own_line_or_remote_bus_or_beyond=int((flt & (
                               (tgt == cfg["line"]) | (tgt == cfg["remote_bus"]) | tgt.isin(cfg["beyond"])).to_numpy()).sum()))
        F["in_zone_by_type"] = et[pos].value_counts().to_dict()
        F["out_of_zone_by_target"] = tgt[neg].value_counts().to_dict()
        sizes = np.bincount(groups)
        F["sibling_groups"] = dict(n_groups=int(len(sizes)),
                                   size_histogram={int(k): int(v) for k, v in zip(*np.unique(sizes, return_counts=True))})
        F["test_cases_with_sibling_in_train_stratifiedCV"] = sibling_share(
            groups, y, RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=0))
        F["test_cases_with_sibling_in_train_groupCV"] = sibling_share(groups, y, GroupKFold(n_splits=5))

        # 3. units: primary (~89.8 kV peak phase) or secondary (~82 V)?
        k = C["cubicles"].index(cfg["relay"])
        ev, spc = C["event_index"], C["samples_per_cycle"]
        pre = np.asarray(C["x"][:, k, :, ev - 2 * spc:ev - spc], dtype=np.float64)   # one pre-fault cycle, all sims
        F["prefault_phase_voltage_peak_median"] = float(np.median(np.abs(pre[:, :3]).max(axis=-1)))
        F["expected_peak_if_primary_V"] = float(V_NOM_PEAK_PRIMARY)
        F["prefault_phase_current_peak_median"] = float(np.median(np.abs(pre[:, 3:]).max(axis=-1)))

        # 4. pre-fault fingerprint and operating-point variation (identical loading => tiny spread)
        F["prefault_voltage_spread_across_sims_rel_nominal"] = float(pre[:, :3].std(axis=0).max() / V_NOM_PEAK_PRIMARY)
        F["prefault_current_spread_across_sims_rel_median_peak"] = float(
            pre[:, 3:].std(axis=0).max() / max(F["prefault_phase_current_peak_median"], 1e-12))
        F["prefault_voltage_max_abs_diff_across_sims_V"] = float(np.ptp(pre[:, :3], axis=0).max())
        F["prefault_current_max_abs_diff_across_sims_A"] = float(np.ptp(pre[:, 3:], axis=0).max())
        # measurement-chain noise sigma of real_ml.py, for comparison with the spread above
        F["real_ml_noise_sigma_V"] = float(1e-3 * V_NOM_PEAK_PRIMARY)

        # 5. near-duplicates: symmetrical (3ph) siblings differ only by a label that has no physical meaning
        x3 = np.where((et == "flt_3ph_shc").to_numpy() & (pos | neg))[0]
        g3 = {}
        for i in x3:
            g3.setdefault((tgt[i], loc[i], rf[i]), []).append(i)
        rel = []
        for members in g3.values():
            if len(members) < 2:
                continue
            W = np.asarray(C["x"][members, k, :, ev - spc:ev + 2 * spc], dtype=np.float64)
            scale = np.abs(W).max(axis=(0, 2))[None, :, None] + 1e-12
            Wn = W / scale
            rel.append(float(np.abs(Wn[1:] - Wn[:1]).max()))
        F["threephase_sibling_max_rel_diff"] = dict(n_groups=len(rel), median=float(np.median(rel)) if rel else None,
                                                    max=float(np.max(rel)) if rel else None)

        # 6. ADC clipping implied by real_ml.measurement_chain full scale (+-40 x pre-fault peak current)
        x_i = np.asarray(C["x"][:, k, 3:], dtype=np.float32)
        i_pre = float(np.abs(x_i[:, :, :x_i.shape[-1] // 5]).max())
        clipped = (np.abs(x_i) >= I_FULL_SCALE * i_pre).any(axis=(1, 2))
        peak_ratio = np.abs(x_i[:, :, ev:]).max(axis=(1, 2)) / i_pre
        F["adc_clipping"] = dict(i_pre_A=i_pre, full_scale_A=I_FULL_SCALE * i_pre, sims_clipped=int(clipped.sum()),
                                 in_zone_clipped=int(clipped[pos].sum()),
                                 in_zone_peak_over_prefault_median=float(np.median(peak_ratio[pos])),
                                 in_zone_peak_over_prefault_max=float(np.max(peak_ratio[pos])),
                                 by_location_in_zone={str(v): int(clipped[pos & (loc == v).to_numpy()].sum())
                                                      for v in (1, 20, 50, 80)})
        facts[name] = F
        print(f"\n[{name}]", json.dumps({kk: F[kk] for kk in (
            "counts", "in_zone_by_type", "sibling_groups", "test_cases_with_sibling_in_train_stratifiedCV",
            "test_cases_with_sibling_in_train_groupCV", "prefault_phase_voltage_peak_median",
            "prefault_phase_current_peak_median", "prefault_voltage_spread_across_sims_rel_nominal",
            "prefault_voltage_max_abs_diff_across_sims_V", "threephase_sibling_max_rel_diff", "adc_clipping",
            "columns_constant")}, indent=1, default=str))

    json.dump(facts, open(os.path.join(ROOT, "results", "DATASET_FACTS.json"), "w"), indent=2, default=str)
    print("\nsaved results/DATASET_FACTS.json")


if __name__ == "__main__":
    main()
