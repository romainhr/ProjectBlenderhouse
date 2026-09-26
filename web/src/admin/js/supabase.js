// Cliente mínimo de Supabase sin librerías: Auth (/auth/v1), PostgREST (/rest/v1) y Storage (/storage/v1).
// No toca el DOM: fetch, almacén, reloj y temporizador se inyectan (en las pruebas son falsos).
//
// Cabeceras: apikey = clave PUBLICABLE del proyecto (la del build, nunca la de servicio) y, en las llamadas con usuario,
// Authorization: Bearer <access_token del propietario>. Así PostgREST y Storage aplican RLS con el rol authenticated
// y auth.uid() del propietario.
import { ErrorApi, errorDesdeRespuesta, esErrorDeSesion } from "./errores.js";
import { rutaCodificada } from "./logica-fotos.js";
import { borrarSesion, debeRefrescar, guardarSesion, leerSesion, msHastaRefresco, normalizarSesion } from "./sesion.js";

export const ESPERA_MS = 20000;              // supuesto: tiempo máximo de una llamada normal
export const ESPERA_SUBIDA_MS = 90000;       // supuesto: subir 5 MB por una red móvil lenta
export const REINTENTO_REFRESCO_MS = 30000;  // supuesto: si el refresco falla por red, reintentar en 30 s
export const CACHE_FOTOS_S = 31536000;       // las rutas de fotos son únicas y no se sobrescriben: caché de un año

