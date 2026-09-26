"""Paleta de la decoración industrial (versión 2): qué textura usa cada material Depto_Mat_* y cómo se aplica.

Los colores base de cada material están en depto_geom.MATERIALES. Aquí sólo se dice, por material, qué textura
lleva (de assets/texturas/propias, generadas por build/deco_texturas.py, o de assets/texturas/polyhaven, CC0) y qué
mapas usa. `aplicar(nombre)` arma el árbol de nodos con sólo nodos que el exportador glTF de Blender 3.6 traduce
(Principled BSDF, Image Texture, Normal Map, Mapping, Texture Coordinate); la escala real va en el nodo Mapping
(KHR_texture_transform) porque las UV están en metros de mundo. Si la textura todavía no existe en disco, el
material queda en su color base y `aplicar` devuelve False (sirve para revisar piezas antes de tener texturas).
"""
import json
import os

import bpy

import depto_geom as G

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES = {
    "propias": os.path.join(RAIZ, "assets", "texturas", "propias"),
    "polyhaven": os.path.join(RAIZ, "assets", "texturas", "polyhaven"),
}

# material -> (id de textura, opciones). color: usar el mapa de color (si no, el color base constante);
# rugosidad: usar el mapa de rugosidad; normal: fuerza del mapa normal (None = sin); escala_m: fuerza el tamaño
# real de una repetición; uv01: UV propias 0-1 de la pieza (cuadros), sin repetición.
TEXTURA_MAT = {
    # pisos
    "Depto_Mat_Microcemento": ("microcemento", dict(color=True, rugosidad=True, normal=0.5)),
    "Depto_Mat_PisoMadera": ("piso_roble", dict(color=True, rugosidad=True, normal=0.6)),
    "Depto_Mat_PisoCeramico": ("baldosa_hex", dict(color=True, rugosidad=True, normal=0.8)),
    "Depto_Mat_PisoBalcon": ("losa_hormigon", dict(color=True, rugosidad=True, normal=0.7)),
    "Depto_Mat_PalierPiso": ("losa_hormigon", dict(color=True, rugosidad=True, normal=0.6)),
    # muros y cielo
    "Depto_Mat_MuroPintado": ("white_plaster_02", dict(color=False, rugosidad=True, normal=0.25)),
    "Depto_Mat_MuroExterior": ("white_plaster_02", dict(color=False, rugosidad=True, normal=0.4)),
    "Depto_Mat_Yeso": ("white_plaster_02", dict(color=False, rugosidad=True, normal=0.15)),
    "Depto_Mat_Palier": ("white_plaster_02", dict(color=False, rugosidad=True, normal=0.3)),
    "Depto_Mat_Cielo": ("concreto_encofrado", dict(color=True, rugosidad=True, normal=0.5)),
    "Depto_Mat_Ladrillo": ("ladrillo", dict(color=True, rugosidad=True, normal=1.0)),
    "Depto_Mat_MuroBano": ("azulejo_subway", dict(color=True, rugosidad=True, normal=0.8)),
    # madera
    "Depto_Mat_PuertaMadera": ("oak_veneer_01", dict(color=True, rugosidad=True, normal=0.4)),
    "Depto_Mat_FrenteCloset": ("oak_veneer_01", dict(color=True, rugosidad=True, normal=0.4)),
    "Depto_Mat_MaderaMueble": ("roble_ahumado", dict(color=True, rugosidad=True, normal=0.5)),
    "Depto_Mat_MuebleBano": ("roble_ahumado", dict(color=True, rugosidad=True, normal=0.5)),
    # metal, piedra y concreto
    "Depto_Mat_AceroNegro": ("acero_pavonado", dict(color=True, rugosidad=True, normal=0.3)),
    "Depto_Mat_PuertaEntrada": ("acero_pavonado", dict(color=True, rugosidad=True, normal=0.3)),
    "Depto_Mat_NeveraAcero": ("acero_cepillado", dict(color=True, rugosidad=True, normal=0.25)),
    "Depto_Mat_CubiertaConcreto": ("concreto_oscuro", dict(color=True, rugosidad=True, normal=0.4)),
    "Depto_Mat_CubiertaBano": ("concreto_oscuro", dict(color=True, rugosidad=True, normal=0.4)),
    "Depto_Mat_Concreto": ("microcemento", dict(color=True, rugosidad=True, normal=0.6, escala_m=0.8)),
    # textiles
    "Depto_Mat_Cuero": ("cuero", dict(color=True, rugosidad=True, normal=0.8)),
    "Depto_Mat_Lana": ("lana", dict(color=True, rugosidad=True, normal=1.0)),
    "Depto_Mat_Manta": ("lana", dict(color=False, rugosidad=True, normal=1.0)),
    "Depto_Mat_Toalla": ("lana", dict(color=False, rugosidad=True, normal=0.6)),
    "Depto_Mat_Textil": ("rough_linen", dict(color=False, rugosidad=True, normal=0.6)),
    "Depto_Mat_Cobertor": ("rough_linen", dict(color=False, rugosidad=True, normal=1.0)),
    "Depto_Mat_Alfombra": ("yute", dict(color=True, rugosidad=True, normal=1.0)),
    # Ropa de los clósets: mismas texturas de tela del depto, sólo el relieve (el tinte lo da el color base).
    "Depto_Mat_RopaCrudo": ("rough_linen", dict(color=False, rugosidad=True, normal=0.5)),
    "Depto_Mat_RopaAzul": ("rough_linen", dict(color=False, rugosidad=True, normal=0.5)),
    "Depto_Mat_RopaGris": ("lana", dict(color=False, rugosidad=True, normal=0.8)),
    "Depto_Mat_RopaVino": ("lana", dict(color=False, rugosidad=True, normal=0.8)),
    "Depto_Mat_RopaVerde": ("poly_wool_herringbone", dict(color=False, rugosidad=True, normal=0.6)),
    "Depto_Mat_RopaCarbon": ("poly_wool_herringbone", dict(color=False, rugosidad=True, normal=0.6)),
    "Depto_Mat_RopaDoblada1": ("lana", dict(color=False, rugosidad=True, normal=0.5)),
    "Depto_Mat_RopaDoblada2": ("rough_linen", dict(color=False, rugosidad=True, normal=0.5)),
    # cuadros: lámina con UV 0-1 propia
    "Depto_Mat_Arte1": ("arte_1", dict(color=True, rugosidad=False, normal=None, uv01=True)),
    "Depto_Mat_Arte2": ("arte_2", dict(color=True, rugosidad=False, normal=None, uv01=True)),
    "Depto_Mat_Arte3": ("arte_3", dict(color=True, rugosidad=False, normal=None, uv01=True)),
}
NODOS_GLTF = {"OUTPUT_MATERIAL", "BSDF_PRINCIPLED", "TEX_IMAGE", "NORMAL_MAP", "MAPPING", "TEX_COORD"}


