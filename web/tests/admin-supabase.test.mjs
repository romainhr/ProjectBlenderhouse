// Pruebas del cliente mínimo de Supabase (web/src/admin/js/supabase.js), de la sesión (sesion.js) y de la API del
// portal (api.js) con fetch, almacén, reloj y temporizador falsos: ninguna llamada sale a la red.
//   cd web && npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { crearApi, COLUMNAS_RESERVA } from "../src/admin/js/api.js";
import { codigoConocido, mensajeError } from "../src/admin/js/errores.js";
import {
  CLAVE_ALMACEN, debeRefrescar, leerSesion, msHastaRefresco, normalizarSesion,
} from "../src/admin/js/sesion.js";
import { REINTENTO_REFRESCO_MS, crearCliente } from "../src/admin/js/supabase.js";

const URL_SB = "https://abcdefghijklmnopqrst.supabase.co";
const CLAVE = "sb_publishable_clave_de_prueba_no_real_000";
const T0 = 1790000000000;                      // ms (reloj falso)
const UUID = "0f8fad5b-d9cb-469f-a165-70867728950e";

class AlmacenFalso {
  constructor() { this.m = new Map(); }
  getItem(k) { return this.m.has(k) ? this.m.get(k) : null; }
  setItem(k, v) { this.m.set(k, String(v)); }
  removeItem(k) { this.m.delete(k); }
  clear() { this.m.clear(); }
}

/** fetch falso: responde en orden lo preparado y guarda cada llamada. */
function fetchFalso(respuestas) {
  const llamadas = [];
  const f = async (url, init = {}) => {
    llamadas.push({ url, metodo: init.method, cabeceras: init.headers || {}, cuerpo: init.body, init });
    const r = respuestas.shift();
    if (!r) throw new Error(`sin respuesta preparada para ${url}`);
    if (r === "red") throw new TypeError("Failed to fetch");
    const { estado = 200, json } = r;
    const cuerpo = estado === 204 || json === undefined ? null : JSON.stringify(json);
    return new Response(cuerpo, { status: estado, headers: json === undefined ? {} : { "content-type": "application/json; charset=utf-8" } });
  };
  f.llamadas = llamadas;
  f.pendientes = respuestas;
  return f;
}

function temporizadorFalso() {
  const t = { programados: new Map(), n: 0 };
  t.poner = (fn, ms) => { t.n += 1; t.programados.set(t.n, { fn, ms }); return t.n; };
  t.quitar = (id) => t.programados.delete(id);
  t.ultimo = () => [...t.programados.values()].at(-1);
  return t;
}

const tokens = (n, extra = {}) => ({
  access_token: `acceso-${n}`, token_type: "bearer", expires_in: 3600, expires_at: 1, refresh_token: `refresco-${n}`,
  user: { id: "11111111-1111-4111-8111-111111111111", email: "dueno@example.com", user_metadata: { nombre: "no guardar" } },
  ...extra,
});

function armar(respuestas, { reloj = { t: T0 }, almacen = new AlmacenFalso() } = {}) {
  const fetch = fetchFalso(respuestas);
  const temporizador = temporizadorFalso();
  const perdidas = [];
  const cliente = crearCliente({
    url: URL_SB + "/", clave: CLAVE, almacen, fetch, ahora: () => reloj.t, temporizador,
    alPerderSesion: (m) => perdidas.push(m),
  });
  return { cliente, fetch, temporizador, perdidas, almacen, reloj };
}

// ---------------------------------------------------------------------------------------------- sesión (pura)
test("sesión: vencimiento con expires_in y el reloj local (no con el reloj del servidor) y sin metadatos", () => {
  const s = normalizarSesion(tokens(1), T0);
  assert.equal(s.expires_at, T0 / 1000 + 3600, "expires_at del servidor (1) se ignora si hay expires_in");
  assert.deepEqual(s.usuario, { id: "11111111-1111-4111-8111-111111111111", email: "dueno@example.com" });
  assert.equal(s.modo, "real");
  assert.equal(normalizarSesion({ ...tokens(1), expires_in: undefined, expires_at: 1790003600 }, T0).expires_at, 1790003600);
  assert.equal(normalizarSesion({ access_token: "x" }, T0), null);
  assert.ok(!debeRefrescar(s, T0));
  assert.ok(debeRefrescar(s, T0 + (3600 - 60) * 1000));
  assert.equal(msHastaRefresco(s, T0), (3600 - 60) * 1000);
  assert.equal(msHastaRefresco(s, T0 + 4000 * 1000), 0);
});

