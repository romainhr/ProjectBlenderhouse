// Interpolación con aceleración/desaceleración para piezas móviles (puertas, cajones, veleros) y para el
// fundido de los grupos de luz. Puro (sin three.js ni DOM) para que web/tests/*.test.mjs lo importe directo.

export function easeInOutCubic(x) {
  const c = Math.max(0, Math.min(1, x));
  return c < 0.5 ? 4 * c * c * c : 1 - Math.pow(-2 * c + 2, 3) / 2;
}

// Duración de la animación de apertura/cierre según la `clase` del contrato de interacción (moviles[].clase).
// Cajones: 0,35 s (livianos). Puertas, ventanas, clósets, la nevera y otros muebles: 0,6 s. Sin `clase`
// (datos aún sin el contrato v2) se trata como puerta.
export function duracionPorClase(clase) {
  return clase === "cajon" ? 0.35 : 0.6;
}

// Estado de una pieza en animación: { t, objetivo, t0, fase }. `t` es la apertura actual (0..1, la misma
// que usa colision.js), `objetivo` hacia dónde va, `t0` el valor de `t` cuando empezó el tramo actual y
// `fase` el tiempo acumulado en ese tramo. Se guarda así (y no como velocidad) para poder invertir el
// sentido a medio camino sin saltos.
export function iniciarToggle(estado, forzar) {
  const objetivo = forzar !== undefined ? forzar : (estado.objetivo > 0.5 ? 0 : 1);
  if (objetivo === estado.objetivo && estado.fase > 0) return estado;
  return { t: estado.t, objetivo, t0: estado.t, fase: 0 };
}

// Un paso del tiempo `dt` (segundos). No pasa de `objetivo` ni retrocede antes de `t0`. Devuelve un estado
// nuevo (no muta `estado`).
export function pasoAnimacion(estado, dt, duracion) {
  if (estado.t === estado.objetivo && estado.fase >= duracion) return estado;
  const fase = Math.min(duracion, estado.fase + Math.max(0, dt));
  const suave = easeInOutCubic(fase / duracion);
  const t = estado.t0 + (estado.objetivo - estado.t0) * suave;
  return { t: fase >= duracion ? estado.objetivo : t, objetivo: estado.objetivo, t0: estado.t0, fase };
}

// Congela la animación en su apertura actual (p. ej. porque la hoja topó con el caminante): el siguiente
// toggle debe partir de aquí, no del objetivo original.
export function congelar(estado) {
  return { t: estado.t, objetivo: estado.t, t0: estado.t, fase: 0 };
}

// Fundido lineal de 0 a 1 en `ms` milisegundos, usado para los grupos de luz (150 ms) y para transiciones
// de momento del día. `fase` en milisegundos.
export function pasoFundido(fase, dt, ms) {
  return Math.min(ms, Math.max(0, fase + dt));
}
export function valorFundido(fase, ms) {
  return ms <= 0 ? 1 : Math.max(0, Math.min(1, fase / ms));
}
