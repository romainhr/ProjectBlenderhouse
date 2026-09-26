"""Renders de detalle de las piezas interactivas nuevas (fase "07 detalle interactivo": nevera, cajones y
puertas de cocina, clósets) con las puertas y cajones abiertos, para revisar a ojo interpenetraciones, piezas
flotando o problemas de escala antes de exportar.

Uso:
    blender -b build/depto.blend --python tools/render_detalle_interactivo.py -- \
        --out review/depto_07_detalle [--engine EEVEE] [--samples 48]

No guarda el .blend: abre en memoria los nodos de ABRIR (según su propia angulo_abierta_deg o
recorrido_m + eje_apertura; si ya vienen abiertos de fábrica, se dejan tal cual) y renderiza con las cámaras
existentes que ya encuadran cada zona (Depto_Cam_Cocina, Depto_Cam_Paso_D1, Depto_Cam_Paso_D2). Pendiente para
otra sesión: cámaras de detalle propias, más cerca de la nevera y de cada clóset (se intentó apuntarlas por la
caja envolvente de sus objetos "_Cuerpo", pero el encuadre salió mal, demasiado cerca).
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_03_formas as F3  # noqa: E402 (sólo para leer F3.CLOSETS; no llama a F3.main())
import depto_plano as P  # noqa: E402

ABRIR = [
    "Depto_Mueble_Nevera_Puerta", "Depto_Mueble_Nevera_Freezer",
    "Depto_Mueble_Cocina_Cajon1Sup", "Depto_Mueble_Cocina_Cajon1Inf",
    "Depto_Mueble_Cocina_Cajon2Inf", "Depto_Mueble_Cocina_Cajon3Sup",
    "Depto_Mueble_Cocina_PuertaLavaplatos1", "Depto_Mueble_Cocina_PuertaLavaplatos2",
    "Depto_Mueble_Cocina_PuertaAlta1", "Depto_Mueble_Cocina_PuertaAlta4",
    "Depto_Closet_D1_Norte_PuertaA", "Depto_Closet_D1_Norte_PuertaB",
    "Depto_Closet_D1_Sur_PuertaA", "Depto_Closet_D1_Sur_PuertaB", "Depto_Closet_D1_Sur_Cajon1",
    "Depto_Closet_D2_Norte_PuertaA", "Depto_Closet_D2_Norte_PuertaB",
    "Depto_Closet_D2_Sur_PuertaA", "Depto_Closet_D2_Sur_PuertaB",
    "Depto_Closet_D2_Sur_Cajon1", "Depto_Closet_D2_Sur_Cajon2",
]


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--engine", default="EEVEE", choices=["EEVEE", "WORKBENCH"])
    p.add_argument("--samples", type=int, default=48)
    p.add_argument("--size", default="960x720")
    return p.parse_args(argv)


def abrir(nombre):
    o = bpy.data.objects.get(nombre)
    if o is None:
        print(f"AVISO: no existe {nombre!r} (¿fase 3 aún no la crea?)")
        return None
    if o.get("abierta"):
        return o                                  # ya viene abierta de fábrica (p.ej. el cajón de cubiertos)
    if "puerta" in o:
        o.rotation_euler.z = math.radians(o["angulo_abierta_deg"])
    elif "recorrido_m" in o:
        eje = Vector(o["eje_apertura"])
        o.location = o.location + eje * o["recorrido_m"]
    return o


def camara_closet(scene, nombre, cid, base_cam):
    """Cámara en la misma posición que `base_cam` (una cámara del paso ya verificada, con holgura a todo
    sólido), pero apuntada de frente a la celda `cid` de F3.CLOSETS (a la altura media de la barra o la
    repisa), para que el hueco de la hoja abierta se vea de frente y no en escorzo."""
    _, x0, x1, yf, yfr = next(c for c in F3.CLOSETS if c[0] == cid)
    xc = (x0 + x1) / 2
    yc = (yf + yfr) / 2
    objetivo = Vector((*P.a_blender(xc, yc), 1.3))
    cd = bpy.data.cameras.new(nombre)
    cd.lens = 24
    cd.clip_start = 0.02
    cam = bpy.data.objects.new(nombre, cd)
    scene.collection.objects.link(cam)
    cam.location = base_cam.matrix_world.translation
    d = (objetivo - cam.location).normalized()
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    return cam


def config_eevee(scene, samples):
    scene.render.engine = "BLENDER_EEVEE"
    ee = scene.eevee
    ee.taa_render_samples = samples
    ee.use_gtao = True
    ee.use_soft_shadows = True
    ee.use_ssr = True
    ee.use_bloom = True
    ee.bloom_intensity = 0.03
    scene.view_settings.view_transform = "Filmic"
    scene.render.image_settings.file_format = "PNG"


def main():
    a = parse_args()
    os.makedirs(a.out, exist_ok=True)
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    abiertos = [abrir(n) for n in ABRIR]
    abiertos = [o for o in abiertos if o is not None]
    bpy.context.view_layer.update()
    if a.engine == "EEVEE":
        config_eevee(scene, a.samples)
    else:
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "MATERIAL"
    w, h = (int(v) for v in a.size.lower().split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    hechos = []
    # 1) cámaras existentes que ya encuadran cocina y los pasos de los clósets
    for suf in ("Cocina", "Paso_D1", "Paso_D2"):
        cam = bpy.data.objects.get(f"Depto_Cam_{suf}")
        if cam is None:
            continue
        ocultar = [bpy.data.objects[n] for n in cam.get("ocultar", "").split(",")
                   if n.strip() and n.strip() in bpy.data.objects]
        for o in ocultar:
            o.hide_render = True
        scene.camera = cam
        ruta = os.path.join(a.out, f"{suf}_abierto.png")
        scene.render.filepath = ruta
        bpy.ops.render.render(write_still=True)
        for o in ocultar:
            o.hide_render = False
        hechos.append(ruta)
        print("RENDER", ruta)
    # 2) una cámara por celda de clóset (misma posición que la cámara del paso, apuntada de frente a la celda)
    for suf, cid in (("Paso_D1", "D1_Norte"), ("Paso_D1", "D1_Sur"), ("Paso_D2", "D2_Norte"),
                     ("Paso_D2", "D2_Sur")):
        base_cam = bpy.data.objects.get(f"Depto_Cam_{suf}")
        if base_cam is None:
            continue
        scene.camera = camara_closet(scene, f"_cam_{cid}", cid, base_cam)
        ruta = os.path.join(a.out, f"Closet_{cid}_abierto.png")
        scene.render.filepath = ruta
        bpy.ops.render.render(write_still=True)
        hechos.append(ruta)
        print("RENDER", ruta)
    print("DETALLE_INTERACTIVO_DONE", len(hechos))


if __name__ == "__main__":
    main()
