// Interacción genérica con lo que mira la cámara (escritorio) o lo que se toca (móvil): abrir/cerrar piezas
// móviles y encender/apagar grupos de luz desde los interruptores. El raycast es SOLO contra `tocables`
// (nunca contra toda la escena) y a lo más 2,5 m, según el encargo.
import { THREE } from "./three.js";
import { estadoMovil, chocaMovil } from "./colision.js";
import { iniciarToggle, pasoAnimacion, congelar, duracionPorClase, valorFundido } from "./animacion.js";
import { INTENSIDAD_POR_WATT, FUNDIDO_MS } from "./luces.js";

const DISTANCIA_MAXIMA = 2.5;
const TILT_TECLA_DEG = 8;

const TEXTO_POR_CLASE = {
  puerta: "puerta", ventana: "ventana", cajon: "cajón", closet: "clóset", nevera: "nevera", mueble: "mueble",
};

export function crearInteraccion(preparado) {
  const rayo = new THREE.Raycaster();
  rayo.far = DISTANCIA_MAXIMA;
  const resaltados = new WeakMap(); // Mesh -> material(es) original(es), para poder devolverlo
  let apuntado = null;              // el objeto Mesh actualmente resaltado (o null)

  return {
    ...preparado,
    rayo,
    apuntado: null,
    _resaltados: resaltados,
    get objetoApuntado() { return apuntado; },
    set objetoApuntado(v) { apuntado = v; },
  };
}

// nx, ny en [-1, 1] (coordenadas normalizadas de three.js, como las que usa THREE.Raycaster.setFromCamera).
export function apuntar(estado, camera, nx, ny) {
  if (!estado.tocables.length) return null;
  estado.rayo.setFromCamera({ x: nx, y: ny }, camera);
  const hits = estado.rayo.intersectObjects(estado.tocables, false);
  if (!hits.length) return null;
  const obj = hits[0].object;
  return estado.mapaTocable.has(obj) ? { objeto: obj, entrada: estado.mapaTocable.get(obj), punto: hits[0].point } : null;
}

// Raycast contra TODA la geometría estática visible (no contra `tocables`), para el toque-en-el-piso del
// modo táctil (caminar hasta el punto). Es una llamada aparte y solo se usa cuando el toque no cayó sobre
// un `tocable`, así que no compite con el límite de "solo contra los interactivos". `estatico` es el grupo
// fusionado que devuelve carga.js.
export function puntoEnElSuelo(camera, nx, ny, estatico) {
  const rayo = new THREE.Raycaster();
  rayo.setFromCamera({ x: nx, y: ny }, camera);
  const hits = rayo.intersectObject(estatico, true);
  return hits.length ? hits[0].point : null;
}

// Tinte emisivo leve (terracota) sobre un material clonado: no se toca el original ni el que comparten
// otras mallas con el mismo material.
function materialResaltado(base) {
  const clon = base.clone();
  if ("emissive" in clon) {
    clon.emissive = new THREE.Color(0xa8481f);
    clon.emissiveIntensity = 0.4;
  }
  return clon;
}

export function resaltar(estado, mesh) {
  if (estado.objetoApuntado === mesh) return;
  quitarResaltado(estado);
  if (!mesh) { estado.objetoApuntado = null; return; }
  if (!estado._resaltados.has(mesh)) {
    const original = mesh.material;
    const nuevo = Array.isArray(original) ? original.map(materialResaltado) : materialResaltado(original);
    estado._resaltados.set(mesh, { original, resaltado: nuevo });
  }
  mesh.material = estado._resaltados.get(mesh).resaltado;
  estado.objetoApuntado = mesh;
}
export function quitarResaltado(estado) {
  const mesh = estado.objetoApuntado;
  if (!mesh) return;
  const par = estado._resaltados.get(mesh);
  if (par) mesh.material = par.original;
  estado.objetoApuntado = null;
}

// Texto de la pista/chip para una entrada de `mapaTocable`.
export function etiquetaAccion(entrada) {
  if (entrada.tipo === "interruptor") return entrada.ref.encendido ? "apagar la luz" : "encender la luz";
  const v = entrada.ref;
  const abrir = v.objetivo < 0.5;
  if (v.m.etiqueta) return (abrir ? "Abrir " : "Cerrar ") + v.m.etiqueta.replace(/^(Abrir|Cerrar)\s+/i, "").toLowerCase();
  const cosa = TEXTO_POR_CLASE[v.m.clase] || "pieza";
  return `${abrir ? "Abrir" : "Cerrar"} ${cosa}`;
}

