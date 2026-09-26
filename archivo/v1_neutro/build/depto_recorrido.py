"""Prueba de recorrido del activo Depto: ¿se llega caminando desde el hall a cada recinto?

Uso (lo ejecuta build/depto_run.sh desde la fase 3):
    blender -b build/depto.blend --python-exit-code 1 --python build/depto_recorrido.py -- \
        --out review/depto_03 [--radio 0.25]

Modelo: un cilindro vertical de radio --radio (la cámara del tour) que pasa por encima de lo que mide
menos de Z_PASO (rieles, umbrales, alfombras) y choca con todo lo que ocupe la franja Z_PASO..Z_CABEZA.
Obstáculos: las mallas visibles de la colección Depto (salvo Depto_Ref_*) y las de colisión ocultas
(["colision"] = True, p.ej. Depto_Col_Baranda); un objeto con ["colision"] = False se ignora. Cada isla de
malla se proyecta en planta como envolvente convexa y se agranda en el radio (en esquinas en ángulo: es
conservador, nunca da paso donde no lo hay). Grilla de 1 px del plano (0,019 m), inundación desde el hall.

No guarda el .blend. Escribe <out>/recorrido.json y <out>/recorrido.png (el plano con lo alcanzable en verde
y las zonas prohibidas para el centro de la cámara en rojo). Sale con código 1 si un recinto obligatorio
no es alcanzable.
"""
import argparse
import json
import os
import sys
from collections import deque

import bpy
import numpy as np
from mathutils import geometry

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_geom as G  # noqa: E402
import depto_plano as P  # noqa: E402

Z_PASO = 0.10      # supuesto: escalón que sube la cámara del tour (el riel del ventanal mide 0,05)
Z_CABEZA = 1.80    # supuesto: alto del cilindro (los dinteles están a 2,05)
INICIO = "Hall"
# Un punto de piso libre por recinto (px del plano), elegido lejos del mobiliario del plano (fase 4).
PUNTOS = {
    "Hall": (395, 340), "Living": (270, 250), "Cocina": (340, 215), "Dorm1": (200, 155),
    "Paso_D1": (315, 91), "Bano1": (362, 100), "Dorm2": (200, 348), "Paso_D2": (315, 425),
    "Bano2": (362, 430), "Balcon": (85, 250),
}
INFORMATIVOS = {"Palier": (470, 335), "Nicho_LV": (312, 345)}   # cerrados por diseño: no se exigen
BUSQUEDA = 5       # px: un punto cuenta como alcanzado si hay una celda alcanzada a esta distancia


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--radio", type=float, default=0.25)
    return p.parse_args(argv)


def obstaculos(root):
    out = []
    for o in root.all_objects:
        if o.type != "MESH" or o.name.startswith("Depto_Ref"):
            continue
        col = o.get("colision")
        if col is False or (o.hide_render and not col):
            continue
        for isla in G.islas_mundo(o):
            z0, z1 = min(v.z for v in isla), max(v.z for v in isla)
            if z1 <= Z_PASO or z0 >= Z_CABEZA:
                continue
            pts = [P.a_plano(v.x, v.y) for v in isla]
            idx = geometry.convex_hull_2d(pts)
            out.append((o.name, [pts[i] for i in idx]))
    return out