// ---------------------------------------------------------------------------------------------- login
test("login: POST /auth/v1/token?grant_type=password con apikey y sin Authorization; sesión en el almacén", async () => {
  const { cliente, fetch, almacen, temporizador } = armar([{ json: tokens(1) }]);
  const s = await cliente.iniciarSesion("  dueno@example.com ", "clave-de-prueba");
  const [ll] = fetch.llamadas;
  assert.equal(ll.url, `${URL_SB}/auth/v1/token?grant_type=password`);
  assert.equal(ll.metodo, "POST");
  assert.equal(ll.cabeceras.apikey, CLAVE);
  assert.equal(ll.cabeceras.Authorization, undefined);
  assert.deepEqual(JSON.parse(ll.cuerpo), { email: "dueno@example.com", password: "clave-de-prueba" });
  assert.equal(ll.init.credentials, "omit");
  assert.equal(s.access_token, "acceso-1");
  const guardada = JSON.parse(almacen.getItem(CLAVE_ALMACEN));
  assert.equal(guardada.refresh_token, "refresco-1");
  assert.ok(!JSON.stringify(guardada).includes("no guardar"), "no guarda metadatos del usuario");
  assert.ok(!JSON.stringify(guardada).includes("clave-de-prueba"), "nunca guarda la contraseña");
  assert.equal(temporizador.ultimo().ms, (3600 - 60) * 1000, "refresco programado 60 s antes de vencer");
});

test("login: credenciales malas -> mensaje claro y nada guardado", async () => {
  const { cliente, almacen } = armar([{ estado: 400, json: { code: 400, error_code: "invalid_credentials", msg: "Invalid login credentials" } }]);
  await assert.rejects(cliente.iniciarSesion("a@example.com", "x"), (e) => codigoConocido(e) === "credenciales");
  assert.equal(almacen.getItem(CLAVE_ALMACEN), null);
  assert.equal(cliente.sesion(), null);
});

// ---------------------------------------------------------------------------------------------- llamadas con sesión
test("REST: apikey + Authorization Bearer <access_token del usuario>", async () => {
  const { cliente, fetch } = armar([{ json: tokens(1) }, { json: [{ id: 1 }] }]);
  await cliente.iniciarSesion("dueno@example.com", "x");
  const datos = await cliente.rest("/reservas?select=id");
  assert.deepEqual(datos, [{ id: 1 }]);
  const ll = fetch.llamadas[1];
  assert.equal(ll.url, `${URL_SB}/rest/v1/reservas?select=id`);
  assert.equal(ll.metodo, "GET");
  assert.equal(ll.cabeceras.apikey, CLAVE);
  assert.equal(ll.cabeceras.Authorization, "Bearer acceso-1");
  assert.equal(ll.cabeceras["Content-Type"], undefined, "GET sin cuerpo");
  assert.equal(ll.init.cache, "no-store");
});

test("401: refresca una vez y reintenta con el token nuevo", async () => {
  const { cliente, fetch, almacen } = armar([
    { json: tokens(1) },
    { estado: 401, json: { code: "PGRST303", message: "JWT expired" } },
    { json: tokens(2) },
    { json: [{ ok: true }] },
  ]);
  await cliente.iniciarSesion("dueno@example.com", "x");
  const datos = await cliente.rest("/contenido?select=clave");
  assert.deepEqual(datos, [{ ok: true }]);
  assert.equal(fetch.llamadas[2].url, `${URL_SB}/auth/v1/token?grant_type=refresh_token`);
  assert.deepEqual(JSON.parse(fetch.llamadas[2].cuerpo), { refresh_token: "refresco-1" });
  assert.equal(fetch.llamadas[2].cabeceras.Authorization, undefined);
  assert.equal(fetch.llamadas[3].cabeceras.Authorization, "Bearer acceso-2");
  assert.equal(leerSesion(almacen).refresh_token, "refresco-2");
});

