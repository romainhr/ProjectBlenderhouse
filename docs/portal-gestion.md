# Portal de gestión: puesta en marcha en Supabase

Con el portal, el propietario inicia sesión y puede editar los textos del sitio, subir u ocultar fotos y manejar las reservas: confirmarlas, rechazarlas, anotarlas o borrarlas. Esta guía prepara la base de datos. La interfaz del portal va aparte.

Todos los pasos se hacen en el panel de Supabase del proyecto: **SQL Editor** para el SQL y **Authentication** para las cuentas. Claude no aplica migraciones, no crea cuentas y no maneja contraseñas.

**Estado al 2026-09-26**, según un sondeo de sólo lectura con la clave pública:

- La 0003 no está aplicada: `contenido` y `es_propietario` no existen.
- El registro público está **abierto** (`disable_signup: false`); el paso 3 lo cierra antes de crear la cuenta. La confirmación por correo está activa y las sesiones anónimas, desactivadas.
- La 0002 está aplicada: la función del día de la propiedad es interna y el rol público no la ve (es lo esperado). La 0004 le cambia el nombre, porque el departamento no es un loft.

## 1. Revisar la 0002

En el SQL Editor, ejecuta:

```sql
select to_regprocedure('public.hoy_loft()') is not null or to_regprocedure('public.hoy_propiedad()') is not null as tiene_0002;
```

- Si da `false`, pega el contenido de `web/supabase/migrations/0002_hoy_propiedad.sql` y ejecútalo (**Run**).
- Las pruebas de reservas (`reservas_test.sql`) se corren después de la 0004 (paso 2, punto 3): usan el nombre nuevo de la función.

## 2. Aplicar la 0003 y probarla

1. Pega el contenido de `web/supabase/migrations/0003_gestion.sql` y ejecútalo.
   - El panel puede advertir que hay operaciones destructivas. Son los `drop policy/trigger if exists` que recrean los objetos de esta misma migración: confirma.
   - Si algo falla, no se aplica nada, porque la migración va en una transacción. Se puede volver a ejecutar sin pisar los textos ya editados.
2. Ejecuta `web/supabase/tests/gestion_test.sql`. El resultado debe ser `PRUEBAS_GESTION_OK`.
   - Usa usuarios y datos inventados y deshace todo al final.
   - Un aviso «S5, S6 o A13 omitida» no es un error: el proyecto bloquea el borrado por SQL en Storage, y el portal borra por la Storage API.
   - Si una prueba falla, copia el mensaje: empieza con su código (A, N, P, S, E o F).
3. Pega y ejecuta `web/supabase/migrations/0004_renombrar_hoy.sql` (renombra la función del día a `hoy_propiedad()`: la propiedad no es un loft). Después ejecuta `web/supabase/tests/reservas_test.sql`: el resultado debe ser `PRUEBAS_OK`.

## 3. Cerrar el registro público

Hazlo **antes** de crear la cuenta. Mientras el registro esté abierto, cualquiera que conozca tu correo puede registrarse primero con él y con su propia contraseña; le basta la URL del proyecto y la clave pública, que están en el sitio.

1. Ve a **Authentication → Sign In / Providers**. Desactiva **Allow new users to sign up** y guarda.
2. En la misma pantalla, confirma que **Allow anonymous sign-ins** sigue desactivado.
3. Revisa **Authentication → Users** y borra toda cuenta que no reconozcas: el registro estuvo abierto.

Una cuenta ajena con **otro** correo no puede hacer nada: sin una fila en `propietarios`, ve lo mismo que el público. La peligrosa es una cuenta creada por otra persona con **tu** correo, porque parece legítima. El paso 4 comprueba que no exista.

Según la documentación de Supabase, con el registro cerrado el panel sigue pudiendo crear cuentas (no se ha probado en este proyecto).

## 4. Crear la cuenta del propietario

La cuenta la creas **tú** en el panel. Claude no crea la cuenta ni escribe o ingresa contraseñas.

