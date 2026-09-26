// Idioma de la página pública, sin red ni espera: español en «/», inglés en «/en/» y francés en «/fr/». web/build.py
// arma cada idioma a partir del HTML en español de web/src y le pone <html lang="…">; este módulo sólo lee ese lang.
//
// Está separado de i18n.js (que además trae los textos del JS) para que un módulo que sólo necesita el formato del
// idioma, como sitio.js al escribir los precios de ejemplo, lo importe sin cargar diccionarios. No tiene await de
// nivel superior ni importa nada: quien lo importa no espera ninguna red. i18n.js reexporta todo lo de aquí.

export const IDIOMAS = Object.freeze(["es", "en", "fr"]);
export const IDIOMA_BASE = "es";
// Formato de fechas y números de cada idioma. es-CL: la propiedad está en Chile (tarifas en CLP, ZONA_PROPIEDAD).
export const LOCALES = Object.freeze({ es: "es-CL", en: "en-US", fr: "fr-FR" });

/** Valor de <html lang> -> "es", "en" o "fr" (se mira sólo la subetiqueta principal: «en-US» es «en»); si no, "es". */
export function idiomaDe(lang) {
  const principal = typeof lang === "string" ? lang.trim().toLowerCase().split("-")[0] : "";
  return IDIOMAS.includes(principal) ? principal : IDIOMA_BASE;
}

/** Idioma -> locale de Intl (es-CL, en-US o fr-FR); un idioma desconocido usa el del español. */
export function localeDe(idioma) {
  return IDIOMAS.includes(idioma) ? LOCALES[idioma] : LOCALES[IDIOMA_BASE];
}

/** Idioma de la página (de <html lang>) y su locale. En Node, sin document, es el español. */
export const IDIOMA = idiomaDe(globalThis.document?.documentElement?.lang);
export const LOCALE = localeDe(IDIOMA);

// ---------------------------------------------------------------- idioma elegido en el selector
// Cookie nf_lang: en Netlify reemplaza la detección por el idioma del navegador (ADR 0007, decisión 4). La usan el
// selector del sitio (sitio.js) y el del tour (tour/js/interfaz.js), que se arma en un solo lugar: aquí.
export const MAX_EDAD_IDIOMA_S = 31536000;   // un año

/** Texto de document.cookie para recordar `codigo` (todo el sitio, un año, Lax y Secure), o null si no es es, en ni fr. */
export function cookieIdioma(codigo) {
  if (!IDIOMAS.includes(codigo)) return null;
  return `nf_lang=${codigo}; path=/; max-age=${MAX_EDAD_IDIOMA_S}; SameSite=Lax; Secure`;
}

/** Guarda en `doc` la cookie de `codigo`. Devuelve false (y no toca nada) si no es es, en ni fr, o si no hay `doc`. */
export function recordarIdioma(codigo, doc = globalThis.document) {
  const cookie = cookieIdioma(codigo);
  if (!cookie || !doc) return false;
  doc.cookie = cookie;
  return true;
}

// Eventos en que se guarda la elección, antes de que el enlace navegue: el clic; el clic central (auxclick, abre otra
// pestaña), y el menú contextual (contextmenu: clic derecho, pulsación larga en el teléfono o la tecla de menú), de
// donde salen «Abrir en una pestaña nueva» y «Abrir en otra ventana». Sin este último, la pestaña nueva llegaba sin
// cookie y la regla Language= devolvía al visitante al idioma de su navegador. Supuesto aceptado: abrir el menú del
// selector sólo para copiar el enlace también guarda ese idioma.
export const EVENTOS_SELECTOR_IDIOMA = Object.freeze(["click", "auxclick", "contextmenu"]);

/** Escucha en `doc` los eventos de EVENTOS_SELECTOR_IDIOMA sobre <a data-i18n-alternar="es|en|fr"> y guarda la
 *  cookie de ese idioma. En auxclick cuenta sólo el botón central: el derecho ya pasó por contextmenu. */
export function escucharSelectorIdioma(doc = globalThis.document) {
  const guardar = (e) => {
    if (e.type === "auxclick" && e.button !== 1) return;
    const enlace = typeof e.target?.closest === "function" ? e.target.closest("a[data-i18n-alternar]") : null;
    if (enlace) recordarIdioma(enlace.getAttribute("data-i18n-alternar"), doc);
  };
  for (const tipo of EVENTOS_SELECTOR_IDIOMA) doc.addEventListener(tipo, guardar);
}
