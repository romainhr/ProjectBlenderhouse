"""Textiles del bloque 09: alfombras (bereber, kilim, camino y pisos de baño) y cortinas de lino con su barra negra.

Contrato de las piezas (docs/deco-industrial.md): coordenadas locales en metros, apoyo en z = 0, frente hacia −Y y
espalda hacia +Y. Las alfombras se centran en el origen, con el ancho a lo largo de X (la U de su textura) y el largo
a lo largo de Y; las cortinas tienen la cara del muro en y = 0 (espalda) y cuelgan hacia −Y.

Alfombras: losa sin cara inferior (no se ve) con el canto suave en cuarto de círculo (espesor de 1 a 1,5 cm), un
anillo plano de 1,5 cm junto al canto para que el sombreado suave del canto no se extienda por toda la cara superior,
esquinas vivas o redondeadas y flecos opcionales en los extremos de la urdimbre (±X): tiras planas de 2 triángulos
apoyadas en el piso, con largo y ángulo sorteados. UV: en metros (textura que se repite, centrada en la alfombra) o
0-1 (alfombra entera, el kilim).

Cortinas (encargo del bloque 09): paños de lino abiertos a los lados, con pliegues de onda de sección senoidal
(una onda cada 5 a 6 cm cuando el paño está recogido), un poco más hondos y abiertos abajo, colgados de anillas en una
barra negra con soportes al muro y terminales. Todo low-poly: 6 columnas por onda y 4 hileras.

Materiales nuevos que registra este módulo (depto_geom.MATERIALES.setdefault); la textura de cada uno la asigna
build/deco_paleta.py en la fase 5.
"""
import math
import random

import bmesh
from mathutils import Vector

import deco_base as B
import depto_geom as G

BEREBER = "Depto_Mat_AlfombraBereber"
KILIM = "Depto_Mat_AlfombraKilim"
CAMINO = "Depto_Mat_AlfombraCamino"
PISO_BANO = "Depto_Mat_PisoBanoAlgodon"
FLECO = "Depto_Mat_Fleco"
LINO = "Depto_Mat_Lino"
METAL = "Depto_Mat_MetalNegroMate"
G.MATERIALES.setdefault(BEREBER, ((0.88, 0.85, 0.79), 0.97, 0.0, 1.0))    # textura bereber (lana cruda y carbón)
G.MATERIALES.setdefault(KILIM, ((0.64, 0.59, 0.53), 0.90, 0.0, 1.0))      # textura kilim
G.MATERIALES.setdefault(CAMINO, ((0.34, 0.32, 0.29), 0.92, 0.0, 1.0))     # textura camino (espiga carbón y topo)
G.MATERIALES.setdefault(PISO_BANO, ((0.88, 0.85, 0.81), 0.95, 0.0, 1.0))  # textura algodon
G.MATERIALES.setdefault(FLECO, ((0.87, 0.84, 0.78), 0.95, 0.0, 1.0))      # hilo de urdimbre crudo (normal de algodon)
G.MATERIALES.setdefault(LINO, ((0.84, 0.81, 0.75), 0.90, 0.0, 1.0))       # lino natural lavado (#D6CFC0; relieve
                                                                          # rough_linen de Poly Haven)


# ---------------------------------------------------------------- alfombras
def _contorno(hx, hy, rc, pasos):
    """Rectángulo de semiejes hx, hy con esquinas de radio rc (0: vivas), antihorario desde la esquina (+, −)."""
    if rc <= 1e-6:
        return [Vector((hx, -hy)), Vector((hx, hy)), Vector((-hx, hy)), Vector((-hx, -hy))]
    pts = []
    for cx, cy, a0 in ((hx - rc, -hy + rc, -90), (hx - rc, hy - rc, 0), (-hx + rc, hy - rc, 90),
                       (-hx + rc, -hy + rc, 180)):
        for k in range(pasos + 1):
            a = math.radians(a0 + 90 * k / pasos)
            pts.append(Vector((cx + rc * math.cos(a), cy + rc * math.sin(a))))
    return pts


