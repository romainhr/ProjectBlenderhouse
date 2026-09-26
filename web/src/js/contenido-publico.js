// Contenido editable del sitio público: textos, precios y fotos que el propietario cambia desde el portal de gestión.
//
// Uso en cada página: <script type="module" src="js/contenido-publico.js"></script>
//   * [data-contenido="clave"]  -> textContent con el texto de public.contenido en el idioma de la página (IDIOMA de
//                                  i18n.js): columna valor en español, valor_en en inglés y valor_fr en francés. Si la
//                                  del idioma viene vacía o no existe (antes de la migración que las agrega), queda el
//                                  texto estático, que el build ya tradujo. Tipo «precio»: siempre la columna valor (el
//                                  monto no depende del idioma), escrito en CLP con el LOCALE del idioma.
//   * [data-precio="noche"|"limpieza"] (los que ya rellena sitio.js con TARIFA) -> el precio editado, si lo hay
//                                  (claves tarifa.noche y tarifa.limpieza de la semilla de 0003_gestion.sql). Si hay
//                                  alguno editado, se reescriben todas las tarifas con el LOCALE del idioma (la no
//                                  editada, con su valor de ejemplo), así la tabla no mezcla formatos. Además fija
//                                  esas tarifas en reserva-logica.js (fijarTarifas), para que el total estimado se
//                                  calcule con los mismos precios que muestra la tabla.
//   * [data-fotos="espacio"]    -> la primera foto visible de ese espacio reemplaza la imagen principal (el primer
//                                  <img>): conserva width, height, las clases y la carga diferida, usa el alt de la
//                                  foto y pone la URL de la foto en el srcset del <img> (si lo tenía) y en cada
//                                  <source> de su <picture>, para que no gane la imagen estática. Con data-galeria,
//                                  las demás van como miniaturas (<ul class="miniaturas">) que se intercambian con la
//                                  principal al tocarlas.
// Sólo se aceptan fotos del bucket público propio: https://<proyecto>.supabase.co/storage/v1/object/public/fotos/…
// con cada segmento de la ruta codificado (urlFotoValida).
// Si falta la configuración (js/config.js lo genera web/build.py), si las tablas no existen todavía (migración 0003)
// o si la red falla o tarda más de TIEMPO_MAX_MS, no se toca nada: quedan el texto y las imágenes estáticas del HTML.
// Lee sólo con la clave PÚBLICA (GET, sin sesión). Todo lo que viene de la base se inserta con textContent o con
// atributos (setAttribute), nunca con innerHTML. Los textos propios del módulo (alt de respaldo y etiquetas de las
// miniaturas) salen de t() de i18n.js: claves js.contenido.* de web/src/i18n/*.json. Se resuelven al aplicar, no al
// leer la base: las lecturas no esperan al diccionario del idioma (ver el final del archivo).
// La lógica sin red está separada en funciones puras (pruebas: web/tests/contenido-publico.test.mjs, `npm test`).
import { PRECIO_MAX, TARIFA, clp, fijarTarifas } from "./reserva-logica.js";
import { IDIOMA, IDIOMAS, listo, localeDe, t } from "./i18n.js";

// Supuesto: 4 s bastan para dos lecturas pequeñas; pasado ese plazo se queda el contenido estático (sin reintentos).
export const TIEMPO_MAX_MS = 4000;
// Bucket PÚBLICO de Storage donde el portal sube las fotos (lo crea la migración 0003). `fotos.ruta` es la ruta del
// objeto DENTRO de este bucket (sin el nombre del bucket ni «/» inicial).
export const BUCKET_FOTOS = "fotos";
// Claves de public.contenido con las tarifas (valor: pesos chilenos enteros, sólo dígitos).
export const CLAVES_TARIFA = Object.freeze({ noche: "tarifa.noche", limpieza: "tarifa.limpieza" });  // 0003_gestion.sql, semilla de public.contenido
// Columna de public.contenido con el texto de cada idioma. valor_en y valor_fr las agrega una migración posterior a la
// 0004; mientras no existan, la lectura con select=* simplemente no las trae.
export const CAMPOS_VALOR = Object.freeze({ es: "valor", en: "valor_en", fr: "valor_fr" });
// Supuesto: texto alternativo si el propietario no escribió uno (mejor que dejar la foto sin descripción).
export const CLAVE_ALT_GENERICO = "js.contenido.alt_generico";
// Supuesto: máximo de miniaturas por galería (evita cargar decenas de imágenes en el teléfono).
export const MAX_MINIATURAS = 12;

