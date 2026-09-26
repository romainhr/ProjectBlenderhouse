import { test } from "node:test";
import assert from "node:assert/strict";
import { chocaCaja, estadoMovil, chocaMovil, libre, libreCercano, mover } from "../src/tour/js/colision.js";

test("chocaCaja: dentro y fuera de la caja, más el margen del radio", () => {
  const caja = [0, 2, 0, 2];
  assert.equal(chocaCaja(1, 1, caja, 0.2), true);           // centro, adentro
  assert.equal(chocaCaja(2.05, 1, caja, 0.2), true);        // justo afuera pero dentro del radio
  assert.equal(chocaCaja(3, 1, caja, 0.2), false);          // lejos
  assert.equal(chocaCaja(-0.1, -0.1, caja, 0.2), true);     // esquina, dentro del radio
});

test("estadoMovil: bisagra gira, corredera se desplaza a lo largo del eje", () => {
  const puerta = { tipo: "bisagra", posicion: [1, 0, 2], angulo_abierto: 1.5708 };
  assert.deepEqual(estadoMovil(puerta, 0), { x: 1, z: 2, ang: 0 });
  const e1 = estadoMovil(puerta, 1);
  assert.equal(e1.x, 1); assert.equal(e1.z, 2);
  assert.ok(Math.abs(e1.ang - 1.5708) < 1e-9);

  const corredera = { tipo: "corredera", posicion: [0, 0, 0], eje: [-1, 0], recorrido: 1, abierta: false };
  const cerrada = estadoMovil(corredera, 0);
  assert.ok(Math.abs(cerrada.x) < 1e-9 && Math.abs(cerrada.z) < 1e-9);
  const abierta = estadoMovil(corredera, 1);
  assert.ok(Math.abs(abierta.x - -1) < 1e-9);
});

test("chocaMovil: usa las cajas locales de la pieza, giradas al mundo", () => {
  const m = { tipo: "bisagra", posicion: [0, 0, 0], angulo_abierto: 0, cajas_locales: [[-0.5, 0.5, -0.1, 0.1]] };
  const v = { m, t: 0 };
  assert.equal(chocaMovil(0, 0, v, 0, 0.05), true);
  assert.equal(chocaMovil(0, 1, v, 0, 0.05), false);
});

test("libre: cajas estáticas y móviles bloquean; los cajones no", () => {
  const estaticos = [[0, 1, 0, 1]];
  const cajon = { m: { tipo: "bisagra", posicion: [3, 0, 3], angulo_abierto: 0, clase: "cajon",
    cajas_locales: [[-0.3, 0.3, -0.3, 0.3]] }, t: 0 };
  const puerta = { m: { tipo: "bisagra", posicion: [5, 0, 5], angulo_abierto: 0,
    cajas_locales: [[-0.3, 0.3, -0.3, 0.3]] }, t: 0 };
  assert.equal(libre(0.5, 0.5, estaticos, [], 0.2), false);
  assert.equal(libre(10, 10, estaticos, [], 0.2), true);
  assert.equal(libre(3, 3, estaticos, [cajon], 0.2), true);   // el cajón no bloquea
  assert.equal(libre(5, 5, estaticos, [puerta], 0.2), false); // la puerta sí
});

test("libreCercano: si el punto está libre lo devuelve tal cual; si no, busca alrededor", () => {
  const estaticos = [[-0.3, 0.3, -0.3, 0.3]];
  assert.deepEqual(libreCercano(5, 5, estaticos, [], 0.2), [5, 5]);
  const [x, z] = libreCercano(0, 0, estaticos, [], 0.1);
  assert.equal(libre(x, z, estaticos, [], 0.1), true);
});

test("mover: desliza a lo largo de una pared en vez de detenerse en la esquina", () => {
  const estaticos = [[1, 2, -5, 5]]; // pared vertical en x=[1,2]
  const [x, z] = mover(0.5, 0, 0.8, 0.8, estaticos, [], 0.2);
  // el movimiento en X se recorta por la pared, pero Z avanza igual (deslizamiento)
  assert.ok(x < 0.9, `x=${x} debería quedar antes de la pared`);
  assert.ok(z > 0.5, `z=${z} debería haber avanzado`);
});

test("mover: sin obstáculos, llega al destino completo", () => {
  const [x, z] = mover(0, 0, 1, -1, [], [], 0.2);
  assert.ok(Math.abs(x - 1) < 1e-6);
  assert.ok(Math.abs(z - -1) < 1e-6);
});
