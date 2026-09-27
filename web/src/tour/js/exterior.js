// Exterior del bloque 08 (docs/contrato-interaccion.md, sección 4, versión 2.3): el paisaje que se ve por las ventanas y
// el balcón (fachada propia, calle, vecinos, árboles, siluetas lejanas) se dibuja como fondo barato.
// - Cada material con extras.exterior = true pasa a un MeshBasicMaterial: no recibe las luces puntuales ni el sol ni el
//   mapa de entorno. El volumen lo da un sombreado por vértice calculado una vez al cargar (sombrear): cielo arriba, sol
//   de la escena según la normal y un oscurecimiento suave junto a la calle.
// - La emisión del glTF (ventanas vecinas y luminarias, exportada con su valor de noche) se suma en el shader, escalada
//   por momento con exterior.emision del modelo; las capas lejanas (extras.exterior_capa = "lejos") se mezclan con el
//   color del horizonte del panorama del momento (bruma).
// - Los panoramas se giran rotacion_deg en un canvas: three r160 no tiene scene.backgroundRotation.
import { THREE } from "./three.js";

// Sombreado por vértice: ambiente + cielo · n.y + sol · max(0, n·s), y en las caras no horizontales un factor de 0,88 a 1
// en los primeros 6 m sobre la calle. Las tarjetas lejanas llevan un valor fijo. Calibrado contra balcon_dia de
// review/08_exterior desde la misma cámara (bitácora del bloque 08): con 0,62 / 0,18 / 0,55 las fachadas en sombra
// coincidían (0,99) pero la calzada y las copas quedaban a la mitad (0,52 y 0,46): en Blender el cielo alumbra mucho más
// lo que mira hacia arriba.
export const SOMBREADO = { ambiente: 0.5, cielo: 1.1, sol: 1.0, aoMin: 0.88, aoAlto: 6.0, lejos: 0.92 };
export const MARCA = "#include <opaque_fragment>";

export function esExterior(material, objeto) {
  return Boolean((material && material.userData && material.userData.exterior)
    || (objeto && objeto.userData && objeto.userData.exterior));
}

// Agrega al fragment shader de MeshBasicMaterial la emisión (con mapa si el material lo trae) y la bruma. `u`: los
// uniformes compartidos del material (se actualizan por momento sin recompilar). Devuelve false si el shader no trae
// la marca esperada (otra versión de three): el material queda sin emisión, pero se dibuja.
export function inyectar(shader, u) {
  if (!shader.fragmentShader.includes(MARCA)) return false;
  Object.assign(shader.uniforms, u);
  const conMapa = Boolean(u.mapaEmisivo);
  const decl = "uniform vec3 colorEmisivo;\nuniform vec3 colorNeblina;\nuniform float neblina;\nuniform float saturacion;\n"
    + (conMapa ? "uniform sampler2D mapaEmisivo;\n" : "");
  // saturación antes de la emisión (las ventanas encendidas conservan su color) y bruma al final
  const suma = "outgoingLight = mix( vec3( dot( outgoingLight, vec3( 0.2126, 0.7152, 0.0722 ) ) ), outgoingLight, saturacion );\n"
    + (conMapa ? "outgoingLight += colorEmisivo * texture2D( mapaEmisivo, vMapUv ).rgb;\n"
      : "outgoingLight += colorEmisivo;\n") + "outgoingLight = mix( outgoingLight, colorNeblina, neblina );\n";
  shader.fragmentShader = decl + shader.fragmentShader.replace(MARCA, suma + MARCA);
  return true;
}

// Material barato a partir del que armó GLTFLoader (MeshStandardMaterial). Conserva mapa, color base (baseColorFactor),
// transparencia y caras dobles; `vertexColors` para el sombreado de sombrear().
export function materialExterior(src) {
  const m = new THREE.MeshBasicMaterial({
    name: src.name, map: src.map || null, color: src.color ? src.color.clone() : new THREE.Color(1, 1, 1),
    vertexColors: true, transparent: Boolean(src.transparent), opacity: src.opacity ?? 1, side: src.side,
    depthWrite: src.depthWrite !== false, alphaTest: src.alphaTest || 0,
  });
  const e = src.emissive;
  const emisivo = e && e.r + e.g + e.b > 0 ? e.clone() : null;
  const u = {
    colorEmisivo: { value: new THREE.Color(0, 0, 0) },
    colorNeblina: { value: new THREE.Color(0, 0, 0) },
    neblina: { value: 0 },
    saturacion: { value: 1 },
  };
  if (emisivo && src.emissiveMap && src.map) u.mapaEmisivo = { value: src.emissiveMap };
  const capa = (src.userData && src.userData.exterior_capa) || "cerca";
  // extras.tinte (lineal): el factor de color de las siluetas, que el exportador de Blender 3.6 no pasa a
  // baseColorFactor cuando va en un nodo MixRGB
  const tinte = src.userData && src.userData.tinte;
  if (Array.isArray(tinte) && tinte.length >= 3) m.color.multiply(new THREE.Color(tinte[0], tinte[1], tinte[2]));
  m.userData = { ...src.userData, exterior: true, capa, colorBase: m.color.clone(), emisivoBase: emisivo, uniformes: u };
  m.onBeforeCompile = (sh) => { inyectar(sh, u); };
  m.customProgramCacheKey = () => `exterior_${u.mapaEmisivo ? "mapa" : "plano"}`;
  return m;
}

