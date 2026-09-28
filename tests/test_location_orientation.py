"""The zone labels measure fault location from the relay (common.load_relay_adapt, loc_rel).

EvEMTBench records a line fault's location from the line's first graph node. Before 28 Sep 2026 the adapt_grid
labels used that number directly, which mirrored the zone of relays at a line's second node (cigre_R1, cigre_R3).
The physical check here would have caught it: on the same fault, the end nearer the fault sees the deeper
voltage dip, so the relay-minus-remote dip difference must grow with loc_rel. Needs the relay caches (skipped
without them; the CIGRE cache is found through EVEMT_CACHE_DIRS).

    python -m pytest tests/test_location_orientation.py -q
"""
import os, sys
import numpy as np
import pytest

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC)

from review import common as cm

RELAYS = ("adapt_A", "adapt_B", "cigre_R1", "cigre_R2", "cigre_R3", "cigre_R4")


def _available(name):
    try:
        cm._cache(cm.CONFIGS[name])
        return True
    except Exception:
        return False


@pytest.mark.parametrize("name", RELAYS)
def test_zone_is_measured_from_the_relay(name):
    if not _available(name):
        pytest.skip(f"cache for {name} not found")
    R = cm.load_relay(name, None)
    Rr = cm.load_relay(name, None, cubicle=R["cfg"]["remote_cubicle"])
    m = np.where((np.char.find(R["et"], "shc") >= 0) & (R["tgt"] == R["cfg"]["line"]) & (R["rf"] < 15))[0]
    dip = lambda X: (lambda p: np.abs(p[1][:, 1]) / np.abs(p[0][:, 1]))(cm.phasors_at(X, m, 20))
    d = dip(R) - dip(Rr)                     # grows as the fault moves away from the relay
    assert np.corrcoef(R["loc_rel"][m], d)[0, 1] > 0.3
    assert np.all(R["loc_rel"][R["pos"]] <= 85.0) and np.all(R["loc_rel"][R["own99"]] > 85.0)
