"""Publica web/dist/ en Netlify por su API (sin la CLI de Netlify).

Uso:
    NETLIFY_TOKEN=... python3 web/desplegar.py [--sitio loft-2d2b] [--env archivo.env]

- El token es un «personal access token» de Netlify: se lee de la variable NETLIFY_TOKEN o del archivo --env; nunca
  se guarda en el repositorio ni se imprime.
- Si no existe un sitio con ese nombre en la cuenta, lo crea (queda en https://<sitio>.netlify.app).
- Sube web/dist/ como .zip (lo arma web/build.py), espera a que el despliegue quede «ready» y verifica que la portada
  responda 200 en la dirección publicada.
Decisión: docs/adr/0003-sitio-arriendo-netlify-supabase.md.
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile

WEB = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(WEB, "dist")
API = "https://api.netlify.com/api/v1"


def token(env):
    t = os.environ.get("NETLIFY_TOKEN")
    if not t and env:
        with open(env) as fh:
            for linea in fh:
                if linea.startswith("NETLIFY_TOKEN="):
                    t = linea.split("=", 1)[1].strip()
    if not t:
        raise SystemExit("falta NETLIFY_TOKEN")
    return t


def pedir(metodo, ruta, tok, cuerpo=None, tipo="application/json", timeout=120):
    datos = json.dumps(cuerpo).encode() if isinstance(cuerpo, dict) else cuerpo
    req = urllib.request.Request(API + ruta, data=datos, method=metodo,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": tipo})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Netlify {metodo} {ruta}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}")


def zip_dist():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, archivos in os.walk(DIST):
            for a in archivos:
                ruta = os.path.join(base, a)
                z.write(ruta, os.path.relpath(ruta, DIST))
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sitio", default="loft-2d2b")
    ap.add_argument("--env", default="")
    args = ap.parse_args()
    if not os.path.exists(os.path.join(DIST, "index.html")):
        raise SystemExit("falta web/dist: corre antes python3 web/build.py")
    tok = token(args.env)
    sitios = pedir("GET", "/sites?filter=all&per_page=100", tok)
    sitio = next((s for s in sitios if s.get("name") == args.sitio), None)
    if sitio is None:
        sitio = pedir("POST", "/sites", tok, {"name": args.sitio})
        print(f"SITIO_CREADO {sitio['name']} {sitio['ssl_url'] or sitio['url']}")
    datos = zip_dist()
    print(f"SUBIENDO {len(datos) / 1e6:.1f} MB a {sitio['name']}")
    dep = pedir("POST", f"/sites/{sitio['id']}/deploys", tok, datos, tipo="application/zip", timeout=600)
    for _ in range(90):
        dep = pedir("GET", f"/deploys/{dep['id']}", tok)
        if dep["state"] in ("ready", "error"):
            break
        time.sleep(4)
    if dep["state"] != "ready":
        raise SystemExit(f"el despliegue quedó en «{dep['state']}»: {dep.get('error_message')}")
    url = sitio.get("ssl_url") or sitio.get("url")
    with urllib.request.urlopen(url + "/", timeout=60) as r:
        ok = r.status == 200
    print(f"DESPLIEGUE_OK {url} (deploy {dep['id']}, portada {'200' if ok else 'ERROR'})")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
