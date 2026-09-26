"""Fase 4 (mobiliario) del activo Depto: camas, veladores, sofá, mesa de centro, alfombra, mueble de TV y pouf.

Uso (o todo el pipeline con build/depto_run.sh 04):
    blender -b build/depto.blend --python-exit-code 1 --python build/depto_04_mobiliario.py

Idempotente: exige que se haya abierto el maestro con el sello vigente de la fase 3 (cadena de
build/depto_sellos.py), borra y reconstruye sólo su colección (Depto_Mobiliario) y no modifica objetos de
otras fases. Antes de guardar prueba (si algo falla, no guarda): cada mueble contra su bbox del plano,
ninguna pieza que penetre muros, artefactos u otros muebles (> 1 mm), cámaras a ≥ 0,20 m de todo sólido y
presupuesto de triángulos. El recorrido con muebles lo prueba build/depto_recorrido.py (radio 0,20 m).
Sella scene["depto_fase04"] y borra los sellos posteriores.

Orígenes (etiqueta en el comentario, como en la fase 3): extracción = bbox de la Fase 0 en bordes de trazo
(build/depto_medicion/extraccion_px_bordes.json); aquí se usa 0,5 px hacia adentro por lado para quedar en el
centro del trazo (brief, decisión 5). brief = tabla de mobiliario del brief. supuesto = medida usual.
"""
import json
import os
import sys

import bpy

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_geom as G  # noqa: E402
import depto_plano as P  # noqa: E402
import depto_sellos as SE  # noqa: E402
from depto_geom import Pieza, px  # noqa: E402

COL = "Depto_Mobiliario"
EXTRACCION = os.path.join(RAIZ, "build", "depto_medicion", "extraccion_px_bordes.json")
TRAZO = 0.5                   # px: de borde de trazo (extracción) a centro de trazo

# ---------------------------------------------------------------------------
# Dormitorios
# ---------------------------------------------------------------------------
CAMA = dict(ancho=1.80, largo=2.00, alto=0.55)   # brief: king de 1,80 × 2,00 (dibujada 1,84 × 1,99), alto inferido
CAMA_BASE_Z = (0.08, 0.30)    # supuesto: zócalo retranqueado y base tapizada; colchón de 0,30 a 0,55
CAMA_CABECERO = (0.06, 1.10)  # supuesto: espesor y alto del cabecero
ALMOHADA = (0.70, 0.40, 0.12)  # supuesto: ancho, fondo, alto (el plano dibuja dos)
COBERTOR = dict(desde=0.60, vuelo=0.02, baja=0.22)   # supuesto: cubre desde 0,60 de la cabecera y cae 0,22
CAMAS = {
    # cx: centro en x del bbox de la extracción (156-255); y_cab: borde del lado de la cabecera; s: hacia los pies
    "D1": dict(cx=205.5, y_cab=31.0, s=+1),       # extracción: cabecera al norte (almohadas y 44-71)
    "D2": dict(cx=205.5, y_cab=471.5, s=-1),      # extracción: cabecera al sur (almohadas y 431-457)
}
VELADOR = (0.40, 0.38, 0.55)  # brief: 0,40 × 0,38 × 0,55 (dibujados de 0,30 a 0,34 de ancho, asimétricos)
VELADOR_PATA = (0.03, 0.10)   # supuesto: lado y alto de las patas
VELADORES_Y = {"D1": (29.0, +1), "D2": (474.5, -1)}   # extracción: borde del lado del muro y sentido

