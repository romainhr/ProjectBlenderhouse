# Depto 2D2B: decoración industrial moderna minimalista (versión 2)

Pedido del usuario (2026-09-25): «decoración medio industrial, moderno, minimalista… puedes cambiar muebles,
texturas, todo. Si no encuentras una textura libre, la creas; si no encuentras un modelo 3D, lo creas. Quiero ver
hasta dónde llegas en modelado 3D y creación desde cero». Esta versión **crea desde cero** (por código) todas las
texturas nuevas y todos los muebles, luminarias y objetos. No se descarga nada nuevo. La versión 1 queda en
`archivo/v1_neutro/`.

## Concepto

Loft urbano contenido: materiales crudos y honestos (concreto, acero pavonado, ladrillo, roble ahumado, cuero),
líneas rectas y pocas piezas, bien elegidas. El contraste lo dan tres cosas: la calidez del roble y el cuero
coñac frente al gris del concreto; el negro mate del acero en marcos, patas y luminarias; y una sola pared de
ladrillo a la vista, la del televisor en el living. Nada de adornos gratuitos: cada objeto tiene uso o es una de
las pocas piezas de acento (dos cuadros, libros, cerámica de gres).

| Rol | Color (sRGB) | Dónde |
|---|---|---|
| Concreto claro | #9C9890 | piso de living, cocina y hall (microcemento) |
| Concreto de cielo | #B3AFA8 | cielo de concreto visto de encofrado |
| Blanco cálido | #ECEAE4 | muros |
| Ladrillo | #8C4A36 (con variación) | pared del televisor |
| Acero pavonado | #232426 | patas, marcos de muebles, luminarias, marcos de ventanas y puertas |
| Carbón | #2B2D2F | frentes de cocina |
| Roble ahumado | #6B4F3A | muebles, repisas, pisos de dormitorios (tablas) |
| Cuero coñac | #8A4B2A | sofá, cabecero del dormitorio 2 |
| Lana avena | #D8CFC0 | cojines, cabecero del dormitorio 1 |
| Acento ocre | #B8862B | sólo en cuadros y un cojín |

## Convenciones para quien modela (obligatorias)

- Blender 3.6 (bpy 3.6), headless, CPU. Determinista: toda aleatoriedad con semilla fija.
- Cada pieza es una función `nombre(col, prefijo, **parámetros) -> list[bpy.types.Object]` en su módulo de `build/`.
  Crea sus objetos en la colección `col`, con nombres `f"{prefijo}_{Parte}"` (p. ej. `Depto_Mueble_Sofa_Cojines`).
- Coordenadas locales en metros, Z arriba, **huella centrada en el origen, apoyada en z = 0, frente hacia −Y**
  (la parte de atrás, la que va contra un muro, hacia +Y). Excepciones indicadas en cada pieza (colgantes: el
  origen es el punto de anclaje en el cielo y la pieza cuelga hacia −Z; piezas murales: la cara de atrás en y = 0).
  Todos los objetos de una pieza comparten origen (0, 0, 0) y no tienen rotación: la fase 4 los mueve juntos.
- Mallas con `build/deco_base.py` (ayudas de modelado) o bmesh directo; al final `deco_base.objeto(...)`, que
  pone normales, UV de caja en metros (la escala real de las texturas la da el material) y sombreado suave.
- Materiales sólo por nombre, con `depto_geom.material(nombre)`; la lista está en `build/depto_geom.py`
  (MATERIALES) y qué textura usa cada uno en `build/deco_paleta.py`. Si falta un material, se agrega en el propio
  módulo con `depto_geom.MATERIALES.setdefault(nombre, ...)` y se informa. No editar `depto_geom.py`.
- Sin booleanos (lentos y frágiles en headless). Subdivisión sólo con `deco_base.aplicar_subdivision` y a nivel ≤ 2.
- Presupuesto: la escena entera debe quedar bajo 200 000 triángulos (`depto_geom.TOPE_TRIANGULOS`, ADR 0004, decisión 4;
  antes 150 000). Cada pieza trae su tope abajo.
- No se modelan orgánicos detallados (plantas, personas): regla de CLAUDE.md.
- Revisión: `blender -b --python-exit-code 1 --python tools/preview_pieza.py -- --modulo <módulo> --funcion <pieza>
  --out review/deco/piezas [--args '{...}'] [--texturas]` renderiza dos vistas (3/4 y lateral) en Eevee y escribe
  las medidas y los triángulos en un JSON. Mirar el render, corregir y volver a renderizar: calidad de catálogo.
- Comentarios y nombres en español; constantes con su origen (`# diseño`, `# supuesto: medida usual`).

