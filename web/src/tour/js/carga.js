// Carga del modelo (modelo/depto.gltf o depto_movil.gltf, según el dispositivo) y de depto_colisiones.json,
// más la preparación de la escena: arregla materiales de vidrio, arma los registros de piezas móviles,
// interruptores y grupos de luz, y fusiona las mallas estáticas por material para bajar los draw calls
// (requisito de rendimiento: < 90). A diferencia de exports/depto_tour.html (que armaba un GLB en memoria
// porque las páginas de claude.ai no servían .glb/.bin), aquí Netlify sirve modelo/depto.gltf y depto.bin
// directo: se cargan con GLTFLoader normal.
import { THREE } from "./three.js";
import { GLTFLoader } from "../../vendor/three/jsm/loaders/GLTFLoader.js";
import { mergeGeometries } from "../../vendor/three/jsm/utils/BufferGeometryUtils.js";
import {
  deducirGrupos, crearLucesTHREE, colorLinealAHex, FUNDIDO_MS, intensidadBase, TILT_TECLA_DEG,
  interruptorEncendido, ordenarInterruptores,
} from "./luces.js";
import { duracionPorClase } from "./animacion.js";
import { esExterior, materialExterior, sombrear, haciaSolDe } from "./exterior.js";
import { etiquetaGrupo } from "./textos.js";

// Carpeta del modelo relativa a este módulo (/tour/js/ -> /tour/modelo/) y no a la página: /en/tour/ y /fr/tour/ usan
// este mismo JS y el mismo modelo de /tour/ (ADR 0007, decisión 5; web/build.py, tour_traducible()).
export const RUTA_MODELO = new URL("../modelo/", import.meta.url).href;

// Materiales de vidrio REALES (nombres exactos del contrato de interacción): Depto_Mat_VidrioNegro es el
// anafe y el frente del horno, opaco a propósito. Antes se usaba una expresión /Vidrio/ que también lo
// volvía transparente por error.
const MATERIALES_VIDRIO = new Set([
  "Depto_Mat_Vidrio", "Depto_Mat_VidrioBombilla", "Depto_Mat_VidrioEsmerilado", "Depto_Mat_VidrioReloj",
]);

// Variante liviana solo para teléfonos: puntero grueso Y pantalla física chica. Antes bastaba una ventana de
// menos de 900 px CSS, y eso incluía a la mayoría de los portátiles (1440×900 deja ~850 px de alto útil),
// que recibían las texturas del teléfono (diagnóstico del 2026-09-26: −90 % de nitidez en el piso).
export function esTactilOPantallaChica(entorno = globalThis) {
  const tactil = entorno.matchMedia("(pointer: coarse)").matches;
  const s = entorno.screen || { width: 0, height: 0 };
  return tactil && Math.min(s.width, s.height) < 900;
}

export async function cargarColisiones() {
  const r = await fetch(RUTA_MODELO + "depto_colisiones.json");
  if (!r.ok) throw new Error(`depto_colisiones.json: HTTP ${r.status}`);
  return r.json();
}

// onProgreso(fraccion 0..1). El LoadingManager cuenta ítems (el .gltf, el .bin y cada textura), no bytes:
// para un modelo con ~50 texturas del mismo tamaño es una aproximación razonable y no requiere adivinar
// content-length por adelantado.
export function cargarGLTF(nombreArchivo, onProgreso) {
  return new Promise((resolve, reject) => {
    const manager = new THREE.LoadingManager();
    if (onProgreso) manager.onProgress = (_url, listos, total) => onProgreso(total ? listos / total : 0);
    new GLTFLoader(manager).load(RUTA_MODELO + nombreArchivo, resolve, undefined, reject);
  });
}

