# Brief: Mesa auxiliar redonda de tres patas (`Mesa`)

Fase 0 escrita por el director (Claude Fable 5.1) a partir de 3 fotos del usuario del 2026-09-25. Las fotos aún no están en `ref/`; medidas marcadas como **estimadas** hasta que el usuario confirme con cinta métrica.

## Qué se ve en las fotos

| Foto | Vista | Contenido |
|---|---|---|
| 1 | cenital, ligeramente en perspectiva | tapa circular de madera maciza color miel (tipo roble/lenga), veta longitudinal, tablas encoladas; se asoman dos patas por debajo |
| 2 | mesa invertida, vista lateral-inferior | tapa con canto redondeado y grosor uniforme; **bloque central hexagonal** de madera (más oscuro) atornillado bajo la tapa; **3 patas redondas cónicas** que salen de tres caras alternas del bloque, con 2 tornillos visibles en una cara; patas abiertas hacia afuera |
| 3 | 3/4 de pie, en habitación | proporciones generales: la mesa es casi tan alta como ancha; patas rectas, inclinadas hacia afuera, adelgazan hacia el pie |

## Patrón de escala

No hay referencia métrica exacta. Se usa la tipología (mesa auxiliar/lateral de estilo nórdico) y las lamas del piso (≈ 19 cm de ancho, típico de piso flotante): en la foto 1 la tapa abarca ≈ 3,2 lamas → **Ø ≈ 60 cm**. Incertidumbre ±6 cm.

## Parámetros (metros)

| Parámetro | Valor | Origen |
|---|---|---|
| `DIAMETRO_TAPA` | 0.60 | foto 1 vs. lamas del piso (estimado ±0.06) |
| `GROSOR_TAPA` | 0.025 | foto 2: canto ≈ 3,6 % del diámetro (estimado ±0.005) |
| `RADIO_CANTO_TAPA` | 0.005 | foto 2: canto suavemente redondeado, no chaflán |
| `ALTURA_TOTAL` | 0.56 | foto 3: alto ≈ 0,93 × diámetro (estimado ±0.05) |
| `HUB_ANCHO` (entre caras del hexágono) | 0.16 | foto 2, re-medido tras la ronda 1: ≈ 30 % del diámetro aparente (estimado ±0.02) |
| `HUB_ALTO` | 0.07 | foto 2, re-medido: ≈ 3 × el grosor de la tapa (estimado ±0.01) |
| `HUB_LADOS` | 6 | foto 2: bloque hexagonal; las patas entran por la **cara inferior** del bloque (espiga en agujero inclinado), cerca de caras alternas (cada 120°) |
| `PATA_DIAM_ARRIBA` | 0.036 | foto 2: ≈ 6 % del diámetro |
| `PATA_DIAM_ABAJO` | 0.022 | foto 2 y 3: pie más fino que la base, cono continuo |
| `PATA_ANGULO_APERTURA` | 15° respecto a la vertical | foto 3: radio de los pies ≈ 0,20 m vs. radio de anclaje ≈ 0,06 m (estimado ±3°) |
| `PATA_LARGO` | ≈ 0.53 | derivado: (altura total − grosor tapa − parte del hub) / cos(15°) |
| `RADIO_PIES` | ≈ 0.20 | derivado de lo anterior |
| `N_PATAS` | 3 | fotos 2 y 3 |
| `TORNILLOS_POR_CARA` | 2, apilados uno sobre otro, centrados en la cara, eje horizontal, Ø 4 mm | foto 2 (fijan la espiga de la pata desde la cara) |

## Materiales

- Tapa y patas: madera clara color miel, veta marcada, acabado satinado (roughness ≈ 0,45). Color base aprox. sRGB (0.72, 0.50, 0.28).
- Hub: madera más oscura/rojiza (0.45, 0.28, 0.18).
- Tornillos: acero (metallic 1, roughness 0.4).

## Partes inferidas (no visibles)

- Cómo se fija el hub a la tapa: se asume atornillado por debajo, sin herrajes visibles desde arriba.
- Sección de las patas en el anclaje: se asume que la pata se inserta/atornilla contra la cara plana del hub con su eje pasando por el centro del hub.
- Base de las patas: corte plano perpendicular al eje de la pata (se ve así en foto 2).

## Criterios de aceptación del blockout (fase 2)

- Tres patas equidistantes a 120°, cónicas, inclinadas 15° hacia afuera, sin atravesar la tapa ni el hub.
- Altura total y diámetro dentro de ±5 % de los valores del brief.
- Hub hexagonal centrado bajo la tapa, con las patas saliendo de caras alternas.
- Origen del activo en el suelo, centrado; +Z arriba; colección raíz `Mesa`.
