"""When is the closed-form (geometric prefix-sum) one-pole lowpass safe?

y[n] = d*y[n-1] + (1-d)*x[n],  y[-1] = state
closed form: y[n] = (1-d)*d**n * cumsum(x[k]*d**-k) + d**(n+1)*state

The d**-k factor grows like d**-B, so long blocks with d near 1 lose precision.
This measures the worst-case error vs the exact sample recursion over a grid of
(d, block_size), on random input, and reports the largest safe block size.
"""
import numpy as np

rng = np.random.default_rng(1)


def recursion(mix, d, state):
    nl, bs = mix.shape
    y = np.empty_like(mix)
    s = state.copy()
    for t in range(bs):
        s = d * s + (1.0 - d) * mix[:, t]
        y[:, t] = s
    return y


def closed_form(mix, d, state):
    nl, bs = mix.shape
    n = np.arange(bs)
    dp = d ** n
    cs = np.cumsum(mix / dp, axis=1)
    return (1.0 - d) * dp * cs + (d ** (n + 1)) * state[:, None]


print(f"{'d':>6} {'B':>5} {'max|err|':>12} {'rms(y)':>10} {'rel err':>10} {'d^-B':>10}")
for d in (0.10, 0.30, 0.50, 0.70, 0.85, 0.90, 0.95, 0.99):
    for B in (32, 64, 128, 256, 512, 1024, 2048):
        mix = rng.standard_normal((4, B))
        st = rng.standard_normal(4)
        ref = recursion(mix, d, st)
        got = closed_form(mix, d, st)
        err = np.max(np.abs(got - ref))
        rms = np.sqrt(np.mean(ref**2))
        flag = "" if err / rms < 1e-8 else "   <-- DEGRADED"
        if B in (64, 256, 1024, 2048):
            print(f"{d:6.2f} {B:5d} {err:12.3e} {rms:10.3f} {err/rms:10.2e} "
                  f"{d**-B:10.2e}{flag}")
    print()
