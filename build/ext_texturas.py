"""Texturas propias del exterior del Depto (fase 08, build/depto_08_exterior.py), generadas por código con numpy.

Uso: lo importa build/depto_08_exterior.py (dentro de Blender). No descarga nada ni usa imágenes de terceros:
todo sale de ruido periódico (build/deco_texturas.py, clase Lienzo) y de dibujos por celda con semillas fijas, así que
cada corrida escribe los mismos archivos. Salida en assets/texturas/exterior/ (JPEG sRGB):

- fachada_<A|B|C|D>.jpg (1024 px) y fachada_<A|B|C|D>_emision.jpg (512 px): atlas de 8 × 8 celdas; cada celda es
  una bahía por un piso del edificio vecino. La fila de abajo (v de 0 a 1/8) es la planta baja (locales o vestíbulo)
  y las otras siete, pisos tipo. La emisión trae las ventanas encendidas de noche (≈ 35 % de los pisos tipo y ≈ 70 %
  de los locales), con la misma cortina que la textura de color: se sortean juntas por celda.
- ventanas_propias.jpg (1024 px) y ventanas_propias_emision.jpg (512 px): 8 × 8 ventanas del edificio propio.
  Filas 0-3: ventana de dos hojas; filas 4-7: ventanal corredera. Columnas 0-4 apagadas y 5-7 encendidas de noche.
- calle.jpg (1024 px): corte de la calle de 14 m (vereda de 3, calzada de 8 y vereda de 3) a lo ancho (u) y 12 m a lo
  largo (v, se repite): baldosas de vereda, solera, asfalto con huellas de rodado y línea central segmentada de 3 m.
- terreno.jpg (512 px, 8 m): pasto del antejardín y de los lotes cercanos.
- fachada_propia.jpg (512 px, 4 m): pintura exterior del edificio propio (el color de Depto_Mat_MuroExterior).
- lejanos.jpg (512 px, 24 m) y lejanos_emision.jpg (256 px): ventanas tenues de las siluetas lejanas.
- paleta.jpg y paleta_emision.jpg (256 px): 16 × 16 muestras de color plano de 16 px (árboles, autos, soleras,
  techos, postes...). Cada cara usa una sola coordenada UV, el centro de su muestra: con derivadas nulas el
  muestreo queda en el nivel 0 del mipmap y no se mezcla con las vecinas.

Las proporciones (bahías, pisos, vanos) son de diseño, no medidas: el exterior no está en el plano (ADR 0004).
"""
import math
import os
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import deco_texturas as DT  # noqa: E402  (Lienzo, guardar_jpg, col, mezcla, ss)

SALIDA = os.path.join(RAIZ, "assets", "texturas", "exterior")
CALIDAD = 88
CELDAS = 8                      # atlas de fachada: 8 bahías × 8 pisos

# Variantes de fachada de los vecinos (diseño). bahia y piso en m: la textura mide 8 bahías × 8 pisos, y la fase 08
# arma cada edificio con un número entero de bahías para que ninguna ventana quede cortada en las esquinas.
# vano = (u0, u1, v0, v1) dentro de la celda (0-1, v hacia arriba); marco en m.
VARIANTES = {
    "A": dict(nombre="ladrillo", bahia=3.2, piso=2.8, planta_baja=3.6, muro="#8b4f3b", vano=(0.30, 0.71, 0.32, 0.86),
              marco="#e6e1d8", marco_m=0.06, alfeizar="#cfc6b6", losa="#a88f7c", ladrillo=True, parteluz=True,
              encendidas=0.36, semilla=11),
    "B": dict(nombre="hormigon", bahia=3.0, piso=2.7, planta_baja=4.0, muro="#b9b7b1", vano=(0.12, 0.88, 0.30, 0.90),
              marco="#3a3d40", marco_m=0.05, alfeizar=None, losa="#cfcdc7", baranda=True, parteluz=True,
              encendidas=0.34, semilla=23),
    "C": dict(nombre="vidrio", bahia=1.5, piso=3.5, planta_baja=4.5, muro="#2b3137", vano=(0.0, 1.0, 0.27, 1.0),
              marco="#8d9398", marco_m=0.045, alfeizar=None, losa="#2b3137", muro_cortina=True,
              encendidas=0.42, semilla=37),
    "D": dict(nombre="estuco", bahia=3.5, piso=3.0, planta_baja=3.4, muro="#d9cdb2", vano=(0.34, 0.66, 0.30, 0.80),
              marco="#f2efe8", marco_m=0.06, alfeizar="#ece4d2", losa="#cabd9f", persianas=True,
              encendidas=0.33, semilla=41),
}