## Texturas nuevas (todas generadas por código, repetibles sin costuras, 1024 px)

Generador: `build/deco_texturas.py` (numpy dentro de Blender). Salida en `assets/texturas/propias/<id>/` con
`<id>_diff_1k.jpg` (sRGB), `<id>_nor_gl_1k.jpg` (normal OpenGL, como glTF) y `<id>_rough_1k.jpg`, más
`assets/texturas/propias/manifest.json` (nombre, `dimensiones_m`, descripción, semilla, licencia «propia»).

| id | Tamaño real | Aspecto |
|---|---|---|
| `microcemento` | 2,0 m | gris cálido claro, nubes suaves de llana, poros finos, brillo satinado desparejo |
| `concreto_encofrado` | 2,4 m | concreto visto con marcas de tablas de 0,15 m, vetas de madera impresas, algunos poros |
| `ladrillo` | 1,2 m | aparejo soga 24 × 7 cm, junta 1 cm hundida, color por ladrillo, cantos gastados |
| `azulejo_subway` | 0,6 m | 7,5 × 15 cm blanco brillante biselado, junta gris oscura 2 mm, trabado a la mitad |
| `baldosa_hex` | 0,6 m | hexágonos de 10 cm gris carbón con variación, junta gris clara |
| `losa_hormigon` | 1,2 m | baldosas de hormigón de 60 × 60 para el balcón, juntas marcadas |
| `piso_roble` | 2,4 m | tablas de roble ahumado de 0,20 × 1,20, veta, nudos ocasionales, juntas finas |
| `roble_ahumado` | 1,2 m | veta continua de roble ahumado para muebles (sin juntas) |
| `acero_pavonado` | 0,6 m | acero negro-azulado, manchas de pavonado, rayas de cepillado |
| `cuero` | 0,4 m | cuero coñac con poro, arrugas suaves y desgaste más claro |
| `lana` | 0,25 m | tejido grueso tipo bouclé color avena |
| `yute` | 0,5 m | tejido plano de yute natural (alfombras) |
| `concreto_oscuro` | 1,0 m | concreto pulido gris oscuro para cubiertas |
| `arte_1`, `arte_2`, `arte_3` | 0,50 × 0,70 | cuadros abstractos minimalistas en la paleta (no se repiten) |

## Piezas (medidas de diseño; origen y frente según las convenciones)

### Living (`build/deco_living.py`)
- `sofa`: 1,80 × 0,90 × 0,78, asiento a 0,44; tres cojines de asiento y tres de respaldo, blandos (costuras
  insinuadas); brazos rectos de 0,15; base sobre patín de acero negro a 0,12 del suelo. Cuero. ≤ 14 000 tris.
- `cojin`: 0,45 × 0,45 × 0,14 por defecto, forma de almohada con esquinas pellizcadas; material por parámetro. ≤ 1 500.
- `mesa_centro`: Ø 0,70 × 0,40; cubierta de roble ahumado de 0,04 con canto redondeado; tres patas hairpin de varilla
  de acero de 12 mm (dos varillas por pata). ≤ 4 000.
- `rack_tv`: 1,60 × 0,35 × 0,30, mueble mural flotante de roble ahumado con perfil de acero en los cantos; dos
  puertas abatibles con buña de sombra y tirador embutido. Se construye de z = 0 a 0,30 con la espalda en y = +0,175
  (la fase 4 lo cuelga a 0,25 del suelo). ≤ 2 000.
- `tv`: 55" (1,23 × 0,03 × 0,71) pantalla negra con marco fino y soporte mural; espalda en y = 0, frente a −Y,
  base en z = 0. ≤ 600.
- `mesa_lateral`: Ø 0,40 × 0,52, marco en C de acero y cubierta circular de roble. ≤ 2 000.
- `lampara_arco`: base de concreto 0,32 × 0,32 × 0,06 centrada en el origen; tubo de acero de Ø 25 mm que sube a
  2,00 y avanza 1,50 hacia −Y en un arco; pantalla domo Ø 0,36 negra por fuera y blanca por dentro; ampolleta con
  el material emisivo. ≤ 4 000.
- `alfombra`: 2,00 × 1,40 × 0,008 por defecto, yute, cantos suavizados. ≤ 300.
- `cuadro`: lámina de 0,50 × 0,70 con `Depto_Mat_Arte1..3` y marco negro de 0,02 × 0,025; espalda en y = 0, frente
  a −Y, base del marco en z = 0; la lámina lleva UV 0-1 propia (no de caja). ≤ 300.

