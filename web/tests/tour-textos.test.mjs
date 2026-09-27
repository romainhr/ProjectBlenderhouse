// Textos del tour en los tres idiomas (web/src/tour/js/textos.js, luces.js, interaccion.js, interfaz.js y main.js):
//   cd web && npm test
// - toda clave js.tour.* que usa el JS del tour existe en es.json, en.json y fr.json;
// - lo que viene del modelo exportado (exports/web/depto_colisiones.json: recintos, grupos de luz y piezas móviles)
//   tiene su clave en los tres idiomas y el español del diccionario dice lo mismo que el modelo;
// - en Node (español) las pistas quedan idénticas a las de antes de pasar a t();
// - en una página en inglés o francés, los nombres salen del diccionario de ese idioma.
import assert from "node:assert/strict";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { MOTIVO_CAMINO, MOTIVO_HOJA, etiquetaAccion } from "../src/tour/js/interaccion.js";
import { textoInterruptor } from "../src/tour/js/luces.js";
import { claveDeTexto, etiquetaGrupo, nombrePieza, nombreRecinto, traduccion } from "../src/tour/js/textos.js";
import { iniciarSelectorIdioma } from "../src/tour/js/interfaz.js";
import { cookieIdioma } from "../src/js/idioma.js";
import { t } from "../src/js/i18n.js";
import { conGlobales, respuesta, sinComentarios } from "./copia-sitio.mjs";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));
const leerJSON = (ruta) => JSON.parse(readFileSync(ruta, "utf8"));
const DICCIONARIOS = Object.fromEntries(["es", "en", "fr"].map((i) => [i, leerJSON(join(SRC, "i18n", `${i}.json`))]));
const D = leerJSON(fileURLToPath(new URL("../../exports/web/depto_colisiones.json", import.meta.url)));

test("toda clave js.tour.* literal del JS del tour existe en es.json, en.json y fr.json", () => {
  const carpeta = join(SRC, "tour", "js");
  const usadas = [];
  for (const archivo of readdirSync(carpeta).filter((a) => a.endsWith(".js"))) {
    const fuente = sinComentarios(readFileSync(join(carpeta, archivo), "utf8"));
    for (const [, k] of fuente.matchAll(/"(js\.tour\.[A-Za-z0-9_.-]+)"/g)) usadas.push([archivo, k]);
  }
  for (const archivo of ["main.js", "interaccion.js", "luces.js", "interfaz.js"]) {
    assert.ok(usadas.some(([a]) => a === archivo), `${archivo} no usa claves js.tour.*`);
  }
  for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
    for (const [archivo, k] of usadas) assert.ok(Object.hasOwn(d, k), `${idioma}.json no tiene ${k} (${archivo})`);
  }
});

test("el JS del tour no escribe textos en español fuera de los diccionarios", () => {
  // los textos que antes eran literales ya no están en el código (salvo NOMBRES_RECINTO, respaldo del contrato)
  for (const archivo of ["main.js", "interaccion.js", "luces.js", "interfaz.js", "minimapa.js"]) {
    const fuente = sinComentarios(readFileSync(join(SRC, "tour", "js", archivo), "utf8"));
    // un texto que empieza así, en un literal ("…", '…' o `…`)
    const viejos = /["'`](No se pudo|Cargando el modelo|Preparando la escena|Listo ·|Clic en la vista|Estás en el camino|Corre primero|Encender|Apagar|Abrir|Cerrar|Luz: )/;
    assert.doesNotMatch(fuente, viejos, `${archivo}: ese texto debería venir de t()`);
  }
});

test("carga.js resuelve el modelo desde el módulo (sirve igual en /tour/, /en/tour/ y /fr/tour/)", async () => {
  const { RUTA_MODELO } = await import("../src/tour/js/carga.js");
  assert.equal(RUTA_MODELO, new URL("../src/tour/modelo/", import.meta.url).href);
});

test("todo recinto, grupo de luz y pieza del modelo exportado tiene su clave, y el español coincide con el modelo", () => {
  const faltan = [];
  const revisar = (clave, es) => {
    for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
      if (typeof d[clave] !== "string" || !d[clave].trim()) faltan.push(`${idioma}: ${clave}`);
    }
    assert.equal(DICCIONARIOS.es[clave], es, `es.json: ${clave} no dice lo mismo que el modelo`);
  };
  for (const [id, etiqueta] of Object.entries(D.recintos_etiquetas)) revisar(`js.tour.recinto.${id}`, etiqueta);
  for (const g of D.grupos_luz) revisar(`js.tour.luz.${g.id}`, g.etiqueta);
  for (const m of D.moviles) {
    revisar(`js.tour.pieza.${claveDeTexto(m.etiqueta)}`, m.etiqueta.toLowerCase());
    for (const d of Object.values(DICCIONARIOS)) assert.ok(d[`js.tour.clase.${m.clase}`], `falta js.tour.clase.${m.clase}`);
  }
  assert.deepEqual(faltan, []);
});

