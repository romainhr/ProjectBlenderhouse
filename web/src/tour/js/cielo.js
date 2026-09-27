// Fondo y momento del día. El modelo trae `exterior.panoramas` (contrato 2.3, sección 4: un cielo de Poly Haven por
// momento, girado `rotacion_deg`); si faltan, un degradado de cielo generado en un canvas (2 px de ancho, un gradiente
// vertical basta como fondo difuso).
import { THREE } from "./three.js";
import { prepararPanorama, texturaHorizonte } from "./exterior.js";

// Escala de normalización de los entornos locales (entornos[].escala del modelo) con la que se midió `entornoLocal`.
// La fase 6 normaliza cada render del entorno (el percentil 97 a 0,9) y guarda la escala: el visor multiplica la
// intensidad por referencia / escala (actualizarEntornos en carga.js; contrato, sección 6), para que un render nuevo del
// entorno no mueva la calibración. Corrección 08, ronda 1: el bloque 08 le puso el exterior en las ventanas y la escala
// pasó de 7,80 a 8,75 con luces y de 19,62 a 30,76 de día. Se volvió a medir contra Blender desde las cámaras de la
// ronda 2 de la 07c, con el exterior (review/08_exterior/cocina, tools/medir_capturas.py): Blender no cambió
// (visera/azulejo 0,49; freezer/forro 0,99, antes 0,98), porque la escala sigue a lo más claro (el cielo de la
// ventana) y no al promedio que refleja el acero. La referencia es la de este render, con luces 0,67 (visera/azulejo
// 0,51) y de día 2,0 (freezer/forro 0,84); con 0,75 y la escala anterior, 0,55 y, con 1,28, 0,75.
export const ESCALA_ENTORNO_CALIBRADA = { luces: 8.7493, dia: 30.7553 };

