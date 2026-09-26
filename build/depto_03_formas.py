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
import random
import sys
import zlib

import bpy
from mathutils import Matrix, Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import deco_base as B_  # noqa: E402
import deco_interiores as DI  # noqa: E402
import depto_geom as G  # noqa: E402
import depto_plano as P  # noqa: E402
import depto_sellos as SE  # noqa: E402
from depto_geom import Pieza, px  # noqa: E402

X, Y = P.X, P.Y
S = P.M_POR_PX               # metros por píxel del plano (px(m) = m / S es la inversa)
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
# Manilla de palanca (corrección 07b, ronda 2; diseño, en la línea de los tiradores de barra negros): roseta Ø 0,05 ×
# 0,008, cuello Ø 0,016 que sale 0,052 de la hoja y palanca de 0,12 × 0,018 × 0,010 con las puntas redondeadas, hacia
# la bisagra, con el eje a 0,06 del canto libre (entrada estándar de cerradura tubular). Antes era un bloque de
# 0,12 × 0,06 × 0,02 pegado a la hoja, que desentonaba junto a los interruptores de tornillos y balancín.
MANILLA = dict(roseta=(0.025, 0.008), cuello=(0.008, 0.052), palanca=(0.12, 0.018, 0.010), eje_desde_canto=0.06)
# Ángulo de las hojas abiertas. D1 y D2: a 90° la manilla del lado de la bisagra toca el tabique T3 (≈86°),
# así que quedan a 84°. B1 y B2: del lado de la bisagra no hay muro (la tina queda a 0,07 m de la manilla) y a
# 90° la hoja deja 0,61 m de paso frente a la jamba opuesta; a 84° dejaba 0,53 (recorrido de 0,25 m: no pasa).
# Entrada (corrección 07c, ronda 1): el plano la dibuja abierta a 90° a lo largo de T9. La hoja queda donde la dibuja
# (su cara sur a 3,2 cm de T9), pero la manilla de palanca sale 6,2 cm de esa cara: a 90° entra 15 mm en T9 y a 88°,
# 1 mm; a 87° queda a 13 mm (tope de puerta, diseño). El tope de 84° de la ronda 0 se atribuía al reloj del hall, que
# ahora está fuera del barrido; la desviación de −3° va en la tabla de la bitácora.
ANGULO_ABIERTA = dict(D1=84.0, D2=84.0, B1=90.0, B2=90.0, Entrada=87.0)
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
# Contenido de los clósets (fase "07 detalle interactivo", 07b; diseño, no lo mide el plano): cascarón interior
# de melamina blanca con costados (las celdas van de tabique a tabique), repisa maletero y contenido de
# build/deco_interiores.py. Las celdas "_Norte" (~0,61 m de fondo) son de colgar: D1 (principal) con una barra
# larga (abrigo y vestidos hasta ~0,8 m del piso) y D2 (segundo) con barra doble (camisas arriba, pantalones
# abajo). Las "_Sur" (~0,46 m) son de repisas, en dos columnas: la izquierda con cajones abajo, que caben en el
# vano que deja la hoja A corrida (un cajón más ancho chocaría con la hoja que sigue delante), y la derecha con
# zapatos y ropa doblada. D1 en crudo/azul/vino/camel, D2 en gris/verde/carbón/denim y más informal.
CLOSET_PANEL_ESP = 0.018     # supuesto: costados, fondo, piso, techo y repisas del cascarón (melamina 18 mm)
CLOSET_RETRANQUEO = 0.012    # diseño: repisas y cajones 12 mm detrás de la cara interior de las hojas
CLOSET_BARRA_R = 0.011       # supuesto: barra de colgar, tubo de acero de 22 mm
CLOSET_ALTURAS = {           # diseño (m): repisa maletero y barras de colgar de las celdas de colgar
    "D1": dict(repisa=1.93, barras=(1.84,)),                 # barra única (ropa larga): 1,84 es alcanzable
    "D2": dict(repisa=2.06, barras=(1.97, 0.99)),            # barra doble: 1,97 arriba y 0,99 abajo
}
CLOSET_CAJON_ALTO = 0.18     # diseño: frente de cada cajón interior
CLOSET_CAJON_JUNTA = 0.004   # diseño: junta entre frentes de cajón
CLOSET_CAJONES = {"D1": 2, "D2": 3}   # diseño: cajones que caben en la columna de la hoja A (CLOSET_CAJON_ALTO +
                                      # junta cada uno) bajo la primera repisa: 2 en D1 y 3 en D2
CLOSET_CAJON_RECORRIDO = 0.27         # diseño (corrección 07c; antes 0,30 sin origen): 3/4 del hondo del cajón (0,356 m
                                      # en D1_Sur y 0,357 en D2_Sur), la extensión de una corredera parcial de cajón.
                                      # El cajón es del ancho interior de la columna que libera la hoja A al correrse
                                      # (del costado al divisor, que queda 1 cm antes del canto de la hoja A corrida y
                                      # 2,8 cm antes del de la hoja B cerrada): abierto sale por ese vano, asoma ≈ 0,21 m
                                      # del frente y su fondo sigue 0,10 m detrás de los rieles. Lo prueba closets() y,
                                      # con las hojas en el estado del contrato (A corrida, B cerrada), depto_06.
CLOSET_REPISAS_PASO = 0.36   # diseño: distancia entre repisas de las columnas (ropa doblada de 3-5 capas)
CLOSET_COL_Z = (0.10, 1.80)  # encargo 07c: alto de Depto_Col_Closet_*, la franja del cilindro del recorrido
                             # (Z_PASO y Z_CABEZA de build/depto_recorrido.py)
MALETERO_CAJA = (0.36, 0.34, 0.22)      # diseño: caja de guardado de tela (~27 L: ancho, hondo, alto) en el maletero
MALETERO_MANTAS = (0.36, 0.34, 3, 0.06)  # diseño: pila de mantas (ancho, hondo, capas, alto de capa)
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
HORNO_Z = (0.75, 1.35)                   # supuesto: nicho del horno empotrado en la torre (horno de 0,60 m)
TORRE_COSTADO = 0.018                    # supuesto: costados, fondo, piso, techo y entrepaños de la torre (melamina)
# Torre como mueble (corrección 07c, ronda 1; inferido: el plano sólo da la huella, con rayado interior y un símbolo de
# dos hojas en su frente). Zócalo retranqueado como el resto de la cocina, puerta bajo el horno (0,10-0,75) con una
# repisa para bandejas, horno con marco de acero, vidrio, franja de mandos y manilla de barra, y puerta de despensa
# arriba (1,35-2,10) con dos repisas. Las dos puertas llevan la bisagra al sur (del lado de la nevera): con la bisagra
# al norte chocaban, abiertas, con el tirador de PuertaLavaplatos2 o de PuertaAltaE3, que sobresale 7 cm delante de la
# torre. Al sur, a 90° la hoja entra en la puerta de la nevera abierta a 100°: se detienen a ANGULO_TORRE.
ANGULO_TORRE = 80.0                      # diseño: a 80° el tirador queda a ~5 cm de la cara de la nevera abierta a
                                         # 100° (a 85° quedaba a 7 mm; a 90° chocaban). Lo verifica prueba_aperturas
TORRE_REPISA_BAJA = 0.42                 # diseño: repisa bajo el horno (bandejas abajo, fuentes y tabla arriba)
TORRE_REPISAS_DESPENSA = (1.605, 1.845)  # diseño: dos repisas en la despensa (tres niveles de ~0,22 m)
TORRE_RETRANQUEO_REPISA = 0.02           # diseño: repisas 2 cm detrás de la cara interior de la puerta
HORNO = dict(marco=0.020, sale=0.002, vidrio=0.004, margen=0.035, z_vidrio=(0.775, 1.235),
             z_mandos=(1.255, 1.330), perilla_r=0.017, perilla_sale=0.022, perilla_desde=0.08,
             manilla_r=0.008, manilla_sale=0.045, manilla_largo=0.46, manilla_z=1.205)
# supuesto: horno empotrable de 0,60 m (catálogo usual): marco de acero cepillado de 2 cm al ras de los frentes (2 mm
# por delante), puerta de vidrio negro con 3,5 cm de marco a la vista, franja de mandos de 7,5 cm arriba con dos
# perillas, y manilla de barra Ø 16 mm de 0,46 m a 4,5 cm de la puerta (encargo 07c: «4-5 cm»)
# Mueble bajo el lavaplatos (corrección 07c, ronda 1): cascarón hueco en vez del bloque macizo, con el rincón ciego de
# la esquina macizo (de T5 al canto norte de la hoja 1).
LAVA_TRAVESANO = (0.06, 0.08)            # supuesto: travesaño frontal bajo la cubierta (fondo, alto)
LAVA_MONTANTE = 0.06                     # diseño: fondo del montante de 18 mm en la junta de las dos hojas, donde se
                                         # atornilla la bisagra de la hoja 1 (un divisor de todo el fondo cortaría el
                                         # sifón, que baja al centro de la cubeta, a 1 cm de la junta)
SIFON = dict(r_tubo=0.020, r_botella=0.034, z_botella=(0.40, 0.58), z_salida=0.53, r_roseta=0.032)
# supuesto: sifón de botella cromado de 1 1/2" (Ø 40 mm) bajo el centro de la cubeta, con la salida horizontal al muro
# (roseta en el fondo del mueble) y la válvula con canastillo en el fondo de la cubeta
BASURERO = (0.24, 0.26, 0.40)            # supuesto: basurero de ~22 L con tapa (ancho, hondo, alto)
ANAFE = (326.0, 358.0, 155.0, 178.4)     # medido (re-medición fase 3): centros del contorno (x0, x1, y0, y1)
BACHA = (390.9, 413.0, 193.7, 218.1)     # medido (re-medición fase 3): centros del contorno del lavaplatos; la
                                         # extracción (392,5-416) estaba corrida 2-3 px al este
BACHA_REBORDE = 0.015                    # supuesto
BACHA_PROF, BACHA_PARED = 0.18, 0.008    # supuesto: cubeta de acero
ESCURRIDOR = (393.0, 411.0, 172.0, 188.0)  # extracción: rectángulo con líneas verticales junto al lavaplatos
# Nevera (corrección 07c): ancho y frente medidos en el plano; antes REFRI = (0,60, 0,60, 1,80), todo inferido.
NEVERA_Y = (261.5, 296.0)                # medido en plano: centros de los trazos norte y sur del contorno gris del
                                         # refrigerador (x 393-412; sondas "cocina nevera" de verificar_lineas.py):
                                         # 34,5 px = 0,656 m de ancho, en el nicho de 0,76 entre la torre y T_COC_S
NEVERA_FRENTE_X = 386.7                  # medido en plano: centro de la discontinua de su frente (convención de
                                         # "equipo no incluido", brief), al ras del frente de la torre (COC_FRENTE_X)
REFRI_ALTO = 1.80                        # inferido (brief)
REFRI_HOLGURA = 0.02                     # supuesto: separación al muro. El contorno dibujado termina 0,07 m antes
                                         # del forro (x ≈ 414,5) y mide 0,46 m de fondo: se lee como el símbolo del
                                         # equipo, no su fondo (con la holgura de 0,02 el fondo queda en 0,58, inferido)
# Corrección 07c: muebles altos en L, como marca el plano (discontinuas ALTOS_Y del tramo norte y ALTOS_X del este,
# que siguen de T3 a la torre y cruzan sobre el anafe). La versión 2 había dejado el norte con repisas abiertas y una
# campana de chimenea; ahora la campana es telescópica, integrada en el módulo del mueble alto sobre el anafe.
ALTOS_RELLENO = 0.05                     # supuesto: rellenador contra T3 y a cada lado de la esquina de la L (el
                                         # mismo RELLENO_ESQUINA de los muebles base): así las hojas vecinas abren a
                                         # ANGULO_MUEBLE sin entrar en el muro ni en la hoja o el tirador del otro tramo
CAMPANA = dict(ancho=0.60, alto=0.18, visera=0.045, filtro=0.003)   # diseño: campana telescópica en el módulo de
                                         # 0,60 centrado sobre el anafe (el de las campanas de mercado): motor de 0,18
                                         # de alto, visera de acero cepillado al ras de las hojas, filtro abajo y frente
                                         # fijo encima (detrás van el motor y el ducto). Su cara inferior es la de los
                                         # altos (ALTOS_Z[0]): 0,59 m sobre el vidrio del anafe (los fabricantes suelen
                                         # pedir 0,60-0,65 en anafes eléctricos: valor de memoria, sin verificar)
SALPICADERO_ESP = 0.005                  # supuesto: azulejo sobre el muro, del mesón a la cara inferior de los altos
TIRADOR = dict(largo_max=0.32, seccion=0.012, separacion=0.035, desde_borde=0.045)   # supuesto: barra de 12 mm
MODULO_BASE = 0.60                       # supuesto: ancho de frentes de mueble base
MODULO_BACHA = 0.40                      # supuesto: bajo el lavaplatos, dos puertas de 0,40 (mueble de 0,80)
MODULO_ALTO = 0.40                       # supuesto
# Cocina: cajones y puertas interactivos, y contenido (fase "07 detalle interactivo"). Frentes que ya no se
# reparten con frentes()/tiradores() (los tramos base y alto de MODULO_BASE/MODULO_ALTO): los base se
# reconstruyen como cajones reales (salvo bajo el lavaplatos, que queda como puerta de bisagra), y los altos como
# puertas de bisagra, cada uno un objeto interactivo con su tirador.
CAJON_ESP = 0.018                        # supuesto: melamina de 18 mm (frente, laterales, fondo, piso)
CAJON_RECORRIDO = 0.40                   # diseño: recorrido de los cajones base (0,35-0,45 m del encargo)
CAJON_PROF_BASE = 0.52                   # supuesto: hondo del cajón (algo menos que el mueble, 0,60 - frente)
ALTO_CAJON_SUP = 0.16                    # diseño: cajón angosto superior (bandeja de cubiertos)
JUNTA_CAJONES = 0.006                    # supuesto: reveal entre los dos cajones apilados de un mismo módulo
ANGULO_MUEBLE = 95.0                     # diseño: puertas de mueble (90-100°) que no sean cajones
ANGULO_MUEBLE_TORRE = 90.0               # diseño (corrección 07c): la hoja del mueble alto con la bisagra junto a la
                                         # torre se detiene al quedar paralela a su cara (a 1,5 mm)
ALTOS_ESP = 0.018                        # supuesto: costados/piso/techo del mueble alto (cascarón hueco)
# ---------------------------------------------------------------------------
# Nevera (fase "07 detalle interactivo"): reemplaza el bloque macizo REFRI por un cuerpo hueco de acero cepillado,
# con puerta principal de bisagra (interactiva) y cajón freezer abajo (interactivo). Freezer abajo: diseño
# (estilo «French door» de mercado; el brief sólo pedía el volumen REFRI).
# ---------------------------------------------------------------------------
NEVERA_ZOCALO = 0.08                     # supuesto: zócalo bajo la nevera, a ras del de la cocina
NEVERA_ESP = 0.020                       # supuesto: chapa + aislación de costados, fondo, techo y piso
NEVERA_ESP_PUERTA = 0.045                # supuesto: espesor de la puerta y el cajón freezer (con aislación)
NEVERA_JUNTA = 0.010                     # supuesto: junta oscura entre el freezer y la puerta principal
NEVERA_HOLGURA_LADO = 0.008              # supuesto: reveal entre la puerta/cajón y el cuerpo
NEVERA_FREEZER_ALTO = 0.42               # diseño: alto interior del cajón freezer
NEVERA_ANGULO_PUERTA = 100.0              # diseño: abre bastante para mostrar el interior. Con la bisagra al norte
                                          # (corrección 07c) la hoja abierta queda en la cocina, delante de la torre,
                                          # y la boca entre el hall y la cocina queda libre (pruebas de aperturas y de
                                          # recorrido de la fase 6, sin excepción para la nevera).