// Color por vértice (atributo `color`) de una geometría ya en espacio de mundo. haciaSol: vector unitario hacia el sol
// (glTF); sueloY: la calle (exterior.suelo_y).
export function sombrear(geo, haciaSol, sueloY = 0, capa = "cerca", p = SOMBREADO) {
  const n = geo.getAttribute("normal");
  const pos = geo.getAttribute("position");
  const c = new Float32Array(pos.count * 3);
  for (let i = 0; i < pos.count; i++) {
    let k = p.lejos;
    if (capa !== "lejos" && n) {
      const nx = n.getX(i), ny = n.getY(i), nz = n.getZ(i);
      const d = Math.max(0, nx * haciaSol.x + ny * haciaSol.y + nz * haciaSol.z);
      k = p.ambiente + p.cielo * ny + p.sol * d;
      if (ny < 0.7) {                              // fachadas: más oscuras junto a la calle
        const t = Math.min(1, Math.max(0, (pos.getY(i) - sueloY) / p.aoAlto));
        k *= p.aoMin + (1 - p.aoMin) * t * t * (3 - 2 * t);
      }
    }
    c[3 * i] = c[3 * i + 1] = c[3 * i + 2] = k;
  }
  geo.setAttribute("color", new THREE.BufferAttribute(c, 3));
  return geo;
}

// Hacia el sol (glTF, unitario) desde D.luces: la dirección del sol es hacia donde viaja la luz. Sin sol, desde arriba.
export function haciaSolDe(D) {
  const sol = (D.luces || []).find((l) => l.tipo === "sol");
  const v = sol ? new THREE.Vector3(-sol.direccion[0], -sol.direccion[1], -sol.direccion[2]) : new THREE.Vector3(0, 1, 0);
  return v.normalize();
}

// Tinte, bruma y emisión del momento. `momento`: MOMENTOS[id] de cielo.js; `id`: su clave; `exterior`: D.exterior (su
// `emision` manda sobre la del momento); `horizonte`: color lineal del horizonte del panorama (o el del momento).
export function aplicarMomentoExterior(materiales, momento, id, exterior = {}, horizonte = null) {
  const e = momento.exterior || {};
  const emision = exterior.emision && id in exterior.emision ? exterior.emision[id] : e.emisivo ?? 0;
  // el horizonte medido en el panorama, con la intensidad con que se dibuja el fondo (de noche, 0,35): sin ella las
  // siluetas quedaban más claras que el cielo detrás
  const neblina = new THREE.Color(...(horizonte || e.horizonte || [0.5, 0.5, 0.5]))
    .multiplyScalar(horizonte ? momento.fondoIntensidad ?? 1 : 1);
  for (const mat of materiales) {
    const ud = mat.userData;
    const lejos = ud.capa === "lejos";
    const t = (lejos ? e.lejos : e.tinte) || [1, 1, 1];
    mat.color.copy(ud.colorBase).multiply(new THREE.Color(t[0], t[1], t[2]));
    ud.uniformes.colorEmisivo.value.setRGB(0, 0, 0);
    if (ud.emisivoBase) ud.uniformes.colorEmisivo.value.copy(ud.emisivoBase).multiplyScalar(emision * (e.brillo ?? 1));
    ud.uniformes.colorNeblina.value.copy(neblina);
    ud.uniformes.neblina.value = lejos ? e.neblina ?? 0 : 0;
    ud.uniformes.saturacion.value = e.saturacion ?? 1;
  }
}

// Píxeles que se corre el panorama hacia la izquierda para girarlo `grados` (antihorario visto desde arriba, +Y de
// glTF): con u = 0,5 − azimut / 360 (convención de three.js y de Blender), el píxel u del girado es el u + grados / 360
// del original.
export function desplazamientoPx(ancho, grados) {
  const f = (((grados || 0) / 360) % 1 + 1) % 1;
  return Math.round(f * ancho) % ancho;
}

// Imagen -> canvas girado (o la misma imagen si no hay giro) y color medio del horizonte (lineal): la franja de 2 % de
// alto justo sobre la línea del horizonte.
export function prepararPanorama(imagen, grados, doc = globalThis.document) {
  const w = imagen.width, h = imagen.height;
  const s = desplazamientoPx(w, grados);
  let fuente = imagen;
  if (s && doc) {
    const cv = doc.createElement("canvas");
    cv.width = w; cv.height = h;
    const ctx = cv.getContext("2d");
    ctx.drawImage(imagen, -s, 0);
    ctx.drawImage(imagen, w - s, 0);
    fuente = cv;
  }
  let horizonte = null;
  if (doc) {
    try {
      const cv = doc.createElement("canvas");
      cv.width = 64; cv.height = 1;
      const ctx = cv.getContext("2d");
      ctx.drawImage(fuente, 0, Math.round(h * 0.47), w, Math.max(1, Math.round(h * 0.02)), 0, 0, 64, 1);
      const px = ctx.getImageData(0, 0, 64, 1).data;
      const m = [0, 0, 0];
      for (let i = 0; i < 64; i++) for (let k = 0; k < 3; k++) m[k] += px[4 * i + k] / 255 / 64;
      horizonte = m.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    } catch (err) {
      horizonte = null;                             // canvas contaminado o sin 2D: queda el color del momento
    }
  }
  return { fuente, horizonte };
}
