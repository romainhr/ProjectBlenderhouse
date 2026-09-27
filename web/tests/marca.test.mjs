// El nombre del lugar sale de web/src/marca.json y debe ser el mismo en todas las páginas públicas; ninguna
// página visible puede llamarlo "loft" (pedido del dueño, 2026-09-26). El portal web/src/admin/ es de otra
// sesión y queda fuera de esta prueba.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src");
const { nombre } = JSON.parse(readFileSync(join(SRC, "marca.json"), "utf8"));
const PAGINAS = ["index.html", "reserva.html", "privacidad.html", "404.html", "tour/index.html"];

// Texto que ve el usuario: sin comentarios HTML, scripts ni estilos, pero con title, alt, aria-label y meta.
function textoVisible(html) {
  return html.replace(/<!--[\s\S]*?-->/g, " ").replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ");
}

for (const pagina of PAGINAS) {
  const html = readFileSync(join(SRC, pagina), "utf8");
  test(`${pagina}: el título usa el nombre de marca.json`, () => {
    const titulo = (html.match(/<title(?:\s[^>]*)?>([^<]*)<\/title>/) || [])[1] || "";   // con o sin data-i18n
    assert.ok(titulo.includes(nombre), `título «${titulo}» sin «${nombre}»`);
  });
  test(`${pagina}: no dice "loft" en el texto visible`, () => {
    assert.doesNotMatch(textoVisible(html), /loft/i);
  });
}