// Vidrio de ventanas y barandas del depto (Depto_Mat_Vidrio en los nodos Depto_Ventana_* y Depto_Balcon_*; corrección 08,
// ronda 2; el mismo material en botellas, repisas de la nevera, vajilla y mamparas sigue como antes: reflejar el cielo
// dentro de la nevera no tiene sentido). Antes era un MeshStandardMaterial
// celeste (0,60; 0,79; 0,89) de opacidad 0,16 que recibía las luces, el hemisferio y el RoomEnvironment: su color
// iluminado se sumaba como un velo lechoso sobre el paisaje (el ladrillo del E2 por el ventanal, de (78, 49, 45) en
// Blender a (91, 73, 66) en el visor; detrás del ventanal y de la baranda, de (100, 62, 55) a (129, 108, 99)). Ahora no
// suma luz difusa (color negro) y sólo refleja (el especular de three: F0 = 0,04 de frente, más de canto) el panorama del
// momento con la intensidad del fondo por `reflejo` (main.js, aplicarMomento); lo de atrás pasa multiplicado por
// `transmision` (mezcla ONE, ONE_MINUS_SRC_ALPHA: fuente + destino · (1 − opacidad)), como el vidrio de revisión de
// Blender (transparente de 0,97-0,98 por 1 − 2 × Fresnel: ≈ 0,89 en lineal de frente). La mezcla va sobre el lienzo ya
// codificado en sRGB: 0,95 ahí es ≈ 0,89 en lineal. Sólo la cara de adelante (FrontSide): los paños son cajas y, con
// las dos caras, cada paño se sumaba dos veces. Medido con tools/medir_08.py (criterios ladrillo_*).
export const VIDRIO_VENTANA = { transmision: 0.95, reflejo: 1.0 };
export const NODOS_VIDRIO_VENTANA = /^Depto_(Ventana|Balcon)_/;

// ¿La malla `o` (o alguno de sus padres, si GLTFLoader partió el nodo en primitivas) es de una ventana o del balcón?
export function esVidrioDeVentana(o) {
  for (let p = o; p; p = p.parent) if (NODOS_VIDRIO_VENTANA.test(p.name || "")) return true;
  return false;
}

export function materialVidrioVentana(mat) {
  const v = new THREE.MeshStandardMaterial({
    name: mat.name, color: 0x000000, roughness: mat.roughness, metalness: 0, transparent: true,
    opacity: 1 - VIDRIO_VENTANA.transmision, depthWrite: false, side: THREE.FrontSide,
    blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor,
    blendDst: THREE.OneMinusSrcAlphaFactor,
  });
  v.userData = { ...(mat.userData || {}), vidrioVentana: true };
  return v;
}

function arreglarVidrios(raiz) {
  // Un material transparente por material de origen (no uno por malla): así la fusión por material de más abajo
  // junta todos los vidrios iguales en una sola llamada de dibujo.
  const cache = new Map();
  raiz.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    mats.forEach((mat, i) => {
      if (!mat || !MATERIALES_VIDRIO.has(mat.name)) return;
      const ventana = mat.name === "Depto_Mat_Vidrio" && esVidrioDeVentana(o);
      const k = `${mat.uuid}|${ventana ? "ventana" : "interior"}`;
      if (cache.has(k)) {
        if (Array.isArray(o.material)) o.material[i] = cache.get(k); else o.material = cache.get(k);
        return;
      }
      const v = ventana ? materialVidrioVentana(mat) : new THREE.MeshStandardMaterial({
        name: mat.name, color: mat.color, roughness: mat.roughness, metalness: 0, transparent: true,
        opacity: mat.name === "Depto_Mat_VidrioEsmerilado" ? 0.55 : 0.16, depthWrite: false, side: THREE.DoubleSide,
      });
      cache.set(k, v);
      if (Array.isArray(o.material)) o.material[i] = v; else o.material = v;
    });
  });
}

// Entornos locales (contrato 2.2, sección 6; corrección 07c, ronda 2). `D.entornos[]` trae un equirectangular
// renderizado en Blender desde el centro de un recinto (la cocina), la caja [xmin, xmax, zmin, zmax] de glTF donde vale y
// los materiales que lo usan. Con el RoomEnvironment genérico de three.js (un estudio con cajas y paneles) el acero
// cepillado de la nevera reflejaba cajas que no existen en la cocina y la visera de la campana se leía como latón.
// ¿La malla de centro (x, z) y material `material` usa el entorno `e`?
export function enEntorno(e, material, x, z) {
  const [x0, x1, z0, z1] = e.caja;
  return Boolean(material) && e.materiales.includes(material.name) && x >= x0 && x <= x1 && z >= z0 && z <= z1;
}

