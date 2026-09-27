// Exterior del bloque 08 (web/src/tour/js/exterior.js y prepararEscena en carga.js; contrato 2.3, sección 4): el paisaje
// va con un material sin luces, sombreado por vértice, emisión y bruma por momento, y en un grupo aparte de lo estático.
import { test } from "node:test";
import assert from "node:assert/strict";
import { THREE } from "../src/tour/js/three.js";
import {
  materialExterior, inyectar, sombrear, aplicarMomentoExterior, desplazamientoPx, esExterior, haciaSolDe, MARCA,
  prepararPanorama,
} from "../src/tour/js/exterior.js";
import { prepararEscena } from "../src/tour/js/carga.js";
import { MOMENTOS } from "../src/tour/js/cielo.js";

function fuente(extras = { exterior: true, exterior_capa: "cerca" }) {
  const map = new THREE.Texture();
  const emissiveMap = new THREE.Texture();
  const m = new THREE.MeshStandardMaterial({ name: "Depto_Ext_Mat_FachadaA", map, emissiveMap, emissive: 0xffffff });
  m.userData = { ...extras };
  return m;
}

test("materialExterior: MeshBasicMaterial con el mapa, colores por vértice y los extras del modelo", () => {
  const m = materialExterior(fuente());
  assert.ok(m.isMeshBasicMaterial);
  assert.equal(m.vertexColors, true);
  assert.ok(m.map);
  assert.equal(m.userData.exterior, true);
  assert.equal(m.userData.capa, "cerca");
  assert.ok(m.userData.uniformes.mapaEmisivo, "trae el mapa de emisión del glTF");
  const lejos = materialExterior(fuente({ exterior: true, exterior_capa: "lejos", tinte: [0.5, 0.75, 1.0] }));
  assert.equal(lejos.userData.capa, "lejos");
  assert.ok(Math.abs(lejos.userData.colorBase.g - 0.75) < 1e-6, "el tinte de los extras entra en el color base");
  const vidrio = new THREE.MeshStandardMaterial({ name: "Depto_Ext_Mat_VidrioBaranda", transparent: true, opacity: 0.28,
    depthWrite: false, side: THREE.DoubleSide });
  vidrio.userData = { exterior: true };
  const v = materialExterior(vidrio);
  assert.equal(v.transparent, true);
  assert.equal(v.opacity, 0.28);
  assert.equal(v.depthWrite, false);
  assert.equal(v.side, THREE.DoubleSide);
  assert.equal(v.userData.emisivoBase, null, "sin emisión: nada que sumar");
});

test("inyectar: suma la emisión con su mapa y la bruma antes de opaque_fragment en el shader real de three", () => {
  const frag = THREE.ShaderLib.basic.fragmentShader;
  assert.ok(frag.includes(MARCA), "three r160 trae la marca en MeshBasicMaterial");
  const m = materialExterior(fuente());
  const sh = { fragmentShader: frag, vertexShader: THREE.ShaderLib.basic.vertexShader, uniforms: {} };
  assert.equal(inyectar(sh, m.userData.uniformes), true);
  const i = sh.fragmentShader.indexOf("outgoingLight += colorEmisivo * texture2D( mapaEmisivo, vMapUv ).rgb;");
  assert.ok(i > 0 && i < sh.fragmentShader.indexOf(MARCA));
  assert.ok(sh.fragmentShader.includes("outgoingLight = mix( outgoingLight, colorNeblina, neblina );"));
  assert.ok(sh.fragmentShader.indexOf("saturacion );") < i, "la saturación va antes de la emisión");
  assert.ok(sh.uniforms.colorEmisivo && sh.uniforms.neblina && sh.uniforms.mapaEmisivo);
  assert.equal(inyectar({ fragmentShader: "void main() {}", uniforms: {} }, m.userData.uniformes), false);
});

test("sombrear: la cara hacia el sol es más clara, la de atrás toma sólo el ambiente y la base de la fachada se oscurece", () => {
  const geo = new THREE.BoxGeometry(2, 20, 2).toNonIndexed();
  geo.translate(0, 10, 0);                                         // de la calle (y = 0) a 20 m
  const sol = new THREE.Vector3(0, 0.5, -1).normalize();          // el sol hacia −Z (el frente del depto en glTF)
  sombrear(geo, sol, 0);
  const n = geo.getAttribute("normal"), c = geo.getAttribute("color"), p = geo.getAttribute("position");
  const media = (f) => {
    let s = 0, k = 0;
    for (let i = 0; i < n.count; i++) if (f(n.getX(i), n.getY(i), n.getZ(i), p.getY(i))) { s += c.getX(i); k++; }
    return s / k;
  };
  const frente = media((x, y, z, h) => z < -0.9 && h > 10);
  const atras = media((x, y, z, h) => z > 0.9 && h > 10);
  const base = media((x, y, z, h) => z < -0.9 && h < 1);
  const techo = media((x, y) => y > 0.9);
  assert.ok(frente > atras + 0.3, `${frente} ${atras}`);
  assert.ok(Math.abs(atras - 0.5) < 1e-6, `${atras}`);
  assert.ok(base < frente, `${base} ${frente}`);
  assert.ok(techo > 0.9, `${techo}`);
  const lejos = new THREE.PlaneGeometry(1, 1);
  sombrear(lejos, sol, 0, "lejos");
  assert.ok(Math.abs(lejos.getAttribute("color").getX(0) - 0.92) < 1e-6);
});

