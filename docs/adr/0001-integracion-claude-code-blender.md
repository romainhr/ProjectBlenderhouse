# ADR 0001: Integración de Claude Code con Blender para modelado 3D desde fotos

- **Fecha:** 2026-09-25
- **Estado:** propuesto, pendiente de ejecutar `setup.sh`
- **Modelo de IA utilizado:** Claude Fable 5.1 (`claude-fable-5-1`), sesión "IA en diseño 3D con Blender"
- **Revisor humano:** Romain Ange (romain.ange@gosocket.net)

## Contexto

Se quiere evaluar la capacidad de Claude Code para producir modelos 3D en Blender a partir de fotos y luego iterar sobre ellos. La máquina disponible es un MacBook Pro 2012 con Intel HD 4000 (OpenGL 4.2), 8 GB de RAM y GPU NVIDIA deshabilitada. Blender 3.6.23 LTS es la última versión con interfaz que corre en ese hardware; Blender 4.x y 5.x exigen OpenGL 4.3.

## Opciones evaluadas

| Opción | Requisito | Veredicto |
|---|---|---|
| MCP oficial de Blender (blender.org/lab) | Blender 5.1+ | descartado por hardware |
| `blend-ai` (175 herramientas, análisis de malla) | Blender 4.2+ | descartado por hardware |
| `blender-game-skills` (imagen→activo con IoU) | Blender 4.2+ | se adopta la metodología, no el código |
| `mcp-for-blender` (ahujasid) | Blender 3.0+, Python 3.10+ | **adoptado** |
| Solo scripts headless `blender -b` | Blender 3.6 | **adoptado** como base reproducible |
| Blender 5.2 + llvmpipe (render por software) | sin GPU | experimento futuro, no probado |
| Imagen→3D local (Hunyuan3D, TRELLIS) | GPU 16 a 24 GB | descartado; se usan servicios en la nube caso por caso |

## Decisión

1. Servidor MCP `mcp-for-blender` instalado en un venv del proyecto y declarado en `.mcp.json`, con telemetría desactivada y socket solo en localhost.
2. El modelado se hace con scripts `bpy` deterministas por fase (`build/`), revisados con renders headless (`tools/render_review.py`) comparados con las fotos. El MCP se usa para inspección y pruebas rápidas, no como fuente de verdad.
3. Skill de proyecto `blender-photo-to-3d` que fija el método (brief con medidas, blockout, formas, detalle, materiales, exportación) y las compuertas de aprobación humana.
4. Generación imagen→3D por IA (Rodin, Hunyuan3D, Tripo) solo para props y orgánicos, con aprobación explícita antes de enviar fotos fuera de la máquina.

## Adenda 2026-09-25: orquestación con workflows

A pedido del usuario, la construcción se orquesta con el Workflow de Claude Code: Claude Fable 5.1 actúa como director (brief, comparación visual contra las fotos, decisiones de cada ronda), Claude Opus 5.5 (`claude-opus-5-5`) como constructor (escribe y ejecuta los scripts `bpy` y los renders), y un agente crítico verifica cada ronda contra el brief antes de devolver el control al director. Primera prueba: mesa auxiliar de tres patas, 2 rondas, blockout aprobado. Revisor humano: Romain Ange.

## Consecuencias

- Todo el trabajo es reproducible y auditable: cada iteración es un cambio de constantes en un script.
- Sin interfaz moderna de Blender, algunas capacidades (extensiones 4.2+, EEVEE Next, geometry nodes recientes) no están disponibles.
- Riesgo conocido: `execute_blender_code` ejecuta código arbitrario. Mitigación: trabajar en esta carpeta, guardar antes, no exponer el puerto.
- Las fotos de referencia se tratan como datos del usuario; no salen de la máquina sin autorización puntual.
