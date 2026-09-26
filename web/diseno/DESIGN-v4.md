# Project-roomVR: sistema de diseño v4 («editorial cálido»)

## Concepto
Sitio de arriendo turístico de un departamento urbano de 2 dormitorios y 2 baños (≈ 54 m² construidos), con balcón y un recorrido 3D en el navegador. El interior es de estilo industrial cálido: un muro de ladrillo, cielo de hormigón visto, acero negro, piso de roble, sofá de cuero y luz cálida. **No es un loft**: nunca usar esa palabra. El nombre visible es exactamente «Project-roomVR» y nunca debe partirse en el guion.

Tono visual: una revista de arquitectura e interiorismo. La fotografía (renders del modelo 3D) manda. Mucho aire, ritmo editorial con tamaños contrastados, calidez y deseo de quedarse. Base clara, con uno o dos bloques de color intenso para dar ritmo. Tiene que ser atractivo, no solo limpio: la versión anterior quedó «fome».

## Color
- Papel `#F6F1EA` (fondo) y arena `#EDE3D6` (superficie alterna).
- Tinta `#1F1B17` (texto) y tinta secundaria `#5F574E`. Línea `#E0D6C8`.
- Terracota `#A4471E` (acento: botón principal, enlaces, foco) y terracota oscura `#7F3515` (hover y bloques de color).
- Oliva `#5E6B52` (secundario, estados correctos).
- Carbón `#26221E`: a lo sumo una sección oscura, para el recorrido 3D.
- Contraste AA en todo el texto. El texto sobre imagen lleva un degradado o un bloque que lo garantice.

## Tipografía
- Títulos: **Fraunces** (serif con carácter, 400 a 600, tipo oración). Display de 72 a 120 px en computador y de 40 a 56 px en teléfono. Un par de palabras en cursiva de Fraunces, con moderación.
- Texto: **Public Sans** 400, 500 y 600, de 16 a 18 px, interlineado de 1,6.
- Nada de fuentes monoespaciadas ni de mayúsculas sostenidas.

## Forma
- Radio de 12 px en imágenes y tarjetas y de 10 px en botones. Sombras mínimas y suaves.
- Botón principal relleno en terracota con texto blanco. Botón secundario con borde de 1 px en tinta. Alto mínimo de 48 px.
- Separadores con línea fina de 1 px. Íconos de línea simples, solo donde aclaran.

## Página de inicio
1. Barra superior delgada y clara: «Project-roomVR» en Fraunces, 4 enlaces (Espacios, Recorrido 3D, Tarifas, Preguntas) y el botón «Reservar». En teléfono, menú compacto.
2. Hero a sangre con el render del living (ladrillo, sofá de cuero, ventanal al balcón). El título va superpuesto abajo a la izquierda, con un degradado que asegure el contraste. Lleva una bajada de una línea, el botón «Recorrer en 3D» y el enlace «Ver fechas».
3. Una sola línea de datos: 2 dormitorios · 2 baños · balcón · hasta 4 huéspedes · ≈ 54 m² construidos.
4. Espacios: galería asimétrica tipo revista (una imagen grande y dos o tres medianas), con pies de foto cortos y una frase destacada en Fraunces cursiva. En teléfono, carrusel horizontal con scroll-snap.
5. Materiales: una franja con 4 o 5 muestras reales (ladrillo, roble, hormigón, cuero y acero) y su nombre.
6. Recorrido 3D: bloque oscuro (carbón) con una captura del tour, dos o tres frases sobre cómo se usa en computador y en teléfono, y el botón «Entrar al recorrido».
7. Equipamiento en dos o tres columnas de texto, sin cajas.
8. Tarifas: tabla editorial con el precio por noche, la limpieza y el mínimo de noches, marcados como «ejemplo».
9. Preguntas frecuentes en acordeón.
10. Pie simple, con la nota «Imágenes renderizadas desde un modelo 3D · tarifas de ejemplo».

## Página de reserva
- Mismo encabezado. Título «Reserva» y una bajada: solicitud sin cobro en línea, que se confirma por correo.
- Calendario claro: dos meses en computador y uno en teléfono. Días ocupados atenuados con trama, rango elegido en terracota suave con los extremos llenos.
- Formulario: nombre, correo, teléfono y mensaje, con etiquetas visibles y foco visible.
- Resumen pegajoso a la derecha (noches, total de ejemplo, botón «Solicitar»). En teléfono, barra fija inferior con el total y el botón.

## Prohibido («AI slop»)
Numeración de secciones (01, 02…), microetiquetas monoespaciadas en mayúsculas, retículas técnicas o cotas decorativas, chips de «sitio de prueba», cajas de estadísticas, una flecha en cada enlace, emojis, degradados de moda, glassmorphism, textos de marketing vacíos («experiencia única», «sumérgete») y la palabra «loft».

## Voz
Español neutro, frases cortas y concretas. No inventar ubicación, vistas ni amenidades que no estén en el modelo.
