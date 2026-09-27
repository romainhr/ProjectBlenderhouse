# Brief: Departamento de 2 dormitorios y 2 baños (`Depto`)

Fase 0, 2026-09-25. Fuente única: el plano de planta `ref/plano/plano_depto.png` (500×500 px, sin cotas, sin escala gráfica, sin flecha de norte). Las fotos de `ref/depto/` **no** son de este departamento y no se usaron.

- **Modelo de IA:** Claude Opus 5.5 (`claude-opus-5-5`) como director, más el workflow `depto-brief-medicion` con 8 subagentes Opus 5.5: 1 extractor de muros y vanos, 4 estimadores de escala independientes, 1 consolidador y 2 críticos adversariales.
- **Revisor humano:** Romain Ange. Compuerta de la Fase 0 aprobada el 2026-09-25 (ver al final: Decisiones de la compuerta).
- **Datos y scripts de medición:** `build/depto_medicion/` (resultado completo del workflow, extracción en px, `consolidar.py`). Constantes para las fases siguientes: `build/depto_plano.py`.
- **Evidencia visual:** `review/depto_00/plano_medido.png` (medidas sobre el plano) y `review/depto_00/overlay_extraccion.png` (muros y vanos detectados sobre el plano).

Convención de este documento: **medido** = leído en píxeles del plano (±1 px ≈ ±2 cm) y convertido con la escala; **inferido** = supuesto por norma, tipología o sentido común, sin respaldo en el plano.

## Resumen

Departamento compacto en un solo nivel, de 6,01 × 8,98 m exterior (medido). Tiene dos dormitorios en suite, cada uno con un paso entre dos closets que lleva a su baño; un living abierto a la cocina en L y al hall de acceso; y un balcón de 1,03 × 2,94 m hacia la fachada. La superficie útil es de unos 45 m² (suma de recintos) o 47 m² (entre caras de los muros perimetrales). La bruta, sin balcón, es de unos 54 m².

## Qué se ve en el plano

| Zona | Contenido (medido salvo que se indique) |
|---|---|
| Dormitorio 1 (arriba) | Cama doble con cabecera contra el muro norte y veladores. Ventana de 1,82 m en el muro de fachada. Puerta de 0,76 m desde el living, que abre hacia el dormitorio. Por un vano libre de 1,23 m se entra a un paso entre dos closets, y desde ahí a la puerta del Baño 1. |
| Baño 1 | Tina contra el muro norte, bajo una ventana de 0,60 m (la única ventana de baño). WC con estanque contra el muro este y vanitorio contra el tabique de la cocina. Shaft en la esquina sureste. Puerta de 0,70 m abisagrada al norte, abre hacia el baño. |
| Living | Rectángulo de 3,15 × 2,93 m. El ventanal ocupa todo el muro de fachada. Tiene mueble de TV contra el tabique del Dormitorio 1, alfombra, mesa de centro, sofá de dos cuerpos y pouf. No hay comedor dibujado. Hacia el este se abre a la cocina y al hall por una abertura continua de 2,75 m. |
| Ventanal y balcón | El ventanal es una corredera de dos paños **desiguales**: el norte mide 1,05 m y tiene la flecha de deslizamiento; el sur mide 1,89 m. El balcón tiene piso útil de 1,03 × 2,94 m, baldosas de 0,20 m (5 a lo largo del fondo, coincide exactamente) y una franja de baranda de dos líneas finas en tres lados. |
| Cocina | En L. El tramo norte mide 2,37 m (con anafe) y el tramo este 1,44 m (con lavaplatos y escurridor). Fondo de 0,60 m en ambos. Los muebles altos están en L (proyección con línea discontinua, fondo de 0,38 m). Junto al muro este hay dos módulos ambiguos: uno rayado con frente curvo, de 0,58 m, y otro de 0,66 m de contorno dentro de un nicho de 0,72 m, con frente discontinuo y un punto. Termina contra un tabique corto de 0,12 m que hace de retorno de la jamba de la entrada. |
| Hall de acceso | Puerta de entrada de 1,07 m de luz en el muro este. Abre hacia adentro, con la bisagra en la jamba sur. Afuera hay un triángulo que marca el acceso. Aquí está el nicho de la lavadora, de 0,71 × 0,71 m; el frente es una línea curva (tipo de cierre no determinable) y el texto del símbolo no se lee a esta resolución. |
| Dormitorio 2 (abajo) | Tiene la misma área de cama que el Dormitorio 1 (3,08 × 2,73 m), pero **no es su espejo**. La ventana mide 2,09 m (+14 %), el vano hacia el paso 1,00 m y el Baño 2 es más corto. La cama tiene la cabecera contra el muro sur. |
| Baño 2 | Tiene la misma disposición que el Baño 1, trasladada, no espejada: tina al norte, WC al centro, vanitorio al sur y puerta abisagrada al norte. **No tiene ventana**; que ventile por el shaft es inferido. |

## Patrón de escala

El plano no tiene cotas. La escala se estimó de forma independiente con cuatro familias de elementos de tamaño estándar. Ningún agente conocía las estimaciones de los demás.

| Familia | Referencias principales | m/px | Rango |
|---|---|---|---|
| Sanitarios | ancho de tina 0,70, profundidad de WC 0,70, taza 0,37, fondo de vanitorio 0,46 | 0,0192 | 0,0180 a 0,0208 |
| Puertas y muros | hojas por ajuste de circunferencia al arco de giro (error rms 0,12 px), núcleo de muro de 0,20 | 0,0188 | 0,0175 a 0,0203 |
| Cocina | fondo del mueble base 0,60 (31,55 px en ambos tramos, desviación 0,1 px) | 0,0190 | 0,0177 a 0,0204 |
| Mobiliario | cama king de 1,80 × 2,00 (la proporción dibujada, 1,08, descarta una de 2 plazas), sofá, mesa de centro | 0,0189 | 0,0180 a 0,0205 |

