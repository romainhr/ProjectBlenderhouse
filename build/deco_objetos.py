"""Luminarias y objetos de la decoración industrial (versión 2, docs/deco-industrial.md, «Luminarias y objetos»).

Piezas: colgante_domo, colgante_jaula, ampolleta_edison, aplique_brazo, conducto, libros, jarron, bol y
reloj_pared. Todo se crea desde cero por código (bmesh), sin booleanos ni subdivisión, determinista y con la API de
bpy 3.6.

Convenciones del documento: metros, Z arriba, huella centrada en el origen, apoyada en z = 0, frente hacia −Y.
Excepciones: colgantes y ampolleta (origen en el anclaje, cuelgan hacia −Z) y piezas murales (cara de atrás en
y = 0). Todos los objetos de una pieza tienen origen (0, 0, 0) y no tienen rotación. Un objeto por material o
por conjunto natural (p. ej. la pantalla lleva exterior negro e interior blanco en la misma malla).

Materiales nuevos que registra este módulo (depto_geom.MATERIALES.setdefault): Depto_Mat_Laton (casquillo E27 e
hilos conductores de la ampolleta) y Depto_Mat_VidrioReloj (cristal neutro del reloj: Depto_Mat_Vidrio es el de
ventanas y tiñe de azul las agujas negras).
"""
import bisect
import math
import random
from contextlib import contextmanager

import bmesh
from mathutils import Matrix, Vector

import deco_base as B
import depto_geom as G

TAU = 2 * math.pi

# ---------------------------------------------------------------- materiales (nombres de depto_geom.MATERIALES)
NEGRO = "Depto_Mat_MetalNegroMate"          # luminarias, herrajes, conducto y reloj
INTERIOR = "Depto_Mat_PantallaInterior"     # esmalte blanco del interior de las pantallas
CABLE = "Depto_Mat_CableTela"
VIDRIO_AMP = "Depto_Mat_VidrioBombilla"     # vidrio ámbar translúcido
FILAMENTO = "Depto_Mat_Bombilla"            # emisivo
LATON = "Depto_Mat_Laton"                   # nuevo: casquillo E27
PAPEL = "Depto_Mat_Papel"
VIDRIO_RELOJ = "Depto_Mat_VidrioReloj"        # nuevo: cristal neutro
LIBROS = [f"Depto_Mat_Libro{i}" for i in range(1, 6)]
GRES_NEGRO, GRES_ARENA, GRES_BLANCO = "Depto_Mat_GresNegro", "Depto_Mat_GresArena", "Depto_Mat_GresBlanco"

G.MATERIALES.setdefault(LATON, ((0.71, 0.55, 0.33), 0.35, 1.0, 1.0))   # latón envejecido (diseño)
G.MATERIALES.setdefault(VIDRIO_RELOJ, ((0.96, 0.96, 0.96), 0.03, 0.0, 0.10))   # cristal claro sin tinte (diseño)


