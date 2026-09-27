# Contrato de interacción: modelo (Blender) ↔ visor web

Versión 2.5 (2026-09-27; secciones 2, 3 y 5 completadas en la fase 07b; `depende_de`/`bloquea`, color por
temperatura y regla del momento del día agregados en la corrección 07b, ADR 0004; `enciende`, grupos de móvil,
`alcance_m` y entornos locales, sección 6, en la ronda 2 de la corrección 07c; exterior con un panorama por momento,
emisión y materiales de fondo, sección 4, en el bloque 08; vidrio y mancha de luz del exterior, sección 4, y uso de la
escala del entorno local, sección 6, en la ronda 1 de la corrección 08; sol de cada panorama, cielos en pantalla con
la curva Filmic y vidrio uniforme, sección 4, en la ronda 2 de la corrección 08). El JSON trae `"version": 2`
(versión mayor: un visor que la entiende puede leer cualquier 2.x e ignorar lo que no conoce) y `"contrato": "2.5"`
(versión completa; `"2.4"` en la ronda 1 de la corrección 08, `"2.3"` en el bloque 08, `"2.2"` en la ronda 2 de la
corrección 07c y `"2.1"` desde la ronda 2 de la corrección 07b hasta la ronda 1 de la 07c). Lo produce `build/depto_06_exportar.py` en `depto_colisiones.json` y en los `extras` de los nodos glTF (three.js los deja en `object.userData`). Coordenadas en glTF: +Y arriba, frente del depto hacia −Z (Blender (x, y, z) → glTF (x, z, −y); `gl()` en depto_06).

## 1. Móviles (`moviles[]`, ya existe, se amplía)

Cualquier objeto con la propiedad `puerta` (bisagra) o `recorrido_m` (corredera) en Blender se exporta como móvil. Campos existentes: `nodo`, `cajas_locales`, `posicion`, `tipo` (`bisagra` | `corredera`), `angulo`, `angulo_abierto`, `eje`, `recorrido`, `abierta`, `hijos`.

Campos nuevos (propiedades de Blender con el mismo nombre, se copian tal cual):

| Campo | Tipo | Uso |
|---|---|---|
| `clase` | `puerta` \| `ventana` \| `cajon` \| `closet` \| `nevera` \| `mueble` | Icono y texto de la pista; los `cajon` no bloquean el recorrido en las pruebas. |
| `etiqueta` | texto corto en español | Pista del visor: "Abrir cajón de cubiertos". |
| `recinto` | nombre de `recintos` | Para la lista de la interfaz y para apagar la pista fuera del recinto. |
| `depende_de` | lista de `nodo` (opcional) | Hojas que deben estar corridas para abrir la pieza (cajones de clóset: su hoja A). |
| `bloquea` | lista de `nodo` (opcional) | Piezas que la hoja tapa al moverse (cada hoja de un clóset de repisas: sus cajones; `PuertaLavaplatos1`: `Cajon3Sup` y `Cajon3Inf`, que su canto cruza al girar). |
| `enciende` | lista de `id` de `grupos_luz` (opcional, 2.2) | Grupos que se prenden mientras la pieza está abierta y se apagan al cerrarla (la puerta de la nevera: `cocina_nevera`). |

