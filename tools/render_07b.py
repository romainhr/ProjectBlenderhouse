"""Renders de revisión de la fase 07b: clósets y nevera abiertos, noche con las luces cálidas por grupo, primer
plano de interruptores y un día normal del living.

Uso:
    blender -b build/depto.blend --python tools/render_07b.py -- --out review/depto_07b \
        [--solo closet_D1_colgar,noche_living] [--samples 64] [--size 1280x800]

No guarda el .blend. Para cada vista: abre las piezas móviles que pide (con su propio angulo_abierta_deg o
recorrido_m + eje_apertura, como el visor), cierra las que pide, prende sólo los grupos de luz indicados (las
luces de los otros grupos se ocultan y sus ampolletas pasan a un material apagado; las encendidas, a una copia del
emisivo con el color de su grupo, como en el visor) y elige mundo de día (HDRI de día de Poly Haven con el sol de la
fase 5) o de noche (cielo HDRI casi apagado y sin sol). Escribe <out>/<vista>.png y <out>/renders.json =
[{archivo, que_muestra, abiertos (todo lo abierto en el render, también lo que el maestro trae abierto), ...}].

Supuestos de revisión (no van al GLB): un volumen de irradiancia y un cubemap por recinto horneados con el mundo y las luces de cada vista (--sin-gi lo
omite), una sonda plana en cada espejo, un suelo neutro oscuro bajo el horizonte del mundo (luz y reflejos), un vidrio
de revisión (transparente con reflejo de Fresnel, sin sombra) en lugar del vidrio del GLB. Corrección 07c (ronda 2):
sin adaptación cromática por defecto (ver BALANCE) y la luz interior de la nevera es la del modelo (grupo que la puerta
prende al abrirse, `enciende`), no un LED de revisión.
"""
import argparse
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_plano as P  # noqa: E402

HDRI_NOCHE = os.path.join(RAIZ, "assets", "hdri", "kloppenheim_02_puresky", "kloppenheim_02_puresky_1k.hdr")
HDRI_DIA = os.path.join(RAIZ, "assets", "hdri", "kloofendal_48d_partly_cloudy_puresky",
                        "kloofendal_48d_partly_cloudy_puresky_1k.hdr")
DIA = dict(fuerza=1.6, saturacion=0.35, fuerza_camara=0.45)   # supuesto de revisión: cielo de día (HDRI de Poly
# Haven) desaturado para iluminar (muros blancos sin tinte azul) y con su color, más tenue, para lo que ve la cámara
# por las ventanas (si no, el exterior se quemaba a blanco al exponer para el interior); el sol de 3 W de la fase 5
SUELO_MUNDO = (0.12, 0.12, 0.11)   # supuesto de revisión: suelo neutro oscuro bajo el horizonte (lineal, antes de la
# fuerza) en la luz del mundo, como depto_05.mundo() (SUELO_COLOR): sin él, el roble, la melamina y el acero reflejaban
# el cielo bajo el horizonte del HDRI (≈ 0,5 lineal con la fuerza de 1,6) y se leían escarchados o con un barrido azul
# Adaptación cromática de la cámara (ASC-CDL, pendiente por canal, en el compositor; no toca las luces). Corrección 07c
# (ronda 2): desactivada por defecto. La pendiente fija (0,85, 1, 1,45) de las vistas con lámparas no existe en el visor
# y teñía de azul lavanda lo iluminado de día y de malva el acero: lo que se aprobaba no era el color del producto. Una
# vista puede pedir una pendiente propia con `balance` (la rotula el texto y renders.json).
BALANCE = {"lamparas": None, "dia": None}
VIDRIOS_REVISION = ("Depto_Mat_Vidrio", "Depto_Mat_VidrioReloj")
TODOS = "*"
# Cajones de cocina que el maestro trae abiertos (estado inicial del recorrido): las vistas de ambiente los cierran.
MUEBLES = ("cajon", "mueble", "nevera", "closet")

