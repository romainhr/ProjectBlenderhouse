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
2. **Regla de bisagras de mueble** (contrato, sección 1; redacción corregida en la ronda 1): el eje de giro va en la
   arista de la cara vista y la hoja cuelga de un costado, divisor o montante. La bisagra va del lado libre cuando se
   puede; si del lado de la bisagra hay muro, torre o esquina, se agrega un rellenador (`ALTOS_RELLENO`,
   `RELLENO_ESQUINA`) o se limita el ángulo (`ANGULO_MUEBLE_TORRE`, `ANGULO_TORRE`). Excepciones con nombre:
   `PuertaAltaN1`, `PuertaAltaE3`, `PuertaLavaplatos2` y las dos puertas de la torre. Dos hojas vecinas no comparten
   la junta de la bisagra. Lo prueba la fase 6
   (`prueba_aperturas`), que abre cada móvil como lo permite el contrato. Es un cambio del modelo, no del esquema
   (sigue `"contrato": "2.1"`): cambian el `posicion`/`cajas_locales` de las hojas y los nombres de las hojas altas
   (`Depto_Mueble_Cocina_PuertaAlta{N1..N3,E1..E3}` en vez de `PuertaAlta1..4`).
3. **Nevera medida en el plano:** 0,656 m de ancho y el frente en la discontinua; el fondo sigue inferido (0,58 m).
   La bisagra pasa al norte para que la hoja abierta no ocupe la boca entre el hall y la cocina, y sale de la lista de
   excepciones de la prueba de recorrido.
4. **Tope de la puerta de entrada** (corregido en la ronda 1): 87°, no 84°. El reloj del hall sale del barrido de la
   hoja (va a la cara sur de T_COC_S) y deja de ser la causa; lo que queda es la manilla de palanca, que sale 6,2 cm de
   la cara de la hoja: a 90° entra 15 mm en T9 y a 88°, 1 mm. El plano dibuja la hoja a 90°: la desviación de −3° está
   en la tabla de la bitácora.

### Ronda 1 de la corrección 07c (2026-09-26)

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`), corrector del bloque 07c. **Revisor humano:** Romain Ange,
  pendiente.

5. **Muebles de cocina como muebles:** los altos llevan un costado o divisor de 18 mm en cada canto con bisagra y en
   cada junta, con el piso, la repisa y el techo partidos por módulo; el mueble del lavaplatos es un cascarón hueco con
   montante en la junta (un divisor de fondo completo cortaría el sifón), sifón y contenido; la torre de horno y
   despensa (inferida) es un cascarón con zócalo, horno empotrado y dos puertas interactivas con la bisagra al sur y
   tope de 80° (al norte chocaban con los tiradores de `PuertaLavaplatos2` o `PuertaAltaE3`; a 90° con la nevera
   abierta). Pasan de 35 a 37 móviles; el esquema del contrato no cambia.
6. **Luz de la cocina:** los dos colgantes de jaula de la v2 se reemplazan por un riel de tres focos (como el del
   hall) y una luz lineal bajo los altos en tres tramos, en el mismo grupo `cocina_techo`. Con los altos de vuelta,
   los colgantes quedaban a su altura y a 0,56 m de sus hojas. El visor pasa de 18 a 22 luces puntuales: por la
   medición de la decisión 5 de la ronda 2 de la 07b (~1,3 ms por luz en una GPU integrada) son ~5 ms más por cuadro;
   no se midió.
7. **Acero cepillado:** sólo el rayado submilimétrico (paso alto de 0,5 mm) y una nube suave; la visera de la campana
   y el marco del horno llevan el UV girado 90° para que el cepillado corra a lo largo de la pieza
   (`depto_geom.uv_mundo(girar=True)`).

### Ronda 2 de la corrección 07c (2026-09-26)

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`), corrector del bloque 07c. **Revisor humano:** Romain Ange,
  pendiente.