test("401 y refresco rechazado: vuelve al login, borra el almacén y avisa «sesión vencida»", async () => {
  const { cliente, almacen, perdidas } = armar([
    { json: tokens(1) },
    { estado: 401, json: { code: "PGRST303", message: "JWT expired" } },
    { estado: 400, json: { error_code: "refresh_token_not_found", msg: "Invalid Refresh Token: Refresh Token Not Found" } },
  ]);
  await cliente.iniciarSesion("dueno@example.com", "x");
  almacen.setItem("otra-cosa", "1");
  await assert.rejects(cliente.rest("/reservas"), (e) => e.codigo === "sesion_vencida" && /venció/.test(mensajeError(e)));
  assert.deepEqual(perdidas, ["sesion_vencida"]);
  assert.equal(almacen.getItem(CLAVE_ALMACEN), null);
  assert.equal(almacen.getItem("otra-cosa"), null, "cerrar la sesión borra todo el sessionStorage");
  assert.equal(cliente.sesion(), null);
});

test("401 dos veces seguidas (aun con token nuevo): no reintenta en bucle", async () => {
  const { cliente, fetch, perdidas } = armar([
    { json: tokens(1) },
    { estado: 401, json: { message: "JWT expired" } },
    { json: tokens(2) },
    { estado: 401, json: { message: "JWT expired" } },
  ]);
  await cliente.iniciarSesion("dueno@example.com", "x");
  await assert.rejects(cliente.rest("/reservas"), (e) => e.codigo === "sesion_vencida");
  assert.equal(fetch.llamadas.length, 4);
  assert.deepEqual(perdidas, ["sesion_vencida"]);
});

test("refresco antes de vencer: si falta menos de un minuto, refresca primero; dos llamadas a la vez, un solo refresco", async () => {
  const reloj = { t: T0 };
  const { cliente, fetch } = armar([{ json: tokens(1) }, { json: tokens(2) }, { json: ["a"] }, { json: ["b"] }], { reloj });
  await cliente.iniciarSesion("dueno@example.com", "x");
  reloj.t = T0 + (3600 - 30) * 1000;
  const [a, b] = await Promise.all([cliente.rest("/a"), cliente.rest("/b")]);
  assert.deepEqual([a, b], [["a"], ["b"]]);
  const refrescos = fetch.llamadas.filter((l) => l.url.includes("grant_type=refresh_token"));
  assert.equal(refrescos.length, 1, "el refresh_token se usa una sola vez");
  assert.ok(fetch.llamadas.slice(2).every((l) => l.cabeceras.Authorization === "Bearer acceso-2"));
});

test("el temporizador programado refresca solo; si falla la red conserva la sesión y reintenta en 30 s", async () => {
  const { cliente, temporizador, perdidas } = armar([{ json: tokens(1) }, "red", { json: tokens(2) }]);
  await cliente.iniciarSesion("dueno@example.com", "x");
  temporizador.ultimo().fn();
  await new Promise((ok) => setTimeout(ok, 10));
  assert.equal(cliente.sesion().access_token, "acceso-1", "sin red, la sesión sigue");
  assert.deepEqual(perdidas, []);
  assert.equal(temporizador.ultimo().ms, REINTENTO_REFRESCO_MS);
  temporizador.ultimo().fn();
  await new Promise((ok) => setTimeout(ok, 10));
  assert.equal(cliente.sesion().access_token, "acceso-2");
});

test("sin sesión, una llamada avisa para volver al login sin tocar la red", async () => {
  const { cliente, fetch, perdidas } = armar([]);
  await assert.rejects(cliente.rest("/reservas"), (e) => e.codigo === "sesion_vencida");
  assert.equal(fetch.llamadas.length, 0);
  assert.deepEqual(perdidas, ["sesion_vencida"]);
});

test("error de red: código «red» y mensaje claro", async () => {
  const { cliente } = armar([{ json: tokens(1) }, "red"]);
  await cliente.iniciarSesion("dueno@example.com", "x");
  await assert.rejects(cliente.rest("/reservas"), (e) => e.codigo === "red" && /conectar/.test(mensajeError(e)));
  assert.ok(cliente.sesion(), "un fallo de red no cierra la sesión");
});

