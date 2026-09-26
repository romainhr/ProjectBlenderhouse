// Pruebas estáticas (sin DOM) de las páginas públicas y su CSS contra web/diseno/ESPEC-v4.md (§6.4 y §8):
// viewport sin bloqueo de zoom, foco nunca eliminado, sin Tailwind ni Google Fonts ni manejadores en línea, rótulos
// únicos, hooks de reserva.js, contenido editable igual a la semilla de 0003_gestion.sql e imágenes con medidas.
//   cd web && npm test
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const SRC = join(WEB, "src");
const leer = (ruta) => readFileSync(join(SRC, ruta), "utf8");
const PUBLICAS = ["index.html", "reserva.html", "privacidad.html", "404.html"];
const html = Object.fromEntries(PUBLICAS.map((p) => [p, leer(p)]));
const css = { "sitio.css": leer("css/sitio.css"), "tokens.css": leer("css/tokens.css") };

/** Texto visible: sin comentarios, scripts, estilos, etiquetas ni atributos. */
function textoVisible(s) {
  return s.replace(/<!--[\s\S]*?-->/g, " ").replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ").replace(/<head>[\s\S]*?<\/head>/i, " ").replace(/<[^>]+>/g, " ");
}
const atributo = (etiqueta, nombre) => (etiqueta.match(new RegExp(`\\s${nombre}="([^"]*)"`)) || [])[1];

test("viewport sin bloqueo de zoom en la portada y la reserva", () => {
  for (const p of ["index.html", "reserva.html"]) {
    const vp = (html[p].match(/<meta name="viewport" content="([^"]*)">/) || [])[1];
    assert.equal(vp, "width=device-width, initial-scale=1, viewport-fit=cover", p);
  }
});

test("la casilla de consentimiento no viene marcada y es obligatoria", () => {
  const casilla = (html["reserva.html"].match(/<input id="acepta"[^>]*>/) || [])[0];
  assert.ok(casilla, "falta #acepta");
  assert.doesNotMatch(casilla, /\bchecked\b/);
  assert.match(casilla, /\brequired\b/);
  assert.doesNotMatch(html["reserva.html"], /value="Ana Pérez"|ejemplo\.com|1234 5678/, "sin valores ni ejemplos precargados");
});

