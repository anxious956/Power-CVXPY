"""The CNN helpers give identical scores for an identical seed (src/torch_det.py).

    python -m pytest tests/test_torch_det.py -q
"""
import os, sys
import numpy as np
import pytest

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC)
torch = pytest.importorskip("torch")

from torch_det import time_mean
from review import q3_inputs as q3


def test_time_mean_equals_adaptive_pool_and_flatten():
    x = torch.randn(5, 7, 11)
    ref = torch.nn.Sequential(torch.nn.AdaptiveAvgPool1d(1), torch.nn.Flatten())(x)
    assert torch.allclose(time_mean()(x), ref, atol=1e-6)


def test_cnn_scores_repeat_bit_for_bit():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, (160, 24, 10)).astype(np.float32)
    y = (rng.random(160) < 0.3).astype(int)
    X[y == 1, :3] += 0.8
    a = q3.cnn_scores(X[:120], y[:120], [X[120:]], seed=3, epochs=3)[0]
    b = q3.cnn_scores(X[:120], y[:120], [X[120:]], seed=3, epochs=3)[0]
    c = q3.cnn_scores(X[:120], y[:120], [X[120:]], seed=4, epochs=3)[0]
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
