"""(b2) hypothesis, static: at the carried delta, is the relay's increment dI2 dominated by the injected signal's own
change between normal operation and the fault (its frame turn plus the limiter), rather than by the fault?

Nominal source point, the shunt bracket at s = 1, solve_v1ref (the EMT-matched model). Per forward case:
  total    dI2 = I2(F, delta) - I2(N, delta)          (what the relay sees)
  fault    I2(F, 0) - I2(N, 0)                        (the same fault without delta)
  signal   total - fault                              (what delta adds)
  dD       the delivered delta's own change, d(F) - d(N), in absolute terms
and the conventional element on the total, on the fault part alone, and on the signal part alone.

    python review/checks/p_i2dir_b2_frameturn.py      (repo root at 1b7e5d3)
"""
import sys
import numpy as np
sys.path.insert(0, "src")
import network as nw
from i2dir_static import network_s, operating_point, direction_pk, FWD, PHI
from i2dir_b2 import settings, solve, U0


def ang_dir(dI, dV):
    a = np.degrees(np.angle(dI / dV)) % 360
    return "f" if PHI < a < 180 + PHI else "r"


net = network_s(1.0, 1e6, filters=True, inject=True)
sg, st = operating_point(1.0, 1e6, U0)
e, ic = sg["G"], complex(st["I"]["ID"], -st["I"]["IQ"])
for label, mag, angd in (("box 0.98 @ 205", 0.98, 205.0), ("structured 0.20 @ 230", 0.20, 230.0)):
    s0, sd = settings(st, ic, 0.0, 0.0), settings(st, ic, mag, angd)
    yN0, _, _ = solve(net, e, s0, None)
    yNd, injN, _ = solve(net, e, sd, None)
    cnt = dict(n=0, wrong_total=0, sig_dominant=0, wrong_follow_sig=0, wrong=0)
    by = {}
    for c in FWD:
        f = (c[0], c[1], c[2], c[3] * net.rF)
        yF0, _, _ = solve(net, e, s0, f)
        yFd, injF, _ = solve(net, e, sd, f)
        tot = yFd[4] - yNd[4]
        flt = yF0[4] - yN0[4]
        sig = tot - flt
        dD = injF["I"][1] - injN["I"][1]
        d_tot = direction_pk(yNd, yFd)
        dV2 = yFd[1] - yNd[1]
        d_sig = ang_dir(sig, dV2) if abs(sig) > 1e-9 else None
        d_flt = ang_dir(flt, yF0[1] - yN0[1]) if abs(flt) > 1e-9 else None
        cnt["n"] += 1
        wrong = d_tot != "f"
        cnt["wrong"] += wrong
        dom = abs(sig) > abs(flt)
        cnt["sig_dominant"] += dom
        if wrong and d_tot is not None and d_tot == d_sig:
            cnt["wrong_follow_sig"] += 1
        t = by.setdefault(c[2], [0, 0, 0, []])
        t[0] += 1; t[1] += wrong; t[2] += dom
        t[3].append(abs(sig - dD) / max(abs(sig), 1e-12))
    print(f"{label}: forward {cnt['n']}, conventional wrong or undecided {cnt['wrong']}; |signal part| > |fault part| in "
          f"{cnt['sig_dominant']}; wrong decisions that follow the signal part's own direction {cnt['wrong_follow_sig']}")
    for k, (n, w, d, rel) in by.items():
        print(f"    {k}: {n} cases, wrong {w}, signal-dominant {d}; |signal part - dD| / |signal part| median {np.median(rel):.2f}")
