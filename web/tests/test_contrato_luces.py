"""Contrato de interacción v2.2 (docs/contrato-interaccion.md, secciones 1 a 3 y 6) en lo que exporta la fase 6, sin
Blender: sólo lee exports/web/depto_colisiones.json y exports/web/depto_gltf.json.

    python3 -m unittest discover -s web/tests -p 'test_*.py'
"""
import json
import math
import os
import re
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "build"))
import depto_color as DC  # noqa: E402

WEB = os.path.join(RAIZ, "exports", "web")
APAGADOS = ("dorm1_velador_izq", "dorm1_velador_der", "dorm2_aplique_izq", "dorm2_aplique_der", "living_lampara_pie")
LUCES_JS = os.path.join(RAIZ, "web", "src", "tour", "js", "luces.js")
ESPESOR_PLACA, CAJA_SUPERFICIE = 0.012, 0.030


def _leer(nombre):
    with open(os.path.join(WEB, nombre), encoding="utf-8") as fh:
        return json.load(fh)


class ContratoLuces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.D = _leer("depto_colisiones.json")
        g = _leer("depto_gltf.json")
        cls.nodos = {n["name"]: n for n in g["nodes"] if "name" in n}
        cls.padre = {}
        for n in g["nodes"]:
            for h in n.get("children", []):
                cls.padre[g["nodes"][h]["name"]] = n.get("name")
        cls.grupos = {x["id"]: x for x in cls.D["grupos_luz"]}

    def test_grupos_luz(self):
        self.assertGreaterEqual(len(self.grupos), 14)
        etiquetas = self.D["recintos_etiquetas"]
        for g in self.D["grupos_luz"]:
            self.assertEqual(set(g) - {"kelvin", "movil"}, {"id", "etiqueta", "recinto", "encendido"}, g)
            self.assertEqual(g["id"], g["id"].lower())
            self.assertTrue(g["etiqueta"].startswith(etiquetas[g["recinto"]] + " · "), g)
            # 2700 K en general, 3000 K en cocina y baños; 5000 K sólo la luz interior de la nevera (contrato 2.2)
            self.assertIn(g.get("kelvin"), (5000,) if g.get("movil") else (2700, 3000), g)

    def test_encendido_de_autor(self):
        for gid in APAGADOS:
            self.assertIs(self.grupos[gid]["encendido"], False, gid)
        for gid, g in self.grupos.items():
            if gid.endswith("_techo") or gid in ("bano1", "bano2", "balcon", "paso_d1", "paso_d2"):
                self.assertIs(g["encendido"], True, gid)

    def test_luces_con_grupo_color_lineal_y_ampolleta(self):
        puntuales = [x for x in self.D["luces"] if x["tipo"] == "puntual"]
        self.assertGreaterEqual(len(puntuales), 17)
        for luz in puntuales:
            self.assertIn(luz["grupo"], self.grupos, luz["nombre"])
            self.assertIn(luz["ampolleta"], self.nodos, luz["nombre"])
            esperado = DC.kelvin_a_lineal(self.grupos[luz["grupo"]]["kelvin"])
            for a, b in zip(luz["color"], esperado):
                self.assertAlmostEqual(a, b, places=3, msg=luz["nombre"])
            if self.grupos[luz["grupo"]]["kelvin"] <= 3000:
                self.assertLess(luz["color"][2], 0.2, "el color debe ser lineal, no sRGB codificado")

    def test_kelvin_a_lineal(self):
        k27, k30 = DC.kelvin_a_lineal(2700), DC.kelvin_a_lineal(3000)
        self.assertEqual(k27[0], 1.0)
        self.assertTrue(0.40 < k27[1] < 0.44 and 0.08 < k27[2] < 0.12, k27)
        self.assertTrue(k30[1] > k27[1] and k30[2] > k27[2])
        srgb = [round(DC.lineal_a_srgb(c) * 255) for c in k27]
        self.assertTrue(abs(srgb[1] - 174) <= 3 and abs(srgb[2] - 89) <= 3, srgb)

    def test_interruptores_y_teclas(self):
        for reg in self.D["interruptores"]:
            nodo = self.nodos.get(reg["nodo"])
            self.assertIsNotNone(nodo, reg["nodo"])
            extras = nodo.get("extras", {})
            self.assertEqual([x for x in str(extras.get("grupo_luz", "")).split(",") if x], reg["grupos"], reg)
            if reg["tecla"]:
                self.assertIn(reg["tecla"], self.nodos)
        placas = [r for r in self.D["interruptores"] if r["nodo"].startswith("Depto_Interruptor_")
                  and not r["nodo"].endswith("_Tecla")]
        self.assertGreaterEqual(len(placas), 8)
        for placa in placas:
            teclas = sorted(n for n, p in self.padre.items() if p == placa["nodo"] and n.endswith("_Tecla"))
            self.assertEqual(len(teclas), len(placa["grupos"]), placa["nodo"])
            self.assertEqual(placa["tecla"], teclas[0] if len(teclas) == 1 else None)
            for t in teclas:
                n = self.nodos[t]
                rot = n.get("rotation", [0, 0, 0, 1])
                self.assertTrue(all(abs(a - b) < 1e-6 for a, b in zip(rot, (0, 0, 0, 1))), f"{t} girada: {rot}")
                x, y, z = n.get("translation", [0, 0, 0])
                self.assertAlmostEqual(y, 0.0, places=4, msg=t)
                self.assertTrue(any(abs(z - e) < 1e-4 for e in (ESPESOR_PLACA, ESPESOR_PLACA + CAJA_SUPERFICIE)),
                                f"{t}: eje de giro a {z} de la espalda (placa de 12 mm o caja de 30 mm)")
                self.assertTrue(any(r["nodo"] == t and r["tecla"] == t for r in self.D["interruptores"]), t)

    def test_lamparas_clicables(self):
        clicables = {r["nodo"]: r["grupos"] for r in self.D["interruptores"] if r["tecla"] is None
                     and not r["nodo"].startswith("Depto_Interruptor_")}
        for nodo, grupo in (("Depto_Mueble_Living_LamparaArco_Pantalla", "living_lampara_pie"),
                            ("Depto_Mueble_Living_LamparaArco_Tubo", "living_lampara_pie"),
                            ("Depto_Mueble_D1_LamparaMesaO_Pantalla", "dorm1_velador_izq"),
                            ("Depto_Mueble_D1_LamparaMesaO_Cuerpo", "dorm1_velador_izq"),
                            ("Depto_Mueble_D1_LamparaMesaE_Pantalla", "dorm1_velador_der"),
                            ("Depto_Mueble_D1_LamparaMesaE_Cuerpo", "dorm1_velador_der")):
            self.assertEqual(clicables.get(nodo), [grupo], nodo)

    def test_cajones_atados_a_su_hoja(self):
        por_nodo = {m["nodo"]: m for m in self.D["moviles"]}
        cajones = [m for m in self.D["moviles"] if m["nodo"].startswith("Depto_Closet_") and m["clase"] == "cajon"]
        self.assertEqual(len(cajones), 5)
        for c in cajones:
            self.assertEqual(len(c.get("depende_de", [])), 1, c["nodo"])
            hoja = por_nodo[c["depende_de"][0]]
            self.assertTrue(hoja["nodo"].endswith("_PuertaA"))
            self.assertIn(c["nodo"], hoja.get("bloquea", []))
            otra = por_nodo[hoja["nodo"][:-1] + "B"]
            self.assertIn(c["nodo"], otra.get("bloquea", []))

    def test_version_del_contrato(self):
        self.assertEqual(self.D["version"], 2)            # versión mayor (compatibilidad)
        self.assertEqual(self.D.get("contrato"), "2.5")   # versión completa del contrato (2.5: sol y cielos del exterior)

    def test_luz_de_la_nevera_la_prende_su_puerta(self):
        """Contrato 2.2: el grupo de la nevera no tiene interruptor; lo nombra `enciende` de la puerta, nace apagado y
        su luz trae un alcance corto (el visor no calcula sombras)."""
        por_nodo = {m["nodo"]: m for m in self.D["moviles"]}
        de_movil = [g for g in self.D["grupos_luz"] if "movil" in g]
        self.assertEqual([g["id"] for g in de_movil], ["cocina_nevera"])
        g = de_movil[0]
        self.assertIs(g["encendido"], False)
        self.assertIn(g["id"], por_nodo[g["movil"]].get("enciende", []))
        self.assertFalse(any(g["id"] in i["grupos"] for i in self.D["interruptores"]))
        luces = [x for x in self.D["luces"] if x.get("grupo") == g["id"]]
        self.assertEqual(len(luces), 1)
        self.assertTrue(3.0 <= luces[0]["potencia_w"] <= 5.0, luces[0])
        self.assertTrue(0 < luces[0]["alcance_m"] <= 1.5, luces[0])
        for m in self.D["moviles"]:
            for gid in m.get("enciende", []):
                self.assertIn(gid, self.grupos, m["nodo"])

    def test_entornos_locales(self):
        """Contrato 2.2, sección 6: cada entorno trae su imagen publicada junto al modelo, su caja y sus materiales."""
        ents = self.D.get("entornos", [])
        self.assertEqual([e["id"] for e in ents], ["cocina"])
        mats = {m["name"] for m in _leer("depto_gltf.json").get("materials", [])}
        for e in ents:
            for archivo in [e["imagen"], *e.get("imagenes", {}).values()]:
                self.assertTrue(os.path.exists(os.path.join(WEB, archivo)), archivo)
            self.assertEqual(set(e.get("imagenes", {})), {"luces", "dia"})
            self.assertEqual(len(e["alto"]), 2)
            x0, x1, z0, z1 = e["caja"]
            self.assertTrue(x0 < x1 and z0 < z1, e)
            self.assertTrue(x0 <= e["centro"][0] <= x1 and z0 <= e["centro"][2] <= z1, e)
            self.assertIn("Depto_Mat_NeveraAcero", e["materiales"])
            self.assertTrue(set(e["materiales"]) <= mats | {"Depto_Mat_AceroInox"}, e["materiales"])

    def test_bisagras_de_la_torre(self):
        """Corrección 07c, ronda 2: la torre tiene dos hojas por nivel (símbolo «<» del plano), con las bisagras en los
        extremos norte y sur; PuertaLavaplatos1 bloquea los cajones del módulo 3 (se cruzaban al girar)."""
        por_nodo = {m["nodo"]: m for m in self.D["moviles"]}
        torre = sorted(n for n in por_nodo if n.startswith("Depto_Mueble_Cocina_PuertaTorre"))
        self.assertEqual(torre, [f"Depto_Mueble_Cocina_PuertaTorre{n}{l}" for n in ("Alta", "Baja") for l in "NS"])
        for n in ("Baja", "Alta"):
            # y del plano -> x de glTF: las bisagras quedan en los extremos (TORRE_Y menos media junta de 3 mm)
            xn = por_nodo[f"Depto_Mueble_Cocina_PuertaTorre{n}N"]["posicion"][0]
            xs = por_nodo[f"Depto_Mueble_Cocina_PuertaTorre{n}S"]["posicion"][0]
            self.assertAlmostEqual(abs(xs - xn), (258.4 - 227.8) * 0.019 - 0.003, places=3)
        l1 = por_nodo["Depto_Mueble_Cocina_PuertaLavaplatos1"]
        self.assertEqual(sorted(l1.get("bloquea", [])), ["Depto_Mueble_Cocina_Cajon3Inf", "Depto_Mueble_Cocina_Cajon3Sup"])

    def test_nombres_recinto_del_visor(self):
        """El respaldo NOMBRES_RECINTO de luces.js dice lo mismo que recintos_etiquetas (una sola fuente de verdad:
        RECINTOS_ETIQUETAS de build/depto_04_mobiliario.py)."""
        with open(LUCES_JS, encoding="utf-8") as fh:
            js = fh.read()
        bloque = re.search(r"export const NOMBRES_RECINTO = \{(.*?)\};", js, re.S).group(1)
        nombres = dict(re.findall(r'(\w+): "([^"]*)"', bloque))
        self.assertEqual(nombres, self.D["recintos_etiquetas"])

    def test_ampolletas_distintas(self):
        amp = [x["ampolleta"] for x in self.D["luces"] if x["tipo"] == "puntual"]
        self.assertEqual(len(amp), len(set(amp)))
        self.assertFalse(any(math.isnan(c) for x in self.D["luces"] if x["tipo"] == "puntual" for c in x["color"]))


if __name__ == "__main__":
    unittest.main()
