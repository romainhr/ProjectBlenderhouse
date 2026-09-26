"""Fase 4 (mobiliario y decoración) del activo Depto, versión 2: decoración industrial moderna minimalista.

Uso (o todo el pipeline con build/depto_run.sh 04):
    blender -b build/depto.blend --python-exit-code 1 --python build/depto_04_mobiliario.py

Ubica las piezas modeladas desde cero en build/deco_living.py, deco_dormitorio.py, deco_cocina_bano.py y
deco_objetos.py (contrato en docs/deco-industrial.md: coordenadas locales, frente hacia −Y, espalda hacia +Y).
Cada pieza se construye en el origen, se mide su caja local y se ubica: contra un muro (la espalda toca la cara
del muro más una holgura), colgada del cielo (con el cable recortado para que nada baje de ALTURA_LIBRE en zonas
de paso) o apoyada sobre otra pieza. La versión 1 (mobiliario neutro) está en archivo/v1_neutro/.

Idempotente: exige el maestro con el sello vigente de la fase 3, borra y reconstruye sólo su colección
(Depto_Mobiliario) y sella scene["depto_fase04"]. Pruebas antes de guardar (si una falla, no guarda):
- camas contra su dibujo del plano (centro a ≤ 2,5 px; las demás piezas se rediseñaron y no se contrastan),
- ninguna pieza sólida penetra muros, losas, artefactos de la fase 3 u otras piezas sólidas (> 1 mm, cajas por
  isla); los adornos (cojines, libros, cerámica, colgantes, lámparas) sólo contra la arquitectura,
- colgantes a ≥ ALTURA_LIBRE, cámaras a ≥ 0,20 m de todo sólido, presupuesto de triángulos.
El recorrido con muebles (radio 0,20 m) lo prueba build/depto_recorrido.py en el pipeline.
"""
import hashlib
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import deco_cocina_bano as CB  # noqa: E402
import deco_comedor as CM  # noqa: E402
import deco_dormitorio as DO  # noqa: E402
import deco_hall as HA  # noqa: E402
import deco_living as LV  # noqa: E402
import deco_objetos as OB  # noqa: E402
import depto_03_formas as F3  # noqa: E402  (medidas de cocina y baños)
import depto_geom as G  # noqa: E402
import depto_plano as P  # noqa: E402
import depto_sellos as SE  # noqa: E402

X, Y, S = P.X, P.Y, P.M_POR_PX
H = P.ALTURA_PISO_CIELO
COL = "Depto_Mobiliario"
EXTRACCION = os.path.join(RAIZ, "build", "depto_medicion", "extraccion_px_bordes.json")
ALTURA_LIBRE = 1.85        # m: nada colgante por debajo en zonas de paso (la cámara del tour choca hasta 1,80)
HOLGURA_MURO = 0.01        # m entre la espalda de una pieza y el muro
ALFOMBRA_ALTO = 0.008      # lo que se levantan las piezas apoyadas en una alfombra
TOL_PENETRACION = 0.001
TOPE_TRIANGULOS = 200_000        # escena visible (ADR 0004, decisión 4: de 150 000 a 200 000)
HOLGURA_CAMARA = 0.20
TOL_BBOX = 2.5
POTENCIA = dict(colgante=40.0, arco=35.0, mesa=12.0, aplique=10.0, foco=8.0, paso=25.0, balcon=30.0)   # W de las
# luces de revisión por lámpara (supuesto; paso y balcón: fase 07b)
# Grupos de luz (contrato de interacción v2, sección 2; fase 07b): uno por luminaria o conjunto que se prende junto.
# (id, etiqueta, recinto, encendido al cargar el visor, color lineal). 2700 K en general y 3000 K en cocina y baños
# (docs/contrato-interaccion.md). Izquierda y derecha de los veladores: mirando la cabecera desde los pies de la cama.
K2700, K3000 = (1.0, 0.72, 0.42), (1.0, 0.78, 0.55)
GRUPOS_LUZ = [
    ("living_techo", "Living · techo", "Living", True, K2700),
    ("living_lampara_pie", "Living · lámpara de pie", "Living", False, K2700),
    ("cocina_techo", "Cocina · techo", "Cocina", True, K3000),
    ("hall_techo", "Hall · focos", "Hall", True, K2700),
    ("dorm1_techo", "Dormitorio principal · techo", "Dorm1", True, K2700),
    ("dorm1_velador", "Dormitorio principal · lámpara del velador", "Dorm1", False, K2700),
    ("paso_d1", "Clósets del principal · techo", "Paso_D1", True, K2700),
    ("dorm2_techo", "Segundo dormitorio · techo", "Dorm2", True, K2700),
    ("dorm2_aplique_izq", "Segundo dormitorio · aplique izquierdo", "Dorm2", False, K2700),
    ("dorm2_aplique_der", "Segundo dormitorio · aplique derecho", "Dorm2", False, K2700),
    ("paso_d2", "Clósets del segundo · techo", "Paso_D2", True, K2700),
    ("bano1", "Baño principal · techo", "Bano1", True, K3000),
    ("bano2", "Segundo baño · techo", "Bano2", True, K3000),
    ("balcon", "Balcón · colgante del comedor", "Balcon", True, K2700),
]
RECINTOS_CON_LUZ = ("Hall", "Living", "Cocina", "Dorm1", "Paso_D1", "Bano1", "Dorm2", "Paso_D2", "Bano2", "Balcon")
# Nombres de los recintos para la interfaz del visor (contrato v2, sección 5); las etiquetas de GRUPOS_LUZ los usan.
RECINTOS_ETIQUETAS = {
    "Hall": "Hall", "Living": "Living", "Cocina": "Cocina", "Dorm1": "Dormitorio principal",
    "Dorm2": "Segundo dormitorio", "Paso_D1": "Clósets del principal", "Paso_D2": "Clósets del segundo",
    "Bano1": "Baño principal", "Bano2": "Segundo baño", "Balcon": "Balcón", "Palier": "Palier",
    "Nicho_LV": "Lavadora",
}
RESOLUCION_CAMA = 0.7     # deco_dormitorio.cama: 13 100 triángulos en vez de 20 000, sin diferencia visible
                          # (review/deco/piezas/cama_r0.7 vs r1.0); deja presupuesto para las piezas de la tanda 2
