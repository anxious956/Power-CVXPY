"""
End-to-end check that a PSCAD run and this repository's relay code are connected: read the run,
resample to 128 samples per cycle, take phasors one cycle before and one cycle after inception,
and let the distance element locate the fault.

    python src/pscad_check.py data/pscad_work/Relay_Cases/case1.gf46 case1 --end 1

Channels follow the PSCAD Relay_Cases naming: V<end>a..c in kV, I<end>a..c in kA, so the loop
impedances come out in ohms directly.
"""
import os, sys, argparse
import numpy as np
from scipy.signal import resample_poly
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pscad_io import read_case, line_constants
from waveforms import sequence_phasors, CYCLE
from zone_model import loop_impedances, released_loops, directional_forward


def to_128_per_cycle(x, fs, f0):
    target = Fraction(int(round(CYCLE * f0)), int(round(fs))).limit_denominator(1000)
    return resample_poly(x, target.numerator, target.denominator, axis=-1), CYCLE * f0


def inception_index(i3, spc, k=5.0):
    """First sample where the cycle-to-cycle difference of any phase current exceeds k times its
    pre-event level: a plain superimposed-current starter, causal."""
    d = np.abs(i3[:, spc:] - i3[:, :-spc]).max(axis=0)
    base = np.median(d[: 2 * spc]) + 1e-9
    hits = np.where(d > k * base + 0.02 * np.abs(i3).max())[0]
    return int(hits[0]) + spc if len(hits) else None


def check(out_dir, case, end="1", line="LINE1", after=1.5):
    """Locate the fault seen from terminal `end`. Returns a dict; distance_pct is None when no
    released loop is forward (the element does not trip), never a sentinel value."""
    run = read_case(out_dir, case)
    z = line_constants(os.path.join(out_dir, line + ".out"))
    f0 = z["f"] or 60.0
    v = np.array([run["ch"][f"V{end}{p}"] for p in "abc"])
    i = np.array([run["ch"][f"I{end}{p}"] for p in "abc"])
    v, fs = to_128_per_cycle(v, run["fs"], f0)
    i, _ = to_128_per_cycle(i, run["fs"], f0)
    ev = inception_index(i, CYCLE)
    pre = ev - 2 * CYCLE
    post = ev + int(round((after - 1) * CYCLE))
    vpre, ipre = sequence_phasors(v, pre), sequence_phasors(i, pre)
    vpost, ipost = sequence_phasors(v, post), sequence_phasors(i, post)
    y = np.array([vpost[1], vpost[2], vpost[0], ipost[1], ipost[2], ipost[0]])
    L = loop_impedances(y, z["z1"], z["z0"])
    rel = released_loops(ipre, ipost)
    fwd, used_neg = directional_forward(vpre, vpost, ipre, ipost, z["z1"])
    x1 = z["z1"].imag
    fwd_loops = [k for k in rel if L[k].imag > 0]
    dist = min(L[k].imag for k in fwd_loops) / x1 * 100 if fwd_loops else None
    return dict(case=case, end=end, fs_in=run["fs"], fs=fs, f0=f0, z1=z["z1"], z0=z["z0"],
                t_inception=ev / fs, released=rel, loops=L, forward=fwd, dir_negseq=used_neg,
                distance_pct=dist, n_channels=len(run["ch"]))


def report(r):
    print(f"{r['case']} (end {r['end']}): {r['n_channels']} channels, {r['fs_in']:.0f} Hz -> {r['fs']:.0f} Hz "
          f"({CYCLE}/cycle at {r['f0']:.0f} Hz); Z1 = {r['z1']:.2f}, Z0 = {r['z0']:.2f} ohm")
    print(f"  inception detected at {r['t_inception']:.4f} s; released loops {r['released']}; "
          f"direction {'FORWARD' if r['forward'] else 'REVERSE'} ({'negative' if r['dir_negseq'] else 'positive'}-sequence)")
    for k, zz in r["loops"].items():
        mark = "  <- released" if k in r["released"] else ""
        print(f"    {k}: {zz.real:9.2f} + j{zz.imag:9.2f} ohm  = {zz.imag / r['z1'].imag * 100:8.1f} % of line X{mark}")
    if r["distance_pct"] is None:
        print("  distance element: no released loop is forward -> NO TRIP")
    else:
        d = r["distance_pct"]
        print(f"  distance element: {d:.1f} % of the line -> {'TRIP (inside 85 % zone 1)' if d <= 85 and r['forward'] else 'no zone-1 trip'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("case")
    ap.add_argument("--end", default="1", help="relay terminal, the digit in V1a / I1a")
    ap.add_argument("--line", default="LINE1")
    ap.add_argument("--after", type=float, default=1.5, help="cycles after inception at which to decide")
    a = ap.parse_args()
    report(check(a.out_dir, a.case, a.end, a.line, a.after))


if __name__ == "__main__":
    main()
