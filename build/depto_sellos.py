"""Cadena de sellos de las fases del activo Depto (sin bpy: se prueba con python3 plano).

sello(N) = sha1(sello(N-1) + archivos de la fase N)[:12], recalculado siempre desde los archivos en disco.
- Cada fase exige que el maestro traiga el sello vigente de la fase anterior. Como se recalcula la cadena
  entera, tocar cualquier script previo (o depto_plano.py, que entra en la fase 1) invalida todo lo que sigue.
- Al sellarse, una fase borra los sellos de las fases posteriores: reejecutar la fase 2 sobre un maestro de
  fase 3 lo deja sin sello de fase 3, y la fase 4 aborta hasta que se reconstruya la 3.
- Las fases 2 en adelante sólo escriben el maestro que abrieron: si se abrió otra ruta (p.ej. la copia que
  muestra tools/watch_blend.py), abortan antes de tocar nada.
Prueba: build/depto_medicion/test_sellos.py (la ejecuta build/depto_run.sh).
"""
import hashlib
import os

BUILD = os.path.dirname(os.path.abspath(__file__))
MAESTRO = os.path.join(BUILD, "depto.blend")

# Archivos de cada fase, relativos a build/. Lo compartido entra en la primera fase que lo usa.
FASES = {
    "01": ("depto_01_calibracion.py", "depto_plano.py", "depto_sellos.py"),
    "02": ("depto_02_blockout.py", "depto_geom.py"),
    "03": ("depto_03_formas.py", "deco_base.py", "deco_interiores.py"),
    "04": ("depto_04_mobiliario.py", "depto_color.py", "deco_living.py", "deco_dormitorio.py", "deco_cocina_bano.py",
           "deco_objetos.py", "deco_comedor.py", "deco_hall.py"),
    "05": ("depto_05_materiales.py", "deco_paleta.py", "deco_texturas.py", "../assets/texturas/propias/manifest.json"),
    "06": ("depto_06_exportar.py",),   # no sella el maestro: el sello va en exports/manifest.json
}


def clave(fase):
    return f"depto_fase{fase}"


def _leer(nombre):
    with open(os.path.join(BUILD, nombre), "rb") as fh:
        return fh.read()


def sello(fase, leer=_leer):
    if fase not in FASES:
        raise KeyError(f"fase desconocida: {fase}")
    previo = ""
    for f in sorted(FASES):
        h = hashlib.sha1(previo.encode())
        for nombre in FASES[f]:
            h.update(leer(nombre))
        previo = h.hexdigest()[:12]
        if f == fase:
            return previo


def exigir(escena, fase_previa, ruta_abierta, leer=_leer):
    """Aborta (SystemExit) si el archivo abierto no es el maestro o no trae el sello vigente de fase_previa."""
    if os.path.abspath(ruta_abierta or "") != MAESTRO:
        raise SystemExit(f"ERROR: se abrió {ruta_abierta!r}; las fases sólo trabajan sobre el maestro {MAESTRO}.")
    esperado = sello(fase_previa, leer)
    actual = escena.get(clave(fase_previa))
    if actual != esperado:
        raise SystemExit(f"ERROR: el maestro no viene de la fase {fase_previa} vigente ({clave(fase_previa)}="
                         f"{actual!r}, esperado {esperado!r}). Ejecutar build/depto_run.sh.")


def sellar(escena, fase, leer=_leer):
    """Sella la fase y borra los sellos de las posteriores. Devuelve el sello."""
    for f in FASES:
        if f > fase and clave(f) in escena:
            del escena[clave(f)]
    escena[clave(fase)] = sello(fase, leer)
    return escena[clave(fase)]
