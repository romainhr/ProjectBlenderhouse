# ADR 0002: Departamento desde un plano de planta y tour virtual web

- **Fecha:** 2026-09-25
- **Estado:** aceptado en la compuerta de la Fase 0 (formato de tour, escala, altura y mobiliario). El formato de exportación web se implementa en la fase 6.
- **Modelo de IA utilizado:** Claude Opus 5.5 (`claude-opus-5-5`), director y constructor. Subagentes Opus 5.5 en dos workflows: `depto-brief-medicion` (8 agentes) y `depto-blockout-verificacion` (3 críticos).
- **Revisor humano:** Romain Ange (romain.ange@gosocket.net)

## Contexto

El usuario entregó un único plano de planta sin cotas (`ref/plano/plano_depto.png`) y pidió un modelo 3D recorrible "como un tour virtual". Las fotos de `ref/depto/` no son de este departamento. La máquina tiene solo CPU y 8 GB de RAM, con Blender 3.6.23.

## Decisiones

1. **Medición:** la escala (0,0190 m/px, ±5 %) se infiere de cuatro familias independientes de elementos estándar. Las coordenadas son centros de línea subpíxel, guardadas en `build/depto_plano.py` como fuente única, y se verifican contra el plano en cada corrida (`build/depto_medicion/verificar_lineas.py`, `tools/compare_plan.py`).
2. **Construcción:** scripts por fase, idempotentes y sellados (`depto_fase01`, `depto_fase02`), ejecutados con `build/depto_run.sh`. Muros por tramos alrededor de los vanos, sin booleanos. Convención: +Y hacia la fachada del balcón y origen en el piso, al centro.
3. **Visualización en vivo:** Blender con interfaz abre una copia del maestro (`tools/watch_blend.py`). Solo los scripts escriben `build/depto.blend`. Esta decisión viene del incidente del 2026-09-25, descrito en el brief.
4. **Tour:** GLB exportado desde Blender más un visor web en primera persona, publicado como página privada en claude.ai. Antes de publicar se vuelve a pedir confirmación, porque el modelo deriva de un plano del usuario. Alternativas descartadas por ahora: panoramas 360° (1 a 2 h de render en CPU, estimado sin medir) y video (varias horas).
5. **Texturas:** Poly Haven (CC0), de 2K como máximo según CLAUDE.md, y solo con aprobación explícita de cada descarga. Para el GLB web se usan de 1K, porque un archivo binario de una página publicada admite 15 MB como máximo.

## Consecuencias

- Toda medida del modelo es trazable a un píxel del plano o a un supuesto declarado en el brief.
- Una cota real del departamento permitiría bajar la incertidumbre de escala de ±5 % a cerca de ±1 %, cambiando una constante.
- El visor web necesitará colisiones y un punto de inicio. Con el mobiliario del plano, el radio de colisión debe ser de 0,20 m como máximo, o algunos muebles bajos no deben tener colisión (hallazgo del crítico de recorrido).

## Adenda: fase 3 (2026-09-25)

- **Modelo de IA utilizado:** Claude Opus 5.5 (`claude-opus-5-5`), más el workflow `depto-formas-verificacion` (3 críticos Opus 5.5).
- **Revisor humano:** Romain Ange; aprobado en la compuerta 3 (2026-09-25).

6. **Sellos encadenados:** `sello(N) = sha1(sello(N−1) + archivos de la fase N)`, siempre recalculado desde el disco (`build/depto_sellos.py`). Una fase que se reejecuta borra los sellos posteriores, y ninguna fase escribe un archivo distinto del maestro. Motivo: con sellos de un solo eslabón, un maestro inconsistente (fase 2 reejecutada sobre uno de fase 3) conservaba un sello de fase 3 válido.
7. **Colisión del tour:** convención `Depto_Col_*` en la colección `Depto_Colision` (oculta y no exportable como visible), más `["colision"]` explícito para las excepciones. La franja de colisión va de 0,10 a 1,80 m. La prueba `build/depto_recorrido.py` corre en el pipeline con radio 0,25 m, más estricto que el ≤ 0,20 m previsto para el visor. En la fase 6 el exportador debe filtrar de forma explícita (en Blender 3.6.23 `export_scene.gltf` exporta por defecto también lo oculto: `use_visible=False`, `use_renderable=False`) y usar `export_extras=True` para llevar estas propiedades.
8. **Piezas animables:** puertas con el origen en la bisagra y la corredera con su recorrido como propiedades, para que el visor web pueda abrir y cerrar sin cambiar la geometría.
9. **UV de mundo:** proyección de caja en metros en todas las mallas, requisito para que las texturas lleguen al GLB (glTF sólo transporta texturas con `TEXCOORD_0`).

## Adenda: compuerta 4 (2026-09-25)

- **Modelo de IA utilizado:** Claude Opus 5.5. **Revisor humano:** Romain Ange.

