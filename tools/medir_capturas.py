"""Mediciones de color y textura sobre renders de revisión y capturas del visor (corrección 07c, ronda 2).

Uso:
    python3 tools/medir_capturas.py <especificacion.json> [--salida resultado.json]

La especificación es una lista de mediciones:
    {"nombre": "...", "imagen": "review/07c_plano/cocina_cajones_cerrados.png",
     "tipo": "acero" | "razon" | "media",
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


def rango_sin_tendencia(Y, lado):
    B = bloques(Y, lado)
    pts = [(i, j, B[j][i]) for j in range(len(B)) for i in range(len(B[0]))]
    n = len(pts)
    if n < 4:
        return float("nan"), n
    # plano z = a + b i + c j por mínimos cuadrados (ecuaciones normales 3 × 3)
    s = lambda f: sum(f(p) for p in pts)   # noqa: E731
    M = [[n, s(lambda p: p[0]), s(lambda p: p[1])],
         [s(lambda p: p[0]), s(lambda p: p[0] ** 2), s(lambda p: p[0] * p[1])],
         [s(lambda p: p[1]), s(lambda p: p[0] * p[1]), s(lambda p: p[1] ** 2)]]
    v = [s(lambda p: p[2]), s(lambda p: p[0] * p[2]), s(lambda p: p[1] * p[2])]

    def det(A):
        return (A[0][0] * (A[1][1] * A[2][2] - A[1][2] * A[2][1]) - A[0][1] * (A[1][0] * A[2][2] - A[1][2] * A[2][0])
                + A[0][2] * (A[1][0] * A[2][1] - A[1][1] * A[2][0]))
    d = det(M)
    coef = []
    for k in range(3):
        A = [fila[:] for fila in M]
        for f in range(3):
            A[f][k] = v[f]
        coef.append(det(A) / d if d else 0.0)
    res = [p[2] - (coef[0] + coef[1] * p[0] + coef[2] * p[1]) for p in pts]
    media = sum(p[2] for p in pts) / n
    return (max(res) - min(res)) / media, n


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
        out.update(region=e["region"], paso_alto=round(paso_alto(Y), 3), residuo_12_60=round(r, 3),
                   rango_4cm=round(g, 4), bloques=[nr, ng], media=media(im, e["region"]))
        out["cumple"] = {"paso_alto<1,5": out["paso_alto"] < 1.5, "residuo_12_60<1,5": out["residuo_12_60"] < 1.5,
                         "rango_4cm<3%": out["rango_4cm"] < 0.03}
    elif e["tipo"] == "razon":
        a, b = media(im, e["num"]), media(im, e["den"])
        out.update(num=a, den=b, razon_luma=round(a["luma"] / b["luma"], 3),
                   razon_Y=round(a["Y_lineal"] / b["Y_lineal"], 3))
    else:
        out.update(region=e["region"], **media(im, e["region"]))
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
