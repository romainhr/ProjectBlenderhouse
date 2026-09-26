"""Texturas PBR propias del Depto 2D2B (decoración industrial v2, docs/deco-industrial.md), creadas desde cero.

Uso:
    blender -b --python-exit-code 1 --python build/deco_texturas.py -- [--solo id1,id2]
        [--revision nada|hoja|todo] [--depurar carpeta]

Sin --solo genera todas las texturas de CATALOGO (las más usadas primero) y la revisión completa; con --solo, sólo
las pedidas y la hoja de texturas. Cada textura sale en assets/texturas/propias/<id>/ como <id>_diff_1k.jpg (color
sRGB), <id>_nor_gl_1k.jpg (normal tangente OpenGL/glTF: rojo = +U, verde = +V, calculado de un mapa de altura) y
<id>_rough_1k.jpg (rugosidad en gris lineal). Los cuadros (arte_*) sólo llevan color. El manifiesto
assets/texturas/propias/manifest.json (el formato que lee build/deco_paleta.py) se reescribe después de cada textura,
así que las primeras ya se pueden usar mientras se generan las demás.

Método (numpy dentro de Blender, sin PIL ni red, semillas fijas):
- Todo se calcula en metros sobre un toro de ancho × alto (dimensiones_m del manifiesto): ruido gaussiano filtrado
  por FFT, Voronoi con distancia periódica, estampas y trazos que dan la vuelta por el borde, y patrones (ladrillos,
  tablas, azulejos, hexágonos) cuyo período divide exacto el tamaño real. Por eso se repiten sin costuras; la
  revisión mide el salto en el borde contra el salto medio entre píxeles vecinos (≈ 1 = sin costura).
- Las matrices van como una imagen (fila 0 arriba, v = 1); al guardar se invierten porque los píxeles de las
  imágenes de Blender van de abajo hacia arriba.
- El normal sale del mapa de altura en metros: n = normalizar(−∂h/∂u, −∂h/∂v, 1), codificado (n + 1) / 2.
  Comprobación (prueba_normal, en review/deco/prueba_normal.*): un bulto gaussiano guardado y releído en el orden de
  Blender tiene verde > 0,5 arriba del centro (v mayor) y rojo > 0,5 a su derecha (u mayor), y en un render de
  Cycles con el nodo Normal Map (espacio tangente, UV del plano) se ve iluminado del lado de la luz, tanto con la luz
  desde +V como desde +U. Un hoyo daría lo contrario.
- JPEG calidad 90 con Image.save (no pasa por la transformada de vista de la escena); cada archivo se relee y se
  compara con lo calculado. El error medio queda en 0,2-1 % en color y rugosidad; en los normales con cantos vivos
  (ladrillo, azulejo) llega a 2-3 % porque el JPEG de Blender submuestrea el croma (4:2:0, no configurable en 3.6,
  ni con calidad 100): por eso la altura se suaviza medio píxel antes del normal. Un error > 6 % detiene el script
  (espacio de color u orientación equivocados).
"""
import argparse
import json
import math
import os
import sys
import time
from types import SimpleNamespace

import bpy
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
SALIDA = os.path.join(RAIZ, "assets", "texturas", "propias")
REVISION = os.path.join(RAIZ, "review", "deco")
N = 1024                                   # requisito: 1K
CALIDAD_JPG = 90
SQ3 = math.sqrt(3.0)
LICENCIA = "propia: generada por build/deco_texturas.py"
LICENCIA_GENERAL = ("Propias del proyecto ProjectBlenderhouse: generadas por código con build/deco_texturas.py "
                    "(numpy, semillas fijas), sin imágenes de terceros ni descargas. Uso libre dentro del proyecto.")


# ======================================================================= campo periódico
class Lienzo:
    """Campo 2D periódico (toro) de ancho × alto metros muestreado en nx × ny píxeles.

    Las matrices van como una imagen: fila 0 arriba. X crece hacia la derecha (u) e Y hacia arriba (v), en metros,
    medidos en el centro de cada píxel. Todo lo que se construye con estos métodos se repite sin costuras."""

    def __init__(self, ancho_m, alto_m, nx=N, ny=N):
        self.w, self.h, self.nx, self.ny = float(ancho_m), float(alto_m), int(nx), int(ny)
        self.px, self.py = self.w / self.nx, self.h / self.ny
        self.x = ((np.arange(self.nx) + 0.5) * self.px).astype(np.float32)
        self.y = (self.h - (np.arange(self.ny) + 0.5) * self.py).astype(np.float32)
        self.X = np.broadcast_to(self.x[None, :], (self.ny, self.nx))
        self.Y = np.broadcast_to(self.y[:, None], (self.ny, self.nx))
        self.fx = np.fft.rfftfreq(self.nx, d=self.px)[None, :]           # ciclos por metro
        self.fy = -np.fft.fftfreq(self.ny, d=self.py)[:, None]           # signo: Y hacia arriba

    def vacio(self):
        return np.zeros((self.ny, self.nx), np.float32)

    # ------------------------------------------------------------ ruido y filtros (FFT: periódicos por construcción)
    def ruido(self, semilla, grande, chico=0.0, p=1.0, estira=1.0, angulo=0.0):
        """Ruido gaussiano periódico de media 0 y desvío 1. Espectro de amplitud (1 + (f·grande)²)^(−p/2) con corte
        gaussiano en los rasgos de tamaño `chico` (m). p = 1: cada octava pesa igual; p = 0 con chico: manchas de
        un solo tamaño. estira > 1 alarga los rasgos en la dirección `angulo` (grados desde +U)."""
        rng = np.random.default_rng(semilla)
        F = np.fft.rfft2(rng.standard_normal((self.ny, self.nx), dtype=np.float32))
        a = math.radians(angulo)
        fpar = self.fx * math.cos(a) + self.fy * math.sin(a)
        fper = -self.fx * math.sin(a) + self.fy * math.cos(a)
        f2 = (fpar * estira) ** 2 + fper ** 2
        filtro = (1.0 + f2 * grande ** 2) ** (-0.5 * p) if p else np.ones_like(f2)
        if chico > 0:
            filtro = filtro * np.exp(-0.5 * (math.pi * chico) ** 2 * f2)
        filtro[0, 0] = 0.0
        out = np.fft.irfft2(F * filtro, s=(self.ny, self.nx)).astype(np.float32)
        return out / (out.std() + 1e-12)

    def desenfocar(self, a, sigma_m):
        g = np.exp(-2.0 * math.pi ** 2 * sigma_m ** 2 * (self.fx ** 2 + self.fy ** 2))
        return np.fft.irfft2(np.fft.rfft2(a) * g, s=a.shape).astype(np.float32)

    # ------------------------------------------------------------ celdas (Voronoi con distancia periódica)
    def vecinos(self, ncx, ncy, jx, jy):
        """Para cada píxel, los puntos de las 3 × 3 celdas vecinas de una grilla ncx × ncy (con vuelta de borde):
        genera (dx, dy, k) = vector del píxel al punto (m) e índice de la celda. jx, jy: posición del punto dentro de
        su celda (0-1), vectores de largo ncx·ncy."""
        cw, ch = self.w / ncx, self.h / ncy
        gx, gy = self.x / cw, self.y / ch
        ci, cj = np.floor(gx).astype(np.int64), np.floor(gy).astype(np.int64)
        fx, fy = (gx - ci).astype(np.float32), (gy - cj).astype(np.float32)
        for dj in (-1, 0, 1):
            nj = (cj + dj) % ncy
            for di in (-1, 0, 1):
                ni = (ci + di) % ncx
                k = nj[:, None] * ncx + ni[None, :]
                yield (di + jx[k] - fx[None, :]) * cw, (dj + jy[k] - fy[:, None]) * ch, k

    def grilla_puntos(self, semilla, celda, jitter, metrica=(1.0, 1.0)):
        ncx = max(2, int(round(self.w / (celda * metrica[0]))))
        ncy = max(2, int(round(self.h / (celda * metrica[1]))))
        rng = np.random.default_rng(semilla)
        jx = (0.5 + (rng.random(ncx * ncy) - 0.5) * jitter).astype(np.float32)
        jy = (0.5 + (rng.random(ncx * ncy) - 0.5) * jitter).astype(np.float32)
        return ncx, ncy, jx, jy

    def voronoi(self, semilla, celda, jitter=0.9, metrica=(1.0, 1.0)):
        """Distancias al punto más cercano (f1) y al segundo (f2), e índice de su celda. celda: separación media de
        los puntos (m), ajustada para dividir exacto el lienzo. metrica (ex, ey): celdas ex × ey veces más largas
        (las distancias se miden en ese espacio estirado)."""
        ex, ey = metrica
        ncx, ncy, jx, jy = self.grilla_puntos(semilla, celda, jitter, metrica)
        f1 = np.full((self.ny, self.nx), np.inf, np.float32)
        f2 = f1.copy()
        idx = np.zeros((self.ny, self.nx), np.int64)
        for dx, dy, k in self.vecinos(ncx, ncy, jx, jy):
            d = np.sqrt((dx / ex) ** 2 + (dy / ey) ** 2)
            m = d < f1
            f2 = np.where(m, f1, np.minimum(f2, d))
            f1 = np.where(m, d, f1)
            idx = np.where(m, k, idx)
        return SimpleNamespace(f1=f1, f2=f2, id=idx, n=ncx * ncy)

    def puntos(self, semilla, espaciado, prob, rmin, rmax, jitter=0.7, metrica=(1.0, 1.0)):
        """Discos dispersos (poros, áridos, motas): uno por celda con probabilidad `prob`, radio entre rmin y rmax.
        Devuelve mascara (0-1, con antialias y atenuada si el disco es menor que un píxel), perfil (hoyo esférico
        0-1), id de celda y azar (0-1 por disco, para el color)."""
        v = self.voronoi(semilla, espaciado, jitter, metrica)
        rng = np.random.default_rng(semilla + 7919)
        activo = rng.random(v.n) < prob
        R = np.where(activo, rmin + (rmax - rmin) * rng.random(v.n), 0.0).astype(np.float32)
        azar = rng.random(v.n).astype(np.float32)
        Rp = R[v.id]
        aa = 0.7 * max(self.px, self.py)
        pico = np.minimum(1.0, (Rp / aa) ** 2)
        mascara = np.clip((Rp - v.f1) / (2 * aa) + 0.5, 0, 1) * pico * (Rp > 0)
        Rm = np.maximum(Rp, aa)
        perfil = np.sqrt(np.clip(1.0 - (v.f1 / Rm) ** 2, 0, 1)) * np.minimum(1.0, Rp / aa) * (Rp > 0)
        return SimpleNamespace(mascara=mascara.astype(np.float32), perfil=perfil.astype(np.float32), id=v.id,
                               azar=azar[v.id])

    # ------------------------------------------------------------ estampas y trazos (con vuelta de borde)
    def estampar(self, capas, cx, cy, radio, f, modo="suma"):
        """Aplica f(dx, dy, ix) -> [valores por capa] en la ventana de ±radio (m) alrededor de (cx, cy). dx, dy: m
        desde el centro; ix: índice de la ventana en las matrices (con vuelta periódica). modo: suma o max."""
        c0 = int(math.floor((cx - radio) / self.px - 0.5))
        c1 = int(math.ceil((cx + radio) / self.px - 0.5))
        r0 = int(math.floor((self.h - cy - radio) / self.py - 0.5))
        r1 = int(math.ceil((self.h - cy + radio) / self.py - 0.5))
        assert c1 - c0 < self.nx and r1 - r0 < self.ny, "estampa más grande que el lienzo"
        cols, filas = np.arange(c0, c1 + 1), np.arange(r0, r1 + 1)
        dx = ((cols + 0.5) * self.px - cx).astype(np.float32)[None, :]
        dy = ((self.h - (filas + 0.5) * self.py) - cy).astype(np.float32)[:, None]
        dx, dy = np.broadcast_arrays(dx, dy)
        ix = np.ix_(filas % self.ny, cols % self.nx)
        for capa, v in zip(capas, f(dx, dy, ix)):
            if v is None:
                continue
            if modo == "suma":
                capa[ix] += v
            else:
                capa[ix] = np.maximum(capa[ix], v)

    def segmento(self, capa, p0, p1, ancho, valor=1.0, puntas=True):
        """Trazo recto de ancho (m) entre p0 y p1 (m), perfil triangular; bajo un píxel se atenúa en vez de
        adelgazar. puntas: se afina en los extremos (rayas)."""
        (x0, y0), (x1, y1) = p0, p1
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        vx, vy = x1 - x0, y1 - y0
        l2 = max(vx * vx + vy * vy, 1e-12)
        w = max(ancho, 0.8 * max(self.px, self.py))
        k = valor * min(1.0, ancho / w)

        def f(dx, dy, ix):
            qx, qy = dx + (cx - x0), dy + (cy - y0)
            t = np.clip((qx * vx + qy * vy) / l2, 0, 1)
            d = np.hypot(qx - t * vx, qy - t * vy)
            v = k * np.clip(1 - d / w, 0, 1)
            if puntas:
                v = v * ss(0, 0.2, t) * ss(1, 0.8, t)
            return [v]
        self.estampar([capa], cx, cy, math.sqrt(l2) / 2 + 2 * w, f, modo="max")

    # ------------------------------------------------------------ muestreo deformado
    def muestrear(self, a, filas, cols):
        r0, c0 = np.floor(filas), np.floor(cols)
        fr, fc = (filas - r0).astype(np.float32), (cols - c0).astype(np.float32)
        r0, c0 = r0.astype(np.int64) % self.ny, c0.astype(np.int64) % self.nx
        r1, c1 = (r0 + 1) % self.ny, (c0 + 1) % self.nx
        return ((a[r0, c0] * (1 - fc) + a[r0, c1] * fc) * (1 - fr) + (a[r1, c0] * (1 - fc) + a[r1, c1] * fc) * fr)

    def deformar(self, a, dx_m, dy_m):
        """a muestreado en (X + dx, Y + dy): desplazamiento de dominio (periódico si dx, dy lo son)."""
        cols = (self.X + dx_m) / self.px - 0.5
        filas = (self.h - (self.Y + dy_m)) / self.py - 0.5
        return self.muestrear(a, filas, cols)

    # ------------------------------------------------------------ normal
    def normal(self, h):
        """Normal tangente OpenGL (verde = +V) de un mapa de altura en metros, codificada en 0-1."""
        dhdx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * self.px)
        dhdy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) / (2 * self.py)     # fila − 1 = más arriba (v mayor)
        inv = 1.0 / np.sqrt(dhdx ** 2 + dhdy ** 2 + 1.0)
        return (np.stack((-dhdx * inv, -dhdy * inv, inv), -1) * 0.5 + 0.5).astype(np.float32)


