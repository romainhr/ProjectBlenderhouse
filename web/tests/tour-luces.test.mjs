import { test } from "node:test";
import assert from "node:assert/strict";
import {
  deducirGrupos, nombreAmpolleta, colorLinealAHex, NOMBRES_RECINTO, interruptorEncendido, ordenarInterruptores,
} from "../src/tour/js/luces.js";

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

test("interruptorEncendido: encendido si alguno de sus grupos lo está (el estado sale de los grupos)", () => {
  const gruposLuz = new Map([["living_techo", { encendido: true }], ["balcon", { encendido: false }]]);
  assert.equal(interruptorEncendido(["living_techo", "balcon"], gruposLuz), true);
  assert.equal(interruptorEncendido(["balcon"], gruposLuz), false);
  assert.equal(interruptorEncendido(["no_existe"], gruposLuz), false);
  gruposLuz.get("living_techo").encendido = false;
  assert.equal(interruptorEncendido(["living_techo", "balcon"], gruposLuz), false);
});

test("ordenarInterruptores: las teclas con registro propio van antes que placas y lámparas", () => {
  const lista = [
    { nodo: "Depto_Interruptor_Dorm1", grupos: ["dorm1_techo", "paso_d1"], tecla: null },
    { nodo: "Depto_Mueble_D1_LamparaMesa_Pantalla", grupos: ["dorm1_velador"], tecla: null },
    { nodo: "Depto_Interruptor_Dorm1_1_Tecla", grupos: ["dorm1_techo"], tecla: "Depto_Interruptor_Dorm1_1_Tecla" },
    { nodo: "Depto_Interruptor_Hall", grupos: ["hall_techo"], tecla: "Depto_Interruptor_Hall_Tecla" },
    { nodo: "Depto_Interruptor_Dorm1_2_Tecla", grupos: ["paso_d1"], tecla: "Depto_Interruptor_Dorm1_2_Tecla" },
  ];
  const orden = ordenarInterruptores(lista).map((i) => i.nodo);
  assert.deepEqual(orden.slice(0, 2), ["Depto_Interruptor_Dorm1_1_Tecla", "Depto_Interruptor_Dorm1_2_Tecla"]);
  assert.equal(orden.length, lista.length);
  // una placa simple (tecla distinta de su nodo) no cuenta como tecla
  assert.ok(orden.indexOf("Depto_Interruptor_Hall") >= 2);
});
