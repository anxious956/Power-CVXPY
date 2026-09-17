"""
Loader for the EvEMTBench dataset (Kordowich et al., FAU Erlangen-Nuernberg).

Reads waveforms straight out of the .tar.gz archive in one streaming pass, without unpacking
it (the archives are 2 to 146 GB and unpack to roughly three times that), keeps only the
measurement cubicles asked for, resamples to 128 samples per nominal cycle so every function
in waveforms.py and the detectors works unchanged, and caches the result as a compressed
.npz next to the archive. Every later experiment reads the cache in seconds.

Archive layout, per the dataset paper and verified on benchmark-DoubleLine:
    <Grid>/data/result<k>.csv        two-row header: (cubicle, quantity); 0.5 s at 9600 Hz,
                                     t = 1.0 .. 1.5 s, primary V and A
    <Grid>/labels/settings_clean.csv one row per simulation; event starts at 1.1 s
    <Grid>/graphs/graph_benchmark.pickle  networkx graph with line and transformer data

  python src/evemt.py cubicles  data/benchmark-DoubleLine.tar.gz
  python src/evemt.py cache     data/benchmark-DoubleLine.tar.gz  "Cub_2\\pex_MainBus1_MainLn1-2A" ...
"""
import io, os, sys, tarfile, time, pickle
import numpy as np
import pandas as pd
from scipy.signal import resample_poly

FS_RAW = 9600
T0 = 1.0                 # first sample time in every result file
EVENT_T = 1.1            # event inception, identical for every simulation
SAMPLES_PER_CYCLE = 128
CHANNELS = ["c:Usec:A in V", "c:Usec:B in V", "c:Usec:C in V",
            "c:Isec:A in A", "c:Isec:B in A", "c:Isec:C in A"]


def _members(path):
    """Stream the archive once; yield (name, bytes) for every regular file."""
    with tarfile.open(path, mode="r|gz") as tf:
        for m in tf:
            if m.isfile():
                yield m.name, tf.extractfile(m).read()


def list_cubicles(path):
    for name, raw in _members(path):
        if "/data/result" in name and name.endswith(".csv"):
            head = pd.read_csv(io.BytesIO(raw), header=[0, 1], nrows=1)
            return sorted({c[0] for c in head.columns if c[0] != "EvemtResult"})


def _resample_factors(fn):
    """9600 Hz -> 128 samples per cycle. 50 Hz: 6400 Hz (2/3). 60 Hz: 7680 Hz (4/5)."""
    return {50: (2, 3), 60: (4, 5)}[int(fn)]


def build_cache(path, cubicles, fn=None, out=None, verbose=True):
    """One streaming pass over the archive. Returns the cache path.

    Cache contents:
        x        float32 (n_sims, n_cubicles, 6, n_samples)  [va vb vc ia ib ic], primary units
        files    result file names, aligned with x
        cubicles the cubicle names, aligned with axis 1
        fs, event_index, samples_per_cycle
        labels   settings_clean.csv as bytes (read with pd.read_csv(io.BytesIO(...)))
        graph    the grid graph pickle as bytes
    """
    out = out or os.path.splitext(os.path.splitext(path)[0])[0] + "_cache.npz"
    arrays, files, labels_raw, graph_raw = [], [], None, None
    t0 = time.time()
    n = 0
    up = down = None
    for name, raw in _members(path):
        if name.endswith("labels/settings_clean.csv"):
            labels_raw = raw
            continue
        if name.endswith(".pickle") and "/graphs/" in name:
            graph_raw = raw
            continue
        if "/data/result" not in name or not name.endswith(".csv"):
            continue
        df = pd.read_csv(io.BytesIO(raw), header=[0, 1], low_memory=False)
        if up is None:
            if fn is None:
                fn = 50   # confirmed later against the labels; the files carry no frequency
            up, down = _resample_factors(fn)
        block = []
        for c in cubicles:
            sig = df[c][CHANNELS].to_numpy(dtype=np.float64).T          # (6, 4801)
            block.append(resample_poly(sig, up, down, axis=1).astype(np.float32))
        arrays.append(np.stack(block))
        files.append(name.rsplit("/", 1)[-1])
        n += 1
        if verbose and n % 100 == 0:
            print(f"  {n} simulations  [{time.time()-t0:.0f}s]", flush=True)

    if labels_raw is not None:
        L = pd.read_csv(io.BytesIO(labels_raw))
        fns = L["general/fn"].unique()
        if len(fns) == 1 and int(fns[0]) != fn:
            raise RuntimeError(f"labels say {fns[0]} Hz but cache was built at {fn} Hz; rerun with fn={fns[0]}")
    fs = FS_RAW * up / down
    x = np.stack(arrays)
    np.savez_compressed(out, x=x, files=np.array(files), cubicles=np.array(cubicles),
                        fs=fs, event_index=int(round((EVENT_T - T0) * fs)),
                        samples_per_cycle=SAMPLES_PER_CYCLE,
                        labels=np.frombuffer(labels_raw or b"", dtype=np.uint8),
                        graph=np.frombuffer(graph_raw or b"", dtype=np.uint8))
    if verbose:
        print(f"cached {x.shape} at {fs:.0f} Hz -> {out}  [{time.time()-t0:.0f}s, "
              f"{os.path.getsize(out)/1e6:.0f} MB]")
    return out