def alfombra(col, prefijo, ancho, largo, alto, material, canto=None, esquina=0.0, uv="metros", tam_uv=None,
             flecos=None, semilla=0):
    """Alfombra centrada en el origen (ancho según X, largo según Y) de espesor `alto`.

    canto: radio del canto suave (por defecto 0,8 · alto); esquina: radio de las esquinas en planta; uv: "metros"
    (U, V en metros desde la esquina (−X, −Y), para una textura que se repite y cuya escala pone la fase 5) o "01"
    (alfombra entera, UV 0-1); tam_uv: con "metros", tamaño (m) de una repetición, para centrar el dibujo;
    flecos: dict(largo, ancho, paso, material) para los extremos ±X. Devuelve [alfombra, flecos?]."""
    rng = random.Random(semilla)
    r = canto if canto is not None else 0.8 * alto
    hx, hy = ancho / 2, largo / 2
    pasos_esq = 3 if esquina > 0 else 0
    # perfil del canto (retranqueo desde el contorno, z): cuarto de círculo de radio r que termina en el plano de
    # arriba, más un anillo plano de 1,5 cm; abajo arranca a 0,3 mm del piso (no hay cara inferior)
    perfil = ([(0.0, 0.0003)] + ([(0.0, alto - r)] if alto - r > 0.0035 else [])
              + [(r - r * math.cos(math.radians(a)), alto - r + r * math.sin(math.radians(a))) for a in (30, 60, 90)]
              + [(r + 0.015, alto)])
    bm = bmesh.new()
    capa = bm.loops.layers.uv.verify()
    anillos = []
    for d, z in perfil:
        anillos.append([bm.verts.new((p.x, p.y, z)) for p in _contorno(hx - d, hy - d, max(esquina - d, 0.0), pasos_esq)])
    n = len(anillos[0])
    caras = []
    for a, b in zip(anillos[:-1], anillos[1:]):
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((a[i], a[j], b[j], b[i]))
            f.smooth = True
            caras.append(f)
    tapa = bm.faces.new(anillos[-1])
    tapa.smooth = True
    caras.append(tapa)
    if tam_uv:                                             # dibujo centrado: la esquina cae en medio período
        u0 = (math.ceil(ancho / tam_uv[0]) * tam_uv[0] - ancho) / 2
        v0 = (math.ceil(largo / tam_uv[1]) * tam_uv[1] - largo) / 2
    else:
        u0 = v0 = 0.0
    for f in caras:
        for lp in f.loops:
            c = lp.vert.co
            if uv == "01":
                lp[capa].uv = ((c.x + hx) / ancho, (c.y + hy) / largo)
            else:
                lp[capa].uv = (c.x + hx + u0, c.y + hy + v0)
    objs = [B.objeto(col, f"{prefijo}_Alfombra", bm, material, angulo_suave=50, uv="propia")]
    if flecos:
        objs.append(_flecos(col, prefijo, hx, hy, alto, flecos, rng))
    return objs


