"""Build the adapt_grid-TestGrid110kV cache: one streaming pass over the archive on D:, cache
written under data/ on the system drive. The archive is never unpacked (evemt.build_cache_disk
streams the .tar.gz), and it is read exactly once.

Same 7 cubicles as the benchmark TestGrid110kV cache (2 relays, 3 line ends, 2 IBRs) of the
grid's 25, so every existing script sees an identical layout. Result, 17 Sep 2026: 9,739
simulations, 5.24 GB, 2,020 s wall on the shared laptop.

    python src/build_adaptgrid_cache.py [archive]      (default D:\evemt\adapt_grid-TestGrid110kV.tar.gz)
"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import numpy as np
from evemt import build_cache_disk

ARC = sys.argv[1] if len(sys.argv) > 1 else r"D:\evemt\adapt_grid-TestGrid110kV.tar.gz"
OUT = os.path.join(ROOT, "data", "adapt_grid-TestGrid110kV_cache")

if __name__ == "__main__":
    z = np.load(os.path.join(ROOT, "data", "benchmark-TestGrid110kV_cache.meta.npz"), allow_pickle=False)
    cubicles = [str(c) for c in z["cubicles"]]
    print("cubicles:", cubicles, flush=True)
    t0 = time.time()
    meta = build_cache_disk(ARC, cubicles, fn=50, out=OUT)
    print(f"DONE {meta}  wall {time.time()-t0:.0f}s", flush=True)