NEVERA_RECORRIDO_FREEZER = 0.36          # diseño: cuánto sale el cajón freezer
NEVERA_CAJON_PROF = 0.50                 # supuesto: hondo del cajón freezer (deja margen contra el fondo)
NEVERA_MANILLA = dict(seccion=0.016, sobresale=0.045, margen=0.16)  # supuesto: manilla de barra vertical
NEVERA_FORRO_ESP = 0.010                 # supuesto: forro interior blanco (puerta y cuerpo)
NEVERA_ESTANTE_ESP = 0.006               # supuesto: estante de vidrio
NEVERA_ESTANTES_Z = (0.40, 0.78)         # diseño: dos estantes de vidrio dentro del compartimento principal
NEVERA_CAJON_VERDURA_ALTO = 0.16         # supuesto: cajón de verduras (no interactivo: se ve al abrir la puerta)
NEVERA_BALCON_ALTO = 0.09                # supuesto: balcones de la contrapuerta
NEVERA_BALCONES_Z = (0.22, 0.72)         # diseño: balcón bajo (botellas altas, 0,41 m libres) y alto (salsas)
NEVERA_LACTEOS_Z = 1.02                  # diseño: compartimento de lácteos con tapa, arriba en la contrapuerta
PLASTICO_ESMERILADO = "Depto_Mat_PlasticoEsmerilado"   # corrección 07b: frente del cajón de verduras, tapa de
                                                        # lácteos y táperes (el vidrio esmerilado dejaba ver nítido)
TAPA_AZUL = ("Depto_Mat_Alimento", "Depto_Mat_RopaAzul")          # tapas y bandejas de plástico teñidas
TAPA_CELESTE = ("Depto_Mat_Alimento", "Depto_Mat_RopaCeleste")

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
# Versión 2: lavamanos, grifería y espejo son piezas de la decoración (build/deco_cocina_bano.py, fase 4).

TOL_PENETRACION = 0.001          # m: dos piezas no pueden solaparse más que esto en los tres ejes
TOPE_TRIANGULOS = G.TOPE_TRIANGULOS
HOLGURA_CAMARA = 0.20            # m: distancia mínima (3D) de cada cámara de ambiente a todo sólido


def uw(eje, u0, u1, w0, w1):
    """(u a lo largo del muro, w a través) -> (x0, x1, y0, y1) del plano."""
    return (u0, u1, w0, w1) if eje == "x" else (w0, w1, u0, u1)


def mundo(eje, u, w, z=0.0):
    x, y = (u, w) if eje == "x" else (w, u)
    return Vector((*P.a_blender(x, y), z))


# ---------------------------------------------------------------------------
# Ayudas genéricas para piezas móviles fuera de la tabla PUERTAS (versión 2, fase "07 detalle interactivo": nevera,
# cocina, clósets). Mismo patrón que puertas()/ventanal(): se arman en su posición final de mundo (px en el plano,
# m en z), con el origen en la bisagra o el punto de reposo, para que el visor las abra sin tocar la geometría.
# ---------------------------------------------------------------------------
def _bisagra(col, nombre, mat, eje, u0, u1, w0, w1, z0, z1, ub_bisagra, cara_bisagra, sentido,
             angulo_abierta_deg, abierta, props):
    """Hoja rectangular de bisagra genérica (mueble, clóset, nevera): caja u0..u1 (a lo largo de eje), w0..w1 (a
    través), z0..z1. `cara_bisagra` debe ser w0 o w1 (la cara donde queda el eje de giro); `ub_bisagra`, u0 o u1
    (el extremo con la bisagra). `sentido`: +1/-1, hacia qué lado de cara_bisagra se abre. Devuelve (objeto,
    pivote de mundo); origen en la bisagra, rotation_euler.z = ángulo actual (0 = cerrada).
    Corrección 07c: cara_bisagra es la cara VISTA de la hoja (la que mira hacia donde abre), como el eje de una
    bisagra de cazoleta: abierta, la hoja queda delante de su propio vano. Con el eje en la cara de atrás, el espesor
    de la hoja barría el muro o el mueble vecino (PuertaAlta1 entraba 6,4 cm en T5)."""
    h = Pieza(nombre, mat)
    h.caja(*uw(eje, u0, u1, w0, w1), z0, z1)
    ulibre = u1 if ub_bisagra == u0 else u0
    piv = mundo(eje, ub_bisagra, cara_bisagra)
    dc = mundo(eje, ulibre, cara_bisagra) - piv
    do = mundo(eje, ub_bisagra, cara_bisagra + sentido) - piv
    signo = 1 if dc.x * do.y - dc.y * do.x > 0 else -1
    ang_max = round(angulo_abierta_deg * signo, 2)
    ang = math.radians(ang_max) if abierta else 0.0
    p = dict(props)
    p.update(puerta=nombre, abierta=abierta, angulo_deg=round(math.degrees(ang), 2), angulo_abierta_deg=ang_max)
    ob = h.crear(col, p, origen=tuple(piv))
    ob.rotation_euler.z = ang
    return ob, piv


def _corredera(col, nombre, mat, eje, u0, u1, w0, w1, z0, z1, sentido_u, recorrido_m, abierta, props):
    """Hoja corredera genérica (clóset): caja u0..u1, w0..w1, z0..z1 en su posición cerrada. Se desliza
    recorrido_m a lo largo de eje, hacia sentido_u (+1/-1). Devuelve (objeto, referencia de mundo); origen en la
    esquina de referencia (u0, w0, z0), la posición cerrada."""
    h = Pieza(nombre, mat)
    h.caja(*uw(eje, u0, u1, w0, w1), z0, z1)
    ref = mundo(eje, u0, w0, z0)
    u_abierta = u0 + sentido_u * px(recorrido_m)
    dvec = mundo(eje, u_abierta, w0, z0) - ref
    p = dict(props)
    p.update(corredera=True, abierta=abierta, recorrido_m=round(dvec.length, 4),
             eje_apertura=[round(c, 6) for c in (dvec.normalized() if dvec.length else Vector((0.0, 0.0, 0.0)))])
    ob = h.crear(col, p, origen=tuple(ref))
    ob.location = ref + (dvec if abierta else Vector((0.0, 0.0, 0.0)))
    return ob, ref


def _cajon(col, nombre, mat, eje, u0, u1, w_frente, sentido_prof, prof, z0, z1, esp, recorrido_m, abierta, props):
    """Cajón real (frente + laterales + fondo + piso, abierto arriba), en un solo objeto: ancho u0..u1 (a lo
    largo de eje, paralelo al mueble), hondo `prof` desde w_frente hacia sentido_prof (transversal, adentro del
    mueble), alto z0..z1 (paredes del cajón), tablero de espesor `esp`. Se desliza recorrido_m hacia afuera
    (transversal, en el sentido opuesto a sentido_prof: sale hacia el frente del mueble). Origen en la esquina de
    referencia (u0, w_frente, z0), la posición cerrada."""
    e = px(esp)
    wl = w_frente + sentido_prof * e                      # cara interior del frente
    wf = w_frente + sentido_prof * px(prof)               # fondo del cajón
    h = Pieza(nombre, mat)
    h.caja(*uw(eje, u0, u1, w_frente, wl), z0, z1)                        # frente
    h.caja(*uw(eje, u0, u0 + e, wl, wf), z0, z1)                          # lateral 1
    h.caja(*uw(eje, u1 - e, u1, wl, wf), z0, z1)                          # lateral 2
    h.caja(*uw(eje, u0, u1, wf - sentido_prof * e, wf), z0, z1)          # fondo
    h.caja(*uw(eje, u0, u1, w_frente, wf), z0, z0 + esp)                  # piso (z: metros, no px)
    ref = mundo(eje, u0, w_frente, z0)
    w_abierta = w_frente - sentido_prof * px(recorrido_m)                 # sale hacia afuera del mueble
    dvec = mundo(eje, u0, w_abierta, z0) - ref
    p = dict(props)
    p.update(corredera=True, abierta=abierta, recorrido_m=round(dvec.length, 4),
             eje_apertura=[round(c, 6) for c in (dvec.normalized() if dvec.length else Vector((0.0, 0.0, 0.0)))])
    ob = h.crear(col, p, origen=tuple(ref))
    ob.location = ref + (dvec if abierta else Vector((0.0, 0.0, 0.0)))
    return ob, ref


def _tramos(eje, u_ini, u_fin, w_frente, s, z0, z1, modulo):
    """Sólo los tramos (u0, u1) de frentes(), sin dejar geometría (el bmesh de prueba se descarta)."""
    tmp = Pieza("_tmp_tramos", "Depto_Mat_MuebleCocina")
    t = frentes(tmp, eje, u_ini, u_fin, w_frente, s, z0, z1, modulo)
    tmp.bm.free()
    return t


def _tirador(col, nombre, eje, u0, u1, w_cara, s, z0, z1, origen, padre, vertical=False):
    """Manilla de barra (dos soportes y la barra que los une, como tiradores()), delante de la cara w_cara, hija de
    `padre` (mismo origen que la hoja). Horizontal (cajones): centrada en u0..u1, cerca del borde superior z1.
    Vertical (puertas de bisagra): centrada en z0..z1, en el punto medio de u0..u1 (canto de la hoja)."""
    T = TIRADOR
    sec, sep = px(T["seccion"]), px(T["separacion"])
    p = Pieza(nombre, "Depto_Mat_MetalNegroMate")
    if vertical:
        zc = (z0 + z1) / 2
        largo = min(T["largo_max"], 0.6 * (z1 - z0))
        uc = (u0 + u1) / 2
        for ze in (zc - largo / 2 + T["seccion"], zc + largo / 2 - T["seccion"]):
            p.caja(*uw(eje, uc - sec / 2, uc + sec / 2, w_cara, w_cara + s * (sep - sec)),
                   ze - T["seccion"] / 2, ze + T["seccion"] / 2)
        p.caja(*uw(eje, uc - sec / 2, uc + sec / 2, w_cara + s * (sep - sec), w_cara + s * sep),
               zc - largo / 2, zc + largo / 2)                                    # barra (faltaba: corrección 07b)
    else:
        zh = z1 - T["desde_borde"]
        largo = min(px(T["largo_max"]), 0.6 * (u1 - u0))
        uc = (u0 + u1) / 2
        for ue in (uc - largo / 2 + sec, uc + largo / 2 - sec):
            p.caja(*uw(eje, ue - sec / 2, ue + sec / 2, w_cara, w_cara + s * (sep - sec)),
                   zh - T["seccion"] / 2, zh + T["seccion"] / 2)
        p.caja(*uw(eje, uc - largo / 2, uc + largo / 2, w_cara + s * (sep - sec), w_cara + s * sep),
               zh - T["seccion"] / 2, zh + T["seccion"] / 2)                     # barra (faltaba: corrección 07b)
    return p.crear(col, origen=origen, padre=padre)


# ---------------------------------------------------------------------------
# Contenido de cocina (fase "07 detalle interactivo"): bandeja de cubiertos y ollas dentro de los cajones
# (hijos del cajón: se mueven con él). La vajilla de los muebles altos está en altos_cocina() (corrección 07c).
# ---------------------------------------------------------------------------
def _bandeja_cubiertos(col, u0, u1, w_frente, w_fondo, z_piso, origen, padre):
    """Bandeja con 3 compartimentos (divisiones) y cubiertos simplificados (placas planas de acero)."""
    m = px(0.010)
    w0, w1 = sorted((w_frente, w_fondo))
    div = Pieza("Depto_Cocina_CajonCubiertosBandeja", "Depto_Mat_MuebleBlanco")
    div.caja(u0 + m, u1 - m, w0 + m, w1 - m, z_piso, z_piso + 0.004)
    n = 3
    paso = (u1 - u0 - 2 * m) / n
    for i in range(1, n):
        ud = u0 + m + i * paso
        div.caja(ud - px(0.0025), ud + px(0.0025), w0 + m, w1 - m, z_piso, z_piso + 0.032)
    div.crear(col, origen=origen, padre=padre)
    cub = Pieza("Depto_Cocina_CajonCubiertosPiezas", "Depto_Mat_Acero")
    wm = px(0.014)
    for i in range(n):
        uc0 = u0 + m + i * paso
        for j, frac in enumerate((0.32, 0.68)):
            uc = uc0 + paso * frac
            largo = px(0.15 + 0.02 * ((i + j) % 3))
            cub.caja(uc - px(0.007), uc + px(0.007), w0 + wm, w0 + wm + largo, z_piso + 0.005, z_piso + 0.010)
    cub.crear(col, origen=origen, padre=padre)


def _ollas_sartenes(col, uc, wc, z_piso, origen, padre):
    """Una olla (cilindro con dos asas cortas) y un sartén (cilindro bajo con una asa corta), apoyados en el
    piso; todo dentro de un radio chico para no tocar las paredes del cajón."""
    r_olla, r_sarten = px(0.095), px(0.105)
    ollas = Pieza("Depto_Cocina_CajonOllas", "Depto_Mat_Acero")
    uo, us = uc - px(0.12), uc + px(0.115)
    ollas.cilindro(uo, wc, r_olla, r_olla, z_piso, z_piso + 0.13, seg=16)
    ollas.cilindro(us, wc, r_sarten, r_sarten, z_piso, z_piso + 0.045, seg=16)
    ollas.crear(col, origen=origen, padre=padre)
    mangos = Pieza("Depto_Cocina_CajonMangos", "Depto_Mat_MetalNegroMate")
    mangos.caja(us + r_sarten, us + r_sarten + px(0.035), wc - px(0.014), wc + px(0.014),
                z_piso + 0.016, z_piso + 0.030)                                  # asa corta del sartén
    mangos.caja(uo - r_olla - px(0.018), uo - r_olla, wc - px(0.045), wc - px(0.028), z_piso + 0.085, z_piso + 0.105)
    mangos.caja(uo - r_olla - px(0.018), uo - r_olla, wc + px(0.028), wc + px(0.045), z_piso + 0.085, z_piso + 0.105)
    mangos.crear(col, origen=origen, padre=padre)


# ---------------------------------------------------------------------------
PUERTA_CONTRATO = {   # clase/etiqueta/recinto del contrato de interacción v2 (docs/contrato-interaccion.md)
    "D1": ("Puerta del dormitorio principal", "Dorm1"),
    "D2": ("Puerta del segundo dormitorio", "Dorm2"),
    "B1": ("Puerta del baño 1", "Bano1"),
    "B2": ("Puerta del baño 2", "Bano2"),
    "Entrada": ("Puerta de entrada", "Hall"),
}


def _manilla_palanca(bm, c, n, t):
    """Manilla de palanca de MANILLA en una cara de la hoja (m, mundo): c = punto del eje sobre la cara, n = normal
    hacia afuera de la cara, t = hacia dónde apunta la palanca (la bisagra). ≈ 180 triángulos."""
    rr, er = MANILLA["roseta"]
    rc, lc = MANILLA["cuello"]
    lp, hp, ep = MANILLA["palanca"]
    B_.tubo(bm, [c, c + n * er], rr, seg=20)                                    # roseta
    wc = lc - ep / 2                                                            # eje de la palanca (sobre la cara)
    B_.tubo(bm, [c + n * (er - 0.001), c + n * wc], rc, seg=12)                 # cuello (entra en la palanca)
    z = Vector((0.0, 0.0, 1.0))
    sec = [(math.cos(TAU_M * k / 8), math.sin(TAU_M * k / 8)) for k in range(8)]
    sec = [(math.copysign(abs(a) ** 0.6, a), math.copysign(abs(b) ** 0.6, b)) for a, b in sec]   # sección redondeada
    anillos = []
    # estaciones (distancia desde el eje hacia la punta, escala de la sección): las dos puntas redondeadas
    for d, k in ((-(rc + 0.003), 0.55), (-(rc - 0.001), 0.92), (lp - rc - 0.012, 1.0), (lp - rc - 0.004, 0.92),
                 (lp - rc, 0.55)):
        o = c + n * wc + t * d
        anillos.append([bm.verts.new(o + n * (a * k * ep / 2) + z * (b * k * hp / 2)) for a, b in sec])
    for a, b in zip(anillos[:-1], anillos[1:]):
        for i in range(8):
            j = (i + 1) % 8
            bm.faces.new((a[i], a[j], b[j], b[i])).smooth = True
    bm.faces.new(list(reversed(anillos[0]))).smooth = True
    bm.faces.new(anillos[-1]).smooth = True