const RE_CLAVE = /^[a-z0-9_.-]{1,64}$/;          // claves en minúsculas, como «tarifa.noche» o «hero.bajada»
const RE_ESPACIO = /^[a-z0-9_-]{1,40}$/;         // supuesto: espacios como «living», «dorm1», «bano»
const RE_ENTERO = /^\d{1,9}$/;
const RE_CONTROL = /[\u0000-\u001f\u007f\\]/;
// El mismo formato que web/build.py exige a SUPABASE_URL (RE_SUPABASE): https://<proyecto>.supabase.co
const RE_PROYECTO = /^https:\/\/[a-z0-9]{10,40}\.supabase\.co$/;
const CAMINO_PUBLICO = `/storage/v1/object/public/${BUCKET_FOTOS}/`;

// ---------------------------------------------------------------- lógica pura (sin DOM ni red)

/** Texto alternativo de respaldo en el idioma de la página. */
export function altGenerico() {
  return t(CLAVE_ALT_GENERICO);
}

const esValor = (v) => typeof v === "string" || (typeof v === "number" && Number.isFinite(v));

/** Filas de public.contenido -> Map clave -> { valor, tipo, valor_en?, valor_fr? }. Descarta filas mal formadas (sin
 *  clave válida o sin `valor`, que es obligatorio en la tabla); las traducciones van sólo si son texto o número. */
export function indexarContenido(filas) {
  const mapa = new Map();
  if (!Array.isArray(filas)) return mapa;
  for (const f of filas) {
    if (!f || typeof f.clave !== "string" || !RE_CLAVE.test(f.clave) || !esValor(f.valor)) continue;
    const entrada = { valor: f.valor, tipo: typeof f.tipo === "string" ? f.tipo : "texto" };
    for (const campo of [CAMPOS_VALOR.en, CAMPOS_VALOR.fr]) if (esValor(f[campo])) entrada[campo] = f[campo];
    mapa.set(f.clave, entrada);
  }
  return mapa;
}

/** Precio entero en CLP (número o texto de sólo dígitos) de 0 a PRECIO_MAX, como el CHECK de 0003 -> número, o null. */
export function precioValido(valor) {
  const n = typeof valor === "number" ? valor : typeof valor === "string" && RE_ENTERO.test(valor.trim()) ? Number(valor.trim()) : NaN;
  return Number.isSafeInteger(n) && n >= 0 && n <= PRECIO_MAX ? n : null;
}

/** Texto a mostrar para una entrada de contenido en `idioma`, o null si hay que dejar el estático: el del idioma vacío
 *  o sin columna (nunca se cae al español en una página en otro idioma) o un precio inválido. Un precio usa `valor`
 *  y el formato del idioma (CLP 65.000, CLP 65,000, CLP 65 000). */
export function textoContenido(entrada, idioma = IDIOMA) {
  if (!entrada) return null;
  if (entrada.tipo === "precio") {
    const n = precioValido(entrada.valor);
    return n === null ? null : clp(n, localeDe(idioma));
  }
  const campo = IDIOMAS.includes(idioma) ? CAMPOS_VALOR[idioma] : CAMPOS_VALOR.es;
  const v = entrada[campo];
  if (!esValor(v)) return null;
  const s = String(v);
  return s.trim() ? s : null;
}

/** Tarifas editadas y válidas -> { noche?, limpieza? }. La noche en 0 no cuenta como editada (no hay estadía gratis):
 *  queda la de ejemplo. La limpieza sí puede ser 0 (sin cobro). */
