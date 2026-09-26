"""Fase 2 (blockout) del activo Depto: muros, tabiques, shafts, losas, balcón y cámaras de revisión.

Uso (o todo el pipeline con build/depto_run.sh):
    blender -b build/depto.blend --python-exit-code 1 --python build/depto_02_blockout.py

Idempotente: carga el maestro de la fase 1, borra lo que crea esta fase (colecciones Depto_Muros,
Depto_Losas, Depto_Cielo, Depto_Balcon, Depto_Colision y las cámaras de ambiente) y lo reconstruye desde
build/depto_plano.py. Exige el sello vigente de la fase 1 (cadena de build/depto_sellos.py) y que el
archivo abierto sea el maestro; si no, aborta sin guardar. Guarda build/depto.blend, lo sella con
scene["depto_fase02"] (y borra los sellos de fases posteriores) e imprime FASE_OK.

Acabados (versión 2, decoración industrial: docs/deco-industrial.md): cada cara de muro, shaft, antepecho y losa
recibe el material de acabado del recinto hacia el que mira: azulejo en los baños (Depto_Mat_MuroBano), ladrillo
en la pared del televisor (ZONAS_ACENTO), pintura exterior hacia afuera y pintura en el resto; en el piso, baldosa
hexagonal en los baños, tablas de roble en dormitorios y pasos, y microcemento en el resto (ver ZONAS_*). Los materiales quedan en su
versión base de color plano (build/depto_geom.MATERIALES); la fase 5 les agrega las texturas en el mismo
datablock, sin tocar estas mallas.

Colisión: con la baranda de vidrio (compuerta 2) la masa de la baranda no se ve; queda como volumen de
colisión Depto_Col_Baranda en la colección Depto_Colision (oculta en render, alambre en el viewport,
["colision"] = True). Convención para el tour: Depto_Col_* / Depto_Colision no se exportan como visibles.

Método: cada muro es un rectángulo del plano (px, centros de línea) extruido de 0 a la altura de
piso a cielo. Los vanos se resuelven partiendo el muro en tramos a lo largo de su eje largo
(macizo | antepecho + dintel | macizo), sin booleanos: geometría limpia y exacta.
"""
import os
import sys

import bmesh
import bpy
from mathutils import Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_geom as G  # noqa: E402
import depto_plano as P  # noqa: E402
import depto_sellos as SE  # noqa: E402

X, Y, S = P.X, P.Y, P.M_POR_PX

# ---------------------------------------------------------------------------
# Constantes de la fase (m). Las alturas vienen del brief (todas inferidas).
# ---------------------------------------------------------------------------
H = P.ALTURA_PISO_CIELO          # 2,40 · compuerta Fase 0
DP = P.DINTEL_PUERTAS            # 2,05 · hoja de 2,00 + marco
DV = P.DINTEL_VENTANAS           # 2,10
AD = P.ANTEPECHO_DORMITORIOS     # 0,95
AB = P.ANTEPECHO_BANO            # 1,50
LOSA = P.ESPESOR_LOSA            # 0,15 · brief: losas de piso y cielo (supuesto, sólo cierra el volumen)
Z_BALCON = -P.DESNIVEL_BALCON    # piso del balcón 3 cm bajo el interior (supuesto)
BARANDA_ALTO = P.ALTURA_BARANDA_BALCON   # 1,00 sobre el piso del balcón
BARANDA_ESPESOR = 0.05           # ≈ 3 px entre las dos líneas finas del plano (medido)
BARANDA_TIPO = "vidrio"          # compuerta 2: vidrio con pasamanos (lo modela la fase 3); "masa" = sólido visible
OJO = 1.60                       # altura de las cámaras de ambiente (convención de tour)
GRIS_ANTEPECHO_PLANTA = 0.30     # color de objeto (lineal) de los antepechos: ≈149/255 en la planta, con
                                 # margen frente a los umbrales de tools/compare_plan.py (negro < 60 ≤ gris < 200)
LENTE_MM = 16                    # gran angular típico de fotografía inmobiliaria (sensor 36 mm)

OUT_BLEND = os.path.join(RAIZ, "build", "depto.blend")
COLS_FASE = ("Depto_Muros", "Depto_Losas", "Depto_Cielo", "Depto_Balcon", "Depto_Colision")

