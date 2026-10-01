"""Servidor local para capturar el visor desde la misma cámara que un render de revisión de Blender (corrección 07c,
ronda 2: calibración del visor contra Blender y controles del acero sobre la captura del visor).

Sirve <carpeta> (por defecto web/src, donde está el tour con su modelo) y acepta POST /__captura/<nombre>.png con el PNG
en el cuerpo, que guarda en <salida>. Sólo escucha en 127.0.0.1; sólo acepta nombres [A-Za-z0-9_-]+.png.

Uso:
    python3 tools/servidor_captura.py [--carpeta web/src] [--salida review/07c_plano] [--puerto 8770]

En el visor, con ?debug: window.__tour.capturar({...}) (web/src/tour/js/main.js) fija la cámara, el momento, los grupos
de luz y las piezas abiertas, dibuja un cuadro y lo envía aquí.
"""
import argparse
import functools
import http.server as h
import os
import re

NOMBRE = re.compile(r"^/__captura/([A-Za-z0-9_-]+\.png)$")
LIMITE = 32 * 1024 * 1024


class Manejador(h.SimpleHTTPRequestHandler):
    salida = "."
    extensions_map = {**h.SimpleHTTPRequestHandler.extensions_map, ".html": "text/html; charset=utf-8",
                      ".json": "application/json; charset=utf-8", ".gltf": "model/gltf+json",
                      ".bin": "application/octet-stream", ".webp": "image/webp"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        m = NOMBRE.match(self.path)
        largo = int(self.headers.get("Content-Length", "0"))
        if not m or not 0 < largo <= LIMITE:
            self.send_error(400, "nombre o tamaño no válido")
            return
        datos = self.rfile.read(largo)
        if not datos.startswith(b"\x89PNG"):
            self.send_error(400, "no es PNG")
            return
        ruta = os.path.join(self.salida, m.group(1))
        with open(ruta, "wb") as fh:
            fh.write(datos)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"guardado {ruta} ({largo} bytes)".encode())


def main():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--carpeta", default=os.path.join(raiz, "web", "src"))
    ap.add_argument("--salida", default=os.path.join(raiz, "review", "07c_plano"))
    ap.add_argument("--puerto", type=int, default=8770)
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    Manejador.salida = a.salida
    h.ThreadingHTTPServer(("127.0.0.1", a.puerto), functools.partial(Manejador, directory=a.carpeta)).serve_forever()


if __name__ == "__main__":
    main()