# vista: cámara (pos px, z, objetivo px, z objetivo, lente mm) o nombre de una cámara del maestro; abrir, cerrar,
# ocultar, grupos de luz encendidos, mundo, exposición, look, balance (pendiente ASC-CDL o None; por defecto
# BALANCE), ssr y descripción. cerrar_muebles: cierra
# todo cajón, mueble, nevera y clóset que no se pida abrir. Orden: las vistas con el mismo horneado (mundo y luces) van
# seguidas.
CAM_D1_REPISAS_DER = ((298.0, 64.0), 1.42, (324.0, 140.0), 0.95, 12.0)
CAM_D2_REPISAS_DER = ((299.5, 404.5), 1.42, (326.0, 470.0), 0.95, 12.0)
VISTAS = {
    "closet_D1_colgar": dict(
        cam=((303.5, 119.5), 1.45, (303.5, 40.0), 1.10, 15.0), mundo="dia", luces=("paso_d1",), expo=0.9,
        abrir=("Depto_Closet_D1_Norte_PuertaA",),
        texto="Clóset de colgar del dormitorio principal (D1_Norte) con la hoja A corrida: barra de lado a lado con "
              "soportes, perchas de madera, abrigo, vestidos, chaqueta, camisas, suéter y pantalones; maletero con "
              "caja y mantas; zapatos en el piso. Luz del paso encendida."),
    "closet_D1_interior": dict(
        cam=((315.4, 121.0), 1.32, (315.4, 40.0), 1.12, 12.0), mundo="dia", luces=("paso_d1",), expo=0.9,
        ocultar=("Depto_Closet_D1_Norte_PuertaA", "Depto_Closet_D1_Norte_PuertaB"),
        texto="Vista de revisión del mismo clóset con las dos hojas ocultas (las correderas sólo dejan ver la mitad "
              "a la vez): la barra completa de costado a costado con sus 11 prendas."),
    "closet_D1_repisas": dict(
        cam=((329.0, 64.0), 1.42, (304.0, 140.0), 0.95, 12.0), mundo="dia", luces=("paso_d1",), expo=0.9,
        abrir=("Depto_Closet_D1_Sur_PuertaA", "Depto_Closet_D1_Sur_Cajon2"),
        texto="Clóset de repisas del dormitorio principal (D1_Sur), hoja A corrida y cajón de arriba abierto "
              "(calcetines): columna de la hoja A con 2 cajones, suéteres y maleta."),
    "closet_D1_repisas_der": dict(
        cam=CAM_D1_REPISAS_DER, mundo="dia", luces=("paso_d1",), expo=0.9,
        abrir=("Depto_Closet_D1_Sur_PuertaB",),
        texto="Mismo clóset con la hoja B corrida: la otra columna, con zapatos en el piso y en la primera repisa, "
              "pilas de ropa doblada y la caja de zapatos arriba."),
    "closet_D2_colgar": dict(
        cam=((304.5, 448.0), 1.45, (304.5, 375.0), 1.10, 15.0), mundo="dia", luces=("paso_d2",), expo=0.9,
        abrir=("Depto_Closet_D2_Norte_PuertaA",),
        texto="Clóset de colgar del segundo dormitorio (D2_Norte), hoja A corrida: barra doble (camisas, "
              "poleras y chaquetas arriba; pantalones de largos distintos en perchas de pantalón abajo), perchas de "
              "alambre negro y zapatillas y botas en el piso."),
    "closet_D2_interior": dict(
        cam=((316.4, 449.5), 1.32, (316.4, 380.0), 1.10, 12.0), mundo="dia", luces=("paso_d2",), expo=0.9,
        ocultar=("Depto_Closet_D2_Norte_PuertaA", "Depto_Closet_D2_Norte_PuertaB"),
        texto="Vista de revisión del clóset de colgar del segundo dormitorio con las hojas ocultas: barra doble "
              "completa (11 prendas arriba y 7 pantalones abajo)."),
    "closet_D2_maletero": dict(
        cam=((316.4, 440.0), 1.90, (316.4, 385.0), 2.12, 14.0), mundo="dia", luces=("paso_d2",), expo=0.9,
        ocultar=("Depto_Closet_D2_Norte_PuertaA", "Depto_Closet_D2_Norte_PuertaB"),
        texto="Maletero del clóset de colgar del segundo dormitorio (cámara a 1,90 m, hojas ocultas): repisa a "
              "2,06 m con la caja de guardado y las mantas dobladas, y la barra alta con las perchas."),
    "closet_D2_repisas": dict(
        cam=((331.0, 404.5), 1.42, (305.0, 470.0), 0.95, 12.0), mundo="dia", luces=("paso_d2",), expo=0.9,
        abrir=("Depto_Closet_D2_Sur_PuertaA", "Depto_Closet_D2_Sur_Cajon3", "Depto_Closet_D2_Sur_Cajon1"),
        texto="Clóset de repisas del segundo dormitorio (D2_Sur), hoja A corrida y los cajones de arriba y de "
              "abajo abiertos (calcetines y poleras dobladas; el del medio cerrado para que se vean los dos)."),
    "closet_D2_repisas_der": dict(
        cam=CAM_D2_REPISAS_DER, mundo="dia", luces=("paso_d2",), expo=0.9,
        abrir=("Depto_Closet_D2_Sur_PuertaB",),
        texto="Mismo clóset con la hoja B corrida: la otra columna, con zapatillas, zapatos y botas en el piso y "
              "en la primera repisa, ropa doblada y la caja de zapatos arriba."),
    "nevera_abierta": dict(
        cam=((338.0, 240.0), 1.50, (400.0, 280.0), 0.95, 14.0), mundo="dia", luces=(), expo=1.0,
        abrir=("Depto_Mueble_Nevera_Puerta", "Depto_Mueble_Nevera_Freezer"),
        texto="Nevera abierta (puerta a 100° y cajón freezer): forro blanco, dos estantes de vidrio, cajón de "
              "verduras con frente de plástico esmerilado, alimentos (lácteos, huevos, fruta, frascos, cartones), "
              "balcones de la contrapuerta con botellas y salsas, congelados en el freezer y manillas de barra. De día "
              "con la luz de la cocina apagada y la luz interior de la nevera (la del modelo) encendida."),
    "interruptor_balcon": dict(
        cam=((153.0, 214.0), 1.40, (131.0, 174.0), 1.04, 22.0), mundo="dia", luces=(), expo=1.0,
        texto="Interruptor del balcón, por dentro, en el muro de ladrillo junto al ventanal: canto a 0,10 m de la "
              "arista del vano, centro a 1,10 m del piso, sobre caja de superficie con el conducto visto que baja de "
              "la derivación en T del interruptor del living."),
    "dia_living": dict(
        cam="Depto_Cam_Living", mundo="dia", luces=(), expo=1.5, cerrar_muebles=True,
        texto="Día normal en el living: cielo HDRI de día y sol de la fase 5, luces apagadas, luz rebotada horneada; "
              "el balcón se ve a través de los tres paños del ventanal."),
    "interruptor_hall": dict(
        cam=((372.0, 350.0), 1.40, (414.0, 308.0), 1.05, 24.0), mundo="noche", luces=TODOS, expo=0.9, ssr=False,
        texto="Interruptor simple del hall (focos del riel) junto a la jamba de la puerta de entrada, del lado de "
              "la manilla de palanca, a 1,10 m. De noche (el hall no tiene ventana), con todas las luces encendidas; "
              "el tercer foco del riel baña la puerta."),
    "interruptor_cocina": dict(
        cam=((321.0, 214.0), 1.40, (293.4, 173.5), 1.06, 22.0), mundo="noche", luces=TODOS, expo=0.8,
        abrir=("Depto_Mueble_Nevera_Puerta",),
        texto="Interruptor de la cocina en la cara este del remate del tabique T3, sobre el extremo de la "
              "cubierta, a 0,10 m del remate por donde se entra desde el living. Nevera abierta a 100°: su puerta "
              "queda a {dist_nevera} m de la placa (distancia entre sus cajas de mundo, calculada en el render), "
              "fuera de su barrido. De noche, con todas las luces encendidas."),
    "interruptor_dorm1_doble": dict(
        cam=((229.0, 131.0), 1.36, (250.0, 170.25), 1.02, 24.0), mundo="noche", luces=TODOS, expo=0.8,
        cerrar=("Depto_Puerta_D1_Hoja",),
        texto="Interruptor doble del dormitorio principal (techo y paso de los clósets) a 1,10 m, a 0,10 m del "
              "marco del lado de la manilla de palanca, con la puerta D1 cerrada; de noche, con todas las luces "
              "encendidas."),
    "noche_living": dict(
        cam="Depto_Cam_Living", mundo="noche", luces=TODOS, expo=0.9, cerrar_muebles=True,
        texto="Noche: living con el colgante de techo y la lámpara de arco sobre el asiento del sofá (2700 K); el "
              "ventanal refleja tenue el living (≈ 7 %, dos caras del vidrio) y deja ver el balcón con su colgante "
              "encendido. Sol apagado y cielo nocturno casi negro."),
    "noche_living_sin_balance": dict(
        cam="Depto_Cam_Living", mundo="noche", luces=TODOS, expo=0.9, cerrar_muebles=True, balance=None,
        texto="La misma vista de noche del living sin la adaptación cromática de la cámara: el color de 2700 K tal "
              "cual (para comparar)."),
    "noche_cocina": dict(
        cam="Depto_Cam_Cocina", mundo="noche", luces=TODOS, expo=0.6, cerrar_muebles=True,
        texto="Noche: cocina con sus dos colgantes de jaula a 3000 K, de cable corto (fondo de la jaula a ≈ 2,0 m); "
              "cajones cerrados."),
    "noche_dorm1": dict(
        cam="Depto_Cam_Dorm1", mundo="noche", luces=TODOS, expo=0.6, cerrar_muebles=True,
        texto="Noche: dormitorio principal con el colgante de techo y las dos lámparas de velador (2700 K)."),
    "noche_bano1": dict(
        cam=((400.0, 67.0), 1.62, (352.0, 131.0), 1.52, 14.0), mundo="noche", luces=TODOS, expo=0.6,
        cerrar_muebles=True, cerrar=("Depto_Puerta_B1_Hoja",),
        texto="Noche: baño principal desde el extremo de la tina hacia el vanitorio, el espejo y la puerta cerrada, "
              "con el colgante de jaula a 3000 K de cable corto en primer plano."),
    "noche_balcon": dict(
        cam=((87.5, 190.0), 1.50, (87.5, 285.0), 0.72, 18.0), mundo="noche", luces=TODOS, expo=0.8,
        cerrar_muebles=True,
        texto="Noche en el balcón desde su extremo norte, junto a la hoja abierta del ventanal: el colgante de domo "
              "(Ø 0,28 m, 30 W, 2700 K) a 0,80 m sobre la mesa bistró, de acero pintado, y la luz del living por el "
              "vidrio (todas las luces encendidas)."),
    "noche_paso_d1": dict(
        cam=((309.0, 121.5), 1.25, (309.0, 40.0), 1.95, 12.0), mundo="noche", luces=("paso_d1",), expo=0.6,
        abrir=("Depto_Closet_D1_Norte_PuertaA",), cerrar_muebles=True,
        texto="Noche, sólo la luz del paso del dormitorio principal (colgante de jaula de 25 W, 2700 K): el clóset de "
              "colgar con la hoja A corrida y la ampolleta en cuadro."),
    "noche_dorm2": dict(
        cam="Depto_Cam_Dorm2", mundo="noche", luces=("dorm2_aplique_izq", "dorm2_aplique_der"), expo=1.0,
        cerrar_muebles=True,
        texto="Noche, sólo los dos apliques de brazo del segundo dormitorio (2700 K): lectura sobre los veladores, "
              "sin fugas de luz por encima de las pantallas."),
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


def bombilla_grupo(grupo):
    """Copia del emisivo con el color de su grupo (2700 K o 3000 K), como hace el visor: sin esto todas las
    ampolletas emitían el mismo tono aunque su luz puntual fuera de otro."""
    nombre = f"_Bombilla_{grupo}"
    m = bpy.data.materials.get(nombre)
    if m is None:
        m = bpy.data.materials["Depto_Mat_Bombilla"].copy()
        m.name = nombre
        color = GRUPOS.get(grupo, {}).get("color")
        if color:
            m.node_tree.nodes.get("Principled BSDF").inputs["Emission"].default_value = (*color, 1.0)
    return m


GRUPOS = {}


def fijar_luces(encendidos, filtro=None):
    """Prende sólo los grupos `encendidos` (TODOS = todos). `filtro` (texto, opcional): de los grupos encendidos, sólo
    las luces cuya ampolleta contiene ese texto (par A/B de una misma vista: sólo el riel o sólo la luz lineal)."""
    bomb, off = bpy.data.materials["Depto_Mat_Bombilla"], apagada()
    propias = {bomb, off} | {m for m in bpy.data.materials if m.name.startswith("_Bombilla_")}
    for o in bpy.data.objects:
        if o.type == "LIGHT" and o.name.startswith("Depto_Luz_") and o.data.type in ("POINT", "SPOT"):
            o.hide_render = not ((encendidos == TODOS or o.get("grupo") in encendidos)
                                 and (not filtro or filtro in o.get("ampolleta", "")))
        if o.type == "MESH" and o.get("luz_w"):
            g = o.get("luz_grupo")
            on = (encendidos == TODOS or g in encendidos) and (not filtro or filtro in o.name)
            for slot in o.material_slots:          # por objeto: las ampolletas iguales comparten la malla
                if slot.material in propias:
                    slot.link = "OBJECT"
                    slot.material = bombilla_grupo(g) if on else off


def _mundo_hdri(nombre, ruta, fuerza, saturacion=1.0, fuerza_camara=None):
    """Mundo con un HDRI; `saturacion` y `fuerza` para la luz que da, y (opcional) otra fuerza, con el color
    original, para los rayos de cámara (Light Path «Is Camera Ray», que Eevee respeta en el mundo)."""
    w = bpy.data.worlds.get(nombre) or bpy.data.worlds.new(nombre)
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(ruta, check_existing=True)
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = saturacion
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = fuerza
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(env.outputs["Color"], hsv.inputs["Color"])
    # suelo neutro oscuro bajo el horizonte en la luz del mundo (y sus reflejos), como depto_05.mundo(): mezcla por la
    # componente Z de la dirección (Generated), antes de la fuerza del mundo (de día 0,12 × 1,6 ≈ 0,19 lineal)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rango = nt.nodes.new("ShaderNodeMapRange")
    rango.inputs["From Min"].default_value, rango.inputs["From Max"].default_value = -0.02, 0.05
    suelo = nt.nodes.new("ShaderNodeMixRGB")
    suelo.inputs["Color1"].default_value = (*SUELO_MUNDO, 1.0)
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], rango.inputs["Value"])
    nt.links.new(rango.outputs["Result"], suelo.inputs["Fac"])
    nt.links.new(hsv.outputs["Color"], suelo.inputs["Color2"])
    nt.links.new(suelo.outputs["Color"], bg.inputs["Color"])
    if fuerza_camara is None:
        nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
        return w
    bgc = nt.nodes.new("ShaderNodeBackground")
    bgc.inputs["Strength"].default_value = fuerza_camara
    nt.links.new(env.outputs["Color"], bgc.inputs["Color"])
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg.outputs["Background"], mix.inputs[1])
    nt.links.new(bgc.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return w


def mundo_noche(scene):
    return _mundo_hdri("_Noche", HDRI_NOCHE, 0.08)             # cielo nocturno casi apagado


def mundo_dia(scene):
    """Cielo de día de revisión (HDRI) en lugar del Nishita con suelo gris de la fase 5, que dejaba el exterior como
    niebla y los muros azulados."""
    return _mundo_hdri("_Dia", HDRI_DIA, DIA["fuerza"], DIA["saturacion"], DIA["fuerza_camara"])


HORNEADO = {"clave": None}
GI_INFLUENCIA = 0.10                     # m: menor que el muro perimetral más delgado (0,20 m, entrada; plano medido)


def cajas_recintos():
    """Cajas (x0, x1, y0, y1 px del plano) de las sondas de reflejo por recinto. Corrección 07b (ronda 2): antes sólo
    los baños tenían cubemap y el resto reflejaba el mundo (el cielo bajo el horizonte): vetas blancas en el roble,
    velo en la nevera y un barrido azul en la puerta de acero del hall. Eevee da prioridad a la sonda más chica donde
    se solapan (los clósets dentro de su paso, por ejemplo)."""
    X, Y = P.X, P.Y
    return {
        "Living": (X["W_I"], X["T3_W"], Y["D1_S"], Y["D2_N"]),
        "Cocina": (X["T3_E"], X["E_FORRO"], Y["T5_S"], Y["COC_N"]),
        "Hall": (X["T3_E"], X["E_FORRO"], Y["COC_S"], Y["T9_N"]),
        "Dorm1": (X["W_I"], X["T3_W"], Y["N_I"], Y["D1_N"]),
        "Dorm2": (X["W_I"], X["T3_W"], Y["D2_S"], Y["S_I"]),
        "Paso_D1": (X["T3_E"], X["T4_W"], Y["N_I"], Y["T5_N"]),
        "Paso_D2": (X["T3_E"], X["T10_W"], Y["T9_S"], Y["S_I"]),
        "B1": (X["T4_E"], X["E_FORRO"], Y["N_I"], Y["T5_N"]),
        "B2": (X["T10_E"], X["E_I"], Y["T9_S"], Y["S_I"]),
    }


def sondas(scene):
    """Sondas de revisión (no van al GLB): volumen de irradiancia sobre el depto para la luz rebotada, un cubemap por
    recinto para sus reflejos (cajas_recintos) y una sonda plana en cada espejo (Eevee 3.6: no necesita horneado;
    sin ella los espejos reflejaban el cielo del mundo)."""
    if bpy.data.objects.get("_GI_Depto"):
        return
    pd = bpy.data.lightprobes.new("_GI_Depto", "GRID")
    ob = bpy.data.objects.new("_GI_Depto", pd)
    scene.collection.objects.link(ob)
    # Corrección 08, ronda 2: la caja termina en la cara interior de los muros perimetrales (antes, 4,6 × 3,1 m de
    # semieje, contenía las caras exteriores de la fachada, en Y = 3,005, y de los muros norte y sur, en X = ±4,49, y les
    # horneaba la luz del interior: la franja del depto salía ≈ 40 % más oscura que el resto del edificio en
    # afuera_control, con el borde difuso de la caída). Con una distancia de influencia de 0,10 m, menor que el muro más
    # delgado (0,20 m, el de la entrada), ninguna cara exterior queda al alcance del volumen.
    (x0, y0), (x1, y1) = P.a_blender(0, P.Y["S_I"]), P.a_blender(0, P.Y["N_I"])
    (_, ya), (_, yb) = P.a_blender(P.X["E_I"], 0), P.a_blender(P.X["W_I"], 0)
    xa, xb = sorted((x0, x1))
    ya, yb = sorted((ya, yb))
    ob.location = ((xa + xb) / 2, (ya + yb) / 2, P.ALTURA_PISO_CIELO / 2)
    ob.scale = ((xb - xa) / 2, (yb - ya) / 2, P.ALTURA_PISO_CIELO / 2 - 0.02)
    pd.influence_distance = GI_INFLUENCIA
    pd.grid_resolution_x, pd.grid_resolution_y, pd.grid_resolution_z = 18, 12, 6
    m = 0.10 / P.M_POR_PX                                # 0,10 m más allá de cada muro: la caja los contiene
    for rid, (x0, x1, y0, y1) in cajas_recintos().items():
        a, b = P.a_blender(x0 - m, y0 - m), P.a_blender(x1 + m, y1 + m)
        cd = bpy.data.lightprobes.new(f"_Cubo_{rid}", "CUBE")
        cd.influence_type = "BOX"
        # la caja de influencia es la del objeto (escala) por esta distancia: con 0,05 (el valor de la ronda 1) cubría
        # el 5 % del recinto y el resto seguía reflejando el mundo (lo encontré por la puerta del hall, negra)
        cd.influence_distance = 1.0
        cd.falloff = 0.15
        oc = bpy.data.objects.new(f"_Cubo_{rid}", cd)
        scene.collection.objects.link(oc)
        oc.location = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, P.ALTURA_PISO_CIELO / 2)
        oc.scale = (abs(a[0] - b[0]) / 2, abs(a[1] - b[1]) / 2, P.ALTURA_PISO_CIELO / 2 + 0.10)
    espejo = bpy.data.materials.get("Depto_Mat_Espejo")
    for o in [o for o in bpy.data.objects if o.type == "MESH" and espejo in o.data.materials[:]]:
        idx = [i for i, m in enumerate(o.data.materials) if m == espejo]
        caras = [f for f in o.data.polygons if f.material_index in idx]
        if not caras:
            continue
        mw = o.matrix_world
        # la cara del frente (−Y local en los dos modelos de espejo). Corrección 07b (ronda 2): con max(área) sobre
        # todas las caras, la elección entre el frente y el respaldo del vidrio (misma área) quedaba al azar del
        # redondeo, y la sonda sólo funciona con su Z hacia el muro, del lado contrario al que refleja (probado en
        # noche_bano1: con Z hacia el cuarto el espejo reflejaba el cielo del mundo; con Z hacia el muro, la puerta y
        # los azulejos). El espejo de pie tenía la orientación mala y el del baño la buena.
        frente = [f for f in caras if f.normal.y < -0.5] or caras
        grande = max(frente, key=lambda f: f.area)
        n = (mw.to_3x3() @ grande.normal).normalized()          # normal del frente (hacia el cuarto)
        pts = [mw @ o.data.vertices[v].co for f in caras for v in f.vertices]
        c = sum(pts, Vector()) / len(pts)
        rot = (-n).to_track_quat("Z", "Y")                       # Z de la sonda hacia el muro
        ux, uy = rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0))
        hx = max(abs((p - c).dot(ux)) for p in pts) + 0.02
        hy = max(abs((p - c).dot(uy)) for p in pts) + 0.02
        ppd = bpy.data.lightprobes.new(f"_Plana_{o.name}", "PLANAR")
        ppd.influence_distance = 0.10
        ppd.falloff = 0.5
        op = bpy.data.objects.new(f"_Plana_{o.name}", ppd)
        scene.collection.objects.link(op)
        op.location = c + n * 0.001
        op.rotation_euler = rot.to_euler()
        op.scale = (hx, hy, 1.0)
        print("SONDA_PLANA", o.name, round(hx * 2, 3), round(hy * 2, 3), "frente", tuple(round(x, 3) for x in n))


