// Pruebas del modo simulado del portal (api-simulada.js) y de los pasos compuestos de fotos (acciones-fotos.js):
// consistencia entre el objeto de Storage y la fila, reintento de ruta y orden.
//   cd web && npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { publicarFoto, quitarFoto, rechazoDefinitivo, reordenarFoto } from "../src/admin/js/acciones-fotos.js";
import { crearApiSimulada, datosEjemplo } from "../src/admin/js/api-simulada.js";
import { ErrorApi, codigoConocido, mensajeError } from "../src/admin/js/errores.js";
import { validarFila, validarTraduccion } from "../src/admin/js/logica-contenido.js";
import { RE_RUTA, fotosDeEspacio } from "../src/admin/js/logica-fotos.js";
import { CLAVE_ALMACEN } from "../src/admin/js/sesion.js";

const HOY = "2026-10-05";

class AlmacenFalso {
  constructor() { this.m = new Map(); }
  getItem(k) { return this.m.has(k) ? this.m.get(k) : null; }
  setItem(k, v) { this.m.set(k, String(v)); }
  removeItem(k) { this.m.delete(k); }
  clear() { this.m.clear(); }
}

async function dentro() {
  const almacen = new AlmacenFalso();
  const api = crearApiSimulada({ almacen, retardo: 0, hoy: HOY });
  await api.iniciarSesion("cualquiera@example.com", "cualquier-cosa");
  return { api, almacen };
}

const webp = (n = 10) => new Blob([new Uint8Array(n)], { type: "image/webp" });
const azarFijo = (...series) => () => new Uint8Array(series.shift() || [9, 9, 9, 9]);

test("simulado: datos de ejemplo inventados (example.com) y con un texto con marcas para probar textContent", () => {
  const d = datosEjemplo(HOY);
  assert.ok(d.reservas.length >= 6);
  assert.ok(d.reservas.every((r) => r.email.endsWith("@example.com")));
  assert.ok(d.reservas.some((r) => /<img|<b>/.test(r.nombre + r.mensaje)));
  assert.ok(d.contenido.some((f) => f.tipo === "precio") && d.contenido.some((f) => f.tipo === "parrafo"));
  assert.ok(d.fotos.every((f) => RE_RUTA.test(f.ruta)));
  assert.ok(d.fotos.some((f) => !f.visible));
});

test("simulado: login falso acepta cualquier dato no vacío, restaura en la pestaña y cerrar borra el almacén", async () => {
  const almacen = new AlmacenFalso();
  const api = crearApiSimulada({ almacen, retardo: 0, hoy: HOY });
  assert.equal(await api.restaurarSesion(), null);
  await assert.rejects(api.reservas.listar(), (e) => e.codigo === "sesion_vencida");
  await assert.rejects(api.iniciarSesion("", "x"), (e) => codigoConocido(e) === "datos_login");
  await api.iniciarSesion("dueno@example.com", "1");
  assert.equal(api.usuario().email, "dueno@example.com");
  assert.equal(JSON.parse(almacen.getItem(CLAVE_ALMACEN)).modo, "simulado");
  const otra = crearApiSimulada({ almacen, retardo: 0, hoy: HOY });
  assert.ok(await otra.restaurarSesion());
  assert.equal(await otra.esPropietario(), true);
  await otra.cerrarSesion();
  assert.equal(almacen.m.size, 0);
});

test("simulado: confirmar una rechazada que choca con otra confirmada da 23P01 y el mensaje claro", async () => {
  const { api } = await dentro();
  const lista = await api.reservas.listar();
  const carla = lista.find((r) => r.nombre.startsWith("Carla"));
  await assert.rejects(api.reservas.cambiarEstado(carla.id, "confirmada"), (e) => {
    assert.equal(e.codigo, "23P01");
    assert.match(mensajeError(e), /chocan con otra solicitud/);
    return true;
  });
  const diego = lista.find((r) => r.nombre.startsWith("Diego"));
  const nueva = await api.reservas.cambiarEstado(diego.id, "confirmada");
  assert.equal(nueva.estado, "confirmada");
  assert.ok(nueva.actualizada);
  await assert.rejects(api.reservas.cambiarEstado(diego.id, "borrada"), (e) => codigoConocido(e) === "regla_base");
});

test("simulado: nota interna (límite 2000), eliminar y fila inexistente", async () => {
  const { api } = await dentro();
  const [r] = await api.reservas.listar();
  assert.equal((await api.reservas.guardarNota(r.id, "Llega tarde")).nota_interna, "Llega tarde");
  await assert.rejects(api.reservas.guardarNota(r.id, "x".repeat(2001)), (e) => codigoConocido(e) === "regla_base");
  await api.reservas.eliminar(r.id);
  assert.ok(!(await api.reservas.listar()).some((x) => x.id === r.id));
  await assert.rejects(api.reservas.eliminar(r.id), (e) => codigoConocido(e) === "sin_filas");
});