APLIQUE_PLACA_Z = 1.20    # diseño: centro de la placa de los apliques de lectura del dormitorio 2
CONDUCTO_SEP = 0.014      # eje del conducto a la cara del cielo o del muro (deco_objetos.conducto: radio + 4 mm)
Z_BALCON = -P.DESNIVEL_BALCON
HALL_MURO = X["LV_E"]      # muro oeste del hall: cara este del tabique del nicho de lavadora (y 325,6 a 363,2)
HALL_EJE_Y = (Y["LV_F"] + Y["T9_N"]) / 2
PERCHERO_Z = 1.55         # diseño: base de la tabla del perchero
RIEL_HALL = (371.0, HALL_EJE_Y)   # diseño: riel de focos en el cielo del hall, a lo largo de x (reemplaza al
                                  # colgante de domo, que quedaba sobre la cámara del hall y la encandilaba)
UTENSILIOS_Z = 1.30       # diseño: eje de la barra de utensilios, bajo la repisa (1,55) y sobre la cubierta (0,94)
TOALLERO_Z = 0.62         # diseño: eje del toallero en el frente del vanitorio (bajo la cubierta a 0,80)
BISTRO = dict(x=(X["BAL_F"] + X["W_O"]) / 2, y=285.0)   # diseño: mesa del balcón en el extremo sur (la silla sur
                                                      # queda a ≈ 9 cm de la baranda); el norte, junto a la hoja
                                                      # abierta, queda libre para salir al balcón

DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "O": (-1, 0)}   # hacia dónde mira el frente, en el plano

# Interruptores de muro (contrato v2, sección 3; fase 07b). Placa con el centro a 1,10 del piso, el canto a 0,10 del
# marco, del lado de la manilla y dentro del recinto (la hoja abierta queda del lado de la bisagra y no la tapa).
INTERRUPTOR_Z = 1.10
INTERRUPTOR_MARCO = 0.10


def _junto(borde_marco, lado):
    """u (px) del centro de una placa cuyo canto queda a INTERRUPTOR_MARCO del borde del marco, hacia `lado`."""
    return borde_marco + lado * (INTERRUPTOR_MARCO + OB.INTERRUPTOR["ancho"] / 2) / S


# (recinto, grupos (una tecla por grupo, de izquierda a derecha), cara del muro px, u px, hacia dónde mira)
INTERRUPTORES = [
    # hall: en la cara sur del tabique cocina/hall, junto a la jamba norte de la entrada (manilla al norte; el
    # marco sobresale hasta E_FORRO - 1 cm del lado del hall)
    ("Hall", ("hall_techo",), Y["COC_S"], _junto(X["E_FORRO"] - F3.px(F3.MARCO_SOBRESALE), -1), "S"),
    # cocina (abierta, sin puerta): en el canto de 0,12 del mismo tabique, que da al paso entre hall y cocina
    ("Cocina", ("cocina_techo",), X["COC_W"], (Y["COC_N"] + Y["COC_S"]) / 2, "O"),
    # living: al pie del conducto visto del muro de ladrillo, junto a la puerta D1 (lado de la manilla), con el
    # colgante del comedor del balcón (docs/deco-industrial.md: el comedor para dos es el del balcón)
    ("Living", ("living_techo", "balcon"), Y["D1_S"], _junto(X["JAMBA_D"], -1), "S"),
    # balcón: por dentro, en el muro de ladrillo junto a la hoja móvil del ventanal (esquina con la fachada)
    ("Balcon", ("balcon",), Y["D1_S"], _junto(X["W_I"], +1), "S"),
    # dormitorios: espalda con espalda con el del living (D1) y del lado de la manilla; la segunda tecla prende el
    # paso de los clósets, que no tiene puerta propia
    ("Dorm1", ("dorm1_techo", "paso_d1"), Y["D1_N"], _junto(X["JAMBA_D"], -1), "N"),
    ("Dorm2", ("dorm2_techo", "paso_d2"), Y["D2_S"], _junto(X["JAMBA_D"], -1), "S"),
    # baños: por dentro, en el tabique de la puerta, al sur de la jamba de la manilla (bisagra al norte)
    ("Bano1", ("bano1",), X["T4_E"], _junto(Y["T4_B"], +1), "E"),
    ("Bano2", ("bano2",), X["T10_E"], _junto(Y["T10_B"], +1), "E"),
]


def yaw(mira):
    """Giro en Z que lleva el frente local (−Y) a la dirección `mira` del plano ('N', 'S', 'E', 'O' o (dx, dy))."""
    dx, dy = DIRS[mira] if isinstance(mira, str) else mira
    return math.atan2(-dx, -dy) + math.pi / 2          # plano (dx, dy) -> Blender (−dy, −dx)


