// Decisiones de estado de las vistas del portal (vista-*.js y app.js) pasadas a funciones puras, para probarlas sin
// DOM: apertura de reservas y nota sin guardar, reserva que desaparece, hash de navegación, cierre de sesión, un solo
// envío o carga a la vez, orden de fotos y borradores de descripción.
//   cd web && npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { publicarFoto, reordenarFoto } from "../src/admin/js/acciones-fotos.js";
import { crearApiSimulada } from "../src/admin/js/api-simulada.js";
import { anotarBorrador, aplicarOrden, fotosDeEspacio, moverFoto, podarBorradores } from "../src/admin/js/logica-fotos.js";
import { VISTAS, VISTA_INICIAL, crearCierre, vistaDeHash } from "../src/admin/js/logica-portal.js";
import { decidirApertura, resolverSeleccion } from "../src/admin/js/logica-reservas.js";
import { unaALaVez } from "../src/admin/js/util.js";

const HOY = "2026-10-05";
const pausa = () => new Promise((r) => setImmediate(r));

class AlmacenFalso {
  constructor() { this.m = new Map(); }
  getItem(k) { return this.m.has(k) ? this.m.get(k) : null; }
  setItem(k, v) { this.m.set(k, String(v)); }
  removeItem(k) { this.m.delete(k); }
  clear() { this.m.clear(); }
}

async function dentro() {
  const api = crearApiSimulada({ almacen: new AlmacenFalso(), retardo: 0, hoy: HOY });
  await api.iniciarSesion("cualquiera@example.com", "cualquier-cosa");
  return api;
}

/** Promesa que se resuelve a mano. */
function diferida() {
  let resolver, rechazar;
  const promesa = new Promise((a, b) => { resolver = a; rechazar = b; });
  return { promesa, resolver, rechazar };
}

// ---------------------------------------------------------------------------------------------- reservas (H1, H9)
test("reservas: pulsar la reserva que ya está abierta sólo enfoca y no descarta la nota (H1)", () => {
  assert.equal(decidirApertura({ id: "a", seleccion: "a", notaSucia: true }), "enfocar", "la nota a medio escribir se conserva");
  assert.equal(decidirApertura({ id: "a", seleccion: "a", notaSucia: false }), "enfocar");
  assert.equal(decidirApertura({ id: "b", seleccion: "a", notaSucia: true }), "confirmar");
  assert.equal(decidirApertura({ id: "b", seleccion: "a", notaSucia: false }), "abrir");
  assert.equal(decidirApertura({ id: "b", seleccion: null, notaSucia: false }), "abrir");
});

test("reservas: si la reserva abierta ya no está al actualizar, se cierra y no queda nota «sin guardar» (H9)", () => {
  const lista = [{ id: "a" }, { id: "b" }];
  const sigue = resolverSeleccion(lista, "a", true);
  assert.equal(sigue.reserva, lista[0]);
  assert.deepEqual([sigue.seleccion, sigue.notaSucia, sigue.desaparecida, sigue.notaPerdida], ["a", true, false, false]);

  const borrada = resolverSeleccion([{ id: "b" }], "a", true);        // otra sesión borró «a»
  assert.equal(borrada.reserva, null);
  assert.equal(borrada.seleccion, null);
  assert.equal(borrada.notaSucia, false, "hayCambios() ya no pide confirmaciones falsas");
  assert.equal(borrada.desaparecida, true);
  assert.equal(borrada.notaPerdida, true, "se avisa que la nota se descartó");
  assert.equal(resolverSeleccion([{ id: "b" }], "a", false).notaPerdida, false);

  const nada = resolverSeleccion(lista, null, false);                 // sin reserva abierta: nada que avisar
  assert.deepEqual([nada.reserva, nada.seleccion, nada.desaparecida], [null, null, false]);
});

// ---------------------------------------------------------------------------------------------- navegación (H2)
test("navegación: sólo los hash de vista cambian de vista; «Saltar al contenido» no lleva a Reservas (H2)", () => {
  assert.deepEqual(VISTAS, ["reservas", "textos", "fotos"]);
  for (const v of VISTAS) assert.equal(vistaDeHash(`#${v}`), v);
  assert.equal(vistaDeHash("#principal"), null, "el enlace de salto no es navegación");
  assert.equal(vistaDeHash("#otra-cosa"), null);
  assert.equal(vistaDeHash("#Reservas"), null);
  assert.equal(vistaDeHash(""), VISTA_INICIAL, "sin hash (p. ej. al volver atrás al inicio) se ve la vista inicial");
  assert.equal(vistaDeHash("#"), VISTA_INICIAL);
  assert.equal(vistaDeHash(undefined), VISTA_INICIAL);
});

