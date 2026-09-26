"""Fase 5 (materiales y luz) del activo Depto: PBR con las texturas CC0 de Poly Haven, granito generado,
salpicadero de cocina, luz de día y una luz por recinto para la revisión con Eevee.

Uso (o todo el pipeline con build/depto_run.sh 05):
    blender -b build/depto.blend --python-exit-code 1 --python build/depto_05_materiales.py

Idempotente: exige que se haya abierto el maestro con el sello vigente de la fase 4 (cadena de
build/depto_sellos.py). Mejora en su mismo datablock los materiales Depto_Mat_* que crearon las fases 2 a 4
(no reasigna materiales ni toca mallas de otras fases), reconstruye sus colecciones (Depto_Revestimientos,
Depto_Luces) y el mundo Depto_Mundo, y ajusta Eevee. Sella scene["depto_fase05"].

Compatibilidad con el tour (compuerta 4: luz en tiempo real en el visor): los materiales usan sólo nodos que el
exportador glTF de Blender 3.6 traduce (Principled BSDF, Image Texture, Normal Map, Mapping, Texture
Coordinate); la escala real de cada textura va en el nodo Mapping (KHR_texture_transform). Las luces y el
cielo son para la revisión en Blender; el visor define las suyas. Una prueba lo verifica antes de guardar.

Orígenes: texturas y tamaño real en assets/texturas/polyhaven/manifest.json (dimensiones_mm). Colores base
supuestos (el plano no indica terminaciones; propuesta neutra del brief).
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_03_formas as F3  # noqa: E402  (constantes de la cocina: mesón, altos, anafe, campana, torre)
import depto_geom as G  # noqa: E402
import depto_plano as P  # noqa: E402
import depto_sellos as SE  # noqa: E402
from depto_geom import Pieza, px  # noqa: E402

X, Y = P.X, P.Y
H = P.ALTURA_PISO_CIELO
COLS = ("Depto_Revestimientos", "Depto_Luces")
TEX = os.path.join(RAIZ, "assets", "texturas", "polyhaven")
MANIFIESTO = os.path.join(TEX, "manifest.json")
GRANITO = os.path.join(RAIZ, "assets", "texturas", "procedural", "granito_gris_512.png")
GRANITO_M = 0.60             # supuesto: la imagen de 512 px cubre 0,60 m
SALPICADERO_ESP = 0.005      # supuesto: cerámica sobre el muro, entre mesón y muebles altos

# Material -> textura. color: usar el mapa Diffuse (si no, color base constante de depto_geom.MATERIALES);
# rugosidad: usar el mapa Rough (si no, la constante); normal: fuerza del mapa normal (OpenGL, como glTF).
PBR = {
    "Depto_Mat_PisoLaminado": dict(tex="laminate_floor_02", color=True, rugosidad=True, normal=0.6),
    "Depto_Mat_PisoCeramico": dict(tex="interior_tiles", color=True, rugosidad=True, normal=0.8),
    "Depto_Mat_PisoBalcon": dict(tex="patio_tiles", color=True, rugosidad=True, normal=0.8),
    "Depto_Mat_MuroPintado": dict(tex="white_plaster_02", color=False, rugosidad=True, normal=0.25),
    "Depto_Mat_MuroExterior": dict(tex="white_plaster_02", color=False, rugosidad=True, normal=0.4),
    "Depto_Mat_Cielo": dict(tex="white_plaster_02", color=False, rugosidad=True, normal=0.15),
    "Depto_Mat_Yeso": dict(tex="white_plaster_02", color=False, rugosidad=True, normal=0.15),
    "Depto_Mat_Palier": dict(tex="white_plaster_02", color=False, rugosidad=True, normal=0.3),
    # tiled_floor_001 es cerámica café (brief): de ella sólo el relieve de las juntas, sobre blanco esmaltado
    "Depto_Mat_MuroBano": dict(tex="tiled_floor_001", color=False, rugosidad=False, normal=0.8),
    "Depto_Mat_PalierPiso": dict(tex="tiled_floor_001", color=False, rugosidad=True, normal=0.6),
    "Depto_Mat_PuertaMadera": dict(tex="oak_veneer_01", color=True, rugosidad=True, normal=0.4),
    "Depto_Mat_MaderaMueble": dict(tex="oak_veneer_01", color=True, rugosidad=True, normal=0.4),
    "Depto_Mat_PuertaEntrada": dict(tex="oak_veneer_01", color=False, rugosidad=True, normal=0.4),
    "Depto_Mat_Alfombra": dict(tex="poly_wool_herringbone", color=True, rugosidad=True, normal=1.0),
    "Depto_Mat_Tapiz": dict(tex="poly_wool_herringbone", color=False, rugosidad=True, normal=1.0),
    "Depto_Mat_TapizAcento": dict(tex="rough_linen", color=False, rugosidad=True, normal=1.0),
    "Depto_Mat_Textil": dict(tex="rough_linen", color=False, rugosidad=True, normal=0.6),
    "Depto_Mat_Cobertor": dict(tex="rough_linen", color=False, rugosidad=True, normal=1.0),
    "Depto_Mat_BaseCama": dict(tex="rough_linen", color=False, rugosidad=True, normal=0.8),
    "Depto_Mat_Granito": dict(tex="granito", color=True, rugosidad=False, normal=None),
}
NODOS_GLTF = {"OUTPUT_MATERIAL", "BSDF_PRINCIPLED", "TEX_IMAGE", "NORMAL_MAP", "MAPPING", "TEX_COORD"}

# Luces de revisión (supuesto): una puntual por recinto a altura de lámpara colgante, más el sol por la fachada.
# A 0,15 m del cielo quemaban una mancha en él (primera corrida de la fase 5); a 0,35 m y con la mitad de
# potencia el cielo queda iluminado sin saturar.
LUZ_Z = H - 0.35
LUCES = {  # recinto: (px del plano, potencia W)
    "Living": ((205, 250), 80), "Cocina": ((340, 220), 50), "Hall": ((395, 335), 30),
    "Dorm1": ((205, 95), 50), "Dorm2": ((205, 410), 50), "Paso_D1": ((315, 91), 20),
    "Paso_D2": ((315, 425), 20), "Bano1": ((365, 100), 30), "Bano2": ((365, 430), 30),
}
SOL = dict(elevacion=35.0, azimut=-25.0, energia=3.0)   # supuesto: sol desde el lado del balcón (+Y), 25° al -X
CIELO_FUERZA = 0.25
SUELO_COLOR = (0.34, 0.34, 0.32)   # bajo el horizonte el cielo Nishita es negro: vidrios y espejos lo reflejaban
TOL_PENETRACION = 0.001


def texturas():
    with open(MANIFIESTO) as fh:
        man = json.load(fh)["texturas"]
    out = {}
    for tid, t in man.items():
        m = t["mapas"]
        out[tid] = dict(tam_m=(t["dimensiones_mm"][0] / 1000, t["dimensiones_mm"][1] / 1000),
                        color=os.path.join(TEX, m["Diffuse"]["archivo"]),
                        normal=os.path.join(TEX, m["nor_gl"]["archivo"]),
                        rugosidad=os.path.join(TEX, m["Rough"]["archivo"]))
    out["granito"] = dict(tam_m=(GRANITO_M, GRANITO_M), color=GRANITO, normal=None, rugosidad=None)
    return out


def generar_granito(ruta, n=512, semilla=7):
    """Granito gris moteado, repetible sin costuras (filtros en el dominio de Fourier = convolución circular)."""
    rng = np.random.default_rng(semilla)
    f = np.fft.fftfreq(n)
    r2 = f[:, None] ** 2 + f[None, :] ** 2

    def ruido(sigma_px):
        w = rng.standard_normal((n, n))
        g = np.real(np.fft.ifft2(np.fft.fft2(w) * np.exp(-2 * (math.pi * sigma_px) ** 2 * r2)))
        return (g - g.mean()) / (g.std() + 1e-9)
    img = 0.42 + 0.035 * ruido(40) + 0.02 * ruido(6)
    img = np.where(ruido(1.2) > 1.9, 0.78, img)            # motas claras
    img = np.where(ruido(1.0) < -2.0, 0.10, img)           # motas oscuras
    img = np.where(ruido(0.8) > 2.3, 0.60, img)
    rgb = np.clip(np.stack([img * 1.00, img * 0.99, img * 0.97, np.ones_like(img)], -1), 0, 1)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    im = bpy.data.images.new("_granito", n, n)
    im.pixels.foreach_set(rgb.astype(np.float32).ravel())
    im.filepath_raw = ruta
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def imagen(ruta, no_color):
    im = bpy.data.images.load(ruta, check_existing=True)
    im.filepath = bpy.path.relpath(ruta)            # relativa al maestro: //../assets/...
    im.colorspace_settings.name = "Non-Color" if no_color else "sRGB"
    return im


def pbr(nombre, spec, tex):
    mat = G.material(nombre)                          # valores base (color, rugosidad, metálico, alfa)
    nt = mat.node_tree
    base = {k: nt.nodes["Principled BSDF"].inputs[k].default_value for k in ("Roughness", "Metallic", "Alpha")}
    color = tuple(nt.nodes["Principled BSDF"].inputs["Base Color"].default_value)
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color
    for k, v in base.items():
        bsdf.inputs[k].default_value = v
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    t = tex[spec["tex"]]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / t["tam_m"][0], 1 / t["tam_m"][1], 1.0)   # UV en metros -> repeticiones
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])

    def nodo_img(ruta, no_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = imagen(ruta, no_color)
        nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
        return n
    if spec["color"]:
        nt.links.new(nodo_img(t["color"], False).outputs["Color"], bsdf.inputs["Base Color"])
    if spec["rugosidad"] and t["rugosidad"]:
        nt.links.new(nodo_img(t["rugosidad"], True).outputs["Color"], bsdf.inputs["Roughness"])
    if spec["normal"] and t["normal"]:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = spec["normal"]
        nt.links.new(nodo_img(t["normal"], True).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    mat["textura"] = spec["tex"]
    mat["escala_m"] = list(t["tam_m"])
    return mat


def salpicadero(col):
    """Cerámica entre el mesón y los muebles altos, sobre T5 (tramo norte) y el forro este (tramo este)."""
    e = px(SALPICADERO_ESP)
    z0, z1, zc = F3.MESON_Z, F3.ALTOS_Z[0], F3.CAMPANA_Z[0]
    s = Pieza("Depto_Revestimiento_Cocina_Salpicadero", "Depto_Mat_MuroBano")
    y0 = Y["T5_S"]
    a0, a1 = F3.ANAFE[0], F3.ANAFE[1]
    s.caja(X["T3_E"], a0, y0, y0 + e, z0, z1)
    s.caja(a0, a1, y0, y0 + e, z0, zc)                     # bajo la campana, hasta su cara inferior
    s.caja(a1, X["E_FORRO"], y0, y0 + e, z0, z1)
    s.caja(X["E_FORRO"] - e, X["E_FORRO"], y0 + e, F3.TORRE_Y[0], z0, z1)
    s.crear(col)


def luces(col):
    for rec, ((x, y), w) in LUCES.items():
        ld = bpy.data.lights.new(f"Depto_Luz_{rec}", "POINT")
        ld.energy = w
        ld.shadow_soft_size = 0.10
        ob = bpy.data.objects.new(f"Depto_Luz_{rec}", ld)
        ob.location = (*P.a_blender(x, y), LUZ_Z)
        ob["recinto"] = rec
        col.objects.link(ob)
    el, az = math.radians(SOL["elevacion"]), math.radians(SOL["azimut"])
    hacia_sol = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))   # +Y = balcón
    sd = bpy.data.lights.new("Depto_Luz_Sol", "SUN")
    sd.energy = SOL["energia"]
    sd.angle = math.radians(1.5)
    sol = bpy.data.objects.new("Depto_Luz_Sol", sd)
    sol.rotation_euler = (-hacia_sol).to_track_quat("-Z", "Y").to_euler()   # la luz apunta por su -Z
    col.objects.link(sol)
    return hacia_sol


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
    ee.gtao_distance = 0.5
    ee.use_ssr = True
    ee.use_soft_shadows = True
    ee.shadow_cube_size = "1024"
    ee.shadow_cascade_size = "2048"
    ee.use_shadow_high_bitdepth = True
    scene.view_settings.view_transform = "Filmic"


def pruebas(root, objs_fase, tex):
    fallos = []
    bpy.context.view_layer.update()
    visibles = [o for o in root.all_objects if o.type == "MESH" and not o.hide_render
                and not o.name.startswith("Depto_Ref")]
    # 1) Toda malla visible tiene UV y materiales en todas sus ranuras; todo material usa sólo nodos de glTF.
    usados = set()
    for o in visibles:
        if not o.data.uv_layers:
            fallos.append(f"{o.name} sin UV")
        if not o.data.materials or any(m is None for m in o.data.materials):
            fallos.append(f"{o.name} con ranuras de material vacías")
        usados |= {m for m in o.data.materials if m}
    for m in usados:
        otros = {n.type for n in m.node_tree.nodes} - NODOS_GLTF
        if otros:
            fallos.append(f"{m.name}: nodos que glTF no exporta {sorted(otros)}")
    # 2) Cada material con textura: imágenes cargadas y escala = tamaño real del manifiesto.
    for nombre, spec in PBR.items():
        m = bpy.data.materials.get(nombre)
        if m is None:
            fallos.append(f"falta el material {nombre}")
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and (n.image is None or n.image.size[0] == 0):
                fallos.append(f"{nombre}: imagen sin cargar {n.image.filepath if n.image else None}")
            if n.type == "MAPPING":
                esc = tuple(n.inputs["Scale"].default_value)[:2]
                esp = tuple(1 / v for v in tex[spec["tex"]]["tam_m"])
                if any(abs(a - b) > 1e-6 for a, b in zip(esc, esp)):
                    fallos.append(f"{nombre}: escala {esc} distinta de {esp}")
    # 3) Revestimientos sin interferencias con el resto.
    propios = G.solidos(objs_fase)
    ajenos = G.solidos([o for o in visibles if o not in objs_fase])
    fallos += G.interferencias(propios, ajenos, TOL_PENETRACION)
    total = 0
    for o in visibles:
        o.data.calc_loop_triangles()
        total += len(o.data.loop_triangles)
    if total > 150_000:
        fallos.append(f"presupuesto de triángulos excedido: {total}")
    imgs = sorted({n.image.filepath for m in usados for n in m.node_tree.nodes if n.type == "TEX_IMAGE"})
    return fallos, len(usados), imgs, total


def main():
    scene = bpy.context.scene
    SE.exigir(scene, "04", bpy.data.filepath)
    root = bpy.data.collections["Depto"]
    cols = G.colecciones_fase(root, COLS)
    generar_granito(GRANITO)
    tex = texturas()
    for nombre, spec in PBR.items():
        pbr(nombre, spec, tex)
    salpicadero(cols["Depto_Revestimientos"])
    hacia_sol = luces(cols["Depto_Luces"])
    mundo(scene, hacia_sol)
    eevee(scene)

    objs = [o for o in cols["Depto_Revestimientos"].all_objects]
    fallos, n_mats, imgs, total = pruebas(root, objs, tex)
    for f in fallos:
        print("FALLA", f)
    if fallos:
        raise SystemExit(f"ERROR: {len(fallos)} pruebas de la fase 5 fallan; no se guarda el maestro.")
    SE.sellar(scene, "05")
    bpy.ops.wm.save_mainfile(filepath=SE.MAESTRO)
    print(f"CHECK fase 5: {n_mats} materiales en uso, {len(PBR)} con textura, {len(imgs)} imágenes, "
          f"{len(LUCES) + 1} luces; escena visible {total} triángulos; todos los nodos exportables a glTF")
    print(f"FASE_OK Depto_05_materiales {len(objs)} {total} sello={scene['depto_fase05']}")


if __name__ == "__main__":
    main()
