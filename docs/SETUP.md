# Setup: Claude Code + Blender en esta máquina

Máquina: MacBook Pro 10,1 (2012), Ubuntu 24.04, i7 4 núcleos, 8 GB RAM, Intel HD 4000 (OpenGL 4.2), NVIDIA apagada. Blender 3.6.23 LTS en `/opt/blender`, comando `blender`.

## 1. Servidor MCP (vía principal, funciona hoy)

Se usa `mcp-for-blender` instalado en un entorno virtual del proyecto (no hace falta `uv`).

```bash
bash setup.sh
```

El script hace, en orden:

1. Crea `.venv` e instala `mcp-for-blender` desde PyPI.
2. Instala el addon en Blender 3.6 (`~/.config/blender/3.6/scripts/addons/`) y lo habilita.
3. Deja `.mcp.json` apuntando al binario del venv, con telemetría desactivada.

Después, en cada sesión de trabajo:

1. Abrir Blender con interfaz: `blender`.
2. En el viewport 3D, tecla `N` → pestaña **MCP for Blender** → **Connect to MCP server** (puerto 9876).
3. Abrir Claude Code en esta carpeta. Al detectar `.mcp.json` pedirá aprobar el servidor `blender`.
4. Probar con: "usa get_scene_info y dime qué hay en la escena".

Sin la interfaz abierta el MCP no responde, pero todo el flujo por scripts (`blender -b ...`) sigue funcionando. Para trabajo largo con la RAM justa, es válido cerrar Blender y trabajar solo en headless.

### Seguridad

- `execute_blender_code` ejecuta Python arbitrario dentro de Blender. Guarda el `.blend` antes de sesiones largas y trabaja en esta carpeta, no en carpetas con datos sensibles.
- El socket escucha solo en `localhost:9876` y no tiene autenticación. No abrir el puerto a la red.
- Las claves de Rodin, Hunyuan3D, Tripo o Sketchfab se configuran en las preferencias del addon dentro de Blender, nunca en archivos de este repositorio. `.gitignore` excluye `.env` y `.venv`.
- Las fotos en `ref/` salen de la máquina solo si se usa un servicio de generación en la nube, y eso se decide caso por caso.

## 2. Generación imagen→3D (opcional, por servicio en la nube)

En esta GPU no corre ningún modelo local. Opciones vía el mismo MCP:

| Servicio | Entrada | Costo | Notas |
|---|---|---|---|
| Hyper3D Rodin | 1 a 5 fotos | créditos gratis iniciales, luego desde 30 USD/mes o 0,4 USD/generación vía fal.ai | mejor para objetos y props; malla densa, no editable con precisión |
| Hunyuan3D (Tencent Cloud) | 1 foto o texto | requiere cuenta Tencent Cloud | también hay un Space gratuito en Hugging Face con cola |
| Tripo | 1 foto | solo modo premium del addon | rápido, formas orgánicas |

Para una **casa**, la generación por IA da una "maqueta" de un solo bloque, poco útil para iterar. La vía recomendada es que el agente modele con `bpy` a partir de medidas tomadas de las fotos (ver skill). La IA generativa queda para mobiliario, vegetación y props.

## 3. Fotogrametría (opcional, CPU)

Con 20 a 80 fotos alrededor del objeto, COLMAP reconstruye una malla a escala relativa que sirve de referencia dentro de Blender. Está en los repositorios de Ubuntu (`sudo apt install colmap`, versión 3.9.1) y funciona solo con CPU, aunque tarda horas. No está instalado; se evalúa si el modelado desde fotos sueltas resulta insuficiente.

## 4. Camera matching con fSpy (opcional, manual)

fSpy calcula la cámara de una foto con perspectiva y su addon la importa a Blender con la foto de fondo, de modo que se puede modelar "calcando" la fachada. Es un paso manual tuyo (la IA no opera la interfaz de fSpy), pero mejora mucho la precisión en casas. Importador para Blender: `fSpy-Blender`.

## 5. Vía experimental: Blender 5.2 LTS con render por software

llvmpipe (Mesa) expone OpenGL 4.5 en esta máquina, así que Blender 5.2 podría arrancar con `LIBGL_ALWAYS_SOFTWARE=1`. Ventaja: acceso al MCP oficial de Blender, `blend-ai` y `blender-game-skills`. Desventaja: interfaz lenta y sin garantías. No probado. Si se quiere intentar:

```bash
mkdir -p ~/apps && cd ~/apps && wget https://download.blender.org/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz && tar xf blender-5.2.2-linux-x64.tar.xz
```

```bash
LIBGL_ALWAYS_SOFTWARE=1 ~/apps/blender-5.2.2-linux-x64/blender -b --python-expr "import gpu; print(gpu.platform.renderer_get(), gpu.platform.version_get())"
```

Si imprime `llvmpipe ... 4.5`, el modo headless sirve. La interfaz se prueba aparte. Pesa 383 MB; no sustituye a la 3.6 instalada.

## Verificación rápida del entorno

```bash
glxinfo -B | grep -E "renderer|version"; blender --version | head -1; ls .venv/bin/mcp-for-blender 2>/dev/null && echo "MCP instalado"
```
