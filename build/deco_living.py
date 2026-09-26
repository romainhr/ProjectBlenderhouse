"""Piezas del living para la decoración industrial (versión 2): docs/deco-industrial.md, sección «Living».

Cada pieza es `nombre(col, prefijo, **parámetros) -> list[bpy.types.Object]`, en coordenadas locales (metros,
Z arriba, huella centrada en el origen, apoyada en z = 0, frente hacia −Y, espalda hacia +Y), salvo las
excepciones que indica el documento (rack, tv, cuadro, lámpara de arco). Todos los objetos quedan con origen en
(0, 0, 0) y sin rotación. Mallas con bmesh (sin booleanos ni modificadores vivos) y un objeto por material.
Toda la variación (arrugas, abombado) es determinista: semillas fijas por parámetro.

Material nuevo que registra este módulo (no está en depto_geom.MATERIALES):
    Depto_Mat_LanaOcre: lana del cojín de acento, ocre #B8862B (docs: «acento ocre, sólo en cuadros y un cojín»).
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector

import deco_base as B
import depto_geom as G

G.MATERIALES.setdefault("Depto_Mat_LanaOcre", ((0.72, 0.53, 0.17), 0.95, 0.0, 1.0))   # diseño: acento ocre #B8862B

# Topes de triángulos por pieza (docs/deco-industrial.md)
TOPES = dict(sofa=14000, cojin=1500, mesa_centro=4000, rack_tv=2000, tv=600, mesa_lateral=2000,
             lampara_arco=4000, alfombra=300, cuadro=300)


# =====================================================================================================
# Ayudas de modelado propias de este módulo
# =====================================================================================================
def _ondulacion(semilla, amp_larga=0.0012, amp_corta=0.0005, k_larga=(7.0, 14.0), k_corta=(28.0, 45.0)):
    """Función de ruido suave (suma de senos con dirección y fase aleatorias, semilla fija): Vector -> metros."""
    rnd = random.Random(semilla)
    ondas = []
    for amp, (k0, k1) in ((amp_larga, k_larga), (amp_corta, k_corta)):
        for _ in range(3):
            d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
            ondas.append((d * rnd.uniform(k0, k1), rnd.uniform(0, 2 * math.pi), amp / math.sqrt(3)))

    def f(p):
        return sum(a * math.sin(k.dot(p) + fase) for k, fase, a in ondas)
    return f


def _muestras(h, r, angulos, n_medio):
    """Posiciones sobre un eje de semiancho h para la caja blanda: en cada banda de redondeo (radio r) una
    muestra por ángulo (0..45°, reparto uniforme sobre el arco) y n_medio intervalos en el tramo plano."""
    nucleo = h - r
    banda = [nucleo + r * math.tan(math.radians(a)) for a in angulos]
    if nucleo <= 1e-9:
        return [-b for b in reversed(banda)][:-1] + banda
    medio = [-nucleo + 2 * nucleo * k / n_medio for k in range(1, n_medio)]
    return [-b for b in reversed(banda)] + medio + banda


def _caja_blanda(bm, x0, x1, y0, y1, z0, z1, radio, angulos=(0, 22, 38, 45), medios=(4, 4, 2), abombar=None,
                 costura=None, costura_prof=(0.002, 0.0012), ruido=None, deformar=None, suave=True):
    """Caja de cantos redondeados con malla regular de quads (cubo subdividido proyectado sobre la caja
    redondeada). Sirve para tapizados: se puede abombar, marcar costuras y deformar sin perder la forma.

    abombar: {(eje, lado): amplitud} empuja hacia fuera el centro de cada cara con perfil (1-u²)(1-v²).
    costura: función (eje_a, lado_a, eje_b, lado_b) -> bool; las aristas del cubo elegidas llevan un vivo en
             relieve (costura_prof[0]) con un pliegue a cada lado (costura_prof[1]).
    ruido: función (posición, normal) -> desplazamiento a lo largo de la normal.
    deformar: función (posición, normal, (u, v, w)) -> posición final.
    Devuelve los vértices creados."""
    c = Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    h = Vector((abs(x1 - x0) / 2, abs(y1 - y0) / 2, abs(z1 - z0) / 2))
    r = min(radio, min(h))
    ejes = [_muestras(h[a], r, angulos, max(1, medios[a])) for a in range(3)]
    n = [len(e) - 1 for e in ejes]
    nucleo = [h[a] - r for a in range(3)]
    abombar = abombar or {}
    cache = {}

    def es_costura(a, sa, b, sb):
        return bool(costura) and (costura(a, sa, b, sb) or costura(b, sb, a, sa))

    def vert(idx):
        if idx in cache:
            return cache[idx]
        p = Vector([ejes[a][idx[a]] for a in range(3)])
        q = Vector([max(-nucleo[a], min(nucleo[a], p[a])) for a in range(3)])
        d = p - q
        nrm = d.normalized() if d.length > 1e-12 else Vector((0.0, 0.0, 1.0))
        pos = q + nrm * r
        uvw = [p[a] / h[a] if h[a] > 1e-12 else 0.0 for a in range(3)]
        for a in range(3):                                    # abombado de caras
            if abs(nrm[a]) < 1e-9:
                continue
            amp = abombar.get((a, 1 if nrm[a] > 0 else -1), 0.0)
            if amp:
                b, e = [k for k in range(3) if k != a]
                pos[a] += nrm[a] * amp * (1 - uvw[b] ** 2) * (1 - uvw[e] ** 2)
        if costura:                                           # vivo de costura y pliegues a sus lados
            ext = [(a, -1 if idx[a] == 0 else 1) for a in range(3) if idx[a] in (0, n[a])]
            vivo = any(es_costura(*ext[i], *ext[j]) for i in range(len(ext)) for j in range(i + 1, len(ext)))
            if vivo:
                pos += nrm * costura_prof[0]
            else:
                for a in range(3):
                    if idx[a] in (0, n[a]) or idx[a] not in (1, n[a] - 1):
                        continue
                    sa = -1 if idx[a] == 1 else 1
                    if any(es_costura(e, se, a, sa) for e, se in ext):
                        pos -= nrm * costura_prof[1]
                        break
        pos += c
        if ruido:
            pos += nrm * ruido(pos, nrm)
        if deformar:
            pos = deformar(pos, nrm, uvw)
        v = bm.verts.new(pos)
        cache[idx] = v
        return v

    for a in range(3):
        b, e = [k for k in range(3) if k != a]
        for extremo in (0, n[a]):
            for i in range(n[b]):
                for j in range(n[e]):
                    ids = []
                    for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        idx = [0, 0, 0]
                        idx[a], idx[b], idx[e] = extremo, i + di, j + dj
                        ids.append(vert(tuple(idx)))
                    bm.faces.new(ids).smooth = suave
    return list(cache.values())


def _redondear(puntos, radios, pasos=6, cerrado=False):
    """Polilínea con esquinas redondeadas (radio por vértice; 0 = esquina viva). cerrado: lazo."""
    pts = [Vector(p) for p in puntos]
    n = len(pts)
    if not isinstance(radios, (list, tuple)):
        radios = [radios] * n
    out = []
    for i in range(n):
        p = pts[i]
        if not cerrado and i in (0, n - 1):
            out.append(p.copy())
            continue
        a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        d1, d2 = p - a, b - p
        l1, l2 = d1.length, d2.length
        d1.normalize()
        d2.normalize()
        ang = math.acos(max(-1.0, min(1.0, d1.dot(d2))))
        if radios[i] <= 0 or ang < 1e-3:
            out.append(p.copy())
            continue
        t = min(radios[i] * math.tan(ang / 2), l1 * 0.49, l2 * 0.49)
        rr = t / math.tan(ang / 2)
        s = p - d1 * t
        eje = d1.cross(d2).normalized()
        centro = s + eje.cross(d1).normalized() * rr
        for k in range(pasos + 1):
            out.append(centro + Matrix.Rotation(ang * k / pasos, 3, eje) @ (s - centro))
    return out


def _barrido(bm, puntos, seccion, radios=0.0, pasos=6, cerrado=False, tapas=True, suave=True, arriba=None):
    """Barre una sección 2D [(u, v), ...] a lo largo de una polilínea 3D. u va sobre la normal del marco y v
    sobre la binormal (tangente × normal). Marcos por transporte paralelo (sin torsión; en lazos cerrados se
    reparte el desfase), esquinas vivas a inglete y esquinas redondeadas con `radios`. Devuelve los anillos."""
    pts = _redondear(puntos, radios, pasos, cerrado)
    limpios = [pts[0]]
    for p in pts[1:]:
        if (p - limpios[-1]).length > 1e-7:
            limpios.append(p)
    if cerrado and (limpios[0] - limpios[-1]).length < 1e-7:
        limpios.pop()
    pts = limpios
    n = len(pts)

    def dirs(i):
        d1 = (pts[i] - pts[(i - 1) % n]).normalized() if (cerrado or i > 0) else None
        d2 = (pts[(i + 1) % n] - pts[i]).normalized() if (cerrado or i < n - 1) else None
        return d1, d2

    tang, inglete = [], []
    for i in range(n):
        d1, d2 = dirs(i)
        if d1 is None or d2 is None:
            tang.append(d2 if d1 is None else d1)
            inglete.append(None)
            continue
        t = d1 + d2
        t = t.normalized() if t.length > 1e-9 else d2
        tang.append(t)
        m = d2 - d1
        inglete.append((m.normalized(), 1.0 / max(d1.dot(t), 0.2)) if m.length > 1e-9 else None)
    ref = Vector(arriba) if arriba else (Vector((0, 0, 1)) if abs(tang[0].z) < 0.9 else Vector((1, 0, 0)))
    nor = (ref - tang[0] * ref.dot(tang[0])).normalized()
    nors = [nor]
    for i in range(1, n):
        nor = tang[i - 1].rotation_difference(tang[i]) @ nor
        nor = (nor - tang[i] * nor.dot(tang[i])).normalized()
        nors.append(nor)
    if cerrado:
        fin = tang[-1].rotation_difference(tang[0]) @ nors[-1]
        fin = (fin - tang[0] * fin.dot(tang[0])).normalized()
        desfase = math.atan2(nors[0].cross(fin).dot(tang[0]), nors[0].dot(fin))
        nors = [Matrix.Rotation(-desfase * i / n, 3, tang[i]) @ nors[i] for i in range(n)]
    anillos = []
    for i in range(n):
        bi = tang[i].cross(nors[i])
        anillo = []
        for u, v in seccion:
            off = nors[i] * u + bi * v
            if inglete[i]:
                m, k = inglete[i]
                off = off + m * (off.dot(m) * (k - 1.0))
            anillo.append(bm.verts.new(pts[i] + off))
        anillos.append(anillo)
    ns = len(seccion)
    pares = list(zip(anillos[:-1], anillos[1:])) + ([(anillos[-1], anillos[0])] if cerrado else [])
    for a, b in pares:
        for k in range(ns):
            j = (k + 1) % ns
            bm.faces.new((a[k], a[j], b[j], b[k])).smooth = suave
    if tapas and not cerrado:
        bm.faces.new(list(reversed(anillos[0])))
        bm.faces.new(anillos[-1])
    return anillos


def _sec_circulo(r, seg=12):
    return [(r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg)) for k in range(seg)]


def _sec_rect(a, b, rc, pasos=2):
    """Rectángulo a × b (u × v) centrado, con esquinas de radio rc."""
    pts = []
    for cx, cy, a0 in ((a / 2 - rc, b / 2 - rc, 0), (-a / 2 + rc, b / 2 - rc, 90),
                       (-a / 2 + rc, -b / 2 + rc, 180), (a / 2 - rc, -b / 2 + rc, 270)):
        for k in range(pasos + 1):
            t = math.radians(a0 + 90 * k / pasos)
            pts.append((cx + rc * math.cos(t), cy + rc * math.sin(t)))
    return pts


def _cilindro(bm, cx, cy, z0, z1, r, seg=16):
    return B.cilindro(bm, cx, cy, z0, z1, r, seg=seg)


def _disco_canto(bm, cx, cy, z0, z1, radio, r_sup, r_inf, seg=48, pasos_sup=3, pasos_inf=2):
    """Disco macizo (cubierta redonda) con canto superior e inferior redondeados, por torno."""
    perfil = [(0.0, z0), (radio - r_inf, z0)]
    for k in range(1, pasos_inf):
        a = -math.pi / 2 + (math.pi / 2) * k / pasos_inf
        perfil.append((radio - r_inf + r_inf * math.cos(a), z0 + r_inf + r_inf * math.sin(a)))
    perfil += [(radio, z0 + r_inf), (radio, z1 - r_sup)]
    for k in range(1, pasos_sup):
        a = (math.pi / 2) * k / pasos_sup
        perfil.append((radio - r_sup + r_sup * math.cos(a), z1 - r_sup + r_sup * math.sin(a)))
    perfil += [(radio - r_sup, z1), (0.0, z1)]
    anillos = B.torno(bm, perfil, seg=seg)
    if cx or cy:
        B.transformar(bm, Matrix.Translation((cx, cy, 0)), [v for an in anillos for v in an])
    return anillos


# =====================================================================================================
# Sofá
# =====================================================================================================
SOFA = dict(
    cojin_asiento=0.14,      # supuesto: espuma de 12 cm con capa de pluma; asiento a 0,44 (docs)
    alto_brazo=0.60,         # supuesto: brazo recto usual de 0,58 a 0,62
    alto_respaldo=0.66,      # supuesto: estructura del respaldo; los cojines suben a 0,78 (docs)
    esp_respaldo=0.16,       # supuesto: espesor de la estructura del respaldo
    esp_cojin_resp=0.20,     # supuesto: cojín de respaldo de 0,20 abajo, se afina a 0,13 arriba
    radio_tapiz=0.03,        # diseño: canto de brazos y respaldo
    radio_cojin=0.045,       # diseño: canto de cojines
    patin_tubo=0.025,        # diseño: tubo cuadrado de 25 mm
    patin_largo=0.76,        # diseño: largo del patín (0,07 de retiro por delante y por detrás)
)


def sofa(col, prefijo, ancho=1.80, fondo=0.90, alto=0.78, alto_asiento=0.44, brazo=0.15, z_base=0.12,
         n_cojines=3, semilla=11):
    """Sofá de cuero de brazos rectos sobre patines de acero: estructura (brazos, respaldo y plataforma),
    tres cojines de asiento y tres de respaldo blandos con vivos de costura, y dos patines de tubo cuadrado."""
    S = SOFA
    hx, hy = ancho / 2, fondo / 2
    z_deck = alto_asiento - S["cojin_asiento"]
    y_resp = hy - S["esp_respaldo"]                          # cara delantera de la estructura del respaldo
    rt = S["radio_tapiz"]

    # --- estructura: brazos, respaldo envolvente y plataforma de asiento
    bm = bmesh.new()

    def cost_brazo(a, sa, b, sb):                            # vivos en el perímetro de la tapa y del frente
        return (a, sa) in ((2, 1), (1, -1))

    for s in (-1, 1):
        xi, xe = s * (hx - brazo), s * (hx - 0.0035)
        _caja_blanda(bm, min(xi, xe), max(xi, xe), -hy + 0.003, y_resp, z_base, S["alto_brazo"] - 0.004, rt,
                     medios=(1, 6, 4), abombar={(2, 1): 0.004, (0, s): 0.002, (1, -1): 0.003},
                     costura=cost_brazo, ruido=_ruido_tapiz(semilla + 1 + s, contacto=((0, -s), (1, 1), (2, -1))))
    _caja_blanda(bm, -hx, hx, y_resp, hy, z_base, S["alto_respaldo"] - 0.004, rt, medios=(12, 1, 4),
                 abombar={(2, 1): 0.004}, costura=lambda a, sa, b, sb: (a, sa) == (2, 1),
                 ruido=_ruido_tapiz(semilla + 5, contacto=((1, -1), (1, 1), (2, -1), (0, -1), (0, 1))))
    _caja_blanda(bm, -hx + brazo, hx - brazo, -hy + 0.012, y_resp, z_base, z_deck, 0.02, angulos=(0, 25, 45),
                 medios=(4, 2, 1), costura=lambda a, sa, b, sb: {(a, sa), (b, sb)} == {(1, -1), (2, 1)})
    estructura = B.objeto(col, f"{prefijo}_Estructura", bm, "Depto_Mat_Cuero", angulo_suave=60)

    # --- cojines de asiento (abombados) y de respaldo (se afinan hacia arriba y ceden en el centro)
    bm = bmesh.new()
    ranura = (ancho - 2 * brazo) / n_cojines
    holg = 0.002
    asientos = []
    for i in range(n_cojines):
        xa = -hx + brazo + i * ranura + holg
        xb = xa + ranura - 2 * holg
        vs = _caja_blanda(bm, xa + 0.004, xb - 0.004, -hy + 0.004 + 0.008, y_resp - 0.001, z_deck,
                          alto_asiento - 0.013, S["radio_cojin"], medios=(4, 6, 1),
                          abombar={(2, 1): 0.013, (1, -1): 0.008, (0, -1): 0.004, (0, 1): 0.004},
                          costura=lambda a, sa, b, sb: a == 2,
                          ruido=_ruido_tapiz(semilla + 10 + i, contacto=((2, -1), (1, 1), (0, -1), (0, 1)),
                                             amp=0.0016))
        asientos.append(vs)
    e_cr = S["esp_cojin_resp"]
    y_fondo = y_resp - 0.001
    for i in range(n_cojines):
        xa = -hx + brazo + i * ranura + holg
        xb = xa + ranura - 2 * holg
        # apoya sobre el cojín de asiento: la cota más alta del asiento bajo su huella, más 1,5 mm
        bajo = [v.co.z for v in asientos[i] if v.co.y > y_fondo - e_cr - 0.02]
        z_b = max(bajo) + 0.0015
        z_t = alto + 0.0015                                  # la cima cede ~3 mm: queda en `alto`

        def afinar(p, nrm, uvw, z_b=z_b, z_t=z_t, xc=(xa + xb) / 2, hxx=(xb - xa) / 2):
            t = max(0.0, min(1.0, (p.z - z_b) / (z_t - z_b)))
            p.y = y_fondo - (y_fondo - p.y) * (1 - 0.35 * t)             # 0,20 abajo, 0,13 arriba
            u = max(-1.0, min(1.0, (p.x - xc) / hxx))
            p.z -= 0.008 * (1 - u * u) * max(0.0, (t - 0.55) / 0.45) ** 2  # el relleno cede al centro
            return p
        _caja_blanda(bm, xa + 0.004, xb - 0.004, y_fondo - e_cr + 0.016, y_fondo, z_b, z_t, 0.05,
                     medios=(4, 1, 3), abombar={(1, -1): 0.016, (0, -1): 0.004, (0, 1): 0.004},
                     costura=lambda a, sa, b, sb: a == 1, deformar=afinar,
                     ruido=_ruido_tapiz(semilla + 20 + i, contacto=((1, 1), (2, -1), (0, -1), (0, 1)), amp=0.0018))
    cojines = B.objeto(col, f"{prefijo}_Cojines", bm, "Depto_Mat_Cuero", angulo_suave=60)

    # --- patines: lazo rectangular de tubo cuadrado bajo cada brazo, de z = 0 a z_base
    bm = bmesh.new()
    t = S["patin_tubo"]
    ly = S["patin_largo"] / 2
    sec = _sec_rect(t, t, 0.003, pasos=2)
    for s in (-1, 1):
        x = s * (hx - brazo / 2 - 0.005)
        _barrido(bm, [(x, -ly, t / 2), (x, ly, t / 2), (x, ly, z_base - t / 2), (x, -ly, z_base - t / 2)], sec,
                 radios=0.03, pasos=4, cerrado=True)
    patin = B.objeto(col, f"{prefijo}_Patin", bm, "Depto_Mat_AceroNegro")
    return [estructura, cojines, patin]


def _ruido_tapiz(semilla, contacto=(), amp=0.0012):
    """Ruido del tapiz a lo largo de la normal, apagado en las caras de contacto [(eje, lado), ...] para que
    ninguna pieza atraviese a su vecina."""
    f = _ondulacion(semilla, amp_larga=amp, amp_corta=amp * 0.4)

    def r(p, nrm):
        peso = 1.0
        for eje, lado in contacto:
            peso = min(peso, 1.0 - max(0.0, nrm[eje] * lado))
        return f(p) * peso
    return r


# =====================================================================================================
# Cojín
# =====================================================================================================
def cojin(col, prefijo, ancho=0.45, alto=0.45, grosor=0.14, material="Depto_Mat_Lana", inclinacion=0.0,
          semilla=3, divisiones=17):
    """Cojín de dos paños cosidos con vivo: esquinas pellizcadas, bordes que se recogen hacia dentro y
    arrugas suaves que salen de las esquinas. Por defecto yace plano (inclinacion = 0°); con inclinacion
    (grados) se levanta sobre su borde de −Y con la cara de arriba hacia −Y (apoyado en un respaldo en +Y)."""
    vivo = 0.0025                                         # supuesto: medio grosor del vivo cosido
    hx, hy, e = ancho / 2 - 0.7 * vivo, alto / 2 - 0.7 * vivo, grosor / 2
    N = divisiones
    rnd = random.Random(semilla)
    fases = [rnd.uniform(0, 2 * math.pi) for _ in range(16)]
    ruido = _ondulacion(semilla + 100, amp_larga=0.0025, amp_corta=0.0008, k_larga=(6, 10), k_corta=(20, 30))
    recogido = 0.10                                       # diseño: el centro de cada borde se recoge 10 %

    def s_a_u(k):                                         # más densidad cerca del borde
        return math.sin((-1 + 2 * k / N) * math.pi / 2)

    def plano(u, v):
        x = u * hx * (1 - recogido * (1 - v * v) * u * u)
        y = v * hy * (1 - recogido * (1 - u * u) * v * v)
        return x, y

    def espesor(u, v):                                    # relleno lleno al centro, cae rápido junto al vivo
        return e * ((1 - abs(u) ** 4) * (1 - abs(v) ** 4)) ** 0.42

    def arrugas(u, v, lado):
        a = 0.0
        o = 0 if lado > 0 else 8
        for i, (cu, cv) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):   # pliegues que salen de las esquinas
            du, dv = u - cu, v - cv
            d = math.hypot(du, dv)
            a += 0.006 * math.sin(math.atan2(dv, du) * 8 + fases[o + i]) * math.exp(-d / 0.45) * min(1.0, d * 3)
        for i, (w, t) in enumerate(((u, v), (-u, v), (v, u), (-v, u))):       # fruncido a lo largo del vivo
            a += 0.0025 * math.exp(-(1 - w) / 0.10) * math.sin(t * 17 + fases[o + 4 + i]) * (1 - t * t)
        return a

    bm = bmesh.new()
    caras = {}
    for lado in (1, -1):
        g = []
        for j in range(N + 1):
            fila = []
            for i in range(N + 1):
                u, v = s_a_u(i), s_a_u(j)
                x, y = plano(u, v)
                borde = i in (0, N) or j in (0, N)
                z = lado * (vivo if borde else max(vivo, espesor(u, v) + arrugas(u, v, lado)))
                if not borde:
                    z += lado * ruido(Vector((x, y, lado * 0.1))) * min(1.0, espesor(u, v) / (e * 0.3))
                fila.append(bm.verts.new((x, y, z)))
            g.append(fila)
        caras[lado] = g
        for j in range(N):
            for i in range(N):
                bm.faces.new((g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i])).smooth = True
    # vivo: anillo del borde a z = 0 empujado hacia fuera, entre el borde de arriba y el de abajo
    borde_idx = ([(0, i) for i in range(N)] + [(j, N) for j in range(N)] + [(N, i) for i in range(N, 0, -1)]
                 + [(j, 0) for j in range(N, 0, -1)])
    medio = []
    for j, i in borde_idx:
        p = caras[1][j][i].co
        d = Vector((p.x, p.y, 0))
        medio.append(bm.verts.new(Vector((p.x, p.y, 0)) + d.normalized() * vivo))
    m = len(borde_idx)
    for k in range(m):
        k2 = (k + 1) % m
        (ja, ia), (jb, ib) = borde_idx[k], borde_idx[k2]
        arriba_a, arriba_b = caras[1][ja][ia], caras[1][jb][ib]
        abajo_a, abajo_b = caras[-1][ja][ia], caras[-1][jb][ib]
        bm.faces.new((arriba_a, arriba_b, medio[k2], medio[k])).smooth = True
        bm.faces.new((medio[k], medio[k2], abajo_b, abajo_a)).smooth = True
    # apoyo: plano sobre z = 0, o levantado sobre el borde −Y
    rot = Matrix.Rotation(math.radians(inclinacion), 4, "X") if inclinacion else Matrix.Identity(4)
    B.transformar(bm, rot)
    lo = Vector([min(v.co[k] for v in bm.verts) for k in range(3)])
    hi = Vector([max(v.co[k] for v in bm.verts) for k in range(3)])
    B.transformar(bm, Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)))
    return [B.objeto(col, f"{prefijo}_Cojin", bm, material, angulo_suave=70)]


# =====================================================================================================
# Mesa de centro
# =====================================================================================================
def mesa_centro(col, prefijo, diametro=0.70, alto=0.40, cubierta=0.04, varilla=0.012, n_patas=3):
    """Cubierta redonda de roble ahumado con canto redondeado sobre tres patas hairpin de varilla de 12 mm
    (una varilla doblada en U por pata = dos varillas), atornilladas a una platina bajo la cubierta."""
    R = diametro / 2
    z_cub = alto - cubierta
    bm = bmesh.new()
    _disco_canto(bm, 0, 0, z_cub, alto, R, r_sup=0.014, r_inf=0.005, seg=64, pasos_sup=4, pasos_inf=2)
    cub = B.objeto(col, f"{prefijo}_Cubierta", bm, "Depto_Mat_MaderaMueble")

    bm = bmesh.new()
    rv = varilla / 2
    esp_platina = 0.005
    z_pl = z_cub - esp_platina
    r_arriba, r_abajo = R - 0.12, R - 0.085          # diseño: las patas se abren 3,5 cm hacia fuera
    sep_arriba, sep_abajo = 0.045, 0.013               # diseño: medio ancho de la horquilla arriba y abajo
    for k in range(n_patas):
        a = math.radians(90 + 360 * k / n_patas)
        rd, tg = Vector((math.cos(a), math.sin(a), 0)), Vector((-math.sin(a), math.cos(a), 0))

        def P(t, r_, z):
            return rd * r_ + tg * t + Vector((0, 0, z))
        pts = [P(sep_arriba, r_arriba, z_pl), P(sep_arriba, r_arriba, z_pl - 0.03),
               P(sep_abajo, r_abajo, rv), P(-sep_abajo, r_abajo, rv),
               P(-sep_arriba, r_arriba, z_pl - 0.03), P(-sep_arriba, r_arriba, z_pl)]
        _barrido(bm, pts, _sec_circulo(rv, 10), radios=[0, 0.05, 0.013, 0.013, 0.05, 0], pasos=6)
        # platina de 0,12 × 0,05 × 5 mm con cantos matados
        antes = set(bm.verts)
        B.caja_redondeada(bm, -0.06, 0.06, -0.025, 0.025, z_pl, z_cub, 0.0015, segmentos=1)
        verts = [v for v in bm.verts if v not in antes]
        m = Matrix.Translation(rd * r_arriba) @ Matrix.Rotation(a - math.pi / 2, 4, "Z")
        B.transformar(bm, m, verts)
    patas = B.objeto(col, f"{prefijo}_Patas", bm, "Depto_Mat_AceroNegro", suave=True)
    return [cub, patas]


# =====================================================================================================
# Rack de TV
# =====================================================================================================
RACK = dict(
    perfil=0.020, perfil_esp=0.003,    # diseño: ángulo de acero de 20 × 20 × 3 mm en el contorno del frente
    tablero=0.017,                     # supuesto: tablero de roble de 17 mm (20 del perfil menos 3)
    fondo_esp=0.012,                   # supuesto: trasera de 12 mm
    luz=0.003, buna=0.006,             # diseño: luz de 3 mm al marco y buña de sombra de 6 mm entre puertas
    puerta_esp=0.019,
    tirador=(0.14, 0.022, 0.012),      # diseño: tirador embutido (ancho, alto, profundidad)
)


def _puerta_embutida(bm, x0, x1, z0, z1, yf, yb, tir, chaflan=0.0012):
    """Puerta maciza con un bolsillo para el tirador (cerca del canto superior, centrado) y cantos matados.
    Devuelve el rectángulo del bolsillo (x0, x1, z0, z1, profundidad)."""
    tw, th, tp = tir
    xc = (x0 + x1) / 2
    px0, px1 = xc - tw / 2, xc + tw / 2
    pz1 = z1 - 0.028
    pz0 = pz1 - th

    def rect(a0, a1, b0, b1, y):
        return [bm.verts.new(c) for c in ((a0, y, b0), (a1, y, b0), (a1, y, b1), (a0, y, b1))]
    of, ob = rect(x0, x1, z0, z1, yf), rect(x0, x1, z0, z1, yb)
    pf, pb = rect(px0, px1, pz0, pz1, yf), rect(px0, px1, pz0, pz1, yf + tp)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((of[i], of[j], pf[j], pf[i]))          # frente, alrededor del bolsillo
        bm.faces.new((pf[i], pf[j], pb[j], pb[i]))          # paredes del bolsillo
        bm.faces.new((of[i], ob[i], ob[j], of[j]))          # cantos
    bm.faces.new(pb)
    bm.faces.new(list(reversed(ob)))
    aristas = [e for e in bm.edges if all(v in of + ob for v in e.verts)]
    bmesh.ops.bevel(bm, geom=aristas, offset=chaflan, offset_type="OFFSET", segments=2, profile=0.5,
                    affect="EDGES", clamp_overlap=True)
    return px0, px1, pz0, pz1, tp


def _copa_tirador(bm, x0, x1, z0, z1, yf, prof, pared=0.0015, fondo=0.002, holgura=0.0002):
    """Copa de acero que llena el bolsillo del tirador: aro al ras del frente y cavidad interior."""
    x0, x1, z0, z1 = x0 + holgura, x1 - holgura, z0 + holgura, z1 - holgura

    def rect(a0, a1, b0, b1, y):
        return [bm.verts.new(c) for c in ((a0, y, b0), (a1, y, b0), (a1, y, b1), (a0, y, b1))]
    of = rect(x0, x1, z0, z1, yf)
    ob = rect(x0, x1, z0, z1, yf + prof - holgura)
    inf = rect(x0 + pared, x1 - pared, z0 + pared, z1 - pared, yf)
    inb = rect(x0 + pared, x1 - pared, z0 + pared, z1 - pared, yf + prof - fondo)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((of[i], of[j], inf[j], inf[i]))
        bm.faces.new((inf[i], inf[j], inb[j], inb[i]))
        bm.faces.new((of[i], ob[i], ob[j], of[j]))
    bm.faces.new(inb)
    bm.faces.new(list(reversed(ob)))


def _prisma_y(bm, poligono, y0, y1):
    """Prisma recto a lo largo de Y con sección `poligono` [(x, z), ...] (puede ser cóncava, p. ej. una L)."""
    a = [bm.verts.new((x, y0, z)) for x, z in poligono]
    b = [bm.verts.new((x, y1, z)) for x, z in poligono]
    n = len(poligono)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)


def rack_tv(col, prefijo, ancho=1.60, fondo=0.35, alto=0.30):
    """Mueble mural flotante de roble ahumado: caja de tableros de 17 mm encajonada en una jaula de ángulo de
    acero de 20 × 20 × 3 mm en sus doce cantos (marcos a inglete en el frente y la espalda y cuatro largueros),
    dos puertas abatibles a ras con luz perimetral, buña de sombra central con tapajunta de acero y tirador
    embutido de acero. De z = 0 a alto, espalda en y = +fondo/2 (la fase 4 lo cuelga)."""
    K = RACK
    hx, hy = ancho / 2, fondo / 2
    p, pe, tb = K["perfil"], K["perfil_esp"], K["tablero"]
    yf, yb = -hy, hy                                         # planos del frente y de la espalda (caras del perfil)
    bm = bmesh.new()
    xo = hx - pe                                             # caras exteriores del roble (bajo el perfil)
    ya, yz = yf + pe, yb - pe                                # el roble va entre las alas de los dos marcos
    B.caja(bm, -xo, xo, ya, yz, pe, pe + tb)                                       # piso
    B.caja(bm, -xo, xo, ya, yz, alto - pe - tb, alto - pe)                         # techo
    for s in (-1, 1):
        B.caja(bm, s * xo, s * (xo - tb), ya, yz, pe + tb, alto - pe - tb)        # costados
    xi, zi0, zi1 = hx - p, p, alto - p                       # vano interior (= borde interior del perfil)
    yt = yb - K["fondo_esp"]
    B.caja(bm, -xi, xi, yt, yb, zi0, zi1)                                          # trasera (dentro del marco)
    luz, buna, pesp = K["luz"], K["buna"], K["puerta_esp"]
    ypf = yf + 0.001                                         # frente de las puertas: 1 mm detrás del perfil
    y_div = ypf + pesp + 0.005                               # divisor: 2 mm detrás de las puertas (+ tapajunta)
    B.caja(bm, -tb / 2, tb / 2, y_div, yt, zi0, zi1)                               # divisor central
    zm = (zi0 + zi1) / 2
    for s in (-1, 1):                                                              # repisas interiores
        B.caja(bm, s * tb / 2, s * xi, -0.02, yt, zm - tb / 2, zm + tb / 2)
    # puertas abatibles (bisagra abajo), tirador junto al canto superior
    bolsillos = []
    for s in (-1, 1):
        xa, xb = sorted((s * (xi - luz), s * buna / 2))
        bolsillos.append(_puerta_embutida(bm, xa, xb, zi0 + luz, zi1 - luz, ypf, ypf + pesp, K["tirador"]))
    madera = B.objeto(col, f"{prefijo}_Cuerpo", bm, "Depto_Mat_MaderaMueble")

    bm = bmesh.new()
    # marcos de frente y espalda: sección en L (u hacia dentro del contorno, v hacia −Y), a inglete; el ala
    # frontal queda en el plano del frente (o de la espalda) y el ala lateral sobre las caras exteriores
    contorno = [(-hx, 0.0), (hx, 0.0), (hx, alto), (-hx, alto)]
    l_frente = [(0.0, 0.0), (p, 0.0), (p, -pe), (pe, -pe), (pe, -p), (0.0, -p)]
    _barrido(bm, [(x, yf, z) for x, z in contorno], l_frente, cerrado=True, suave=False)
    _barrido(bm, [(x, yb, z) for x, z in contorno], [(u, -v) for u, v in l_frente], cerrado=True, suave=False)
    # cuatro largueros en los cantos paralelos a Y, entre las alas laterales de los dos marcos
    for sx in (-1, 1):
        for sz in (0, 1):
            zc = alto if sz else 0.0
            dz = -1 if sz else 1                             # hacia dentro en z
            L = [(0.0, 0.0), (p, 0.0), (p, pe), (pe, pe), (pe, p), (0.0, p)]   # (hacia dentro en x, en z)
            poli = [(sx * (hx - a_), zc + dz * b_) for a_, b_ in L]
            _prisma_y(bm, poli, yf + p, yb - p)
    # tapajunta de la buña: pletina negra al frente del divisor, se ve por la luz entre puertas
    B.caja(bm, -tb / 2, tb / 2, y_div - 0.003, y_div, zi0, zi1)
    for x0, x1, z0, z1, tp in bolsillos:
        _copa_tirador(bm, x0, x1, z0, z1, ypf, tp)
    acero = B.objeto(col, f"{prefijo}_Acero", bm, "Depto_Mat_AceroNegro")
    return [madera, acero]


# =====================================================================================================
# Televisor
# =====================================================================================================
def tv(col, prefijo, ancho=1.23, alto=0.71, fondo=0.03):
    """Televisor de 55": panel delgado con marco fino, vidrio negro, caja trasera y soporte mural de perfil
    bajo. Espalda (soporte) en y = 0, pantalla hacia −Y, canto inferior en z = 0."""
    hx = ancho / 2
    y_vid, y_pan, y_caja, y_riel = -fondo, -fondo + 0.0005, -fondo + 0.0085, -fondo + 0.0185
    bm = bmesh.new()
    B.caja_redondeada(bm, -hx, hx, y_pan, y_caja, 0.0, alto, 0.002, segmentos=2)                # panel
    B.caja_redondeada(bm, -0.44, 0.44, y_caja, y_riel, 0.10, alto - 0.17, 0.004, segmentos=2)   # electrónica
    cuerpo = B.objeto(col, f"{prefijo}_Cuerpo", bm, "Depto_Mat_MetalNegroMate", suave=True)
    bm = bmesh.new()
    marco, marco_inf = 0.006, 0.011                           # supuesto: marco fino, algo más alto abajo
    B.caja(bm, -hx + marco, hx - marco, y_vid, y_pan, marco_inf, alto - marco)
    pantalla = B.objeto(col, f"{prefijo}_Pantalla", bm, "Depto_Mat_VidrioNegro")
    bm = bmesh.new()
    for s in (-1, 1):                                         # rieles verticales atornillados al televisor
        B.caja(bm, s * 0.20 - 0.02, s * 0.20 + 0.02, y_riel, -0.004, 0.14, alto - 0.21)
    B.caja(bm, -0.26, 0.26, -0.004, 0.0, 0.22, alto - 0.29)   # placa mural
    soporte = B.objeto(col, f"{prefijo}_Soporte", bm, "Depto_Mat_AceroNegro")
    return [cuerpo, pantalla, soporte]


# =====================================================================================================
# Mesa lateral
# =====================================================================================================
def mesa_lateral(col, prefijo, diametro=0.40, alto=0.52, cubierta=0.022, tubo=0.016):
    """Mesa lateral en C: marco de tubo de acero de 16 mm en un solo lazo (U en el piso, dos postes atrás y U
    bajo la cubierta; la C abre hacia −Y para meterse bajo el sofá) y cubierta redonda de roble."""
    R = diametro / 2
    rt = tubo / 2
    bm = bmesh.new()
    _disco_canto(bm, 0, 0, alto - cubierta, alto, R, r_sup=0.006, r_inf=0.004, seg=48, pasos_sup=3, pasos_inf=2)
    cub = B.objeto(col, f"{prefijo}_Cubierta", bm, "Depto_Mat_MaderaMueble")
    a, yp, yfb, yft = 0.11, 0.14, -0.16, -0.12               # diseño: medio ancho, postes, frentes abajo y arriba
    zb, zt = rt, alto - cubierta - rt
    pts = [(-a, yfb, zb), (-a, yp, zb), (-a, yp, zt), (-a, yft, zt),
           (a, yft, zt), (a, yp, zt), (a, yp, zb), (a, yfb, zb)]
    bm = bmesh.new()
    _barrido(bm, pts, _sec_circulo(rt, 10), radios=0.035, pasos=5, cerrado=True)
    marco = B.objeto(col, f"{prefijo}_Marco", bm, "Depto_Mat_AceroNegro")
    return [cub, marco]


# =====================================================================================================
# Lámpara de arco
# =====================================================================================================
def lampara_arco(col, prefijo, alto=2.00, avance=1.50, tubo=0.025, pantalla=0.36):
    """Lámpara de pie de arco: base de concreto de 0,32 × 0,32 × 0,06 centrada en el origen, tubo de acero de
    Ø 25 mm que sube recto, se curva (arco circular y luego elíptico) hasta alto y baja vertical a y = −avance,
    donde cuelga una pantalla domo negra por fuera y blanca por dentro con portalámparas y ampolleta."""
    rt = tubo / 2
    objs = []
    # base
    bm = bmesh.new()
    _caja_blanda(bm, -0.16, 0.16, -0.16, 0.16, 0.0, 0.06, 0.006, angulos=(0, 25, 45), medios=(2, 2, 1))
    objs.append(B.objeto(col, f"{prefijo}_Base", bm, "Depto_Mat_Concreto"))
    # tubo: recto, cuarto de círculo (a1) hasta la cima y cuarto de elipse (a2, b2) que termina vertical
    z_col = 0.09
    a2, b2 = 0.55, 0.30                                      # diseño: remate más cerrado sobre la pantalla
    a1 = avance - a2
    h1 = alto - rt - a1
    pts = [Vector((0, 0, z_col))]
    for k in range(0, 17):
        t = math.radians(90 * k / 16)
        pts.append(Vector((0, -a1 + a1 * math.cos(t), h1 + a1 * math.sin(t))))
    z_fin = h1 + a1 - b2
    for k in range(1, 15):
        t = math.radians(90 * k / 14)
        pts.append(Vector((0, -a1 - a2 * math.sin(t), z_fin + b2 * math.cos(t))))
    bm = bmesh.new()
    _barrido(bm, pts, _sec_circulo(rt, 14))
    _cilindro(bm, 0, 0, 0.06, z_col, 0.02, seg=20)          # casquillo sobre la base
    # pantalla: casquillo, domo y portalámparas
    yc = -avance
    z_top = z_fin - 0.05
    _cilindro(bm, 0, yc, z_top, z_fin, 0.02, seg=20)
    objs.append(B.objeto(col, f"{prefijo}_Tubo", bm, "Depto_Mat_AceroNegro", suave=True))

    bm = bmesh.new()
    Rp, Hp, esp, r0 = pantalla / 2, 0.17, 0.0015, 0.025
    ext = [(0.0, z_top), (r0, z_top)]
    for k in range(1, 11):
        f = math.radians(90 * k / 10)
        ext.append((r0 + (Rp - r0) * math.sin(f), z_top - Hp * (1 - math.cos(f))))
    ext.append((Rp, z_top - Hp - 0.004))                     # faldón corto del borde
    intr = [(Rp - esp, z_top - Hp - 0.004)]
    for k in range(10, 0, -1):
        f = math.radians(90 * k / 10)
        intr.append((r0 + (Rp - esp - r0) * math.sin(f), z_top - esp - (Hp - esp) * (1 - math.cos(f))))
    intr += [(r0, z_top - esp), (0.0, z_top - esp)]
    anillos = B.torno(bm, ext + intr, seg=36, cerrado=True)
    B.transformar(bm, Matrix.Translation((0, yc, 0)))
    interiores = {v for an in anillos[len(ext):] for v in an}
    for f in bm.faces:
        f.material_index = 1 if all(v in interiores for v in f.verts) else 0
    objs.append(B.objeto(col, f"{prefijo}_Pantalla", bm, None,
                         materiales=["Depto_Mat_MetalNegroMate", "Depto_Mat_PantallaInterior"]))
    bm = bmesh.new()
    _cilindro(bm, 0, yc, z_top - esp - 0.045, z_top - esp, 0.016, seg=16)            # portalámparas
    objs.append(B.objeto(col, f"{prefijo}_Portalamparas", bm, "Depto_Mat_MetalNegroMate", suave=True))
    bm = bmesh.new()
    rb, rn = 0.04, 0.012                                      # supuesto: ampolleta globo G80
    z_n = z_top - esp - 0.045
    zc = z_n - 0.008 - math.sqrt(rb * rb - rn * rn)
    perfil = [(0.0, z_n), (rn, z_n), (rn, z_n - 0.008)]
    a0 = math.asin(rn / rb)
    for k in range(1, 10):
        a = a0 + (math.pi - a0) * k / 9
        perfil.append((rb * math.sin(a) if k < 9 else 0.0, zc + rb * math.cos(a)))
    B.torno(bm, perfil, seg=20)
    B.transformar(bm, Matrix.Translation((0, yc, 0)))
    objs.append(B.objeto(col, f"{prefijo}_Ampolleta", bm, "Depto_Mat_Bombilla", suave=True))
    return objs


# =====================================================================================================
# Alfombra
# =====================================================================================================
def alfombra(col, prefijo, ancho=2.00, largo=1.40, alto=0.008):
    """Alfombra de yute: losa delgada con los cantos en media caña."""
    bm = bmesh.new()
    _caja_blanda(bm, -ancho / 2, ancho / 2, -largo / 2, largo / 2, 0.0, alto, alto / 2, angulos=(0, 25, 45),
                 medios=(1, 1, 1))
    return [B.objeto(col, f"{prefijo}_Alfombra", bm, "Depto_Mat_Alfombra", angulo_suave=60)]


# =====================================================================================================
# Cuadro
# =====================================================================================================
def cuadro(col, prefijo, arte=1, ancho=0.50, alto=0.70, marco=0.020, fondo=0.025):
    """Lámina enmarcada: marco negro de 0,020 × 0,025 con rebaje y lámina con UV 0-1 propia (la ventana visible
    ocupa todo el rango 0-1). Espalda en y = 0, frente hacia −Y, base del marco en z = 0."""
    hx = ancho / 2 + marco
    H = alto + 2 * marco
    rebaje, cara_lamina = 0.005, 0.013                       # supuesto: la lámina entra 5 mm bajo el marco
    bm = bmesh.new()
    # sección (u hacia dentro, v hacia el frente = −Y), camino en el contorno exterior de la espalda (y = 0)
    sec = [(0.0, 0.0), (0.0, fondo), (marco, fondo), (marco, cara_lamina), (marco - rebaje, cara_lamina),
           (marco - rebaje, 0.0)]
    _barrido(bm, [(-hx, 0.0, 0.0), (hx, 0.0, 0.0), (hx, 0.0, H), (-hx, 0.0, H)], sec, cerrado=True, suave=False)
    m = B.objeto(col, f"{prefijo}_Marco", bm, "Depto_Mat_MetalNegroMate")
    bm = bmesh.new()
    x0, x1 = -ancho / 2 - rebaje + 0.0003, ancho / 2 + rebaje - 0.0003
    z0, z1 = marco - rebaje + 0.0003, marco + alto + rebaje - 0.0003
    B.caja(bm, x0, x1, -cara_lamina, -cara_lamina + 0.003, z0, z1)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for lp in f.loops:
            c = lp.vert.co
            lp[uv].uv = ((c.x + ancho / 2) / ancho, (c.z - marco) / alto)
    lam = B.objeto(col, f"{prefijo}_Lamina", bm, f"Depto_Mat_Arte{int(arte)}", uv="propia")
    return [m, lam]
