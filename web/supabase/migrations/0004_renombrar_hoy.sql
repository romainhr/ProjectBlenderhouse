-- 0004 (sobre 0002_hoy_propiedad.sql, ya aplicada): la propiedad no es un loft. Corrección de Romain Ange
-- (2026-09-26): «en ningún momento dije que era un loft esto, y no lo es». El nombre visible del sitio es «Project-roomVR».
--
-- * public.hoy_loft() pasa a llamarse public.hoy_propiedad() (misma definición: el día en America/Santiago, sin
--   depender del TimeZone de la sesión). La 0002 no se reescribe porque ya está aplicada.
-- * solicitar_reserva vuelve a crearse igual que en la 0002, pero con la función nueva. Después se borra la vieja:
--   nadie más la llama (ni el sitio ni el portal; el front sólo usa las funciones públicas).
-- * El comentario de la tabla, que se ve en el panel de Supabase, deja de decir «LOFT».
-- Pruebas: web/supabase/tests/reservas_test.sql (5g, 5i).

begin;

create or replace function public.hoy_propiedad()
returns date
language sql
stable
set search_path = public
as $$
  select (now() at time zone 'America/Santiago')::date;
$$;

revoke all on function public.hoy_propiedad() from public;

create or replace function public.solicitar_reserva(
  p_entrada date, p_salida date, p_huespedes int, p_nombre text, p_email text,
  p_telefono text default null, p_mensaje text default null)
returns table (codigo text, noches int)
language plpgsql
volatile
security definer
set search_path = public
as $$
#variable_conflict use_column
declare
  r public.reservas;
  v_hoy date := public.hoy_propiedad();
begin
  if p_entrada is null or p_salida is null then
    raise exception 'fechas_requeridas' using errcode = '22023';
  end if;
  if p_entrada < v_hoy then
    raise exception 'fecha_pasada' using errcode = '22023';
  end if;
  if p_entrada > v_hoy + 365 then
    raise exception 'fecha_lejana' using errcode = '22023';
  end if;
  insert into public.reservas (entrada, salida, huespedes, nombre, email, telefono, mensaje)
  values (p_entrada, p_salida, p_huespedes, btrim(p_nombre), lower(btrim(p_email)),
          nullif(btrim(p_telefono), ''), nullif(btrim(p_mensaje), ''))
  returning * into r;
  return query select r.codigo, (r.salida - r.entrada);
exception
  when exclusion_violation then
    raise exception 'fechas_ocupadas' using errcode = 'P0001';
  when check_violation then
    raise exception 'datos_invalidos' using errcode = '22023';
end;
$$;

revoke all on function public.solicitar_reserva(date, date, int, text, text, text, text) from public;
grant execute on function public.solicitar_reserva(date, date, int, text, text, text, text) to anon, authenticated;

drop function if exists public.hoy_loft();      -- sin cascade: si algo la usara, falla y no cambia nada

comment on table public.reservas is
  'Solicitudes de reserva de Project-roomVR (sitio de prueba). Datos personales: sólo para responder.';

commit;