function tarifasEditadas(contenido) {
  const t = Object.create(null);                   // sin prototipo: t["toString"] no existe
  for (const [k, clave] of Object.entries(CLAVES_TARIFA)) {
    const v = precioValido(contenido.get(clave)?.valor);
    if (v !== null && !(k === "noche" && v === 0)) t[k] = v;
  }
  return t;
}

/** Tarifas editadas -> { noche, limpieza } (la que falte queda con el valor de ejemplo de TARIFA) o null si no hay. */
export function tarifasDe(contenido) {
  if (!(contenido instanceof Map)) return null;
  const t = tarifasEditadas(contenido);
  if (t.noche === undefined && t.limpieza === undefined) return null;
  return { noche: t.noche ?? TARIFA.noche, limpieza: t.limpieza ?? TARIFA.limpieza };
}

/** ¿Es `ruta` una ruta de objeto segura dentro del bucket? (sin «..», «.», segmentos vacíos, «\» ni controles) */
export function rutaValida(ruta) {
  if (typeof ruta !== "string" || !ruta || ruta.length > 512 || RE_CONTROL.test(ruta)) return false;
  return ruta.split("/").every((s) => s !== "" && s !== "." && s !== "..");
}

/** `base` -> https://<proyecto>.supabase.co sin «/» final, o null si no tiene esa forma. */
function baseProyecto(base) {
  if (typeof base !== "string") return null;
  const b = base.trim().replace(/\/+$/, "");
  return RE_PROYECTO.test(b) ? b : null;
}

/** URL pública de una foto: {base}/storage/v1/object/public/fotos/{ruta con cada segmento codificado}, o null. */
export function urlPublica(base, ruta) {
  const b = baseProyecto(base);
  if (!b || !rutaValida(ruta)) return null;
  return b + CAMINO_PUBLICO + ruta.split("/").map(encodeURIComponent).join("/");
}

/** ¿Es `url` exactamente la URL pública de un objeto del bucket «fotos» de un proyecto Supabase (y, si se da `base`,
 *  de ese proyecto), con cada segmento codificado de forma canónica? Así no pasan otro sitio, otro bucket, http,
 *  «?», «#», «..» codificados, espacios ni comas (la URL sirve tal cual como único candidato de un srcset). */
export function urlFotoValida(url, base) {
  if (typeof url !== "string") return false;
  const i = url.indexOf(CAMINO_PUBLICO);
  if (i < 0) return false;
  const origen = url.slice(0, i);
  if (!RE_PROYECTO.test(origen)) return false;
  if (base !== undefined && origen !== baseProyecto(base)) return false;
  let ruta;
  try {
    ruta = decodeURIComponent(url.slice(i + CAMINO_PUBLICO.length));
  } catch {
    return false;                                  // «%» suelto o secuencia inválida
  }
  return urlPublica(origen, ruta) === url;
}

/** Filas de public.fotos -> Map espacio -> [{ url, alt, orden }] en orden ascendente. Descarta filas mal formadas.
 *  Sin alt escrito por el propietario, `alt` queda "": el de respaldo (altGenerico) se pone al aplicar, en el idioma
 *  que ya tenga t() entonces. */
export function indexarFotos(filas, base) {
  const mapa = new Map();
  if (!Array.isArray(filas)) return mapa;
  filas.forEach((f, i) => {
    if (!f || typeof f.espacio !== "string" || !RE_ESPACIO.test(f.espacio)) return;
    const url = urlPublica(base, f.ruta);
    if (!url) return;
    const alt = typeof f.alt === "string" ? f.alt.trim() : "";
    const orden = Number.isFinite(f.orden) ? f.orden : Number.MAX_SAFE_INTEGER;
    if (!mapa.has(f.espacio)) mapa.set(f.espacio, []);
    mapa.get(f.espacio).push({ url, alt, orden, i });
  });
  for (const lista of mapa.values()) {
    lista.sort((a, b) => a.orden - b.orden || a.i - b.i);    // estable: a igual orden, el de la base
    for (const f of lista) delete f.i;
  }
  return mapa;
}

