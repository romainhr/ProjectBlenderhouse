"""Plantas de interior del bloque 09: modelos CC0 de Poly Haven (assets/modelos/polyhaven/, glTF 1k) importados con
bpy.ops.import_scene.gltf, reducidos con Decimate (colapso) hasta su tope de triángulos y puestos en macetas modeladas
aquí (una maceta no es orgánica: va por bmesh, como el resto de la decoración). CLAUDE.md pide no modelar orgánicos
con bpy: las hojas son las de los escaneos, sólo se decima, se escala y se gira.

Texturas derivadas (`blender -b --python build/deco_plantas.py -- --derivar`; se versionan en
assets/modelos/polyhaven/<modelo>/derivadas/ y su origen queda en assets/modelos/polyhaven/manifest.json):
Poly Haven entregó el color en JPEG, sin canal alfa, aunque el material pide MASK. La silueta de las hojas se recupera:
- fern_02: del mapa ARM (G = rugosidad), que fuera de las frondas vale 1 exacto (medido: 83 % del atlas en G = 255 y
  las frondas bajo 240); alfa = 1 donde G < 0,955, con 1,5 % de transición;
- calathea_orbifolia_01: del mismo canal, cuyo fondo es un valor plano (el pico del histograma en G ≈ 0,65) mientras
  hojas y tallos quedan bajo 0,60; se intersecta con la cobertura de las UV (los tallos están fuera de ese pico);
- anthurium_botany_01: el fondo del ARM es un relleno estirado sin valor propio; la silueta la da la geometría (hojas
  modeladas) y el alfa es la cobertura de las UV del atlas dilatada 2 px: recorta sólo el relleno;
- potted_plant_04 (haworthia): opaca, como su material original (hojas carnosas modeladas). Corrección 09 (ronda 1):
  se usa sólo su nodo `plant`, en una maceta modelada de 24 lados; la maceta del escaneo, decimada junto con la planta
  (colapso, que no respeta las costuras UV), quedaba facetada y con la textura estirada.
Además: rugosidad en gris (el canal G del ARM) para el visor, y el normal original tal cual.

Piezas (contrato de docs/deco-industrial.md: metros, apoyo en z = 0, frente hacia −Y): `planta` devuelve la malla de
una variante del modelo con su base (el origen del nodo glTF) en el origen; `maceta`, la maceta con su tierra;
`en_maceta` junta las dos (la maceta colgada del helecho del living se quitó en la corrección 09). Los materiales Depto_Mat_Planta* llevan alfa CLIP (umbral 0,5) y dos caras
(glTF: alphaMode MASK, doubleSided); la fase 5 les pone las texturas (build/deco_paleta.py, fuente "modelos").
"""
import argparse
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import deco_base as B  # noqa: E402
import depto_geom as G  # noqa: E402

MODELOS = os.path.join(RAIZ, "assets", "modelos", "polyhaven")
MANIFIESTO = os.path.join(MODELOS, "manifest.json")
TOPE_PLANTA = 8000       # encargo del bloque 09: cada planta decimada a 8 000 triángulos o menos
MATERIAL = {
    "anthurium_botany_01": "Depto_Mat_PlantaAnturio",
    "calathea_orbifolia_01": "Depto_Mat_PlantaCalathea",
    "fern_02": "Depto_Mat_PlantaHelecho",
    "potted_plant_04": "Depto_Mat_PlantaHaworthia",
}
# colores base (sin textura: revisión de piezas antes de la fase 5), medidos a ojo sobre el color de cada atlas
G.MATERIALES.setdefault("Depto_Mat_PlantaAnturio", ((0.20, 0.30, 0.14), 0.55, 0.0, 1.0))
G.MATERIALES.setdefault("Depto_Mat_PlantaCalathea", ((0.24, 0.34, 0.18), 0.55, 0.0, 1.0))
G.MATERIALES.setdefault("Depto_Mat_PlantaHelecho", ((0.25, 0.36, 0.14), 0.70, 0.0, 1.0))
G.MATERIALES.setdefault("Depto_Mat_PlantaHaworthia", ((0.30, 0.38, 0.22), 0.60, 0.0, 1.0))
TIERRA = "Depto_Mat_Tierra"
G.MATERIALES.setdefault(TIERRA, ((0.16, 0.12, 0.09), 0.95, 0.0, 1.0))    # sustrato húmedo (diseño)
# Cómo se recupera el alfa de cada atlas (ver el docstring). arm_g: (umbral, transición) sobre el canal G del ARM.
ALFA = {
    "fern_02": dict(metodo="arm_g", umbral=0.955, transicion=0.015, cobertura=False),
    "calathea_orbifolia_01": dict(metodo="arm_g", umbral=0.615, transicion=0.015, cobertura=True),
    "anthurium_botany_01": dict(metodo="cobertura"),
    "potted_plant_04": None,
}


