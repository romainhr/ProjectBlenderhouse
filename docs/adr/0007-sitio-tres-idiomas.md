# ADR 0007: sitio público en tres idiomas y textos editables traducidos

- **Fecha:** 2026-09-26
- **Estado:** propuesto; implementado en la rama `web/i18n-base` y pendiente de revisión en su PR.
- **Modelo de IA utilizado:** Claude Opus 5.5 (`claude-opus-5-5`).
- **Revisor humano:** Romain Ange. Pidió el sitio «en los tres idiomas pero con selección automática por idioma navegador». La revisión final se hace en la PR.

## Contexto

El sitio público estaba sólo en español y el propietario edita sus textos desde el portal `/admin` (ADR 0003, decisiones 11 a 17). Para ofrecerlo en inglés y en francés hay que resolver dos cosas:

- cómo se generan y se eligen las páginas en otro idioma;
- qué pasa con los textos que el propietario edita en `public.contenido`.

El trabajo se reparte entre sesiones de Claude. Esta rama trae la base: el build en tres idiomas, la migración 0005 y el portal. El marcado `data-i18n` de las páginas públicas, el selector de idioma y las traducciones de las páginas llegan en una PR posterior de otra sesión.

## Decisiones

### Sitio (mecanismo acordado entre las sesiones, implementado en `web/build.py`)

1. **Rutas:** `/` en español, como hasta ahora; `/en/` y `/fr/` con las mismas páginas (index, reserva, privacidad, 404 y `tour/`).
2. **Fuente en español:**
   - El HTML de `web/src` sigue en español.
   - Un texto traducible es un elemento hoja con `data-i18n="clave"`. Los atributos se marcan con `data-i18n-attr="alt:clave; aria-label:clave; content:clave"`. `<title>` y `<meta name="description">` también se traducen.
   - **`data-i18n-attr` sólo traduce texto (lista blanca, hallazgo H3 de la revisión del build):**
     - Admite `alt`, `title` (salvo en `<link>` y `<style>`), `aria-label`, `aria-description`, `aria-roledescription`, `aria-valuetext`, `aria-placeholder`, `placeholder` y `label`.
     - `content` sólo se admite en `<meta name="description">`, `og:title` y `og:description`, sin `http-equiv`.
     - Cualquier otro atributo detiene el build. Así, un diccionario nunca pone una URL, HTML (`srcdoc`), una redirección (`<meta http-equiv="refresh">`), un tipo, un `rel`, estilos ni manejadores.
   - **Lectura del HTML (hallazgo H4):** el build acepta, como el navegador, un atributo pegado a la comilla del anterior (`class="x"data-i18n="k"`). Si una marca queda en una etiqueta que no sabe leer, se detiene con el archivo y la línea en vez de saltarla.
   - Los diccionarios son planos (clave -> texto) en `web/src/i18n/es.json`, `en.json` y `fr.json`. Las claves del JS llevan el prefijo `js.`; las del tour, `tour.` (HTML) y `js.tour.` (JS).
   - **Textos del JS (`web/src/js/i18n.js`), corregido en la revisión (hallazgos JS-2 a JS-4):**
     - El español no depende de la red. Sus claves `js.*` vienen en `web/src/js/textos-es.js`, que se importa de forma estática. Es un espejo de `es.json`: se regenera con `python3 web/build.py --textos-es`, y el build y `npm test` fallan si no coincide. La página en español no pide ningún diccionario, y en `/en/` y `/fr/` el respaldo en español siempre está, así que nunca se ven las claves.
     - En `/en/` y `/fr/` se pide sólo el diccionario propio. `i18n.js` no tiene `await` de nivel superior: exporta `listo`, que se cumple cuando el diccionario llega, falla o vence el plazo de 5 s, y nunca se rechaza. `reserva.js` espera `listo` antes de pintar, pero pide la disponibilidad antes de esa espera. `contenido-publico.js` empieza sus lecturas de Supabase enseguida y espera `listo` sólo antes de aplicar los textos.
     - El idioma y el locale de la página están en `web/src/js/idioma.js`, que no importa nada ni espera nada, e `i18n.js` los reexporta. Así `sitio.js` puede escribir los precios de ejemplo con `clp(…, LOCALE)` sin esperar ninguna red. Ese cambio le corresponde a la sesión dueña de `sitio.js`. Mientras tanto, si el propietario editó alguna tarifa, `contenido-publico.js` reescribe todas con el formato del idioma, para que una misma tabla no mezcle «CLP 70,000» con «CLP 15.000».