# Colores de ventanas encendidas (sRGB, antes de la intensidad): 2700 K, 3000 K, 4000 K y una pantalla fría.
LUCES_VENTANA = (((1.00, 0.64, 0.34), 0.40), ((1.00, 0.72, 0.46), 0.30), ((1.00, 0.86, 0.70), 0.22),
                 ((0.62, 0.72, 1.00), 0.08))
CORTINAS = ("#d9cbb3", "#c8b89c", "#b9c2c6", "#e6dfd2", "#a99a86", "#d6c1a0")

# Paleta de colores planos (sRGB) y su emisión. El índice es la posición en la grilla de 16 × 16 (fila 0 arriba).
PALETA = {
    "marca_blanca": "#e8e8e3", "marca_amarilla": "#e2bf3a", "solera": "#9d9b94", "muro_bajo": "#b8b2a6",
    "sendero": "#948c80", "techo": "#6c6c6e", "techo_grava": "#8b877f", "caja_techo": "#aeaeaa",
    "tronco": "#4d3e30", "copa_1": "#3b5a2a", "copa_2": "#4f6b2e", "copa_3": "#2f4c2c", "copa_4": "#5d7440",
    "arbusto": "#3f5e33", "poste": "#2d2f32", "luminaria": "#d8d6cc", "auto_rojo": "#8c1d18",
    "auto_blanco": "#dcdcd8", "auto_gris": "#74777b", "auto_azul": "#233a66", "auto_negro": "#141517",
    "auto_plata": "#a5a8ab", "vidrio_auto": "#1d2328", "neumatico": "#151515", "losa_balcon": "#a3a19a",
    "pasamanos": "#1c1c1f", "remate_A": "#7a4535", "remate_B": "#c4c2bc", "remate_C": "#3b4148", "remate_D": "#d3c6a8",
    "suelo_lejano": "#5f615d", "vestibulo": "#20262b", "vestibulo_luz": "#2a2c2a", "muro_propio": "#cdcac2",
    "tierra": "#5b4a38", "toldo_verde": "#355a44", "banca": "#6a5440",
}
EMISION = {"luminaria": (1.00, 0.80, 0.55), "vestibulo_luz": (1.00, 0.86, 0.66)}
LADO_PALETA = 16                 # muestras por lado
PX_MUESTRA = 16


def indice_paleta():
    return {n: i for i, n in enumerate(PALETA)}


def uv_paleta(nombre):
    """Centro (u, v) de la muestra de la paleta (v hacia arriba, como las UV de Blender y de glTF invertidas)."""
    i = indice_paleta()[nombre]
    fila, col = divmod(i, LADO_PALETA)
    return ((col + 0.5) / LADO_PALETA, 1.0 - (fila + 0.5) / LADO_PALETA)


# ---------------------------------------------------------------------------------------------- utilidades
def _c(hexa):
    return DT.col(hexa)


def _mezcla(a, b, t):
    return DT.mezcla(a, b, t)


def _guardar(arr, nombre):
    os.makedirs(SALIDA, exist_ok=True)
    ruta = os.path.join(SALIDA, nombre)
    DT.guardar_jpg(np.clip(arr, 0, 1).astype(np.float32), ruta, CALIDAD)
    return ruta


