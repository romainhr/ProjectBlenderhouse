// Pruebas de web/src/js/contenido-publico.js con el ejecutor incluido en Node (sin dependencias ni DOM real):
//   cd web && npm test     (node --test tests/*.test.mjs)
// El DOM se imita con objetos mínimos (querySelectorAll, atributos, textContent, eventos); innerHTML lanza un error
// para comprobar que el módulo nunca lo usa. La red se imita con un fetch falso.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { TARIFA, clp, fijarTarifas, tarifaVigente, total } from "../src/js/reserva-logica.js";
import { IDIOMA, LOCALE, fijarTextos } from "../src/js/i18n.js";
import {
  BUCKET_FOTOS, CAMPOS_VALOR, CLAVES_TARIFA, CLAVE_ALT_GENERICO, MAX_MINIATURAS, RUTA_CONTENIDO, RUTA_FOTOS,
  altGenerico, aplicar, aplicarContenido, aplicarFotos, cabecerasPublicas, indexarContenido, indexarFotos, leerFilas,
  obtenerDatos, precioValido, rutaValida, tarifas, tarifasDe, textoContenido, urlFotoValida, urlPublica,
} from "../src/js/contenido-publico.js";
import { MODULOS_I18N, conGlobales, copiaDelSitio, hasta } from "./copia-sitio.mjs";

const BASE = "https://abcdefghijklmnopqrst.supabase.co";            // ficticia: estas pruebas no usan la red
const OTRO = "https://zyxwvutsrqponmlkjihg.supabase.co";            // otro proyecto, también ficticio
const PUB = `${BASE}/storage/v1/object/public/${BUCKET_FOTOS}`;
const leer = (ruta) => readFileSync(new URL(ruta, import.meta.url), "utf8");
// Textos del módulo (alt de respaldo, etiquetas de las miniaturas): en Node no hay document y i18n.js no carga nada;
// se fijan los de es.json, los de una página en español.
const DICCIONARIOS = Object.fromEntries(["es", "en", "fr"].map((i) => [i, JSON.parse(leer(`../src/i18n/${i}.json`))]));
fijarTextos(DICCIONARIOS.es);
const ALT_GENERICO = DICCIONARIOS.es[CLAVE_ALT_GENERICO];

// ---------------------------------------------------------------- DOM falso
class Nodo {
  constructor(etiqueta, atributos = {}, hijos = []) {
    this.tagName = etiqueta.toUpperCase();
    this.atributos = new Map(Object.entries(atributos));
    this.children = [];
    this.parentElement = null;
    this.texto = "";
    this.oyentes = {};
    this.append(...hijos);
  }
  get textContent() { return this.texto + this.children.map((c) => c.textContent).join(""); }
  set textContent(v) { for (const c of [...this.children]) c.remove(); this.texto = String(v); }
  set innerHTML(_) { throw new Error("innerHTML prohibido"); }
  get className() { return this.getAttribute("class") ?? ""; }
  set className(v) { this.setAttribute("class", v); }
  getAttribute(n) { return this.atributos.has(n) ? this.atributos.get(n) : null; }
  setAttribute(n, v) { this.atributos.set(n, String(v)); }
  removeAttribute(n) { this.atributos.delete(n); }
  hasAttribute(n) { return this.atributos.has(n); }
  append(...nodos) {
    for (const n of nodos) { n.remove(); n.parentElement = this; this.children.push(n); }
  }
  insertBefore(n, ref) {
    n.remove();
    const i = this.children.indexOf(ref);
    n.parentElement = this;
    this.children.splice(i < 0 ? this.children.length : i, 0, n);
    return n;
  }
  after(n) {
    const p = this.parentElement;
    n.remove();
    n.parentElement = p;
    p.children.splice(p.children.indexOf(this) + 1, 0, n);
  }
  remove() {
    const p = this.parentElement;
    if (!p) return;
    p.children.splice(p.children.indexOf(this), 1);
    this.parentElement = null;
  }
  addEventListener(tipo, fn) { (this.oyentes[tipo] ??= []).push(fn); }
  emitir(tipo) { for (const fn of this.oyentes[tipo] ?? []) fn({ type: tipo, target: this }); }
  *descendientes() { for (const c of this.children) { yield c; yield* c.descendientes(); } }
  querySelectorAll(sel) {
    // sólo lo que usa el módulo: «[atributo]» o una etiqueta
    const ok = sel.startsWith("[") ? (el) => el.hasAttribute(sel.slice(1, -1)) : (el) => el.tagName === sel.toUpperCase();
    return [...this.descendientes()].filter(ok);
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] ?? null; }
}

class Documento extends Nodo {
  constructor(hijos) { super("#document", {}, hijos); }
  createElement(etiqueta) { return new Nodo(etiqueta); }
}

const n = (etiqueta, atributos, ...hijos) => new Nodo(etiqueta, atributos, hijos);
const conTexto = (nodo, texto) => { nodo.texto = texto; return nodo; };

/** Un <figure data-fotos> como los de index.html: <picture> con un <source> WebP y el <img> estático. */
function figura(espacio, extra = {}, extraImg = {}) {
  const source = n("source", { type: "image/webp", srcset: "img/x-800.webp 800w, img/x-1600.webp 1600w", sizes: "100vw" });
  const img = n("img", { src: "img/x-800.jpg", alt: "Render estático", loading: "lazy", width: "800", height: "500",
    class: "foto redondeada", ...extraImg });
  const picture = n("picture", {}, source, img);
  const caption = conTexto(n("figcaption", {}), "Pie");
  const fig = n("figure", { "data-fotos": espacio, ...extra }, picture, caption);
  return { fig, picture, source, img, caption };
}

/** Cuenta setAttribute y removeAttribute sobre los nodos dados. */
function espiar(...nodos) {
  let cambios = 0;
  for (const nodo of nodos) {
    for (const m of ["setAttribute", "removeAttribute"]) {
      const original = nodo[m].bind(nodo);
      nodo[m] = (...a) => { cambios++; return original(...a); };
    }
  }
  return () => cambios;
}

// Filas de la semilla de web/supabase/migrations/0003_gestion.sql, escritas tal cual (sin CLAVES_TARIFA): si alguien
// cambia el nombre de las claves en un lado y no en el otro, estas pruebas fallan.
const SEMILLA_0003 = [
  { clave: "tarifa.noche", valor: "58000", tipo: "precio" },
  { clave: "tarifa.limpieza", valor: "15000", tipo: "precio" },
];

// ---------------------------------------------------------------- lógica pura
test("indexarContenido: acepta filas bien formadas y descarta el resto", () => {
  const m = indexarContenido([
    { clave: "titulo", valor: "Departamento nuevo", tipo: "texto", valor_en: null, valor_fr: null },
    { clave: "tarifa.noche", valor: "65000", tipo: "precio" },
    { clave: "huespedes", valor: 4 },                          // número y sin tipo -> texto
    { clave: "Mayus", valor: "x", tipo: "texto" },             // clave inválida
    { clave: "nulo", valor: null, tipo: "texto" },
    { clave: "objeto", valor: { a: 1 }, tipo: "texto" },
    null,
    "basura",
  ]);
  assert.deepEqual([...m.keys()], ["titulo", "tarifa.noche", "huespedes"]);
  assert.deepEqual(m.get("huespedes"), { valor: 4, tipo: "texto" });
  assert.deepEqual(m.get("titulo"), { valor: "Departamento nuevo", tipo: "texto" });   // traducciones null: no van
  assert.equal(indexarContenido(null).size, 0);
  assert.equal(indexarContenido({ message: "relation does not exist" }).size, 0);
});