// ---------------------------------------------------------------------------------------------- cierre de sesión (H3)
test("cierre de sesión: limpia la pantalla sin esperar a Auth y un ingreso nuevo espera la revocación (H3)", async () => {
  const logout = diferida();
  const orden = [];
  const api = { cerrarSesion: () => { orden.push("cerrarSesion"); return logout.promesa; } };
  const cierre = crearCierre(api);
  await cierre.esperar();                                  // sin cierre previo no hay nada que esperar

  let terminada = false;
  const revocacion = cierre.cerrar(() => orden.push("limpiar"));
  revocacion.then(() => { terminada = true; });
  assert.deepEqual(orden, ["cerrarSesion", "limpiar"], "la pantalla se limpia en el mismo turno, antes de la respuesta");
  let ingreso = false;
  cierre.esperar().then(() => { ingreso = true; });
  await pausa();
  assert.equal(terminada, false);
  assert.equal(ingreso, false, "el ingreso nuevo sigue esperando al logout");
  logout.rechazar(new Error("red"));                        // aunque Auth falle, la revocación termina sin error
  await pausa();
  assert.equal(terminada, true);
  assert.equal(ingreso, true);

  const cierreRoto = crearCierre({ cerrarSesion: () => { throw new Error("síncrono"); } });
  let limpio = false;
  await cierreRoto.cerrar(() => { limpio = true; });
  assert.ok(limpio, "si cerrarSesion lanza, igual se limpia la pantalla");
});

// ---------------------------------------------------------------------------------------------- una vez a la vez (H5, H10)
test("unaALaVez: dos envíos mientras se reduce la imagen suben una sola foto (H5)", async () => {
  const api = await dentro();
  const antes = (await api.fotos.listar()).length;
  const preparando = diferida();
  let publicaciones = 0;
  const enviar = unaALaVez(async () => {
    await preparando.promesa;                                // «Preparando la imagen…»
    publicaciones++;
    return publicarFoto({ api, espacio: "living", blob: new Blob([new Uint8Array(8)], { type: "image/webp" }), alt: "Una",
      fotosEspacio: fotosDeEspacio(await api.fotos.listar(), "living"), hoy: HOY,
      azar: () => new Uint8Array([publicaciones, 7, 7, 7]) });
  });
  const primero = enviar();
  const segundo = enviar();                                  // segundo clic en «Agregar foto»
  assert.equal(segundo, primero, "el segundo envío recibe la misma promesa");
  assert.equal(enviar.ocupada(), true);
  preparando.resolver();
  await primero;
  assert.equal(publicaciones, 1);
  assert.equal((await api.fotos.listar()).length, antes + 1, "una sola fila nueva");
  assert.equal(enviar.ocupada(), false);
  await enviar();                                            // terminado el primero, se puede volver a enviar
  assert.equal(publicaciones, 2);
});

test("unaALaVez: soltar() al cerrar sesión deja cargar de nuevo aunque la carga vieja siga colgada (H10)", async () => {
  const cargas = [];
  const cargaInicial = unaALaVez(() => {
    const d = diferida();
    cargas.push(d);
    return d.promesa;
  });
  const vieja = cargaInicial();
  assert.equal(cargaInicial(), vieja, "mostrar() dos veces: una sola carga");
  assert.equal(cargas.length, 1);

  cargaInicial.soltar();                                     // reiniciar(): se cerró la sesión
  assert.equal(cargaInicial.ocupada(), false);
  const nueva = cargaInicial();                              // nuevo ingreso: mostrar() vuelve a cargar
  assert.notEqual(nueva, vieja);
  assert.equal(cargas.length, 2);

  cargas[0].resolver("respuesta vieja");                     // la vieja termina después…
  await vieja;
  assert.equal(cargaInicial.ocupada(), true, "…y no suelta a la nueva");
  assert.equal(cargaInicial(), nueva);
  cargas[1].resolver("respuesta nueva");
  assert.equal(await nueva, "respuesta nueva");
  assert.equal(cargaInicial.ocupada(), false);
});

test("unaALaVez: un error, incluso síncrono, libera para el próximo intento", async () => {
  let n = 0;
  const f = unaALaVez(() => {
    n++;
    if (n === 1) throw new Error("síncrono");
    if (n === 2) return Promise.reject(new Error("asíncrono"));
    return "ok";
  });
  await assert.rejects(f(), /síncrono/);
  await assert.rejects(f(), /asíncrono/);
  assert.equal(await f(), "ok");
});

