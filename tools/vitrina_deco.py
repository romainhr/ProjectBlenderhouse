"""Vitrina en vivo de la decoración (versión 2): Blender con interfaz que muestra todas las piezas de los módulos
build/deco_*.py en una grilla, con sus texturas, y se reconstruye sola cuando cambian los módulos o las texturas.

Uso:
    blender --python tools/vitrina_deco.py

No abre ni guarda build/depto.blend: todo vive en memoria (si alguien guarda desde la interfaz, que sea con
"Guardar como" en otra ruta). Una fila por módulo; cada pieza con su nombre en el piso. Si una pieza falla (el
módulo se está escribiendo), se muestra un rótulo "(error)" y se reintenta en el próximo cambio. Registro en
/tmp/blenderhouse_watch/vitrina.log.
"""
import importlib
import os
import sys
import tempfile
import time
import traceback

import bpy

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
PIEZAS = {   # docs/deco-industrial.md
    "deco_living": ["sofa", "cojin", "mesa_centro", "rack_tv", "tv", "mesa_lateral", "lampara_arco", "alfombra",
                    "cuadro"],
    "deco_dormitorio": ["cama", "velador", "lampara_mesa", "espejo_pie"],
    "deco_cocina_bano": ["repisa_abierta", "set_repisa", "grifo_cocina", "ducha_expuesta", "mampara",
                         "espejo_redondo", "grifo_lavabo_mural", "lavabo_concreto", "escalera_toallas", "portarrollo"],
    "deco_objetos": ["colgante_domo", "colgante_jaula", "ampolleta_edison", "aplique_brazo", "conducto", "libros",
                     "jarron", "bol", "reloj_pared"],
    "deco_comedor": ["mesa_comedor", "silla_comedor", "mesa_bistro", "silla_bistro"],
    "deco_hall": ["banca_entrada", "perchero_mural", "riel_focos", "felpudo", "riel_utensilios", "toallero_barra"],
}
CARPETA_LOG = os.path.join(tempfile.gettempdir(), "blenderhouse_watch")
LOG = os.path.join(CARPETA_LOG, "vitrina.log")
MANIFIESTO_TEX = os.path.join(RAIZ, "assets", "texturas", "propias", "manifest.json")
PASO_X, PASO_Y = 2.6, 3.2       # separación de la grilla (m)
ALTO_CIELO = 2.6                # a qué altura cuelgan las piezas de cielo (colgantes)
_estado = {"firma": None, "cambio": 0.0}


def _log(msg):
    os.makedirs(CARPETA_LOG, exist_ok=True)
    with open(LOG, "a") as fh:
        fh.write(time.strftime("%H:%M:%S ") + msg + "\n")
    print("[vitrina]", msg, flush=True)


def _firma():
    rutas = [os.path.join(RAIZ, "build", f"{m}.py") for m in PIEZAS] + [MANIFIESTO_TEX]
    return tuple(os.path.getmtime(r) if os.path.exists(r) else 0 for r in rutas)


