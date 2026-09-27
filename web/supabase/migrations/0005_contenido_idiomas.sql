-- 0005 (sobre 0003_gestion.sql): traducciones al inglés y al francés de los textos editables del sitio.
-- Pedido de Romain Ange (2026-09-26): el sitio público «en los tres idiomas pero con selección automática por idioma
-- del navegador». El sitio en español sigue leyendo `valor`; las páginas /en/ y /fr/ leen `valor_en` y `valor_fr`.
-- Guía de aplicación: docs/portal-gestion.md (paso 2). Pruebas: web/supabase/tests/idiomas_test.sql.
--
-- Qué significa cada valor:
--   * valor     -> español, obligatorio (como en la 0003).
--   * valor_en  -> inglés, opcional.  null = el sitio en inglés usa su traducción fija (web/src/i18n/en.json).
--   * valor_fr  -> francés, opcional. null = el sitio en francés usa su traducción fija (web/src/i18n/fr.json).
--   Un valor vacío no significa «sin traducción»: se guarda null (el portal convierte el campo vacío en null), y un
--   texto en blanco se rechaza, igual que en `valor`, para que una página nunca quede con un hueco.
--   * Los precios (tipo 'precio') no se traducen: el monto es el mismo en los tres idiomas y el sitio lo formatea.
--     Por eso sus valor_en y valor_fr deben ser null.
--
-- Privilegios y políticas (revisados contra la 0003):
--   * La 0003 da privilegios de TABLA sobre public.contenido: select a anon y authenticated; insert, update y delete a
--     authenticated. Un privilegio de tabla vale para todas sus columnas, también las que se agregan después: las
--     columnas nuevas quedan legibles por el público y editables por authenticated sin otro grant.
--   * Las filas las siguen filtrando las políticas de la 0003, que no miran columnas: contenido_publico_lee (todos
--     leen) y contenido_propietario_* (sólo es_propietario() inserta, actualiza o borra). No hay que tocarlas.
--   * Aun así se vuelven a declarar los privilegios, iguales a los de la 0003 (revoke all y luego los grants): así la
--     migración deja el estado conocido aunque alguien los haya cambiado a mano en el panel. anon sigue sin escribir.
--
-- Todo va en una transacción: si algo falla, no queda nada a medias. Es idempotente: se puede volver a ejecutar
-- (add column if not exists, drop constraint if exists antes de add). No trae semilla: las traducciones empiezan en
-- null, es decir, con las traducciones fijas del sitio. Si se usara la CLI de Supabase (que ya abre su propia
-- transacción), quitar el begin y el commit.

begin;

-- 0. Requisito: la 0003 aplicada. Sin esto, el error sería un «relation does not exist» menos claro.
do $$
begin
  if to_regclass('public.contenido') is null then
    raise exception '0005 requiere la 0003_gestion.sql: public.contenido no existe';
  end if;
end $$;

-- 1. Columnas ----------------------------------------------------------------------------------------------------
alter table public.contenido add column if not exists valor_en text;
alter table public.contenido add column if not exists valor_fr text;

-- 2. Límites: los mismos que contenido_valor_largo de la 0003 (no en blanco y hasta 4000 caracteres, contados como
-- char_length, es decir, en puntos de código), pero con null permitido. Restricciones aparte (drop + add) para que
-- volver a ejecutar la migración no falle ni las duplique.
alter table public.contenido drop constraint if exists contenido_valor_en_largo;
alter table public.contenido add constraint contenido_valor_en_largo
  check (valor_en is null or (btrim(valor_en) <> '' and char_length(valor_en) <= 4000));

alter table public.contenido drop constraint if exists contenido_valor_fr_largo;
alter table public.contenido add constraint contenido_valor_fr_largo
  check (valor_fr is null or (btrim(valor_fr) <> '' and char_length(valor_fr) <= 4000));

-- Un precio no se traduce. También impide que un texto ya traducido pase a tipo 'precio' con sus traducciones.
alter table public.contenido drop constraint if exists contenido_precio_sin_traduccion;
alter table public.contenido add constraint contenido_precio_sin_traduccion
  check (tipo <> 'precio' or (valor_en is null and valor_fr is null));

comment on column public.contenido.valor is
  'Texto en español (obligatorio). Es el que muestra el sitio en /.';
comment on column public.contenido.valor_en is
  'Texto en inglés editado por el propietario, o null: el sitio en /en/ usa su traducción fija. Siempre null en precios.';
comment on column public.contenido.valor_fr is
  'Texto en francés editado por el propietario, o null: el sitio en /fr/ usa su traducción fija. Siempre null en precios.';

-- 3. Privilegios: los mismos de la 0003 (ver el encabezado). El trigger contenido_actualizado de la 0003 es
-- «before insert or update» por fila: también marca `actualizado` cuando sólo cambia una traducción.
revoke all on table public.contenido from anon, authenticated;
grant select on table public.contenido to anon, authenticated;
grant insert, update, delete on table public.contenido to authenticated;   -- filtrado por las políticas de la 0003

-- PostgREST recarga su caché de esquema al confirmar: sin esto, /rest/v1/contenido?select=valor_en respondería que la
-- columna no existe hasta la próxima recarga.
notify pgrst, 'reload schema';

commit;
