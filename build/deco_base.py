"""Ayudas de modelado para las piezas de la decoración industrial (versión 2, docs/deco-industrial.md).

Coordenadas locales en metros (no px del plano). Las funciones de malla agregan geometría a un bmesh; `objeto`
convierte el bmesh en un objeto con normales, UV de caja en metros y materiales por nombre (depto_geom.material).
Todo es bpy 3.6 y funciona en headless.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import depto_geom as G


# ---------------------------------------------------------------- primitivas
def caja(bm, x0, x1, y0, y1, z0, z1):
    """Caja alineada a los ejes. Devuelve (vértices, caras)."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    v = [bm.verts.new(c) for c in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    caras = [bm.faces.new([v[i] for i in f]) for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
                                                        (2, 3, 7, 6), (3, 0, 4, 7))]
    return v, caras


def caja_redondeada(bm, x0, x1, y0, y1, z0, z1, radio, segmentos=3):
    """Caja con todas sus aristas redondeadas (bisel de bmesh). Devuelve las caras resultantes."""
    v, caras = caja(bm, x0, x1, y0, y1, z0, z1)
    aristas = list({e for f in caras for e in f.edges})
    res = bmesh.ops.bevel(bm, geom=aristas, offset=radio, offset_type="OFFSET", segments=segmentos,
                          profile=0.5, affect="EDGES", clamp_overlap=True)
    return res.get("faces", [])


def cilindro(bm, cx, cy, z0, z1, r, seg=24, tapas=True, suave=True):
    """Cilindro vertical. Devuelve (anillo inferior, anillo superior)."""
    abajo = [bm.verts.new((cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg), z0))
             for i in range(seg)]
    arriba = [bm.verts.new((v.co.x, v.co.y, z1)) for v in abajo]
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((abajo[i], abajo[j], arriba[j], arriba[i])).smooth = suave
    if tapas:
        bm.faces.new(list(reversed(abajo)))
        bm.faces.new(arriba)
    return abajo, arriba


def torno(bm, perfil, seg=32, suave=True, cerrado=False):
    """Superficie de revolución alrededor de Z. perfil: [(radio, z), ...]. Un radio 0 es un polo (se cierra en
    abanico). cerrado=True une el último punto con el primero (sección cerrada, p. ej. pared con espesor)."""
    anillos = []
    for r, z in perfil:
        if r < 1e-7:
            anillos.append([bm.verts.new((0.0, 0.0, z))])
        else:
            anillos.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z))
                            for i in range(seg)])
    pares = list(zip(anillos[:-1], anillos[1:])) + ([(anillos[-1], anillos[0])] if cerrado else [])
    for a, b in pares:
        for i in range(seg):
            j = (i + 1) % seg
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                f = bm.faces.new((a[0], b[i], b[j]))
            elif len(b) == 1:
                f = bm.faces.new((a[i], a[j], b[0]))
            else:
                f = bm.faces.new((a[i], a[j], b[j], b[i]))
            f.smooth = suave
    return anillos


def _redondear_polilinea(puntos, radio, pasos=6):
    pts = [Vector(p) for p in puntos]
    if radio <= 0 or len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, p, b = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = (p - a), (b - p)
        l1, l2 = d1.length, d2.length
        d1.normalize()
        d2.normalize()
        cosang = max(-1.0, min(1.0, d1.dot(d2)))
        ang = math.acos(cosang)
        if ang < 1e-3:
            out.append(p)
            continue
        t = min(radio * math.tan(ang / 2), l1 * 0.49, l2 * 0.49)
        r = t / math.tan(ang / 2)
        s = p - d1 * t
        eje = d1.cross(d2).normalized()
        normal = eje.cross(d1).normalized()          # perpendicular a d1 hacia la curva
        centro = s + normal * r
        for k in range(pasos + 1):
            rot = Matrix.Rotation(ang * k / pasos, 3, eje)
            out.append(centro + rot @ (s - centro))
    out.append(pts[-1])
    return out