# ======================================================================= ayudas numéricas y de color
def ss(e0, e1, x):
    """smoothstep (acepta e0 > e1: función decreciente)."""
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def col(hexa):
    return np.array([int(hexa[i:i + 2], 16) / 255.0 for i in (1, 3, 5)], np.float32)


def mezcla(a, b, t):
    t = np.asarray(t, np.float32)
    if t.ndim == 2:
        t = t[..., None]
    return a + (b - a) * t


def pulso(fase, centro, k):
    """Pulso periódico de período 1 en `fase`, máximo 1 en `centro`, más angosto con k mayor."""
    return ((1.0 + np.cos(2 * math.pi * (fase - centro))) * 0.5) ** k


def media_pulso(k):
    return float(pulso(np.linspace(0, 1, 4096, endpoint=False), 0.0, k).mean())


def f32(a):
    return np.asarray(a, np.float32)


def por_px(c, v):
    """Color (3,) o (ny, nx, 3) por un factor (ny, nx)."""
    return c * np.asarray(v, np.float32)[..., None]


def ajustar_media(c, objetivo, mascara=None):
    """Escala cada canal para que el promedio (en la máscara) sea el color objetivo (sRGB)."""
    if mascara is None:
        m = c.reshape(-1, 3).mean(0)
    else:
        w = mascara.reshape(-1)
        m = (c.reshape(-1, 3) * w[:, None]).sum(0) / max(w.sum(), 1e-6)
    return c * (objetivo / np.maximum(m, 1e-6))


def sd_rect(dx, dy, mx, my, rc):
    """Distancia con signo (positiva adentro) al borde de un rectángulo de semiejes mx, my con esquinas de radio rc."""
    qx = np.abs(dx) - (mx - rc)
    qy = np.abs(dy) - (my - rc)
    fuera = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - rc
    return -fuera


class Semillas:
    """Semillas derivadas y reproducibles: s() da un entero nuevo; s.rng sirve para sorteos."""

    def __init__(self, semilla):
        self.rng = np.random.default_rng(semilla)

    def __call__(self):
        return int(self.rng.integers(0, 2 ** 31 - 1))


# ======================================================================= texturas
def tex_microcemento(L, s):
    """Microcemento: pasadas de llana en arco que se superponen (tono y canto marcado), nubes, grano y poros."""
    r = s.rng
    sombra, canto = L.vacio(), L.vacio()
    for _ in range(190):                                 # pasadas de llana (arcos de 0,18 a 0,45 m de radio)
        cx, cy = r.uniform(0, L.w), r.uniform(0, L.h)
        R, T = r.uniform(0.16, 0.42), r.uniform(0.07, 0.12)       # radio del arco y ancho de la llana
        a0, da = r.uniform(0, 2 * math.pi), r.uniform(0.7, 1.6)
        amp = r.normal(0, 1)
        lin = r.uniform(0.4, 1.0) if r.random() < 0.6 else 0.0

        def f(dx, dy, ix, R=R, T=T, a0=a0, da=da, amp=amp, lin=lin):
            rr = np.hypot(dx, dy)
            rel = np.mod(np.arctan2(dy, dx) - a0, 2 * math.pi) / da
            fade = ss(0, 0.25, rel) * ss(1, 0.75, rel)
            d = rr - R
            banda = np.where(d > 0, ss(T / 2, T / 2 - 0.008, d), ss(-T / 2, -T / 2 + 0.035, d))
            return [amp * banda * fade, lin * np.exp(-((d - T / 2) / 0.0022) ** 2) * fade]
        L.estampar([sombra, canto], cx, cy, R + T, f)
    sombra = L.desenfocar(sombra, 0.002)
    sombra /= sombra.std() + 1e-9
    canto = np.clip(L.desenfocar(canto, 0.0012), 0, 1.5)
    nubes = L.ruido(s(), 0.9, 0.03, p=1.4)
    manchas = L.ruido(s(), 0.15, 0.006, p=1.0)
    grano = L.ruido(s(), 0.004, 0.0, p=0.3)
    tibio = L.ruido(s(), 0.7, 0.05, p=1.2)
    brillo = L.ruido(s(), 0.3, 0.01, p=1.1)
    poros = L.puntos(s(), 0.011, 0.35, 0.0004, 0.0012)
    motas = L.puntos(s(), 0.02, 0.4, 0.0005, 0.0012)
    v = 1 + 0.035 * nubes + 0.016 * manchas + 0.026 * sombra - 0.035 * canto + 0.012 * grano
    c = por_px(col("#9C9890"), v) + np.array([0.004, 0.0015, -0.004], np.float32) * tibio[..., None]
    c = mezcla(c, c * np.where(motas.azar > 0.5, 1.12, 0.86)[..., None], motas.mascara * 0.6)
    c = mezcla(c, c * 0.6, poros.mascara * 0.85)
    c = ajustar_media(c, col("#9C9890"))
    piel = L.ruido(s(), 0.003, 0.0008, p=0.5)
    h = (0.00025 * sombra + 0.0001 * canto + 0.00005 * nubes + 0.00002 * grano + 0.000012 * piel
         - 0.0004 * poros.perfil)
    rug = 0.50 + 0.05 * brillo - 0.045 * sombra - 0.08 * canto + 0.02 * grano + 0.28 * poros.mascara
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.28, 0.9))


def tex_concreto_encofrado(L, s):
    """Concreto visto de encofrado: tablas de 0,15 m con veta impresa, rebarba en las juntas, nidos y poros."""
    r = s.rng
    TABLA = 0.15                                       # docs/deco-industrial.md
    nf = int(round(L.h / TABLA))                       # 16 tablas en 2,4 m
    yy = L.y + TABLA / 2                               # medio módulo: las juntas no caen en el borde
    fila_px = (np.floor(yy / TABLA).astype(np.int64)) % nf
    b = np.broadcast_to((yy - np.floor(yy / TABLA) * TABLA)[:, None], (L.ny, L.nx)).astype(np.float32)
    tabla = np.zeros((L.ny, L.nx), np.int64)
    a = L.vacio()                                      # m a lo largo de la tabla desde su tope
    dtope = L.vacio()                                  # distancia al tope más cercano
    for f in range(nf):
        juntas = np.sort(r.uniform(0, L.w, size=1 if r.random() < 0.65 else 2))
        cnt = (L.x[:, None] >= juntas[None, :]).sum(1)
        inicio = juntas[(cnt - 1) % len(juntas)]
        d = np.abs(L.x[:, None] - juntas[None, :])
        filas = fila_px == f
        tabla[filas] = (f * 2 + cnt % len(juntas))[None, :]
        a[filas] = np.mod(L.x - inicio, L.w)[None, :]
        dtope[filas] = np.minimum(d, L.w - d).min(1)[None, :]
    nt = nf * 2
    dz, tono = r.normal(0, 0.0005, nt), r.normal(0, 0.035, nt)
    comba = r.normal(0, 0.00025, nt)
    c_p, d0 = r.uniform(-0.3, 0.45, nt), r.uniform(0.02, 0.2, nt)
    incl, paso = r.uniform(-0.05, 0.05, nt), r.uniform(0.005, 0.009, nt)
    t = tabla
    ondas = 0.004 * L.ruido(s(), 0.15, 0.01, p=1.2, estira=6) + 0.001 * L.ruido(s(), 0.02, 0.002, estira=4)
    radio = np.sqrt((b - c_p[t]) ** 2 + (d0[t] + incl[t] * (a - 1.2)) ** 2) + ondas
    fase = radio / paso[t]
    gy, gx = np.gradient(fase)
    aa = np.clip((0.4 - np.hypot(gx, gy)) / 0.2, 0, 1)
    tardia = aa * pulso(fase, 0.8, 8) + (1 - aa) * media_pulso(8)
    fibra = L.ruido(s(), 0.02, 0.002, p=0.8, estira=10)
    dj = np.minimum(np.minimum(b, TABLA - b), dtope)
    rebaba = np.exp(-(dj / 0.0014) ** 2) * (0.6 + 0.4 * ss(-1, 1, L.ruido(s(), 0.05, 0.004)))
    nidos = L.puntos(s(), 0.045, 0.14, 0.0012, 0.005)
    poros = L.puntos(s(), 0.012, 0.3, 0.0003, 0.0010)
    nubes = L.ruido(s(), 1.0, 0.05, p=1.4)
    agua = ss(0.8, 2.2, L.ruido(s(), 0.3, 0.02, p=1.2))
    lechada = ss(0.6, 2.0, L.ruido(s(), 0.2, 0.015, p=1.0))
    grano = L.ruido(s(), 0.004, 0.0, p=0.3)
    u = (b / TABLA - 0.5) * 2
    h = (dz[t] + comba[t] * u * u - 0.0002 * tardia + 0.00004 * fibra + 0.0005 * rebaba
         - 0.0022 * nidos.perfil - 0.0005 * poros.perfil + 0.00002 * grano)
    v = (1 + tono[t] + 0.04 * nubes - 0.07 * (tardia - media_pulso(8)) + 0.012 * fibra - 0.06 * rebaba
         - 0.05 * agua + 0.04 * lechada + 0.015 * grano)
    c = por_px(col("#B3AFA8"), v) + np.array([0.006, 0.002, -0.006], np.float32) * L.ruido(s(), 0.6, 0.05)[..., None]
    c = mezcla(c, c * 0.62, nidos.mascara * (0.6 + 0.4 * nidos.azar))
    c = mezcla(c, c * 0.8, poros.mascara * 0.7)
    c = ajustar_media(c, col("#B3AFA8"))
    rug = 0.86 + 0.04 * nubes - 0.10 * lechada + 0.03 * fibra + 0.1 * nidos.mascara
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.55, 1.0))


