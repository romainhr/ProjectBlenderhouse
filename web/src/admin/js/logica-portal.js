// Decisiones del arranque y la navegación del portal (app.js), sin DOM, para probarlas con `cd web && npm test`.

export const VISTAS = Object.freeze(["reservas", "textos", "fotos"]);
export const VISTA_INICIAL = "reservas";

/**
 * Vista que corresponde al hash de la URL, o null si el hash no es de navegación.
 *   "#textos" -> "textos"; "" o "#" -> "reservas" (sin hash se ve la vista inicial, también al volver atrás);
 *   "#principal" (el enlace «Saltar al contenido») u otro ancla -> null: no se cambia de vista.
 */
export function vistaDeHash(hash) {
  const nombre = String(hash ?? "").replace(/^#/, "");
  if (nombre === "") return VISTA_INICIAL;
  return VISTAS.includes(nombre) ? nombre : null;
}

/**
 * Cierre de sesión que no deja datos a la vista mientras Auth responde.
 * cerrar(limpiar): llama a api.cerrarSesion(), cuya parte síncrona ya borra la sesión local, y enseguida a limpiar()
 * (quitar de la página los datos de huéspedes). La revocación en /auth/v1/logout sigue en segundo plano y la promesa
 * devuelta nunca falla. esperar(): la revocación pendiente; un ingreso nuevo la espera antes de pedir tokens, porque
 * (supuesto, no verificado contra el proyecto) /auth/v1/logout sin «scope» revoca todas las sesiones de la cuenta y
 * podría alcanzar a la sesión nueva.
 */
export function crearCierre(api) {
  let revocacion = Promise.resolve();
  return {
    cerrar(limpiar) {
      let p;
      try {
        p = Promise.resolve(api.cerrarSesion());
      } catch (e) {
        p = Promise.reject(e);
      }
      const esta = p.then(() => {}, () => {});
      revocacion = esta;
      limpiar();
      return esta;
    },
    esperar: () => revocacion,
  };
}
