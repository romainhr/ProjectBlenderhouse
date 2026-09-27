"""Contrato entre el portal (/admin, vista Textos) y el marcado de idiomas de las páginas públicas.

El portal dice que un inglés o un francés vacío (valor_en o valor_fr en null) deja en /en/ y /fr/ «el texto fijo de la
página». Ese texto fijo sólo es una traducción si el elemento con data-contenido también lleva data-i18n y su clave
tiene texto en en.json y en fr.json; si no, /en/ y /fr/ muestran el español original (hallazgo P3 de la revisión).

Estas pruebas lo exigen en cada página pública que ya tiene marcado data-i18n. Las que todavía no lo tienen (el
marcado y sus traducciones llegan en una PR posterior del sitio) quedan omitidas con su nombre, para que se vean.
   python3 -m unittest discover -s web/tests -p 'test_*.py'
"""
import json
import os
import sys
import unittest

WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WEB)
import build  # noqa: E402

SRC = os.path.join(WEB, "src")
TRADUCCIONES = ("en", "fr")                      # los idiomas con columna propia en public.contenido (0005)


def diccionarios(carpeta):
    """{idioma: {clave: texto}} de <carpeta>/en.json y fr.json ({} si falta uno)."""
    dics = {}
    for idioma in TRADUCCIONES:
        ruta = os.path.join(carpeta, f"{idioma}.json")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as fh:
                dics[idioma] = json.load(fh)
        else:
            dics[idioma] = {}
    return dics


def contenidos_sin_traduccion(html, dics):
    """[(clave de data-contenido, motivo)] de los elementos editables desde el portal que en /en/ o /fr/ no tendrían
    traducción fija: sin data-i18n en el mismo elemento, o con una clave sin texto en en.json o fr.json."""
    faltan = []
    for m in build._etiquetas(html):
        attrs = build._atributos(m)
        if "data-contenido" not in attrs:
            continue
        contenido = attrs["data-contenido"].valor
        if "data-i18n" not in attrs:
            faltan.append((contenido, "sin data-i18n"))
            continue
        clave = attrs["data-i18n"].valor.strip()
        for idioma in TRADUCCIONES:
            texto = dics.get(idioma, {}).get(clave)
            if not isinstance(texto, str) or not texto.strip():
                faltan.append((contenido, f"data-i18n={clave} sin texto en {idioma}.json"))
    return faltan


def paginas_publicas(src=SRC):
    """Rutas (con /) de las páginas que también se publican en /en/ y /fr/, como build.paginas_traducibles()."""
    return sorted(build.paginas_traducibles(src))


class ContratoContenidoIdiomas(unittest.TestCase):
    DICS = {"en": {"espacio.titulo": "Kitchen", "vacia": "  "}, "fr": {"espacio.titulo": "Cuisine"}}

    def test_elemento_editable_con_su_traduccion_fija(self):
        html = '<h3 class="t" data-contenido="espacio.cocina.titulo" data-i18n="espacio.titulo">Cocina</h3>'
        self.assertEqual(contenidos_sin_traduccion(html, self.DICS), [])

    def test_elemento_editable_sin_data_i18n(self):
        html = '<h1 data-i18n="espacio.titulo">Cocina</h1><p data-contenido="hero.bajada">Departamento…</p>'
        self.assertEqual(contenidos_sin_traduccion(html, self.DICS), [("hero.bajada", "sin data-i18n")])

    def test_clave_sin_texto_en_un_idioma(self):
        html = '<p data-contenido="hero.bajada" data-i18n="vacia">Hola</p>'
        self.assertEqual(contenidos_sin_traduccion(html, self.DICS), [
            ("hero.bajada", "data-i18n=vacia sin texto en en.json"),
            ("hero.bajada", "data-i18n=vacia sin texto en fr.json"),
        ])

    def test_no_cuentan_comentarios_ni_scripts(self):
        html = ('<!-- <p data-contenido="x.y">a</p> -->'
                '<script>const s = \'<p data-contenido="x.z">b</p>\';</script>')
        self.assertEqual(contenidos_sin_traduccion(html, self.DICS), [])

    def test_paginas_publicas_marcadas(self):
        """En cada página ya marcada con data-i18n, todo data-contenido tiene su traducción fija en en y fr."""
        dics = diccionarios(os.path.join(SRC, "i18n"))
        paginas = paginas_publicas()
        self.assertIn("index.html", paginas)
        self.assertNotIn("admin/index.html", paginas, "el portal queda sólo en español")
        editables = 0
        for ruta in paginas:
            with open(os.path.join(SRC, ruta), encoding="utf-8") as fh:
                html = fh.read()
            if "data-contenido" not in html:
                continue
            editables += 1
            with self.subTest(pagina=ruta):
                if not build.marcas_i18n(html, ruta):
                    self.skipTest(f"{ruta}: sin data-i18n todavía (en /en/ y /fr/ los textos editables quedan en "
                                  "español hasta la PR del marcado)")
                self.assertEqual(contenidos_sin_traduccion(html, dics), [],
                                 f"{ruta}: textos editables sin traducción fija en /en/ o /fr/")
        self.assertGreater(editables, 0, "ninguna página pública tiene data-contenido: ¿cambió el contrato?")


class AdrIdiomas(unittest.TestCase):
    """Hallazgo P2: la decisión de las traducciones (0005 y portal) tiene su ADR, con modelo y revisor humano, y lo que
    dice el ADR existe de verdad en la migración y en el portal."""
    RAIZ = os.path.dirname(WEB)

    def leer(self, *partes):
        with open(os.path.join(self.RAIZ, *partes), encoding="utf-8") as fh:
            return fh.read()

    def test_registra_modelo_revisor_y_decisiones(self):
        adr = self.leer("docs", "adr", "0007-sitio-tres-idiomas.md")
        self.assertIn("**Modelo de IA utilizado:** Claude Opus 5.5 (`claude-opus-5-5`)", adr)
        self.assertIn("**Revisor humano:** Romain Ange", adr)
        for texto in ("valor_en", "valor_fr", "`null` significa", "contenido_precio_sin_traduccion", "`42703`",
                      "`PGRST204`", "Supuesto explícito", "`/admin` queda sólo en español",
                      "La traducción fija no sigue al español editado", "0005_contenido_idiomas.sql", "SQL Editor",
                      "columnasCambiadas"):
            self.assertIn(texto, adr)

    def test_lo_que_cita_el_adr_existe(self):
        migracion = self.leer("web", "supabase", "migrations", "0005_contenido_idiomas.sql")
        for restriccion in ("contenido_valor_en_largo", "contenido_valor_fr_largo", "contenido_precio_sin_traduccion"):
            self.assertIn(f"add constraint {restriccion}", migracion)
        errores = self.leer("web", "src", "admin", "js", "errores.js")
        self.assertIn('err.codigo === "42703" || err.codigo === "PGRST204"', errores)
        logica = self.leer("web", "src", "admin", "js", "logica-contenido.js")
        self.assertIn("export function columnasCambiadas(", logica)
        self.assertTrue(os.path.exists(os.path.join(self.RAIZ, "web", "supabase", "tests", "idiomas_test.sql")))


if __name__ == "__main__":
    unittest.main()