1. En el SQL Editor, cambia el correo y comprueba que todavía no haya una cuenta con él:

   ```sql
   select id, created_at, email_confirmed_at, last_sign_in_at
   from auth.users
   where lower(email) = lower('CORREO-DEL-PROPIETARIO');
   ```

   - Debe dar **0 filas**.
   - Si da alguna, bórrala en **Authentication → Users**, aunque creas que es tuya: con el registro abierto, cualquiera pudo crearla con tu correo y su propia contraseña. No hagas clic en correos de confirmación que no pediste.
2. Ve a **Authentication → Users → Add user → Create new user**.
3. Escribe **tu** correo y una contraseña larga y única; lo ideal es generarla con un gestor de contraseñas.
4. Marca **Auto Confirm User**, si aparece. Si no aparece, confirma la cuenta sólo con el correo que llegue justo después de crearla.
5. Si el panel responde que el correo ya existe, alguien se adelantó: vuelve al punto 1.
6. Ejecuta otra vez la consulta del punto 1. Ahora debe dar **una** fila, con `created_at` de hace unos minutos y `email_confirmed_at` con fecha. Su `id` es el UID de la cuenta (el panel también lo muestra como UID): anótalo para el paso 5.

No escribas la contraseña en archivos del repositorio ni en el chat.

## 5. Dar el rol de propietario

Dale el rol por el **UID** de la cuenta que acabas de crear, no sólo por el correo. En el SQL Editor, cambia el UID y el correo y ejecuta:

```sql
insert into public.propietarios (user_id, email)
select id, email from auth.users
where id = 'UID-DE-LA-CUENTA'
  and lower(email) = lower('CORREO-DEL-PROPIETARIO')
  and email_confirmed_at is not null
on conflict (user_id) do nothing
returning user_id, email;
```

- Debe devolver **una** fila. Si no devuelve ninguna, revisa que el UID y el correo sean los del paso 4 y que la cuenta esté confirmada (`email_confirmed_at` con fecha). Tampoco devuelve filas si esa cuenta ya tenía el rol.
- Para revisar: `select user_id, email, creado from public.propietarios;`. Debe aparecer sólo el UID del paso 4.
- Para quitar el rol: `delete from public.propietarios where user_id = 'UID';`. Hazlo también si borras una cuenta que lo tenía: la tabla no se limpia sola.

La tabla `propietarios` sólo se edita desde el panel: nadie, ni el propio propietario, puede darse el rol desde el sitio.

## 6. Qué puede hacer cada uno

| | Público (sin sesión) | Cuenta sin rol | Propietario |
|---|---|---|---|
| Ver textos (`contenido`) | sí | sí | sí, y editar, crear o borrar |
| Ver fotos (`fotos`) | sólo visibles | sólo visibles | todas, y editar, crear o borrar |
| Archivos del bucket `fotos` | descarga por URL pública | descarga por URL pública | subir, reemplazar, mover, borrar y listar |
| Reservas | sólo fechas ocupadas y enviar solicitud | lo mismo que el público | ver todo, borrar y cambiar **sólo** `estado` y `nota_interna` |
| Lista de propietarios | no | no | no (sólo el panel) |

El propietario no puede cambiar los datos del huésped ni las fechas de una reserva. Para otras fechas, rechaza la reserva y se envía una solicitud nueva.

## 7. Claves de contenido para el sitio

Para el sitio público, cada elemento editable lleva `data-contenido="clave"` y conserva en el HTML el texto actual, que queda como respaldo si la base no responde. El script lee `GET <SUPABASE_URL>/rest/v1/contenido?select=clave,valor,tipo`, con la cabecera `apikey` pública, y reemplaza el texto **siempre con `textContent`**, nunca con `innerHTML`.