// ---------------------------------------------------------------------------------------------- cierre y restauración
test("cerrar sesión: POST /auth/v1/logout con el token y borra el sessionStorage aunque falle la red", async () => {
  const a = armar([{ json: tokens(1) }, { estado: 204 }]);
  await a.cliente.iniciarSesion("dueno@example.com", "x");
  a.almacen.setItem("borrador", "algo");
  await a.cliente.cerrarSesion();
  const ll = a.fetch.llamadas[1];
  assert.equal(ll.url, `${URL_SB}/auth/v1/logout`);
  assert.equal(ll.metodo, "POST");
  assert.equal(ll.cabeceras.Authorization, "Bearer acceso-1");
  assert.equal(ll.cabeceras.apikey, CLAVE);
  assert.equal(a.almacen.m.size, 0);
  assert.equal(a.temporizador.programados.size, 0, "sin refresco pendiente");

  const b = armar([{ json: tokens(1) }, "red"]);
  await b.cliente.iniciarSesion("dueno@example.com", "x");
  await b.cliente.cerrarSesion();
  assert.equal(b.almacen.m.size, 0);
  assert.equal(b.cliente.sesion(), null);
});

test("restaurar: sólo sesiones del modo real; si está por vencer la refresca", async () => {
  const almacen = new AlmacenFalso();
  almacen.setItem(CLAVE_ALMACEN, JSON.stringify({ ...normalizarSesion(tokens(1), T0), modo: "simulado" }));
  assert.equal(await armar([], { almacen }).cliente.restaurar(), null, "una sesión simulada no sirve en modo real");

  almacen.setItem(CLAVE_ALMACEN, JSON.stringify(normalizarSesion(tokens(1), T0)));
  const vigente = armar([], { almacen });
  assert.equal((await vigente.cliente.restaurar()).access_token, "acceso-1");
  assert.equal(vigente.fetch.llamadas.length, 0);

  const vieja = armar([{ json: tokens(2) }], { almacen, reloj: { t: T0 + 7200 * 1000 } });
  assert.equal((await vieja.cliente.restaurar()).access_token, "acceso-2");

  almacen.setItem(CLAVE_ALMACEN, "{no es json");
  assert.equal(await armar([], { almacen }).cliente.restaurar(), null);
});

// ---------------------------------------------------------------------------------------------- Storage
test("Storage: subir con POST /storage/v1/object/fotos/<ruta>, x-upsert y FormData (sin Content-Type a mano)", async () => {
  const { cliente, fetch } = armar([{ json: tokens(1) }, { json: { Key: "fotos/living/20260926-0aff007b.webp" } }]);
  await cliente.iniciarSesion("dueno@example.com", "x");
  const blob = new Blob([new Uint8Array([1, 2, 3])], { type: "image/webp" });
  await cliente.subirObjeto("fotos", "living/20260926-0aff007b.webp", blob);
  const ll = fetch.llamadas[1];
  assert.equal(ll.url, `${URL_SB}/storage/v1/object/fotos/living/20260926-0aff007b.webp`);
  assert.equal(ll.metodo, "POST");
  assert.equal(ll.cabeceras["x-upsert"], "false");
  assert.equal(ll.cabeceras.Authorization, "Bearer acceso-1");
  assert.equal(ll.cabeceras["Content-Type"], undefined, "el navegador pone multipart/form-data con su boundary");
  assert.ok(ll.cuerpo instanceof FormData);
  assert.equal(ll.cuerpo.get("cacheControl"), "31536000");
  const archivo = ll.cuerpo.get("");
  assert.equal(archivo.type, "image/webp");
  assert.equal(archivo.name, "20260926-0aff007b.webp", "nombre generado, nunca el original");
});

test("Storage: borrar con DELETE /storage/v1/object/fotos y { prefixes } ; URL pública", async () => {
  const { cliente, fetch } = armar([{ json: tokens(1) }, { json: [{ name: "living/x.webp" }] }]);
  await cliente.iniciarSesion("dueno@example.com", "x");
  await cliente.borrarObjetos("fotos", ["living/x.webp"]);
  const ll = fetch.llamadas[1];
  assert.equal(ll.url, `${URL_SB}/storage/v1/object/fotos`);
  assert.equal(ll.metodo, "DELETE");
  assert.deepEqual(JSON.parse(ll.cuerpo), { prefixes: ["living/x.webp"] });
  assert.equal(cliente.urlPublica("fotos", "living/x.webp"), `${URL_SB}/storage/v1/object/public/fotos/living/x.webp`);
});

// ---------------------------------------------------------------------------------------------- API del portal
async function apiCon(respuestas) {
  const a = armar([{ json: tokens(1) }, ...respuestas]);
  await a.cliente.iniciarSesion("dueno@example.com", "x");
  return { api: crearApi(a.cliente), fetch: a.fetch, ultima: () => a.fetch.llamadas.at(-1) };
}

