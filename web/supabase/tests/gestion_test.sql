-- Pruebas del portal de gestión (0003_gestion.sql). Se ejecutan en el SQL Editor de Supabase o con psql
-- (-v ON_ERROR_STOP=1), como postgres, después de aplicar la 0003, dentro de una transacción que se deshace: no dejan
-- datos. Si todo pasa, el resultado es «PRUEBAS_GESTION_OK»; si una falla, se aborta con el código de la prueba
-- (E = estructura, A = anon, N = autenticado sin rol de propietario, P = propietario, S = storage, F = final).
--
-- Los roles se simulan como lo hacen PostgREST y la Storage API: «set local role» más los claims del JWT en
-- request.jwt.claims (de ahí lee auth.uid()). Los usuarios son identificadores inventados: no se crean cuentas en
-- auth.users; la 0003 no tiene clave foránea hacia esa tabla.
begin;

-- 0. Preparación (como postgres) -----------------------------------------------------------------------------------
-- Reservas en estado «rechazada»: la exclusión de solapes sólo mira pendientes y confirmadas, así estas filas no
-- chocan con reservas reales del calendario. Los códigos llevan letras que no son hexadecimales (P, R, U, G), así
-- que no pueden coincidir con un código real.
do $$
begin
  insert into public.propietarios (user_id, email)
  values ('a0000000-0000-4000-8000-00000000000a', 'propietario.prueba@ejemplo.cl');

  insert into public.reservas (id, codigo, entrada, salida, huespedes, nombre, email, estado) values
    ('c0000000-0000-4000-8000-000000000001', 'PRUEBAG1', current_date + 300, current_date + 303, 2,
     'Gestion Prueba', 'gestion@ejemplo.cl', 'rechazada'),
    ('c0000000-0000-4000-8000-000000000002', 'PRUEBAG2', current_date + 310, current_date + 312, 1,
     'Borrar Prueba', 'borrar@ejemplo.cl', 'rechazada');

  insert into public.fotos (id, espacio, ruta, alt, orden, visible) values
    ('d0000000-0000-4000-8000-000000000001', 'living', 'prueba-gestion/visible.webp', 'Foto visible de prueba', 1, true),
    ('d0000000-0000-4000-8000-000000000002', 'living', 'prueba-gestion/oculta.webp', 'Foto oculta de prueba', 2, false);

  -- Otro bucket, para comprobar que las políticas sólo abren «fotos».
  insert into storage.buckets (id, name, public) values ('prueba-gestion-otro', 'prueba-gestion-otro', false);

  -- Supabase bloquea el DELETE directo en storage.objects con un trigger (storage.protect_delete) salvo que esta
  -- variable valga 'true'; la Storage API la activa igual en sus borrados. Sólo vale dentro de esta transacción.
  perform set_config('storage.allow_delete_query', 'true', true);
end $$;

-- 1. Estructura y privilegios (como postgres) ---------------------------------------------------------------------
do $$
declare
  claves text[] := array[
    'hero.bajada', 'espacios.bajada',
    'espacio.living.titulo', 'espacio.living.texto', 'espacio.cocina.titulo', 'espacio.cocina.texto',
    'espacio.dorm1.titulo', 'espacio.dorm1.texto', 'espacio.dorm2.titulo', 'espacio.dorm2.texto',
    'espacio.banos.titulo', 'espacio.banos.texto', 'espacio.balcon.titulo', 'espacio.balcon.texto',
    'espacio.recibidor.titulo', 'espacio.recibidor.texto',
    'tarifa.noche', 'tarifa.limpieza', 'condiciones.llegada', 'condiciones.salida'];
  b record;
