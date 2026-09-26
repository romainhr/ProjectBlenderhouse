// Textos del JS del sitio público en el idioma de la página: español en «/», inglés en «/en/» y francés en «/fr/».
// El idioma sale de <html lang> (lo pone web/build.py) y lo resuelve idioma.js; este módulo lo reexporta.
//
// Diccionarios planos clave -> texto: web/src/i18n/{es,en,fr}.json (el build los copia a dist/i18n/). Las claves del
// JS llevan el prefijo «js.» (js.reserva.fecha_pasada, js.contenido.ver_foto, …). t(clave, variables) busca en el
// idioma de la página, después en el español y, si tampoco está, devuelve la clave tal cual: queda a la vista y se nota.
// Variables con {nombre}: t("js.reserva.exito.texto", { noches: "3 noches" }). Plurales con tn(clave, n): usa
// <clave>.one / <clave>.other según Intl.PluralRules del idioma ({n} es el número con el formato del idioma).
//
// El español no depende de la red: sus textos js.* vienen en textos-es.js, que genera el build desde es.json y se
// importa de forma estática. La página en español no pide ningún diccionario, y en /en/ y /fr/ el respaldo siempre
// está: aunque su diccionario no llegue, nunca se ven las claves (hallazgo JS-2 de la revisión).
// En /en/ y /fr/ se pide sólo el diccionario propio, con fetch(new URL(`../i18n/${IDIOMA}.json`, import.meta.url)),
// es decir, relativo a este archivo y no a la página (sirve igual desde /en/reserva.html o /fr/tour/).
// Sin await de nivel superior: importar este módulo no espera la red, así quien lo importa (contenido-publico.js)
// puede empezar sus lecturas de inmediato (hallazgo JS-3). `listo` se cumple cuando el diccionario del idioma llegó o
// falló (nunca se rechaza); quien pinta textos lo espera antes: `await listo`. Hasta entonces t() da el español.
// Sin document (Node, pruebas) no se pide nada; las pruebas fijan los textos con fijarTextos(). Los textos se
// insertan siempre con textContent o setAttribute (nunca como HTML).
import { IDIOMA, IDIOMAS, IDIOMA_BASE, LOCALE } from "./idioma.js";
import TEXTOS_ES from "./textos-es.js";

export { IDIOMA, IDIOMAS, IDIOMA_BASE, LOCALE, LOCALES, idiomaDe, localeDe } from "./idioma.js";

// Supuesto: 5 s bastan para un JSON chico del mismo sitio; pasado ese plazo se sigue con el español.
export const TIEMPO_MAX_MS = 5000;

const RE_VARIABLE = /\{([A-Za-z_][A-Za-z0-9_]*)\}/g;

// ---------------------------------------------------------------- lógica pura (se prueba en Node)

/** Objeto del JSON -> Map clave -> texto. Descarta lo que no es texto y los textos vacíos (cuentan como faltantes, así
 *  se usa el respaldo en español). Con Map no hay claves heredadas: t("constructor") no devuelve una función. */
export function diccionario(datos) {
  const mapa = new Map();
  if (!datos || typeof datos !== "object" || Array.isArray(datos)) return mapa;
  for (const [clave, texto] of Object.entries(datos)) {
    if (typeof texto === "string" && texto.trim()) mapa.set(clave, texto);
  }
  return mapa;
}

/** Textos js.* en español que vienen con el JS (textos-es.js): el respaldo de t() en los tres idiomas. */
export const RESPALDO_ES = diccionario(TEXTOS_ES);

/** Reemplaza {nombre} por variables[nombre] en una sola pasada (lo insertado no se vuelve a interpretar). Una variable
 *  que falta deja la marca a la vista. */
export function interpolar(texto, variables) {
  if (!variables || typeof variables !== "object") return texto;
  return texto.replace(RE_VARIABLE, (marca, nombre) =>
    Object.prototype.hasOwnProperty.call(variables, nombre) && variables[nombre] != null ? String(variables[nombre]) : marca);
}

