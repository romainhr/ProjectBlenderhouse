"""Las páginas públicas de web/src y sus diccionarios pasan la compuerta de idiomas de web/build.py (ADR 0007).

Sin armar el sitio entero (imágenes, tour/modelo): sólo las funciones puras del build sobre el HTML real.
   python3 -m unittest discover -s web/tests -p 'test_*.py'
"""
import os
import re
import sys
import unittest

WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WEB)
import build  # noqa: E402

SRC = os.path.join(WEB, "src")
PAGINAS = {"index.html", "reserva.html", "privacidad.html", "404.html", "tour/index.html"}


def fuentes():
    datos = {}
    for ruta in build.paginas_traducibles(SRC):
        with open(os.path.join(SRC, *ruta.split("/")), encoding="utf-8") as fh:
            datos[ruta] = fh.read()
    return datos


class CompuertaDeIdiomas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fuentes = fuentes()
        cls.dics = build.cargar_diccionarios(os.path.join(SRC, "i18n"))

    def test_sin_errores_ni_avisos(self):
        """Lo mismo que el build imprimiría como error o como AVISO_I18N: nada."""
        errores, avisos = build.validar_i18n(self.fuentes, self.dics)
        self.assertEqual(errores, [])
        self.assertEqual(avisos, [])

    def test_se_publican_las_cinco_paginas_con_el_tour(self):
        self.assertTrue(build.tour_traducible(SRC), "carga.js debe armar RUTA_MODELO con import.meta.url")
        paginas, avisos = build.publicables(self.fuentes, build.tour_traducible(SRC))
        self.assertEqual(paginas, PAGINAS)
        self.assertEqual(avisos, [])

    def test_cada_pagina_traducida_queda_en_su_idioma(self):
        for ruta in sorted(PAGINAS):
            for idioma in ("en", "fr"):
                with self.subTest(pagina=ruta, idioma=idioma):
                    s = build.traducir_pagina(self.fuentes[ruta], ruta, idioma, self.dics[idioma], PAGINAS)
                    self.assertIn(f'<html lang="{idioma}">', s)
                    titulo = re.search(r"<title[^>]*>([^<]*)</title>", s).group(1)
                    self.assertIn("Project-roomVR", titulo)
                    self.assertNotEqual(titulo, re.search(r"<title[^>]*>([^<]*)</title>", self.fuentes[ruta]).group(1))
                    # el selector apunta a esta misma página en los tres idiomas y marca el actual
                    actuales = re.findall(r'<a data-i18n-alternar="(\w+)" href="([^"]+)"[^>]*aria-current="true"', s)
                    self.assertTrue(actuales)
                    self.assertTrue(all(i == idioma and h == build.url_de_pagina(ruta, idioma) for i, h in actuales))
                    # ningún texto marcado queda en español cuando su traducción es otra
                    for mk in build.marcas_i18n(self.fuentes[ruta], ruta):
                        if mk.atributo is None and self.dics[idioma][mk.clave] != self.dics["es"][mk.clave]:
                            self.assertNotIn(f">{mk.texto.strip()}<", s, f"{mk.clave} quedó en español")

    def test_tour_en_otro_idioma_usa_el_js_y_el_modelo_de_tour(self):
        s = build.traducir_pagina(self.fuentes["tour/index.html"], "tour/index.html", "en", self.dics["en"], PAGINAS)
        self.assertIn('<script type="module" src="../../tour/js/main.js"></script>', s)
        self.assertIn('href="../../tour/tour.css"', s)
        with open(os.path.join(SRC, "tour", "js", "carga.js"), encoding="utf-8") as fh:
            self.assertRegex(fh.read(), r'RUTA_MODELO = new URL\("\.\./modelo/", import\.meta\.url\)\.href;')


if __name__ == "__main__":
    unittest.main()
