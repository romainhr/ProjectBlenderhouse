"""Mediciones de color y textura sobre renders de revisión y capturas del visor (corrección 07c, ronda 2).

Uso:
    python3 tools/medir_capturas.py <especificacion.json> [--salida resultado.json]

La especificación es una lista de mediciones:
    {"nombre": "...", "imagen": "review/07c_plano/cocina_cajones_cerrados.png",
     "tipo": "acero" | "razon" | "media",          # media con "croma_max": |B − R| en sRGB, máximo
     "region": [x0, y0, x1, y1],                    # acero y media: la región medida (px de la imagen)
     "bloque_4cm": 20,                              # acero: lado en px de un bloque de ~4 cm a esa distancia
     "num": [x0, y0, x1, y1], "den": [x0, y0, x1, y1]}   # razon: dos regiones

Todo se mide en luma sRGB codificada (Y' = 0,2126 R' + 0,7152 G' + 0,0722 B', niveles de 0 a 255), como las cifras
de las revisiones anteriores; `media` y `razon` dan además la luminancia lineal y la cromaticidad (r, g) lineal.
Criterios del acero (docs/noche-2026-09-26.md, 07c ronda 2):
- paso_alto: σ de Y' menos su media móvil horizontal de 9 px (franjas del cepillado). Criterio < 1,5.
- residuo_12_60: medias de bloques de 12 px menos la media de sus 5 × 5 bloques vecinos (manchas de 12-60 px), σ.
  Criterio < 1,5 niveles.
- rango_4cm: medias de bloques de ~4 cm sin la tendencia lineal (plano ajustado), (máx − mín) / media. Criterio < 3 %.
  rango_4cm_cuadrica: lo mismo sin una cuádrica. En un render el reflejo del entorno también varía a esa escala (lo
  hace en Blender, sin nube en la textura): el criterio sólo aísla la textura en una imagen de la textura misma
  (tipo "textura": el mapa, sin luz) o con luz pareja.
Sin dependencias fuera de Pillow.
"""
import argparse
import json
import math
import os

from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luma(px):
    r, g, b = px[:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _recorte(im, reg):
    x0, y0, x1, y1 = reg
    return im.crop((x0, y0, x1, y1))


def _matriz(im):
    w, h = im.size
    datos = list(im.getdata())
    return [[_luma(datos[y * w + x]) for x in range(w)] for y in range(h)]


def _sigma(v):
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / len(v))


def paso_alto(Y, ancho=9):
    res = []
    r = ancho // 2
    for fila in Y:
        acum = [0.0]
        for x in fila:
            acum.append(acum[-1] + x)
        for i in range(r, len(fila) - r):
            res.append(fila[i] - (acum[i + r + 1] - acum[i - r]) / ancho)
    return _sigma(res) if res else float("nan")


def bloques(Y, lado):
    h, w = len(Y), len(Y[0])
    nb_y, nb_x = h // lado, w // lado
    return [[sum(Y[y][x] for y in range(j * lado, (j + 1) * lado) for x in range(i * lado, (i + 1) * lado)) / lado ** 2
             for i in range(nb_x)] for j in range(nb_y)]


def residuo_12_60(Y):
    B = bloques(Y, 12)
    ny, nx = len(B), len(B[0]) if B else 0
    res = []
    for j in range(2, ny - 2):
        for i in range(2, nx - 2):
            vec = [B[jj][ii] for jj in range(j - 2, j + 3) for ii in range(i - 2, i + 3)]
            res.append(B[j][i] - sum(vec) / 25)
    return (_sigma(res) if res else float("nan")), len(res)


