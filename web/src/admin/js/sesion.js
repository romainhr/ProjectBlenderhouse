// Sesión del propietario: forma, vencimiento y guardado en sessionStorage (no localStorage: se borra al cerrar la
// pestaña). Sin DOM: el almacén se inyecta (sessionStorage en el navegador, un objeto falso en las pruebas).

export const CLAVE_ALMACEN = "depto2d2b-admin-sesion";
// Supuesto: refrescar 60 s antes de vencer. El access_token de Supabase dura 3600 s por defecto (JWT expiry del
// proyecto); si el proyecto usa otro valor, el cálculo sale de expires_in igual.
export const MARGEN_REFRESCO_S = 60;
const DURACION_POR_DEFECTO_S = 3600;             // supuesto: sólo si la respuesta no trae expires_in ni expires_at

/**
 * Normaliza la respuesta de /auth/v1/token a lo mínimo que el portal guarda (sin metadatos del usuario).
 * El vencimiento se calcula con expires_in y el reloj local, para no depender de que el reloj del dispositivo
 * coincida con el del servidor; expires_at (segundos Unix del servidor) sólo se usa si falta expires_in.
 */
export function normalizarSesion(r, ahoraMs, { usuarioPrevio = null, modo = "real" } = {}) {
  if (!r || typeof r.access_token !== "string" || !r.access_token || typeof r.refresh_token !== "string" || !r.refresh_token) {
    return null;
  }
  const ahoraS = Math.floor(ahoraMs / 1000);
  const dur = Number(r.expires_in);
  const exp = Number(r.expires_at);
  let expira;
  if (Number.isFinite(dur) && dur > 0) expira = ahoraS + dur;
  else if (Number.isFinite(exp) && exp > 0) expira = exp;
  else expira = ahoraS + DURACION_POR_DEFECTO_S;
  const u = r.user && typeof r.user === "object" ? r.user : usuarioPrevio || {};
  return {
    modo,
    access_token: r.access_token,
    refresh_token: r.refresh_token,
    expires_at: expira,
    usuario: { id: String(u.id || ""), email: String(u.email || "") },
  };
}

export function esSesion(s) {
  return Boolean(s && typeof s === "object" && typeof s.access_token === "string" && s.access_token &&
    typeof s.refresh_token === "string" && s.refresh_token && Number.isFinite(s.expires_at) &&
    s.usuario && typeof s.usuario === "object" && typeof s.modo === "string");
}

export function segundosRestantes(sesion, ahoraMs) {
  return sesion.expires_at - ahoraMs / 1000;
}

/** ¿Hay que refrescar ya? (vencida o a menos de `margen` segundos de vencer) */
export function debeRefrescar(sesion, ahoraMs, margen = MARGEN_REFRESCO_S) {
  return Boolean(sesion) && segundosRestantes(sesion, ahoraMs) <= margen;
}

/** Milisegundos hasta el refresco programado (0 si ya toca). */
export function msHastaRefresco(sesion, ahoraMs, margen = MARGEN_REFRESCO_S) {
  return Math.max(0, Math.round((sesion.expires_at - margen) * 1000 - ahoraMs));
}

export function leerSesion(almacen) {
  try {
    const s = JSON.parse(almacen.getItem(CLAVE_ALMACEN) || "null");
    return esSesion(s) ? s : null;
  } catch {
    return null;
  }
}

export function guardarSesion(almacen, sesion) {
  try {
    almacen.setItem(CLAVE_ALMACEN, JSON.stringify(sesion));
  } catch {
    /* almacén lleno o bloqueado: la sesión sigue en memoria mientras la pestaña esté abierta */
  }
}

/** Cerrar sesión borra el sessionStorage completo del sitio (el sitio público no guarda nada ahí). */
export function borrarSesion(almacen) {
  try {
    almacen.removeItem(CLAVE_ALMACEN);
    almacen.clear();
  } catch {
    /* sin almacén disponible */
  }
}
