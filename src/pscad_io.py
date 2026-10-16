"""
Read PSCAD/EMTDC output into the same arrays the rest of this repository uses.

A PSCAD run with "save channels to disk" writes, in <case>.gf46/ (or .gf81/):
    <case>.inf          one line per output channel: PGB(k) Output Desc="name" ... Units="kV"
    <case>_01.out, ...  whitespace-separated columns, time first, then up to 10 channels per file
and the line-constants program writes <LINE>.out with the sequence impedances.

    from pscad_io import read_case, line_constants
    run = read_case(r"...\\case1.gf46", "case1")        # run["t"], run["ch"]["V1a"], run["units"]
    z = line_constants(r"...\\case1.gf46\\LINE1.out")  # z["z1"], z["z0"] in ohms, whole line

No PSCAD needed to read; the automation side (running cases) needs PSCAD's own Python 3.7 with
mhi.pscad, see docs/PSCAD.md.
"""
import os, re, glob
import numpy as np

_INF = re.compile(r'PGB\((\d+)\)\s+Output\s+Desc="([^"]*)".*?Units="([^"]*)"')


def read_inf(path):
    """[(k, name, units)] in PGB order; PGB numbering is 1-based and matches the .out columns."""
    rows = []
    for line in open(path, encoding="latin-1"):
        m = _INF.search(line)
        if m:
            rows.append((int(m.group(1)), m.group(2).strip(), m.group(3)))
    return sorted(rows)


def _read_out(path):
    # first line is the run title in some versions; skip any line that does not parse as numbers
    data = []
    for line in open(path, encoding="latin-1"):
        parts = line.split()
        try:
            data.append([float(p) for p in parts])
        except ValueError:
            continue
    return np.array(data)


def read_case(out_dir, case):
    """All channels of one run: dict(t, ch={name: array}, units={name: str}, fs)."""
    chans = read_inf(os.path.join(out_dir, case + ".inf"))
    files = sorted(glob.glob(os.path.join(out_dir, case + "_[0-9][0-9].out")))
    if not files:
        raise FileNotFoundError(f"no {case}_NN.out in {out_dir}: was 'save channels to disk' (PlotType=OUT) on?")
    blocks = [_read_out(f) for f in files]
    n = min(len(b) for b in blocks)
    t = blocks[0][:n, 0]
    cols = np.hstack([b[:n, 1:] for b in blocks])
    if cols.shape[1] < len(chans):
        raise ValueError(f"{cols.shape[1]} data columns for {len(chans)} channels in {case}.inf")
    ch, units = {}, {}
    for j, (_, name, u) in enumerate(chans):
        key = name if name not in ch else f"{name}_{j + 1}"
        ch[key], units[key] = cols[:, j], u
    return dict(t=t, ch=ch, units=units, fs=1.0 / np.median(np.diff(t)))


def line_constants(path):
    """Whole-line positive- and zero-sequence series impedance (ohms) from a LCP .out file,
    the plain (not long-line corrected) values, which are what a distance relay is set with."""
    txt = open(path, encoding="latin-1").read()
    # some cases print per unit ("Base of Per-Unit Quantities : 230.00 kV (L-L) ,100.00 MVA")
    base = re.search(r"Base of Per-Unit Quantities\s*:\s*([\d.]+)\s*kV.*?,\s*([\d.]+)\s*MVA", txt)
    zbase = float(base.group(1)) ** 2 / float(base.group(2)) if base else None
    blocks = re.split(r"\n\s*(Positive Sequence|Zero Sequence)\s*(\(Long-Line Corrected\))?\s*\n", txt)
    found = {}
    for i in range(1, len(blocks) - 2, 3):
        kind, corrected, body = blocks[i], blocks[i + 1], blocks[i + 2]
        if corrected:
            continue
        m_r = re.search(r"Rsq\s+\[(Ohms|pu)\]:\s*([-\d.Ee+]+)", body)
        m_x = re.search(r"Xsq\s+\[(Ohms|pu)\]:\s*([-\d.Ee+]+)", body)
        scale = 1.0
        if m_r.group(1) == "pu":
            if zbase is None:
                raise ValueError(f"{path}: per-unit values without a stated base")
            scale = zbase
        found["z1" if kind.startswith("Positive") else "z0"] = complex(float(m_r.group(2)), float(m_x.group(2))) * scale
    m = re.search(r"@\s*([\d.]+)\s*Hz", txt)
    found["f"] = float(m.group(1)) if m else None
    return found