Reglas del modelo:
- El origen del objeto es el eje de giro (bisagra) o el punto de reposo (corredera). El giro de bisagra es en torno a +Z de Blender (+Y de glTF).
- El contenido que debe moverse con la pieza (manilla, ropa en un cajón, estantes de la puerta de la nevera) se emparenta al objeto móvil y aparece en `hijos`.
- Un cajón es una caja abierta arriba (frente + fondo + laterales + piso), no un bloque macizo, para que se vea su interior al abrirse.
- Corrección 07c: todos los cajones y puertas de mueble nacen cerrados (`abierta: false`). En las hojas de mueble y de
  la nevera el eje de giro va en la arista de la cara vista (la que mira hacia donde abre), como una bisagra de
  cazoleta, y la hoja cuelga de un costado, divisor o montante del mueble. La bisagra va del lado libre cuando se
  puede; si del lado de la bisagra hay muro, torre o esquina, se agrega un rellenador (`ALTOS_RELLENO`,
  `RELLENO_ESQUINA`) o se limita el ángulo (`ANGULO_MUEBLE_TORRE`, `ANGULO_TORRE`), y `prueba_aperturas` lo verifica.
  Excepciones con nombre (corrección 07c, rondas 1 y 2): `PuertaAltaN1` (bisagra del lado de T3, detrás del
  rellenador), `PuertaAltaE3` (junto a la torre, tope a 80°: comparte la junta con la hoja alta norte de la torre),
  `PuertaLavaplatos2` (junto a la torre, tope a 90°: comparte la junta con la hoja baja norte de la torre) y las cuatro
  hojas de la torre, `PuertaTorre{Baja,Alta}{N,S}` (dos por nivel, con las bisagras en los extremos norte y sur como el
  símbolo «<» del plano, tope a 90°; hasta la ronda 1, `PuertaTorreBaja` y `PuertaDespensa`, una hoja por nivel con la
  bisagra al sur). La fase 6 prueba que ninguna hoja ni cajón, abierto en el estado que permite este contrato (con las
  hojas de su `depende_de` corridas y las demás como en el modelo), entre más de 1 mm en una caja estática o en otro
  móvil; que dos hojas de mueble, o una hoja y un cajón del mismo recinto, abiertos a la vez no se crucen, y que
  tampoco se crucen **mientras se mueven**: cada pieza se lleva de cerrada a abierta cada 2° (hojas) o cada 2 cm
  (cajones y correderas) contra los demás móviles de su recinto, abiertos y cerrados, salvo los estados que el visor no
  permite durante ese movimiento (lo que la pieza nombra en `bloquea`, cerrado; lo de su `depende_de`, abierto)
  (`prueba_aperturas` y `prueba_giros` en `build/depto_06_exportar.py`). Hasta la ronda 1 sólo se probaban los estados
  finales, y `PuertaLavaplatos1` cruzaba 18 mm el frente de `Cajon3Sup` abierto entre 11° y 60° de su giro.
- Cajones detrás de correderas (corrección 07b): un móvil con `depende_de` sólo se abre si esas hojas están corridas
  del todo y cualquier otra hoja que lo nombre en `bloquea` está cerrada (en un clóset de dos hojas, la B corrida tapa
  la columna de cajones). Antes de mover una hoja con `bloquea`, el visor cierra los cajones abiertos que tapa y la
  hoja espera a que terminen (`web/src/tour/js/bloqueos.js`). En Blender son propiedades de texto separadas por
  comas; la fase 6 las exporta como listas y prueba que nombren móviles exportados y sean recíprocas.

## 2. Luces (`luces[]` y `grupos_luz[]`)

Cada luz puntual trae además `grupo` (id de `grupos_luz`), `color` [r, g, b] lineal y `ampolleta` (nombre del nodo emisivo que la representa).

```json
"grupos_luz": [
  {"id": "living_techo", "etiqueta": "Living · techo", "recinto": "Living", "encendido": true, "kelvin": 2700},
  {"id": "dorm1_velador_izq", "etiqueta": "Dormitorio principal · velador izquierdo", "recinto": "Dorm1", "encendido": false, "kelvin": 2700},
  {"id": "cocina_nevera", "etiqueta": "Cocina · luz de la nevera", "recinto": "Cocina", "encendido": false, "kelvin": 5000, "movil": "Depto_Mueble_Nevera_Puerta"}
]
```

- `movil` (2.2, opcional): el grupo no tiene interruptor ni lámpara; lo prende el móvil nombrado mientras está abierto
  (su `enciende`, sección 1). Nace apagado, no cambia con el momento del día y el panel de luces del visor no lo
  muestra (`gruposDelPanel`, `estadoGruposParaMomento` y `gruposDeMovil` en `web/src/tour/js/luces.js`).
- `alcance_m` (2.2, opcional, en `luces[]`): distancia a la que el visor corta la luz (`distance` de three.js; si
  falta, 7 m). La luz de la nevera trae 0,9 m: el visor no calcula sombras y, sin límite, alumbraba la cocina a través
  del cuerpo de la nevera.