# Zonas de acabado (px del plano, rectángulos). Versión 2 (diseño): microcemento continuo en living, cocina, hall y
# nicho LV; tablas de roble en dormitorios y pasos; baldosa hexagonal en los baños. Los rectángulos de piso
# incluyen el espesor del muro bajo cada puerta, para que el cambio de piso quede bajo la hoja.
ZONAS_BANO = [(X["T4_E"], X["E_FORRO"], Y["N_I"], Y["T5_N"]), (X["T10_E"], X["E_I"], Y["T9_S"], Y["S_I"])]
ZONAS_PISO_CERAMICO = [(X["T4_W"], X["E_FORRO"], Y["N_I"], Y["T5_N"]), (X["T10_W"], X["E_I"], Y["T9_S"], Y["S_I"])]
ZONAS_PISO_MADERA = [(X["W_I"], X["T3_W"], Y["N_I"], Y["D1_S"]),        # dormitorio 1 hasta la cara del living
                     (X["W_I"], X["T3_W"], Y["D2_N"], Y["S_I"]),        # dormitorio 2
                     (X["T3_W"], X["T4_W"], Y["CL1_N"], Y["CL1_S"]),    # paso D1 (con el vano de T3)
                     (X["T3_W"], X["T10_W"], Y["CL2_N"], Y["CL2_S"])]   # paso D2
# Pared de acento: franja de 3 px delante de la cara de ladrillo (la prueba de acabado mira 3 cm delante de cada cara).
ZONAS_ACENTO = [((X["W_I"], X["JAMBA_D"], Y["D1_S"], Y["D1_S"] + 3), "Depto_Mat_Ladrillo")]   # muro del televisor

# ---------------------------------------------------------------------------
# Muros: (nombre, x0, x1, y0, y1 en px del plano, vanos, tipo ext|tab|shaft: informativo; el acabado va por cara)
# vano = (desde, hasta [px a lo largo del eje largo], antepecho m, dintel m, id del brief)
# ---------------------------------------------------------------------------
MUROS = [
    # Perímetro (espesores medidos: fachada 0,25 · norte 0,24 · sur y este 0,20 · forro este 0,04)
    ("Depto_Muro_Fachada", X["W_O"], X["W_I"], Y["N_O"], Y["S_O"], [
        (Y["V_D1_A"], Y["V_D1_B"], AD, DV, "V_D1"),      # ventana Dorm 1, 1,82
        (Y["VEN_A"], Y["VEN_B"], 0.0, DV, "VEN_LIV"),     # ventanal corredera al balcón, 2,94
        (Y["V_D2_A"], Y["V_D2_B"], AD, DV, "V_D2"),      # ventana Dorm 2, 2,09
    ], "ext"),
    ("Depto_Muro_Norte", X["W_I"], X["E_O"], Y["N_O"], Y["N_I"], [
        (X["V_B1_A"], X["V_B1_B"], AB, DV, "V_B1"),      # ventana Baño 1, 0,60, sobre la tina
    ], "ext"),
    ("Depto_Muro_Sur", X["W_I"], X["E_O"], Y["S_I"], Y["S_O"], [], "ext"),
    ("Depto_Muro_Este", X["E_I"], X["E_O"], Y["N_I"], Y["S_I"], [
        (Y["ENT_N"], Y["ENT_S"], 0.0, DP, "P_ENT"),      # puerta de entrada, luz 1,07 (dibujada)
    ], "ext"),
    ("Depto_Muro_Este_Forro", X["E_FORRO"], X["E_I"], Y["N_I"], Y["ENT_N"], [], "ext"),  # capa interior Baño 1 + cocina
    # Tabiques (0,072 entre centros de línea)
    ("Depto_Tabique_D1_Living", X["W_I"], X["T3_W"], Y["D1_N"], Y["D1_S"], [
        (X["JAMBA_D"], X["T3_W"], 0.0, DP, "P_D1"),      # puerta Dorm 1, luz 0,76
    ], "tab"),
    ("Depto_Tabique_Living_D2", X["W_I"], X["T3_W"], Y["D2_N"], Y["D2_S"], [
        (X["JAMBA_D"], X["T3_W"], 0.0, DP, "P_D2"),      # puerta Dorm 2, luz 0,76
    ], "tab"),
    # T3: lado oeste de los closets. El vano libre al paso lleva dintel a altura de puerta (inferido).
    ("Depto_Tabique_T3_Norte", X["T3_W"], X["T3_E"], Y["N_I"], Y["T3_C"], [
        (Y["CL1_N"], Y["CL1_S"], 0.0, DP, "VL_D1"),      # paso Dorm 1, 1,23
    ], "tab"),
    ("Depto_Tabique_T3_Sur", X["T3_W"], X["T3_E"], Y["T3_D"], Y["S_I"], [
        (Y["CL2_N"], Y["CL2_S"], 0.0, DP, "VL_D2"),      # paso Dorm 2, 1,00
    ], "tab"),
    ("Depto_Tabique_T4", X["T4_W"], X["T4_E"], Y["N_I"], Y["T5_N"], [
        (Y["T4_A"], Y["T4_B"], 0.0, DP, "P_B1"),         # puerta Baño 1, luz 0,70
    ], "tab"),
    ("Depto_Tabique_T10", X["T10_W"], X["T10_E"], Y["T9_S"], Y["S_I"], [
        (Y["T10_A"], Y["T10_B"], 0.0, DP, "P_B2"),       # puerta Baño 2, luz 0,70
    ], "tab"),
    ("Depto_Tabique_T5", X["T3_E"], X["E_FORRO"], Y["T5_N"], Y["T5_S"], [], "tab"),     # Baño 1 / cocina
    ("Depto_Tabique_T9", X["T3_E"], X["E_I"], Y["T9_N"], Y["T9_S"], [], "tab"),         # hall / Baño 2
    ("Depto_Tabique_LV", X["LV_W"], X["LV_E"], Y["LV_F"], Y["T9_N"], [], "tab"),        # lado este del nicho LV
    ("Depto_Tabique_CocinaHall", X["COC_W"], X["E_FORRO"], Y["COC_N"], Y["COC_S"], [], "tab"),  # 0,12, retorno de jamba
    # Shafts: macizos (no son recorribles)
    ("Depto_Shaft_1", X["SH1_W"], X["E_FORRO"], Y["SH1_N"], Y["T5_N"], [], "shaft"),
    ("Depto_Shaft_2", X["SH2_W"], X["E_I"], Y["SH2_N"], Y["S_I"], [], "shaft"),
]