/** Cabeceras de lectura con la clave pública (igual que reservas-api.js: Bearer sólo con la clave «anon» antigua). */
export function cabecerasPublicas(clave) {
  const h = { apikey: clave, Accept: "application/json" };
  if (!clave.startsWith("sb_publishable_")) h.Authorization = `Bearer ${clave}`;
  return h;
}

// ---------------------------------------------------------------- aplicar al DOM (recibe la raíz: document o un falso)

const TARIFA_DE_CLAVE = new Map(Object.entries(CLAVES_TARIFA).map(([k, clave]) => [clave, k]));

/** [data-contenido] y [data-precio] -> textContent en `idioma` (por defecto, el de la página). Devuelve cuántos
 *  elementos cambió. Sin tarifas editadas, los precios quedan como los escribió sitio.js. Con alguna editada, todas
 *  las tarifas se escriben con el locale del idioma (la no editada, con su valor de ejemplo de TARIFA): si no, en
 *  /en/ se veían «CLP 70,000» (editada) y «CLP 15.000» (la de sitio.js) en la misma tabla (hallazgo JS-4). */
export function aplicarContenido(raiz, contenido, idioma = IDIOMA) {
  if (!(contenido instanceof Map) || !contenido.size) return 0;
  const locale = localeDe(idioma);
  const precios = tarifasDe(contenido);             // null si ninguna está editada (la noche > 0, como en tarifasDe)
  let n = 0;
  for (const el of raiz.querySelectorAll("[data-contenido]")) {
    const clave = el.getAttribute("data-contenido");
    const k = TARIFA_DE_CLAVE.get(clave);           // una tarifa sigue la misma regla que [data-precio]
    const texto = k ? (precios ? clp(precios[k], locale) : null) : textoContenido(contenido.get(clave), idioma);
    if (texto !== null) { el.textContent = texto; n++; }
  }
  if (precios) {
    for (const el of raiz.querySelectorAll("[data-precio]")) {
      const k = el.getAttribute("data-precio");
      if (Object.hasOwn(CLAVES_TARIFA, k)) { el.textContent = clp(precios[k], locale); n++; }
    }
  }
  return n;
}

const originales = new WeakMap();                 // img -> estado estático, para restaurarlo si la foto no carga
const ATRIBUTOS_IMG = ["src", "srcset", "sizes", "alt"];
const ATRIBUTOS_SOURCE = ["srcset", "sizes", "type"];

function esEtiqueta(el, nombre) {
  return Boolean(el && typeof el.tagName === "string" && el.tagName.toUpperCase() === nombre);
}

function atributo(el, nombre, valor) {
  if (valor === null || valor === undefined) el.removeAttribute(nombre);
  else el.setAttribute(nombre, valor);
}

const leerAtributos = (el, nombres) => Object.fromEntries(nombres.map((a) => [a, el.getAttribute(a)]));

/** Vuelve a la imagen estática. Sólo una vez por reemplazo: si la estática también falla, su `error` no repite esto. */
function restaurar(img) {
  const o = originales.get(img);
  if (!o?.activa) return;
  o.activa = false;
  for (const f of o.fuentes) for (const a of ATRIBUTOS_SOURCE) atributo(f.el, a, f.atributos[a]);
  for (const a of ATRIBUTOS_IMG) atributo(img, a, o.atributos[a]);
  o.lista?.remove();
  o.lista = null;
}

/** Pone `foto` en el <img> y en cada <source> del <picture>. No toca width, height, class ni loading. */
function ponerFoto(img, o, foto) {
  for (const f of o.fuentes) {
    f.el.setAttribute("srcset", foto.url);         // URL canónica: sin espacios ni comas, un solo candidato
    f.el.removeAttribute("sizes");
    f.el.removeAttribute("type");                  // el tipo era el del archivo estático (p. ej. WebP), no el de la foto
  }
  if (o.atributos.srcset !== null) img.setAttribute("srcset", foto.url);
  img.removeAttribute("sizes");
  img.setAttribute("src", foto.url);
  img.setAttribute("alt", foto.alt);
}