def hornear(scene, clave):
    """Luz rebotada de Eevee (volumen y cubemaps) horneada con el mundo y las luces de la vista (también de día:
    corrección 07b, ronda 2; antes se horneaba sólo el sol y el cielo y las sombras de una lámpara encendida quedaban
    grises o negras junto a superficies naranjas). Se rehace sólo si cambian (las vistas con el mismo horneado van
    seguidas en VISTAS). Cada horneado tarda 4-6 min en esta CPU (medido; casi no depende de la resolución de los
    cubemaps: 365 s a 256 px y 334 s a 128), así que las vistas comparten horneado todo lo posible."""
    if HORNEADO["clave"] == clave:
        return
    sondas(scene)
    scene.eevee.gi_diffuse_bounces = 2
    scene.eevee.gi_cubemap_resolution = "256"
    scene.eevee.gi_visibility_resolution = "32"
    # el horneado usa la visibilidad de viewport: se iguala a la de render (fijar_luces y led_nevera sólo tocan esa)
    luces = [o for o in bpy.data.objects if o.type == "LIGHT"]
    previo = {o.name: o.hide_viewport for o in luces}
    for o in luces:
        o.hide_viewport = o.hide_render
    bpy.ops.scene.light_cache_bake()
    for o in luces:
        o.hide_viewport = previo[o.name]
    HORNEADO["clave"] = clave
    print("HORNEADO", clave, time.strftime("%H:%M:%S"))