class Colocador:
    def __init__(self, col):
        self.col = col
        self.piezas = []        # (nombre, clase, objs)

    def construir(self, fn, nombre, **params):
        objs = [o for o in fn(self.col, f"Depto_Mueble_{nombre}", **params) if o is not None]
        for o in objs:
            if o.name not in self.col.objects:
                self.col.objects.link(o)
        return objs

    @staticmethod
    def caja_local(objs):
        pts = [v.co for o in objs if o.type == "MESH" for v in o.data.vertices]
        return (Vector([min(p[k] for p in pts) for k in range(3)]), Vector([max(p[k] for p in pts) for k in range(3)]))

    def poner(self, nombre, clase, objs, x, y, z=0.0, mira="N", props=None):
        th = yaw(mira)
        X0, Y0 = P.a_blender(x, y)
        for o in objs:
            if o.parent is None:
                o.location = (X0, Y0, z)
                o.rotation_euler = (0.0, 0.0, th)
            o["pieza"] = nombre
            o["clase"] = clase
            for k, v in (props or {}).items():
                o[k] = v
        self.piezas.append((nombre, clase, objs))
        return objs

    def contra_muro(self, fn, nombre, clase, muro, u, mira, z=0.0, holgura=HOLGURA_MURO, **params):
        """Espalda (local +Y) contra la cara de muro `muro` (px; y si mira N/S, x si mira E/O); u = la otra coordenada."""
        objs = self.construir(fn, nombre, **params)
        lo, hi = self.caja_local(objs)
        d = (hi.y + holgura) / S                        # del origen local a la cara del muro, en px
        dx, dy = DIRS[mira]
        x, y = (u, muro + dy * d) if mira in ("N", "S") else (muro + dx * d, u)
        return self.poner(nombre, clase, objs, x, y, z, mira)

    def centro(self, fn, nombre, clase, x, y, z=0.0, mira="N", **params):
        return self.poner(nombre, clase, self.construir(fn, nombre, **params), x, y, z, mira)

    def mundo(self, fn, nombre, clase, **params):
        """Pieza que ya se construye en coordenadas del mundo (p. ej. un conducto por puntos): sin mover ni girar."""
        objs = self.construir(fn, nombre, **params)
        for o in objs:
            o["pieza"], o["clase"] = nombre, clase
        self.piezas.append((nombre, clase, objs))
        return objs

    def colgante(self, fn, nombre, x, y, cable_pref=0.8, minimo=ALTURA_LIBRE, **params):
        """Cuelga del cielo; si la pieza baja de `minimo`, se recorta el cable y se reconstruye."""
        objs = self.construir(fn, nombre, largo_cable=cable_pref, **params)
        lo, _ = self.caja_local(objs)
        if H + lo.z < minimo:
            for o in objs:
                bpy.data.objects.remove(o, do_unlink=True)
            cable = max(0.08, cable_pref - (minimo - (H + lo.z)) - 0.01)
            objs = self.construir(fn, nombre, largo_cable=cable, **params)
        return self.poner(nombre, "adorno", objs, x, y, H, "S")


def marcar_ampolletas(objs, potencia, radio=None, grupo=None):
    """Marca los objetos emisivos para la fase 5 (luz puntual en su centroide); `radio`: radio de la fuente si no
    sirve el de la fase 5 (p. ej. dentro de un foco, cuya boca es más chica que ese radio); `grupo`: id de
    GRUPOS_LUZ al que pertenece la luz (lo exige pruebas_luces)."""
    for o in objs:
        if o.type == "MESH" and any(m and m.name == "Depto_Mat_Bombilla" for m in o.data.materials):
            o["luz_w"] = potencia
            if radio is not None:
                o["luz_radio"] = radio
            if grupo is not None:
                o["luz_grupo"] = grupo


def clicable(objs, grupo, sufijos):
    """Lámparas que se prenden tocándolas (contrato v2, sección 3): `grupo_luz` en su pantalla y su cuerpo."""
    for o in objs:
        if o.name.endswith(tuple(sufijos)):
            o["grupo_luz"] = grupo


# ---------------------------------------------------------------------------
# Distribución (px del plano; diseño salvo donde se indica)
# ---------------------------------------------------------------------------
LIV_X = (X["W_I"] + X["JAMBA_D"]) / 2      # eje del muro de ladrillo del living (≈188,6)
MURO_TV = Y["D1_S"]                        # cara del ladrillo
MURO_SOFA = Y["D2_N"]                      # tabique living / dormitorio 2
SOFA_HOLGURA = 0.10                        # diseño: sofá separado 0,10 del muro
MESA_A_SOFA = 0.40                         # diseño: de la mesa de centro al frente del sofá
RACK_Z = 0.25                              # diseño: mueble de TV flotante
TV_CENTRO_Z = 1.15                         # diseño: centro de la pantalla
CUADROS_Z = 1.35                           # diseño: base de los cuadros sobre el sofá
# cx: centro de la cama dibujada (extracción 156-255: 205,5) corrido 2,3 px (4 cm) hacia la ventana: con la manta, la
# cama llega a x ≈ 257 y la manilla de la hoja abierta de D1/D2 está en x ≈ 279; sin correrla el paso al closet y al
# baño quedaba en 0,42 m y la cámara del tour (radio 0,20) no pasaba. Cabecero contra el muro de las almohadas del plano.
CAMA_CX = 205.5 - 2.3
VELADOR_ANCHO = 0.42       # diseño: 3 cm menos que la especificación, para que quepa junto a la ventana
# lectura: D1 con lámpara de mesa en el velador oeste; D2 con apliques de brazo sobre los dos veladores (y un jarrón)
CAMAS = {"D1": dict(cx=CAMA_CX, muro=Y["N_I"], mira="S", tapiz="Depto_Mat_Lana", espejo=(150.0, Y["D1_N"], "N"),
                    lectura="mesa"),
         "D2": dict(cx=CAMA_CX, muro=Y["S_I"], mira="N", tapiz="Depto_Mat_Cuero", espejo=(150.0, Y["D2_S"], "S"),
                    lectura="aplique")}


