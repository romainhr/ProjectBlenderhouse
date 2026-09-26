// Plano dibujado desde depto_colisiones.json (igual que exports/depto_tour.html): u = z de glTF (izquierda
// = balcón), v = -x (arriba = dormitorio 1). Los colores se leen UNA vez de getComputedStyle (antes se leían
// en cada cuadro) y solo se redibuja cuando la posición o la mirada cambiaron.
// Los nombres de recinto van en el idioma de la página (textos.js) y los acomoda ubicarEtiquetas: cada uno en una
// línea del tamaño más grande que quepa en ANCHO_ETIQUETA; si ni con TAM_MIN cabe (p. ej. «Placards de la chambre
// principale»), en dos líneas; y si pisa a una etiqueta ya puesta (los clósets y el baño de cada dormitorio tienen el
// centro a menos de 40 px), se corre en vertical lo mínimo para que no se toquen. Achicar la letra no bastaba: dos
// recintos vecinos se seguían pisando, también en español.
import { estadoMovil } from "./colision.js";
import { nombreRecinto } from "./textos.js";

export const ANCHO_ETIQUETA = 0.42;   // fracción del ancho del plano que puede ocupar una línea
// px del lienzo (380 de ancho): el panel lo muestra en unos 278 px de pantalla, así que 12 px se ven de unos 9 px
export const TAM_MIN = 12;
const INTERLINEA = 1.15;
export const SEPARACION_ETIQUETAS = 3;       // px libres entre dos etiquetas
const DESPLAZAMIENTO_MAX = 48;               // px que una etiqueta se puede alejar del centro de su recinto

/** Escala y paso de coordenadas del modelo (x, z) a px de un lienzo de W × H, con el plano centrado y un margen. */
export function transformacionPlano(D, W, H) {
  let u0 = Infinity, u1 = -Infinity, v0 = Infinity, v1 = -Infinity;
  for (const c of D.estaticos) {
    u0 = Math.min(u0, c[2]); u1 = Math.max(u1, c[3]); v0 = Math.min(v0, -c[1]); v1 = Math.max(v1, -c[0]);
  }
  const pad = 14;
  const s = Math.min((W - 2 * pad) / (u1 - u0), (H - 2 * pad) / (v1 - v0));
  const ox = (W - s * (u1 - u0)) / 2, oy = (H - s * (v1 - v0)) / 2;
  return { s, a: (x, z) => [ox + (z - u0) * s, oy + (-x - v0) * s] };
}

export function prepararMinimapa(canvas, D) {
  const W = canvas.width, H = canvas.height;
  const { s, a } = transformacionPlano(D, W, H);
  const estilo = getComputedStyle(document.documentElement);
  const leer = (n, resp) => estilo.getPropertyValue(n).trim() || resp;
  return {
    ctx: canvas.getContext("2d"), W, H, s, a,
    colores: {
      papel: leer("--papel", "#F7F4EF"), tinta: leer("--tinta", "#1E1C19"),
      tintaSuave: leer("--tinta-2", "#5E5850"), acento: leer("--acento", "#A8481F"),
    },
    ultX: null, ultZ: null, ultYaw: null,
    etiquetas: null,                 // [{ lineas, x, y, tam, font }] de los recintos (etiquetasRecintos)
  };
}

/** Caja de `ancho` × `alto` px centrada en (x, y); dos cajas se pisan si quedan a menos de `sep` px. */
const caja = (x, y, ancho, alto) => ({ x0: x - ancho / 2, x1: x + ancho / 2, y0: y - alto / 2, y1: y + alto / 2 });
const sePisan = (p, q, sep) => p.x0 < q.x1 + sep && q.x0 < p.x1 + sep && p.y0 < q.y1 + sep && q.y0 < p.y1 + sep;

/** Líneas y tamaño de una etiqueta: una línea del tamaño más grande (de `base` a `min`) que quepa en `ancho`; si no,
 *  dos líneas con el corte entre palabras más parejo; si tampoco, una línea de `min` (no cabe de ninguna forma). */
function forma(texto, medir, base, min, ancho) {
  for (let tam = base; tam >= min; tam--) if (medir(texto, tam) <= ancho) return { lineas: [texto], tam };
  const palabras = texto.split(" ");
  for (let tam = base; tam >= min; tam--) {
    let mejor = null;
    for (let i = 1; i < palabras.length; i++) {
      const lineas = [palabras.slice(0, i).join(" "), palabras.slice(i).join(" ")];
      const w = Math.max(...lineas.map((l) => medir(l, tam)));
      if (w <= ancho && (!mejor || w < mejor.w)) mejor = { lineas, w };
    }
    if (mejor) return { lineas: mejor.lineas, tam };
  }
  return { lineas: [texto], tam: min };
}

/** Acomoda las etiquetas [{ texto, x, y }] (centro de cada recinto, en px del lienzo W × H) sin que se pisen.
 *  `medir(texto, tam)`: ancho en px con la letra de `tam` px. En orden, cada una queda en su centro o, si pisa a una
 *  ya puesta, corrida en vertical lo mínimo (hasta DESPLAZAMIENTO_MAX), sin salirse del lienzo.
 *  Devuelve [{ texto, lineas, tam, x, y, caja }] (y: centro del bloque de líneas). Se prueba en Node. */
