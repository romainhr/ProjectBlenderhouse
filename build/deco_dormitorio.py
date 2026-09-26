"""Dormitorios de la decoración industrial (versión 2): cama, velador, lámpara de mesa y espejo de pie.

Especificación: docs/deco-industrial.md, sección «Dormitorios». Cada función crea sus objetos en `col` con nombres
f"{prefijo}_{Parte}", en coordenadas locales (m, Z arriba): huella centrada en el origen, apoyada en z = 0, frente
hacia −Y y espalda hacia +Y. Todos los objetos quedan con origen (0, 0, 0) y sin rotación.

Sin booleanos ni subdivisión. Las formas blandas salen de superficies paramétricas con semilla fija:
- el cabecero es un barrido de su perfil lateral a lo largo de X, con el bombé de cada canal del capitoné;
- la ropa de cama son capas de tela de dos caras (arriba y abajo, unidas en la costura) drapeadas sobre el colchón:
  un punto (s, t) de la tela plana se lleva a la cara superior, al canto redondeado o a la caída vertical;
- almohadas y cojines son sacos de dos caras con esquinas pellizcadas, asentados contra el cabecero y la cama.
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector

import deco_base as B
import depto_geom as G

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))

# ---------------------------------------------------------------- cama: medidas
COLCHON = (1.80, 2.00)            # brief: king de 1,80 × 2,00
Z_PLATAFORMA = (0.10, 0.30)       # diseño (docs): plataforma de tubo de acero de 0,10 a 0,30
Z_COLCHON = (0.30, 0.55)          # diseño (docs): colchón de 0,30 a 0,55 (alto de cama del brief)
R_COLCHON = 0.04                  # supuesto: canto redondeado de un colchón con sábana ajustable
Y_COLCHON_CABECERA = 0.95         # armado: cabecero de y 0,955 a 1,05 detrás (al final la huella se centra en Y)
VUELO_PLATAFORMA = (0.02, 0.01)   # diseño: el marco asoma 2 cm por los costados y 1 cm a los pies
PERFIL_RIEL = (0.04, 0.004)       # supuesto: tubo rectangular de 200 × 40 mm, canto de 4 mm
PATA = (0.05, 0.10)               # supuesto: tubo cuadrado de 50 mm; alto = 0,10 (base de la plataforma)
PATA_X = 0.78                     # diseño: patas retranqueadas 14 cm (la cama parece flotar)
PATAS_Y = (-0.93, -0.05, 0.83)    # diseño: seis patas, bajo tres travesaños
TRAVESANO = (0.05, 0.05)          # supuesto: travesaños de 50 × 50 mm a ras de la base de los rieles
ALTO_CABECERO = 1.05              # diseño (docs): cabecero de 1,05 de alto
CABECERO = dict(
    ancho=1.90,                   # diseño (docs): 1,90 × 1,05 de alto, de pie en el suelo
    espalda=1.05,                 # armado: espalda del cabecero (10 cm detrás del colchón en el centro del canal)
    frente=0.985,                 # supuesto: 6,5 cm de espesor en las costuras
    bombe=0.030,                  # supuesto: el canal se infla 3 cm (9,5 cm en el centro de cada canal)
    z0=0.08,                      # diseño: el panel se apoya en dos pies de 8 cm
    caida_costura=0.012,          # supuesto: el borde superior baja 1,2 cm en cada costura (festón)
    canales=9,                    # diseño: 9 canales verticales de 0,211 (impar: uno al centro de la cama)
    muestras_canal=10,
    r_sup=(0.030, 0.050),         # radio del canto superior delantero en la costura y en el centro del canal
    r_inf=0.020, r_esp=0.008,     # radios del canto inferior delantero y de los cantos de la espalda
    r_extremo=0.035,              # los costados del cabecero se redondean como un rulo
    exponente=0.35,               # forma del bombé: sin(pi u)^e, e < 1 da costuras hundidas y canales llenos
    pies_x=0.70, pies=(0.04, 0.03),
)
HOLGURA = 0.003                   # separación mínima entre telas y lo que tienen debajo
SOBRE_EDREDON = 0.004             # separación de la sábana y la manta sobre el edredón (error de cuerda de los pliegues)
EDREDON = dict(desde_cabecera=0.55, caida=0.22, espesor=0.045, borde=0.07, esquina_extra=0.015,  # docs + supuestos
               aplaste=0.50)               # en la caída el relleno se asienta (espesor −50 %)
SABANA = dict(desde=0.13, hasta=0.52, espesor=0.005, borde=0.018, caida=0.20)   # sábana doblada sobre el edredón
MANTA = dict(desde=-0.93, hasta=-0.50, espesor=0.028, caida=0.17)                # manta doblada a los pies
ALMOHADA = dict(medidas=(0.72, 0.50, 0.17), x=0.40, inclinacion=58, giro=2.0, forma=0.5)    # supuesto: king
COJIN = dict(medidas=(0.42, 0.42, 0.15), x=0.36, inclinacion=66, giro=-4.0, forma=0.75, recogido=0.08,
             vivo=0.004, ladeo=5.0)  # 42 cm con vivo; ladeo: giro en su plano, casual


# ---------------------------------------------------------------- ayudas propias del módulo
def _suave(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def _rect_redondeado(a0, a1, b0, b1, radios, segs):
    """Contorno cerrado (antihorario en el plano a-b) de un rectángulo con un radio por esquina, en el orden
    (a0,b0), (a1,b0), (a1,b1), (a0,b1). La cantidad de puntos no depende de los radios (sum(segs) + 4), así los
    contornos sucesivos de un barrido se unen aunque los radios cambien."""
    radios = radios if isinstance(radios, (list, tuple)) else (radios,) * 4
    segs = segs if isinstance(segs, (list, tuple)) else (segs,) * 4
    esquinas = ((a0, b0, 1, 1, 180), (a1, b0, -1, 1, 270), (a1, b1, -1, -1, 0), (a0, b1, 1, -1, 90))
    pts = []
    for (ca, cb, sa, sb, ang0), r, n in zip(esquinas, radios, segs):
        r = max(r, 2e-4)
        c0, c1 = ca + sa * r, cb + sb * r
        for k in range(n + 1):
            a = math.radians(ang0 + 90 * k / n)
            pts.append((c0 + r * math.cos(a), c1 + r * math.sin(a)))
    return pts


def _marco_ingleteado(bm, origen, eu, ev, en, ancho, alto, perfil):
    """Marco rectangular con esquinas a inglete: barre un perfil cerrado alrededor de un rectángulo.
    origen: esquina (0, 0) del borde exterior; eu, ev: ejes del plano (ancho, alto); en: eje del espesor.
    perfil: [(i, d)] cerrado; i = distancia hacia adentro desde el borde exterior, d = coordenada según en."""
    lazos = []
    for i, d in perfil:
        esq = ((i, i), (ancho - i, i), (ancho - i, alto - i), (i, alto - i))
        lazos.append([bm.verts.new(origen + eu * u + ev * v + en * d) for u, v in esq])
    for k in range(len(lazos)):
        a, b = lazos[k], lazos[(k + 1) % len(lazos)]
        for c in range(4):
            c2 = (c + 1) % 4
            bm.faces.new((a[c], a[c2], b[c2], b[c]))


def _torno(bm, perfil, seg, indices=None, suave=True):
    """Superficie de revolución alrededor de Z (como deco_base.torno) con material_index por tramo del perfil:
    indices[k] vale para el tramo entre perfil[k] y perfil[k + 1]. Un radio 0 es un polo."""
    anillos = []
    for r, z in perfil:
        if r < 1e-7:
            anillos.append([bm.verts.new((0.0, 0.0, z))])
        else:
            anillos.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z))
                            for i in range(seg)])
    for k, (a, b) in enumerate(zip(anillos[:-1], anillos[1:])):
        for i in range(seg):
            j = (i + 1) % seg
            if len(a) == 1:
                f = bm.faces.new((a[0], b[i], b[j]))
            elif len(b) == 1:
                f = bm.faces.new((a[i], a[j], b[0]))
            else:
                f = bm.faces.new((a[i], a[j], b[j], b[i]))
            f.smooth = suave
            f.material_index = indices[k] if indices else 0
    return anillos


def _eje(tramos, extra=(), tol=0.004):
    """Muestras ordenadas de un eje: tramos [(a, b, paso)] uniformes más puntos extra (refinar bordes); descarta
    las que quedan a menos de `tol` de una ya tomada (los extremos de los tramos y los extra mandan)."""
    fijos = sorted({round(v, 6) for a, b, _ in tramos for v in (a, b)} | {round(v, 6) for v in extra})
    libres = []
    for a, b, paso in tramos:
        n = max(1, round(abs(b - a) / paso))
        libres += [a + (b - a) * k / n for k in range(1, n)]
    out = list(fijos)
    for v in sorted(libres):
        if all(abs(v - w) >= tol for w in out):
            out.append(v)
    return sorted(out)


def _sub_eje(muestras, a, b, extra=(), tol=0.004):
    """Las muestras de otro eje que caen dentro de [a, b], más a, b y los extra (que mandan si quedan cerca)."""
    fijos = sorted({a, b} | {v for v in extra if a <= v <= b})
    out = list(fijos)
    for v in muestras:
        if a < v < b and all(abs(v - w) >= tol for w in out):
            out.append(v)
    return sorted(out)


def _refinar(a, b, ancho):
    """Puntos extra cerca de los dos bordes de [a, b], donde la tela se cierra en su costura."""
    return [a + ancho * f for f in (0.12, 0.35, 0.65)] + [b - ancho * f for f in (0.12, 0.35, 0.65)]


def _caja(bm, x0, x1, y0, y1, z0, z1, r=0.002, seg=1):
    B.caja_redondeada(bm, x0, x1, y0, y1, z0, z1, r, seg)


# ---------------------------------------------------------------- cama: telas
class _Apoyo:
    """Superficie sobre la que se apoya la ropa de cama: el colchón (caja de cantos redondeados) visto desde
    afuera y separado HOLGURA. Coordenadas de tela plana (s, t): s según X, t según Y. Dentro del rectángulo de la
    cara superior (|s| <= ax, t >= y_pie) la tela queda plana; fuera se envuelve por el canto (radio r) y cae."""

    RP = 0.12           # radio equivalente de las esquinas para la coordenada de perímetro (pliegues continuos)

    def __init__(self, ax, y_pie, z_sup, r, vuelo_lado=0.03, vuelo_esquina=0.18):
        self.ax, self.yp, self.z, self.r = ax, y_pie, z_sup, r
        self.arco = math.pi / 2 * r
        self.vl, self.ve = vuelo_lado, vuelo_esquina

    def punto(self, s, t, largo_esquina=None, extra_esquina=0.0):
        """-> (punto de apoyo, normal hacia afuera, caída bajo el canto (<0 sobre el colchón), perímetro, esquina).
        largo_esquina: largo de caída de la tela; si se da, la esquina de la tela se reparte para que el ruedo
        quede parejo (más extra_esquina en la diagonal, el peso de la punta)."""
        ex, ey = max(abs(s) - self.ax, 0.0), max(self.yp - t, 0.0)
        if ex == 0.0 and ey == 0.0:
            return Vector((s, t, self.z)), Z.copy(), -self.arco, None, 0.0
        d = math.hypot(ex, ey)
        th = math.atan2(ey, ex)                        # 0: costado, 90°: pies
        esq = math.sin(2 * th) if (ex > 0 and ey > 0) else 0.0
        if esq and largo_esquina:
            dmax = min(largo_esquina / max(math.cos(th), 1e-6), largo_esquina / max(math.sin(th), 1e-6))
            d *= (largo_esquina + extra_esquina * esq) / dmax
        dx, dy = math.copysign(math.cos(th), s) if ex > 0 else 0.0, -math.sin(th)
        bx = math.copysign(self.ax, s) if ex > 0 else s
        by = self.yp if ey > 0 else t
        caida = d - self.arco
        if caida <= 0:
            phi = d / self.r
            hor, z = self.r * math.sin(phi), self.z - self.r + self.r * math.cos(phi)
            n = Vector((dx * math.sin(phi), dy * math.sin(phi), math.cos(phi)))
        else:
            hor = self.r + (self.vl + self.ve * esq) * caida
            z = self.z - self.r - caida
            n = Vector((dx, dy, 0.0))
        p1 = 1.0 - self.yp
        if ey == 0.0:                                   # costados
            per = (1.0 - t) if s < 0 else p1 + math.pi * self.RP + 2 * self.ax + (t - self.yp)
        elif ex == 0.0:                                 # pies
            per = p1 + math.pi / 2 * self.RP + (s + self.ax)
        elif s < 0:                                     # esquina izquierda
            per = p1 + th * self.RP
        else:                                           # esquina derecha
            per = p1 + math.pi / 2 * self.RP + 2 * self.ax + (math.pi / 2 - th) * self.RP
        return Vector((bx + dx * hor, by + dy * hor, z)), n, caida, per, esq


class _Arrugas:
    """Desplazamiento hacia afuera (siempre >= 0, así ninguna tela entra en lo que tiene debajo): ondulación suave
    arriba y pliegues verticales en la caída, que crecen hacia el ruedo y son mayores en las esquinas."""

    def __init__(self, rng, amp_arriba=0.011, amp_pliegue=0.014):
        self.aa, self.ap = amp_arriba, amp_pliegue
        self.arriba = []
        for _ in range(5):
            lam, ang = rng.uniform(0.25, 0.70), rng.uniform(0, math.pi)
            k = 2 * math.pi / lam
            self.arriba.append((k * math.cos(ang), k * math.sin(ang), rng.uniform(0, 2 * math.pi), rng.uniform(0.5, 1)))
        self.pliegues = [(2 * math.pi / rng.uniform(0.20, 0.45), rng.uniform(0, 2 * math.pi), rng.uniform(0.5, 1),
                          rng.uniform(-0.6, 0.6)) for _ in range(4)]
        self.sa = sum(a for *_, a in self.arriba)
        self.sp = sum(a for _, _, a, _ in self.pliegues)

    def __call__(self, s, t, caida, per, esq):
        wa = self.aa * (0.5 + 0.5 * sum(a * math.sin(kx * s + ky * t + f) for kx, ky, f, a in self.arriba) / self.sa)
        if per is None:
            return wa
        k = _suave(-0.03, 0.05, caida)
        g = _suave(-0.02, 0.20, caida) * (1 + 0.8 * esq)
        fp = sum(a * math.sin(kk * per * (1 + dv * max(caida, 0)) + f) for kk, f, a, dv in self.pliegues) / self.sp
        return (1 - k) * wa + k * (0.5 * wa + self.ap * g * (0.5 + 0.5 * fp))


def _capa(bm, apoyo, ss, ts, espesor, base, arrugas, largo_esquina=None, extra_esquina=0.0, filas_abajo=None):
    """Capa de tela de dos caras que comparten el borde (costura), sobre el apoyo. espesor(s, t) debe valer 0 en el
    borde; base(s, t, h) es la separación de la cara de abajo sobre el apoyo. filas_abajo: la cara de abajo sólo se
    arma hasta esa cantidad de filas desde el borde (el resto queda oculto contra lo que la tela tiene debajo)."""
    ns, nt = len(ss), len(ts)
    arriba = [[None] * nt for _ in range(ns)]
    abajo = [[None] * nt for _ in range(ns)]
    for i, s in enumerate(ss):
        for j, t in enumerate(ts):
            p, n, caida, per, esq = apoyo.punto(s, t, largo_esquina, extra_esquina)
            h = espesor(s, t)
            b = base(s, t, h) + arrugas(s, t, caida, per, esq)
            arriba[i][j] = bm.verts.new(p + n * (b + h))
            k = min(i, j, ns - 1 - i, nt - 1 - j)
            if k == 0:
                abajo[i][j] = arriba[i][j]
            elif filas_abajo is None or k <= filas_abajo:
                abajo[i][j] = bm.verts.new(p + n * b)
    for i in range(ns - 1):
        for j in range(nt - 1):
            bm.faces.new((arriba[i][j], arriba[i + 1][j], arriba[i + 1][j + 1], arriba[i][j + 1]))
            q = (abajo[i][j + 1], abajo[i + 1][j + 1], abajo[i + 1][j], abajo[i][j])
            if all(q):
                bm.faces.new(q)


def _almohada(bm, ancho, largo, espesor, nu, nv, rng, matriz, forma=0.45, recogido=0.05):
    """Saco de dos caras (almohada o cojín) en el plano XY local, espesor según Z, con costura perimetral,
    costados que se recogen hacia el centro y esquinas pellizcadas; transformado por `matriz`. -> vértices.
    forma: exponente del perfil (bajo = lleno y de cantos duros; alto = más redondo); recogido: cuánto se meten
    los costados en su punto medio."""
    us = [(1 - math.cos(math.pi * k / nu)) / 2 for k in range(nu + 1)]
    vs = [(1 - math.cos(math.pi * k / nv)) / 2 for k in range(nv + 1)]
    f = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
    arriba = [[None] * (nv + 1) for _ in range(nu + 1)]
    abajo = [[None] * (nv + 1) for _ in range(nu + 1)]
    for i, u in enumerate(us):
        for j, v in enumerate(vs):
            su, sv = math.sin(math.pi * u), math.sin(math.pi * v)
            h = espesor * (su * sv) ** forma
            x = (u - 0.5) * ancho * (1 - recogido * sv)
            y = (v - 0.5) * largo * (1 - recogido * su)
            r1 = 1 + 0.05 * math.sin(2 * math.pi * 1.3 * u + f[0]) * math.sin(2 * math.pi * v + f[1])
            r2 = 1 + 0.05 * math.sin(2 * math.pi * u + f[2]) * math.sin(2 * math.pi * 1.2 * v + f[3])
            arriba[i][j] = bm.verts.new(matriz @ Vector((x, y, h / 2 * r1)))
            borde = i in (0, nu) or j in (0, nv)
            abajo[i][j] = arriba[i][j] if borde else bm.verts.new(matriz @ Vector((x, y, -h / 2 * r2)))
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((arriba[i][j], arriba[i + 1][j], arriba[i + 1][j + 1], arriba[i][j + 1]))
            bm.faces.new((abajo[i][j + 1], abajo[i + 1][j + 1], abajo[i + 1][j], abajo[i][j]))
    borde = ([arriba[0][j] for j in range(nv)] + [arriba[i][nv] for i in range(nu)] +
             [arriba[nu][j] for j in range(nv, 0, -1)] + [arriba[i][0] for i in range(nu, 0, -1)])
    return list({v for fila in arriba + abajo for v in fila}), borde


def _asentar(verts, altura, planos, penetracion=0.006, vueltas=6):
    """Apoya un saco blando: lo traslada hasta que entra `penetracion` en la cama (z >= altura(x, y)) y en cada
    plano [(p0, n)] (lado permitido: (v - p0)·n >= 0), y luego aplasta lo que entró (parche de contacto plano).
    -> traslación total aplicada."""
    total = Vector((0, 0, 0))
    for _ in range(vueltas):
        for p0, n in planos:
            m = min((v.co - p0).dot(n) for v in verts)
            dv = n * (-penetracion - m)
            for v in verts:
                v.co += dv
            total += dv
        m = min(v.co.z - altura(v.co.x, v.co.y) for v in verts)
        dz = -penetracion - m
        for v in verts:
            v.co.z += dz
        total.z += dz
    for v in verts:
        for p0, n in planos:
            d = (v.co - p0).dot(n)
            if d < 0:
                v.co -= n * d
        zc = altura(v.co.x, v.co.y) + 0.0005
        if v.co.z < zc:
            v.co.z = zc
    return total


# ---------------------------------------------------------------- cama: piezas rígidas
def _perfil_cabecero(p, delta, alto):
    C = CABECERO
    yf = C["frente"] - C["bombe"] * p + delta
    yb = C["espalda"] - delta
    z0 = C["z0"] + delta
    z1 = alto - C["caida_costura"] * (1 - p) - delta
    r_ft = C["r_sup"][0] + (C["r_sup"][1] - C["r_sup"][0]) * p - delta
    r_fb, r_b = C["r_inf"] - delta, C["r_esp"] - delta
    return _rect_redondeado(yf, yb, z0, z1, (r_fb, r_b, r_b, r_ft), (3, 2, 2, 7))


def _cabecero(bm, alto, m=CABECERO["muestras_canal"]):
    """Panel tapizado con capitoné de canales verticales: barrido del perfil lateral a lo largo de X (m muestras
    por canal)."""
    C = CABECERO
    w, n, re = C["ancho"], C["canales"], C["r_extremo"]
    wc = w / n
    xs = [-w / 2 + (c + (1 - math.cos(math.pi * k / m)) / 2) * wc for c in range(n) for k in range(m)] + [w / 2]
    for k in range(1, 6):                                 # rulo de los costados: cuarto de círculo
        q = math.sin(math.pi / 2 * k / 6)
        xs += [w / 2 - re + re * q, -(w / 2 - re + re * q)]
    xs = sorted(xs)
    xs = [x for i, x in enumerate(xs) if i == 0 or x - xs[i - 1] > 0.0015]
    lazos = []
    for x in xs:
        c = min(max(int((x + w / 2) / wc), 0), n - 1)
        u = (x + w / 2) / wc - c
        if (c == 0 and u < 0.5) or (c == n - 1 and u > 0.5):
            p = 1.0                                       # los canales de los extremos envuelven el costado
        else:
            p = max(math.sin(math.pi * min(max(u, 0.0), 1.0)), 0.0) ** C["exponente"]
        q = max(abs(x) - (w / 2 - re), 0.0) / re
        delta = re * (1 - math.sqrt(max(1 - q * q, 0.0)))
        lazos.append([bm.verts.new((x, a, b)) for a, b in _perfil_cabecero(p, delta, alto)])
    for a, b in zip(lazos[:-1], lazos[1:]):
        for k in range(len(a)):
            k2 = (k + 1) % len(a)
            bm.faces.new((a[k], a[k2], b[k2], b[k])).smooth = True
    bm.faces.new(lazos[0])
    bm.faces.new(list(reversed(lazos[-1])))


def _estructura(bm):
    """Plataforma de acero: riel perimetral a inglete, tres travesaños, seis patas, tablero y pies del cabecero."""
    ax = COLCHON[0] / 2 + VUELO_PLATAFORMA[0]
    y0 = Y_COLCHON_CABECERA - COLCHON[1] - VUELO_PLATAFORMA[1]
    y1 = Y_COLCHON_CABECERA
    e, r = PERFIL_RIEL
    z0, z1 = Z_PLATAFORMA
    perfil = [(i, z) for i, z in _rect_redondeado(0.0, e, z0, z1, r, 2)]
    _marco_ingleteado(bm, Vector((-ax, y0, 0.0)), X, Y, Z, 2 * ax, y1 - y0, perfil)
    ai = ax - e                                            # cara interior de los rieles
    lp, hp = PATA
    wt, ht = TRAVESANO
    for yc in PATAS_Y:
        _caja(bm, -ai, ai, yc - wt / 2, yc + wt / 2, z0, z0 + ht, 0.003, 1)
        for sx in (-1, 1):
            _caja(bm, sx * PATA_X - lp / 2, sx * PATA_X + lp / 2, yc - lp / 2, yc + lp / 2, 0.0, hp, 0.003, 1)
    B.caja(bm, -ai, ai, y0 + e, y1 - e, z1 - 0.015, z1 - 0.0005)    # tablero de apoyo del colchón (oculto)
    C = CABECERO
    fx, fy = C["pies"]
    ym = (C["frente"] + C["espalda"]) / 2 + 0.005
    for sx in (-1, 1):
        _caja(bm, sx * C["pies_x"] - fx / 2, sx * C["pies_x"] + fx / 2, ym - fy / 2, ym + fy / 2, 0.0, C["z0"] - 0.0005, 0.003, 1)


# ---------------------------------------------------------------- cama
def cama(col, prefijo, tapiz="Depto_Mat_Lana", cojines=None, manta="Depto_Mat_Manta", edredon="Depto_Mat_Cobertor",
         sabanas="Depto_Mat_Textil", alto_cabecero=ALTO_CABECERO, semilla=7, resolucion=1.0):
    """Cama king sobre plataforma de acero negro, cabecero tapizado con capitoné de canales (material `tapiz`:
    Depto_Mat_Lana o Depto_Mat_Cuero) y ropa de cama completa. Cabecero hacia +Y, pies hacia −Y; al final la huella
    completa (con la caída de la ropa de cama) se centra en el origen.
    resolucion: densidad de la malla de telas, cabecero, almohadas y cojines (1 = la de la especificación; 0,7
    deja la cama en ≈ 60 % de los triángulos con los mismos cantos y pliegues, sólo con cuerdas más largas)."""
    for m in (tapiz, manta, edredon, sabanas) + ((cojines,) if cojines else ()):
        assert m in G.MATERIALES, f"material desconocido: {m}"
    if cojines is None:                                  # contraste con el cabecero
        cojines = "Depto_Mat_Manta" if tapiz == "Depto_Mat_Lana" else "Depto_Mat_Lana"
    rng = random.Random(semilla)
    k = 1.0 / resolucion                                  # factor de los pasos de muestreo
    ancho, largo = COLCHON
    y_cab, y_pie = Y_COLCHON_CABECERA, Y_COLCHON_CABECERA - largo
    zc0, zc1 = Z_COLCHON
    partes = []                                           # (parte, bmesh, material, ángulo de suavizado)

    bm = bmesh.new()
    _estructura(bm)
    partes.append(("Estructura", bm, "Depto_Mat_AceroNegro", 35))
    bm = bmesh.new()
    _cabecero(bm, alto_cabecero, max(4, round(CABECERO["muestras_canal"] * resolucion)))
    partes.append(("Cabecero", bm, tapiz, 50))

    # ---- telas sobre el colchón
    apoyo = _Apoyo(ancho / 2 - R_COLCHON, y_pie + R_COLCHON, zc1 + HOLGURA, R_COLCHON + HOLGURA)
    arrugas = _Arrugas(rng)
    ax, arco = apoyo.ax, apoyo.arco
    zc_canto = apoyo.z - apoyo.r

    def largo_caida(caida):                               # largo de tela plana para caer `caida` bajo la cara superior
        return arco + (zc_canto - (zc1 - caida))

    def caida_plana(s, t):                                # caída aproximada de (s, t), sin repartir la esquina
        return math.hypot(max(abs(s) - ax, 0.0), max(apoyo.yp - t, 0.0)) - arco

    def eje_s(r):                                         # más muestras en el canto y la caída que arriba
        return _eje([(r[0], -(ax + arco), 0.035 * k), (-(ax + arco), -ax, 0.017 * k), (-ax, ax, 0.05 * k),
                     (ax, ax + arco, 0.017 * k), (ax + arco, r[1], 0.035 * k)], _refinar(r[0], r[1], 0.05))

    def dentro(r, s, t):
        return r[0] <= s <= r[1] and r[2] <= t <= r[3]

    def dist(r, s, t):
        return min(s - r[0], r[1] - s, t - r[2], r[3] - t)

    E = EDREDON
    L = largo_caida(E["caida"])
    ed = (-(ax + L), ax + L, apoyo.yp - L, y_cab - E["desde_cabecera"])
    ondas = [(2 * math.pi / rng.uniform(0.25, 0.6), rng.uniform(0, math.pi), rng.uniform(0, 2 * math.pi))
             for _ in range(3)]

    def h_edredon(s, t):
        if not dentro(ed, s, t):
            return 0.0
        e = math.sin(math.pi / 2 * min(dist(ed, s, t) / E["borde"], 1.0)) ** 0.6
        inflado = sum(math.sin(k * (s * math.cos(a) + t * math.sin(a)) + f) for k, a, f in ondas) / 3
        colgado = 1 - E["aplaste"] * _suave(-0.02, 0.10, caida_plana(s, t))   # en la caída el relleno se asienta
        return E["espesor"] * e * (0.88 + 0.12 * inflado) * colgado

    def sobre_edredon(s, t):                              # cara de arriba del edredón: base 0,15 h + espesor h
        return 1.15 * h_edredon(s, t)

    S = SABANA
    sa = (-(ax + largo_caida(S["caida"])), ax + largo_caida(S["caida"]), S["desde"], S["hasta"])

    def h_sabana(s, t):
        if not dentro(sa, s, t):
            return 0.0
        return S["espesor"] * math.sin(math.pi / 2 * min(dist(sa, s, t) / S["borde"], 1.0)) ** 0.5

    M = MANTA
    ma = (-(ax + largo_caida(M["caida"])), ax + largo_caida(M["caida"]), M["desde"], M["hasta"])

    def h_manta(s, t):
        if not dentro(ma, s, t):
            return 0.0
        q = min(dist(ma, s, t) / M["espesor"], 1.0)      # canto del doblez: medio círculo
        colgado = 1 - 0.25 * _suave(-0.02, 0.10, caida_plana(s, t))
        return M["espesor"] * math.sqrt(max(1 - (1 - q) ** 2, 0.0)) * colgado

    # edredón (la cara de abajo sólo cerca del borde: el resto queda oculto sobre el colchón)
    ss_ed = eje_s(ed)
    ts_ed = _eje([(ed[2], apoyo.yp - arco, 0.035 * k), (apoyo.yp - arco, apoyo.yp, 0.017 * k), (apoyo.yp, ed[3], 0.05 * k)],
                 _refinar(ed[2], ed[3], E["borde"]))
    bm = bmesh.new()
    _capa(bm, apoyo, ss_ed, ts_ed, h_edredon, lambda s, t, h: 0.15 * h, arrugas, largo_esquina=L,
          extra_esquina=E["esquina_extra"], filas_abajo=5)
    partes.append(("Edredon", bm, edredon, 60))

    # Las capas que van encima del edredón usan sus mismas muestras (más las de su propio borde): así sus caras
    # siguen las mismas cuerdas y no lo atraviesan donde la tela se curva (canto, pliegues, borde de la cabecera).
    def sobre(muestras, a, b, borde, extra=()):
        return _sub_eje(muestras, a, b, list(_refinar(a, b, borde)) + list(extra))

    # manta doblada a los pies
    bm = bmesh.new()
    _capa(bm, apoyo, sobre(ss_ed, ma[0], ma[1], 0.05), sobre(ts_ed, ma[2], ma[3], M["espesor"]), h_manta,
          lambda s, t, h: sobre_edredon(s, t) + SOBRE_EDREDON, arrugas, filas_abajo=3)
    partes.append(("Manta", bm, manta, 60))

    # colchón con sábana ajustable, sábana encimera doblada sobre el edredón y almohadas (todo en el mismo textil)
    bm = bmesh.new()
    B.caja_redondeada(bm, -ancho / 2, ancho / 2, y_pie, y_cab, zc0, zc1, R_COLCHON, 3)
    ts_sa = ts_ed + _eje([(ed[3], sa[3], 0.045 * k)], (ed[3] + 0.012, ed[3] + 0.03))   # sigue hasta bajo las almohadas
    _capa(bm, apoyo, sobre(ss_ed, sa[0], sa[1], 0.05), sobre(ts_sa, sa[2], sa[3], S["borde"]), h_sabana,
          lambda s, t, h: sobre_edredon(s, t) + SOBRE_EDREDON, arrugas, filas_abajo=3)

    def altura(x, y):                                     # cara de arriba de la cama en la zona plana
        o = max(sobre_edredon(x, y), (sobre_edredon(x, y) + SOBRE_EDREDON + h_sabana(x, y)) if dentro(sa, x, y) else 0.0)
        return apoyo.z + o + arrugas(x, y, -1.0, None, 0.0)

    frente_cabecero = CABECERO["frente"] - CABECERO["bombe"] - 0.002
    plano_cabecero = (Vector((0, frente_cabecero, 0)), Vector((0, -1, 0)))
    frentes = []
    A = ALMOHADA
    for sx in (-1, 1):
        rot = Matrix.Rotation(math.radians(sx * A["giro"]), 4, "Z") @ Matrix.Rotation(math.radians(A["inclinacion"]), 4, "X")
        c0 = Vector((sx * A["x"], y_cab - 0.18, zc1 + 0.2))
        vs, _ = _almohada(bm, *A["medidas"], max(8, round(16 * resolucion)), max(6, round(12 * resolucion)), rng, Matrix.Translation(c0) @ rot, forma=A["forma"])
        mov = _asentar(vs, altura, [plano_cabecero])
        n = (rot.to_3x3() @ Z).normalized()
        frentes.append((c0 + mov + n * (A["medidas"][2] / 2 * 1.05), n))
    partes.append(("Sabanas", bm, sabanas, 50))

    # cojines, apoyados en las almohadas
    bm = bmesh.new()
    Cj = COJIN
    for sx, frente in zip((-1, 1), frentes):
        rot = (Matrix.Rotation(math.radians(sx * Cj["giro"]), 4, "Z") @
               Matrix.Rotation(math.radians(Cj["inclinacion"]), 4, "X") @
               Matrix.Rotation(math.radians(-sx * Cj["ladeo"]), 4, "Z"))           # ladeado en su plano
        c0 = frente[0] + frente[1] * 0.12 + Vector((sx * (Cj["x"] - A["x"]), 0, 0))
        vs, borde = _almohada(bm, *Cj["medidas"], max(6, round(12 * resolucion)), max(6, round(12 * resolucion)), rng, Matrix.Translation(c0) @ rot, forma=Cj["forma"],
                              recogido=Cj["recogido"])
        _asentar(vs, altura, [frente, plano_cabecero])
        pts = [v.co.copy() for v in borde]                # vivo (cordón) en la costura: dibuja el contorno
        B.tubo(bm, pts + pts[:1], Cj["vivo"], seg=5, tapas=False)
    partes.append(("Cojines", bm, cojines, 50))

    # huella completa centrada en el origen (la ropa de cama cae por los pies; el cabecero va atrás)
    pts = [v.co for _, bm, _, _ in partes for v in bm.verts]
    dx = -(min(p.x for p in pts) + max(p.x for p in pts)) / 2
    dy = -(min(p.y for p in pts) + max(p.y for p in pts)) / 2
    objs = []
    for parte, bm, mat, ang in partes:
        B.transformar(bm, Matrix.Translation((dx, dy, 0.0)))
        objs.append(B.objeto(col, f"{prefijo}_{parte}", bm, mat, suave=True, angulo_suave=ang))
    return objs


# ---------------------------------------------------------------- velador
def velador(col, prefijo, ancho=0.45, fondo=0.35, alto=0.52):
    """Velador de marco de tubo cuadrado de acero de 20 mm, con cubierta y repisa baja de roble ahumado."""
    E_TUBO = 0.020          # diseño (docs): tubo cuadrado de 20 mm
    E_CUBIERTA = 0.025      # supuesto: tabla de roble de 25 mm
    E_REPISA = 0.018        # supuesto: tabla de 18 mm
    VUELO = 0.010           # diseño: la cubierta vuela 1 cm sobre el marco
    Z_REPISA = 0.12         # diseño: repisa baja a 12 cm (cara de arriba del travesaño)
    fx, fy = ancho / 2 - VUELO, fondo / 2 - VUELO
    zt = alto - E_CUBIERTA
    e = E_TUBO
    bm = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0, y0 = (fx - e, fy - e)
            _caja(bm, sx * x0, sx * fx, sy * y0, sy * fy, 0.0, zt, 0.0025, 1)            # patas
    for z1 in (Z_REPISA, zt):
        for sy in (-1, 1):                                                                # frente y espalda
            _caja(bm, -(fx - e), fx - e, sy * (fy - e), sy * fy, z1 - e, z1, 0.0025, 1)
        for sx in (-1, 1):                                                                # costados
            _caja(bm, sx * (fx - e), sx * fx, -(fy - e), fy - e, z1 - e, z1, 0.0025, 1)
    marco = B.objeto(col, f"{prefijo}_Marco", bm, "Depto_Mat_AceroNegro", suave=True)
    bm = bmesh.new()
    B.caja_redondeada(bm, -ancho / 2, ancho / 2, -fondo / 2, fondo / 2, zt, alto, 0.004, 2)
    # la repisa se apoya en los travesaños de frente y espalda y queda entre las patas
    B.caja_redondeada(bm, -(fx - e) + 0.002, fx - e - 0.002, -fy + 0.002, fy - 0.002,
                      Z_REPISA, Z_REPISA + E_REPISA, 0.003, 2)
    madera = B.objeto(col, f"{prefijo}_Madera", bm, "Depto_Mat_MaderaMueble", suave=True)
    return [marco, madera]


# ---------------------------------------------------------------- lámpara de mesa
def lampara_mesa(col, prefijo, alto=0.42, diametro=0.22):
    """Lámpara de mesa: base de disco, vástago, casquillo con ampolleta globo y pantalla domo negra (blanca por
    dentro) sujeta al casquillo con tres varillas."""
    R_BASE, E_BASE = 0.075, 0.020          # supuesto: disco de 15 cm y 2 cm, pesado
    R_VASTAGO = 0.006                      # supuesto: tubo de 12 mm
    Z_CASQ, R_CASQ, H_CASQ = 0.298, 0.017, 0.036   # supuesto: casquillo E27
    R_GLOBO = 0.0275                       # supuesto: ampolleta globo de 55 mm
    Rd = diametro / 2
    Hd = 0.124                             # supuesto: domo algo más alto que media esfera
    z_borde = alto - 0.006 - Hd            # 0,006 del remate superior
    ESP = 0.0015                           # chapa de 1,5 mm
    bm = bmesh.new()
    arco = [(R_BASE - 0.007 + 0.007 * math.cos(math.radians(a)), E_BASE - 0.007 + 0.007 * math.sin(math.radians(a)))
            for a in (0, 30, 60, 90)]
    _torno(bm, [(0.0, 0.0), (R_BASE - 0.0015, 0.0), (R_BASE, 0.0015)] + arco + [(0.0, E_BASE)], 32)
    zc = Z_CASQ + H_CASQ
    _torno(bm, [(0.0, E_BASE), (0.014, E_BASE), (0.014, E_BASE + 0.007), (0.011, E_BASE + 0.010),
                (R_VASTAGO, E_BASE + 0.011), (R_VASTAGO, Z_CASQ - 0.003), (R_CASQ - 0.002, Z_CASQ),
                (R_CASQ, Z_CASQ + 0.003), (R_CASQ, zc - 0.003), (R_CASQ - 0.003, zc), (0.0, zc)], 10)
    B.caja(bm, -0.006, 0.006, -R_BASE + 0.012, -R_BASE + 0.024, E_BASE, E_BASE + 0.005)   # interruptor
    # varillas del casquillo al domo (por dentro)
    r_in = 0.07
    z_in = z_borde + (Hd - ESP) * math.sqrt(1 - (r_in / (Rd - ESP)) ** 2)
    for k in range(3):
        a = 2 * math.pi * k / 3 + math.pi / 2
        u = Vector((math.cos(a), math.sin(a), 0))
        B.tubo(bm, [u * (R_CASQ - 0.002) + Vector((0, 0, zc - 0.004)), u * r_in + Vector((0, 0, z_in + 0.0005))],
               0.0015, seg=6)
    objs = [B.objeto(col, f"{prefijo}_Cuerpo", bm, "Depto_Mat_MetalNegroMate", suave=True)]
    # pantalla: tramos 0 = negro exterior y borde, 1 = interior blanco
    angs = (0, 11, 22, 33, 44, 55, 66, 76)            # la silueta del domo: pasos de 11°
    interior = [(0.0, z_borde + Hd - ESP)] + [((Rd - ESP) * math.cos(math.radians(a)),       # se ve poco: menos anillos
                                                z_borde + (Hd - ESP) * math.sin(math.radians(a))) for a in (60, 30, 0)]
    exterior = [(Rd * math.cos(math.radians(a)), z_borde + Hd * math.sin(math.radians(a))) for a in angs]
    rk = 0.012
    zk = z_borde + Hd * math.sqrt(1 - (rk / Rd) ** 2)
    remate = [(rk, zk), (rk, alto - 0.002), (rk - 0.002, alto), (0.0, alto)]
    perfil = interior + exterior + remate
    indices = [1] * (len(interior) - 1) + [0] * (len(exterior) + len(remate))
    bm = bmesh.new()
    _torno(bm, perfil, 36, indices)
    objs.append(B.objeto(col, f"{prefijo}_Pantalla", bm, None, suave=True, angulo_suave=40,
                         materiales=["Depto_Mat_MetalNegroMate", "Depto_Mat_PantallaInterior"]))
    # ampolleta globo sobre el casquillo
    zg = zc + 0.006 + R_GLOBO * math.sin(math.radians(62))    # el punto de -62° queda 6 mm sobre el casquillo
    globo = [((R_GLOBO * math.cos(math.radians(a))), zg + R_GLOBO * math.sin(math.radians(a)))
             for a in (-62, -40, -15, 10, 35, 60, 80)]
    bm = bmesh.new()
    _torno(bm, [(0.0, zc), (0.0105, zc), (0.0115, zc + 0.003)] + globo + [(0.0, zg + R_GLOBO)], 16)
    objs.append(B.objeto(col, f"{prefijo}_Ampolleta", bm, "Depto_Mat_Bombilla", suave=True, angulo_suave=60))
    return objs


# ---------------------------------------------------------------- espejo de pie
def espejo_pie(col, prefijo, ancho=0.60, alto=1.70, inclinacion=8.0):
    """Espejo de cuerpo entero con marco de acero negro, apoyado en el muro con `inclinacion` grados: el canto de
    atrás de abajo toca el suelo y el de arriba toca el muro en y = +0,125."""
    CARA, FONDO = 0.030, 0.020     # supuesto: marco de tubo de 30 × 20 mm (se lee a la distancia de la pieza)
    REBAJE = 0.005                 # el vidrio queda 5 mm hundido respecto del frente del marco
    E_VIDRIO = 0.004
    Y_MURO = 0.125                 # diseño (docs): espalda en y = +0,125
    bm_m, bm_e = bmesh.new(), bmesh.new()
    perfil = [(i, d) for i, d in _rect_redondeado(0.0, CARA, -FONDO, 0.0, 0.003, 2)]
    _marco_ingleteado(bm_m, Vector((-ancho / 2, 0.0, 0.0)), X, Z, Y, ancho, alto, perfil)
    xi, zi = ancho / 2 - CARA, CARA
    B.caja(bm_m, -xi, xi, -0.006, -0.002, zi, alto - CARA)                  # respaldo de chapa
    yv = -FONDO + REBAJE
    B.caja(bm_e, -xi, xi, yv, yv + E_VIDRIO, zi, alto - CARA)
    rot = Matrix.Rotation(math.radians(-inclinacion), 4, "X")                # la parte de arriba va hacia +Y
    for bm in (bm_m, bm_e):
        B.transformar(bm, rot)
    zmin = min(v.co.z for v in bm_m.verts)
    ymax = max(v.co.y for v in bm_m.verts)
    for bm in (bm_m, bm_e):
        B.transformar(bm, Matrix.Translation((0.0, Y_MURO - ymax, -zmin)))
    return [B.objeto(col, f"{prefijo}_Marco", bm_m, "Depto_Mat_AceroNegro", suave=True),
            B.objeto(col, f"{prefijo}_Espejo", bm_e, "Depto_Mat_Espejo")]