def tex_ladrillo(L, s):
    """Ladrillo a la vista, aparejo soga 24 × 7 cm con junta de 1 cm hundida: color por ladrillo, cantos gastados y
    despostillados, superficie arenosa, motas y restos de mortero."""
    r = s.rng
    MX, MY = 0.25, 0.08                                # módulo = ladrillo + junta (docs: 24 × 7, junta 1 cm)
    nf, npf = int(round(L.h / MY)), int(round(L.w / MX))            # 16 hiladas × 5 ladrillos
    X, Y = L.X + MX / 4, L.Y + MY / 2                  # desfase: las juntas no caen en el borde
    fila = np.floor(Y / MY).astype(np.int64)
    yb = Y - fila * MY
    fila %= nf
    xo = X + (fila % 2) * (MX / 2)
    cc = np.floor(xo / MX).astype(np.int64)
    xb = xo - cc * MX
    idl = fila * npf + cc % npf
    n = nf * npf
    largo, alto = 0.24 + r.normal(0, 0.0015, n), 0.07 + r.normal(0, 0.0009, n)
    ox, oy = r.normal(0, 0.0012, n), r.normal(0, 0.0007, n)
    sd = sd_rect(xb - MX / 2 - ox[idl], yb - MY / 2 - oy[idl], largo[idl] / 2, alto[idl] / 2, 0.002)
    sd = sd + 0.0008 * L.ruido(s(), 0.015, 0.003, p=0.8)
    sd = sd - 0.005 * ss(1.5, 2.7, L.ruido(s(), 0.025, 0.004, p=1.0))          # despostillados en los cantos
    cara = ss(0.0, 0.0035, sd)
    lx, ly = r.normal(0, 0.004, n), r.normal(0, 0.006, n)                       # ladrillos algo torcidos
    dz = r.normal(0, 0.0008, n)
    arena = L.ruido(s(), 0.004, 0.0005, p=0.8)
    pliegue = L.ruido(s(), 0.03, 0.002, p=1.0, estira=5)
    hoyos = L.puntos(s(), 0.006, 0.25, 0.0004, 0.0013)
    h_l = (0.010 + dz[idl] + lx[idl] * (xb - MX / 2) + ly[idl] * (yb - MY / 2) + 0.00025 * arena
           + 0.0003 * pliegue - 0.0008 * hoyos.perfil)
    fuera = np.clip(-sd, 0, 0.01)
    arena_m = L.ruido(s(), 0.003, 0.0004, p=0.5)
    h_m = 0.0038 + 0.0002 * arena_m - 0.0008 * ss(0.0, 0.005, fuera)
    h = h_m + (h_l - h_m) * cara
    # color por ladrillo
    rojo, marron, oscuro, claro = col("#904C37"), col("#6F4031"), col("#4A2D25"), col("#9E6149")
    ceniza = col("#6E5850")
    t1 = r.random(n)
    base = marron[None, :] + (rojo - marron)[None, :] * t1[:, None]
    tipo = r.random(n)
    base = np.where((tipo < 0.12)[:, None], base + (oscuro - base) * 0.65, base)
    base = np.where((tipo > 0.91)[:, None], base + (claro - base) * 0.7, base)
    base = np.where(((tipo > 0.12) & (tipo < 0.2))[:, None], base + (ceniza - base) * 0.6, base)
    base = base * np.clip(r.normal(1, 0.06, n), 0.85, 1.15)[:, None]
    cb = base[idl].astype(np.float32)
    quema = np.where(r.random(n) < 0.18, 1.0, 0.0)[idl] * ss(0.09, 0.0, np.where(
        (r.random(n) < 0.5)[idl], xb, MX - xb))
    mot = L.ruido(s(), 0.05, 0.003, p=1.0)
    v = (1 + 0.05 * mot + 0.03 * arena + 0.04 * pliegue) * (1 - 0.35 * quema)
    cb = por_px(cb, v)
    mang = L.puntos(s(), 0.006, 0.35, 0.0003, 0.0009)
    cb = mezcla(cb, cb * 0.55, mang.mascara)
    cal = L.puntos(s(), 0.008, 0.25, 0.0003, 0.0008)
    cb = mezcla(cb, col("#C49E86"), cal.mascara * 0.6)
    resto = ss(0.8, 1.8, L.ruido(s(), 0.02, 0.003)) * ss(0.012, 0.0, sd) * (r.random(n) < 0.3)[idl]
    cb = mezcla(cb, col("#A69E94"), resto * 0.55)
    ladrillo = ss(-0.0003, 0.0012, sd)
    cb = ajustar_media(cb, col("#8C4A36"), ladrillo)
    cm = por_px(col("#9A948A"), (1 + 0.045 * arena_m) * (0.62 + 0.38 * ss(0, 0.004, fuera))
                * (1 - 0.1 * ss(-0.5, 1.5, L.ruido(s(), 0.1, 0.01, p=1.0))))
    cm = mezcla(cm, cm * 0.8, L.puntos(s(), 0.006, 0.2, 0.0002, 0.0005).mascara)
    c = mezcla(cm, cb, ladrillo)
    c = por_px(c, 1 - 0.05 * ss(0, 1.5, L.ruido(s(), 0.4, 0.05, p=1.2)))          # hollín suave
    rug = np.where(ladrillo > 0.5, 0.80 + 0.05 * mot + 0.05 * hoyos.mascara, 0.93 + 0.03 * arena_m)
    return dict(color=c, altura=h, rugosidad=np.clip(rug + 0.04 * resto, 0.6, 1.0))


def tex_azulejo_subway(L, s):
    """Azulejo subway blanco brillante biselado de 7,5 × 15 cm, trabado a la mitad, junta gris oscura de 2 mm."""
    r = s.rng
    MX, MY, J = 0.15, 0.075, 0.002                     # docs: 7,5 × 15, junta 2 mm
    nf, npf = int(round(L.h / MY)), int(round(L.w / MX))            # 8 hiladas × 4
    fila = np.floor((L.Y + MY / 2) / MY).astype(np.int64)            # desfase de medio módulo
    yb = L.Y + MY / 2 - fila * MY
    fila %= nf
    xo = L.X + MX / 4 + (fila % 2) * (MX / 2)
    cc = np.floor(xo / MX).astype(np.int64)
    xb = xo - cc * MX
    ida = fila * npf + cc % npf
    n = nf * npf
    sd = sd_rect(xb - MX / 2, yb - MY / 2, (MX - J) / 2, (MY - J) / 2, 0.0025)
    t = np.clip(sd / 0.009, 0, 1)                      # bisel de 9 mm
    bisel = 1 - (1 - t) ** 2.2
    labio = ss(0.0, 0.0007, sd)
    ondas = L.ruido(s(), 0.05, 0.01, p=1.2)
    piel = L.ruido(s(), 0.002, 0.0006, p=0.4)
    ix, iy, iz = r.normal(0, 0.0012, n), r.normal(0, 0.002, n), r.normal(0, 0.00012, n)
    h_a = labio * (0.0028 * bisel + 0.00013 * ondas + ix[ida] * (xb - MX / 2) + iy[ida] * (yb - MY / 2) + iz[ida]
                   + 0.000004 * piel)
    arena = L.ruido(s(), 0.0015, 0.0003, p=0.4)
    h_j = -0.0007 + 0.00008 * arena
    cara = ss(-0.0002, 0.0004, sd)
    h = h_j + (h_a - h_j) * cara
    blanco = col("#F1F0EB")
    tv = np.clip(r.normal(1, 0.011, n), 0.97, 1.02)
    tt = r.normal(0, 0.005, n)
    ca = por_px(blanco, tv[ida] * (1 + 0.004 * ondas)) + np.stack((tt, tt * 0.3, -tt), -1)[ida].astype(np.float32)
    ca = mezcla(ca, col("#E0E0D8"), 0.5 * (1 - bisel) * labio)                 # esmalte más grueso en el bisel
    motas = L.puntos(s(), 0.02, 0.12, 0.00015, 0.0004)
    ca = mezcla(ca, ca * 0.75, motas.mascara)
    cj = por_px(col("#4E4E4C"), 1 + 0.09 * arena)
    c = mezcla(cj, ca, cara)
    rv = r.uniform(0.05, 0.1, n)
    rug = cara * (rv[ida] + 0.01 * ondas) + (1 - cara) * (0.86 + 0.04 * arena)
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.03, 1.0))


def tex_baldosa_hex(L, s):
    """Baldosa hexagonal de 10 cm entre caras, gris carbón con variación por pieza, junta gris clara de 2 mm."""
    r = s.rng
    D = 0.10                                           # docs: hexágonos de 10 cm (entre caras paralelas)
    RY = D * SQ3 / 2                                   # separación de hileras
    X, Y = L.X, L.Y
    nx6, nj = int(round(L.w / D)), int(round(L.h / (2 * RY)))       # 6 × 4 (dos redes desfasadas)
    ia, ja = np.round(X / D), np.round(Y / (2 * RY))
    ax, ay = X - ia * D, Y - ja * 2 * RY
    ib, jb = np.round((X - D / 2) / D), np.round((Y - RY) / (2 * RY))
    bx, by = X - ib * D - D / 2, Y - jb * 2 * RY - RY
    usa_b = bx * bx + by * by < ax * ax + ay * ay
    dx, dy = np.where(usa_b, bx, ax), np.where(usa_b, by, ay)
    idh = np.where(usa_b, nj * nx6 + (jb.astype(np.int64) % nj) * nx6 + ib.astype(np.int64) % nx6,
                   (ja.astype(np.int64) % nj) * nx6 + ia.astype(np.int64) % nx6)
    n = 2 * nj * nx6
    hexd = np.maximum(np.abs(dx), 0.5 * np.abs(dx) + SQ3 / 2 * np.abs(dy))
    sd = D / 2 - hexd + 0.00015 * L.ruido(s(), 0.01, 0.002, p=0.8)
    cara = ss(0.0008, 0.0022, sd)
    ix, iy, iz = r.normal(0, 0.002, n), r.normal(0, 0.002, n), r.normal(0, 0.0001, n)
    mot = L.ruido(s(), 0.03, 0.002, p=1.0)
    grano = L.ruido(s(), 0.002, 0.0, p=0.3)
    arena = L.ruido(s(), 0.0015, 0.0003, p=0.4)
    h = cara * (0.0015 + ix[idh] * dx + iy[idh] * dy + iz[idh] + 0.00002 * mot) + 0.00012 * arena * (1 - cara)
    tv = np.clip(r.normal(1, 0.09, n), 0.78, 1.25)
    ct = por_px(col("#3B3B3A"), tv[idh] * (1 + 0.05 * mot + 0.025 * grano))
    motas = L.puntos(s(), 0.003, 0.3, 0.0002, 0.0005)
    ct = mezcla(ct, col("#62615E"), motas.mascara * 0.6)
    cj = por_px(col("#BAB6AE"), 1 + 0.07 * arena)
    junta = ss(0.0006, 0.0013, sd)
    c = mezcla(cj, ct, junta)
    rv = r.uniform(0.44, 0.58, n)
    rug = junta * (rv[idh] + 0.03 * mot) + (1 - junta) * 0.9
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.3, 1.0))


