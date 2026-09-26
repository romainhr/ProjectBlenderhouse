// Pruebas de web/src/js/contenido-publico.js con el ejecutor incluido en Node (sin dependencias ni DOM real):
//   cd web && npm test     (node --test tests/*.test.mjs)
// El DOM se imita con objetos mínimos (querySelectorAll, atributos, textContent, eventos); innerHTML lanza un error
// para comprobar que el módulo nunca lo usa. La red se imita con un fetch falso.
import assert from "node:assert/strict";
import { test } from "node:test";

import { TARIFA, clp } from "../src/js/reserva-logica.js";
import {
  ALT_GENERICO, BUCKET_FOTOS, CLAVES_TARIFA, MAX_MINIATURAS, RUTA_CONTENIDO, RUTA_FOTOS, aplicar, aplicarContenido,
  aplicarFotos, cabecerasPublicas, indexarContenido, indexarFotos, leerFilas, obtenerDatos, precioValido, rutaValida,
  tarifas, tarifasDe, textoContenido, urlPublica,
} from "../src/js/contenido-publico.js";

const BASE = "https://abcdefghijklmnopqrst.supabase.co";            // ficticia: estas pruebas no usan la red
const PUB = `${BASE}/storage/v1/object/public/${BUCKET_FOTOS}`;

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
function figura(espacio, extra = {}) {
  const source = n("source", { type: "image/webp", srcset: "img/x-800.webp 800w, img/x-1600.webp 1600w", sizes: "100vw" });
  const img = n("img", { src: "img/x-800.jpg", alt: "Render estático", loading: "lazy", width: "800", height: "500" });
  const picture = n("picture", {}, source, img);
  const caption = conTexto(n("figcaption", {}), "Pie");
  const fig = n("figure", { "data-fotos": espacio, ...extra }, picture, caption);
  return { fig, picture, source, img, caption };
}

// ---------------------------------------------------------------- lógica pura
test("indexarContenido: acepta filas bien formadas y descarta el resto", () => {
  const m = indexarContenido([
    { clave: "titulo", valor: "Loft nuevo", tipo: "texto" },
    { clave: "precio_noche", valor: "65000", tipo: "precio" },
    { clave: "huespedes", valor: 4 },                          // número y sin tipo -> texto
    { clave: "Mayus", valor: "x", tipo: "texto" },             // clave inválida
    { clave: "nulo", valor: null, tipo: "texto" },
    { clave: "objeto", valor: { a: 1 }, tipo: "texto" },
    null,
    "basura",
  ]);
  assert.deepEqual([...m.keys()], ["titulo", "precio_noche", "huespedes"]);
  assert.deepEqual(m.get("huespedes"), { valor: 4, tipo: "texto" });
  assert.equal(indexarContenido(null).size, 0);
  assert.equal(indexarContenido({ message: "relation does not exist" }).size, 0);
});

