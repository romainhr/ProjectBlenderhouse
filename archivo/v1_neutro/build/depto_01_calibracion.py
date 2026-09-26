"""Fase 1 (calibración) del activo Depto: blend maestro, plano de referencia a escala y cámara de planta.

Uso (o todo el pipeline con build/depto_run.sh):
    blender -b --python-exit-code 1 --python build/depto_01_calibracion.py

Idempotente: parte de una escena de fábrica vacía (esta fase CREA el maestro; las siguientes lo
cargan y reconstruyen sólo lo suyo). Guarda build/depto.blend sólo si las pruebas pasan, y lo
sella con scene["depto_fase01"] (primer eslabón de la cadena de build/depto_sellos.py: este script,
depto_plano.py y depto_sellos.py) para que las fases siguientes comprueben de qué maestro parten.

Pruebas (review/depto_01/calibracion.json):
1. Imagen: renderiza el plano texturizado desde Depto_Cam_Planta (1000x1000, 2 px de render por px
   de plano) y lo compara con el PNG ampliado 2x: mejor desplazamiento (0, 0) y diferencia ~0.
   Valida que cámara y referencia coinciden, pero NO la escala ni el sentido de a_blender (ambas
   usan la misma escala).
2. Mapeo: para 5 puntos del plano (4 esquinas exteriores y el centro) compara depto_plano.a_blender
   con la posición que tiene ese píxel en la referencia colocada en Blender (matrix_world). Detecta
   un espejo o una rotación equivocada entre los muros (que usan a_blender) y la referencia.
La escala en sí (m/px) no se puede validar sin una cota real: viene del brief.
"""
import json
import math
import os
import sys

import bpy
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_plano as P  # noqa: E402
import depto_sellos as S  # noqa: E402

PLANO_PNG = os.path.join(RAIZ, "ref", "plano", "plano_depto.png")
OUT_BLEND = os.path.join(RAIZ, "build", "depto.blend")
OUT_REVIEW = os.path.join(RAIZ, "review", "depto_01")

PLANO_PX = 500                       # ref/plano/plano_depto.png es de 500x500
LADO_PLANO_M = PLANO_PX * P.M_POR_PX  # 9,50 m: lado real que cubre la imagen completa
Z_REF = 0.003                        # la referencia queda 3 mm sobre el piso terminado (visible en el viewport)
RES_PLANTA = 1000                    # 2 px de render por px de plano: comparación exacta
Z_CAM_PLANTA = 20.0                  # altura de la cámara ortográfica de planta
CORTE_PLANTA = 1.20                  # convención de planta de arquitectura: corte horizontal a ~1,2 m
BUSQUEDA_PX = 3                      # desplazamientos probados en la prueba (px de render)


def colecciones():
    root = bpy.data.collections.new("Depto")
    bpy.context.scene.collection.children.link(root)
    subs = {}
    for n in ("Depto_Ref", "Depto_Camaras"):
        c = bpy.data.collections.new(n)
        root.children.link(c)
        subs[n] = c
    return root, subs


def referencia_plano(col):
    img = bpy.data.images.load(PLANO_PNG, check_existing=True)
    img.name = "plano_depto.png"
    cx, cy = P.a_blender(PLANO_PX / 2, PLANO_PX / 2)
    rot = (0.0, 0.0, -math.pi / 2)   # derecha de la imagen -> -Y ; arriba de la imagen -> +X (ver depto_plano.a_blender)

    # 1) Empty de imagen: la referencia para trabajar en el viewport.
    emp = bpy.data.objects.new("Depto_Ref_Plano", None)
    emp.empty_display_type = "IMAGE"
    emp.data = img
    emp.empty_display_size = LADO_PLANO_M
    emp.empty_image_offset = (-0.5, -0.5)
    emp.location = (cx, cy, Z_REF)
    emp.rotation_euler = rot
    emp.color[3] = 0.6
    emp.use_empty_image_alpha = True
    col.objects.link(emp)

    # 2) Plano de malla con la misma imagen: los empties no se renderizan, así que la prueba de
    #    calibración usa esta malla. Queda oculta en viewport y render.
    h = LADO_PLANO_M / 2
    me = bpy.data.meshes.new("Depto_Ref_PlanoMalla")
    me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for li, (u, v) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[li].uv = (u, v)
    mat = bpy.data.materials.new("Depto_Ref_PlanoMat")
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Closest"
    nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes.active = tex             # Workbench (color TEXTURE) usa el nodo de imagen activo
    me.materials.append(mat)
    obj = bpy.data.objects.new("Depto_Ref_PlanoMalla", me)
    obj.location = (cx, cy, Z_REF)
    obj.rotation_euler = rot
    obj.hide_render = True
    obj.hide_viewport = True
    col.objects.link(obj)
    return emp, obj


