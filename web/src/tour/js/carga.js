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

export const RUTA_MODELO = "modelo/";

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

function arreglarVidrios(raiz) {
  // Un material transparente por material de origen (no uno por malla): así la fusión por material de más abajo
  // junta todos los vidrios iguales en una sola llamada de dibujo.
  const cache = new Map();
  raiz.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    mats.forEach((mat, i) => {
      if (!mat || !MATERIALES_VIDRIO.has(mat.name)) return;
      if (cache.has(mat)) {
        if (Array.isArray(o.material)) o.material[i] = cache.get(mat); else o.material = cache.get(mat);
        return;
      }
      const v = new THREE.MeshStandardMaterial({
        name: mat.name, color: mat.color, roughness: mat.roughness, metalness: 0, transparent: true,
        opacity: mat.name === "Depto_Mat_VidrioEsmerilado" ? 0.55 : 0.16, depthWrite: false, side: THREE.DoubleSide,
      });
      cache.set(mat, v);
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
        const tex = await cargador.loadAsync(rutaBase + archivo);
        tex.mapping = THREE.EquirectangularReflectionMapping;
        tex.colorSpace = THREE.SRGBColorSpace;
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
// el momento. `gruposLuz`: Map id -> { encendido }. Devuelve true si cambió algo (hay que redibujar).
export function actualizarEntornos(materiales, gruposLuz, intensidades) {
  let cambio = false;
  for (const mat of materiales) {
    const g = mat.userData.grupoEntorno ? gruposLuz.get(mat.userData.grupoEntorno) : null;
    const on = g ? Boolean(g.encendido) : true;
    const tex = varianteEntorno(mat.userData.variantesEntorno, on);
    const inten = typeof intensidades === "number" ? intensidades : (intensidades || {})[on ? "luces" : "dia"] ?? 1;
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
        clon.userData = { ...clon.userData, entornoLocal: e.id, variantesEntorno: variantes, grupoEntorno: e.grupo };
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

// Arma { estaticoFusionado, sueltos, moviles, interruptores, lucesTHREE, gruposLuz, tocables } a partir de
// `raiz` (gltf.scene) y `D` (depto_colisiones.json ya parseado). `opciones.entornos`: Map id -> textura de
// cargarEntornos (opcional).
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
  const gruposLuz = new Map(datosGrupos.map((g) => [g.id, {
    ...g, encendidoInicial: Boolean(g.encendido), luces: [], clones: new Map(), intensidad: g.encendido ? 1 : 0,
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

  return { estaticoFusionado, sueltos, moviles, interruptores, lucesTHREE, gruposLuz, tocables, mapaTocable, ampolletas };
}
