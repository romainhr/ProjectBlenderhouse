"""Contenido de clósets y nevera (fase "07 detalle interactivo", parte 07b): ropa colgada en perchas, ropa
doblada, zapatos, cajas de guardado, maleta y alimentos. Lo usa build/depto_03_formas.py (closets() y nevera()).

Todo se arma con bmesh en un marco local métrico (u, v, z) que `Marco` lleva al mundo de Blender: u a lo largo
del mueble (la barra de colgar, el ancho de la nevera), v del fondo hacia el frente y z hacia arriba. Así las
medidas se escriben en metros y no en px del plano. Sin booleanos ni subdivisión; determinista (random.Random
con semilla fija); API de bpy 3.6.

Criterios (diseño, no salen del plano; docs/noche-2026-09-26.md, entrada 07b):
- Las prendas cuelgan perpendiculares a la barra, como en un clóset real: de frente se ven de canto, una junto
  a otra. Cada prenda es una superficie cerrada con la silueta de la prenda (camisa, polera, suéter, polerón,
  chaqueta, abrigo, vestido, pantalón doblado en una percha de pantalón): más gruesa al centro que en los cantos,
  con pliegues que se marcan hacia el ruedo y mangas que cuelgan de los hombros.
- La percha (madera o alambre) queda dentro de los hombros de la prenda y el gancho abraza la barra. La barra,
  las perchas y las prendas de una barra son un solo objeto con varios materiales: se tocan por diseño, y la
  prueba de interferencias de la fase 3 (islas de objetos distintos) se sigue aplicando contra puertas, fondo,
  costados y repisas.
- La separación entre prendas sale de su espesor real más el barrido de su giro (±1,5°), así ninguna prenda
  atraviesa a la vecina; la densidad (70-90 % de la barra) es la de un clóset en uso, no la de una vitrina.
"""
import math
import random
from contextlib import contextmanager

import bmesh
import bpy
from mathutils import Matrix, Vector

import deco_base as B
import depto_geom as G

TAU = 2 * math.pi


# ================================================================ marco y malla con varios materiales
class Marco:
    """Marco local métrico -> mundo: p = origen + u·U + v·V + z·Z (U y V horizontales y ortogonales)."""

    def __init__(self, origen, U, V):
        self.O, self.U, self.V = Vector(origen), Vector(U).normalized(), Vector(V).normalized()
        o, u, v = self.O, self.U, self.V
        self.M = Matrix(((u.x, v.x, 0.0, o.x), (u.y, v.y, 0.0, o.y), (u.z, v.z, 1.0, o.z), (0.0, 0.0, 0.0, 1.0)))

    def p(self, u, v, z):
        return self.O + self.U * u + self.V * v + Vector((0.0, 0.0, z))


