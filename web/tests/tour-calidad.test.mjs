// Resolución adaptable (calidad.js) y elección de la variante de texturas (carga.js), según el diagnóstico de
// texturas del 2026-09-26.
import { test } from "node:test";
import assert from "node:assert/strict";

globalThis.window = globalThis.window || { devicePixelRatio: 2, location: { search: "" } };
const { crearCalidad } = await import("../src/tour/js/calidad.js");

function rendererFalso() {
  const r = { pr: null, setPixelRatio(v) { this.pr = v; } };
  return r;
}

test("techo de pixelRatio: 1,75 en escritorio y 1,5 en táctil", () => {
  const e = rendererFalso(); crearCalidad(e, false); assert.equal(e.pr, 1.75);
  const t = rendererFalso(); crearCalidad(t, true); assert.equal(t.pr, 1.5);
});

test("no avisa al crear, pero sí al cambiar de resolución", () => {
  let avisos = 0;
  const r = rendererFalso();
  const c = crearCalidad(r, false, () => { avisos++; });
  assert.equal(avisos, 0);
  for (let i = 0; i < 24; i++) c.registrarCuadro(40);
  assert.equal(c.factor, 0.75);
  assert.equal(avisos, 1);
});

test("los cuadros de compilación (> 200 ms) no bajan la resolución", () => {
  const r = rendererFalso();
  const c = crearCalidad(r, false);
  c.registrarCuadro(3500);
  for (let i = 0; i < 23; i++) c.registrarCuadro(3);
  assert.equal(c.factor, 1);
});
