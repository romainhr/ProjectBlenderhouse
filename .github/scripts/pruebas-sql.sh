#!/usr/bin/env bash
# Aplica web/supabase/migrations/*.sql en orden y corre cada web/supabase/tests/*.sql contra el Supabase local que
# levantó `supabase start` (job «Pruebas SQL» de .github/workflows/ci.yml; Docker en el runner).
# Cada archivo corre como postgres, igual que en el SQL Editor, con ON_ERROR_STOP: el `raise exception` de una prueba
# hace fallar el job. Las pruebas se deshacen solas (begin … rollback). No aplica nada en el proyecto real de Supabase.
# Uso: bash .github/scripts/pruebas-sql.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

DB="$(docker ps --filter 'name=^supabase_db_' --format '{{.Names}}' | head -1)"
if [ -z "$DB" ]; then
  echo "::error::No hay un contenedor supabase_db_*: ¿corrió supabase start?"
  exit 1
fi

correr() {   # la contraseña es la de desarrollo local que fija el CLI de Supabase, no un secreto
  echo "== $1"
  docker exec -i -e PGPASSWORD=postgres "$DB" \
    psql -h 127.0.0.1 -U postgres -d postgres -X -q -v ON_ERROR_STOP=1 < "$1" 2>&1 | tail -n 20
}

shopt -s nullglob
migraciones=(web/supabase/migrations/*.sql)
pruebas=(web/supabase/tests/*.sql)
if [ "${#migraciones[@]}" -eq 0 ] || [ "${#pruebas[@]}" -eq 0 ]; then
  echo "::error::Faltan migraciones o pruebas en web/supabase/"
  exit 1
fi
for f in "${migraciones[@]}"; do correr "$f"; done
for f in "${pruebas[@]}"; do correr "$f"; done
echo "PRUEBAS_SQL_OK ${#migraciones[@]} migraciones, ${#pruebas[@]} archivos de pruebas"
