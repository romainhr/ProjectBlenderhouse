"""Renders de revisión del bloque 08 (exterior y paisaje): la vista desde el balcón de día, de tarde y de noche, desde el
dormitorio principal por la ventana, desde el living hacia el ventanal y una vista de control desde afuera.

Uso:
    blender -b build/depto.blend --python tools/render_08.py -- --out review/08_exterior \
        [--solo balcon_dia,balcon_tarde] [--samples 64] [--size 1280x800] [--sin-gi]

Usa la maquinaria de tools/render_07b.py (luces por grupo, horneado de luz rebotada por recinto, vidrio de revisión) y
arma el cielo con los HDR de Poly Haven que registra la fase 08 (scene["depto_exterior"]): el mismo giro que el visor
(rotacion_deg), el sol de la fase 5 con el color y la fuerza relativa de cada momento del visor
(web/src/tour/js/cielo.js) y la emisión del exterior (ventanas y luminarias) según scene["depto_exterior"]["emision"].
No guarda el .blend. Escribe <out>/<vista>.png, <out>/renders.json = [{archivo, que_muestra}] y
<out>/renders_detalle.json (cámara, momento, exposición, muestras y resolución).
"""
import json
import math
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import render_07b as R  # noqa: E402
from mathutils import Vector  # noqa: E402


