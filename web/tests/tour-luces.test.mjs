import { test } from "node:test";
import assert from "node:assert/strict";
import { deducirGrupos, nombreAmpolleta, colorLinealAHex, NOMBRES_RECINTO } from "../src/tour/js/luces.js";

const recintos = { Living: [0, 0], Dorm1: [5, 0] };

test("nombreAmpolleta: quita el prefijo Depto_Luz_", () => {
  assert.equal(nombreAmpolleta("Depto_Luz_Depto_Mueble_Living_Colgante_Filamento"), "Depto_Mueble_Living_Colgante_Filamento");
  assert.equal(nombreAmpolleta("SinPrefijo"), "SinPrefijo");
});

test("colorLinealAHex: 2700 K lineal da un naranja cálido, blanco y negro en los extremos", () => {
  assert.equal(colorLinealAHex([1, 0.72, 0.42]).toLowerCase(), "#ffddad");
  assert.equal(colorLinealAHex([1, 1, 1]), "#ffffff");
  assert.equal(colorLinealAHex([0, 0, 0]), "#000000");
});

test("deducirGrupos: agrupa por el recinto más cercano en XZ cuando no hay grupos_luz", () => {
  const luces = [
    { nombre: "Depto_Luz_A", tipo: "puntual", posicion: [0.1, 2, 0.1], potencia_w: 40 },
    { nombre: "Depto_Luz_B", tipo: "puntual", posicion: [5.2, 2, -0.1], potencia_w: 12 },
    { nombre: "Depto_Luz_Sol", tipo: "sol", direccion: [0, -1, 0], intensidad: 3 },
  ];
  const { luces: out, grupos } = deducirGrupos({ luces, recintos });
  assert.equal(out[0].grupo, "Living");
  assert.equal(out[1].grupo, "Dorm1");
  assert.equal(out[2].grupo, undefined); // el sol no tiene grupo
  assert.equal(out[0].ampolleta, "A");
  assert.equal(grupos.length, 2);
  const living = grupos.find((g) => g.id === "Living");
  assert.equal(living.etiqueta, NOMBRES_RECINTO.Living);
  assert.equal(living.encendido, false);
});

test("deducirGrupos: respeta grupos_luz de autor si ya vienen completos", () => {
  const luces = [{ nombre: "Depto_Luz_A", tipo: "puntual", posicion: [0, 2, 0], grupo: "living_techo" }];
  const grupos_luz = [{ id: "living_techo", etiqueta: "Living · techo", recinto: "Living", encendido: true }];
  const { luces: out, grupos } = deducirGrupos({ luces, recintos, grupos_luz });
  assert.equal(out[0].grupo, "living_techo");
  assert.deepEqual(grupos, grupos_luz);
});

test("deducirGrupos: varias luces del mismo recinto comparten un solo grupo", () => {
  const luces = [
    { nombre: "Depto_Luz_A", tipo: "puntual", posicion: [0.1, 2, 0.1], potencia_w: 40 },
    { nombre: "Depto_Luz_B", tipo: "puntual", posicion: [-0.2, 2, 0.2], potencia_w: 40 },
  ];
  const { grupos } = deducirGrupos({ luces, recintos });
  assert.equal(grupos.length, 1);
});
