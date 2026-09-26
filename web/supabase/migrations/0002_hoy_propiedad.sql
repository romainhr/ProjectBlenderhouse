-- 0002 (sobre 0001_reservas.sql, ya aplicada): «hoy» en el huso de la propiedad y sin btree_gist.
--
-- Hallazgos de la verificación del 2026-09-26 (docs/adr/0003, decisión 6):
-- * solicitar_reserva usaba current_date, que sigue el TimeZone de la sesión: PostgREST lo deja cambiar con la
--   cabecera «Prefer: timezone=…», y por defecto es UTC, distinto del día que ve el visitante (de noche en Chile,
--   «hoy» salía rechazado como fecha pasada). Ahora el día sale de public.hoy_loft(), en un huso fijo.
-- * btree_gist no hace falta: la exclusión sólo compara rangos (GiST nativo de daterange).
--
-- Supuesto: la propiedad está en Chile continental (tarifas en CLP, textos es-CL); si no, cambiar el huso aquí y
-- ZONA_PROPIEDAD en web/src/js/reserva-logica.js.

create or replace function public.hoy_loft()
returns date
language sql
stable
set search_path = public
as $$
  select (now() at time zone 'America/Santiago')::date;
$$;

revoke all on function public.hoy_loft() from public;

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
  v_hoy date := public.hoy_loft();
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

drop extension if exists btree_gist;     -- sin cascade: si algo dependiera de ella, falla y no cambia nada