def _flecos(col, prefijo, hx, hy, alto, f, rng):
    """Flecos en los extremos ±X: una tira plana por grupo de hilos, desde 6 mm bajo el canto hasta su largo
    (± 20 %), con un ángulo de ±8° y apoyada a 1,5-2,5 mm del piso (debajo de la hoja de cualquier puerta)."""
    bm = bmesh.new()
    capa = bm.loops.layers.uv.verify()
    n = max(2, int(round(2 * hy / f["paso"])))
    for lado in (-1, 1):
        for k in range(n):
            y = -hy + (k + 0.5) * 2 * hy / n + rng.uniform(-0.2, 0.2) * f["paso"]
            largo = f["largo"] * rng.uniform(0.8, 1.2)
            ang = math.radians(rng.uniform(-8, 8))
            x0 = lado * (hx - 0.006)
            dx, dy = lado * math.cos(ang), math.sin(ang)
            w = f["ancho"] * rng.uniform(0.85, 1.15) / 2
            z0, z1 = 0.0025, 0.0015 + 0.0005 * rng.random()
            px, py = -dy * w, dx * w                         # perpendicular en planta
            vs = [bm.verts.new((x0 - px, y - py, z0)), bm.verts.new((x0 + px, y + py, z0)),
                  bm.verts.new((x0 + dx * largo + px * 0.8, y + dy * largo + py * 0.8, z1)),
                  bm.verts.new((x0 + dx * largo - px * 0.8, y + dy * largo - py * 0.8, z1))]
            cara = bm.faces.new(vs if lado > 0 else list(reversed(vs)))
            for lp, uvv in zip(cara.loops, ((0.0, 0.0), (0.012, 0.0), (0.012, largo), (0.0, largo))):
                lp[capa].uv = uvv
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for cara in bm.faces:                                  # todas hacia arriba (tiras sobre el piso)
        if cara.normal.z < 0:
            cara.normal_flip()
    return B.objeto(col, f"{prefijo}_Flecos", bm, f.get("material", FLECO), recalc=False, uv="propia")


# ---------------------------------------------------------------- cortinas
def _paño(bm, capa, x0, x1, y_eje, z_top, z_hem, ondas, fondo, lado, rng, cols_onda=6):
    """Un paño recogido entre x0 y x1 (m, a lo largo del muro): sección senoidal alrededor de y_eje con `ondas`
    ondas y hondura `fondo`; abajo se abre un 7 % hacia el vano (lado = +1: el vano queda hacia +X; −1: hacia −X) y la
    onda se hace 15 % más honda, con hondura y fase propias por onda (los pliegues no son perfectos). La cara de
    adelante mira al cuarto (−Y). Devuelve los puntos de cuelgue (x, y) de las anillas: donde la tela cruza la barra."""
    ncol = ondas * cols_onda
    filas = [(z_top, 0.0), (z_top - 0.16, 0.10), (0.5 * (z_top + z_hem), 0.55), (z_hem, 1.0)]
    fases = [rng.uniform(-0.2, 0.2) for _ in range(ondas)]
    amps = [rng.uniform(0.9, 1.1) for _ in range(ondas)]
    ancho = x1 - x0
    grilla = []
    for z, t in filas:
        abre = 1 + 0.07 * t
        fila = []
        for i in range(ncol + 1):
            s = i / ncol
            k = min(int(s * ondas), ondas - 1)
            ang = 2 * math.pi * s * ondas + (2 * math.pi * fases[k] * t if 0 < i < ncol else 0.0)
            hond = fondo * (1 + 0.15 * t) * (1 + (amps[k] - 1) * (0.4 + 0.6 * t))
            xa = x0 + s * ancho
            xa = x0 + (xa - x0) * abre if lado > 0 else x1 - (x1 - xa) * abre
            fila.append(bm.verts.new((xa, y_eje - 0.5 * hond * math.sin(ang), z)))
        grilla.append(fila)
    uvs = {}
    for fila in grilla:                                    # U: largo de tela (arco); V: altura (m)
        acc = 0.0
        for i, v in enumerate(fila):
            if i:
                acc += (v.co - fila[i - 1].co).length
            uvs[v] = (acc, v.co.z)
    for a, b in zip(grilla[:-1], grilla[1:]):
        for i in range(ncol):
            f = bm.faces.new((a[i], b[i], b[i + 1], a[i + 1]))
            f.smooth = True
            for lp in f.loops:
                lp[capa].uv = uvs[lp.vert]
    return [(x0 + ancho * k / ondas, y_eje) for k in range(ondas + 1)]