/** Reemplaza la imagen principal por `foto`; si la foto no carga, vuelve a la imagen estática. */
function reemplazarPrincipal(img, foto) {
  let o = originales.get(img);
  if (!o) {
    const picture = esEtiqueta(img.parentElement, "PICTURE") ? img.parentElement : null;
    o = {
      picture,
      fuentes: (picture ? [...picture.children] : []).filter((c) => esEtiqueta(c, "SOURCE"))
        .map((el) => ({ el, atributos: leerAtributos(el, ATRIBUTOS_SOURCE) })),
      atributos: leerAtributos(img, ATRIBUTOS_IMG),
      lista: null,
      activa: false,
    };
    originales.set(img, o);
    img.addEventListener("error", () => restaurar(img));
  }
  o.activa = true;
  ponerFoto(img, o, foto);
  return o;
}

/** Miniaturas de las demás fotos: botones que intercambian su foto con la principal. */
function crearMiniaturas(doc, img, o, principal, resto) {
  const lista = doc.createElement("ul");
  lista.className = "miniaturas";
  lista.setAttribute("data-miniaturas", "");
  lista.setAttribute("aria-label", t("js.contenido.mas_fotos"));
  const estado = { principal };
  for (const inicial of resto.slice(0, MAX_MINIATURAS)) {
    let actual = inicial;
    const li = doc.createElement("li");
    const boton = doc.createElement("button");
    boton.setAttribute("type", "button");
    const mini = doc.createElement("img");
    mini.setAttribute("alt", "");                  // el nombre accesible lo da el botón
    mini.setAttribute("loading", "lazy");
    mini.setAttribute("decoding", "async");
    const pintar = () => {
      mini.setAttribute("src", actual.url);
      boton.setAttribute("aria-label", t("js.contenido.ver_foto", { alt: actual.alt }));
    };
    pintar();
    mini.addEventListener("error", () => li.remove());
    boton.addEventListener("click", () => {
      if (!o.activa) return;                       // ya se volvió a la estática
      [estado.principal, actual] = [actual, estado.principal];
      ponerFoto(img, o, estado.principal);
      pintar();
    });
    boton.append(mini);
    li.append(boton);
    lista.append(li);
  }
  return lista;
}

/** Las fotos de una lista que se pueden mostrar: URL del bucket propio (urlFotoValida) y alt de texto. */
function fotosAceptables(lista, base) {
  if (!Array.isArray(lista)) return [];
  return lista.filter((f) => f && urlFotoValida(f.url, base))
    .map((f) => ({ url: f.url, alt: typeof f.alt === "string" && f.alt.trim() ? f.alt.trim() : altGenerico() }));
}

/** [data-fotos] -> foto principal y, con data-galeria, miniaturas. Devuelve cuántos contenedores cambió.
 *  Con `base` (lo que usa aplicar), sólo se aceptan fotos de ese proyecto. */
export function aplicarFotos(raiz, fotos, { doc = raiz.ownerDocument || raiz, base } = {}) {
  if (!(fotos instanceof Map) || !fotos.size) return 0;
  let n = 0;
  for (const cont of raiz.querySelectorAll("[data-fotos]")) {
    const lista = fotosAceptables(fotos.get(cont.getAttribute("data-fotos")), base);
    const img = cont.querySelector("img");
    if (!lista.length || !img) continue;
    const [primera, ...resto] = lista;
    const o = reemplazarPrincipal(img, primera);
    o.lista?.remove();                             // idempotente: una sola galería por contenedor
    o.lista = null;
    if (cont.hasAttribute("data-galeria") && resto.length) {
      o.lista = crearMiniaturas(doc, img, o, primera, resto);
      (o.picture || img).after(o.lista);
    }
    n++;
  }
  return n;
}

/** Aplica todo lo leído en `idioma` (por defecto, el de la página). `d` es lo que devuelve obtenerDatos (o null: no
 *  hace nada). */
