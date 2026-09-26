"""Fase 0 (brief): plano con las medidas inferidas superpuestas, para revisar la escala a ojo.

Uso:
    python3 build/depto_00_plano_anotado.py

Lee ref/plano/plano_depto.png y build/depto_plano.py; escribe review/depto_00/plano_medido.png.
Requiere PIL (python3 del sistema). No usa Blender.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_plano as P  # noqa: E402

K = 3            # ampliación del plano
MARGEN = (150, 150, 60, 150)  # izquierda, arriba, derecha, abajo (px de salida)
FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FUENTE_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
AZUL = (20, 60, 150)
VERDE = (0, 120, 60)
ROJO = (190, 30, 30)
X, Y, m = P.X, P.Y, P.m


def f(size, bold=False):
    return ImageFont.truetype(FUENTE_B if bold else FUENTE, size)


def q(x, y):
    """px del plano -> px de la imagen de salida."""
    return (MARGEN[0] + x * K, MARGEN[1] + y * K)


def num(v, d=2):
    return f"{v:.{d}f}".replace(".", ",")


def etiqueta(d, xy, lineas, color=AZUL, tam=(19, 15)):
    """Bloque de texto centrado con fondo blanco translúcido."""
    fuentes = [f(tam[0], True)] + [f(tam[1])] * (len(lineas) - 1)
    cajas = [d.textbbox((0, 0), t, font=fu) for t, fu in zip(lineas, fuentes)]
    w = max(c[2] - c[0] for c in cajas) + 12
    h = sum(c[3] - c[1] + 5 for c in cajas) + 8
    x0, y0 = xy[0] - w / 2, xy[1] - h / 2
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=6, fill=(255, 255, 255, 215), outline=color + (120,))
    yy = y0 + 5
    for t, fu, c in zip(lineas, fuentes, cajas):
        d.text((xy[0] - (c[2] - c[0]) / 2, yy), t, font=fu, fill=color)
        yy += c[3] - c[1] + 5


def cota_vano(d, xy, metros, color=VERDE):
    t = num(metros)
    fu = f(14, True)
    c = d.textbbox((0, 0), t, font=fu)
    w, h = c[2] - c[0] + 8, c[3] - c[1] + 6
    d.rectangle([xy[0] - w / 2, xy[1] - h / 2, xy[0] + w / 2, xy[1] + h / 2], fill=(235, 255, 240, 230), outline=color)
    d.text((xy[0] - (c[2] - c[0]) / 2, xy[1] - h / 2 + 2), t, font=fu, fill=color)


def main():
    plano = Image.open(os.path.join(RAIZ, "ref/plano/plano_depto.png")).convert("RGB")
    plano = plano.resize((plano.width * K, plano.height * K), Image.LANCZOS)
    # Aclarar el plano para que resalten las anotaciones
    plano = Image.blend(plano, Image.new("RGB", plano.size, "white"), 0.35)
    W = plano.width + MARGEN[0] + MARGEN[2]
    H = plano.height + MARGEN[1] + MARGEN[3]
    img = Image.new("RGB", (W, H), "white")
    img.paste(plano, (MARGEN[0], MARGEN[1]))
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)

    # Título
    d.text((MARGEN[0], 18), "Depto 2D2B · plano medido (Fase 0)", font=f(28, True), fill=(30, 30, 30))
    d.text((MARGEN[0], 56), f"Escala inferida {num(P.M_POR_PX, 4)} m/px (±5 %: {num(P.M_POR_PX_BAJO, 4)} a "
           f"{num(P.M_POR_PX_ALTO, 4)}). Medidas interiores entre caras de muro; vanos en verde.",
           font=f(17), fill=(60, 60, 60))

    # Cotas generales exteriores
    x0, y0 = q(X["W_O"], Y["N_O"])
    x1, y1 = q(X["E_O"], Y["S_O"])
    yc = MARGEN[1] - 22
    d.line([(x0, yc), (x1, yc)], fill=ROJO, width=2)
    for xx in (x0, x1):
        d.line([(xx, yc - 8), (xx, yc + 8)], fill=ROJO, width=2)
    t = f"{num(m(X['E_O'] - X['W_O']))} m exterior"
    d.text(((x0 + x1) / 2 - 60, yc - 26), t, font=f(17, True), fill=ROJO)
    xc = x1 + 28
    d.line([(xc, y0), (xc, y1)], fill=ROJO, width=2)
    for yy in (y0, y1):
        d.line([(xc - 8, yy), (xc + 8, yy)], fill=ROJO, width=2)
    tv = Image.new("RGBA", (220, 26), (0, 0, 0, 0))
    ImageDraw.Draw(tv).text((0, 0), f"{num(m(Y['S_O'] - Y['N_O']))} m exterior", font=f(17, True), fill=ROJO)
    tv = tv.rotate(90, expand=True)
    capa.alpha_composite(tv, (int(xc + 6), int((y0 + y1) / 2 - 110)))

    # Ambientes: (nombre, centro px, ancho m, fondo m, área m2)
    amb = [
        ("Dormitorio 1", (208, 96), X["T3_W"] - X["W_I"], Y["D1_N"] - Y["N_I"], 8.41, "+ paso 1,0 m² + 2 closets"),
        ("Dormitorio 2", (208, 404), X["T3_W"] - X["W_I"], Y["S_I"] - Y["D2_S"], 8.42, "+ paso 0,9 m² + 2 closets"),
        ("Living", (208, 238), X["T3_E"] - X["W_I"], Y["D2_N"] - Y["D1_S"], 9.23, "abierto a cocina y hall"),
        ("Cocina", (338, 238), X["E_FORRO"] - X["T3_E"], Y["COC_N"] - Y["T5_S"], 6.64, "mesón en L, fondo 0,60"),
        ("Hall", (372, 332), X["E_I"] - X["T3_E"], Y["T9_N"] - Y["COC_N"], 2.32, None),
        ("Baño 1", (373, 106), X["E_FORRO"] - X["T4_E"], Y["T5_N"] - Y["N_I"], 3.16, "en suite Dorm. 1"),
        ("Baño 2", (374, 428), X["E_I"] - X["T10_E"], Y["S_I"] - Y["T9_S"], 2.66, "en suite, sin ventana"),
    ]
    for nombre, c, w, h, a, extra in amb:
        lineas = [nombre, f"{num(m(w))} × {num(m(h))} m", f"{num(a, 1)} m²"]
        if extra:
            lineas.append(extra)
        etiqueta(d, q(*c), lineas)
    # Balcón (angosto): texto más chico
    etiqueta(d, q(83, 251), ["Balcón", f"{num(m(X['W_O'] - X['BAL_F']))} ×", f"{num(m(Y['BAL_FS'] - Y['BAL_FN']))} m",
                             "3,0 m²"], tam=(16, 13))

    # Vanos (luz en m): posición de la etiqueta en px del plano
    vanos = [
        ((270, 160), m(X["T3_W"] - X["JAMBA_D"])),        # puerta Dorm 1
        ((270, 342), m(X["T3_W"] - X["JAMBA_D"])),        # puerta Dorm 2
        ((326, 89), m(Y["T4_B"] - Y["T4_A"])),            # puerta Baño 1
        ((328, 428), m(Y["T10_B"] - Y["T10_A"])),         # puerta Baño 2
        ((408, 318), m(Y["ENT_S"] - Y["ENT_N"])),         # puerta de entrada
        ((140, 104), m(Y["V_D1_B"] - Y["V_D1_A"])),       # ventana Dorm 1
        ((140, 404), m(Y["V_D2_B"] - Y["V_D2_A"])),       # ventana Dorm 2
        ((140, 200), m(Y["VEN_ENCUENTRO"] - Y["VEN_A"])),  # ventanal, paño norte (corredera)
        ((140, 262), m(Y["VEN_B"] - Y["VEN_ENCUENTRO"])),  # ventanal, paño sur
        ((357, 6), m(X["V_B1_B"] - X["V_B1_A"])),         # ventana Baño 1
    ]
    for c, v in vanos:
        cota_vano(d, q(*c), v)

    # Barra de escala
    bx, by = MARGEN[0], H - 95
    paso = 1.0 / P.M_POR_PX * K
    for i in range(3):
        d.rectangle([bx + i * paso, by, bx + (i + 1) * paso, by + 12], fill=(30, 30, 30) if i % 2 == 0 else (255, 255, 255),
                    outline=(30, 30, 30))
        d.text((bx + i * paso - 5, by + 16), str(i), font=f(15), fill=(30, 30, 30))
    d.text((bx + 3 * paso - 5, by + 16), "3 m", font=f(15), fill=(30, 30, 30))

    # Ejes de Blender (convención del proyecto: +Y hacia el frente = fachada del balcón)
    ax, ay = W - 360, H - 70
    d.line([(ax, ay), (ax - 70, ay)], fill=(40, 140, 40), width=4)
    d.polygon([(ax - 82, ay), (ax - 68, ay - 8), (ax - 68, ay + 8)], fill=(40, 140, 40))
    d.text((ax - 72, ay + 10), "+Y Blender (frente: balcón)", font=f(14, True), fill=(40, 140, 40))
    d.line([(ax, ay), (ax, ay - 60)], fill=(200, 40, 40), width=4)
    d.polygon([(ax, ay - 72), (ax - 8, ay - 58), (ax + 8, ay - 58)], fill=(200, 40, 40))
    d.text((ax + 10, ay - 70), "+X Blender", font=f(14, True), fill=(200, 40, 40))
    d.text((MARGEN[0], H - 45), "Útil ≈ 45 m² (recintos) / 47 m² (entre caras perimetrales) · bruta ≈ 54 m² sin balcón · "
           "alturas no están en el plano: inferidas", font=f(15), fill=(60, 60, 60))

    img = Image.alpha_composite(img.convert("RGBA"), capa).convert("RGB")
    out = os.path.join(RAIZ, "review/depto_00/plano_medido.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("PLANO_ANOTADO_OK", out, img.size)


if __name__ == "__main__":
    main()
