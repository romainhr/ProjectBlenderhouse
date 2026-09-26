"""Abre Blender con interfaz para MIRAR un .blend que construyen los scripts headless, sin poder pisarlo.

Uso:
    blender --python tools/watch_blend.py -- build/depto.blend [--ocultar Depto_Cielo] [--material]

Cada vez que el .blend maestro cambia en disco, lo copia a una carpeta temporal y abre la COPIA
(con las rutas relativas, p.ej. la imagen del plano, reapuntadas al proyecto). Si alguien guarda desde
la interfaz (Ctrl+S o al cerrar), se guarda la copia: el maestro sólo lo escriben los scripts de build/.
--ocultar oculta colecciones en el viewport de la copia (p.ej. el cielo, para ver el interior desde arriba).
--material usa el sombreado Material Preview (texturas y luces en Eevee) en vez de Solid. La vista se encuadra
sólo en la primera carga: las recargas siguientes conservan el punto de vista de quien mira.

Historia: la versión anterior abría el maestro directamente, y el 2026-09-25 un cierre con "guardar"
sobrescribió build/depto.blend con un estado viejo. Ver asset-brief-depto.md, Correcciones posteriores.
"""
import os
import shutil
import sys
import tempfile

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PATH = os.path.abspath(ARGS[0]) if ARGS else ""
OCULTAR = []
if "--ocultar" in ARGS:
    OCULTAR = [s.strip() for s in ARGS[ARGS.index("--ocultar") + 1].split(",") if s.strip()]
COPIA_DIR = os.path.join(tempfile.gettempdir(), "blenderhouse_watch")
COPIA = os.path.join(COPIA_DIR, "VISTA_" + os.path.basename(PATH))
LOG = os.path.join(COPIA_DIR, os.path.basename(PATH) + ".watch.log")
MATERIAL = "--material" in ARGS
_state = {"mtime": 0.0, "encuadrada": False}


def _log(msg):
    print(f"[watch] {msg}", flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def _reapuntar_rutas():
    """Las rutas '//...' del maestro son relativas a build/: en la copia se vuelven absolutas."""
    base = os.path.dirname(PATH)
    for im in bpy.data.images:
        if im.filepath.startswith("//"):
            im.filepath = os.path.normpath(os.path.join(base, im.filepath[2:]))
            im.reload()


def _preparar_vista():
    for n in OCULTAR:
        c = bpy.data.collections.get(n)
        if c:
            c.hide_viewport = True
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                for region in area.regions:
                    if region.type == "WINDOW":
                        if not _state["encuadrada"]:
                            with bpy.context.temp_override(window=win, area=area, region=region):
                                bpy.ops.view3d.view_all(center=True)
                            _state["encuadrada"] = True
                        sp = area.spaces[0]
                        if MATERIAL:
                            bpy.context.scene.render.engine = "BLENDER_EEVEE"   # (en la copia) Material Preview
                            sp.shading.type = "MATERIAL"                         # no existe con Workbench
                        else:
                            sp.shading.type = "SOLID"
                            sp.shading.color_type = "MATERIAL"
                            sp.shading.show_cavity = True
                return


def _tick():
    try:
        m = os.path.getmtime(PATH) if os.path.exists(PATH) else 0.0
        if m and m != _state["mtime"]:
            os.makedirs(COPIA_DIR, exist_ok=True)
            shutil.copy2(PATH, COPIA)
            bpy.ops.wm.open_mainfile(filepath=COPIA, load_ui=False)
            _reapuntar_rutas()
            _state["mtime"] = m          # sólo después de abrir bien: si estaba a medio escribir, se reintenta
            _log(f"recargado {PATH} (mtime={m}) como copia {COPIA}")
            bpy.app.timers.register(_preparar_vista, first_interval=0.3)
    except Exception as e:  # el maestro puede estar a medio escribir
        _log(f"error {e}")
    return 2.0


if not PATH:
    print("[watch] falta la ruta del .blend: blender --python tools/watch_blend.py -- build/depto.blend")
else:
    bpy.app.timers.register(_tick, first_interval=1.0, persistent=True)
