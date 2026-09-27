"""Renders de revisión del bloque 09 (alfombras, cortinas y plantas).

Uso:
    blender -b build/depto.blend --python tools/render_09.py -- --out review/09_textiles \
        [--solo dormitorio1,living_ventanal] [--samples 48] [--size 1280x800] [--sin-gi] [--sin-cama]

Usa la maquinaria de tools/render_07b.py (mundo HDRI de día con el sol de la fase 5, horneado de luz rebotada y
cubemaps por recinto, vidrio de revisión); nada va al GLB. Las vistas de día van con las luces apagadas, como el visor
en su momento día, y con la exposición calibrada contra un muro o azulejo blanco en luz indirecta (ver VISTAS y
`calibrar`); la de noche, con las del dormitorio principal y exposición fija. Al final, sin --sin-cama, compara la cama del dormitorio
principal con la resolución de telas del bloque 09 (0,5) contra la anterior (0,7), desde la misma cámara y con la misma
luz: la de 0,7 se arma aparte en el lugar de la otra y no se guarda. Escribe <out>/<vista>.png,
<out>/renders.json = [{archivo, que_muestra}] y <out>/renders_detalle.json (cámara, luces y resolución de cada vista).
"""
import json
import os
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import render_07b as R  # noqa: E402

import deco_dormitorio as DO  # noqa: E402  (render_07b ya puso build/ en sys.path)
import depto_04_mobiliario as F4  # noqa: E402  (constantes del bloque 09)
P = R.P
bpy = R.bpy

NOCHE_D1 = ("dorm1_techo", "dorm1_velador_izq", "dorm1_velador_der")
# Corrección 09 (ronda 1): todas las vistas de día van con las luces apagadas, como el visor en su momento día (antes
# el hall, la cocina y los baños se renderizaban con las luces de techo de 2700-3000 K y sin balance: los muros y
# azulejos blancos salían naranjas o crema y no se podía juzgar el color del camino, del algodón ni de la calathea).
# Y cada vista de día calibra su exposición con una referencia neutra (muro pintado o azulejo blanco en luz indirecta)
# hasta el gris del visor (≈ 190 sRGB; medido en sus capturas: muro del hall 193, azulejo 192, muro del D1 195):
# `ref` es una lista de puntos de pantalla (x, y en fracción del cuadro, desde arriba a la izquierda) candidatos; se usa
# el primero cuyo rayo pega en un material neutro (NEUTROS). `ref` = nombre de otra vista: usa su exposición.
# `medir`: materiales cuyo color medio en el render se compara con el promedio de su textura.
NEUTROS = ("Depto_Mat_MuroPintado", "Depto_Mat_MuroBano", "Depto_Mat_Yeso")
OBJETIVO_SRGB = 190.0       # gris del muro blanco en el visor, momento día (capturas recorrido_web_* del bloque 09)
TOL_SRGB = 4.0
ALTOS = (0.97, 238.0)       # tope de las luces del interior (sin cielo, vidrios ni espejos): el percentil 97 del gris
                            # a ≤ 238 sRGB. Con sólo la luz del día, en el hall y los baños el piso recibe mucha más
                            # luz que los muros: llevar el muro a 190 dejaba el piso y las alfombras lavados