test("textos del módulo desde es.json: alt de respaldo (el de antes) y claves en los tres idiomas", () => {
  assert.equal(ALT_GENERICO, "Foto del departamento");
  assert.equal(altGenerico(), ALT_GENERICO);
  for (const clave of [CLAVE_ALT_GENERICO, "js.contenido.mas_fotos", "js.contenido.ver_foto"]) {
    for (const [idioma, d] of Object.entries(DICCIONARIOS)) assert.ok(d[clave]?.trim(), `${idioma}.json sin ${clave}`);
  }
  // el alt de respaldo no se fija al leer la base (indexarFotos deja ""), sino al aplicar: sale en el idioma que tenga
  // t() en ese momento, aunque las lecturas hayan llegado antes que el diccionario (hallazgo JS-3)
  const m = indexarFotos([{ espacio: "living", ruta: "living/a.jpg", alt: "", orden: 1 }], BASE);
  assert.equal(m.get("living")[0].alt, "");
  try {
    fijarTextos(DICCIONARIOS.en, DICCIONARIOS.es);
    assert.equal(altGenerico(), "Photo of the apartment");
    const f = figura("living");
    aplicarFotos(new Documento([f.fig]), m, { base: BASE });
    assert.equal(f.img.getAttribute("alt"), "Photo of the apartment");
  } finally {
    fijarTextos(DICCIONARIOS.es);
  }
});

test("precioValido y textoContenido: CLP entero, formato es-CL y vacíos que dejan el estático", () => {
  assert.equal(precioValido("65000"), 65000);
  assert.equal(precioValido(" 65000 "), 65000);
  assert.equal(precioValido(65000), 65000);
  // el mismo rango que el CHECK contenido_precio_entero de la 0003: de 0 a 10 000 000
  assert.equal(precioValido("0"), 0);
  assert.equal(precioValido(0), 0);
  assert.equal(precioValido("10000000"), 10_000_000);
  assert.equal(textoContenido({ valor: "0", tipo: "precio" }), clp(0));
  for (const malo of ["65.000", "65,5", "-1", -1, "10000001", 10_000_001, 1.5, 1e8, "abc", "", null, undefined, NaN]) {
    assert.equal(precioValido(malo), null, `debería rechazar ${String(malo)}`);
  }
  assert.equal(textoContenido({ valor: "65000", tipo: "precio" }), clp(65000));
  assert.match(textoContenido({ valor: "65000", tipo: "precio" }), /^CLP 65\.000$/);
  assert.equal(textoContenido({ valor: "65.000", tipo: "precio" }), null);
  assert.equal(textoContenido({ valor: "Hola", tipo: "texto" }), "Hola");
  assert.equal(textoContenido({ valor: "Línea 1\nLínea 2", tipo: "otro" }), "Línea 1\nLínea 2");
  assert.equal(textoContenido({ valor: 4, tipo: "texto" }), "4");
  assert.equal(textoContenido({ valor: "   ", tipo: "texto" }), null);
  assert.equal(textoContenido(undefined), null);
});

test("tarifasDe: las dos editadas, una sola (la otra de ejemplo) o ninguna", () => {
  const c = (filas) => indexarContenido(filas);
  assert.deepEqual(tarifasDe(c([
    { clave: CLAVES_TARIFA.noche, valor: "70000", tipo: "precio" },
    { clave: CLAVES_TARIFA.limpieza, valor: "20000", tipo: "precio" },
  ])), { noche: 70000, limpieza: 20000 });
  assert.deepEqual(tarifasDe(c([{ clave: CLAVES_TARIFA.noche, valor: "70000", tipo: "precio" }])),
    { noche: 70000, limpieza: TARIFA.limpieza });
  assert.equal(tarifasDe(c([{ clave: CLAVES_TARIFA.noche, valor: "setenta", tipo: "precio" }])), null);
  // limpieza sin cobro: 0 es válido y llega tal cual (antes se descartaba y se sumaban 15 000 de más)
  assert.deepEqual(tarifasDe(c([
    { clave: CLAVES_TARIFA.noche, valor: "70000", tipo: "precio" },
    { clave: CLAVES_TARIFA.limpieza, valor: "0", tipo: "precio" },
  ])), { noche: 70000, limpieza: 0 });
  // noche en 0: no hay estadía gratis, se trata como no editada y queda la de ejemplo
  assert.deepEqual(tarifasDe(c([
    { clave: CLAVES_TARIFA.noche, valor: "0", tipo: "precio" },
    { clave: CLAVES_TARIFA.limpieza, valor: "20000", tipo: "precio" },
  ])), { noche: TARIFA.noche, limpieza: 20000 });
  assert.equal(tarifasDe(c([{ clave: CLAVES_TARIFA.noche, valor: "0", tipo: "precio" }])), null);
  assert.equal(tarifasDe(c([{ clave: "titulo", valor: "x", tipo: "texto" }])), null);
  assert.equal(tarifasDe(new Map()), null);
  assert.equal(tarifasDe(null), null);
});