def _reducir(arr, n):
    """Promedio por bloques (arr de lado múltiplo de n) -> n × n."""
    f = arr.shape[0] // n
    return arr.reshape(n, f, n, f, -1).mean(axis=(1, 3))


def _luz(rng):
    colores, pesos = zip(*LUCES_VENTANA)
    k = rng.choice(len(colores), p=np.array(pesos) / sum(pesos))
    return np.array(colores[k], np.float32)


# ---------------------------------------------------------------------------------------------- fachadas vecinas
def fachada(var):
    """Atlas de color (1024) y de emisión (512) de una variante de VARIANTES."""
    V = VARIANTES[var]
    N = 1024
    bw, fh = V["bahia"], V["piso"]
    L = DT.Lienzo(CELDAS * bw, CELDAS * fh, N, N)
    rng = np.random.default_rng(V["semilla"])
    X, Yy = L.X, L.Y
    ci = np.minimum((X / bw).astype(np.int64), CELDAS - 1)
    cj = np.minimum((Yy / fh).astype(np.int64), CELDAS - 1)          # 0 = fila de abajo (planta baja)
    cu = X / bw - ci
    cv = Yy / fh - cj
    # --- muro con manchas grandes, variación por celda y veta fina
    muro = _c(V["muro"])
    manchas = L.ruido(rng.integers(1 << 30), grande=6.0, chico=0.6, p=1.2)
    fino = L.ruido(rng.integers(1 << 30), grande=0.3, chico=0.02, p=0.6)
    tono_celda = (rng.normal(0.0, 0.025, (CELDAS, CELDAS))).astype(np.float32)
    k = 1.0 + 0.035 * manchas + 0.025 * fino + tono_celda[cj, ci]
    img = muro[None, None, :] * k[..., None]
    if V.get("ladrillo"):
        # ladrillo de 0,29 × 0,075 m con traba corrida: tono por ladrillo y cantería más clara (a 40 px/m la junta no
        # alcanza un píxel: queda como modulación)
        hilada = np.floor(Yy / 0.075).astype(np.int64)
        desfase = (hilada % 2) * 0.145
        pieza = np.floor((X + desfase) / 0.29).astype(np.int64)
        azar = ((pieza * 73856093) ^ (hilada * 19349663)) % 1000 / 1000.0
        junta = np.maximum(DT.ss(0.012, 0.0, np.abs(((Yy / 0.075) % 1.0) - 0.0) * 0.075),
                           DT.ss(0.012, 0.0, np.abs((((X + desfase) / 0.29) % 1.0)) * 0.29))
        img = img * (0.90 + 0.18 * azar[..., None]).astype(np.float32)
        img = _mezcla(img, _c("#b9ab9b")[None, None, :] * k[..., None], 0.35 * junta)
    if V.get("losa"):                                                  # borde de losa, 0,15 m al pie de cada piso
        banda = (cv * fh < 0.15) & (cj > 0)
        img = np.where(banda[..., None], _c(V["losa"])[None, None, :] * k[..., None], img)
    # --- vano de cada celda (planta baja aparte)
    u0, u1, v0, v1 = V["vano"]
    sorteo = rng.random((CELDAS, CELDAS))
    encend = sorteo < V["encendidas"]
    encend[0, :] = rng.random(CELDAS) < 0.7                            # locales y vestíbulo: casi todos con luz
    luces = np.stack([np.stack([_luz(rng) for _ in range(CELDAS)]) for _ in range(CELDAS)])
    inten = (0.65 + 0.35 * rng.random((CELDAS, CELDAS))).astype(np.float32)
    cortina_lado = rng.choice([-1, 0, 1], size=(CELDAS, CELDAS), p=[0.3, 0.35, 0.35])
    cortina_frac = (0.25 + 0.35 * rng.random((CELDAS, CELDAS))).astype(np.float32)
    cortina_col = np.stack([np.stack([_c(CORTINAS[rng.integers(len(CORTINAS))]) for _ in range(CELDAS)])
                            for _ in range(CELDAS)])
    persiana = rng.random((CELDAS, CELDAS)) < 0.18                     # persiana baja en la parte de arriba
    persiana_frac = (0.2 + 0.4 * rng.random((CELDAS, CELDAS))).astype(np.float32)
    em = np.zeros_like(img)
    tipo = cj > 0
    if V.get("muro_cortina"):
        dentro = tipo & (cv >= v0)
    else:
        dentro = tipo & (cu >= u0) & (cu <= u1) & (cv >= v0) & (cv <= v1)
    # coordenadas dentro del vano (0-1) y distancia al borde en m
    su = np.clip((cu - u0) / (u1 - u0), 0, 1)
    sv = np.clip((cv - v0) / (v1 - v0), 0, 1)
    d_borde = np.minimum(np.minimum(su, 1 - su) * (u1 - u0) * bw, np.minimum(sv, 1 - sv) * (v1 - v0) * fh)
    # vidrio: reflejo del cielo (más claro arriba) con una diagonal suave, y el interior oscuro abajo
    vid_osc, vid_cielo = _c("#1f262c"), _c("#8397a8")
    refl = np.clip(0.15 + 0.55 * sv ** 1.6 + 0.12 * np.sin(6.0 * (su + 0.6 * sv) + ci * 1.7), 0, 1)
    vidrio = _mezcla(vid_osc[None, None, :], vid_cielo[None, None, :], refl)
    if V.get("muro_cortina"):
        vidrio = _mezcla(_c("#26343e")[None, None, :], _c("#8fa9b8")[None, None, :], refl * 0.85)
    # cortina (desde un lado o ninguna) y persiana
    lado = cortina_lado[cj, ci]
    frac = cortina_frac[cj, ci]
    en_cortina = ((lado == -1) & (su < frac)) | ((lado == 1) & (su > 1 - frac))
    tela = cortina_col[cj, ci] * (0.92 + 0.08 * np.cos(su * 60.0))[..., None]
    vidrio = np.where(en_cortina[..., None], _mezcla(vidrio, tela, 0.78), vidrio)
    en_persiana = persiana[cj, ci] & (sv > 1 - persiana_frac[cj, ci])
    lamas = 0.85 + 0.15 * (((sv * (v1 - v0) * fh) / 0.05) % 1.0 > 0.5)
    vidrio = np.where(en_persiana[..., None], _c("#d8d4ca")[None, None, :] * lamas[..., None], vidrio)
    # sombra del dintel y de una jamba (el vano está retranqueado)
    sombra = 1.0 - 0.45 * DT.ss(0.10, 0.0, (1 - sv) * (v1 - v0) * fh) - 0.25 * DT.ss(0.08, 0.0, su * (u1 - u0) * bw)
    vidrio = vidrio * sombra[..., None]
    img = np.where(dentro[..., None], vidrio, img)
    # emisión: techo más claro arriba, cortina tamiza (más tenue y más cálida)
    luz = luces[cj, ci] * (inten[cj, ci] * (0.70 + 0.30 * sv))[..., None]
    luz = np.where(en_cortina[..., None], luz * np.array([0.62, 0.52, 0.40], np.float32), luz)
    luz = np.where(en_persiana[..., None], luz * 0.45, luz)
    em = np.where((dentro & encend[cj, ci])[..., None], luz, em)
    # marco y parteluz
    marco = _c(V["marco"])
    en_marco = dentro & (d_borde < V["marco_m"])
    if V.get("parteluz"):
        en_marco |= dentro & (np.abs(su - 0.5) * (u1 - u0) * bw < V["marco_m"] * 0.6)
    if V.get("muro_cortina"):
        en_marco = tipo & ((np.minimum(cu, 1 - cu) * bw < V["marco_m"]) | (np.abs(cv - v0) * fh < V["marco_m"])
                           | ((1 - cv) * fh < V["marco_m"]))
        img = np.where((tipo & (cv < v0))[..., None], _c(V["muro"])[None, None, :] * k[..., None], img)
    img = np.where(en_marco[..., None], marco[None, None, :] * (0.95 + 0.05 * k[..., None]), img)
    em = np.where(en_marco[..., None], 0.0, em)
    # alféizar bajo la ventana, con chorreado leve debajo
    if V.get("alfeizar"):
        bajo = tipo & (cu >= u0 - 0.03) & (cu <= u1 + 0.03) & (cv < v0) & (cv > v0 - 0.05 / fh)
        img = np.where(bajo[..., None], _c(V["alfeizar"])[None, None, :] * k[..., None], img)
        chorreo = tipo & (cu >= u0) & (cu <= u1) & (cv < v0 - 0.05 / fh) & (cv > v0 - 0.9 / fh)
        rayas = 0.5 + 0.5 * L.ruido(rng.integers(1 << 30), grande=0.05, chico=0.01, p=0.0, estira=12.0, angulo=90.0)
        img = np.where(chorreo[..., None], img * (1.0 - 0.06 * rayas * (cv - (v0 - 0.9 / fh)) / (0.9 / fh))[..., None],
                       img)
    # baranda dibujada (variante B: balcón corrido; la losa del balcón es geometría en la fase 08)
    if V.get("baranda"):
        barra = tipo & (cv * fh > 0.15) & (cv * fh < 1.05) & ((np.abs(((cv * fh - 0.15) / 0.3) % 1.0) < 0.12)
                                                          | (np.abs(cv * fh - 1.02) < 0.03))
        img = np.where(barra[..., None], _c("#2e3134")[None, None, :], img)
        em = np.where(barra[..., None], em * 0.25, em)
    # persianas de madera a los lados (variante D)
    if V.get("persianas"):
        ancho_p = (u1 - u0) * 0.5
        izq = tipo & (cu < u0) & (cu > u0 - ancho_p) & (cv >= v0) & (cv <= v1)
        der = tipo & (cu > u1) & (cu < u1 + ancho_p) & (cv >= v0) & (cv <= v1)
        tabla = 0.88 + 0.12 * (((cv * fh) / 0.06) % 1.0 > 0.4)
        verde = _c("#4f6650")[None, None, :] * tabla[..., None]
        img = np.where((izq | der)[..., None], verde, img)
    # --- planta baja: vitrinas con marco, toldo o letrero por bahía y zócalo
    pb = cj == 0
    vit = pb & (cu > 0.07) & (cu < 0.93) & (cv > 0.10) & (cv < 0.70)
    col_toldo = np.stack([_c(h) for h in rng.choice(["#355a44", "#7b2f2a", "#2f4a6b", "#8a6a2f", "#4a4a4a", "#6b3e5c"],
                                                    size=CELDAS)])
    toldo = pb & (cv > 0.74) & (cv < 0.88)
    img = np.where(toldo[..., None], col_toldo[ci] * (0.9 + 0.1 * np.cos(cu * 40))[..., None], img)
    vitrina = _mezcla(_c("#1c2328")[None, None, :], _c("#6d8190")[None, None, :], np.clip(0.2 + 0.5 * (cv - 0.1) / 0.6, 0, 1))
    img = np.where(vit[..., None], vitrina, img)
    borde_vit = pb & ~vit & (cu > 0.05) & (cu < 0.95) & (cv > 0.08) & (cv < 0.72)
    img = np.where(borde_vit[..., None], _c("#2a2b2c")[None, None, :], img)
    zocalo = pb & (cv < 0.08)
    img = np.where(zocalo[..., None], img * 0.72, img)
    em = np.where((vit & encend[cj, ci])[..., None], luces[cj, ci] * (0.8 * inten[cj, ci])[..., None], em)
    return img, _reducir(em, 512)