TAU_M = 2 * math.pi


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
        u_eje = ulibre - du * px(MANILLA["eje_desde_canto"])
        hacia_bisagra = (mundo(eje, u_eje - du, w0) - mundo(eje, u_eje, w0)).normalized()
        for w_cara, afuera in ((w0, -1), (w1, +1)):
            n = (mundo(eje, u_eje, w_cara + afuera) - mundo(eje, u_eje, w_cara)).normalized()
            _manilla_palanca(man.bm, mundo(eje, u_eje, w_cara, MANILLA_Z), n, hacia_bisagra)
        # Giro: del sentido cerrado (bisagra -> canto libre) hacia el lado en que abre, en coordenadas de mundo.
        dc, do = mundo(eje, ub + du, cara) - piv, mundo(eje, ub, cara + sentido) - piv
        signo = 1 if dc.x * do.y - dc.y * do.x > 0 else -1
        ang_max = ANGULO_ABIERTA.get(pid, 90.0) * signo          # la entrada (cerrada) abre a 87°
        ang = math.radians(ang_max) if abierta else 0.0
        etiqueta, recinto = PUERTA_CONTRATO[pid]
        ob = h.crear(col, {"puerta": pid, "abierta": abierta, "angulo_deg": round(math.degrees(ang), 2),
                           "angulo_abierta_deg": ang_max, "bisagra": "origen, eje Z",
                           "clase": "puerta", "etiqueta": etiqueta, "recinto": recinto},
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
                        "eje_apertura": list((dvec.normalized() if dvec.length else Vector((0, 0, 0)))[:]),
                        "clase": "ventana", "etiqueta": "Ventanal del living", "recinto": "Living"},
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


# ---------------------------------------------------------------------------
# Clósets (versión 07b): puertas correderas, cascarón interior y contenido de build/deco_interiores.py.
# ---------------------------------------------------------------------------
BLANCO_CLOSET = "Depto_Mat_MuebleBlanco"
# Ropa colgada: (tipo, material[, largo]) en el orden de la barra, de izquierda a derecha mirando el clóset.
CLOSET_COLGADO = {
    "D1": [[("abrigo", "Depto_Mat_RopaCamel"), ("vestido", "Depto_Mat_RopaVino"), ("vestido", "Depto_Mat_RopaNegro", 0.95),
            ("chaqueta", "Depto_Mat_RopaCarbon"), ("camisa", "Depto_Mat_RopaBlanco"),
            ("camisa", "Depto_Mat_RopaCeleste"), ("camisa", "Depto_Mat_RopaCrudo"), ("camisa", "Depto_Mat_RopaAzul", 0.72),
            ("sueter", "Depto_Mat_RopaGris"), ("pantalon", "Depto_Mat_RopaDenim"), ("pantalon", "Depto_Mat_RopaCarbon")]],
    "D2": [[("poleron", "Depto_Mat_RopaVerde"), ("chaqueta", "Depto_Mat_RopaDenim"), ("camisa", "Depto_Mat_RopaGris"),
            ("camisa", "Depto_Mat_RopaCeleste"), ("camisa", "Depto_Mat_RopaCarbon"), ("polera", "Depto_Mat_RopaNegro"),
            ("polera", "Depto_Mat_RopaCrudo"), ("camisa", "Depto_Mat_RopaVerde"), ("sueter", "Depto_Mat_RopaVino"),
            ("camisa", "Depto_Mat_RopaBlanco"), ("polera", "Depto_Mat_RopaGris"), ("camisa", "Depto_Mat_RopaAzul"),
            ("chaqueta", "Depto_Mat_RopaCarbon")],
           # pantalones con largo propio (0,52-0,64 m colgando de la barra; corrección 07b: con el mismo largo los
           # ruedos quedaban alineados al milímetro y se leían como tablas)
           [("pantalon", "Depto_Mat_RopaDenim", 0.60), ("pantalon", "Depto_Mat_RopaCarbon", 0.55),
            ("pantalon", "Depto_Mat_RopaGris", 0.63), ("pantalon", "Depto_Mat_RopaVerde", 0.52),
            ("pantalon", "Depto_Mat_RopaCrudo", 0.58), ("pantalon", "Depto_Mat_RopaDenim", 0.64),
            ("pantalon", "Depto_Mat_RopaNegro", 0.56)]],
}
# Paletas de la ropa doblada por dormitorio (cada capa elige un material de la lista).
CLOSET_DOBLADA = {
    "D1": (("Depto_Mat_RopaCrudo", "Depto_Mat_RopaGris", "Depto_Mat_RopaBlanco"),
           ("Depto_Mat_RopaAzul", "Depto_Mat_RopaDenim", "Depto_Mat_RopaCeleste"),
           ("Depto_Mat_RopaVino", "Depto_Mat_RopaCamel", "Depto_Mat_RopaCrudo")),
    "D2": (("Depto_Mat_RopaGris", "Depto_Mat_RopaCarbon", "Depto_Mat_RopaNegro"),
           ("Depto_Mat_RopaVerde", "Depto_Mat_RopaCrudo", "Depto_Mat_RopaGris"),
           ("Depto_Mat_RopaDenim", "Depto_Mat_RopaAzul", "Depto_Mat_RopaCeleste")),
}
SUELA_CLARA, SUELA_OSCURA = "Depto_Mat_SuelaClara", "Depto_Mat_CableTela"
# Zapatos por celda: (tipo, capellada, suela). Los de la celda de colgar van en el piso; los de repisas, en el
# piso y la primera repisa de la columna derecha.
CLOSET_ZAPATOS = {
    "D1_Norte": [("zapatilla", "Depto_Mat_RopaBlanco", SUELA_CLARA), ("zapato", "Depto_Mat_Cuero", SUELA_OSCURA),
                 ("taco", "Depto_Mat_RopaNegro", SUELA_OSCURA)],
    "D1_Sur": [("bota", "Depto_Mat_Zapato", SUELA_OSCURA), ("zapato", "Depto_Mat_RopaNegro", SUELA_OSCURA),
               ("zapatilla", "Depto_Mat_RopaGris", SUELA_CLARA), ("taco", "Depto_Mat_Cuero", SUELA_OSCURA)],
    # D2_Norte (corrección 07b, ronda 2): la bota al final, fuera de la barra baja de pantalones (que ocupa hasta
    # u ≈ 0,45 m); primera, su caña quedaba a 1-3 cm del ruedo del pantalón gris y se leía apoyado en ella.
    "D2_Norte": [("zapatilla", "Depto_Mat_RopaBlanco", SUELA_CLARA), ("zapatilla", "Depto_Mat_RopaCarbon", SUELA_CLARA),
                 ("bota", "Depto_Mat_Cuero", SUELA_OSCURA)],
    # D2_Sur: zapatillas en tintes claros (salvia y gris claro); en verde oscuro y denim se leían negras como el zapato
    # y la bota
    "D2_Sur": [("zapatilla", "Depto_Mat_RopaSalvia", SUELA_CLARA), ("zapato", "Depto_Mat_Zapato", SUELA_OSCURA),
               ("bota", "Depto_Mat_RopaNegro", SUELA_OSCURA), ("zapatilla", "Depto_Mat_RopaGrisClaro", SUELA_CLARA)],
}


def _marco_closet(x0, y_fondo, s):
    """Marco métrico de una celda: u a lo largo de x del plano (desde x0), v del fondo hacia el frente (desde la
    cara interior del fondo), z desde el piso. -> (Marco, función (u, v) -> (x, y) px)."""
    o = Vector((*P.a_blender(x0, y_fondo), 0.0))
    U = Vector((*P.a_blender(x0 + 1.0, y_fondo), 0.0)) - o
    V = Vector((*P.a_blender(x0, y_fondo + s), 0.0)) - o
    return DI.Marco(o, U, V), (lambda u, v: (x0 + px(u), y_fondo + s * px(v)))


def _caja_uv(pieza, a_px, u0, u1, v0, v1, z0, z1):
    (xa, ya), (xb, yb) = a_px(u0, v0), a_px(u1, v1)
    pieza.caja(min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb), z0, z1)


def _repisas(z_desde, z_hasta, paso):
    """Alturas (cara inferior) de repisas repartidas por igual entre z_desde y z_hasta, lo más cerca de `paso`."""
    n = max(1, round((z_hasta - z_desde) / paso))
    h = (z_hasta - z_desde) / n
    return [z_desde + h * k - CLOSET_PANEL_ESP for k in range(1, n)]