- `color` es sRGB **lineal** (primarias Rec. 709, blanco D65, canal mayor = 1) y sale de `kelvin`
  (`build/depto_color.py`: radiancia de Planck contra CIE 1931; calculado, no medido): 2700 K ≈ [1.0, 0.42, 0.10] y
  3000 K ≈ [1.0, 0.48, 0.15]. Hasta la corrección 07b se escribía [1.0, 0.72, 0.42], que es el sRGB codificado de
  ~3000 K: usado como lineal daba ~4200 K.
- 2700 K en general; cocina y baños a 3000 K; la luz interior de la nevera, 5000 K (LED usual; ronda 2 de la 07c).
- Luces con pantalla (domos de techo, lámpara de arco, colgante del balcón, focos de los rieles y los tramos de la
  luz lineal bajo los altos de la cocina): `cono_deg` (semiángulo, 60° en domos y en la luz lineal, 35° en focos) y
  `direccion` (vector glTF del eje; hacia abajo en los domos y en la luz lineal). El
  visor, que no calcula sombras, las arma como un foco (SpotLight) con toda la intensidad; sin eso el cielo sobre un
  domo cerrado recibía ~20 veces la luz del piso. Hasta la ronda 2 de la corrección 07b llevaban además una puntual
  con el 15 % para el rebote en el cielo: se quitó porque cada luz cuesta ~1,3-1,7 ms por cuadro en una GPU
  integrada (ADR 0004, adenda de la ronda 2). Las jaulas, los veladores y los apliques no traen cono. En Blender
  todas son puntuales (la pantalla hace la sombra), salvo la luz lineal bajo los altos de la cocina, que desde la
  ronda 2 de la corrección 07c es un foco (SPOT) de 2 × `cono_deg` hacia abajo, como en el visor: puntual, a 8,5 mm
  bajo el piso de los altos, emitía también hacia arriba y quemaba los platos de N1.
- El visor clona el material emisivo de cada `ampolleta` para que cada grupo se apague por separado, y dibuja las
  ampolletas como nodos sueltos (fuera de la fusión estática).
- **Momento del día:** al aplicar un momento, cada grupo queda encendido sólo si el momento prende las luces
  (tarde, noche) y el grupo nace con `encendido: true`; el día apaga todos. El visor guarda el valor de autor en
  `encendidoInicial` (`estadoGruposParaMomento` en `web/src/tour/js/luces.js`): los veladores, apliques y la lámpara
  de pie sólo se prenden a mano. Lo que el usuario cambió a mano vuelve a este estado al cambiar de momento.

Grupos que exporta el modelo (fase 07b; `GRUPOS_LUZ` en `build/depto_04_mobiliario.py`, que también los guarda en
la escena para las fases 5 y 6). `encendido` es el estado con que nace el grupo: `true` para las luces de techo,
`false` para veladores, apliques y la lámpara de pie. Izquierda y derecha de los veladores: mirando la cabecera
desde los pies de la cama.

| id | luminaria | recinto | color | encendido |
|---|---|---|---|---|
| `living_techo` | colgante de domo | Living | 2700 K | sí |
| `living_lampara_pie` | lámpara de arco | Living | 2700 K | no |
| `cocina_techo` | riel de 3 focos y luz lineal bajo los muebles altos (3 tramos); hasta la corrección 07c, 2 colgantes de jaula | Cocina | 3000 K | sí |
| `hall_techo` | riel de 3 focos | Hall | 2700 K | sí |
| `dorm1_techo` | colgante de domo | Dorm1 | 2700 K | sí |
| `dorm1_velador_izq`, `dorm1_velador_der` | lámparas de mesa (veladores oeste y este; hasta la ronda 2 de la corrección 07b había una sola, `dorm1_velador`) | Dorm1 | 2700 K | no |
| `paso_d1` | colgante de jaula de cable corto (nuevo en 07b) | Paso_D1 | 2700 K | sí |
| `dorm2_techo` | colgante de domo | Dorm2 | 2700 K | sí |
| `dorm2_aplique_izq`, `dorm2_aplique_der` | apliques de brazo (este y oeste) | Dorm2 | 2700 K | no |
| `paso_d2` | colgante de jaula de cable corto (nuevo en 07b) | Paso_D2 | 2700 K | sí |
| `bano1`, `bano2` | colgante de jaula | Bano1, Bano2 | 3000 K | sí |
| `balcon` | colgante de domo Ø 0,28 sobre la mesa bistró, bajo la losa del balcón de arriba (nuevo en 07b) | Balcon | 2700 K | sí |
| `cocina_nevera` | luz interior de la nevera (difusor en el techo, 4 W; nuevo en la ronda 2 de la 07c): la prende la puerta al abrirse (`movil`) | Cocina | 5000 K | no |

