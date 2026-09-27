# ADR 0005: git, GitHub y pipeline de GitHub Actions para todas las sesiones

- **Fecha:** 2026-09-26
- **Estado:** aceptado; entra con la PR del pipeline, la primera del repositorio.
- **Modelo de IA utilizado:** Claude Opus 5.5 (`claude-opus-5-5`), en la sesión «Configurar git, GitHub y el pipeline CI/CD». Se coordinó con las sesiones «Modelo 3D departamento desde planos» (backend y publicación) y «Modelo 3D, navegación móvil y UI» (diseño, visor y fases de Blender).
- **Revisor humano:** Romain Ange (romain.ange@gosocket.net). El 2026-09-26 decidió:
  - repositorio privado;
  - de `ref/`, versionar sólo el plano;
  - protección en GitHub más reglas locales;
  - que cada sesión fusione su propia PR cuando el CI esté en verde.

## Contexto

- Hasta el 2026-09-26 la carpeta no estaba bajo control de versiones.
- Varias sesiones de Claude escribían a la vez en la misma carpeta. Un cambio podía pisar otro sin dejar rastro.
- El despliegue a Netlify dependía de que el usuario corriera `web/desplegar.py` a mano. El modo automático de las sesiones lo bloquea.
- El usuario pidió «iniciar git, subir el repo a GitHub y trabajar estrictamente con el pipeline de GitHub», para esta sesión, la otra y las futuras.

## Decisiones

1. **Repositorio:**
   - git con la rama `main`, en el repositorio privado `romainhr/ProjectBlenderhouse`;
   - la autenticación usa la sesión de `gh` que ya existía en la máquina, sin claves SSH ni tokens nuevos.
   - La instantánea inicial (commit `979572f`, 04:29) se tomó por orden del usuario, sin esperar el aviso de la sesión de Blender. Ningún archivo versionable había cambiado en los 20 minutos anteriores; esa sesión sólo escribía renders en `review/`, que no se versiona.
   - Las rutas del portal de gestión, todavía en construcción, quedaron fuera por acuerdo con su sesión y entran por su propia PR.
2. **Qué se versiona** (`.gitignore`):
   - **Sí:** fuentes, scripts, documentos y ADR; `assets/` (texturas CC0 de Poly Haven y texturas propias generadas por código); `exports/web/` y `web/renders_png/`, que son entradas de `web/build.py` y el CI las necesita; y `ref/plano/`, entrada de la fase 1.
   - **No:** `review/` (238 MB de renders regenerables), `web/dist/` (salida del build) y los GLB de validación de la fase 6.
   - **Tampoco `build/*.blend`:** el maestro se regenera con `bash build/depto_run.sh`. Es un binario de 10 MB que cambia en cada corrida, y dos worktrees que lo regeneran producen un conflicto imposible de fusionar.
   - **Tampoco `ref/depto/`:** son fotos de otro inmueble.
   - **Sin Git LFS:** ningún archivo versionado pasa de 5 MB.
3. **Un worktree, una rama y una PR por sesión:**
   - Varias sesiones comparten la carpeta. Si una cambia de rama en el working tree compartido, cambia los archivos que están usando las demás.
   - La carpeta principal queda en `main` y sólo se actualiza con `git pull --ff-only`.
4. **CI** (`.github/workflows/ci.yml`, «CI y despliegue»), en cada PR y en cada push a `main`:
   - **Sin secretos versionados:** `.github/scripts/buscar-secretos.sh` y su prueba. Revisa lo versionado e imprime el archivo y el tipo de hallazgo, nunca el valor.
   - **Pruebas:** `cd web && npm test`, `python3 -m unittest discover -s web/tests -p 'test_*.py'` y `python3 build/depto_medicion/test_sellos.py`.
   - **Pruebas SQL:** ver la decisión 10.
   - **Build del sitio:** `python3 web/build.py` con Pillow fija (`.github/requirements-ci.txt`). Sube `web/dist` como artefacto, que sirve de vista previa descargable.
   - Un push a una rama sin PR no dispara el CI. Así se evita correr todo dos veces por cada push a una PR.