8. **Torre como despensa de dos hojas por nivel:** el símbolo «<» del plano se lee como dos hojas de ≈0,29 m con las
   bisagras en los extremos norte y sur, que se encuentran al centro (243,1 px). Sale el horno de la ronda 1: la torre
   de 0,58 m (0,544 m libres) no admite un horno empotrable comercial. Cuatro hojas (`PuertaTorre{Baja,Alta}{N,S}`,
   junta de niveles a 1,50 m) en vez de dos: pasan de 37 a 39 móviles. Las del norte comparten la junta con
   `PuertaLavaplatos2` y `PuertaAltaE3`, que quedan con tope a 90° y 80°. Queda para el usuario si el horno va bajo el
   anafe (el sitio lo promete; habría que reordenar los módulos base para dejar uno de 0,60).
9. **Prueba del recorrido de cada móvil** (`prueba_giros`, fase 6): cada pieza se mueve cada 2° o 2 cm contra los
   móviles de su recinto, abiertos y cerrados, en los estados que el visor permite durante ese movimiento
   (`bloqueos.js`). La prueba de estados finales no veía que `PuertaLavaplatos1` cruzaba 18 mm el cajón 3 abierto a
   mitad de su giro; ahora esa hoja lo nombra en `bloquea`.
10. **Contrato 2.2:** `enciende` en los móviles y `movil` en los grupos (la luz interior de la nevera, 4 W a 5000 K,
    que la puerta prende al abrirse; sin interruptor ni fila en el panel), `alcance_m` en las luces (el visor no
    calcula sombras: la de la nevera se corta a 0,9 m) y `entornos[]` (sección 6): un equirectangular de la cocina
    renderizado en Cycles en la fase 6 que el visor usa como `envMap` del acero de la cocina en vez del
    `RoomEnvironment` genérico, que dibujaba sus cajas en la nevera. Se prefirió a un cubemap en tiempo real (una
    pasada de render más por cuadro) y a hornear el reflejo en la textura (fijo, no cambia con el punto de vista).
11. **Revisión sin adaptación cromática:** los renders de revisión dejan de aplicar la pendiente fija de las vistas
    con lámparas, que el visor no tiene; la luz lineal bajo los altos es un foco hacia abajo también en Blender.

## Adenda 08 (2026-09-26): exterior y paisaje

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`), constructor del bloque 08. **Revisor humano:** Romain Ange,
  pendiente.

12. **Paisaje modelado por script en una fase propia, la 08, entre la 5 y la exportación.** `build/depto_08_exterior.py`
    arma la colección `Depto_Exterior` (prefijo `Depto_Ext_`) desde constantes con origen. Incluye la fachada del
    edificio propio (8 pisos, tres deptos por piso, balcones apilados sobre los ejes medidos del nuestro), la calle con
    su cruce, siete vecinos con fachadas de textura propia, un barrio intermedio de manzanas y 21 árboles de calle de
    pocos polígonos. En la cadena de sellos, la 08 va después de la 05 y antes de la 06 (`ORDEN` en
    `build/depto_sellos.py`), así que exportar siempre la reconstruye. El exterior no toca el plano: salvo la fachada,
    el balcón y los vanos propios, todo es diseño o inferido (brief, sección «Bloque 08»).
13. **Texturas generadas por código, no descargadas:** cuatro atlas de fachada de 8 × 8 bahías-piso, con emisión de las
    ventanas encendidas sorteada junto con sus cortinas; más ventanas propias, calle, pasto, pintura, siluetas y una
    paleta de colores planos (`build/ext_texturas.py`). Se evitó la transparencia en las siluetas lejanas: la
    exportación pasa todas las imágenes a JPEG. Por eso son tarjetas con el contorno en la geometría.
14. **Contrato 2.3 (sección 4):** `exterior` con un panorama por momento, `rotacion_deg` (medido: lleva el sol del HDR de
    día al de la escena), `suelo_y` y `emision` por momento. Los materiales `Depto_Ext_Mat_*` traen `exterior: true`
    en los extras y el visor los dibuja como fondo barato: `MeshBasicMaterial` sin luces, sombreado por vértice
    calculado al cargar, emisión y bruma sumadas en el shader. Van en un grupo aparte del raycast del piso. Se
    descartó dejarles un material con luces: sin sombras, las puntuales del depto alumbrarían las fachadas vecinas, y
    cada fragmento pagaría las 24 luces. La emisión se exporta con su valor de noche y el visor la escala. El maestro
    la deja en 0 para que los renders de día no tengan ventanas encendidas.
15. **Panorama girado en un canvas:** three r160 no tiene `scene.backgroundRotation`. El visor corre la imagen al
    cargarla (`prepararPanorama`) y mide ahí el color del horizonte para la bruma de las siluetas.
16. **Consecuencias:** la escena queda en 197 902 triángulos, a 2 098 del tope de 200 000. El próximo contenido del
    interior tendrá que ahorrar o pedir que se suba el tope. El entorno local de la cocina (sección 6) ahora ve el
    exterior por las ventanas. Su escala de normalización pasó de 7,8 a 8,7 (luces) y de 19,6 a 30,9 (día), porque los
    vecinos tapan parte del cielo. La intensidad `entornoLocal` del visor no se recalibró.

## Adenda 08, corrección de la ronda 1 (2026-09-27): contrato 2.4

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`), corrector del bloque 08. **Revisor humano:** Romain Ange,
  pendiente.