10. **Iluminación del tour:** en tiempo real en el visor web (luz de día direccional, luz ambiente y una luz puntual por recinto), sin hornear la iluminación en texturas. Alternativa descartada: horneado con Cycles en CPU, porque tarda horas (estimado, sin medir) y aumenta el peso del GLB, que tiene un límite de 15 MB por archivo en la página publicada. Consecuencia: los materiales de la fase 5 deben verse bien con PBR estándar de glTF (Principled BSDF con color, rugosidad y normal), y las luces de Blender sirven sólo para la revisión con Eevee; el visor define las suyas.

## Adenda: fase 5 (2026-09-25)

- **Modelo de IA utilizado:** Claude Opus 5.5. **Revisor humano:** Romain Ange (compuerta 5).

11. **Materiales compatibles con glTF por construcción:** la fase 2 asigna por cara materiales de acabado (según el recinto al que mira cada cara) y la fase 5 sólo los mejora en su datablock. Así, ninguna fase modifica mallas de otra. La fase 5 prueba que cada material use sólo nodos que el exportador glTF de Blender 3.6 traduce. La cubierta de granito es una imagen generada, porque un procedural no se exporta.
12. **Imágenes del GLB en JPEG:** con el formato automático, el exportador genera PNG sin pérdida para rugosidad y metálico, y el GLB de prueba pesó 17,5 MB. En JPEG pesó 9,8 MB, bajo el límite de 15 MB por archivo de la página publicada.

## Adenda: versión 2, decoración industrial (2026-09-25)

- **Modelo de IA utilizado:** Claude Opus 5.5 (director e integrador), más el workflow `depto-deco-industrial` (5 agentes Opus 5.5: texturas, living, dormitorios, cocina y baños, luminarias y objetos). **Revisor humano:** Romain Ange (pidió el rediseño; revisa en la compuerta de la versión 2).

13. **Creación desde cero:** el usuario pidió decoración industrial moderna minimalista, creando lo que falte. No se descarga nada nuevo. Las texturas nuevas se generan por código (`build/deco_texturas.py`, numpy dentro de Blender, repetibles y a escala física) y los muebles, luminarias y objetos se modelan por código en módulos de piezas (`build/deco_*.py`) que siguen un contrato común (`docs/deco-industrial.md`: coordenadas locales, frente hacia −Y, materiales por nombre). La fase 4 los ubica. La versión 1 queda en `archivo/v1_neutro/`.
14. **Acabados por cara, mejorados en su datablock:** se mantiene la decisión 11. La fase 2 asigna los acabados nuevos (microcemento, tablas de roble, baldosa hexagonal, ladrillo de acento) y la fase 5 los texturiza con `build/deco_paleta.py`, sin tocar mallas de otras fases.
15. **Texturas en la página publicada:** con la política de seguridad de la página, el `ImageBitmapLoader` de three.js (que hace `fetch` de un `blob:`) falla y el modelo quedaba sin texturas. Se reprodujo en local con `tools/servidor_csp.py`. El visor usa ahora un plugin de GLTFLoader que decodifica con `<img>` (TextureLoader).
16. **Transporte web:** las páginas no sirven `.glb` ni `.bin`, y un solo archivo de texto admite hasta 16 MB. El modelo se publica como glTF separado: `depto_gltf.json`, `depto_bin.b64.txt` (sólo la geometría) y `tex/*.jpg` (imágenes sin recodificar). El visor arma el GLB en memoria. La fase 6 hace el mismo armado en Python y lo reimporta para validarlo. Límite de versión: 64 MB y 255 archivos.

## Adenda: versión 2, segunda tanda de piezas e instancias (2026-09-26)

- **Modelo de IA utilizado:** Claude Opus 5.5 (director e integrador), más dos agentes Opus 5.5 que modelaron
  `build/deco_comedor.py` y `build/deco_hall.py`. **Revisor humano:** Romain Ange (pidió «seguir con el resto de las
  piezas y instancias»; revisa en la compuerta de la versión 2).

17. **Instancias por huella de malla:** después de ubicar las piezas, la fase 4 calcula una huella de cada malla
    (vértices, caras, aristas, suavizado, UV y materiales) y hace que las idénticas compartan un datablock, como un
    duplicado enlazado. No hace falta que cada pieza sepa si se repite, y comparte también partes iguales de piezas
    distintas (las dos camas sólo difieren en el cabecero y los cojines). El exportador glTF de Blender 3.6 conserva
    la malla compartida (medido: 263 objetos sobre 196 mallas). Alternativa descartada: una caché por llamada
    (función + parámetros) en el colocador, que no detecta partes iguales de piezas distintas. Requisito que se
    agrega al contrato: las piezas deben ser deterministas (mismos parámetros, misma malla; un agente encontró y
    corrigió un recorrido de `set` de bmesh que no lo era).
18. **Presupuesto de triángulos:** se mantiene el tope de 150 000 para la escena. Para hacer lugar a la segunda
    tanda, la cama recibe `resolucion=0.7` (de 20 000 a 13 100 triángulos por cama, sin diferencia visible en la
    revisión lado a lado). No se cuentan las instancias una sola vez: el costo de dibujo es por objeto.
