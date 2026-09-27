"""Mediciones del bloque 08 (exterior) sobre los renders de revisión de Blender y las capturas del visor desde las
mismas cámaras (review/08_exterior: <vista>.png y recorrido_web_<vista>.png). Corrección 08, ronda 1.

Uso:
    python3 tools/medir_08.py [--carpeta review/08_exterior] [--solo-blender] [--salida mediciones.json]

Las regiones van en px de una imagen de 1280 × 800 y se escalan a la resolución de cada imagen (sirve para las
pruebas rápidas a 640 × 400). Por región: luminancia lineal media (Rec. 709 sobre sRGB decodificado), RGB medio,
fracción de píxeles con algún canal ≥ 250 (recortados) y fracción con luma sRGB < 8 (negros). Después, los criterios
del encargo y de la revisión: razones dentro de Blender (tarde contra día, cielo contra ventana encendida...) y
razones visor / Blender de la misma región. Escribe <carpeta>/mediciones.json (salvo --salida) y termina con
MEDICIONES_08 <pasan>/<total>. Sólo Pillow.
"""
import argparse
import json
import os

from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = (1280, 800)

# id: (vista, (x0, y0, x1, y1) en 1280 × 800, qué es)
REGIONES = {
    # --- balcon_dia
    "dia.E2_ladrillo": ("balcon_dia", (440, 400, 480, 440), "E2, paño de ladrillo en sombra"),
    "dia.E3_pilar": ("balcon_dia", (726, 200, 739, 235), "E3, pilar de hormigón en sombra"),
    "dia.E3_fachada": ("balcon_dia", (660, 40, 940, 440), "E3, fachada entera"),
    "dia.E3_losas": ("balcon_dia", (700, 5, 900, 9), "E3, fondo de las losas de balcón sobre el ojo"),
    "dia.E4_vidrio": ("balcon_dia", (1000, 60, 1270, 380), "E4, muro cortina"),
    "dia.calzada": ("balcon_dia", (260, 660, 660, 710), "calzada"),
    "dia.calzada_sombra": ("balcon_dia", (820, 610, 960, 650), "calzada en sombra"),
    "dia.copa": ("balcon_dia", (560, 480, 640, 560), "copa de árbol"),
    "dia.bajo_copa": ("balcon_dia", (230, 612, 310, 628), "mitad baja de una copa"),
    "dia.bajo_copa_ancho": ("balcon_dia", (160, 590, 390, 640), "bajo la copa, región ancha"),
    "dia.vereda": ("balcon_dia", (350, 555, 480, 605), "vereda y antejardín de enfrente"),
    "dia.silueta": ("balcon_dia", (170, 140, 230, 190), "tarjeta de siluetas grande de la izquierda"),
    "dia.cielo_silueta": ("balcon_dia", (170, 60, 230, 100), "cielo justo sobre esa tarjeta"),
    "dia.cielo": ("balcon_dia", (32, 10, 208, 95), "cielo"),
    # --- balcon_tarde
    "tarde.E2_ladrillo": ("balcon_tarde", (660, 420, 700, 450), "E2, paño de ladrillo en sombra"),
    "tarde.E3_pilar": ("balcon_tarde", (987, 242, 1000, 278), "E3, pilar de hormigón en sombra"),
    "tarde.E3_fachada": ("balcon_tarde", (900, 32, 1248, 320), "E3, fachada entera"),
    "tarde.cielo_alto": ("balcon_tarde", (300, 20, 700, 110), "cielo alto"),
    "tarde.horizonte": ("balcon_tarde", (420, 170, 500, 195), "cielo junto al horizonte, bajo el sol"),
    "tarde.calzada": ("balcon_tarde", (400, 690, 800, 750), "calzada"),
    "tarde.copa": ("balcon_tarde", (432, 480, 576, 576), "copa de árbol"),
    "tarde.siluetas": ("balcon_tarde", (290, 170, 480, 225), "siluetas lejanas"),
    # --- vistas interiores de tarde
    "dormitorio.cielo_ventana": ("dormitorio_ventana", (340, 95, 580, 230), "cielo por la ventana del dormitorio"),
    "living.cielo_ventanal": ("living_ventanal", (440, 40, 840, 130), "cielo por el ventanal del living"),
    # --- balcon_noche
    "noche.cielo_izq": ("balcon_noche", (20, 20, 140, 90), "cielo, arriba a la izquierda"),
    "noche.cielo": ("balcon_noche", (300, 110, 340, 140), "cielo sobre las siluetas"),
    "noche.cielo_centro": ("balcon_noche", (420, 110, 470, 150), "cielo al centro"),
    "noche.ventana_E3": ("balcon_noche", (668, 200, 720, 238), "ventana encendida del E3"),
    "noche.E2_ladrillo": ("balcon_noche", (440, 400, 480, 440), "E2, paño de ladrillo (sin ventanas)"),
    "noche.E3_pilar": ("balcon_noche", (726, 200, 739, 235), "E3, pilar de hormigón"),
    "noche.calzada": ("balcon_noche", (260, 660, 660, 710), "calzada"),
    # proyecciones de la cámara BALCON: bajo el cabezal de la luminaria de enfrente en x = −3,5 y a mitad de camino
    # hacia la de x = 14,5
    "noche.calzada_luz": ("balcon_noche", (436, 692, 496, 720), "calzada bajo la luminaria de enfrente (x −3,5)"),
    "noche.vereda_luz": ("balcon_noche", (446, 622, 502, 646), "vereda al pie de esa luminaria"),
    "noche.calzada_entre": ("balcon_noche", (720, 662, 780, 686), "calzada entre dos luminarias (x 5,5)"),
    "noche.vereda_entre": ("balcon_noche", (690, 585, 740, 605), "vereda entre dos luminarias (x 5,5)"),
    # --- afuera_control (de día)
    "afuera.calzada_sombra": ("afuera_control", (500, 640, 700, 680), "calzada en sombra"),
}