begin
  assert (select bool_and(relrowsecurity) from pg_class
          where oid in ('public.propietarios'::regclass, 'public.contenido'::regclass,
                        'public.fotos'::regclass, 'public.reservas'::regclass)), 'E1: RLS inactiva en alguna tabla';

  assert not has_table_privilege('anon', 'public.reservas', 'select'), 'E2: anon puede leer reservas';
  assert not has_table_privilege('anon', 'public.propietarios', 'select'), 'E2: anon puede leer propietarios';
  assert not has_table_privilege('authenticated', 'public.propietarios', 'select,insert,update,delete'),
         'E2: authenticated tiene privilegios sobre propietarios';
  assert not has_table_privilege('authenticated', 'public.reservas', 'insert'), 'E2: authenticated puede insertar reservas';
  assert not has_table_privilege('authenticated', 'public.reservas', 'update'), 'E2: update de tabla completa en reservas';
  assert has_column_privilege('authenticated', 'public.reservas', 'estado', 'update'), 'E2: falta update(estado)';
  assert has_column_privilege('authenticated', 'public.reservas', 'nota_interna', 'update'), 'E2: falta update(nota_interna)';
  assert not has_column_privilege('authenticated', 'public.reservas', 'email', 'update'), 'E2: update(email) concedido';
  assert not has_column_privilege('authenticated', 'public.reservas', 'entrada', 'update'), 'E2: update(entrada) concedido';
  assert not has_column_privilege('authenticated', 'public.reservas', 'actualizada', 'update'), 'E2: update(actualizada) concedido';
  assert has_table_privilege('anon', 'public.contenido', 'select')
     and not has_table_privilege('anon', 'public.contenido', 'insert')
     and not has_table_privilege('anon', 'public.fotos', 'insert'), 'E2: privilegios de anon en contenido o fotos';

  assert has_function_privilege('anon', 'public.es_propietario()', 'execute'), 'E3: anon no ejecuta es_propietario';
  assert (select prosecdef from pg_proc where oid = 'public.es_propietario()'::regprocedure),
         'E3: es_propietario no es SECURITY DEFINER';
  -- Una función SECURITY DEFINER sin search_path fijo resolvería nombres con el search_path de quien la llama.
  -- proconfig null (sin «set») hace que la comparación dé null y el assert falle.
  assert (select proconfig from pg_proc where oid = 'public.es_propietario()'::regprocedure)
         @> array['search_path=public'], 'E3: es_propietario no fija search_path';
  assert not has_function_privilege('anon', 'public.tg_reservas_actualizada()', 'execute')
     and not has_function_privilege('authenticated', 'public.tg_contenido_actualizado()', 'execute'),
         'E3: funciones de trigger ejecutables por clientes';

  assert (select count(*) from public.contenido where clave = any (claves)) = array_length(claves, 1),
         'E4: falta alguna clave de la semilla';
  assert (select count(*) from public.contenido where clave in ('tarifa.noche', 'tarifa.limpieza') and tipo = 'precio') = 2,
         'E4: las tarifas no son de tipo precio';

  select public, file_size_limit, allowed_mime_types into b from storage.buckets where id = 'fotos';
  assert b.public and b.file_size_limit = 5242880
     and b.allowed_mime_types @> array['image/jpeg', 'image/png', 'image/webp']
     and array_length(b.allowed_mime_types, 1) = 3, 'E5: configuración del bucket fotos';
  assert (select count(*) from pg_policies where schemaname = 'storage' and tablename = 'objects'
          and policyname like 'fotos_propietario_%') = 4, 'E5: faltan políticas de storage.objects';
end $$;

-- 2. Público (anon) ------------------------------------------------------------------------------------------------
set local role anon;
do $$
declare
  n int;
  err text;