# ---------------------------------------------------------------------------------------------- ventanas propias
def ventanas_propias():
    """Atlas de 8 × 8 ventanas del edificio propio (marco de aluminio negro como el del depto)."""
    N, T = 1024, 128
    rng = np.random.default_rng(5)
    img = np.zeros((N, N, 3), np.float32)
    em = np.zeros((N, N, 3), np.float32)
    yy, xx = np.mgrid[0:T, 0:T].astype(np.float32)
    su = (xx + 0.5) / T
    sv = 1.0 - (yy + 0.5) / T                                          # v hacia arriba dentro de la baldosa
    marco = _c("#141516")
    for fila in range(8):                                              # fila 0 = abajo
        for col in range(8):
            ventanal = fila >= 4
            encendida = col >= 5
            refl = np.clip(0.18 + 0.5 * sv ** 1.5 + 0.1 * np.sin(5.0 * (su + 0.7 * sv) + col), 0, 1)
            t = _mezcla(_c("#1c2329")[None, None, :], _c("#7f93a3")[None, None, :], refl)
            lado = rng.choice([-1, 1])
            frac = 0.2 + 0.45 * rng.random()
            en_c = (su < frac) if lado < 0 else (su > 1 - frac)
            if rng.random() < 0.8:
                tela = _c(CORTINAS[rng.integers(len(CORTINAS))]) * (0.9 + 0.1 * np.cos(su * 70))[..., None]
                t = np.where(en_c[..., None], _mezcla(t, tela, 0.8), t)
            else:
                en_c = np.zeros_like(su, bool)
            e = np.zeros_like(t)
            if encendida:
                luz = _luz(rng) * (0.75 + 0.25 * rng.random())
                e = luz[None, None, :] * (0.7 + 0.3 * sv)[..., None]
                e = np.where(en_c[..., None], e * np.array([0.62, 0.52, 0.40], np.float32), e)
            fw = 0.035
            div = 0.357 if ventanal else 0.5                            # encuentro de hojas (el ventanal: 1,05 / 2,94)
            en_m = (np.minimum(su, 1 - su) < fw) | (np.minimum(sv, 1 - sv) < fw * 1.4) | (np.abs(su - div) < fw * 0.7)
            t = np.where(en_m[..., None], marco[None, None, :], t)
            e = np.where(en_m[..., None], 0.0, e)
            r0, c0 = N - (fila + 1) * T, col * T
            img[r0:r0 + T, c0:c0 + T] = t
            em[r0:r0 + T, c0:c0 + T] = e
    return img, _reducir(em, 512)


