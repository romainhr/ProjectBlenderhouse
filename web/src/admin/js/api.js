// API del portal sobre el cliente de Supabase (modo real). La misma forma la implementa api-simulada.js.
// Tablas y columnas según el contrato de las migraciones 0003_gestion.sql y 0005_contenido_idiomas.sql:
//   reservas: + nota_interna, actualizada; el propietario puede select, delete y update SÓLO de (estado, nota_interna)
//   contenido(clave, valor, valor_en, valor_fr, tipo, etiqueta, grupo, orden, actualizado); valor_en y valor_fr los
//     agrega la 0005: mientras no esté aplicada, el portal lee y guarda sólo el español (contenido.listar -> idiomas)
//   fotos(id, espacio, ruta, alt, orden, visible, creada) y bucket público «fotos»
//   es_propietario() -> boolean
import { ErrorApi, esColumnaInexistente } from "./errores.js";
import { RE_CLAVE } from "./logica-contenido.js";
import { BUCKET } from "./logica-fotos.js";

export const COLUMNAS_RESERVA = "id,codigo,creada,entrada,salida,huespedes,nombre,email,telefono,mensaje,estado,nota_interna,actualizada";
export const COLUMNAS_CONTENIDO_BASE = "clave,valor,tipo,etiqueta,grupo,orden,actualizado";             // 0003
export const COLUMNAS_CONTENIDO = "clave,valor,valor_en,valor_fr,tipo,etiqueta,grupo,orden,actualizado"; // 0003 + 0005
const ORDEN_CONTENIDO = "order=grupo.asc,orden.asc,clave.asc";
// lo único que el portal cambia de un texto: sin la 0005, sólo el español
const CAMBIOS_CONTENIDO = Object.freeze(["valor", "valor_en", "valor_fr"]);
const CAMBIOS_CONTENIDO_BASE = Object.freeze(["valor"]);
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
      /**
       * -> { filas, idiomas }. Pide también valor_en y valor_fr; si PostgREST responde que no existen (0005 sin
       * aplicar), vuelve a pedir sin ellas e informa idiomas: false. Si esa segunda lectura también falla, el problema
       * es otro (p. ej. falta la 0003) y se propaga ese error.
       */
      listar: async () => {
        try {
          return { filas: await cliente.rest(`/contenido?select=${COLUMNAS_CONTENIDO}&${ORDEN_CONTENIDO}`), idiomas: true };
        } catch (e) {
          if (!esColumnaInexistente(e)) throw e;
          return { filas: await cliente.rest(`/contenido?select=${COLUMNAS_CONTENIDO_BASE}&${ORDEN_CONTENIDO}`), idiomas: false };
        }
      },
      /**
       * Guarda en un solo PATCH las columnas que trae `cambios`, cualquier subconjunto de { valor, valor_en, valor_fr }
       * (null = sin traducción propia), o sólo el texto en español. Las que no vienen no se tocan: la vista manda sólo
       * las que cambiaron, para no pisar lo guardado entretanto en otro lado. Con idiomas: false (base sin la 0005) se
       * manda sólo `valor`. Si la base rechaza las columnas de traducción, el error es «falta_idiomas» (y no se guarda
       * nada: el PATCH es una sola sentencia).
       */
      guardar: async (k, cambios, { idiomas = true } = {}) => {
        const ruta = `/contenido?clave=eq.${clave(k)}&select=${idiomas ? COLUMNAS_CONTENIDO : COLUMNAS_CONTENIDO_BASE}`;
        const datos = typeof cambios === "string" ? { valor: cambios } : cambios || {};
        const permitidos = idiomas ? CAMBIOS_CONTENIDO : CAMBIOS_CONTENIDO_BASE;
        const cuerpo = Object.fromEntries(Object.entries(datos).filter(([c]) => permitidos.includes(c)));
        if (!Object.keys(cuerpo).length) throw new ErrorApi({ codigo: "respuesta_invalida" });
        try {
          return unaFila(await cliente.rest(ruta, { metodo: "PATCH", cuerpo, prefer: REP }));
        } catch (e) {
          if (idiomas && esColumnaInexistente(e)) {
            throw new ErrorApi({ estado: e.estado, codigo: "falta_idiomas", mensaje: e.message, detalle: e.detalle, origen: e.origen });
          }
          throw e;
        }
      },
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