def _resolver(A, b):
    """Gauss con pivoteo parcial (sistemas chicos, sin numpy)."""
    n = len(b)
    M = [fila[:] + [b[i]] for i, fila in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        if abs(M[c][c]) < 1e-12:
            return [0.0] * n
        for r in range(c + 1, n):
            f = M[r][c] / M[c][c]
            for k in range(c, n + 1):
                M[r][k] -= f * M[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (M[r][n] - sum(M[r][k] * x[k] for k in range(r + 1, n))) / M[r][r]
    return x


def rango_sin_tendencia(Y, lado, grado=1):
    """Medias de bloques de `lado` px menos la superficie ajustada (plano si grado = 1, cuádrica si 2),
    (máx − mín) / media."""
    B = bloques(Y, lado)
    pts = [(i, j, B[j][i]) for j in range(len(B)) for i in range(len(B[0]))]
    n = len(pts)
    base = (lambda i, j: [1.0, i, j]) if grado == 1 else (lambda i, j: [1.0, i, j, i * i, i * j, j * j])
    if n < len(base(0, 0)) + 1:
        return float("nan"), n
    F = [base(p[0], p[1]) for p in pts]
    m = len(F[0])
    A = [[sum(f[a] * f[b] for f in F) for b in range(m)] for a in range(m)]
    v = [sum(f[a] * p[2] for f, p in zip(F, pts)) for a in range(m)]
    coef = _resolver(A, v)
    res = [p[2] - sum(c * x for c, x in zip(coef, f)) for f, p in zip(F, pts)]
    media_b = sum(p[2] for p in pts) / n
    return (max(res) - min(res)) / media_b, n


def media(im, reg):
    c = _recorte(im, reg)
    datos = list(c.getdata())
    n = len(datos)
    srgb = [sum(p[k] for p in datos) / n for k in range(3)]
    lin = [sum(_lin(p[k]) for p in datos) / n for k in range(3)]
    Y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    suma = sum(lin) or 1.0
    return {"srgb": [round(x, 1) for x in srgb], "luma": round(_luma(srgb), 2), "Y_lineal": round(Y, 4),
            "rg_lineal": [round(lin[0] / suma, 3), round(lin[1] / suma, 3)]}


def medir(e):
    im = Image.open(os.path.join(RAIZ, e["imagen"])).convert("RGB")
    out = {"nombre": e["nombre"], "imagen": e["imagen"], "tipo": e["tipo"]}
    if e["tipo"] == "acero":
        Y = _matriz(_recorte(im, e["region"]))
        r, nr = residuo_12_60(Y)
        g, ng = rango_sin_tendencia(Y, e.get("bloque_4cm", 20))
        g2, _ = rango_sin_tendencia(Y, e.get("bloque_4cm", 20), grado=2)
        out.update(region=e["region"], paso_alto=round(paso_alto(Y), 3), residuo_12_60=round(r, 3),
                   rango_4cm=round(g, 4), rango_4cm_cuadrica=round(g2, 4), bloques=[nr, ng],
                   media=media(im, e["region"]))
        out["cumple"] = {"paso_alto<1,5": out["paso_alto"] < 1.5, "residuo_12_60<1,5": out["residuo_12_60"] < 1.5,
                         "rango_4cm<3%": out["rango_4cm"] < 0.03}
    elif e["tipo"] == "textura":
        Y = _matriz(_recorte(im, e.get("region", [0, 0, im.size[0], im.size[1]])))
        g, ng = rango_sin_tendencia(Y, e["bloque_4cm"])
        r, nr = residuo_12_60(Y)
        out.update(rango_4cm=round(g, 4), residuo_12_60=round(r, 3), bloques=[nr, ng],
                   media=round(sum(map(sum, Y)) / (len(Y) * len(Y[0])), 2))
        out["cumple"] = {"rango_4cm<3%": out["rango_4cm"] < 0.03}
    elif e["tipo"] == "razon":
        a, b = media(im, e["num"]), media(im, e["den"])
        out.update(num=a, den=b, razon_luma=round(a["luma"] / b["luma"], 3),
                   razon_Y=round(a["Y_lineal"] / b["Y_lineal"], 3))
    else:
        out.update(region=e["region"], **media(im, e["region"]))
        if "croma_max" in e:                # corrección 08, ronda 2: el acero neutro, |B − R| en sRGB
            out["croma_B_menos_R"] = round(out["srgb"][2] - out["srgb"][0], 1)
            out["cumple"] = {f"|B−R|≤{e['croma_max']}": abs(out["croma_B_menos_R"]) <= e["croma_max"]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("especificacion")
    ap.add_argument("--salida")
    a = ap.parse_args()
    with open(a.especificacion) as fh:
        spec = json.load(fh)
    res = [medir(e) for e in spec]
    for r in res:
        print(json.dumps(r, ensure_ascii=False))
    if a.salida:
        with open(a.salida, "w") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
