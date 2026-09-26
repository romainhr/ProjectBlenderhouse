"""Arma el sitio Project-roomVR en web/dist/ (lo que se sube a Netlify).

Uso:
    python3 web/build.py [--env archivo.env]

- Copia web/src/.
- Convierte los renders de web/renders_png/ (Eevee, 1600 × 1000; tools/render_interior.py) a JPEG y WebP de 1600
  y 800 px, y genera las muestras de materiales de la portada (img/material-*-{360,720}) desde las texturas propias.
- Arma web/dist/tour/: la página y el visor v3 vienen de web/src/tour/ y el modelo (tour/modelo/, con su versión
  liviana para teléfono) lo genera web/tour_modelo.py a partir de exports/web/ (fase 6). El visor de la página
  publicada en claude.ai (exports/depto_tour.html) ya no se inyecta: el sitio tiene su propio tour.
- Escribe js/config.js con SUPABASE_URL y SUPABASE_CLAVE_PUBLICA (variables de entorno o --env). Es la clave
  pública (publishable/anon): con RLS no da acceso a la tabla. Nunca poner aquí la clave de servicio.
- Idiomas: con web/src/i18n/{es,en,fr}.json publica también en dist/en/ y dist/fr/ las páginas públicas que tienen
  marcas data-i18n (texto de data-i18n y data-i18n-attr, <html lang>, rutas, selector de idioma y hreflang) y escribe
  _redirects con la detección del idioma del navegador de Netlify. El tour, sólo si resuelve su modelo con
  import.meta.url. Sin en.json o fr.json, o sin ninguna página marcada, el sitio queda sólo en español (ver idiomas()). El tour
  se publica en otro idioma sólo si su JS resuelve el modelo con import.meta.url (ver tour_traducible()).
- Revisa que web/src/js/textos-es.js (respaldo en español del JS) coincida con es.json; `--textos-es` lo regenera.
- Pone en cada HTML su CSP como <meta>, derivada de lo que la página carga de verdad (scripts propios, rutas exactas
  de jsDelivr, Google Fonts sólo si la enlaza, hashes de sus scripts en línea), y escribe _headers (Netlify) con las
  cabeceras de seguridad comunes y la caché de imágenes y texturas.
- Revisa que todo enlace local de los HTML exista en dist/ (también en las páginas de en/ y fr/).
Sin dependencias fuera de Pillow (incluida en el sistema).
"""
import argparse
import base64
import hashlib
import json
import os
import posixpath
import re
import shutil
import sys
from collections import namedtuple
from html import escape as escapar, unescape as desescapar

from PIL import Image

WEB = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(WEB)
SRC, DIST = os.path.join(WEB, "src"), os.path.join(WEB, "dist")
RENDERS = os.path.join(WEB, "renders_png")
IMAGENES = {"Living": "living", "Living_Sofa": "living-sofa", "Cocina": "cocina", "Dorm1": "dorm1", "Dorm2": "dorm2",
            "Bano1_Vanitorio": "bano", "Balcon": "balcon", "Hall_Recibidor": "recibidor", "Maqueta": "maqueta"}
ANCHOS = (1600, 800)
# Muestras de materiales de la portada (ADR 0006, decisión 5; ids elegidos con la sesión de diseño): recorte cuadrado
# centrado de la textura difusa propia. `fraccion` = lado del recorte / lado de la textura, para que se lea la escala
# real (docs/deco-industrial.md: ladrillo 1,2 m, concreto y roble 2,4 m, cuero 0,4 m, acero 0,6 m por textura) sin
# agrandar: el recorte más chico (768 px) todavía alcanza para la variante de 720.
TEXTURAS = os.path.join(RAIZ, "assets", "texturas", "propias")
MUESTRAS = {"ladrillo": ("ladrillo", 1.0), "concreto": ("concreto_encofrado", 0.75), "roble": ("piso_roble", 0.75),
            "cuero": ("cuero", 1.0), "acero": ("acero_pavonado", 1.0)}
LADOS_MUESTRA = (360, 720)
RE_SUPABASE = re.compile(r"^https://[a-z0-9]{10,40}\.supabase\.co$")
RE_PUBLICABLE = re.compile(r"sb_publishable_[A-Za-z0-9_-]{20,}")
RE_CDN = re.compile(r"https://cdn\.jsdelivr\.net/npm/[A-Za-z0-9._-]+@[0-9][0-9A-Za-z.-]*/")

