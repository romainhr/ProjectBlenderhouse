// Pruebas de web/src/js/reserva-logica.js con el ejecutor incluido en Node (sin dependencias):
//   cd web && npm test     (node --test tests/*.test.mjs)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  CELDA_MIN, CODIGOS, PRECIO_MAX, PREFIJO_MENSAJES, SEPARACION_MESES, TARIFA, VARIABLES_MENSAJES, clp, codigoError,
  diasCortos, esCodigo, esIso, fijarTarifas, grillaMes, hayMesSiguiente, hoyIso, mesesPorPagina, nocheOcupada, noches,
  nombresDias, salidaMaxima, solapa, sumarDias, tarifaVigente, textoMensaje, total, validarDatos, validarRango,
} from "../src/js/reserva-logica.js";
import { crearTraductor, t as tPagina, tn as tnPagina, traducirPlural } from "../src/js/i18n.js";
import { sinComentarios } from "./copia-sitio.mjs";

const HOY = "2026-10-05";
const leer = (ruta) => readFileSync(new URL(ruta, import.meta.url), "utf8");
const DICCIONARIOS = Object.fromEntries(["es", "en", "fr"].map((i) => [i, JSON.parse(leer(`../src/i18n/${i}.json`))]));
// traductor de cada idioma con el respaldo en español, como t() de i18n.js en una página de ese idioma
const T = Object.fromEntries(Object.entries(DICCIONARIOS).map(([i, d]) => [i, crearTraductor(d, DICCIONARIOS.es)]));
const LOCALES = { es: "es-CL", en: "en-US", fr: "fr-FR" };
const OCUPADOS = [{ entrada: "2026-10-10", salida: "2026-10-13" }, { entrada: "2026-10-20", salida: "2026-10-22" }];

test("fechas ISO: válidas, inválidas y aritmética sin corrimiento de huso", () => {
  assert.ok(esIso("2026-02-28"));
  assert.ok(!esIso("2026-02-30"));
  assert.ok(!esIso("26-2-3"));
  assert.equal(sumarDias("2026-12-31", 1), "2027-01-01");
  assert.equal(sumarDias("2026-03-01", -1), "2026-02-28");
  assert.equal(noches("2026-10-10", "2026-10-13"), 3);
  // «hoy» en el huso de la propiedad (America/Santiago, UTC−3 en octubre), no el del visitante ni el UTC
  assert.equal(hoyIso(new Date("2026-10-06T02:30:00Z")), "2026-10-05");   // 23:30 en Chile, ya el 6 en UTC
  assert.equal(hoyIso(new Date("2026-10-06T03:30:00Z")), "2026-10-06");   // 00:30 en Chile
  assert.equal(hoyIso(new Date("2026-06-15T03:30:00Z")), "2026-06-14");   // invierno: UTC−4, 23:30 en Chile
});

test("solape en intervalos semiabiertos: se puede entrar el día que otro sale", () => {
  assert.ok(solapa("2026-10-11", "2026-10-14", "2026-10-10", "2026-10-13"));
  assert.ok(!solapa("2026-10-13", "2026-10-15", "2026-10-10", "2026-10-13"));
  assert.ok(!solapa("2026-10-08", "2026-10-10", "2026-10-10", "2026-10-13"));
  assert.ok(nocheOcupada("2026-10-12", OCUPADOS));
  assert.ok(!nocheOcupada("2026-10-13", OCUPADOS));
});

test("validarRango aplica las mismas reglas que la base de datos", () => {
  assert.deepEqual(validarRango("2026-10-06", "2026-10-09", OCUPADOS, HOY), { ok: true, noches: 3 });
  assert.equal(validarRango("2026-10-04", "2026-10-07", OCUPADOS, HOY).error, "fecha_pasada");
  assert.equal(validarRango("2026-10-06", "2026-10-07", OCUPADOS, HOY).error, "min_noches");
  assert.equal(validarRango("2026-10-06", sumarDias("2026-10-06", 31), [], HOY).error, "max_noches");
  assert.equal(validarRango("2026-10-08", "2026-10-11", OCUPADOS, HOY).error, "fechas_ocupadas");
  assert.equal(validarRango("2026-10-13", "2026-10-15", OCUPADOS, HOY).ok, true);
  assert.equal(validarRango("2027-11-01", "2027-11-04", [], HOY).error, "fecha_lejana");
  assert.equal(validarRango("", "2026-10-09", [], HOY).error, "fechas_requeridas");
});

