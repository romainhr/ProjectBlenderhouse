-- Pruebas de las traducciones de public.contenido (0005_contenido_idiomas.sql). Se ejecutan en el SQL Editor de
-- Supabase o con psql (-v ON_ERROR_STOP=1), como postgres, después de aplicar la 0003 y la 0005, dentro de una
-- transacción que se deshace: no dejan datos. Si todo pasa, el resultado es «PRUEBAS_IDIOMAS_OK»; si una falla, se
-- aborta con el código de la prueba (E = estructura, A = anon, N = autenticado sin rol de propietario,
-- P = propietario, F = final).
--
-- Los roles se simulan igual que en gestion_test.sql, como lo hace PostgREST: «set local role» más los claims del JWT
-- en request.jwt.claims (de ahí lee auth.uid()). Los usuarios son identificadores inventados: no se crean cuentas en
-- auth.users. Las filas de prueba usan claves propias (prueba.idiomas.*): no dependen de la semilla ni de lo que el
-- propietario haya editado en el proyecto real.
begin;

-- 0. Preparación (como postgres) -----------------------------------------------------------------------------------
do $$
begin
  insert into public.propietarios (user_id, email)
  values ('a1000000-0000-4000-8000-00000000001a', 'propietario.idiomas@ejemplo.cl');

  insert into public.contenido (clave, valor, valor_en, valor_fr, tipo, etiqueta, grupo, orden) values
    ('prueba.idiomas.texto', 'Texto de prueba', 'Test text', 'Texte d''essai', 'parrafo', 'Prueba de idiomas', 'prueba', 9000),
    ('prueba.idiomas.solo-es', 'Sólo en español', null, null, 'texto', 'Prueba sin traducción', 'prueba', 9001),
    ('prueba.idiomas.precio', '58000', null, null, 'precio', 'Precio de prueba', 'prueba', 9002);
end $$;

-- 1. Estructura y privilegios (como postgres) ---------------------------------------------------------------------
do $$
declare
  c record;
begin
  for c in
    select column_name, data_type, is_nullable from information_schema.columns
    where table_schema = 'public' and table_name = 'contenido' and column_name in ('valor_en', 'valor_fr')
  loop
    assert c.data_type = 'text' and c.is_nullable = 'YES', 'E1: ' || c.column_name || ' no es text con null permitido';
  end loop;
  assert (select count(*) from information_schema.columns
          where table_schema = 'public' and table_name = 'contenido' and column_name in ('valor_en', 'valor_fr')) = 2,
         'E1: faltan las columnas valor_en o valor_fr';

  assert (select count(*) from pg_constraint
          where conrelid = 'public.contenido'::regclass and contype = 'c'
            and conname in ('contenido_valor_en_largo', 'contenido_valor_fr_largo', 'contenido_precio_sin_traduccion')) = 3,
         'E2: faltan restricciones de la 0005';
  assert (select count(*) from pg_constraint
          where conrelid = 'public.contenido'::regclass and conname in ('contenido_valor_largo', 'contenido_precio_entero')) = 2,
         'E2: la 0005 no debe quitar las restricciones de la 0003';

  -- privilegios por columna (has_column_privilege también ve los de tabla)
  assert has_column_privilege('anon', 'public.contenido', 'valor_en', 'select')
     and has_column_privilege('anon', 'public.contenido', 'valor_fr', 'select'), 'E3: anon no puede leer las traducciones';
  assert not has_column_privilege('anon', 'public.contenido', 'valor_en', 'update')
     and not has_column_privilege('anon', 'public.contenido', 'valor_fr', 'update')
     and not has_column_privilege('anon', 'public.contenido', 'valor_fr', 'insert')
     and not has_table_privilege('anon', 'public.contenido', 'insert,update,delete,truncate'),
         'E3: anon tiene privilegios de escritura en contenido';
  assert has_column_privilege('authenticated', 'public.contenido', 'valor_en', 'update')
     and has_column_privilege('authenticated', 'public.contenido', 'valor_fr', 'update')
     and has_column_privilege('authenticated', 'public.contenido', 'valor_fr', 'insert'),
         'E3: authenticated no puede editar las traducciones (las filas las filtra RLS)';
  assert (select relrowsecurity from pg_class where oid = 'public.contenido'::regclass), 'E4: RLS inactiva en contenido';
  assert (select count(*) from pg_policies where schemaname = 'public' and tablename = 'contenido'
          and policyname in ('contenido_publico_lee', 'contenido_propietario_inserta', 'contenido_propietario_actualiza',
                             'contenido_propietario_borra')) = 4, 'E4: faltan políticas de contenido de la 0003';

  -- ningún precio del proyecto tiene traducciones (la restricción lo garantiza; esto confirma que se validó al crearla)
  assert not exists (select 1 from public.contenido where tipo = 'precio' and (valor_en is not null or valor_fr is not null)),
         'E5: hay precios con traducción';
end $$;