# Cámaras de ambiente: (sufijo, posición px, objetivo px[, (z cámara, z objetivo)]). Por defecto a la altura
# OJO y mirada horizontal. Cada una dentro de su ambiente, fuera del barrido de las hojas de puerta; la fase 3
# prueba que queden a ≥ 0,20 m (3D) de todo sólido. Los baños miran hacia abajo: con 16 mm y cámara
# horizontal a 1,60, a 0,4 m sólo se ve lo que está sobre 1,3 m y quedaban fuera WC y tina (crítico fase 3).
CAMARAS = [
    ("Living", (284, 300), (127, 228)),     # desde el borde cocina/hall hacia el ventanal
    ("Living_Sofa", (140, 200), (240, 300), (OJO, 1.00)),     # desde junto al ventanal hacia sofá, mesa y alfombra
    ("Cocina", (330, 285), (410, 165)),     # dentro de la cocina, hacia la L
    ("Hall", (405, 346), (190, 250)),       # desde la puerta de entrada (0,29 m de la hoja cerrada) hacia el living
    ("Hall_Recibidor", (402, 322), (336, 350), (OJO, 1.10)),  # hacia la banca, el perchero y el cuadro del hall
    ("Dorm1", (262, 158), (130, 55)),       # desde junto a la puerta hacia la ventana y la cama
    ("Dorm2", (262, 342), (130, 450)),
    ("Paso_D1", (272, 95), (345, 88)),      # desde el Dorm 1 hacia el paso entre closets y la puerta del Baño 1
    ("Paso_D2", (272, 425), (345, 428)),
    ("Bano1", (360, 112), (395, 50), (OJO, 0.60)),            # hacia tina, WC y ventana (pasa al este de la hoja)
    ("Bano1_Vanitorio", (392, 100), (352, 140), (OJO, 1.00)),  # desde junto al WC hacia vanitorio y espejo
    ("Bano2", (362, 445), (400, 395), (OJO, 0.60)),            # hacia tina y WC (pasa al este de la hoja)
    ("Bano2_Vanitorio", (368, 432), (355, 470), (OJO, 1.00)),  # hacia vanitorio y espejo
    ("Balcon", (84, 190), (92, 300), (OJO, 0.55)),   # extremo norte, junto a la hoja abierta, hacia la mesa bistró
                                                     # del extremo sur (v2; antes miraba desde el sur al ventanal)
]
MAQUETA = ((-60, 520), (262, 250), 7.5, 26)  # posición px, objetivo px, altura m, lente mm (vista sin cielo)


