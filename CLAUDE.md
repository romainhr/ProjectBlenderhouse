# ProjectBlenderhouse: reglas para el agente

Objetivo: a partir de fotos en `ref/`, construir un modelo 3D en Blender y mejorarlo por iteraciones guiadas por renders. Lee `README.md` para el contexto y `docs/SETUP.md` para el entorno.

## Entorno (no asumir otra cosa)

- Blender **3.6.23** (API `bpy` 3.6; no usar funciones de 4.x como extensiones, `bpy.types.NodeTreeInterface`, EEVEE Next ni `object.children_recursive` en versiones donde no exista). Comando: `blender`.
- CPU solamente. Cycles siempre con `device='CPU'` y pocas muestras; para revisiones usar Workbench.
- 8 GB de RAM: escenas ligeras, sin subdivisiones altas, texturas ≤ 2K.
- El MCP `blender` solo responde si Blender está abierto con el addon conectado. Si no responde, trabajar en headless: `blender -b archivo.blend --python script.py`.

## Método de trabajo

1. **Brief primero.** Antes de modelar, escribir `asset-brief.md`: qué se ve en cada foto, dimensiones estimadas con su justificación (puertas ≈ 2,1 m, escalones ≈ 0,17 m, ladrillos ≈ 0,065 m de alto, etc.), proporciones medidas en las fotos, y qué partes no se ven y se infieren.
2. **Construir por scripts, no a mano.** Cada fase es un script `build/NN_fase.py` que carga el `.blend` maestro, borra lo que le toca y lo reconstruye a partir de constantes con comentario de origen (`ANCHO_FACHADA = 8.4  # ref/frente.jpg: 12,3 ventanas de 0,68 m`). Iterar = cambiar constantes y volver a ejecutar. Los scripts deben ser idempotentes.
3. **Revisar con renders en cada fase.** Ejecutar `tools/render_review.py` hacia `review/NN/`, mirar `contact.png` y `stats.json`, comparar con las fotos, y anotar desviaciones como medidas ("el techo es 15 % más bajo que en ref/lado.jpg"). No pasar de fase sin renders.
4. **El usuario decide en cada compuerta.** Mostrar el render y resumir qué se cambió y qué duda queda. Pedir aprobación antes de pasar a la fase siguiente.
5. **Nombrar y organizar.** Colección raíz con el nombre del activo; objetos con prefijo (`Casa_Muro_N`, `Casa_Techo`). Origen del activo en el suelo, centrado, +Y hacia el frente, unidades métricas.
6. **Exportar con manifiesto.** `exports/<nombre>.glb` más `manifest.json` (dimensiones, triángulos, materiales, fecha, fase). Reimportar el GLB en una escena vacía y renderizar para validar.

## Trabajo con git y GitHub

Aplica a todas las sesiones de Claude, las actuales y las futuras. Repositorio privado `romainhr/ProjectBlenderhouse`; decisión y motivos en `docs/adr/0005-git-github-pipeline.md`.

- **Todo cambio va en una rama con PR y CI en verde.** Nada de push directo a `main`, ni forzado, ni reescribir historia ya publicada. Para ponerse al día: `git merge origin/main` dentro de la rama.
- **Cada sesión usa su propio worktree.** Al empezar, `EnterWorktree` (crea `.claude/worktrees/<nombre>` desde `origin/main`) o `git worktree add .claude/worktrees/<nombre> -b <tema>/<descripcion> origin/main`. Varias sesiones comparten esta carpeta: la carpeta principal queda en `main`, no se edita y sólo se actualiza con `git pull --ff-only`.
- **Fusionar:** la sesión dueña de la PR la fusiona sola cuando todas las verificaciones están en verde (`gh pr checks <n> --watch` y después `gh pr merge <n> --squash`; GitHub borra la rama remota al fusionar). Nunca con verificaciones en rojo o pendientes, nunca con `--admin`. Lo decidió Romain Ange el 2026-09-26.
- **Nadie publica en Netlify fuera del pipeline.** Sólo el workflow «CI y despliegue» publica, al fusionar en `main` (o relanzado desde Actions sobre `main`). No se corre `web/desplegar.py` a mano: el bloqueo del modo automático de las sesiones y las reglas deny de `.claude/settings.json` no se esquivan.
- **Secretos:** `NETLIFY_TOKEN`, `SUPABASE_URL` y `SUPABASE_CLAVE_PUBLICA` son secretos de GitHub Actions y los administra el usuario. Nunca van en archivos, commits, PR ni logs. El CI falla si encuentra algo con forma de secreto.
- **Qué se versiona:** lo define `.gitignore`. No se versionan `review/`, `web/dist/`, `build/*.blend` ni `ref/depto/`. Si el worktree necesita el maestro, se copia `build/depto.blend` desde la carpeta principal o se regenera con `bash build/depto_run.sh`.
- **Binarios generados que sí se versionan** (`exports/web/`, `web/renders_png/`, `assets/texturas/propias/`): se commitean sólo en la PR que cambió el script que los produce. Si dos ramas los tocan, se regeneran; no se fusionan a mano.
- **Migraciones SQL:** el job «Pruebas SQL» aplica `web/supabase/migrations/` y corre `web/supabase/tests/` en un Supabase local del runner. Cada migración nueva va con sus pruebas. El CI no toca el proyecto real: la PR dice qué migración debe aplicar el usuario en el SQL Editor después de fusionar.
- **Atribución:** cada commit termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (si la sesión corre con otro modelo, se nombra ese modelo con la misma forma), y cada PR termina con `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- Una decisión de arquitectura va con su ADR en `docs/adr/`, en la misma PR.

## Lo que no hacer

- No subir fotos de `ref/` a servicios externos sin preguntar en ese momento. Excepción autorizada por el usuario el 2026-09-26: `ref/plano/` se versiona en el repositorio privado. `ref/depto/` no se versiona.
- No escribir claves de API en archivos del repositorio. Las claves van en las preferencias del addon.
- No usar `execute_blender_code` para operaciones destructivas sobre archivos fuera de esta carpeta.
- No prometer precisión que no se midió: distinguir siempre "medido en foto" de "inferido".
- No modelar orgánicos detallados (árboles, personas) con `bpy`; para eso proponer un activo de Poly Haven o generación en la nube.
