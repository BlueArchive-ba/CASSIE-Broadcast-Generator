"""Air absorption per ISO 9613-1, implemented from the published formula.

Transcribed from the ISO 9613-1 reference implementation in the CRAN package
`bioSNR` (R/absorptionAir.R), which documents itself as "the standard method of
calculating the absorption of sound in air (ISO 9613-1)".

Returns the attenuation coefficient alpha in dB/m (the `m` of the Sabine /
image-source air-absorption term).
"""
import numpy as np

P_REF = 101.325   # kPa, standard sea-level pressure
T_REF = 293.15    # K
T_TRIPLE = 273.16  # K


def alpha_air(f, p=P_REF, t_c=20.0, h=50.0):
    """ISO 9613-1 attenuation coefficient in dB/m.

    f   : frequency, Hz (scalar or array)
    p   : ambient pressure, kPa
    t_c : temperature, degrees C
    h   : relative humidity, %
    """
    f = np.asarray(f, dtype=float)
    T = t_c + 273.15

    # saturation vapour pressure
    v1 = 10.79586 * (1.0 - T_TRIPLE / T)
    v2 = np.log10(T / T_TRIPLE)
    v3 = 1e-4 * (1.0 - 10.0 ** (-8.29692 * (T / T_TRIPLE - 1.0)))
    v4 = 1e-3 * (-1.0 + 10.0 ** (4.76955 * (1.0 - T_TRIPLE / T)))
    v = v1 - 5.02808 * v2 + 1.50474 * v3 + 0.42873 * v4 - 2.2195983
    ps = P_REF * 10.0 ** v

    # molar water-vapour concentration, %
    h_eff = h * (ps / P_REF) * (p / P_REF) ** -1

    # oxygen relaxation frequency
    fo = p / P_REF * (24.0 + 4.04e4 * h_eff * (0.02 + h_eff) / (0.391 + h_eff))
    # nitrogen relaxation frequency
    fn = (p / P_REF) * (T / T_REF) ** -0.5 * (
        9.0 + 280.0 * h_eff * np.exp(-4.170 * ((T / T_REF) ** (-1.0 / 3.0) - 1.0))
    )

    a = 8.686 * f**2 * (
        1.84e-11 * (p / P_REF) ** -1 * (T / T_REF) ** 0.5
        + (T / T_REF) ** -2.5
        * (
            0.01275 * np.exp(-2239.1 / T) * (fo / (f**2 + fo**2))
            + 0.1068 * np.exp(-3352.0 / T) * (fn / (f**2 + fn**2))
        )
    )
    return a


if __name__ == "__main__":
    bands = [125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    print("ISO 9613-1 air attenuation coefficient (dB/m and dB/km)")
    print("pressure 101.325 kPa, 20 degC, 50% RH\n")
    print(f"{'Hz':>7} {'dB/m':>12} {'dB/km':>10} {'dB/100m':>9} "
          f"{'e-folds/100m':>13}  m=dB/m")
    for f in bands:
        a = alpha_air(f)
        print(f"{f:7d} {a:12.6f} {a*1000:10.2f} {a*100:9.3f} {a*100/8.686:13.4f}")

    print("\nHumidity dependence at 4 kHz, 20 degC:")
    for h in (10, 20, 30, 40, 50, 60, 70, 80, 90):
        print(f"  RH {h:3d}% : {alpha_air(4000, h=h):9.6f} dB/m "
              f"({alpha_air(4000, h=h)*1000:7.2f} dB/km)")

    print("\nTemperature dependence at 4 kHz, 50% RH:")
    for t in (-10, 0, 10, 20, 30, 40):
        print(f"  T {t:4d} C : {alpha_air(4000, t_c=t):9.6f} dB/m")

    # How much does air alone attenuate the tail in a 60 m corridor,
    # i.e. how many round trips before 4 kHz is 60 dB down?
    print("\nAir-only attenuation in a 60 m corridor (one-way 60 m):")
    for f in (500, 1000, 2000, 4000, 8000):
        a = alpha_air(f)
        db = a * 60
        print(f"  {f:5d} Hz: {db:6.2f} dB over 60 m  -> "
              f"{'60 dB reached in %.0f m' % (60/a/60*60) if False else '%.0f m for 60 dB' % (60.0/a)}")
