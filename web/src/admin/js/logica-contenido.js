// Lógica de la vista de textos (public.contenido, migraciones 0003 y 0005). Sin DOM.
import { clp } from "../../js/reserva-logica.js";
import { largo } from "./util.js";

// 0003_gestion.sql (contrato del backend): tipo in ('texto', 'parrafo', 'precio'); valor text not null (<= 4000);
// un 'precio' es un entero entre 0 y 10 000 000 escrito como texto de dígitos; clave '^[a-z0-9][a-z0-9_.-]{1,59}$'.
// 0005_contenido_idiomas.sql: valor_en y valor_fr, text con null permitido, con los mismos límites que valor (no en
// blanco, hasta 4000) y siempre null en los precios. null = el sitio en ese idioma muestra el texto fijo de la página:
// su traducción de web/src/i18n/<idioma>.json si el HTML de la página ya marca ese texto para traducir, o el original
// en español si todavía no (el build lo avisa con AVISO_I18N). Las ayudas del portal lo dicen así para no prometer más.
export const TIPOS = Object.freeze(["texto", "parrafo", "precio"]);
export const LIMITE_VALOR = 4000;
export const PRECIO_MAX = 10000000;
export const RE_CLAVE = /^[a-z0-9][a-z0-9_.-]{1,59}$/;

// Se aceptan dígitos sueltos o con separador de miles de es-CL («58.000» o «58 000»); se guarda sólo con dígitos.
const RE_PRECIO = /^(\d+|\d{1,3}([. ]\d{3})+)$/;

/**
 * Valida y normaliza el valor según el tipo -> { ok: true, valor } o { ok: false, error }.
 * Regla propia del portal (más estricta que la base): los textos no pueden quedar vacíos, para no dejar huecos en el sitio.
 */
export function validarValor(tipo, bruto, clave = "") {
  const s = String(bruto ?? "").replace(/\r\n?/g, "\n");
  if (tipo === "precio") {
    const t = s.replace(/[  ]/g, " ").trim().replace(/^CLP\s*/i, "").replace(/^\$\s*/, "");
    if (!t) return { ok: false, error: "vacio" };
    if (!RE_PRECIO.test(t)) return { ok: false, error: "precio_formato" };
    const digitos = t.replace(/[. ]/g, "");
    const n = Number(digitos);
    if (!Number.isSafeInteger(n) || n < 0 || n > PRECIO_MAX) return { ok: false, error: "precio_rango" };
    // el sitio trata una noche en 0 como «sin editar» (contenido-publico.js, tarifasEditadas): no se acepta
    if (clave === "tarifa.noche" && n === 0) return { ok: false, error: "precio_noche_cero" };
    return { ok: true, valor: String(n) };                     // sin ceros a la izquierda
  }
  if (!TIPOS.includes(tipo)) return { ok: false, error: "tipo" };
  const v = tipo === "texto" ? s.replace(/\s+/g, " ").trim() : s.trim();
  if (!v) return { ok: false, error: "vacio" };
  if (largo(v) > LIMITE_VALOR) return { ok: false, error: "largo" };
  return { ok: true, valor: v };
}

export const MENSAJES_VALOR = Object.freeze({
  vacio: "Este texto no puede quedar vacío.",
  largo: `Admite hasta ${LIMITE_VALOR.toLocaleString("es-CL")} caracteres.`,
  precio_formato: "Escribe sólo el monto en pesos, con dígitos (p. ej. 58000 o 58.000), sin decimales.",
  precio_rango: `El monto debe estar entre 0 y ${PRECIO_MAX.toLocaleString("es-CL")}.`,
  precio_noche_cero: "La tarifa por noche debe ser mayor que 0 (la limpieza sí puede ser 0).",
  tipo: "Tipo de contenido desconocido.",
  precio_sin_traduccion: "Los precios no se traducen: el monto es el mismo en los tres idiomas.",
});

