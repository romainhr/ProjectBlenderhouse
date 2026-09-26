// Fondo y momento del día. Si el modelo trae `exterior.panorama` (todavía no: lo agrega otro agente más
// tarde) se usa como panorama equirectangular; si no, un degradado de cielo generado en un canvas (2 px de
// ancho, un gradiente vertical basta como fondo difuso).
import { THREE } from "./three.js";

export const MOMENTOS = {
  // entorno: intensidad del mapa de entorno (RoomEnvironment) en los materiales; sin él el PBR queda plano y
  // oscuro. Valores ajustados a ojo sobre el render de Blender (review/depto_06_v3ind), no medidos.
  dia: {
    etiqueta: "Día", cielo: { arriba: "#7fadd8", abajo: "#eaf3fa" },
    sol: { color: 0xfff7ec, intensidad: 3.4 }, ambiente: 0.45, entorno: 0.7, exposicion: 1.0, fondoIntensidad: 1,
    lucesEncendidas: false,
  },
  tarde: {
    etiqueta: "Tarde", cielo: { arriba: "#9aa9c9", abajo: "#f3cfa4" },
    sol: { color: 0xffc58f, intensidad: 1.8 }, ambiente: 0.32, entorno: 0.42, exposicion: 1.0, fondoIntensidad: 0.95,
    lucesEncendidas: true,
  },
  noche: {
    etiqueta: "Noche", cielo: { arriba: "#0d1524", abajo: "#232c3e" },
    sol: { color: 0x9db4d8, intensidad: 0.04 }, ambiente: 0.06, entorno: 0.07, exposicion: 0.95, fondoIntensidad: 0.35,
    lucesEncendidas: true,
  },
};
export const MOMENTO_POR_DEFECTO = "tarde";

export function generarCieloCanvas(colores) {
  const cv = document.createElement("canvas");
  cv.width = 2; cv.height = 256;
  const ctx = cv.getContext("2d");
  const g = ctx.createLinearGradient(0, 0, 0, 256);
  g.addColorStop(0, colores.arriba);
  g.addColorStop(0.55, colores.abajo);
  g.addColorStop(1, colores.abajo);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 2, 256);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.needsUpdate = true;
  return tex;
}

// Panoramas reales cuando el JSON los trae (contrato de interacción, sección 4): `exterior.panoramas` con un
// archivo por momento ({dia, tarde, noche}) o, en la versión anterior del contrato, un único `exterior.panorama`.
// `rutaBase` es la carpeta modelo/. Devuelve {dia: textura, ...}; los que fallen quedan fuera (se usa el degradado).
export async function cargarPanoramas(rutaBase, exterior) {
  const archivos = exterior.panoramas || { dia: exterior.panorama, tarde: exterior.panorama, noche: exterior.panorama };
  const cache = new Map();
  const out = {};
  const cargador = new THREE.TextureLoader();
  for (const [momento, archivo] of Object.entries(archivos)) {
    if (!archivo) continue;
    if (!cache.has(archivo)) {
      cache.set(archivo, cargador.loadAsync(rutaBase + archivo).then((tex) => {
        tex.mapping = THREE.EquirectangularReflectionMapping;
        tex.colorSpace = THREE.SRGBColorSpace;
        return tex;
      }).catch((e) => { console.warn("[tour] panorama no disponible", archivo, e); return null; }));
    }
    const tex = await cache.get(archivo);
    if (tex) out[momento] = tex;
  }
  return out;
}
