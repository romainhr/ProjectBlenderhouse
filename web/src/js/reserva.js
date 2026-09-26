// Página de reserva: calendario de disponibilidad, datos del huésped, resumen y envío de la solicitud.
import {
  MENSAJES, TARIFA, clp, codigoError, esIso, fijarTarifas, grillaMes, hayMesSiguiente, hoyIso, mesesPorPagina,
  nocheOcupada, noches, salidaMaxima, sumarDias, tarifaVigente, total, validarDatos, validarRango,
} from "./reserva-logica.js";
import { disponibilidad, simulado, solicitar } from "./reservas-api.js";
import { tarifas } from "./contenido-publico.js";

const $ = (s) => document.querySelector(s);
const HOY = hoyIso();
const LLEGADA_MAX = sumarDias(HOY, TARIFA.anticipacionMaxDias);   // la base rechaza llegadas más lejanas (fecha_lejana)
const HASTA = sumarDias(LLEGADA_MAX, TARIFA.maxNoches);          // última salida posible
const DIAS = ["lu", "ma", "mi", "ju", "vi", "sá", "do"];
const DIAS_LARGOS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
const fMes = new Intl.DateTimeFormat("es-CL", { month: "long", year: "numeric", timeZone: "UTC" });
const fDia = new Intl.DateTimeFormat("es-CL", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
const fLargo = new Intl.DateTimeFormat("es-CL", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const aFecha = (s) => new Date(s + "T00:00:00Z");
/** Ancho disponible para los meses: el de contenido de #calendario. No se mide #meses: con un solo mes, el CSS lo
 *  angosta a 392 px (.cal-cuerpo:has(.mes:only-child)) y la cuenta se quedaba en 1 aunque la ventana creciera. */
function anchoMeses() {
  const c = $("#calendario"), s = getComputedStyle(c);
  return c.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
}

const estado = {
  ocupados: [],
  entrada: null,
  salida: null,
  huespedes: 2,
  mes: (() => { const d = aFecha(HOY); return { anio: d.getUTCFullYear(), mes: d.getUTCMonth() }; })(),
  porPagina: mesesPorPagina(anchoMeses()),   // 1 o 2 según el ancho del contenedor, no del viewport
  enviando: false,
};

// ---------------------------------------------------------------- datos iniciales (parámetros de la portada)
const q = new URLSearchParams(location.search);
const h = Number(q.get("huespedes"));
if (Number.isInteger(h) && h >= 1 && h <= TARIFA.maxHuespedes) estado.huespedes = h;
const qEntrada = q.get("entrada") || "", qSalida = q.get("salida") || "";
if (esIso(qEntrada) && qEntrada >= HOY && qEntrada <= LLEGADA_MAX) {
  estado.entrada = qEntrada;
  const d = aFecha(qEntrada);
  estado.mes = { anio: d.getUTCFullYear(), mes: d.getUTCMonth() };
  if (esIso(qSalida)) estado.salida = qSalida;         // se valida contra la disponibilidad al cargarla
}
if (simulado) $("#aviso-sim").hidden = false;

// ---------------------------------------------------------------- calendario
/** Llegada posible: noche libre, dentro del año y con al menos una salida válida después. */
function llegadaPosible(d) {
  return d >= HOY && d <= LLEGADA_MAX && !nocheOcupada(d, estado.ocupados) &&
    salidaMaxima(d, estado.ocupados) >= sumarDias(d, TARIFA.minNoches);
}
/** Salida posible para la llegada elegida (se puede salir el día en que otro llega). */
function salidaPosible(d) {
  return Boolean(estado.entrada && !estado.salida) && d >= sumarDias(estado.entrada, TARIFA.minNoches) &&
    d <= salidaMaxima(estado.entrada, estado.ocupados);
}

function motivo(d) {
  if (d < HOY) return "ya pasó";
  if (nocheOcupada(d, estado.ocupados)) return "ocupado";
  if (d > LLEGADA_MAX) return "más de un año adelante";
  if (estado.entrada && !estado.salida && d > estado.entrada && d < sumarDias(estado.entrada, TARIFA.minNoches)) {
    return `mínimo ${TARIFA.minNoches} noches`;
  }
  return `no quedan ${TARIFA.minNoches} noches libres desde aquí`;
}

function pintar() {
  const previo = document.activeElement, foco = previo?.dataset?.dia;
  const cont = $("#meses");
  cont.replaceChildren();
  cont.style.setProperty("--meses", String(estado.porPagina));
  for (let k = 0; k < estado.porPagina; k++) {
    const fecha = new Date(Date.UTC(estado.mes.anio, estado.mes.mes + k, 1));
    const anio = fecha.getUTCFullYear(), mes = fecha.getUTCMonth();
    const bloque = document.createElement("div");
    bloque.className = "mes";
    const titulo = document.createElement("h3");
    titulo.textContent = fMes.format(fecha);
    const tabla = document.createElement("table");
    tabla.setAttribute("aria-label", fMes.format(fecha));
    const cab = tabla.createTHead().insertRow();
    DIAS.forEach((d, i) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.abbr = DIAS_LARGOS[i];
      th.textContent = d;
      cab.append(th);
    });
    const cuerpo = tabla.createTBody();
    for (const semana of grillaMes(anio, mes)) {
      const fila = cuerpo.insertRow();
      for (const dia of semana) {
        const td = fila.insertCell();
        if (!dia) continue;
        const b = document.createElement("button");
        b.type = "button";
        b.className = "dia";
        b.dataset.dia = dia;
        b.textContent = String(Number(dia.slice(8)));
        const ocupada = nocheOcupada(dia, estado.ocupados);
        const habilitado = salidaPosible(dia) || llegadaPosible(dia);
        if (dia < HOY || dia > HASTA) b.classList.add("pasado");
        else if (ocupada) b.classList.add("ocupado");
        b.disabled = !habilitado || estado.enviando;
        const esEntrada = dia === estado.entrada, esSalida = dia === estado.salida;
        const enRango = estado.entrada && estado.salida && dia > estado.entrada && dia < estado.salida;
        if (esEntrada || esSalida) b.classList.add("extremo");
        if (esEntrada) b.classList.add("llegada");
        if (esSalida) b.classList.add("salida");
        if (enRango) b.classList.add("en-rango");
        if (dia === HOY) { b.classList.add("hoy"); b.setAttribute("aria-current", "date"); }
        if (esEntrada || esSalida) b.setAttribute("aria-pressed", "true");
        const extra = esEntrada ? ", llegada elegida" : esSalida ? ", salida elegida" : enRango ? ", dentro de tu estadía"
          : !habilitado ? `, no disponible: ${motivo(dia)}` : "";
        b.setAttribute("aria-label", fLargo.format(aFecha(dia)) + extra);
        td.append(b);
      }
    }
    bloque.append(titulo, tabla);
    cont.append(bloque);
  }
  const inicio = new Date(Date.UTC(estado.mes.anio, estado.mes.mes, 1));
  const hoy = aFecha(HOY);
  $("#mes-ant").disabled = estado.enviando || inicio <= new Date(Date.UTC(hoy.getUTCFullYear(), hoy.getUTCMonth(), 1));
  // la última página alcanzable es la que contiene HASTA (con uno o dos meses por página)
  $("#mes-sig").disabled = estado.enviando || !hayMesSiguiente(estado.mes.anio, estado.mes.mes, estado.porPagina, HASTA);
  $("#rango-texto").textContent = !estado.entrada ? "Elige la llegada"
    : !estado.salida ? `Llegada ${fDia.format(aFecha(estado.entrada))} · elige la salida`
      : `${fDia.format(aFecha(estado.entrada))} → ${fDia.format(aFecha(estado.salida))} · ` +
        `${noches(estado.entrada, estado.salida)} noches`;
  // conservar el foco (ESPEC-v4 §8.3). replaceChildren() lo deja en el body, así que se decide con lo que había antes:
  // el mismo día si sigue habilitado; si no (una salida que no sirve de llegada queda deshabilitada), #rango-texto, que
  // anuncia el rango; y si una flecha llegó al tope, la otra flecha.
  const mismo = foco && document.querySelector(`button.dia[data-dia="${foco}"]`);
  if (mismo && !mismo.disabled) mismo.focus();
  else if (foco) $("#rango-texto").focus();
  else if (previo?.disabled && previo.closest(".cal-nav")) {
    (["#mes-sig", "#mes-ant"].map((s) => $(s)).find((b) => !b.disabled) || $("#rango-texto")).focus();
  }
  resumen();
}

$("#meses").addEventListener("click", (ev) => {
  if (estado.enviando) return;
  const b = ev.target.closest("button.dia");
  if (!b || b.disabled) return;
  const dia = b.dataset.dia;
  if (salidaPosible(dia)) {
    estado.salida = dia;
  } else {
    estado.entrada = dia;
    estado.salida = null;
  }
  $("#cal-error").hidden = true;
  b.focus();
  pintar();
});
function moverMes(delta) {
  if (estado.enviando) return;
  const d = new Date(Date.UTC(estado.mes.anio, estado.mes.mes + delta, 1));
  estado.mes = { anio: d.getUTCFullYear(), mes: d.getUTCMonth() };
  pintar();
}
$("#mes-ant").addEventListener("click", () => moverMes(-1));
$("#mes-sig").addEventListener("click", () => moverMes(1));
// meses por página según el ancho real del calendario (con el resumen al lado, dos meses caben desde unos 1.230 px)
if ("ResizeObserver" in window) {
  new ResizeObserver(() => {
    const n = mesesPorPagina(anchoMeses());
    if (n !== estado.porPagina) { estado.porPagina = n; pintar(); }
  }).observe($("#calendario"));
}

// ---------------------------------------------------------------- huéspedes y resumen
function huespedes(n) {
  if (estado.enviando) return;
  estado.huespedes = Math.min(TARIFA.maxHuespedes, Math.max(1, n));
  $("#huespedes").textContent = String(estado.huespedes);
  $("#menos").disabled = estado.huespedes <= 1;
  $("#mas").disabled = estado.huespedes >= TARIFA.maxHuespedes;
  if (document.activeElement?.disabled) (estado.huespedes <= 1 ? $("#mas") : $("#menos")).focus();
}
$("#menos").addEventListener("click", () => huespedes(estado.huespedes - 1));
$("#mas").addEventListener("click", () => huespedes(estado.huespedes + 1));

function rangoActual() {
  return estado.entrada && estado.salida ? validarRango(estado.entrada, estado.salida, estado.ocupados, HOY) : { ok: false };
}

function resumen() {
  const v = rangoActual();
  const t = total(v.ok ? v.noches : 0);
  $("#s-entrada").textContent = estado.entrada ? fDia.format(aFecha(estado.entrada)) : "—";
  $("#s-salida").textContent = estado.salida ? fDia.format(aFecha(estado.salida)) : "—";
  $("#s-noches-txt").textContent = v.ok ? `${v.noches} noches × ${clp(tarifaVigente().noche)}` : "Noches";
  $("#s-alojamiento").textContent = v.ok ? clp(t.alojamiento) : "—";
  $("#s-limpieza").textContent = v.ok ? clp(t.limpieza) : "—";
  $("#s-total").textContent = v.ok ? clp(t.total) : "—";
  $("#m-total").textContent = v.ok ? clp(t.total) : "Elige tus fechas";
  $("#m-total").classList.toggle("vacio", !v.ok);
  $("#m-noches").textContent = v.ok ? `${v.noches} noches · total de ejemplo` : "sin cobro en línea";
  if (estado.entrada && estado.salida && !v.ok && v.error) mostrarError($("#cal-error"), MENSAJES[v.error]);
  // sin fechas válidas los botones siguen activos (aria-disabled): al tocarlos, el envío explica qué falta y lleva al
  // calendario. disabled de verdad, solo mientras se envía.
  for (const b of [$("#enviar"), $("#enviar-movil")]) {
    b.disabled = estado.enviando;
    b.setAttribute("aria-disabled", String(!v.ok));
  }
}
function rotuloEnvio(texto) {
  for (const b of [$("#enviar"), $("#enviar-movil")]) b.textContent = texto;
}

// ---------------------------------------------------------------- envío
const campos = ["nombre", "email", "telefono", "mensaje"];
function mostrarError(el, texto) {
  el.textContent = texto;
  el.hidden = !texto;
}
/** Lleva al calendario con #cal-error a la vista. Si la tarjeta entera no cabe entre el encabezado y la barra fija
 *  (teléfono), manda el mensaje, que va al final de la tarjeta: con block "start" quedaba tapado por la barra. */
function verCalendario() {
  const cal = $("#calendario"), raiz = getComputedStyle(document.documentElement);
  const libre = innerHeight - (parseFloat(raiz.scrollPaddingTop) || 0) - (parseFloat(raiz.scrollPaddingBottom) || 0);
  if (cal.getBoundingClientRect().height <= libre) cal.scrollIntoView({ block: "start" });
  else $("#cal-error").scrollIntoView({ block: "end" });
}

$("#formulario").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (estado.enviando) return;
  // desde dónde se envió (Safari no enfoca un botón al hacer clic): mientras se envía, el botón queda disabled y el
  // foco cae al body; si hay error, vuelve aquí
  const origen = document.activeElement && document.activeElement !== document.body ? document.activeElement : ev.submitter;
  const datos = Object.fromEntries(campos.map((c) => [c, $("#" + c).value]));
  datos.huespedes = estado.huespedes;
  datos.acepta = $("#acepta").checked;
  const v = rangoActual();
  if (!v.ok) {
    mostrarError($("#cal-error"), MENSAJES[v.error || "fechas_requeridas"]);
    verCalendario();
    return;
  }
  const errores = validarDatos(datos);
  for (const c of [...campos, "acepta"]) $("#" + c).setAttribute("aria-invalid", String(Boolean(errores[c])));
  const claves = Object.keys(errores);
  if (claves.length) {
    mostrarError($("#form-error"), claves.map((k) => MENSAJES[k]).join(" "));
    $("#" + claves[0])?.focus();
    return;
  }
  mostrarError($("#form-error"), "");
  // lo que se envía queda congelado: el resumen de éxito no depende de lo que se toque mientras tanto
  const pedido = { entrada: estado.entrada, salida: estado.salida, huespedes: estado.huespedes,
    nombre: datos.nombre.trim(), email: datos.email.trim(), telefono: datos.telefono.trim(), mensaje: datos.mensaje.trim() };
  if ($("#sitio").value) { exito("—", v.noches, pedido); return; }   // campo trampa lleno: un bot; no se envía nada
  estado.enviando = true;
  pintar();
  rotuloEnvio("Enviando…");
  let r;
  try {
    [r] = await solicitar(pedido);
  } catch (err) {
    const c = codigoError(err);
    estado.enviando = false;
    rotuloEnvio("Solicitar");
    if (c === "fechas_ocupadas") await cargarDisponibilidad();
    const aviso = c === "fechas_ocupadas" || c.startsWith("fecha") ? $("#cal-error") : $("#form-error");
    mostrarError(aviso, MENSAJES[c]);
    pintar();
    if (!document.activeElement || document.activeElement === document.body) {
      origen?.focus({ preventScroll: true });
      if (document.activeElement !== origen) aviso.focus({ preventScroll: true });   // p. ej. #enviar oculto (< 1000 px)
    }
    if (aviso.id === "cal-error") verCalendario();
    return;
  }
  estado.enviando = false;
  rotuloEnvio("Solicitar");
  exito(r.codigo, r.noches, pedido);
});

