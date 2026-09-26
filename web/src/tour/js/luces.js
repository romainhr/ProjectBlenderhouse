// Luces y grupos de luz. Las funciones puras (sin `import`, para que web/tests/*.test.mjs las use directo)
// deducen los grupos cuando el modelo todavía no trae `grupos_luz` (contrato de interacción v2, sección 2):
// "un grupo por recinto según el punto de recintos más cercano en XZ, con la ampolleta como nodo de nombre
// luces[i].nombre sin el prefijo Depto_Luz_". Las funciones que construyen objetos de three.js reciben el
// espacio de nombres THREE como parámetro (inyección) en vez de importarlo, por la misma razón.

export const NOMBRES_RECINTO = {
  Hall: "Hall", Living: "Living", Cocina: "Cocina", Dorm1: "Dormitorio 1", Dorm2: "Dormitorio 2",
  Paso_D1: "Paso del dormitorio 1", Paso_D2: "Paso del dormitorio 2", Bano1: "Baño 1", Bano2: "Baño 2",
  Balcon: "Balcón",
};

// 2700 K en lineal, según el contrato de interacción (sección 2).
export const KELVIN_2700 = [1.0, 0.72, 0.42];
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

// --- A partir de aquí, THREE se recibe por parámetro: no hay `import` en este archivo. ---

export function crearLuzTHREE(THREE, l) {
  if (l.tipo === "sol") {
    const sol = new THREE.DirectionalLight(0xfff4e5, l.intensidad ?? 3);
    sol.position.set(-l.direccion[0] * 20, -l.direccion[1] * 20, -l.direccion[2] * 20);
    sol.userData.esSol = true;
    return sol;
  }
  const luz = new THREE.PointLight(colorLinealAHex(l.color || KELVIN_2700), 0, DISTANCIA_LUZ, 2);
  luz.position.set(l.posicion[0], l.posicion[1], l.posicion[2]);
  luz.userData.potenciaW = l.potencia_w || 40;
  return luz;
}

// Intensidad objetivo (grupo encendido a pleno) de una luz puntual.
export function intensidadBase(luzTHREE) {
  return (luzTHREE.userData.potenciaW || 40) * INTENSIDAD_POR_WATT;
}
