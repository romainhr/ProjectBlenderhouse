"""Pruebas de la cadena de sellos (build/depto_sellos.py), sin Blender.

Uso: python3 build/depto_medicion/test_sellos.py   (sale con código 1 si alguna falla)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import depto_sellos as S  # noqa: E402


def leer_con(nombre_modificado):
    def leer(nombre):
        datos = S._leer(nombre)
        return datos + b"\n# cambio" if nombre == nombre_modificado else datos
    return leer


def main():
    fallos = []
    base = {f: S.sello(f) for f in S.FASES}
    # 1) Un cambio en un archivo de la fase 1 cambia los sellos de todas las fases siguientes.
    for archivo in S.FASES["01"]:
        otro = {f: S.sello(f, leer_con(archivo)) for f in S.FASES}
        if any(otro[f] == base[f] for f in S.FASES):
            fallos.append(f"cambiar {archivo} no invalida todas las fases: {otro} vs {base}")
    # 2) Un cambio en la fase 3 no toca los sellos de las fases 1 y 2.
    otro = {f: S.sello(f, leer_con("depto_03_formas.py")) for f in S.FASES}
    if otro["01"] != base["01"] or otro["02"] != base["02"] or otro["03"] == base["03"]:
        fallos.append("un cambio en la fase 3 afecta sellos previos o no cambia el suyo")
    # 3) Sellar la fase 2 borra el sello de la fase 3 (reejecutar una fase previa invalida las siguientes).
    escena = {"depto_fase01": base["01"], "depto_fase02": base["02"], "depto_fase03": base["03"]}
    S.sellar(escena, "02")
    if "depto_fase03" in escena or escena["depto_fase02"] != base["02"]:
        fallos.append(f"sellar('02') no dejó la escena como se espera: {escena}")
    # 3b) La fase 08 (exterior) va entre la 05 y la 06: cambiarla cambia su sello y el de la 06, no el de la 05; sellar
    #     la 05 borra el de la 08.
    otro = {f: S.sello(f, leer_con("depto_08_exterior.py")) for f in S.FASES}
    if otro["05"] != base["05"] or otro["08"] == base["08"] or otro["06"] == base["06"]:
        fallos.append("un cambio en la fase 08 no cambia sólo los sellos de la 08 y la 06")
    if sorted(S.ORDEN) != sorted(S.FASES):
        fallos.append(f"ORDEN {S.ORDEN} no tiene las mismas fases que FASES")
    escena = {"depto_fase05": base["05"], "depto_fase08": base["08"]}
    S.sellar(escena, "05")
    if "depto_fase08" in escena:
        fallos.append("sellar('05') no borró el sello de la fase 08")
    # 4) exigir: acepta la cadena vigente, rechaza un sello viejo y una ruta distinta del maestro.
    escena = {"depto_fase02": base["02"]}
    try:
        S.exigir(escena, "02", S.MAESTRO)
    except SystemExit as e:
        fallos.append(f"exigir rechazó un maestro válido: {e}")
    for esc, ruta, motivo in (({"depto_fase02": "viejo"}, S.MAESTRO, "sello viejo"),
                              ({"depto_fase02": base["02"]}, "/tmp/blenderhouse_watch/VISTA_depto.blend", "copia")):
        try:
            S.exigir(esc, "02", ruta)
            fallos.append(f"exigir aceptó {motivo}")
        except SystemExit:
            pass
    for f in fallos:
        print("FALLA", f)
    print("SELLOS_OK" if not fallos else f"SELLOS: {len(fallos)} fallas", base)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