// ---------------------------------------------------------------- idiomas (0005)
// El sitio público está en español (/), inglés (/en/) y francés (/fr/). El portal sigue en español.
export const IDIOMAS = Object.freeze(["es", "en", "fr"]);
export const TRADUCCIONES = Object.freeze(["en", "fr"]);                  // opcionales
export const COLUMNA_IDIOMA = Object.freeze({ es: "valor", en: "valor_en", fr: "valor_fr" });
export const NOMBRE_IDIOMA = Object.freeze({ es: "Español", en: "Inglés", fr: "Francés" });

/** «el sitio en inglés»: para las ayudas y avisos. */
function sitioEn(idioma) {
  return `el sitio en ${NOMBRE_IDIOMA[idioma].toLowerCase()}`;
}

/** Qué muestra una página en inglés o en francés sin traducción propia: cierto antes y después de traducir la página. */
export const TEXTO_FIJO = "el texto fijo de la página (el original en español mientras esa página no esté traducida)";

/** Aviso de la vista cuando la base todavía no tiene valor_en y valor_fr (0005 sin aplicar). */
export const AVISO_SIN_IDIOMAS =
  "Las traducciones al inglés y al francés todavía no se pueden editar: falta aplicar la migración " +
  "0005_contenido_idiomas.sql en Supabase (pasos en docs/portal-gestion.md). Mientras tanto puedes editar el español; " +
  `el sitio en inglés y en francés muestra ${TEXTO_FIJO}.`;

/** ¿La fila tiene traducciones? Los precios no: el monto es el mismo en los tres idiomas. */
export function esTraducible(fila) {
  return Boolean(fila) && fila.tipo !== "precio";
}

/**
 * Traducción opcional -> { ok: true, valor } (valor null si quedó vacía) o { ok: false, error }.
 * Vacía (o sólo espacios) = null: el sitio en ese idioma muestra TEXTO_FIJO. Si trae texto, se valida y normaliza
 * igual que el español (validarValor). En un precio sólo se acepta vacía.
 */
export function validarTraduccion(tipo, bruto) {
  const vacia = !String(bruto ?? "").trim();
  if (tipo === "precio") return vacia ? { ok: true, valor: null } : { ok: false, error: "precio_sin_traduccion" };
  if (!TIPOS.includes(tipo)) return { ok: false, error: "tipo" };
  if (vacia) return { ok: true, valor: null };
  return validarValor(tipo, bruto);
}

/** Valores de una fila para el formulario, por idioma (null -> ""). */
export function valoresDeFila(fila) {
  const f = fila || {};
  return Object.fromEntries(IDIOMAS.map((i) => [i, String(f[COLUMNA_IDIOMA[i]] ?? "")]));
}

/** Idiomas que se editan en la fila: los tres si la base los tiene y el tipo se traduce; si no, sólo el español. */
export function idiomasDeFila(fila, { idiomas = true } = {}) {
  return idiomas && esTraducible(fila) ? IDIOMAS : ["es"];
}

/**
 * Valida la fila completa (campos: { es, en?, fr? }) ->
 *   { ok: true, cambios }   cambios = { valor } o { valor, valor_en, valor_fr } (vacío -> null), ya normalizados
 *   { ok: false, errores }  errores = { es?, en?, fr? } con códigos de MENSAJES_VALOR
 * `idiomas: false` (base sin la 0005) valida y guarda sólo el español.
 * No se manda tal cual: la vista guarda sólo las columnas que cambiaron (columnasCambiadas).
 */
export function validarFila(fila, campos, { idiomas = true } = {}) {
  const c = campos || {};
  const errores = {};
  const cambios = {};
  const es = validarValor(fila.tipo, c.es, fila.clave);
  if (es.ok) cambios.valor = es.valor;
  else errores.es = es.error;
  for (const idioma of idiomasDeFila(fila, { idiomas })) {
    if (idioma === "es") continue;
    const t = validarTraduccion(fila.tipo, c[idioma]);
    if (t.ok) cambios[COLUMNA_IDIOMA[idioma]] = t.valor;
    else errores[idioma] = t.error;
  }
  return Object.keys(errores).length ? { ok: false, errores } : { ok: true, cambios };
}

