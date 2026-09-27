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
from mathutils import Matrix, Vector

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_03_formas as F3  # noqa: E402  (sólo constantes: F3.CLOSETS)
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
CONTRATO = "2.2"                      # versión del contrato de interacción (docs/contrato-interaccion.md); "version"
                                      # sigue siendo la mayor (2), por compatibilidad del visor. 2.2 (corrección 07c,
                                      # ronda 2): enciende / movil (luz de la nevera), alcance_m y entornos[]
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


def descendientes(o):
    """Hijos, nietos, etc. (el contenido teñido de una pieza móvil cuelga de su contenido liso: fase 07b). Todos
    comparten el origen del móvil, así que sus coordenadas locales son las del marco del móvil."""
    out = []
    for h in o.children:
        out += [h, *descendientes(h)]
    return out


def colisiones(root):
    moviles_ob = [o for o in exportables(root) if "puerta" in o or "recorrido_m" in o]
    excluir = set(moviles_ob) | {h for o in moviles_ob for h in descendientes(o)}
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
        for isla in [i for ob in (o, *descendientes(o)) for i in G.islas_locales(ob)]:
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
        # Contrato v2, sección 1 (corrección 07b): cajones detrás de una corredera. depende_de = hoja que debe estar
        # corrida para abrir el cajón; bloquea = cajones que la hoja cierra antes de moverse. Contrato 2.2 (corrección
        # 07c, ronda 2): enciende = grupos de luz que se prenden mientras la pieza está abierta (la nevera).
        for k in ("depende_de", "bloquea", "enciende"):
            if k in o:
                m[k] = [n for n in str(o[k]).split(",") if n]
        m["hijos"] = [h.name for h in o.children]
        moviles.append(m)
    return estaticos, moviles


def luces():
    """Luces de la fase 5. Contrato v2, sección 2: cada puntual trae su grupo, su color lineal y el nodo emisivo
    (ampolleta) que la representa."""
    out = []
    for o in bpy.data.objects:
        if o.type == "LIGHT" and o.name.startswith("Depto_Luz_"):
            if o.data.type in ("POINT", "SPOT"):   # SPOT: la luz lineal bajo los altos (corrección 07c, ronda 2)
                luz = {"nombre": o.name, "tipo": "puntual", "posicion": [r4(c) for c in gl(o.location)],
                       "potencia_w": o.data.energy, "grupo": o.get("grupo", ""),
                       "color": [r4(c) for c in o.data.color], "ampolleta": o.get("ampolleta", "")}
                if "cono_deg" in o:              # contrato v2.1: luz que deja salir un domo o un foco (visor)
                    luz.update(cono_deg=r4(o["cono_deg"]), direccion=[r4(c) for c in gl(Vector(o["direccion"]))])
                if "alcance_m" in o:             # contrato 2.2: distancia a la que el visor la corta (sin sombras)
                    luz["alcance_m"] = r4(o["alcance_m"])
                out.append(luz)
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
    por_nodo = {m["nodo"]: m for m in datos["moviles"]}
    for g in datos["grupos_luz"]:
        gid = g["id"]
        if not any(l["grupo"] == gid for l in puntuales):
            fallos.append(f"grupo {gid} sin luces")
        if "movil" in g:                      # contrato 2.2: lo prende un móvil al abrirse, no un interruptor
            m = por_nodo.get(g["movil"])
            if m is None or gid not in m.get("enciende", []):
                fallos.append(f"grupo {gid}: el móvil {g['movil']} no está exportado o no lo nombra en enciende")
            if g["encendido"]:
                fallos.append(f"grupo {gid}: un grupo de móvil nace apagado (la pieza nace cerrada)")
        elif not any(gid in i["grupos"] for i in datos["interruptores"]):
            fallos.append(f"grupo {gid} sin interruptor ni lámpara")
    for m in datos["moviles"]:
        for gid in m.get("enciende", []):
            if gid not in ids:
                fallos.append(f"{m['nodo']}: enciende nombra el grupo {gid}, que no existe")
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
        for isla in [i for o in (ob, *descendientes(ob)) for i in G.islas_mundo(o)]:
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
# Excepciones documentadas: móviles cuyo canto, abiertos, sí invade el paso frente a la pieza (lo que sigue exigiendo la
# prueba es que, CERRADOS, no rompan nada: ya lo cubre `cerradas`). Corrección 07c: vacía. La nevera estaba aquí hasta
# que su bisagra pasó al norte; ahora abierta deja pasar (prueba_muebles) y no toca la boca del hall (prueba_nevera).
EXCLUIR_ABIERTO = {}


