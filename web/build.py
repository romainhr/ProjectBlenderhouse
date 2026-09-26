"""Arma el sitio Project-roomVR en web/dist/ (lo que se sube a Netlify).

Uso:
    python3 web/build.py [--env archivo.env]

- Copia web/src/.
- Convierte los renders de web/renders_png/ (Eevee, 1600 × 1000; tools/render_interior.py) a JPEG y WebP de 1600
  y 800 px.
- Arma web/dist/tour/: la página y el visor v3 vienen de web/src/tour/ y el modelo (tour/modelo/, con su versión
  liviana para teléfono) lo genera web/tour_modelo.py a partir de exports/web/ (fase 6). El visor de la página
  publicada en claude.ai (exports/depto_tour.html) ya no se inyecta: el sitio tiene su propio tour.
- Escribe js/config.js con SUPABASE_URL y SUPABASE_CLAVE_PUBLICA (variables de entorno o --env). Es la clave
  pública (publishable/anon): con RLS no da acceso a la tabla. Nunca poner aquí la clave de servicio.
- Pone en cada HTML su CSP como <meta>, derivada de lo que la página carga de verdad (scripts propios, rutas exactas
  de jsDelivr, Google Fonts sólo si la enlaza, hashes de sus scripts en línea), y escribe _headers (Netlify) con las
  cabeceras de seguridad comunes y la caché de imágenes y texturas.
- Revisa que todo enlace local de los HTML exista en dist/.
Sin dependencias fuera de Pillow (incluida en el sistema).
"""
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sys

from PIL import Image

WEB = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(WEB)
SRC, DIST = os.path.join(WEB, "src"), os.path.join(WEB, "dist")
RENDERS = os.path.join(WEB, "renders_png")
IMAGENES = {"Living": "living", "Living_Sofa": "living-sofa", "Cocina": "cocina", "Dorm1": "dorm1", "Dorm2": "dorm2",
            "Bano1_Vanitorio": "bano", "Balcon": "balcon", "Hall_Recibidor": "recibidor", "Maqueta": "maqueta"}
ANCHOS = (1600, 800)
RE_SUPABASE = re.compile(r"^https://[a-z0-9]{10,40}\.supabase\.co$")
RE_PUBLICABLE = re.compile(r"sb_publishable_[A-Za-z0-9_-]{20,}")
RE_CDN = re.compile(r"https://cdn\.jsdelivr\.net/npm/[A-Za-z0-9._-]+@[0-9][0-9A-Za-z.-]*/")


def leer_env(ruta):
    if not ruta:
        return {}
    datos = {}
    with open(ruta) as fh:
        for linea in fh:
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                datos[k.strip()] = v.strip().strip('"').strip("'")
    return datos


def imagenes():
    os.makedirs(os.path.join(DIST, "img"), exist_ok=True)
    for nombre, slug in IMAGENES.items():
        ruta = os.path.join(RENDERS, f"{nombre}.png")
        if not os.path.exists(ruta):
            raise SystemExit(f"falta el render {ruta} (tools/render_interior.py --size 1600x1000)")
        im = Image.open(ruta).convert("RGB")
        for ancho in ANCHOS:
            alto = round(im.height * ancho / im.width)
            r = im if im.width == ancho else im.resize((ancho, alto), Image.LANCZOS)
            r.save(os.path.join(DIST, "img", f"{slug}-{ancho}.jpg"), quality=82, optimize=True, progressive=True)
            r.save(os.path.join(DIST, "img", f"{slug}-{ancho}.webp"), quality=80, method=6)


def tour():
    """dist/tour/ ya trae la página y el visor (copiados de web/src/tour/); aquí se genera tour/modelo/ con
    web/tour_modelo.py (una copia de desarrollo en src/tour/modelo se descarta y se regenera)."""
    carpeta = os.path.join(DIST, "tour")
    if not os.path.exists(os.path.join(carpeta, "index.html")):
        raise SystemExit("falta web/src/tour/index.html: el sitio necesita su tour")
    import tour_modelo
    modelo = os.path.join(carpeta, "modelo")
    if os.path.exists(modelo):
        shutil.rmtree(modelo)
    return tour_modelo.construir(destino=modelo)


def configuracion(env):
    url = env.get("SUPABASE_URL", "").strip().rstrip("/")
    clave = (env.get("SUPABASE_CLAVE_PUBLICA") or env.get("SUPABASE_ANON_KEY", "")).strip()
    if url and not RE_SUPABASE.match(url):
        raise SystemExit(f"SUPABASE_URL con forma inesperada: {url}")
    if clave and not _es_clave_publica(clave):
        raise SystemExit("SUPABASE_CLAVE_PUBLICA no es una clave publicable (sb_publishable_…) ni «anon»: "
                         "no se publica (podría ser la de servicio o un secreto).")
    if bool(url) != bool(clave):
        raise SystemExit("faltan SUPABASE_URL o SUPABASE_CLAVE_PUBLICA (van las dos o ninguna)")
    with open(os.path.join(DIST, "js", "config.js"), "w") as fh:
        fh.write("// Generado por web/build.py desde variables de entorno. Clave PÚBLICA de Supabase (con RLS no lee la tabla).\n")
        fh.write(f"export const SUPABASE_URL = {json.dumps(url)};\nexport const SUPABASE_CLAVE_PUBLICA = {json.dumps(clave)};\n")
    return url


def _es_clave_publica(clave):
    """Lista blanca: sólo la clave publicable nueva o un JWT antiguo con rol «anon» van al navegador."""
    if RE_PUBLICABLE.fullmatch(clave):
        return True
    try:
        datos = json.loads(_payload_jwt(clave) or "null")
    except ValueError:
        return False
    return isinstance(datos, dict) and datos.get("role") == "anon"


