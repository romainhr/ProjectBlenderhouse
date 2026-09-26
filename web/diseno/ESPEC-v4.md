# Project-roomVR: especificación de implementación v4

- **Fecha:** 2026-09-26
- **Qué es:** la especificación para reescribir la portada y la reserva con el lenguaje visual del modelo de Google Stitch v4. Se corrigen los defectos que encontraron tres críticas: atractivo (7,5), UX en teléfono (6) y reglas y viabilidad (6).
- **Fuentes:** capturas y HTML de Stitch (`scratchpad/stitch_v4/r0/stitch/`: `inicio_escritorio`, `inicio_movil`, `reserva_escritorio` y `reserva_movil`), `web/diseno/DESIGN-v4.md` y el sitio real, `web/src/`.
- **Síntesis:** Claude Opus 5.5 (`claude-opus-5-5`). **Revisor humano:** pendiente (Romain Ange).
- **Archivos que se tocan:** `web/src/index.html`, `web/src/reserva.html`, `web/src/css/tokens.css`, `web/src/css/sitio.css`, `web/src/js/sitio.js`, `web/src/js/reserva.js` y `web/src/js/reserva-logica.js`, más `web/build.py` (recortes de materiales) y pruebas nuevas en `web/tests/`. Heredan los tokens y el encabezado: `privacidad.html`, `404.html` y `tour/`.
- **Regla de contenido:** no se evalúa lo que muestran las imágenes. Ninguna imagen de Stitch se lleva al sitio. Se usan los renders que `build.py` genera desde `web/renders_png/`, o las fotos que el dueño suba al portal.
- **Convención:** «medido» quiere decir medido en una captura o calculado desde el CSS. «Inferido» es una estimación que hay que verificar. Los contrastes se calcularon con la fórmula de WCAG 2.x.

---

## 0. Antes de empezar