// Saturación de cada variante del entorno local al cargarla (corrección 08, ronda 2): el entorno «dia» ya se renderiza
// con el mundo desaturado de los renders de revisión, pero lo que refleja el frente del freezer seguía frío (B − R =
// +13 en sRGB contra −5 en Blender, cámara acero_neutro; +9 con 0,5 y +7 con 0,2, el resto es el color base del acero,
// (0,477; 0,477; 0,507)). La de las luces, tal cual (su tono cálido está medido: visera/azulejo).
export const SATURACION_ENTORNO = { dia: 0.2, luces: 1.0 };

// Mezcla los píxeles RGBA (sRGB de 8 bits) con su luma: s = 1 los deja igual, 0 los deja grises.
export function desaturarPixeles(px, s) {
  for (let i = 0; i < px.length; i += 4) {
    const y = 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2];
    for (let k = 0; k < 3; k++) px[i + k] = Math.round(y + (px[i + k] - y) * s);
  }
  return px;
}

function desaturarTextura(tex, s, doc = globalThis.document) {
  if (s >= 1 || !doc || !tex.image) return tex;
  try {
    const { width: w, height: h } = tex.image;
    const cv = doc.createElement("canvas");
    cv.width = w; cv.height = h;
    const ctx = cv.getContext("2d");
    ctx.drawImage(tex.image, 0, 0);
    const d = ctx.getImageData(0, 0, w, h);
    desaturarPixeles(d.data, s);
    ctx.putImageData(d, 0, 0);
    const t = new THREE.CanvasTexture(cv);
    t.mapping = tex.mapping;
    t.colorSpace = tex.colorSpace;
    tex.dispose();
    return t;
  } catch (err) {
    return tex;                                   // sin canvas 2D: queda como viene
  }
}

// Carga cada imagen de D.entornos como mapa prefiltrado (PMREM): las variantes de `imagenes` («luces», con los grupos
// que nacen encendidos, y «dia», sólo el sol y el cielo) o, en un JSON anterior, la única `imagen`. -> Map id ->
// { luces, dia } (texturas); los que fallen quedan fuera (esas mallas siguen con el entorno general).
export async function cargarEntornos(renderer, D, rutaBase = RUTA_MODELO) {
  const out = new Map();
  if (!D.entornos || !D.entornos.length) return out;
  const pm = new THREE.PMREMGenerator(renderer);
  const cargador = new THREE.TextureLoader();
  for (const e of D.entornos) {
    const variantes = {};
    for (const [nombre, archivo] of Object.entries(e.imagenes || { luces: e.imagen })) {
      try {
        let tex = await cargador.loadAsync(rutaBase + archivo);
        tex.mapping = THREE.EquirectangularReflectionMapping;
        tex.colorSpace = THREE.SRGBColorSpace;
        tex = desaturarTextura(tex, SATURACION_ENTORNO[nombre] ?? 1);
        variantes[nombre] = pm.fromEquirectangular(tex).texture;
        tex.dispose();
      } catch (err) {
        console.warn("[tour] entorno local no disponible", archivo, err);
      }
    }
    if (Object.keys(variantes).length) out.set(e.id, variantes);
  }
  pm.dispose();
  return out;
}

// La variante del entorno local según la luz de su recinto (el grupo `e.grupo`, cocina_techo): encendida, la de las
// luces; apagada, la del día; si falta, la otra. `variantes`: { luces, dia } o una textura sola.
export function varianteEntorno(variantes, lucesEncendidas) {
  if (!variantes || variantes.isTexture) return variantes || null;
  return (lucesEncendidas ? variantes.luces || variantes.dia : variantes.dia || variantes.luces) || null;
}

// Pone en cada material con entorno local la variante y la intensidad que tocan (`intensidades` = { luces, dia } del
// momento, cielo.js): se llama en cada cuadro, porque la luz de la cocina puede cambiar con un interruptor, el panel o
// el momento. `gruposLuz`: Map id -> { encendido }. `referencia` ({ luces, dia }, opcional): la escala de normalización
// del entorno con que se calibraron las intensidades; la intensidad se multiplica por referencia / entornos[].escala de
// esa variante (contrato, sección 6), para que un render nuevo del entorno no cambie el brillo del reflejo.
// Devuelve true si cambió algo (hay que redibujar).
export function factorEscalaEntorno(escala, referencia, variante) {
  const e = escala && escala[variante], r = referencia && referencia[variante];
  return typeof e === "number" && typeof r === "number" && e > 0 ? r / e : 1;
}