def prueba_muebles(datos):
    """Los móviles de clase cajón, clóset, nevera y mueble no deben romper el recorrido: se prueban cerrados (ya
    lo cubre `cerradas`, más abajo, para los que dan a un recinto detrás de puerta) y, uno por vez con los demás
    tal cual, que al abrirse no dejen inalcanzable el recinto donde están. Si alguno lo hace, hay que reducirle
    el recorrido o el ángulo, o excluirlo en EXCLUIR_ABIERTO con un comentario que explique por qué. También:
    depende_de y bloquea sólo nombran móviles exportados y son recíprocos (cajón -> hoja que lo bloquea)."""
    fallos = []
    por_nodo = {m["nodo"]: m for m in datos["moviles"]}
    for m in datos["moviles"]:
        for k in ("depende_de", "bloquea"):
            for n in m.get(k, []):
                if n not in por_nodo:
                    fallos.append(f"{m['nodo']}: {k} nombra {n}, que no es un móvil exportado")
        for n in m.get("depende_de", []):
            if n in por_nodo and m["nodo"] not in por_nodo[n].get("bloquea", []):
                fallos.append(f"{m['nodo']} depende de {n}, pero {n} no lo bloquea")
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


# ---------------------------------------------------------------------------
# Prueba de aperturas (corrección 07c): cada hoja o cajón, abierto en el estado que permite el contrato (con las hojas
# de su depende_de corridas), no entra más de TOL_APERTURA en ninguna caja estática (mallas visibles que no son móviles)
# ni en los demás móviles en su estado de referencia: los de mueble (cajón, clóset, nevera, mueble) cerrados, y las
# puertas y el ventanal como en el modelo. Además, dos hojas de bisagra de mueble abiertas a la vez no se tocan, ni una
# hoja y un cajón del mismo recinto.
# Cada isla de malla es su caja local llevada al mundo (exacta para las piezas de cajas; giro sólo en Z) y el choque se
# mide con ejes separadores en planta y el solape en altura.
# ---------------------------------------------------------------------------
TOL_APERTURA = 0.001


def _solo_giro_z(M):
    R = M.to_3x3()
    return (abs(R[2][2] - 1.0) < 1e-6 and abs(R[0][2]) < 1e-6 and abs(R[1][2]) < 1e-6
            and abs(R.determinant() - 1.0) < 1e-5)


_ISLAS = {}      # nombre -> [(isla, aabb local)]: las islas no cambian durante la fase (el giro va en la matriz)


def _islas(o):
    if o.name not in _ISLAS:
        _ISLAS[o.name] = [(isla, G.aabb(isla)) for isla in G.islas_locales(o)]
    return _ISLAS[o.name]


