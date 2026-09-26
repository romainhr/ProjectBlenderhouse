// Lógica de la vista de fotos (public.fotos y bucket «fotos», migración 0003). Sin DOM ni canvas: validaciones,
// firma y medidas del archivo, rutas en Storage, URL pública y orden.
import { largo } from "./util.js";

export const BUCKET = "fotos";                                  // 0003: bucket público 'fotos'
// Espacios del sitio (pedido del usuario; los mismos de las secciones de web/src/index.html).
export const ESPACIOS = Object.freeze([
  Object.freeze({ id: "living", nombre: "Living" }),
  Object.freeze({ id: "cocina", nombre: "Cocina" }),
  Object.freeze({ id: "dorm1", nombre: "Dormitorio 1" }),
  Object.freeze({ id: "dorm2", nombre: "Dormitorio 2" }),
  Object.freeze({ id: "banos", nombre: "Baños" }),
  Object.freeze({ id: "balcon", nombre: "Balcón" }),
  Object.freeze({ id: "recibidor", nombre: "Recibidor" }),
]);
export const TIPOS_ACEPTADOS = Object.freeze(["image/jpeg", "image/png", "image/webp"]);   // 0003: allowed_mime_types
export const MAX_ORIGINAL = 20 * 1024 * 1024;   // supuesto: una foto de teléfono pesa 3-12 MB; más arriesga la memoria
export const MAX_PIXELES = 50e6;                // supuesto: 50 MP (≈ 200 MB al decodificar); evita colgar el teléfono
export const MAX_SUBIDA = 5242880;              // 0003: file_size_limit = 5242880 (5 MB) del bucket
export const ANCHO_MAX = 1600;                  // pedido: máximo 1600 px de ancho (igual que ANCHOS en web/build.py)
export const CALIDAD_WEBP = 0.82;               // supuesto: calidad visual alta con ~150-400 kB a 1600 px
export const CALIDAD_JPEG = 0.85;               // supuesto: respaldo si el navegador no codifica WebP
export const LIMITE_ALT = 200;                  // 0003: alt text not null (1 a 200)
const RE_ESPACIO = /^[a-z0-9][a-z0-9_.-]{1,59}$/;   // 0003: mismo check de formato que contenido.clave
export const RE_RUTA = /^[a-z0-9][a-z0-9_.-]{1,59}\/\d{8}-[0-9a-f]{8}\.(webp|jpg|png)$/;

export function esEspacio(id) {
  return RE_ESPACIO.test(String(id)) && ESPACIOS.some((e) => e.id === id);
}

export function nombreEspacio(id) {
  return (ESPACIOS.find((e) => e.id === id) || { nombre: id }).nombre;
}

/** Revisión rápida con lo que declara el navegador (el tipo se vuelve a comprobar con la firma de los bytes). */
export function validarArchivo(archivo) {
  if (!archivo || !Number.isFinite(archivo.size) || archivo.size <= 0) return { ok: false, error: "vacio" };
  if (!TIPOS_ACEPTADOS.includes(archivo.type)) return { ok: false, error: "tipo" };
  if (archivo.size > MAX_ORIGINAL) return { ok: false, error: "tamano" };
  return { ok: true };
}

const igual = (b, i, firma) => firma.every((x, k) => b[i + k] === x);

