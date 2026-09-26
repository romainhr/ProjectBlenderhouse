// Preparación de una foto en el navegador antes de subirla: comprueba tipo, peso, firma y píxeles; la reduce a
// ANCHO_MAX px de ancho con canvas y la vuelve a codificar como WebP (o JPEG si el navegador no codifica WebP).
// Volver a codificar también quita los metadatos del archivo original (EXIF, ubicación GPS del teléfono).
import {
  ANCHO_MAX, CALIDAD_JPEG, CALIDAD_WEBP, MAX_PIXELES, MAX_SUBIDA, dimensionesPorCabecera, dimensionesReducidas,
  pasosReduccion, tipoPorFirma, validarArchivo,
} from "./logica-fotos.js";

const BYTES_CABECERA = 512 * 1024;     // la cabecera JPEG (EXIF + ICC) cabe de sobra en 512 kB

export class ErrorImagen extends Error {
  constructor(codigo) {
    super(codigo);
    this.name = "ErrorImagen";
    this.codigo = codigo;
  }
}

/** Decodifica con un <img> (los navegadores actuales aplican la orientación EXIF al dibujarlo en canvas). */
async function decodificar(archivo) {
  const url = URL.createObjectURL(archivo);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    if (!img.naturalWidth || !img.naturalHeight) throw new Error("sin medidas");
    return img;
  } catch {
    throw new ErrorImagen("decodificar");
  } finally {
    URL.revokeObjectURL(url);
  }
}

function lienzo(ancho, alto) {
  const c = document.createElement("canvas");
  c.width = ancho;
  c.height = alto;
  const ctx = c.getContext("2d", { alpha: false });
  if (!ctx) throw new ErrorImagen("codificar");
  ctx.fillStyle = "#ffffff";                           // fondo blanco: un PNG con transparencia no queda negro en JPEG
  ctx.fillRect(0, 0, ancho, alto);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  return { c, ctx };
}

function aBlob(canvas, tipo, calidad) {
  return new Promise((ok) => canvas.toBlob((b) => ok(b), tipo, calidad));
}

/**
 * -> { blob, tipo, ancho, alto, anchoOrigen, altoOrigen, pesoOrigen }
 * Lanza ErrorImagen con un código de MENSAJES_FOTO.
 */
export async function prepararImagen(archivo) {
  const v = validarArchivo(archivo);
  if (!v.ok) throw new ErrorImagen(v.error);
  const cabecera = new Uint8Array(await archivo.slice(0, BYTES_CABECERA).arrayBuffer());
  if (!tipoPorFirma(cabecera)) throw new ErrorImagen("firma");
  const dims = dimensionesPorCabecera(cabecera);
  if (dims && dims.ancho * dims.alto > MAX_PIXELES) throw new ErrorImagen("pixeles");

  const img = await decodificar(archivo);
  const anchoOrigen = img.naturalWidth, altoOrigen = img.naturalHeight;
  if (anchoOrigen * altoOrigen > MAX_PIXELES) throw new ErrorImagen("pixeles");
  const final = dimensionesReducidas(anchoOrigen, altoOrigen, ANCHO_MAX);

  let fuente = img, w = anchoOrigen, h = altoOrigen, canvas = null;
  for (const paso of pasosReduccion(anchoOrigen, final.ancho)) {
    const alto = paso === final.ancho ? final.alto : Math.max(1, Math.round((h * paso) / w));
    const { c, ctx } = lienzo(paso, alto);
    ctx.drawImage(fuente, 0, 0, w, h, 0, 0, paso, alto);
    if (canvas) { canvas.width = 0; canvas.height = 0; }         // libera el paso anterior
    fuente = canvas = c;
    w = paso;
    h = alto;
  }

  let blob = await aBlob(canvas, "image/webp", CALIDAD_WEBP);
  if (!blob || blob.type !== "image/webp") blob = await aBlob(canvas, "image/jpeg", CALIDAD_JPEG);
  canvas.width = 0;
  canvas.height = 0;
  if (!blob || (blob.type !== "image/webp" && blob.type !== "image/jpeg")) throw new ErrorImagen("codificar");
  if (blob.size > MAX_SUBIDA) throw new ErrorImagen("tamano_final");
  return { blob, tipo: blob.type, ancho: final.ancho, alto: final.alto, anchoOrigen, altoOrigen, pesoOrigen: archivo.size };
}