test("claveDeTexto: minúsculas, sin tildes y con «_» (la misma regla para todas las piezas)", () => {
  assert.equal(claveDeTexto("Puerta del clóset"), "puerta_del_closet");
  assert.equal(claveDeTexto("Cajón 1 profundo de la cocina"), "cajon_1_profundo_de_la_cocina");
  assert.equal(claveDeTexto("Puerta del mueble alto (platos)"), "puerta_del_mueble_alto_platos");
  assert.equal(claveDeTexto("  Baño  "), "bano");
});

test("claveDeTexto: quita toda marca combinante (\\p{M}), no sólo las del bloque U+0300–U+036F", () => {
  assert.equal(claveDeTexto("Ñandú Über Ça"), "nandu_uber_ca");
  assert.equal(claveDeTexto("Cafe\u0301"), "cafe");                    // ya descompuesto: e + acento agudo
  assert.equal(claveDeTexto("a\u1ab0b\u20ddc\ufe20"), "abc");          // marcas de otros bloques
  // y el código no escribe caracteres combinantes a mano (no se ven y se rompen al copiar)
  for (const carpeta of [join(SRC, "js"), join(SRC, "tour", "js")]) {
    for (const archivo of readdirSync(carpeta).filter((a) => a.endsWith(".js"))) {
      assert.doesNotMatch(readFileSync(join(carpeta, archivo), "utf8"), /\p{M}/u, `${archivo}: carácter combinante literal`);
    }
  }
});

test("en español las pistas son las mismas que antes de pasar a t()", () => {
  // fórmula anterior de interaccion.js: "Abrir " + etiqueta en minúsculas
  for (const m of D.moviles) {
    for (const objetivo of [0, 1]) {
      const antes = (objetivo < 0.5 ? "Abrir " : "Cerrar ") + m.etiqueta.replace(/^(Abrir|Cerrar)\s+/i, "").toLowerCase();
      assert.equal(etiquetaAccion({ tipo: "movil", ref: { m, objetivo } }), antes, m.nodo);
    }
  }
  // sin etiqueta: el nombre de la clase, como TEXTO_POR_CLASE
  assert.equal(etiquetaAccion({ tipo: "movil", ref: { m: { clase: "cajon" }, objetivo: 0 } }), "Abrir cajón");
  assert.equal(etiquetaAccion({ tipo: "movil", ref: { m: { clase: "otra" }, objetivo: 1 } }), "Cerrar pieza");
  assert.equal(t(MOTIVO_CAMINO), "Estás en el camino: retrocede un paso");
  assert.equal(t(MOTIVO_HOJA), "Corre primero la puerta del clóset");
  for (const [id, etiqueta] of Object.entries(D.recintos_etiquetas)) assert.equal(nombreRecinto(id, D.recintos_etiquetas), etiqueta);
  for (const g of D.grupos_luz) assert.equal(etiquetaGrupo(g), g.etiqueta);
  // un grupo o recinto que el diccionario no conoce queda con el texto del modelo
  assert.equal(etiquetaGrupo({ id: "nuevo", etiqueta: "Pasillo · techo", recinto: "Pasillo" }), "Pasillo · techo");
  assert.equal(nombreRecinto("Pasillo", { Pasillo: "Pasillo" }), "Pasillo");
  assert.equal(nombreRecinto("Sin_nombre"), "Sin_nombre");
  assert.equal(traduccion("js.tour.no.existe"), null);
});

