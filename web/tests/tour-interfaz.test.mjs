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
