"""Decision latency of the adapt_grid sequence-trajectory CNN: can it run inside a relay's decision budget?

Times, per single decision (batch of one, as a relay decides), on real adapt_grid records at the relay front
end:
  features   phase selection for the canonical rotation, the rotation, the mimic filter and the ten
             sequence-phasor frames of q3_inputs.seq_traj (the CNN's whole input pipeline)
  cnn        one forward pass of the q3_inputs.cnn_scores network (24 x 10 input), CPU and, if present, GPU
  total      features + CNN on CPU
Weights do not change the arithmetic, so the network is timed with the architecture's initial weights.
Reported as median, 95th and 99th percentile over many repeats after a warm-up, with the machine's CPU and
GPU names; a relay's budget for a 20 ms decision is the time left after the window closes, so these numbers
are compared with one sampling interval at 6.4 kHz (156 us) and with the 1.25 ms of a quarter cycle.
This is a desktop Python measurement, not an embedded one: it bounds the arithmetic, not a relay firmware.

    python src/review/cnn_latency.py
    -> results/adaptgrid/cnn_latency.json
"""
import os, sys, json, time, platform
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from torch_det import seed_everything, time_mean
from review import common as cm
from review import frontend
from review import q3_inputs as q3
from review.zone_cv import zone_task
from review.adaptgrid_run import bundle

OUT = os.path.join(cm.ROOT, "results", "adaptgrid")


def pct(t):
    t = np.asarray(t) * 1e6
    return dict(median_us=float(np.median(t)), p95_us=float(np.percentile(t, 95)), p99_us=float(np.percentile(t, 99)),
                n=int(len(t)))


def net(C=24, dev="cpu"):
    import torch.nn as nn
    k1 = 3
    return nn.Sequential(nn.Conv1d(C, 32, k1, padding=k1 // 2), nn.ReLU(), nn.Conv1d(32, 32, k1, padding=k1 // 2), nn.ReLU(),
                         time_mean(), nn.Dropout(0.2), nn.Linear(32, 1)).to(dev).eval()


def time_features(R, rows):
    out = []
    for r in rows:
        sel = np.array([r])
        t0 = time.perf_counter()
        rot = q3.rotation_index(R, sel)
        Rc, cidx = q3.rotated(R, sel, rot)
        Rc["ev"] = R["ev"]
        x = q3.seq_traj(Rc, cidx)
        out.append(time.perf_counter() - t0)
    return out, x


def time_cnn(x, dev, repeats=2000, warm=200):
    import torch
    m = net(x.shape[1], dev)
    xt = torch.tensor(x, dtype=torch.float32, device=dev)
    ts = []
    with torch.no_grad():
        for i in range(warm + repeats):
            if dev == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            y = m(xt)
            if dev == "cuda":
                torch.cuda.synchronize()
            if i >= warm:
                ts.append(time.perf_counter() - t0)
    return ts


def main():
    import torch
    seed_everything(0)
    frontend.enable()
    R = bundle("adapt_A", None)
    idx, y, _ = zone_task(R)
    rows = idx[np.random.default_rng(0).choice(len(idx), 300, replace=False)]
    ft, x = time_features(R, rows[:50])                      # warm-up pass
    ft, x = time_features(R, rows)
    torch.set_num_threads(1)                                 # one core, as a relay would dedicate
    cpu1 = time_cnn(x, "cpu")
    torch.set_num_threads(os.cpu_count() or 1)
    res = dict(script="cnn_latency", commit=cm.git_commit(), relay="adapt_A", frontend="relayfe",
               machine=dict(cpu=platform.processor(), cores=os.cpu_count(), python=platform.python_version(),
                            torch=torch.__version__,
                            gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None),
               input_shape=list(x.shape[1:]),
               n_parameters=int(sum(p.numel() for p in net(x.shape[1]).parameters())),
               features_cpu=pct(ft), cnn_cpu_one_thread=pct(cpu1))
    if torch.cuda.is_available():
        res["cnn_gpu"] = pct(time_cnn(x, "cuda"))
    res["total_cpu_median_us"] = res["features_cpu"]["median_us"] + res["cnn_cpu_one_thread"]["median_us"]
    res["reference_us"] = dict(one_sample_6400Hz=1e6 / 6400, quarter_cycle_50Hz=5000.0 / 4)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "cnn_latency.json")
    json.dump(res, open(path, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("machine",)}, indent=1))
    print("machine", res["machine"])
    print("saved", path)


if __name__ == "__main__":
    main()