export const MOMENTOS = {
  // entorno: intensidad del mapa de entorno (RoomEnvironment) en los materiales: sin él el PBR queda plano y
  // oscuro; con demasiado, lavado (0,42 en la tarde era demasiado). Ajustados a ojo contra review/depto_06_t2 (la v2
  // publicada), no medidos. entornoLocal (corrección 07c, ronda 2): intensidad del entorno local de la cocina
  // (contrato 2.2, sección 6) en su acero, por variante: `luces` (con la luz de la cocina encendida; no depende del
  // momento, las lámparas son las mismas) y `dia` (apagada; sigue a la luz del día de cada momento). Medido contra
  // Blender desde las mismas cámaras (docs/noche-2026-09-26.md, entradas de las 21:21 y de la corrección 08, ronda 1),
  // con la escala del entorno de ESCALA_ENTORNO_CALIBRADA: con luces 0,67 la razón visera/azulejo da 0,51 (Blender
  // 0,49); de día 2,0 da freezer/forro 0,84 (0,99).
  // sol.elevacion (corrección 08, ronda 1): la del sol (o la luna) medido en el panorama de cada momento (el píxel más
  // brillante del HDR, fase 08: 48,0°, 12,1° y 17,1°), con el azimut del sol de la escena, que el giro de los panoramas
  // ya alineó. Mueve el sol del depto y el sombreado del exterior; antes los tres momentos tenían los 35° de la fase 5.
  // exterior (bloque 08, exterior.js): tinte lineal del paisaje (`tinte`, y `lejos` para las siluetas), `cielo` y `sol`
  // (lo que pesan el cielo y el sol del momento en el sombreado por vértice), bruma de las siluetas hacia el horizonte
  // del panorama (`neblina`, 0-1; `horizonte` si el panorama no carga), `saturacion` (0-1), `exposicion` (EV) y
  // `curva` (el look de Filmic de los renders de Blender: sin look de día y de tarde, "contraste_medio" de noche),
  // `reflejo` del cielo en el vidrio, `brillo` de la emisión y `luzSuelo` de la mancha de luz de las luminarias, y
  // `emisivo` de respaldo si el modelo no trae exterior.emision. Calibrado con tools/medir_08.py contra los renders de
  // review/08_exterior desde las mismas cámaras (docs/noche-2026-09-26.md, corrección 08, ronda 1).
  dia: {
    etiqueta: "Día", cielo: { arriba: "#7fadd8", abajo: "#eaf3fa" },
    sol: { color: 0xfff7ec, intensidad: 3.4, elevacion: 48.0 }, ambiente: 0.45, entorno: 0.35, entornoLocal: { luces: 0.67, dia: 2.0 }, exposicion: 1.0, fondoIntensidad: 1.1,
    lucesEncendidas: false,
    exterior: { tinte: [1.0, 1.0, 1.0], lejos: [0.38, 0.40, 0.43], cielo: 1.0, sol: 1.0, neblina: 0.1, saturacion: 0.85, exposicion: 0.1, curva: "ninguno", reflejo: 1.8, horizonte: [0.32, 0.34, 0.41], brillo: 1, luzSuelo: 1, emisivo: 0 },
  },
  tarde: {
    etiqueta: "Tarde", cielo: { arriba: "#9aa9c9", abajo: "#f3cfa4" },
    sol: { color: 0xffc58f, intensidad: 1.8, elevacion: 12.1 }, ambiente: 0.32, entorno: 0.22, entornoLocal: { luces: 0.67, dia: 1.1 }, exposicion: 0.95, fondoIntensidad: 0.95,
    lucesEncendidas: true,
    exterior: { tinte: [1.0, 0.97, 0.95], lejos: [1.0, 0.9, 0.92], cielo: 0.5, sol: 0.53, neblina: 0.45, saturacion: 0.9, exposicion: 0, curva: "ninguno", reflejo: 1, horizonte: [0.26, 0.2, 0.25], brillo: 1, luzSuelo: 0.4, emisivo: 0.35 },
  },
  noche: {
    etiqueta: "Noche", cielo: { arriba: "#0d1524", abajo: "#232c3e" },
    // fondoIntensidad (corrección 08, ronda 1; 0,35 hasta el bloque 08 y 0,25 en él): medido contra el cielo de
    // balcon_noche, que queda bajo 0,3 de una ventana encendida
    sol: { color: 0x9db4d8, intensidad: 0.04, elevacion: 17.1 }, ambiente: 0.06, entorno: 0.07, entornoLocal: { luces: 0.67, dia: 0.06 }, exposicion: 0.95, fondoIntensidad: 0.1,
    lucesEncendidas: true,
    exterior: { tinte: [0.027, 0.029, 0.04], lejos: [0.027, 0.029, 0.04], cielo: 1.0, sol: 0.0, neblina: 0.2, saturacion: 1, exposicion: 0.4, curva: "contraste_medio", reflejo: 1, horizonte: [0.05, 0.06, 0.08], brillo: 1.35, luzSuelo: 1, emisivo: 1 },
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
// guarda en `userData.horizonte` el color lineal medio de su horizonte y en `userData.horizonteTex` sus 64 muestras
// por azimut (la bruma de las siluetas lejanas). Devuelve
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
        const { fuente, horizonte, muestras } = prepararPanorama(img, exterior.rotacion_deg || 0);
        const tex = fuente === img ? new THREE.Texture(img) : new THREE.CanvasTexture(fuente);
        tex.mapping = THREE.EquirectangularReflectionMapping;
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.needsUpdate = true;
        tex.userData.horizonte = horizonte;
        tex.userData.horizonteTex = texturaHorizonte(muestras);    // la bruma de las siluetas, por azimut
        return tex;
      }).catch((e) => { console.warn("[tour] panorama no disponible", archivo, e); return null; }));
    }
    const tex = await cache.get(archivo);
    if (tex) out[momento] = tex;
  }
  return out;
}
