// Lógica de la vista de textos (public.contenido, migración 0003). Sin DOM.
import { clp } from "../../js/reserva-logica.js";
import { largo } from "./util.js";

// 0003_gestion.sql (contrato del backend): tipo in ('texto', 'parrafo', 'precio'); valor text not null (<= 4000);
// un 'precio' es un entero entre 0 y 10 000 000 escrito como texto de dígitos; clave '^[a-z0-9][a-z0-9_.-]{1,59}$'.
export const TIPOS = Object.freeze(["texto", "parrafo", "precio"]);
export const LIMITE_VALOR = 4000;
export const PRECIO_MAX = 10000000;
export const RE_CLAVE = /^[a-z0-9][a-z0-9_.-]{1,59}$/;

// Se aceptan dígitos sueltos o con separador de miles de es-CL («58.000» o «58 000»); se guarda sólo con dígitos.
const RE_PRECIO = /^(\d+|\d{1,3}([. ]\d{3})+)$/;

/**
 * Valida y normaliza el valor según el tipo -> { ok: true, valor } o { ok: false, error }.
 * Regla propia del portal (más estricta que la base): los textos no pueden quedar vacíos, para no dejar huecos en el sitio.
 */
export function validarValor(tipo, bruto, clave = "") {
  const s = String(bruto ?? "").replace(/\r\n?/g, "\n");
  if (tipo === "precio") {
    const t = s.replace(/[  ]/g, " ").trim().replace(/^CLP\s*/i, "").replace(/^\$\s*/, "");
    if (!t) return { ok: false, error: "vacio" };
    if (!RE_PRECIO.test(t)) return { ok: false, error: "precio_formato" };
    const digitos = t.replace(/[. ]/g, "");
    const n = Number(digitos);
    if (!Number.isSafeInteger(n) || n < 0 || n > PRECIO_MAX) return { ok: false, error: "precio_rango" };
    // el sitio trata una noche en 0 como «sin editar» (contenido-publico.js, tarifasEditadas): no se acepta
    if (clave === "tarifa.noche" && n === 0) return { ok: false, error: "precio_noche_cero" };
    return { ok: true, valor: String(n) };                     // sin ceros a la izquierda
  }
  if (!TIPOS.includes(tipo)) return { ok: false, error: "tipo" };
  const v = tipo === "texto" ? s.replace(/\s+/g, " ").trim() : s.trim();
  if (!v) return { ok: false, error: "vacio" };
  if (largo(v) > LIMITE_VALOR) return { ok: false, error: "largo" };
  return { ok: true, valor: v };
}

export const MENSAJES_VALOR = Object.freeze({
  vacio: "Este texto no puede quedar vacío.",
  largo: `Admite hasta ${LIMITE_VALOR.toLocaleString("es-CL")} caracteres.`,
  precio_formato: "Escribe sólo el monto en pesos, con dígitos (p. ej. 58000 o 58.000), sin decimales.",
  precio_rango: `El monto debe estar entre 0 y ${PRECIO_MAX.toLocaleString("es-CL")}.`,
  precio_noche_cero: "La tarifa por noche debe ser mayor que 0 (la limpieza sí puede ser 0).",
  tipo: "Tipo de contenido desconocido.",
});

/** Vista previa del precio como lo muestra el sitio («CLP 58.000»), o "" si no es válido. */
export function previaPrecio(bruto) {
  const v = validarValor("precio", bruto);
  return v.ok ? clp(Number(v.valor)) : "";
}

function comparar(a, b) {
  const oa = Number(a.orden) || 0, ob = Number(b.orden) || 0;
  if (oa !== ob) return oa - ob;
  return String(a.clave).localeCompare(String(b.clave));
}

/**
 * Agrupa las filas por `grupo`, con las filas por `orden` (y clave). Los grupos siguen el menor `orden` de sus filas
 * (así el orden de la semilla decide también el de las secciones) y, a igualdad, el nombre.
 * -> [{ grupo, titulo, filas: [...] }]
 */
export function agruparContenido(filas) {
  const mapa = new Map();
  for (const f of filas || []) {
    const g = String(f.grupo || "otros");
    if (!mapa.has(g)) mapa.set(g, []);
    mapa.get(g).push(f);
  }
  const grupos = [...mapa.entries()].map(([grupo, fs]) => {
    fs.sort(comparar);
    return { grupo, titulo: tituloGrupo(grupo), filas: fs, min: Math.min(...fs.map((f) => Number(f.orden) || 0)) };
  });
  grupos.sort((a, b) => a.min - b.min || a.grupo.localeCompare(b.grupo));
  return grupos.map(({ grupo, titulo, filas: fs }) => ({ grupo, titulo, filas: fs }));
}

export function tituloGrupo(grupo) {
  const s = String(grupo || "").replace(/[_.-]+/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "Otros";
}