def living(c):
    rack = c.contra_muro(LV.rack_tv, "Living_RackTV", "solido", MURO_TV, LIV_X, "S", z=RACK_Z)
    tv = c.contra_muro(LV.tv, "Living_TV", "solido", MURO_TV, LIV_X, "S")
    lo, hi = c.caja_local(tv)
    for o in tv:
        o.location.z = TV_CENTRO_Z - (lo.z + hi.z) / 2
    sofa = c.contra_muro(LV.sofa, "Living_Sofa", "solido", MURO_SOFA, LIV_X, "N", z=ALFOMBRA_ALTO, holgura=SOFA_HOLGURA)
    lo, hi = c.caja_local(sofa)
    sofa_y = P.a_plano(*sofa[0].location[:2])[1]
    frente = sofa_y - (-lo.y) / S                     # el frente local (−Y) mira al norte: y menor
    alf = c.centro(LV.alfombra, "Living_Alfombra", "solido", LIV_X, frente - 0.10 / S, mira="N", ancho=2.0, largo=1.4)
    mesa = c.construir(LV.mesa_centro, "Living_MesaCentro")
    mlo, mhi = c.caja_local(mesa)
    my = frente - (MESA_A_SOFA + mhi.y) / S
    c.poner("Living_MesaCentro", "solido", mesa, LIV_X, my, ALFOMBRA_ALTO, "N")
    # lámpara de arco en la esquina sureste, detrás del extremo del sofá, con la pantalla sobre el asiento (hacia el
    # oeste). Base alineada a los ejes: girada en diagonal su caja tocaba el marco de la puerta D2.
    arco = c.construir(LV.lampara_arco, "Living_LamparaArco")
    alo, ahi = c.caja_local(arco)
    base_x = LIV_X + (sofa_ancho(sofa) / 2 + 0.05) / S - alo.x / S     # justo al este del sofá
    base_y = MURO_SOFA - (0.03 + ahi.x) / S                           # a 3 cm del tabique (tras girar, x local -> y)
    c.poner("Living_LamparaArco", "adorno", arco, base_x, base_y, 0.0, "O")
    marcar_ampolletas(arco, POTENCIA["arco"], grupo="living_lampara_pie")
    clicable(arco, "living_lampara_pie", ("_Base", "_Tubo", "_Pantalla"))
    lat = c.construir(LV.mesa_lateral, "Living_MesaLateral")
    llo, lhi = c.caja_local(lat)
    c.poner("Living_MesaLateral", "solido", lat, base_x, base_y - (ahi.x + 0.05 + lhi.y) / S - 0.0, 0.0, "N")
    # cojines y cuadros
    for i, (dx, mat) in enumerate(((-0.55, "Depto_Mat_Lana"), (0.55, "Depto_Mat_Manta"))):
        coj = c.construir(LV.cojin, f"Living_Cojin{i + 1}", material=mat, inclinacion=70.0, semilla=5 + i)
        c.poner(f"Living_Cojin{i + 1}", "adorno", coj, LIV_X + dx / S, sofa_y + 0.02 / S,
                ALFOMBRA_ALTO + 0.44, "N")                # de pie sobre el asiento, apoyado en el respaldo
    for i, (dx, arte) in enumerate(((-0.30, 1), (0.30, 2))):
        c.contra_muro(LV.cuadro, f"Living_Cuadro{i + 1}", "solido", MURO_SOFA, LIV_X + dx / S, "N", z=CUADROS_Z,
                      holgura=0.0, arte=arte)
    # sobre el rack: libros y un jarrón
    ztop = RACK_Z + (c.caja_local(rack)[1].z - c.caja_local(rack)[0].z)
    rack_y = P.a_plano(*rack[0].location[:2])[1]
    lib = c.construir(OB.libros, "Living_Libros", n=6, semilla=3)
    c.poner("Living_Libros", "adorno", lib, LIV_X - 0.55 / S, rack_y, ztop, "S")
    jar = c.construir(OB.jarron, "Living_Jarron", variante=0)
    c.poner("Living_Jarron", "adorno", jar, LIV_X + 0.55 / S, rack_y, ztop, "S")
    return sofa


def sofa_ancho(sofa):
    lo, hi = Colocador.caja_local(sofa)
    return hi.x - lo.x


def dormitorios(c):
    for did, d in CAMAS.items():
        rug_y = d["muro"] + (1.25 / S if d["mira"] == "S" else -1.25 / S)   # sin pisar los veladores
        c.centro(LV.alfombra, f"{did}_Alfombra", "solido", d["cx"], rug_y, mira=d["mira"], ancho=2.4, largo=1.6)
        cama = c.contra_muro(DO.cama, f"{did}_Cama", "solido", d["muro"], d["cx"], d["mira"], z=ALFOMBRA_ALTO,
                             tapiz=d["tapiz"], resolucion=RESOLUCION_CAMA)
        lo, hi = c.caja_local(cama)
        for lado in (-1, 1):
            vel = c.construir(DO.velador, f"{did}_Velador{'O' if lado < 0 else 'E'}", ancho=VELADOR_ANCHO)
            vlo, vhi = c.caja_local(vel)
            vx = d["cx"] + lado * ((hi.x - lo.x) / 2 + 0.03 + (vhi.x - vlo.x) / 2) / S
            dy = DIRS[d["mira"]][1]
            vy = d["muro"] + dy * (vhi.y + HOLGURA_MURO) / S
            c.poner(f"{did}_Velador{'O' if lado < 0 else 'E'}", "solido", vel, vx, vy, 0.0, d["mira"])
            zt = vhi.z - vlo.z
            if d["lectura"] == "aplique":
                lado_n = 'O' if lado < 0 else 'E'
                apl = c.contra_muro(OB.aplique_brazo, f"{did}_Aplique{lado_n}", "adorno", d["muro"], vx, d["mira"],
                                    holgura=0.0)
                pc = next(o["placa_centro_z"] for o in apl if "placa_centro_z" in o)
                for o in apl:
                    o.location.z = APLIQUE_PLACA_Z - pc
                g = f"dorm{did[1]}_aplique_{'der' if lado < 0 else 'izq'}"   # mirando la cabecera: el oeste a la derecha
                marcar_ampolletas(apl, POTENCIA["aplique"], grupo=g)
                clicable(apl, g, ("_Metal", "_Pantalla"))
            if lado < 0 and d["lectura"] == "mesa":
                lam = c.construir(DO.lampara_mesa, f"{did}_LamparaMesa")
                c.poner(f"{did}_LamparaMesa", "adorno", lam, vx, vy, zt, d["mira"])
                marcar_ampolletas(lam, POTENCIA["mesa"], grupo=f"dorm{did[1]}_velador")
                clicable(lam, f"dorm{did[1]}_velador", ("_Cuerpo", "_Pantalla"))
            elif lado < 0:
                jar = c.construir(OB.jarron, f"{did}_Jarron", variante=2)
                c.poner(f"{did}_Jarron", "adorno", jar, vx, vy, zt, d["mira"])
            else:
                lib = c.construir(OB.libros, f"{did}_Libros", n=3, apilados=True, semilla=7 if did == "D1" else 11)
                c.poner(f"{did}_Libros", "adorno", lib, vx, vy, zt, d["mira"])
        ex, ey, em = d["espejo"]
        c.contra_muro(DO.espejo_pie, f"{did}_Espejo", "solido", ey, ex, em)
        col = c.colgante(OB.colgante_domo, f"{did}_Colgante", d["cx"], d["muro"] + (1.15 / S if d["mira"] == "S"
                                                                                     else -1.15 / S))
        marcar_ampolletas(col, POTENCIA["colgante"], grupo=f"dorm{did[1]}_techo")