def camara_planta(col):
    cd = bpy.data.cameras.new("Depto_Cam_Planta")
    cd.type = "ORTHO"
    cd.ortho_scale = LADO_PLANO_M
    cd.clip_start = Z_CAM_PLANTA - CORTE_PLANTA   # todo lo que está sobre el corte (dinteles, cielo) no se ve
    cd.clip_end = 50.0
    cam = bpy.data.objects.new("Depto_Cam_Planta", cd)
    cx, cy = P.a_blender(PLANO_PX / 2, PLANO_PX / 2)
    cam.location = (cx, cy, Z_CAM_PLANTA)
    cam.rotation_euler = (0.0, 0.0, -math.pi / 2)  # arriba de la imagen = +X, como el plano
    cam["resolucion"] = [RES_PLANTA, RES_PLANTA]
    # Colecciones de la fase 2. En la planta no se ve el cielo, y las losas de piso se ocultan porque su
    # cara superior coincide con la base de los muros cortados (el corte deja ver esa base, en negro).
    cam["ocultar"] = "Depto_Cielo,Depto_Losas,Depto_Balcon_Losa"
    col.objects.link(cam)
    return cam


def pixels(path):
    im = bpy.data.images.load(path)
    w, hh = im.size
    a = np.empty(w * hh * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(hh, w, 4)[:, :, :3].mean(axis=2)


def prueba_calibracion(malla, cam):
    scene = bpy.context.scene
    os.makedirs(OUT_REVIEW, exist_ok=True)
    malla.hide_render = False
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "FLAT"
    sh.color_type = "TEXTURE"
    sh.show_cavity = False
    sh.show_shadows = False
    scene.display.render_aa = "OFF"
    scene.view_settings.view_transform = "Standard"
    scene.render.resolution_x = scene.render.resolution_y = RES_PLANTA
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    out = os.path.join(OUT_REVIEW, "calib_planta.png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    malla.hide_render = True

    ren = pixels(out)
    plano = pixels(PLANO_PNG)
    plano2 = np.repeat(np.repeat(plano, 2, axis=0), 2, axis=1)  # ampliación 2x vecino más cercano
    m = BUSQUEDA_PX + 1
    resultados = {}
    for dy in range(-BUSQUEDA_PX, BUSQUEDA_PX + 1):
        for dx in range(-BUSQUEDA_PX, BUSQUEDA_PX + 1):
            a = ren[m + dy:RES_PLANTA - m + dy, m + dx:RES_PLANTA - m + dx]
            b = plano2[m:RES_PLANTA - m, m:RES_PLANTA - m]
            resultados[(dx, dy)] = float(np.abs(a - b).mean())
    mejor = min(resultados, key=resultados.get)
    res = {
        "mejor_desplazamiento_px_render": list(mejor),
        "diferencia_media_en_mejor": resultados[mejor],
        "diferencia_media_en_0_0": resultados[(0, 0)],
        "px_render_por_px_plano": RES_PLANTA / PLANO_PX,
        "m_por_px_plano": P.M_POR_PX,
        "ok": mejor == (0, 0) and resultados[(0, 0)] < 0.01,
    }
    print("CALIBRACION", json.dumps(res))
    return res


def prueba_mapeo(*refs):
    """a_blender(px) debe caer donde está ese píxel en cada referencia colocada en Blender.

    Se usa matrix_basis (posición/rotación/escala del objeto, sin padre) y no matrix_world: la malla
    está deshabilitada en el viewport y el depsgraph no le calcula matrix_world en headless.
    """
    from mathutils import Vector
    puntos = [(P.X["W_O"], P.Y["N_O"]), (P.X["E_O"], P.Y["N_O"]), (P.X["W_O"], P.Y["S_O"]),
              (P.X["E_O"], P.Y["S_O"]), (PLANO_PX / 2, PLANO_PX / 2)]
    h = LADO_PLANO_M / 2
    err = 0.0
    for ref in refs:
        assert ref.parent is None
        for x, y in puntos:
            local = Vector((x / PLANO_PX * 2 * h - h, h - y / PLANO_PX * 2 * h, 0.0))  # imagen: +x derecha, +y arriba
            w = ref.matrix_basis @ local
            bx, by = P.a_blender(x, y)
            err = max(err, abs(w.x - bx), abs(w.y - by))
    return err


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
    scene["activo"] = "Depto"
    scene["m_por_px_plano"] = P.M_POR_PX

    root, subs = colecciones()
    emp, malla = referencia_plano(subs["Depto_Ref"])
    cam = camara_planta(subs["Depto_Camaras"])
    scene.camera = cam
    bpy.context.view_layer.update()

    res = prueba_calibracion(malla, cam)
    res["error_mapeo_m"] = prueba_mapeo(malla, emp)   # el empty de imagen usa el mismo tamaño y offset centrado
    res["ok"] = res["ok"] and res["error_mapeo_m"] < 1e-4   # 0,1 mm: precisión de float32 a ~5 m del origen
    with open(os.path.join(OUT_REVIEW, "calibracion.json"), "w") as f:
        json.dump(res, f, indent=2)
    print("MAPEO error máximo (m):", res["error_mapeo_m"])
    assert res["ok"], f"la calibración no pasa: {res}"

    # Sólo si pasa: configuración de render neutra, sello y guardado del maestro.
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.light = "STUDIO"
    S.sellar(scene, "01")   # cadena de sellos: build/depto_sellos.py
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()
    print(f"FASE_OK Depto_01_calibracion {len(root.all_objects)} 0 sello={scene['depto_fase01']}")


if __name__ == "__main__":
    main()