// ---------------------------------------------------------------- en inglés y en francés
// Copia de web/src/js (i18n.js, idioma.js, textos-es.js), web/src/i18n y los módulos puros del tour, con la misma
// estructura de carpetas: cada importación es una instancia nueva con el IDIOMA de su <html lang>.
const copias = [];
after(() => { for (const d of copias) rmSync(d, { recursive: true, force: true }); });

async function tourEn(lang) {
  const dir = mkdtempSync(join(tmpdir(), "tour-textos-"));
  copias.push(dir);
  mkdirSync(join(dir, "js"));
  mkdirSync(join(dir, "tour", "js"), { recursive: true });
  for (const m of ["i18n.js", "idioma.js", "textos-es.js"]) cpSync(join(SRC, "js", m), join(dir, "js", m));
  for (const m of ["textos.js", "luces.js", "interfaz.js"]) cpSync(join(SRC, "tour", "js", m), join(dir, "tour", "js", m));
  cpSync(join(SRC, "i18n"), join(dir, "i18n"), { recursive: true });
  const url = (ruta) => pathToFileURL(join(dir, ruta)).href;
  const fetch = async (u) => respuesta(JSON.parse(readFileSync(fileURLToPath(new URL(String(u))), "utf8")));
  const mods = await conGlobales({ document: { documentElement: { lang } }, fetch }, async () => ({
    i18n: await import(url("js/i18n.js")),
    textos: await import(url("tour/js/textos.js")),
    luces: await import(url("tour/js/luces.js")),
  }));
  await mods.i18n.listo;
  return mods;
}

test("en inglés: recintos, grupos, piezas e interruptores salen de en.json", async () => {
  const { i18n, textos, luces } = await tourEn("en");
  assert.equal(i18n.IDIOMA, "en");
  assert.equal(textos.nombreRecinto("Dorm1", D.recintos_etiquetas), "Primary bedroom");
  assert.equal(textos.nombreRecinto("Palier", D.recintos_etiquetas), "Landing");
  const pieza = D.moviles.find((m) => m.etiqueta === "Puerta del clóset");
  assert.equal(i18n.t("js.tour.accion.abrir", { cosa: textos.nombrePieza(pieza) }), "Open the closet door");
  // una pieza nueva sin clave: el nombre de su clase en inglés, no media frase en español
  assert.equal(textos.nombrePieza({ etiqueta: "Puerta del altillo", clase: "puerta" }), "the door");
  assert.equal(textos.nombrePieza({ clase: "desconocida" }), "the item");
  const grupos = new Map(D.grupos_luz.map((g) => [g.id, { ...g, etiqueta: textos.etiquetaGrupo(g) }]));
  assert.equal(grupos.get("living_techo").etiqueta, "Living room · ceiling light");
  assert.equal(luces.textoInterruptor(["living_techo"], grupos, false), "Turn on Living room · ceiling light");
  assert.equal(luces.textoInterruptor(["living_techo", "balcon"], grupos, true),
    "Turn off Living room · ceiling light and Balcony · dining pendant light");
  assert.equal(luces.textoInterruptor(["no_existe"], grupos, true), "Turn off the light");
  assert.equal(i18n.t("js.tour.carga.modelo", { porcentaje: 40 }), "Loading the model… 40%");
});