# Idiomas del sitio público (mecanismo acordado entre las sesiones; el marcado del HTML lo hace otra PR):
# - web/src sigue en español y se publica en la raíz; dist/en/ y dist/fr/ son copias traducidas de las mismas páginas,
#   salvo admin/, que queda sólo en español. Del tour se copia sólo tour/index.html: su JS, su CSS y su modelo son los
#   de /tour/ (un solo JS y un solo modelo en caché).
# - Texto: elemento hoja con data-i18n="clave". Atributos: data-i18n-attr="alt:clave; aria-label:clave; content:clave".
# - Diccionarios planos clave -> texto en web/src/i18n/<idioma>.json (el copytree los deja en dist/i18n/). Las claves
#   «js.*» las usa el JS (web/src/js/i18n.js) y deben ser las mismas en los tres.
# - Selector: <a data-i18n-alternar="es|en|fr">; el build le pone el href a la misma página en ese idioma.
IDIOMAS = ("es", "en", "fr")
IDIOMA_BASE = "es"                                  # el de web/src, en la raíz del sitio; también es el x-default
SITIO_URL = "https://loft-2d2b.netlify.app"         # hreflang pide URL absolutas; se cambia con la variable SITIO_URL
RE_SITIO = re.compile(r"^https://[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
RE_CLAVE = re.compile(r"^[A-Za-z0-9_.-]+$")
RE_ESQUEMA = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")        # https:, mailto:, tel:, data:, javascript:, blob:…
# Etiqueta de apertura con sus atributos (comillas dobles, simples o sin comillas), o un comentario entero. Un atributo
# va después de un espacio o pegado a la comilla que cierra el anterior (class="x"data-i18n="k"): el navegador lo
# acepta como un error de parseo menor y conserva el atributo, así que el build también.
_ATRIBUTO = r"""[^\s"'>/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?"""
RE_TOKEN = re.compile(rf"""<!--.*?-->|<([A-Za-z][A-Za-z0-9-]*)((?:(?:\s+|(?<=["'])){_ATRIBUTO})*)\s*/?>""", re.S)
RE_ATRIBUTO = re.compile(r"""([^\s"'>/=]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s"'=<>`]+))?""")
# Cualquier aparición de las marcas de idioma, para detectar las que quedan en una etiqueta que RE_TOKEN no reconoce.
RE_MARCA_CRUDA = re.compile(r"(?<![\w-])data-i18n(?:-attr|-alternar)?(?![\w-])", re.I)
VACIOS = frozenset("area base br col embed hr img input link meta source track wbr".split())
# data-i18n-attr sólo traduce atributos que el navegador muestra o lee en voz alta como texto (lista blanca): nunca URL,
# HTML (srcdoc), tipos, rel, estilos ni manejadores. `content` sólo en los <meta> de descripción y título (sin
# http-equiv: <meta http-equiv="refresh" content="0; url=…"> redirige).
TRADUCIBLES = frozenset("alt title aria-label aria-description aria-roledescription aria-valuetext aria-placeholder "
                        "placeholder label".split())
META_TRADUCIBLES = frozenset({("name", "description"), ("property", "og:title"), ("property", "og:description")})
Marca = namedtuple("Marca", "clave texto inicio fin atributo")    # atributo None = el texto del elemento
Atributo = namedtuple("Atributo", "valor valor_span span")


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


def muestras():
    """img/material-<nombre>-<lado>.{jpg,webp} desde assets/texturas/propias/<id>/<id>_diff_1k.jpg (no desde los
    renders: así se leen como muestras del material y no como objetos)."""
    for nombre, (tid, fraccion) in MUESTRAS.items():
        ruta = os.path.join(TEXTURAS, tid, f"{tid}_diff_1k.jpg")
        if not os.path.exists(ruta):
            raise SystemExit(f"falta la textura {ruta} (build/deco_texturas.py)")
        im = Image.open(ruta).convert("RGB")
        lado = round(min(im.size) * fraccion)
        if lado < max(LADOS_MUESTRA):
            raise SystemExit(f"{nombre}: el recorte de {lado} px no alcanza para {max(LADOS_MUESTRA)} px sin agrandar")
        x0, y0 = (im.width - lado) // 2, (im.height - lado) // 2
        recorte = im.crop((x0, y0, x0 + lado, y0 + lado))
        for l in LADOS_MUESTRA:
            r = recorte.resize((l, l), Image.LANCZOS)
            r.save(os.path.join(DIST, "img", f"material-{nombre}-{l}.jpg"), quality=82, optimize=True, progressive=True)
            r.save(os.path.join(DIST, "img", f"material-{nombre}-{l}.webp"), quality=80, method=6)


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


# ---------------------------------------------------------------- idiomas: lectura del HTML (funciones puras)

def _etiquetas(s, ignorados=None):
    """Etiquetas de apertura de `s` (coincidencias de RE_TOKEN: grupo 1 el nombre, grupo 2 los atributos), sin las que
    están dentro de un comentario o del contenido de <script> y <style>, donde «<» no abre una etiqueta. Si se pasa la
    lista `ignorados`, se le agregan los tramos (inicio, fin) de esos comentarios y contenidos."""
    pos = 0
    while True:
        m = RE_TOKEN.search(s, pos)
        if not m:
            return
        pos = m.end()
        if m.group(1) is None:                                     # comentario
            if ignorados is not None:
                ignorados.append(m.span())
            continue
        yield m
        nombre = m.group(1).lower()
        if nombre in ("script", "style"):
            cierre = re.compile(rf"</{nombre}\s*>", re.I).search(s, pos)
            if ignorados is not None:
                ignorados.append((pos, cierre.start() if cierre else len(s)))
            pos = cierre.start() if cierre else len(s)


def revisar_marcas_legibles(s, ruta):
    """Falla si data-i18n, data-i18n-attr o data-i18n-alternar aparecen fuera de las etiquetas que el build reconoce (y
    fuera de comentarios, <script> y <style>). Una etiqueta que RE_TOKEN no sabe leer se saltaría sin aviso: el texto
    quedaría en español en /en/ y el selector sin href."""
    tramos = []
    tramos += [m.span() for m in _etiquetas(s, tramos)]
    for c in RE_MARCA_CRUDA.finditer(s):
        if not any(inicio <= c.start() < fin for inicio, fin in tramos):
            linea = s.count("\n", 0, c.start()) + 1
            raise SystemExit(f"{ruta}:{linea}: «{c.group(0)}» está en una etiqueta que el build no sabe leer (revisa "
                             "comillas, «=» y espacios entre atributos): esa marca se perdería sin aviso")


def _atributos(m):
    """Atributos de la etiqueta `m`: nombre en minúsculas -> Atributo(valor sin entidades, tramo del valor con sus
    comillas o None si no tiene, tramo del atributo entero), con posiciones en el texto completo. Si un nombre se
    repite vale el primero, como en el navegador."""
    base, datos = m.start(2), {}
    for a in RE_ATRIBUTO.finditer(m.group(2)):
        nombre, crudo = a.group(1).lower(), a.group(2)
        if nombre in datos:
            continue
        valor = desescapar(crudo[1:-1] if crudo and crudo[0] in "\"'" else (crudo or ""))
        datos[nombre] = Atributo(valor, (base + a.start(2), base + a.end(2)) if crudo else None,
                                 (base + a.start(), base + a.end()))
    return datos


def _editar(s, ediciones):
    """Aplica reemplazos (inicio, fin, texto) que no se solapan."""
    partes, pos = [], 0
    for inicio, fin, texto in sorted(ediciones):
        if inicio < pos:
            raise ValueError(f"reemplazos solapados en {inicio}")
        partes += [s[pos:inicio], texto]
        pos = fin
    return "".join(partes) + s[pos:]


def _etiqueta_con(s, m, cambios):
    """Texto de la etiqueta `m` con los atributos de `cambios` (nombre -> valor, que se escapa, o None para quitarlo).
    Los que no estaban se agregan al final; el resto de la etiqueta queda igual."""
    attrs, ediciones, nuevos = _atributos(m), [], []
    for nombre, valor in cambios.items():
        a = attrs.get(nombre)
        if a is None:
            if valor is not None:
                nuevos.append(f' {nombre}="{escapar(valor)}"')
        elif valor is None:
            inicio = a.span[0]
            while inicio > m.start(2) and s[inicio - 1].isspace():         # con el espacio que lo separa
                inicio -= 1
            ediciones.append((inicio - m.start(), a.span[1] - m.start(), ""))
        else:
            ediciones.append((a.span[0] - m.start(), a.span[1] - m.start(), f'{nombre}="{escapar(valor)}"'))
    corte = m.end(2) - m.start()
    etiqueta = s[m.start():m.end()]
    return _editar(etiqueta[:corte], ediciones) + "".join(nuevos) + etiqueta[corte:]


def _clave_valida(clave, ruta, donde):
    if not RE_CLAVE.match(clave):
        raise SystemExit(f"{ruta}: {donde}: clave «{clave}» inválida (letras, números, «.», «_» y «-»)")
    return clave


def atributo_traducible(nombre, etiqueta, attrs):
    """¿Puede data-i18n-attr traducir el atributo `nombre` de <`etiqueta`> (con sus atributos `attrs`)? Lista blanca
    TRADUCIBLES, salvo `title` en <link> y <style>, donde nombra un juego de hojas de estilo; `content`, sólo en un
    <meta> sin http-equiv cuyo name o property esté en META_TRADUCIBLES."""
    if nombre in TRADUCIBLES:
        return not (nombre == "title" and etiqueta in ("link", "style"))
    if nombre != "content" or etiqueta != "meta" or "http-equiv" in attrs:
        return False
    return any(a in attrs and attrs[a].valor.strip().lower() == v for a, v in META_TRADUCIBLES)


def _pares_i18n_attr(valor, ruta, etiqueta, attrs):
    """data-i18n-attr="alt:clave; aria-label:clave" de <`etiqueta`> -> [("alt", "clave"), ("aria-label", "clave")].
    Falla si pide un atributo que no es texto (ver atributo_traducible())."""
    pares = []
    for parte in valor.split(";"):
        if not parte.strip():
            continue
        nombre, sep, clave = parte.partition(":")
        nombre, clave = nombre.strip().lower(), clave.strip()
        if not sep or not nombre or not clave:
            raise SystemExit(f'{ruta}: data-i18n-attr="{valor}" mal formado (se espera «atributo:clave; …»)')
        _clave_valida(clave, ruta, f"data-i18n-attr {nombre}")
        if not atributo_traducible(nombre, etiqueta, attrs):
            raise SystemExit(f"{ruta}: data-i18n-attr no traduce «{nombre}» en <{etiqueta}> ({clave}): sólo "
                             f"{', '.join(sorted(TRADUCIBLES))} y content de <meta name=\"description\">, og:title u "
                             "og:description (nunca URL, HTML, tipos, rel, estilos ni manejadores)")
        if any(n == nombre for n, _ in pares):
            raise SystemExit(f'{ruta}: data-i18n-attr="{valor}" repite «{nombre}»')
        pares.append((nombre, clave))
    if not pares:
        raise SystemExit(f'{ruta}: data-i18n-attr="{valor}" vacío')
    return pares


def marcas_i18n(s, ruta):
    """Textos traducibles de la página `ruta`: [Marca(clave, texto en español, inicio, fin, atributo)]. Para un
    data-i18n, el tramo es el contenido del elemento sin los espacios de los bordes (se conservan); para un
    data-i18n-attr, el valor del atributo con sus comillas. Falla, con el archivo y la clave, si el elemento no es
    hoja (su contenido trae «<»), si es vacío (img, meta…), si le falta el atributo que se pide traducir o si una
    marca queda en una etiqueta ilegible (revisar_marcas_legibles())."""
    revisar_marcas_legibles(s, ruta)
    marcas = []
    for m in _etiquetas(s):
        attrs, etiqueta = _atributos(m), m.group(1).lower()
        if "data-i18n-attr" in attrs:
            for nombre, clave in _pares_i18n_attr(attrs["data-i18n-attr"].valor, ruta, etiqueta, attrs):
                a = attrs.get(nombre)
                if a is None or a.valor_span is None:
                    raise SystemExit(f"{ruta}: data-i18n-attr pide «{nombre}» ({clave}) y <{etiqueta}> no lo trae")
                marcas.append(Marca(clave, a.valor, *a.valor_span, nombre))
        if "data-i18n" not in attrs:
            continue
        clave = _clave_valida(attrs["data-i18n"].valor.strip(), ruta, "data-i18n")
        if etiqueta in VACIOS or etiqueta in ("script", "style") or m.group(0).endswith("/>"):
            raise SystemExit(f'{ruta}: data-i18n="{clave}" en <{etiqueta}>, que no tiene texto (usa data-i18n-attr)')
        j = s.find("<", m.end())
        if j < 0 or not re.compile(rf"</{re.escape(etiqueta)}\s*>", re.I).match(s, j):
            raise SystemExit(f'{ruta}: data-i18n="{clave}": <{etiqueta}> no es hoja (su contenido trae «<»); marca '
                             "cada texto en un elemento sin hijos")
        contenido = s[m.end():j]
        inicio = m.end() + len(contenido) - len(contenido.lstrip())
        fin = max(inicio, j - (len(contenido) - len(contenido.rstrip())))
        marcas.append(Marca(clave, desescapar(s[inicio:fin]), inicio, fin, None))
    return marcas


# ---------------------------------------------------------------- idiomas: transformación (funciones puras)

def url_de_pagina(ruta, idioma):
    """URL, desde la raíz del sitio, de la página `ruta` en `idioma` (las index.html en forma de carpeta):
    ("index.html", "es") -> "/", ("tour/index.html", "en") -> "/en/tour/", ("reserva.html", "fr") -> "/fr/reserva.html"."""
    publica = ruta[:-len("index.html")] if ruta == "index.html" or ruta.endswith("/index.html") else ruta
    return ("/" if idioma == IDIOMA_BASE else f"/{idioma}/") + publica


def url_en_idioma(ref, ruta, idioma, paginas):
    """`ref`, tal como la usa la página `ruta` de la raíz, reescrita para la copia de esa página en dist/<idioma>/.

    Se resuelve contra la ruta original. Si el destino es una página traducida (está en `paginas`), queda dentro de
    /<idioma>/; si no (css, js, img, fonts, i18n, tour/js, tour/modelo, admin…), apunta al archivo compartido de la
    raíz. Una ruta relativa sigue relativa (ahora desde <idioma>/<ruta>) y una que empieza con «/» sigue así (la usa
    404.html, que Netlify sirve en cualquier ruta). Conserva ?query y #ancla. No toca URL con esquema (https:,
    mailto:, tel:, data:…), las que empiezan con //, # o ?, ni las que salen del sitio."""
    u = ref.strip()
    if not u or u.startswith(("#", "?", "//")) or RE_ESQUEMA.match(u):
        return ref
    corte = min([i for i in (u.find("?"), u.find("#")) if i >= 0] or [len(u)])
    camino, cola = u[:corte], u[corte:]
    absoluta = camino.startswith("/")
    base = posixpath.dirname(ruta)
    destino = posixpath.normpath(camino.lstrip("/") if absoluta else posixpath.join(base, camino))
    destino = "" if destino == "." else destino
    if destino == ".." or destino.startswith("../"):
        return ref                                   # fuera del sitio: queda igual y revisar_enlaces() lo reporta
    carpeta = camino.endswith("/") or posixpath.basename(camino) in (".", "..")
    indice = posixpath.join(destino, "index.html") if destino else "index.html"
    pagina = (indice if carpeta else destino) in paginas or (not carpeta and indice in paginas)   # «tour» sin barra
    nuevo = (f"{idioma}/{destino}" if destino else idioma) if pagina else destino
    if absoluta:
        salida = "/" + nuevo
    else:
        salida = posixpath.relpath(nuevo or ".", f"{idioma}/{base}" if base else idioma)
    if carpeta:
        salida = "./" if salida == "." else salida.rstrip("/") + "/"
    return ref if salida + cola == u else salida + cola


def _candidatos(srcset):
    """[(url, descriptor)] de un srcset. La URL es una corrida sin espacios (las comas finales la cierran) y el
    descriptor llega hasta la coma siguiente fuera de paréntesis (algoritmo de WHATWG, simplificado): así una
    URL data: con comas no se parte."""
    salida, i, n = [], 0, len(srcset)
    while i < n:
        while i < n and (srcset[i].isspace() or srcset[i] == ","):
            i += 1
        j = i
        while j < n and not srcset[j].isspace():
            j += 1
        if i == j:
            break
        url, descriptor = srcset[i:j], ""
        if url.endswith(","):
            url, i = url.rstrip(","), j
        else:
            k, prof = j, 0
            while k < n and (srcset[k] != "," or prof):
                prof = prof + 1 if srcset[k] == "(" else max(0, prof - 1) if srcset[k] == ")" else prof
                k += 1
            descriptor, i = srcset[j:k].strip(), k + 1
        salida.append((url, descriptor))
    return salida


def _srcset_en_idioma(valor, ruta, idioma, paginas):
    candidatos = _candidatos(valor)
    nuevos = [(url_en_idioma(u, ruta, idioma, paginas), d) for u, d in candidatos]
    if nuevos == candidatos:
        return valor
    return ", ".join(u + (" " + d if d else "") for u, d in nuevos)


def traducir_textos(s, ruta, dic):
    """Pone en cada data-i18n y data-i18n-attr el texto de `dic`, escapado como HTML (& < > y comillas)."""
    ediciones = []
    for mk in marcas_i18n(s, ruta):
        texto = dic.get(mk.clave)
        if not isinstance(texto, str) or not texto.strip():
            raise SystemExit(f"{ruta}: la clave {mk.clave} no tiene texto en el diccionario")
        if mk.atributo:
            ediciones.append((mk.inicio, mk.fin, f'"{escapar(texto)}"'))
        else:
            ediciones.append((mk.inicio, mk.fin, escapar(texto.strip())))
    return _editar(s, ediciones)


def poner_lang(s, ruta, idioma):
    m = next((m for m in _etiquetas(s) if m.group(1).lower() == "html"), None)
    if m is None:
        raise SystemExit(f"{ruta}: falta <html> para ponerle lang")
    return s[:m.start()] + _etiqueta_con(s, m, {"lang": idioma}) + s[m.end():]


def reescribir_urls(s, ruta, idioma, paginas):
    """Rutas de src, href, srcset, imagesrcset (cada candidato), poster y el content de <meta property="og:image">,
    reescritas con url_en_idioma(). Los <a data-i18n-alternar> los resuelve alternar()."""
    ediciones = []
    for m in _etiquetas(s):
        attrs = _atributos(m)
        if "data-i18n-alternar" in attrs:
            continue
        og = m.group(1).lower() == "meta" and attrs.get("property", Atributo("", None, None)).valor.strip() == "og:image"
        for nombre, a in attrs.items():
            if a.valor_span is None:
                continue
            if nombre in ("srcset", "imagesrcset"):
                nuevo = _srcset_en_idioma(a.valor, ruta, idioma, paginas)
            elif nombre in ("src", "href", "poster") or (og and nombre == "content"):
                nuevo = url_en_idioma(a.valor, ruta, idioma, paginas)
            else:
                continue
            if nuevo != a.valor:
                ediciones.append((*a.valor_span, f'"{escapar(nuevo)}"'))
    return _editar(s, ediciones)


def alternar(s, ruta, idioma, paginas=None):
    """Selector de idioma: cada <a data-i18n-alternar="xx"> apunta a esta misma página en xx (en la raíz si xx es
    «es»), con hreflang="xx" y lang="xx"; el del idioma de la página lleva aria-current="true" y los demás no.

    Con `paginas` (las traducidas): si `ruta` no está entre ellas, la página queda sólo en español y no existe en xx,
    así que el enlace a otro idioma lleva al inicio de ese idioma. Si el inicio tampoco está traducido, falla: el
    enlace no tendría destino."""
    ediciones = []
    for m in _etiquetas(s):
        a = _atributos(m).get("data-i18n-alternar")
        if a is None:
            continue
        destino = a.valor.strip().lower()
        if m.group(1).lower() != "a" or destino not in IDIOMAS:
            raise SystemExit(f'{ruta}: data-i18n-alternar="{a.valor}" va en un <a> y vale {", ".join(IDIOMAS)}')
        if paginas is None or ruta in paginas or destino == IDIOMA_BASE:
            href = url_de_pagina(ruta, destino)
        elif "index.html" in paginas:
            href = url_de_pagina("index.html", destino)
        else:
            raise SystemExit(f"{ruta}: trae selector de idioma, pero ni esta página ni el inicio se publican en "
                             f"{destino}/ (sin data-i18n): el enlace a «{destino}» no tendría destino")
        cambios = {"href": href, "hreflang": destino, "lang": destino,
                   "aria-current": "true" if destino == idioma else None}
        ediciones.append((m.start(), m.end(), _etiqueta_con(s, m, cambios)))
    return _editar(s, ediciones)


def enlaces_alternos(ruta, sitio_url):
    """<link rel="alternate" hreflang> de la página `ruta` en los tres idiomas, más x-default (el español)."""
    filas = [(i, sitio_url + url_de_pagina(ruta, i)) for i in IDIOMAS]
    filas.append(("x-default", sitio_url + url_de_pagina(ruta, IDIOMA_BASE)))
    return "\n".join(f'<link rel="alternate" hreflang="{i}" href="{escapar(u)}">' for i, u in filas)


def poner_alternos(s, ruta, sitio_url):
    if any(m.group(1).lower() == "link" and "hreflang" in _atributos(m) for m in _etiquetas(s)):
        raise SystemExit(f"{ruta}: ya trae <link hreflang>; los genera build.py")
    cierres = [m.start() for m in re.finditer(r"</head\s*>", s, re.I)]
    if len(cierres) != 1:
        raise SystemExit(f"{ruta}: se espera un solo </head> para colgar los enlaces hreflang")
    return s[:cierres[0]] + enlaces_alternos(ruta, sitio_url) + "\n" + s[cierres[0]:]


def traducir_pagina(s, ruta, idioma, dic, paginas, sitio_url=SITIO_URL):
    """HTML de la página `ruta` (el de la raíz, en español) para dist/<idioma>/<ruta>: textos de `dic`, <html lang>,
    rutas, selector de idioma y hreflang. Con idioma «es» es la misma página de la raíz y sólo se le ponen el
    selector y los hreflang."""
    if idioma != IDIOMA_BASE:
        s = traducir_textos(s, ruta, dic)
        s = poner_lang(s, ruta, idioma)
        s = reescribir_urls(s, ruta, idioma, paginas)
    return poner_alternos(alternar(s, ruta, idioma), ruta, sitio_url)


def redirecciones(paginas):
    """Texto de dist/_redirects: el idioma del navegador elige la versión de cada página traducida."""
    lineas = [
        "# Generado por web/build.py: idioma automático del sitio público con las reglas Language= de Netlify.",
        "# - Netlify mira el primer idioma del Accept-Language del navegador. «302!» fuerza la regla aunque la página",
        "#   exista: el español está en la raíz y, sin «!», Netlify serviría el archivo sin mirar el idioma.",
        "# - La cookie nf_lang reemplaza esa detección: la pone el selector de idioma al elegir (nf_lang=es, en o fr).",
        "#   Con nf_lang=es no calza ninguna regla Language=en|fr y el visitante se queda en la raíz aunque su",
        "#   navegador pida otro idioma; con nf_lang=en va a /en/ aunque el navegador pida francés.",
        "# - Sólo se redirigen las páginas traducidas. /admin/*, /i18n/* y los recursos (css, js, img, fonts, tour/js,",
        "#   tour/modelo…) se sirven siempre desde la raíz.",
        "# - Rutas sin archivo (reglas 404 sin «!»: sólo se aplican si no existe el archivo): /en/* y /fr/* dan el 404",
        "#   de su idioma y el resto del sitio, el del idioma del navegador. Netlify sirve /404.html en cualquier ruta",
        "#   sin archivo sin pasar por una regla «/404.html», por eso 404.html no tiene regla 302!.",
        "#   Supuesto sin verificar en un despliegue: Netlify aplica Language= también en una regla 404.",
    ]
    otros = [i for i in IDIOMAS if i != IDIOMA_BASE]
    filas = []
    for ruta in sorted(set(paginas) - {"404.html"}, key=lambda r: (r != "index.html", r)):
        for idioma in otros:
            filas.append((url_de_pagina(ruta, IDIOMA_BASE), url_de_pagina(ruta, idioma), "302!", f"Language={idioma}"))
    if "404.html" in paginas:
        filas += [(f"/{i}/*", f"/{i}/404.html", "404", "") for i in otros]
        filas += [("/*", f"/{i}/404.html", "404", f"Language={i}") for i in otros]     # después: /en/* gana en /en/
    anchos = [max(len(f[c]) for f in filas) for c in range(3)] if filas else []
    for f in filas:
        lineas.append("  ".join(f[c].ljust(anchos[c]) for c in range(3)) + ("  " + f[3] if f[3] else "").rstrip())
    return "\n".join(l.rstrip() for l in lineas) + "\n"


# ---------------------------------------------------------------- idiomas: diccionarios y validación

def _sin_repetidas(pares):
    datos = {}
    for k, v in pares:
        if k in datos:
            raise ValueError(f"clave repetida: {k}")
        datos[k] = v
    return datos


def leer_diccionario(ruta):
    """Diccionario plano clave -> texto. Falla si el JSON no es válido, repite una clave o trae algo que no sea
    texto (un objeto anidado, un número…)."""
    nombre = os.path.relpath(ruta, WEB)
    try:
        with open(ruta, encoding="utf-8") as fh:
            datos = json.load(fh, object_pairs_hook=_sin_repetidas)
    except ValueError as e:
        raise SystemExit(f"{nombre}: JSON inválido ({e})")
    if not isinstance(datos, dict):
        raise SystemExit(f"{nombre}: se espera un objeto plano clave -> texto")
    for k, v in datos.items():
        _clave_valida(k, nombre, "diccionario")
        if not isinstance(v, str):
            raise SystemExit(f"{nombre}: {k} no es texto (el diccionario es plano: clave -> texto)")
    return datos


def cargar_diccionarios(carpeta):
    """{idioma: diccionario} desde <carpeta>/{es,en,fr}.json, o None si falta en.json o fr.json (el sitio queda sólo
    en español, como antes de los idiomas). Con en.json y fr.json, es.json es obligatorio: contra él se valida."""
    rutas = {i: os.path.join(carpeta, f"{i}.json") for i in IDIOMAS}
    if any(not os.path.exists(rutas[i]) for i in IDIOMAS if i != IDIOMA_BASE):
        return None
    if not os.path.exists(rutas[IDIOMA_BASE]):
        raise SystemExit(f"hay i18n/en.json e i18n/fr.json pero falta i18n/{IDIOMA_BASE}.json (contra él se valida el HTML)")
    return {i: leer_diccionario(r) for i, r in rutas.items()}


def _normalizar(texto):
    return " ".join(texto.split())


def validar_i18n(fuentes, dics):
    """Revisa las páginas en español (`fuentes`: ruta -> HTML) contra los diccionarios. Devuelve (errores, avisos).

    Errores: una clave de data-i18n o data-i18n-attr sin texto en es, en o fr; el texto de es.json distinto del
    que dice el HTML (con los espacios normalizados: así es.json no se desfasa); claves js.* distintas entre los tres.
    Avisos: claves que no usa nadie, páginas sin data-i18n y textos js.* vacíos."""
    errores, avisos, usadas, sin_texto = [], [], set(), {}
    for ruta in sorted(fuentes):
        marcas = marcas_i18n(fuentes[ruta], ruta)
        if not marcas:
            avisos.append(f"{ruta}: sin data-i18n: no se publica en en/ ni fr/ (queda sólo en español)")
        for mk in marcas:
            usadas.add(mk.clave)
            donde = f"{ruta}: {mk.clave}" + (f" ({mk.atributo})" if mk.atributo else "")
            for idioma in IDIOMAS:
                texto = dics[idioma].get(mk.clave)
                if not isinstance(texto, str) or not texto.strip():
                    sin_texto.setdefault((mk.clave, idioma), donde)
            es = dics[IDIOMA_BASE].get(mk.clave)
            if isinstance(es, str) and es.strip() and _normalizar(es) != _normalizar(mk.texto):
                errores.append(f"{donde}: {IDIOMA_BASE}.json dice «{_normalizar(es)}» y el HTML «{_normalizar(mk.texto)}»")
    errores += [f"{donde}: sin texto en {idioma}.json" for (_, idioma), donde in sorted(sin_texto.items())]
    js = {i: {k for k in dics[i] if k.startswith("js.")} for i in IDIOMAS}
    for idioma in IDIOMAS:
        if idioma == IDIOMA_BASE:
            continue
        for k in sorted(js[IDIOMA_BASE] - js[idioma]):
            errores.append(f"{idioma}.json: falta {k} (está en {IDIOMA_BASE}.json)")
        for k in sorted(js[idioma] - js[IDIOMA_BASE]):
            errores.append(f"{idioma}.json: sobra {k} (no está en {IDIOMA_BASE}.json)")
    for idioma in IDIOMAS:
        avisos += [f"{idioma}.json: {k} está vacío" for k in sorted(js[idioma]) if not dics[idioma][k].strip()]
    sin_uso = {}
    for idioma in IDIOMAS:
        for k in dics[idioma]:
            if not k.startswith("js.") and k not in usadas:
                sin_uso.setdefault(k, []).append(idioma)
    avisos += [f"clave sin uso: {k} ({', '.join(i)})" for k, i in sorted(sin_uso.items())]
    return errores, avisos


# ---------------------------------------------------------------- idiomas: escritura en dist/

def paginas_traducibles(dist):
    """Rutas (con /) de los HTML que también se publican en en/ y fr/: todo HTML de dist salvo admin/ (sólo en
    español) y vendor/; hoy, las páginas de la raíz y tour/index.html."""
    paginas = set()
    for base, carpetas, archivos in os.walk(dist):
        rel = os.path.relpath(base, dist).replace(os.sep, "/")
        if rel == ".":
            carpetas[:] = [c for c in carpetas if c not in ("admin", "vendor", *IDIOMAS)]
            rel = ""
        paginas |= {posixpath.join(rel, a) for a in archivos if a.endswith(".html")}
    return paginas


# El tour en otro idioma (dist/<idioma>/tour/index.html) usa el JS y el modelo de /tour/. Para eso el JS debe resolver
# el modelo con import.meta.url, es decir, relativo al módulo y no a la página: con RUTA_MODELO = "modelo/", desde
# /en/tour/ pediría /en/tour/modelo/…, que no existe (hallazgo JS-1 de la revisión). Mientras sea así, el tour no se
# publica en en/ ni fr/ y no tiene reglas Language= (quien entra a /tour/ se queda en el tour en español, que funciona).
# Se habilita solo cuando web/src/tour/js/carga.js pase a `new URL("../modelo/", import.meta.url)`.
RE_MODELO_DEL_MODULO = re.compile(r"""\bRUTA_MODELO\s*=\s*new\s+URL\(\s*(["'`])[^"'`]*\1\s*,\s*import\.meta\.url\s*\)""")
RE_MODELO_DE_LA_PAGINA = re.compile(r"""["'`](?:\./)?modelo/""")     # «"modelo/…"»: relativo a la página


def tour_traducible(dist):
    """¿Puede publicarse el tour en en/ y fr/? No si dist/tour/js/carga.js existe y su RUTA_MODELO no se arma con
    import.meta.url, ni si algún JS de dist/tour/js/ nombra el modelo con una ruta relativa a la página («modelo/…»)."""
    carpeta = os.path.join(dist, "tour", "js")
    if not os.path.isdir(carpeta):
        return True
    for a in sorted(os.listdir(carpeta)):
        if not a.endswith(".js"):
            continue
        with open(os.path.join(carpeta, a), encoding="utf-8") as fh:
            s = fh.read()
        if RE_MODELO_DE_LA_PAGINA.search(s) or (a == "carga.js" and not RE_MODELO_DEL_MODULO.search(s)):
            return False
    return True


def textos_es_js(dic_es):
    """Texto de web/src/js/textos-es.js: las claves js.* de es.json, en su orden, como módulo ES. Es el respaldo en
    español de web/src/js/i18n.js y viene con el JS: la página en español no pide ningún diccionario por la red y en
    /en/ y /fr/ nunca se ven las claves (hallazgo JS-2 de la revisión)."""
    js = {k: v for k, v in dic_es.items() if k.startswith("js.")}
    return ("// Generado por web/build.py desde web/src/i18n/es.json (sólo las claves js.*). No se edita a mano: después\n"
            "// de cambiar es.json se regenera con  python3 web/build.py --textos-es  (el build y npm test revisan que\n"
            "// coincidan). Es el respaldo en español de i18n.js: viene con el JS y no depende de la red.\n"
            f"export default {json.dumps(js, ensure_ascii=False, indent=2)};\n")


def revisar_textos_es(carpeta):
    """Falla si <carpeta>/js/i18n.js existe y <carpeta>/js/textos-es.js no es textos_es_js() de <carpeta>/i18n/es.json."""
    if not os.path.exists(os.path.join(carpeta, "js", "i18n.js")):
        return
    es = os.path.join(carpeta, "i18n", f"{IDIOMA_BASE}.json")
    if not os.path.exists(es):
        raise SystemExit(f"js/i18n.js necesita i18n/{IDIOMA_BASE}.json para su respaldo js/textos-es.js")
    ruta = os.path.join(carpeta, "js", "textos-es.js")
    actual = None
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as fh:
            actual = fh.read()
    if actual != textos_es_js(leer_diccionario(es)):
        raise SystemExit("web/src/js/textos-es.js no coincide con las claves js.* de web/src/i18n/es.json: "
                         "regenéralo con  python3 web/build.py --textos-es")


def escribir_textos_es():
    """--textos-es: escribe web/src/js/textos-es.js desde web/src/i18n/es.json."""
    with open(os.path.join(SRC, "js", "textos-es.js"), "w", encoding="utf-8") as fh:
        fh.write(textos_es_js(leer_diccionario(os.path.join(SRC, "i18n", f"{IDIOMA_BASE}.json"))))


def publicables(fuentes, tour_listo=True):
    """(páginas que se publican en en/ y fr/, avisos), de las candidatas `fuentes` (ruta -> HTML en español).

    Sólo las que tienen al menos un data-i18n o data-i18n-attr: una página sin marcas saldría en /en/ con su texto en
    español pero con lang="en" (un lector de pantalla la leería con la voz del inglés), hreflang que la anuncian como
    versión inglesa y una regla 302! que manda ahí a los navegadores en inglés. Del tour, además, sólo si `tour_listo`
    (tour_traducible())."""
    paginas, avisos = {r for r, s in fuentes.items() if marcas_i18n(s, r)}, []
    if not tour_listo:
        paginas = {p for p in paginas if not p.startswith("tour/")}
        avisos.append("tour/: no se publica en en/ ni fr/ (ni con reglas Language=): web/src/tour/js/carga.js "
                      "resuelve el modelo relativo a la página; con RUTA_MODELO = new URL(\"../modelo/\", "
                      "import.meta.url).href se publica solo")
    return paginas, avisos


def publicar_idiomas(fuentes, dics, paginas, sitio_url=SITIO_URL):
    """Escribe en dist/ cada página de `paginas` en los tres idiomas (la de la raíz con su selector y sus hreflang),
    el selector de las demás de `fuentes` (quedan sólo en español; ver alternar()) y dist/_redirects."""
    for idioma in IDIOMAS:
        for ruta in sorted(paginas):
            destino = os.path.join(DIST, *([] if idioma == IDIOMA_BASE else [idioma]), *ruta.split("/"))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "w", encoding="utf-8") as fh:
                fh.write(traducir_pagina(fuentes[ruta], ruta, idioma, dics[idioma], paginas, sitio_url))
    for ruta in sorted(set(fuentes) - set(paginas)):
        s = alternar(fuentes[ruta], ruta, IDIOMA_BASE, paginas)
        if s != fuentes[ruta]:
            print("AVISO_I18N", f"{ruta}: queda sólo en español; su selector lleva al inicio de cada idioma")
            with open(os.path.join(DIST, *ruta.split("/")), "w", encoding="utf-8") as fh:
                fh.write(s)
    with open(os.path.join(DIST, "_redirects"), "w") as fh:
        fh.write(redirecciones(paginas))


