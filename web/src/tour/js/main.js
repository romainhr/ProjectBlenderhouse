// Orquesta el visor: crea la escena, carga el modelo, conecta controles/interacción/luces/interfaz y corre
// el bucle de cuadro (con render bajo demanda y resolución adaptable). Ver docs/contrato-interaccion.md y
// CLAUDE.md § Método de trabajo.
import { THREE } from "./three.js";
import * as carga from "./carga.js";
import * as colision from "./colision.js";
import { crearControles } from "./controles.js";
import { crearInteraccion, apuntar, puntoEnElSuelo, resaltar, quitarResaltado, etiquetaAccion, activar, fijarGrupo, pasoMundo, MOTIVO_CAMINO } from "./interaccion.js";
import { MOMENTOS, MOMENTO_POR_DEFECTO, generarCieloCanvas, cargarPanoramas } from "./cielo.js";
import { RoomEnvironment } from "../../vendor/three/jsm/environments/RoomEnvironment.js";
import { NOMBRES_RECINTO, estadoGruposParaMomento } from "./luces.js";
import { prepararMinimapa, dibujarMinimapa, recintoTocado } from "./minimapa.js";
import { crearCalidad, activarDepuracion, textoDepuracion } from "./calidad.js";
import * as ui from "./interfaz.js";

const $ = (s) => document.querySelector(s);
const tactil = matchMedia("(pointer: coarse)").matches;
const debug = activarDepuracion();
ui.marcarTactil(tactil);
if (debug) ui.mostrarDepuracion();

// ---------------------------------------------------------------------------------------------- escena
const canvas = $("#vista");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: !tactil, powerPreference: "high-performance" });
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
const calidad = crearCalidad(renderer, tactil);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(70, 1, 0.05, 500);
camera.rotation.order = "YXZ";

const ambiente = new THREE.HemisphereLight(0xe7ecef, 0x746a5c, 0.4);
scene.add(ambiente);
// Mapa de entorno neutro (un cuarto con paneles emisivos) para el reflejo difuso y especular del PBR; se
// genera una sola vez (PMREM de 256 px) y su intensidad por material la fija cada momento del día.
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
pmrem.dispose();
let panoramas = {};

// Con ?debug, un asomo de estado para inspeccionar desde la consola (no se usa en producción). Va después
// de declarar camera/scene: son const y acceder antes de esta línea sería un error de inicialización.
if (debug) window.__tour = { get yo() { return controles && controles.yo; }, get D() { return D; }, get estado() { return estado; }, get controles() { return controles; }, camera, scene };

function ajustarTamano() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  sucio = true;
}
window.addEventListener("resize", ajustarTamano);

let sol = null;
let momentoActual = MOMENTO_POR_DEFECTO;
function aplicarMomento(id, estadoInteraccion) {
  const m = MOMENTOS[id];
  momentoActual = id;
  scene.background = panoramas[id] || generarCieloCanvas(m.cielo);
  scene.backgroundIntensity = m.fondoIntensidad;
  scene.traverse((o) => {
    if (!o.isMesh) return;
    for (const mat of Array.isArray(o.material) ? o.material : [o.material]) {
      if (!mat || !("envMapIntensity" in mat)) continue;
      // metales y espejos reflejan más; el resto recibe un relleno suave
      mat.envMapIntensity = m.entorno * (mat.metalness > 0.5 ? 1.8 : 1);
    }
  });
  ambiente.intensity = m.ambiente;
  renderer.toneMappingExposure = m.exposicion;
  if (sol) { sol.color.set(m.sol.color); sol.intensity = m.sol.intensidad; }
  if (estadoInteraccion) {
    // cada grupo vuelve al estado de autor para este momento (grupos_luz[].encendido): el día apaga todo; la tarde y
    // la noche prenden sólo los que nacen encendidos (techos), no los veladores, apliques ni la lámpara de pie
    const estados = estadoGruposParaMomento(estadoInteraccion.gruposLuz.values(), m.lucesEncendidas);
    for (const [id2, encendido] of estados) fijarGrupo(estadoInteraccion, id2, encendido);
    ui.refrescarGruposLuzUI(estadoInteraccion.gruposLuz);
  }
  sucio = true;
}