def closets(col):
    e, sep, j = px(PUERTA_CLOSET_ESP), px(RIEL_SEP), px(JUNTA)
    ep = px(CLOSET_PANEL_ESP)
    E = CLOSET_PANEL_ESP
    informe = {}
    for cid, x0, x1, yf, yfr in CLOSETS:
        s = 1 if yfr > yf else -1                               # sentido fondo -> frente (hacia el recinto)
        fondo_rieles = yfr - s * (2 * e + sep + px(0.005))       # cara del cuerpo detrás de los dos rieles
        did = cid.split("_")[0]                                  # "D1" | "D2"
        recinto = "Paso_D1" if did == "D1" else "Paso_D2"
        z_techo_bot = H - CLOSET_CABEZAL - CLOSET_PANEL_ESP
        # Cabezal del riel (roble, a la vista sobre las hojas) y fondo contra el muro.
        cuerpo = Pieza(f"Depto_Closet_{cid}_Cuerpo", "Depto_Mat_FrenteCloset")
        cuerpo.caja(x0, x1, fondo_rieles, yfr, H - CLOSET_CABEZAL, H)                        # cabezal (riel)
        cuerpo.crear(col)

        # Puertas correderas: dos hojas independientes, cada una con su tirador embutido (hijo). Recorrido: hasta
        # casi la mitad del ancho; corrida una, queda libre la otra mitad (con las dos corridas se cruzan).
        mid, sol = (x0 + x1) / 2, px(CLOSET_SOLAPE)
        w_ext0, w_ext1 = sorted((yfr - s * e, yfr))
        w_int = yfr - s * (e + sep)
        w_int0, w_int1 = sorted((w_int - s * e, w_int))
        recorrido_m = ((x1 - x0) / 2 - px(CLOSET_SOLAPE) - 2 * j) * S
        zt = (0.90, 1.30)
        hoja_a, ref_a = _corredera(col, f"Depto_Closet_{cid}_PuertaA", "Depto_Mat_FrenteCloset", "x",
                                   x0 + j, mid + sol / 2, w_ext0, w_ext1, LUZ_PISO, H - CLOSET_CABEZAL,
                                   +1, recorrido_m, False,
                                   dict(clase="closet", etiqueta="Puerta del clóset", recinto=recinto))
        Pieza(f"Depto_Closet_{cid}_PuertaA_Tirador", "Depto_Mat_Manilla").caja(
            x0 + px(0.03), x0 + px(0.05), yfr, yfr + s * px(0.002), *zt
        ).crear(col, origen=ref_a, padre=hoja_a)
        hoja_b, ref_b = _corredera(col, f"Depto_Closet_{cid}_PuertaB", "Depto_Mat_FrenteCloset", "x",
                                   mid - sol / 2, x1 - j, w_int0, w_int1, LUZ_PISO, H - CLOSET_CABEZAL,
                                   -1, recorrido_m, False,
                                   dict(clase="closet", etiqueta="Puerta del clóset", recinto=recinto))
        Pieza(f"Depto_Closet_{cid}_PuertaB_Tirador", "Depto_Mat_Manilla").caja(
            x1 - px(0.05), x1 - px(0.03), w_int, w_int + s * px(0.002), *zt
        ).crear(col, origen=ref_b, padre=hoja_b)

        # Cascarón interior de melamina blanca: fondo, piso, techo y costados (de tabique a tabique).
        y_fondo = yf + s * ep                                    # cara interior del fondo
        marco, a_px = _marco_closet(x0, y_fondo, s)
        W = (x1 - x0) * S
        D = abs(fondo_rieles - y_fondo) * S                      # fondo útil hasta la cara interior de las hojas
        Dr = D - CLOSET_RETRANQUEO                               # frente de repisas y cajones
        inte = Pieza(f"Depto_Closet_{cid}_Interior", BLANCO_CLOSET)
        inte.caja(x0, x1, yf, y_fondo, 0.0, H)                                              # fondo (muro)
        inte.caja(x0, x1, y_fondo, fondo_rieles, 0.0, E)                                     # piso
        inte.caja(x0, x1, y_fondo, fondo_rieles, z_techo_bot, H - CLOSET_CABEZAL)             # techo
        _caja_uv(inte, a_px, 0.0, E, 0.0, D, E, z_techo_bot)                                 # costados
        _caja_uv(inte, a_px, W - E, W, 0.0, D, E, z_techo_bot)
        rng = random.Random(zlib.crc32(cid.encode()) + 2026)
        cont = DI.Mallas()                                       # contenido suelto de la celda
        barras = []
        if cid.endswith("Norte"):
            alt = CLOSET_ALTURAS[did]
            zr = alt["repisa"]
            _caja_uv(inte, a_px, E, W - E, 0.0, Dr, zr, zr + E)                              # maletero
            for k, (zb, prendas) in enumerate(zip(alt["barras"], CLOSET_COLGADO[did])):
                ob, n, ocup = DI.barra_colgar(
                    col, f"Depto_Closet_{cid}_Barra{'' if k == 0 else 'Baja'}", marco, E, W - E, D / 2, zb, prendas,
                    semilla=zlib.crc32(f"{cid}{k}".encode()), r_barra=CLOSET_BARRA_R,
                    percha_mat="Depto_Mat_FrenteCloset" if did == "D1" else "alambre",
                    gancho_mat="Depto_Mat_Acero" if did == "D1" else "Depto_Mat_MetalNegroMate")
                ob["colision"] = False                           # la colisión es Depto_Col_Closet_* (abajo)
                barras.append((ob.name, n, ocup))
            # maletero: cajas de guardado y mantas dobladas
            z_m = zr + E
            ca, ch, cz = MALETERO_CAJA
            DI.caja_guardado(cont, 0.24, D / 2, z_m, ca, ch, cz, "Depto_Mat_RopaCrudo", "Depto_Mat_RopaCrudo")
            ma, mh, mn, mc = MALETERO_MANTAS
            DI.pila_doblada(cont, W - 0.22, D / 2 - 0.02, z_m, ma, mh, mn,
                            ("Depto_Mat_RopaCarbon", "Depto_Mat_RopaCrudo", "Depto_Mat_RopaGris"), rng, alto_capa=mc)
            # piso: zapatos en fila, puntas hacia el frente
            zs = CLOSET_ZAPATOS[cid]
            paso_u = (W - 2 * E - 0.06) / len(zs)
            for k, (tipo, cap, suela) in enumerate(zs):
                DI.par_zapatos(cont, tipo, cap, suela, E + 0.03 + paso_u * (k + 0.5), D * 0.55, E,
                               giro=rng.uniform(-2, 2))
        else:
            # Dos columnas: la izquierda cabe en el vano de la hoja A corrida (u < j + recorrido).
            u_div1 = j * S + recorrido_m - 0.010
            u_div0 = u_div1 - E
            _caja_uv(inte, a_px, u_div0, u_div1, 0.0, Dr, E, z_techo_bot)                    # divisor
            # columna izquierda: cajones abajo, cubierta y repisas
            n_caj = CLOSET_CAJONES[did]
            z_c = E + 0.003
            cajones = []
            for k in range(n_caj):
                z1c = z_c + CLOSET_CAJON_ALTO
                (xa, ya), (xb, _) = a_px(E + 0.003, Dr), a_px(u_div0 - 0.003, Dr)
                prof = Dr - 0.025
                # corrección 07c: el cajón cabe en el vano de la hoja A corrida y no llega a la B cerrada, y abierto
                # conserva su fondo detrás de los rieles (no se sale de la corredera)
                assert u_div0 - 0.003 < j * S + recorrido_m and u_div0 - 0.003 < (mid - sol / 2 - x0) * S, cid
                assert Dr - prof + CLOSET_CAJON_RECORRIDO < D, (cid, Dr, prof)
                ob_c, ref_c = _cajon(col, f"Depto_Closet_{cid}_Cajon{k + 1}", "Depto_Mat_FrenteCloset", "x",
                                     xa, xb, ya, -s, prof, z_c, z1c, 0.015, CLOSET_CAJON_RECORRIDO, False,
                                     dict(clase="cajon", etiqueta="Cajón del clóset", recinto=recinto))
                cajones.append(ob_c)
                uc = (xa + xb) / 2
                Pieza(f"Depto_Closet_{cid}_Cajon{k + 1}_Tirador", "Depto_Mat_Manilla").caja(
                    uc - px(0.06), uc + px(0.06), ya, ya + s * px(0.002), z1c - 0.030, z1c - 0.018
                ).crear(col, origen=ref_c, padre=ob_c)
                # contenido del cajón (hijo: sale con él): calcetines arriba, poleras dobladas en los demás
                dm = DI.Mallas()
                u_in0, u_in1 = E + 0.003 + 0.015, u_div0 - 0.003 - 0.015
                v_in0, v_in1 = Dr - prof + 0.015, Dr - 0.015
                zp = z_c + 0.015
                if k == n_caj - 1:
                    DI.calcetines(dm, u_in0 + 0.005, u_in1 - 0.005, v_in0 + 0.01, v_in1 - 0.01, zp,
                                  CLOSET_DOBLADA[did][0] + ("Depto_Mat_RopaNegro",), rng)
                else:
                    ancho_p = (u_in1 - u_in0 - 0.02) / 2
                    for q in range(2):
                        DI.pila_doblada(dm, u_in0 + 0.005 + ancho_p * (q + 0.5) + 0.005 * q, (v_in0 + v_in1) / 2, zp,
                                        ancho_p, min(0.28, v_in1 - v_in0 - 0.01), 2, CLOSET_DOBLADA[did][k % 3], rng,
                                        alto_capa=0.045)
                dm.crear(col, f"Depto_Closet_{cid}_Cajon{k + 1}_Ropa", marco, origen=ref_c, padre=ob_c)
                z_c = z1c + CLOSET_CAJON_JUNTA
            informe[f"{cid}_cajones"] = dict(ancho=round(u_div0 - 0.006 - E, 3), hondo=round(prof, 3),
                                             asoma=round(CLOSET_CAJON_RECORRIDO - (D + 2 * PUERTA_CLOSET_ESP + RIEL_SEP
                                                                                   + 0.005 - Dr), 3))
            # Contrato v2, sección 1 (corrección 07b): los cajones quedan detrás de las hojas. Un cajón sólo abre con
            # su hoja A corrida (depende_de) y la B cerrada; mover cualquiera de las dos hojas cierra antes los
            # cajones que tapa (bloquea). Sin esto, la hoja atravesaba el frente de un cajón abierto.
            for ob_c in cajones:
                ob_c["depende_de"] = hoja_a.name
            for hoja in (hoja_a, hoja_b):
                hoja["bloquea"] = ",".join(o.name for o in cajones)
            z_cub = z_c + 0.002
            _caja_uv(inte, a_px, E, u_div0, 0.0, Dr, z_cub, z_cub + E)                        # cubierta de cajones
            rep_izq = _repisas(z_cub + E, z_techo_bot, CLOSET_REPISAS_PASO)
            rep_der = _repisas(E, z_techo_bot, CLOSET_REPISAS_PASO)
            for z in rep_izq:
                _caja_uv(inte, a_px, E, u_div0, 0.0, Dr, z, z + E)
            for z in rep_der:
                _caja_uv(inte, a_px, u_div1, W - E, 0.0, Dr, z, z + E)
            # contenido: columna derecha, zapatos en el piso y en la primera repisa, luego ropa doblada y cajas
            zs = CLOSET_ZAPATOS[cid]
            ud0, ud1 = u_div1, W - E
            ancho_d = ud1 - ud0
            for k, (tipo, cap, suela) in enumerate(zs):
                nivel, lado = divmod(k, 2)
                z0 = E if nivel == 0 else rep_der[0] + E
                DI.par_zapatos(cont, tipo, cap, suela, ud0 + ancho_d * (0.26 + 0.48 * lado), Dr * 0.52, z0,
                               giro=rng.uniform(-2, 2))
            pal = CLOSET_DOBLADA[did]
            for n_rep, z in enumerate(rep_der[1:-1]):
                zt_ = z + E
                if ancho_d > 0.40:
                    for q in range(2):
                        DI.pila_doblada(cont, ud0 + ancho_d * (0.26 + 0.48 * q), Dr * 0.5, zt_, 0.19, 0.28,
                                        rng.randint(3, 5), pal[(n_rep + q) % 3], rng, alto_capa=0.045)
                else:
                    DI.pila_doblada(cont, (ud0 + ud1) / 2, Dr * 0.5, zt_, 0.30, 0.30, rng.randint(3, 4),
                                    pal[n_rep % 3], rng)
            z_top = rep_der[-1] + E
            DI.caja_guardado(cont, (ud0 + ud1) / 2, Dr * 0.5, z_top, min(0.38, ancho_d - 0.04), 0.32,
                             min(0.24, z_techo_bot - z_top - 0.03), "Depto_Mat_CajaZapatos")
            # columna izquierda: sobre la cubierta, sueteres gruesos; más arriba, jeans y una caja de guardado
            ui0, ui1 = E, u_div0
            for n_rep, z in enumerate([z_cub] + rep_izq[:-1]):
                zt_ = z + E
                DI.pila_doblada(cont, (ui0 + ui1) / 2, Dr * 0.5, zt_, min(0.30, ui1 - ui0 - 0.04), 0.30,
                                rng.randint(3, 5), pal[(n_rep + 1) % 3], rng, alto_capa=0.055)
            z_top = (rep_izq[-1] if rep_izq else z_cub) + E
            if did == "D1":
                DI.maleta(cont, (ui0 + ui1) / 2, Dr * 0.5, z_top, min(0.30, ui1 - ui0 - 0.04), 0.34,
                          min(0.20, z_techo_bot - z_top - 0.03), "Depto_Mat_RopaCarbon", "Depto_Mat_MetalNegroMate")
            else:
                DI.caja_guardado(cont, (ui0 + ui1) / 2, Dr * 0.5, z_top, min(0.30, ui1 - ui0 - 0.04), 0.32,
                                 min(0.22, z_techo_bot - z_top - 0.03), "Depto_Mat_RopaGris", "Depto_Mat_RopaCarbon")
        inte.crear(col)["colision"] = False
        cont.crear(col, f"Depto_Closet_{cid}_Contenido", marco, angulo=50.0, props={"colision": False})
        # Colisión de la celda (corrección 07c): una caja oculta con el mismo patrón que Depto_Col_Baranda (colision =
        # True, oculta en render, alambre) en vez de las islas de cada prenda, que ocupa toda la huella del plano: de
        # x0 a x1 y del fondo (yf) al frente (yfr, la línea gris CL*), en la franja del cilindro del recorrido. Antes
        # llegaba sólo hasta la cara del cuerpo detrás de los rieles y el frente quedaba en manos de las hojas móviles.
        cb = Pieza(f"Depto_Col_Closet_{cid}", "Depto_Mat_Colision")
        cb.caja(x0, x1, *sorted((yf, yfr)), *CLOSET_COL_Z)
        ob = cb.crear(col, {"colision": True})
        ob.hide_render = True
        ob.display_type = "WIRE"
        informe[cid] = dict(W=round(W, 3), D=round(D, 3), barras=barras)
    print("CHECK clósets:", informe)


def frentes(obj, eje, u_ini, u_fin, w_frente, s, z0, z1, modulo):
    """Frentes de mueble con juntas: a lo largo de u, en el plano w_frente, hacia afuera según s."""
    assert u_fin > u_ini, (u_ini, u_fin)
    n = max(1, round((u_fin - u_ini) / px(modulo)))
    paso = (u_fin - u_ini) / n
    j = px(JUNTA)
    tramos = []
    for i in range(n):
        u0, u1 = u_ini + i * paso + j / 2, u_ini + (i + 1) * paso - j / 2
        obj.caja(*uw(eje, u0, u1, w_frente, w_frente + s * px(FRENTE_ESP)), z0, z1)
        tramos.append((u0, u1))
    return tramos


def tiradores(obj, eje, tramos, w_cara, s, zh):
    """Tirador de barra horizontal (dos soportes y la barra) centrado en cada frente, delante de su cara w_cara."""
    T = TIRADOR
    sec, sep = px(T["seccion"]), px(T["separacion"])
    for u0, u1 in tramos:
        largo = min(px(T["largo_max"]), 0.6 * (u1 - u0))
        uc = (u0 + u1) / 2
        for ue in (uc - largo / 2 + sec, uc + largo / 2 - sec):          # soportes
            obj.caja(*uw(eje, ue - sec / 2, ue + sec / 2, w_cara, w_cara + s * (sep - sec)), zh - T["seccion"] / 2,
                     zh + T["seccion"] / 2)
        obj.caja(*uw(eje, uc - largo / 2, uc + largo / 2, w_cara + s * (sep - sec), w_cara + s * sep),
                 zh - T["seccion"] / 2, zh + T["seccion"] / 2)               # barra


def cocina(col):
    f, rel = px(FRENTE_ESP), px(RELLENO_ESQUINA)
    zc = MESON_Z - CUBIERTA_ESP
    rb = px(BACHA_REBORDE)
    hueco = (BACHA[0] + rb, BACHA[1] - rb, BACHA[2] + rb, BACHA[3] - rb)   # corte de la cubierta y cubeta
    z_fondo_cubeta = MESON_Z - BACHA_PROF
    # Muebles base: tramo norte con cajones reales (interactivos), tramo este con hueco para la cubeta y sus
    # puertas de bisagra (bajo el lavaplatos: no son cajones, brief fase 3).
    e_bn = px(CAJON_ESP)
    # Cascarón hueco (estilo europeo sin marco: los cajones llegan casi al ancho completo y sus propios
    # laterales cierran los extremos; sólo el fondo, el piso y el techo son del cuerpo, no costados de punta).
    basen = Pieza("Depto_Cocina_BaseNorteCascaron", "Depto_Mat_MuebleCocina")
    basen.caja(X["T3_E"], COC_FRENTE_X + f, Y["T5_S"], Y["T5_S"] + e_bn, ZOCALO_ALTO, zc)          # fondo (muro)
    basen.caja(X["T3_E"], COC_FRENTE_X + f, Y["T5_S"], COC_FRENTE_Y - f, ZOCALO_ALTO, ZOCALO_ALTO + CAJON_ESP)
    basen.crear(col)                          # el techo lo cierra la cubierta de arriba (sin panel propio)
    # Tramo este: rincón ciego macizo de la esquina (de T5 al canto norte de la hoja 1) y, al sur, el mueble del
    # lavaplatos como cascarón hueco (corrección 07c, ronda 1: antes era un bloque macizo con sólo el hueco de la cubeta)
    zf = (ZOCALO_ALTO, zc - 0.003)
    t_e = _tramos("y", COC_FRENTE_Y + rel, TORRE_Y[0], COC_FRENTE_X + f, -1, *zf, MODULO_BACHA)
    assert len(t_e) == 2, t_e
    Pieza("Depto_Cocina_BaseEste", "Depto_Mat_MuebleCocina").caja(
        COC_FRENTE_X + f, X["E_FORRO"], Y["T5_S"], COC_FRENTE_Y + rel, ZOCALO_ALTO, zc).crear(col)
    mueble_lavaplatos(col, COC_FRENTE_Y + rel, (t_e[0][1] + t_e[1][0]) / 2, zc, hueco, z_fondo_cubeta)
    zoc = Pieza("Depto_Cocina_Zocalo", "Depto_Mat_Zocalo")
    zr = px(ZOCALO_RETRANQUEO)
    zoc.caja(X["T3_E"], COC_FRENTE_X + zr, Y["T5_S"], COC_FRENTE_Y - zr, 0.0, ZOCALO_ALTO)
    zoc.caja(COC_FRENTE_X + zr, X["E_FORRO"], COC_FRENTE_Y - zr, TORRE_Y[1], 0.0, ZOCALO_ALTO)   # sigue bajo la torre
    zoc.crear(col)
    relle = Pieza("Depto_Cocina_Rellenos", "Depto_Mat_FrenteCocina")     # esquina de la L: no son cajón ni puerta
    relle.caja(COC_FRENTE_X - rel + px(JUNTA) / 2, COC_FRENTE_X + f, COC_FRENTE_Y - f, COC_FRENTE_Y, *zf)
    relle.caja(COC_FRENTE_X, COC_FRENTE_X + f, COC_FRENTE_Y, COC_FRENTE_Y + rel - px(JUNTA) / 2, *zf)
    relle.crear(col)
    # Cajones del tramo norte: dos por módulo (angosto arriba, profundo abajo), cada uno un objeto interactivo.
    # Corrección 07c: todos cerrados por defecto (antes el de cubiertos y el de ollas venían abiertos de fábrica); la
    # apertura para revisarlos es cosa de los renders (tools/render_detalle_interactivo.py, tools/render_07c.py).
    z_sup = (zf[1] - ALTO_CAJON_SUP, zf[1])
    z_inf = (zf[0] + CAJON_ESP, zf[1] - ALTO_CAJON_SUP - JUNTA_CAJONES)   # apoyado sobre el piso del cascarón
    CUTLERY_BAY, POTS_BAY = 0, 1
    t_n = _tramos("x", X["T3_E"], COC_FRENTE_X - rel, COC_FRENTE_Y - f, +1, *zf, MODULO_BASE)
    for i, (u0, u1) in enumerate(t_n):
        es_cubiertos, es_ollas = i == CUTLERY_BAY, i == POTS_BAY
        etq_sup = "Cajón de cubiertos" if es_cubiertos else f"Cajón {i + 1} de la cocina"
        ob_s, ref_s = _cajon(col, f"Depto_Mueble_Cocina_Cajon{i + 1}Sup", "Depto_Mat_MuebleCocina", "x", u0, u1,
                             COC_FRENTE_Y, -1, CAJON_PROF_BASE, *z_sup, CAJON_ESP, CAJON_RECORRIDO, False,
                             dict(clase="cajon", etiqueta=etq_sup, recinto="Cocina"))
        _tirador(col, f"Depto_Mueble_Cocina_Cajon{i + 1}Sup_Tirador", "x", u0, u1, COC_FRENTE_Y, +1, *z_sup,
                ref_s, ob_s)
        if es_cubiertos:
            _bandeja_cubiertos(col, u0 + px(CAJON_ESP + 0.008), u1 - px(CAJON_ESP + 0.008),
                               COC_FRENTE_Y - px(CAJON_ESP + 0.008),
                               COC_FRENTE_Y - px(CAJON_ESP) - px(CAJON_PROF_BASE) + px(0.008),
                               z_sup[0] + CAJON_ESP, ref_s, ob_s)
        etq_inf = "Cajón de ollas y sartenes" if es_ollas else f"Cajón {i + 1} profundo de la cocina"
        ob_i, ref_i = _cajon(col, f"Depto_Mueble_Cocina_Cajon{i + 1}Inf", "Depto_Mat_MuebleCocina", "x", u0, u1,
                             COC_FRENTE_Y, -1, CAJON_PROF_BASE, *z_inf, CAJON_ESP, CAJON_RECORRIDO, False,
                             dict(clase="cajon", etiqueta=etq_inf, recinto="Cocina"))
        _tirador(col, f"Depto_Mueble_Cocina_Cajon{i + 1}Inf_Tirador", "x", u0, u1, COC_FRENTE_Y, +1, *z_inf,
                ref_i, ob_i)
        if es_ollas:
            _ollas_sartenes(col, (u0 + u1) / 2, COC_FRENTE_Y - px(CAJON_ESP) - px(CAJON_PROF_BASE) / 2,
                            z_inf[0] + CAJON_ESP, ref_i, ob_i)
    # Puertas bajo el lavaplatos: bisagra (mueble). Corrección 07c: las dos con la bisagra al sur. Con la bisagra junto
    # a la esquina, la hoja 1 abierta a ANGULO_MUEBLE chocaba con los frentes y los tiradores de Cajon3 (el último del
    # tramo norte); con las dos bisagras al centro, abiertas a la vez, sus tiradores se cruzaban. La hoja 1 se atornilla
    # al montante de la junta y la 2 (excepción a la regla: bisagra junto a la torre) al costado sur del mueble; abierta
    # pasa delante de la torre, al ras de su frente, sin tocar sus puertas ni el horno.
    for i, (u0, u1) in enumerate(t_e):
        ub = u1
        ob, piv = _bisagra(col, f"Depto_Mueble_Cocina_PuertaLavaplatos{i + 1}", "Depto_Mat_FrenteCocina", "y",
                           u0, u1, COC_FRENTE_X, COC_FRENTE_X + f, zf[0], zf[1], ub, COC_FRENTE_X, -1,
                           ANGULO_MUEBLE, False,
                           dict(clase="mueble", etiqueta="Puerta bajo el lavaplatos", recinto="Cocina"))
        ul = u1 - px(0.06) if ub == u0 else u0 + px(0.06)   # manilla junto al canto libre, no al centro
        _tirador(col, f"Depto_Mueble_Cocina_PuertaLavaplatos{i + 1}_Tirador", "y", ul - px(0.02), ul + px(0.02),
                COC_FRENTE_X, -1, zf[0], zf[1], piv, ob, vertical=True)
    cub = Pieza("Depto_Cocina_Cubierta", "Depto_Mat_CubiertaConcreto")
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
    # (la grifería es de la decoración: grifo_cocina en build/deco_cocina_bano.py)
    # Muebles altos en L (corrección 07c): altos_cocina(), más abajo.
    altos_cocina(col)
    # Azulejo del mesón a la cara inferior de los altos, en los dos tramos (sobre los altos ya no se ve)
    e = px(SALPICADERO_ESP)
    sal = Pieza("Depto_Cocina_Salpicadero", "Depto_Mat_MuroBano")
    y0 = Y["T5_S"]
    sal.caja(X["T3_E"], X["E_FORRO"], y0, y0 + e, MESON_Z, ALTOS_Z[0])
    sal.caja(X["E_FORRO"] - e, X["E_FORRO"], y0 + e, TORRE_Y[0], MESON_Z, ALTOS_Z[0])
    sal.crear(col)
    torre_cocina(col)
    # La nevera (cuerpo, puerta y cajón freezer interactivos) se arma en nevera(), más abajo.


