// Pruebas de web/src/js/i18n.js y de los diccionarios web/src/i18n/{es,en,fr}.json con el ejecutor incluido en Node
// (sin dependencias ni DOM real):   cd web && npm test     (node --test tests/*.test.mjs)
// La página se imita con un `document` mínimo ({ documentElement: { lang } }) y la red con un fetch falso; cada caso
// importa una copia nueva de los módulos (copiaDelSitio) para tener una instancia nueva con su propio IDIOMA.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  IDIOMA, IDIOMAS, IDIOMA_BASE, LOCALE, LOCALES, RESPALDO_ES, cargarDiccionario, crearTraductor, diccionario,
  fijarTextos, idiomaDe, interpolar, listo, localeDe, t, tn, traducirPlural,
} from "../src/js/i18n.js";
import * as idioma from "../src/js/idioma.js";
import TEXTOS_ES from "../src/js/textos-es.js";
import { conGlobales, copiaDelSitio, respuesta, sinComentarios } from "./copia-sitio.mjs";

const leer = (ruta) => readFileSync(new URL(ruta, import.meta.url), "utf8");
const DICCIONARIOS = Object.fromEntries(["es", "en", "fr"].map((i) => [i, JSON.parse(leer(`../src/i18n/${i}.json`))]));

/** Importa una instancia nueva de i18n.js como si estuviera en una página con <html lang="`lang`"> y `fetch`
 *  (sin `lang`, como en Node: sin document). La importación no espera el diccionario: se devuelve apenas evalúa. */
async function enPagina(lang, fetch) {
  const copia = copiaDelSitio();
  return conGlobales({ document: lang === undefined ? undefined : { documentElement: { lang } }, fetch },
    () => import(copia.url("js/i18n.js")));
}

/** fetch falso que sirve los diccionarios reales desde el disco y anota cada URL pedida. */
function fetchDelDisco(pedidos) {
  return async (url, op) => {
    pedidos.push({ url: String(url), op });
    return respuesta(JSON.parse(readFileSync(fileURLToPath(new URL(String(url))), "utf8")));
  };
}

// ---------------------------------------------------------------- idioma y locale
test("idiomaDe: es, en o fr desde <html lang> (subetiqueta principal); cualquier otra cosa es español", () => {
  assert.deepEqual(IDIOMAS, ["es", "en", "fr"]);
  assert.equal(IDIOMA_BASE, "es");
  for (const [lang, idioma] of [["es", "es"], ["en", "en"], ["fr", "fr"], ["en-US", "en"], ["FR", "fr"],
    [" fr-CA ", "fr"], ["es-CL", "es"], ["de", "es"], ["pt-BR", "es"], ["english", "es"], ["", "es"],
    [undefined, "es"], [null, "es"], [42, "es"]]) {
    assert.equal(idiomaDe(lang), idioma, `lang=${JSON.stringify(lang)}`);
  }
});

test("localeDe: es-CL, en-US y fr-FR; un idioma desconocido usa el del español", () => {
  assert.deepEqual(LOCALES, { es: "es-CL", en: "en-US", fr: "fr-FR" });
  assert.ok(Object.isFrozen(LOCALES) && Object.isFrozen(IDIOMAS));
  assert.equal(localeDe("en"), "en-US");
  assert.equal(localeDe("fr"), "fr-FR");
  assert.equal(localeDe("es"), "es-CL");
  assert.equal(localeDe("de"), "es-CL");
  assert.equal(localeDe("toString"), "es-CL");
});