/** Traductor sobre dos diccionarios (Map u objeto del JSON): primero `propio`, después `respaldo`, después la clave. */
export function crearTraductor(propio, respaldo) {
  const a = propio instanceof Map ? propio : diccionario(propio);
  const b = respaldo instanceof Map ? respaldo : diccionario(respaldo);
  return (clave, variables) => {
    const texto = a.get(clave) ?? b.get(clave);
    return texto === undefined ? String(clave) : interpolar(texto, variables);
  };
}

const reglas = new Map();
const numeros = new Map();
function enCache(cache, locale, crear) {
  if (!cache.has(locale)) cache.set(locale, crear(locale));
  return cache.get(locale);
}

/** Plural con el traductor `traducir`: <clave>.<categoría de Intl.PluralRules> y, si no existe, <clave>.other.
 *  Agrega la variable {n} con `n` escrito con el formato de `locale`. */
export function traducirPlural(traducir, locale, clave, n, variables = {}) {
  const categoria = enCache(reglas, locale, (l) => new Intl.PluralRules(l)).select(n);
  const vars = { ...variables, n: enCache(numeros, locale, (l) => new Intl.NumberFormat(l)).format(n) };
  const exacta = `${clave}.${categoria}`;
  const texto = traducir(exacta, vars);
  return texto === exacta ? traducir(`${clave}.other`, vars) : texto;
}

// ---------------------------------------------------------------- red

/** Diccionario de `idioma` leído de ../i18n/<idioma>.json relativo a `base` (por defecto, este módulo). Devuelve un
 *  Map vacío ante cualquier falla (sin fetch, idioma desconocido, respuesta no ok, JSON inválido o plazo vencido). */
export async function cargarDiccionario(idioma, { fetch: f = globalThis.fetch, base = import.meta.url, tiempo = TIEMPO_MAX_MS } = {}) {
  if (!IDIOMAS.includes(idioma) || typeof f !== "function") return new Map();
  const ctrl = typeof AbortController === "function" ? new AbortController() : null;
  const reloj = setTimeout(() => ctrl?.abort(), tiempo);
  try {
    const r = await f(new URL(`../i18n/${idioma}.json`, base), ctrl ? { signal: ctrl.signal } : {});
    if (!r || !r.ok) return new Map();
    return diccionario(await r.json());             // el cuerpo también queda bajo el plazo (misma señal)
  } catch {
    return new Map();
  } finally {
    clearTimeout(reloj);
  }
}

// ---------------------------------------------------------------- estado de la página

let traductor = crearTraductor(new Map(), RESPALDO_ES);

/** Texto de `clave` en el idioma de la página, con {variables}. Si falta, el español; si falta también, la clave. */
export function t(clave, variables) {
  return traductor(clave, variables);
}

/** Plural de `clave` para `n` en el idioma de la página: tn("js.reserva.noches", 3) -> «3 noches». */
export function tn(clave, n, variables) {
  return traducirPlural(t, LOCALE, clave, n, variables);
}

/** Fija los textos sin red: `propio` (los del idioma que se quiere probar) y `respaldo` (por defecto, el español de
 *  textos-es.js). Para pruebas en Node, donde no hay document y no se carga nada. Acepta Map u objeto del JSON. */
export function fijarTextos(propio, respaldo = RESPALDO_ES) {
  traductor = crearTraductor(propio, respaldo);
}

/** Se cumple cuando t() ya tiene los textos del idioma de la página (o cuando su diccionario falló o venció el plazo:
 *  entonces sigue el español). En español y en Node se cumple enseguida, sin red. Nunca se rechaza. */
export const listo = typeof document === "undefined" || IDIOMA === IDIOMA_BASE
  ? Promise.resolve()
  : cargarDiccionario(IDIOMA).then((propio) => { if (propio.size) fijarTextos(propio); }, () => {});