def cortinas(col, prefijo, largo_barra, paneles, z_barra=2.26, sep_muro=0.07, r_barra=0.0125, z_hem=0.012,
             ondas=5, fondo=0.09, soportes=None, terminales=True, semilla=3):
    """Barra de largo `largo_barra` centrada en x = 0, a z_barra y a sep_muro del muro (y = 0), con soportes
    (lista de x; por defecto uno a 0,12 m de cada extremo) y terminales o tapas; `paneles`: [(x0, x1, lado)] con el
    tramo recogido de cada paño (lado: −1 si el vano queda hacia −X, +1 hacia +X). Devuelve [tela, barra]."""
    rng = random.Random(semilla)
    y_eje = -sep_muro
    bm = bmesh.new()
    capa = bm.loops.layers.uv.verify()
    cuelgues = []
    z_top = z_barra - r_barra - 0.028                     # anilla (Ø int. 3,4 cm) y gancho de 1 cm
    for x0, x1, lado in paneles:
        cuelgues += _paño(bm, capa, x0, x1, y_eje, z_top, z_hem, ondas, fondo, lado, rng)
    tela = B.objeto(col, f"{prefijo}_Tela", bm, LINO, angulo_suave=80, recalc=False, uv="propia")
    # barra, anillas, soportes y terminales (metal negro mate)
    bm = bmesh.new()
    hx = largo_barra / 2
    B.tubo(bm, [(-hx, y_eje, z_barra), (hx, y_eje, z_barra)], r_barra, seg=12)
    for s in (-1, 1):
        if terminales:                                     # terminal: cuello y esfera achatada
            B.tubo(bm, [(s * hx, y_eje, z_barra), (s * (hx + 0.012), y_eje, z_barra)], r_barra * 0.7, seg=8)
            anillos = B.torno(bm, [(0.0, -0.022), (0.017, -0.015), (0.022, 0.0), (0.015, 0.015), (0.0, 0.021)],
                              seg=8)
            for v in (v for an in anillos for v in an):  # eje del torno (Z) a lo largo de la barra
                v.co = Vector((s * (hx + 0.034 + v.co.z), y_eje + v.co.y, z_barra + v.co.x))
        else:                                              # tapa (barra de muro a muro)
            B.tubo(bm, [(s * hx, y_eje, z_barra), (s * (hx + 0.004), y_eje, z_barra)], r_barra + 0.002, seg=12)
    for x, y in cuelgues:                                  # anillas: toro de 6 × 3 alrededor de la barra
        R, rr = r_barra + 0.0045, 0.0022
        anillos = []
        for i in range(6):
            a = 2 * math.pi * i / 6
            anillos.append([bm.verts.new((x + rr * math.cos(2 * math.pi * k / 3), y + (R + rr * math.sin(2 * math.pi * k / 3)) * math.cos(a),
                                          z_barra + (R + rr * math.sin(2 * math.pi * k / 3)) * math.sin(a)))
                            for k in range(3)])
        for i in range(6):
            a, b = anillos[i], anillos[(i + 1) % 6]
            for k in range(3):
                bm.faces.new((a[k], a[(k + 1) % 3], b[(k + 1) % 3], b[k])).smooth = True
    xs = soportes if soportes is not None else (-hx + 0.12, hx - 0.12)
    for x in xs:                                           # soporte: roseta al muro, brazo y horquilla bajo la barra
        abajo, arriba = B.cilindro(bm, 0.0, 0.0, 0.0, 0.006, 0.022, seg=8)
        for v in abajo + arriba:                           # eje del cilindro (Z) hacia el cuarto (−Y)
            v.co = Vector((x + v.co.x, -v.co.z, z_barra + 0.004 + v.co.y))
        B.tubo(bm, [(x, -0.006, z_barra + 0.004), (x, y_eje, z_barra + 0.004)], 0.0055, seg=6)
        B.caja(bm, x - 0.007, x + 0.007, y_eje - r_barra - 0.003, y_eje + r_barra + 0.003,
               z_barra - r_barra - 0.004, z_barra - r_barra)
    barra = B.objeto(col, f"{prefijo}_Barra", bm, METAL, angulo_suave=40)
    return [tela, barra]
