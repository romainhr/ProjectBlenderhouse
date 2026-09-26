// Pruebas de la lógica pura del portal del propietario (web/src/admin/js): reservas, textos, fotos, modo y errores.
//   cd web && npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ACCIONES, ESTADOS, accionesPermitidas, contarPorEstado, enPeriodo, enlaceCorreo, enlaceTelefono, filtrarReservas,
  pendientesPorResolver, reemplazar, situacion, validarNota,
} from "../src/admin/js/logica-reservas.js";
import { LIMITE_VALOR, agruparContenido, previaPrecio, tituloGrupo, validarValor } from "../src/admin/js/logica-contenido.js";
import {
  ESPACIOS, MAX_SUBIDA, RE_RUTA, contarPorEspacio, dimensionesPorCabecera, dimensionesReducidas, esEspacio, extensionPara,
  fotosDeEspacio, moverFoto, pasosReduccion, rutaCodificada, rutaFoto, siguienteOrden, sufijoAleatorio, tipoPorFirma,
  urlPublica, validarAlt, validarArchivo,
} from "../src/admin/js/logica-fotos.js";
import { configValida, decidirModo, esLocal } from "../src/admin/js/modo.js";
import { ErrorApi, codigoConocido, errorDesdeRespuesta, esErrorDeSesion, mensajeError } from "../src/admin/js/errores.js";
import { formatearDia, hrefSeguro, largo, peso, rangoCorto } from "../src/admin/js/util.js";

const HOY = "2026-10-05";
const R = (id, entrada, salida, estado, creada = "2026-09-01T00:00:00Z") => ({ id, entrada, salida, estado, creada });
const RESERVAS = [
  R("a", "2026-10-08", "2026-10-11", "pendiente"),
  R("b", "2026-10-03", "2026-10-06", "confirmada"),          // en curso
  R("c", "2026-10-01", "2026-10-05", "confirmada"),          // sale hoy
  R("d", "2026-09-20", "2026-09-23", "rechazada"),           // pasada
  R("e", "2026-11-01", "2026-11-04", "cancelada"),
  R("f", "2026-09-25", "2026-09-28", "pendiente"),           // pendiente ya pasada (no cuenta como por resolver)
];

// ---------------------------------------------------------------------------------------------- reservas
test("reservas: periodo próximas/pasadas con la salida como límite (la noche de salida no se ocupa)", () => {
  assert.ok(enPeriodo(RESERVAS[2], "proximas", HOY), "la que sale hoy sigue en próximas");
  assert.ok(!enPeriodo(RESERVAS[2], "pasadas", HOY));
  assert.ok(enPeriodo(RESERVAS[3], "pasadas", HOY));
  assert.equal(situacion(RESERVAS[1], HOY), "en_curso");
  assert.equal(situacion(RESERVAS[2], HOY), "sale_hoy");
  assert.equal(situacion(RESERVAS[3], HOY), "pasada");
  assert.equal(situacion(RESERVAS[0], HOY), "proxima");
});

test("reservas: filtro por estado y periodo, con orden útil", () => {
  const prox = filtrarReservas(RESERVAS, { estado: "todas", periodo: "proximas" }, HOY).map((r) => r.id);
  assert.deepEqual(prox, ["c", "b", "a", "e"], "próximas: de la más cercana a la más lejana");
  const pasadas = filtrarReservas(RESERVAS, { estado: "todas", periodo: "pasadas" }, HOY).map((r) => r.id);
  assert.deepEqual(pasadas, ["f", "d"], "pasadas: la más reciente primero");
  assert.deepEqual(filtrarReservas(RESERVAS, { estado: "confirmada", periodo: "todas" }, HOY).map((r) => r.id), ["b", "c"]);
  assert.deepEqual(filtrarReservas(RESERVAS, { estado: "pendiente", periodo: "pasadas" }, HOY).map((r) => r.id), ["f"]);
});

test("reservas: contadores por estado dentro del periodo y pendientes por resolver", () => {
  assert.deepEqual(contarPorEstado(RESERVAS, "proximas", HOY),
    { todas: 4, pendiente: 1, confirmada: 2, rechazada: 0, cancelada: 1 });
  assert.deepEqual(contarPorEstado(RESERVAS, "todas", HOY),
    { todas: 6, pendiente: 2, confirmada: 2, rechazada: 1, cancelada: 1 });
  assert.equal(pendientesPorResolver(RESERVAS, HOY), 1);
});

