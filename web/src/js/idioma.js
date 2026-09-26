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
