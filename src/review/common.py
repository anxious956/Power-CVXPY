"""Shared helpers for the synthetic-pipeline review scripts (src/review/*.py).

ORIGINAL reproduces the pipeline at commit 321e12b; FIXED is every correction applied.
Each review script passes a cfg explicitly, so re-running an old script after later fixes
still measures what it says it measures.
"""
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, SRC)
OUT = os.path.join(SRC, "..", "results", "review_synth")
os.makedirs(OUT, exist_ok=True)

ORIGINAL = dict(polarity="test")
FIXED = dict(polarity="train")


def design_direction():
    with open(os.path.join(SRC, "..", "results", "aux_signal_toy_weak_sg.json")) as f:
        o = json.load(f)["cvxpy_opt"]
    d = complex(o[0], o[1])
    return d / abs(d)


def save(name, obj):
    path = os.path.join(OUT, name)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=float)
    print("saved", os.path.relpath(path))
