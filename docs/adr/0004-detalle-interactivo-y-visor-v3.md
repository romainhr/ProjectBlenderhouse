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
las dos). 18 luces en el modelo (17 puntuales y el sol; antes 15) [corrección de la ronda 2: en el visor eran 26
luces de three.js desde la ronda 1 (17 PointLight, 8 SpotLight y el sol) más el ambiente; ahora 19 más el
ambiente: 18 lámparas, 8 de ellas SpotLight, y el sol]. Llamadas de dibujo medidas con `?debug` a 1280 px: vista inicial del
hall 119, living 93, cocina 92, dormitorio 56, paso 48 (antes de los tintes y la caché de vidrios eran 152, 117,
117, 65 y 54; el informe del visor v3, sin el contenido de esta fase, daba 48 a 95). Lo que queda por encima es
sobre todo interruptores y lámparas clicables (nodos sueltos, ~17 en la vista del hall) y cajones de otros
recintos que caen en el frustum detrás de los muros: pide culling por recinto en el visor.

## Adenda 07b, corrección de la ronda 1 (2026-09-26): contrato 2.1

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`), corrector de la fase 07b. **Revisor humano:** Romain Ange,
  pendiente.

Decisiones (cambian el contrato de interacción, que pasa a la versión 2.1):

1. **Color de las luces por temperatura:** `grupos_luz[].kelvin` (2700 o 3000) y `luces[].color` en sRGB lineal
   calculado desde esa temperatura (`build/depto_color.py`: Planck contra CIE 1931, ajuste de Wyman 2013). El triple
   del encargo, (1.0, 0.72, 0.42), es el sRGB codificado de ~3000 K; tomado como lineal, en Blender y en el visor,
   daba ~4200 K. Se prefirió la temperatura pedida al número aproximado que la acompañaba.
2. **Cajones atados a su hoja** (`moviles[].depende_de` y `bloquea`): un cajón de clóset sólo abre con su hoja A
   corrida y la B cerrada; mover una hoja cierra antes sus cajones. Sin esto, en el visor una hoja atravesaba el
   frente de un cajón abierto (0,29 m por delante de su plano).
3. **Momento del día y `encendido`:** el momento decide si hay luces (tarde y noche sí, día no) y `encendido` qué
   grupos prende. Antes el momento inicial prendía los 14 grupos, contra lo que decía el contrato.
4. **Luces con pantalla en el visor** (`luces[].cono_deg` y `direccion`, sólo domos y focos): el visor no calcula
   sombras; una puntual dentro de un domo cerrado iluminaba el cielo ~20 veces más que el piso (inverso del
   cuadrado: 0,42 m al cielo contra 1,98 m al piso). Se reparte en un foco (85 %) y una puntual (15 %). En Blender
   siguen siendo puntuales: la pantalla hace la sombra.
5. **Interruptor de la cocina** en el remate del tabique T3, a la entrada desde el living: en el canto del tabique
   cocina/hall la puerta de la nevera (bisagra al sur, 100°) pasaba a 4-8 cm de la placa y la tapaba desde la cocina.
   Mover la bisagra al norte no sirve (la torre del horno está pegada) y limitar la puerta a 90° dejaba la manilla a
   4 cm del canto.
6. **Renders de revisión de día** con el HDRI de Poly Haven (`kloofendal_48d_partly_cloudy_puresky`) desaturado, luz
   rebotada horneada también de día, sondas planas en los espejos y un cubemap por baño (`tools/render_07b.py`). Son
   supuestos de revisión y no van al GLB.

## Adenda 07b, corrección de la ronda 2 (2026-09-26)

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`), corrector de la fase 07b (ronda 2). **Revisor humano:**
  Romain Ange, pendiente.

Decisiones:

1. **Dos lámparas de velador en el dormitorio principal:** el grupo `dorm1_velador` se reemplaza por
   `dorm1_velador_izq` y `dorm1_velador_der` (mirando la cabecera desde los pies de la cama, como en el segundo
   dormitorio), y los nodos pasan a `Depto_Mueble_D1_LamparaMesa{O,E}_*`. Es un cambio de ids del contrato: un visor
   con estado guardado por id de grupo lo pierde para ese grupo.