export function actualizarEntornos(materiales, gruposLuz, intensidades, referencia = null) {
  let cambio = false;
  for (const mat of materiales) {
    const g = mat.userData.grupoEntorno ? gruposLuz.get(mat.userData.grupoEntorno) : null;
    const on = g ? Boolean(g.encendido) : true;
    const tex = varianteEntorno(mat.userData.variantesEntorno, on);
    const variante = on ? "luces" : "dia";
    const base = typeof intensidades === "number" ? intensidades : (intensidades || {})[variante] ?? 1;
    const inten = base * factorEscalaEntorno(mat.userData.escalaEntorno, referencia, variante);
    if (tex && mat.envMap !== tex) { mat.envMap = tex; mat.needsUpdate = true; cambio = true; }
    if (mat.envMapIntensity !== inten) { mat.envMapIntensity = inten; cambio = true; }
  }
  return cambio;
}

// Proyección en caja (parallax) del entorno local: un equirectangular visto desde un solo punto no tiene paralaje, y la
// visera de la campana, que mira hacia la cubierta y los muebles bajos oscuros, reflejaba el piso claro que se ve desde
// el centro de la cocina (se leía como latón). El reflejo se corta contra la caja del recinto (e.caja en XZ y e.alto en
// Y) y se mira desde e.centro, como las sondas de caja de Eevee en los renders de revisión. Modifica los shaders de
// MeshStandardMaterial (three r160) en onBeforeCompile; si no encuentra los trozos que espera, deja el shader como está.
export const MARCA_REFLEJO = "reflectVec = inverseTransformDirection( reflectVec, viewMatrix );";
export function proyeccionCaja(shader, e, THREE_ = THREE) {
  const [x0, x1, z0, z1] = e.caja;
  const [y0, y1] = e.alto || [0, 2.4];
  const chunk = THREE_.ShaderChunk.envmap_physical_pars_fragment;
  if (!chunk.includes(MARCA_REFLEJO) || !shader.vertexShader.includes("#include <project_vertex>")) return false;
  shader.uniforms.uCajaMin = { value: new THREE_.Vector3(x0, y0, z0) };
  shader.uniforms.uCajaMax = { value: new THREE_.Vector3(x1, y1, z1) };
  shader.uniforms.uCentroEntorno = { value: new THREE_.Vector3(...e.centro) };
  shader.vertexShader = "varying vec3 vPosMundo;\n" + shader.vertexShader.replace("#include <project_vertex>",
    "#include <project_vertex>\nvPosMundo = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;");
  const proyectar = `
    uniform vec3 uCajaMin; uniform vec3 uCajaMax; uniform vec3 uCentroEntorno; varying vec3 vPosMundo;
    vec3 proyectarCaja( vec3 R ) {
      vec3 Rs = R + vec3( 1e-5 );
      vec3 t = max( ( uCajaMax - vPosMundo ) / Rs, ( uCajaMin - vPosMundo ) / Rs );
      float d = min( min( t.x, t.y ), t.z );
      return normalize( vPosMundo + R * max( d, 0.0 ) - uCentroEntorno );
    }\n`;
  const nuevo = proyectar + chunk.replace(MARCA_REFLEJO, MARCA_REFLEJO + "\n reflectVec = proyectarCaja( reflectVec );");
  shader.fragmentShader = shader.fragmentShader.replace("#include <envmap_physical_pars_fragment>", nuevo);
  return true;
}