# ---------------------------------------------------------------------------
# Living (todo apoya sobre la alfombra, que asoma bajo el mueble de TV, la mesa y el sofá)
# ---------------------------------------------------------------------------
ALFOMBRA = (148.0 + TRAZO, 267.0 - TRAZO, 193.0 + TRAZO, 301.5 - TRAZO)   # extracción
ALFOMBRA_ALTO = 0.008         # supuesto
SOFA = dict(ancho=1.55, fondo=0.80, alto=0.85,   # brief (dibujado 1,53 × 0,76, dos cuerpos)
            cx=(161.5 + 244.0) / 2, y_resp=323.0,  # extracción: centro en x y respaldo al sur (y 313-323)
            junta=201.5,                          # extracción: cojines divididos en x≈201,5
            brazo=0.15, respaldo=0.20, asiento_z=(0.30, 0.45), brazo_alto=0.62, base_z=0.08)   # supuesto
MESA_CENTRO = dict(bbox=(174.0 + TRAZO, 230.0 - TRAZO, 225.0 + TRAZO, 259.0 - TRAZO),   # extracción
                   alto=0.40, cubierta=0.04, pata=0.05, retiro=0.03)                      # supuesto
MUEBLE_TV = dict(bbox=(171.0, 233.0, 183.0, 202.0),   # brief: 1,18 × 0,36 (extracción 170-234 × 182-203)
                 alto=0.45, zocalo=0.10, puertas=3)   # supuesto
TV = dict(x=(182.0, 221.0), yc=187.5,                  # extracción: TV dibujada x 182-221, y 185-190
          alto=0.42, esp=0.04, pie=(0.30, 0.12, 0.02), cuello=0.08)   # supuesto: 16:9 de 0,74 de ancho
POUF = dict(bbox=(136.0 + TRAZO, 158.0 - TRAZO, 288.0 + TRAZO, 313.5 - TRAZO), alto=0.42)   # extracción; alto supuesto

TOL_PENETRACION = 0.001
HOLGURA_CAMARA = 0.20
# Contraste con la extracción: bordes a <= TOL_BBOX px, salvo las medidas decididas en el brief, donde se
# exige el centro a <= TOL_BBOX px y se informa la diferencia de tamaño.
TOL_BBOX = 2.5
CONTRASTE = [
    # (objetos que forman el mueble, nombre en la extracción, criterio)
    (("Depto_Mueble_D1_Cabecero", "Depto_Mueble_D1_Cama"), "Cama D1", "bordes"),
    (("Depto_Mueble_D2_Cabecero", "Depto_Mueble_D2_Cama"), "Cama D2", "bordes"),
    (("Depto_Mueble_D1_VeladorO",), "Velador izq. D1", "centro"), (("Depto_Mueble_D1_VeladorE",), "Velador der. D1", "centro"),
    (("Depto_Mueble_D2_VeladorO",), "Velador izq. D2", "centro"), (("Depto_Mueble_D2_VeladorE",), "Velador der. D2", "centro"),
    (("Depto_Mueble_Sofa",), "Sofá 2 cuerpos", "bordes"), (("Depto_Mueble_MesaCentro",), "Mesa de centro", "bordes"),
    (("Depto_Mueble_TV_Mueble", "Depto_Mueble_TV_Frentes"), "Mueble TV", "bordes"),
    (("Depto_Mueble_Alfombra",), "Alfombra", "bordes"), (("Depto_Mueble_Pouf",), "Pouf / mesa lateral", "bordes"),
]


