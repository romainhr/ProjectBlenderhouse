// Pruebas de web/src/js/reserva-logica.js con el ejecutor incluido en Node (sin dependencias):
//   cd web && npm test     (node --test tests/*.test.mjs)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  CELDA_MIN, MENSAJES, PRECIO_MAX, SEPARACION_MESES, TARIFA, clp, codigoError, esIso, fijarTarifas, grillaMes,
  hayMesSiguiente, hoyIso, mesesPorPagina, nocheOcupada, noches, salidaMaxima, solapa, sumarDias, tarifaVigente, total,
  validarDatos, validarRango,
} from "../src/js/reserva-logica.js";

const HOY = "2026-10-05";
const OCUPADOS = [{ entrada: "2026-10-10", salida: "2026-10-13" }, { entrada: "2026-10-20", salida: "2026-10-22" }];

test("fechas ISO: válidas, inválidas y aritmética sin corrimiento de huso", () => {
  assert.ok(esIso("2026-02-28"));
  assert.ok(!esIso("2026-02-30"));
  assert.ok(!esIso("26-2-3"));
  assert.equal(sumarDias("2026-12-31", 1), "2027-01-01");
  assert.equal(sumarDias("2026-03-01", -1), "2026-02-28");
  assert.equal(noches("2026-10-10", "2026-10-13"), 3);
  // «hoy» en el huso de la propiedad (America/Santiago, UTC−3 en octubre), no el del visitante ni el UTC
  assert.equal(hoyIso(new Date("2026-10-06T02:30:00Z")), "2026-10-05");   // 23:30 en Chile, ya el 6 en UTC
  assert.equal(hoyIso(new Date("2026-10-06T03:30:00Z")), "2026-10-06");   // 00:30 en Chile
  assert.equal(hoyIso(new Date("2026-06-15T03:30:00Z")), "2026-06-14");   // invierno: UTC−4, 23:30 en Chile
});

test("solape en intervalos semiabiertos: se puede entrar el día que otro sale", () => {
  assert.ok(solapa("2026-10-11", "2026-10-14", "2026-10-10", "2026-10-13"));
  assert.ok(!solapa("2026-10-13", "2026-10-15", "2026-10-10", "2026-10-13"));
  assert.ok(!solapa("2026-10-08", "2026-10-10", "2026-10-10", "2026-10-13"));
  assert.ok(nocheOcupada("2026-10-12", OCUPADOS));
  assert.ok(!nocheOcupada("2026-10-13", OCUPADOS));
});

test("validarRango aplica las mismas reglas que la base de datos", () => {
  assert.deepEqual(validarRango("2026-10-06", "2026-10-09", OCUPADOS, HOY), { ok: true, noches: 3 });
  assert.equal(validarRango("2026-10-04", "2026-10-07", OCUPADOS, HOY).error, "fecha_pasada");
  assert.equal(validarRango("2026-10-06", "2026-10-07", OCUPADOS, HOY).error, "min_noches");
  assert.equal(validarRango("2026-10-06", sumarDias("2026-10-06", 31), [], HOY).error, "max_noches");
  assert.equal(validarRango("2026-10-08", "2026-10-11", OCUPADOS, HOY).error, "fechas_ocupadas");
  assert.equal(validarRango("2026-10-13", "2026-10-15", OCUPADOS, HOY).ok, true);
  assert.equal(validarRango("2027-11-01", "2027-11-04", [], HOY).error, "fecha_lejana");
  assert.equal(validarRango("", "2026-10-09", [], HOY).error, "fechas_requeridas");
});

test("salidaMaxima corta en la próxima llegada o en el máximo de noches", () => {
  assert.equal(salidaMaxima("2026-10-06", OCUPADOS), "2026-10-10");
  assert.equal(salidaMaxima("2026-10-23", OCUPADOS), sumarDias("2026-10-23", TARIFA.maxNoches));
});

test("total y formato en pesos chilenos", () => {
  assert.deepEqual(total(3), { noches: 3, alojamiento: 174000, limpieza: 15000, total: 189000 });
  assert.equal(total(0).total, 0);
  assert.equal(clp(189000).replace(/\s/g, " "), "CLP 189.000");
});