test("salidaMaxima corta en la próxima llegada o en el máximo de noches", () => {
  assert.equal(salidaMaxima("2026-10-06", OCUPADOS), "2026-10-10");
  assert.equal(salidaMaxima("2026-10-23", OCUPADOS), sumarDias("2026-10-23", TARIFA.maxNoches));
});

test("total y formato en pesos chilenos: es-CL por defecto, en-US y fr-FR con su separador y siempre «CLP»", () => {
  assert.deepEqual(total(3), { noches: 3, alojamiento: 174000, limpieza: 15000, total: 189000 });
  assert.equal(total(0).total, 0);
  assert.equal(clp(189000).replace(/\s/g, " "), "CLP 189.000");
  assert.equal(clp(189000, "es-CL"), clp(189000));                       // el portal lo llama sin locale
  assert.equal(clp(189000, "en-US"), "CLP 189,000");
  assert.match(clp(189000, "fr-FR"), /^CLP 189[\u00a0\u202f ]000$/);      // espacio (fino) de Intl, no punto ni coma
  assert.equal(clp(0, "en-US"), "CLP 0");
  assert.equal(clp(10_000_000, "en-US"), "CLP 10,000,000");
  assert.equal(clp(58000.4, "fr-FR").replace(/\s/g, " "), "CLP 58 000");  // sin decimales
});

test("fijarTarifas: sólo enteros del rango del CHECK de la 0003 y noche mayor que 0; TARIFA no cambia", () => {
  try {
    assert.deepEqual(tarifaVigente(), { noche: TARIFA.noche, limpieza: TARIFA.limpieza });
    assert.equal(PRECIO_MAX, 10_000_000);
    for (const malo of [
      { noche: 0, limpieza: 15000 }, { noche: -1, limpieza: 15000 }, { noche: 1.5, limpieza: 15000 },
      { noche: "70000", limpieza: 15000 }, { noche: NaN, limpieza: 0 }, { noche: PRECIO_MAX + 1, limpieza: 0 },
      { noche: 70000, limpieza: -1 }, { noche: 70000, limpieza: "0" }, { noche: 70000, limpieza: PRECIO_MAX + 1 },
      { noche: 70000 }, { limpieza: 0 }, {}, null, undefined, 70000,
    ]) {
      assert.equal(fijarTarifas(malo), false, `debería rechazar ${JSON.stringify(malo)}`);
      assert.deepEqual(tarifaVigente(), { noche: 58000, limpieza: 15000 }, "un rechazo no cambia nada");
    }
    assert.equal(fijarTarifas({ noche: 70000, limpieza: 0 }), true);      // limpieza sin cobro
    assert.deepEqual(tarifaVigente(), { noche: 70000, limpieza: 0 });
    assert.deepEqual(total(3), { noches: 3, alojamiento: 210000, limpieza: 0, total: 210000 });
    assert.equal(total(0).total, 0);
    assert.deepEqual(total(3, TARIFA), { noches: 3, alojamiento: 174000, limpieza: 15000, total: 189000 });   // pura
    assert.equal(fijarTarifas({ noche: PRECIO_MAX, limpieza: PRECIO_MAX }), true);   // los extremos del CHECK
    assert.throws(() => { tarifaVigente().noche = 1; }, TypeError);            // congelada: no se cambia por fuera
    assert.deepEqual([TARIFA.noche, TARIFA.limpieza], [58000, 15000]);         // los valores por defecto siguen
    assert.ok(Object.isFrozen(TARIFA));
  } finally {
    fijarTarifas(TARIFA);                                                      // vuelve a los de ejemplo
  }
  assert.deepEqual(total(3), { noches: 3, alojamiento: 174000, limpieza: 15000, total: 189000 });
});

