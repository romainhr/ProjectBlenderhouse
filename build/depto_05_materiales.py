"""Fase 5 (materiales y luz) del activo Depto, versión 2 (decoración industrial, docs/deco-industrial.md).

Uso (o todo el pipeline con build/depto_run.sh 05):
    blender -b build/depto.blend --python-exit-code 1 --python build/depto_05_materiales.py

Idempotente: exige el maestro con el sello vigente de la fase 4 (cadena de build/depto_sellos.py). Mejora en su
mismo datablock cada material Depto_Mat_* que usan las mallas visibles, con la textura que le asigna
build/deco_paleta.py (texturas propias generadas por build/deco_texturas.py y CC0 de Poly Haven); no reasigna
materiales ni toca mallas. Reconstruye su colección Depto_Luces: una luz puntual en cada ampolleta que la fase 4
marcó con ["luz_w"] (potencia en W), más el sol entrando por la fachada, y el mundo Depto_Mundo (cielo Nishita con
suelo neutro bajo el horizonte). Ajusta Eevee. Sella scene["depto_fase05"].

Compatibilidad con el tour (compuerta 4: luz en tiempo real en el visor): los materiales usan sólo nodos que el
exportador glTF de Blender 3.6 traduce; la escala real va en el nodo Mapping (KHR_texture_transform). Las luces y
el cielo son para la revisión en Blender; el visor recibe la posición y potencia de las luces por
exports/depto_colisiones.json. Las pruebas lo verifican antes de guardar.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import deco_paleta as PAL  # noqa: E402
import depto_color as DC  # noqa: E402
import depto_geom as G  # noqa: E402
# Los módulos de piezas registran sus materiales propios (MATERIALES.setdefault) al importarse.
import deco_cocina_bano, deco_comedor, deco_dormitorio, deco_hall, deco_living, deco_objetos  # noqa: E402,F401
import depto_sellos as SE  # noqa: E402

COLS = ("Depto_Luces",)
LUZ_COLOR = DC.kelvin_a_lineal(2700)   # 2700 K lineal (contrato v2, sección 2): respaldo si el grupo no trae color
LUZ_RADIO = 0.03                   # radio de la fuente (sombras suaves)
AMPOLLETA_SIN_SOMBRA = ("Depto_Mat_Bombilla", "Depto_Mat_VidrioBombilla")
LUZ_CLIP_SOMBRA = 0.005            # m: inicio del mapa de sombras de cada luz (Eevee usa 0,05 por defecto: dentro de
                                   # las pantallas cerradas, el tapón a ~5 cm de la ampolleta no hacía sombra)
FOCO_BORDE = 0.5                   # spot_blend de los focos de Blender: la penumbra del SpotLight del visor
                                   # (PENUMBRA_CONO de web/src/tour/js/luces.js)
SOL = dict(elevacion=35.0, azimut=-25.0, energia=3.0)   # supuesto: sol desde el lado del balcón (+Y), 25° al -X
CIELO_FUERZA = 0.25
TOPE_TRIANGULOS = G.TOPE_TRIANGULOS
SUELO_COLOR = (0.34, 0.34, 0.32)   # bajo el horizonte el cielo Nishita es negro: vidrios y espejos lo reflejaban


def direccion_luz(o):
    """Eje de la luz que deja salir una pantalla (Blender, mundo): hacia abajo en los domos (ampolleta de revolución,
    sus normales se anulan); en un foco, la normal de su disco emisivo más grande, orientada hacia abajo."""
    mw = o.matrix_world.to_3x3()
    suma = sum((f.normal * f.area for f in o.data.polygons), Vector())
    total = sum(f.area for f in o.data.polygons)
    if total <= 0 or suma.length < 0.5 * total:          # superficie de revolución (ampolleta): sin eje propio
        return Vector((0.0, 0.0, -1.0))
    n = (mw @ suma).normalized()                          # disco plano (foco): su normal
    if abs(n.z) < 0.2:
        return Vector((0.0, 0.0, -1.0))
    return n if n.z < 0 else -n


def luces(col, root, grupos):
    """Una luz puntual por ampolleta marcada en la fase 4, con el color de su grupo (2700 K o 3000 K) y las
    propiedades `ampolleta` y `grupo` que exporta la fase 6."""
    n = 0
    for o in list(root.all_objects):     # copia: se agregan luces a una colección hija mientras se recorre
        w = o.get("luz_w")
        if o.type != "MESH" or not w:
            continue
        pts = [o.matrix_world @ v.co for v in o.data.vertices]
        centro = sum(pts, Vector()) / len(pts)
        # corrección 07c (ronda 2): la ampolleta con ["luz_foco"] (la luz lineal bajo los altos) es un foco hacia abajo
        # de 2 × cono_deg, como el SpotLight del visor; las demás siguen puntuales (su pantalla hace la sombra)
        foco = bool(o.get("luz_foco")) and bool(o.get("luz_cono_deg"))
        ld = bpy.data.lights.new(f"Depto_Luz_{o.name}", "SPOT" if foco else "POINT")
        ld.energy = float(w)
        if foco:
            ld.spot_size = math.radians(min(180.0, 2.0 * float(o["luz_cono_deg"])))
            ld.spot_blend = FOCO_BORDE
            ld.show_cone = False
        g = grupos.get(o.get("luz_grupo"), {})
        ld.color = tuple(g.get("color", LUZ_COLOR))
        ld.shadow_soft_size = float(o.get("luz_radio", LUZ_RADIO))   # la fase 4 lo achica dentro de los focos
        ld.shadow_buffer_clip_start = LUZ_CLIP_SOMBRA
        ob = bpy.data.objects.new(f"Depto_Luz_{o.name}", ld)
        ob.location = centro
        ob["ampolleta"] = o.name
        ob["grupo"] = o.get("luz_grupo", "")
        if o.get("luz_cono_deg"):
            ob["cono_deg"] = float(o["luz_cono_deg"])
            ob["direccion"] = list(direccion_luz(o))
            if foco:
                ob.rotation_euler = Vector(ob["direccion"]).to_track_quat("-Z", "Y").to_euler()   # el foco apunta por -Z
        if o.get("luz_alcance_m"):
            ob["alcance_m"] = float(o["luz_alcance_m"])        # contrato 2.2: distancia de corte en el visor
        col.objects.link(ob)
        n += 1
    el, az = math.radians(SOL["elevacion"]), math.radians(SOL["azimut"])
    hacia_sol = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))   # +Y = balcón
    sd = bpy.data.lights.new("Depto_Luz_Sol", "SUN")
    sd.energy = SOL["energia"]
    sd.angle = math.radians(1.5)
    sol = bpy.data.objects.new("Depto_Luz_Sol", sd)
    sol.rotation_euler = (-hacia_sol).to_track_quat("-Z", "Y").to_euler()   # la luz apunta por su -Z
    col.objects.link(sol)
    return hacia_sol, n


def mundo(scene, hacia_sol):
    w = bpy.data.worlds.get("Depto_Mundo") or bpy.data.worlds.new("Depto_Mundo")
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_disc = False                                   # el sol lo pone la lámpara (no duplicar)
    sky.sun_elevation = math.radians(SOL["elevacion"])
    sky.sun_rotation = math.atan2(hacia_sol.x, hacia_sol.y)
    # suelo neutro bajo el horizonte: mezcla por la componente Z de la dirección de vista (sólo el mundo; no va al GLB)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rango = nt.nodes.new("ShaderNodeMapRange")
    rango.inputs["From Min"].default_value, rango.inputs["From Max"].default_value = -0.02, 0.05
    mezcla = nt.nodes.new("ShaderNodeMixRGB")
    mezcla.inputs["Color1"].default_value = (*SUELO_COLOR, 1.0)
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], rango.inputs["Value"])
    nt.links.new(rango.outputs["Result"], mezcla.inputs["Fac"])
    nt.links.new(sky.outputs["Color"], mezcla.inputs["Color2"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = CIELO_FUERZA
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(mezcla.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    w.color = (0.8, 0.85, 0.9)                             # Workbench y viewport
    scene.world = w


def eevee(scene):
    ee = scene.eevee
    ee.taa_render_samples = 32
    ee.use_gtao = True
    ee.gtao_distance = 0.2               # 0,5 dejaba un halo oscuro alrededor de los florones del cielo
    ee.use_ssr = True
    ee.use_soft_shadows = True
    ee.use_bloom = True                  # halo suave de las ampolletas encendidas
    ee.bloom_intensity = 0.03
    ee.shadow_cube_size = "1024"
    ee.shadow_cascade_size = "2048"
    ee.use_shadow_high_bitdepth = True
    scene.view_settings.view_transform = "Filmic"


def visibles(root):
    return [o for o in root.all_objects if o.type == "MESH" and not o.hide_render and not o.name.startswith("Depto_Ref")]


def pruebas(root):
    fallos = []
    vis = visibles(root)
    usados = set()
    for o in vis:
        if not o.data.uv_layers:
            fallos.append(f"{o.name} sin UV")
        if not o.data.materials or any(m is None for m in o.data.materials):
            fallos.append(f"{o.name} con ranuras de material vacías")
        usados |= {m for m in o.data.materials if m}
    for m in usados:
        otros = {n.type for n in m.node_tree.nodes} - PAL.NODOS_GLTF
        if otros:
            fallos.append(f"{m.name}: nodos que glTF no exporta {sorted(otros)}")
        if m.name in PAL.TEXTURA_MAT:
            imgs = [n for n in m.node_tree.nodes if n.type == "TEX_IMAGE"]
            if not imgs:
                fallos.append(f"{m.name}: debería llevar la textura {PAL.TEXTURA_MAT[m.name][0]} y no la tiene")
            for n in imgs:
                if n.image is None or n.image.size[0] == 0:
                    fallos.append(f"{m.name}: imagen sin cargar {n.image.filepath if n.image else None}")
    total = 0
    for o in vis:
        o.data.calc_loop_triangles()
        total += len(o.data.loop_triangles)
    if total > TOPE_TRIANGULOS:
        fallos.append(f"presupuesto de triángulos excedido: {total}")
    return fallos, usados, total


def main():
    scene = bpy.context.scene
    SE.exigir(scene, "04", bpy.data.filepath)
    root = bpy.data.collections["Depto"]
    cols = G.colecciones_fase(root, COLS)
    bpy.context.view_layer.update()
    usados = sorted({m.name for o in visibles(root) for m in o.data.materials if m})
    con_textura = [n for n in usados if PAL.aplicar(n)]
    # La ampolleta (filamento emisivo y vidrio) no hace sombra a la luz que la representa: con el mapa de sombras
    # desde 5 mm (LUZ_CLIP_SOMBRA), una ampolleta cerrada alrededor de su luz la apagaba (velador de D1).
    for n in AMPOLLETA_SIN_SOMBRA:
        if bpy.data.materials.get(n):
            bpy.data.materials[n].shadow_method = "NONE"
    grupos = {g["id"]: g for g in json.loads(scene.get("depto_grupos_luz", "[]"))}
    hacia_sol, n_luces = luces(cols["Depto_Luces"], root, grupos)
    mundo(scene, hacia_sol)
    eevee(scene)
    fallos, mats, total = pruebas(root)
    sin_grupo = [o.name for o in cols["Depto_Luces"].objects if o.data.type in ("POINT", "SPOT")
                 and o.get("grupo") not in grupos]
    if sin_grupo:
        fallos.append(f"luces sin grupo de luz de la fase 4: {sin_grupo}")
    for f in fallos:
        print("FALLA", f)
    if fallos:
        raise SystemExit(f"ERROR: {len(fallos)} pruebas de la fase 5 fallan; no se guarda el maestro.")
    SE.sellar(scene, "05")
    bpy.ops.wm.save_mainfile(filepath=SE.MAESTRO)
    imgs = {n.image.filepath for m in mats for n in m.node_tree.nodes if n.type == "TEX_IMAGE"}
    print(f"CHECK fase 5: {len(mats)} materiales en uso, {len(con_textura)} con textura, {len(imgs)} imágenes, "
          f"{n_luces} luces de ampolleta + sol; escena visible {total} triángulos; todos los nodos exportables a glTF")
    print(f"FASE_OK Depto_05_materiales {n_luces} {total} sello={scene['depto_fase05']}")


if __name__ == "__main__":
    main()