| Clave | Tipo | Grupo | Dónde va hoy (`web/src/index.html`) |
|---|---|---|---|
| `hero.bajada` | parrafo | portada | bajada de la portada |
| `espacios.bajada` | parrafo | espacios | bajada de la sección Espacios |
| `espacio.living.titulo`, `espacio.living.texto` | texto, parrafo | espacios | tarjeta Living (`h3` y `p`) |
| `espacio.cocina.titulo`, `espacio.cocina.texto` | texto, parrafo | espacios | tarjeta Cocina |
| `espacio.dorm1.titulo`, `espacio.dorm1.texto` | texto, parrafo | espacios | tarjeta Dormitorio 1 |
| `espacio.dorm2.titulo`, `espacio.dorm2.texto` | texto, parrafo | espacios | tarjeta Dormitorio 2 |
| `espacio.banos.titulo`, `espacio.banos.texto` | texto, parrafo | espacios | tarjeta Dos baños |
| `espacio.balcon.titulo`, `espacio.balcon.texto` | texto, parrafo | espacios | tarjeta Balcón |
| `espacio.recibidor.titulo`, `espacio.recibidor.texto` | texto, parrafo | espacios | tarjeta Recibidor |
| `tarifa.noche` | precio | tarifas | hoy `data-precio="noche"` (58000, ejemplo) |
| `tarifa.limpieza` | precio | tarifas | hoy `data-precio="limpieza"` (15000, ejemplo) |
| `condiciones.llegada` | texto | condiciones | «desde 15:00» en la fila Llegada / salida |
| `condiciones.salida` | texto | condiciones | «hasta 11:00» en la misma fila |

Cómo se muestra cada tipo:

- **texto:** una línea.
- **parrafo:** puede traer saltos de línea. Se muestra con `textContent` y `white-space: pre-line`, o se parte en varios `<p>`, cada uno con `textContent`.
- **precio:** un entero en pesos escrito sólo con dígitos (de 0 a 10 000 000), que el sitio formatea en CLP. El sitio aplica las tarifas editadas a los precios publicados y al total de la reserva (`contenido-publico.js`, `tarifas()`; `reserva-logica.js`, `fijarTarifas`), así que coinciden. La noche debe ser mayor que 0: con 0, el sitio usa el valor por defecto, y por eso el portal no la acepta.

Las fotos se leen con `GET <SUPABASE_URL>/rest/v1/fotos?select=espacio,ruta,alt,orden&order=espacio.asc,orden.asc`. El público recibe sólo las visibles.

- **URL de cada imagen:** `<SUPABASE_URL>/storage/v1/object/public/fotos/<ruta>`.
- **Espacios:** `living`, `cocina`, `dorm1`, `dorm2`, `banos`, `balcon` y `recibidor`, los mismos que ofrece el portal (`ESPACIOS` en `web/src/admin/js/logica-fotos.js`). Un espacio sin filas sigue mostrando las imágenes de `web/src/img/`. Para sumar otro, por ejemplo una foto de portada, hay que agregarlo a `ESPACIOS` y poner el `data-fotos` correspondiente en el HTML.
- **Nombre de archivo:** una carpeta opcional y un nombre en minúsculas, con extensión `jpg`, `jpeg`, `png` o `webp`. Por ejemplo, `living/20260926-a1b2c3d4.webp`, que es el formato que genera el portal. Máximo 5 MB, y nada de SVG. Un nombre que no cumple la regla se rechaza al subir.

## 8. Cuidados

- **Ocultar no es borrar:** con `visible = false`, la foto sale del sitio, pero el archivo sigue accesible para quien tenga la URL. Para retirarlo, bórralo desde el portal o desde **Storage**.
- **Borrar archivos:** hazlo por el portal o el panel, nunca con `delete` en SQL. Si no, el archivo queda huérfano en el almacenamiento.
- **Nota interna:** sólo el propietario la ve. Aun así, no guardes en ella datos del huésped que no hagan falta.
- **Clave del sitio:** el sitio usa únicamente la clave pública. La clave de servicio (`service_role` o `sb_secret_…`) nunca va en el sitio ni en el repositorio: `build.py` la rechaza.