17. **Un sol por momento, el de su panorama.** La luz de la tarde tenía la elevación de 35° de la fase 5 bajo un cielo
    con el sol a 12°. Ahora cada momento orienta el sol con la elevación medida en su HDR: 48,0° de día, 12,1° de tarde
    y 17,1° para la luna. El azimut es el que ya alineó el giro. Esto vale en `tools/render_08.py`, en el sol del visor
    y en el sombreado por vértice del exterior, que se rehace al cambiar de momento. La fase 5 conserva sus 35° para
    los demás renders. La tarde de Blender baja la luz del cielo a 0,4, medido para que el hormigón en sombra quede a
    0,4-0,6 del de día.
18. **Curva de tono Filmic en el exterior del visor.** Los renders de revisión salen con Filmic, y con ACES el mismo
    valor de escena daba otra imagen: sombras más oscuras y claros más claros. Por eso ningún sombreado podía igualar a
    la vez el ladrillo y el hormigón. Los materiales de fondo aplican la curva Filmic de Blender, medida en Blender por
    `tools/curva_filmic.py` y guardada en `web/src/tour/js/filmic.js`. El resto del visor sigue con ACES. Se descartó
    compensar con un tinte por material, porque no se sostiene al cambiar de momento.
19. **Vidrio y mancha de luz sin luces nuevas.** El muro cortina y las ventanas propias reflejan el panorama del momento
    (`envMap` en `MeshBasicMaterial`), con la máscara de un mapa de rugosidad propio. La mancha de luz de las
    luminarias es una malla con una textura propia que se suma con mezcla aditiva. En Blender, en cambio, alumbran seis
    focos sin sombra. Se descartó darle al visor seis luces puntuales más: cada fragmento del depto las pagaría, y ya
    hay 24.
20. **La escala del entorno local se usa.** El visor multiplica la intensidad del reflejo de la cocina por
    escala_de_referencia / `entornos[].escala`. Un render nuevo del entorno ya no mueve la calibración (sección 6 del
    contrato).