### Dormitorios (`build/deco_dormitorio.py`)
- `cama`: colchón de 1,80 × 2,00 (medida del brief) sobre plataforma de tubo de acero negro con seis patas
  (plataforma de 0,10 a 0,30, colchón de 0,30 a 0,55). Cabecero tapizado de 1,90 × 1,05 de alto con capitoné de
  canales verticales, en el material del parámetro `tapiz`. Espalda (cabecero) hacia +Y y pies hacia −Y; huella
  total de ≈ 1,90 × 2,10 centrada. Ropa de cama: sábana, dos almohadas grandes y dos cojines, edredón que cubre desde
  0,55 m de la cabecera y cae 0,22 por los lados y los pies con arrugas suaves (malla desplazada), y una manta doblada
  a los pies. ≤ 25 000.
- `velador`: 0,45 × 0,35 × 0,52; marco de tubo cuadrado de acero de 20 mm, cubierta y repisa baja de roble. ≤ 1 500.
- `lampara_mesa`: alto 0,42, base de disco, vástago y pantalla domo Ø 0,22 negra, con ampolleta emisiva. ≤ 2 000.
- `espejo_pie`: 0,60 × 1,70 con marco de acero negro, apoyado en el muro con 8° de inclinación; huella de 0,60 × 0,25
  con la espalda en y = +0,125. ≤ 800.

### Cocina y baños (`build/deco_cocina_bano.py`)
- `repisa_abierta`: largo por parámetro, fondo 0,25, dos niveles (0 y 0,40 sobre la base), tablas de roble de
  0,035 y ménsulas de acero negro. Mural: espalda en y = 0, la repisa avanza hacia −Y, base en z = 0. ≤ 1 500.
- `set_repisa`: objetos para una repisa de largo dado (frascos de vidrio con tapa de madera, platos apilados, bowls de
  gres, tabla de picar apoyada). Base en z = 0 sobre la tabla, frente hacia −Y, entre y = 0 y −0,25. ≤ 5 000.
- `grifo_cocina`: cuello de cisne negro de 0,40 de alto, caño que avanza 0,22 hacia −Y, palanca lateral. ≤ 2 000.
- `ducha_expuesta`: columna de tubería negra vista: mezclador a z 1,00, tubo a 2,05, brazo de 0,35 hacia −Y,
  flor de lluvia Ø 0,25, caño de tina a z 0,65. Muro en y = 0. ≤ 4 000.
- `mampara`: vidrio fijo de 8 mm de 0,80 × 1,40 con perfil negro, en el plano x ∈ [0, 0,80], y = 0, de z = 0 a
  1,40 (x = 0 contra el muro); barra estabilizadora de la esquina superior libre al muro. ≤ 1 000.
- `espejo_redondo`: Ø 0,60 con aro de acero negro; espalda en y = 0, centro en z = radio. ≤ 1 500.
- `grifo_lavabo_mural`: grifería mural de tubería vista con dos manillas en cruz; caño de 0,18; muro en y = 0,
  eje del caño en z = 0. ≤ 2 000.
- `lavabo_concreto`: vessel de 0,46 × 0,34 × 0,13, rectangular de cantos redondeados, con cubeta interior. ≤ 3 000.
- `escalera_toallas`: 0,50 × 1,60 de acero negro, apoyada con 10° de inclinación y dos toallas dobladas colgando;
  espalda en y = +0,15. ≤ 3 000.
- `portarrollo`: negro, con rollo; muro en y = 0. ≤ 800.

### Luminarias y objetos (`build/deco_objetos.py`)
- `colgante_domo`: florón en el cielo (origen, z = 0), cable de tela de `largo_cable` (0,8 por defecto) y domo de
  Ø 0,35 negro por fuera y blanco por dentro, con ampolleta Edison emisiva. Cuelga hacia −Z. ≤ 3 000.
- `colgante_jaula`: igual, con jaula de alambre y ampolleta a la vista. ≤ 3 000.
- `ampolleta_edison`: vidrio ámbar translúcido y filamento emisivo; origen en el casquillo, cuelga hacia −Z. ≤ 1 000.
- `aplique_brazo`: aplique mural de brazo articulado negro con pantalla; muro en y = 0. ≤ 2 000.
- `conducto`: tubo eléctrico visto de Ø 20 mm a lo largo de una polilínea dada (puntos locales), con curvas de radio
  0,05 y cajas de derivación en los puntos que se indiquen. ≤ 300 por tramo.
- `libros`: hilera de `n` libros de pie a lo largo de +X (o `apilados=True`, en pila), con lomos de 2 a 5 cm, alto de
  0,20 a 0,28 y cinco colores de tapa; semilla por parámetro. ≤ 150 por libro.
