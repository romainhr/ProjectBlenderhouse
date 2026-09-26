// Luces y grupos de luz. Las funciones puras (sin `import`, para que web/tests/*.test.mjs las use directo)
// deducen los grupos cuando el modelo todavía no trae `grupos_luz` (contrato de interacción v2, sección 2):
// "un grupo por recinto según el punto de recintos más cercano en XZ, con la ampolleta como nodo de nombre
// luces[i].nombre sin el prefijo Depto_Luz_". Las funciones que construyen objetos de three.js reciben el
// espacio de nombres THREE como parámetro (inyección) en vez de importarlo, por la misma razón.

// Respaldo de los nombres de recinto para cuando el JSON no trae `recintos_etiquetas` (la fuente es
// RECINTOS_ETIQUETAS de build/depto_04_mobiliario.py; web/tests/test_contrato_luces.py exige que coincidan).
export const NOMBRES_RECINTO = {
  Hall: "Hall", Living: "Living", Cocina: "Cocina", Dorm1: "Dormitorio principal",
  Dorm2: "Segundo dormitorio", Paso_D1: "Clósets del principal", Paso_D2: "Clósets del segundo",
  Bano1: "Baño principal", Bano2: "Segundo baño", Balcon: "Balcón", Palier: "Palier",
  Nicho_LV: "Lavadora",
};

// 2700 K en sRGB LINEAL (contrato de interacción, sección 2; build/depto_color.py: Planck + CIE 1931, calculado).
// Sólo es el respaldo si una luz no trae `color`. Antes valía [1, 0.72, 0.42], que es ~3000 K en sRGB codificado:
// usado como lineal daba una luz de ~4200 K.
export const KELVIN_2700 = [1.0, 0.423, 0.0996];
export const INTENSIDAD_POR_WATT = 0.35; // escala no física, igual a la del visor anterior (se ve bien, no se midió)
export const DISTANCIA_LUZ = 7; // m, del encargo ("distance ≈ 7 m")
export const FUNDIDO_MS = 150;

export function nombreAmpolleta(nombreLuz) {
  return nombreLuz.replace(/^Depto_Luz_/, "");
}

// Codifica un color lineal (0..1 por canal) a "#rrggbb" sRGB, para pasarlo a THREE.Color / CSS.
export function colorLinealAHex(rgb) {
  const canal = (v) => {
    const x = Math.max(0, Math.min(1, v));
    const s = x <= 0.0031308 ? x * 12.92 : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
    return Math.round(s * 255).toString(16).padStart(2, "0");
  };
  return "#" + rgb.map(canal).join("");
}

function recintoMasCercanoXZ(posicionXYZ, recintos) {
  let mejor = null, mejorD = Infinity;
  for (const [nombre, p] of Object.entries(recintos)) {
    const d = (posicionXYZ[0] - p[0]) ** 2 + (posicionXYZ[2] - p[1]) ** 2;
    if (d < mejorD) { mejorD = d; mejor = nombre; }
  }
  return mejor;
}

// Recibe los datos crudos de depto_colisiones.json (luces, recintos, recintos_etiquetas y, si ya existe,
// grupos_luz) y devuelve { luces, grupos } con todo completo: cada luz puntual con `.grupo`, `.ampolleta` y
// `.color`, y la lista de grupos con `.id`, `.etiqueta`, `.recinto`, `.encendido`. Si el JSON ya trae
// `grupos_luz` con todas las luces asignadas, se respeta tal cual (no se reemplaza autoría por deducción).
export function deducirGrupos({ luces, recintos, recintos_etiquetas: etiquetas = {}, grupos_luz: gruposDeAutor }) {
  const puntuales = luces.filter((l) => l.tipo === "puntual");
  const yaCompleto = Array.isArray(gruposDeAutor) && gruposDeAutor.length > 0 && puntuales.every((l) => l.grupo);
  if (yaCompleto) {
    return {
      luces: luces.map((l) => (l.tipo === "puntual"
        ? { ...l, ampolleta: l.ampolleta || nombreAmpolleta(l.nombre), color: l.color || KELVIN_2700 }
        : l)),
      grupos: gruposDeAutor,
    };
  }
  const grupos = new Map();
  const lucesCompletas = luces.map((l) => {
    if (l.tipo !== "puntual") return l;
    const id = l.grupo || recintoMasCercanoXZ(l.posicion, recintos) || "General";
    if (!grupos.has(id)) {
      grupos.set(id, { id, etiqueta: etiquetas[id] || NOMBRES_RECINTO[id] || id, recinto: id, encendido: false });
    }
    return { ...l, grupo: id, ampolleta: l.ampolleta || nombreAmpolleta(l.nombre), color: l.color || KELVIN_2700 };
  });
  return { luces: lucesCompletas, grupos: Array.from(grupos.values()) };
}

// Inclinación de la tecla de un interruptor según su estado (contrato v2, sección 3: ±8°).
export const TILT_TECLA_DEG = 8;

