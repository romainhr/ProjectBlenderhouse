-- LOFT 2D2B (sitio de prueba): solicitudes de reserva sin cobro en línea. El dueño las confirma o rechaza desde el
-- panel de Supabase (Table editor -> reservas -> estado). Decisión: docs/adr/0003-sitio-arriendo-netlify-supabase.md
--
-- Seguridad (el sitio usa la clave pública «anon», que viaja en el navegador):
--   * RLS activa y SIN políticas: el público no puede leer, crear, cambiar ni borrar filas de la tabla.
--   * El público sólo ejecuta dos funciones SECURITY DEFINER:
--       disponibilidad(desde, hasta) -> rangos ocupados (sin datos personales)
--       solicitar_reserva(...)       -> crea una solicitud validada y devuelve sólo su código y las noches
--   * La restricción de exclusión impide dos solicitudes activas (pendiente o confirmada) con noches en común,
--     aunque lleguen al mismo tiempo.

create extension if not exists btree_gist;

create table if not exists public.reservas (
  id          uuid primary key default gen_random_uuid(),
  codigo      text not null unique default upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8)),
  creada      timestamptz not null default now(),
  entrada     date not null,
  salida      date not null,                       -- día de salida (la noche de salida no se ocupa)
  huespedes   smallint not null check (huespedes between 1 and 4),
  nombre      text not null check (char_length(btrim(nombre)) between 2 and 80),
  email       text not null check (char_length(email) <= 120 and email ~* '^[^@[:space:]]+@[^@[:space:]]+\.[a-z]{2,}$'),
  telefono    text check (telefono is null or telefono ~ '^[0-9 +().-]{6,20}$'),
  mensaje     text check (mensaje is null or char_length(mensaje) <= 1000),
  estado      text not null default 'pendiente'
              check (estado in ('pendiente', 'confirmada', 'rechazada', 'cancelada')),
  constraint reservas_noches check (salida - entrada between 2 and 30),     -- mínimo 2 noches, máximo 30
  constraint reservas_sin_solape exclude using gist (daterange(entrada, salida, '[)') with &&)
    where (estado in ('pendiente', 'confirmada'))
);

comment on table public.reservas is 'Solicitudes de reserva de LOFT 2D2B (prueba). Datos personales: sólo para responder.';

alter table public.reservas enable row level security;
revoke all on table public.reservas from anon, authenticated;

create or replace function public.disponibilidad(desde date, hasta date)
returns table (entrada date, salida date)
language sql
stable
security definer
set search_path = public
as $$
  select r.entrada, r.salida
  from public.reservas r
  where r.estado in ('pendiente', 'confirmada')
    and hasta > desde
    and hasta - desde <= 400
    and daterange(r.entrada, r.salida, '[)') && daterange(desde, hasta, '[)')
  order by r.entrada;
$$;

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
begin
  if p_entrada is null or p_salida is null then
    raise exception 'fechas_requeridas' using errcode = '22023';
  end if;
  if p_entrada < current_date then
    raise exception 'fecha_pasada' using errcode = '22023';
  end if;
  if p_entrada > current_date + 365 then
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

revoke all on function public.disponibilidad(date, date) from public;
revoke all on function public.solicitar_reserva(date, date, int, text, text, text, text) from public;
grant execute on function public.disponibilidad(date, date) to anon, authenticated;
grant execute on function public.solicitar_reserva(date, date, int, text, text, text, text) to anon, authenticated;