// Un clon del material por entorno (no por malla: la fusión de abajo los sigue juntando) con envMap = el del entorno y
// userData.entornoLocal = su id (aplicarMomento le da su propia intensidad) y la proyección en caja. Va antes de
// registrar los móviles: la puerta de la nevera también lo usa.
function aplicarEntornos(raiz, entornos, texturas) {
  const clones = new Map();
  const caja = new THREE.Box3();
  const c = new THREE.Vector3();
  raiz.traverse((o) => {
    if (!o.isMesh || Array.isArray(o.material)) return;
    caja.setFromObject(o).getCenter(c);
    for (const e of entornos) {
      const variantes = texturas.get(e.id);
      const tex = varianteEntorno(variantes, true);
      if (!tex || !enEntorno(e, o.material, c.x, c.z)) continue;
      const k = `${e.id}|${o.material.uuid}`;
      if (!clones.has(k)) {
        const clon = o.material.clone();
        clon.envMap = tex;
        clon.userData = { ...clon.userData, entornoLocal: e.id, variantesEntorno: variantes, grupoEntorno: e.grupo,
          escalaEntorno: e.escala || null };
        if (e.centro) {
          clon.onBeforeCompile = (sh) => { proyeccionCaja(sh, e); };
          clon.customProgramCacheKey = () => `entorno_${e.id}`;
        }
        clones.set(k, clon);
      }
      o.material = clones.get(k);
      break;
    }
  });
  return clones.size;
}

// Exterior (bloque 08, contrato 2.4, sección 4): las mallas con extras.exterior (en el material o en el nodo) pasan a
// un material sin luces (exterior.js), con su sombreado por vértice calculado en espacio de mundo (aquí con el sol de la
// escena; aplicarMomento lo rehace con el del momento, sombrearExterior), y se fusionan por
// material en un grupo aparte, `exteriorFusionado`: no entra en el raycast del piso (tocar la calle por la ventana no
// manda a caminar hacia afuera) y se puede ocultar entero. Devuelve { grupo, materiales }.
export function prepararExterior(raiz, D, excluidos) {
  const haciaSol = haciaSolDe(D);
  const sueloY = D.exterior && typeof D.exterior.suelo_y === "number" ? D.exterior.suelo_y : 0;
  const clones = new Map();
  const porMaterial = new Map();
  raiz.traverse((o) => {
    if (!o.isMesh || excluidos.has(o) || Array.isArray(o.material) || !esExterior(o.material, o)) return;
    let mat = clones.get(o.material);
    if (!mat) { mat = materialExterior(o.material); clones.set(o.material, mat); }
    const geo = o.geometry.clone();
    geo.applyMatrix4(o.matrixWorld);
    sombrear(geo, haciaSol, sueloY, mat.userData.capa);
    if (!porMaterial.has(mat)) porMaterial.set(mat, []);
    porMaterial.get(mat).push(geo);
    excluidos.add(o);
  });
  const grupo = new THREE.Group();
  grupo.name = "Depto_Exterior";
  for (const [material, geometrias] of porMaterial) {
    const fusionada = mergeGeometries(geometrias, false);
    for (const g of geometrias) g.dispose();
    if (!fusionada) { console.warn("[tour] no se pudo fusionar el exterior", material.name); continue; }
    const malla = new THREE.Mesh(fusionada, material);
    malla.name = `Depto_Exterior_${material.name || "sin_nombre"}`;
    malla.matrixAutoUpdate = false;
    grupo.add(malla);
  }
  return { grupo, materiales: [...clones.values()] };
}

