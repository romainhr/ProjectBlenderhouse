# Contrato de interacción: modelo (Blender) ↔ visor web

Versión 2.1 (2026-09-26; secciones 2, 3 y 5 completadas en la fase 07b; `depende_de`/`bloquea`, color por
temperatura y regla del momento del día agregados en la corrección 07b, ADR 0004). El JSON trae `"version": 2`
(versión mayor: un visor que la entiende puede leer cualquier 2.x e ignorar lo que no conoce) y `"contrato": "2.1"`
(versión completa, desde la ronda 2 de la corrección 07b). Lo produce `build/depto_06_exportar.py` en `depto_colisiones.json` y en los `extras` de los nodos glTF (three.js los deja en `object.userData`). Coordenadas en glTF: +Y arriba, frente del depto hacia −Z (Blender (x, y, z) → glTF (x, z, −y); `gl()` en depto_06).

## 1. Móviles (`moviles[]`, ya existe, se amplía)

Cualquier objeto con la propiedad `puerta` (bisagra) o `recorrido_m` (corredera) en Blender se exporta como móvil. Campos existentes: `nodo`, `cajas_locales`, `posicion`, `tipo` (`bisagra` | `corredera`), `angulo`, `angulo_abierto`, `eje`, `recorrido`, `abierta`, `hijos`.

Campos nuevos (propiedades de Blender con el mismo nombre, se copian tal cual):

| Campo | Tipo | Uso |
|---|---|---|
| `clase` | `puerta` \| `ventana` \| `cajon` \| `closet` \| `nevera` \| `mueble` | Icono y texto de la pista; los `cajon` no bloquean el recorrido en las pruebas. |
| `etiqueta` | texto corto en español | Pista del visor: "Abrir cajón de cubiertos". |
| `recinto` | nombre de `recintos` | Para la lista de la interfaz y para apagar la pista fuera del recinto. |
| `depende_de` | lista de `nodo` (opcional) | Hojas que deben estar corridas para abrir la pieza (cajones de clóset: su hoja A). |
| `bloquea` | lista de `nodo` (opcional) | Piezas que la hoja tapa al moverse (cada hoja de un clóset de repisas: sus cajones). |

Reglas del modelo:
- El origen del objeto es el eje de giro (bisagra) o el punto de reposo (corredera). El giro de bisagra es en torno a +Z de Blender (+Y de glTF).
- El contenido que debe moverse con la pieza (manilla, ropa en un cajón, estantes de la puerta de la nevera) se emparenta al objeto móvil y aparece en `hijos`.
- Un cajón es una caja abierta arriba (frente + fondo + laterales + piso), no un bloque macizo, para que se vea su interior al abrirse.
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
  {"id": "dorm1_velador_izq", "etiqueta": "Dormitorio principal · velador izquierdo", "recinto": "Dorm1", "encendido": false, "kelvin": 2700}
]
```

- `color` es sRGB **lineal** (primarias Rec. 709, blanco D65, canal mayor = 1) y sale de `kelvin`
  (`build/depto_color.py`: radiancia de Planck contra CIE 1931; calculado, no medido): 2700 K ≈ [1.0, 0.42, 0.10] y
  3000 K ≈ [1.0, 0.48, 0.15]. Hasta la corrección 07b se escribía [1.0, 0.72, 0.42], que es el sRGB codificado de
  ~3000 K: usado como lineal daba ~4200 K.
- 2700 K en general; cocina y baños a 3000 K.
- Luces con pantalla (domos de techo, lámpara de arco, colgante del balcón y focos del riel): `cono_deg`
  (semiángulo, 60° en domos y 35° en focos) y `direccion` (vector glTF del eje; hacia abajo en los domos). El
  visor, que no calcula sombras, las arma como un foco (SpotLight) con toda la intensidad; sin eso el cielo sobre un
  domo cerrado recibía ~20 veces la luz del piso. Hasta la ronda 2 de la corrección 07b llevaban además una puntual
  con el 15 % para el rebote en el cielo: se quitó porque cada luz cuesta ~1,3-1,7 ms por cuadro en una GPU
  integrada (ADR 0004, adenda de la ronda 2). Las jaulas, los veladores y los apliques no traen cono. En Blender
  todas son puntuales (la pantalla hace la sombra).
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
| `cocina_techo` | 2 colgantes de jaula | Cocina | 3000 K | sí |
| `hall_techo` | riel de 3 focos | Hall | 2700 K | sí |
| `dorm1_techo` | colgante de domo | Dorm1 | 2700 K | sí |
| `dorm1_velador_izq`, `dorm1_velador_der` | lámparas de mesa (veladores oeste y este; hasta la ronda 2 de la corrección 07b había una sola, `dorm1_velador`) | Dorm1 | 2700 K | no |
| `paso_d1` | colgante de jaula de cable corto (nuevo en 07b) | Paso_D1 | 2700 K | sí |
| `dorm2_techo` | colgante de domo | Dorm2 | 2700 K | sí |
| `dorm2_aplique_izq`, `dorm2_aplique_der` | apliques de brazo (este y oeste) | Dorm2 | 2700 K | no |
| `paso_d2` | colgante de jaula de cable corto (nuevo en 07b) | Paso_D2 | 2700 K | sí |
| `bano1`, `bano2` | colgante de jaula | Bano1, Bano2 | 3000 K | sí |
| `balcon` | colgante de domo Ø 0,28 sobre la mesa bistró, bajo la losa del balcón de arriba (nuevo en 07b) | Balcon | 2700 K | sí |

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

## 4. Exterior

`exterior: {"panorama": "tex/<archivo>.jpg", "rotacion_deg": n, "suelo_y": n}`: panorama equirectangular (Poly Haven, CC0) que el visor usa como fondo y como reflejo tenue. En Blender se usa el HDRI equivalente como mundo para los renders de revisión.

## 5. Recintos

`recintos` sigue siendo `{nombre: [x, z]}`. Se agrega `recintos_etiquetas: {nombre: "Dormitorio principal"}` para la interfaz.

Etiquetas (fase 07b, `RECINTOS_ETIQUETAS` en `build/depto_04_mobiliario.py`): Hall, Living, Cocina, Dormitorio
principal (Dorm1), Segundo dormitorio (Dorm2), Clósets del principal (Paso_D1), Clósets del segundo (Paso_D2),
Baño principal (Bano1), Segundo baño (Bano2), Balcón, Palier y Lavadora (Nicho_LV).
