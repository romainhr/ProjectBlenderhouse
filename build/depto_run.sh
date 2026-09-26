#!/usr/bin/env bash
# Pipeline del activo Depto: reconstruye el maestro desde cero y regenera toda la evidencia de revisión.
# Uso: bash build/depto_run.sh [NN] [vK]
#   NN = última fase a construir (por defecto 06); vK = sufijo opcional de la carpeta de revisión
#   (review/depto_NN_vK), para no pisar la evidencia de una compuerta ya presentada.
# Se detiene en el primer error: cada paso devuelve código distinto de 0 si falla una prueba.
set -euo pipefail
cd "$(dirname "$0")/.."
BL="blender -b --python-exit-code 1"
HASTA="$(printf '%02d' "$((10#${1:-06}))")"
REV="review/depto_${HASTA}${2:+_$2}"
filtro() { grep -vE "EGL Error" | grep -E "FASE_OK|CALIBRACION|MAPEO|CHECK|INTERIOR_DONE|REVIEW_DONE|COMPARE|VERIFICACION|RECORRIDO|SELLOS|VALIDACION_GLB|ERROR|Error|Traceback|FALLA" || true; }
fase() { echo "== Fase $1"; $BL ${2:+build/depto.blend} --python "build/depto_$1.py" 2>&1 | filtro; test "${PIPESTATUS[0]}" -eq 0; }

echo "== Cadena de sellos (prueba sin Blender)"
python3 build/depto_medicion/test_sellos.py | tail -1
fase 01_calibracion
fase 02_blockout 1
[[ "$HASTA" > "02" ]] && fase 03_formas 1
[[ "$HASTA" > "03" ]] && fase 04_mobiliario 1
[[ "$HASTA" > "04" ]] && fase 05_materiales 1
if [[ "$HASTA" > "05" ]]; then
    fase 06_exportar 1
    echo "== Reimportación del GLB en una escena vacía"
    $BL --python tools/validar_glb.py -- --glb exports/depto.glb --manifiesto exports/manifest.json --activo depto \
        --out "$REV" --ocultar Depto_Cielo,Depto_Palier_Cielo 2>&1 | filtro; test "${PIPESTATUS[0]}" -eq 0
    echo "== El GLB que arma el visor con los archivos web (exports/web) también coincide"
    $BL --python tools/validar_glb.py -- --glb exports/depto_web_armado.glb --manifiesto exports/manifest.json \
        --activo depto --out "$REV/web" --ocultar Depto_Cielo,Depto_Palier_Cielo 2>&1 | filtro; test "${PIPESTATUS[0]}" -eq 0
fi
# Desde la fase 5 (materiales y luz) las vistas se revisan en Eevee; la planta de comparación sigue en Workbench.
MOTOR=$([[ "$HASTA" > "04" ]] && echo EEVEE || echo WORKBENCH)
echo "== Renders de ambiente ($MOTOR) y planta -> $REV"
$BL build/depto.blend --python tools/render_interior.py -- --out "$REV" --engine "$MOTOR" --samples 32 \
    --planta-plana --planta-solo Depto_Muros 2>&1 | filtro; test "${PIPESTATUS[0]}" -eq 0
echo "== Planta vs plano (sólo la colección Depto_Muros)"
python3 tools/compare_plan.py --plano ref/plano/plano_depto.png --render "$REV/Planta.png" \
    --out "$REV" --min-cubierto 0.90 --max-sobre-blanco 0.03 \
    --excluir "48,158,113,343;428,312,452,356" | head -1   # balcón (baranda, no muro) y triángulo de acceso
echo "== Líneas del plano vs coordenadas (muros, cocina y baños)"
python3 build/depto_medicion/verificar_lineas.py | tail -1
if [[ "$HASTA" > "02" ]]; then
    # Sin muebles se exige 0,25 m; con el mobiliario del plano, el radio del tour (0,20 m, ADR 0002).
    RADIO=$([[ "$HASTA" > "03" ]] && echo 0.20 || echo 0.25)
    echo "== Recorrido desde el hall (cámara de $RADIO m de radio)"
    $BL build/depto.blend --python build/depto_recorrido.py -- --out "$REV" --radio "$RADIO" 2>&1 | filtro
    test "${PIPESTATUS[0]}" -eq 0
fi
echo "== Revisión estándar (render_review)"
$BL build/depto.blend --python tools/render_review.py -- --out "$REV/ortho" --target Depto \
    --hide Depto_Cielo,Depto_Palier --frente +Y 2>&1 | filtro; test "${PIPESTATUS[0]}" -eq 0
echo "PIPELINE_OK hasta la fase $HASTA ($REV)"
