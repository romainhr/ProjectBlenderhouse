# ADR 0004: Detalle interactivo del modelo, exterior y visor web v3

- **Fecha:** 2026-09-26
- **Estado:** propuesto; se implementó durante la noche por pedido del usuario y queda pendiente de su revisión.
- **Modelo de IA utilizado:** Claude Opus 5.5 (`claude-opus-5-5`) como director; subagentes Claude Sonnet 5 (`claude-sonnet-5`) para el sitio, el visor y las fases de Blender.
- **Revisor humano:** Romain Ange (romain.ange@gosocket.net), pendiente.

## Contexto

El usuario pidió, antes de dormir, más detalle en los objetos (textura de nevera, cajones que se abren, luces cálidas, interruptores por luz y por recinto, paisaje, alfombras, clósets con ropa e interactivos), caminar en el teléfono, una interfaz más clara y con menos "AI slop", y mejor estética y rendimiento. Autorizó Blender, Netlify, Supabase y la descarga de texturas y complementos.

## Decisiones

1. **Contrato modelo ↔ visor v2** (`docs/contrato-interaccion.md`): se amplía el mecanismo de `moviles` existente (props `puerta` / `recorrido_m`) con `clase`, `etiqueta` y `recinto`, en vez de crear un sistema paralelo. Luces con `grupo`, `color` y `ampolleta`; `grupos_luz` e `interruptores` en `depto_colisiones.json`, y `grupo_luz` en los `extras` de los nodos para el raycast.
2. **Visor v3 en `web/src/tour/`**, modular, con three.js 0.160.0 autoalojado. El sitio en Netlify carga el glTF separado directamente (`.gltf` + `.bin` + texturas), sin el base64 que exigía claude.ai. `exports/depto_tour.html` queda como versión del artefacto de claude.ai y ya no se parchea con reemplazos de texto.
3. **Rendimiento en el visor, no en Blender:** unión de mallas estáticas por material al cargar, raycast solo contra nodos interactivos, resolución adaptable y render bajo demanda. El `.blend` mantiene objetos separados y editables.
4. **Tope de triángulos de 150 000 a 200 000**: la unión de mallas reduce las llamadas de dibujo, que eran el costo dominante en teléfonos; el contenido nuevo (ropa, cubiertos, alimentos) es low-poly e instanciado.
5. **Exterior:** cielos "puresky" de Poly Haven (CC0; día `kloofendal_48d_partly_cloudy_puresky`, tarde `qwantani_dusk_2_puresky`, noche `kloppenheim_02_puresky`) más un entorno urbano low-poly modelado por script (calle, edificios vecinos, árboles simples). Se descartaron los HDRI de azotea porque muestran el piso de la azotea bajo la línea de la ventana. La altura del piso (≈ 5.º piso) es un supuesto, no sale del plano.
6. **Plantas de interior:** modelos de Poly Haven de bajo conteo (CC0), no modelados con `bpy`, según CLAUDE.md.
7. **Sitio:** tema claro "luz de tarde" (papel `#F7F4EF`, tinta `#1E1C19`, acento terracota `#A8481F`, Newsreader + Public Sans autoalojadas). Reemplaza el sistema oscuro de Stitch de ADR 0003 (decisión 2).

## Consecuencias

- Iterar el visor ya no rompe el build del sitio por un reemplazo de texto que deja de calzar.
- El artefacto de claude.ai queda en la versión 2 hasta que se republique con el visor nuevo (requiere volver al transporte base64 y a `TextureLoader`).
- Las compuertas de CLAUDE.md se registraron en `docs/noche-2026-09-26.md` en vez de detener el trabajo, por pedido explícito del usuario.

## Adenda 07b (2026-09-26): interiores, luces por grupo e interruptores

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`), constructor de la fase 07b. **Revisor humano:** Romain Ange, pendiente.

Decisiones:

1. **Ropa colgada como en un clóset real:** las prendas cuelgan perpendiculares a la barra (de frente se ven de
   canto), con percha, gancho que abraza la barra, mangas y pliegues que se marcan hacia el ruedo
   (`build/deco_interiores.py`). La separación entre prendas sale de su espesor con mangas y del barrido de su giro,
   así ninguna atraviesa a la vecina. Barra, perchas y prendas de una barra son un solo objeto de varios
   materiales: se tocan por diseño y la prueba de interferencias de la fase 3 sigue valiendo contra puertas,
   fondo, costados y repisas.
2. **Cajones interiores en el vano de una hoja:** en los clósets de repisas los cajones van en la columna que deja
   libre la hoja A corrida; un cajón a todo el ancho chocaría con la hoja que siempre queda delante de la otra mitad.
3. **Colisión de celda en vez de islas:** cada celda de clóset lleva una caja oculta `Depto_Col_Closet_*`
   (`colision: true`) y el contenido va con `colision: false`; el visor no necesita una caja por prenda.
4. **Grupos de luz por luminaria real** (14), con 2700 K general y 3000 K en cocina y baños; los recintos sin luz
   (pasos de los clósets y balcón) reciben luminarias del mismo catálogo industrial (colgante de jaula de cable corto
   y colgante de domo bajo la losa del balcón). Tabla en `docs/contrato-interaccion.md`, sección 2.
5. **Interruptores:** placa de acero negro con teclas de latón (contraste para encontrarlas en el visor), una tecla
   hija por grupo con el origen en su eje de giro y registro propio por tecla. El «comedor» del pedido es el del
   balcón (no hay comedor interior, `docs/deco-industrial.md`), así que el living tiene placa doble techo + balcón y
   el balcón además su placa junto al ventanal (dos puntos de encendido del mismo grupo).
6. **Visor:** el estado de un interruptor sale de sus grupos (no de un estado propio) y las teclas se registran antes
   que su placa y siguen colgando de ella (`web/src/tour/js/carga.js`, `interaccion.js`, funciones puras en
   `luces.js` con pruebas). Sin esto, el primer clic sobre un grupo de techo (que nace encendido) no hacía nada, dos
   interruptores del mismo grupo se desincronizaban y una placa doble prendía sus dos grupos a la vez.

7. **Tintes por vértice:** ropa, zapatos, cajas de tela y alimentos usan cinco materiales base blancos y llevan su
   color en COLOR_0. Con un material por tinte, la fusión por material del visor sumaba una llamada de dibujo por
   color en casi todas las vistas. En el visor, además, los vidrios comparten un material por vidrio de origen.

Consecuencias: 180 064 triángulos visibles (tope 200 000), 73 materiales (antes 78), GLB de 16,3 MB (antes 15,9);
descarga del tour con WebP 9,6 MB en escritorio y 7,1 MB en teléfono (antes 7,5 y 5,0: la geometría nueva va en
las dos). 18 luces en el visor (antes 15). Llamadas de dibujo medidas con `?debug` a 1280 px: vista inicial del
hall 119, living 93, cocina 92, dormitorio 56, paso 48 (antes de los tintes y la caché de vidrios eran 152, 117,
117, 65 y 54; el informe del visor v3, sin el contenido de esta fase, daba 48 a 95). Lo que queda por encima es
sobre todo interruptores y lámparas clicables (nodos sueltos, ~17 en la vista del hall) y cajones de otros
recintos que caen en el frustum detrás de los muros: pide culling por recinto en el visor.
