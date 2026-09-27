// Exterior del bloque 08 (web/src/tour/js/exterior.js y prepararEscena en carga.js; contrato 2.4, sección 4): el paisaje
// va con un material sin luces, sombreado por vértice, emisión y bruma por momento, y en un grupo aparte de lo estático.
// Corrección 08, ronda 1: sombreado acotado y por momento, curva Filmic, vidrio con reflejo, bruma por azimut y la
// mancha de luz aditiva de las luminarias.
import { test } from "node:test";
import assert from "node:assert/strict";
import { THREE } from "../src/tour/js/three.js";
import {
  materialExterior, inyectar, sombrear, sombrearExterior, aplicarMomentoExterior, desplazamientoPx, esExterior,
  haciaSolDe, MARCA, prepararPanorama, SOMBREADO, factorSombreado, curvaFilmic, texturaHorizonte, horizonteMedio,
} from "../src/tour/js/exterior.js";
import { FILMIC } from "../src/tour/js/filmic.js";
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
  assert.ok(sh.fragmentShader.includes("outgoingLight = mix( outgoingLight, acesFondoExt( neb ), neblina );"));
  const curva = sh.fragmentShader.indexOf("outgoingLight = curvaFilmicExt( outgoingLight * exposicion );");
  assert.ok(curva > i, "la curva Filmic va después de la emisión");
  assert.equal(m.toneMapped, false, "sin el ACES del resto del visor");
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
  assert.ok(Math.abs(atras - SOMBREADO.ambiente) < 1e-6, `${atras}`);
  assert.ok(base < frente, `${base} ${frente}`);
  assert.ok(techo > 0.9, `${techo}`);
  const lejos = new THREE.PlaneGeometry(1, 1);
  sombrear(lejos, sol, 0, "lejos");
  assert.ok(Math.abs(lejos.getAttribute("color").getX(0) - SOMBREADO.lejos) < 1e-6);
});

// Una cara de una normal dada a 20 m sobre la calle (fuera del oscurecimiento de los primeros 6 m).
function kDe(normal, sol, f = {}) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array([0, 20, 0]), 3));
  geo.setAttribute("normal", new THREE.BufferAttribute(new Float32Array(normal), 3));
  sombrear(geo, sol, 0, "cerca", SOMBREADO, f);
  return geo.getAttribute("color").getX(0);
}

test("sombrear: lo que mira hacia abajo no queda negativo ni más claro que una fachada en sombra, y hacia arriba no pasa de 1,6", () => {
  const sol = new THREE.Vector3(0, 0.74, -0.67).normalize();       // el sol de día, a 48°
  const abajo = kDe([0, -1, 0], sol);
  const fachadaSombra = kDe([0, 0, 1], sol);                       // de espaldas al sol
  const arriba = kDe([0, 1, 0], sol);
  assert.ok(abajo > 0 && abajo >= SOMBREADO.kMin - 1e-6, `abajo ${abajo}`);   // antes: ambiente + cielo · n.y = −0,6
  assert.ok(SOMBREADO.kMin >= 0.25, "la cota de abajo no deja caras casi negras");
  assert.ok(abajo < fachadaSombra, `${abajo} < ${fachadaSombra}`);
  assert.ok(arriba <= SOMBREADO.kMax + 1e-6 && SOMBREADO.kMax <= 2, `arriba ${arriba}`);   // antes: 2,17 al sol
  assert.ok(arriba > fachadaSombra);
  // en cualquier dirección, y con el sol de frente, dentro de [kMin, kMax]
  for (let i = 0; i < 200; i++) {
    const n = new THREE.Vector3(Math.sin(i * 1.7), Math.cos(i * 0.91), Math.sin(i * 2.3 + 1)).normalize();
    const k = kDe([n.x, n.y, n.z], n);
    assert.ok(k >= SOMBREADO.kMin - 1e-6 && k <= SOMBREADO.kMax + 1e-6, `${k}`);
  }
  // el momento escala el cielo y el sol: la tarde, con el sol bajo, deja las caras en sombra más oscuras que el día
  const f = { cielo: MOMENTOS.tarde.exterior.cielo, sol: MOMENTOS.tarde.exterior.sol };
  const tardeSombra = kDe([0, 0, 1], sol, f);
  assert.ok(tardeSombra < fachadaSombra, `${tardeSombra} ${fachadaSombra}`);
  assert.ok(Math.abs(factorSombreado(0, 0, 1, sol) - SOMBREADO.ambiente) < 1e-9);
});