test("API reservas: listar, cambiar estado (sólo la columna estado), nota y eliminar", async () => {
  const fila = { id: UUID, estado: "confirmada" };
  const { api, ultima } = await apiCon([{ json: [] }, { json: [fila] }, { json: [fila] }, { json: [{ id: UUID }] }]);
  await api.reservas.listar();
  assert.equal(ultima().url, `${URL_SB}/rest/v1/reservas?select=${COLUMNAS_RESERVA}&order=entrada.desc`);
  assert.ok(COLUMNAS_RESERVA.includes("nota_interna") && COLUMNAS_RESERVA.includes("email"));

  assert.deepEqual(await api.reservas.cambiarEstado(UUID, "confirmada"), fila);
  assert.equal(ultima().metodo, "PATCH");
  assert.equal(ultima().url, `${URL_SB}/rest/v1/reservas?id=eq.${UUID}&select=${COLUMNAS_RESERVA}`);
  assert.deepEqual(JSON.parse(ultima().cuerpo), { estado: "confirmada" }, "el grant por columnas sólo deja estado y nota");
  assert.equal(ultima().cabeceras.Prefer, "return=representation");
  assert.equal(ultima().cabeceras["Content-Type"], "application/json");

  await api.reservas.guardarNota(UUID, null);
  assert.deepEqual(JSON.parse(ultima().cuerpo), { nota_interna: null });

  await api.reservas.eliminar(UUID);
  assert.equal(ultima().metodo, "DELETE");
  assert.equal(ultima().url, `${URL_SB}/rest/v1/reservas?id=eq.${UUID}&select=id`);
});

test("API reservas: 0 filas (RLS o ya borrada) y choque de fechas se informan claro; id inválido no llama", async () => {
  const { api, fetch } = await apiCon([
    { json: [] },
    { estado: 409, json: { code: "23P01", message: 'conflicting key value violates exclusion constraint "reservas_sin_solape"' } },
  ]);
  await assert.rejects(api.reservas.cambiarEstado(UUID, "confirmada"), (e) => codigoConocido(e) === "sin_filas");
  await assert.rejects(api.reservas.cambiarEstado(UUID, "confirmada"), (e) => /chocan/.test(mensajeError(e)));
  const n = fetch.llamadas.length;
  await assert.rejects(api.reservas.cambiarEstado("1 or 1=1", "confirmada"), (e) => e.codigo === "id_invalido");
  await assert.rejects(api.reservas.eliminar("*"), (e) => e.codigo === "id_invalido");
  assert.equal(fetch.llamadas.length, n);
});

test("API contenido y fotos: rutas, filtros y sólo los campos permitidos", async () => {
  const { api, ultima, fetch } = await apiCon([
    { json: [{ clave: "tarifa.noche", valor: "60000" }] },
    { json: [{ id: UUID, orden: 10 }] },
    { json: [{ id: UUID }] },
    { json: [] },
    { json: true },
    { estado: 404, json: { code: "PGRST202", message: "Could not find the function public.es_propietario" } },
  ]);
  await api.contenido.guardar("tarifa.noche", "60000");
  assert.equal(ultima().url, `${URL_SB}/rest/v1/contenido?clave=eq.tarifa.noche&select=clave,valor,tipo,etiqueta,grupo,orden,actualizado`);
  assert.deepEqual(JSON.parse(ultima().cuerpo), { valor: "60000" });
  const n = fetch.llamadas.length;
  await assert.rejects(api.contenido.guardar("x&clave=neq.y", "1"), (e) => e.codigo === "id_invalido");
  assert.equal(fetch.llamadas.length, n);

  await api.fotos.actualizar(UUID, { orden: 10, ruta: "../../otro", espacio: "x" });
  assert.deepEqual(JSON.parse(ultima().cuerpo), { orden: 10 });

  await api.fotos.eliminarFila(UUID);
  assert.equal(ultima().url, `${URL_SB}/rest/v1/fotos?id=eq.${UUID}&select=id`);

  await assert.rejects(api.fotos.borrarObjeto("living/x.webp"), (e) => e.codigo === "objeto_no_borrado");

  assert.equal(await api.esPropietario(), true);
  assert.equal(ultima().url, `${URL_SB}/rest/v1/rpc/es_propietario`);
  assert.equal(ultima().metodo, "POST");
  await assert.rejects(api.esPropietario(), (e) => codigoConocido(e) === "falta_migracion");
});