# ================================================================ ayudas propias
class _Malla:
    """bmesh con lista de materiales; `parte` asigna material, sombreado y matriz a lo que se construya dentro."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def indice(self, material):
        if material not in self.mats:
            self.mats.append(material)
        return self.mats.index(material)

    @contextmanager
    def parte(self, material=None, matriz=None, suave=None):
        idx = self.indice(material) if material else None
        antes_v, antes_f = set(self.bm.verts), set(self.bm.faces)
        yield self.bm
        if idx is not None or suave is not None:
            for f in self.bm.faces:
                if f not in antes_f:
                    if idx is not None:
                        f.material_index = idx
                    if suave is not None:
                        f.smooth = suave
        if matriz is not None:
            bmesh.ops.transform(self.bm, matrix=matriz, verts=[v for v in self.bm.verts if v not in antes_v])

    def trasladar(self, vec):
        bmesh.ops.translate(self.bm, vec=Vector(vec), verts=list(self.bm.verts))

    def crear(self, col, nombre, angulo=35.0, recalc=True, props=None):
        if not self.bm.faces:
            self.bm.free()
            return None
        return B.objeto(col, nombre, self.bm, self.mats[0], materiales=self.mats, angulo_suave=angulo,
                        recalc=recalc, props=props)


def _caja_mallas(mallas):
    pts = [v.co for m in mallas for v in m.bm.verts]
    return (Vector([min(p[k] for p in pts) for k in range(3)]), Vector([max(p[k] for p in pts) for k in range(3)]))


def _M(origen=(0.0, 0.0, 0.0), eje=None):
    """Matriz que lleva el eje Z local a `eje` y el origen local a `origen`."""
    R = Matrix.Identity(3)
    if eje is not None:
        R = Vector((0.0, 0.0, 1.0)).rotation_difference(Vector(eje).normalized()).to_matrix()
    return Matrix.Translation(Vector(origen)) @ R.to_4x4()


def _torno(bm, perfil, seg=32, cerrado=False, indices=None, fase=0.0):
    """Superficie de revolución alrededor de Z con caras orientadas de forma coherente (la normal queda a la
    derecha del recorrido del perfil en el semiplano (r, z): un perfil antihorario da normales hacia afuera).
    perfil: [(r, z)] o [(r, z, estria)]; estria > 0 alterna el radio de los vértices del anillo (moleteado, seg
    par). Un radio 0 es un polo. indices: índice de material de cada tramo del perfil."""
    anillos = []
    for p in perfil:
        r, z = p[0], p[1]
        est = p[2] if len(p) > 2 else 0.0
        if r < 1e-7:
            anillos.append([bm.verts.new((0.0, 0.0, z))])
            continue
        anillo = []
        for i in range(seg):
            a = TAU * i / seg + fase
            rr = r - (est if i % 2 else 0.0)
            anillo.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z)))
        anillos.append(anillo)
    n = len(anillos)
    tramos = [(k, k + 1) for k in range(n - 1)] + ([(n - 1, 0)] if cerrado else [])
    for t, (ka, kb) in enumerate(tramos):
        a, b = anillos[ka], anillos[kb]
        if len(a) == 1 and len(b) == 1:
            continue
        for i in range(seg):
            j = (i + 1) % seg
            if len(a) == 1:
                vs = (a[0], b[j], b[i])
            elif len(b) == 1:
                vs = (a[i], a[j], b[0])
            else:
                vs = (a[i], a[j], b[j], b[i])
            f = bm.faces.new(vs)
            f.smooth = True
            if indices is not None:
                f.material_index = indices[t]
    return anillos


def _torno_eje(bm, perfil, origen, eje, seg=16, **kw):
    """_torno alrededor de un eje cualquiera que pasa por `origen` (z del perfil = distancia sobre el eje)."""
    antes = set(bm.verts)
    _torno(bm, perfil, seg, **kw)
    bmesh.ops.transform(bm, matrix=_M(origen, eje), verts=[v for v in bm.verts if v not in antes])


def _toro(bm, R, r, z=0.0, seg=32, seg_sec=5):
    """Anillo de alambre (toro) horizontal de radio medio R y sección r, centrado en el eje Z a la altura z."""
    anillos = []
    for i in range(seg):
        a = TAU * i / seg
        c, s = math.cos(a), math.sin(a)
        anillos.append([bm.verts.new(((R + r * math.cos(TAU * j / seg_sec)) * c,
                                      (R + r * math.cos(TAU * j / seg_sec)) * s,
                                      z + r * math.sin(TAU * j / seg_sec))) for j in range(seg_sec)])
    for i in range(seg):
        A, Bn = anillos[i], anillos[(i + 1) % seg]
        for j in range(seg_sec):
            k = (j + 1) % seg_sec
            bm.faces.new((A[j], Bn[j], Bn[k], A[k])).smooth = True


def _area(contorno):
    return 0.5 * sum(contorno[i][0] * contorno[(i + 1) % len(contorno)][1]
                     - contorno[(i + 1) % len(contorno)][0] * contorno[i][1] for i in range(len(contorno)))


def _extruir(bm, contorno, z0, z1, suave=False):
    """Prisma recto de un polígono plano (x, y) entre z0 y z1, con caras hacia afuera (el polígono se reordena
    en sentido antihorario si hace falta). Sirve para polígonos cóncavos."""
    if _area(contorno) < 0:
        contorno = list(reversed(contorno))
    abajo = [bm.verts.new((x, y, z0)) for x, y in contorno]
    arriba = [bm.verts.new((x, y, z1)) for x, y in contorno]
    bm.faces.new(list(reversed(abajo)))
    bm.faces.new(arriba)
    n = len(contorno)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((abajo[i], abajo[j], arriba[j], arriba[i])).smooth = suave


def _cinta(bm, pts, lateral, ancho, espesor):
    """Fleje de sección rectangular (ancho según `lateral`, espesor en el plano del recorrido) a lo largo de una
    polilínea plana, con esquinas en inglete. Cerrado."""
    lateral = Vector(lateral).normalized()
    n = len(pts)
    anillos = []
    for i in range(n):
        d1 = (pts[i] - pts[i - 1]).normalized() if i > 0 else (pts[i + 1] - pts[i]).normalized()
        d2 = (pts[i + 1] - pts[i]).normalized() if i < n - 1 else d1
        d = (d1 + d2).normalized()
        esc = 1.0 / max(0.35, d.dot(d2))
        m = lateral.cross(d).normalized() * esc
        anillos.append([bm.verts.new(pts[i] + lateral * (sx * ancho / 2) + m * (sy * espesor / 2))
                        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for a, b in zip(anillos[:-1], anillos[1:]):
        for k in range(4):
            j = (k + 1) % 4
            bm.faces.new((a[k], a[j], b[j], b[k]))
    bm.faces.new(list(reversed(anillos[0])))
    bm.faces.new(anillos[-1])


def _spline(ctrl, pasos=12):
    """Catmull-Rom uniforme por los puntos de control 2D; devuelve la curva densa (incluye los extremos)."""
    P = [Vector(c) for c in ctrl]
    ext = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for s in range(pasos):
            t = s / pasos
            out.append(0.5 * (p1 * 2 + (p2 - p0) * t + (p0 * 2 - p1 * 5 + p2 * 4 - p3) * t * t
                              + (p1 * 3 - p0 - p2 * 3 + p3) * t * t * t))
    out.append(P[-1])
    return [(v.x, v.y) for v in out]


def _remuestrear(pts, n, curvatura=0.55):
    """n puntos sobre una polilínea densa, repartidos por largo y por curvatura (más puntos donde dobla)."""
    P = [Vector(p) for p in pts]
    L = [(P[i + 1] - P[i]).length for i in range(len(P) - 1)]
    A = [0.0] * len(P)
    for i in range(1, len(P) - 1):
        d1, d2 = P[i] - P[i - 1], P[i + 1] - P[i]
        if d1.length > 1e-9 and d2.length > 1e-9:
            A[i] = d1.angle(d2)
    ang = [(A[i] + A[i + 1]) / 2 for i in range(len(L))]
    sl, sa = sum(L), sum(ang)
    w = [(1 - curvatura) * L[i] / sl + (curvatura * ang[i] / sa if sa > 1e-9 else curvatura * L[i] / sl)
         for i in range(len(L))]
    acum = [0.0]
    for x in w:
        acum.append(acum[-1] + x)
    out = []
    for k in range(n):
        s = acum[-1] * k / (n - 1)
        i = max(0, min(len(L) - 1, bisect.bisect_right(acum, s) - 1))
        f = (s - acum[i]) / (acum[i + 1] - acum[i]) if acum[i + 1] > acum[i] else 0.0
        q = P[i].lerp(P[i + 1], min(1.0, f))
        out.append((q.x, q.y))
    return out


def _paralela(pts, d):
    """Curva 2D paralela, desplazada d hacia la izquierda del recorrido (d < 0: hacia la derecha)."""
    n = len(pts)
    out = []
    for i in range(n):
        t = (Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        q = Vector(pts[i]) + Vector((-t.y, t.x)) * d
        out.append((q.x, q.y))
    return out


def _labio(p_ext, p_int, tangente, radio, angulos):
    """Puntos de un labio circular alrededor del punto medio entre la cara exterior y la interior del borde."""
    p_ext, p_int, t = Vector(p_ext), Vector(p_int), Vector(tangente).normalized()
    n_o = (p_ext - p_int).normalized()
    c = (p_ext + p_int) / 2
    return [tuple(c + (n_o * math.cos(math.radians(a)) + t * math.sin(math.radians(a))) * radio) for a in angulos]


# ================================================================ ampolleta Edison
# Control (r, z) del perfil del vidrio desde la boca (dentro del casquillo) hasta la punta; z = 0 es el contacto
# del casquillo. El perfil se suaviza con una spline y se remuestrea por curvatura. jaula del filamento: (z sup, r sup,
# z inf, r inf, ganchos); tallo: cota inferior del tallo de vidrio.
def _esfera(R, zc, grados):
    return [(R * math.sin(math.radians(f)), zc + R * math.cos(math.radians(f))) for f in grados]


_AMPOLLETAS = {
    # ST64 «pera vintage»: Ø 64 × 143 (medida usual de catálogo)
    "ST64": dict(vidrio=[(0.0113, -0.018), (0.0118, -0.028), (0.0150, -0.043), (0.0215, -0.062), (0.0285, -0.082),
                         (0.0320, -0.101), (0.0305, -0.118), (0.0245, -0.131), (0.0130, -0.1395),
                         (0.0028, -0.1418)], punta=-0.1432, jaula=(-0.060, 0.0085, -0.098, 0.0140, 8),
                 tallo=-0.0975),
    # G95 «globo»: Ø 95 × 139
    "G95": dict(vidrio=[(0.0113, -0.018), (0.0118, -0.027), (0.0150, -0.036)]
                + _esfera(0.0475, -0.090, (30, 50, 70, 90, 110, 130, 150, 166)) + [(0.0028, -0.1377)],
                punta=-0.1388, jaula=(-0.068, 0.0100, -0.108, 0.0170, 8), tallo=-0.1075),
    # G45 «globo chico»: Ø 45 × 78
    "G45": dict(vidrio=[(0.0113, -0.018), (0.0116, -0.025), (0.0128, -0.030)]
                + _esfera(0.0225, -0.0555, (42, 65, 90, 115, 140, 162)) + [(0.0022, -0.0778)],
                punta=-0.0784, jaula=(-0.045, 0.0045, -0.066, 0.0075, 6), tallo=-0.0655),
}


def _perfil_casquillo(rosca=True):
    """Casquillo E27 (Ø 26,5 × 23,5): contacto arriba (z = 0), rosca redondeada, borde que abraza el vidrio."""
    p = [(0.0, 0.0), (0.0045, 0.0), (0.0108, -0.0022), (0.0124, -0.0038)]
    if rosca:
        p += [(0.0133 if k % 2 == 0 else 0.0121, -0.0058 - 0.0019 * k) for k in range(7)]
    else:
        p += [(0.0131, -0.0058), (0.0131, -0.0172)]
    return p + [(0.0127, -0.0205), (0.0121, -0.0235), (0.0, -0.0235)]


def _ampolleta(vid, fil, cas, M, forma="ST64", seg=16, n_vidrio=13, seg_casquillo=10, rosca=True, soportes=True,
               guias=True, tallo=True):
    """Ampolleta completa en tres mallas (vidrio, filamento emisivo, casquillo de latón), con el contacto del
    casquillo en el origen de M y colgando hacia −Z local."""
    F = _AMPOLLETAS[forma]
    with cas.parte(LATON, M) as bm:
        _torno(bm, _perfil_casquillo(rosca), seg=seg_casquillo)
    with vid.parte(VIDRIO_AMP, M) as bm:
        perfil = _remuestrear(_spline(F["vidrio"], 10), n_vidrio, curvatura=0.5)
        _torno(bm, [(0.0, -0.018)] + perfil + [(0.0, F["punta"])], seg=seg)
        if tallo:
            B.caja(bm, -0.0045, 0.0045, -0.0011, 0.0011, -0.034, -0.021)          # prensado de vidrio
            B.cilindro(bm, 0.0, 0.0, F["tallo"], -0.0335, 0.0015, seg=6)           # tallo
            B.cilindro(bm, 0.0, 0.0, F["tallo"] - 0.0015, F["tallo"] + 0.0015, 0.0028, seg=6)   # botón
    zs, rs, zi, ri, n = F["jaula"]
    f0 = math.pi / n                     # ganchos simétricos respecto del plano del prensado
    arriba = [Vector((rs * math.cos(f0 + TAU * k / n), rs * math.sin(f0 + TAU * k / n), zs)) for k in range(n)]
    abajo = [Vector((ri * math.cos(f0 + TAU * (k + 0.5) / n), ri * math.sin(f0 + TAU * (k + 0.5) / n), zi))
             for k in range(n)]
    camino = []
    for k in range(n):
        camino.append(arriba[k])
        if k < n - 1:
            camino.append(abajo[k])
    with fil.parte(FILAMENTO, M) as bm:
        B.tubo(bm, camino, 0.00045, seg=4)           # filamento «jaula de ardilla» en zigzag
    with cas.parte(LATON, M) as bm:
        if guias:                                   # hilos conductores del prensado a los extremos del filamento
            for s, p in ((1, arriba[0]), (-1, arriba[-1])):
                B.tubo(bm, [Vector((0.0026, 0.0004 * s, -0.0335)), Vector((0.0048, 0.0016 * s, zs + 0.010)), p],
                       0.0003, seg=4)
        if soportes:                                # alambres de soporte desde el tallo a cada gancho
            for p in arriba:
                B.tubo(bm, [Vector((0.0, 0.0, zs + 0.003)), p], 0.00022, seg=3)
            for p in abajo:
                B.tubo(bm, [Vector((0.0, 0.0, F["tallo"])), p], 0.00022, seg=3)
    return F["punta"]


def ampolleta_edison(col, prefijo, forma="ST64", soportes=True):
    """Ampolleta Edison de filamento (ST64 pera, G95 globo o G45 globo chico) con casquillo E27. Origen en el
    contacto del casquillo; cuelga hacia −Z. ≤ 1 000 triángulos."""
    vid, fil, cas = _Malla(), _Malla(), _Malla()
    _ampolleta(vid, fil, cas, Matrix.Identity(4), forma, seg=16, n_vidrio=13 if forma != "G45" else 11,
               seg_casquillo=10, soportes=soportes)
    objs = [cas.crear(col, f"{prefijo}_Casquillo", angulo=40), vid.crear(col, f"{prefijo}_Vidrio"),
            fil.crear(col, f"{prefijo}_Filamento", angulo=60)]
    return [o for o in objs if o]


# ================================================================ piezas comunes de colgantes
def _floron(bm, seg=24):
    """Florón de cielo Ø 0,11 × 0,030 (tope en z = 0) con canto redondeado, prensacable con tuerca hexagonal y dos
    tornillos laterales. Devuelve la cota por donde sale el cable."""
    R, H = 0.055, 0.030                                                 # diseño: florón estándar
    _torno(bm, [(0.0, -H), (R - 0.007, -H), (R - 0.002, -H + 0.002), (R, -H + 0.007), (R, 0.0), (0.0, 0.0)], seg)
    B.cilindro(bm, 0.0, 0.0, -H - 0.006, -H + 0.0005, 0.0095, seg=6)                    # tuerca
    _torno(bm, [(0.0, -H - 0.013), (0.0042, -H - 0.013), (0.0068, -H - 0.0105), (0.0072, -H - 0.006),
                (0.0, -H - 0.006)], 16)                                                 # capuchón
    for s in (1, -1):
        B.tubo(bm, [(s * (R - 0.001), 0.0, -0.013), (s * (R + 0.0022), 0.0, -0.013)], 0.0028, seg=8)
    return -H - 0.013


def _prensacable(bm):
    """Prensacable sobre el cuello de una pantalla (z de 0 a 0,014): tuerca hexagonal y capuchón."""
    B.cilindro(bm, 0.0, 0.0, -0.001, 0.0065, 0.0088, seg=6)
    _torno(bm, [(0.0, 0.0065), (0.0066, 0.0065), (0.0062, 0.011), (0.0040, 0.014), (0.0, 0.014)], 12)


def _pantalla(m, R, alto, r_cuello, alto_cuello, t, seg, n_campana=8, n_interior=5, rb=0.0026, theta_max=68.0,
              angulos_labio=(-40, 25, 90, 155, 220)):
    """Pantalla domo de chapa, en la malla m (con su matriz ya puesta por quien llama): tope del cuello en z = 0,
    cuelga hacia −Z; cuello con tapa, campana elíptica que abre levemente hacia el borde, borde enrollado de
    radio rb, espesor t. Exterior negro e interior blanco (bajo el cuello). La cara interior lleva menos
    muestras que la exterior: no se ve de canto y sus cuerdas se alejan de la cara exterior."""
    ext = [(0.0, 0.0), (r_cuello - 0.003, 0.0), (r_cuello, -0.003), (r_cuello, -(alto_cuello - 0.004)),
           (r_cuello + 0.004, -alto_cuello)]
    r0, z0 = r_cuello + 0.004, -alto_cuello
    tm = math.radians(theta_max)
    a = (R - r0) / math.sin(tm)
    b = (alto - alto_cuello) / (1 - math.cos(tm))

    def campana(th):
        return (r0 + a * math.sin(th), z0 - b * (1 - math.cos(th)))
    ext += [campana(tm * k / n_campana) for k in range(1, n_campana + 1)]
    densa = [campana(tm * k / 60) for k in range(61)]
    bell_int = _remuestrear(_paralela(densa, -t), n_interior + 1, curvatura=0.3)[1:]
    inter = [(0.0, -t), (r_cuello - t, -t)] + _paralela(ext[:6], -t)[3:5] + bell_int
    tang = Vector(ext[-1]) - Vector(ext[-2])
    lab = _labio(ext[-1], inter[-1], tang, rb, angulos_labio)
    perfil = ext[:-1] + lab + list(reversed(inter[:-1]))
    i_int = len(ext) - 1 + len(lab)
    ne, ni = m.indice(NEGRO), m.indice(INTERIOR)
    idx = []
    for k in range(len(perfil) - 1):
        zm = (perfil[k][1] + perfil[k + 1][1]) / 2
        idx.append(ni if (k >= i_int - 1 and zm < -alto_cuello + 1e-4) else ne)
    _torno(m.bm, perfil, seg, indices=idx)


# portalámparas: perfil (r, z) desde el fondo del alojamiento del casquillo; z = 0 es el tope
_PORTA = {
    "domo": ([(0.0, -0.044), (0.0138, -0.044), (0.0138, -0.062), (0.0205, -0.062), (0.0205, -0.0525),
              (0.0185, -0.0515), (0.0185, -0.002), (0.0165, 0.0), (0.0, 0.0)], -0.044),
    "simple": ([(0.0, -0.030), (0.0138, -0.030), (0.0138, -0.046), (0.0168, -0.046), (0.0168, 0.0), (0.0, 0.0)],
               -0.030),
    # vintage a la vista: prensacable moleteado, hombro, cuerpo con buña y fondo abierto
    "vintage": ([(0.0, -0.050), (0.0142, -0.050), (0.0142, -0.058), (0.0190, -0.058), (0.0190, -0.042),
                 (0.0180, -0.041), (0.0180, -0.039), (0.0190, -0.038), (0.0190, -0.0165), (0.0150, -0.012),
                 (0.0085, -0.012, 0.0007), (0.0085, -0.0008, 0.0007), (0.0072, 0.0), (0.0, 0.0)], -0.050),
}


def _portalampara(bm, tipo, seg=16):
    perfil, z_casquillo = _PORTA[tipo]
    _torno(bm, perfil, seg)
    return z_casquillo


# ================================================================ colgantes
def colgante_domo(col, prefijo, largo_cable=0.8, diametro=0.35, alto=0.24, forma="ST64"):
    """Colgante industrial de domo: florón en el cielo (origen, z = 0), cable de tela de `largo_cable` (visible,
    del prensacable del florón al de la pantalla) y domo de chapa de Ø `diametro` × `alto` negro por fuera y
    blanco por dentro, con borde enrollado y ampolleta Edison. Cuelga hacia −Z; caída total ≈ largo_cable +
    alto + 0,060 (valor exacto en la propiedad `caida_m` del objeto Metal). ≤ 3 000 triángulos."""
    metal, pant, cable = _Malla(), _Malla(), _Malla()
    vid, fil, cas = _Malla(), _Malla(), _Malla()
    with metal.parte(NEGRO) as bm:
        z_cable = _floron(bm)
    zt = z_cable - largo_cable - 0.014                     # tope del cuello (bajo el prensacable de 14 mm)
    with metal.parte(NEGRO, _M((0, 0, zt))) as bm:
        _prensacable(bm)
    with cable.parte(CABLE) as bm:
        B.tubo(bm, [(0.0, 0.0, z_cable + 0.004), (0.0, 0.0, zt + 0.010)], 0.0035, seg=10)
    with pant.parte(None, _M((0, 0, zt))):
        _pantalla(pant, diametro / 2, alto, r_cuello=0.025, alto_cuello=0.058, t=0.0015, seg=36)
    z_s = zt - 0.0015                                       # tope del portalámparas bajo la tapa del cuello
    with metal.parte(NEGRO, _M((0, 0, z_s))) as bm:
        z_c = _portalampara(bm, "domo", seg=12)
    _ampolleta(vid, fil, cas, _M((0, 0, z_s + z_c)), forma, seg=16, n_vidrio=10, seg_casquillo=8, rosca=False,
               soportes=False)                              # la rosca queda dentro del portalámparas
    lo, _ = _caja_mallas((metal, pant, cable, vid, fil, cas))
    props = {"caida_m": round(-lo.z, 4), "largo_cable_m": largo_cable}
    objs = [metal.crear(col, f"{prefijo}_Metal", angulo=50, props=props), pant.crear(col, f"{prefijo}_Pantalla"),
            cable.crear(col, f"{prefijo}_Cable", angulo=40), vid.crear(col, f"{prefijo}_Vidrio"),
            fil.crear(col, f"{prefijo}_Filamento", angulo=60), cas.crear(col, f"{prefijo}_Casquillo", angulo=40)]
    return [o for o in objs if o]


def colgante_jaula(col, prefijo, largo_cable=0.8, diametro=0.14, alto=0.17, varillas=6, forma="ST64"):
    """Colgante de jaula: florón (origen, z = 0), cable de tela de `largo_cable`, portalámparas vintage negro con
    prensacable moleteado y anillo roscado que aprieta la jaula de alambre de Ø 3 mm (`varillas` verticales, un
    aro en el ecuador y otro al fondo) y ampolleta Edison a la vista. Cuelga hacia −Z; caída total ≈
    largo_cable + alto + 0,115 (valor exacto en la propiedad `caida_m` del objeto Metal). ≤ 3 000 triángulos."""
    metal, jaula, cable = _Malla(), _Malla(), _Malla()
    vid, fil, cas = _Malla(), _Malla(), _Malla()
    with metal.parte(NEGRO) as bm:
        z_cable = _floron(bm)
    zs = z_cable - largo_cable                               # tope del prensacable del portalámparas
    with cable.parte(CABLE) as bm:
        B.tubo(bm, [(0.0, 0.0, z_cable + 0.004), (0.0, 0.0, zs - 0.004)], 0.0035, seg=10)
    with metal.parte(NEGRO, _M((0, 0, zs))) as bm:
        z_c = _portalampara(bm, "vintage", seg=16)
        # anillo roscado moleteado + arandela de la jaula (un solo perfil cerrado)
        _torno(bm, [(0.0225, -0.058, 0.0006), (0.0225, -0.068, 0.0006), (0.0335, -0.068), (0.0335, -0.0695),
                    (0.0145, -0.0695), (0.0145, -0.058)], 20, cerrado=True)
    _ampolleta(vid, fil, cas, _M((0, 0, zs + z_c)), forma, seg=16, n_vidrio=12, seg_casquillo=10, rosca=False,
               soportes=False)                              # la rosca queda dentro del portalámparas
    # jaula: perfil (r, dz) bajo la arandela, escalado a diametro × alto
    rw = 0.0015                                                          # alambre Ø 3 mm
    sx, sz = (diametro / 2 - rw) / 0.068, alto / 0.165
    ctrl = [(0.031, -0.0015), (0.046, -0.010), (0.059, -0.028), (0.066, -0.055), (0.068, -0.085),
            (0.064, -0.113), (0.053, -0.137), (0.036, -0.155), (0.019, -0.163), (0.0125, -0.165)]
    ctrl = [(ctrl[0][0], ctrl[0][1])] + [(r * sx, z * sz) for r, z in ctrl[1:]]
    ctrl[-1] = (0.0125, ctrl[-1][1])
    perfil = _remuestrear(_spline(ctrl, 10), 12 if varillas <= 6 else 10, curvatura=0.35)   # tope de 3 000
    zc = zs - 0.0695                                                     # cara inferior de la arandela
    with jaula.parte(NEGRO) as bm:
        for k in range(varillas):
            a = TAU * (k + 0.5) / varillas
            B.tubo(bm, [(r * math.cos(a), r * math.sin(a), zc + z) for r, z in perfil], rw, seg=5)
        # aro del ecuador (por fuera de las varillas, soldado) y aro del fondo
        dens = _spline(ctrl, 10)
        r_ec, z_ec = max(dens, key=lambda p: p[0])
        _toro(bm, r_ec + 1.7 * rw, 0.0016, zc + z_ec, seg=28, seg_sec=5)
        _toro(bm, 0.0125, 0.0022, zc + ctrl[-1][1], seg=16, seg_sec=5)
    lo, _ = _caja_mallas((metal, jaula, cable, vid, fil, cas))
    props = {"caida_m": round(-lo.z, 4), "largo_cable_m": largo_cable}
    objs = [metal.crear(col, f"{prefijo}_Metal", angulo=50, props=props),
            jaula.crear(col, f"{prefijo}_Jaula", angulo=80),
            cable.crear(col, f"{prefijo}_Cable", angulo=40), vid.crear(col, f"{prefijo}_Vidrio"),
            fil.crear(col, f"{prefijo}_Filamento", angulo=60), cas.crear(col, f"{prefijo}_Casquillo", angulo=40)]
    return [o for o in objs if o]


# ================================================================ aplique de brazo articulado
def _articulacion(bm, centro, r, ancho, ranuras=1, seg=12, ch=0.0008, prof=0.0012):
    """Articulación de discos con eje en X: `ranuras` buñas en V separan los discos; cantos chaflanados."""
    a = ancho / 2
    perfil = [(0.0, -a), (r - ch, -a), (r, -a + ch)]
    for k in range(ranuras):
        x = -a + ancho * (k + 1) / (ranuras + 1)
        perfil += [(r, x - ch), (r - prof, x), (r, x + ch)]
    perfil += [(r, a - ch), (r - ch, a), (0.0, a)]
    _torno_eje(bm, perfil, centro, (1, 0, 0), seg)


def _perilla(bm, centro, desde):
    """Perilla de apriete de una articulación, del lado +X, desde la cara del disco."""
    _torno_eje(bm, [(0.0, -0.001), (0.0082, -0.001), (0.0082, 0.0068), (0.0062, 0.009), (0.0, 0.009)],
               Vector(centro) + Vector((desde, 0, 0)), (1, 0, 0), 8)


def aplique_brazo(col, prefijo, brazo1=0.28, brazo2=0.26, angulo1=50.0, angulo2=-30.0, inclinacion=25.0,
                  diametro=0.16, forma="G45", giro=0.0):
    """Aplique mural de brazo articulado negro (estilo taller): placa rectangular atornillada al muro (cara de
    atrás en y = 0), dos brazos de tubo de Ø 17 mm con articulaciones de discos y perillas, y pantalla domo de
    Ø `diametro` inclinada hacia −Y con ampolleta (G45 por defecto: la ST64 y la G95 sobresalen de una
    pantalla de 0,16 y pasan el tope). Centrado en X, apoyado en z = 0 (el punto más bajo es el borde de la
    pantalla); la altura del centro de la placa queda en la propiedad `placa_centro_z` del objeto Metal.
    giro (grados, corrección 09): el brazo gira en la primera articulación alrededor de Z (positivo: de −Y hacia
    +X); placa y espiga no giran. ≤ 2 000 triángulos."""
    metal, pant = _Malla(), _Malla()
    vid, fil, cas = _Malla(), _Malla(), _Malla()
    with metal.parte(NEGRO, suave=True) as bm:
        B.caja_redondeada(bm, -0.032, 0.032, -0.012, 0.0, -0.055, 0.055, 0.004, segmentos=2)
    j1 = Vector((0.0, -0.060, 0.0))
    d1 = Vector((0.0, -math.cos(math.radians(angulo1)), math.sin(math.radians(angulo1))))
    j2 = j1 + d1 * brazo1
    d2 = Vector((0.0, -math.cos(math.radians(angulo2)), math.sin(math.radians(angulo2))))
    j3 = j2 + d2 * brazo2
    Mg = Matrix.Translation(j1) @ Matrix.Rotation(math.radians(giro), 4, "Z") @ Matrix.Translation(-j1)
    with metal.parte(NEGRO) as bm:
        for z in (-0.038, 0.038):                                            # tornillos de cabeza redonda
            _torno_eje(bm, [(0.0, 0.0), (0.0042, 0.0), (0.0036, 0.0012), (0.0, 0.0018)], (0, -0.0118, z),
                       (0, -1, 0), 6)
        B.tubo(bm, [(0.0, -0.011, 0.0), (0.0, j1.y + 0.006, 0.0)], 0.0095, seg=8)    # espiga de la placa
    with metal.parte(NEGRO, Mg) as bm:
        B.tubo(bm, [j1, j2], 0.0085, seg=8)
        B.tubo(bm, [j2, j3], 0.0085, seg=8)
        _articulacion(bm, j1, 0.019, 0.031, ranuras=1, seg=13)
        _articulacion(bm, j2, 0.019, 0.031, ranuras=1, seg=13)
        _articulacion(bm, j3, 0.016, 0.026, ranuras=1)
        _perilla(bm, j1, 0.0155)
        _perilla(bm, j2, 0.0155)
    # pantalla: su tope del cuello en el origen local, colgando de la articulación j3 e inclinada hacia −Y
    z_j = 0.012 + 0.016
    Msh = Mg @ Matrix.Translation(j3) @ Matrix.Rotation(math.radians(-inclinacion), 4, "X") @ \
        Matrix.Translation((0.0, 0.0, -z_j))
    with metal.parte(NEGRO, Msh) as bm:
        B.tubo(bm, [(0.0, 0.0, -0.002), (0.0, 0.0, z_j)], 0.0065, seg=8)           # vástago de la pantalla
    Mps = Msh @ Matrix.Translation((0.0, 0.0, -0.0012))                            # bajo la tapa del cuello
    with metal.parte(NEGRO, Mps) as bm:
        z_c = _portalampara(bm, "simple", seg=10)
    with pant.parte(None, Msh):
        _pantalla(pant, diametro / 2, 0.125, r_cuello=0.020, alto_cuello=0.035, t=0.0012, seg=24, n_campana=5,
                  n_interior=2, rb=0.0018, angulos_labio=(-35, 90, 215))
    _ampolleta(vid, fil, cas, Mps @ Matrix.Translation((0, 0, z_c)), forma, seg=10, n_vidrio=6, seg_casquillo=6,
               rosca=False, soportes=False, guias=False, tallo=False)
    mallas = (metal, pant, vid, fil, cas)
    lo, _ = _caja_mallas(mallas)
    for m in mallas:
        m.trasladar((0.0, 0.0, -lo.z))
    props = {"placa_centro_z": round(-lo.z, 4)}
    objs = [metal.crear(col, f"{prefijo}_Metal", angulo=50, props=props), pant.crear(col, f"{prefijo}_Pantalla"),
            vid.crear(col, f"{prefijo}_Vidrio"), fil.crear(col, f"{prefijo}_Filamento", angulo=60),
            cas.crear(col, f"{prefijo}_Casquillo", angulo=40)]
    return [o for o in objs if o]


# ================================================================ conducto eléctrico visto
CONDUCTO_CAJA = dict(radio=0.040, fondo=0.046, boca=0.012)   # diseño: caja de derivación redonda de fundición


def conducto(col, prefijo, puntos=((-0.45, -0.014, 0.10), (0.25, -0.014, 0.10), (0.25, -0.014, 0.65),
                                   (0.25, -0.014, 1.15), (0.70, -0.014, 1.15)),
             cajas=(0, 2), normal_muro=(0.0, 1.0, 0.0), radio=0.010, radio_curva=0.05, paso_abrazaderas=0.8,
             material=NEGRO, ramales=None):
    """Tubo metálico de Ø 20 mm por el eje `puntos` (locales, se usan tal cual), con curvas de radio `radio_curva`,
    cajas de derivación redondas de fundición (Ø 0,08 × 0,046, tapa con buña y dos tornillos, bocas roscadas
    donde entra el tubo) en los índices de `cajas`, abrazaderas omega sobre el muro cada `paso_abrazaderas` y
    copla en los extremos libres. `normal_muro` apunta del tubo al muro; el eje queda a radio + 4 mm del muro
    (por defecto el muro está en y = 0). `ramales` = {índice de caja: (puntos,)}: bocas extra de esa caja hacia
    otros conductos (derivación en T; el otro conducto termina en la boca, a radio + boca del centro de la caja).
    ≤ 300 triángulos por tramo."""
    P = [Vector(p) for p in puntos]
    nm = Vector(normal_muro).normalized()
    sep = radio + 0.004                                  # eje del tubo al muro (abrazadera con separador)
    cajas = sorted({i % len(P) for i in cajas})
    RB, DB, LB = CONDUCTO_CAJA["radio"], CONDUCTO_CAJA["fondo"], CONDUCTO_CAJA["boca"]   # caja (diseño)
    ramales = {i % len(P): [Vector(q) for q in qs] for i, qs in (ramales or {}).items()}
    rh = radio + 0.0035
    m = _Malla()

    def en_plano(v):
        return (v - nm * v.dot(nm)).normalized()

    cortes = sorted(set([0, len(P) - 1] + cajas))
    with m.parte(material) as bm:
        for a, b in zip(cortes[:-1], cortes[1:]):
            pts = [p.copy() for p in P[a:b + 1]]
            libres = []
            if a in cajas:
                pts[0] = pts[0] + (pts[1] - pts[0]).normalized() * (RB + LB - 0.006)
            else:
                libres.append((P[a], (P[a] - P[a + 1]).normalized()))
                pts[0] = pts[0] + (pts[1] - pts[0]).normalized() * 0.004
            if b in cajas:
                pts[-1] = pts[-1] + (pts[-2] - pts[-1]).normalized() * (RB + LB - 0.006)
            else:
                libres.append((P[b], (P[b] - P[b - 1]).normalized()))
                pts[-1] = pts[-1] + (pts[-2] - pts[-1]).normalized() * 0.004
            B.tubo(bm, B._redondear_polilinea(pts, radio_curva, pasos=4), radio, seg=10)
            for p_fin, d in libres:                      # copla en el extremo libre
                _torno_eje(bm, [(0.0, 0.0), (radio + 0.0025, 0.0), (radio + 0.0025, 0.022), (0.0, 0.022)],
                           p_fin - d * 0.022, d, 12)
            # abrazaderas en los tramos rectos paralelos al muro
            tl = [0.0] * len(pts)
            for i in range(1, len(pts) - 1):
                ang = (pts[i] - pts[i - 1]).angle(pts[i + 1] - pts[i])
                tl[i] = radio_curva * math.tan(ang / 2)
            for i in range(len(pts) - 1):
                seg_v = pts[i + 1] - pts[i]
                L = seg_v.length
                d = seg_v.normalized()
                if abs(d.dot(nm)) > 0.3:
                    continue
                s0 = tl[i] + (0.03 if i == 0 else 0.02)
                s1 = L - tl[i + 1] - (0.03 if i == len(pts) - 2 else 0.02)
                if s1 - s0 < 0.12:
                    continue
                k = max(1, round((s1 - s0) / paso_abrazaderas))
                for j in range(k):
                    q = pts[i] + d * (s0 + (s1 - s0) * (j + 0.5) / k)
                    s = d.cross(nm).normalized()
                    e, rho, pie = 0.0015, radio + 0.0015 / 2 + 0.0002, 0.011
                    wc = sep - e / 2
                    arco = [q + (s * math.cos(math.radians(f)) - nm * math.sin(math.radians(f))) * rho
                            for f in (0, 60, 120, 180)]
                    camino = ([q + s * (rho + pie) + nm * wc, q + s * rho + nm * wc] + arco
                              + [q - s * rho + nm * wc, q - s * (rho + pie) + nm * wc])
                    _cinta(bm, camino, d, 0.012, e)
        for i in cajas:                                   # cajas de derivación
            vecinos = [P[j] for j in (i - 1, i + 1) if 0 <= j < len(P)]
            u = en_plano(vecinos[0] - P[i])
            w = -nm
            v = w.cross(u)
            R3 = Matrix((u, v, w)).transposed()
            Mc = Matrix.Translation(P[i] + nm * sep) @ R3.to_4x4()
            antes = set(bm.verts)
            _torno(bm, [(0.0, 0.0), (RB, 0.0), (RB, DB - 0.0072), (RB - 0.0012, DB - 0.006),
                        (RB + 0.0006, DB - 0.0052), (RB - 0.0024, DB), (0.0, DB + 0.0008)], 20)
            for x in (-(RB - 0.011), RB - 0.011):          # tornillos hexagonales de la tapa
                B.cilindro(bm, x, 0.0, DB - 0.0005, DB + 0.0022, 0.0032, seg=6)
            for q in vecinos + ramales.get(i, []):       # bocas donde entra el tubo
                e_loc = R3.transposed() @ en_plano(q - P[i])
                c0 = e_loc * (RB - 0.004) + Vector((0, 0, sep))
                c1 = e_loc * (RB + LB) + Vector((0, 0, sep))
                B.tubo(bm, [c0, c1], rh, seg=10)
            bmesh.ops.transform(bm, matrix=Mc, verts=[vv for vv in bm.verts if vv not in antes])
    return [m.crear(col, f"{prefijo}_Tubo", angulo=40)]


# ================================================================ libros
def _libro(tapas, hojas, M, w, h, d, dura, i_tapa, i_etiqueta, etiqueta_z):
    """Libro de pie en coordenadas propias (grosor en X centrado, lomo en y = 0 hacia −Y, canto de hojas en
    y = d, de z = 0 a h), transformado por M. Tapa dura: cartón de 2,4 mm con ceja de 3 mm, lomo redondeado y
    ranura de bisagra; rústica: tapa de 0,8 mm, lomo casi plano."""
    hw = w / 2
    fs = (math.pi, 0.75 * math.pi, 0.5 * math.pi, 0.25 * math.pi, 0.0)
    if dura:
        tb, ceja, bul = 0.0024, 0.003, 0.18 * w
        yg = bul + 0.006
        izq = [(-hw, d), (-hw, yg + 0.004), (-hw + 0.0007, yg + 0.002), (-hw, yg)]
        der = [(hw, yg), (hw - 0.0007, yg + 0.002), (hw, yg + 0.004), (hw, d)]
    else:
        tb, ceja, bul = 0.0008, 0.0, 0.03 * w
        izq, der = [(-hw, d)], [(hw, d)]
    lomo_ext = [(hw * math.cos(f), bul * (1 - math.sin(f))) for f in fs]
    lomo_int = [((hw - tb) * math.cos(f), bul + tb - bul * math.sin(f)) for f in reversed(fs)]
    contorno = izq + lomo_ext + der + [(hw - tb, d)] + lomo_int + [(-hw + tb, d)]
    with tapas.parte(None, M) as bm:
        antes = set(bm.faces)
        _extruir(bm, contorno, 0.0, h)
        if i_etiqueta is not None:                        # banda impresa en el lomo, 0,3 mm en relieve
            z1, z2 = etiqueta_z
            fuera = [((hw + 0.0003) * math.cos(f), bul - (bul + 0.0003) * math.sin(f)) for f in fs]
            dentro = [((hw - 0.0006) * math.cos(f), bul - (bul - 0.0006) * math.sin(f)) for f in reversed(fs)]
            antes_e = set(bm.faces)
            _extruir(bm, fuera + dentro, z1 * h, z2 * h)
            for f in bm.faces:
                if f not in antes_e:
                    f.material_index = i_etiqueta
            antes |= {f for f in bm.faces if f not in antes_e}   # no pisar el material de la banda
        for f in bm.faces:
            if f not in antes:
                f.material_index = i_tapa
    cl = 0.0003
    xi = hw - tb - cl
    lomo_h = [(xi * math.cos(f), bul + tb + cl - bul * math.sin(f)) for f in fs]
    yf = d - ceja - cl
    canto = [(xi, yf), (0.0, yf - 0.6 * bul), (-xi, yf)] if dura else [(xi, yf), (-xi, yf)]
    with hojas.parte(PAPEL, M) as bm:
        _extruir(bm, lomo_h + canto, ceja + cl, h - ceja - cl)


def libros(col, prefijo, n=8, apilados=False, semilla=7, inclinar_ultimo=False):
    """Hilera de `n` libros de pie a lo largo de +X (lomos hacia −Y, alineados al frente) o, con apilados=True, una
    pila con los más grandes abajo. Lomos de 2 a 5 cm, alto de 0,20 a 0,28, fondo de 0,66 a 0,76 del alto; 70 %
    tapa dura; cinco colores de tapa sin repetir el vecino; algunas bandas impresas en el lomo. inclinar_ultimo:
    el último de la hilera se apoya en el anterior a 14°. Semilla fija por parámetro. ≤ 150 triángulos por
    libro."""
    rng = random.Random(semilla)
    tapas, hojas = _Malla(), _Malla()
    it = [tapas.indice(mt) for mt in LIBROS]
    ip = tapas.indice(PAPEL)
    orden = []                                   # los cinco colores rotan sin repetir vecino
    while len(orden) < n:
        bloque = list(range(5))
        rng.shuffle(bloque)
        if orden and bloque[0] == orden[-1]:
            bloque.reverse()
        orden += bloque
    datos = []
    for c in orden[:n]:
        w, h = rng.uniform(0.02, 0.05), rng.uniform(0.20, 0.28)
        d = h * rng.uniform(0.66, 0.76)
        dura = rng.random() < 0.7
        etq = None
        if rng.random() < 0.45:
            etq = (ip if rng.random() < 0.5 else it[rng.choice([k for k in range(5) if k != c])],
                   rng.choice(((0.78, 0.86), (0.12, 0.18), (0.62, 0.74))))
        datos.append((w, h, d, dura, it[c], etq))
    if apilados:
        datos.sort(key=lambda t: -(t[1] * t[2]))
        z = 0.0
        for w, h, d, dura, ic, etq in datos:
            ry = Matrix.Rotation(math.radians(-90), 4, "Y")                 # acostado: grosor en Z, alto en X
            M = (Matrix.Translation((rng.uniform(-0.012, 0.012), 0.0, z + w / 2))
                 @ Matrix.Rotation(math.radians(rng.uniform(-5, 5)), 4, "Z")
                 @ Matrix.Translation((h / 2, -d / 2, 0.0)) @ ry)
            _libro(tapas, hojas, M, w, h, d, dura, ic, *(etq if etq else (None, None)))
            z += w
    else:
        y0 = -max(t[2] for t in datos) / 2                                   # lomos alineados al frente
        x, h_prev, x_der = 0.0, None, 0.0
        for k, (w, h, d, dura, ic, etq) in enumerate(datos):
            if inclinar_ultimo and k == len(datos) - 1 and k > 0:
                th = math.radians(14)
                g = h_prev * math.tan(th) if h_prev / math.cos(th) <= h else h * math.sin(th)
                piv = x_der + g
                M = (Matrix.Translation((piv, y0, 0.0)) @ Matrix.Rotation(-th, 4, "Y")
                     @ Matrix.Translation((w / 2, 0.0, 0.0)))
            else:
                M = Matrix.Translation((x + w / 2, y0, 0.0))
            _libro(tapas, hojas, M, w, h, d, dura, ic, *(etq if etq else (None, None)))
            x_der = x + w
            x += w + rng.uniform(0.0005, 0.003)
            h_prev = h
    lo, hi = _caja_mallas((tapas, hojas))
    for m in (tapas, hojas):
        m.trasladar((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
    objs = [tapas.crear(col, f"{prefijo}_Tapas", angulo=50), hojas.crear(col, f"{prefijo}_Hojas", angulo=40)]
    return [o for o in objs if o]


# ================================================================ cerámica de gres
def _vasija(m, ctrl, espesor, fondo, n_ext, esmalte, crudo, alto_crudo, semilla, amp=0.004, ondula=0.0012,
            curvatura=0.2, hueco_hasta=None, tope=1500, seg_max=36):
    """Pieza de gres por torno en la malla m: pie con rebaje, pared de espesor real (paralela a cada muestra de la
    cara exterior, así la cara interior nunca cruza la exterior en cuellos cóncavos), fondo interior plano, labio
    redondeado, esmalte con pie crudo y una leve irregularidad de torno (ovalización y borde ondulado) con semilla
    fija. ctrl: control (r, z) de la cara exterior desde el canto del pie hasta el borde. hueco_hasta: en piezas
    de boca angosta, cota bajo la cual la cavidad no se modela (no se ve por la boca). El número de lados del
    torno se elige para no pasar `tope` triángulos."""
    densa = _spline(ctrl, 14)
    ext = _remuestrear(densa, n_ext, curvatura)
    for i in range(len(ext) - 1):                          # anillo justo en la línea del esmalte
        if ext[i][1] < alto_crudo < ext[i + 1][1]:
            f = (alto_crudo - ext[i][1]) / (ext[i + 1][1] - ext[i][1])
            ext.insert(i + 1, tuple(Vector(ext[i]).lerp(Vector(ext[i + 1]), f)))
            break
    z_min = fondo + 0.004 if hueco_hasta is None else hueco_hasta
    inter = [q for q in _paralela(ext, espesor) if q[1] > z_min]
    z_piso = fondo if hueco_hasta is None else inter[0][1] - 0.006
    tang = Vector(ext[-1]) - Vector(ext[-2])
    lab = _labio(ext[-1], inter[-1], tang, espesor / 2, (60, 120))
    r_pie = ctrl[0][0]
    pie = [(0.0, 0.003), (r_pie - 0.006, 0.003), (r_pie - 0.0045, 0.0)]
    piso = [(max(inter[0][0] - 0.004, 0.002), z_piso), (0.0, z_piso)]
    perfil = pie + ext + lab + list(reversed(inter)) + piso
    seg = min(seg_max, tope // (2 * (len(perfil) - 2)))
    seg -= seg % 2
    ie, ic = m.indice(esmalte), m.indice(crudo)
    n_afuera = len(pie) + len(ext) - 1
    idx = [ic if (k < n_afuera and max(perfil[k][1], perfil[k + 1][1]) <= alto_crudo + 1e-9) else ie
           for k in range(len(perfil))]
    with m.parte(None) as bm:
        antes = set(bm.verts)
        _torno(bm, perfil, seg, cerrado=True, indices=idx)
        rng = random.Random(semilla)
        f1, f2, f3 = (rng.uniform(0, TAU) for _ in range(3))
        alto = ctrl[-1][1]
        for v in bm.verts:
            if v in antes:
                continue
            r = math.hypot(v.co.x, v.co.y)
            if r < 1e-7:
                continue
            a = math.atan2(v.co.y, v.co.x)
            hz = max(0.0, v.co.z / alto)
            k = 1 + amp * (0.6 * math.sin(2 * a + f1) + 0.4 * math.sin(3 * a + f2)) * (0.3 + 0.7 * hz)
            v.co.x *= k
            v.co.y *= k
            v.co.z += ondula * math.sin(2 * a + f3) * max(0.0, hz - 0.85) / 0.15
    return seg


_JARRONES = {
    # 0: botella de cuello angosto, esmalte negro mate (Ø 0,15 × 0,30)
    0: dict(material=GRES_NEGRO, espesor=0.0055, fondo=0.012, n_ext=15, hueco=0.19,
            ctrl=[(0.046, 0.0018), (0.060, 0.014), (0.072, 0.050), (0.075, 0.100), (0.070, 0.150), (0.054, 0.196),
                  (0.031, 0.229), (0.0205, 0.252), (0.0190, 0.276), (0.0212, 0.295), (0.0222, 0.300)]),
    # 1: globo «luna» de boca corta, gres arena (Ø 0,21 × 0,22)
    1: dict(material=GRES_ARENA, espesor=0.006, fondo=0.012, n_ext=14, hueco=0.15,
            ctrl=[(0.050, 0.0018), (0.075, 0.016), (0.097, 0.055), (0.105, 0.100), (0.098, 0.145), (0.075, 0.186),
                  (0.045, 0.206), (0.033, 0.212), (0.0315, 0.217), (0.033, 0.221)]),
    # 2: cilindro alto de boca abierta con cintura suave, esmalte blanco (Ø 0,12 × 0,27)
    2: dict(material=GRES_BLANCO, espesor=0.006, fondo=0.012, n_ext=10, hueco=None,
            ctrl=[(0.049, 0.0018), (0.055, 0.010), (0.057, 0.040), (0.0555, 0.120), (0.057, 0.200),
                  (0.060, 0.250), (0.061, 0.270)]),
}


def jarron(col, prefijo, variante=0, material=None, pie_crudo=True, semilla=None):
    """Jarrón de gres por torno: variante 0 botella negra (Ø 0,15 × 0,30), 1 globo arena (Ø 0,21 × 0,22), 2
    cilindro blanco (Ø 0,12 × 0,27). Pared con espesor, pie crudo de 8 mm (arena) salvo pie_crudo=False. En
    las variantes de boca angosta (0 y 1) la cavidad se modela hasta el hombro, que es lo que se ve por la boca.
    ≤ 1 500 triángulos."""
    J = _JARRONES[variante]
    esm = material or J["material"]
    m = _Malla()
    _vasija(m, J["ctrl"], J["espesor"], J["fondo"], J["n_ext"], esm, GRES_ARENA if pie_crudo else esm, 0.008,
            11 + variante if semilla is None else semilla, hueco_hasta=J["hueco"])
    return [m.crear(col, f"{prefijo}_Gres", angulo=40)]


def bol(col, prefijo, diametro=0.24, alto=0.09, material=GRES_NEGRO, pie_crudo=True, semilla=5):
    """Bol de gres por torno (Ø 0,24 × 0,09 por defecto), esmalte negro con pie crudo, pared de 6 mm, fondo
    interior plano y labio redondeado. ≤ 1 500 triángulos."""
    sx, sz = diametro / 0.24, alto / 0.09
    ctrl = [(0.046, 0.0018), (0.056, 0.007), (0.080, 0.022), (0.102, 0.045), (0.115, 0.068), (0.120, 0.090)]
    ctrl = [(ctrl[0][0] * sx, ctrl[0][1])] + [(r * sx, z * sz) for r, z in ctrl[1:]]
    m = _Malla()
    _vasija(m, ctrl, 0.006, 0.010, 9, material, GRES_ARENA if pie_crudo else material, 0.007, semilla,
            amp=0.003, ondula=0.0010)
    return [m.crear(col, f"{prefijo}_Gres", angulo=40)]


# ================================================================ reloj de pared
def reloj_pared(col, prefijo, diametro=0.40, hora=(10, 10, 36), cristal=True):
    """Reloj mural industrial: caja de chapa negra de Ø `diametro` × 0,048 con aro de frente enrollado, esfera
    clara hundida 16 mm, doce índices en barra (los cardinales más gruesos), minutero impreso, agujas de bastón,
    segundero con contrapeso, tapa central y cristal. Muro en y = 0, frente hacia −Y, centro en z = radio.
    ≤ 1 500 triángulos."""
    R, D = diametro / 2, 0.048
    wd = D - 0.016                                           # plano de la esfera
    M = Matrix.Translation((0.0, 0.0, R)) @ Matrix.Rotation(math.radians(90), 4, "X")   # w local -> −Y
    caja, marcas, vid = _Malla(), _Malla(), _Malla()
    perfil = [(0.0, 0.0), (R - 0.005, 0.0), (R, 0.005), (R, D - 0.012), (R - 0.0035, D - 0.0035),
              (R - 0.012, D), (R - 0.016, D), (R - 0.019, D - 0.003), (R - 0.019, wd), (0.0, wd)]
    ine, ipa = caja.indice(NEGRO), caja.indice(PAPEL)
    idx = [ine] * (len(perfil) - 2) + [ipa]
    with caja.parte(None, M) as bm:
        _torno(bm, perfil, 48, indices=idx)
    r_o = R - 0.025                                          # borde exterior de los índices

    def polar(largo, ancho_, a):
        u = Vector((math.sin(a), math.cos(a)))
        p = Vector((-math.cos(a), math.sin(a)))
        return [tuple(u * s + p * t) for s, t in largo_ancho(largo, ancho_)]

    def largo_ancho(largo, ancho_):
        (s0, s1), (t0, t1) = largo, ancho_
        return [(s0, t0), (s1, t0), (s1, t1), (s0, t1)]

    with marcas.parte(NEGRO, M) as bm:
        for k in range(12):                                  # índices de hora
            a = TAU * k / 12
            L, W = (0.030, 0.0075) if k % 3 == 0 else (0.020, 0.0035)
            _extruir(bm, polar((r_o - L, r_o), (-W / 2, W / 2), a), wd - 0.0002, wd + 0.0007)
        for k in range(60):                                  # minutero impreso
            if k % 5 == 0:
                continue
            a = TAU * k / 60
            q = polar((r_o - 0.008, r_o), (-0.0006, 0.0006), a)
            if _area(q) < 0:
                q = list(reversed(q))
            bm.faces.new([bm.verts.new((x, y, wd + 0.00025)) for x, y in q])
        hh, mm, ss = hora
        a_h = TAU * ((hh % 12) + mm / 60 + ss / 3600) / 12
        a_m = TAU * (mm + ss / 60) / 60
        a_s = TAU * ss / 60
        for a, cola, largo, w0, w1, z0 in ((a_h, 0.020, R * 0.46, 0.0042, 0.0030, 0.0012),
                                           (a_m, 0.024, R * 0.75, 0.0034, 0.0022, 0.0024),
                                           (a_s, 0.045, R * 0.79, 0.0008, 0.0006, 0.0036)):
            u = Vector((math.sin(a), math.cos(a)))
            p = Vector((-math.cos(a), math.sin(a)))
            pol = [tuple(u * s + p * t) for s, t in ((-cola, -w0), (largo, -w1), (largo, w1), (-cola, w0))]
            _extruir(bm, pol, wd + z0, wd + z0 + (0.0004 if w0 < 0.001 else 0.0008))
        u = Vector((math.sin(a_s), math.cos(a_s)))
        c = -u * 0.034                                       # contrapeso del segundero
        _extruir(bm, [tuple(c + Vector((math.cos(TAU * i / 10), math.sin(TAU * i / 10))) * 0.0055)
                      for i in range(10)], wd + 0.0036, wd + 0.0040)
        _torno(bm, [(0.0, wd + 0.0008), (0.0065, wd + 0.0008), (0.0065, wd + 0.0042), (0.0050, wd + 0.0052),
                    (0.0, wd + 0.0054)], 16)                 # tapa central
    if cristal:
        with vid.parte(VIDRIO_RELOJ, M) as bm:
            _torno(bm, [(0.0, D - 0.0055), (R - 0.0192, D - 0.0055), (R - 0.0192, D - 0.0035), (0.0, D - 0.0035)],
                   48)
    objs = [caja.crear(col, f"{prefijo}_Caja", angulo=50), marcas.crear(col, f"{prefijo}_Marcas", recalc=False),
            vid.crear(col, f"{prefijo}_Cristal")]
    return [o for o in objs if o]


# ================================================================ interruptor de muro (fase 07b)
TECLA = LATON            # teclas de latón envejecido: contrastan con la placa negra y el visor las ve girar
INTERRUPTOR = dict(ancho=0.08, alto=0.12, espesor=0.012,     # contrato de interacción, sección 3 (encargo 07b)
                   r_canto=0.0025, tornillo_z=0.047,           # diseño: canto redondeado y tornillos de la placa
                   tecla_alto=0.056, tecla_saliente=0.008,     # diseño: balancín de interruptor de tecla estándar
                   tecla_ancho_1=0.034, tecla_ancho_2=0.026, tecla_sep=0.006,   # diseño: placa simple y doble
                   tecla_hundida=0.0045,     # espalda de la tecla dentro de la placa: ≥ (alto/2)·sen 8° = 3,9 mm
                                             # para que al inclinarse ±8° no quede rendija (corrección 07b)
                   caja_ancho=0.085, caja_alto=0.125)          # diseño: caja de superficie de acero (conducto visto)


def interruptor(col, nombre, n_teclas=1, caja=0.0):
    """Placa de interruptor de muro de acero negro mate con dos tornillos pavonados y `n_teclas` teclas de balancín
    de latón envejecido (1 o 2), estilo industrial. Mural: espalda en y = 0, frente hacia −Y, centro de la placa en el
    origen (x = z = 0). Cada tecla es un objeto hijo de la placa, sin giro propio y con el origen en su eje de
    giro (horizontal, paralelo al muro, a la altura del centro de la tecla y sobre la cara de la placa): el visor
    la inclina ±8° girándola en su X local. Nombres: la placa `nombre`; las teclas `nombre`_Tecla (una) o
    `nombre`_1_Tecla y `nombre`_2_Tecla (izquierda y derecha mirando la placa). `caja` > 0: la placa va sobre una
    caja de superficie de ese fondo (m), parte de la misma malla, y placa y teclas avanzan lo mismo (la espalda de la
    caja queda en y = 0). ≤ 320 triángulos."""
    I = INTERRUPTOR
    a, h, e = I["ancho"] / 2, I["alto"] / 2, I["espesor"]
    placa = _Malla()
    with placa.parte(NEGRO, suave=True) as bm:
        if caja > 0:
            ca, ch = I["caja_ancho"] / 2, I["caja_alto"] / 2
            B.caja_redondeada(bm, -ca, ca, -caja, 0.0, -ch, ch, 0.004, segmentos=1)
        B.caja_redondeada(bm, -a, a, -caja - e, -caja, -h, h, I["r_canto"], segmentos=1)
    with placa.parte(NEGRO, suave=True) as bm:              # tornillos pavonados (un solo material: 1 llamada de dibujo)
        for z in (-I["tornillo_z"], I["tornillo_z"]):
            _torno_eje(bm, [(0.0, 0.0), (0.0032, 0.0), (0.0027, 0.0010), (0.0, 0.0015)], (0.0, -caja - e, z),
                       (0, -1, 0), 8)
    ob_placa = placa.crear(col, nombre, angulo=50)
    ancho_t = I["tecla_ancho_1"] if n_teclas == 1 else I["tecla_ancho_2"]
    xs = [0.0] if n_teclas == 1 else [-(ancho_t + I["tecla_sep"]) / 2, (ancho_t + I["tecla_sep"]) / 2]
    teclas = []
    for i, xc in enumerate(xs):
        t = _Malla()
        with t.parte(TECLA, suave=True) as bm:
            # balancín: perfil (y, z) con una arista suave al centro (el frente baja 1,5 mm hacia arriba y abajo),
            # extruido a lo ancho; la espalda entra tecla_hundida en la placa para que no quede luz al inclinarse
            sa, ht, hu = I["tecla_saliente"], I["tecla_alto"] / 2, I["tecla_hundida"]
            perfil = [(hu, -ht), (-(sa - 0.0015), -ht), (-(sa - 0.0005), -ht * 0.55), (-sa, 0.0),
                      (-(sa - 0.0005), ht * 0.55), (-(sa - 0.0015), ht), (hu, ht)]
            izq = [bm.verts.new((-ancho_t / 2, y, z)) for y, z in perfil]
            der = [bm.verts.new((ancho_t / 2, y, z)) for y, z in perfil]
            bm.faces.new(izq)
            bm.faces.new(list(reversed(der)))
            n = len(perfil)
            for k in range(n):
                j = (k + 1) % n
                bm.faces.new((izq[k], der[k], der[j], izq[j]))
        nt = f"{nombre}_Tecla" if n_teclas == 1 else f"{nombre}_{i + 1}_Tecla"
        ob = t.crear(col, nt, angulo=50)
        ob.parent = ob_placa
        ob.location = (xc, -caja - e, 0.0)               # eje de giro: sobre la cara de la placa
        teclas.append(ob)
    return [ob_placa] + teclas