# ---------------------------------------------------------------------------
rect_bl = G.rect_bl


def tramos_muro(x0, x1, y0, y1, vanos, z0=0.0, z1=H):
    """Cajas (x0, x1, y0, y1, z0, z1) en px/m que forman el muro con sus vanos: (macizos y dinteles, antepechos)."""
    eje_x = (x1 - x0) >= (y1 - y0)
    ini, fin = (x0, x1) if eje_x else (y0, y1)

    def caja(a, b, za, zb):
        return (a, b, y0, y1, za, zb) if eje_x else (x0, x1, a, b, za, zb)

    cajas, antepechos, cursor = [], [], ini
    for a, b, ante, dintel, _ in sorted(vanos):
        assert ini <= a < b <= fin, f"vano fuera del muro: {a}-{b} en {ini}-{fin}"
        if a - cursor > 1e-6:
            cajas.append(caja(cursor, a, z0, z1))
        if ante > 1e-6:
            antepechos.append(caja(a, b, z0, ante))
        if z1 - dintel > 1e-6:
            cajas.append(caja(a, b, dintel, z1))
        cursor = b
    if fin - cursor > 1e-6:
        cajas.append(caja(cursor, fin, z0, z1))
    return cajas, antepechos


def en_zonas(zonas, x, y):
    return any(x0 < x < x1 and y0 < y < y1 for x0, x1, y0, y1 in zonas)


def fuera(x, y):
    return not (X["W_O"] < x < X["E_O"] and Y["N_O"] < y < Y["S_O"])


def acabado_muro(centro, normal):
    """Material de una cara de muro según el recinto al que mira (3 cm delante de la cara)."""
    if abs(normal.z) > 0.5:
        return "Depto_Mat_MuroPintado"            # cantos superior e inferior: no se ven
    x, y = P.a_plano(centro.x + normal.x * 0.03, centro.y + normal.y * 0.03)
    if fuera(x, y):
        return "Depto_Mat_MuroExterior"
    for zona, mat in ZONAS_ACENTO:
        if en_zonas([zona], x, y):
            return mat
    return "Depto_Mat_MuroBano" if en_zonas(ZONAS_BANO, x, y) else "Depto_Mat_MuroPintado"


def acabado_piso(centro, normal):
    x, y = P.a_plano(centro.x, centro.y)
    if en_zonas(ZONAS_PISO_CERAMICO, x, y):
        return "Depto_Mat_PisoCeramico"
    return "Depto_Mat_PisoMadera" if en_zonas(ZONAS_PISO_MADERA, x, y) else "Depto_Mat_Microcemento"


def particion(x0, x1, y0, y1, zonas):
    """Rectángulo del plano partido en celdas por los bordes de las zonas (para asignar acabado por celda)."""
    xs = sorted({x0, x1} | {v for z in zonas for v in z[:2] if x0 < v < x1})
    ys = sorted({y0, y1} | {v for z in zonas for v in z[2:] if y0 < v < y1})
    return [(xs[i], xs[i + 1], ys[j], ys[j + 1]) for i in range(len(xs) - 1) for j in range(len(ys) - 1)]


def objeto(nombre, cajas, col, acabado, color_planta):
    """acabado: nombre de material o función (centro, normal) -> material, por cara."""
    bm = bmesh.new()
    for c in cajas:
        G.caja(bm, *c)
    if callable(acabado):
        me = G.malla_desde_bmesh(nombre, bm, None, acabado=acabado)   # con UV de mundo en metros (fase 5)
    else:
        me = G.malla_desde_bmesh(nombre, bm, G.material(acabado))
    ob = bpy.data.objects.new(nombre, me)
    ob.color = color_planta          # color de objeto: sólo para la comparación de planta (tools/compare_plan.py)
    col.objects.link(ob)
    return ob