test("reservas: acciones permitidas por estado y todas con su texto", () => {
  assert.deepEqual(accionesPermitidas("pendiente"), ["confirmada", "rechazada"]);
  assert.deepEqual(accionesPermitidas("confirmada"), ["cancelada"]);
  assert.ok(accionesPermitidas("rechazada").includes("confirmada"), "reabrir es donde puede chocar (23P01)");
  assert.deepEqual(accionesPermitidas("inventado"), []);
  for (const e of ESTADOS) for (const destino of accionesPermitidas(e)) {
    assert.ok(ESTADOS.includes(destino));
    assert.ok(ACCIONES[destino].texto);
  }
  assert.ok(ACCIONES.rechazada.peligro && ACCIONES.cancelada.peligro);
});

test("reservas: nota interna con el límite de la base (2000 puntos de código) y vacía -> null", () => {
  assert.deepEqual(validarNota("  \n"), { ok: true, valor: null });
  assert.deepEqual(validarNota("Llega tarde\r\n"), { ok: true, valor: "Llega tarde" });
  assert.ok(validarNota("x".repeat(2000)).ok);
  assert.equal(validarNota("x".repeat(2001)).error, "nota_larga");
  assert.ok(validarNota("😀".repeat(2000)).ok, "cuenta como char_length, no como unidades UTF-16");
});

test("reservas: enlaces mailto y tel sólo con formas seguras", () => {
  assert.equal(enlaceCorreo("ana@example.com"), "mailto:ana@example.com");
  assert.equal(enlaceCorreo("ana@example.com", "Código A&B?"), "mailto:ana@example.com?subject=C%C3%B3digo%20A%26B%3F");
  assert.equal(enlaceCorreo("ana@example.com?bcc=otro@x.com"), null);
  assert.equal(enlaceCorreo("javascript:alert(1)//@x.com"), null);
  assert.equal(enlaceCorreo("sin-arroba"), null);
  assert.equal(enlaceTelefono("+56 9 1234 5678"), "tel:+56912345678");
  assert.equal(enlaceTelefono("(2) 2345-6789"), "tel:223456789");
  assert.equal(enlaceTelefono("12"), null);
  assert.equal(enlaceTelefono(null), null);
});

test("reservas: reemplazar una fila por id sin tocar las demás", () => {
  const l = reemplazar(RESERVAS, { id: "a", estado: "confirmada" });
  assert.equal(l.find((r) => r.id === "a").estado, "confirmada");
  assert.equal(l.find((r) => r.id === "a").entrada, "2026-10-08");
  assert.equal(RESERVAS[0].estado, "pendiente", "no muta la original");
});

// ---------------------------------------------------------------------------------------------- textos
test("textos: precio validado como el check de la base (entero 0..10 000 000 en dígitos)", () => {
  assert.deepEqual(validarValor("precio", "58000"), { ok: true, valor: "58000" });
  assert.deepEqual(validarValor("precio", "58.000"), { ok: true, valor: "58000" }, "acepta separador de miles es-CL");
  assert.deepEqual(validarValor("precio", "CLP 58 000"), { ok: true, valor: "58000" });
  assert.deepEqual(validarValor("precio", "058000"), { ok: true, valor: "58000" }, "sin ceros a la izquierda");
  assert.deepEqual(validarValor("precio", "0"), { ok: true, valor: "0" });
  assert.deepEqual(validarValor("precio", "10000000"), { ok: true, valor: "10000000" });
  assert.equal(validarValor("precio", "10000001").error, "precio_rango");
  assert.equal(validarValor("precio", "58000.5").error, "precio_formato");
  assert.equal(validarValor("precio", "58,5").error, "precio_formato");
  assert.equal(validarValor("precio", "-5").error, "precio_formato");
  assert.equal(validarValor("precio", "1e5").error, "precio_formato");
  assert.equal(validarValor("precio", " ").error, "vacio");
});