def cocina(c):
    y_muro = Y["T5_S"] + F3.px(F3.SALPICADERO_ESP)     # cara del azulejo del tramo norte
    tramos = [(X["T3_E"] + 0.03 / S, F3.ANAFE[0] - 0.06 / S), (F3.ANAFE[1] + 0.06 / S, F3.ALTOS_X - 0.03 / S)]
    for i, (x0, x1) in enumerate(tramos):
        largo = (x1 - x0) * S
        rep = c.contra_muro(CB.repisa_abierta, f"Cocina_Repisa{i + 1}", "solido", y_muro, (x0 + x1) / 2, "S",
                            z=1.55, holgura=0.0, largo=largo)
        for nivel, zn in enumerate(alturas_repisa(rep)):
            s_ = c.construir(CB.set_repisa, f"Cocina_Set{i + 1}{nivel}", largo=largo - 0.04, semilla=10 * i + nivel)
            c.poner(f"Cocina_Set{i + 1}{nivel}", "adorno", s_, (x0 + x1) / 2, y_muro, zn, "S")
    x0, x1 = tramos[0]
    c.contra_muro(HA.riel_utensilios, "Cocina_Utensilios", "adorno", y_muro, (x0 + x1) / 2, "S", z=UTENSILIOS_Z,
                  holgura=0.0, largo=min(0.45, (x1 - x0) * S - 0.04))
    g = c.construir(CB.grifo_cocina, "Cocina_Grifo")
    c.poner("Cocina_Grifo", "adorno", g, F3.BACHA[1] + 0.035 / S, (F3.BACHA[2] + F3.BACHA[3]) / 2, F3.MESON_Z, "O")
    for i, x in enumerate((310.0, 368.0)):
        col = c.colgante(OB.colgante_jaula, f"Cocina_Colgante{i + 1}", x, 200.0)
        marcar_ampolletas(col, POTENCIA["colgante"], grupo="cocina_techo")


def alturas_repisa(objs):
    """z de la cara superior de cada tabla de una repisa ya ubicada (islas de madera, de abajo arriba)."""
    bpy.context.view_layer.update()                   # matrix_world de la repisa recién movida
    zs = []
    for o in objs:
        if o.type == "MESH" and any(m and m.name == "Depto_Mat_MaderaMueble" for m in o.data.materials):
            for isla in G.islas_mundo(o):
                zs.append(round(max(v.z for v in isla), 4))
    return sorted(set(zs))


def banos(c):
    for bid, b in F3.BANOS.items():
        vx0, vx1, vy0, vy1 = b["vanitorio"]["bbox"]
        muro_v = b["vanitorio"]["muro"][1]
        cx = (vx0 + vx1) / 2
        ztop = F3.VANITORIO_Z[1]
        lav = c.construir(CB.lavabo_concreto, f"{bid}_Lavabo")
        llo, lhi = c.caja_local(lav)
        c.poner(f"{bid}_Lavabo", "solido", lav, cx, muro_v - (0.07 + lhi.y) / S, ztop, "N")
        c.contra_muro(CB.grifo_lavabo_mural, f"{bid}_Grifo", "adorno", muro_v, cx, "N", z=ztop + 0.25, holgura=0.0)
        c.contra_muro(CB.espejo_redondo, f"{bid}_Espejo", "solido", muro_v, cx, "N", z=1.25, holgura=0.0)
        tx0, tx1, tym, ts = b["tina"]
        ty1 = tym + ts * F3.px(F3.TINA_FONDO)
        c.contra_muro(CB.ducha_expuesta, f"{bid}_Ducha", "adorno", tx0, (tym + ty1) / 2, "E", holgura=0.0)
        mam = c.construir(CB.mampara, f"{bid}_Mampara", barra_y=0.45)   # barra hacia el muro macizo, no hacia la puerta
        c.poner(f"{bid}_Mampara", "solido", mam, tx0, ty1 - ts * F3.px(F3.TINA_PARED) / 2, F3.TINA_ALTO,
                (0, ts))    # el panel corre hacia el este desde el muro; su frente mira al baño
        frente_v = vy0 if b["vanitorio"]["muro"][0] == "S" else vy1
        c.contra_muro(HA.toallero_barra, f"{bid}_Toallero", "adorno", frente_v, cx, "N", z=TOALLERO_Z, holgura=0.0,
                      largo=0.40)                                   # en el frente del vanitorio, bajo el lavabo
        col = c.colgante(OB.colgante_jaula, f"{bid}_Colgante", (tx0 + tx1) / 2, (ty1 + vy0) / 2)
        marcar_ampolletas(col, POTENCIA["colgante"], grupo=f"bano{bid[1]}")
    # portarrollos: B1 en la cara de la repisa de instalaciones, B2 en el muro este junto al WC
    rep = F3.BANOS["B1"]["repisa"]
    c.contra_muro(CB.portarrollo, "B1_Portarrollo", "adorno", rep[0], 101.0, "O", z=0.65, holgura=0.0)
    c.contra_muro(CB.portarrollo, "B2_Portarrollo", "adorno", X["E_I"], 441.0, "O", z=0.65, holgura=0.0)


