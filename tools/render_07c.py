"""Renders de revisión del bloque 07c (respetar el plano): muebles altos en L con la campana telescópica y la vajilla,
esquina de la cocina con las hojas abiertas, cajones cerrados por defecto, nevera con la bisagra al norte (la boca
del hall libre) y su acero cepillado en primer plano, y los cajones de los clósets Sur abiertos como en el visor.

Uso:
    blender -b build/depto.blend --python tools/render_07c.py -- --out review/07c_plano \
        [--solo cocina_altos,acero_primer_plano] [--samples 64] [--size 1280x800] [--sin-gi]

Usa la maquinaria de tools/render_07b.py (mundo HDRI de día, horneado de luz rebotada y cubemaps por recinto, vidrio
de revisión, LED interior de la nevera sólo de revisión); nada va al GLB. Todas las vistas son de día con las luces
apagadas, así que comparten un solo horneado. Escribe <out>/<vista>.png, <out>/renders.json = [{archivo, que_muestra}]
y <out>/renders_detalle.json (cámara, lo abierto, exposición y resolución de cada vista).
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import render_07b as R  # noqa: E402
P = R.P

N = [f"Depto_Mueble_Cocina_PuertaAlta{h}" for h in ("N1", "N2", "N3")]
E = [f"Depto_Mueble_Cocina_PuertaAlta{h}" for h in ("E1", "E2", "E3")]
LAVA = ["Depto_Mueble_Cocina_PuertaLavaplatos1", "Depto_Mueble_Cocina_PuertaLavaplatos2"]
NEVERA = "Depto_Mueble_Nevera_Puerta"
CAM_COCINA = ((316.0, 262.0), 1.62, (360.0, 172.0), 1.45, 14.0)
VISTAS = {
    "cocina_altos": dict(
        cam=CAM_COCINA, mundo="dia", luces=(), expo=1.3, cerrar_muebles=True,
        texto="Cocina en L, todo cerrado: muebles altos en los dos tramos como marca el plano (discontinuas ALTOS_Y y "
              "ALTOS_X, de 1,50 a 2,10 m), con rellenadores de 5 cm contra T3 y en la esquina, y el módulo de 0,60 m "
              "sobre el anafe con la campana telescópica (visera de acero cepillado al ras de las hojas). Sin las "
              "repisas abiertas de la versión 2 ni la campana de chimenea; el azulejo llega hasta la cara inferior de "
              "los altos."),
    "cocina_altos_abiertos": dict(
        cam=CAM_COCINA, mundo="dia", luces=(), expo=1.3, cerrar_muebles=True, abrir=(*N, *E),
        texto="La misma vista con las seis hojas de los muebles altos abiertas (bisagra en la arista de la cara vista, "
              "95°; la de la torre a 90°): platos, boles, vasos, tazas, fuentes y frascos de despensa en los pisos y "
              "las repisas medias. Ninguna hoja toca muro, torre ni otra hoja (prueba de aperturas de la fase 6)."),
    "altos_norte_izquierda": dict(
        cam=((311.0, 207.0), 1.45, (311.0, 160.0), 1.72, 18.0), mundo="dia", luces=(), expo=1.4, cerrar_muebles=True,
        abrir=(N[0],),
        texto="Mueble alto de la izquierda del tramo norte abierto (hoja de 0,57 m con la bisagra en T3, detrás del "
              "rellenador): platos llanos en dos pilas abajo; boles y platos de postre en la repisa media."),
    "altos_norte_derecha": dict(
        cam=((377.0, 207.0), 1.45, (377.0, 160.0), 1.72, 18.0), mundo="dia", luces=(), expo=1.4, cerrar_muebles=True,
        abrir=(N[1], N[2]),
        texto="Mueble alto de la derecha del tramo norte con sus dos hojas abiertas (bisagras al oeste): vasos bajos y "
              "altos abajo; tazas con el asa hacia adelante y boles en la repisa. A la izquierda, la visera de la "
              "campana."),
    "altos_este": dict(
        cam=((352.0, 202.0), 1.50, (398.0, 202.0), 1.72, 16.0), mundo="dia", luces=(), expo=1.4, cerrar_muebles=True,
        abrir=tuple(E),
        texto="Tramo este de los altos con las tres hojas abiertas (bisagras al sur): fuentes y boles junto al rincón "
              "ciego de la esquina, frascos de despensa, vasos y tazas. La hoja junto a la torre se detiene a 90°, "
              "paralela a su cara."),
    "cocina_esquina": dict(
        cam=((352.0, 232.0), 1.55, (394.0, 178.0), 1.15, 14.0), mundo="dia", luces=(), expo=1.3, cerrar_muebles=True,
        abrir=(N[2], E[0], *LAVA),
        texto="Esquina de la L con la hoja de la esquina de cada tramo alto abierta y las dos puertas bajo el "
              "lavaplatos abiertas (bisagras al sur): la hoja 1 ya no choca con los frentes ni los tiradores de Cajon3, "
              "y la 2 pasa delante de la torre sin tocar el horno."),
    "cocina_cajones_cerrados": dict(
        cam="Depto_Cam_Cocina", mundo="dia", luces=(), expo=1.3,
        texto="Estado inicial del modelo desde la cámara de la cocina: todos los cajones cerrados por defecto "
              "(también el de cubiertos y el de ollas, que hasta la 07c venían abiertos)."),
    "nevera_boca": dict(
        cam=((352.0, 322.0), 1.60, (366.0, 250.0), 1.10, 14.0), mundo="dia", luces=(), expo=1.3, cerrar_muebles=True,
        abrir=(NEVERA,),
        texto="Desde el hall hacia la cocina con la nevera abierta a 100°: con la bisagra al norte la hoja queda en la "
              "cocina, delante de la torre, a {dist_boca} m de la boca entre el hall y la cocina (cara norte de "
              "T_COC_S), que queda libre."),
    "nevera_interior": dict(
        cam=((342.0, 294.0), 1.50, (400.0, 270.0), 1.00, 14.0), mundo="dia", luces=(), expo=1.0,
        abrir=(NEVERA, "Depto_Mueble_Nevera_Freezer"), cerrar_muebles=True, led_nevera=True,
        texto="Nevera de 0,656 m de ancho (medido en el plano, antes 0,60 inferido) abierta, con el cajón freezer: "
              "forro blanco, estantes de vidrio, cajón de verduras, alimentos y los balcones de la contrapuerta. LED "
              "interior sólo de revisión."),
    "acero_primer_plano": dict(
        cam=((371.0, 287.0), 1.38, (386.7, 274.0), 1.22, 35.0), mundo="dia", luces=(), expo=1.6, cerrar_muebles=True,
        texto="Primer plano de la puerta de la nevera: acero inoxidable cepillado rehecho (gris frío claro, vetas "
              "rectas muy finas y parejas, contraste bajo, metálico 1, rugosidad de 0,25 a 0,35) con la manilla de "
              "barra. En la 07b la textura se leía como madera clara veteada."),
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


def main():
    R.VISTAS.clear()
    R.VISTAS.update(VISTAS)
    R.MARCAS["{dist_boca}"] = dist_boca
    R.main()
    a = R.parse_args()
    ruta = os.path.join(a.out, "renders.json")
    with open(ruta) as fh:
        det = json.load(fh)
    with open(os.path.join(a.out, "renders_detalle.json"), "w") as fh:
        json.dump(det, fh, ensure_ascii=False, indent=2)
    with open(ruta, "w") as fh:
        json.dump([{"archivo": r["archivo"], "que_muestra": r["que_muestra"]} for r in det], fh, ensure_ascii=False,
                  indent=2)
    print("RENDERS_07C_DONE", len(det))


if __name__ == "__main__":
    main()
