// Paneles, textos y controles de la interfaz (no toca three.js). Traduce las acciones del usuario a
// llamadas de vuelta hacia main.js/interaccion.js; no conoce la escena 3D. Los textos propios salen de t()
// (claves js.tour.* de web/src/i18n/*.json) y se insertan con textContent o setAttribute, nunca como HTML.
import { IDIOMAS, t } from "../../js/i18n.js";

const $ = (s) => document.querySelector(s);

// --- selector de idioma ---------------------------------------------------------------------------------------
// <a data-i18n-alternar="es|en|fr"> (web/build.py le pone el href a este tour en ese idioma). Al elegir se guarda la
// cookie nf_lang, que en Netlify reemplaza la detección por el idioma del navegador (ADR 0007, decisión 4), antes de
// que el enlace navegue. El tour no carga js/sitio.js, que hace lo mismo en el resto del sitio.
export const MAX_EDAD_IDIOMA_S = 31536000;   // un año

/** Texto de document.cookie para recordar `idioma`, o null si no es es, en ni fr. */
export function cookieIdioma(idioma) {
  if (!IDIOMAS.includes(idioma)) return null;
  return `nf_lang=${idioma}; path=/; max-age=${MAX_EDAD_IDIOMA_S}; SameSite=Lax; Secure`;
}

/** Escucha los clics (y el clic central, que abre otra pestaña) sobre el selector y guarda la cookie. */
export function iniciarSelectorIdioma(doc = document) {
  const guardar = (e) => {
    if (e.type === "auxclick" && e.button !== 1) return;
    const enlace = e.target && typeof e.target.closest === "function" ? e.target.closest("a[data-i18n-alternar]") : null;
    const cookie = enlace ? cookieIdioma(enlace.getAttribute("data-i18n-alternar")) : null;
    if (cookie) doc.cookie = cookie;
  };
  doc.addEventListener("click", guardar);
  doc.addEventListener("auxclick", guardar);
}

export function marcarTactil(tactil) {
  document.body.classList.toggle("tactil", tactil);
}

// Botonera inferior <-> paneles flotantes: un botón abre su panel y cierra los demás; "cerrar" o Escape
// cierran el que esté abierto.
export function iniciarPaneles() {
  const botones = Array.from(document.querySelectorAll(".boton-icono[data-panel]"));
  const paneles = new Map(botones.map((b) => [b.dataset.panel, $(`#panel-${b.dataset.panel}`)]));

  function cerrarTodos() {
    for (const [id, panel] of paneles) {
      panel.hidden = true;
      const b = botones.find((x) => x.dataset.panel === id);
      if (b) b.setAttribute("aria-expanded", "false");
    }
  }
  for (const boton of botones) {
    boton.addEventListener("click", () => {
      const panel = paneles.get(boton.dataset.panel);
      const yaAbierto = !panel.hidden;
      cerrarTodos();
      if (!yaAbierto) { panel.hidden = false; boton.setAttribute("aria-expanded", "true"); }
    });
  }
  for (const panel of paneles.values()) {
    panel.querySelector(".cerrar")?.addEventListener("click", cerrarTodos);
  }
  window.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarTodos(); });
  return { cerrarTodos };
}

