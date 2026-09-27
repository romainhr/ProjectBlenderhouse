// Página de reserva: calendario de disponibilidad, datos del huésped, resumen y envío de la solicitud.
// Todo texto visible y toda etiqueta aria sale de t()/tn() de i18n.js (claves js.reserva.* de web/src/i18n/*.json), y
// las fechas y los montos se escriben con el LOCALE del idioma de la página (es-CL, en-US o fr-FR).
// Antes de pintar se espera `listo` de i18n.js (en español se cumple enseguida; en /en/ y /fr/, cuando llega su
// diccionario o vence el plazo, y entonces sigue el español). La disponibilidad se pide antes de esa espera, para que
// la lectura de la base no vaya detrás del diccionario.
import {
  TARIFA, clp, codigoError, diasCortos, esIso, fijarTarifas, grillaMes, hayMesSiguiente, hoyIso, mesesPorPagina,
  nocheOcupada, noches, nombresDias, salidaMaxima, sumarDias, tarifaVigente, textoMensaje, total, validarDatos,
  validarRango,
} from "./reserva-logica.js";
import { LOCALE, listo, t, tn } from "./i18n.js";
import { disponibilidad, simulado, solicitar } from "./reservas-api.js";
import { tarifas } from "./contenido-publico.js";

const $ = (s) => document.querySelector(s);
const HOY = hoyIso();
const LLEGADA_MAX = sumarDias(HOY, TARIFA.anticipacionMaxDias);   // la base rechaza llegadas más lejanas (fecha_lejana)
const HASTA = sumarDias(LLEGADA_MAX, TARIFA.maxNoches);          // última salida posible
const primeraDisponibilidad = disponibilidad(HOY, HASTA);        // ya, sin esperar los textos (cargarDisponibilidad)
primeraDisponibilidad.catch(() => {});                           // el error lo muestra cargarDisponibilidad
await listo;
const DIAS = diasCortos(t("js.reserva.cal.dias_cortos"), LOCALE);   // cabecera: lu ma mi … (Mo Tu We …, lu ma me …)
const DIAS_LARGOS = nombresDias(LOCALE);                          // abbr de cada columna, para lectores de pantalla
const fMes = new Intl.DateTimeFormat(LOCALE, { month: "long", year: "numeric", timeZone: "UTC" });
const fDia = new Intl.DateTimeFormat(LOCALE, { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
const fLargo = new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const mensaje = (codigo) => textoMensaje(codigo, t);
const nNoches = (n) => tn("js.reserva.noches", n);
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
  if (d < HOY) return t("js.reserva.cal.motivo.pasado");
  if (nocheOcupada(d, estado.ocupados)) return t("js.reserva.cal.motivo.ocupado");
  if (d > LLEGADA_MAX) return t("js.reserva.cal.motivo.lejano");
  if (estado.entrada && !estado.salida && d > estado.entrada && d < sumarDias(estado.entrada, TARIFA.minNoches)) {
    return t("js.reserva.cal.motivo.minimo", { n: TARIFA.minNoches });
  }
  return t("js.reserva.cal.motivo.sin_salida", { n: TARIFA.minNoches });
}

/** Nombre accesible de un día: la fecha larga y, si corresponde, su papel en la estadía o por qué no se puede elegir. */
function etiquetaDia(dia, { esEntrada, esSalida, enRango, habilitado }) {
  const fecha = fLargo.format(aFecha(dia));
  if (esEntrada) return t("js.reserva.cal.dia_llegada", { fecha });
  if (esSalida) return t("js.reserva.cal.dia_salida", { fecha });
  if (enRango) return t("js.reserva.cal.dia_en_rango", { fecha });
  if (!habilitado) return t("js.reserva.cal.dia_no_disponible", { fecha, motivo: motivo(dia) });
  return fecha;
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
        b.setAttribute("aria-label", etiquetaDia(dia, { esEntrada, esSalida, enRango, habilitado }));
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
  $("#rango-texto").textContent = !estado.entrada ? t("js.reserva.cal.elige_llegada")
    : !estado.salida ? t("js.reserva.cal.elige_salida", { entrada: fDia.format(aFecha(estado.entrada)) })
      : t("js.reserva.cal.rango", { entrada: fDia.format(aFecha(estado.entrada)),
        salida: fDia.format(aFecha(estado.salida)), noches: nNoches(noches(estado.entrada, estado.salida)) });
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
  const monto = total(v.ok ? v.noches : 0);
  $("#s-entrada").textContent = estado.entrada ? fDia.format(aFecha(estado.entrada)) : "—";
  $("#s-salida").textContent = estado.salida ? fDia.format(aFecha(estado.salida)) : "—";
  $("#s-noches-txt").textContent = v.ok
    ? t("js.reserva.resumen.noches_por_tarifa", { noches: nNoches(v.noches), tarifa: clp(tarifaVigente().noche, LOCALE) })
    : t("js.reserva.resumen.noches");
  $("#s-alojamiento").textContent = v.ok ? clp(monto.alojamiento, LOCALE) : "—";
  $("#s-limpieza").textContent = v.ok ? clp(monto.limpieza, LOCALE) : "—";
  $("#s-total").textContent = v.ok ? clp(monto.total, LOCALE) : "—";
  $("#m-total").textContent = v.ok ? clp(monto.total, LOCALE) : t("js.reserva.resumen.elige_fechas");
  $("#m-total").classList.toggle("vacio", !v.ok);
  $("#m-noches").textContent = v.ok ? t("js.reserva.resumen.total_ejemplo", { noches: nNoches(v.noches) })
    : t("js.reserva.resumen.sin_cobro");
  if (estado.entrada && estado.salida && !v.ok && v.error) mostrarError($("#cal-error"), mensaje(v.error));
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
    mostrarError($("#cal-error"), mensaje(v.error || "fechas_requeridas"));
    verCalendario();
    return;
  }
  const errores = validarDatos(datos);
  for (const c of [...campos, "acepta"]) $("#" + c).setAttribute("aria-invalid", String(Boolean(errores[c])));
  const claves = Object.keys(errores);
  if (claves.length) {
    mostrarError($("#form-error"), claves.map((k) => mensaje(k)).join(" "));
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
  rotuloEnvio(t("js.reserva.envio.enviando"));
  let r;
  try {
    [r] = await solicitar(pedido);
  } catch (err) {
    const c = codigoError(err);
    estado.enviando = false;
    rotuloEnvio(t("js.reserva.envio.solicitar"));
    if (c === "fechas_ocupadas") await cargarDisponibilidad();
    const aviso = c === "fechas_ocupadas" || c.startsWith("fecha") ? $("#cal-error") : $("#form-error");
    mostrarError(aviso, mensaje(c));
    pintar();
    if (!document.activeElement || document.activeElement === document.body) {
      origen?.focus({ preventScroll: true });
      if (document.activeElement !== origen) aviso.focus({ preventScroll: true });   // p. ej. #enviar oculto (< 1000 px)
    }
    if (aviso.id === "cal-error") verCalendario();
    return;
  }
  estado.enviando = false;
  rotuloEnvio(t("js.reserva.envio.solicitar"));
  exito(r.codigo, r.noches, pedido);
});

