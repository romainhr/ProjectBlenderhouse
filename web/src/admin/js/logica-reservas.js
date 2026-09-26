// Lógica de la vista de reservas (sin DOM). Fechas como texto ISO "AAAA-MM-DD"; «hoy» en el huso de la propiedad
// (hoyIso de reserva-logica.js, el mismo criterio que public.hoy_loft()).
import { noches } from "../../js/reserva-logica.js";
import { largo } from "./util.js";

// 0001_reservas.sql: check (estado in ('pendiente', 'confirmada', 'rechazada', 'cancelada'))
export const ESTADOS = Object.freeze(["pendiente", "confirmada", "rechazada", "cancelada"]);
export const ACTIVOS = Object.freeze(["pendiente", "confirmada"]);        // los que bloquean noches (reservas_sin_solape)
export const ETIQUETA_ESTADO = Object.freeze({
  pendiente: "Pendiente", confirmada: "Confirmada", rechazada: "Rechazada", cancelada: "Cancelada",
});
export const PLURAL_ESTADO = Object.freeze({
  todas: "Todas", pendiente: "Pendientes", confirmada: "Confirmadas", rechazada: "Rechazadas", cancelada: "Canceladas",
});
export const PERIODOS = Object.freeze({ proximas: "Próximas y en curso", pasadas: "Pasadas", todas: "Todas las fechas" });

export const LIMITE_NOTA = 2000;          // 0003_gestion.sql: nota_interna text (<= 2000)

// Cambios de estado que ofrece el portal. La base sólo exige que el estado sea uno de los cuatro y que dos solicitudes
// activas no compartan noches; reabrir una rechazada o cancelada es donde puede aparecer el choque de fechas (23P01).
export const TRANSICIONES = Object.freeze({
  pendiente: Object.freeze(["confirmada", "rechazada"]),
  confirmada: Object.freeze(["cancelada"]),
  rechazada: Object.freeze(["confirmada", "pendiente"]),
  cancelada: Object.freeze(["confirmada", "pendiente"]),
});

export const ACCIONES = Object.freeze({
  confirmada: { texto: "Confirmar", clase: "primario", peligro: false,
    explicacion: "Las noches quedan ocupadas en el calendario público. Recuerda avisar al huésped por correo." },
  rechazada: { texto: "Rechazar", clase: "secundario", peligro: true,
    explicacion: "Las noches vuelven a quedar libres en el calendario público." },
  cancelada: { texto: "Cancelar reserva", clase: "secundario", peligro: true,
    explicacion: "La reserva confirmada se anula y las noches vuelven a quedar libres." },
  pendiente: { texto: "Volver a pendiente", clase: "secundario", peligro: false,
    explicacion: "La solicitud vuelve a bloquear sus noches mientras decides." },
});

export function accionesPermitidas(estado) {
  return TRANSICIONES[estado] || [];
}

/** Situación de la estadía respecto de hoy (la noche del día de salida no se ocupa). */
export function situacion(r, hoy) {
  if (r.salida < hoy) return "pasada";
  if (r.salida === hoy) return "sale_hoy";
  if (r.entrada <= hoy) return "en_curso";
  return "proxima";
}
export const ETIQUETA_SITUACION = Object.freeze({ proxima: "", en_curso: "En curso", sale_hoy: "Sale hoy", pasada: "Pasada" });

/** Próximas: las que todavía no terminan (incluye las en curso y la que sale hoy). Pasadas: salida antes de hoy. */
export function enPeriodo(r, periodo, hoy) {
  if (periodo === "proximas") return r.salida >= hoy;
  if (periodo === "pasadas") return r.salida < hoy;
  return true;
}

function porEntrada(a, b) {
  return a.entrada < b.entrada ? -1 : a.entrada > b.entrada ? 1 : String(a.creada).localeCompare(String(b.creada));
}

/** Filtra y ordena: las próximas de la más cercana a la más lejana; pasadas y todas, de la más reciente hacia atrás. */
export function filtrarReservas(lista, { estado = "todas", periodo = "proximas" } = {}, hoy) {
  const r = lista.filter((x) => enPeriodo(x, periodo, hoy) && (estado === "todas" || x.estado === estado));
  r.sort(porEntrada);
  if (periodo !== "proximas") r.reverse();
  return r;
}

/** Contadores por estado dentro del periodo elegido: { todas, pendiente, confirmada, rechazada, cancelada }. */
export function contarPorEstado(lista, periodo, hoy) {
  const c = { todas: 0, pendiente: 0, confirmada: 0, rechazada: 0, cancelada: 0 };
  for (const x of lista) {
    if (!enPeriodo(x, periodo, hoy)) continue;
    c.todas++;
    if (Object.prototype.hasOwnProperty.call(c, x.estado)) c[x.estado]++;
  }
  return c;
}

/** Pendientes que todavía no terminan: el número del aviso en la navegación. */
export function pendientesPorResolver(lista, hoy) {
  return lista.filter((x) => x.estado === "pendiente" && x.salida >= hoy).length;
}

export function nochesDe(r) {
  return noches(r.entrada, r.salida);
}

/** Valida la nota interna: se guarda sin espacios al final; vacía -> null. */
export function validarNota(texto) {
  const v = String(texto ?? "").replace(/\r\n?/g, "\n").replace(/\s+$/, "");
  if (largo(v) > LIMITE_NOTA) return { ok: false, error: "nota_larga" };
  return { ok: true, valor: v === "" ? null : v };
}

// Correo con la misma forma que exige la base (0001: email ~* '^[^@[:space:]]+@[^@[:space:]]+\.[a-z]{2,}$'), sin los
// caracteres que cambiarían el sentido de un enlace mailto (?, &, #, %, comillas, <, >, comas, punto y coma).
const RE_CORREO_ENLACE = /^[^@\s?&#%"'<>,;:\\/]+@[^@\s?&#%"'<>,;:\\/]+\.[a-z]{2,}$/i;

/** Enlace mailto para responder al huésped, o null si el correo no tiene una forma segura. */
export function enlaceCorreo(email, asunto = "") {
  const e = String(email ?? "").trim();
  if (!RE_CORREO_ENLACE.test(e)) return null;
  return asunto ? `mailto:${e}?subject=${encodeURIComponent(asunto)}` : `mailto:${e}`;
}

/** Enlace tel con sólo dígitos y un + inicial (0001: telefono ~ '^[0-9 +().-]{6,20}$'), o null. */
export function enlaceTelefono(telefono) {
  const t = String(telefono ?? "").trim();
  if (!t) return null;
  const mas = t.startsWith("+") ? "+" : "";
  const digitos = t.replace(/\D/g, "");
  if (digitos.length < 6 || digitos.length > 20) return null;
  return `tel:${mas}${digitos}`;
}

export function asuntoCorreo(r) {
  return `Tu solicitud de reserva en LOFT 2D2B (código ${r.codigo || "—"})`;
}

/** Reemplaza una fila por id (devuelve una lista nueva). */
export function reemplazar(lista, fila) {
  return lista.map((x) => (x.id === fila.id ? { ...x, ...fila } : x));
}
