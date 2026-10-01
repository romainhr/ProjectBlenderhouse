"""Valida un GLB exportado reimportándolo en una escena vacía y comparándolo con su manifiesto.

Uso:
    blender -b --python-exit-code 1 --python tools/validar_glb.py -- --glb exports/depto.glb \
        --manifiesto exports/manifest.json --activo depto --out review/depto_06 [--ocultar Depto_Cielo,Depto_Palier_Cielo] \
        [--excluir-dims Depto_Ext_]

Compara mallas, triángulos, materiales y dimensiones (±1 mm) con la entrada del manifiesto, verifica que haya
imágenes y renderiza reimport_iso.png y reimport_top.png. Con --excluir-dims, las dimensiones se miden sin esos
prefijos (el exterior del bloque 08, cuyas mallas y triángulos se comparan con manifiesto[activo]["exterior"]), y (Eevee con un sol: Workbench no muestra bien los
materiales importados sin imagen). Sale con código 1 si algo no
coincide. Escribe <out>/reimport.json.
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--glb", required=True)
    p.add_argument("--manifiesto", required=True)
    p.add_argument("--activo", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--ocultar", default="", help="prefijos de objetos a ocultar en los renders (p.ej. el cielo)")
    p.add_argument("--excluir-dims", default="", help="prefijos que no cuentan en las dimensiones (p.ej. el exterior)")
    return p.parse_args(argv)


def render(scene, objs, out, direccion, nombre):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector([min(p[k] for p in pts) for k in range(3)])
    hi = Vector([max(p[k] for p in pts) for k in range(3)])
    centro, dims = (lo + hi) / 2, hi - lo
    cd = bpy.data.cameras.new(nombre)
    cd.type = "ORTHO"
    cd.ortho_scale = max(dims.x, dims.y) * 1.25
    cd.clip_end = 200
    cam = bpy.data.objects.new(nombre, cd)
    scene.collection.objects.link(cam)
    d = Vector(direccion).normalized()
    cam.location = centro + d * dims.length * 3
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    scene.render.filepath = os.path.join(out, f"{nombre}.png")
    bpy.ops.render.render(write_still=True)


def main():
    a = parse_args()
    os.makedirs(a.out, exist_ok=True)
    with open(a.manifiesto) as fh:
        esp = json.load(fh)[a.activo]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(a.glb))
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    objs = [o for o in scene.objects if o.type == "MESH"]
    tris = 0
    for o in objs:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    fuera = tuple(x.strip() for x in a.excluir_dims.split(",") if x.strip())
    medidos = [o for o in objs if not (fuera and o.name.startswith(fuera))]
    pts = [o.matrix_world @ v.co for o in medidos for v in o.data.vertices]
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    dims = {"x": hi[0] - lo[0], "y": hi[1] - lo[1], "z": hi[2] - lo[2]}
    mats = sorted({m.name for o in objs for m in o.data.materials if m})
    imgs = [i for i in bpy.data.images if i.size[0] > 0]
    fallos = []
    if len(objs) != esp["mallas"]:
        fallos.append(f"mallas {len(objs)} != {esp['mallas']}")
    if tris != esp["triangulos"]:
        fallos.append(f"triángulos {tris} != {esp['triangulos']}")
    if mats != sorted(esp["materiales"]):
        fallos.append(f"materiales distintos: {sorted(set(mats) ^ set(esp['materiales']))}")
    for k, v in dims.items():
        if abs(v - esp["dimensiones_m"][k]) > 0.001:
            fallos.append(f"dimensión {k} {v:.4f} != {esp['dimensiones_m'][k]}")
    if not imgs:
        fallos.append("el GLB no trae imágenes")
    ext = [o for o in objs if fuera and o.name.startswith(fuera)]
    tris_ext = 0
    for o in ext:
        tris_ext += len(o.data.loop_triangles)
    if fuera and "exterior" in esp:
        if len(ext) != esp["exterior"]["mallas"] or tris_ext != esp["exterior"]["triangulos"]:
            fallos.append(f"exterior: {len(ext)} mallas y {tris_ext} triángulos != {esp['exterior']}")
    extras = sorted(o.name for o in scene.objects if "puerta" in o or "recorrido_m" in o)
    res = {"mallas": len(objs), "triangulos": tris, "materiales": len(mats), "imagenes": len(imgs),
           "dimensiones_m": {k: round(v, 4) for k, v in dims.items()}, "nodos_con_extras_moviles": extras,
           "exterior": {"mallas": len(ext), "triangulos": tris_ext},
           "fallos": fallos}
    with open(os.path.join(a.out, "reimport.json"), "w") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    prefijos = tuple(s.strip() for s in a.ocultar.split(",") if s.strip())
    vis = []
    for o in objs:
        if prefijos and o.name.startswith(prefijos):
            o.hide_render = True
        else:
            vis.append(o)
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 16
    scene.eevee.use_gtao = True
    scene.view_settings.view_transform = "Filmic"
    scene.world = bpy.data.worlds.new("_w")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.75, 0.8, 0.88, 1.0)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    sd = bpy.data.lights.new("_sol", "SUN")
    sd.energy = 3.0
    sol = bpy.data.objects.new("_sol", sd)
    sol.rotation_euler = (math.radians(50), 0, math.radians(150))
    scene.collection.objects.link(sol)
    scene.render.resolution_x, scene.render.resolution_y = 1100, 800
    render(scene, vis, a.out, (0.9, 0.8, 1.0), "reimport_iso")
    render(scene, vis, a.out, (0, 0, 1), "reimport_top")
    for f in fallos:
        print("FALLA", f)
    print("VALIDACION_GLB", json.dumps({k: res[k] for k in ("mallas", "triangulos", "materiales", "imagenes")}),
          "OK" if not fallos else f"{len(fallos)} fallas")
    if fallos:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