## Adenda 08, corrección de la ronda 2 (2026-09-27): contrato 2.5

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`), corrector del bloque 08. **Revisor humano:** Romain Ange,
  pendiente.

21. **El sol y el cielo de cada momento salen del modelo (contrato 2.5).** La fase 6 exporta `exterior.sol` (azimut ya
    girado, elevación y el vector hacia el sol en glTF) desde lo que mide la fase 08 en cada HDR; el visor lo usa para el
    sol del depto y el sombreado del exterior, y `MOMENTOS[].sol.elevacion` queda sólo de respaldo, con una prueba que
    lo compara con el JSON. Los cielos de día y de tarde dejan de ser el JPG de Poly Haven, que traía su propio tono: la
    fase 6 los hornea desde el HDR con la vista Filmic de Blender y la fuerza del cielo de cámara de los renders
    (`cielo_camara` de la fase 08, que `tools/render_08.py` verifica), con el detalle de las nubes del JPG de 2048, y el
    visor los dibuja con intensidad 1 (`panoramas_intensidad`). La noche sigue con el JPG: su cielo ya coincidía y en
    pantalla es tan oscuro que en 8 bits quedaría en escalones. Se descartó desaturar el JPG en el visor: arreglaba el
    promedio, no el tono de cada región del cielo. De paso, la bruma de las siluetas deja el ACES que se le aplicaba:
    three r160 no aplica tone mapping a un fondo sRGB.
22. **La franja del depto lleva la piel del edificio.** La fase 08 tiende una piel con la pintura exterior a 1 cm de
    los muros propios (5.º piso de la columna 0, de −0,15 a 2,55 m, con los vanos medidos recortados), y los renders de
    revisión acotan el volumen de irradiancia a la cara interior de los muros perimetrales (distancia de influencia
    0,10 m, menor que el muro más delgado). Se descartó que la fase 08 cambiara el material de las caras exteriores de
    los muros de la fase 2: una fase modificaría objetos de otra y perdería la idempotencia por fase.
23. **La línea central de las calles es geometría** (96 triángulos) que salta el cruce y los pasos de cebra, con una
    prueba en la fase 08. Con un período de 12 m en la textura, ninguna fase libraba a la vez el cruce y las dos cebras.
24. **Vidrio.** En el exterior, el reflejo del panorama se suma al difuso (`AddOperation`, como el especular del
    Principled), la enjuta del muro cortina y las cortinas detrás del vidrio tienen su rugosidad propia, el vidrio de
    las barandas refleja parejo sin sombreado por vértice (`exterior_vidrio.uniforme`) y lo transparente usa
    α' = 1 − (1 − α)^1,35, porque three.js mezcla sobre el lienzo ya codificado en sRGB y Blender en lineal. En el depto,
    el vidrio de ventanas y barandas (`Depto_Mat_Vidrio` en nodos `Depto_Ventana_*` y `Depto_Balcon_*`) no suma luz
    difusa: refleja el panorama y deja pasar el 92 % de lo de atrás, con una sola cara por paño. Las botellas, repisas,
    vajilla y mamparas del mismo material siguen como antes: reflejar el cielo dentro de la nevera no tiene sentido.
25. **Un objetivo de tono único para el interior de tarde:** la pared blanca bajo la luz de techo con R/B lineal ≤ 2,5.
    Blender, que no adapta, la deja mostaza (≈ 5,7 con 2700 K); la vista `dormitorio_ventana_adaptada` muestra el
    objetivo con una adaptación de cámara (pendiente ASC-CDL antes de Filmic) y el visor se recalibró para cumplirlo con
    la luminancia de Blender (pared / cielo y piso del living). No se cambió la temperatura de las lámparas del modelo:
    con 3000 K la pared seguiría en R/B ≈ 4,4 y es una decisión de diseño pendiente desde la 07b. Las vistas
    interiores de Blender llevan ahora las lámparas a +0,6 EV con la cámara a 0 EV, en vez de la cámara a +0,6 EV con
    sólo el cielo compensado: así lo que se ve por la ventana tiene la exposición de las vistas del balcón y se puede
    comparar con el visor, que no cambia la exposición del exterior desde adentro.
26. **Entorno local de la cocina con el mundo de los renders de revisión** (el HDR de día desaturado), no con el cielo
    Nishita del maestro, y la variante de día desaturada a 0,2 al cargarla: el frente del freezer salía azulado. La
    escala de referencia se volvió a medir con este render.

## Adenda 09 (2026-09-27): alfombras, cortinas y plantas

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`), constructor del bloque 09. **Revisor humano:** Romain Ange,
  pendiente.

