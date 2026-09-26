// Resolución adaptable y overlay de depuración (?debug). Techo de pixelRatio: 1,5 en escritorio, 1,25 en
// táctil (batería); baja a un factor 0,75 si el cuadro promedia más de ~24 ms sostenidos, sube de nuevo si
// sobra margen. Mide con performance.now() alrededor de renderer.render(), no con requestAnimationFrame
// (que incluye el tiempo de espera de vsync, no el costo real del cuadro).
const VENTANA = 24;         // cuadros que promedia antes de decidir
const MS_ALTO = 24;
const MS_BAJO = 14;

export function crearCalidad(renderer, tactil) {
  const techo = tactil ? 1.25 : 1.5;
  const estado = { factor: 1, historia: [], techo };
  function aplicar() {
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, techo) * estado.factor);
  }
  aplicar();
  return {
    techo,
    get factor() { return estado.factor; },
    aplicar,
    registrarCuadro(ms) {
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