def limpiar(root):
    cams = [o for o in bpy.data.objects
            if o.type == "CAMERA" and o.name.startswith("Depto_Cam_") and o.name != "Depto_Cam_Planta"]
    datos = [o.data for o in cams]
    for o in cams:
        bpy.data.objects.remove(o, do_unlink=True)
    for d in datos:
        if d.users == 0:
            bpy.data.cameras.remove(d)
    return G.colecciones_fase(root, COLS_FASE)


def camara(nombre, pos, obj, z, lente, col, ocultar=""):
    cd = bpy.data.cameras.new(nombre)
    cd.lens = lente
    cd.sensor_width = 36
    cd.clip_start = 0.05
    cd.clip_end = 60
    cam = bpy.data.objects.new(nombre, cd)
    p = Vector((*P.a_blender(*pos), z[0]))
    t = Vector((*P.a_blender(*obj), z[1]))
    cam.location = p
    cam.rotation_euler = (t - p).to_track_quat("-Z", "Y").to_euler()
    if ocultar:
        cam["ocultar"] = ocultar
    col.objects.link(cam)
    return cam


def dentro(cajas_mundo, pt):
    return any(c[0] - 1e-9 <= pt[0] <= c[1] + 1e-9 and c[2] - 1e-9 <= pt[1] <= c[3] + 1e-9 and
               c[4] - 1e-9 <= pt[2] <= c[5] + 1e-9 for c in cajas_mundo)


