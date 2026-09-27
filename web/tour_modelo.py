"""Convierte exports/web/ (el glTF separado de la fase 6: JSON + geometría en base64 + tex/*.jpg) y
exports/depto_colisiones.json en web/src/tour/modelo/, listo para que el visor v3 (web/src/tour/) lo cargue
con GLTFLoader normal:

- depto.gltf   el mismo JSON de exports/web/depto_gltf.json, con buffers[0].uri apuntando a "depto.bin".
- depto.bin    la geometría de depto_bin.b64.txt, decodificada de base64 a binario.
- tex/         copia de exports/web/tex/ (1024 px, la calidad de escritorio) MÁS un .webp por cada .jpg.
- tex_movil/   las mismas texturas a 512 px (lo que hacía web/build.py hasta ahora para el teléfono) MÁS
  su .webp.
- depto_movil.gltf   igual a depto.gltf, pero con las imágenes apuntando a tex_movil/ en vez de tex/.
- depto_colisiones.json   copia tal cual. Desde el contrato 2.1 el modelo exporta `grupos_luz`,
  `interruptores` y `recintos_etiquetas` (docs/contrato-interaccion.md, secciones 2, 3 y 5); la deducción
  por recinto de js/luces.js y la clase/etiqueta por defecto quedan sólo de respaldo para un JSON viejo.
- Cielos (contrato 2.3, sección 4, bloque 08): `exterior.panoramas` nombra JPG de exports/web/tex/ (tex/cielo_dia.jpg,
  ...) que el visor carga tal cual desde modelo/tex/, en escritorio y en teléfono. Se copian con el resto de tex/ y
  quedan fuera de la conversión: no llevan gemela .webp ni copia en tex_movil/ (nadie las pediría). Si el JSON nombra
  un panorama que no está, construir() se detiene.

Ambos .gltf declaran la extensión estándar EXT_texture_webp (en extensionsUsed, no en extensionsRequired):
cada imagen JPG tiene su gemela .webp, y cada textures[i] que usa una imagen trae
extensions.EXT_texture_webp.source apuntando al índice de la imagen .webp, dejando "source" apuntando al
JPG de siempre. three.js 0.160 (src/vendor/three/jsm/loaders/GLTFLoader.js, EXTENSIONS.EXT_TEXTURE_WEBP)
detecta si el navegador decodifica WebP y elige una u otra por su cuenta; un GLTFLoader más viejo que no
conozca la extensión simplemente la ignora y usa el JPG. Así un navegador con WebP baja bastante menos
peso, y uno sin soporte no nota la diferencia.

A diferencia del visor anterior (exports/depto_tour.html), que armaba un GLB en memoria porque las páginas
publicadas de claude.ai no servían .glb ni .bin, Netlify sí sirve .gltf y .bin sin problema: no hace falta
ningún armado, GLTFLoader los carga directo.

Uso:
    python3 web/tour_modelo.py                          # regenera web/src/tour/modelo/ (rutas por defecto)
    python3 web/tour_modelo.py web/src/tour/modelo       # o hacia una carpeta modelo/ explícita
    import tour_modelo; tour_modelo.construir(destino=...)   # destino = la carpeta modelo/ misma
    import tour_modelo; tour_modelo.generar(destino_tour=...)  # destino_tour/modelo/ (para build.py)

Sin dependencias fuera de Pillow (la misma que usa build.py; trae soporte WebP).
"""
import argparse
import base64
import json
import os
import shutil

from PIL import Image

WEB = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(WEB)
ORIGEN_WEB = os.path.join(RAIZ, "exports", "web")
ORIGEN_COLISIONES = os.path.join(RAIZ, "exports", "depto_colisiones.json")
DESTINO = os.path.join(WEB, "src", "tour", "modelo")
TEX_MOVIL = 512  # px: mismo tamaño que usaba build.py para el teléfono (tour(), hoy retirado de ahí)

# Calidad del WEBP por tipo de mapa (0-100, con el método de compresión más lento/mejor de Pillow). Los
# normales toleran mal la compresión fuerte (aparecen bloques en zonas lisas): 88. Difuso y rugosidad
# valen menos por píxel, 80 no se nota en el contact sheet de revisión.
CALIDAD_WEBP = {"normal": 88, "rough": 80, "diff": 88}
# diff 80 → 88 (2026-09-26): con 80, microcemento conservaba 22 % del detalle fino y cuero 33 %; con 88, 78 %
# y 109 % (varianza del laplaciano contra el JPG de 1024), a cambio de ~1 MB más en escritorio.

