"""Comedor y balcón: piezas de la decoración industrial (versión 2; docs/deco-industrial.md, «Comedor y balcón»).

Piezas:
    mesa_comedor   mesa redonda de pedestal (Ø 0,80 × 0,75): cubierta de roble ahumado con canto redondeado,
                   cruceta de platina, columna de tubo de Ø 76 con maza abajo y collarín arriba, y base en cruz de
                   cuatro patas de platina que bajan en curva hasta regatones redondos.
    silla_comedor  silla bistró de chapa de acero estampado (genérica, sin marca): asiento levemente cóncavo con
                   borde enrollado y faldón, cuatro patas de chapa en U ahusadas y abiertas, y respaldo de una sola
                   chapa en arco: dos brazos remachados al faldón trasero que suben hasta una banda curva en planta
                   con calado de agarre.
    mesa_bistro    mesa de balcón (Ø 0,55 × 0,72): cubierta de chapa con el borde doblado hacia abajo y pie de tres
                   varillas en haz, juntas por un anillo, que se abren en curva hacia tres regatones.
    silla_bistro   silla plegable de balcón: marco de tubo negro (pata delantera y larguero del asiento en un solo
                   tubo doblado, que cruza la pata trasera en un pivote a la vista con perno, buje y tuerca), cinco
                   listones de asiento y tres de respaldo curvos de roble.

Convenciones (docs/deco-industrial.md): cada pieza es `nombre(col, prefijo, **parámetros) -> list[Object]`, en
metros, Z arriba, huella centrada en el origen, apoyada en z = 0, frente hacia −Y y espalda hacia +Y; todos los
objetos con origen (0, 0, 0) y sin rotación, un objeto por material. Sólo bmesh (tornos, lofts y barridos), sin
booleanos ni subdivisión. Determinista: no hay aleatoriedad ni se recorren conjuntos (set) de elementos de bmesh,
cuyo orden depende de la memoria; la misma llamada da exactamente la misma malla, también entre procesos (se
instancian). El sombreado se fija con el ángulo de suavizado de cada objeto y, donde conviven piezas que necesitan
ángulos distintos, marcando aristas vivas antes de agregar las demás (`_aristas_vivas`). UV en metros: la de caja
de siempre (depto_geom.uv_mundo) y, en las superficies de revolución verticales (cantos de cubiertas, faldón,
columna), u = radio × ángulo, que deja una sola costura atrás en vez de cuatro (`_uv_cilindro`). bpy 3.6,
headless.

Materiales (todos ya existen en depto_geom.MATERIALES; este módulo no agrega ninguno): Depto_Mat_MaderaMueble
(roble ahumado), Depto_Mat_AceroNegro (acero pavonado: mesas y silla plegable) y Depto_Mat_MetalNegroMate (acero
pintado negro mate: silla de comedor).
"""
import bisect
import math

import bmesh
from mathutils import Vector

import deco_base as B
import deco_cocina_bano as CB
import depto_geom as G
from deco_living import _barrido, _sec_circulo

MADERA = "Depto_Mat_MaderaMueble"
ACERO = "Depto_Mat_AceroNegro"
NEGRO = "Depto_Mat_MetalNegroMate"

# Topes de triángulos por pieza (pedido y docs/deco-industrial.md, «Comedor y balcón»)
TOPES = dict(mesa_comedor=1800, silla_comedor=2000, mesa_bistro=1200, silla_bistro=1800)
PIEZAS = tuple(TOPES)