# (id, tipo, a, b, mínimo, máximo, texto). tipo: "blender" (a / b en los renders), "visor" (a / b en las capturas),
# "vb" (visor / Blender de la región a), "recorte" (fracción ≥ 250 de a en Blender, máximo), "negros" (fracción de
# luma < 8 de a en el visor menos la de Blender, máximo), "color" (visor / Blender por canal de a).
CRITERIOS = (
    ("sol_tarde", "blender", "tarde.E3_pilar", "dia.E3_pilar", 0.40, 0.60,
     "E3 en sombra, tarde / día (sol y cielo de cada HDR)"),
    ("recorte_tarde_alto", "recorte", "tarde.cielo_alto", None, 0.0, 0.01, "cielo alto de la tarde sin quemar"),
    ("recorte_tarde_horizonte", "recorte", "tarde.horizonte", None, 0.0, 0.01, "horizonte de la tarde sin quemar"),
    ("recorte_dormitorio", "recorte", "dormitorio.cielo_ventana", None, 0.0, 0.01, "cielo por la ventana sin quemar"),
    ("cielo_noche_blender", "blender", "noche.cielo", "noche.ventana_E3", 0.0, 0.30,
     "de noche, cielo / ventana encendida (Blender)"),
    ("afuera_control", "blender", "afuera.calzada_sombra", "dia.calzada_sombra", 0.5, 2.0,
     "calzada en sombra, afuera_control / balcon_dia (misma luz)"),
    ("luz_calzada", "blender", "noche.calzada_luz", "noche.calzada_entre", 2.0, 1e9,
     "de noche, calzada bajo una luminaria / entre dos (Blender)"),
    ("luz_vereda", "blender", "noche.vereda_luz", "noche.vereda_entre", 2.0, 1e9,
     "de noche, vereda al pie de una luminaria / entre dos (Blender)"),
    ("bajo_copa_negros", "negros", "dia.bajo_copa_ancho", None, 0.0, 0.02, "sin negros bajo la copa (visor − Blender)"),
    ("bajo_copa", "vb", "dia.bajo_copa", None, 0.80, 1.25, "mitad baja de la copa"),
    ("losas_E3", "vb", "dia.E3_losas", None, 0.80, 1.25, "fondo de las losas de balcón del E3"),
    ("E2_dia", "vb", "dia.E2_ladrillo", None, 0.80, 1.25, "E2 de día"),
    ("E3_dia", "vb", "dia.E3_pilar", None, 0.80, 1.25, "E3 de día"),
    ("calzada_dia", "vb", "dia.calzada", None, 0.80, 1.25, "calzada de día"),
    ("copa_dia", "vb", "dia.copa", None, 0.80, 1.25, "copa de día"),
    ("E4_vidrio", "vb", "dia.E4_vidrio", None, 0.80, 1.20, "muro cortina del E4"),
    ("silueta_dia", "vb", "dia.silueta", None, 0.90, 1.10, "siluetas de día"),
    ("silueta_cielo_visor", "visor", "dia.silueta", "dia.cielo_silueta", 0.30, 0.50, "silueta / cielo (visor)"),
    ("cielo_dia", "vb", "dia.cielo", None, 0.80, 1.25, "cielo de día"),
    ("E2_tarde", "vb", "tarde.E2_ladrillo", None, 0.90, 1.10, "E2 de tarde"),
    ("E3_tarde", "vb", "tarde.E3_pilar", None, 0.90, 1.10, "E3 de tarde"),
    ("horizonte_tarde", "vb", "tarde.horizonte", None, 0.90, 1.10, "horizonte de la tarde (luminancia)"),
    ("horizonte_tarde_color", "color", "tarde.horizonte", None, 0.90, 1.10,
     "color del horizonte de la tarde, por canal (Filmic desatura los claros; el JPG del visor, no)"),
    ("cielo_tarde", "vb", "tarde.cielo_alto", None, 0.80, 1.25, "cielo alto de la tarde"),
    ("cielo_noche", "vb", "noche.cielo", None, 0.90, 1.10, "cielo de noche"),
    ("E2_noche", "vb", "noche.E2_ladrillo", None, 0.70, 1.40, "E2 de noche"),
    ("E3_noche", "vb", "noche.E3_pilar", None, 0.70, 1.40, "E3 de noche"),
    ("ventana_noche", "vb", "noche.ventana_E3", None, 0.80, 1.25, "ventana encendida del E3"),
    ("cielo_noche_visor", "visor", "noche.cielo", "noche.ventana_E3", 0.0, 0.30,
     "de noche, cielo / ventana encendida (visor)"),
    ("luz_calzada_visor", "vb", "noche.calzada_luz", None, 0.70, 1.40, "mancha de luz en la calzada"),
    ("luz_vereda_visor", "vb", "noche.vereda_luz", None, 0.70, 1.40, "mancha de luz en la vereda"),
    ("entre_luces_visor", "vb", "noche.calzada_entre", None, 0.70, 1.40, "calzada entre dos luminarias"),
)


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


