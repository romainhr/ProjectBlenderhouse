"""Cocina y baños: piezas de la decoración industrial (versión 2; docs/deco-industrial.md, «Cocina y baños»).

Cada pieza es `nombre(col, prefijo, **parámetros) -> list[bpy.types.Object]`, en coordenadas locales (metros, Z
arriba), con todos sus objetos en el origen (0, 0, 0) y sin rotación; un objeto por material (o pocos). Frente
hacia −Y. Las piezas murales tienen la cara de atrás en y = 0; el punto de apoyo de cada pieza se indica en su
docstring. Sin booleanos: todo se arma con tornos, barridos, cajas y lofts de bmesh. Determinista (semillas fijas).
Sólo API de bpy 3.6; funciona en headless.

Materiales que este módulo agrega a depto_geom.MATERIALES (con setdefault): Depto_Mat_GranoClaro,
Depto_Mat_GranoOscuro (contenido de los frascos) y Depto_Mat_Carton (tubo del rollo de papel).
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector

import deco_base as B
import depto_geom as G

# ---------------------------------------------------------------- materiales
MADERA = "Depto_Mat_MaderaMueble"       # roble ahumado (tablas, tapas, tabla de picar)
ACERO = "Depto_Mat_AceroNegro"          # acero pavonado (ménsulas, escalera, aro del espejo)
NEGRO = "Depto_Mat_MetalNegroMate"      # grifería, ducha, perfil de mampara, portarrollo
VIDRIO = "Depto_Mat_Vidrio"
ESPEJO = "Depto_Mat_Espejo"
CONCRETO = "Depto_Mat_Concreto"
GRES_BLANCO = "Depto_Mat_GresBlanco"
GRES_ARENA = "Depto_Mat_GresArena"
GRES_NEGRO = "Depto_Mat_GresNegro"
TOALLA = "Depto_Mat_Toalla"
TOALLA_OSCURA = "Depto_Mat_Manta"       # lana carbón: toalla de manos oscura (contraste)
PAPEL = "Depto_Mat_Papel"
GRANO_CLARO = "Depto_Mat_GranoClaro"
GRANO_OSCURO = "Depto_Mat_GranoOscuro"
CARTON = "Depto_Mat_Carton"

# Nuevos (no están en depto_geom.py): (color sRGB, rugosidad, metálico, alfa). Supuestos de diseño.
G.MATERIALES.setdefault(GRANO_CLARO, ((0.86, 0.79, 0.63), 0.85, 0.0, 1.0))    # arroz / pasta corta
G.MATERIALES.setdefault(GRANO_OSCURO, ((0.26, 0.13, 0.05), 0.50, 0.0, 1.0))   # café en grano
G.MATERIALES.setdefault(CARTON, ((0.62, 0.49, 0.34), 0.90, 0.0, 1.0))         # tubo de cartón del rollo


# ================================================================ ayudas de modelado propias
def _giro_z_a(eje):
    """Matriz 4×4 que lleva +Z a la dirección `eje`."""
    return Vector((0.0, 0.0, 1.0)).rotation_difference(Vector(eje).normalized()).to_matrix().to_4x4()


def _verts(anillos):
    return [v for a in anillos for v in a]


def revolucion(bm, perfil, centro=(0.0, 0.0, 0.0), eje=(0.0, 0.0, 1.0), seg=24, cerrado=False, giro=0.0):
    """deco_base.torno alrededor de un eje cualquiera que pasa por `centro`. perfil: [(radio, altura)], con la
    altura medida a lo largo de `eje` desde `centro`. Devuelve los anillos de vértices."""
    limpio = [perfil[0]]
    for q in perfil[1:]:                 # sin puntos repetidos (darían caras de área nula)
        if abs(q[0] - limpio[-1][0]) + abs(q[1] - limpio[-1][1]) > 1e-7:
            limpio.append(q)
    anillos = B.torno(bm, limpio, seg=seg, cerrado=cerrado)
    m = Matrix.Translation(Vector(centro)) @ _giro_z_a(eje) @ Matrix.Rotation(math.radians(giro), 4, "Z")
    B.transformar(bm, m, _verts(anillos))
    return anillos


def perfil_cilindro(r, largo, canto=0.0, n=2, base=0.0):
    """Perfil (radio, altura) de un cilindro macizo con tapas y cantos redondeados de radio `canto`."""
    pts = [(0.0, base)]
    if canto > 0:
        for k in range(n + 1):
            a = math.pi / 2 * k / n
            pts.append((r - canto + canto * math.sin(a), base + canto - canto * math.cos(a)))
        for k in range(n + 1):
            a = math.pi / 2 * k / n
            pts.append((r - canto + canto * math.cos(a), base + largo - canto + canto * math.sin(a)))
    else:
        pts += [(r, base), (r, base + largo)]
    pts.append((0.0, base + largo))
    return pts


def cilindro_ab(bm, a, b, r, seg=16, canto=0.0, n=1):
    """Cilindro macizo de `a` a `b` (puntos 3D), con cantos redondeados opcionales."""
    a, b = Vector(a), Vector(b)
    d = b - a
    return revolucion(bm, perfil_cilindro(r, d.length, canto, n), centro=a, eje=d, seg=seg)


def esfera(bm, centro, r, seg=12, pisos=6):
    perfil = [(r * math.sin(math.pi * k / pisos), -r * math.cos(math.pi * k / pisos)) for k in range(pisos + 1)]
    return revolucion(bm, perfil, centro=centro, seg=seg)


def rr_contorno(ax, ay, r, n_esq=4, lados=((), (), (), ()), cx=0.0, cy=0.0):
    """Contorno de un rectángulo redondeado (semiancho ax, semialto ay, radio de esquina r), antihorario, desde la
    esquina (+, +). `lados`: fracciones (0-1) de puntos intermedios en los lados arriba, izquierda, abajo y
    derecha, para que contornos con distinto desfase tengan los mismos puntos."""
    r = max(min(r, ax - 1e-4, ay - 1e-4), 2e-4)
    arcos = []
    for qx, qy, a0 in ((1, 1, 0.0), (-1, 1, 90.0), (-1, -1, 180.0), (1, -1, 270.0)):
        ccx, ccy = cx + qx * (ax - r), cy + qy * (ay - r)
        arcos.append([(ccx + r * math.cos(math.radians(a0 + 90.0 * k / n_esq)),
                       ccy + r * math.sin(math.radians(a0 + 90.0 * k / n_esq))) for k in range(n_esq + 1)])
    pts = []
    for i, arco in enumerate(arcos):
        pts += arco
        a, b = arco[-1], arcos[(i + 1) % 4][0]
        pts += [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in lados[i]]
    return pts


def perfil_canto(z0, z1, canto, n=3):
    """[(desfase hacia adentro, z)] de una losa de z0 a z1 con sus dos aristas horizontales redondeadas."""
    if canto <= 0:
        return [(0.0, z0), (0.0, z1)]
    abajo = [(canto * (1 - math.sin(math.pi / 2 * k / n)), z0 + canto * (1 - math.cos(math.pi / 2 * k / n)))
             for k in range(n + 1)]
    arriba = [(canto * (1 - math.cos(math.pi / 2 * k / n)), z1 - canto + canto * math.sin(math.pi / 2 * k / n))
              for k in range(n + 1)]
    return abajo + arriba


def loft(bm, anillos, tapa_ini=True, tapa_fin=True, suave=True, polo_ini=None, polo_fin=None, cerrado=True):
    """Superficie entre anillos de puntos 3D con igual cantidad de puntos. Tapas planas (n-gono) o polos
    (abanico hacia un punto). Devuelve los anillos de vértices."""
    vs = [[bm.verts.new(p) for p in a] for a in anillos]
    for a, b in zip(vs[:-1], vs[1:]):
        n = len(a)
        for i in range(n if cerrado else n - 1):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i])).smooth = suave
    for anillo, polo, tapa, invertir in ((vs[0], polo_ini, tapa_ini, True), (vs[-1], polo_fin, tapa_fin, False)):
        if polo is not None:
            pv = bm.verts.new(polo)
            n = len(anillo)
            for i in range(n):
                bm.faces.new((anillo[i], anillo[(i + 1) % n], pv)).smooth = suave
        elif tapa:
            bm.faces.new(list(reversed(anillo)) if invertir else anillo)
    return vs


def losa_rr(bm, ax, ay, r_esq, z0, z1, canto, n_esq=4, n_canto=3, cx=0.0, cy=0.0):
    """Losa de planta rectangular redondeada con las aristas de arriba y abajo redondeadas (tablas, lavabo)."""
    anillos = [[(x, y, z) for x, y in rr_contorno(ax - d, ay - d, r_esq - d, n_esq, cx=cx, cy=cy)]
               for d, z in perfil_canto(z0, z1, canto, n_canto)]
    return loft(bm, anillos)


def redondear(puntos, radio, pasos=4):
    """Polilínea con esquinas redondeadas (misma construcción que deco_base.tubo, con pasos a elección)."""
    return B._redondear_polilinea(puntos, radio, pasos) if radio > 0 else [Vector(p) for p in puntos]


def barra_plana(bm, puntos, ancho, espesor, radio_curva=0.0, pasos=4, lateral=(1.0, 0.0, 0.0), tapas=True):
    """Pletina de sección rectangular (ancho según `lateral`, espesor en el plano de la polilínea), barrida por
    una polilínea plana normal a `lateral`, con dobleces redondeados."""
    L = Vector(lateral).normalized()
    pts = redondear(puntos, radio_curva, pasos)
    n = len(pts)
    anillos = []
    for i in range(n):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        nv = L.cross(t).normalized()
        anillos.append([pts[i] + L * (sx * ancho / 2) + nv * (sy * espesor / 2)
                        for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))])
    return loft(bm, anillos, tapa_ini=tapas, tapa_fin=tapas)


def tubo_codos(bm, puntos, r, seg=12, radio_curva=0.03, pasos=4):
    """Tubo por una polilínea con curvas de `pasos` tramos (deco_base.tubo con la curva ya redondeada)."""
    return B.tubo(bm, redondear(puntos, radio_curva, pasos), r, seg=seg, radio_curva=0.0)


def codo(bm, a, p, b, r, radio_curva, extra=0.012, seg=12, pasos=4):
    """Fitting de codo: tubo más grueso que envuelve la curva en `p` entre los tramos p-a y p-b."""
    a, p, b = Vector(a), Vector(p), Vector(b)
    d1, d2 = (p - a).normalized(), (b - p).normalized()
    ang = math.acos(max(-1.0, min(1.0, d1.dot(d2))))
    t = radio_curva * math.tan(ang / 2)
    la = min(t + extra, (p - a).length * 0.95)
    lb = min(t + extra, (b - p).length * 0.95)
    return tubo_codos(bm, [p - d1 * la, p, p + d2 * lb], r, seg=seg, radio_curva=radio_curva, pasos=pasos)


def _mover(bms, v):
    for bm in bms:
        bmesh.ops.translate(bm, vec=Vector(v), verts=bm.verts)


def _caja_env(bms):
    pts = [v.co for bm in bms for v in bm.verts]
    return (Vector([min(p[k] for p in pts) for k in range(3)]), Vector([max(p[k] for p in pts) for k in range(3)]))


def _crear(col, prefijo, partes, angulo=40):
    """partes: [(sufijo, bmesh, material o lista de materiales)] -> objetos (omite los bmesh vacíos)."""
    objs = []
    for suf, bm, mat in partes:
        if len(bm.verts) == 0:
            bm.free()
            continue
        if isinstance(mat, (list, tuple)):
            objs.append(B.objeto(col, f"{prefijo}_{suf}", bm, mat[0], materiales=list(mat), angulo_suave=angulo))
        else:
            objs.append(B.objeto(col, f"{prefijo}_{suf}", bm, mat, angulo_suave=angulo))
    return objs


def _manilla_cruz(bm, centro, eje, largo=0.030, r_rayo=0.0045, r_bola=0.0065, seg=8, seg_bola=None):
    """Manilla en cruz de cuatro rayos (a 45°) con bolitas en las puntas, en el plano normal a `eje`."""
    c, e = Vector(centro), Vector(eje).normalized()
    u = e.cross(Vector((0, 0, 1)) if abs(e.z) < 0.9 else Vector((1, 0, 0))).normalized()
    w = e.cross(u).normalized()
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = u * math.cos(a) + w * math.sin(a)
        B.tubo(bm, [c, c + d * (largo - r_bola * 0.6)], r_rayo, seg=seg)
        esfera(bm, c + d * largo, r_bola, seg=seg_bola or seg, pisos=4)


# ================================================================ cocina
PLETINA_A = 0.040        # ménsula: pletina de 40 × 5 mm (medida comercial usual)
PLETINA_E = 0.005
ESPESOR_TABLA = 0.035    # docs/deco-industrial.md
MARGEN_MENSULA = 0.15    # supuesto: ménsulas a 15 cm de cada extremo
SEP_MAX_MENSULAS = 0.90  # supuesto: luz máxima de una tabla de roble de 35 mm cargada


def repisa_abierta(col, prefijo, largo=1.20, fondo=0.25, niveles=(0.0, 0.40), espesor=ESPESOR_TABLA):
    """Repisa mural abierta: tablas de roble de `espesor` sobre ménsulas de pletina de acero negro de 40 × 5 mm
    en «[» (una pletina vertical atornillada al muro que une los brazos de todos los niveles), cada brazo con un
    labio que sube 18 mm por delante del canto de la tabla. Espalda en y = 0 (la pletina toca el muro); el labio
    llega a y = −fondo. Cada nivel es la cara inferior del brazo: la tabla del nivel z apoya en z + 0,005 y su cara
    de arriba queda en z + 0,005 + espesor (ahí va set_repisa). Base (brazo inferior) en z = 0."""
    niveles = sorted(niveles)
    assert len(niveles) >= 2, "la ménsula en «[» necesita al menos dos niveles"
    e = PLETINA_E
    labio = 0.018
    partes = []
    # tablas: entre la cara de la pletina (y = −e) y el labio (y = −fondo + e); cantos redondeados de 3 mm
    bm = bmesh.new()
    y0, y1 = -fondo + e, -e
    for z in niveles:
        losa_rr(bm, largo / 2, (y1 - y0) / 2, 0.004, z + e, z + e + espesor, 0.003, n_esq=2, n_canto=3,
                cy=(y0 + y1) / 2)
    partes.append(("Tablas", bm, MADERA))
    # ménsulas
    bm = bmesh.new()
    n = max(2, math.ceil((largo - 2 * MARGEN_MENSULA) / SEP_MAX_MENSULAS) + 1)
    xs = [-(largo / 2 - MARGEN_MENSULA) + i * (largo - 2 * MARGEN_MENSULA) / (n - 1) for i in range(n)]
    yl = -fondo + e / 2                    # eje del labio
    for x in xs:
        zs = [z + e / 2 for z in niveles]
        barra_plana(bm, [(x, yl, zs[0] + e / 2 + labio), (x, yl, zs[0]), (x, -e / 2, zs[0]), (x, -e / 2, zs[-1]),
                         (x, yl, zs[-1]), (x, yl, zs[-1] + e / 2 + labio)], PLETINA_A, e, radio_curva=0.005,
                    pasos=4)
        for z in zs[1:-1]:                 # niveles intermedios: brazo con labio soldado a la pletina vertical
            barra_plana(bm, [(x, -e, z), (x, yl, z), (x, yl, z + e / 2 + labio)], PLETINA_A, e, radio_curva=0.005,
                        pasos=4)
        for za, zb in zip(niveles[:-1], niveles[1:]):
            for f in (0.28, 0.72):         # dos tornillos de cabeza redonda por tramo
                zt = za + (zb - za) * f
                cilindro_ab(bm, (x, -e, zt), (x, -e - 0.0028, zt), 0.0048, seg=10, canto=0.0014, n=1)
    partes.append(("Mensulas", bm, ACERO))
    return _crear(col, prefijo, partes)


# ---------------------------------------------------------------- set de repisa
def _perfil_pila_platos(n, R=0.11, paso=0.010):
    """Silueta de revolución de `n` platos de gres apilados (un solo torno). Cada plato: pie en r ≈ 0,065, ala
    que sube hasta el borde (R) a 0,025 y pozo plano a 0,010; entre platos queda la ranura de sombra."""
    def ala(z0):          # borde de un plato cuya base está en z0 (de afuera por abajo a arriba)
        return [(R - 0.004, z0 + 0.0195), (R, z0 + 0.0226), (R - 0.006, z0 + 0.025)]
    p = [(0.0, 0.003), (0.063, 0.003), (0.0655, 0.0), (0.0705, 0.0), (0.073, 0.0025)]
    for k in range(n):
        z0 = k * paso
        p += ala(z0)
        if k < n - 1:
            rc = R - 0.013            # ranura: entra hasta rc por la cara de arriba del plato k ...
            z_arriba = z0 + 0.025 - (R - 0.006 - rc) / (R - 0.006 - 0.080) * 0.015
            z_abajo = (z0 + paso) + 0.0025 + (rc - 0.073) / (R - 0.004 - 0.073) * 0.017
            p += [(rc, z_arriba), (rc + 0.0005, z_abajo)]   # ... y sale por la cara de abajo del plato k+1
    zt = (n - 1) * paso
    p += [(0.082, zt + 0.0112), (0.077, zt + 0.0100), (0.0, zt + 0.0100)]
    return p, zt + 0.0100


def _perfil_bol(R, H, t=0.006):
    """Bol de gres de torno (radio de boca R, alto H, pared t), de polo a polo: superficie cerrada."""
    return [(0.0, 0.004), (0.45 * R, 0.004), (0.50 * R, 0.0), (0.57 * R, 0.0), (0.61 * R, 0.006),
            (0.82 * R, 0.27 * H), (0.95 * R, 0.60 * H), (R, 0.95 * H), (R - t / 2, H),
            (R - t, 0.93 * H), (0.95 * R - t, 0.60 * H), (0.80 * R - t, 0.30 * H), (0.45 * R, 0.13 * H + 0.004),
            (0.0, 0.12 * H + 0.004)]


def _frasco(bmv, bmm, bmg, cx, cy, alto, ro, llenado, seg=28):
    """Frasco de vidrio (pared 3,5 mm, fondo 7 mm) con tapa de madera de tapón, y su contenido."""
    ri, fb = ro - 0.0035, 0.007
    perfil = [(0.0, 0.0), (ro - 0.006, 0.0), (ro - 0.00176, 0.00176), (ro, 0.006), (ro, alto), (ri, alto),
              (ri, fb + 0.0015), (0.0, fb)]
    revolucion(bmv, perfil, centro=(cx, cy, 0.0), seg=seg)
    hb = alto + 0.0003                # la tapa apoya en el borde (0,3 mm de holgura contra el parpadeo)
    lt = 0.018
    tapa = [(0.0, hb + lt), (ro - 0.0045, hb + lt), (ro + 0.0008, hb + lt - 0.0048), (ro + 0.0008, hb),
            (ri - 0.0006, hb), (ri - 0.0006, hb - 0.011), (0.0, hb - 0.011)]
    revolucion(bmm, tapa, centro=(cx, cy, 0.0), seg=seg - 4)
    zc = fb + 0.0004 + (alto - fb - 0.03) * llenado
    rc = ri - 0.0006
    cont = [(0.0, zc + 0.006), (rc * 0.55, zc + 0.004), (rc, zc - 0.002), (rc, fb + 0.0019), (0.0, fb + 0.0004)]
    revolucion(bmg, cont, centro=(cx, cy, 0.0), seg=seg - 4)


def _tabla_picar(bm, ancho=0.24, alto=0.36, t=0.022, r_esq=0.03, r_hueco=0.012, dz_hueco=0.036, chaflan=0.003):
    """Tabla de picar en el plano XZ (ancho en X, alto en Z, espesor t en Y), base en z = 0, centrada en x = 0 e
    y = 0, con un agujero pasante para colgar cerca del borde de arriba. Sin booleanos: la cara se arma con
    cuadriláteros entre el contorno y el agujero, uno por ángulo visto desde el centro del agujero."""
    ax, ay, cy = ancho / 2, alto / 2, alto / 2
    hx, hz = 0.0, alto - dz_hueco
    # fracciones de los puntos del lado de arriba: repartidas en ángulo visto desde el agujero
    a_ini = math.atan2(ay + cy - hz, ax - r_esq)
    arriba = []
    m = 9
    for k in range(1, m + 1):
        phi = a_ini + (math.pi - 2 * a_ini) * k / (m + 1)
        x = (ay + cy - hz) / math.tan(phi)
        arriba.append(((ax - r_esq) - x) / (2 * (ax - r_esq)))
    lados = (arriba, [0.25, 0.5, 0.75], [0.5], [0.25, 0.5, 0.75])
    base = rr_contorno(ax, ay, r_esq, 3, lados, cy=cy)
    phis = [math.atan2(z - hz, x - hx) for x, z in base]
    capas = [(chaflan, -t / 2), (0.0, -t / 2 + chaflan), (0.0, t / 2 - chaflan), (chaflan, t / 2)]
    ext, hue = [], []
    for d, y in capas:
        ext.append([bm.verts.new((x, y, z)) for x, z in rr_contorno(ax - d, ay - d, r_esq - d, 3, lados, cy=cy)])
        rh = r_hueco + d
        hue.append([bm.verts.new((hx + rh * math.cos(p), y, hz + rh * math.sin(p))) for p in phis])
    n = len(base)
    for k in range(len(capas) - 1):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((ext[k][i], ext[k][j], ext[k + 1][j], ext[k + 1][i])).smooth = True
            bm.faces.new((hue[k][i], hue[k][j], hue[k + 1][j], hue[k + 1][i])).smooth = True
    for k in (0, len(capas) - 1):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((ext[k][i], ext[k][j], hue[k][j], hue[k][i]))
    return _verts(ext) + _verts(hue)


def set_repisa(col, prefijo, largo=1.20, fondo=0.25, semilla=7):
    """Objetos para una repisa de `largo`: tabla de picar apoyada en el muro, pila de tres platos de gres blanco con un
    bol negro encima, bol grande de gres arena y tres frascos de vidrio con tapa de madera (café, arroz, pasta).
    Base en z = 0 (cara de arriba de la tabla), entre y = 0 (muro) e y = −fondo; frente hacia −Y. Si el largo no
    alcanza, se omiten grupos (primero la tabla de picar, luego el bol grande)."""
    rnd = random.Random(semilla)
    frascos_ancho = 3 * 0.095 + 2 * 0.014
    grupos = {"tabla": 0.24, "platos": 0.22, "bol": 0.16, "frascos": frascos_ancho}
    orden = ["tabla", "platos", "bol", "frascos"]
    margen = 0.05
    for quitar in ("tabla", "bol", "platos"):
        activos = [g for g in orden if g in grupos]
        libre = largo - 2 * margen - sum(grupos[g] for g in activos)
        if libre / max(len(activos) - 1, 1) >= 0.03:
            break
        del grupos[quitar]
    activos = [g for g in orden if g in grupos]
    libre = largo - 2 * margen - sum(grupos[g] for g in activos)
    hueco = libre / max(len(activos) - 1, 1)
    yc = -fondo / 2                    # centro del fondo útil (repisa_abierta: tabla de −0,005 a −fondo + 0,005)
    bms = {k: bmesh.new() for k in ("vidrio", "madera", "blanco", "arena", "negro", "claro", "oscuro")}
    x = -largo / 2 + margen if len(activos) > 1 else -grupos[activos[0]] / 2   # un solo grupo: centrado
    for g in activos:
        w = grupos[g]
        cx = x + w / 2
        if g == "tabla":
            vs = _tabla_picar(bms["madera"])
            ang = math.radians(rnd.uniform(11.0, 13.0))
            B.transformar(bms["madera"], Matrix.Rotation(-ang, 4, "X"), vs)   # la cabeza se apoya en el muro (+Y)
            lo = Vector([min(v.co[k] for v in vs) for k in range(3)])
            hi = Vector([max(v.co[k] for v in vs) for k in range(3)])
            bmesh.ops.translate(bms["madera"], vec=Vector((cx, -0.0005 - hi.y, -lo.z)), verts=vs)
        elif g == "platos":
            perfil, z_pozo = _perfil_pila_platos(3)
            revolucion(bms["blanco"], perfil, centro=(cx, yc, 0.0), seg=30)
            revolucion(bms["negro"], _perfil_bol(0.058, 0.052, 0.005), centro=(cx + 0.004, yc - 0.003, z_pozo),
                       seg=18)
        elif g == "bol":
            revolucion(bms["arena"], _perfil_bol(0.08, 0.075), centro=(cx, yc + rnd.uniform(-0.006, 0.006), 0.0),
                       seg=22)
        elif g == "frascos":
            specs = [(0.17, 0.62, "oscuro"), (0.21, 0.78, "claro"), (0.13, 0.52, "claro")]
            fx = x + 0.0475
            for alto, llen, contenido in specs:
                alto += rnd.uniform(-0.004, 0.004)
                _frasco(bms["vidrio"], bms["madera"], bms[contenido], fx, yc + rnd.uniform(-0.012, 0.012), alto,
                        0.0475, llen)
                fx += 0.095 + 0.014
        x += w + hueco
    partes = [("Frascos", bms["vidrio"], VIDRIO), ("Madera", bms["madera"], MADERA),
              ("Platos", bms["blanco"], GRES_BLANCO), ("BolArena", bms["arena"], GRES_ARENA),
              ("BolNegro", bms["negro"], GRES_NEGRO), ("Arroz", bms["claro"], GRANO_CLARO),
              ("Cafe", bms["oscuro"], GRANO_OSCURO)]
    return _crear(col, prefijo, partes, angulo=50)


# ---------------------------------------------------------------- grifo de cocina
def grifo_cocina(col, prefijo, alto=0.40, alcance=0.22):
    """Grifo monomando de cuello de cisne negro mate. La roseta apoya en la cubierta (z = 0) centrada en el
    origen (huella = roseta Ø 58 mm); el cuello sube a `alto` y el caño llega a y = −alcance (eje del aireador);
    palanca lateral hacia +X."""
    bm = bmesh.new()
    r_cuello = 0.011
    # roseta + cuerpo del mezclador + collar giratorio, en un solo torno
    cuerpo = [(0.0, 0.0), (0.029, 0.0), (0.029, 0.0035), (0.0278, 0.0068), (0.025, 0.008), (0.0178, 0.008),
              (0.0178, 0.168), (0.0168, 0.1735), (0.014, 0.1762), (0.0118, 0.1765), (0.0118, 0.19), (0.0, 0.19)]
    revolucion(bm, cuerpo, seg=24)
    # cuello de cisne: sube, arco semicircular de radio alcance/2 y baja al cabezal
    R = alcance / 2
    zc = alto - r_cuello - R
    z_cab = zc - 0.022                          # cara de arriba del cabezal
    pts = [Vector((0.0, 0.0, 0.186))]
    for k in range(25):
        th = math.pi * k / 24
        pts.append(Vector((0.0, -R + R * math.cos(th), zc + R * math.sin(th))))
    pts.append(Vector((0.0, -alcance, z_cab - 0.004)))
    B.tubo(bm, pts, r_cuello, seg=12)
    # cabezal (rociador) con ranura y aireador rehundido
    h = 0.045
    cab = [(0.0, h), (0.0112, h), (0.0128, h - 0.003), (0.0135, h - 0.008), (0.0135, 0.013), (0.0126, 0.0122),
           (0.0126, 0.0098), (0.0135, 0.009), (0.0135, 0.002), (0.0126, 0.0), (0.0092, 0.0), (0.0092, 0.0016),
           (0.0, 0.0016)]
    revolucion(bm, cab, centro=(0.0, -alcance, z_cab - h), seg=20)
    # palanca lateral: buje y mango que sube levemente, con remate esférico
    zp = 0.122
    cilindro_ab(bm, (0.0165, 0.0, zp), (0.031, 0.0, zp), 0.0095, seg=14, canto=0.002)
    mango = [Vector((0.029, 0.0, zp)), Vector((0.060, 0.0, zp + 0.005)), Vector((0.092, 0.0, zp + 0.024))]
    tubo_codos(bm, mango, 0.0052, seg=10, radio_curva=0.03, pasos=3)
    esfera(bm, mango[-1], 0.0062, seg=10, pisos=5)
    return _crear(col, prefijo, [("Grifo", bm, NEGRO)], angulo=45)


# ================================================================ baños
R_TUBO = 0.0125         # tubería vista de 1/2" con camisa: Ø 25 mm (supuesto de diseño)
Y_TUBO = -0.050         # eje de la tubería a 5 cm del muro (roseta + niple)


def _roseta(bm, centro, eje, r=0.030, e=0.009, seg=16):
    """Roseta de muro (disco con canto redondeado) que sale de `centro` hacia `eje`."""
    perfil = [(0.0, 0.0), (r, 0.0), (r, e * 0.4), (r - e * 0.35, e * 0.85), (r - e * 0.9, e), (0.0, e)]
    return revolucion(bm, perfil, centro=centro, eje=eje, seg=seg)


def _llave_mural(bm, x, z, y_fin=-0.080, seg=20):
    """Llave de paso mural: roseta, cuerpo, bonete y manilla en cruz, a lo largo de −Y."""
    perfil = [(0.0, 0.0), (0.030, 0.0), (0.030, 0.0035), (0.0265, 0.0075), (0.021, 0.0088), (0.021, -y_fin - 0.004),
              (0.0195, -y_fin), (0.013, -y_fin), (0.013, -y_fin + 0.012), (0.0095, -y_fin + 0.0135),
              (0.0095, -y_fin + 0.029), (0.0, -y_fin + 0.029)]
    revolucion(bm, perfil, centro=(x, 0.0, z), eje=(0, -1, 0), seg=seg)
    _manilla_cruz(bm, (x, y_fin - 0.020, z), (0, -1, 0), largo=0.034, seg=8)


def ducha_expuesta(col, prefijo, z_mezclador=1.00, z_tubo=2.05, brazo=0.35, d_flor=0.25, z_cano=0.65,
                   separacion_llaves=0.30):
    """Columna de ducha de tubería negra vista. z = 0 es el piso de la tina/ducha y el muro está en y = 0; la
    columna va en x = 0. Mezclador de dos llaves en cruz a z_mezclador (con desviador al centro), tubo hasta
    z_tubo, brazo de `brazo` hacia −Y, flor de lluvia de Ø d_flor y caño de tina a z_cano. Abrazadera al muro a
    0,25 bajo el brazo."""
    bm = bmesh.new()
    r, yt, rm = R_TUBO, Y_TUBO, R_TUBO + 0.0035
    rc = 0.030                                         # radio de las curvas de la tubería
    y_flor = yt - brazo
    z_boca = z_cano - 0.040
    camino = [Vector(p) for p in ((0.0, yt - 0.15, z_boca), (0.0, yt - 0.15, z_cano), (0.0, yt, z_cano),
                                  (0.0, yt, z_tubo), (0.0, y_flor, z_tubo), (0.0, y_flor, z_tubo - 0.046))]
    tubo_codos(bm, camino, r, seg=12, radio_curva=rc, pasos=4)
    for i in range(1, len(camino) - 1):               # codos de fundición en cada curva
        codo(bm, camino[i - 1], camino[i], camino[i + 1], rm, rc, extra=0.012, seg=12, pasos=3)
    # boca del caño de tina
    boca = [(0.0, 0.004), (r - 0.0035, 0.004), (r - 0.0035, 0.0), (rm + 0.001, 0.0), (rm + 0.001, 0.016),
            (0.0, 0.016)]
    revolucion(bm, boca, centro=(0.0, yt - 0.15, z_boca - 0.012), seg=12)
    # mezclador: tubo horizontal entre las dos llaves, cruz central y desviador hacia el frente
    s = separacion_llaves / 2
    B.tubo(bm, [(-s, yt, z_mezclador), (s, yt, z_mezclador)], r, seg=12)
    for x in (-s, s):
        _llave_mural(bm, x, z_mezclador)
    cilindro_ab(bm, (-0.028, yt, z_mezclador), (0.028, yt, z_mezclador), rm, seg=12, canto=0.0015)
    cilindro_ab(bm, (0.0, yt, z_mezclador - 0.028), (0.0, yt, z_mezclador + 0.028), rm, seg=12, canto=0.0015)
    cilindro_ab(bm, (0.0, yt, z_mezclador), (0.0, yt - rm - 0.014, z_mezclador), 0.0065, seg=10)
    cilindro_ab(bm, (0.0, yt - rm - 0.012, z_mezclador), (0.0, yt - rm - 0.028, z_mezclador), 0.012, seg=12,
                canto=0.003)
    # abrazadera al muro
    zb = z_tubo - 0.25
    _roseta(bm, (0.0, 0.0, zb), (0, -1, 0), r=0.022, e=0.008, seg=16)
    cilindro_ab(bm, (0.0, -0.007, zb), (0.0, yt + r + 0.003, zb), 0.0065, seg=10)
    anillo = [(r + 0.0002, -0.010), (r + 0.0062, -0.010), (r + 0.0062, 0.010), (r + 0.0002, 0.010)]
    revolucion(bm, anillo, centro=(0.0, yt, zb), seg=16, cerrado=True)
    # flor de lluvia: rótula, cuello y disco con placa de toberas levemente rehundida
    z_top = z_tubo - 0.075
    esfera(bm, (0.0, y_flor, z_top + 0.022), 0.016, seg=12, pisos=5)
    cilindro_ab(bm, (0.0, y_flor, z_top - 0.001), (0.0, y_flor, z_top + 0.012), 0.011, seg=12)
    Rf = d_flor / 2
    flor = [(0.0, 0.0), (0.03, -0.0004), (Rf * 0.8, -0.0028), (Rf - 0.0035, -0.0038), (Rf - 0.0004, -0.0062),
            (Rf, -0.0088), (Rf - 0.0012, -0.0112), (Rf - 0.004, -0.0122), (Rf - 0.012, -0.0122),
            (Rf - 0.0132, -0.0114), (0.0, -0.0114)]
    revolucion(bm, flor, centro=(0.0, y_flor, z_top), seg=32)
    return _crear(col, prefijo, [("Ducha", bm, NEGRO)], angulo=50)


def mampara(col, prefijo, ancho=0.80, alto=1.40, espesor=0.008, perfil=0.025, fondo_perfil=0.022, travesano=0.56,
            barra_y=-0.45):
    """Mampara fija de vidrio de `espesor` con marco negro de perfil `perfil` × `fondo_perfil` y un travesaño
    horizontal aplicado (estilo acero-vidrio). En el plano y = 0, x ∈ [0, ancho] (x = 0 contra el muro), de z = 0
    a `alto`. Barra estabilizadora Ø 16 mm desde la esquina superior libre hasta el muro x = 0 en y = barra_y
    (con el signo se elige el lado), con botón en el cabezal y roseta al muro. travesano: altura del eje del
    travesaño (None: sin travesaño)."""
    bm_v, bm_m = bmesh.new(), bmesh.new()
    p, f = perfil, fondo_perfil / 2
    ch = 0.0012                                        # chaflán de los perfiles
    B.caja_redondeada(bm_m, 0.0, p, -f, f, 0.0, alto, ch, segmentos=1)                 # montante al muro
    B.caja_redondeada(bm_m, ancho - p, ancho, -f, f, 0.0, alto, ch, segmentos=1)       # montante libre
    B.caja_redondeada(bm_m, p, ancho - p, -f, f, 0.0, p, ch, segmentos=1)              # zócalo
    B.caja_redondeada(bm_m, p, ancho - p, -f, f, alto - p, alto, ch, segmentos=1)      # cabezal
    if travesano:
        a = 0.020
        for y0, y1 in ((-f, -espesor / 2), (espesor / 2, f)):   # pletinas aplicadas a cada cara del vidrio
            B.caja_redondeada(bm_m, p, ancho - p, y0, y1, travesano - a / 2, travesano + a / 2, 0.0008,
                              segmentos=1)
    B.caja(bm_v, p, ancho - p, -espesor / 2, espesor / 2, p, alto - p)
    # barra estabilizadora: botón en el cabezal, varilla y roseta al muro
    zc = alto - p / 2
    lado = -1 if barra_y < 0 else 1
    yb = lado * (f + 0.010)
    xb = ancho - 0.06
    cilindro_ab(bm_m, (xb, lado * f, zc), (xb, yb + lado * 0.002, zc), 0.011, seg=14, canto=0.002)
    _roseta(bm_m, (0.0, barra_y, zc), (1, 0, 0), r=p / 2, e=0.008, seg=14)       # no sobresale de z = alto
    esfera(bm_m, (0.0115, barra_y, zc), 0.0095, seg=12, pisos=6)                 # rótula: absorbe el ángulo
    B.tubo(bm_m, [Vector((xb, yb, zc)), Vector((0.0115, barra_y, zc))], 0.008, seg=12)
    return _crear(col, prefijo, [("Vidrio", bm_v, VIDRIO), ("Perfil", bm_m, NEGRO)], angulo=40)


def espejo_redondo(col, prefijo, diametro=0.60, seg=52):
    """Espejo redondo con aro de acero negro en «L» (banda + labio frontal) que se separa 4 mm del muro (línea de
    sombra), colgado de un listón oculto. Espalda en y = 0, centro en z = radio, frente a −Y."""
    R = diametro / 2
    rot = Matrix.Translation((0.0, 0.0, R)) @ Matrix.Rotation(math.radians(90), 4, "X")   # (x, y, d) -> (x, −d, y+R)
    bm_a, bm_e = bmesh.new(), bmesh.new()
    prof = 0.028
    aro = [(R - 0.012, 0.021), (R - 0.012, 0.0268), (R - 0.0108, prof), (R - 0.0018, prof), (R - 0.0005, 0.0272),
           (R, 0.0258), (R, 0.0055), (R - 0.0012, 0.004), (R - 0.003, 0.004), (R - 0.003, 0.021)]
    an = B.torno(bm_a, aro, seg=seg, cerrado=True)
    B.transformar(bm_a, rot, _verts(an))
    B.caja(bm_a, -0.05, 0.05, -0.004, 0.0, 2 * R - 0.10, 2 * R - 0.07)               # listón de colgar (oculto)
    luna = [(0.0, 0.021), (R - 0.0035, 0.021), (R - 0.0035, 0.004), (0.0, 0.004)]
    an = B.torno(bm_e, luna, seg=seg)
    B.transformar(bm_e, rot, _verts(an))
    return _crear(col, prefijo, [("Aro", bm_a, ACERO), ("Luna", bm_e, ESPEJO)], angulo=40)


def grifo_lavabo_mural(col, prefijo, cano=0.18, separacion=0.16):
    """Grifería mural de tubería vista: dos llaves con manilla en cruz arriba, puente horizontal con T central y
    caño de `cano` que remata en un codo corto hacia abajo con aireador. Muro en y = 0, eje del caño en z = 0,
    centrada en x = 0."""
    bm = bmesh.new()
    r, rm, yp = 0.0095, 0.013, -0.050
    s = separacion / 2
    for x in (-s, s):
        _roseta(bm, (x, 0.0, 0.0), (0, -1, 0), r=0.026, e=0.008, seg=16)
        B.tubo(bm, [(x, -0.007, 0.0), (x, yp, 0.0)], r, seg=12)
        cuerpo = [(0.0, -0.022), (0.0135, -0.022), (0.0162, -0.019), (0.0162, 0.020), (0.0148, 0.024),
                  (0.0105, 0.025), (0.0105, 0.035), (0.0078, 0.037), (0.0078, 0.046), (0.0, 0.046)]
        revolucion(bm, cuerpo, centro=(x, yp, 0.0), seg=16)
        _manilla_cruz(bm, (x, yp, 0.041), (0, 0, 1), largo=0.030, r_rayo=0.004, r_bola=0.006, seg=6, seg_bola=8)
    B.tubo(bm, [(-s, yp, 0.0), (s, yp, 0.0)], r, seg=12)
    cilindro_ab(bm, (-0.022, yp, 0.0), (0.022, yp, 0.0), rm, seg=14, canto=0.0015)
    rc = 0.016
    trazo = [Vector((0.0, yp, 0.0)), Vector((0.0, -cano, 0.0)), Vector((0.0, -cano, -0.032))]
    tubo_codos(bm, trazo, r, seg=12, radio_curva=rc, pasos=4)
    cilindro_ab(bm, (0.0, yp - rm + 0.004, 0.0), (0.0, yp - rm - 0.014, 0.0), rm, seg=14, canto=0.0015)
    aireador = [(0.0, 0.0035), (0.0082, 0.0035), (0.0082, 0.0), (0.0122, 0.0), (0.0128, 0.001), (0.0128, 0.016),
                (0.0, 0.016)]
    revolucion(bm, aireador, centro=(0.0, -cano, -0.034 - 0.010), seg=14)
    return _crear(col, prefijo, [("Griferia", bm, NEGRO)], angulo=50)


def lavabo_concreto(col, prefijo, ancho=0.46, fondo=0.34, alto=0.13, pared=0.025, espesor_fondo=0.030,
                    r_esq=0.07):
    """Lavabo de apoyo (vessel) de concreto: planta rectangular de esquinas redondeadas, cantos suavizados, pared
    de `pared` con leve desmolde y cubeta de fondo plano unido a las paredes por un acuerdo curvo de 35 mm.
    Apoya en z = 0, centrado; desagüe negro al centro del fondo (z = espesor_fondo)."""
    ax, ay = ancho / 2, fondo / 2
    perfil = []                                    # (desfase hacia adentro, z)
    rb, rt, ri, rf = 0.006, 0.008, 0.006, 0.035
    perfil += [(rb * (1 - math.sin(a)), rb * (1 - math.cos(a))) for a in (0, math.pi / 6, math.pi / 3, math.pi / 2)]
    perfil += [(rt * (1 - math.cos(a)), alto - rt + rt * math.sin(a)) for a in (0, math.pi / 6, math.pi / 3,
                                                                                  math.pi / 2)]
    perfil += [(pared - ri + ri * math.sin(a), alto - ri + ri * math.cos(a)) for a in (0, math.pi / 6, math.pi / 3,
                                                                                         math.pi / 2)]
    dm = 0.004                                     # desmolde de la pared interior
    for k in range(5):
        a = math.pi / 2 * k / 4
        perfil.append((pared + dm + rf - rf * math.cos(a), espesor_fondo + rf - rf * math.sin(a)))
    anillos = [[(x, y, z) for x, y in rr_contorno(ax - d, ay - d, max(r_esq - d, 0.012), 8)] for d, z in perfil]
    bm = bmesh.new()
    loft(bm, anillos)
    bm_d = bmesh.new()
    desague = [(0.0, 0.0012), (0.0135, 0.0012), (0.0148, 0.0021), (0.0200, 0.0023), (0.0215, 0.0012), (0.0215, 0.0),
               (0.0, 0.0)]
    revolucion(bm_d, desague, centro=(0.0, 0.0, espesor_fondo), seg=24)
    return _crear(col, prefijo, [("Lavabo", bm, CONCRETO), ("Desague", bm_d, NEGRO)], angulo=40)


# ---------------------------------------------------------------- escalera toallero
def _riel_inclinado(bm, p0, d, largo_eje, r, seg=16, pisos=4):
    """Tubo de la escalera: base cortada horizontal (apoya plana en la zapata) y remate en domo arriba."""
    u = Vector((1.0, 0.0, 0.0))
    v = d.cross(u).normalized()
    angs = [2 * math.pi * k / seg for k in range(seg)]
    base = []
    for a in angs:
        q = p0 + (u * math.cos(a) + v * math.sin(a)) * r
        base.append(q + d * ((p0.z - q.z) / d.z))
    p1 = p0 + d * largo_eje
    anillos = [base, [p1 + (u * math.cos(a) + v * math.sin(a)) * r for a in angs]]
    for j in range(1, pisos):
        b = math.pi / 2 * j / pisos
        anillos.append([p1 + d * (r * math.sin(b)) + (u * math.cos(a) + v * math.sin(a)) * (r * math.cos(b))
                        for a in angs])
    loft(bm, anillos, tapa_ini=True, polo_fin=p1 + d * r)
    return p1 + d * r


def _toalla(bm, yc, zc, r_apoyo, ancho, t, caida_atras, caida_frente, semilla, nx=6, abre=0.008):
    """Toalla doblada colgada sobre un peldaño (eje en X por (yc, zc)): tira de sección de estadio ancho × t que
    baja por atrás, abraza el peldaño y cae por delante, con ondas suaves que crecen hacia los extremos libres."""
    rnd = random.Random(semilla)
    fases = [rnd.uniform(0, 2 * math.pi) for _ in range(2)]
    R = r_apoyo + t / 2 + 0.0005                     # radio del eje de la tela alrededor del peldaño
    cam = []
    for k in range(5):                               # caída de atrás (de abajo hacia arriba)
        f = 1 - k / 5
        cam.append((yc + R + abre * f * f, zc - caida_atras * f))
    for k in range(11):                              # abrazo del peldaño (+Y -> arriba -> −Y)
        th = math.pi * k / 10
        cam.append((yc + R * math.cos(th), zc + R * math.sin(th)))
    for k in range(1, 6):                            # caída de adelante
        f = k / 5
        cam.append((yc - R - abre * 1.3 * f * f, zc - caida_frente * f))
    pts = [Vector((0.0, y, z)) for y, z in cam]
    s = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        s.append(s[-1] + (b - a).length)
    s_mid = (s[5] + s[15]) / 2
    medio_arco = (s[15] - s[5]) / 2
    h = t / 2
    sec = [(-ancho / 2 + h + (ancho - 2 * h) * i / nx, h) for i in range(nx + 1)]
    sec += [(ancho / 2 - h + h * math.cos(a), h * math.sin(a)) for a in (math.pi / 4, 0.0, -math.pi / 4)]
    sec += [(ancho / 2 - h - (ancho - 2 * h) * i / nx, -h) for i in range(nx + 1)]
    sec += [(-ancho / 2 + h + h * math.cos(a), h * math.sin(a)) for a in (-3 * math.pi / 4, math.pi, 3 * math.pi / 4)]
    X = Vector((1.0, 0.0, 0.0))
    anillos = []
    n = len(pts)
    for i in range(n):
        tg = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        nv = X.cross(tg).normalized()
        libre = min(max((abs(s[i] - s_mid) - medio_arco) / 0.12, 0.0), 1.0)
        anillo = []
        for sx, sn in sec:
            onda = 0.0045 * libre * (0.7 * math.sin(2 * math.pi * sx / 0.14 + fases[0] + s[i] * 4.0)
                                     + 0.3 * math.sin(2 * math.pi * sx / 0.06 + fases[1]))
            panza = -0.004 * libre * (1.0 - (2.0 * sx / ancho) ** 2)   # nv apunta hacia el peldaño: panza afuera
            ensancha = 1.0 + 0.02 * libre                 # la tela se abre un poco al caer
            anillo.append(pts[i] + X * (sx * ensancha) + nv * (sn + onda + panza))
        anillos.append(anillo)
    # dobladillos: anillo final encogido para redondear las puntas
    for idx, signo in ((0, -1), (n - 1, 1)):
        c = pts[idx]
        tg = (pts[min(idx + 1, n - 1)] - pts[max(idx - 1, 0)]).normalized() * signo
        nuevo = [c + tg * (h * 0.6) + X * ((q - c).dot(X) * 0.99) + ((q - c) - X * (q - c).dot(X)) * 0.45
                 for q in anillos[idx]]
        if idx == 0:
            anillos.insert(0, nuevo)
        else:
            anillos.append(nuevo)
    loft(bm, anillos)


def escalera_toallas(col, prefijo, ancho=0.50, largo=1.60, inclinacion=10.0, peldanos=5, fondo_muro=0.15):
    """Escalera toallero de tubo de acero negro (largueros Ø 25, peldaños Ø 16) apoyada en el muro con
    `inclinacion` grados; dos toallas dobladas colgando (una clara grande y una de manos carbón). Apoya en z = 0
    sobre zapatas; la cabeza toca el muro en y = +fondo_muro; centrada en x."""
    a = math.radians(inclinacion)
    d = Vector((0.0, math.sin(a), math.cos(a)))
    rr, rp, z_zap = 0.0125, 0.008, 0.006
    largo_eje = largo - rr - z_zap
    p1y = fondo_muro - rr                           # el domo toca el muro en su punto más a +Y (aprox. r)
    y0 = p1y - largo_eje * d.y
    xr = ancho / 2 - rr
    bm_a, bm_z, bm_t1, bm_t2 = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    for x in (-xr, xr):
        p0 = Vector((x, y0, z_zap))
        _riel_inclinado(bm_a, p0, d, largo_eje, rr)
        # zapata elíptica (la sección horizontal del tubo inclinado)
        anillos = []
        for e_, z in ((0.0022, 0.0), (0.0, 0.0018), (0.0, z_zap)):
            anillos.append([(x + (rr + 0.0015 - e_) * math.cos(2 * math.pi * k / 16),
                             y0 + (rr / math.cos(a) + 0.0015 - e_) * math.sin(2 * math.pi * k / 16), z)
                            for k in range(16)])
        loft(bm_z, anillos)
    paso = (largo_eje - 0.28) / (peldanos - 0.5)
    ss = [0.28 + i * paso for i in range(peldanos)]
    centros = []
    for sp in ss:
        c = Vector((0.0, y0, z_zap)) + d * sp
        centros.append(c)
        B.tubo(bm_a, [(-xr + rr * 0.6, c.y, c.z), (xr - rr * 0.6, c.y, c.z)], rp, seg=12)
    # toallas: grande en el cuarto peldaño y de manos en el segundo (caídas menores que el paso: no tocan el
    # peldaño de abajo)
    i1, i2 = min(3, peldanos - 1), min(1, peldanos - 1)
    c1, c2 = centros[i1], centros[i2]
    cae = paso * math.cos(a) - 0.035
    _toalla(bm_t1, c1.y, c1.z, rp, 0.40, 0.022, min(0.26, cae), min(0.28, cae), semilla=11)
    _toalla(bm_t2, c2.y, c2.z, rp, 0.32, 0.016, min(0.20, cae), min(0.22, cae), semilla=23)
    todos = [bm_a, bm_z, bm_t1, bm_t2]
    _, hi = _caja_env([bm_a])
    _mover(todos, (0.0, fondo_muro - hi.y, 0.0))       # la cabeza de los largueros toca el muro en y = fondo_muro
    return _crear(col, prefijo, [("Escalera", bm_a, ACERO), ("Zapatas", bm_z, NEGRO), ("Toalla", bm_t1, TOALLA),
                                 ("ToallaManos", bm_t2, TOALLA_OSCURA)], angulo=40)


def portarrollo(col, prefijo, ancho_rollo=0.10, r_rollo=0.058):
    """Portarrollo de tubería negra (roseta, niple, codo y eje con tope) con rollo de papel colgando del eje y
    una punta de papel. Muro en y = 0; centrado en x; lo más bajo (la punta del papel) en z = 0. El eje del
    portarrollo (centro de la roseta) queda en z = r_rollo + 0,0532 (0,111 con los valores por defecto)."""
    bm_n, bm_r, bm_p = bmesh.new(), bmesh.new(), bmesh.new()
    r, y_eje, rc = 0.008, -0.078, 0.018
    x_fin = 0.035 + ancho_rollo + 0.018
    _roseta(bm_n, (0.0, 0.0, 0.0), (0, -1, 0), r=0.025, e=0.008, seg=20)
    tubo_codos(bm_n, [Vector((0.0, -0.006, 0.0)), Vector((0.0, y_eje, 0.0)), Vector((x_fin, y_eje, 0.0))], r,
               seg=10, radio_curva=rc, pasos=4)
    tope = [(0.0, 0.0), (0.0105, 0.0), (0.0105, 0.0055), (0.0088, 0.0098), (0.0, 0.0112)]
    revolucion(bm_n, tope, centro=(x_fin - 0.004, y_eje, 0.0), eje=(1, 0, 0), seg=12)
    # rollo: el tubo de cartón (r 21 mm) cuelga del eje: su cara interior superior toca el tubo
    ri_c, ro_c = 0.0212, 0.0226
    zc = r - ri_c
    W = ancho_rollo
    rollo = [(ri_c, 0.0), (ro_c, 0.0), (r_rollo, 0.0), (r_rollo, W), (ro_c, W), (ri_c, W)]
    x0 = 0.035
    revolucion(bm_r, rollo, centro=(x0, y_eje, zc), eje=(1, 0, 0), seg=30, cerrado=True)
    for fc in bm_r.faces:                            # caras del tubo de cartón -> material 1
        if all(((v.co.y - y_eje) ** 2 + (v.co.z - zc) ** 2) ** 0.5 < ro_c + 1e-5 for v in fc.verts):
            fc.material_index = 1
    # punta de papel que cae tangente por delante del rollo
    yp = y_eje - r_rollo - 0.0004
    barra_plana(bm_p, [(x0 + W / 2, yp, zc + 0.004), (x0 + W / 2, yp, zc - r_rollo), (x0 + W / 2, yp - 0.0025,
                                                                                         zc - r_rollo - 0.040)],
                W - 0.003, 0.0006, radio_curva=0.03, pasos=3)
    lo, hi = _caja_env([bm_n, bm_r, bm_p])
    _mover([bm_n, bm_r, bm_p], (-(lo.x + hi.x) / 2, 0.0, -lo.z))
    return _crear(col, prefijo, [("Soporte", bm_n, NEGRO), ("Rollo", bm_r, (PAPEL, CARTON)),
                                 ("PuntaPapel", bm_p, PAPEL)], angulo=40)


PIEZAS = ("repisa_abierta", "set_repisa", "grifo_cocina", "ducha_expuesta", "mampara", "espejo_redondo",
          "grifo_lavabo_mural", "lavabo_concreto", "escalera_toallas", "portarrollo")