# =====================================================================================================
# Ayudas de modelado propias de este módulo
# =====================================================================================================
def _aristas_vivas(bm, angulo=40.0):
    """Marca como vivas (sharp) las aristas ya construidas cuyo ángulo entre caras supera `angulo`. Así un objeto
    puede usar un ángulo de suavizado alto (tubos y regatones de pocos lados) sin redondear los chaflanes de lo que
    se construyó antes."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    lim = math.radians(angulo)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
            e.smooth = False


def _tubo(bm, puntos, r, seg=8, radios=0.0, pasos=4, ini="tapa", fin="tapa", pasos_domo=2):
    """Tubo de sección circular por una polilínea con curvas de `radios` (deco_living._barrido). Extremos:
    "tapa" (plano, normal al eje), "piso" (cortado horizontal en z = 0, para apoyar en el suelo) o "domo"
    (tapón semiesférico)."""
    anillos = _barrido(bm, puntos, _sec_circulo(r, seg), radios=radios, pasos=pasos, tapas=False)
    for idx, modo in ((0, ini), (-1, fin)):
        anillo = anillos[idx]
        vecino = anillos[1] if idx == 0 else anillos[-2]
        c = sum((v.co for v in anillo), Vector()) / len(anillo)
        d = (c - sum((v.co for v in vecino), Vector()) / len(vecino)).normalized()   # hacia afuera del tubo
        if modo == "piso":
            for v in anillo:
                v.co = v.co + d * (-v.co.z / d.z)
            bm.faces.new(anillo)
        elif modo == "domo":
            previo = anillo
            for j in range(1, pasos_domo):
                b = (math.pi / 2) * j / pasos_domo
                nuevo = [bm.verts.new(c + (v.co - c) * math.cos(b) + d * (r * math.sin(b))) for v in anillo]
                for i in range(seg):
                    k = (i + 1) % seg
                    bm.faces.new((previo[i], previo[k], nuevo[k], nuevo[i])).smooth = True
                previo = nuevo
            polo = bm.verts.new(c + d * r)
            for i in range(seg):
                bm.faces.new((previo[i], previo[(i + 1) % seg], polo)).smooth = True
        else:
            bm.faces.new(anillo)
    return anillos


def _remache(bm, p, eje, r=0.0042, h=0.0024, seg=8, hundido=0.0004):
    """Cabeza de remache (o de tornillo de cabeza redonda) sobre una cara, hacia `eje`, hundida `hundido`."""
    eje = Vector(eje).normalized()
    CB.revolucion(bm, [(0.0, 0.0), (r, 0.0), (r * 0.78, h * 0.62), (0.0, h)], centro=Vector(p) - eje * hundido,
                  eje=eje, seg=seg)


def _disco(bm, R, z0, z1, r_sup, r_inf, seg=64, pasos_sup=3, apoyo=0.004):
    """Disco macizo por torno: canto superior redondeado (radio r_sup en `pasos_sup` tramos), chaflán inferior de
    r_inf y un anillo de apoyo en la cara de arriba, a `apoyo` del comienzo del radio, para que el sombreado suave
    no abombe la cara plana."""
    perfil = [(0.0, z0), (R - r_inf, z0), (R, z0 + r_inf), (R, z1 - r_sup)]
    for k in range(1, pasos_sup):
        a = (math.pi / 2) * k / pasos_sup
        perfil.append((R - r_sup + r_sup * math.cos(a), z1 - r_sup + r_sup * math.sin(a)))
    perfil += [(R - r_sup, z1), (R - r_sup - apoyo, z1), (0.0, z1)]
    return B.torno(bm, perfil, seg=seg)


def _cruz(L, w2, ch, giro=45.0):
    """Contorno antihorario (x, y) de una cruz de cuatro brazos de largo L medido desde el centro y semiancho w2,
    con las puntas achaflanadas `ch`, girada `giro` grados."""
    base = [(w2, -w2), (L - ch, -w2), (L, -w2 + ch), (L, w2 - ch), (L - ch, w2)]
    pts = []
    for k in range(4):
        a = math.radians(giro + 90 * k)
        ca, sa = math.cos(a), math.sin(a)
        pts += [(x * ca - y * sa, x * sa + y * ca) for x, y in base]
    return pts


def _rect_chaflan(a, z0, z1, c):
    """Sección (u, z) de una platina de canto: ancho `a` centrado en u = 0, de z0 a z1, aristas achaflanadas c."""
    h = a / 2
    return [(h, z1 - c), (h - c, z1), (-h + c, z1), (-h, z1 - c), (-h, z0 + c), (-h + c, z0), (h - c, z0),
            (h, z0 + c)]


def _perfil_u(p, n, t, ancho, ala, e, ch):
    """Contorno horizontal de una pata de chapa plegada en U: alma de `ancho` centrada en p con su cara exterior
    hacia `n`, alas de `ala` hacia adentro (−n), chapa de espesor e y pliegues exteriores matados con un chaflán
    `ch` (con el ángulo de suavizado del objeto se ven redondeados)."""
    h = ancho / 2
    pts = [(h, -ala), (h, -ch), (h - ch, 0.0), (-h + ch, 0.0), (-h, -ch), (-h, -ala), (-h + e, -ala), (-h + e, -e),
           (h - e, -e), (h - e, -ala)]
    return [p + t * a + n * b for a, b in pts]


def _uv_cilindro(bm, caras, max_nz=0.7):
    """UV en metros para superficies de revolución alrededor del eje Z: primero la UV de caja de siempre
    (depto_geom.uv_mundo) y luego, en las `caras` casi verticales, u = radio × ángulo y v = z. La caja cambia de
    proyección cada 90° y deja cuatro costuras en cantos y columnas; así queda una sola, atrás (+Y). Se usa con
    deco_base.objeto(..., uv="propia")."""
    G.uv_mundo(bm)
    uv = bm.loops.layers.uv.verify()
    for f in caras:
        if not f.is_valid or abs(f.normal.z) > max_nz:
            continue
        angs = [math.atan2(lp.vert.co.x, -lp.vert.co.y) for lp in f.loops]   # 0 al frente (−Y), ±π atrás
        if max(angs) - min(angs) > math.pi:
            angs = [a + 2 * math.pi if a < 0 else a for a in angs]
        for lp, a in zip(f.loops, angs):
            c = lp.vert.co
            lp[uv].uv = (math.hypot(c.x, c.y) * a, c.z)


def _centrar(bms):
    """Deja la huella de la pieza centrada en el origen y apoyada en z = 0."""
    lo, hi = CB._caja_env(bms)
    CB._mover(bms, (-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))


# =====================================================================================================
# Mesa de comedor
# =====================================================================================================
MESA_COMEDOR = dict(
    cubierta=0.030,              # pedido: cubierta de roble de 0,03
    r_canto=0.008,               # diseño: radio del canto superior (tres tramos)
    chaflan=0.003,               # diseño: chaflán del canto inferior
    tubo=0.076,                  # pedido: columna de tubo de acero de Ø 0,076
    collarin=(0.092, 0.028),     # diseño: collarín superior de Ø 92 × 28 mm
    maza=(0.100, 0.024, 0.098),  # diseño: maza (collarín inferior) de Ø 100, de 24 a 98 mm del piso
    base=0.62 / 0.80,            # pedido: base de Ø ≈ 0,62 para la cubierta de Ø 0,80 (se escala con ella)
    platina=(0.060, 0.012),      # pedido: platina de 60 × 12 en la raíz de cada pata
    punta=0.031,                 # diseño: la platina se afina a 31 mm de alto en la punta
    z_raiz=(0.030, 0.090),       # diseño: canto inferior y superior de la pata en la maza
    cruceta=(0.045, 0.008),      # diseño: cruceta de platina de 45 × 8 bajo la cubierta
    brazo_cruceta=0.30 / 0.80,   # diseño: brazos de 0,30 para la cubierta de Ø 0,80 (se escala con ella)
    regaton=(0.029, 0.014),      # supuesto: regatón de Ø 29 × 14 mm (tope usual de muebles)
    giro=45.5,                   # diseño: patas y cruceta en diagonal (quedan entre las sillas); 0,5° más que 45
                                 # para que la UV de caja no salte entre X e Y en las caras de cada pata
)


def mesa_comedor(col, prefijo, diametro=0.80, alto=0.75):
    """Mesa redonda de pedestal para dos o tres personas. Cubierta de roble ahumado de 0,03 con canto superior
    redondeado y chaflán abajo; cruceta de platina de 45 × 8 atornillada bajo la cubierta; columna de tubo de Ø 76
    con collarín arriba y maza abajo; base en cruz (patas en diagonal, alineadas con la cruceta) de platina de 60 × 12
    que baja en curva desde la maza hasta la punta, sobre regatones redondos. Huella: la cubierta."""
    K = MESA_COMEDOR
    R = diametro / 2
    z_cub = alto - K["cubierta"]
    bm = bmesh.new()
    _disco(bm, R, z_cub, alto, K["r_canto"], K["chaflan"], seg=64, pasos_sup=3)
    _uv_cilindro(bm, bm.faces)
    cub = B.objeto(col, f"{prefijo}_Cubierta", bm, MADERA, suave=True, angulo_suave=35, uv="propia")

    bm = bmesh.new()
    # cruceta: placa en cruz, 0,3 mm bajo la cubierta (sin caras coplanares)
    a_c, e_c = K["cruceta"]
    z_c1 = z_cub - 0.0003
    z_c0 = z_c1 - e_c
    contorno = _cruz(K["brazo_cruceta"] * diametro, a_c / 2, 0.006, giro=K["giro"])
    CB.loft(bm, [[(x, y, z_c0) for x, y in contorno], [(x, y, z_c1) for x, y in contorno]])
    # columna, maza y collarín en un solo torno (el collarín entra 0,5 mm en la cruceta)
    rt = K["tubo"] / 2
    rc, hc = K["collarin"][0] / 2, K["collarin"][1]
    rh, zh0, zh1 = K["maza"][0] / 2, K["maza"][1], K["maza"][2]
    zc1 = z_c0 + 0.0005
    zc0 = zc1 - hc
    c = 0.002
    antes = set(bm.faces)
    B.torno(bm, [(0.0, zh0), (rh, zh0), (rh, zh1 - c), (rh - c, zh1), (rt, zh1), (rt, zc0), (rc - c, zc0),
                 (rc, zc0 + c), (rc, zc1), (0.0, zc1)], seg=20)
    columna = set(bm.faces) - antes
    # patas: platina de canto que nace dentro de la maza y baja en curva hasta la punta
    r_base = K["base"] * diametro / 2
    rr, hr = K["regaton"][0] / 2, K["regaton"][1]
    s0, s1 = rh - 0.010, r_base
    zb0, zt0 = K["z_raiz"]
    zb1 = hr - 0.001                               # la punta entra 1 mm en el regatón
    zt1 = zb1 + K["punta"]
    esp = K["platina"][1]
    dirs = []
    for k in range(4):
        a = math.radians(K["giro"] + 90 * k)
        er, et = Vector((math.cos(a), math.sin(a), 0.0)), Vector((-math.sin(a), math.cos(a), 0.0))
        dirs.append(er)
        anillos = []
        for q in (0.0, 0.3, 0.58, 0.82, 1.0):
            s = s0 + (s1 - s0) * q
            zb = zb1 + (zb0 - zb1) * max(0.0, 1.0 - q / 0.9) ** 1.4      # llega plana sobre el regatón
            zt = zt0 - (zt0 - zt1) * q ** 1.35
            anillos.append([er * s + et * u + Vector((0.0, 0.0, z)) for u, z in _rect_chaflan(esp, zb, zt, 0.0015)])
        CB.loft(bm, anillos)
    _aristas_vivas(bm, 40.0)
    # regatones de 12 lados (se suavizan con el ángulo del objeto)
    for er in dirs:
        p = er * (r_base - rr)
        CB.revolucion(bm, [(0.0, 0.0), (rr, 0.0), (rr, hr), (0.0, hr)], centro=(p.x, p.y, 0.0), seg=12)
    _uv_cilindro(bm, [f for f in bm.faces if f in columna])
    est = B.objeto(col, f"{prefijo}_Estructura", bm, ACERO, suave=True, angulo_suave=50, uv="propia")
    return [cub, est]


# =====================================================================================================
# Silla de comedor (bistró de chapa estampada)
# =====================================================================================================
SILLA_COMEDOR = dict(
    asiento=(0.43, 0.42),        # pedido: asiento de 0,43 × 0,42
    alto_asiento=0.45,           # pedido: asiento a 0,45 (cima del borde enrollado)
    alto=0.84,                   # pedido: alto total ≈ 0,84
    r_esquina=0.06,              # diseño: esquina redondeada del asiento
    r_rollo=0.0065,              # diseño: borde enrollado de Ø 13 mm
    concavo=0.010,               # diseño: el centro del asiento baja 10 mm
    faldon=0.046,                # diseño: el faldón baja hasta 46 mm bajo la cima del asiento
    chapa=0.0018,                # supuesto: chapa de acero de 1,8 mm
    pata_arriba=(0.046, 0.022),  # diseño: alma × ala de la pata en U bajo el asiento
    pata_abajo=(0.024, 0.013),   # diseño: alma × ala en el piso (pata ahusada)
    pata_dentro=0.040,           # diseño: alma a 40 mm del centro de la esquina (queda dentro del faldón)
    pie=(0.212, -0.224, 0.232),  # diseño: alma en el piso (x, y delantera, y trasera): huella ≈ 0,44 × 0,50
    chapa_resp=0.0025,           # supuesto: chapa del respaldo de 2,5 mm
    inclinacion=8.0,             # diseño: sobre el rollo, el respaldo sube inclinado 8° hacia atrás
    r_curva=0.50,                # diseño: radio en planta de la banda (cóncava hacia adelante)
    ancho_resp=0.40,             # diseño: banda de 0,40 de desarrollo
    banda=(0.13, 0.165),         # diseño: alto de la banda entre los brazos y en los costados
    esquina_resp=0.03,           # diseño: esquinas de arriba de la banda
    acuerdo=0.05,                # diseño: radio del acuerdo entre cada brazo y el canto bajo (recto) de la banda
    brazo=(0.115, 0.150),        # diseño: cantos interior y exterior de cada brazo al pie (desarrollo)
    calado=(0.10, 0.026, 0.042), # diseño: calado de agarre de 10 × 2,6 cm, centro a 4,2 cm del canto de arriba
)


def _espina(puntos_yz, radio, pasos):
    """Curva guía en el plano x = 0 (puntos (y, z)) con esquinas redondeadas, parametrizada por longitud de arco.
    Devuelve f(v) -> (punto, normal hacia atrás), con la tangente interpolada (normal continua)."""
    pts = CB.redondear([Vector((0.0, y, z)) for y, z in puntos_yz], radio, pasos)
    limpios = [pts[0]]
    for p in pts[1:]:
        if (p - limpios[-1]).length > 1e-7:
            limpios.append(p)
    pts = limpios
    n = len(pts)
    s = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        s.append(s[-1] + (b - a).length)
    tang = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]

    def f(v):
        v = max(0.0, min(s[-1], v))
        i = min(bisect.bisect_right(s, v) - 1, n - 2)
        t = (v - s[i]) / (s[i + 1] - s[i])
        tg = tang[i].lerp(tang[i + 1], t).normalized()
        return pts[i].lerp(pts[i + 1], t), Vector((0.0, tg.z, -tg.y))
    return f


def _estaciones_respaldo(K, v_top):
    """Estaciones de la chapa del respaldo en su desarrollo (u a lo ancho, v a lo largo de la espina desde el pie de
    los brazos), de izquierda a derecha: cada una con cuatro puntos del canto interior (brazo, acuerdo, canto bajo
    de la banda) al exterior y la marca de si cae dentro del calado. Brazos: estaciones horizontales; acuerdo:
    abanico desde su centro hasta puntos del borde exterior; banda: estaciones verticales, que en el calado separan
    sus dos puntos del medio (en los extremos del calado se juntan). Se arma la mitad derecha y se refleja."""
    W2 = K["ancho_resp"] / 2
    h_c, h_l = K["banda"]
    rc = K["esquina_resp"]
    rf = K["acuerdo"]
    ui, uo = K["brazo"]
    a_s, b_s, d_s = K["calado"][0] / 2, K["calado"][1] / 2, K["calado"][2]
    v_s = v_top - d_s
    v_a = v_top - h_c                                 # canto bajo de la banda, entre los brazos
    u_f, v_f = ui - rf, v_a - rf                      # centro del acuerdo brazo-banda
    v_b = v_top - h_l                                 # el canto exterior llega al costado de la banda

    def exterior(v):                                  # vertical al pie, se abre en S hasta la banda
        t = max(0.0, min(1.0, v / v_b))
        return uo + (W2 - uo) * t * t * (3 - 2 * t)

    def cuatro(pi, po):
        return [pi] + [(pi[0] + (po[0] - pi[0]) * f, pi[1] + (po[1] - pi[1]) * f) for f in (1 / 3, 2 / 3)] + [po]

    est = [(cuatro((ui, v), (exterior(v), v)), False)
           for v in (0.0, 0.024, 0.030, 0.036, 0.044, 0.10, 0.15, 0.20) if v < v_f - 0.02]
    # abanico: puntos del borde exterior (costado, esquina cada 15°, canto de arriba) unidos con el acuerdo por
    # rectas que pasan por su centro
    afuera = [(exterior(v_f), v_f), (W2, v_b), (W2, (v_b + v_top - rc) / 2), (W2, v_top - rc)]
    afuera += [(W2 - rc + rc * math.cos(math.radians(a)), v_top - rc + rc * math.sin(math.radians(a)))
               for a in (15, 30, 45, 60, 75, 90)]
    afuera += [(u, v_top) for u in (0.13, 0.10, u_f)]
    for po in afuera:
        th = math.atan2(po[1] - v_f, po[0] - u_f)
        est.append((cuatro((u_f + rf * math.cos(th), v_f + rf * math.sin(th)), po), False))
    punta = [a_s - b_s * (1 - math.cos(math.radians(a))) for a in (0.0, 22.5, 45.0, 67.5, 90.0)]   # semicírculo
    for u in [0.06] + punta + [0.025, 0.012, 0.0]:
        pi, po = (u, v_a), (u, v_top)
        if u <= a_s + 1e-9:
            du = max(0.0, u - (a_s - b_s))
            h = math.sqrt(max(0.0, b_s * b_s - du * du))
            est.append(([pi, (u, v_s - h), (u, v_s + h), po], True))
        else:
            est.append((cuatro(pi, po), False))
    return [([(-u, v) for u, v in pts], cal) for pts, cal in est] + est[::-1][1:]


def _chapa(bm, estaciones, S, espesor):
    """Chapa con espesor sobre las estaciones: cara delantera S(u, v, 0), trasera S(u, v, espesor) y canto recto
    en todo el borde (exterior y calado). Los puntos repetidos de una estación se funden en un solo vértice."""
    frente, atras, mapa = [], [], {}
    for pts, _cal in estaciones:
        ff, fb = [], []
        for j, (u, v) in enumerate(pts):
            if j > 0 and abs(u - pts[j - 1][0]) + abs(v - pts[j - 1][1]) < 1e-9:
                ff.append(ff[-1])
                fb.append(fb[-1])
                continue
            ff.append(bm.verts.new(S(u, v, 0.0)))
            fb.append(bm.verts.new(S(u, v, espesor)))
            mapa[ff[-1]] = fb[-1]
        frente.append(ff)
        atras.append(fb)
    caras = []
    for i in range(len(estaciones) - 1):
        for j in range(3):
            if j == 1 and estaciones[i][1] and estaciones[i + 1][1]:
                continue                                  # calado
            for filas, cara in ((frente, True), (atras, False)):
                unicos = []
                for v in (filas[i][j], filas[i + 1][j], filas[i + 1][j + 1], filas[i][j + 1]):
                    if v not in unicos:
                        unicos.append(v)
                if len(unicos) >= 3:
                    f = bm.faces.new(unicos if cara else unicos[::-1])
                    f.smooth = True
                    if cara:
                        caras.append(f)
    # lista ordenada (no un set: el orden de un set de elementos de bmesh depende de la memoria y cambiaría el
    # orden de las caras entre corridas)
    borde = list(dict.fromkeys(e for f in caras for e in f.edges if len(e.link_faces) == 1))
    for e in borde:
        a, b = e.verts
        bm.faces.new((a, b, mapa[b], mapa[a])).smooth = True


def silla_comedor(col, prefijo, material=NEGRO):
    """Silla bistró industrial de chapa de acero estampado, genérica. Asiento de 0,43 × 0,42 con cima a 0,45,
    levemente cóncavo, con borde enrollado de Ø 13 mm y faldón; cuatro patas de chapa en U, ahusadas y abiertas,
    remachadas por dentro del faldón en las esquinas; respaldo de una sola chapa en arco: dos brazos que se
    remachan planos al faldón trasero, saltan el borde enrollado y suben inclinados abriéndose hasta una banda
    curva en planta con calado de agarre. Alto 0,84. `material`: Depto_Mat_MetalNegroMate por defecto (acero
    pintado negro mate: en el render se lee más limpio que el pavonado, cuyas manchas ensucian el cóncavo del
    asiento) o Depto_Mat_AceroNegro."""
    K = SILLA_COMEDOR
    zs, alto = K["alto_asiento"], K["alto"]
    ax, ay = K["asiento"][0] / 2, K["asiento"][1] / 2
    r0, rb, e = K["r_esquina"], K["r_rollo"], K["chapa"]
    bm = bmesh.new()

    # --- asiento: una chapa cerrada (u = entrada desde el borde, z): cóncavo, rollo, faldón y cara inferior
    z_bajo = zs - K["concavo"] - e
    zf = zs - K["faldon"]
    perfil = [(0.165, zs - 0.0100), (0.110, zs - 0.0094), (0.065, zs - 0.0070), (0.030, zs - 0.0032)]
    for a in (90, 50, 10, -30, -70):                          # rollo de radio rb, de la cima hacia afuera y abajo
        t = math.radians(a)
        perfil.append((rb - rb * math.cos(t), zs - rb + rb * math.sin(t)))
    perfil += [(0.0055, zs - 0.0145), (0.0060, zf), (0.0060 + e, zf), (0.0055 + e, z_bajo)]
    CB.loft(bm, [[(x, y, z) for x, y in CB.rr_contorno(ax - u, ay - u, max(r0 - u, 0.015), 4)]
                 for u, z in perfil])

    # --- patas en U (alma hacia afuera, en la diagonal de cada esquina) y sus remaches al faldón
    z_pt = z_bajo - 0.0003
    (w1, f1), (w0, f0) = K["pata_arriba"], K["pata_abajo"]
    px, py0, py1 = K["pie"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            n = Vector((sx, sy, 0.0)).normalized()
            t = Vector((-sy, sx, 0.0)).normalized()
            esq = Vector((sx * (ax - r0), sy * (ay - r0), 0.0))
            arriba = esq + n * K["pata_dentro"] + Vector((0.0, 0.0, z_pt))
            abajo = Vector((sx * px, py0 if sy < 0 else py1, 0.0))
            CB.loft(bm, [_perfil_u(abajo, n, t, w0, f0, e, 0.003), _perfil_u(arriba, n, t, w1, f1, e, 0.004)])
            _remache(bm, esq + n * (r0 - 0.0057) + Vector((0.0, 0.0, zs - 0.028)), n)

    # --- respaldo: la espina es la cara delantera de la chapa en x = 0 (plana contra el faldón, salta el rollo y
    # sube inclinada); a lo ancho la chapa se curva con radio r_curva, que crece desde 0 (brazos planos en el
    # faldón) hasta la banda
    tp = K["chapa_resp"]
    beta = math.radians(K["inclinacion"])
    y0 = ay - 0.0055 + 0.0002                                  # 0,2 mm fuera de la cara del faldón
    y1 = y0 + 0.0065                                           # por fuera del rollo
    espina = _espina([(y0, zs - 0.042), (y0, zs - 0.018), (y1, zs - 0.008),
                      (y1 + 0.6 * math.sin(beta), zs - 0.008 + 0.6 * math.cos(beta))], 0.008, 3)
    k_b = 1.0 / K["r_curva"]
    v_k0 = 0.05                                                # hasta aquí los brazos siguen planos

    def mapa(v_top):
        v_f = v_top - K["banda"][0] - K["acuerdo"]

        def S(u, v, n_):
            c, N = espina(v)
            t = max(0.0, min(1.0, (v - v_k0) / (v_f - v_k0)))
            k = k_b * t * t * (3 - 2 * t)
            if k < 1e-9:
                return c + Vector((u, 0.0, 0.0)) + N * n_
            a = k * u
            return c + Vector((math.sin(a) / k + n_ * math.sin(a), 0.0, 0.0)) + N * ((math.cos(a) - 1) / k
                                                                                    + n_ * math.cos(a))
        return S

    v_top = (alto - zs) / math.cos(beta)
    for _ in range(3):                                         # la esquina más alta de la banda queda en `alto`
        S = mapa(v_top)
        z_max = max(S(u, v, n_).z for pts, _cal in _estaciones_respaldo(K, v_top) for u, v in pts
                    for n_ in (0.0, tp))
        v_top += (alto - z_max) / math.cos(beta)
    S = mapa(v_top)
    _chapa(bm, _estaciones_respaldo(K, v_top), S, tp)
    for s in (-1, 1):                                          # dos remaches por brazo al faldón
        for u in (K["brazo"][0] + 0.0095, K["brazo"][1] - 0.0095):
            _remache(bm, S(s * u, 0.013, tp), espina(0.013)[1])
    _centrar([bm])
    return [B.objeto(col, f"{prefijo}_Estructura", bm, material, suave=True, angulo_suave=60)]


# =====================================================================================================
# Mesa bistró de balcón
# =====================================================================================================
MESA_BISTRO = dict(
    chapa=0.002,                 # supuesto: chapa de 2 mm
    faldon=0.025,                # pedido: canto visible de ≈ 0,025
    r_doblez=0.004,              # diseño: radio exterior del doblez del borde
    placa=(0.10, 0.006),         # diseño: placa de fijación de Ø 100 × 6 bajo la cubierta
    varilla=0.014,               # diseño: tres varillas macizas de Ø 14
    haz=0.0092,                  # diseño: eje de cada varilla a 9,2 mm del centro (2 mm entre varillas)
    z_abre=0.30,                 # diseño: vértice de la curva en que se abren las varillas
    r_curva=0.30,                # diseño: radio de esa curva
    r_pie=0.21,                  # diseño: pies a 0,21 del eje
    anillo=(0.042, 0.030),       # diseño: anillo que junta el haz, Ø 42 × 30
    regaton=(0.021, 0.011),      # supuesto: regatón de Ø 21 × 11
)


def mesa_bistro(col, prefijo, diametro=0.55, alto=0.72):
    """Mesa de balcón de acero negro, liviana: cubierta de chapa de 2 mm con el borde doblado hacia abajo (canto
    visible de 25 mm), placa de fijación y pie de tres varillas de Ø 14 en haz, juntas por un anillo, que se abren
    en una curva amplia hasta tres regatones. Un solo objeto (todo es acero)."""
    K = MESA_BISTRO
    R = diametro / 2
    t, lab, rb = K["chapa"], K["faldon"], K["r_doblez"]
    s45 = math.sqrt(0.5)
    bm = bmesh.new()
    B.torno(bm, [(0.0, alto), (R - rb - 0.004, alto), (R - rb, alto), (R - rb + rb * s45, alto - rb + rb * s45),
                 (R, alto - rb), (R, alto - lab), (R - t, alto - lab), (R - t, alto - t), (0.0, alto - t)], seg=40)
    # placa de fijación (entra 0,3 mm en la chapa)
    dp, epl = K["placa"]
    zp1, zp0 = alto - t + 0.0003, alto - t - epl
    CB.revolucion(bm, [(0.0, zp0), (dp / 2, zp0), (dp / 2, zp1), (0.0, zp1)], seg=18)
    # varillas: nacen dentro de la placa, bajan en haz y se abren hacia los regatones
    rv = K["varilla"] / 2
    rg, hg = K["regaton"][0] / 2, K["regaton"][1]
    z_fin = hg - 0.002
    abre = 0.0
    antes = set(bm.faces)
    for k in range(3):
        a = math.radians(-90 + 120 * k)                        # una varilla hacia el frente (−Y)
        d = Vector((math.cos(a), math.sin(a), 0.0))
        p0 = d * K["haz"] + Vector((0.0, 0.0, zp0 + 0.002))
        p1 = d * K["haz"] + Vector((0.0, 0.0, K["z_abre"]))
        p2 = d * K["r_pie"] + Vector((0.0, 0.0, z_fin))
        _tubo(bm, [p0, p1, p2], rv, seg=8, radios=[0.0, K["r_curva"], 0.0], pasos=4)
        dd = (p2 - p1).normalized()
        c = p2 + dd * ((hg - 0.0005 - p2.z) / dd.z)            # donde el eje cruza la cara de arriba del regatón
        CB.revolucion(bm, [(0.0, 0.0), (rg, 0.0), (rg, hg), (0.0, hg)], centro=(c.x, c.y, 0.0), seg=12)
        abre = math.acos(max(-1.0, min(1.0, -dd.z)))
    varillas = set(bm.faces) - antes                           # varillas y regatones: conservan la UV de caja
    # anillo sobre el comienzo de la curva
    ra, ha = K["anillo"][0] / 2, K["anillo"][1]
    za = K["z_abre"] + K["r_curva"] * math.tan(abre / 2) + 0.004
    CB.revolucion(bm, [(0.0, za), (ra, za), (ra, za + ha), (0.0, za + ha)], seg=16)
    _uv_cilindro(bm, [f for f in bm.faces if f not in varillas])
    return [B.objeto(col, f"{prefijo}_Estructura", bm, ACERO, suave=True, angulo_suave=50, uv="propia")]


# =====================================================================================================
# Silla bistró plegable de balcón
# =====================================================================================================
SILLA_BISTRO = dict(
    tubo=0.020,                  # supuesto: tubo de acero de Ø 20 mm (usual en sillas plegables)
    alto_asiento=0.45,           # pedido
    alto=0.82,                   # pedido: alto total ≈ 0,82 (cima del domo de las patas traseras)
    listones=5,                  # pedido: cinco listones de asiento
    liston=(0.064, 0.018),       # diseño: listón de 64 × 18
    junta=0.012,                 # diseño: junta de 12 mm entre listones
    largo_liston=(0.42, 0.37),   # diseño: asiento trapecial, 0,42 adelante y 0,37 atrás (libra las patas)
    frente_asiento=-0.205,       # diseño: canto delantero del asiento (antes de centrar)
    x_larguero=0.176,            # diseño: eje de patas delanteras y largueros
    x_trasera=0.198,             # diseño: patas traseras por fuera de los largueros (2 mm de buje entre tubos)
    pie_delantero=-0.215,        # diseño: el pie delantero avanza 2,5 cm respecto de la esquina del asiento
    esquina=-0.190,              # diseño: y de la esquina delantera (curva de radio 0,03)
    pie_trasero=0.255,           # diseño: pie trasero
    rodilla=(0.172, 0.47),       # diseño: quiebre de la pata trasera (y, z), radio 0,12
    tope=(0.215, 0.81),          # diseño: punta del eje de la pata trasera (con el domo llega a 0,82)
    cola=0.032,                  # diseño: el larguero sigue 32 mm detrás del pivote
    respaldo=3,                  # pedido: tres listones de respaldo
    liston_resp=(0.058, 0.016),  # diseño: listón de respaldo de 58 × 16
    junta_resp=0.020,            # diseño
    r_resp=0.75,                 # diseño: curva en planta de los listones de respaldo (cóncavos hacia adelante)
    largo_resp=0.425,            # diseño: largo de los listones de respaldo (huella de ≈ 0,425 de ancho)
    cima_resp=0.80,              # diseño: canto de arriba del listón superior
    travesano=(0.10, 0.14),      # diseño: alturas de los travesaños delantero y trasero
    r_travesano=0.007,           # diseño: travesaños de Ø 14
)


def silla_bistro(col, prefijo):
    """Silla plegable de balcón estilo bistró parisino. Cada pata delantera y su larguero del asiento son un solo
    tubo de Ø 20 doblado en la esquina delantera; el larguero cruza la pata trasera (por dentro) en un pivote a la
    vista (perno de cabeza redonda, buje y tuerca hexagonal) y sigue 32 mm detrás. Las patas traseras suben con un
    quiebre a la altura del asiento y forman los montantes del respaldo; largueros y montantes terminan en tapones
    abombados. Travesaños bajos adelante y atrás. Cinco listones de asiento de roble (asiento trapecial) y tres de
    respaldo curvos, atornillados al frente de los montantes. Asiento a 0,45, alto 0,82."""
    K = SILLA_BISTRO
    rt = K["tubo"] / 2
    zs = K["alto_asiento"]
    b_l, e_l = K["liston"]
    z_r = zs - e_l - 0.0002 - rt                               # eje del larguero: el listón apoya sobre él
    xa, xb = K["x_larguero"], K["x_trasera"]
    y_pt, (yk, zk), (yt, ztop) = K["pie_trasero"], K["rodilla"], K["tope"]
    y_pd, y_esq = K["pie_delantero"], K["esquina"]

    def y_trasera(z):                                          # eje de la pata trasera, tramo bajo
        return y_pt + (yk - y_pt) * z / zk

    def y_delantera(z):                                        # eje de la pata delantera, tramo recto
        return y_pd + (y_esq - y_pd) * z / z_r

    y_piv = y_trasera(z_r)
    bm_t, bm_m = bmesh.new(), bmesh.new()
    for s in (-1, 1):
        _tubo(bm_t, [(s * xb, y_pt, 0.0), (s * xb, yk, zk), (s * xb, yt, ztop)], rt, seg=8, radios=[0.0, 0.12, 0.0],
              pasos=4, ini="piso", fin="domo")
        _tubo(bm_t, [(s * xa, y_pd, 0.0), (s * xa, y_esq, z_r), (s * xa, y_piv + K["cola"], z_r)], rt, seg=8,
              radios=[0.0, 0.03, 0.0], pasos=5, ini="piso", fin="domo")
        # pivote: cabeza abombada por fuera de la pata trasera, buje en la luz entre tubos, tuerca por dentro
        rh = 0.0068
        base = xb + math.sqrt(rt * rt - rh * rh)
        CB.revolucion(bm_t, [(0.0, 0.0), (rh, 0.0), (rh, 0.0032), (rh * 0.72, 0.0062), (0.0, 0.0074)],
                      centro=(s * base, y_piv, z_r), eje=(s, 0.0, 0.0), seg=10)
        CB.revolucion(bm_t, [(0.0, 0.0), (0.005, 0.0), (0.005, 0.006), (0.0, 0.006)],
                      centro=(s * (xa + 0.008), y_piv, z_r), eje=(s, 0.0, 0.0), seg=8)
        base = xa - math.sqrt(rt * rt - rh * rh)
        CB.revolucion(bm_t, [(0.0, 0.0), (rh, 0.0), (rh, 0.0055), (0.0, 0.0055)], centro=(s * base, y_piv, z_r),
                      eje=(-s, 0.0, 0.0), seg=6, giro=30.0)
    zf, zt = K["travesano"]
    for x, y, z in ((xa, y_delantera(zf), zf), (xb, y_trasera(zt), zt)):
        _tubo(bm_t, [(-x, y, z), (x, y, z)], K["r_travesano"], seg=8)

    # listones del asiento (roble, cantos achaflanados), trapecio: más largos adelante
    n = K["listones"]
    L0, L1 = K["largo_liston"]
    for i in range(n):
        ya = K["frente_asiento"] + i * (b_l + K["junta"])
        L = L0 + (L1 - L0) * i / (n - 1)
        CB.losa_rr(bm_m, L / 2, b_l / 2, 0.006, zs - e_l, zs, 0.003, n_esq=1, n_canto=1, cy=ya + b_l / 2)

    # listones del respaldo: curvos en planta, apoyados en el frente de los montantes
    ev = Vector((0.0, yt - yk, ztop - zk)).normalized()
    ed = Vector((0.0, ev.z, -ev.y))                            # hacia atrás, normal al respaldo
    ex = Vector((1.0, 0.0, 0.0))
    Rb = K["r_resp"]
    fe = math.asin(xb / Rb)                                    # ángulo en que el listón toca el montante
    fm = math.asin(K["largo_resp"] / 2 / Rb)
    De = -(rt + 0.0008)                                        # cara de atrás del listón, 0,8 mm delante del tubo
    Dc = De - Rb * math.cos(fe)
    hb, eb = K["liston_resp"]
    c = 0.0025
    sec = [(Rb, -hb / 2 + c), (Rb, hb / 2 - c), (Rb - c, hb / 2), (Rb - eb + c, hb / 2), (Rb - eb, hb / 2 - c),
           (Rb - eb, -hb / 2 + c), (Rb - eb + c, -hb / 2), (Rb - c, -hb / 2)]
    angs = [-fm, -fe, -2 * fe / 3, -fe / 3, 0.0, fe / 3, 2 * fe / 3, fe, fm]
    tau0 = (K["cima_resp"] - zk) / ev.z - hb / 2
    for k in range(K["respaldo"]):
        C = Vector((0.0, yk, zk)) + ev * (tau0 - k * (hb + K["junta_resp"]))
        CB.loft(bm_m, [[C + ex * (r * math.sin(f)) + ed * (Dc + r * math.cos(f)) + ev * w for r, w in sec]
                       for f in angs])
        for f in (-fe, fe):                                    # tornillos de cabeza redonda sobre cada montante
            nrm = -(ex * math.sin(f) + ed * math.cos(f))
            p = C + ex * ((Rb - eb) * math.sin(f)) + ed * (Dc + (Rb - eb) * math.cos(f))
            _remache(bm_t, p, nrm, r=0.0045, h=0.0022, hundido=0.0005)
    _centrar([bm_t, bm_m])
    return [B.objeto(col, f"{prefijo}_Estructura", bm_t, ACERO, suave=True, angulo_suave=50),
            B.objeto(col, f"{prefijo}_Listones", bm_m, MADERA, suave=True, angulo_suave=35)]
