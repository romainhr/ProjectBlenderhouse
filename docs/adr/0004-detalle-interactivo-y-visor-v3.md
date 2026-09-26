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