test("los mensajes no llevan precios, en ningún idioma: al fijar otras tarifas no quedan desfasados", () => {
  try {
    fijarTarifas({ noche: 70000, limpieza: 0 });
    for (const [idioma, t] of Object.entries(T)) {
      const montos = [TARIFA.noche, TARIFA.limpieza, 70000].map((m) => new Intl.NumberFormat(LOCALES[idioma]).format(m));
      for (const codigo of CODIGOS) {
        const texto = textoMensaje(codigo, t);
        assert.doesNotMatch(texto, /CLP|\$|\d{4,}/, `${idioma}/${codigo} menciona un precio: «${texto}»`);
        for (const m of montos) assert.ok(!texto.includes(m), `${idioma}/${codigo} menciona ${m}: «${texto}»`);
      }
    }
  } finally {
    fijarTarifas(TARIFA);
  }
});

test("mensajes: cada código tiene texto en es, en y fr, sin marcas {…} sin reemplazar", () => {
  assert.equal(new Set(CODIGOS).size, CODIGOS.length);
  assert.ok(Object.isFrozen(CODIGOS));
  for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
    for (const codigo of CODIGOS) {
      const clave = PREFIJO_MENSAJES + codigo;
      assert.equal(typeof d[clave], "string", `${idioma}.json no tiene ${clave}`);
      assert.ok(d[clave].trim(), `${idioma}.json: ${clave} vacío`);
      const texto = textoMensaje(codigo, crearTraductor(d));          // sin respaldo: el texto es del propio idioma
      assert.notEqual(texto, clave);
      assert.doesNotMatch(texto, /\{[A-Za-z_]\w*\}/, `${idioma}/${codigo}: «${texto}»`);
    }
  }
  // las claves js.reserva.<algo sin punto> son exactamente los códigos (los demás textos de la reserva van en grupos)
  for (const d of Object.values(DICCIONARIOS)) {
    const sueltas = Object.keys(d).filter((k) => k.startsWith(PREFIJO_MENSAJES) && !k.slice(PREFIJO_MENSAJES.length).includes("."));
    assert.deepEqual(sueltas.sort(), CODIGOS.map((c) => PREFIJO_MENSAJES + c).sort());
  }
});

test("mensajes en español: los mismos textos que antes de separarlos a es.json; las cifras vienen de TARIFA", () => {
  const antes = {
    fechas_requeridas: "Elige la fecha de llegada y la de salida.",
    fecha_pasada: "La llegada no puede ser en el pasado.",
    fecha_lejana: "Por ahora se reciben solicitudes hasta un año adelante.",
    min_noches: "La estadía mínima es de 2 noches.",
    max_noches: "La estadía máxima es de 30 noches.",
    fechas_ocupadas: "Esas fechas ya tienen una solicitud. Elige otras.",
    datos_invalidos: "Revisa los datos del formulario.",
    nombre: "Escribe tu nombre (2 a 80 caracteres).",
    email: "Escribe un correo válido.",
    telefono: "El teléfono sólo admite números, espacios y + ( ) - .",
    mensaje: "El mensaje admite hasta 1 000 caracteres.",
    huespedes: "Pueden alojar de 1 a 4 personas.",
    acepta: "Necesitamos tu consentimiento para responder la solicitud.",
    red: "No se pudo conectar con el servidor de reservas. Intenta de nuevo.",
    sin_configurar: "Las reservas todavía no están conectadas en este sitio.",
  };
  assert.deepEqual([...CODIGOS].sort(), Object.keys(antes).sort());
  for (const [codigo, texto] of Object.entries(antes)) assert.equal(textoMensaje(codigo, T.es), texto, codigo);
  assert.deepEqual(VARIABLES_MENSAJES, { minNoches: TARIFA.minNoches, maxNoches: TARIFA.maxNoches, maxHuespedes: TARIFA.maxHuespedes });
  assert.match(DICCIONARIOS.es["js.reserva.min_noches"], /\{minNoches\}/, "la cifra no va escrita en el JSON");
  // y en los otros idiomas la cifra también sale de TARIFA
  assert.match(textoMensaje("min_noches", T.en), /\b2\b/);
  assert.match(textoMensaje("huespedes", T.fr), /\b4\b/);
});

