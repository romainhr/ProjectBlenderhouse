"""Utilidades de geometría y materiales para las fases 2 en adelante del activo Depto (bpy 3.6).

Convención: las piezas se definen en px del plano (x, y) y metros en z, y se convierten con
depto_plano.a_blender. Todo es ortogonal a los ejes del plano, así que casi todo son cajas.
Cada malla lleva UV por proyección de caja en metros de mundo (1 unidad UV = 1 m), para que la fase 5
aplique texturas a escala real (dimensiones_mm del manifiesto de texturas) y el GLB las transporte.
Los materiales se crean o reutilizan por nombre (Depto_Mat_*): cada fase los deja en una versión
simple de color plano y la fase 5 los mejora en el mismo datablock, sin reasignar nada.
"""
import math

import bmesh
import bpy

import depto_plano as P

S = P.M_POR_PX


def px(m):
    """Metros -> px del plano."""
    return m / S


def rect_bl(x0, x1, y0, y1):
    """Rectángulo del plano (px) -> (Xmin, Xmax, Ymin, Ymax) en Blender (m)."""
    a = P.a_blender(x0, y0)
    b = P.a_blender(x1, y1)
    return min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1])


def caja(bm, x0, x1, y0, y1, z0, z1):
    """Caja alineada a los ejes: x/y en px del plano, z en m."""
    X0, X1, Y0, Y1 = rect_bl(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))
    z0, z1 = min(z0, z1), max(z0, z1)
    v = [bm.verts.new(c) for c in ((X0, Y0, z0), (X1, Y0, z0), (X1, Y1, z0), (X0, Y1, z0),
                                   (X0, Y0, z1), (X1, Y0, z1), (X1, Y1, z1), (X0, Y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([v[i] for i in f])


def caja_con_hueco(bm, x0, x1, y0, y1, z0, z1, hueco, z_hueco):
    """Caja con un hueco rectangular (hx0, hx1, hy0, hy1 en px) abierto desde z_hueco hasta z1.

    Se arma con una caja inferior (si z_hueco > z0) y cuatro franjas alrededor del hueco: sin booleanos.
    """
    hx0, hx1, hy0, hy1 = hueco
    assert x0 < hx0 < hx1 < x1 and y0 < hy0 < hy1 < y1, f"hueco fuera de la caja: {hueco} en {(x0, x1, y0, y1)}"
    if z_hueco > z0 + 1e-9:
        caja(bm, x0, x1, y0, y1, z0, z_hueco)
    caja(bm, x0, hx0, y0, y1, z_hueco, z1)
    caja(bm, hx1, x1, y0, y1, z_hueco, z1)
    caja(bm, hx0, hx1, y0, hy0, z_hueco, z1)
    caja(bm, hx0, hx1, hy1, y1, z_hueco, z1)


def _anillo(bm, cx, cy, rx, ry, z, seg):
    out = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        X, Y = P.a_blender(cx + rx * math.cos(a), cy + ry * math.sin(a))
        out.append(bm.verts.new((X, Y, z)))
    return out


def cilindro(bm, cx, cy, rx, ry, z0, z1, seg=24):
    """Cilindro elíptico vertical: centro y radios en px del plano, z en m. Laterales suaves."""
    bot, top = _anillo(bm, cx, cy, rx, ry, z0, seg), _anillo(bm, cx, cy, rx, ry, z1, seg)
    # a_blender invierte el sentido de giro respecto de (x, y) en px (determinante -1): el anillo queda en
    # sentido horario visto desde +Z. Así la tapa inferior mira a -Z y los laterales se arman al revés
    # que en un anillo antihorario. recalc_face_normals (en Pieza.crear) lo confirma en mallas cerradas.
    bm.faces.new(bot)
    bm.faces.new(list(reversed(top)))
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((bot[j], bot[i], top[i], top[j])).smooth = True


def cuenco(bm, cx, cy, rx, ry, z0, z1, pared, fondo, seg=24):
    """Cuenco elíptico de apoyo (lavamanos sobre cubierta): exterior de z0 a z1, pared y fondo en m."""
    ix, iy = rx - px(pared), ry - px(pared)
    zi = z0 + fondo
    ob, ot = _anillo(bm, cx, cy, rx, ry, z0, seg), _anillo(bm, cx, cy, rx, ry, z1, seg)
    it, ib = _anillo(bm, cx, cy, ix, iy, z1, seg), _anillo(bm, cx, cy, ix, iy, zi, seg)
    bm.faces.new(ob)                                   # base exterior (-Z)
    bm.faces.new(list(reversed(ib)))                   # fondo interior (+Z)
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((ob[j], ob[i], ot[i], ot[j])).smooth = True     # pared exterior
        bm.faces.new((ot[j], ot[i], it[i], it[j]))                   # borde superior
        bm.faces.new((it[j], it[i], ib[i], ib[j])).smooth = True     # pared interior


def uv_mundo(bm):
    """UV por proyección de caja en metros de mundo, según el eje dominante de la normal de cada cara."""
    bm.normal_update()
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        eje = max(range(3), key=lambda k: abs(n[k]))
        for lp in f.loops:
            c = lp.vert.co
            lp[uv].uv = (c.x, c.y) if eje == 2 else ((c.y, c.z) if eje == 0 else (c.x, c.z))


# ---------------------------------------------------------------------------
# Materiales base (color sRGB, rugosidad, metálico, alfa). La fase 5 los reemplaza por PBR con textura.
# ---------------------------------------------------------------------------
MATERIALES = {
    "Depto_Mat_MarcoVentana": ((0.90, 0.90, 0.90), 0.35, 0.3, 1.0),   # aluminio o PVC blanco (supuesto)
    "Depto_Mat_Vidrio": ((0.80, 0.90, 0.95), 0.02, 0.0, 0.18),
    "Depto_Mat_VidrioEsmerilado": ((0.90, 0.93, 0.95), 0.35, 0.0, 0.55),
    "Depto_Mat_Pasamanos": ((0.55, 0.56, 0.58), 0.30, 1.0, 1.0),      # acero inoxidable
    "Depto_Mat_MarcoPuerta": ((0.93, 0.93, 0.91), 0.45, 0.0, 1.0),    # marco pintado blanco
    "Depto_Mat_PuertaMadera": ((0.72, 0.55, 0.36), 0.50, 0.0, 1.0),   # enchapado de roble (fase 5: oak_veneer_01)
    "Depto_Mat_PuertaEntrada": ((0.36, 0.26, 0.18), 0.45, 0.0, 1.0),  # hoja de acceso más oscura (supuesto)
    "Depto_Mat_Manilla": ((0.70, 0.70, 0.72), 0.25, 1.0, 1.0),
    "Depto_Mat_MuebleBlanco": ((0.94, 0.94, 0.92), 0.35, 0.0, 1.0),   # cocina y closets melamina blanca (supuesto)
    "Depto_Mat_Zocalo": ((0.30, 0.30, 0.30), 0.60, 0.0, 1.0),
    "Depto_Mat_Granito": ((0.45, 0.45, 0.46), 0.30, 0.0, 1.0),        # cubierta gris (fase 5: procedural)
    "Depto_Mat_Acero": ((0.72, 0.72, 0.74), 0.30, 1.0, 1.0),
    "Depto_Mat_VidrioNegro": ((0.03, 0.03, 0.035), 0.08, 0.0, 1.0),   # anafe vitrocerámico y frente de horno
    "Depto_Mat_Ceramica": ((0.96, 0.96, 0.96), 0.12, 0.0, 1.0),       # loza sanitaria
    "Depto_Mat_Espejo": ((0.90, 0.92, 0.93), 0.02, 1.0, 1.0),
    "Depto_Mat_CubiertaBano": ((0.85, 0.80, 0.72), 0.25, 0.0, 1.0),   # cubierta de vanitorio (supuesto)
    "Depto_Mat_Electro": ((0.85, 0.85, 0.86), 0.35, 0.2, 1.0),        # lavadora
    "Depto_Mat_Palier": ((0.82, 0.81, 0.78), 0.70, 0.0, 1.0),         # muros y piso neutros del palier
    "Depto_Mat_PalierPiso": ((0.55, 0.54, 0.52), 0.60, 0.0, 1.0),
    "Depto_Mat_Yeso": ((0.95, 0.95, 0.94), 0.85, 0.0, 1.0),           # ducto y cielo falso pintados (como el cielo)
    # Acabados de muros, pisos y cielos (fase 2 los asigna por cara según el recinto; fase 5 les pone textura)
    "Depto_Mat_MuroPintado": ((0.90, 0.90, 0.88), 0.85, 0.0, 1.0),    # látex blanco (fase 5: white_plaster_02)
    "Depto_Mat_MuroBano": ((0.93, 0.94, 0.94), 0.25, 0.0, 1.0),       # cerámica blanca (fase 5: relieve de tiled_floor_001)
    "Depto_Mat_MuroExterior": ((0.80, 0.79, 0.76), 0.90, 0.0, 1.0),   # fachada y palier (fase 5: white_plaster_02)
    "Depto_Mat_Cielo": ((0.95, 0.95, 0.94), 0.90, 0.0, 1.0),          # cielo pintado
    "Depto_Mat_PisoLaminado": ((0.60, 0.50, 0.40), 0.55, 0.0, 1.0),   # áreas secas (fase 5: laminate_floor_02)
    "Depto_Mat_PisoCeramico": ((0.78, 0.72, 0.64), 0.35, 0.0, 1.0),   # baños, cocina y nicho LV (fase 5: interior_tiles)
    "Depto_Mat_PisoBalcon": ((0.70, 0.48, 0.32), 0.60, 0.0, 1.0),     # balcón (fase 5: patio_tiles)
    "Depto_Mat_Colision": ((0.90, 0.20, 0.60), 1.00, 0.0, 1.0),       # volúmenes Depto_Col_* (ocultos)
    # Mobiliario (fase 4; todos supuestos: el plano no indica terminaciones)
    "Depto_Mat_Tapiz": ((0.42, 0.45, 0.48), 0.90, 0.0, 1.0),          # sofá (fase 5: textura de tela)
    "Depto_Mat_TapizAcento": ((0.62, 0.50, 0.36), 0.90, 0.0, 1.0),    # pouf
    "Depto_Mat_Textil": ((0.93, 0.92, 0.90), 0.90, 0.0, 1.0),         # sábanas y almohadas (fase 5: rough_linen)
    "Depto_Mat_Cobertor": ((0.66, 0.62, 0.56), 0.90, 0.0, 1.0),       # cubrecama
    "Depto_Mat_BaseCama": ((0.35, 0.35, 0.36), 0.80, 0.0, 1.0),       # base tapizada de la cama
    "Depto_Mat_Alfombra": ((0.70, 0.66, 0.60), 0.95, 0.0, 1.0),       # fase 5: poly_wool_herringbone
    "Depto_Mat_MaderaMueble": ((0.62, 0.47, 0.32), 0.50, 0.0, 1.0),   # veladores, mesa, cabeceros (fase 5: oak_veneer_01)
    "Depto_Mat_Patas": ((0.12, 0.12, 0.12), 0.50, 0.3, 1.0),          # patas y zócalos de muebles
}


def srgb_a_lineal(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def material(nombre):
    """Material por nombre: se crea si falta y se deja en su versión base (idempotente)."""
    mat = bpy.data.materials.get(nombre) or bpy.data.materials.new(nombre)
    rgb, rough, metal, alfa = MATERIALES[nombre]
    lin = tuple(srgb_a_lineal(c) for c in rgb)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Alpha"].default_value = alfa
    if alfa < 1.0:
        bsdf.inputs["Transmission"].default_value = 1.0 if "Vidrio" in nombre else 0.0
        mat.blend_method = "BLEND"
        mat.shadow_method = "HASHED"
        mat.use_backface_culling = False
        mat.show_transparent_back = True
    else:
        mat.blend_method = "OPAQUE"
    mat.diffuse_color = (*lin, alfa)   # Workbench (color MATERIAL) y viewport
    mat.roughness = rough
    mat.metallic = metal
    return mat


def malla_desde_bmesh(nombre, bm, mat, origen=None, acabado=None):
    """Normales, UV de mundo y sombreado suave con auto smooth; origen (m, mundo) opcional para el objeto.

    acabado: función (centro de cara, normal) -> nombre de material, para asignar un material por cara (muros y
    losas: el recinto hacia el que mira cada cara). Si se da, `mat` se ignora."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mats = [mat]
    if acabado is not None:
        nombres = []
        for f in bm.faces:
            n = acabado(f.calc_center_median(), f.normal)
            if n not in nombres:
                nombres.append(n)
            f.material_index = nombres.index(n)
        mats = [material(n) for n in nombres]
    uv_mundo(bm)                      # UV con coordenadas de mundo: se calcula antes de mover el origen
    if origen is not None:
        bmesh.ops.translate(bm, vec=[-c for c in origen], verts=bm.verts)
    suave = any(f.smooth for f in bm.faces)
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    if suave:
        me.use_auto_smooth = True
        me.auto_smooth_angle = math.radians(35)
    for m in mats:
        me.materials.append(m)
    return me


class Pieza:
    """Acumula cajas y cilindros de un objeto y lo crea de una vez."""

    def __init__(self, nombre, mat_nombre):
        self.nombre, self.mat_nombre = nombre, mat_nombre
        self.bm = bmesh.new()

    def caja(self, x0, x1, y0, y1, z0, z1):
        caja(self.bm, x0, x1, y0, y1, z0, z1)
        return self

    def caja_con_hueco(self, x0, x1, y0, y1, z0, z1, hueco, z_hueco):
        caja_con_hueco(self.bm, x0, x1, y0, y1, z0, z1, hueco, z_hueco)
        return self

    def cilindro(self, cx, cy, rx, ry, z0, z1, seg=24):
        cilindro(self.bm, cx, cy, rx, ry, z0, z1, seg)
        return self

    def cuenco(self, cx, cy, rx, ry, z0, z1, pared, fondo, seg=24):
        cuenco(self.bm, cx, cy, rx, ry, z0, z1, pared, fondo, seg)
        return self

    def crear(self, col, props=None, origen=None, padre=None, color=(1.0, 1.0, 1.0, 1.0)):
        """Crea el objeto. origen: punto de mundo (m) donde queda el origen del objeto (p.ej. la bisagra).
        padre: objeto con ese mismo origen al que se emparenta (manillas que siguen a la hoja)."""
        me = malla_desde_bmesh(self.nombre, self.bm, material(self.mat_nombre), origen)
        ob = bpy.data.objects.new(self.nombre, me)
        if origen is not None and padre is None:
            ob.location = origen
        if padre is not None:
            ob.parent = padre              # matrix_parent_inverse = identidad: el local es relativo al padre
        ob.color = color   # blanco en la planta de comparación: compare_plan sólo mide muros
        for k, v in (props or {}).items():
            ob[k] = v
        col.objects.link(ob)
        return ob


def colecciones_fase(root, nombres):
    """Borra y recrea las colecciones de una fase, con los datablocks que quedan huérfanos al borrar sus objetos.

    Sólo se eliminan las mallas, cámaras, luces y materiales que usaban esos objetos: nada de otras fases.
    """
    datos, mats = [], []
    for n in nombres:
        c = bpy.data.collections.get(n)
        if c:
            for o in list(c.all_objects):
                if o.data is not None:
                    datos.append(o.data)
                    mats += [m for m in getattr(o.data, "materials", []) if m]
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(c)
    for d in datos:
        if d.users == 0:
            for tipo, coleccion in ((bpy.types.Mesh, bpy.data.meshes), (bpy.types.Camera, bpy.data.cameras),
                                    (bpy.types.Light, bpy.data.lights)):
                if isinstance(d, tipo):
                    coleccion.remove(d)
    for m in set(mats):
        if m.users == 0:
            bpy.data.materials.remove(m)
    cols = {}
    for n in nombres:
        c = bpy.data.collections.new(n)
        root.children.link(c)
        cols[n] = c
    return cols


def islas_mundo(ob):
    """Componentes conexas de la malla de un objeto -> lista de (vértices de mundo)."""
    return _islas(ob, ob.matrix_world)


def islas_locales(ob):
    """Idem en coordenadas locales del objeto (sin su transformación)."""
    return _islas(ob, None)


def _islas(ob, mw):
    me = ob.data
    padre = list(range(len(me.vertices)))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i
    for e in me.edges:
        a, b = raiz(e.vertices[0]), raiz(e.vertices[1])
        if a != b:
            padre[a] = b
    grupos = {}
    for v in me.vertices:
        grupos.setdefault(raiz(v.index), []).append(mw @ v.co if mw is not None else v.co.copy())
    return list(grupos.values())


def aabb(puntos):
    xs, ys, zs = [p.x for p in puntos], [p.y for p in puntos], [p.z for p in puntos]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


# ---------------------------------------------------------------------------
# Pruebas compartidas (fases 3 en adelante): cajas envolventes por isla de malla, en metros de mundo.
# ---------------------------------------------------------------------------
def solidos(objs):
    """(objeto, aabb) por isla de malla."""
    return [(o, aabb(isla)) for o in objs for isla in islas_mundo(o)]


def penetracion(A, B):
    """Solape mínimo entre dos aabb en los tres ejes (> 0: se penetran)."""
    return min(min(A[1], B[1]) - max(A[0], B[0]), min(A[3], B[3]) - max(A[2], B[2]),
               min(A[5], B[5]) - max(A[4], B[4]))


def dist_punto_caja(p, c):
    d = [max(c[2 * k] - p[k], 0.0, p[k] - c[2 * k + 1]) for k in range(3)]
    return math.sqrt(sum(x * x for x in d))


def segmento_cruza(c, p0, p1):
    """¿El segmento p0-p1 atraviesa la caja c? (método de las franjas)"""
    t0, t1 = 0.0, 1.0
    for k in range(3):
        d = p1[k] - p0[k]
        lo, hi = c[2 * k], c[2 * k + 1]
        if abs(d) < 1e-12:
            if p0[k] < lo or p0[k] > hi:
                return False
            continue
        ta, tb = sorted(((lo - p0[k]) / d, (hi - p0[k]) / d))
        t0, t1 = max(t0, ta), min(t1, tb)
        if t0 > t1:
            return False
    return True


def interferencias(propios, ajenos, tol):
    """Pares de islas que se penetran más de tol: propios contra ajenos y entre sí (salvo mismo objeto o
    padre/hijo, que se prueban aparte en su marco local)."""
    fallos = []
    for i, (oa, A) in enumerate(propios):
        for ob, B in ajenos + propios[i + 1:]:
            if ob is oa or ob.parent is oa or oa.parent is ob:
                continue
            if penetracion(A, B) > tol:
                fallos.append(f"interferencia {oa.name} / {ob.name}: {penetracion(A, B) * 1000:.1f} mm")
    return fallos


def holgura_camaras(todos, minimo, excluir=("Depto_Cam_Planta", "Depto_Cam_Maqueta")):
    """Distancia 3D de cada cámara de ambiente al sólido más cercano. Devuelve (fallos, holguras)."""
    fallos, holguras = [], {}
    for cam in [o for o in bpy.data.objects if o.type == "CAMERA" and o.name.startswith("Depto_Cam_")
                and o.name not in excluir]:
        p = cam.matrix_world.translation
        d, cerca = min((dist_punto_caja(p, c), o.name) for o, c in todos)
        holguras[cam.name] = round(d, 3)
        if d < minimo:
            fallos.append(f"{cam.name} a {d:.3f} m de {cerca}")
    return fallos, holguras