**Escala adoptada: 0,0190 m/px (1 m = 52,6 px), con incertidumbre total de ±5 % (0,0181 a 0,0200).** El ajuste ponderado de las 9 referencias retenidas da 0,01908 ± 0,00026, sin tensión entre ellas. Ese ±1,4 % es solo error estadístico: los bloques CAD pueden compartir un sesgo común, así que la incertidumbre real es de ±5 % mientras no haya una cota verdadera.

- Qué fija la escala: el fondo del mesón y el largo de la cama. Las puertas no resuelven la ambigüedad entre hojas de 0,70/0,65 y de 0,75/0,70, pero en ambos casos la escala se mueve menos de 1,5 %.
- Referencia que no encaja: la **puerta de entrada**. Con esta escala la hoja mide 1,03 m. Para que fuera una estándar de 0,90 m, la escala tendría que ser 0,0166, y entonces el mesón mediría 0,52 m y la cama 1,74 m. Por eso se excluyó del ajuste (ver Decisiones).
- Control por superficie: 47 m² entre caras perimetrales es el extremo bajo de un 2D2B típico. Si el departamento tuviera 55 m² útiles, la escala sería 0,0205, y el mesón y la cama quedarían fuera de estándar.

## Medidas principales (metros)

| Parámetro | Valor | Origen |
|---|---|---|
| `M_POR_PX` | 0,0190 | consolidación de 4 familias (±5 %) |
| Exterior (ancho × fondo) | 6,01 × 8,98 | medido, caras exteriores entre centros de línea |
| Muro de fachada (oeste, con balcón) | 0,25 | medido (13,0 px) |
| Muro norte | 0,24 | medido (12,7 px, incluye un forro interior de 0,05) |
| Muros sur y este | 0,20 | medido (10,5 px); el este tiene 0,24 con forro en la cocina y el Baño 1 |
| Tabiques interiores | 0,072 | medido entre centros de línea (3,8 px). De borde a borde de trazo daría 0,11: el trazo engorda. |
| Tabique corto cocina/hall | 0,12, altura completa | medido; la altura se infiere del trazo de corte negro |
| Muros de shaft | 0,084 | medido |
| Altura piso-cielo | 2,40 | **inferido** (ver Alturas) |

### Ambientes (interiores, entre caras de muro)

| Ambiente | Ancho × fondo | Área | Nota |
|---|---|---|---|
| Dormitorio 1 | 3,08 × 2,73 | 8,4 m² | + paso de 0,83 × 1,22 (1,0 m²) + closets de 0,52 y 0,39 m² |
| Dormitorio 2 | 3,08 × 2,73 | 8,4 m² | + paso de 0,87 × 1,00 (0,9 m²) + closets de 0,53 y 0,40 m² |
| Living | 3,15 × 2,93 | 9,2 m² | abierto; living + cocina + hall suman 18,2 m² |
| Cocina | 2,37 × 2,80 | 6,6 m² | límite sur virtual |
| Hall de acceso | 2,41 × 1,23 | 2,3 m² | límites norte y oeste virtuales |
| Baño 1 | 1,46 × 2,30 | 3,2 m² | descontado el shaft |
| Baño 2 | 1,46 × 2,07 | 2,7 m² | descontado el shaft |
| Nicho de lavadora | 0,71 × 0,71 | 0,5 m² | cabe una lavadora de 0,60 |
| Balcón | 1,03 × 2,94 (útil) | 3,0 m² | losa bruta de 1,18 × 3,33 = 3,9 m² |
| **Suma de recintos** | | **45,1 m²** | 47,3 m² entre caras perimetrales; rango de ±5 % de escala: 41 a 50 m² |

### Vanos

| Vano | Luz | Hoja | Tipo y giro |
|---|---|---|---|
| Puerta Dormitorio 1 y 2 | 0,76 | 0,71 (puerta de 70) | abatible; bisagra en la jamba este; abre hacia el dormitorio |
| Puerta Baño 1 y 2 | 0,70 | 0,66 (puerta de 65) | abatible; bisagra en la jamba norte; abre hacia el baño |
| Puerta de entrada | 1,07 | 1,03 | abatible hacia adentro; bisagra en la jamba sur (**conflicto**, ver Decisiones) |
| Ventanal del living | 2,94 | paños de 1,05 + 1,89 | corredera; el paño norte es la hoja móvil (por la flecha); si el sur es fijo o son dos hojas no se puede determinar |
| Ventana Dormitorio 1 | 1,82 | encuentro de hojas a 1,03 de la jamba norte | hojas desiguales (medido) |
| Ventana Dormitorio 2 | 2,09 | dos hojas iguales | |
| Ventana Baño 1 | 0,60 | | muro norte, sobre la tina |
| Vano libre Dorm. 1 → paso | 1,23 | | sin puerta; frentes de closet re-medidos en la fase 2 (CL1_N 58,76 y CL1_S 123,52 px) |
| Vano libre Dorm. 2 → paso | 1,00 | | sin puerta |
| Living → cocina y hall | 2,75 | | abertura continua |
| Frentes de closet | 0,83 (D1), 0,87 (D2) | | tipo de puerta no determinable |

## Alturas (todas inferidas: una planta no las muestra)

| Elemento | Valor | Justificación |
|---|---|---|
| Piso a cielo | 2,40 | El país no está indicado en el plano. En Chile la OGUC exige un mínimo de 2,35 m. En la región el rango va de 2,30 a 2,60 (valores de memoria, sin verificar). |
| Cielo falso en baños, hall y cocina | no se modela | es frecuente (2,20 a 2,30 para ductos), pero no hay evidencia |
| Dintel de puertas | 2,05 | hoja comercial de 2,00 más marco |
| Dintel de ventanas y ventanal | 2,10 | alineado bajo la viga |
| Antepecho de ventanas de dormitorio | 0,95 | lo usual es 0,90 a 1,00; no se puede descartar que vayan de piso a cielo |
| Ventana del baño | antepecho de 1,50 (vano de 0,60 × 0,60) | privacidad, sobre la tina |
| Baranda del balcón | 1,00 | mínimo usual de 0,95; el tipo (vidrio, metálica o maciza) no se puede determinar |
| Piso del balcón | 0,03 bajo el interior | supuesto |
| Mesón de cocina | 0,90 | estándar de 0,85 a 0,92 |
| Muebles altos de cocina | de 1,50 a 2,10 | 0,60 sobre el mesón |
| Closets | hasta el cielo | supuesto |
| Losa de piso y de cielo | 0,15 | supuesto; solo para cerrar el volumen en el tour |
| Dintel de los vanos libres hacia los pasos (VL_D1, VL_D2) | 2,05 | inferido: igual que las puertas; el plano no lo muestra |
| Abertura de 2,75 m del living hacia cocina y hall | sin dintel, hasta el cielo | el plano no dibuja viga ni dintel proyectado |
| Losa sobre el balcón | a 2,40, como el cielo interior | inferido: edificio en altura con balcones apilados |