def hall(c):
    c.contra_muro(OB.reloj_pared, "Hall_Reloj", "solido", Y["T9_N"], 398.0, "N", z=1.65, holgura=0.0)
    c.contra_muro(LV.cuadro, "Hall_Cuadro", "solido", Y["T9_N"], 356.0, "N", z=1.20, holgura=0.0,
                  arte=3)
    col = c.colgante(OB.colgante_domo, "Living_Colgante", 205.0, 246.0)
    marcar_ampolletas(col, POTENCIA["colgante"], grupo="living_techo")


def hall_entrada(c):
    """Recibidor: banca y perchero en el muro oeste, riel de focos en el cielo y felpudo afuera, en el palier (la
    hoja de entrada barre el piso del hall: un felpudo adentro lo rozaría)."""
    c.contra_muro(HA.banca_entrada, "Hall_Banca", "solido", HALL_MURO, HALL_EJE_Y, "E", ancho=0.66)
    c.contra_muro(HA.perchero_mural, "Hall_Perchero", "solido", HALL_MURO, HALL_EJE_Y, "E", z=PERCHERO_Z,
                  holgura=0.0, ancho=0.60)
    # focos (giro 0 = −Y local = sur del plano; −90 = oeste): banca y perchero, cuadro (en diagonal) y reloj
    riel = c.construir(HA.riel_focos, "Hall_Riel", giros=(-90.0, -30.0, 20.0), inclinaciones=(35.0, 30.0, 30.0))
    c.poner("Hall_Riel", "adorno", riel, *RIEL_HALL, H, "S")          # "S": el riel (x local) corre según x
    marcar_ampolletas(riel, POTENCIA["foco"], radio=0.01, grupo="hall_techo")    # la boca del foco mide Ø 0,06
    fel = c.construir(HA.felpudo, "Palier_Felpudo")
    flo, fhi = c.caja_local(fel)
    c.poner("Palier_Felpudo", "solido", fel, X["E_O"] + 0.02 / S + (fhi.y - flo.y) / 2 / S,
            (Y["ENT_N"] + Y["ENT_S"]) / 2, 0.0, "E")                  # ancho (x local) según y, frente a la puerta


def balcon(c):
    mesa = c.construir(CM.mesa_bistro, "Balcon_Mesa")
    c.poner("Balcon_Mesa", "solido", mesa, BISTRO["x"], BISTRO["y"], Z_BALCON, "N")
    r = (c.caja_local(mesa)[1].x - c.caja_local(mesa)[0].x) / 2
    for nombre, lado, mira in (("Balcon_SillaN", -1, "S"), ("Balcon_SillaS", 1, "N")):
        silla = c.construir(CM.silla_bistro, nombre)
        slo, shi = c.caja_local(silla)
        d = (r + 0.06 + (shi.y - slo.y) / 2) / S                # frente del asiento a 6 cm del canto de la mesa
        c.poner(nombre, "solido", silla, BISTRO["x"], BISTRO["y"] + lado * d, Z_BALCON, mira)
    # fase 07b: el balcón no tenía luz. Colgante de domo (el del living, más chico) sobre la mesa, colgado de la losa
    # del balcón de arriba (Depto_Cielo_Balcon), con su conducto visto desde la fachada.
    col = c.colgante(OB.colgante_domo, "Balcon_Colgante", BISTRO["x"], BISTRO["y"], cable_pref=0.45, diametro=0.28,
                     alto=0.19)
    marcar_ampolletas(col, POTENCIA["balcon"], grupo="balcon")


def pasos(c):
    """Fase 07b: los pasos de los clósets no tenían luz. Colgante de jaula (el de la cocina y los baños) con cable
    corto, casi pegado al cielo, al centro de cada paso."""
    for pid, (x0, x1, y0, y1) in (("Paso_D1", (X["T3_E"], X["T4_W"], Y["CL1_N"], Y["CL1_S"])),
                                  ("Paso_D2", (X["T3_E"], X["T10_W"], Y["CL2_N"], Y["CL2_S"]))):
        col = c.colgante(OB.colgante_jaula, f"{pid}_Colgante", (x0 + x1) / 2, (y0 + y1) / 2, cable_pref=0.10)
        marcar_ampolletas(col, POTENCIA["paso"], grupo=pid.lower())


def interruptores(c):
    """Placas de INTERRUPTORES con una tecla por grupo; grupo_luz en la placa ("id1,id2") y en cada tecla ("id").
    Sin colisión: son 12 mm de muro y no deben angostar los pasos del recorrido."""
    for recinto, grupos, muro, u, mira in INTERRUPTORES:
        nombre = f"Depto_Interruptor_{recinto}"
        objs = OB.interruptor(c.col, nombre, n_teclas=len(grupos))
        x, y = (u, muro) if mira in ("N", "S") else (muro, u)
        c.poner(f"Interruptor_{recinto}", "adorno", objs, x, y, INTERRUPTOR_Z, mira)
        placa, teclas = objs[0], objs[1:]
        placa["grupo_luz"] = ",".join(grupos)
        for t, g in zip(teclas, grupos):
            t["grupo_luz"] = g
        for o in objs:
            o["recinto"] = recinto
            o["colision"] = False


