import { test } from "node:test";
import assert from "node:assert/strict";
import {
  deducirGrupos, nombreAmpolleta, colorLinealAHex, NOMBRES_RECINTO, interruptorEncendido, ordenarInterruptores,
  estadoGruposParaMomento, textoInterruptor, KELVIN_2700,
} from "../src/tour/js/luces.js";
import { MOMENTOS, MOMENTO_POR_DEFECTO } from "../src/tour/js/cielo.js";

const recintos = { Living: [0, 0], Dorm1: [5, 0] };

test("nombreAmpolleta: quita el prefijo Depto_Luz_", () => {
  assert.equal(nombreAmpolleta("Depto_Luz_Depto_Mueble_Living_Colgante_Filamento"), "Depto_Mueble_Living_Colgante_Filamento");
  assert.equal(nombreAmpolleta("SinPrefijo"), "SinPrefijo");
});

test("colorLinealAHex: codifica a sRGB; blanco y negro en los extremos", () => {
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

test("KELVIN_2700 es lineal: codificado a sRGB da ≈ (255, 174, 89), no el (255, 221, 173) de ~4200 K", () => {
  assert.equal(colorLinealAHex(KELVIN_2700).toLowerCase(), "#ffae59");
});

const GRUPOS = [
  { id: "living_techo", encendido: true }, { id: "living_lampara_pie", encendido: false },
  { id: "dorm1_velador", encendido: false }, { id: "dorm2_aplique_izq", encendido: false },
  { id: "dorm2_aplique_der", encendido: false }, { id: "bano1", encendido: true },
];

test("estadoGruposParaMomento: tarde y noche respetan grupos_luz[].encendido; el día apaga todo", () => {
  for (const momento of ["tarde", "noche"]) {
    const e = estadoGruposParaMomento(GRUPOS, MOMENTOS[momento].lucesEncendidas);
    assert.equal(e.get("living_techo"), true, momento);
    assert.equal(e.get("bano1"), true, momento);
    for (const id of ["living_lampara_pie", "dorm1_velador", "dorm2_aplique_izq", "dorm2_aplique_der"]) {
      assert.equal(e.get(id), false, `${momento}: ${id} debe nacer apagado`);
    }
  }
  const dia = estadoGruposParaMomento(GRUPOS, MOMENTOS.dia.lucesEncendidas);
  assert.ok([...dia.values()].every((v) => v === false));
  assert.equal(MOMENTOS[MOMENTO_POR_DEFECTO].lucesEncendidas, true); // el momento inicial prende los techos
});

test("estadoGruposParaMomento: usa encendidoInicial (autor) aunque el usuario haya cambiado encendido", () => {
  const e = estadoGruposParaMomento([{ id: "dorm1_velador", encendido: true, encendidoInicial: false }], true);
  assert.equal(e.get("dorm1_velador"), false);
});

test("textoInterruptor: la pista nombra el grupo; la placa doble une las dos etiquetas", () => {
  const g = new Map([["living_techo", { etiqueta: "Living · techo" }], ["balcon", { etiqueta: "Balcón · colgante del comedor" }]]);
  assert.equal(textoInterruptor(["living_techo"], g, false), "Encender Living · techo");
  assert.equal(textoInterruptor(["balcon"], g, true), "Apagar Balcón · colgante del comedor");
  assert.equal(textoInterruptor(["living_techo", "balcon"], g, true), "Apagar Living · techo y Balcón · colgante del comedor");
  assert.equal(textoInterruptor(["no_existe"], g, false), "Encender la luz");
});

test("contrato 2.2: los grupos de un móvil no cambian con el momento ni salen en el panel", async () => {
  const { gruposDeMovil, gruposDelPanel } = await import("../src/tour/js/luces.js");
  const grupos = new Map([
    ["cocina_techo", { id: "cocina_techo", encendido: true }],
    ["cocina_nevera", { id: "cocina_nevera", encendido: false, movil: "Depto_Mueble_Nevera_Puerta" }],
  ]);
  const tarde = estadoGruposParaMomento(grupos.values(), true);
  assert.equal(tarde.get("cocina_techo"), true);
  assert.equal(tarde.has("cocina_nevera"), false);
  assert.deepEqual(gruposDelPanel(grupos).map((g) => g.id), ["cocina_techo"]);
  assert.deepEqual(gruposDeMovil({ enciende: ["cocina_nevera"] }, 1), [["cocina_nevera", true]]);
  assert.deepEqual(gruposDeMovil({ enciende: ["cocina_nevera"] }, 0), [["cocina_nevera", false]]);
  assert.deepEqual(gruposDeMovil({}, 1), []);
});