export function ubicarEtiquetas(etiquetas, medir, { W, H, base = Math.round(W / 26), min = TAM_MIN,
  ancho = W * ANCHO_ETIQUETA, sep = SEPARACION_ETIQUETAS } = {}) {
  const puestas = [];
  return etiquetas.map(({ texto, x, y }) => {
    const f = forma(texto, medir, base, min, ancho);
    const w = Math.max(...f.lineas.map((l) => medir(l, f.tam))), h = f.lineas.length * f.tam * INTERLINEA;
    const cx = Math.min(Math.max(x, w / 2 + 2), W - w / 2 - 2);          // entera dentro del lienzo
    const dentro = (cy) => cy - h / 2 >= 2 && cy + h / 2 <= H - 2;
    let cy = y;
    for (let d = 0; d <= DESPLAZAMIENTO_MAX; d++) {
      const libre = [y + d, y - d].find((c) => dentro(c) && !puestas.some((p) => sePisan(caja(cx, c, w, h), p, sep)));
      if (libre !== undefined) { cy = libre; break; }
    }
    const e = { texto, lineas: f.lineas, tam: f.tam, x: cx, y: cy, caja: caja(cx, cy, w, h) };
    puestas.push(e.caja);
    return e;
  });
}

// Etiquetas de los recintos con la tipografía del plano, medidas la primera vez que se dibujan.
function etiquetasRecintos(M, D) {
  const { ctx, W, H, a } = M;
  const fuente = (tam) => `500 ${tam}px "Public Sans", sans-serif`;
  const medir = (texto, tam) => { ctx.font = fuente(tam); return ctx.measureText(texto).width; };
  const lista = Object.entries(D.recintos || {}).map(([k, p]) => {
    const [x, y] = a(p[0], p[1]);
    return { texto: nombreRecinto(k, D.recintos_etiquetas), x, y };
  });
  return ubicarEtiquetas(lista, medir, { W, H }).map((e) => ({ ...e, font: fuente(e.tam) }));
}

export function dibujarMinimapa(M, D, moviles, yo, forzar) {
  const movio = M.ultX === null || Math.hypot(yo.x - M.ultX, yo.z - M.ultZ) > 0.03
    || Math.abs(yo.yaw - (M.ultYaw ?? yo.yaw)) > 0.03;
  if (!forzar && !movio) return;
  M.ultX = yo.x; M.ultZ = yo.z; M.ultYaw = yo.yaw;
  const { ctx, W, H, a, colores } = M;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = colores.papel; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = colores.tinta;
  for (const c of D.estaticos) {
    const [x1, y1] = a(c[1], c[2]), [x2, y2] = a(c[0], c[3]);
    ctx.fillRect(Math.min(x1, x2), Math.min(y1, y2), Math.max(1, Math.abs(x2 - x1)), Math.max(1, Math.abs(y2 - y1)));
  }
  ctx.fillStyle = colores.acento;
  for (const v of moviles) {
    const st = estadoMovil(v.m, v.t), ca = Math.cos(st.ang), sa = Math.sin(st.ang);
    ctx.beginPath();
    v.m.cajas_locales.forEach((c) => {
      [[c[0], c[2]], [c[1], c[2]], [c[1], c[3]], [c[0], c[3]]].forEach(([x, z], i) => {
        const [px, py] = a(st.x + x * ca + z * sa, st.z - x * sa + z * ca);
        i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
      });
    });
    ctx.fill();
  }
  M.etiquetas ??= etiquetasRecintos(M, D);
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillStyle = colores.tintaSuave;
  for (const e of M.etiquetas) {
    ctx.font = e.font;
    e.lineas.forEach((l, i) => ctx.fillText(l, e.x, e.y + (i - (e.lineas.length - 1) / 2) * e.tam * INTERLINEA));
  }
  const [px, py] = a(yo.x, yo.z);
  const dx = -Math.sin(yo.yaw), dz = -Math.cos(yo.yaw);
  const ang = Math.atan2(-dx, dz);
  ctx.fillStyle = colores.acento; ctx.globalAlpha = 0.28;
  ctx.beginPath(); ctx.moveTo(px, py); ctx.arc(px, py, M.s * 1.3, ang - 0.6, ang + 0.6); ctx.closePath(); ctx.fill();
  ctx.globalAlpha = 1;
  ctx.beginPath(); ctx.arc(px, py, Math.max(4, M.s * (D.radio || 0.2)), 0, Math.PI * 2); ctx.fill();
}

// Recinto más cercano al punto tocado del canvas (coordenadas de cliente), o null si el toque quedó lejos
// de todos los recintos.
export function recintoTocado(M, D, canvas, clientX, clientY) {
  const r = canvas.getBoundingClientRect();
  const x = ((clientX - r.left) / r.width) * canvas.width, y = ((clientY - r.top) / r.height) * canvas.height;
  let mejor = null, dmin = Infinity;
  for (const [k, p] of Object.entries(D.recintos || {})) {
    const [px, py] = M.a(p[0], p[1]);
    const d = Math.hypot(px - x, py - y);
    if (d < dmin) { dmin = d; mejor = k; }
  }
  return mejor !== null && dmin < M.W / 6 ? mejor : null;
}
