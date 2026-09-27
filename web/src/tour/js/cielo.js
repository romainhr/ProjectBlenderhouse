// Fondo y momento del día. El modelo trae `exterior.panoramas` (contrato 2.5, sección 4: un cielo por momento, girado
// `rotacion_deg`; los de `exterior.panoramas_intensidad`, ya en pantalla con la curva Filmic de los renders de revisión,
// se dibujan con esa intensidad en vez de fondoIntensidad) y `exterior.sol` (el sol de cada panorama); si faltan, un
// degradado de cielo generado en un canvas (2 px de ancho, un gradiente vertical basta como fondo difuso).
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
// 0,51) y de día 2,0 (freezer/forro 0,84); con 0,75 y la escala anterior, 0,55 y, con 1,28, 0,75. Corrección 08, ronda
// 2: el entorno se renderiza ahora con el mundo de los renders de revisión (el HDR de día desaturado, no el Nishita del
// maestro) y se volvió a medir con este render (luces 8,36, día 35,37): con luces 0,67, visera/azulejo 0,49 (Blender
// 0,49); de día 2,4, freezer/forro 0,83 (0,99) y el frente del freezer neutro, B − R = +7 en sRGB (antes +22).
export const ESCALA_ENTORNO_CALIBRADA = { luces: 8.3566, dia: 35.3659 };

