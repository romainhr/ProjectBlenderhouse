// prepararEscena (carga.js) con una escena three.js mínima: las ampolletas quedan en `sueltos` (antes se sacaban de
// la fusión y no se dibujaban) y los grupos guardan su estado de autor para aplicarMomento().
import { test } from "node:test";
import assert from "node:assert/strict";
import { THREE } from "../src/tour/js/three.js";
import { prepararEscena } from "../src/tour/js/carga.js";
import { estadoGruposParaMomento } from "../src/tour/js/luces.js";

function malla(nombre, material, padre) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.1, 0.1), material);
  m.name = nombre;
  padre.add(m);
  return m;
}

function escena() {
  const raiz = new THREE.Group();
  const muro = new THREE.MeshStandardMaterial({ name: "Depto_Mat_Muro" });
  const bombilla = new THREE.MeshStandardMaterial({ name: "Depto_Mat_Bombilla", emissive: 0xffaa55 });
  malla("Depto_Muro", muro, raiz);
  malla("Depto_Mueble_Living_Colgante_Filamento", bombilla, raiz);
  malla("Depto_Mueble_D1_LamparaMesa_Filamento", bombilla, raiz);
  const pantalla = malla("Depto_Mueble_D1_LamparaMesa_Pantalla", muro, raiz);
  pantalla.userData.grupo_luz = "dorm1_velador";
  const placa = malla("Depto_Interruptor_Living", muro, raiz);
  placa.userData.grupo_luz = "living_techo";
  const tecla = malla("Depto_Interruptor_Living_Tecla", muro, placa);
  tecla.userData.grupo_luz = "living_techo";
  const D = {
    moviles: [],
    recintos: { Living: [0, 0], Dorm1: [5, 0] },
    luces: [
      { nombre: "Depto_Luz_Depto_Mueble_Living_Colgante_Filamento", tipo: "puntual", posicion: [0, 2, 0],
        potencia_w: 40, grupo: "living_techo", color: [1, 0.423, 0.0996],
        ampolleta: "Depto_Mueble_Living_Colgante_Filamento" },
      { nombre: "Depto_Luz_Depto_Mueble_D1_LamparaMesa_Filamento", tipo: "puntual", posicion: [5, 0.9, 0],
        potencia_w: 12, grupo: "dorm1_velador", color: [1, 0.423, 0.0996],
        ampolleta: "Depto_Mueble_D1_LamparaMesa_Filamento" },
      { nombre: "Depto_Luz_Sol", tipo: "sol", direccion: [0, -1, 0], intensidad: 3 },
    ],
    grupos_luz: [
      { id: "living_techo", etiqueta: "Living · techo", recinto: "Living", encendido: true },
      { id: "dorm1_velador", etiqueta: "Dormitorio principal · lámpara del velador", recinto: "Dorm1", encendido: false },
    ],
    interruptores: [
      { nodo: "Depto_Interruptor_Living", grupos: ["living_techo"], tecla: "Depto_Interruptor_Living_Tecla" },
      { nodo: "Depto_Interruptor_Living_Tecla", grupos: ["living_techo"], tecla: "Depto_Interruptor_Living_Tecla" },
      { nodo: "Depto_Mueble_D1_LamparaMesa_Pantalla", grupos: ["dorm1_velador"], tecla: null },
    ],
  };
  return { raiz, D };
}

test("prepararEscena: cada luces[].ampolleta termina en `sueltos` (se dibuja) y no en la fusión estática", () => {
  const { raiz, D } = escena();
  const p = prepararEscena(raiz, D);
  const nombres = p.sueltos.map((o) => o.name);
  for (const l of D.luces.filter((x) => x.tipo === "puntual")) {
    assert.ok(nombres.includes(l.ampolleta), `falta ${l.ampolleta} en sueltos`);
  }
  // la tecla sigue colgando de su placa (no se suelta aparte) y la fusión no trae el material emisivo
  assert.ok(!nombres.includes("Depto_Interruptor_Living_Tecla"));
  const fusionadas = p.estaticoFusionado.children.map((m) => m.name);
  assert.ok(!fusionadas.some((n) => n.includes("Bombilla")), fusionadas.join(","));
});

test("prepararEscena: los grupos nacen con su estado de autor y el momento inicial lo respeta", () => {
  const { raiz, D } = escena();
  const p = prepararEscena(raiz, D);
  assert.equal(p.gruposLuz.get("living_techo").encendidoInicial, true);
  assert.equal(p.gruposLuz.get("dorm1_velador").encendidoInicial, false);
  const tarde = estadoGruposParaMomento(p.gruposLuz.values(), true);
  assert.equal(tarde.get("living_techo"), true);
  assert.equal(tarde.get("dorm1_velador"), false);
  // el filamento del velador apagado no brilla; el del techo sí
  const amp = new Map(p.sueltos.map((o) => [o.name, o]));
  assert.equal(amp.get("Depto_Mueble_D1_LamparaMesa_Filamento").material.emissiveIntensity, 0);
  assert.ok(amp.get("Depto_Mueble_Living_Colgante_Filamento").material.emissiveIntensity > 0);
});

test("crearLucesTHREE: un domo con cono_deg da un solo foco hacia abajo con toda la intensidad", async () => {
  const { crearLucesTHREE, intensidadBase, INTENSIDAD_POR_WATT } = await import("../src/tour/js/luces.js");
  const l = { nombre: "Depto_Luz_X", tipo: "puntual", posicion: [1, 2, 3], potencia_w: 40, color: [1, 0.42, 0.1],
    cono_deg: 60, direccion: [0, -1, 0] };
  const [foco, ...resto] = crearLucesTHREE(THREE, l);
  assert.equal(resto.length, 0);              // sin la puntual complementaria (corrección 07b, ronda 2: rendimiento)
  assert.ok(foco.isSpotLight);
  assert.deepEqual([foco.position.x, foco.position.y, foco.position.z], [1, 2, 3]);
  assert.ok(Math.abs(foco.angle - Math.PI / 3) < 1e-9);
  assert.ok(Math.abs(intensidadBase(foco) - 40 * INTENSIDAD_POR_WATT) < 1e-9);
  const g = new THREE.Group();
  g.add(foco);
  g.updateMatrixWorld(true);
  const p = new THREE.Vector3().setFromMatrixPosition(foco.target.matrixWorld);
  assert.deepEqual([p.x, p.y, p.z].map((v) => Math.round(v * 1000) / 1000), [1, 1, 3]);
  // sin cono: una sola puntual con toda la intensidad
  const sola = crearLucesTHREE(THREE, { ...l, cono_deg: undefined });
  assert.equal(sola.length, 1);
  assert.equal(intensidadBase(sola[0]), 40 * INTENSIDAD_POR_WATT);
});