LIN = [_lin(i) for i in range(256)]


def medir(ruta, reg):
    im = Image.open(ruta).convert("RGB")
    w, h = im.size
    sx, sy = w / REF[0], h / REF[1]
    x0, y0, x1, y1 = reg
    caja = (round(x0 * sx), round(y0 * sy), max(round(x1 * sx), round(x0 * sx) + 1),
            max(round(y1 * sy), round(y0 * sy) + 1))
    px = list(im.crop(caja).getdata())
    n = len(px)
    rgb = [sum(p[k] for p in px) / n for k in range(3)]
    lin = [sum(LIN[p[k]] for p in px) / n for k in range(3)]
    return {"L": round(0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2], 5),
            "lin": [round(v, 5) for v in lin], "rgb": [round(v, 1) for v in rgb],
            "recortados": round(sum(1 for p in px if max(p) >= 250) / n, 4),
            "negros": round(sum(1 for p in px if 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2] < 8) / n, 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--carpeta", default=os.path.join(RAIZ, "review", "08_exterior"))
    ap.add_argument("--solo-blender", action="store_true")
    ap.add_argument("--salida", default=None)
    a = ap.parse_args()
    med = {}
    for rid, (vista, reg, que) in REGIONES.items():
        fila = {"vista": vista, "region": list(reg), "que": que}
        for fuente, nombre in (("blender", f"{vista}.png"), ("visor", f"recorrido_web_{vista}.png")):
            ruta = os.path.join(a.carpeta, nombre)
            if (fuente == "visor" and a.solo_blender) or not os.path.exists(ruta):
                continue
            fila[fuente] = medir(ruta, reg)
        med[rid] = fila

    def val(rid, fuente):
        return med.get(rid, {}).get(fuente)

    res = []
    for cid, tipo, ra, rb, lo, hi, texto in CRITERIOS:
        v = None
        if tipo in ("blender", "visor") and val(ra, tipo) and val(rb, tipo):
            v = val(ra, tipo)["L"] / max(val(rb, tipo)["L"], 1e-6)
        elif tipo == "vb" and val(ra, "visor") and val(ra, "blender"):
            v = val(ra, "visor")["L"] / max(val(ra, "blender")["L"], 1e-6)
        elif tipo == "recorte" and val(ra, "blender"):
            v = val(ra, "blender")["recortados"]
        elif tipo == "negros" and val(ra, "visor") and val(ra, "blender"):
            v = val(ra, "visor")["negros"] - val(ra, "blender")["negros"]
        elif tipo == "color" and val(ra, "visor") and val(ra, "blender"):
            cv, cb = val(ra, "visor")["lin"], val(ra, "blender")["lin"]
            v = [round(cv[k] / max(cb[k], 1e-6), 3) for k in range(3)]
        if v is None:
            continue
        ok = all(lo <= x <= hi for x in (v if isinstance(v, list) else [v]))
        res.append({"id": cid, "tipo": tipo, "regiones": [r for r in (ra, rb) if r], "valor":
                    v if isinstance(v, list) else round(v, 3), "objetivo": [lo, hi if hi < 1e8 else None],
                    "pasa": ok, "que": texto})
        print(f"{'PASA' if ok else 'NO  '} {cid:24s} {v if isinstance(v, list) else round(v, 3)!s:22s} "
              f"[{lo}, {hi if hi < 1e8 else '∞'}]  {texto}")
    salida = a.salida or os.path.join(a.carpeta, "mediciones.json")
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump({"descripcion": "bloque 08, corrección de la ronda 1: regiones (px de 1280 × 800) medidas en los "
                                  "renders de Blender (<vista>.png) y en las capturas del visor desde la misma cámara "
                                  "(recorrido_web_<vista>.png); L = luminancia lineal media",
                   "herramienta": "tools/medir_08.py", "criterios": res, "regiones": med}, fh, ensure_ascii=False,
                  indent=1)
    print(f"MEDICIONES_08 {sum(r['pasa'] for r in res)}/{len(res)}")


if __name__ == "__main__":
    main()