19. **Sin comedor interior:** el espacio libre entre living, cocina y hall es circulación y el plano no dibuja
    comedor; una mesa de 0,80 con dos sillas dejaba 0,6 a 0,7 m frente a la cocina o cortaba el paso del hall al
    living. El comedor para dos va al balcón (mesa y sillas bistró). La mesa y la silla de comedor quedan modeladas,
    fuera del departamento.

## Adenda: visor v3 (`web/src/tour/`), trabajo nocturno (2026-09-26)

- **Modelo de IA utilizado:** Claude Sonnet 5 (`claude-sonnet-5`), trabajando de noche sin compuertas (autorizado por
  Romain Ange antes de dormir; ver `docs/noche-2026-09-26.md`). **Revisor humano pendiente:** Romain Ange (revisa al
  despertar; nada de esto se publicó en Netlify sin su aprobación).

20. **three.js autoalojado, sin `import map`:** se reemplaza el `exports/depto_tour.html` de un solo archivo (jsDelivr,
    armado de GLB en memoria) por un visor modular en `web/src/tour/js/*.js`. `web/src/vendor/three/` trae
    `three.module.min.js`, `jsm/loaders/GLTFLoader.js` y `jsm/utils/BufferGeometryUtils.js` (npm pack 0.160.0), con
    sus imports reescritos a rutas relativas. Sin `<script type="importmap">` ni ningún script en línea: la CSP del
    tour queda en `script-src 'self'` sin hashes (acordado con la sesión dueña de `web/build.py`), más estricta que la
    del artefacto anterior.
21. **Transporte del modelo, ahora directo:** `web/tour_modelo.py` decodifica `depto_bin.b64.txt` a `depto.bin` y
    reescribe `depto_gltf.json` como `depto.gltf`/`depto_movil.gltf` (con y sin `tex_movil/`). Netlify sirve `.gltf` y
    `.bin` sin problema (a diferencia de una página de claude.ai): el visor usa `GLTFLoader.load()` normal, sin el
    armado de GLB en memoria que hacía `exports/depto_tour.html`.
22. **Grupos de luz deducidos, no autorados:** el contrato de interacción v2 (`docs/contrato-interaccion.md`) define
    `grupos_luz[]`, pero `depto_colisiones.json` todavía no los trae (lo exporta la fase de Blender, en curso la misma
    noche). `js/luces.js` deduce un grupo por recinto (el más cercano en XZ a cada luz puntual) cuando faltan; si el
    JSON llega con `grupos_luz` completos, se respetan tal cual. Mismo criterio para `clase`/`etiqueta` de `moviles[]`
    (si faltan, texto genérico por `tipo`) y para `interruptores[]` (si falta la lista, se buscan nodos con
    `userData.grupo_luz` en los `extras` del glTF).
23. **Estado inicial de las luces según el momento del día:** el encargo pide que de noche empiecen encendidas; no
    dice qué pasa de día o tarde. Se decidió apagadas en Día/Tarde y encendidas en Noche (para todos los grupos, al
    elegir el momento), sin recordar el estado manual de una sesión a otra. Alternativa descartada: recordar el
    estado por grupo entre momentos, más fiel a lo que dejó el usuario pero no pedida explícitamente y más difícil de
    razonar para quien prueba el visor.
24. **Sin mapa de entorno (PMREM):** el visor anterior generaba un `RoomEnvironment` para reflejos; se omite en v3 por
    rendimiento (menos memoria y un renderizado inicial menos) y para no sumar otro archivo vendorizado. Los metales y
    vidrios se ven algo menos reflectantes; se puede reincorporar si el rendimiento en el teléfono lo permite.
25. **Fusión de mallas estáticas por material:** excluye móviles (y sus hijos), interruptores/lámparas
    (`userData.grupo_luz`) y ampolletas, con la transformación de mundo horneada en la geometría
    (`BufferGeometryUtils.mergeGeometries`). Medido en el navegador integrado: 48 a 95 llamadas de dibujo según el
    punto de vista (la mayoría bajo 90; el peor caso mide dos puertas abiertas mostrando tres recintos a la vez).
26. **Render bajo demanda + resolución adaptable:** no se llama a `renderer.render()` si no hay entrada activa,
    piezas en movimiento ni fundidos de luz en curso. `pixelRatio` baja a ×0,75 si el cuadro promedia más de 24 ms
    sostenidos. Techo inicial: 1,5 en escritorio, 1,25 en táctil.
27. **Caminar automático al tocar el piso (táctil):** sin `pathfinding`; es una línea recta con la misma colisión y
    deslizamiento del caminar manual (`colision.mover`), así que se detiene limpio contra una pared en vez de
    atravesarla, pero no rodea obstáculos. Suficiente para tocar un punto visible del mismo recinto; cruzar a otro
    recinto por un pasillo angosto puede requerir un segundo toque.