def cama(col, did, c):
    cx, yh, s = c["cx"], c["y_cab"], c["s"]
    x0, x1 = cx - px(CAMA["ancho"]) / 2, cx + px(CAMA["ancho"]) / 2
    L = px(CAMA["largo"])

    def y(m):                                     # distancia desde la cabecera (m) -> y del plano
        return yh + s * px(m)
    ce, ca = CAMA_CABECERO
    Pieza(f"Depto_Mueble_{did}_Cabecero", "Depto_Mat_MaderaMueble").caja(x0, x1, yh, y(ce), 0.0, ca).crear(col)
    z0, z1 = CAMA_BASE_Z
    Pieza(f"Depto_Mueble_{did}_Zocalo", "Depto_Mat_Patas").caja(
        x0 + px(0.05), x1 - px(0.05), y(ce), y(CAMA["largo"] - 0.05), 0.0, z0).crear(col)
    Pieza(f"Depto_Mueble_{did}_Cama", "Depto_Mat_BaseCama").caja(x0, x1, y(ce), yh + s * L, z0, z1).crear(col)
    Pieza(f"Depto_Mueble_{did}_Colchon", "Depto_Mat_Textil").caja(
        x0 + px(0.01), x1 - px(0.01), y(ce + 0.01), y(CAMA["largo"] - 0.01), z1, CAMA["alto"]).crear(col)
    alm = Pieza(f"Depto_Mueble_{did}_Almohadas", "Depto_Mat_Textil")
    aw, ad, ah = ALMOHADA
    for sx in (-1, 1):
        xc = cx + sx * px(0.42)
        alm.caja(xc - px(aw) / 2, xc + px(aw) / 2, y(ce + 0.05), y(ce + 0.05 + ad), CAMA["alto"], CAMA["alto"] + ah)
    alm.crear(col)
    cb = COBERTOR
    v, zb = px(cb["vuelo"]), CAMA["alto"] - cb["baja"]
    cob = Pieza(f"Depto_Mueble_{did}_Cobertor", "Depto_Mat_Cobertor")
    cob.caja(x0 - v, x1 + v, y(cb["desde"]), yh + s * (L + v), CAMA["alto"], CAMA["alto"] + 0.02)   # encima
    cob.caja(x0 - v, x0, y(cb["desde"]), yh + s * L, zb, CAMA["alto"])                             # costados
    cob.caja(x1, x1 + v, y(cb["desde"]), yh + s * L, zb, CAMA["alto"])
    cob.caja(x0 - v, x1 + v, yh + s * L, yh + s * (L + v), zb, CAMA["alto"])                       # pies
    cob.crear(col)
    return x0, x1


def veladores(col, did, x0_cama, x1_cama):
    yw, s = VELADORES_Y[did]
    w, d, h = VELADOR
    lp, hp = VELADOR_PATA
    for lado, (xa, xb) in (("O", (x0_cama - px(w), x0_cama)), ("E", (x1_cama, x1_cama + px(w)))):
        ya, yb = sorted((yw, yw + s * px(d)))
        Pieza(f"Depto_Mueble_{did}_Velador{lado}", "Depto_Mat_MaderaMueble").caja(xa, xb, ya, yb, hp, h).crear(col)
        patas = Pieza(f"Depto_Mueble_{did}_Velador{lado}_Patas", "Depto_Mat_Patas")
        r = px(0.02)
        for px_, py_ in ((xa + r, ya + r), (xb - r - px(lp), ya + r), (xa + r, yb - r - px(lp)),
                         (xb - r - px(lp), yb - r - px(lp))):
            patas.caja(px_, px_ + px(lp), py_, py_ + px(lp), 0.0, hp)
        patas.crear(col)


def sofa(col):
    S = SOFA
    z = ALFOMBRA_ALTO
    x0, x1 = S["cx"] - px(S["ancho"]) / 2, S["cx"] + px(S["ancho"]) / 2
    y1 = S["y_resp"]
    y0 = y1 - px(S["fondo"])
    b, r = px(S["brazo"]), px(S["respaldo"])
    za, zs = S["asiento_z"]
    Pieza("Depto_Mueble_Sofa_Zocalo", "Depto_Mat_Patas").caja(
        x0 + px(0.04), x1 - px(0.04), y0 + px(0.04), y1 - px(0.04), z, z + S["base_z"]).crear(col)
    base = Pieza("Depto_Mueble_Sofa", "Depto_Mat_Tapiz")
    base.caja(x0, x1, y0, y1, z + S["base_z"], z + za)                         # base
    base.caja(x0 + b, x1 - b, y1 - r, y1, z + za, z + S["alto"])                # respaldo
    for xa, xb in ((x0, x0 + b), (x1 - b, x1)):                                 # brazos
        base.caja(xa, xb, y0, y1, z + za, z + S["brazo_alto"])
    base.crear(col)
    coj = Pieza("Depto_Mueble_Sofa_Cojines", "Depto_Mat_Tapiz")
    j = px(0.005)
    for xa, xb in ((x0 + b, S["junta"] - j), (S["junta"] + j, x1 - b)):
        coj.caja(xa, xb, y0 + px(0.01), y1 - r, z + za, z + zs)                           # asientos
        coj.caja(xa, xb, y1 - r - px(0.15), y1 - r, z + zs, z + S["alto"] - 0.05)         # respaldos
    coj.crear(col)