test("textos: texto de una línea, párrafo y límites", () => {
  assert.deepEqual(validarValor("texto", "  Living \n grande "), { ok: true, valor: "Living grande" });
  assert.deepEqual(validarValor("parrafo", "Línea 1\r\nLínea 2  "), { ok: true, valor: "Línea 1\nLínea 2" });
  assert.equal(validarValor("parrafo", "   ").error, "vacio");
  assert.ok(validarValor("parrafo", "a".repeat(LIMITE_VALOR)).ok);
  assert.equal(validarValor("parrafo", "a".repeat(LIMITE_VALOR + 1)).error, "largo");
  assert.equal(validarValor("html", "x").error, "tipo");
  assert.equal(previaPrecio("58000"), "CLP 58.000");
  assert.equal(previaPrecio("abc"), "");
});

test("textos: agrupar por grupo, filas por orden y grupos por su menor orden", () => {
  const filas = [
    { clave: "tarifa.noche", grupo: "tarifas", orden: 40 },
    { clave: "espacio.cocina.titulo", grupo: "espacios", orden: 22 },
    { clave: "hero.bajada", grupo: "portada", orden: 10 },
    { clave: "espacio.living.titulo", grupo: "espacios", orden: 20 },
    { clave: "tarifa.limpieza", grupo: "tarifas", orden: 41 },
    { clave: "b", grupo: "espacios", orden: 20 },
  ];
  const g = agruparContenido(filas);
  assert.deepEqual(g.map((x) => x.grupo), ["portada", "espacios", "tarifas"]);
  assert.deepEqual(g[1].filas.map((f) => f.clave), ["b", "espacio.living.titulo", "espacio.cocina.titulo"]);
  assert.equal(g[1].titulo, "Espacios");
  assert.equal(tituloGrupo("condiciones_estadia"), "Condiciones estadia");
  assert.deepEqual(agruparContenido([]), []);
});

// ---------------------------------------------------------------------------------------------- fotos
test("fotos: validación de archivo por tipo y peso", () => {
  assert.ok(validarArchivo({ type: "image/jpeg", size: 3e6 }).ok);
  assert.equal(validarArchivo({ type: "image/gif", size: 1000 }).error, "tipo");
  assert.equal(validarArchivo({ type: "image/svg+xml", size: 1000 }).error, "tipo");
  assert.equal(validarArchivo({ type: "image/png", size: 21 * 1024 * 1024 }).error, "tamano");
  assert.equal(validarArchivo({ type: "image/png", size: 0 }).error, "vacio");
  assert.equal(validarArchivo(null).error, "vacio");
  assert.equal(MAX_SUBIDA, 5242880, "igual al file_size_limit del bucket en 0003");
});

function bytes(largoTotal, parches) {
  const b = new Uint8Array(largoTotal);
  for (const [i, arr] of parches) b.set(arr, i);
  return b;
}
const be32 = (n) => [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255];

test("fotos: tipo real por la firma de los bytes, no por la extensión", () => {
  const png = bytes(32, [[0, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]], [12, [0x49, 0x48, 0x44, 0x52]], [16, be32(4000)], [20, be32(3000)]]);
  assert.equal(tipoPorFirma(png), "image/png");
  assert.deepEqual(dimensionesPorCabecera(png), { ancho: 4000, alto: 3000 });

  const webpX = bytes(32, [[0, [0x52, 0x49, 0x46, 0x46]], [8, [0x57, 0x45, 0x42, 0x50]], [12, [0x56, 0x50, 0x38, 0x58]],
    [24, [0x3f, 0x06, 0x00]], [27, [0xaf, 0x04, 0x00]]]);                     // 1600 × 1200 (valor − 1 en 24 bits LE)
  assert.equal(tipoPorFirma(webpX), "image/webp");
  assert.deepEqual(dimensionesPorCabecera(webpX), { ancho: 1600, alto: 1200 });

  const webp = bytes(32, [[0, [0x52, 0x49, 0x46, 0x46]], [8, [0x57, 0x45, 0x42, 0x50]], [12, [0x56, 0x50, 0x38, 0x20]],
    [23, [0x9d, 0x01, 0x2a]], [26, [0x40, 0x06]], [28, [0xb0, 0x04]]]);      // VP8: 1600 × 1200
  assert.deepEqual(dimensionesPorCabecera(webp), { ancho: 1600, alto: 1200 });

  // JPEG: SOI, APP1 (EXIF) de 16 bytes y luego SOF0 con alto 3024 y ancho 4032
  const jpg = bytes(64, [[0, [0xff, 0xd8, 0xff, 0xe1, 0x00, 0x10]], [20, [0xff, 0xc0, 0x00, 0x11, 0x08, 0x0b, 0xd0, 0x0f, 0xc0]]]);
  assert.equal(tipoPorFirma(jpg), "image/jpeg");
  assert.deepEqual(dimensionesPorCabecera(jpg), { ancho: 4032, alto: 3024 });

  const gif = bytes(16, [[0, [0x47, 0x49, 0x46, 0x38, 0x39, 0x61]]]);
  assert.equal(tipoPorFirma(gif), null);
  const html = new TextEncoder().encode("<svg onload=alert(1)>....");
  assert.equal(tipoPorFirma(html), null);
  assert.equal(dimensionesPorCabecera(html), null);
  assert.equal(tipoPorFirma(new Uint8Array(4)), null);
});

