"""Pruebas de web/build.py (sin red ni Netlify):  python3 -m unittest discover -s web/tests -p 'test_*.py'"""
import base64
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
PAGINAS = {"index.html", "reserva.html", "privacidad.html", "404.html", "tour/index.html"}


@contextlib.contextmanager
def con_dist(d):
    """build.DIST apuntando a `d` mientras dura el bloque."""
    viejo, build.DIST = build.DIST, d
    try:
        yield d
    finally:
        build.DIST = viejo


def en(ref, ruta="index.html", idioma="en"):
    return build.url_en_idioma(ref, ruta, idioma, PAGINAS)


def jwt(payload):
    parte = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJIUzI1NiJ9.{parte}.firma"


class ClavePublica(unittest.TestCase):
    def test_lista_blanca(self):
        self.assertTrue(build._es_clave_publica("sb_publishable_" + "a" * 30))
        self.assertTrue(build._es_clave_publica(jwt({"role": "anon", "iss": "supabase"})))
        self.assertFalse(build._es_clave_publica("sb_secret_" + "a" * 30))
        self.assertFalse(build._es_clave_publica(jwt({"role": "service_role"})))
        self.assertFalse(build._es_clave_publica("cualquier-otra-cosa"))
        self.assertFalse(build._es_clave_publica("sb_publishable_corta"))

    def test_configuracion_rechaza_secretos(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "js"))
            viejo, build.DIST = build.DIST, d
            try:
                with self.assertRaises(SystemExit):
                    build.configuracion({"SUPABASE_URL": "https://abcdefghijklmnop.supabase.co",
                                         "SUPABASE_CLAVE_PUBLICA": "sb_secret_" + "x" * 30})
                with self.assertRaises(SystemExit):
                    build.configuracion({"SUPABASE_URL": "https://abcdefghijklmnop.supabase.co"})   # falta la clave
                url = build.configuracion({"SUPABASE_URL": "https://abcdefghijklmnop.supabase.co/ ",
                                           "SUPABASE_CLAVE_PUBLICA": " sb_publishable_" + "b" * 30})
                self.assertEqual(url, "https://abcdefghijklmnop.supabase.co")
            finally:
                build.DIST = viejo