PRE = dict(ancho=320, muestras=8, iteraciones=5)   # pre-render de calibración
# Orden: primero la de noche (su horneado) y después todas las de día sin lámparas (un solo horneado, también para la
# comparación de la cama).
VISTAS = {
    "noche_dormitorio1": dict(
        cam=((272.0, 160.0), 1.55, (182.0, 92.0), 0.30, 15.0), mundo="noche", luces=NOCHE_D1, expo=0.3,
        texto="Dormitorio principal de noche con el colgante y las dos lámparas de los veladores (2700 K): la luz "
              "cálida sobre la lana cruda de la alfombra y el lino de las cortinas (exposición fija de noche, sin "
              "calibrar)."),
    "hall_camino": dict(
        cam=((392.0, 346.0), 1.60, (316.0, 300.0), 0.0, 15.0), mundo="dia", luces=(), expo=1.5,
        ref=[(0.15, 0.35), (0.10, 0.25), (0.25, 0.20)], medir=("Depto_Mat_AlfombraCamino",),
        texto="Camino del hall, de día y con las luces apagadas (como el visor): lana en espiga de columnas de 3,75 cm "
              "con sarga de 1 cm, carbón y topo, con orillos avena, 0,60 × 1,50 × 0,010 m, del hall hacia el living al "
              "norte del nicho de lavadora; la plegable del nicho, con 2 cm de holgura, pasa sobre él al abrirse. Su "
              "extremo este queda fuera del barrido de la hoja de entrada."),
    "cocina_planta": dict(
        cam=((352.0, 224.0), 1.50, (374.0, 160.0), 1.00, 24.0), mundo="dia", luces=(), expo=1.0,
        ref=[(0.25, 0.25), (0.75, 0.22), (0.5, 0.12)],
        texto="Cocina de día: haworthia de Poly Haven (sólo el nodo de la planta, 900 triángulos tras decimar 3 394) en "
              "una maceta de gres blanco de 24 lados, en la cubierta del tramo norte, entre el anafe y la esquina de la "
              "L, bajo los muebles altos."),
    "bano1": dict(
        cam=((400.0, 122.0), 1.65, (360.0, 78.0), 0.10, 15.0), mundo="dia", luces=(), expo=1.5,
        ref=[(0.85, 0.35), (0.90, 0.25), (0.75, 0.15)], medir=("Depto_Mat_PisoBanoAlgodon",),
        texto="Baño principal de día: piso de baño de algodón mechado (0,65 × 0,45 × 0,012 m, esquinas de 4 cm) frente "
              "a la tina; la hoja del baño, con 2 cm de holgura, pasa sobre él."),
    "bano1_repisa": dict(
        cam=((374.0, 114.0), 1.45, (413.0, 108.0), 1.20, 24.0), mundo="dia", luces=(), expo=1.5,
        ref=[(0.30, 0.15), (0.15, 0.25), (0.55, 0.12)],
        texto="Repisa de instalaciones del baño principal (1,10 m), de día: calathea chica (variante e, 900 "
              "triángulos, escala 0,78) en maceta blanca, lejos del pulsador."),
    "bano2": dict(
        cam=((385.0, 443.0), 1.70, (362.0, 414.0), 0.05, 15.0), mundo="dia", luces=(), expo=1.5,
        ref=[(0.90, 0.35), (0.92, 0.20), (0.80, 0.15)], medir=("Depto_Mat_PisoBanoAlgodon",),
        texto="Segundo baño de día: el mismo piso de baño frente a la tina, con la hoja abierta sobre él."),
    "dormitorio1": dict(
        cam=((272.0, 160.0), 1.55, (182.0, 92.0), 0.30, 15.0), mundo="dia", luces=(), expo=1.3,
        ref=[(0.70, 0.15), (0.80, 0.20), (0.55, 0.10)],
        texto="Dormitorio principal desde la puerta, de día: alfombra bereber de lana cruda de 2,50 × 2,00 × 0,015 m "
              "con la retícula de rombos carbón a mano alzada, bajo los dos tercios de la cama hacia los pies, y flecos "
              "en los extremos este y oeste; la cama apoya en ella. En la ventana, dos paños de lino recogidos a los "
              "lados en una barra negra."),
    "dormitorio1_cortinas": dict(
        cam=((208.0, 128.0), 1.45, (128.0, 66.0), 1.30, 18.0), mundo="dia", luces=(), expo=1.1,
        ref=[(0.85, 0.35), (0.90, 0.50), (0.75, 0.20)],
        texto="Paño norte de la ventana del dormitorio principal: lino natural (tafetán con flameado) con pliegues de "
              "onda de 8 columnas por onda, 6 ondas en 0,30 m de ancho y hondura desparejos que abajo se corren hacia "
              "un lado; las anillas apoyan en la barra negra (2,26 m) y la tela llega a 2 mm de ellas. El dobladillo "
              "queda a 1,2 cm del piso."),
    "dormitorio1_cabecera": dict(
        cam=((168.0, 92.0), 1.85, (131.0, 60.0), 2.10, 30.0), mundo="dia", luces=(), expo=1.1,
        ref=[(0.80, 0.55), (0.85, 0.35), (0.70, 0.70), (0.60, 0.40)],
        texto="Cabecera del paño norte de la ventana del dormitorio principal, de cerca: las anillas apoyan en la barra "
              "negra y la tela sube hasta 2 mm bajo su fondo (antes colgaba 2,1 cm más abajo y se veía el muro entre "
              "las anillas y la tela); terminal de 12 lados y soporte. Arriba, las ondas con la cresta y el valle "
              "redondos."),
    "dormitorio1_pie": dict(
        cam=((252.0, 160.0), 0.85, (196.0, 146.0), 0.0, 20.0), mundo="dia", luces=(), expo=1.3, ref="dormitorio1",
        texto="Franja de la alfombra bereber al pie de la cama del dormitorio principal, a media altura y hacia el "
              "oeste: el pelo peinado, el borde suave de la retícula carbón decidido por mechón y el canto de 1,5 cm "
              "sobre el roble, el espejo de pie (5 cm más al este) y el paño sur de la cortina al fondo. Exposición la "
              "de la vista dormitorio1."),
    "dormitorio2": dict(
        cam=((272.0, 342.0), 1.55, (182.0, 412.0), 0.30, 15.0), mundo="dia", luces=(), expo=1.3,
        ref=[(0.35, 0.15), (0.25, 0.10), (0.45, 0.12)],
        texto="Segundo dormitorio desde la puerta, de día: kilim de 2,30 × 1,60 × 0,010 m con relieve y tono por celda "
              "de pasada y lazy lines, 0,20 m más allá de los pies de la cama; paños de lino en la ventana, el sur "
              "corrido hacia el vano para no bajar sobre el velador, y los apliques girados hacia la cama."),
    "dormitorio2_velador": dict(
        cam=((182.0, 430.0), 1.25, (136.0, 462.0), 0.72, 22.0), mundo="dia", luces=(), expo=1.1,
        ref=[(0.40, 0.30), (0.30, 0.20), (0.45, 0.15), (0.35, 0.40)],
        texto="Velador oeste del segundo dormitorio: calathea orbifolia (variante c, 1 200 triángulos, escala 0,8) en "
              "maceta de gres arena, con las hojas recortadas por alfa. El aplique gira 25° hacia la cama y su pantalla "
              "queda sobre la almohada, a más de 5 cm del paño sur de la cortina."),
    "living_ventanal": dict(
        cam=((282.0, 262.0), 1.55, (128.0, 250.0), 1.20, 15.0), mundo="dia", luces=(), expo=0.9,
        ref=[(0.05, 0.60), (0.08, 0.45), (0.95, 0.60), (0.30, 0.10)],
        texto="Ventanal del living: paños laterales de lino de 0,26 m recogidos en los extremos de una barra de muro a "
              "muro (tapas a 3 cm de los tabiques y soporte al medio); dejan libre casi todo el vidrio y 0,68 m de paso "
              "en la hoja abierta del balcón. A la izquierda, la planta de piso junto al extremo oeste del sofá."),
    "living_planta": dict(
        cam=((152.0, 236.0), 1.35, (147.0, 305.0), 0.45, 20.0), mundo="dia", luces=(), expo=0.9,
        ref=[(0.30, 0.25), (0.20, 0.35), (0.45, 0.20), (0.60, 0.25)],
        texto="Rincón del living junto al balcón, desde el ventanal: calathea orbifolia (variante a, 1 200 triángulos "
              "tras decimar 5 904, "
              "escala 0,64) en una maceta alta de gres negro de 24 lados, de Ø 0,30 × 0,42 m (≈ 0,66 m en total), "
              "centrada "
              "en el elemento de 0,36 × 0,47 m que el plano dibuja junto al extremo oeste del sofá. El sofá vuelve al "
              "ancho del plano (1,54 m) con el extremo este donde estaba."),
    "balcon_anturio": dict(
        cam=((104.0, 252.0), 1.50, (75.5, 189.5), 0.35, 20.0), mundo="dia", luces=(), expo=0.2,
        texto="Balcón: anturio de Poly Haven (variante c, 2 200 triángulos tras decimar los 9 072 del escaneo, "
              "escala 0,85) en maceta de gres negro de 0,26 m en la esquina noroeste, junto a la baranda (exterior: "
              "exposición fija, sin muro de referencia)."),
}
EXPOS = {}                  # vista -> exposición usada (para las vistas con ref = otra vista)