def living(col):
    Pieza("Depto_Mueble_Alfombra", "Depto_Mat_Alfombra").caja(*ALFOMBRA, 0.0, ALFOMBRA_ALTO).crear(col)
    z = ALFOMBRA_ALTO
    sofa(col)
    M = MESA_CENTRO
    x0, x1, y0, y1 = M["bbox"]
    Pieza("Depto_Mueble_MesaCentro", "Depto_Mat_MaderaMueble").caja(
        x0, x1, y0, y1, z + M["alto"] - M["cubierta"], z + M["alto"]).crear(col)
    patas = Pieza("Depto_Mueble_MesaCentro_Patas", "Depto_Mat_Patas")
    r, lp = px(M["retiro"]), px(M["pata"])
    for xa in (x0 + r, x1 - r - lp):
        for ya in (y0 + r, y1 - r - lp):
            patas.caja(xa, xa + lp, ya, ya + lp, z, z + M["alto"] - M["cubierta"])
    patas.crear(col)
    T = MUEBLE_TV
    x0, x1, y0, y1 = T["bbox"]
    f = px(0.018)
    Pieza("Depto_Mueble_TV_Zocalo", "Depto_Mat_Patas").caja(
        x0 + px(0.03), x1 - px(0.03), y0 + px(0.03), y1 - px(0.03), z, z + T["zocalo"]).crear(col)
    Pieza("Depto_Mueble_TV_Mueble", "Depto_Mat_MaderaMueble").caja(
        x0, x1, y0, y1 - f, z + T["zocalo"], z + T["alto"]).crear(col)
    fr = Pieza("Depto_Mueble_TV_Frentes", "Depto_Mat_MuebleBlanco")
    n, jj = T["puertas"], px(0.003)
    for i in range(n):                                                          # frentes hacia el sofá (sur)
        fr.caja(x0 + (x1 - x0) * i / n + jj / 2, x0 + (x1 - x0) * (i + 1) / n - jj / 2, y1 - f, y1,
                z + T["zocalo"] + 0.01, z + T["alto"] - 0.01)
    fr.crear(col)
    V = TV
    zt = z + T["alto"]
    xc = (V["x"][0] + V["x"][1]) / 2
    pw, pd, ph = V["pie"]
    tv = Pieza("Depto_Mueble_TV", "Depto_Mat_VidrioNegro")
    tv.caja(xc - px(pw) / 2, xc + px(pw) / 2, V["yc"] - px(pd) / 2, V["yc"] + px(pd) / 2, zt, zt + ph)   # pie
    tv.caja(xc - px(0.05), xc + px(0.05), V["yc"] - px(0.015), V["yc"] + px(0.015), zt + ph, zt + V["cuello"])
    tv.caja(V["x"][0], V["x"][1], V["yc"] - px(V["esp"]) / 2, V["yc"] + px(V["esp"]) / 2,
            zt + V["cuello"], zt + V["cuello"] + V["alto"])                   # pantalla
    tv.crear(col)
    Pieza("Depto_Mueble_Pouf", "Depto_Mat_TapizAcento").caja(*POUF["bbox"], z, z + POUF["alto"]).crear(col)