def _cajas(o, M):
    """Islas de la malla de o con la matriz M -> [(4 esquinas en planta, z0, z1, aabb de mundo)]."""
    out = []
    for isla, (x0, x1, y0, y1, z0, z1) in _islas(o):
        if _solo_giro_z(M):
            esq = [(M @ Vector((x, y, 0.0)))[:2] for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
            zs = (z0 + M.translation.z, z1 + M.translation.z)
        else:
            pts = [M @ v for v in isla]
            bx0, bx1, by0, by1, bz0, bz1 = G.aabb(pts)
            esq, zs = [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], (bz0, bz1)
        xs, ys = [p[0] for p in esq], [p[1] for p in esq]
        out.append((esq, zs[0], zs[1], (min(xs), max(xs), min(ys), max(ys))))
    return out


def _pen_planta(A, B):
    """Solape mínimo de dos cuadriláteros convexos en los ejes normales a sus lados (<= 0: separados)."""
    m = float("inf")
    for Q in (A, B):
        for i in range(4):
            ex, ey = Q[(i + 1) % 4][0] - Q[i][0], Q[(i + 1) % 4][1] - Q[i][1]
            n = math.hypot(ex, ey)
            if n < 1e-9:
                continue
            nx, ny = -ey / n, ex / n
            pa, pb = [x * nx + y * ny for x, y in A], [x * nx + y * ny for x, y in B]
            m = min(m, min(max(pa), max(pb)) - max(min(pa), min(pb)))
            if m <= 0:
                return m
    return m


def _pen(a, b):
    if a[3][1] <= b[3][0] or b[3][1] <= a[3][0] or a[3][3] <= b[3][2] or b[3][3] <= a[3][2]:
        return 0.0
    dz = min(a[2], b[2]) - max(a[1], b[1])
    if dz <= 0:
        return 0.0
    return min(dz, _pen_planta(a[0], b[0]))


def _matriz_movil(o, abierta):
    """Matriz de mundo del móvil o (sin padre) abierto o cerrado, como lo mueve el visor."""
    if "puerta" in o:
        ang = math.radians(o["angulo_abierta_deg"]) if abierta else 0.0
        return Matrix.Translation(o.location) @ Matrix.Rotation(ang, 4, "Z")
    eje = Vector(o["eje_apertura"]) * o["recorrido_m"]
    cerrada = o.location - (eje if o.get("abierta") else Vector())
    return Matrix.Translation(cerrada + (eje if abierta else Vector()))


def _cajas_movil(o, M):
    """Cajas del móvil y de todo lo que cuelga de él (mismo origen), con la matriz M del móvil."""
    out = []

    def rec(ob, Mo):
        out.extend(_cajas(ob, Mo))
        for h in ob.children:
            if h.type == "MESH":
                rec(h, Mo @ h.matrix_parent_inverse @ h.matrix_basis)
    rec(o, M)
    return out


def prueba_aperturas(root):
    bpy.context.view_layer.update()
    moviles = [o for o in exportables(root) if o.parent is None and ("puerta" in o or "recorrido_m" in o)]
    propios = set(moviles) | {h for o in moviles for h in descendientes(o)}
    estaticos = [(o, c) for o in exportables(root) if o not in propios for c in _cajas(o, o.matrix_world)]
    ref = {o.name: (False if o.get("clase") in CLASES_MUEBLE else bool(o.get("abierta"))) for o in moviles}
    por_nombre = {o.name: o for o in moviles}
    cache = {}

    def cajas(o, abierta):
        k = (o.name, abierta)
        if k not in cache:
            cache[k] = _cajas_movil(o, _matriz_movil(o, abierta))
        return cache[k]
    fallos, peor = [], {}
    for m in moviles:
        estado = dict(ref)
        estado[m.name] = True
        for n in [n for n in str(m.get("depende_de", "")).split(",") if n]:
            estado[n] = True
        mias = cajas(m, True)
        caja = (min(a[3][0] for a in mias), max(a[3][1] for a in mias), min(a[3][2] for a in mias),
                max(a[3][3] for a in mias), min(a[1] for a in mias), max(a[2] for a in mias))
        cerca = [(ob, b) for ob, b in [(o.name, c) for o, c in estaticos]
                 + [(o.name, c) for o in moviles if o is not m for c in cajas(o, estado[o.name])]
                 if b[3][0] < caja[1] and caja[0] < b[3][1] and b[3][2] < caja[3] and caja[2] < b[3][3]
                 and b[1] < caja[5] and caja[4] < b[2]]
        for a in mias:
            for ob, b in cerca:
                p = _pen(a, b)
                if p > peor.get(m.name, (0.0, ""))[0]:
                    peor[m.name] = (p, ob)
        if m.name in peor and peor[m.name][0] > TOL_APERTURA:
            p, ob = peor[m.name]
            fallos.append(f"{m.name} abierto entra {p * 1000:.1f} mm en {ob}")
    # Pares abiertos a la vez: dos hojas de bisagra de mueble, y una hoja con un cajón del mismo recinto (salvo que el
    # contrato los ate con depende_de o bloquea: entonces el visor no los deja abiertos juntos).
    hojas = [o for o in moviles if "puerta" in o and o.get("clase") in CLASES_MUEBLE]
    cajones = [o for o in moviles if o.get("clase") == "cajon"]

    def atados(a, b):
        lista = lambda o, k: [n for n in str(o.get(k, "")).split(",") if n]   # noqa: E731
        return b.name in lista(a, "bloquea") + lista(a, "depende_de") or a.name in lista(b, "bloquea") + lista(b, "depende_de")
    candidatos = [(a, b) for i, a in enumerate(hojas) for b in hojas[i + 1:]]
    candidatos += [(a, b) for a in hojas for b in cajones if a.get("recinto") == b.get("recinto") and not atados(a, b)]
    pares = 0
    for a, b in candidatos:
        pa = max((_pen(x, y) for x in cajas(a, True) for y in cajas(b, True)), default=0.0)
        pares += 1
        if pa > TOL_APERTURA:
            fallos.append(f"{a.name} y {b.name} abiertos a la vez se cruzan {pa * 1000:.1f} mm")
    f_giro, inf_giro = prueba_giros(moviles, cajas)
    fallos += f_giro
    informe = {"moviles": len(moviles), "estaticos": len(estaticos), "pares_abiertos": pares,
               "max_mm": round(max((p for p, _ in peor.values()), default=0.0) * 1000, 2), "giros": inf_giro}
    return fallos, informe


# ---------------------------------------------------------------------------
# Prueba del recorrido (corrección 07c, ronda 2): la prueba de aperturas sólo miraba los estados finales, y
# PuertaLavaplatos1 atravesaba el frente de Cajon3 abierto entre 11° y 60° de su giro (18 mm; 0 mm a 95°). Aquí cada
# móvil se mueve de cerrado a abierto, en pasos de PASO_GIRO_DEG (hojas) o PASO_CORREDERA_M (cajones y correderas), y
# en cada paso no puede entrar más de TOL_APERTURA en los demás móviles de su recinto, en los estados en que el visor
# los puede dejar mientras se mueve (bloqueos.js): lo que nombra en `bloquea`, cerrado (el visor lo cierra antes); lo
# que nombra en `depende_de`, abierto; si tiene `depende_de`, las hojas que lo nombran en `bloquea`, cerradas; el resto,
# abierto y cerrado.
# ---------------------------------------------------------------------------
PASO_GIRO_DEG = 2.0
PASO_CORREDERA_M = 0.02


def _recorrido(o):
    """[(matriz de mundo, texto)] del móvil o (sin padre) de cerrado a abierto, ambos incluidos."""
    if "puerta" in o:
        amax = o["angulo_abierta_deg"]
        n = max(1, math.ceil(abs(amax) / PASO_GIRO_DEG))
        return [(Matrix.Translation(o.location) @ Matrix.Rotation(math.radians(amax * k / n), 4, "Z"),
                 f"a {abs(amax) * k / n:.0f}°") for k in range(n + 1)]
    eje = Vector(o["eje_apertura"]) * o["recorrido_m"]
    cerrada = o.location - (eje if o.get("abierta") else Vector())
    n = max(1, math.ceil(o["recorrido_m"] / PASO_CORREDERA_M))
    return [(Matrix.Translation(cerrada + eje * (k / n)), f"a {o['recorrido_m'] * k / n * 100:.0f} cm")
            for k in range(n + 1)]


def _estados_permitidos(m, o):
    lista = lambda x, k: [n for n in str(x.get(k, "")).split(",") if n]   # noqa: E731
    if o.name in lista(m, "bloquea"):
        return (False,)
    if o.name in lista(m, "depende_de"):
        return (True,)
    if lista(m, "depende_de") and m.name in lista(o, "bloquea"):
        return (False,)
    return (False, True)


def prueba_giros(moviles, cajas):
    fallos, peor, pasos = [], {}, 0
    for m in moviles:
        otros = [(o, est) for o in moviles if o is not m and o.get("recinto") and o.get("recinto") == m.get("recinto")
                 for est in _estados_permitidos(m, o)]
        obst = [(o.name, est, b) for o, est in otros for b in cajas(o, est)]
        if not obst:
            continue
        for M, etq in _recorrido(m):
            pasos += 1
            mias = _cajas_movil(m, M)
            caja = (min(a[3][0] for a in mias), max(a[3][1] for a in mias), min(a[3][2] for a in mias),
                    max(a[3][3] for a in mias), min(a[1] for a in mias), max(a[2] for a in mias))
            cerca = [(n, est, b) for n, est, b in obst
                     if b[3][0] < caja[1] and caja[0] < b[3][1] and b[3][2] < caja[3] and caja[2] < b[3][3]
                     and b[1] < caja[5] and caja[4] < b[2]]
            for a in mias:
                for n, est, b in cerca:
                    p = _pen(a, b)
                    if p > peor.get(m.name, (0.0,))[0]:
                        peor[m.name] = (p, n, est, etq)
        if m.name in peor and peor[m.name][0] > TOL_APERTURA:
            p, n, est, etq = peor[m.name]
            fallos.append(f"{m.name} al moverse ({etq}) entra {p * 1000:.1f} mm en {n} "
                          f"{'abierto' if est else 'cerrado'}")
    return fallos, {"pasos": pasos, "max_mm": round(max((v[0] for v in peor.values()), default=0.0) * 1000, 2)}


def prueba_nevera(root):
    """Corrección 07c: la hoja de la nevera abierta queda en la cocina, a >= RADIO de la boca entre el hall y la cocina
    (la cara norte de T_COC_S, y = COC_N, de T3 al remate COC_W). Devuelve (fallos, distancia en m)."""
    o = bpy.data.objects["Depto_Mueble_Nevera_Puerta"]
    ys = [P.a_plano(*p[:2])[1] for c in _cajas_movil(o, _matriz_movil(o, True)) for p in c[0]]
    xs = [P.a_plano(*p[:2])[0] for c in _cajas_movil(o, _matriz_movil(o, True)) for p in c[0]]
    d = (P.Y["COC_N"] - max(ys)) * P.M_POR_PX
    fallos = []
    if d < RADIO:
        fallos.append(f"la nevera abierta queda a {d:.2f} m de la boca hall-cocina (mínimo {RADIO})")
    return fallos, {"distancia_boca_m": round(d, 3), "x_px": [round(min(xs), 1), round(max(xs), 1)],
                    "y_px": [round(min(ys), 1), round(max(ys), 1)]}


def prueba_closets(datos):
    """Corrección 07c: la huella de cada clóset del plano (x0..x1, del fondo al frente CL*) está cubierta por las cajas
    estáticas de colisión (lo que dibuja el minimapa y choca en el visor), muestreada cada 2 cm."""
    fallos, cub = [], {}
    for cid, x0, x1, yf, yfr in F3.CLOSETS:
        a, b = P.a_blender(x0, yf), P.a_blender(x1, yfr)
        gx = sorted((a[0], b[0]))
        gz = sorted((-a[1], -b[1]))
        pts = [(gx[0] + 0.01 + 0.02 * i, gz[0] + 0.01 + 0.02 * k)
               for i in range(int((gx[1] - gx[0] - 0.02) / 0.02) + 1) for k in range(int((gz[1] - gz[0] - 0.02) / 0.02) + 1)]
        dentro = sum(any(c[0] <= x <= c[1] and c[2] <= z <= c[3] for c in datos["estaticos"]) for x, z in pts)
        cub[cid] = round(dentro / len(pts), 4)
        if cub[cid] < 0.999:
            fallos.append(f"clóset {cid}: la colisión cubre sólo el {cub[cid] * 100:.1f} % de su huella")
    return fallos, cub


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


# ---------------------------------------------------------------------------
# Entorno local de la cocina (corrección 07c, ronda 2; contrato 2.2, sección 6). El visor usaba para todos los
# materiales el RoomEnvironment de three.js (un estudio genérico con cajas y paneles): con rugosidad 0,25-0,35 la nevera
# reflejaba cajas que no existen en la cocina (nubes oscuras de 7-15 cm en la puerta) y la visera de la campana se leía
# como latón. Aquí se renderiza en Cycles (CPU, pocas muestras) un equirectangular de la cocina desde ENTORNO["centro"],
# con las luces que nacen encendidas (el estado de la tarde en el visor), y se publica junto al modelo; el visor lo usa
# como envMap de ENTORNO["materiales"] en las mallas dentro de ENTORNO["caja"].
# ---------------------------------------------------------------------------
ENTORNO = dict(
    id="cocina", archivo="tex/entorno_cocina.jpg", archivo_dia="tex/entorno_cocina_dia.jpg", resolucion=(512, 256),
    muestras=48,
    centro=(360.0, 235.0), z=1.30,          # diseño: px del plano y m; centro de la cocina, a media altura entre la
                                            # cubierta y los altos (el tramo de la nevera y la visera)
    caja=(P.X["T3_E"], P.X["E_FORRO"], P.Y["T5_S"], P.Y["COC_N"]),   # recinto Cocina del plano (px): mallas de los
                                            # materiales de abajo cuyo centro cae aquí
    materiales=("Depto_Mat_NeveraAcero", "Depto_Mat_Acero", "Depto_Mat_AceroInox"),
    grupo="cocina_techo",                   # la luz del recinto: encendida, el visor usa la variante «luces»; apagada, «dia»
    percentil=0.97, blanco=0.90,            # escala: el 97 % de los píxeles queda bajo 0,90 lineal (el resto, las
                                            # ampolletas y la ventana, se recorta en el JPEG de 8 bits)
)


def entorno_cocina(scene, grupos):
    """Renderiza ENTORNO en dos variantes, «luces» (los grupos que nacen encendidos: tarde y noche del visor) y «dia»
    (sólo el sol y el cielo), en exports/web/, y devuelve su registro del contrato (sección 6). Con una sola variante,
    la de las luces, de día el acero reflejaba una cocina alumbrada a 2700-3000 K y la visera se veía de latón junto al
    azulejo neutro. No guarda el .blend: la fase 6 no modifica el maestro."""
    E_ = ENTORNO
    apagados = {g["id"] for g in grupos if not g.get("encendido")}
    previo = {o.name: o.hide_render for o in bpy.data.objects if o.type == "LIGHT"}
    escalas = {}
    # de día también se apaga el emisivo de las ampolletas: en Cycles una malla emisiva alumbra (la luz lineal bajo los
    # altos seguía encendida en la variante del día)
    bsdf = bpy.data.materials["Depto_Mat_Bombilla"].node_tree.nodes.get("Principled BSDF")
    emision = bsdf.inputs["Emission Strength"].default_value
    for variante, archivo in (("luces", E_["archivo"]), ("dia", E_["archivo_dia"])):
        for o in bpy.data.objects:
            if o.type == "LIGHT" and o.name.startswith("Depto_Luz_") and o.data.type != "SUN":
                o.hide_render = previo[o.name] or variante == "dia" or o.get("grupo") in apagados
        bsdf.inputs["Emission Strength"].default_value = 0.0 if variante == "dia" else emision
        escalas[variante] = _render_entorno(scene, archivo)
    bsdf.inputs["Emission Strength"].default_value = emision
    for n, h in previo.items():
        bpy.data.objects[n].hide_render = h
    x0, x1, y0, y1 = E_["caja"]
    a, b = P.a_blender(x0, y0), P.a_blender(x1, y1)
    reg = {"id": E_["id"], "imagen": E_["archivo"], "imagenes": {"luces": E_["archivo"], "dia": E_["archivo_dia"]},
           "centro": [r4(c) for c in gl(Vector((*P.a_blender(*E_["centro"]), E_["z"])))],
           "caja": [r4(min(a[0], b[0])), r4(max(a[0], b[0])), r4(min(-a[1], -b[1])), r4(max(-a[1], -b[1]))],
           "alto": [0.0, r4(P.ALTURA_PISO_CIELO)],     # y de glTF: piso y cielo (proyección en caja del visor)
           "materiales": list(E_["materiales"]), "grupo": E_["grupo"], "escala": {k: r4(v) for k, v in escalas.items()},
           "muestras": E_["muestras"], "luces": "luces: grupos que nacen encendidos; dia: sólo el sol y el cielo"}
    print("CHECK entorno local:", reg, {k: f"{os.path.getsize(os.path.join(WEB, v)) / 1e3:.0f} kB"
                                        for k, v in reg["imagenes"].items()})
    return reg


def _render_entorno(scene, archivo):
    """Un equirectangular de ENTORNO en Cycles hacia exports/web/<archivo>; devuelve la escala aplicada."""
    import numpy as np
    E_ = ENTORNO
    cd = bpy.data.cameras.new("_Entorno")
    cd.type = "PANO"
    cd.cycles.panorama_type = "EQUIRECTANGULAR"          # Blender 3.6: en los ajustes de Cycles de la cámara
    cam = bpy.data.objects.new("_Entorno", cd)
    scene.collection.objects.link(cam)
    cam.location = (*P.a_blender(*E_["centro"]), E_["z"])
    cam.rotation_euler = (math.pi / 2, 0.0, -math.pi / 2)     # adelante = +X de Blender (+X de glTF), arriba = +Z
    r = scene.render
    r.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = E_["muestras"]
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 4
    r.resolution_x, r.resolution_y = E_["resolucion"]
    r.resolution_percentage = 100
    r.image_settings.file_format = "OPEN_EXR"
    r.image_settings.color_depth = "32"
    scene.camera = cam
    tmp = os.path.join(bpy.app.tempdir or "/tmp", "_entorno_cocina.exr")
    r.filepath = tmp
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(tmp)
    px = np.array(im.pixels[:], dtype=np.float32).reshape(-1, 4)
    lum = px[:, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    escala = E_["blanco"] / max(float(np.quantile(lum, E_["percentil"])), 1e-6)
    px[:, :3] *= escala
    im.pixels.foreach_set(px.ravel())
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    r.image_settings.file_format = "JPEG"
    r.image_settings.quality = 92
    r.image_settings.color_mode = "RGB"
    ruta = os.path.join(WEB, archivo)
    im.save_render(ruta, scene=scene)
    bpy.data.images.remove(im)
    bpy.data.objects.remove(cam)
    return escala


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
        "version": 2, "contrato": CONTRATO, "unidades": "m", "ejes": "glTF: Y arriba; el balcón (frente) hacia -Z; cajas [xmin, xmax, zmin, zmax]",
        "radio": RADIO, "franja_y": [R.Z_PASO, R.Z_CABEZA], "ojo": OJO,
        "inicio": {"posicion": punto_gl(R.PUNTOS[INICIO]), "mirar": punto_gl(MIRAR)},
        "recintos": {n: punto_gl(p) for n, p in R.PUNTOS.items()},
        "estaticos": estaticos, "moviles": moviles, "luces": luces(),
        "grupos_luz": [{k: g[k] for k in ("id", "etiqueta", "recinto", "encendido", "kelvin", "movil") if k in g}
                       for g in grupos],
        "interruptores": interruptores(objs),
        "recintos_etiquetas": json.loads(scene.get("depto_recintos_etiquetas", "{}")),
    }
    fallos, informe = pruebas(datos)
    fallos += prueba_luces(datos, objs)
    f_ap, informe["aperturas"] = prueba_aperturas(root)
    f_nev, informe["nevera_abierta"] = prueba_nevera(root)
    f_cl, informe["closets_cubiertos"] = prueba_closets(datos)
    fallos += f_ap + f_nev + f_cl
    print("CHECK aperturas:", informe["aperturas"], "nevera:", informe["nevera_abierta"],
          "clósets cubiertos:", informe["closets_cubiertos"])
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
    datos["entornos"] = [entorno_cocina(scene, grupos)]
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
