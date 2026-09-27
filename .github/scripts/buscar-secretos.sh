#!/usr/bin/env bash
# Falla si un archivo versionado tiene algo con forma de secreto, o si se versionó un archivo que no debe estar en git.
# Imprime sólo el archivo y el tipo de hallazgo, nunca el valor encontrado (los logs de Actions se conservan).
# Uso: bash .github/scripts/buscar-secretos.sh [carpeta del repositorio]
# Prueba: bash .github/scripts/test_buscar_secretos.sh. Decisión: docs/adr/0005-git-github-pipeline.md.
# Las claves de prueba de web/tests se arman en tiempo de ejecución ("sb_secret_" + "a" * 30) y no calzan.
set -euo pipefail
cd "${1:-.}"

# tipo|expresión regular extendida (git grep -E)
PATRONES=(
  "clave de servicio de Supabase|sb_secret_[A-Za-z0-9_-]{20,}"
  "token de Netlify|nfp_[A-Za-z0-9]{20,}"
  "token de GitHub|gh[pousr]_[A-Za-z0-9]{30,}"
  "token de grano fino de GitHub|github_pat_[A-Za-z0-9_]{30,}"
  "clave de Google|AQ\.[A-Za-z0-9_-]{20,}"
  "clave de API de Google|AIza[0-9A-Za-z_-]{35}"
  "clave de Anthropic|sk-ant-[A-Za-z0-9_-]{20,}"
  "clave privada|-----BEGIN [A-Z ]*PRIVATE KEY-----"
  "JWT literal (p. ej. service_role)|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
)

# Rutas que nunca se versionan (.gitignore las excluye; esto atrapa un git add -f)
PROHIBIDOS='(^|/)\.env(\.[^/]*)?$|\.(pem|key|p12)$|^web/src/(admin/)?js/config\.js$|^web/dist/|^review/|^build/[^/]*\.blend$'
# De ref/ sólo se versionan su README y el plano (autorizado); cualquier otra foto de referencia es privada
REF_PERMITIDO='^ref/(README\.md$|plano/)'

hallazgos=0
for p in "${PATRONES[@]}"; do
  tipo="${p%%|*}"
  re="${p#*|}"
  while IFS= read -r archivo; do
    [ -n "$archivo" ] || continue
    echo "SECRETO_POSIBLE ${archivo}: ${tipo}"
    hallazgos=$((hallazgos + 1))
  done < <(git grep -I -l -E -e "$re" -- . || true)
done
while IFS= read -r archivo; do
  [ -n "$archivo" ] || continue
  echo "ARCHIVO_PROHIBIDO ${archivo}"
  hallazgos=$((hallazgos + 1))
done < <(git ls-files | grep -E "$PROHIBIDOS" || true)
while IFS= read -r archivo; do
  [ -n "$archivo" ] || continue
  echo "REFERENCIA_PRIVADA ${archivo}"
  hallazgos=$((hallazgos + 1))
done < <(git ls-files -- ref | grep -vE "$REF_PERMITIDO" || true)

if [ "$hallazgos" -gt 0 ]; then
  echo "::error::${hallazgos} hallazgo(s): quita el secreto del commit (y rótalo si llegó a GitHub) o saca el archivo de git."
  exit 1
fi
echo "SECRETOS_OK $(git ls-files | wc -l) archivos versionados revisados"