# Superficies grandes vistas de cerca (pisos, muros, mesón, puertas): mantienen 1024 px también en el teléfono
# (difuso y normal) y su rugosidad no baja en escritorio; a 512 px el piso de roble quedaba en 213 px/m.
SUPERFICIES_GRANDES = ("piso_roble", "microcemento", "concreto_encofrado", "losa_hormigon", "ladrillo",
                       "roble_ahumado", "oak_veneer_01")


def _es_grande(nombre):
    return any(clave in nombre for clave in SUPERFICIES_GRANDES)

# Los mapas de rugosidad son de muy baja frecuencia (casi un solo tono con algo de ruido): medido sobre
# las 16 texturas _rough del depto, el .webp de escritorio a 1024 px (calidad 80) pesa 933.0 KB en total;
# el mismo lote reescalado a 512 px pesa 236.5 KB (-74.7%, -696.6 KB) sin bloques visibles al acercar la
# cámara. El JPG de respaldo se deja como está (1024 px) por si un navegador viejo lo necesita; sólo el
# .webp de escritorio de rugosidad baja de tamaño.
RUGOSIDAD_ESCRITORIO_WEBP = 512


def _decodificar_bin(ruta_b64, destino_bin):
    with open(ruta_b64, encoding="ascii") as fh:
        texto = fh.read().strip()
    datos = base64.b64decode(texto)
    with open(destino_bin, "wb") as fh:
        fh.write(datos)
    return len(datos)


def _gltf_hacia(gltf, nombre_bin, carpeta_tex):
    """Copia superficial del glTF con buffers[0].uri y las uri de las imágenes reescritas."""
    g = dict(gltf)
    g["buffers"] = [dict(gltf["buffers"][0], uri=nombre_bin)]
    imagenes = []
    for im in gltf.get("images", []):
        im2 = dict(im)
        if im2.get("uri", "").startswith("tex/"):
            im2["uri"] = carpeta_tex + "/" + im2["uri"][len("tex/"):]
        imagenes.append(im2)
    if imagenes:
        g["images"] = imagenes
    return g


def _usos_por_imagen(gltf):
    """índice de imagen -> conjunto de usos ('normal'/'rough'/'diff') según cómo la referencian los
    materiales (normalTexture, metallicRoughnessTexture, baseColorTexture). Sirve de respaldo para
    identificar el tipo de mapa cuando el nombre del archivo no trae _nor/_rough/_diff."""
    texturas = gltf.get("textures", [])

    def origen_de(tex_ref):
        if not tex_ref:
            return None
        idx = tex_ref.get("index")
        if idx is None or idx >= len(texturas):
            return None
        return texturas[idx].get("source")

    usos = {}
    for mat in gltf.get("materials", []):
        pbr = mat.get("pbrMetallicRoughness", {})
        for tex_ref, tipo in (
            (mat.get("normalTexture"), "normal"),
            (pbr.get("metallicRoughnessTexture"), "rough"),
            (pbr.get("baseColorTexture"), "diff"),
        ):
            origen = origen_de(tex_ref)
            if origen is not None:
                usos.setdefault(origen, set()).add(tipo)
    return usos


def _tipos_por_archivo(gltf):
    """nombre de archivo (basename del .jpg) -> tipo de mapa, para elegir la calidad del .webp. Primero
    por el nombre (convención Poly Haven: _nor_gl, _rough, _diff); si no calza, por el uso en los
    materiales del glTF."""
    usos = _usos_por_imagen(gltf)
    tipos = {}
    for i, im in enumerate(gltf.get("images", [])):
        nombre = os.path.basename(im.get("uri", ""))
        n = nombre.lower()
        if "_nor" in n:
            tipo = "normal"
        elif "_rough" in n:
            tipo = "rough"
        elif "_diff" in n:
            tipo = "diff"
        else:
            usos_img = usos.get(i, set())
            tipo = "normal" if "normal" in usos_img else "rough" if "rough" in usos_img else "diff"
        tipos.setdefault(nombre, tipo)
    return tipos


def _gltf_con_webp(gltf):
    """Copia superficial del glTF con una imagen .webp agregada por cada imagen (mismo orden, así que
    imagen N+i es la gemela .webp de la imagen i), textures[].extensions.EXT_texture_webp.source
    apuntando a su índice, y EXT_texture_webp sumado a extensionsUsed (nunca a extensionsRequired: la
    decisión de cuál cargar la toma GLTFLoader según si el navegador decodifica WebP)."""
    g = dict(gltf)
    imagenes = list(gltf.get("images", []))
    n = len(imagenes)
    gemelas = []
    for im in imagenes:
        base, _ext = os.path.splitext(im.get("uri", ""))
        gemelas.append({**im, "uri": base + ".webp", "mimeType": "image/webp"})
    g["images"] = imagenes + gemelas

    texturas = []
    for t in gltf.get("textures", []):
        t2 = dict(t)
        origen = t.get("source")
        if origen is not None:
            ext = dict(t2.get("extensions", {}))
            ext["EXT_texture_webp"] = {"source": n + origen}
            t2["extensions"] = ext
        texturas.append(t2)
    g["textures"] = texturas

    usados = list(gltf.get("extensionsUsed", []))
    if "EXT_texture_webp" not in usados:
        usados.append("EXT_texture_webp")
    g["extensionsUsed"] = usados
    return g


