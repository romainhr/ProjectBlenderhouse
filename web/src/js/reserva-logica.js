// Lógica de reservas sin DOM (se prueba con `cd web && npm test`). Fechas como texto ISO "AAAA-MM-DD" y
// aritmética en UTC, para que el huso horario del visitante no corra los días; «hoy» es el día en el huso de la
// propiedad, el mismo que usa la base (public.hoy_loft(), 0002_hoy_propiedad.sql). Un rango [entrada, salida) ocupa las
// noches desde la entrada hasta la noche anterior a la salida: la base de datos usa el mismo criterio (daterange '[)').

// Valores de EJEMPLO del sitio de prueba (no son tarifas reales). Deben coincidir con 0001_reservas.sql.
export const TARIFA = Object.freeze({
  noche: 58000,
  limpieza: 15000,
  minNoches: 2,
  maxNoches: 30,
  maxHuespedes: 4,
  anticipacionMaxDias: 365,
});

// Supuesto: la propiedad está en Chile continental (tarifas en CLP). Debe coincidir con public.hoy_loft().
export const ZONA_PROPIEDAD = "America/Santiago";

const DIA_MS = 86400000;
const RE_ISO = /^\d{4}-\d{2}-\d{2}$/;

export function esIso(s) {
  if (typeof s !== "string" || !RE_ISO.test(s)) return false;
  const d = desdeIso(s);
  return iso(d) === s;                                   // descarta 2026-02-30 y similares
}

export function desdeIso(s) {
  const [a, m, d] = s.split("-").map(Number);
  return new Date(Date.UTC(a, m - 1, d));
}

export function iso(d) {
  return d.toISOString().slice(0, 10);
}

const fHoy = new Intl.DateTimeFormat("en-CA", { timeZone: ZONA_PROPIEDAD, year: "numeric", month: "2-digit", day: "2-digit" });

/** El día de hoy en la propiedad (no el del visitante ni el UTC). */
export function hoyIso(ahora = new Date()) {
  return fHoy.format(ahora);                             // en-CA escribe AAAA-MM-DD
}

export function sumarDias(s, n) {
  return iso(new Date(desdeIso(s).getTime() + n * DIA_MS));
}

export function noches(entrada, salida) {
  return Math.round((desdeIso(salida) - desdeIso(entrada)) / DIA_MS);
}

/** ¿Se cruzan [a0, a1) y [b0, b1)? (compara texto ISO: el orden lexicográfico es el cronológico) */
export function solapa(a0, a1, b0, b1) {
  return a0 < b1 && b0 < a1;
}

/** La noche que empieza en `dia` está ocupada por algún rango. */
export function nocheOcupada(dia, ocupados) {
  return ocupados.some((r) => r.entrada <= dia && dia < r.salida);
}

/** Valida un rango de estadía -> { ok: true } o { ok: false, error } con el código del mensaje. */
export function validarRango(entrada, salida, ocupados, hoy = hoyIso()) {
  if (!esIso(entrada) || !esIso(salida)) return { ok: false, error: "fechas_requeridas" };
  if (entrada < hoy) return { ok: false, error: "fecha_pasada" };
  if (noches(hoy, entrada) > TARIFA.anticipacionMaxDias) return { ok: false, error: "fecha_lejana" };
  const n = noches(entrada, salida);
  if (n < TARIFA.minNoches) return { ok: false, error: "min_noches" };
  if (n > TARIFA.maxNoches) return { ok: false, error: "max_noches" };
  if (ocupados.some((r) => solapa(entrada, salida, r.entrada, r.salida))) return { ok: false, error: "fechas_ocupadas" };
  return { ok: true, noches: n };
}

/** Primer día ocupado después de `entrada`: la salida no puede pasar de ahí (se puede salir el día que otro entra). */
export function salidaMaxima(entrada, ocupados) {
  const siguientes = ocupados.filter((r) => r.entrada > entrada).map((r) => r.entrada).sort();
  const tope = sumarDias(entrada, TARIFA.maxNoches);
  return siguientes.length && siguientes[0] < tope ? siguientes[0] : tope;
}

export function total(n) {
  const alojamiento = n * TARIFA.noche;
  return { noches: n, alojamiento, limpieza: n > 0 ? TARIFA.limpieza : 0, total: n > 0 ? alojamiento + TARIFA.limpieza : 0 };
}

export function clp(monto) {
  return "CLP " + new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 }).format(monto);
}

/** Semanas del mes (lunes primero): [[null, "2026-10-01", ...], ...] */
export function grillaMes(anio, mes) {
  const primero = new Date(Date.UTC(anio, mes, 1));
  const dias = new Date(Date.UTC(anio, mes + 1, 0)).getUTCDate();
  const desfase = (primero.getUTCDay() + 6) % 7;         // 0 = lunes
  const celdas = Array(desfase).fill(null);
  for (let d = 1; d <= dias; d++) celdas.push(iso(new Date(Date.UTC(anio, mes, d))));
  while (celdas.length % 7) celdas.push(null);
  const semanas = [];
  for (let i = 0; i < celdas.length; i += 7) semanas.push(celdas.slice(i, i + 7));
  return semanas;
}

const RE_CORREO = /^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i;
const RE_FONO = /^[0-9 +().-]{6,20}$/;

/** Valida los datos del huésped con las mismas reglas que la base de datos -> { campo: código } */
export function validarDatos({ nombre = "", email = "", telefono = "", mensaje = "", huespedes = 0, acepta = false }) {
  const e = {};
  const n = nombre.trim();
  if (n.length < 2 || n.length > 80) e.nombre = "nombre";
  if (email.trim().length > 120 || !RE_CORREO.test(email.trim())) e.email = "email";
  if (telefono.trim() && !RE_FONO.test(telefono.trim())) e.telefono = "telefono";
  if (mensaje.length > 1000) e.mensaje = "mensaje";
  if (!Number.isInteger(huespedes) || huespedes < 1 || huespedes > TARIFA.maxHuespedes) e.huespedes = "huespedes";
  if (!acepta) e.acepta = "acepta";
  return e;
}

export const MENSAJES = Object.freeze({
  fechas_requeridas: "Elige la fecha de llegada y la de salida.",
  fecha_pasada: "La llegada no puede ser en el pasado.",
  fecha_lejana: "Por ahora se reciben solicitudes hasta un año adelante.",
  min_noches: `La estadía mínima es de ${TARIFA.minNoches} noches.`,
  max_noches: `La estadía máxima es de ${TARIFA.maxNoches} noches.`,
  fechas_ocupadas: "Esas fechas ya tienen una solicitud. Elige otras.",
  datos_invalidos: "Revisa los datos del formulario.",
  nombre: "Escribe tu nombre (2 a 80 caracteres).",
  email: "Escribe un correo válido.",
  telefono: "El teléfono sólo admite números, espacios y + ( ) - .",
  mensaje: "El mensaje admite hasta 1 000 caracteres.",
  huespedes: `Pueden alojar de 1 a ${TARIFA.maxHuespedes} personas.`,
  acepta: "Necesitamos tu consentimiento para responder la solicitud.",
  red: "No se pudo conectar con el servidor de reservas. Intenta de nuevo.",
  sin_configurar: "Las reservas todavía no están conectadas en este sitio.",
});

/** Código conocido a partir del error del servidor (PostgREST devuelve el texto de la excepción en `message`). */
export function codigoError(err) {
  const m = (err && (err.codigo || err.message)) || "";
  return Object.prototype.hasOwnProperty.call(MENSAJES, m) ? m : "red";
}
