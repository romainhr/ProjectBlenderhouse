// Utilidades puras del portal del propietario (sin DOM; se prueban con `cd web && npm test`).
import { ZONA_PROPIEDAD, desdeIso, esIso } from "../../js/reserva-logica.js";

/** Largo en caracteres como lo cuenta char_length() de Postgres (puntos de código, no unidades UTF-16). */
export function largo(s) {
  return [...String(s ?? "")].length;
}

// Sólo estos esquemas pueden ir en un href armado con datos (nunca javascript:, data:, vbscript:…).
const HREF_SEGURO = /^(mailto:|tel:|https:\/\/|#|\.\.?\/)/i;

/** Devuelve el href si empieza con un esquema permitido; si no, "#". */
export function hrefSeguro(href) {
  const s = String(href ?? "").trim();
  return HREF_SEGURO.test(s) ? s : "#";
}

// Fechas «solas» (entrada, salida) en UTC para que no se corran de día; momentos (creada) en el huso de la propiedad.
const fDiaLargo = new Intl.DateTimeFormat("es-CL", { timeZone: "UTC", weekday: "short", day: "numeric", month: "short", year: "numeric" });
const fDiaMes = new Intl.DateTimeFormat("es-CL", { timeZone: "UTC", day: "numeric", month: "short" });
const fMomento = new Intl.DateTimeFormat("es-CL", {
  timeZone: ZONA_PROPIEDAD, day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
const fHora = new Intl.DateTimeFormat("es-CL", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });   // hora del dispositivo

export function formatearDia(isoDia) {
  return esIso(isoDia) ? fDiaLargo.format(desdeIso(isoDia)) : "—";
}

/** «12 oct – 15 oct 2026» (o con los dos años si cambia de año). */
export function rangoCorto(entrada, salida) {
  if (!esIso(entrada) || !esIso(salida)) return "—";
  const a0 = entrada.slice(0, 4), a1 = salida.slice(0, 4);
  if (a0 === a1) return `${fDiaMes.format(desdeIso(entrada))} – ${fDiaMes.format(desdeIso(salida))} ${a1}`;
  return `${fDiaMes.format(desdeIso(entrada))} ${a0} – ${fDiaMes.format(desdeIso(salida))} ${a1}`;
}

export function formatearMomento(marca) {
  if (marca == null || marca === "") return "—";
  const d = new Date(marca);
  return Number.isNaN(d.getTime()) ? "—" : fMomento.format(d);
}

export function horaCorta(d = new Date()) {
  return fHora.format(d);
}

/** Peso legible: «850 kB», «3,2 MB». */
export function peso(bytes) {
  const n = Number(bytes) || 0;
  if (n < 1000) return `${n} B`;
  if (n < 1e6) return `${Math.round(n / 1000)} kB`;
  return `${(n / 1e6).toLocaleString("es-CL", { maximumFractionDigits: 1 })} MB`;
}
