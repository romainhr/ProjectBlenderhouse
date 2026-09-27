// Orquesta el visor: crea la escena, carga el modelo, conecta controles/interacción/luces/interfaz y corre
// el bucle de cuadro (con render bajo demanda y resolución adaptable). Ver docs/contrato-interaccion.md y
// CLAUDE.md § Método de trabajo.
import { THREE } from "./three.js";
import * as carga from "./carga.js";
import * as colision from "./colision.js";
import { crearControles } from "./controles.js";
import { crearInteraccion, apuntar, puntoEnElSuelo, resaltar, quitarResaltado, etiquetaAccion, activar, fijarGrupo, pasoMundo, MOTIVO_CAMINO } from "./interaccion.js";
import { MOMENTOS, MOMENTO_POR_DEFECTO, generarCieloCanvas, cargarPanoramas } from "./cielo.js";
import { aplicarMomentoExterior } from "./exterior.js";
import { RoomEnvironment } from "../../vendor/three/jsm/environments/RoomEnvironment.js";
import { NOMBRES_RECINTO, estadoGruposParaMomento, gruposDelPanel } from "./luces.js";
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
// MSAA también en teléfonos con dpr < 2 (en GPU por teselas es barato); con dpr ≥ 2 el propio pixelRatio suaviza.
const renderer = new THREE.WebGLRenderer({ canvas, antialias: !tactil || (window.devicePixelRatio || 1) < 2, powerPreference: "high-performance" });
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
const calidad = crearCalidad(renderer, tactil, () => { sucio = true; });

const scene = new THREE.Scene();
// 72°: el mismo de la v2 y de los renders. Lejos a 2 000 m (bloque 08): el suelo del exterior llega a 900 m y las
// siluetas a 340; la precisión de profundidad la fija el plano cercano, no el lejano.
const camera = new THREE.PerspectiveCamera(72, 1, 0.05, 2000);
camera.rotation.order = "YXZ";

// Suelo del hemisferio neutro (corrección 07c, ronda 2): con 0x746a5c (marrón) teñía de cálido todo lo que mira hacia
// abajo, como el cielo de concreto, que se leía como terciado de pino. La intensidad la fija cada momento (cielo.js).
const ambiente = new THREE.HemisphereLight(0xe7ecef, 0x6c6c6a, 0.4);
scene.add(ambiente);
// Mapa de entorno neutro (un cuarto con paneles emisivos) para el reflejo difuso y especular del PBR; se
// genera una sola vez (PMREM de 256 px) y su intensidad por material la fija cada momento del día.
const pmrem = new THREE.PMREMGenerator(renderer);
// Con `renderer`, three r160 sube la luz interna de RoomEnvironment de 5 a 900: es el relleno que reemplaza la
// luz rebotada (sin él el cielo queda negro). Pero a envMapIntensity 0,42 lavaba las texturas (≈7 veces el
// relleno de la v2; diagnóstico del 2026-09-26): la intensidad por momento (cielo.js) queda a la mitad.
// Sigma 0,1 (corrección 07c, ronda 2; antes 0,04): el estudio genérico se refleja más difuso y no dibuja sus cajas en
// los metales pulidos que no tienen entorno local (D.entornos, carga.js).
scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.1).texture;
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
      // entorno local (la cocina, contrato 2.2): su propia intensidad por momento. Si no, los metales pulidos y los
      // espejos reflejan más y el resto recibe un relleno suave. Corrección 07c (ronda 2): el refuerzo de 1,8 era para
      // todo metal y hacía del acero cepillado (rugosidad 0,25-0,35) un espejo del estudio; queda sólo bajo 0,25. Un
      // material con mapa de rugosidad trae roughness = 1 (el factor de glTF): queda en 1 también.
      if (mat.userData && mat.userData.entornoLocal) continue;          // actualizarEntornos, en cada cuadro
      mat.envMapIntensity = m.entorno * (mat.metalness > 0.5 && mat.roughness < 0.25 ? 1.8 : 1);
    }
  });
  ambiente.intensity = m.ambiente;
  renderer.toneMappingExposure = m.exposicion;
  if (sol) { sol.color.set(m.sol.color); sol.intensity = m.sol.intensidad; }
  // exterior (bloque 08): tinte, bruma de las siluetas con el horizonte del panorama y emisión de las ventanas vecinas
  const pano = panoramas[id];
  aplicarMomentoExterior(materialesExterior, m, id, (D && D.exterior) || {}, pano && pano.userData.horizonte);
  if (estadoInteraccion) {
    // cada grupo vuelve al estado de autor para este momento (grupos_luz[].encendido): el día apaga todo; la tarde y
    // la noche prenden sólo los que nacen encendidos (techos), no los veladores, apliques ni la lámpara de pie
    const estados = estadoGruposParaMomento(estadoInteraccion.gruposLuz.values(), m.lucesEncendidas);
    for (const [id2, encendido] of estados) fijarGrupo(estadoInteraccion, id2, encendido);
    ui.refrescarGruposLuzUI(estadoInteraccion.gruposLuz);
    carga.actualizarEntornos(materialesEntorno, estadoInteraccion.gruposLuz, m.entornoLocal);
  }
  sucio = true;
}

