"""Renders de revisión del bloque 07c (respetar el plano): muebles altos en L con la campana telescópica y la vajilla,
esquina de la cocina con las hojas abiertas, cajones cerrados por defecto, nevera con la bisagra al norte (la boca
del hall libre) y su acero cepillado en primer plano, y los cajones de los clósets Sur abiertos como en el visor.

Uso:
    blender -b build/depto.blend --python tools/render_07c.py -- --out review/07c_plano \
        [--solo cocina_altos,acero_primer_plano] [--samples 64] [--size 1280x800] [--sin-gi]

Usa la maquinaria de tools/render_07b.py (mundo HDRI de día, horneado de luz rebotada y cubemaps por recinto, vidrio
de revisión); nada va al GLB. Desde la ronda 2 no hay adaptación cromática (el visor no la tiene) y la luz interior de la
nevera es la del modelo. Todas las vistas son de día: las de la cocina con su luz encendida (riel de focos y luz lineal
bajo los altos, ronda 1; el par A/B de altos_norte_izquierda con sólo una de las dos), las de control de color,
nevera y clósets con las luces apagadas y la del hall con sus focos. Escribe <out>/<vista>.png, <out>/renders.json = [{archivo, que_muestra}]
y <out>/renders_detalle.json (cámara, lo abierto, exposición y resolución de cada vista).
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import render_07b as R  # noqa: E402
from mathutils import Matrix  # noqa: E402

import depto_geom as G  # noqa: E402  (render_07b ya puso build/ en sys.path)
P = R.P

N = [f"Depto_Mueble_Cocina_PuertaAlta{h}" for h in ("N1", "N2", "N3")]
E = [f"Depto_Mueble_Cocina_PuertaAlta{h}" for h in ("E1", "E2", "E3")]
LAVA = ["Depto_Mueble_Cocina_PuertaLavaplatos1", "Depto_Mueble_Cocina_PuertaLavaplatos2"]
TORRE = [f"Depto_Mueble_Cocina_PuertaTorre{n}{l}" for n in ("Baja", "Alta") for l in ("N", "S")]
NEVERA = "Depto_Mueble_Nevera_Puerta"
CAM_COCINA = ((316.0, 262.0), 1.62, (360.0, 172.0), 1.45, 14.0)
COCINA = ("cocina_techo",)   # vistas de cocina con su luz encendida (3000 K): desde la ronda 1, riel de tres focos y luz
                             # lineal bajo los altos (antes, dos colgantes de jaula); de día, con la luz apagada, los
                             # frentes carbón quedaban casi negros
VISTAS = {
    "cocina_altos": dict(
        cam=CAM_COCINA, mundo="dia", luces=COCINA, expo=0.9, cerrar_muebles=True,
        texto="Cocina en L, todo cerrado: muebles altos en los dos tramos como marca el plano (discontinuas ALTOS_Y y "
              "ALTOS_X, de 1,50 a 2,10 m), con rellenadores de 5 cm contra T3 y en la esquina, y el módulo de 0,60 m "
              "sobre el anafe con la campana telescópica (visera de acero cepillado al ras de las hojas). Luz de la "
              "ronda 1: riel de tres focos casi verticales en el cielo y luz lineal bajo los altos (en vez de los "
              "colgantes de jaula, que lavaban las hojas). Torre como despensa de dos hojas por nivel (ronda 2)."),
    "cocina_altos_abiertos": dict(
        cam=CAM_COCINA, mundo="dia", luces=COCINA, expo=0.9, cerrar_muebles=True, abrir=(*N, *E),
        texto="La misma vista con las seis hojas de los muebles altos abiertas (bisagra en la arista de la cara vista, "
              "95°; la de la torre, E3, a 80°): cada hoja cuelga de un costado o divisor de 18 mm, con el piso, la "
              "repisa y el techo partidos por módulo; platos, boles, vasos, tazas, fuentes y frascos de despensa dentro "
              "de su módulo; tiradores junto al canto inferior. Ninguna hoja toca muro, torre ni otra hoja, abierta ni "
              "durante el giro (pruebas de aperturas y de recorrido de la fase 6, cada 2°)."),
    "altos_norte_izquierda": dict(
        cam=((311.0, 207.0), 1.45, (311.0, 160.0), 1.72, 18.0), mundo="dia", luces=COCINA, expo=1.0, cerrar_muebles=True,
        abrir=(N[0],),
        texto="Mueble alto de la izquierda del tramo norte abierto (hoja de 0,57 m con la bisagra del lado de T3, en el "
              "costado que queda detrás del rellenador): platos llanos en dos pilas abajo; boles y platos de postre en "
              "la repisa media. A la derecha, la visera de acero de la campana con el cepillado a lo largo. Ronda 2: la "
              "luz lineal es un foco hacia abajo (120°), sin las manchas quemadas en los platos."),
    "altos_norte_derecha": dict(
        cam=((384.0, 211.0), 1.40, (376.0, 160.0), 1.72, 18.0), mundo="dia", luces=COCINA, expo=1.0, cerrar_muebles=True,
        abrir=(N[1], N[2]),
        texto="Mueble alto de la derecha del tramo norte con sus dos hojas abiertas (bisagras al oeste): la de N3 en el "
              "divisor de la junta, que parte el piso, la repisa y el techo. Vasos bajos (N2) y altos (N3) abajo; "
              "tazas con el asa hacia adelante y boles en la repisa. A la izquierda, la visera de la campana."),
    "altos_este": dict(
        cam=((352.0, 202.0), 1.50, (398.0, 202.0), 1.72, 16.0), mundo="dia", luces=COCINA, expo=1.0, cerrar_muebles=True,
        abrir=tuple(E),
        texto="Tramo este de los altos con las tres hojas abiertas (bisagras al sur, cada una en su divisor o en el "
              "costado de la torre): fuentes y boles junto al rincón ciego de la esquina, frascos de despensa, vasos y "
              "tazas. La hoja junto a la torre (E3) se detiene a 80° (ronda 2): comparte la junta con la hoja alta "
              "norte de la torre y a 90° su tirador entraba en ella abierta."),
    "cocina_esquina": dict(
        cam=((350.0, 236.0), 1.62, (394.0, 180.0), 1.10, 14.0), mundo="dia", luces=COCINA, expo=0.9, cerrar_muebles=True,
        abrir=(N[2], E[0], *LAVA),
        texto="Esquina de la L con la hoja de la esquina de cada tramo alto abierta y las dos puertas bajo el "
              "lavaplatos abiertas (bisagras al sur, la 2 a 90°): el mueble del lavaplatos ya es hueco, con el sifón "
              "bajo la cubeta, y la hoja 2 queda paralela a la hoja baja norte de la torre. Tiradores de los bajos junto "
              "al canto superior y de los altos junto al inferior (ronda 2)."),
    "lavaplatos_abierto": dict(
        cam=((345.0, 196.0), 1.05, (402.0, 206.0), 0.45, 18.0), mundo="dia", luces=COCINA, expo=1.1,
        cerrar_muebles=True, abrir=tuple(LAVA),
        texto="Mueble del lavaplatos abierto (corrección 07c, ronda 1): cascarón hueco con piso, fondo, costados, "
              "travesaño bajo la cubierta y el montante de 18 mm de la junta donde se atornilla la bisagra de la hoja 1; "
              "sifón de botella cromado bajo el centro de la cubeta con su salida al muro, basurero con tapa del lado "
              "de la hoja 1 y productos de limpieza del lado de la hoja 2. El rincón ciego de la esquina sigue macizo."),
    "torre": dict(
        cam=((318.0, 243.1), 1.15, (386.7, 243.1), 1.10, 14.0), mundo="dia", luces=COCINA, expo=0.9,
        cerrar_muebles=True,
        texto="Torre como despensa de dos hojas por nivel (corrección 07c, ronda 2), como el símbolo «<» del plano: "
              "hojas de 0,29 m con las bisagras en los extremos norte y sur, que se encuentran al centro (y 243,1 px); "
              "junta de los niveles a 1,50 m, la línea de los altos. Tiradores junto al encuentro, arriba en las hojas "
              "bajas y abajo en las altas. A la derecha, la nevera con su manilla de acero de 0,70 m junto al canto "
              "libre."),
    "torre_abierta": dict(
        cam=((318.0, 243.1), 1.15, (386.7, 243.1), 1.10, 14.0), mundo="dia", luces=COCINA, expo=0.9,
        cerrar_muebles=True, abrir=tuple(TORRE),
        texto="La despensa con sus cuatro hojas abiertas a 90°: abajo, bandejas y una olla en el piso, fuente de vidrio "
              "y tabla de picar, frascos y cajas de cereal, leche, aceite y vinagre en tres repisas; arriba, cajas de "
              "guardado."),
    "cocina_cajones_cerrados": dict(
        cam="Depto_Cam_Cocina", mundo="dia", luces=COCINA, expo=0.9,
        texto="Estado inicial del modelo desde la cámara de la cocina (a 1-2 m de la nevera): todos los cajones y "
              "puertas cerrados por defecto. Aquí se miden sobre el acero de la nevera el paso alto (σ < 1,5 niveles), "
              "el residuo de manchas de 12-60 px (σ < 1,5) y el rango de bloques de ~4 cm sin tendencia (< 3 %; "
              "tools/medir_capturas.py)."),
    "nevera_boca": dict(
        cam=((352.0, 322.0), 1.60, (366.0, 250.0), 1.10, 14.0), mundo="dia", luces=COCINA, expo=0.9, cerrar_muebles=True,
        abrir=(NEVERA,),
        texto="Desde el hall hacia la cocina con la nevera abierta a 100°: con la bisagra al norte la hoja queda en la "
              "cocina, delante de la torre, a {dist_boca} m de la boca entre el hall y la cocina (cara norte de "
              "T_COC_S), que queda libre. Ronda 2: reflejos en pantalla hasta rugosidad 1,0 (el piso de microcemento "
              "ya no se parte en manchas de borde duro; comparar con Hall.png de la fase 6) y la luz interior del "
              "modelo encendida con la puerta abierta."),
    "acero_primer_plano": dict(
        cam=((364.0, 292.0), 1.42, (386.7, 282.0), 1.22, 30.0), mundo="dia", luces=COCINA, expo=1.0, cerrar_muebles=True,
        texto="Primer plano de la puerta de la nevera con la luz de la cocina (3000 K), sin adaptación cromática (ronda "
              "2; antes, con la pendiente fija, salía malva): acero inoxidable cepillado (rayado submilimétrico; la "
              "rugosidad ya no sigue la nube) y la manilla de barra de acero de 0,70 m. La neutralidad se juzga contra "
              "el azulejo blanco bajo la misma luz; la captura del visor desde la misma cámara es "
              "recorrido_web_acero_primer_plano."),
    "visera_primer_plano": dict(
        cam=((342.0, 194.0), 1.38, (342.0, 170.5), 1.53, 35.0), mundo="dia", luces=COCINA, expo=1.1, cerrar_muebles=True,
        texto="Primer plano de la visera de la campana (0,60 × 0,045 m) con el UV girado: el cepillado corre a lo largo "
              "de la tira, como en una campana real; en la ronda 0 las vetas la cruzaban y se leía como roble."),
    # par A/B de altos_norte_izquierda: van después de las vistas con toda la luz de la cocina (cada una con su propio
    # horneado, que se hace una sola vez si las vistas con el mismo horneado van seguidas)
    "altos_norte_izquierda_riel": dict(
        cam=((311.0, 207.0), 1.45, (311.0, 160.0), 1.72, 18.0), mundo="dia", luces=COCINA, filtro_luz="Riel",
        expo=1.0, cerrar_muebles=True, abrir=(N[0],),
        texto="Par A/B (A): la misma vista sólo con los tres focos del riel encendidos (la luz lineal apagada). Muestra "
              "qué ilumina el riel en los platos de N1."),
    "altos_norte_izquierda_lineal": dict(
        cam=((311.0, 207.0), 1.45, (311.0, 160.0), 1.72, 18.0), mundo="dia", luces=COCINA, filtro_luz="LuzBajoAltos",
        expo=1.0, cerrar_muebles=True, abrir=(N[0],),
        texto="Par A/B (B): la misma vista sólo con la luz lineal bajo los altos (foco hacia abajo desde la ronda 2). "
              "Con la luz puntual de la ronda 1, a 8,5 mm bajo el piso del mueble, las manchas quemadas de los platos "
              "venían de aquí y no del riel."),
    "acero_neutro": dict(
        cam=((360.0, 292.0), 1.20, (386.7, 272.0), 0.85, 22.0), mundo="dia", luces=(), expo=1.8, cerrar_muebles=True,
        abrir=(NEVERA,), balance=None,
        texto="Control de color del acero, sólo con la luz del día (sin lámparas y sin adaptación cromática): el frente "
              "del cajón freezer y los cantos de acero de la nevera junto al blanco de referencia de la contrapuerta y "
              "el forro interior, en el mismo cuadro. La cromaticidad medida va en la bitácora."),
    "nevera_interior": dict(
        cam=((342.0, 294.0), 1.50, (400.0, 270.0), 1.00, 14.0), mundo="dia", luces=(), expo=1.0,
        abrir=(NEVERA, "Depto_Mueble_Nevera_Freezer"), cerrar_muebles=True,
        texto="Nevera de 0,656 m de ancho (medido en el plano, antes 0,60 inferido) abierta, con el cajón freezer: "
              "forro blanco, estantes de vidrio, cajón de verduras, alimentos y los balcones de la contrapuerta. Luz "
              "interior del modelo (ronda 2): difusor en el techo y 4 W a 5000 K, en el grupo cocina_nevera que la "
              "puerta prende al abrirse, igual que en el visor."),
    "closet_D1_cajon": dict(
        cam=((329.0, 64.0), 1.42, (304.0, 140.0), 0.95, 12.0), mundo="dia", luces=(), expo=1.2, cerrar_muebles=True,
        abrir=("Depto_Closet_D1_Sur_PuertaA", "Depto_Closet_D1_Sur_Cajon2"),
        texto="Clóset de repisas del dormitorio principal con la hoja A corrida y el cajón de arriba abierto, como lo "
              "permite el visor (la hoja B cerrada): el cajón, del ancho de la columna que libera la hoja A, sale por "
              "ese vano 0,27 m (0,21 m por delante del frente) sin tocar ninguna hoja."),
    "closet_D2_cajones": dict(
        cam=((331.0, 404.5), 1.42, (305.0, 470.0), 0.95, 12.0), mundo="dia", luces=(), expo=1.2, cerrar_muebles=True,
        abrir=("Depto_Closet_D2_Sur_PuertaA", "Depto_Closet_D2_Sur_Cajon3", "Depto_Closet_D2_Sur_Cajon1"),
        texto="Clóset de repisas del segundo dormitorio, hoja A corrida y los cajones de arriba y de abajo abiertos: "
              "salen por la columna de la hoja A, con la B cerrada."),
    "hall_entrada": dict(
        cam=((350.0, 346.0), 1.55, (404.0, 316.0), 1.45, 16.0), mundo="dia", luces=("hall_techo",), expo=1.0,
        abrir=("Depto_Puerta_Entrada_Hoja",),
        texto="Hall con la puerta de entrada abierta a 87° contra T9 (el plano la dibuja a 90°; a 88° la manilla de "
              "palanca ya entra en el muro) y el reloj en la cara sur de T_COC_S, sobre el interruptor, fuera del "
              "barrido de la hoja."),
}


def dist_boca():
    """Distancia (m) de la hoja de la nevera abierta, con todo lo que cuelga de ella, a la cara norte de T_COC_S (la
    boca entre el hall y la cocina). render_07b la llama con las piezas ya en el estado de la vista."""
    o = R.bpy.data.objects[NEVERA]
    objs, pila = [], [o]
    while pila:
        q = pila.pop()
        objs.append(q)
        pila.extend(q.children)
    ys = [P.a_plano(*(q.matrix_world @ v.co)[:2])[1] for q in objs if q.type == "MESH" for v in q.data.vertices]
    return f"{(P.Y['COC_N'] - max(ys)) * P.M_POR_PX:.2f}".replace(".", ",")


# Planta de la cocina contra el plano (sin cámara): huella de cada isla de malla de estos objetos (cerrados), en px del
# plano, dibujada sobre un recorte del plano ampliado. Colores (RGB 0-1): altos, nevera, muebles base y torre.
PLANTA_RECORTE = (283, 145, 425, 305)          # x0, y0, x1, y1 px del plano
PLANTA_ESCALA = 6
PLANTA_OBJETOS = {
    (0.10, 0.35, 0.95): ("Depto_Cocina_AltosNorteCascaron", "Depto_Cocina_AltosEsteCascaron",
                         "Depto_Cocina_AltosRellenos", "Depto_Cocina_CampanaVisera", "Depto_Cocina_CampanaFrente",
                         *N, *E),
    (0.95, 0.45, 0.05): ("Depto_Cocina_NeveraCuerpo", NEVERA, "Depto_Mueble_Nevera_Freezer"),
    (0.10, 0.65, 0.25): ("Depto_Cocina_Cubierta", "Depto_Cocina_Torre", *TORRE),
}


def planta_cocina(out):
    import numpy as np
    bpy = R.bpy
    im = bpy.data.images.load(os.path.join(R.RAIZ, "ref", "plano", "plano_depto.png"))
    W, Hh = im.size
    px = np.array(im.pixels[:], dtype=np.float32).reshape(Hh, W, 4)[::-1]       # fila 0 = arriba (y del plano)
    x0, y0, x1, y1 = PLANTA_RECORTE
    k = PLANTA_ESCALA
    rec = np.repeat(np.repeat(px[y0:y1, x0:x1], k, axis=0), k, axis=1)
    rec[..., :3] = 0.35 + 0.65 * rec[..., :3]                                     # plano aclarado bajo los contornos
    bpy.context.view_layer.update()
    for color, nombres in PLANTA_OBJETOS.items():
        for n in nombres:
            o = bpy.data.objects.get(n)
            if o is None:
                continue
            M = o.matrix_world
            if "puerta" in o:                                                     # cerrada: sin su giro
                M = Matrix.Translation(o.location)
            for isla in G.islas_locales(o):
                pts = [P.a_plano(*(M @ v)[:2]) for v in isla]
                u0 = int(round((min(p[0] for p in pts) - x0) * k))
                u1 = int(round((max(p[0] for p in pts) - x0) * k))
                v0 = int(round((min(p[1] for p in pts) - y0) * k))
                v1 = int(round((max(p[1] for p in pts) - y0) * k))
                u0, u1 = max(0, min(u0, rec.shape[1] - 1)), max(0, min(u1, rec.shape[1] - 1))
                v0, v1 = max(0, min(v0, rec.shape[0] - 1)), max(0, min(v1, rec.shape[0] - 1))
                for u in (u0, u1):
                    rec[v0:v1 + 1, u, :3] = color
                for v in (v0, v1):
                    rec[v, u0:u1 + 1, :3] = color
    alto, ancho = rec.shape[:2]
    sal = bpy.data.images.new("_planta_cocina", ancho, alto, alpha=False)
    sal.pixels.foreach_set(np.ascontiguousarray(rec[::-1]).ravel())
    ruta = os.path.join(out, "planta_cocina.png")
    sal.filepath_raw = ruta
    sal.file_format = "PNG"
    sal.save()
    print("PLANTA_COCINA", ruta)
    return {"vista": "planta_cocina", "archivo": "planta_cocina.png", "que_muestra": (
        "Planta de la cocina sobre el plano (recorte ampliado 6 veces): contorno de cada pieza del modelo, cerrada, "
        "en azul los muebles altos (tramo norte hasta la discontinua ALTOS_Y, este hasta ALTOS_X, rellenadores, "
        "divisores y campana), en naranja la nevera (contorno del plano de y 261,5 a 296,0 px, frente en la "
        "discontinua) y en verde la cubierta, la torre y sus puertas.")}


def main():
    R.VISTAS.clear()
    R.VISTAS.update(VISTAS)
    R.MARCAS["{dist_boca}"] = dist_boca
    a = R.parse_args()
    ruta = os.path.join(a.out, "renders.json")
    detalle = os.path.join(a.out, "renders_detalle.json")
    if os.path.exists(detalle):                    # render_07b conserva las vistas previas desde su formato completo
        with open(detalle) as fh:
            previos = [r for r in json.load(fh) if r.get("vista") in VISTAS]
        with open(ruta, "w") as fh:
            json.dump(previos, fh, ensure_ascii=False, indent=2)
    R.main()
    with open(ruta) as fh:
        det = json.load(fh)
    det.append(planta_cocina(a.out))
    with open(os.path.join(a.out, "renders_detalle.json"), "w") as fh:
        json.dump(det, fh, ensure_ascii=False, indent=2)
    with open(ruta, "w") as fh:
        json.dump([{"archivo": r["archivo"], "que_muestra": r["que_muestra"]} for r in det], fh, ensure_ascii=False,
                  indent=2)
    print("RENDERS_07C_DONE", len(det))


if __name__ == "__main__":
    main()