def tex_losa_hormigon(L, s):
    """Baldosas de hormigón de 60 × 60 cm (balcón): áridos finos, barrido suave, suciedad en las juntas."""
    r = s.rng
    LOSA = 0.60
    nl = int(round(L.w / LOSA))
    X, Y = L.X + LOSA / 2, L.Y + LOSA / 2              # desfase: las juntas no caen en el borde
    i = np.floor(X / LOSA).astype(np.int64)
    j = np.floor(Y / LOSA).astype(np.int64)
    lx, ly = X - i * LOSA, Y - j * LOSA
    idl = (j % nl) * nl + i % nl
    n = nl * nl
    sd = sd_rect(lx - LOSA / 2, ly - LOSA / 2, LOSA / 2 - 0.0025, LOSA / 2 - 0.0025, 0.004)
    sd = sd + 0.0006 * L.ruido(s(), 0.006, 0.001, p=0.7)
    sd = sd - 0.007 * ss(1.5, 2.7, L.ruido(s(), 0.03, 0.004))                  # cantos saltados
    chaflan = ss(0.0, 0.003, sd)
    barrido0 = L.ruido(s(), 0.01, 0.0008, p=0.5, estira=25, angulo=0)
    barrido1 = L.ruido(s(), 0.01, 0.0008, p=0.5, estira=25, angulo=90)
    dir_b = (r.random(n) < 0.5)[idl]
    barrido = np.where(dir_b, barrido0, barrido1)
    arena = L.ruido(s(), 0.003, 0.0004, p=0.5)
    arido = L.puntos(s(), 0.0045, 0.5, 0.0005, 0.0017)
    poros = L.puntos(s(), 0.01, 0.3, 0.0003, 0.0011)
    ix, iy = r.normal(0, 0.002, n), r.normal(0, 0.002, n)
    h_l = (0.004 * chaflan + ix[idl] * (lx - LOSA / 2) * chaflan + iy[idl] * (ly - LOSA / 2) * chaflan
           + 0.00008 * barrido + 0.00008 * arena + 0.00012 * arido.perfil - 0.0006 * poros.perfil)
    h_j = 0.0006 + 0.0002 * L.ruido(s(), 0.002, 0.0003, p=0.4)
    losa = ss(-0.0003, 0.0006, sd)
    h = h_j + (h_l - h_j) * losa
    tv, tt = np.clip(r.normal(1, 0.045, n), 0.9, 1.1), r.normal(0, 0.008, n)
    nubes = L.ruido(s(), 0.4, 0.03, p=1.3)
    manchas = L.ruido(s(), 0.08, 0.005, p=1.0)
    agua = ss(0.6, 2.0, L.ruido(s(), 0.2, 0.02, p=1.2))
    v = tv[idl] * (1 + 0.05 * nubes + 0.025 * manchas + 0.03 * arena + 0.02 * barrido) * (1 - 0.06 * agua)
    cl = por_px(col("#8E8B84"), v) + np.stack((tt, tt * 0.3, -tt), -1)[idl].astype(np.float32)
    tono_a = np.where(arido.azar < 0.4, 0, np.where(arido.azar < 0.75, 1, 2))
    paleta_a = np.stack([col("#ABA9A2"), col("#5F5D58"), col("#A09482")])
    cl = mezcla(cl, paleta_a[tono_a], arido.mascara * 0.45)
    cl = mezcla(cl, cl * 0.6, poros.mascara * 0.8)
    sucio = ss(0.03, 0.0, sd) * (0.5 + 0.5 * ss(-1, 1, L.ruido(s(), 0.03, 0.004)))
    cl = por_px(cl, 1 - 0.2 * sucio)
    cj = por_px(col("#58544D"), 1 + 0.1 * arena)
    c = mezcla(cj, cl, losa)
    rug = losa * (0.82 + 0.04 * nubes + 0.03 * barrido) + (1 - losa) * 0.95
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.6, 1.0))


def veta_roble(L, s, fase, aa, q):
    """Anillos de roble a partir de su fase (ciclos): madera temprana porosa (líneas oscuras), poros alargados a lo
    largo de la veta (+U) y radios medulares (motas claras alargadas, más visibles en corte radial, q ≈ 1).
    aa (0-1) apaga los anillos donde son más finos que dos píxeles. Devuelve (factor de color, altura m, Δrugosidad)."""
    temprana = aa * pulso(fase, 0.10, 8) + (1 - aa) * media_pulso(8)
    tardia = aa * pulso(fase, 0.60, 2) + (1 - aa) * media_pulso(2)
    banda = pulso(fase / 5.0, 0.0, 1.2) - media_pulso(1.2)        # grupos de anillos: la figura que se ve de lejos
    fibra = L.ruido(s(), 0.006, 0.0008, p=0.6, estira=20)
    poros = ss(1.3, 2.5, L.ruido(s(), 0.002, 0.0003, p=0.2, estira=16)) * (0.2 + 1.0 * temprana)
    radios = L.puntos(s(), 0.004, 0.45, 0.0006, 0.0014, jitter=0.9, metrica=(4.0, 1.0)).mascara * (0.35 + 0.65 * q)
    fac = (1 - 0.30 * temprana - 0.07 * (tardia - media_pulso(2)) + 0.08 * banda - 0.12 * poros + 0.03 * fibra
           + 0.08 * radios)
    alt = -0.00008 * temprana - 0.0001 * poros + 0.00002 * fibra + 0.00002 * radios
    drug = 0.06 * temprana + 0.1 * poros - 0.08 * radios
    return fac, alt, drug


def tex_piso_roble(L, s):
    """Piso de tablas de roble ahumado de 0,20 × 1,20 m, trabadas al azar: veta de tronco (catedrales y rayado),
    nudos ocasionales, color por tabla, microbisel y juntas finas."""
    r = s.rng
    ANCHO, LARGO = 0.20, 1.20                          # docs/deco-industrial.md
    nf = int(round(L.h / ANCHO))                       # 12 hileras × 2 tablas (2,4 m)
    ofs = []
    for f in range(nf):
        for _ in range(200):
            o = r.uniform(0, LARGO)
            ok = not ofs or abs((o - ofs[-1] + LARGO / 2) % LARGO - LARGO / 2) > 0.25
            if ok and f == nf - 1:
                ok = abs((o - ofs[0] + LARGO / 2) % LARGO - LARGO / 2) > 0.25
            if ok:
                break
        ofs.append(o)
    fila = np.floor((L.Y + ANCHO / 2) / ANCHO).astype(np.int64)      # desfase de media tabla
    b = L.Y + ANCHO / 2 - fila * ANCHO
    fila %= nf
    xr = np.mod(L.X - np.array(ofs, np.float32)[fila], 2 * LARGO)
    k = (xr >= LARGO).astype(np.int64)
    a = xr - k * LARGO
    tb = fila * 2 + k
    n = nf * 2
    cp, d0 = r.uniform(-0.25, 0.45, n), r.uniform(0.03, 0.2, n)          # posición de la médula bajo la tabla
    incl, paso = r.uniform(-0.06, 0.06, n), r.uniform(0.006, 0.010, n)    # inclinación del tronco, anillo
    radio_log = np.sqrt((b - cp[tb]) ** 2 + (d0[tb] + incl[tb] * (a - LARGO / 2)) ** 2)
    rr = radio_log + 0.003 * L.ruido(s(), 0.12, 0.01, p=1.2, estira=6) + 0.0007 * L.ruido(s(), 0.02, 0.002, estira=4)
    q = np.clip(np.abs(b - cp[tb]) / np.maximum(radio_log, 1e-4), 0, 1) ** 2
    nudo, nudo_r = L.vacio(), L.vacio()
    for _ in range(6):                                 # nudos ocasionales
        t_id = int(r.integers(n))
        f_id, k_id = divmod(t_id, 2)
        ak, bk, R = r.uniform(0.1, 1.1), r.uniform(0.045, 0.155), r.uniform(0.004, 0.010)
        xk = (ofs[f_id] + k_id * LARGO + ak) % L.w
        yk = (f_id * ANCHO + bk - ANCHO / 2) % L.h

        def fn(dx, dy, ix, R=R, t_id=t_id):
            d = np.hypot(dx, dy * 1.3)
            misma = tb[ix] == t_id
            return [np.where(misma, 3.5 * paso[t_id] * (R / 0.007) * np.exp(-(d / (2.8 * R)) ** 2), 0),
                    np.where(misma, np.clip(1 - d / R, 0, 1), 0)]
        L.estampar([nudo, nudo_r], xk, yk, 9 * R, fn)
    rr = rr + nudo
    fase = rr / paso[tb] + r.random(n)[tb]
    gy, gx = np.gradient(fase)
    aa = np.clip((0.40 - np.hypot(gx, gy)) / 0.2, 0, 1)
    fac, alt, drug = veta_roble(L, s, fase, aa, q)
    tv = np.clip(r.normal(1, 0.075, n), 0.84, 1.16)
    tc = r.uniform(0, 1, n)
    base = (col("#66503F")[None, :] + (col("#75523A") - col("#66503F"))[None, :] * tc[:, None]) * tv[:, None]
    c = por_px(base[tb].astype(np.float32), fac * (1 + 0.03 * L.ruido(s(), 0.8, 0.1, p=1.2)))
    nucleo = ss(0.0, 0.35, nudo_r)
    c = mezcla(c, por_px(col("#3A2A20"), 0.9 + 0.1 * pulso(nudo_r * 7, 0, 2)), nucleo * 0.85)
    sd = np.minimum(np.minimum(a, LARGO - a), np.minimum(b, ANCHO - b))
    junta = 1 - ss(0.0, 1.3 * L.px, sd)
    c = por_px(c, 1 - 0.6 * junta)
    c = ajustar_media(c, col("#6B4F3A"))
    dzt, cup = r.normal(0, 0.00008, n), r.normal(0, 0.0001, n)
    u = (b / ANCHO - 0.5) * 2
    h = alt + dzt[tb] + cup[tb] * u * u - 0.0006 * (1 - ss(0.0, 0.0025, sd)) - 0.0002 * nucleo
    rv = r.uniform(0.44, 0.54, n)
    rug = rv[tb] + drug + 0.1 * nucleo + 0.2 * junta
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.3, 0.9))


def tex_roble_ahumado(L, s):
    """Roble ahumado para muebles: veta continua (sin juntas) de chapa plana, con catedrales por deformación de la
    fase y zonas de corte radial con radios medulares."""
    K = 150                                            # anillos visibles por repetición: 8 mm en 1,2 m (supuesto)
    w1 = L.ruido(s(), 0.15, 0.01, p=1.7, estira=4)
    w2 = L.ruido(s(), 0.04, 0.004, p=1.2, estira=5)
    w3 = L.ruido(s(), 0.015, 0.0015, p=1.0, estira=4)
    per = K * (L.h - L.Y) / L.h                        # parte lineal: K entero (y múltiplo de 5) asegura la repetición
    w = 11.0 * w1 + 1.5 * w2 + 0.3 * w3
    fase = per + w
    gy, gx = np.gradient(w)
    gy = gy - K / L.ny
    aa = np.clip((0.40 - np.hypot(gx, gy)) / 0.2, 0, 1)
    q = ss(0.3, 1.6, L.ruido(s(), 0.25, 0.03, p=1.2))
    fac, alt, drug = veta_roble(L, s, fase, aa, q)
    tono = L.ruido(s(), 0.15, 0.02, p=1.3, estira=8)
    c = por_px(col("#6B4F3A"), fac * (1 + 0.03 * tono))
    c = c + np.array([0.005, 0.002, -0.003], np.float32) * L.ruido(s(), 0.3, 0.05, estira=4)[..., None]
    c = ajustar_media(c, col("#6B4F3A"))
    h = alt + 0.00003 * L.ruido(s(), 0.2, 0.02, p=1.0)
    rug = 0.48 + drug + 0.03 * tono
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.3, 0.9))


def tex_acero_pavonado(L, s):
    """Acero pavonado: negro azulado con manchas pardas del pavonado, cepillado en +U, algunas rayas claras."""
    r = s.rng
    mot = L.ruido(s(), 0.35, 0.02, p=1.4)
    mot2 = L.ruido(s(), 0.08, 0.006, p=1.0)
    calamina = ss(1.0, 2.4, L.ruido(s(), 0.15, 0.015, p=1.2))
    cep = L.ruido(s(), 0.06, 0.0004, p=0.7, estira=45)
    cep2 = L.ruido(s(), 0.2, 0.001, p=0.5, estira=80)
    c = mezcla(col("#1F2227"), col("#2A2724"), ss(-1.6, 1.6, mot))
    c = mezcla(c, col("#34363A"), 0.35 * calamina)
    c = por_px(c, 1 + 0.06 * mot2 + 0.04 * cep + 0.03 * cep2)
    rayas = L.vacio()
    for _ in range(45):
        x0, y0 = r.uniform(0, L.w), r.uniform(0, L.h)
        ang = math.radians(r.normal(0, 20) if r.random() < 0.7 else r.uniform(0, 180))
        lg = r.uniform(0.015, 0.16)
        L.segmento(rayas, (x0, y0), (x0 + lg * math.cos(ang), y0 + lg * math.sin(ang)),
                   r.uniform(0.00012, 0.0003), r.uniform(0.3, 1.0))
    c = mezcla(c, col("#6A6D72"), 0.45 * rayas)
    c = ajustar_media(c, col("#232426"))
    rug = 0.36 + 0.05 * mot + 0.04 * cep + 0.05 * calamina - 0.1 * rayas
    h = 0.000008 * cep + 0.00004 * L.ruido(s(), 0.15, 0.02, p=1.0) - 0.00002 * rayas
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.2, 0.6))