// Hallazgo JS-5: los textos de reserva.js y contenido-publico.js que antes eran literales del código (HEAD de
// origin/main antes de web/i18n-base), escritos tal cual. Si alguien cambia es.json por accidente («Elige la llegada»
// -> «Selecciona»), esta prueba falla. Las cifras y fechas son variables: {n}, {fecha}, {entrada}…
const ANTES_ES = Object.freeze({
  "js.reserva.cal.dias_cortos": "lu,ma,mi,ju,vi,sá,do",                       // const DIAS = ["lu", "ma", …]
  "js.reserva.cal.motivo.pasado": "ya pasó",
  "js.reserva.cal.motivo.ocupado": "ocupado",
  "js.reserva.cal.motivo.lejano": "más de un año adelante",
  "js.reserva.cal.motivo.minimo": "mínimo {n} noches",                        // `mínimo ${TARIFA.minNoches} noches`
  "js.reserva.cal.motivo.sin_salida": "no quedan {n} noches libres desde aquí",
  "js.reserva.cal.dia_llegada": "{fecha}, llegada elegida",                   // fLargo.format(…) + ", llegada elegida"
  "js.reserva.cal.dia_salida": "{fecha}, salida elegida",
  "js.reserva.cal.dia_en_rango": "{fecha}, dentro de tu estadía",
  "js.reserva.cal.dia_no_disponible": "{fecha}, no disponible: {motivo}",
  "js.reserva.cal.elige_llegada": "Elige la llegada",
  "js.reserva.cal.elige_salida": "Llegada {entrada} · elige la salida",
  "js.reserva.cal.rango": "{entrada} → {salida} · {noches}",                  // `${e} → ${s} · ` + `${n} noches`
  "js.reserva.resumen.noches_por_tarifa": "{noches} × {tarifa}",              // `${n} noches × ${clp(…)}`
  "js.reserva.resumen.noches": "Noches",
  "js.reserva.resumen.elige_fechas": "Elige tus fechas",
  "js.reserva.resumen.total_ejemplo": "{noches} · total de ejemplo",
  "js.reserva.resumen.sin_cobro": "sin cobro en línea",
  "js.reserva.envio.enviando": "Enviando…",
  "js.reserva.envio.solicitar": "Solicitar",
  "js.reserva.exito.texto": "Pediste {noches}, del {entrada} al {salida}, para {personas}.",
  "js.reserva.noches.other": "{n} noches",                                    // `${n} noches`
  "js.reserva.noches.one": "{n} noche",                                       // nuevo: antes no había singular (mínimo 2)
  "js.reserva.personas.one": "{n} persona",                                   // p.huespedes === 1 ? "persona" : …
  "js.reserva.personas.other": "{n} personas",
  "js.contenido.alt_generico": "Foto del departamento",                       // ALT_GENERICO
  "js.contenido.mas_fotos": "Más fotos de este espacio",
  "js.contenido.ver_foto": "Ver foto: {alt}",                                 // `Ver foto: ${actual.alt}`
});