test("en francés: los mismos textos salen de fr.json, con la lista y la tipografía del francés", async () => {
  const { i18n, textos, luces } = await tourEn("fr");
  assert.equal(i18n.IDIOMA, "fr");
  assert.equal(textos.nombreRecinto("Bano1", D.recintos_etiquetas), "Salle de bains principale");
  const nevera = D.moviles.find((m) => m.etiqueta === "Puerta de la nevera");
  assert.equal(i18n.t("js.tour.accion.cerrar", { cosa: textos.nombrePieza(nevera) }), "Fermer la porte du réfrigérateur");
  const grupos = new Map(D.grupos_luz.map((g) => [g.id, { ...g, etiqueta: textos.etiquetaGrupo(g) }]));
  assert.equal(luces.textoInterruptor(["dorm1_velador_izq", "dorm1_velador_der"], grupos, false),
    "Allumer Chambre principale · lampe de chevet gauche et Chambre principale · lampe de chevet droite");
  assert.equal(i18n.t(MOTIVO_HOJA), "Faites d'abord coulisser la porte du placard");
  assert.equal(i18n.t("js.tour.luz.interruptor", { nombre: "Séjour · plafonnier" }), "Lumière : Séjour · plafonnier");
});

// ---------------------------------------------------------------- selector de idioma del tour (interfaz.js)
function documentoFalso() {
  const oyentes = {};
  return {
    cookie: "",
    addEventListener: (tipo, fn) => { (oyentes[tipo] ??= []).push(fn); },
    disparar(tipo, idioma, extra = {}) {
      const enlace = { getAttribute: (n) => (n === "data-i18n-alternar" ? idioma : null) };
      const target = { closest: (sel) => (sel === "a[data-i18n-alternar]" && idioma !== undefined ? enlace : null) };
      for (const fn of oyentes[tipo] || []) fn({ type: tipo, target, button: 0, ...extra });
    },
  };
}

test("cookieIdioma: nf_lang por un año, para todo el sitio, SameSite=Lax y Secure; sólo es, en y fr", () => {
  assert.equal(cookieIdioma("en"), "nf_lang=en; path=/; max-age=31536000; SameSite=Lax; Secure");
  assert.equal(cookieIdioma("es"), "nf_lang=es; path=/; max-age=31536000; SameSite=Lax; Secure");
  for (const malo of ["de", "", "en; path=/admin", undefined, null]) assert.equal(cookieIdioma(malo), null, String(malo));
});

test("iniciarSelectorIdioma: el clic en un enlace del selector guarda la cookie antes de navegar", () => {
  const doc = documentoFalso();
  iniciarSelectorIdioma(doc);
  doc.disparar("click", undefined);                      // un clic fuera del selector no toca nada
  assert.equal(doc.cookie, "");
  doc.disparar("click", "de");                           // un valor fuera de la lista tampoco
  assert.equal(doc.cookie, "");
  doc.disparar("click", "fr");
  assert.equal(doc.cookie, "nf_lang=fr; path=/; max-age=31536000; SameSite=Lax; Secure");
  doc.disparar("auxclick", "en", { button: 2 });         // el botón derecho no elige por auxclick…
  assert.match(doc.cookie, /^nf_lang=fr;/);
  doc.disparar("auxclick", "en", { button: 1 });         // el central (abre otra pestaña) sí
  assert.match(doc.cookie, /^nf_lang=en;/);
  doc.disparar("contextmenu", "es", { button: 2 });      // …sino por el menú contextual («Abrir en una pestaña nueva»)
  assert.match(doc.cookie, /^nf_lang=es;/);
  doc.disparar("contextmenu", undefined, { button: 2 }); // el menú contextual fuera del selector no toca nada
  assert.match(doc.cookie, /^nf_lang=es;/);
});

test("main.js: los errores de carga salen al instante (no esperan `listo`) y se reescriben cuando llega el diccionario", () => {
  const fuente = sinComentarios(readFileSync(join(SRC, "tour", "js", "main.js"), "utf8"));
  assert.doesNotMatch(fuente, /await listo;\s*ui\.marcarError/, "sin red, `listo` tarda hasta 5 s");
  assert.equal([...fuente.matchAll(/ui\.marcarError\(/g)].length, 2, "sólo mostrarError llama a marcarError");
  for (const clave of ["js.tour.error.colisiones", "js.tour.error.modelo"]) assert.ok(fuente.includes(`mostrarError("${clave}")`), clave);
});
