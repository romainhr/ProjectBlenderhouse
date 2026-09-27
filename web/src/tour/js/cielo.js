// Fondo y momento del día. El modelo trae `exterior.panoramas` (contrato 2.3, sección 4: un cielo de Poly Haven por
// momento, girado `rotacion_deg`); si faltan, un degradado de cielo generado en un canvas (2 px de ancho, un gradiente
// vertical basta como fondo difuso).
import { THREE } from "./three.js";
import { prepararPanorama } from "./exterior.js";

export const MOMENTOS = {
  // entorno: intensidad del mapa de entorno (RoomEnvironment) en los materiales: sin él el PBR queda plano y
  // oscuro; con demasiado, lavado (0,42 en la tarde era demasiado). Ajustados a ojo contra review/depto_06_t2 (la v2
  // publicada), no medidos. entornoLocal (corrección 07c, ronda 2): intensidad del entorno local de la cocina
  // (contrato 2.2, sección 6) en su acero, por variante: `luces` (con la luz de la cocina encendida; no depende del
  // momento, las lámparas son las mismas) y `dia` (apagada; sigue a la luz del día de cada momento). Medido contra
  // Blender desde las mismas cámaras (docs/noche-2026-09-26.md, entrada de las 21:21): con luces 0,75 la razón visera/azulejo da 0,53
  // (Blender 0,49) y nevera/azulejo 0,69 (0,87); de día 2,0 da freezer/forro 0,82 (0,98).
  // exterior (bloque 08, exterior.js): tinte lineal del paisaje (`tinte`, y `lejos` para las siluetas), bruma de las
  // siluetas hacia el color del horizonte del panorama (`neblina`, 0-1; `horizonte` si el panorama no carga),
  // `saturacion` (0-1: Blender, con Filmic y la luz del cielo, da colores menos saturados que el ACES del visor), `brillo`
  // de la emisión y `emisivo` de respaldo si el modelo no trae exterior.emision. Calibrado contra los renders de
  // review/08_exterior desde las mismas cámaras (docs/noche-2026-09-26.md, entrada del bloque 08).
  dia: {
    etiqueta: "Día", cielo: { arriba: "#7fadd8", abajo: "#eaf3fa" },
    sol: { color: 0xfff7ec, intensidad: 3.4 }, ambiente: 0.45, entorno: 0.35, entornoLocal: { luces: 0.75, dia: 2.0 }, exposicion: 1.0, fondoIntensidad: 1,
    lucesEncendidas: false,
    exterior: { tinte: [1.0, 1.0, 1.0], lejos: [1.0, 1.0, 1.0], neblina: 0.25, saturacion: 0.72, horizonte: [0.32, 0.34, 0.41], brillo: 1, emisivo: 0 },
  },
  tarde: {
    etiqueta: "Tarde", cielo: { arriba: "#9aa9c9", abajo: "#f3cfa4" },
    sol: { color: 0xffc58f, intensidad: 1.8 }, ambiente: 0.32, entorno: 0.22, entornoLocal: { luces: 0.75, dia: 1.1 }, exposicion: 0.95, fondoIntensidad: 0.95,
    lucesEncendidas: true,
    exterior: { tinte: [1.05, 0.94, 0.93], lejos: [1.0, 0.9, 0.92], neblina: 0.45, saturacion: 0.85, horizonte: [0.26, 0.2, 0.25], brillo: 1, emisivo: 0.35 },
  },
  noche: {
    etiqueta: "Noche", cielo: { arriba: "#0d1524", abajo: "#232c3e" },
    // fondoIntensidad 0,25 (bloque 08; antes 0,35): con el exterior, el cielo de luna de kloppenheim_02 a 0,35 se leía
    // como fin de tarde y apagaba las ventanas vecinas encendidas
    sol: { color: 0x9db4d8, intensidad: 0.04 }, ambiente: 0.06, entorno: 0.07, entornoLocal: { luces: 0.75, dia: 0.06 }, exposicion: 0.95, fondoIntensidad: 0.25,
    lucesEncendidas: true,
    exterior: { tinte: [0.06, 0.065, 0.09], lejos: [0.06, 0.065, 0.09], neblina: 0.2, saturacion: 1, horizonte: [0.05, 0.06, 0.08], brillo: 1, emisivo: 1 },
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
// `rutaBase` es la carpeta modelo/. Cada imagen se gira `exterior.rotacion_deg` (exterior.js, prepararPanorama) y
// guarda en `userData.horizonte` el color lineal de su horizonte (la bruma de las siluetas lejanas). Devuelve
// {dia: textura, ...}; los que fallen quedan fuera (se usa el degradado).
export async function cargarPanoramas(rutaBase, exterior) {
  const archivos = exterior.panoramas || { dia: exterior.panorama, tarde: exterior.panorama, noche: exterior.panorama };
  const cache = new Map();
  const out = {};
  const cargador = new THREE.ImageLoader();
  for (const [momento, archivo] of Object.entries(archivos)) {
    if (!archivo) continue;
    if (!cache.has(archivo)) {
      cache.set(archivo, cargador.loadAsync(rutaBase + archivo).then((img) => {
        const { fuente, horizonte } = prepararPanorama(img, exterior.rotacion_deg || 0);
        const tex = fuente === img ? new THREE.Texture(img) : new THREE.CanvasTexture(fuente);
        tex.mapping = THREE.EquirectangularReflectionMapping;
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.needsUpdate = true;
        tex.userData.horizonte = horizonte;
        return tex;
      }).catch((e) => { console.warn("[tour] panorama no disponible", archivo, e); return null; }));
    }
    const tex = await cache.get(archivo);
    if (tex) out[momento] = tex;
  }
  return out;
}