// ---------------------------------------------------------------------------------------------- carga
let D = null, estado = null, controles = null, M = null;
let sucio = true;

async function iniciar() {
  ajustarTamano();
  try {
    D = await carga.cargarColisiones();
  } catch (e) {
    ui.marcarError("No se pudieron leer los datos de colisión. Recarga la página.");
    console.error(e);
    return;
  }
  const variante = carga.esTactilOPantallaChica() ? "depto_movil.gltf" : "depto.gltf";
  let gltf;
  try {
    gltf = await carga.cargarGLTF(variante, (f) => ui.actualizarCarga(f, `Cargando el modelo… ${Math.round(f * 100)} %`));
  } catch (e) {
    ui.marcarError("No se pudo cargar el modelo 3D. Revisa la conexión y recarga la página.");
    console.error(e);
    return;
  }
  ui.actualizarCarga(1, "Preparando la escena…");

  const preparado = carga.prepararEscena(gltf.scene, D);
  estado = crearInteraccion(preparado);
  scene.add(estado.estaticoFusionado);
  for (const nodo of estado.sueltos) scene.attach(nodo);
  for (const luz of estado.lucesTHREE) {
    scene.add(luz);
    if (luz.userData.esSol) sol = luz;
  }

  if (D.exterior && (D.exterior.panoramas || D.exterior.panorama)) {
    panoramas = await cargarPanoramas(carga.RUTA_MODELO, D.exterior);
  }
  aplicarMomento(MOMENTO_POR_DEFECTO, estado);

  const [ix, iz] = D.inicio.posicion, [mx, mz] = D.inicio.mirar;
  const yawInicial = Math.atan2(ix - mx, iz - mz);
  controles = crearControles({ canvas, tactil, inicioXZ: D.inicio.posicion, yawInicial });
  cablearControles();

  M = prepararMinimapa($("#lienzo-plano"), D);
  $("#lienzo-plano").addEventListener("click", (e) => {
    const r = recintoTocado(M, D, $("#lienzo-plano"), e.clientX, e.clientY);
    if (r) irARecinto(r);
  });

  ui.pintarGruposLuz(estado.gruposLuz, {
    onCambiar: (id, encendido) => { fijarGrupo(estado, id, encendido); sucio = true; },
    onTodo: (encendido) => { for (const id of estado.gruposLuz.keys()) fijarGrupo(estado, id, encendido); sucio = true; },
  });
  ui.iniciarMomento(MOMENTO_POR_DEFECTO, (id) => aplicarMomento(id, estado));
  ui.iniciarPantallaCompleta();
  ui.iniciarPaneles();

  ui.actualizarCarga(1, `Listo · ${D.estaticos.length} obstáculos estáticos`);
  ui.habilitarEntrar();
  sucio = true;
}

function irARecinto(nombre) {
  const p = D.recintos[nombre];
  const [x, z] = colision.libreCercano(p[0], p[1], D.estaticos, estado.moviles, D.radio);
  controles.yo.x = x; controles.yo.z = z;
  ui.mostrarAviso((D.recintos_etiquetas && D.recintos_etiquetas[nombre]) || NOMBRES_RECINTO[nombre] || nombre, 1400);
  sucio = true;
}

