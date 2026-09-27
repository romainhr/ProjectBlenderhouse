"""Contrato de interacción 2.3, sección 4 (exterior, bloque 08) en lo que exporta la fase 6, sin Blender: lee
exports/web/depto_colisiones.json y exports/web/depto_gltf.json.

    python3 -m unittest discover -s web/tests -p 'test_*.py'
"""
import json
import os
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB = os.path.join(RAIZ, "exports", "web")
TOPE_EXTERIOR = 15_000          # encargo del bloque 08
TOPE_ESCENA = 200_000           # build/depto_geom.py, TOPE_TRIANGULOS


def _leer(nombre):
    with open(os.path.join(WEB, nombre), encoding="utf-8") as fh:
        return json.load(fh)


def _tris_primitiva(gltf, prim):
    if "indices" in prim:
        return gltf["accessors"][prim["indices"]]["count"] // 3
    return gltf["accessors"][prim["attributes"]["POSITION"]]["count"] // 3


class ContratoExterior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.D = _leer("depto_colisiones.json")
        cls.g = _leer("depto_gltf.json")
        cls.mats = cls.g.get("materials", [])

    def test_panoramas_por_momento(self):
        ext = self.D["exterior"]
        self.assertEqual(set(ext["panoramas"]), {"dia", "tarde", "noche"})
        for momento, ruta in ext["panoramas"].items():
            self.assertTrue(ruta.startswith("tex/") and ruta.endswith(".jpg"), ruta)
            self.assertTrue(os.path.exists(os.path.join(WEB, ruta)), ruta)          # modelo/<ruta> en el visor
        self.assertIsInstance(ext["rotacion_deg"], (int, float))
        self.assertTrue(-180 < ext["rotacion_deg"] <= 180, ext["rotacion_deg"])
        self.assertLess(ext["suelo_y"], -10)                                          # un 5.º piso: la calle, abajo
        self.assertEqual(set(ext["emision"]), {"dia", "tarde", "noche"})
        self.assertEqual(ext["emision"]["dia"], 0)
        self.assertEqual(ext["emision"]["noche"], 1)
        self.assertEqual(set(ext["cielos"]), {"dia", "tarde", "noche"})

    def test_materiales_del_exterior_marcados(self):
        ext = [m for m in self.mats if m["name"].startswith("Depto_Ext_Mat_")]
        self.assertGreaterEqual(len(ext), 10)
        for m in ext:
            self.assertIs(m.get("extras", {}).get("exterior"), True, m["name"])
            self.assertIn(m["extras"].get("exterior_capa"), ("cerca", "lejos"), m["name"])
        for m in self.mats:
            if not m["name"].startswith("Depto_Ext_Mat_"):
                self.assertFalse(m.get("extras", {}).get("exterior"), m["name"])
        # las ventanas vecinas llevan su emisión de noche (el visor la escala por momento)
        emisivos = [m["name"] for m in ext if "emissiveTexture" in m]
        for n in ("Depto_Ext_Mat_FachadaA", "Depto_Ext_Mat_FachadaB", "Depto_Ext_Mat_FachadaC",
                  "Depto_Ext_Mat_FachadaD", "Depto_Ext_Mat_VentanasPropias", "Depto_Ext_Mat_Paleta"):
            self.assertIn(n, emisivos)
        vidrio = next(m for m in ext if m["name"] == "Depto_Ext_Mat_VidrioBaranda")
        self.assertEqual(vidrio.get("alphaMode"), "BLEND")

    def test_presupuesto_y_nodos(self):
        nombres_mat = [m["name"] for m in self.mats]
        tris_ext = tris = 0
        nodos_ext = [n for n in self.g["nodes"] if n.get("name", "").startswith("Depto_Ext_")]
        self.assertGreaterEqual(len(nodos_ext), 12)
        for n in self.g["nodes"]:
            if "mesh" not in n:
                continue
            ext = n.get("name", "").startswith("Depto_Ext_")
            for prim in self.g["meshes"][n["mesh"]]["primitives"]:
                t = _tris_primitiva(self.g, prim)
                tris += t
                if ext:
                    tris_ext += t
                    self.assertTrue(nombres_mat[prim["material"]].startswith("Depto_Ext_Mat_"), n["name"])
                    self.assertIn("TEXCOORD_0", prim["attributes"], n["name"])
            if ext:
                self.assertIs(n.get("extras", {}).get("exterior"), True, n["name"])
                self.assertIs(n.get("extras", {}).get("colision"), False, n["name"])
        self.assertLessEqual(tris_ext, TOPE_EXTERIOR)
        self.assertLessEqual(tris, TOPE_ESCENA)

    def test_sin_colision(self):
        """Ninguna caja estática del recorrido queda en el exterior (a más de 2 m del depto y su balcón)."""
        for x0, x1, z0, z1 in self.D["estaticos"]:
            self.assertTrue(-7.0 < x0 and x1 < 7.0 and -6.0 < z0 and z1 < 7.0, (x0, x1, z0, z1))


if __name__ == "__main__":
    unittest.main()
