# ADR 0003: sitio de arriendo turístico con el tour 3D (Netlify + Supabase, diseño en Stitch)

- **Fecha:** 2026-09-26
- **Estado:** aceptado. Versión inicial publicada en https://loft-2d2b.netlify.app (2026-09-26, desplegada por Romain Ange); el rediseño de `web/src` está en curso en otra sesión.
- **Modelo de IA utilizado:** Claude Opus 5.5 (`claude-opus-5-5`). Stitch (Google) generó las pantallas de referencia del diseño con Gemini 3.8 Flash.
- **Revisor humano:** Romain Ange. Pidió el sitio y confirmó que Stitch, Netlify y Supabase están aprobados para este proyecto personal de prueba.

## Contexto

El usuario quiere hospedar el recorrido 3D del departamento en un sitio web «ultra moderno industrial» que:
- permita recorrer la propiedad y solicitar reservas para arriendo turístico;
- funcione en computador y en teléfono;
- use el diseño de Stitch;
- use plataformas gratuitas (Supabase, Netlify u otras).

Es una prueba: las tarifas y parte del equipamiento son de ejemplo, y las imágenes son renders, no fotos.

## Decisiones

1. **Sitio estático sin framework ni dependencias:**
   - HTML, CSS y JS nativos en `web/src/`.
   - `web/build.py`, en Python con Pillow ya instalada, arma `web/dist/`.
   - Pruebas de la lógica con el ejecutor incluido en Node (`cd web && npm test`), sin instalar paquetes.
   - Motivo: no hay nada que compilar y así no se agregan herramientas externas.
2. **Diseño de Stitch como referencia, no como código:**
   - Se creó un proyecto en Stitch con un sistema de diseño propio (`web/diseno/DESIGN.md`) y se generaron cinco pantallas, guardadas en `web/diseno/stitch/`.
   - Del resultado se tomaron los tokens (colores, tipografías, radio de 2 px, retícula técnica, cotas, numeración de secciones) y la composición, reescritos en CSS propio.
   - No se usa su HTML, que depende de Tailwind por CDN, imágenes generadas por IA y texto con datos inventados: «Santiago», «doble altura», «wifi de 500 Mbps», «cuarzo negro».
   - El contenido del sitio sale del modelo, y lo no modelado se marca como «ejemplo».
3. **Netlify para el hosting:**
   - Hosting estático gratuito con HTTPS y CDN. Sirve `.glb` y `.bin`, aunque se mantiene el transporte de la página publicada, que ya está validado.
   - La política de seguridad (CSP) va como `<meta>` en cada página. En `_headers`, Netlify junta las reglas que calzan con una misma ruta, y el tour quedaría con dos políticas, una de las cuales bloquea sus scripts.
   - La CSP del tour permite jsDelivr y los hashes de sus dos scripts en línea, que calcula el build.
   - Despliegue desde `web/dist/`, sin build en Netlify.
4. **Supabase para las reservas:**
   - Reservas como solicitudes sin cobro en línea que el dueño confirma.
   - La tabla `reservas` tiene RLS activa y sin políticas, así que la clave pública no puede leerla ni escribirla.
   - El público sólo ejecuta dos funciones `SECURITY DEFINER`:
     - `disponibilidad`: devuelve rangos ocupados, sin datos personales;
     - `solicitar_reserva`: valida y devuelve sólo el código y las noches.
   - Una restricción de exclusión (GiST nativo de rangos, `daterange '[)'`) impide que dos solicitudes activas compartan noches, aun si llegan al mismo tiempo.
   - Pruebas SQL en `web/supabase/tests/reservas_test.sql`, dentro de una transacción que se deshace.
   - La URL y la clave pública llegan por variables de entorno a `js/config.js`, que genera el build. El build rechaza la clave de servicio.
5. **Tour en teléfono:** el build genera texturas de 512 px (6,4 MB en vez de 15,3 MB) y un índice `depto_web_movil.json`.
   - El visor lo prueba primero en pantallas táctiles o chicas.
   - Si no lo encuentra, como en la página publicada, usa el índice normal.

## Alternativas descartadas

- **Netlify Forms:** no da un calendario de disponibilidad ni evita reservas dobles.
- **Cobro con pasarela de pago:** fuera del alcance de una prueba, y agrega manejo de datos de pago.
- **Framework (Vite, Next):** agrega dependencias sin necesidad.

## Consecuencias y riesgos

- **Abuso de las solicitudes:** las pendientes bloquean noches. Un tercero podría llenar el calendario con solicitudes falsas. Mitigaciones: un campo trampa en el formulario y que el dueño rechace desde el panel. Si el sitio pasa a uso real, hay que agregar límite de tasa o captcha.
- **Datos personales:** nombre, correo y teléfono de huéspedes. Por ser prueba, se deben usar sólo datos inventados. Para uso real faltan un aviso de privacidad revisado, plazos de borrado y revisar la ley de datos personales aplicable.
- **Imágenes:** son renders de un modelo inferido desde el plano (± 5 %). El sitio lo dice en la portada, en el pie y en las preguntas.

## Adenda: verificación y reparto (2026-09-26)

- **Modelo de IA utilizado:** Claude Opus 5.5, con el workflow `verificar-sitio-reservas` (8 agentes: 4 revisores y 4 escépticos). Registro en `docs/verificacion-sitio-2026-09-26.md`.
- **Revisor humano:** Romain Ange.

6. **«Hoy» en el huso de la propiedad:**
   - La función `solicitar_reserva` usaba `current_date`, que sigue el huso de la sesión. PostgREST permite cambiarlo con la cabecera `Prefer: timezone`, y por defecto es UTC. Por eso, de noche en Chile, «hoy» salía rechazado.
   - La migración `0002_hoy_propiedad.sql` agrega `public.hoy_loft()`, que devuelve la fecha en America/Santiago. El front usa el mismo huso en `ZONA_PROPIEDAD`.
   - **Supuesto:** Chile continental, por las tarifas en CLP; la ubicación no está publicada.
   - La 0002 también quita `btree_gist`, que no hacía falta. La 0001 no se reescribe porque ya está aplicada.
7. **Clave de Supabase por lista blanca:** `build.py` sólo publica una clave `sb_publishable_…` o un JWT con rol `anon`. Antes sólo rechazaba dos formas de la clave de servicio.
8. **CSP derivada de cada página:** `build.py` arma la política de cada HTML con lo que ese HTML carga:
   - scripts propios;
   - de jsDelivr, sólo las rutas exactas `paquete@versión`, nunca el CDN completo;
   - Google Fonts sólo si la página lo enlaza;
   - hashes de los scripts en línea.
9. **Tour propio del sitio:** si existe `web/src/tour/index.html` (visor v3, con three.js alojado en el sitio), el build lo usa tal cual y genera `tour/modelo/` con `web/tour_modelo.py`. El visor de la página publicada queda como respaldo.
10. **Reparto entre dos sesiones de Claude:**
    - La sesión «Modelo 3D, navegación móvil y UI» se ocupa del diseño en `web/src/`.
    - Esta sesión se ocupa del backend y la publicación: `web/supabase/`, `web/build.py` y `web/desplegar.py`.
    - La publicación en Netlify la ejecuta el usuario: en esta sesión, el modo automático bloquea el despliegue.