## Mobiliario y artefactos dibujados (a escala)

| Elemento | Medida en plano | Decisión para el modelo |
|---|---|---|
| Camas | 1,84 × 1,99 | king de 1,80 × 2,00, altura de 0,55 (inferida) |
| Veladores | 0,30 a 0,34 × 0,38 (asimétricos) | veladores de 0,40 × 0,38 × 0,55 (inferido) |
| Sofá | 1,53 × 0,76 (2 cuerpos) | 1,55 × 0,80 × 0,85 |
| Mesa de centro, alfombra, mueble TV, pouf | 1,03 × 0,62 · 2,23 × 2,04 · 1,18 × 0,36 · 0,42 × 0,48 | según el plano |
| Tinas | 1,27 × 0,72 dibujadas, en un nicho de 1,46 | **decisión:** tina de 1,45 × 0,70 que llena el nicho, como se construye en obra. El bloque dibujado es genérico (inferido). |
| WC, vanitorios | 0,68 × 0,37 · 0,72 × 0,47 | según el plano |
| Anafe | 0,61 × 0,45 | 4 platos (supuesto: no se pueden contar) |
| Módulo rayado de la cocina | 0,58 × 0,57 | **inferido:** torre de horno y despensa hasta 2,10 (su borde sur tiene trazo de corte, lo que indica un elemento alto). **Corrección 07c (ronda 1), inferido:** el símbolo «<» de su frente oeste (x ≈ 383-388, y 228-258 px) se lee como dos hojas; se modela como mueble: zócalo retranqueado de 0,10/0,05, puerta bajo el horno (0,10-0,75) con una repisa, horno empotrado de 0,60 (0,75-1,35) con marco de acero, vidrio, franja de mandos y manilla de barra a 4,5 cm, y puerta de despensa (1,35-2,10) con dos repisas. Las dos puertas llevan la bisagra al sur con tope de 80° (diseño). **Corrección 07c (ronda 2), medido en plano:** el trazo del «<» va de (387; 229) a un vértice en (384,3; 241-244) y vuelve a (387; 257), con un trazo horizontal corto en y 243,5 (centroide): dos hojas de ≈0,29 m con las bisagras en los extremos norte (227,8) y sur (258,4) que se encuentran al centro (243,1; hojas iguales, 8 mm del trazo). La torre queda como **despensa de dos hojas por nivel** (junta a 1,50 m, la de los altos; tres repisas abajo y una arriba; tope de 90°, diseño) y el horno sale: con 0,544 m libres no cabe un horno empotrable comercial (nicho usual ≥ 0,56; supuesto). |
| Módulo con frente discontinuo | nicho de 0,76 (re-medido en la fase 3; se había anotado 0,72) | **Medido (corrección 07c):** contorno del refrigerador de y 261,5 a 296,0 px (0,656 m de ancho, antes 0,60 inferido) y frente en la discontinua x 386,7 (la convención de "equipo no incluido"), al ras de la torre. **Inferido:** fondo de 0,58 (del frente al forro menos 0,02 de holgura; el contorno dibujado mide 0,46 de fondo y termina 0,07 antes del forro, y se lee como el símbolo del equipo) y alto de 1,80. |
| Lavadora | nicho de 0,71 | lavadora de carga frontal de 0,60 con puerta plegable (inferido) |
| Líneas finas junto a los WC | continua en B1 (x 408,5, de la tina al shaft); discontinua en B2 (x ≈412,3, de y 369 a 445, cruzando la tina) | **B1:** repisa de instalaciones de 1,10 m que oculta el estanque (inferido). **B2 (cambio de la fase 3, confirmado en la compuerta 3):** la discontinua pasa sobre la tina, así que no puede ser una repisa baja; se lee como un elemento sobre el plano de corte: ducto o cielo falso local de 0,16 m contra el muro este, de 2,10 m al cielo (inferido). El estanque del WC del B2 queda a la vista. |

## Decisiones por defecto ante conflictos (corregibles en la compuerta)

1. **Puerta de entrada:** se modela con hoja de 1,00 m en la luz dibujada de 1,07 m (jambas de 3,6 cm). El arco del plano mide 1,03 m; se usa 1,00 por ser la medida comercial más cercana (diferencia dentro de la incertidumbre de escala). Una puerta ancha es plausible en accesos accesibles. Si en realidad es de 0,90 m, se cambia una constante (`HOJA_ENTRADA`) y el hall no se altera. *(Hasta la primera versión de la fase 3 el código usaba 1,03; se corrigió para que coincida con esta decisión.)*
2. **Tinas:** de 1,45 m, llenando el nicho, en lugar del bloque genérico de 1,27 m.
3. **Closets inferiores de ambos dormitorios:** tienen 0,46 m de fondo, poco para colgar ropa. Se modelan como closets de repisas.
4. **Dormitorio 2 y Baño 2:** se construyen con sus propias constantes. Espejar el Dormitorio 1 daría un resultado incorrecto.
5. **Espesores:** se usan centros de línea, no bordes de trazo. Los ambientes quedan entre 2 y 5 cm más grandes que si se midieran de borde a borde.

## Partes no visibles e inferidas

