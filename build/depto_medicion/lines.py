# Centros de linea subpixel (coordenadas continuas: pixel i ocupa [i,i+1], centro i+0.5)
from PIL import Image
import sys
import os
g=Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ref', 'plano', 'plano_depto.png')).convert('L')
W,H=g.size
def prof(axis,fixed,a,b):
    if axis=='x':  # recorrer x con y fijo
        return [(i,g.getpixel((i,fixed))) for i in range(a,b)]
    return [(i,g.getpixel((fixed,i))) for i in range(a,b)]
def runs(axis,fixed,a,b,thr=200):
    p=prof(axis,fixed,a,b); out=[]; cur=[]
    for i,v in p:
        if v<thr: cur.append((i,v))
        else:
            if cur: out.append(cur); cur=[]
    if cur: out.append(cur)
    res=[]
    for r in out:
        w=[(255-v) for i,v in r]; s=sum(w)
        c=sum((i+0.5)*wi for (i,v),wi in zip(r,w))/s
        res.append((round(c,2), r[0][0], r[-1][0]+1, min(v for i,v in r)))
    return res
if __name__=='__main__':
    axis=sys.argv[1]; fixed=int(sys.argv[2]); a=int(sys.argv[3]); b=int(sys.argv[4]); thr=int(sys.argv[5]) if len(sys.argv)>5 else 200
    for r in runs(axis,fixed,a,b,thr): print(r)