test("fijarTarifas: sólo enteros del rango del CHECK de la 0003 y noche mayor que 0; TARIFA no cambia", () => {
  try {
    assert.deepEqual(tarifaVigente(), { noche: TARIFA.noche, limpieza: TARIFA.limpieza });
    assert.equal(PRECIO_MAX, 10_000_000);
    for (const malo of [
      { noche: 0, limpieza: 15000 }, { noche: -1, limpieza: 15000 }, { noche: 1.5, limpieza: 15000 },
      { noche: "70000", limpieza: 15000 }, { noche: NaN, limpieza: 0 }, { noche: PRECIO_MAX + 1, limpieza: 0 },
      { noche: 70000, limpieza: -1 }, { noche: 70000, limpieza: "0" }, { noche: 70000, limpieza: PRECIO_MAX + 1 },
      { noche: 70000 }, { limpieza: 0 }, {}, null, undefined, 70000,
    ]) {
      assert.equal(fijarTarifas(malo), false, `debería rechazar ${JSON.stringify(malo)}`);
      assert.deepEqual(tarifaVigente(), { noche: 58000, limpieza: 15000 }, "un rechazo no cambia nada");
    }
    assert.equal(fijarTarifas({ noche: 70000, limpieza: 0 }), true);      // limpieza sin cobro
    assert.deepEqual(tarifaVigente(), { noche: 70000, limpieza: 0 });
    assert.deepEqual(total(3), { noches: 3, alojamiento: 210000, limpieza: 0, total: 210000 });
    assert.equal(total(0).total, 0);
    assert.deepEqual(total(3, TARIFA), { noches: 3, alojamiento: 174000, limpieza: 15000, total: 189000 });   // pura
    assert.equal(fijarTarifas({ noche: PRECIO_MAX, limpieza: PRECIO_MAX }), true);   // los extremos del CHECK
    assert.throws(() => { tarifaVigente().noche = 1; }, TypeError);            // congelada: no se cambia por fuera
    assert.deepEqual([TARIFA.noche, TARIFA.limpieza], [58000, 15000]);         // los valores por defecto siguen
    assert.ok(Object.isFrozen(TARIFA));
  } finally {
    fijarTarifas(TARIFA);                                                      // vuelve a los de ejemplo
  }
  assert.deepEqual(total(3), { noches: 3, alojamiento: 174000, limpieza: 15000, total: 189000 });
});

test("MENSAJES no llevan precios: al fijar otras tarifas no quedan desfasados", () => {
  try {
    fijarTarifas({ noche: 70000, limpieza: 0 });
    for (const [codigo, texto] of Object.entries(MENSAJES)) {
      assert.doesNotMatch(texto, /CLP|\$|\d{1,3}\.\d{3}|\d{4,}/, `${codigo} menciona un precio fijo: «${texto}»`);
    }
  } finally {
    fijarTarifas(TARIFA);
  }
});

test("reserva.js calcula con la tarifa vigente y fija las que lee contenido-publico.js", () => {
  const fuente = readFileSync(new URL("../src/js/reserva.js", import.meta.url), "utf8");
  assert.match(fuente, /import \{ tarifas \} from "\.\/contenido-publico\.js";/);
  assert.match(fuente, /tarifas\(\)\.then\(\(t\) => \{ if \(t && fijarTarifas\(t\)\) resumen\(\); \}\)\.catch\(/);
  assert.doesNotMatch(fuente, /TARIFA\.(noche|limpieza)|TARIFA\[/, "el precio sale de tarifaVigente(), no de TARIFA");
  assert.match(fuente, /clp\(tarifaVigente\(\)\.noche\)/);
});

test("grillaMes: semanas completas, lunes primero", () => {
  const oct = grillaMes(2026, 9);                        // octubre 2026 empieza en jueves
  assert.deepEqual(oct[0].slice(0, 4), [null, null, null, "2026-10-01"]);
  assert.ok(oct.every((s) => s.length === 7));
  assert.equal(oct.flat().filter(Boolean).length, 31);
});

test("mesesPorPagina: dos meses solo si caben 2 × 7 días de 48 px más la separación", () => {
  assert.equal(2 * 7 * CELDA_MIN + SEPARACION_MESES, 704);
  assert.equal(mesesPorPagina(320), 1);
  assert.equal(mesesPorPagina(703), 1);
  assert.equal(mesesPorPagina(704), 2);
  assert.equal(mesesPorPagina(738), 2);                  // #meses a 1280 px, con el resumen al lado
  assert.equal(mesesPorPagina(0), 1);                    // sin medir (display: none) se pinta uno
});

test("hayMesSiguiente: la última página alcanzable es la que contiene `hasta`", () => {
  const HASTA = "2027-10-26";
  assert.equal(hayMesSiguiente(2027, 8, 2, HASTA), false);   // septiembre + octubre: octubre ya contiene HASTA
  assert.equal(hayMesSiguiente(2027, 8, 1, HASTA), true);    // septiembre solo: falta octubre
  assert.equal(hayMesSiguiente(2027, 9, 1, HASTA), false);   // octubre contiene HASTA
  assert.equal(hayMesSiguiente(2027, 7, 2, HASTA), true);    // agosto + septiembre: falta octubre
  assert.equal(hayMesSiguiente(2026, 11, 1, "2027-01-01"), true);   // cruza de año
  assert.equal(hayMesSiguiente(2026, 11, 2, "2027-01-31"), false);
});

test("validarDatos replica los CHECK de la tabla", () => {
  const bien = { nombre: "Ana Pérez", email: "ana@ejemplo.cl", telefono: "+56 9 1234 5678", huespedes: 2, acepta: true };
  assert.deepEqual(validarDatos(bien), {});
  assert.deepEqual(Object.keys(validarDatos({ ...bien, nombre: " ", email: "x@y", huespedes: 5, acepta: false })).sort(),
                   ["acepta", "email", "huespedes", "nombre"]);
  assert.equal(validarDatos({ ...bien, telefono: "llámame" }).telefono, "telefono");
  assert.equal(validarDatos({ ...bien, mensaje: "x".repeat(1001) }).mensaje, "mensaje");
});

test("codigoError reconoce los errores del servidor y cae en «red» si no", () => {
  assert.equal(codigoError({ message: "fechas_ocupadas" }), "fechas_ocupadas");
  assert.equal(codigoError(new Error("Failed to fetch")), "red");
  assert.equal(codigoError(null), "red");
});
