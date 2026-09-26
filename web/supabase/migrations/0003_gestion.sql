-- 0003 (sobre 0001_reservas.sql; no depende de 0002): portal de gestión del propietario del Departamento 2D2B.
-- Pedido: «un portal de gestión con login simple para que el propietario pueda editar fotos, descripción y manejar
-- reservas». Guía de aplicación: docs/portal-gestion.md. Pruebas: web/supabase/tests/gestion_test.sql.
--
-- Modelo de seguridad (el navegador usa la clave pública; el login entrega un JWT con rol «authenticated»):
--   * Estar autenticado NO da permisos. Cualquiera que logre una cuenta (registro abierto, o sesión anónima si se
--     activara) llega con el rol «authenticated». Por eso toda política de escritura o de lectura privada exige
--     public.es_propietario(), que busca auth.uid() en public.propietarios.
--   * public.propietarios sólo se modifica desde el panel de Supabase (rol postgres): nadie se da el rol a sí mismo.
--   * Primero se quitan todos los privilegios y luego se dan los mínimos: Supabase concede por defecto ALL sobre las
--     tablas nuevas de public a anon y authenticated (privilegios por defecto del esquema), así que cada tabla nueva
--     hace «revoke all» antes de cualquier «grant».
--   * Los privilegios de tabla o columna dicen QUÉ se puede tocar; las políticas RLS dicen QUÉ FILAS. Se usan ambos:
--     aunque una política quedara mal, el propietario no puede cambiar datos del huésped ni fechas (grant por columnas).
--   * En las políticas, la función va como «(select public.es_propietario())»: Postgres la evalúa una vez por
--     sentencia (initPlan) y no una vez por fila (recomendación de la documentación de RLS de Supabase).
--   * Todo va en una transacción: si algo falla, no queda nada a medias. Es idempotente: se puede volver a ejecutar
--     (create ... if not exists, create or replace, drop ... if exists antes de create, semilla con on conflict).
--     Si se usara la CLI de Supabase (que ya abre su propia transacción), quitar el begin y el commit.

begin;

-- 1. Propietarios ------------------------------------------------------------------------------------------------
-- Sin clave foránea a auth.users, a propósito: las pruebas usan identificadores inventados sin tocar el esquema auth
-- (Supabase recomienda no escribir en él). Si se borra un usuario, su fila queda huérfana pero es inofensiva: los
-- uuid no se reutilizan. La guía indica cómo quitarla.
create table if not exists public.propietarios (
  user_id  uuid primary key,
  email    text not null constraint propietarios_email_largo check (char_length(email) between 3 and 254),
  creado   timestamptz not null default now()
);

comment on table public.propietarios is
  'Usuarios de Supabase Auth con acceso al portal de gestión. Se edita sólo desde el panel (SQL Editor).';

-- RLS activa y sin políticas + revoke: ni anon ni authenticated leen ni escriben esta tabla, ni siquiera el propio
-- propietario (así una sesión robada no puede agregar otro propietario). Sólo la lee es_propietario().
alter table public.propietarios enable row level security;
revoke all on table public.propietarios from anon, authenticated;

-- SECURITY DEFINER: se ejecuta como su dueño (postgres), que sí puede leer propietarios; devuelve sólo un booleano,
-- sin exponer la lista. search_path fijo y nombres calificados: nadie puede suplantar una tabla o función que use.
-- Sin sesión, auth.uid() es null y la comparación da false.
create or replace function public.es_propietario()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.propietarios p
    where p.user_id = (select auth.uid())
  );
$$;

comment on function public.es_propietario() is
  'true si el usuario de la sesión (auth.uid()) está en public.propietarios. El portal la llama por /rest/v1/rpc.';

revoke all on function public.es_propietario() from public;
grant execute on function public.es_propietario() to anon, authenticated;     -- anon siempre obtiene false

-- 2. Reservas: gestión por el propietario ------------------------------------------------------------------------
alter table public.reservas add column if not exists nota_interna text;
alter table public.reservas add column if not exists actualizada timestamptz;   -- null = nunca modificada

-- Restricción aparte (drop + add) para que volver a ejecutar la migración no falle ni la duplique.
alter table public.reservas drop constraint if exists reservas_nota_interna_largo;
alter table public.reservas add constraint reservas_nota_interna_largo
  check (nota_interna is null or char_length(nota_interna) <= 2000);

comment on column public.reservas.nota_interna is 'Nota del propietario; el huésped nunca la ve (anon no lee reservas).';
comment on column public.reservas.actualizada is 'Última modificación; la pone el trigger reservas_actualizada.';

-- El trigger fija la fecha en el servidor: el cliente no puede falsearla (tampoco tiene privilegio sobre la columna).
-- No es SECURITY DEFINER: sólo modifica la fila NEW que ya se está actualizando.
create or replace function public.tg_reservas_actualizada()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.actualizada := now();
  return new;