// Activa lo que se está apuntando/tocando (clic, E o toque corto). `walker` = { x, z, radio }.
export function activar(estado, entrada, walker) {
  if (entrada.tipo === "movil") {
    const v = entrada.ref;
    const nuevo = iniciarToggle(v, undefined);
    if (chocaMovil(walker.x, walker.z, v, nuevo.objetivo, walker.radio)) return false; // no dejes atrapado al caminante
    Object.assign(v, nuevo);
    return true;
  }
  const reg = entrada.ref;
  const nuevoEstado = !reg.encendido;
  reg.encendido = nuevoEstado;
  reg._desdeGrados = reg._grados || 0;
  reg._hastaGrados = nuevoEstado ? TILT_TECLA_DEG : -TILT_TECLA_DEG;
  reg._faseTecla = 0;
  for (const id of reg.grupos) {
    const grupo = estado.gruposLuz.get(id);
    if (!grupo) continue;
    grupo.encendido = nuevoEstado;
    grupo._desde = grupo.intensidad;
    grupo._hasta = nuevoEstado ? 1 : 0;
    grupo.faseMs = 0;
  }
  return true;
}

// Enciende ("encender"|"apagar"|"alternar") uno o todos los grupos, para el botón "Apagar/encender todo" y
// el panel de luces.
export function fijarGrupo(estado, idGrupo, encendido) {
  const grupo = estado.gruposLuz.get(idGrupo);
  if (!grupo || grupo.encendido === encendido) return;
  grupo.encendido = encendido;
  grupo._desde = grupo.intensidad;
  grupo._hasta = encendido ? 1 : 0;
  grupo.faseMs = 0;
}

// Un paso del mundo interactivo: anima puertas/cajones (deteniéndolos si la hoja topa con el caminante),
// funde los grupos de luz y sus ampolletas, e inclina la tecla de los interruptores. `dt` en segundos.
export function pasoMundo(estado, dt, walker) {
  for (const v of estado.moviles) {
    if (v.t === v.objetivo && v.fase >= duracionPorClase(v.m.clase)) continue;
    const duracion = duracionPorClase(v.m.clase);
    const siguiente = pasoAnimacion(v, dt, duracion);
    if (chocaMovil(walker.x, walker.z, v, siguiente.t, walker.radio)) {
      Object.assign(v, congelar(v));
    } else {
      Object.assign(v, siguiente);
    }
    const e = estadoMovil(v.m, v.t);
    if (v.m.tipo === "bisagra") v.nodo.rotation.set(0, e.ang, 0);
    else v.nodo.position.set(e.x, v.m.posicion[1], e.z);
  }

  for (const grupo of estado.gruposLuz.values()) {
    if (grupo.faseMs >= FUNDIDO_MS) continue;
    grupo.faseMs = Math.min(FUNDIDO_MS, grupo.faseMs + dt * 1000);
    const k = valorFundido(grupo.faseMs, FUNDIDO_MS);
    grupo.intensidad = grupo._desde + ((grupo._hasta ?? grupo.intensidad) - grupo._desde) * k;
    for (const luz of grupo.luces) luz.intensity = (luz.userData.potenciaW || 40) * INTENSIDAD_POR_WATT * grupo.intensidad;
    for (const clon of grupo.clones.values()) clon.emissiveIntensity = 1.4 * grupo.intensidad;
  }

  for (const reg of estado.interruptores) {
    if (!reg.tecla || reg._faseTecla === undefined || reg._faseTecla >= 150) continue;
    reg._faseTecla = Math.min(150, reg._faseTecla + dt * 1000);
    const k = valorFundido(reg._faseTecla, 150);
    reg._grados = (reg._desdeGrados ?? 0) + ((reg._hastaGrados ?? 0) - (reg._desdeGrados ?? 0)) * k;
    reg.tecla.rotation.x = (reg._grados * Math.PI) / 180;
  }
}
