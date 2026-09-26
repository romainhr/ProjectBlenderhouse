// Acceso a las reservas en Supabase por su API REST (PostgREST), sin librerías. Sólo llama a las dos funciones públicas
// de web/supabase/migrations/0001_reservas.sql; la tabla no es accesible con la clave pública (RLS sin políticas).
// config.js lo genera web/build.py desde variables de entorno; si faltan, en localhost se usa una simulación en memoria
// (para probar la interfaz) y en cualquier otro sitio las reservas quedan desactivadas con un aviso.
import { SUPABASE_URL, SUPABASE_CLAVE_PUBLICA } from "./config.js";

export const conectado = Boolean(SUPABASE_URL && SUPABASE_CLAVE_PUBLICA);
export const simulado = !conectado && ["localhost", "127.0.0.1"].includes(location.hostname);

async function rpc(funcion, cuerpo) {
  const cabeceras = { "Content-Type": "application/json", apikey: SUPABASE_CLAVE_PUBLICA };
  if (!SUPABASE_CLAVE_PUBLICA.startsWith("sb_publishable_")) {
    cabeceras.Authorization = `Bearer ${SUPABASE_CLAVE_PUBLICA}`;          // claves «anon» antiguas (JWT)
  }
  let r;
  try {
    r = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${funcion}`, { method: "POST", headers: cabeceras, body: JSON.stringify(cuerpo) });
  } catch {
    throw Object.assign(new Error("red"), { codigo: "red" });
  }
  const datos = await r.json().catch(() => null);
  if (!r.ok) throw Object.assign(new Error(datos?.message || `HTTP ${r.status}`), { codigo: datos?.message });
  return datos;
}

// ---------------------------------------------------------------- simulación local (sólo localhost sin Supabase)
const memoria = [];
function sumar(isoDia, n) {
  const d = new Date(isoDia + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
function simulacion() {
  if (!memoria.length) {
    const hoy = new Date().toISOString().slice(0, 10);
    memoria.push({ entrada: sumar(hoy, 6), salida: sumar(hoy, 9) }, { entrada: sumar(hoy, 17), salida: sumar(hoy, 21) });
  }
  return memoria;
}

export async function disponibilidad(desde, hasta) {
  if (simulado) return simulacion().filter((r) => r.entrada < hasta && desde < r.salida);
  if (!conectado) throw Object.assign(new Error("sin_configurar"), { codigo: "sin_configurar" });
  return rpc("disponibilidad", { desde, hasta });
}

export async function solicitar({ entrada, salida, huespedes, nombre, email, telefono, mensaje }) {
  if (simulado) {
    await new Promise((ok) => setTimeout(ok, 600));
    if (simulacion().some((r) => entrada < r.salida && r.entrada < salida)) {
      throw Object.assign(new Error("fechas_ocupadas"), { codigo: "fechas_ocupadas" });
    }
    memoria.push({ entrada, salida });
    const n = Math.round((new Date(salida) - new Date(entrada)) / 86400000);
    return [{ codigo: "SIM" + String(memoria.length).padStart(5, "0"), noches: n }];
  }
  if (!conectado) throw Object.assign(new Error("sin_configurar"), { codigo: "sin_configurar" });
  return rpc("solicitar_reserva", {
    p_entrada: entrada, p_salida: salida, p_huespedes: huespedes, p_nombre: nombre, p_email: email,
    p_telefono: telefono || null, p_mensaje: mensaje || null,
  });
}