def idiomas(sitio_url=SITIO_URL):
    """Con dist/i18n/{es,en,fr}.json: valida las páginas públicas, escribe dist/en/ y dist/fr/ con las que tienen
    marcas (publicables()), pone el selector y los hreflang en las de la raíz y escribe dist/_redirects. Devuelve las
    páginas traducidas; vacío, sin escribir nada, si faltan diccionarios o si ninguna página tiene marcas."""
    dics = cargar_diccionarios(os.path.join(DIST, "i18n"))
    if dics is None:
        print("IDIOMAS sólo español: faltan web/src/i18n/en.json o fr.json")
        return set()
    for ocupado in [*(i for i in IDIOMAS if i != IDIOMA_BASE), "_redirects"]:
        if os.path.exists(os.path.join(DIST, ocupado)):
            raise SystemExit(f"web/src/{ocupado} no debe existir: lo genera build.py")
    fuentes = {}
    for ruta in paginas_traducibles(DIST):
        with open(os.path.join(DIST, ruta), encoding="utf-8") as fh:
            fuentes[ruta] = fh.read()
    errores, avisos = validar_i18n(fuentes, dics)
    paginas, avisos_tour = publicables(fuentes, tour_traducible(DIST))
    for a in avisos_tour + avisos:
        print("AVISO_I18N", a)
    if errores:
        raise SystemExit("idiomas:\n  " + "\n  ".join(errores))
    if not paginas:
        for ruta in sorted(fuentes):                        # un selector sin destino es un error, aun sin idiomas
            alternar(fuentes[ruta], ruta, IDIOMA_BASE, paginas)
        print("IDIOMAS sólo español: ninguna página pública tiene data-i18n")
        return set()
    publicar_idiomas(fuentes, dics, paginas, sitio_url)
    return paginas


