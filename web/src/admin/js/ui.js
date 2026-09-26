// Ayudas de DOM del portal. Todo texto entra con textContent o nodos de texto; nunca innerHTML.
import { hrefSeguro } from "./util.js";

const PROHIBIDAS = new Set(["innerHTML", "outerHTML", "srcdoc"]);

/**
 * Crea un elemento. props:
 *   texto -> textContent; clase -> className; for -> htmlFor; href -> filtrado por hrefSeguro;
 *   on<evento> -> addEventListener; aria-*, data-* y role -> setAttribute; el resto se asigna como propiedad
 *   (type, value, checked, disabled, id, name, src, alt, rows, maxLength, inputMode, hidden, tabIndex…).
 * Los hijos pueden ser nodos o textos (los textos se agregan como nodos de texto).
 */
export function el(etiqueta, props = {}, ...hijos) {
  const n = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (PROHIBIDAS.has(k)) throw new Error(`propiedad no permitida: ${k}`);
    if (k === "texto") n.textContent = String(v);
    else if (k === "clase") n.className = v;
    else if (k === "for") n.htmlFor = v;
    else if (k === "href") n.setAttribute("href", hrefSeguro(v));
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else if (k.startsWith("aria-") || k.startsWith("data-") || k === "role") n.setAttribute(k, v === true ? "true" : String(v));
    else n[k] = v;
  }
  for (const h of hijos.flat(Infinity)) {
    if (h == null || h === false) continue;
    n.append(h instanceof Node ? h : document.createTextNode(String(h)));
  }
  return n;
}

export function vaciar(nodo) {
  nodo.replaceChildren();
}

/** Escribe un aviso en una región con aria-live. tipo: "info" | "ok" | "error" | "cargando". */
export function anunciar(nodo, texto, tipo = "info") {
  if (!nodo) return;
  nodo.textContent = texto || "";
  nodo.dataset.tipo = texto ? tipo : "";
}

/** Oculta visualmente pero deja el texto para lectores de pantalla. */
export function oculto(texto) {
  return el("span", { clase: "visually-hidden", texto });
}

/**
 * Diálogo de confirmación (el <dialog id="dialogo"> de index.html). El foco arranca en «Volver», la opción segura.
 * -> Promise<boolean>
 */
export function confirmar({ titulo, texto, boton = "Confirmar", peligro = false }) {
  const d = document.getElementById("dialogo");
  if (!d || typeof d.showModal !== "function") {
    return Promise.resolve(window.confirm(`${titulo}\n\n${texto}`));
  }
  const previo = document.activeElement;
  d.querySelector("#dialogo-titulo").textContent = titulo;
  d.querySelector("#dialogo-texto").textContent = texto;
  const si = d.querySelector("#dialogo-si");
  const no = d.querySelector("#dialogo-no");
  si.textContent = boton;
  si.className = peligro ? "boton peligro" : "boton primario";
  return new Promise((resolver) => {
    const cerrar = (v) => () => d.close(v);
    const alSi = cerrar("si"), alNo = cerrar("no");
    si.addEventListener("click", alSi);
    no.addEventListener("click", alNo);
    d.addEventListener("close", () => {
      si.removeEventListener("click", alSi);
      no.removeEventListener("click", alNo);
      resolver(d.returnValue === "si");
      if (previo && previo.isConnected && typeof previo.focus === "function") previo.focus();
    }, { once: true });
    d.returnValue = "";
    d.showModal();
    no.focus();
  });
}

/** Deshabilita los controles dados mientras corre la promesa. */
export async function mientras(controles, promesa) {
  const lista = controles.filter(Boolean);
  const previos = lista.map((c) => c.disabled);
  lista.forEach((c) => { c.disabled = true; });
  try {
    return await promesa();
  } finally {
    lista.forEach((c, i) => { if (c.isConnected) c.disabled = previos[i]; });
  }
}
