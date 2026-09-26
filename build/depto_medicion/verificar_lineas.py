"""Verifica cada cara de muro del blockout contra el plano: centro de línea real vs. coordenada declarada.

Uso:
    python3 build/depto_medicion/verificar_lineas.py

Para cada muro de build/depto_02_blockout.py (sin cargar Blender: se leen los rectángulos del script
mediante un bpy simulado), toma sus dos caras largas y, en 9 posiciones a lo largo del muro (fuera de
los vanos), busca el trazo negro más cercano (v < 110) en ±4 px y calcula su centroide de oscuridad.
Informa el desvío mediano por cara. Un desvío > 1 px indica una coordenada mal leída en la Fase 0.
Además, sondas explícitas: jambas, remates y shafts (depto_plano.py) y, desde la fase 3, las líneas px de
cocina y baños que usa build/depto_03_formas.py (trazos grises, con su propio umbral).
Salida: build/depto_medicion/verificacion_lineas.json
"""
import json
import os
import statistics
import sys
import types

from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "build"))
# bpy/bmesh/mathutils simulados: sólo se necesitan las constantes de los scripts de las fases 2 y 3
for mod in ("bpy", "bmesh", "mathutils"):
    m = types.ModuleType(mod)
    m.Vector = m.Matrix = object
    sys.modules[mod] = m
import importlib.util  # noqa: E402


def cargar(nombre, archivo):
    spec = importlib.util.spec_from_file_location(nombre, os.path.join(RAIZ, "build", archivo))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


blk = cargar("blk", "depto_02_blockout.py")
f3 = cargar("f3", "depto_03_formas.py")      # constantes px de la fase 3 (cocina y baños)

OSCURO = 110
BUSQUEDA = 4.0
VENTANA = 1.3
plano = Image.open(os.path.join(RAIZ, "ref", "plano", "plano_depto.png")).convert("L")
px = plano.load()


def perfil(fijo, eje_x, lo, hi, umbral=OSCURO):
    """Oscuridad bajo `umbral` a lo largo de la perpendicular, en la fila/columna `fijo`."""
    out = []
    for i in range(int(lo), int(hi) + 1):
        v = px[i, fijo] if eje_x else px[fijo, i]
        out.append((i + 0.5, max(0, umbral - v)))   # centro del píxel i en coordenadas continuas
    return out


def centro_cercano(pos, fijo, perp_es_x, umbral=OSCURO):
    prof = perfil(fijo, perp_es_x, pos - BUSQUEDA - 1, pos + BUSQUEDA + 1, umbral)
    cand = [(abs(c - pos), c) for c, w in prof if w > 0 and abs(c - pos) <= BUSQUEDA]
    if not cand:
        return None
    pico = min(cand)[1]
    sel = [(c, w) for c, w in prof if abs(c - pico) <= VENTANA]
    tot = sum(w for _, w in sel)
    return sum(c * w for c, w in sel) / tot if tot else None