def rutas(modelo):
    d = os.path.join(MODELOS, modelo)
    der = os.path.join(d, "derivadas")
    diff = os.path.join(d, "textures", f"{modelo}_diff_1k.jpg")
    return dict(gltf=os.path.join(d, f"{modelo}_1k.gltf"), diff=diff,
                arm=os.path.join(d, "textures", f"{modelo}_arm_1k.jpg"),
                normal=os.path.join(d, "textures", f"{modelo}_nor_gl_1k.jpg"), carpeta=der,
                color=os.path.join(der, f"{modelo}_diff_alfa_1k.png") if ALFA[modelo] else diff,   # opaca: el original
                rugosidad=os.path.join(der, f"{modelo}_rough_1k.jpg"))


# ---------------------------------------------------------------- importación
def _importar(modelo):
    """Importa el glTF entero en la escena activa y devuelve sus objetos nuevos (una variante por nodo)."""
    antes = set(bpy.data.objects)
    mats_antes, imgs_antes = set(bpy.data.materials), set(bpy.data.images)
    bpy.ops.import_scene.gltf(filepath=rutas(modelo)["gltf"])
    nuevos = [o for o in bpy.data.objects if o not in antes]
    return nuevos, [m for m in bpy.data.materials if m not in mats_antes], [i for i in bpy.data.images
                                                                              if i not in imgs_antes]


def _limpiar_importacion(objs, mats, imgs):
    for o in objs:
        me = o.data if o.type == "MESH" else None
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    for m in mats:
        if m.users == 0:
            bpy.data.materials.remove(m)
    for i in imgs:
        if i.users == 0:
            bpy.data.images.remove(i)