def uv_ventana_propia(fila, col):
    """Rectángulo UV (u0, v0, u1, v1) de la baldosa (fila 0 abajo), con 1,5 px de margen contra el mipmap."""
    m = 1.5 / 1024
    return (col / 8 + m, fila / 8 + m, (col + 1) / 8 - m, (fila + 1) / 8 - m)


# ---------------------------------------------------------------------------------------------- calle
CALLE_ANCHO, CALLE_LARGO = 14.0, 12.0          # m que cubre la textura: vereda 3 + calzada 8 + vereda 3; 12 m a lo largo
VEREDA, CALZADA = 3.0, 8.0


def calle():
    L = DT.Lienzo(CALLE_ANCHO, CALLE_LARGO, 1024, 1024)
    rng = np.random.default_rng(71)
    X, Yy = L.X, L.Y
    fino = L.ruido(int(rng.integers(1 << 30)), grande=0.08, chico=0.012, p=0.4)
    medio = L.ruido(int(rng.integers(1 << 30)), grande=1.5, chico=0.2, p=1.0)
    grande = L.ruido(int(rng.integers(1 << 30)), grande=8.0, chico=1.0, p=1.2)
    # asfalto
    asf = _c("#3d3e40")[None, None, :] * (1.0 + 0.10 * fino + 0.06 * medio + 0.05 * grande)[..., None]
    img = asf.copy()
    x_calz = X - VEREDA
    carril = CALZADA / 2
    for c in (carril * 0.5, carril * 1.5):                             # huellas de rodado (dos por pista)
        for d in (-0.85, 0.85):
            h = DT.ss(0.45, 0.0, np.abs(x_calz - c - d))
            img = img * (1.0 - 0.10 * h)[..., None]
    for borde in (0.0, CALZADA):                                       # cuneta más sucia junto a la solera
        img = img * (1.0 - 0.18 * DT.ss(0.5, 0.0, np.abs(x_calz - borde)))[..., None]
    raya = (np.abs(x_calz - carril) < 0.06) & (Yy % CALLE_LARGO < 3.0)
    desgaste = np.clip(0.8 + 0.2 * fino, 0, 1)
    img = np.where(raya[..., None], _mezcla(img, _c("#e4e3dc")[None, None, :], desgaste), img)
    # veredas: baldosa de 0,40 m con junta, manchas y la solera clara
    en_vereda = (X < VEREDA) | (X > VEREDA + CALZADA)
    xv = np.where(X < VEREDA, X, CALLE_ANCHO - X)                      # distancia desde el borde exterior
    base = _c("#aaa69d")[None, None, :] * (1.0 + 0.05 * fino + 0.06 * medio + 0.04 * grande)[..., None]
    bi = np.floor(X / 0.4).astype(np.int64)
    bj = np.floor(Yy / 0.4).astype(np.int64)
    tono = (((bi * 92821) ^ (bj * 68917)) % 97 / 97.0 - 0.5) * 0.06
    base = base * (1.0 + tono)[..., None]
    junta = (np.minimum(X % 0.4, 0.4 - X % 0.4) < 0.008) | (np.minimum(Yy % 0.4, 0.4 - Yy % 0.4) < 0.008)
    base = np.where(junta[..., None], base * 0.82, base)
    solera = (xv > VEREDA - 0.16)
    base = np.where(solera[..., None], _c("#c3c0b8")[None, None, :] * (1.0 + 0.04 * fino)[..., None], base)
    img = np.where(en_vereda[..., None], base, img)
    return img