resultados, malos = [], []
for nombre, x0, x1, y0, y1, vanos, _ in blk.MUROS:
    eje_x = (x1 - x0) >= (y1 - y0)       # muro horizontal en el plano: caras en y0 e y1
    ini, fin = (x0, x1) if eje_x else (y0, y1)
    libres = [(a, b) for a, b, *_ in vanos]
    muestras = [ini + (fin - ini) * t for t in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
    muestras = [u for u in muestras if not any(a - 2 <= u <= b + 2 for a, b in libres)]
    for cara, pos in (("min", y0 if eje_x else x0), ("max", y1 if eje_x else x1)):
        desv = []
        for u in muestras:
            c = centro_cercano(pos, int(u), perp_es_x=not eje_x)
            if c is not None:
                desv.append(c - pos)
        med = statistics.median(desv) if desv else None
        r = {"muro": nombre, "cara": cara, "coord_px": round(pos, 2), "n": len(desv),
             "desvio_mediano_px": None if med is None else round(med, 2)}
        resultados.append(r)
        if med is None or abs(med) > 1.0:
            malos.append(r)

# Sondas explícitas: jambas, remates, shafts y caras cortas que el recorrido de caras largas no cubre.
# (nombre, eje de la coordenada 'x' o 'y', clave en depto_plano, rango de muestreo en el otro eje)
X, Y = blk.P.X, blk.P.Y
SONDAS = [
    ("jamba V_D1_A", "y", "V_D1_A", (116, 126)), ("jamba V_D1_B", "y", "V_D1_B", (116, 126)),
    ("jamba VEN_A", "y", "VEN_A", (116, 126)), ("jamba VEN_B", "y", "VEN_B", (116, 126)),
    ("jamba V_D2_A", "y", "V_D2_A", (116, 126)), ("jamba V_D2_B", "y", "V_D2_B", (116, 126)),
    ("jamba V_B1_A", "x", "V_B1_A", (16, 24)), ("jamba V_B1_B", "x", "V_B1_B", (16, 24)),
    ("jamba ENT_N", "y", "ENT_N", (422, 429)), ("jamba ENT_S", "y", "ENT_S", (422, 429)),
    ("jamba T4_A", "y", "T4_A", (338, 341)), ("jamba T4_B", "y", "T4_B", (338, 341)),
    ("jamba T10_A", "y", "T10_A", (340, 343)), ("jamba T10_B", "y", "T10_B", (340, 343)),
    ("remate JAMBA_D (D1)", "x", "JAMBA_D", (171, 173)), ("remate T3_C", "y", "T3_C", (290, 293)),
    ("remate T3_D", "y", "T3_D", (290, 293)), ("remate COC_W", "x", "COC_W", (299, 304)),
    ("shaft SH1_N", "y", "SH1_N", (398, 416)), ("shaft SH1_S", "y", "SH1_S", (398, 416)),
    ("shaft SH1_W", "x", "SH1_W", (133, 146)), ("shaft SH1_WI", "x", "SH1_WI", (133, 146)),
    ("shaft SH2_N", "y", "SH2_N", (396, 418)), ("shaft SH2_S", "y", "SH2_S", (396, 418)),
    ("shaft SH2_W", "x", "SH2_W", (452, 474)), ("shaft SH2_WI", "x", "SH2_WI", (452, 474)),
    ("cara E_I tramo Baño 2", "x", "E_I", (372, 440)), ("cara E_FORRO cocina", "x", "E_FORRO", (160, 290)),
    ("cara E_O tramo Baño 2", "x", "E_O", (372, 470)),
    # Líneas grises (frentes de closet, barandas): umbral 200 para separarlas del relleno gris claro (~222)
    ("frente closet CL1_N", "y", "CL1_N", (298, 334), 200), ("frente closet CL1_S", "y", "CL1_S", (298, 334), 200),
    ("frente closet CL2_N", "y", "CL2_N", (298, 336), 200), ("frente closet CL2_S", "y", "CL2_S", (298, 336), 200),
    # Barandas: dos líneas finas paralelas; el eje es el centroide de ambas (modo "doble", ventana ±3 px)
    ("baranda BARANDA_O", "x", "BARANDA_O", (180, 320), 235, "doble"),
    ("baranda BARANDA_N", "y", "BARANDA_N", (65, 110), 235, "doble"),
    ("baranda BARANDA_S", "y", "BARANDA_S", (65, 110), 235, "doble"),
]
# Fase 3: líneas de cocina y baños que usa build/depto_03_formas.py (valor numérico en lugar de clave).
# Son trazos grises finos (190-230 en el PNG, fondo >= 245): umbral 235. Rangos de muestreo elegidos para no
# cruzar otros trazos a ±4 px (quemadores del anafe, desagüe, escurridor, WC).
F3 = 235
SONDAS += [
    ("cocina lavaplatos O", "x", f3.BACHA[0], (197, 215), F3), ("cocina lavaplatos E", "x", f3.BACHA[1], (197, 215), F3),
    ("cocina lavaplatos N", "y", f3.BACHA[2], (395, 409), F3), ("cocina lavaplatos S", "y", f3.BACHA[3], (395, 409), F3),
    ("cocina torre N", "y", f3.TORRE_Y[0], (391, 415)), ("cocina torre S", "y", f3.TORRE_Y[1], (391, 415)),
    ("cocina frente tramo N", "y", f3.COC_FRENTE_Y, (298, 320), F3),
    ("cocina frente tramo E", "x", f3.COC_FRENTE_X, (192, 224), F3),
    ("cocina altos N (discontinua)", "y", f3.ALTOS_Y, (298, 322), F3),
    ("cocina altos E (discontinua)", "x", f3.ALTOS_X, (219, 226), F3),
    ("cocina anafe O", "x", f3.ANAFE[0], (159, 174), F3), ("cocina anafe E", "x", f3.ANAFE[1], (159, 174), F3),
    ("cocina anafe N", "y", f3.ANAFE[2], (330, 354), F3), ("cocina anafe S", "y", f3.ANAFE[3], (330, 354), F3),
    ("baño 1 repisa", "x", f3.BANOS["B1"]["repisa"][0], (100, 120), F3),
    # sobre la tina hay otro trazo gris en x≈409 (borde interior de la tina): umbral 200 para la discontinua
    ("baño 2 ducto (discontinua)", "x", f3.BANOS["B2"]["ducto"][0], (371, 402), 200),
]
# Caras sin trazo propio en el plano (contacto interno): se informan pero no hacen fallar la verificación.
EXCLUIR = {
    ("Depto_Muro_Este_Forro", "max"): "cara de contacto forro/muro este: en el Baño 1 la banda 418-421 es negra continua",
}
for sonda in SONDAS:
    nombre, eje, clave, (lo, hi) = sonda[:4]
    umbral = sonda[4] if len(sonda) > 4 else OSCURO
    doble = len(sonda) > 5 and sonda[5] == "doble"
    pos = clave if isinstance(clave, (int, float)) else (X if eje == "x" else Y)[clave]
    clave = clave if isinstance(clave, str) else f"{pos:.2f}"
    desv = []
    for u in range(lo, hi + 1):
        if doble:
            prof = perfil(u, eje == "x", pos - 3, pos + 3, umbral)
            tot = sum(w for _, w in prof)
            c = sum(cc * w for cc, w in prof) / tot if tot else None
        else:
            c = centro_cercano(pos, u, perp_es_x=(eje == "x"), umbral=umbral)
        if c is not None:
            desv.append(c - pos)
    med = statistics.median(desv) if desv else None
    r = {"muro": nombre, "cara": clave, "coord_px": round(pos, 2), "n": len(desv),
         "desvio_mediano_px": None if med is None else round(med, 2)}
    resultados.append(r)
    if med is None or abs(med) > 1.0:
        malos.append(r)

excluidos = [r for r in malos if (r["muro"], r["cara"]) in EXCLUIR]
malos = [r for r in malos if (r["muro"], r["cara"]) not in EXCLUIR]
for r in resultados:
    marca = "  <-- REVISAR" if r in malos else ("  (excluida: " + EXCLUIR[(r["muro"], r["cara"])] + ")"
                                               if (r["muro"], r["cara"]) in EXCLUIR else "")
    print(f"{r['muro']:28s} {r['cara']} {r['coord_px']:7.2f}  n={r['n']}  desvío={r['desvio_mediano_px']}{marca}")
with open(os.path.join(RAIZ, "build", "depto_medicion", "verificacion_lineas.json"), "w") as f:
    json.dump({"caras": resultados, "desvios_mayores_a_1px": malos,
               "excluidas": [dict(r, motivo=EXCLUIR[(r["muro"], r["cara"])]) for r in excluidos]},
              f, indent=2, ensure_ascii=False)
print("VERIFICACION", len(resultados), "caras;", len(malos), "con desvío > 1 px o sin trazo;", len(excluidos), "excluidas")
if malos:
    raise SystemExit(1)