def main():
    scene = bpy.context.scene
    SE.exigir(scene, "01", bpy.data.filepath)
    root = bpy.data.collections["Depto"]
    cols = limpiar(root)
    negro, blanco = (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0, 1.0)

    todas = []   # (nombre, caja px/m) para las pruebas
    gris = (GRIS_ANTEPECHO_PLANTA,) * 3 + (1.0,)  # antepechos: en la planta cortada a 1,20 m se ven como ventana
    for nombre, x0, x1, y0, y1, vanos, clave in MUROS:
        cajas, antepechos = tramos_muro(x0, x1, y0, y1, vanos)
        objeto(nombre, cajas, cols["Depto_Muros"], acabado_muro, negro)
        if antepechos:
            objeto(f"{nombre}_Antepechos", antepechos, cols["Depto_Muros"], acabado_muro, gris)
        todas += [(nombre, c) for c in cajas + antepechos]

    # Losas (supuesto: 0,15 m) y balcón
    celdas = particion(X["W_O"], X["E_O"], Y["N_O"], Y["S_O"], ZONAS_PISO_CERAMICO + ZONAS_PISO_MADERA)
    objeto("Depto_Losa_Piso", [(*c, -LOSA, 0.0) for c in celdas], cols["Depto_Losas"], acabado_piso, blanco)
    objeto("Depto_Cielo_Losa", [(X["W_O"], X["E_O"], Y["N_O"], Y["S_O"], H, H + LOSA)], cols["Depto_Cielo"],
           "Depto_Mat_Cielo", blanco)
    # El balcón queda bajo la losa del balcón superior (inferido: edificio en altura con balcones apilados).
    objeto("Depto_Cielo_Balcon", [(X["BAL_O"], X["W_O"], Y["BAL_N"], Y["BAL_S"], H, H + LOSA)], cols["Depto_Cielo"],
           "Depto_Mat_Cielo", blanco)
    objeto("Depto_Balcon_Losa", [(X["BAL_O"], X["W_O"], Y["BAL_N"], Y["BAL_S"], Z_BALCON - LOSA, Z_BALCON)],
           cols["Depto_Balcon"], "Depto_Mat_PisoBalcon", blanco)
    e = BARANDA_ESPESOR / S / 2   # medio espesor en px
    zb = (Z_BALCON, Z_BALCON + BARANDA_ALTO)
    # Tramos que se encuentran en las esquinas sin sobresalir (el oeste entre los ejes N y S; N y S desde
    # la cara del oeste hasta la fachada).
    tramos_baranda = [
        (X["BARANDA_O"] - e, X["BARANDA_O"] + e, Y["BARANDA_N"] - e, Y["BARANDA_S"] + e, *zb),
        (X["BARANDA_O"] + e, X["W_O"], Y["BARANDA_N"] - e, Y["BARANDA_N"] + e, *zb),
        (X["BARANDA_O"] + e, X["W_O"], Y["BARANDA_S"] - e, Y["BARANDA_S"] + e, *zb),
    ]
    if BARANDA_TIPO == "masa":
        objeto("Depto_Balcon_Baranda", tramos_baranda, cols["Depto_Balcon"], "Depto_Mat_MuroExterior", negro)
    else:   # vidrio: la masa sólo es colisión (la baranda visible es de la fase 3)
        col_ob = objeto("Depto_Col_Baranda", tramos_baranda, cols["Depto_Colision"], "Depto_Mat_Colision", blanco)
        col_ob["colision"] = True
        col_ob.hide_render = True
        col_ob.display_type = "WIRE"
        cols["Depto_Colision"].hide_render = True

    # Cámaras
    col_cam = bpy.data.collections["Depto_Camaras"]
    for suf, pos, obj, *z in CAMARAS:
        camara(f"Depto_Cam_{suf}", pos, obj, z[0] if z else (OJO, OJO), LENTE_MM, col_cam)
    pos, obj, z, lente = MAQUETA
    # El cielo del palier es de la fase 3: si aún no existe, render_interior sólo avisa.
    camara("Depto_Cam_Maqueta", pos, obj, (z, 0.0), lente, col_cam, ocultar="Depto_Cielo,Depto_Palier_Cielo")

    # ------------------------------------------------------------------ pruebas
    mundo = []
    for _, (x0, x1, y0, y1, z0, z1) in todas:
        X0, X1, Y0, Y1 = rect_bl(x0, x1, y0, y1)
        mundo.append((X0, X1, Y0, Y1, z0, z1))
    # 1) Dimensiones exteriores = las del brief (6,01 × 8,98), sin balcón.
    xs = [c[0] for c in mundo] + [c[1] for c in mundo]
    ys = [c[2] for c in mundo] + [c[3] for c in mundo]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    esp_x, esp_y = (Y["S_O"] - Y["N_O"]) * S, (X["E_O"] - X["W_O"]) * S
    assert abs(dx - esp_x) < 1e-6 and abs(dy - esp_y) < 1e-6, (dx, dy)
    # 2) Cada vano: libre en su centro (a 1,0 m o a mitad de ventana) y macizo 2 cm más allá de cada jamba.
    fallos = []
    for nombre, x0, x1, y0, y1, vanos, _ in MUROS:
        eje_x = (x1 - x0) >= (y1 - y0)
        mid = (y0 + y1) / 2 if eje_x else (x0 + x1) / 2
        for a, b, ante, dintel, vid in vanos:
            zc = 1.0 if ante == 0 else (ante + dintel) / 2
            def pt(u, z):
                px = (u, mid) if eje_x else (mid, u)
                return (*P.a_blender(*px), z)
            if dentro(mundo, pt((a + b) / 2, zc)):
                fallos.append(f"{vid}: centro obstruido")
            if dintel < H and not dentro(mundo, pt((a + b) / 2, (dintel + H) / 2)):
                fallos.append(f"{vid}: falta dintel")
            if ante > 0 and not dentro(mundo, pt((a + b) / 2, ante / 2)):
                fallos.append(f"{vid}: falta antepecho")
            for u in (a - 0.02 / S, b + 0.02 / S):
                ini, fin = (x0, x1) if eje_x else (y0, y1)
                if ini < u < fin and not dentro(mundo, pt(u, zc)):
                    fallos.append(f"{vid}: jamba abierta en {u:.1f}px")
    assert not fallos, fallos
    n_vanos = sum(len(m[5]) for m in MUROS)

    objs = [o for n in COLS_FASE for o in bpy.data.collections[n].all_objects]   # sólo lo de esta fase
    tris = 0
    for o in objs:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    scene.camera = bpy.data.objects["Depto_Cam_Planta"]
    SE.sellar(scene, "02")
    bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
    print(f"CHECK exterior {dx:.3f} x {dy:.3f} m (esperado {esp_x:.3f} x {esp_y:.3f}); vanos verificados {n_vanos}")
    print(f"FASE_OK Depto_02_blockout {len(objs)} {tris} sello={scene['depto_fase02']}")


if __name__ == "__main__":
    main()