def vidrio_revision():
    """Vidrio de revisión (sólo en este render; el GLB y el visor no cambian). Corrección 07b (ronda 2): el vidrio del
    GLB (alfa 0,18, Transmission 1, BLEND, caras traseras visibles y sin backface culling) sumaba en Eevee la sonda del
    mundo una vez por cara: de día el ventanal se veía lechoso y tapaba el balcón, de noche un velo azul, y los
    estantes de la nevera placas grises. Aquí: Transparent BSDF casi blanco mezclado con un Glossy nítido por el doble
    del Fresnel de IOR 1,45 (las dos caras del paño; ≈ 7 % de frente), sin caras traseras ni sombra."""
    for nombre in VIDRIOS_REVISION:
        m = bpy.data.materials.get(nombre)
        if m is None:
            continue
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        mix = nt.nodes.new("ShaderNodeMixShader")
        fr = nt.nodes.new("ShaderNodeFresnel")
        fr.inputs["IOR"].default_value = 1.45
        dos = nt.nodes.new("ShaderNodeMath")          # dos caras del paño (sólo se dibuja la de adelante)
        dos.operation, dos.use_clamp = "MULTIPLY", True
        dos.inputs[1].default_value = 2.0
        nt.links.new(fr.outputs["Fac"], dos.inputs[0])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        tr.inputs["Color"].default_value = (0.97, 0.98, 0.98, 1.0)
        gl = nt.nodes.new("ShaderNodeBsdfGlossy")
        gl.inputs["Roughness"].default_value = 0.02
        nt.links.new(dos.outputs["Value"], mix.inputs["Fac"])
        nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
        nt.links.new(gl.outputs["BSDF"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
        m.blend_method = "BLEND"
        m.show_transparent_back = False
        m.use_backface_culling = True
        m.shadow_method = "NONE"


def compositor(scene):
    """Render Layers -> Color Balance (ASC-CDL) -> Composite; devuelve el nodo de balance (pendiente por vista)."""
    scene.use_nodes = True
    nt = scene.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    cb = nt.nodes.new("CompositorNodeColorBalance")
    cb.correction_method = "OFFSET_POWER_SLOPE"
    co = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], cb.inputs["Image"])
    nt.links.new(cb.outputs["Image"], co.inputs["Image"])
    return cb


