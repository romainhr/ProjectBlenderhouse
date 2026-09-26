"""Pruebas de web/build.py (sin red ni Netlify):  python3 -m unittest discover -s web/tests -p 'test_*.py'"""
import base64
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
