"""Focused benchmark: what actually costs time in a numpy block FDN, and how
to vectorise the per-delay-line one-pole damping recursion.

Findings to verify:
  1. block size must be <= min(delay-line length) or the read wraps twice.
  2. a naive Python `for t in range(block)` damping recursion dominates cost.
  3. the same one-pole can be evaluated in closed form per block (geometric
     prefix sum) -> fully vectorised.
  4. generating the IR once + FFT convolution beats running the FDN online.
"""
import time
import numpy as np

FS = 44100
DUR = 3.0
N = int(FS * DUR)
RT60 = 3.0
DAMP = 0.25

DELAYS = np.array([997, 1153, 1327, 1499, 1657, 1783, 1949, 2081,
                   2203, 2341, 2477, 2593, 2711, 2837, 2963, 3109], dtype=np.int64)
G = 10.0 ** (-3.0 * DELAYS / (RT60 * FS))

x = np.zeros(N)
x[0] = 1.0


def hadamard(n):
    H = np.array([[1.0]])
    while H.shape[0] < n:
        H = np.block([[H, H], [H, -H]])
    return H


def timeit(fn, *a, **kw):
    t0 = time.perf_counter()
    r = fn(*a, **kw)
    return time.perf_counter() - t0, r


# ---------------------------------------------------------------- variants
def fdn_no_damp(x, delays, g, block, H, nl):
    bufs = [np.zeros(int(d)) for d in delays]
    w = [0] * nl
    out = np.empty(len(x))
    for s in range(0, len(x), block):
        e = min(s + block, len(x)); bs = e - s
        taps = np.empty((nl, bs))
        for j in range(nl):
            d = len(bufs[j]); wi = w[j]
            if wi + bs <= d:
                taps[j] = bufs[j][wi:wi + bs]
            else:
                k = d - wi
                taps[j, :k] = bufs[j][wi:]; taps[j, k:] = bufs[j][:bs - k]
        mix = H @ taps
        inj = x[s:e] / nl + mix * g[:, None]
        for j in range(nl):
            d = len(bufs[j]); wi = w[j]
            if wi + bs <= d:
                bufs[j][wi:wi + bs] = inj[j]
            else:
                k = d - wi
                bufs[j][wi:] = inj[j, :k]; bufs[j][:bs - k] = inj[j, k:]
            w[j] = (wi + bs) % d
        out[s:e] = taps.sum(axis=0) / nl
    return out


def fdn_py_damp(x, delays, g, block, H, nl):
    """Damping applied with a Python loop over the block (the slow way)."""
    bufs = [np.zeros(int(d)) for d in delays]
    w = [0] * nl
    lp = np.zeros(nl)
    out = np.empty(len(x))
    for s in range(0, len(x), block):
        e = min(s + block, len(x)); bs = e - s
        taps = np.empty((nl, bs))
        for j in range(nl):
            d = len(bufs[j]); wi = w[j]
            if wi + bs <= d:
                taps[j] = bufs[j][wi:wi + bs]
            else:
                k = d - wi
                taps[j, :k] = bufs[j][wi:]; taps[j, k:] = bufs[j][:bs - k]
        mix = H @ taps
        lpc = np.empty_like(mix)
        for t in range(bs):
            lp = (1.0 - DAMP) * mix[:, t] + DAMP * lp
            lpc[:, t] = lp
        inj = x[s:e] / nl + lpc * g[:, None]
        for j in range(nl):
            d = len(bufs[j]); wi = w[j]
            if wi + bs <= d:
                bufs[j][wi:wi + bs] = inj[j]
            else:
                k = d - wi
                bufs[j][wi:] = inj[j, :k]; bufs[j][:bs - k] = inj[j, k:]
            w[j] = (wi + bs) % d
        out[s:e] = taps.sum(axis=0) / nl
    return out


def onepole_block(mix, d, state):
    """Vectorised one-pole lowpass over the last axis of `mix` (nl, bs).

    y[n] = d*y[n-1] + (1-d)*x[n],  y[-1] = state
    closed form: y[n] = d**(n+1)*state + (1-d)*d**n * cumsum(x[k]*d**-k)
    """
    nl, bs = mix.shape
    n = np.arange(bs)
    dpow = d ** n                     # d^n
    inv = 1.0 / dpow                  # d^-n
    cs = np.cumsum(mix * inv, axis=1)  # sum_{k<=n} x[k] d^-k
    y = (1.0 - d) * dpow * cs + (d ** (n + 1)) * state[:, None]
    new_state = y[:, -1]
    return y, new_state


