// Errores de Supabase (Auth, PostgREST, Storage) convertidos en mensajes claros para el propietario. Sin DOM.
//
// Formas de cuerpo que se esperan (según la documentación pública de cada servicio; ver el informe si alguna no se
// pudo confirmar contra el proyecto real):
//   PostgREST: { code: "23P01", message, details, hint }       (code = SQLSTATE de Postgres o PGRSTxxx)
//   Auth:      { code, error_code: "invalid_credentials", msg }  (versiones nuevas)
//              { error: "invalid_grant", error_description }    (versiones antiguas)
//   Storage:   { statusCode: "409", error: "Duplicate", message }

export class ErrorApi extends Error {
  constructor({ estado = 0, codigo = "", mensaje = "", detalle = "", origen = "" } = {}) {
    super(mensaje || codigo || (estado ? `HTTP ${estado}` : "error"));
    this.name = "ErrorApi";
    this.estado = estado;
    this.codigo = codigo;
    this.detalle = detalle;
    this.origen = origen;
  }
}

/** Arma un ErrorApi a partir del estado HTTP y del cuerpo (ya leído) de una respuesta con error. */
export function errorDesdeRespuesta(estado, cuerpo, origen = "rest") {
  const c = cuerpo && typeof cuerpo === "object" ? cuerpo : {};
  let codigo = "", mensaje = "", detalle = "";
  if (origen === "storage") {
    const real = Number(c.statusCode);
    if (Number.isInteger(real) && real >= 400 && real < 600) estado = real;   // algunas versiones responden 400 y
    codigo = String(c.error || c.code || "");                                  // ponen el estado real en el cuerpo
    mensaje = String(c.message || "");
  } else if (origen === "auth") {
    codigo = String(c.error_code || c.error || "");
    mensaje = String(c.msg || c.error_description || c.message || "");
  } else {
    codigo = String(c.code || "");
    mensaje = String(c.message || "");
    detalle = String(c.details || "");
  }
  if (!mensaje && typeof cuerpo === "string") mensaje = cuerpo.slice(0, 200);
  return new ErrorApi({ estado, codigo, mensaje, detalle, origen });
}

/** ¿El error indica un token vencido o inválido? (entonces se intenta un refresco y se reintenta una vez) */
export function esErrorDeSesion(err) {
  if (!err || err.codigo === "red") return false;
  if (err.estado === 401) return true;
  if (["PGRST301", "PGRST303", "bad_jwt"].includes(err.codigo)) return true;
  return /jwt expired|exp" claim|exp claim|invalid jwt|jwt malformed/i.test(err.message || "");
}

export const MENSAJES = Object.freeze({
  red: "No se pudo conectar con Supabase. Revisa la conexión e intenta de nuevo.",
  tiempo_agotado: "Supabase tardó demasiado en responder. Intenta de nuevo.",
  sesion_vencida: "Tu sesión venció. Ingresa de nuevo.",
  credenciales: "Correo o contraseña incorrectos.",
  datos_login: "Escribe el correo y la contraseña.",
  correo_sin_confirmar: "El correo de esta cuenta no está confirmado. Confírmalo en el panel de Supabase (Authentication → Users).",
  demasiados_intentos: "Demasiados intentos seguidos. Espera unos minutos y vuelve a probar.",
  fechas_chocan: "Esas fechas chocan con otra solicitud pendiente o confirmada. Rechaza o cancela esa otra antes de confirmar esta.",
  regla_base: "La base rechazó el cambio porque no cumple sus reglas (largo, formato o estado permitido).",
  duplicado: "Ya existe un registro con ese valor.",
  sin_permiso: "Tu cuenta no tiene permiso para hacer esto. ¿Está registrada como propietario?",
  sin_filas: "No se encontró el registro (quizá ya se borró) o tu cuenta no tiene permiso para cambiarlo. Actualiza la lista.",
  falta_migracion: "La base todavía no tiene lo que el portal necesita (tabla, columna o función). Falta aplicar la migración 0003_gestion.sql en Supabase.",
  archivo_duplicado: "Ya existe un archivo con ese nombre en Storage.",
  archivo_grande: "La imagen supera el tamaño que acepta el bucket de fotos.",
  archivo_tipo: "Storage no acepta ese tipo de archivo (sólo JPEG, PNG o WebP).",
  objeto_no_borrado: "Storage no borró el archivo (no existe o tu cuenta no tiene permiso).",
  id_invalido: "Identificador inválido.",
  respuesta_invalida: "Supabase respondió algo inesperado.",
  sin_configurar: "El portal no está conectado a Supabase en este sitio (falta la configuración del build).",
  desconocido: "Supabase respondió con un error.",
});

/** Código de MENSAJES que corresponde al error. */
export function codigoConocido(err) {
  if (!err) return "desconocido";
  if (Object.prototype.hasOwnProperty.call(MENSAJES, err.codigo) && err.codigo !== "desconocido") return err.codigo;
  const c = String(err.codigo || ""), m = String(err.message || "");
  if (err.origen === "auth") {
    if (c === "invalid_credentials" || c === "invalid_grant") return "credenciales";
    if (c === "email_not_confirmed") return "correo_sin_confirmar";
    if (err.estado === 429 || /rate_limit/.test(c)) return "demasiados_intentos";
    if (c === "validation_failed") return "datos_login";
  }
  if (err.origen === "storage") {
    if (err.estado === 409 || /duplicate|already exists/i.test(c + " " + m)) return "archivo_duplicado";
    if (err.estado === 413 || /too ?large|exceeded the maximum/i.test(c + " " + m)) return "archivo_grande";
    if (err.estado === 415 || /mime/i.test(c + " " + m)) return "archivo_tipo";
    if (/bucket not found/i.test(c + " " + m)) return "falta_migracion";
    if (err.estado === 403 || /row-level security|unauthorized/i.test(c + " " + m)) return "sin_permiso";
  }
  switch (c) {
    case "23P01": return "fechas_chocan";                 // exclusion_violation (reservas_sin_solape)
    case "23514": return "regla_base";                    // check_violation
    case "23505": return "duplicado";                     // unique_violation
    case "42501": return "sin_permiso";                   // insufficient_privilege (grants o RLS)
    case "42703": case "42P01": case "42883":             // columna, tabla o función inexistente (Postgres)
    case "PGRST202": case "PGRST204": case "PGRST205":    // función, columna o tabla fuera del caché de PostgREST
      return "falta_migracion";
    default: break;
  }
  if (err.estado === 403) return "sin_permiso";
  return "desconocido";
}

/** Mensaje para mostrar (con textContent). Para errores no reconocidos agrega el estado y el texto del servidor. */
export function mensajeError(err) {
  const c = codigoConocido(err);
  if (c !== "desconocido") return MENSAJES[c];
  const partes = [MENSAJES.desconocido];
  if (err && err.estado) partes.push(`(HTTP ${err.estado})`);
  const m = err && typeof err.message === "string" ? err.message.slice(0, 200) : "";
  if (m && !/^HTTP \d+$/.test(m)) partes.push(`Detalle: ${m}`);
  return partes.join(" ");
}
