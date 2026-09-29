"""Build the adapt_grid-CigreMVGrid cache: one streaming pass over the archive, EVERY measurement cubicle.

The 20 kV CIGRE MV grid is the EvEMTBench grid where inverters are the only generator type (about 20 % of
buses), i.e. the closest public data to the inverter-dominated case the project is about. Which lines to
use as relays is decided afterwards, from the grid graph and the inverters' share of fault current, so all
cubicles are cached now and the 68 GB archive is read exactly once (evemt.build_cache_disk streams it,
never unpacks it). The cache goes to D: (about 0.75 GB per cubicle for ~9,700 simulations; the system
drive and the OneDrive-synced repository have no room for it).

    python src/build_cigremv_cache.py [archive] [out_base]
    defaults: D:/evemt/adapt_grid-CigreMVGrid.tar.gz  ->  D:/evemt/cache/adapt_grid-CigreMVGrid_cache.{bin,meta.npz}
"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evemt import build_cache_disk, list_cubicles

ARC = sys.argv[1] if len(sys.argv) > 1 else r"D:\evemt\adapt_grid-CigreMVGrid.tar.gz"
OUT = sys.argv[2] if len(sys.argv) > 2 else r"D:\evemt\cache\adapt_grid-CigreMVGrid_cache"

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cubicles = list_cubicles(ARC)
    print(f"{len(cubicles)} cubicles:", cubicles, flush=True)
    t0 = time.time()
    meta = build_cache_disk(ARC, cubicles, fn=50, out=OUT)
    print(f"DONE {meta}  wall {time.time()-t0:.0f}s", flush=True)