def _decimar(ob, tope):
    """Decimate (colapso, triangulado) hasta `tope` triángulos o menos; aplicado. Devuelve (antes, después)."""
    ob.data.calc_loop_triangles()
    antes = len(ob.data.loop_triangles)
    if antes <= tope:
        return antes, antes
    ratio = tope / antes
    for _ in range(4):
        m = ob.modifiers.new("_dec", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = ratio
        m.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        nueva = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.remove(m)
        nueva.calc_loop_triangles()
        if len(nueva.loop_triangles) <= tope:
            vieja = ob.data
            ob.data = nueva
            nueva.name = vieja.name
            bpy.data.meshes.remove(vieja)
            return antes, len(nueva.loop_triangles)
        bpy.data.meshes.remove(nueva)
        ratio *= 0.97 * tope / len(nueva.loop_triangles)
    raise SystemExit(f"ERROR: no se pudo decimar {ob.name} a {tope} triángulos")


def planta(col, prefijo, modelo, nodos, tope, escala=1.0, giro=0.0):
    """Malla de la variante `nodos` (nombre o tupla de nombres de nodo glTF, que se juntan) de `modelo`, decimada a
    `tope` triángulos (≤ TOPE_PLANTA), con su origen de nodo en el origen, escalada y girada `giro` grados en Z.
    Queda con el material Depto_Mat_Planta* (una ranura), normales suaves y la UV del escaneo. -> objeto."""
    assert tope <= TOPE_PLANTA, f"{prefijo}: tope {tope} sobre el del encargo ({TOPE_PLANTA})"
    nodos = (nodos,) if isinstance(nodos, str) else tuple(nodos)
    objs, mats, imgs = _importar(modelo)
    elegidos = [o for o in objs if o.name in nodos]
    assert len(elegidos) == len(nodos), f"{modelo}: faltan nodos {set(nodos) - {o.name for o in elegidos}}"
    origen = elegidos[0].matrix_world.translation.copy()
    bm = bmesh.new()
    for o in elegidos:                                     # datos en metros con el origen del primer nodo
        tmp = bmesh.new()
        tmp.from_mesh(o.data)
        tmp.transform(Matrix.Translation(-origen) @ o.matrix_world)
        me_tmp = bpy.data.meshes.new("_tmp")
        tmp.to_mesh(me_tmp)
        tmp.free()
        bm.from_mesh(me_tmp)
        bpy.data.meshes.remove(me_tmp)
    bm.transform(Matrix.Rotation(math.radians(giro), 4, "Z") @ Matrix.Scale(escala, 4))
    me = bpy.data.meshes.new(f"{prefijo}_Hojas")
    bm.to_mesh(me)
    bm.free()
    _limpiar_importacion(objs, mats, imgs)
    if me.has_custom_normals:                              # el decimado no conserva las normales propias del glTF
        me.free_normals_split()
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        ob_tmp = bpy.data.objects.new("_tmp", me)
        col.objects.link(ob_tmp)
        with bpy.context.temp_override(object=ob_tmp, active_object=ob_tmp, selected_objects=[ob_tmp]):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        bpy.data.objects.remove(ob_tmp, do_unlink=True)
    uv = me.uv_layers[0]
    uv.name = "UVMap"
    while len(me.uv_layers) > 1:
        me.uv_layers.remove(me.uv_layers[1])
    me.materials.clear()
    me.materials.append(G.material(MATERIAL[modelo]))
    for p in me.polygons:
        p.material_index = 0
        p.use_smooth = True
    me.use_auto_smooth = True
    me.auto_smooth_angle = math.radians(80)
    ob = bpy.data.objects.new(f"{prefijo}_Hojas", me)
    col.objects.link(ob)
    antes, despues = _decimar(ob, tope)
    ob["planta"] = modelo
    ob["variante"] = ",".join(nodos)
    ob["triangulos_escaneo"] = antes
    ob["colision"] = False                                  # hojas: el recorrido pasa por su lado, no se choca
    return ob


# ---------------------------------------------------------------- macetas
def _perfil_maceta(diametro, alto, conicidad, labio=0.006, pared=0.008, z_tierra=None):
    r1 = diametro / 2
    r0 = r1 * conicidad
    zt = alto - 0.022 if z_tierra is None else z_tierra
    ext = [(0.0, 0.0), (r0 - 0.006, 0.0), (r0, 0.005), (r1 - 0.001, alto - labio), (r1, alto - 0.002),
           (r1 - 0.003, alto), (r1 - pared - 0.001, alto), (r1 - pared, alto - 0.004)]
    k = (zt - 0.0) / max(alto, 1e-6)
    r_in = r0 + (r1 - r0) * k - pared
    return ext + [(r_in, zt)], r_in, zt


def maceta(col, prefijo, diametro, alto, material, conicidad=0.82, seg=16):
    """Maceta de revolución (fondo cerrado, pared de 8 mm, labio redondeado) y su tierra (disco apenas cóncavo bajo
    el borde). Base en z = 0. -> ([maceta, tierra], z de la tierra, radio interior en la tierra)."""
    perfil, r_in, zt = _perfil_maceta(diametro, alto, conicidad)
    bm = bmesh.new()
    B.torno(bm, perfil, seg=seg)
    pot = B.objeto(col, f"{prefijo}_Maceta", bm, material, angulo_suave=50)
    bm = bmesh.new()
    B.torno(bm, [(r_in + 0.001, zt), (0.6 * r_in, zt - 0.003), (0.0, zt - 0.004)], seg=seg)
    tierra = B.objeto(col, f"{prefijo}_Tierra", bm, TIERRA, angulo_suave=60)
    tierra["colision"] = False
    return [pot, tierra], zt - 0.003, r_in


def en_maceta(col, prefijo, modelo, nodos, tope, pot, escala=1.0, giro=0.0, hundir=0.004, base=0.0):
    """Planta dentro de su maceta: `pot` = (objs, z tierra, radio interior) de `maceta`. La base de
    la planta queda `hundir` bajo la tierra (los tallos arrancan dentro); `base`: altura (m, en el escaneo) donde
    arranca la planta sobre el origen de su nodo (0 salvo en los escaneos que traían su maceta). -> lista de objetos."""
    objs, zt, _ = pot
    hojas = planta(col, prefijo, modelo, nodos, tope, escala, giro)
    hojas.data.transform(Matrix.Translation((0.0, 0.0, zt - hundir - base * escala)))
    return objs + [hojas]


# ---------------------------------------------------------------- texturas derivadas (en Blender, con numpy)
def _leer(ruta):
    im = bpy.data.images.load(ruta, check_existing=False)
    im.colorspace_settings.name = "Non-Color"            # valores del archivo tal cual
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)                            # fila 0 = abajo (orden de Blender, como las UV)


