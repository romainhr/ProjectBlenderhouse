// Lógica pura de colisión: cilindro (el caminante, radio D.radio) contra cajas en el plano XZ.
// Sin dependencias (ni de three.js ni del DOM) para que web/tests/*.test.mjs la importe directo.
// Ejes: coordenadas glTF (Y arriba, +Y del frente hacia -Z). Cajas estáticas: [xmin, xmax, zmin, zmax].
// Reutiliza la lógica de exports/depto_tour.html (chocaCaja/estadoMovil/chocaMovil/libre/libreCercano),
// reescrita como funciones puras con el estado como parámetro en vez de variables globales del módulo.

export function chocaCaja(x, z, caja, r) {
  const cx = Math.max(caja[0], Math.min(x, caja[1]));
  const cz = Math.max(caja[2], Math.min(z, caja[3]));
  const dx = x - cx, dz = z - cz;
  return dx * dx + dz * dz < r * r;
}

// Posición y ángulo de una pieza móvil con apertura t (0 cerrada, 1 abierta). `m` es el objeto `moviles[i]`
// del contrato (depto_colisiones.json): tipo "bisagra" (gira en torno a +Y de glTF) o "corredera" (se desplaza
// a lo largo de `eje`, un vector XZ unitario).
export function estadoMovil(m, t) {
  if (m.tipo === "bisagra") return { x: m.posicion[0], z: m.posicion[2], ang: m.angulo_abierto * t };
  const k = t - (m.abierta ? 1 : 0);
  return { x: m.posicion[0] + m.eje[0] * m.recorrido * k, z: m.posicion[2] + m.eje[1] * m.recorrido * k, ang: 0 };
}

// ¿El cilindro en (x,z) choca con alguna de las cajas locales de la pieza móvil `v` (= {m, t})?
// Las cajas locales están en el espacio de la pieza; se transforman al mundo con la inversa del giro en Y.
export function chocaMovil(x, z, v, t, r) {
  const e = estadoMovil(v.m, t);
  const px = x - e.x, pz = z - e.z, ca = Math.cos(e.ang), sa = Math.sin(e.ang);
  const lx = px * ca - pz * sa, lz = px * sa + pz * ca;
  return v.m.cajas_locales.some((c) => chocaCaja(lx, lz, c, r));
}

// `moviles` es un arreglo de {m, t} (t = apertura actual, 0..1). Los cajones (clase "cajon") no bloquean el
// recorrido, según el contrato de interacción.
export function libre(x, z, estaticos, moviles, radio) {
  for (const c of estaticos) if (chocaCaja(x, z, c, radio)) return false;
  for (const v of moviles) {
    if (v.m.clase === "cajon") continue;
    if (chocaMovil(x, z, v, v.t, radio)) return false;
  }
  return true;
}

export function libreCercano(x, z, estaticos, moviles, radio) {
  if (libre(x, z, estaticos, moviles, radio)) return [x, z];
  for (let rad = 0.05; rad <= 0.8; rad += 0.05) {
    for (let a = 0; a < Math.PI * 2; a += Math.PI / 12) {
      const nx = x + Math.cos(a) * rad, nz = z + Math.sin(a) * rad;
      if (libre(nx, nz, estaticos, moviles, radio)) return [nx, nz];
    }
  }
  return [x, z];
}

// Desplaza (x,z) por (dx,dz) en subpasos de máximo `paso` metros, deslizando a lo largo de las paredes
// (primero el movimiento completo, si no se puede solo el eje X, si no solo el eje Z). Devuelve la posición
// final; no muta los argumentos.
export function mover(x, z, dx, dz, estaticos, moviles, radio, paso = 0.08) {
  const n = Math.max(1, Math.ceil(Math.hypot(dx, dz) / paso));
  const px = dx / n, pz = dz / n;
  let cx = x, cz = z;
  for (let i = 0; i < n; i++) {
    if (libre(cx + px, cz + pz, estaticos, moviles, radio)) { cx += px; cz += pz; }
    else if (libre(cx + px, cz, estaticos, moviles, radio)) cx += px;
    else if (libre(cx, cz + pz, estaticos, moviles, radio)) cz += pz;
  }
  return [cx, cz];
}