2. **`"contrato": "2.1"`** en `depto_colisiones.json`; `"version"` sigue en 2 y es la versión mayor.
3. **Materiales del GLB:** el roble de puertas y clósets pierde el mapa de rugosidad (0,55 constante) y la melamina
   blanca sube de 0,35 a 0,55 de rugosidad. El Specular se deja en 0,5 a propósito: otro valor exporta
   `KHR_materials_specular` y three.js convierte el material en `MeshPhysicalMaterial`, más caro por fragmento.
4. **Render de revisión** (`tools/render_07b.py`, no va al GLB ni al visor): vidrio propio (Transparent + Glossy por
   Fresnel, sin caras traseras ni sombra), un cubemap por recinto, suelo neutro oscuro bajo el horizonte del mundo, luz
   rebotada horneada con las lámparas de la vista también de día (cada horneado tarda 4-6 min en esta CPU, así que
   las vistas comparten horneado) y adaptación cromática parcial de la cámara (ASC-CDL en el compositor) en las vistas
   con lámparas. El color de las luces no cambia: sigue en 2700 K y 3000 K.
5. **Visor: un solo foco por domo o foco del riel**, sin la puntual complementaria del 15 % (decisión 4 de la
   ronda 1). Medido con `window.__tour.medirCuadro()` (nuevo, sólo con `?debug`), de noche a 1280 × 800 en la vista
   inicial, en una Intel HD Graphics 4000: 27 luces, 48 ms por cuadro; 19 luces, 37,5 ms; sólo el sol, 15 ms. En
   otra sesión, con otra vista, 62,8 contra 49,4 ms, y dejando sólo las luces más cercanas a la cámara: 11 luces
   35,8 ms y 7 luces 28,8 ms. El cielo de la vista inicial baja ~13 % de luminancia. Falta medir en un teléfono. El
   paso siguiente, si hace falta, es un conjunto fijo de ~10 luces que se reasignan a las del recinto actual y los
   contiguos al cambiar de recinto: con un número fijo de luces three.js no recompila los shaders.
6. **Diseño:** la mesa bistró del balcón pasa a acero pintado al horno (`Depto_Mat_AceroPintado`, dieléctrico; 75
   materiales), porque con acero pavonado el colgante no dejaba charco en la cubierta. El tercer foco del riel del
   hall ilumina la puerta de entrada en vez del reloj.

## Adenda 07c (2026-09-26): respetar el plano

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`), constructor del bloque 07c. **Revisor humano:** Romain Ange,
  pendiente.

Decisiones:

1. **El plano manda sobre la decoración v2 en la cocina:** vuelven los muebles altos del tramo norte (discontinua
   `ALTOS_Y`, de T3 a la esquina, sobre el anafe) y se quitan las repisas abiertas y la campana de chimenea de
   `docs/deco-industrial.md`. La campana pasa a ser telescópica, integrada en el módulo de 0,60 m sobre el anafe
   (su cara inferior queda a 0,59 m del vidrio; el valor que piden los fabricantes no está verificado).
2. **Regla de bisagras de mueble** (contrato, sección 1): el eje de giro va en la arista de la cara vista y la bisagra
   del lado sin muro, torre ni esquina; dos hojas vecinas no comparten la junta de la bisagra. Lo prueba la fase 6
   (`prueba_aperturas`), que abre cada móvil como lo permite el contrato. Es un cambio del modelo, no del esquema
   (sigue `"contrato": "2.1"`): cambian el `posicion`/`cajas_locales` de las hojas y los nombres de las hojas altas
   (`Depto_Mueble_Cocina_PuertaAlta{N1..N3,E1..E3}` en vez de `PuertaAlta1..4`).
3. **Nevera medida en el plano:** 0,656 m de ancho y el frente en la discontinua; el fondo sigue inferido (0,58 m).
   La bisagra pasa al norte para que la hoja abierta no ocupe la boca entre el hall y la cocina, y sale de la lista de
   excepciones de la prueba de recorrido.
4. **Tope de la puerta de entrada a 84°:** a 90° entraba en el reloj del hall.
