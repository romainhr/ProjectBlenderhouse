"""Color de las luces por temperatura de color (sin bpy: lo usan la fase 4, la fase 5 y las pruebas sin Blender).

kelvin_a_lineal(K) -> (r, g, b) en sRGB LINEAL (primarias Rec. 709, blanco D65), normalizado para que el canal
mayor valga 1. Es el color que esperan `Light.color` de Blender y `luces[].color` del contrato de interacción
(sección 2). Calculado, no medido: radiancia de Planck integrada de 380 a 780 nm contra las funciones de
igualación CIE 1931 (ajuste analítico de Wyman, Sloan y Shirley 2013) y matriz XYZ -> sRGB lineal de IEC 61966-2-1.
Referencia de control (misma cuenta): 2700 K ≈ (1.00, 0.42, 0.10) lineal ≈ (1.00, 0.68, 0.35) en sRGB codificado;
3000 K ≈ (1.00, 0.48, 0.15) lineal ≈ (1.00, 0.73, 0.43) sRGB.
"""
import math

_H, _C, _KB = 6.62607015e-34, 2.99792458e8, 1.380649e-23
_XYZ_A_SRGB = ((3.2404542, -1.5371385, -0.4985314),
               (-0.9692660, 1.8760108, 0.0415560),
               (0.0556434, -0.2040259, 1.0572252))


def _g(x, mu, s1, s2):
    t = (x - mu) / (s1 if x < mu else s2)
    return math.exp(-0.5 * t * t)


def cie1931(nm):
    """Funciones de igualación x̄, ȳ, z̄ (ajuste de varios lóbulos de Wyman et al. 2013)."""
    x = 1.056 * _g(nm, 599.8, 37.9, 31.0) + 0.362 * _g(nm, 442.0, 16.0, 26.7) - 0.065 * _g(nm, 501.1, 20.4, 26.2)
    y = 0.821 * _g(nm, 568.8, 46.9, 40.5) + 0.286 * _g(nm, 530.9, 16.3, 31.1)
    z = 1.217 * _g(nm, 437.0, 11.8, 36.0) + 0.681 * _g(nm, 459.0, 26.0, 13.8)
    return x, y, z


def planck(nm, kelvin):
    lam = nm * 1e-9
    return (2 * _H * _C ** 2) / (lam ** 5 * (math.exp(_H * _C / (lam * _KB * kelvin)) - 1.0))


def kelvin_a_lineal(kelvin, decimales=4):
    X = Y = Z = 0.0
    for nm in range(380, 781):
        p = planck(nm, kelvin)
        x, y, z = cie1931(nm)
        X, Y, Z = X + p * x, Y + p * y, Z + p * z
    rgb = [max(0.0, a * X + b * Y + c * Z) for a, b, c in _XYZ_A_SRGB]
    m = max(rgb)
    return tuple(round(v / m, decimales) for v in rgb)


def lineal_a_srgb(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


if __name__ == "__main__":
    for k in (2700, 3000, 4000, 6500):
        lin = kelvin_a_lineal(k)
        print(k, lin, tuple(round(lineal_a_srgb(c), 3) for c in lin))
