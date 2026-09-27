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

test("crearLucesTHREE: alcance_m corta la luz (contrato 2.2: la de la nevera no alumbra a través de su cuerpo)", async () => {
  const { crearLucesTHREE, DISTANCIA_LUZ } = await import("../src/tour/js/luces.js");
  const l = { nombre: "Depto_Luz_Nevera", tipo: "puntual", posicion: [0, 1.7, 0], potencia_w: 4, color: [1, 0.8, 0.63] };
  assert.equal(crearLucesTHREE(THREE, l)[0].distance, DISTANCIA_LUZ);
  assert.equal(crearLucesTHREE(THREE, { ...l, alcance_m: 0.9 })[0].distance, 0.9);
});

test("prepararEscena: un entorno local (contrato 2.2, sección 6) va sólo a sus materiales dentro de su caja", async () => {
  const { enEntorno } = await import("../src/tour/js/carga.js");
  const { raiz, D } = escena();
  const acero = new THREE.MeshStandardMaterial({ name: "Depto_Mat_NeveraAcero", metalness: 1, roughness: 1 });
  const dentro = malla("Depto_Cocina_NeveraCuerpo", acero, raiz);
  dentro.position.set(1, 1, 1);
  const fuera = malla("Depto_Bano_Grifo", acero, raiz);
  fuera.position.set(9, 1, 9);
  const muro = malla("Depto_Cocina_Muro", new THREE.MeshStandardMaterial({ name: "Depto_Mat_Muro" }), raiz);
  muro.position.set(1, 1, 1);
  D.entornos = [{ id: "cocina", imagen: "tex/entorno_cocina.jpg", caja: [0, 2, 0, 2], materiales: ["Depto_Mat_NeveraAcero"] }];
  assert.equal(enEntorno(D.entornos[0], acero, 1, 1), true);
  assert.equal(enEntorno(D.entornos[0], acero, 9, 9), false);
  const tex = new THREE.Texture();
  const p = prepararEscena(raiz, D, { entornos: new Map([["cocina", tex]]) });
  const conEntorno = p.estaticoFusionado.children.filter((m) => m.material.envMap === tex);
  assert.equal(conEntorno.length, 1);
  assert.equal(conEntorno[0].material.userData.entornoLocal, "cocina");
  assert.equal(conEntorno[0].material.name, "Depto_Mat_NeveraAcero");
  // el grifo del baño (fuera de la caja) y el muro (otro material) siguen con el entorno general
  assert.equal(p.estaticoFusionado.children.filter((m) => m.material.envMap === null).length >= 2, true);
  assert.equal(acero.envMap, null);              // el material original no se toca
});

test("proyeccionCaja: el reflejo del entorno local se corta contra la caja del recinto (paralaje)", async () => {
  const { proyeccionCaja, MARCA_REFLEJO } = await import("../src/tour/js/carga.js");
  const sh = { uniforms: {}, vertexShader: THREE.ShaderLib.physical.vertexShader,
    fragmentShader: THREE.ShaderLib.physical.fragmentShader };
  const e = { caja: [0, 2, 0, 3], alto: [0, 2.4], centro: [1, 1.3, 1.5] };
  assert.equal(proyeccionCaja(sh, e), true);
  assert.ok(sh.vertexShader.includes("vPosMundo = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;"));
  assert.ok(!sh.fragmentShader.includes("#include <envmap_physical_pars_fragment>"));
  assert.ok(sh.fragmentShader.includes(MARCA_REFLEJO + "\n reflectVec = proyectarCaja( reflectVec );"));
  assert.deepEqual(sh.uniforms.uCajaMax.value.toArray(), [2, 2.4, 3]);
  assert.deepEqual(sh.uniforms.uCentroEntorno.value.toArray(), [1, 1.3, 1.5]);
});

test("varianteEntorno: de día la variante del día, con luces la de las luces; una textura sola vale para todo", async () => {
  const { varianteEntorno } = await import("../src/tour/js/carga.js");
  const dia = new THREE.Texture(), luces = new THREE.Texture();
  assert.equal(varianteEntorno({ dia, luces }, false), dia);
  assert.equal(varianteEntorno({ dia, luces }, true), luces);
  assert.equal(varianteEntorno({ luces }, false), luces);
  assert.equal(varianteEntorno(dia, true), dia);
  assert.equal(varianteEntorno(undefined, true), null);
});

test("actualizarEntornos: la variante y la intensidad del entorno local siguen a la luz de la cocina", async () => {
  const { actualizarEntornos } = await import("../src/tour/js/carga.js");
  const dia = new THREE.Texture(), luces = new THREE.Texture();
  const mat = new THREE.MeshStandardMaterial({ name: "Depto_Mat_NeveraAcero" });
  mat.userData = { entornoLocal: "cocina", variantesEntorno: { dia, luces }, grupoEntorno: "cocina_techo" };
  const grupos = new Map([["cocina_techo", { encendido: false }]]);
  const inten = { luces: 0.75, dia: 2.0 };
  assert.equal(actualizarEntornos([mat], grupos, inten), true);
  assert.equal(mat.envMap, dia);
  assert.equal(mat.envMapIntensity, 2.0);
  assert.equal(actualizarEntornos([mat], grupos, inten), false);      // sin cambios, no pide redibujar
  grupos.get("cocina_techo").encendido = true;
  assert.equal(actualizarEntornos([mat], grupos, inten), true);
  assert.equal(mat.envMap, luces);
  assert.equal(mat.envMapIntensity, 0.75);
});
