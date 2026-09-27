// Nombres de recinto en el plano del tour (web/src/tour/js/minimapa.js, ubicarEtiquetas), en los tres idiomas:
//   cd web && npm test
// - ninguna etiqueta pisa a otra (antes, «Clósets del principal» pisaba a «Baño principal» también en español, y en
//   francés «Placards de la chambre principale», achicada a 10 px, se cruzaba 122 × 6 px con «Salle de bains
//   principale»);
// - ninguna baja de TAM_MIN px ni pasa de ANCHO_ETIQUETA del plano por línea: la que no cabe va en dos líneas;
// - todas quedan dentro del lienzo y cerca del centro de su recinto.
// Los anchos salen de una medida aproximada (0,55 em por carácter, algo más que Public Sans 500, que ronda 0,48 em).
// En el navegador, con measureText real, se midió lo mismo en /tour/, /en/tour/ y /fr/tour/: ningún cruce.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  ANCHO_ETIQUETA, SEPARACION_ETIQUETAS, TAM_MIN, fuenteEtiqueta, remedirConLaFuente, transformacionPlano, ubicarEtiquetas,
} from "../src/tour/js/minimapa.js";

const leerJSON = (ruta) => JSON.parse(readFileSync(new URL(ruta, import.meta.url), "utf8"));
const D = leerJSON("../../exports/web/depto_colisiones.json");
const DICCIONARIOS = Object.fromEntries(["es", "en", "fr"].map((i) => [i, leerJSON(`../src/i18n/${i}.json`)]));
const HTML = readFileSync(new URL("../src/tour/index.html", import.meta.url), "utf8");
const [, W, H] = HTML.match(/<canvas id="lienzo-plano" width="(\d+)" height="(\d+)"/).map(Number);

const medir = (texto, tam) => [...texto].length * 0.55 * tam;

/** Etiquetas del plano en `idioma`, como las arma etiquetasRecintos (centro de cada recinto, nombre del diccionario). */
function etiquetas(idioma) {
  const { a } = transformacionPlano(D, W, H);
  const lista = Object.entries(D.recintos).map(([k, p]) => {
    const [x, y] = a(p[0], p[1]);
    return { id: k, texto: DICCIONARIOS[idioma][`js.tour.recinto.${k}`], x, y };
  });
  return { lista, puestas: ubicarEtiquetas(lista, medir, { W, H }) };
}

const cruce = (p, q) => [Math.min(p.x1, q.x1) - Math.max(p.x0, q.x0), Math.min(p.y1, q.y1) - Math.max(p.y0, q.y0)];

test("plano: el lienzo y los recintos del modelo exportado son los de siempre", () => {
  assert.deepEqual([W, H], [380, 560]);
  assert.ok(Object.keys(D.recintos).length >= 10);
  for (const idioma of Object.keys(DICCIONARIOS)) {
    for (const k of Object.keys(D.recintos)) assert.ok(DICCIONARIOS[idioma][`js.tour.recinto.${k}`], `${idioma}: ${k}`);
  }
});

test("plano: sin mover nada, los clósets y el baño de cada dormitorio se pisaban (el caso que hay que resolver)", () => {
  const { lista } = etiquetas("es");
  const pos = Object.fromEntries(lista.map((e) => [e.id, e]));
  for (const [p, q] of [["Paso_D1", "Bano1"], ["Paso_D2", "Bano2"]]) {
    assert.ok(Math.hypot(pos[p].x - pos[q].x, pos[p].y - pos[q].y) < 40, `${p} y ${q} tienen el centro a menos de 40 px`);
  }
});

for (const idioma of ["es", "en", "fr"]) {
  test(`plano en ${idioma}: ninguna etiqueta pisa a otra, ni baja de ${TAM_MIN} px, ni se sale del lienzo`, () => {
    const { lista, puestas } = etiquetas(idioma);
    for (let i = 0; i < puestas.length; i++) {
      const e = puestas[i];
      assert.ok(e.tam >= TAM_MIN, `${e.texto}: ${e.tam} px`);
      assert.ok(e.lineas.length <= 2, e.texto);
      assert.equal(e.lineas.join(" "), lista[i].texto);
      for (const l of e.lineas) assert.ok(medir(l, e.tam) <= W * ANCHO_ETIQUETA, `${e.texto}: «${l}» no cabe`);
      assert.ok(e.caja.x0 >= 0 && e.caja.x1 <= W && e.caja.y0 >= 0 && e.caja.y1 <= H, `${e.texto}: fuera del lienzo`);
      assert.ok(Math.abs(e.y - lista[i].y) <= 48 && Math.abs(e.x - lista[i].x) <= 1, `${e.texto}: lejos de su recinto`);
      for (let j = 0; j < i; j++) {
        const [w, h] = cruce(e.caja, puestas[j].caja);
        assert.ok(w <= -SEPARACION_ETIQUETAS || h <= -SEPARACION_ETIQUETAS,
          `«${e.texto}» y «${puestas[j].texto}» se pisan (${w.toFixed(0)} × ${h.toFixed(0)} px)`);
      }
    }
  });
}

test("plano: una etiqueta que cabe en una línea no se corta, y la que no, se corta en dos líneas parejas", () => {
  const [corta] = ubicarEtiquetas([{ texto: "Hall", x: 100, y: 100 }], medir, { W, H });
  assert.deepEqual([corta.lineas, corta.tam], [["Hall"], Math.round(W / 26)]);
  const [larga] = ubicarEtiquetas([{ texto: "Placards de la chambre principale", x: 200, y: 200 }], medir, { W, H });
  assert.deepEqual(larga.lineas, ["Placards de la", "chambre principale"]);
  assert.ok(larga.tam >= TAM_MIN);
});

test("plano: dos etiquetas con el mismo centro quedan una debajo de la otra, a la separación mínima", () => {
  const [a, b] = ubicarEtiquetas([{ texto: "Baño principal", x: 200, y: 200 }, { texto: "Segundo baño", x: 200, y: 200 }],
    medir, { W, H });
  assert.equal(a.y, 200);
  assert.ok(b.caja.y0 >= a.caja.y1 + SEPARACION_ETIQUETAS || b.caja.y1 <= a.caja.y0 - SEPARACION_ETIQUETAS);
  assert.ok(Math.abs(b.y - 200) <= a.caja.y1 - a.caja.y0 + SEPARACION_ETIQUETAS + 1);
});

test("plano: cuando llega Public Sans (o termina otra carga de letras) se vuelven a medir las etiquetas", async () => {
  let cumplir;
  const pedidas = [], oyentes = {};
  const fuentes = {
    load: (f) => { pedidas.push(f); return new Promise((ok) => { cumplir = ok; }); },
    addEventListener: (tipo, fn) => { oyentes[tipo] = fn; },
  };
  const M = { etiquetas: [{ texto: "medida con la letra de respaldo" }], ultX: 1 };
  remedirConLaFuente(M, fuentes);
  assert.deepEqual(pedidas, [fuenteEtiqueta(16)]);
  assert.match(pedidas[0], /^500 16px "Public Sans"/);        // la misma letra con que se miden y dibujan
  assert.ok(M.etiquetas, "no se descarta antes de que llegue");
  cumplir();
  await new Promise((ok) => setTimeout(ok, 0));
  assert.deepEqual([M.etiquetas, M.ultX], [null, null]);       // se vuelven a medir y se fuerza el redibujo
  M.etiquetas = []; M.ultX = 1;
  oyentes.loadingdone();
  assert.deepEqual([M.etiquetas, M.ultX], [null, null]);
  remedirConLaFuente(M, undefined);                            // sin FontFaceSet (Node) no falla
});