begin
  perform set_config('request.jwt.claims', '{"role":"anon"}', true);

  assert not public.es_propietario(), 'A1: anon es propietario';

  begin perform 1 from public.reservas limit 1; raise exception 'A2: anon leyó reservas';
  exception when insufficient_privilege then null; end;
  begin perform 1 from public.propietarios limit 1; raise exception 'A3: anon leyó propietarios';
  exception when insufficient_privilege then null; end;
  begin insert into public.propietarios (user_id, email) values ('e0000000-0000-4000-8000-00000000000e', 'x@ejemplo.cl');
        raise exception 'A3: anon se agregó como propietario';
  exception when insufficient_privilege then null; end;
  begin update public.reservas set estado = 'cancelada' where codigo = 'PRUEBAG1';
        raise exception 'A4: anon actualizó reservas';
  exception when insufficient_privilege then null; end;

  select count(*) into n from public.contenido where clave in ('hero.bajada', 'tarifa.noche');
  assert n = 2, 'A5: anon no lee contenido';
  select count(*) into n from public.fotos where ruta like 'prueba-gestion/%';
  assert n = 1, 'A6: anon debe ver sólo la foto visible, vio ' || n;
  assert not exists (select 1 from public.fotos where ruta = 'prueba-gestion/oculta.webp'), 'A6: anon vio la foto oculta';

  begin insert into public.contenido (clave, valor, tipo, etiqueta, grupo) values ('prueba.anon', 'x', 'texto', 'x', 'prueba');
        raise exception 'A7: anon insertó contenido';
  exception when insufficient_privilege then null; end;
  begin update public.contenido set valor = 'pirateado' where clave = 'hero.bajada';
        raise exception 'A7: anon actualizó contenido';
  exception when insufficient_privilege then null; end;
  begin delete from public.contenido where clave = 'hero.bajada';
        raise exception 'A7: anon borró contenido';
  exception when insufficient_privilege then null; end;
  begin insert into public.fotos (espacio, ruta, alt) values ('living', 'prueba-gestion/anon.webp', 'x');
        raise exception 'A8: anon insertó fotos';
  exception when insufficient_privilege then null; end;
  begin update public.fotos set visible = true where ruta like 'prueba-gestion/%';
        raise exception 'A8: anon actualizó fotos';
  exception when insufficient_privilege then null; end;

  -- storage: anon no sube (RLS de storage.objects). Que no liste, renombre ni borre se prueba en la sección 7,
  -- cuando el bucket ya tiene un archivo de prueba: aquí puede estar vacío y la prueba no podría fallar.
  begin insert into storage.objects (bucket_id, name) values ('fotos', 'prueba-gestion/anon.webp');
        raise exception 'A9: anon subió un archivo';
  exception when insufficient_privilege then null; end;

  -- lo de 0001/0002 sigue funcionando con las columnas nuevas (la fecha puede chocar con una reserva real)
  perform * from public.disponibilidad(current_date, current_date + 30);
  begin
    perform public.solicitar_reserva(current_date + 355, current_date + 357, 1, 'Anon Gestion', 'anon.gestion@ejemplo.cl');
  exception when others then
    get stacked diagnostics err = message_text;
    assert err = 'fechas_ocupadas', 'A10: solicitar_reserva falló: ' || err;
  end;
end $$;
reset role;

-- 3. Autenticado que NO es propietario ----------------------------------------------------------------------------
set local role authenticated;
do $$
declare
  n int;
begin
  perform set_config('request.jwt.claims',
    '{"sub":"b0000000-0000-4000-8000-00000000000b","role":"authenticated"}', true);

  assert not public.es_propietario(), 'N1: un usuario cualquiera es propietario';

  select count(*) into n from public.reservas;
  assert n = 0, 'N2: un usuario cualquiera ve ' || n || ' reservas';
  update public.reservas set estado = 'cancelada', nota_interna = 'intruso' where codigo = 'PRUEBAG1';
  get diagnostics n = row_count;
  assert n = 0, 'N3: un usuario cualquiera actualizó una reserva';
  delete from public.reservas where codigo = 'PRUEBAG1';
  get diagnostics n = row_count;
  assert n = 0, 'N3: un usuario cualquiera borró una reserva';
  begin update public.reservas set email = 'intruso@ejemplo.cl' where codigo = 'PRUEBAG1';
        raise exception 'N4: update de email permitido';
  exception when insufficient_privilege then null; end;

  begin perform 1 from public.propietarios limit 1; raise exception 'N5: leyó propietarios';
  exception when insufficient_privilege then null; end;
  begin insert into public.propietarios (user_id, email)
        values ('b0000000-0000-4000-8000-00000000000b', 'intruso@ejemplo.cl');
        raise exception 'N5: se dio a sí mismo el rol de propietario';
  exception when insufficient_privilege then null; end;

  select count(*) into n from public.contenido where clave = 'hero.bajada';
  assert n = 1, 'N6: no lee contenido';
  begin insert into public.contenido (clave, valor, tipo, etiqueta, grupo) values ('prueba.intruso', 'x', 'texto', 'x', 'prueba');
        raise exception 'N7: insertó contenido';
  exception when insufficient_privilege then null; end;               -- RLS: «new row violates row-level security»
  update public.contenido set valor = 'pirateado' where clave = 'hero.bajada';
  get diagnostics n = row_count;
  assert n = 0, 'N7: actualizó contenido';
  delete from public.contenido where clave = 'hero.bajada';
  get diagnostics n = row_count;
  assert n = 0, 'N7: borró contenido';

  select count(*) into n from public.fotos where ruta like 'prueba-gestion/%';
  assert n = 1, 'N8: debe ver sólo la foto visible, vio ' || n;
  begin insert into public.fotos (espacio, ruta, alt) values ('living', 'prueba-gestion/intruso.webp', 'x');
        raise exception 'N8: insertó una foto';
  exception when insufficient_privilege then null; end;
  update public.fotos set alt = 'pirateado' where ruta like 'prueba-gestion/%';
  get diagnostics n = row_count;
  assert n = 0, 'N8: actualizó fotos';
  delete from public.fotos where ruta like 'prueba-gestion/%';
  get diagnostics n = row_count;
  assert n = 0, 'N8: borró fotos';

  begin insert into storage.objects (bucket_id, name) values ('fotos', 'prueba-gestion/intruso.webp');
        raise exception 'N9: subió un archivo al bucket fotos';
  exception when insufficient_privilege then null; end;
