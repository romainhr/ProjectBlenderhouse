// Lógica de reservas sin DOM (se prueba con `cd web && npm test`). Fechas como texto ISO "AAAA-MM-DD" y
// aritmética en UTC, para que el huso horario del visitante no corra los días; «hoy» es el día en el huso de la
// propiedad, el mismo que usa la base (public.hoy_propiedad(), 0004_renombrar_hoy.sql). Un rango [entrada, salida) ocupa las
// noches desde la entrada hasta la noche anterior a la salida: la base de datos usa el mismo criterio (daterange '[)').

// Valores de EJEMPLO del sitio de prueba (no son tarifas reales). Deben coincidir con 0001_reservas.sql.
// noche y limpieza son sólo los valores POR DEFECTO: el total se calcula con tarifaVigente(), que fijarTarifas()
// cambia por las que editó el propietario (public.contenido, claves tarifa.*, que lee contenido-publico.js).
export const TARIFA = Object.freeze({
  noche: 58000,
  limpieza: 15000,
  minNoches: 2,
  maxNoches: 30,
  maxHuespedes: 4,
  anticipacionMaxDias: 365,
});

// Rango de un precio en CLP: el del CHECK contenido_precio_entero de 0003_gestion.sql (entero de 0 a 10 000 000).
export const PRECIO_MAX = 10_000_000;

let vigente = Object.freeze({ noche: TARIFA.noche, limpieza: TARIFA.limpieza });

/** Tarifas con que se calcula el total: { noche, limpieza } en CLP (congelado), las de TARIFA o las fijadas.
 *  Todo texto con un precio se arma al pintar con esto; los mensajes (CODIGOS) no llevan precios. */
export function tarifaVigente() {
  return vigente;
}

/** Fija noche y limpieza: enteros de 0 a PRECIO_MAX y la noche mayor que 0. Si alguna no es válida no cambia nada
 *  y devuelve false. fijarTarifas(TARIFA) vuelve a los valores de ejemplo. */
export function fijarTarifas(t) {
  const noche = t?.noche, limpieza = t?.limpieza;
  const entero = (n) => Number.isSafeInteger(n) && n >= 0 && n <= PRECIO_MAX;
  if (!entero(noche) || noche === 0 || !entero(limpieza)) return false;
  vigente = Object.freeze({ noche, limpieza });
  return true;
}

// Supuesto: la propiedad está en Chile continental (tarifas en CLP). Debe coincidir con public.hoy_propiedad().
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

/** Total de `n` noches con la tarifa `t` (por defecto, la vigente). */
export function total(n, t = vigente) {
  const alojamiento = n * t.noche;
  return { noches: n, alojamiento, limpieza: n > 0 ? t.limpieza : 0, total: n > 0 ? alojamiento + t.limpieza : 0 };
}

const formatosClp = new Map();

/** Monto en pesos chilenos: «CLP» y el número entero con el separador de miles de `locale` (es-CL por defecto, el que
 *  usa el portal): es-CL «CLP 189.000», en-US «CLP 189,000», fr-FR «CLP 189 000» (espacio fino de Intl). La moneda es
 *  siempre CLP: el idioma sólo cambia cómo se escribe el número. */
export function clp(monto, locale = "es-CL") {
  if (!formatosClp.has(locale)) formatosClp.set(locale, new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }));
  return "CLP " + formatosClp.get(locale).format(monto);
}

const LUNES = Date.UTC(2024, 0, 1);                      // el 1 de enero de 2024 fue lunes

/** Los siete días de la semana, de lunes a domingo, con Intl en `locale` (weekday: "long", "short" o "narrow"). */
export function nombresDias(locale, formato = "long") {
  const f = new Intl.DateTimeFormat(locale, { weekday: formato, timeZone: "UTC" });
  return Array.from({ length: 7 }, (_, i) => f.format(new Date(LUNES + i * DIA_MS)));
}

/** Abreviaturas de la cabecera del calendario desde un texto «lu,ma,mi,ju,vi,sá,do» (el de js.reserva.cal.dias_cortos).
 *  Si no trae siete abreviaturas no vacías, usa las cortas de Intl en `locale`. */
export function diasCortos(texto, locale) {
  const dias = typeof texto === "string" ? texto.split(",").map((d) => d.trim()) : [];
  return dias.length === 7 && dias.every(Boolean) ? dias : nombresDias(locale, "short");
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

export const CELDA_MIN = 48;          // px: área táctil mínima de un día (DESIGN-v4, WCAG 2.5.5)
export const SEPARACION_MESES = 32;   // px: column-gap de #meses (sitio.css)

/** Meses que caben lado a lado en `ancho` px: 2 si caben dos semanas de 7 × CELDA_MIN más la separación, si no 1. */
export function mesesPorPagina(ancho) {
  return ancho >= 2 * 7 * CELDA_MIN + SEPARACION_MESES ? 2 : 1;
}

/** ¿Se puede avanzar un mes? La última página alcanzable es la que contiene `hasta` (ISO). `mes` va de 0 a 11. */
export function hayMesSiguiente(anio, mes, porPagina, hasta) {
  return Date.UTC(anio, mes + porPagina, 1) <= desdeIso(hasta).getTime();
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

// Códigos de los mensajes para el visitante: los devuelven validarRango, validarDatos y el servidor (PostgREST pone el
// texto de la excepción en `message`), más «red» y «sin_configurar» de reservas-api.js. Sus textos están en
// web/src/i18n/{es,en,fr}.json como js.reserva.<código>; este módulo no los carga (no depende de i18n.js ni de fetch:
// lo importan también el portal y las pruebas en Node), así que quien muestra un mensaje pasa su traductor a
// textoMensaje(). Los textos no llevan precios, así no quedan desfasados si el propietario cambia las tarifas.
export const CODIGOS = Object.freeze([
  "fechas_requeridas", "fecha_pasada", "fecha_lejana", "min_noches", "max_noches", "fechas_ocupadas", "datos_invalidos",
  "nombre", "email", "telefono", "mensaje", "huespedes", "acepta", "red", "sin_configurar",
]);
export const PREFIJO_MENSAJES = "js.reserva.";
// Las cifras de los mensajes salen de TARIFA, para que el texto no se separe de la regla ({minNoches} en el JSON).
export const VARIABLES_MENSAJES = Object.freeze({
  minNoches: TARIFA.minNoches,
  maxNoches: TARIFA.maxNoches,
  maxHuespedes: TARIFA.maxHuespedes,
});

/** ¿Es `c` uno de CODIGOS? */
export function esCodigo(c) {
  return typeof c === "string" && CODIGOS.includes(c);
}

/** Texto del mensaje `codigo` con el traductor `t` (el t de i18n.js o uno de prueba): t("js.reserva.<código>",
 *  VARIABLES_MENSAJES). Sin traductor devuelve la clave, igual que t() cuando falta un texto. */
export function textoMensaje(codigo, t) {
  const clave = PREFIJO_MENSAJES + String(codigo);
  return typeof t === "function" ? t(clave, VARIABLES_MENSAJES) : clave;
}

/** Código conocido a partir del error del servidor (PostgREST devuelve el texto de la excepción en `message`). */
export function codigoError(err) {
  const m = (err && (err.codigo || err.message)) || "";
  return esCodigo(m) ? m : "red";
}
