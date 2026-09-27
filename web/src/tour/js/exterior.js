// Exterior del bloque 08 (docs/contrato-interaccion.md, sección 4, versión 2.5): el paisaje que se ve por las ventanas y
// el balcón (fachada propia, calle, vecinos, árboles, siluetas lejanas) se dibuja como fondo barato.
// - Cada material con extras.exterior = true pasa a un MeshBasicMaterial: no recibe las luces puntuales ni el sol ni el
//   mapa de entorno general. El volumen lo da un sombreado por vértice (sombrear) con el cielo, el rebote del suelo y el
//   sol del momento; se recalcula al cambiar de momento (sombrearExterior), porque cada panorama tiene su sol.
// - La emisión del glTF (ventanas vecinas y luminarias, exportada con su valor de noche) se suma en el shader, escalada
//   por momento con exterior.emision del modelo; las capas lejanas (extras.exterior_capa = "lejos") se mezclan con el
//   color del horizonte del panorama en su azimut (bruma).
// - Corrección 08, ronda 1: la curva de tono de estos materiales es la Filmic de Blender (filmic.js, medida en Blender
//   con tools/curva_filmic.py), no la ACES del resto del visor: los renders de revisión del exterior salen con Filmic y,
//   con ACES, el mismo valor de escena daba sombras mucho más oscuras y claros más claros (ladrillo del E2 a 0,75 de
//   Blender y hormigón del E3 a 1,32 con el mismo sombreado). El vidrio (extras.exterior_vidrio) refleja el panorama
//   del momento donde su mapa de rugosidad dice vidrio, y la mancha de luz de las luminarias (extras.exterior_aditivo)
//   se suma con mezcla aditiva sólo cuando hay emisión (tarde y noche).
// - Los panoramas se giran rotacion_deg en un canvas: three r160 no tiene scene.backgroundRotation.
// - Corrección 08, ronda 2: el reflejo del vidrio se suma al difuso (AddOperation), como el especular del Principled de
//   Blender, en vez de mezclarse. three r160 no aplica tone mapping a un fondo sRGB (WebGLBackground: toneMapped = false si la
//   textura es sRGB), así que la bruma de las siluetas va hacia el horizonte del panorama tal como se dibuja, su color
//   lineal por la intensidad del fondo, sin el ACES que se le aplicaba; el vidrio con exterior_vidrio.uniforme (las
//   barandas) refleja el panorama parejo, sin máscara y sin sombreado por vértice (capa "plano", k = 1); el sol de cada
//   momento sale de exterior.sol del modelo (haciaSolMomento); y de noche el término hacia arriba del sombreado lleva
//   su propio factor (MOMENTOS[].exterior.arriba), que baja el suelo entre luminarias sin tocar las fachadas.
import { THREE } from "./three.js";
import { FILMIC } from "./filmic.js";

