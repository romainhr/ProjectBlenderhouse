"""Medidas del plano del departamento (Fase 0). Fuente única para todas las fases del activo `Depto`.

Todo lo que está en píxeles es MEDIDO en ref/plano/plano_depto.png (PNG 500x500, x a la derecha,
y hacia abajo, coordenadas continuas: el píxel i ocupa [i, i+1]). Los valores son centros de línea
subpíxel medidos con perfiles de gris (build/depto_medicion/lines.py y consolidar.py), no bordes de
trazo: el trazo de 1,5 a 2 px engorda los muros entre un 20 y un 45 %.

Todo lo que está en metros sin "px" es INFERIDO o SUPUESTO; el comentario dice de dónde sale.
Ver asset-brief-depto.md para la justificación completa.

Módulo de Python puro (sin bpy ni PIL): lo importan los scripts de Blender y las herramientas.
"""

# ---------------------------------------------------------------------------
# Escala (inferida: el plano no tiene cotas)
# ---------------------------------------------------------------------------
# Cuatro familias independientes coinciden al ±1 %: sanitarios 0,0192, puertas y muros 0,0188,
# cocina 0,0190, mobiliario 0,0189. El ajuste ponderado de 9 referencias da 0,01908 ± 0,00026
# (error estadístico). Incertidumbre total ±5 % mientras no haya una cota real.
M_POR_PX = 0.0190
M_POR_PX_BAJO = 0.0181
M_POR_PX_ALTO = 0.0200

# ---------------------------------------------------------------------------
# Líneas verticales (x, px): centros de línea medidos
# ---------------------------------------------------------------------------
X = dict(
    BAL_O=52.3,      # contorno exterior del balcón
    BARANDA_O=56.2,  # eje de la baranda oeste del balcón, entre las dos líneas finas (verificado en la fase 2: 56,0-56,3)
    BAL_F=60.5,      # borde interior de la franja de baranda del balcón (inicio del piso útil)
    W_O=114.45,      # cara exterior del muro oeste (fachada del balcón)
    W_I=127.45,      # cara interior del muro oeste
    JAMBA_D=249.7,   # remate de los tabiques Dorm/Living: jamba oeste de las puertas de dormitorio
    T3_W=289.57,     # tabique T3 (closets / jamba este de puertas de dormitorio), cara oeste
    T3_E=293.43,     # tabique T3, cara este
    LV_W=330.84,     # tabique este del nicho de lavadora, cara oeste
    LV_E=334.68,     # idem, cara este
    T4_W=337.37,     # tabique closets Dorm1 / Baño 1, cara oeste
    T4_E=341.29,     # idem, cara este
    T10_W=339.4,     # tabique closets Dorm2 / Baño 2, cara oeste
    T10_E=343.36,    # idem, cara este
    V_B1_A=341.65,   # ventana del Baño 1 (muro norte), jamba oeste
    V_B1_B=373.43,   # ventana del Baño 1, jamba este
    COC_W=386.4,     # extremo oeste del tabique corto T_COC_S (retorno de jamba de la entrada)
    SH2_W=389.45,    # shaft del Baño 2, cara oeste
    SH2_WI=393.64,   # shaft del Baño 2, cara interior oeste
    SH1_W=392.25,    # shaft del Baño 1, cara oeste
    SH1_WI=396.57,   # shaft del Baño 1, cara interior oeste
    E_FORRO=418.2,   # cara interior del forro del muro este (tramo cocina y Baño 1)
    E_I=420.3,       # cara interior del muro este (tramo Baño 2)
    E_O=430.8,       # cara exterior del muro este (lado de la entrada)
)

