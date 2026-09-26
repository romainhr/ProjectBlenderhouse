// Modo simulado del portal: la misma API que api.js, con datos de EJEMPLO en memoria y un login falso que acepta
// cualquier correo y contraseña no vacíos. Sólo se activa en un host local (modo.js). Imita las reglas de la base que el
// portal debe saber mostrar: choque de fechas (23P01), checks (23514), filas inexistentes y límites del bucket.
// Todos los nombres, correos y teléfonos son inventados (dominio reservado example.com).
import { hoyIso, solapa, sumarDias } from "../../js/reserva-logica.js";
import { ErrorApi } from "./errores.js";
import { ACTIVOS, ESTADOS, LIMITE_NOTA } from "./logica-reservas.js";
import { validarValor } from "./logica-contenido.js";
import { ESPACIOS, MAX_SUBIDA, TIPOS_ACEPTADOS, nombreEspacio, validarAlt } from "./logica-fotos.js";
import { borrarSesion, guardarSesion, leerSesion } from "./sesion.js";
import { largo } from "./util.js";

let serie = 0;
function idFalso() {
  serie += 1;
  return `00000000-0000-4000-8000-${String(serie).padStart(12, "0")}`;
}

function copia(x) {
  return JSON.parse(JSON.stringify(x));
}

