"""Renders de revisión de la fase 07b: clósets y nevera abiertos, noche con las luces cálidas por grupo, primer
plano de interruptores y un día normal del living.

Uso:
    blender -b build/depto.blend --python tools/render_07b.py -- --out review/depto_07b \
        [--solo closet_D1_colgar,noche_living] [--samples 64] [--size 1280x800]

No guarda el .blend. Para cada vista: abre las piezas móviles que pide (con su propio angulo_abierta_deg o
recorrido_m + eje_apertura, como el visor), cierra las que pide, prende sólo los grupos de luz indicados (las
luces de los otros grupos se ocultan y sus ampolletas pasan a un material apagado, porque el emisivo es uno solo
para todas) y elige mundo de día (el Depto_Mundo de la fase 5, con sol) o de noche (cielo HDRI de Poly Haven casi
apagado y sin sol). Escribe <out>/<vista>.png y <out>/renders.json = [{archivo, que_muestra, ...}].

Supuestos de revisión (no van al GLB): luz interior de la nevera (LED frío de 5 W, sólo en la vista de la nevera)
y un volumen de irradiancia horneado para la luz rebotada de Eevee en las vistas de noche (--sin-gi lo omite).
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_plano as P  # noqa: E402

HDRI_NOCHE = os.path.join(RAIZ, "assets", "hdri", "kloppenheim_02_puresky", "kloppenheim_02_puresky_1k.hdr")
TODOS = "*"

# vista: cámara (pos px, z, objetivo px, z objetivo, lente mm) o nombre de una cámara del maestro; abrir, cerrar,
# grupos de luz encendidos, mundo, exposición y descripción
VISTAS = {
    "closet_D1_colgar": dict(
        cam=((303.5, 119.5), 1.45, (303.5, 40.0), 1.10, 15.0), mundo="dia", luces=("paso_d1",), expo=0.4,
        abrir=("Depto_Closet_D1_Norte_PuertaA",),
        texto="Clóset de colgar del dormitorio principal (D1_Norte) con la hoja A corrida: barra de lado a lado con "
              "soportes, perchas de madera, abrigo, vestidos, chaqueta, camisas, suéter y pantalones; maletero con "
              "caja y mantas; zapatos en el piso. Luz del paso encendida."),
    "closet_D1_interior": dict(
        cam=((315.4, 121.0), 1.32, (315.4, 40.0), 1.12, 12.0), mundo="dia", luces=("paso_d1",), expo=0.4,
        ocultar=("Depto_Closet_D1_Norte_PuertaA", "Depto_Closet_D1_Norte_PuertaB"),
        texto="Vista de revisión del mismo clóset con las dos hojas ocultas (las correderas sólo dejan ver la mitad "
              "a la vez): la barra completa de costado a costado con sus 11 prendas."),
    "closet_D1_repisas": dict(
        cam=((329.0, 64.0), 1.42, (304.0, 140.0), 0.95, 12.0), mundo="dia", luces=("paso_d1",), expo=0.4,
        abrir=("Depto_Closet_D1_Sur_PuertaA", "Depto_Closet_D1_Sur_Cajon2"),
        texto="Clóset de repisas del dormitorio principal (D1_Sur), hoja A corrida y cajón de arriba abierto "
              "(calcetines): columna izquierda con 2 cajones, suéteres y maleta; derecha con zapatos, ropa "
              "doblada y caja."),
    "closet_D2_colgar": dict(
        cam=((304.5, 448.0), 1.45, (304.5, 375.0), 1.10, 15.0), mundo="dia", luces=("paso_d2",), expo=0.4,
        abrir=("Depto_Closet_D2_Norte_PuertaA",),
        texto="Clóset de colgar del segundo dormitorio (D2_Norte), hoja A corrida: barra doble (camisas, "
              "poleras y chaquetas arriba; pantalones en perchas de pantalón abajo), perchas de alambre negro, "
              "cajas en el maletero y zapatillas y botas en el piso."),
    "closet_D2_interior": dict(
        cam=((316.4, 449.5), 1.32, (316.4, 380.0), 1.10, 12.0), mundo="dia", luces=("paso_d2",), expo=0.4,
        ocultar=("Depto_Closet_D2_Norte_PuertaA", "Depto_Closet_D2_Norte_PuertaB"),
        texto="Vista de revisión del clóset de colgar del segundo dormitorio con las hojas ocultas: barra doble "
              "completa (13 prendas arriba y 7 pantalones abajo)."),
    "closet_D2_repisas": dict(
        cam=((331.0, 404.5), 1.42, (305.0, 470.0), 0.95, 12.0), mundo="dia", luces=("paso_d2",), expo=0.4,
        abrir=("Depto_Closet_D2_Sur_PuertaA", "Depto_Closet_D2_Sur_Cajon3", "Depto_Closet_D2_Sur_Cajon2"),
        texto="Clóset de repisas del segundo dormitorio (D2_Sur), hoja A corrida y los dos cajones de arriba "
              "abiertos (calcetines y poleras dobladas): 3 cajones, ropa doblada, zapatos y cajas."),
    "nevera_abierta": dict(
        cam=((338.0, 240.0), 1.50, (400.0, 280.0), 0.95, 14.0), mundo="dia", luces=("cocina_techo",), expo=0.2,
        abrir=("Depto_Mueble_Nevera_Puerta", "Depto_Mueble_Nevera_Freezer"), led_nevera=True,
        texto="Nevera abierta (puerta a 100° y cajón freezer): forro blanco, dos estantes de vidrio, cajón de "
              "verduras con frente esmerilado, alimentos (lácteos, huevos, fruta, frascos, cartones), balcones "
              "de la contrapuerta con botellas y salsas, y congelados en el freezer. LED interior sólo de revisión."),
    "noche_living": dict(
        cam="Depto_Cam_Living", mundo="noche", luces=TODOS, expo=0.6,
        texto="Noche: living con el colgante de techo, la lámpara de arco y, al fondo, el colgante del comedor "
              "del balcón (2700 K). Sol apagado y cielo nocturno casi negro."),
    "noche_cocina": dict(
        cam="Depto_Cam_Cocina", mundo="noche", luces=TODOS, expo=0.6,
        texto="Noche: cocina con sus dos colgantes de jaula a 3000 K."),
    "noche_dorm1": dict(
        cam="Depto_Cam_Dorm1", mundo="noche", luces=TODOS, expo=0.6,
        texto="Noche: dormitorio principal con el colgante de techo y la lámpara del velador (2700 K)."),
    "noche_bano1": dict(
        cam="Depto_Cam_Bano1", mundo="noche", luces=TODOS, expo=0.6,
        texto="Noche: baño principal con su colgante de jaula a 3000 K."),
    "interruptor_dorm1_doble": dict(
        cam=((229.0, 131.0), 1.36, (250.0, 170.25), 1.02, 24.0), mundo="dia", luces=(), expo=0.3,
        cerrar=("Depto_Puerta_D1_Hoja",),
        texto="Interruptor doble del dormitorio principal (techo y paso de los clósets) a 1,10 m, a 0,10 m del "
              "marco del lado de la manilla, con la puerta D1 cerrada."),
    "interruptor_hall": dict(
        cam=((393.0, 338.0), 1.38, (416.0, 306.0), 1.02, 24.0), mundo="dia", luces=(), expo=0.3,
        texto="Interruptor simple del hall (focos del riel) junto a la jamba de la puerta de entrada, del lado de "
              "la manilla, a 1,10 m."),
    "dia_living": dict(
        cam="Depto_Cam_Living", mundo="dia", luces=(), expo=0.0,
        texto="Día normal en el living: sol y cielo de la fase 5, luces apagadas."),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--solo", default="")
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--size", default="1280x800")
    p.add_argument("--sin-gi", action="store_true")
    return p.parse_args(argv)


def a_mundo(p_px, z):
    return Vector((*P.a_blender(*p_px), z))


def camara(nombre, pos, z, objetivo, z_obj, lente):
    cd = bpy.data.cameras.new(nombre)
    cd.lens = lente
    cd.clip_start = 0.02
    cam = bpy.data.objects.new(nombre, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = a_mundo(pos, z)
    d = (a_mundo(objetivo, z_obj) - cam.location).normalized()
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return cam


CERRADA = {}      # corredera -> posición cerrada (la del maestro menos el recorrido si viene abierta)


def estado_movil(o, abierta):
    if "puerta" in o:
        o.rotation_euler.z = math.radians(o["angulo_abierta_deg"]) if abierta else 0.0
    elif "recorrido_m" in o:
        eje = Vector(o["eje_apertura"]) * o["recorrido_m"]
        if o.name not in CERRADA:
            CERRADA[o.name] = o.location - (eje if o.get("abierta") else Vector())
        o.location = CERRADA[o.name] + (eje if abierta else Vector())


def apagada():
    m = bpy.data.materials.get("_Bombilla_apagada")
    if m is None:
        m = bpy.data.materials["Depto_Mat_Bombilla"].copy()
        m.name = "_Bombilla_apagada"
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Emission Strength"].default_value = 0.0
        b.inputs["Base Color"].default_value = (0.55, 0.45, 0.32, 1.0)
    return m


def fijar_luces(encendidos):
    bomb, off = bpy.data.materials["Depto_Mat_Bombilla"], apagada()
    for o in bpy.data.objects:
        if o.type == "LIGHT" and o.name.startswith("Depto_Luz_") and o.data.type == "POINT":
            o.hide_render = not (encendidos == TODOS or o.get("grupo") in encendidos)
        if o.type == "MESH" and o.get("luz_w"):
            on = encendidos == TODOS or o.get("luz_grupo") in encendidos
            for slot in o.material_slots:          # por objeto: las ampolletas iguales comparten la malla
                if slot.material in (bomb, off):
                    slot.link = "OBJECT"
                    slot.material = bomb if on else off


def mundo_noche(scene):
    w = bpy.data.worlds.get("_Noche") or bpy.data.worlds.new("_Noche")
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI_NOCHE, check_existing=True)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.08                 # cielo nocturno casi apagado
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return w


HORNEADO = {"noche": False}


def gi_noche(scene):
    """Volumen de irradiancia sobre el depto y horneado de Eevee (luz rebotada de las ampolletas encendidas). Se
    hornea una vez para todas las vistas de noche (todas con las mismas luces)."""
    if HORNEADO["noche"]:
        return
    HORNEADO["noche"] = True
    if bpy.data.objects.get("_GI_Depto"):
        bpy.ops.scene.light_cache_bake()
        return
    pd = bpy.data.lightprobes.new("_GI_Depto", "GRID")
    ob = bpy.data.objects.new("_GI_Depto", pd)
    scene.collection.objects.link(ob)
    ob.location = (0.0, 0.0, P.ALTURA_PISO_CIELO / 2)
    ob.scale = (4.6, 3.1, P.ALTURA_PISO_CIELO / 2 - 0.02)
    pd.grid_resolution_x, pd.grid_resolution_y, pd.grid_resolution_z = 18, 12, 4
    scene.eevee.gi_diffuse_bounces = 2
    scene.eevee.gi_cubemap_resolution = "128"
    scene.eevee.gi_visibility_resolution = "16"
    bpy.ops.scene.light_cache_bake()


def led_nevera(on):
    ob = bpy.data.objects.get("_LED_Nevera")
    if on and ob is None:
        ref = bpy.data.objects["Depto_Cocina_NeveraCuerpo"]
        pts = [ref.matrix_world @ v.co for v in ref.data.vertices]
        c = sum(pts, Vector()) / len(pts)
        ld = bpy.data.lights.new("_LED_Nevera", "POINT")
        ld.energy, ld.color, ld.shadow_soft_size = 5.0, (0.92, 0.96, 1.0), 0.05
        ob = bpy.data.objects.new("_LED_Nevera", ld)
        bpy.context.scene.collection.objects.link(ob)
        frente = max(pts, key=lambda p: p.y).y                  # la nevera abre hacia +Y de Blender (oeste)
        ob.location = (c.x, frente - 0.12, 1.66)
    if ob is not None:
        ob.hide_render = not on


def config(scene, a):
    scene.render.engine = "BLENDER_EEVEE"
    ee = scene.eevee
    ee.taa_render_samples = a.samples
    ee.use_gtao = True
    ee.gtao_distance = 0.5
    ee.use_ssr = True
    ee.use_soft_shadows = True
    ee.use_bloom = True
    ee.bloom_intensity = 0.03
    ee.shadow_cube_size = "512"
    ee.shadow_cascade_size = "2048"
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium Contrast"
    w, h = (int(v) for v in a.size.lower().split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"


def main():
    a = parse_args()
    os.makedirs(a.out, exist_ok=True)
    scene = bpy.context.scene
    config(scene, a)
    dia, sol = scene.world, bpy.data.objects.get("Depto_Luz_Sol")
    noche = mundo_noche(scene)
    moviles = {o.name: o for o in bpy.data.objects if "puerta" in o or "recorrido_m" in o}
    inicial = {n: bool(o.get("abierta")) for n, o in moviles.items()}
    solo = [s.strip() for s in a.solo.split(",") if s.strip()]
    hechos = []
    ruta_json = os.path.join(a.out, "renders.json")
    previos = []
    if solo and os.path.exists(ruta_json):
        with open(ruta_json) as fh:
            previos = [r for r in json.load(fh) if r["vista"] not in solo]
    for vista, v in VISTAS.items():
        if solo and vista not in solo:
            continue
        for n, o in moviles.items():
            estado_movil(o, inicial[n])
        for n in v.get("abrir", ()):
            estado_movil(moviles[n], True)
        for n in v.get("cerrar", ()):
            estado_movil(moviles[n], False)
        fijar_luces(v["luces"])
        led_nevera(bool(v.get("led_nevera")))
        if v["mundo"] == "noche":
            scene.world = noche
            if sol:
                sol.hide_render = True
            if not a.sin_gi:
                gi_noche(scene)
        else:
            scene.world = dia
            if sol:
                sol.hide_render = False
            if HORNEADO["noche"]:
                bpy.ops.scene.light_cache_free()           # el horneado de noche no sirve de día
                HORNEADO["noche"] = False
        scene.view_settings.exposure = v.get("expo", 0.0)
        bpy.context.view_layer.update()
        cam = bpy.data.objects[v["cam"]] if isinstance(v["cam"], str) else camara(f"_cam_{vista}", *v["cam"])
        ocultar = [bpy.data.objects[n] for n in cam.get("ocultar", "").split(",") if n in bpy.data.objects]
        for n in v.get("ocultar", ()):
            ocultar += [bpy.data.objects[n], *bpy.data.objects[n].children]     # la hoja y su tirador
        for o in ocultar:
            o.hide_render = True
        scene.camera = cam
        ruta = os.path.join(a.out, f"{vista}.png")
        scene.render.filepath = ruta
        bpy.ops.render.render(write_still=True)
        for o in ocultar:
            o.hide_render = False
        hechos.append({"vista": vista, "archivo": os.path.basename(ruta), "que_muestra": v["texto"],
                       "mundo": v["mundo"], "luces": "todas" if v["luces"] == TODOS else list(v["luces"]),
                       "abiertos": list(v.get("abrir", ())), "camara": cam.name,
                       "lente_mm": round(cam.data.lens, 1), "motor": "EEVEE", "muestras": a.samples,
                       "resolucion": [scene.render.resolution_x, scene.render.resolution_y]})
        print("RENDER", ruta)
    orden = list(VISTAS)
    todos = sorted(previos + hechos, key=lambda r: orden.index(r["vista"]))
    with open(ruta_json, "w") as fh:
        json.dump(todos, fh, ensure_ascii=False, indent=2)
    print("RENDERS_07B_DONE", len(hechos))


if __name__ == "__main__":
    main()
