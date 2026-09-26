"""Hall, cocina y baño: piezas de la decoración industrial (versión 2; docs/deco-industrial.md, «Hall, cocina y baño»).

Piezas (cada una `nombre(col, prefijo, **parámetros) -> list[bpy.types.Object]`):
- banca_entrada: banca de recibidor de cuatro listones de roble ahumado con junta de sombra, sobre marco soldado de
  tubo cuadrado de acero negro de 20 mm, con repisa baja de varillas para zapatos.
- perchero_mural: tabla de roble con cuatro ganchos de cañería de fierro negro (flange atornillado, niple, codo de
  90° hacia arriba y tapón) y, encima, una repisa angosta de roble sobre dos escuadras de cañería.
- riel_focos: riel sobrepuesto negro en el cielo, con tapa, caja de alimentación y n focos cilíndricos orientables
  (adaptador, vástago, horquilla y perillas); cada foco lleva su disco emisivo en un objeto aparte
  (`{prefijo}_Luz1`, `_Luz2`, ...) para que la fase 4 le ponga su propia luz.
- felpudo: felpudo de fibra (textura de yute) en una bandeja de caucho negro con canto biselado.
- riel_utensilios: barra mural de cocina de Ø 12 mm con dos soportes y tapas, cinco ganchos en S y cuatro utensilios
  colgando (espátula y batidor con mango de roble; cucharón y pinzas de acero inoxidable).
- toallero_barra: toallero mural de barra doblada de Ø 16 mm con dos rosetas y una toalla doblada colgando.

Convenciones (docs/deco-industrial.md): metros, Z arriba, frente hacia −Y; todos los objetos con origen (0, 0, 0)
y sin rotación; un objeto por material (salvo las luces del riel, una por foco). Banca y felpudo: huella centrada
en el origen y apoyados en z = 0. Piezas murales: cara de atrás en y = 0 (perchero: base de la tabla en z = 0;
riel de utensilios y toallero: eje de la barra en z = 0, lo colgado baja hacia −Z). Riel de focos (de cielo): origen
en el cielo (z = 0), el riel apoyado bajo z = 0 y todo colgando hacia −Z. Sin booleanos ni subdivisión: tornos,
barridos de sección variable, lofts y cajas de bmesh. Determinista (la toalla usa semilla fija), API de bpy 3.6.

Materiales nuevos que registra este módulo (depto_geom.MATERIALES.setdefault; sólo color, sin textura):
    Depto_Mat_Caucho: goma negra del borde del felpudo.
    Depto_Mat_AceroInox: acero inoxidable de los utensilios (cabezas, mangos de acero, virola y alambres).
El felpudo usa Depto_Mat_Alfombra, que es el material con la textura de yute en build/deco_paleta.py (no existe un
Depto_Mat_Yute). El reflector de los focos usa Depto_Mat_PantallaInterior (esmalte claro de las pantallas).
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector

import deco_base as B
import deco_cocina_bano as CB
import deco_objetos as O
import depto_geom as G

TAU = 2 * math.pi

# ---------------------------------------------------------------- materiales (nombres de depto_geom.MATERIALES)
MADERA = "Depto_Mat_MaderaMueble"        # roble ahumado con textura
ACERO = "Depto_Mat_AceroNegro"           # acero pavonado con textura (marcos, cañería, barras)
NEGRO = "Depto_Mat_MetalNegroMate"       # luminarias
REFLECTOR = "Depto_Mat_PantallaInterior"  # aro reflector claro dentro de cada foco
LUZ = "Depto_Mat_Bombilla"               # emisivo: la fase 4 pone una luz en el centroide de cada objeto que lo usa
TOALLA = "Depto_Mat_Toalla"
YUTE = "Depto_Mat_Alfombra"              # textura `yute` (deco_paleta): la fibra del felpudo
CAUCHO = "Depto_Mat_Caucho"              # nuevo
INOX = "Depto_Mat_AceroInox"             # nuevo

# Nuevos (color sRGB, rugosidad, metálico, alfa), como el resto de depto_geom.MATERIALES. Supuestos de diseño.
G.MATERIALES.setdefault(CAUCHO, ((0.055, 0.055, 0.055), 0.80, 0.0, 1.0))   # goma negra satinada
G.MATERIALES.setdefault(INOX, ((0.80, 0.80, 0.79), 0.28, 1.0, 1.0))        # inoxidable cepillado

# Topes de triángulos por pieza (docs/deco-industrial.md, «Hall, cocina y baño»)
TOPES = dict(banca_entrada=1500, perchero_mural=2000, riel_focos=1800, felpudo=300, riel_utensilios=2000,
             toallero_barra=1500)
PIEZAS = tuple(TOPES)


# ================================================================ ayudas de modelado
def _barrido(bm, puntos, radios, seg=10, giro=0.0, tapa_ini=True, tapa_fin=True, arriba=None):
    """Tubo de sección circular con radio propio en cada punto de una polilínea 3D (marcos por transporte paralelo:
    sin torsión). Dos puntos iguales seguidos con radios distintos dan un escalón plano (la boca de un fitting); radio
    0 en un extremo da un polo (remate en domo). arriba: dirección de referencia del primer marco (para trazados
    planos conviene la normal del plano). Devuelve los anillos."""
    P = [Vector(p) for p in puntos]
    n = len(P)
    tang = []
    for i in range(n):
        ant = next((P[j] for j in range(i - 1, -1, -1) if (P[j] - P[i]).length > 1e-9), None)
        sig = next((P[j] for j in range(i + 1, n) if (P[j] - P[i]).length > 1e-9), None)
        if ant is None:
            d = sig - P[i]
        elif sig is None:
            d = P[i] - ant
        else:
            d = (sig - P[i]).normalized() + (P[i] - ant).normalized()
            if d.length < 1e-9:
                d = sig - P[i]
        tang.append(d.normalized())
    ref = Vector(arriba) if arriba else (Vector((0, 0, 1)) if abs(tang[0].z) < 0.9 else Vector((1, 0, 0)))
    nor = (ref - tang[0] * ref.dot(tang[0])).normalized()
    anillos = []
    for i in range(n):
        if i > 0:
            nor = tang[i - 1].rotation_difference(tang[i]) @ nor
            nor = (nor - tang[i] * nor.dot(tang[i])).normalized()
        bi = tang[i].cross(nor)
        r = radios[i]
        if r < 1e-7:
            anillos.append([bm.verts.new(P[i])])
            continue
        anillos.append([bm.verts.new(P[i] + (nor * math.cos(a) + bi * math.sin(a)) * r)
                        for a in (TAU * k / seg + math.radians(giro) for k in range(seg))])
    for a, b in zip(anillos[:-1], anillos[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        for k in range(seg):
            j = (k + 1) % seg
            if len(a) == 1:
                f = bm.faces.new((a[0], b[j], b[k]))
            elif len(b) == 1:
                f = bm.faces.new((a[k], a[j], b[0]))
            else:
                f = bm.faces.new((a[k], a[j], b[j], b[k]))
            f.smooth = True
    if tapa_ini and len(anillos[0]) > 1:
        bm.faces.new(list(reversed(anillos[0])))
    if tapa_fin and len(anillos[-1]) > 1:
        bm.faces.new(anillos[-1])
    return anillos


def _prisma_x(bm, poligono, x0, x1):
    """Prisma a lo largo de X de sección `poligono` [(y, z), ...] (puede ser cóncava). Caras laterales suaves: el
    ángulo de suavizado del objeto decide qué aristas quedan vivas."""
    a = [bm.verts.new((x0, y, z)) for y, z in poligono]
    b = [bm.verts.new((x1, y, z)) for y, z in poligono]
    n = len(poligono)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i])).smooth = True
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)


def _cinta(bm, puntos, anchos, espesor, lateral=(1.0, 0.0, 0.0)):
    """Fleje de sección rectangular de ancho variable (según `lateral`) y `espesor` (en el plano del recorrido),
    barrido por una polilínea plana normal a `lateral`. anchos: uno por punto."""
    L = Vector(lateral).normalized()
    P = [Vector(p) for p in puntos]
    n = len(P)
    anillos = []
    for i in range(n):
        t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        nv = L.cross(t).normalized()
        w = anchos[i] / 2
        anillos.append([P[i] + L * (sx * w) + nv * (sy * espesor / 2)
                        for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))])
    return CB.loft(bm, anillos)


def _placa_ojal(bm, R, r_ojal, z_c, ancho_inf, z_inf, espesor, chaflan=0.0, n=10, y=0.0):
    """Placa plana en el plano XZ (espesor en Y, centrada en y) con el extremo de arriba semicircular de radio R y un
    ojal pasante de radio r_ojal concéntrico en (0, z_c); los costados bajan rectos angostándose hasta ancho_inf en
    z_inf (canto de abajo recto). chaflan > 0: el canto lleva una arista al medio del espesor (tres capas; con el
    suavizado se ve redondeado); 0: canto recto. Sin booleanos: el contorno y el ojal se unen por rayos desde el
    centro del ojal (n direcciones parejas más las dos esquinas de abajo). Caras de frente y espalda planas."""
    wb = ancho_inf / 2
    angulos = [TAU * k / n for k in range(n)]
    for sx in (1, -1):                                   # esquinas de abajo: tienen que ser puntos del contorno
        a = math.atan2(z_inf - z_c, sx * wb) % TAU
        if all(abs(a - b) > 1e-3 for b in angulos):
            angulos.append(a)
    angulos.sort()

    def contorno(phi, d):
        Rd, wd, zi = R - d, wb - d, z_inf + d
        s, c = math.sin(phi), math.cos(phi)
        if s >= -1e-9:                                   # semicírculo de arriba
            return (Rd * c, z_c + Rd * s)
        x = (zi - z_c) / s * c                           # canto de abajo
        if abs(x) <= wd + 1e-9:
            return (x, zi)
        sg = 1.0 if c > 0 else -1.0                      # costado de (sg Rd, z_c) a (sg wd, zi)
        u = sg * Rd / ((zi - z_c) * c / s - sg * (wd - Rd))
        return (sg * Rd + sg * (wd - Rd) * u, z_c + (zi - z_c) * u)

    capas = ([(chaflan, y - espesor / 2), (0.0, y), (chaflan, y + espesor / 2)] if chaflan > 0
             else [(0.0, y - espesor / 2), (0.0, y + espesor / 2)])
    ext, hue = [], []
    for d, yy in capas:
        ext.append([bm.verts.new((x, yy, z)) for x, z in (contorno(p, d) for p in angulos)])
        ro = r_ojal + d
        hue.append([bm.verts.new((ro * math.cos(p), yy, z_c + ro * math.sin(p))) for p in angulos])
    m = len(angulos)
    for k in range(len(capas) - 1):
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((ext[k][i], ext[k][j], ext[k + 1][j], ext[k + 1][i])).smooth = True
            bm.faces.new((hue[k][j], hue[k][i], hue[k + 1][i], hue[k + 1][j])).smooth = True
    for k in (0, len(capas) - 1):
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((ext[k][i], ext[k][j], hue[k][j], hue[k][i]))


def _suave(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ================================================================ 1. banca de entrada
BANCA = dict(
    tubo=0.020,          # diseño (pedido): tubo cuadrado de acero de 20 mm
    r_tubo=0.0025,       # supuesto: canto de laminación del tubo (a tope se ve la junta soldada)
    tablero=0.030,       # diseño (pedido): roble de 30 mm
    listones=4,          # diseño: cuatro listones con junta de sombra
    junta=0.006,         # diseño: junta de sombra de 6 mm
    canto=0.004,         # diseño: canto suavizado de los listones
    vuelo=0.010,         # diseño: el asiento vuela 1 cm sobre el marco (como el velador)
    z_repisa=0.10,       # diseño (pedido): cara de arriba de las varillas a z ≈ 0,10
    varilla=0.012,       # supuesto: varilla lisa de 12 mm (como las patas hairpin)
    n_varillas=5,        # diseño: repisa de cinco varillas
)


def banca_entrada(col, prefijo, ancho=0.80, fondo=0.32, alto=0.46):
    """Banca de recibidor: asiento de cuatro listones de roble ahumado de 30 mm (junta de sombra de 6 mm, cantos
    suavizados) que vuela 1 cm sobre un marco soldado de tubo cuadrado de acero negro de 20 mm (cuatro patas,
    largueros y travesaños bajo el asiento), y repisa baja para zapatos de cinco varillas de 12 mm apoyadas en dos
    travesaños bajos (cara de arriba de las varillas a z ≈ 0,10). Huella de ancho × fondo centrada, apoyada en
    z = 0, frente hacia −Y. ≈ 1 300 triángulos (tope 1 500)."""
    K = BANCA
    e, r = K["tubo"], K["r_tubo"]
    fx, fy = ancho / 2 - K["vuelo"], fondo / 2 - K["vuelo"]
    zs = alto - K["tablero"]                               # cara de abajo del asiento = cara de arriba del marco
    rv = K["varilla"] / 2
    zr = K["z_repisa"] - K["varilla"]                      # cara de arriba de los travesaños bajos
    bm = bmesh.new()

    def tubo(x0, x1, y0, y1, z0, z1):
        B.caja_redondeada(bm, x0, x1, y0, y1, z0, z1, r, segmentos=1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            tubo(sx * (fx - e), sx * fx, sy * (fy - e), sy * fy, 0.0, zs)                # patas
    for sy in (-1, 1):
        tubo(-(fx - e), fx - e, sy * (fy - e), sy * fy, zs - e, zs)                     # largueros del asiento
    for sx in (-1, 1):
        tubo(sx * (fx - e), sx * fx, -(fy - e), fy - e, zs - e, zs)                     # travesaños altos
        tubo(sx * (fx - e), sx * fx, -(fy - e), fy - e, zr - e, zr)                     # travesaños de la repisa
    # varillas de la repisa: a lo largo de X, apoyadas (soldadas) sobre los travesaños bajos
    n = K["n_varillas"]
    yr = fy - e - rv - 0.006                               # 6 mm de luz a las patas
    zv = zr + rv - 0.0004
    for k in range(n):
        y = -yr + 2 * yr * k / (n - 1)
        CB.cilindro_ab(bm, (-(fx - 0.004), y, zv), (fx - 0.004, y, zv), rv, seg=8, canto=0.002, n=1)
    marco = B.objeto(col, f"{prefijo}_Marco", bm, ACERO, angulo_suave=40)

    bm = bmesh.new()
    nl, g, c = K["listones"], K["junta"], K["canto"]
    w = (fondo - (nl - 1) * g) / nl
    for k in range(nl):
        y0 = -fondo / 2 + k * (w + g)
        CB.losa_rr(bm, ancho / 2, w / 2, c + 0.003, zs, alto, c, n_esq=2, n_canto=2, cy=y0 + w / 2)
    asiento = B.objeto(col, f"{prefijo}_Asiento", bm, MADERA, angulo_suave=50)
    return [asiento, marco]


# ================================================================ 2. perchero mural de cañería
CANERIA = dict(
    r=0.0107,            # cañería de 1/2" (Ø exterior 21,3 mm, norma)
    r_fit=0.0148,        # supuesto: codo y tapa de fundición maleable de 1/2" (Ø ≈ 30 mm)
    r_curva=0.022,       # supuesto: radio al eje del codo de 90°
    niple=0.025,         # diseño: niple visible del gancho (el gancho avanza ≈ 0,10 desde el muro)
    tapa=0.015,          # supuesto: tapón de 1/2" roscado en el codo
    seg=8,               # lados de la cañería (tope de triángulos)
)
BRIDA = dict(
    R=0.031,             # supuesto: flange de piso de 1/2" (Ø 62 mm)
    e=0.0055,            # espesor de la placa
    r_cubo=0.0155, h=0.017,   # cubo roscado
    tornillo=(0.0042, 0.0022),   # cabeza redonda Ø 8,4 × 2,2 mm
    tornillos=3,         # supuesto: flange de 1/2" de tres agujeros
    seg=16, seg_cubo=8,  # placa redonda; el cubo va con los lados de la cañería
)
PERCHERO = dict(
    tabla=(0.14, 0.025),     # diseño (pedido): tabla de ancho × 0,14 × 0,025 contra el muro
    repisa=(0.20, 0.028),    # diseño (pedido): repisa de 0,20 de fondo; supuesto: tabla de 28 mm
    alto=0.40,               # diseño (pedido): alto total ≈ 0,40 (cara de arriba de la repisa)
    z_gancho=0.07,           # diseño: ganchos al medio de la tabla
    z_escuadra=0.26,         # diseño: eje del brazo horizontal de las escuadras
    y_escuadra=-0.14,        # diseño: flange de la repisa a 6 cm del canto
    canto=0.003,             # diseño: canto matado de las tablas
)


def _brida(bm, centro, eje, fase=90.0):
    """Flange de fierro atornillado (floor flange): placa de Ø 2R cuya cara de atrás apoya en `centro`, con la cara de
    arriba apenas cónica, cubo roscado hacia `eje` y tornillos de cabeza redonda en la placa. Devuelve el alto del
    cubo."""
    K = BRIDA
    R, e, rc, h = K["R"], K["e"], K["r_cubo"], K["h"]
    antes = set(bm.verts)
    O._torno(bm, [(0.0, 0.0), (R, 0.0), (R, e), (0.0, e + 0.0016)], K["seg"])
    O._torno(bm, [(0.0, e - 0.0004), (rc, e - 0.0004), (rc, h), (0.0, h)], K["seg_cubo"])
    rs, hs = K["tornillo"]
    rt = (R + rc) / 2 + 0.0005
    zt = e + 0.0016 * (1 - rt / R) - 0.0003                           # sobre la cara cónica de la placa
    n = K["tornillos"]
    for k in range(n):
        a = math.radians(fase + 360.0 * k / n)
        CB.revolucion(bm, [(0.0, 0.0), (rs, 0.0), (0.0, hs)], centro=(rt * math.cos(a), rt * math.sin(a), zt),
                      seg=5)
    B.transformar(bm, O._M(centro, eje), [v for v in bm.verts if v not in antes])
    return h


def _gancho_caneria(bm, x, y_base, z0):
    """Gancho de cañería sobre la cara y = y_base (hacia −Y): flange, niple, codo de 90° hacia arriba y tapón de
    remate (0,8 mm más grueso que el codo, así se lee la junta) con canto achaflanado y cara levemente abombada. Un
    solo barrido de radio variable: los escalones son las bocas de los fittings."""
    C = CANERIA
    h = _brida(bm, (x, y_base, z0), (0.0, -1.0, 0.0))
    rn, rf, Rb = C["r"], C["r_fit"], C["r_curva"]
    y1 = y_base - h - C["niple"]
    pts = [Vector((x, y_base - h + 0.003, z0)), Vector((x, y1, z0))]
    rad = [rn, rn]
    for a in (0.0, 22.5, 45.0, 67.5, 90.0):              # codo: de −Y a +Z
        t = math.radians(a)
        pts.append(Vector((x, y1 - Rb * math.sin(t), z0 + Rb - Rb * math.cos(t))))
        rad.append(rf)
    top = pts[-1]
    rt = rf + 0.0008
    z2 = top.z + C["tapa"]
    for z, rr in ((top.z, rt), (z2 - 0.003, rt), (z2, rt - 0.003), (z2 + 0.0018, 0.0)):
        pts.append(Vector((x, top.y, z)))
        rad.append(rr)
    _barrido(bm, pts, rad, seg=C["seg"], arriba=(1.0, 0.0, 0.0))


def _escuadra_caneria(bm, x, z_brazo, y_vertical, z_repisa):
    """Escuadra de cañería: flange en el muro (y = 0), brazo horizontal hacia −Y, codo hacia arriba y niple vertical
    hasta un flange atornillado bajo la repisa (cara de abajo en z_repisa)."""
    C = CANERIA
    h = _brida(bm, (x, 0.0, z_brazo), (0.0, -1.0, 0.0))
    h2 = _brida(bm, (x, y_vertical, z_repisa), (0.0, 0.0, -1.0), fase=30.0)
    rn, rf, Rb = C["r"], C["r_fit"], C["r_curva"]
    y1 = y_vertical + Rb
    pts = [Vector((x, -h + 0.003, z_brazo)), Vector((x, y1, z_brazo))]
    rad = [rn, rn]
    for a in (0, 30, 60, 90):
        t = math.radians(a)
        pts.append(Vector((x, y1 - Rb * math.sin(t), z_brazo + Rb - Rb * math.cos(t))))
        rad.append(rf)
    top = pts[-1]
    pts += [top.copy(), Vector((x, y_vertical, z_repisa - h2 + 0.003))]
    rad += [rn, rn]
    _barrido(bm, pts, rad, seg=C["seg"], arriba=(1.0, 0.0, 0.0))


def perchero_mural(col, prefijo, ancho=0.80):
    """Perchero mural de cañería: tabla de roble ahumado de ancho × 0,14 × 0,025 contra el muro (espalda en y = 0,
    base en z = 0) con cuatro ganchos de cañería de fierro negro de 1/2" (flange de Ø 62 de tres tornillos, niple,
    codo de 90° hacia arriba y tapón; avanzan ≈ 0,10) y, encima, una repisa angosta de roble de 0,20 de fondo
    (cara de arriba a 0,40) sobre dos escuadras de cañería alineadas con los ganchos de los extremos (flange al
    muro, brazo, codo, niple y flange bajo la repisa). Centrado en X. ≈ 1 950 triángulos (tope 2 000)."""
    K = PERCHERO
    alto_t, esp_t = K["tabla"]
    fondo_r, esp_r = K["repisa"]
    c = K["canto"]
    bm = bmesh.new()
    B.caja_redondeada(bm, -ancho / 2, ancho / 2, -esp_t, 0.0, 0.0, alto_t, c, segmentos=1)
    z_rep = K["alto"] - esp_r
    B.caja_redondeada(bm, -ancho / 2, ancho / 2, -fondo_r, 0.0, z_rep, K["alto"], c, segmentos=1)
    madera = B.objeto(col, f"{prefijo}_Madera", bm, MADERA, angulo_suave=40)

    bm = bmesh.new()
    xs = [-ancho / 2 + ancho / 8 + k * ancho / 4 for k in range(4)]        # diseño: repartidos a ancho/4
    for x in xs:
        _gancho_caneria(bm, x, -esp_t, K["z_gancho"])
    for x in (xs[0], xs[-1]):
        _escuadra_caneria(bm, x, K["z_escuadra"], K["y_escuadra"], z_rep)
    caneria = B.objeto(col, f"{prefijo}_Caneria", bm, ACERO, angulo_suave=45)
    return [madera, caneria]


# ================================================================ 3. riel de focos (cielo)
RIEL = dict(
    ancho=0.035, alto=0.035,     # diseño (pedido): perfil de ≈ 35 × 35 mm
    r_canto=0.004,               # diseño: cantos inferiores redondeados
    ranura=(0.012, 0.0045),      # supuesto: ranura de contactos de 12 mm en la cara de abajo
    tapa=0.004,                  # diseño: tapa de extremo de 4 mm
    caja=(0.075, 0.044, 0.040),  # supuesto: caja de alimentación (largo, ancho, alto) en el extremo −X
)
FOCO = dict(
    r=0.030, largo=0.12,         # diseño (pedido): foco cilíndrico Ø 0,06 × 0,12
    pivote=0.045,                # diseño: pivote a 45 mm de la espalda del cilindro
    rebaje=0.026,                # diseño: el disco queda 26 mm adentro (antideslumbre)
    reflector=0.006,             # diseño: aro reflector cónico de 6 mm de profundidad
    r_luz=0.0135,                # diseño: disco emisivo Ø 27 mm
    pared=0.0022,                # supuesto: pared de aluminio de 2,2 mm
    seg=24,
)
ADAPTADOR = (0.056, 0.030, 0.018)    # supuesto: adaptador de riel (largo X, ancho Y, alto Z)
VASTAGO = (0.0065, 0.008)            # supuesto: vástago giratorio (radio, largo)
HORQUILLA = (0.012, 0.003, 0.001)    # supuesto: pletina de la horquilla (ancho, espesor) y luz al cilindro
PERILLA = (0.0085, 0.0045)           # supuesto: perilla de apriete (radio, salida)


def _seccion_riel(pasos=3):
    """Sección (y, z) del perfil: cantos de abajo redondeados y ranura de contactos al centro de la cara de abajo."""
    h, H, rc = RIEL["ancho"] / 2, RIEL["alto"], RIEL["r_canto"]
    s, ds = RIEL["ranura"][0] / 2, RIEL["ranura"][1]
    pts = [(-h, 0.0)]
    for k in range(pasos + 1):
        a = math.radians(180 + 90 * k / pasos)
        pts.append((-h + rc + rc * math.cos(a), -H + rc + rc * math.sin(a)))
    pts += [(-s, -H), (-s, -H + ds), (s, -H + ds), (s, -H)]
    for k in range(pasos + 1):
        a = math.radians(270 + 90 * k / pasos)
        pts.append((h - rc + rc * math.cos(a), -H + rc + rc * math.sin(a)))
    pts.append((h, 0.0))
    return pts


def riel_focos(col, prefijo, largo=1.00, n=3, giros=None, inclinaciones=None):
    """Riel sobrepuesto de focos para el cielo: perfil negro de 35 × 35 mm con ranura de contactos, de `largo` a lo
    largo de X y centrado (la caja de alimentación ocupa el extremo −X y una tapa cierra el +X), con n focos
    cilíndricos negros de Ø 0,06 × 0,12 repartidos por igual. Cada foco: adaptador al riel con palanca de traba,
    vástago, horquilla de pletina con dos perillas de apriete y cilindro con rebaje antideslumbre, aro reflector
    claro y, al fondo, un disco emisivo en un objeto propio (`{prefijo}_Luz1`, ...). giros: grados alrededor de Z
    (0 = apunta hacia −Y; por defecto alternados 0, 180, 0...); inclinaciones: grados desde la vertical (30 por
    defecto). Origen en el cielo (z = 0), todo cuelga hacia −Z: punto más bajo ≈ −0,20 con 30° (propiedad `caida_m`
    del objeto Metal). ≈ 140 + 535 n triángulos (tope 1 800 con n = 3)."""
    giros = [float(g) for g in giros] if giros is not None else [0.0 if i % 2 == 0 else 180.0 for i in range(n)]
    incl = [float(a) for a in inclinaciones] if inclinaciones is not None else [30.0] * n
    assert len(giros) >= n and len(incl) >= n, "giros e inclinaciones: uno por foco"
    R, F = RIEL, FOCO
    H = R["alto"]
    metal = O._Malla()
    i_negro, i_refl = metal.indice(NEGRO), metal.indice(REFLECTOR)
    x_caja = -largo / 2 + R["caja"][0]
    x_tapa = largo / 2 - R["tapa"]
    with metal.parte(NEGRO) as bm:
        _prisma_x(bm, _seccion_riel(), x_caja - 0.003, x_tapa + 0.001)
        lc, ac, hc = R["caja"]
        B.caja_redondeada(bm, -largo / 2, x_caja, -ac / 2, ac / 2, -hc, 0.0, 0.003, segmentos=1)
        B.caja_redondeada(bm, x_tapa, largo / 2, -R["ancho"] / 2 - 0.0008, R["ancho"] / 2 + 0.0008, -H - 0.0008,
                          0.0, 0.0015, segmentos=1)
    # geometría común de los focos
    ax, ay, az = ADAPTADOR
    rv, lv = VASTAGO
    ancho_h, t, luz = HORQUILLA
    rk, hk = PERILLA
    r, L, a = F["r"], F["largo"], F["pivote"]
    z_top_h = -H - az - lv                                   # cara de arriba de la horquilla
    hf = math.hypot(a, r) + 0.004                            # la espalda del cilindro barre una esfera de ese radio
    z_p = z_top_h - t - hf                                   # eje de giro (pivote)
    xa = r + luz + t / 2                                     # eje de los brazos de la horquilla
    zf = -(L - a)                                            # boca del cilindro (coordenada local del foco)
    zr = zf + F["rebaje"]
    zl = zr + F["reflector"]
    perfil = [(0.0, a), (r - 0.0025, a), (r, a - 0.0025), (r, zf), (r - F["pared"], zf), (r - F["pared"], zr),
              (F["r_luz"] + 0.0012, zl), (0.0, zl)]
    indices = [i_negro] * 5 + [i_refl] * 2
    xs_a, xs_b = x_caja, x_tapa
    luces = []
    for i in range(n):
        xi = xs_a + (xs_b - xs_a) * (i + 0.5) / n
        with metal.parte(NEGRO) as bm:
            B.caja_redondeada(bm, xi - ax / 2, xi + ax / 2, -ay / 2, ay / 2, -H - az, -H, 0.002, segmentos=1)
            B.caja(bm, xi + 0.008, xi + 0.020, ay / 2 - 0.0005, ay / 2 + 0.0035, -H - az + 0.004, -H - 0.004)
            B.cilindro(bm, xi, 0.0, z_top_h - 0.0005, -H - az + 0.001, rv, seg=10)
        Mh = Matrix.Translation((xi, 0.0, z_p)) @ Matrix.Rotation(math.radians(giros[i]), 4, "Z")
        with metal.parte(NEGRO, Mh) as bm:
            CB.barra_plana(bm, [(-xa, 0.0, 0.0), (-xa, 0.0, hf + t / 2), (xa, 0.0, hf + t / 2), (xa, 0.0, 0.0)],
                           ancho_h, t, radio_curva=0.006, pasos=2, lateral=(0.0, 1.0, 0.0))
            for s in (-1, 1):
                O._torno_eje(bm, [(0.0, -t + 0.0008), (rk, -t + 0.0008), (rk, hk), (0.0, hk)],
                             (s * (xa + t / 2), 0.0, 0.0), (s, 0.0, 0.0), 10)
        Mc = Mh @ Matrix.Rotation(math.radians(-incl[i]), 4, "X")
        with metal.parte(None, Mc) as bm:
            O._torno(bm, perfil, F["seg"], indices=indices)
        # disco emisivo: casquete apenas cóncavo (0,3 mm) mirando a la boca; abierto, para que la luz de la fase 4
        # (en su centroide) quede delante de la superficie y no dentro de un volumen cerrado
        bm = bmesh.new()
        nl = 16
        borde = [bm.verts.new(Mc @ Vector((F["r_luz"] * math.cos(TAU * k / nl), F["r_luz"] * math.sin(TAU * k / nl),
                                           zl - 0.0004))) for k in range(nl)]
        centro = bm.verts.new(Mc @ Vector((0.0, 0.0, zl - 0.0001)))
        for k in range(nl):
            bm.faces.new((borde[(k + 1) % nl], borde[k], centro))
        luces.append(B.objeto(col, f"{prefijo}_Luz{i + 1}", bm, LUZ, recalc=False))
    lo, _ = O._caja_mallas([metal])
    obj = metal.crear(col, f"{prefijo}_Metal", angulo=40, props={"caida_m": round(-lo.z, 4)})
    return [obj] + luces


# ================================================================ 4. felpudo
FELPUDO = dict(
    borde=0.025,         # diseño: borde de goma de 25 mm
    rampa=0.010,         # diseño: el borde baja en rampa de 10 mm hasta el piso (no se tropieza)
    r_esq=0.045,         # diseño: esquinas redondeadas en planta
    z_borde=0.0095,      # diseño: el labio de goma queda 5,5 mm bajo la fibra
    z_fondo=0.004,       # supuesto: base de goma de 4 mm bajo la fibra
    canto=0.0025,        # diseño: canto suavizado de la fibra
)


def felpudo(col, prefijo, ancho=0.70, largo=0.45, alto=0.015):
    """Felpudo de fibra (textura de yute) encajado en una bandeja de caucho negro: base de 4 mm y borde de 25 mm que
    baja en rampa hasta el piso desde un labio a 9,5 mm; la fibra sobresale hasta `alto` con cantos suaves. Esquinas redondeadas en
    planta. Huella ancho × largo centrada, apoyado en z = 0. ≈ 280 triángulos (tope 300)."""
    K = FELPUDO
    ax, ay = ancho / 2, largo / 2
    b, rq = K["borde"], K["r_esq"]
    zb = min(K["z_borde"], alto * 0.63)
    zf = min(K["z_fondo"], zb * 0.45)
    bm = bmesh.new()
    perfil = [(0.0, 0.0), (K["rampa"], zb), (b, zb), (b, zf)]
    anillos = [[(x, y, z) for x, y in CB.rr_contorno(ax - d, ay - d, rq - d, 4)] for d, z in perfil]
    CB.loft(bm, anillos)
    borde = B.objeto(col, f"{prefijo}_Borde", bm, CAUCHO, angulo_suave=50)
    bm = bmesh.new()
    hueco = b + 0.0008
    CB.losa_rr(bm, ax - hueco, ay - hueco, rq - hueco, zf + 0.0002, alto, K["canto"], n_esq=3, n_canto=1)
    fibra = B.objeto(col, f"{prefijo}_Fibra", bm, YUTE, angulo_suave=50)
    return [fibra, borde]


# ================================================================ 5. riel de utensilios de cocina
BARRA_COCINA = dict(
    r=0.006,             # diseño (pedido): barra Ø 12 mm
    y=-0.040,            # diseño: eje de la barra a 40 mm del muro (caben los ganchos y el batidor)
    tapa=(0.0075, 0.012),   # diseño: tapas de Ø 15 × 12 mm
    roseta=(0.016, 0.008),  # supuesto: roseta de soporte Ø 32 × 8 mm
    r_poste=0.0045,      # supuesto: poste del soporte Ø 9 mm
    x_soporte=0.035,     # diseño: soportes a 35 mm de cada extremo
    seg=8,
)
GANCHO_S = dict(
    r=0.002,             # supuesto: alambre de Ø 4 mm
    R1=0.011, R2=0.015,  # supuesto: radios (al eje) de las curvas de arriba y de abajo
    phi1=210.0,          # diseño: la curva de arriba termina a 210° y baja en diagonal (el cuelgue queda bajo la barra)
    tip1=-25.0, tip2=-200.0,   # diseño: puntas de las curvas
    pasos=(6, 6), seg=4,
)


def _gancho_s(bm, x, yb, zb, rb):
    """Gancho en S de alambre en el plano YZ, colgado de una barra de eje X en (yb, zb) y radio rb. Devuelve (y, z)
    del eje del alambre en el fondo de la curva de abajo y el radio de esa curva (para colgar los utensilios)."""
    K = GANCHO_S
    rw, R1, R2 = K["r"], K["R1"], K["R2"]
    c1 = Vector((yb, zb + rb + rw - R1))                # el alambre toca la barra en su punto más alto
    p1 = math.radians(K["phi1"])
    u = Vector((math.cos(p1), math.sin(p1)))
    d = Vector((-math.sin(p1), math.cos(p1)))
    ls = (R1 + R2) * math.cos(p1) / math.sin(p1)        # tramo recto: la curva de abajo queda bajo la barra
    c2 = c1 + u * (R1 + R2) + d * ls
    n1, n2 = K["pasos"]
    pts = []
    for k in range(n1 + 1):
        a = math.radians(K["tip1"] + (K["phi1"] - K["tip1"]) * k / n1)
        pts.append(c1 + Vector((math.cos(a), math.sin(a))) * R1)
    a0 = K["phi1"] - 180.0
    for k in range(n2 + 1):
        a = math.radians(a0 + (K["tip2"] - a0) * k / n2)
        pts.append(c2 + Vector((math.cos(a), math.sin(a))) * R2)
    _barrido(bm, [(x, p.x, p.y) for p in pts], [rw] * len(pts), seg=K["seg"], giro=45.0, arriba=(1.0, 0.0, 0.0))
    return Vector((c2.x, c2.y - R2)), R2


def _contacto(espesor, R2):
    """Cota (sobre el eje del alambre en el fondo del gancho) del borde de arriba de un ojal de `espesor`: el
    alambre curvo sube hacia las dos caras del mango y el ojal apoya en esos dos puntos."""
    rw = GANCHO_S["r"]
    e2 = min(espesor / 2, R2 * 0.9)
    return rw + (R2 - math.sqrt(R2 * R2 - e2 * e2))


def _espatula(mad, inox, M, R2):
    """Espátula de voltear: mango plano de roble con ojal y cantos suavizados, cuello de pletina inoxidable con
    acodado hacia el frente y hoja de 72 × 92 mm. Origen de M: eje del alambre del gancho (cuelga del ojal)."""
    e = 0.012                                              # supuesto: mango de 12 mm de espesor
    r_oj, Rm = 0.0055, 0.013
    zc = _contacto(e, R2) - r_oj
    z_inf = zc - 0.125                                     # supuesto: mango de ≈ 0,14
    with mad.parte(MADERA, M) as bm:
        _placa_ojal(bm, Rm, r_oj, zc, 0.020, z_inf, e, chaflan=0.0035, n=10)
    ang = math.radians(20)                                 # diseño: la hoja se adelanta 20°
    dn = Vector((0.0, -math.sin(ang), -math.cos(ang)))
    p2 = Vector((0.0, 0.0, z_inf - 0.030))
    p3 = p2 + dn * 0.030
    with inox.parte(INOX, M) as bm:
        CB.barra_plana(bm, [(0.0, 0.0, z_inf + 0.025), tuple(p2), tuple(p3)], 0.010, 0.0025, radio_curva=0.03,
                       pasos=3, lateral=(1.0, 0.0, 0.0))
        # hoja: contorno en (u = X, v = a lo largo de dn), espesor según w = X × dn
        cont = [(-0.007, -0.004), (0.007, -0.004), (0.030, 0.022), (0.036, 0.032), (0.036, 0.082),
                (0.0331, 0.0891), (0.026, 0.092), (-0.026, 0.092), (-0.0331, 0.0891), (-0.036, 0.082),
                (-0.036, 0.032), (-0.030, 0.022)]
        antes = set(bm.verts)
        O._extruir(bm, cont, -0.0006, 0.0006)
        X = Vector((1.0, 0.0, 0.0))
        w = X.cross(dn)
        Mb = Matrix((X, dn, w)).transposed().to_4x4()
        Mb.translation = p3
        B.transformar(bm, Mb, [v for v in bm.verts if v not in antes])


def _cucharon(inox, M, R2):
    """Cucharón de acero inoxidable: mango plano con ojal que se angosta, cuello con un leve quiebre hacia el frente
    y cazo de Ø 80 × 35 mm abierto hacia arriba, soldado por el borde de atrás. Origen de M: eje del alambre."""
    e = 0.0025
    r_oj, Rm = 0.0045, 0.011
    zc = _contacto(e, R2) - r_oj
    z_inf = zc - 0.19                                      # supuesto: mango de ≈ 0,20
    Rb, Hb, tb = 0.040, 0.035, 0.0015                      # supuesto: cazo de 80 mm (≈ 120 ml)
    yc = -(Rb + 0.008)                                     # el cazo queda delante del plano del mango
    z_rim = z_inf - 0.050
    yn = yc + Rb + 0.001 - 0.0002                          # cara interior del cuello 0,2 mm dentro del borde
    with inox.parte(INOX, M) as bm:
        _placa_ojal(bm, Rm, r_oj, zc, 0.012, z_inf, e, n=10)
        CB.barra_plana(bm, [(0.0, 0.0, z_inf + 0.012), (0.0, 0.0, z_inf - 0.008), (0.0, yn, z_inf - 0.030),
                            (0.0, yn, z_rim - 0.006)], 0.009, 0.002, radio_curva=0.015, pasos=2,
                       lateral=(1.0, 0.0, 0.0))
        ext = [(0.0, -Hb)] + [(Rb * math.sin(math.radians(bb)), -Hb * math.cos(math.radians(bb))) for bb in (35, 65, 90)]
        ri, hi = Rb - tb, Hb - tb
        inn = [(ri * math.sin(math.radians(bb)), -hi * math.cos(math.radians(bb))) for bb in (90, 50)]
        CB.revolucion(bm, ext + inn + [(0.0, -hi)], centro=(0.0, yc, z_rim), seg=16)


def _batidor(mad, inox, M):
    """Batidor de varillas: seis varillas inoxidables de Ø 1,6 mm (tres lazos en planos a 60°, cruzados a
    distinta altura en la punta) en una virola, mango torneado de roble y lazo de alambre para colgar. Origen de
    M: eje del alambre del gancho (el lazo apoya sobre él)."""
    rw = GANCHO_S["r"]
    rl, Rl = 0.0012, 0.0075                                # supuesto: lazo de alambre de Ø 2,4
    zcl = rw + rl - Rl                                     # centro del lazo: su borde interior apoya en el gancho
    z_ht = -0.014                                          # tope del mango
    z_hb = z_ht - 0.105                                    # supuesto: mango de 0,105
    a0, a1 = -55.0, 235.0
    lazo = [Vector((0.0036, 0.0, z_ht - 0.006))]
    lazo += [Vector((Rl * math.cos(math.radians(a0 + (a1 - a0) * k / 8)), 0.0,
                     zcl + Rl * math.sin(math.radians(a0 + (a1 - a0) * k / 8)))) for k in range(9)]
    lazo.append(Vector((-0.0036, 0.0, z_ht - 0.006)))
    with inox.parte(INOX, M) as bm:
        _barrido(bm, lazo, [rl] * len(lazo), seg=3, arriba=(0.0, 1.0, 0.0))
        # virola cónica que abraza el pie del mango
        CB.revolucion(bm, [(0.0, 0.016), (0.0106, 0.016), (0.0092, -0.004), (0.0, -0.004)], centro=(0.0, 0.0, z_hb),
                      seg=8)
        z_fb = z_hb - 0.004
        ctrl = [(0.0045, 0.006), (0.0052, -0.004), (0.013, -0.035), (0.023, -0.080), (0.0275, -0.115),
                (0.021, -0.145)]
        for k in range(3):
            punta = -0.157 - 0.0034 * k                   # cada lazo cruza la punta 3,4 mm más abajo que el anterior
            c = ctrl + [(0.0, punta)] + [(-u, z) for u, z in reversed(ctrl)]
            dens = O._spline(c, 10)
            pts2 = O._remuestrear(dens, 15, curvatura=0.65)
            al = math.radians(60.0 * k)
            dr = Vector((math.cos(al), math.sin(al), 0.0))
            pts = [dr * u + Vector((0.0, 0.0, z_fb + z)) for u, z in pts2]
            _barrido(bm, pts, [0.0008] * len(pts), seg=3, arriba=(-math.sin(al), math.cos(al), 0.0))
    with mad.parte(MADERA, M) as bm:
        CB.revolucion(bm, [(0.0, z_ht), (0.0085, z_ht), (0.0105, z_ht - 0.003), (0.0115, z_ht - 0.045),
                           (0.0098, z_hb), (0.0, z_hb)], seg=8)


def _pinzas(inox, M, R2):
    """Pinzas de acero inoxidable: cabeza plana con ojal (las dos ramas unidas) y dos ramas de fleje que se
    abren hacia el frente y el fondo y terminan en paletas redondeadas curvadas hacia adentro. Origen de M: eje del
    alambre del gancho."""
    e = 0.0036
    r_oj, Rm = 0.0045, 0.012
    zc = _contacto(e, R2) - r_oj
    z_inf = zc - 0.032
    tf = 0.0012                                            # supuesto: fleje de 1,2 mm
    with inox.parte(INOX, M) as bm:
        _placa_ojal(bm, Rm, r_oj, zc, 0.022, z_inf, e, n=10)
        for s in (-1, 1):
            ys = [0.0009, 0.0009, 0.0040, 0.0068, 0.0062, 0.0036, 0.0028]
            zs = [0.008, -0.004, -0.030, -0.120, -0.165, -0.192, -0.200]
            anchos = [0.018, 0.018, 0.018, 0.020, 0.030, 0.026, 0.013]
            _cinta(bm, [(0.0, s * y, z_inf + z) for y, z in zip(ys, zs)], anchos, tf)


def riel_utensilios(col, prefijo, largo=0.50):
    """Barra mural de cocina de acero negro Ø 12 mm (eje a 40 mm del muro y en z = 0, tapas de Ø 15 en los extremos)
    sobre dos soportes de roseta y poste, con cinco ganchos en S de alambre de Ø 4 mm y cuatro utensilios colgando
    hacia −Z: cucharón y pinzas de acero inoxidable, batidor de varillas y espátula con mango de roble (el quinto
    gancho queda libre). Espalda (rosetas) en y = 0, centrada en X. Los utensilios bajan hasta ≈ −0,33.
    ≈ 1 900 triángulos (tope 2 000)."""
    K = BARRA_COCINA
    rb, yb = K["r"], K["y"]
    rc, lc = K["tapa"]
    barra, mad, inox = O._Malla(), O._Malla(), O._Malla()
    with barra.parte(ACERO) as bm:
        perfil = [(0.0, 0.0), (rc - 0.0012, 0.0), (rc, 0.0012), (rc, lc), (rb, lc), (rb, largo - lc), (rc, largo - lc),
                  (rc, largo - 0.0012), (rc - 0.0012, largo), (0.0, largo)]
        O._torno_eje(bm, perfil, (-largo / 2, yb, 0.0), (1.0, 0.0, 0.0), K["seg"])
        Rr, er = K["roseta"]
        xsop = largo / 2 - K["x_soporte"]
        for s in (-1, 1):
            O._torno_eje(bm, [(0.0, 0.0), (Rr, 0.0), (Rr - 0.0015, er), (0.0, er)], (s * xsop, 0.0, 0.0),
                         (0.0, -1.0, 0.0), 14)
            B.tubo(bm, [(s * xsop, -er + 0.001, 0.0), (s * xsop, yb, 0.0)], K["r_poste"], seg=6)
        paso = (2 * xsop - 0.09) / 4                       # diseño: ganchos parejos entre los soportes
        xs = [-2 * paso + k * paso for k in range(5)]
        cuelgues = [_gancho_s(bm, x, yb, 0.0, rb) for x in xs]
    # utensilios: del más ancho al más angosto, el último gancho libre
    for (q, R2), x, fn in zip(cuelgues, xs, ("cucharon", "batidor", "espatula", "pinzas")):
        M = Matrix.Translation((x, q.x, q.y))
        if fn == "cucharon":
            _cucharon(inox, M, R2)
        elif fn == "batidor":
            _batidor(mad, inox, M)
        elif fn == "espatula":
            _espatula(mad, inox, M, R2)
        else:
            _pinzas(inox, M, R2)
    objs = [barra.crear(col, f"{prefijo}_Barra", angulo=50), inox.crear(col, f"{prefijo}_Inox", angulo=60),
            mad.crear(col, f"{prefijo}_Madera", angulo=70)]
    return [o for o in objs if o]


# ================================================================ 6. toallero de barra con toalla
TOALLERO = dict(
    r=0.008,             # diseño (pedido): barra Ø 16 mm
    sep=0.080,           # diseño (pedido): eje de la barra a 0,08 del muro
    r_curva=0.030,       # diseño: la barra se dobla hacia el muro con radio 30 mm
    roseta=(0.026, 0.011),   # supuesto: roseta Ø 52 × 11 mm
    seg=12,
)
TOALLA_BARRA = dict(
    ancho=0.40,          # supuesto: toalla de baño doblada a lo largo (se achica si la barra es corta)
    espesor=0.018,       # supuesto: dos capas de rizo
    caida_frente=0.45,   # diseño (pedido)
    caida_atras=0.30,    # diseño (pedido)
    abre=0.010,          # diseño: los paños se separan un poco al caer
    semilla=17,
)


def _toalla_barra(bm, yc, zc, r_apoyo, ancho, t, caida_atras, caida_frente, semilla, abre, nx=8, n_atras=5,
                  n_abrazo=7, n_frente=7):
    """Toalla doblada colgada de una barra de eje X por (yc, zc): banda de sección de estadio ancho × t que baja por
    atrás (hacia el muro, +Y), abraza la barra y cae por delante. Pliegues verticales suaves que crecen hacia los
    extremos libres, panza, leve ensanche y ruedo apenas ondulado; semilla fija (misma forma en cada llamada).
    Adaptada de deco_cocina_bano._toalla, con más anillos en las caídas largas."""
    rnd = random.Random(semilla)
    f = [rnd.uniform(0, TAU) for _ in range(5)]
    R = r_apoyo + t / 2 + 0.0005                          # eje de la tela alrededor de la barra (0,5 mm de luz)
    cam = []
    for k in range(n_atras):
        q = 1 - k / n_atras
        cam.append((yc + R + abre * q * q, zc - caida_atras * q))
    for k in range(n_abrazo + 1):
        th = math.pi * k / n_abrazo
        cam.append((yc + R * math.cos(th), zc + R * math.sin(th)))
    for k in range(1, n_frente + 1):
        q = k / n_frente
        cam.append((yc - R - 1.3 * abre * q * q, zc - caida_frente * q))
    pts = [Vector((0.0, y, z)) for y, z in cam]
    s = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        s.append(s[-1] + (b - a).length)
    i0, i1 = n_atras, n_atras + n_abrazo
    s_mid, medio = (s[i0] + s[i1]) / 2, (s[i1] - s[i0]) / 2
    h = t / 2
    sec = [(-ancho / 2 + h + (ancho - 2 * h) * i / nx, h) for i in range(nx + 1)]
    sec += [(ancho / 2 - h + h * math.cos(a), h * math.sin(a)) for a in (math.pi / 4, 0.0, -math.pi / 4)]
    sec += [(ancho / 2 - h - (ancho - 2 * h) * i / nx, -h) for i in range(nx + 1)]
    sec += [(-ancho / 2 + h + h * math.cos(a), h * math.sin(a)) for a in (-3 * math.pi / 4, math.pi, 3 * math.pi / 4)]
    X = Vector((1.0, 0.0, 0.0))
    n = len(pts)
    anillos = []
    for i in range(n):
        tg = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        nv = X.cross(tg).normalized()
        frente = s[i] > s_mid
        dist = abs(s[i] - s_mid) - medio
        libre = _suave(dist / 0.16)
        amp = (0.016 if frente else 0.009) * libre         # diseño: pliegues de hasta 16 mm adelante, 9 atrás
        caida = caida_frente if frente else caida_atras
        anillo = []
        for sx, sn in sec:
            u = sx / ancho
            onda = amp * (0.65 * math.sin(TAU * sx / 0.19 + f[0] + 2.2 * s[i])
                          + 0.35 * math.sin(TAU * sx / 0.12 + f[1] - 1.5 * s[i]))
            panza = -0.004 * libre * (1.0 - 4.0 * u * u)   # nv apunta hacia la barra: la panza sale hacia afuera
            ensancha = 1.0 + 0.03 * libre
            # un costado cuelga 1,5 % más largo que el otro (la toalla nunca queda pareja)
            baja = -0.015 * caida * u * libre * (1 if frente else -1)
            anillo.append(pts[i] + X * (sx * ensancha) + nv * (sn + onda + panza) + Vector((0.0, 0.0, baja)))
        anillos.append(anillo)
    # ruedos: anillo final encogido (redondea las puntas) y apenas ondulado
    for idx, signo in ((0, -1), (n - 1, 1)):
        c = pts[idx]
        tg = (pts[min(idx + 1, n - 1)] - pts[max(idx - 1, 0)]).normalized() * signo
        nuevo = []
        for q in anillos[idx]:
            dx = (q - c).dot(X)
            ola = 0.002 * math.sin(TAU * dx / 0.17 + f[2 if signo > 0 else 3])
            nuevo.append(c + tg * (h * 0.6 + ola) + X * (dx * 0.99) + ((q - c) - X * dx) * 0.45)
        for q in anillos[idx]:                            # el ruedo del anillo original acompaña la ola
            dx = (q - c).dot(X)
            q += tg * (0.002 * math.sin(TAU * dx / 0.17 + f[2 if signo > 0 else 3]))
        if idx == 0:
            anillos.insert(0, nuevo)
        else:
            anillos.append(nuevo)
    CB.loft(bm, anillos)


def toallero_barra(col, prefijo, largo=0.60, ancho_toalla=None, caida_frente=None, caida_atras=None, semilla=None):
    """Toallero mural de baño: barra de acero negro Ø 16 mm a 0,08 del muro que se dobla (radio 30 mm) hacia dos
    rosetas redondas de Ø 52; espalda en y = 0, eje de la barra en z = 0, ancho total `largo` centrado en X. Una
    toalla doblada (Depto_Mat_Toalla) cuelga por encima de la barra con pliegues suaves: cae ≈ 0,45 por delante y
    ≈ 0,30 por detrás (hacia el muro, sin tocarlo). ancho_toalla: por defecto 0,40, o menos si la barra es corta
    (deja 3 cm libres antes de cada curva). ≈ 1 400 triángulos (tope 1 500)."""
    K, T = TOALLERO, TOALLA_BARRA
    r, sep, rc = K["r"], K["sep"], K["r_curva"]
    Rr, er = K["roseta"]
    xr = largo / 2 - Rr
    bm = bmesh.new()
    for s in (-1, 1):
        O._torno_eje(bm, [(0.0, 0.0), (Rr, 0.0), (Rr - 0.0025, er), (0.0, er)], (s * xr, 0.0, 0.0),
                     (0.0, -1.0, 0.0), 16)
    trazo = [(xr, -er + 0.003, 0.0), (xr, -sep, 0.0), (-xr, -sep, 0.0), (-xr, -er + 0.003, 0.0)]
    B.tubo(bm, B._redondear_polilinea(trazo, rc, pasos=4), r, seg=K["seg"])
    barra = B.objeto(col, f"{prefijo}_Barra", bm, ACERO, angulo_suave=45)
    libre = 2 * (xr - rc) - 0.06
    at = min(T["ancho"], libre) if ancho_toalla is None else ancho_toalla
    bm = bmesh.new()
    _toalla_barra(bm, -sep, 0.0, r, at, T["espesor"], caida_atras or T["caida_atras"],
                  caida_frente or T["caida_frente"], T["semilla"] if semilla is None else semilla, T["abre"])
    toalla = B.objeto(col, f"{prefijo}_Toalla", bm, TOALLA, angulo_suave=60)
    return [barra, toalla]