test("simulado: contenido con el mismo check de precio que la base", async () => {
  const { api } = await dentro();
  assert.equal((await api.contenido.guardar("tarifa.noche", "60000")).valor, "60000");
  await assert.rejects(api.contenido.guardar("tarifa.noche", "60.000,5"), (e) => codigoConocido(e) === "regla_base");
  await assert.rejects(api.contenido.guardar("no.existe", "x"), (e) => codigoConocido(e) === "sin_filas");
});

// ---------------------------------------------------------------------------------------------- idiomas (0005)
test("simulado: traducciones de ejemplo (algunas en null) y precios sin traducir", () => {
  const { contenido } = datosEjemplo(HOY);
  assert.ok(contenido.every((f) => "valor_en" in f && "valor_fr" in f), "todas las filas traen las columnas de la 0005");
  assert.ok(contenido.some((f) => f.valor_en && f.valor_fr), "hay filas con inglés y francés propios");
  assert.ok(contenido.some((f) => f.valor_en && f.valor_fr === null), "y filas con un solo idioma");
  assert.ok(contenido.some((f) => f.tipo !== "precio" && f.valor_en === null && f.valor_fr === null), "y filas sin traducción");
  assert.ok(contenido.filter((f) => f.tipo === "precio").every((f) => f.valor_en === null && f.valor_fr === null));
  for (const f of contenido) for (const c of ["valor_en", "valor_fr"]) {
    if (f[c] !== null) assert.equal(validarTraduccion(f.tipo, f[c]).valor, f[c], `${f.clave}.${c} ya normalizado`);
  }
});

test("simulado: listar informa idiomas y guardar recibe los tres valores de la fila", async () => {
  const { api } = await dentro();
  const { filas, idiomas } = await api.contenido.listar();
  assert.equal(idiomas, true);
  assert.equal(filas.find((f) => f.clave === "hero.bajada").valor_fr.length > 0, true);
  const antes = filas.find((f) => f.clave === "espacio.cocina.titulo");
  const v = validarFila(antes, { es: " Cocina ", en: "", fr: "Cuisine" });
  assert.ok(v.ok);
  const nueva = await api.contenido.guardar(antes.clave, v.cambios);
  assert.deepEqual([nueva.valor, nueva.valor_en, nueva.valor_fr], ["Cocina", null, "Cuisine"], "vacío -> null");
  assert.notEqual(nueva.actualizado, antes.actualizado);
  const releida = (await api.contenido.listar()).filas.find((f) => f.clave === antes.clave);
  assert.deepEqual([releida.valor_en, releida.valor_fr], [null, "Cuisine"]);
});

test("simulado: las traducciones cumplen los checks de la 0005 y el cambio es todo o nada", async () => {
  const { api } = await dentro();
  const regla = (e) => codigoConocido(e) === "regla_base";
  await assert.rejects(api.contenido.guardar("tarifa.noche", { valor: "58000", valor_en: "58000" }), regla, "precio traducido");
  await assert.rejects(api.contenido.guardar("hero.bajada", { valor: "Hola", valor_en: "   " }), regla, "en blanco");
  await assert.rejects(api.contenido.guardar("hero.bajada", { valor: "Hola", valor_fr: "" }), regla, "vacío en vez de null");
  await assert.rejects(api.contenido.guardar("hero.bajada", { valor: "Hola", valor_fr: "x".repeat(4001) }), regla, "largo");
  await assert.rejects(api.contenido.guardar("hero.bajada", { valor: "Nuevo", valor_en: 5 }), regla, "no es texto");
  const f = (await api.contenido.listar()).filas.find((x) => x.clave === "hero.bajada");
  assert.notEqual(f.valor, "Nuevo", "un rechazo no deja el español a medio guardar");
  assert.deepEqual((await api.contenido.guardar("tarifa.noche", { valor: "59000", valor_en: null, valor_fr: null })).valor, "59000");
});

test("simulado sin la 0005: sin columnas de traducción, aviso al guardarlas y el español se sigue editando", async () => {
  const api = crearApiSimulada({ almacen: new AlmacenFalso(), retardo: 0, hoy: HOY, idiomas: false });
  await api.iniciarSesion("cualquiera@example.com", "x");
  const { filas, idiomas } = await api.contenido.listar();
  assert.equal(idiomas, false);
  assert.ok(filas.length && filas.every((f) => !("valor_en" in f) && !("valor_fr" in f)));
  await assert.rejects(api.contenido.guardar("hero.bajada", { valor: "Hola", valor_en: "Hello" }), (e) => {
    assert.equal(codigoConocido(e), "falta_idiomas");
    assert.match(mensajeError(e), /0005/);
    return true;
  });
  const nueva = await api.contenido.guardar("hero.bajada", { valor: "Hola", valor_en: "Hello" }, { idiomas: false });
  assert.equal(nueva.valor, "Hola");
  assert.ok(!("valor_en" in nueva));
});

