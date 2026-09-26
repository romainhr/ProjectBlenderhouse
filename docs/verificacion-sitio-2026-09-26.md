# Verificación del sitio LOFT 2D2B (2026-09-26)

Workflow `verificar-sitio-reservas`: cuatro revisores (API de Supabase sin crear filas, seguridad del front, lógica de reservas, teléfono y accesibilidad) y un escéptico por dimensión que intentó refutar cada hallazgo. Aquí sólo están los **confirmados**.

Reparto acordado con Romain Ange:
- **Backend y publicación** (`web/supabase/`, `web/build.py` y `web/desplegar.py`): sesión «Modelo 3D departamento desde planos».
- **Diseño** (`web/src/`, HTML, CSS y JS de interfaz): sesión «Modelo 3D, navegación móvil y UI».

Las líneas citadas son del código revisado a las 02:50. Si el diseño cambió, aplica el criterio y no el número de línea.

## api (backend)

### API-03 · baja · **aplicado**: current_date depende del huso de la sesión, que el cliente controla, y no coincide con el día local del front
- **Archivo:** `web/supabase/migrations/0001_reservas.sql`, línea 69.
- **Qué pasa:** Las validaciones usan current_date, que sigue el TimeZone de la sesión. PostgREST lo deja cambiar con la cabecera Prefer: timezone. Un cliente puede pedir una entrada que ya pasó en UTC (entre las 00:00 y las 12:00 UTC) o una hasta 366 días adelante. Además, el front calcula HOY con el día local del visitante (reserva-logica.js:33-35) y la base usa, por defecto, la fecha UTC (inferido: es el valor por defecto de Supabase y no pude confirmarlo, porque ahora ambas fechas coinciden). Entre las 21:00 y las 23:59 de Chile (UTC-3), elegir llegada hoy termina en «La llegada no puede ser en el pasado».
- **Corrección:** Usar un único huso fijo, el de la propiedad, en la base y en el front. Se supone America/Santiago por CLP y es-CL; hay que confirmarlo con el usuario. (1) En 0001_reservas.sql, en el bloque declare de solicitar_reserva (después de la línea 64), agregar `v_hoy date := (now() at time zone 'America/Santiago')::date;` y reemplazar `current_date` por `v_hoy` en las líneas 69 y 72. (2) En reserva-logica.js:33-35, dejar `export const ZONA_PROPIEDAD = "America/Santiago"; export function hoyIso(ahora = new Date()) { return new Intl.DateTimeFormat("en-CA", { timeZone: ZONA_PROPIEDAD, year: "numeric", month: "2-digit", day: "2-digit" }).format(ahora); }`. (3) En tests/reserva-logica.test.mjs:21, usar un instante fijo que no dependa del huso de la máquina: `assert.equal(hoyIso(new Date("2026-10-06T02:30:00Z")), "2026-10-05");`. (4) En reservas_test.sql:8, usar `hoy date := (now() at time zone 'America/Santiago')::date;`; si no, la prueba 5a (hoy - 1) falla entre las 00:00 y las 03:00 UTC. (5) Aplicar el `create or replace function` en Supabase y volver a correr reservas_test.sql y `npm test`.

### API-06 · baja · **aplicado**: Extensión btree_gist innecesaria e instalada en el esquema public
- **Archivo:** `web/supabase/migrations/0001_reservas.sql`, línea 12.
- **Qué pasa:** La única exclusión usa `daterange(...) with &&` (línea 28). Los tipos de rango ya tienen soporte GiST nativo; btree_gist solo hace falta para combinar columnas escalares con `=`. Sin `with schema`, la extensión queda en el esquema expuesto por la API, y el asesor de Supabase lo marca (extension_in_public). No pude verificar si sus funciones aparecen como RPC: la raíz OpenAPI exige la clave secreta y los sondeos no son concluyentes.
- **Corrección:** (1) En 0001_reservas.sql, quitar la línea 12 (`create extension if not exists btree_gist;`) para que una instalación nueva no la cree. (2) Como la base real ya la tiene, agregar web/supabase/migrations/0002_quitar_btree_gist.sql con `drop extension if exists btree_gist;`, sin CASCADE: si algo dependiera de ella, falla y no cambia nada. El usuario la ejecuta en el SQL Editor. (3) En el ADR 0003, línea 41, cambiar «(`btree_gist`, `daterange '[)'`)» por «(GiST nativo de rangos, `daterange '[)'`)». (4) Volver a correr reservas_test.sql y confirmar PRUEBAS_OK: las pruebas 2 y 3 ejercitan la exclusión.