3. **Selector:** enlaces `<a data-i18n-alternar="es|en|fr">`. El build los apunta a la misma página en ese idioma.
   - Una página que queda sólo en español (sin marcas, o el tour sin `import.meta.url`) no existe en `/en/` ni `/fr/`. Su selector lleva al inicio de cada idioma. Si el inicio tampoco está traducido, el build se detiene: el enlace no tendría destino.
4. **Selección automática:** `dist/_redirects` con reglas `302!` y `Language=en|fr` por página.
   - Según la documentación de Netlify que consultó la sesión que diseñó el mecanismo, Netlify mira el primer idioma del `Accept-Language`. El «!» es obligatorio porque la página en español existe.
   - La cookie `nf_lang`, que pondrá el selector al elegir, reemplaza la detección.
   - Sólo tienen regla las páginas que se publican en otro idioma (ver «Consecuencias y riesgos»).
   - **404 (hallazgo H5):** según la documentación de Netlify, `/404.html` se sirve en cualquier ruta sin archivo sin pasar por una regla `/404.html`. Por eso el 404 no tiene regla `302!`. Al final van estas reglas, sin «!» (sólo se aplican si no existe el archivo):
     - `/en/*` y `/fr/*`, con el 404 de su idioma;
     - `/*  /<idioma>/404.html  404  Language=<idioma>`, con el 404 del idioma del navegador en el resto del sitio.
   - **Supuesto:** no se comprobó en un despliegue real, tampoco que Netlify aplique `Language=` en una regla 404. Esta rama no publica en Netlify; se confirma en el primer despliegue.
5. **Tour en otro idioma:** sólo se genera `dist/<idioma>/tour/index.html`. Sus `<script src>` y `<link>` apuntan a los compartidos de `/tour/`, así hay un solo JS y un solo modelo en caché.
   - El tour debe resolver su modelo con `import.meta.url`.
   - Estado al escribir este ADR: `web/src/tour/js/carga.js` todavía usa la ruta relativa a la página (`RUTA_MODELO = "modelo/"`). Desde `/en/tour/` apuntaría a `/en/tour/modelo/`, que no existe. El cambio le corresponde a la sesión dueña de `web/src/tour/`: `export const RUTA_MODELO = new URL("../modelo/", import.meta.url).href;`.
   - Hasta ese cambio, el build no publica el tour en otro idioma (hallazgo JS-1 de la revisión). `tour_traducible()` en `web/build.py` deja fuera `tour/` mientras `carga.js` no arme `RUTA_MODELO` con `import.meta.url`, o mientras algún JS del tour nombre el modelo con una ruta relativa a la página (`"modelo/…"`). En ese caso no se genera `dist/<idioma>/tour/` ni la regla `/tour/ … Language=`. Quien entra a `/tour/` se queda en el tour en español, que funciona, y los enlaces de `/en/` y `/fr/` llevan a ese mismo tour. Con el cambio en `carga.js` se habilita sin tocar el build. Las pruebas están en `web/tests/test_build_js.py`.

### Textos editables (migración 0005 y portal)

6. **Dos columnas nuevas en `public.contenido`:** `valor_en` y `valor_fr`, de tipo `text` con `null` permitido.
   - Tienen los mismos límites que `valor` en la 0003: no en blanco y hasta 4000 caracteres. Son las restricciones `contenido_valor_en_largo` y `contenido_valor_fr_largo`.
   - Los privilegios y las políticas no cambian: el público las lee y sólo el propietario las edita. La 0005 vuelve a declarar los mismos grants de la 0003.
7. **`null` significa «sin traducción propia»:** la página en ese idioma deja su texto fijo, es decir, el del HTML generado por el build.
   - El portal convierte un campo vacío en `null`. Nunca guarda un texto en blanco.
   - El sitio (`web/src/js/contenido-publico.js`) usa `valor_en` en `/en/` y `valor_fr` en `/fr/` cuando traen texto. Nunca muestra en esas páginas el `valor` editado en español.
   - Lee con `select=*`, así funciona antes y después de la 0005.
8. **Los precios no se traducen:** el monto es el mismo en los tres idiomas y cada página lo formatea.
   - La restricción `contenido_precio_sin_traduccion` exige `valor_en` y `valor_fr` en `null` cuando `tipo = 'precio'`.
   - El portal muestra un solo campo para los precios.
