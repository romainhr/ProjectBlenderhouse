-- Pruebas de public.reservas y sus funciones (0001_reservas.sql y 0002_hoy_propiedad.sql). Se ejecutan en el SQL Editor de Supabase (o psql
-- como postgres) dentro de una transacción que se deshace: no dejan datos. Si todo pasa, la última línea del
-- resultado es «PRUEBAS_OK»; si una falla, se aborta con el nombre de la prueba.
begin;

do $$
declare
  hoy date := public.hoy_loft();                        -- el día en el huso de la propiedad (0002)
  c text;
  n int;
  err text;
begin
  -- 1. una solicitud válida devuelve código de 8 caracteres y las noches
  select codigo, noches into c, n from public.solicitar_reserva(hoy + 10, hoy + 13, 2, 'Ana Prueba', 'ANA@ejemplo.cl');
  assert char_length(c) = 8 and n = 3, 'prueba 1: solicitud válida';
  assert (select email from public.reservas where codigo = c) = 'ana@ejemplo.cl', 'prueba 1: correo normalizado';

  -- 2. solape con una solicitud activa -> fechas_ocupadas
  begin
    perform public.solicitar_reserva(hoy + 12, hoy + 15, 2, 'Beto Prueba', 'beto@ejemplo.cl');
    raise exception 'prueba 2: debía rechazar el solape';
  exception when others then
    get stacked diagnostics err = message_text;
    assert err = 'fechas_ocupadas', 'prueba 2: mensaje ' || err;
  end;

  -- 3. rango contiguo (entra el día que el otro sale) sí se permite
  perform public.solicitar_reserva(hoy + 13, hoy + 15, 1, 'Caro Prueba', 'caro@ejemplo.cl');

  -- 4. una solicitud rechazada libera sus fechas
  update public.reservas set estado = 'rechazada' where codigo = c;
  perform public.solicitar_reserva(hoy + 10, hoy + 12, 2, 'Dani Prueba', 'dani@ejemplo.cl');

  -- 5. validaciones: fecha pasada, 1 noche, más de 30, 5 huéspedes, correo inválido, nombre vacío
  begin perform public.solicitar_reserva(hoy - 1, hoy + 2, 2, 'Eva', 'eva@ejemplo.cl');
        raise exception 'prueba 5a';
  exception when others then get stacked diagnostics err = message_text; assert err = 'fecha_pasada', '5a ' || err; end;
  begin perform public.solicitar_reserva(hoy + 40, hoy + 41, 2, 'Eva', 'eva@ejemplo.cl');
        raise exception 'prueba 5b';
  exception when others then get stacked diagnostics err = message_text; assert err = 'datos_invalidos', '5b ' || err; end;
  begin perform public.solicitar_reserva(hoy + 40, hoy + 80, 2, 'Eva', 'eva@ejemplo.cl');
        raise exception 'prueba 5c';
  exception when others then get stacked diagnostics err = message_text; assert err = 'datos_invalidos', '5c ' || err; end;
  begin perform public.solicitar_reserva(hoy + 40, hoy + 43, 5, 'Eva', 'eva@ejemplo.cl');
        raise exception 'prueba 5d';
  exception when others then get stacked diagnostics err = message_text; assert err = 'datos_invalidos', '5d ' || err; end;
  begin perform public.solicitar_reserva(hoy + 40, hoy + 43, 2, 'Eva', 'no-es-correo');
        raise exception 'prueba 5e';
  exception when others then get stacked diagnostics err = message_text; assert err = 'datos_invalidos', '5e ' || err; end;
  begin perform public.solicitar_reserva(hoy + 40, hoy + 43, 2, ' ', 'eva@ejemplo.cl');
        raise exception 'prueba 5f';
  exception when others then get stacked diagnostics err = message_text; assert err = 'datos_invalidos', '5f ' || err; end;

  -- 5g. cambiar el huso de la sesión no mueve «hoy» (antes current_date seguía a la sesión)
  perform set_config('timezone', 'Etc/GMT+12', true);
  begin perform public.solicitar_reserva(public.hoy_loft() - 1, public.hoy_loft() + 2, 2, 'Eva', 'eva@ejemplo.cl');
        raise exception 'prueba 5g';
  exception when others then get stacked diagnostics err = message_text; assert err = 'fecha_pasada', '5g ' || err; end;
  perform set_config('timezone', 'UTC', true);
  assert not exists (select 1 from pg_extension where extname = 'btree_gist'), 'prueba 5h: btree_gist sigue instalada';

  -- 6. disponibilidad: sólo rangos activos y sin columnas personales
  assert (select count(*) from public.disponibilidad(hoy, hoy + 60)) = 2, 'prueba 6: dos rangos activos';
  assert pg_get_function_result('public.disponibilidad(date, date)'::regprocedure) = 'TABLE(entrada date, salida date)',
         'prueba 6: disponibilidad sólo devuelve fechas';
  assert pg_get_function_result('public.solicitar_reserva(date, date, int, text, text, text, text)'::regprocedure)
         = 'TABLE(codigo text, noches integer)', 'prueba 6: solicitar_reserva sólo devuelve código y noches';
end $$;

-- 7. el rol público (anon) no lee ni escribe la tabla, pero sí ejecuta las dos funciones
set local role anon;
do $$
declare err text;
begin
  begin
    perform 1 from public.reservas limit 1;
    raise exception 'prueba 7a: anon leyó la tabla';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into public.reservas (entrada, salida, huespedes, nombre, email)
    values (current_date + 100, current_date + 103, 2, 'Intruso', 'x@ejemplo.cl');
    raise exception 'prueba 7b: anon insertó directo';
  exception when insufficient_privilege then null;
  end;
  perform * from public.disponibilidad(current_date, current_date + 30);
  perform public.solicitar_reserva(current_date + 200, current_date + 202, 1, 'Anon Prueba', 'anon@ejemplo.cl');
end $$;
reset role;

select 'PRUEBAS_OK' as resultado;
rollback;