Descartados por el escéptico: API-01 (Cualquiera con la clave pública puede bloquear todo el calendario con unas 13 so); API-02 (Registro de Auth abierto y rol authenticated con EXECUTE, aunque el sitio no usa); API-04 (Errores no controlados devuelven el mensaje crudo de Postgres con la fila comple); API-05 (disponibilidad devuelve [] con HTTP 200 ante rangos inválidos y permite consulta).

## seguridad_front (backend)

### SF-01 · media · pendiente: build.py sólo rechaza dos formas de clave de servicio: cualquier otro secreto se publica en config.js
- **Archivo:** `web/build.py`, línea 132.
- **Qué pasa:** La verificación funciona como lista negra: aborta sólo si la clave empieza con 'sb_secret_' o si es un JWT cuyo payload contiene "service_role". Todo lo demás se escribe tal cual en dist/js/config.js, que es público. Si por error se pone en SUPABASE_CLAVE_PUBLICA un token personal de acceso (sbp_..., que da acceso de administración a toda la cuenta), la contraseña de la base de datos, un JWT 'authenticated' o una clave de servicio con un espacio al inicio (los valores de os.environ no se recortan, línea 223), el build la publica. El riesgo es concreto ahora mismo, porque el usuario está buscando un token personal de acceso.
- **Corrección:** En web/build.py, cambiar la lista negra por una lista blanca. (1) Agregar `RE_PUBLICABLE = re.compile(r"sb_publishable_[A-Za-z0-9_-]{20,}")` y la función `def _es_clave_publica(clave):
    if RE_PUBLICABLE.fullmatch(clave):
        return True
    try:
        datos = json.loads(_payload_jwt(clave) or "null")
    except ValueError:
        return False
    return isinstance(datos, dict) and datos.get("role") == "anon"`. (2) En configuracion(), usar `clave = (env.get("SUPABASE_CLAVE_PUBLICA") or env.get("SUPABASE_ANON_KEY", "")).strip()` y `url = env.get("SUPABASE_URL", "").strip().rstrip("/")`. Reemplazar las líneas 132-133 por `if clave and not _es_clave_publica(clave): raise SystemExit("SUPABASE_CLAVE_PUBLICA no es la clave publicable (sb_publishable_…) ni un JWT «anon»: no se publica. No uses la clave de servicio, un token personal ni la contraseña de la base.")`; el mensaje no debe imprimir el valor. (3) Agregar web/tests/test_build.py (unittest, con build.DIST en un tempfile.mkdtemp() que tenga js/) con estos casos ficticios: se aceptan sb_publishable_ y JWT anon; se rechazan sb_secret_, ' sb_secret_', sbp_, texto cualquiera, JWT authenticated y JWT service_role. Sumar a package.json `"test:build": "python3 -m unittest discover -s tests -p 'test_*.py'"`. (4) En ADR 0003, línea 43, cambiar «El build rechaza la clave de servicio» por «El build sólo acepta la clave publicable o un JWT anon».

### SF-03 · baja · pendiente: La CSP del tour permite todo cdn.jsdelivr.net y el import map no tiene integridad
- **Archivo:** `web/build.py`, línea 174.
- **Qué pasa:** script-src autoriza el host completo https://cdn.jsdelivr.net, que sirve cualquier paquete de npm o repositorio de GitHub. Ante una inyección de HTML en el tour, un atacante podría cargar su propio script desde jsDelivr sin que la CSP lo impida. Hoy no encontré un punto de inyección, así que esto es defensa en profundidad. Además, three@0.160.0 se carga sin integridad: un compromiso del CDN ejecutaría código en la página.
- **Corrección:** En web/build.py, dentro de politicas(), reemplazar la línea 174 por `cdn = sorted(set(re.findall(r"https://cdn\.jsdelivr\.net/npm/[A-Za-z0-9._-]+@[0-9][0-9.]*/", s)))` y `scripts = "script-src 'self'" + ((" " + " ".join(cdn + en_linea)) if en_linea else "")`. El resultado en el tour es `script-src 'self' https://cdn.jsdelivr.net/npm/three@0.160.0/ 'sha256-…' 'sha256-…'`. Después de reconstruir, el agente que aplique el cambio debe abrir /tour/ y confirmar que no hay violaciones de CSP en la consola y que el modelo carga con texturas.

Descartados por el escéptico: SF-02 (El campo trampa sólo se evalúa en el navegador; la RPC se puede llamar directame); SF-04 (Directivas CSP más amplias de lo necesario: worker-src, connect-src a Supabase e); SF-05 (style-src con 'unsafe-inline' en todas las páginas); SF-06 (_headers sin línea base de CSP en cabecera ni Cross-Origin-Opener-Policy); SF-07 (El consentimiento se exige sólo en el navegador y no queda registrado); SF-08 (El formulario de reserva haría un GET con los datos personales en la URL si se e); SF-09 (web/dist/ (con config.js y la clave pública) no está excluido en .gitignore).