def conductos(c):
    """Conducto eléctrico visto (deco_objetos.conducto) por el cielo de concreto, en coordenadas del mundo."""
    zc = H - CONDUCTO_SEP
    florn = (0.055 + 0.001) / S                       # radio del florón de los colgantes (deco_objetos._floron), px

    def pt(x, y, z):
        return (*P.a_blender(x, y), z)

    # living: del florón del colgante hacia el este (libre del televisor), al muro de ladrillo y bajando a una caja
    x_baja, y_muro = _junto(X["JAMBA_D"], -1), MURO_TV + CONDUCTO_SEP / S    # 07b: baja al interruptor del living
    c.mundo(OB.conducto, "Living_ConductoCielo", "adorno", normal_muro=(0.0, 0.0, 1.0), cajas=(),
            puntos=(pt(205.0 + florn, 246.0, zc), pt(x_baja, 246.0, zc), pt(x_baja, y_muro, zc),
                    pt(x_baja, y_muro, H - 0.25)))
    c.mundo(OB.conducto, "Living_ConductoMuro", "adorno", normal_muro=(1.0, 0.0, 0.0), cajas=(),
            puntos=(pt(x_baja, y_muro, H - 0.25),                           # copla contra copla: unión
                    pt(x_baja, y_muro, INTERRUPTOR_Z + OB.INTERRUPTOR["alto"] / 2)))   # entra por arriba a la placa
    # balcón: del muro de la fachada al florón del colgante, por la losa del balcón de arriba
    c.mundo(OB.conducto, "Balcon_Conducto", "adorno", normal_muro=(0.0, 0.0, 1.0), cajas=(),
            puntos=(pt(X["W_O"] - 0.001 / S, BISTRO["y"], zc), pt(BISTRO["x"] + florn, BISTRO["y"], zc)))
    # cocina: entre los dos colgantes de jaula, con caja de derivación al medio
    c.mundo(OB.conducto, "Cocina_Conducto", "adorno", normal_muro=(0.0, 0.0, 1.0), cajas=(1,),
            puntos=(pt(310.0 + florn, 200.0, zc), pt(339.0, 200.0, zc), pt(368.0 - florn, 200.0, zc)))


# ---------------------------------------------------------------------------
# Instancias: piezas repetidas comparten una sola malla
# ---------------------------------------------------------------------------
def firma_malla(me):
    """Huella de todo lo que define la malla: vértices, caras, aristas, suavizado, UV y materiales."""
    h = hashlib.sha1()

    def arr(coleccion, attr, n, tipo):
        a = np.empty(n, dtype=tipo)
        coleccion.foreach_get(attr, a)
        return a
    h.update(np.round(arr(me.vertices, "co", len(me.vertices) * 3, np.float64), 6).tobytes())
    h.update(arr(me.loops, "vertex_index", len(me.loops), np.int32).tobytes())
    for attr, tipo in (("loop_total", np.int32), ("material_index", np.int32), ("use_smooth", bool)):
        h.update(arr(me.polygons, attr, len(me.polygons), tipo).tobytes())
    h.update(arr(me.edges, "vertices", len(me.edges) * 2, np.int32).tobytes())
    h.update(arr(me.edges, "use_edge_sharp", len(me.edges), bool).tobytes())
    for uv in me.uv_layers:
        h.update(uv.name.encode())
        h.update(np.round(arr(uv.data, "uv", len(me.loops) * 2, np.float64), 6).tobytes())
    h.update(repr(([m.name if m else None for m in me.materials], me.use_auto_smooth,
                   round(me.auto_smooth_angle, 6), me.has_custom_normals)).encode())
    return h.hexdigest()


def compartir_mallas(objs):
    """Objetos con mallas idénticas pasan a compartir un solo datablock (instancias enlazadas, como Alt+D): el .blend
    y el GLB guardan una sola copia. -> (objetos que ahora comparten, mallas únicas, mallas antes)."""
    grupos = {}
    for o in objs:
        if o.type == "MESH":
            grupos.setdefault(firma_malla(o.data), []).append(o)
    antes = len({o.data.as_pointer() for g in grupos.values() for o in g})
    n = 0
    for lista in grupos.values():
        base = lista[0].data
        for o in lista[1:]:
            viejo = o.data
            if viejo is base:
                continue
            o.data = base
            if viejo.users == 0:
                bpy.data.meshes.remove(viejo)
            n += 1
    return n, len(grupos), antes


# ---------------------------------------------------------------------------
# Pruebas
# ---------------------------------------------------------------------------
def pruebas(root, c):
    fallos = []
    bpy.context.view_layer.update()
    mis = {o for _, _, objs in c.piezas for o in objs}
    arq = [o for o in root.all_objects if o.type == "MESH" and not o.hide_render and o not in mis
           and not o.name.startswith("Depto_Ref")]
    arq_s = G.solidos(arq)
    grupos = [(n, cl, G.solidos([o for o in objs if o.type == "MESH"])) for n, cl, objs in c.piezas]
    for i, (n, cl, sol) in enumerate(grupos):
        for o, A in sol:
            for ob, B in arq_s:
                if G.penetracion(A, B) > TOL_PENETRACION:
                    fallos.append(f"{o.name} entra {G.penetracion(A, B) * 1000:.1f} mm en {ob.name}")
            if cl != "solido":
                continue
            for n2, cl2, sol2 in grupos[i + 1:]:
                if cl2 != "solido":
                    continue
                for ob, B in sol2:
                    if G.penetracion(A, B) > TOL_PENETRACION:
                        fallos.append(f"{o.name} entra {G.penetracion(A, B) * 1000:.1f} mm en {ob.name}")
    for n, cl, objs in c.piezas:
        if n.endswith("Colgante"):
            zmin = min((o.matrix_world @ v.co).z for o in objs if o.type == "MESH" for v in o.data.vertices)
            if zmin < ALTURA_LIBRE - 1e-4:
                fallos.append(f"{n} baja hasta {zmin:.2f} m (mínimo {ALTURA_LIBRE})")
    f_cam, holguras = G.holgura_camaras(arq_s + [s for _, cl, sol in grupos if cl == "solido" for s in sol],
                                        HOLGURA_CAMARA)
    fallos += f_cam
    with open(EXTRACCION) as fh:
        ext = {f["name"]: f for f in json.load(fh)["fixtures"]}
    for did, ref in (("D1", "Cama D1"), ("D2", "Cama D2")):
        objs = next(objs for n, _, objs in c.piezas if n == f"{did}_Cama")
        pts = [P.a_plano(*(o.matrix_world @ v.co)[:2]) for o in objs if o.type == "MESH" for v in o.data.vertices]
        cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
        e = ext[ref]
        if abs(cx - (e["x0"] + e["x1"]) / 2) > TOL_BBOX:
            fallos.append(f"{did}_Cama corrida {cx - (e['x0'] + e['x1']) / 2:.1f} px de su dibujo")
    total = 0
    for o in root.all_objects:
        if o.type == "MESH" and not o.hide_render and not o.name.startswith("Depto_Ref"):
            o.data.calc_loop_triangles()
            total += len(o.data.loop_triangles)
    if total > TOPE_TRIANGULOS:
        fallos.append(f"presupuesto de triángulos excedido: {total}")
    return fallos, holguras, total


