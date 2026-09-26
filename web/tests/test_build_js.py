"""Pruebas de las partes de web/build.py que dependen del JS del sitio (hallazgos JS-1 y JS-2 de la revisión de la
rama web/i18n-base), sin red ni Netlify:  python3 -m unittest discover -s web/tests -p 'test_*.py'

- JS-1: el tour sólo se publica en en/ y fr/ (y con reglas Language=) si su JS resuelve el modelo con import.meta.url.
- JS-2: web/src/js/textos-es.js, el respaldo en español de i18n.js, coincide con las claves js.* de es.json.
"""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build  # noqa: E402

DATOS_I18N = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos", "i18n")   # mini sitio en 3 idiomas
# Las dos formas de RUTA_MODELO: la de hoy (relativa a la página) y la que pide el mecanismo acordado.
CARGA_PAGINA = 'export const RUTA_MODELO = "modelo/";\nfetch(RUTA_MODELO + "depto_colisiones.json");\n'
CARGA_MODULO = ('export const RUTA_MODELO = new URL("../modelo/", import.meta.url).href;\n'
                'fetch(RUTA_MODELO + "depto_colisiones.json");\n')


def _escribir(ruta, texto):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)


def _leer(*partes):
    with open(os.path.join(*partes), encoding="utf-8") as fh:
        return fh.read()


@contextlib.contextmanager
def con_dist(d):
    viejo, build.DIST = build.DIST, d
    try:
        yield d
    finally:
        build.DIST = viejo