def panoramas(colisiones):
    """Nombres de archivo (dentro de tex/) de los cielos que pide exterior.panoramas (o el exterior.panorama único)."""
    ext = colisiones.get("exterior") or {}
    rutas = list((ext.get("panoramas") or {}).values()) + ([ext["panorama"]] if ext.get("panorama") else [])
    out = set()
    for r in rutas:
        if not r.startswith("tex/") or "/" in r[len("tex/"):]:
            raise SystemExit(f"panorama fuera de tex/: {r!r}")
        out.add(r[len("tex/"):])
    return out


def construir(origen_web=ORIGEN_WEB, origen_colisiones=ORIGEN_COLISIONES, destino=DESTINO):
    if not os.path.isdir(origen_web):
        raise SystemExit(f"falta {origen_web} (exporta primero con build/depto_06_exportar.py)")
    os.makedirs(destino, exist_ok=True)
    with open(origen_colisiones, encoding="utf-8") as fh:
        cielos = panoramas(json.load(fh))
    faltan = sorted(c for c in cielos if not os.path.exists(os.path.join(origen_web, "tex", c)))
    if faltan:
        raise SystemExit(f"faltan los panoramas {faltan} en {origen_web}/tex (fase 6, bloque 08)")

    with open(os.path.join(origen_web, "depto_gltf.json"), encoding="utf-8") as fh:
        gltf = json.load(fh)

    peso_bin = _decodificar_bin(os.path.join(origen_web, "depto_bin.b64.txt"), os.path.join(destino, "depto.bin"))

    # tamaño "antes" (sin EXT_texture_webp): el mismo glTF que armaba esta función previo a este cambio,
    # medido sin escribirlo a disco, sólo para el reporte de pesos antes/después.
    peso_gltf_escritorio_antes = len(json.dumps(_gltf_hacia(gltf, "depto.bin", "tex"), ensure_ascii=False).encode("utf-8"))
    peso_gltf_movil_antes = len(json.dumps(_gltf_hacia(gltf, "depto.bin", "tex_movil"), ensure_ascii=False).encode("utf-8"))

    gltf_webp = _gltf_con_webp(gltf)  # una sola vez: los índices de imagen webp son los mismos para ambas variantes

    escritorio = _gltf_hacia(gltf_webp, "depto.bin", "tex")
    with open(os.path.join(destino, "depto.gltf"), "w", encoding="utf-8") as fh:
        json.dump(escritorio, fh, ensure_ascii=False)

    movil = _gltf_hacia(gltf_webp, "depto.bin", "tex_movil")
    with open(os.path.join(destino, "depto_movil.gltf"), "w", encoding="utf-8") as fh:
        json.dump(movil, fh, ensure_ascii=False)

    tex_dst = os.path.join(destino, "tex")
    if os.path.exists(tex_dst):
        shutil.rmtree(tex_dst)
    shutil.copytree(os.path.join(origen_web, "tex"), tex_dst)

    tex_movil_dst = os.path.join(destino, "tex_movil")
    if os.path.exists(tex_movil_dst):
        shutil.rmtree(tex_movil_dst)
    os.makedirs(tex_movil_dst)

    tipos = _tipos_por_archivo(gltf)
    peso_tex, peso_tex_movil = 0, 0
    peso_tex_webp, peso_tex_movil_webp = 0, 0
    peso_cielos = 0
    for nombre in sorted(os.listdir(tex_dst)):
        ruta = os.path.join(tex_dst, nombre)
        if nombre in cielos:                          # el visor pide el JPG tal cual, en las dos variantes
            peso_cielos += os.path.getsize(ruta)
            continue
        peso_tex += os.path.getsize(ruta)
        tipo = tipos.get(nombre, "diff")
        nombre_webp = os.path.splitext(nombre)[0] + ".webp"

        # .webp de escritorio: mismo tamaño que el JPG, salvo rugosidad (ver RUGOSIDAD_ESCRITORIO_WEBP).
        im_esc = Image.open(ruta)
        if tipo == "rough" and not _es_grande(nombre) and max(im_esc.size) > RUGOSIDAD_ESCRITORIO_WEBP:
            im_esc = im_esc.resize(
                (RUGOSIDAD_ESCRITORIO_WEBP, round(im_esc.height * RUGOSIDAD_ESCRITORIO_WEBP / im_esc.width)),
                Image.LANCZOS,
            )
        im_esc.convert("RGB").save(os.path.join(tex_dst, nombre_webp), "WEBP", quality=CALIDAD_WEBP[tipo], method=6)
        peso_tex_webp += os.path.getsize(os.path.join(tex_dst, nombre_webp))

        # móvil: el JPG a 512 px (como ya hacía) y su .webp a partir de la misma imagen ya reescalada.
        im = Image.open(ruta)
        lado_movil = TEX_MOVIL if (tipo == "rough" or not _es_grande(nombre)) else max(im.size)
        if max(im.size) > lado_movil:
            im = im.resize((lado_movil, round(im.height * lado_movil / im.width)), Image.LANCZOS)
        destino_img = os.path.join(tex_movil_dst, nombre)
        im.convert("RGB").save(destino_img, quality=80, optimize=True)
        peso_tex_movil += os.path.getsize(destino_img)

        im.convert("RGB").save(os.path.join(tex_movil_dst, nombre_webp), "WEBP", quality=CALIDAD_WEBP[tipo], method=6)
        peso_tex_movil_webp += os.path.getsize(os.path.join(tex_movil_dst, nombre_webp))

    shutil.copyfile(origen_colisiones, os.path.join(destino, "depto_colisiones.json"))

    peso_gltf_escritorio_despues = os.path.getsize(os.path.join(destino, "depto.gltf"))
    peso_gltf_movil_despues = os.path.getsize(os.path.join(destino, "depto_movil.gltf"))

    # "antes": lo que bajaba cualquier navegador con el script anterior (gltf sin webp + bin + jpg).
    # "después": lo que baja un navegador CON WebP hoy (gltf con soporte webp, algo más pesado por las
    # imágenes/extensions de más, + bin + sólo los .webp; el JPG queda en disco de respaldo pero un
    # navegador con WebP no lo pide).
    # los cielos los bajan los dos (el visor pide los tres al cargar), con o sin WebP
    antes_escritorio = peso_gltf_escritorio_antes + peso_bin + peso_tex + peso_cielos
    despues_escritorio = peso_gltf_escritorio_despues + peso_bin + peso_tex_webp + peso_cielos
    antes_movil = peso_gltf_movil_antes + peso_bin + peso_tex_movil + peso_cielos
    despues_movil = peso_gltf_movil_despues + peso_bin + peso_tex_movil_webp + peso_cielos

    construir.ultimos_pesos = {
        "escritorio": {"antes": antes_escritorio, "despues": despues_escritorio},
        "movil": {"antes": antes_movil, "despues": despues_movil},
        "cielos": peso_cielos,
    }
    # peso_escritorio/peso_movil: lo que realmente descarga hoy un navegador con soporte WebP (mayoría),
    # que es el número útil para build.py (no cambia su firma: sigue devolviendo 2 valores).
    return despues_escritorio, despues_movil


