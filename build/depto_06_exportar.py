"""Fase 6 (exportación) del activo Depto: GLB para el recorrido web, datos de colisión del visor y manifiesto.

Uso (o todo el pipeline con build/depto_run.sh 06):
    blender -b build/depto.blend --python-exit-code 1 --python build/depto_06_exportar.py

Exige el maestro con el sello vigente de la fase 5 y no lo modifica (sólo lee y exporta). Escribe:
    exports/depto.glb                 mallas visibles (sin Depto_Ref_*, Depto_Col_*, cámaras ni luces), imágenes
                                      JPEG (en automático el GLB pesaba 17,5 MB; límite de la página: 15 MB),
                                      propiedades extra (puertas, corredera) para el visor
    exports/web/                      lo que se publica con el visor (las páginas de claude.ai no sirven .glb ni
                                      .bin): depto_gltf.json (el glTF), depto_bin.b64.txt (geometría en base64),
                                      tex/*.jpg (las imágenes tal cual) y depto_web.json (índice con tamaños). El
                                      visor arma el GLB en memoria; aquí se arma igual (armar_glb) y se reimporta.
    exports/depto_colisiones.json     cajas 2D en el plano XZ de glTF (Y arriba) para una cámara cilíndrica:
                                      estáticas, y móviles en el marco local de su nodo (hojas y corredera)
    exports/manifest.json             entrada "depto": dimensiones, triángulos, materiales, créditos, sellos
Antes de escribir prueba el recorrido con los propios datos de colisión (convertidos de vuelta al plano):
con las puertas como en el modelo se llega a los 10 recintos; con todas cerradas quedan fuera los que están
tras una puerta; con la entrada abierta se llega al palier. Así se verifica la conversión de ejes que usa el
visor. La reimportación del GLB la valida tools/validar_glb.py (lo corre build/depto_run.sh).

Ejes: Blender (x, y, z) -> glTF (x, z, -y). El frente del activo (+Y de Blender, fachada del balcón) queda
hacia -Z de glTF. Un giro en Z de Blender es el mismo giro en Y de glTF (mismo signo).
"""
import base64
import datetime
import hashlib
import json
import math
import os
import shutil
import sys

import bpy
from mathutils import Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_geom as G  # noqa: E402
import depto_plano as P  # noqa: E402
import depto_recorrido as R  # noqa: E402
import depto_sellos as SE  # noqa: E402

EXPORTS = os.path.join(RAIZ, "exports")
GLB = os.path.join(EXPORTS, "depto.glb")
COLISIONES = os.path.join(EXPORTS, "depto_colisiones.json")
WEB = os.path.join(EXPORTS, "web")
LIMITE_ARCHIVO = 15 * 1024 * 1024    # límites de la página publicada: 15 MB por binario, 16 MB por texto,
LIMITE_TEXTO = 16 * 1024 * 1024      # 255 archivos y 64 MB por versión
LIMITE_TOTAL = 60 * 1024 * 1024
LIMITE_ARCHIVOS = 240
MANIFIESTO = os.path.join(EXPORTS, "manifest.json")
TEX_MANIFIESTO = os.path.join(RAIZ, "assets", "texturas", "polyhaven", "manifest.json")
RADIO = 0.20                          # compuerta 0 / ADR 0002: radio de la cámara del tour con el mobiliario
OJO = 1.60                            # altura de los ojos (la de las cámaras de revisión)
INICIO, MIRAR = "Hall", (190, 250)    # crítico de recorrido, fase 3: hall con 0,45 m de holgura, hacia el living
DETRAS_DE_PUERTA = {"Dorm1", "Dorm2", "Bano1", "Bano2", "Paso_D1", "Paso_D2", "Balcon"}


def gl(v):
    """Punto o vector de Blender -> glTF (x, y, z) con Y arriba."""
    return (v[0], v[2], -v[1])


def r4(x):
    return round(float(x), 4)