end $$;
reset role;

-- 4. Propietario ---------------------------------------------------------------------------------------------------
set local role authenticated;
do $$
declare
  n int;
  v text;
  r record;
begin
  perform set_config('request.jwt.claims',
    '{"sub":"a0000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);

  assert public.es_propietario(), 'P1: el propietario no es reconocido';

  -- reservas: ve los datos, cambia estado y nota interna; el trigger marca la fecha
  select count(*) into n from public.reservas where codigo in ('PRUEBAG1', 'PRUEBAG2');
  assert n = 2, 'P2: el propietario no ve las reservas';
  assert (select email from public.reservas where codigo = 'PRUEBAG1') = 'gestion@ejemplo.cl', 'P2: no lee el correo';
  update public.reservas set estado = 'cancelada', nota_interna = 'Pidió cambiar fechas' where codigo = 'PRUEBAG1';
  get diagnostics n = row_count;
  assert n = 1, 'P3: no actualizó la reserva';
  select estado, nota_interna, actualizada into r from public.reservas where codigo = 'PRUEBAG1';
  assert r.estado = 'cancelada' and r.nota_interna = 'Pidió cambiar fechas', 'P3: valores no guardados';
  assert r.actualizada = now(), 'P3: el trigger no marcó actualizada';

  -- no puede tocar datos del huésped, fechas ni la marca de tiempo (privilegio por columnas)
  begin update public.reservas set email = 'otro@ejemplo.cl' where codigo = 'PRUEBAG1';
        raise exception 'P4: cambió el correo';
  exception when insufficient_privilege then null; end;
  begin update public.reservas set nombre = 'Otro Nombre' where codigo = 'PRUEBAG1';
        raise exception 'P4: cambió el nombre';
  exception when insufficient_privilege then null; end;
  begin update public.reservas set entrada = entrada + 1 where codigo = 'PRUEBAG1';
        raise exception 'P4: cambió la entrada';
  exception when insufficient_privilege then null; end;
  begin update public.reservas set salida = salida + 1 where codigo = 'PRUEBAG1';
        raise exception 'P4: cambió la salida';
  exception when insufficient_privilege then null; end;
  begin update public.reservas set actualizada = '2000-01-01' where codigo = 'PRUEBAG1';
        raise exception 'P4: falseó actualizada';
  exception when insufficient_privilege then null; end;
  begin insert into public.reservas (entrada, salida, huespedes, nombre, email)
        values (current_date + 320, current_date + 322, 1, 'Directa', 'directa@ejemplo.cl');
        raise exception 'P4: insertó una reserva sin pasar por solicitar_reserva';
  exception when insufficient_privilege then null; end;

  -- los check siguen valiendo para el propietario
  begin update public.reservas set nota_interna = repeat('x', 2001) where codigo = 'PRUEBAG1';
        raise exception 'P5: nota de 2001 caracteres aceptada';
  exception when check_violation then null; end;
  begin update public.reservas set estado = 'borrada' where codigo = 'PRUEBAG1';
        raise exception 'P5: estado inválido aceptado';
  exception when check_violation then null; end;

  delete from public.reservas where codigo = 'PRUEBAG2';
  get diagnostics n = row_count;
  assert n = 1, 'P6: el propietario no pudo borrar una reserva';

  -- tampoco lee ni amplía la lista de propietarios (sólo desde el panel)
  begin perform 1 from public.propietarios limit 1; raise exception 'P7: el propietario leyó propietarios';
  exception when insufficient_privilege then null; end;
  begin insert into public.propietarios (user_id, email) values ('f0000000-0000-4000-8000-00000000000f', 'amigo@ejemplo.cl');
        raise exception 'P7: el propietario agregó otro propietario';
  exception when insufficient_privilege then null; end;

  -- contenido: edita, crea y borra
  update public.contenido set valor = 'Texto editado en la prueba.' where clave = 'hero.bajada';
  get diagnostics n = row_count;
  assert n = 1, 'P8: no editó hero.bajada';
  assert (select actualizado from public.contenido where clave = 'hero.bajada') = now(), 'P8: no marcó actualizado';
  insert into public.contenido (clave, valor, tipo, etiqueta, grupo, orden)
  values ('prueba.nueva', 'Nuevo', 'texto', 'Prueba', 'prueba', 999);
  delete from public.contenido where clave = 'prueba.nueva';
  get diagnostics n = row_count;
  assert n = 1, 'P8: no borró contenido';

  -- precio: entero de 0 a 10 000 000 sólo con dígitos
  foreach v in array array['58.000', '58,000', '-1', '10000001', '99999999', '100000000', 'abc', '', ' 58000',
                           '58000 ', '058000', '1e5', '5.5', '+5']
  loop
    begin
      update public.contenido set valor = v where clave = 'tarifa.noche';
      raise exception 'P9: precio inválido aceptado: «%»', v;
    exception when check_violation then null;
    end;
  end loop;
  foreach v in array array['0', '10000000', '65000'] loop
    update public.contenido set valor = v where clave = 'tarifa.noche';
    get diagnostics n = row_count;
    assert n = 1, 'P9: precio válido rechazado: ' || v;
  end loop;
  begin update public.contenido set tipo = 'precio' where clave = 'hero.bajada';
        raise exception 'P9: un texto pasó a precio';
  exception when check_violation then null; end;
  begin insert into public.contenido (clave, valor, tipo, etiqueta, grupo) values ('prueba.tipo', 'x', 'html', 'x', 'prueba');
        raise exception 'P9: tipo html aceptado';
  exception when check_violation then null; end;
  begin update public.contenido set valor = repeat('x', 4001) where clave = 'hero.bajada';
        raise exception 'P9: valor de 4001 caracteres aceptado';
  exception when check_violation then null; end;
  begin update public.contenido set valor = '   ' where clave = 'hero.bajada';
        raise exception 'P9: valor en blanco aceptado';
  exception when check_violation then null; end;

  -- clave: minúsculas, dígitos, «_ . -», de 2 a 60 caracteres, empieza con letra o dígito
  foreach v in array array['Hero.bajada', '.oculta', '-guion', 'a', 'con espacio', 'acento.ñ', 'barra/clave',
                           'comilla"x', 'menor<x', repeat('a', 61)]
  loop
    begin
      insert into public.contenido (clave, valor, tipo, etiqueta, grupo) values (v, 'x', 'texto', 'x', 'prueba');
      raise exception 'P10: clave inválida aceptada: «%»', v;
    exception when check_violation then null;
    end;
  end loop;
  insert into public.contenido (clave, valor, tipo, etiqueta, grupo) values (repeat('a', 60), 'x', 'texto', 'x', 'prueba');
  delete from public.contenido where clave = repeat('a', 60);

  -- fotos: ve también las ocultas, crea, edita y borra
  select count(*) into n from public.fotos where ruta like 'prueba-gestion/%';
  assert n = 2, 'P11: el propietario debe ver las 2 fotos de prueba, vio ' || n;
  insert into public.fotos (espacio, ruta, alt, orden) values ('cocina', 'prueba-gestion/nueva.webp', 'Cocina de prueba', 5);
  update public.fotos set visible = false, alt = 'Cocina de prueba, oculta' where ruta = 'prueba-gestion/nueva.webp';
  get diagnostics n = row_count;
  assert n = 1, 'P11: no editó la foto';
  delete from public.fotos where ruta = 'prueba-gestion/nueva.webp';
  get diagnostics n = row_count;
  assert n = 1, 'P11: no borró la foto';

  foreach v in array array['../secreto.jpg', '/absoluta.jpg', 'prueba/Mayus.JPG', 'prueba/foto.svg', 'a/b/c.jpg',
                           'sin-extension', 'javascript:alert(1).png', 'con espacio.jpg', 'prueba/.oculta.png']
  loop
    begin
      insert into public.fotos (espacio, ruta, alt) values ('living', v, 'x');
      raise exception 'P12: ruta inválida aceptada: «%»', v;
    exception when check_violation then null;
    end;
  end loop;
  begin insert into public.fotos (espacio, ruta, alt) values ('living', 'prueba-gestion/alt.webp', '  ');
        raise exception 'P12: alt en blanco aceptado';
  exception when check_violation then null; end;
  begin insert into public.fotos (espacio, ruta, alt) values ('living', 'prueba-gestion/alt.webp', repeat('x', 201));
        raise exception 'P12: alt de 201 caracteres aceptado';
  exception when check_violation then null; end;
  begin insert into public.fotos (espacio, ruta, alt) values ('Living', 'prueba-gestion/esp.webp', 'x');
        raise exception 'P12: espacio con mayúscula aceptado';
  exception when check_violation then null; end;
  begin insert into public.fotos (espacio, ruta, alt) values ('living', 'prueba-gestion/visible.webp', 'Duplicada');
        raise exception 'P12: ruta duplicada aceptada';
  exception when unique_violation then null; end;
end $$;
reset role;

-- 5. Storage: el propietario sube, lista y renombra -------------------------------------------------------------
-- Es un insert directo en storage.objects, como el que hace la Storage API con el rol del usuario; no sube bytes.
set local role authenticated;
do $$
declare
  n int;
begin
  perform set_config('request.jwt.claims',
    '{"sub":"a0000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);

  begin
    insert into storage.objects (bucket_id, name) values ('fotos', 'prueba-gestion/propietario.webp');
  exception when others then
    raise exception 'S1: el propietario no pudo registrar un archivo en fotos: % (SQLSTATE %)', sqlerrm, sqlstate;
  end;
  begin insert into storage.objects (bucket_id, name) values ('prueba-gestion-otro', 'prueba-gestion/otro.webp');
        raise exception 'S1: el propietario subió a otro bucket';
  exception when insufficient_privilege then null; end;
  begin insert into storage.objects (bucket_id, name) values ('fotos', 'prueba-gestion/Mayus.JPG');
        raise exception 'S1: nombre de archivo fuera de formato aceptado';
  exception when insufficient_privilege then null; end;
  select count(*) into n from storage.objects where bucket_id = 'fotos' and name = 'prueba-gestion/propietario.webp';
  assert n = 1, 'S2: el propietario no ve su archivo';
  update storage.objects set name = 'prueba-gestion/renombrada.webp'
  where bucket_id = 'fotos' and name = 'prueba-gestion/propietario.webp';
  get diagnostics n = row_count;
  assert n = 1, 'S3: el propietario no pudo renombrar su archivo';
end $$;
reset role;

-- 6. Storage: otro usuario no toca el archivo del propietario -----------------------------------------------------
set local role authenticated;
do $$
declare
  n int;
  err text;
begin
  perform set_config('request.jwt.claims',
    '{"sub":"b0000000-0000-4000-8000-00000000000b","role":"authenticated"}', true);

  select count(*) into n from storage.objects where bucket_id = 'fotos';
  assert n = 0, 'S4: un usuario cualquiera lista el bucket fotos';
  update storage.objects set name = 'prueba-gestion/robada.webp'
  where bucket_id = 'fotos' and name = 'prueba-gestion/renombrada.webp';
  get diagnostics n = row_count;
  assert n = 0, 'S4: un usuario cualquiera renombró un archivo';
  begin
    delete from storage.objects where bucket_id = 'fotos' and name = 'prueba-gestion/renombrada.webp';
    get diagnostics n = row_count;
    assert n = 0, 'S5: un usuario cualquiera borró un archivo';
  exception when insufficient_privilege then
    get stacked diagnostics err = message_text;
    if err not like 'Direct deletion%' then raise exception 'S5: %', err; end if;
    raise notice 'S5 omitida: el proyecto bloquea el DELETE directo en storage.objects (%)', err;
  end;
end $$;
reset role;

-- 7. Storage: el público (anon) no lista, renombra ni borra el archivo del propietario ----------------------------
-- Va aquí porque ya existe «prueba-gestion/renombrada.webp» (S1 y S3), así la prueba de listado sí puede fallar; la
-- sección 8 comprueba que el archivo siguiera ahí. Si anon no tiene privilegio de tabla, tampoco lista ni escribe.
set local role anon;
do $$
declare
  n int;
  err text;
begin
  perform set_config('request.jwt.claims', '{"role":"anon"}', true);

  begin
    select count(*) into n from storage.objects where bucket_id = 'fotos';
    assert n = 0, 'A11: anon lista el bucket fotos, vio ' || n || ' archivos';
  exception when insufficient_privilege then null;
  end;
  begin
    update storage.objects set name = 'prueba-gestion/anon.webp'
    where bucket_id = 'fotos' and name = 'prueba-gestion/renombrada.webp';
    get diagnostics n = row_count;
    assert n = 0, 'A12: anon renombró el archivo del propietario';
  exception when insufficient_privilege then null;
  end;
  begin
    delete from storage.objects where bucket_id = 'fotos' and name = 'prueba-gestion/renombrada.webp';
    get diagnostics n = row_count;
    assert n = 0, 'A13: anon borró el archivo del propietario';
  exception when insufficient_privilege then
    get stacked diagnostics err = message_text;
    if err like 'Direct deletion%' then
      raise notice 'A13 omitida: el proyecto bloquea el DELETE directo en storage.objects (%)', err;
    end if;
  end;
end $$;
reset role;

-- 8. Storage: el propietario borra su archivo ---------------------------------------------------------------------
set local role authenticated;
do $$
declare
  n int;
  err text;
begin
  perform set_config('request.jwt.claims',
    '{"sub":"a0000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);

  -- el archivo siguió en su lugar durante S4, S5 y A11 a A13: esas pruebas corrieron contra un archivo real
  select count(*) into n from storage.objects where bucket_id = 'fotos' and name = 'prueba-gestion/renombrada.webp';
  assert n = 1, 'S6: el archivo de prueba desapareció antes de que el propietario lo borrara';

  begin
    delete from storage.objects where bucket_id = 'fotos' and name = 'prueba-gestion/renombrada.webp';
    get diagnostics n = row_count;
    assert n = 1, 'S6: el propietario no pudo borrar su archivo';
  exception when insufficient_privilege then
    get stacked diagnostics err = message_text;
    if err not like 'Direct deletion%' then raise exception 'S6: %', err; end if;
    raise notice 'S6 omitida: el proyecto bloquea el DELETE directo en storage.objects (%)', err;
  end;
end $$;
reset role;

-- 9. Verificación final (como postgres): nada de lo intentado por otros quedó escrito --------------------------
do $$
begin
  assert (select valor from public.contenido where clave = 'hero.bajada') = 'Texto editado en la prueba.',
         'F1: hero.bajada no tiene el valor del propietario';
  assert (select email from public.reservas where codigo = 'PRUEBAG1') = 'gestion@ejemplo.cl', 'F2: el correo cambió';
  assert (select nota_interna from public.reservas where codigo = 'PRUEBAG1') = 'Pidió cambiar fechas', 'F2: nota alterada';
  assert not exists (select 1 from public.propietarios
                     where email in ('x@ejemplo.cl', 'intruso@ejemplo.cl', 'amigo@ejemplo.cl')), 'F3: propietario intruso';
  assert (select count(*) from public.fotos where ruta like 'prueba-gestion/%') = 2, 'F4: fotos de prueba alteradas';
end $$;

select 'PRUEBAS_GESTION_OK' as resultado;
rollback;
