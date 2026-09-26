---
name: blender-photo-to-3d
description: Construye un modelo 3D en Blender 3.6 a partir de fotos de referencia (casas, edificios, muebles, objetos rígidos) mediante fases con compuertas, scripts bpy reproducibles y renders de revisión comparados con las fotos. Usar cuando el usuario entregue fotos y pida un modelo 3D, o pida iterar sobre uno existente en este proyecto.
---

# Foto → modelo 3D en Blender (fases con compuertas)

Cada fase produce un script en `build/`, un `.blend` actualizado y renders en `review/NN/`. No se avanza sin mostrar el render al usuario y obtener su visto bueno. Las fotos en perspectiva dan silueta y detalle; las medidas se sacan solo de vistas frontales/laterales o de referencias de tamaño conocido.

## Fase 0: Brief (`asset-brief.md`)

1. Mirar cada foto de `ref/` con la herramienta de lectura de imágenes. Anotar: vista (frente, lado, 3/4, detalle), qué elementos se ven, condiciones (lente, distorsión, obstrucciones).
2. Elegir un **patrón de escala** presente en la foto y su medida estándar. Tabla útil: puerta 2,05 a 2,15 m de alto y 0,8 a 0,9 m de ancho; ventana estándar 1,2 m; escalón 0,16 a 0,18 m; ladrillo 0,065 m de alto; bloque de hormigón 0,2 m; piso de vivienda 2,6 a 3,0 m; auto 4,3 a 4,8 m de largo; persona 1,7 m.
3. Medir proporciones en píxeles sobre la foto más ortogonal (ancho de fachada / alto de puerta, etc.) y convertirlas a metros con el patrón. Registrar 8 a 15 parámetros con su origen y una incertidumbre (±).
4. Listar las partes no visibles y cómo se van a inferir (simetría, tipología constructiva).
5. Escribir el brief y presentarlo. Compuerta: el usuario corrige medidas o supuestos.

## Fase 1: Calibración (`build/01_calibracion.py`)

Crear el `.blend` maestro con unidades métricas, colección raíz con el nombre del activo, un plano de suelo, y planos de referencia con las fotos frontal y lateral escaladas según el brief (imagen como empty `IMAGE` con `empty_display_size` = medida real). Guardar como `build/<nombre>.blend`.

## Fase 2: Blockout (`build/02_blockout.py`)

Solo masas primarias: cuerpo, techo, volúmenes anexos, terreno. Cubos y prismas con dimensiones del brief. Ejecutar `tools/render_review.py --out review/02`. Comparar `front.png` y `right.png` con las fotos: contornos, pendiente del techo, proporción alto/ancho. Objetivo: silueta correcta a ±5 %. Compuerta.

## Fase 3: Formas (`build/03_formas.py`)

Vanos (puertas y ventanas por booleano o inset+extrude), aleros, chimeneas, escaleras, porches, columnas. Mantener todo paramétrico: posiciones de ventanas en listas de tuplas con comentario de origen. Render y compuerta.

## Fase 4: Detalle (`build/04_detalle.py`)

Marcos, cornisas, zócalos, barandas, tejas o chapa como geometría simple o como normal map. Presupuesto: ≤ 150k triángulos para toda la escena en esta máquina. Render y compuerta.

## Fase 5: Materiales (`build/05_materiales.py`)

Materiales Principled con colores muestreados de las fotos; texturas CC0 de Poly Haven vía MCP si el usuario lo aprueba (≤ 2K). Render Eevee de `iso.png` para revisar. Compuerta.

## Fase 6: Exportación

`exports/<nombre>.glb` (con `export_apply=True`) y `manifest.json`. Reimportar en escena vacía, renderizar y comprobar dimensiones contra el brief.

## Iteración sobre un modelo existente

Cuando el usuario pida un cambio ("la ventana derecha es más ancha", "el techo tiene menos pendiente"):

1. Localizar la constante o entrada de lista en el script de la fase correspondiente.
2. Cambiarla, anotar el motivo en el comentario y volver a ejecutar esa fase y las siguientes (los scripts reconstruyen desde el `.blend` maestro).
3. Renderizar a `review/NN_vK/` y mostrar antes/después.

Si Blender está abierto con el MCP conectado, usar `get_viewport_screenshot` para vistas rápidas y `execute_blender_code` para inspección, pero los cambios definitivos siempre van al script de la fase, para que el modelo se pueda reconstruir.

## Reglas de código bpy 3.6

- Empezar cada script con la limpieza de lo que esa fase crea (por nombre o colección) para que sea re-ejecutable.
- Crear mallas con `bmesh` o `bpy.data.meshes.new` + `from_pydata` cuando la forma sea paramétrica; usar `bpy.ops` solo con contexto válido (`bpy.context.view_layer.objects.active`).
- Aplicar transformaciones antes de booleanos. Booleanos con `solver='EXACT'`.
- Guardar con `bpy.ops.wm.save_mainfile()` al final e imprimir un resumen (`FASE_OK <nombre> <n objetos> <triángulos>`).
- Ejecutar con: `blender -b build/<nombre>.blend --python build/NN_fase.py` y después el render de revisión.