def exportables(root):
    return [o for o in root.all_objects if o.type == "MESH" and not o.hide_render
            and not o.name.startswith(("Depto_Ref", "Depto_Col_"))]


def en_franja(z0, z1):
    return z1 > R.Z_PASO and z0 < R.Z_CABEZA


def colisiones(root):
    moviles_ob = [o for o in exportables(root) if "puerta" in o or "recorrido_m" in o]
    excluir = set(moviles_ob) | {h for o in moviles_ob for h in o.children}
    estaticos = []
    fuentes = [o for o in root.all_objects if o.type == "MESH" and not o.name.startswith("Depto_Ref")
               and ((not o.hide_render and o.get("colision") is not False) or o.get("colision") is True)]
    for o in fuentes:
        if o in excluir:
            continue
        for isla in G.islas_mundo(o):
            x0, x1, y0, y1, z0, z1 = G.aabb(isla)
            if en_franja(z0, z1):
                estaticos.append([r4(x0), r4(x1), r4(-y1), r4(-y0)])     # [xmin, xmax, zmin, zmax] en glTF
    moviles = []
    for o in moviles_ob:
        cajas = []
        # marco local del nodo (sin su giro); los hijos (manillas, vidrio de la corredera) tienen el mismo origen
        for isla in [i for ob in (o, *o.children) for i in G.islas_locales(ob)]:
            x0, x1, y0, y1, z0, z1 = G.aabb(isla)
            if en_franja(z0, z1):
                cajas.append([r4(x0), r4(x1), r4(-y1), r4(-y0)])
        m = {"nodo": o.name, "cajas_locales": cajas, "posicion": [r4(c) for c in gl(o.location)]}
        if "puerta" in o:
            m.update(tipo="bisagra", angulo=r4(o.rotation_euler.z),
                     angulo_abierto=r4(math.radians(o["angulo_abierta_deg"])), abierta=bool(o["abierta"]))
        else:
            e = gl(o["eje_apertura"])
            m.update(tipo="corredera", eje=[r4(e[0]), r4(e[2])], recorrido=r4(o["recorrido_m"]),
                     abierta=bool(o["abierta"]))
        # Contrato v2 (docs/contrato-interaccion.md): clase, etiqueta y recinto, copiados tal cual de las
        # propiedades de Blender con el mismo nombre. clase por defecto según el tipo, para los móviles antiguos
        # que no la traían explícita (puertas interiores, ventanal).
        m["clase"] = o.get("clase", "puerta" if "puerta" in o else "corredera")
        m["etiqueta"] = o.get("etiqueta", "")
        m["recinto"] = o.get("recinto", "")
        m["hijos"] = [h.name for h in o.children]
        moviles.append(m)
    return estaticos, moviles


def luces():
    """Luces de la fase 5. Contrato v2, sección 2: cada puntual trae su grupo, su color lineal y el nodo emisivo
    (ampolleta) que la representa."""
    out = []
    for o in bpy.data.objects:
        if o.type == "LIGHT" and o.name.startswith("Depto_Luz_"):
            if o.data.type == "POINT":
                out.append({"nombre": o.name, "tipo": "puntual", "posicion": [r4(c) for c in gl(o.location)],
                            "potencia_w": o.data.energy, "grupo": o.get("grupo", ""),
                            "color": [r4(c) for c in o.data.color], "ampolleta": o.get("ampolleta", "")})
            elif o.data.type == "SUN":
                d = o.matrix_world.to_3x3() @ Vector((0, 0, -1))
                out.append({"nombre": o.name, "tipo": "sol", "direccion": [r4(c) for c in gl(d)],
                            "intensidad": o.data.energy})
    return out