def dist_cajas(a, b):
    """Distancia entre dos objetos (cajas de mundo alineadas a los ejes, con sus hijos), m."""
    def caja(o):
        pts = [q.matrix_world @ Vector(c) for q in [o, *o.children] if q.type == "MESH" for c in q.bound_box]
        return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]
    (a0, a1), (b0, b1) = caja(a), caja(b)
    return math.sqrt(sum(max(0.0, b0[k] - a1[k], a0[k] - b1[k]) ** 2 for k in range(3)))


def _dist_nevera():
    d = dist_cajas(bpy.data.objects["Depto_Mueble_Nevera_Puerta"], bpy.data.objects["Depto_Interruptor_Cocina"])
    return f"{d:.2f}".replace(".", ",")


# marcas del texto de una vista que se completan con una medida del render, con las piezas ya en su estado (07c: las
# usa también tools/render_07c.py)
MARCAS = {"{dist_nevera}": _dist_nevera}


def grupos_de_moviles(estado, moviles):
    """Grupos de luz que prenden los móviles abiertos del render (`enciende`, contrato 2.2: la luz de la nevera)."""
    return {g for n, ab in estado.items() if ab for g in str(moviles[n].get("enciende", "")).split(",") if g}


def config(scene, a):
    scene.render.engine = "BLENDER_EEVEE"
    ee = scene.eevee
    ee.taa_render_samples = a.samples
    ee.use_gtao = True
    ee.gtao_distance = 0.2                 # 0,5 dejaba un halo oscuro con anillos alrededor de los florones
    ee.use_ssr = True
    # corrección 07b (ronda 2): reflejos en pantalla sólo en lo bastante brillante, a resolución completa y con un
    # espesor de objeto más realista; lo más rugoso refleja la sonda de su recinto. 0,45 deja fuera el roble y la
    # melamina (0,55) y deja dentro, entera, la cubierta de concreto (mapa de 0,18 a 0,38, medido): con 0,25 el umbral
    # la partía en manchas de reflejo nítido y difuso
    # corrección 07c (ronda 2): 1,0. Con 0,45 el umbral partía también el microcemento (mapa de 0,25 a 0,91, el 20,6 %
    # de los texeles bajo 0,45): manchas blancas de borde duro en el piso de la cocina y del hall, con reflejo nítido de
    # la ventana en unas y el de la sonda en otras. La cubierta (0,18-0,39) sigue dentro entera
    ee.ssr_max_roughness = 1.0
    ee.use_ssr_halfres = False
    ee.ssr_thickness = 0.1
    ee.use_soft_shadows = True
    ee.use_bloom = True
    ee.bloom_intensity = 0.03
    ee.shadow_cube_size = "1024"           # como la fase 5 (con 512 salían anillos en el cielo)
    ee.shadow_cascade_size = "2048"
    ee.use_shadow_high_bitdepth = True
    scene.view_settings.view_transform = "Filmic"
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
    vidrio_revision()
    balance = compositor(scene)
    GRUPOS.update({g["id"]: g for g in json.loads(scene.get("depto_grupos_luz", "[]"))})
    sol = bpy.data.objects.get("Depto_Luz_Sol")
    dia, noche = mundo_dia(scene), mundo_noche(scene)
    moviles = {o.name: o for o in bpy.data.objects if "puerta" in o or "recorrido_m" in o}
    inicial = {n: bool(o.get("abierta")) for n, o in moviles.items()}
    solo = [s_.strip() for s_ in a.solo.split(",") if s_.strip()]
    hechos = []
    ruta_json = os.path.join(a.out, "renders.json")
    previos = []
    if solo and os.path.exists(ruta_json):
        with open(ruta_json) as fh:
            previos = [r for r in json.load(fh) if r["vista"] not in solo and r["vista"] in VISTAS]
    def clave_luz(v):
        # la luz de la nevera (grupo de la puerta) no cambia la clave: sólo alumbra su interior (luz directa)
        return (v["mundo"], "todas" if v["luces"] == TODOS else ",".join(v["luces"]), v.get("filtro_luz", ""))
    for vista, v in VISTAS.items():
        if solo and vista not in solo:
            continue
        estado = dict(inicial)
        if v.get("cerrar_muebles"):
            estado.update({n: False for n, o in moviles.items() if o.get("clase") in MUEBLES})
        estado.update({n: True for n in v.get("abrir", ())})
        estado.update({n: False for n in v.get("cerrar", ())})
        for n, o in moviles.items():
            estado_movil(o, estado[n])
        luces_v = v["luces"] if v["luces"] == TODOS else tuple(v["luces"]) + tuple(grupos_de_moviles(estado, moviles))
        fijar_luces(luces_v, v.get("filtro_luz"))
        scene.world = noche if v["mundo"] == "noche" else dia
        if sol:
            sol.hide_render = v["mundo"] == "noche"
        bpy.context.view_layer.update()
        scene.eevee.use_ssr = v.get("ssr", True)
        if not a.sin_gi:
            hornear(scene, clave_luz(v))
        con_lamparas = bool(v["luces"])        # grupos de 2700-3000 K (la luz de la nevera es de 5000 K: no cuenta)
        pend = v.get("balance", BALANCE["lamparas"] if con_lamparas else BALANCE["dia"])
        balance.slope = pend or (1.0, 1.0, 1.0)
        texto = v["texto"]
        for marca, fn in MARCAS.items():
            if marca in texto:
                texto = texto.replace(marca, fn())
        if pend:
            txt_pend = ", ".join(f"{x:.2f}" for x in pend)
            texto += f" Con adaptación cromática de la cámara (pendiente {txt_pend}; el visor no la aplica)."
        scene.view_settings.exposure = v.get("expo", 0.0)
        scene.view_settings.look = v.get("look", "Medium Contrast" if v["mundo"] == "noche" else "None")
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
        hechos.append({"vista": vista, "archivo": os.path.basename(ruta), "que_muestra": texto,
                       "balance_blancos": list(pend) if pend else None,
                       "mundo": v["mundo"], "luces": "todas" if v["luces"] == TODOS else list(luces_v),
                       "filtro_luz": v.get("filtro_luz"),
                       "abiertos": sorted(n for n, e in estado.items() if e),      # todo lo abierto en el render
                       "ocultos": [o.name for o in ocultar], "camara": cam.name,
                       "lente_mm": round(cam.data.lens, 1), "motor": "EEVEE", "muestras": a.samples,
                       "look": scene.view_settings.look, "exposicion": scene.view_settings.exposure,
                       "resolucion": [scene.render.resolution_x, scene.render.resolution_y]})
        print("RENDER", ruta)
    orden = list(VISTAS)
    todos = sorted(previos + hechos, key=lambda r: orden.index(r["vista"]))
    with open(ruta_json, "w") as fh:
        json.dump(todos, fh, ensure_ascii=False, indent=2)
    print("RENDERS_07B_DONE", len(hechos))


if __name__ == "__main__":
    main()