bpy = R.bpy
# Momentos: cielo (id de scene["depto_exterior"]["fuentes"]), fuerza de la luz del cielo y su saturación, fuerza del
# cielo que ve la cámara, sol (fracción de la fuerza del sol de la fase 5 y color sRGB, los del visor: 3,4 / 1,8 / 0,04)
# y grupos de luz encendidos: los que nacen encendidos de tarde y de noche, como en el visor; de día ninguno.
MOMENTOS = {
    "dia": dict(fuerza=1.6, saturacion=0.35, camara=1.0, sol=(1.0, "#fff7ec"), luces=()),
    "tarde": dict(fuerza=1.0, saturacion=0.7, camara=0.8, sol=(1.8 / 3.4, "#ffc58f"), luces="autor"),
    "noche": dict(fuerza=0.08, saturacion=1.0, camara=1.0, sol=None, luces="autor"),     # el cielo de la cámara, como
    # la luz (antes, 0,30: el cielo quedaba 6 veces más oscuro que el del visor)
}
LENTE_ANCHA = 14.0
# vista: cámara ((x, y, z), (x, y, z) mirado, lente mm) en m de Blender, momento, exposición y texto
BALCON = ((-0.6, 3.85, 1.60), (1.5, 13.6, -2.1), LENTE_ANCHA)          # hacia el cruce (derecha)
BALCON_SOL = ((0.4, 3.85, 1.60), (-2.2, 13.6, -1.3), LENTE_ANCHA)       # hacia el sol de la tarde (izquierda)
VISTAS = {
    "balcon_dia": dict(
        cam=BALCON, momento="dia", expo=0.0,
        texto="Desde el balcón, de día (cielo kloofendal_48d_partly_cloudy_puresky girado {rot}°, sol de la fase 5): "
              "calle con veredas de baldosa, soleras y línea central; enfrente el E2 de ladrillo (4 pisos, bajo la "
              "vista) y el E3 de hormigón (11 pisos, con balcones corridos); a la derecha el cruce con pasos de cebra y "
              "el E4 de muro cortina; árboles de calle estilizados y siluetas lejanas en tarjetas. El piso del depto "
              "está a 12,5 m de la calzada (supuesto)."),
    "balcon_tarde": dict(
        cam=BALCON_SOL, momento="tarde", expo=0.0,
        texto="Desde el balcón hacia la izquierda, de tarde (cielo qwantani_dusk_2_puresky con el mismo giro, sol "
              "cálido a 0,53 de la fuerza del día, como el visor): el resplandor queda sobre el E2, que es más bajo que el ojo, y un tercio "
              "de la emisión de las ventanas vecinas y de las luminarias ya encendida."),
    "dormitorio_ventana": dict(
        cam=((2.70, 1.25, 1.45), (2.95, 10.0, 0.1), 16.0), momento="tarde", expo=0.6,
        texto="Desde el dormitorio principal por su ventana (1,82 m, antepecho de 0,95), de tarde con la luz de techo "
              "encendida: la calle y el E3 de enfrente, el cruce a la derecha."),
    "living_ventanal": dict(
        cam=((0.05, -2.0, 1.50), (0.25, 10.0, -0.9), 16.0), momento="tarde", expo=0.6,
        texto="Desde el living hacia el ventanal y el balcón, de tarde con las luces de techo: los tres paños del "
              "ventanal (la hoja móvil corrida), la baranda de vidrio y detrás la calle, los vecinos y el cielo."),
    "balcon_noche": dict(
        cam=BALCON, momento="noche", expo=0.4,
        texto="Desde el balcón, de noche (kloppenheim_02_puresky casi apagado): las ventanas vecinas encendidas "
              "(≈ 35 % de los pisos tipo, 2700-4000 K y alguna pantalla fría), los locales de las plantas bajas, las "
              "luminarias de la calle y las ventanas de las siluetas lejanas."),
    "afuera_control": dict(
        cam=((-7.0, 31.0, 13.0), (-5.0, 3.0, -4.5), 20.0), momento="dia", expo=0.0, sin_gi=True,
        texto="Vista de control desde afuera (no se ve desde el depto): el edificio propio de 8 pisos con el depto en "
              "el 5.º (extremo norte), los balcones apilados sobre los ejes del plano, el antejardín con sendero, "
              "murete y arbustos, la calle con su cruce, los árboles, los autos estacionados, las luminarias y los "
              "vecinos E5 a E7 del mismo lado."),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--solo", default="")
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--size", default="1280x800")
    p.add_argument("--sin-gi", action="store_true")
    return p.parse_args(argv)


def srgb(hexa):
    return tuple(R_srgb(int(hexa[i:i + 2], 16) / 255) for i in (1, 3, 5))


def R_srgb(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def mundo(momento, ext):
    """Mundo con el HDR del momento girado rotacion_deg (Mapping: la dirección de consulta gira −θ en Z, así el cielo
    gira +θ, como el visor en web/src/tour/js/cielo.js)."""
    M = MOMENTOS[momento]
    f = ext["fuentes"][momento]
    w = R._mundo_hdri(f"_Ext_{momento}", os.path.join(R.RAIZ, f["hdr"]), M["fuerza"], M["saturacion"],
                      M["fuerza"] * M["camara"])
    nt = w.node_tree
    env = next(n for n in nt.nodes if n.type == "TEX_ENVIRONMENT")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.vector_type = "POINT"
    mp.inputs["Rotation"].default_value = (0.0, 0.0, -math.radians(ext["rotacion_deg"]))
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    return w


def emision(momento, ext):
    k = ext["emision"][momento]
    for m in bpy.data.materials:
        if m.get("exterior") and "emision_noche" in m:
            m.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = k * m["emision_noche"]


def camara(nombre, pos, mira, lente):
    cd = bpy.data.cameras.new(nombre)
    cd.lens = lente
    cd.clip_start = 0.05
    cd.clip_end = 2500.0                  # las siluetas lejanas están a 170-340 m y el suelo lejano llega a 900 m
    cam = bpy.data.objects.new(nombre, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = pos
    cam.rotation_euler = (Vector(mira) - Vector(pos)).normalized().to_track_quat("-Z", "Y").to_euler()
    return cam


def main():
    a = parse_args()
    os.makedirs(a.out, exist_ok=True)
    scene = bpy.context.scene
    ext = json.loads(scene["depto_exterior"])
    R.config(scene, a)
    R.vidrio_revision()
    R.compositor(scene).slope = (1.0, 1.0, 1.0)            # sin adaptación cromática (el visor no la tiene)
    grupos = json.loads(scene.get("depto_grupos_luz", "[]"))
    R.GRUPOS.update({g["id"]: g for g in grupos})
    autor = tuple(g["id"] for g in grupos if g.get("encendido"))
    sol = bpy.data.objects.get("Depto_Luz_Sol")
    fuerza_sol = sol.data.energy
    sol.data.shadow_cascade_max_distance = 150.0          # el exterior visto llega a ~60 m; más cerca, sombras más finas
    mundos = {m: mundo(m, ext) for m in MOMENTOS}
    solo = [s.strip() for s in a.solo.split(",") if s.strip()]
    hechos = []
    ruta_det = os.path.join(a.out, "renders_detalle.json")
    previos = []
    if solo and os.path.exists(ruta_det):
        with open(ruta_det) as fh:
            previos = [r for r in json.load(fh) if r["vista"] not in solo and r["vista"] in VISTAS]
    for vista, v in VISTAS.items():
        if solo and vista not in solo:
            continue
        M = MOMENTOS[v["momento"]]
        luces = autor if M["luces"] == "autor" else tuple(M["luces"])
        R.fijar_luces(luces)
        scene.world = mundos[v["momento"]]
        sol.hide_render = M["sol"] is None
        if M["sol"]:
            sol.data.energy = fuerza_sol * M["sol"][0]
            sol.data.color = srgb(M["sol"][1])
        emision(v["momento"], ext)
        bpy.context.view_layer.update()
        if not (a.sin_gi or v.get("sin_gi")):
            R.hornear(scene, (v["momento"], ",".join(luces)))
        scene.view_settings.exposure = v["expo"]
        scene.view_settings.look = "Medium Contrast" if v["momento"] == "noche" else "None"
        cam = camara(f"_cam_{vista}", *v["cam"])
        scene.camera = cam
        ruta = os.path.join(a.out, f"{vista}.png")
        scene.render.filepath = ruta
        bpy.ops.render.render(write_still=True)
        texto = v["texto"].replace("{rot}", f"{ext['rotacion_deg']:.1f}".replace(".", ","))
        hechos.append({"vista": vista, "archivo": os.path.basename(ruta), "que_muestra": texto,
                       "momento": v["momento"], "cielo": ext["fuentes"][v["momento"]]["id"],
                       "rotacion_deg": ext["rotacion_deg"], "emision_exterior": ext["emision"][v["momento"]],
                       "luces": list(luces), "camara": {"pos": list(v["cam"][0]), "mira": list(v["cam"][1]),
                                                        "lente_mm": v["cam"][2]},
                       "motor": "EEVEE", "muestras": a.samples, "exposicion": v["expo"],
                       "look": scene.view_settings.look, "luz_rebotada": not (a.sin_gi or v.get("sin_gi")),
                       "resolucion": [scene.render.resolution_x, scene.render.resolution_y]})
        print("RENDER", ruta, flush=True)
    orden = list(VISTAS)
    todos = sorted(previos + hechos, key=lambda r: orden.index(r["vista"]))
    with open(ruta_det, "w") as fh:
        json.dump(todos, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(a.out, "renders.json"), "w") as fh:
        json.dump([{"archivo": r["archivo"], "que_muestra": r["que_muestra"]} for r in todos], fh, ensure_ascii=False,
                  indent=2)
    print("RENDERS_08_DONE", len(hechos))


if __name__ == "__main__":
    main()