// Un interruptor (placa, tecla o lámpara) está "encendido" si alguno de sus grupos lo está. El estado sale de los
// grupos y no del propio interruptor: varios interruptores pueden mandar el mismo grupo (una tecla y su placa,
// la pantalla y el cuerpo de una lámpara, dos puntos de encendido) y los grupos de techo nacen encendidos.
// `gruposLuz`: Map id -> { encendido }.
export function interruptorEncendido(grupos, gruposLuz) {
  return grupos.some((id) => {
    const g = gruposLuz.get(id);
    return Boolean(g && g.encendido);
  });
}

// Estado de cada grupo al aplicar un momento del día (contrato v2, sección 2): un grupo queda encendido sólo si el
// momento prende las luces y el autor lo exportó con `encendido: true` (lo guarda `encendidoInicial`). Así los
// veladores, apliques y la lámpara de pie nacen apagados también de tarde y de noche, y el día apaga todo.
// `grupos`: iterable de { id, encendidoInicial (o encendido) }. -> Map id -> boolean.
export function estadoGruposParaMomento(grupos, lucesEncendidas) {
  const out = new Map();
  for (const g of grupos) {
    const deAutor = g.encendidoInicial !== undefined ? g.encendidoInicial : g.encendido;
    out.set(g.id, Boolean(lucesEncendidas) && Boolean(deAutor));
  }
  return out;
}

// Texto de la pista de un interruptor con las etiquetas de sus grupos: "Encender Living · techo"; en una placa
// doble, las dos unidas con "y". `gruposLuz`: Map id -> { etiqueta }.
export function textoInterruptor(grupos, gruposLuz, encendido) {
  const etiquetas = grupos.map((id) => gruposLuz && gruposLuz.get(id) && gruposLuz.get(id).etiqueta).filter(Boolean);
  if (!etiquetas.length) return encendido ? "Apagar la luz" : "Encender la luz";
  return `${encendido ? "Apagar" : "Encender"} ${etiquetas.join(" y ")}`;
}

// Orden de registro de interruptores[]: primero las teclas con registro propio (tecla === nodo) y después placas y
// lámparas, para que una placa doble no se quede con las mallas de sus teclas y cada tecla mande sólo su grupo.
export function ordenarInterruptores(lista) {
  const esTecla = (i) => Boolean(i.tecla) && i.tecla === i.nodo;
  return [...lista.filter(esTecla), ...lista.filter((i) => !esTecla(i))];
}

// --- A partir de aquí, THREE se recibe por parámetro: no hay `import` en este archivo. ---

// Luces con pantalla (contrato v2.1, sección 2: `cono_deg` y `direccion` en domos y focos). El visor no calcula
// sombras, así que una PointLight sola iluminaba el cielo sobre cada domo cerrado ~20 veces más que el piso: va un
// foco hacia abajo con toda la intensidad. Jaulas, veladores y apliques siguen puntuales.
// Corrección 07b (ronda 2): hasta aquí el domo era un foco (85 %) más una puntual tenue (15 %) para el rebote en el
// cielo, 8 luces más en la escena. Medido con window.__tour.medirCuadro() de ?debug, de noche a 1280 × 800 en la vista
// inicial (Intel HD Graphics 4000): 27 luces 48 ms por cuadro, 19 luces 37,5 ms, sólo el sol 15 ms. La puntual
// complementaria se quitó; el cielo de la vista inicial baja ~13 % de luminancia.
export const FRACCION_CONO = 1;
export const PENUMBRA_CONO = 0.5;

export function crearLucesTHREE(THREE, l) {
  if (l.tipo === "sol") {
    const sol = new THREE.DirectionalLight(0xfff4e5, l.intensidad ?? 3);
    sol.position.set(-l.direccion[0] * 20, -l.direccion[1] * 20, -l.direccion[2] * 20);
    sol.userData.esSol = true;
    return [sol];
  }
  const color = colorLinealAHex(l.color || KELVIN_2700);
  const potenciaW = l.potencia_w || 40;
  if (!l.cono_deg) {
    const puntual = new THREE.PointLight(color, 0, DISTANCIA_LUZ, 2);
    puntual.position.set(l.posicion[0], l.posicion[1], l.posicion[2]);
    puntual.userData.potenciaW = potenciaW;
    return [puntual];
  }
  const d = l.direccion || [0, -1, 0];
  const foco = new THREE.SpotLight(color, 0, DISTANCIA_LUZ, (l.cono_deg * Math.PI) / 180, PENUMBRA_CONO, 2);
  foco.position.set(l.posicion[0], l.posicion[1], l.posicion[2]);
  foco.target.position.set(d[0], d[1], d[2]);   // hijo del foco: se mueve con él
  foco.add(foco.target);
  foco.userData.potenciaW = potenciaW;
  foco.userData.fraccion = FRACCION_CONO;
  return [foco];
}

// Compatibilidad: la primera luz de crearLucesTHREE.
export function crearLuzTHREE(THREE, l) {
  return crearLucesTHREE(THREE, l)[0];
}

// Intensidad objetivo (grupo encendido a pleno) de una luz puntual o de su parte en cono.
export function intensidadBase(luzTHREE) {
  const f = luzTHREE.userData.fraccion ?? 1;
  return (luzTHREE.userData.potenciaW || 40) * INTENSIDAD_POR_WATT * f;
}
