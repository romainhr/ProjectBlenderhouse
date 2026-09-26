# ProjectBlenderhouse

Banco de pruebas para evaluar qué tan bien Claude Code puede diseñar modelos 3D en Blender.

- **Entrada:** fotos de un objeto (una casa, un mueble, lo que sea) en `ref/`.
- **Salida:** un modelo 3D editable (`.blend`) y exportado (`.glb`), construido por scripts reproducibles en `build/`.
- **Iteración:** el agente renderiza vistas de revisión, las compara con las fotos y corrige. Tú comentas sobre los renders y él vuelve a construir.

## Estado del setup (2026-09-25)

| Componente | Estado |
|---|---|
| Blender 3.6.23 LTS en `/opt/blender` | instalado, renders headless verificados (Workbench, Eevee, Cycles CPU) |
| Servidor MCP `mcp-for-blender` | pendiente: ejecutar `setup.sh` (ver [docs/SETUP.md](docs/SETUP.md)) |
| Skill `blender-photo-to-3d` | lista en `.claude/skills/` |
| Script de renders de revisión | `tools/render_review.py`, probado |

## Por qué este setup y no otro

La máquina es un MacBook Pro 2012 con Intel HD 4000 (OpenGL 4.2), 8 GB de RAM y la NVIDIA apagada por temperatura. Eso descarta:

- Blender 4.2+ y 5.x con interfaz gráfica (exigen OpenGL 4.3). Por tanto también el MCP oficial de Blender (requiere 5.1+), `blend-ai` y las skills `blender-game-skills` tal cual (requieren 4.2+).
- Modelos de IA imagen→3D locales (Hunyuan3D, TRELLIS): necesitan GPU NVIDIA con 16 a 24 GB de VRAM.

Lo que sí funciona hoy, y es lo que se usa:

1. **`mcp-for-blender`** (antes `blender-mcp`, de Siddharth Ahuja): soporta Blender 3.0+, expone `execute_blender_code`, `get_scene_info`, `get_object_info`, `get_viewport_screenshot`, búsqueda de API, exportación a GLB/FBX, activos CC0 de Poly Haven, y generación imagen→3D en la nube vía Hyper3D Rodin, Hunyuan3D (Tencent Cloud) y Tripo, con claves propias.
2. **Blender headless (`blender -b`)** para construir con scripts deterministas y renderizar vistas de revisión. Es la parte reproducible: cada iteración es editar constantes en `build/*.py` y volver a ejecutar.
3. **Skill propia** `blender-photo-to-3d`, adaptada de la metodología de `blender-game-skills` (fases con compuertas, medidas contra referencia, evidencia renderizada) pero para Blender 3.6 y para arquitectura y objetos, no personajes.

Vía opcional, no probada: Blender 5.2 LTS portátil con render por software (`LIBGL_ALWAYS_SOFTWARE=1`, llvmpipe expone OpenGL 4.5 en esta máquina). Abriría el MCP oficial y las skills modernas, a costa de una interfaz lenta. Se documenta en [docs/SETUP.md](docs/SETUP.md) como experimento posterior.

## Flujo de trabajo

```
ref/fotos  ->  asset-brief.md (medidas, proporciones, supuestos)
           ->  build/01_calibracion.py   planos de referencia a escala real
           ->  build/02_blockout.py      masas principales      -> review/02/  (comparar con fotos)
           ->  build/03_formas.py        techo, vanos, volúmenes -> review/03/
           ->  build/04_detalle.py       marcos, cornisas, etc.  -> review/04/
           ->  build/05_materiales.py    materiales y texturas   -> review/05/
           ->  exports/<nombre>.glb + manifest.json
```

Renderizar una revisión de cualquier `.blend`:

```bash
blender -b build/casa.blend --python tools/render_review.py -- --out review/02 --target Casa
```

Genera `front/right/back/top/iso/iso_wire.png`, una hoja de contacto `contact.png` y `stats.json` con dimensiones y conteo de polígonos.

## Estructura

```
ref/        fotos de entrada (no se suben a ningún servicio sin tu autorización)
build/      scripts bpy por fase + .blend maestro
review/     renders de revisión por fase
exports/    GLB/FBX finales + manifiestos
tools/      utilidades (render_review.py)
docs/       SETUP.md, adr/
.claude/    skill del proyecto
```

## Fuentes consultadas

- [MCP for Blender (ahujasid/blender-mcp)](https://github.com/ahujasid/blender-mcp) y [paquete PyPI mcp-for-blender](https://pypi.org/project/mcp-for-blender/)
- [MCP Server oficial de Blender (requiere 5.1+)](https://www.blender.org/lab/mcp-server/) y [su conexión a Claude Code](https://dev.classmethod.jp/en/articles/claude-blender-connector-desktop-and-code/)
- [blender-game-skills: skills de Claude Code para imagen→3D](https://github.com/majidmanzarpour/blender-game-skills)
- [blend-ai: MCP con capturas de viewport y análisis de malla (4.2+)](https://github.com/HoldMyBeer-gg/blend-ai)
- [Qué hace bien y mal Claude + Blender MCP](https://www.mindstudio.ai/blog/claude-blender-mcp-real-world-performance)
- [Requisitos de Blender (OpenGL 4.3)](https://www.blender.org/download/requirements/) y [Blender 4.0 e Intel HD 4000](https://projects.blender.org/blender/blender/issues/114961)
- [Hunyuan3D-2.1 en Hugging Face](https://huggingface.co/spaces/tencent/Hunyuan3D-2.1), [Hyper3D Rodin precios](https://hyper3d.ai/pricing), [comparativa de generadores 3D 2026](https://learn.rundiffusion.com/ai-3d-model-generators/)
- [fSpy, camera matching desde una foto](https://fspy.io/) y [COLMAP, fotogrametría](https://colmap.github.io/tutorial.html)