def tex_acero_cepillado(L, s):
    """Acero inoxidable cepillado (electrodomésticos; corrección 07c): gris frío claro, vetas rectas muy finas y parejas
    a lo largo de V (verticales en la puerta de la nevera, a lo largo en la visera de la campana y el marco del horno,
    que llevan el UV girado), de contraste bajo, y una nube apenas perceptible. Sin ondulación ni vetas anchas de brillo
    desigual: con ellas (versión 07b) la chapa se leía como madera clara veteada.
    Corrección 07c (ronda 1): sólo queda el rayado submilimétrico, con un paso alto que le quita todo rasgo de más de
    ~1,5 mm de ancho, y la nube. La capa "medio" (pasadas de 0,7-10 mm, estirada 260 veces) sobrevivía al filtrado de
    mipmaps y, en un metal, el albedo multiplica el reflejo: a 1-2 m la puerta mostraba franjas verticales de 3 a 8 mm,
    como vidrio acanalado. El rayado fino se promedia por mip a esa distancia (un píxel del render cubre ~2 mm).
    Rugosidad de 0,25 a 0,35 que sigue al rayado y a la nube; el relieve son surcos de décimas de micra."""
    fino = L.ruido(s(), 0.004, 0.00025, p=0.3, estira=420, angulo=90.0)     # rayado del cepillo: ~0,25 mm de ancho
    fino = fino - L.desenfocar(fino, 0.0005)                                 # paso alto (sigma 0,5 mm): sin franjas
    fino = fino / (fino.std() + 1e-12)
    nube = L.ruido(s(), 0.12, 0.04, p=1.2)                                  # variación de brillo de la chapa, muy suave
    c = por_px(col("#C3C7CB"), 1 + 0.014 * fino + 0.006 * nube)
    c = ajustar_media(c, col("#C3C7CB"))
    rug = 0.30 + 0.018 * fino + 0.012 * nube
    h = 0.000005 * fino
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.25, 0.35))


def tex_cuero(L, s):
    """Cuero coñac: flor granulada (celdas de 1,5 a 3,5 mm), arrugas suaves, poros y desgaste más claro en lo alto."""
    r = s.rng
    v1 = L.voronoi(s(), 0.0017, jitter=1.0)
    v2 = L.voronoi(s(), 0.0036, jitter=1.0)
    g1 = np.clip(1 - (2 * v1.f1 / (v1.f1 + v1.f2 + 1e-9)) ** 2, 0, 1) ** 0.7     # granos redondeados
    g2 = np.clip(1 - (2 * v2.f1 / (v2.f1 + v2.f2 + 1e-9)) ** 2, 0, 1) ** 0.7
    grano = 0.6 * g1 + 0.4 * g2
    v3 = L.voronoi(s(), 0.007, jitter=1.0)            # pliegues del batanado: polígonos de 5 a 10 mm
    arr = L.deformar(np.exp(-((v3.f2 - v3.f1) / 0.00045) ** 2),
                     0.0012 * L.ruido(s(), 0.006, 0.001), 0.0012 * L.ruido(s(), 0.006, 0.001))
    arr = L.desenfocar(arr * (0.35 + 0.65 * ss(-1.0, 1.0, L.ruido(s(), 0.02, 0.004, p=1.0))), 0.0003)
    ondul = L.ruido(s(), 0.06, 0.006, p=1.2)
    poros = L.puntos(s(), 0.0011, 0.3, 0.00008, 0.00016)
    h = 0.00006 * grano - 0.00016 * arr + 0.00015 * ondul - 0.00004 * poros.perfil
    alto = grano + 0.35 * ondul - 0.8 * arr
    alto = (alto - alto.mean()) / (alto.std() + 1e-9)
    desgaste = ss(0.4, 1.6, alto) * ss(-0.5, 1.5, L.ruido(s(), 0.15, 0.02, p=1.2))
    mot = L.ruido(s(), 0.2, 0.006, p=1.3)
    c = por_px(col("#8A4B2A"), (1 + 0.045 * mot) * (0.9 + 0.1 * grano) * (1 - 0.17 * arr))
    c = mezcla(c, col("#AC6A3E"), 0.35 * desgaste)
    c = mezcla(c, c * 0.7, poros.mascara)
    c = ajustar_media(c, col("#8A4B2A"))
    rug = 0.45 + 0.08 * (1 - grano) + 0.12 * arr - 0.08 * desgaste + 0.03 * mot
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.28, 0.75))


def tex_lana(L, s):
    """Lana bouclé color avena: rulos irregulares de hilo grueso (arcos abiertos y motas de 3 a 6 mm), apretados y
    superpuestos sobre un tejido de base de 2 mm."""
    r = s.rng
    hmax, suma, tono_p, peso = L.vacio(), L.vacio(), L.vacio(), L.vacio()
    for celda, amp0 in ((0.0045, 1.0), (0.0055, 0.95), (0.0038, 0.9), (0.005, 0.85)):
        ncx, ncy, jx, jy = L.grilla_puntos(s(), celda, 1.0)
        nc = ncx * ncy
        R, W = f32(r.uniform(0.25, 0.42, nc) * celda), f32(r.uniform(0.13, 0.2, nc) * celda)
        e, ang = f32(r.uniform(0.65, 1.0, nc)), r.uniform(0, math.pi, nc)
        ca, sa = f32(np.cos(ang)), f32(np.sin(ang))
        amp, ext, th0 = f32(amp0 * r.uniform(0.6, 1.0, nc)), f32(r.uniform(0.55, 1.0, nc)), f32(r.uniform(0, 6.3, nc))
        wob, fw = f32(r.uniform(0, 0.25, nc)), f32(r.uniform(0, 6.3, nc))
        bola, tn = r.random(nc) < 0.15, f32(r.random(nc))
        for dx, dy, k in L.vecinos(ncx, ncy, jx, jy):
            u = dx * ca[k] + dy * sa[k]
            v = (-dx * sa[k] + dy * ca[k]) / e[k]
            d = np.sqrt(u * u + v * v)
            th = np.arctan2(v, u)
            rk = R[k] * (1 + wob[k] * np.cos(2 * th + fw[k]))
            rel = np.mod(th - th0[k], 2 * math.pi) / (2 * math.pi * ext[k])
            arco = ss(0, 0.12, rel) * ss(1, 0.88, rel)
            forma = np.where(bola[k], np.exp(-(d / (0.75 * R[k])) ** 2), np.exp(-((d - rk) / W[k]) ** 2) * arco)
            forma = forma * amp[k]
            hmax = np.maximum(hmax, forma)
            suma += forma
            w4 = forma ** 4
            tono_p += w4 * tn[k]
            peso += w4
    tono = (tono_p + 0.01 * 0.5) / (peso + 0.01)       # en los huecos, tono medio (sin bloques)
    fibras = L.ruido(s(), 0.0012, 0.0003, p=0.5)
    P = L.h / int(round(L.h / 0.002))                  # tejido de base de 2 mm (divide exacto la repetición)
    base = 0.5 + 0.25 * (np.sin(2 * math.pi * L.X / P) * np.sin(2 * math.pi * L.Y / P))
    hh = np.clip(0.6 * hmax + 0.15 * np.clip(suma, 0, 2) + 0.15 * base + 0.06 * fibras, 0, 1.3)
    c = mezcla(col("#CBBFAB"), col("#E2D9CB"), tono)
    c = por_px(c, (0.72 + 0.32 * np.clip(hh, 0, 1)) * (1 + 0.04 * fibras))
    c = ajustar_media(c, col("#D8CFC0"))
    rug = 0.95 - 0.05 * np.clip(hh, 0, 1) + 0.02 * fibras
    return dict(color=c, altura=0.0016 * hh, rugosidad=np.clip(rug, 0.8, 1.0))