test("aplicarMomentoExterior: la emisión sigue a exterior.emision del modelo y la bruma sólo toca las lejanas", () => {
  const cerca = materialExterior(fuente());
  const lejos = materialExterior(fuente({ exterior: true, exterior_capa: "lejos" }));
  const ext = { emision: { dia: 0, tarde: 0.35, noche: 1 } };
  aplicarMomentoExterior([cerca, lejos], MOMENTOS.dia, "dia", ext);
  assert.equal(cerca.userData.uniformes.colorEmisivo.value.r, 0);
  assert.equal(cerca.userData.uniformes.neblina.value, 0);
  assert.ok(lejos.userData.uniformes.neblina.value > 0);
  aplicarMomentoExterior([cerca, lejos], MOMENTOS.noche, "noche", ext, [0.1, 0.1, 0.12]);
  assert.equal(cerca.userData.uniformes.colorEmisivo.value.r, 1);
  assert.ok(cerca.color.r < 0.1, "de noche las fachadas quedan casi negras");
  // el horizonte del panorama va con la intensidad del fondo del momento
  assert.ok(Math.abs(lejos.userData.uniformes.colorNeblina.value.b - 0.12 * MOMENTOS.noche.fondoIntensidad) < 1e-6);
  aplicarMomentoExterior([cerca], MOMENTOS.tarde, "tarde", ext);
  assert.ok(Math.abs(cerca.userData.uniformes.colorEmisivo.value.g - 0.35) < 1e-6);
  aplicarMomentoExterior([cerca], MOMENTOS.tarde, "tarde", {});     // sin exterior.emision: el respaldo del momento
  assert.ok(Math.abs(cerca.userData.uniformes.colorEmisivo.value.g - MOMENTOS.tarde.exterior.emisivo) < 1e-6);
  for (const id of ["dia", "tarde", "noche"]) assert.ok(MOMENTOS[id].exterior, `MOMENTOS.${id}.exterior`);
});

test("desplazamientoPx: giro antihorario del panorama, módulo el ancho", () => {
  assert.equal(desplazamientoPx(2048, 0), 0);
  assert.equal(desplazamientoPx(2048, 90), 512);
  assert.equal(desplazamientoPx(2048, 149.3), Math.round(149.3 / 360 * 2048));
  assert.equal(desplazamientoPx(2048, -90), 1536);
  assert.equal(desplazamientoPx(2048, 450), 512);
  assert.equal(desplazamientoPx(2048, 360), 0);
  // sin document (node) no gira ni mide el horizonte: devuelve la misma imagen
  const img = { width: 8, height: 4 };
  assert.deepEqual(prepararPanorama(img, 90, null), { fuente: img, horizonte: null });
});

test("haciaSolDe: opuesto a la dirección del sol de D.luces", () => {
  const v = haciaSolDe({ luces: [{ tipo: "sol", direccion: [0, -0.6, 0.8] }] });
  assert.ok(Math.abs(v.y - 0.6) < 1e-6 && Math.abs(v.z + 0.8) < 1e-6);
  assert.equal(haciaSolDe({}).y, 1);
});

test("prepararEscena: el exterior va a exteriorFusionado con su material barato, no a la fusión estática", () => {
  const raiz = new THREE.Group();
  const muro = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ name: "Depto_Mat_Muro" }));
  muro.name = "Depto_Muro";
  raiz.add(muro);
  const nodo = new THREE.Group();                                   // nodo glTF de varias primitivas: extras en el nodo
  nodo.name = "Depto_Ext_Vecino_E1";
  nodo.userData.exterior = true;
  const fach = new THREE.Mesh(new THREE.BoxGeometry(10, 20, 10), fuente());
  const techo = new THREE.Mesh(new THREE.PlaneGeometry(10, 10), fuente());
  techo.material.name = "Depto_Ext_Mat_Paleta";
  nodo.add(fach, techo);
  raiz.add(nodo);
  const D = { moviles: [], recintos: {}, luces: [{ tipo: "sol", direccion: [0, -1, 0] }], exterior: { suelo_y: -12.5 } };
  const p = prepararEscena(raiz, D);
  const estaticas = p.estaticoFusionado.children.map((m) => m.material.name);
  assert.deepEqual(estaticas, ["Depto_Mat_Muro"]);
  assert.equal(p.exteriorFusionado.name, "Depto_Exterior");
  assert.equal(p.exteriorFusionado.children.length, 2);
  for (const m of p.exteriorFusionado.children) {
    assert.ok(m.material.isMeshBasicMaterial);
    assert.ok(m.geometry.getAttribute("color"), "sombreado por vértice");
    assert.ok(esExterior(m.material));
  }
  assert.equal(p.materialesExterior.length, 2);
});