test("precioValido y textoContenido: CLP entero, formato es-CL y vacíos que dejan el estático", () => {
  assert.equal(precioValido("65000"), 65000);
  assert.equal(precioValido(" 65000 "), 65000);
  assert.equal(precioValido(65000), 65000);
  for (const malo of ["65.000", "65,5", "-1", "0", 0, 1.5, 1e8, "abc", "", null, undefined, NaN]) {
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
  assert.equal(tarifasDe(c([{ clave: "titulo", valor: "x", tipo: "texto" }])), null);
  assert.equal(tarifasDe(new Map()), null);
  assert.equal(tarifasDe(null), null);
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
});

test("indexarFotos: agrupa por espacio, ordena de forma estable y completa el texto alternativo", () => {
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
  assert.deepEqual(m.get("cocina").map((f) => f.alt), [ALT_GENERICO, "S"]);
  assert.ok(!("i" in m.get("living")[0]));
  assert.equal(indexarFotos(null, BASE).size, 0);
});

test("cabecerasPublicas: Bearer sólo con la clave «anon» antigua, como reservas-api.js", () => {
  assert.deepEqual(cabecerasPublicas("sb_publishable_abc"), { apikey: "sb_publishable_abc", Accept: "application/json" });
  assert.equal(cabecerasPublicas("eyJ.x.y").Authorization, "Bearer eyJ.x.y");
});

// ---------------------------------------------------------------- aplicar al DOM falso
test("aplicarContenido: textContent en [data-contenido] y precios editados en [data-precio]", () => {
  const titulo = conTexto(n("h1", { "data-contenido": "titulo" }), "Loft 2D2B");
  const bajada = n("p", { "data-contenido": "bajada" }, conTexto(n("b", {}), "negrita estática"));
  const sinDato = conTexto(n("p", { "data-contenido": "no_existe" }), "estático");
  const precio = n("span", { "data-contenido": "precio_noche" });
  const vacio = conTexto(n("p", { "data-contenido": "vacio" }), "se queda");
  const pNoche = conTexto(n("td", { "data-precio": "noche" }), clp(TARIFA.noche));
  const pLimpieza = conTexto(n("td", { "data-precio": "limpieza" }), clp(TARIFA.limpieza));
  const pOtro = conTexto(n("td", { "data-precio": "minNoches" }), "2");
  const doc = new Documento([n("main", {}, titulo, bajada, sinDato, precio, vacio, pNoche, pLimpieza, pOtro)]);
  const contenido = indexarContenido([
    { clave: "titulo", valor: "<img src=x onerror=alert(1)>", tipo: "texto" },
    { clave: "bajada", valor: "Nueva bajada", tipo: "texto" },
    { clave: "precio_noche", valor: "70000", tipo: "precio" },
    { clave: "vacio", valor: "", tipo: "texto" },
  ]);
  const cambiados = aplicarContenido(doc, contenido);
  assert.equal(cambiados, 4);                                     // titulo, bajada, precio y [data-precio="noche"]
  assert.equal(titulo.textContent, "<img src=x onerror=alert(1)>"); // queda como texto, no como HTML
  assert.equal(titulo.children.length, 0);
  assert.equal(bajada.textContent, "Nueva bajada");
  assert.equal(bajada.children.length, 0);
  assert.equal(sinDato.textContent, "estático");
  assert.equal(precio.textContent, clp(70000));
  assert.equal(vacio.textContent, "se queda");
  assert.equal(pNoche.textContent, clp(70000));
  assert.equal(pLimpieza.textContent, clp(TARIFA.limpieza));      // no se editó: queda el ejemplo
  assert.equal(pOtro.textContent, "2");
  assert.equal(aplicarContenido(doc, new Map()), 0);
});

test("aplicarFotos: la primera foto reemplaza <img> y quita los <source> del <picture>", () => {
  const living = figura("living");
  const cocina = figura("cocina");                                // sin fotos: no se toca
  const doc = new Documento([living.fig, cocina.fig]);
  const fotos = indexarFotos([
    { espacio: "living", ruta: "living/1.jpg", alt: "Living con sol de tarde", orden: 1 },
    { espacio: "living", ruta: "living/2.jpg", alt: "Otra", orden: 2 },
  ], BASE);
  assert.equal(aplicarFotos(doc, fotos), 1);
  const { img, picture } = living;
  assert.equal(img.getAttribute("src"), `${PUB}/living/1.jpg`);
  assert.equal(img.getAttribute("alt"), "Living con sol de tarde");
  assert.equal(img.getAttribute("srcset"), null);
  assert.equal(img.getAttribute("sizes"), null);
  assert.equal(img.getAttribute("loading"), "lazy");              // se respeta la carga diferida
  assert.deepEqual(picture.children.map((c) => c.tagName), ["IMG"]);
  assert.equal(living.fig.querySelector("[data-miniaturas]"), null);   // sin data-galeria no hay miniaturas
  assert.equal(cocina.img.getAttribute("src"), "img/x-800.jpg");
  assert.equal(cocina.picture.children.length, 2);
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
  assert.deepEqual(f.picture.children.map((c) => c.tagName), ["SOURCE", "IMG"]);
  assert.equal(f.picture.children[0], f.source);
  assert.equal(f.source.getAttribute("srcset"), "img/x-800.webp 800w, img/x-1600.webp 1600w");
  assert.equal(f.fig.querySelector("[data-miniaturas]"), null);   // sin galería a medias
});

test("aplicarFotos con data-galeria: miniaturas de las demás que se intercambian con la principal", () => {
  const f = figura("dorm1", { "data-galeria": "" });
  const doc = new Documento([f.fig]);
  const fotos = indexarFotos([1, 2, 3].map((k) => ({ espacio: "dorm1", ruta: `dorm1/${k}.jpg`, alt: `Foto ${k}`, orden: k })), BASE);
  aplicarFotos(doc, fotos);
  const lista = f.fig.querySelector("[data-miniaturas]");
  assert.equal(lista.tagName, "UL");
  assert.equal(lista.className, "miniaturas");
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
  const titulo = conTexto(n("h1", { "data-contenido": "titulo" }), "Loft 2D2B");
  const f = figura("living", { "data-galeria": "" });
  const doc = new Documento([titulo, f.fig]);
  assert.deepEqual(aplicar(doc, null), { textos: 0, fotos: 0 });
  assert.deepEqual(aplicar(doc, { contenido: new Map(), fotos: new Map() }), { textos: 0, fotos: 0 });
  assert.equal(titulo.textContent, "Loft 2D2B");
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
  assert.equal(pedidos[0].url, `${BASE}/rest/v1/contenido?select=clave,valor,tipo`);
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
});

test("tarifas(): sin js/config.js (no existe en src/, lo genera el build) devuelve null", async () => {
  assert.equal(await tarifas(), null);
});
