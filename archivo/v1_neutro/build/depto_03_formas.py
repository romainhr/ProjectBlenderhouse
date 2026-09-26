"""Fase 3 (formas) del activo Depto: puertas, ventanas, baranda de vidrio, palier, closets, cocina, nicho
de lavadora y sanitarios.

Uso (o todo el pipeline con build/depto_run.sh):
    blender -b build/depto.blend --python-exit-code 1 --python build/depto_03_formas.py

Idempotente: exige que se haya abierto el maestro con el sello vigente de la fase 2 (cadena de
build/depto_sellos.py), borra y reconstruye sólo sus colecciones (Depto_Aberturas, Depto_Fijos,
Depto_Sanitarios, Depto_BalconDetalle, Depto_Palier) y no modifica objetos de otras fases. Antes de
guardar prueba (si algo falla, no guarda): presupuesto de triángulos, cada hoja cerrada dentro de su
vano, ninguna pieza que penetre muros u otras piezas (> 1 mm), cámaras a ≥ 0,20 m de todo sólido y el
paso libre de la corredera del living. Sella scene["depto_fase03"] y borra los sellos posteriores.

Orígenes de cada constante (etiqueta en el comentario):
  medido    = línea del plano (centro de trazo, build/depto_plano.py o re-medición indicada);
              verificado en cada corrida por build/depto_medicion/verificar_lineas.py cuando se indica.
  extracción= bbox de artefactos de la Fase 0 (build/depto_medicion/extraccion_px_bordes.json, bordes de
              trazo, ±1 px).
  brief     = decisión del brief (asset-brief-depto.md); compuerta = decisión del usuario en una compuerta.
  supuesto  = medida comercial o constructiva usual, no está en el plano.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_geom as G  # noqa: E402
import depto_plano as P  # noqa: E402
import depto_sellos as SE  # noqa: E402
from depto_geom import Pieza, px  # noqa: E402

X, Y = P.X, P.Y
H = P.ALTURA_PISO_CIELO
OUT_BLEND = SE.MAESTRO
COLS = ("Depto_Aberturas", "Depto_Fijos", "Depto_Sanitarios", "Depto_BalconDetalle", "Depto_Palier")
JUNTA = 0.003                # junta entre frentes y hojas de mueble (supuesto)

# ---------------------------------------------------------------------------
# Puertas (m salvo px). Hojas interiores: radio del arco de giro medido (P.HOJA_PX).
# ---------------------------------------------------------------------------
HOJA_ALTO = 2.00             # supuesto: hoja comercial (brief: dintel 2,05 = hoja + marco)
HOJA_ESP = 0.04              # supuesto: hoja interior
HOJA_ESP_ENTRADA = 0.05      # supuesto: hoja de acceso
HOJA_ENTRADA = 1.00          # brief (decisión 1): hoja de 1,00 en la luz dibujada de 1,07 (el arco mide 1,03)
LUZ_PISO = 0.01              # supuesto: holgura bajo la hoja
MARCO_ANCHO = 0.025          # medido: jamba = (luz 0,76 − hoja 0,71) / 2 en las puertas interiores
MARCO_SOBRESALE = 0.01       # supuesto: el marco sobresale 1 cm de cada cara del muro
MANILLA_Z = 1.00             # supuesto: altura estándar
MANILLA = (0.12, 0.06)       # supuesto: largo de la manilla y cuánto sobresale de la hoja
# Ángulo de las hojas abiertas. D1 y D2: a 90° la manilla del lado de la bisagra toca el tabique T3 (≈86°),
# así que quedan a 84°. B1 y B2: del lado de la bisagra no hay muro (la tina queda a 0,07 m de la manilla) y a
# 90° la hoja deja 0,61 m de paso frente a la jamba opuesta; a 84° dejaba 0,53 (recorrido de 0,25 m: no pasa).
ANGULO_ABIERTA = dict(D1=84.0, D2=84.0, B1=90.0, B2=90.0)
# (id, muro: 'x'|'y' = eje del muro en el plano, a, b [px a lo largo del eje], c0, c1 [px espesor del muro],
#  hoja px, lado bisagra 'a'|'b', abre hacia: +1/-1 en el eje perpendicular, abierta, opciones)
PUERTAS = [
    ("D1", "x", X["JAMBA_D"], X["T3_W"], Y["D1_N"], Y["D1_S"], P.HOJA_PX["D1"], "b", -1, True, {}),   # abre al Dorm 1 (norte)
    ("D2", "x", X["JAMBA_D"], X["T3_W"], Y["D2_N"], Y["D2_S"], P.HOJA_PX["D2"], "b", +1, True, {}),   # abre al Dorm 2 (sur)
    ("B1", "y", Y["T4_A"], Y["T4_B"], X["T4_W"], X["T4_E"], P.HOJA_PX["B1"], "a", +1, True, {}),      # abre al Baño 1 (este)
    ("B2", "y", Y["T10_A"], Y["T10_B"], X["T10_W"], X["T10_E"], P.HOJA_PX["B2"], "a", +1, True, {}),  # abre al Baño 2 (este)
    # compuerta 2: cerrada. Bisagra al sur (arco del plano), abre hacia el hall. La jamba norte cubre el canto del
    # forro (E_FORRO) y el sobresaliente del lado del hall no entra en T9 (que empieza en T9_N, antes de ENT_S).
    ("Entrada", "y", Y["ENT_N"], Y["ENT_S"], X["E_I"], X["E_O"], px(HOJA_ENTRADA), "b", -1, False,
     {"w_c0_a": X["E_FORRO"] - px(MARCO_SOBRESALE), "u_max_c0": Y["T9_N"]}),
]

# ---------------------------------------------------------------------------
# Ventanas: marco de 0,05 × 0,06 m centrado en el espesor del muro (supuesto), con los encuentros de hojas
# medidos en el plano (crítico de topología, Fase 0; confirmados por el crítico de ubicación de la fase 3).
# ---------------------------------------------------------------------------
PERFIL = 0.05                # supuesto: ancho visto del perfil
PERFIL_PROF = 0.06           # supuesto: fondo del marco de una hoja
PERFIL_PROF_CORREDERA = 0.10  # supuesto: marco de dos rieles del ventanal
HOJA_CORREDERA_PROF = 0.04   # supuesto: fondo del perfil de cada hoja corredera
VIDRIO_ESP = 0.006           # supuesto: vidrio simple de 6 mm
VENTANAS = [
    # (id, eje del muro, a, b, c0, c1 [espesor], antepecho, dintel, encuentros px, material de vidrio)
    ("VD1", "y", Y["V_D1_A"], Y["V_D1_B"], X["W_O"], X["W_I"], P.ANTEPECHO_DORMITORIOS, P.DINTEL_VENTANAS,
     [111.0], "Depto_Mat_Vidrio"),                        # medido: encuentro y≈111 (hojas desiguales 1,03 + 0,79)
    ("VD2", "y", Y["V_D2_A"], Y["V_D2_B"], X["W_O"], X["W_I"], P.ANTEPECHO_DORMITORIOS, P.DINTEL_VENTANAS,
     [404.5], "Depto_Mat_Vidrio"),                        # medido: encuentro y≈404,5 (hojas iguales)
    ("VB1", "x", X["V_B1_A"], X["V_B1_B"], Y["N_O"], Y["N_I"], P.ANTEPECHO_BANO, P.DINTEL_VENTANAS,
     [], "Depto_Mat_VidrioEsmerilado"),                   # supuesto: ventana alta del baño con vidrio esmerilado
]
# Ventanal del living: corredera de dos rieles. Medido: encuentro VEN_ENCUENTRO y flecha de deslizamiento en el
# paño norte (hoja móvil de 1,05); el paño sur (1,89) es fijo, en el riel exterior. Para el recorrido la hoja
# móvil queda corrida detrás del paño fijo y deja libre el paño norte (≈0,97 m entre jamba y montante).
VENTANAL = dict(a=Y["VEN_A"], b=Y["VEN_B"], c0=X["W_O"], c1=X["W_I"], z0=0.0, z1=P.DINTEL_VENTANAS,
                encuentro=Y["VEN_ENCUENTRO"], abierta=True)

# ---------------------------------------------------------------------------
# Baranda de vidrio del balcón (compuerta 2): canal inferior, vidrio y pasamanos, sobre los ejes medidos.
# La colisión es Depto_Col_Baranda (fase 2, BARANDA_TIPO = "vidrio").
# ---------------------------------------------------------------------------
Z_BAL = -P.DESNIVEL_BALCON
CANAL = (0.05, 0.06)          # supuesto: ancho, alto del perfil inferior
PASAMANOS = (0.05, 0.05)      # supuesto: ancho, alto; tope a 1,00 sobre el piso del balcón (brief)
VIDRIO_BARANDA = 0.012        # supuesto: laminado 6+6

# ---------------------------------------------------------------------------
# Palier exterior neutro (compuerta 2: "palier neutro"; las medidas son supuestas, el plano no lo muestra).
# ---------------------------------------------------------------------------
PALIER_ANCHO = 1.40           # supuesto: pasillo común usual
PALIER_LARGO_EXTRA = 1.00     # supuesto: tramo visible a cada lado de la puerta
PALIER_MURO = 0.15            # supuesto
LOSA = P.ESPESOR_LOSA         # supuesto (el mismo de la fase 2)

# ---------------------------------------------------------------------------
# Closets hasta el cielo (brief), con puertas correderas en dos rieles: el plano no dibuja arcos de giro en
# los closets (inferido), y abatibles tapaban la puerta del Baño 2 al abrirse (crítico de uso, fase 3).
# ---------------------------------------------------------------------------
PUERTA_CLOSET_ESP = 0.02      # supuesto: melamina de 18 mm con canto
RIEL_SEP = 0.005              # supuesto: separación entre las hojas de los dos rieles
CLOSET_CABEZAL = 0.05         # supuesto: cabezal del riel superior
CLOSET_SOLAPE = 0.03          # supuesto: traslape de las dos hojas en el centro
CLOSETS = [
    # (id, x0, x1, y_fondo, y_frente)  frente = línea gris medida (CL*), fondo = muro o tabique
    ("D1_Norte", X["T3_E"], X["T4_W"], Y["N_I"], Y["CL1_N"]),
    ("D1_Sur", X["T3_E"], X["T4_W"], Y["T5_N"], Y["CL1_S"]),
    ("D2_Norte", X["T3_E"], X["T10_W"], Y["T9_S"], Y["CL2_N"]),
    ("D2_Sur", X["T3_E"], X["T10_W"], Y["S_I"], Y["CL2_S"]),
]

# ---------------------------------------------------------------------------
# Cocina en L. Todas las líneas px se verifican contra el plano en verificar_lineas.py (sondas "cocina").
# ---------------------------------------------------------------------------
COC_FRENTE_Y = Y["T5_S"] + 31.55        # medido: frente del tramo norte (y≈182,8; fondo 0,60)
COC_FRENTE_X = X["E_FORRO"] - 31.51     # medido: frente del tramo este (x≈386,7; fondo 0,60)
TORRE_Y = (227.8, 258.4)                # medido (re-medición fase 3): centros de los trazos N y S del módulo rayado
ALTOS_Y = 170.5                          # medido: discontinua de muebles altos, tramo norte (centroide 171,1)
ALTOS_X = 398.5                          # medido: idem, tramo este
MESON_Z = P.ALTURA_MESON                 # brief: 0,90
CUBIERTA_ESP = 0.04                      # supuesto
ZOCALO_ALTO, ZOCALO_RETRANQUEO = 0.10, 0.05   # supuesto
FRENTE_ESP = 0.018                       # supuesto: melamina de 18 mm
RELLENO_ESQUINA = 0.05                   # supuesto: rellenador en la esquina de la L (los frentes no chocan)
ALTOS_Z = P.MUEBLES_ALTOS_Z              # brief: 1,50 a 2,10
TORRE_ALTO = 2.10                        # brief (inferido): torre de horno y despensa hasta 2,10
HORNO_Z = (0.75, 1.35)                   # supuesto: frente de horno empotrado en la torre
TORRE_COSTADO = 0.018                    # supuesto: costados de la torre a cada lado del horno
ANAFE = (326.0, 358.0, 155.0, 178.4)     # medido (re-medición fase 3): centros del contorno (x0, x1, y0, y1)
BACHA = (390.9, 413.0, 193.7, 218.1)     # medido (re-medición fase 3): centros del contorno del lavaplatos; la
                                         # extracción (392,5-416) estaba corrida 2-3 px al este
BACHA_REBORDE = 0.015                    # supuesto
BACHA_PROF, BACHA_PARED = 0.18, 0.008    # supuesto: cubeta de acero
ESCURRIDOR = (393.0, 411.0, 172.0, 188.0)  # extracción: rectángulo con líneas verticales junto al lavaplatos
REFRI = (0.60, 0.60, 1.80)               # inferido (brief): ancho, fondo, alto; fondo 0,60 para quedar al ras del
                                         # frente discontinuo (el rectángulo dibujado mide ≈0,61)
REFRI_HOLGURA = 0.02                     # supuesto: separación al muro
CAMPANA_Z = (ALTOS_Z[0] - 0.02, ALTOS_Z[0])  # supuesto: campana telescópica bajo el mueble alto, ≈0,57 m sobre el
CAMPANA_FONDO = 0.48                     # anafe (con los altos a 1,50 del brief no cabe más; fabricantes: 0,60-0,75,
                                         # valor de memoria sin verificar)
MODULO_BASE = 0.60                       # supuesto: ancho de frentes de mueble base
MODULO_BACHA = 0.40                      # supuesto: bajo el lavaplatos, dos puertas de 0,40 (mueble de 0,80)
MODULO_ALTO = 0.40                       # supuesto

# ---------------------------------------------------------------------------
# Nicho de lavadora: frente plegable cerrado (el arco del plano) y dintel sobre la puerta.
# ---------------------------------------------------------------------------
LAVADORA = (0.60, 0.60, 0.85)          # supuesto: carga frontal estándar
LAVADORA_HOLGURA = 0.03                # supuesto: separación al fondo del nicho
LV_FRENTE_ESP = 0.02                   # supuesto
LV_DINTEL_ESP = 0.072                  # supuesto: como un tabique (0,072 entre centros de línea, medido)

# ---------------------------------------------------------------------------
# Sanitarios.
# ---------------------------------------------------------------------------
TINA_FONDO = 0.70            # brief (decisión 2): tina de 1,45 × 0,70 que llena el nicho
TINA_ALTO = 0.55             # supuesto
TINA_PARED = 0.07            # supuesto
TINA_BASE = 0.12             # supuesto
BANOS = {
    # tina: (x0, x1, cara del muro en y, sentido hacia el baño)
    # wc: bbox de la extracción, muro del estanque ('E'|'O') y estanque 'visible' u 'oculto' (en la repisa)
    # repisa (B1): línea continua medida x≈408,65 entre tina y shaft; alto 1,10 del brief
    # ducto (B2): discontinua medida de y 369 a 445, que cruza la tina: elemento sobre el plano de corte ->
    #             ducto o cielo falso local contra el muro este, de 2,10 al cielo (inferido, fase 3). Centro de
    #             trazo 412,6 sobre la tina y ≈412,0 junto al WC (ahí se confunde con el estanque): se usa 412,3
    # vanitorio: bbox de la extracción con el borde del muro declarado y el extremo libre
    "B1": dict(tina=(X["T4_E"], X["E_FORRO"], Y["N_I"], +1),
               wc=dict(bbox=(382.0, X["E_FORRO"], 71.0, 96.0), muro="E", estanque="oculto"),
               repisa=(408.5, X["E_FORRO"], 64.4, Y["SH1_N"], 1.10),
               vanitorio=dict(bbox=(X["T4_E"], 380.0, 121.0, Y["T5_N"]), muro=("S", Y["T5_N"]), libre="E")),
    "B2": dict(tina=(X["T10_E"], X["E_I"], Y["T9_S"], +1),
               wc=dict(bbox=(381.0, X["E_I"], 412.0, 436.0), muro="E", estanque="visible"),
               ducto=(412.3, X["E_I"], Y["T9_S"], Y["SH2_N"], 2.10),
               vanitorio=dict(bbox=(X["T10_E"], 382.0, 451.0, Y["S_I"]), muro=("S", Y["S_I"]), libre="E")),
}
WC = dict(taza_alto=0.40, pedestal_alto=0.30, taza_largo=0.52, taza_ancho=0.37, estanque_z=(0.40, 0.80),
          estanque_fondo=0.18, estanque_ancho=0.40)   # supuesto: medidas comerciales usuales
VANITORIO_Z = (0.80, 0.85)       # supuesto: mueble y cubierta
VANITORIO_RETRANQUEO = 0.02      # supuesto: vuelo de la cubierta sobre el mueble
RESPALDO_ALTO = 0.08             # supuesto
LAVAMANOS = dict(rx=0.21, ry=0.15, alto=0.13, pared=0.012, fondo=0.015, al_muro=0.08)  # supuesto: de apoyo
LLAVE = dict(al_muro=0.05, radio=0.018, alto=0.25, cano=0.13)   # supuesto: grifería alta contra el muro
ESPEJO_Z = (1.15, 1.90)          # supuesto

TOL_PENETRACION = 0.001          # m: dos piezas no pueden solaparse más que esto en los tres ejes
HOLGURA_CAMARA = 0.20            # m: distancia mínima (3D) de cada cámara de ambiente a todo sólido


def uw(eje, u0, u1, w0, w1):
    """(u a lo largo del muro, w a través) -> (x0, x1, y0, y1) del plano."""
    return (u0, u1, w0, w1) if eje == "x" else (w0, w1, u0, u1)


def mundo(eje, u, w, z=0.0):
    x, y = (u, w) if eje == "x" else (w, u)
    return Vector((*P.a_blender(x, y), z))


# ---------------------------------------------------------------------------
def puertas(col):
    """Marco, hoja y manillas. La hoja y sus manillas se arman cerradas con el origen en la bisagra, y la
    hoja abierta es la misma malla girada ANGULO_ABIERTA[id]: el tour puede abrir y cerrar rotando en Z."""
    hojas = []
    for pid, eje, a, b, c0, c1, hoja, bisagra, sentido, abierta, opc in PUERTAS:
        es_ent = pid == "Entrada"
        ma, ms = px(MARCO_ANCHO), px(MARCO_SOBRESALE)
        if es_ent:
            ma = ((b - a) - hoja) / 2              # jamba = (luz − hoja) / 2
        assert ma > 0, f"{pid}: la hoja no cabe en la luz"
        dintel = P.DINTEL_PUERTAS
        marco = Pieza(f"Depto_Puerta_{pid}_Marco", "Depto_Mat_MarcoPuerta")
        umax0 = opc.get("u_max_c0", b)

        def pieza_marco(u0, u1, z0, z1, w_c0):
            marco.caja(*uw(eje, u0, u1, c0, c1 + ms), z0, z1)              # dentro del muro y lado c1
            if min(u1, umax0) > u0:
                marco.caja(*uw(eje, u0, min(u1, umax0), w_c0, c0), z0, z1)  # sobresaliente del lado c0
        pieza_marco(a, a + ma, 0.0, dintel, opc.get("w_c0_a", c0 - ms))    # jambas
        pieza_marco(b - ma, b, 0.0, dintel, c0 - ms)
        pieza_marco(a + ma, b - ma, HOJA_ALTO, dintel, c0 - ms)             # cabezal entre jambas
        marco.crear(col)

        # Hoja cerrada: entre jambas, al ras de la cara hacia la que abre. Bisagra en esa cara, junto a la jamba.
        e = px(HOJA_ESP_ENTRADA if es_ent else HOJA_ESP)
        cara = c0 if sentido < 0 else c1
        w0, w1 = sorted((cara, cara - sentido * e))
        du = 1 if bisagra == "a" else -1                  # de la bisagra hacia el canto libre
        ub = a + ma if bisagra == "a" else b - ma
        ulibre = b - ma if bisagra == "a" else a + ma
        piv = mundo(eje, ub, cara)
        h = Pieza(f"Depto_Puerta_{pid}_Hoja", "Depto_Mat_PuertaEntrada" if es_ent else "Depto_Mat_PuertaMadera")
        h.caja(*uw(eje, a + ma, b - ma, w0, w1), LUZ_PISO, HOJA_ALTO)
        man = Pieza(f"Depto_Puerta_{pid}_Manillas", "Depto_Mat_Manilla")
        m0, m1 = sorted((ulibre - du * px(0.05), ulibre - du * px(0.05 + MANILLA[0])))
        for wa, wb in ((w0 - px(MANILLA[1]), w0), (w1, w1 + px(MANILLA[1]))):
            man.caja(*uw(eje, m0, m1, wa, wb), MANILLA_Z - 0.01, MANILLA_Z + 0.01)
        # Giro: del sentido cerrado (bisagra -> canto libre) hacia el lado en que abre, en coordenadas de mundo.
        dc, do = mundo(eje, ub + du, cara) - piv, mundo(eje, ub, cara + sentido) - piv
        signo = 1 if dc.x * do.y - dc.y * do.x > 0 else -1
        ang_max = ANGULO_ABIERTA.get(pid, 90.0) * signo          # la entrada (cerrada) abriría a 90°
        ang = math.radians(ang_max) if abierta else 0.0
        ob = h.crear(col, {"puerta": pid, "abierta": abierta, "angulo_deg": round(math.degrees(ang), 2),
                           "angulo_abierta_deg": ang_max, "bisagra": "origen, eje Z"},
                     origen=tuple(piv))
        ob.rotation_euler.z = ang
        man.crear(col, origen=tuple(piv), padre=ob)
        hojas.append((ob, eje, a, b, c0, c1))
    return hojas


def marco_ventana(marco, vidrio, eje, a, b, c0, c1, z0, z1, encuentros):
    p, pp, vg = px(PERFIL), px(PERFIL_PROF), px(VIDRIO_ESP)
    cm = (c0 + c1) / 2
    assert encuentros == sorted(encuentros) and all(a + 2 * p < e < b - 2 * p for e in encuentros), encuentros
    wa, wb = cm - pp / 2, cm + pp / 2
    marco.caja(*uw(eje, a, a + p, wa, wb), z0, z1)                     # jambas
    marco.caja(*uw(eje, b - p, b, wa, wb), z0, z1)
    marco.caja(*uw(eje, a + p, b - p, wa, wb), z0, z0 + PERFIL)        # riel inferior y cabezal, a tope
    marco.caja(*uw(eje, a + p, b - p, wa, wb), z1 - PERFIL, z1)
    zi0, zi1 = z0 + PERFIL, z1 - PERFIL
    for e in encuentros:                                               # montante: dos perfiles traslapados
        marco.caja(*uw(eje, e - p, e + p * 0.2, wa, cm), zi0, zi1)
        marco.caja(*uw(eje, e - p * 0.2, e + p, cm, wb), zi0, zi1)
    bordes = [a + p] + [x for e in encuentros for x in (e - p, e + p)] + [b - p]
    for i in range(0, len(bordes), 2):
        vidrio.caja(*uw(eje, bordes[i], bordes[i + 1], cm - vg / 2, cm + vg / 2), zi0, zi1)


def ventanas(col):
    for vid, eje, a, b, c0, c1, z0, z1, encuentros, mat_vidrio in VENTANAS:
        marco = Pieza(f"Depto_Ventana_{vid}_Marco", "Depto_Mat_MarcoVentana")
        vidrio = Pieza(f"Depto_Ventana_{vid}_Vidrio", mat_vidrio)
        marco_ventana(marco, vidrio, eje, a, b, c0, c1, z0, z1, encuentros)
        marco.crear(col)
        vidrio.crear(col, {"vidrio": True})


def hoja_corredera(marco, vidrio, u0, u1, wc, z0, z1):
    """Hoja de corredera (perfil perimetral + vidrio) en el riel centrado en wc, eje del muro 'y'."""
    p, hp, vg = px(PERFIL), px(HOJA_CORREDERA_PROF), px(VIDRIO_ESP)
    wa, wb = wc - hp / 2, wc + hp / 2
    marco.caja(*uw("y", u0, u0 + p, wa, wb), z0, z1)
    marco.caja(*uw("y", u1 - p, u1, wa, wb), z0, z1)
    marco.caja(*uw("y", u0 + p, u1 - p, wa, wb), z0, z0 + PERFIL)
    marco.caja(*uw("y", u0 + p, u1 - p, wa, wb), z1 - PERFIL, z1)
    vidrio.caja(*uw("y", u0 + p, u1 - p, wc - vg / 2, wc + vg / 2), z0 + PERFIL, z1 - PERFIL)


def ventanal(col):
    """Corredera de dos rieles: marco perimetral, paño fijo sur en el riel exterior y hoja móvil norte en el
    interior, corrida detrás del fijo. Devuelve (u del centro del paso libre, u de control del paño fijo)."""
    v = VENTANAL
    a, b, c0, c1, z0, z1, e = v["a"], v["b"], v["c0"], v["c1"], v["z0"], v["z1"], v["encuentro"]
    p, pp = px(PERFIL), px(PERFIL_PROF_CORREDERA)
    cm = (c0 + c1) / 2
    w_ext, w_int = cm - pp / 4, cm + pp / 4            # c0 = W_O es la cara exterior
    marco = Pieza("Depto_Ventana_Ventanal_Marco", "Depto_Mat_MarcoVentana")
    vidrio = Pieza("Depto_Ventana_Ventanal_Vidrio", "Depto_Mat_Vidrio")
    wa, wb = cm - pp / 2, cm + pp / 2
    marco.caja(*uw("y", a, a + p, wa, wb), z0, z1)
    marco.caja(*uw("y", b - p, b, wa, wb), z0, z1)
    marco.caja(*uw("y", a + p, b - p, wa, wb), z0, z0 + PERFIL)       # riel inferior (5 cm: bajo el escalón del tour)
    marco.caja(*uw("y", a + p, b - p, wa, wb), z1 - PERFIL, z1)
    zi0, zi1 = z0 + PERFIL, z1 - PERFIL
    hoja_corredera(marco, vidrio, e - p / 2, b - p, w_ext, zi0, zi1)  # paño fijo: parte del marco
    marco.crear(col)
    vidrio.crear(col, {"vidrio": True})
    # Hoja móvil: cerrada va de la jamba norte al encuentro (con traslape de un perfil sobre el fijo).
    u0, u1 = a + p, e + p / 2
    desplaz = (e - p / 2) - u0 if v["abierta"] else 0.0              # corrida hasta alinear con el fijo
    assert u1 + desplaz <= b - p, "la hoja móvil no cabe detrás del paño fijo"
    hm = Pieza("Depto_Ventana_Ventanal_Hoja", "Depto_Mat_MarcoVentana")
    hv = Pieza("Depto_Ventana_Ventanal_HojaVidrio", "Depto_Mat_Vidrio")
    hoja_corredera(hm, hv, u0, u1, w_int, zi0, zi1)
    ref = mundo("y", u0, w_int, zi0)                                  # origen: esquina de la hoja cerrada
    dvec = mundo("y", u0 + desplaz, w_int, zi0) - ref
    ob = hm.crear(col, {"corredera": True, "abierta": v["abierta"], "recorrido_m": round(dvec.length, 4),
                        "eje_apertura": list((dvec.normalized() if dvec.length else Vector((0, 0, 0)))[:])},
                  origen=tuple(ref))
    ob.location = ref + dvec
    hv.crear(col, {"vidrio": True}, origen=tuple(ref), padre=ob)
    return (u0 + (e - p / 2)) / 2, (u1 + desplaz + b - p) / 2


def baranda_vidrio(col):
    if "Depto_Col_Baranda" not in bpy.data.objects:
        raise SystemExit("ERROR: falta Depto_Col_Baranda: la fase 2 debe tener BARANDA_TIPO = 'vidrio' (compuerta 2).")
    e = px(VIDRIO_BARANDA) / 2
    cw, ch = px(CANAL[0]) / 2, CANAL[1]
    pw, ph = px(PASAMANOS[0]) / 2, PASAMANOS[1]
    top = Z_BAL + P.ALTURA_BARANDA_BALCON
    tramos = [  # (eje, fijo px, desde, hasta): mismos extremos que la masa del blockout
        ("y", X["BARANDA_O"], Y["BARANDA_N"] - cw, Y["BARANDA_S"] + cw),
        ("x", Y["BARANDA_N"], X["BARANDA_O"] + cw, X["W_O"]),
        ("x", Y["BARANDA_S"], X["BARANDA_O"] + cw, X["W_O"]),
    ]
    vid = Pieza("Depto_Balcon_BarandaVidrio", "Depto_Mat_Vidrio")
    met = Pieza("Depto_Balcon_BarandaPerfiles", "Depto_Mat_Pasamanos")
    for eje, f, u0, u1 in tramos:
        # eje = eje largo del tramo: 'y' = a lo largo de y (fijo en x)
        def c(obj, half, za, zb):
            obj.caja(*uw(eje, u0, u1, f - half, f + half), za, zb)
        c(met, cw, Z_BAL, Z_BAL + ch)                           # canal inferior
        c(vid, e, Z_BAL + ch, top - ph)                         # vidrio
        c(met, pw, top - ph, top)                               # pasamanos
    vid.crear(col, {"vidrio": True})
    met.crear(col)


def palier(col):
    ancho, extra, m = px(PALIER_ANCHO), px(PALIER_LARGO_EXTRA), px(PALIER_MURO)
    x0, x1 = X["E_O"], X["E_O"] + ancho
    y0, y1 = Y["ENT_N"] - extra, Y["ENT_S"] + extra
    Pieza("Depto_Palier_Piso", "Depto_Mat_PalierPiso").caja(x0, x1 + m, y0 - m, y1 + m, -LOSA, 0.0).crear(col)
    muros = Pieza("Depto_Palier_Muros", "Depto_Mat_Palier")
    muros.caja(x1, x1 + m, y0 - m, y1 + m, 0.0, H)              # muro de fondo
    muros.caja(x0, x1, y0 - m, y0, 0.0, H)                      # muros de los extremos
    muros.caja(x0, x1, y1, y1 + m, 0.0, H)
    muros.crear(col)
    Pieza("Depto_Palier_Cielo", "Depto_Mat_Palier").caja(x0, x1 + m, y0 - m, y1 + m, H, H + LOSA).crear(col)


def closets(col):
    e, sep, j = px(PUERTA_CLOSET_ESP), px(RIEL_SEP), px(JUNTA)
    for cid, x0, x1, yf, yfr in CLOSETS:
        s = 1 if yfr > yf else -1                               # sentido fondo -> frente (hacia el recinto)
        fondo_rieles = yfr - s * (2 * e + sep + px(0.005))       # cara del cuerpo detrás de los dos rieles
        cuerpo = Pieza(f"Depto_Closet_{cid}_Cuerpo", "Depto_Mat_MuebleBlanco")
        cuerpo.caja(x0, x1, yf, fondo_rieles, 0.0, H)
        cuerpo.caja(x0, x1, fondo_rieles, yfr, H - CLOSET_CABEZAL, H)   # cabezal con el riel superior
        cuerpo.crear(col)
        mid, sol = (x0 + x1) / 2, px(CLOSET_SOLAPE)
        hojas = Pieza(f"Depto_Closet_{cid}_Puertas", "Depto_Mat_MuebleBlanco")
        tir = Pieza(f"Depto_Closet_{cid}_Tiradores", "Depto_Mat_Manilla")
        zt = (0.90, 1.30)
        # hoja del riel exterior (al ras de la línea del plano) y hoja del riel interior
        hojas.caja(x0 + j, mid + sol / 2, yfr - s * e, yfr, LUZ_PISO, H - CLOSET_CABEZAL)
        w_int = yfr - s * (e + sep)                             # cara de la hoja interior hacia el recinto
        hojas.caja(mid - sol / 2, x1 - j, w_int - s * e, w_int, LUZ_PISO, H - CLOSET_CABEZAL)
        tir.caja(x0 + px(0.03), x0 + px(0.05), yfr, yfr + s * px(0.002), *zt)          # tiradores embutidos
        tir.caja(x1 - px(0.05), x1 - px(0.03), w_int, w_int + s * px(0.002), *zt)
        hojas.crear(col, {"corredera": True})
        tir.crear(col)


def frentes(obj, eje, u_ini, u_fin, w_frente, s, z0, z1, modulo):
    """Frentes de mueble con juntas: a lo largo de u, en el plano w_frente, hacia afuera según s."""
    assert u_fin > u_ini, (u_ini, u_fin)
    n = max(1, round((u_fin - u_ini) / px(modulo)))
    paso = (u_fin - u_ini) / n
    j = px(JUNTA)
    for i in range(n):
        u0, u1 = u_ini + i * paso + j / 2, u_ini + (i + 1) * paso - j / 2
        obj.caja(*uw(eje, u0, u1, w_frente, w_frente + s * px(FRENTE_ESP)), z0, z1)


def cocina(col):
    f, rel = px(FRENTE_ESP), px(RELLENO_ESQUINA)
    zc = MESON_Z - CUBIERTA_ESP
    rb = px(BACHA_REBORDE)
    hueco = (BACHA[0] + rb, BACHA[1] - rb, BACHA[2] + rb, BACHA[3] - rb)   # corte de la cubierta y cubeta
    z_fondo_cubeta = MESON_Z - BACHA_PROF
    # Muebles base: tramo norte hasta el frente del tramo este (+ frente), tramo este con hueco para la cubeta
    base = Pieza("Depto_Cocina_Base", "Depto_Mat_MuebleBlanco")
    base.caja(X["T3_E"], COC_FRENTE_X + f, Y["T5_S"], COC_FRENTE_Y - f, ZOCALO_ALTO, zc)
    base.caja_con_hueco(COC_FRENTE_X + f, X["E_FORRO"], Y["T5_S"], TORRE_Y[0], ZOCALO_ALTO, zc,
                        hueco, z_fondo_cubeta - 0.01)
    base.crear(col)
    zoc = Pieza("Depto_Cocina_Zocalo", "Depto_Mat_Zocalo")
    zr = px(ZOCALO_RETRANQUEO)
    zoc.caja(X["T3_E"], COC_FRENTE_X + zr, Y["T5_S"], COC_FRENTE_Y - zr, 0.0, ZOCALO_ALTO)
    zoc.caja(COC_FRENTE_X + zr, X["E_FORRO"], COC_FRENTE_Y - zr, TORRE_Y[0], 0.0, ZOCALO_ALTO)
    zoc.crear(col)
    fr = Pieza("Depto_Cocina_Frentes", "Depto_Mat_MuebleBlanco")
    zf = (ZOCALO_ALTO, zc - 0.003)
    frentes(fr, "x", X["T3_E"], COC_FRENTE_X - rel, COC_FRENTE_Y - f, +1, *zf, MODULO_BASE)
    fr.caja(COC_FRENTE_X - rel + px(JUNTA) / 2, COC_FRENTE_X + f, COC_FRENTE_Y - f, COC_FRENTE_Y, *zf)   # rellenadores
    fr.caja(COC_FRENTE_X, COC_FRENTE_X + f, COC_FRENTE_Y, COC_FRENTE_Y + rel - px(JUNTA) / 2, *zf)
    frentes(fr, "y", COC_FRENTE_Y + rel, TORRE_Y[0], COC_FRENTE_X + f, -1, *zf, MODULO_BACHA)
    fr.crear(col)
    cub = Pieza("Depto_Cocina_Cubierta", "Depto_Mat_Granito")
    vuelo = px(0.02)
    cub.caja(X["T3_E"], X["E_FORRO"], Y["T5_S"], COC_FRENTE_Y + vuelo, zc, MESON_Z)
    cub.caja_con_hueco(COC_FRENTE_X - vuelo, X["E_FORRO"], COC_FRENTE_Y + vuelo, TORRE_Y[0], zc, MESON_Z, hueco, zc)
    cub.crear(col)
    Pieza("Depto_Cocina_Anafe", "Depto_Mat_VidrioNegro").caja(*ANAFE, MESON_Z, MESON_Z + 0.006).crear(col)
    bacha = Pieza("Depto_Cocina_Lavaplatos", "Depto_Mat_Acero")
    bacha.caja_con_hueco(*BACHA, MESON_Z, MESON_Z + 0.004, hueco, MESON_Z)                  # reborde
    bp = px(BACHA_PARED)
    bacha.caja_con_hueco(*hueco, z_fondo_cubeta, MESON_Z,
                         (hueco[0] + bp, hueco[1] - bp, hueco[2] + bp, hueco[3] - bp), z_fondo_cubeta + BACHA_PARED)
    bacha.crear(col)
    esc = Pieza("Depto_Cocina_Escurridor", "Depto_Mat_Acero")
    ex0, ex1, ey0, ey1 = ESCURRIDOR
    esc.caja(ex0, ex1, ey0, ey1, MESON_Z, MESON_Z + 0.003)
    for i in range(1, 6):                                                # nervios (las líneas del plano)
        xr = ex0 + (ex1 - ex0) * i / 6
        esc.caja(xr - px(0.003), xr + px(0.003), ey0 + px(0.02), ey1 - px(0.02), MESON_Z + 0.003, MESON_Z + 0.006)
    esc.crear(col)
    llave = Pieza("Depto_Cocina_Llave", "Depto_Mat_Acero")
    lx = BACHA[1] + px(0.025)
    ly = (BACHA[2] + BACHA[3]) / 2
    llave.cilindro(lx, ly, px(0.02), px(0.02), MESON_Z, MESON_Z + 0.30, seg=12)
    llave.caja(lx - px(0.20), lx - px(0.02), ly - px(0.012), ly + px(0.012), MESON_Z + 0.28, MESON_Z + 0.30)
    llave.crear(col)
    # Muebles altos: el cuerpo este arranca en la cara del norte (sin ranura en la esquina)
    altos = Pieza("Depto_Cocina_Altos", "Depto_Mat_MuebleBlanco")
    altos.caja(X["T3_E"], X["E_FORRO"], Y["T5_S"], ALTOS_Y - f, ALTOS_Z[0], ALTOS_Z[1])
    altos.caja(ALTOS_X + f, X["E_FORRO"], ALTOS_Y - f, TORRE_Y[0], ALTOS_Z[0], ALTOS_Z[1])
    altos.crear(col)
    fa = Pieza("Depto_Cocina_FrentesAltos", "Depto_Mat_MuebleBlanco")
    za = (ALTOS_Z[0] + 0.003, ALTOS_Z[1] - 0.003)
    frentes(fa, "x", X["T3_E"], ALTOS_X - rel, ALTOS_Y - f, +1, *za, MODULO_ALTO)
    fa.caja(ALTOS_X - rel + px(JUNTA) / 2, ALTOS_X + f, ALTOS_Y - f, ALTOS_Y, *za)            # rellenadores
    fa.caja(ALTOS_X, ALTOS_X + f, ALTOS_Y, ALTOS_Y + rel - px(JUNTA) / 2, *za)
    frentes(fa, "y", ALTOS_Y + rel, TORRE_Y[0], ALTOS_X + f, -1, *za, MODULO_ALTO)
    fa.crear(col)
    Pieza("Depto_Cocina_Campana", "Depto_Mat_Acero").caja(ANAFE[0], ANAFE[1], Y["T5_S"], Y["T5_S"] + px(CAMPANA_FONDO),
                                                           *CAMPANA_Z).crear(col)
    torre = Pieza("Depto_Cocina_Torre", "Depto_Mat_MuebleBlanco")
    torre.caja(COC_FRENTE_X, X["E_FORRO"], TORRE_Y[0], TORRE_Y[1], 0.0, TORRE_ALTO)
    torre.crear(col)
    tc = px(TORRE_COSTADO)
    Pieza("Depto_Cocina_Horno", "Depto_Mat_VidrioNegro").caja(COC_FRENTE_X - px(0.004), COC_FRENTE_X,
                                                              TORRE_Y[0] + tc, TORRE_Y[1] - tc, *HORNO_Z).crear(col)
    a, fo, al = REFRI
    yc = (TORRE_Y[1] + Y["COC_N"]) / 2
    xr1 = X["E_FORRO"] - px(REFRI_HOLGURA)
    Pieza("Depto_Cocina_Refrigerador", "Depto_Mat_Acero").caja(xr1 - px(fo), xr1, yc - px(a) / 2, yc + px(a) / 2,
                                                               0.0, al).crear(col)


def nicho_lavadora(col):
    e = px(LV_FRENTE_ESP)
    x0, x1 = X["T3_E"], X["LV_W"]
    frente = Pieza("Depto_LV_Frente", "Depto_Mat_MuebleBlanco")
    mid = (x0 + x1) / 2
    for u0, u1 in ((x0 + px(JUNTA), mid - px(JUNTA) / 2), (mid + px(JUNTA) / 2, x1 - px(JUNTA))):
        frente.caja(u0, u1, Y["LV_F"], Y["LV_F"] + e, LUZ_PISO, P.DINTEL_PUERTAS)   # puerta plegable cerrada
    frente.caja(x0, x1, Y["LV_F"], Y["LV_F"] + px(LV_DINTEL_ESP), P.DINTEL_PUERTAS, H)   # dintel
    frente.crear(col)
    w, d, h = LAVADORA
    yb = Y["T9_N"] - px(LAVADORA_HOLGURA)
    Pieza("Depto_LV_Lavadora", "Depto_Mat_Electro").caja(mid - px(w) / 2, mid + px(w) / 2, yb - px(d), yb,
                                                         0.0, h).crear(col)


def tina(col, bid, x0, x1, ym, s):
    y1 = ym + s * px(TINA_FONDO)
    pa = px(TINA_PARED)
    t = Pieza(f"Depto_Sanitario_{bid}_Tina", "Depto_Mat_Ceramica")
    t.caja(x0, x1, ym, y1, 0.0, TINA_BASE)                          # fondo
    t.caja(x0, x1, y1 - s * pa, y1, TINA_BASE, TINA_ALTO)           # faldón frontal
    t.caja(x0, x1, ym, ym + s * pa, TINA_BASE, TINA_ALTO)           # borde contra el muro
    for xa, xb in ((x0, x0 + pa), (x1 - pa, x1)):                   # bordes laterales, a tope (sin traslapes)
        t.caja(xa, xb, ym + s * pa, y1 - s * pa, TINA_BASE, TINA_ALTO)
    t.crear(col)


def inodoro(col, bid, wc, repisa):
    wx0, wx1, wy0, wy1 = wc["bbox"]
    d = -1 if wc["muro"] == "E" else +1                              # del muro del estanque hacia el baño
    muro_x = wx1 if wc["muro"] == "E" else wx0
    wyc = (wy0 + wy1) / 2
    pz = Pieza(f"Depto_Sanitario_{bid}_WC", "Depto_Mat_Ceramica")
    if wc["estanque"] == "oculto":                                   # B1: estanque dentro de la repisa
        assert repisa is not None, f"{bid}: estanque oculto sin repisa"
        fondo = repisa[0] if d < 0 else repisa[1]
    else:
        fondo = muro_x + d * px(WC["estanque_fondo"])
        pz.caja(muro_x, fondo, wyc - px(WC["estanque_ancho"]) / 2, wyc + px(WC["estanque_ancho"]) / 2,
                *WC["estanque_z"])
    pz.caja(fondo + d * px(0.20), fondo, wyc - px(0.11), wyc + px(0.11), 0.0, WC["pedestal_alto"])   # pedestal
    rx = px(WC["taza_largo"]) / 2
    pz.cilindro(fondo + d * rx, wyc, rx, px(WC["taza_ancho"]) / 2, WC["pedestal_alto"], WC["taza_alto"], seg=20)
    pz.crear(col)


def vanitorio(col, bid, v):
    vx0, vx1, vy0, vy1 = v["bbox"]
    lado, muro_y = v["muro"]
    assert (lado == "S" and abs(vy1 - muro_y) < 1e-6) or (lado == "N" and abs(vy0 - muro_y) < 1e-6), \
        f"{bid}: el muro del vanitorio no coincide con el borde del bbox"
    sv = 1 if lado == "S" else -1                                    # del frente hacia el muro, en y
    frente = vy0 if lado == "S" else vy1
    libre_e = v["libre"] == "E"
    z0, z1 = VANITORIO_Z
    cuerpo = Pieza(f"Depto_Sanitario_{bid}_Vanitorio", "Depto_Mat_MuebleBlanco")
    cuerpo.caja(vx0, vx1, frente + sv * px(VANITORIO_RETRANQUEO), muro_y, 0.08, z0)
    zx0, zx1 = (vx0, vx1 - px(0.03)) if libre_e else (vx0 + px(0.03), vx1)
    cuerpo.caja(zx0, zx1, frente + sv * px(0.07), muro_y, 0.0, 0.08)   # zócalo retranqueado al frente y al extremo libre
    cuerpo.crear(col)
    c = Pieza(f"Depto_Sanitario_{bid}_Cubierta", "Depto_Mat_CubiertaBano")
    c.caja(vx0, vx1, vy0, vy1, z0, z1)
    c.caja(vx0, vx1, muro_y - sv * px(0.02), muro_y, z1, z1 + RESPALDO_ALTO)   # respaldo
    c.crear(col)
    L = LAVAMANOS
    cx = (vx0 + vx1) / 2
    cy = muro_y - sv * px(L["al_muro"] + L["ry"])
    Pieza(f"Depto_Sanitario_{bid}_Lavamanos", "Depto_Mat_Ceramica").cuenco(
        cx, cy, px(L["rx"]), px(L["ry"]), z1, z1 + L["alto"], L["pared"], L["fondo"], seg=24).crear(col)
    K = LLAVE
    ly = muro_y - sv * px(K["al_muro"])
    llave = Pieza(f"Depto_Sanitario_{bid}_Llave", "Depto_Mat_Acero")
    llave.cilindro(cx, ly, px(K["radio"]), px(K["radio"]), z1, z1 + K["alto"], seg=12)
    ca, cb = sorted((ly - sv * px(K["radio"]), ly - sv * px(K["cano"])))
    llave.caja(cx - px(0.012), cx + px(0.012), ca, cb, z1 + K["alto"] - 0.02, z1 + K["alto"])   # caño hacia la cubeta
    llave.crear(col)
    Pieza(f"Depto_Sanitario_{bid}_Espejo", "Depto_Mat_Espejo").caja(
        vx0 + px(0.03), vx1 - px(0.03), muro_y - sv * px(0.01), muro_y, *ESPEJO_Z).crear(col)


def sanitarios(col):
    for bid, b in BANOS.items():
        tina(col, bid, *b["tina"])
        rep = b.get("repisa")
        inodoro(col, bid, b["wc"], rep)
        if rep:
            rx0, rx1, ry0, ry1, rz = rep
            Pieza(f"Depto_Sanitario_{bid}_Repisa", "Depto_Mat_Yeso").caja(rx0, rx1, ry0, ry1, 0.0, rz).crear(col)
            wyc = (b["wc"]["bbox"][2] + b["wc"]["bbox"][3]) / 2
            Pieza(f"Depto_Sanitario_{bid}_Pulsador", "Depto_Mat_Acero").caja(
                rx0 - px(0.01), rx0, wyc - px(0.10), wyc + px(0.10), rz - 0.20, rz - 0.05).crear(col)
        if "ducto" in b:
            dx0, dx1, dy0, dy1, dz = b["ducto"]
            Pieza(f"Depto_Sanitario_{bid}_Ducto", "Depto_Mat_Yeso").caja(dx0, dx1, dy0, dy1, dz, H).crear(col)
        vanitorio(col, bid, b["vanitorio"])


# ---------------------------------------------------------------------------
# Pruebas
# ---------------------------------------------------------------------------
def pruebas(root, objs_fase, hojas, ventanal_u):
    fallos = []
    bpy.context.view_layer.update()
    visibles = [o for o in root.all_objects if o.type == "MESH" and not o.hide_render
                and not o.name.startswith("Depto_Ref")]
    # 1) Cada hoja cerrada (su malla sin giro, en el origen de la bisagra) queda dentro de su vano.
    for ob, eje, a, b, c0, c1 in hojas:
        pts = [v.co + ob.location for v in ob.data.vertices]
        x0, x1, y0, y1 = G.rect_bl(*uw(eje, a, b, c0, c1))
        bb = G.aabb(pts)
        if bb[0] < x0 - 1e-6 or bb[1] > x1 + 1e-6 or bb[2] < y0 - 1e-6 or bb[3] > y1 + 1e-6:
            fallos.append(f"hoja cerrada fuera de su vano: {ob.name}")
    # 2) Interferencias: piezas de esta fase contra muros, losas y otras piezas (salvo dentro del mismo objeto).
    #    Con cajas envolventes de mundo, que para una hoja girada son conservadoras. Una hoja y sus manillas
    #    (hijas) se comparan en el marco local de la hoja, cerrada: ahí son cajas exactas que sólo se tocan.
    propios = G.solidos([o for o in objs_fase if not o.hide_render])
    ajenos = G.solidos([o for o in visibles if o not in objs_fase])
    fallos += G.interferencias(propios, ajenos, TOL_PENETRACION)
    for ob, *_ in hojas:
        loc = lambda o: [G.aabb(isla) for isla in G.islas_locales(o)]  # noqa: E731
        for hijo in ob.children:
            for A in loc(ob):
                for B in loc(hijo):
                    if G.penetracion(A, B) > TOL_PENETRACION:
                        fallos.append(f"interferencia {ob.name} / {hijo.name} (cerrada): "
                                      f"{G.penetracion(A, B) * 1000:.1f} mm")
    # 3) Cámaras de ambiente a >= HOLGURA_CAMARA de todo sólido visible.
    todos = propios + ajenos
    f_cam, holguras = G.holgura_camaras(todos, HOLGURA_CAMARA)
    fallos += f_cam
    # 4) Ventanal: paso libre a 1,0 m en el paño norte; el paño fijo sí está cerrado.
    u_libre, u_fijo = ventanal_u
    v = VENTANAL

    def cruza(u):
        p0, p1 = mundo("y", u, v["c0"] - 5, 1.0), mundo("y", u, v["c1"] + 5, 1.0)
        return [o.name for o, c in todos if G.segmento_cruza(c, p0, p1)]
    if cruza(u_libre):
        fallos.append(f"ventanal: el paso libre está obstruido por {cruza(u_libre)}")
    if not any("Vidrio" in n for n in cruza(u_fijo)):
        fallos.append("ventanal: el paño fijo no tiene vidrio")
    # 5) Presupuesto de la escena visible.
    total = 0
    for o in visibles:
        o.data.calc_loop_triangles()
        total += len(o.data.loop_triangles)
    if total > 150_000:
        fallos.append(f"presupuesto de triángulos excedido: {total}")
    return fallos, holguras, total


def main():
    scene = bpy.context.scene
    SE.exigir(scene, "02", bpy.data.filepath)
    root = bpy.data.collections["Depto"]
    cols = G.colecciones_fase(root, COLS)
    hojas = puertas(cols["Depto_Aberturas"])
    ventanas(cols["Depto_Aberturas"])
    ventanal_u = ventanal(cols["Depto_Aberturas"])
    baranda_vidrio(cols["Depto_BalconDetalle"])
    palier(cols["Depto_Palier"])
    closets(cols["Depto_Fijos"])
    cocina(cols["Depto_Fijos"])
    nicho_lavadora(cols["Depto_Fijos"])
    sanitarios(cols["Depto_Sanitarios"])

    objs = [o for n in COLS for o in bpy.data.collections[n].all_objects]
    fallos, holguras, total = pruebas(root, objs, hojas, ventanal_u)
    for f in fallos:
        print("FALLA", f)
    print("CHECK holgura de cámaras (m):", holguras)
    if fallos:
        raise SystemExit(f"ERROR: {len(fallos)} pruebas de la fase 3 fallan; no se guarda el maestro.")
    tris = 0
    for o in objs:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    SE.sellar(scene, "03")
    bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
    print(f"CHECK fase 3: {len(objs)} objetos, {tris} triángulos; escena visible {total} triángulos; "
          f"{len(hojas)} hojas cerradas en su vano; sin interferencias > {TOL_PENETRACION * 1000:.0f} mm")
    print(f"FASE_OK Depto_03_formas {len(objs)} {tris} sello={scene['depto_fase03']}")


if __name__ == "__main__":
    main()
