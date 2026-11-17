"""
Relay lesson 1, the check: did the PSCAD overcurrent relay (itoc51) trip when the hand calculation says?

Reads the runs of src/pscad_relay51.py and compares, for each one,
    the current the relay saw (60 Hz RMS, CT secondary amps) with the phasor calculation, and
    the trip time with the IEEE C37.112 very-inverse curve  t = TD * (19.61 / (M^2 - 1) + 0.491),  M = I / pickup.

    python src/pscad_relay51_check.py r51_base:5:1:0.01 r51_td05:5:0.5:0.01 ...      (name:pickup:TD:Rf)
    python src/pscad_relay51_check.py --plot r51_base docs/figures/relay51/r51_base.png
"""
import os, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pscad_io import read_case

WORK = r"D:\JOSHUA_TAYLOR_data\data\pscad_work\relay"
VLN = 13.8e3 / math.sqrt(3)
ZS, ZL, RLOAD = 0.5j, 2.0 + 4.0j, 13.8 ** 2 / 2.4      # ohm; the load is 2.4 MW at 13.8 kV, star
CTR = 200.0 / 5.0
A, B, P = 19.61, 0.491, 2.0                           # IEEE C37.112 very inverse


def curve(i_sec, pickup, td):
    m = i_sec / pickup
    return td * (A / (m ** P - 1.0) + B) if m > 1.0 else float("inf")


def expected_current(rf):
    """Relay current in secondary amps: (before the fault, during a three-phase fault of rf ohm at BUS2)."""
    pre = VLN / abs(ZS + ZL + RLOAD)
    zf = rf * RLOAD / (rf + RLOAD)
    return pre / CTR, VLN / abs(ZS + ZL + zf) / CTR


def first_time(t, x, level=0.5):
    k = np.nonzero(x > level)[0]
    return t[k[0]] if len(k) else None


def check(name, pickup, td, rf, t_fault=0.5):
    run = read_case(os.path.join(WORK, name + ".gf46"), name)
    t, ch = run["t"], run["ch"]
    pre_c, flt_c = expected_current(rf)
    pre_m = ch["Irelay"][np.searchsorted(t, t_fault - 0.02)]
    t_trip = first_time(t, ch["TRIP51"])
    t_brk = first_time(t, ch["BRK"])
    # the fault current the relay saw: the plateau between the fault and the trip
    t1 = t_trip if t_trip is not None else t[-1]
    k = (t > t_fault + 0.1) & (t < t1 - 0.01)
    flt_m = float(np.median(ch["Irelay"][k])) if k.any() else float("nan")
    t_calc = curve(flt_c, pickup, td)
    t_open = None
    if t_brk is not None:
        k2 = np.nonzero((t > t_brk) & (np.abs(ch["Ia"]) < 1e-4))[0]
        t_open = t[k2[0]] if len(k2) else None
    print(f"{name}: pickup {pickup} A, TD {td}, Rf {rf} ohm")
    print(f"   current before the fault  calc {pre_c:6.2f} A   PSCAD {pre_m:6.2f} A   (primary {pre_m * CTR:.0f} A)")
    print(f"   current in the fault      calc {flt_c:6.2f} A   PSCAD {flt_m:6.2f} A   (primary {flt_m * CTR:.0f} A, M = {flt_m / pickup:.2f})")
    if t_trip is None:
        print(f"   trip                      calc {'none' if math.isinf(t_calc) else f'{t_calc:.3f} s after the fault'}   PSCAD none in {t[-1]:.1f} s")
    else:
        print(f"   trip time after the fault calc {t_calc:.3f} s   PSCAD {t_trip - t_fault:.3f} s")
        if t_open is not None:
            print(f"   breaker signal at {t_brk:.3f} s, current zero at {t_open:.3f} s")
    return dict(name=name, pre=pre_m, flt=flt_m, t_trip=None if t_trip is None else t_trip - t_fault, t_calc=t_calc)


def plot(name, path, pickup=5.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    run = read_case(os.path.join(WORK, name + ".gf46"), name)
    t, ch = run["t"], run["ch"]
    fig, ax = plt.subplots(4, 1, figsize=(9, 8), sharex=True)
    ax[0].plot(t, ch["Ia"] * 1e3, lw=0.6)
    ax[0].set_ylabel("line current,\nphase A [A]")
    ax[1].plot(t, ch["Irelay"], color="C1")
    ax[1].axhline(pickup, color="k", ls="--", lw=0.8)
    ax[1].text(t[-1], pickup, " pickup", va="bottom", ha="right")
    ax[1].set_ylabel("relay current\n[A secondary]")
    ax[2].plot(t, ch["IntOP"], color="C2")
    ax[2].axhline(1.0, color="k", ls="--", lw=0.8)
    ax[2].set_ylabel("51 integrator\n(trip at 1)")
    ax[3].plot(t, ch["TRIP51"], label="TRIP51 (relay output)")
    ax[3].plot(t, ch["BRK"] * 0.9, label="BRK (1 = breaker open)")
    ax[3].set_ylabel("signals")
    ax[3].legend(loc="center left", frameon=False)
    ax[3].set_xlabel("time [s]")
    for a in ax:
        a.grid(alpha=0.3)
    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=150)
    print("wrote", path)


if __name__ == "__main__":
    if sys.argv[1] == "--plot":
        plot(sys.argv[2], sys.argv[3], *(float(a) for a in sys.argv[4:]))
    else:
        for arg in sys.argv[1:]:
            n, pk, td, rf = arg.split(":")
            check(n, float(pk), float(td), float(rf))