def mueble_lavaplatos(col, y0, y_junta, zc, hueco, z_fondo_cubeta):
    """Mueble bajo el lavaplatos (corrección 07c, ronda 1): cascarón hueco de y0 (canto norte de la hoja 1, contra el
    rincón ciego) a la torre, con piso, fondo, costado sur, travesaño frontal bajo la cubierta y montante en la junta
    de las hojas (bisagra de la hoja 1); sifón de botella bajo la cubeta con su salida al muro, y adentro un basurero
    (lado de la hoja 1) y productos de limpieza (lado de la hoja 2), lejos del sifón."""
    e, E = px(TORRE_COSTADO), TORRE_COSTADO
    xf0, xb, y1 = COC_FRENTE_X + px(FRENTE_ESP), X["E_FORRO"], TORRE_Y[0]
    tf, ta = LAVA_TRAVESANO
    zp = ZOCALO_ALTO + E                                                   # cara de arriba del piso
    m = Pieza("Depto_Cocina_BaseLavaplatos", "Depto_Mat_MuebleCocina")
    m.caja(xf0, xb - e, y0, y1 - e, ZOCALO_ALTO, zp)                                   # piso
    m.caja(xb - e, xb, y0, y1 - e, ZOCALO_ALTO, zc)                                    # fondo (forro)
    m.caja(xf0, xb, y1 - e, y1, ZOCALO_ALTO, zc)                                       # costado sur (bisagra de la hoja 2)
    m.caja(xf0, xf0 + px(tf), y0, y1 - e, zc - ta, zc)                                 # travesaño frontal
    m.caja(xf0, xf0 + px(LAVA_MONTANTE), y_junta - e / 2, y_junta + e / 2, zp, zc - ta)   # montante (bisagra hoja 1)
    m.crear(col)
    # sifón: marco con origen bajo el centro del desagüe, u hacia el muro (+x del plano), v según +y del plano
    xd, yd = (hueco[0] + hueco[1]) / 2, (hueco[2] + hueco[3]) / 2
    sif = DI.Mallas()
    mk = _marco_px((xd, yd), (1.0, 0.0), (0.0, 1.0))
    Sf = SIFON
    rt, rbo = Sf["r_tubo"], Sf["r_botella"]
    zb0, zb1 = Sf["z_botella"]
    u_muro = (xb - e - xd) * S
    with sif.parte("Depto_Mat_Acero", suave=True) as bm:
        B_.cilindro(bm, 0.0, 0.0, z_fondo_cubeta + BACHA_PARED, z_fondo_cubeta + BACHA_PARED + 0.003, 0.045, seg=20)
        B_.cilindro(bm, 0.0, 0.0, zb1, z_fondo_cubeta, rt, seg=14)                       # válvula y tubo de bajada
        B_.cilindro(bm, 0.0, 0.0, zb0, zb1, rbo, seg=18)                                 # botella del sifón
        B_.cilindro(bm, 0.0, 0.0, zb1 - 0.004, zb1 + 0.012, rbo + 0.004, seg=18)         # tuerca de la botella
        B_.tubo(bm, [Vector((rbo - 0.004, 0.0, Sf["z_salida"])), Vector((u_muro - 0.004, 0.0, Sf["z_salida"]))],
                rt * 0.8, seg=12)                                                        # salida horizontal al muro
        DI.cilindro_eje(bm, (u_muro - 0.004, 0.0, Sf["z_salida"]), (u_muro, 0.0, Sf["z_salida"]), Sf["r_roseta"],
                        seg=18)                                                          # roseta en el fondo
    sif.crear(col, "Depto_Cocina_Sifon", mk, props={"colision": False})
    # contenido: marco con origen en la esquina interior (frente, norte) del mueble; u según +y, v hacia el fondo
    mc = _marco_px((xf0 + px(tf), y0), (0.0, 1.0), (1.0, 0.0))
    fondo = (xb - e - xf0 - px(tf)) * S
    cont = DI.Mallas()
    bw, bd, bh = BASURERO
    u_bas = (y_junta - e / 2 - y0) * S / 2 - 0.01                                        # centrado en la hoja 1
    DI.caja_guardado(cont, u_bas, 0.03 + bd / 2, zp, bw, bd, bh, "Depto_Mat_MuebleBlanco",
                     "Depto_Mat_MetalNegroMate", tapa=0.03)
    u2 = (y_junta + e / 2 - y0) * S                                                      # comienzo del lado de la hoja 2
    for du, dv, r, alto, cuerpo, tapa in ((0.06, 0.07, 0.038, 0.27, ("Depto_Mat_Alimento", "Depto_Mat_RopaCeleste"),
                                           "Depto_Mat_MuebleBlanco"),                   # lavalozas
                                          (0.15, 0.06, 0.042, 0.30, ("Depto_Mat_Alimento", "Depto_Mat_ComidaNaranja"),
                                           "Depto_Mat_MetalNegroMate"),                 # detergente
                                          (0.25, 0.08, 0.035, 0.24, ("Depto_Mat_Alimento", "Depto_Mat_RopaVerde"),
                                           "Depto_Mat_MuebleBlanco")):                  # limpiador
        DI.botella(cont, u2 + du, dv, zp, r, alto, cuerpo, None, cuello=0.22, tapa_mat=tapa)
    DI.caja_guardado(cont, u2 + 0.16, fondo - 0.10, zp, 0.24, 0.16, 0.12, ("Depto_Mat_Alimento", "Depto_Mat_RopaAzul"))
    cont.crear(col, "Depto_Cocina_LavaplatosContenido", mc, props={"colision": False})


def torre_cocina(col):
    """Torre de horno y despensa como mueble (corrección 07c, ronda 1; antes una caja lisa de 2,10 m con una placa
    negra): cascarón hueco de melamina sobre el zócalo de la cocina, puerta bajo el horno con una repisa, horno
    empotrado y puerta de despensa con dos repisas y contenido. Las dos puertas son interactivas (clase "mueble"), con
    la bisagra al sur y tope en ANGULO_TORRE (ver la constante)."""
    e, E, f, j = px(TORRE_COSTADO), TORRE_COSTADO, px(FRENTE_ESP), px(JUNTA)
    x0, xf0, xb = COC_FRENTE_X, COC_FRENTE_X + px(FRENTE_ESP), X["E_FORRO"]
    y0, y1 = TORRE_Y
    hz0, hz1 = HORNO_Z
    t = Pieza("Depto_Cocina_Torre", "Depto_Mat_MuebleCocina")
    t.caja(xf0, xb, y0, y0 + e, ZOCALO_ALTO, TORRE_ALTO)                              # costado norte
    t.caja(xf0, xb, y1 - e, y1, ZOCALO_ALTO, TORRE_ALTO)                              # costado sur
    t.caja(xb - e, xb, y0 + e, y1 - e, ZOCALO_ALTO, TORRE_ALTO)                       # fondo (forro)
    for za_, zb_ in ((ZOCALO_ALTO, ZOCALO_ALTO + E), (hz0 - E, hz0), (hz1, hz1 + E), (TORRE_ALTO - E, TORRE_ALTO)):
        t.caja(xf0, xb - e, y0 + e, y1 - e, za_, zb_)                                  # piso, entrepaños y techo
    xr = xf0 + px(TORRE_RETRANQUEO_REPISA)
    for zr_ in (TORRE_REPISA_BAJA, *TORRE_REPISAS_DESPENSA):
        t.caja(xr, xb - e, y0 + e, y1 - e, zr_, zr_ + E)                               # repisas
    t.crear(col)
    # horno: marco de acero cepillado (UV girado: el cepillado corre a lo ancho), vidrio, franja de mandos, perillas
    Hn = HORNO
    xm = x0 - px(Hn["sale"])
    ym0, ym1 = y0 + j / 2, y1 - j / 2
    Pieza("Depto_Cocina_HornoMarco", "Depto_Mat_NeveraAcero", uv_girado=True).caja(
        xm, xf0, ym0, ym1, hz0 + JUNTA, hz1 - JUNTA).crear(col)
    xv = xm - px(Hn["vidrio"])
    mg = px(Hn["margen"])
    Pieza("Depto_Cocina_Horno", "Depto_Mat_VidrioNegro").caja(
        xv, xm, ym0 + mg, ym1 - mg, *Hn["z_vidrio"]).crear(col)
    Pieza("Depto_Cocina_HornoMandos", "Depto_Mat_VidrioNegro").caja(
        xv, xm, ym0 + mg, ym1 - mg, *Hn["z_mandos"]).crear(col)
    # perillas y manilla: marco con origen en el centro del frente del horno, u según +y del plano, v hacia afuera (-x)
    yc = (y0 + y1) / 2
    mh = _marco_px((xv, yc), (0.0, 1.0), (-1.0, 0.0))
    ph = DI.Mallas()
    zm = sum(Hn["z_mandos"]) / 2
    ua = (y1 - y0) * S / 2 - Hn["perilla_desde"]
    zh, rm, sm, lm = Hn["manilla_z"], Hn["manilla_r"], Hn["manilla_sale"], Hn["manilla_largo"]
    with ph.parte("Depto_Mat_Acero", suave=True) as bm:
        for u in (-ua, ua):
            DI.cilindro_eje(bm, (u, 0.0, zm), (u, Hn["perilla_sale"], zm), Hn["perilla_r"], seg=16)
        for u in (-lm / 2 + 0.03, lm / 2 - 0.03):                                         # soportes de la manilla
            DI.cilindro_eje(bm, (u, 0.0, zh), (u, sm - rm, zh), 0.006, seg=10)
        DI.cilindro_eje(bm, (-lm / 2, sm, zh), (lm / 2, sm, zh), rm, seg=14)              # barra
    ph.crear(col, "Depto_Cocina_HornoManilla", mh, props={"colision": False})   # 4,5 cm: no angosta el recorrido
    # puertas (bisagra al sur, cara vista en x0, tirador vertical junto al canto libre del norte)
    for nombre, (za_, zb_), etq in (("PuertaTorreBaja", (ZOCALO_ALTO, hz0 - JUNTA), "Puerta bajo el horno (bandejas y fuentes)"),
                                    ("PuertaDespensa", (hz1 + JUNTA, TORRE_ALTO - JUNTA), "Puerta de la despensa")):
        _hoja_alta(col, f"Depto_Mueble_Cocina_{nombre}", "y", ym0, ym1, x0, -1, (za_, zb_), ym1, etq, ANGULO_TORRE)
    # contenido (fijo): bajo el horno, bandejas y una olla; sobre la repisa, fuente de vidrio y tabla. Despensa:
    # frascos, cajas y botellas en los tres niveles. Marco con origen en la esquina interior (frente, norte).
    mt = _marco_px((xf0, y0 + e), (0.0, 1.0), (1.0, 0.0))
    W = (y1 - y0 - 2 * e) * S
    ct = DI.Mallas()
    zp = ZOCALO_ALTO + E
    with ct.parte("Depto_Mat_AceroNegro") as bm:                                          # dos bandejas de horno
        B_.caja(bm, 0.04, W - 0.04, 0.05, 0.47, zp, zp + 0.022)
        B_.caja(bm, 0.05, W - 0.05, 0.06, 0.46, zp + 0.024, zp + 0.044)
    with ct.parte("Depto_Mat_Acero", suave=True) as bm:                                   # olla grande sobre ellas
        B_.cilindro(bm, W / 2, 0.26, zp + 0.046, zp + 0.226, 0.13, seg=18)
    zr1 = TORRE_REPISA_BAJA + E
    with ct.parte("Depto_Mat_Vidrio") as bm:                                              # fuente de vidrio
        B_.caja(bm, 0.05, 0.37, 0.08, 0.30, zr1, zr1 + 0.06)
    with ct.parte("Depto_Mat_MaderaMueble") as bm:                                        # tabla de picar
        B_.caja(bm, 0.40, W - 0.03, 0.06, 0.44, zr1, zr1 + 0.022)
    niveles = (hz1 + E, TORRE_REPISAS_DESPENSA[0] + E, TORRE_REPISAS_DESPENSA[1] + E)
    for k, u in zip((0, 1, 3), (0.08, 0.19, 0.30)):                                      # frascos (nivel 1, < 0,22 m)
        r, alto, contenido = FRASCOS_DESPENSA[k]
        DI.frasco(ct, u, 0.12, niveles[0], r, alto, "Depto_Mat_Vidrio", contenido, "Depto_Mat_MaderaMueble")
    for u, tinte in ((0.43, "Depto_Mat_ComidaRoja"), (0.49, "Depto_Mat_RopaCrudo")):      # cajas de cereal y galletas
        DI.caja_guardado(ct, u, 0.18, niveles[0], 0.05, 0.19, 0.21, ("Depto_Mat_Alimento", tinte), tapa=0.008)
    for k, u in enumerate((0.07, 0.15, 0.23)):                                            # nivel 2: leche y jugo
        DI.carton(ct, u, 0.10, niveles[1], 0.07, 0.07, 0.16, "Depto_Mat_MuebleBlanco",
                  TAPA_AZUL if k < 2 else TAPA_CELESTE)
    DI.botella(ct, 0.36, 0.12, niveles[1], 0.035, 0.20, "Depto_Mat_Vidrio", "Depto_Mat_ComidaAmarilla", llenado=0.7,
               tapa_mat="Depto_Mat_MetalNegroMate")                                       # aceite
    DI.botella(ct, 0.46, 0.12, niveles[1], 0.032, 0.18, "Depto_Mat_GresNegro", None, cuello=0.35,
               tapa_mat="Depto_Mat_Acero")                                                # vinagre
    for u, tinte in ((0.10, "Depto_Mat_RopaVino"), (0.26, "Depto_Mat_CajaZapatos")):      # nivel 3: cajas de guardado
        DI.caja_guardado(ct, u, 0.20, niveles[2], 0.14, 0.30, 0.18, ("Depto_Mat_Alimento", tinte))
    ct.crear(col, "Depto_Cocina_TorreContenido", mt, props={"colision": False})