test("tarifas: las claves son las de la semilla de 0003_gestion.sql y los data-precio de index.html", () => {
  assert.deepEqual(CLAVES_TARIFA, { noche: "tarifa.noche", limpieza: "tarifa.limpieza" });
  // filas de la semilla sin editar: son las de ejemplo de TARIFA
  assert.deepEqual(tarifasDe(indexarContenido(SEMILLA_0003)), { noche: 58000, limpieza: 15000 });
  assert.deepEqual({ noche: TARIFA.noche, limpieza: TARIFA.limpieza }, { noche: 58000, limpieza: 15000 });
  // las mismas filas editadas desde el portal
  const editadas = indexarContenido([
    { clave: "tarifa.noche", valor: "70000", tipo: "precio" },
    { clave: "tarifa.limpieza", valor: "20000", tipo: "precio" },
  ]);
  assert.deepEqual(tarifasDe(editadas), { noche: 70000, limpieza: 20000 });
  const pNoche = conTexto(n("td", { "data-precio": "noche" }), clp(TARIFA.noche));
  const pLimpieza = conTexto(n("td", { "data-precio": "limpieza" }), clp(TARIFA.limpieza));
  assert.equal(aplicarContenido(new Documento([pNoche, pLimpieza]), editadas), 2);
  assert.deepEqual([pNoche.textContent, pLimpieza.textContent], [clp(70000), clp(20000)]);

  // la migración siembra exactamente esas claves de tipo precio, con los valores de TARIFA
  const sql = leer("../supabase/migrations/0003_gestion.sql");
  const semilla = /insert into public\.contenido\b[\s\S]*?on conflict \(clave\) do nothing/.exec(sql)?.[0] ?? "";
  assert.ok(semilla, "no se encontró la semilla de public.contenido en la 0003");
  const sembradas = Object.fromEntries([...semilla.matchAll(/\('([a-z0-9][a-z0-9_.-]+)',\s*'([^']*)',\s*'precio'/g)]
    .map((m) => [m[1], m[2]]));
  assert.deepEqual(sembradas, Object.fromEntries(SEMILLA_0003.map((f) => [f.clave, f.valor])));
  // y cada data-precio de index.html tiene su clave
  const usados = [...leer("../src/index.html").matchAll(/data-precio="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(usados.length > 0);
  assert.deepEqual(usados.filter((k) => !Object.hasOwn(CLAVES_TARIFA, k)), []);
});

test("tarifasDe -> fijarTarifas: el total de la reserva usa las tarifas editadas (también la limpieza en 0)", () => {
  try {
    const t = tarifasDe(indexarContenido([
      { clave: "tarifa.noche", valor: "70000", tipo: "precio" },
      { clave: "tarifa.limpieza", valor: "0", tipo: "precio" },
    ]));
    assert.equal(fijarTarifas(t), true);
    assert.deepEqual(tarifaVigente(), { noche: 70000, limpieza: 0 });
    assert.deepEqual(total(3), { noches: 3, alojamiento: 210000, limpieza: 0, total: 210000 });   // noches × noche
    // sólo la noche editada: la limpieza sigue la de ejemplo
    assert.equal(fijarTarifas(tarifasDe(indexarContenido([{ clave: "tarifa.noche", valor: "60000", tipo: "precio" }]))), true);
    assert.equal(total(2).total, 2 * 60000 + TARIFA.limpieza);
    // sin tarifas editadas (null) no cambia nada
    assert.equal(fijarTarifas(tarifasDe(indexarContenido(null))), false);
    assert.equal(total(2).total, 2 * 60000 + TARIFA.limpieza);
  } finally {
    fijarTarifas(TARIFA);
  }
  assert.equal(total(3).total, 3 * TARIFA.noche + TARIFA.limpieza);
});

// ---------------------------------------------------------------- idiomas (valor, valor_en, valor_fr)
// Filas como las devuelve select=* después de la migración que agrega valor_en y valor_fr (las demás columnas de la
// 0003 también llegan y se ignoran).
const FILAS_IDIOMAS = [
  { clave: "hero.bajada", valor: "Bajada editada", valor_en: "Edited lead", valor_fr: "Chapeau modifié", tipo: "parrafo",
    etiqueta: "Bajada", grupo: "portada", orden: 1, actualizado: "2026-09-26T12:00:00Z" },
  { clave: "tour.titulo", valor: "Recorrido", valor_en: "Tour", valor_fr: null, tipo: "texto" },
  { clave: "faq.uno", valor: "Pregunta", valor_en: "   ", tipo: "texto" },                   // en blanco: no cuenta
  { clave: "tarifa.noche", valor: "70000", valor_en: null, valor_fr: null, tipo: "precio" },
  { clave: "raro", valor: "Algo", valor_en: { a: 1 }, valor_fr: 7, tipo: "texto" },
];

test("indexarContenido guarda valor_en y valor_fr cuando son texto (o número); la fila sigue exigiendo valor", () => {
  const m = indexarContenido(FILAS_IDIOMAS);
  assert.deepEqual(CAMPOS_VALOR, { es: "valor", en: "valor_en", fr: "valor_fr" });
  assert.deepEqual(m.get("hero.bajada"), { valor: "Bajada editada", tipo: "parrafo", valor_en: "Edited lead", valor_fr: "Chapeau modifié" });
  assert.deepEqual(m.get("tour.titulo"), { valor: "Recorrido", tipo: "texto", valor_en: "Tour" });
  assert.deepEqual(m.get("raro"), { valor: "Algo", tipo: "texto", valor_fr: 7 });
  assert.equal(indexarContenido([{ clave: "x", valor: null, valor_en: "Only English", tipo: "texto" }]).size, 0);
});

test("textoContenido por idioma: la columna del idioma o null (queda el estático, nunca se cae al español)", () => {
  const m = indexarContenido(FILAS_IDIOMAS);
  const e = (k) => m.get(k);
  assert.equal(textoContenido(e("hero.bajada")), "Bajada editada");               // Node: IDIOMA es «es»
  assert.equal(textoContenido(e("hero.bajada"), "es"), "Bajada editada");
  assert.equal(textoContenido(e("hero.bajada"), "en"), "Edited lead");
  assert.equal(textoContenido(e("hero.bajada"), "fr"), "Chapeau modifié");
  assert.equal(textoContenido(e("tour.titulo"), "fr"), null);                     // null en la base
  assert.equal(textoContenido(e("faq.uno"), "en"), null);                         // en blanco
  assert.equal(textoContenido(e("faq.uno"), "fr"), null);                         // columna ausente (antes de migrar)
  assert.equal(textoContenido(e("raro"), "fr"), "7");
  assert.equal(textoContenido(e("hero.bajada"), "de"), "Bajada editada");         // idioma desconocido: el base
  // un precio usa siempre `valor`, escrito con el locale del idioma
  assert.equal(textoContenido(e("tarifa.noche"), "es"), clp(70000));
  assert.equal(textoContenido(e("tarifa.noche"), "en"), "CLP 70,000");
  assert.equal(textoContenido(e("tarifa.noche"), "fr"), clp(70000, "fr-FR"));
  assert.match(textoContenido(e("tarifa.noche"), "fr"), /^CLP 70[\u00a0\u202f ]000$/);
  assert.equal(textoContenido({ valor: "65.000", tipo: "precio" }, "en"), null);
});

test("aplicarContenido en inglés y en francés: textos del idioma, estáticos si falta y precios con su formato", () => {
  const pagina = () => {
    const bajada = conTexto(n("p", { "data-contenido": "hero.bajada" }), "Static lead");
    const titulo = conTexto(n("h2", { "data-contenido": "tour.titulo" }), "Texto estático traducido");
    const faq = conTexto(n("p", { "data-contenido": "faq.uno" }), "Static question");
    // precios: lo que escribe hoy sitio.js en toda página, clp(TARIFA[…]) sin locale, es decir, en formato es-CL
    const precio = conTexto(n("span", { "data-contenido": "tarifa.noche" }), clp(TARIFA.noche));
    const pNoche = conTexto(n("td", { "data-precio": "noche" }), clp(TARIFA.noche));
    const pLimpieza = conTexto(n("td", { "data-precio": "limpieza" }), clp(TARIFA.limpieza));
    return { doc: new Documento([bajada, titulo, faq, precio, pNoche, pLimpieza]), bajada, titulo, faq, precio, pNoche, pLimpieza };
  };
  const contenido = indexarContenido(FILAS_IDIOMAS);
  assert.equal(clp(TARIFA.limpieza), "CLP 15.000");

  const en = pagina();
  assert.equal(aplicarContenido(en.doc, contenido, "en"), 5);                     // bajada, título y tres precios
  assert.equal(en.bajada.textContent, "Edited lead");
  assert.equal(en.titulo.textContent, "Tour");
  assert.equal(en.faq.textContent, "Static question");                            // en blanco: queda el del build
  assert.equal(en.precio.textContent, "CLP 70,000");
  assert.equal(en.pNoche.textContent, "CLP 70,000");
  // hallazgo JS-4: la limpieza no editada también pasa al formato del idioma (antes quedaba «CLP 15.000» de sitio.js
  // al lado de «CLP 70,000»)
  assert.equal(en.pLimpieza.textContent, "CLP 15,000");
  for (const el of [en.precio, en.pNoche, en.pLimpieza]) assert.match(el.textContent, /^CLP \d{1,3}(,\d{3})*$/);

  const fr = pagina();
  assert.equal(aplicar(fr.doc, { contenido, fotos: new Map(), base: BASE }, "fr").textos, 4);   // bajada y tres precios
  assert.equal(fr.bajada.textContent, "Chapeau modifié");
  assert.equal(fr.titulo.textContent, "Texto estático traducido");                // valor_fr null: no se pone el español
  assert.equal(fr.faq.textContent, "Static question");
  assert.equal(fr.precio.textContent, clp(70000, "fr-FR"));
  assert.equal(fr.pNoche.textContent, clp(70000, "fr-FR"));
  assert.equal(fr.pLimpieza.textContent, clp(TARIFA.limpieza, "fr-FR"));
  assert.match(fr.pLimpieza.textContent, /^CLP 15[\u00a0\u202f ]000$/);

  // por defecto, el idioma de la página (en Node, español) con su locale
  assert.equal(IDIOMA, "es");
  assert.equal(LOCALE, "es-CL");
  const es = pagina();
  assert.equal(aplicarContenido(es.doc, contenido), 6);                           // los tres textos y tres precios
  assert.equal(es.bajada.textContent, "Bajada editada");
  assert.equal(es.faq.textContent, "Pregunta");
  assert.equal(es.pNoche.textContent, "CLP 70.000");
  assert.equal(es.pLimpieza.textContent, "CLP 15.000");

  // sin tarifas editadas no se tocan los precios: quedan como los escribió sitio.js (su formato es asunto de sitio.js)
  const sinTarifas = pagina();
  const soloTextos = indexarContenido(FILAS_IDIOMAS.filter((f) => f.tipo !== "precio"));
  assert.equal(aplicarContenido(sinTarifas.doc, soloTextos, "en"), 2);
  assert.equal(sinTarifas.pNoche.textContent, clp(TARIFA.noche));
  assert.equal(sinTarifas.pLimpieza.textContent, clp(TARIFA.limpieza));
});

test("antes de la migración (select=* sin valor_en ni valor_fr): en otro idioma quedan los textos estáticos", () => {
  const contenido = indexarContenido([
    { clave: "hero.bajada", valor: "Bajada editada", tipo: "parrafo", etiqueta: "Bajada", grupo: "portada", orden: 1 },
    { clave: "tarifa.noche", valor: "65000", tipo: "precio", etiqueta: "Noche", grupo: "tarifas", orden: 1 },
  ]);
  const bajada = conTexto(n("p", { "data-contenido": "hero.bajada" }), "Static lead");
  const pNoche = conTexto(n("td", { "data-precio": "noche" }), "CLP 58,000");
  assert.equal(aplicarContenido(new Documento([bajada, pNoche]), contenido, "en"), 1);
  assert.equal(bajada.textContent, "Static lead");
  assert.equal(pNoche.textContent, "CLP 65,000");                                 // la tarifa sí vale en todo idioma
  assert.deepEqual(tarifasDe(contenido), { noche: 65000, limpieza: TARIFA.limpieza });
});

test("miniaturas: etiquetas aria en el idioma de los textos (t de i18n.js)", () => {
  const fotos = indexarFotos([1, 2].map((k) => ({ espacio: "dorm1", ruta: `dorm1/${k}.jpg`, alt: `Foto ${k}`, orden: k })), BASE);
  try {
    for (const [idioma, lista, boton] of [["en", "More photos of this space", "View photo: Foto 2"],
      ["fr", "Plus de photos de cet espace", "Voir la photo\u00a0: Foto 2"]]) {
      fijarTextos(DICCIONARIOS[idioma], DICCIONARIOS.es);
      const f = figura("dorm1", { "data-galeria": "" });
      aplicarFotos(new Documento([f.fig]), fotos);
      const ul = f.fig.querySelector("[data-miniaturas]");
      assert.equal(ul.getAttribute("aria-label"), lista, idioma);
      assert.equal(ul.querySelector("button").getAttribute("aria-label"), boton, idioma);
    }
  } finally {
    fijarTextos(DICCIONARIOS.es);
  }
});

test("rutaValida y urlPublica: sólo objetos dentro del bucket, con cada segmento codificado", () => {
  assert.equal(urlPublica(BASE, "living/foto 1.jpg"), `${PUB}/living/foto%201.jpg`);
  assert.equal(urlPublica(`${BASE}/`, "a.webp"), `${PUB}/a.webp`);
  assert.equal(urlPublica(BASE, "ñandú/sofá#1?.jpg"), `${PUB}/%C3%B1and%C3%BA/sof%C3%A1%231%3F.jpg`);
  assert.equal(urlPublica(BASE, "a/%2e%2e/b.jpg"), `${PUB}/a/%252e%252e/b.jpg`);   // no se decodifica: no sube
  for (const mala of ["", "/a.jpg", "a//b.jpg", "../privado/x.jpg", "a/./b.jpg", "a/..", "a\\b.jpg",
    "https://otro.sitio/x.jpg", "a\nb.jpg", "x".repeat(513), null, 5]) {
    assert.equal(rutaValida(mala), false, `debería rechazar ${JSON.stringify(mala)}`);
    assert.equal(urlPublica(BASE, mala), null);
  }
  assert.equal(urlPublica("", "a.jpg"), null);
  assert.equal(urlPublica("javascript:alert(1)", "a.jpg"), null);
  assert.equal(urlPublica(`${BASE}/ruta`, "a.jpg"), null);
  // sólo https://<proyecto>.supabase.co, la misma forma que exige web/build.py
  for (const base of ["https://otro.sitio", "http://abcdefghijklmnopqrst.supabase.co", "https://abc.supabase.co",
    "https://abcdefghijklmnopqrst.supabase.co.otro.sitio", "https://ABCDEFGHIJKLMNOPQRST.supabase.co",
    "https://abcdefghijklmnopqrst.supabase.co:8443", "https://usuario@abcdefghijklmnopqrst.supabase.co", null]) {
    assert.equal(urlPublica(base, "a.jpg"), null, `debería rechazar la base ${base}`);
  }
});

test("urlFotoValida: sólo la URL pública del bucket «fotos» propio, con cada segmento codificado", () => {
  const buenas = [urlPublica(BASE, "living/foto 1.jpg"), urlPublica(BASE, "ñandú/sofá#1?.jpg"), `${PUB}/a.webp`];
  for (const url of buenas) {
    assert.equal(urlFotoValida(url), true, url);
    assert.equal(urlFotoValida(url, BASE), true, url);
    assert.equal(urlFotoValida(url, `${BASE}/`), true, url);
    assert.equal(urlFotoValida(url, OTRO), false, `no es del proyecto propio: ${url}`);
  }
  assert.equal(urlFotoValida(urlPublica(OTRO, "a.jpg")), true);         // sin base: cualquier proyecto Supabase
  assert.equal(urlFotoValida(urlPublica(OTRO, "a.jpg"), BASE), false);
  for (const mala of [
    `${BASE}/storage/v1/object/public/privado/a.jpg`,                   // otro bucket
    `${BASE}/storage/v1/object/fotos/a.jpg`,                            // no es la ruta pública
    `${BASE}/storage/v1/object/sign/fotos/a.jpg?token=x`,
    `${PUB}/`, `${PUB}`,                                                // sin objeto
    `http://abcdefghijklmnopqrst.supabase.co/storage/v1/object/public/fotos/a.jpg`,
    `https://otro.sitio/storage/v1/object/public/fotos/a.jpg`,
    `https://abcdefghijklmnopqrst.supabase.co.otro.sitio/storage/v1/object/public/fotos/a.jpg`,
    `${PUB}/a.jpg?x=1`, `${PUB}/a.jpg#x`,                               // consulta o fragmento sin codificar
    `${PUB}/foto 1.jpg`, `${PUB}/a,b.jpg`, `${PUB}/a.jpg 2x`,          // espacio o coma: romperían el srcset
    `${PUB}/%2e%2e/b.jpg`, `${PUB}/a%2Fb.jpg`, `${PUB}/../b.jpg`,      // «..» o «/» escondidos
    `${PUB}/%41.jpg`, `${PUB}/%c3%b1.jpg`,                              // codificación no canónica
    `${PUB}/a%.jpg`, `${PUB}/a%zz.jpg`,                                 // «%» inválido
    `${PUB}/a//b.jpg`, `javascript:alert(1)//${PUB.slice(8)}/a.jpg`,
    "", null, 5, { toString: () => `${PUB}/a.jpg` },
  ]) {
    assert.equal(urlFotoValida(mala), false, `debería rechazar ${String(mala)}`);
  }
});

test("indexarFotos: agrupa por espacio, ordena de forma estable y deja \"\" si falta el alt (se completa al aplicar)", () => {
  const m = indexarFotos([
    { espacio: "living", ruta: "living/b.jpg", alt: "B", orden: 2 },
    { espacio: "living", ruta: "living/a.jpg", alt: " A ", orden: 1 },
    { espacio: "living", ruta: "living/c.jpg", alt: "C", orden: 2 },
    { espacio: "cocina", ruta: "cocina/x.jpg", alt: "", orden: 1 },
    { espacio: "cocina", ruta: "cocina/sin-orden.jpg", alt: "S" },
    { espacio: "Living Grande", ruta: "l.jpg", alt: "x", orden: 1 },   // espacio inválido
    { espacio: "living", ruta: "../fuera.jpg", alt: "x", orden: 0 },    // ruta inválida
    null,
  ], BASE);
  assert.deepEqual([...m.keys()], ["living", "cocina"]);
  assert.deepEqual(m.get("living").map((f) => [f.alt, f.url]), [
    ["A", `${PUB}/living/a.jpg`], ["B", `${PUB}/living/b.jpg`], ["C", `${PUB}/living/c.jpg`]]);
  assert.deepEqual(m.get("cocina").map((f) => f.alt), ["", "S"]);
  assert.ok(!("i" in m.get("living")[0]));
  const f = figura("cocina");
  aplicarFotos(new Documento([f.fig]), m, { base: BASE });
  assert.equal(f.img.getAttribute("alt"), ALT_GENERICO);
  assert.equal(indexarFotos(null, BASE).size, 0);
});

test("cabecerasPublicas: Bearer sólo con la clave «anon» antigua, como reservas-api.js", () => {
  assert.deepEqual(cabecerasPublicas("sb_publishable_abc"), { apikey: "sb_publishable_abc", Accept: "application/json" });
  assert.equal(cabecerasPublicas("eyJ.x.y").Authorization, "Bearer eyJ.x.y");
});

// ---------------------------------------------------------------- aplicar al DOM falso
test("aplicarContenido: textContent en [data-contenido] y precios editados en [data-precio]", () => {
  const titulo = conTexto(n("h1", { "data-contenido": "titulo" }), "Departamento 2D2B");
  const bajada = n("p", { "data-contenido": "bajada" }, conTexto(n("b", {}), "negrita estática"));
  const sinDato = conTexto(n("p", { "data-contenido": "no_existe" }), "estático");
  const precio = n("span", { "data-contenido": "tarifa.noche" });
  const vacio = conTexto(n("p", { "data-contenido": "vacio" }), "se queda");
  const pNoche = conTexto(n("td", { "data-precio": "noche" }), clp(TARIFA.noche));
  const pLimpieza = conTexto(n("td", { "data-precio": "limpieza" }), clp(TARIFA.limpieza));
  const pOtro = conTexto(n("td", { "data-precio": "minNoches" }), "2");
  const doc = new Documento([n("main", {}, titulo, bajada, sinDato, precio, vacio, pNoche, pLimpieza, pOtro)]);
  const contenido = indexarContenido([
    { clave: "titulo", valor: "<img src=x onerror=alert(1)>", tipo: "texto" },
    { clave: "bajada", valor: "Nueva bajada", tipo: "texto" },
    { clave: "tarifa.noche", valor: "70000", tipo: "precio" },
    { clave: "vacio", valor: "", tipo: "texto" },
  ]);
  const cambiados = aplicarContenido(doc, contenido);
  assert.equal(cambiados, 5);                                     // titulo, bajada, precio y los dos [data-precio]
  assert.equal(titulo.textContent, "<img src=x onerror=alert(1)>"); // queda como texto, no como HTML
  assert.equal(titulo.children.length, 0);
  assert.equal(bajada.textContent, "Nueva bajada");
  assert.equal(bajada.children.length, 0);
  assert.equal(sinDato.textContent, "estático");
  assert.equal(precio.textContent, clp(70000));
  assert.equal(vacio.textContent, "se queda");
  assert.equal(pNoche.textContent, clp(70000));
  assert.equal(pLimpieza.textContent, clp(TARIFA.limpieza));      // no se editó: el ejemplo, con el mismo formato
  assert.equal(pOtro.textContent, "2");
  assert.equal(aplicarContenido(doc, new Map()), 0);
});

test("aplicarContenido: limpieza en 0 se muestra como CLP 0; noche en 0 deja el precio de ejemplo", () => {
  const pNoche = conTexto(n("td", { "data-precio": "noche" }), clp(TARIFA.noche));
  const pLimpieza = conTexto(n("td", { "data-precio": "limpieza" }), clp(TARIFA.limpieza));
  const cNoche = conTexto(n("span", { "data-contenido": "tarifa.noche" }), "estático");
  const cLimpieza = conTexto(n("span", { "data-contenido": "tarifa.limpieza" }), "estático");
  const pRaro = conTexto(n("td", { "data-precio": "toString" }), "se queda");
  const doc = new Documento([pNoche, pLimpieza, cNoche, cLimpieza, pRaro]);
  const cambiados = aplicarContenido(doc, indexarContenido([
    { clave: "tarifa.noche", valor: "0", tipo: "precio" },
    { clave: "tarifa.limpieza", valor: "0", tipo: "precio" },
  ]));
  assert.equal(cambiados, 4);                                     // las cuatro tarifas, con un solo formato
  assert.equal(pLimpieza.textContent, clp(0));
  assert.equal(cLimpieza.textContent, clp(0));
  assert.equal(pNoche.textContent, clp(TARIFA.noche));            // noche en 0: no editada, queda la de ejemplo
  assert.equal(cNoche.textContent, clp(TARIFA.noche));            // misma regla por data-contenido
  // con la noche en 0 como única «edición» no hay tarifas editadas: no se toca nada
  const solo0 = conTexto(n("span", { "data-contenido": "tarifa.noche" }), "estático");
  assert.equal(aplicarContenido(new Documento([solo0]), indexarContenido([{ clave: "tarifa.noche", valor: "0", tipo: "precio" }])), 0);
  assert.equal(solo0.textContent, "estático");
  assert.equal(pRaro.textContent, "se queda");
});

test("aplicarFotos: la primera foto reemplaza el <img> y la URL de cada <source>; conserva tamaño y clases", () => {
  const living = figura("living");
  const cocina = figura("cocina");                                // sin fotos: no se toca
  const doc = new Documento([living.fig, cocina.fig]);
  const fotos = indexarFotos([
    { espacio: "living", ruta: "living/1.jpg", alt: "Living con sol de tarde", orden: 1 },
    { espacio: "living", ruta: "living/2.jpg", alt: "Otra", orden: 2 },
  ], BASE);
  assert.equal(aplicarFotos(doc, fotos), 1);
  const { img, picture, source } = living;
  assert.equal(img.getAttribute("src"), `${PUB}/living/1.jpg`);
  assert.equal(img.getAttribute("alt"), "Living con sol de tarde");   // el alt de la foto
  assert.equal(img.getAttribute("srcset"), null);                 // no tenía srcset: no se agrega
  assert.equal(img.getAttribute("sizes"), null);
  assert.equal(img.getAttribute("loading"), "lazy");              // se respeta la carga diferida
  assert.equal(img.getAttribute("width"), "800");                 // sin saltos de diseño
  assert.equal(img.getAttribute("height"), "500");
  assert.equal(img.className, "foto redondeada");
  // el <source> sigue en su lugar, pero con la foto: si no, el navegador elegiría el WebP estático
  assert.deepEqual(picture.children, [source, img]);
  assert.equal(source.getAttribute("srcset"), `${PUB}/living/1.jpg`);
  assert.equal(source.getAttribute("sizes"), null);
  assert.equal(source.getAttribute("type"), null);                // era el tipo del WebP estático, no el de la foto
  assert.equal(living.fig.querySelector("[data-miniaturas]"), null);   // sin data-galeria no hay miniaturas
  assert.equal(cocina.img.getAttribute("src"), "img/x-800.jpg");
  assert.equal(cocina.source.getAttribute("srcset"), "img/x-800.webp 800w, img/x-1600.webp 1600w");
  assert.equal(cocina.picture.children.length, 2);
});

test("aplicarFotos: un <img> con srcset propio recibe la URL de la foto y la recupera al restaurar", () => {
  const f = figura("living", {}, { srcset: "img/x-800.jpg 800w, img/x-1600.jpg 1600w", sizes: "(min-width: 60em) 50vw, 100vw" });
  aplicarFotos(new Documento([f.fig]), indexarFotos([{ espacio: "living", ruta: "living/1.jpg", alt: "Uno", orden: 1 }], BASE));
  assert.equal(f.img.getAttribute("srcset"), `${PUB}/living/1.jpg`);
  assert.equal(f.img.getAttribute("sizes"), null);
  assert.equal(f.img.getAttribute("src"), `${PUB}/living/1.jpg`);
  f.img.emitir("error");
  assert.equal(f.img.getAttribute("srcset"), "img/x-800.jpg 800w, img/x-1600.jpg 1600w");
  assert.equal(f.img.getAttribute("sizes"), "(min-width: 60em) 50vw, 100vw");
  assert.equal(f.img.getAttribute("src"), "img/x-800.jpg");
  assert.equal(f.img.className, "foto redondeada");
});

test("aplicarFotos: rechaza fotos que no son del bucket público propio, aunque vengan en el Map", () => {
  const f = figura("living", { "data-galeria": "" });
  const doc = new Documento([f.fig]);
  const ajenas = new Map([["living", [
    { url: "https://otro.sitio/x.jpg", alt: "Otro sitio" },
    { url: `${BASE}/storage/v1/object/public/privado/x.jpg`, alt: "Otro bucket" },
    { url: `${PUB}/a b.jpg`, alt: "Sin codificar" },
    { url: "javascript:alert(1)", alt: "x" },
    null,
  ]]]);
  assert.equal(aplicarFotos(doc, ajenas), 0);
  assert.equal(f.img.getAttribute("src"), "img/x-800.jpg");
  // de otro proyecto: sin base se acepta la forma; con la base propia (lo que hace aplicar) no
  const deOtro = new Map([["living", [{ url: urlPublica(OTRO, "x.jpg"), alt: "X" }]]]);
  assert.equal(aplicar(doc, { contenido: new Map(), fotos: deOtro, base: BASE }).fotos, 0);
  assert.equal(f.img.getAttribute("src"), "img/x-800.jpg");
  // mezcladas: sólo quedan las válidas, con alt de respaldo
  const mezcla = new Map([["living", [{ url: "https://otro.sitio/x.jpg", alt: "Mala" }, { url: `${PUB}/b.jpg`, alt: " " },
    { url: `${PUB}/c.jpg`, alt: "C" }]]]);
  assert.equal(aplicar(doc, { contenido: new Map(), fotos: mezcla, base: BASE }).fotos, 1);
  assert.equal(f.img.getAttribute("src"), `${PUB}/b.jpg`);
  assert.equal(f.img.getAttribute("alt"), ALT_GENERICO);
  assert.equal(f.fig.querySelectorAll("button").length, 1);
});

test("aplicarFotos: si la foto no carga, vuelve la imagen estática con su <source>", () => {
  const f = figura("living", { "data-galeria": "" });
  const doc = new Documento([f.fig]);
  aplicarFotos(doc, indexarFotos([
    { espacio: "living", ruta: "living/rota.jpg", alt: "Rota", orden: 1 },
    { espacio: "living", ruta: "living/2.jpg", alt: "Dos", orden: 2 },
  ], BASE));
  assert.ok(f.fig.querySelector("[data-miniaturas]"));
  f.img.emitir("error");
  assert.equal(f.img.getAttribute("src"), "img/x-800.jpg");
  assert.equal(f.img.getAttribute("alt"), "Render estático");
  assert.equal(f.img.getAttribute("sizes"), null);                // el <img> estático no tenía sizes
  assert.equal(f.img.getAttribute("width"), "800");
  assert.equal(f.img.className, "foto redondeada");
  assert.deepEqual(f.picture.children.map((c) => c.tagName), ["SOURCE", "IMG"]);
  assert.equal(f.picture.children[0], f.source);
  assert.equal(f.source.getAttribute("srcset"), "img/x-800.webp 800w, img/x-1600.webp 1600w");
  assert.equal(f.source.getAttribute("sizes"), "100vw");
  assert.equal(f.source.getAttribute("type"), "image/webp");
  assert.equal(f.fig.querySelector("[data-miniaturas]"), null);   // sin galería a medias
});

test("aplicarFotos: si la estática también falla, la restauración no se repite (sin bucle de descargas)", () => {
  const f = figura("living", { "data-galeria": "" });
  const doc = new Documento([f.fig]);
  const fotos = indexarFotos([
    { espacio: "living", ruta: "living/rota.jpg", alt: "Rota", orden: 1 },
    { espacio: "living", ruta: "living/2.jpg", alt: "Dos", orden: 2 },
  ], BASE);
  aplicarFotos(doc, fotos);
  f.img.emitir("error");                                          // la foto falla: vuelve la estática
  assert.equal(f.img.getAttribute("src"), "img/x-800.jpg");
  const cambios = espiar(f.img, f.source, f.picture);
  const hijos = [...f.picture.children];
  f.img.emitir("error");                                          // la estática tampoco carga (sin red)
  f.img.emitir("error");
  assert.equal(cambios(), 0, "no vuelve a asignar src ni a tocar el <source>");
  assert.deepEqual(f.picture.children, hijos);
  assert.equal(f.img.getAttribute("src"), "img/x-800.jpg");
  // otro aplicarFotos vuelve a activar la restauración
  aplicarFotos(doc, fotos);
  assert.equal(f.img.getAttribute("src"), `${PUB}/living/rota.jpg`);
  assert.equal(f.source.getAttribute("srcset"), `${PUB}/living/rota.jpg`);
  f.img.emitir("error");
  assert.equal(f.img.getAttribute("src"), "img/x-800.jpg");
  assert.equal(f.source.getAttribute("srcset"), "img/x-800.webp 800w, img/x-1600.webp 1600w");
  assert.equal(f.fig.querySelector("[data-miniaturas]"), null);
});

test("aplicarFotos con data-galeria: miniaturas de las demás que se intercambian con la principal", () => {
  const f = figura("dorm1", { "data-galeria": "" });
  const doc = new Documento([f.fig]);
  const fotos = indexarFotos([1, 2, 3].map((k) => ({ espacio: "dorm1", ruta: `dorm1/${k}.jpg`, alt: `Foto ${k}`, orden: k })), BASE);
  aplicarFotos(doc, fotos);
  const lista = f.fig.querySelector("[data-miniaturas]");
  assert.equal(lista.tagName, "UL");
  assert.equal(lista.className, "miniaturas");
  assert.equal(lista.getAttribute("aria-label"), "Más fotos de este espacio");
  assert.deepEqual(f.fig.children.map((c) => c.tagName), ["PICTURE", "UL", "FIGCAPTION"]);  // figcaption sigue al final
  const botones = lista.querySelectorAll("button");
  assert.equal(botones.length, 2);
  assert.deepEqual(botones.map((b) => b.getAttribute("aria-label")), ["Ver foto: Foto 2", "Ver foto: Foto 3"]);
  assert.ok(botones.every((b) => b.getAttribute("type") === "button"));
  const minis = lista.querySelectorAll("img");
  assert.deepEqual(minis.map((m) => m.getAttribute("src")), [`${PUB}/dorm1/2.jpg`, `${PUB}/dorm1/3.jpg`]);
  assert.ok(minis.every((m) => m.getAttribute("alt") === "" && m.getAttribute("loading") === "lazy"));

  botones[1].emitir("click");                                     // la 3 pasa a principal, la 1 a la miniatura
  assert.equal(f.img.getAttribute("src"), `${PUB}/dorm1/3.jpg`);
  assert.equal(f.source.getAttribute("srcset"), `${PUB}/dorm1/3.jpg`);   // el <source> no deja ganar a la anterior
  assert.equal(f.img.getAttribute("alt"), "Foto 3");
  assert.equal(minis[1].getAttribute("src"), `${PUB}/dorm1/1.jpg`);
  assert.equal(botones[1].getAttribute("aria-label"), "Ver foto: Foto 1");
  botones[0].emitir("click");                                     // la 2 a principal, la 3 a la primera miniatura
  assert.equal(f.img.getAttribute("src"), `${PUB}/dorm1/2.jpg`);
  assert.equal(minis[0].getAttribute("src"), `${PUB}/dorm1/3.jpg`);

  minis[0].emitir("error");                                       // una miniatura rota desaparece
  assert.equal(lista.querySelectorAll("button").length, 1);

  aplicarFotos(doc, fotos);                                       // aplicar de nuevo no duplica la galería
  assert.equal(f.fig.querySelectorAll("[data-miniaturas]").length, 1);
  assert.equal(f.img.getAttribute("src"), `${PUB}/dorm1/1.jpg`);
  f.img.emitir("error");                                          // y la restauración sigue siendo la estática
  assert.equal(f.img.getAttribute("src"), "img/x-800.jpg");
  assert.equal(f.fig.querySelectorAll("[data-miniaturas]").length, 0);
});

test("aplicarFotos: <img> suelto (sin <picture>), tope de miniaturas y contenedor sin imagen", () => {
  const img = n("img", { src: "img/b.jpg", alt: "Estático" });
  const suelto = n("div", { "data-fotos": "bano", "data-galeria": "" }, img);
  const sinImg = n("div", { "data-fotos": "bano" });
  const doc = new Documento([suelto, sinImg]);
  const filas = Array.from({ length: MAX_MINIATURAS + 5 }, (_, k) => ({ espacio: "bano", ruta: `b/${k}.jpg`, alt: `B${k}`, orden: k }));
  assert.equal(aplicarFotos(doc, indexarFotos(filas, BASE)), 1);
  assert.equal(img.getAttribute("src"), `${PUB}/b/0.jpg`);
  assert.deepEqual(suelto.children.map((c) => c.tagName), ["IMG", "UL"]);
  assert.equal(suelto.querySelectorAll("button").length, MAX_MINIATURAS);
  assert.equal(sinImg.children.length, 0);
  img.emitir("error");
  assert.equal(img.getAttribute("src"), "img/b.jpg");
  assert.deepEqual(suelto.children.map((c) => c.tagName), ["IMG"]);
});

test("aplicar: sin datos no toca nada", () => {
  const titulo = conTexto(n("h1", { "data-contenido": "titulo" }), "Departamento 2D2B");
  const f = figura("living", { "data-galeria": "" });
  const doc = new Documento([titulo, f.fig]);
  assert.deepEqual(aplicar(doc, null), { textos: 0, fotos: 0 });
  assert.deepEqual(aplicar(doc, { contenido: new Map(), fotos: new Map() }), { textos: 0, fotos: 0 });
  assert.equal(titulo.textContent, "Departamento 2D2B");
  assert.equal(f.img.getAttribute("src"), "img/x-800.jpg");
  assert.equal(f.picture.children.length, 2);
});

// ---------------------------------------------------------------- red falsa
const respuesta = (cuerpo, estado = 200) => ({ ok: estado >= 200 && estado < 300, status: estado, json: async () => cuerpo });
const esperarAborto = (signal) => new Promise((_, no) => {
  signal.addEventListener("abort", () => no(Object.assign(new Error("abortado"), { name: "AbortError" })));
});

test("leerFilas: filas, errores de PostgREST, respuesta que no es arreglo y red caída -> null", async () => {
  const pedidos = [];
  const f = async (url, op) => { pedidos.push({ url, op }); return respuesta([{ clave: "a", valor: "b", tipo: "texto" }]); };
  assert.deepEqual(await leerFilas(BASE, "sb_publishable_x", RUTA_CONTENIDO, { fetch: f }), [{ clave: "a", valor: "b", tipo: "texto" }]);
  assert.equal(pedidos[0].url, `${BASE}/rest/v1/contenido?select=*`);
  assert.equal(pedidos[0].op.headers.apikey, "sb_publishable_x");
  assert.equal(pedidos[0].op.method, undefined);                  // GET: nunca escribe
  assert.equal(pedidos[0].op.body, undefined);
  assert.ok(pedidos[0].op.signal);
  // tabla que todavía no existe (migración 0003 sin aplicar): PostgREST responde 404 con un objeto de error
  assert.equal(await leerFilas(BASE, "k", RUTA_FOTOS, { fetch: async () => respuesta({ code: "PGRST205", message: "x" }, 404) }), null);
  assert.equal(await leerFilas(BASE, "k", RUTA_FOTOS, { fetch: async () => respuesta({ no: "arreglo" }) }), null);
  assert.equal(await leerFilas(BASE, "k", RUTA_FOTOS, { fetch: async () => { throw new TypeError("Failed to fetch"); } }), null);
  assert.equal(await leerFilas(BASE, "k", RUTA_FOTOS, { fetch: async () => ({ ok: true, json: async () => { throw new SyntaxError("x"); } }) }), null);
  assert.equal(await leerFilas(BASE, "k", RUTA_FOTOS, { fetch: null }), null);
});

test("leerFilas: el plazo corta tanto la conexión como la lectura del cuerpo (sin reintentos)", async () => {
  let llamadas = 0;
  const t0 = Date.now();
  const colgado = (_, { signal }) => { llamadas++; return esperarAborto(signal); };
  assert.equal(await leerFilas(BASE, "k", RUTA_FOTOS, { fetch: colgado, tiempo: 30 }), null);
  const cuerpoLento = async (_, { signal }) => { llamadas++; return { ok: true, json: () => esperarAborto(signal) }; };
  assert.equal(await leerFilas(BASE, "k", RUTA_FOTOS, { fetch: cuerpoLento, tiempo: 30 }), null);
  assert.equal(llamadas, 2);
  assert.ok(Date.now() - t0 < 2000);
});

test("obtenerDatos: sin configuración no llama a la red; con ella lee las dos tablas con la clave pública", async () => {
  let llamadas = 0;
  const contar = async () => { llamadas++; return respuesta([]); };
  assert.equal(await obtenerDatos({ config: null, fetch: contar }), null);
  assert.equal(await obtenerDatos({ config: { url: "", clave: "" }, fetch: contar }), null);
  assert.equal(await obtenerDatos({ config: { url: "http://abc.supabase.co", clave: "k" }, fetch: contar }), null);
  assert.equal(await obtenerDatos({ config: { url: BASE, clave: "  " }, fetch: contar }), null);
  assert.equal(await obtenerDatos({ config: { url: "https://otro.ejemplo.com", clave: "k" }, fetch: contar }), null);
  assert.equal(llamadas, 0);

  const urls = [];
  const f = async (url) => {
    urls.push(url);
    if (url.includes("/rest/v1/contenido?")) return respuesta([{ clave: "titulo", valor: "Nuevo", tipo: "texto" }]);
    return respuesta({ message: "relation \"public.fotos\" does not exist" }, 404);
  };
  const d = await obtenerDatos({ config: { url: `${BASE}/`, clave: "sb_publishable_x" }, fetch: f });
  assert.deepEqual(urls.sort(), [`${BASE}/rest/v1/${RUTA_CONTENIDO}`, `${BASE}/rest/v1/${RUTA_FOTOS}`].sort());
  assert.equal(RUTA_FOTOS, "fotos?select=espacio,ruta,alt,orden&visible=eq.true&order=orden.asc");
  assert.equal(d.contenido.get("titulo").valor, "Nuevo");
  assert.equal(d.fotos.size, 0);                                  // la tabla que falló no rompe la otra
  assert.equal(d.base, BASE);                                     // aplicar sólo acepta fotos de este proyecto
});

test("tarifas(): sin js/config.js (no existe en src/, lo genera el build) devuelve null", async () => {
  assert.equal(await tarifas(), null);
});

// ---------------------------------------------------------------- orden de carga en una página (hallazgo JS-3)
test("en /en/: las lecturas de la base empiezan antes de que llegue el diccionario y los textos se aplican después", async () => {
  // copia de los módulos con un js/config.js ficticio (no hay red: el fetch es falso y la URL, inventada)
  const copia = copiaDelSitio([...MODULOS_I18N, "contenido-publico.js", "reserva-logica.js"], {
    "js/config.js": `export const SUPABASE_URL = "${BASE}";\nexport const SUPABASE_CLAVE_PUBLICA = "clave-publica-de-prueba";\n`,
  });
  const eventos = [];
  let soltar;
  const diccionario = new Promise((ok) => { soltar = ok; });
  const fetchFalso = async (url) => {
    const u = new URL(String(url));
    if (u.protocol === "file:") {                                   // ../i18n/en.json, relativo a la copia de i18n.js
      eventos.push(`pide ${u.pathname.split("/").slice(-2).join("/")}`);
      await diccionario;
      eventos.push("llega el diccionario");
      return respuesta(DICCIONARIOS.en);
    }
    eventos.push(`pide ${u.pathname}`);
    if (u.pathname === "/rest/v1/contenido") return respuesta(FILAS_IDIOMAS);
    if (u.pathname === "/rest/v1/fotos") return respuesta([{ espacio: "living", ruta: "living/1.jpg", alt: "", orden: 1 }]);
    return respuesta(null, 404);
  };
  const bajada = conTexto(n("p", { "data-contenido": "hero.bajada" }), "Static lead");
  const living = figura("living");
  const doc = new Documento([bajada, living.fig]);
  doc.documentElement = { lang: "en" };
  await conGlobales({ document: doc, fetch: fetchFalso }, async () => {
    // con await de nivel superior en i18n.js, esta importación no terminaría hasta soltar el diccionario
    await Promise.race([import(copia.url("js/contenido-publico.js")),
      new Promise((_, no) => setTimeout(() => no(new Error("importar contenido-publico.js esperó al diccionario")), 1000))]);
    await hasta(() => eventos.filter((e) => e.startsWith("pide /rest/v1/")).length === 2);
    assert.deepEqual(eventos.slice().sort(), ["pide /rest/v1/contenido", "pide /rest/v1/fotos", "pide i18n/en.json"],
      "las dos lecturas de la base salieron con el diccionario todavía pendiente");
    await new Promise((ok) => setTimeout(ok, 20));
    assert.equal(bajada.textContent, "Static lead", "los textos esperan al diccionario");
    soltar();
    await hasta(() => bajada.textContent === "Edited lead");
    assert.equal(eventos.indexOf("llega el diccionario"), 3);
    // el alt de respaldo sale en inglés: se resolvió al aplicar, con el diccionario ya cargado
    assert.equal(living.img.getAttribute("alt"), DICCIONARIOS.en[CLAVE_ALT_GENERICO]);
    assert.equal(living.img.getAttribute("src"), `${PUB}/living/1.jpg`);
  });
});