def interruptores(objs):
    """Contrato v2, sección 3: un registro por placa (con sus grupos; tecla = la suya si es simple, null si es doble),
    uno por tecla (su grupo) y uno por pieza de lámpara clicable (pantalla o cuerpo, sin tecla)."""
    out = []
    nombres = {o.name for o in objs}
    for o in sorted(objs, key=lambda o: o.name):
        if "grupo_luz" not in o:
            continue
        grupos = [g for g in str(o["grupo_luz"]).split(",") if g]
        if o.name.startswith("Depto_Interruptor_") and o.parent is None:
            teclas = sorted(h.name for h in o.children if h.name.endswith("_Tecla") and h.name in nombres)
            out.append({"nodo": o.name, "grupos": grupos, "tecla": teclas[0] if len(teclas) == 1 else None})
        elif o.name.endswith("_Tecla"):
            out.append({"nodo": o.name, "grupos": grupos, "tecla": o.name})
        else:
            out.append({"nodo": o.name, "grupos": grupos, "tecla": None})
    return out


def prueba_luces(datos, objs):
    """Grupos, luces e interruptores coherentes entre sí y con los nodos del GLB."""
    fallos = []
    ids = [g["id"] for g in datos["grupos_luz"]]
    nombres = {o.name for o in objs}
    puntuales = [l for l in datos["luces"] if l["tipo"] == "puntual"]
    for l in puntuales:
        if l["grupo"] not in ids:
            fallos.append(f"{l['nombre']}: grupo {l['grupo']!r} no está en grupos_luz")
        if l["ampolleta"] not in nombres:
            fallos.append(f"{l['nombre']}: la ampolleta {l['ampolleta']!r} no es un nodo exportado")
    for g in ids:
        if not any(l["grupo"] == g for l in puntuales):
            fallos.append(f"grupo {g} sin luces")
        if not any(g in i["grupos"] for i in datos["interruptores"]):
            fallos.append(f"grupo {g} sin interruptor ni lámpara")
    for i in datos["interruptores"]:
        if i["nodo"] not in nombres:
            fallos.append(f"interruptor {i['nodo']} no es un nodo exportado")
        if i["tecla"] and i["tecla"] not in nombres:
            fallos.append(f"interruptor {i['nodo']}: tecla {i['tecla']} no exportada")
        if any(g not in ids for g in i["grupos"]):
            fallos.append(f"interruptor {i['nodo']}: grupos desconocidos {i['grupos']}")
    sin_luz = [r for r in R.PUNTOS if not any(g["recinto"] == r for g in datos["grupos_luz"])]
    if sin_luz:
        fallos.append(f"recintos sin grupo de luz: {sin_luz}")
    faltan = [r for r in {**R.PUNTOS, **R.INFORMATIVOS} if r not in datos["recintos_etiquetas"]]
    if faltan:
        fallos.append(f"recintos sin etiqueta: {faltan}")
    return fallos


def punto_gl(p):
    X, Y = P.a_blender(*p)
    return [r4(X), r4(-Y)]


# ---------------------------------------------------------------------------
# Prueba de recorrido sobre los datos de colisión (lo que verá el visor), convertidos de vuelta al plano.
# ---------------------------------------------------------------------------
def a_plano_gl(x, z):
    return P.a_plano(x, -z)


def caja_a_hull(c, rot=0.0, pos=(0.0, 0.0)):
    x0, x1, z0, z1 = c
    ca, sa = math.cos(rot), math.sin(rot)
    pts = []
    for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1)):
        # giro en Y de glTF (three.js): x' = x cos + z sin ; z' = -x sin + z cos
        pts.append(a_plano_gl(pos[0] + x * ca + z * sa, pos[1] - x * sa + z * ca))
    return ("caja", pts)


