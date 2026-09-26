import { test } from "node:test";
import assert from "node:assert/strict";
import { easeInOutCubic, duracionPorClase, iniciarToggle, pasoAnimacion, congelar } from "../src/tour/js/animacion.js";

test("easeInOutCubic: extremos fijos, simétrico en 0,5 y monótono", () => {
  assert.equal(easeInOutCubic(0), 0);
  assert.equal(easeInOutCubic(1), 1);
  assert.ok(Math.abs(easeInOutCubic(0.5) - 0.5) < 1e-9);
  let anterior = -1;
  for (let x = 0; x <= 1; x += 0.05) {
    const y = easeInOutCubic(x);
    assert.ok(y >= anterior, `no monótono en x=${x}`);
    anterior = y;
  }
});

test("duracionPorClase: cajón 0,35 s; el resto (incluida sin clase) 0,6 s", () => {
  assert.equal(duracionPorClase("cajon"), 0.35);
  assert.equal(duracionPorClase("puerta"), 0.6);
  assert.equal(duracionPorClase("ventana"), 0.6);
  assert.equal(duracionPorClase(undefined), 0.6);
});

test("iniciarToggle: alterna 0<->1 y reinicia la fase", () => {
  const cerrada = { t: 0, objetivo: 0, t0: 0, fase: 0.6 };
  const abre = iniciarToggle(cerrada);
  assert.equal(abre.objetivo, 1);
  assert.equal(abre.fase, 0);
  assert.equal(abre.t0, 0);
});

test("pasoAnimacion: llega exactamente al objetivo tras `duracion` y es monótono", () => {
  const duracion = 0.6;
  let estado = iniciarToggle({ t: 0, objetivo: 0, t0: 0, fase: 0 }); // -> objetivo 1
  let anterior = -1;
  const pasos = 30;
  for (let i = 0; i < pasos; i++) {
    estado = pasoAnimacion(estado, duracion / pasos, duracion);
    assert.ok(estado.t >= anterior - 1e-9, `retrocedió en el paso ${i}`);
    anterior = estado.t;
  }
  assert.ok(Math.abs(estado.t - 1) < 1e-9);
});

test("pasoAnimacion: invertir a mitad de camino parte del punto actual, no del extremo", () => {
  const duracion = 0.6;
  let estado = iniciarToggle({ t: 0, objetivo: 0, t0: 0, fase: 0 });
  estado = pasoAnimacion(estado, duracion / 2, duracion); // a medio camino (~0.5 por la simetría del ease)
  const tMedioCamino = estado.t;
  assert.ok(tMedioCamino > 0.1 && tMedioCamino < 0.9);
  const invertido = iniciarToggle(estado); // ahora objetivo 0
  assert.equal(invertido.objetivo, 0);
  assert.equal(invertido.t0, tMedioCamino);
  const siguiente = pasoAnimacion(invertido, 0.01, duracion);
  assert.ok(siguiente.t < tMedioCamino, "debería empezar a cerrar desde donde iba, no desde 1");
});

test("congelar: fija el objetivo en la apertura actual (la hoja topó con el caminante)", () => {
  const enMovimiento = { t: 0.37, objetivo: 1, t0: 0, fase: 0.2 };
  const detenido = congelar(enMovimiento);
  assert.equal(detenido.objetivo, 0.37);
  assert.equal(detenido.t, 0.37);
  assert.equal(detenido.fase, 0);
});
