// En qué modo corre el portal. Sin DOM: recibe hostname, search y la configuración.
//   "real"           -> Supabase con la configuración del build (dist/js/config.js)
//   "simulado"       -> datos en memoria y login falso; SÓLO en un host local (sin configuración o con ?simulado=1)
//   "sin_configurar" -> fuera de un host local y sin configuración: el portal avisa y no deja ingresar

export const HOSTS_LOCALES = Object.freeze(["localhost", "127.0.0.1", "[::1]", "::1"]);

export function esLocal(hostname) {
  const h = String(hostname || "").toLowerCase();
  return HOSTS_LOCALES.includes(h) || h.endsWith(".localhost");
}

// Igual que web/build.py (RE_SUPABASE) más la API local de `supabase start` (http://127.0.0.1:54321), por si se usa.
const RE_URL = /^(https:\/\/[a-z0-9-]+(\.[a-z0-9-]+)+|http:\/\/(localhost|127\.0\.0\.1)(:\d{2,5})?)$/i;

export function configValida(config) {
  if (!config) return false;
  const url = String(config.url || "");
  const clave = String(config.clave || "");
  return RE_URL.test(url) && clave.length >= 20 && !/\s/.test(clave);
}

export function decidirModo({ hostname, search = "", config }) {
  const local = esLocal(hostname);
  let pideSimulado = false;
  try {
    pideSimulado = new URLSearchParams(search).get("simulado") === "1";
  } catch {
    pideSimulado = false;
  }
  if (local && (pideSimulado || !configValida(config))) return "simulado";
  if (configValida(config)) return "real";
  return "sin_configurar";
}

/**
 * Sólo en modo simulado: ?sin-idiomas=1 imita una base sin la migración 0005 (sin valor_en ni valor_fr), para ver en
 * el navegador cómo avisa el portal y que el español se sigue pudiendo editar.
 */
export function pideSinIdiomas(search = "") {
  try {
    return new URLSearchParams(search).get("sin-idiomas") === "1";
  } catch {
    return false;
  }
}
