"""Compara la planta renderizada (corte horizontal) con el plano original, píxel a píxel.

Uso:
    python3 tools/compare_plan.py --plano ref/plano/plano_depto.png --render review/depto_02/Planta.png \
        --out review/depto_02 [--escala 2]

La planta debe venir de tools/render_interior.py --planta-plana: fondo blanco, muros negros,
antepechos grises, y --escala px de render por px de plano (la cámara de planta cubre el plano entero).

Genera:
    planta_vs_plano.png    plano en gris + muros del modelo en rojo + antepechos en azul, con los
                           desajustes marcados (magenta: línea oscura del plano sin muro en el modelo;
                           verde: muro del modelo donde el plano está en blanco)
    planta_vs_plano.json   conteos y lista de manchas de desajuste con su bbox en px del plano
Requiere PIL (python3 del sistema).
"""
import argparse
import json
import os
from collections import deque

from PIL import Image, ImageFilter

OSCURO_PLANO = 110     # línea de corte o relleno de muro en el plano
BLANCO_PLANO = 232     # papel
MIN_MANCHA = 4         # px de plano: manchas más chicas se cuentan pero no se listan


def mascara(img, cond):
    return img.point(lambda v: 255 if cond(v) else 0).convert("1").convert("L")


def manchas(mask):
    w, h = mask.size
    px = mask.load()
    visto = set()
    out = []
    for y in range(h):
        for x in range(w):
            if px[x, y] and (x, y) not in visto:
                q = deque([(x, y)])
                visto.add((x, y))
                xs, ys, n = [x], [y], 0
                while q:
                    cx, cy = q.popleft()
                    n += 1
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < w and 0 <= ny < h and px[nx, ny] and (nx, ny) not in visto:
                            visto.add((nx, ny))
                            q.append((nx, ny))
                            xs.append(nx)
                            ys.append(ny)
                out.append({"px": n, "bbox": [min(xs), min(ys), max(xs) + 1, max(ys) + 1]})
    return sorted(out, key=lambda m: -m["px"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plano", required=True)
    ap.add_argument("--render", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--escala", type=int, default=2)
    ap.add_argument("--min-cubierto", type=float, default=0.0,
                    help="falla (código 1) si la fracción de px oscuros del plano cubiertos por el modelo es menor")
    ap.add_argument("--max-sobre-blanco", type=float, default=1.0,
                    help="falla (código 1) si la fracción de muro del modelo sobre papel blanco es mayor")
    ap.add_argument("--excluir", default="",
                    help="zonas del plano que no son muros, en px: 'x0,y0,x1,y1;x0,y0,x1,y1' (se informan aparte)")
    a = ap.parse_args()

    plano = Image.open(a.plano).convert("L")
    ren = Image.open(a.render).convert("L")
    k = a.escala
    assert ren.size == (plano.width * k, plano.height * k), (ren.size, plano.size, k)

    # Render a resolución de plano: un px de plano es "muro" si la mayoría de sus k×k sub-px son negros.
    muro_hr = mascara(ren, lambda v: v < 60)
    ante_hr = mascara(ren, lambda v: 60 <= v < 200)
    muro = muro_hr.resize(plano.size, Image.BOX).point(lambda v: 255 if v >= 128 else 0)
    ante = ante_hr.resize(plano.size, Image.BOX).point(lambda v: 255 if v >= 128 else 0)
    solido = Image.new("L", plano.size, 0)
    solido.paste(255, mask=muro)
    solido.paste(255, mask=ante)

    oscuro = mascara(plano, lambda v: v < OSCURO_PLANO)
    blanco = mascara(plano, lambda v: v > BLANCO_PLANO)
    # Tolerancia de 1 px de plano (±2 cm) en ambos sentidos
    solido_d = solido.filter(ImageFilter.MaxFilter(3))
    blanco_e = blanco.filter(ImageFilter.MinFilter(3))

    falta = Image.new("L", plano.size, 0)   # plano oscuro sin modelo cerca
    sobra = Image.new("L", plano.size, 0)   # modelo sobre papel blanco
    zonas = [tuple(float(v) for v in z.split(",")) for z in a.excluir.split(";") if z.strip()]
    excl = Image.new("L", plano.size, 0)
    for x0, y0, x1, y1 in zonas:
        excl.paste(255, (int(x0), int(y0), int(x1), int(y1)))
    po, ps, pf, pb, pm = oscuro.load(), solido_d.load(), falta.load(), blanco_e.load(), muro.load()
    pe = excl.load()
    sb = sobra.load()
    n_osc = n_falta = n_muro = n_sobra = 0
    for y in range(plano.height):
        for x in range(plano.width):
            if po[x, y] and not pe[x, y]:
                n_osc += 1
                if not ps[x, y]:
                    pf[x, y] = 255
                    n_falta += 1
            if pm[x, y]:
                n_muro += 1
                if pb[x, y]:
                    sb[x, y] = 255
                    n_sobra += 1

    m_falta = manchas(falta)
    m_sobra = manchas(sobra)

    # Imagen de revisión a 3x
    K = 3
    base = Image.blend(plano.convert("RGB"), Image.new("RGB", plano.size, "white"), 0.25)
    capa = Image.new("RGBA", plano.size, (0, 0, 0, 0))
    capa.paste((220, 30, 30, 110), mask=muro)
    capa.paste((40, 90, 230, 130), mask=ante)
    capa.paste((255, 0, 255, 255), mask=falta)
    capa.paste((0, 200, 60, 255), mask=sobra)
    img = Image.alpha_composite(base.convert("RGBA"), capa).convert("RGB")
    img = img.resize((plano.width * K, plano.height * K), Image.NEAREST)
    os.makedirs(a.out, exist_ok=True)
    img.save(os.path.join(a.out, "planta_vs_plano.png"))

    res = {
        "px_plano_oscuros": n_osc,
        "px_oscuros_sin_muro_en_modelo": n_falta,
        "frac_oscuros_cubiertos": round(1 - n_falta / max(n_osc, 1), 4),
        "px_muro_modelo": n_muro,
        "px_muro_sobre_papel_blanco": n_sobra,
        "frac_muro_sobre_blanco": round(n_sobra / max(n_muro, 1), 4),
        "zonas_excluidas_px": zonas,
        "manchas_faltantes": [m for m in m_falta if m["px"] >= MIN_MANCHA],
        "manchas_sobrantes": [m for m in m_sobra if m["px"] >= MIN_MANCHA],
        "nota": "px de plano; tolerancia 1 px (≈2 cm). Las faltantes esperables son marcos de ventana, hojas y "
                "arcos de puerta, símbolos (triángulo de acceso, LV) y bordes de muebles: no son muros.",
    }
    with open(os.path.join(a.out, "planta_vs_plano.json"), "w") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print("COMPARE", json.dumps({k: v for k, v in res.items() if not k.startswith("manchas")}))
    for m in res["manchas_faltantes"][:25]:
        print("  FALTA", m)
    for m in res["manchas_sobrantes"][:25]:
        print("  SOBRA", m)
    # Las métricas globales detectan muros faltantes o fuera de lugar, pero NO errores de 2-5 cm en una
    # cara (quedan dentro de la tolerancia): para eso está build/depto_medicion/verificar_lineas.py.
    if res["frac_oscuros_cubiertos"] < a.min_cubierto or res["frac_muro_sobre_blanco"] > a.max_sobre_blanco:
        raise SystemExit(f"COMPARE_FALLA cubierto={res['frac_oscuros_cubiertos']} sobre_blanco={res['frac_muro_sobre_blanco']}")


if __name__ == "__main__":
    main()