def alcance(datos, estado):
    """estado: nodo -> abierta (bool). Devuelve {recinto: alcanzado}."""
    obs = [caja_a_hull(c) for c in datos["estaticos"]]
    for m in datos["moviles"]:
        ab = estado.get(m["nodo"], m["abierta"])
        px_, pz_ = m["posicion"][0], m["posicion"][2]
        if m["tipo"] == "bisagra":
            ang = m["angulo_abierto"] if ab else 0.0
            obs += [caja_a_hull(c, ang, (px_, pz_)) for c in m["cajas_locales"]]
        else:
            # la posición exportada es la del estado del modelo; cerrada = abierta − eje · recorrido
            k = 0.0 if ab == m["abierta"] else (-1.0 if m["abierta"] else 1.0)
            dx, dz = m["eje"][0] * m["recorrido"] * k, m["eje"][1] * m["recorrido"] * k
            obs += [caja_a_hull(c, 0.0, (px_ + dx, pz_ + dz)) for c in m["cajas_locales"]]
    ancho, alto = 500, 500
    bloq = R.rasterizar(obs, ancho, alto, RADIO / P.M_POR_PX)
    ini = R.PUNTOS[INICIO]
    alc = R.inundar(~bloq, (int(ini[0]), int(ini[1])))
    todos = {**R.PUNTOS, **R.INFORMATIVOS}
    return {n: R.alcanzado(alc, p) for n, p in todos.items()}


def transformar(m, c):
    """Caja local de un móvil -> aabb de mundo en XZ de glTF, con la misma fórmula que el visor (three.js)."""
    pos = (m["posicion"][0], m["posicion"][2])
    rot = m.get("angulo", 0.0) if m["tipo"] == "bisagra" else 0.0
    xs, zs = [], []
    ca, sa = math.cos(rot), math.sin(rot)
    for x, z in ((c[0], c[2]), (c[1], c[2]), (c[1], c[3]), (c[0], c[3])):
        xs.append(pos[0] + x * ca + z * sa)
        zs.append(pos[1] - x * sa + z * ca)
    return min(xs), max(xs), min(zs), max(zs)


def prueba_transformacion(datos):
    """Las cajas de cada móvil, transformadas como en el visor, deben caer sobre la pieza en Blender (±1 mm)."""
    fallos = []
    for m in datos["moviles"]:
        ob = bpy.data.objects[m["nodo"]]
        esperado = []
        for isla in [i for o in (ob, *ob.children) for i in G.islas_mundo(o)]:
            x0, x1, y0, y1, z0, z1 = G.aabb(isla)
            if en_franja(z0, z1):
                esperado.append((x0, x1, -y1, -y0))
        obtenido = [transformar(m, c) for c in m["cajas_locales"]]
        lo = lambda cs, k: min(c[k] for c in cs)   # noqa: E731
        hi = lambda cs, k: max(c[k] for c in cs)   # noqa: E731
        err = max(abs(lo(esperado, 0) - lo(obtenido, 0)), abs(hi(esperado, 1) - hi(obtenido, 1)),
                  abs(lo(esperado, 2) - lo(obtenido, 2)), abs(hi(esperado, 3) - hi(obtenido, 3)))
        if err > 0.001:
            fallos.append(f"{m['nodo']}: la transformación del visor se aparta {err * 1000:.1f} mm de Blender")
    return fallos


CLASES_MUEBLE = {"cajon", "closet", "nevera", "mueble"}  # docs/contrato-interaccion.md: no bloquean el recorrido
# Excepciones documentadas (fase "07 detalle interactivo"): el canto de estas hojas, abiertas, sí invade el paso
# frente a la pieza. Es el comportamiento esperado de un electrodoméstico o mueble real (no se circula con la
# puerta abierta); lo que sigue exigiendo la prueba es que, CERRADAS, no rompan nada (ya lo cubre `cerradas`).
EXCLUIR_ABIERTO = {
    "Depto_Mueble_Nevera_Puerta": "el paso de la cocina frente a la nevera es angosto; a más de ~50° el canto "
                                  "exterior lo tapa (medido en la prueba de recorrido de la fase 6).",
}