def _payload_jwt(clave):
    partes = clave.split(".")
    if len(partes) != 3:
        return ""
    try:
        return base64.urlsafe_b64decode(partes[1] + "=" * (-len(partes[1]) % 4)).decode("utf-8", "replace")
    except ValueError:
        return ""


def hashes_en_linea(s):
    hs = []
    for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", s, re.S):
        hs.append("'sha256-" + base64.b64encode(hashlib.sha256(m.group(1).encode("utf-8")).digest()).decode() + "'")
    return hs


def politicas(url_supabase):
    """CSP de cada página como <meta>, derivada de lo que carga (con _headers, Netlify junta las reglas que calzan con
    una ruta y una página podría quedar con dos políticas a la vez). Scripts: los propios, las rutas exactas de
    jsDelivr que use (paquete@versión, no todo el CDN) y los hashes de sus scripts en línea."""
    for base_dir, _, archivos in os.walk(DIST):
        for a in archivos:
            if not a.endswith(".html"):
                continue
            ruta = os.path.join(base_dir, a)
            with open(ruta, encoding="utf-8") as fh:
                s = fh.read()
            en_linea = hashes_en_linea(s)
            cdn = sorted(set(RE_CDN.findall(s)))
            google = "fonts.googleapis.com" in s
            partes = ["default-src 'self'",
                      "img-src 'self' data: blob:" + (f" {url_supabase}" if url_supabase else ""),   # fotos de Storage
                      "font-src 'self'" + (" https://fonts.gstatic.com" if google else ""),
                      "style-src 'self' 'unsafe-inline'" + (" https://fonts.googleapis.com" if google else ""),
                      "connect-src 'self'" + (f" {url_supabase}" if url_supabase else ""),
                      "script-src " + " ".join(["'self'", *cdn, *en_linea]),
                      "base-uri 'self'", "form-action 'self'", "object-src 'none'"]
            if cdn:                                        # el visor antiguo (jsDelivr) decodifica texturas en workers blob:
                partes.append("worker-src 'self' blob:")
            meta = f'<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="{"; ".join(partes)}">'
            if s.count('<meta charset="utf-8">') != 1:
                raise SystemExit(f"{os.path.relpath(ruta, DIST)}: falta <meta charset=\"utf-8\"> para colgar la CSP")
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(s.replace('<meta charset="utf-8">', meta))


def cabeceras():
    comunes = ["  X-Content-Type-Options: nosniff", "  X-Frame-Options: DENY",
               "  Referrer-Policy: strict-origin-when-cross-origin",
               "  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()",
               "  Strict-Transport-Security: max-age=31536000"]
    lineas = ["/*", *comunes,
              "/admin/*", "  X-Robots-Tag: noindex, nofollow", "  Cache-Control: no-store",   # portal del propietario
              "/img/*", "  Cache-Control: public, max-age=604800",
              "/fonts/*", "  Cache-Control: public, max-age=2592000, immutable",
              "/tour/tex/*", "  Cache-Control: public, max-age=604800",
              "/tour/tex_movil/*", "  Cache-Control: public, max-age=604800",
              "/tour/modelo/tex/*", "  Cache-Control: public, max-age=604800",
              "/tour/modelo/tex_movil/*", "  Cache-Control: public, max-age=604800",
              "/fonts/*", "  Cache-Control: public, max-age=31536000, immutable"]
    with open(os.path.join(DIST, "_headers"), "w") as fh:
        fh.write("\n".join(lineas) + "\n")


def revisar_enlaces():
    faltan = []
    for base, _, archivos in os.walk(DIST):
        for a in archivos:
            if not a.endswith(".html"):
                continue
            ruta = os.path.join(base, a)
            with open(ruta, encoding="utf-8") as fh:
                s = fh.read()
            for atributo, ref in re.findall(r'\b(src|href|srcset|imagesrcset)="([^"]+)"', s):
                for parte in (ref.split(",") if "srcset" in atributo else [ref]):      # sólo srcset es una lista
                    u = parte.strip().split(" ")[0]
                    if not u or re.match(r"^(https?:|mailto:|tel:|data:|#|javascript:)", u):
                        continue
                    u = u.split("#")[0].split("?")[0]
                    destino = os.path.join(DIST, u.lstrip("/")) if u.startswith("/") else os.path.join(base, u)
                    if u.endswith("/") or os.path.isdir(destino):
                        destino = os.path.join(destino, "index.html")
                    if not os.path.exists(os.path.normpath(destino)):
                        faltan.append(f"{os.path.relpath(ruta, DIST)} -> {u}")
    return faltan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="")
    args = ap.parse_args()
    env = {**leer_env(args.env), **{k: v for k, v in os.environ.items() if k.startswith("SUPABASE_")}}
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    shutil.copytree(SRC, DIST)
    imagenes()
    escritorio, movil = tour()
    url = configuracion(env)
    politicas(url)
    cabeceras()
    faltan = revisar_enlaces()
    for f in faltan:
        print("ENLACE_ROTO", f)
    n, peso = 0, 0
    for base, _, archivos in os.walk(DIST):
        n += len(archivos)
        peso += sum(os.path.getsize(os.path.join(base, a)) for a in archivos)
    print(f"SITIO_OK {n} archivos, {peso / 1e6:.1f} MB; tour {escritorio / 1e6:.1f} MB (escritorio) y "
          f"{movil / 1e6:.1f} MB (teléfono); reservas {'conectadas a ' + url if url else 'SIN conectar (simuladas en localhost)'}")
    if faltan:
        sys.exit(1)


if __name__ == "__main__":
    main()