// ---------------------------------------------------------------------------------------------- controles
function cablearControles() {
  $("#entrar").addEventListener("click", () => {
    ui.ocultarPortada();
    if (!tactil) ui.mostrarMira();
    controles.empezarMarcha();
    sucio = true;
  });
  controles.onPointerLockPerdido = () => ui.mostrarAviso("Clic en la vista para seguir mirando", 2500);
  controles.onActivar = () => {
    if (!estado.objetoApuntado) return;
    const entrada = estado.mapaTocable.get(estado.objetoApuntado);
    if (!entrada) return;
    if (activar(estado, entrada, { x: controles.yo.x, z: controles.yo.z, radio: D.radio })) {
      ui.refrescarGruposLuzUI(estado.gruposLuz);
    } else if (entrada.tipo === "movil") {
      ui.mostrarAviso(estado.motivo || MOTIVO_CAMINO, 2000);
    }
    sucio = true;
  };
  controles.onToqueCorto = (nx, ny, clientX, clientY) => {
    const hit = apuntar(estado, camera, nx, ny);
    if (hit) {
      const etiqueta = etiquetaAccion(hit.entrada, estado.gruposLuz); // antes de activar(): la acción que se hará
      const ok = activar(estado, hit.entrada, { x: controles.yo.x, z: controles.yo.z, radio: D.radio });
      if (ok) {
        ui.refrescarGruposLuzUI(estado.gruposLuz);
        ui.mostrarChip(etiqueta, clientX, clientY);
        chipHasta = performance.now() + 1400;
      } else if (hit.entrada.tipo === "movil") {
        ui.mostrarAviso(estado.motivo || MOTIVO_CAMINO, 2000);
      }
      sucio = true;
      return;
    }
    const punto = puntoEnElSuelo(camera, nx, ny, estado.estaticoFusionado);
    if (punto) controles.caminoObjetivo = { x: punto.x, z: punto.z };
  };
}

// ---------------------------------------------------------------------------------------------- movimiento
const VEL_CAMINAR = 1.4, VEL_CORRER = 2.6;
function moverJugador(dt) {
  const yo = controles.yo;
  let f = 0, s = 0;
  if (controles.caminoObjetivo) {
    const dx = controles.caminoObjetivo.x - yo.x, dz = controles.caminoObjetivo.z - yo.z;
    const dist = Math.hypot(dx, dz);
    if (dist < 0.12) { controles.caminoObjetivo = null; }
    else {
      // f/s en ejes locales (adelante = -Z del yaw actual): se gira suavemente hacia el punto y se avanza.
      const yawObjetivo = Math.atan2(dx, dz);
      let delta = yawObjetivo - yo.yaw;
      delta = Math.atan2(Math.sin(delta), Math.cos(delta));
      yo.yaw += Math.max(-4 * dt, Math.min(4 * dt, delta));
      f = 1;
    }
  } else {
    const intento = controles.leerIntento(dt);
    f = intento.f; s = intento.s;
  }
  const L = Math.hypot(f, s);
  if (L < 1e-3) return;
  const vel = (controles.corriendo ? VEL_CORRER : VEL_CAMINAR) * Math.min(1, L);
  const fn = f / L, sn = s / L;
  const fx = -Math.sin(yo.yaw), fz = -Math.cos(yo.yaw), rx = Math.cos(yo.yaw), rz = -Math.sin(yo.yaw);
  const dx = (fx * fn + rx * sn) * vel * dt, dz = (fz * fn + rz * sn) * vel * dt;
  const [nx, nz] = colision.mover(yo.x, yo.z, dx, dz, D.estaticos, estado.moviles, D.radio);
  if (controles.caminoObjetivo && Math.hypot(nx - yo.x, nz - yo.z) < 1e-4) controles.caminoObjetivo = null; // chocó: se detiene
  yo.x = nx; yo.z = nz;
}

// ---------------------------------------------------------------------------------------------- bucle
let cuadrosApuntado = 0;
let chipHasta = 0;
let ultimoApunte = null; // { yaw, pitch, x, z }
const reloj = new THREE.Clock();
function actualizarApuntado() {
  const usaMira = !tactil && controles && controles.activo;
  if (!usaMira) { quitarResaltado(estado); ui.ocultarPista(); return; }
  const yo = controles.yo;
  const semovio = !ultimoApunte || Math.abs(yo.yaw - ultimoApunte.yaw) > 1e-3 || Math.abs(yo.pitch - ultimoApunte.pitch) > 1e-3
    || Math.abs(yo.x - ultimoApunte.x) > 1e-3 || Math.abs(yo.z - ultimoApunte.z) > 1e-3;
  cuadrosApuntado++;
  // Solo se recalcula el rayo cuando la cámara se movió o cada 3 cuadros como máximo, según el encargo.
  if (!semovio && cuadrosApuntado % 3 !== 0) return;
  ultimoApunte = { yaw: yo.yaw, pitch: yo.pitch, x: yo.x, z: yo.z };
  const hit = apuntar(estado, camera, 0, 0);
  resaltar(estado, hit ? hit.objeto : null);
  ui.marcarMiraActiva(!!hit);
  if (hit) ui.mostrarPista(etiquetaAccion(hit.entrada, estado.gruposLuz)); else ui.ocultarPista();
}