test("fotos: reducción a 1600 px de ancho, sin agrandar, en pasos de a la mitad", () => {
  assert.deepEqual(dimensionesReducidas(4032, 3024), { ancho: 1600, alto: 1200 });
  assert.deepEqual(dimensionesReducidas(3024, 4032), { ancho: 1600, alto: 2133 });
  assert.deepEqual(dimensionesReducidas(1200, 800), { ancho: 1200, alto: 800 });
  assert.equal(dimensionesReducidas(0, 10), null);
  assert.deepEqual(pasosReduccion(4032, 1600), [2016, 1600]);
  assert.deepEqual(pasosReduccion(8000, 1600), [4000, 2000, 1600]);
  assert.deepEqual(pasosReduccion(1600, 1600), [1600]);
  assert.deepEqual(pasosReduccion(1000, 1600), [1000]);
});

test("fotos: rutas generadas por el código (espacio/aaaammdd-xxxxxxxx.ext), nunca el nombre original", () => {
  const suf = sufijoAleatorio(new Uint8Array([0x0a, 0xff, 0x00, 0x7b]));
  assert.equal(suf, "0aff007b");
  const ruta = rutaFoto("dorm1", "2026-09-26", suf, "image/webp");
  assert.equal(ruta, "dorm1/20260926-0aff007b.webp");
  assert.match(ruta, RE_RUTA);
  assert.equal(rutaFoto("living", "2026-09-26", suf, "image/jpeg"), "living/20260926-0aff007b.jpg");
  assert.throws(() => rutaFoto("../otro", "2026-09-26", suf, "image/webp"), /espacio_invalido/);
  assert.throws(() => rutaFoto("terraza", "2026-09-26", suf, "image/webp"), /espacio_invalido/);
  assert.throws(() => rutaFoto("living", "2026-09-26", "foto de mi casa", "image/webp"), /sufijo_invalido/);
  assert.throws(() => rutaFoto("living", "2026-09-26", suf, "image/gif"), /tipo_invalido/);
  assert.equal(extensionPara("image/png"), "png");
  assert.equal(ESPACIOS.length, 7);
  assert.ok(ESPACIOS.every((e) => esEspacio(e.id)));
});

test("fotos: URL pública con cada segmento codificado", () => {
  const base = "https://abcdefghijklmnop.supabase.co/";
  assert.equal(urlPublica(base, "living/20260926-0aff007b.webp"),
    "https://abcdefghijklmnop.supabase.co/storage/v1/object/public/fotos/living/20260926-0aff007b.webp");
  assert.equal(rutaCodificada("a b/c?d#e.webp"), "a%20b/c%3Fd%23e.webp");
});

test("fotos: texto alternativo obligatorio (1 a 200)", () => {
  assert.deepEqual(validarAlt("  Living   con sofá  "), { ok: true, valor: "Living con sofá" });
  assert.equal(validarAlt("   ").error, "alt_vacio");
  assert.equal(validarAlt("a".repeat(201)).error, "alt_largo");
  assert.ok(validarAlt("a".repeat(200)).ok);
});