-- 2. Público (anon) ------------------------------------------------------------------------------------------------
set local role anon;
do $$
declare
  n int;
  r record;
begin
  perform set_config('request.jwt.claims', '{"role":"anon"}', true);

  -- lo que pide el sitio en /en/ y /fr/: GET /rest/v1/contenido?select=clave,valor,valor_en,valor_fr,tipo
  select valor, valor_en, valor_fr into r from public.contenido where clave = 'prueba.idiomas.texto';
  assert r.valor = 'Texto de prueba' and r.valor_en = 'Test text' and r.valor_fr = 'Texte d''essai',
         'A1: anon no lee las traducciones';
  select count(*) into n from public.contenido
  where clave = 'prueba.idiomas.solo-es' and valor_en is null and valor_fr is null;
  assert n = 1, 'A1: anon debe ver null donde no hay traducción';

  begin update public.contenido set valor_en = 'Hacked' where clave = 'prueba.idiomas.texto';
        raise exception 'A2: anon actualizó valor_en';
  exception when insufficient_privilege then null; end;
  begin update public.contenido set valor_fr = 'Piraté' where clave = 'prueba.idiomas.texto';
        raise exception 'A2: anon actualizó valor_fr';
  exception when insufficient_privilege then null; end;
  begin insert into public.contenido (clave, valor, valor_fr, tipo, etiqueta, grupo)
        values ('prueba.idiomas.anon', 'x', 'x', 'texto', 'x', 'prueba');
        raise exception 'A3: anon insertó contenido con traducción';
  exception when insufficient_privilege then null; end;
end $$;
reset role;

-- 3. Autenticado que NO es propietario ----------------------------------------------------------------------------
set local role authenticated;
do $$
declare
  n int;
begin
  perform set_config('request.jwt.claims',
    '{"sub":"b1000000-0000-4000-8000-00000000001b","role":"authenticated"}', true);

  select count(*) into n from public.contenido where clave = 'prueba.idiomas.texto' and valor_fr = 'Texte d''essai';
  assert n = 1, 'N1: no lee las traducciones';
  update public.contenido set valor_fr = 'Intrus' where clave = 'prueba.idiomas.texto';
  get diagnostics n = row_count;
  assert n = 0, 'N2: un usuario cualquiera actualizó valor_fr';
  update public.contenido set valor_en = 'Intruder', valor_fr = 'Intrus' where clave = 'prueba.idiomas.solo-es';
  get diagnostics n = row_count;
  assert n = 0, 'N2: un usuario cualquiera agregó traducciones';
end $$;
reset role;

-- 4. Propietario ---------------------------------------------------------------------------------------------------
set local role authenticated;
do $$
declare
  n int;
  v text;
  k text;
