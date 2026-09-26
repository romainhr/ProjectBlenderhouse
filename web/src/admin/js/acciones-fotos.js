// Pasos compuestos de fotos (objeto en Storage + fila en public.fotos), con el orden que deja todo consistente si
// algo falla a mitad de camino. Sin DOM: reciben la API (real o simulada).
import { hoyIso } from "../../js/reserva-logica.js";
import { ErrorApi, codigoConocido } from "./errores.js";
import { TIPOS_ACEPTADOS, esEspacio, moverFoto, rutaFoto, siguienteOrden, sufijoAleatorio, validarAlt } from "./logica-fotos.js";

const INTENTOS_RUTA = 3;       // si la ruta aleatoria ya existe (409), se prueba otra

function azarDelNavegador() {
  return globalThis.crypto.getRandomValues(new Uint8Array(4));
}

/**
 * Sube la imagen ya reducida y crea su fila. Orden: 1) objeto, 2) fila. Si la fila falla, se borra el objeto recién
 * subido para no dejar archivos huérfanos. -> la fila creada.
 */
export async function publicarFoto({ api, espacio, blob, alt, visible = true, fotosEspacio = [], hoy = hoyIso(), azar = azarDelNavegador }) {
  const a = validarAlt(alt);
  if (!a.ok) throw new ErrorApi({ codigo: a.error });
  if (!esEspacio(espacio)) throw new ErrorApi({ codigo: "id_invalido" });
  if (!blob || !TIPOS_ACEPTADOS.includes(blob.type)) throw new ErrorApi({ codigo: "archivo_tipo", origen: "storage" });
  let ruta = null;
  for (let intento = 1; ; intento++) {
    ruta = rutaFoto(espacio, hoy, sufijoAleatorio(azar()), blob.type);
    try {
      await api.fotos.subir(ruta, blob);
      break;
    } catch (e) {
      if (codigoConocido(e) === "archivo_duplicado" && intento < INTENTOS_RUTA) continue;
      throw e;
    }
  }
  try {
    return await api.fotos.crear({ espacio, ruta, alt: a.valor, visible: Boolean(visible), orden: siguienteOrden(fotosEspacio) });
  } catch (e) {
    await api.fotos.borrarObjeto(ruta).catch(() => {});
    throw e;
  }
}

/**
 * Borra una foto. Orden: 1) fila (el sitio deja de mostrarla aunque luego falle Storage), 2) objeto.
 * -> { objetoBorrado: boolean, error? } ; si la fila no se pudo borrar, lanza el error y no toca el objeto.
 */
export async function quitarFoto({ api, foto }) {
  await api.fotos.eliminarFila(foto.id);
  try {
    await api.fotos.borrarObjeto(foto.ruta);
    return { objetoBorrado: true };
  } catch (error) {
    return { objetoBorrado: false, error };
  }
}

/** Mueve una foto dentro de su espacio y guarda sólo los órdenes que cambian. -> la lista en el orden nuevo. */
export async function reordenarFoto({ api, fotosEspacio, id, delta }) {
  const { lista, cambios } = moverFoto(fotosEspacio, id, delta);
  for (const c of cambios) await api.fotos.actualizar(c.id, { orden: c.orden });
  return lista;
}