La etiqueta de cada grupo empieza con el nombre del recinto de `recintos_etiquetas` ("Dormitorio principal ·
techo"); la fase 4 lo prueba.

## 3. Interruptores y objetos que prenden luces

Propiedad de Blender `grupo_luz` (texto o lista separada por comas) en cualquier objeto clicable:
- Placas de interruptor en el muro (`Depto_Interruptor_<Recinto>[_n]`, a 1,10 m del piso y 0,10 m del marco de la puerta, del lado de la manilla). Su tecla (`..._Tecla`) es hija y el visor la inclina ±8° al cambiar de estado.
- Lámparas de pie o de velador: la propiedad va en el objeto de la pantalla o del cuerpo.

Se exporta como `interruptores: [{"nodo", "grupos": [...], "tecla": nombre o null}]`. Los `extras` del nodo repiten `grupo_luz` para que el raycast lo reconozca sin buscar en la lista.

Detalle (fase 07b):
- Placa de 0,08 × 0,12 × 0,012 m de acero negro mate con dos tornillos pavonados; teclas de balancín de latón
  envejecido. Centro a 1,10 m, canto a 0,10 m del marco, del lado de la manilla y dentro del recinto. Sin colisión
  (`colision: false`): 12 mm de muro no deben angostar los pasos del recorrido.
- Teclas hijas de la placa, sin giro propio y con el origen en su eje de giro (horizontal, paralelo al muro, sobre
  la cara de la placa: traslación local glTF (x, 0, 0,012), o (x, 0, 0,042) sobre las cajas de superficie del
  living y del balcón): el visor las inclina con `rotation.x`. La espalda de la tecla entra 4,5 mm en la placa, así que al
  inclinarse ±8° no queda rendija.
- `recinto` de placas y teclas: el recinto donde está la placa, que puede no ser el de sus grupos (la placa del
  balcón está en el living).
- Pista del visor: «Encender»/«Apagar» más la etiqueta del grupo («Encender Living · techo»); la placa doble une
  las dos etiquetas con «y». Nombres: `<placa>_Tecla` (placa simple) o
  `<placa>_1_Tecla` y `<placa>_2_Tecla` (placa doble, de izquierda a derecha mirando la placa).
- Registros: uno por placa (`grupos` = los de todas sus teclas; `tecla` = la suya si es simple, `null` si es
  doble), uno por tecla (`nodo` = `tecla` = la tecla, `grupos` = el suyo) y uno por pieza clicable de lámpara
  (`tecla: null`). El visor registra primero las teclas (cada una manda sólo su grupo) y deja la tecla colgando de
  su placa.
- El estado de un interruptor sale de sus grupos (encendido si alguno lo está), no de un estado propio: varios
  nodos mandan el mismo grupo (tecla y placa, pantalla y cuerpo de una lámpara, los dos puntos de encendido del
  balcón) y los grupos de techo nacen encendidos.

| placa | teclas (izquierda → derecha) | dónde |
|---|---|---|
| `Depto_Interruptor_Hall` | `hall_techo` | tabique cocina/hall, junto a la jamba norte de la entrada |
| `Depto_Interruptor_Cocina` | `cocina_techo` | cara este del remate del tabique T3, sobre el extremo de la cubierta, a 0,10 m del remate (entrada desde el living; la cocina no tiene puerta). Hasta la corrección 07b iba en el canto del tabique cocina/hall, donde la puerta abierta de la nevera la tapaba |
| `Depto_Interruptor_Living` | `living_techo`, `balcon` | muro de ladrillo junto a la puerta D1, sobre una caja de superficie de 0,03 m donde entra el conducto visto; el comedor para dos es el del balcón (`docs/deco-industrial.md`) |
| `Depto_Interruptor_Balcon` | `balcon` | por dentro, muro de ladrillo junto a la hoja móvil del ventanal, con el canto a 0,10 m de la arista del vano (hasta la ronda 2 se medía desde el marco, retranqueado 7,4 cm, y quedaba a 2,6 cm de la arista); sobre caja de superficie de 0,03 m, con el conducto visto que viene de la derivación en T del living; `recinto` = `Living` (donde está la placa) |
| `Depto_Interruptor_Dorm1` | `dorm1_techo`, `paso_d1` | dentro del dormitorio, espalda con espalda con la del living |
| `Depto_Interruptor_Dorm2` | `dorm2_techo`, `paso_d2` | dentro del dormitorio |
| `Depto_Interruptor_Bano1`, `_Bano2` | `bano1`, `bano2` | dentro del baño, en el tabique de la puerta |

Lámparas clicables: `Depto_Mueble_Living_LamparaArco_{Tubo,Pantalla}`, `Depto_Mueble_D1_LamparaMesa{O,E}_{Cuerpo,Pantalla}`
y `Depto_Mueble_D2_Aplique{O,E}_{Metal,Pantalla}`.

## 4. Exterior (2.3, bloque 08; 2.4, corrección 08, ronda 1; 2.5, ronda 2)

```json
"exterior": {
  "panoramas": {"dia": "tex/cielo_dia.jpg", "tarde": "tex/cielo_tarde.jpg", "noche": "tex/cielo_noche.jpg"},
  "panoramas_intensidad": {"dia": 1.0, "tarde": 1.0},
  "rotacion_deg": 149.3, "suelo_y": -12.5, "emision": {"dia": 0.0, "tarde": 0.35, "noche": 1.0},
  "sol": {"dia": {"azimut_deg": 115.0, "elevacion_deg": 48.0, "hacia_gl": [-0.2828, 0.7431, -0.6064]},
          "tarde": {"azimut_deg": 116.8, "elevacion_deg": 12.1, "hacia_gl": [-0.4409, 0.2096, -0.8728]},
          "noche": {"azimut_deg": 113.6, "elevacion_deg": 17.1, "hacia_gl": [-0.3827, 0.294, -0.8759]}},
  "cielos": {"dia": "kloofendal_48d_partly_cloudy_puresky", "tarde": "qwantani_dusk_2_puresky",
             "noche": "kloppenheim_02_puresky"},
  "nota": "..."
}
```

- `panoramas`: un equirectangular por momento de 2048 × 1024, con la ruta relativa a la carpeta `modelo/` del visor.
  `web/tour_modelo.py` los lleva a `modelo/tex/` tal cual, sin gemela `.webp` ni copia en `tex_movil/`. Hasta la 2.2 el
  campo era un único `panorama`, que el visor sigue aceptando. Desde la 2.5, los que figuran en `panoramas_intensidad`
  (día y tarde) están ya en pantalla: la fase 6 los hornea desde el HDR 1k de Poly Haven (CC0) por la fuerza del cielo
  que ve la cámara en los renders de revisión (`cielo_camara` de la fase 08: día 1,6, tarde 0,32), con la vista Filmic
  sin look de Blender, y toma el detalle de las nubes del JPG de 2048 de Poly Haven (multiplicado por la razón Filmic /
  JPG suavizada). El visor los dibuja con esa intensidad (1) y sin otra curva: three r160 no aplica tone mapping a un
  fondo sRGB. Antes el JPG de Poly Haven traía su propio tono (de día más azul y de tarde más rosado que los renders).
  El de noche sigue siendo el JPG de Poly Haven, copiado tal cual, con la intensidad de fondo del visor
  (`MOMENTOS.noche.fondoIntensidad`).
- `sol` (2.5): el sol de cada panorama (la luna de noche), el píxel más brillante del HDR que mide la fase 08, con el
  azimut ya girado `rotacion_deg`: `azimut_deg` en la convención de Blender (desde +X hacia +Y, antihorario visto desde
  arriba), `elevacion_deg` y `hacia_gl`, el vector unitario hacia él en glTF. Es el mismo que usan los renders de
  revisión (`tools/render_08.py`, `orientar_sol`). El visor lo usa para el sol del depto y para el sombreado del
  exterior; `MOMENTOS[].sol.elevacion` de `cielo.js` queda como respaldo de un modelo sin `sol`, y una prueba exige que
  coincida con el JSON exportado.
- `rotacion_deg`: giro de los tres panoramas alrededor de +Y de glTF (+Z de Blender), antihorario visto desde arriba.
  Con la convención común de Blender y de three.js (el centro de la imagen mira hacia +X y u = 0,5 − azimut / 360), el
  píxel u del panorama girado es el u + rotacion_deg / 360 del original. La fase 08 lo mide: lleva el sol del HDR de día
  (el píxel más brillante, azimut −34,3°) al sol de la escena de la fase 5 (115,0°). Los otros dos HDR tienen el sol, o
  la luna, a menos de 4° de ése. En Blender es un nodo Mapping que gira −θ la dirección de consulta
  (`tools/render_08.py`); three r160 no tiene `scene.backgroundRotation`, así que el visor gira la imagen en un canvas
  (`prepararPanorama` en `web/src/tour/js/exterior.js`).
- `suelo_y`: altura de la calzada en glTF (m). Es un supuesto: el piso del depto queda a 12,5 m sobre la calle.
- `emision`: fuerza de la emisión del exterior por momento. El glTF trae la de noche: ventanas encendidas de los
  vecinos y del edificio propio, locales y luminarias. En el maestro queda en 0, para los renders de día, y la fase 6
  la sube a su valor de noche sólo mientras exporta.
- Materiales de fondo: todo material `Depto_Ext_Mat_*` trae en sus `extras` `exterior: true` y `exterior_capa`, con
  `"cerca"` o `"lejos"` (las siluetas lejanas). Los nodos `Depto_Ext_*` traen `exterior: true` y `colision: false`: no
  entran en `estaticos`. El visor (`prepararExterior` en `carga.js`) los pasa a `MeshBasicMaterial`, que no recibe
  luces puntuales, sol ni entorno. Les calcula al cargar un sombreado por vértice con el sol de `luces[]` y
  `suelo_y`, y los fusiona por material en un grupo aparte (`Depto_Exterior`), fuera del raycast del piso. Por momento
  les aplica el tinte, la emisión y la bruma de las siluetas con el color del horizonte del panorama
  (`MOMENTOS[].exterior` en `cielo.js`).
- Vidrio (2.4): los materiales con vidrio a la vista (`Depto_Ext_Mat_FachadaC`, el muro cortina, y
  `Depto_Ext_Mat_VentanasPropias`) traen en los extras `exterior_vidrio = {reflectividad, rugosidad_vidrio,
  rugosidad_marco}` y un `metallicRoughnessTexture` cuyo canal G separa el vidrio (`rugosidad_vidrio`) del marco y el
  muro (`rugosidad_marco`). El visor les pone como `envMap` el panorama del momento, con la máscara
  (rugosidad_marco − G) / (rugosidad_marco − rugosidad_vidrio) y `reflectividad`; sigue sin luces. Desde la 2.5 el
  reflejo se suma al difuso (`AddOperation`, como el especular del Principled de Blender) y el mapa trae valores
  intermedios: la enjuta del muro cortina a 0,35 y las cortinas y persianas detrás del vidrio a 0,45. El vidrio de las
  barandas (`Depto_Ext_Mat_VidrioBaranda`) trae `exterior_vidrio = {reflectividad, uniforme: true}` sin mapa: todo el
  paño refleja parejo y no lleva sombreado por vértice. Lo transparente del exterior se dibuja con
  α' = 1 − (1 − α)^1,35 (`opacidadVisor`): three.js mezcla sobre el lienzo ya codificado en sRGB y Blender en lineal.
- Mancha de luz (2.4): `Depto_Ext_Mat_LuzSuelo` trae `exterior_aditivo: true`, alfa 0 (en Blender no se ve: los renders
  de revisión alumbran la calle con un foco por luminaria) y la mancha en su `emissiveTexture` (mitad izquierda para el
  asfalto y el pasto, derecha para la vereda, que refleja más). El visor la suma al cuadro con mezcla aditiva,
  escalada por `emision` del momento: de día no se dibuja.
- El sombreado por vértice se rehace al cambiar de momento con el sol de su panorama (`sol[momento]`; en un modelo 2.4,
  la elevación de `cielo.js` con el azimut del sol de `luces[]`), y la curva de tono de los materiales de fondo es
  la Filmic de Blender (`web/src/tour/js/filmic.js`, medida con `tools/curva_filmic.py`), la de los renders de
  revisión, en lugar del ACES del resto del visor. La bruma de las siluetas va hacia el horizonte del panorama tal
  como se dibuja (su color lineal por la intensidad del fondo; hasta la 2.4 se le aplicaba ACES, que el fondo no lleva).
- La franja del depto en la fachada (5.º piso de la columna 0, de −0,15 a 2,55 m) lleva desde la 2.5 una piel exterior
  del edificio (`Depto_Ext_Edificio_Fachada`, material `Depto_Ext_Mat_FachadaPropia`) a 1 cm de los muros propios, con
  los vanos medidos recortados: el visor la dibuja con el mismo material y sombreado que el resto de la fachada, y los
  muros del depto (`Depto_Mat_MuroExterior`) quedan detrás.
- En Blender, los renders de revisión del exterior usan los HDR 1k equivalentes como mundo, con el mismo giro, y el sol
  de la escena orientado hacia el sol medido en el HDR de cada momento (`tools/render_08.py`).

## 5. Recintos

`recintos` sigue siendo `{nombre: [x, z]}`. Se agrega `recintos_etiquetas: {nombre: "Dormitorio principal"}` para la interfaz.

Etiquetas (fase 07b, `RECINTOS_ETIQUETAS` en `build/depto_04_mobiliario.py`): Hall, Living, Cocina, Dormitorio
principal (Dorm1), Segundo dormitorio (Dorm2), Clósets del principal (Paso_D1), Clósets del segundo (Paso_D2),
Baño principal (Bano1), Segundo baño (Bano2), Balcón, Palier y Lavadora (Nicho_LV).

## 6. Entornos locales (`entornos[]`, 2.2)

Mapas de reflejo de un recinto, renderizados en Blender para los metales que se ven de cerca (corrección 07c, ronda 2).
Con el entorno genérico del visor (`RoomEnvironment` de three.js, un estudio con cajas y paneles), el acero cepillado
de la nevera reflejaba cajas que no existen en la cocina (nubes oscuras de 7-15 cm) y la visera de la campana se leía
como latón.

```json
"entornos": [
  {"id": "cocina", "imagen": "tex/entorno_cocina.jpg",
   "imagenes": {"luces": "tex/entorno_cocina.jpg", "dia": "tex/entorno_cocina_dia.jpg"},
   "centro": [0.288, 1.3, 1.660], "caja": [-0.921, 1.878, 0.395, 2.766], "alto": [0.0, 2.4],
   "materiales": ["Depto_Mat_NeveraAcero", "Depto_Mat_Acero", "Depto_Mat_AceroInox"], "grupo": "cocina_techo",
   "escala": {"luces": 8.36, "dia": 35.37}, "muestras": 48, "luces": "luces: grupos que nacen encendidos; dia: sólo el sol y el cielo",
   "mundo": "HDR de día de Poly Haven desaturado a 0,35, fuerza 1,6 (el de los renders de revisión de día)"}
]
```

- `imagenes`: equirectangulares de 512 × 256 (JPEG sRGB, junto a las texturas del modelo), renderizados en Cycles
  (CPU, 48 muestras con eliminación de ruido) desde `centro` (glTF): `luces`, con los grupos que nacen encendidos, y
  `dia`, sólo con el sol y el cielo (sin luces ni emisivos). El visor usa `luces` mientras el grupo `grupo` (la luz del
  recinto) está encendido y `dia` si está apagado. `imagen` repite la de las luces
  para un visor que sólo lea una. El centro de la imagen mira hacia +X de glTF y la derecha hacia +Z, la convención de
  `EquirectangularReflectionMapping`. `escala` es el factor que llevó el percentil 97 de la luminancia a 0,9 antes de
  codificar. Desde la 2.4 el visor lo usa: multiplica la intensidad del entorno de cada variante por
  escala_de_referencia / `escala`, con la escala del render con que se midió esa intensidad
  (`ESCALA_ENTORNO_CALIBRADA` en `web/src/tour/js/cielo.js`). Así, un render nuevo del entorno no cambia el brillo de
  los reflejos. La referencia es la del render con el mundo de los renders de revisión (luces 8,36, día 35,37), contra
  el que se volvió a medir en la corrección 08 (ronda 2). La escala sigue a lo más claro del entorno (el cielo de la
  ventana) y no al promedio que refleja el acero: al entrar el exterior subió 1,6 veces de día y los reflejos de
  Blender no cambiaron. Por eso, cuando cambia mucho, conviene volver a medir. Desde la 2.5 las dos variantes se
  renderizan con el mundo que alumbra los renders de revisión de día (el HDR de día desaturado a 0,35, fuerza 1,6),
  no con el cielo Nishita del maestro: con el cielo saturado por la ventana, el acero del freezer salía azulado en el
  visor.
- `caja` [xmin, xmax, zmin, zmax] (glTF), `alto` [ymin, ymax] y `materiales`: el visor clona esos materiales en las
  mallas cuyo centro cae dentro de la caja (también las móviles, como la puerta de la nevera) y les pone como `envMap`
  el mapa prefiltrado (PMREM) de la variante que toca; su intensidad es la de `entornoLocal` del momento del día para
  esa variante (`web/src/tour/js/cielo.js`, calibrada contra Blender desde las mismas cámaras), corregida por la
  escala (`actualizarEntornos` en `carga.js`, en cada cuadro). El reflejo se proyecta en la caja (paralaje, como las sondas de caja de Eevee): sin
  eso, la visera de la campana, que mira hacia la cubierta y los muebles bajos, reflejaba el piso claro que se ve desde
  el centro. Las demás mallas siguen con el entorno general.
- Lo produce `entorno_cocina()` en `build/depto_06_exportar.py`; lo usan `cargarEntornos` y `prepararEscena` en
  `web/src/tour/js/carga.js`.

## 7. Textiles y plantas (bloque 09; sin campos nuevos, la versión sigue en 2.5)

- Alfombras (`Depto_Mueble_*_Alfombra`, `_Flecos`, `Hall_Camino`, `*_PisoBano`), cortinas (`*_Cortinas_Tela` y
  `_Barra`), hojas de las plantas (`*_Planta_Hojas`) y su tierra traen
  `colision: false` en los extras: no generan cajas en `depto_colisiones.json`. Las macetas sí.
- Las hojas usan materiales `Depto_Mat_Planta*` con `alphaMode: "MASK"`, `alphaCutoff: 0.5` y `doubleSided: true`; su
  color es un PNG con alfa (las únicas imágenes PNG del modelo). GLTFLoader lo resuelve con `alphaTest`; lo que el visor
  debe cuidar es no perder el alfa: `web/tour_modelo.py` genera el `.webp` y la copia del teléfono en RGBA cuando la
  imagen trae alfa (prueba en `web/tests/test_tour_modelo.py`).
- Las hojas abatibles interiores (dormitorios y baños) dejan 2 cm sobre el piso; la de entrada, 1 cm. No cambia nada
  de `moviles[]`.