# ---------------------------------------------------------------------------
# Líneas horizontales (y, px): centros de línea medidos
# ---------------------------------------------------------------------------
Y = dict(
    N_O=13.77,       # cara exterior del muro norte
    N_NUCLEO=24.0,   # fin del relleno gris del muro norte
    N_I=26.5,        # cara interior del muro norte
    V_D1_A=56.52,    # ventana Dorm 1, jamba norte
    CL1_N=58.76,     # frente del closet superior Dorm 1 (línea gris; re-medido en la fase 2, antes 59,0)
    T4_A=70.43,      # jamba norte de la puerta del Baño 1 (bisagra)
    T4_B=107.28,     # jamba sur de la puerta del Baño 1
    CL1_S=123.52,    # frente del closet inferior Dorm 1 (re-medido en la fase 2, antes 123,2): paso de 1,23 m
    SH1_N=126.7,     # shaft Baño 1, cara norte
    SH1_S=131.16,    # shaft Baño 1, cara interior norte
    T5_N=147.5,      # tabique T5 (baño 1 / cocina), cara norte
    T5_S=151.29,     # tabique T5, cara sur
    V_D1_B=152.56,   # ventana Dorm 1, jamba sur
    BAL_N=163.3,     # contorno norte del balcón
    BARANDA_N=168.7,  # eje de la baranda norte del balcón (rectángulo fino y 166-170; verificado en la fase 2)
    D1_N=170.25,     # tabique Dorm 1 / Living, cara norte
    BAL_FN=173.6,    # piso útil del balcón, borde norte
    VEN_A=173.96,    # ventanal living, jamba norte
    D1_S=174.04,     # tabique Dorm 1 / Living, cara sur
    T3_C=180.91,     # remate sur del tabique T3 junto a la cocina (inicio de la cocina abierta)
    VEN_ENCUENTRO=229.0,  # encuentro de hojas del ventanal (medido; paño norte ≈1,05 m corredera)
    COC_N=298.63,    # tabique corto T_COC_S, cara norte
    COC_S=305.02,    # tabique corto T_COC_S, cara sur
    ENT_N=306.95,    # puerta de entrada, jamba norte
    LV_F=325.57,     # frente del nicho de lavadora
    T3_D=325.67,     # remate norte del tabique T3 (jamba este puerta Dorm 2)
    BAL_FS=328.1,    # piso útil del balcón, borde sur
    D2_N=328.31,     # tabique Living / Dorm 2, cara norte
    VEN_B=328.5,     # ventanal living, jamba sur
    D2_S=332.14,     # tabique Living / Dorm 2, cara sur
    BARANDA_S=333.2,  # eje de la baranda sur del balcón (rectángulo fino y 331-335; verificado en la fase 2: 333,1-333,4)
    BAL_S=338.7,     # contorno sur del balcón
    V_D2_A=349.8,    # ventana Dorm 2, jamba norte
    T9_N=363.18,     # tabique T9 (hall / baño 2), cara norte
    ENT_S=363.39,    # puerta de entrada, jamba sur (bisagra)
    T9_S=367.02,     # tabique T9, cara sur
    CL2_N=398.96,    # frente del closet superior Dorm 2 (re-medido en la fase 2, antes 399,2)
    T10_A=409.32,    # jamba norte de la puerta del Baño 2 (bisagra)
    SH2_N=446.47,    # shaft Baño 2, cara norte. Corregido en la fase 2 (verificar_lineas.py): la Fase 0 dio 443,38
    T10_B=445.95,    # jamba sur de la puerta del Baño 2
    SH2_S=450.52,    # shaft Baño 2, cara interior norte. Corregido en la fase 2 (la Fase 0 dio 447,59)
    CL2_S=451.94,    # frente del closet inferior Dorm 2 (re-medido en la fase 2, antes 452,0)
    V_D2_B=459.61,   # ventana Dorm 2, jamba sur
    S_I=476.04,      # cara interior del muro sur
    S_O=486.54,      # cara exterior del muro sur
)

# ---------------------------------------------------------------------------
# Hojas de puerta (px): radio del arco de giro, ajuste de circunferencia (rms 0,11-0,13 px)
# ---------------------------------------------------------------------------
HOJA_PX = dict(D1=37.44, D2=37.48, B1=34.68, B2=34.66, ENT=54.29)

# ---------------------------------------------------------------------------
# Alturas: TODAS INFERIDAS (una planta no da alturas). Ver brief, sección Alturas.
# ---------------------------------------------------------------------------
ALTURA_PISO_CIELO = 2.40      # supuesto regional (rango 2,30-2,60 según país; OGUC Chile mín. 2,35)
DINTEL_PUERTAS = 2.05         # hoja comercial de 2,00 m + marco
DINTEL_VENTANAS = 2.10        # ventanas y ventanal alineados, bajo viga
ANTEPECHO_DORMITORIOS = 0.95  # usual 0,90-1,00; no se descarta ventana de piso a cielo
ANTEPECHO_BANO = 1.50         # ventana alta sobre la tina (privacidad)
ALTURA_BARANDA_BALCON = 1.00  # mínimo usual 0,95
DESNIVEL_BALCON = 0.03        # piso del balcón bajo el interior (supuesto)
ALTURA_MESON = 0.90           # estándar 0,85-0,92
MUEBLES_ALTOS_Z = (1.50, 2.10)  # base y tope de los muebles altos de cocina
ESPESOR_LOSA = 0.15           # losas de piso y cielo, palier (supuesto: sólo cierra el volumen)


def m(px):
    """Convierte una distancia en px a metros con la escala adoptada."""
    return px * M_POR_PX


# Origen del activo: centro del rectángulo exterior del departamento (sin balcón), en el suelo.
CENTRO_PX = ((X["W_O"] + X["E_O"]) / 2, (Y["N_O"] + Y["S_O"]) / 2)


def a_blender(x_px, y_px):
    """Punto del plano (px) -> (X, Y) de Blender en metros.

    Convención del proyecto: +Y hacia el frente. El frente del departamento es la fachada del
    balcón (izquierda del plano), así que el plano gira -90°: izquierda del plano -> +Y,
    arriba del plano (Dormitorio 1) -> +X, derecha (entrada) -> -Y. Es una rotación, no un espejo.
    """
    cx, cy = CENTRO_PX
    return ((cy - y_px) * M_POR_PX, (cx - x_px) * M_POR_PX)


def a_plano(x_bl, y_bl):
    """Inversa de a_blender: (X, Y) de Blender en metros -> punto del plano (px)."""
    cx, cy = CENTRO_PX
    return (cx - y_bl / M_POR_PX, cy - x_bl / M_POR_PX)