- Todas las alturas (tabla anterior), cielos lisos, sin vigas a la vista y sin cielo falso.
- Terminaciones y materiales: ninguna está en el plano. Propuesta neutra, sin copiar las fotos ajenas: piso laminado claro en áreas secas, cerámica en baños, cocina y balcón, muros blancos, muebles de cocina blancos con cubierta gris.
- El exterior: la fachada vista desde afuera, el pasillo común de la entrada y la vista desde las ventanas. Para el tour se propone un fondo de cielo (HDRI de Poly Haven, CC0, previa aprobación) y un piso exterior neutro, sin inventar edificios vecinos. **Reemplazado en el bloque 08** por el paisaje de la sección «Bloque 08: exterior» (pedido del usuario, ADR 0004, decisión 5).
- La orientación solar: no hay norte. Se propone luz de día entrando por la fachada del balcón.
- Iluminación artificial: un punto de luz de cielo por ambiente (supuesto).

## Convención del activo

- Colección raíz `Depto`. Prefijos: `Depto_Muro_*`, `Depto_Tabique_*`, `Depto_Shaft_*`, `Depto_Losa_*`, `Depto_Cielo_*`, `Depto_Balcon_*`, `Depto_Puerta_*`, `Depto_Ventana_*`, `Depto_Closet_*`, `Depto_Cocina_*`, `Depto_LV_*` (nicho de lavadora), `Depto_Sanitario_*`, `Depto_Palier_*`, `Depto_Piso_*`, `Depto_Mueble_*`, `Depto_Col_*` (volúmenes de colisión, en la colección `Depto_Colision`: ocultos en render y no se exportan como visibles), `Depto_Cam_*` (cámaras de revisión, no se exportan), `Depto_Ref_*` (plano de referencia, no se exporta).
- Colisión para el tour: todo lo visible colisiona, salvo lo que mida menos de 0,10 m (rieles, umbrales) y lo marcado `["colision"] = False`; lo oculto colisiona sólo si tiene `["colision"] = True`. Lo prueba `build/depto_recorrido.py` en cada corrida.
- Piezas móviles: cada hoja de puerta tiene el origen en su bisagra (`["angulo_deg"]`, `["angulo_abierta_deg"]`, giro en Z) y las manillas son hijas de la hoja. La hoja corredera del ventanal tiene `["corredera"]`, `["recorrido_m"]` y `["eje_apertura"]`. El tour puede animarlas sin tocar la geometría.
- Todas las mallas llevan UV por proyección de caja en metros de mundo (1 unidad UV = 1 m), para las texturas de la fase 5.
- Origen en el suelo (piso terminado interior, Z = 0), en el centro del rectángulo exterior sin balcón. Unidades métricas.
- **+Y hacia el frente**, que es la fachada del balcón (izquierda del plano). El plano gira -90°: el Dormitorio 1 queda hacia +X y la entrada hacia -Y. Es una rotación, no un espejo (`depto_plano.a_blender`).
- Blend maestro `build/depto.blend`. Scripts `build/depto_NN_fase.py`. Revisiones en `review/depto_NN/` (o `review/depto_NN_vK/` al repetir una compuerta: `bash build/depto_run.sh NN vK`).

## Plan de fases propuesto

| Fase | Script | Contenido | Revisión |
|---|---|---|---|
| 1 Calibración | `depto_01_calibracion.py` | Blend maestro, plano como imagen en el suelo a escala real, cámara superior ortográfica | vista superior contra plano |
| 2 Blockout | `depto_02_blockout.py` | Muros y tabiques extruidos a 2,40 con vanos (booleano EXACT o armado por tramos), losas de piso y cielo, balcón y baranda como masas | superior superpuesta al plano ±2 px; vistas a la altura de los ojos por ambiente |
| 3 Formas | `depto_03_formas.py` | Puertas con marco y hoja entreabierta, ventanas y corredera con vidrio, closets, cocina en L con muebles altos, sanitarios simples | renders por ambiente |
| 4 Mobiliario | `depto_04_mobiliario.py` | Muebles del plano como geometría simple, con presupuesto de 150k triángulos para toda la escena | renders por ambiente |
| 5 Materiales y luz | `depto_05_materiales.py` | Principled, texturas CC0 de 2K como máximo (con aprobación), luz de día y lámparas | Eevee o Cycles CPU con pocas muestras |
| 6 Tour y exportación | `depto_06_tour.py` | GLB + manifiesto, más el formato de tour que elijas (ver preguntas) | reimportar y renderizar |

## Criterios de aceptación del blockout (fase 2)

- Vista superior superpuesta al plano: caras de muro dentro de ±2 px (±4 cm) en todo el perímetro y en los tabiques.
- Exterior de 6,01 × 8,98 m dentro de ±1 %. Cada ambiente dentro de ±3 % de la tabla.
- Los 5 vanos de puerta, las 3 ventanas, el ventanal y los 4 vanos libres, en su posición y con su luz dentro de ±2 cm.
- Altura piso-cielo de 2,40. Origen, orientación y nombres según la convención.

## Preguntas para la compuerta (las de mayor impacto primero)

1. ¿Hay alguna medida real (superficie útil de un folleto, ancho de una pieza, algo medido con huincha)? Con una sola cota, la escala pasa de ±5 % a cerca de ±1 %.
2. Altura de piso a cielo: ¿2,40 está bien? ¿De qué país es el departamento?
3. ¿Qué formato de tour quieres?
4. ¿Cuánto mobiliario incluyo?
5. Puerta de entrada de 1,00 m como está dibujada, o una estándar de 0,90.

## Decisiones de la compuerta (2026-09-25, Romain Ange)

- Escala: se usa la inferida, 0,0190 m/px. No hay medida real.
- Altura de piso a cielo: 2,40 m.
- Formato del tour: recorrido web 3D en primera persona, con el GLB en una página privada de claude.ai. Antes de subir el modelo se vuelve a pedir confirmación.
- Mobiliario: amoblado según el plano (camas, veladores, sofá, mesa, alfombra, mueble de TV, cocina completa y sanitarios), con geometría simple.
- Sin comentarios sobre la puerta de entrada, las tinas ni los módulos de cocina: rigen las decisiones por defecto de este brief.