def _guardar(rgba, ruta, formato):
    h, w = rgba.shape[:2]
    alfa = formato == "PNG"
    im = bpy.data.images.new("_derivada", w, h, alpha=alfa)
    im.pixels.foreach_set(np.ascontiguousarray(rgba, np.float32).ravel())
    im.filepath_raw = ruta
    im.file_format = formato
    if formato == "JPEG":
        im.save(filepath=ruta, quality=92)
    else:
        im.save()
    bpy.data.images.remove(im)
    vuelta = _leer(ruta)
    canales = 4 if alfa else 3
    err = float(np.abs(vuelta[..., :canales] - rgba[..., :canales]).mean())
    assert err < 0.02, f"{ruta}: la relectura difiere {err:.4f}"
    return err


def _cobertura(modelo, w, h, dilatar=2):
    """Máscara (h, w) de los píxeles que cubren las UV de todas las mallas del glTF (fila 0 = abajo), dilatada."""
    objs, mats, imgs = _importar(modelo)
    m = np.zeros((h, w), bool)
    for o in objs:
        if o.type != "MESH":
            continue
        me = o.data
        me.calc_loop_triangles()
        uv = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers[0].data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("loops", tri)
        t = uv[tri.reshape(-1, 3)] * (w, h) - 0.5         # píxeles (centros en enteros)
        for (ax, ay), (bx, by), (cx, cy) in t:
            x0, x1 = int(max(0, math.floor(min(ax, bx, cx)))), int(min(w - 1, math.ceil(max(ax, bx, cx))))
            y0, y1 = int(max(0, math.floor(min(ay, by, cy)))), int(min(h - 1, math.ceil(max(ay, by, cy))))
            if x1 < x0 or y1 < y0:
                continue
            X, Y = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-12:
                continue
            l1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / d
            l2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / d
            e = -0.02
            dentro = (l1 >= e) & (l2 >= e) & (1 - l1 - l2 >= e)
            m[y0:y1 + 1, x0:x1 + 1] |= dentro
    _limpiar_importacion(objs, mats, imgs)
    for _ in range(dilatar):
        m = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
    return m


def derivar(modelo):
    """Genera las texturas derivadas de `modelo` y devuelve su entrada para el manifiesto."""
    R = rutas(modelo)
    os.makedirs(R["carpeta"], exist_ok=True)
    diff, arm = _leer(R["diff"]), _leer(R["arm"])
    h, w = diff.shape[:2]
    cfg = ALFA[modelo]
    entrada = {"color": os.path.relpath(R["color"], MODELOS), "normal": os.path.relpath(R["normal"], MODELOS),
               "rugosidad": os.path.relpath(R["rugosidad"], MODELOS), "alfa": None}
    rough = np.ones((h, w, 4), np.float32)
    rough[..., :3] = arm[..., 1:2]
    entrada["error_jpg_rugosidad"] = round(_guardar(rough, R["rugosidad"], "JPEG"), 4)
    if cfg is None:                                       # opaca: el color es el JPG original
        return entrada
    if cfg["metodo"] == "arm_g":
        g = arm[..., 1]
        hist = np.histogram(g, bins=64, range=(0, 1))[0]
        alfa = np.clip((cfg["umbral"] - g) / cfg["transicion"] + 0.5, 0, 1)
        entrada["pico_fondo_g"] = round((int(np.argmax(hist)) + 0.5) / 64, 3)
        if cfg["cobertura"]:
            alfa = alfa * _cobertura(modelo, w, h)
    else:
        alfa = _cobertura(modelo, w, h).astype(np.float32)
    rgba = diff.copy()
    rgba[..., 3] = alfa
    entrada["error_png_color"] = round(_guardar(rgba, R["color"], "PNG"), 4)
    entrada["alfa"] = dict(cfg, fraccion_opaca=round(float((alfa > 0.5).mean()), 4))
    return entrada


def escribir_manifiesto(derivadas):
    with open(MANIFIESTO) as fh:
        man = json.load(fh)
    man["derivadas"] = {"generador": "build/deco_plantas.py --derivar",
                        "nota": ("color con alfa (MASK) recuperado del ARM o de la cobertura de las UV, rugosidad en "
                                 "gris del canal G del ARM; el normal es el original. Ver el docstring del script."),
                        **{k: derivadas[k] for k in sorted(derivadas)}}
    tmp = MANIFIESTO + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(man, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, MANIFIESTO)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--derivar", action="store_true")
    a = ap.parse_args(argv)
    if a.derivar:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        der = {m: derivar(m) for m in MATERIAL}
        escribir_manifiesto(der)
        for m, e in der.items():
            print("DERIVADA", m, json.dumps(e, ensure_ascii=False))
        print("DERIVADAS_OK", len(der))


if __name__ == "__main__":
    main()