def prueba_muebles(datos):
    """Los móviles de clase cajón, clóset, nevera y mueble no deben romper el recorrido: se prueban cerrados (ya
    lo cubre `cerradas`, más abajo, para los que dan a un recinto detrás de puerta) y, uno por vez con los demás
    tal cual, que al abrirse no dejen inalcanzable el recinto donde están. Si alguno lo hace, hay que reducirle
    el recorrido o el ángulo, o excluirlo en EXCLUIR_ABIERTO con un comentario que explique por qué."""
    fallos = []
    for m in datos["moviles"]:
        if m.get("clase") not in CLASES_MUEBLE or m["nodo"] in EXCLUIR_ABIERTO:
            continue
        recinto = m.get("recinto")
        if recinto not in R.PUNTOS:
            continue          # sin punto de recorrido que revisar (adorno o recinto sólo informativo)
        alc = alcance(datos, {m["nodo"]: True})
        if not alc[recinto]:
            fallos.append(f"{m['nodo']} abierto deja inalcanzable {recinto}")
    return fallos


def pruebas(datos):
    fallos = prueba_transformacion(datos)
    tal_cual = alcance(datos, {})
    faltan = [n for n in R.PUNTOS if not tal_cual[n]]
    if faltan:
        fallos.append(f"con las puertas como en el modelo no se llega a {faltan}")
    cerradas = alcance(datos, {m["nodo"]: False for m in datos["moviles"]})
    abiertos = [n for n in DETRAS_DE_PUERTA if cerradas[n]]
    if abiertos:
        fallos.append(f"con todo cerrado igual se llega a {abiertos}: faltan colisiones de hojas")
    entrada = alcance(datos, {"Depto_Puerta_Entrada_Hoja": True})
    if not entrada["Palier"]:
        fallos.append("con la entrada abierta no se llega al palier")
    fallos += prueba_muebles(datos)
    return fallos, {"tal_cual": tal_cual, "todo_cerrado": cerradas, "entrada_abierta": entrada}


def exportar(objs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    os.makedirs(EXPORTS, exist_ok=True)
    comun = dict(use_selection=True, export_apply=True, export_extras=True, export_image_format="JPEG",
                 export_cameras=False, export_lights=False, export_yup=True)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", **comun)
    # Versión web: glTF separado; luego el .bin pasa a base64 (texto) y el .gltf a .json (tipos que la página sirve)
    if os.path.isdir(WEB):
        shutil.rmtree(WEB)
    os.makedirs(WEB)
    bpy.ops.export_scene.gltf(filepath=os.path.join(WEB, "depto.gltf"), export_format="GLTF_SEPARATE",
                              export_texture_dir="tex", **comun)
    with open(os.path.join(WEB, "depto.gltf")) as fh:
        gltf = json.load(fh)
    assert len(gltf["buffers"]) == 1, "se esperaba un solo buffer"
    bin_ruta = os.path.join(WEB, gltf["buffers"][0]["uri"])
    with open(bin_ruta, "rb") as fh, open(os.path.join(WEB, "depto_bin.b64.txt"), "wb") as out:
        out.write(base64.b64encode(fh.read()))
    gltf["buffers"][0]["uri"] = "depto_bin.b64.txt"          # informativo: el visor lo decodifica
    with open(os.path.join(WEB, "depto_gltf.json"), "w") as fh:
        json.dump(gltf, fh, separators=(",", ":"))
    os.remove(bin_ruta)
    os.remove(os.path.join(WEB, "depto.gltf"))
    imagenes = [{"uri": im["uri"], "bytes": os.path.getsize(os.path.join(WEB, im["uri"]))} for im in gltf.get("images", [])]
    archivos = ["depto_gltf.json", "depto_bin.b64.txt"] + [i["uri"] for i in imagenes]
    indice = {"gltf": "depto_gltf.json", "bin": "depto_bin.b64.txt", "imagenes": imagenes,
              "total_bytes": sum(os.path.getsize(os.path.join(WEB, a)) for a in archivos)}
    with open(os.path.join(WEB, "depto_web.json"), "w") as fh:
        json.dump(indice, fh, ensure_ascii=False, indent=1)
    return indice


def armar_glb(carpeta):
    """El mismo armado que hace el visor: glTF + geometría en base64 + imágenes -> GLB en memoria (bytes)."""
    with open(os.path.join(carpeta, "depto_web.json")) as fh:
        idx = json.load(fh)
    with open(os.path.join(carpeta, idx["gltf"])) as fh:
        gltf = json.load(fh)
    with open(os.path.join(carpeta, idx["bin"]), "rb") as fh:
        binario = bytearray(base64.b64decode(fh.read()))
    pad4 = lambda n: (n + 3) & ~3   # noqa: E731
    binario += b"\0" * (pad4(len(binario)) - len(binario))
    for im in gltf.get("images", []):
        with open(os.path.join(carpeta, im["uri"]), "rb") as fh:
            datos = fh.read()
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": len(binario), "byteLength": len(datos)})
        im["mimeType"] = im.get("mimeType") or ("image/png" if im["uri"].endswith(".png") else "image/jpeg")
        im["bufferView"] = len(gltf["bufferViews"]) - 1
        del im["uri"]
        binario += datos + b"\0" * (pad4(len(datos)) - len(datos))
    gltf["buffers"] = [{"byteLength": len(binario)}]
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (pad4(len(js)) - len(js))
    total = 12 + 8 + len(js) + 8 + len(binario)
    import struct
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binario), 0x004E4942) + bytes(binario))


