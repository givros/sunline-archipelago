import math
import numpy as np
from layout import ISLANDS,PLAZAS,VILLAS,RAILS,xy,pixel
_profiles={}
_rail=np.array([p for r in RAILS for p in r['points']],dtype=float)
def profile(island):
 if island['id'] not in _profiles:
  c=np.array(island['center']);p=np.array(island['shore']);a=np.arctan2(p[:,1]-c[1],p[:,0]-c[0]);r=np.linalg.norm(p-c,axis=1);o=np.argsort(a)
  _profiles[island['id']]=(np.r_[a[o][-1]-2*np.pi,a[o],a[o][0]+2*np.pi],np.r_[r[o][-1],r[o],r[o][0]])
 return _profiles[island['id']]
def radius(island,a):
 aa,rr=profile(island);r=np.interp(a,aa,rr)
 return r*(1+.018*np.sin(7*a+island['seed'])+.012*np.sin(13*a+1))
def island_distance(island,x,y):
 px,py=pixel((x,y));cx,cy=island['center'];a=math.atan2(py-cy,px-cx);return (radius(island,a)-math.hypot(px-cx,py-cy))*.7
def raw_height(island,x,y):
 px,py=pixel((x,y));dist=island_distance(island,x,y)
 if dist<0:return .05+dist*.18
 coastal=(1-math.exp(-max(0,dist)/9))
 h=.05+3.0*coastal
 for hx,hy,hz,rx,ry in island['hills']:
  r=((px-hx)/rx)**2+((py-hy)/ry)**2;h+=hz*math.exp(-r*1.7)*coastal
 h+=coastal*(1.4*math.sin(x*.094+2*math.sin(y*.065))*math.cos(y*.11+math.sin(x*.081))+.3*math.sin(x*.41+2*math.sin(y*.29)))
 return h
def height(island,x,y):
 h=raw_height(island,x,y);px,py=pixel((x,y));dist=island_distance(island,x,y)
 if dist<0:return h
 for p in PLAZAS:
  cx,cy=p['center'];rx,ry=p['radius'];r=math.sqrt(((px-cx)/rx)**2+((py-cy)/ry)**2)
  t=min(1,max(0,(1.25-r)/.38));t=t*t*(3-2*t);h=h*(1-t)+p['level']*t
 for v in VILLAS:
  if abs(px-v[0])>24 or abs(py-v[1])>20:continue
  vx,vy=xy(v);d=math.hypot((x-vx)/1.1,y-vy);t=min(1,max(0,(13-d)/4));t=t*t*(3-2*t)
  target=raw_height(island,vx,vy)
  for p in PLAZAS:
   cx,cy=p['center'];rx,ry=p['radius']
   if ((v[0]-cx)/rx)**2+((v[1]-cy)/ry)**2<1.3:target=p['level']
  h=h*(1-t)+target*t
 # The hill church sits on a real level terrace connected to the main plaza.
 tx,ty=xy((369,657));d=math.sqrt(((x-tx)/1.0)**2+((y-ty)/1.12)**2)
 if d<26:
  t=min(1,max(0,(26-d)/7));t=t*t*(3-2*t);h=h*(1-t)+7.0*t
 # Open rail corridor cut into hills; bridge deck provides support over low land/water.
 d=float(np.sqrt(((_rail[:,:2]-[x,y])**2).sum(axis=1)).min())
 if h>16.95 and d<10:
  t=min(1,max(0,(10-d)/3.5));t=t*t*(3-2*t);h=h*(1-t)+16.95*t
 return h
def at(x,y):
 candidates=[(island_distance(i,x,y),i) for i in ISLANDS];d,i=max(candidates,key=lambda p:p[0]);return height(i,x,y) if d>=0 else -.6
def nearest_island(x,y):return max(ISLANDS,key=lambda i:island_distance(i,x,y))
def build_islands():
 from core import mesh,material,collection
 col=collection('03 • Island terrain')
 sand=material('Warm coral sand',(.76,.67,.43),.9);soil=material('Island forest floor',(.115,.18,.045),.97);stone=material('Weathered limestone',(.28,.30,.265),.88)
 result=[]
 for isle in ISLANDS:
  print('TERRAIN_BUILD',isle['id'],flush=True)
  cx,cy=isle['center'];vs=[];N=384;M=100
  # Concentric authored coast rings preserve reference silhouettes; triangles are actual support geometry.
  for j in range(M+1):
   t=(j+.08)/(M+.08)*1.13
   for k in range(N):
    a=math.tau*k/N;r=radius(isle,a)*t;x,y=xy((cx+math.cos(a)*r,cy+math.sin(a)*r));z=height(isle,x,y);vs.append((x,y,z))
  faces=[]
  for j in range(M):
   for k in range(N):
    a=j*N+k;b=j*N+(k+1)%N;c=(j+1)*N+(k+1)%N;d=(j+1)*N+k;faces.extend([(a,b,c),(a,c,d)])
  ground=material('Continuous coastal terrain', (1,1,1),.94)
  if 'TerrainTint' not in ground.node_tree.nodes:
   node=ground.node_tree.nodes.new('ShaderNodeVertexColor');node.name='TerrainTint';node.layer_name='TerrainTint';ground.node_tree.links.new(node.outputs['Color'],ground.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
  ob=mesh(isle['id'],vs,faces,ground,col,True);ob['walkable']=True;ob['region_id']=isle['id'];ob['material_role']='terrain'
  colors=ob.data.color_attributes.new(name='TerrainTint',type='FLOAT_COLOR',domain='POINT')
  sand_color=np.array([.76,.67,.43]);soil_color=np.array([.095,.17,.038]);rock_color=np.array([.25,.28,.24])
  # Fetch all normals before writing any attribute: a per-vertex color write
  # invalidates Blender's derived mesh cache, making an interleaved loop quadratic.
  coords=np.asarray(vs,dtype=np.float32);normals=np.empty(len(vs)*3,dtype=np.float32);ob.data.vertices.foreach_get('normal',normals);normals=normals.reshape((-1,3))
  px=coords[:,0]/.65+724;py=543-coords[:,1]/.82;angles=np.arctan2(py-cy,px-cx)
  shores=(radius(isle,angles)-np.sqrt((px-cx)**2+(py-cy)**2))*.7
  st=np.clip((shores-5.2)/5.8,0,1);st=st*st*(3-2*st);rt=np.clip((.80-normals[:,2])/.26,0,1)*st
  x=coords[:,0];y=coords[:,1];patch=.94+.10*np.sin(x*.13+1.2*np.sin(y*.14))*np.cos(y*.089+np.sin(x*.085))+.027*np.sin(x*2.1+y*1.13)
  colarray=np.ones((len(vs),4),dtype=np.float32);colarray[:,:3]=((sand_color[None,:]*(1-st[:,None])+soil_color[None,:]*st[:,None])*(1-rt[:,None])+rock_color[None,:]*rt[:,None])*patch[:,None]
  colors.data.foreach_set('color',colarray.ravel());print('TERRAIN_READY',isle['id'],len(vs),flush=True)
  result.append(ob)
 return result