## Correcciones posteriores

- **2026-09-25, fase 2:** la cara norte del shaft del Baño 2 estaba leída 3 px (≈6 cm) al norte de su posición real. Pasa de y = 443,38 a 446,47 px, y la cara interior de 447,59 a 450,52 px. La corrección salió de la comparación de la planta renderizada con el plano (`tools/compare_plan.py`) y se confirmó con `build/depto_medicion/verificar_lineas.py` (hoy 70 caras, jambas, frentes de closet y barandas: ninguna desvía más de 1 px, salvo una cara de contacto interno sin trazo propio, excluida con su motivo). Efecto: el Baño 2 gana 0,03 m² (2,69 m²); nada más cambia.
- **2026-09-25, fase 2 (verificación adversarial):** 3 críticos independientes (geometría, recorrido y código) no refutaron la geometría: exterior, ambientes y vanos coinciden con el brief dentro del 0,6 %, y desde el hall se llega a los 11 recintos con una cámara de 0,25 m de radio. Correcciones aplicadas: extremos de la baranda sin sobrepasos en las esquinas; ejes de baranda y frentes de closet re-medidos (menos de 1 cm); cámaras de cocina y baños dentro de su recinto, más vistas de los pasos; la fase 1 guarda sólo si pasa la calibración y prueba el mapeo px→Blender; las fases se sellan (`depto_fase01`, `depto_fase02`) y la fase 2 exige el sello vigente; pipeline completo en `build/depto_run.sh`, con código de salida.
- **2026-09-25, fase 3 (verificación adversarial):** 3 críticos (ubicación contra el plano, uso y recorrido, código) confirmaron puertas, ventanas, closets, cocina, nicho LV, tinas, WC y vanitorios dentro de ±1 px en su mayoría. Correcciones aplicadas: ventanal abierto (antes el balcón quedaba inaccesible); lavaplatos (+3 px), torre (−1,2 px) y anafe re-medidos; refrigerador con 0,60 de fondo; closets correderos; manillas que entraban 5 mm en T3 y marco de entrada que entraba 4 mm en T9; ranuras y rellenadores en la esquina de la cocina; tinas sin caras superpuestas; cámaras de baño inclinadas, más dos vistas de vanitorio. En el código: cadena de sellos que se recalcula entera (`build/depto_sellos.py`, con prueba); las fases sólo escriben el maestro que abrieron; la masa de baranda pasa a ser colisión de la fase 2 (`Depto_Col_Baranda`) y la fase 3 ya no toca objetos de otra fase; UV de mundo en todas las mallas; la fase 3 prueba hojas cerradas dentro de su vano, interferencias de más de 1 mm, holgura de cámaras (≥ 0,20 m) y el paso de la corredera; `verificar_lineas.py` controla también 16 líneas de cocina y baños; `build/depto_recorrido.py` prueba que desde el hall se llega a los 10 recintos con una cámara de 0,25 m de radio.
- **2026-09-25, incidente:** a las 20:59:57, una sesión de Blender con interfaz que tenía abierto `build/depto.blend` en un estado viejo de la fase 1 lo guardó al cerrarse, y el maestro perdió el blockout. Se reconstruyó con `build/depto_run.sh`. `tools/watch_blend.py` ahora abre una copia en `/tmp/blenderhouse_watch/` y nunca el maestro.

## Decisiones de la compuerta de la fase 2 (2026-09-25, Romain Ange)

- Blockout aprobado; se pasa a la fase 3: puertas, ventanas con vidrio, closets, cocina en L y sanitarios.
- Entrada: hoja cerrada más un palier exterior neutro (piso, muros y cielo lisos), sin inventar detalles del edificio.
- Baranda del balcón: panel de vidrio de 1,00 m con pasamanos metálico.
- Texturas: descargar las 8 texturas CC0 de Poly Haven a 1K (15,0 MB) en `assets/texturas/polyhaven/`. La cubierta de cocina y los muebles blancos se hacen con materiales procedurales.

## Fase 3: decisiones y supuestos

Modelo: Claude Opus 5.5. Revisor humano: Romain Ange (compuerta 3, abajo).

- **Puertas interiores abiertas** para el recorrido: D1 y D2 a 84° (a 90° la manilla toca el tabique T3), B1 y B2 a 90° (a 84° el paso del Baño 2 quedaba en 0,53 m). La entrada queda cerrada (compuerta 2).
- **Ventanal:** corredera de dos rieles. La hoja móvil es el paño norte (flecha del plano), corrida detrás del paño fijo; deja ≈0,97 m libres hacia el balcón. En la primera versión de la fase 3 estaba cerrado y el balcón no se alcanzaba.
- **Closets:** puertas correderas en dos rieles con tiradores embutidos. El plano no dibuja arcos de giro y, con puertas abatibles, las hojas tapaban el acceso al Baño 2 (quedaban 0,15 m).
- **Baño 2:** ducto o cielo falso local contra el muro este, de 2,10 m al cielo (ver la tabla de mobiliario).
- **Cocina:** lavaplatos, torre y anafe re-medidos por centro de trazo; se habían tomado de los bordes de la extracción, con hasta 3 px (6 cm) de desvío. Supuestos: campana telescópica plana bajo el mueble alto, a ≈0,57 m sobre el anafe (los fabricantes suelen pedir 0,60 a 0,75; valor de memoria, no verificado; con los altos a 1,50 no cabe más sin subirlos). Horno con 0,545 m de frente visible, porque la torre medida mide 0,58 y no admite uno comercial de 0,595 (desde la corrección 07c, ronda 1: marco de 0,577 m al ras de las puertas de la torre y vidrio de 0,51 m). Desde la ronda 2 de la corrección 07c la torre es sólo despensa y no hay horno en el modelo (duda abierta: el sitio lo promete; podría ir bajo el anafe con un módulo base de 0,60). Rellenadores de 5 cm en la esquina de la L, dos puertas de 0,40 bajo el lavaplatos y escurridor sobre la cubierta.
- **Vanitorios:** lavamanos de apoyo con grifería alta contra el muro, y espejo de 1,15 a 1,90 (supuestos). En el B2, el plano marca la grifería hacia el frente del mueble; se deja contra el muro porque es lo físicamente coherente.
- **Nicho de lavadora:** frente plegable cerrado con un dintel de 2,05 al cielo (supuesto).
- **Palier:** 1,40 m de ancho y 1,00 m a cada lado de la puerta (supuestos; la compuerta 2 sólo pidió un "palier neutro").
- **No modelado:** las líneas finas junto a los vanitorios (¿toalleros?) y el frente curvo de la torre. Son ambiguos y se dejan para la fase 4 si se confirman. (El frente de la torre se modeló en la corrección 07c, ronda 1, como dos puertas y el horno, y en la ronda 2 como dos hojas por nivel, la lectura del símbolo: ver la tabla de mobiliario.)

