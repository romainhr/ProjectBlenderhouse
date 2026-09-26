## Qué cambia

<!-- Qué y por qué, en pocas líneas. Si hay una decisión de arquitectura, enlaza su ADR en docs/adr/. -->

## Cómo se probó

- [ ] CI en verde: secretos, pruebas, pruebas SQL y build del sitio
- [ ] Si toca `build/`: renders de revisión revisados (`review/...`) y desviaciones anotadas como medidas
- [ ] Si toca `web/supabase/`: la migración que el usuario debe aplicar en el SQL Editor después de fusionar:
- [ ] Si toca binarios generados (`exports/web/`, `web/renders_png/`, `assets/texturas/propias/`): van con el cambio del script que los produce

Al fusionar en `main`, el workflow «CI y despliegue» publica el sitio en https://loft-2d2b.netlify.app.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
