"""Before/after tables for the zone sweep from zone_detect.py JSON outputs: ROC AUC mean +- sd
over seeds, and dependability at the 1 % FAR threshold mean +- sd with the realised test
false-alarm rate in brackets. Each cell is "original -> corrected".

  python src/review/sweep_table.py ORIGINAL.json CORRECTED.json
"""
import sys, json

KEYS = (("reactance", "reactance"), ("negseq", "\\|i-\\|"), ("engineered", "engineered+LR"), ("cnn", "CNN"))


def load(p):
    d = json.load(open(p))
    return {round(r["delta"], 3): r for r in d["rows"]}


a, b = load(sys.argv[1]), load(sys.argv[2])
common = sorted(set(a) & set(b))
print("AUC (mean +- sd over seeds), original -> corrected\n")
print("| delta | " + " | ".join(lab for _, lab in KEYS) + " |")
print("|---" * (1 + len(KEYS)) + "|")
for t in common:
    print(f"| {t:.3f} | " + " | ".join(
        f"{a[t][k]['auc']:.3f} +- {a[t][k]['auc_std']:.3f} -> {b[t][k]['auc']:.3f} +- {b[t][k]['auc_std']:.3f}"
        for k, _ in KEYS) + " |")
print("\nDependability at 1 % FAR, % (realised test FAR %), original -> corrected\n")
print("| delta | " + " | ".join(lab for _, lab in KEYS) + " |")
print("|---" * (1 + len(KEYS)) + "|")
for t in common:
    f = lambda r, k: f"{r[k]['detection_rate']*100:.1f} +- {r[k]['detection_std']*100:.1f} ({r[k]['false_alarm']*100:.2f})"
    print(f"| {t:.3f} | " + " | ".join(f"{f(a[t], k)} -> {f(b[t], k)}" for k, _ in KEYS) + " |")