## Decisiones de la compuerta de la fase 3 (2026-09-25, Romain Ange)

- Fase 3 aprobada (versión v2, `review/depto_03_v2/`); se pasa a la fase 4: mobiliario del plano.
- Baño 2: ducto o cielo falso de 0,16 m contra el muro este, de 2,10 m al cielo, con el estanque del WC a la vista.
- Closets de los pasos: puertas correderas en dos rieles.

## Fase 4: mobiliario (decisiones y supuestos)

Modelo: Claude Opus 5.5. Revisor humano: Romain Ange (compuerta 4, abajo).

- **Posiciones:** cada mueble sale de su bbox de la extracción, 0,5 px hacia adentro por lado (centro de trazo). La fase 4 lo contrasta con el plano en cada corrida: bordes a ±2,5 px como máximo (`build/depto_medicion/contraste_mobiliario.json`).
- **Medidas del brief:** camas king de 1,80 × 2,00 × 0,55, centradas en su dibujo; veladores de 0,40 × 0,38 × 0,55 (los dibujados miden de 0,30 a 0,34 de ancho, así que se contrasta el centro); sofá de 1,55 × 0,80 × 0,85, con los cojines divididos donde los dibuja el plano. Mueble de TV de 1,18 × 0,36.
- **Supuestos:** cabecero de 1,10 m; base tapizada, colchón y cubrecama; mesa de centro de 0,40 m; mueble de TV de 0,45 m con 3 puertas y una TV de 0,74 m de ancho (16:9) sobre pie; pouf de 0,42 m; alfombra de 8 mm, sobre la que apoyan los muebles del living.
- **Recorrido:** con los muebles, desde el hall se llega a los 10 recintos con una cámara de 0,20 m de radio (el radio del tour). Con 0,25 m (verificado) quedan fuera los pasos, los baños y el balcón. Los cuellos son el costado de la cama junto a la hoja abierta de D1 y D2 (0,56 m) y los pasos entre el mueble de TV, la mesa y el sofá (0,43 a 0,45 m), que son el único camino del living al ventanal.
- **Nueva vista:** `Depto_Cam_Living_Sofa`, desde junto al ventanal hacia el sofá.

## Decisiones de la compuerta de la fase 4 (2026-09-25, Romain Ange)

- Mobiliario aprobado (`review/depto_04/`); se pasa a la fase 5: materiales y luz.
- Luz del recorrido web: en tiempo real en el visor (luz de día más una por ambiente), sin hornear con Cycles.

## Fase 5: materiales y luz (decisiones y supuestos)

Modelo: Claude Opus 5.5. Revisor humano: Romain Ange (compuerta 5, abajo).

- **Acabados por cara (asignados en la fase 2):** cerámica en los muros de los baños (sólo el relieve de las juntas de `tiled_floor_001`, sobre blanco esmaltado), pintura blanca en el resto (relieve de `white_plaster_02`) y pintura exterior hacia afuera. Piso cerámico (`interior_tiles`) en los baños, la cocina y el nicho LV, y laminado (`laminate_floor_02`) en las áreas secas. El límite cocina/living sigue la cara oeste de T3 por la abertura, y el límite cocina/hall la cara norte del tabique cocina-hall (supuestos). Balcón con `patio_tiles`.
- **Madera y telas:** `oak_veneer_01` en puertas interiores, cabeceros, veladores, mesa y mueble de TV (la puerta de entrada lleva el mismo relieve con un color más oscuro). `poly_wool_herringbone` en la alfombra (con su color) y en el sofá (sólo el relieve, color gris azulado). `rough_linen` (sólo el relieve) en las sábanas, el cubrecama, la base de la cama y el pouf.
- **Cubierta de cocina:** granito gris generado por el script (`assets/texturas/procedural/granito_gris_512.png`, 0,60 m, sin costuras; hecho por nosotros, sin licencia de terceros), porque un material procedural de nodos no se exporta a glTF. Muebles blancos, metales, loza, vidrios y espejo: colores y rugosidades constantes.
- **Escala real:** cada textura se repite según `dimensiones_mm` del manifiesto (nodo Mapping, que llega al GLB como `KHR_texture_transform`). Las UV están en metros de mundo.
- **Salpicadero:** cerámica de 5 mm entre el mesón (0,90) y los muebles altos (1,50), y bajo la campana hasta su cara inferior (supuesto).
- **Luz de revisión (sólo Blender; el visor web define la suya, compuerta 4):** sol a 35° desde el lado del balcón, cielo Nishita con un suelo gris neutro bajo el horizonte (sin él, vidrios y espejos reflejaban negro) y una luz puntual por recinto a 2,05 m. Eevee con 32 muestras, AO y reflejos en pantalla. Sin sondas de luz: la luz indirecta es aproximada.
- **Exportación de prueba** (scratchpad, no publicada): 130 mallas, 35 materiales, 22 imágenes. Con el formato de imagen automático pesa 17,5 MB, porque el exportador empaqueta rugosidad y metálico en PNG; con todas las imágenes en JPEG baja a 9,8 MB. **La fase 6 exportará en JPEG** para quedar bajo el límite de 15 MB por archivo de la página publicada.