export function crearCliente({
  url,
  clave,
  almacen,
  fetch: pedirHttp = (...a) => globalThis.fetch(...a),
  ahora = () => Date.now(),
  alPerderSesion = () => {},
  temporizador = { poner: (f, ms) => setTimeout(f, ms), quitar: (t) => clearTimeout(t) },
} = {}) {
  const base = String(url || "").replace(/\/+$/, "");
  let sesion = null;
  let refrescoEnCurso = null;
  let timer = null;

  function quitarTimer() {
    if (timer != null && temporizador) temporizador.quitar(timer);
    timer = null;
  }

  function programar(ms) {
    quitarTimer();
    if (!sesion || !temporizador) return;
    const espera = ms ?? msHastaRefresco(sesion, ahora());
    timer = temporizador.poner(() => {
      timer = null;
      refrescar().catch(() => {});
    }, espera);
  }

  function fijar(s) {
    sesion = s;
    guardarSesion(almacen, s);
    programar();
  }

  function perder(motivo) {
    const habia = sesion !== null;
    sesion = null;
    quitarTimer();
    borrarSesion(almacen);
    if (habia) alPerderSesion(motivo);
  }

  async function http(ruta, { metodo = "GET", cabeceras = {}, cuerpo, espera = ESPERA_MS, origen = "rest" } = {}) {
    const control = typeof AbortController === "function" ? new AbortController() : null;
    const t = control ? setTimeout(() => control.abort(), espera) : null;
    let r;
    try {
      r = await pedirHttp(base + ruta, {
        method: metodo, headers: cabeceras, body: cuerpo, signal: control ? control.signal : undefined,
        credentials: "omit", cache: "no-store", referrerPolicy: "no-referrer",
      });
    } catch (e) {
      const agotado = e && e.name === "AbortError";
      throw new ErrorApi({ codigo: agotado ? "tiempo_agotado" : "red", mensaje: agotado ? "tiempo_agotado" : "red", origen });
    } finally {
      if (t) clearTimeout(t);
    }
    const tipo = (r.headers && r.headers.get && r.headers.get("content-type")) || "";
    const texto = await r.text().catch(() => "");
    let datos = null;
    if (texto) {
      if (tipo.includes("json")) {
        try { datos = JSON.parse(texto); } catch { datos = texto; }
      } else {
        datos = texto;
      }
    }
    if (!r.ok) throw errorDesdeRespuesta(r.status, datos, origen);
    return datos;
  }

  const json = { "Content-Type": "application/json" };

  async function iniciarSesion(email, contrasena) {
    const datos = await http("/auth/v1/token?grant_type=password", {
      metodo: "POST", origen: "auth", cabeceras: { apikey: clave, ...json },
      cuerpo: JSON.stringify({ email: String(email ?? "").trim(), password: String(contrasena ?? "") }),
    });
    const s = normalizarSesion(datos, ahora());
    if (!s) throw new ErrorApi({ codigo: "respuesta_invalida", origen: "auth" });
    fijar(s);
    return s;
  }

  /** Canjea el refresh_token por una sesión nueva. Un solo refresco a la vez (el refresh_token se usa una vez). */
  function refrescar() {
    if (refrescoEnCurso) return refrescoEnCurso;
    const actual = sesion;
    if (!actual) return Promise.reject(new ErrorApi({ codigo: "sesion_vencida", estado: 401, origen: "auth" }));
    refrescoEnCurso = (async () => {
      try {
        const datos = await http("/auth/v1/token?grant_type=refresh_token", {
          metodo: "POST", origen: "auth", cabeceras: { apikey: clave, ...json },
          cuerpo: JSON.stringify({ refresh_token: actual.refresh_token }),
        });
        if (sesion !== actual) throw new ErrorApi({ codigo: "sesion_vencida", estado: 401, origen: "auth" });
        const s = normalizarSesion(datos, ahora(), { usuarioPrevio: actual.usuario });
        if (!s) throw new ErrorApi({ codigo: "respuesta_invalida", origen: "auth" });
        fijar(s);
        return s;
      } catch (e) {
        if (sesion !== actual) {                      // se cerró o cambió la sesión mientras tanto: no tocarla
          throw new ErrorApi({ codigo: "sesion_vencida", estado: 401, origen: "auth" });
        }
        const transitorio = e.codigo === "red" || e.codigo === "tiempo_agotado" || e.estado === 429 || e.estado >= 500;
        if (transitorio) {
          programar(REINTENTO_REFRESCO_MS);           // se conserva la sesión y se vuelve a intentar
          throw e;
        }
        perder("sesion_vencida");                     // refresh_token rechazado (400/401/403): volver al login
        throw new ErrorApi({ codigo: "sesion_vencida", estado: 401, origen: "auth" });
      } finally {
        refrescoEnCurso = null;
      }
    })();
    return refrescoEnCurso;
  }

  /** Llamada con el token del propietario: refresca si está por vencer y, ante un 401, refresca y reintenta una vez. */
  async function conSesion(ruta, opciones, reintentar = true) {
    if (!sesion) {
      alPerderSesion("sesion_vencida");
      throw new ErrorApi({ codigo: "sesion_vencida", estado: 401 });
    }
    if (debeRefrescar(sesion, ahora())) await refrescar();
    const cabeceras = { ...opciones.cabeceras, apikey: clave, Authorization: `Bearer ${sesion.access_token}` };
    try {
      return await http(ruta, { ...opciones, cabeceras });
    } catch (e) {
      if (!esErrorDeSesion(e)) throw e;
      if (reintentar) {
        await refrescar();
        return conSesion(ruta, opciones, false);
      }
      perder("sesion_vencida");
      throw new ErrorApi({ codigo: "sesion_vencida", estado: 401, origen: e.origen });
    }
  }

  /** PostgREST: ruta relativa a /rest/v1 (p. ej. "/reservas?select=*"). */
  function rest(ruta, { metodo = "GET", cuerpo, prefer } = {}) {
    const cabeceras = { Accept: "application/json" };
    if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
    if (prefer) cabeceras.Prefer = prefer;
    return conSesion(`/rest/v1${ruta}`, {
      metodo, cabeceras, cuerpo: cuerpo === undefined ? undefined : JSON.stringify(cuerpo), origen: "rest",
    });
  }

  function rpc(nombre, args = {}) {
    return rest(`/rpc/${encodeURIComponent(nombre)}`, { metodo: "POST", cuerpo: args });
  }

  /**
   * Storage: sube un objeto con POST /storage/v1/object/{bucket}/{ruta}. El cuerpo va como FormData (campo
   * «cacheControl» y el archivo), igual que hace supabase-js con un Blob en el navegador; x-upsert decide si puede
   * sobrescribir (por defecto no: las rutas son nuevas y un choque se reintenta con otra).
   */
  function subirObjeto(bucket, ruta, blob, { sobrescribir = false, cacheSegundos = CACHE_FOTOS_S } = {}) {
    const fd = new FormData();
    fd.append("cacheControl", String(cacheSegundos));
    fd.append("", blob, String(ruta).split("/").pop());
    return conSesion(`/storage/v1/object/${encodeURIComponent(bucket)}/${rutaCodificada(ruta)}`, {
      metodo: "POST", cabeceras: { "x-upsert": sobrescribir ? "true" : "false" }, cuerpo: fd, origen: "storage",
      espera: ESPERA_SUBIDA_MS,
    });
  }

  /** Storage: borra objetos con DELETE /storage/v1/object/{bucket} y { prefixes: [...] } (lo que usa supabase-js). */
  function borrarObjetos(bucket, rutas) {
    return conSesion(`/storage/v1/object/${encodeURIComponent(bucket)}`, {
      metodo: "DELETE", cabeceras: { ...json }, cuerpo: JSON.stringify({ prefixes: rutas }), origen: "storage",
    });
  }

  function urlPublica(bucket, ruta) {
    return `${base}/storage/v1/object/public/${encodeURIComponent(bucket)}/${rutaCodificada(ruta)}`;
  }

  /** Cierra la sesión: primero borra la local (aunque falle la red) y luego avisa a Auth para revocar el token. */
  async function cerrarSesion() {
    const s = sesion;
    sesion = null;
    quitarTimer();
    borrarSesion(almacen);
    if (!s) return;
    try {
      await http("/auth/v1/logout", {
        metodo: "POST", origen: "auth", cabeceras: { apikey: clave, Authorization: `Bearer ${s.access_token}` },
      });
    } catch {
      /* el token local ya no existe; si Auth no respondió, el access_token vence solo */
    }
  }

  /** Recupera la sesión guardada en esta pestaña (si es del modo real) y la refresca si está por vencer. */
  async function restaurar() {
    const s = leerSesion(almacen);
    if (!s || s.modo !== "real") return null;
    sesion = s;
    if (debeRefrescar(s, ahora())) {
      try {
        await refrescar();
      } catch {
        return sesion;                                 // null si se perdió; la misma si sólo falló la red
      }
    } else {
      programar();
    }
    return sesion;
  }

  return {
    iniciarSesion, cerrarSesion, restaurar, refrescar, rest, rpc, subirObjeto, borrarObjetos, urlPublica,
    sesion: () => sesion,
  };
}