def _rayo(scene, cam, fx, fy, marco=None):
    """Objeto y material que ve la cámara en el punto (fx, fy) del cuadro (desde arriba a la izquierda). marco:
    (esquinas de view_frame, depsgraph) ya calculados, para muchos rayos."""
    (tr, br, bl, tl), dg = marco or (cam.data.view_frame(scene=scene), bpy.context.evaluated_depsgraph_get())
    p = tl + (tr - tl) * fx + (bl - tl) * fy
    d = (cam.matrix_world.to_3x3() @ p).normalized()
    hit, _, _, idx, ob, _ = scene.ray_cast(dg, cam.matrix_world.translation, d)
    if not hit or ob.type != "MESH":
        return None, None
    ev = ob.evaluated_get(dg)
    mi = ev.data.polygons[idx].material_index if idx < len(ev.data.polygons) else 0
    mat = ob.material_slots[mi].material.name if mi < len(ob.material_slots) and ob.material_slots[mi].material \
        else None
    return ob.name, mat


def _leer_png(ruta):
    im = bpy.data.images.load(ruta, check_existing=False)
    im.colorspace_settings.name = "Non-Color"            # valores del archivo (sRGB codificado) tal cual
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)[::-1, :, :3] * 255.0      # fila 0 arriba


def _ventana(img, fx, fy, r=0.03):
    h, w = img.shape[:2]
    x0, x1 = int(max(0, (fx - r) * w)), int(min(w, (fx + r) * w + 1))
    y0, y1 = int(max(0, (fy - r) * h)), int(min(h, (fy + r) * h + 1))
    return img[y0:y1, x0:x1].reshape(-1, 3)


