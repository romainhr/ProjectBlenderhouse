"""Servidor estático local para probar el visor con una política de seguridad parecida a la de las páginas
publicadas en claude.ai (scripts sólo de jsDelivr/cdnjs, fetch sólo del mismo origen, imágenes del mismo origen,
data: y blob:). Es una aproximación: la política real puede diferir.

Uso: python3 tools/servidor_csp.py <carpeta> [puerto]
"""
import functools
import http.server as h
import sys

CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
       "img-src 'self' data: blob:; connect-src 'self'; worker-src 'self' blob:")


class Manejador(h.SimpleHTTPRequestHandler):
    extensions_map = {**h.SimpleHTTPRequestHandler.extensions_map, ".html": "text/html; charset=utf-8",
                      ".json": "application/json; charset=utf-8", ".txt": "text/plain; charset=utf-8"}

    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "exports"
    puerto = int(sys.argv[2]) if len(sys.argv) > 2 else 8766
    h.ThreadingHTTPServer(("127.0.0.1", puerto), functools.partial(Manejador, directory=carpeta)).serve_forever()