// ---------------------------------------------------------------------------------------------- carga
let D = null, estado = null, controles = null, M = null;
let materialesEntorno = [];   // materiales con entorno local (carga.js): su variante sigue a la luz de la cocina
let materialesExterior = [];  // materiales del paisaje (exterior.js): tinte y emisión por momento
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

  // Filtrado anisotrópico: la mejora más barata para pisos y muros vistos en ángulo rasante (+30 a +110 % de
  // nitidez medida). 4 alcanza en teléfonos; en escritorio, 8.
  const aniso = Math.min(renderer.capabilities.getMaxAnisotropy(), tactil ? 4 : 8);
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    for (const mat of Array.isArray(o.material) ? o.material : [o.material]) {
      for (const k of ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap", "emissiveMap"]) {
        if (mat && mat[k]) { mat[k].anisotropy = aniso; mat[k].needsUpdate = true; }
      }
    }
  });
  const entornos = await carga.cargarEntornos(renderer, D);
  const preparado = carga.prepararEscena(gltf.scene, D, { entornos });
  estado = crearInteraccion(preparado);
  preparado.estaticoFusionado.traverse((o) => { if (o.isMesh && o.material.userData.entornoLocal) materialesEntorno.push(o.material); });
  for (const n of preparado.sueltos) n.traverse((o) => {
    if (o.isMesh && o.material.userData && o.material.userData.entornoLocal && !materialesEntorno.includes(o.material)) materialesEntorno.push(o.material);
  });
  scene.add(estado.estaticoFusionado);
  if (preparado.exteriorFusionado) scene.add(preparado.exteriorFusionado);
  materialesExterior = preparado.materialesExterior || [];
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
    onTodo: (encendido) => { for (const g of gruposDelPanel(estado.gruposLuz)) fijarGrupo(estado, g.id, encendido); sucio = true; },
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

  // la variante del entorno local sigue a la luz de la cocina (interruptor, panel o momento)
  if (estado && carga.actualizarEntornos(materialesEntorno, estado.gruposLuz, MOMENTOS[momentoActual].entornoLocal)) sucio = true;
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
// Con ?debug, captura la vista desde una cámara dada, para compararla con un render de revisión de Blender desde la
// misma cámara (corrección 07c, ronda 2; tools/servidor_captura.py guarda el PNG). op = { pos: [x, y, z], mirar:
// [x, y, z] (glTF), fov (vertical, grados), ancho, alto, momento, grupos: {id: bool}, abrir: [nodo...], nombre }.
// Deja el momento, los grupos y las piezas como los pide; la cámara vuelve a la del recorrido en el cuadro siguiente.
if (debug) {
  window.__tour.capturar = async (op) => {
    const lejos = { x: 1e3, z: 1e3, radio: D.radio };
    if (op.momento) aplicarMomento(op.momento, estado);
    for (const [id, on] of Object.entries(op.grupos || {})) fijarGrupo(estado, id, on);
    for (const v of estado.moviles) {
      const quiere = (op.abrir || []).includes(v.m.nodo);
      if (v.m.clase !== "puerta" && v.m.clase !== "corredera" && (v.objetivo >= 1) !== quiere) {
        activar(estado, { tipo: "movil", ref: v }, lejos);
      }
    }
    for (let i = 0; i < 80; i++) pasoMundo(estado, 0.05, lejos);     // animaciones y fundidos terminados
    carga.actualizarEntornos(materialesEntorno, estado.gruposLuz, MOMENTOS[momentoActual].entornoLocal);
    ui.refrescarGruposLuzUI(estado.gruposLuz);
    renderer.setPixelRatio(1);
    renderer.setSize(op.ancho || 1280, op.alto || 800, false);
    camera.aspect = (op.ancho || 1280) / (op.alto || 800);
    camera.fov = op.fov || 72;
    camera.position.set(...op.pos);
    camera.lookAt(...op.mirar);
    camera.updateProjectionMatrix();
    renderer.render(scene, camera);
    const blob = await new Promise((r) => renderer.domElement.toBlob(r, "image/png"));
    let respuesta = "sin nombre";
    if (op.nombre) respuesta = await (await fetch(`/__captura/${op.nombre}.png`, { method: "POST", body: blob })).text();
    camera.fov = 72;
    calidad.aplicar(true);
    ajustarTamano();
    return respuesta;
  };
}
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