## Decisiones de la compuerta de la fase 5 (2026-09-25, Romain Ange)

- Materiales y luz aprobados (`review/depto_05/`); se pasa a la fase 6: GLB final y visor web.
- Puertas en el visor: se abren y cierran con clic (hojas sobre su bisagra y corredera del ventanal), con colisiones que siguen a la hoja.
- Antes de publicar la página se vuelve a pedir confirmación.

## Fase 6: exportación y visor web

Modelo: Claude Opus 5.5. Revisor humano: Romain Ange (confirmó la publicación privada el 2026-09-25).

- **GLB** (`exports/depto.glb`): 9,84 MB, 130 mallas, 5.292 triángulos, 35 materiales y 22 imágenes JPEG, más propiedades extra para puertas y corredera. Se reimportó en una escena vacía y coinciden las mallas, los triángulos, los materiales y las dimensiones (±1 mm) (`tools/validar_glb.py`, `review/depto_06/reimport_*.png`).
- **Colisiones del visor** (`exports/depto_colisiones.json`): 257 cajas estáticas y 6 piezas móviles (5 hojas y la corredera), en el marco XZ de glTF, para una cámara de 0,20 m de radio y la franja de 0,10 a 1,80 m. Antes de exportar se prueba lo siguiente: la transformación que usa el visor cae sobre cada pieza en Blender (±1 mm); con las puertas como en el modelo se llega a los 10 recintos; con todo cerrado quedan fuera los recintos tras una puerta; con la entrada abierta se llega al palier.
- **Manifiesto** (`exports/manifest.json`, entrada `depto`): dimensiones, triángulos, materiales, sellos de las fases 1 a 6, créditos CC0 de las texturas, escala inferida ±5 % y convención de ejes (Blender +Y = glTF −Z).
- **Visor** (`exports/depto_tour.html`): three.js 0.160 desde jsDelivr. Primera persona con teclado y ratón (y controles táctiles en teléfono); puertas y ventanal se abren y cierran con clic, y la hoja se detiene si topa con el caminante; minimapa dibujado desde los datos de colisión (no usa la imagen del plano de `ref/`) para saltar entre recintos. Luz en tiempo real (compuerta 4): luz de día, luz hemisférica, una luz por recinto tomada de Blender y reflejos de un entorno genérico. El vidrio se simplifica a transparencia, sin la pasada de transmisión, pensando en GPU integradas. Probado en local (`.claude/launch.json`, servidor estático en 127.0.0.1:8765): carga, caminata, minimapa y salto entre recintos, sin errores de consola.
- **Publicación (2026-09-25, confirmada por Romain Ange):** página privada en claude.ai, https://claude.ai/artifact/1mgoQA8NbZPmFfe4e6azeP. Las páginas publicadas no sirven `.glb`, así que el GLB viaja como `depto_glb.b64.txt` (13,1 MB en base64, que la fase 6 genera) y el visor lo decodifica. No se subió nada de `ref/`. Para actualizarla: `bash build/depto_run.sh 06` y republicar `exports/depto_tour.html` con los mismos archivos.

## Versión 2: decoración industrial moderna minimalista (en curso, 2026-09-25)

Pedido de Romain Ange: rediseñar la decoración en estilo industrial moderno minimalista, pudiendo cambiar muebles y texturas, y crear desde cero lo que no se encuentre libre. Concepto, paleta, convenciones y especificación de cada pieza y textura en `docs/deco-industrial.md`. Resumen de lo decidido:

- **Pisos:** microcemento continuo en living, cocina, hall y nicho LV; tablas de roble ahumado en dormitorios y pasos; baldosa hexagonal carbón en los baños; losas de hormigón en el balcón. El cambio de piso queda bajo la hoja de cada puerta.
- **Muros y cielo:** blancos, con una sola pared de ladrillo a la vista (la del televisor, lado living del tabique D1). Azulejo subway blanco con junta oscura en los baños y la cocina, cielo de concreto visto de encofrado.
- **Cocina:** frentes carbón mate con tiradores de barra negros, cubierta de concreto oscuro y campana de chimenea de acero (canopia a 0,64 m sobre el anafe). El tramo norte queda sin muebles altos, con repisas abiertas y azulejo hasta 2,10; los muebles altos quedan sólo en el tramo este. **Corrección 07c:** vuelven los muebles altos del tramo norte que marca el plano (discontinua ALTOS_Y), con campana telescópica integrada sobre el anafe y vajilla adentro; el azulejo llega hasta la cara inferior de los altos (1,50).
- **Carpintería:** marcos de ventanas, puertas y baranda en negro; puertas interiores de roble; puerta de entrada de acero pavonado; closets y nicho LV con frentes de roble.
- **Baños:** vanitorio de roble con cubierta de concreto, lavabo de apoyo de concreto, grifería mural de tubería vista, espejo redondo, ducha de tubería vista y mampara sobre la tina. Lavamanos, llave y espejo pasan de la fase 3 a la decoración.
- **Piezas nuevas modeladas desde cero:** ver la lista en `docs/deco-industrial.md`. Luminarias: colgantes de domo y de jaula con ampolletas Edison y conducto eléctrico a la vista; cada ampolleta lleva su luz.
- **Visor:** se corrigieron las texturas que no cargaban en la página publicada, y el modelo pasa a publicarse como glTF separado (ADR 0002, decisiones 15 y 16).
- **Para mirar en vivo:** `blender --python tools/vitrina_deco.py` (vitrina de piezas que se reconstruye sola) y `tools/watch_blend.py` (el maestro).
- **Segunda tanda (2026-09-26), pedida por Romain Ange («el resto de las piezas y instancias»):** módulos nuevos `build/deco_comedor.py` y `build/deco_hall.py`. Detalle en `docs/deco-industrial.md` (Segunda tanda) y ADR 0002, decisiones 17 a 19.
  - Balcón: mesa bistró y dos sillas plegables en el extremo sur. La cámara del balcón pasa al extremo norte, mirando hacia ellas.
  - Hall: banca y perchero de cañería en el muro oeste, y riel de tres focos en el cielo en lugar del colgante que encandilaba la cámara del hall. El felpudo va afuera, en el palier. Cámara nueva `Hall_Recibidor`.
  - Cocina: barra de utensilios bajo la repisa.
  - Baños: toallero en el frente de cada vanitorio.
  - Dormitorio 2: apliques de brazo.
  - Conductos vistos en el living y la cocina.
  - Sin comedor interior: el espacio libre es circulación.
  - Instancias: las mallas idénticas comparten un datablock, 186 objetos sobre 121 mallas en la fase 4.
  - Cama a resolución 0,7.
  - Resultado (`review/depto_06_t2`): 138 700 triángulos; GLB de 14,2 MB; web de 15,3 MB en 53 archivos; recorrido 10/10.
  - Supuesto: medidas de diseño, no medidas en el plano. Sólo las camas se contrastan con su dibujo.