function exito(codigo, n, p) {
  $("#codigo").textContent = codigo;
  $("#exito-texto").textContent = `Pediste ${n} noches, del ${fLargo.format(aFecha(p.entrada))} al ` +
    `${fLargo.format(aFecha(p.salida))}, para ${p.huespedes} ${p.huespedes === 1 ? "persona" : "personas"}.`;
  document.querySelector(".reserva").hidden = true;
  document.querySelector(".barra-movil").hidden = true;
  const s = $("#exito");
  s.hidden = false;
  s.focus();
  s.scrollIntoView({ block: "start" });
}

async function cargarDisponibilidad() {
  try {
    estado.ocupados = await disponibilidad(HOY, HASTA);
    if (estado.entrada && !llegadaPosible(estado.entrada)) { estado.entrada = null; estado.salida = null; }
    if (estado.salida && !rangoActual().ok) estado.salida = null;
  } catch (err) {
    mostrarError($("#cal-error"), MENSAJES[codigoError(err)]);
  }
  pintar();
}

huespedes(estado.huespedes);
pintar();
cargarDisponibilidad();
// Tarifas que editó el propietario (public.contenido, vía contenido-publico.js). Si no llegan (sin configuración,
// Supabase caído o la migración 0003 sin aplicar), el resumen sigue con las de ejemplo de TARIFA.
tarifas().then((t) => { if (t && fijarTarifas(t)) resumen(); }).catch(() => {});