test("sombrearExterior: rehace el color por vértice de todo el grupo con el sol del momento, sin crear otro atributo", () => {
  const grupo = new THREE.Group();
  const geo = new THREE.BoxGeometry(2, 2, 2).toNonIndexed();
  geo.translate(0, 20, 0);
  const malla = new THREE.Mesh(geo, materialExterior(fuente()));
  grupo.add(malla);
  const alto = new THREE.Vector3(0, 1, 0), bajo = new THREE.Vector3(0, 0.2, -1).normalize();
  assert.equal(sombrearExterior(grupo, alto, 0), 1);
  const attr = geo.getAttribute("color");
  const frenteAlto = attr.getX(geo.getAttribute("normal").array.findIndex((v, i) => i % 3 === 2 && v < -0.9) / 3);
  sombrearExterior(grupo, bajo, 0);
  assert.equal(geo.getAttribute("color"), attr, "el mismo atributo");
  const frenteBajo = attr.getX(geo.getAttribute("normal").array.findIndex((v, i) => i % 3 === 2 && v < -0.9) / 3);
  assert.ok(frenteBajo > frenteAlto, `con el sol bajo de frente, la cara al sol es más clara (${frenteBajo} > ${frenteAlto})`);
});

test("haciaSolDe: con la elevación del momento conserva el azimut del sol de la escena", () => {
  const D = { luces: [{ tipo: "sol", direccion: [0.3, -0.57, 0.76] }] };
  const base = haciaSolDe(D);
  const tarde = haciaSolDe(D, 12.1);
  assert.ok(Math.abs(Math.asin(tarde.y) * 180 / Math.PI - 12.1) < 1e-6);
  assert.ok(Math.abs(Math.atan2(tarde.z, tarde.x) - Math.atan2(base.z, base.x)) < 1e-9);
  assert.ok(Math.abs(tarde.length() - 1) < 1e-9);
});

test("curvaFilmic: la curva medida en Blender es creciente y deja el gris medio cerca de Filmic (≈ 0,2 lineal)", () => {
  for (const fila of ["ninguno", "contraste_medio"]) {
    const c = FILMIC[fila];
    assert.ok(c.length >= 32);
    for (let i = 1; i < c.length; i++) assert.ok(c[i] >= c[i - 1] - 1e-6, `${fila} ${i}`);
  }
  const medio = curvaFilmic(0.18);
  assert.ok(medio > 0.12 && medio < 0.3, `${medio}`);
  assert.ok(curvaFilmic(0.02) > 0.02, "Filmic levanta las sombras más que ACES (≈ 0,007)");
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
  assert.ok(Math.abs(cerca.userData.uniformes.colorEmisivo.value.r - MOMENTOS.noche.exterior.brillo) < 1e-6);
  assert.ok(MOMENTOS.noche.exterior.brillo > 1, "de noche las ventanas vecinas brillan sobre el cielo");
  assert.equal(cerca.userData.uniformes.filaCurva.value, 1, "de noche, Medium Contrast como render_08");
  assert.ok(cerca.color.r < 0.1, "de noche las fachadas quedan casi negras");
  // el horizonte del panorama va con la intensidad del fondo del momento
  assert.ok(Math.abs(lejos.userData.uniformes.colorNeblina.value.b - 0.12 * MOMENTOS.noche.fondoIntensidad) < 1e-6);
  aplicarMomentoExterior([cerca], MOMENTOS.tarde, "tarde", ext);
  assert.ok(Math.abs(cerca.userData.uniformes.colorEmisivo.value.g - 0.35 * MOMENTOS.tarde.exterior.brillo) < 1e-6);
  aplicarMomentoExterior([cerca], MOMENTOS.tarde, "tarde", {});     // sin exterior.emision: el respaldo del momento
  assert.ok(Math.abs(cerca.userData.uniformes.colorEmisivo.value.g
    - MOMENTOS.tarde.exterior.emisivo * MOMENTOS.tarde.exterior.brillo) < 1e-6);
  for (const id of ["dia", "tarde", "noche"]) assert.ok(MOMENTOS[id].exterior, `MOMENTOS.${id}.exterior`);
});

test("noche: el cielo del fondo queda bajo, y las elevaciones del sol son las de los panoramas", () => {
  assert.ok(MOMENTOS.noche.fondoIntensidad <= 0.15, `${MOMENTOS.noche.fondoIntensidad}`);
  assert.equal(MOMENTOS.dia.sol.elevacion, 48.0);
  assert.equal(MOMENTOS.tarde.sol.elevacion, 12.1);
  assert.ok(MOMENTOS.tarde.exterior.cielo < MOMENTOS.dia.exterior.cielo);
});

