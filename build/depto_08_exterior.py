"""Fase 08 (exterior y paisaje) del activo Depto: cielo, fachada del edificio propio, calle con cruce, edificios vecinos,
árboles de calle y siluetas lejanas, vistos desde un 5.º piso.

Uso (o todo el pipeline con build/depto_run.sh; corre entre la fase 5 y la exportación):
    blender -b build/depto.blend --python-exit-code 1 --python build/depto_08_exterior.py

Idempotente: exige el maestro con el sello vigente de la fase 5, borra la colección Depto_Exterior (con sus materiales
Depto_Ext_Mat_*) y la rebuilda desde las constantes de este archivo. No toca objetos de otras fases. Sella
scene["depto_fase08"]; la fase 6 exige ese sello (cadena de build/depto_sellos.py: 05 -> 08 -> 06).

Nada del exterior sale del plano, que es una planta del departamento: todo es diseño o inferido, salvo la posición de
la fachada, del balcón y de las ventanas propias, que son las medidas de build/depto_plano.py. El supuesto base es el
de ADR 0004 (decisión 5): el piso del depto queda a ≈ 12,5 m sobre la calzada (5.º piso de 8).

Para el visor (docs/contrato-interaccion.md, sección 4, versión 2.5):
- cada objeto lleva colision = False y exterior = True, y cada material Depto_Ext_Mat_* trae en sus extras
  exterior = true y exterior_capa ("cerca" o "lejos"): el visor lo dibuja con un material sin luces
  (MeshBasicMaterial), sin las luces puntuales, con el sombreado del sol calculado por vértice al cargar;
- la emisión (ventanas encendidas, luminarias) queda con fuerza 0 en el maestro (renders de día) y con
  emision_noche = 1 en el material: la fase 6 la sube a 1 sólo para exportar, y el visor la escala por momento
  (scene["depto_exterior"]["emision"]);
- scene["depto_exterior"] guarda los cielos (HDR y JPG de Poly Haven, assets/hdri/manifest.json), el sol medido en
  cada HDR, la rotación que lleva el sol del HDR de día al sol de la escena, la altura del suelo y el conteo.
- los materiales de vidrio (muro cortina y ventanas propias) traen exterior_vidrio (el visor refleja el panorama donde
  su mapa de rugosidad dice vidrio; desde la ronda 2, el de las barandas con uniforme = true, sin mapa) y la mancha de
  luz de las luminarias, exterior_aditivo (el visor la suma de tarde y de noche; en Blender es invisible y alumbran
  focos, tools/render_08.py).
- corrección 08, ronda 2: la franja del depto en la fachada lleva la misma piel exterior que el resto del edificio
  (piel_depto, a 1 cm de los muros propios) y la línea central de las calles es geometría que salta el cruce.
Pruebas antes de guardar: presupuesto de triángulos (exterior ≤ 15 000 y escena ≤ 200 000), materiales y objetos
marcados, UV en todo, nada del exterior dentro del volumen del depto, del balcón o del palier, las ventanas propias
con la vista libre (ningún rayo hacia afuera choca con el exterior antes de 3 m), y desde la corrección 08 (ronda 1)
los choques entre piezas: cada poste de luminaria a 1,1·R_max + 0,3 m o más del eje de cada árbol y su brazo, carcasa
y refractor fuera de las copas; y los balcones corridos de los B, uno por piso tipo y ninguno en el techo; desde la
ronda 2, ningún segmento de la línea central dentro del cruce ni de un paso de cebra.
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_02_blockout as B2  # noqa: E402  (vanos medidos de la fachada y del muro norte)
import depto_geom as G  # noqa: E402
import depto_plano as P  # noqa: E402
import depto_sellos as SE  # noqa: E402
import ext_texturas as T  # noqa: E402

X, Y, S = P.X, P.Y, P.M_POR_PX
COL = "Depto_Exterior"
TOPE_EXTERIOR = 15_000                  # encargo del bloque 08
SEMILLA = 2026

# ---------------------------------------------------------------------------------------------- cielo
HDRI = os.path.join(RAIZ, "assets", "hdri")
with open(os.path.join(HDRI, "manifest.json")) as _fh:
    CIELOS = json.load(_fh)["cielos"]    # {dia, tarde, noche}: ids de Poly Haven (CC0)
PANORAMA = "tex/cielo_{}.jpg"            # ruta en la carpeta modelo/ del visor (la fase 6 copia los JPG)
EMISION_MOMENTO = {"dia": 0.0, "tarde": 0.35, "noche": 1.0}   # diseño: ventanas y luminarias; de tarde, a un tercio
# Fuerza del cielo que ve la cámara en los renders de revisión (tools/render_08.py, MOMENTOS: fuerza × camara, que
# render_08 verifica contra este valor): la fase 6 hornea con ella los cielos del visor en pantalla (corrección 08,
# ronda 2; contrato 2.5)
CIELO_CAMARA = {"dia": 1.6, "tarde": 0.32, "noche": 0.044}

# ---------------------------------------------------------------------------------------------- alturas (inferidas)
Z_CALLE = -12.5                          # supuesto (ADR 0004, decisión 5; encargo del bloque 08): piso del depto a
                                         # ≈ 12,5 m sobre la calzada, 5.º piso
SOLERA = 0.15                            # supuesto: alto de solera usual (0,12-0,18 m)
Z_VEREDA = Z_CALLE + SOLERA              # vereda, antejardín y lotes
LOSA = P.ESPESOR_LOSA                    # 0,15, supuesto del brief
ENTREPISO = P.ALTURA_PISO_CIELO + LOSA   # 2,55: derivado de dos supuestos del brief (2,40 + 0,15)
PISO_DEPTO = 5                           # supuesto (ADR 0004)
PISOS = 8                                # supuesto: tres pisos sobre el depto
PARAPETO = 1.0                           # diseño
Z_BALCON = -P.DESNIVEL_BALCON            # piso de los balcones: 3 cm bajo el interior, como el del depto (supuesto)


def z_piso(n):
    """Nivel de piso terminado del piso n (2 en adelante; el 1 es la planta baja sobre la vereda)."""
    return (n - PISO_DEPTO) * ENTREPISO


Z_TECHO = z_piso(PISOS + 1)              # losa del techo: 10,20

# ---------------------------------------------------------------------------------------------- planta propia (medida)
YF = P.a_blender(X["W_O"], 0)[1]          # fachada del balcón (cara exterior del muro oeste): 3,005 m
YE = P.a_blender(X["E_O"], 0)[1]          # cara exterior del muro de la entrada: −3,005 m
XN = P.a_blender(0, Y["N_O"])[0]          # cara exterior del muro norte: 4,491 m
XS = P.a_blender(0, Y["S_O"])[0]          # cara exterior del muro sur: −4,491 m
ANCHO = XN - XS                          # 8,98 m
XB0, XB1 = sorted((P.a_blender(0, Y["BAL_S"])[0], P.a_blender(0, Y["BAL_N"])[0]))   # losa del balcón: −1,68 a 1,65
YB = P.a_blender(X["BAL_O"], 0)[1]        # borde exterior del balcón: 4,186 m
XR0, XR1 = sorted((P.a_blender(0, Y["BARANDA_S"])[0], P.a_blender(0, Y["BARANDA_N"])[0]))  # ejes de la baranda
YR = P.a_blender(X["BARANDA_O"], 0)[1]    # eje de la baranda del frente: 4,112 m
BARANDA_ALTO = P.ALTURA_BARANDA_BALCON   # 1,00 (supuesto del brief)
Y_ATRAS = YE - 1.55 - 6.0                # inferido: palier de 1,40 + muro de 0,15 y otra crujía de 6 m detrás
# El depto es el del extremo norte (tiene ventana en el muro norte, V_B1, medido) y hacia el sur siguen dos deptos
# (supuesto): el primero en espejo y el segundo igual al nuestro. (desplazamiento, signo) de x' = d + s·x.
COLUMNAS = ((0.0, 1.0), (2.0 * XS, -1.0), (-2.0 * ANCHO, 1.0))
X_SUR = XS - 2.0 * ANCHO                 # extremo sur del edificio: −22,45 m
PROF_VANO = 0.12                         # diseño: retranqueo del vidrio en los vanos de los otros pisos


def _vanos_fachada():
    """Vanos del muro de la fachada (fase 2, medidos): [(x0, x1, antepecho, dintel, id)] en X de Blender."""
    muro = next(m for m in B2.MUROS if m[0] == "Depto_Muro_Fachada")
    out = []
    for a, b, ante, dintel, vid in muro[5]:
        xa, xb = P.a_blender(0, a)[0], P.a_blender(0, b)[0]
        out.append((min(xa, xb), max(xa, xb), ante, dintel, vid))
    return out


def _vanos_norte():
    muro = next(m for m in B2.MUROS if m[0] == "Depto_Muro_Norte")
    out = []
    for a, b, ante, dintel, vid in muro[5]:
        ya, yb = P.a_blender(a, 0)[1], P.a_blender(b, 0)[1]
        out.append((min(ya, yb), max(ya, yb), ante, dintel, vid))
    return out


VANOS = _vanos_fachada()                 # V_D1, VEN_LIV y V_D2
VANOS_NORTE = _vanos_norte()             # V_B1

# ---------------------------------------------------------------------------------------------- calles (diseño)
# Calle principal paralela a la fachada (a lo largo de X) y transversal a lo largo de Y, al norte del edificio. Anchos
# usuales de una calle local: vereda de 3 m y calzada de 8 m (dos pistas); antejardín de 3 m (diseño).
Y_VEREDA_A, Y_CALZ_0, Y_CALZ_1, Y_VEREDA_B = 6.0, 9.0, 17.0, 20.0
X_VEREDA_A, X_CALZ_0, X_CALZ_1, X_VEREDA_B = 16.0, 19.0, 27.0, 30.0
LARGO = 400.0                            # m hasta donde llegan las calles (el visor corta a 2 000 m)
LEJOS = 900.0                            # suelo lejano, bajo todo, hasta aquí
CERCA = (-70.0, 70.0, -40.0, 80.0)       # lotes con pasto (xmin, xmax, ymin, ymax); afuera, suelo lejano liso
FASE_CALLE = X_CALZ_0 - 3.5              # desfase de la textura de calle a lo largo de X: v = (x − fase) / 12
# Línea central segmentada (corrección 08, ronda 2): geometría, no textura. Con la raya en la textura (3 m de cada 12,
# v = (x − 15,5) / 12) caía en x 15,5-18,5 y 27,5-30,5, dentro de los dos pasos de cebra que cruzan la principal
# (x 16,3-18,7 y 27,3-29,7), y ninguna fase de un período de 12 m libraba a la vez el cruce (19-27) y las dos cebras.
# Segmentos de ext_texturas.LINEA_CENTRAL en el eje de las pistas, 2 cm sobre el asfalto, desde LINEA_FASE + 12·k y
# saltando LINEA_LIBRE (el cruce, sus cebras y 1 m de margen). Diseño: un segmento termina a 3,3 m de la primera cebra
# en cada calle; hasta LINEA_ALCANCE m del origen (más lejos, desde el 5.º piso, la raya de 12 cm no alcanza un píxel).
LINEA_ALCANCE = 150.0
LINEA_FASE = {"x": 10.0, "y": 0.0}
LINEA_LIBRE = {"x": (X_VEREDA_A - 1.0, X_VEREDA_B + 1.0), "y": (Y_VEREDA_A - 1.0, Y_VEREDA_B + 1.0)}
CEBRAS, LINEAS = [], []                   # rectángulos (x0, x1, y0, y1) de los pasos de cebra y de la línea (pruebas)

# ---------------------------------------------------------------------------------------------- vecinos (diseño)
# (nombre, variante de ext_texturas.VARIANTES, x0, x1, y0, y1, pisos, frente): anchos y fondos en bahías enteras de la
# variante, para que ninguna ventana quede cortada en una esquina. A 15-40 m del depto. El E2, de 4 pisos, queda bajo
# la vista (≈ 13 m sobre la vereda contra 14,1 del ojo): por encima se ve el horizonte hacia donde está el sol.
EDIFICIOS = (
    ("E1", "D", -28.0, -10.5, 23.0, 37.0, 3, -1),
    ("E2", "A", -9.6, 3.2, 22.5, 35.3, 4, -1),
    ("E3", "B", 3.8, 15.8, 22.0, 34.0, 11, -1),
    ("E4", "C", 31.0, 46.0, 22.0, 37.0, 8, -1),
    ("E5", "B", 30.0, 42.0, -9.0, 3.0, 6, 1),
    ("E6", "D", 7.0, 14.0, -7.5, 3.0, 1, 1),
    ("E7", "A", -40.3, -24.3, -9.8, 3.0, 7, 1),
)
REMATE = {"A": "remate_A", "B": "remate_B", "C": "remate_C", "D": "remate_D"}
PARAPETO_VECINO = 0.9                    # diseño
BALCON_VECINO = 1.1                      # diseño: vuelo de los balcones corridos de la variante B
BARANDA_VECINO = 1.0                     # diseño: vidrio de 1,0 m con pasamanos, como el del depto (brief)
VARIANTE_BALCON = {"B": "B_balcon"}      # la cara de la calle de los B lleva el atlas con puertas-ventana hasta el piso;
                                         # las otras caras y el barrio, el atlas B sin balcón
BALCONES_VECINOS = {}                    # nombre -> losas de balcón construidas (para pruebas())

# ---------------------------------------------------------------------------------------------- árboles y mobiliario
ARBOLES = ([(x, 8.3) for x in (-38.0, -30.0, -22.0, -14.0, -5.5, 5.5, 13.5)]
           + [(x, 17.7) for x in (-35.0, -26.0, -17.0, -8.0, 1.0, 10.0)]
           + [(18.3, y) for y in (-14.0, -5.0, 26.0, 34.0)] + [(27.7, y) for y in (-10.0, -1.0, 26.0, 34.0)])
# Luminarias (x, y del poste, lado hacia donde sale el brazo): entre dos árboles de su vereda, a 4-4,5 m de cada uno
# (corrección 08, ronda 1: la de −18,0 atravesaba la copa del árbol de −17,0; pruebas() exige ahora poste–eje de árbol
# ≥ 1,1·R_max + 0,3 en planta y el cabezal fuera de las copas).
LUMINARIAS = ([(x, 8.65, 1) for x in (-26.0, -10.0, 9.5)] + [(x, 17.35, -1) for x in (-21.5, -3.5, 14.5)])
POSTE_ALTO, BRAZO, CABEZAL = 7.0, 1.3, (0.36, 0.55)      # diseño: poste de 7 m, brazo de 1,3 m y cabezal de 36 × 55 cm
# Autos estacionados en la faja de 2 m junto a la solera de la vereda A (y 9,0-11,0; ext_texturas.ESTACIONAMIENTO) y en
# la de la transversal (x 19,0-21,0): la calzada de 8 m queda con dos pistas de 3 m (diseño; antes había autos a los
# dos lados y quedaban pistas de 2,05 m). Lejos del cruce y sin tapar el sendero de la entrada (x −10,2..−7,8).
Y_AUTOS = Y_CALZ_0 + 1.05
AUTOS = ((-33.0, Y_AUTOS, 0.0, "auto_blanco"), (-27.5, Y_AUTOS, 0.0, "auto_azul"), (-20.5, Y_AUTOS, 0.0, "auto_gris"),
         (-13.2, Y_AUTOS, 0.0, "auto_negro"), (2.5, Y_AUTOS, 0.0, "auto_rojo"), (8.2, Y_AUTOS, 0.0, "auto_plata"),
         (X_CALZ_0 + 1.05, -8.0, 90.0, "auto_gris"), (X_CALZ_0 + 1.05, -15.0, 90.0, "auto_blanco"))
ARBUSTOS_X = (-20.5, -17.5, -14.5, -12.2, -5.8, -2.5, 0.8, 3.6)   # antejardín propio (el sendero va en −10,2..−7,8)
SENDERO = (-10.2, -7.8)

# ---------------------------------------------------------------------------------------------- siluetas lejanas
# (material, radio mín., radio máx., azimut desde, hasta (grados, 0 = +X, 90 = +Y), tarjetas, alto mín., alto máx.)
# Altos de diseño: la primera capa asoma hasta ≈ 6° sobre el horizonte del ojo (a 14,1 m de la calle) y la segunda hasta
# ≈ 7°, para que el resplandor de la tarde (sol del HDR a 12° de elevación) quede sobre ellas.
CAPAS_LEJANAS = (("Depto_Ext_Mat_Lejanos1", 170.0, 215.0, -15.0, 195.0, 8, 10.0, 32.0),
                 ("Depto_Ext_Mat_Lejanos2", 280.0, 340.0, -20.0, 200.0, 8, 16.0, 52.0))
CENTRO_VISTA = (0.0, 3.5)                 # las tarjetas miran hacia el balcón

# ---------------------------------------------------------------------------------------------- materiales
# tex: id de ext_texturas.generar(); capa: "cerca" o "lejos" (el visor aplica la bruma del momento a las lejanas).
# vidrio (corrección 08, ronda 1): la rugosidad sale del mapa de ext_texturas (vidrio 0,12, marco y muro 0,70) y el
# material lleva en los extras exterior_vidrio = {reflectividad, rugosidad_vidrio, rugosidad_marco}: el visor refleja
# el panorama del momento donde el mapa dice vidrio (MeshBasicMaterial con envMap, sin luces). Reflectividad de diseño.
# aditivo: la mancha de luz de las luminarias; en el maestro es invisible (alfa 0: Blender alumbra con focos en
# tools/render_08.py) y el visor la suma de tarde y de noche (extras exterior_aditivo).
VIDRIO_EXT = dict(reflectividad=0.30, rugosidad_vidrio=T.RUGOSIDAD["vidrio"], rugosidad_marco=T.RUGOSIDAD["marco"])
MATERIALES = {
    "Depto_Ext_Mat_FachadaA": dict(tex="fachada_A", emision=True, rugosidad=0.85),
    "Depto_Ext_Mat_FachadaB": dict(tex="fachada_B", emision=True, rugosidad=0.80),
    "Depto_Ext_Mat_FachadaB_balcon": dict(tex="fachada_B_balcon", emision=True, rugosidad=0.80),
    "Depto_Ext_Mat_FachadaC": dict(tex="fachada_C", emision=True, vidrio=VIDRIO_EXT),
    "Depto_Ext_Mat_FachadaD": dict(tex="fachada_D", emision=True, rugosidad=0.85),
    "Depto_Ext_Mat_FachadaPropia": dict(tex="fachada_propia", rugosidad=0.90),
    "Depto_Ext_Mat_VentanasPropias": dict(tex="ventanas_propias", emision=True, vidrio=VIDRIO_EXT),
    "Depto_Ext_Mat_LuzSuelo": dict(tex="luz_suelo", emision=True, aditivo=True),
    "Depto_Ext_Mat_Calle": dict(tex="calle", rugosidad=0.90),
    "Depto_Ext_Mat_Terreno": dict(tex="terreno", rugosidad=0.95),
    "Depto_Ext_Mat_Paleta": dict(tex="paleta", emision=True, rugosidad=0.70),
    # bruma: la capa más lejana, más clara y más azul (diseño; Eevee no tiene perspectiva aérea)
    "Depto_Ext_Mat_Lejanos1": dict(tex="lejanos", emision=True, rugosidad=0.90, tinte=(0.86, 0.90, 0.96), capa="lejos"),
    "Depto_Ext_Mat_Lejanos2": dict(tex="lejanos", emision=True, rugosidad=0.90, tinte=(0.97, 1.00, 1.06), capa="lejos"),
    # corrección 08, ronda 2: el vidrio de las barandas refleja el cielo parejo (exterior_vidrio con uniforme = true, sin
    # mapa: todo el paño es vidrio) y no lleva el sombreado por vértice. Antes era un MeshBasic multiplicado por el k de
    # una cara vertical (≈ 0,44) que sólo restaba luz: una lámina ahumada donde Blender aclara lo de atrás con el reflejo
    # (+37 % sobre la ventana del E3 detrás de la baranda, balcon_dia). Reflectividad de diseño, calibrada con
    # tools/medir_08.py (criterio vidrio_baranda)
    "Depto_Ext_Mat_VidrioBaranda": dict(color=(0.70, 0.80, 0.84), alfa=0.28, rugosidad=0.05,
                                        vidrio_uniforme=dict(reflectividad=0.25, uniforme=True)),
}


def _imagen(ruta):
    im = bpy.data.images.load(ruta, check_existing=True)
    im.reload()                          # la textura se regenera en cada corrida
    return im


def material_ext(nombre, spec, tex):
    m = bpy.data.materials.get(nombre) or bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    b.inputs["Roughness"].default_value = spec.get("rugosidad", 0.85)
    b.inputs["Specular"].default_value = 0.5            # otro valor exporta KHR_materials_specular
    b.inputs["Emission Strength"].default_value = 0.0
    if spec.get("aditivo"):
        # sólo emisión, invisible en Blender (alfa 0: el Principled de 3.6 apaga también la emisión): el glTF lleva la
        # textura de emisión y el visor la suma con mezcla aditiva
        t = tex[spec["tex"]]
        b.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        ie = nt.nodes.new("ShaderNodeTexImage")
        ie.image = _imagen(t["emision"])
        ie.name = "Emision"
        nt.links.new(ie.outputs["Color"], b.inputs["Emission"])
        m["emision_noche"] = 1.0
        m["exterior_aditivo"] = True
        b.inputs["Alpha"].default_value = 0.0
        m.blend_method = "BLEND"
        m.shadow_method = "NONE"
        m.use_backface_culling = True
        m.show_transparent_back = False
        m.diffuse_color = (0.0, 0.0, 0.0, 0.0)
        m["exterior"] = True
        m["exterior_capa"] = "cerca"
        return m
    if "tex" in spec:
        t = tex[spec["tex"]]
        im = nt.nodes.new("ShaderNodeTexImage")
        im.image = _imagen(t["color"])
        if spec.get("vidrio"):
            ir = nt.nodes.new("ShaderNodeTexImage")
            ir.image = _imagen(t["rugosidad"])
            ir.image.colorspace_settings.name = "Non-Color"
            ir.name = "Rugosidad"
            nt.links.new(ir.outputs["Color"], b.inputs["Roughness"])
            m["exterior_vidrio"] = dict(spec["vidrio"])
        if "tinte" in spec:                               # factor de color base (baseColorFactor en glTF)
            mix = nt.nodes.new("ShaderNodeMixRGB")
            mix.blend_type = "MULTIPLY"
            mix.inputs["Fac"].default_value = 1.0
            mix.inputs["Color2"].default_value = (*spec["tinte"], 1.0)
            nt.links.new(im.outputs["Color"], mix.inputs["Color1"])
            nt.links.new(mix.outputs["Color"], b.inputs["Base Color"])
        else:
            nt.links.new(im.outputs["Color"], b.inputs["Base Color"])
        if spec.get("emision") and t.get("emision"):
            ie = nt.nodes.new("ShaderNodeTexImage")
            ie.image = _imagen(t["emision"])
            ie.name = "Emision"
            nt.links.new(ie.outputs["Color"], b.inputs["Emission"])
            m["emision_noche"] = 1.0                      # la fase 6 exporta con esta fuerza; el visor la escala
        m.diffuse_color = (0.6, 0.6, 0.6, 1.0)
    else:
        c = spec["color"]
        b.inputs["Base Color"].default_value = (*c, 1.0)
        m.diffuse_color = (*c, spec.get("alfa", 1.0))
        if spec.get("vidrio_uniforme"):                   # extras exterior_vidrio sin mapa (el visor: reflejo parejo)
            m["exterior_vidrio"] = dict(spec["vidrio_uniforme"])
    alfa = spec.get("alfa", 1.0)
    b.inputs["Alpha"].default_value = alfa
    if alfa < 1.0:
        m.blend_method = "BLEND"
        m.shadow_method = "NONE"
        m.use_backface_culling = False                    # glTF doubleSided: las barandas se ven de los dos lados
        m.show_transparent_back = True
    else:
        m.blend_method = "OPAQUE"
        m.use_backface_culling = True                     # caras de un solo lado (el visor no dibuja las de atrás)
    m["exterior"] = True
    m["exterior_capa"] = spec.get("capa", "cerca")
    if "tinte" in spec:
        # el exportador glTF de 3.6 no traduce el MixRGB a baseColorFactor: el visor lo lee de los extras
        m["tinte"] = list(spec["tinte"])
    return m


# ---------------------------------------------------------------------------------------------- mallas
class Malla:
    """Caras sueltas (sombreado plano) con UV y material por cara. `cara` orienta el polígono según la normal pedida."""

    def __init__(self, nombre, materiales):
        self.nombre, self.mats = nombre, list(materiales)
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")

    def cara(self, pts, uvs, mat, normal):
        pts = [Vector(p) for p in pts]
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.dot(Vector(normal)) < 0:
            pts, uvs = pts[::-1], list(uvs)[::-1]
        vs = [self.bm.verts.new(p) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self.mats.index(mat)
        for lp, uv in zip(f.loops, uvs):
            lp[self.uv].uv = uv
        return f

    def plana(self, pts, mat, normal, color):
        """Cara de color plano de la paleta (una sola UV: el centro de la muestra)."""
        uv = T.uv_paleta(color)
        return self.cara(pts, [uv] * len(pts), mat, normal)

    def caja(self, x0, x1, y0, y1, z0, z1, mat, color, caras="xXyYzZ"):
        """Caja de la paleta; caras: x/X = −X/+X, y/Y, z/Z (abajo/arriba)."""
        c = {"x": ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
             "X": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
             "y": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
             "Y": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
             "z": ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
             "Z": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1))}
        for k in caras:
            pts, n = c[k]
            self.plana(pts, mat, n, color)

    def prisma(self, cx, cy, r, z0, z1, lados, mat, color, tapa=False):
        pts = [(cx + r * math.cos(2 * math.pi * i / lados), cy + r * math.sin(2 * math.pi * i / lados))
               for i in range(lados)]
        for i in range(lados):
            (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % lados]
            nm = ((xa + xb) / 2 - cx, (ya + yb) / 2 - cy, 0)
            self.plana([(xa, ya, z0), (xb, yb, z0), (xb, yb, z1), (xa, ya, z1)], mat, nm, color)
        if tapa:
            self.plana([(x, y, z1) for x, y in pts], mat, (0, 0, 1), color)

    def crear(self, col):
        me = bpy.data.meshes.new(self.nombre)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        for n in self.mats:
            me.materials.append(bpy.data.materials[n])
        ob = bpy.data.objects.new(self.nombre, me)
        ob["colision"] = False             # el recorrido y la fase 6 lo ignoran (sin colisión)
        ob["exterior"] = True              # extras del nodo (el material también lo trae)
        ob.color = (1.0, 1.0, 1.0, 1.0)
        col.objects.link(ob)
        return ob


def _icosfera(sub):
    t = (1 + 5 ** 0.5) / 2
    v = [Vector(p).normalized() for p in ((-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
                                          (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1))]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7),
         (9, 8, 1)]
    for _ in range(sub):
        medio, nf = {}, []

        def m(a, b):
            k = (min(a, b), max(a, b))
            if k not in medio:
                v.append(((v[a] + v[b]) / 2).normalized())
                medio[k] = len(v) - 1
            return medio[k]
        for a, b, c in f:
            ab, bc, ca = m(a, b), m(b, c), m(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    return v, f


def esfera(malla, centro, radios, sub, mat, color, rng, jitter=0.1):
    v, f = _icosfera(sub)
    c = Vector(centro)
    pts = [c + Vector((p.x * radios[0], p.y * radios[1], p.z * radios[2])) * (1 + jitter * (2 * rng.random() - 1))
           for p in v]
    for a, b, d in f:
        tri = [pts[a], pts[b], pts[d]]
        nm = sum(tri, Vector()) / 3 - c
        malla.plana(tri, mat, nm, color)


# ---------------------------------------------------------------------------------------------- paredes con vanos
class Plano:
    """Plano vertical de una fachada: punto(s, z, d) con s a lo largo, z la altura y d hacia afuera (normal)."""

    def __init__(self, punto, normal, derecha):
        self.punto, self.normal, self.derecha = punto, Vector(normal), derecha   # derecha: signo de s hacia la
        # derecha de quien mira la fachada desde afuera (para no espejar las baldosas de ventana)

    def t(self):
        return (self.punto(1, 0, 0) - self.punto(0, 0, 0)).normalized()


FACHADA = Plano(lambda s, z, d: Vector((s, YF + d, z)), (0, 1, 0), -1)
LATERAL = Plano(lambda s, z, d: Vector((XN + d, s, z)), (1, 0, 0), 1)
# Piel de la franja del depto (corrección 08, ronda 2). Entre z = −0,15 y 2,55 la fachada y el lateral norte del 5.º
# piso de la columna 0 eran los muros propios (fase 2, Depto_Mat_MuroExterior): en Blender la luz rebotada del interior
# (el volumen de irradiancia de los renders de revisión) los dejaba ≈ 40 % más oscuros que la fachada de arriba y de
# abajo, y en el visor quedaban ≈ 20 % más claros (PBR con las luces del depto contra el MeshBasic de la fachada). Una
# piel con la misma pintura, UV y sombreado que el resto de la fachada, a PIEL de los muros y con los vanos medidos
# recortados, cubre la franja con la misma piel exterior en los dos motores. Diseño: 1 cm (a 30 m de distancia la
# profundidad del visor resuelve ≈ 1 mm).
PIEL = 0.01
FACHADA_PIEL = Plano(lambda s, z, d: Vector((s, YF + PIEL + d, z)), (0, 1, 0), -1)
LATERAL_PIEL = Plano(lambda s, z, d: Vector((XN + PIEL + d, s, z)), (1, 0, 0), 1)


def _uv_pintura(p):
    return p / T.PINTURA_M


def pared(malla, plano, s0, s1, z0, z1, vanos, mat):
    """Paño de [s0, s1] × [z0, z1] sin los vanos [(sa, sb, za, zb)] (rectángulos por franjas, sin booleanos)."""
    cortes = sorted({z0, z1, *[min(max(v[2], z0), z1) for v in vanos], *[min(max(v[3], z0), z1) for v in vanos]})
    for za, zb in zip(cortes, cortes[1:]):
        if zb - za < 1e-6:
            continue
        huecos = sorted((v[0], v[1]) for v in vanos if v[2] <= za + 1e-6 and v[3] >= zb - 1e-6)
        s = s0
        for ha, hb in huecos + [(s1, s1)]:
            if ha - s > 1e-6:
                pts = [plano.punto(s, za, 0), plano.punto(ha, za, 0), plano.punto(ha, zb, 0), plano.punto(s, zb, 0)]
                uvs = [(_uv_pintura(a), _uv_pintura(b)) for a, b in ((s, za), (ha, za), (ha, zb), (s, zb))]
                malla.cara(pts, uvs, mat, plano.normal)
            s = max(s, hb)


def vano(malla, plano, sa, sb, za, zb, baldosa, mat_pared, mat_vidrio, prof=PROF_VANO, alfeizar=True):
    """Vidrio retranqueado `prof` con sus cuatro caras de vano (jambas, dintel y alféizar)."""
    u0, v0, u1, v1 = baldosa
    izq_a_der = [(sa, u1), (sb, u0)] if plano.derecha < 0 else [(sa, u0), (sb, u1)]
    (s_a, ua), (s_b, ub) = izq_a_der
    pts = [plano.punto(sa, za, -prof), plano.punto(sb, za, -prof), plano.punto(sb, zb, -prof),
           plano.punto(sa, zb, -prof)]
    malla.cara(pts, [(ua, v0), (ub, v0), (ub, v1), (ua, v1)], mat_vidrio, plano.normal)
    t = plano.t()
    for s, n in ((sa, t), (sb, -t)):                                     # jambas
        pts = [plano.punto(s, za, -prof), plano.punto(s, za, 0), plano.punto(s, zb, 0), plano.punto(s, zb, -prof)]
        malla.cara(pts, [(0, _uv_pintura(za)), (prof / T.PINTURA_M, _uv_pintura(za)),
                         (prof / T.PINTURA_M, _uv_pintura(zb)), (0, _uv_pintura(zb))], mat_pared, n)
    for z, n, hay in ((zb, (0, 0, -1), True), (za, (0, 0, 1), alfeizar)):
        if not hay:
            continue
        pts = [plano.punto(sa, z, -prof), plano.punto(sb, z, -prof), plano.punto(sb, z, 0), plano.punto(sa, z, 0)]
        malla.cara(pts, [(_uv_pintura(sa), 0), (_uv_pintura(sb), 0), (_uv_pintura(sb), prof / T.PINTURA_M),
                         (_uv_pintura(sa), prof / T.PINTURA_M)], mat_pared, n)


# ---------------------------------------------------------------------------------------------- edificio propio
M_PINTURA, M_VENT, M_PAL, M_VIDRIO = ("Depto_Ext_Mat_FachadaPropia", "Depto_Ext_Mat_VentanasPropias",
                                      "Depto_Ext_Mat_Paleta", "Depto_Ext_Mat_VidrioBaranda")


def _baldosa(rng, ventanal):
    """Baldosa del atlas de ventanas propias: filas 0-3 ventana, 4-7 ventanal; columnas 5-7 encendidas (37,5 %)."""
    fila = (4 if ventanal else 0) + int(rng.integers(4))
    return T.uv_ventana_propia(fila, int(rng.integers(8)))


def _tx(x, col):
    d, s = col
    return d + s * x


def edificio_propio(col):
    rng = np.random.default_rng(SEMILLA)
    fach = Malla("Depto_Ext_Edificio_Fachada", [M_PINTURA, M_VENT, M_PAL])
    balc = Malla("Depto_Ext_Edificio_Balcones", [M_PAL, M_VIDRIO])
    for n in range(1, PISOS + 1):
        for ci, c in enumerate(COLUMNAS):
            x0, x1 = sorted((_tx(XS, c), _tx(XN, c)))
            propio = ci == 0
            if n == 1:                                                  # planta baja: vestíbulo o local vidriado
                zt = z_piso(2) - LOSA
                hueco = (x0 + 0.7, x1 - 0.7, Z_VEREDA + 0.25, Z_VEREDA + 3.1)
                pared(fach, FACHADA, x0, x1, Z_VEREDA, zt, [hueco], M_PINTURA)
                luz = "vestibulo_luz" if ci != 2 else "vestibulo"
                vano_plano(fach, FACHADA, *hueco, luz)
                pared(fach, FACHADA, x0, x1, zt, zt + LOSA, [], M_PINTURA)
                continue
            zn = z_piso(n)
            if not (propio and n == PISO_DEPTO):
                vs = []
                for a, b, ante, dintel, vid in VANOS:
                    xa, xb = sorted((_tx(a, c), _tx(b, c)))
                    vs.append((xa, xb, zn + ante, zn + dintel, vid))
                pared(fach, FACHADA, x0, x1, zn, zn + P.ALTURA_PISO_CIELO, vs, M_PINTURA)
                for xa, xb, za, zb, vid in vs:
                    vano(fach, FACHADA, xa, xb, za, zb, _baldosa(rng, vid == "VEN_LIV"), M_PINTURA, M_VENT,
                         alfeizar=vid != "VEN_LIV")
            if not (propio and n in (PISO_DEPTO - 1, PISO_DEPTO)):         # borde de la losa del piso de arriba
                pared(fach, FACHADA, x0, x1, zn + P.ALTURA_PISO_CIELO, zn + ENTREPISO, [], M_PINTURA)
            if not (propio and n == PISO_DEPTO):
                balcon(balc, c, zn, sin_losa=propio and n == PISO_DEPTO + 1)
    # lateral norte (x = XN), con la ventana del baño de cada piso; el del depto ya es su muro norte
    for n in range(1, PISOS + 1):
        if n == 1:
            zt = z_piso(2) - LOSA
            pared(fach, LATERAL, Y_ATRAS, YF, Z_VEREDA, zt + LOSA, [], M_PINTURA)
            continue
        zn = z_piso(n)
        tramos = [(Y_ATRAS, YE)] if n == PISO_DEPTO else [(Y_ATRAS, YF)]
        for s0, s1 in tramos:
            vs = [(a, b, zn + ante, zn + dintel, vid) for a, b, ante, dintel, vid in VANOS_NORTE if s0 <= a and b <= s1]
            pared(fach, LATERAL, s0, s1, zn, zn + P.ALTURA_PISO_CIELO, vs, M_PINTURA)
            for a, b, za, zb, _ in vs:
                vano(fach, LATERAL, a, b, za, zb, _baldosa(rng, False), M_PINTURA, M_VENT)
        banda = [(Y_ATRAS, YE)] if n in (PISO_DEPTO - 1, PISO_DEPTO) else [(Y_ATRAS, YF)]
        for s0, s1 in banda:
            pared(fach, LATERAL, s0, s1, zn + P.ALTURA_PISO_CIELO, zn + ENTREPISO, [], M_PINTURA)
    piel_depto(fach)
    # parapeto, techo, fondo y extremo sur (no se ven desde el depto: cierran el volumen para las vistas de afuera)
    pared(fach, FACHADA, X_SUR, XN, Z_TECHO, Z_TECHO + PARAPETO, [], M_PINTURA)
    pared(fach, LATERAL, Y_ATRAS, YF, Z_TECHO, Z_TECHO + PARAPETO, [], M_PINTURA)
    fach.plana([(X_SUR, Y_ATRAS, Z_TECHO), (XN, Y_ATRAS, Z_TECHO), (XN, YF, Z_TECHO), (X_SUR, YF, Z_TECHO)], M_PAL,
               (0, 0, 1), "techo")
    fondo = Plano(lambda s, z, d: Vector((s, Y_ATRAS - d, z)), (0, -1, 0), 1)
    sur = Plano(lambda s, z, d: Vector((X_SUR - d, s, z)), (-1, 0, 0), -1)
    pared(fach, fondo, X_SUR, XN, Z_VEREDA, Z_TECHO + PARAPETO, [], M_PINTURA)
    pared(fach, sur, Y_ATRAS, YF, Z_VEREDA, Z_TECHO + PARAPETO, [], M_PINTURA)
    # marquesina de la entrada (columna 1) y el sendero hasta la vereda
    fach.caja(SENDERO[0] - 0.4, SENDERO[1] + 0.4, YF, YF + 1.8, Z_VEREDA + 3.2, Z_VEREDA + 3.38, M_PAL, "losa_balcon",
              caras="xXYzZ")
    return fach.crear(col), balc.crear(col)


def piel_depto(malla):
    """Piel de la franja del depto (PIEL): fachada y lateral norte del 5.º piso de la columna 0, de −0,15 a 2,55, con los
    vanos medidos recortados (fase 2) y los dos cantos de 1 cm hasta la fachada vecina y el lateral del palier."""
    z0, z1 = z_piso(PISO_DEPTO) - LOSA, z_piso(PISO_DEPTO) + ENTREPISO
    pared(malla, FACHADA_PIEL, XS, XN + PIEL, z0, z1, [(a, b, ante, dintel) for a, b, ante, dintel, _ in VANOS],
          M_PINTURA)
    pared(malla, LATERAL_PIEL, YE, YF + PIEL, z0, z1,
          [(a, b, ante, dintel) for a, b, ante, dintel, _ in VANOS_NORTE], M_PINTURA)
    uvs = [(0.0, _uv_pintura(z0)), (PIEL / T.PINTURA_M, _uv_pintura(z0)), (PIEL / T.PINTURA_M, _uv_pintura(z1)),
           (0.0, _uv_pintura(z1))]
    malla.cara([(XS, YF, z0), (XS, YF + PIEL, z0), (XS, YF + PIEL, z1), (XS, YF, z1)], uvs, M_PINTURA, (-1, 0, 0))
    malla.cara([(XN, YE, z0), (XN + PIEL, YE, z0), (XN + PIEL, YE, z1), (XN, YE, z1)], uvs, M_PINTURA, (0, -1, 0))


def vano_plano(malla, plano, sa, sb, za, zb, color, prof=0.20):
    """Vitrina de la planta baja: vidrio de color plano de la paleta (el vestíbulo con luz de noche) y su vano."""
    pts = [plano.punto(sa, za, -prof), plano.punto(sb, za, -prof), plano.punto(sb, zb, -prof), plano.punto(sa, zb, -prof)]
    malla.plana(pts, M_PAL, plano.normal, color)
    t = plano.t()
    for s, n in ((sa, t), (sb, -t)):
        malla.plana([plano.punto(s, za, -prof), plano.punto(s, za, 0), plano.punto(s, zb, 0), plano.punto(s, zb, -prof)],
                    M_PAL, n, "muro_propio")
    for z, n in ((zb, (0, 0, -1)), (za, (0, 0, 1))):
        malla.plana([plano.punto(sa, z, -prof), plano.punto(sb, z, -prof), plano.punto(sb, z, 0), plano.punto(sa, z, 0)],
                    M_PAL, n, "muro_propio")


def balcon(malla, c, zn, sin_losa=False):
    """Balcón de otro piso: losa, vidrio y pasamanos sobre los ejes medidos del nuestro (columna c, piso en zn)."""
    x0, x1 = sorted((_tx(XB0, c), _tx(XB1, c)))
    r0, r1 = sorted((_tx(XR0, c), _tx(XR1, c)))
    zp = zn + Z_BALCON
    if sin_losa:                     # el piso de arriba del nuestro: la losa es Depto_Cielo_Balcon (fase 2)
        zp = P.ALTURA_PISO_CIELO + LOSA
    else:
        malla.caja(x0, x1, YF, YB, zp - LOSA, zp, M_PAL, "losa_balcon", caras="xXYzZ")
    zt = zp + BARANDA_ALTO
    malla.cara([(r0, YR, zp), (r1, YR, zp), (r1, YR, zt), (r0, YR, zt)], [(0, 0)] * 4, M_VIDRIO, (0, 1, 0))
    for x, n in ((r0, (-1, 0, 0)), (r1, (1, 0, 0))):
        malla.cara([(x, YF, zp), (x, YR, zp), (x, YR, zt), (x, YF, zt)], [(0, 0)] * 4, M_VIDRIO, n)
    e = 0.025                        # pasamanos de 5 × 5 cm (como el del depto): cara de arriba y las dos verticales
    malla.caja(r0 - e, r1 + e, YR - e, YR + e, zt - 0.05, zt, M_PAL, "pasamanos", caras="yYZ")
    for x in (r0, r1):
        malla.caja(x - e, x + e, YF, YR - e, zt - 0.05, zt, M_PAL, "pasamanos", caras="xXZ")


# ---------------------------------------------------------------------------------------------- vecinos
def fachadas_textura(m, var, x0, x1, y0, y1, pisos, rng, var_cara=None):
    """Las cuatro caras de un volumen con el atlas de la variante: planta baja en la fila 0 y los pisos tipo en tramos
    de hasta 7 filas. var_cara {normal: variante}: otra variante para alguna cara (la de los balcones corridos, con la
    misma bahía y el mismo piso). Devuelve [(esquina izquierda vista desde afuera, esquina derecha, normal)]."""
    V = T.VARIANTES[var]
    bw, fh, pb = V["bahia"], V["piso"], V["planta_baja"]
    z_pb = Z_VEREDA + pb
    caras = (  # la U crece hacia la derecha de quien mira la cara desde afuera
        ((x0, y0), (x1, y0), (0, -1, 0)), ((x1, y1), (x0, y1), (0, 1, 0)),
        ((x0, y1), (x0, y0), (-1, 0, 0)), ((x1, y0), (x1, y1), (1, 0, 0)))
    for (ax, ay), (bx, by), nrm in caras:
        vc = (var_cara or {}).get(nrm, var)
        assert (T.VARIANTES[vc]["bahia"], T.VARIANTES[vc]["piso"], T.VARIANTES[vc]["planta_baja"]) == (bw, fh, pb)
        mat = f"Depto_Ext_Mat_Fachada{vc}"
        largo = math.hypot(bx - ax, by - ay)
        off = int(rng.integers(8)) * bw
        u0, u1 = off / (T.CELDAS * bw), (largo + off) / (T.CELDAS * bw)

        def quad(za, zb, va, vb):
            m.cara([(ax, ay, za), (bx, by, za), (bx, by, zb), (ax, ay, zb)], [(u0, va), (u1, va), (u1, vb), (u0, vb)],
                   mat, nrm)
        quad(Z_VEREDA, z_pb, 0.0, 1 / T.CELDAS)
        k = 0
        while k < pisos - 1:                          # tramos de hasta 7 pisos (la fila 0 es la planta baja)
            n = min(7, pisos - 1 - k)
            quad(z_pb + k * fh, z_pb + (k + n) * fh, 1 / T.CELDAS, (1 + n) / T.CELDAS)
            k += n
    return caras


def alto_vecino(var, pisos):
    V = T.VARIANTES[var]
    return V["planta_baja"] + (pisos - 1) * V["piso"]


def edificio_vecino(col, nombre, var, x0, x1, y0, y1, pisos, frente, rng):
    V = T.VARIANTES[var]
    balcones = var in VARIANTE_BALCON
    cara_calle = (0, frente, 0)
    var_cara = {cara_calle: VARIANTE_BALCON[var]} if balcones else None
    mats = [f"Depto_Ext_Mat_Fachada{var}"] + ([f"Depto_Ext_Mat_Fachada{VARIANTE_BALCON[var]}"] if balcones else [])
    m = Malla(f"Depto_Ext_Vecino_{nombre}", mats + [M_PAL, M_VIDRIO])
    fh, z_pb = V["piso"], Z_VEREDA + V["planta_baja"]
    top = Z_VEREDA + alto_vecino(var, pisos)
    for (ax, ay), (bx, by), nrm in fachadas_textura(m, var, x0, x1, y0, y1, pisos, rng, var_cara):
        m.plana([(ax, ay, top), (bx, by, top), (bx, by, top + PARAPETO_VECINO), (ax, ay, top + PARAPETO_VECINO)],
                M_PAL, nrm, REMATE[var])
    e = 0.2                                            # parapeto: coronación y cara interior
    zc = top + PARAPETO_VECINO
    for xa, xb, ya, yb in ((x0, x1, y0, y0 + e), (x0, x1, y1 - e, y1), (x0, x0 + e, y0 + e, y1 - e),
                           (x1 - e, x1, y0 + e, y1 - e)):
        m.caja(xa, xb, ya, yb, top, zc, M_PAL, REMATE[var], caras="Z")
    m.caja(x0 + e, x1 - e, y0 + e, y1 - e, top, zc, M_PAL, REMATE[var], caras="xXyY")   # caras interiores
    for f in list(m.bm.faces)[-4:]:                    # la caja de arriba mira hacia afuera: se dan vuelta
        f.normal_flip()
    m.plana([(x0 + e, y0 + e, top), (x1 - e, y0 + e, top), (x1 - e, y1 - e, top), (x0 + e, y1 - e, top)], M_PAL,
            (0, 0, 1), "techo_grava" if var in "AD" else "techo")
    # sala de máquinas y estanque (diseño) en los techos de más de dos pisos
    if pisos > 2:
        cx, cy = x0 + (x1 - x0) * (0.30 + 0.4 * rng.random()), y0 + (y1 - y0) * (0.35 + 0.3 * rng.random())
        m.caja(cx - 1.6, cx + 1.6, cy - 1.4, cy + 1.4, top, top + 2.6, M_PAL, "caja_techo", caras="xXyYZ")
        m.prisma(cx + 3.0, cy, 0.8, top, top + 1.6, 8, M_PAL, "caja_techo", tapa=True)
    # balcones corridos de la variante B en la cara de la calle: uno por piso tipo, con el piso del balcón al nivel del
    # piso (z_pb + k·fh, k = 0 es el 2.º piso, sobre la planta baja) y ninguno en el techo. Corrección 08, ronda 1:
    # el bucle iba de k = 1 a pisos − 1, un piso más arriba (el 2.º sin losa y una losa volada en el techo).
    if balcones:
        yb = y0 if frente < 0 else y1
        ya = yb + frente * BALCON_VECINO
        ymin, ymax = sorted((ya, yb))
        xa, xb = x0 + 0.3, x1 - 0.3
        e = 0.025
        frente_c = "y" if frente < 0 else "Y"
        losas = []
        for k in range(pisos - 1):
            z = z_pb + k * fh
            zt = z + BARANDA_VECINO
            losas.append(round(z, 4))
            m.caja(xa, xb, ymin, ymax, z - LOSA, z, M_PAL, "losa_balcon", caras="xX" + frente_c + "zZ")
            m.cara([(xa, ya, z), (xb, ya, z), (xb, ya, zt), (xa, ya, zt)], [(0, 0)] * 4, M_VIDRIO, cara_calle)
            for x, n in ((xa, (-1, 0, 0)), (xb, (1, 0, 0))):          # vidrio de los extremos del balcón corrido
                m.cara([(x, yb, z), (x, ya, z), (x, ya, zt), (x, yb, zt)], [(0, 0)] * 4, M_VIDRIO, n)
            m.caja(xa, xb, ya - e, ya + e, zt - 0.05, zt, M_PAL, "pasamanos", caras=frente_c + "Z")
        BALCONES_VECINOS[nombre] = dict(losas=losas, top=round(top, 4), pisos=pisos, z_pb=round(z_pb, 4), piso=fh)
    # toldo de la planta baja del café (E6) hacia la calle transversal
    if nombre == "E6":
        m.caja(x1, x1 + 1.6, y0 + 0.5, y1 - 0.5, Z_VEREDA + 2.6, Z_VEREDA + 2.72, M_PAL, "toldo_verde", caras="xXyYzZ")
    return m.crear(col)


# ---------------------------------------------------------------------------------------------- barrio intermedio
# Entre los vecinos modelados (≤ 46 m) y las siluetas (≥ 170 m) el suelo quedaba como una explanada. Manzanas de 60 m
# con calles de 14 m sobre la grilla de las dos calles modeladas (diseño), con volúmenes de las cuatro variantes a lo
# largo de cada borde: cuatro caras con el atlas y el techo, sin parapeto (se ven a 45-150 m).
MANZANA, CALLE_GRILLA = 60.0, 14.0
PASO_GRILLA = MANZANA + CALLE_GRILLA
EJE_X, EJE_Y = (X_CALZ_0 + X_CALZ_1) / 2, (Y_CALZ_0 + Y_CALZ_1) / 2      # ejes de las dos calles modeladas
BARRIO_RADIO = 150.0                                                     # m desde el balcón (CENTRO_VISTA)
BARRIO_PISOS = ((2, 5), (3, 9))                                          # pisos a menos y a más de 90 m (diseño: los
                                                                         # cercanos no tapan el cielo sobre los vecinos)
BARRIO_VARIANTES = ("A", "B", "D", "A", "B", "D", "A", "B", "D", "C")     # el muro cortina, uno de cada diez
MARGEN_VECINOS = 4.0                                                     # m libres alrededor de lo modelado


def huellas_modeladas():
    """Huellas (x0, x1, y0, y1) que el barrio no puede pisar: el edificio propio, los vecinos, E6 y sus calles."""
    h = [(X_SUR, XN, Y_ATRAS, YF + 3.0)]
    h += [(x0, x1, y0, y1) for _, _, x0, x1, y0, y1, _, _ in EDIFICIOS]
    return [(a - MARGEN_VECINOS, b + MARGEN_VECINOS, c - MARGEN_VECINOS, d + MARGEN_VECINOS) for a, b, c, d in h]


def _se_cruzan(a, b):
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def barrio(col, rng):
    m = Malla("Depto_Ext_Barrio", [f"Depto_Ext_Mat_Fachada{v}" for v in "ABCD"] + [M_PAL])
    ocupado = huellas_modeladas()
    n_vol = 0
    for i in range(-3, 4):
        for j in range(-2, 4):
            bx0 = EJE_X + i * PASO_GRILLA + CALLE_GRILLA / 2              # manzana entre dos ejes de la grilla
            by0 = EJE_Y + j * PASO_GRILLA + CALLE_GRILLA / 2
            bx1, by1 = bx0 + MANZANA, by0 + MANZANA
            for lado in range(4):                                         # 0: sur, 1: norte, 2: oeste, 3: este
                s = 2.0
                largo_lado = MANZANA - 4.0
                while s < largo_lado:
                    var = BARRIO_VARIANTES[int(rng.integers(len(BARRIO_VARIANTES)))]
                    V = T.VARIANTES[var]
                    bahias = int(rng.integers(3, 7))
                    ancho = bahias * V["bahia"]
                    fondo = round(12.0 / V["bahia"]) * V["bahia"]
                    if s + ancho > largo_lado:
                        break
                    if lado == 0:
                        fp = (bx0 + s, bx0 + s + ancho, by0 + 2.0, by0 + 2.0 + fondo)
                    elif lado == 1:
                        fp = (bx0 + s, bx0 + s + ancho, by1 - 2.0 - fondo, by1 - 2.0)
                    elif lado == 2:
                        fp = (bx0 + 2.0, bx0 + 2.0 + fondo, by0 + s, by0 + s + ancho)
                    else:
                        fp = (bx1 - 2.0 - fondo, bx1 - 2.0, by0 + s, by0 + s + ancho)
                    s += ancho + (0.0 if rng.random() < 0.7 else 3.0 + 6.0 * rng.random())
                    cx, cy = (fp[0] + fp[1]) / 2, (fp[2] + fp[3]) / 2
                    dist = math.hypot(cx - CENTRO_VISTA[0], cy - CENTRO_VISTA[1])
                    if dist > BARRIO_RADIO:
                        continue
                    if any(_se_cruzan(fp, o) for o in ocupado):
                        continue
                    ocupado.append(fp)
                    p0, p1 = BARRIO_PISOS[dist > 90.0]
                    pisos = int(rng.integers(p0, p1 + 1))
                    fachadas_textura(m, var, *fp, pisos, rng)
                    top = Z_VEREDA + alto_vecino(var, pisos)
                    m.plana([(fp[0], fp[2], top), (fp[1], fp[2], top), (fp[1], fp[3], top), (fp[0], fp[3], top)],
                            M_PAL, (0, 0, 1), "techo_grava" if var in "AD" else "techo")
                    n_vol += 1
    ob = m.crear(col)
    ob["volumenes"] = n_vol
    return ob


# ---------------------------------------------------------------------------------------------- calles y suelo
M_CALLE, M_TERRENO = "Depto_Ext_Mat_Calle", "Depto_Ext_Mat_Terreno"


def calles(col):
    m = Malla("Depto_Ext_Calle", [M_CALLE, M_PAL])
    up = (0, 0, 1)

    def tira_x(x0, x1, y0, y1, z):         # a lo largo de X: u = (y − 6) / 14, v = (x − fase) / 12
        uvs = [T.uv_calle(y - Y_VEREDA_A, x - FASE_CALLE) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        m.cara([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], uvs, M_CALLE, up)

    def tira_y(x0, x1, y0, y1, z):         # a lo largo de Y: u = (x − 16) / 14, v = y / 12
        uvs = [T.uv_calle(x - X_VEREDA_A, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        m.cara([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], uvs, M_CALLE, up)
    tira_x(-LARGO, LARGO, Y_CALZ_0, Y_CALZ_1, Z_CALLE)                       # calzada principal, con el cruce
    for xa, xb in ((-LARGO, X_CALZ_0), (X_CALZ_1, LARGO)):                   # veredas de la principal
        tira_x(xa, xb, Y_VEREDA_A, Y_CALZ_0, Z_VEREDA)
        tira_x(xa, xb, Y_CALZ_1, Y_VEREDA_B, Z_VEREDA)
    for ya, yb in ((-LARGO, Y_CALZ_0), (Y_CALZ_1, LARGO)):                    # calzada transversal
        tira_y(X_CALZ_0, X_CALZ_1, ya, yb, Z_CALLE)
    for ya, yb in ((-LARGO, Y_VEREDA_A), (Y_VEREDA_B, LARGO)):               # veredas de la transversal
        tira_y(X_VEREDA_A, X_CALZ_0, ya, yb, Z_VEREDA)
        tira_y(X_CALZ_1, X_VEREDA_B, ya, yb, Z_VEREDA)
    # soleras (la cara vertical hacia la calzada)
    for xa, xb in ((-LARGO, X_CALZ_0), (X_CALZ_1, LARGO)):
        m.plana([(xa, Y_CALZ_0, Z_CALLE), (xb, Y_CALZ_0, Z_CALLE), (xb, Y_CALZ_0, Z_VEREDA), (xa, Y_CALZ_0, Z_VEREDA)],
                M_PAL, (0, 1, 0), "solera")
        m.plana([(xa, Y_CALZ_1, Z_CALLE), (xb, Y_CALZ_1, Z_CALLE), (xb, Y_CALZ_1, Z_VEREDA), (xa, Y_CALZ_1, Z_VEREDA)],
                M_PAL, (0, -1, 0), "solera")
    for ya, yb in ((-LARGO, Y_CALZ_0), (Y_CALZ_1, LARGO)):
        m.plana([(X_CALZ_0, ya, Z_CALLE), (X_CALZ_0, yb, Z_CALLE), (X_CALZ_0, yb, Z_VEREDA), (X_CALZ_0, ya, Z_VEREDA)],
                M_PAL, (1, 0, 0), "solera")
        m.plana([(X_CALZ_1, ya, Z_CALLE), (X_CALZ_1, yb, Z_CALLE), (X_CALZ_1, yb, Z_VEREDA), (X_CALZ_1, ya, Z_VEREDA)],
                M_PAL, (-1, 0, 0), "solera")
    # pasos de cebra (franjas de 0,5 m con 0,5 m de separación, 2 cm sobre el asfalto)
    zc = Z_CALLE + 0.02
    CEBRAS.clear()
    LINEAS.clear()
    for ya, yb in ((Y_VEREDA_A + 0.3, Y_CALZ_0 - 0.3), (Y_CALZ_1 + 0.3, Y_VEREDA_B - 0.3)):   # cruzan la transversal
        x = X_CALZ_0 + 0.25
        while x + 0.5 <= X_CALZ_1 - 0.2:
            m.plana([(x, ya, zc), (x + 0.5, ya, zc), (x + 0.5, yb, zc), (x, yb, zc)], M_PAL, up, "marca_blanca")
            CEBRAS.append((x, x + 0.5, ya, yb))
            x += 1.0
    for xa, xb in ((X_VEREDA_A + 0.3, X_CALZ_0 - 0.3), (X_CALZ_1 + 0.3, X_VEREDA_B - 0.3)):   # cruzan la principal
        y = Y_CALZ_0 + 0.25
        while y + 0.5 <= Y_CALZ_1 - 0.2:
            m.plana([(xa, y, zc), (xb, y, zc), (xb, y + 0.5, zc), (xa, y + 0.5, zc)], M_PAL, up, "marca_blanca")
            CEBRAS.append((xa, xb, y, y + 0.5))
            y += 1.0
    # línea central segmentada de las dos calles (LINEA_*), en el eje de sus pistas
    LC = T.LINEA_CENTRAL
    w = LC["ancho"] / 2
    for eje, centro in (("x", Y_CALZ_0 + T.EJE_PISTAS), ("y", X_CALZ_0 + T.EJE_PISTAS)):
        libre0, libre1 = LINEA_LIBRE[eje]
        k = math.ceil((-LINEA_ALCANCE - LINEA_FASE[eje]) / LC["periodo"])
        while True:
            a = LINEA_FASE[eje] + k * LC["periodo"]
            b = a + LC["largo"]
            k += 1
            if b > LINEA_ALCANCE:
                break
            if b > libre0 and a < libre1:                  # dentro del cruce o de sus cebras: se salta
                continue
            r = (a, b, centro - w, centro + w) if eje == "x" else (centro - w, centro + w, a, b)
            m.plana([(r[0], r[2], zc), (r[1], r[2], zc), (r[1], r[3], zc), (r[0], r[3], zc)], M_PAL, up,
                    "marca_blanca")
            LINEAS.append(r)
    return m.crear(col)


def suelo(col):
    m = Malla("Depto_Ext_Suelo", [M_TERRENO, M_PAL])
    up = (0, 0, 1)
    cx0, cx1, cy0, cy1 = CERCA
    for x0, x1, y0, y1 in ((cx0, X_VEREDA_A, cy0, Y_VEREDA_A), (X_VEREDA_B, cx1, cy0, Y_VEREDA_A),
                           (cx0, X_VEREDA_A, Y_VEREDA_B, cy1), (X_VEREDA_B, cx1, Y_VEREDA_B, cy1)):
        m.cara([(x0, y0, Z_VEREDA), (x1, y0, Z_VEREDA), (x1, y1, Z_VEREDA), (x0, y1, Z_VEREDA)],
               [(x / T.TERRENO_M, y / T.TERRENO_M) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))], M_TERRENO, up)
    zl = Z_CALLE - 0.05                                   # bajo la calzada: sólo se ve fuera de los lotes cercanos
    m.plana([(-LEJOS, -LEJOS, zl), (LEJOS, -LEJOS, zl), (LEJOS, LEJOS, zl), (-LEJOS, LEJOS, zl)], M_PAL, up,
            "suelo_lejano")
    # antejardín propio: sendero a la entrada, murete en el deslinde y arbustos
    zs = Z_VEREDA + 0.02
    m.plana([(SENDERO[0], YF, zs), (SENDERO[1], YF, zs), (SENDERO[1], Y_VEREDA_A, zs), (SENDERO[0], Y_VEREDA_A, zs)],
            M_PAL, up, "sendero")
    for xa, xb in ((X_SUR, SENDERO[0]), (SENDERO[1], X_VEREDA_A - 1.0)):
        m.caja(xa, xb, Y_VEREDA_A - 0.2, Y_VEREDA_A, Z_VEREDA, Z_VEREDA + 0.5, M_PAL, "muro_bajo", caras="xXyYZ")
    rng = np.random.default_rng(SEMILLA + 3)
    for x in ARBUSTOS_X:
        r = 0.55 + 0.25 * rng.random()
        esfera(m, (x, 5.0 + 0.2 * rng.random(), Z_VEREDA + 0.6 * r), (r, r, 0.8 * r), 0, M_PAL, "arbusto", rng, 0.15)
    return m.crear(col)


COPAS = []                               # (centro, radios) de cada copa, con el margen del jitter (para pruebas())
JITTER_COPA = 0.1


def arboles(col):
    m = Malla("Depto_Ext_Arboles", [M_PAL])
    rng = np.random.default_rng(SEMILLA + 5)
    copas = ("copa_1", "copa_2", "copa_3", "copa_4")
    COPAS.clear()
    for x, y in ARBOLES:
        ht = 2.4 + 0.8 * rng.random()                      # fuste libre (diseño: árboles de calle de 7-9 m)
        R = 2.0 + 0.8 * rng.random()
        zc = Z_VEREDA + ht + 0.8 * R
        m.plana([(x - 0.6, y - 0.6, Z_VEREDA + 0.01), (x + 0.6, y - 0.6, Z_VEREDA + 0.01),
                 (x + 0.6, y + 0.6, Z_VEREDA + 0.01), (x - 0.6, y + 0.6, Z_VEREDA + 0.01)], M_PAL, (0, 0, 1), "tierra")
        m.prisma(x, y, 0.11 + 0.05 * rng.random(), Z_VEREDA, zc, 6, M_PAL, "tronco")
        color = copas[int(rng.integers(len(copas)))]
        esfera(m, (x, y, zc), (R, R, 0.85 * R), 1, M_PAL, color, rng, JITTER_COPA)
        a = 2 * math.pi * rng.random()
        c2 = (x + 0.45 * R * math.cos(a), y + 0.45 * R * math.sin(a), zc + 0.5 * R)
        r2 = (0.62 * R,) * 2 + (0.55 * R,)
        esfera(m, c2, r2, 1, M_PAL, color, rng, JITTER_COPA)
        k = 1 + JITTER_COPA
        COPAS.append(dict(eje=(x, y), R=R, elipsoides=[((x, y, zc), (k * R, k * R, k * 0.85 * R)),
                                                       (c2, tuple(k * r for r in r2))]))
    return m.crear(col)


def cabezal(x, y, lado):
    """Cajas del brazo, de la carcasa y del refractor de una luminaria: [(x0, x1, y0, y1, z0, z1)]."""
    ya, yb = sorted((y, y + lado * BRAZO))
    yc = y + lado * BRAZO
    c0, c1 = sorted((yc, yc + lado * CABEZAL[1]))
    zt = Z_VEREDA + POSTE_ALTO
    w = CABEZAL[0] / 2
    return {"brazo": (x - 0.05, x + 0.05, ya, yb, zt - 0.1, zt),
            "carcasa": (x - w, x + w, c0, c1, zt - 0.13, zt - 0.03),
            "refractor": (x - w + 0.03, x + w - 0.03, c0 + 0.03, c1 - 0.03, zt - 0.25, zt - 0.13)}


def centro_luz(x, y, lado):
    """Pie de la vertical del refractor (x, y) y su altura z: el centro de la mancha de luz y la posición del foco."""
    c = cabezal(x, y, lado)["refractor"]
    return (c[0] + c[1]) / 2, (c[2] + c[3]) / 2, c[4]


def mobiliario(col):
    m = Malla("Depto_Ext_Mobiliario", [M_PAL])
    for x, y, lado in LUMINARIAS:                          # poste de 7 m con brazo hacia la calzada
        m.prisma(x, y, 0.08, Z_VEREDA, Z_VEREDA + POSTE_ALTO, 6, M_PAL, "poste")
        c = cabezal(x, y, lado)
        m.caja(*c["brazo"], M_PAL, "poste", caras="xXyYzZ")
        m.caja(*c["carcasa"], M_PAL, "poste", caras="xXyYZ")
        # refractor emisivo bajo la carcasa: se ve encendido desde arriba y de lado (corrección 08, ronda 1: la única
        # cara emisiva miraba hacia abajo y desde el depto sólo se veía la tapa oscura)
        m.caja(*c["refractor"], M_PAL, "luminaria", caras="xXyYz")
    for x, y, giro, color in AUTOS:                        # autos estacionados junto a la solera (4,3 × 1,8 m)
        a = math.radians(giro)
        ca, sa = math.cos(a), math.sin(a)

        def p(u, v, z):
            return (x + u * ca - v * sa, y + u * sa + v * ca, Z_CALLE + z)

        def caja_auto(u0, u1, v0, v1, z0, z1, col_, caras, techo=None):
            pts = {"x": ([p(u0, v0, z0), p(u0, v1, z0), p(u0, v1, z1), p(u0, v0, z1)], (-ca, -sa, 0)),
                   "X": ([p(u1, v0, z0), p(u1, v1, z0), p(u1, v1, z1), p(u1, v0, z1)], (ca, sa, 0)),
                   "y": ([p(u0, v0, z0), p(u1, v0, z0), p(u1, v0, z1), p(u0, v0, z1)], (sa, -ca, 0)),
                   "Y": ([p(u0, v1, z0), p(u1, v1, z0), p(u1, v1, z1), p(u0, v1, z1)], (-sa, ca, 0)),
                   "Z": ([p(u0, v0, z1), p(u1, v0, z1), p(u1, v1, z1), p(u0, v1, z1)], (0, 0, 1))}
            for k in caras:
                pts_, n = pts[k]
                m.plana(pts_, M_PAL, n, techo if (k == "Z" and techo) else col_)
        caja_auto(-2.15, 2.15, -0.9, 0.9, 0.28, 0.85, color, "xXyYZ")
        # cabina: vidrios a los lados y techo del color del auto, más angosta arriba
        t0, t1, s0, s1 = -1.0, 1.05, -0.78, 0.78
        cab = [p(t0, s0, 0.85), p(t1, s0, 0.85), p(t1, s1, 0.85), p(t0, s1, 0.85)]
        arriba = [p(t0 + 0.35, s0 + 0.08, 1.42), p(t1 - 0.25, s0 + 0.08, 1.42), p(t1 - 0.25, s1 - 0.08, 1.42),
                  p(t0 + 0.35, s1 - 0.08, 1.42)]
        centro = Vector((x, y, Z_CALLE + 0.85))
        for i in range(4):
            j = (i + 1) % 4
            nm = (Vector(cab[i]) + Vector(cab[j])) / 2 - centro             # hacia afuera de la cabina
            m.plana([cab[i], cab[j], arriba[j], arriba[i]], M_PAL, (nm.x, nm.y, 0.3), "vidrio_auto")
        m.plana(arriba, M_PAL, (0, 0, 1), color)
        for u in (-1.35, 1.35):                             # ruedas: caras laterales oscuras
            for v, n in ((-0.905, (sa, -ca, 0)), (0.905, (-sa, ca, 0))):
                m.plana([p(u - 0.33, v, 0.0), p(u + 0.33, v, 0.0), p(u + 0.33, v, 0.62), p(u - 0.33, v, 0.62)],
                        M_PAL, n, "neumatico")
    return m.crear(col)


# Suelo alrededor de las luminarias (x0, x1, y0, y1, z, clara): la mancha de luz se corta en estas piezas para quedar
# 3 cm sobre cada superficie; `clara` elige la mitad de la textura de la vereda (que refleja ≈ 8 veces más que el
# asfalto) o la de lo oscuro (asfalto y pasto).
INF = 1.0e3
SUELO_LUMINARIAS = (
    (-INF, INF, Y_CALZ_0, Y_CALZ_1, Z_CALLE, False),                              # calzada principal y cruce
    (-INF, X_CALZ_0, Y_VEREDA_A, Y_CALZ_0, Z_VEREDA, True), (X_CALZ_1, INF, Y_VEREDA_A, Y_CALZ_0, Z_VEREDA, True),
    (-INF, X_CALZ_0, Y_CALZ_1, Y_VEREDA_B, Z_VEREDA, True), (X_CALZ_1, INF, Y_CALZ_1, Y_VEREDA_B, Z_VEREDA, True),
    (X_CALZ_0, X_CALZ_1, -INF, Y_CALZ_0, Z_CALLE, False), (X_CALZ_0, X_CALZ_1, Y_CALZ_1, INF, Z_CALLE, False),
    (X_VEREDA_A, X_CALZ_0, -INF, Y_VEREDA_A, Z_VEREDA, True), (X_VEREDA_A, X_CALZ_0, Y_VEREDA_B, INF, Z_VEREDA, True),
    (-INF, X_VEREDA_A, YF, Y_VEREDA_A, Z_VEREDA, False), (-INF, X_VEREDA_A, Y_VEREDA_B, INF, Z_VEREDA, False),
)
SOBRE_SUELO_LUZ = 0.03                   # m: sobre el sendero y los pasos de cebra (2 cm)


def luz_suelo(col):
    m = Malla("Depto_Ext_LuzSuelo", ["Depto_Ext_Mat_LuzSuelo"])
    R = T.radio_luz_suelo()
    for x, y, lado in LUMINARIAS:
        cx, cy, _ = centro_luz(x, y, lado)
        for x0, x1, y0, y1, z, clara in SUELO_LUMINARIAS:
            a0, a1, b0, b1 = max(x0, cx - R), min(x1, cx + R), max(y0, cy - R), min(y1, cy + R)
            if a1 - a0 < 0.05 or b1 - b0 < 0.05:
                continue
            dx = min(abs(cx - v) for v in (a0, a1)) if not a0 <= cx <= a1 else 0.0
            dy = min(abs(cy - v) for v in (b0, b1)) if not b0 <= cy <= b1 else 0.0
            if T.perfil_luz_suelo(math.hypot(dx, dy)) < 0.01:                # la pieza queda fuera de la mancha
                continue
            pts = [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]
            m.cara([(px, py, z + SOBRE_SUELO_LUZ) for px, py in pts],
                   [T.uv_luz_suelo(px - cx, py - cy, clara) for px, py in pts], "Depto_Ext_Mat_LuzSuelo", (0, 0, 1))
    return m.crear(col)


def lejanos(col):
    """Tarjetas de siluetas: una fila de edificios de anchos y altos al azar por tarjeta, mirando al balcón."""
    objs = []
    rng = np.random.default_rng(SEMILLA + 7)
    for k, (mat, r0, r1, a0, a1, n, h0, h1) in enumerate(CAPAS_LEJANAS):
        m = Malla(f"Depto_Ext_Lejanos{k + 1}", [mat])
        paso = (a1 - a0) / n
        for i in range(n):
            a = math.radians(a0 + paso * (i + 0.5) + paso * 0.15 * (2 * rng.random() - 1))
            r = r0 + (r1 - r0) * rng.random()
            cx, cy = CENTRO_VISTA[0] + r * math.cos(a), CENTRO_VISTA[1] + r * math.sin(a)
            hacia = Vector((-math.cos(a), -math.sin(a), 0.0))            # normal: hacia el depto
            tang = Vector((math.sin(a), -math.cos(a), 0.0))              # a la derecha de quien mira desde el depto
            ancho = 2 * r * math.tan(math.radians(paso * 0.62))
            s = -ancho / 2
            z0 = Z_CALLE - 0.05
            while s < ancho / 2:
                w = min(8.0 + 16.0 * rng.random(), ancho / 2 - s)
                if w < 4.0:
                    break
                h = h0 + (h1 - h0) * rng.random() ** 1.6
                pa = Vector((cx, cy, 0)) + tang * s
                pb = Vector((cx, cy, 0)) + tang * (s + w)
                uva, uvb = s / T.LEJANOS_M, (s + w) / T.LEJANOS_M
                zt = Z_VEREDA + h
                m.cara([(pa.x, pa.y, z0), (pb.x, pb.y, z0), (pb.x, pb.y, zt), (pa.x, pa.y, zt)],
                       [(uva, 0), (uvb, 0), (uvb, (zt - z0) / T.LEJANOS_M), (uva, (zt - z0) / T.LEJANOS_M)], mat, hacia)
                if rng.random() < 0.35 and w > 10:                          # remate más angosto
                    q = 0.2 + 0.2 * rng.random()
                    pc, pd = pa + tang * (w * q), pb - tang * (w * q)
                    zz = zt + 3.0 + 6.0 * rng.random()
                    uc, ud = (s + w * q) / T.LEJANOS_M, (s + w - w * q) / T.LEJANOS_M
                    m.cara([(pc.x, pc.y, zt), (pd.x, pd.y, zt), (pd.x, pd.y, zz), (pc.x, pc.y, zz)],
                           [(uc, (zt - z0) / T.LEJANOS_M), (ud, (zt - z0) / T.LEJANOS_M), (ud, (zz - z0) / T.LEJANOS_M),
                            (uc, (zz - z0) / T.LEJANOS_M)], mat, hacia)
                s += w + (0.0 if rng.random() < 0.6 else 2.0 + 5.0 * rng.random())
        objs.append(m.crear(col))
    return objs


# ---------------------------------------------------------------------------------------------- cielo y datos
def sol_hdr(ruta):
    """Píxel más brillante del HDR (el sol, o la luna de noche) -> (azimut de Blender desde +X, elevación), grados.
    Convención de Blender (y de three.js, contrato sección 6): u = 0,5 − azimut / 360, v = 0,5 + elevación / 180."""
    im = bpy.data.images.load(ruta, check_existing=True)
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    lum = px.reshape(h, w, 4)[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    fila, colm = divmod(int(np.argmax(lum)), w)
    bpy.data.images.remove(im)
    return round((0.5 - (colm + 0.5) / w) * 360.0, 1), round(((fila + 0.5) / h - 0.5) * 180.0, 1)


def azimut_sol_escena():
    """Azimut (grados desde +X) hacia el sol de la fase 5 (Depto_Luz_Sol apunta por su −Z)."""
    o = bpy.data.objects["Depto_Luz_Sol"]
    d = -(o.matrix_world.to_3x3() @ Vector((0, 0, -1)))
    return math.degrees(math.atan2(d.y, d.x)), math.degrees(math.asin(max(-1.0, min(1.0, d.z))))


def datos_cielo(tris):
    fuentes = {}
    for k, cid in CIELOS.items():
        hdr = os.path.join(HDRI, cid, f"{cid}_1k.hdr")
        jpg = os.path.join(HDRI, cid, f"{cid}_2048.jpg")
        az, el = sol_hdr(hdr)
        fuentes[k] = {"id": cid, "hdr": os.path.relpath(hdr, RAIZ), "jpg": os.path.relpath(jpg, RAIZ),
                      "sol_azimut_deg": az, "sol_elevacion_deg": el}
    az_escena, el_escena = azimut_sol_escena()
    rot = round((az_escena - fuentes["dia"]["sol_azimut_deg"] + 180.0) % 360.0 - 180.0, 1)
    return {
        "panoramas": {k: PANORAMA.format(k) for k in CIELOS},
        "rotacion_deg": rot, "suelo_y": Z_CALLE,
        "rotacion_origen": (f"medido: lleva el sol del HDR de día (azimut {fuentes['dia']['sol_azimut_deg']}°) al "
                            f"de la escena ({az_escena:.1f}°, elevación {el_escena:.1f}°); los tres HDR tienen el sol "
                            "a menos de 4° entre sí"),
        "fuentes": fuentes, "emision": EMISION_MOMENTO, "cielo_camara": CIELO_CAMARA,
        # focos de las luminarias para los renders de Blender (tools/render_08.py): la misma mancha que la textura
        # luz_suelo que suma el visor (ext_texturas.LUZ_SUELO)
        "luminarias": {"posiciones": [list(map(lambda v: round(v, 3), centro_luz(x, y, lado))) for x, y, lado in LUMINARIAS],
                       "medio_angulo_deg": T.LUZ_SUELO["medio_angulo_deg"], "borde": T.LUZ_SUELO["borde"],
                       "color": T.LUZ_SUELO["color"]},
        "altura_piso_m": -Z_CALLE, "piso": PISO_DEPTO, "pisos": PISOS, "triangulos": tris,
        "supuestos": "piso del depto a 12,5 m sobre la calle (5.º de 8), calles, vecinos y árboles de diseño",
    }


# ---------------------------------------------------------------------------------------------- pruebas
def _tris(objs):
    t = 0
    for o in objs:
        o.data.calc_loop_triangles()
        t += len(o.data.loop_triangles)
    return t


def cajas_prohibidas():
    """Volúmenes del depto, del balcón y del palier (m de Blender): el exterior no entra en ellos (> 1 mm)."""
    pal = bpy.data.objects.get("Depto_Palier_Muros")
    # el balcón empieza a 2·PIEL de la fachada: la piel de la franja del depto (a PIEL del muro) es el muro, no entra
    # en el balcón
    out = [("depto", (XS, XN, YE, YF, -LOSA, P.ALTURA_PISO_CIELO + LOSA)),
           ("balcon", (XB0, XB1, YF + 2 * PIEL, YB, Z_BALCON - LOSA, P.ALTURA_PISO_CIELO + LOSA))]
    if pal:
        pts = [pal.matrix_world @ Vector(c) for c in pal.bound_box]
        out.append(("palier", (min(p.x for p in pts), max(p.x for p in pts), min(p.y for p in pts),
                               max(p.y for p in pts), -LOSA, P.ALTURA_PISO_CIELO + LOSA)))
    return out


def _dentro_elipsoide(p, centro, radios):
    return sum(((p[k] - centro[k]) / radios[k]) ** 2 for k in range(3)) < 1.0


def pruebas_piezas():
    """Choques entre piezas del exterior (corrección 08, ronda 1), balcones de los vecinos B y, desde la ronda 2, la
    línea central fuera del cruce y de los pasos de cebra."""
    fallos = []
    cruce = (X_CALZ_0, X_CALZ_1, Y_CALZ_0, Y_CALZ_1)
    if not LINEAS or not CEBRAS:
        fallos.append("faltan la línea central o los pasos de cebra")
    for r in LINEAS:
        for c in CEBRAS + [cruce]:
            if _se_cruzan(r, c):
                fallos.append(f"línea central {tuple(round(v, 2) for v in r)} dentro de {tuple(round(v, 2) for v in c)}")
    r_max = max(c["R"] for c in COPAS)
    minimo = 1.1 * r_max + 0.3                       # la copa, con su jitter, más 30 cm de holgura
    for x, y, lado in LUMINARIAS:
        for c in COPAS:
            d = math.hypot(x - c["eje"][0], y - c["eje"][1])
            if d < minimo:
                fallos.append(f"luminaria ({x}, {y}) a {d:.2f} m del árbol {c['eje']} (mínimo {minimo:.2f} m)")
        for pieza, (x0, x1, y0, y1, z0, z1) in cabezal(x, y, lado).items():
            for p in ((a, b, z) for a in (x0, x1) for b in (y0, y1) for z in (z0, z1)):
                for c in COPAS:
                    if any(_dentro_elipsoide(p, ce, ra) for ce, ra in c["elipsoides"]):
                        fallos.append(f"luminaria ({x}, {y}): el {pieza} entra en la copa del árbol {c['eje']}")
                        break
    for nombre, *_ in EDIFICIOS:
        b = BALCONES_VECINOS.get(nombre)
        if b is None:
            continue
        esperadas = [round(b["z_pb"] + k * b["piso"], 4) for k in range(b["pisos"] - 1)]
        if any(z >= b["top"] - 0.01 for z in b["losas"]):
            fallos.append(f"{nombre}: una losa de balcón en el techo ({b['losas']}, techo {b['top']})")
        if sorted(b["losas"]) != esperadas:
            fallos.append(f"{nombre}: losas de balcón {b['losas']}, se esperaba una por piso tipo {esperadas}")
    return fallos


def pruebas(objs, total_escena):
    fallos = []
    tris = _tris(objs)
    if tris > TOPE_EXTERIOR:
        fallos.append(f"exterior con {tris} triángulos (tope {TOPE_EXTERIOR})")
    if total_escena > G.TOPE_TRIANGULOS:
        fallos.append(f"escena con {total_escena} triángulos (tope {G.TOPE_TRIANGULOS})")
    for o in objs:
        if not o.name.startswith("Depto_Ext_"):
            fallos.append(f"{o.name}: sin el prefijo Depto_Ext_")
        if o.get("colision") is not False or o.get("exterior") is not True:
            fallos.append(f"{o.name}: falta colision = False o exterior = True")
        if not o.data.uv_layers:
            fallos.append(f"{o.name}: sin UV")
        for m in o.data.materials:
            if m is None or not m.get("exterior") or not m.name.startswith("Depto_Ext_Mat_"):
                fallos.append(f"{o.name}: material {m.name if m else None} sin exterior = True")
    # nada dentro del depto, del balcón ni del palier (caras sueltas: la caja de cada cara)
    prohibidas = cajas_prohibidas()
    for o in objs:
        mw = o.matrix_world
        for f in o.data.polygons:
            pts = [mw @ o.data.vertices[i].co for i in f.vertices]
            lo = [min(p[k] for p in pts) for k in range(3)]
            hi = [max(p[k] for p in pts) for k in range(3)]
            for nombre, (x0, x1, y0, y1, z0, z1) in prohibidas:
                caja = ((x0, x1), (y0, y1), (z0, z1))
                if all(min(hi[k], caja[k][1]) - max(lo[k], caja[k][0]) > 1e-3 for k in range(3)):
                    fallos.append(f"{o.name}: una cara entra en el volumen del {nombre} ({lo}, {hi})")
                    break
    fallos += pruebas_piezas()
    # vista libre: rayos desde cada ventana propia hacia afuera (abanico de ±40° y de −35° a +20°)
    verts, polys = [], []
    for o in objs:
        base = len(verts)
        verts += [o.matrix_world @ v.co for v in o.data.vertices]
        polys += [[base + i for i in f.vertices] for f in o.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)
    minimo = {}
    for a, b, ante, dintel, vid in VANOS:
        orig = Vector(((a + b) / 2, YF - 0.3, max(ante, 0.9) + 0.5))
        d_min = math.inf
        for az in range(-40, 41, 10):
            for el in range(-35, 21, 11):
                d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)),
                            math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
                hit = bvh.ray_cast(orig, d, 1e4)
                if hit[0] is not None:
                    d_min = min(d_min, hit[3])
        minimo[vid] = round(d_min, 2)
        if d_min < 3.0:
            fallos.append(f"ventana {vid}: el exterior tapa la vista a {d_min:.2f} m")
    return fallos, tris, minimo


# ---------------------------------------------------------------------------------------------- principal
def main():
    scene = bpy.context.scene
    SE.exigir(scene, "05", bpy.data.filepath)
    root = bpy.data.collections["Depto"]
    cols = G.colecciones_fase(root, (COL,))
    col = cols[COL]
    tex = T.generar()
    for nombre, spec in MATERIALES.items():
        material_ext(nombre, spec, tex)
    rng = np.random.default_rng(SEMILLA + 11)
    objs = [*edificio_propio(col)]
    for e in EDIFICIOS:
        objs.append(edificio_vecino(col, *e, rng))
    objs += [barrio(col, np.random.default_rng(SEMILLA + 13)), calles(col), suelo(col), arboles(col), mobiliario(col),
             luz_suelo(col), *lejanos(col)]
    bpy.context.view_layer.update()
    visibles = [o for o in root.all_objects if o.type == "MESH" and not o.hide_render
                and not o.name.startswith("Depto_Ref")]
    total = _tris(visibles)
    fallos, tris, vista = pruebas(objs, total)
    for f in fallos:
        print("FALLA", f)
    if fallos:
        raise SystemExit(f"ERROR: {len(fallos)} pruebas de la fase 08 fallan; no se guarda el maestro.")
    datos = datos_cielo(tris)
    scene["depto_exterior"] = json.dumps(datos, ensure_ascii=False)
    SE.sellar(scene, "08")
    bpy.ops.wm.save_mainfile(filepath=SE.MAESTRO)
    por_obj = {o.name: len(o.data.polygons) for o in objs}
    print(f"CHECK fase 08: {len(objs)} objetos, {tris} triángulos de exterior (tope {TOPE_EXTERIOR}), escena "
          f"{total} (tope {G.TOPE_TRIANGULOS}), {len(MATERIALES)} materiales; rotación del cielo "
          f"{datos['rotacion_deg']}°; vista libre desde las ventanas (m): {vista}")
    print("CHECK caras por objeto:", por_obj)
    print(f"FASE_OK Depto_08_exterior {len(objs)} {tris} sello={scene['depto_fase08']}")


if __name__ == "__main__":
    main()