## correctitud (backend)

### H1 · alta · **aplicado**: Si el visitante toca el calendario o cambia los huéspedes mientras se envía, una solicitud que sí se creó aparece como error de red
- **Archivo:** `web/src/js/reserva.js`, línea 101.
- **Qué pasa:** Mientras la solicitud está en curso, solo se bloquean los botones Enviar (resumen(), línea 147). El clic en el calendario (líneas 101-114) y los botones +/- (129-130) no revisan estado.enviando. Si el visitante toca un día en ese momento, el manejador deja estado.salida = null (línea 107). Cuando llega la respuesta correcta, exito() (líneas 199-202) arma el texto con el estado actual, no con lo que se envió. fLargo.format(aFecha(null)) lanza RangeError: Invalid time value. Ese error lo captura el mismo try/catch del envío (línea 188), codigoError lo convierte en 'red' y se muestra 'No se pudo conectar con el servidor de reservas. Intenta de nuevo.'. La solicitud ya quedó creada y pendiente, bloqueando esas noches. La pantalla de éxito no aparece y el visitante no ve su código. Si reintenta, recibe fechas_ocupadas por su propia solicitud o crea una segunda. Si en cambio toca +/-, el texto de éxito muestra una cantidad de huéspedes distinta de la enviada.
- **Corrección:** En web/src/js/reserva.js:
1) Agregar `if (estado.enviando) return;` como primera línea del manejador de #meses (línea 102) y de huespedes() (línea 124).
2) En el submit, congelar lo enviado antes del await: `const pedido = { entrada: estado.entrada, salida: estado.salida, huespedes: estado.huespedes, nombre: datos.nombre.trim(), email: datos.email.trim(), telefono: datos.telefono.trim(), mensaje: datos.mensaje.trim() };`. Cambiar la firma a `function exito(codigo, n, p)` y usar p.entrada, p.salida y p.huespedes en las líneas 201-202. En la línea 180, llamar `exito("—", v.noches, estado)`.
3) Sacar exito() del try: `let r; try { [r] = await solicitar(pedido); } catch (err) { ...igual...; return; } finally { ...igual... }` y después `exito(r.codigo, r.noches, pedido);`. Así, un fallo al pintar nunca se muestra como error de red.
Prueba: con el DOM mínimo, hacer clic en un día y en #mas durante el envío. Comprobar que #exito queda visible y que muestra las fechas y los huéspedes enviados.

### H2 · media · **aplicado**: Husos horarios: el front usa el día local del visitante y la base usa current_date del servidor
- **Archivo:** `web/supabase/migrations/0001_reservas.sql`, línea 69.
- **Qué pasa:** hoyIso() (reserva-logica.js:33-35) toma el día local del navegador. solicitar_reserva compara con current_date (líneas 69 y 72), que se calcula en la zona de la sesión de Postgres. Supabase usa UTC por defecto. Lo que pasa es esto:
(a) En Chile desde las 21:00 (UTC-3, horario de verano) o las 20:00 (UTC-4, invierno) hasta la medianoche, el calendario deja elegir 'hoy'. validarRango lo acepta y el servidor responde fecha_pasada. El catch (líneas 188-191) muestra 'La llegada no puede ser en el pasado.' en #cal-error pero no vuelve a pintar el calendario. Hoy sigue habilitado y cada reintento da el mismo error. En México, Colombia o Perú (UTC-6/-5) esto pasa desde las 18:00-19:00.
(b) Al este de UTC (por ejemplo, España entre las 00:00 y las 02:00 locales), el front permite llegar el día hoy_local+365 = UTC+366, y el servidor responde fecha_lejana.
(c) HOY se calcula una sola vez al cargar (reserva.js:9, y sitio.js:41 en la portada). Si la página sigue abierta después de medianoche, el día anterior sigue habilitado y el servidor lo rechaza.
- **Corrección:** Usar en ambos lados la misma zona, la del inmueble. Hay que confirmarla con el usuario: CLP sugiere Chile, pero la ubicación no está publicada.
SQL, en una migración nueva 0002: `create or replace function public.hoy_loft() returns date language sql stable as $$ select (now() at time zone 'America/Santiago')::date $$;`. Volver a crear solicitar_reserva con `public.hoy_loft()` en lugar de current_date en las líneas 69 y 72.
JS, en reserva-logica.js:33-35: `export const ZONA = "America/Santiago"; export function hoyIso(ahora = new Date()) { return new Intl.DateTimeFormat("en-CA", { timeZone: ZONA, year: "numeric", month: "2-digit", day: "2-digit" }).format(ahora); }`.
En reserva.js, ante fecha_pasada o fecha_lejana en el catch, recalcular HOY y HASTA (cambiarlos a let), llamar a cargarDisponibilidad() y volver a pintar.
Pruebas: reemplazar la aserción de test.mjs:21 por `hoyIso(new Date("2026-09-27T01:00:00Z")) === "2026-09-26"` y `hoyIso(new Date("2026-09-27T03:30:00Z")) === "2026-09-27"`, que no dependen del TZ del equipo. Agregar una prueba de hoy_loft() en reservas_test.sql y registrar el criterio en el ADR 0003.

