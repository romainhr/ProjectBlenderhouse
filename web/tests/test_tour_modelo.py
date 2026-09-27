"""web/tour_modelo.py con un export mínimo sintético (sin Blender ni los exports reales):

    python3 -m unittest discover -s web/tests -p 'test_*.py'

Bloque 08 (contrato 2.3, sección 4): los cielos que nombra exterior.panoramas llegan a modelo/tex/ tal cual, sin gemela
.webp ni copia en tex_movil/, y si falta uno la construcción se detiene.
"""
import base64
import json
import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tour_modelo  # noqa: E402


def export_minimo(carpeta, con_cielos=True):
    web = os.path.join(carpeta, "web")
    tex = os.path.join(web, "tex")
    os.makedirs(tex)
    Image.new("RGB", (64, 64), (120, 90, 60)).save(os.path.join(tex, "fachada_A.jpg"))
    if con_cielos:
        for k in ("dia", "tarde"):
            Image.new("RGB", (128, 64), (90, 120, 200)).save(os.path.join(tex, f"cielo_{k}.jpg"))
    gltf = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4, "uri": "depto_bin.b64.txt"}],
            "images": [{"uri": "tex/fachada_A.jpg", "mimeType": "image/jpeg"}], "textures": [{"source": 0}],
            "materials": [{"name": "Depto_Ext_Mat_FachadaA", "extras": {"exterior": True},
                           "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}]}
    with open(os.path.join(web, "depto_gltf.json"), "w") as fh:
        json.dump(gltf, fh)
    with open(os.path.join(web, "depto_bin.b64.txt"), "w") as fh:
        fh.write(base64.b64encode(b"\0\0\0\0").decode())
    col = os.path.join(carpeta, "depto_colisiones.json")
    with open(col, "w") as fh:
        json.dump({"version": 2, "exterior": {"panoramas": {"dia": "tex/cielo_dia.jpg", "tarde": "tex/cielo_tarde.jpg",
                                                            "noche": "tex/cielo_tarde.jpg"},
                                              "rotacion_deg": 149.3, "suelo_y": -12.5}}, fh)
    return web, col


class Cielos(unittest.TestCase):
    def test_panoramas_tal_cual_en_las_dos_variantes(self):
        with tempfile.TemporaryDirectory() as d:
            web, col = export_minimo(d)
            destino = os.path.join(d, "modelo")
            tour_modelo.construir(web, col, destino)
            tex = set(os.listdir(os.path.join(destino, "tex")))
            movil = set(os.listdir(os.path.join(destino, "tex_movil")))
            self.assertTrue({"cielo_dia.jpg", "cielo_tarde.jpg"} <= tex, tex)
            self.assertFalse({"cielo_dia.webp", "cielo_tarde.webp"} & tex, tex)
            self.assertFalse({n for n in movil if n.startswith("cielo_")}, movil)
            self.assertTrue({"fachada_A.jpg", "fachada_A.webp"} <= tex, tex)       # las texturas siguen igual
            self.assertTrue({"fachada_A.jpg", "fachada_A.webp"} <= movil, movil)
            with open(os.path.join(destino, "depto_colisiones.json")) as fh:
                ext = json.load(fh)["exterior"]
            for ruta in ext["panoramas"].values():                                # rutas del visor: modelo/<ruta>
                self.assertTrue(os.path.exists(os.path.join(destino, ruta)), ruta)
            self.assertGreater(tour_modelo.construir.ultimos_pesos["cielos"], 0)

    def test_falta_un_panorama(self):
        with tempfile.TemporaryDirectory() as d:
            web, col = export_minimo(d, con_cielos=False)
            with self.assertRaises(SystemExit):
                tour_modelo.construir(web, col, os.path.join(d, "modelo"))

    def test_panorama_fuera_de_tex(self):
        with self.assertRaises(SystemExit):
            tour_modelo.panoramas({"exterior": {"panoramas": {"dia": "../cielo.jpg"}}})
        self.assertEqual(tour_modelo.panoramas({}), set())


if __name__ == "__main__":
    unittest.main()