test("el CSS nunca quita el foco ni el resaltado táctil", () => {
  for (const [nombre, s] of Object.entries(css)) {
    assert.doesNotMatch(s, /outline:\s*(none|0)\b/, nombre);
    assert.doesNotMatch(s, /tap-highlight-color:\s*transparent/, nombre);
    assert.doesNotMatch(s, /font-variation-settings/, `${nombre}: el tamaño óptico lo decide font-optical-sizing`);
  }
  assert.match(css["sitio.css"], /:focus-visible\s*\{\s*outline:\s*2px solid var\(--anillo\)/);
  assert.match(css["sitio.css"], /@media \(prefers-reduced-motion: reduce\)/);
});

test("sin Tailwind, Google Fonts, scripts en línea ni manejadores on…=", () => {
  for (const [p, s] of Object.entries(html)) {
    assert.doesNotMatch(s, /cdn\.tailwindcss\.com|fonts\.googleapis\.com|fonts\.gstatic\.com/, p);
    assert.doesNotMatch(s, /<[^>]+\son[a-z]+=/i, `${p}: manejador en línea`);
    assert.doesNotMatch(s, /<script(?![^>]*\bsrc=)[^>]*>/, `${p}: script en línea (la CSP de build.py no lo permite)`);
    assert.doesNotMatch(s, /href="#"/, `${p}: destino roto`);
  }
});

test("rótulos únicos: ni «tour» ni los retirados en el texto visible", () => {
  for (const [p, s] of Object.entries(html)) {
    const t = textoVisible(s);
    assert.doesNotMatch(t, /\btour\b/i, p);
    assert.doesNotMatch(t, /Ver disponibilidad|Solicitar reserva|Ver fechas disponibles|Tour 3D/, p);
  }
});

test("«Project-roomVR» siempre va en un elemento que no se parte", () => {
  for (const [p, s] of Object.entries(html)) {
    const cuerpo = s.slice(s.indexOf("<body"));
    const sinAtributos = cuerpo.replace(/<[^>]+>/g, (e) => e.replace(/"[^"]*"/g, '""'));
    const ocurrencias = [...sinAtributos.matchAll(/Project-roomVR/g)].length;
    const envueltas = [...cuerpo.matchAll(/<(b|span class="nombre"|a class="pie-marca"[^>]*)>Project-roomVR<\//g)].length;
    assert.equal(envueltas, ocurrencias, `${p}: ${ocurrencias - envueltas} sin .nombre, .marca b ni .pie-marca`);
  }
  assert.match(css["sitio.css"], /\.nombre \{ white-space: nowrap; \}/);
  assert.match(css["sitio.css"], /\.marca b \{[^}]*white-space: nowrap/);
  assert.match(css["sitio.css"], /\.pie-marca \{[^}]*white-space: nowrap/);
});

test("reserva.html conserva todos los hooks de reserva.js", () => {
  const ids = ["calendario", "meses", "mes-ant", "mes-sig", "rango-texto", "cal-error", "aviso-sim", "s-entrada",
    "s-salida", "s-noches-txt", "s-alojamiento", "s-limpieza", "s-total", "enviar", "formulario", "menos", "mas",
    "huespedes", "nombre", "email", "telefono", "mensaje", "sitio", "acepta", "form-error", "m-total", "m-noches",
    "enviar-movil", "exito", "codigo", "exito-texto"];
  for (const id of ids) assert.match(html["reserva.html"], new RegExp(`\\sid="${id}"`), `falta #${id}`);
  for (const clase of ["reserva", "barra-movil"]) assert.match(html["reserva.html"], new RegExp(`class="${clase}"`));
  // las flechas van antes de los días (orden de tabulación) y los dos botones de envío apuntan al formulario
  const r = html["reserva.html"];
  assert.ok(r.indexOf('id="mes-sig"') < r.indexOf('id="meses"'));
  for (const id of ["enviar", "enviar-movil"]) {
    const b = (r.match(new RegExp(`<button[^>]*id="${id}"[^>]*>`)) || [])[0];
    assert.match(b, /type="submit"/);
    assert.match(b, /form="formulario"/);
    assert.match(b, /aria-disabled="true"/);
    assert.doesNotMatch(b, /\sdisabled/);
  }
  // orden del DOM de la retícula: calendario, resumen, qué pasa después, formulario
  const orden = ['id="calendario"', 'class="resumen"', 'class="despues"', 'id="formulario"'].map((x) => r.indexOf(x));
  assert.deepEqual([...orden].sort((a, b) => a - b), orden);
});

// semilla de public.contenido: ('clave', 'valor', 'tipo', …)
const SEMILLA = new Map([...readFileSync(join(WEB, "supabase", "migrations", "0003_gestion.sql"), "utf8")
  .matchAll(/\(\s*'([a-z0-9_.-]+)',\s*'((?:[^']|'')*)',\s*'(texto|parrafo|precio)'/g)].map((m) => [m[1], m[2].replace(/''/g, "'")]));

test("contenido editable: claves de la semilla, respaldo idéntico y los 7 grupos de fotos", () => {
  const s = html["index.html"];
  const usados = [...s.matchAll(/<([a-z0-9]+)[^>]*\sdata-contenido="([^"]+)"[^>]*>([^<]*)</g)];
  assert.ok(usados.length >= 18, `solo ${usados.length} data-contenido`);
  for (const [, , clave, texto] of usados) {
    assert.ok(SEMILLA.has(clave), `«${clave}» no está en la semilla de 0003_gestion.sql`);
    assert.equal(texto, SEMILLA.get(clave), `el respaldo de «${clave}» no es el de la semilla`);
  }
  for (const espacio of ["living", "cocina", "dorm1", "dorm2", "banos", "balcon", "recibidor"]) {
    const m = s.match(new RegExp(`<figure class="fotos" data-fotos="${espacio}"><div class="fotos-grid"><div class="foto"><picture>`));
    assert.ok(m, `falta figure.fotos[data-fotos=${espacio}] > .fotos-grid > .foto > picture`);
  }
  assert.match(html["reserva.html"], /data-fotos="living"/);
  // ningún precio escrito fuera de [data-precio]
  const sinPrecios = s.replace(/<span[^>]*data-precio="[^"]+"[^>]*>[^<]*<\/span>/g, "");
  assert.doesNotMatch(textoVisible(sinPrecios), /CLP/);
  for (const p of ["index.html", "reserva.html"]) assert.match(html[p], /<script type="module" src="js\/contenido-publico\.js"><\/script>/);
});

test("imágenes con width y height, srcset con sizes y el hero con fetchpriority alta", () => {
  for (const [p, s] of Object.entries(html)) {
    for (const [img] of s.matchAll(/<img\s[^>]*>/g)) {
      assert.ok(atributo(img, "width") && atributo(img, "height"), `${p}: ${img} sin width/height`);
    }
    for (const [etq] of s.matchAll(/<(?:img|source)\s[^>]*srcset="[^"]*\d+w[^"]*"[^>]*>/g)) {
      assert.ok(atributo(etq, "sizes"), `${p}: ${etq} con descriptores w pero sin sizes`);
    }
  }
  const hero = (html["index.html"].match(/<img class="hero-img"[^>]*>/) || [])[0];
  assert.match(hero, /fetchpriority="high"/);
  assert.doesNotMatch(hero, /loading="lazy"/);
  for (const m of ["ladrillo", "concreto", "roble", "cuero", "acero"]) {
    for (const ext of ["jpg", "webp"]) assert.ok(existsSync(join(SRC, "img", `material-${m}-360.${ext}`)), `falta material-${m}-360.${ext}`);
  }
});

test("fuentes: todas las de tokens.css existen y no queda ninguna sin uso", () => {
  const urls = [...css["tokens.css"].matchAll(/url\("\.\.\/fonts\/([^"]+)"\)/g)].map((m) => m[1]).sort();
  const archivos = readdirSync(join(SRC, "fonts")).filter((f) => f.endsWith(".woff2")).sort();
  assert.deepEqual(archivos, urls);
  assert.ok(urls.includes("fraunces-var.woff2") && urls.includes("fraunces-var-italic.woff2"));
  assert.doesNotMatch(css["tokens.css"], /Newsreader/);
  for (const nombre of ["--papel", "--papel-2", "--tarjeta", "--tinta", "--tinta-2", "--linea", "--acento", "--acento-2",
    "--salvia", "--error", "--radio", "--sombra", "--f-titulo", "--f-texto"]) {
    assert.match(css["tokens.css"], new RegExp(`\\s${nombre}:`), `tokens.css perdió ${nombre} (lo usan el tour y el portal)`);
  }
});
