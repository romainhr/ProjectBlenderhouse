// Cajones de clóset atados a sus hojas correderas (contrato v2, sección 1: depende_de y bloquea).
import { test } from "node:test";
import assert from "node:assert/strict";
import { puedeAbrir, cajonesQueCerrar, ESPERA_HOJA_S } from "../src/tour/js/bloqueos.js";
import { activar, pasoMundo, MOTIVO_HOJA } from "../src/tour/js/interaccion.js";
import { duracionPorClase } from "../src/tour/js/animacion.js";

function movil(nodo, extra = {}, abierto = false) {
  const t = abierto ? 1 : 0;
  return {
    m: { nodo, tipo: "corredera", eje: [1, 0], recorrido: 0.3, posicion: [0, 0, 0], cajas_locales: [], ...extra },
    t, objetivo: t, t0: t, fase: 1, nodo: { position: { set() {} }, rotation: { set() {} } },
  };
}

function celda({ aAbierta = false, bAbierta = false, cajonAbierto = false } = {}) {
  const cajones = ["Cajon1", "Cajon2"];
  const A = movil("PuertaA", { clase: "closet", bloquea: cajones }, aAbierta);
  const B = movil("PuertaB", { clase: "closet", bloquea: cajones }, bAbierta);
  const c1 = movil("Cajon1", { clase: "cajon", depende_de: ["PuertaA"] }, cajonAbierto);
  const c2 = movil("Cajon2", { clase: "cajon", depende_de: ["PuertaA"] });
  const moviles = [A, B, c1, c2];
  const porNodo = new Map(moviles.map((v) => [v.m.nodo, v]));
  return { A, B, c1, c2, moviles, porNodo };
}

const lejos = { x: 50, z: 50, radio: 0.2 };

test("puedeAbrir: el cajón sólo abre con la hoja A corrida y la B cerrada", () => {
  assert.equal(puedeAbrir(celda().c1, celda().porNodo), false);
  const abierta = celda({ aAbierta: true });
  assert.equal(puedeAbrir(abierta.c1, abierta.porNodo), true);
  const cruzadas = celda({ aAbierta: true, bAbierta: true });
  assert.equal(puedeAbrir(cruzadas.c1, cruzadas.porNodo), false);
  assert.equal(puedeAbrir(movil("Suelto", { clase: "cajon" }), new Map()), true);   // sin depende_de
});

test("activar: con la hoja cerrada el cajón no se abre y el aviso lo explica", () => {
  const c = celda();
  const estado = { moviles: c.moviles, porNodo: c.porNodo };
  assert.equal(activar(estado, { tipo: "movil", ref: c.c1 }, lejos), false);
  assert.equal(estado.motivo, MOTIVO_HOJA);
  assert.equal(c.c1.objetivo, 0);
});

test("activar: mover una hoja cierra antes sus cajones abiertos y la hoja espera a que terminen", () => {
  const c = celda({ aAbierta: true, cajonAbierto: true });
  assert.deepEqual(cajonesQueCerrar(c.A, c.porNodo).map((v) => v.m.nodo), ["Cajon1"]);
  const estado = { moviles: c.moviles, porNodo: c.porNodo, gruposLuz: new Map(), interruptores: [] };
  assert.equal(activar(estado, { tipo: "movil", ref: c.A }, lejos), true);     // cerrar la hoja A
  assert.equal(c.c1.objetivo, 0);
  assert.equal(c.A.objetivo, 0);
  assert.equal(c.A.espera, ESPERA_HOJA_S);
  // mientras el cajón se cierra la hoja no se mueve; después sí, hasta cerrar
  pasoMundo(estado, duracionPorClase("cajon") / 2, lejos);
  assert.equal(c.A.t, 1);
  assert.ok(c.c1.t < 1);
  for (let i = 0; i < 40; i++) pasoMundo(estado, 0.05, lejos);
  assert.equal(c.c1.t, 0);
  assert.equal(c.A.t, 0);
});

test("activar: la puerta de la nevera prende su grupo al abrirse y lo apaga al cerrarse (contrato 2.2, enciende)", () => {
  const puerta = movil("Nevera_Puerta", { clase: "nevera", tipo: "bisagra", angulo_abierto: 1.7, enciende: ["cocina_nevera"] });
  const grupo = { id: "cocina_nevera", movil: "Nevera_Puerta", encendido: false, intensidad: 0, _desde: 0, _hasta: 0,
    faseMs: 150, luces: [], clones: new Map() };
  const estado = { moviles: [puerta], porNodo: new Map([["Nevera_Puerta", puerta]]),
    gruposLuz: new Map([["cocina_nevera", grupo]]), interruptores: [] };
  assert.equal(activar(estado, { tipo: "movil", ref: puerta }, lejos), true);
  assert.equal(puerta.objetivo, 1);
  assert.equal(grupo.encendido, true);
  for (let i = 0; i < 10; i++) pasoMundo(estado, 0.05, lejos);
  assert.equal(grupo.intensidad, 1);
  assert.equal(activar(estado, { tipo: "movil", ref: puerta }, lejos), true);
  assert.equal(puerta.objetivo, 0);
  assert.equal(grupo.encendido, false);
});

test("activar: PuertaLavaplatos1 cierra antes los cajones del módulo 3 que bloquea (se cruzaban al girar)", () => {
  const c3s = movil("Cajon3Sup", { clase: "cajon" }, true);
  const c3i = movil("Cajon3Inf", { clase: "cajon" });
  const hoja = movil("PuertaLavaplatos1", { clase: "mueble", tipo: "bisagra", angulo_abierto: 1.66,
    bloquea: ["Cajon3Sup", "Cajon3Inf"] });
  const moviles = [c3s, c3i, hoja];
  const estado = { moviles, porNodo: new Map(moviles.map((v) => [v.m.nodo, v])), gruposLuz: new Map(), interruptores: [] };
  assert.equal(activar(estado, { tipo: "movil", ref: hoja }, lejos), true);
  assert.equal(c3s.objetivo, 0);                 // el cajón abierto empieza a cerrarse
  assert.equal(hoja.espera, ESPERA_HOJA_S);      // y la hoja espera a que termine
  assert.equal(c3i.objetivo, 0);
});
