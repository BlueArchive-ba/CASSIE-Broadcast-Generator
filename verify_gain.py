"""Verify the RT60 -> feedback-gain formula and quantify wet-level normalisation."""
import numpy as np

FS = 44100


def g_for(L, rt60, fs=FS):
    """Per-round-trip feedback gain for a delay of L samples and target T60."""
    return 10.0 ** (-3.0 * L / (rt60 * fs))


def measure_t60_comb(L, rt60, fs=FS, dur=30.0):
    """Build the exact IR of H(z)=1/(1-g z^-L) and measure T60 from the EDC."""
    g = g_for(L, rt60, fs)
    n = int(fs * dur)
    y = np.zeros(n)
    y[0] = 1.0
    # impulse train: g^k at sample k*L
    k = 0
    while k * L < n:
        y[k * L] = g**k
        k += 1
    edc = np.cumsum(y[::-1] ** 2)[::-1]
    edc_db = 10 * np.log10(np.maximum(edc, 1e-300) / edc[0])
    hit = np.argmax(edc_db <= -60) if (edc_db <= -60).any() else n - 1
    return g, hit / fs


print("=== A. Does g = 10^(-3L/(T60*fs)) give the requested T60? ===")
print(f"{'L (smp)':>8} {'T60 req':>8} {'g':>10} {'T60 meas':>9} {'err':>8}")
for L in (997, 1617, 4410):
    for rt in (1.0, 2.0, 3.0, 6.0):
        g, m = measure_t60_comb(L, rt, dur=rt * 12 + 5)
        print(f"{L:8d} {rt:8.2f} {g:10.6f} {m:9.3f} {m-rt:+8.3f}")
print("(measured T60 = time for the EDC to fall 60 dB; matches to within the")
print(" 1-delay-line quantisation of the impulse train)\n")

print("=== B. Wet-level growth: why you MUST normalise ===")
print("A feedback comb has DC gain 1/(1-g) and impulse-response energy 1/(1-g^2).")
print(f"{'T60':>6} {'g(L=1617)':>10} {'DC gain':>9} {'dB':>7} {'energy':>9} {'amp':>7}")
for rt in (0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 10.0):
    L = 1617
    g = g_for(L, rt)
    dcg = 1.0 / (1.0 - g)
    en = 1.0 / (1.0 - g * g)
    print(f"{rt:6.1f} {g:10.6f} {dcg:9.2f} {20*np.log10(dcg):7.1f} "
          f"{en:9.2f} {np.sqrt(en):7.2f}")
print("\n=> amplitude scale factor between T60=1s and T60=6s on a single comb:",
      f"{np.sqrt(1/(1-g_for(1617,6.0)**2)) / np.sqrt(1/(1-g_for(1617,1.0)**2)):.2f}x")
print("=> so normalise per comb by sqrt(1-g^2) (unity IR energy), and")
print("   highpass the wet path: DC gain 1/(1-g) is where the boom comes from.\n")

print("=== C. Freeverb comb feedback f = roomsize*0.28 + 0.7 ===")
print(f"{'roomsize':>9} {'f':>7} {'DC gain 1/(1-f)':>16} {'dB':>8}")
for rs in (0.0, 0.25, 0.5, 0.75, 0.9, 1.0):
    f = rs * 0.28 + 0.7
    print(f"{rs:9.2f} {f:7.4f} {1/(1-f):16.2f} {20*np.log10(1/(1-f)):8.1f}")
print("Freeverb initialroom=0.5 -> f=0.84 ; slider max 1.0 -> f=0.98")
print("PASP: f<1 required for DC stability, so roomsize < 1.0714\n")

print("=== D. Freeverb-type damp: what HF T60 does d give? ===")
print("Comb feedback path gain at frequency w is g*|H_lp(w)|, H_lp=(1-d)/(1-d e^-jw).")
print("T60(w) = -3*L / (fs * log10(g*|H_lp(w)|)).")
for d in (0.0, 0.1, 0.2, 0.4, 0.6):
    L, rt = 1617, 3.0
    g = g_for(L, rt)
    out = []
    for fhz in (1000, 4000, 8000, 12000):
        w = 2 * np.pi * fhz / FS
        H = (1 - d) / (1 - d * np.exp(-1j * w))
        gg = g * abs(H)
        t60 = -3.0 * L / (FS * np.log10(gg)) if gg < 1 else np.inf
        out.append(f"{fhz/1000:>4.0f}k {t60:5.2f}s")
    print(f"  damp={d:4.2f}: " + " | ".join(out))
print("\n=> damping lowers HF T60 relative to the 3.0 s low-frequency value:")
print("   physically correct (real rooms: decayHFRatio < 1).")
