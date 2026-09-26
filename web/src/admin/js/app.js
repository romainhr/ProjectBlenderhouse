// Portal del propietario de LOFT 2D2B: arranque, modo (real, simulado o sin configurar), login, navegación por
// hash (#reservas, #textos, #fotos: nunca datos de huéspedes en la URL) y cierre de sesión.
import { crearApi } from "./api.js";
import { crearApiSimulada } from "./api-simulada.js";
import { mensajeError, MENSAJES } from "./errores.js";
import { decidirModo } from "./modo.js";
import { crearCliente } from "./supabase.js";
import { anunciar, confirmar, el } from "./ui.js";
import { crearVistaFotos } from "./vista-fotos.js";
import { crearVistaReservas } from "./vista-reservas.js";
import { crearVistaTextos } from "./vista-textos.js";

const $ = (s) => document.querySelector(s);
const VISTAS = ["reservas", "textos", "fotos"];

/** dist/js/config.js lo genera web/build.py; en web/src no existe y el import falla: se trata como «sin configurar». */
async function cargarConfiguracion() {
  try {
    const m = await import("../../js/config.js");
    return { url: String(m.SUPABASE_URL || "").replace(/\/+$/, ""), clave: String(m.SUPABASE_CLAVE_PUBLICA || "") };
  } catch {
    return { url: "", clave: "" };
  }
}

function almacenDeSesion() {
  try {
    const s = window.sessionStorage;
    s.getItem("x");
    return s;
  } catch {
    const m = new Map();                    // sessionStorage bloqueado: la sesión dura lo que la página abierta
    return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)),
      removeItem: (k) => m.delete(k), clear: () => m.clear() };
  }
}

