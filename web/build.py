"""Arma el sitio LOFT 2D2B en web/dist/ (lo que se sube a Netlify).

Uso:
    python3 web/build.py [--env archivo.env]

- Copia web/src/.
- Convierte los renders de web/renders_png/ (Eevee, 1600 × 1000; tools/render_interior.py) a JPEG y WebP de 1600
  y 800 px.
- Arma web/dist/tour/ con los archivos del modelo (exports/web/, fase 6) y una versión liviana para teléfono
  (texturas de 512 px en tex_movil/ y su índice depto_web_movil.json). La página del tour es web/src/tour/index.html
  si existe (tour propio del sitio); si no, el visor exports/depto_tour.html (el de la página publicada) con los
  colores del sitio inyectados.
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
VISOR = os.path.join(RAIZ, "exports", "depto_tour.html")
MODELO = os.path.join(RAIZ, "exports", "web")
IMAGENES = {"Living": "living", "Living_Sofa": "living-sofa", "Cocina": "cocina", "Dorm1": "dorm1", "Dorm2": "dorm2",
            "Bano1_Vanitorio": "bano", "Balcon": "balcon", "Hall_Recibidor": "recibidor", "Maqueta": "maqueta"}
ANCHOS = (1600, 800)
TEX_MOVIL = 512                     # px: texturas del tour en teléfono (las de escritorio son de 1024)
FUENTES = ("https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600"
           "&family=JetBrains+Mono:wght@400;500;600&display=swap")
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


def visor_del_sitio():
    """El HTML del visor como página completa del sitio, con la barra «Sitio / Reservar» y los colores del sitio."""
    with open(VISOR, encoding="utf-8") as fh:
        s = fh.read()
    cambios = [
        ("<title>Recorrido Depto 2D2B</title>",
         '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
         '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
         '<title>Tour 3D · LOFT 2D2B</title>\n<meta name="theme-color" content="#0f1113">\n'
         '<meta name="description" content="Recorre en 3D el departamento LOFT 2D2B, en computador o teléfono.">\n'
         '<link rel="icon" href="../img/favicon.svg" type="image/svg+xml">'),
        ("</style>\n",
         f'</style>\n<link rel="stylesheet" href="{FUENTES}">\n<link rel="stylesheet" href="../css/tour-loft.css">\n'
         "</head>\n<body>\n"),
        ('<canvas id="vista" tabindex="0" aria-label="Vista 3D del departamento"></canvas>\n',
         '<canvas id="vista" tabindex="0" aria-label="Vista 3D del departamento"></canvas>\n'
         '<nav id="sitio-barra" class="panel" aria-label="Sitio">\n'
         '  <a href="../"><span aria-hidden="true">←</span> Sitio</a>\n'
         '  <a class="primario" href="../reserva.html">Reservar<span class="solo-grande"> estadía</span></a>\n</nav>\n'),
        ("<h1>Depto 2D2B</h1>", "<h1>LOFT 2D2B</h1>"),
    ]
    for viejo, nuevo in cambios:
        if s.count(viejo) != 1:
            raise SystemExit(f"el visor cambió: no se encontró una sola vez {viejo[:60]!r}")
        s = s.replace(viejo, nuevo)
    return s.rstrip() + "\n</body>\n</html>\n"


def tour():
    carpeta = os.path.join(DIST, "tour")
    if os.path.exists(os.path.join(carpeta, "index.html")):
        # tour propio del sitio (web/src/tour/, visor v3): lee tour/modelo/, que arma web/tour_modelo.py a partir de
        # exports/web; una copia de desarrollo en src/tour/modelo se descarta y se regenera
        import tour_modelo
        modelo = os.path.join(carpeta, "modelo")
        if os.path.exists(modelo):
            shutil.rmtree(modelo)
        return tour_modelo.construir(destino=modelo)
    # si no, el visor de la página publicada (exports/depto_tour.html) con los colores del sitio
    shutil.copytree(MODELO, carpeta, dirs_exist_ok=True)
    for extra in ("depto_web_armado.glb",):
        if os.path.exists(os.path.join(carpeta, extra)):
            os.remove(os.path.join(carpeta, extra))
    with open(os.path.join(carpeta, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(visor_del_sitio())
    # versión liviana para teléfono
    with open(os.path.join(carpeta, "depto_web.json")) as fh:
        idx = json.load(fh)
    movil = os.path.join(carpeta, "tex_movil")
    os.makedirs(movil, exist_ok=True)
    total = sum(os.path.getsize(os.path.join(carpeta, idx[k])) for k in ("gltf", "bin"))
    for nombre in sorted(os.listdir(os.path.join(carpeta, "tex"))):
        im = Image.open(os.path.join(carpeta, "tex", nombre))
        if max(im.size) > TEX_MOVIL:
            im = im.resize((TEX_MOVIL, round(im.height * TEX_MOVIL / im.width)), Image.LANCZOS)
        destino = os.path.join(movil, nombre)
        im.convert("RGB").save(destino, quality=80, optimize=True)
        total += os.path.getsize(destino)
    idx_movil = dict(idx, tex_base="tex_movil/", total_bytes=total)
    with open(os.path.join(carpeta, "depto_web_movil.json"), "w") as fh:
        json.dump(idx_movil, fh, ensure_ascii=False, indent=1)
    return idx["total_bytes"], total


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
