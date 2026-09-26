// Entrada: teclado y ratón (escritorio, con pointer lock) y táctil (Pointer Events: palanca virtual abajo a
// la izquierda para caminar, arrastrar el resto de la pantalla para mirar, toque corto para interactuar o
// caminar hasta el piso). Sin pointer lock en táctil. Reutiliza la idea de exports/depto_tour.html, pero
// separada del resto: este módulo solo entrega la intención de movimiento y la mirada; no conoce la
// colisión ni la escena.
const TECLAS_MOV = new Set([
  "KeyW", "KeyA", "KeyS", "KeyD", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "ShiftLeft", "ShiftRight",
]);
const ZONA_PALANCA_ANCHO = 0.4;   // 40% del ancho, según el encargo
const UMBRAL_TOQUE_CORTO_MS = 250;
const UMBRAL_TOQUE_CORTO_PX = 12;

export function crearControles({ canvas, tactil, inicioXZ, yawInicial }) {
  const yo = { x: inicioXZ[0], z: inicioXZ[1], yaw: yawInicial, pitch: -0.05 };
  const teclas = new Set();
  let palancaVec = { x: 0, y: 0 };
  let activo = false;
  let caminoObjetivo = null;
  let ultimoMiroEn = 0;

  const controles = {
    yo,
    tactil,
    get activo() { return activo; },
    get corriendo() { return teclas.has("ShiftLeft") || teclas.has("ShiftRight"); },
    get caminoObjetivo() { return caminoObjetivo; },
    set caminoObjetivo(v) { caminoObjetivo = v; },
    // Para el render bajo demanda: ¿hay alguna entrada activa ahora mismo? (teclas, palanca, arrastre para
    // mirar hace poco, o un camino automático en curso).
    get entradaActiva() {
      return teclas.size > 0 || Math.hypot(palancaVec.x, palancaVec.y) > 1e-3 || caminoObjetivo !== null
        || performance.now() - ultimoMiroEn < 120;
    },
    // Intención de movimiento en ejes locales: adelante/atrás y lateral, cada uno en [-1, 1]. Las flechas
    // izquierda/derecha giran directamente (no son un eje lateral), por eso reciben `dt` aparte.
    leerIntento(dt) {
      let f = 0, s = 0;
      if (teclas.has("KeyW") || teclas.has("ArrowUp")) f += 1;
      if (teclas.has("KeyS") || teclas.has("ArrowDown")) f -= 1;
      if (teclas.has("KeyD")) s += 1;
      if (teclas.has("KeyA")) s -= 1;
      if (teclas.has("ArrowLeft")) yo.yaw += 1.8 * dt;
      if (teclas.has("ArrowRight")) yo.yaw -= 1.8 * dt;
      f -= palancaVec.y; s += palancaVec.x;
      return { f, s };
    },
    empezarMarcha() {
      activo = true;
      if (!tactil && canvas.requestPointerLock) {
        try { const p = canvas.requestPointerLock(); if (p && p.catch) p.catch(() => {}); } catch (_) { /* opcional */ }
      }
      canvas.focus();
    },
    // callbacks que asigna quien use el módulo (main.js)
    onActivar: null,           // desktop: E o clic con el puntero bloqueado
    onToqueCorto: null,        // móvil: (nx, ny) normalizados [-1,1], toque que no fue sobre la palanca
    onPointerLockPerdido: null,
  };

  document.addEventListener("gesturestart", (e) => e.preventDefault());  // iOS: sin pellizco para hacer zoom
  canvas.addEventListener("dblclick", (e) => e.preventDefault());

  function mirarDelta(dx, dy, k) {
    yo.yaw -= dx * k;
    yo.pitch = Math.max(-1.35, Math.min(1.35, yo.pitch - dy * k));
    ultimoMiroEn = performance.now();
  }

  if (!tactil) {
    canvas.addEventListener("click", () => {
      if (!activo) return;
      if (document.pointerLockElement !== canvas) {
        try { const p = canvas.requestPointerLock(); if (p && p.catch) p.catch(() => {}); } catch (_) { /* opcional */ }
        return;
      }
      if (controles.onActivar) controles.onActivar();
    });
    document.addEventListener("pointerlockchange", () => {
      if (document.pointerLockElement !== canvas && activo && controles.onPointerLockPerdido) controles.onPointerLockPerdido();
    });
    document.addEventListener("mousemove", (e) => {
      if (document.pointerLockElement !== canvas) return;
      mirarDelta(e.movementX, e.movementY, 0.0022);
    });
    // Sin bloqueo del puntero (algunos navegadores lo rechazan): arrastrar con el ratón también mira.
    let arrastre = null;
    canvas.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "mouse" || document.pointerLockElement === canvas) return;
      arrastre = { x: e.clientX, y: e.clientY };
    });
    window.addEventListener("pointerup", (e) => { if (e.pointerType === "mouse") arrastre = null; });
    window.addEventListener("pointermove", (e) => {
      if (!arrastre || e.pointerType !== "mouse") return;
      mirarDelta(e.clientX - arrastre.x, e.clientY - arrastre.y, 0.004);
      arrastre = { x: e.clientX, y: e.clientY };
    });
    window.addEventListener("keydown", (e) => {
      if (!activo) return;
      if (TECLAS_MOV.has(e.code)) { teclas.add(e.code); e.preventDefault(); }
      if ((e.code === "KeyE" || e.code === "Enter") && controles.onActivar) controles.onActivar();
    });
    window.addEventListener("keyup", (e) => teclas.delete(e.code));
    window.addEventListener("blur", () => teclas.clear());
  } else {
    const toques = new Map();
    controles.palanca = { visible: false, x: 0, y: 0, pomoX: 0, pomoY: 0 };
    canvas.addEventListener("pointerdown", (e) => {
      if (e.pointerType === "mouse" || !activo) return;
      try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* algunos navegadores lo rechazan; seguimos igual */ }
      const enPalanca = e.clientX < window.innerWidth * ZONA_PALANCA_ANCHO && e.clientY > window.innerHeight * 0.3;
      toques.set(e.pointerId, { palanca: enPalanca, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, t0: performance.now() });
      if (enPalanca) {
        caminoObjetivo = null; // el usuario retoma el control manual
        controles.palanca = { visible: true, x: e.clientX, y: e.clientY, pomoX: 0, pomoY: 0 };
      }
    });
    canvas.addEventListener("pointermove", (e) => {
      const t = toques.get(e.pointerId);
      if (!t) return;
      if (t.palanca) {
        const dx = e.clientX - t.x0, dy = e.clientY - t.y0, L = Math.hypot(dx, dy), max = 48;
        const k = L > max ? max / L : 1;
        palancaVec = { x: (dx * k) / max, y: (dy * k) / max };
        controles.palanca.pomoX = dx * k; controles.palanca.pomoY = dy * k;
      } else {
        mirarDelta(e.clientX - t.x, e.clientY - t.y, 0.0055);
      }
      t.x = e.clientX; t.y = e.clientY;
    });
    function soltar(e) {
      const t = toques.get(e.pointerId);
      if (!t) return;
      toques.delete(e.pointerId);
      if (t.palanca) {
        palancaVec = { x: 0, y: 0 };
        controles.palanca = { visible: false, x: 0, y: 0, pomoX: 0, pomoY: 0 };
      }
      const corto = performance.now() - t.t0 < UMBRAL_TOQUE_CORTO_MS
        && Math.hypot(e.clientX - t.x0, e.clientY - t.y0) < UMBRAL_TOQUE_CORTO_PX;
      if (corto && !t.palanca && controles.onToqueCorto) {
        const nx = (e.clientX / window.innerWidth) * 2 - 1, ny = -(e.clientY / window.innerHeight) * 2 + 1;
        controles.onToqueCorto(nx, ny, e.clientX, e.clientY);
      }
    }
    canvas.addEventListener("pointerup", soltar);
    canvas.addEventListener("pointercancel", soltar);
  }

  return controles;
}