test("textos de reserva.js y contenido-publico.js en español: los mismos que antes de pasarlos a es.json (hallazgo JS-5)", () => {
  // toda clave js.* de es.json que no es un mensaje (CODIGOS) está en la tabla, y al revés
  const noMensajes = Object.keys(DICCIONARIOS.es).filter((k) => k.startsWith("js.") && !CODIGOS.includes(k.slice(PREFIJO_MENSAJES.length)));
  assert.deepEqual(noMensajes.sort(), Object.keys(ANTES_ES).sort(), "falta o sobra un texto en la tabla ANTES_ES");
  for (const [k, texto] of Object.entries(ANTES_ES)) {
    assert.equal(DICCIONARIOS.es[k], texto, `es.json: ${k}`);
    assert.equal(tPagina(k), texto, `textos-es.js: ${k}`);          // el respaldo que usa la página, sin red
  }
  // lo que ve el visitante, armado como en reserva.js con el t() de la página (en Node, el español de textos-es.js):
  // idéntico a las plantillas de antes
  const nN = (n) => tnPagina("js.reserva.noches", n);
  assert.equal(tPagina("js.reserva.cal.rango", { entrada: "vie 9 oct", salida: "lun 12 oct", noches: nN(3) }), "vie 9 oct → lun 12 oct · 3 noches");
  assert.equal(tPagina("js.reserva.cal.elige_salida", { entrada: "vie 9 oct" }), "Llegada vie 9 oct · elige la salida");
  assert.equal(tPagina("js.reserva.resumen.noches_por_tarifa", { noches: nN(3), tarifa: clp(58000, "es-CL") }), "3 noches × CLP 58.000");
  assert.equal(tPagina("js.reserva.resumen.total_ejemplo", { noches: nN(4) }), "4 noches · total de ejemplo");
  assert.equal(tPagina("js.reserva.cal.dia_no_disponible", { fecha: "sábado, 10 de octubre de 2026", motivo: tPagina("js.reserva.cal.motivo.ocupado") }),
    "sábado, 10 de octubre de 2026, no disponible: ocupado");
  assert.equal(tPagina("js.reserva.cal.motivo.minimo", { n: TARIFA.minNoches }), "mínimo 2 noches");
  assert.equal(tPagina("js.reserva.exito.texto", { noches: nN(3), entrada: "viernes, 9 de octubre de 2026",
    salida: "lunes, 12 de octubre de 2026", personas: tnPagina("js.reserva.personas", 1) }),
  "Pediste 3 noches, del viernes, 9 de octubre de 2026 al lunes, 12 de octubre de 2026, para 1 persona.");
  assert.equal(traducirPlural(T.es, "es-CL", "js.reserva.personas", 2), "2 personas");
});

test("reserva.js: pide la disponibilidad antes de esperar los textos (`await listo`) y pinta después", () => {
  const fuente = sinComentarios(leer("../src/js/reserva.js"));
  const espera = fuente.indexOf("await listo;");
  assert.ok(espera > 0, "reserva.js espera `listo` antes de pintar");
  assert.equal(fuente.indexOf("await listo;", espera + 1), -1);
  assert.ok(fuente.indexOf("disponibilidad(HOY, HASTA)") < espera, "la lectura de la base no va detrás del diccionario");
  assert.ok(fuente.indexOf('t("js.') > espera && fuente.indexOf('tn("js.') > espera, "ningún texto antes de `listo`");
  assert.match(fuente, /^cargarDisponibilidad\(primeraDisponibilidad\);$/m);
});

test("textoMensaje recibe el traductor por parámetro: sin él (o con un código desconocido) queda la clave", () => {
  const pedidos = [];
  const espia = (clave, variables) => { pedidos.push([clave, variables]); return "ok"; };
  assert.equal(textoMensaje("fecha_pasada", espia), "ok");
  assert.deepEqual(pedidos, [["js.reserva.fecha_pasada", VARIABLES_MENSAJES]]);
  assert.equal(textoMensaje("fecha_pasada"), "js.reserva.fecha_pasada");
  assert.equal(textoMensaje("no_existe", T.es), "js.reserva.no_existe");
  assert.equal(textoMensaje("constructor", T.es), "js.reserva.constructor");
  assert.equal(esCodigo("red"), true);
  for (const malo of ["constructor", "toString", "", null, undefined, 5]) assert.equal(esCodigo(malo), false);
});

