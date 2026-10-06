"""Benchmark: pure-Python sample loop vs numpy block-based FDN reverb.

Measures wall-clock throughput for a 3-second tail at 44.1 kHz,
8 delay lines, per-line one-pole damping, Hadamard feedback matrix.
"""
import time
import numpy as np

FS = 44100
DUR = 3.0
N = int(FS * DUR)          # 132300 samples
LINES = 8
RT60 = 3.0

# Mutually-prime-ish delay lengths in samples (Jot/Schlecht style, ~20-80 ms)
DELAYS = np.array([997, 1153, 1327, 1499, 1657, 1783, 1949, 2081], dtype=np.int64)

# Hadamard 8x8 (Sylvester construction), normalized so it is orthogonal
H = np.array([[1]], dtype=np.float64)
while H.shape[0] < LINES:
    H = np.block([[H, H], [H, -H]])
H = H / np.sqrt(LINES)

# Per-line feedback gain for a target RT60: g = 10^(-3*D/(RT60*fs))
G = 10.0 ** (-3.0 * DELAYS / (RT60 * FS))

# Damping: one-pole lowpass in the feedback path, y = (1-d)*x + d*y_prev
DAMP = 0.25

x = np.zeros(N, dtype=np.float64)
x[0] = 1.0


def pure_python_fdn(x, delays, g, damp):
    """Sample-by-sample FDN with one-pole damping per line."""
    n = len(x)
    nl = len(delays)
    bufs = [np.zeros(int(d), dtype=np.float64) for d in delays]
    idx = [0] * nl
    lp = [0.0] * nl          # one-pole state
    out = np.zeros(n, dtype=np.float64)
    inv = 1.0 / nl
    for i in range(n):
        # read taps
        taps = [0.0] * nl
        for j in range(nl):
            taps[j] = bufs[j][idx[j]]
        # mix (Hadamard via butterfly-free naive matmul on Python lists)
        y = 0.0
        for j in range(nl):
            s = 0.0
            for k in range(nl):
                s += H[j, k] * taps[k]
            lp[j] = (1.0 - damp) * s + damp * lp[j]
            v = lp[j] * g[j]
            bufs[j][idx[j]] = x[i] * inv + v
            idx[j] += 1
            if idx[j] >= len(bufs[j]):
                idx[j] = 0
            y += taps[j]
        out[i] = y * inv
    return out


def numpy_block_fdn(x, delays, g, damp, block=64):
    """Block-based FDN: per block, gather taps -> matmul -> scatter."""
    n = len(x)
    nl = len(delays)
    maxd = int(delays.max())
    # circular buffers, each a flat array of length = its delay
    bufs = [np.zeros(int(d), dtype=np.float64) for d in delays]
    w = [0] * nl                      # write index per line
    lp = np.zeros(nl, dtype=np.float64)
    out = np.zeros(n, dtype=np.float64)
    nomat = block
    for start in range(0, n, block):
        stop = min(start + block, n)
        bs = stop - start
        taps = np.empty((nl, bs), dtype=np.float64)
        for j in range(nl):
            d = len(bufs[j])
            wi = w[j]
            # contiguous read of bs samples with wraparound
            end = wi + bs
            if end <= d:
                taps[j] = bufs[j][wi:end]
            else:
                k = d - wi
                taps[j, :k] = bufs[j][wi:]
                taps[j, k:] = bufs[j][: bs - k]
        # feedback matrix (block of vectors: H @ (nl x bs))
        mix = H @ taps                     # (nl, bs)
        # damping one-pole, state carried across blocks (vectorised over lines)
        # lp = (1-damp)*mix + damp*lp_prev  -> causal recursion over bs samples
        # do it with lfilter-style sparse recursion, but bs is small so a
        # short Python loop over the block is fine
        lpc = np.empty_like(mix)
        for t in range(bs):
            lp = (1.0 - damp) * mix[:, t] + damp * lp
            lpc[:, t] = lp
        fb = lpc * g[:, None]
        inj = x[start:stop] / nl + fb
        for j in range(nl):
            d = len(bufs[j])
            wi = w[j]
            end = wi + bs
            if end <= d:
                bufs[j][wi:end] = inj[j]
            else:
                k = d - wi
                bufs[j][wi:] = inj[j, :k]
                bufs[j][: bs - k] = inj[j, k:]
            w[j] = end % d
        out[start:stop] = taps.sum(axis=0) / nl
    return out


def numpy_block_fdn_matmul_only(x, delays, g, block=64):
    """Same but skipping the damping recursion (to isolate matmul cost)."""
    n = len(x)
    nl = len(delays)
    bufs = [np.zeros(int(d), dtype=np.float64) for d in delays]
    w = [0] * nl
    out = np.zeros(n, dtype=np.float64)
    for start in range(0, n, block):
        stop = min(start + block, n)
        bs = stop - start
        taps = np.empty((nl, bs), dtype=np.float64)
        for j in range(nl):
            d = len(bufs[j]); wi = w[j]; end = wi + bs
            if end <= d:
                taps[j] = bufs[j][wi:end]
            else:
                k = d - wi
                taps[j, :k] = bufs[j][wi:]
                taps[j, k:] = bufs[j][: bs - k]
        mix = H @ taps
        inj = x[start:stop] / nl + mix * g[:, None]
        for j in range(nl):
            d = len(bufs[j]); wi = w[j]; end = wi + bs
            if end <= d:
                bufs[j][wi:end] = inj[j]
            else:
                k = d - wi
                bufs[j][wi:] = inj[j, :k]
                bufs[j][: bs - k] = inj[j, k:]
            w[j] = end % d
        out[start:stop] = taps.sum(axis=0) / nl
    return out