/** Tipo real según los primeros bytes (no la extensión): JPEG FF D8 FF, PNG 89 50 4E 47…, WebP RIFF….WEBP. */
export function tipoPorFirma(b) {
  if (!b || b.length < 12) return null;
  if (igual(b, 0, [0xff, 0xd8, 0xff])) return "image/jpeg";
  if (igual(b, 0, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) return "image/png";
  if (igual(b, 0, [0x52, 0x49, 0x46, 0x46]) && igual(b, 8, [0x57, 0x45, 0x42, 0x50])) return "image/webp";
  return null;
}

const u16be = (b, i) => (b[i] << 8) | b[i + 1];
const u32be = (b, i) => ((b[i] << 24) >>> 0) + (b[i + 1] << 16) + (b[i + 2] << 8) + b[i + 3];
const u24le = (b, i) => b[i] | (b[i + 1] << 8) | (b[i + 2] << 16);
const SOF = new Set([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf]);

/**
 * Ancho y alto leídos de la cabecera, sin decodificar la imagen (para rechazar a tiempo imágenes gigantes).
 * -> { ancho, alto } o null si no se encuentran en los bytes dados.
 */
export function dimensionesPorCabecera(b) {
  const tipo = tipoPorFirma(b);
  if (tipo === "image/png") {
    if (b.length < 24 || !igual(b, 12, [0x49, 0x48, 0x44, 0x52])) return null;         // IHDR
    return { ancho: u32be(b, 16), alto: u32be(b, 20) };
  }
  if (tipo === "image/webp") {
    if (b.length < 30) return null;
    if (igual(b, 12, [0x56, 0x50, 0x38, 0x58])) {                                       // VP8X (extendido)
      return { ancho: u24le(b, 24) + 1, alto: u24le(b, 27) + 1 };
    }
    if (igual(b, 12, [0x56, 0x50, 0x38, 0x20]) && igual(b, 23, [0x9d, 0x01, 0x2a])) {   // VP8 (con pérdida)
      return { ancho: (b[26] | (b[27] << 8)) & 0x3fff, alto: (b[28] | (b[29] << 8)) & 0x3fff };
    }
    if (igual(b, 12, [0x56, 0x50, 0x38, 0x4c]) && b[20] === 0x2f) {                     // VP8L (sin pérdida)
      return {
        ancho: 1 + (((b[22] & 0x3f) << 8) | b[21]),
        alto: 1 + (((b[24] & 0x0f) << 10) | (b[23] << 2) | ((b[22] & 0xc0) >> 6)),
      };
    }
    return null;
  }
  if (tipo === "image/jpeg") {
    let i = 2;
    while (i + 9 < b.length) {
      if (b[i] !== 0xff) return null;
      const m = b[i + 1];
      if (m === 0xff) { i++; continue; }                                                // relleno
      if (m === 0xd8 || m === 0x01 || (m >= 0xd0 && m <= 0xd7)) { i += 2; continue; }  // marcadores sin largo
      if (SOF.has(m)) return { ancho: u16be(b, i + 7), alto: u16be(b, i + 5) };
      if (m === 0xd9 || m === 0xda) return null;                                       // fin o datos: no hubo SOF
      i += 2 + u16be(b, i + 2);
    }
    return null;
  }
  return null;
}

/** Medidas finales: como máximo `max` px de ancho, sin agrandar. */
export function dimensionesReducidas(ancho, alto, max = ANCHO_MAX) {
  if (!(ancho > 0 && alto > 0)) return null;
  if (ancho <= max) return { ancho, alto };
  return { ancho: max, alto: Math.max(1, Math.round((alto * max) / ancho)) };
}

/**
 * Anchos intermedios para reducir en pasos de a la mitad (un solo drawImage de 4000 a 1600 px deja dientes de sierra en
 * algunos navegadores). El último es el ancho final.
 */
export function pasosReduccion(anchoOrigen, anchoDestino) {
  if (!(anchoOrigen > anchoDestino)) return [anchoOrigen];
  const pasos = [];
  let w = anchoOrigen;
  while (w > anchoDestino * 2) {
    w = Math.round(w / 2);
    pasos.push(w);
  }
  pasos.push(anchoDestino);
  return pasos;
}

export function extensionPara(tipo) {
  return { "image/webp": "webp", "image/jpeg": "jpg", "image/png": "png" }[tipo] || null;
}

/** 8 caracteres hexadecimales a partir de 4 bytes aleatorios (crypto.getRandomValues en el navegador). */
export function sufijoAleatorio(bytes) {
  return [...bytes].slice(0, 4).map((x) => x.toString(16).padStart(2, "0")).join("");
}

/**
 * Ruta del objeto en el bucket, generada por el código y nunca con el nombre original del archivo:
 * «espacio/aaaammdd-xxxxxxxx.webp».
 */
export function rutaFoto(espacio, hoyIso, sufijo, tipo) {
  const ext = extensionPara(tipo);
  const fecha = String(hoyIso || "").replace(/-/g, "");
  if (!esEspacio(espacio)) throw new Error("espacio_invalido");
  if (!/^\d{8}$/.test(fecha)) throw new Error("fecha_invalida");
  if (!/^[0-9a-f]{8}$/.test(sufijo)) throw new Error("sufijo_invalido");
  if (!ext) throw new Error("tipo_invalido");
  return `${espacio}/${fecha}-${sufijo}.${ext}`;
}

/** Codifica cada segmento de la ruta por separado (las barras quedan como separadores). */
export function rutaCodificada(ruta) {
  return String(ruta).split("/").map(encodeURIComponent).join("/");
}

/** URL pública del objeto: {url}/storage/v1/object/public/{bucket}/{ruta}. */
export function urlPublica(base, ruta, bucket = BUCKET) {
  return `${String(base).replace(/\/+$/, "")}/storage/v1/object/public/${encodeURIComponent(bucket)}/${rutaCodificada(ruta)}`;
}

export function validarAlt(alt) {
  const v = String(alt ?? "").replace(/\s+/g, " ").trim();
  if (!v) return { ok: false, error: "alt_vacio" };
  if (largo(v) > LIMITE_ALT) return { ok: false, error: "alt_largo" };
  return { ok: true, valor: v };
}

export const MENSAJES_FOTO = Object.freeze({
  vacio: "Elige una imagen.",
  tipo: "Sólo se aceptan imágenes JPEG, PNG o WebP.",
  tamano: `La imagen pesa más de ${MAX_ORIGINAL / 1024 / 1024} MB. Usa una versión más liviana.`,
  firma: "El archivo no es una imagen JPEG, PNG o WebP válida (su contenido no coincide con el tipo).",
  pixeles: `La imagen tiene demasiados píxeles (más de ${MAX_PIXELES / 1e6} MP). Usa la versión normal de la foto.`,
  decodificar: "El navegador no pudo abrir la imagen.",
  codificar: "El navegador no pudo preparar la imagen reducida.",
  tamano_final: "Aun reducida, la imagen supera los 5 MB que acepta el bucket.",
  alt_vacio: "Describe la foto: el texto alternativo es obligatorio.",
  alt_largo: `El texto alternativo admite hasta ${LIMITE_ALT} caracteres.`,
  sin_imagen: "Primero elige una imagen.",
});

function comparar(a, b) {
  const oa = Number(a.orden) || 0, ob = Number(b.orden) || 0;
  if (oa !== ob) return oa - ob;
  const ca = String(a.creada || ""), cb = String(b.creada || "");
  if (ca !== cb) return ca < cb ? -1 : 1;
  return String(a.id).localeCompare(String(b.id));
}

/** Fotos de un espacio en el orden del sitio (la primera visible es la imagen principal). */
export function fotosDeEspacio(fotos, espacio) {
  return (fotos || []).filter((f) => f.espacio === espacio).sort(comparar);
}

export function contarPorEspacio(fotos) {
  const c = Object.fromEntries(ESPACIOS.map((e) => [e.id, 0]));
  for (const f of fotos || []) if (Object.prototype.hasOwnProperty.call(c, f.espacio)) c[f.espacio]++;
  return c;
}

export function siguienteOrden(fotosEspacio) {
  const ordenes = (fotosEspacio || []).map((f) => Number(f.orden) || 0);
  return ordenes.length ? Math.max(...ordenes) + 10 : 0;
}

/**
 * Mueve una foto `delta` posiciones (-1 sube, +1 baja) y renumera 0, 10, 20…
 * -> { lista, cambios: [{ id, orden }] } con sólo las filas cuyo orden cambia.
 */
export function moverFoto(fotosEspacio, id, delta) {
  const lista = [...(fotosEspacio || [])].sort(comparar);
  const i = lista.findIndex((f) => f.id === id);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= lista.length || i === j) return { lista, cambios: [] };
  [lista[i], lista[j]] = [lista[j], lista[i]];
  const cambios = [];
  const nueva = lista.map((f, k) => {
    const orden = k * 10;
    if (Number(f.orden) !== orden) cambios.push({ id: f.id, orden });
    return { ...f, orden };
  });
  return { lista: nueva, cambios };
}