function exito(codigo, n, p) {
  $("#codigo").textContent = codigo;
  $("#exito-texto").textContent = t("js.reserva.exito.texto", { noches: nNoches(n),
    entrada: fLargo.format(aFecha(p.entrada)), salida: fLargo.format(aFecha(p.salida)),
    personas: tn("js.reserva.personas", p.huespedes) });
  document.querySelector(".reserva").hidden = true;
  document.querySelector(".barra-movil").hidden = true;
  const s = $("#exito");
  s.hidden = false;
  s.focus();
  s.scrollIntoView({ block: "start" });
}

async function cargarDisponibilidad(pedido = disponibilidad(HOY, HASTA)) {
  try {
    estado.ocupados = await pedido;
    if (estado.entrada && !llegadaPosible(estado.entrada)) { estado.entrada = null; estado.salida = null; }
    if (estado.salida && !rangoActual().ok) estado.salida = null;
  } catch (err) {
    mostrarError($("#cal-error"), mensaje(codigoError(err)));
  }
  pintar();
}

huespedes(estado.huespedes);
pintar();
cargarDisponibilidad(primeraDisponibilidad);
// Tarifas que editó el propietario (public.contenido, vía contenido-publico.js). Si no llegan (sin configuración,
// Supabase caído o la migración 0003 sin aplicar), el resumen sigue con las de ejemplo de TARIFA.
tarifas().then((editadas) => { if (editadas && fijarTarifas(editadas)) resumen(); }).catch(() => {});
