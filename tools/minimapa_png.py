"""Minimapa del visor en PNG, desde depto_colisiones.json: lo mismo que dibuja web/src/tour/js/minimapa.js (cajas
estáticas en tinta, móviles en acento en su estado del modelo), más el contorno de la huella de cada clóset del plano
(build/depto_03_formas.py, CLOSETS) en azul, para revisar que la colisión los cubra (corrección 07c).

Uso (python3 con PIL, sin Blender):
    python3 tools/minimapa_png.py --json exports/depto_colisiones.json --out review/07c_plano/minimapa_colision.png \
        [--renders review/07c_plano/renders.json]

Con --renders agrega (o reemplaza) su entrada {archivo, que_muestra} en ese renders.json.
"""
import argparse
import json
import math
import os
import sys
import types

from PIL import Image, ImageDraw

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
for mod in ("bpy", "bmesh", "mathutils"):          # depto_03_formas sólo se lee por sus constantes
    m = types.ModuleType(mod)
    m.Vector = m.Matrix = object
    sys.modules.setdefault(mod, m)
import depto_plano as P  # noqa: E402

PAPEL, TINTA, ACENTO, CLOSET = (247, 244, 239), (30, 28, 25), (168, 72, 31), (40, 90, 200)
ESCALA = 2                                          # px de salida por px del plano


def closets():
    import importlib.util
    spec = importlib.util.spec_from_file_location("f3", os.path.join(RAIZ, "build", "depto_03_formas.py"))
    f3 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(f3)
    return f3.CLOSETS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--renders", default="")
    a = ap.parse_args()
    with open(a.json) as fh:
        D = json.load(fh)
    im = Image.new("RGB", (500 * ESCALA, 500 * ESCALA), PAPEL)
    dr = ImageDraw.Draw(im)

    def pt(x, z):                                   # glTF (x, z) -> px de salida (plano: Blender (x, -z))
        u, v = P.a_plano(x, -z)
        return (u * ESCALA, v * ESCALA)
    for c in D["estaticos"]:
        (u0, v0), (u1, v1) = pt(c[0], c[2]), pt(c[1], c[3])
        dr.rectangle((min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1)), fill=TINTA)
    for m in D["moviles"]:
        ang = (m["angulo"] if m["tipo"] == "bisagra" else 0.0)
        ca, sa = math.cos(ang), math.sin(ang)
        px_, pz_ = m["posicion"][0], m["posicion"][2]
        for c in m["cajas_locales"]:
            poli = [pt(px_ + x * ca + z * sa, pz_ - x * sa + z * ca)
                    for x, z in ((c[0], c[2]), (c[1], c[2]), (c[1], c[3]), (c[0], c[3]))]
            dr.polygon(poli, fill=ACENTO)
    for cid, x0, x1, yf, yfr in closets():
        dr.rectangle((x0 * ESCALA, min(yf, yfr) * ESCALA, x1 * ESCALA, max(yf, yfr) * ESCALA), outline=CLOSET, width=2)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    im.save(a.out)
    print("MINIMAPA", a.out, len(D["estaticos"]), "estáticas", len(D["moviles"]), "móviles")
    if a.renders:
        lista = []
        if os.path.exists(a.renders):
            with open(a.renders) as fh:
                lista = json.load(fh)
        nombre = os.path.basename(a.out)
        lista = [r for r in lista if r["archivo"] != nombre]
        lista.append({"archivo": nombre, "que_muestra": (
            "Minimapa del visor dibujado desde exports/depto_colisiones.json (cajas estáticas en tinta, móviles en "
            "acento, estado del modelo) con la huella de los cuatro clósets del plano en azul: cada uno queda lleno "
            "por su Depto_Col_Closet_<id> (del fondo a la línea CL*, z 0,10-1,80), no hueco.")})
        with open(a.renders, "w") as fh:
            json.dump(lista, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
