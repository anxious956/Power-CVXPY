"""Deterministic torch set-up for the three small CNNs (detect.py, review/h19_verify.py, review/q3_inputs.py).

With a fixed seed alone, two GPU runs of the same CNN differ in the last bits: cuDNN picks non-deterministic
convolution backward kernels by default and adaptive average pooling has no deterministic CUDA backward. At a
zero-false-trip threshold (the largest out-of-fold score among the training negatives) those bits move
dependability by several points, so a single seed's number did not reproduce. seed_everything() makes the
same seed give the same scores on the same machine; time_mean() replaces AdaptiveAvgPool1d(1) + Flatten,
which it equals exactly, with a plain mean whose backward is deterministic. Results still differ between a
GPU and a CPU run, and between GPU models or driver versions.

Import this module before torch initialises CUDA: cuBLAS reads CUBLAS_WORKSPACE_CONFIG at context creation.
"""
import os
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")


def seed_everything(seed):
    """Seed torch (CPU and every GPU) and switch every op to its deterministic implementation. Numpy's global
    RNG is left alone: callers that relied on it seed it themselves."""
    import torch
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True)


def time_mean():
    """(N, C, T) -> (N, C): the mean over time, i.e. AdaptiveAvgPool1d(1) followed by Flatten."""
    import torch.nn as nn

    class TimeMean(nn.Module):
        def forward(self, x):
            return x.mean(dim=-1)

    return TimeMean()
