"""N2-synth: the distance element uses the sign of the loop reactance as its direction test.

zone_model.phase_selected_reactance keeps only released loops with Im(Z) > 0 and otherwise
returns default = 10.0 ("reverse", never trips). On real data most in-zone high-resistance
faults at a relay with remote infeed read negative X and are discarded. Measured here on the
synthetic zone study (zone_detect.score_reactance), --quick sizes, 3 seeds:
  1. fraction of positives / negatives (and per fault kind) scored 10.0, per delta;
     fraction whose released loops have min X < 0;
  2. AUC and dependability at 1 % FAR (train-chosen polarity) for
       original      phase_selected_reactance (Im(Z) > 0 test, default 10)
       no-sign       min X over released loops, no direction test at all
       directional   min X over released loops, gated by a separate directional element
                     (negative-sequence, positive-sequence memory-polarised fallback)
  3. forward-decision rate of the directional element per class and per kind vs delta, and
     how often the negative-sequence branch is used (delta is itself negative-sequence current).
Test sets only for the rates; thresholds on train. CPU only.

  python src/review/n2_directional.py
"""
import time
import numpy as np
from dataclasses import replace
from common import design_direction, save
from waveforms import SigParams
import detect as D
import zone_detect as Z
from zone_model import phase_selected_reactance, directional_reactance, directional_forward, released_loops, loop_impedances

direction = design_direction()
grid = replace(Z.ZoneParams(), rF=0.3)
z1, z0 = grid.z1, grid.z0_ratio * grid.z1
DELTAS = (0.0, 0.10, 0.30, 0.514)


def all_scores(X):
    orig, nosign, direc, fwd, negbr, minx = [], [], [], [], [], []
    for x in X:
        vpre, vpost, ipre, ipost = Z._phasors(x)
        orig.append(phase_selected_reactance(vpost, ipre, ipost, z1, z0))
        nosign.append(directional_reactance(vpre, vpost, ipre, ipost, z1, z0, directional=False))
        direc.append(directional_reactance(vpre, vpost, ipre, ipost, z1, z0, directional=True))
        f, nb = directional_forward(vpre, vpost, ipre, ipost, z1)
        fwd.append(f); negbr.append(nb)
    return dict(original=np.array(orig), nosign=np.array(nosign), directional=np.array(direc),
                forward=np.array(fwd), negseq_branch=np.array(negbr))


rows = []; rates = []; t0 = time.time()
for t in DELTAS:
    for sd in range(3):
        Xtr, ytr, _ = Z.make_zone_dataset(350, np.random.default_rng(100 + 17 * sd), t * direction, SigParams(), grid)
        Xte, yte, kte = Z.make_zone_dataset(250, np.random.default_rng(999 + 31 * sd), t * direction, SigParams(), grid)
        A, B = all_scores(Xtr), all_scores(Xte)
        for v in ("original", "nosign", "directional"):
            rows.append(dict(delta=t, seed=sd, variant=v, **D.evaluate(A[v], ytr, B[v], yte)))
        r = dict(delta=t, seed=sd)
        for grp, m in (("pos", yte == 1), ("neg", yte == 0), ("ag", kte == "ag"), ("ab", kte == "ab"),
                       ("ag2", kte == "ag2"), ("ab2", kte == "ab2")):
            r[grp] = dict(default10=float((B["original"][m] >= 10.0).mean()),
                          minx_negative=float((B["nosign"][m] < 0).mean()),
                          forward=float(B["forward"][m].mean()),
                          negseq_branch=float(B["negseq_branch"][m].mean()),
                          directional_default10=float((B["directional"][m] >= 10.0).mean()))
        rates.append(r)
    print(f"delta={t} [{time.time()-t0:.0f}s]", flush=True)

print("\n(1)+(3) test-set rates, mean over 3 seeds (%)")
print("delta  group  scored10(orig)  minX<0  dir.forward  negseq-branch  scored10(directional)")
for t in DELTAS:
    for grp in ("pos", "neg", "ag", "ab", "ag2", "ab2"):
        rr = [r[grp] for r in rates if r["delta"] == t]
        f = lambda k: np.mean([x[k] for x in rr]) * 100
        print(f"{t:.3f}  {grp:4s}   {f('default10'):6.1f}         {f('minx_negative'):6.1f}  {f('forward'):6.1f}       "
              f"{f('negseq_branch'):6.1f}         {f('directional_default10'):6.1f}")
print("\n(2) AUC and dependability at 1 % FAR, mean +- sd over seeds")
summary = {}
for v in ("original", "nosign", "directional"):
    au = [np.mean([r["auc"] for r in rows if r["delta"] == t and r["variant"] == v]) for t in DELTAS]
    sdv = [np.std([r["auc"] for r in rows if r["delta"] == t and r["variant"] == v]) for t in DELTAS]
    de = [np.mean([r["detection_rate"] for r in rows if r["delta"] == t and r["variant"] == v]) * 100 for t in DELTAS]
    fa = [np.mean([r["false_alarm"] for r in rows if r["delta"] == t and r["variant"] == v]) * 100 for t in DELTAS]
    summary[v] = dict(auc=au, auc_sd=sdv, dep=de, far=fa, slope=float(np.polyfit(DELTAS, au, 1)[0]))
    print(f"{v:12s} AUC " + "  ".join(f"{a:.3f}+-{s:.3f}" for a, s in zip(au, sdv)) +
          f"   slope {summary[v]['slope']:+.3f}/pu   dep " + "/".join(f"{d:.0f}" for d in de) +
          "   FAR " + "/".join(f"{x:.1f}" for x in fa))
save("n2_directional.json", dict(rows=rows, rates=rates, summary=summary, runtime_s=time.time() - t0))