// ---------------------------------------------------------------------------------------------- orden de fotos (H6)
test("fotos: dos «Subir» seguidos calculados con la lista actual no dejan órdenes repetidos (H6)", async () => {
  const api = await dentro();
  for (const [i, alt] of ["A", "B", "C"].entries()) {
    await publicarFoto({ api, espacio: "dorm1", blob: new Blob([new Uint8Array(8)], { type: "image/webp" }), alt,
      fotosEspacio: fotosDeEspacio(await api.fotos.listar(), "dorm1"), hoy: HOY, azar: () => new Uint8Array([i, 1, 2, 3]) });
  }
  let fotos = await api.fotos.listar();
  const id = (alt) => fotos.find((f) => f.espacio === "dorm1" && f.alt === alt).id;
  const ordenes = (lista) => Object.fromEntries(fotosDeEspacio(lista, "dorm1").map((f) => [f.alt, f.orden]));
  assert.deepEqual(ordenes(fotos), { A: 0, B: 10, C: 20 });
  const pintada = fotosDeEspacio(fotos, "dorm1");             // la lista del momento de pintar las tarjetas

  // como hace ahora mover(): cada clic calcula con fotosDeEspacio(fotos, espacio) y aplicarOrden guarda el resultado
  fotos = aplicarOrden(fotos, await reordenarFoto({ api, fotosEspacio: fotosDeEspacio(fotos, "dorm1"), id: id("B"), delta: -1 }));
  fotos = aplicarOrden(fotos, await reordenarFoto({ api, fotosEspacio: fotosDeEspacio(fotos, "dorm1"), id: id("C"), delta: -1 }));
  assert.deepEqual(ordenes(fotos), { B: 0, C: 10, A: 20 });
  assert.deepEqual(ordenes(await api.fotos.listar()), { B: 0, C: 10, A: 20 }, "la base queda igual, sin empates");

  // el cálculo viejo: el segundo clic parte de la lista pintada y deja A y C con el mismo orden (el caso del hallazgo)
  const base = new Map(pintada.map((f) => [f.alt, f.orden]));
  for (const c of moverFoto(pintada, id("B"), -1).cambios) base.set(pintada.find((f) => f.id === c.id).alt, c.orden);
  for (const c of moverFoto(pintada, id("C"), -1).cambios) base.set(pintada.find((f) => f.id === c.id).alt, c.orden);
  assert.deepEqual(Object.fromEntries(base), { A: 10, B: 20, C: 10 });
});

test("fotos: aplicarOrden copia sólo los órdenes nuevos y no toca otros campos ni otros espacios", () => {
  const fotos = [
    { id: "1", espacio: "living", orden: 0, alt: "uno", visible: true },
    { id: "2", espacio: "living", orden: 10, alt: "dos", visible: false },
    { id: "3", espacio: "cocina", orden: 0, alt: "tres", visible: true },
  ];
  const r = aplicarOrden(fotos, [{ id: "2", orden: 0, alt: "no se copia" }, { id: "1", orden: 10 }]);
  assert.deepEqual(r.map((f) => [f.id, f.orden, f.alt]), [["1", 10, "uno"], ["2", 0, "dos"], ["3", 0, "tres"]]);
  assert.equal(fotos[0].orden, 0, "no modifica la lista original");
  assert.deepEqual(aplicarOrden(fotos, []), fotos);
});

// ---------------------------------------------------------------------------------------------- borradores (H8)
test("fotos: descripciones sin guardar cuentan como cambios, también en otro espacio, hasta guardarlas (H8)", () => {
  const borradores = new Map();
  assert.equal(anotarBorrador(borradores, "1", "Living nuevo", "Living"), true);
  assert.equal(borradores.size, 1, "hayCambios() ve el borrador");
  assert.equal(anotarBorrador(borradores, "1", "  Living ", "Living"), false, "volver al texto guardado lo quita");
  assert.equal(borradores.size, 0);
  assert.equal(anotarBorrador(borradores, "1", "Living  de   noche", "Living de noche"), false,
    "mismo texto que dejaría validarAlt: no hay nada que guardar");
  anotarBorrador(borradores, "1", "Living con sol", "Living");
  anotarBorrador(borradores, "2", "Cocina", "Cocina vieja");
  anotarBorrador(borradores, "3", "Balcón", "Balcón viejo");

  // al repintar (cambio de espacio, recarga o tras guardar): se conservan los que siguen pendientes
  const fotos = [
    { id: "1", espacio: "living", alt: "Living" },                  // sigue distinto: se conserva (otro espacio incluido)
    { id: "2", espacio: "cocina", alt: "Cocina" },                  // ya se guardó: se quita
  ];                                                                 // la 3 se borró: se quita
  podarBorradores(borradores, fotos);
  assert.deepEqual([...borradores.keys()], ["1"]);
  assert.equal(borradores.get("1"), "Living con sol", "el texto escrito se conserva tal cual");
  podarBorradores(borradores, []);
  assert.equal(borradores.size, 0);
});