def md5(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def main():
    scene = bpy.context.scene
    SE.exigir(scene, "05", bpy.data.filepath)
    root = bpy.data.collections["Depto"]
    bpy.context.view_layer.update()
    objs = exportables(root)
    estaticos, moviles = colisiones(root)
    grupos = json.loads(scene.get("depto_grupos_luz", "[]"))
    datos = {
        "version": 2, "unidades": "m", "ejes": "glTF: Y arriba; el balcón (frente) hacia -Z; cajas [xmin, xmax, zmin, zmax]",
        "radio": RADIO, "franja_y": [R.Z_PASO, R.Z_CABEZA], "ojo": OJO,
        "inicio": {"posicion": punto_gl(R.PUNTOS[INICIO]), "mirar": punto_gl(MIRAR)},
        "recintos": {n: punto_gl(p) for n, p in R.PUNTOS.items()},
        "estaticos": estaticos, "moviles": moviles, "luces": luces(),
        "grupos_luz": [{k: g[k] for k in ("id", "etiqueta", "recinto", "encendido")} for g in grupos],
        "interruptores": interruptores(objs),
        "recintos_etiquetas": json.loads(scene.get("depto_recintos_etiquetas", "{}")),
    }
    fallos, informe = pruebas(datos)
    fallos += prueba_luces(datos, objs)
    for f in fallos:
        print("FALLA", f)
    if fallos:
        raise SystemExit(f"ERROR: {len(fallos)} pruebas de la fase 6 fallan; no se exporta.")
    indice = exportar(objs)
    tam = os.path.getsize(GLB)
    grandes = [f"{a}: {os.path.getsize(os.path.join(WEB, a)) / 1e6:.2f} MB" for a in
               ["depto_gltf.json", "depto_bin.b64.txt"] + [i["uri"] for i in indice["imagenes"]]
               if os.path.getsize(os.path.join(WEB, a)) > (LIMITE_TEXTO if a.endswith((".json", ".txt")) else LIMITE_ARCHIVO)]
    n_arch = 4 + len(indice["imagenes"])          # + página, colisiones, índice
    if grandes or indice["total_bytes"] > LIMITE_TOTAL or n_arch > LIMITE_ARCHIVOS:
        raise SystemExit(f"ERROR: la versión web no cabe en los límites de la página: {grandes}, "
                         f"{indice['total_bytes'] / 1e6:.1f} MB, {n_arch} archivos.")
    with open(os.path.join(EXPORTS, "depto_web_armado.glb"), "wb") as fh:   # lo reimporta tools/validar_glb.py
        fh.write(armar_glb(WEB))
    with open(COLISIONES, "w") as fh:
        json.dump(datos, fh, ensure_ascii=False, separators=(",", ":"))
    shutil.copy(COLISIONES, os.path.join(WEB, "depto_colisiones.json"))

    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    tris = 0
    for o in objs:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    mats = sorted({m.name for o in objs for m in o.data.materials if m})
    with open(TEX_MANIFIESTO) as fh:
        tex = json.load(fh)
    man = {}
    if os.path.exists(MANIFIESTO):
        with open(MANIFIESTO) as fh:
            man = json.load(fh)
    man["depto"] = {
        "archivo": "depto.glb", "bytes": tam, "md5": md5(GLB),
        "web": {"carpeta": "web", "archivos": 4 + len(indice["imagenes"]), "bytes": indice["total_bytes"],
                "formato": "glTF separado: depto_gltf.json + depto_bin.b64.txt + tex/*.jpg (índice depto_web.json)"},
        "colisiones": {"archivo": "depto_colisiones.json", "bytes": os.path.getsize(COLISIONES),
                       "estaticos": len(estaticos), "moviles": len(moviles),
                       "luces": len(datos["luces"]), "grupos_luz": len(datos["grupos_luz"]),
                       "interruptores": len(datos["interruptores"])},
        "fecha": datetime.date.today().isoformat(), "fase": "06",
        "sellos": {**{f: scene.get(SE.clave(f)) for f in ("01", "02", "03", "04", "05")}, "06": SE.sello("06")},
        "origen": "piso terminado interior (Z=0), centro del rectángulo exterior sin balcón",
        "ejes": "Blender +Y (fachada del balcón) = glTF -Z; Blender Z = glTF Y",
        "dimensiones_m": {"x": r4(hi[0] - lo[0]), "y": r4(hi[1] - lo[1]), "z": r4(hi[2] - lo[2])},
        "bbox_blender_m": {"min": [r4(v) for v in lo], "max": [r4(v) for v in hi]},
        "mallas": len(objs), "triangulos": tris, "materiales": mats,
        "escala": {"m_por_px_plano": P.M_POR_PX, "incertidumbre": "±5 % (inferida de elementos estándar; sin cota real)"},
        "exportacion": {"formato": "GLB", "imagenes": "JPEG", "extras": True, "camaras": False, "luces": False,
                        "blender": bpy.app.version_string},
        "texturas": {tid: {"nombre": t["nombre"], "autores": t["autores"], "pagina": t["pagina"], "licencia": "CC0"}
                     for tid, t in tex["texturas"].items()},
        "texturas_propias": {"granito_gris_512": "generada por build/depto_05_materiales.py"},
        "prueba_recorrido": informe,
        "fuente": "ref/plano/plano_depto.png (plano del usuario); medidas en asset-brief-depto.md",
    }
    with open(MANIFIESTO, "w") as fh:
        json.dump(man, fh, indent=2, ensure_ascii=False)
    print(f"CHECK fase 6: {len(objs)} mallas, {tris} triángulos, {len(mats)} materiales; GLB {tam / 1e6:.2f} MB; "
          f"colisiones {len(estaticos)} estáticas + {len(moviles)} móviles; {len(datos['luces'])} luces en "
          f"{len(datos['grupos_luz'])} grupos, {len(datos['interruptores'])} interruptores; "
          f"recorrido: 10/10, cerrado y palier OK; "
          f"web {indice['total_bytes'] / 1e6:.1f} MB en {4 + len(indice['imagenes'])} archivos")
    print(f"FASE_OK Depto_06_exportar {len(objs)} {tris} sello={SE.sello('06')}")


if __name__ == "__main__":
    main()