test("materialExterior: la mancha de luz es aditiva y sólo se ve cuando hay emisión", () => {
  const src = new THREE.MeshStandardMaterial({ name: "Depto_Ext_Mat_LuzSuelo", emissive: 0xffffff, transparent: true,
    opacity: 0 });
  src.emissiveMap = new THREE.Texture();
  src.userData = { exterior: true, exterior_capa: "cerca", exterior_aditivo: true };
  const m = materialExterior(src);
  assert.equal(m.blending, THREE.AdditiveBlending);
  assert.equal(m.map, src.emissiveMap);
  assert.equal(m.opacity, 1);
  assert.equal(m.depthWrite, false);
  const ext = { emision: { dia: 0, tarde: 0.35, noche: 1 } };
  aplicarMomentoExterior([m], MOMENTOS.dia, "dia", ext);
  assert.equal(m.visible, false);
  assert.equal(m.color.r, 0);
  aplicarMomentoExterior([m], MOMENTOS.noche, "noche", ext);
  assert.equal(m.visible, true);
  assert.ok(m.color.r > 0);
  // en el sombreado vale 1 (no lo oscurece la calle)
  const geo = new THREE.PlaneGeometry(1, 1);
  sombrear(geo, new THREE.Vector3(0, 1, 0), 0, "aditivo");
  assert.equal(geo.getAttribute("color").getX(0), 1);
});

test("materialExterior: el vidrio refleja el panorama del momento con la máscara de su mapa de rugosidad", () => {
  const src = fuente({ exterior: true, exterior_capa: "cerca",
    exterior_vidrio: { reflectividad: 0.3, rugosidad_vidrio: 0.12, rugosidad_marco: 0.7 } });
  src.roughnessMap = new THREE.Texture();
  const m = materialExterior(src);
  assert.equal(m.combine, THREE.MixOperation);
  assert.equal(m.reflectivity, 0.3);
  assert.equal(m.specularMap, src.roughnessMap);
  const pano = new THREE.Texture();
  pano.mapping = THREE.EquirectangularReflectionMapping;
  aplicarMomentoExterior([m], MOMENTOS.dia, "dia", {}, null, pano);
  assert.equal(m.envMap, pano);
  assert.ok(Math.abs(m.userData.uniformes.intensidadReflejo.value - MOMENTOS.dia.fondoIntensidad
    * MOMENTOS.dia.exterior.reflejo) < 1e-9);
  aplicarMomentoExterior([m], MOMENTOS.noche, "noche", {}, null, null);
  assert.equal(m.envMap, null);
  // el shader: la máscara sale del canal G del mapa (vidrio liso = 1) y el reflejo va con su intensidad
  const sh = { fragmentShader: THREE.ShaderLib.basic.fragmentShader, vertexShader: THREE.ShaderLib.basic.vertexShader,
    uniforms: {} };
  assert.equal(inyectar(sh, m.userData.uniformes), true);
  assert.ok(sh.fragmentShader.includes("rugosidadMarco - texture2D( specularMap, vSpecularMapUv ).g"));
  assert.ok(sh.fragmentShader.includes("envColor.xyz * intensidadReflejo"));
  // sin mapa de rugosidad no hay máscara: queda opaco
  const opaco = materialExterior(fuente({ exterior: true, exterior_vidrio: { reflectividad: 0.3 } }));
  assert.equal(opaco.userData.vidrio, false);
});

test("bruma de las siluetas: el horizonte por azimut en una textura de 64 × 1 que se repite", () => {
  const muestras = new Uint8Array(64 * 4);
  for (let i = 0; i < 64; i++) muestras.set([i * 4, 128, 255 - i * 4, 255], 4 * i);
  const t = texturaHorizonte(muestras);
  assert.equal(t.image.width, 64);
  assert.equal(t.wrapS, THREE.RepeatWrapping);
  assert.equal(t.colorSpace, THREE.SRGBColorSpace);
  assert.equal(texturaHorizonte(null), null);
  const m = horizonteMedio(muestras);
  assert.ok(Math.abs(m[1] - ((128 / 255 + 0.055) / 1.055) ** 2.4) < 1e-6);
  const lejos = materialExterior(fuente({ exterior: true, exterior_capa: "lejos" }));
  const pano = new THREE.Texture();
  pano.userData.horizonteTex = t;
  aplicarMomentoExterior([lejos], MOMENTOS.dia, "dia", {}, m, pano);
  assert.equal(lejos.userData.uniformes.horizonteTex.value, t);
  const sh = { fragmentShader: THREE.ShaderLib.basic.fragmentShader, vertexShader: THREE.ShaderLib.basic.vertexShader,
    uniforms: {} };
  assert.equal(inyectar(sh, lejos.userData.uniformes), true);
  assert.ok(sh.vertexShader.includes("vPosMundoExt = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;"));
  assert.ok(sh.fragmentShader.includes("atan( dirH.z, dirH.x ) * RECIPROCAL_PI2 + 0.5"), "la convención de equirectUv");
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
  assert.deepEqual(prepararPanorama(img, 90, null), { fuente: img, horizonte: null, muestras: null });
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
