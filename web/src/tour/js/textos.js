// Textos del visor que salen de los datos del modelo (depto_colisiones.json): nombres de recinto, grupos de luz y
// piezas móviles, en el idioma de la página. Los diccionarios son los del sitio (web/src/i18n/*.json, claves
// js.tour.*) y se leen con t() de ../../js/i18n.js: el tour en /en/tour/ y /fr/tour/ usa este mismo JS de /tour/js/.
//
// Los datos del modelo vienen en español (los escribe build/depto_04_mobiliario.py). Cada texto se busca por una
// clave estable y, si el diccionario no la tiene (un recinto, grupo o pieza nuevos), queda el texto del modelo:
//   - recinto: js.tour.recinto.<id del recinto> (Hall, Dorm1…);
//   - grupo de luz: js.tour.luz.<id del grupo> (living_techo…);
//   - pieza móvil: js.tour.pieza.<su etiqueta en español, sin tildes y con «_»> ("Puerta del clóset" ->
//     js.tour.pieza.puerta_del_closet). En inglés y francés, una pieza sin clave usa el nombre de su clase
//     (js.tour.clase.<clase>): mejor «Open the door» que media frase en español.
// web/tests/tour-textos.test.mjs revisa que todo lo del modelo exportado tenga su clave en los tres idiomas y que el
// español del diccionario diga lo mismo que el modelo.
// Nada de esto se inserta como HTML: quien lo muestra usa textContent, aria-label o fillText.
import { IDIOMA, IDIOMA_BASE, t } from "../../js/i18n.js";
import { NOMBRES_RECINTO } from "./luces.js";

/** t(clave, variables) o null si ningún diccionario la tiene (t() devuelve entonces la clave tal cual). */
export function traduccion(clave, variables) {
  const texto = t(clave, variables);
  return texto === clave ? null : texto;
}

/** Texto -> sufijo de clave: minúsculas, sin tildes y con «_» entre palabras ("Cajón 1 profundo" -> cajon_1_profundo).
 *  NFD separa cada letra de sus marcas (tilde, diéresis, cedilla) y \p{M} las quita todas, sin escribir en la regex
 *  caracteres combinantes, que no se ven. */
export function claveDeTexto(texto) {
  return String(texto ?? "").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

/** Nombre del recinto `id` en el idioma de la página. `etiquetas`: recintos_etiquetas del JSON (opcional). */
export function nombreRecinto(id, etiquetas) {
  return traduccion(`js.tour.recinto.${id}`) ?? (etiquetas && etiquetas[id]) ?? NOMBRES_RECINTO[id] ?? String(id);
}

/** Etiqueta de un grupo de luz ({ id, etiqueta, recinto }) en el idioma de la página. Un grupo deducido por recinto
 *  (sin grupos_luz en el JSON, ver deducirGrupos) se llama como su recinto. */
export function etiquetaGrupo(grupo, etiquetas) {
  const propia = traduccion(`js.tour.luz.${grupo.id}`);
  if (propia) return propia;
  if (grupo.recinto === grupo.id && traduccion(`js.tour.recinto.${grupo.id}`)) return nombreRecinto(grupo.id, etiquetas);
  return grupo.etiqueta || String(grupo.id);
}

/** Qué se abre o se cierra, para «Abrir {cosa}»: la pieza móvil `m` (moviles[] del JSON) en el idioma de la página.
 *  Sin clave propia: en español, su etiqueta en minúsculas (como antes); en otro idioma, el nombre de su clase. */
export function nombrePieza(m) {
  const etiqueta = typeof m.etiqueta === "string" ? m.etiqueta.replace(/^(Abrir|Cerrar)\s+/i, "").trim() : "";
  if (etiqueta) {
    const propia = traduccion(`js.tour.pieza.${claveDeTexto(etiqueta)}`);
    if (propia) return propia;
    if (IDIOMA === IDIOMA_BASE) return etiqueta.toLowerCase();
  }
  return traduccion(`js.tour.clase.${m.clase}`) ?? t("js.tour.clase.pieza");
}
