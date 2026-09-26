"""Vista previa de una pieza de la decoración: la construye sola en un estudio neutro y la renderiza en Eevee.

Uso:
    blender -b --python-exit-code 1 --python tools/preview_pieza.py -- --modulo deco_living --funcion sofa \
        --out review/deco/piezas [--args '{"ancho": 1.8}'] [--texturas] [--nombre sofa_largo]

Escribe <out>/<nombre>.png (vista 3/4 frontal y vista lateral, lado a lado) y <out>/<nombre>.json (objetos,
triángulos, dimensiones, materiales). Con --texturas aplica las texturas de build/deco_paleta.py que ya existan
en disco. El estudio: piso gris claro en la cota más baja de la pieza, un muro detrás (lado +Y), sol, luz de
área y cielo gris. No guarda ningún .blend.
"""
import argparse
import importlib
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--modulo", required=True)
    p.add_argument("--funcion", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--args", default="{}")
    p.add_argument("--texturas", action="store_true")
    p.add_argument("--nombre", default="")
    p.add_argument("--size", default="800x600")
    return p.parse_args(argv)


def estudio(scene, lo, hi):
    import depto_geom as G
    for nombre, rgb in (("_piso_estudio", (0.72, 0.72, 0.70)), ("_muro_estudio", (0.86, 0.85, 0.83))):
        G.MATERIALES.setdefault(nombre, (rgb, 0.8, 0.0, 1.0))
    import deco_base as B
    col = bpy.data.collections.new("_estudio")
    scene.collection.children.link(col)
    tam = max((hi - lo).length, 1.0) * 3
    bm = __import__("bmesh").new()
    B.caja(bm, -tam, tam, -tam, tam, lo.z - 0.02, lo.z)
    B.objeto(col, "_piso", bm, "_piso_estudio")
    if hi.z - lo.z > 0.05:
        bm = __import__("bmesh").new()
        B.caja(bm, -tam, tam, hi.y + 0.002, hi.y + 0.05, lo.z, lo.z + max(3.0, (hi.z - lo.z) * 1.6))
        B.objeto(col, "_muro", bm, "_muro_estudio")
    sd = bpy.data.lights.new("_sol", "SUN")
    sd.energy = 3.0
    sd.angle = math.radians(3)
    sol = bpy.data.objects.new("_sol", sd)
    sol.rotation_euler = (math.radians(50), 0, math.radians(-35))
    col.objects.link(sol)
    ad = bpy.data.lights.new("_area", "AREA")
    ad.energy = 300 * max(1.0, (hi - lo).length) ** 2
    ad.size = 2.0
    area = bpy.data.objects.new("_area", ad)
    c = (lo + hi) / 2
    area.location = c + Vector((-2.0, -2.5, 2.0)) * max(1.0, (hi - lo).length)
    area.rotation_euler = (c - area.location).to_track_quat("-Z", "Y").to_euler()
    col.objects.link(area)
    w = bpy.data.worlds.new("_mundo")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.57, 0.6, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    scene.world = w


def camara(scene, lo, hi, direccion, nombre):
    c = (lo + hi) / 2
    radio = max((hi - lo).length / 2, 0.08)
    cd = bpy.data.cameras.new(nombre)
    cd.lens = 50
    cd.clip_start = 0.005
    cd.clip_end = 100
    cam = bpy.data.objects.new(nombre, cd)
    scene.collection.objects.link(cam)
    d = Vector(direccion).normalized()
    dist = radio / math.tan(math.atan(18 / 50)) * 1.15
    cam.location = c + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    return cam


def main():
    a = parse_args()
    os.makedirs(a.out, exist_ok=True)
    nombre = a.nombre or a.funcion
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    col = bpy.data.collections.new("Pieza")
    scene.collection.children.link(col)
    mod = importlib.import_module(a.modulo)
    objs = getattr(mod, a.funcion)(col, f"Depto_Pieza_{nombre}", **json.loads(a.args))
    bpy.context.view_layer.update()
    mats = sorted({m.name for o in objs if o.type == "MESH" for m in o.data.materials if m})
    con_textura = []
    if a.texturas:
        import deco_paleta
        con_textura = [m for m in mats if deco_paleta.aplicar(m)]
    pts = [o.matrix_world @ v.co for o in objs if o.type == "MESH" for v in o.data.vertices]
    lo = Vector([min(p[k] for p in pts) for k in range(3)])
    hi = Vector([max(p[k] for p in pts) for k in range(3)])
    import deco_base as B
    info = {"modulo": a.modulo, "funcion": a.funcion, "args": json.loads(a.args),
            "objetos": {o.name: B.triangulos([o]) for o in objs if o.type == "MESH"},
            "triangulos": B.triangulos([o for o in objs if o.type == "MESH"]),
            "dimensiones_m": [round(v, 4) for v in (hi - lo)], "bbox_min": [round(v, 4) for v in lo],
            "bbox_max": [round(v, 4) for v in hi], "materiales": mats, "con_textura": con_textura}
    estudio(scene, lo, hi)
    scene.render.engine = "BLENDER_EEVEE"
    ee = scene.eevee
    ee.taa_render_samples = 32
    ee.use_gtao = True
    ee.use_soft_shadows = True
    ee.use_ssr = True
    ee.shadow_cube_size = "1024"
    ee.shadow_cascade_size = "2048"
    scene.view_settings.view_transform = "Filmic"
    w, h = (int(v) for v in a.size.split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.image_settings.file_format = "PNG"
    vistas = []
    for i, d in enumerate(((-0.75, -1.0, 0.55), (-1.0, 0.0, 0.22))):
        scene.camera = camara(scene, lo, hi, d, f"_cam{i}")
        ruta = os.path.join(a.out, f"_{nombre}_{i}.png")
        scene.render.filepath = ruta
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(ruta)
        arr = np.empty(w * h * 4, dtype=np.float32)
        im.pixels.foreach_get(arr)
        vistas.append(arr.reshape(h, w, 4))
        bpy.data.images.remove(im)
        os.remove(ruta)
    hoja = np.concatenate(vistas, axis=1)
    im = bpy.data.images.new("_hoja", w * 2, h)
    im.pixels.foreach_set(hoja.ravel())
    im.filepath_raw = os.path.join(a.out, f"{nombre}.png")
    im.file_format = "PNG"
    im.save()
    with open(os.path.join(a.out, f"{nombre}.json"), "w") as fh:
        json.dump(info, fh, indent=2, ensure_ascii=False)
    print("PREVIEW_OK", nombre, info["triangulos"], info["dimensiones_m"])


if __name__ == "__main__":
    main()