def contraste_extraccion():
    """Cada mueble frente a su bbox de la extracción (px). Devuelve (fallos, informe)."""
    with open(EXTRACCION) as fh:
        ext = {f["name"]: f for f in json.load(fh)["fixtures"]}
    fallos, informe = [], {}
    for nombres, ref, criterio in CONTRASTE:
        nombre = nombres[-1]
        pts = [P.a_plano(*(ob.matrix_world @ v.co)[:2]) for ob in map(bpy.data.objects.get, nombres)
               for v in ob.data.vertices]
        m = (min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts))
        e = ext[ref]
        r = (e["x0"], e["x1"], e["y0"], e["y1"])
        bordes = [round(m[k] - r[k], 2) for k in range(4)]
        centro = [round((m[0] + m[1] - r[0] - r[1]) / 2, 2), round((m[2] + m[3] - r[2] - r[3]) / 2, 2)]
        tam_m = [round((m[1] - m[0] - (r[1] - r[0])) * P.M_POR_PX, 3), round((m[3] - m[2] - (r[3] - r[2])) * P.M_POR_PX, 3)]
        informe[nombre] = dict(extraccion=ref, criterio=criterio, desvio_bordes_px=bordes, desvio_centro_px=centro,
                               diferencia_tamano_m=tam_m)
        malo = (max(abs(b) for b in bordes) if criterio == "bordes" else max(abs(c) for c in centro)) > TOL_BBOX
        if malo:
            fallos.append(f"{nombre} fuera de su bbox del plano ({criterio}): bordes {bordes}, centro {centro}")
    return fallos, informe


def pruebas(root, objs_fase):
    bpy.context.view_layer.update()
    fallos, informe = contraste_extraccion()
    visibles = [o for o in root.all_objects if o.type == "MESH" and not o.hide_render
                and not o.name.startswith("Depto_Ref")]
    propios = G.solidos(objs_fase)
    ajenos = G.solidos([o for o in visibles if o not in objs_fase])
    fallos += G.interferencias(propios, ajenos, TOL_PENETRACION)
    f_cam, holguras = G.holgura_camaras(propios + ajenos, HOLGURA_CAMARA)
    fallos += f_cam
    total = 0
    for o in visibles:
        o.data.calc_loop_triangles()
        total += len(o.data.loop_triangles)
    if total > 150_000:
        fallos.append(f"presupuesto de triángulos excedido: {total}")
    return fallos, informe, holguras, total


def main():
    scene = bpy.context.scene
    SE.exigir(scene, "03", bpy.data.filepath)
    root = bpy.data.collections["Depto"]
    col = G.colecciones_fase(root, (COL,))[COL]
    for did, c in CAMAS.items():
        x0, x1 = cama(col, did, c)
        veladores(col, did, x0, x1)
    living(col)

    objs = list(col.all_objects)
    fallos, informe, holguras, total = pruebas(root, objs)
    with open(os.path.join(RAIZ, "build", "depto_medicion", "contraste_mobiliario.json"), "w") as fh:
        json.dump(informe, fh, indent=2, ensure_ascii=False)
    for f in fallos:
        print("FALLA", f)
    print("CHECK holgura de cámaras (m):", holguras)
    if fallos:
        raise SystemExit(f"ERROR: {len(fallos)} pruebas de la fase 4 fallan; no se guarda el maestro.")
    tris = 0
    for o in objs:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    SE.sellar(scene, "04")
    bpy.ops.wm.save_mainfile(filepath=SE.MAESTRO)
    print(f"CHECK fase 4: {len(objs)} objetos, {tris} triángulos; escena visible {total}; "
          f"{len(CONTRASTE)} muebles dentro de su bbox del plano; sin interferencias > {TOL_PENETRACION * 1000:.0f} mm")
    print(f"FASE_OK Depto_04_mobiliario {len(objs)} {tris} sello={scene['depto_fase04']}")


if __name__ == "__main__":
    main()