def _limpiar():
    col = bpy.data.collections.get("Vitrina")
    if col:
        for o in list(col.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for c in list(col.children_recursive):
            bpy.data.collections.remove(c)
        bpy.data.collections.remove(col)
    for datos in (bpy.data.meshes, bpy.data.curves, bpy.data.lights):
        for d in list(datos):
            if d.users == 0:
                datos.remove(d)


def _rotulo(col, texto, x, y, error=False):
    cu = bpy.data.curves.new(f"_rot_{texto}", "FONT")
    cu.body = texto
    cu.size = 0.16
    cu.align_x = "CENTER"
    ob = bpy.data.objects.new(f"_rot_{texto}", cu)
    ob.location = (x, y - 1.1, 0.005)
    ob.color = (0.8, 0.1, 0.1, 1) if error else (0.1, 0.1, 0.1, 1)
    col.objects.link(ob)


def _estudio(col, ancho, fondo):
    import bmesh
    import deco_base as B
    import depto_geom as G
    G.MATERIALES.setdefault("_piso_vitrina", ((0.62, 0.62, 0.60), 0.8, 0.0, 1.0))
    bm = bmesh.new()
    B.caja(bm, -2, ancho + 2, -fondo - 2, 3, -0.02, 0.0)
    B.objeto(col, "_piso_vitrina", bm, "_piso_vitrina")
    sd = bpy.data.lights.new("_sol_vitrina", "SUN")
    sd.energy = 3.0
    sol = bpy.data.objects.new("_sol_vitrina", sd)
    sol.rotation_euler = (0.9, 0.0, -0.6)
    col.objects.link(sol)


def reconstruir():
    t0 = time.time()
    _limpiar()
    raiz = bpy.data.collections.new("Vitrina")
    bpy.context.scene.collection.children.link(raiz)
    import deco_paleta
    importlib.reload(deco_paleta)
    n_ok, n_err = 0, 0
    fila_max = max(len(v) for v in PIEZAS.values())
    for fila, (modulo, funciones) in enumerate(PIEZAS.items()):
        y = -fila * PASO_Y
        if not os.path.exists(os.path.join(RAIZ, "build", f"{modulo}.py")):
            _rotulo(raiz, f"{modulo}: todavía no existe", 0.0, y, error=True)
            continue
        try:
            mod = importlib.reload(sys.modules[modulo]) if modulo in sys.modules else importlib.import_module(modulo)
        except Exception as e:  # el agente puede estar a mitad de escribirlo
            _rotulo(raiz, f"{modulo}: (error al importar)", 0.0, y, error=True)
            _log(f"{modulo}: {e!r}")
            n_err += 1
            continue
        for col_i, fn in enumerate(funciones):
            x = col_i * PASO_X
            if not hasattr(mod, fn):
                _rotulo(raiz, f"{fn} (pendiente)", x, y, error=True)
                continue
            sub = bpy.data.collections.new(f"{modulo}.{fn}")
            raiz.children.link(sub)
            try:
                objs = getattr(mod, fn)(sub, f"Vitrina_{fn}")
                bpy.context.view_layer.update()
                zs = [(o.matrix_world @ v.co).z for o in objs if o.type == "MESH" for v in o.data.vertices]
                dz = ALTO_CIELO if zs and max(zs) <= 0.01 else 0.0      # colgantes: cuelgan desde z = 0
                for o in objs:
                    o.location = (o.location.x + x, o.location.y + y, o.location.z + dz)
                for m in {m for o in objs if o.type == "MESH" for m in o.data.materials if m}:
                    deco_paleta.aplicar(m.name)
                _rotulo(raiz, fn, x, y)
                n_ok += 1
            except Exception:
                _rotulo(raiz, f"{fn} (error)", x, y, error=True)
                _log(f"{modulo}.{fn}:\n{traceback.format_exc(limit=3)}")
                n_err += 1
    _estudio(raiz, (fila_max - 1) * PASO_X, (len(PIEZAS) - 1) * PASO_Y)
    _log(f"reconstruida: {n_ok} piezas, {n_err} con error, {time.time() - t0:.1f} s")


def _vista():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                sp = area.spaces[0]
                sp.shading.type = "MATERIAL"
                sp.overlay.show_floor = False
                for region in area.regions:
                    if region.type == "WINDOW" and not _estado.get("encuadrado"):
                        with bpy.context.temp_override(window=win, area=area, region=region):
                            bpy.ops.view3d.view_all(center=False)
                        _estado["encuadrado"] = True
                return


def _tick():
    try:
        f = _firma()
        ahora = time.time()
        if f != _estado["firma"]:
            if _estado["cambio"] == 0.0:
                _estado["cambio"] = ahora
            elif ahora - _estado["cambio"] > 3.0:       # esperar a que el archivo termine de escribirse
                _estado["firma"], _estado["cambio"] = f, 0.0
                reconstruir()
                bpy.app.timers.register(_vista, first_interval=0.5)
    except Exception:
        _log(traceback.format_exc(limit=3))
    return 4.0


def _inicio():
    for o in list(bpy.data.objects):                    # la escena de inicio (cubo, cámara, luz) sobra
        bpy.data.objects.remove(o, do_unlink=True)
    _log("vitrina iniciada")
    bpy.app.timers.register(_tick, first_interval=1.0, persistent=True)


bpy.app.timers.register(_inicio, first_interval=0.5)