begin
  perform set_config('request.jwt.claims',
    '{"sub":"a1000000-0000-4000-8000-00000000001a","role":"authenticated"}', true);

  assert public.es_propietario(), 'P1: el propietario no es reconocido';

  -- edita valor_fr (lo que hace el portal: PATCH con los tres valores de la fila)
  update public.contenido
  set valor = 'Texto de prueba', valor_en = 'Test text', valor_fr = 'Texte modifié par le propriétaire.'
  where clave = 'prueba.idiomas.texto';
  get diagnostics n = row_count;
  assert n = 1, 'P2: el propietario no editó valor_fr';
  select valor_fr into v from public.contenido where clave = 'prueba.idiomas.texto';
  assert v = 'Texte modifié par le propriétaire.', 'P2: valor_fr no guardado';

  -- el trigger de la 0003 marca `actualizado` aunque sólo cambie una traducción. Se prueba con una fila creada antes de
  -- esta transacción (las de prueba ya tienen actualizado = now(), así que no servirían); el rollback la deja igual.
  select clave into k from public.contenido
  where tipo <> 'precio' and actualizado < now() and clave not like 'prueba.%' order by orden, clave limit 1;
  if k is null then
    raise notice 'P2b omitida: no hay una fila de texto anterior a esta transacción';
  else
    update public.contenido set valor_fr = 'Traduction de test (idiomas_test.sql).' where clave = k;
    get diagnostics n = row_count;
    assert n = 1, 'P2b: el propietario no editó valor_fr de ' || k;
    assert (select actualizado from public.contenido where clave = k) = now(),
           'P2b: cambiar sólo valor_fr no marcó actualizado en ' || k;
  end if;

  -- agrega y quita traducciones; null = vuelve a la traducción fija del sitio
  update public.contenido set valor_en = 'Spanish only, now in English' where clave = 'prueba.idiomas.solo-es';
  get diagnostics n = row_count;
  assert n = 1, 'P3: no agregó valor_en';
  update public.contenido set valor_en = null, valor_fr = null where clave = 'prueba.idiomas.texto';
  get diagnostics n = row_count;
  assert n = 1, 'P3: no pudo dejar las traducciones en null';
  update public.contenido set valor_fr = 'Texte modifié par le propriétaire.' where clave = 'prueba.idiomas.texto';

  -- crea una fila con los tres idiomas y la borra
  insert into public.contenido (clave, valor, valor_en, valor_fr, tipo, etiqueta, grupo, orden)
  values ('prueba.idiomas.nueva', 'Nueva', 'New', 'Nouvelle', 'texto', 'Prueba', 'prueba', 9003);
  delete from public.contenido where clave = 'prueba.idiomas.nueva';
  get diagnostics n = row_count;
  assert n = 1, 'P4: no borró la fila nueva';

  -- el precio no se traduce: ni en un update, ni al crear, ni pasando a precio un texto traducido
  begin update public.contenido set valor_en = '58000' where clave = 'prueba.idiomas.precio';
        raise exception 'P5: precio con valor_en aceptado';
  exception when check_violation then null; end;
  begin update public.contenido set valor_fr = 'cinquante-huit mille' where clave = 'prueba.idiomas.precio';
        raise exception 'P5: precio con valor_fr aceptado';
  exception when check_violation then null; end;
  begin insert into public.contenido (clave, valor, valor_en, tipo, etiqueta, grupo)
        values ('prueba.idiomas.precio2', '1000', '1000', 'precio', 'x', 'prueba');
        raise exception 'P5: precio nuevo con valor_en aceptado';
  exception when check_violation then null; end;
  begin update public.contenido set tipo = 'precio', valor = '1000' where clave = 'prueba.idiomas.solo-es';
        raise exception 'P5: un texto con traducción pasó a precio';
  exception when check_violation then null; end;
  update public.contenido set valor = '60000' where clave = 'prueba.idiomas.precio';   -- el monto sí se edita
  get diagnostics n = row_count;
  assert n = 1, 'P5: no editó el precio';

  -- en blanco: se rechaza (vacío en el portal = null, nunca «»)
  foreach v in array array['', ' ', '   '] loop
    begin
      update public.contenido set valor_en = v where clave = 'prueba.idiomas.texto';
      raise exception 'P6: valor_en en blanco aceptado: «%»', v;
    exception when check_violation then null;
    end;
    begin
      update public.contenido set valor_fr = v where clave = 'prueba.idiomas.texto';
      raise exception 'P6: valor_fr en blanco aceptado: «%»', v;
    exception when check_violation then null;
    end;
  end loop;

  -- largo: hasta 4000 caracteres (char_length: una «é» cuenta uno, aunque ocupe dos bytes)
  begin update public.contenido set valor_en = repeat('x', 4001) where clave = 'prueba.idiomas.texto';
        raise exception 'P7: valor_en de 4001 caracteres aceptado';
  exception when check_violation then null; end;
  begin update public.contenido set valor_fr = repeat('é', 4001) where clave = 'prueba.idiomas.texto';
        raise exception 'P7: valor_fr de 4001 caracteres aceptado';
  exception when check_violation then null; end;
  update public.contenido set valor_en = repeat('x', 4000), valor_fr = repeat('é', 4000)
  where clave = 'prueba.idiomas.solo-es';
  get diagnostics n = row_count;
  assert n = 1, 'P7: 4000 caracteres rechazados';
  update public.contenido set valor_en = null, valor_fr = null where clave = 'prueba.idiomas.solo-es';

  -- las reglas de la 0003 siguen valiendo para el español
  begin update public.contenido set valor = '   ' where clave = 'prueba.idiomas.texto';
        raise exception 'P8: valor en blanco aceptado';
  exception when check_violation then null; end;
  begin update public.contenido set valor = null where clave = 'prueba.idiomas.texto';
        raise exception 'P8: valor null aceptado';
  exception when not_null_violation then null; end;
end $$;
reset role;

-- 5. Verificación final (como postgres): quedó lo del propietario y nada de lo intentado por otros ------------------
do $$
declare
  r record;
begin
  select valor, valor_en, valor_fr into r from public.contenido where clave = 'prueba.idiomas.texto';
  assert r.valor = 'Texto de prueba' and r.valor_en is null and r.valor_fr = 'Texte modifié par le propriétaire.',
         'F1: la fila de prueba no tiene los valores del propietario';
  select valor, valor_en, valor_fr into r from public.contenido where clave = 'prueba.idiomas.precio';
  assert r.valor = '60000' and r.valor_en is null and r.valor_fr is null, 'F2: el precio quedó con traducción';
  assert (select tipo from public.contenido where clave = 'prueba.idiomas.solo-es') = 'texto', 'F3: cambió el tipo';
  assert not exists (select 1 from public.contenido
                     where clave in ('prueba.idiomas.anon', 'prueba.idiomas.precio2', 'prueba.idiomas.nueva')
                        or valor_en in ('Hacked', 'Intruder') or valor_fr in ('Piraté', 'Intrus')),
         'F4: quedó escrito algo de un intento rechazado';
end $$;

select 'PRUEBAS_IDIOMAS_OK' as resultado;
rollback;
