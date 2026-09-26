// API del portal sobre el cliente de Supabase (modo real). La misma forma la implementa api-simulada.js.
// Tablas y columnas según el contrato de la migración 0003_gestion.sql (todavía no aplicada al escribir esto):
//   reservas: + nota_interna, actualizada; el propietario puede select, delete y update SÓLO de (estado, nota_interna)
//   contenido(clave, valor, tipo, etiqueta, grupo, orden, actualizado)
//   fotos(id, espacio, ruta, alt, orden, visible, creada) y bucket público «fotos»
//   es_propietario() -> boolean
import { ErrorApi } from "./errores.js";
import { RE_CLAVE } from "./logica-contenido.js";
import { BUCKET } from "./logica-fotos.js";

export const COLUMNAS_RESERVA = "id,codigo,creada,entrada,salida,huespedes,nombre,email,telefono,mensaje,estado,nota_interna,actualizada";
export const COLUMNAS_CONTENIDO = "clave,valor,tipo,etiqueta,grupo,orden,actualizado";
export const COLUMNAS_FOTO = "id,espacio,ruta,alt,orden,visible,creada";
const CAMBIOS_FOTO = Object.freeze(["orden", "visible", "alt"]);     // lo único que el portal cambia de una foto
const RE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const REP = "return=representation";

function uuid(v) {
  if (!RE_UUID.test(String(v))) throw new ErrorApi({ codigo: "id_invalido" });
  return String(v).toLowerCase();
}

function clave(v) {
  if (!RE_CLAVE.test(String(v))) throw new ErrorApi({ codigo: "id_invalido" });
  return encodeURIComponent(v);
}

/** PATCH y DELETE con RLS: si la política no deja ver la fila, PostgREST responde 200 con [] (no un error). */
function unaFila(filas) {
  if (!Array.isArray(filas) || filas.length !== 1) throw new ErrorApi({ codigo: "sin_filas" });
  return filas[0];
}

export function crearApi(cliente) {
  return {
    modo: "real",
    restaurarSesion: () => cliente.restaurar(),
    iniciarSesion: (email, contrasena) => cliente.iniciarSesion(email, contrasena),
    cerrarSesion: () => cliente.cerrarSesion(),
    usuario: () => (cliente.sesion() ? cliente.sesion().usuario : null),
    esPropietario: async () => (await cliente.rpc("es_propietario", {})) === true,

    reservas: {
      listar: () => cliente.rest(`/reservas?select=${COLUMNAS_RESERVA}&order=entrada.desc`),
      cambiarEstado: async (id, estado) => unaFila(await cliente.rest(
        `/reservas?id=eq.${uuid(id)}&select=${COLUMNAS_RESERVA}`, { metodo: "PATCH", cuerpo: { estado }, prefer: REP })),
      guardarNota: async (id, nota) => unaFila(await cliente.rest(
        `/reservas?id=eq.${uuid(id)}&select=${COLUMNAS_RESERVA}`,
        { metodo: "PATCH", cuerpo: { nota_interna: nota ?? null }, prefer: REP })),
      eliminar: async (id) => unaFila(await cliente.rest(
        `/reservas?id=eq.${uuid(id)}&select=id`, { metodo: "DELETE", prefer: REP })),
    },

    contenido: {
      listar: () => cliente.rest(`/contenido?select=${COLUMNAS_CONTENIDO}&order=grupo.asc,orden.asc,clave.asc`),
      guardar: async (k, valor) => unaFila(await cliente.rest(
        `/contenido?clave=eq.${clave(k)}&select=${COLUMNAS_CONTENIDO}`, { metodo: "PATCH", cuerpo: { valor }, prefer: REP })),
    },

    fotos: {
      listar: () => cliente.rest(`/fotos?select=${COLUMNAS_FOTO}&order=espacio.asc,orden.asc,creada.asc`),
      crear: async ({ espacio, ruta, alt, orden, visible }) => unaFila(await cliente.rest(
        `/fotos?select=${COLUMNAS_FOTO}`, { metodo: "POST", cuerpo: { espacio, ruta, alt, orden, visible }, prefer: REP })),
      actualizar: async (id, cambios) => {
        const cuerpo = Object.fromEntries(Object.entries(cambios || {}).filter(([k]) => CAMBIOS_FOTO.includes(k)));
        if (!Object.keys(cuerpo).length) throw new ErrorApi({ codigo: "respuesta_invalida" });
        return unaFila(await cliente.rest(`/fotos?id=eq.${uuid(id)}&select=${COLUMNAS_FOTO}`,
          { metodo: "PATCH", cuerpo, prefer: REP }));
      },
      eliminarFila: async (id) => unaFila(await cliente.rest(`/fotos?id=eq.${uuid(id)}&select=id`,
        { metodo: "DELETE", prefer: REP })),
      subir: (ruta, blob) => cliente.subirObjeto(BUCKET, ruta, blob, { sobrescribir: false }),
      borrarObjeto: async (ruta) => {
        const r = await cliente.borrarObjetos(BUCKET, [ruta]);
        if (!Array.isArray(r) || r.length === 0) throw new ErrorApi({ codigo: "objeto_no_borrado", origen: "storage" });
        return true;
      },
      url: (ruta) => cliente.urlPublica(BUCKET, ruta),
    },
  };
}