// --- luces -----------------------------------------------------------------------------------------------
export function pintarGruposLuz(gruposLuz, { onCambiar, onTodo }) {
  const lista = $("#lista-grupos-luz");
  lista.innerHTML = "";
  for (const grupo of gruposLuz.values()) {
    const fila = document.createElement("div");
    fila.className = "grupo-luz";
    const nombre = document.createElement("span");
    nombre.textContent = grupo.etiqueta;
    const interruptor = document.createElement("button");
    interruptor.type = "button"; interruptor.className = "interruptor"; interruptor.setAttribute("role", "switch");
    interruptor.setAttribute("aria-label", t("js.tour.luz.interruptor", { nombre: grupo.etiqueta }));
    interruptor.setAttribute("aria-pressed", String(grupo.encendido));
    interruptor.addEventListener("click", () => {
      const nuevo = !grupo.encendido;
      interruptor.setAttribute("aria-pressed", String(nuevo));
      onCambiar(grupo.id, nuevo);
    });
    fila.append(nombre, interruptor);
    lista.appendChild(fila);
  }
  $("#luces-todo [data-accion='apagar']").onclick = () => { onTodo(false); refrescarGruposLuzUI(gruposLuz); };
  $("#luces-todo [data-accion='encender']").onclick = () => { onTodo(true); refrescarGruposLuzUI(gruposLuz); };
}
export function refrescarGruposLuzUI(gruposLuz) {
  const filas = Array.from(document.querySelectorAll("#lista-grupos-luz .grupo-luz"));
  Array.from(gruposLuz.values()).forEach((grupo, i) => {
    filas[i]?.querySelector(".interruptor")?.setAttribute("aria-pressed", String(grupo.encendido));
  });
}

// --- momento del día ---------------------------------------------------------------------------------------
export function iniciarMomento(momentoInicial, onElegir) {
  const botones = Array.from(document.querySelectorAll(".opcion-momento button"));
  for (const b of botones) {
    b.setAttribute("aria-pressed", String(b.dataset.momento === momentoInicial));
    b.addEventListener("click", () => {
      botones.forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      onElegir(b.dataset.momento);
    });
  }
}

// --- carga y errores ---------------------------------------------------------------------------------------
export function actualizarCarga(fraccion, texto) {
  $("#barra-carga i").style.width = `${Math.round(Math.min(100, fraccion * 100))}%`;
  if (texto) $("#texto-estado").textContent = texto;
}
export function marcarError(texto) {
  const el = $("#texto-estado");
  el.textContent = texto; el.classList.add("es-error");
}
export function habilitarEntrar() {
  const b = $("#entrar");
  b.disabled = false; b.focus();
}
export function ocultarPortada() { $("#pantalla-inicio").hidden = true; }

// --- mira, pista, chip y avisos ------------------------------------------------------------------------------
export function marcarMiraActiva(activa) { $("#mira").classList.toggle("activa", activa); }
export function mostrarMira() { $("#mira").hidden = false; }
export function mostrarPista(texto) { const p = $("#pista"); p.textContent = texto; p.hidden = false; }
export function ocultarPista() { $("#pista").hidden = true; }
export function mostrarChip(texto, x, y) {
  const p = $("#chip-tactil"); p.textContent = texto; p.style.left = `${x}px`; p.style.top = `${y}px`; p.hidden = false;
}
export function ocultarChip() { $("#chip-tactil").hidden = true; }
let avisoHasta = 0;
export function mostrarAviso(texto, ms) {
  const el = $("#aviso"); el.textContent = texto; el.hidden = false; avisoHasta = performance.now() + ms;
}
export function actualizarAviso() {
  if (performance.now() > avisoHasta) $("#aviso").hidden = true;
}

// --- joystick (sincroniza el DOM con controles.palanca) ----------------------------------------------------
export function dibujarJoystick(palanca) {
  const el = $("#joystick");
  el.hidden = !palanca.visible;
  if (!palanca.visible) return;
  el.style.left = `${palanca.x}px`; el.style.top = `${palanca.y}px`;
  el.querySelector("i").style.transform = `translate(${palanca.pomoX}px, ${palanca.pomoY}px)`;
}

// --- pantalla completa --------------------------------------------------------------------------------------
export function iniciarPantallaCompleta() {
  const boton = $("#btn-pantalla-completa");
  if (!document.fullscreenEnabled) return;
  boton.hidden = false;
  boton.addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen().catch(() => {});
  });
}

// --- depuración (?debug) -------------------------------------------------------------------------------------
export function mostrarDepuracion() { $("#depuracion").hidden = false; }
export function actualizarDepuracion(texto) { $("#depuracion").textContent = texto; }
