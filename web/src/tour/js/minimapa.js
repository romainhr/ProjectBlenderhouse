// Plano dibujado desde depto_colisiones.json (igual que exports/depto_tour.html): u = z de glTF (izquierda
// = balcón), v = -x (arriba = dormitorio 1). Los colores se leen UNA vez de getComputedStyle (antes se leían
// en cada cuadro) y solo se redibuja cuando la posición o la mirada cambiaron.
// Los nombres de recinto van en el idioma de la página (textos.js); uno más largo que el español (p. ej. «Placards
// de la chambre principale») se achica hasta caber en ANCHO_ETIQUETA del plano, sin bajar de TAM_MIN px.
import { estadoMovil } from "./colision.js";
import { nombreRecinto } from "./textos.js";

const ANCHO_ETIQUETA = 0.42;   // fracción del ancho del plano (supuesto: así dos recintos vecinos no se pisan)
const TAM_MIN = 10;

export function prepararMinimapa(canvas, D) {
  let u0 = Infinity, u1 = -Infinity, v0 = Infinity, v1 = -Infinity;
  for (const c of D.estaticos) {
    u0 = Math.min(u0, c[2]); u1 = Math.max(u1, c[3]); v0 = Math.min(v0, -c[1]); v1 = Math.max(v1, -c[0]);
  }
  const pad = 14, W = canvas.width, H = canvas.height;
  const s = Math.min((W - 2 * pad) / (u1 - u0), (H - 2 * pad) / (v1 - v0));
  const ox = (W - s * (u1 - u0)) / 2, oy = (H - s * (v1 - v0)) / 2;
  const estilo = getComputedStyle(document.documentElement);
  const leer = (n, resp) => estilo.getPropertyValue(n).trim() || resp;
  return {
    ctx: canvas.getContext("2d"), W, H, s,
    a: (x, z) => [ox + (z - u0) * s, oy + (-x - v0) * s],
    colores: {
      papel: leer("--papel", "#F7F4EF"), tinta: leer("--tinta", "#1E1C19"),
      tintaSuave: leer("--tinta-2", "#5E5850"), acento: leer("--acento", "#A8481F"),
    },
    ultX: null, ultZ: null, ultYaw: null,
    etiquetas: null,                 // [{ texto, x, y, font }] de los recintos, medidas la primera vez que se dibujan
  };
}

// Texto, posición y tipografía de cada recinto: el tamaño base es W/26 y baja hasta que el texto quepa.
function etiquetasRecintos(M, D) {
  const { ctx, W, a } = M;
  const base = Math.round(W / 26), maximo = W * ANCHO_ETIQUETA;
  return Object.entries(D.recintos || {}).map(([k, p]) => {
    const texto = nombreRecinto(k, D.recintos_etiquetas);
    let tam = base, font;
    do {
      font = `500 ${tam}px "Public Sans", sans-serif`;
      ctx.font = font;
    } while (ctx.measureText(texto).width > maximo && --tam >= TAM_MIN);
    const [x, y] = a(p[0], p[1]);
    return { texto, x, y, font };
  });
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
    ctx.fillText(e.texto, e.x, e.y);
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