5. **Despliegue:**
   - El job `desplegar` corre sólo en `main`, después de los otros cuatro, y publica exactamente el `web/dist` que pasó el build, con `python3 web/desplegar.py --sitio loft-2d2b`.
   - En `main`, el build exige `SUPABASE_URL` y `SUPABASE_CLAVE_PUBLICA`, para no publicar un sitio con las reservas desconectadas.
   - Los tres secretos (`NETLIFY_TOKEN`, `SUPABASE_URL`, `SUPABASE_CLAVE_PUBLICA`) los crea el usuario en GitHub. La clave de Supabase es la publicable, pública por diseño con RLS.
6. **Pipeline de Blender** (`.github/workflows/blender.yml`):
   - Manual (`workflow_dispatch`), con la última fase como entrada.
   - Blender 3.6.23 descargado de blender.org y verificado contra un sha256 fijado en el workflow. Corre con Xvfb y Mesa llvmpipe, sin GPU.
   - Sube el maestro, los exports y los renders como artefacto. No commitea: lo regenerado entra por PR.
   - **No se había corrido en un runner** al escribir este ADR.
7. **Fusión:**
   - La sesión dueña de la PR la fusiona cuando todas las verificaciones están en verde, por decisión del usuario.
   - No se exige una aprobación en GitHub: hay una sola cuenta, y GitHub no deja aprobar la PR propia.
8. **Protección de `main` y reglas locales:**
   - En GitHub: PR obligatoria, con las verificaciones «Sin secretos versionados», «Pruebas», «Pruebas SQL» y «Build del sitio» en verde, sin push directo ni forzado. Resultado de la configuración: ver la adenda.
   - En `.claude/settings.json` (versionado, aplica a toda sesión en este proyecto): reglas deny contra push a `main`, push forzado, `gh pr merge --admin` y `desplegar.py` a mano. Son una barrera más, no una garantía: los patrones son prefijos de comando.
9. **Endurecimiento del CI:**
   - acciones oficiales fijadas por SHA;
   - `permissions: contents: read`;
   - `persist-credentials: false`;
   - los secretos entran sólo como variables de entorno;
   - las entradas manuales pasan por `env`, nunca interpoladas en el script.
10. **Pruebas SQL** (`web/supabase/tests/*.sql`), con Supabase CLI, que el usuario aprobó el 2026-09-26:
    - Las pruebas usan `auth.uid()`, `storage.objects` y los roles `anon` y `authenticated` de Supabase, así que no corren en un PostgreSQL cualquiera.
    - El job «Pruebas SQL» instala el CLI 2.118.0 (`supabase/setup-cli`, fijada por SHA) y levanta un Supabase local con Docker en el runner. Sólo arranca Postgres, Auth y Storage.
    - `.github/scripts/pruebas-sql.sh` aplica las migraciones en orden y corre cada archivo de pruebas con `psql` como `postgres` (lo mismo que el SQL Editor), con `ON_ERROR_STOP`.
    - El `config.toml` se genera en una carpeta temporal del runner; no se agrega nada a `web/supabase/`.
    - No se usa `supabase test db`: exige pgTAP y estas pruebas son SQL plano con `raise exception`.
    - El CI no aplica migraciones en el proyecto real. Las sigue aplicando el usuario en el SQL Editor, después de que la PR pase.

## Alternativas descartadas

- **Un solo working tree con varias ramas:** ver decisión 3.
- **Versionar `build/depto.blend`:** ver decisión 2.
- **Git LFS:** hoy no hace falta, y cada checkout del CI consumiría su cuota de transferencia. Se reevalúa si la historia crece mucho (ver consecuencias).
- **Conectar el repositorio a Netlify para que construya ahí:**
  - habría dos pipelines;
  - Netlify necesitaría acceso al repositorio;
  - el build y el despliegue quedarían fuera de las verificaciones de GitHub.
  - El pedido es un solo pipeline en GitHub.
- **Vistas previas de PR en Netlify, por ahora:** `desplegar.py` sólo publica en producción. La sesión dueña de ese archivo agregará un modo borrador, verificado contra la API de Netlify, y se engancha en el workflow. Mientras tanto, la vista previa es el artefacto `sitio-dist`.
- **gitleaks o trufflehog:** son herramientas externas sin aprobación. Se usa un script propio con prueba, que puede reemplazarse si se aprueba una.
- **Que el usuario fusione cada PR:** era la opción recomendada. El usuario prefirió la fusión por la sesión con el CI en verde.