// Arma { estaticoFusionado, exteriorFusionado, materialesExterior, sueltos, moviles, interruptores, lucesTHREE,
// gruposLuz, tocables } a partir de `raiz` (gltf.scene) y `D` (depto_colisiones.json ya parseado).
// `opciones.entornos`: Map id -> textura de cargarEntornos (opcional).
export function prepararEscena(raiz, D, opciones = {}) {
  arreglarVidrios(raiz);
  raiz.updateWorldMatrix(true, true);
  if (opciones.entornos && D.entornos) aplicarEntornos(raiz, D.entornos, opciones.entornos);

  const excluidos = new Set();
  const tocables = [];              // Mesh[] — únicos objetos contra los que hace raycast interaccion.js
  const mapaTocable = new Map();    // Mesh -> { tipo: "movil" | "interruptor", ref }

  // --- piezas móviles: puertas, ventanas, cajones, clósets, nevera (moviles[] del contrato) ---
  const moviles = (D.moviles || []).map((m) => ({
    m, t: m.abierta ? 1 : 0, objetivo: m.abierta ? 1 : 0, t0: m.abierta ? 1 : 0,
    fase: duracionPorClase(m.clase), // "ya terminada": pasoMundo no la vuelve a tocar hasta el próximo toggle
    nodo: null,
  }));
  for (const v of moviles) {
    const nodo = raiz.getObjectByName(v.m.nodo);
    if (!nodo) { console.warn("[tour] falta el nodo móvil", v.m.nodo); continue; }
    v.nodo = nodo;
    nodo.traverse((o) => {
      excluidos.add(o);
      if (o.isMesh) { tocables.push(o); mapaTocable.set(o, { tipo: "movil", ref: v }); }
    });
  }

  // --- interruptores y lámparas: cualquier nodo con userData.grupo_luz (viene de los extras del glTF) ---
  // Primero las teclas con registro propio en interruptores[] (cada una manda sólo su grupo), después el resto
  // (placas, lámparas y nodos sin registro): una placa doble ya no se queda con las mallas de sus teclas.
  const interruptores = [];
  const explicitos = new Map((D.interruptores || []).map((i) => [i.nodo, i]));
  const registrar = (o, info, grupoLuz) => {
    const grupos = info ? info.grupos : String(grupoLuz).split(",").map((s) => s.trim()).filter(Boolean);
    let tecla = null;
    if (info) tecla = info.tecla ? raiz.getObjectByName(info.tecla) : null;
    else o.traverse((h) => { if (!tecla && /_Tecla$/.test(h.name || "")) tecla = h; });
    const reg = { nodo: o, grupos, tecla, encendido: false, faseGrado: 0 };
    interruptores.push(reg);
    o.traverse((d) => {
      excluidos.add(d);
      if (d.isMesh && !mapaTocable.has(d)) { tocables.push(d); mapaTocable.set(d, { tipo: "interruptor", ref: reg }); }
    });
  };
  for (const info of ordenarInterruptores(D.interruptores || [])) {
    if (!(info.tecla && info.tecla === info.nodo)) break;            // ordenadas: las teclas van primero
    const o = raiz.getObjectByName(info.nodo);
    if (o && !interruptores.some((r) => r.nodo === o)) registrar(o, info, null);
  }
  raiz.traverse((o) => {
    const grupoLuz = o.userData && o.userData.grupo_luz;
    if (!grupoLuz || interruptores.some((r) => r.nodo === o)) return;
    if (excluidos.has(o) && !explicitos.has(o.name)) return;          // hija de un interruptor ya registrado
    registrar(o, explicitos.get(o.name), grupoLuz);
  });

  // --- luces y sus grupos (deducidos por recinto si el JSON todavía no trae grupos_luz) ---
  const { luces: datosLuces, grupos: datosGrupos } = deducirGrupos(D);
  // encendidoInicial: el estado de autor (grupos_luz[].encendido), que aplicarMomento() respeta al cambiar de momento.
  // La etiqueta queda en el idioma de la página (etiquetaGrupo: js.tour.luz.<id>, o la del modelo si no hay clave).
  const gruposLuz = new Map(datosGrupos.map((g) => [g.id, {
    ...g, etiqueta: etiquetaGrupo(g, D.recintos_etiquetas), encendidoInicial: Boolean(g.encendido), luces: [],
    clones: new Map(), intensidad: g.encendido ? 1 : 0,
    _desde: g.encendido ? 1 : 0, _hasta: g.encendido ? 1 : 0, faseMs: FUNDIDO_MS, // ya "asentado": sin fundido al iniciar
  }]));
  const lucesTHREE = [];
  const ampolletas = [];            // nodos emisivos: quedan fuera de la fusión y van a `sueltos` (se dibujan aparte)
  for (const l of datosLuces) {
    const lucesDeEsta = crearLucesTHREE(THREE, l);    // una puntual, o un foco si trae cono_deg
    lucesTHREE.push(...lucesDeEsta);
    if (l.tipo !== "puntual") continue;
    const grupo = gruposLuz.get(l.grupo);
    if (!grupo) continue;
    grupo.luces.push(...lucesDeEsta);
    const nodoAmpolleta = raiz.getObjectByName(l.ampolleta);
    if (!nodoAmpolleta || !nodoAmpolleta.isMesh) {
      console.warn("[tour] no se encontró la ampolleta", l.ampolleta, "de", l.nombre);
      continue;
    }
    excluidos.add(nodoAmpolleta);
    if (!ampolletas.includes(nodoAmpolleta)) ampolletas.push(nodoAmpolleta);
    const base = Array.isArray(nodoAmpolleta.material) ? nodoAmpolleta.material[0] : nodoAmpolleta.material;
    let clon = grupo.clones.get(base.uuid);
    if (!clon) {
      clon = base.clone();
      clon.emissive = new THREE.Color(colorLinealAHex(l.color));
      clon.emissiveIntensity = grupo.intensidad * 1.4;
      grupo.clones.set(base.uuid, clon);
    }
    nodoAmpolleta.material = clon;
  }
  // Aplica de una vez la intensidad inicial (encendido/apagado según grupos_luz o la deducción): el fundido
  // de pasoMundo() solo corre cuando `faseMs < FUNDIDO_MS`, y los grupos nacen ya "asentados".
  for (const grupo of gruposLuz.values()) {
    for (const luz of grupo.luces) luz.intensity = intensidadBase(luz) * grupo.intensidad;
    for (const clon of grupo.clones.values()) clon.emissiveIntensity = 1.4 * grupo.intensidad;
  }
  // Estado inicial de cada interruptor según sus grupos, con la tecla ya inclinada hacia ese lado.
  for (const reg of interruptores) {
    reg.encendido = interruptorEncendido(reg.grupos, gruposLuz);
    reg._grados = reg.encendido ? TILT_TECLA_DEG : -TILT_TECLA_DEG;
    if (reg.tecla) reg.tecla.rotation.x = (reg._grados * Math.PI) / 180;
  }

  // --- exterior: fondo barato y aparte (antes de la fusión de lo estático, que ya no lo toma) ---
  const exterior = prepararExterior(raiz, D, excluidos);

  // --- fusión de las mallas estáticas por material, con la transformación de mundo horneada ---
  const porMaterial = new Map();
  raiz.traverse((o) => {
    if (!o.isMesh || excluidos.has(o) || Array.isArray(o.material)) return;
    const geo = o.geometry.clone();
    geo.applyMatrix4(o.matrixWorld);
    if (!porMaterial.has(o.material)) porMaterial.set(o.material, []);
    porMaterial.get(o.material).push(geo);
    excluidos.add(o); // para no volver a tocarlo si el árbol tiene referencias repetidas
  });
  const estaticoFusionado = new THREE.Group();
  estaticoFusionado.name = "Depto_Estatico";
  for (const [material, geometrias] of porMaterial) {
    const fusionada = mergeGeometries(geometrias, false);
    for (const g of geometrias) g.dispose();
    const malla = new THREE.Mesh(fusionada, material);
    malla.name = `Depto_Estatico_${material.name || "sin_nombre"}`;
    malla.matrixAutoUpdate = false; // ya está en espacio de mundo; congelar la matriz evita recomponerla cada cuadro
    estaticoFusionado.add(malla);
  }

  // Los móviles e interruptores quedan sueltos en la raíz de la escena con su transformación de mundo
  // (Object3D.attach preserva la posición mundial al cambiar de padre).
  // Una tecla con registro propio sigue siendo hija de su placa (gira en su X local, relativa a la placa): sólo se
  // sueltan los interruptores sin otro interruptor por encima.
  // Las ampolletas también se sueltan (antes quedaban fuera de la fusión y de la escena: no se dibujaba ningún
  // filamento), salvo las que ya cuelgan de un móvil o de un interruptor suelto, que viajan con él.
  const nodosInterruptor = new Set(interruptores.map((i) => i.nodo));
  const bajoOtro = (o) => { for (let p = o.parent; p; p = p.parent) if (nodosInterruptor.has(p)) return true; return false; };
  const nodosMoviles = new Set(moviles.map((v) => v.nodo).filter(Boolean));
  const bajoSuelto = (o) => {
    for (let p = o.parent; p; p = p.parent) if (nodosInterruptor.has(p) || nodosMoviles.has(p)) return true;
    return false;
  };
  const sueltos = [...moviles.map((v) => v.nodo), ...interruptores.map((i) => i.nodo).filter((n) => !bajoOtro(n)),
    ...ampolletas.filter((a) => !bajoSuelto(a))].filter(Boolean);

  return { estaticoFusionado, exteriorFusionado: exterior.grupo, materialesExterior: exterior.materiales, sueltos, moviles,
    interruptores, lucesTHREE, gruposLuz, tocables, mapaTocable, ampolletas };
}