end;
$$;

revoke all on function public.tg_reservas_actualizada() from public, anon, authenticated;

drop trigger if exists reservas_actualizada on public.reservas;
create trigger reservas_actualizada
  before update on public.reservas
  for each row execute function public.tg_reservas_actualizada();

-- Privilegios: se parte de cero (como en 0001). anon sigue sin ningún acceso a la tabla (sólo a las funciones de
-- 0001/0002). authenticated puede leer y borrar, y actualizar SÓLO estado y nota_interna: nombre, correo, teléfono,
-- mensaje, fechas, código y huéspedes quedan fuera del alcance de cualquier sesión, incluida la del propietario.
-- No se da insert: las reservas nuevas siguen entrando sólo por solicitar_reserva(), con sus validaciones.
revoke all on table public.reservas from anon, authenticated;
grant select, delete on table public.reservas to authenticated;
grant update (estado, nota_interna) on table public.reservas to authenticated;

-- Filas: sólo el propietario. Un authenticated que no es propietario ve 0 filas y sus update/delete no afectan nada.
-- Las funciones SECURITY DEFINER de 0001/0002 no cambian: su dueño es el dueño de la tabla y no pasa por RLS.
drop policy if exists reservas_propietario_lee on public.reservas;
create policy reservas_propietario_lee on public.reservas
  for select to authenticated
  using ((select public.es_propietario()));

drop policy if exists reservas_propietario_actualiza on public.reservas;
create policy reservas_propietario_actualiza on public.reservas
  for update to authenticated
  using ((select public.es_propietario()))
  with check ((select public.es_propietario()));

drop policy if exists reservas_propietario_borra on public.reservas;
create policy reservas_propietario_borra on public.reservas
  for delete to authenticated
  using ((select public.es_propietario()));

-- 3. Contenido editable del sitio ---------------------------------------------------------------------------------
-- Texto plano, nunca HTML: el sitio lo inserta con textContent (regla del proyecto), así que un valor con «<script>»
-- se muestra tal cual y no se ejecuta. La clave tiene formato fijo para usarse sin escapar en data-contenido="…".
create table if not exists public.contenido (
  clave        text primary key
               constraint contenido_clave_formato check (clave ~ '^[a-z0-9][a-z0-9_.-]{1,59}$'),
  valor        text not null
               constraint contenido_valor_largo check (btrim(valor) <> '' and char_length(valor) <= 4000),
  tipo         text not null default 'texto'
               constraint contenido_tipo check (tipo in ('texto', 'parrafo', 'precio')),
  etiqueta     text not null
               constraint contenido_etiqueta_largo check (btrim(etiqueta) <> '' and char_length(etiqueta) <= 120),
  grupo        text not null
               constraint contenido_grupo_formato check (grupo ~ '^[a-z0-9][a-z0-9_.-]{1,59}$'),
  orden        integer not null default 0,
  actualizado  timestamptz not null default now(),
  -- Un precio es un entero de 0 a 10 000 000 escrito sólo con dígitos, sin ceros a la izquierda, puntos ni signos
  -- (el sitio lo formatea en CLP). CASE garantiza el orden: el cast sólo corre si el texto ya son dígitos, así un
  -- valor inválido da check_violation y no un error de conversión.
  constraint contenido_precio_entero check (
    case
      when tipo <> 'precio' then true
      when valor !~ '^(0|[1-9][0-9]{0,7})$' then false
      else valor::integer <= 10000000
    end)
);

comment on table public.contenido is
  'Textos editables del sitio (clave -> valor). Lectura pública; escritura sólo del propietario. Claves en docs/portal-gestion.md.';

create or replace function public.tg_contenido_actualizado()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.actualizado := now();
  return new;
end;
$$;

revoke all on function public.tg_contenido_actualizado() from public, anon, authenticated;

drop trigger if exists contenido_actualizado on public.contenido;
create trigger contenido_actualizado
  before insert or update on public.contenido
  for each row execute function public.tg_contenido_actualizado();

alter table public.contenido enable row level security;
revoke all on table public.contenido from anon, authenticated;
grant select on table public.contenido to anon, authenticated;
grant insert, update, delete on table public.contenido to authenticated;   -- filtrado por las políticas

drop policy if exists contenido_publico_lee on public.contenido;
create policy contenido_publico_lee on public.contenido
  for select to anon, authenticated
  using (true);                                                    -- los textos del sitio son públicos

drop policy if exists contenido_propietario_inserta on public.contenido;
create policy contenido_propietario_inserta on public.contenido
  for insert to authenticated
  with check ((select public.es_propietario()));