def build_cache_disk(path, cubicles, fn=50, out=None, verbose=True):
    """Same as build_cache, but writes each simulation to disk as it is read, so memory stays
    flat however large the archive is. Produces <out>.bin (raw float32, C order,
    (n_sims, n_cubicles, 6, n_samples)) and <out>.meta.npz with everything else.
    load_cache accepts the .meta.npz path."""
    base = out or os.path.splitext(os.path.splitext(path)[0])[0] + "_cache"
    bin_path, meta_path = base + ".bin", base + ".meta.npz"
    up, down = _resample_factors(fn)
    files, labels_raw, graph_raw, n_samples = [], None, None, None
    t0 = time.time()
    with open(bin_path, "wb") as fbin:
        for name, raw in _members(path):
            if name.endswith("labels/settings_clean.csv"):
                labels_raw = raw
                continue
            if name.endswith(".pickle") and "/graphs/" in name:
                graph_raw = raw
                continue
            if "/data/result" not in name or not name.endswith(".csv"):
                continue
            df = pd.read_csv(io.BytesIO(raw), header=[0, 1], low_memory=False)
            block = np.stack([resample_poly(df[c][CHANNELS].to_numpy(dtype=np.float64).T, up, down, axis=1)
                              for c in cubicles]).astype(np.float32)
            if n_samples is None:
                n_samples = block.shape[-1]
            if block.shape[-1] != n_samples:
                raise RuntimeError(f"{name}: {block.shape[-1]} samples, expected {n_samples}")
            fbin.write(np.ascontiguousarray(block).tobytes())
            files.append(name.rsplit("/", 1)[-1])
            if verbose and len(files) % 200 == 0:
                print(f"  {len(files)} simulations  [{time.time()-t0:.0f}s]", flush=True)
    if labels_raw is not None:
        fns = pd.read_csv(io.BytesIO(labels_raw))["general/fn"].unique()
        if len(fns) == 1 and int(fns[0]) != fn:
            raise RuntimeError(f"labels say {fns[0]} Hz but cache was built at {fn} Hz")
    fs = FS_RAW * up / down
    np.savez_compressed(meta_path, bin=os.path.basename(bin_path),
                        shape=np.array([len(files), len(cubicles), 6, n_samples]),
                        files=np.array(files), cubicles=np.array(cubicles), fs=fs,
                        event_index=int(round((EVENT_T - T0) * fs)), samples_per_cycle=SAMPLES_PER_CYCLE,
                        labels=np.frombuffer(labels_raw or b"", dtype=np.uint8),
                        graph=np.frombuffer(graph_raw or b"", dtype=np.uint8))
    if verbose:
        print(f"cached ({len(files)}, {len(cubicles)}, 6, {n_samples}) at {fs:.0f} Hz -> {bin_path}  "
              f"[{time.time()-t0:.0f}s, {os.path.getsize(bin_path)/1e9:.2f} GB]")
    return meta_path


def load_cache(path):
    if path.endswith(".meta.npz"):
        z = np.load(path, allow_pickle=False)
        shape = tuple(int(s) for s in z["shape"])
        x = np.memmap(os.path.join(os.path.dirname(path), str(z["bin"])), dtype=np.float32, mode="r", shape=shape)
        labels = pd.read_csv(io.BytesIO(z["labels"].tobytes()))
        labels["file"] = labels["general/result_file_path"].str.replace("\\", "/", regex=False).str.rsplit("/", n=1).str[-1]
        labels = labels.set_index("file").loc[list(z["files"])].reset_index()
        graph = pickle.loads(z["graph"].tobytes()) if z["graph"].size else None
        return dict(x=x, files=list(z["files"]), cubicles=list(z["cubicles"]), fs=float(z["fs"]),
                    event_index=int(z["event_index"]), samples_per_cycle=int(z["samples_per_cycle"]),
                    labels=labels, graph=graph)
    z = np.load(path, allow_pickle=False)
    labels = pd.read_csv(io.BytesIO(z["labels"].tobytes()))
    labels["file"] = labels["general/result_file_path"].str.replace("\\", "/", regex=False).str.rsplit("/", n=1).str[-1]
    labels = labels.set_index("file").loc[list(z["files"])].reset_index()
    graph = pickle.loads(z["graph"].tobytes()) if z["graph"].size else None
    return dict(x=z["x"], files=list(z["files"]), cubicles=list(z["cubicles"]),
                fs=float(z["fs"]), event_index=int(z["event_index"]),
                samples_per_cycle=int(z["samples_per_cycle"]), labels=labels, graph=graph)


def line_params(graph, line):
    """Per-km positive and zero sequence impedance of a line, from the grid graph."""
    for u, v, k, d in graph.edges(keys=True, data=True):
        if k == line:
            p = d[f"{line}_param_dict"]
            return dict(z1=complex(p["rline"], p["xline"]), z0=complex(p["rline0"], p["xline0"]),
                        length_km=float(p["length"]))
    raise KeyError(line)


def window(x, event_index, cycles_before=4, cycles_after=4, spc=SAMPLES_PER_CYCLE):
    """Cut the record so the event sits at sample 4*spc of an 8-cycle window, which is the
    layout waveforms.py and the detectors assume."""
    a = event_index - cycles_before * spc
    return x[..., a:a + (cycles_before + cycles_after) * spc]


if __name__ == "__main__":
    cmd, arc = sys.argv[1], sys.argv[2]
    if cmd == "cubicles":
        for c in list_cubicles(arc):
            print(c)
    elif cmd == "cache":
        build_cache(arc, sys.argv[3:])
    elif cmd == "cache-disk":
        build_cache_disk(arc, sys.argv[3:])
    else:
        raise SystemExit(__doc__)