/** Imagen de ejemplo (SVG como data: URI) con el nombre del espacio; el texto sale de ESPACIOS, no del usuario. */
export function imagenEjemplo(espacio, tono) {
  const nombre = nombreEspacio(espacio).replace(/[<>&"']/g, "");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000">` +
    `<rect width="1600" height="1000" fill="${tono}"/><rect x="60" y="60" width="1480" height="880" fill="none" ` +
    `stroke="#fff" stroke-opacity=".5" stroke-width="4"/><text x="800" y="530" font-family="Georgia,serif" ` +
    `font-size="96" fill="#fff" text-anchor="middle">${nombre} (ejemplo)</text></svg>`;
  return "data:image/svg+xml," + encodeURIComponent(svg);
}

export function datosEjemplo(hoy = hoyIso()) {
  const d = (n) => sumarDias(hoy, n);
  const creada = (n) => `${d(n)}T15:20:00.000Z`;
  const r = (entrada, salida, extra) => ({
    id: idFalso(), codigo: "SIM" + String(serie).padStart(5, "0"), creada: creada(-5), entrada, salida,
    huespedes: 2, nombre: "", email: "", telefono: null, mensaje: null, estado: "pendiente", nota_interna: null,
    actualizada: null, ...extra,
  });
  const reservas = [
    r(d(3), d(6), { nombre: "Ana Ejemplo", email: "ana@example.com", telefono: "+56 9 1234 5678",
      mensaje: "Llegamos cerca de las 22 h. ¿Se puede hacer el ingreso tarde?", creada: creada(-1) }),
    r(d(10), d(14), { nombre: "Bruno Prueba", email: "bruno@example.com", huespedes: 3, estado: "confirmada",
      nota_interna: "Pidió cuna (dato de ejemplo)." }),
    // rechazada que choca con la confirmada de Bruno: al intentar confirmarla aparece el error 23P01
    r(d(11), d(13), { nombre: "Carla Simulada", email: "carla@example.com", estado: "rechazada" }),
    r(d(20), d(23), { nombre: "Diego Ficticio", email: "diego@example.com", telefono: "(2) 2345 6789", estado: "cancelada" }),
    // texto con marcas HTML a propósito: debe verse literal (el portal usa textContent)
    r(d(25), d(27), { nombre: "Eva <b>Etiqueta</b>", email: "eva@example.com", huespedes: 1,
      mensaje: "<img src=x onerror=alert(1)> Este mensaje debe verse como texto, sin ejecutar nada." }),
    r(d(-1), d(2), { nombre: "Franco En Curso", email: "franco@example.com", huespedes: 4, estado: "confirmada", creada: creada(-20) }),
    r(d(-12), d(-9), { nombre: "Gabriela Pasada", email: "gabriela@example.com", estado: "confirmada", creada: creada(-40) }),
    r(d(-30), d(-27), { nombre: "Hugo Antiguo", email: "hugo@example.com", estado: "rechazada", creada: creada(-50) }),
  ];
  const contenido = [
    { clave: "hero.bajada", grupo: "portada", orden: 10, tipo: "parrafo", etiqueta: "Bajada de la portada",
      valor: "Texto de ejemplo del modo simulado: departamento de dos dormitorios y dos baños para arriendo turístico." },
    ...ESPACIOS.flatMap((e, i) => [
      { clave: `espacio.${e.id}.titulo`, grupo: "espacios", orden: 20 + i * 2, tipo: "texto", etiqueta: `${e.nombre}: título`, valor: e.nombre },
      { clave: `espacio.${e.id}.texto`, grupo: "espacios", orden: 21 + i * 2, tipo: "parrafo", etiqueta: `${e.nombre}: texto`,
        valor: `Descripción de ejemplo de ${e.nombre.toLowerCase()} (modo simulado).` },
    ]),
    { clave: "tarifa.noche", grupo: "tarifas", orden: 40, tipo: "precio", etiqueta: "Tarifa por noche (ejemplo)", valor: "58000" },
    { clave: "tarifa.limpieza", grupo: "tarifas", orden: 41, tipo: "precio", etiqueta: "Limpieza (ejemplo)", valor: "15000" },
    { clave: "condiciones.llegada", grupo: "condiciones", orden: 50, tipo: "texto", etiqueta: "Llegada (ejemplo)", valor: "Desde las 15:00 (ejemplo)" },
    { clave: "condiciones.salida", grupo: "condiciones", orden: 51, tipo: "texto", etiqueta: "Salida (ejemplo)", valor: "Hasta las 11:00 (ejemplo)" },
  ].map((f) => ({ ...f, actualizado: `${d(-3)}T12:00:00.000Z` }));
  const fotos = [
    { espacio: "living", ruta: `living/${hoy.replace(/-/g, "")}-0a1b2c3d.webp`, alt: "Living de ejemplo con sofá y ventanal", orden: 0, visible: true, tono: "#8E6F55" },
    { espacio: "living", ruta: `living/${hoy.replace(/-/g, "")}-1a2b3c4d.webp`, alt: "Otro ángulo del living (ejemplo)", orden: 10, visible: true, tono: "#6F7F66" },
    { espacio: "cocina", ruta: `cocina/${hoy.replace(/-/g, "")}-2a3b4c5d.webp`, alt: "Cocina de ejemplo", orden: 0, visible: true, tono: "#A8481F" },
    { espacio: "balcon", ruta: `balcon/${hoy.replace(/-/g, "")}-3a4b5c6d.webp`, alt: "Balcón de ejemplo (oculta)", orden: 0, visible: false, tono: "#5E5850" },
  ].map(({ tono, ...f }) => ({ ...f, id: idFalso(), creada: creada(-2), _url: imagenEjemplo(f.espacio, tono) }));
  return { reservas, contenido, fotos };
}

export function crearApiSimulada({ almacen, retardo = 250, hoy = hoyIso(), ahora = () => Date.now() } = {}) {
  const db = datosEjemplo(hoy);
  const objetos = new Map();           // ruta -> { url, tipo, tamano }
  for (const f of db.fotos) objetos.set(f.ruta, { url: f._url, tipo: "image/webp", tamano: 100000 });
  let sesion = null;

  const esperar = () => (retardo > 0 ? new Promise((ok) => setTimeout(ok, retardo)) : Promise.resolve());
  const sinPrivados = (f) => { const { _url, ...resto } = f; return resto; };
  const exigirSesion = () => (sesion ? null : new ErrorApi({ codigo: "sesion_vencida", estado: 401 }));

  async function paso(fn) {
    await esperar();
    const e = exigirSesion();
    if (e) throw e;
    return fn();
  }

  function reserva(id) {
    const r = db.reservas.find((x) => x.id === id);
    if (!r) throw new ErrorApi({ codigo: "sin_filas" });
    return r;
  }

  return {
    modo: "simulado",
    async restaurarSesion() {
      const s = leerSesion(almacen);
      sesion = s && s.modo === "simulado" ? s : null;
      return sesion;
    },
    async iniciarSesion(email, contrasena) {
      await esperar();
      if (!String(email ?? "").trim() || !String(contrasena ?? "")) {
        throw new ErrorApi({ estado: 400, codigo: "validation_failed", origen: "auth" });
      }
      sesion = {
        modo: "simulado", access_token: "simulado", refresh_token: "simulado",
        expires_at: Math.floor(ahora() / 1000) + 3600, usuario: { id: "simulado", email: String(email).trim() },
      };
      guardarSesion(almacen, sesion);
      return sesion;
    },
    async cerrarSesion() {
      sesion = null;
      borrarSesion(almacen);
    },
    usuario: () => (sesion ? sesion.usuario : null),
    esPropietario: () => paso(() => true),

    reservas: {
      listar: () => paso(() => copia(db.reservas)),
      cambiarEstado: (id, estado) => paso(() => {
        const r = reserva(id);
        if (!ESTADOS.includes(estado)) throw new ErrorApi({ estado: 400, codigo: "23514", mensaje: "violates check constraint" });
        if (ACTIVOS.includes(estado) && db.reservas.some((o) => o.id !== id && ACTIVOS.includes(o.estado) &&
            solapa(r.entrada, r.salida, o.entrada, o.salida))) {
          throw new ErrorApi({ estado: 409, codigo: "23P01",
            mensaje: 'conflicting key value violates exclusion constraint "reservas_sin_solape"' });
        }
        r.estado = estado;
        r.actualizada = new Date(ahora()).toISOString();
        return copia(r);
      }),
      guardarNota: (id, nota) => paso(() => {
        const r = reserva(id);
        if (nota != null && largo(nota) > LIMITE_NOTA) throw new ErrorApi({ estado: 400, codigo: "23514" });
        r.nota_interna = nota ?? null;
        r.actualizada = new Date(ahora()).toISOString();
        return copia(r);
      }),
      eliminar: (id) => paso(() => {
        const r = reserva(id);
        db.reservas = db.reservas.filter((x) => x !== r);
        return { id };
      }),
    },

    contenido: {
      listar: () => paso(() => copia(db.contenido)),
      guardar: (k, valor) => paso(() => {
        const f = db.contenido.find((x) => x.clave === k);
        if (!f) throw new ErrorApi({ codigo: "sin_filas" });
        const v = validarValor(f.tipo, valor, f.clave);
        if (!v.ok || v.valor !== valor) throw new ErrorApi({ estado: 400, codigo: "23514", mensaje: "violates check constraint" });
        f.valor = valor;
        f.actualizado = new Date(ahora()).toISOString();
        return copia(f);
      }),
    },

    fotos: {
      listar: () => paso(() => db.fotos.map((f) => copia(sinPrivados(f)))),
      crear: ({ espacio, ruta, alt, orden, visible }) => paso(() => {
        if (!validarAlt(alt).ok || !ESPACIOS.some((e) => e.id === espacio)) throw new ErrorApi({ estado: 400, codigo: "23514" });
        if (db.fotos.some((f) => f.ruta === ruta)) throw new ErrorApi({ estado: 409, codigo: "23505" });
        const f = { id: idFalso(), espacio, ruta, alt, orden: Number(orden) || 0, visible: visible !== false,
          creada: new Date(ahora()).toISOString() };
        db.fotos.push(f);
        return copia(f);
      }),
      actualizar: (id, cambios) => paso(() => {
        const f = db.fotos.find((x) => x.id === id);
        if (!f) throw new ErrorApi({ codigo: "sin_filas" });
        if ("alt" in cambios && !validarAlt(cambios.alt).ok) throw new ErrorApi({ estado: 400, codigo: "23514" });
        for (const k of ["orden", "visible", "alt"]) if (k in cambios) f[k] = cambios[k];
        return copia(sinPrivados(f));
      }),
      eliminarFila: (id) => paso(() => {
        const f = db.fotos.find((x) => x.id === id);
        if (!f) throw new ErrorApi({ codigo: "sin_filas" });
        db.fotos = db.fotos.filter((x) => x !== f);
        return { id };
      }),
      subir: (ruta, blob) => paso(() => {
        if (objetos.has(ruta)) throw new ErrorApi({ estado: 409, codigo: "Duplicate", origen: "storage" });
        if (!TIPOS_ACEPTADOS.includes(blob.type)) throw new ErrorApi({ estado: 415, codigo: "invalid_mime_type", origen: "storage" });
        if (blob.size > MAX_SUBIDA) throw new ErrorApi({ estado: 413, codigo: "EntityTooLarge", origen: "storage" });
        const url = typeof URL.createObjectURL === "function" ? URL.createObjectURL(blob) : "";
        objetos.set(ruta, { url, tipo: blob.type, tamano: blob.size });
        return { Key: `fotos/${ruta}` };
      }),
      borrarObjeto: (ruta) => paso(() => {
        const o = objetos.get(ruta);
        if (!o) throw new ErrorApi({ codigo: "objeto_no_borrado", origen: "storage" });
        if (o.url.startsWith("blob:")) URL.revokeObjectURL(o.url);
        objetos.delete(ruta);
        return true;
      }),
      url: (ruta) => (objetos.get(ruta) || { url: "" }).url,
      /** Sólo para pruebas: ¿existe el objeto? */
      _existe: (ruta) => objetos.has(ruta),
    },
  };
}
