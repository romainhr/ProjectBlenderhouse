"""Renderiza vistas de revisión de un archivo .blend en modo headless.

Uso:
    blender -b escena.blend --python tools/render_review.py -- --out review/01 [--target Casa] [--size 640]

Genera en la carpeta de salida:
    front.png, right.png, back.png, top.png, bottom.png, iso.png, iso_low.png (Workbench sólido)
    iso_wire.png                                        (mismo encuadre, con wireframe)
    contact.png                                         (hoja de contacto con las 6 vistas)
    stats.json                                          (bounding box, dimensiones, conteo de polígonos)

Pensado para el bucle: el agente construye/modifica -> renderiza -> mira las imágenes ->
compara con las fotos de referencia -> corrige. Funciona en CPU e Intel HD 4000 (Blender 3.6).
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True, help="carpeta de salida")
    p.add_argument("--target", default=None, help="nombre de objeto o colección a encuadrar (por defecto: todo lo visible)")
    p.add_argument("--size", type=int, default=640, help="resolución (px, cuadrado)")
    p.add_argument("--engine", default="WORKBENCH", choices=["WORKBENCH", "EEVEE", "CYCLES"])
    p.add_argument("--hide", default="", help="objetos o colecciones a ocultar en el render, separados por coma (p.ej. un cielo)")
    p.add_argument("--frente", default="-Y", choices=["-Y", "+Y"],
                   help="hacia dónde mira el frente del activo: -Y (por defecto, como Mesa) o +Y (Depto: fachada del balcón)")
    return p.parse_args(argv)


def hide_for_render(names):
    """Oculta en render los objetos/colecciones pedidos (no se guarda: el script no salva el .blend)."""
    for n in [s.strip() for s in names.split(",") if s.strip()]:
        if n in bpy.data.collections:
            for o in bpy.data.collections[n].all_objects:
                o.hide_render = True
        elif n in bpy.data.objects:
            bpy.data.objects[n].hide_render = True
        else:
            sys.exit(f"--hide: '{n}' no existe en este .blend")


def visible_mesh_objects(target):
    objs = []
    if target and target in bpy.data.collections:
        objs = [o for o in bpy.data.collections[target].all_objects if o.type == "MESH"]
    elif target and target in bpy.data.objects:
        root = bpy.data.objects[target]
        objs = [root] + [c for c in root.children_recursive if c.type == "MESH"]
        objs = [o for o in objs if o.type == "MESH"]
    else:
        objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]
    return objs


def world_bbox(objs):
    pts = []
    total_verts = sum(len(o.data.vertices) for o in objs)
    for o in objs:
        if total_verts <= 300_000:  # exacto: vértices reales (importa en objetos rotados)
            pts += [o.matrix_world @ v.co for v in o.data.vertices]
        else:  # aproximado: caja local transformada
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not pts:
        return Vector((-1, -1, -1)), Vector((1, 1, 1))
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def make_camera(name, center, radius, direction, ortho_scale):
    cam_data = bpy.data.cameras.new(name)
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho_scale
    cam_data.clip_end = radius * 20
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    d = Vector(direction).normalized()
    cam.location = center + d * radius * 5
    cam.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return cam


def main():
    args = parse_args()
    os.makedirs(args.out, exist_ok=True)
    scene = bpy.context.scene
    hide_for_render(args.hide)
    objs = [o for o in visible_mesh_objects(args.target) if not o.hide_render]
    lo, hi = world_bbox(objs)
    center = (lo + hi) / 2
    dims = hi - lo
    radius = max(dims.length / 2, 0.01)

    # Estadísticas útiles para comparar contra medidas de la referencia
    stats = {
        "objects": [o.name for o in objs],
        "bbox_min": list(lo),
        "bbox_max": list(hi),
        "dimensions_m": {"x": dims.x, "y": dims.y, "z": dims.z},
        "triangles": sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs),
        "faces": sum(len(o.data.polygons) for o in objs),
    }
    with open(os.path.join(args.out, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    # Motor y encuadre
    if args.engine == "WORKBENCH":
        scene.render.engine = "BLENDER_WORKBENCH"
        sh = scene.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
        sh.show_cavity = True
        sh.show_shadows = True
        sh.background_type = "WORLD"
        if scene.world is None:
            scene.world = bpy.data.worlds.new("_review_world")
        scene.world.color = (0.35, 0.35, 0.35)
    elif args.engine == "EEVEE":
        scene.render.engine = "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = 16
    else:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 32
    scene.render.resolution_x = scene.render.resolution_y = args.size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"

    axis_scale = max(dims.x, dims.y, dims.z) * 1.25
    f = 1 if args.frente == "+Y" else -1   # con el frente hacia +Y, la cámara "front" va en +Y y "right" en -X
    views = {
        "front": ((0, f, 0), max(dims.x, dims.z) * 1.25),
        "right": ((-f, 0, 0), max(dims.y, dims.z) * 1.25),
        "back": ((0, -f, 0), max(dims.x, dims.z) * 1.25),
        "top": ((0, 0, 1), max(dims.x, dims.y) * 1.25),
        "bottom": ((0, 0, -1), max(dims.x, dims.y) * 1.25),
        "iso": ((1, -1, 0.7), dims.length * 1.05),
        "iso_low": ((1, -1, -0.5), dims.length * 1.05),
    }
    old_cam = scene.camera
    for name, (direction, ortho_scale) in views.items():
        cam = make_camera(f"_review_{name}", center, radius, direction, max(ortho_scale, axis_scale * 0.5))
        scene.camera = cam
        scene.render.filepath = os.path.join(args.out, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        if name == "iso" and args.engine == "WORKBENCH":
            scene.display.shading.show_object_outline = True
            for o in objs:
                o.show_wire = True
            scene.display.shading.color_type = "SINGLE"
            scene.display.shading.single_color = (0.8, 0.8, 0.8)
            # Wireframe real: activar overlay no existe en render; usamos modificador temporal
            wires = []
            for o in objs:
                m = o.modifiers.new("_review_wire", "WIREFRAME")
                m.thickness = radius * 0.004
                m.use_replace = False
                wires.append((o, m))
            scene.render.filepath = os.path.join(args.out, "iso_wire.png")
            bpy.ops.render.render(write_still=True)
            for o, m in wires:
                o.modifiers.remove(m)
            scene.display.shading.color_type = "MATERIAL"
        bpy.data.objects.remove(cam, do_unlink=True)
    scene.camera = old_cam

    # Hoja de contacto con las vistas (2 filas x 3 columnas) usando el compositor no es
    # necesario: la armamos con el módulo de imágenes de Blender.
    try:
        names = ["front", "right", "back", "iso", "top", "bottom", "iso_low", "iso_wire"]
        tiles = [bpy.data.images.load(os.path.join(args.out, f"{n}.png")) for n in names if os.path.exists(os.path.join(args.out, f"{n}.png"))]
        s = args.size
        cols, rows = 4, math.ceil(len(tiles) / 4)
        sheet = bpy.data.images.new("_contact", s * cols, s * rows)
        buf = [0.0] * (s * cols * s * rows * 4)
        for i, im in enumerate(tiles):
            px = list(im.pixels)
            cx, cy = (i % cols) * s, (rows - 1 - i // cols) * s
            for y in range(s):
                src = (y * s) * 4
                dst = ((cy + y) * s * cols + cx) * 4
                buf[dst : dst + s * 4] = px[src : src + s * 4]
        sheet.pixels = buf
        sheet.filepath_raw = os.path.join(args.out, "contact.png")
        sheet.file_format = "PNG"
        sheet.save()
    except Exception as e:  # la hoja es opcional
        print("contact sheet skipped:", e)

    print("REVIEW_DONE", json.dumps(stats["dimensions_m"]))


if __name__ == "__main__":
    main()