class Politicas(unittest.TestCase):
    def _csp(self, html):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "p.html"), "w", encoding="utf-8") as fh:
                fh.write(html)
            viejo, build.DIST = build.DIST, d
            try:
                build.politicas("https://abcdefghijklmnop.supabase.co")
            finally:
                build.DIST = viejo
            with open(os.path.join(d, "p.html"), encoding="utf-8") as fh:
                s = fh.read()
        return s.split('Content-Security-Policy" content="')[1].split('"')[0]

    def test_pagina_propia_sin_externos(self):
        csp = self._csp('<meta charset="utf-8"><script type="module" src="js/a.js"></script>')
        self.assertIn("script-src 'self' ;", csp.replace("script-src 'self';", "script-src 'self' ;"))
        self.assertNotIn("jsdelivr", csp)
        self.assertNotIn("googleapis", csp)
        self.assertIn("connect-src 'self' https://abcdefghijklmnop.supabase.co", csp)
        self.assertIn("img-src 'self' data: blob: https://abcdefghijklmnop.supabase.co", csp)   # fotos de Storage

    def test_cdn_exacto_y_hash_en_linea(self):
        html = ('<meta charset="utf-8"><script type="importmap">{"imports":{"three":'
                '"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"}}</script>'
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=X">')
        csp = self._csp(html)
        self.assertIn("https://cdn.jsdelivr.net/npm/three@0.160.0/", csp)
        self.assertNotIn("https://cdn.jsdelivr.net ", csp)             # nunca todo el CDN
        self.assertIn("'sha256-", csp)
        self.assertIn("https://fonts.gstatic.com", csp)
        self.assertIn("worker-src 'self' blob:", csp)


class Muestras(unittest.TestCase):
    def test_materiales_de_la_portada(self):
        """Los cinco nombres que usa web/src/index.html, en 360 y 720 px, desde texturas propias (no desde renders)."""
        self.assertEqual(sorted(build.MUESTRAS), ["acero", "concreto", "cuero", "ladrillo", "roble"])
        self.assertNotIn("acero_cepillado", {tid for tid, _ in build.MUESTRAS.values()})   # la rehace la fase 07c
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "img"))
            viejo, build.DIST = build.DIST, d
            try:
                build.muestras()
            finally:
                build.DIST = viejo
            from PIL import Image
            for nombre in build.MUESTRAS:
                for lado in build.LADOS_MUESTRA:
                    for ext in ("jpg", "webp"):
                        with Image.open(os.path.join(d, "img", f"material-{nombre}-{lado}.{ext}")) as im:
                            self.assertEqual(im.size, (lado, lado), f"{nombre} {lado} {ext}")
        with open(os.path.join(build.SRC, "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        for nombre in build.MUESTRAS:
            self.assertIn(f"img/material-{nombre}-360.webp", html)


# ---------------------------------------------------------------- idiomas

class LecturaI18n(unittest.TestCase):
    def test_hojas_y_atributos(self):
        s = ('<html><head><title data-i18n="t">Hola &amp; chao</title></head><body>\n'
             '<!-- <p data-i18n="en.comentario">no cuenta</p> -->\n'
             '<p data-i18n="p">\n   Ladrillo,  roble\n </p>\n'
             '<img src="a.jpg" alt="Foto &quot;1&quot;" aria-label=\'Otra\' data-i18n-attr="alt:f.alt; aria-label:f.aria">\n'
             '</body></html>')
        marcas = build.marcas_i18n(s, "x.html")
        self.assertEqual([(m.clave, m.texto, m.atributo) for m in marcas],
                         [("t", "Hola & chao", None), ("p", "Ladrillo,  roble", None),
                          ("f.alt", 'Foto "1"', "alt"), ("f.aria", "Otra", "aria-label")])
        self.assertEqual(s[marcas[1].inicio:marcas[1].fin], "Ladrillo,  roble")     # sin los espacios de los bordes

    def test_no_hoja_falla_con_archivo_y_clave(self):
        with self.assertRaises(SystemExit) as e:
            build.marcas_i18n('<p data-i18n="inicio.bajada">Hola <b>mundo</b></p>', "index.html")
        self.assertIn("index.html", str(e.exception))
        self.assertIn("inicio.bajada", str(e.exception))
        self.assertIn("no es hoja", str(e.exception))
        with self.assertRaises(SystemExit):                                        # sin cierre
            build.marcas_i18n('<p data-i18n="a">Hola', "index.html")

    def test_elemento_sin_texto_falla(self):
        for html in ('<img src="a.jpg" data-i18n="a">', '<meta content="x" data-i18n="a">', '<span data-i18n="a"/>',
                     '<script type="module" data-i18n="a"></script>'):
            with self.assertRaises(SystemExit, msg=html) as e:
                build.marcas_i18n(html, "p.html")
            self.assertIn("data-i18n-attr", str(e.exception))

    def test_data_i18n_attr_mal_formado_o_prohibido(self):
        for attr in ("alt", "alt:", ":clave", ";", "alt:a; alt:b", "alt:con espacio"):
            with self.assertRaises(SystemExit, msg=attr):
                build.marcas_i18n(f'<img alt="x" data-i18n-attr="{attr}">', "p.html")
        for nombre in ("href", "src", "srcset", "style", "onclick", "data-i18n"):     # nunca URL ni manejadores
            with self.assertRaises(SystemExit, msg=nombre) as e:
                build.marcas_i18n(f'<a {nombre}="x" data-i18n-attr="{nombre}:clave">t</a>', "p.html")
            self.assertIn(nombre, str(e.exception))
        with self.assertRaises(SystemExit) as e:                                   # el atributo pedido no está
            build.marcas_i18n('<img src="a.jpg" data-i18n-attr="alt:foto">', "p.html")
        self.assertIn("foto", str(e.exception))

    def test_data_i18n_attr_solo_atributos_de_texto(self):
        """Lista blanca (hallazgo H3): un diccionario nunca pone una redirección, HTML, una URL, un tipo o un rel."""
        prohibidos = [
            ('<meta http-equiv="refresh" content="3600" data-i18n-attr="content:k">', "content"),   # redirige
            ('<meta name="description" http-equiv="refresh" content="x" data-i18n-attr="content:k">', "content"),
            ('<meta name="viewport" content="width=device-width" data-i18n-attr="content:k">', "content"),
            ('<meta property="og:image" content="img/a.jpg" data-i18n-attr="content:k">', "content"),
            ('<p content="x" data-i18n-attr="content:k">t</p>', "content"),
            ('<iframe srcdoc="x" data-i18n-attr="srcdoc:k"></iframe>', "srcdoc"),                   # HTML
            ('<a ping="https://example.invalid/p" href="a.html" data-i18n-attr="ping:k">t</a>', "ping"),
            ('<script type="module" src="a.js" data-i18n-attr="type:k"></script>', "type"),
            ('<link rel="stylesheet" href="a.css" data-i18n-attr="rel:k">', "rel"),
            ('<link rel="alternate stylesheet" title="Oscuro" href="a.css" data-i18n-attr="title:k">', "title"),
            ('<input type="submit" value="Enviar" data-i18n-attr="value:k">', "value"),
            ('<form action="a" data-i18n-attr="action:k"></form>', "action"),
        ]
        for html, nombre in prohibidos:
            with self.assertRaises(SystemExit, msg=html) as e:
                build.traducir_textos(html, "p.html", {"k": "0; url=https://example.invalid/"})
            self.assertIn(f"«{nombre}»", str(e.exception), html)
        permitidos = {
            '<meta name="description" content="Hola" data-i18n-attr="content:k">': 'content="X"',
            '<meta name="Description" content="Hola" data-i18n-attr="content:k">': 'content="X"',
            '<meta property="og:title" content="Hola" data-i18n-attr="content:k">': 'content="X"',
            '<meta property="og:description" content="Hola" data-i18n-attr="content:k">': 'content="X"',
            '<abbr title="Hola" data-i18n-attr="title:k">H</abbr>': 'title="X"',
            '<input placeholder="Hola" aria-description="d" data-i18n-attr="placeholder:k; aria-description:k">':
                'placeholder="X" aria-description="X"',
            '<track label="Hola" data-i18n-attr="label:k">': 'label="X"',
            '<div role="slider" aria-valuetext="3 noches" aria-roledescription="selector" '
            'data-i18n-attr="aria-valuetext:k; aria-roledescription:k"></div>': 'aria-valuetext="X" aria-roledescription="X"',
        }
        for html, esperado in permitidos.items():
            self.assertIn(esperado, build.traducir_textos(html, "p.html", {"k": "X"}), html)
        self.assertTrue(build.atributo_traducible("alt", "img", {}))
        self.assertFalse(build.atributo_traducible("title", "style", {}))

    def test_atributos_pegados_sin_espacio(self):
        """El navegador acepta class="x"data-i18n="k" (error de parseo menor) y conserva el atributo: el build también
        lo lee, en la marca, en el selector y en las rutas (hallazgo H4)."""
        s = ('<link rel="stylesheet"href="css/a.css"><p class="x"data-i18n="k">Hola</p>'
             '<a data-i18n-alternar="en"class="b">EN</a><img alt=\'Foto\'data-i18n-attr="alt:f" src="img/a.jpg">')
        self.assertEqual([(m.clave, m.texto, m.atributo) for m in build.marcas_i18n(s, "index.html")],
                         [("k", "Hola", None), ("f", "Foto", "alt")])
        r = build.reescribir_urls(s, "index.html", "en", PAGINAS)
        self.assertIn('<link rel="stylesheet"href="../css/a.css">', r)
        self.assertIn('src="../img/a.jpg"', r)
        a = build.alternar(s, "index.html", "en")
        self.assertIn('<a data-i18n-alternar="en"class="b" href="/en/" hreflang="en" lang="en" aria-current="true">', a)
        t = build.traducir_textos(s, "index.html", {"k": "Hello", "f": "Photo"})
        self.assertIn('<p class="x"data-i18n="k">Hello</p>', t)
        self.assertIn("alt=\"Photo\"data-i18n-attr", t)

    def test_marca_en_etiqueta_ilegible_detiene_el_build(self):
        """Si una etiqueta con marca no se puede leer, el build falla con archivo y línea en vez de saltarla."""
        for html, marca in (('<p>x</p>\n<p data-i18n="k" =x>Hola</p>', "data-i18n"),
                            ('<p>x</p>\n<img alt="a" =x data-i18n-attr="alt:k">', "data-i18n-attr"),
                            ('<nav>\n<a data-i18n-alternar="en" =x>EN</a></nav>', "data-i18n-alternar")):
            with self.assertRaises(SystemExit, msg=html) as e:
                build.marcas_i18n(html, "index.html")
            self.assertIn("index.html:2", str(e.exception))
            self.assertIn(f"«{marca}»", str(e.exception))
        s = ('<!-- <p data-i18n="a" =x>x</p> --><script>const s = "<a data-i18n-alternar=\'en\' =x>";</script>'
             '<style>/* data-i18n-attr */</style><p data-i18n="d">z</p>')
        self.assertEqual([m.clave for m in build.marcas_i18n(s, "p.html")], ["d"])         # comentario y código: no

    def test_clave_invalida(self):
        for clave in ("", "con espacio", "a/b", "a<b"):
            with self.assertRaises(SystemExit, msg=clave):
                build.marcas_i18n(f'<p data-i18n="{clave}">x</p>', "p.html")

    def test_ignora_comentarios_y_contenido_de_script_y_style(self):
        s = ('<!-- <p data-i18n="a">x</p> --><style>p::after { content: "<p data-i18n=\\"b\\">"; }</style>'
             '<script>const x = \'<p data-i18n="c">y</p>\';</script><p data-i18n="d">z</p>')
        self.assertEqual([m.clave for m in build.marcas_i18n(s, "p.html")], ["d"])


class TextosI18n(unittest.TestCase):
    def test_escapa_como_html(self):
        s = '<p data-i18n="a">x</p><img alt="y" data-i18n-attr="alt:b">'
        r = build.traducir_textos(s, "p.html", {"a": 'Tom & Jerry <b> "c" \'d\'', "b": '<"&\'>'})
        self.assertEqual(r, '<p data-i18n="a">Tom &amp; Jerry &lt;b&gt; &quot;c&quot; &#x27;d&#x27;</p>'
                            '<img alt="&lt;&quot;&amp;&#x27;&gt;" data-i18n-attr="alt:b">')

    def test_conserva_los_espacios_de_los_bordes_y_el_resto(self):
        s = '<p>Antes <span data-i18n="a">\n  uno  dos\n</span> después</p>'
        self.assertEqual(build.traducir_textos(s, "p.html", {"a": " one two "}),
                         '<p>Antes <span data-i18n="a">\n  one two\n</span> después</p>')

    def test_sin_texto_falla(self):
        for dic in ({}, {"a": ""}, {"a": "   "}):
            with self.assertRaises(SystemExit) as e:
                build.traducir_textos('<p data-i18n="a">x</p>', "p.html", dic)
            self.assertIn("p.html", str(e.exception))

    def test_lang_del_html(self):
        self.assertIn('<html lang="en">', build.poner_lang('<!doctype html>\n<html lang="es"><head>', "p.html", "en"))
        self.assertIn('<html class="x" lang="fr">', build.poner_lang('<html class="x"><head>', "p.html", "fr"))
        with self.assertRaises(SystemExit):
            build.poner_lang("<p>sin html</p>", "p.html", "en")


class RutasI18n(unittest.TestCase):
    def test_pagina_traducida_recurso_y_admin(self):
        self.assertEqual(en("reserva.html"), "reserva.html")                      # página: se queda en /en/
        self.assertEqual(en("./"), "./")
        self.assertEqual(en("tour/"), "tour/")
        self.assertEqual(en("tour"), "tour")                                      # carpeta sin barra, también página
        self.assertEqual(en("index.html"), "index.html")
        self.assertEqual(en("css/sitio.css"), "../css/sitio.css")                 # recurso: el compartido de la raíz
        self.assertEqual(en("img/favicon.svg"), "../img/favicon.svg")
        self.assertEqual(en("fonts/fraunces-var.woff2"), "../fonts/fraunces-var.woff2")
        self.assertEqual(en("i18n/en.json"), "../i18n/en.json")
        self.assertEqual(en("admin/"), "../admin/")                               # admin sólo en español
        self.assertEqual(en("admin/index.html"), "../admin/index.html")
        self.assertEqual(en("tour/modelo/depto.gltf"), "../tour/modelo/depto.gltf")
        self.assertEqual(en("otra.html"), "../otra.html")                         # no traducida: la de la raíz
        self.assertEqual(en("reserva.html", "reserva.html", "fr"), "reserva.html")

    def test_desde_el_tour(self):
        t = "tour/index.html"
        self.assertEqual(en("../", t), "../")                                      # /en/
        self.assertEqual(en("../reserva.html", t), "../reserva.html")              # /en/reserva.html
        self.assertEqual(en("../img/favicon.svg", t), "../../img/favicon.svg")
        self.assertEqual(en("../css/tokens.css", t), "../../css/tokens.css")
        self.assertEqual(en("tour.css", t), "../../tour/tour.css")                 # un solo CSS del tour
        self.assertEqual(en("js/main.js", t), "../../tour/js/main.js")             # un solo JS del tour
        self.assertEqual(en("./", t), "./")

    def test_ancla_y_query(self):
        self.assertEqual(en("reserva.html#calendario"), "reserva.html#calendario")
        self.assertEqual(en("./#espacios", "reserva.html"), "./#espacios")
        self.assertEqual(en("css/sitio.css?v=3#x"), "../css/sitio.css?v=3#x")
        self.assertEqual(en("../?a=1#b", "tour/index.html"), "../?a=1#b")
        self.assertEqual(en("js/a.js#x?y"), "../js/a.js#x?y")

    def test_no_toca_absolutas_ni_especiales(self):
        for ref in ("https://example.invalid/a.css", "http://example.invalid/", "//cdn.example.invalid/x.js",
                    "#arriba", "?q=1", "mailto:reservas@example.invalid", "tel:+56900000000",
                    "data:image/png;base64,AAAA", "javascript:void(0)", "", "../fuera.html"):
            self.assertEqual(en(ref), ref)

    def test_desde_la_raiz_del_sitio(self):
        """404.html usa rutas con «/» porque Netlify la sirve en cualquier ruta: siguen así."""
        self.assertEqual(en("/", "404.html"), "/en/")
        self.assertEqual(en("/reserva.html#calendario", "404.html", "fr"), "/fr/reserva.html#calendario")
        self.assertEqual(en("/tour/", "404.html"), "/en/tour/")
        self.assertEqual(en("/css/sitio.css", "404.html"), "/css/sitio.css")
        self.assertEqual(en("/admin/", "404.html"), "/admin/")

    def test_srcset_con_varios_candidatos(self):
        s = ('<source srcset="img/a-800.webp 800w, img/a-1600.webp 1600w">'
             '<img src="img/a.jpg" srcset="img/a.jpg 1x,img/b.jpg 2x" alt="">'
             '<img srcset="data:image/gif;base64,R0lGOD,lh 1x, img/c.jpg 2x" alt="">'
             '<link rel="preload" as="image" href="img/a.webp" imagesrcset="img/a-800.webp 800w, img/a-1600.webp 1600w">')
        r = build.reescribir_urls(s, "index.html", "en", PAGINAS)
        self.assertIn('srcset="../img/a-800.webp 800w, ../img/a-1600.webp 1600w"', r)
        self.assertIn('srcset="../img/a.jpg 1x, ../img/b.jpg 2x"', r)
        self.assertIn('srcset="data:image/gif;base64,R0lGOD,lh 1x, ../img/c.jpg 2x"', r)   # data: con coma, entera
        self.assertIn('imagesrcset="../img/a-800.webp 800w, ../img/a-1600.webp 1600w"', r)
        self.assertEqual(build._candidatos(" a.jpg 1x , b.jpg (x, y) 2x,c.jpg,"),
                         [("a.jpg", "1x"), ("b.jpg", "(x, y) 2x"), ("c.jpg", "")])

    def test_og_image_poster_y_meta_que_no_es_url(self):
        s = ('<meta property="og:image" content="img/living-1600.jpg">'
             '<meta name="description" content="img/no-es-una-ruta.jpg">'
             '<video poster="img/p.jpg" src="video/v.mp4"></video>'
             '<a href="reserva.html?x=1&amp;y=2">r</a>')
        r = build.reescribir_urls(s, "index.html", "en", PAGINAS)
        self.assertIn('<meta property="og:image" content="../img/living-1600.jpg">', r)
        self.assertIn('<meta name="description" content="img/no-es-una-ruta.jpg">', r)
        self.assertIn('poster="../img/p.jpg" src="../video/v.mp4"', r)
        self.assertIn('href="reserva.html?x=1&amp;y=2"', r)                         # sin cambios, entidades intactas
        s2 = '<link rel="stylesheet" href="css/a.css?x=1&amp;y=2">'
        self.assertIn('href="../css/a.css?x=1&amp;y=2"', build.reescribir_urls(s2, "index.html", "en", PAGINAS))

    def test_comentarios_y_selector_no_se_reescriben(self):
        s = '<!-- <link href="css/viejo.css"> --><a data-i18n-alternar="es" href="index.html">ES</a>'
        self.assertEqual(build.reescribir_urls(s, "index.html", "en", PAGINAS), s)


class SelectorYHreflang(unittest.TestCase):
    NAV = ('<nav><a data-i18n-alternar="es" href="#" aria-current="true">ES</a> '
           '<a data-i18n-alternar="en">EN</a> <a class="x" data-i18n-alternar="fr">FR</a></nav>')

    def _enlaces(self, s):
        return {re.search(r'data-i18n-alternar="(\w+)"', a).group(1): a for a in re.findall(r"<a\b[^>]*>", s)}

    def test_selector_en_la_raiz_en_otro_idioma_y_en_el_tour(self):
        casos = [("reserva.html", "es", {"es": "/reserva.html", "en": "/en/reserva.html", "fr": "/fr/reserva.html"}),
                 ("reserva.html", "en", {"es": "/reserva.html", "en": "/en/reserva.html", "fr": "/fr/reserva.html"}),
                 ("index.html", "fr", {"es": "/", "en": "/en/", "fr": "/fr/"}),
                 ("tour/index.html", "en", {"es": "/tour/", "en": "/en/tour/", "fr": "/fr/tour/"})]
        for ruta, idioma, esperado in casos:
            enlaces = self._enlaces(build.alternar(self.NAV, ruta, idioma))
            for destino, href in esperado.items():
                a = enlaces[destino]
                self.assertIn(f'href="{href}"', a, (ruta, idioma))
                self.assertIn(f'hreflang="{destino}"', a)
                self.assertIn(f'lang="{destino}"', a)
                self.assertEqual('aria-current="true"' in a, destino == idioma, (ruta, idioma, destino))
            self.assertIn('class="x"', enlaces["fr"])

    def test_selector_invalido(self):
        for s in ('<a data-i18n-alternar="de">DE</a>', '<button data-i18n-alternar="en">EN</button>'):
            with self.assertRaises(SystemExit, msg=s):
                build.alternar(s, "index.html", "es")

    def test_selector_de_una_pagina_que_queda_en_espanol(self):
        """Una página que no se publica en en/ ni fr/ lleva al inicio de cada idioma; sin inicio traducido, falla."""
        enlaces = self._enlaces(build.alternar(self.NAV, "tour/index.html", "es", {"index.html", "reserva.html"}))
        self.assertIn('href="/tour/"', enlaces["es"])
        self.assertIn('aria-current="true"', enlaces["es"])
        self.assertIn('href="/en/"', enlaces["en"])
        self.assertIn('href="/fr/"', enlaces["fr"])
        self.assertNotIn("aria-current", enlaces["en"])
        traducida = self._enlaces(build.alternar(self.NAV, "reserva.html", "es", {"index.html", "reserva.html"}))
        self.assertIn('href="/en/reserva.html"', traducida["en"])                  # la traducida, a sí misma
        with self.assertRaises(SystemExit) as e:
            build.alternar(self.NAV, "reserva.html", "es", {"tour/index.html"})
        self.assertIn("reserva.html", str(e.exception))
        with self.assertRaises(SystemExit):
            build.alternar(self.NAV, "reserva.html", "es", set())
        self.assertEqual(build.alternar("<p>sin selector</p>", "reserva.html", "es", set()), "<p>sin selector</p>")

    def test_hreflang_con_url_absolutas(self):
        s = "<html><head>\n<title>x</title>\n</head><body></body></html>"
        r = build.poner_alternos(s, "tour/index.html", "https://ejemplo.netlify.app")
        self.assertEqual(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', r),
                         [("es", "https://ejemplo.netlify.app/tour/"), ("en", "https://ejemplo.netlify.app/en/tour/"),
                          ("fr", "https://ejemplo.netlify.app/fr/tour/"), ("x-default", "https://ejemplo.netlify.app/tour/")])
        self.assertLess(r.index("hreflang"), r.index("</head>"))
        self.assertIn('hreflang="en" href="https://loft-2d2b.netlify.app/en/"', build.enlaces_alternos("index.html", build.SITIO_URL))
        self.assertIn('hreflang="x-default" href="https://loft-2d2b.netlify.app/reserva.html"',
                      build.enlaces_alternos("reserva.html", build.SITIO_URL))
        with self.assertRaises(SystemExit):                                        # ya los trae: no se duplican
            build.poner_alternos('<head><link rel="alternate" hreflang="en" href="/en/"></head>', "index.html", build.SITIO_URL)
        with self.assertRaises(SystemExit):
            build.poner_alternos("<p>sin head</p>", "index.html", build.SITIO_URL)

    def test_sitio_publico(self):
        self.assertEqual(build.sitio_publico({}), "https://loft-2d2b.netlify.app")
        self.assertEqual(build.sitio_publico({"SITIO_URL": " https://otro.example.org/ "}), "https://otro.example.org")
        for malo in ("http://loft-2d2b.netlify.app", "https://loft-2d2b.netlify.app/en", 'https://a.b"><script>',
                     "loft-2d2b.netlify.app", "https://localhost"):
            with self.assertRaises(SystemExit, msg=malo):
                build.sitio_publico({"SITIO_URL": malo})

    def test_pagina_en_espanol_solo_suma_selector_y_hreflang(self):
        s = ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n<link rel="stylesheet" href="css/a.css">\n'
             '</head>\n<body>' + self.NAV + '<p data-i18n="a">Hola</p></body>\n</html>\n')
        r = build.traducir_pagina(s, "index.html", "es", {}, PAGINAS)
        self.assertIn('<html lang="es">', r)
        self.assertIn('href="css/a.css"', r)
        self.assertIn('<p data-i18n="a">Hola</p>', r)
        self.assertEqual(r.count('rel="alternate"'), 4)
        self.assertIn('href="/en/"', r)


class Redirecciones(unittest.TestCase):
    def test_reglas_por_pagina_y_404_al_final(self):
        texto = build.redirecciones(PAGINAS)
        reglas = [l.split() for l in texto.splitlines() if l and not l.startswith("#")]
        self.assertEqual(reglas[:2], [["/", "/en/", "302!", "Language=en"], ["/", "/fr/", "302!", "Language=fr"]])
        for origen, destino in [("/reserva.html", "/{}/reserva.html"), ("/privacidad.html", "/{}/privacidad.html"),
                                ("/tour/", "/{}/tour/")]:
            for idioma in ("en", "fr"):
                self.assertIn([origen, destino.format(idioma), "302!", f"Language={idioma}"], reglas)
        # Netlify sirve /404.html en cualquier ruta sin archivo sin evaluar una regla «/404.html» (hallazgo H5): el
        # 404 en el idioma del navegador sale de reglas 404 sin «!» (sólo si no hay archivo), después de /en/* y /fr/*.
        self.assertFalse([r for r in reglas if r[0] == "/404.html"])
        self.assertEqual(reglas[-4:], [["/en/*", "/en/404.html", "404"], ["/fr/*", "/fr/404.html", "404"],
                                       ["/*", "/en/404.html", "404", "Language=en"],
                                       ["/*", "/fr/404.html", "404", "Language=fr"]])
        self.assertEqual(len(reglas), 2 * (len(PAGINAS) - 1) + 4)
        self.assertTrue(all(r[2] == "302!" for r in reglas[:-4]))
        self.assertIn("Supuesto sin verificar", texto)
        for r in reglas:                                                          # nada de admin, i18n ni recursos
            self.assertFalse(re.match(r"^/(admin|i18n|css|js|img|fonts|vendor|tour/js|tour/modelo)", r[0]), r)
        self.assertIn("nf_lang", texto)
        self.assertTrue(all(l.startswith("#") for l in texto.splitlines()[:3]))
        self.assertTrue(texto.endswith("\n"))

    def test_sin_404_no_hay_regla_de_404(self):
        texto = build.redirecciones({"index.html"})
        self.assertNotIn("404", texto.split("\n# ")[-1].split("\n", 1)[-1])


class Diccionarios(unittest.TestCase):
    def _escribir(self, d, **dics):
        for idioma, contenido in dics.items():
            with open(os.path.join(d, f"{idioma}.json"), "w", encoding="utf-8") as fh:
                fh.write(contenido if isinstance(contenido, str) else json.dumps(contenido))

    def test_sin_en_o_fr_no_hay_idiomas(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(build.cargar_diccionarios(d))
            self._escribir(d, es={"a": "x"}, en={"a": "y"})
            self.assertIsNone(build.cargar_diccionarios(d))                       # falta fr.json
            os.remove(os.path.join(d, "en.json"))
            self._escribir(d, fr={"a": "z"})
            self.assertIsNone(build.cargar_diccionarios(d))                       # falta en.json
            self._escribir(d, en={"a": "y"})
            self.assertEqual(build.cargar_diccionarios(d), {"es": {"a": "x"}, "en": {"a": "y"}, "fr": {"a": "z"}})
            os.remove(os.path.join(d, "es.json"))
            with self.assertRaises(SystemExit):                                   # en y fr sin es: error
                build.cargar_diccionarios(d)

    def test_diccionario_plano_valido(self):
        with tempfile.TemporaryDirectory() as d:
            for malo in ('{"a": "x",}', '["a"]', '{"a": {"b": "c"}}', '{"a": 1}', '{"a": "x", "a": "y"}',
                         '{"con espacio": "x"}'):
                self._escribir(d, es=malo)
                with self.assertRaises(SystemExit, msg=malo):
                    build.leer_diccionario(os.path.join(d, "es.json"))

    def _dics(self, **cambios):
        dics = {"es": {"a": "Hola", "b": "Foto", "js.x": "uno"}, "en": {"a": "Hi", "b": "Photo", "js.x": "one"},
                "fr": {"a": "Salut", "b": "Photo", "js.x": "un"}}
        for idioma, dic in cambios.items():
            dics[idioma] = dic
        return dics

    FUENTES = {"index.html": '<p data-i18n="a">\n  Hola\n</p><img alt="Foto" data-i18n-attr="alt:b">',
               "404.html": "<p>Sin marcas</p>"}

    def test_validacion_correcta_con_avisos(self):
        dics = self._dics()
        dics["en"]["sin.uso"] = "x"
        errores, avisos = build.validar_i18n(self.FUENTES, dics)
        self.assertEqual(errores, [])
        self.assertIn("clave sin uso: sin.uso (en)", avisos)                      # sólo aviso
        self.assertTrue(any(a.startswith("404.html: sin data-i18n") for a in avisos))

    def test_clave_sin_texto_en_algun_idioma(self):
        errores, _ = build.validar_i18n(self.FUENTES, self._dics(fr={"a": "Salut", "b": " ", "js.x": "un"}))
        self.assertEqual(errores, ["index.html: b (alt): sin texto en fr.json"])
        errores, _ = build.validar_i18n(self.FUENTES, self._dics(en={"b": "Photo", "js.x": "one"}))
        self.assertEqual(errores, ["index.html: a: sin texto en en.json"])

    def test_es_json_igual_al_html(self):
        errores, _ = build.validar_i18n(self.FUENTES, self._dics(es={"a": " Hola ", "b": "Foto", "js.x": "uno"}))
        self.assertEqual(errores, [])                                              # espacios normalizados
        errores, _ = build.validar_i18n(self.FUENTES, self._dics(es={"a": "Hola!", "b": "Foto", "js.x": "uno"}))
        self.assertEqual(len(errores), 1)
        self.assertIn("index.html: a", errores[0])
        self.assertIn("«Hola!»", errores[0])

    def test_claves_js_iguales_en_los_tres(self):
        errores, _ = build.validar_i18n(self.FUENTES, self._dics(fr={"a": "Salut", "b": "Photo", "js.y": "deux"}))
        self.assertEqual(errores, ["fr.json: falta js.x (está en es.json)", "fr.json: sobra js.y (no está en es.json)"])
        _, avisos = build.validar_i18n(self.FUENTES, self._dics(en={"a": "Hi", "b": "Photo", "js.x": ""}))
        self.assertIn("en.json: js.x está vacío", avisos)


def _copiar_datos(d):
    shutil.copytree(DATOS_I18N, d, dirs_exist_ok=True)
    os.remove(os.path.join(d, "LEEME.txt"))


def _leer(*partes):
    with open(os.path.join(*partes), encoding="utf-8") as fh:
        return fh.read()


def _archivos(d):
    return {os.path.relpath(os.path.join(b, a), d): _leer(b, a) for b, _, archivos in os.walk(d) for a in archivos}


class SitioEnTresIdiomas(unittest.TestCase):
    """build.idiomas() de punta a punta sobre web/tests/datos/i18n (y sobre una copia de web/src)."""

    def _armar(self, d, sitio=build.SITIO_URL):
        with con_dist(d), contextlib.redirect_stdout(io.StringIO()) as salida:
            paginas = build.idiomas(sitio)
            build.politicas("")
            faltan = build.revisar_enlaces(sitio)
        return paginas, faltan, salida.getvalue()

    def test_sin_en_o_fr_el_sitio_queda_como_hoy(self):
        for falta in ("en.json", "fr.json"):
            with tempfile.TemporaryDirectory() as d:
                _copiar_datos(d)
                os.remove(os.path.join(d, "i18n", falta))
                antes = _archivos(d)
                with con_dist(d), contextlib.redirect_stdout(io.StringIO()) as salida:
                    self.assertEqual(build.idiomas(), set())
                self.assertEqual(_archivos(d), antes, falta)                    # ni un byte distinto
                self.assertFalse(os.path.exists(os.path.join(d, "_redirects")))
                self.assertIn("IDIOMAS sólo español", salida.getvalue())

    def test_tres_idiomas(self):
        with tempfile.TemporaryDirectory() as d:
            _copiar_datos(d)
            admin = _leer(d, "admin", "index.html")
            paginas, faltan, salida = self._armar(d)
            self.assertEqual(paginas, {"index.html", "reserva.html", "404.html", "tour/index.html"})
            self.assertEqual(faltan, [])                            # enlaces de en/ y fr/ (y sus hreflang) completos
            self.assertNotIn("AVISO_I18N", salida)
            for idioma in ("en", "fr"):
                for ruta in paginas:
                    s = _leer(d, idioma, ruta)
                    self.assertIn(f'<html lang="{idioma}">', s, ruta)
                    self.assertEqual(s.count("Content-Security-Policy"), 1, ruta)   # la CSP cubre lo generado
                    self.assertEqual(s.count('rel="alternate"'), 4, ruta)
            generados = sorted(os.path.relpath(os.path.join(b, a), d) for b, _, archivos in os.walk(d)
                               for a in archivos if os.path.relpath(b, d).split(os.sep)[0] in ("en", "fr"))
            self.assertEqual(generados, sorted(f"{i}/{r}" for i in ("en", "fr") for r in paginas))   # sólo HTML
            self.assertEqual(_leer(d, "admin", "index.html").replace(re.search(
                r'<meta http-equiv="Content-Security-Policy"[^>]*>\n', _leer(d, "admin", "index.html")).group(0), ""),
                admin)                                                             # admin: sólo la CSP
            self.assertFalse(os.path.exists(os.path.join(d, "en", "admin")))

            inicio = _leer(d, "en", "index.html")
            self.assertIn('<title data-i18n="inicio.titulo">Home · Test site</title>', inicio)
            self.assertIn("Welcome to &quot;Brick &amp; Oak&quot; &lt;home&gt;", inicio)
            self.assertIn('content="Test page for the build&#x27;s languages."', inicio)
            self.assertIn('alt="Living room with a brick wall"', inicio)
            self.assertIn('<p data-i18n="inicio.bajada">\n  Brick, oak and warm light.\n</p>', inicio)
            self.assertIn('href="reserva.html#calendario"', inicio)
            self.assertIn('href="../css/sitio.css"', inicio)
            self.assertIn('imagesrcset="../img/portada.svg 800w, ../img/portada.svg?v=2 1600w"', inicio)
            self.assertIn('<meta property="og:image" content="../img/portada.svg">', inicio)
            self.assertIn('href="../admin/"', inicio)
            self.assertIn('href="https://example.invalid/fuera"', inicio)
            self.assertIn('<a data-i18n-alternar="en" href="/en/" hreflang="en" lang="en" aria-current="true">', inicio)
            self.assertIn("clave.inexistente", inicio)                            # el comentario queda igual

            tour = _leer(d, "fr", "tour", "index.html")
            for ref in ('href="../../img/favicon.svg"', 'href="../../tour/tour.css"', 'src="../../tour/js/main.js"',
                        'href="../"', 'href="../reserva.html"', 'aria-label="Vue 3D de l&#x27;appartement"',
                        'href="https://loft-2d2b.netlify.app/fr/tour/"'):
                self.assertIn(ref, tour)
            error = _leer(d, "en", "404.html")
            self.assertIn('<a href="/en/" data-i18n="error.volver">Back to home</a>', error)
            self.assertIn('href="/css/sitio.css"', error)

            raiz = _leer(d, "reserva.html")                                        # español: selector y hreflang
            self.assertIn('<html lang="es">', raiz)
            self.assertIn('<a data-i18n-alternar="es" href="/reserva.html" hreflang="es" lang="es" aria-current="true">', raiz)
            self.assertIn('<a data-i18n-alternar="fr" href="/fr/reserva.html" hreflang="fr" lang="fr">', raiz)
            self.assertIn('<link rel="alternate" hreflang="x-default" href="https://loft-2d2b.netlify.app/reserva.html">', raiz)
            self.assertIn("/tour/         /en/tour/         302!  Language=en", _leer(d, "_redirects"))

            os.remove(os.path.join(d, "fr", "reserva.html"))                      # revisar_enlaces ve lo generado
            with con_dist(d):
                faltan = build.revisar_enlaces(build.SITIO_URL)
            self.assertIn("reserva.html -> /fr/reserva.html", faltan)
            self.assertIn(os.path.join("en", "reserva.html") + " -> /fr/reserva.html", faltan)

    def test_error_de_validacion_detiene_el_build(self):
        with tempfile.TemporaryDirectory() as d:
            _copiar_datos(d)
            ruta = os.path.join(d, "i18n", "fr.json")
            dic = json.loads(_leer(ruta))
            del dic["tour.vista"]
            with open(ruta, "w", encoding="utf-8") as fh:
                json.dump(dic, fh)
            with con_dist(d), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as e:
                build.idiomas()
            self.assertIn("tour/index.html: tour.vista (aria-label): sin texto en fr.json", str(e.exception))
            self.assertFalse(os.path.exists(os.path.join(d, "en")))
            self.assertFalse(os.path.exists(os.path.join(d, "_redirects")))

    def test_no_pisa_lo_que_genera(self):
        with tempfile.TemporaryDirectory() as d:
            _copiar_datos(d)
            os.makedirs(os.path.join(d, "en"))
            with con_dist(d), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                build.idiomas()

    def _quitar_marcas(self, d, ruta, selector=False):
        """Quita data-i18n y data-i18n-attr (y el selector si `selector`) de la página `ruta` de la copia `d`."""
        patron = r'\s+data-i18n(?:-attr|-alternar)?="[^"]*"' if selector else r'\s+data-i18n(?:-attr)?="[^"]*"'
        s = re.sub(patron, "", _leer(d, ruta))
        self.assertEqual(build.marcas_i18n(s, ruta), [])
        with open(os.path.join(d, ruta), "w", encoding="utf-8") as fh:
            fh.write(s)

    def test_solo_se_publican_las_paginas_con_marcas(self):
        """Hallazgo H2: una página sin data-i18n no sale en en/ ni fr/ (ni lang, ni hreflang, ni 302!); las marcadas
        sí, y los enlaces de las traducidas hacia ella van a la de la raíz."""
        with tempfile.TemporaryDirectory() as d:
            _copiar_datos(d)
            self._quitar_marcas(d, "reserva.html")                                # conserva su selector
            paginas, faltan, salida = self._armar(d)
            self.assertEqual(paginas, {"index.html", "404.html", "tour/index.html"})
            self.assertEqual(faltan, [])
            self.assertIn("AVISO_I18N reserva.html: sin data-i18n: no se publica en en/ ni fr/", salida)
            for idioma in ("en", "fr"):
                self.assertFalse(os.path.exists(os.path.join(d, idioma, "reserva.html")))
                self.assertTrue(os.path.exists(os.path.join(d, idioma, "index.html")))
            redirects = _leer(d, "_redirects")
            self.assertNotIn("/reserva.html", redirects)
            self.assertIn("/en/", redirects)
            self.assertIn('href="../reserva.html#calendario"', _leer(d, "en", "index.html"))   # la de la raíz
            self.assertIn('href="../../reserva.html"', _leer(d, "fr", "tour", "index.html"))
            raiz = _leer(d, "reserva.html")
            self.assertNotIn('rel="alternate"', raiz)                              # sin hreflang
            self.assertIn('<html lang="es">', raiz)
            self.assertIn('<a data-i18n-alternar="es" href="/reserva.html" hreflang="es" lang="es" aria-current="true">', raiz)
            self.assertIn('<a data-i18n-alternar="en" href="/en/" hreflang="en" lang="en">', raiz)   # al inicio en inglés
            self.assertIn("AVISO_I18N reserva.html: queda sólo en español", salida)

    def test_sin_marcas_no_se_publica_ningun_idioma(self):
        """Hallazgo H2: con diccionarios pero sin ninguna marca, no se escriben en/, fr/, _redirects ni hreflang."""
        with tempfile.TemporaryDirectory() as d:
            _copiar_datos(d)
            for ruta in ("index.html", "reserva.html", "404.html", "tour/index.html"):
                self._quitar_marcas(d, ruta, selector=True)
            antes = _archivos(d)
            with con_dist(d), contextlib.redirect_stdout(io.StringIO()) as salida:
                self.assertEqual(build.idiomas(), set())
            self.assertEqual(_archivos(d), antes)                                  # ni un byte distinto
            self.assertIn("IDIOMAS sólo español: ninguna página pública tiene data-i18n", salida.getvalue())

    def test_selector_sin_ninguna_pagina_marcada_falla(self):
        with tempfile.TemporaryDirectory() as d:
            _copiar_datos(d)
            for ruta in ("index.html", "reserva.html", "404.html", "tour/index.html"):
                self._quitar_marcas(d, ruta)                                       # quedan los selectores
            with con_dist(d), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as e:
                build.idiomas()
            self.assertIn("selector de idioma", str(e.exception))
            self.assertFalse(os.path.exists(os.path.join(d, "en")))
            self.assertFalse(os.path.exists(os.path.join(d, "_redirects")))

    def test_publicables(self):
        fuentes = {"index.html": '<p data-i18n="a">x</p>', "reserva.html": "<p>x</p>",
                   "privacidad.html": '<img alt="x" data-i18n-attr="alt:b">', "tour/index.html": '<p data-i18n="t">x</p>'}
        self.assertEqual(build.publicables(fuentes)[0], {"index.html", "privacidad.html", "tour/index.html"})
        paginas, avisos = build.publicables(fuentes, tour_listo=False)
        self.assertEqual(paginas, {"index.html", "privacidad.html"})
        self.assertTrue(avisos and avisos[0].startswith("tour/: no se publica en en/ ni fr/"))

    def test_tour_que_resuelve_el_modelo_desde_la_pagina_queda_en_espanol(self):
        """Hallazgo H1: si tour/js/carga.js arma RUTA_MODELO relativo a la página, desde /en/tour/ pediría
        /en/tour/modelo/, que no existe. Ese tour no se publica en en/ ni fr/; con import.meta.url, sí."""
        casos = {'export const RUTA_MODELO = "modelo/";': False,
                 'export const RUTA_MODELO = new URL("../modelo/", import.meta.url).href;': True}
        for carga, publicado in casos.items():
            with self.subTest(carga=carga), tempfile.TemporaryDirectory() as d:
                _copiar_datos(d)
                with open(os.path.join(d, "tour", "js", "carga.js"), "w", encoding="utf-8") as fh:
                    fh.write(carga + "\n")
                os.makedirs(os.path.join(d, "tour", "modelo"))
                paginas, faltan, salida = self._armar(d)
                self.assertEqual(faltan, [])
                self.assertEqual("tour/index.html" in paginas, publicado)
                self.assertEqual(os.path.exists(os.path.join(d, "en", "tour")), publicado)
                self.assertEqual("/tour/" in _leer(d, "_redirects"), publicado)
                self.assertEqual('rel="alternate"' in _leer(d, "tour", "index.html"), publicado)
                if not publicado:
                    self.assertIn("AVISO_I18N tour/: no se publica en en/ ni fr/", salida)
                    self.assertIn('<a href="../tour/">', _leer(d, "en", "index.html"))   # el tour de la raíz
                    self.assertIn('<a data-i18n-alternar="en" href="/en/"', _leer(d, "tour", "index.html"))

    def _copia_de_web_src(self, d):
        """Copia de web/src en `d`, con tour/modelo/ vacío (el build lo genera) y sin la copia de desarrollo."""
        shutil.copytree(build.SRC, d, dirs_exist_ok=True, ignore=shutil.ignore_patterns("modelo"))
        os.makedirs(os.path.join(d, "tour", "modelo"), exist_ok=True)
        return build.paginas_traducibles(d)

    def _completar_recursos(self, d):
        """Los recursos que genera el build (img/*, tour/modelo…) se reemplazan por archivos vacíos en la raíz, así
        cualquier enlace roto que quede sale de la traducción."""
        with con_dist(d):
            for f in build.revisar_enlaces():
                pagina, ref = f.split(" -> ")
                base = d if ref.startswith("/") else os.path.dirname(os.path.join(d, pagina))
                destino = os.path.normpath(os.path.join(base, ref.lstrip("/") if ref.startswith("/") else ref))
                if ref.endswith("/"):
                    destino = os.path.join(destino, "index.html")
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                open(destino, "w").close()

    def test_paginas_de_web_src(self):
        """Con el web/src real, idiomas() publica exactamente las páginas con marcas (el tour, sólo si su carga.js usa
        import.meta.url). Hoy ninguna tiene data-i18n: no se escribe en/, fr/ ni _redirects (hallazgo H2)."""
        with open(os.path.join(build.SRC, "tour", "js", "carga.js"), encoding="utf-8") as fh:
            carga = fh.read()
        tour_listo = bool(re.search(r"RUTA_MODELO\s*=\s*new URL\([^)]*import\.meta\.url", carga))
        with tempfile.TemporaryDirectory() as d:
            candidatas = self._copia_de_web_src(d)
            self.assertTrue({"index.html", "reserva.html", "privacidad.html", "404.html", "tour/index.html"} <= candidatas)
            self.assertFalse(any(p.startswith(("admin/", "vendor/")) for p in candidatas))
            marcadas = {p for p in candidatas if build.marcas_i18n(_leer(d, p), p)}
            esperadas = {p for p in marcadas if tour_listo or not p.startswith("tour/")}
            self._completar_recursos(d)
            paginas, faltan, salida = self._armar(d)
            self.assertEqual(paginas, esperadas)
            self.assertEqual(faltan, [])
            if not esperadas:
                self.assertIn("IDIOMAS sólo español", salida)
                for ocupado in ("en", "fr", "_redirects"):
                    self.assertFalse(os.path.exists(os.path.join(d, ocupado)), ocupado)
            for idioma in ("en", "fr"):
                for p in paginas:
                    self.assertIn(f'<html lang="{idioma}">', _leer(d, idioma, p), p)

    def test_tour_real_solo_en_otro_idioma_con_import_meta_url(self):
        """Hallazgo H1 sobre el web/src real: aunque el tour tenga marcas, tour/index.html sólo queda entre las
        páginas traducidas si web/src/tour/js/carga.js arma RUTA_MODELO con import.meta.url."""
        with open(os.path.join(build.SRC, "tour", "js", "carga.js"), encoding="utf-8") as fh:
            carga = fh.read()
        tour_listo = bool(re.search(r"RUTA_MODELO\s*=\s*new URL\([^)]*import\.meta\.url", carga))
        with tempfile.TemporaryDirectory() as d:
            self._copia_de_web_src(d)
            ruta = os.path.join(d, "tour", "index.html")
            s = _leer(ruta)
            titulo = re.search(r"<title>([^<]*)</title>", s)
            if titulo:                                          # una marca propia, por si el tour todavía no tiene
                s = s.replace(titulo.group(0), f'<title data-i18n="tour.prueba_h1">{titulo.group(1)}</title>', 1)
                with open(ruta, "w", encoding="utf-8") as fh:
                    fh.write(s)
                for idioma in build.IDIOMAS:
                    dic_ruta = os.path.join(d, "i18n", f"{idioma}.json")
                    dic = json.loads(_leer(dic_ruta))
                    dic["tour.prueba_h1"] = build.desescapar(titulo.group(1)) if idioma == "es" else f"[{idioma}] tour"
                    with open(dic_ruta, "w", encoding="utf-8") as fh:
                        json.dump(dic, fh, ensure_ascii=False)
            self.assertTrue(build.marcas_i18n(_leer(ruta), "tour/index.html"))
            self._completar_recursos(d)
            paginas, faltan, _ = self._armar(d)
            self.assertEqual("tour/index.html" in paginas, tour_listo,
                             "tour/index.html se publica en en/ y fr/ sólo si carga.js usa import.meta.url")
            self.assertEqual(os.path.exists(os.path.join(d, "en", "tour", "index.html")), tour_listo)
            if os.path.exists(os.path.join(d, "_redirects")):
                self.assertEqual("/tour/" in _leer(d, "_redirects"), tour_listo)
            self.assertEqual(faltan, [])

    def test_rutas_de_las_paginas_reales_en_otro_idioma(self):
        """Todas las páginas reales, forzadas a en/ y fr/ con publicar_idiomas() aunque todavía no tengan marcas,
        quedan sin enlaces rotos (rutas, selector y hreflang)."""
        with tempfile.TemporaryDirectory() as d:
            candidatas = self._copia_de_web_src(d)
            fuentes = {p: _leer(d, p) for p in candidatas}
            marcas = [m for p in candidatas for m in build.marcas_i18n(fuentes[p], p)]
            dics = {i: {m.clave: m.texto if i == "es" else f"[{i}] {m.texto}" for m in marcas} for i in build.IDIOMAS}
            self._completar_recursos(d)
            with con_dist(d), contextlib.redirect_stdout(io.StringIO()):
                build.publicar_idiomas(fuentes, dics, candidatas)
                build.politicas("")
                faltan = build.revisar_enlaces(build.SITIO_URL)
            self.assertEqual(faltan, [])
            self.assertIn('href="/en/"', _leer(d, "en", "404.html"))              # «Volver al inicio» en inglés
            self.assertIn('src="../../tour/js/main.js"', _leer(d, "en", "tour", "index.html"))
            for idioma in ("en", "fr"):
                for p in candidatas:
                    self.assertIn(f'<html lang="{idioma}">', _leer(d, idioma, p), p)


if __name__ == "__main__":
    unittest.main()
