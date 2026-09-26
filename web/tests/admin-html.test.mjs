// Revisión estática del portal (web/src/admin): lo que exige la CSP 'self' del build y las reglas de seguridad del
// pedido (sin scripts en línea, nada de innerHTML, sin localStorage, enlaces e imports que existen).
//   cd web && npm test
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const ADMIN = resolve(dirname(fileURLToPath(import.meta.url)), "../src/admin");
const html = readFileSync(join(ADMIN, "index.html"), "utf8");
const css = readFileSync(join(ADMIN, "admin.css"), "utf8");
const modulos = readdirSync(join(ADMIN, "js")).filter((f) => f.endsWith(".js"));
const fuentes = Object.fromEntries(modulos.map((f) => [f, readFileSync(join(ADMIN, "js", f), "utf8")]));

test("index.html: meta charset exacto (el build cuelga ahí la CSP), noindex y sin scripts en línea", () => {
  assert.equal(html.split('<meta charset="utf-8">').length - 1, 1);
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
  assert.ok(scripts.length >= 1);
  for (const [, atributos, cuerpo] of scripts) {
    assert.match(atributos, /\bsrc="[^"]+"/, "todo script con src");
    assert.match(atributos, /\btype="module"/);
    assert.equal(cuerpo.trim(), "", "sin código en línea");
  }
  assert.doesNotMatch(html, /\son[a-z]+\s*=/i, "sin manejadores en línea (onclick=…)");
  assert.doesNotMatch(html, /javascript:/i);
  assert.doesNotMatch(html, /https?:\/\//, "nada externo: ni CDN ni fuentes remotas");
  assert.match(html, /<html lang="es">/);
});

test("index.html: los ids que usan los módulos existen y los enlaces locales apuntan a archivos reales", () => {
  const ids = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));
  const usados = new Set();
  for (const s of Object.values(fuentes)) {
    for (const m of s.matchAll(/(?:querySelector|\$)\("#([a-z0-9-]+)"\)/g)) usados.add(m[1]);
    for (const m of s.matchAll(/getElementById\("([a-z0-9-]+)"\)/g)) usados.add(m[1]);
  }
  const faltan = [...usados].filter((id) => !ids.has(id) && !["nota-interna"].includes(id));   // nota-interna la crea JS
  assert.deepEqual(faltan, []);
  for (const [, ref] of html.matchAll(/\b(?:src|href)="([^"#][^"]*)"/g)) {
    const destino = resolve(ADMIN, ref.endsWith("/") ? ref + "index.html" : ref);
    assert.ok(existsSync(destino), `falta ${ref}`);
  }
});

test("módulos: nunca innerHTML ni equivalentes, ni eval, ni localStorage", () => {
  for (const [f, s] of Object.entries(fuentes)) {
    const codigo = s.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
    assert.doesNotMatch(codigo, /\.innerHTML\s*=|\.outerHTML\s*=|insertAdjacentHTML|document\.write|createContextualFragment/, f);
    assert.doesNotMatch(codigo, /\beval\s*\(|new Function\s*\(/, f);
    assert.doesNotMatch(codigo, /localStorage/, f);
    assert.doesNotMatch(codigo, /https?:\/\/(?!www\.w3\.org\/2000\/svg)/, `${f}: sin URL fijas (salen de config.js)`);
  }
});

test("módulos: los imports relativos existen (config.js sólo por import dinámico, porque en src no existe)", () => {
  for (const [f, s] of Object.entries(fuentes)) {
    for (const [, ruta] of s.matchAll(/^\s*import\s[^"']*["']([^"']+)["']/gm)) {
      assert.ok(ruta.startsWith("."), `${f}: import sin ruta relativa (${ruta})`);
      assert.ok(existsSync(resolve(ADMIN, "js", ruta)), `${f}: no existe ${ruta}`);
    }
  }
  assert.match(fuentes["app.js"], /await import\("\.\.\/\.\.\/js\/config\.js"\)/);
  assert.ok(!Object.values(fuentes).some((s) => /^\s*import\s[^;]*config\.js/m.test(s)), "config.js nunca como import estático");
});

test("admin.css: usa los tokens del sitio con respaldo, foco visible y base para teléfono", () => {
  assert.match(css, /@import url\("\.\.\/css\/tokens\.css"\)/);
  assert.ok(existsSync(resolve(ADMIN, "../css/tokens.css")));
  assert.match(css, /var\(--papel, #F7F4EF\)/);
  assert.match(css, /:focus-visible\s*\{[^}]*outline/);
  assert.match(css, /@media \(min-width: 900px\)/);
  assert.doesNotMatch(css, /https?:\/\//);
});