export const MOMENTOS = {
  // entorno: intensidad del mapa de entorno (RoomEnvironment) en los materiales: sin él el PBR queda plano y
  // oscuro; con demasiado, lavado (0,42 en la tarde era demasiado). Ajustados a ojo contra review/depto_06_t2 (la v2
  // publicada), no medidos, salvo la tarde (corrección 08, ronda 2): ambiente, entorno y exposición medidos contra
  // review/08_exterior (tools/medir_08.py) con tres criterios: pared del dormitorio / cielo por su ventana 0,35-0,55
  // (Blender 0,45; antes 0,90), piso del living a ±25 % de Blender (antes 2,4 veces) y el tono de la pared blanca bajo la
  // luz de techo, R/B lineal ≤ 2,5 (el objetivo de tono único; Blender lo alcanza con la adaptación de cámara de
  // dormitorio_ventana_adaptada). Con menos relleno neutro el interior queda más cálido: la exposición baja más que el
  // relleno. entornoLocal (corrección 07c, ronda 2): intensidad del entorno local de la cocina
  // (contrato 2.2, sección 6) en su acero, por variante: `luces` (con la luz de la cocina encendida; no depende del
  // momento, las lámparas son las mismas) y `dia` (apagada; sigue a la luz del día de cada momento). Medido contra
  // Blender desde las mismas cámaras (docs/noche-2026-09-26.md, entradas de las 21:21 y de la corrección 08, ronda 1),
  // con la escala del entorno de ESCALA_ENTORNO_CALIBRADA: con luces 0,67 la razón visera/azulejo da 0,51 (Blender
  // 0,49); de día 2,0 da freezer/forro 0,84 (0,99).
  // sol.elevacion (corrección 08, ronda 1): la del sol (o la luna) medido en el panorama de cada momento (el píxel más
  // brillante del HDR, fase 08: 48,0°, 12,1° y 17,1°). Corrección 08, ronda 2: es sólo el respaldo de un modelo sin
  // exterior.sol (contrato 2.5), que trae azimut y elevación de cada panorama; tour-exterior.test.mjs exige que
  // coincida con el JSON exportado. Mueve el sol del depto y el sombreado del exterior.
  // exterior (bloque 08, exterior.js): tinte lineal del paisaje (`tinte`, y `lejos` para las siluetas), `cielo` y `sol`
  // (lo que pesan el cielo y el sol del momento en el sombreado por vértice), bruma de las siluetas hacia el horizonte
  // del panorama (`neblina`, 0-1; `horizonte` si el panorama no carga), `saturacion` (0-1), `exposicion` (EV) y
  // `curva` (el look de Filmic de los renders de Blender: sin look de día y de tarde, "contraste_medio" de noche),
  // `reflejo` del cielo en el vidrio, `brillo` de la emisión y `luzSuelo` de la mancha de luz de las luminarias, y
  // `emisivo` de respaldo si el modelo no trae exterior.emision, y `arriba` (corrección 08, ronda 2), el factor del
  // término hacia arriba del sombreado (exterior.js, factorSombreado). Calibrado con tools/medir_08.py contra los renders
  // de review/08_exterior desde las mismas cámaras (docs/noche-2026-09-26.md, corrección 08, rondas 1 y 2). Ronda 2:
  // de día el reflejo del vidrio baja de 1,8 a 1,0 (con 1,8 los paños del E4 quedaban 1,8 veces más claros que en
  // Blender y el promedio lo compensaba la enjuta negra); de tarde las siluetas llevan un tinte del orden del de día
  // (antes [1,0; 0,9; 0,92] con bruma 0,45: a contraluz salían 1,6-2,7 veces más claras que en Blender, casi del color
  // del horizonte), el tinte de las caras en sombra es el del cielo del atardecer, más frío ([1,0; 0,98; 1,18] con
  // saturación 0,75: el ladrillo del E2 pasa de R/B 4,4 a ≈ 3, como Blender) y lo que mira hacia arriba baja (0,65:
  // la calzada estaba a 1,38 de Blender); de noche el suelo entre luminarias baja con arriba = 0,3 y la mancha de luz
  // sube a 1,4 (su textura guarda el incremento medido sobre el promedio de la región, no el del pie del poste).
  dia: {
    etiqueta: "Día", cielo: { arriba: "#7fadd8", abajo: "#eaf3fa" },
    sol: { color: 0xfff7ec, intensidad: 3.4, elevacion: 48.0 }, ambiente: 0.45, entorno: 0.35, entornoLocal: { luces: 0.67, dia: 2.4 }, exposicion: 1.0, fondoIntensidad: 1.1,
    lucesEncendidas: false,
    exterior: { tinte: [1.0, 1.0, 1.0], lejos: [0.38, 0.40, 0.43], cielo: 1.0, sol: 1.0, neblina: 0.1, saturacion: 0.85, exposicion: 0.1, curva: "ninguno", reflejo: 1.0, horizonte: [0.32, 0.34, 0.41], brillo: 1, luzSuelo: 1, emisivo: 0 },
  },
  tarde: {
    etiqueta: "Tarde", cielo: { arriba: "#9aa9c9", abajo: "#f3cfa4" },
    sol: { color: 0xffc58f, intensidad: 1.8, elevacion: 12.1 }, ambiente: 0.28, entorno: 0.19, entornoLocal: { luces: 0.67, dia: 1.1 }, exposicion: 0.47, fondoIntensidad: 0.95,
    lucesEncendidas: true,
    exterior: { tinte: [1.0, 0.98, 1.18], lejos: [0.272, 0.234, 0.277], cielo: 0.5, sol: 0.53, arriba: 0.65, neblina: 0.12, saturacion: 0.75, exposicion: 0, curva: "ninguno", reflejo: 1, horizonte: [0.26, 0.2, 0.25], brillo: 1, luzSuelo: 0.4, emisivo: 0.35 },
  },
  noche: {
    etiqueta: "Noche", cielo: { arriba: "#0d1524", abajo: "#232c3e" },
    // fondoIntensidad (corrección 08, ronda 1; 0,35 hasta el bloque 08 y 0,25 en él): medido contra el cielo de
    // balcon_noche, que queda bajo 0,3 de una ventana encendida
    sol: { color: 0x9db4d8, intensidad: 0.04, elevacion: 17.1 }, ambiente: 0.06, entorno: 0.07, entornoLocal: { luces: 0.67, dia: 0.06 }, exposicion: 0.95, fondoIntensidad: 0.1,
    lucesEncendidas: true,
    exterior: { tinte: [0.027, 0.029, 0.04], lejos: [0.027, 0.029, 0.04], cielo: 1.0, sol: 0.0, arriba: 0.3, neblina: 0.2, saturacion: 1, exposicion: 0.4, curva: "contraste_medio", reflejo: 1, horizonte: [0.05, 0.06, 0.08], brillo: 1.35, luzSuelo: 1.4, emisivo: 1 },
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