class TourTraducible(unittest.TestCase):
    def _con_js(self, archivos):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        for nombre, texto in archivos.items():
            _escribir(os.path.join(d, "tour", "js", nombre), texto)
        return d

    def test_ruta_relativa_a_la_pagina_no_se_traduce(self):
        self.assertFalse(build.tour_traducible(self._con_js({"carga.js": CARGA_PAGINA})))
        self.assertFalse(build.tour_traducible(self._con_js({"carga.js": "export const RUTA_MODELO = './modelo/';"})))
        # carga.js sin RUTA_MODELO armada con import.meta.url tampoco (p. ej. otra ruta fija)
        self.assertFalse(build.tour_traducible(self._con_js({"carga.js": 'export const RUTA_MODELO = "/tour/modelo/";'})))

    def test_import_meta_url_si_se_traduce(self):
        self.assertTrue(build.tour_traducible(self._con_js({"carga.js": CARGA_MODULO, "main.js": "export {};"})))
        self.assertTrue(build.tour_traducible(self._con_js(
            {"carga.js": "export const RUTA_MODELO = new URL('../modelo/', import.meta.url).href;"})))

    def test_otro_modulo_con_ruta_de_la_pagina(self):
        d = self._con_js({"carga.js": CARGA_MODULO, "cielo.js": 'loader.load("modelo/cielo.jpg");'})
        self.assertFalse(build.tour_traducible(d))

    def test_sin_js_del_tour(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        self.assertTrue(build.tour_traducible(d))
        self.assertTrue(build.tour_traducible(self._con_js({"main.js": "export {};"})))    # el mini sitio de pruebas

    def test_src_real_coincide_con_su_carga_js(self):
        """El veredicto sobre web/src coincide con leer carga.js a mano (sin las expresiones de build.py)."""
        carga = _leer(build.SRC, "tour", "js", "carga.js")
        linea = next(l for l in carga.splitlines() if l.startswith("export const RUTA_MODELO"))
        esperado = "import.meta.url" in linea and "new URL(" in linea
        self.assertEqual(build.tour_traducible(build.SRC), esperado, linea)


class TourEnElSitio(unittest.TestCase):
    """build.idiomas() sobre el mini sitio de web/tests/datos/i18n con un carga.js de cada forma."""

    def _armar(self, carga):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        shutil.copytree(DATOS_I18N, d, dirs_exist_ok=True)
        os.remove(os.path.join(d, "LEEME.txt"))
        _escribir(os.path.join(d, "tour", "js", "carga.js"), carga)
        with con_dist(d), contextlib.redirect_stdout(io.StringIO()) as salida:
            paginas = build.idiomas(build.SITIO_URL)
            faltan = build.revisar_enlaces(build.SITIO_URL)
        return d, paginas, faltan, salida.getvalue()

    def test_con_ruta_de_la_pagina_no_hay_tour_en_otro_idioma_ni_reglas(self):
        d, paginas, faltan, salida = self._armar(CARGA_PAGINA)
        self.assertNotIn("tour/index.html", paginas)
        self.assertTrue(paginas, "las demás páginas sí se traducen")
        self.assertEqual(faltan, [])
        for idioma in ("en", "fr"):
            self.assertFalse(os.path.exists(os.path.join(d, idioma, "tour")), idioma)
        redirects = _leer(d, "_redirects")
        self.assertIsNone(re.search(r"^/tour/", redirects, re.M), redirects)       # quien entra a /tour/ se queda ahí
        self.assertIn("Language=en", redirects)
        self.assertIn("AVISO_I18N tour/: no se publica en en/ ni fr/", salida)
        # los enlaces al tour desde /en/ van al tour compartido de la raíz, que existe y carga su modelo
        self.assertIn('href="../tour/"', _leer(d, "en", "index.html"))

    def test_con_import_meta_url_el_tour_se_publica_con_sus_reglas(self):
        d, paginas, faltan, salida = self._armar(CARGA_MODULO)
        self.assertIn("tour/index.html", paginas)
        self.assertEqual(faltan, [])
        self.assertTrue(os.path.exists(os.path.join(d, "en", "tour", "index.html")))
        self.assertRegex(_leer(d, "_redirects"), r"(?m)^/tour/\s+/en/tour/\s+302!\s+Language=en$")
        self.assertNotIn("AVISO_I18N tour/", salida)
        self.assertIn('src="../../tour/js/main.js"', _leer(d, "en", "tour", "index.html"))   # un solo JS del tour


class TextosEs(unittest.TestCase):
    def _carpeta(self, es, textos=None, i18n_js=True):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        _escribir(os.path.join(d, "i18n", "es.json"), json.dumps(es, ensure_ascii=False))
        if i18n_js:
            _escribir(os.path.join(d, "js", "i18n.js"), "export {};\n")
        if textos is not None:
            _escribir(os.path.join(d, "js", "textos-es.js"), textos)
        return d

    def test_modulo_con_las_claves_js_en_su_orden(self):
        es = {"inicio.titulo": "Inicio", "js.b": "Bé «x» \"y\" \\ {n}", "js.a": "A B", "tour.x": "T"}
        texto = build.textos_es_js(es)
        self.assertTrue(texto.startswith("// Generado por web/build.py"))
        cuerpo = re.search(r"(?s)^export default (\{.*\});\n\Z", texto, re.M)
        self.assertIsNotNone(cuerpo, texto)
        datos = json.loads(cuerpo.group(1))                    # JSON válido, y por eso también JS válido
        self.assertEqual(list(datos.items()), [("js.b", es["js.b"]), ("js.a", es["js.a"])])   # sólo js.*, en orden

    def test_revisar_textos_es(self):
        es = {"js.a": "A", "otra": "B"}
        build.revisar_textos_es(self._carpeta(es, build.textos_es_js(es)))                 # al día: no falla
        for malo in (None, build.textos_es_js({"js.a": "Otro"}), build.textos_es_js({}), "export default {};\n"):
            with self.assertRaises(SystemExit) as e:
                build.revisar_textos_es(self._carpeta(es, malo))
            self.assertIn("--textos-es", str(e.exception))
        build.revisar_textos_es(self._carpeta(es, None, i18n_js=False))                      # sin i18n.js: nada que revisar

    def test_src_real_al_dia(self):
        """web/src/js/textos-es.js es exactamente lo que genera build.py desde web/src/i18n/es.json."""
        es = build.leer_diccionario(os.path.join(build.SRC, "i18n", "es.json"))
        self.assertEqual(_leer(build.SRC, "js", "textos-es.js"), build.textos_es_js(es),
                         "regenéralo con  python3 web/build.py --textos-es")
        build.revisar_textos_es(build.SRC)


if __name__ == "__main__":
    unittest.main()