def _manifiestos():
    out = {}
    ph = os.path.join(FUENTES["polyhaven"], "manifest.json")
    if os.path.exists(ph):
        with open(ph) as fh:
            for tid, t in json.load(fh)["texturas"].items():
                m = t["mapas"]
                out[tid] = dict(fuente="polyhaven", tam_m=tuple(v / 1000 for v in t["dimensiones_mm"]),
                                color=os.path.join(FUENTES["polyhaven"], m["Diffuse"]["archivo"]),
                                normal=os.path.join(FUENTES["polyhaven"], m["nor_gl"]["archivo"]),
                                rugosidad=os.path.join(FUENTES["polyhaven"], m["Rough"]["archivo"]))
    pr = os.path.join(FUENTES["propias"], "manifest.json")
    if os.path.exists(pr):
        with open(pr) as fh:
            for tid, t in json.load(fh)["texturas"].items():
                d = os.path.join(FUENTES["propias"], tid)
                mapas = t.get("mapas", {})
                out[tid] = dict(fuente="propias", tam_m=tuple(t["dimensiones_m"]),
                                color=os.path.join(d, mapas.get("color", f"{tid}_diff_1k.jpg")),
                                normal=os.path.join(d, mapas["normal"]) if "normal" in mapas else None,
                                rugosidad=os.path.join(d, mapas["rugosidad"]) if "rugosidad" in mapas else None)
    return out


def textura(tid):
    """Rutas y tamaño real de una textura, o None si todavía no existe en disco."""
    t = _manifiestos().get(tid)
    if t is None or not os.path.exists(t["color"]):
        return None
    return t


def _imagen(ruta, no_color):
    im = bpy.data.images.load(ruta, check_existing=True)
    if bpy.data.filepath:
        try:
            im.filepath = bpy.path.relpath(ruta)       # relativa al .blend (//../assets/...)
        except ValueError:
            pass                                       # otra unidad de disco: queda absoluta
    im.colorspace_settings.name = "Non-Color" if no_color else "sRGB"
    return im


def aplicar(nombre):
    """Material en su versión con textura (idempotente). Devuelve True si quedó con textura."""
    mat = G.material(nombre)                          # base: color, rugosidad, metálico, alfa, emisión
    if nombre not in TEXTURA_MAT:
        return False
    tid, op = TEXTURA_MAT[nombre]
    t = textura(tid)
    if t is None:
        return False
    nt = mat.node_tree
    viejo = nt.nodes["Principled BSDF"]
    base = {k: tuple(viejo.inputs[k].default_value) if hasattr(viejo.inputs[k].default_value, "__len__")
            else viejo.inputs[k].default_value
            for k in ("Base Color", "Roughness", "Metallic", "Alpha", "Emission", "Emission Strength")}
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    for k, v in base.items():
        bsdf.inputs[k].default_value = v
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    if op.get("uv01"):
        esc = (1.0, 1.0)
    else:
        e = op.get("escala_m")
        tam = (e, e) if e else t["tam_m"]
        esc = (1 / tam[0], 1 / tam[1])
    mp.inputs["Scale"].default_value = (*esc, 1.0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])

    def nodo(ruta, no_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = _imagen(ruta, no_color)
        if op.get("uv01"):
            n.extension = "EXTEND"
        nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
        return n
    if op.get("color"):
        nt.links.new(nodo(t["color"], False).outputs["Color"], bsdf.inputs["Base Color"])
    if op.get("rugosidad") and t["rugosidad"]:
        nt.links.new(nodo(t["rugosidad"], True).outputs["Color"], bsdf.inputs["Roughness"])
    if op.get("normal") and t["normal"]:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = op["normal"]
        nt.links.new(nodo(t["normal"], True).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    mat["textura"] = tid
    mat["escala_mapping"] = list(esc)
    return True