# ---------------------------------------------------------------------------
# Muebles altos en L (corrección 07c). Tramo norte de T3 a la esquina (cara vista en la discontinua ALTOS_Y) y tramo
# este de la esquina a la torre (cara vista en ALTOS_X), de ALTOS_Z[0] a ALTOS_Z[1]: cascarones huecos con un costado o
# divisor en cada canto con bisagra y en cada junta (piso, repisa media y techo partidos por módulo; ronda 1),
# rellenadores contra T3 y a cada lado de la esquina, campana telescópica en el módulo sobre el anafe y hojas de
# bisagra (clase "mueble"). Regla de bisagras de mueble (contrato, sección 1): la bisagra va del lado libre cuando se
# puede; si del lado de la bisagra hay muro, torre o esquina, se agrega un rellenador (ALTOS_RELLENO, RELLENO_ESQUINA)
# o se limita el ángulo (ANGULO_MUEBLE_TORRE, ANGULO_TORRE), y prueba_aperturas (fase 6) lo verifica. Excepciones con
# nombre: PuertaAltaN1 (bisagra del lado de T3, en el costado que queda detrás del rellenador), PuertaAltaE3 (junto a
# la torre, tope a 90°), PuertaLavaplatos2 (junto a la torre) y las dos puertas de la torre (junto a la nevera, tope a
# ANGULO_TORRE). Vajilla en los pisos y las repisas (estática: sólo se mueven las hojas).
# ---------------------------------------------------------------------------
def _marco_px(p0, du, dv):
    """Marco métrico de deco_interiores con origen en el punto p0 (px del plano); u hacia du y v hacia dv, vectores
    unitarios del plano (horizontales y perpendiculares)."""
    o = Vector((*P.a_blender(*p0), 0.0))
    U = Vector((*P.a_blender(p0[0] + du[0], p0[1] + du[1]), 0.0)) - o
    V = Vector((*P.a_blender(p0[0] + dv[0], p0[1] + dv[1]), 0.0)) - o
    return DI.Marco(o, U, V)


def _hoja_alta(col, nombre, eje, u0, u1, w_frente, s, za, ub, etiqueta, angulo=ANGULO_MUEBLE):
    """Hoja de mueble alto: FRENTE_ESP detrás de su cara vista w_frente (que mira hacia s), bisagra en la arista de esa
    cara del lado ub y tirador vertical junto al canto libre."""
    ob, piv = _bisagra(col, nombre, "Depto_Mat_FrenteCocina", eje, u0, u1, *sorted((w_frente, w_frente - s * px(FRENTE_ESP))),
                       za[0], za[1], ub, w_frente, s, angulo, False,
                       dict(clase="mueble", etiqueta=etiqueta, recinto="Cocina"))
    ul = u1 - px(0.05) if ub == u0 else u0 + px(0.05)
    _tirador(col, f"{nombre}_Tirador", eje, ul - px(0.02), ul + px(0.02), w_frente, s, za[0], za[1], piv, ob,
             vertical=True)
    return ob


FRASCOS_DESPENSA = (   # (radio, alto, contenido) de los frascos de vidrio con tapa de roble (diseño)
    (0.045, 0.20, ("Depto_Mat_Alimento", "Depto_Mat_ComidaAmarilla")),    # pasta corta
    (0.045, 0.16, ("Depto_Mat_Alimento", "Depto_Mat_RopaCrudo")),         # arroz
    (0.040, 0.24, ("Depto_Mat_Alimento", "Depto_Mat_Cuero")),             # lentejas
    (0.045, 0.18, ("Depto_Mat_Alimento", "Depto_Mat_Zapato")),            # café
)


def altos_cocina(col):
    f, e, j, rel = px(FRENTE_ESP), px(ALTOS_ESP), px(JUNTA), px(ALTOS_RELLENO)
    E = ALTOS_ESP
    z0, z1 = ALTOS_Z
    za = (z0 + 0.003, z1 - 0.003)                          # hojas y rellenadores: 3 mm de junta arriba y abajo
    z_rep = (z0 + z1) / 2                                  # cara inferior de la repisa media
    zb, zs = z0 + E, z_rep + E                             # z de apoyo: piso y repisa
    yb, yn = Y["T5_S"], ALTOS_Y                            # tramo norte: muro T5 y cara vista de las hojas
    yf = yn - f                                            # cara de atrás de las hojas = frente del cascarón
    xw, xa = X["T3_E"], ALTOS_X                            # tramo norte: de T3 a la cara vista del tramo este
    xb, xe = X["E_FORRO"], ALTOS_X                         # tramo este: forro y cara vista de las hojas
    xc = (ANAFE[0] + ANAFE[1]) / 2
    h0, h1 = xc - px(CAMPANA["ancho"]) / 2, xc + px(CAMPANA["ancho"]) / 2   # módulo de la campana, sobre el anafe
    C = CAMPANA

    # --- tramos de las hojas (sus juntas definen dónde van los costados y divisores del cascarón)
    t_l = _tramos("x", xw + rel, h0, yn, +1, *za, C["ancho"])
    t_r = _tramos("x", h1, xa - rel, yn, +1, *za, MODULO_ALTO)
    t_e = _tramos("y", yn + rel, TORRE_Y[0], xe, -1, *za, MODULO_ALTO)
    assert (len(t_l), len(t_r), len(t_e)) == (1, 2, 3), (t_l, t_r, t_e)
    jn = (t_r[0][1] + t_r[1][0]) / 2                        # junta N2/N3 (bisagra de N3): x ≈ 376,8 px
    je = [(t_e[k][1] + t_e[k + 1][0]) / 2 for k in range(2)]   # juntas E1/E2 y E2/E3 (bisagras de E1 y E2)

    # --- cascarones (corrección 07c, ronda 1): un costado o divisor de ALTOS_ESP, de alto completo, detrás de cada
    # canto con bisagra y en cada junta entre hojas, con el piso, la repisa media y el techo partidos en ellos (antes
    # las hojas N3, E1 y E2 colgaban de la nada y las repisas corrían sin apoyo 0,72 y 1,42 m). Los costados de los
    # extremos del tramo norte van al ras del canto de la hoja, detrás de su rellenador (la bisagra de N1 se atornilla
    # ahí); el hueco de 3,2 cm entre ese costado y T3 o la esquina se cierra abajo y arriba con una tira.
    cn = Pieza("Depto_Cocina_AltosNorteCascaron", "Depto_Mat_MuebleCocina")
    xo, xf_ = xw + rel, xa - rel                                                   # caras interiores de los extremos
    cn.caja(xw, xa, yb, yb + e, z0, z1)                                            # fondo (muro T5)
    cn.caja(xo - e, xo, yb + e, yf, z0, z1)                                        # costado oeste (bisagra de N1)
    cn.caja(xf_, xf_ + e, yb + e, yf, z0, z1)                                      # costado este (junto a la esquina)
    for a, b in ((xw, xo - e), (xf_ + e, xa)):                                     # tiras bajo y sobre el hueco del
        cn.caja(a, b, yb + e, yf, z0, z0 + E)                                      # rellenador
        cn.caja(a, b, yb + e, yf, z1 - E, z1)
    for xd in (h0, h1, jn):                                                        # campana (h0, h1) y junta N2/N3
        cn.caja(xd - e / 2, xd + e / 2, yb + e, yf, z0, z1)
    bahias_n = ((xo, h0 - e / 2), (h1 + e / 2, jn - e / 2), (jn + e / 2, xf_))    # N1, N2 y N3
    for a, b in bahias_n:
        cn.caja(a, b, yb + e, yf, z0, z0 + E)                                      # piso
        cn.caja(a, b, yb + e, yf, z_rep, z_rep + E)                                # repisa media
        cn.caja(a, b, yb + e, yf, z1 - E, z1)                                      # techo
    cn.caja(h0 + e / 2, h1 - e / 2, yb + e, yf, z1 - E, z1)                        # techo del módulo de la campana
    cn.crear(col)                                                                  # (la campana lleva su propio fondo)
    ce = Pieza("Depto_Cocina_AltosEsteCascaron", "Depto_Mat_MuebleCocina")
    ce.caja(xb - e, xb, yb, TORRE_Y[0], z0, z1)                                    # fondo (forro)
    ce.caja(xe + f, xb - e, yb, yb + e, z0, z1)                                    # costado norte (muro T5)
    ce.caja(xe + f, xb - e, TORRE_Y[0] - e, TORRE_Y[0], z0, z1)                    # costado sur (torre; bisagra de E3)
    for yd in je:                                                                  # divisores (bisagras de E1 y E2)
        ce.caja(xe + f, xb - e, yd - e / 2, yd + e / 2, z0, z1)
    bahias_e = ((yb + e, je[0] - e / 2), (je[0] + e / 2, je[1] - e / 2), (je[1] + e / 2, TORRE_Y[0] - e))
    for a, b in bahias_e:                                                          # E1 (con el rincón ciego), E2, E3
        ce.caja(xe + f, xb - e, a, b, z1 - E, z1)                                  # techo
        ce.caja(xe + f, xb - e, a, b, z0, z0 + E)                                  # piso
        ce.caja(xe + f, xb - e, a, b, z_rep, z_rep + E)                            # repisa media
    ce.crear(col)
    # --- rellenadores: contra T3, a cada lado de la esquina (el del este tapa también el rincón ciego)
    rl = Pieza("Depto_Cocina_AltosRellenos", "Depto_Mat_FrenteCocina")
    rl.caja(xw, xw + rel - j / 2, yf, yn, *za)
    rl.caja(xa - rel + j / 2, xa, yf, yn, *za)
    rl.caja(xe, xe + f, yb, yn + rel - j / 2, *za)
    rl.crear(col)
    # --- campana telescópica: motor (acero) con filtro abajo, visera de acero cepillado y frente fijo encima
    Pieza("Depto_Cocina_Campana", "Depto_Mat_Acero").caja(
        h0 + e / 2, h1 - e / 2, yb + e, yf, z0 + C["filtro"], z0 + C["alto"]).crear(col)
    Pieza("Depto_Cocina_CampanaFiltro", "Depto_Mat_MetalNegroMate").caja(
        h0 + e / 2 + px(0.015), h1 - e / 2 - px(0.015), yb + e + px(0.015), yf - px(0.015), z0,
        z0 + C["filtro"]).crear(col)
    # visera con el UV girado (corrección 07c, ronda 1): el cepillado corre a lo largo de sus 0,60 m, como en una
    # campana real; con el UV de caja la V iba en vertical y las vetas cruzaban la tira de 4,5 cm (se leía como roble)
    Pieza("Depto_Cocina_CampanaVisera", "Depto_Mat_NeveraAcero", uv_girado=True).caja(
        h0 + j / 2, h1 - j / 2, yf, yn, za[0], za[0] + C["visera"]).crear(col)
    Pieza("Depto_Cocina_CampanaFrente", "Depto_Mat_FrenteCocina").caja(
        h0 + j / 2, h1 - j / 2, yf, yn, za[0] + C["visera"] + JUNTA, za[1]).crear(col)
    # --- hojas. Dos hojas vecinas no llevan la bisagra en la misma junta: abiertas a la vez, sus caras vistas quedan
    # enfrentadas y los tiradores se cruzan (prueba de pares de la fase 6). Norte: la de la izquierda (N1) con bisagra
    # del lado de T3, en el costado que queda detrás del rellenador (excepción a la regla: ver el encabezado), y las
    # dos de la derecha con la bisagra al oeste (con la de la esquina al este, abierta, su tirador entraba 11 mm en la
    # hoja E1). Este: las tres con la bisagra al sur; con la bisagra en la esquina, abierta, la hoja E1 barría con su
    # tirador la hoja norte vecina. La de la torre (E3, excepción) abre sólo a ANGULO_MUEBLE_TORRE: más allá de 90° su
    # canto entra en la cara norte de la torre, que sobresale 0,22 m (PuertaAlta4 entraba 6,7 cm).
    hojas = [("N1", "x", t_l[0], yn, +1, 0, ANGULO_MUEBLE, "Puerta del mueble alto (platos y boles)"),
             ("N2", "x", t_r[0], yn, +1, 0, ANGULO_MUEBLE, "Puerta del mueble alto (vasos y tazas)"),
             ("N3", "x", t_r[1], yn, +1, 0, ANGULO_MUEBLE, "Puerta del mueble alto (vasos altos, taza y boles)"),
             ("E1", "y", t_e[0], xe, -1, 1, ANGULO_MUEBLE, "Puerta del mueble alto de la esquina (fuentes y boles)"),
             ("E2", "y", t_e[1], xe, -1, 1, ANGULO_MUEBLE, "Puerta del mueble alto (despensa y vasos)"),
             ("E3", "y", t_e[2], xe, -1, 1, ANGULO_MUEBLE_TORRE, "Puerta del mueble alto (despensa y tazas)")]
    for hid, eje, (u0, u1), w, s, lado, ang, etq in hojas:
        _hoja_alta(col, f"Depto_Mueble_Cocina_PuertaAlta{hid}", eje, u0, u1, w, s, za, (u0, u1)[lado], etq, ang)

    # --- vajilla (corrección 07c, ronda 1: cada pieza dentro de su módulo, entre sus costados o divisores). Marcos: u a
    # lo largo del tramo, v del fondo hacia las hojas. Tramo norte: u desde la cara interior del fondo en xw + e; cada
    # módulo va de a_k a b_k. Tramo este: u desde yb + e; el rincón ciego (u 0 a 0,40 m) es parte del módulo de E1.
    mn = _marco_px((xw + e, yb + e), (1.0, 0.0), (0.0, 1.0))
    Dn = (yf - yb - e) * S
    (a1, b1), (a2, b2), (a3, b3) = [((a - xw - e) * S, (b - xw - e) * S) for a, b in bahias_n]
    vn = DI.Mallas()
    DI.pila_platos(vn, a1 + 0.14, Dn / 2, zb, 6, 0.13)                                # N1: platos llanos
    DI.pila_platos(vn, b1 - 0.14, Dn / 2, zb, 4, 0.13)
    for u in (a1 + 0.09, a1 + 0.26):
        DI.pila_boles(vn, u, Dn / 2, zs, 3, 0.075, 0.065)                             # boles
    DI.pila_platos(vn, b1 - 0.115, Dn / 2, zs, 5, 0.10)                               # platos de postre
    for u in (0.07, 0.16, 0.25):                                                      # N2: vasos en dos filas de tres
        for dv in (-0.065, 0.065):
            DI.vaso(vn, a2 + u + (0.012 if dv > 0 else 0.0), Dn / 2 + dv, zb, 0.037, 0.12)
    for k, (u, giro) in enumerate(((0.07, 80.0), (0.17, 100.0), (0.27, 70.0))):      # tazas, asa adelante
        DI.taza(vn, a2 + u, Dn / 2 - 0.03, zs, 0.042, 0.095, "Depto_Mat_Ceramica" if k % 2 == 0 else
                "Depto_Mat_GresNegro", giro=giro)
    for u in (0.08, 0.17, 0.26):                                                      # N3: vasos altos
        DI.vaso(vn, a3 + u, Dn / 2, zb, 0.033, 0.15)
    DI.taza(vn, a3 + 0.07, Dn / 2 - 0.03, zs, 0.042, 0.095, "Depto_Mat_GresNegro", giro=95.0)
    DI.pila_boles(vn, a3 + 0.24, Dn / 2, zs, 3, 0.075, 0.065)
    vn.crear(col, "Depto_Cocina_AltosNorteVajilla", mn, props={"colision": False})
    me = _marco_px((xb - e, yb + e), (0.0, 1.0), (-1.0, 0.0))
    De = (xb - e - xe - f) * S
    ue = [((a - yb - e) * S, (b - yb - e) * S) for a, b in bahias_e]
    ve = DI.Mallas()
    DI.pila_platos(ve, 0.57, De / 2, zb, 4, 0.15)                                     # E1: fuentes
    DI.pila_boles(ve, 0.46, De / 2, zs, 3, 0.075, 0.065)
    DI.pila_boles(ve, 0.63, De / 2, zs, 2, 0.075, 0.065, mat="Depto_Mat_GresNegro")
    for k, u in enumerate((0.81, 0.91, 1.01, 1.16, 1.26, 1.36)):                     # E2 y E3: frascos con tapa
        r, alto, cont = FRASCOS_DESPENSA[k % len(FRASCOS_DESPENSA)]
        DI.frasco(ve, u, De / 2, zb, r, alto, "Depto_Mat_Vidrio", cont, "Depto_Mat_MaderaMueble")
    for u in (0.81, 0.90, 0.99):
        DI.vaso(ve, u, De / 2, zs, 0.037, 0.12)
    for u, giro in ((1.17, 85.0), (1.30, 105.0)):
        DI.taza(ve, u, De / 2 - 0.03, zs, 0.042, 0.095, giro=giro)
    ve.crear(col, "Depto_Cocina_AltosEsteVajilla", me, props={"colision": False})
    print("CHECK altos de cocina: módulos norte (m)", [(round(a, 3), round(b, 3)) for a, b in ((a1, b1), (a2, b2), (a3, b3))],
          "este", [(round(a, 3), round(b, 3)) for a, b in ue])
    print("CHECK altos de cocina: hojas", {h[0]: round((h[2][1] - h[2][0]) * S, 3) for h in hojas},
          f"fondo útil norte {Dn:.3f} m, este {De:.3f} m; campana a {z0 - MESON_Z - 0.006:.3f} m del anafe")


