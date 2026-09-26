# Contrato de interacción: modelo (Blender) ↔ visor web

Versión 2 (2026-09-26). Lo produce `build/depto_06_exportar.py` en `depto_colisiones.json` y en los `extras` de los nodos glTF (three.js los deja en `object.userData`). Coordenadas en glTF: +Y arriba, frente del depto hacia −Z (Blender (x, y, z) → glTF (x, z, −y); `gl()` en depto_06).

## 1. Móviles (`moviles[]`, ya existe, se amplía)

Cualquier objeto con la propiedad `puerta` (bisagra) o `recorrido_m` (corredera) en Blender se exporta como móvil. Campos existentes: `nodo`, `cajas_locales`, `posicion`, `tipo` (`bisagra` | `corredera`), `angulo`, `angulo_abierto`, `eje`, `recorrido`, `abierta`, `hijos`.

Campos nuevos (propiedades de Blender con el mismo nombre, se copian tal cual):

| Campo | Tipo | Uso |
|---|---|---|
| `clase` | `puerta` \| `ventana` \| `cajon` \| `closet` \| `nevera` \| `mueble` | Icono y texto de la pista; los `cajon` no bloquean el recorrido en las pruebas. |
| `etiqueta` | texto corto en español | Pista del visor: "Abrir cajón de cubiertos". |
| `recinto` | nombre de `recintos` | Para la lista de la interfaz y para apagar la pista fuera del recinto. |

Reglas del modelo:
- El origen del objeto es el eje de giro (bisagra) o el punto de reposo (corredera). El giro de bisagra es en torno a +Z de Blender (+Y de glTF).
- El contenido que debe moverse con la pieza (manilla, ropa en un cajón, estantes de la puerta de la nevera) se emparenta al objeto móvil y aparece en `hijos`.
- Un cajón es una caja abierta arriba (frente + fondo + laterales + piso), no un bloque macizo, para que se vea su interior al abrirse.

## 2. Luces (`luces[]` y `grupos_luz[]`)

Cada luz puntual trae además `grupo` (id de `grupos_luz`), `color` [r, g, b] lineal y `ampolleta` (nombre del nodo emisivo que la representa).

```json
"grupos_luz": [
  {"id": "living_techo", "etiqueta": "Living · techo", "recinto": "Living", "encendido": true},
  {"id": "dorm1_velador_izq", "etiqueta": "Dormitorio 1 · velador izquierdo", "recinto": "Dorm1", "encendido": false}
]
```

- Color cálido por defecto: 2700 K (≈ [1.0, 0.72, 0.42] lineal). Los focos de cocina y baño pueden ir a 3000 K.
- El visor clona el material emisivo de cada `ampolleta` para que cada grupo se apague por separado.

## 3. Interruptores y objetos que prenden luces

Propiedad de Blender `grupo_luz` (texto o lista separada por comas) en cualquier objeto clicable:
- Placas de interruptor en el muro (`Depto_Interruptor_<Recinto>[_n]`, a 1,10 m del piso y 0,10 m del marco de la puerta, del lado de la manilla). Su tecla (`..._Tecla`) es hija y el visor la inclina ±8° al cambiar de estado.
- Lámparas de pie o de velador: la propiedad va en el objeto de la pantalla o del cuerpo.

Se exporta como `interruptores: [{"nodo", "grupos": [...], "tecla": nombre o null}]`. Los `extras` del nodo repiten `grupo_luz` para que el raycast lo reconozca sin buscar en la lista.

## 4. Exterior

`exterior: {"panorama": "tex/<archivo>.jpg", "rotacion_deg": n, "suelo_y": n}`: panorama equirectangular (Poly Haven, CC0) que el visor usa como fondo y como reflejo tenue. En Blender se usa el HDRI equivalente como mundo para los renders de revisión.

## 5. Recintos

`recintos` sigue siendo `{nombre: [x, z]}`. Se agrega `recintos_etiquetas: {nombre: "Dormitorio principal"}` para la interfaz.