### H3 · media · **aplicado**: Calendario sin salida: se puede elegir una llegada que no admite ninguna salida y el visitante queda atrapado
- **Archivo:** `web/src/js/reserva.js`, línea 39.
- **Qué pasa:** estadoDia() habilita como llegada cualquier noche libre, aunque la noche siguiente esté ocupada. Pasa, por ejemplo, con una noche suelta antes de otra llegada o entre dos reservas. En ese caso salidaMaxima(entrada) < entrada + minNoches, la ventana de salida queda vacía y todos los días posteriores se deshabilitan (líneas 43-45). Según la condición de la línea 105, solo se puede cambiar la llegada tocando un día anterior. Si esa llegada es hoy, o el primer día libre, no hay ningún día clicable salvo la misma llegada, y no aparece ningún mensaje: hay que recargar la página. Además, aunque la llegada sea válida, mientras se elige la salida no se puede cambiar la llegada a un día posterior a la ventana (más de 30 noches o más allá de la próxima llegada) sin antes completar el rango o tocar un día anterior.
- **Corrección:** En reserva.js, definir `const LLEGADA_MAX = sumarDias(HOY, TARIFA.anticipacionMaxDias);` y dos funciones:
`const llegadaPosible = (d) => d >= HOY && d <= LLEGADA_MAX && !nocheOcupada(d, estado.ocupados) && salidaMaxima(d, estado.ocupados) >= sumarDias(d, TARIFA.minNoches);`
`const salidaPosible = (d) => Boolean(estado.entrada && !estado.salida) && d >= sumarDias(estado.entrada, TARIFA.minNoches) && d <= salidaMaxima(estado.entrada, estado.ocupados);`
En estadoDia, mantener las clases y usar `deshabilitado: !(salidaPosible(dia) || llegadaPosible(dia))`.
En el clic (líneas 105-110): `if (salidaPosible(dia)) estado.salida = dia; else { estado.entrada = dia; estado.salida = null; }`.
En cargarDisponibilidad, línea 214: cambiar `nocheOcupada(estado.entrada, estado.ocupados)` por `!llegadaPosible(estado.entrada)`, para que la entrada de la URL tampoco atrape al visitante.
Conviene llevar las dos funciones a reserva-logica.js, con parámetros hoy y ocupados, y probar en npm test el caso de la noche suelta antes de otra llegada.

### H4 · media · **aplicado**: El calendario y la URL aceptan llegadas entre 366 y 395 días adelante, que luego se rechazan sin ningún mensaje
- **Archivo:** `web/src/js/reserva.js`, línea 40.
- **Qué pasa:** HASTA = HOY + 365 + 30 (línea 10) es el tope correcto para la salida, pero estadoDia() también lo usa como tope de la llegada (línea 40). Por eso quedan habilitados como llegada 30 días que validarRango rechaza con fecha_lejana (reserva-logica.js:59). Lo mismo pasa con el parámetro ?entrada= de la URL, que solo se compara con HOY (línea 30). El visitante completa el rango, el resumen queda en '—' y #enviar queda deshabilitado (líneas 147-149). El mensaje fecha_lejana solo se muestra dentro del submit (línea 167), y el submit nunca ocurre porque los botones están deshabilitados, también al pulsar Enter. Nunca se entera de por qué no puede enviar. Además, una llegada en HASTA no admite ninguna salida (otro caso de H3).
- **Corrección:** Usar LLEGADA_MAX = sumarDias(HOY, TARIFA.anticipacionMaxDias) como tope de llegada en estadoDia, con el mismo llegadaPosible de H3. HASTA queda solo para la salida y para disponibilidad().
En la línea 30, exigir además `q.get("entrada") <= LLEGADA_MAX`.
Como respaldo, en resumen(): `const err = $("#cal-error"); if (estado.entrada && estado.salida && !v.ok && v.error) mostrarError(err, MENSAJES[v.error]);`. Así el motivo se ve sin esperar al submit.

