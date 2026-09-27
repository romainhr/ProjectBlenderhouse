// Ayudas de las pruebas que imitan una página (no es un archivo de pruebas: npm test sólo corre tests/*.test.mjs).
//
// copiaDelSitio() copia módulos de web/src/js/ y los diccionarios de web/src/i18n/ a una carpeta temporal nueva. Cada
// copia es una instancia nueva de i18n.js e idioma.js, con su propio IDIOMA (el de <html lang> al importarla), como
// una página recién abierta. Importar src/js/i18n.js con «?caso=…» no alcanza: sus import estáticos (idioma.js,
// textos-es.js) quedarían compartidos entre los casos. `extra` agrega archivos (p. ej. un js/config.js ficticio).
import { copyFileSync, cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));
export const MODULOS_I18N = Object.freeze(["i18n.js", "idioma.js", "textos-es.js"]);
const copias = [];
after(() => { for (const d of copias) rmSync(d, { recursive: true, force: true }); });

/** Carpeta temporal con js/<modulos> e i18n/*.json. Devuelve { dir, url(ruta) } (url: file:// de un archivo). */
export function copiaDelSitio(modulos = MODULOS_I18N, extra = {}) {
  const dir = mkdtempSync(join(tmpdir(), "sitio-prueba-"));
  copias.push(dir);
  mkdirSync(join(dir, "js"));
  for (const m of modulos) copyFileSync(join(SRC, "js", m), join(dir, "js", m));
  cpSync(join(SRC, "i18n"), join(dir, "i18n"), { recursive: true });
  for (const [ruta, texto] of Object.entries(extra)) {
    mkdirSync(dirname(join(dir, ruta)), { recursive: true });
    writeFileSync(join(dir, ruta), texto);
  }
  return { dir, url: (ruta) => pathToFileURL(join(dir, ruta)).href };
}

/** Pone `document` y `fetch` globales mientras corre `fn` (async) y después deja los que había. */
export async function conGlobales({ document, fetch }, fn) {
  const antes = { document: globalThis.document, fetch: globalThis.fetch, tenia: "document" in globalThis };
  if (document === undefined) delete globalThis.document; else globalThis.document = document;
  globalThis.fetch = fetch;
  try {
    return await fn();
  } finally {
    if (antes.tenia) globalThis.document = antes.document; else delete globalThis.document;
    globalThis.fetch = antes.fetch;
  }
}

/** Espera (con vueltas del bucle de eventos) a que `condicion()` sea verdadera; falla pasado `ms`. */
export async function hasta(condicion, ms = 2000) {
  const fin = Date.now() + ms;
  while (!condicion()) {
    if (Date.now() > fin) throw new Error("la condición no se cumplió a tiempo");
    await new Promise((ok) => setTimeout(ok, 1));
  }
}

/** Respuesta de fetch falsa con `cuerpo` como JSON. */
export const respuesta = (cuerpo, estado = 200) => ({ ok: estado >= 200 && estado < 300, status: estado, json: async () => cuerpo });

/** Código fuente JS sin comentarios, en una sola pasada que respeta los textos ("…", '…', `…`): un «/*» o un «//»
 *  dentro de un texto no abre un comentario, y un «/*» dentro de un comentario de línea (p. ej. «i18n/*.json») no se
 *  come el código hasta el próximo «*\/». No entiende expresiones regulares literales con comillas o barras dobles. */
export function sinComentarios(fuente) {
  return fuente.replace(/("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`)|\/\*[\s\S]*?\*\/|\/\/[^\n]*/g,
    (_, texto) => texto ?? "");
}