function pasoCuadro(dt) {
  ui.actualizarAviso();
  if (tactil && controles) ui.dibujarJoystick(controles.palanca);
  if (performance.now() >= chipHasta) ui.ocultarChip();

  let actividad = false;
  if (D && controles) {
    // También antes de "Recorrer": la portada se dibuja sobre la vista inicial, no desde el origen a ras del piso.
    camera.position.set(controles.yo.x, D.ojo, controles.yo.z);
    camera.rotation.set(controles.yo.pitch, controles.yo.yaw, 0);
  }
  if (D && estado && controles && controles.activo) {
    moverJugador(dt);
    pasoMundo(estado, dt, { x: controles.yo.x, z: controles.yo.z, radio: D.radio });
    camera.position.set(controles.yo.x, D.ojo, controles.yo.z);
    camera.rotation.set(controles.yo.pitch, controles.yo.yaw, 0);
    actualizarApuntado();
    dibujarMinimapa(M, D, estado.moviles, controles.yo, sucio);
    actividad = controles.entradaActiva
      || estado.moviles.some((v) => v.t !== v.objetivo)
      || Array.from(estado.gruposLuz.values()).some((g) => g.faseMs < 150)
      || estado.interruptores.some((r) => r._faseTecla !== undefined && r._faseTecla < 150);
  }

  if (sucio || actividad) {
    const t0 = performance.now();
    renderer.render(scene, camera);
    calidad.registrarCuadro(performance.now() - t0);
    sucio = false;
  }
  if (debug) ui.actualizarDepuracion(textoDepuracion(renderer, calidad, 1 / Math.max(dt, 1 / 240)));
}

function cuadro() {
  requestAnimationFrame(cuadro);
  pasoCuadro(Math.min(0.05, reloj.getDelta()));
}

iniciar();
cuadro();

// Con ?debug, permite avanzar el mundo "a mano" desde la consola (rAF se pausa si la pestaña queda oculta,
// p. ej. en pruebas automatizadas): window.__tour.paso(1/60) simula exactamente un cuadro de esa duración.
if (debug) window.__tour.paso = (dt) => pasoCuadro(dt);
// Con ?debug, mide el costo real de dibujar la vista actual (sirve también en un teléfono con depuración remota):
// `n` renders seguidos, cada uno esperando a la GPU con un readPixels de 1 px. Devuelve ms por cuadro (mediana, p90)
// y cuántas luces de three.js hay visibles. No cambia nada de la escena.
if (debug) {
  window.__tour.renderer = renderer;
  window.__tour.medirCuadro = (n = 30) => {
    const gl = renderer.getContext();
    const px = new Uint8Array(4);
    const t = [];
    renderer.render(scene, camera);                   // compila lo que falte antes de medir
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
    for (let i = 0; i < n; i++) {
      const t0 = performance.now();
      renderer.render(scene, camera);
      gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
      t.push(performance.now() - t0);
    }
    t.sort((a, b) => a - b);
    let luces = 0;
    scene.traverse((o) => { if (o.isLight && o.visible && !o.isHemisphereLight) luces += 1; });
    return { mediana_ms: +t[n >> 1].toFixed(1), p90_ms: +t[Math.floor(n * 0.9)].toFixed(1), luces,
      llamadas: renderer.info.render.calls, pixelRatio: renderer.getPixelRatio() };
  };
}