27. **Textiles por script en la fase 4.** `build/deco_textiles.py` arma las alfombras (losa sin cara inferior con el
    canto en cuarto de círculo y flecos de tiras planas) y las cortinas (paños con sección senoidal recogidos en una
    barra negra con anillas, soportes y terminales). La fase 4 las ubica y las prueba: espesor de 1 a 1,5 cm, sin
    colisión, ninguna dentro de un mueble y, bajo el barrido de una hoja, 3 mm libres hasta su canto. Las texturas son
    propias (`bereber`, `kilim`, `camino` y `algodon` en `build/deco_texturas.py`, 1024 px y periódicas). El kilim, que
    tiene guarda, es la alfombra entera con UV 0-1 (como los cuadros); las demás se repiten.
28. **Holgura de 2 cm bajo las hojas abatibles interiores** (`LUZ_PISO_ABATIBLE` en la fase 3). Con 1 cm, ninguna
    alfombra de 1-1,5 cm podía quedar bajo el barrido de las puertas de los dormitorios ni de los baños, que abren
    sobre la zona de los pies de la cama y sobre el frente de la tina. La entrada conserva 1 cm y el camino queda fuera
    de su barrido. Se descartó dejar las alfombras fuera de los barridos: en el dormitorio principal la del pie de la
    cama quedaba de 2,0 m de ancho y los pisos de baño no cabían frente a la tina.
29. **Plantas de Poly Haven importadas, no modeladas** (CLAUDE.md). `build/deco_plantas.py` importa el glTF con
    `bpy.ops.import_scene.gltf`, toma una variante, la decima con Decimate (colapso) hasta su tope (≤ 8 000 triángulos,
    entre 900 y 2 200 en la práctica) y la pone en una maceta modelada. Los atlas vinieron en JPEG sin alfa. La silueta
    se recuperó del canal de rugosidad del ARM (helecho y calathea, cuyo fondo tiene un valor plano) o de la cobertura
    de las UV (anturio, de hojas modeladas). El color con alfa y la rugosidad se guardan como texturas derivadas
    versionadas (`--derivar`) y su origen queda en `assets/modelos/polyhaven/manifest.json`. Los materiales van con
    alfa CLIP (glTF `MASK`, umbral 0,5, dos caras), y `web/tour_modelo.py` conserva el alfa en el `.webp` y en la copia
    del teléfono. Se descartaron tres alternativas: bajar los PNG con alfa (una descarga nueva no autorizada en esta
    sesión), recortar por color (el relleno del atlas es el color del borde estirado) y tarjetas opacas.
30. **Presupuesto de triángulos.** La escena estaba a 1 766 del tope de 200 000. Para las alfombras, las cortinas y las
    plantas, la resolución de telas de las camas baja de 0,7 a 0,5 (−7 912, con la comparación en
    `review/09_textiles/cama_r05` y `cama_r07`) y los árboles de la calle quedan con una sola copa (−1 680; lo proponía
    la bitácora del bloque 08). Se descartó recortar los interiores de clósets o las lámparas: se ven de cerca.
31. **Colisión:** alfombras, telas, barras, hojas, tierra y cordeles llevan `colision: false`. Las macetas sí chocan.
    Así el recorrido pasa entre la maceta del balcón y la hoja abierta del ventanal, y la cámara no se traba en los
    paños del ventanal.
32. **Consecuencias:** la escena queda en 199 357 triángulos, a 643 del tope. Lo próximo tendrá que ahorrar o subir el
    tope. El visor pesa 16,99 MB en escritorio (antes 13,64) y 12,13 MB en teléfono (antes 10,78). El entorno local de
    la cocina ve ahora las cortinas del ventanal y las plantas. Su escala cambia, y el visor la compensa por la
    referencia (sección 6 del contrato).
