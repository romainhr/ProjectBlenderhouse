# ADR 0006: Sistema visual v4 del sitio (modelo de Google Stitch)

- **Fecha:** 2026-09-26
- **Estado:** propuesto; implementado en la rama `web/diseno-atractivo` y pendiente de revisión.
- **Modelo de IA utilizado:** Claude Opus 5.5 (`claude-opus-5-5`), como implementador de `web/diseno/ESPEC-v4.md`.
- **Revisor humano:** Romain Ange (romain.ange@gosocket.net), pendiente.

## Contexto

Al dueño le gustó el modelo v4 hecho en Google Stitch (`web/diseno/stitch-v4/`) y pidió llevarlo al sitio real con fidelidad. `web/diseno/ESPEC-v4.md` traduce ese modelo a valores del sitio y corrige los defectos que encontraron tres críticas. Este ADR registra las decisiones de arquitectura que pide la especificación (§0.5) y las desviaciones que se tomaron al medir el resultado en el navegador.

## Decisiones

1. **Fraunces autoalojada en `tokens.css`.** Fraunces variable (ejes `opsz` 9–144 y `wght` 400–600, redonda y cursiva, subconjunto latin con tildes y ñ, licencia OFL) se descargó de Google Fonts y queda en `web/src/fonts/fraunces-var.woff2` (67 KB) y `fraunces-var-italic.woff2` (82 KB). Sus `@font-face` van en `tokens.css`, que comparten el sitio, el tour y el portal: los tres pasan de Newsreader a Fraunces sin tocar su CSS. Se retiró `newsreader-500.woff2`. No se enlaza Google Fonts, así que la CSP de `build.py` no cambia y sigue siendo cierto lo que dice `privacidad.html` sobre las tipografías.
2. **Encabezado con estado por IntersectionObserver.** En la portada, `header.barra` parte con `.sobre-hero` (transparente, sin marca) y `sitio.js` la quita cuando el hero deja de estar bajo el encabezado. El mismo observador oculta la barra fija inferior sobre el hero y sobre Tarifas. Sin JS, un `<noscript>` deja el encabezado sólido y la barra visible; sin IntersectionObserver, `sitio.js` hace lo mismo. En las demás páginas el encabezado siempre es sólido.
3. **Meses por página según el ancho del contenedor.** `mesesPorPagina(ancho)` (en `reserva-logica.js`, con pruebas) da 2 meses si `#meses` mide al menos 2 × 7 × 48 + 32 = 704 px, y 1 si no. `reserva.js` lo recalcula con un ResizeObserver sobre `#meses` y `hayMesSiguiente()` limita el avance con 1 o 2 meses por página. Medido: 2 meses a 1280 y 900 px de ventana, 1 a 1100, 1024, 768 y en teléfono.

## Desviaciones de ESPEC-v4, medidas

4. **Tamaño óptico de los títulos grandes.** La especificación pide `font-optical-sizing: auto` en todo. Medido en Chrome y Firefox: desde un `opsz` cercano a 88, el travesaño de la «e» de Fraunces se vuelve un pelo y «Project-roomVR» se lee «Projcct» a 112 px. Con `font-optical-sizing: none` en los títulos de 40 px o más (hero, «Reserva», capítulos y secciones), el nombre mide 7,45 em, la medida que la especificación tomó del modelo (834 px a 112 px), y el trazo coincide con el de Stitch. El resto del texto sigue en `auto`. No se usa `font-variation-settings`, que la especificación prohíbe.
5. **Recortes de materiales como archivos estáticos.** La especificación ubica los recortes en `build.py`, pero esta tarea no podía modificarlo. Los cinco recortes (360 × 360, JPEG q82 y WebP q80, las mismas calidades de `build.py`) se generaron una vez desde `web/renders_png/` y quedan en `web/src/img/material-*-360.*`. Las cajas, en píxeles del render de 1600 × 1000, son estas:
   - ladrillo: `Living.png` (1220, 250, 1500, 530), el muro del living sobre el televisor;
   - concreto: `Living.png` (600, 0, 880, 280), el cielo del living;
   - roble: `Bano1_Vanitorio.png` (1245, 690, 1555, 1000), el piso de tablas del dormitorio visto por la puerta del baño (`docs/deco-industrial.md`: roble en muebles, repisas y pisos de dormitorios);
   - cuero: `Living_Sofa.png` (880, 640, 1120, 880), el sofá;
   - acero: `Balcon.png` (720, 455, 930, 665), la mesa bistró.
   Si cambian los renders, hay que regenerarlos. Queda pendiente llevar esta tabla a `build.py` (ESPEC-v4 §6.5).
6. **La aparición al hacer scroll no oculta contenido.** En vez de partir con opacidad 0, `.aparece` solo se anima (`.visible`) cuando el bloque entra desde abajo después de la carga. Sin JS, sin IntersectionObserver o en una captura de página completa, todo se ve (RA-16).
7. **Resumen compacto en computador.** Se redujeron unos 40 px la introducción y el resumen para que «Solicitar» se vea entero sin desplazarse a 1280 × 800 y a 1366 × 768 (medido: el botón termina en y = 766 y 767).

## Consecuencias

- El tour y el portal cambian de tipografía de títulos (Newsreader a Fraunces) sin cambios en sus archivos.
- Los velos del hero quedan en los valores mínimos de §1.2. Medido sobre el render real, el peor contraste del blanco es de 6,2:1 bajo el H1 y 10,8:1 bajo la bajada a 1280 × 800, y de 7,2:1 y 11,0:1 a 375 × 667.
- La tarjeta de reserva rápida de la portada y su código se eliminaron: el único camino para reservar es el calendario de `reserva.html`.