9. **Respaldo del portal cuando falta la 0005:**
   - El portal pide `valor_en` y `valor_fr` por nombre. Si la base responde que la columna no existe, vuelve a leer sin ellas, avisa en **Textos** y deja editar sólo el español.
   - **Supuesto explícito, sin verificar contra el proyecto real:** PostgREST informa la columna inexistente con HTTP 400 y el código `42703` (en `select=`) o `PGRST204` (en el cuerpo de un PATCH). Como respaldo, se reconoce también el mensaje «column … does not exist» o «could not find the '…' column» (`esColumnaInexistente` en `web/src/admin/js/errores.js`).
   - Para esta decisión no se llamó a Supabase: las pruebas usan respuestas simuladas.
   - Si el supuesto falla, la lectura muestra el error de Supabase en vez del aviso, y el propietario no puede editar hasta aplicar la 0005.
10. **Guardar sólo las columnas que cambiaron:**
    - Cada fila de **Textos** manda en un solo PATCH sólo los idiomas cuyo campo se modificó (`columnasCambiadas` en `web/src/admin/js/logica-contenido.js`).
    - Así, guardar el inglés no devuelve el español ni el francés al valor cargado al abrir la vista, si alguien los cambió entretanto en otra pestaña, en el teléfono o en el SQL Editor. Es el hallazgo P1 de la revisión.
11. **`/admin` queda sólo en español:** el build no genera `/en/admin` ni `/fr/admin`, y el portal no lleva marcado `data-i18n`. El único usuario es el propietario.

## Alternativas descartadas

- **Una tabla aparte de traducciones (clave, idioma, texto):** obliga a una segunda lectura o a un join en el sitio y en el portal. Con tres idiomas fijos, dos columnas son más simples y se validan con CHECK.
- **Copiar el español en `valor_en` y `valor_fr` como semilla:** las páginas en inglés y en francés mostrarían español con apariencia de texto editado. Con `null`, queda el texto fijo del build.
- **Control de concurrencia optimista (`&actualizado=eq.<fecha>` en el PATCH):** detectaría también dos ediciones del mismo idioma. Queda para más adelante, porque depende de que la fecha que devuelve PostgREST vuelva idéntica en el filtro, y eso no se verificó contra el proyecto real. Con la decisión 10, lo único que se pisa es el mismo idioma de la misma fila, como antes de la 0005.
- **Portal en tres idiomas:** no hay otro usuario que el propietario. Duplicaría los mensajes sin beneficio.

## Consecuencias y riesgos

- **La traducción fija no sigue al español editado:** si el propietario cambia el español y deja vacío el inglés, `/en/` sigue mostrando la traducción del texto original. El portal y `docs/portal-gestion.md` piden escribir también el inglés y el francés.
- **Hasta la PR del marcado, el sitio queda sólo en español:** el build publica en `/en/` y `/fr/` sólo las páginas con al menos una marca `data-i18n` o `data-i18n-attr` (`publicables()` en `web/build.py`, hallazgo H2 de la revisión del build).
  - Una página sin marcas saldría en español, pero con `lang="en"` (un lector de pantalla la leería con la voz del inglés), con hreflang que la anuncian como versión inglesa y con una regla `302!` que manda ahí a los navegadores en inglés.
  - Sin ninguna página marcada, no se escriben `en/`, `fr/`, `_redirects` ni hreflang. El build lo avisa con `AVISO_I18N` e `IDIOMAS sólo español`.
  - Por eso el portal no promete una traducción: dice que un campo vacío deja «el texto fijo de la página (el original en español mientras esa página no esté traducida)». Es el hallazgo P3 de la revisión.
  - Esta rama se puede fusionar antes que la PR del marcado: sin marcas, el build publica el sitio sólo en español, como hoy.
  - `web/tests/test_contenido_i18n.py` exige que, en cada página ya marcada, todo `data-contenido` tenga su `data-i18n` con texto en `en.json` y en `fr.json`. Las páginas todavía sin marcar quedan como pruebas omitidas.
- **Ediciones simultáneas del mismo idioma:** gana el último que guarda, sin aviso. Ver la alternativa descartada del control optimista.
- **La 0005 no se aplica sola:** el CI la prueba en un Supabase local, pero no toca el proyecto real.

## Después de fusionar

1. En el SQL Editor de Supabase, pegar y ejecutar `web/supabase/migrations/0005_contenido_idiomas.sql`.
2. Ejecutar `web/supabase/tests/idiomas_test.sql`. El resultado esperado es `PRUEBAS_IDIOMAS_OK`.
3. En el portal, pulsar **Actualizar** en **Textos**: aparecen los campos de inglés y francés.

Los pasos detallados están en `docs/portal-gestion.md`, paso 2, punto 4, y en la sección 7. Mientras la 0005 no esté aplicada, el portal edita sólo el español y el sitio en inglés y en francés muestra su texto fijo.