def pruebas_luces(root):
    """Cada ampolleta en un grupo válido, cada grupo con ampolletas y con algo que lo prenda (tecla o lámpara),
    cada recinto con luz, y cada placa a 1,10 con una tecla hija sin giro por grupo."""
    fallos = []
    ids = [g[0] for g in GRUPOS_LUZ]
    if len(set(ids)) != len(ids):
        fallos.append("ids de GRUPOS_LUZ repetidos")
    amp = [o for o in root.all_objects if o.get("luz_w")]
    for o in amp:
        if o.get("luz_grupo") not in ids:
            fallos.append(f"{o.name}: ampolleta sin grupo de luz válido ({o.get('luz_grupo')!r})")
    con_luz = {o.get("luz_grupo") for o in amp}
    controles = {}
    for o in root.all_objects:
        for g in str(o.get("grupo_luz", "")).split(","):
            if g:
                controles.setdefault(g, []).append(o.name)
    for g in ids:
        if g not in con_luz:
            fallos.append(f"grupo {g} sin ampolletas")
        if g not in controles:
            fallos.append(f"grupo {g} sin interruptor ni lámpara que lo prenda")
    for g, nombres in controles.items():
        if g not in ids:
            fallos.append(f"{nombres}: grupo_luz {g} no existe en GRUPOS_LUZ")
    for i, e, r, *_ in GRUPOS_LUZ:
        if not e.startswith(RECINTOS_ETIQUETAS[r] + " · "):
            fallos.append(f"grupo {i}: la etiqueta {e!r} no empieza con el nombre de su recinto")
    faltan = set(RECINTOS_CON_LUZ) - {g[2] for g in GRUPOS_LUZ}
    if faltan:
        fallos.append(f"recintos sin luz: {sorted(faltan)}")
    bpy.context.view_layer.update()
    for o in root.all_objects:
        if not o.name.startswith("Depto_Interruptor_") or o.parent is not None:
            continue
        if abs(o.matrix_world.translation.z - INTERRUPTOR_Z) > 1e-4:
            fallos.append(f"{o.name}: centro a {o.matrix_world.translation.z:.3f} m (se pide {INTERRUPTOR_Z})")
        grupos = str(o.get("grupo_luz", "")).split(",")
        teclas = [h for h in o.children if h.name.endswith("_Tecla")]
        if len(teclas) != len(grupos):
            fallos.append(f"{o.name}: {len(teclas)} teclas para {len(grupos)} grupos")
        for t in teclas:
            if t.rotation_euler.to_quaternion().angle > 1e-6 or t.get("grupo_luz") not in grupos:
                fallos.append(f"{t.name}: tecla girada o con grupo_luz ajeno a su placa")
    return fallos


def main():
    scene = bpy.context.scene
    SE.exigir(scene, "03", bpy.data.filepath)
    root = bpy.data.collections["Depto"]
    col = G.colecciones_fase(root, (COL,))[COL]
    c = Colocador(col)
    living(c)
    dormitorios(c)
    cocina(c)
    banos(c)
    hall(c)
    hall_entrada(c)
    balcon(c)
    pasos(c)
    interruptores(c)
    conductos(c)
    compartidos, unicas, antes = compartir_mallas([o for _, _, objs in c.piezas for o in objs])
    fallos, holguras, total = pruebas(root, c)
    fallos += pruebas_luces(root)
    for f in fallos:
        print("FALLA", f)
    print("CHECK holgura de cámaras (m):", holguras)
    print(f"CHECK instancias: {antes} mallas -> {unicas} únicas; {compartidos} objetos comparten la malla de otro")
    if fallos:
        raise SystemExit(f"ERROR: {len(fallos)} pruebas de la fase 4 fallan; no se guarda el maestro.")
    objs = list(col.all_objects)
    tris = sum(len(o.data.loop_triangles) for o in objs if o.type == "MESH")
    luces = sum(1 for o in objs if o.get("luz_w"))
    n_int = sum(1 for o in objs if o.name.startswith("Depto_Interruptor_") and o.parent is None)
    # para las fases 5 (color de cada luz) y 6 (grupos_luz del contrato)
    scene["depto_grupos_luz"] = json.dumps([dict(id=i, etiqueta=e, recinto=r, encendido=en, color=list(k))
                                            for i, e, r, en, k in GRUPOS_LUZ], ensure_ascii=False)
    scene["depto_recintos_etiquetas"] = json.dumps(RECINTOS_ETIQUETAS, ensure_ascii=False)
    SE.sellar(scene, "04")
    bpy.ops.wm.save_mainfile(filepath=SE.MAESTRO)
    print(f"CHECK fase 4: {len(c.piezas)} piezas, {len(objs)} objetos, {tris} triángulos, {luces} ampolletas en {len(GRUPOS_LUZ)} grupos, "
          f"{n_int} interruptores; "
          f"escena visible {total}; sin interferencias > {TOL_PENETRACION * 1000:.0f} mm")
    print(f"FASE_OK Depto_04_mobiliario {len(objs)} {tris} sello={scene['depto_fase04']}")


if __name__ == "__main__":
    main()
