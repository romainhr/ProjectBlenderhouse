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

test("index.html: el portal sigue sólo en español (sin marcas de traducción del sitio público) y explica los idiomas", () => {
  assert.match(html, /<html lang="es">/);
  assert.doesNotMatch(html, /data-i18n/, "el build traduce sólo el sitio público; /admin no se genera en /en/ ni /fr/");
  for (const s of Object.values(fuentes)) assert.doesNotMatch(s, /data-i18n/);
  const ayuda = (html.match(/<section id="vista-textos"[\s\S]*?<\/section>/) || [""])[0].replace(/\s+/g, " ");
  assert.match(ayuda, /el español es obligatorio/);
  assert.match(ayuda, /el inglés y el francés son opcionales/);
  assert.match(ayuda, /Si dejas vacío el inglés o el francés, el sitio en ese idioma muestra el texto fijo de la página/);
  // hallazgo P3: la traducción fija depende del marcado data-i18n de cada página (PR posterior); sin él, /en/ y /fr/
  // muestran el español, y la ayuda no debe prometer una traducción que el sitio todavía no tiene
  assert.match(ayuda, /mientras esa página no esté traducida, el original en español/);
  assert.doesNotMatch(ayuda, /muestra su traducción fija/);
  assert.match(ayuda, /si cambias el español, escribe también el inglés y el francés/, "la fija no sigue al español editado");
  assert.match(ayuda, /Los precios no se traducen/);
  assert.match(css, /\.aviso-linea\[data-tipo="aviso"\]/, "el aviso de la 0005 tiene estilo propio");
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
  // las imágenes de ../img/<nombre>-<ancho>.<jpg|webp> las genera web/build.py desde web/renders_png/ (no están en src)
  const RENDERS = resolve(ADMIN, "../../renders_png");
  const DE_RENDER = { living: "Living", "living-sofa": "Living_Sofa", cocina: "Cocina", dorm1: "Dorm1", dorm2: "Dorm2",
    bano: "Bano1_Vanitorio", balcon: "Balcon", recibidor: "Hall_Recibidor", maqueta: "Maqueta" };   // build.py, IMAGENES
  const refs = [...html.matchAll(/\b(?:src|href)="([^"#][^"]*)"/g)].map((m) => m[1])
    .concat([...html.matchAll(/\bsrcset="([^"]+)"/g)].flatMap((m) => m[1].split(",").map((p) => p.trim().split(/\s+/)[0])));
  for (const ref of refs) {
    const generada = ref.match(/^\.\.\/img\/([a-z0-9-]+)-(?:800|1600)\.(?:jpg|webp)$/);
    if (generada) {
      assert.ok(DE_RENDER[generada[1]] && existsSync(join(RENDERS, `${DE_RENDER[generada[1]]}.png`)),
        `${ref}: build.py no la genera (falta su render en web/renders_png)`);
      continue;
    }
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

test("admin.css: las regiones vivas no se ocultan con display:none, ni vacías ni en teléfono (H7)", () => {
  // clases de los elementos con role=status/alert o aria-live, en index.html y en los módulos (el(…, { clase, role }))
  const vivas = new Set();
  for (const [etiqueta] of html.matchAll(/<[a-z]+\b[^>]*>/g)) {
    if (!/\brole="(status|alert)"|\baria-live=/.test(etiqueta)) continue;
    const c = etiqueta.match(/\bclass="([^"]+)"/);
    if (c) c[1].split(/\s+/).forEach((x) => vivas.add(x));
  }
  for (const s of Object.values(fuentes)) {
    for (const [, props] of s.matchAll(/el\("[a-z]+", \{([^}]*)\}/g)) {
      if (!/role: "(status|alert)"|"aria-live"/.test(props)) continue;
      const c = props.match(/clase: "([^"]+)"/);
      if (c) c[1].split(/\s+/).forEach((x) => vivas.add(x));
    }
  }
  for (const c of ["aviso-linea", "indicador", "aviso-accion", "error"]) assert.ok(vivas.has(c), `${c} es región viva`);
  const idsVivos = [...html.matchAll(/<[a-z]+\b[^>]*\bid="([^"]+)"[^>]*\b(?:role="(?:status|alert)"|aria-live=)[^>]*>/g)].map((m) => m[1]);
  assert.ok(idsVivos.includes("reservas-aviso"));
  // reglas con display:none (también dentro de @media): ningún selector puede apuntar a una región viva
  const malas = [];
  for (const [, selectores, cuerpo] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!/display:\s*none/.test(cuerpo)) continue;
    for (const sel of selectores.split(",").map((x) => x.trim())) {
      const ultimo = sel.split(/\s+/).at(-1);
      const clase = ultimo.match(/^\.([a-z0-9-]+)(?::empty)?$/);
      const id = ultimo.match(/^#([a-z0-9-]+)$/);
      if ((clase && vivas.has(clase[1])) || (id && idsVivos.includes(id[1]))) malas.push(sel);
    }
  }
  assert.deepEqual(malas, []);
  // vacías salen del flujo (no dejan hueco ni «gap»), pero quedan en el árbol de accesibilidad
  assert.match(css, /\.aviso-linea:empty, \.indicador:empty, \.aviso-accion:empty, \.error:empty \{[^}]*position: absolute/);
});

test("vistas: usan las decisiones puras de admin-vistas.test.mjs (H1-H3, H5, H6, H8-H10) y el aviso estable de la nota (H7)", () => {
  const r = fuentes["vista-reservas.js"], f = fuentes["vista-fotos.js"], t = fuentes["vista-textos.js"], a = fuentes["app.js"];
  assert.match(r, /decidirApertura\(\{ id, seleccion, notaSucia \}\)/, "H1: abrir() decide con decidirApertura");
  assert.match(r, /resolverSeleccion\(reservas, seleccion, notaSucia\)/, "H9: pintarDetalle() usa resolverSeleccion");
  assert.match(a, /addEventListener\("hashchange", \(\) => \{\s*if \(vistaDeHash\(location\.hash\)\) enrutar\(\);/,
    "H2: hashchange sólo enruta con un hash de vista");
  assert.match(a, /cierre\.cerrar\(\(\) => salir\(""\)\)/, "H3: se limpia la pantalla sin esperar al logout");
  assert.doesNotMatch(a, /await api\.cerrarSesion\(\)/, "H3");
  assert.match(a, /await cierre\.esperar\(\);[^\n]*\n\s*await api\.iniciarSesion/, "H3: un ingreso nuevo espera la revocación");
  assert.match(f, /const enviar = unaALaVez\(async \(\) => \{\s*const gen = generacion;\s*n\.boton\.disabled = true;/,
    "H5: un solo envío y el botón bloqueado antes del primer await");
  assert.match(f, /mientras\(botones, \(\) => reordenarFoto\(\{\s*api, fotosEspacio: fotosDeEspacio\(fotos, f\.espacio\)/,
    "H6: botones bloqueados y lista actual");
  assert.match(f, /fotos = aplicarOrden\(fotos, nueva\)/, "H6");
  assert.match(f, /hayCambios: \(\) => [^\n]*borradores\.size > 0/, "H8: las descripciones sin guardar cuentan");
  for (const [nombre, s] of [["reservas", r], ["textos", t], ["fotos", f]]) {
    assert.doesNotMatch(s, /\benCurso\b/, `H10 ${nombre}: sin la variable enCurso sin limpiar`);
    assert.match(s, /mostrar\(\) \{\s*if \(!cargada\) cargaInicial\(\);/, `H10 ${nombre}`);
    assert.match(s, /reiniciar\(\) \{\s*generacion\+\+;\s*cargaInicial\.soltar\(\);/, `H10 ${nombre}`);
  }
  assert.match(r, /anunciar\(estado, aviso, "ok"\);\s*area\.focus\(\);/,
    "H7: «Nota guardada» va a la región viva que ya estaba en la página");
});