async function iniciar() {
  const config = await cargarConfiguracion();
  const modo = decidirModo({ hostname: location.hostname, search: location.search, config });
  const almacen = almacenDeSesion();
  const secciones = {
    cargando: $("#vista-cargando"), login: $("#vista-login"), sinRol: $("#vista-sin-rol"),
    reservas: $("#vista-reservas"), textos: $("#vista-textos"), fotos: $("#vista-fotos"),
  };
  const nav = $("#navegacion");
  const usuario = $("#usuario");
  const loginAviso = $("#login-aviso");
  const loginError = $("#login-error");
  const form = $("#form-login");
  let dentro = false;

  let api;
  if (modo === "simulado") {
    $("#aviso-modo").hidden = false;
    document.title = `[Simulado] ${document.title}`;
    api = crearApiSimulada({ almacen });
  } else if (modo === "real") {
    api = crearApi(crearCliente({ url: config.url, clave: config.clave, almacen, alPerderSesion: () => salir("sesion_vencida") }));
  }

  const badge = $("#insignia-pendientes");
  const vistas = api ? {
    reservas: crearVistaReservas({ raiz: secciones.reservas, api, alCambiarPendientes: (n) => {
      badge.hidden = n === 0;
      badge.replaceChildren(String(n), el("span", { clase: "visually-hidden", texto: n === 1 ? " pendiente" : " pendientes" }));
    } }),
    textos: crearVistaTextos({ raiz: secciones.textos, api }),
    fotos: crearVistaFotos({ raiz: secciones.fotos, api }),
  } : {};

  function mostrarSolo(nombre) {
    for (const [k, s] of Object.entries(secciones)) s.hidden = k !== nombre;
  }

  function mostrarLogin(motivo = "") {
    dentro = false;
    nav.hidden = true;
    usuario.hidden = true;
    mostrarSolo("login");
    anunciar(loginError, "");
    if (motivo) {
      loginAviso.textContent = MENSAJES[motivo] || motivo;
      loginAviso.hidden = false;
    } else {
      loginAviso.hidden = true;
    }
    $("#login-correo").focus();
  }

  function enrutar({ enfocar = true } = {}) {
    if (!dentro) return;
    const nombre = VISTAS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "reservas";
    mostrarSolo(nombre);
    for (const a of nav.querySelectorAll("a[data-vista]")) {
      if (a.dataset.vista === nombre) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    }
    vistas[nombre].mostrar();
    if (enfocar) secciones[nombre].querySelector("h1").focus();
  }

  async function entrar() {
    mostrarSolo("cargando");
    let propietario = false;
    try {
      propietario = await api.esPropietario();
    } catch (e) {
      if (e && e.codigo === "sesion_vencida") return;           // alPerderSesion ya volvió al login
      $("#sin-rol-texto").textContent = mensajeError(e);
      $("#t-sin-rol").textContent = "No se pudo comprobar el acceso";
      mostrarSinRol();
      return;
    }
    if (!propietario) {
      $("#t-sin-rol").textContent = "Sin acceso de propietario";
      $("#sin-rol-texto").textContent = "Esta cuenta existe, pero no está registrada como propietario del loft. " +
        "Quien administra Supabase debe agregarla a public.propietarios (paso a paso en docs/portal-gestion.md).";
      mostrarSinRol();
      return;
    }
    dentro = true;
    nav.hidden = false;
    mostrarUsuario();
    vistas.reservas.mostrar();                                     // el aviso de pendientes aparece en cualquier vista
    enrutar();
  }

  function mostrarUsuario() {
    const u = api.usuario();
    $("#usuario-correo").textContent = u && u.email ? u.email : "";
    usuario.hidden = false;
  }

  function mostrarSinRol() {
    dentro = false;
    nav.hidden = true;
    mostrarUsuario();
    mostrarSolo("sinRol");
    $("#t-sin-rol").focus();
  }

  function limpiarVistas() {
    for (const v of Object.values(vistas)) v.reiniciar();
    badge.hidden = true;
  }

  /** Vuelve al login (cierre voluntario o sesión vencida) y quita de la página los datos cargados. */
  function salir(motivo = "") {
    limpiarVistas();
    mostrarLogin(motivo);
  }

  // ------------------------------------------------------------------ eventos
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!api) return;
    const correo = $("#login-correo"), clave = $("#login-clave"), boton = $("#login-boton");
    if (!correo.value.trim() || !clave.value) {
      anunciar(loginError, MENSAJES.datos_login, "error");
      (correo.value.trim() ? clave : correo).focus();
      return;
    }
    boton.disabled = true;
    anunciar(loginError, "");
    loginAviso.hidden = true;
    boton.textContent = "Ingresando…";
    try {
      await api.iniciarSesion(correo.value, clave.value);
      clave.value = "";
      await entrar();
    } catch (e) {
      anunciar(loginError, mensajeError(e), "error");
      clave.focus();
    } finally {
      boton.disabled = false;
      boton.textContent = "Ingresar";
    }
  });

  $("#cerrar-sesion").addEventListener("click", async () => {
    const pendientes = Object.values(vistas).some((v) => v.hayCambios());
    if (pendientes) {
      const ok = await confirmar({ titulo: "Cambios sin guardar", texto: "Hay cambios sin guardar. Si cierras la sesión se pierden.",
        boton: "Cerrar sesión igual", peligro: true });
      if (!ok) return;
    }
    await api.cerrarSesion();
    salir("");
    anunciar(loginError, "");
    loginAviso.textContent = "Sesión cerrada.";
    loginAviso.hidden = false;
  });

  window.addEventListener("hashchange", () => enrutar());
  window.addEventListener("beforeunload", (ev) => {
    if (dentro && Object.values(vistas).some((v) => v.hayCambios())) {
      ev.preventDefault();
      ev.returnValue = "";
    }
  });

  // ------------------------------------------------------------------ arranque
  if (modo === "sin_configurar") {
    mostrarLogin("sin_configurar");
    for (const c of form.elements) c.disabled = true;
    return;
  }
  const sesion = await api.restaurarSesion();
  if (sesion) await entrar();
  else if (secciones.cargando.hidden === false) mostrarLogin();
}

iniciar().catch(() => {
  const s = document.getElementById("vista-cargando");
  if (s) s.textContent = "No se pudo iniciar el portal. Recarga la página.";
});
