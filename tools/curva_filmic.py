"""Curva de tono Filmic de Blender 3.6 medida en Blender, para el exterior del visor (corrección 08, ronda 1).

Uso:
    blender -b --python tools/curva_filmic.py -- [--salida web/src/tour/js/filmic.js]

Los renders de revisión del exterior (tools/render_08.py) salen con Filmic (sin look de día y de tarde, «Medium
Contrast» de noche) y el visor dibuja con ACES de three.js. Con el mismo valor de escena, ACES deja las sombras
bastante más oscuras que Filmic y los claros más claros: el ladrillo del E2 en sombra salía a 0,75 de Blender y el
hormigón del E3 a 1,32 con el mismo sombreado. El visor aplica a los materiales del exterior esta curva en lugar de
ACES (web/src/tour/js/exterior.js), para que la misma luz dé el mismo gris que en Blender.

Método: una imagen de coma flotante de N × 1 píxeles grises con valores de escena 0,18 · 2^s, s de LO a HI pasos (el
rango de Filmic), guardada con image.save_render() y la gestión de color de la escena (Filmic, sin exposición, sRGB):
el PNG trae el valor de pantalla (sRGB codificado, 0-255) de cada muestra. En grises el LUT de desaturación de Filmic
no actúa: es la curva de tono pura, por canal. Escribe un módulo de JavaScript con las dos curvas.
"""
import json
import os
import sys

import bpy
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LO, HI, N = -10.0, 6.5, 64          # pasos desde el gris medio (el rango de Filmic Log en Blender 3.x)
LOOKS = {"ninguno": "None", "contraste_medio": "Medium Contrast"}


def medir(look, ruta_tmp):
    scene = bpy.context.scene
    vs = scene.view_settings
    scene.display_settings.display_device = "sRGB"
    vs.view_transform, vs.look, vs.exposure, vs.gamma = "Filmic", look, 0.0, 1.0
    vs.use_curve_mapping = False
    s = np.linspace(LO, HI, N)
    v = 0.18 * 2.0 ** s
    im = bpy.data.images.new("_curva", N, 1, alpha=False, float_buffer=True)
    px = np.ones((1, N, 4), np.float32)
    px[0, :, :3] = v[:, None]
    im.pixels.foreach_set(px.ravel())
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    im.save_render(ruta_tmp, scene=scene)
    bpy.data.images.remove(im)
    lee = bpy.data.images.load(ruta_tmp)
    lee.colorspace_settings.name = "Non-Color"       # el valor guardado, sin pasarlo a lineal: el de pantalla
    out = np.empty(N * 4, np.float32)
    lee.pixels.foreach_get(out)
    srgb = out.reshape(N, 4)[:, 0]
    bpy.data.images.remove(lee)
    return [round(float(x), 5) for x in np.clip(srgb, 0, 1)]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    salida = os.path.join(RAIZ, "web", "src", "tour", "js", "filmic.js")
    if "--salida" in argv:
        salida = argv[argv.index("--salida") + 1]
    tmp = bpy.app.tempdir or "/tmp"
    curvas = {k: medir(look, os.path.join(tmp, f"_curva_{k}.png")) for k, look in LOOKS.items()}
    txt = ("// Generado por tools/curva_filmic.py (Blender " + bpy.app.version_string + "): curva de tono Filmic de Blender\n"
           "// por canal, medida con image.save_render() sobre grises de escena 0,18 · 2^s, s de LO a HI pasos en N muestras\n"
           "// iguales. Valores de pantalla sRGB codificados (0-1). «ninguno»: sin look (día y tarde en tools/render_08.py);\n"
           "// «contraste_medio»: Medium Contrast (noche). No editar a mano.\n"
           f"export const FILMIC = {json.dumps({'lo': LO, 'hi': HI, 'medio': 0.18, **curvas})};\n")
    with open(salida, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print("CURVA_FILMIC", salida, {k: (c[0], c[N // 2], c[-1]) for k, c in curvas.items()})


if __name__ == "__main__":
    main()
