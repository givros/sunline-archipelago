from pathlib import Path
import json,math,sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
sys.path.insert(0,str(Path(__file__).parent))
from layout import *
def make_layout():
 im=Image.new('RGB',(1448,1086),'#0d5776');d=ImageDraw.Draw(im)
 palette=['#81bc67','#44ac6c','#7ab57b','#a4b869','#dacb6a','#f1d3a0','#9eb378','#bf9b57','#77bc95','#99b959']
 for i,r in enumerate(ISLANDS):
  d.polygon([tuple(p) for p in r['shore']],fill=palette[i],outline='#f9e2b5',width=3)
  p=tuple(r['center']);d.text((p[0]-35,p[1]),r['name'],fill='white',stroke_width=1,stroke_fill='#173d39')
 for route in [MAIN_RAIL_PIXELS,SOUTH_RAIL_PIXELS,NORTH_SPUR_PIXELS]:
  p=[tuple(p) for p in route];d.line(p,fill='#273c42',width=10);d.line(p,fill='#f1ebe0',width=4)
 for a in STILT_DISTRICTS:
  d.line([tuple(a['shore']),tuple(a['hub'])],fill='#d2a572',width=4)
  for h in a['houses']:
   d.line([tuple(a['hub']),tuple(h)],fill='#d2a572',width=3);d.rectangle([h[0]-8,h[1]-6,h[0]+8,h[1]+6],fill='#d47548')
 for h in VILLAS:d.rectangle([h[0]-8,h[1]-6,h[0]+8,h[1]+6],fill='#f3cf9b',outline='#8b6244')
 for a in DOCKS:d.line([tuple(p) for p in a['points']],fill='#d5aa79',width=4)
 for b in BOATS:d.ellipse([b[0]-4,b[1]-3,b[0]+4,b[1]+3],fill='#f8f2dd')
 d.rectangle([18,1020,673,1068],fill='#103c4d');d.text((32,1036),'REFERENCE-TRACED LAYOUT  |  10 islands  /  connected rail  /  6 stilt districts',fill='#fff1d7')
 im.save(ROOT/'semantic_layout.png')
 return im
def comparison(right,name,label):
 ref=Image.open(ROOT/'references/primary_layout.png').convert('RGB'); right=right.resize(ref.size)
 sheet=Image.new('RGB',(2896,1130),'#132d35');sheet.paste(ref,(0,44));sheet.paste(right,(1448,44));d=ImageDraw.Draw(sheet)
 d.text((24,16),'PRIMARY REFERENCE',fill='white');d.text((1470,16),label,fill='white');sheet.save(ROOT/f'comparisons/{name}.png')
def ocean_texture():
 # Full-resolution bathymetric color field, authored from the same coast polygons.
 n=4096; extent=1450.; coords=np.linspace(-extent/2,extent/2,n,dtype=np.float32)
 xx,yy=np.meshgrid(coords,coords[::-1]); px=xx/.65+724;py=543-yy/.82
 depth=np.full((n,n),200,np.float32)
 for island in ISLANDS:
  pts=island['shore'];cx,cy=island['center']; angles=np.arctan2(np.array(pts)[:,1]-cy,np.array(pts)[:,0]-cx); rs=np.sqrt((np.array(pts)[:,0]-cx)**2+(np.array(pts)[:,1]-cy)**2);order=np.argsort(angles);angles=angles[order];rs=rs[order]
  a=np.arctan2(py-cy,px-cx);r=np.interp(a,np.r_[angles[-1]-2*np.pi,angles,angles[0]+2*np.pi],np.r_[rs[-1],rs,rs[0]])
  dist=(np.sqrt((px-cx)**2+(py-cy)**2)-r)*.7; depth=np.minimum(depth,dist)
 noise=np.zeros_like(xx)
 rng=np.random.default_rng(907)
 for res,weight in [(22,.34),(64,.24),(150,.22),(370,.13),(890,.07)]:
  small=Image.fromarray((rng.random((res,res))*255).astype('uint8'));noise+=np.asarray(small.resize((n,n),Image.Resampling.BICUBIC),dtype=np.float32)/255*weight
 # Irregular reef shelves; channels remain deep blue between islands.
 dist=depth+(noise-.5)*36
 t=np.clip(dist/78,0,1)
 deep=np.array([24,114,153],np.float32); shallow=np.array([45,202,196],np.float32)
 col=shallow[None,None,:]*(1-t[:,:,None])+deep[None,None,:]*t[:,:,None]
 # Soft, granular coral colonies: no binary contour rings around noise bands.
 detail=Image.fromarray((rng.random((1800,1800))*255).astype('uint8'))
 grain=np.asarray(detail.resize((n,n),Image.Resampling.BICUBIC),dtype=np.float32)/255
 colony_field=np.zeros_like(noise)
 for res,weight in [(150,.45),(370,.35),(890,.20)]:
  small=Image.fromarray((rng.random((res,res))*255).astype('uint8'))
  colony_field+=np.asarray(small.resize((n,n),Image.Resampling.BICUBIC),dtype=np.float32)/255*weight
 colony_noise=noise*.15+colony_field*.85
 colony=np.clip((colony_noise-.487)*7+(grain-.5)*.8,0,1)
 colony=colony*colony*(3-2*colony)
 reef=colony*np.clip(1-np.abs(dist-24)/64,0,1)
 col*=1-reef[:,:,None]*.32
 # Sand streaks in water, fine dapple and subtle coherent caustics.
 sand=np.clip((.46-noise)*15,0,1)*np.clip(1-np.maximum(dist,0)/36,0,1)
 col=col*(1-sand[:,:,None]*.25)+np.array([115,210,191])[None,None,:]*sand[:,:,None]*.25
 fine=(np.sin(xx*2.7+np.sin(yy*.91))*np.sin(yy*2.1+np.sin(xx*.72)))
 col+=fine[:,:,None]*1.4+(noise[:,:,None]-.5)*14+(grain[:,:,None]-.5)*4
 Image.fromarray(np.clip(col,0,255).astype('uint8')).save(ROOT/'references/ocean_bathymetry.png')
if __name__=='__main__':
 write_spec();im=make_layout();comparison(im,'01_boundaries','CHECKPOINT 01 • traced boundaries and reservations')
 ocean_texture()