def nevera(col):
    """Nevera de acero cepillado (Depto_Mat_NeveraAcero), estilo «french door» con freezer abajo (diseño; el
    brief sólo pedía el volumen). Ancho y frente medidos en el plano (NEVERA_Y, NEVERA_FRENTE_X; corrección 07c).
    Cuerpo hueco contra el muro este; puerta principal de bisagra
    (interactiva, clase "nevera") con contrapuerta (forro blanco y dos balcones con botellas y frascos, hijos de
    la puerta) y cajón freezer abajo (interactivo, clase "cajon"). Interior fijo (no se mueve, sólo la puerta
    que lo tapa): dos estantes de vidrio con cartón de huevos, fruta y un táper, cajón de verduras y frascos."""
    al = REFRI_ALTO
    e_n = px(NEVERA_ESP)
    xf1 = X["E_FORRO"] - px(REFRI_HOLGURA)      # fondo (contra el muro, este)
    xf0 = NEVERA_FRENTE_X                       # frente (hacia la cocina, oeste): medido en plano
    yf0, yf1 = NEVERA_Y                         # norte, sur: medidos en plano

    zr = px(ZOCALO_RETRANQUEO)
    Pieza("Depto_Cocina_NeveraZocalo", "Depto_Mat_Zocalo").caja(xf0 + zr, xf1, yf0 + zr, yf1 - zr, 0.0,
                                                                NEVERA_ZOCALO).crear(col)
    z_piso_top = NEVERA_ZOCALO + NEVERA_ESP
    z_freezer_top = z_piso_top + NEVERA_FREEZER_ALTO
    z_div_top = z_freezer_top + NEVERA_ESP
    z_techo_bot = al - NEVERA_ESP
    cuerpo = Pieza("Depto_Cocina_NeveraCuerpo", "Depto_Mat_NeveraAcero")
    cuerpo.caja(xf1 - e_n, xf1, yf0, yf1, NEVERA_ZOCALO, al)                  # fondo (muro este)
    cuerpo.caja(xf0, xf1, yf0, yf0 + e_n, NEVERA_ZOCALO, al)                  # costado norte (junto a la torre)
    cuerpo.caja(xf0, xf1, yf1 - e_n, yf1, NEVERA_ZOCALO, al)                  # costado sur
    cuerpo.caja(xf0, xf1, yf0, yf1, al - NEVERA_ESP, al)                     # techo
    cuerpo.caja(xf0, xf1, yf0, yf1, NEVERA_ZOCALO, z_piso_top)               # piso general
    cuerpo.caja(xf0, xf1, yf0, yf1, z_freezer_top, z_div_top)                # divisor freezer / compartimento
    cuerpo.crear(col)
    # Forro interior (plástico blanco, no acero): sólo el exterior es de acero cepillado. Cubre las caras del
    # cascarón que quedan a la vista al abrir la puerta o el cajón freezer (fondo, costados, techo y piso de
    # cada compartimento), con un pequeño espesor delante de cada cara.
    le = px(0.004)
    forro_cuerpo = Pieza("Depto_Cocina_NeveraForroInterior", "Depto_Mat_MuebleBlanco")
    for z0i, z1i in ((z_div_top, z_techo_bot), (z_piso_top, z_freezer_top)):   # compartimento principal, freezer
        forro_cuerpo.caja(xf1 - e_n - le, xf1 - e_n, yf0 + e_n, yf1 - e_n, z0i, z1i)          # fondo
        forro_cuerpo.caja(xf0, xf1 - e_n, yf0 + e_n, yf0 + e_n + le, z0i, z1i)                # costado norte
        forro_cuerpo.caja(xf0, xf1 - e_n, yf1 - e_n - le, yf1 - e_n, z0i, z1i)                # costado sur
        forro_cuerpo.caja(xf0, xf1 - e_n, yf0 + e_n, yf1 - e_n, z1i - 0.004, z1i)             # techo
        forro_cuerpo.caja(xf0, xf1 - e_n, yf0 + e_n, yf1 - e_n, z0i, z0i + 0.004)             # piso
    forro_cuerpo.crear(col)

    # Puerta principal, abre hacia el oeste. Corrección 07c: bisagra al norte, junto a la torre. Con la bisagra al sur
    # (hasta la 07b) la hoja abierta a 100° ocupaba 0,50 m de la boca entre el hall y la cocina (junto al remate de
    # T_COC_S); al norte queda en la cocina, delante de la torre, y la boca queda libre.
    DOOR_Y0, DOOR_Y1 = yf0 + px(NEVERA_ESP + NEVERA_HOLGURA_LADO), yf1 - px(NEVERA_ESP + NEVERA_HOLGURA_LADO)
    DOOR_Z0, DOOR_Z1 = z_div_top + NEVERA_JUNTA, z_techo_bot - NEVERA_HOLGURA_LADO
    cara_puerta = xf0 + px(NEVERA_ESP_PUERTA)
    puerta, piv_p = _bisagra(col, "Depto_Mueble_Nevera_Puerta", "Depto_Mat_NeveraAcero", "y", DOOR_Y0, DOOR_Y1,
                             xf0, cara_puerta, DOOR_Z0, DOOR_Z1, DOOR_Y0, xf0, -1,
                             NEVERA_ANGULO_PUERTA, False,
                             dict(clase="nevera", etiqueta="Puerta de la nevera", recinto="Cocina"))
    ul = DOOR_Y1 - px(NEVERA_MANILLA["margen"])                              # cerca del canto libre (sur)
    _tirador(col, "Depto_Mueble_Nevera_Puerta_Tirador", "y", ul - px(0.02), ul + px(0.02), xf0, -1,
            DOOR_Z0, DOOR_Z1, piv_p, puerta, vertical=True)

    # Contrapuerta (hija de la puerta): forro blanco y dos balcones con botellas, salsas y frascos. Balcón bajo
    # para botellas altas (0,41 m libres hasta el de arriba) y balcón alto para salsas.
    forro_w0, forro_w1 = cara_puerta, cara_puerta + px(NEVERA_FORRO_ESP)
    Pieza("Depto_Cocina_NeveraContrapuerta", "Depto_Mat_MuebleBlanco").caja(
        *uw("y", DOOR_Y0 + px(0.01), DOOR_Y1 - px(0.01), forro_w0, forro_w1), DOOR_Z0 + 0.01, DOOR_Z1 - 0.01
    ).crear(col, origen=piv_p, padre=puerta)
    balcon_w1 = forro_w1 + px(0.10)
    # marco del lado interior de la puerta cerrada: u a lo largo de y (desde DOOR_Y0), v desde forro_w1 hacia el
    # fondo de la nevera (+x del plano), z desde el piso
    mp = DI.Marco(Vector((*P.a_blender(forro_w1, DOOR_Y0), 0.0)),
                  Vector((*P.a_blender(forro_w1, DOOR_Y0 + 1.0), 0.0)) - Vector((*P.a_blender(forro_w1, DOOR_Y0), 0.0)),
                  Vector((*P.a_blender(forro_w1 + 1.0, DOOR_Y0), 0.0)) - Vector((*P.a_blender(forro_w1, DOOR_Y0), 0.0)))
    ancho_p = (DOOR_Y1 - DOOR_Y0) * S
    botellas = DI.Mallas()
    for k, (zb, items) in enumerate(((DOOR_Z0 + NEVERA_BALCONES_Z[0], "bajo"), (DOOR_Z0 + NEVERA_BALCONES_Z[1], "alto"))):
        bal = Pieza(f"Depto_Cocina_NeveraBalcon{k + 1}", "Depto_Mat_MuebleBlanco")
        ua, ub = DOOR_Y0 + px(0.015), DOOR_Y1 - px(0.015)
        bal.caja(*uw("y", ua, ub, forro_w1, balcon_w1), zb, zb + 0.006)                        # piso
        bal.caja(*uw("y", ua, ub, balcon_w1 - px(0.004), balcon_w1), zb, zb + NEVERA_BALCON_ALTO)  # labio
        for u_a, u_b in ((ua, ua + px(0.004)), (ub - px(0.004), ub)):                              # costados
            bal.caja(*uw("y", u_a, u_b, forro_w1, balcon_w1 - px(0.004)), zb, zb + NEVERA_BALCON_ALTO)
        bal.crear(col, origen=piv_p, padre=puerta)
        z0b = zb + 0.006
        if items == "bajo":      # leche, jugo, agua y una botella de vino (vidrio verde oscuro: opaco)
            for u, r, alto, liq, tapa in ((0.085, 0.036, 0.30, "Depto_Mat_Ceramica", TAPA_AZUL),
                                          (0.200, 0.034, 0.28, "Depto_Mat_ComidaNaranja", "Depto_Mat_MuebleBlanco"),
                                          (0.315, 0.036, 0.31, None, TAPA_CELESTE)):
                DI.botella(botellas, u, 0.05, z0b, r, alto, "Depto_Mat_Vidrio", liq, llenado=0.85, tapa_mat=tapa)
            DI.botella(botellas, ancho_p - 0.085, 0.05, z0b, 0.037, 0.32, "Depto_Mat_GresNegro", cuello=0.36,
                       tapa_mat="Depto_Mat_Acero")
        else:                    # salsas y frascos
            DI.botella(botellas, 0.07, 0.05, z0b, 0.030, 0.19, "Depto_Mat_ComidaRoja", cuello=0.25,
                       tapa_mat="Depto_Mat_MuebleBlanco")
            DI.botella(botellas, 0.15, 0.05, z0b, 0.028, 0.18, "Depto_Mat_ComidaAmarilla", cuello=0.25,
                       tapa_mat="Depto_Mat_ComidaRoja")
            DI.frasco(botellas, 0.25, 0.05, z0b, 0.035, 0.11, "Depto_Mat_Vidrio", "Depto_Mat_ComidaVerde",
                      "Depto_Mat_MetalNegroMate")
            DI.frasco(botellas, 0.34, 0.05, z0b, 0.033, 0.10, "Depto_Mat_Vidrio", "Depto_Mat_ComidaRoja",
                      "Depto_Mat_Acero")
            with botellas.parte("Depto_Mat_ComidaAmarilla", suave=True) as bm:                # mantequilla
                B_.caja_redondeada(bm, 0.40, 0.50, 0.012, 0.088, z0b, z0b + 0.045, 0.004, segmentos=1)
    # compartimento de lácteos arriba de la contrapuerta: bandeja con tapa abatible esmerilada (cerrada)
    zl = DOOR_Z0 + NEVERA_LACTEOS_Z
    lac = Pieza("Depto_Cocina_NeveraLacteos", "Depto_Mat_MuebleBlanco")
    ua, ub = DOOR_Y0 + px(0.03), DOOR_Y1 - px(0.03)
    lac.caja(*uw("y", ua, ub, forro_w1, forro_w1 + px(0.085)), zl, zl + 0.006)
    for u_a, u_b in ((ua, ua + px(0.004)), (ub - px(0.004), ub)):
        lac.caja(*uw("y", u_a, u_b, forro_w1, forro_w1 + px(0.085)), zl, zl + 0.10)
    lac.crear(col, origen=piv_p, padre=puerta)
    Pieza("Depto_Cocina_NeveraLacteosTapa", PLASTICO_ESMERILADO).caja(
        *uw("y", ua + px(0.004), ub - px(0.004), forro_w1 + px(0.081), forro_w1 + px(0.085)), zl + 0.006, zl + 0.10
    ).crear(col, origen=piv_p, padre=puerta)
    botellas.crear(col, "Depto_Cocina_NeveraPuertaAlimentos", mp, origen=piv_p, padre=puerta)

    # Cajón freezer: corredera hacia afuera (oeste), mismo ancho que la puerta, con forro blanco y congelados.
    FRE_Z0, FRE_Z1 = z_piso_top + NEVERA_HOLGURA_LADO, z_freezer_top - NEVERA_HOLGURA_LADO
    freezer, ref_f = _cajon(col, "Depto_Mueble_Nevera_Freezer", "Depto_Mat_NeveraAcero", "y", DOOR_Y0, DOOR_Y1,
                            xf0, +1, NEVERA_CAJON_PROF, FRE_Z0, FRE_Z1, NEVERA_ESP, NEVERA_RECORRIDO_FREEZER,
                            False, dict(clase="cajon", etiqueta="Cajón del freezer", recinto="Cocina"))
    _tirador(col, "Depto_Mueble_Nevera_Freezer_Tirador", "y", DOOR_Y0, DOOR_Y1, xf0, -1, FRE_Z0, FRE_Z1,
            ref_f, freezer)
    e_c, lf = px(NEVERA_ESP), px(0.004)
    fx0, fx1 = xf0 + e_c, xf0 + px(NEVERA_CAJON_PROF) - e_c              # interior del cajón (frente -> fondo)
    fy0, fy1 = DOOR_Y0 + e_c, DOOR_Y1 - e_c
    zf = FRE_Z0 + NEVERA_ESP
    forro_f = Pieza("Depto_Cocina_NeveraFreezerForro", "Depto_Mat_MuebleBlanco")
    forro_f.caja(fx0, fx1, fy0, fy1, zf, zf + 0.004)
    for a, b, c, d in ((fx0, fx0 + lf, fy0, fy1), (fx1 - lf, fx1, fy0, fy1), (fx0, fx1, fy0, fy0 + lf),
                       (fx0, fx1, fy1 - lf, fy1)):
        forro_f.caja(a, b, c, d, zf, FRE_Z1 - 0.01)
    forro_f.crear(col, origen=ref_f, padre=freezer)
    mf = DI.Marco(Vector((*P.a_blender(fx1 - lf, fy0 + lf), 0.0)),
                  Vector((*P.a_blender(fx1 - lf, fy0 + lf + 1.0), 0.0)) - Vector((*P.a_blender(fx1 - lf, fy0 + lf), 0.0)),
                  Vector((*P.a_blender(fx1 - lf - 1.0, fy0 + lf), 0.0)) - Vector((*P.a_blender(fx1 - lf, fy0 + lf), 0.0)))
    ancho_f, hondo_f = (fy1 - fy0 - 2 * lf) * S, (fx1 - fx0 - 2 * lf) * S
    cong = DI.Mallas()
    z0f = zf + 0.004
    for q, (uc, vc) in enumerate(((0.08, 0.09), (0.205, 0.10))):                             # potes de helado
        with cong.parte("Depto_Mat_Ceramica", suave=True) as bm:
            B_.cilindro(bm, uc, vc, z0f, z0f + 0.09, 0.055, seg=16)
        with cong.parte("Depto_Mat_ComidaRoja" if q == 0 else "Depto_Mat_ComidaAmarilla", suave=True) as bm:
            B_.cilindro(bm, uc, vc, z0f + 0.09, z0f + 0.104, 0.057, seg=16)
    with cong.parte("Depto_Mat_ComidaVerde", suave=True) as bm:                              # bolsa de arvejas
        B_.caja_redondeada(bm, 0.30, ancho_f - 0.03, 0.03, 0.20, z0f, z0f + 0.05, 0.02, segmentos=2)
    with cong.parte("Depto_Mat_Papel") as bm:                                               # cajas apiladas
        B_.caja(bm, 0.03, 0.30, hondo_f - 0.20, hondo_f - 0.02, z0f, z0f + 0.035)
        B_.caja(bm, 0.05, 0.28, hondo_f - 0.19, hondo_f - 0.03, z0f + 0.035, z0f + 0.075)
    for q in range(2):                                                                       # cubeteras
        with cong.parte(TAPA_CELESTE) as bm:
            B_.caja(bm, 0.30 + 0.095 * q, 0.39 + 0.095 * q, hondo_f - 0.24, hondo_f - 0.02, z0f, z0f + 0.03)
    cong.crear(col, "Depto_Cocina_NeveraCongelados", mf, origen=ref_f, padre=freezer)

    # Interior fijo (no se mueve; la puerta lo tapa): estantes de vidrio, cajón de verduras con frente esmerilado y
    # tapa de vidrio, y alimentos. Marco: u a lo ancho (desde el forro norte), v desde el forro del fondo hacia el
    # frente, z desde el piso.
    shelf_w0, shelf_w1 = xf0 + px(0.22), xf1 - e_n - px(0.02)
    for k, zz in enumerate(NEVERA_ESTANTES_Z):
        z_e = z_div_top + zz
        Pieza(f"Depto_Cocina_NeveraEstante{k + 1}", "Depto_Mat_Vidrio").caja(
            *uw("y", DOOR_Y0 + px(0.01), DOOR_Y1 - px(0.01), shelf_w0, shelf_w1), z_e, z_e + NEVERA_ESTANTE_ESP
        ).crear(col)
    x_fondo, y_norte = xf1 - e_n - le, yf0 + e_n + le
    mi = DI.Marco(Vector((*P.a_blender(x_fondo, y_norte), 0.0)),
                  Vector((*P.a_blender(x_fondo, y_norte + 1.0), 0.0)) - Vector((*P.a_blender(x_fondo, y_norte), 0.0)),
                  Vector((*P.a_blender(x_fondo - 1.0, y_norte), 0.0)) - Vector((*P.a_blender(x_fondo, y_norte), 0.0)))
    ui0, ui1 = (DOOR_Y0 + px(0.01) - y_norte) * S, (DOOR_Y1 - px(0.01) - y_norte) * S       # ancho de los estantes
    vi0, vi1 = (x_fondo - shelf_w1) * S, (x_fondo - shelf_w0) * S                          # hondo de los estantes
    z_cv0, z_cv1 = z_div_top + 0.004, z_div_top + 0.004 + NEVERA_CAJON_VERDURA_ALTO
    verd = Pieza("Depto_Cocina_NeveraCajonVerdura", "Depto_Mat_MuebleBlanco")               # bandeja blanca
    xa, xb = shelf_w0 + px(0.015), shelf_w1
    ya, yb = DOOR_Y0 + px(0.01), DOOR_Y1 - px(0.01)
    verd.caja(xa, xb, ya, yb, z_cv0, z_cv0 + 0.006)                                           # piso
    verd.caja(xa, xb, ya, ya + px(0.006), z_cv0, z_cv1)                                       # costados
    verd.caja(xa, xb, yb - px(0.006), yb, z_cv0, z_cv1)
    verd.caja(xb - px(0.006), xb, ya, yb, z_cv0, z_cv1)                                       # fondo
    verd.crear(col)
    Pieza("Depto_Cocina_NeveraCajonVerduraFrente", PLASTICO_ESMERILADO).caja(
        xa - px(0.015), xa, ya, yb, z_cv0, z_cv1).crear(col)
    Pieza("Depto_Cocina_NeveraCajonVerduraTapa", "Depto_Mat_Vidrio").caja(
        xa - px(0.015), xb, ya, yb, z_cv1, z_cv1 + NEVERA_ESTANTE_ESP).crear(col)
    ali = DI.Mallas()
    # dentro del cajón de verduras: lechuga, tomates, pimentones y zanahorias
    zc0 = z_cv0 + 0.006
    DI.fruta(ali, ui0 + 0.12, vi0 + 0.18, zc0, 0.072, "Depto_Mat_ComidaVerde", aplastar=0.78)       # lechuga
    for du, dv in ((0.24, 0.10), (0.30, 0.12), (0.26, 0.17)):                                          # tomates
        DI.fruta(ali, ui0 + du, vi0 + dv, zc0, 0.032, "Depto_Mat_ComidaRoja", aplastar=0.85)
    # pimentones: medidos desde el frente del cajón (corrección 07c: con la nevera de 0,58 de fondo, desde el fondo
    # entraban 1,5 mm en el frente esmerilado)
    DI.fruta(ali, ui0 + 0.26, vi1 - 0.07, zc0, 0.040, "Depto_Mat_ComidaAmarilla", aplastar=1.05)
    DI.fruta(ali, ui0 + 0.35, vi1 - 0.07, zc0, 0.040, "Depto_Mat_ComidaRoja", aplastar=1.05)
    for k in range(3):                                                                                  # zanahorias
        DI.zanahoria(ali, (ui0 + 0.43 + 0.035 * k, vi0 + 0.07, zc0 + 0.016),
                     (ui0 + 0.415 + 0.04 * k, vi1 - 0.05, zc0 + 0.012), 0.016, "Depto_Mat_ComidaNaranja",
                     "Depto_Mat_ComidaVerde")
    # sobre la tapa del cajón (0,23 m libres): queso, yogures y un táper
    zt = z_cv1 + NEVERA_ESTANTE_ESP
    with ali.parte("Depto_Mat_ComidaAmarilla") as bm:                                          # cuña de queso
        DI.extruir_poligono(bm, [(ui0 + 0.03, vi1 - 0.03), (ui0 + 0.16, vi1 - 0.03), (ui0 + 0.16, vi1 - 0.12)],
                            zt, zt + 0.06)
    for k in range(4):                                                                          # yogures
        u_y, v_y = ui0 + 0.22 + 0.055 * (k % 2), vi1 - 0.05 - 0.055 * (k // 2)
        with ali.parte("Depto_Mat_Ceramica", suave=True) as bm:
            B_.cilindro(bm, u_y, v_y, zt, zt + 0.075, 0.025, seg=12)
        with ali.parte("Depto_Mat_ComidaRoja") as bm:
            B_.cilindro(bm, u_y, v_y, zt + 0.075, zt + 0.078, 0.026, seg=12)
    DI.caja_guardado(ali, ui0 + 0.42, vi0 + 0.12, zt, 0.16, 0.12, 0.08, PLASTICO_ESMERILADO,
                     TAPA_AZUL, tapa=0.018)
    # estante 1: cartón de huevos, fuente con fruta y táper
    z1 = z_div_top + NEVERA_ESTANTES_Z[0] + NEVERA_ESTANTE_ESP
    with ali.parte("Depto_Mat_Papel", suave=True) as bm:                                      # cartón de huevos
        B_.caja_redondeada(bm, ui0 + 0.02, ui0 + 0.29, vi1 - 0.14, vi1 - 0.03, z1, z1 + 0.07, 0.008, segmentos=1)
    uf, vf = ui0 + 0.415, vi0 + 0.14
    with ali.parte("Depto_Mat_GresBlanco", Matrix.Translation((uf, vf, 0.0)), suave=True) as bm:   # fuente baja
        B_.torno(bm, [(0.0, z1), (0.07, z1), (0.105, z1 + 0.05), (0.098, z1 + 0.05), (0.064, z1 + 0.008),
                      (0.0, z1 + 0.008)], seg=20)
    for du, dv, mat, r in ((-0.035, -0.02, "Depto_Mat_ComidaRoja", 0.036), (0.035, -0.015, "Depto_Mat_ComidaVerde", 0.035),
                           (0.0, 0.04, "Depto_Mat_ComidaNaranja", 0.038)):
        DI.fruta(ali, uf + du, vf + dv, z1 + 0.012, r, mat, aplastar=0.95)
    DI.caja_guardado(ali, ui0 + 0.13, vi0 + 0.10, z1, 0.18, 0.13, 0.09, PLASTICO_ESMERILADO,
                     TAPA_CELESTE, tapa=0.02)
    # estante 2: leche y jugo en cartón, frascos y una botella al fondo
    z2 = z_div_top + NEVERA_ESTANTES_Z[1] + NEVERA_ESTANTE_ESP
    DI.carton(ali, ui0 + 0.06, vi1 - 0.07, z2, 0.07, 0.07, 0.20, "Depto_Mat_Papel", TAPA_AZUL, giro=4)
    DI.carton(ali, ui0 + 0.15, vi1 - 0.08, z2, 0.07, 0.07, 0.20, "Depto_Mat_ComidaNaranja", "Depto_Mat_MuebleBlanco",
              giro=-3)
    DI.frasco(ali, ui0 + 0.26, vi1 - 0.06, z2, 0.036, 0.12, "Depto_Mat_Vidrio", "Depto_Mat_ComidaRoja",
              "Depto_Mat_MetalNegroMate")
    DI.frasco(ali, ui0 + 0.34, vi1 - 0.07, z2, 0.034, 0.10, "Depto_Mat_Vidrio", "Depto_Mat_ComidaAmarilla",
              "Depto_Mat_Acero")
    DI.botella(ali, ui0 + 0.45, vi0 + 0.07, z2, 0.036, 0.31, "Depto_Mat_GresNegro", cuello=0.36,
               tapa_mat="Depto_Mat_Acero")
    DI.botella(ali, ui0 + 0.10, vi0 + 0.10, z2, 0.050, 0.22, "Depto_Mat_Vidrio", "Depto_Mat_ComidaAmarilla",
               llenado=0.7, cuello=0.08)                                                  # jarro de limonada
    with ali.parte("Depto_Mat_GresBlanco", suave=True) as bm:                                 # fuente tapada
        B_.cilindro(bm, ui0 + 0.27, vi0 + 0.12, z2, z2 + 0.06, 0.075, seg=20)
    with ali.parte("Depto_Mat_Ceramica", suave=True) as bm:
        B_.cilindro(bm, ui0 + 0.27, vi0 + 0.12, z2 + 0.06, z2 + 0.066, 0.082, seg=20)
    ali.crear(col, "Depto_Cocina_NeveraAlimentos", mi)


def nicho_lavadora(col):
    e = px(LV_FRENTE_ESP)
    x0, x1 = X["T3_E"], X["LV_W"]
    frente = Pieza("Depto_LV_Frente", "Depto_Mat_FrenteCloset")
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


WC_SEGMENTOS = 32            # corrección 07b: con 20 lados la tapa se leía facetada en primer plano (+24 triángulos)


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
    pz.cilindro(fondo + d * rx, wyc, rx, px(WC["taza_ancho"]) / 2, WC["pedestal_alto"], WC["taza_alto"],
                seg=WC_SEGMENTOS)
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
    cuerpo = Pieza(f"Depto_Sanitario_{bid}_Vanitorio", "Depto_Mat_MuebleBano")
    cuerpo.caja(vx0, vx1, frente + sv * px(VANITORIO_RETRANQUEO), muro_y, 0.08, z0)
    zx0, zx1 = (vx0, vx1 - px(0.03)) if libre_e else (vx0 + px(0.03), vx1)
    cuerpo.caja(zx0, zx1, frente + sv * px(0.07), muro_y, 0.0, 0.08)   # zócalo retranqueado al frente y al extremo libre
    cuerpo.crear(col)
    c = Pieza(f"Depto_Sanitario_{bid}_Cubierta", "Depto_Mat_CubiertaBano")
    c.caja(vx0, vx1, vy0, vy1, z0, z1)
    c.caja(vx0, vx1, muro_y - sv * px(0.02), muro_y, z1, z1 + RESPALDO_ALTO)   # respaldo
    c.crear(col)
    # lavamanos, grifería mural y espejo: piezas de la decoración (fase 4)


def sanitarios(col):
    for bid, b in BANOS.items():
        tina(col, bid, *b["tina"])
        rep = b.get("repisa")
        inodoro(col, bid, b["wc"], rep)
        if rep:
            rx0, rx1, ry0, ry1, rz = rep
            Pieza(f"Depto_Sanitario_{bid}_Repisa", "Depto_Mat_MuroBano").caja(rx0, rx1, ry0, ry1, 0.0, rz).crear(col)
            wyc = (b["wc"]["bbox"][2] + b["wc"]["bbox"][3]) / 2
            Pieza(f"Depto_Sanitario_{bid}_Pulsador", "Depto_Mat_MetalNegroMate").caja(
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
    if total > TOPE_TRIANGULOS:
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
    nevera(cols["Depto_Fijos"])
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