test("fotos: orden por espacio, siguiente orden y mover arriba/abajo con sólo los cambios necesarios", () => {
  const fotos = [
    { id: "1", espacio: "living", orden: 0, creada: "2026-09-01" },
    { id: "2", espacio: "living", orden: 10, creada: "2026-09-02" },
    { id: "3", espacio: "living", orden: 20, creada: "2026-09-03" },
    { id: "4", espacio: "cocina", orden: 5, creada: "2026-09-01" },
  ];
  assert.deepEqual(fotosDeEspacio(fotos, "living").map((f) => f.id), ["1", "2", "3"]);
  assert.equal(contarPorEspacio(fotos).living, 3);
  assert.equal(contarPorEspacio(fotos).banos, 0);
  assert.equal(siguienteOrden(fotosDeEspacio(fotos, "living")), 30);
  assert.equal(siguienteOrden([]), 0);

  const sube = moverFoto(fotosDeEspacio(fotos, "living"), "3", -1);
  assert.deepEqual(sube.lista.map((f) => f.id), ["1", "3", "2"]);
  assert.deepEqual(sube.cambios, [{ id: "3", orden: 10 }, { id: "2", orden: 20 }]);
  assert.deepEqual(moverFoto(fotosDeEspacio(fotos, "living"), "1", -1).cambios, [], "la primera no sube");
  assert.deepEqual(moverFoto(fotosDeEspacio(fotos, "living"), "3", 1).cambios, [], "la última no baja");
  assert.deepEqual(moverFoto(fotosDeEspacio(fotos, "living"), "x", 1).cambios, []);

  // órdenes repetidos (p. ej. filas creadas a mano): se desempata por fecha y se renumera
  const repetidos = [{ id: "a", orden: 0, creada: "2" }, { id: "b", orden: 0, creada: "1" }];
  const m = moverFoto(repetidos, "a", -1);
  assert.deepEqual(m.lista.map((f) => [f.id, f.orden]), [["a", 0], ["b", 10]]);
  assert.deepEqual(m.cambios, [{ id: "b", orden: 10 }]);
});

// ---------------------------------------------------------------------------------------------- modo
test("modo simulado sólo en un host local; fuera de él sin configuración no hay login", () => {
  const cfg = { url: "https://abcdefghijklmnopqrst.supabase.co", clave: "sb_publishable_abcdefghijklmnopqrstuvwxyz" };
  assert.equal(decidirModo({ hostname: "localhost", search: "", config: { url: "", clave: "" } }), "simulado");
  assert.equal(decidirModo({ hostname: "127.0.0.1", search: "", config: cfg }), "real");
  assert.equal(decidirModo({ hostname: "127.0.0.1", search: "?simulado=1", config: cfg }), "simulado");
  assert.equal(decidirModo({ hostname: "[::1]", search: "", config: null }), "simulado");
  assert.equal(decidirModo({ hostname: "loft-2d2b.netlify.app", search: "?simulado=1", config: cfg }), "real");
  assert.equal(decidirModo({ hostname: "loft-2d2b.netlify.app", search: "?simulado=1", config: { url: "", clave: "" } }),
    "sin_configurar");
  assert.equal(decidirModo({ hostname: "localhost.evil.com", search: "?simulado=1", config: null }), "sin_configurar");
  assert.ok(esLocal("portal.localhost"));
  assert.ok(!esLocal("localhost.evil.com"));
  assert.ok(!configValida({ url: "javascript:alert(1)", clave: cfg.clave }));
  assert.ok(!configValida({ url: cfg.url, clave: "corta" }));
  assert.ok(configValida({ url: "http://127.0.0.1:54321", clave: cfg.clave }));
});