test("en Node (sin document) el módulo carga sin red: español, es-CL y los textos de textos-es.js", async () => {
  assert.equal(IDIOMA, "es");
  assert.equal(LOCALE, "es-CL");
  await listo;                                                       // se cumple enseguida, sin red
  assert.equal(t("js.clave.que.no.existe"), "js.clave.que.no.existe");
  assert.equal(t("js.reserva.red"), DICCIONARIOS.es["js.reserva.red"]);
  // una instancia nueva sin document no llama a fetch aunque exista
  let llamadas = 0;
  const m = await enPagina(undefined, async () => { llamadas++; return respuesta({}); });
  await m.listo;
  assert.equal(llamadas, 0);
  assert.equal(m.IDIOMA, "es");
  assert.equal(m.t("js.reserva.red"), DICCIONARIOS.es["js.reserva.red"]);
  // y sin fetch tampoco falla: queda el español
  const sinFetch = await enPagina("en", undefined);
  await sinFetch.listo;
  assert.equal(sinFetch.IDIOMA, "en");
  assert.equal(sinFetch.t("js.reserva.red"), DICCIONARIOS.es["js.reserva.red"]);
});

test("idioma.js: idioma y locale de la página sin red ni await, y i18n.js reexporta lo mismo", async () => {
  for (const nombre of ["IDIOMAS", "IDIOMA_BASE", "LOCALES", "IDIOMA", "LOCALE", "idiomaDe", "localeDe"]) {
    assert.ok(nombre in idioma, nombre);
  }
  assert.equal(IDIOMAS, idioma.IDIOMAS);                             // la misma instancia, no una copia
  assert.equal(LOCALES, idioma.LOCALES);
  assert.equal(idiomaDe, idioma.idiomaDe);
  assert.equal(localeDe, idioma.localeDe);
  const fuente = sinComentarios(readFileSync(new URL("../src/js/idioma.js", import.meta.url), "utf8"));
  assert.doesNotMatch(fuente, /^\s*import\b|\bimport\(|\bawait\b|\bfetch\b/m, "idioma.js no importa ni espera nada");
  // en una página en francés: el locale sale de <html lang> sin pedir nada
  const copia = copiaDelSitio(["idioma.js"]);
  let llamadas = 0;
  const fr = await conGlobales({ document: { documentElement: { lang: "fr" } }, fetch: async () => { llamadas++; } },
    () => import(copia.url("js/idioma.js")));
  assert.equal(fr.IDIOMA, "fr");
  assert.equal(fr.LOCALE, "fr-FR");
  assert.equal(llamadas, 0);
});

// ---------------------------------------------------------------- traducción
test("diccionario: sólo textos no vacíos, en un Map sin claves heredadas", () => {
  const d = diccionario(JSON.parse('{"a":"A","b":"","c":"  ","d":5,"e":null,"f":{"x":1},"__proto__":"P","g":"G"}'));
  assert.deepEqual([...d.keys()], ["a", "__proto__", "g"]);
  assert.equal(d.get("__proto__"), "P");
  for (const malo of [null, undefined, "texto", 5, ["a"], true]) assert.equal(diccionario(malo).size, 0);
});

test("crearTraductor: idioma propio, después el respaldo en español, después la clave", () => {
  const tr = crearTraductor({ saludo: "Hello {nombre}", vacio: "" }, { saludo: "Hola {nombre}", solo_es: "Sólo en español", vacio: "Vacío en en" });
  assert.equal(tr("saludo", { nombre: "Ana" }), "Hello Ana");
  assert.equal(tr("solo_es"), "Sólo en español");
  assert.equal(tr("vacio"), "Vacío en en");                        // vacío en el idioma: cuenta como faltante
  assert.equal(tr("no.existe"), "no.existe");
  for (const heredada of ["constructor", "toString", "__proto__", "hasOwnProperty"]) assert.equal(tr(heredada), heredada);
  assert.equal(crearTraductor()("x"), "x");
  assert.equal(crearTraductor(new Map([["x", "equis"]]), null)("x"), "equis");
});

test("interpolar: {nombre} en una sola pasada; lo que falta queda a la vista y lo insertado no se reinterpreta", () => {
  assert.equal(interpolar("{a} y {b}", { a: 1, b: "dos" }), "1 y dos");
  assert.equal(interpolar("{a} y {falta}", { a: "x" }), "x y {falta}");
  assert.equal(interpolar("{a}", { a: "{b}", b: "no" }), "{b}");
  assert.equal(interpolar("{a}{a}", { a: 0 }), "00");
  assert.equal(interpolar("{a}", { a: null }), "{a}");
  assert.equal(interpolar("{toString}", {}), "{toString}");      // sólo propiedades propias
  assert.equal(interpolar("<b>{a}</b>", { a: "<img src=x>" }), "<b><img src=x></b>");   // texto: se usa con textContent
  assert.equal(interpolar("sin variables", undefined), "sin variables");
  assert.equal(interpolar("{ a }", { a: 1 }), "{ a }");
});

test("traducirPlural: categoría de Intl.PluralRules, respaldo en .other y {n} con el formato del idioma", () => {
  const tr = crearTraductor({ "n.one": "{n} noche", "n.other": "{n} noches", "p.other": "{n} × {x}" });
  assert.equal(traducirPlural(tr, "es-CL", "n", 1), "1 noche");
  assert.equal(traducirPlural(tr, "es-CL", "n", 3), "3 noches");
  assert.equal(traducirPlural(tr, "es-CL", "n", 0), "0 noches");
  assert.equal(traducirPlural(tr, "es-CL", "n", 1_000_000), "1.000.000 noches");   // «many» en es: cae en .other
  assert.equal(traducirPlural(tr, "es-CL", "p", 1, { x: "y" }), "1 × y");          // sin .one: .other
  const fr = crearTraductor({ "n.one": "{n} nuit", "n.other": "{n} nuits" });
  assert.equal(traducirPlural(fr, "fr-FR", "n", 0), "0 nuit");                     // en francés 0 es singular
  assert.equal(traducirPlural(fr, "fr-FR", "n", 2), "2 nuits");
  const en = crearTraductor({ "n.one": "{n} night", "n.other": "{n} nights" });
  assert.equal(traducirPlural(en, "en-US", "n", 0), "0 nights");
  assert.equal(traducirPlural(en, "en-US", "n", 1000), "1,000 nights");
  assert.equal(traducirPlural(en, "en-US", "falta", 2), "falta.other");            // sin textos: la clave a la vista
});

test("t, tn y fijarTextos: los textos del módulo se fijan sin red (Map u objeto del JSON)", () => {
  try {
    fijarTextos(DICCIONARIOS.es);
    assert.equal(t("js.reserva.fecha_pasada"), "La llegada no puede ser en el pasado.");
    assert.equal(t("js.reserva.min_noches", { minNoches: 2 }), "La estadía mínima es de 2 noches.");
    assert.equal(tn("js.reserva.noches", 1), "1 noche");
    assert.equal(tn("js.reserva.personas", 3), "3 personas");
    fijarTextos(new Map([["js.reserva.red", "Offline"]]), DICCIONARIOS.es);
    assert.equal(t("js.reserva.red"), "Offline");
    assert.equal(t("js.reserva.acepta"), DICCIONARIOS.es["js.reserva.acepta"]);   // respaldo en español
    fijarTextos({ "js.reserva.red": "Hors ligne" });                               // respaldo por defecto: textos-es.js
    assert.equal(t("js.reserva.red"), "Hors ligne");
    assert.equal(t("js.reserva.acepta"), DICCIONARIOS.es["js.reserva.acepta"]);
    fijarTextos({}, {});                                                           // sin ningún texto: las claves
    assert.equal(t("js.reserva.red"), "js.reserva.red");
  } finally {
    fijarTextos({});
  }
});

// ---------------------------------------------------------------- red
test("cargarDiccionario: ../i18n/<idioma>.json relativo al módulo, con plazo; cualquier falla da un Map vacío", async () => {
  const pedidos = [];
  const f = async (url, op) => { pedidos.push({ url: String(url), op }); return respuesta({ "js.a": "A", "js.b": 3 }); };
  const d = await cargarDiccionario("en", { fetch: f, base: "https://sitio.test/js/i18n.js" });
  assert.deepEqual([...d], [["js.a", "A"]]);
  assert.equal(pedidos[0].url, "https://sitio.test/i18n/en.json");
  assert.ok(pedidos[0].op.signal, "con señal de plazo");
  assert.equal(pedidos[0].op.method, undefined);                    // GET
  // desde un módulo servido en /js/ la ruta es la misma para /, /en/ y /fr/tour/
  await cargarDiccionario("fr", { fetch: f, base: "https://sitio.test/js/i18n.js?v=2" });
  assert.equal(pedidos[1].url, "https://sitio.test/i18n/fr.json");
  // por defecto, relativo a src/js/i18n.js -> src/i18n/
  await cargarDiccionario("es", { fetch: f });
  assert.equal(pedidos[2].url, new URL("../src/i18n/es.json", import.meta.url).href);
  // idioma desconocido: no se pide nada (nada de rutas armadas con texto ajeno)
  for (const malo of ["de", "../secreto", "", null, "en/../../x"]) {
    assert.equal((await cargarDiccionario(malo, { fetch: f })).size, 0);
  }
  assert.equal(pedidos.length, 3);
  for (const falla of [
    async () => respuesta({ "js.a": "A" }, 404),
    async () => respuesta(["js.a", "A"]),
    async () => respuesta("texto"),
    async () => ({ ok: true, json: async () => { throw new SyntaxError("JSON inválido"); } }),
    async () => { throw new TypeError("Failed to fetch"); },
    async () => null,
  ]) {
    assert.equal((await cargarDiccionario("en", { fetch: falla })).size, 0);
  }
  assert.equal((await cargarDiccionario("en", { fetch: null })).size, 0);
});

test("cargarDiccionario: el plazo corta la conexión y la lectura del cuerpo", async () => {
  const esperarAborto = (signal) => new Promise((_, no) => {
    signal.addEventListener("abort", () => no(Object.assign(new Error("abortado"), { name: "AbortError" })));
  });
  const t0 = Date.now();
  assert.equal((await cargarDiccionario("en", { fetch: (_, { signal }) => esperarAborto(signal), tiempo: 30 })).size, 0);
  assert.equal((await cargarDiccionario("en", {
    fetch: async (_, { signal }) => ({ ok: true, json: () => esperarAborto(signal) }), tiempo: 30,
  })).size, 0);
  assert.ok(Date.now() - t0 < 2000);
});

test("en una página en inglés o francés: carga sólo su diccionario, y t() usa el español de textos-es.js como respaldo", async () => {
  const pedidos = [];
  const en = await enPagina("en", fetchDelDisco(pedidos));
  await en.listo;
  assert.equal(en.IDIOMA, "en");
  assert.equal(en.LOCALE, "en-US");
  assert.equal(pedidos.length, 1);
  assert.match(pedidos[0].url, /\/i18n\/en\.json$/);                  // ../i18n/ relativo al módulo; es.json, no
  assert.equal(en.t("js.reserva.fecha_pasada"), DICCIONARIOS.en["js.reserva.fecha_pasada"]);
  assert.equal(en.tn("js.reserva.noches", 1), "1 night");
  assert.equal(en.tn("js.reserva.noches", 3), "3 nights");
  assert.equal(en.t("js.no.existe"), "js.no.existe");

  const fr = await enPagina("fr-FR", async (url) => {
    // francés sin una clave: se usa la del español
    assert.match(String(url), /\/i18n\/fr\.json$/);
    const d = { ...DICCIONARIOS.fr };
    delete d["js.reserva.red"];
    return respuesta(d);
  });
  await fr.listo;
  assert.equal(fr.IDIOMA, "fr");
  assert.equal(fr.LOCALE, "fr-FR");
  assert.equal(fr.t("js.reserva.acepta"), DICCIONARIOS.fr["js.reserva.acepta"]);
  assert.equal(fr.t("js.reserva.red"), DICCIONARIOS.es["js.reserva.red"]);
  assert.equal(fr.tn("js.reserva.personas", 1), "1 personne");
});

test("hallazgo JS-2: la página en español no pide nada por la red y, con la red caída, se ve el español y no las claves", async () => {
  let llamadas = 0;
  const caidaEs = async () => { llamadas++; throw new TypeError("Failed to fetch"); };
  const es = await enPagina("es", caidaEs);
  // antes de `listo` y sin esperar nada: los textos ya están
  assert.equal(es.t("js.reserva.cal.elige_llegada"), "Elige la llegada");
  assert.equal(es.tn("js.reserva.noches", 3), "3 noches");
  assert.equal(es.t("js.reserva.envio.solicitar"), "Solicitar");
  assert.equal(es.t("js.reserva.red"), "No se pudo conectar con el servidor de reservas. Intenta de nuevo.");
  assert.equal(es.t("js.contenido.alt_generico"), "Foto del departamento");
  await es.listo;
  assert.equal(es.IDIOMA, "es");
  assert.equal(llamadas, 0, "en español no se pide ningún diccionario");

  // en inglés o francés con la red caída (o un 404, o un JSON inválido): el español, nunca las claves
  for (const [lang, falla] of [["en", caidaEs], ["fr", async () => respuesta({}, 404)],
    ["en", async () => ({ ok: true, json: async () => { throw new SyntaxError("JSON inválido"); } })]]) {
    const m = await enPagina(lang, falla);
    await m.listo;                                                      // se cumple aunque falle: nunca se rechaza
    assert.equal(m.IDIOMA, lang);
    for (const k of ["js.reserva.cal.elige_llegada", "js.reserva.envio.solicitar", "js.reserva.red", "js.contenido.alt_generico"]) {
      assert.equal(m.t(k), DICCIONARIOS.es[k], `${lang}: ${k}`);
    }
    assert.equal(m.tn("js.reserva.noches", 3), "3 noches");            // el plural del español
  }

  const otra = await enPagina("de", fetchDelDisco([]));   // idioma sin sitio: español
  assert.equal(otra.IDIOMA, "es");
  assert.equal(otra.LOCALE, "es-CL");
});

test("hallazgo JS-3: importar i18n.js no espera el diccionario; `listo` se cumple cuando llega y recién ahí cambia t()", async () => {
  let soltar;
  const colgado = new Promise((ok) => { soltar = ok; });
  const pedidos = [];
  // con await de nivel superior, esta importación no terminaría hasta soltar el diccionario
  const en = await Promise.race([
    enPagina("en", async (url) => { pedidos.push(String(url)); await colgado; return respuesta(DICCIONARIOS.en); }),
    new Promise((_, no) => setTimeout(() => no(new Error("importar i18n.js esperó al diccionario")), 1000)),
  ]);
  assert.equal(pedidos.length, 1);
  let cumplido = false;
  en.listo.then(() => { cumplido = true; });
  await new Promise((ok) => setTimeout(ok, 20));
  assert.equal(cumplido, false, "listo espera al diccionario");
  assert.equal(en.t("js.reserva.envio.solicitar"), "Solicitar");        // mientras tanto, el español
  soltar();
  await en.listo;
  assert.equal(en.t("js.reserva.envio.solicitar"), DICCIONARIOS.en["js.reserva.envio.solicitar"]);
  assert.notEqual(DICCIONARIOS.en["js.reserva.envio.solicitar"], "Solicitar");
});

test("textos-es.js: exactamente las claves js.* de es.json, en su orden (es el respaldo sin red de i18n.js)", () => {
  const deEs = Object.fromEntries(Object.entries(DICCIONARIOS.es).filter(([k]) => k.startsWith("js.")));
  assert.deepEqual(Object.keys(TEXTOS_ES), Object.keys(deEs),
    "textos-es.js desfasado de es.json: regenéralo con  python3 web/build.py --textos-es");
  assert.deepEqual(TEXTOS_ES, deEs, "textos-es.js desfasado de es.json: regenéralo con  python3 web/build.py --textos-es");
  assert.deepEqual([...RESPALDO_ES], Object.entries(deEs));
  assert.match(sinComentarios(leer("../src/js/i18n.js")), /^import TEXTOS_ES from "\.\/textos-es\.js";$/m,
    "import estático: el español llega con el JS");
});

// ---------------------------------------------------------------- diccionarios
const variables = (texto) => [...texto.matchAll(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g)].map((m) => m[1]).sort();
const deJs = (d) => Object.keys(d).filter((k) => k.startsWith("js.")).sort();

test("diccionarios: JSON plano de textos no vacíos, las mismas claves js.* en es, en y fr y las mismas variables", () => {
  for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
    assert.equal(Object.getPrototypeOf(d), Object.prototype, idioma);
    for (const [k, v] of Object.entries(d)) {
      assert.equal(typeof v, "string", `${idioma}: ${k} no es texto`);
      assert.ok(v.trim(), `${idioma}: ${k} vacío`);
      assert.equal(v, v.trim(), `${idioma}: ${k} con espacios en los bordes`);
    }
  }
  const claves = deJs(DICCIONARIOS.es);
  assert.ok(claves.length >= 40);
  assert.deepEqual(deJs(DICCIONARIOS.en), claves, "en.json: faltan o sobran claves js.*");
  assert.deepEqual(deJs(DICCIONARIOS.fr), claves, "fr.json: faltan o sobran claves js.*");
  for (const k of claves) {
    for (const idioma of ["en", "fr"]) {
      assert.deepEqual(variables(DICCIONARIOS[idioma][k]), variables(DICCIONARIOS.es[k]), `${idioma}: variables de ${k}`);
    }
  }
});