def fdn_vec_damp(x, delays, g, block, H, nl):
    """Damping evaluated with the closed-form geometric prefix sum."""
    bufs = [np.zeros(int(d)) for d in delays]
    w = [0] * nl
    lp = np.zeros(nl)
    out = np.empty(len(x))
    for s in range(0, len(x), block):
        e = min(s + block, len(x)); bs = e - s
        taps = np.empty((nl, bs))
        for j in range(nl):
            d = len(bufs[j]); wi = w[j]
            if wi + bs <= d:
                taps[j] = bufs[j][wi:wi + bs]
            else:
                k = d - wi
                taps[j, :k] = bufs[j][wi:]; taps[j, k:] = bufs[j][:bs - k]
        mix = H @ taps
        lpc, lp = onepole_block(mix, DAMP, lp)
        inj = x[s:e] / nl + lpc * g[:, None]
        for j in range(nl):
            d = len(bufs[j]); wi = w[j]
            if wi + bs <= d:
                bufs[j][wi:wi + bs] = inj[j]
            else:
                k = d - wi
                bufs[j][wi:] = inj[j, :k]; bufs[j][:bs - k] = inj[j, k:]
            w[j] = (wi + bs) % d
        out[s:e] = taps.sum(axis=0) / nl
    return out


def fdn_band_gain(x, delays, g, block, H, nl):
    """No per-sample damping at all: one scalar gain per line. Fastest."""
    bufs = [np.zeros(int(d)) for d in delays]
    w = [0] * nl
    out = np.empty(len(x))
    for s in range(0, len(x), block):
        e = min(s + block, len(x)); bs = e - s
        taps = np.empty((nl, bs))
        for j in range(nl):
            d = len(bufs[j]); wi = w[j]
            if wi + bs <= d:
                taps[j] = bufs[j][wi:wi + bs]
            else:
                k = d - wi
                taps[j, :k] = bufs[j][wi:]; taps[j, k:] = bufs[j][:bs - k]
        inj = x[s:e] / nl + (H @ taps) * g[:, None]
        for j in range(nl):
            d = len(bufs[j]); wi = w[j]
            if wi + bs <= d:
                bufs[j][wi:wi + bs] = inj[j]
            else:
                k = d - wi
                bufs[j][wi:] = inj[j, :k]; bufs[j][:bs - k] = inj[j, k:]
            w[j] = (wi + bs) % d
        out[s:e] = taps.sum(axis=0) / nl
    return out


if __name__ == "__main__":
    print(f"numpy {np.__version__} | {N} samples = {DUR}s @ {FS} Hz | min delay "
          f"{DELAYS.min()} samples ({DELAYS.min()/FS*1000:.1f} ms)")
    print()
    for nl in (8, 16):
        d = DELAYS[:nl]
        g = G[:nl]
        H = hadamard(nl) / np.sqrt(nl)
        print(f"--- N={nl} delay lines ---")
        for name, fn in (("no damping      ", fdn_no_damp),
                         ("Python-loop damp", fdn_py_damp),
                         ("vectorised damp ", fdn_vec_damp),
                         ("per-line gain   ", fdn_band_gain)):
            for B in (64, 256):
                t, _ = timeit(fn, x, d, g, B, H, nl)
                print(f"  {name} B={B:4d}: {t:6.3f}s  ({N/t/1e3:7.1f} ksamples/s)")
        print()

    # correctness of the closed-form one-pole vs the recursion
    rng = np.random.default_rng(0)
    mix = rng.standard_normal((4, 37))
    st = rng.standard_normal(4)
    ref = np.empty_like(mix)
    s = st.copy()
    for t in range(mix.shape[1]):
        s = (1 - DAMP) * mix[:, t] + DAMP * s
        ref[:, t] = s
    got, _ = onepole_block(mix, DAMP, st)
    print("one-pole closed form max abs err vs recursion:",
          np.max(np.abs(got - ref)))

    # IR + FFT convolution
    H8 = hadamard(8) / np.sqrt(8)
    t_ir, ir = timeit(fdn_vec_damp, x, DELAYS[:8], G[:8], 64, H8, 8)
    sig = rng.standard_normal(FS * 10)
    t0 = time.perf_counter()
    nfft = 1 << int(np.ceil(np.log2(len(sig) + len(ir) - 1)))
    np.fft.irfft(np.fft.rfft(sig, nfft) * np.fft.rfft(ir, nfft))[: len(sig)]
    t1 = time.perf_counter()
    print(f"\nIR generation (3 s tail): {t_ir:.3f}s")
    print(f"FFT-convolve a 10 s signal with that IR: {t1-t0:.3f}s")
    print(f"=> total for a 10 s file: {t_ir + t1 - t0:.3f}s")
    print(f"   vs running the FDN over 10 s = {t_ir * 10/3:.3f}s")

    # measured decay
    env = np.abs(ir)
    edc = np.cumsum(env[::-1] ** 2)[::-1]
    edc_db = 10 * np.log10(np.maximum(edc, 1e-300) / edc[0])
    hit = np.argmax(edc_db <= -60) if (edc_db <= -60).any() else len(edc_db) - 1
    print(f"\nmeasured T60 from EDC (-60 dB) = {hit/FS:.2f}s "
          f"(requested {RT60}s; damping={DAMP} shortens HF so EDC T60 is shorter)")