// ---------------------------------------------------------------------------------------------- errores
test("errores: cuerpos de PostgREST, Auth y Storage a mensajes claros", () => {
  const choque = errorDesdeRespuesta(409, { code: "23P01", message: 'conflicting key value violates exclusion constraint "reservas_sin_solape"', details: "Key ..." }, "rest");
  assert.equal(codigoConocido(choque), "fechas_chocan");
  assert.match(mensajeError(choque), /chocan con otra solicitud/);
  assert.equal(codigoConocido(errorDesdeRespuesta(400, { code: "23514", message: "check" })), "regla_base");
  assert.equal(codigoConocido(errorDesdeRespuesta(403, { code: "42501", message: "permission denied for table reservas" })), "sin_permiso");
  assert.equal(codigoConocido(errorDesdeRespuesta(404, { code: "PGRST202", message: "Could not find the function" })), "falta_migracion");
  assert.equal(codigoConocido(errorDesdeRespuesta(404, { code: "PGRST205", message: "Could not find the table" })), "falta_migracion");
  assert.equal(codigoConocido(errorDesdeRespuesta(400, { code: "42703", message: "column reservas.nota_interna does not exist" })), "falta_migracion");

  assert.equal(codigoConocido(errorDesdeRespuesta(400, { code: 400, error_code: "invalid_credentials", msg: "Invalid login credentials" }, "auth")), "credenciales");
  assert.equal(codigoConocido(errorDesdeRespuesta(400, { error: "invalid_grant", error_description: "Invalid login credentials" }, "auth")), "credenciales");
  assert.equal(codigoConocido(errorDesdeRespuesta(400, { error_code: "email_not_confirmed" }, "auth")), "correo_sin_confirmar");
  assert.equal(codigoConocido(errorDesdeRespuesta(429, { error_code: "over_request_rate_limit" }, "auth")), "demasiados_intentos");

  const dup = errorDesdeRespuesta(400, { statusCode: "409", error: "Duplicate", message: "The resource already exists" }, "storage");
  assert.equal(dup.estado, 409, "el estado real del cuerpo de Storage");
  assert.equal(codigoConocido(dup), "archivo_duplicado");
  assert.equal(codigoConocido(errorDesdeRespuesta(413, { statusCode: "413", error: "Payload too large" }, "storage")), "archivo_grande");
  assert.equal(codigoConocido(errorDesdeRespuesta(400, { statusCode: "415", error: "invalid_mime_type", message: "mime type image/gif is not supported" }, "storage")), "archivo_tipo");
  assert.equal(codigoConocido(errorDesdeRespuesta(400, { statusCode: "403", error: "Unauthorized", message: "new row violates row-level security policy" }, "storage")), "sin_permiso");
  assert.equal(codigoConocido(errorDesdeRespuesta(404, { statusCode: "404", error: "Bucket not found", message: "Bucket not found" }, "storage")), "falta_migracion");

  const raro = errorDesdeRespuesta(500, { code: "XX000", message: "algo raro" });
  assert.match(mensajeError(raro), /HTTP 500.*algo raro/);
  assert.equal(mensajeError(new ErrorApi({ codigo: "red" })), mensajeError({ codigo: "red" }));
});

test("errores: qué cuenta como token vencido (para refrescar y reintentar)", () => {
  assert.ok(esErrorDeSesion(errorDesdeRespuesta(401, { code: "PGRST303", message: "JWT expired" })));
  assert.ok(esErrorDeSesion(errorDesdeRespuesta(400, { statusCode: "400", error: "InvalidJWT", message: "jwt expired" }, "storage")));
  assert.ok(!esErrorDeSesion(errorDesdeRespuesta(403, { code: "42501", message: "permission denied" })), "403 de permisos no es sesión");
  assert.ok(!esErrorDeSesion(new ErrorApi({ codigo: "red" })));
});

// ---------------------------------------------------------------------------------------------- utilidades
test("util: href seguro, largo en puntos de código, fechas y pesos", () => {
  assert.equal(hrefSeguro("javascript:alert(1)"), "#");
  assert.equal(hrefSeguro(" JaVaScRiPt:alert(1)"), "#");
  assert.equal(hrefSeguro("data:text/html,<b>"), "#");
  assert.equal(hrefSeguro("mailto:a@example.com"), "mailto:a@example.com");
  assert.equal(hrefSeguro("tel:+56912345678"), "tel:+56912345678");
  assert.equal(hrefSeguro("../"), "../");
  assert.equal(largo("año😀"), 4);
  assert.match(formatearDia("2026-10-05"), /5.*oct.*2026/);
  assert.equal(formatearDia("2026-02-30"), "—");
  assert.match(rangoCorto("2026-12-30", "2027-01-02"), /2026.*2027/);
  assert.match(rangoCorto("2026-10-05", "2026-10-08"), /^5 oct.*8 oct.* 2026$/);
  assert.equal(peso(850000), "850 kB");
  assert.match(peso(3200000), /^3,2 MB$/);
});