def uv_calle(x_desde_borde, a_lo_largo):
    """UV de la textura de calle: x_desde_borde en m desde el borde exterior de la vereda A (0-14), a_lo_largo en m."""
    return (x_desde_borde / CALLE_ANCHO, a_lo_largo / CALLE_LARGO)


# ---------------------------------------------------------------------------------------------- terreno, pintura, lejanos
TERRENO_M, PINTURA_M, LEJANOS_M = 8.0, 4.0, 24.0


def terreno():
    L = DT.Lienzo(TERRENO_M, TERRENO_M, 512, 512)
    rng = np.random.default_rng(83)
    fino = L.ruido(int(rng.integers(1 << 30)), grande=0.05, chico=0.01, p=0.3)
    medio = L.ruido(int(rng.integers(1 << 30)), grande=0.8, chico=0.1, p=1.0)
    seco = DT.ss(0.6, 1.6, L.ruido(int(rng.integers(1 << 30)), grande=3.0, chico=0.5, p=1.4))
    pasto = _mezcla(_c("#4b6a2f")[None, None, :], _c("#6f7a3e")[None, None, :], seco)
    return pasto * (1.0 + 0.14 * fino + 0.08 * medio)[..., None]


def fachada_propia():
    L = DT.Lienzo(PINTURA_M, PINTURA_M, 512, 512)
    rng = np.random.default_rng(89)
    fino = L.ruido(int(rng.integers(1 << 30)), grande=0.03, chico=0.006, p=0.3)
    medio = L.ruido(int(rng.integers(1 << 30)), grande=0.6, chico=0.08, p=1.0)
    rayas = L.ruido(int(rng.integers(1 << 30)), grande=0.2, chico=0.03, p=0.8, estira=10.0, angulo=90.0)
    return _c("#cdcac2")[None, None, :] * (1.0 + 0.018 * fino + 0.02 * medio - 0.012 * np.abs(rayas))[..., None]


