# Portal de gestión: puesta en marcha en Supabase

Con el portal, el propietario inicia sesión y puede editar los textos del sitio, subir u ocultar fotos y manejar las reservas: confirmarlas, rechazarlas, anotarlas o borrarlas. Esta guía prepara la base de datos. La interfaz del portal va aparte.

Todos los pasos se hacen en el panel de Supabase del proyecto: **SQL Editor** para el SQL y **Authentication** para las cuentas. Claude no aplica migraciones, no crea cuentas y no maneja contraseñas.

**Estado al 2026-09-26**, según un sondeo de sólo lectura con la clave pública:

- La 0003 no está aplicada: `contenido` y `es_propietario` no existen.
- El registro público está **abierto** (`disable_signup: false`). La confirmación por correo está activa y las sesiones anónimas, desactivadas.
- `hoy_loft()` no aparece para el rol público. O falta la 0002, o ese rol no tiene permiso para ejecutarla. El paso 1 lo aclara.

## 1. Revisar la 0002

En el SQL Editor, ejecuta:

```sql
select to_regprocedure('public.hoy_loft()') is not null as tiene_0002;
```

- Si da `false`, pega el contenido de `web/supabase/migrations/0002_hoy_propiedad.sql` y ejecútalo (**Run**).
- Después, ejecuta `web/supabase/tests/reservas_test.sql`. El resultado debe ser `PRUEBAS_OK`.

## 2. Aplicar la 0003 y probarla

1. Pega el contenido de `web/supabase/migrations/0003_gestion.sql` y ejecútalo.
   - El panel puede advertir que hay operaciones destructivas. Son los `drop policy/trigger if exists` que recrean los objetos de esta misma migración: confirma.
   - Si algo falla, no se aplica nada, porque la migración va en una transacción. Se puede volver a ejecutar sin pisar los textos ya editados.
2. Ejecuta `web/supabase/tests/gestion_test.sql`. El resultado debe ser `PRUEBAS_GESTION_OK`.
   - Usa usuarios y datos inventados y deshace todo al final.
   - Un aviso «S5/S6 omitida» no es un error: el proyecto bloquea el borrado por SQL en Storage, y el portal borra por la Storage API.
   - Si una prueba falla, copia el mensaje: empieza con su código (A, N, P, S, E o F).

## 3. Crear la cuenta del propietario

1. Ve a **Authentication → Users → Add user → Create new user**.
2. Escribe **tu** correo y una contraseña larga y única; lo ideal es generarla con un gestor de contraseñas.
3. Marca **Auto Confirm User**, si aparece. El proyecto exige confirmar el correo, así que sin esa marca hay que confirmarlo desde el mensaje que llega.

No escribas la contraseña en archivos del repositorio ni en el chat.

## 4. Cerrar el registro público

1. Ve a **Authentication → Sign In / Providers**. Desactiva **Allow new users to sign up** y guarda.
2. En la misma pantalla, confirma que **Allow anonymous sign-ins** sigue desactivado.
3. Revisa **Authentication → Users** y borra toda cuenta que no reconozcas: el registro estuvo abierto.

Aunque quedara una cuenta ajena, no podría hacer nada: sin una fila en `propietarios`, ve lo mismo que el público. Cerrar el registro evita cuentas basura.

## 5. Dar el rol de propietario

En el SQL Editor, cambia el correo y ejecuta:

```sql
insert into public.propietarios (user_id, email)
select id, email from auth.users where lower(email) = lower('CORREO-DEL-PROPIETARIO')
on conflict (user_id) do nothing
returning user_id, email;
```

- Debe devolver **una** fila. Si no devuelve ninguna, el correo no coincide con el del paso 3.
- Para revisar: `select user_id, email, creado from public.propietarios;`
- Para quitar el rol: `delete from public.propietarios where email = 'CORREO';`

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
- **precio:** un entero en pesos escrito sólo con dígitos (de 0 a 10 000 000), que el sitio formatea en CLP. Si la tarifa se vuelve editable, el cálculo del total en `reserva-logica.js` (`TARIFA`) también debe leerla. Si no, la tabla y el total no coincidirán.

Las fotos se leen con `GET <SUPABASE_URL>/rest/v1/fotos?select=espacio,ruta,alt,orden&order=espacio.asc,orden.asc`. El público recibe sólo las visibles.

- **URL de cada imagen:** `<SUPABASE_URL>/storage/v1/object/public/fotos/<ruta>`.
- **Espacios sugeridos:** `portada`, `living`, `cocina`, `dorm1`, `dorm2`, `banos`, `balcon` y `recibidor`. Un espacio sin filas sigue mostrando las imágenes de `web/src/img/`.
- **Nombre de archivo:** una carpeta opcional y un nombre en minúsculas, con extensión `jpg`, `jpeg`, `png` o `webp`. Por ejemplo, `living/2026-09-26-a1b2c3.webp`. Máximo 5 MB, y nada de SVG. Un nombre que no cumple la regla se rechaza al subir.

## 8. Cuidados

- **Ocultar no es borrar:** con `visible = false`, la foto sale del sitio, pero el archivo sigue accesible para quien tenga la URL. Para retirarlo, bórralo desde el portal o desde **Storage**.
- **Borrar archivos:** hazlo por el portal o el panel, nunca con `delete` en SQL. Si no, el archivo queda huérfano en el almacenamiento.
- **Nota interna:** sólo el propietario la ve. Aun así, no guardes en ella datos del huésped que no hagan falta.
- **Clave del sitio:** el sitio usa únicamente la clave pública. La clave de servicio (`service_role` o `sb_secret_…`) nunca va en el sitio ni en el repositorio: `build.py` la rechaza.
