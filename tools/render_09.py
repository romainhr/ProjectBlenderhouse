"""Renders de revisión del bloque 09 (alfombras, cortinas y plantas).

Uso:
    blender -b build/depto.blend --python tools/render_09.py -- --out review/09_textiles \
        [--solo dormitorio1,living_ventanal] [--samples 48] [--size 1280x800] [--sin-gi] [--sin-cama]

Usa la maquinaria de tools/render_07b.py (mundo HDRI de día con el sol de la fase 5, horneado de luz rebotada y
cubemaps por recinto, vidrio de revisión); nada va al GLB. Las vistas de día van con las luces apagadas salvo que se
indique; la de noche, con las del dormitorio principal. Al final, sin --sin-cama, compara la cama del dormitorio
principal con la resolución de telas del bloque 09 (0,5) contra la anterior (0,7), desde la misma cámara y con la misma
luz: la de 0,7 se arma aparte en el lugar de la otra y no se guarda. Escribe <out>/<vista>.png,
<out>/renders.json = [{archivo, que_muestra}] y <out>/renders_detalle.json (cámara, luces y resolución de cada vista).
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import render_07b as R  # noqa: E402

import deco_dormitorio as DO  # noqa: E402  (render_07b ya puso build/ en sys.path)
import depto_04_mobiliario as F4  # noqa: E402  (constantes del bloque 09)
P = R.P
bpy = R.bpy

NOCHE_D1 = ("dorm1_techo", "dorm1_velador_izq", "dorm1_velador_der")
TECHOS = ("hall_techo", "cocina_techo", "bano1", "bano2")      # un solo horneado para hall, cocina y baños
# Orden: primero las vistas con las luces de techo (un horneado), luego la de noche y al final las de día sin lámparas,
# con cuyo horneado se hace también la comparación de la cama.
VISTAS = {
    "hall_camino": dict(
        cam=((392.0, 346.0), 1.60, (316.0, 300.0), 0.0, 15.0), mundo="dia", luces=TECHOS, expo=0.8,
        texto="Camino del hall: lana en espiga carbón y topo con orillos avena, 0,60 × 1,50 × 0,010 m, del hall hacia "
              "el living al norte del nicho de lavadora y de la banca; su extremo este queda fuera del barrido de la "
              "hoja de entrada (la esquina más cercana a 1,08 m de la bisagra; la hoja mide 1,03 m)."),
    "cocina_planta": dict(
        cam=((352.0, 224.0), 1.50, (374.0, 160.0), 1.00, 24.0), mundo="dia", luces=TECHOS, expo=0.8,
        texto="Cocina: haworthia de Poly Haven con su maceta del escaneo (1 500 triángulos tras decimar 8 929) en la "
              "cubierta del tramo norte, entre el anafe y la esquina de la L, bajo los muebles altos (no quedan repisas "
              "abiertas desde la corrección 07c)."),
    "bano1": dict(
        cam=((400.0, 122.0), 1.65, (360.0, 78.0), 0.10, 15.0), mundo="dia", luces=TECHOS, expo=0.8,
        texto="Baño principal: piso de baño de algodón mechado (0,65 × 0,45 × 0,012 m, esquinas de 4 cm) frente a la "
              "tina; la hoja del baño, con 2 cm de holgura, pasa sobre él."),
    "bano1_repisa": dict(
        cam=((374.0, 114.0), 1.45, (413.0, 108.0), 1.20, 24.0), mundo="dia", luces=TECHOS, expo=0.8,
        texto="Repisa de instalaciones del baño principal (1,10 m): calathea chica (variante e, 900 triángulos, escala "
              "0,78) en maceta blanca, lejos del pulsador."),
    "bano2": dict(
        cam=((385.0, 443.0), 1.70, (362.0, 414.0), 0.05, 15.0), mundo="dia", luces=TECHOS, expo=0.8,
        texto="Segundo baño: el mismo piso de baño frente a la tina, con la hoja abierta sobre él."),
    "noche_dormitorio1": dict(
        cam=((272.0, 160.0), 1.55, (182.0, 92.0), 0.30, 15.0), mundo="noche", luces=NOCHE_D1, expo=0.3,
        texto="Dormitorio principal de noche con el colgante y las dos lámparas de los veladores (2700 K): la luz "
              "cálida sobre la lana cruda de la alfombra y el lino de las cortinas."),
    "dormitorio1": dict(
        cam=((272.0, 160.0), 1.55, (182.0, 92.0), 0.30, 15.0), mundo="dia", luces=(), expo=1.3,
        texto="Dormitorio principal desde la puerta, de día: alfombra bereber de lana cruda de 2,50 × 2,00 × 0,015 m "
              "con la retícula de rombos carbón a mano alzada, bajo los dos tercios de la cama hacia los pies (sobresale "
              "0,27 m por lado y 0,24 m al pie) y flecos en los extremos este y oeste; la cama apoya en ella y sus patas "
              "de la cabecera bajan al piso. En la ventana, dos paños de lino recogidos a los lados en una barra negra."),
    "dormitorio1_cortinas": dict(
        cam=((208.0, 128.0), 1.45, (128.0, 66.0), 1.30, 18.0), mundo="dia", luces=(), expo=1.1,
        texto="Paño norte de la ventana del dormitorio principal: lino natural con pliegues de onda (5 ondas en 0,30 m, "
              "15 % más hondas y 7 % más abiertas abajo), anillas, soporte y terminal de la barra negra a 2,26 m; el "
              "dobladillo queda a 1,2 cm del piso y la tela a 2-12 cm del muro, fuera del velador."),
    "dormitorio1_pie": dict(
        cam=((252.0, 160.0), 0.85, (196.0, 146.0), 0.0, 20.0), mundo="dia", luces=(), expo=1.3,
        texto="Franja de la alfombra bereber al pie de la cama del dormitorio principal, a media altura y hacia el "
              "oeste: el canto suave (1,5 cm, cuarto de círculo) sobre el roble, la retícula que sigue por el canto, "
              "el espejo de pie fuera de la alfombra y el paño sur de la cortina al fondo."),
    "dormitorio2": dict(
        cam=((272.0, 342.0), 1.55, (182.0, 412.0), 0.30, 15.0), mundo="dia", luces=(), expo=1.3,
        texto="Segundo dormitorio desde la puerta, de día: kilim de 2,30 × 1,60 × 0,010 m (más chico y de otro diseño: "
              "tejido plano con guarda de diente de lobo y rombos escalonados carbón, ladrillo y ocre), 0,20 m más allá "
              "de los pies de la cama; paños de lino en la ventana, el sur corrido hacia el vano para no bajar sobre el "
              "velador."),
    "dormitorio2_velador": dict(
        cam=((182.0, 430.0), 1.25, (136.0, 462.0), 0.72, 22.0), mundo="dia", luces=(), expo=1.1,
        texto="Velador oeste del segundo dormitorio: calathea orbifolia de Poly Haven (variante c, 1 200 triángulos "
              "tras decimar los 3 542 del escaneo, escala 0,8) en maceta de gres arena, en lugar del jarrón; hojas con "
              "alfa recortado. Detrás, el paño sur de la cortina, que termina 2 cm antes del velador."),
    "living_ventanal": dict(
        cam=((282.0, 262.0), 1.55, (128.0, 250.0), 1.20, 15.0), mundo="dia", luces=(), expo=0.9,
        texto="Ventanal del living: paños laterales de lino de 0,26 m recogidos en los extremos de una barra de muro a "
              "muro (tapas a 3 cm de los tabiques y soporte al medio); dejan libre casi todo el vidrio y 0,68 m de paso "
              "en la hoja abierta del balcón. A la izquierda, el helecho colgado en el rincón junto al balcón."),
    "living_helecho": dict(
        cam=((222.0, 288.0), 1.40, (148.5, 312.0), 1.78, 20.0), mundo="dia", luces=(), expo=0.9,
        texto="Rincón del living junto al balcón: helecho (fern_02, variante c, 1 500 triángulos tras decimar 2 248, "
              "escala 0,6) con las "
              "frondas recortadas por alfa, en maceta blanca colgada del cielo por tres cordeles, sobre el brazo del "
              "sofá, entre el paño de la cortina y la lámpara de arco (en el piso no cabe: 0,26 m entre el sofá y el "
              "vidrio)."),
    "balcon_anturio": dict(
        cam=((104.0, 252.0), 1.50, (75.5, 189.5), 0.35, 20.0), mundo="dia", luces=(), expo=0.2,
        texto="Balcón: anturio de Poly Haven (variante c, 2 200 triángulos tras decimar los 9 072 del escaneo, "
              "escala 0,85) en maceta de gres negro de 0,26 m en la esquina noroeste, junto a la baranda; el paso desde la hoja abierta "
              "hacia la mesa queda libre."),
}

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
    scene.view_settings.exposure = 0.6
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
        json.dump([{"archivo": r["archivo"], "que_muestra": r["que_muestra"]} for r in det], fh, ensure_ascii=False,
                  indent=2)
    print("RENDERS_09_DONE", len(det))


if __name__ == "__main__":
    main()
