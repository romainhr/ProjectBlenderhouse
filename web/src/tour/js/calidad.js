// Resolución adaptable y overlay de depuración (?debug). Techo de pixelRatio: 1,75 en escritorio, 1,5 en
// táctil; baja a un factor 0,75 si el cuadro promedia más de ~24 ms sostenidos, sube de nuevo si
// sobra margen. Mide con performance.now() alrededor de renderer.render(), no con requestAnimationFrame
// (que incluye el tiempo de espera de vsync, no el costo real del cuadro).
const VENTANA = 24;         // cuadros que promedia antes de decidir
const MS_DESCARTE = 200;    // cuadros de compilación de shaders o subida de texturas: no cuentan
const MS_ALTO = 24;
const MS_BAJO = 14;

// Techo 1,5 en táctil y 1,75 en escritorio (la v2 usaba 1,75 fijo). Con 1,25 el teléfono perdía 28-63 % de
// nitidez en ladrillo y microcemento (diagnóstico del 2026-09-26). `alCambiar` se llama tras setPixelRatio,
// que vacía el lienzo: el visor debe redibujar o la vista queda en blanco hasta la próxima entrada.
export function crearCalidad(renderer, tactil, alCambiar = () => {}) {
  const techo = tactil ? 1.5 : 1.75;
  const estado = { factor: 1, historia: [], techo };
  function aplicar(inicial = false) {
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, techo) * estado.factor);
    if (!inicial) alCambiar(); // al crear, el visor todavía no declaró su estado de redibujo
  }
  aplicar(true);
  return {
    techo,
    get factor() { return estado.factor; },
    aplicar,
    registrarCuadro(ms) {
      if (ms > MS_DESCARTE) return;
      estado.historia.push(ms);
      if (estado.historia.length < VENTANA) return;
      const prom = estado.historia.reduce((a, b) => a + b, 0) / estado.historia.length;
      estado.historia.length = 0;
      if (prom > MS_ALTO && estado.factor > 0.75) { estado.factor = 0.75; aplicar(); }
      else if (prom < MS_BAJO && estado.factor < 1) { estado.factor = 1; aplicar(); }
    },
  };
}

export function activarDepuracion() {
  return new URLSearchParams(window.location.search).has("debug");
}

export function textoDepuracion(renderer, calidad, fps) {
  const info = renderer.info;
  return `${fps.toFixed(0)} fps · pixelRatio ${(renderer.getPixelRatio()).toFixed(2)} (×${calidad.factor})\n`
    + `draw calls ${info.render.calls} · triángulos ${info.render.triangles}\n`
    + `geometrías ${info.memory.geometries} · texturas ${info.memory.textures}`;
}
