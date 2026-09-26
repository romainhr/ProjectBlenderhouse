// Selector de idioma y textos de las páginas públicas en español, inglés y francés (ADR 0007):
//   cd web && npm test
// - cada página pública y el tour traen el selector (<a data-i18n-alternar> es, en y fr);
// - sitio.js guarda la cookie nf_lang al elegir y escribe los precios de ejemplo con el formato del idioma;
// - los diccionarios respetan las reglas del contenido: «Project-roomVR» sin traducir, «ejemplo» conservado, nunca
//   «loft», sin marcado HTML y nada sin traducir en inglés ni en francés.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { conGlobales, copiaDelSitio, sinComentarios } from "./copia-sitio.mjs";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));
const leer = (ruta) => readFileSync(join(SRC, ruta), "utf8");
const PAGINAS = ["index.html", "reserva.html", "privacidad.html", "404.html", "tour/index.html"];
const DICCIONARIOS = Object.fromEntries(["es", "en", "fr"].map((i) => [i, JSON.parse(leer(`i18n/${i}.json`))]));
const { nombre: MARCA } = JSON.parse(leer("marca.json"));

test("cada página pública y el tour traen el selector con es, en y fr, y cada grupo los tres en ese orden", () => {
  for (const p of PAGINAS) {
    const html = leer(p);
    const grupos = [...html.matchAll(/(<(nav|div) class="idiomas[^"]*"[^>]*>)([\s\S]*?)<\/\2>/g)];
    assert.ok(grupos.length >= 1, `${p}: sin selector de idioma`);
    for (const [, etiqueta, , cuerpo] of grupos) {
      assert.match(etiqueta, /data-i18n-attr="aria-label:[a-z_.]+\.idioma"/, `${p}: el grupo no tiene nombre traducible`);
      const idiomas = [...cuerpo.matchAll(/<a data-i18n-alternar="([a-z]+)"/g)].map((m) => m[1]);
      assert.deepEqual(idiomas, ["es", "en", "fr"], p);
    }
    // cada enlace nombra su idioma en ese idioma (el build le pone lang) y no trae href: lo pone el build
    for (const [a] of html.matchAll(/<a data-i18n-alternar[^>]*>/g)) assert.doesNotMatch(a, /\shref=/, `${p}: ${a}`);
    for (const n of ["Español", "English", "Français"]) assert.ok(html.includes(`<span class="visually-hidden">${n}</span>`), `${p}: ${n}`);
  }
  // el 404 no carga sitio.js desde otra página: la ruta es absoluta (Netlify lo sirve en cualquier ruta)
  assert.match(leer("404.html"), /<script type="module" src="\/js\/sitio\.js"><\/script>/);
});

test("las páginas públicas no traen comentarios HTML: el build los copiaría en español a /en/ y /fr/", () => {
  // las notas van en el CSS o en el JS, que no se publican por idioma
  for (const p of PAGINAS) assert.doesNotMatch(leer(p), /<!--/, p);
});

// sitio.js con un DOM mínimo: sin IntersectionObserver, sin hero ni carruseles; sólo precios, año y el selector.
function paginaFalsa(lang) {
  const oyentes = {};
  const precios = ["noche", "limpieza"].map((precio) => ({ dataset: { precio }, textContent: "" }));
  const document = {
    documentElement: { lang, classList: { add() {} } },
    cookie: "",
    querySelector: () => null,
    querySelectorAll: (sel) => (sel === "[data-precio]" ? precios : []),
    addEventListener: (tipo, fn) => { (oyentes[tipo] ??= []).push(fn); },
    elegir(tipo, idioma, button = 0) {
      const enlace = { getAttribute: (n) => (n === "data-i18n-alternar" ? idioma : null) };
      const target = { closest: (sel) => (sel === "a[data-i18n-alternar]" ? enlace : null) };
      for (const fn of oyentes[tipo] || []) fn({ type: tipo, target, button });
    },
  };
  return { document, precios };
}

/** Carga una copia nueva de sitio.js en una página falsa con <html lang="`lang`"> y corre `fn(pagina)` mientras esa
 *  página es el `document` global (los manejadores de sitio.js escriben en document.cookie). */
async function sitioEn(lang, fn = () => {}) {
  const copia = copiaDelSitio(["sitio.js", "reserva-logica.js", "idioma.js"]);
  const pagina = paginaFalsa(lang);
  const antes = { window: globalThis.window, matchMedia: globalThis.matchMedia, tenia: "window" in globalThis };
  globalThis.window = {};                                   // sin IntersectionObserver
  globalThis.matchMedia = () => ({ matches: true });
  try {
    return await conGlobales({ document: pagina.document, fetch: undefined }, async () => {
      await import(copia.url("js/sitio.js"));
      await fn(pagina);
      return pagina;
    });
  } finally {
    if (antes.tenia) globalThis.window = antes.window; else delete globalThis.window;
    globalThis.matchMedia = antes.matchMedia;
  }
}

test("sitio.js: precios de ejemplo con el formato del idioma de la página", async () => {
  const esperados = { es: ["CLP 58.000", "CLP 15.000"], en: ["CLP 58,000", "CLP 15,000"] };
  for (const [lang, [noche, limpieza]] of Object.entries(esperados)) {
    const { precios } = await sitioEn(lang);
    assert.equal(precios[0].textContent, noche, lang);
    assert.equal(precios[1].textContent, limpieza, lang);
  }
  const { precios } = await sitioEn("fr");                  // fr-FR separa los miles con un espacio fino
  assert.match(precios[0].textContent, /^CLP 58\s000$/u);
});

test("sitio.js: elegir un idioma guarda nf_lang (un año, todo el sitio, Lax y Secure) antes de navegar", async () => {
  await sitioEn("es", ({ document }) => {
    document.elegir("click", "en");
    assert.equal(document.cookie, "nf_lang=en; path=/; max-age=31536000; SameSite=Lax; Secure");
    document.elegir("click", "xx");                         // fuera de la lista: no cambia
    assert.match(document.cookie, /^nf_lang=en;/);
    document.elegir("auxclick", "fr", 2);                   // botón derecho: no elige por auxclick…
    assert.match(document.cookie, /^nf_lang=en;/);
    document.elegir("auxclick", "fr", 1);                   // clic central: sí
    assert.match(document.cookie, /^nf_lang=fr;/);
  });
});

test("sitio.js: abrir el selector en una pestaña nueva desde el menú contextual también guarda nf_lang", async () => {
  // clic derecho -> «Abrir en una pestaña nueva», pulsación larga en el teléfono o la tecla de menú: sin la cookie, la
  // pestaña nueva llegaba a / y la regla Language=en la mandaba de vuelta a /en/
  await sitioEn("en", ({ document }) => {
    document.elegir("contextmenu", "es", 2);
    assert.equal(document.cookie, "nf_lang=es; path=/; max-age=31536000; SameSite=Lax; Secure");
    document.elegir("contextmenu", "xx", 2);                // fuera de la lista: no cambia
    assert.match(document.cookie, /^nf_lang=es;/);
  });
});

test("cookie del idioma: se arma sólo en idioma.js (recordarIdioma); sitio.js y el tour la usan desde ahí", async () => {
  const idioma = await import("../src/js/idioma.js");
  const i18n = await import("../src/js/i18n.js");
  assert.equal(idioma.cookieIdioma("fr"), "nf_lang=fr; path=/; max-age=31536000; SameSite=Lax; Secure");
  for (const malo of ["de", "", "en; path=/admin", "EN", undefined, null, 1]) assert.equal(idioma.cookieIdioma(malo), null, String(malo));
  const doc = { cookie: "" };
  assert.equal(idioma.recordarIdioma("en", doc), true);
  assert.equal(doc.cookie, "nf_lang=en; path=/; max-age=31536000; SameSite=Lax; Secure");
  assert.equal(idioma.recordarIdioma("de", doc), false);   // un código fuera de la lista no toca la cookie
  assert.match(doc.cookie, /^nf_lang=en;/);
  assert.equal(idioma.recordarIdioma("es", undefined), false);   // sin document (Node) no falla
  assert.deepEqual([...idioma.EVENTOS_SELECTOR_IDIOMA], ["click", "auxclick", "contextmenu"]);
  // i18n.js reexporta las mismas funciones (no copias), como el resto de idioma.js
  for (const nombre of ["cookieIdioma", "recordarIdioma", "escucharSelectorIdioma", "EVENTOS_SELECTOR_IDIOMA", "MAX_EDAD_IDIOMA_S"]) {
    assert.equal(i18n[nombre], idioma[nombre], nombre);
  }
  // ni sitio.js ni el tour arman la cookie ni escriben document.cookie por su cuenta
  for (const archivo of ["js/sitio.js", "tour/js/interfaz.js", "tour/js/main.js"]) {
    const fuente = sinComentarios(leer(archivo));
    assert.doesNotMatch(fuente, /nf_lang|\.cookie\b|max-age/, archivo);
    assert.match(fuente, /escucharSelectorIdioma|iniciarSelectorIdioma/, archivo);
  }
});

// ---------------------------------------------------------------- diccionarios
const claves = Object.keys(DICCIONARIOS.es);
// «:», «?», «;» o «!» ante un espacio o el final, sin U+00A0 ni U+202F antes (el francés los separa con un espacio duro)
const SIN_ESPACIO_DURO = /(?<![\u00a0\u202f])[:?;!](?=\s|$)/u;

test("diccionarios: «Project-roomVR» nunca se traduce y los títulos de página lo llevan en los tres idiomas", () => {
  for (const k of claves) {
    if (!DICCIONARIOS.es[k].includes(MARCA)) continue;
    for (const idioma of ["en", "fr"]) assert.ok(DICCIONARIOS[idioma][k].includes(MARCA), `${idioma}: ${k}`);
  }
  for (const k of ["inicio.titulo", "reserva.titulo", "privacidad.titulo", "no_encontrada.titulo", "tour.titulo"]) {
    for (const [idioma, d] of Object.entries(DICCIONARIOS)) assert.ok(d[k].includes(MARCA), `${idioma}: ${k}`);
  }
});

test("diccionarios: donde el español dice «ejemplo», el inglés dice «example» y el francés «exemple»", () => {
  const conEjemplo = claves.filter((k) => /ejemplo/i.test(DICCIONARIOS.es[k]) && !k.endsWith(".ejemplo"));
  assert.ok(conEjemplo.length >= 10, "¿se perdieron las marcas de ejemplo?");
  for (const k of conEjemplo) {
    assert.match(DICCIONARIOS.en[k], /example/i, `en: ${k}`);
    assert.match(DICCIONARIOS.fr[k], /exemple/i, `fr: ${k}`);
  }
});

test("francés: «à titre d'exemple» o «(exemple)», nunca «d'exemple» como adjetivo («tarifs d'exemple» es un calco)", () => {
  for (const [k, v] of Object.entries(DICCIONARIOS.fr)) {
    if (k.startsWith("js.reserva.") || k.startsWith("js.contenido.")) continue;   // textos de otra sesión
    assert.doesNotMatch(v, /(?<!à titre )d['’]exemple/u, `fr: ${k}: «${v}»`);
  }
});

test("diccionarios: sin «loft», sin marcado HTML y con las mismas claves en los tres idiomas", () => {
  for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
    assert.deepEqual(Object.keys(d).sort(), [...claves].sort(), `${idioma}.json: faltan o sobran claves`);
    for (const [k, v] of Object.entries(d)) {
      assert.doesNotMatch(v, /loft/i, `${idioma}: ${k}`);
      assert.doesNotMatch(v, /[<>]/, `${idioma}: ${k}`);
    }
  }
});

test("diccionarios: los textos de las páginas están traducidos (salvo nombres propios, cifras y siglas)", () => {
  // iguales al español a propósito: el mismo término en ese idioma (p. ej. «Cookies», «Disponible», «Joystick»)
  const iguales = { en: new Set(["privacidad.cookies", "reserva.campo.mensaje", "tour.ayuda.esc",
    "inicio.equipo.closets", "no_encontrada.etiqueta"]),
    fr: new Set(["privacidad.cookies", "reserva.campo.mensaje", "reserva.leyenda.disponible", "reserva.fechas",
      "comun.nav.principal", "comun.nav.menu", "comun.menu.preguntas", "tour.ayuda.palanca"]) };
  for (const idioma of ["en", "fr"]) {
    const d = DICCIONARIOS[idioma];
    const copiados = claves.filter((k) => d[k] === DICCIONARIOS.es[k]
      && /[A-Za-zÀ-ÿ]{3,}/.test(d[k].replace(MARCA, "").replace(/\{\w+\}/g, "")));
    assert.deepEqual(copiados.filter((k) => !iguales[idioma].has(k)), [], `${idioma}: textos iguales al español`);
  }
});

test("francés: espacio duro antes de «:», «?», «;» y «!», y dentro de las comillas francesas", () => {
  // U+00A0 o U+202F, nunca el espacio común: con él, el signo puede quedar solo al comienzo de una línea (medido en
  // /fr/reserva.html: «: nous vous…» a 312 y a 482 px). La versión anterior aceptaba el espacio común, porque \s lo
  // incluye.
  for (const [k, v] of Object.entries(DICCIONARIOS.fr)) {
    if (k.startsWith("js.reserva.") || k.startsWith("js.contenido.")) continue;   // textos de otra sesión
    assert.doesNotMatch(v, SIN_ESPACIO_DURO, `fr: ${k}: «${v}»`);
    assert.doesNotMatch(v, /«(?![\u00a0\u202f])|(?<![\u00a0\u202f])»/u, `fr: ${k}: «${v}»`);
  }
});

test("la prueba del espacio duro en francés detecta el espacio común y la falta de espacio antes de «:»", () => {
  assert.match("Sans paiement en ligne : nous", SIN_ESPACIO_DURO);
  assert.match("Sans paiement en ligne: nous", SIN_ESPACIO_DURO);
  assert.match("Des questions ?", SIN_ESPACIO_DURO);
  assert.doesNotMatch("Sans paiement en ligne\u00a0: nous", SIN_ESPACIO_DURO);
  assert.doesNotMatch("Des questions\u202f?", SIN_ESPACIO_DURO);
  assert.doesNotMatch("https://ejemplo", SIN_ESPACIO_DURO);
});

test("inglés y francés: las teclas (W A S D, Z Q S D) van con espacios duros y no se cortan entre líneas", () => {
  for (const idioma of ["en", "fr"]) {
    for (const [k, v] of Object.entries(DICCIONARIOS[idioma])) {
      assert.doesNotMatch(v, /\b[WZ] [AQ]\b|\b[AQ] S\b|\bS D\b/u, `${idioma}: ${k}: «${v}»`);
    }
  }
});

test("francés: sin los calcos que encontró la revisión", () => {
  const calcos = [
    [/glisser le reste de l['’]écran/u, "se desliza el dedo sobre la pantalla, no la pantalla"],
    [/\bCeci est un site/u, "«Il s'agit d'un site…»"],
    [/\bservies depuis\b/u, "«hébergées sur…»"],
  ];
  for (const [k, v] of Object.entries(DICCIONARIOS.fr)) {
    for (const [re, motivo] of calcos) assert.doesNotMatch(v, re, `fr: ${k}: «${v}» (${motivo})`);
  }
  // «Séjour» es el living: la duración de la estadía, en la misma página, no se llama igual
  assert.notEqual(DICCIONARIOS.fr["inicio.tarifas.estadia"], DICCIONARIOS.fr["espacio.living.titulo"]);
  // nombre del landmark: «Menu principal, navigation», no el adjetivo solo
  assert.equal(DICCIONARIOS.fr["comun.nav.principal"], "Menu principal");
});

test("inglés: el ventanal del living se llama siempre «sliding glass door»", () => {
  for (const [k, v] of Object.entries(DICCIONARIOS.en)) assert.doesNotMatch(v, /sliding door/u, `en: ${k}: «${v}»`);
});

test("reserva: el botón de envío dice lo mismo en el HTML y cuando reserva.js lo reescribe tras un error", () => {
  // reserva.html trae reserva.solicitar; reserva.js le vuelve a poner js.reserva.envio.solicitar después de un error
  for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
    assert.equal(d["reserva.solicitar"], d["js.reserva.envio.solicitar"], idioma);
  }
  for (const id of ["enviar", "enviar-movil"]) {
    assert.match(leer("reserva.html"), new RegExp(`<button[^>]*id="${id}"[^>]*data-i18n="reserva\\.solicitar"`), id);
  }
});

test("precios de ejemplo sin JS: el texto de respaldo en cada idioma es el mismo que escribe sitio.js", async () => {
  const { TARIFA, clp } = await import("../src/js/reserva-logica.js");
  const { localeDe } = await import("../src/js/idioma.js");
  const marcas = [...leer("index.html").matchAll(/<span[^>]*data-precio="([a-z]+)"[^>]*>/g)];
  assert.ok(marcas.length >= 3, "¿se perdieron los precios de ejemplo?");
  for (const [span, precio] of marcas) {
    assert.match(span, new RegExp(`data-i18n="comun\\.precio\\.${precio}"`), span);
    for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
      assert.equal(d[`comun.precio.${precio}`], clp(TARIFA[precio], localeDe(idioma)), `${idioma}: ${precio}`);
    }
  }
});