test("fotos: publicar sube el objeto con ruta generada y crea la fila al final del espacio", async () => {
  const { api } = await dentro();
  const antes = fotosDeEspacio(await api.fotos.listar(), "living");
  const fila = await publicarFoto({ api, espacio: "living", blob: webp(), alt: "  Living  de noche ", visible: false,
    fotosEspacio: antes, hoy: HOY, azar: azarFijo([0xde, 0xad, 0xbe, 0xef]) });
  assert.equal(fila.ruta, "living/20261005-deadbeef.webp");
  assert.equal(fila.alt, "Living de noche");
  assert.equal(fila.visible, false);
  assert.equal(fila.orden, Math.max(...antes.map((f) => f.orden)) + 10);
  assert.ok(api.fotos._existe(fila.ruta));
});

test("fotos: si la ruta aleatoria ya existe (409) se prueba otra", async () => {
  const { api } = await dentro();
  await publicarFoto({ api, espacio: "cocina", blob: webp(), alt: "a", hoy: HOY, azar: azarFijo([1, 1, 1, 1]) });
  const f = await publicarFoto({ api, espacio: "cocina", blob: webp(), alt: "b", hoy: HOY,
    azar: azarFijo([1, 1, 1, 1], [2, 2, 2, 2]) });
  assert.equal(f.ruta, "cocina/20261005-02020202.webp");
});

test("fotos: si falla la fila, se borra el objeto recién subido (sin huérfanos)", async () => {
  const { api } = await dentro();
  let subida = null;
  const subir = api.fotos.subir;
  api.fotos.subir = async (ruta, blob) => { subida = ruta; return subir(ruta, blob); };
  api.fotos.crear = async () => { throw new ErrorApi({ estado: 403, codigo: "42501", mensaje: "new row violates row-level security policy" }); };
  await assert.rejects(publicarFoto({ api, espacio: "banos", blob: webp(), alt: "Baño", hoy: HOY, azar: azarFijo([3, 3, 3, 3]) }),
    (e) => codigoConocido(e) === "sin_permiso");
  assert.equal(subida, "banos/20261005-03030303.webp");
  assert.ok(!api.fotos._existe(subida));
});

test("fotos: qué errores de la fila son un rechazo definitivo (se borra el objeto) y cuáles no se saben", () => {
  for (const estado of [400, 401, 403, 404, 409, 413, 500, 503]) assert.equal(rechazoDefinitivo({ estado }), true, String(estado));
  for (const e of [{ estado: 0, codigo: "red" }, { codigo: "tiempo_agotado" }, { estado: 502 }, { estado: 504 },
    { codigo: "sin_filas" }, null, undefined]) {
    assert.equal(rechazoDefinitivo(e), false, JSON.stringify(e));
  }
});

test("fotos: si la fila se creó pero se perdió la respuesta (tiempo agotado), no se borra el archivo y es éxito (H4)", async () => {
  const { api } = await dentro();
  const crear = api.fotos.crear;
  let borrados = 0;
  const borrar = api.fotos.borrarObjeto;
  api.fotos.borrarObjeto = async (ruta) => { borrados++; return borrar(ruta); };
  api.fotos.crear = async (fila) => {
    await crear(fila);                                          // el INSERT se hizo…
    throw new ErrorApi({ codigo: "tiempo_agotado", mensaje: "tiempo_agotado", origen: "rest" });   // …y la respuesta no llegó
  };
  const antes = (await api.fotos.listar()).length;
  const fila = await publicarFoto({ api, espacio: "banos", blob: webp(), alt: "Baño", hoy: HOY, azar: azarFijo([6, 6, 6, 6]) });
  assert.equal(fila.ruta, "banos/20261005-06060606.webp");
  assert.equal(borrados, 0, "el archivo de una fila existente no se borra");
  assert.ok(api.fotos._existe(fila.ruta));
  const despues = await api.fotos.listar();
  assert.equal(despues.length, antes + 1, "una sola fila: nada que reintentar ni duplicar");
  assert.ok(despues.some((f) => f.id === fila.id));
});

