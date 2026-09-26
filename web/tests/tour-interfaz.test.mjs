// Interfaz del tour con los textos más largos de inglés y francés (web/src/tour/js/interfaz.js y tour/tour.css):
//   cd web && npm test
// - el chip táctil (#chip-tactil) queda entero dentro de la pantalla aunque el toque caiga junto a un borde;
// - el selector de idioma de la tarjeta de inicio y el de la barra superior van fuera del flujo: no alargan la tarjeta
//   (en un teléfono en horizontal no cabría) ni descentran la pastilla del nombre.
// Las medidas en el navegador (667 × 375, 844 × 390 y 375 px, en es, en y fr) están en el mensaje del commit.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { MARGEN_CHIP_PX, centroChip, mostrarChip } from "../src/tour/js/interfaz.js";

const CSS = readFileSync(new URL("../src/tour/tour.css", import.meta.url), "utf8");
const HTML = readFileSync(new URL("../src/tour/index.html", import.meta.url), "utf8");

/** Bordes izquierdo y derecho del chip: tour.css lo corre -50 % de su ancho desde `left`. */
const bordes = (centro, ancho) => [centro - ancho / 2, centro + ancho / 2];

test("centroChip: con el toque a 20 px de cada borde, el chip queda entero y a 10 px del borde", () => {
  const vista = 375;
  for (const ancho of [114, 200, 315]) {
    const [izq] = bordes(centroChip(20, ancho, vista), ancho);
    assert.equal(izq, MARGEN_CHIP_PX, `ancho ${ancho}, x = 20`);
    const [, der] = bordes(centroChip(vista - 20, ancho, vista), ancho);
    assert.equal(der, vista - MARGEN_CHIP_PX, `ancho ${ancho}, x = ${vista - 20}`);
  }
});

test("centroChip: lejos de los bordes sigue la x del toque; si mide todo el ancho posible, va al centro", () => {
  assert.equal(centroChip(187, 114, 375), 187);
  assert.equal(centroChip(300, 114, 375), 300);
  assert.equal(centroChip(20, 355, 375), 187.5);              // max-width: calc(100vw - 20px)
  assert.equal(centroChip(355, 355, 375), 187.5);
  assert.equal(centroChip(60, 400, 375), 187.5);              // más ancho que la vista (no debería pasar): centrado
});

test("mostrarChip: escribe el texto, lo muestra y recién entonces lo mide para acomodar left", async () => {
  // en /fr/tour/ a 375 px, «Allumer Placards de la chambre principale · plafonnier» mide 355 px (dos líneas)
  const chip = { hidden: true, textContent: "", style: {}, get offsetWidth() { return this.hidden ? 0 : 355; } };
  const antes = { tenia: "document" in globalThis, document: globalThis.document };
  globalThis.document = { querySelector: (s) => (s === "#chip-tactil" ? chip : null) };
  try {
    for (const x of [20, 60, 300, 355]) {
      mostrarChip("Allumer Placards de la chambre principale · plafonnier", x, 240, 375);
      assert.equal(chip.hidden, false);
      assert.equal(chip.style.left, "187.5px", `x = ${x}`);
      assert.equal(chip.style.top, "240px");
    }
    chip.hidden = true;
    Object.defineProperty(chip, "offsetWidth", { get() { return this.hidden ? 0 : 114; } });
    mostrarChip("Ouvrir le tiroir", 20, 240, 375);
    assert.equal(chip.style.left, "67px");                   // 114 / 2 + 10
    mostrarChip("Ouvrir le tiroir", 355, 240, 375);
    assert.equal(chip.style.left, "308px");                  // 375 - 114 / 2 - 10
    assert.equal(chip.textContent, "Ouvrir le tiroir");
  } finally {
    if (antes.tenia) globalThis.document = antes.document; else delete globalThis.document;
  }
});

/** Cuerpos de las reglas cuyo selector es exactamente `selector` (fuera de @media), unidos. */
function regla(selector) {
  const sinComentarios = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  const patron = new RegExp(`(?<=^|\\})\\s*${selector.replace(/[.*+?^${}()|[\]\\#]/g, "\\$&")}\\s*\\{([^}]*)\\}`, "g");
  const cuerpos = [...sinComentarios.matchAll(patron)].map((m) => m[1]);
  assert.ok(cuerpos.length, `tour.css: falta la regla ${selector}`);
  return cuerpos.join("\n");
}

test("tour.css: el ancho del chip no depende de left (max-content, con el mismo margen que interfaz.js)", () => {
  assert.match(regla("#chip-tactil"), /width:\s*max-content/);
  assert.match(regla("#aviso, #chip-tactil"), new RegExp(`max-width:\\s*calc\\(100vw - ${2 * MARGEN_CHIP_PX}px\\)`));
});