def rasterizar(obs, ancho, alto, r_px):
    """Celdas cuyo centro está a menos de r_px de alguna envolvente (polígono agrandado con esquinas en ángulo)."""
    bloq = np.zeros((alto, ancho), bool)
    for _, hull in obs:
        xs, ys = [p[0] for p in hull], [p[1] for p in hull]
        i0, i1 = max(0, int(min(xs) - r_px) - 1), min(ancho, int(max(xs) + r_px) + 2)
        j0, j1 = max(0, int(min(ys) - r_px) - 1), min(alto, int(max(ys) + r_px) + 2)
        if i0 >= i1 or j0 >= j1:
            continue
        XX, YY = np.meshgrid(np.arange(i0, i1) + 0.5, np.arange(j0, j1) + 0.5)
        m = np.ones(XX.shape, bool)
        n = len(hull)
        area = sum(hull[k][0] * hull[(k + 1) % n][1] - hull[(k + 1) % n][0] * hull[k][1] for k in range(n))
        sg = 1.0 if area >= 0 else -1.0
        if n < 3:            # isla degenerada en planta (una línea): se trata como su bbox
            m &= (XX >= min(xs) - r_px) & (XX <= max(xs) + r_px) & (YY >= min(ys) - r_px) & (YY <= max(ys) + r_px)
        else:
            for k in range(n):
                (ax, ay), (bx, by) = hull[k], hull[(k + 1) % n]
                L = max(((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5, 1e-9)
                dist = sg * ((bx - ax) * (YY - ay) - (by - ay) * (XX - ax)) / L   # > 0 dentro
                m &= dist > -r_px
        bloq[j0:j1, i0:i1] |= m
    return bloq


def inundar(libre, semilla):
    alto, ancho = libre.shape
    alc = np.zeros_like(libre)
    i, j = semilla
    if not libre[j, i]:
        return alc
    q = deque([(i, j)])
    alc[j, i] = True
    while q:
        i, j = q.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < ancho and 0 <= b < alto and libre[b, a] and not alc[b, a]:
                alc[b, a] = True
                q.append((a, b))
    return alc


def alcanzado(alc, p):
    i, j = int(p[0]), int(p[1])
    return bool(alc[max(0, j - BUSQUEDA):j + BUSQUEDA + 1, max(0, i - BUSQUEDA):i + BUSQUEDA + 1].any())


def guardar_png(ruta, plano_rgba, bloq, alc, puntos_estado):
    alto, ancho = bloq.shape
    img = plano_rgba.copy()
    img[..., :3] = 0.35 + 0.65 * img[..., :3]                       # plano aclarado de fondo
    rojo, verde = np.array([0.95, 0.35, 0.30]), np.array([0.35, 0.80, 0.40])
    img[bloq, :3] = 0.5 * img[bloq, :3] + 0.5 * rojo
    img[alc, :3] = 0.45 * img[alc, :3] + 0.55 * verde
    for (x, y), ok in puntos_estado:
        c = np.array([0.1, 0.4, 0.1]) if ok else np.array([0.8, 0.0, 0.0])
        i, j = int(x), int(y)
        img[max(0, j - 3):j + 4, max(0, i - 3):i + 4, :3] = c
    im = bpy.data.images.new("_recorrido", ancho, alto, alpha=True)
    im.pixels = img[::-1].ravel().tolist()                           # Blender guarda las filas de abajo arriba
    im.filepath_raw = ruta
    im.file_format = "PNG"
    im.save()


def main():
    args = parse_args()
    os.makedirs(args.out, exist_ok=True)
    root = bpy.data.collections["Depto"]
    bpy.context.view_layer.update()
    plano = bpy.data.images.load(os.path.join(RAIZ, "ref", "plano", "plano_depto.png"))
    ancho, alto = plano.size
    rgba = np.array(plano.pixels[:], dtype=np.float32).reshape(alto, ancho, 4)[::-1]
    r_px = args.radio / P.M_POR_PX
    obs = obstaculos(root)
    bloq = rasterizar(obs, ancho, alto, r_px)
    ini = PUNTOS[INICIO]
    alc = inundar(~bloq, (int(ini[0]), int(ini[1])))
    res = {n: alcanzado(alc, p) for n, p in PUNTOS.items()}
    info = {n: alcanzado(alc, p) for n, p in INFORMATIVOS.items()}
    faltan = [n for n, ok in res.items() if not ok]
    guardar_png(os.path.join(args.out, "recorrido.png"), rgba, bloq, alc,
                [(p, res.get(n, info.get(n))) for n, p in {**PUNTOS, **INFORMATIVOS}.items()])
    salida = {"radio_m": args.radio, "franja_z_m": [Z_PASO, Z_CABEZA], "inicio_px": ini, "islas_obstaculo": len(obs),
              "obligatorios": res, "informativos_cerrados_por_diseno": info, "faltan": faltan,
              "area_alcanzable_m2": round(float(alc.sum()) * P.M_POR_PX ** 2, 2)}
    with open(os.path.join(args.out, "recorrido.json"), "w") as f:
        json.dump(salida, f, indent=2, ensure_ascii=False)
    print("RECORRIDO", json.dumps({"radio_m": args.radio, "alcanzados": sum(res.values()), "de": len(res),
                                   "faltan": faltan, "area_m2": salida["area_alcanzable_m2"]}, ensure_ascii=False))
    if faltan:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