- **Para mirar en vivo:** `blender --python tools/watch_blend.py -- build/depto.blend --ocultar Depto_Cielo,Depto_Palier_Cielo --material` abre una copia del maestro en Material Preview, que se recarga sola y conserva el punto de vista.
- **Publicación de la versión 2 (2026-09-26, confirmada por Romain Ange):** misma página privada, https://claude.ai/artifact/1mgoQA8NbZPmFfe4e6azeP (versión 2 del artefacto).
  - Archivos: `index.html` más los 53 de `exports/web/`: `depto_web.json`, `depto_gltf.json`, `depto_bin.b64.txt` (4,7 MB), `depto_colisiones.json` y 49 imágenes en `tex/`. Se quitó `depto_glb.b64.txt` de la versión 1.
  - Prueba previa en local con `tools/servidor_csp.py`: carga completa, texturas visibles y sin errores de consola.
  - No se subió nada de `ref/`.

## Bloque 08: exterior (2026-09-26; `build/depto_08_exterior.py`, `build/ext_texturas.py`)

Nada del exterior está en el plano: es una planta del depto. Lo medido es lo que ya usaban las fases 2 y 3: la cara
exterior de la fachada (x 114,45 px → y = 3,005 m), el balcón y los ejes de su baranda, y los vanos de la fachada y del
muro norte, con sus antepechos y dinteles, que también son supuestos del brief. Todo lo demás es inferido o de diseño.

| Elemento | Valor | Origen |
|---|---|---|
| Piso del depto sobre la calzada | 12,5 m (5.º piso de 8) | supuesto del encargo (ADR 0004, decisión 5) |
| Entrepiso | 2,55 m | derivado: 2,40 de piso a cielo + losa de 0,15 (dos supuestos del brief) |
| Planta baja del edificio propio | 4,55 m, vidriada | derivado del entrepiso y de los 12,5 m |
| Deptos por piso hacia el sur | dos, el primero en espejo | supuesto: el nuestro es el del extremo norte, porque tiene ventana en el muro norte (V_B1, medido) |
| Balcones de los otros pisos | los mismos ejes del nuestro (losa, vidrio y pasamanos) | medido en el nuestro; apilados, supuesto |
| Fondo del edificio | 13,6 m | inferido: depto de 6,01 (medido), palier de 1,40 + 0,15 y otra crujía de 6 m |
| Antejardín, vereda y calzada | 3 + 3 + 8 m; solera de 0,15 m | diseño: calle local usual |
| Reparto de la calzada de 8 m | estacionamiento de 2,0 m junto a la vereda del edificio + dos pistas de 3,0 m, con la línea central entre ellas | diseño (corrección 08, ronda 1: con autos a los dos lados quedaban pistas de 2,05 m) |
| Luminarias | seis, poste de 7 m, brazo de 1,3 m y refractor encendido de noche; a 4-4,5 m de los árboles de su vereda | diseño |
| Mancha de luz de una luminaria | foco de 90° (borde suave) a 6,9 m sobre la calzada: radio útil de ≈ 6,9 m | diseño (la misma en Blender, con focos, y en el visor, con una textura) |
| Balcones corridos del E3 y del E5 | uno por piso tipo (desde el 2.º), vuelo de 1,1 m, vidrio de 1,0 m con pasamanos y vidrio en los extremos; puertas-ventana hasta el piso | diseño |
| Calle transversal y cruce | a 14,5 m del muro norte, con pasos de cebra | diseño |
| Vecinos modelados | E1 a E7, de 1 a 11 pisos, a 15-46 m, con bahías enteras de su variante | diseño |
| Fachadas vecinas | 4 atlas propios (ladrillo, hormigón, muro cortina y estuco), 8 × 8 bahías-piso; ≈ 35 % de ventanas encendidas de noche | diseño; texturas generadas por código |
| Barrio intermedio | manzanas de 60 m con calles de 14 m, a 45-150 m | diseño |
| Árboles de calle | 21, de 7-9 m, fuste de 2,4-3,2 m, copa de icosaedro subdividido | diseño (estilizados, no orgánicos detallados) |
| Siluetas lejanas | 16 tarjetas en dos capas, a 170-215 y 280-340 m, de 10-52 m de alto | diseño |
| Giro del cielo | 149,3° | medido: lleva el sol del HDR de día al sol de la fase 5 |

La vista libre desde las ventanas propias, con un abanico de rayos de ±40° y de −35° a +20°, llega a 16,3 m. Ése es el
primer choque con el exterior. Presupuesto: 9 632 triángulos de exterior (tope del bloque, 15 000) y 198 110 en la
escena (tope, 200 000), después de la corrección 08 (ronda 1; antes, 9 424 y 197 902).

La luz de los tres momentos sale de los panoramas (medido en los HDR, fase 08): el sol de día a 48,0° de elevación, el
de la tarde a 12,1° y la luna a 17,1°, con el azimut alineado por el giro. Los renders de revisión y el visor orientan
el sol del depto con esa elevación en cada momento; la fase 5 sigue con su sol de 35° para los demás renders.