- `jarron` (variantes 0, 1, 2), `bol`: gres por torno, pared con espesor. ≤ 1 500 cada uno.
- `reloj_pared`: Ø 0,40, aro negro, esfera clara, marcas de hora y agujas; muro en y = 0, centro en z = radio. ≤ 1 500.

## Segunda tanda (2026-09-26): piezas nuevas, instancias y ubicación

Pedido del usuario: «seguir con el resto de las piezas y instancias». Se agregan dos módulos y se ubican las piezas
que habían quedado sin lugar. Mismas convenciones que arriba.

### Comedor y balcón (`build/deco_comedor.py`)
- `mesa_comedor`: Ø 0,80 × 0,75, pedestal de acero negro con base en cruz y cubierta de roble ahumado. ≤ 1 800.
- `silla_comedor`: silla bistró de chapa de acero estampado (genérica), asiento a 0,45, alto ≈ 0,84. ≤ 2 000.
- `mesa_bistro`: Ø 0,55 × 0,72, chapa de acero negro con borde doblado. ≤ 1 200.
- `silla_bistro`: plegable, marco de tubo negro y listones de roble, asiento a 0,45. ≤ 1 800.

### Hall, cocina y baño (`build/deco_hall.py`)
- `banca_entrada`: 0,80 × 0,32 × 0,46, roble sobre tubo cuadrado de 20 mm, repisa baja de varillas. ≤ 1 500.
- `perchero_mural`: tabla de roble con cuatro ganchos de cañería negra y repisa superior; mural. ≤ 2 000.
- `riel_focos`: riel sobrepuesto de 1,00 con tres focos cilíndricos orientables; de cielo; un objeto emisivo por
  foco (cada uno recibe su luz). ≤ 1 800.
- `felpudo`: 0,70 × 0,45 de fibra con borde de goma. ≤ 300.
- `riel_utensilios`: barra mural de 0,50 con ganchos en S y cuatro utensilios colgando. ≤ 2 000.
- `toallero_barra`: barra mural de 0,60 con toalla doblada. ≤ 1 500.

### Ubicación (fase 4)
- **Balcón**: mesa bistró y dos sillas enfrentadas en y ≈ 262 px, lejos de la hoja abierta del ventanal (norte) y
  de la cámara del balcón (sur). El punto de recorrido del balcón pasa a (85, 205).
- **Hall**: banca y perchero (0,66 y 0,60 de ancho) en el muro oeste (tabique del nicho de lavadora, 0,71 de
  largo); riel de focos en el cielo en lugar del colgante de domo, que quedaba sobre la cámara del hall y la
  encandilaba; felpudo **afuera**, en el palier, porque la hoja de entrada barre el piso del hall.
- **Cocina**: barra de utensilios bajo el mueble alto izquierdo del tramo norte (eje a 1,30). Corrección 07c: el
  tramo norte vuelve a tener muebles altos, como marca el plano, y ya no lleva `repisa_abierta` ni `set_repisa` (quedan
  en el catálogo; ADR 0004, adenda 07c).
- **Baños**: toallero de 0,40 en el frente de cada vanitorio, bajo el lavabo (eje a 0,62). Los baños no tienen un
  muro libre de 0,50 para la escalera de toallas: `escalera_toallas` queda sólo en la vitrina.
- **Dormitorio 2**: apliques de brazo sobre los dos veladores (en vez de la lámpara de mesa) y un jarrón.
- **Conductos vistos**: del colgante del living por el cielo hasta el muro de ladrillo, bajando a una caja a
  1,10; y entre los dos colgantes de la cocina, con caja de derivación al medio.
- **Sin comedor interior**: el espacio libre entre living, cocina y hall es circulación (el plano no dibuja
  comedor). Una mesa de 0,80 con dos sillas dejaba 0,6 a 0,7 m frente a la cocina o cortaba el paso del hall al
  living. La mesa y la silla de comedor quedan en la vitrina; el comedor para dos es el del balcón.
- **Camas**: `resolucion=0.7` (13 100 triángulos en vez de 20 000, sin diferencia visible) para dejar presupuesto.

### Instancias
Después de ubicar todo, la fase 4 compara la huella de cada malla (vértices, caras, aristas, suavizado, UV y
materiales) y hace que las idénticas compartan un solo datablock, como un duplicado enlazado (Alt+D). Así el
`.blend` y el glTF guardan una sola copia de cada pieza repetida: veladores, lámparas, colgantes, lavabos,
griferías, espejos, mamparas, sillas del balcón y partes iguales de las dos camas. El exportador glTF de Blender
3.6 conserva la malla compartida: 263 objetos usan 196 mallas y el binario del visor baja de ≈ 4,4 a 3,0 MB.
