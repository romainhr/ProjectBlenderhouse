// Vista «Textos» del portal (web/src/admin/js/vista-textos.js) con los tres idiomas de la migración 0005, probada de
// punta a punta contra el modo simulado con un DOM falso mínimo (sin dependencias): qué campos pinta cada fila, qué
// guarda, cómo valida y qué pasa si la base todavía no tiene la 0005.
//   cd web && npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { crearApiSimulada } from "../src/admin/js/api-simulada.js";
import { ErrorApi, MENSAJES } from "../src/admin/js/errores.js";
import { AVISO_SIN_IDIOMAS, MENSAJES_VALOR, TEXTO_FIJO } from "../src/admin/js/logica-contenido.js";
import { crearVistaTextos } from "../src/admin/js/vista-textos.js";

// ---------------------------------------------------------------------------------------------- DOM falso
// Sólo lo que usan ui.js y vista-textos.js: createElement, createTextNode, propiedades, atributos, eventos,
// append/replaceChildren, textContent, dataset y querySelector("#id").
class NodoFalso {
  constructor(etiqueta) {
    this.tagName = etiqueta.toUpperCase();
    this.hijos = [];
    this.atributos = new Map();
    this.escuchas = new Map();
    this.dataset = {};
    this.texto = "";
    this.className = "";
    this.value = "";
    this.disabled = false;
    this.readOnly = false;
  }
  setAttribute(k, v) { this.atributos.set(k, String(v)); }
  getAttribute(k) { return this.atributos.has(k) ? this.atributos.get(k) : null; }
  removeAttribute(k) { this.atributos.delete(k); }
  addEventListener(tipo, f) {
    if (!this.escuchas.has(tipo)) this.escuchas.set(tipo, []);
    this.escuchas.get(tipo).push(f);
  }
  /** Dispara el evento y devuelve las promesas de los manejadores asíncronos. */
  disparar(tipo) {
    const ev = { type: tipo, target: this, preventDefault() { this.prevenido = true; } };
    return Promise.all((this.escuchas.get(tipo) || []).map((f) => f(ev)));
  }
  append(...nodos) { for (const n of nodos) this.hijos.push(n); }
  replaceChildren(...nodos) { this.hijos = []; this.append(...nodos); }
  get textContent() { return this.hijos.length ? this.hijos.map((h) => h.textContent).join("") : this.texto; }
  set textContent(v) { this.hijos = []; this.texto = String(v); }
  get isConnected() { return true; }
  focus() { globalThis.document.activeElement = this; }
  querySelector(selector) {
    const id = selector.replace(/^#/, "");
    return buscar(this, (n) => n.id === id)[0] || null;
  }
}
class TextoFalso extends NodoFalso {
  constructor(t) { super("#text"); this.texto = t; }
}

function buscar(raiz, cumple) {
  const r = [];
  const recorrer = (n) => { for (const h of n.hijos) { if (cumple(h)) r.push(h); recorrer(h); } };
  recorrer(raiz);
  return r;
}

globalThis.Node = NodoFalso;
globalThis.document = {
  activeElement: null,
  createElement: (e) => new NodoFalso(e),
  createTextNode: (t) => new TextoFalso(t),
  getElementById: () => null,
};

class AlmacenFalso {
  constructor() { this.m = new Map(); }
  getItem(k) { return this.m.has(k) ? this.m.get(k) : null; }
  setItem(k, v) { this.m.set(k, String(v)); }
  removeItem(k) { this.m.delete(k); }
}

const HOY = "2026-10-05";
const pausa = async () => { for (let i = 0; i < 5; i++) await new Promise((r) => setImmediate(r)); };

function raizFalsa() {
  const raiz = new NodoFalso("section");
  for (const id of ["textos-grupos", "textos-aviso", "textos-recargar"]) {
    const n = new NodoFalso(id === "textos-recargar" ? "button" : "div");
    n.id = id;
    raiz.append(n);
  }
  return raiz;
}

/** Vista cargada con el modo simulado; `guardados` registra cada llamada a contenido.guardar. */
async function montar({ idiomas = true, guardar } = {}) {
  const api = crearApiSimulada({ almacen: new AlmacenFalso(), retardo: 0, hoy: HOY, idiomas });
  await api.iniciarSesion("dueno@example.com", "x");
  const guardados = [];
  const original = api.contenido.guardar;
  api.contenido.guardar = (clave, cambios, opciones) => {
    guardados.push({ clave, cambios, opciones });
    return guardar ? guardar(clave, cambios, opciones) : original(clave, cambios, opciones);
  };
  const raiz = raizFalsa();
  const vista = crearVistaTextos({ raiz, api });
  vista.mostrar();
  await pausa();
  return { api, raiz, vista, guardados, aviso: raiz.querySelector("#textos-aviso") };
}

/** La fila (form.fila-texto) de una clave, con sus controles por idioma. */
function filaDe(raiz, clave) {
  const form = buscar(raiz, (n) => n.className === "fila-texto" && buscar(n, (c) => c.tagName === "CODE" && c.textContent === clave).length)[0];
  assert.ok(form, `no se pintó la fila ${clave}`);
  const controles = buscar(form, (n) => n.tagName === "INPUT" || n.tagName === "TEXTAREA");
  const boton = buscar(form, (n) => n.tagName === "BUTTON")[0];
  const porIdioma = Object.fromEntries(controles.map((c) => [c.lang, c]));
  const errorDe = (c) => buscar(form, (n) => n.id === `${c.id}-error`)[0];
  const etiquetas = buscar(form, (n) => n.tagName === "LABEL").map((l) => [l.htmlFor, l.textContent]);
  return { form, controles, boton, porIdioma, errorDe, etiquetas };
}

async function escribir(control, valor) {
  control.value = valor;
  await control.disparar("input");
}

// ---------------------------------------------------------------------------------------------- pruebas
test("vista textos: cada texto tiene español, inglés y francés; los precios, un solo campo", async () => {
  const { raiz, aviso } = await montar();
  assert.equal(aviso.textContent, "", "con la 0005 aplicada no hay aviso");

  const hero = filaDe(raiz, "hero.bajada");
  assert.deepEqual(hero.controles.map((c) => [c.tagName, c.lang]), [["TEXTAREA", "es"], ["TEXTAREA", "en"], ["TEXTAREA", "fr"]]);
  assert.deepEqual(hero.etiquetas.map(([, t]) => t), ["Español (obligatorio)", "Inglés (opcional)", "Francés (opcional)"]);
  assert.ok(hero.etiquetas.every(([para], i) => para === hero.controles[i].id), "cada rótulo apunta a su campo");
  const grupo = buscar(hero.form, (n) => n.getAttribute("role") === "group")[0];
  const titulo = buscar(hero.form, (n) => n.id === grupo.getAttribute("aria-labelledby"))[0];
  assert.equal(titulo.textContent, "Bajada de la portada", "el grupo de los tres campos se nombra con la etiqueta");
  assert.match(hero.porIdioma.en.value, /^Sample text/, "trae la traducción guardada");

  const cocina = filaDe(raiz, "espacio.cocina.titulo");
  assert.equal(cocina.porIdioma.fr.value, "", "null se muestra como campo vacío");
  const ayudaFr = buscar(cocina.form, (n) => n.id === `${cocina.porIdioma.fr.id}-ayuda`)[0];
  assert.equal(ayudaFr.textContent, `Vacío: el sitio en francés muestra ${TEXTO_FIJO}.`, "la interfaz dice qué pasa si queda vacío");
  assert.ok(cocina.porIdioma.fr.getAttribute("aria-describedby").split(" ").includes(ayudaFr.id));

  const noche = filaDe(raiz, "tarifa.noche");
  assert.equal(noche.controles.length, 1, "el precio no se traduce");
  assert.deepEqual(noche.etiquetas.map(([, t]) => t), ["Tarifa por noche (ejemplo)"]);
});

test("vista textos: guardar manda sólo los idiomas que cambiaron, vacío -> null, y la fila queda limpia", async () => {
  const { raiz, vista, guardados } = await montar();
  const f = filaDe(raiz, "espacio.cocina.titulo");
  assert.equal(f.boton.disabled, true);
  await escribir(f.porIdioma.fr, "  Cuisine ");
  await escribir(f.porIdioma.en, "   ");
  assert.equal(f.boton.disabled, false);
  assert.equal(vista.hayCambios(), true);

  await f.form.disparar("submit");
  await pausa();
  assert.equal(guardados.length, 1);
  assert.deepEqual(guardados[0], { clave: "espacio.cocina.titulo", cambios: { valor_en: null, valor_fr: "Cuisine" },
    opciones: { idiomas: true } }, "el español no cambió: no se reenvía");
  assert.deepEqual([f.porIdioma.es.value, f.porIdioma.en.value, f.porIdioma.fr.value], ["Cocina", "", "Cuisine"],
    "los campos muestran lo que guardó la base");
  assert.equal(vista.hayCambios(), false);
  assert.equal(f.boton.disabled, true);

  const precio = filaDe(raiz, "tarifa.limpieza");
  await escribir(precio.porIdioma.es, "16.000");
  await precio.form.disparar("submit");
  await pausa();
  assert.deepEqual(guardados[1].cambios, { valor: "16000" }, "el precio guarda un solo valor");
});

// Hallazgo P1: guardar una fila no debe devolver a su valor cargado los idiomas que otro cambió entretanto (otra
// pestaña, el teléfono o el SQL Editor). La vista está cargada; «otro lado» guarda con la misma API simulada.
test("vista textos: guardar el español no pisa el inglés que otra pestaña cambió después de cargar", async () => {
  const { api, raiz, guardados } = await montar();
  const f = filaDe(raiz, "espacio.cocina.titulo");
  assert.equal(f.porIdioma.en.value, "Kitchen", "la vista cargó el inglés de antes");
  await api.contenido.guardar("espacio.cocina.titulo", { valor_en: "Kitchen and dining" });   // otra pestaña
  guardados.length = 0;

  await escribir(f.porIdioma.es, "Cocina equipada");
  await f.form.disparar("submit");
  await pausa();
  assert.deepEqual(guardados.map((g) => g.cambios), [{ valor: "Cocina equipada" }], "sólo el español en el PATCH");
  const fila = (await api.contenido.listar()).filas.find((x) => x.clave === "espacio.cocina.titulo");
  assert.deepEqual([fila.valor, fila.valor_en, fila.valor_fr], ["Cocina equipada", "Kitchen and dining", null],
    "el inglés de la otra pestaña se conserva");
  assert.equal(f.porIdioma.en.value, "Kitchen and dining", "después de guardar, la fila muestra lo que tiene la base");
  const estado = buscar(f.form, (n) => n.getAttribute("role") === "status")[0];
  assert.match(estado.textContent, /^Guardado a las /);
  assert.equal(f.boton.disabled, true);
});

test("vista textos: guardar el inglés no pisa el español ni el francés que se cambiaron en otro lado", async () => {
  const { api, raiz, guardados } = await montar();
  const f = filaDe(raiz, "hero.bajada");
  await api.contenido.guardar("hero.bajada", { valor: "Bajada corregida en el teléfono.", valor_fr: "Texte corrigé." });
  guardados.length = 0;

  await escribir(f.porIdioma.en, "New English lead.");
  await f.form.disparar("submit");
  await pausa();
  assert.deepEqual(guardados.map((g) => g.cambios), [{ valor_en: "New English lead." }]);
  const fila = (await api.contenido.listar()).filas.find((x) => x.clave === "hero.bajada");
  assert.deepEqual([fila.valor, fila.valor_en, fila.valor_fr], ["Bajada corregida en el teléfono.", "New English lead.", "Texte corrigé."]);
  assert.deepEqual([f.porIdioma.es.value, f.porIdioma.fr.value], ["Bajada corregida en el teléfono.", "Texte corrigé."]);
});

test("vista textos: si lo escrito vuelve a lo cargado no se llama a la base", async () => {
  const { raiz, vista, guardados } = await montar();
  const f = filaDe(raiz, "espacio.living.titulo");
  const antes = f.porIdioma.es.value;
  await escribir(f.porIdioma.es, antes + " x");
  assert.equal(f.boton.disabled, false);
  await escribir(f.porIdioma.es, antes);
  assert.equal(f.boton.disabled, true);
  await f.form.disparar("submit");            // p. ej. Enter en un campo: el envío implícito no debe mandar nada
  await pausa();
  assert.equal(guardados.length, 0);
  assert.equal(vista.hayCambios(), false);
});

test("vista textos: valida cada idioma con la lógica de logica-contenido.js y no llama si hay errores", async () => {
  const { raiz, guardados } = await montar();
  const f = filaDe(raiz, "hero.bajada");
  await escribir(f.porIdioma.es, "  ");
  await escribir(f.porIdioma.fr, "x".repeat(4001));
  await f.form.disparar("submit");
  await pausa();
  assert.equal(guardados.length, 0);
  assert.equal(f.errorDe(f.porIdioma.es).textContent, MENSAJES_VALOR.vacio);
  assert.equal(f.errorDe(f.porIdioma.en).textContent, "", "el inglés estaba bien");
  assert.equal(f.errorDe(f.porIdioma.fr).textContent, MENSAJES_VALOR.largo);
  assert.equal(f.porIdioma.es.getAttribute("aria-invalid"), "true");
  assert.equal(f.porIdioma.fr.getAttribute("aria-invalid"), "true");
  assert.equal(globalThis.document.activeElement, f.porIdioma.es, "el foco va al primer campo con error");
  await escribir(f.porIdioma.es, "Hola");
  assert.equal(f.errorDe(f.porIdioma.es).textContent, "", "al corregir se limpia el error");
});

test("vista textos sin la 0005: lo explica, pinta sólo el español y lo sigue guardando", async () => {
  const { raiz, aviso, guardados } = await montar({ idiomas: false });
  assert.equal(aviso.textContent, AVISO_SIN_IDIOMAS);
  assert.equal(aviso.dataset.tipo, "aviso");
  const f = filaDe(raiz, "hero.bajada");
  assert.deepEqual(f.controles.map((c) => c.lang), ["es"]);
  assert.deepEqual(f.etiquetas.map(([, t]) => t), ["Bajada de la portada"], "como antes de la 0005");
  await escribir(f.porIdioma.es, "Texto nuevo en español.");
  await f.form.disparar("submit");
  await pausa();
  assert.deepEqual(guardados[0], { clave: "hero.bajada", cambios: { valor: "Texto nuevo en español." }, opciones: { idiomas: false } });
  const estado = buscar(f.form, (n) => n.getAttribute("role") === "status")[0];
  assert.match(estado.textContent, /^Guardado a las /);
});

test("vista textos: si al guardar la base rechaza las traducciones, se explica en la fila y no se pierde lo escrito", async () => {
  const { raiz, vista } = await montar({
    guardar: () => Promise.reject(new ErrorApi({ estado: 400, codigo: "falta_idiomas" })),
  });
  const f = filaDe(raiz, "espacio.living.titulo");
  await escribir(f.porIdioma.en, "Lounge");
  await f.form.disparar("submit");
  await pausa();
  const errorFila = buscar(f.form, (n) => n.id === f.porIdioma.es.id.replace(/-es$/, "-error"))[0];
  assert.equal(errorFila.textContent, MENSAJES.falta_idiomas);
  assert.ok(f.porIdioma.en.getAttribute("aria-describedby").split(" ").includes(errorFila.id), "el campo anuncia el error de la fila");
  assert.equal(f.porIdioma.en.value, "Lounge");
  assert.equal(f.porIdioma.en.readOnly, false);
  assert.equal(f.boton.disabled, false, "se puede reintentar");
  assert.equal(vista.hayCambios(), true);
});

test("vista textos: al cerrar sesión se vacía y el próximo ingreso vuelve a detectar los idiomas", async () => {
  const { api, raiz, vista, aviso } = await montar({ idiomas: false });
  assert.equal(aviso.dataset.tipo, "aviso");
  vista.reiniciar();
  assert.equal(raiz.querySelector("#textos-grupos").hijos.length, 0);
  assert.equal(aviso.textContent, "");
  assert.equal(vista.hayCambios(), false);

  // entretanto se aplicó la 0005: la próxima carga pinta los tres idiomas y quita el aviso
  const conIdiomas = crearApiSimulada({ almacen: new AlmacenFalso(), retardo: 0, hoy: HOY });
  await conIdiomas.iniciarSesion("dueno@example.com", "x");
  api.contenido.listar = () => conIdiomas.contenido.listar();
  vista.mostrar();
  await pausa();
  assert.equal(filaDe(raiz, "hero.bajada").controles.length, 3);
  assert.equal(aviso.textContent, "");
});
