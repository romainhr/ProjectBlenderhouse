"""Fase 2 (blockout con formas correctas): mesa auxiliar redonda de tres patas.

Uso:
    blender -b --python build/01_mesa.py

Idempotente: parte de una escena de fábrica vacía y reconstruye todo desde las
constantes de abajo. Guarda build/mesa.blend e imprime FASE_OK.
Convención: metros, origen en el suelo y centrado en XY, +Z arriba, frente = -Y.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------------------
# Constantes (todas en metros salvo indicación). Origen: asset-brief.md
# ---------------------------------------------------------------------------
DIAMETRO_TAPA = 0.60          # brief: foto 1 vs. lamas del piso (estimado ±0.06)
GROSOR_TAPA = 0.025           # brief: foto 2, canto ≈ 3,6 % del diámetro (±0.005)
RADIO_CANTO_TAPA = 0.005      # brief: foto 2, canto suavemente redondeado
SEGMENTOS_TAPA = 64           # tarea fase 2
SEGMENTOS_BEVEL_TAPA = 3      # decisión de blockout: redondeo suficiente para la silueta
ALTURA_TOTAL = 0.56           # brief: foto 3, alto ≈ 0,93 × diámetro (±0.05)

HUB_ANCHO = 0.16              # re-medido foto 2: hub ≈ 30 % del diámetro (entre caras del hexágono)
HUB_ALTO = 0.07               # re-medido foto 2 (mesa invertida)
HUB_LADOS = 6                 # brief: foto 2, bloque hexagonal

N_PATAS = 3                   # brief: fotos 2 y 3
PATA_DIAM_ARRIBA = 0.036      # brief: foto 2, ≈ 6 % del diámetro
PATA_DIAM_ABAJO = 0.022       # brief: fotos 2 y 3, pie más fino
PATA_ANGULO_APERTURA = math.radians(15.0)  # brief: foto 3, respecto a la vertical (±3°)
# Unión pata-hub (ronda 2, foto 2 invertida): la pata sale por DEBAJO del hub como una
# espiga en un agujero inclinado de la cara inferior. El eje corta Z_HUB_ABAJO a este
# margen del borde de la cara (radio = apotema − PATA_DIAM_ARRIBA/2 − margen).
PATA_MARGEN_BORDE = 0.008     # director ronda 2
# Prolongación virtual del cono por encima de Z_HUB_ABAJO antes del bisect (luego se
# recorta; sólo garantiza que el corte horizontal atraviese toda la sección inclinada).
PATA_PROLONGACION = 0.010     # decisión técnica: > (PATA_DIAM_ARRIBA/2)·tan(15°) ≈ 0.0048
SEGMENTOS_PATA = 24           # tarea fase 2
# Ángulo (en planta) de la primera pata: sale de la cara plana orientada a -Y
# (tarea fase 2); las demás, en caras alternas cada 120° (brief: foto 2).
PATA_ANGULO_INICIAL = math.radians(-90.0)

TORNILLOS_POR_CARA = 2        # brief: foto 2
TORNILLO_DIAM = 0.004         # brief: foto 2, Ø 4 mm
TORNILLO_LARGO = 0.012        # supuesto: 9 mm embutidos en el hub + 3 mm de cabeza visible
TORNILLO_SALIENTE = 0.003     # supuesto: cabeza que sobresale de la cara
# Ronda 2: apilados verticalmente, centrados horizontalmente en la cara con pata.
TORNILLO_Z_REL = (0.022, 0.048)  # director ronda 2: alturas sobre Z_HUB_ABAJO
SEGMENTOS_TORNILLO = 12       # decisión de blockout

# Colores sRGB del brief (sección Materiales)
COLOR_MADERA = (0.72, 0.50, 0.28)   # tapa y patas, roughness 0.45
COLOR_HUB = (0.45, 0.28, 0.18)      # hub, madera más oscura
COLOR_ACERO = (0.60, 0.60, 0.62)    # supuesto: acero neutro (metallic 1, roughness 0.4)

OUT_BLEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mesa.blend")

# ---------------------------------------------------------------------------
# Geometría derivada
# ---------------------------------------------------------------------------
Z_TAPA_ARRIBA = ALTURA_TOTAL
Z_TAPA_ABAJO = ALTURA_TOTAL - GROSOR_TAPA
Z_HUB_ARRIBA = Z_TAPA_ABAJO                  # hub pegado bajo la tapa
Z_HUB_ABAJO = Z_HUB_ARRIBA - HUB_ALTO
Z_HUB_MEDIO = (Z_HUB_ARRIBA + Z_HUB_ABAJO) / 2
HUB_APOTEMA = HUB_ANCHO / 2
HUB_CIRCUNRADIO = HUB_APOTEMA / math.cos(math.pi / HUB_LADOS)

# Pata: el eje corta la cara inferior del hub a este radio del centro.
PATA_RADIO_ANCLAJE = HUB_APOTEMA - PATA_DIAM_ARRIBA / 2 - PATA_MARGEN_BORDE
# Centro del pie: corte perpendicular al eje, su punto más bajo toca Z=0.
Z_PIE_CENTRO = (PATA_DIAM_ABAJO / 2) * math.sin(PATA_ANGULO_APERTURA)
# Largo a lo largo del eje, del centro del pie al punto de anclaje en Z_HUB_ABAJO:
# recalculado para conservar ALTURA_TOTAL (antes 0.53 con la unión por la cara lateral).
PATA_LARGO = (Z_HUB_ABAJO - Z_PIE_CENTRO) / math.cos(PATA_ANGULO_APERTURA)
SMOOTH_ANGULO = math.radians(30.0)  # director ronda 2: auto smooth 30°


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_material(name, srgb, roughness, metallic=0.0):
    mat = bpy.data.materials.new(name)
    lin = tuple(srgb_to_linear(c) for c in srgb) + (1.0,)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = lin
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    mat.diffuse_color = lin          # color en Workbench / viewport
    mat.roughness = roughness
    mat.metallic = metallic
    return mat


def new_object(name, bm, collection, material, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = smooth
    if smooth:
        me.use_auto_smooth = True
        me.auto_smooth_angle = SMOOTH_ANGULO
    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)
    return obj


def build_tapa(col, mat):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=SEGMENTOS_TAPA,
        radius1=DIAMETRO_TAPA / 2, radius2=DIAMETRO_TAPA / 2, depth=GROSOR_TAPA,
        matrix=Matrix.Translation((0, 0, Z_TAPA_ABAJO + GROSOR_TAPA / 2)),
    )
    # Canto redondeado: bevel sobre las aristas del borde (las que separan caras
    # laterales de las tapas circulares).
    rim = [e for e in bm.edges
           if len(e.link_faces) == 2 and abs(e.link_faces[0].normal.z - e.link_faces[1].normal.z) > 0.5]
    bm.normal_update()
    bmesh.ops.bevel(
        bm, geom=rim, offset=RADIO_CANTO_TAPA, offset_type="OFFSET",
        profile_type="SUPERELLIPSE", segments=SEGMENTOS_BEVEL_TAPA, profile=0.5,
        affect="EDGES", clamp_overlap=True,
    )
    return new_object("Mesa_Tapa", bm, col, mat, smooth=True)


def build_hub(col, mat):
    # Vértices a 0°, 60°, ... → caras centradas en 30° + k·60°, incluida una en 270° (-Y).
    bm = bmesh.new()
    bot, top = [], []
    for i in range(HUB_LADOS):
        a = 2 * math.pi * i / HUB_LADOS
        x, y = HUB_CIRCUNRADIO * math.cos(a), HUB_CIRCUNRADIO * math.sin(a)
        bot.append(bm.verts.new((x, y, Z_HUB_ABAJO)))
        top.append(bm.verts.new((x, y, Z_HUB_ARRIBA)))
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    for i in range(HUB_LADOS):
        j = (i + 1) % HUB_LADOS
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_object("Mesa_Hub", bm, col, mat)


def pata_frame(ang):
    """Devuelve (salida radial horizontal n, eje hacia arriba e, vector u) para una pata."""
    n = Vector((math.cos(ang), math.sin(ang), 0.0))
    s, c = math.sin(PATA_ANGULO_APERTURA), math.cos(PATA_ANGULO_APERTURA)
    e = Vector((-n.x * s, -n.y * s, c))          # eje de la pata, del pie hacia arriba
    u = Vector((n.x * c, n.y * c, s))            # perpendicular al eje en el plano radial, hacia afuera
    return n, e, u


def pata_posicion(ang):
    """Centro del pie B y punto de anclaje P (eje ∩ cara inferior del hub).

    Criterios (ronda 2): el eje, inclinado PATA_ANGULO_APERTURA hacia afuera en el plano
    vertical que pasa por el centro del hub y el centro de la cara, corta Z = Z_HUB_ABAJO a
    radio PATA_RADIO_ANCLAJE; el pie (corte perpendicular al eje) toca Z=0 en su punto
    más bajo. |P − B| = PATA_LARGO.
    """
    n, e, _ = pata_frame(ang)
    P = n * PATA_RADIO_ANCLAJE + Vector((0, 0, Z_HUB_ABAJO))
    B = P - e * PATA_LARGO
    return B, P


def build_pata(idx, ang, col, mat):
    n, e, _ = pata_frame(ang)
    B, P = pata_posicion(ang)
    # Cono prolongado PATA_PROLONGACION por encima de P, conservando la conicidad
    # (diámetro PATA_DIAM_ARRIBA exactamente en P).
    largo_tot = PATA_LARGO + PATA_PROLONGACION
    r_ab = PATA_DIAM_ABAJO / 2
    r_top = r_ab + (PATA_DIAM_ARRIBA / 2 - r_ab) * largo_tot / PATA_LARGO
    T = B + e * largo_tot
    rot = Vector((0, 0, 1)).rotation_difference(e).to_matrix().to_4x4()
    mtx = Matrix.Translation((B + T) / 2) @ rot
    bm = bmesh.new()
    # create_cone: radius1 en -Z local (pie), radius2 en +Z local (arriba)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=SEGMENTOS_PATA,
        radius1=r_ab, radius2=r_top, depth=largo_tot,
        matrix=mtx,
    )
    # Recorte horizontal en la cara inferior del hub: lo que quedaría dentro del hub
    # (la espiga) no se modela; el hueco se tapa.
    res = bmesh.ops.bisect_plane(
        bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        plane_co=Vector((0, 0, Z_HUB_ABAJO)), plane_no=Vector((0, 0, 1)),
        clear_outer=True, dist=1e-6,
    )
    cut_edges = [g for g in res["geom_cut"] if isinstance(g, bmesh.types.BMEdge)]
    if cut_edges:
        bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object(f"Mesa_Pata_{idx}", bm, col, mat, smooth=True)
    return obj, B, P, bool(cut_edges)


def build_tornillos(idx, ang, col, mat):
    n, _, _ = pata_frame(ang)
    t = Vector((-n.y, n.x, 0.0))                  # tangente de la cara
    rot = Vector((0, 0, 1)).rotation_difference(n).to_matrix().to_4x4()
    objs = []
    centro_radial = HUB_APOTEMA + TORNILLO_SALIENTE - TORNILLO_LARGO / 2
    for k in range(TORNILLOS_POR_CARA):
        # Centrado en la cara (desplazamiento tangencial 0), apilados en Z.
        c = n * centro_radial + t * 0.0 + Vector((0, 0, Z_HUB_ABAJO + TORNILLO_Z_REL[k]))
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm, cap_ends=True, cap_tris=False, segments=SEGMENTOS_TORNILLO,
            radius1=TORNILLO_DIAM / 2, radius2=TORNILLO_DIAM / 2, depth=TORNILLO_LARGO,
            matrix=Matrix.Translation(c) @ rot,
        )
        objs.append(new_object(f"Mesa_Tornillo_{idx}{'ab'[k]}", bm, col, mat, smooth=True))
    return objs


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"

    col = bpy.data.collections.new("Mesa")
    scene.collection.children.link(col)

    m_madera = make_material("Mesa_Madera", COLOR_MADERA, 0.45)
    m_hub = make_material("Mesa_Hub_Madera", COLOR_HUB, 0.5)
    m_acero = make_material("Mesa_Acero", COLOR_ACERO, 0.4, metallic=1.0)

    build_tapa(col, m_madera)
    build_hub(col, m_hub)
    patas = []
    for i in range(N_PATAS):
        ang = PATA_ANGULO_INICIAL + i * 2 * math.pi / N_PATAS
        pata, B, T, cut = build_pata(i + 1, ang, col, m_madera)
        patas.append(pata)
        print(f"PATA {i+1}: pie=({B.x:.4f},{B.y:.4f},{B.z:.4f}) anclaje=({T.x:.4f},{T.y:.4f},{T.z:.4f}) "
              f"radio_pie={B.xy.length:.4f} largo={PATA_LARGO:.5f} recorte_fondo_hub={cut}")
        build_tornillos(i + 1, ang, col, m_acero)

    # Todo se construye en coordenadas de mundo con transformaciones identidad;
    # aun así se aplican para garantizarlo.
    for o in col.objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = col.objects[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Comprobaciones básicas
    objs = list(col.objects)
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    zmin = min(p.z for p in pts)
    zmax = max(p.z for p in pts)
    tris = 0
    for o in objs:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    # Unión pata-hub: ningún vértice de la pata por encima de Z_HUB_ABAJO, y los vértices
    # de la sección de corte (|Z − Z_HUB_ABAJO| ≤ 1 mm) dentro del hexágono (radio y
    # distancia a cada plano de cara < apotema) → la pata no atraviesa las caras laterales.
    normales_caras = [Vector((math.cos(math.pi / HUB_LADOS + k * 2 * math.pi / HUB_LADOS),
                              math.sin(math.pi / HUB_LADOS + k * 2 * math.pi / HUB_LADOS), 0.0))
                      for k in range(HUB_LADOS)]
    for pata in patas:
        vs = [pata.matrix_world @ v.co for v in pata.data.vertices]
        zmax_p = max(v.z for v in vs)
        banda = [v for v in vs if v.z >= Z_HUB_ABAJO - 0.001]
        r_max = max(v.xy.length for v in banda)
        d_max = max(max(v.dot(nk) for nk in normales_caras) for v in banda)
        zmin_p = min(v.z for v in vs)
        ok = zmax_p <= Z_HUB_ABAJO + 1e-5 and r_max < HUB_APOTEMA and d_max < HUB_APOTEMA
        print(f"CHECK_PATA {pata.name}: zmax={zmax_p:.5f} (Z_HUB_ABAJO={Z_HUB_ABAJO:.5f}) "
              f"zmin={zmin_p:.5f} n_banda={len(banda)} r_max_banda={r_max:.5f} "
              f"dist_cara_max={d_max:.5f} apotema={HUB_APOTEMA:.5f} OK={ok}")
        assert ok, f"{pata.name} atraviesa el hub"
    assert abs(zmin) < 1e-5, f"pie más bajo fuera de Z=0: {zmin}"

    print(f"CHECK zmin={zmin:.5f} zmax={zmax:.5f} "
          f"dx={max(p.x for p in pts)-min(p.x for p in pts):.4f} "
          f"dy={max(p.y for p in pts)-min(p.y for p in pts):.4f}")

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"FASE_OK Mesa {len(objs)} {tris}")


if __name__ == "__main__":
    main()