class Malla:
    """bmesh con lista de materiales. `parte(material, matriz)` asigna el material a lo que se construya dentro y
    le aplica la matriz (del sistema de la pieza al marco del mueble)."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def indice(self, material):
        if material not in self.mats:
            self.mats.append(material)
        return self.mats.index(material)

    @contextmanager
    def parte(self, material, matriz=None, suave=False):
        idx = self.indice(material)
        antes_v, antes_f = set(self.bm.verts), set(self.bm.faces)
        yield self.bm
        for f in self.bm.faces:
            if f not in antes_f:
                f.material_index = idx
                f.smooth = suave
        if matriz is not None:
            bmesh.ops.transform(self.bm, matrix=matriz, verts=[v for v in self.bm.verts if v not in antes_v])

    def vacia(self):
        return not self.bm.faces

    def crear(self, col, nombre, marco, origen=None, padre=None, props=None, angulo=40.0):
        """Lleva la malla del marco local al mundo, calcula UV de mundo (metros, como el resto del depto) y crea el
        objeto. origen: punto de mundo del origen del objeto (con padre: el mismo origen del padre, que debe estar
        en su posición de reposo, sin giro)."""
        bm = self.bm
        bmesh.ops.transform(bm, matrix=marco.M, verts=bm.verts)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        G.uv_mundo(bm)
        if origen is not None:
            bmesh.ops.translate(bm, vec=-Vector(origen), verts=bm.verts)
        me = bpy.data.meshes.new(nombre)
        bm.to_mesh(me)
        bm.free()
        if any(p.use_smooth for p in me.polygons):
            me.use_auto_smooth = True
            me.auto_smooth_angle = math.radians(angulo)
        for m in self.mats:
            me.materials.append(G.material(m))
        ob = bpy.data.objects.new(nombre, me)
        if origen is not None and padre is None:
            ob.location = origen
        if padre is not None:
            ob.parent = padre                  # matrix_parent_inverse = identidad: local relativo al padre
        for k, v in (props or {}).items():
            ob[k] = v
        col.objects.link(ob)
        return ob


def _M(u=0.0, v=0.0, z=0.0, giro=0.0):
    """Traslación (u, v, z) con giro en grados alrededor de Z."""
    return Matrix.Translation((u, v, z)) @ Matrix.Rotation(math.radians(giro), 4, "Z")


def _ccw(poli):
    a = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poli, poli[1:] + poli[:1]))
    return poli if a > 0 else list(reversed(poli))


def extruir_poligono(bm, poli, z0, z1):
    """Prisma vertical de base poli [(x, y)] (se ordena CCW) entre z0 y z1."""
    poli = _ccw([tuple(p) for p in poli])
    a = [bm.verts.new((x, y, z0)) for x, y in poli]
    b = [bm.verts.new((x, y, z1)) for x, y in poli]
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    n = len(poli)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))


def esfera(bm, centro, r, escala=(1.0, 1.0, 1.0), subdiv=2):
    """Icoesfera suave (80 caras con subdiv=2; 1 es el icosaedro de 20), escalada por eje."""
    M = Matrix.Translation(Vector(centro)) @ Matrix.Diagonal((*escala, 1.0))
    res = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r, matrix=M)
    return res["verts"]


def cilindro_eje(bm, p0, p1, r, seg=10, tapas=True):
    return B.tubo(bm, [Vector(p0), Vector(p1)], r, seg=seg, tapas=tapas)


# ================================================================ ropa colgada
# Perchas (diseño): hombros de madera 10 × 22 mm o de alambre Ø 4 mm. El eje de la barra es z = 0 del sistema de
# la prenda; el gancho la abraza con 3 mm de holgura.
PERCHA = dict(z_cuello=-0.050, caida_hombro=0.055, alto_madera=0.022, espesor_madera=0.010, r_alambre=0.0022,
              r_gancho=0.0021)


def z_hombro(v, media):
    """Eje de los hombros de la percha a la distancia v del centro (media = media anchura de la percha)."""
    return PERCHA["z_cuello"] - PERCHA["caida_hombro"] * (min(abs(v), media * 1.15) / media) ** 1.6


# tipo: (media anchura de hombros, largo desde el cuello, espesor al centro, espesor del canto)
PRENDAS = {
    "camisa": (0.225, 0.76, 0.024, 0.017),
    "polera": (0.235, 0.68, 0.018, 0.016),
    "sueter": (0.225, 0.64, 0.050, 0.020),
    "poleron": (0.235, 0.66, 0.060, 0.022),
    "chaqueta": (0.235, 0.74, 0.064, 0.024),
    "abrigo": (0.240, 1.00, 0.078, 0.026),
    "vestido": (0.190, 1.02, 0.028, 0.017),
    "pantalon": (0.170, 0.58, 0.036, 0.020),       # doblado sobre la barra de una percha de pantalón
}


RUEDO = {"vestido": 0.05, "abrigo": 0.01, "camisa": -0.012, "polera": -0.02, "sueter": -0.035, "poleron": -0.03,
         "chaqueta": -0.008}      # ancho del ruedo respecto de los hombros (diseño)


def cuerpo_prenda(bm, tipo, largo, t, rng, n=16, niveles=7):
    """Cuerpo de la prenda colgada como superficie cerrada: secciones horizontales desde la línea de hombros (que
    sigue la percha 6 mm por encima) hasta el ruedo curvo. Cada sección es una lente de espesor `t` con pliegues
    que se marcan hacia abajo, como la tela que cae; los cantos (v = ±ancho) quedan finos. z = 0 en el eje de la
    barra; la prenda en el plano v-z, el espesor en u."""
    w, L, _, _ = PRENDAS[tipo]
    L = largo or L
    h2 = PERCHA["alto_madera"] / 2
    if tipo == "pantalon":
        zb = -0.140                                                     # barra de la percha de pantalón

        def z_top(v):
            return zb + 0.013
        bot, curva = zb - L, 0.0
        anchos = [(0.0, w), (0.08, w + 0.004), (1.0, w - 0.018)]
    else:
        media = min(0.205, w - 0.016)
        cuello = 0.055 if tipo in ("poleron", "sueter") else 0.045
        zc = PERCHA["z_cuello"] + h2 + 0.004

        def z_top(v):
            return min(zc, z_hombro(min(abs(v), w), media) + h2 + 0.006) if abs(v) > cuello else zc
        bot, curva = PERCHA["z_cuello"] - L, 0.012 + rng.uniform(0.0, 0.008)
        axila = (0.30 if tipo == "vestido" else 0.18) / L
        lado = w + (0.004 if tipo in ("camisa", "chaqueta", "abrigo") else -0.004)
        anchos = [(0.0, w), (axila, lado), (1.0 - 0.05 / L, w + RUEDO[tipo] + 0.004), (1.0, w + RUEDO[tipo] - 0.012)]

    def ancho(f):
        for (f0, a0), (f1, a1) in zip(anchos[:-1], anchos[1:]):
            if f <= f1:
                return a0 + (a1 - a0) * (f - f0) / max(f1 - f0, 1e-9)
        return anchos[-1][1]
    W1 = ancho(1.0)

    def z_bot(v):
        return bot - curva * max(0.0, 1.0 - (v / W1) ** 2)
    k, fase = rng.choice((3, 4, 5)), rng.uniform(0.0, TAU)
    anillos = []
    for q in range(niveles):
        f = q / (niveles - 1)
        W = ancho(f)
        Tf = t * (0.85 + 0.25 * math.sin(math.pi * min(1.0, f * 1.6)))    # algo más llena en el pecho
        A = 0.06 + 0.30 * f                                                # pliegues más marcados abajo
        anillo = []
        for i in range(n):
            th = TAU * i / n
            c, s_ = math.cos(th), math.sin(th)
            v = W * c
            z = z_top(v) + f * (z_bot(v) - z_top(v))
            u = 0.5 * Tf * math.copysign(abs(s_) ** 0.5, s_) * (1.0 + A * math.sin(k * th + fase))
            anillo.append(bm.verts.new((u, v, z)))
        anillos.append(anillo)
    for a, b in zip(anillos[:-1], anillos[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(anillos[0])
    bm.faces.new(list(reversed(anillos[-1])))


def percha(m, tipo, material, mat_gancho, media, r_barra, pantalon=False):
    """Percha en el sistema de la prenda (eje de la barra en el origen, prenda en el plano v-z)."""
    P = PERCHA
    madera = material != "alambre"
    mat = material if madera else "Depto_Mat_MetalNegroMate"
    n = 7
    pts = [Vector((0.0, v, z_hombro(v, media))) for v in (media * (2 * k / (n - 1) - 1) for k in range(n))]
    with m.parte(mat, suave=not madera) as bm:
        if madera:
            h, t = P["alto_madera"] / 2, P["espesor_madera"] / 2
            anillos = []
            for p in pts:
                anillos.append([bm.verts.new(p + Vector(d)) for d in ((t, 0, h), (-t, 0, h), (-t, 0, -h), (t, 0, -h))])
            for a, b in zip(anillos[:-1], anillos[1:]):
                for k in range(4):
                    j = (k + 1) % 4
                    bm.faces.new((a[k], a[j], b[j], b[k]))
            bm.faces.new(list(reversed(anillos[0])))
            bm.faces.new(anillos[-1])
            if pantalon:
                zb = -0.140
                B.caja(bm, -t, t, -media, media, zb - 0.006, zb + 0.006)                     # barra de abajo
                for s_, p in ((-1, pts[0]), (1, pts[-1])):                                  # brazos laterales
                    B.caja(bm, -t, t, s_ * media - 0.004, s_ * media + 0.004, zb - 0.006, p.z)
        else:
            B.tubo(bm, pts, P["r_alambre"], seg=5, radio_curva=0.0)
            if pantalon:
                zb = -0.140
                B.tubo(bm, [pts[0], Vector((0.0, -media, zb)), Vector((0.0, media, zb)), pts[-1]], P["r_alambre"],
                       seg=5, radio_curva=0.01)
    # gancho: sube del cuello, rodea la barra por arriba y termina en punta
    rb = r_barra + P["r_gancho"] + 0.0005                 # apoyado en la barra
    z0 = pts[n // 2].z + (P["alto_madera"] / 2 if madera else 0.0)
    camino = [Vector((0.0, 0.0, z0 - 0.002)), Vector((0.0, 0.004, z0 + 0.012)), Vector((0.0, rb, -0.004))]
    camino += [Vector((0.0, rb * math.cos(math.radians(a)), rb * math.sin(math.radians(a)))) for a in (0, 50, 95, 140)]
    camino += [Vector((0.0, -rb * 1.02, -0.010))]
    with m.parte(mat_gancho, suave=True) as bm:
        B.tubo(bm, camino, P["r_gancho"], seg=5, radio_curva=0.0)


# Mangas (diseño): largo desde el hombro y radios de la sección elíptica (u = espesor, v = ancho) en el hombro.
MANGAS = {"camisa": (0.60, 0.019, 0.042), "chaqueta": (0.60, 0.030, 0.052), "abrigo": (0.64, 0.034, 0.056),
          "sueter": (0.56, 0.028, 0.048), "poleron": (0.56, 0.032, 0.052), "polera": (0.19, 0.016, 0.055)}


def espesor_efectivo(tipo):
    """Espesor de la prenda en la barra (u), contando las mangas: define la separación entre perchas."""
    t = PRENDAS[tipo][2]
    return max(t, 2 * MANGAS[tipo][1] + 0.004) if tipo in MANGAS else t


def manga(bm, s, w, z_hombro_, largo, ru, rv, rng):
    """Manga colgando del hombro por el costado s (±1) del cuerpo: tubo de sección elíptica que se angosta hacia
    el puño y se mete apenas hacia el cuerpo; su borde exterior no pasa del ancho de la prenda."""
    fr = (0.0, 0.25, 0.62, 1.0)
    ks = (1.0, 0.92, 0.80, 0.70)
    pts = [Vector((rng.uniform(-0.002, 0.002), s * (w - rv * k - 0.004 - 0.018 * f), z_hombro_ - 0.012 - largo * f))
           for f, k in zip(fr, ks)]
    n = 8
    anillos = []
    for p, k in zip(pts, ks):
        anillos.append([bm.verts.new(p + Vector((ru * k * math.cos(TAU * i / n), rv * k * math.sin(TAU * i / n),
                                                 0.0))) for i in range(n)])
    for a, b in zip(anillos[:-1], anillos[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(anillos[0])))
    bm.faces.new(anillos[-1])


def prenda(m, tipo, material, rng, largo=None):
    """Losa de la prenda en su sistema (eje de la barra en el origen), con mangas si las tiene."""
    w, L, t, tb = PRENDAS[tipo]
    t *= rng.uniform(0.9, 1.12)
    with m.parte(material, suave=True) as bm:
        cuerpo_prenda(bm, tipo, largo, t, rng)
        if tipo in MANGAS:
            lm, ru, rv = MANGAS[tipo]
            media = min(0.205, w - 0.016)
            zs = z_hombro(w, media) + PERCHA["alto_madera"] / 2 + 0.006
            for s in (-1, 1):
                manga(bm, s, w, zs, lm * rng.uniform(0.96, 1.03), ru * rng.uniform(0.95, 1.08), rv, rng)
    return t


def barra_colgar(col, nombre, marco, u0, u1, v, z, prendas, semilla, percha_mat="Depto_Mat_FrenteCloset",
                 gancho_mat="Depto_Mat_Acero", barra_mat="Depto_Mat_AceroNegro", r_barra=0.011, llenado=0.92,
                 alineacion="izq"):
    """Barra de colgar de u0 a u1 (de costado a costado, con sus soportes) a la altura z y la profundidad v del
    marco, con `prendas` = [(tipo, material[, largo])] en ese orden. La separación entre prendas es su espesor
    más el barrido del giro más una holgura; si no caben, se descartan las últimas. Devuelve (objeto, n_prendas,
    ocupación de la barra)."""
    rng = random.Random(semilla)
    m = Malla()
    with m.parte(barra_mat, suave=True) as bm:
        cilindro_eje(bm, (u0, v, z), (u1, v, z), r_barra, seg=12)
        for ue, s in ((u0, 1), (u1, -1)):                              # soportes: roseta y copa abierta arriba
            cilindro_eje(bm, (ue, v, z), (ue + s * 0.006, v, z), 0.024, seg=14)
            cilindro_eje(bm, (ue + s * 0.006, v, z - 0.004), (ue + s * 0.020, v, z - 0.004), 0.016, seg=10)
    libre = (u1 - u0) - 0.05
    colocadas = []
    cursor = 0.0
    for item in prendas:
        tipo, mat = item[0], item[1]
        largo = item[2] if len(item) > 2 else None
        w = PRENDAS[tipo][0]
        t = espesor_efectivo(tipo)
        giro = rng.uniform(-1.5, 1.5)
        barrido = t * 1.12 + 2 * (w + 0.01) * math.sin(math.radians(abs(giro)))
        paso = barrido + rng.uniform(0.004, 0.012)
        if cursor + paso > libre * llenado + 0.02:
            break
        colocadas.append((tipo, mat, largo, giro, cursor + paso / 2))
        cursor += paso
    ocupado = cursor
    if alineacion == "centro":
        u_ini = u0 + 0.025 + (libre - ocupado) / 2
    else:
        u_ini = u0 + 0.03
    for tipo, mat, largo, giro, uc in colocadas:
        w = PRENDAS[tipo][0]
        media = 0.19 if tipo == "pantalon" else min(0.205, w - 0.016)
        dv = rng.uniform(-0.008, 0.008)
        antes = set(m.bm.verts)
        percha(m, tipo, percha_mat, gancho_mat, media, r_barra, pantalon=(tipo == "pantalon"))
        prenda(m, tipo, mat, rng, largo)
        bmesh.ops.transform(m.bm, matrix=_M(u_ini + uc, v + dv, z, giro), verts=[x for x in m.bm.verts if x not in antes])
    ob = m.crear(col, nombre, marco, angulo=50.0)
    return ob, len(colocadas), round(ocupado / (u1 - u0), 3)


# ================================================================ ropa doblada, zapatos, cajas
def pila_doblada(m, u_c, v_c, z0, ancho, hondo, capas, materiales, rng, alto_capa=0.052):
    """Pila de prendas dobladas: capas redondeadas (el doblez al frente), cada una algo corrida y de tamaño
    levemente distinto, con el material elegido entre `materiales`. Devuelve el z de arriba."""
    z = z0
    for k in range(capas):
        h = alto_capa * rng.uniform(0.82, 1.15)
        a = ancho * rng.uniform(0.94, 1.0)
        d = hondo * rng.uniform(0.95, 1.0)
        du, dv = rng.uniform(-0.008, 0.008), rng.uniform(-0.006, 0.006)
        with m.parte(rng.choice(materiales), suave=True) as bm:
            B.caja_redondeada(bm, u_c + du - a / 2, u_c + du + a / 2, v_c + dv - d / 2, v_c + dv + d / 2, z, z + h,
                              min(0.018, h * 0.42), segmentos=1)
        z += h
    return z


def _perfil_zapato(tipo):
    """Estaciones (x desde el talón, media anchura, alto del empeine) y alto de la suela, por tipo (diseño)."""
    if tipo == "bota":
        return 0.27, 0.022, [(0.0, 0.030, 0.150), (0.03, 0.036, 0.160), (0.08, 0.040, 0.150), (0.12, 0.043, 0.090),
                             (0.18, 0.046, 0.065), (0.23, 0.040, 0.050), (0.258, 0.030, 0.038), (0.27, 0.016, 0.022)]
    if tipo == "zapatilla":
        return 0.27, 0.026, [(0.0, 0.031, 0.060), (0.03, 0.038, 0.072), (0.08, 0.040, 0.070), (0.13, 0.045, 0.062),
                             (0.19, 0.048, 0.050), (0.235, 0.042, 0.040), (0.259, 0.030, 0.030), (0.27, 0.015, 0.018)]
    if tipo == "taco":                                                  # botín de taco bajo, de mujer
        return 0.245, 0.014, [(0.0, 0.026, 0.120), (0.03, 0.031, 0.125), (0.07, 0.034, 0.110), (0.11, 0.036, 0.060),
                              (0.165, 0.040, 0.040), (0.21, 0.034, 0.030), (0.234, 0.024, 0.022), (0.245, 0.012, 0.014)]
    return 0.27, 0.014, [(0.0, 0.030, 0.055), (0.03, 0.036, 0.062), (0.08, 0.039, 0.058), (0.13, 0.043, 0.048),
                         (0.19, 0.046, 0.040), (0.235, 0.040, 0.032), (0.259, 0.028, 0.024), (0.27, 0.014, 0.014)]


def zapato(m, tipo, mat_capellada, mat_suela, M):
    """Un zapato: suela (planta extruida) y capellada (loft de secciones redondeadas). Sistema: x hacia la punta,
    y a lo ancho, z arriba; apoyado en z = 0 con el talón en x = 0. M: matriz al marco del mueble."""
    L, s, est = _perfil_zapato(tipo)
    planta = [(x, b + 0.003) for x, b, _ in est] + [(x, -(b + 0.003)) for x, b, _ in reversed(est)]
    with m.parte(mat_suela, M) as bm:
        extruir_poligono(bm, planta, 0.0, s)
    with m.parte(mat_capellada, M, suave=True) as bm:
        anillos = []
        for x, b, h in est:
            sec = [(-b, 0.0), (-b, 0.45 * h), (-0.72 * b, 0.86 * h), (0.0, h), (0.72 * b, 0.86 * h), (b, 0.45 * h),
                   (b, 0.0)]
            anillos.append([bm.verts.new((x, y, s + z)) for y, z in sec])
        for a, b in zip(anillos[:-1], anillos[1:]):
            for k in range(len(a) - 1):
                bm.faces.new((a[k], a[k + 1], b[k + 1], b[k]))
            bm.faces.new((a[-1], a[0], b[0], b[-1]))                                  # base (sobre la suela)
        bm.faces.new(list(reversed(anillos[0])))
        bm.faces.new(anillos[-1])
    if tipo != "bota":
        # boca del zapato: óvalo oscuro (el forro) pegado 1 mm sobre la capellada, entre el talón y el medio pie
        x0b, x1b = est[0][0] + 0.014, est[2][0] + 0.03
        with m.parte("Depto_Mat_CableTela", M) as bm:
            pts = []
            for i in range(12):
                x = x0b + (x1b - x0b) * (0.5 + 0.5 * math.cos(TAU * i / 12))
                y = 0.60 * est[1][1] * math.sin(TAU * i / 12)
                pts.append(bm.verts.new((x, y, _z_capellada(est, s, x, y) + 0.001)))
            bm.faces.new(pts)


def _z_capellada(est, s, x, y):
    """Altura de la cara de arriba de la capellada en (x, y), interpolando las estaciones de _perfil_zapato."""
    for (xa, ba, ha), (xb, bb, hb) in zip(est[:-1], est[1:]):
        if x <= xb:
            t = (x - xa) / max(xb - xa, 1e-9)
            b, h = ba + (bb - ba) * t, ha + (hb - ha) * t
            break
    else:
        _, b, h = est[-1]
    a = min(1.0, abs(y) / max(b, 1e-9))
    tramo = [(0.0, 1.0), (0.72, 0.86), (1.0, 0.45)]                     # (|y|/b, z/h) de la sección
    for (ya, za), (yb, zb) in zip(tramo[:-1], tramo[1:]):
        if a <= yb:
            return s + h * (za + (zb - za) * (a - ya) / (yb - ya))
    return s + h * 0.45


def par_zapatos(m, tipo, mat_capellada, mat_suela, u_c, v_c, z0, hacia_frente=True, separacion=0.105, giro=0.0):
    """Par de zapatos con la punta hacia el frente del mueble (+v) o hacia el fondo, centrado en (u_c, v_c)."""
    L = _perfil_zapato(tipo)[0]
    ang = 90.0 if hacia_frente else -90.0
    for k, s in enumerate((-1, 1)):
        g = ang + giro + s * 2.0
        c = Vector((u_c + s * separacion / 2, v_c, z0))
        d = Matrix.Rotation(math.radians(g), 3, "Z") @ Vector((L / 2, 0.0, 0.0))
        M = Matrix.Translation(c - d) @ Matrix.Rotation(math.radians(g), 4, "Z")
        zapato(m, tipo, mat_capellada, mat_suela, M)


def caja_guardado(m, u_c, v_c, z0, ancho, hondo, alto, mat_cuerpo, mat_tapa=None, tapa=0.035):
    """Caja de guardado con tapa que sobresale 4 mm por lado."""
    with m.parte(mat_cuerpo) as bm:
        B.caja(bm, u_c - ancho / 2, u_c + ancho / 2, v_c - hondo / 2, v_c + hondo / 2, z0, z0 + alto - tapa + 0.004)
    with m.parte(mat_tapa or mat_cuerpo, suave=True) as bm:
        B.caja_redondeada(bm, u_c - ancho / 2 - 0.004, u_c + ancho / 2 + 0.004, v_c - hondo / 2 - 0.004,
                          v_c + hondo / 2 + 0.004, z0 + alto - tapa, z0 + alto, 0.003, segmentos=1)


def maleta(m, u_c, v_c, z0, ancho, hondo, alto, mat_casco, mat_detalle):
    """Maleta de cabina acostada: casco redondeado, cierre perimetral y manilla."""
    with m.parte(mat_casco, suave=True) as bm:
        B.caja_redondeada(bm, u_c - ancho / 2, u_c + ancho / 2, v_c - hondo / 2, v_c + hondo / 2, z0, z0 + alto,
                          0.025, segmentos=1)
    zc = z0 + alto * 0.52
    with m.parte(mat_detalle) as bm:
        B.caja(bm, u_c - ancho / 2 - 0.002, u_c + ancho / 2 + 0.002, v_c - hondo / 2 - 0.002, v_c + hondo / 2 + 0.002,
               zc - 0.006, zc + 0.006)
        B.tubo(bm, [Vector((u_c - 0.07, v_c + hondo / 2 - 0.004, zc + 0.03)),
                    Vector((u_c - 0.06, v_c + hondo / 2 + 0.022, zc + 0.03)),
                    Vector((u_c + 0.06, v_c + hondo / 2 + 0.022, zc + 0.03)),
                    Vector((u_c + 0.07, v_c + hondo / 2 - 0.004, zc + 0.03))], 0.007, seg=6, radio_curva=0.01)


def calcetines(m, u0, u1, v0, v1, z0, materiales, rng, r=0.022):
    """Calcetines enrollados (cilindros acostados) en filas dentro de un cajón."""
    paso_u, paso_v = 2 * r + 0.008, 0.095
    nu, nv = int((u1 - u0) // paso_u), int((v1 - v0) // paso_v)
    for i in range(nu):
        for j in range(nv):
            uc = u0 + paso_u * (i + 0.5)
            vc = v0 + paso_v * (j + 0.5)
            with m.parte(rng.choice(materiales), suave=True) as bm:
                cilindro_eje(bm, (uc, vc - 0.04, z0 + r), (uc, vc + 0.04, z0 + r), r * rng.uniform(0.9, 1.05), seg=8)


# ================================================================ alimentos (nevera)
def botella(m, x, y, z0, r, alto, mat_vidrio, mat_liquido=None, llenado=0.8, cuello=0.3, tapa_mat=None):
    """Botella de vidrio (cuerpo, hombro y cuello) con líquido interior opcional y tapa."""
    zh = z0 + alto * (1 - cuello)
    perfil = [(0.0, z0), (r, z0), (r, zh), (r * 0.42, zh + alto * cuello * 0.45), (r * 0.36, z0 + alto),
              (0.0, z0 + alto)]
    with m.parte(mat_vidrio, suave=True) as bm:
        an = B.torno(bm, perfil, seg=14)
        bmesh.ops.translate(bm, vec=(x, y, 0.0), verts=[v for a in an for v in a])
    if mat_liquido:
        zl = z0 + 0.004 + (alto * (1 - cuello) - 0.008) * llenado
        with m.parte(mat_liquido, suave=True) as bm:
            an = B.torno(bm, [(0.0, z0 + 0.004), (r - 0.003, z0 + 0.004), (r - 0.003, zl), (0.0, zl)], seg=12)
            bmesh.ops.translate(bm, vec=(x, y, 0.0), verts=[v for a in an for v in a])
    if tapa_mat:
        with m.parte(tapa_mat, suave=True) as bm:
            B.cilindro(bm, x, y, z0 + alto - 0.002, z0 + alto + 0.012, r * 0.40, seg=10)


def frasco(m, x, y, z0, r, alto, mat_vidrio, mat_contenido, mat_tapa):
    with m.parte(mat_vidrio, suave=True) as bm:
        B.cilindro(bm, x, y, z0, z0 + alto - 0.012, r, seg=14)
    with m.parte(mat_contenido, suave=True) as bm:
        B.cilindro(bm, x, y, z0 + 0.003, z0 + (alto - 0.012) * 0.75, r - 0.003, seg=12)
    with m.parte(mat_tapa, suave=True) as bm:
        B.cilindro(bm, x, y, z0 + alto - 0.013, z0 + alto, r * 1.03, seg=14)


def carton(m, x, y, z0, ancho, hondo, alto, mat, mat_tapa=None, giro=0.0):
    """Envase de cartón de techo a dos aguas (leche, jugo), girado `giro` grados."""
    Mg = Matrix.Translation((x, y, z0)) @ Matrix.Rotation(math.radians(giro), 4, "Z")
    a, d = ancho / 2, hondo / 2
    with m.parte(mat, Mg) as bm:
        B.caja(bm, -a, a, -d, d, 0.0, alto)
        v = [bm.verts.new(c) for c in ((-a, -d, alto), (a, -d, alto), (a, d, alto), (-a, d, alto),
                                       (-a, 0.0, alto + 0.045), (a, 0.0, alto + 0.045))]
        bm.faces.new((v[0], v[1], v[5], v[4]))
        bm.faces.new((v[2], v[3], v[4], v[5]))
        bm.faces.new((v[0], v[4], v[3]))
        bm.faces.new((v[1], v[2], v[5]))
        B.caja(bm, -a, a, -0.002, 0.002, alto + 0.043, alto + 0.058)                  # pestaña del techo
    if mat_tapa:
        with m.parte(mat_tapa, Mg, suave=True) as bm:
            B.cilindro(bm, a * 0.35, -d * 0.45, alto + 0.018, alto + 0.034, 0.012, seg=10)


def fruta(m, x, y, z0, r, mat, aplastar=1.0):
    """Fruta o verdura redonda (manzana, naranja, tomate, lechuga) apoyada en z0; aplastar < 1 la achata."""
    with m.parte(mat, suave=True) as bm:
        esfera(bm, (x, y, z0 + r * aplastar), r, (1.0, 1.0, aplastar))


def zanahoria(m, p0, p1, r, mat, mat_hojas):
    """Cono acostado de p0 (hombro) a p1 (punta) con un penacho corto de hojas."""
    with m.parte(mat, suave=True) as bm:
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0)
        pts = [p0 + d * t for t in (0.0, 0.25, 0.6, 1.0)]
        radios = [r, r * 0.9, r * 0.6, r * 0.12]
        anillos = []
        eje = d.normalized()
        ref = Vector((0, 0, 1)) if abs(eje.z) < 0.9 else Vector((1, 0, 0))
        n1 = (ref - eje * ref.dot(eje)).normalized()
        n2 = eje.cross(n1)
        for p, rr in zip(pts, radios):
            anillos.append([bm.verts.new(p + (n1 * math.cos(TAU * k / 8) + n2 * math.sin(TAU * k / 8)) * rr)
                            for k in range(8)])
        for a, b in zip(anillos[:-1], anillos[1:]):
            for k in range(8):
                j = (k + 1) % 8
                bm.faces.new((a[k], a[j], b[j], b[k]))
        bm.faces.new(list(reversed(anillos[0])))
        bm.faces.new(anillos[-1])
    with m.parte(mat_hojas, suave=True) as bm:
        cilindro_eje(bm, p0, p0 - (p1 - p0).normalized() * 0.03, r * 0.35, seg=6)
