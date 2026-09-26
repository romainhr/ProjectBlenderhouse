// Carga del modelo (modelo/depto.gltf o depto_movil.gltf, según el dispositivo) y de depto_colisiones.json,
// más la preparación de la escena: arregla materiales de vidrio, arma los registros de piezas móviles,
// interruptores y grupos de luz, y fusiona las mallas estáticas por material para bajar los draw calls
// (requisito de rendimiento: < 90). A diferencia de exports/depto_tour.html (que armaba un GLB en memoria
// porque las páginas de claude.ai no servían .glb/.bin), aquí Netlify sirve modelo/depto.gltf y depto.bin
// directo: se cargan con GLTFLoader normal.
import { THREE } from "./three.js";
import { GLTFLoader } from "../../vendor/three/jsm/loaders/GLTFLoader.js";
import { mergeGeometries } from "../../vendor/three/jsm/utils/BufferGeometryUtils.js";
import { deducirGrupos, crearLuzTHREE, colorLinealAHex, FUNDIDO_MS, INTENSIDAD_POR_WATT } from "./luces.js";
import { duracionPorClase } from "./animacion.js";

export const RUTA_MODELO = "modelo/";

// Materiales de vidrio REALES (nombres exactos del contrato de interacción): Depto_Mat_VidrioNegro es el
// anafe y el frente del horno, opaco a propósito. Antes se usaba una expresión /Vidrio/ que también lo
// volvía transparente por error.
const MATERIALES_VIDRIO = new Set([
  "Depto_Mat_Vidrio", "Depto_Mat_VidrioBombilla", "Depto_Mat_VidrioEsmerilado", "Depto_Mat_VidrioReloj",
]);

export function esTactilOPantallaChica() {
  const tactil = matchMedia("(pointer: coarse)").matches;
  return tactil || Math.min(window.innerWidth, window.innerHeight) < 900;
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

function arreglarVidrios(raiz) {
  raiz.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    mats.forEach((mat, i) => {
      if (!mat || !MATERIALES_VIDRIO.has(mat.name)) return;
      const v = new THREE.MeshStandardMaterial({
        name: mat.name, color: mat.color, roughness: mat.roughness, metalness: 0, transparent: true,
        opacity: mat.name === "Depto_Mat_VidrioEsmerilado" ? 0.55 : 0.16, depthWrite: false, side: THREE.DoubleSide,
      });
      if (Array.isArray(o.material)) o.material[i] = v; else o.material = v;
    });
  });
}

// Arma { estaticoFusionado, sueltos, moviles, interruptores, lucesTHREE, gruposLuz, tocables } a partir de
// `raiz` (gltf.scene) y `D` (depto_colisiones.json ya parseado).
export function prepararEscena(raiz, D) {
  arreglarVidrios(raiz);
  raiz.updateWorldMatrix(true, true);

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
  const interruptores = [];
  const explicitos = new Map((D.interruptores || []).map((i) => [i.nodo, i]));
  raiz.traverse((o) => {
    if (excluidos.has(o)) return;
    const grupoLuz = o.userData && o.userData.grupo_luz;
    if (!grupoLuz) return;
    const info = explicitos.get(o.name);
    const grupos = info ? info.grupos : String(grupoLuz).split(",").map((s) => s.trim()).filter(Boolean);
    let tecla = null;
    if (info && info.tecla) tecla = raiz.getObjectByName(info.tecla);
    else o.traverse((h) => { if (!tecla && /_Tecla$/.test(h.name || "")) tecla = h; });
    const reg = { nodo: o, grupos, tecla, encendido: false, faseGrado: 0 };
    interruptores.push(reg);
    o.traverse((d) => {
      excluidos.add(d);
      if (d.isMesh) { tocables.push(d); mapaTocable.set(d, { tipo: "interruptor", ref: reg }); }
    });
  });

  // --- luces y sus grupos (deducidos por recinto si el JSON todavía no trae grupos_luz) ---
  const { luces: datosLuces, grupos: datosGrupos } = deducirGrupos(D);
  const gruposLuz = new Map(datosGrupos.map((g) => [g.id, {
    ...g, luces: [], clones: new Map(), intensidad: g.encendido ? 1 : 0,
    _desde: g.encendido ? 1 : 0, _hasta: g.encendido ? 1 : 0, faseMs: FUNDIDO_MS, // ya "asentado": sin fundido al iniciar
  }]));
  const lucesTHREE = [];
  for (const l of datosLuces) {
    const luzTHREE = crearLuzTHREE(THREE, l);
    lucesTHREE.push(luzTHREE);
    if (l.tipo !== "puntual") continue;
    const grupo = gruposLuz.get(l.grupo);
    if (!grupo) continue;
    grupo.luces.push(luzTHREE);
    const nodoAmpolleta = raiz.getObjectByName(l.ampolleta);
    if (!nodoAmpolleta || !nodoAmpolleta.isMesh) {
      console.warn("[tour] no se encontró la ampolleta", l.ampolleta, "de", l.nombre);
      continue;
    }
    excluidos.add(nodoAmpolleta);
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
    for (const luz of grupo.luces) luz.intensity = (luz.userData.potenciaW || 40) * INTENSIDAD_POR_WATT * grupo.intensidad;
    for (const clon of grupo.clones.values()) clon.emissiveIntensity = 1.4 * grupo.intensidad;
  }

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
  const sueltos = [...moviles.map((v) => v.nodo), ...interruptores.map((i) => i.nodo)].filter(Boolean);

  return { estaticoFusionado, sueltos, moviles, interruptores, lucesTHREE, gruposLuz, tocables, mapaTocable };
}