test("diccionarios: los plurales tienen .one y .other en los tres idiomas, con {n}", () => {
  const bases = new Set(Object.keys(DICCIONARIOS.es).filter((k) => /\.(one|other)$/.test(k)).map((k) => k.replace(/\.(one|other)$/, "")));
  assert.ok(bases.has("js.reserva.noches") && bases.has("js.reserva.personas"));
  for (const base of bases) {
    for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
      for (const cat of ["one", "other"]) assert.match(d[`${base}.${cat}`] ?? "", /\{n\}/, `${idioma}: ${base}.${cat}`);
    }
  }
});

test("toda clave literal que usa el JS del sitio (t/tn) existe en es.json, en.json y fr.json", () => {
  const carpeta = new URL("../src/js/", import.meta.url);
  const usadas = [], plurales = [];
  for (const archivo of readdirSync(carpeta).filter((a) => a.endsWith(".js"))) {
    // sin comentarios: ahí se citan claves de ejemplo como js.reserva.<código>
    const fuente = sinComentarios(readFileSync(new URL(archivo, carpeta), "utf8"));
    for (const [, k] of fuente.matchAll(/\bt\(\s*"(js\.[^"]+)"/g)) usadas.push([archivo, k]);
    for (const [, k] of fuente.matchAll(/\btn\(\s*"(js\.[^"]+)"/g)) plurales.push([archivo, k]);
  }
  assert.ok(usadas.some(([a]) => a === "reserva.js") && usadas.some(([a]) => a === "contenido-publico.js"));
  assert.ok(plurales.length > 0);
  for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
    for (const [archivo, k] of usadas) assert.ok(Object.hasOwn(d, k), `${idioma}.json no tiene ${k} (${archivo})`);
    for (const [archivo, k] of plurales) {
      for (const cat of ["one", "other"]) assert.ok(Object.hasOwn(d, `${k}.${cat}`), `${idioma}.json no tiene ${k}.${cat} (${archivo})`);
    }
  }
});

test("diccionarios: cada idioma está traducido (no es una copia del español) y sin marcado HTML en los textos del JS", () => {
  const claves = deJs(DICCIONARIOS.es);
  for (const idioma of ["en", "fr"]) {
    const iguales = claves.filter((k) => DICCIONARIOS[idioma][k] === DICCIONARIOS.es[k]);
    // sólo pueden coincidir los que no tienen palabras (p. ej. «{entrada} → {salida} · {noches}»)
    for (const k of iguales) assert.doesNotMatch(DICCIONARIOS.es[k].replace(/\{\w+\}/g, ""), /[A-Za-zÀ-ÿ]{2,}/, `${idioma}: ${k} sin traducir`);
  }
  for (const d of Object.values(DICCIONARIOS)) for (const k of claves) assert.doesNotMatch(d[k], /[<>]/, k);
});