// Sombreado por vértice: k = f_cielo · (ambiente + f_arriba · cielo · max(0, n.y) + (rebote − ambiente) · max(0, −n.y))
// + f_sol · sol · max(0, n·s), por el oscurecimiento de 0,88 a 1 de los primeros 6 m sobre la calle en lo que no mira
// hacia arriba, acotado a [kMin · f_cielo, kMax]. `ambiente`: una cara vertical en sombra (ve medio cielo y medio suelo);
// `cielo`: lo que suma mirar hacia arriba; `rebote`: una cara que mira hacia abajo, que sólo ve el suelo (en Blender el
// fondo de las losas de balcón queda a ≈ 0,55 de la fachada en sombra). Corrección 08, ronda 1: antes era
// ambiente + cielo · n.y, que valía −0,6 mirando hacia abajo, y ACES devolvía claro lo negativo (losas color crema y
// copas negras por debajo); y 2,2 hacia arriba al sol (coronaciones naranjas). f_cielo y f_sol son del momento
// (MOMENTOS[].exterior.cielo y .sol en cielo.js) y `s`, el sol de su panorama. f_arriba (MOMENTOS[].exterior.arriba,
// 1 si falta; corrección 08, ronda 2): de noche el cielo casi no alumbra el suelo en Blender y, con el 1,3 del término
// hacia arriba, la vereda entre dos luminarias quedaba a 2,2 veces la de Blender (contraste luz / entre 4,0 contra
// 9,7). Las tarjetas lejanas llevan un valor fijo (su tinte es el del momento) y el vidrio uniforme, 1.
// Cotas [0,25; 2,0]: la revisión pedía [0,3; 1,6], pero en Blender la calzada al sol queda a ≈ 11 veces el fondo de las
// losas de balcón y ese intervalo sólo deja 5,3 (con 1,6 la calzada salía a 0,78 de Blender; con 0,3, las losas a
// 1,33). k no pasa de 2 y, con la curva Filmic, lo claro ya no se desborda como con ACES.
// Calibrado con tools/medir_08.py contra review/08_exterior desde las mismas cámaras (bitácora, corrección 08, ronda 1).
export const SOMBREADO = { ambiente: 0.44, cielo: 1.3, rebote: 0.25, sol: 1.0, kMin: 0.25, kMax: 2.0, aoMin: 0.88, aoAlto: 6.0, lejos: 0.92 };
// Intensidad de la mancha de luz de las luminarias (extras.exterior_aditivo): con emisión 1 (noche), la textura tal cual,
// que ya es el incremento de pantalla medido en Blender.
export const LUZ_SUELO = 1.0;
// Transparencia (corrección 08, ronda 2): three.js mezcla lo transparente sobre el lienzo ya codificado en sRGB y
// Blender, en lineal; con el mismo alfa, un vidrio claro aclara mucho menos lo oscuro de atrás (la ventana del E3 detrás
// de la baranda de alfa 0,28: 81 en el visor contra 99 en Blender, sRGB). El visor usa α' = 1 − (1 − α)^MEZCLA_SRGB:
// con 1,35, 0,28 pasa a 0,36 (ventana 0,88 y muro 1,15 de Blender detrás del vidrio, tools/medir_08.py).
export const MEZCLA_SRGB = 1.35;
export function opacidadVisor(alfa) {
  return alfa >= 1 ? 1 : 1 - (1 - Math.max(0, alfa)) ** MEZCLA_SRGB;
}
export const MARCA = "#include <opaque_fragment>";

export function esExterior(material, objeto) {
  return Boolean((material && material.userData && material.userData.exterior)
    || (objeto && objeto.userData && objeto.userData.exterior));
}

// Textura de 1 × N de la curva Filmic (fila 0 sin look, fila 1 Medium Contrast), sRGB: se muestrea ya en lineal.
let curvaTex = null;
export function texturaCurva() {
  if (curvaTex) return curvaTex;
  const filas = [FILMIC.ninguno, FILMIC.contraste_medio];
  const n = filas[0].length;
  const px = new Uint8Array(n * 2 * 4);
  filas.forEach((f, j) => f.forEach((v, i) => {
    const k = 4 * (j * n + i);
    px[k] = px[k + 1] = px[k + 2] = Math.round(Math.min(1, Math.max(0, v)) * 255);
    px[k + 3] = 255;
  }));
  curvaTex = new THREE.DataTexture(px, n, 2, THREE.RGBAFormat);
  curvaTex.colorSpace = THREE.SRGBColorSpace;
  curvaTex.magFilter = curvaTex.minFilter = THREE.LinearFilter;
  curvaTex.generateMipmaps = false;
  curvaTex.needsUpdate = true;
  return curvaTex;
}

