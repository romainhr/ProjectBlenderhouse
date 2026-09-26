// Cajones detrás de una corredera (contrato de interacción v2, sección 1: `depende_de` y `bloquea`). Puro, sin
// three.js, para que web/tests/*.test.mjs lo importe directo.
//
// Un móvil `v` es { m (registro de moviles[]), t (apertura 0..1), objetivo (0 | 1), ... } y `porNodo` un Map
// nodo -> v. Reglas:
// - un cajón con `depende_de` sólo se abre si esas hojas están corridas del todo y quieta cualquier otra hoja que
//   lo bloquee (en un clóset de dos hojas, la B corrida tapa la columna de cajones);
// - antes de mover una hoja con `bloquea`, se cierran los cajones abiertos que tapa (cajonesQueCerrar) y la hoja
//   espera a que terminen (ESPERA_HOJA_S).

export const ESPERA_HOJA_S = 0.35; // = duracionPorClase("cajon") (animacion.js)

const quieta = (v) => v.t === 0 && v.objetivo === 0;
const corrida = (v) => v.t >= 1 && v.objetivo >= 1;

export function puedeAbrir(v, porNodo) {
  const requeridas = v.m.depende_de || [];
  if (!requeridas.length) return true;
  for (const nodo of requeridas) {
    const hoja = porNodo.get(nodo);
    if (hoja && !corrida(hoja)) return false;
  }
  for (const otra of porNodo.values()) {
    if (otra === v || requeridas.includes(otra.m.nodo)) continue;
    if ((otra.m.bloquea || []).includes(v.m.nodo) && !quieta(otra)) return false;
  }
  return true;
}

export function cajonesQueCerrar(hoja, porNodo) {
  return (hoja.m.bloquea || []).map((n) => porNodo.get(n)).filter((c) => c && (c.t > 0 || c.objetivo > 0));
}
