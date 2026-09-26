# Consolidacion Fase 0: escala y conversion a metros.
# Coordenadas = centros de linea subpixel (px continuos) medidos con lines.py / perfiles en esta carpeta.
import math
# ---------- 1) ESCALA ----------
fam = {  # familia: (m/px, bajo, alto)
 'sanitarios': (0.0192, 0.0180, 0.0208),
 'puertas_muros': (0.0188, 0.0175, 0.0203),
 'cocina': (0.0190, 0.0177, 0.0204),
 'mobiliario': (0.0189, 0.0180, 0.0205),
}
print('Interseccion de rangos:', max(v[1] for v in fam.values()), min(v[2] for v in fam.values()))
# Mediciones individuales fuertes: (nombre, px, m_prob, sigma_m)  sigma ~ 1/4 del rango estandar
M = [
 ('fondo meson (2 tramos)', 31.55, 0.60, 0.020),
 ('largo cama (bloque)',    104.9, 2.00, 0.050),
 ('hoja dormitorio',        37.46, 0.725,0.030),
 ('hoja bano',              34.67, 0.675,0.030),
 ('ancho tina',             37.5,  0.70, 0.025),
 ('prof. WC',               36.0,  0.70, 0.035),
 ('mesa centro 1.00x0.60 (media geom.)', math.sqrt(54*32.4), math.sqrt(0.60), 0.06),
 ('sofa 2 cuerpos ancho',   80.7,  1.55, 0.10),
 ('nucleo muro hormigon',   10.45, 0.20, 0.02),
]
num=den=0
for n,px,m,sg in M:
    s=m/px; ss=sg/px; w=1/ss**2; num+=w*s; den+=w
    print(f'{n:40s} {px:7.2f}px -> {s:.5f} m/px (sigma {ss:.5f})')
S=num/den; sig=math.sqrt(1/den)
chi2=sum(((m/px-S)/(sg/px))**2 for n,px,m,sg in M)
print(f'WLS: s={S:.5f} +- {sig:.5f}  chi2={chi2:.2f} gl={len(M)-1}')
ent=0.90/54.29; print(f'entrada 0.90 -> {ent:.5f}  ({(ent-S)/(0.05/54.29):.1f} sigma)')
fm=sum(v[0] for v in fam.values())/4; print('media familias', round(fm,5))
s=0.0190; lo=0.0181; hi=0.0200
# ---------- 2) GEOMETRIA (px, centros de linea) ----------
X=dict(Wo=114.45,Wi=127.45,T3w=289.57,T3e=293.43,T4w=337.37,T4e=341.29,T10w=339.4,T10e=343.36,
       LVw=330.84,LVe=334.68,SH1w=392.25,SH1wi=396.57,SH2w=389.45,SH2wi=393.64,Eforro=418.2,Ei=420.3,Eo=430.8,
       COCw=386.4,jD=249.7,balO=52.3,balF=60.5)
Y=dict(No=13.77,Ncore=24.0,Ni=26.5,T3A=58.82,T3B=123.33,CL1n=59.0,CL1s=123.2,T4A=70.43,T4B=107.28,SH1n=126.7,SH1s=131.16,
       T5n=147.5,T5s=151.29,D1n=170.25,D1s=174.04,T3C=180.91,COCn=298.63,COCs=305.02,entN=306.95,T3D=325.67,LVf=325.57,
       D2n=328.31,D2s=332.14,T9n=363.18,entS=363.39,T9s=367.02,T3E=399.03,CL2n=399.2,T10A=409.32,SH2n=443.38,T10B=445.95,
       SH2s=447.59,T3F=451.77,CL2s=452.0,Si=476.04,So=486.54,balN=163.3,balFn=173.6,balFs=328.1,balS=338.7)
m=lambda px: px*s
def rect(x0,x1,y0,y1): return (x1-x0)*(y1-y0)
ext_w=X['Eo']-X['Wo']; ext_d=Y['So']-Y['No']
print(f"\nEXTERIOR {ext_w:.2f} x {ext_d:.2f} px -> {m(ext_w):.3f} x {m(ext_d):.3f} m ; bruta {m(ext_w)*m(ext_d):.2f} m2 (rango {ext_w*ext_d*lo*lo:.1f}-{ext_w*ext_d*hi*hi:.1f})")
print(f"  bordes de trazo 319 x 474.5 px -> {m(319):.3f} x {m(474.5):.3f}")
walls={'N total (con forro)':Y['Ni']-Y['No'],'N nucleo (relleno)':Y['Ncore']-Y['No'],'O':X['Wi']-X['Wo'],'S':Y['So']-Y['Si'],
       'E nucleo':X['Eo']-X['Ei'],'E con forro (cocina/bano1)':X['Eo']-X['Eforro'],'tabique tipico':3.8,'tabique T_COC_S':6.39,'muro shaft':4.4,
       'tabique borde a borde (trazo)':6.0,'muro S borde a borde':13.0}