## Consecuencias

- **Cada fusión en `main` publica en producción sin revisión humana previa.**
  - Mitigaciones: el CI tiene que pasar entero, y `desplegar.py` verifica que la portada responda 200.
  - Para volver atrás: una PR de revert, que vuelve a desplegar, o restaurar un despliegue anterior desde el panel de Netlify.
- **Cuotas del plan gratuito en un repositorio privado.** Según la documentación de GitHub que conozco: 2.000 minutos de Actions al mes y 500 MB para artefactos (hay que verificarlo en Settings → Billing).
  - `web/dist` pesa unos 19 MB por corrida, con retención de 3 días en las PR y de 1 día en `main`.
  - El pipeline de Blender es manual y puede tardar decenas de minutos (estimado, sin medir).
- **Crecimiento de la historia:** los binarios versionados (unos 17 MB de `exports/web`, 17 MB de `web/renders_png` y 24 MB de texturas) la hacen crecer en cada regeneración. Si el repositorio se acerca a 1 GB, se evalúa LFS o generar esos archivos en el CI.
- **Pruebas SQL:** corren contra el Postgres y el Storage que trae el CLI, que pueden diferir en versión del proyecto real. Una migración que pasa en el CI todavía se aplica a mano en producción.
- **Lo que el CI no cubre:** el pipeline de Blender en cada PR y las pruebas del sitio en un navegador.

## Adenda: protección de `main` (2026-09-26)

- **Modelo de IA utilizado:** Claude Opus 5.5. **Revisor humano:** Romain Ange, que aprobó intentar la configuración.
- GitHub rechazó las dos vías con HTTP 403 («Upgrade to GitHub Pro or make this repository public to enable this feature»): la protección de rama (`PUT /branches/main/protection`) y un ruleset (`POST /rulesets`). El plan gratuito no las ofrece en repositorios privados.
- Lo que sí rige:
  - la regla de `CLAUDE.md` para todas las sesiones;
  - las reglas deny de `.claude/settings.json`;
  - el propio CI: en `main`, el job de despliegue vuelve a correr todas las verificaciones y no publica si alguna falla. Una fusión en rojo ensuciaría la historia de `main`, pero no llegaría a producción.
- Para tener protección real: pasar a GitHub Pro o hacer público el repositorio. El JSON de la protección (PR obligatoria, las cuatro verificaciones, sin push forzado ni borrado, también para administradores) está listo para aplicarlo con `gh api`.

## Adenda: revisión y fusión centralizadas (2026-09-26)

- **Modelo de IA utilizado:** Claude Opus 5.5 (`claude-opus-5-5`), en la sesión «Configurar git, GitHub y el pipeline CI/CD». **Revisor humano:** Romain Ange, que pidió el cambio: «cualquier PR que hagan las otras sesiones quiero que las analices, valides y apruebes a main».
- **Reemplaza la decisión 7.** Las sesiones autoras ya no fusionan. La sesión «Configurar git, GitHub y el pipeline CI/CD» revisa cada PR (revisión de código con el skill `code-review` y validación de lo que el CI no cubre) y la fusiona o devuelve observaciones.
- **Antecedente:** las PR #2 a #8 las fusionaron sus propias sesiones con el CI en verde, según la regla anterior. Según la sesión autora, Romain aprobó en su chat, después de ver capturas, las PR #4, #5 y #7.
- **Aprobación en GitHub:** todas las PR salen de la cuenta `romainhr` y GitHub no permite aprobar una PR propia. La aprobación queda como comentario en la PR.
- **Sin regla deny para `gh pr merge`:** también bloquearía a la sesión revisora, y rodearla con otra vía sería esquivar un control. La regla es de conducta y está en `CLAUDE.md`.
- **Consecuencias:**
  - Una revisión más antes de cada despliegue, y un cuello de botella si la sesión revisora no está activa. En ese caso Romain puede fusionar desde GitHub.
  - Hay trazabilidad: cada PR queda con su comentario de revisión.