test("reserva-logica.js no depende de i18n.js ni de la red (lo importan el portal y las pruebas en Node)", () => {
  const codigo = sinComentarios(leer("../src/js/reserva-logica.js"));
  assert.doesNotMatch(codigo, /^\s*import\b|\bimport\(/m);
  assert.doesNotMatch(codigo, /\bfetch\b|\bdocument\b|i18n/);
});

test("todos los códigos que producen validarRango, validarDatos y reservas-api.js tienen mensaje", () => {
  const vistos = new Set();
  for (const r of [validarRango("", "", [], HOY), validarRango("2026-10-04", "2026-10-07", [], HOY),
    validarRango("2027-11-01", "2027-11-04", [], HOY), validarRango("2026-10-06", "2026-10-07", [], HOY),
    validarRango("2026-10-06", sumarDias("2026-10-06", 31), [], HOY),
    validarRango("2026-10-08", "2026-10-11", OCUPADOS, HOY)]) vistos.add(r.error);
  for (const c of Object.values(validarDatos({ nombre: "", email: "x", telefono: "?", mensaje: "x".repeat(1001), huespedes: 9 }))) vistos.add(c);
  for (const [, c] of leer("../src/js/reservas-api.js").matchAll(/codigo: "([a-z_]+)"/g)) vistos.add(c);
  assert.ok(vistos.size >= 12);
  for (const c of vistos) assert.ok(esCodigo(c), `«${c}» no está en CODIGOS`);
  // y los de la base (raise exception '<código>' en las migraciones), que llegan por codigoError
  for (const archivo of ["0001_reservas.sql", "0002_hoy_propiedad.sql", "0004_renombrar_hoy.sql"]) {   // solicitar_reserva
    for (const [, c] of leer(`../supabase/migrations/${archivo}`).matchAll(/raise exception '([a-z_]+)'/g)) {
      assert.ok(esCodigo(c), `${archivo}: «${c}» no está en CODIGOS`);
    }
  }
});

test("días de la semana: de lunes a domingo con Intl y las abreviaturas del diccionario", () => {
  assert.deepEqual(nombresDias("es-CL"), ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]);
  assert.equal(nombresDias("en-US")[0], "Monday");
  assert.equal(nombresDias("fr-FR")[6], "dimanche");
  assert.deepEqual(diasCortos(DICCIONARIOS.es["js.reserva.cal.dias_cortos"], "es-CL"), ["lu", "ma", "mi", "ju", "vi", "sá", "do"]);
  for (const [idioma, d] of Object.entries(DICCIONARIOS)) {
    const dias = diasCortos(d["js.reserva.cal.dias_cortos"], LOCALES[idioma]);
    assert.equal(d["js.reserva.cal.dias_cortos"].split(",").length, 7, `${idioma}: siete abreviaturas`);
    assert.equal(new Set(dias).size, 7, `${idioma}: abreviaturas distintas`);
  }
  // sin siete abreviaturas (clave faltante o mal escrita) se usan las cortas de Intl
  assert.deepEqual(diasCortos("js.reserva.cal.dias_cortos", "en-US"), nombresDias("en-US", "short"));
  assert.deepEqual(diasCortos("a,b,,d,e,f,g", "fr-FR"), nombresDias("fr-FR", "short"));
  assert.deepEqual(diasCortos(undefined, "es-CL"), nombresDias("es-CL", "short"));
});