def lejanos():
    """Ventanas tenues de las siluetas lejanas (celdas de 3 × 3 m) y su emisión escasa."""
    L = DT.Lienzo(LEJANOS_M, LEJANOS_M, 512, 512)
    rng = np.random.default_rng(97)
    X, Yy = L.X, L.Y
    ci, cj = (X / 3.0).astype(np.int64), (Yy / 3.0).astype(np.int64)
    cu, cv = X / 3.0 - ci, Yy / 3.0 - cj
    medio = L.ruido(int(rng.integers(1 << 30)), grande=4.0, chico=0.5, p=1.0)
    img = _c("#a9b1ba")[None, None, :] * (1.0 + 0.04 * medio)[..., None]
    hay = rng.random((8, 8)) < 0.85
    vano = (cu > 0.32) & (cu < 0.68) & (cv > 0.34) & (cv < 0.78) & hay[cj % 8, ci % 8]
    img = np.where(vano[..., None], img * 0.86, img)                 # en la bruma, ventanas de poco contraste
    enc = rng.random((8, 8)) < 0.18
    luces = np.stack([np.stack([_luz(rng) for _ in range(8)]) for _ in range(8)])
    em = np.where((vano & enc[cj % 8, ci % 8])[..., None], luces[cj % 8, ci % 8] * 0.8, 0.0).astype(np.float32)
    return img, _reducir(em, 256)