drop policy if exists contenido_propietario_actualiza on public.contenido;
create policy contenido_propietario_actualiza on public.contenido
  for update to authenticated
  using ((select public.es_propietario()))
  with check ((select public.es_propietario()));

drop policy if exists contenido_propietario_borra on public.contenido;
create policy contenido_propietario_borra on public.contenido
  for delete to authenticated
  using ((select public.es_propietario()));

-- Semilla: los textos vigentes de web/src/index.html (2026-09-26). on conflict do nothing: volver a ejecutar la
-- migración no pisa lo que el propietario ya editó. Tarifas: las de TARIFA en web/src/js/reserva-logica.js (ejemplo).
insert into public.contenido (clave, valor, tipo, etiqueta, grupo, orden) values
  ('hero.bajada',
   'Departamento de dos dormitorios de estilo industrial: concreto, acero y roble, con living luminoso y balcón. Recórrelo en 3D desde el navegador antes de reservar.',
   'parrafo', 'Portada: descripción principal', 'portada', 10),
  ('espacios.bajada',
   'Un living-cocina integrado entre dos dormitorios, cada uno con su baño cerca y closet corredero.',
   'parrafo', 'Espacios: introducción', 'espacios', 100),
  ('espacio.living.titulo', 'Living', 'texto', 'Living: título', 'espacios', 110),
  ('espacio.living.texto',
   'Muro de ladrillo a la vista, mueble de TV flotante de roble, sofá de cuero y lámpara de arco. Ventanal corredero al balcón.',
   'parrafo', 'Living: descripción', 'espacios', 111),
  ('espacio.cocina.titulo', 'Cocina', 'texto', 'Cocina: título', 'espacios', 120),
  ('espacio.cocina.texto',
   'En L, con frentes carbón, cubierta de concreto, anafe con campana de acero, horno y refrigerador. Repisas abiertas de roble.',
   'parrafo', 'Cocina: descripción', 'espacios', 121),
  ('espacio.dorm1.titulo', 'Dormitorio 1', 'texto', 'Dormitorio 1: título', 'espacios', 130),
  ('espacio.dorm1.texto',
   'Cama king de 1,80 × 2,00 con cabecero tapizado, veladores de acero y roble y closet corredero.',
   'parrafo', 'Dormitorio 1: descripción', 'espacios', 131),
  ('espacio.dorm2.titulo', 'Dormitorio 2', 'texto', 'Dormitorio 2: título', 'espacios', 140),
  ('espacio.dorm2.texto',
   'Cama king con cabecero de cuero, apliques de brazo para leer y closet corredero.',
   'parrafo', 'Dormitorio 2: descripción', 'espacios', 141),
  ('espacio.banos.titulo', 'Dos baños', 'texto', 'Baños: título', 'espacios', 150),
  ('espacio.banos.texto',
   'Tina con ducha de tubería vista y mampara, lavabo de concreto sobre vanitorio de roble y espejo redondo.',
   'parrafo', 'Baños: descripción', 'espacios', 151),
  ('espacio.balcon.titulo', 'Balcón', 'texto', 'Balcón: título', 'espacios', 160),
  ('espacio.balcon.texto',
   'Mesa bistró de acero y dos sillas plegables de roble, con baranda de vidrio. Se sale por el ventanal del living.',
   'parrafo', 'Balcón: descripción', 'espacios', 161),
  ('espacio.recibidor.titulo', 'Recibidor', 'texto', 'Recibidor: título', 'espacios', 170),
  ('espacio.recibidor.texto',
   'Banca con repisa para zapatos y perchero de cañería negra junto a la entrada.',
   'parrafo', 'Recibidor: descripción', 'espacios', 171),
  ('tarifa.noche', '58000', 'precio', 'Noche (ejemplo), en CLP', 'tarifas', 200),
  ('tarifa.limpieza', '15000', 'precio', 'Limpieza, una vez (ejemplo), en CLP', 'tarifas', 210),
  ('condiciones.llegada', 'desde 15:00', 'texto', 'Llegada (ejemplo)', 'condiciones', 300),
  ('condiciones.salida', 'hasta 11:00', 'texto', 'Salida (ejemplo)', 'condiciones', 310)
on conflict (clave) do nothing;

-- 4. Fotos --------------------------------------------------------------------------------------------------------
-- Cada fila apunta a un archivo del bucket «fotos». La ruta tiene un formato cerrado (una carpeta opcional y un
-- nombre en minúsculas con extensión de imagen): el sitio arma la URL pública con ella sin escapar nada y no puede
-- llegar un «../», un «javascript:», espacios ni una extensión .svg.
create table if not exists public.fotos (
  id       uuid primary key default gen_random_uuid(),
  espacio  text not null
           constraint fotos_espacio_formato check (espacio ~ '^[a-z0-9][a-z0-9_.-]{1,59}$'),
  ruta     text not null
           constraint fotos_ruta_unica unique
           constraint fotos_ruta_formato
             check (ruta ~ '^([a-z0-9][a-z0-9_-]{0,59}/)?[a-z0-9][a-z0-9_.-]{0,119}\.(jpg|jpeg|png|webp)$'),
  alt      text not null
           constraint fotos_alt_largo check (btrim(alt) <> '' and char_length(alt) <= 200),
  orden    integer not null default 0,
  visible  boolean not null default true,
  creada   timestamptz not null default now()
);