// La curva en JavaScript (pruebas y mediciones): valor de escena lineal -> pantalla lineal.
export function curvaFilmic(x, fila = "ninguno") {
  const c = FILMIC[fila];
  const n = c.length;
  const t = (Math.log2(Math.max(x, 1e-9) / FILMIC.medio) - FILMIC.lo) / (FILMIC.hi - FILMIC.lo);
  const f = Math.min(n - 1, Math.max(0, t * (n - 1)));
  const i = Math.min(n - 2, Math.floor(f));
  const s = c[i] + (c[i + 1] - c[i]) * (f - i);
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

const GLSL_TONO = `
vec3 curvaFilmicExt( vec3 x ) {
  vec3 t = ( log2( max( x, vec3( 1e-9 ) ) / ${FILMIC.medio.toFixed(4)} ) - ( ${FILMIC.lo.toFixed(4)} ) ) / ${(FILMIC.hi - FILMIC.lo).toFixed(4)};
  float n = ${FILMIC.ninguno.length.toFixed(1)};
  vec3 u = ( clamp( t, 0.0, 1.0 ) * ( n - 1.0 ) + 0.5 ) / n;
  float v = ( filaCurva + 0.5 ) * 0.5;
  return vec3( texture2D( curvaTono, vec2( u.r, v ) ).r, texture2D( curvaTono, vec2( u.g, v ) ).r,
    texture2D( curvaTono, vec2( u.b, v ) ).r );
}
`;

// Agrega al shader de MeshBasicMaterial la emisión (con mapa si el material lo trae), la curva de tono Filmic, la bruma
// (con el horizonte del panorama por azimut si hay textura) y, en el vidrio, la intensidad del reflejo y, si trae mapa
// de rugosidad, su máscara.
// `u`: los uniformes del material (se actualizan por momento sin recompilar). Devuelve false si el shader no trae la
// marca esperada (otra versión de three): el material queda como MeshBasicMaterial, sin emisión.
export function inyectar(shader, u, THREE_ = THREE) {
  if (!shader.fragmentShader.includes(MARCA)) return false;
  Object.assign(shader.uniforms, u);
  const conMapa = Boolean(u.mapaEmisivo);
  const horizonte = Boolean(u.horizonteTex);
  const vidrio = Boolean(u.intensidadReflejo);
  const mascara = vidrio && Boolean(u.rugosidadVidrio);
  let decl = "uniform vec3 colorEmisivo;\nuniform vec3 colorNeblina;\nuniform float neblina;\nuniform float saturacion;\n"
    + "uniform float exposicion;\nuniform sampler2D curvaTono;\nuniform float filaCurva;\n"
    + (conMapa ? "uniform sampler2D mapaEmisivo;\n" : "")
    + (horizonte ? "uniform sampler2D horizonteTex;\nuniform float intensidadHorizonte;\nvarying vec3 vPosMundoExt;\n" : "")
    + (mascara ? "uniform float rugosidadVidrio;\nuniform float rugosidadMarco;\n" : "")
    + (vidrio ? "uniform float intensidadReflejo;\n" : "");
  let frag = shader.fragmentShader;
  if (mascara) {
    // máscara del reflejo: el canal G del mapa de rugosidad (metallicRoughnessTexture de glTF), 1 en el vidrio y 0 en
    // el marco; el cielo reflejado con la intensidad del fondo del momento
    frag = frag.replace("#include <specularmap_fragment>", `float specularStrength = 1.0;
#ifdef USE_SPECULARMAP
  specularStrength = clamp( ( rugosidadMarco - texture2D( specularMap, vSpecularMapUv ).g )
    / max( rugosidadMarco - rugosidadVidrio, 1e-3 ), 0.0, 1.0 );
#endif`);
  }
  if (vidrio) {
    frag = frag.replace("#include <envmap_fragment>", THREE_.ShaderChunk.envmap_fragment.replace(
      "outgoingLight = mix( outgoingLight, envColor.xyz, specularStrength * reflectivity );",
      "outgoingLight = mix( outgoingLight, envColor.xyz * intensidadReflejo, specularStrength * reflectivity );").replace(
      "outgoingLight += envColor.xyz * specularStrength * reflectivity;",
      "outgoingLight += envColor.xyz * intensidadReflejo * specularStrength * reflectivity;"));
  }
  const bruma = horizonte
    ? "vec3 dirH = normalize( vPosMundoExt - cameraPosition );\n"
      + "vec3 neb = texture2D( horizonteTex, vec2( atan( dirH.z, dirH.x ) * RECIPROCAL_PI2 + 0.5, 0.5 ) ).rgb * intensidadHorizonte;\n"
    : "vec3 neb = colorNeblina;\n";
  // saturación antes de la emisión (las ventanas encendidas conservan su color), la curva de tono y la bruma al final,
  // hacia el horizonte como lo dibuja el fondo: su color lineal por la intensidad del fondo, sin curva (three.js no
  // aplica tone mapping a un fondo sRGB)
  const suma = "outgoingLight = mix( vec3( dot( outgoingLight, vec3( 0.2126, 0.7152, 0.0722 ) ) ), outgoingLight, saturacion );\n"
    + (conMapa ? "outgoingLight += colorEmisivo * texture2D( mapaEmisivo, vMapUv ).rgb;\n" : "outgoingLight += colorEmisivo;\n")
    + "outgoingLight = curvaFilmicExt( outgoingLight * exposicion );\n" + bruma
    + "outgoingLight = mix( outgoingLight, neb, neblina );\n";
  shader.fragmentShader = decl + GLSL_TONO + frag.replace(MARCA, suma + MARCA);
  if (horizonte) {
    shader.vertexShader = "varying vec3 vPosMundoExt;\n" + shader.vertexShader.replace("#include <project_vertex>",
      "#include <project_vertex>\nvPosMundoExt = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;");
  }
  return true;
}

// Material barato a partir del que armó GLTFLoader (MeshStandardMaterial). Conserva mapa, color base (baseColorFactor),
// transparencia y caras dobles; `vertexColors` para el sombreado de sombrear().
export function materialExterior(src) {
  const ud0 = src.userData || {};
  const e = src.emissive;
  const emisivo = e && e.r + e.g + e.b > 0 ? e.clone() : null;
  const capa = ud0.exterior_capa || "cerca";
  if (ud0.exterior_aditivo) {
    // la mancha de luz de las luminarias: su textura de emisión como mapa, sumada al cuadro (mezcla aditiva) con el
    // color que le da el momento (negro de día: no suma nada); sin curva de tono ni sombreado
    const m = new THREE.MeshBasicMaterial({
      name: src.name, map: src.emissiveMap || null, color: new THREE.Color(0, 0, 0), vertexColors: true,
      transparent: true, opacity: 1, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false,
    });
    m.userData = { ...ud0, exterior: true, aditivo: true, capa: "aditivo", colorBase: new THREE.Color(1, 1, 1),
      emisivoBase: emisivo || new THREE.Color(1, 1, 1), uniformes: null };
    return m;
  }
  // vidrio (extras.exterior_vidrio): con mapa de rugosidad (la máscara del reflejo) o, con uniforme = true (las barandas;
  // corrección 08, ronda 2), todo el paño refleja parejo y no lleva sombreado por vértice (capa "plano")
  const ev = ud0.exterior_vidrio && typeof ud0.exterior_vidrio === "object" ? ud0.exterior_vidrio : null;
  const uniforme = Boolean(ev && ev.uniforme);
  const vidrio = ev && (src.roughnessMap || uniforme) ? ev : null;
  const capaFinal = uniforme ? "plano" : capa;
  const m = new THREE.MeshBasicMaterial({
    name: src.name, map: src.map || null, color: src.color ? src.color.clone() : new THREE.Color(1, 1, 1),
    vertexColors: true, transparent: Boolean(src.transparent),
    opacity: src.transparent ? opacidadVisor(src.opacity ?? 1) : src.opacity ?? 1, side: src.side,
    depthWrite: src.depthWrite !== false, alphaTest: src.alphaTest || 0, toneMapped: false,
  });
  const u = {
    colorEmisivo: { value: new THREE.Color(0, 0, 0) },
    colorNeblina: { value: new THREE.Color(0, 0, 0) },
    neblina: { value: 0 },
    saturacion: { value: 1 },
    exposicion: { value: 1 },
    curvaTono: { value: texturaCurva() },
    filaCurva: { value: 0 },
  };
  if (emisivo && src.emissiveMap && src.map) u.mapaEmisivo = { value: src.emissiveMap };
  if (capa === "lejos") {
    u.horizonteTex = { value: null };
    u.intensidadHorizonte = { value: 1 };
  }
  if (vidrio) {
    // el reflejo se suma (corrección 08, ronda 2; antes se mezclaba): el Principled de Blender suma el especular al
    // difuso, y con la mezcla lo claro detrás del vidrio (cortinas, persianas) se apagaba hacia el cielo reflejado
    m.combine = THREE.AddOperation;
    m.reflectivity = vidrio.reflectividad ?? 0.3;
    u.intensidadReflejo = { value: 1 };
    if (!uniforme) {
      m.specularMap = src.roughnessMap;
      u.rugosidadVidrio = { value: vidrio.rugosidad_vidrio ?? 0.12 };
      u.rugosidadMarco = { value: vidrio.rugosidad_marco ?? 0.7 };
    }
  }
  // extras.tinte (lineal): el factor de color de las siluetas, que el exportador de Blender 3.6 no pasa a
  // baseColorFactor cuando va en un nodo MixRGB
  const tinte = ud0.tinte;
  if (Array.isArray(tinte) && tinte.length >= 3) m.color.multiply(new THREE.Color(tinte[0], tinte[1], tinte[2]));
  m.userData = { ...ud0, exterior: true, capa: capaFinal, vidrio: Boolean(vidrio), colorBase: m.color.clone(),
    emisivoBase: emisivo, uniformes: u };
  m.onBeforeCompile = (sh) => { inyectar(sh, u); };
  const clave = `exterior_${u.mapaEmisivo ? "mapa" : "plano"}_${capaFinal}_${vidrio ? (uniforme ? "reflejo" : "vidrio") : "opaco"}`;
  m.customProgramCacheKey = () => clave;
  return m;
}

// k de una normal (nx, ny, nz) con el sol `s` (unitario) y los factores del momento `f` = { cielo, sol, arriba }, sin
// el oscurecimiento junto a la calle ni las cotas.
export function factorSombreado(nx, ny, nz, s, p = SOMBREADO, f = {}) {
  const fc = f.cielo ?? 1, fs = f.sol ?? 1, fa = f.arriba ?? 1;
  const d = Math.max(0, nx * s.x + ny * s.y + nz * s.z);
  return fc * (p.ambiente + fa * p.cielo * Math.max(0, ny) + (p.rebote - p.ambiente) * Math.max(0, -ny))
    + fs * p.sol * d;
}

// Color por vértice (atributo `color`) de una geometría ya en espacio de mundo. haciaSol: vector unitario hacia el sol
// (glTF); sueloY: la calle (exterior.suelo_y); capa: "cerca", "lejos", "aditivo" (la mancha de luz: 1) o "plano" (el
// vidrio uniforme: 1); f: factores del momento. Reusa el atributo si ya existe (se recalcula en cada cambio de momento).
export function sombrear(geo, haciaSol, sueloY = 0, capa = "cerca", p = SOMBREADO, f = {}) {
  const n = geo.getAttribute("normal");
  const pos = geo.getAttribute("position");
  let attr = geo.getAttribute("color");
  if (!attr || attr.count !== pos.count || attr.itemSize !== 3) {
    attr = new THREE.BufferAttribute(new Float32Array(pos.count * 3), 3);
    geo.setAttribute("color", attr);
  }
  const c = attr.array;
  const fc = f.cielo ?? 1;
  for (let i = 0; i < pos.count; i++) {
    let k = capa === "aditivo" || capa === "plano" ? 1 : p.lejos;
    if (capa === "cerca" && n) {
      const nx = n.getX(i), ny = n.getY(i), nz = n.getZ(i);
      k = factorSombreado(nx, ny, nz, haciaSol, p, f);
      if (ny < 0.7) {                              // lo que no mira hacia arriba: más oscuro junto a la calle
        const t = Math.min(1, Math.max(0, (pos.getY(i) - sueloY) / p.aoAlto));
        k *= p.aoMin + (1 - p.aoMin) * t * t * (3 - 2 * t);
      }
      k = Math.min(p.kMax, Math.max(p.kMin * fc, k));
    }
    c[3 * i] = c[3 * i + 1] = c[3 * i + 2] = k;
  }
  attr.needsUpdate = true;
  return geo;
}

// Recalcula el sombreado de todo el grupo del exterior (Depto_Exterior) para el sol y los factores de un momento.
export function sombrearExterior(grupo, haciaSol, sueloY = 0, p = SOMBREADO, f = {}) {
  if (!grupo) return 0;
  let n = 0;
  grupo.traverse((o) => {
    if (!o.isMesh) return;
    sombrear(o.geometry, haciaSol, sueloY, (o.material.userData && o.material.userData.capa) || "cerca", p, f);
    n++;
  });
  return n;
}

// Hacia el sol (glTF, unitario) desde D.luces: la dirección del sol es hacia donde viaja la luz. Sin sol, desde arriba.
// `elevacionDeg`: la elevación del sol del panorama del momento (cielo.js), con el azimut del sol de la escena, que la
// fase 08 ya alineó con los tres panoramas (rotacion_deg).
export function haciaSolDe(D, elevacionDeg = null) {
  const sol = ((D && D.luces) || []).find((l) => l.tipo === "sol");
  const v = sol ? new THREE.Vector3(-sol.direccion[0], -sol.direccion[1], -sol.direccion[2]) : new THREE.Vector3(0, 1, 0);
  v.normalize();
  const h = Math.hypot(v.x, v.z);
  if (typeof elevacionDeg === "number" && h > 1e-6) {
    const el = (elevacionDeg * Math.PI) / 180;
    v.set((v.x / h) * Math.cos(el), Math.sin(el), (v.z / h) * Math.cos(el));
  }
  return v;
}

// Hacia el sol del momento `id` (glTF, unitario): exterior.sol[id] del modelo (contrato 2.5: el sol medido en su
// panorama, con el azimut ya girado; hacia_gl, o azimut_deg y elevacion_deg en la convención de Blender) o, si el
// modelo no lo trae, el azimut del sol de la escena con `elevacionRespaldo` (MOMENTOS[id].sol.elevacion).
export function haciaSolMomento(D, id, elevacionRespaldo = null) {
  const s = D && D.exterior && D.exterior.sol && D.exterior.sol[id];
  if (s && Array.isArray(s.hacia_gl) && s.hacia_gl.length === 3) {
    return new THREE.Vector3(...s.hacia_gl).normalize();
  }
  if (s && typeof s.azimut_deg === "number" && typeof s.elevacion_deg === "number") {
    const a = (s.azimut_deg * Math.PI) / 180, e = (s.elevacion_deg * Math.PI) / 180;
    // Blender (cos e cos a, cos e sin a, sin e) -> glTF (x, z, −y)
    return new THREE.Vector3(Math.cos(e) * Math.cos(a), Math.sin(e), -Math.cos(e) * Math.sin(a)).normalize();
  }
  return haciaSolDe(D, elevacionRespaldo);
}

// Intensidad con que se dibuja el panorama del momento: exterior.panoramas_intensidad[id] del modelo (contrato 2.5: los
// cielos ya en pantalla con la curva Filmic de los renders van con 1) o, si falta, la del momento (cielo.js).
export function intensidadFondo(D, id, momento) {
  const pi = D && D.exterior && D.exterior.panoramas_intensidad;
  return pi && typeof pi[id] === "number" ? pi[id] : momento.fondoIntensidad ?? 1;
}

// Tinte, bruma, emisión, curva, exposición y reflejo del momento. `momento`: MOMENTOS[id] de cielo.js; `id`: su clave;
// `exterior`: D.exterior (su `emision` manda sobre la del momento); `horizonte`: color lineal medio del horizonte del
// panorama; `panorama`: la textura del panorama del momento (su userData.horizonteTex, el horizonte por azimut, y el
// reflejo del vidrio), o null.
export function aplicarMomentoExterior(materiales, momento, id, exterior = {}, horizonte = null, panorama = null) {
  const e = momento.exterior || {};
  const emision = exterior.emision && id in exterior.emision ? exterior.emision[id] : e.emisivo ?? 0;
  const fondo = momento.fondoIntensidad ?? 1;
  // el horizonte medido en el panorama, con la intensidad con que se dibuja el fondo: sin ella las siluetas quedaban
  // más claras que el cielo detrás
  const neblina = new THREE.Color(...(horizonte || e.horizonte || [0.5, 0.5, 0.5])).multiplyScalar(horizonte ? fondo : 1);
  const texH = panorama && panorama.userData ? panorama.userData.horizonteTex || null : null;
  for (const mat of materiales) {
    const ud = mat.userData;
    if (ud.aditivo) {
      // la textura ya es el incremento de pantalla de noche (ext_texturas.luz_suelo): con emisión 1 se suma tal cual
      mat.color.copy(ud.emisivoBase).multiplyScalar(emision * (e.luzSuelo ?? 1) * LUZ_SUELO);
      mat.visible = emision > 0;
      continue;
    }
    const lejos = ud.capa === "lejos";
    const t = (lejos ? e.lejos : e.tinte) || [1, 1, 1];
    mat.color.copy(ud.colorBase).multiply(new THREE.Color(t[0], t[1], t[2]));
    const u = ud.uniformes;
    u.colorEmisivo.value.setRGB(0, 0, 0);
    if (ud.emisivoBase) u.colorEmisivo.value.copy(ud.emisivoBase).multiplyScalar(emision * (e.brillo ?? 1));
    u.colorNeblina.value.copy(neblina);
    u.neblina.value = lejos ? e.neblina ?? 0 : 0;
    u.saturacion.value = e.saturacion ?? 1;
    u.exposicion.value = 2 ** (e.exposicion ?? 0);
    u.filaCurva.value = e.curva === "contraste_medio" ? 1 : 0;
    if (u.horizonteTex) {
      u.horizonteTex.value = texH;
      u.intensidadHorizonte.value = fondo;
    }
    if (ud.vidrio) {
      const env = panorama || null;
      if (mat.envMap !== env) { mat.envMap = env; mat.needsUpdate = true; }
      u.intensidadReflejo.value = fondo * (e.reflejo ?? 1);
    }
  }
}

// Píxeles que se corre el panorama hacia la izquierda para girarlo `grados` (antihorario visto desde arriba, +Y de
// glTF): con u = 0,5 − azimut / 360 (convención de three.js y de Blender), el píxel u del girado es el u + grados / 360
// del original.
export function desplazamientoPx(ancho, grados) {
  const f = (((grados || 0) / 360) % 1 + 1) % 1;
  return Math.round(f * ancho) % ancho;
}

export const MUESTRAS_HORIZONTE = 64;

// Imagen -> canvas girado (o la misma imagen si no hay giro), color medio del horizonte (lineal) y sus 64 muestras
// por azimut (RGBA sRGB de 8 bits, para una textura de 64 × 1): la franja de 2 % de alto justo sobre el horizonte.
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
  let horizonte = null, muestras = null;
  if (doc) {
    try {
      const cv = doc.createElement("canvas");
      cv.width = MUESTRAS_HORIZONTE; cv.height = 1;
      const ctx = cv.getContext("2d");
      ctx.drawImage(fuente, 0, Math.round(h * 0.47), w, Math.max(1, Math.round(h * 0.02)), 0, 0, MUESTRAS_HORIZONTE, 1);
      muestras = new Uint8Array(ctx.getImageData(0, 0, MUESTRAS_HORIZONTE, 1).data);
      horizonte = horizonteMedio(muestras);
    } catch (err) {
      horizonte = null;                             // canvas contaminado o sin 2D: queda el color del momento
      muestras = null;
    }
  }
  return { fuente, horizonte, muestras };
}

// Color medio lineal de las muestras RGBA sRGB del horizonte.
export function horizonteMedio(muestras) {
  const n = muestras.length / 4;
  const m = [0, 0, 0];
  for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) m[k] += muestras[4 * i + k] / 255 / n;
  return m.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
}

// Textura de 64 × 1 (sRGB, se repite en u) con el horizonte del panorama por azimut: la bruma de cada silueta toma el
// color del cielo que tiene detrás, no el promedio de los 360°.
export function texturaHorizonte(muestras) {
  if (!muestras) return null;
  const t = new THREE.DataTexture(muestras, muestras.length / 4, 1, THREE.RGBAFormat);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = THREE.RepeatWrapping;
  t.magFilter = t.minFilter = THREE.LinearFilter;
  t.generateMipmaps = false;
  t.needsUpdate = true;
  return t;
}
