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

import { conGlobales, copiaDelSitio } from "./copia-sitio.mjs";

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
    document.elegir("auxclick", "fr", 2);                   // botón derecho: no elige
    assert.match(document.cookie, /^nf_lang=en;/);
    document.elegir("auxclick", "fr", 1);                   // clic central: sí
    assert.match(document.cookie, /^nf_lang=fr;/);
  });
});

// ---------------------------------------------------------------- diccionarios
const claves = Object.keys(DICCIONARIOS.es);

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
  const iguales = { en: new Set(["privacidad.cookies", "reserva.campo.mensaje", "tour.ayuda.teclas", "tour.ayuda.esc",
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

test("francés: espacio fino antes de «:», «?», «;» y «!», y dentro de las comillas francesas", () => {
  for (const [k, v] of Object.entries(DICCIONARIOS.fr)) {
    if (k.startsWith("js.reserva.") || k.startsWith("js.contenido.")) continue;   // textos de otra sesión
    assert.doesNotMatch(v, /[^\s  ][:?;!](\s|$)/u, `fr: ${k}: «${v}»`);
    assert.doesNotMatch(v, /«(?! )|(?<! )»/u, `fr: ${k}: «${v}»`);
  }
});