comment on table public.fotos is
  'Fotos por espacio (ruta dentro del bucket «fotos»). El público ve sólo visible = true; el propietario ve y edita todo.';
comment on column public.fotos.visible is
  'false la oculta del sitio, pero el archivo sigue accesible por su URL pública: para retirarlo hay que borrarlo.';

create index if not exists fotos_espacio_orden on public.fotos (espacio, orden);

alter table public.fotos enable row level security;
revoke all on table public.fotos from anon, authenticated;
grant select on table public.fotos to anon, authenticated;
grant insert, update, delete on table public.fotos to authenticated;      -- filtrado por las políticas

-- Dos políticas de lectura permisivas (se combinan con OR): el público ve las visibles; el propietario, todas.
drop policy if exists fotos_publico_lee on public.fotos;
create policy fotos_publico_lee on public.fotos
  for select to anon, authenticated
  using (visible);

drop policy if exists fotos_propietario_lee on public.fotos;
create policy fotos_propietario_lee on public.fotos
  for select to authenticated
  using ((select public.es_propietario()));

drop policy if exists fotos_propietario_inserta on public.fotos;
create policy fotos_propietario_inserta on public.fotos
  for insert to authenticated
  with check ((select public.es_propietario()));

drop policy if exists fotos_propietario_actualiza on public.fotos;
create policy fotos_propietario_actualiza on public.fotos
  for update to authenticated
  using ((select public.es_propietario()))
  with check ((select public.es_propietario()));

drop policy if exists fotos_propietario_borra on public.fotos;
create policy fotos_propietario_borra on public.fotos
  for delete to authenticated
  using ((select public.es_propietario()));

-- 5. Storage: bucket «fotos» --------------------------------------------------------------------------------------
-- Público: las imágenes se sirven por /storage/v1/object/public/fotos/<ruta> sin sesión y sin políticas de lectura.
-- Límites que aplica la Storage API al subir: 5 MB (5 * 1024 * 1024 = 5242880 bytes; supuesto: suficiente para
-- una foto web de 1600 px) y sólo JPEG, PNG o WebP. SVG queda fuera a propósito: puede traer scripts.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('fotos', 'fotos', true, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
  set public             = excluded.public,
      file_size_limit    = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- Políticas en storage.objects (tabla común a todos los buckets; cada política se limita a bucket_id = 'fotos').
-- Subir, reemplazar, mover y borrar: sólo el propietario. El nombre del archivo debe cumplir el mismo formato que
-- public.fotos.ruta, para que todo archivo subido se pueda referenciar.
-- La lectura por SQL/API (listar, /object/info) también es sólo del propietario: el público no puede enumerar el
-- bucket (por ejemplo, para descubrir fotos ocultas), aunque sí descarga por URL pública si conoce la ruta. Esa
-- política de lectura hace falta además para reemplazar (upsert) y para que update/delete encuentren la fila.
drop policy if exists fotos_propietario_lee on storage.objects;
create policy fotos_propietario_lee on storage.objects
  for select to authenticated
  using (bucket_id = 'fotos' and (select public.es_propietario()));

drop policy if exists fotos_propietario_sube on storage.objects;
create policy fotos_propietario_sube on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'fotos'
    and (select public.es_propietario())
    and name ~ '^([a-z0-9][a-z0-9_-]{0,59}/)?[a-z0-9][a-z0-9_.-]{0,119}\.(jpg|jpeg|png|webp)$'
  );

drop policy if exists fotos_propietario_actualiza on storage.objects;
create policy fotos_propietario_actualiza on storage.objects
  for update to authenticated
  using (bucket_id = 'fotos' and (select public.es_propietario()))
  with check (
    bucket_id = 'fotos'
    and (select public.es_propietario())
    and name ~ '^([a-z0-9][a-z0-9_-]{0,59}/)?[a-z0-9][a-z0-9_.-]{0,119}\.(jpg|jpeg|png|webp)$'
  );

drop policy if exists fotos_propietario_borra on storage.objects;
create policy fotos_propietario_borra on storage.objects
  for delete to authenticated
  using (bucket_id = 'fotos' and (select public.es_propietario()));

-- PostgREST recarga su caché de esquema al confirmar (las tablas y es_propietario aparecen en /rest/v1).
notify pgrst, 'reload schema';

commit;
