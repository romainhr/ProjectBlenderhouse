#!/usr/bin/env bash
# Instala el servidor MCP para Blender en un venv del proyecto, el addon en Blender 3.6
# y deja .mcp.json listo para Claude Code. Idempotente. No requiere sudo ni uv.
set -euo pipefail
cd "$(dirname "$0")"
PROJECT="$(pwd)"
BLENDER_VER="$(blender --version | head -1 | sed -E 's/Blender ([0-9]+\.[0-9]+).*/\1/')"
ADDONS_DIR="$HOME/.config/blender/$BLENDER_VER/scripts/addons"

echo "==> [1/3] Entorno virtual y paquete mcp-for-blender"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet --upgrade mcp-for-blender
.venv/bin/mcp-for-blender --help >/dev/null 2>&1 || true
echo "    instalado: $(.venv/bin/pip show mcp-for-blender | grep -E '^Version')"

echo "==> [2/3] Addon en Blender $BLENDER_VER"
mkdir -p "$ADDONS_DIR"
# Primero el instalador del propio paquete; si no reconoce 3.6, copiamos el addon.py que trae el paquete.
if ! .venv/bin/mcp-for-blender install-addon >/tmp/mcp_addon_install.log 2>&1; then
  ADDON_SRC="$(find .venv -name 'addon.py' -path '*blender_mcp*' | head -1 || true)"
  if [ -z "$ADDON_SRC" ]; then
    echo "    El paquete no trae addon.py; descargando la versión publicada en GitHub"
    curl -fsSL https://raw.githubusercontent.com/ahujasid/blender-mcp/main/addon.py -o "$ADDONS_DIR/mcp_for_blender.py"
  else
    cp "$ADDON_SRC" "$ADDONS_DIR/mcp_for_blender.py"
  fi
fi
ADDON_FILE="$(grep -l 'MCP for Blender\|BlenderMCP' "$ADDONS_DIR"/*.py 2>/dev/null | head -1 || true)"
[ -n "$ADDON_FILE" ] || { echo "No se encontró el addon en $ADDONS_DIR"; exit 1; }
MODULE="$(basename "$ADDON_FILE" .py)"
blender -b --python-expr "import bpy; bpy.ops.preferences.addon_enable(module='$MODULE'); bpy.ops.wm.save_userpref(); print('ADDON_ENABLED $MODULE')" 2>/dev/null | grep ADDON_ENABLED

echo "==> [3/3] .mcp.json para Claude Code"
cat > .mcp.json <<EOF
{
  "mcpServers": {
    "blender": {
      "type": "stdio",
      "command": "$PROJECT/.venv/bin/mcp-for-blender",
      "args": [],
      "env": { "DISABLE_TELEMETRY": "true", "BLENDER_HOST": "localhost", "BLENDER_PORT": "9876" }
    }
  }
}
EOF
echo "    escrito .mcp.json"
echo
echo "Listo. Ahora: abre 'blender', tecla N > pestaña 'MCP for Blender' > Connect, y reinicia Claude Code en esta carpeta."