### H6 · baja · **aplicado**: El botón 'mes siguiente' lleva a una página de dos meses sin ningún día habilitado
- **Archivo:** `web/src/js/reserva.js`, línea 94.
- **Qué pasa:** #mes-sig se deshabilita solo cuando el primer mes mostrado empieza en HASTA o después, pero cada página muestra dos meses. Por eso la última página alcanzable queda completamente deshabilitada.
- **Corrección:** En reserva.js:94: `$("#mes-sig").disabled = new Date(Date.UTC(estado.mes.anio, estado.mes.mes + 2, 1)) > aFecha(HASTA);`. Así la última página alcanzable es [sept, oct 2027], que contiene HASTA. La página anterior sigue habilitada, porque 2027-10-01 <= HASTA.

Descartados por el escéptico: H5 (Parámetros de la portada: una salida inválida se descarta sin avisar y la portad); H7 (El largo del nombre se mide distinto: el front cuenta unidades UTF-16 y la base ).

## responsive_a11y (diseño)

### RA-01 · alta · pendiente: Texto del hero sobre la imagen sin contraste suficiente (bajada, h1 y aviso «Sitio de prueba»)
- **Archivo:** `web/src/css/loft.css`, línea 117.
- **Qué pasa:** El degradado de .hero::after baja a 0,15 de opacidad hacia el 35 % de la altura, que es donde quedan el h1, la bajada (#d8d4cc, 17-18 px) y el aviso de sitio de prueba (#8a909a, 12 px, sobre velo de 0,6). En teléfono, el recorte central de living-1600 pone el ventanal iluminado detrás de la bajada. En computador, detrás de «LOFT» quedan el muro blanco y la lámpara de arco. El aviso es justamente la advertencia de que las imágenes son renders. Es una estimación hecha sin navegador: compuse píxeles reales de web/dist/img/living-1600.jpg con el degradado del CSS, en posiciones calculadas para 390×865 y 1440×900.
- **Corrección:** En loft.css:118, usar `linear-gradient(180deg, rgba(15,17,19,.6) 0%, rgba(15,17,19,.5) 35%, rgba(15,17,19,.92) 88%)`, o agregar `.hero .contenedor { background: radial-gradient(ellipse at 20% 60%, rgba(15,17,19,.75), transparent 70%); }`. En loft.css:120, subir el velo del aviso a `rgba(15,17,19,.9)` y darle `color: var(--texto)`. Confirmar con capturas a 390 y 1440 px, revisando también que «2D2B» en óxido llegue a 3:1.

### RA-02 · media · pendiente: Texto blanco sobre óxido: 4,14:1 en todos los botones primarios, el día elegido y el tour
- **Archivo:** `web/src/css/loft.css`, línea 75.
- **Qué pasa:** El texto #f6f4ef sobre #c0562f no llega a 4,5:1. El texto de 14 px en peso 600 no cuenta como texto grande (eso empieza en 18,66 px en negrita). Afecta a todas las llamadas a la acción (Reservar, Entrar al tour 3D, Ver disponibilidad, Solicitar reserva), a los días de llegada y salida del calendario (.dia.extremo, línea 265) y a dos botones del tour inyectado: #entrar y #sitio-barra a.primario, este último de 11 px (web/src/css/tour-loft.css, líneas 20 y 30).
- **Corrección:** - Usar `background: var(--oxido-2)` (#a84622) como fondo normal en .boton.primario (loft.css:75), .dia.extremo (loft.css:265), #entrar (tour-loft.css:20) y #sitio-barra a.primario (tour-loft.css:30).
- Usar un tono más oscuro para hover (por ejemplo #8f3b1c).
- Mantener #c0562f en bordes y anillos de foco.

### RA-03 · media · pendiente: Precio de ejemplo sin marcar en la barra fija del teléfono
- **Archivo:** `web/src/index.html`, línea 281.
- **Qué pasa:** En pantallas de menos de 1000 px, la barra inferior muestra siempre «CLP 58.000 / noche» sin decir que es un ejemplo. La tarjeta de tarifas sí lo marca, y el ADR exige marcar como ejemplo todo lo no modelado. En reserva.html la barra muestra el total estimado, también sin la marca.
- **Corrección:** - En index.html:281, usar `<small>/ noche · ejemplo</small>`.
- En reserva.js:146, usar `` `${v.noches} noches · ejemplo` ``.

### RA-04 · media · pendiente: El formulario pide datos personales sin advertir que es un sitio de prueba
- **Archivo:** `web/src/reserva.html`, línea 70.
- **Qué pasa:** La página de reserva pide nombre, correo y teléfono, y promete «te confirmamos por correo». La advertencia de no enviar datos reales sólo aparece en privacidad.html. El ADR 0003 dice que, por ser prueba, sólo deben usarse datos inventados. Sin ese aviso junto al formulario, un visitante puede dejar datos personales reales (información Restringida según la política de la organización).
- **Corrección:** Al comienzo de #formulario (después del h2 de reserva.html:71), agregar `<p class="mensaje">Sitio de prueba: usa un nombre y un correo inventados; no envíes datos reales.</p>`. Si se puede, repetir una versión corta junto a #enviar (línea 109).

### RA-05 · media · pendiente: «Superficie ≈ 54 m²» es la superficie bruta; la útil inferida es de 45 a 47 m²
- **Archivo:** `web/src/index.html`, línea 71.
- **Qué pasa:** El dato de la portada presenta como superficie la bruta sin balcón (6,01 × 8,98 m, que incluye los muros). El brief del modelo da una superficie útil de unos 45 m² (suma de recintos) o 47 m² (entre caras de muro), con un rango de 41 a 50 m² por la incertidumbre de escala. En un aviso de arriendo, la superficie se lee como útil, así que el sitio la exagera en un 15 a 20 %.
- **Corrección:** En index.html:71, usar `<dd><b>≈ 45 m²</b><span class="etiqueta">útiles · inferida ± 5 %</span></dd>`, o bien `<b>≈ 54 m²</b><span class="etiqueta">brutos · inferida del plano</span>`.

### RA-06 · media · pendiente: La barra fija inferior puede tapar el elemento enfocado (WCAG 2.2, criterio 2.4.11)
- **Archivo:** `web/src/css/loft.css`, línea 30.
- **Qué pasa:** Sólo se compensa la cabecera fija con scroll-padding-top. En pantallas de menos de 1000 px, la barra inferior mide 65 px más el área segura inferior (unos 99 px en un iPhone con barra de inicio) y queda encima del contenido. Al avanzar con Tab, el navegador desplaza la página lo justo para mostrar el elemento enfocado, y lo deja debajo de la barra: campos y casilla de reserva.html, enlaces y resúmenes de las preguntas. El pie no queda tapado (112 px de relleno contra unos 99 px de barra), pero sólo sobran 13 px, porque --pie-extra no suma el área segura.
- **Corrección:** - En loft.css, después de la línea 230, agregar `@media (max-width: 999px) { html:has(body.con-barra-movil) { scroll-padding-bottom: calc(80px + env(safe-area-inset-bottom, 0px)); } }`.
- En la línea 230, usar `--pie-extra: calc(72px + env(safe-area-inset-bottom, 0px))`.

### RA-07 · media · pendiente: Campos de formulario: el foco se reduce a un borde de 1 px y el borde en reposo tiene 1,51:1
- **Archivo:** `web/src/css/loft.css`, línea 202.
- **Qué pasa:** La regla :focus de los campos quita el contorno global de :focus-visible, porque tiene más especificidad (0,2,1 contra 0,1,0). En input, select y textarea el foco sólo cambia el borde de 1 px de #33383f a #c0562f, con un contraste de 2,59:1 entre ambos estados. Además, en reposo los campos casi no se distinguen de la tarjeta: la regla 1.4.11 pide 3:1 para identificar un control.
- **Corrección:** - En loft.css:202, cambiar a `.campo input:focus-visible, .campo select:focus-visible, .campo textarea:focus-visible { border-color: var(--oxido); box-shadow: 0 0 0 1px var(--oxido); }` y quitar `outline: none`, para heredar el anillo global.
- En loft.css:200, usar un borde en reposo de #6b717b (3,62:1 sobre #16181b).

### RA-08 · media · **aplicado**: Calendario: role="grid" sin teclado de grilla, estado con aria-pressed y sin motivo en los días deshabilitados
- **Archivo:** `web/src/js/reserva.js`, línea 61.
- **Qué pasa:** La tabla declara role="grid", pero no implementa la navegación con flechas. Cada día es un botón en el orden de tabulación, hasta 62 paradas en dos meses. Los lectores de pantalla pasan a modo foco dentro de un grid y esperan poder moverse con flechas, que no hacen nada. aria-pressed marca igual la llegada, la salida y las noches intermedias. La etiqueta sólo agrega «, ocupado», y los días deshabilitados por estadía mínima o máxima, o por estar fuera de rango, no explican por qué. Las cabeceras son «lu», «ma»… sin nombre completo. El texto de los días deshabilitados y ocupados tiene poco contraste: están exentos por ser controles inactivos, pero ese texto es la única pista visual además de la trama.
- **Corrección:** Arreglo mínimo:
- Quitar `tabla.setAttribute("role", "grid")` (reserva.js:61) y dejar la tabla nativa con botones.
- Usar aria-pressed sólo en la llegada y la salida, y agregar a la etiqueta el estado y el motivo: «, llegada elegida», «, salida elegida», «, dentro de tu estadía», «, no disponible: mínimo 2 noches» u «, ocupado».
- Agregar `year: "numeric"` a fLargo.
- Usar `th.abbr = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"][i]` en las cabeceras.

### RA-10 · media · pendiente: El botón de la pantalla de éxito se desborda y queda cortado en teléfonos de 384 px o menos
- **Archivo:** `web/src/reserva.html`, línea 124.
- **Qué pasa:** El botón «Mientras, recorre el tour 3D →» no puede partirse en líneas (nowrap) y mide unos 340 px, dentro de una tarjeta con 28 px de relleno. En pantallas angostas sobresale de la tarjeta y de la ventana. Como body tiene overflow-x: hidden, la parte que sobra se recorta sin barra de desplazamiento, lo que falla el criterio 1.4.10 (Reflow) a 320 px. Es una estimación por métricas de fuente: JetBrains Mono avanza 0,6 em.
- **Corrección:** - En reserva.html:124, usar `<a class="boton secundario bloque" href="tour/">Ver el tour 3D <span class="flecha" aria-hidden="true">→</span></a>`.
- Como red general, agregar en loft.css `@media (max-width: 480px) { .boton { white-space: normal; text-align: center; line-height: 1.2; padding-block: 12px; } }`.

### RA-11 · media · pendiente: Tour inyectado: la barra «Sitio / Reservar» choca con el mini plano bajo unos 357 px, sus enlaces miden 36/40 px y viewport-fit=cover no deja margen lateral
- **Archivo:** `web/src/css/tour-loft.css`, línea 34.
- **Qué pasa:** Hasta 640 px, build.py y tour-loft.css bajan #sitio-barra a la esquina inferior derecha, en la misma franja que #mapa (inferior izquierda). En pantallas angostas se superponen. Los enlaces inyectados y el botón de ayuda del visor miden menos de 44 px. La inyección agrega viewport-fit=cover, que el visor original no tenía, pero los paneles fijos usan 16 px sin env(safe-area-inset-left/right), así que en un iPhone horizontal quedan bajo la muesca. Además, build.py suma una segunda hoja de Google Fonts sin quitar la del visor, y la IBM Plex Mono del visor queda sin uso porque tour-loft.css redefine --f-mono.
- **Corrección:** - En tour-loft.css, dentro o después del bloque de la línea 32, agregar `@media (max-width: 400px) { #sitio-barra { flex-direction: column; } #sitio-barra a + a { border-left: 0; border-top: 1px solid var(--linea); } }`. Así la barra mide unos 88 px de ancho y deja libre el mapa.
- Agregar `#sitio-barra { right: calc(16px + env(safe-area-inset-right, 0px)); }` y `#cajetin, #mapa { left: calc(16px + env(safe-area-inset-left, 0px)); }`.

### RA-12 · baja · pendiente: Números de sección en óxido de 12 px: 4,16:1 sobre la base y 3,91:1 sobre tarjetas
- **Archivo:** `web/src/css/loft.css`, línea 58.
- **Qué pasa:** .numero y los números del menú usan #c0562f como color de texto en tamaño chico, y no llegan a 4,5:1.
- **Corrección:** - Agregar `--oxido-texto: #d46a40;` en :root.
- Usar `.numero, .menu a span, .panel-menu a span { color: var(--oxido-texto); }`.
- Dejar #c0562f para bordes y decoración.

### RA-13 · baja · pendiente: Rótulos chicos sobre imágenes (figcaption y HUD) entre 3,0:1 y 4,2:1
- **Archivo:** `web/src/css/loft.css`, línea 163.
- **Qué pasa:** Los rótulos de las tarjetas de espacios y el HUD de la maqueta usan texto #8a909a de 12 px sobre un velo de 0,78 a 0,8 que deja ver la imagen. Donde la imagen es clara, el contraste queda bajo 4,5:1. El HUD es uno de los avisos de que el modelo es inferido («Modelo 3D · escala inferida ± 5 %»).
- **Corrección:** En loft.css:163, agregar `color: var(--texto);` a `.espacio figcaption` (queda en 8:1 o más con cualquier fondo bajo el velo de 0,78). Hacer lo mismo en `.tour .hud` (loft.css:174), o subir su velo a 0,9.

### RA-15 · baja · pendiente: viewport-fit=cover sin margen para la muesca en el sitio
- **Archivo:** `web/src/index.html`, línea 5.
- **Qué pasa:** Las tres páginas piden viewport-fit=cover, pero el margen lateral es fijo de 16 px y no usa env(safe-area-inset-left/right). En un iPhone horizontal (por ejemplo 844×390, con la cabecera y la barra de teléfono activas por estar bajo 1000 px), la marca, la hamburguesa y el precio de la barra inferior pueden quedar bajo la muesca. No medí el valor exacto del área segura.
- **Corrección:** - En loft.css:22, usar `--margen: max(16px, env(safe-area-inset-left, 0px), env(safe-area-inset-right, 0px));`.
- En loft.css:26, usar `--margen: max(32px, env(safe-area-inset-left, 0px), env(safe-area-inset-right, 0px));`.
- .barra-movil y .panel-menu ya usan var(--margen), así que no necesitan otro cambio.

### RA-16 · baja · pendiente: Si falla el JS, el contenido de la portada queda invisible
- **Archivo:** `web/src/css/loft.css`, línea 234.
- **Qué pasa:** Las secciones con .aparece empiezan con opacidad 0 y sólo se muestran cuando sitio.js les agrega .visible. sitio.js es un módulo que importa reserva-logica.js. Si el módulo no carga (red, CSP, bloqueador o un error en el grafo de módulos), las secciones Espacios, Tour, Equipamiento, Tarifas y Preguntas quedan en blanco. Los precios con data-precio también quedan vacíos.
- **Corrección:** - En loft.css:234, usar `.js .aparece { opacity: 0; transform: translateY(12px); … }` y `.js .aparece.visible { opacity: 1; transform: none; }`.
- En el `<head>` de index.html, antes del módulo, agregar `<script>document.documentElement.classList.add('js')</script>`. Como la CSP es 'self', en build.py hay que dar el hash o ponerlo en un .js no-módulo.
- Otra opción, sin tocar la CSP: poner `document.documentElement.classList.add("js")` en la primera línea de sitio.js, sabiendo que no cubre un fallo del grafo de módulos.

### RA-17 · baja · pendiente: Nombres accesibles y puntos de referencia: números pegados, menú de computador fuera de un <nav> y sin enlace de salto
- **Archivo:** `web/src/index.html`, línea 28.
- **Qué pasa:** En computador no hay punto de referencia de navegación: el menú visible es un <ul> suelto y el <nav> del panel queda con display:none. Los números decorativos se pegan al nombre de los enlaces y del h1. El «+» de los resúmenes de las preguntas se suma a su nombre en Chrome. Con 7 elementos enfocables en la cabecera, falta un enlace para saltar al contenido.
- **Corrección:** - En index.html:28-34 y reserva.html:25-30, envolver el menú en `<nav aria-label="Principal">…</nav>`.
- Usar `<span aria-hidden="true">01</span>` en los números del menú y del panel.
- En loft.css:213-214, usar `content: "+" / "";` y `content: "−" / "";`.
- En index.html:57, escribir `Loft <span>2D2B</span>`.

### RA-18 · baja · **aplicado**: Se pierde el foco al deshabilitar botones del contador y del calendario, y al cerrar el menú con Escape
- **Archivo:** `web/src/js/reserva.js`, línea 127.
- **Qué pasa:** Al llegar al límite, el botón que tiene el foco se deshabilita y el foco cae al body: «+» al llegar a 4, «−» en 1, y las flechas de mes en los extremos. En sitio.js, Escape cierra el panel del menú sin devolver el foco a la hamburguesa. Si el foco estaba en un enlace del panel, se pierde.
- **Corrección:** - En sitio.js:17, usar `document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) { cerrar(); boton.focus(); } });`.
- En reserva.js, al final de huespedes(n), agregar `if (document.activeElement?.disabled) (estado.huespedes <= 1 ? $("#mas") : $("#menos")).focus();`.
- Al final de pintar(), agregar `if (document.activeElement?.disabled) (…el otro botón de mes…).focus();`. Otra opción: usar aria-disabled e ignorar el clic.

Descartados por el escéptico: RA-09 (Días del calendario de menos de 44 px en teléfonos y en tableta horizontal); RA-14 (Cabecera entre 320 y unos 370 px: se desborda o parte la marca, y el botón mide ); RA-19 (Reglas de ejemplo y detalles inferidos presentados como hechos); RA-20 (Privacidad: no hay canal de contacto para pedir el borrado).