def generar(destino_tour, origen_web=ORIGEN_WEB, origen_colisiones=ORIGEN_COLISIONES):
    """Conveniencia para build.py: `destino_tour` es la carpeta del tour (p. ej. dist/tour); esta función
    escribe en `destino_tour/modelo/`."""
    return construir(origen_web, origen_colisiones, os.path.join(destino_tour, "modelo"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("destino", nargs="?", default=DESTINO, help="carpeta modelo/ de destino (no la del tour)")
    ap.add_argument("--origen-web", default=ORIGEN_WEB)
    ap.add_argument("--origen-colisiones", default=ORIGEN_COLISIONES)
    a = ap.parse_args()
    e, m = construir(a.origen_web, a.origen_colisiones, a.destino)
    p = construir.ultimos_pesos
    print(f"MODELO_OK {a.destino}")
    print(
        f"  escritorio: antes {p['escritorio']['antes'] / 1e6:.2f} MB (jpg)  ->  "
        f"después {p['escritorio']['despues'] / 1e6:.2f} MB (webp)  "
        f"[-{100 * (1 - p['escritorio']['despues'] / p['escritorio']['antes']):.0f}%]"
    )
    print(
        f"  móvil:      antes {p['movil']['antes'] / 1e6:.2f} MB (jpg)  ->  "
        f"después {p['movil']['despues'] / 1e6:.2f} MB (webp)  "
        f"[-{100 * (1 - p['movil']['despues'] / p['movil']['antes']):.0f}%]"
    )
    assert (e, m) == (p["escritorio"]["despues"], p["movil"]["despues"])