def tex_yute(L, s):
    """Yute natural en tejido de canasta 2 × 2 (hilos de 7,8 mm): perfil redondeado, torsión, fibras y color por
    hilo, algunas hebras sueltas."""
    r = s.rng
    NH = 64                                            # hilos por repetición (0,5 m / 64 = 7,8 mm)
    paso = L.w / NH
    gi, gj = L.X / paso + 0.5, L.Y / paso + 0.5        # desfase de medio hilo
    i, j = np.floor(gi).astype(np.int64), np.floor(gj).astype(np.int64)
    lx, ly = gi - i, gj - j
    i %= NH
    j %= NH
    urd = ((i // 2 + j // 2) % 2) == 0                 # urdimbre (vertical) arriba
    gros_u = 1 + 0.12 * L.ruido(s(), 0.05, 0.004, p=1.0, estira=30, angulo=90)
    gros_t = 1 + 0.12 * L.ruido(s(), 0.05, 0.004, p=1.0, estira=30, angulo=0)
    perf_u = np.sqrt(np.clip(1 - ((2 * lx - 1) / gros_u) ** 2, 0, 1))
    perf_t = np.sqrt(np.clip(1 - ((2 * ly - 1) / gros_t) ** 2, 0, 1))
    comba_u = 0.4 + 0.6 * np.sin(math.pi * ((j % 2) + ly) / 2) ** 0.7
    comba_t = 0.4 + 0.6 * np.sin(math.pi * ((i % 2) + lx) / 2) ** 0.7
    ph_u, ph_t = r.random(NH).astype(np.float32), r.random(NH).astype(np.float32)
    PT = 128                                           # cabos de la torsión por repetición (3,9 mm)
    tors_u = 0.5 + 0.5 * np.cos(2 * math.pi * (L.Y / L.h * PT + 1.2 * lx + ph_u[i]))
    tors_t = 0.5 + 0.5 * np.cos(2 * math.pi * (L.X / L.w * PT + 1.2 * ly + ph_t[j]))
    fib_u = L.ruido(s(), 0.004, 0.0003, p=0.5, estira=12, angulo=90)
    fib_t = L.ruido(s(), 0.004, 0.0003, p=0.5, estira=12, angulo=0)
    hh = np.where(urd, perf_u * comba_u * (0.8 + 0.2 * tors_u), perf_t * comba_t * (0.8 + 0.2 * tors_t))
    fib = np.where(urd, fib_u, fib_t)
    hh = hh + 0.05 * fib
    tu, tt = r.random(NH).astype(np.float32), r.random(NH).astype(np.float32)
    largo_u = ss(-1.6, 1.6, L.ruido(s(), 0.03, 0.004, p=1.0, estira=12, angulo=90))
    largo_t = ss(-1.6, 1.6, L.ruido(s(), 0.03, 0.004, p=1.0, estira=12, angulo=0))
    tono = np.where(urd, 0.35 * tu[i] + 0.65 * largo_u, 0.35 * tt[j] + 0.65 * largo_t)
    c = mezcla(col("#9A7F59"), col("#BCA17A"), tono)
    c = por_px(c, (0.62 + 0.42 * np.clip(hh, 0, 1)) * (1 + 0.07 * fib))
    hebras = L.vacio()
    for _ in range(70):
        x0, y0 = r.uniform(0, L.w), r.uniform(0, L.h)
        ang, lg = r.uniform(0, math.pi), r.uniform(0.008, 0.03)
        L.segmento(hebras, (x0, y0), (x0 + lg * math.cos(ang), y0 + lg * math.sin(ang)), 0.00012, r.uniform(0.4, 1))
    c = mezcla(c, col("#CDB690"), 0.5 * hebras)
    c = ajustar_media(c, col("#A48A63"))
    rug = 0.92 - 0.04 * hh + 0.02 * fib
    return dict(color=c, altura=0.0025 * hh + 0.0001 * hebras, rugosidad=np.clip(rug, 0.8, 1.0))


def tex_concreto_oscuro(L, s):
    """Concreto pulido gris oscuro para cubiertas: nubes, áridos finos claros y oscuros, poros y brillo desparejo."""
    nubes = L.ruido(s(), 0.5, 0.02, p=1.4)
    manchas = L.ruido(s(), 0.1, 0.005, p=1.0)
    arena = L.ruido(s(), 0.002, 0.0, p=0.2)
    brillo = L.ruido(s(), 0.2, 0.01, p=1.1)
    arido = L.puntos(s(), 0.004, 0.45, 0.0003, 0.0011)
    poros = L.puntos(s(), 0.02, 0.25, 0.0003, 0.0009)
    c = por_px(col("#545351"), 1 + 0.06 * nubes + 0.03 * manchas + 0.02 * arena)
    tono_a = np.where(arido.azar < 0.45, 0, np.where(arido.azar < 0.8, 1, 2))
    paleta_a = np.stack([col("#8C8B86"), col("#2E2E2D"), col("#6E6A62")])
    c = mezcla(c, paleta_a[tono_a], 0.55 * arido.mascara)
    c = mezcla(c, c * 0.45, 0.9 * poros.mascara)
    c = ajustar_media(c, col("#545351"))
    rug = 0.28 + 0.04 * nubes + 0.03 * brillo + 0.5 * poros.mascara
    h = -0.0003 * poros.perfil + 0.00001 * arena + 0.00002 * arido.perfil + 0.00002 * nubes
    return dict(color=c, altura=h, rugosidad=np.clip(rug, 0.18, 0.85))


# ------------------------------------------------------------------------ cuadros (0,50 × 0,70 m, no se repiten)
OCRE, CARBON = col("#B8862B"), col("#2B2D2F")          # paleta de docs/deco-industrial.md
LADRILLO_A, AVENA, CONCRETO_A = col("#8C4A36"), col("#D8CFC0"), col("#B3AFA8")


def papel(L, s):
    """Papel de algodón cálido: grano fino, leve ondulación de tono y fibras sueltas."""
    r = s.rng
    g1 = L.ruido(s(), 0.0015, 0.0003, p=0.6)
    g2 = L.ruido(s(), 0.03, 0.002, p=1.2)
    fib = L.vacio()
    for _ in range(260):
        x0, y0 = r.uniform(0, L.w), r.uniform(0, L.h)
        a, lg = r.uniform(0, math.pi), r.uniform(0.002, 0.007)
        L.segmento(fib, (x0, y0), (x0 + lg * math.cos(a), y0 + lg * math.sin(a)), 0.00008, r.uniform(0.3, 1))
    c = por_px(col("#F1EDE5"), (1 + 0.014 * g1 + 0.005 * g2) * (1 - 0.05 * fib))
    return c, g1


def tinta(L, s, c, mascara, color, grano, veladura=0.025):
    """Aplica una tinta plana (serigrafía) con leve moteado y el grano del papel."""
    mot = L.ruido(s(), 0.03, 0.002, p=1.2)
    ct = por_px(color, 1 + veladura * mot + 0.012 * grano)
    return mezcla(c, ct, np.clip(mascara, 0, 1) * (0.96 + 0.03 * grano))


def disco(L, cx, cy, radio, borde):
    return ss(radio + 0.6 * L.px, radio - 0.6 * L.px, np.hypot(L.X - cx, L.Y - cy) + borde)


def rect(L, x0, x1, y0, y1, borde, suave=None):
    e = suave if suave else 0.6 * L.px
    sd = sd_rect(L.X - (x0 + x1) / 2, L.Y - (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, 0.0) - borde
    return ss(-e, e, sd)


def arte_1(L, s):
    """Círculos y franjas en ocre y carbón (geometría de la escuela Bauhaus) sobre papel crema."""
    c, grano = papel(L, s)
    borde = 0.00012 * L.ruido(s(), 0.002, 0.0003, p=0.6)
    c = tinta(L, s, c, disco(L, 0.235, 0.43, 0.135, borde), OCRE, grano)
    c = tinta(L, s, c, rect(L, 0.07, 0.43, 0.255, 0.305, borde), CARBON, grano)
    medio = disco(L, 0.325, 0.255, 0.075, borde) * ss(0.255 + 0.6 * L.py, 0.255 - 0.6 * L.py, L.Y)
    c = tinta(L, s, c, medio, CARBON, grano)
    c = tinta(L, s, c, disco(L, 0.375, 0.585, 0.02, borde), CARBON, grano)
    c = tinta(L, s, c, rect(L, 0.07, 0.43, 0.1195, 0.1205, 0.0), CARBON, grano)
    c = tinta(L, s, c, rect(L, 0.105, 0.108, 0.13, 0.25, borde * 0.5), OCRE, grano)
    return dict(color=c)


def arte_2(L, s):
    """Campos de color superpuestos de bordes difusos (ladrillo, avena y carbón sobre gris cálido)."""
    c, grano = papel(L, s)
    pincel = L.ruido(s(), 0.06, 0.004, p=1.2, estira=8)
    borde = 0.0015 * L.ruido(s(), 0.04, 0.008, p=1.2) + 0.0003 * L.ruido(s(), 0.006, 0.0015, p=0.8)
    fondo = rect(L, 0.05, 0.45, 0.075, 0.655, 0.0)
    c = tinta(L, s, c, fondo, por_px(col("#B5ADA1"), 1 + 0.025 * pincel), grano, 0.02)
    c = tinta(L, s, c, rect(L, 0.08, 0.42, 0.395, 0.62, borde, suave=0.005) * (0.95 + 0.03 * pincel),
              por_px(LADRILLO_A, 1 + 0.035 * pincel), grano, 0.04)
    c = tinta(L, s, c, rect(L, 0.08, 0.42, 0.363, 0.374, 0.5 * borde, suave=0.002) * 0.9, AVENA, grano, 0.02)
    c = tinta(L, s, c, rect(L, 0.08, 0.42, 0.105, 0.345, borde, suave=0.005) * (0.96 + 0.03 * pincel),
              por_px(CARBON, 1 + 0.045 * pincel), grano, 0.04)
    return dict(color=c)


def arte_3(L, s):
    """Líneas finas: curvas de nivel de una colina imaginaria en carbón, una de ellas en ocre."""
    c, grano = papel(L, s)
    campo = (np.exp(-((L.X - 0.3) ** 2 + (L.Y - 0.42) ** 2) / (2 * 0.1 ** 2))
             + 0.55 * np.exp(-((L.X - 0.16) ** 2 + (L.Y - 0.24) ** 2) / (2 * 0.07 ** 2))
             + 0.10 * L.ruido(s(), 0.12, 0.02, p=1.8))
    K = 20
    f = campo * K
    gy, gx = np.gradient(f)
    g = np.hypot(gx, gy) + 1e-6
    d_px = np.abs(np.mod(f + 0.5, 1.0) - 0.5) / g
    nivel = np.floor(f + 0.5)
    area = rect(L, 0.075, 0.425, 0.1, 0.63, 0.0)
    lineas = ss(1.6, 0.8, d_px) * area                 # ≈ 2,4 px = 1,2 mm de trazo
    ocre = (nivel == 9) & (d_px < 2.6)
    c = tinta(L, s, c, np.where(ocre, 0, lineas), CARBON, grano)
    c = tinta(L, s, c, np.where(ocre, ss(2.4, 1.4, d_px) * area, 0), OCRE, grano)
    return dict(color=c)


# ======================================================================= catálogo
# id -> nombre, dimensiones reales (m) de una repetición, semilla, generador, descripción
CATALOGO = {
    "microcemento": ("Microcemento gris cálido", (2.0, 2.0), 101, tex_microcemento,
                     "Microcemento gris cálido claro (#9C9890): pasadas de llana en arco con canto marcado, nubes "
                     "suaves, grano, poros finos y brillo satinado desparejo."),
    "piso_roble": ("Piso de tablas de roble ahumado", (2.4, 2.4), 107, tex_piso_roble,
                   "Tablas de roble ahumado de 0,20 × 1,20 m trabadas al azar (12 hileras × 2): veta de tronco con "
                   "catedrales y rayado, poros, radios medulares, nudos ocasionales, color por tabla, microbisel y "
                   "juntas finas."),
    "roble_ahumado": ("Roble ahumado (chapa continua)", (1.2, 1.2), 108, tex_roble_ahumado,
                      "Veta continua de roble ahumado (#6B4F3A) para muebles, sin juntas: anillos deformados en "
                      "catedrales, poros alargados y radios medulares; la veta corre a lo largo de U."),
    "cuero": ("Cuero coñac", (0.4, 0.4), 110, tex_cuero,
              "Cuero coñac (#8A4B2A) de flor granulada de 1,5 a 3,5 mm, arrugas suaves, poros y desgaste más claro "
              "en las partes altas."),
    "acero_pavonado": ("Acero pavonado", (0.6, 0.6), 109, tex_acero_pavonado,
                       "Acero negro azulado (#232426) con manchas pardas del pavonado, cepillado a lo largo de U y "
                       "algunas rayas claras."),
    "acero_cepillado": ("Acero inoxidable cepillado (electrodomésticos)", (0.3, 0.3), 119, tex_acero_cepillado,
                        "Acero inoxidable gris frío claro (#C3C7CB) con vetas rectas muy finas y parejas a lo largo "
                        "de V, contraste bajo y rugosidad de 0,25 a 0,35 que sigue a las vetas."),
    "ladrillo": ("Ladrillo a la vista", (1.25, 1.28), 103, tex_ladrillo,
                 "Ladrillo #8C4A36 con variación por pieza, aparejo soga de 24 × 7 cm y junta hundida de 1 cm "
                 "(5 ladrillos × 16 hiladas: por eso 1,25 × 1,28 m), cantos gastados, motas y restos de mortero."),
    "azulejo_subway": ("Azulejo subway blanco biselado", (0.6, 0.6), 104, tex_azulejo_subway,
                       "Azulejo subway blanco brillante biselado de 7,5 × 15 cm trabado a la mitad, junta gris "
                       "oscura de 2 mm, esmalte con leves ondulaciones por pieza."),
    "baldosa_hex": ("Baldosa hexagonal carbón", (0.6, 0.6928203), 105, tex_baldosa_hex,
                    "Hexágonos de 10 cm entre caras en gris carbón con variación por pieza y junta gris clara de "
                    "2 mm (6 × 8 hileras: 0,60 × 0,6928 m para que la red hexagonal se repita exacta)."),
    "concreto_encofrado": ("Concreto visto de encofrado", (2.4, 2.4), 102, tex_concreto_encofrado,
                           "Concreto visto (#B3AFA8) con marcas de tablas de 0,15 m, veta de madera impresa, rebarba "
                           "en las juntas, nidos y poros."),
    "losa_hormigon": ("Baldosa de hormigón 60 × 60", (1.2, 1.2), 106, tex_losa_hormigon,
                      "Baldosas de hormigón de 60 × 60 cm (2 × 2) con juntas marcadas, áridos finos, barrido suave "
                      "y suciedad en las juntas, para el balcón."),
    "lana": ("Lana bouclé avena", (0.25, 0.25), 111, tex_lana,
             "Tejido bouclé grueso color avena (#D8CFC0): rulos de hilo de 3 a 6 mm sobre un tejido de base."),
    "yute": ("Yute natural", (0.5, 0.5), 112, tex_yute,
             "Tejido de canasta 2 × 2 de yute natural con hilos de 7,8 mm, torsión, fibras y hebras sueltas "
             "(alfombras)."),
    "concreto_oscuro": ("Concreto pulido oscuro", (1.0, 1.0), 113, tex_concreto_oscuro,
                        "Concreto pulido gris oscuro (#545351) para cubiertas: nubes, áridos finos, poros y brillo "
                        "desparejo."),
    "arte_1": ("Cuadro: círculos y franjas", (0.5, 0.7), 201, arte_1,
               "Lámina abstracta: círculo ocre, franja y medio círculo carbón, líneas finas; papel crema con grano."),
    "arte_2": ("Cuadro: campos de color", (0.5, 0.7), 202, arte_2,
               "Lámina abstracta de campos de color de bordes difusos: ladrillo, avena y carbón sobre gris cálido."),
    "arte_3": ("Cuadro: líneas finas", (0.5, 0.7), 203, arte_3,
               "Lámina abstracta de líneas finas: curvas de nivel en carbón con una en ocre, sobre papel crema."),
}
PX_CUADRO = (1024, 1434)                              # 0,50 × 0,70 m a 2048 px/m


# ======================================================================= archivos
def guardar_jpg(arr, ruta, calidad=CALIDAD_JPG):
    """Guarda (ny, nx) o (ny, nx, 3) en 0-1 como JPEG sin gestión de color y lo relee para verificarlo.
    Devuelve el error medio absoluto de la relectura."""
    ny, nx = arr.shape[:2]
    rgba = np.ones((ny, nx, 4), np.float32)
    rgba[..., :3] = np.clip(arr if arr.ndim == 3 else arr[..., None], 0, 1)
    im = bpy.data.images.new("_textura", nx, ny, alpha=False, float_buffer=False)
    im.pixels.foreach_set(rgba[::-1].ravel())         # Blender: fila 0 = abajo
    im.filepath_raw = ruta
    im.file_format = "JPEG"
    im.save(filepath=ruta, quality=calidad)
    bpy.data.images.remove(im)
    with open(ruta, "rb") as fh:
        assert fh.read(3) == b"\xff\xd8\xff", f"{ruta} no quedó en JPEG"
    err = float(np.abs(leer_imagen(ruta) - rgba[..., :3]).mean())
    assert err < 0.06, f"{ruta}: la relectura difiere {err:.4f}"   # > 6 %: color o orientación mal
    return err


def leer_imagen(ruta):
    """Imagen de disco -> (ny, nx, 3) en 0-1, fila 0 arriba, valores tal cual están en el archivo."""
    im = bpy.data.images.load(ruta, check_existing=False)
    im.colorspace_settings.name = "Non-Color"
    nx, ny = im.size
    a = np.empty(nx * ny * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(ny, nx, 4)[::-1, :, :3].copy()


def guardar_png(arr, ruta):
    ny, nx = arr.shape[:2]
    rgba = np.ones((ny, nx, 4), np.float32)
    rgba[..., :3] = np.clip(arr if arr.ndim == 3 else arr[..., None], 0, 1)
    im = bpy.data.images.new("_hoja", nx, ny, alpha=False)
    im.pixels.foreach_set(rgba[::-1].ravel())
    im.filepath_raw = ruta
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def costura(a):
    """Salto medio a través del borde de repetición (última fila → primera, última columna → primera) dividido por
    el salto medio de las tres filas y columnas vecinas a cada lado (≈ 1: sin costura; una costura da ≫ 1)."""
    a = a.mean(-1) if a.ndim == 3 else a
    borde = np.abs(a[0] - a[-1]).mean() + np.abs(a[:, 0] - a[:, -1]).mean()
    dv, dh = np.abs(np.diff(a, axis=0)).mean(1), np.abs(np.diff(a, axis=1)).mean(0)
    vecinas = np.concatenate((dv[:3], dv[-3:])).mean() + np.concatenate((dh[:3], dh[-3:])).mean()
    return float(borde / max(vecinas, 1e-9))


def archivos(tid):
    carpeta = os.path.join(SALIDA, tid)
    mapas = {"color": f"{tid}_diff_1k.jpg"}
    if not tid.startswith("arte_"):
        mapas["normal"] = f"{tid}_nor_gl_1k.jpg"
        mapas["rugosidad"] = f"{tid}_rough_1k.jpg"
    return carpeta, mapas


def generar(tid, depurar=None):
    nombre, dims, semilla, fn, desc = CATALOGO[tid]
    t0 = time.time()
    nx, ny = PX_CUADRO if tid.startswith("arte_") else (N, N)
    L = Lienzo(dims[0], dims[1], nx, ny)
    res = fn(L, Semillas(semilla))
    t_calc = time.time() - t0
    carpeta, mapas = archivos(tid)
    os.makedirs(carpeta, exist_ok=True)
    stats = {"px": [nx, ny], "dimensiones_m": list(dims), "mm_por_px": round(1000 * L.px, 3)}
    color = np.clip(res["color"], 0, 1)
    stats["error_jpg"] = {"color": round(guardar_jpg(color, os.path.join(carpeta, mapas["color"])), 4)}
    stats["color_medio_srgb"] = [int(round(v * 255)) for v in color.reshape(-1, 3).mean(0)]
    salida = {"color": color}
    if "normal" in mapas:
        nor = L.normal(L.desenfocar(res["altura"].astype(np.float32), 0.5 * max(L.px, L.py)))
        rug = np.clip(res["rugosidad"], 0, 1).astype(np.float32)
        stats["error_jpg"]["normal"] = round(guardar_jpg(nor, os.path.join(carpeta, mapas["normal"])), 4)
        stats["error_jpg"]["rugosidad"] = round(guardar_jpg(rug, os.path.join(carpeta, mapas["rugosidad"])), 4)
        h = res["altura"]
        stats["altura_mm"] = [round(1000 * float(h.min()), 3), round(1000 * float(h.max()), 3)]
        stats["rugosidad"] = [round(float(rug.min()), 3), round(float(rug.mean()), 3), round(float(rug.max()), 3)]
        stats["normal_z_min"] = round(float(nor[..., 2].min() * 2 - 1), 3)
        stats["costura"] = {"color": round(costura(color), 3), "normal": round(costura(nor), 3),
                            "rugosidad": round(costura(rug), 3)}
        salida.update(normal=nor, rugosidad=rug)
    stats["segundos"] = round(time.time() - t0, 2)
    stats["segundos_calculo"] = round(t_calc, 2)
    if depurar:
        depurar_textura(tid, salida, depurar)
    entrada = {"nombre": nombre, "dimensiones_m": [round(dims[0], 7), round(dims[1], 7)], "mapas": mapas,
               "descripcion": desc, "semilla": semilla, "licencia": LICENCIA, "resolucion_px": [nx, ny]}
    return entrada, stats


def escribir_manifiesto(entradas):
    ruta = os.path.join(SALIDA, "manifest.json")
    datos = {}
    if os.path.exists(ruta):
        with open(ruta) as fh:
            datos = json.load(fh)
    tex = datos.get("texturas", {})
    tex.update(entradas)
    orden = [k for k in CATALOGO if k in tex] + [k for k in tex if k not in CATALOGO]
    datos = {"licencia_general": LICENCIA_GENERAL, "generador": "build/deco_texturas.py",
             "texturas": {k: tex[k] for k in orden}}
    tmp = ruta + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(datos, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, ruta)


# ======================================================================= revisión
FUENTE = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 10001 01010 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    "_": "00000 00000 00000 00000 00000 00000 11111", ".": "00000 00000 00000 00000 00000 01100 01100",
    ",": "00000 00000 00000 00000 01100 00100 01000", "-": "00000 00000 00000 11111 00000 00000 00000",
    " ": "00000 00000 00000 00000 00000 00000 00000", ":": "00000 01100 01100 00000 01100 01100 00000",
    "/": "00001 00001 00010 00100 01000 10000 10000", "+": "00000 00100 00100 11111 00100 00100 00000",
    "(": "00010 00100 01000 01000 01000 00100 00010", ")": "01000 00100 00010 00010 00010 00100 01000",
    "?": "01110 10001 00001 00010 00100 00000 00100",
}


def texto(img, x, y, cadena, escala=3, color=(0.08, 0.08, 0.08)):
    """Escribe con una fuente de mapa de bits de 5 × 7 (mayúsculas) en img (fila 0 arriba)."""
    for ch in cadena.upper():
        filas = FUENTE.get(ch, FUENTE["?"]).split()
        for fy, bits in enumerate(filas):
            for fx, bit in enumerate(bits):
                if bit == "1":
                    y0, x0 = y + fy * escala, x + fx * escala
                    img[y0:y0 + escala, x0:x0 + escala] = color
        x += 6 * escala


def _pesos(viejo, nuevo):
    W = np.zeros((nuevo, viejo), np.float32)
    e = viejo / nuevo
    for i in range(nuevo):
        a, b = i * e, (i + 1) * e
        for j in range(int(math.floor(a)), min(int(math.ceil(b)), viejo)):
            W[i, j] = min(b, j + 1) - max(a, j)
    return W / W.sum(1, keepdims=True)


def reducir(img, ancho, alto):
    """Reducción por promedio de área."""
    Wy, Wx = _pesos(img.shape[0], alto), _pesos(img.shape[1], ancho)
    return np.stack([Wy @ img[..., k] @ Wx.T for k in range(img.shape[2])], -1)


def depurar_textura(tid, mapas, carpeta):
    """Recortes a resolución completa alrededor de la esquina de un mosaico 2 × 2 (costuras) y vista general."""
    os.makedirs(carpeta, exist_ok=True)
    partes = []
    for k in ("color", "normal", "rugosidad"):
        if k not in mapas:
            continue
        a = mapas[k] if mapas[k].ndim == 3 else np.repeat(mapas[k][..., None], 3, -1)
        ny, nx = a.shape[:2]
        mos = np.tile(a, (2, 2, 1))
        partes.append(mos[ny - 256:ny + 256, nx - 256:nx + 256])
    guardar_png(np.concatenate(partes, 1), os.path.join(carpeta, f"{tid}_esquina.png"))
    guardar_png(mapas["color"], os.path.join(carpeta, f"{tid}_color.png"))


def hoja_texturas():
    """review/deco/texturas.png: cada textura en mosaico 2 × 2 (costuras), con su normal y su rugosidad."""
    manif = os.path.join(SALIDA, "manifest.json")
    with open(manif) as fh:
        tex = json.load(fh)["texturas"]
    ids = [t for t in CATALOGO if t in tex]
    M, T, E = 384, 192, 34                              # mosaico, miniatura, franja del nombre
    CW, CH = M + T + 16, M + E + 12
    cols = 4
    filas = math.ceil(len(ids) / cols)
    hoja = np.full((filas * CH + 10, cols * CW + 10, 3), 0.93, np.float32)
    for n, tid in enumerate(ids):
        oy, ox = 10 + (n // cols) * CH, 10 + (n % cols) * CW
        carpeta = os.path.join(SALIDA, tid)
        mp = tex[tid]["mapas"]
        c = leer_imagen(os.path.join(carpeta, mp["color"]))
        w, h = tex[tid]["dimensiones_m"]
        texto(hoja, ox, oy + 4, tid, 3)
        texto(hoja, ox + 18 * len(tid) + 10, oy + 11, f"{w:g} x {h:g} m", 2, (0.35, 0.35, 0.35))
        oy += E
        if tid.startswith("arte_"):
            ancho = int(round(M * c.shape[1] / c.shape[0]))
            hoja[oy:oy + M, ox:ox + ancho] = reducir(c, ancho, M)
            continue
        hoja[oy:oy + M, ox:ox + M] = np.tile(reducir(c, M // 2, M // 2), (2, 2, 1))
        for k, (clave, dy) in enumerate((("normal", 0), ("rugosidad", T))):
            a = leer_imagen(os.path.join(carpeta, mp[clave]))
            hoja[oy + dy:oy + dy + T, ox + M + 8:ox + M + 8 + T] = reducir(a, T, T)
    ruta = os.path.join(REVISION, "texturas.png")
    guardar_png(hoja, ruta)
    return ruta


def _escena_limpia():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def prueba_normal():
    """Convención del mapa normal: un bulto gaussiano pasa por el mismo camino que las texturas (Lienzo.normal,
    guardar_jpg) y se comprueba (1) leyendo el archivo en el orden de Blender y (2) en un render de Cycles con el nodo
    Normal Map, con luz rasante desde +V y desde +U: el lado del bulto que mira a la luz debe verse más claro."""
    carpeta = os.path.join(REVISION, "prueba_normal")
    os.makedirs(carpeta, exist_ok=True)
    L = Lienzo(0.1, 0.1, 256, 256)
    h = 0.006 * np.exp(-((L.X - 0.05) ** 2 + (L.Y - 0.05) ** 2) / (2 * 0.012 ** 2))
    ruta = os.path.join(carpeta, "bulto_nor_gl.jpg")
    guardar_jpg(L.normal(h), ruta)
    im = bpy.data.images.load(ruta, check_existing=False)
    im.colorspace_settings.name = "Non-Color"
    a = np.empty(256 * 256 * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    a = a.reshape(256, 256, 4)                         # orden de Blender: fila 0 = abajo (v = 0)
    c, d = 128, 24
    lectura = {"verde_arriba": round(float(a[c + d, c, 1]), 3), "verde_abajo": round(float(a[c - d, c, 1]), 3),
               "rojo_derecha": round(float(a[c, c + d, 0]), 3), "rojo_izquierda": round(float(a[c, c - d, 0]), 3)}
    ok_lectura = (lectura["verde_arriba"] > 0.6 > 0.4 > lectura["verde_abajo"]
                  and lectura["rojo_derecha"] > 0.6 > 0.4 > lectura["rojo_izquierda"])
    # render
    sc = _escena_limpia()
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    plano = bpy.context.active_object
    me = plano.data
    uv = me.uv_layers.active.data
    esq = max(range(len(me.loops)), key=lambda i: me.vertices[me.loops[i].vertex_index].co.x
              + me.vertices[me.loops[i].vertex_index].co.y)
    assert tuple(round(v, 3) for v in uv[esq].uv) == (1.0, 1.0), "UV del plano: se esperaba u → +X, v → +Y"
    mat = bpy.data.materials.new("_prueba_normal")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1)
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Specular"].default_value = 0.0
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = bpy.data.images.load(ruta)
    tx.image.colorspace_settings.name = "Non-Color"
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tx.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    me.materials.append(mat)
    cd = bpy.data.cameras.new("_cam")
    cd.type = "ORTHO"
    cd.ortho_scale = 1.0
    cam = bpy.data.objects.new("_cam", cd)
    cam.location = (0, 0, 2)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sd = bpy.data.lights.new("_sol", "SUN")
    sd.energy = 4.0
    sd.angle = 0.0
    sol = bpy.data.objects.new("_sol", sd)
    sc.collection.objects.link(sol)
    w = bpy.data.worlds.new("_mundo")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    sc.world = w
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = 128
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    vistas, render = [], {}
    centro, lado_mas, lado_menos = slice(52, 76), slice(72, 100), slice(28, 56)   # píxeles del render (fila 0 = v 0)
    for nombre, rot, zona_luz, zona_sombra in (
            ("luz_desde_+V", (math.radians(-65), 0, 0), (lado_mas, centro), (lado_menos, centro)),
            ("luz_desde_+U", (0, math.radians(65), 0), (centro, lado_mas), (centro, lado_menos))):
        sol.rotation_euler = rot
        p = os.path.join(carpeta, f"_{nombre}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        img = leer_imagen(p)[::-1]                     # de vuelta al orden de Blender (fila 0 = v 0)
        os.remove(p)
        lum = img.mean(-1)
        render[nombre] = {"lado_luz": round(float(lum[zona_luz].mean()), 3),
                          "lado_opuesto": round(float(lum[zona_sombra].mean()), 3)}
        vistas.append(img[::-1])
    ok_render = all(v["lado_luz"] > v["lado_opuesto"] + 0.05 for v in render.values())
    mapa = reducir(leer_imagen(ruta), 128, 128)
    hoja = np.full((128 + 40, 3 * 128 + 40, 3), 0.93, np.float32)
    for k, a in enumerate([mapa] + vistas):
        hoja[30:158, 10 + k * 138:138 + k * 138] = a
    texto(hoja, 10, 8, "normal gl", 2)
    texto(hoja, 148, 8, "luz +v", 2)
    texto(hoja, 286, 8, "luz +u", 2)
    guardar_png(hoja, os.path.join(REVISION, "prueba_normal.png"))
    res = {"lectura_archivo": lectura, "render_cycles": render, "ok": bool(ok_lectura and ok_render),
           "metodo": "bulto gaussiano de 6 mm → Lienzo.normal → guardar_jpg; lectura en orden de Blender y render "
                     "Cycles (plano con UV u→+X, v→+Y, nodo Normal Map tangente, sol rasante a 25°)"}
    with open(os.path.join(REVISION, "prueba_normal.json"), "w") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    assert res["ok"], f"convención del normal: {res}"
    return res


def hoja_materiales():
    """review/deco/materiales.png: cubos redondeados (y los cuadros en un panel) en Eevee con los materiales de
    build/deco_paleta.py que usan estas texturas, uno por render (480 × 360)."""
    import bmesh
    import deco_base as B
    import deco_paleta as PAL
    import depto_geom as G
    sc = _escena_limpia()
    lista, vistos = [], set()
    for nombre, (tid, op) in PAL.TEXTURA_MAT.items():
        if tid not in CATALOGO:
            continue
        clave = (tid, op.get("color"), op.get("escala_m"), None if op.get("color") else G.MATERIALES[nombre][0])
        if clave not in vistos:
            vistos.add(clave)
            lista.append((nombre, tid))
    G.MATERIALES.setdefault("_piso_muestra", ((0.62, 0.62, 0.60), 0.8, 0.0, 1.0))
    col_ = bpy.data.collections.new("_muestras")
    sc.collection.children.link(col_)
    bm = bmesh.new()
    B.caja(bm, -4, 4, -4, 4, -0.02, 0.0)
    B.objeto(col_, "_piso", bm, "_piso_muestra")
    bm = bmesh.new()
    B.caja_redondeada(bm, -0.3, 0.3, -0.3, 0.3, 0.0, 0.6, 0.025, 3)
    cubo = B.objeto(col_, "_cubo", bm, lista[0][0], suave=True, angulo_suave=40)
    bm = bmesh.new()
    capa = bm.loops.layers.uv.verify()
    vs = [bm.verts.new(p) for p in ((-0.25, 0, 0.05), (0.25, 0, 0.05), (0.25, 0, 0.75), (-0.25, 0, 0.75))]
    f = bm.faces.new(vs)
    for lp, uvv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp[capa].uv = uvv
    panel = B.objeto(col_, "_panel", bm, "Depto_Mat_Arte1", uv="propia", recalc=False)
    sd = bpy.data.lights.new("_sol", "SUN")
    sd.energy = 3.0
    sd.angle = math.radians(3)
    sol = bpy.data.objects.new("_sol", sd)
    sol.rotation_euler = (math.radians(50), 0, math.radians(-35))
    col_.objects.link(sol)
    ad = bpy.data.lights.new("_area", "AREA")
    ad.energy = 250
    ad.size = 2.0
    area = bpy.data.objects.new("_area", ad)
    area.location = (-2.0, -2.2, 2.2)
    area.rotation_euler = (area.location * -1).to_track_quat("-Z", "Y").to_euler()
    col_.objects.link(area)
    w = bpy.data.worlds.new("_mundo")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.57, 0.6, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    sc.world = w
    from mathutils import Vector

    def camara(nombre, pos, mira, lente):
        cd = bpy.data.cameras.new(nombre)
        cd.lens = lente
        cam = bpy.data.objects.new(nombre, cd)
        cam.location = pos
        cam.rotation_euler = (Vector(mira) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(cam)
        return cam
    cam_cubo = camara("_cam_cubo", (-1.05, -1.35, 1.05), (0, 0, 0.27), 50)
    cam_panel = camara("_cam_panel", (-0.35, -1.75, 0.55), (0, 0, 0.4), 50)
    sc.render.engine = "BLENDER_EEVEE"
    ee = sc.eevee
    ee.taa_render_samples = 24
    ee.use_gtao = True
    ee.use_soft_shadows = True
    ee.use_ssr = True
    ee.shadow_cube_size = "1024"
    ee.shadow_cascade_size = "2048"
    sc.view_settings.view_transform = "Filmic"
    sc.render.resolution_x, sc.render.resolution_y = 480, 360
    sc.render.image_settings.file_format = "PNG"
    E = 30
    cols = 4
    filas = math.ceil(len(lista) / cols)
    hoja = np.full((filas * (360 + E) + 10, cols * (480 + 10) + 10, 3), 0.93, np.float32)
    hechos = []
    for n, (nombre, tid) in enumerate(lista):
        ok = PAL.aplicar(nombre)
        mat = G.material(nombre) if not ok else bpy.data.materials[nombre]
        es_panel = bool(PAL.TEXTURA_MAT[nombre][1].get("uv01"))
        obj = panel if es_panel else cubo
        obj.data.materials[0] = mat
        cubo.hide_render, panel.hide_render = es_panel, not es_panel
        sc.camera = cam_panel if es_panel else cam_cubo
        p = os.path.join(REVISION, "_material.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        img = leer_imagen(p)
        os.remove(p)
        oy, ox = 10 + (n // cols) * (360 + E), 10 + (n % cols) * 490
        texto(hoja, ox, oy + 4, nombre.replace("Depto_Mat_", "") + ("" if ok else " (sin textura)"), 3)
        texto(hoja, ox + 10 + 6 * 3 * len(nombre.replace("Depto_Mat_", "")), oy + 11, tid, 2, (0.35, 0.35, 0.35))
        hoja[oy + E - 4:oy + E - 4 + 360, ox:ox + 480] = img
        hechos.append({"material": nombre, "textura": tid, "con_textura": ok})
    ruta = os.path.join(REVISION, "materiales.png")
    guardar_png(hoja, ruta)
    return ruta, hechos


# ======================================================================= principal
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="Texturas PBR propias del Depto (docs/deco-industrial.md)")
    ap.add_argument("--solo", default="", help="ids separados por coma (sin: todas)")
    ap.add_argument("--revision", choices=("nada", "hoja", "todo"), default=None,
                    help="nada | hoja (texturas.png) | todo (+ prueba del normal y materiales.png). Por defecto: "
                         "todo sin --solo, hoja con --solo")
    ap.add_argument("--depurar", default="", help="carpeta para recortes de costura a resolución completa")
    a = ap.parse_args(argv)
    ids = [t.strip() for t in a.solo.split(",") if t.strip()] or list(CATALOGO)
    faltan = [t for t in ids if t not in CATALOGO]
    assert not faltan, f"ids desconocidos: {faltan} (hay: {', '.join(CATALOGO)})"
    revision = a.revision or ("hoja" if a.solo else "todo")
    os.makedirs(SALIDA, exist_ok=True)
    os.makedirs(REVISION, exist_ok=True)
    ruta_stats = os.path.join(REVISION, "texturas.json")
    stats = {}
    if os.path.exists(ruta_stats):
        with open(ruta_stats) as fh:
            stats = json.load(fh).get("texturas", {})
    for tid in ids:
        entrada, st = generar(tid, a.depurar or None)
        escribir_manifiesto({tid: entrada})
        stats[tid] = st
        print(f"TEXTURA_OK {tid} {st['segundos']:.1f} s costura={st.get('costura', '-')} "
              f"color={st['color_medio_srgb']}", flush=True)
    resumen = {"texturas": {k: stats[k] for k in CATALOGO if k in stats}}
    if revision in ("hoja", "todo"):
        resumen["hoja"] = os.path.relpath(hoja_texturas(), RAIZ)
        print("HOJA_TEXTURAS", resumen["hoja"], flush=True)
    if revision == "todo":
        resumen["prueba_normal"] = prueba_normal()
        print("PRUEBA_NORMAL", json.dumps(resumen["prueba_normal"]["render_cycles"]), flush=True)
        ruta, hechos = hoja_materiales()
        resumen["hoja_materiales"] = os.path.relpath(ruta, RAIZ)
        resumen["materiales"] = hechos
        print("HOJA_MATERIALES", resumen["hoja_materiales"], flush=True)
    with open(ruta_stats, "w") as fh:
        json.dump(resumen, fh, indent=2, ensure_ascii=False)
    print("TEXTURAS_DONE", len(ids), flush=True)


if __name__ == "__main__":
    main()