test("tour.css: el selector de la tarjeta de inicio va en su esquina, fuera del flujo, y no le suma alto", () => {
  assert.match(regla("#pantalla-inicio .tarjeta"), /position:\s*relative/);
  const sel = regla("#pantalla-inicio .idiomas");
  assert.match(sel, /position:\s*absolute/);
  assert.doesNotMatch(sel, /margin/);
  // en pantallas bajas la portada se puede desplazar y la tarjeta no se corta por arriba (margin: auto, no sólo
  // place-items: center)
  assert.match(CSS, /@media \(max-height: 480px\) \{\s*#pantalla-inicio \{ overflow-y: auto;/);
  assert.match(regla("#pantalla-inicio .tarjeta"), /margin:\s*auto/);
});

test("tour: el selector de la barra cuelga de «Reservar» fuera del flujo y mide 44 px de alto, como sus vecinos", () => {
  // en el HTML: .barra-derecha envuelve el selector y «Reservar»; la barra tiene tres hijos, como antes del selector
  const barra = HTML.match(/<header id="barra-superior">([\s\S]*?)<\/header>/)[1];
  const hijos = [...barra.replace(/<!--[\s\S]*?-->/g, "").matchAll(/^ {2}<(a|p|div|nav)\b[^>]*>/gm)].map((m) => m[0].trim());
  assert.equal(hijos.length, 3, hijos.join("\n"));
  assert.match(hijos[2], /class="barra-derecha"/);
  assert.match(barra, /<div class="barra-derecha">\s*<nav class="idiomas panel"[\s\S]*?<\/nav>\s*<a class="btn-reservar panel"/);
  assert.match(regla(".barra-derecha"), /position:\s*relative/);
  assert.match(regla("#barra-superior .idiomas"), /position:\s*absolute/);
  assert.match(regla("#barra-superior .idiomas a"), /min-height:\s*42px/);   // + 2 px de borde del .panel
});

// ---------------------------------------------------------------- botonera inferior
// Con left: 50% y sin ancho propio, el ancho disponible de #botonera era la mitad de la vista: entre unos 565 y 690 px,
// «Floor plan», «Full screen» y «Plein écran» partían en dos líneas y la botonera pasaba de 60 a 72 px (los paneles
// flotantes, puestos a 66 px del borde, la tapaban). Medido después del cambio a 640 × 360 y 667 × 375: 60 px en los
// tres idiomas.
const DICCIONARIOS = Object.fromEntries(["es", "en", "fr"].map((i) =>
  [i, JSON.parse(readFileSync(new URL(`../src/i18n/${i}.json`, import.meta.url), "utf8"))]));
const ANCHO_SIN_ETIQUETAS = 560;         // @media (max-width: 560px): bajo ese ancho las etiquetas se ocultan

/** Ancho de `texto` a `px` px con Public Sans 500, por lo alto: 0,62 em por carácter (la media medida en el navegador
 *  es de unos 0,5 em; así la prueba avisa antes de que una etiqueta no quepa de verdad). */
const anchoTexto = (texto, px) => [...texto].length * 0.62 * px;

test("tour.css: la botonera tiene su ancho natural y sus etiquetas no parten en dos líneas", () => {
  assert.match(regla("#botonera"), /width:\s*max-content/);
  assert.match(regla(".boton-icono span"), /white-space:\s*nowrap/);
  const oculta = CSS.match(/@media \(max-width: (\d+)px\) \{\s*\.boton-icono span \{ display: none; \}/);
  assert.ok(oculta, "falta la regla que oculta las etiquetas en el teléfono");
  assert.equal(Number(oculta[1]), ANCHO_SIN_ETIQUETAS);
});

test("botonera: por encima de 560 px, con las etiquetas en una línea, cabe en la vista en los tres idiomas", () => {
  const boton = regla(".boton-icono"), span = regla(".boton-icono span"), barra = regla("#botonera");
  const minimo = Number(boton.match(/min-width:\s*(\d+)px/)[1]);
  const relleno = Number(boton.match(/padding:\s*\d+px\s+(\d+)px/)[1]);
  const letra = Number(span.match(/font-size:\s*([\d.]+)px/)[1]);
  const hueco = Number(barra.match(/gap:\s*(\d+)px/)[1]), rellenoBarra = Number(barra.match(/padding:\s*(\d+)px/)[1]);
  const claves = [...HTML.matchAll(/<button class="boton-icono"[\s\S]*?<span data-i18n="([^"]+)">/g)].map((m) => m[1]);
  assert.deepEqual(claves, ["tour.plano", "tour.luces", "tour.momento", "tour.ayuda", "tour.pantalla"]);
  const vista = ANCHO_SIN_ETIQUETAS + 1;
  for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
    const botones = claves.map((k) => Math.max(minimo, anchoTexto(d[k], letra) + 2 * relleno));
    const ancho = botones.reduce((a, b) => a + b, 0) + hueco * (botones.length - 1) + 2 * rellenoBarra + 2;
    assert.ok(ancho <= vista - 20, `${idioma}: la botonera mediría ${Math.round(ancho)} px en una vista de ${vista} px`);
  }
});

test("botonera: la etiqueta de «Momento del día» está en el nombre accesible de su botón", () => {
  // el botón lleva aria-label (bajo 560 px la etiqueta se oculta); el texto visible tiene que estar dentro del nombre
  const boton = HTML.match(/<button class="boton-icono"[^>]*data-panel="momento"[^>]*>/)[0];
  const clave = boton.match(/data-i18n-attr="aria-label:([^"]+)"/)[1];
  for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
    assert.ok(d[clave].toLowerCase().includes(d["tour.momento"].toLowerCase()), `${idioma}: «${d["tour.momento"]}» / «${d[clave]}»`);
  }
});