1. **Integrar `origin/main` en la rama.** `web/diseno-atractivo` está 2 commits adelante y 3 atrás (medido con `git status`). Le falta el portal (#3): `js/contenido-publico.js`, `tarifaVigente()` y `fijarTarifas()` en `reserva-logica.js`, el uso de `tarifas()` en `reserva.js`, `tests/contenido-publico.test.mjs` y la migración `0003_gestion.sql`. Sin esto, `data-contenido`, `data-fotos` y las tarifas editadas no tienen efecto. Pedir aprobación al usuario antes de cada operación de git.
2. Correr `cd web && npm test` y `python3 -m unittest discover -s web/tests -p 'test_*.py'`. Las dos deben pasar **antes** de tocar nada.
3. **No copiar el HTML de Stitch.** Partir del marcado actual (`index.html`, `reserva.html`) y cambiar solo la envoltura, las clases y el CSS. De Stitch se traducen **valores** (medidas, colores, radios), nunca marcado ni clases.
4. **Fraunces:** pedir aprobación antes de descargarla. Es de Google Fonts, con licencia OFL, igual que las fuentes que ya aloja el sitio. `privacidad.html` promete «Las tipografías se sirven desde este mismo sitio», así que no se enlaza Google Fonts.
5. **Trazabilidad:** registrar `docs/adr/0006-sistema-visual-v4.md` con el formato de los ADR 0001 a 0005. Debe cubrir tres decisiones: Fraunces alojada en `tokens.css` (lo comparte el tour), el encabezado con estado por IntersectionObserver y los meses por página según el ancho. Indicar el modelo de IA y el revisor humano.

### 0.1 Decisiones que concilian las críticas

Las tres críticas no coincidieron en todo. Esto es lo que se decidió, para no volver a discutirlo al implementar:

| Tema | Decisión | Por qué |
|---|---|---|
| Encabezado | Fijo en las dos páginas. En la portada es **transparente sobre el hero**, con un velo garantizado, y pasa a papel con filete al salir del hero. En las demás páginas siempre es papel | Al dueño le gustó la portada; «delgada y clara» se cumple fuera del hero. Dos críticas aceptan el cambio de estado |
| Marca en el encabezado sobre el hero | Oculta (`visibility: hidden`) mientras el encabezado es transparente | Una portada tiene una sola cabecera; el H1 ya es la marca |
| Tarjeta de reserva rápida en Tarifas | **Se elimina** en todos los anchos. Queda una frase y el botón «Ver fechas» hacia la reserva | Dos críticas contra una: los `input type=date` nativos no muestran días ocupados y su formato depende del navegador |
| Cifras de la línea de datos | Se mantienen en Fraunces cursiva terracota, con la línea base corregida | La crítica de atractivo las destaca y el dueño aprobó el modelo. No son cajas de estadísticas, sino texto en línea |
| Días ocupados | Solo trama y número atenuado, **sin tachado** | DESIGN-v4 dice «atenuados con trama». La trama ya no depende del color, y el `aria-label` dice «ocupado» |
| Jerarquía en Tarifas | «Tarifas» como capítulo (88 px) y el precio a 48 px | El precio es editable, hasta «CLP 10.000.000», y a 96 px no cabría con `nowrap` |
| Tamaño de los títulos de capítulo | 88 px como máximo (no 96) | «Recorrido 3D» a 96 px mide unos 580 px (inferido de la captura: 433 px a 72 px) |
| Imágenes en la reserva | Sin imagen en la introducción. En el resumen, una imagen de 21:9 solo si la ventana mide 860 px de alto o más | La tarea (el calendario) va primero y el botón siempre se ve |
| Rótulo de envío | «Solicitar» en los dos tamaños | DESIGN-v4 lo pide. «Solicitar reserva» no cabe en la barra a 320 px |
| Botón sin fechas | `aria-disabled="true"` (no `disabled`). Al tocarlo, explica el problema y lleva al calendario. `disabled` real solo mientras se envía | Un botón deshabilitado sin explicación no le dice al usuario qué falta |
| Tamaños de texto | Texto corrido ≥ 16 px. Notas de una o dos líneas: 15 px. Metadatos de una a cuatro palabras: 14 px. Nada por debajo de 14 | Equilibrio entre DESIGN-v4 (16 a 18) y el aire del modelo |
| Meses por página | Los decide el **ancho del contenedor** de los meses (JS con ResizeObserver), no el viewport | Con el resumen a la derecha, dos meses solo caben de unos 1.230 px de ventana hacia arriba |
| «Qué pasa después» | Entre el Resumen y Tus datos, como `h2` | Se lee antes de decidir. El orden del DOM coincide con el del teléfono |
| Frase destacada | Sin comillas ni autor, con un dato concreto del modelo | Entre comillas se leía como una reseña inventada |
| Errores | Terracota oscura `#7F3515` sobre `#F2DDD2`, con `role=alert`. El éxito va en oliva | Pedido explícito de la crítica de atractivo; es la paleta del sistema |
| Carrusel | Barra de progreso fina en terracota (JS). La barra de desplazamiento nativa queda visible y delgada con mouse, y oculta en pantallas táctiles | Conserva el detalle del modelo sin quitar la ayuda a quien usa mouse |

---

## 1. Tokens

### 1.1 Color

Se usan los valores exactos de DESIGN-v4. Donde Stitch agregó alguno, se indica.

| Token (`tokens.css`) | Hex | Uso | Contraste medido |
|---|---|---|---|
| `--papel` | `#F6F1EA` | Fondo general, encabezado sólido, barra fija, botón invertido | Tinta sobre papel: 15,2:1 |
| `--arena` (alias `--papel-2`) | `#EDE3D6` | Franja de Materiales, pie, resumen en teléfono, hover de días y botones | Tinta secundaria: 5,6:1 |
| `--tarjeta` | `#FBF8F3` | Tarjetas de la reserva (de Stitch: `--color-surface-card`) | Tinta secundaria: 6,7:1 |
| `--tinta` | `#1F1B17` | Texto y títulos | — |
| `--tinta-2` | `#5F574E` | Texto secundario, rótulos, **bordes de campo** y marcadores | Sobre papel: 6,3:1. Sobre arena: 5,6:1. Sobre `#F2DDD2`: 5,4:1 |
| `--linea` | `#E0D6C8` | Filetes decorativos (nunca el borde de un control) | Sobre papel: 1,28:1 (solo decorativo) |
| `--terracota` (alias `--acento`) | `#A4471E` | Botón principal, enlaces, foco, cifras, extremos del rango | Blanco encima: 6,0:1. Sobre papel: 5,3:1. Sobre arena: 4,7:1. Sobre tarjeta: 5,7:1 |
| `--terracota-osc` (alias `--acento-2`) | `#7F3515` | Hover, bloque de Tarifas, frase destacada, texto del rango, errores | Papel encima: 7,7:1. Sobre `#F2DDD2`: 6,6:1 |
| `--terracota-suave` | `#F2DDD2` | Días dentro del rango, fondo de los mensajes de error (de Stitch) | Tinta encima: 13,1:1 |
| `--oliva` (alias `--salvia`) | `#5E6B52` | Estado correcto: éxito y confirmación | Sobre papel: 5,05:1. Blanco encima: 5,7:1 |
| `--carbon` | `#26221E` | Solo el bloque del Recorrido 3D | Papel encima: 14,1:1. Papel al 70 %: 7,6:1 |
| `--error` | `#7F3515` | Igual a `--terracota-osc` (reemplaza `#B3261E`) | 6,6:1 sobre `#F2DDD2` |

**Colores derivados (fijos, sin token nuevo):**
- Número de un día ocupado o pasado: `#9C9388` (2,7:1). Solo se usa en controles deshabilitados, que WCAG 1.4.3 exime.
- Trama de ocupado: `repeating-linear-gradient(45deg, var(--linea) 0 1.5px, transparent 1.5px 6px)`.

**Ritmo de fondos de la portada** (medido en el modelo; se conserva): papel (hero, datos y Espacios), arena (Materiales), carbón (Recorrido 3D), papel (Lo que hay), terracota oscura (Tarifas), papel (Preguntas) y arena (pie). Son dos bloques intensos, como pide el sistema.

### 1.2 Velos y transparencias

| Uso | Valor | Garantía |
|---|---|---|
| Velo inferior del hero (detrás del texto, **atado al bloque**, ver 3.2) | `rgba(20,16,12,.85)` en la base, `.70` en el borde superior del texto y `0` a 160 px por encima | Blanco sobre `.70` en el peor caso (render blanco): 7,1:1 |
| Velo superior del hero (detrás del encabezado) | `rgba(20,16,12,.6)` de 0 a 72 px y `0` a 180 px | Blanco sobre `.6` en el peor caso: 5,0:1 |
| Texto secundario sobre carbón | `rgba(246,241,234,.7)` | 7,6:1 |
| Texto sobre terracota oscura | `rgba(246,241,234,.88)` | 6,4:1 |
| Filete sobre carbón | `rgba(246,241,234,.16)` | Decorativo |
| Filete sobre terracota oscura | `rgba(246,241,234,.25)` | Decorativo |

Los velos del hero son el mínimo garantizado. Solo se pueden aclarar si, con el render real, se mide al menos 4,5:1 en el punto más claro bajo la bajada y 3:1 bajo el H1 (ver 8.2).

### 1.3 Tipografía

**Familias**
- Títulos: **Fraunces** variable, con los ejes `opsz` 9–144 y `wght` 400–600, en redonda y cursiva, subconjunto latin. Va autoalojada en `web/src/fonts/fraunces-var.woff2` y `fraunces-var-italic.woff2`.
- Texto: **Public Sans** 400, 500 y 600 (ya está alojada).
- Se retira **Newsreader** (`newsreader-500.woff2` y su `@font-face`) cuando ninguna página la use. Confirmarlo con `grep -r Newsreader web/src`.

**Reglas**
- `font-optical-sizing: auto` en todas las páginas. **Prohibido** `font-variation-settings: "opsz" …`: la reserva de Stitch lo fija en 72, lo que quita el contraste del tamaño óptico 144 a 104 px y adelgaza el texto chico. También se quita `font-feature-settings: "opsz"` de la portada de Stitch, que no es válido.
- `font-synthesis: none`, para no falsear negritas ni cursivas si falla la carga de una fuente.
- Títulos en tipo oración, peso 400. Peso 500 para la marca, los pies de foto (`h3`), los ítems de equipamiento, las preguntas y los nombres de material. Peso 600 solo para el precio de la barra fija.
- Sin mayúsculas sostenidas ni monoespaciadas.
- **La cursiva tiene solo cuatro usos:** la línea «Ladrillo, roble y luz cálida.», las cifras de la línea de datos, la frase destacada y «sin cobro en línea.». Los pies de foto van en redonda.
- El nombre «Project-roomVR» va **siempre** en un elemento con `white-space: nowrap` (clase `.nombre`, o `b` dentro de `.marca`).
- Números tabulares (`font-variant-numeric: tabular-nums`) en precios, días del calendario y totales.

**Escala fluida.** Todos los tamaños se interpolan de 375 a 1280 px de ancho de ventana: `clamp(mín, a + b·vw, máx)`.

| Token | Mín (375) | Máx (1280) | Valor | Familia y peso | Interlineado | Uso |
|---|---|---|---|---|---|---|
| `--t-marca-hero` | 36 | 112 | `clamp(36px, calc((100vw - 2 * var(--margen)) / 7.8), 112px)` | Fraunces 400, `letter-spacing: -0.02em` | 0,95 | H1 del hero. El divisor sale del ancho medido de «Project-roomVR»: 7,45 em (834 px a 112 px), con un 5 % de margen |
| `--t-reserva` | 52 | 104 | `clamp(52px, calc(30.5px + 5.75vw), 104px)` | Fraunces 400, −0.02em | 0,95 | H1 «Reserva» |
| `--t-capitulo` | 48 | 88 | `clamp(48px, calc(31.4px + 4.42vw), 88px)` | Fraunces 400, −0.02em | 1,0 | Espacios, Recorrido 3D y Tarifas |
| `--t-seccion` | 40 | 56 | `clamp(40px, calc(33.4px + 1.77vw), 56px)` | Fraunces 400, −0.01em | 1,05 | Materiales, Lo que hay y Preguntas |
| `--t-precio` | 32 | 48 | `clamp(32px, calc(25.4px + 1.77vw), 48px)` | Fraunces 400, `nowrap` | 1,0 | Precio de Tarifas |
| `--t-cita` | 30 | 44 | `clamp(30px, calc(24.2px + 1.55vw), 44px)` | Fraunces cursiva 400, −0.01em | 1,22 | Frase destacada |
| `--t-cursiva-reserva` | 26 | 40 | `clamp(26px, calc(20.2px + 1.55vw), 40px)` | Fraunces cursiva 400 | 1,15 | «sin cobro en línea.» |
| `--t-lema` | 24 | 36 | `clamp(24px, calc(19px + 1.33vw), 36px)` | Fraunces cursiva 400 | 1,2 | «Ladrillo, roble y luz cálida.» |
| `--t-total` | 28 | 34 | `clamp(28px, calc(25.5px + 0.66vw), 34px)` | Fraunces 400 | 1,0 | Total estimado |
| `--t-tarjeta` | 28 | 32 | `clamp(28px, calc(26.3px + 0.44vw), 32px)` | Fraunces 400 | 1,1 | `h2` de las tarjetas de la reserva y «Qué pasa después» |
| `--t-pie` | 22 | 26 | `clamp(22px, calc(20.3px + 0.44vw), 26px)` | Fraunces 500 | 1,25 | `h3` de Espacios |
| `--t-cifra` | 22 | 26 | `clamp(22px, calc(20.3px + 0.44vw), 26px)` | Fraunces cursiva 400, terracota | 1,0 | Cifras de la línea de datos |
| `--t-marca` | 21 | 24 | `clamp(21px, calc(19.8px + 0.33vw), 24px)` | Fraunces 500 | 1,0 | Marca del encabezado |
| `--t-pregunta` | 19 | 24 | `clamp(19px, calc(16.9px + 0.55vw), 24px)` | Fraunces 500 | 1,3 | `summary` de las preguntas |
| `--t-item` | 20 | 22 | `clamp(20px, calc(19.2px + 0.22vw), 22px)` | Fraunces 500 | 1,25 | `h3` de equipamiento y de «Qué pasa después» |
| `--t-material` | 16 | 22 | `clamp(16px, calc(13.5px + 0.66vw), 22px)` | Fraunces 500 | 1,2 | Nombre de cada material |
| `--t-bajada` | 16 | 18 | `clamp(16px, calc(15.2px + 0.22vw), 18px)` | Public Sans 400 | 1,6 | Bajadas |
| `--t-cuerpo` | 16 | 16 | `16px` | Public Sans 400 | 1,6 | Texto corrido, descripciones, respuestas, tablas y campos |
| `--t-nota` | 15 | 15 | `15px` | Public Sans 400 | 1,55 | Notas de una o dos líneas: la del modelo, la del total, la del pie y los pies de captura |
| `--t-meta` | 14 | 14 | `14px` | Public Sans 500 | 1,4 | Metadatos: días de la semana, leyenda, rótulo de la barra, migas y «Arriendo turístico» |

Dos tamaños fijos más: el nombre del mes en el calendario, Fraunces 400 de 22 px en minúscula con alto de línea de 48 px, y los botones, Public Sans 500 de 16 px.

### 1.4 Espaciado, retícula y cortes

| Token | Valor | Uso |
|---|---|---|
| `--margen` | `max(16px, env(safe-area-inset-left), env(safe-area-inset-right))`. Desde 700 px: `max(32px, …)` | Margen lateral |
| `--ancho` | `1216px` | Contenido máximo: 1280 menos 2 × 32, como el `container-1280` de Stitch |
| `.contenedor` | `width: min(var(--ancho), 100% - 2 * var(--margen)); margin-inline: auto` | Siempre fluido, sin `max-width: 390px` |
| `--barra-alto` | `60px`. Desde 1000 px: `72px` | Encabezado |
| `--sec-y` | `clamp(48px, calc(14.9px + 8.84vw), 128px)` | Relleno vertical de cada sección (Stitch: 120 a 140 en escritorio y 48 en teléfono) |
| `--cab-y` | `clamp(24px, calc(4.1px + 5.3vw), 72px)` | Separación entre la cabecera de la sección y su contenido |
| `--fila-y` | `clamp(40px, calc(23.4px + 4.42vw), 80px)` | Separación entre filas de la galería |
| Escala fija | 4, 8, 12, 16, 20, 24, 32, 48, 56, 80 y 96 px | Separaciones internas |
| Columnas | 12 columnas con `column-gap: 24px` en la galería. 48 px en Recorrido, Tarifas y Preguntas | Retícula de escritorio |

**Cortes** (mobile-first, `min-width`; son los mismos que ya usa `sitio.css`):

| Corte | Qué cambia |
|---|---|
| base (< 560) | Teléfono. Calendario a sangre (ver 4.4) |
| 560 | Carruseles con tarjetas al 60 %, calendario como tarjeta, «Correo» y «Teléfono» en dos columnas |
| 600 | Aparece «Arriendo turístico» junto a la marca |
| 700 | Tableta: márgenes de 32 px, galerías en retícula (no carrusel), Materiales en 5 columnas, equipamiento en 2 columnas, pie de portada visible, migas visibles |
| 1000 | Computador: menú completo, «Reservar» en el encabezado, sin barra fija inferior, Recorrido, Tarifas y Preguntas en 2 columnas, reserva en 2 columnas con resumen fijo, equipamiento en 3 columnas, hero al 88 % del alto |
| 1100 | Galería editorial de 12 columnas en Espacios |

### 1.5 Forma: radios, sombras y filetes

| Token | Valor | Uso |
|---|---|---|
| `--radio` | `10px` | Botones, campos, contador, chip de cada día y mensajes (el tour lo usa: se conserva el nombre) |
| `--radio-img` | `12px` | Imágenes, tarjetas, muestras y bloque de resumen |
| Radios menores | 4 px en las muestras de la leyenda, 1 px en la barra de progreso; círculo (50 %) en las flechas de mes y el ícono 3D | — |
| `--sombra-1` | `0 1px 2px rgba(31,27,23,.06)` | Botones y tarjetas |
| `--sombra` | `0 1px 2px rgba(30,28,25,.06), 0 8px 24px rgba(30,28,25,.06)` | Se conserva para el tour y el panel del menú |
| `--sombra-barra` | `0 -2px 10px rgba(31,27,23,.05)` | Barra fija inferior |
| `--sombra-oscura` | `0 12px 32px rgba(0,0,0,.3)` | Solo la captura del Recorrido sobre carbón |
| Filete | `1px solid var(--linea)` (o `var(--filete)` en los bloques oscuros) | Separadores |

Se descarta la sombra `0 4px 20px rgba(0,0,0,.15)` de la tarjeta de reserva de Stitch.

### 1.6 Foco (corrige los defectos de foco invisible y de anillo sobre bloques oscuros)

```css
:root { --anillo: var(--terracota); }
:focus-visible { outline: 2px solid var(--anillo); outline-offset: 2px; border-radius: 4px; }
.hero, .barra.sobre-hero { --anillo: #fff; }                          /* 7,1:1 sobre el velo */
.fondo-carbon, .fondo-terracota { --anillo: var(--papel); }          /* 14,1:1 y 7,7:1 */
```

- Se usa `outline` con separación, no `box-shadow`. El resultado es el mismo «anillo doble» del campo Nombre de Stitch (2 px de fondo y 2 px de color), pero también se ve en modo de alto contraste y no lo recorta un `overflow: hidden`.
- **Prohibido** en todo el CSS: `outline: none`, `outline: 0`, `focus:ring-0` y `-webkit-tap-highlight-color: transparent`.
- En los campos, `:focus` cambia además el borde a terracota. El anillo de `:focus-visible` se mantiene.
- En un botón terracota, la separación de 2 px deja el anillo sobre el fondo de la página, no sobre el botón.

### 1.7 Movimiento

- `.aparece`: opacidad 0 → 1 y desplazamiento de 10 px, en 0,5 s `ease`. Ya existe y se conserva, pero no se aplica al hero ni a la línea de datos.
- Encabezado y barra fija: transición de 0,2 s en color, fondo y `transform`.
- Captura del Recorrido: `transform: scale(1.03)` en 0,3 s al pasar el cursor.
- Con `prefers-reduced-motion: reduce`: sin transiciones, sin escala y `scroll-behavior: auto`.

### 1.8 Bloque de `tokens.css`

Se reemplaza `:root` y se agregan las dos `@font-face` de Fraunces. Los nombres que usa el tour se conservan: `--papel`, `--papel-2`, `--tarjeta`, `--tinta`, `--tinta-2`, `--linea`, `--acento`, `--acento-2`, `--salvia`, `--error`, `--radio`, `--sombra`, `--f-titulo` y `--f-texto`.

```css
@font-face { font-family: "Fraunces"; font-style: normal; font-weight: 400 600; font-display: swap;
  src: url("../fonts/fraunces-var.woff2") format("woff2");
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122; }
@font-face { font-family: "Fraunces"; font-style: italic; font-weight: 400 600; font-display: swap;
  src: url("../fonts/fraunces-var-italic.woff2") format("woff2");
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122; }
/* (Public Sans 400, 500 y 600: sin cambios) */
:root {
  --papel: #F6F1EA; --arena: #EDE3D6; --papel-2: var(--arena); --tarjeta: #FBF8F3;
  --tinta: #1F1B17; --tinta-2: #5F574E; --linea: #E0D6C8;
  --terracota: #A4471E; --terracota-osc: #7F3515; --terracota-suave: #F2DDD2;
  --acento: var(--terracota); --acento-2: var(--terracota-osc);
  --oliva: #5E6B52; --salvia: var(--oliva); --carbon: #26221E; --error: var(--terracota-osc);
  --radio: 10px; --radio-img: 12px;
  --sombra-1: 0 1px 2px rgba(31, 27, 23, .06);
  --sombra: 0 1px 2px rgba(30, 28, 25, .06), 0 8px 24px rgba(30, 28, 25, .06);
  --f-titulo: "Fraunces", "Iowan Old Style", Georgia, serif;
  --f-texto: "Public Sans", system-ui, -apple-system, sans-serif;
  color-scheme: light;
}
```

Las variables de la escala tipográfica (1.3) y de espaciado (1.4) van en `sitio.css`, no en `tokens.css`, porque el tour no las usa. Hay que actualizar `<meta name="theme-color">` a `#F6F1EA` en todas las páginas. Precargar la redonda en `index.html` y `reserva.html` con `<link rel="preload" as="font" type="font/woff2" href="fonts/fraunces-var.woff2" crossorigin>`.

---

## 2. Componentes comunes

### 2.1 Botones y enlaces de acción

| Clase | Aspecto | Estados |
|---|---|---|
| `.boton.primario` | Fondo terracota, texto `#fff`, Public Sans 500 de 16 px, `min-height: 48px`, `padding: 0 28px`, `--radio`, `--sombra-1` | Hover y activo: `--terracota-osc`. Con `[aria-disabled="true"]` o `[disabled]`: opacidad 0,5 y `cursor: not-allowed` |
| `.boton.secundario` | Borde de 1 px en `--tinta`, texto tinta, fondo transparente (así lo pide DESIGN-v4) | Hover: fondo `rgba(31,27,23,.04)` |
| `.boton.invertido` | Fondo papel, texto tinta en 600. Solo sobre terracota oscura | Hover: fondo `#fff` |
| `.boton.grande` | `min-height: 52px` | Botón del resumen de escritorio |
| `.boton.bloque` | `width: 100%` | Botones de teléfono y del resumen |
| `.enlace-accion` | Texto subrayado (`text-underline-offset: 6px`), 16 px en 500, `display: inline-flex; align-items: center; min-height: 48px; padding-inline: 8px` | Solo «Ver fechas» del hero. En teléfono va a todo el ancho y centrado |

Bajo 480 px los botones pueden partir su rótulo, como hoy (`white-space: normal`). Los rótulos cortos del encabezado y de la barra no se parten.

### 2.2 Encabezado (`header.barra`) y panel del menú

Es el mismo marcado en todas las páginas y parte del actual. Corrige los defectos del encabezado absoluto, del encabezado distinto entre páginas, del botón «Tour 3D», de la hamburguesa sin panel y de la marca repetida.

```html
<header class="barra sobre-hero">  <!-- «sobre-hero» solo en index.html -->
  <div class="contenedor">
    <a class="marca" href="./" aria-label="Project-roomVR, inicio"><b>Project-roomVR</b><small>Arriendo turístico</small></a>
    <nav class="menu-nav" aria-label="Principal"><ul class="menu">
      <li><a href="#espacios">Espacios</a></li>        <!-- desde otra página: ./#espacios -->
      <li><a href="#tour">Recorrido 3D</a></li>
      <li><a href="#tarifas">Tarifas</a></li>
      <li><a href="#preguntas">Preguntas</a></li>
    </ul></nav>
    <a class="boton primario reservar" href="reserva.html">Reservar</a>   <!-- en reserva.html: aria-current="page" -->
    <button class="hamburguesa" type="button" aria-label="Abrir menú" aria-controls="panel-menu" aria-expanded="false">…svg actual…</button>
  </div>
</header>
<nav id="panel-menu" class="panel-menu" hidden aria-label="Menú">
  <!-- en reserva.html: primero <a href="./">Inicio</a> -->
  <a href="#espacios">Espacios</a><a href="#tour">Recorrido 3D</a><a href="#tarifas">Tarifas</a><a href="#preguntas">Preguntas</a>
  <a href="reserva.html">Reservar</a>
</nav>
```

- **Estado sólido** (el que viene por defecto): `position: fixed; inset: 0 0 auto; height: var(--barra-alto); background: var(--papel); border-bottom: 1px solid var(--linea); color: var(--tinta)`. Sin `backdrop-filter` ni transparencias. Los enlaces van en Public Sans 500 de 16 px, en `--tinta-2`, separados 32 px. Al pasar el cursor, o con `[aria-current]`, cambian a terracota.
- **Estado `.sobre-hero`** (solo en la portada, mientras el hero está bajo el encabezado): fondo y filete transparentes, texto y enlaces `#fff` y `.marca { visibility: hidden }`. El contraste lo asegura el velo superior del hero (1.2). Si el panel está abierto, el encabezado vuelve al estado sólido: `body:has(#panel-menu:not([hidden])) .barra.sobre-hero { …estado sólido… }`, con la marca visible.
- **Sin JS:** en `index.html`, `<noscript><style>.barra.sobre-hero { background: var(--papel); color: var(--tinta); border-bottom-color: var(--linea) } .barra.sobre-hero .marca { visibility: visible }</style></noscript>`. Va junto a la regla de `.aparece` que ya existe.
- **Marca:** `b` con `font: 500 var(--t-marca)/1 var(--f-titulo); white-space: nowrap`. `small` en `--t-meta` y tinta secundaria, oculto bajo 600 px.
- **Bajo 1000 px:** marca y hamburguesa; el menú y `.reservar` se ocultan. Hamburguesa de **48 × 48**, sin borde, con `--radio`. El hover es arena en el estado sólido y `rgba(255,255,255,.12)` sobre el hero. Ícono de 20 × 14 con trazo de 1,5.
- **Desde 1000 px:** marca, menú (con `margin-left: auto`) y «Reservar» (48 px, 24 px a la izquierda del menú). La hamburguesa y el panel se ocultan.
- **Panel:** lo que ya tiene `sitio.css`: fijo bajo la barra, fondo papel, enlaces en Fraunces 500 de 20 px con filetes y `padding: 14px 0`, lo que da un alto de unos 52 px. Se cierra con Esc (ya lo hace `sitio.js`).
- **En `reserva.html`**, «Reservar» lleva `aria-current="page"` y el mismo aspecto. Se elimina el botón «Tour 3D».
- **`privacidad.html`** usa el mismo componente que `reserva.html`. **`404.html`** no tiene encabezado y se deja así.

### 2.3 Barra fija inferior (`.barra-movil`, bajo 1000 px)

Se reutilizan `.barra-movil` y `body.con-barra-movil` del CSS actual, que ya calculan el área segura y el espacio extra del pie (`--pie-extra`).

- Fondo papel **opaco**, sin desenfoque. `border-top: 1px solid var(--linea)`, `box-shadow: var(--sombra-barra)`. `padding: 12px var(--margen) max(12px, env(safe-area-inset-bottom))`. Flex con `justify-content: space-between`.
- Izquierda: `p.precio` con el monto en Fraunces 600 de 22 px (tabular) y, debajo, un `small` en `--t-meta` y tinta secundaria (`display: block`).
- Derecha: `.boton.primario` de 48 px.
- Ancho completo con `inset: auto 0 0`. **Sin** `max-width: 390px` ni `translateX`.
- Estado `.oculta`: `transform: translateY(100%); visibility: hidden`, lo que además la saca del orden de tabulación.
- **En la portada**, la barra se muestra solo cuando el hero salió de la vista y Tarifas no está en pantalla (ver 6.2). Sin JS o sin IntersectionObserver, queda visible.
- `html:has(body.con-barra-movil)`: `scroll-padding-bottom: calc(80px + env(safe-area-inset-bottom))` bajo 1000 px. Ya existe y se conserva.

### 2.4 Campos

- `label` y `.rotulo` visibles, Public Sans 500 de 15 px en tinta, 6 px sobre el campo. «(opcional)» va dentro de la etiqueta.
- `input`, `select` y `textarea`: `min-height: 48px`, `padding: 0 14px` (el `textarea` lleva 12 y 14, con alto mínimo de 120), `--radio`, fondo papel sobre la tarjeta, **borde de 1 px en `--tinta-2`** (6,3:1; corrige el `#CFC3B3` de Stitch, que da 1,5:1) y **`font-size: 16px`**, lo que evita el zoom automático de iOS sin bloquear el zoom.
- `:focus`: borde terracota y fondo `#fff`, más el anillo de `:focus-visible` (1.6).
- `[aria-invalid="true"]`: `border-color: var(--terracota-osc); box-shadow: inset 0 0 0 1px var(--terracota-osc)`.
- Marcadores de posición: solo en «Mensaje» («Hora estimada de llegada, preguntas…»), en `--tinta-2` (6,3:1). **Ningún** ejemplo en correo ni teléfono, y ningún valor precargado: nada de «Ana Pérez».
- Casilla: `input#acepta` de 20 × 20 con `accent-color: var(--terracota)`, **sin `checked`** y `required`. `label.check` ocupa la fila completa, con `min-height: 48px`, `display: flex; gap: 12px; align-items: flex-start` y 16 px en tinta secundaria.

### 2.5 Mensajes y estados

| Clase | Aspecto | Rol |
|---|---|---|
| `.mensaje` | `padding: 12px 16px`, `--radio`, `border: 1px solid var(--linea)`, 15 px | Aviso de simulación (`#aviso-sim`) |
| `.mensaje.error` | Fondo `--terracota-suave`, texto `--terracota-osc` (6,6:1), `border: 0`, `border-left: 3px solid var(--terracota-osc)`, 16 px | `role="alert"` (ya está en `#cal-error` y `#form-error`) |
| `.mensaje.ok` y `.exito` | Borde izquierdo de 3 px en `--oliva`. Rótulo en oliva y 600 (5,05:1 sobre papel) | Confirmación |

### 2.6 Pie (`footer.pie`)

- Fondo arena y `border-top` con filete. `padding: 64px 0 calc(64px + var(--pie-extra, 0px))` en escritorio y `40px 0 calc(40px + var(--pie-extra))` en teléfono.
- Desde 900 px: una retícula de tres columnas (`auto 1fr auto`, alineadas al centro). Bajo ese corte: apilado con `gap: 12px`.
- Marca `a.pie-marca` en Fraunces 500 (28 px en escritorio y 22 en teléfono), con `nowrap`, hacia `./`. Nota «Imágenes renderizadas desde un modelo 3D · tarifas de ejemplo» en `--t-nota`. Derechos: `© <span id="anio">2026</span> <span class="nombre">Project-roomVR</span> · <a href="privacidad.html">Privacidad</a>`.
- Los enlaces del pie llevan `display: inline-block; padding-block: 12px`, para llegar a unos 44 px de área táctil.

### 2.7 Patrón de carrusel (Espacios y Materiales, bajo 700 px)

Corrige el carrusel sin `scroll-padding`, la primera tarjeta pegada al borde, la falta de foco y la barra que no calzaba.

```css
.desliza { display: flex; gap: 12px; overflow-x: auto; overscroll-behavior-x: contain;
  scroll-snap-type: x mandatory; scroll-padding-inline: var(--margen);
  padding: 4px var(--margen) 8px; margin-inline: calc(-1 * var(--margen)); scrollbar-width: thin; }
.desliza > * { scroll-snap-align: start; }
@media (pointer: coarse) { .desliza { scrollbar-width: none; } .desliza::-webkit-scrollbar { display: none; } }
```

- El contenedor lleva `tabindex="0" role="region" aria-label="…"`, para que se pueda recorrer con las flechas del teclado.
- La primera tarjeta queda alineada con el título de la sección (x = 16 px a 375). Verificarlo en la captura.
- Barra de progreso (solo en Espacios): `div.progreso` con `aria-hidden="true"`, de 2 px de alto, fondo línea y un `i` interior en terracota. Queda a 16 px del carrusel y dentro del margen. El ancho del relleno es `clientWidth / scrollWidth` y se desplaza con el scroll (ver 6.2). Se oculta desde 700 px.

---

## 3. Portada (`index.html`), sección por sección

Orden: encabezado, hero, línea de datos, Espacios, Materiales, Recorrido 3D, Lo que hay, Tarifas, Preguntas, pie y barra fija. Los `id` son `espacios`, `materiales`, `tour`, `equipamiento`, `tarifas` y `preguntas`. Se conservan `<a class="saltar" href="#contenido">` y `<main id="contenido">`.

### 3.1 Encabezado
Ver 2.2. Mientras el hero ocupa el borde superior, en teléfono solo se ve la hamburguesa y en escritorio el menú y «Reservar».

### 3.2 Hero

**Se conserva del modelo:** la portada a sangre; «Project-roomVR» abajo a la izquierda en Fraunces 400; la línea «Ladrillo, roble y luz cálida.» en cursiva; una bajada corta; el botón «Recorrer en 3D» junto al enlace subrayado «Ver fechas»; y el pie «Portada: el living, con el balcón al fondo» abajo a la derecha, alineado con los botones.

**Se corrige:** el velo que no aseguraba el contraste (atado ahora al texto), el encabezado del teléfono sin velo, el H1 que se desbordaba, la triple llamada de la primera pantalla y la claridad en 5 segundos.

```html
<section class="hero" aria-labelledby="titulo">
  <picture>
    <source type="image/webp" srcset="img/living-800.webp 800w, img/living-1600.webp 1600w" sizes="100vw">
    <img class="hero-img" src="img/living-1600.jpg" alt="(el alt actual)" width="1600" height="1000" fetchpriority="high">
  </picture>
  <div class="hero-texto">
    <div class="contenedor">
      <div class="hero-bloque">
        <h1 id="titulo"><span class="nombre">Project-roomVR</span></h1>
        <p class="lema">Ladrillo, roble y luz cálida.</p>
        <p class="bajada" data-contenido="hero.bajada">(texto de la semilla de 0003, idéntico)</p>
        <div class="acciones">
          <a class="boton primario" href="tour/">Recorrer en 3D</a>
          <a class="enlace-accion" href="reserva.html#calendario">Ver fechas</a>
        </div>
      </div>
      <p class="hero-pie">Portada: el living, con el balcón al fondo</p>
    </div>
  </div>
</section>
```

- **Caja:** `.hero { position: relative; height: max(540px, 82svh); max-height: 1200px; overflow: hidden; background: var(--carbon); color: #fff }`. Desde 1000 px: `height: max(640px, 88svh)`. Se usa `svh` para que el texto quede dentro de la vista con las barras de Safari visibles. Sin relleno superior, porque el encabezado flota encima.
- **Imagen:** `position: absolute; inset: 0; object-fit: cover`. `object-position: 60% 50%` en teléfono y `50% 60%` desde 1000 px (valores de Stitch). La precarga actual de `living-1600.webp` se mantiene.
- **Velo superior:** `.hero::before`, con `height: 180px` y el velo de 1.2, `z-index: 1` y `pointer-events: none`.
- **Velo inferior, atado al texto:** `.hero-texto` es una banda de ancho completo con `position: absolute; inset: auto 0 0; z-index: 2; padding-top: 160px; padding-bottom: clamp(24px, calc(8px + 3.8vw), 56px)`. Su fondo es:
  `linear-gradient(to top, rgba(20,16,12,.85) 0, rgba(20,16,12,.70) calc(100% - 160px), rgba(20,16,12,0) 100%)`.
  El borde superior del texto siempre queda sobre un velo de 0,70, aunque la bajada del portal tenga 2, 3 o 4 líneas y el hero mida lo que mida. Verificado con el CSS: con 375 × 547 el bloque más el degradado miden unos 497 px de los 547 disponibles, y con 1280 × 704, unos 556 de 704. Ambos valores son inferidos.
- **`.contenedor` interior:** en teléfono, `display: block`. Desde 700 px, `display: flex; justify-content: space-between; align-items: flex-end; gap: 32px`.
- **H1:** `font: 400 var(--t-marca-hero)/.95 var(--f-titulo); letter-spacing: -0.02em; white-space: nowrap; margin: 0 0 12px; color: #fff`. A 320 px mide 36 px (unos 268 de 288 disponibles); a 375, 44 px; a 768, unos 94 px; desde unos 1.000 px, 112 px.
- **Lema:** `.lema`, en `--t-lema` y cursiva, color papel, con 16 px debajo (10 en teléfono).
- **Bajada:** `--t-bajada`, `rgba(255,255,255,.92)`, `max-width: 46ch`, `white-space: pre-line` (el tipo es `parrafo`) y 28 px debajo (16 en teléfono). **El texto viene del portal.** La semilla actual mide dos líneas en escritorio y cuatro a 375 px; el diseño lo admite. Queda como sugerencia para el dueño, no para el implementador, acortarla en el portal a una línea funcional: por ejemplo, «Departamento de dos dormitorios con balcón, por noches. Recórrelo en 3D antes de reservar.».
- **Acciones:** desde 700 px, fila con `gap: 24px` y botón de ancho automático. En teléfono, el botón a todo el ancho y «Ver fechas» debajo, como bloque de 48 px centrado.
- **Pie de portada:** `.hero-pie`, Public Sans 400 en `--t-meta`, `rgba(255,255,255,.85)`, `nowrap`, `padding-bottom: 14px` para alinearlo con la base del botón. Se oculta bajo 700 px. **Tiene que describir la imagen real;** si cambia la portada, se cambia el texto.
- **Sin `.aparece`** en el hero.

### 3.3 Línea de datos

**Se conserva:** una sola línea entre filetes, con las cifras en Fraunces cursiva terracota.
**Se corrige:** el corte «hasta 4 / huéspedes», los separadores invisibles (1,28:1) y la línea base de las cifras.

```html
<section class="datos" aria-label="Datos del departamento"><p class="contenedor">
  <span class="dato"><span class="cifra">2</span> dormitorios</span><span class="sep" aria-hidden="true">·</span>
  <span class="dato"><span class="cifra">2</span> baños</span><span class="sep" aria-hidden="true">·</span>
  <span class="dato">balcón</span><span class="sep" aria-hidden="true">·</span>
  <span class="dato">hasta <span class="cifra">4</span> huéspedes</span><span class="sep" aria-hidden="true">·</span>
  <span class="dato">≈ <span class="cifra">54</span> m² construidos</span>
</p></section>
```

- `border-block: 1px solid var(--linea)`, centrado, 16 px en tinta. En teléfono, `padding: 20px 0` e interlineado de 1,9. Desde 1000 px, `min-height: 72px` con `display: grid; place-items: center`.
- `.dato { white-space: nowrap }`. `.cifra { font: italic 400 var(--t-cifra)/1 var(--f-titulo); color: var(--terracota); margin-inline: 2px; vertical-align: baseline }`. `.sep { color: var(--tinta-2); margin-inline: 12px }` (6,3:1).

### 3.4 Espacios

**Se conserva:** la cabecera en capítulo con la bajada a la derecha; el arranque asimétrico (Living en 7 columnas a 4:3 y Cocina en 5 a 4:5, bajada 96 px); Dormitorio 1 junto a la frase destacada; pies con título en Fraunces y descripción en tinta secundaria; y el carrusel al 82 % con barra de progreso en teléfono.
**Se corrige:** la sección de unos 2.970 px con cuatro filas y el «Recibidor» huérfano; la fila de tres con aspecto de cuadrícula genérica; los títulos en `div`; las imágenes sueltas sin `<picture>`; la falta de `data-*`; la frase que parecía reseña; y el carrusel pegado al borde.

```html
<section id="espacios" class="seccion" aria-labelledby="t-espacios">
  <div class="contenedor">
    <header class="cabecera capitulo aparece">
      <h2 id="t-espacios">Espacios</h2>
      <p class="bajada" data-contenido="espacios.bajada">(semilla)</p>
    </header>
    <div class="galeria">
      <div class="espacios desliza" tabindex="0" role="region" aria-label="Espacios del departamento">
        <article class="espacio e-living aparece">
          <figure data-fotos="living"><picture>
            <source type="image/webp" srcset="img/living-sofa-800.webp 800w, img/living-sofa-1600.webp 1600w" sizes="(min-width: 1100px) 700px, (min-width: 700px) calc(100vw - 64px), 82vw">
            <img src="img/living-sofa-800.jpg" alt="(alt actual)" width="800" height="500" loading="lazy" decoding="async"></picture></figure>
          <h3 data-contenido="espacio.living.titulo">Living</h3>
          <p data-contenido="espacio.living.texto">(semilla)</p>
        </article>
        <!-- e-cocina (cocina-*), e-dorm1 (dorm1-*), e-dorm2 (dorm2-*), e-banos (bano-*), e-balcon (balcon-*), e-recibidor (recibidor-*),
             con data-fotos = cocina | dorm1 | dorm2 | banos | balcon | recibidor y data-contenido = espacio.<clave>.titulo / .texto -->
      </div>
      <div class="progreso" aria-hidden="true"><i></i></div>
      <p class="frase">Dos dormitorios, cada uno con cama king y closet corredero.</p>
    </div>
  </div>
</section>
```

- **Cabecera de capítulo** (`.cabecera.capitulo`): `h2` en `--t-capitulo`. En teléfono, apilada con `gap: 12px`. Desde 1000 px: `display: grid; grid-template-columns: minmax(0,1fr) minmax(0,42ch); column-gap: 48px; align-items: last baseline`. `margin-bottom: var(--cab-y)`.
- **Tarjeta:** sin caja, sin borde ni sombra (se quita `.tarjeta`). `figure { margin: 0; border-radius: var(--radio-img); overflow: hidden; background: var(--arena) }`, con la imagen al 100 % y `object-fit: cover`. `h3` en `--t-pie`, 16 px arriba. `p` en 16 px, tinta secundaria, `max-width: 52ch` y `white-space: pre-line`, 4 px arriba. Se eliminan los `figcaption` actuales («Zona social», «Acceso», etc.): repetían el título.
- **La frase:** `p.frase`, en `--t-cita` y cursiva, color `--terracota-osc` (7,7:1). **Sin comillas.** Un `::before` dibuja un filete de 48 × 2 px en terracota, 24 px arriba. El texto es un dato concreto, sacado de las descripciones de `dorm1` y `dorm2`; no repite «ladrillo» ni «roble», y no es editable.
- **Teléfono (< 700):** `.galeria` en bloque. `.espacios` es un carrusel (2.7) con `flex: 0 0 82%` (60 % desde 560 px) y todas las imágenes a 4:5. Luego la `.progreso` y la `.frase` con `margin-top: 32px`.
- **Tableta (700 a 1099):** `.galeria { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 48px 16px }` y `.espacios { display: contents }`. Living ocupa `grid-column: 1 / -1` a 16:10. Cocina y Dormitorio 1 van a 4:5; el resto, a 3:2. La `.frase` ocupa `grid-column: 1 / -1`. La `.progreso` se oculta. El resultado son cinco filas completas, sin huérfanos.
- **Computador (≥ 1100):** `.galeria { grid-template-columns: repeat(12, minmax(0,1fr)); column-gap: 24px; row-gap: var(--fila-y) }` y `.espacios { display: contents }`.

  | Pieza | Posición | Proporción |
  |---|---|---|
  | `.e-living` | `grid-column: 1 / span 7; grid-row: 1` | 4:3 |
  | `.e-cocina` | `grid-column: 8 / span 5; grid-row: 1; margin-top: 96px` | 4:5 |
  | `.e-dorm1` | `grid-column: 1 / span 5; grid-row: 2` | 4:5 |
  | `.frase` | `grid-column: 7 / span 6; grid-row: 2; align-self: center` | — |
  | `.e-dorm2`, `.e-banos`, `.e-balcon`, `.e-recibidor` | `span 3` desde las columnas 1, 4, 7 y 10; `grid-row: 3` | 3:2 |

  La fila D se elimina y la sección se acorta unos 700 px (inferido). En la fila de cuatro, los pies llevan el texto completo del portal (3 o 4 líneas a unos 286 px), sin cortarlo.
- `sizes`: Cocina y Dormitorio 1, `(min-width: 1100px) 500px, (min-width: 700px) calc(50vw - 40px), 82vw`. La fila de cuatro, `(min-width: 1100px) 290px, (min-width: 700px) calc(50vw - 40px), 82vw`. Los nombres de archivo son los actuales.
- **`data-galeria`:** no se usa en v4. Si se agrega después, hay que darle estilo a `ul.miniaturas`, que hoy no tiene CSS.

### 3.5 Materiales (franja arena)

**Se conserva:** la franja arena con cinco muestras nombradas y el lugar donde está cada una.
**Se corrige:** las cinco imágenes completas ampliadas con `transform: scale(3)` y un `transform-origin` en línea, el hueco de 204 px a la derecha, los datos sin verificar, la bajada repetida y el carrusel sin margen.

```html
<section id="materiales" class="seccion fondo-arena" aria-labelledby="t-materiales">
  <div class="contenedor">
    <header class="cabecera aparece">
      <h2 id="t-materiales">Materiales</h2>
      <p class="bajada">Las mismas texturas del modelo 3D que ves en las imágenes y en el recorrido.</p>
    </header>
    <div class="muestras desliza" tabindex="0" role="region" aria-label="Muestras de materiales">
      <ul role="list">
        <li class="muestra"><img src="img/material-ladrillo-360.webp" alt="" width="360" height="360" loading="lazy" decoding="async">
          <h3>Ladrillo a la vista</h3><p>Muro del living</p></li>
        <!-- material-concreto: «Concreto visto» / «Cielo raso»
             material-roble:    «Tablas de roble» / «Mueble de TV y repisas»
             material-cuero:    «Cuero coñac» / «Sofá y cabecero del dormitorio 2»
             material-acero:    «Acero negro» / «Veladores y mesa bistró» -->
      </ul>
    </div>
  </div>
</section>
```

- `alt=""`: el nombre ya está al lado como texto. Los lugares salen de las descripciones de la semilla: living, cocina, dorm1, dorm2 y balcón. Se quitan «con marcas de encofrado» y «marcos», que no están verificados.
- **Cabecera de sección** (sin `.capitulo`): `h2` en `--t-seccion`, con la bajada debajo (`max-width: 60ch`, 16 px de separación).
- Muestra: imagen cuadrada (`aspect-ratio: 1`), `--radio-img`, `--sombra-1` y fondo `#DFD7CC` mientras carga. `h3` en `--t-material`, 14 px arriba. `p` en `--t-nota` y tinta secundaria (5,6:1 sobre arena).
- **Teléfono:** `.muestras` es un carrusel (2.7). El `ul` va en flex con `gap: 16px` y cada `li` en `flex: 0 0 140px`: se ven unas dos muestras y media, lo que muestra que hay más.
- **Desde 700 px:** sin desplazamiento. `.muestras { overflow: visible; margin: 0; padding: 0 }` y `ul { display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 16px }` (24 px desde 1000). A 1280, cada muestra mide unos 224 px de lado y llena el contenedor.
- **Imágenes:** recortes propios de 360 × 360 generados por `build.py` (ver 6.5). **No** se amplía el render completo.

### 3.6 Recorrido 3D (bloque carbón, el único)

**Se conserva:** el bloque carbón; las instrucciones en filas separadas por filetes, cada una con la entrada en negrita y una raya; un solo botón; la nota del modelo al 70 %; y la fila «En teléfono» primero en teléfono.
**Se corrige:** la captura que no era enlace, los destinos rotos (`#`, `#tour`) y la fila «Descarga» que se había perdido. Las instrucciones del teléfono se alinean con el visor v3 (`tour/index.html`: «palanca … a la izquierda para caminar y arrastra el resto de la pantalla para mirar»).

```html
<section id="tour" class="seccion fondo-carbon" aria-labelledby="t-tour">
  <div class="contenedor recorrido">
    <header class="cabecera capitulo aparece">
      <h2 id="t-tour">Recorrido 3D</h2>
      <p class="bajada">Camina por el departamento en primera persona, en el computador o en el teléfono.</p>
    </header>
    <figure class="recorrido-media aparece">
      <a class="recorrido-enlace" href="tour/" tabindex="-1" aria-hidden="true">
        <picture><source type="image/webp" srcset="img/maqueta-800.webp 800w, img/maqueta-1600.webp 1600w" sizes="(min-width: 1000px) 700px, 100vw">
          <img src="img/maqueta-1600.jpg" alt="" width="1600" height="1000" loading="lazy" decoding="async"></picture>
        <span class="icono-3d"><svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg></span>
      </a>
      <figcaption>La maqueta completa, vista desde arriba y sin cielo.</figcaption>
    </figure>
    <div class="recorrido-texto">
      <ul class="filas">
        <li><b>En computador</b> — se camina con el teclado (W A S D o las flechas) y se mira con el ratón.</li>
        <li class="f-telefono"><b>En teléfono</b> — se camina con la palanca de abajo a la izquierda y se mira arrastrando el resto de la pantalla.</li>
        <li><b>Puertas y ventanal</b> — se abren con un clic o un toque.</li>
        <li><b>Descarga</b> — en el teléfono carga una versión con texturas más livianas.</li>
      </ul>
      <a class="boton primario" href="tour/">Entrar al recorrido</a>
      <p class="nota">Modelo hecho desde el plano de arquitectura, sin cotas: las alturas y las terminaciones son una propuesta de decoración.</p>
    </div>
  </div>
</section>
```

- **`.fondo-carbon`:** `background: var(--carbon); color: var(--papel); --anillo: var(--papel)`. El `h2` y la bajada van en papel.
- **La captura como enlace:** es un duplicado del botón, así que va fuera del orden de tabulación y de la lectura (`tabindex="-1"`, `aria-hidden`). Lleva `display: block; position: relative`, `--radio-img`, `overflow: hidden`, borde `1px solid rgba(255,255,255,.08)`, `--sombra-oscura` y la imagen a 16:10. `.icono-3d` es un círculo de 64 px centrado, con borde de 1,5 px en `rgba(246,241,234,.9)` y fondo `rgba(20,16,12,.35)`. Al pasar el cursor: la imagen a `scale(1.03)` y el velo a `.5`.
- **`figcaption`:** `--t-nota`, en redonda, `rgba(246,241,234,.7)`, 12 px arriba.
- **`.filas`:** sin viñetas. Cada `li` lleva `padding: 16px 0` y `border-top: 1px solid rgba(246,241,234,.16)`; el último, también borde inferior. El texto va en 16 px a `rgba(246,241,234,.9)` (11,6:1). `b` en 600, color papel. Bajo 700 px: `.filas { display: flex; flex-direction: column }` y `.f-telefono { order: -1 }`, que son elementos independientes.
- **Botón:** 32 px arriba. A todo el ancho bajo 700 px.
- **`.nota`:** `--t-nota`, `rgba(246,241,234,.7)` (7,6:1), 24 px arriba.
- **Desde 1000 px:** `.recorrido { display: grid; grid-template-columns: repeat(12, minmax(0,1fr)); column-gap: 48px }`. La `.cabecera` ocupa `1 / -1`, igual que en Espacios, para que «Recorrido 3D» quepa a 88 px sin partirse. `.recorrido-media` ocupa `1 / span 7` y `.recorrido-texto`, `8 / span 5` con `align-self: center`. En teléfono todo va apilado en el orden del DOM.

### 3.7 Lo que hay (equipamiento)

**Se conserva:** tres columnas de texto sin cajas, con títulos en Fraunces y filetes.
**Se corrige:** los títulos en `div`, «TV de 55"» con comillas rectas y «Wi-Fi» cuya descripción era solo «ejemplo».

- Cabecera de sección (como en Materiales) con la bajada «Lo que se ve en el modelo, más lo marcado como ejemplo en este sitio de demostración.».
- `ul.equipos` con 8 `li`, cada uno con `h3` en `--t-item` y `p` en 16 px de tinta secundaria. `columns: 1` en teléfono, `2` desde 700 px y `3` desde 1000 px, con `column-gap: 48px`. `li { break-inside: avoid; padding: 20px 0; border-bottom: 1px solid var(--linea) }` y `ul { border-top: 1px solid var(--linea) }`. Por columnas, el orden queda como en el modelo: cocina, lavadora y TV; baños, closets y balcón; Wi-Fi y ropa de cama.
- Textos: «Cocina equipada» / «Anafe, campana, horno y refrigerador.»; «Lavadora» / «En un nicho con puerta plegable.»; **«TV de 55 pulgadas»** / «Sobre el mueble flotante del living.»; «Dos baños» / «Tina con ducha y mampara en cada uno.»; «Closets» / «Correderos, en los dos dormitorios.»; «Balcón» / «Mesa bistró y dos sillas.»; **«Wi-Fi» / «Valor de ejemplo del sitio de demostración.»**; «Ropa de cama» / «Sábanas y toallas (ejemplo).».

### 3.8 Tarifas (bloque terracota oscura)

**Se conserva:** el bloque terracota oscura; una tabla editorial de rótulo y valor entre filetes al 25 %; y el botón invertido color papel.
**Se corrige:** los dos titulares que competían (72 contra 64 px); el precio repetido en la tabla; la tarjeta que no llegaba a la altura de la columna y dejaba un hueco; los `input type=date` nativos; el segundo mecanismo de reserva sin ocupados; los precios escritos a mano; la tabla hecha de `div`; y los cortes en teléfono («CLP / 58.000», «desde 15:00 / hasta / 11:00»).

```html
<section id="tarifas" class="seccion fondo-terracota" aria-labelledby="t-tarifas">
  <div class="contenedor tarifas">
    <div class="tarifas-info">
      <h2 id="t-tarifas" class="t-capitulo">Tarifas</h2>
      <p class="precio-grande"><span class="monto" data-precio="noche">CLP 58.000</span><span class="precio-nota">por noche · ejemplo</span></p>
      <p class="bajada">Envías una solicitud con tus fechas y te respondemos por correo para confirmarla. No se cobra nada en línea.</p>
      <table class="tabla-tarifas"><tbody>
        <tr><th scope="row">Limpieza, una vez (ejemplo)</th><td><span data-precio="limpieza">CLP 15.000</span></td></tr>
        <tr><th scope="row">Estadía</th><td>de 2 a 30 noches</td></tr>
        <tr><th scope="row">Huéspedes</th><td>hasta 4</td></tr>
        <tr><th scope="row">Llegada (ejemplo)</th><td><span data-contenido="condiciones.llegada">desde 15:00</span></td></tr>
        <tr><th scope="row">Salida (ejemplo)</th><td><span data-contenido="condiciones.salida">hasta 11:00</span></td></tr>
        <tr><th scope="row">Pago</th><td>se acuerda al confirmar</td></tr>
      </tbody></table>
    </div>
    <div class="tarifas-accion">
      <p>Elige tus noches en el calendario y envía la solicitud. Te confirmamos por correo.</p>
      <a class="boton invertido" href="reserva.html#calendario">Ver fechas</a>
    </div>
  </div>
</section>
```

- **`.fondo-terracota`:** `background: var(--terracota-osc); color: var(--papel); --anillo: var(--papel)`.
- **Precio:** `.monto { display: block; font: 400 var(--t-precio)/1 var(--f-titulo); white-space: nowrap; font-variant-numeric: tabular-nums }`, 20 px bajo el `h2`. `.precio-nota { display: block; margin-top: 8px; font-size: 16px; color: rgba(246,241,234,.88) }`, en su propia línea. La fila «Noche» se quita de la tabla.
- **Bajada:** en `--t-bajada` y `rgba(246,241,234,.9)`. 24 px arriba y 32 abajo.
- **Tabla:** `width: 100%; border-collapse: collapse`. Cada fila lleva `border-top: 1px solid rgba(246,241,234,.25)`; la última, también borde inferior. `th` a la izquierda, en 400 de 16 px, `rgba(246,241,234,.88)` (6,4:1) y `padding: 15px 16px 15px 0`. `td` a la derecha, en Public Sans 600 de 16 px, papel, tabular y `white-space: nowrap`: la misma fuente en todos los anchos (el Fraunces 600 de escritorio se descarta).
- **`.tarifas-accion`:** `p` en `--t-bajada`, `rgba(246,241,234,.9)` y `max-width: 36ch`, con el botón invertido 24 px debajo. En teléfono y tableta, 32 px bajo la tabla, con el botón a todo el ancho bajo 700 px.
- **Desde 1000 px:** `.tarifas { display: grid; grid-template-columns: repeat(12, minmax(0,1fr)); column-gap: 48px }`. `.tarifas-info` ocupa `1 / span 6`; `.tarifas-accion`, `8 / span 5` con `align-self: end`, de modo que su botón queda alineado con el filete inferior de la tabla, sin hueco.
- **Precios:** los rellena `sitio.js` desde `TARIFA` y los reemplaza `contenido-publico.js` si el dueño los editó. El texto dentro del `span` es el respaldo sin JS. **Ningún** precio queda escrito fuera de un `[data-precio]`.
- Se elimina `form#reserva-rapida` y también su bloque en `sitio.js` (ver 6.2).

### 3.9 Preguntas

**Se conserva:** el acordeón tipográfico, con el título en 4 columnas y las preguntas en 8, y el +/− terracota del teléfono.
**Se corrige:** el acordeón hecho con `div` sin teclado, los `button` sin `aria-expanded`, los manejadores `onclick` en línea, las respuestas que faltaban o que Stitch reescribió, la falta de enlace a la privacidad y el nombre «tour».

- Se usa `details` y `summary` sin JS, sobre el CSS actual. El primer `details` va con `open`.
- `summary`: `list-style: none; display: flex; justify-content: space-between; align-items: center; gap: 16px; min-height: 64px; padding: 20px 0`, en `--t-pregunta` y tinta. El ícono va en `::after`: 14 × 14 px, dos barras terracota de 2 px dibujadas con `background` (`linear-gradient`). Con `[open]` se oculta la barra vertical. Sin `content` de texto.
- `details { border-bottom: 1px solid var(--linea) }` y, en el contenedor, `border-top`. La respuesta va en 16/1,6, tinta secundaria, `max-width: 68ch`, `margin: 0 0 24px`.
- Desde 1000 px: `.preguntas-grid { display: grid; grid-template-columns: repeat(12, minmax(0,1fr)); column-gap: 48px }`. `h2` (en `--t-seccion`) en `1 / span 4`; la lista, en `5 / span 8`. En teléfono, apilado, con 24 px entre el título y la lista.
- **Textos idénticos en todos los anchos.** Son los seis de `index.html` con dos cambios: «sólo» pasa a «solo» y la pregunta 5 se ajusta al visor v3.
  1. **¿Las imágenes son fotos del departamento?** No. Son renders de un modelo 3D construido desde el plano de arquitectura, que no trae cotas: las medidas se infirieron con un margen de ± 5 % y las alturas, los muebles y las terminaciones son una propuesta de decoración.
  2. **¿Cómo se confirma una reserva?** Eliges las fechas y envías la solicitud. Queda pendiente y bloquea esas noches en el calendario hasta que te respondemos por correo para confirmarla o rechazarla.
  3. **¿Se paga en línea?** No. El sitio no pide ni guarda datos de pago. La forma de pago se acuerda al confirmar.
  4. **¿Dónde está?** La dirección se entrega al confirmar la reserva. Este es un sitio de demostración y no publica la ubicación.
  5. **¿El recorrido 3D funciona en el teléfono?** Sí. En el teléfono se camina con la palanca de abajo a la izquierda y se mira arrastrando el resto de la pantalla. Carga una versión con texturas más livianas.
  6. **¿Qué hacen con mis datos?** Se usan solo para responder tu solicitud. Detalle en la `<a href="privacidad.html">política de privacidad</a>`.

### 3.10 Pie y barra fija

- El pie, según 2.6.
- La barra fija, según 2.3:
  `<div class="barra-movil"><p class="precio"><span data-precio="noche">CLP 58.000</span><small>por noche · ejemplo</small></p><a class="boton primario" href="reserva.html">Reservar</a></div>`.
  Se muestra solo después del hero y se oculta sobre Tarifas.

---

## 4. Reserva (`reserva.html`), sección por sección

Corrige el viewport con `user-scalable=no` y `maximum-scale=1.0`, que debe quedar `width=device-width, initial-scale=1, viewport-fit=cover` como hoy. También quita el `outline: none` global y Tailwind, y soluciona los hooks que no calzaban, la casilla premarcada, lo principal fuera de la primera pantalla, el resumen demasiado alto, las flechas de mes mal ubicadas, los días de 41 px, el botón fuera del formulario y los estados que faltaban.

### 4.1 Encabezado
Ver 2.2. Siempre sólido, con «Reservar» y `aria-current="page"`. Menú con `./#espacios`, `./#tour`, `./#tarifas` y `./#preguntas`.

### 4.2 Introducción (solo texto, sin imagen)

```html
<main id="contenido" class="pagina">
  <div class="contenedor">
    <header class="intro">
      <nav class="migas" aria-label="Migas"><a href="./">Inicio</a><span aria-hidden="true">/</span><span aria-current="page">Reserva</span></nav>
      <h1 class="t-reserva">Reserva</h1>
      <p class="lema-reserva">sin cobro en línea.</p>
      <p class="bajada">Elige tus noches en el calendario y envía la solicitud. Queda pendiente hasta que te confirmamos por correo.</p>
    </header>
    <p id="aviso-sim" class="mensaje" hidden>Modo local de prueba: disponibilidad y envíos simulados en este navegador.</p>
    <div class="reserva">…4.3…</div>
    <section id="exito" …>…4.9…</section>
  </div>
</main>
```

- `.pagina { padding: calc(var(--barra-alto) + 16px) 0 64px }`. Desde 1000 px, `calc(var(--barra-alto) + 32px)`.
- `h1` en `--t-reserva`, con interlineado de 0,95. `.lema-reserva` en `--t-cursiva-reserva`, cursiva, terracota (5,3:1), 4 px arriba. Bajada en `--t-bajada`, tinta secundaria.
- **Teléfono:** las migas se ocultan bajo 700 px (el logo ya lleva al inicio); la bajada va 10 px bajo el lema; `.intro` lleva 24 px debajo.
- **Desde 700 px:** migas en `--t-meta`, con `a` de `padding-block: 12px` y 8 px debajo.
- **Desde 1000 px:** `.intro { display: grid; grid-template-columns: repeat(12, minmax(0,1fr)); column-gap: 48px; padding-bottom: 32px; border-bottom: 1px solid var(--linea); margin-bottom: 32px }`. Migas, H1 y lema en `1 / span 7`. La bajada en `8 / span 5` (`grid-row: 2 / span 2; align-self: end`).
- **Meta de altura** (inferida desde el CSS): a 1280 × 800, la primera fila de días empieza cerca de 520 px (el máximo aceptable es 600). A 390 × 664, antes de la barra fija se ven la cabecera del calendario y cuatro filas de días.
- No hay imagen del dormitorio 1: se eliminan la de 16:10 y la versión `div` con `role=img` del teléfono.

### 4.3 Retícula de la página

`.reserva` tiene **cuatro hijos directos, en este orden en el DOM:** `section#calendario`, `aside.resumen`, `section.despues` y `form#formulario`. Todos los `id` actuales se conservan.

```css
.reserva { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px;
  grid-template-areas: "cal" "res" "despues" "form"; }
.reserva > * { min-width: 0; }
#calendario { grid-area: cal; } .resumen { grid-area: res; } .despues { grid-area: despues; } #formulario { grid-area: form; }
@media (min-width: 1000px) {
  .reserva { grid-template-columns: minmax(0, 1fr) 380px; gap: 32px; align-items: start;
    grid-template-areas: "cal res" "despues res" "form res"; }
  .resumen { position: sticky; top: calc(var(--barra-alto) + 24px);
    max-height: calc(100svh - var(--barra-alto) - 48px); overflow: auto; }
}
```

El orden de lectura y de tabulación coincide con el visual del teléfono. En computador, el foco pasa por el botón del resumen antes que por los campos. Es aceptable, porque el envío lleva el foco al primer campo con error (ver 6.3).

### 4.4 Fechas (calendario)

**Se conserva:** la trama diagonal en los ocupados; los extremos del rango llenos en terracota; los días intermedios en `#F2DDD2` con texto `#7F3515` (6,6:1); el punto de «hoy»; las cifras tabulares; los meses en Fraunces minúscula; la leyenda; un mes en teléfono y dos donde quepan; y el rango en una línea propia bajo la cuadrícula.
**Se corrige:** 35 baldosas con borde por mes; el rango partido en baldosas; el tachado; las flechas alrededor del texto del rango; celdas de 41 px y flechas de 40; y el marcado estático de `div`, que no se usa: el calendario lo genera `reserva.js`.

```html
<section id="calendario" class="tarjeta bloque" aria-labelledby="t-cal">
  <h2 id="t-cal">Fechas</h2>
  <div class="cal-cuerpo">
    <div class="cal-nav">
      <button id="mes-ant" type="button" aria-label="Mes anterior"><svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><polyline points="15 18 9 12 15 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
      <button id="mes-sig" type="button" aria-label="Mes siguiente"><svg …><polyline points="9 18 15 12 9 6" …/></svg></button>
    </div>
    <div id="meses" class="calendario"></div>
  </div>
  <p id="rango-texto" class="rango-texto" aria-live="polite" tabindex="-1">Elige la llegada</p>
  <div class="leyenda" aria-hidden="true">
    <span><i class="m-disp">8</i>Disponible</span><span><i class="m-ocup">8</i>Ocupado</span><span><i class="m-sel">8</i>Tu selección</span>
  </div>
  <p id="cal-error" class="mensaje error" hidden role="alert"></p>
</section>
```

- **Las dos flechas van antes de `#meses` en el DOM**, para que el foco pase por ellas antes que por los 30 a 60 días. Visualmente, `.cal-cuerpo { position: relative }` y `.cal-nav button { position: absolute; top: 0 }`, con `#mes-ant { left: 0 }` y `#mes-sig { right: 0 }`. Así quedan a la izquierda del primer mes y a la derecha del último, a la altura de los nombres de mes. En teléfono, a los lados del único mes. Botones de **48 × 48** en círculo, con `border: 1px solid var(--linea)`, fondo tarjeta, ícono en tinta y hover con borde tinta. `:disabled` a opacidad 0,35.
- **`#meses`:** `display: grid; grid-template-columns: repeat(var(--meses, 1), minmax(0, 1fr)); column-gap: 32px`. JS fija `--meses` con la cantidad que pinta (ver 6.4). `.mes h3`: Fraunces 400 de 22 px, minúscula (`text-transform: lowercase`), centrado, `line-height: 48px` y 8 px debajo. `reserva.js` escribe el mes con `Intl` (es-CL), que puede decir «octubre de 2026»: no se cambia.
- **Tabla:** `.mes table { width: 100%; max-width: 392px; margin-inline: auto; border-collapse: separate; border-spacing: 0; table-layout: fixed }`. `th` en `--t-meta`, tinta secundaria, `padding: 6px 0`. `td { padding: 0; height: 48px }`.
- **Día** (`button.dia`, generado por JS):
  ```css
  .dia { position: relative; isolation: isolate; display: grid; place-items: center; width: 100%; height: 48px;
    border: 0; background: transparent; border-radius: var(--radio); cursor: pointer;
    font: 500 16px/1 var(--f-texto); font-variant-numeric: tabular-nums; color: var(--tinta); }
  .dia::before { content: ""; position: absolute; z-index: -1; top: 2px; bottom: 2px; left: 50%; width: 44px; margin-left: -22px; border-radius: var(--radio); } /* chip */
  .dia::after  { content: ""; position: absolute; z-index: -2; top: 2px; bottom: 2px; left: 0; right: 0; }                               /* banda */
  .dia:hover:not(:disabled)::before { background: var(--arena); }
  .dia:disabled { cursor: not-allowed; color: #9C9388; }
  .dia.pasado { color: #B5ACA1; }
  .dia.ocupado::before { background: repeating-linear-gradient(45deg, var(--linea) 0 1.5px, transparent 1.5px 6px); } /* sin tachado */
  .dia.en-rango { color: var(--terracota-osc); }
  .dia.en-rango::after { background: var(--terracota-suave); }
  .dia.extremo { color: #fff; font-weight: 600; }
  .dia.extremo::before { background: var(--terracota); }
  .calendario:has(.salida) .dia.llegada::after { background: var(--terracota-suave); left: 50%; }
  .dia.salida::after { background: var(--terracota-suave); right: 50%; }
  /* la banda se redondea al empezar o terminar una fila, y al empezar o terminar el mes */
  td:first-child > .dia.en-rango::after, td:empty + td > .dia.en-rango::after { left: 2px; border-radius: var(--radio) 0 0 var(--radio); }
  td:last-child > .dia.en-rango::after, td:has(+ td:empty) > .dia.en-rango::after { right: 2px; border-radius: 0 var(--radio) var(--radio) 0; }
  td:last-child > .dia.llegada::after, td:first-child > .dia.salida::after { display: none; }
  .dia.hoy { background-image: radial-gradient(circle, currentColor 2.5px, transparent 3px);
    background-repeat: no-repeat; background-size: 6px 6px; background-position: 50% calc(100% - 7px); }
  .dia.hoy:not(.extremo) { color: var(--tinta); }
  .dia:focus-visible { outline-offset: 0; z-index: 1; }
  ```
  El resultado es una banda continua, sin espacio entre celdas: el chip visible mide 44 px y el área táctil 48 × el ancho de la celda. `.llegada`, `.salida` y `.hoy` son clases nuevas que agrega `reserva.js` (6.4). Si todavía no hay salida, la llegada es un chip solo.
- **Teléfono (< 560):** `#calendario` deja de ser tarjeta y va a sangre, porque en una tarjeta no caben 7 × 48. `background: none; border: 0; border-block: 1px solid var(--linea); border-radius: 0; box-shadow: none; margin-inline: calc(-1 * var(--margen)); padding: 20px 4px`. `h2`, `.rango-texto`, `.leyenda` y `#cal-error` llevan `padding-inline: calc(var(--margen) - 4px)`, y la tabla `max-width: none`. Las celdas quedan en (ancho − 8) / 7: 52 px a 375 y 44,6 px a 320. Este último es el único caso bajo 48, y queda dentro de la mínima de WCAG 2.5.8 (24 px).
- **Desde 560 px:** tarjeta con fondo `--tarjeta`, `border: 1px solid var(--linea)`, `--radio-img`, `--sombra-1` y `padding: 24px` (32 desde 1000). `h2` en `--t-tarjeta`, 24 px debajo.
- **`.rango-texto`:** 16 px en 500 y tinta, `margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--linea)`. Recibe el foco de respaldo que ya usa `reserva.js` (por eso lleva `tabindex="-1"`).
- **Leyenda:** `display: flex; flex-wrap: wrap; gap: 8px 24px; margin-top: 12px`, en `--t-meta` y tinta secundaria. Cada `i` es una muestra de 24 × 24 px con `--radio` y un número de 12 px: `.m-disp` solo con el número, `.m-ocup` con la trama y `.m-sel` con fondo terracota y texto blanco.

### 4.5 Resumen

**Se conserva:** «Total estimado» con la cifra en Fraunces, «Valores de ejemplo. Sin cobro en línea.» junto al total y el bloque arena en teléfono.
**Se corrige:** una tarjeta fija de unos 748 px, con el botón oculto en ventanas de menos de 780 px de alto, y la imagen repetida del living a 16:10.

```html
<aside class="resumen" aria-labelledby="t-resumen">
  <figure class="resumen-img" data-fotos="living"><picture>
    <source type="image/webp" srcset="img/living-800.webp 800w" sizes="380px">
    <img src="img/living-800.jpg" alt="" width="800" height="500" loading="lazy" decoding="async"></picture></figure>
  <div class="cuerpo">
    <h2 id="t-resumen">Resumen</h2>
    <div class="linea"><span>Llegada</span><span id="s-entrada">—</span></div>
    <div class="linea"><span>Salida</span><span id="s-salida">—</span></div>
    <div class="linea"><span id="s-noches-txt">Noches</span><span id="s-alojamiento">—</span></div>
    <div class="linea"><span>Limpieza (ejemplo)</span><span id="s-limpieza">—</span></div>
    <div class="linea total"><span>Total estimado</span><b id="s-total">—</b></div>
    <p class="nota">Valores de ejemplo. Sin cobro en línea: te confirmamos por correo.</p>
    <button id="enviar" class="boton primario grande bloque" type="submit" form="formulario" aria-disabled="true">Solicitar</button>
    <a class="enlace-dudas" href="./#preguntas">¿Dudas? Revisa las preguntas frecuentes</a>
  </div>
</aside>
```

- `.linea`: flex con `justify-content: space-between`, 16 px, `padding: 10px 0` y `border-bottom: 1px solid var(--linea)`. El rótulo va en tinta secundaria y el valor en tinta, 500 y tabular. `.linea.total`: `align-items: baseline`, sin borde inferior, 12 px arriba. El rótulo en 600 de 17 px y `#s-total` en `--t-total`. `.nota` en `--t-nota`, tinta secundaria.
- **Teléfono y tableta (< 1000):** bloque arena, sin borde, con `--radio-img` y `padding: 20px`. `h2` en 24 px. Se ocultan `#enviar` (el envío está en la barra) y `.resumen-img`. `.enlace-dudas` queda visible.
- **Computador (≥ 1000):** tarjeta (`--tarjeta`, borde, `--radio-img`, `--sombra-1`, `overflow: hidden`) y `.cuerpo { padding: 24px; display: grid; gap: 4px }`. `h2` en 28 px. `#enviar` con 20 px arriba. `.enlace-dudas` en 15 px, tinta secundaria, subrayado, centrado, `display: block; padding-block: 12px`.
- **Imagen:** se oculta por defecto. Solo se muestra con `@media (min-width: 1000px) and (min-height: 860px)`, en 21:9 (unos 163 px). Con eso, y el `max-height` de 4.3, el botón «Solicitar» se ve siempre a 1366 × 768 y a 1280 × 800.
- Estados de los valores: ver 4.10.

### 4.6 Qué pasa después

**Se conserva:** tres pasos sin numerar, en tres columnas con filetes verticales. **Se corrige:** el `h3` sin `h2`, y la ubicación después del formulario.

```html
<section class="despues" aria-labelledby="t-despues">
  <h2 id="t-despues">Qué pasa después</h2>
  <div class="pasos">
    <div><h3>Queda pendiente</h3><p>Tu solicitud bloquea esas noches mientras la revisamos.</p></div>
    <div><h3>Te escribimos</h3><p>Te respondemos al correo para confirmarla o proponer otras fechas.</p></div>
    <div><h3>Acordamos el pago</h3><p>Al confirmar acordamos el pago y te enviamos la dirección.</p></div>
  </div>
</section>
```

- `h2` en `--t-tarjeta`, 16 px debajo. `h3` en `--t-item`. `p` en 16 px, tinta secundaria, 4 px arriba.
- En teléfono, filas con `padding: 14px 0` y `border-top: 1px solid var(--linea)`.
- Desde 760 px, `grid-template-columns: repeat(3, 1fr)`; la 2.ª y la 3.ª columna llevan `border-left: 1px solid var(--linea); padding-left: 32px`, y la 1.ª y la 2.ª, `padding-right: 32px`.

### 4.7 Tus datos

**Se conserva:** las etiquetas visibles, «(opcional)», los campos de 48 px, el aviso de demostración y el anillo de foco del campo Nombre (ahora en todo).
**Se corrige:** la casilla premarcada, «Huéspedes» como `label` sin `for`, el valor en `span` que no se anunciaba, el sufijo «2 huéspedes», los botones de 32 y 44 px, los bordes de 1,5:1, los campos de 15 px y los ejemplos que parecían valores ya cargados.

Parte del marcado actual del formulario y conserva todos sus `id`:

- `form#formulario.tarjeta.bloque` con `novalidate` y `aria-labelledby="t-datos"`. `h2#t-datos` «Tus datos», en `--t-tarjeta`. `p.aviso-demo` en `--t-nota`, tinta secundaria: «Es un sitio de demostración: usa un nombre y un correo inventados.».
- Campos en `display: grid; gap: 20px`, en este orden:
  1. **Huéspedes:** `span.rotulo#rot-huespedes`, más `div.contador[role=group][aria-labelledby=rot-huespedes]` con `button#menos`, `output#huespedes[aria-live=polite]` (solo el número) y `button#mas`. El contenedor lleva `display: inline-flex; align-items: center; height: 50px; border: 1px solid var(--tinta-2); border-radius: var(--radio); background: var(--papel)`. Botones de **48 × 48**, con la fuente en 500 de 20 px y hover arena. El `output` va en 600 de 17 px, con `min-width: 56px` y centrado.
  2. **Nombre:** `input#nombre` con `autocomplete=name`, `maxlength=80` y `required`, sin `value`.
  3. **Correo y teléfono:** `div.dos` con `grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px`. Contiene `input#email` (`type=email`, `autocomplete=email`, `maxlength=120`, `required`) e `input#telefono` (`type=tel`, `autocomplete=tel`, `maxlength=20`). Sin marcadores de posición.
  4. **Mensaje:** `textarea#mensaje` con `maxlength=1000` y el marcador de 2.4.
  5. **Campo trampa:** `div.trampa[aria-hidden=true]` con `input#sitio[tabindex=-1]`, sin cambios.
  6. **Casilla:** `label.check` con `input#acepta` (`type=checkbox`, `required`, **sin `checked`**) y el texto «Acepto que usen mis datos solo para responder esta solicitud (`<a href="privacidad.html">privacidad</a>`).».
  7. `p#form-error.mensaje.error` con `hidden` y `role=alert`.
- La tarjeta lleva `padding: 20px` en teléfono y `32px` en computador.

### 4.8 Barra fija (teléfono y tableta)

```html
<div class="barra-movil">
  <p class="precio"><span id="m-total">Elige tus fechas</span><small id="m-noches">sin cobro en línea</small></p>
  <button class="boton primario" type="submit" form="formulario" id="enviar-movil" aria-disabled="true">Solicitar</button>
</div>
```

El estilo es el de 2.3. `#m-total` va en Fraunces: 600 de 22 px con un total y 500 de 20 px con «Elige tus fechas». Los estados, en 4.10.

### 4.9 Éxito

- `section#exito.tarjeta.exito` con `hidden`, `tabindex="-1"` y `aria-labelledby="t-exito"`. Va después de `.reserva`, y `exito()` le pasa el foco. Lleva `border-left: 3px solid var(--oliva)` y `padding: 32px` (20 en teléfono).
- Contenido: `p.estado-ok` «Solicitud recibida» (en 600 de 15 px, oliva, 5,05:1); `h2#t-exito` «Gracias», en `--t-seccion`; `p#codigo` (Fraunces 400 de 36 px, tinta, tabular, `letter-spacing: .02em`); y `p#exito-texto` en 16 px. Luego los tres pasos de 4.6 como `h3` y `p`, **sin «Paso 1/2/3»**. Al final, `a.boton.secundario` «Entrar al recorrido» → `tour/`.

### 4.10 Estados de la página

| Estado | Calendario | Resumen | Barra fija (< 1000) | Botones «Solicitar» |
|---|---|---|---|---|
| Carga inicial o sin fechas | `#rango-texto` dice «Elige la llegada» | Todos los valores en «—» y `#s-noches-txt` en «Noches» | «Elige tus fechas» / «sin cobro en línea» | `aria-disabled="true"`. Al tocarlos, el formulario muestra en `#cal-error` «Elige la fecha de llegada y la de salida.» y lleva al calendario (lógica actual) |
| Llegada elegida | La llegada es un chip terracota; los días posibles quedan habilitados y el resto, deshabilitado con su motivo en el `aria-label` | Llegada con fecha; lo demás, «—» | Igual que el anterior | Igual que el anterior |
| Rango válido | Banda continua; `#rango-texto` dice «vie 9 oct → lun 12 oct · 3 noches» | Todos los valores y el total | Total en CLP / «3 noches · total de ejemplo» | `aria-disabled="false"` |
| Rango que cruza ocupados o no es válido | JS no deja elegir salidas imposibles. Si el servidor responde `fechas_ocupadas`, vuelve a cargar la disponibilidad y muestra `#cal-error` | Vuelve a «—» | Vuelve a «Elige tus fechas» | `aria-disabled="true"` |
| Error en un campo | Sin cambios | Sin cambios | Sin cambios | Se muestra `#form-error`, el campo queda con `aria-invalid` y recibe el foco (lógica actual) |
| Enviando | Días y flechas deshabilitados (lógica actual) | Sin cambios | Sin cambios | `disabled` real, con el texto «Enviando…» en **los dos** |
| Error de envío o de red | `#cal-error` o `#form-error` según el código | Sin cambios | Sin cambios | Vuelven a «Solicitar» |
| Éxito | `.reserva` se oculta | Se oculta | Se oculta (`exito()`) | — |

---

## 5. Qué NO se lleva del HTML de Stitch

1. **Tailwind:** `cdn.tailwindcss.com`, la `tailwind.config` en línea y las unas 200 clases utilitarias (`h-[48px]`, `text-[#5F574E]`, `aspect-[16/10]`…). La CSP de `build.py` solo admite `'self'`, rutas exactas de jsDelivr y hashes, así que en producción Tailwind no cargaría. De esas clases solo se traducen los valores.
2. **Google Fonts enlazado** (`fonts.googleapis.com` y `preconnect`): se aloja Fraunces (1.3).
3. **Manejadores y scripts en línea:** `onclick="toggleAccordion(this)"`, `onsubmit="event.preventDefault()"`, `onsubmit="return false;"` y el `<script>` de la barra de progreso con su 300 % fijo. La CSP no tiene `'unsafe-hashes'`.
4. **Viewport** con `maximum-scale=1.0, user-scalable=no`; `input:focus, textarea:focus, button:focus { outline: none }`; `focus:ring-0`; `focus:outline-none`; y `-webkit-tap-highlight-color: transparent`.
5. **Ancho fijo:** `body { max-width: 390px }`, la barra centrada con `translateX(-50%)`, los `max-w-[390px]` y el que no haya ningún `@media` (medido: 0 en los 5 HTML).
6. **Encabezado absoluto** (`position: absolute`) y los dos encabezados distintos. El botón «Tour 3D» de 40 px, el filete vertical junto a «Arriendo turístico» y el margen de 48 px del encabezado de la reserva.
7. **Marcado sin semántica:** acordeón de `div`; títulos de tarjeta, pies y equipamiento en `div`; tarifas en `div` con flex; días del calendario en `div`; «Huéspedes» como `label` sin `for`; el valor del contador en `span`; «Privacidad» como texto sin enlace; y la marca sin enlace en el teléfono.
8. **Calendario estático:** septiembre y octubre de 2026 escritos a mano, las clases `day-past`, `day-occupied`, `day-selected-*` y `hatch-pattern`, y el tachado.
9. **Datos escritos a mano:** «CLP 58.000», «CLP 15.000», «CLP 174.000», «CLP 189.000», «© 2026», «desde 15:00 / hasta 11:00» en un solo `span` y el sufijo «2 huéspedes».
10. **Estado inválido de la maqueta:** la casilla con `checked`, `value="Ana Pérez"` y los marcadores `ana.perez@ejemplo.com`, `ejemplo@correo.com` y `+56 9 1234 5678`.
11. **Tarjeta de reserva rápida** con `input type=date` y valores en el pasado (`2026-04-10`, `2026-04-14`), más su sombra `0 4px 20px rgba(0,0,0,.15)`.
12. **Imágenes:** todas las URL de Stitch (`lh3.googleusercontent.com`, `stitch-placeholder`), la imagen como `div` con `background-image` y `role=img`, las muestras con `transform: scale(3)` y `transform-origin` en línea o con `!important`, y las imágenes repetidas (el dormitorio 1 en la introducción y el living a 16:10 en el resumen).
13. **Tipografía:** `font-variation-settings: "opsz" 72` y `font-feature-settings: "opsz" auto`. El peso 400 de la marca en la reserva (va en 500 en todas partes).
14. **Textos reescritos por Stitch** en las preguntas del teléfono («con total privacidad», «instrucciones de llegada», etc.). Se usan los de 3.9.
15. **Rótulos que se retiran:** «Tour 3D», «tour», «Ver disponibilidad», «Ver fechas disponibles», «Solicitar reserva», «/ noche · ejemplo» partido y «Llegada / salida (ejemplo)» en una sola fila.
16. **Comillas** «» en la frase destacada, y los pies de foto en cursiva de 14 px.
17. **Destinos rotos:** `href="#"`, `#tarifas` para «Reservar», `#recorrido`, `#tour` para «Entrar al recorrido».

---

## 6. Mapeo a JS y al contenido editable

### 6.1 Contenido editable (`contenido-publico.js`, portal)

Hay que cargar `<script type="module" src="js/contenido-publico.js"></script>` en `index.html` y `reserva.html`, después de `sitio.js`. El texto que queda en el HTML es el respaldo y debe ser **idéntico a la semilla** de `0003_gestion.sql`, para que la página no salte al cargar. Los valores se insertan siempre con `textContent`.

| Elemento | Atributo | Clave o valor | Nota |
|---|---|---|---|
| `p.bajada` del hero | `data-contenido` | `hero.bajada` | `white-space: pre-line` |
| `p.bajada` de Espacios | `data-contenido` | `espacios.bajada` | `pre-line` |
| `figure` de cada espacio | `data-fotos` | `living`, `cocina`, `dorm1`, `dorm2`, `banos`, `balcon`, `recibidor` | El `img` dentro de un `picture`, con `width`, `height` y `loading=lazy` |
| `h3` de cada espacio | `data-contenido` | `espacio.<clave>.titulo` | — |
| `p` de cada espacio | `data-contenido` | `espacio.<clave>.texto` | `pre-line` |
| Precio grande de Tarifas y precio de la barra de la portada | `data-precio` | `noche` | `sitio.js` lo rellena con `TARIFA` y el portal lo reemplaza |
| Limpieza en la tabla | `data-precio` | `limpieza` | Igual que el anterior |
| Llegada en la tabla | `data-contenido` | `condiciones.llegada` | Fila propia |
| Salida en la tabla | `data-contenido` | `condiciones.salida` | Fila propia |
| Imagen del resumen (reserva) | `data-fotos` | `living` | Solo se ve con 860 px de alto o más |

No quedan precios fuera de `[data-precio]`. El resumen y la barra de la reserva los calcula `reserva.js` con `tarifaVigente()`.

### 6.2 `sitio.js`: lo que se conserva y lo que cambia

| Selector | Qué hace | Estado |
|---|---|---|
| `.hamburguesa`, `#panel-menu` | Abre y cierra el menú, `aria-expanded`, Esc | Se conserva |
| `.aparece` → `.visible` | Aparición al hacer scroll | Se conserva |
| `[data-precio]` | Precio de ejemplo | Se conserva |
| `#anio` | Año del pie | Se conserva |
| `#reserva-rapida` y su bloque | Tarjeta rápida | **Se elimina** el bloque y las importaciones que quedan sin uso (`hoyIso`, `noches`, `sumarDias`, `total`, `validarRango` y `MENSAJES`). `TARIFA` y `clp` se quedan |
| **Nuevo:** `.hero`, `.barra`, `.barra-movil`, `#tarifas` | Estado del encabezado y de la barra | Ver el código de abajo |
| **Nuevo:** `.espacios` y `.progreso i` | Barra de progreso del carrusel | Ver el código de abajo |

```js
// Encabezado transparente sobre el hero y barra fija oculta en el hero y sobre Tarifas (solo en la portada).
const hero = $(".hero"), barra = $(".barra"), movil = $(".barra-movil"), tarifas = $("#tarifas");
if (hero && barra) {
  if ("IntersectionObserver" in window) {
    let enHero = true, enTarifas = false;
    const aplicar = () => {
      barra.classList.toggle("sobre-hero", enHero);
      movil?.classList.toggle("oculta", enHero || enTarifas);
    };
    new IntersectionObserver(([e]) => { enHero = e.isIntersecting; aplicar(); },
      { rootMargin: `-${barra.offsetHeight}px 0px 0px 0px` }).observe(hero);
    if (tarifas && movil) new IntersectionObserver(([e]) => { enTarifas = e.isIntersecting; aplicar(); },
      { rootMargin: `0px 0px -${movil.offsetHeight}px 0px` }).observe(tarifas);
  } else {
    barra.classList.remove("sobre-hero");
  }
}
// Barra de progreso del carrusel de Espacios (decorativa: aria-hidden).
const car = $(".espacios"), relleno = $(".progreso i");
if (car && relleno) {
  const avance = () => {
    const f = car.clientWidth / car.scrollWidth, max = car.scrollWidth - car.clientWidth;
    relleno.style.width = `${Math.min(1, f) * 100}%`;
    relleno.style.transform = `translateX(${max > 0 ? (car.scrollLeft / max) * (1 / f - 1) * 100 : 0}%)`;
  };
  car.addEventListener("scroll", avance, { passive: true });
  addEventListener("resize", avance);
  avance();
}
```

### 6.3 `reserva.js`: los hooks que deben existir

Todos están en el `reserva.html` actual y se mantienen **con el mismo `id` o clase**. Si falta uno, el JS falla en la primera línea (`$("#meses")` es `null`).

| Hook | Elemento | Lugar en v4 |
|---|---|---|
| `#calendario` | `section` | Área `cal` |
| `#meses` | `div.calendario` (los meses los genera JS) | Dentro de `.cal-cuerpo` |
| `#mes-ant`, `#mes-sig` | `button` | En `.cal-nav`, antes de `#meses` |
| `#rango-texto` | `p` con `aria-live`, `tabindex=-1` | Bajo la cuadrícula |
| `#cal-error` | `p.mensaje.error` con `role=alert` | Al final del calendario |
| `#aviso-sim` | `p.mensaje` | Bajo la introducción |
| `.reserva` | Contenedor de la retícula | `exito()` lo oculta |
| `#s-entrada`, `#s-salida`, `#s-noches-txt`, `#s-alojamiento`, `#s-limpieza`, `#s-total` | Valores del resumen | `aside.resumen` |
| `#enviar` | `button type=submit form=formulario` | Resumen; oculto bajo 1000 px |
| `#formulario` | `form` con `novalidate` | Área `form` |
| `#menos`, `#mas`, `#huespedes` (`output`) | Contador | Formulario |
| `#nombre`, `#email`, `#telefono`, `#mensaje` | Campos (`campos` en el JS) | Formulario |
| `#sitio` | Campo trampa | Formulario |
| `#acepta` | Casilla | Formulario |
| `#form-error` | `p.mensaje.error` con `role=alert` | Formulario |
| `.barra-movil`, `#m-total`, `#m-noches`, `#enviar-movil` | Barra fija | Fuera de `main`; `exito()` la oculta |
| `#exito`, `#codigo`, `#exito-texto` | Éxito | Después de `.reserva` |

JS genera `.mes > h3 + table`, con `th[scope=col][abbr]` y `td > button.dia[data-dia]`, y las clases `.pasado`, `.ocupado`, `.extremo` y `.en-rango`, además de `aria-pressed`, `aria-label` (fecha larga y motivo) y `disabled`. El CSS de 4.4 les da estilo sin cambiar esa estructura.

### 6.4 Cambios de JS y sus pruebas

**`reserva-logica.js`** (funciones puras nuevas, junto a las demás):

```js
export const CELDA_MIN = 48;          // px: área táctil mínima de un día (DESIGN-v4, WCAG 2.5.5)
export const SEPARACION_MESES = 32;   // px: column-gap de #meses
/** Meses que caben lado a lado en `ancho` px: 2 si caben dos semanas de 7 × CELDA_MIN más la separación, si no 1. */
export function mesesPorPagina(ancho) { return ancho >= 2 * 7 * CELDA_MIN + SEPARACION_MESES ? 2 : 1; }
/** ¿Se puede avanzar un mes? La última página alcanzable es la que contiene `hasta` (ISO). */
export function hayMesSiguiente(anio, mes, porPagina, hasta) { return Date.UTC(anio, mes + porPagina, 1) <= desdeIso(hasta).getTime(); }
```

**`reserva.js`**:
1. `estado.porPagina = mesesPorPagina($("#meses").clientWidth)`. Un `ResizeObserver` sobre `#meses` recalcula el valor y llama a `pintar()` solo si cambió.
2. En `pintar()`: `for (let k = 0; k < estado.porPagina; k++)`, más `$("#meses").style.setProperty("--meses", estado.porPagina)`. `$("#mes-sig").disabled = estado.enviando || !hayMesSiguiente(estado.mes.anio, estado.mes.mes, estado.porPagina, HASTA)`. Esto corrige que siempre pintara dos meses y el tope pensado para páginas de dos.
3. En cada día: `if (esEntrada) b.classList.add("llegada")`, `if (esSalida) b.classList.add("salida")` y `if (dia === HOY) { b.classList.add("hoy"); b.setAttribute("aria-current", "date"); }`.
4. `#rango-texto` con el rango completo: `` `${fDia(entrada)} → ${fDia(salida)} · ${noches(entrada, salida)} noches` ``. Hay que importar `noches`.
5. En `resumen()`:
   ```js
   $("#m-total").textContent = v.ok ? clp(t.total) : "Elige tus fechas";
   $("#m-noches").textContent = v.ok ? `${v.noches} noches · total de ejemplo` : "sin cobro en línea";
   for (const b of [$("#enviar"), $("#enviar-movil")]) { b.disabled = estado.enviando; b.setAttribute("aria-disabled", String(!v.ok)); }
   ```
   El manejador de `submit` ya valida el rango, muestra `#cal-error` y lleva al calendario. Queda igual.
6. Los rótulos se aplican a los dos botones: `"Enviando…"` al enviar y `"Solicitar"` al volver (hoy solo cambia `#enviar` y escribe «Solicitar reserva»).
7. CSS: `.boton[aria-disabled="true"] { opacity: .5; cursor: not-allowed; }`.

**Pruebas en `web/tests/reserva-logica.test.mjs`:**
- `mesesPorPagina(320) === 1`, `mesesPorPagina(703) === 1` y `mesesPorPagina(704) === 2`.
- `hayMesSiguiente` con `hasta = "2027-10-26"`: desde septiembre de 2027, con 2 meses por página, da `false`. Desde septiembre de 2027 con 1 da `true`. Desde octubre de 2027 con 1 da `false`, porque octubre contiene `hasta`. Desde agosto de 2027 con 2 da `true`.

**Pruebas nuevas en `web/tests/sitio-html.test.mjs`** (estáticas y sin DOM, como `marca.test.mjs`):
- En `index.html` y `reserva.html`, el viewport es exactamente `width=device-width, initial-scale=1, viewport-fit=cover`.
- `#acepta` no tiene `checked`.
- `sitio.css` y `tokens.css` no contienen `outline: none`, `outline:none` ni `outline: 0`.
- Ninguna página pública contiene `cdn.tailwindcss.com`, `fonts.googleapis.com` ni atributos `on[a-z]+=`.
- El texto visible (sin etiquetas) no contiene `/\btour\b/i`, «Ver disponibilidad» ni «Solicitar reserva».
- `reserva.html` contiene todos los `id` de 6.3.
- Cada `data-contenido` de `index.html` es una clave de la semilla de `web/supabase/migrations/0003_gestion.sql`, y los 7 `data-fotos` de 6.1 están presentes.

### 6.5 `build.py`: recortes de materiales

Se agrega una tabla de recortes con constantes que comentan su origen (regla del proyecto):
`RECORTES = {"material-ladrillo": ("Living", (x0, y0, x1, y1)), "material-concreto": (…), "material-roble": (…), "material-cuero": (…), "material-acero": (…)}`.
Las fuentes son los renders de `web/renders_png/` (los nombres de `IMAGENES`). Cada recorte es cuadrado y se exporta a 360 × 360 en `.webp` y `.jpg`, con la misma calidad que las demás imágenes. Las cajas se eligen mirando los renders reales y se anotan con un comentario (por ejemplo, `# Living.png: muro de ladrillo, esquina superior derecha`). `revisar_enlaces()` falla si falta alguno, porque el `img src` apunta a `img/`.

---

## 7. Rótulos y destinos (únicos en todo el sitio)

| Acción | Rótulo | Destino | Dónde |
|---|---|---|---|
| Nombre del recorrido | «Recorrido 3D» | `#tour` o `./#tour` | Menú, panel, título de la sección |
| Entrar al tour desde el hero | «Recorrer en 3D» | `tour/` | Hero |
| Entrar al tour desde su sección | «Entrar al recorrido» | `tour/` | Recorrido 3D, éxito |
| Reservar | «Reservar» | `reserva.html` | Encabezado (≥ 1000), panel, barra de la portada |
| Ver el calendario | «Ver fechas» | `reserva.html#calendario` | Hero, Tarifas |
| Enviar | «Solicitar» y «Enviando…» | `submit` de `#formulario` | Resumen, barra de la reserva |
| Dudas | «¿Dudas? Revisa las preguntas frecuentes» | `./#preguntas` | Resumen |
| Privacidad | «Privacidad» o «privacidad» | `privacidad.html` | Pie, casilla, pregunta 6 |

Solo son anclas los enlaces del menú. No queda ningún `href="#"`. Se escribe «solo», sin tilde, en el sitio (casilla y pregunta 6). En `MENSAJES.telefono` es opcional.

---

## 8. Lista de verificación final

### 8.1 Capturas (en `index.html` y `reserva.html`)

Anchos de **1280 × 800, 768 × 1024, 450 × 900 y 375 × 667**, más un control de desborde a 320 × 568. Todas se comparan con las capturas de Stitch en composición, no en contenido.

- Portada: la primera pantalla (encabezado sobre el hero, sin marca, con el velo), el encabezado sólido después de bajar, Espacios completo, Materiales, Recorrido, Lo que hay, Tarifas, Preguntas con una abierta, el pie, la barra fija oculta en el hero, visible después del hero y oculta sobre Tarifas (< 1000), y el menú abierto sobre el hero.
- Reserva: sin fechas, con la llegada elegida, con el rango en un mes, con el rango que cruza de mes y de fila, con el foco en un día, con errores en los campos, con la casilla sin marcar, enviando, con error de red y con éxito. Meses por página: 2 a 1280 (el contenedor de los meses mide unos 738 px), 1 a 1100 y 1024, 2 a 900 (una sola columna) y 1 a 768 y en teléfono (valores inferidos desde el CSS; confirmarlos). A 1366 × 768: el botón del resumen visible.
- Regresión: `privacidad.html`, `404.html` y `tour/` a 1280 y a 375 (Fraunces reemplaza a Newsreader en el tour).

### 8.2 Mediciones (con las herramientas del navegador)

- `document.documentElement.scrollWidth === innerWidth` en todos los anchos: sin desplazamiento horizontal, salvo dentro de los carruseles.
- H1 del hero: `scrollWidth <= clientWidth` a 320, 375, 768 y 1280. El nombre no se corta ni se parte.
- Contraste con el **render real**: el píxel más claro bajo el H1 debe dar ≥ 3:1, y bajo la bajada, el pie y el menú sobre el hero, ≥ 4,5:1. Si alguno no llega, se oscurece el velo; nunca se aclara por debajo de lo que dice 1.2.
- Carruseles a 375: la primera tarjeta arranca en x = 16 px, igual que el título. En Materiales se asoma la tercera muestra.
- Reserva a 1280 × 800: la primera fila de días empieza en y ≤ 600. A 390 × 664 hay al menos una fila de días visible sobre la barra fija.
- Tamaños táctiles ≥ 48 px: hamburguesa, «Reservar», «Ver fechas», flechas de mes, días (salvo a 320), contador, fila de la casilla, botones de la barra y enlaces del pie (≥ 44).
- Peso de Fraunces: anotar el tamaño de cada `woff2` (inferido: unos 100 KB cada uno). Confirmar que el archivo trae los ejes `opsz` y `wght`.

### 8.3 Accesibilidad

- Con Tab en las dos páginas y los dos anchos: foco visible en todo, con el anillo en blanco sobre el hero y en papel sobre carbón y terracota oscura. Orden lógico. «Saltar al contenido» funciona.
- El menú de teléfono se abre y se cierra con Enter y con Esc, y `aria-expanded` cambia.
- Las preguntas se abren con Enter y con Espacio.
- Calendario con teclado: flechas de mes, luego los días. Después de elegir, el foco se conserva. `#rango-texto` se anuncia.
- Lector de pantalla (VoiceOver u Orca): cada día anuncia la fecha larga y su motivo; los errores se anuncian (`role=alert`); el contador anuncia el número; el éxito recibe el foco.
- Zoom al 200 % y reflujo a 320 px CSS (WCAG 1.4.4 y 1.4.10) sin pérdida de contenido.
- `prefers-reduced-motion`: sin transiciones ni escala.
- Alto contraste (`forced-colors`): el foco sigue visible (es `outline`).
- Encabezados en orden: un `h1`, un `h2` por sección y `h3` en las tarjetas y los ítems. «Qué pasa después» es `h2`.
- Los bordes de campo miden ≥ 3:1 (`--tinta-2`, 6,3:1). Ningún texto por debajo de 14 px.

### 8.4 Pruebas automáticas

- `cd web && npm test`: `reserva-logica` (con las pruebas nuevas), `contenido-publico` (de main), `marca` y `sitio-html` (nueva).
- `python3 -m unittest discover -s web/tests -p 'test_*.py'`.
- `python3 web/build.py`: sin enlaces faltantes. En la CSP de cada página no debe aparecer `fonts.googleapis.com`, y el `script-src` no lleva hashes nuevos (no hay scripts en línea).
- `grep -rn "loft" web/src/*.html web/src/tour/index.html` sin resultados, en el texto visible (lo verifica `marca.test.mjs`).

### 8.5 Cobertura de los defectos altos y medios

| Defecto (crítica) | Sección |
|---|---|
| Velo del hero que no asegura el contraste; encabezado del teléfono sin velo (atractivo alta, UX media) | 1.2, 3.2 |
| Encabezado absoluto o distinto entre páginas; «Tour 3D»; menú sin panel (atractivo alta, UX media, reglas alta y media) | 2.2 |
| Zoom bloqueado y foco eliminado (atractivo alta, UX alta ×2, reglas alta) | 1.6, 4, 5 (ítem 4) |
| Destinos rotos (UX alta, reglas media) | 7 |
| Días de 41 px y flechas de 40 (UX alta) | 4.4 |
| «Solicitar» fuera del formulario y estados que faltaban (UX alta, atractivo media) | 4.8, 4.10, 6.4 |
| Tailwind y ancho fijo sin `@media` (reglas alta ×2) | 1.4, 5 |
| Casilla premarcada (reglas alta, UX media) | 2.4, 4.7 |
| Hooks de `reserva.js` y calendario estático (reglas alta ×2) | 4.4, 6.3, 6.4 |
| Hooks de la tarjeta rápida (reglas alta) | 3.8 (se elimina), 6.2 |
| Manejadores en línea y acordeón de `div` (reglas alta, UX media, atractivo media) | 3.9, 5 |
| Portal: `data-fotos`, `data-contenido` y `data-precio` (reglas alta) | 3.4, 3.8, 6.1 |
| H1 con `nowrap` que se desborda (reglas alta, atractivo media) | 1.3, 3.2 |
| Espacios largo y «Recibidor» huérfano (atractivo media, reglas media) | 3.4 |
| Dos titulares en Tarifas, tarjeta con hueco y `input type=date` (atractivo media, UX media) | 3.8 |
| Cortes en el teléfono: precio, filas y línea de datos (atractivo media, reglas media) | 3.3, 3.8 |
| Carruseles sin `scroll-padding` ni foco; Materiales cortado (atractivo, UX y reglas media) | 2.7, 3.5 |
| Resumen fijo más alto que la pantalla (atractivo, UX y reglas media) | 4.3, 4.5 |
| La tarea fuera de la primera pantalla; imágenes decorativas (atractivo, UX y reglas media) | 4.2 |
| Flechas de mes alrededor del rango (atractivo media) | 4.4 |
| Nombres de acciones distintos (atractivo media) | 7 |
| Rango de 600 a 1100 px sin diseño (atractivo media) | 1.4 y cada sección |
| Barra fija visible desde la carga (UX media) | 2.3, 6.2 |
| Bordes de campo, marcadores y campos de 15 px (UX y reglas media) | 2.4 |
| Contador sin semántica y botones chicos (UX y reglas media) | 4.7 |
| Anillo invisible en bloques oscuros (UX media) | 1.6 |
| Texto por debajo de 16 px (UX media) | 1.3 |
| Preguntas reescritas o sin enlace a la privacidad (UX y reglas media) | 3.9 |
| Claridad en 5 segundos y bajada larga (UX media) | 3.2 (nota al dueño) |
| Frase destacada que parecía reseña (reglas media) | 3.4 |
| Materiales sin verificar y `scale(3)` (reglas media) | 3.5, 6.5 |
| Fraunces desde Google y `opsz` fijo (reglas media) | 1.3 |
| Orden de la reserva en teléfono con un solo DOM (reglas media) | 4.3 |
| Worktree atrasado respecto de main (reglas media) | 0 |