def paleta():
    n = LADO_PALETA * PX_MUESTRA
    img = np.full((n, n, 3), 0.5, np.float32)
    em = np.zeros((n, n, 3), np.float32)
    for nombre, i in indice_paleta().items():
        fila, col = divmod(i, LADO_PALETA)
        r, c = fila * PX_MUESTRA, col * PX_MUESTRA
        img[r:r + PX_MUESTRA, c:c + PX_MUESTRA] = _c(PALETA[nombre])
        if nombre in EMISION:
            em[r:r + PX_MUESTRA, c:c + PX_MUESTRA] = EMISION[nombre]
    return img, em


# ---------------------------------------------------------------------------------------------- todo
def generar():
    """Escribe todas las texturas en SALIDA; devuelve {id: {"color": ruta, "emision": ruta o None, "metros": ...}}."""
    out = {}
    for var in VARIANTES:
        c, e = fachada(var)
        V = VARIANTES[var]
        out[f"fachada_{var}"] = {"color": _guardar(c, f"fachada_{var}.jpg"), "emision": _guardar(e, f"fachada_{var}_emision.jpg"),
                                 "metros": [CELDAS * V["bahia"], CELDAS * V["piso"]], "nombre": V["nombre"]}
    c, e = ventanas_propias()
    out["ventanas_propias"] = {"color": _guardar(c, "ventanas_propias.jpg"),
                               "emision": _guardar(e, "ventanas_propias_emision.jpg"), "metros": None}
    out["calle"] = {"color": _guardar(calle(), "calle.jpg"), "emision": None, "metros": [CALLE_ANCHO, CALLE_LARGO]}
    out["terreno"] = {"color": _guardar(terreno(), "terreno.jpg"), "emision": None, "metros": [TERRENO_M] * 2}
    out["fachada_propia"] = {"color": _guardar(fachada_propia(), "fachada_propia.jpg"), "emision": None,
                             "metros": [PINTURA_M] * 2}
    c, e = lejanos()
    out["lejanos"] = {"color": _guardar(c, "lejanos.jpg"), "emision": _guardar(e, "lejanos_emision.jpg"),
                      "metros": [LEJANOS_M] * 2}
    c, e = paleta()
    out["paleta"] = {"color": _guardar(c, "paleta.jpg"), "emision": _guardar(e, "paleta_emision.jpg"), "metros": None}
    return out


if __name__ == "__main__":
    import json
    print(json.dumps({k: {kk: (os.path.relpath(vv, RAIZ) if isinstance(vv, str) and os.path.isabs(vv) else vv)
                          for kk, vv in v.items()} for k, v in generar().items()}, indent=1))
    print("TEXTURAS_EXTERIOR_OK")