for k,v in walls.items(): print(f'  muro {k:32s} {v:6.2f} px -> {m(v):.3f} m')
R={}
R['Dormitorio 1 (area cama)']=(X['T3w']-X['Wi'],Y['D1n']-Y['Ni'])
R['Dormitorio 1 (vestidor/paso)']=(X['T4w']-X['T3e'],Y['CL1s']-Y['CL1n'])
R['Closet D1 sup']=(X['T4w']-X['T3e'],Y['CL1n']-Y['Ni'])
R['Closet D1 inf']=(X['T4w']-X['T3e'],Y['T5n']-Y['CL1s'])
R['Dormitorio 2 (area cama)']=(X['T3w']-X['Wi'],Y['Si']-Y['D2s'])
R['Dormitorio 2 (vestidor/paso)']=(X['T10w']-X['T3e'],Y['CL2s']-Y['CL2n'])
R['Closet D2 sup']=(X['T10w']-X['T3e'],Y['CL2n']-Y['T9s'])
R['Closet D2 inf']=(X['T10w']-X['T3e'],Y['Si']-Y['CL2s'])
R['Living-comedor']=(X['T3e']-X['Wi'],Y['D2n']-Y['D1s'])
R['Cocina']=(X['Eforro']-X['T3e'],Y['COCn']-Y['T5s'])
R['Nicho LV']=(X['LVw']-X['T3e'],Y['T9n']-Y['LVf'])
R['Bano 1 (bbox)']=(X['Eforro']-X['T4e'],Y['T5n']-Y['Ni'])
R['Bano 2 (bbox)']=(X['Ei']-X['T10e'],Y['Si']-Y['T9s'])
R['Balcon (piso util)']=(X['Wo']-X['balF'],Y['balFs']-Y['balFn'])
R['Balcon (losa, bruto)']=(X['Wo']-X['balO'],Y['balS']-Y['balN'])
A={}
for k,(w,d) in R.items():
    A[k]=w*d
# correcciones
A['Living-comedor']-= (X['T3e']-X['T3w'])*((Y['T3C']-Y['D1s'])+(Y['D2n']-Y['T3D']))  # remates de T3
sh1=(X['Eforro']-X['SH1w'])*(Y['T5n']-Y['SH1n']); sh2=(X['Ei']-X['SH2w'])*(Y['Si']-Y['SH2n'])
A['Bano 1 (bbox)']-=sh1; A['Bano 2 (bbox)']-=sh2
hall=rect(X['T3e'],X['Ei'],Y['COCn'],Y['T9n'])-rect(X['COCw'],X['Ei'],Y['COCn'],Y['COCs'])-rect(X['T3e'],X['LVe'],Y['LVf'],Y['T9n'])
A['Hall de acceso']=hall; R['Hall de acceso (bbox)']=(X['Ei']-X['T3e'],Y['T9n']-Y['COCn'])
print()
for k,(w,d) in R.items(): print(f'  {k:32s} {w:7.2f} x {d:7.2f} px -> {m(w):5.2f} x {m(d):5.2f} m')
print()
tot=0
for k,a in A.items():
    am=a*s*s
    if 'Balcon' not in k: tot+=am
    print(f'  AREA {k:32s} {a:9.1f} px2 -> {am:6.2f} m2')
print(f'  SUMA recintos interiores (util neta, sin muros ni shafts, sin balcon): {tot:.2f} m2  (rango {tot*(lo/s)**2:.1f}-{tot*(hi/s)**2:.1f})')
inner=rect(X['Wi'],X['Eforro'],Y['Ni'],Y['entN'])+rect(X['Wi'],X['Ei'],Y['entN'],Y['Si'])
print(f'  Interior entre caras de muros perimetrales (incluye tabiques y shafts): {inner*s*s:.2f} m2')
print(f'  Shafts (bbox con muros): {sh1*s*s:.2f} + {sh2*s*s:.2f} m2')
print(f'  Tabiques/closets aprox = interior - recintos = {(inner*s*s-tot):.2f} m2')
print(f'  Bruta sin balcon {m(ext_w)*m(ext_d):.2f}; con 50% balcon {m(ext_w)*m(ext_d)+0.5*A["Balcon (losa, bruto)"]*s*s:.2f}; con 100% {m(ext_w)*m(ext_d)+A["Balcon (losa, bruto)"]*s*s:.2f}')
# ---------- 3) VANOS ----------
V=[('P_D1 luz (jamba a jamba)',X['T3w']-X['jD']),('P_D1 hoja (radio arco)',37.44),('P_D2 luz',X['T3w']-249.69),('P_D2 hoja',37.48),
   ('P_B1 luz',Y['T4B']-Y['T4A']),('P_B1 hoja',34.68),('P_B2 luz',Y['T10B']-Y['T10A']),('P_B2 hoja',34.66),
   ('P_ENT luz',Y['entS']-Y['entN']),('P_ENT hoja',54.29),('VEN_LIV',328.5-173.96),('V_D1',152.56-56.52),('V_D2',459.61-349.8),
   ('V_B1',373.43-341.65),('VL_D1',Y['T3B']-Y['T3A']),('VL_D2',Y['T3F']-Y['T3E']),('VL cocina+hall->living (T3C a T3D)',Y['T3D']-Y['T3C']),
   ('VL_COC_LIV (T3C a y298.63)',Y['COCn']-Y['T3C']),('VL_HALL_LIV (298.63 a 325.6)',Y['LVf']-Y['COCn']),('VL_COC_HALL (293.43 a 386.4)',X['COCw']-X['T3e']),
   ('CL_D1 frentes',X['T4w']-X['T3e']),('CL_D2 frentes',X['T10w']-X['T3e']),('LV frente',X['LVw']-X['T3e'])]
print()
for k,v in V: print(f'  {k:40s} {v:7.2f} px -> {m(v):.3f} m  [{v*lo:.3f}-{v*hi:.3f}]')
print('\nbaldosa balcon 10.76 px ->', round(10.76*s,3), ' ; 5 baldosas en fondo del balcon =', round(53.95/10.76,2))
print('tina B1 dibujada ~67 x 38 px ->', round(67*s,2), round(38*s,2), '; nicho de tina', round(m(X['Eforro']-X['T4e']),2))
print('meson fondo', round(m(31.55),3), ' muebles altos fondo', round(m(20),3))
print('cama', round(m(96.9),2), round(m(104.9),2))