test("fotos: si no hubo respuesta y la fila no aparece, se deja el archivo (huérfano invisible) y se informa (H4)", async () => {
  const { api } = await dentro();
  let subida = null;
  const subir = api.fotos.subir;
  api.fotos.subir = async (ruta, blob) => { subida = ruta; return subir(ruta, blob); };
  api.fotos.crear = async () => { throw new ErrorApi({ codigo: "red", mensaje: "red", origen: "rest" }); };
  await assert.rejects(publicarFoto({ api, espacio: "banos", blob: webp(), alt: "Baño", hoy: HOY, azar: azarFijo([7, 7, 7, 7]) }),
    (e) => e.codigo === "red");
  assert.ok(api.fotos._existe(subida), "sin saber si la fila existe, no se borra el archivo");

  // 502 del intermediario y, además, la consulta de comprobación también falla: igual no se borra
  api.fotos.crear = async () => { throw new ErrorApi({ estado: 502, mensaje: "Bad Gateway" }); };
  api.fotos.listar = async () => { throw new ErrorApi({ codigo: "red" }); };
  await assert.rejects(publicarFoto({ api, espacio: "banos", blob: webp(), alt: "Baño", hoy: HOY, azar: azarFijo([8, 8, 8, 8]) }),
    (e) => e.estado === 502);
  assert.ok(api.fotos._existe("banos/20261005-08080808.webp"));
});

test("fotos: validaciones antes de tocar Storage (alt, espacio, tipo, tamaño del bucket)", async () => {
  const { api } = await dentro();
  let llamadas = 0;
  const subir = api.fotos.subir;
  api.fotos.subir = async (...a) => { llamadas++; return subir(...a); };
  await assert.rejects(publicarFoto({ api, espacio: "living", blob: webp(), alt: "  ", hoy: HOY }), (e) => e.codigo === "alt_vacio");
  await assert.rejects(publicarFoto({ api, espacio: "../x", blob: webp(), alt: "a", hoy: HOY }), (e) => e.codigo === "id_invalido");
  await assert.rejects(publicarFoto({ api, espacio: "living", blob: new Blob(["<svg/>"], { type: "image/svg+xml" }), alt: "a", hoy: HOY }),
    (e) => codigoConocido(e) === "archivo_tipo");
  assert.equal(llamadas, 0);
  await assert.rejects(publicarFoto({ api, espacio: "living", blob: webp(5242881), alt: "a", hoy: HOY, azar: azarFijo([4, 4, 4, 4]) }),
    (e) => codigoConocido(e) === "archivo_grande");
});

test("fotos: quitar borra primero la fila y luego el objeto; si Storage falla, la fila ya no está y se avisa", async () => {
  const { api } = await dentro();
  const [f] = fotosDeEspacio(await api.fotos.listar(), "living");
  assert.deepEqual(await quitarFoto({ api, foto: f }), { objetoBorrado: true });
  assert.ok(!(await api.fotos.listar()).some((x) => x.id === f.id));
  assert.ok(!api.fotos._existe(f.ruta));

  const [g] = fotosDeEspacio(await api.fotos.listar(), "cocina");
  api.fotos.borrarObjeto = async () => { throw new ErrorApi({ codigo: "objeto_no_borrado", origen: "storage" }); };
  const r = await quitarFoto({ api, foto: g });
  assert.equal(r.objetoBorrado, false);
  assert.match(mensajeError(r.error), /Storage no borró/);
  assert.ok(!(await api.fotos.listar()).some((x) => x.id === g.id));

  api.fotos.eliminarFila = async () => { throw new ErrorApi({ codigo: "sin_filas" }); };
  let tocado = false;
  api.fotos.borrarObjeto = async () => { tocado = true; };
  await assert.rejects(quitarFoto({ api, foto: { id: "x", ruta: "living/x.webp" } }), (e) => e.codigo === "sin_filas");
  assert.ok(!tocado, "si la fila no se borró, el objeto no se toca");
});

test("fotos: reordenar guarda sólo los órdenes que cambian", async () => {
  const { api } = await dentro();
  await publicarFoto({ api, espacio: "living", blob: webp(), alt: "tercera", hoy: HOY,
    fotosEspacio: fotosDeEspacio(await api.fotos.listar(), "living"), azar: azarFijo([5, 5, 5, 5]) });
  const lista = fotosDeEspacio(await api.fotos.listar(), "living");
  assert.equal(lista.length, 3);
  const cambios = [];
  const actualizar = api.fotos.actualizar;
  api.fotos.actualizar = async (id, c) => { cambios.push([id, c]); return actualizar(id, c); };
  const nueva = await reordenarFoto({ api, fotosEspacio: lista, id: lista[2].id, delta: -1 });
  assert.deepEqual(nueva.map((f) => f.id), [lista[0].id, lista[2].id, lista[1].id]);
  assert.deepEqual(cambios, [[lista[2].id, { orden: 10 }], [lista[1].id, { orden: 20 }]]);
  const guardadas = fotosDeEspacio(await api.fotos.listar(), "living").map((f) => f.id);
  assert.deepEqual(guardadas, nueva.map((f) => f.id));
});