export function aplicar(raiz, d, idioma = IDIOMA) {
  if (!d) return { textos: 0, fotos: 0 };
  return { textos: aplicarContenido(raiz, d.contenido, idioma), fotos: aplicarFotos(raiz, d.fotos, { base: d.base }) };
}

// ---------------------------------------------------------------- red (una lectura por página, sin reintentos)

/** GET a PostgREST con plazo; devuelve el arreglo de filas o null ante cualquier error (tabla inexistente, red, plazo). */
export async function leerFilas(base, clave, ruta, { fetch: f = globalThis.fetch, tiempo = TIEMPO_MAX_MS } = {}) {
  if (typeof f !== "function") return null;
  const ctrl = new AbortController();
  const reloj = setTimeout(() => ctrl.abort(), tiempo);
  try {
    const r = await f(`${base}/rest/v1/${ruta}`, { headers: cabecerasPublicas(clave), signal: ctrl.signal });
    if (!r.ok) return null;
    const d = await r.json();                      // el cuerpo también queda bajo el plazo (misma señal)
    return Array.isArray(d) ? d : null;
  } catch {
    return null;
  } finally {
    clearTimeout(reloj);
  }
}

// select=* y no la lista de columnas: funciona antes y después de la migración que agrega valor_en y valor_fr (pedir
// una columna que no existe haría fallar la lectura entera). La tabla es de lectura pública (contenido_publico_lee).
export const RUTA_CONTENIDO = "contenido?select=*";
export const RUTA_FOTOS = "fotos?select=espacio,ruta,alt,orden&visible=eq.true&order=orden.asc";

/** Configuración pública -> { contenido: Map, fotos: Map, base } (vacíos si algo falla), o null sin configuración
 *  (o si la URL no es https://<proyecto>.supabase.co, la misma regla del build). */
export async function obtenerDatos({ config, fetch, tiempo } = {}) {
  const base = baseProyecto(config?.url);
  const clave = typeof config?.clave === "string" ? config.clave.trim() : "";
  if (!base || !clave) return null;
  const op = { fetch, tiempo };
  const [filasContenido, filasFotos] = await Promise.all([
    leerFilas(base, clave, RUTA_CONTENIDO, op),
    leerFilas(base, clave, RUTA_FOTOS, op),
  ]);
  return { contenido: indexarContenido(filasContenido), fotos: indexarFotos(filasFotos, base), base };
}

/** js/config.js lo genera el build; si no existe (p. ej. sirviendo src/), no hay configuración. */
async function cargarConfig() {
  try {
    const m = await import("./config.js");
    return { url: m.SUPABASE_URL, clave: m.SUPABASE_CLAVE_PUBLICA };
  } catch {
    return null;
  }
}

let pendiente = null;

/** Lo publicado por el propietario, leído una sola vez por página (la misma promesa para todos los que la pidan). */
export function datos() {
  pendiente ??= cargarConfig().then((config) => (config ? obtenerDatos({ config }) : null)).catch(() => null);
  return pendiente;
}

/** Tarifas editadas por el propietario -> { noche, limpieza } en CLP, o null (usar TARIFA, de ejemplo). */
export async function tarifas() {
  const d = await datos();
  return d ? tarifasDe(d.contenido) : null;
}

// Al cargarse en una página (no en Node): las lecturas de la base empiezan enseguida y se aplican cuando lleguen. Ni
// este módulo ni i18n.js tienen await de nivel superior: importarlos no espera ninguna red, así las lecturas no van
// detrás del diccionario del idioma y reserva.js, que importa tarifas(), no se demora por este módulo (hallazgo JS-3).
// Las tarifas se fijan apenas llegan, para que el total estimado que calcule cualquier página (reserva.js) use los
// mismos precios que la tabla. Los textos se aplican después de `listo` de i18n.js: los propios del módulo (alt de
// respaldo, etiquetas de las miniaturas) ya están en el idioma de la página.
if (typeof document !== "undefined") {
  datos().then(async (d) => {
    const precios = d ? tarifasDe(d.contenido) : null;
    if (precios) fijarTarifas(precios);
    await listo;
    aplicar(document, d);
  }).catch(() => {});
}