test("reserva.js calcula con la tarifa vigente y fija las que lee contenido-publico.js", () => {
  const fuente = leer("../src/js/reserva.js");
  assert.match(fuente, /import \{ tarifas \} from "\.\/contenido-publico\.js";/);
  assert.match(fuente, /tarifas\(\)\.then\(\(editadas\) => \{ if \(editadas && fijarTarifas\(editadas\)\) resumen\(\); \}\)\.catch\(/);
  assert.doesNotMatch(fuente, /TARIFA\.(noche|limpieza)|TARIFA\[/, "el precio sale de tarifaVigente(), no de TARIFA");
  assert.match(fuente, /clp\(tarifaVigente\(\)\.noche, LOCALE\)/);
});

/** Literales de texto de un módulo, sin comentarios y sin las partes ${…} de las plantillas. */
function literales(fuente) {
  return [...sinComentarios(fuente).matchAll(/"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`/g)]
    .map(([m]) => m.slice(1, -1).replace(/\$\{[^}]*\}/g, ""));
}

test("reserva.js: todo texto visible y toda etiqueta aria sale de t()/tn(), y las fechas y montos del LOCALE", () => {
  const fuente = leer("../src/js/reserva.js");
  assert.match(fuente, /import \{ LOCALE, listo, t, tn \} from "\.\/i18n\.js";/);
  for (const lit of literales(fuente)) {
    if (lit.startsWith("js.")) continue;                             // claves de los diccionarios
    assert.doesNotMatch(lit, /[A-Za-zÀ-ÿ]\s+[A-Za-zÀ-ÿ]/, `texto sin traducir: «${lit}»`);
    assert.doesNotMatch(lit, /[À-ÿ…]/, `texto sin traducir: «${lit}»`);
    assert.doesNotMatch(lit, /^[A-Z][a-z]+$/, `texto sin traducir: «${lit}»`);
  }
  assert.doesNotMatch(fuente, /MENSAJES|"es-CL"|"es"/);
  assert.equal([...fuente.matchAll(/new Intl\.DateTimeFormat\(([^,]+),/g)].filter(([, l]) => l !== "LOCALE").length, 0);
  assert.equal([...fuente.matchAll(/\bclp\(([^()]|\([^()]*\))*\)/g)].filter(([m]) => !m.endsWith(", LOCALE)")).length, 0,
    "todo monto con clp(…, LOCALE)");
  // aria-label de los días por t(): llegada, salida, estadía y motivo de no disponible
  for (const k of ["dia_llegada", "dia_salida", "dia_en_rango", "dia_no_disponible"]) {
    assert.match(fuente, new RegExp(`t\\("js\\.reserva\\.cal\\.${k}"`));
  }
});

test("grillaMes: semanas completas, lunes primero", () => {
  const oct = grillaMes(2026, 9);                        // octubre 2026 empieza en jueves
  assert.deepEqual(oct[0].slice(0, 4), [null, null, null, "2026-10-01"]);
  assert.ok(oct.every((s) => s.length === 7));
  assert.equal(oct.flat().filter(Boolean).length, 31);
});

test("mesesPorPagina: dos meses solo si caben 2 × 7 días de 48 px más la separación", () => {
  assert.equal(2 * 7 * CELDA_MIN + SEPARACION_MESES, 704);
  assert.equal(mesesPorPagina(320), 1);
  assert.equal(mesesPorPagina(703), 1);
  assert.equal(mesesPorPagina(704), 2);
  assert.equal(mesesPorPagina(738), 2);                  // #meses a 1280 px, con el resumen al lado
  assert.equal(mesesPorPagina(0), 1);                    // sin medir (display: none) se pinta uno
});

test("hayMesSiguiente: la última página alcanzable es la que contiene `hasta`", () => {
  const HASTA = "2027-10-26";
  assert.equal(hayMesSiguiente(2027, 8, 2, HASTA), false);   // septiembre + octubre: octubre ya contiene HASTA
  assert.equal(hayMesSiguiente(2027, 8, 1, HASTA), true);    // septiembre solo: falta octubre
  assert.equal(hayMesSiguiente(2027, 9, 1, HASTA), false);   // octubre contiene HASTA
  assert.equal(hayMesSiguiente(2027, 7, 2, HASTA), true);    // agosto + septiembre: falta octubre
  assert.equal(hayMesSiguiente(2026, 11, 1, "2027-01-01"), true);   // cruza de año
  assert.equal(hayMesSiguiente(2026, 11, 2, "2027-01-31"), false);
});

test("validarDatos replica los CHECK de la tabla", () => {
  const bien = { nombre: "Ana Pérez", email: "ana@ejemplo.cl", telefono: "+56 9 1234 5678", huespedes: 2, acepta: true };
  assert.deepEqual(validarDatos(bien), {});
  assert.deepEqual(Object.keys(validarDatos({ ...bien, nombre: " ", email: "x@y", huespedes: 5, acepta: false })).sort(),
                   ["acepta", "email", "huespedes", "nombre"]);
  assert.equal(validarDatos({ ...bien, telefono: "llámame" }).telefono, "telefono");
  assert.equal(validarDatos({ ...bien, mensaje: "x".repeat(1001) }).mensaje, "mensaje");
});

test("codigoError reconoce los errores del servidor y cae en «red» si no", () => {
  assert.equal(codigoError({ message: "fechas_ocupadas" }), "fechas_ocupadas");
  assert.equal(codigoError(new Error("Failed to fetch")), "red");
  assert.equal(codigoError(null), "red");
});