/**
 * Lo que se guarda de una fila: de `cambios` (validarFila, ya normalizados) sólo las columnas cuyo campo difiere de lo
 * cargado (`originales`, de valoresDeFila) -> { valor?, valor_en?, valor_fr? }, vacío si no cambió nada.
 * Así guardar un idioma no reenvía los otros tal como se cargaron: si alguien los cambió después (otra pestaña, el
 * teléfono o el SQL Editor), ese cambio se conserva. Se compara lo escrito (`actuales`) y no lo normalizado, para no
 * reenviar un campo sin tocar sólo porque la base lo guarda con otros espacios.
 */
export function columnasCambiadas(cambios, originales, actuales) {
  const c = cambios || {}, o = originales || {}, a = actuales || {};
  const r = {};
  for (const idioma of IDIOMAS) {
    const columna = COLUMNA_IDIOMA[idioma];
    if (!(idioma in a) || !(columna in c)) continue;
    if (String(a[idioma] ?? "") !== String(o[idioma] ?? "")) r[columna] = c[columna];
  }
  return r;
}

/** ¿Algún campo de la fila cambió respecto de lo guardado? (sólo los idiomas presentes en `actuales`) */
export function hayCambiosFila(originales, actuales) {
  return Object.keys(actuales || {}).some((i) => String(actuales[i] ?? "") !== String((originales || {})[i] ?? ""));
}

/**
 * Texto de ayuda bajo cada campo:
 *   precio -> la vista previa en CLP;
 *   inglés o francés vacío -> qué muestra el sitio en ese idioma (TEXTO_FIJO);
 *   párrafos, o textos cerca del límite -> el contador de caracteres.
 */
export function ayudaCampo({ tipo, idioma = "es", valor = "" }) {
  if (tipo === "precio") {
    const p = previaPrecio(valor);
    return p ? `En el sitio se verá como «${p}». Monto en pesos, sin decimales; es el mismo en los tres idiomas.`
      : "Monto en pesos, sin decimales; es el mismo en los tres idiomas.";
  }
  if (idioma !== "es" && !String(valor ?? "").trim()) {
    return `Vacío: ${sitioEn(idioma)} muestra ${TEXTO_FIJO}.`;
  }
  const l = largo(valor);
  return tipo === "parrafo" || l > LIMITE_VALOR * 0.8
    ? `${l.toLocaleString("es-CL")} / ${LIMITE_VALOR.toLocaleString("es-CL")} caracteres` : "";
}

/** Rótulo de cada campo: «Español (obligatorio)», «Inglés (opcional)». */
export function rotuloIdioma(idioma) {
  return { nombre: NOMBRE_IDIOMA[idioma], requisito: idioma === "es" ? "obligatorio" : "opcional" };
}

/** Vista previa del precio como lo muestra el sitio («CLP 58.000»), o "" si no es válido. */
export function previaPrecio(bruto) {
  const v = validarValor("precio", bruto);
  return v.ok ? clp(Number(v.valor)) : "";
}

function comparar(a, b) {
  const oa = Number(a.orden) || 0, ob = Number(b.orden) || 0;
  if (oa !== ob) return oa - ob;
  return String(a.clave).localeCompare(String(b.clave));
}

/**
 * Agrupa las filas por `grupo`, con las filas por `orden` (y clave). Los grupos siguen el menor `orden` de sus filas
 * (así el orden de la semilla decide también el de las secciones) y, a igualdad, el nombre.
 * -> [{ grupo, titulo, filas: [...] }]
 */
export function agruparContenido(filas) {
  const mapa = new Map();
  for (const f of filas || []) {
    const g = String(f.grupo || "otros");
    if (!mapa.has(g)) mapa.set(g, []);
    mapa.get(g).push(f);
  }
  const grupos = [...mapa.entries()].map(([grupo, fs]) => {
    fs.sort(comparar);
    return { grupo, titulo: tituloGrupo(grupo), filas: fs, min: Math.min(...fs.map((f) => Number(f.orden) || 0)) };
  });
  grupos.sort((a, b) => a.min - b.min || a.grupo.localeCompare(b.grupo));
  return grupos.map(({ grupo, titulo, filas: fs }) => ({ grupo, titulo, filas: fs }));
}

export function tituloGrupo(grupo) {
  const s = String(grupo || "").replace(/[_.-]+/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "Otros";
}