def tubo(bm, puntos, radio, seg=12, radio_curva=0.0, tapas=True, suave=True, giro=0.0):
    """Tubo de sección circular (seg=4 y giro=45°: tubo cuadrado) a lo largo de una polilínea 3D, con curvas
    redondeadas de radio_curva en los vértices intermedios. Marcos que minimizan la torsión."""
    pts = _redondear_polilinea(puntos, radio_curva)
    n = len(pts)
    tang = []
    for i in range(n):
        d = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])
        tang.append(d.normalized())
    ref = Vector((0, 0, 1)) if abs(tang[0].z) < 0.9 else Vector((1, 0, 0))
    nor = (ref - tang[0] * ref.dot(tang[0])).normalized()
    anillos = []
    for i in range(n):
        if i > 0:
            nor = (nor - tang[i] * nor.dot(tang[i])).normalized()
        bi = tang[i].cross(nor)
        anillo = []
        for k in range(seg):
            a = 2 * math.pi * k / seg + math.radians(giro)
            anillo.append(bm.verts.new(pts[i] + (nor * math.cos(a) + bi * math.sin(a)) * radio))
        anillos.append(anillo)
    for a, b in zip(anillos[:-1], anillos[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((a[k], a[j], b[j], b[k])).smooth = suave
    if tapas:
        bm.faces.new(list(reversed(anillos[0])))
        bm.faces.new(anillos[-1])
    return anillos


def grilla(bm, x0, x1, y0, y1, nx, ny, z=0.0):
    """Plano subdividido en nx × ny quads (para telas que luego se deforman). Devuelve la matriz de vértices."""
    vs = [[bm.verts.new((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny, z)) for i in range(nx + 1)]
          for j in range(ny + 1)]
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
    return vs


def transformar(bm, matriz, verts=None):
    bmesh.ops.transform(bm, matrix=matriz, verts=list(verts) if verts is not None else bm.verts)


# ---------------------------------------------------------------- objetos
def objeto(col, nombre, bm, material, suave=False, angulo_suave=35, materiales=None, recalc=True, uv="mundo",
           props=None):
    """Crea el objeto desde el bmesh (y lo libera). material: nombre Depto_Mat_*; con `materiales` (lista), el
    material de cada cara lo fija su material_index. uv="mundo": caja en metros; uv="propia": ya las puso quien
    llama (capa activa del bmesh)."""
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if suave:
        for f in bm.faces:
            f.smooth = True
    if uv == "mundo":
        G.uv_mundo(bm)
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    if any(p.use_smooth for p in me.polygons):
        me.use_auto_smooth = True
        me.auto_smooth_angle = math.radians(angulo_suave)
    for m in (materiales or [material]):
        me.materials.append(G.material(m))
    ob = bpy.data.objects.new(nombre, me)
    col.objects.link(ob)
    for k, v in (props or {}).items():
        ob[k] = v
    return ob


def aplicar_subdivision(ob, niveles=1):
    """Subdivisión Catmull-Clark aplicada (la colección de `ob` debe estar en la escena). Máximo nivel 2."""
    assert niveles <= 2, "subdivisión alta: revienta el presupuesto de triángulos"
    m = ob.modifiers.new("_sub", "SUBSURF")
    m.levels = m.render_levels = niveles
    auto = ob.data.use_auto_smooth, ob.data.auto_smooth_angle
    dg = bpy.context.evaluated_depsgraph_get()
    nueva = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    vieja = ob.data
    ob.modifiers.remove(m)
    ob.data = nueva
    nueva.name = vieja.name
    bpy.data.meshes.remove(vieja)
    nueva.use_auto_smooth, nueva.auto_smooth_angle = auto
    for p in nueva.polygons:
        p.use_smooth = True
    return ob


def desplazar(ob, funcion):
    """Mueve cada vértice: funcion(Vector local) -> Vector nuevo."""
    for v in ob.data.vertices:
        v.co = funcion(v.co.copy())
    ob.data.update()


def triangulos(objs):
    total = 0
    for o in objs:
        o.data.calc_loop_triangles()
        total += len(o.data.loop_triangles)
    return total