def _excluido(mat):
    """Lo que no cuenta para las luces del interior: cielo, exterior, vidrios y espejos (reflejan la ventana)."""
    return mat is None or mat.startswith("Depto_Ext_") or "Vidrio" in mat or mat == "Depto_Mat_Espejo"


def _mascara_interior(scene, cam, nx, ny):
    """(ny, nx) True donde la cámara ve el interior (ver _excluido)."""
    marco = (cam.data.view_frame(scene=scene), bpy.context.evaluated_depsgraph_get())
    m = np.zeros((ny, nx), bool)
    for j in range(ny):
        for i in range(nx):
            m[j, i] = not _excluido(_rayo(scene, cam, (i + 0.5) / nx, (j + 0.5) / ny, marco)[1])
    return m


def _altos(img, mascara):
    """Percentil ALTOS[0] del gris (media de R, G y B) de los píxeles interiores."""
    h, w = img.shape[:2]
    mh, mw = mascara.shape
    m = mascara[(np.arange(h) * mh // h)[:, None], (np.arange(w) * mw // w)[None, :]]
    g = img.mean(-1)[m]
    return float(np.percentile(g, 100 * ALTOS[0])) if g.size else 0.0


def calibrar(scene, cam, vista, v, a):
    """Exposición de la vista: pre-renders de PRE['ancho'] px y PRE['muestras'] muestras hasta que la mediana del gris
    (media de R, G y B) en la referencia neutra quede a ±TOL_SRGB de OBJETIVO_SRGB (secante en EV), sin que las luces
    del interior pasen ALTOS (si no, se baja por bisección y la referencia queda más oscura: la luz del cuarto es más
    despareja que la del visor)."""
    ref = v.get("ref")
    if isinstance(ref, str):
        if ref not in EXPOS:                             # --solo sin la vista de referencia: la de la tanda anterior
            previa = os.path.join(a.out, "renders_detalle.json")
            if os.path.exists(previa):
                with open(previa) as fh:
                    EXPOS.update({r["vista"]: r["exposicion"] for r in json.load(fh) if r.get("vista") == ref})
        scene.view_settings.exposure = EXPOS.get(ref, float(v.get("expo", 0.0)))
        EXPOS[vista] = scene.view_settings.exposure
        return {"calibracion": {"de_la_vista": ref, "exposicion": round(EXPOS[vista], 3)}}
    if not ref:
        EXPOS[vista] = scene.view_settings.exposure
        return {}
    punto = None
    for fx, fy in ref:
        ob, mat = _rayo(scene, cam, fx, fy)
        if mat in NEUTROS:
            punto = (fx, fy, ob, mat)
            break
    assert punto, f"{vista}: ningún punto de referencia pega en un material neutro ({ref})"
    fx, fy, ob, mat = punto
    r = scene.render
    previo = (r.resolution_x, r.resolution_y, scene.eevee.taa_render_samples, r.filepath)
    r.resolution_y = int(round(r.resolution_y * PRE["ancho"] / r.resolution_x))
    r.resolution_x = PRE["ancho"]
    scene.eevee.taa_render_samples = PRE["muestras"]
    tmp = os.path.join(a.out, f"_pre_{vista}.png")
    r.filepath = tmp
    pasos = []

    def medir(ev):
        scene.view_settings.exposure = ev
        bpy.ops.render.render(write_still=True)
        m = float(np.median(_ventana(_leer_png(tmp), fx, fy).mean(1)))
        pasos.append((round(ev, 3), round(m, 1)))
        return m
    e0 = float(v.get("expo", 0.0))
    m0 = medir(e0)
    e1 = e0 + (OBJETIVO_SRGB - m0) / 45.0                # primera pendiente supuesta: ≈ 45 sRGB por EV en los medios
    for _ in range(PRE["iteraciones"]):
        if abs(m0 - OBJETIVO_SRGB) <= TOL_SRGB:
            break
        e1 = max(-4.0, min(5.0, e1))
        m1 = medir(e1)
        if abs(m1 - OBJETIVO_SRGB) <= TOL_SRGB:
            e0, m0 = e1, m1
            break
        pend = (m1 - m0) / (e1 - e0) if abs(e1 - e0) > 1e-4 and abs(m1 - m0) > 0.5 else 45.0
        e0, m0, e1 = e1, m1, e1 + (OBJETIVO_SRGB - m1) / max(pend, 5.0)
    e_ref = e0
    if abs(pasos[-1][0] - round(e0, 3)) > 1e-3:           # la última imagen tiene que ser la de e0
        m0 = medir(e0)
    mascara = _mascara_interior(scene, cam, 160, 100)
    rec = _altos(_leer_png(tmp), mascara)
    limite = "referencia"
    if rec > ALTOS[1]:                                     # bisección: la mayor exposición con las luces en el tope
        lo, hi = e0 - 4.0, e0
        for _ in range(6):
            mid = 0.5 * (lo + hi)
            m_mid = medir(mid)
            r_mid = _altos(_leer_png(tmp), mascara)
            if r_mid > ALTOS[1]:
                hi = mid
            else:
                lo, m0, rec = mid, m_mid, r_mid
        e0, limite = lo, "luces"
        if abs(pasos[-1][0] - round(e0, 3)) > 1e-3:
            m0 = medir(e0)
            rec = _altos(_leer_png(tmp), mascara)
    os.remove(tmp)
    r.resolution_x, r.resolution_y, scene.eevee.taa_render_samples, r.filepath = previo
    scene.view_settings.exposure = e0
    EXPOS[vista] = e0
    return {"calibracion": {"punto_pantalla": [fx, fy], "objeto": ob, "material": mat, "objetivo_srgb": OBJETIVO_SRGB,
                            "tolerancia_srgb": TOL_SRGB, "pasos_ev_srgb": pasos, "exposicion": round(e0, 3),
                            "exposicion_por_referencia": round(e_ref, 3), "limite": limite,
                            "referencia_srgb": round(m0, 1), "luces_interior_srgb": round(rec, 1),
                            "luces_tope": {"percentil": ALTOS[0], "srgb": ALTOS[1]}}}


def _textura_media(mat):
    """Color medio sRGB de la textura de color del material (review/deco/texturas.json de build/deco_texturas.py)."""
    tid = bpy.data.materials[mat].get("textura")
    with open(os.path.join(RAIZ, "review", "deco", "texturas.json")) as fh:
        return tid, json.load(fh)["texturas"].get(tid, {}).get("color_medio_srgb")


def medir_colores(scene, cam, vista, v, a, ruta):
    """Color medio (sRGB) en el render de los píxeles cuyo rayo pega en cada material de v['medir'] (grilla de 64 × 40
    rayos), contra el promedio de su textura."""
    if not v.get("medir"):
        return {}
    img = _leer_png(ruta)
    h, w = img.shape[:2]
    out = {}
    for mat in v["medir"]:
        vals = []
        for j in range(40):
            for i in range(64):
                fx, fy = (i + 0.5) / 64, (j + 0.5) / 40
                if _rayo(scene, cam, fx, fy)[1] == mat:
                    vals.append(img[int(fy * h), int(fx * w)])
        tid, media_tex = _textura_media(mat)
        out[mat] = {"render_srgb": [round(float(c)) for c in np.mean(vals, 0)] if vals else None,
                    "muestras": len(vals), "textura": tid, "textura_media_srgb": media_tex}
    return {"colores_medidos": out}


CAMARA_CAMA = ((222.0, 152.0), 1.30, (203.0, 72.0), 0.55, 20.0)


def comparar_cama(out, a):
    """Cama del dormitorio principal con RESOLUCION_CAMA (0,5) y con 0,7, desde la misma cámara y luz de día."""
    scene = bpy.context.scene
    R.fijar_luces(())
    scene.world = R.mundo_dia(scene)
    sol = bpy.data.objects.get("Depto_Luz_Sol")
    if sol:
        sol.hide_render = False
    bpy.context.view_layer.update()
    if not a.sin_gi:
        R.hornear(scene, ("dia", "", ""))         # la misma clave que las vistas de día sin lámparas
    scene.view_settings.exposure = EXPOS.get("dormitorio1", 0.6)   # corrección 09: la calibrada del dormitorio
    scene.view_settings.look = "None"
    cam = R.camara("_cam_cama", *CAMARA_CAMA)
    scene.camera = cam
    actual = [o for o in bpy.data.objects if o.get("pieza") == "D1_Cama"]
    col = bpy.data.collections.new("_cama_07")
    scene.collection.children.link(col)
    d = F4.CAMAS["D1"]
    alto = F4.ALFOMBRAS["D1"]["alto"]
    nueva = DO.cama(col, "_Cama07", tapiz=d["tapiz"], resolucion=0.7, bajada_cabecera=alto)
    por_sufijo = {o.name.split("_")[-1]: o for o in actual}
    for o in nueva:
        ref = por_sufijo[o.name.split("_")[-1]]
        o.location, o.rotation_euler = ref.location.copy(), ref.rotation_euler.copy()
    salidas = []
    for etiqueta, ocultar, mostrar in (("r05", nueva, actual), ("r07", actual, nueva)):
        for o in ocultar:
            o.hide_render = True
        for o in mostrar:
            o.hide_render = False
        tris = 0
        for o in mostrar:
            o.data.calc_loop_triangles()
            tris += len(o.data.loop_triangles)
        ruta = os.path.join(out, f"cama_{etiqueta}.png")
        scene.render.filepath = ruta
        bpy.ops.render.render(write_still=True)
        salidas.append((etiqueta, tris))
        print("RENDER", ruta)
    for o in actual:
        o.hide_render = False
    for o in nueva:
        bpy.data.objects.remove(o, do_unlink=True)
    (_, t05), (_, t07) = salidas
    comun = ("Cama del dormitorio principal con la luz de día, desde la misma cámara. Bloque 09: la resolución de telas, "
             "cabecero, almohadas y cojines pasa de 0,7 a 0,5 para hacer lugar a los textiles y las plantas bajo el "
             "tope de 200 000 triángulos; los cantos y pliegues son los mismos, con cuerdas más largas.")
    return [{"vista": "cama_r05", "archivo": "cama_r05.png", "que_muestra": f"{comun} Esta: 0,5 ({t05} triángulos)."},
            {"vista": "cama_r07", "archivo": "cama_r07.png", "que_muestra": f"{comun} Esta: 0,7 ({t07} triángulos, la "
             "de antes, armada sólo para la comparación)."}]


def main():
    R.VISTAS.clear()
    R.VISTAS.update(VISTAS)
    R.GANCHOS.update(antes=calibrar, despues=medir_colores)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    sin_cama = "--sin-cama" in argv
    if sin_cama:
        sys.argv.remove("--sin-cama")
    a = R.parse_args()
    ruta = os.path.join(a.out, "renders.json")
    detalle = os.path.join(a.out, "renders_detalle.json")
    if os.path.exists(detalle):                     # render_07b conserva las vistas previas desde su formato completo
        with open(detalle) as fh:
            previos = [r for r in json.load(fh) if r.get("vista") in VISTAS]
        with open(ruta, "w") as fh:
            json.dump(previos, fh, ensure_ascii=False, indent=2)
    R.main()
    with open(ruta) as fh:
        det = json.load(fh)
    if not sin_cama:
        det += comparar_cama(a.out, a)
    elif os.path.exists(detalle):
        with open(detalle) as fh:
            det += [r for r in json.load(fh) if r.get("vista", "").startswith("cama_")]
    with open(detalle, "w") as fh:
        json.dump(det, fh, ensure_ascii=False, indent=2)
    with open(ruta, "w") as fh:
        json.dump([{"archivo": r["archivo"], "que_muestra": r["que_muestra"] + _nota_calibracion(r)} for r in det], fh,
                  ensure_ascii=False, indent=2)
    print("RENDERS_09_DONE", len(det))


def _nota_calibracion(r):
    """Texto para renders.json con la exposición usada, su referencia y los colores medidos."""
    cal, txt = r.get("calibracion") or {}, ""
    if cal.get("material"):
        ref = f"{cal['material'].replace('Depto_Mat_', '')} ({cal['objeto'].replace('Depto_', '')})"
        if cal.get("limite") == "luces":
            txt += (f" Exposición {cal['exposicion']:+.2f} EV: la mayor que deja las luces del interior (percentil "
                    f"{100 * ALTOS[0]:.0f}) a ≤ {ALTOS[1]:.0f} sRGB; con ella la referencia neutra, {ref}, queda a "
                    f"{cal['referencia_srgb']:.0f} sRGB "
                    f"(para llegar a {OBJETIVO_SRGB:.0f}, el muro del visor de día, harían falta "
                    f"{cal['exposicion_por_referencia']:+.2f} EV: la luz de día de este cuarto es más despareja que la "
                    "del visor).")
        else:
            corto = abs(cal["referencia_srgb"] - OBJETIVO_SRGB) > TOL_SRGB
            txt += (f" Exposición {cal['exposicion']:+.2f} EV, calibrada con {ref} en luz indirecta a "
                    f"{cal['referencia_srgb']:.0f} sRGB (objetivo {OBJETIVO_SRGB:.0f}, el muro del visor de día"
                    f"{', que no alcanza con el tope de +5 EV: con sólo la luz del día el cuarto es oscuro' if corto else ''}"
                    f"; luces del interior a {cal['luces_interior_srgb']:.0f}).")
    elif cal.get("de_la_vista"):
        txt += f" Exposición {cal['exposicion']:+.2f} EV, la de la vista {cal['de_la_vista']}."
    for mat, c in (r.get("colores_medidos") or {}).items():
        if c.get("render_srgb"):
            txt += (f" {mat.replace('Depto_Mat_', '')}: {tuple(c['render_srgb'])} en el render contra "
                    f"{tuple(c['textura_media_srgb'])} de promedio en su textura ({c['muestras']} muestras).")
    return txt


if __name__ == "__main__":
    main()
