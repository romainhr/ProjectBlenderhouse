"""Renderiza las cámaras de revisión de un interior (planta, maqueta, vistas a la altura de los ojos).

Uso:
    blender -b build/depto.blend --python tools/render_interior.py -- --out review/depto_02 \
        [--prefix Depto_Cam_] [--only Planta,Living] [--engine WORKBENCH|EEVEE|CYCLES] [--size 960x640] \
        [--samples 32] [--planta-plana]

Cada cámara cuyo nombre empieza con --prefix se renderiza a <out>/<sufijo>.png. Custom properties
opcionales en la cámara (objeto):
    "resolucion": [ancho, alto]     resolución propia (p.ej. la planta ortográfica)
    "ocultar": "ColA,ObjB"          objetos o colecciones a ocultar sólo para esa cámara (p.ej. el cielo)
Con --planta-plana la cámara "Planta" se renderiza en Workbench plano con el color de objeto
(object.color), sin antialiasing, para compararla píxel a píxel con el plano (tools/compare_plan.py);
--planta-solo limita esa planta a unas colecciones (p.ej. sólo muros, sin puertas ni muebles).

Genera contact.png (vistas en perspectiva, 3 columnas) y renders.json. Funciona en CPU (Blender 3.6).
"""
import argparse
import json
import math
import os
import sys

import bpy
import numpy as np


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--prefix", default="Depto_Cam_")
    p.add_argument("--only", default="", help="sufijos de cámara separados por coma (por defecto, todas)")
    p.add_argument("--engine", default="WORKBENCH", choices=["WORKBENCH", "EEVEE", "CYCLES"])
    p.add_argument("--size", default="960x640")
    p.add_argument("--samples", type=int, default=32)
    p.add_argument("--planta-plana", action="store_true")
    p.add_argument("--planta-solo", default="",
                   help="con --planta-plana: colecciones que se dibujan en la planta (el resto se oculta), p.ej. Depto_Muros")
    return p.parse_args(argv)


def set_hidden(names, value):
    changed = []
    for n in [s.strip() for s in names.split(",") if s.strip()]:
        objs = (list(bpy.data.collections[n].all_objects) if n in bpy.data.collections
                else [bpy.data.objects[n]] if n in bpy.data.objects else None)
        if objs is None:
            print(f"AVISO ocultar: '{n}' no existe en este .blend (¿fase aún no construida?)")
            continue
        for o in objs:
            if o.hide_render != value:
                o.hide_render = value
                changed.append(o)
    return changed


def config_engine(scene, engine, samples):
    # Todo lo que config_planta_plana cambia se fija aquí también: nada se arrastra entre cámaras.
    scene.display.shading.show_object_outline = False
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("_review_world")
    if engine == "WORKBENCH":
        scene.render.engine = "BLENDER_WORKBENCH"
        sh = scene.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
        sh.show_cavity = True
        sh.cavity_type = "WORLD"
        sh.show_shadows = False
        sh.background_type = "WORLD"
        scene.world.color = (0.8, 0.85, 0.9)
        scene.display.render_aa = "8"
        scene.view_settings.view_transform = "Standard"
    elif engine == "EEVEE":
        scene.render.engine = "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = samples
        scene.view_settings.view_transform = "Filmic"
    else:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.view_settings.view_transform = "Filmic"


def config_planta_plana(scene):
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "FLAT"
    sh.color_type = "OBJECT"
    sh.show_cavity = False
    sh.show_shadows = False
    sh.show_object_outline = False
    sh.background_type = "WORLD"
    scene.world.color = (1.0, 1.0, 1.0)
    scene.display.render_aa = "OFF"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0


def load_rgb(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)  # fila 0 = abajo


def contact_sheet(paths, out, cols=3, tile_w=480):
    tiles = [load_rgb(p) for p in paths]
    if not tiles:
        return
    tile_h = int(round(tile_w * tiles[0].shape[0] / tiles[0].shape[1]))
    rows = math.ceil(len(tiles) / cols)
    sheet = np.ones((rows * tile_h, cols * tile_w, 4), dtype=np.float32)
    for i, t in enumerate(tiles):
        ys = (np.arange(tile_h) * t.shape[0] / tile_h).astype(int)
        xs = (np.arange(tile_w) * t.shape[1] / tile_w).astype(int)
        small = t[ys][:, xs]
        r, c = i // cols, i % cols
        y0 = (rows - 1 - r) * tile_h  # la imagen de Blender se guarda desde abajo
        sheet[y0:y0 + tile_h, c * tile_w:(c + 1) * tile_w] = small
    im = bpy.data.images.new("_contact", cols * tile_w, rows * tile_h)
    im.pixels.foreach_set(sheet.ravel())
    im.filepath_raw = out
    im.file_format = "PNG"
    im.save()


def main():
    args = parse_args()
    os.makedirs(args.out, exist_ok=True)
    scene = bpy.context.scene
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    cams = sorted((o for o in scene.objects if o.type == "CAMERA" and o.name.startswith(args.prefix)),
                  key=lambda o: o.name)
    if only:
        cams = [c for c in cams if c.name[len(args.prefix):] in only]
    w, h = (int(v) for v in args.size.lower().split("x"))
    info, persp = [], []
    for cam in cams:
        suf = cam.name[len(args.prefix):]
        config_engine(scene, args.engine, args.samples)
        plana = args.planta_plana and suf == "Planta"
        if plana:
            config_planta_plana(scene)
        res = cam.get("resolucion")
        scene.render.resolution_x, scene.render.resolution_y = (int(res[0]), int(res[1])) if res else (w, h)
        scene.render.resolution_percentage = 100
        changed = set_hidden(cam.get("ocultar", ""), True)
        if plana and args.planta_solo:
            dejar = {o for n in args.planta_solo.split(",") if n.strip() in bpy.data.collections
                     for o in bpy.data.collections[n.strip()].all_objects}
            for o in scene.objects:
                if o.type == "MESH" and o not in dejar and not o.hide_render:
                    o.hide_render = True
                    changed.append(o)
        scene.camera = cam
        path = os.path.abspath(os.path.join(args.out, f"{suf}.png"))
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        for o in changed:
            o.hide_render = False
        info.append({"camara": cam.name, "archivo": os.path.basename(path), "tipo": cam.data.type,
                     "lente_mm": cam.data.lens if cam.data.type == "PERSP" else None,
                     "ubicacion": list(cam.matrix_world.translation), "motor": "PLANA" if plana else args.engine,
                     "resolucion": [scene.render.resolution_x, scene.render.resolution_y]})
        if cam.data.type == "PERSP" and not res:
            persp.append(path)
        print(f"RENDER {suf} -> {path}")
    if persp:
        contact_sheet(persp, os.path.abspath(os.path.join(args.out, "contact.png")))
    with open(os.path.join(args.out, "renders.json"), "w") as f:
        json.dump(info, f, indent=2)
    print("INTERIOR_DONE", len(info))


if __name__ == "__main__":
    main()