def pure_python_fdn_fast(x, delays, g, damp):
    """Pure-Python FDN using a Hadamard butterfly (O(N log N)) for the mix.

    This is the fastest *reasonable* pure-Python formulation, so it is the
    fair baseline to compare against the numpy block version.
    """
    n = len(x)
    nl = len(delays)
    bufs = [np.zeros(int(d), dtype=np.float64) for d in delays]
    idx = [0] * nl
    lens = [len(b) for b in bufs]
    lp = [0.0] * nl
    out = np.zeros(n, dtype=np.float64)
    inv = 1.0 / nl
    gl = g.tolist()
    sc = nl ** -0.5
    for i in range(n):
        t = [bufs[j][idx[j]] for j in range(nl)]
        h = 1
        while h < nl:
            for s in range(0, nl, h * 2):
                for j in range(s, s + h):
                    u = t[j]
                    v = t[j + h]
                    t[j] = u + v
                    t[j + h] = u - v
            h *= 2
        y = 0.0
        for j in range(nl):
            m = t[j] * sc
            lp[j] = (1.0 - damp) * m + damp * lp[j]
            nd = x[i] * inv + lp[j] * gl[j]
            bufs[j][idx[j]] = nd
            jj = idx[j] + 1
            idx[j] = 0 if jj >= lens[j] else jj
            y += nd
        out[i] = y * inv
    return out


def timeit(fn, *a, **kw):
    t0 = time.perf_counter()
    r = fn(*a, **kw)
    t1 = time.perf_counter()
    return t1 - t0, r


if __name__ == "__main__":
    print(f"numpy {np.__version__}, N={N} samples ({DUR}s @ {FS}Hz), {LINES} lines")
    try:
        import scipy
        print("scipy:", scipy.__version__)
    except Exception as e:
        print("scipy: NOT AVAILABLE", e)

    # --- pure python, on a shorter run, then extrapolate ---
    short = 20000
    t, _ = timeit(pure_python_fdn, x[:short], DELAYS, G, DAMP)
    print(f"[pure python naive O(N^2)] {short} samples in {t:.3f}s "
          f"=> {short/t/1e6:.3f} Msamples/s ; full {DUR}s tail would take {t*N/short:.1f}s")

    t, _ = timeit(pure_python_fdn_fast, x[:short], DELAYS, G, DAMP)
    print(f"[pure python FWHT O(NlogN)] {short} samples in {t:.3f}s "
          f"=> {short/t/1e6:.3f} Msamples/s ; full {DUR}s tail would take {t*N/short:.1f}s")

    for B in (16, 32, 64, 128, 256, 512, 1024):
        t, _ = timeit(numpy_block_fdn, x, DELAYS, G, DAMP, B)
        print(f"[numpy block B={B:5d}] {N} samples in {t:.4f}s "
              f"=> {N/t/1e6:.2f} Msamples/s ({N/t:.0f} samples/s)")

    for B in (64, 256):
        t, _ = timeit(numpy_block_fdn_matmul_only, x, DELAYS, G, B)
        print(f"[numpy block B={B:5d} no-damp] {N} samples in {t:.4f}s "
              f"=> {N/t/1e6:.2f} Msamples/s")

    # --- generate IR then FFT-convolve a 10 s signal ---
    t, ir = timeit(numpy_block_fdn, x, DELAYS, G, DAMP, 64)
    sig = np.random.randn(FS * 10)
    t0 = time.perf_counter()
    nfft = 1 << int(np.ceil(np.log2(len(sig) + len(ir) - 1)))
    y = np.fft.irfft(np.fft.rfft(sig, nfft) * np.fft.rfft(ir, nfft))[: len(sig)]
    t1 = time.perf_counter()
    print(f"[IR gen {t:.3f}s] + [fftconvolve 10s signal {t1-t0:.3f}s] total {t + t1 - t0:.3f}s")

    # --- verify the block FDN actually decays with the requested RT60 ---
    t, ir = timeit(numpy_block_fdn, x, DELAYS, G, DAMP, 64)
    env = np.abs(ir)
    # crude RT60 from a Schroeder-style backwards energy integral
    edc = np.cumsum(env[::-1] ** 2)[::-1]
    edc_db = 10 * np.log10(np.maximum(edc, 1e-300) / edc[0])
    idx = np.argmax(edc_db <= -60) if (edc_db <= -60).any() else len(edc_db) - 1
    print(f"measured T60 (EDC, -60 dB) = {idx / FS:.2f} s "
          f"(requested {RT60}s, damping={DAMP} shortens HF so <{RT60})")
    for frac in (0.05, 0.25, 0.5, 0.75):
        i = int(frac * len(edc_db))
        print(f"   EDC @ {frac*DUR:.2f}s = {edc_db[i]:7.1f} dB")
