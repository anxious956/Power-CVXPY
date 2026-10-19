"""
The two-frame model (src/frames.py) with several V1-referenced current sources: the injecting inverter (the box of
the source symbols, delta) plus fixed-command sinks, inverter-interfaced loads that draw a set current in their own
V1 frame (docs/I2_DIRECTION.md, stage b). Each source's frame follows its own bus V1; the fixed point runs over all
frames together. The frame symbols lam (the move from the pre-fault to the fault frame through the relay window) and
drift are shared by all frames: identical PLL-like reference filters, one inception, one frequency.

Sinks carry no box symbols, like the impedance loads; their commands come from the all-impedance operating point the
EMT runs use (i2dir_static.operating_point). The source inverter's command box is the network's own box for it,
rotated into its frame at the nominal point of the all-impedance base network, so that at S = 0 the command equals the
EMT setting. With no sinks the class reduces to frames.FrameModel (regression: tests below and src/i2dir_design.py).
"""
import numpy as np
import network as nw
import frames as fr


def unit_maps_multi(net, inj, sinks, fault):
    """y = My @ [e, i1, d, i_sink...]; V1 at each source's bus = mv[name] @ [...] (names: inj and the sinks)."""
    (sg,) = list(net.sgs)
    zero = {k: 0.0 for k in list(net.sgs) + list(net.ibrs)}
    cols = [("e", sg), ("i1", inj), ("d", inj)] + [("i1", s) for s in sinks]
    cy, cv = [], {k: [] for k in [inj] + list(sinks)}
    for kind, name in cols:
        vals, dels = dict(zero), {}
        if kind == "d":
            dels[name] = 1.0
        else:
            vals[name] = 1.0
        y, V = nw.solve(net, vals, dels, fault, full=True)
        cy.append(y)
        for k in cv:
            cv[k].append(V[net.ibrs[k].bus][0])
    return np.stack(cy, 1), {k: np.array(v) for k, v in cv.items()}


class FrameModelMulti(fr.FrameModel):
    def __init__(self, net, cases, sinks=None, base_net=None, **kw):
        """sinks: {ibr name: command in its own frame (complex pu, the current it injects; a load draws: negative
        real part)}. base_net: the all-impedance network whose nominal operating point fixes the source inverter's
        frame rotation (default: net)."""
        super().__init__(net, cases, **kw)
        self.sinks = dict(sinks or {})
        self.maps_N = unit_maps_multi(net, self.inj, self.sinks, None)
        self.maps_F = [unit_maps_multi(net, self.inj, self.sinks, (ln, m, s, mr * net.rF)) for ln, m, s, mr in self.cases]
        b = base_net or net
        _, V = nw.solve(b, {}, {}, None, full=True)
        g = net.ibrs[self.inj]
        self.u_nom = V[g.bus][0] / abs(V[g.bus][0])
        cI, gI = nw.source_set(b, "ibr", self.inj, "outer")
        rot = np.conj(self.u_nom)
        self.cI, self.gI = cI * rot, [x * rot for x in gI]
        self.u_sink0 = {k: V[net.ibrs[k].bus][0] / abs(V[net.ibrs[k].bus][0]) for k in self.sinks}

    # ---------------------------------------------------------------- the fixed point over all frames
    def _x(self, e, i_cmd, d_cmd, u):
        i1, d = fr.limiter_vec(i_cmd * u[self.inj], d_cmd * u[self.inj], self.i_max, self.lim)
        cols = [e, i1, d] + [self.sinks[k] * u[k] for k in self.sinks]
        return np.stack(cols, 1), i1, d

    def _fixed(self, mv, e, i_cmd, d_cmd, u0, tol=1e-12):
        """The fixed point over all frames. Plain iteration first; where it does not converge (a period-2 swing between
        frames), under-relaxed iteration from the same start (as network.solve_v1ref's relax): the relaxation changes
        the path, not the fixed point."""
        for relax, iters in ((1.0, 400), (0.5, 2000), (0.25, 6000)):
            u = {k: v.copy() for k, v in u0.items()}
            for _ in range(iters):
                X, i1, d = self._x(e, i_cmd, d_cmd, u)
                step = 0.0
                for k in u:
                    v = X @ mv[k]
                    new = v / np.maximum(np.abs(v), 1e-12)
                    new = (1 - relax) * u[k] + relax * new
                    new /= np.maximum(np.abs(new), 1e-12)
                    step = max(step, float(np.max(np.abs(new - u[k]))))
                    u[k] = new
                if step < tol:
                    X, i1, d = self._x(e, i_cmd, d_cmd, u)
                    self._v1_last = {k: np.abs(X @ mv[k]) for k in mv}
                    return u, X, np.abs(X @ mv[self.inj])
        raise RuntimeError(f"FrameModelMulti: fixed point not converged even under-relaxed (step {step:.1e})")

    def _u0(self, n):
        u = {self.inj: np.full(n, self.u_nom)}
        u.update({k: np.full(n, v) for k, v in self.u_sink0.items()})
        return u

    def normal_state(self, S, d_cmd):
        e, i_cmd = self.sources(S)
        My, mv = self.maps_N
        u, X, _ = self._fixed(mv, e, i_cmd, d_cmd, self._u0(len(S)))
        y = X @ My.T
        return y, y[:, 0] / np.abs(y[:, 0]), u

    def measure(self, S, d_cmd, case=None, lam=None, drift=None, E=None):
        yN, uL, u_pre = self.normal_state(S, d_cmd)
        if case is None:
            return yN * np.conj(uL)[:, None]
        e, i_cmd = self.sources(S)
        My, mv = self.maps_F[case]
        u_f, _, v1 = self._fixed(mv, e, i_cmd, d_cmd, u_pre)
        lam = np.ones(len(S)) if lam is None else lam
        drift = np.zeros(len(S)) if drift is None else drift
        uu = {}
        for k in u_pre:
            w = (1 - lam) * u_pre[k] + lam * u_f[k]
            uu[k] = w / np.maximum(np.abs(w), 1e-12) * np.exp(1j * self.drift * drift * lam)
        # no usable frame where a source's own bus V1 collapses: any angle, independently per source; the rule is
        # per bus (I and SR share bus R), each source judged on its own bus V1 in the fault
        v1s = self._v1_last
        for k in uu:
            dead = v1s[k] < self.v1_min
            if dead.any():
                uu[k] = uu[k].copy()
                uu[k][dead] = np.exp(1j * self.rng.uniform(0, 2 * np.pi, dead.sum()))
        X, _, _ = self._x(e, i_cmd, d_cmd, uu)
        return (X @ My.T) * np.conj(uL)[:, None]

    def dead_frames(self, d_cmd):
        """Cases where any source's own bus V1 falls below v1_min at some sample point."""
        S = np.vstack(self.samples)
        e, i_cmd = self.sources(S)
        _, _, u_pre = self.normal_state(S, d_cmd)
        out = []
        for k in range(len(self.cases)):
            self._fixed(self.maps_F[k][1], e, i_cmd, d_cmd, u_pre)
            if any((v < self.v1_min).any() for v in self._v1_last.values()):
                out.append(self.cases[k])
        return out
