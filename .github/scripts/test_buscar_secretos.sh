#!/usr/bin/env bash
# Prueba de buscar-secretos.sh en repositorios temporales: un repositorio limpio pasa; cada tipo de secreto y cada
# archivo prohibido lo hacen fallar sin que el valor aparezca en la salida.
# Los secretos de prueba se arman en tiempo de ejecución, para que este archivo no calce con los patrones.
# Uso: bash .github/scripts/test_buscar_secretos.sh
set -euo pipefail
SCRIPT="$(cd "$(dirname "$0")" && pwd)/buscar-secretos.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fallas=0
relleno() { head -c "$1" /dev/zero | tr '\0' "${2:-a}"; }

repo() {   # repositorio temporal con un archivo inocente que sí menciona los prefijos
  local d="$TMP/$1"
  git init -q "$d"
  printf 'la clave de servicio (sb_secret_...) nunca va aquí; sb_publishable_%s es pública\n' "$(relleno 30)" > "$d/ok.md"
  printf '"sb_secret_" + "a" * 30\n' > "$d/prueba.py"
  git -C "$d" add -A
  echo "$d"
}

esperar() {   # esperar <nombre> <código esperado> <texto que no debe salir o vacío> <carpeta>
  local nombre="$1" codigo="$2" oculto="$3" d="$4" salida real=0
  salida="$(bash "$SCRIPT" "$d" 2>&1)" || real=$?
  if [ "$real" -ne "$codigo" ]; then
    echo "FALLA $nombre: código $real, se esperaba $codigo"; echo "$salida"; fallas=$((fallas + 1)); return
  fi
  if [ -n "$oculto" ] && grep -qF -- "$oculto" <<< "$salida"; then
    echo "FALLA $nombre: la salida muestra el valor del secreto"; fallas=$((fallas + 1)); return
  fi
  echo "ok $nombre"
}

esperar "repositorio limpio" 0 "" "$(repo limpio)"

declare -A SECRETOS=(
  [supabase]="sb_secret_$(relleno 30 x)"
  [netlify]="nfp_$(relleno 30 b)"
  [github]="ghp_$(relleno 36 c)"
  [github_pat]="github_pat_$(relleno 40 d)"
  [google]="AQ.$(relleno 30 e)"
  [google_api]="AIza$(relleno 35 f)"
  [anthropic]="sk-ant-$(relleno 30 g)"
  [privada]="-----BEGIN RSA PRIV""ATE KEY-----"
  [jwt]="eyJ$(relleno 12 h).eyJ$(relleno 12 i).$(relleno 12 j)"
)
for nombre in "${!SECRETOS[@]}"; do
  d="$(repo "s_$nombre")"
  printf 'x = "%s"\n' "${SECRETOS[$nombre]}" > "$d/config.py"
  git -C "$d" add config.py
  oculto="${SECRETOS[$nombre]}"
  [ "$nombre" = privada ] && oculto=""   # el encabezado no es secreto; basta con que falle
  esperar "secreto $nombre" 1 "$oculto" "$d"
done

for ruta in .env web/.env.local claves/servidor.pem web/src/js/config.js web/dist/index.html review/x/a.txt \
            ref/depto/foto.txt build/depto.blend; do
  d="$(repo "p_${ruta//\//_}")"
  mkdir -p "$d/$(dirname "$ruta")"
  echo "contenido" > "$d/$ruta"
  git -C "$d" add -f "$ruta"
  esperar "prohibido $ruta" 1 "" "$d"
done

# sin seguimiento (sólo en disco) no cuenta: el buscador revisa lo versionado
d="$(repo sin_seguimiento)"
printf 'x = "nfp_%s"\n' "$(relleno 30 k)" > "$d/suelto.py"
esperar "archivo sin seguimiento" 0 "" "$d"

if [ "$fallas" -gt 0 ]; then echo "TEST_SECRETOS_FALLA $fallas"; exit 1; fi
echo "TEST_SECRETOS_OK"