def sitio_publico(env):
    """URL pública del sitio para hreflang (SITIO_URL, por defecto la de Netlify): https://dominio, sin ruta."""
    sitio = (env.get("SITIO_URL") or SITIO_URL).strip().rstrip("/")
    if not RE_SITIO.match(sitio):
        raise SystemExit(f"SITIO_URL con forma inesperada: {sitio} (se espera https://dominio, sin ruta)")
    return sitio


def revisar_enlaces(sitio_url=""):
    """Enlaces locales rotos de todos los HTML de dist (también los de en/ y fr/): src, href, srcset, imagesrcset,
    poster y og:image. Con `sitio_url`, las URL absolutas del propio sitio (hreflang) también se revisan."""
    faltan = []
    for base, _, archivos in os.walk(DIST):
        for a in archivos:
            if not a.endswith(".html"):
                continue
            ruta = os.path.join(base, a)
            with open(ruta, encoding="utf-8") as fh:
                s = fh.read()
            refs = re.findall(r'\b(src|href|srcset|imagesrcset|poster)="([^"]+)"', s)
            refs += [("content", c) for e in re.findall(r'<meta\b[^>]*\bproperty="og:image"[^>]*>', s)
                     for c in re.findall(r'\bcontent="([^"]*)"', e)]
            for atributo, ref in refs:
                ref = desescapar(ref)
                for u in ([c for c, _ in _candidatos(ref)] if "srcset" in atributo else [ref.strip()]):
                    if sitio_url and (u + "/").startswith(sitio_url + "/"):
                        u = u[len(sitio_url):] or "/"
                    if not u or re.match(r"^(https?:|mailto:|tel:|data:|#|javascript:|//)", u):
                        continue
                    u = u.split("#")[0].split("?")[0]
                    if not u:                                  # sólo ?query: es la misma página
                        continue
                    destino = os.path.join(DIST, u.lstrip("/")) if u.startswith("/") else os.path.join(base, u)
                    if u.endswith("/") or os.path.isdir(destino):
                        destino = os.path.join(destino, "index.html")
                    if not os.path.exists(os.path.normpath(destino)):
                        faltan.append(f"{os.path.relpath(ruta, DIST)} -> {u}")
    return faltan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="")
    ap.add_argument("--textos-es", action="store_true",
                    help="sólo regenera web/src/js/textos-es.js desde web/src/i18n/es.json y termina")
    args = ap.parse_args()
    if args.textos_es:
        escribir_textos_es()
        print("TEXTOS_ES_OK web/src/js/textos-es.js")
        return
    env = {**leer_env(args.env),
           **{k: v for k, v in os.environ.items() if k.startswith("SUPABASE_") or k == "SITIO_URL"}}
    sitio = sitio_publico(env)
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    shutil.copytree(SRC, DIST)
    revisar_textos_es(DIST)                # el respaldo en español del JS, al día con es.json
    imagenes()
    muestras()
    escritorio, movil = tour()
    url = configuracion(env)
    traducidas = idiomas(sitio)            # antes de politicas() y revisar_enlaces(): cubren también en/ y fr/
    politicas(url)
    cabeceras()
    faltan = revisar_enlaces(sitio)
    for f in faltan:
        print("ENLACE_ROTO", f)
    n, peso = 0, 0
    for base, _, archivos in os.walk(DIST):
        n += len(archivos)
        peso += sum(os.path.getsize(os.path.join(base, a)) for a in archivos)
    print(f"SITIO_OK {n} archivos, {peso / 1e6:.1f} MB; tour {escritorio / 1e6:.1f} MB (escritorio) y "
          f"{movil / 1e6:.1f} MB (teléfono); reservas {'conectadas a ' + url if url else 'SIN conectar (simuladas en localhost)'}; "
          f"idiomas {', '.join(IDIOMAS) + f' ({len(traducidas)} páginas cada uno)' if traducidas else 'sólo es'}")
    if faltan:
        sys.exit(1)


if __name__ == "__main__":
    main()
